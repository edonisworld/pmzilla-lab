"""
Masquage de v_team_flow_inout (migration 0031, mothra-slices tâche 36.1, exception F12) par masquer_vue : primaire (sous le seuil), ligne du produit
visible seulement si chaque cellule d'équipe de sa colonne l'est (masking-sums D3, décision Q8), famille = même trimestre et même groupe de types.
Données inventées (équipes A à D), aucun compte réel.

    uv run --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/flow_views -v

Les relations avec d'autres vues (T13 et les trois de D35) ne sont pas implémentées ici : voir l'en-tête de la migration.
"""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402

NOMS = ["team", "quarter_start", "type_group", "created", "done"]
T1, T2 = "2026-01-01", "2026-04-01"
PRODUIT = "(produit)"
SANS = "(sans équipe)"


def masquee(cell) -> bool:
    return "masked" in cell and cell["value"] is None


def masques(lignes, seuil=fv.PLANCHER):
    return [(masquee(c["created"]), masquee(c["done"])) for c in fv.masquer_vue("v_team_flow_inout", NOMS, lignes, seuil)]


class Declarations(unittest.TestCase):
    def test_la_vue_est_dans_la_liste_fermee_avec_ses_bornes(self):
        self.assertIn("v_team_flow_inout", fv.VUES)
        self.assertEqual(fv.VUE_FLUX, "v_team_flow_inout")
        self.assertEqual(fv.BORNES["v_team_flow_inout"], {"created": (0, False), "done": (0, False)})
        for colonne in ("created", "done"):
            self.assertIn(colonne, fv.COLONNES_COMPTE)

    def test_team_et_type_group_ne_sont_jamais_masques(self):
        cellules = fv.masquer_vue("v_team_flow_inout", NOMS, [("A", T1, "story", 3, 3)], fv.PLANCHER)[0]
        self.assertEqual((cellules["team"], cellules["quarter_start"], cellules["type_group"]),
                         ({"value": "A"}, {"value": T1}, {"value": "story"}))

    def test_la_sorte_de_vue_se_deduit_des_colonnes(self):
        self.assertEqual(fv.masquer_vue(None, NOMS, [("A", T1, "story", 3, 9)], fv.PLANCHER),
                         fv.masquer_vue("v_team_flow_inout", NOMS, [("A", T1, "story", 3, 9)], fv.PLANCHER))


class Primaire(unittest.TestCase):
    def test_sous_le_seuil_un_a_quatre_et_zero_masques_cinq_rendu(self):
        for n in (0, 1, 4):
            self.assertEqual(masques([("A", T1, "story", n, 9)])[0], (True, False), n)
        self.assertEqual(masques([("A", T1, "story", 5, 5)])[0], (False, False))

    def test_un_nul_de_la_vue_est_une_cellule_cachee(self):
        self.assertEqual(masques([("A", T1, "story", None, 9)])[0], (True, False))

    def test_au_seuil_releve_cinq_a_neuf_sont_masques(self):
        self.assertEqual(masques([("A", T1, "story", 7, 12)], seuil=10)[0], (True, False))


class LigneDuProduit(unittest.TestCase):
    def test_produit_masque_quand_une_cellule_d_equipe_de_sa_colonne_est_masquee(self):
        lignes = [("A", T1, "story", 20, 9), ("B", T1, "story", 3, 8), (PRODUIT, T1, "story", 23, 17)]
        self.assertEqual(masques(lignes), [(False, False), (True, False), (True, False)])

    def test_produit_visible_quand_toutes_les_cellules_d_equipe_le_sont(self):
        lignes = [("A", T1, "story", 20, 9), ("B", T1, "story", 6, 8), (PRODUIT, T1, "story", 26, 17)]
        self.assertEqual(masques(lignes), [(False, False)] * 3)

    def test_la_ligne_sans_equipe_compte_comme_une_equipe(self):
        lignes = [("A", T1, "defect", 20, 20), (SANS, T1, "defect", 2, 9), (PRODUIT, T1, "defect", 22, 29)]
        self.assertEqual(masques(lignes), [(False, False), (True, False), (True, False)])

    def test_la_famille_est_le_trimestre_et_le_groupe_de_types(self):
        lignes = [("A", T1, "story", 3, 9), ("A", T1, "defect", 9, 9), ("A", T2, "story", 9, 9),
                  (PRODUIT, T1, "defect", 9, 9), (PRODUIT, T2, "story", 9, 9), (PRODUIT, T1, "story", 3, 9)]
        self.assertEqual(masques(lignes), [(True, False), (False, False), (False, False), (False, False), (False, False), (True, False)])

    def test_produit_sans_aucune_ligne_d_equipe_est_masque(self):
        self.assertEqual(masques([(PRODUIT, T1, "story", 40, 40)]), [(True, True)])

    def test_produit_dont_la_propre_cellule_est_sous_le_seuil_est_masque(self):
        self.assertEqual(masques([("A", T1, "story", 20, 20), (PRODUIT, T1, "story", 4, 20)])[1], (True, False))

    def test_aucune_cellule_masquee_n_a_de_valeur(self):
        lignes = [("A", T1, "story", 3, 9), ("B", T1, "story", 8, 9), (PRODUIT, T1, "story", 11, 18)]
        for cellules in fv.masquer_vue("v_team_flow_inout", NOMS, lignes, fv.PLANCHER):
            for colonne in ("created", "done"):
                if masquee(cellules[colonne]):
                    self.assertEqual(set(cellules[colonne]), {"value", "masked", "threshold"})

    def test_au_seuil_releve_la_famille_suit_le_seuil(self):
        lignes = [("A", T1, "story", 20, 20), ("B", T1, "story", 7, 12), (PRODUIT, T1, "story", 27, 32)]
        self.assertEqual(masques(lignes, seuil=10), [(False, False), (True, False), (True, False)])


if __name__ == "__main__":
    unittest.main()
