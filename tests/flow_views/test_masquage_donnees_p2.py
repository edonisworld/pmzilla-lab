"""
Preuve sans base des données du dbtest de la photo (change masking-sums, R-144 ; diagnostic du 2026-11-04 sur les 7 erreurs « intervalle vide dans la
lecture où m est libre »).

    bash tests/run_all.sh flow_views

Les tests de tests/db fournissaient des données que D15 déclare impossibles : un trouvé plus grand que les défauts distincts (créés - sans affects), donc
P2 « D_r >= f_v » vide (design.md D15 ; flow_views._epingles). Ici, sans base, masquer_vue au plancher reçoit :
  - les lignes d'origine de `jeu_complet` (tests/db/test_flow_version_photo_views.py) : MasquageInstable, échec fermé, rien n'est publié ;
  - les mêmes lignes corrigées (créés 28 par équipe, donc D = 20 = trouvé) : aucune exception ;
  - les trois jeux corrigés de remplir_semaines (tests/db/test_masquage_somme_vues.py, deux versions par semaine) : aucune exception. Le diagnostic ne
    les avait pas simulés à la main ; ce test en est la vérification.
Chiffres inventés ; aucune ligne du Jira réel.
"""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402

NOMS_PHOTO = ["week_start", "n_adopted", "team", "version_no", "found", "defects_created", "defects_without_affects", "resolved_week",
              "resolved_week_defects"]
MESSAGE = "intervalle vide dans la lecture où m est libre"
LUNDI = "2026-11-02"


def jeu_complet(crees):
    """La semaine retenue de `jeu_complet` : trois équipes (un trouvé de 20 pour une version, une ligne sans version) et la ligne du produit, somme des
    équipes (D3), dans le format de NOMS_PHOTO."""
    lignes = []
    for equipe in ("Alpha", "Beta", "Gamma"):
        lignes.append((LUNDI, True, equipe, 1, 20, None, None, None, None))
        lignes.append((LUNDI, True, equipe, None, None, crees, 8, 20, 6))
    lignes.append((LUNDI, True, "(produit)", 1, 60, None, None, None, None))
    lignes.append((LUNDI, True, "(produit)", None, None, 3 * crees, 24, 60, 18))
    return lignes


def semaines_db(equipes, lundis):
    """Reproduit remplir_semaines de tests/db/test_masquage_somme_vues.py : deux versions par semaine, un trouvé par version dans l'ordre, la ligne du
    produit étant la somme des équipes (D3 ; résolus 20 et 10 par équipe)."""
    lignes = []
    for rang, lundi in enumerate(lundis):
        nos = [2 * rang + 1, 2 * rang + 2]
        somme_trouves = {no: None for no in nos}
        crees_p = sans_p = 0
        for equipe, par_semaine in equipes.items():
            crees, sans, trouves = par_semaine[rang]
            for no, found in zip(nos, trouves or ()):
                lignes.append((lundi, True, equipe, no, found, None, None, None, None))
                somme_trouves[no] = (somme_trouves[no] or 0) + found
            lignes.append((lundi, True, equipe, None, None, crees, sans, 20, 10))
            crees_p += crees
            sans_p += sans
        for no, total in somme_trouves.items():
            if total is not None:
                lignes.append((lundi, True, "(produit)", no, total, None, None, None, None))
        lignes.append((lundi, True, "(produit)", None, None, crees_p, sans_p, 20 * len(equipes), 10 * len(equipes)))
    return lignes


LUNDIS = ["2026-11-02", "2026-12-07", "2027-01-11"]


class DonneesDuDbtest(unittest.TestCase):
    def test_les_lignes_d_origine_de_jeu_complet_donnent_un_intervalle_vide(self):
        """Créés 20, sans affects 8 : D = 12 pour un trouvé de 20 (P2 : D >= f vide). Le produit : D = 36 pour un trouvé de 60."""
        with self.assertRaisesRegex(fv.MasquageInstable, MESSAGE):
            fv.masquer_vue(fv.VUE_PHOTO, NOMS_PHOTO, jeu_complet(20), fv.PLANCHER)

    def test_jeu_complet_corrige_ne_leve_aucune_exception(self):
        """Créés 28 par équipe (D = 20 = trouvé) ; le produit : 84 - 24 = 60 = trouvé."""
        lignes = jeu_complet(28)
        cellules = fv.masquer_vue(fv.VUE_PHOTO, NOMS_PHOTO, lignes, fv.PLANCHER)
        self.assertEqual(len(cellules), len(lignes))

    def test_d3_avant_d5_d_corrige_ne_leve_aucune_exception(self):
        equipes = {"A": [(40, 5, (25, 20)), (3, 0, None), (40, 5, (25, 20))],
                   "B": [(10, 5, (5, 5)), (52, 5, (30, 27)), (18, 5, (12, 11))]}
        lignes = semaines_db(equipes, LUNDIS)
        self.assertEqual(len(fv.masquer_vue(fv.VUE_PHOTO, NOMS_PHOTO, lignes, fv.PLANCHER)), len(lignes))

    def test_d5_d_avant_d2_corrige_ne_leve_aucune_exception(self):
        equipes = {"A": [(30, 15, (10, 10)), (45, 25, (15, 10))], "B": [(30, 15, (10, 10)), (25, 8, (12, 10))]}
        lignes = semaines_db(equipes, LUNDIS[:2])
        self.assertEqual(len(fv.masquer_vue(fv.VUE_PHOTO, NOMS_PHOTO, lignes, fv.PLANCHER)), len(lignes))

    def test_d3_avant_d2_corrige_ne_leve_aucune_exception(self):
        equipes = {"A": [(30, 3, None)], "B": [(40, 27, (13,))]}
        lignes = semaines_db(equipes, LUNDIS[:1])
        self.assertEqual(len(fv.masquer_vue(fv.VUE_PHOTO, NOMS_PHOTO, lignes, fv.PLANCHER)), len(lignes))


if __name__ == "__main__":
    unittest.main()
