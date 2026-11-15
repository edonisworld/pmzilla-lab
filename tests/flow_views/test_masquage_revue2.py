"""
Seconde revue R-144 (M2, M3) : départage des égalités par (valeur, identifiant Jira) et ligne à compléter dont sans affects est déjà nul.

    bash tests/run_all.sh flow_views

Chiffres inventés.
"""
import sys
import unittest
import unittest.mock
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402

NOMS_EQUIPES = ["team", "team_type", "tickets"]
NOMS_IDS = ["team", "jira_team_id", "tickets"]
NOMS_PHOTO = ["week_start", "n_adopted", "team", "version_no", "found", "defects_created", "defects_without_affects", "resolved_week",
              "resolved_week_defects"]


class DepartageDesIdentifiants(unittest.TestCase):
    """Le départage joue dans le complément : nom publié, un identifiant déjà masqué (idc), le plus petit visible est masqué à son tour."""

    def masques(self, ids, compte):
        liees = {"v_teams": (NOMS_EQUIPES, [("N", None, compte)])}
        cellules = fv.masquer_vue("v_team_jira_ids", NOMS_IDS, ids, 5, liees=liees)
        return [c["jira_team_id"]["value"] for c in cellules if "masked" in c["tickets"]]

    def test_egalite_departagee_par_l_identifiant_et_non_par_la_position_de_ligne(self):
        self.assertEqual(self.masques([("N", "idb", 6), ("N", "ida", 6), ("N", "idc", None)], 16), ["ida", "idc"])
        self.assertEqual(self.masques([("N", "ida", 6), ("N", "idb", 6), ("N", "idc", None)], 16), ["ida", "idc"])

    def test_la_valeur_prime_sur_l_identifiant(self):
        self.assertEqual(self.masques([("N", "ida", 9), ("N", "idb", 6), ("N", "idc", None)], 17), ["idb", "idc"])

    def test_nom_masque_tous_les_identifiants_visibles_sont_masques(self):
        self.assertEqual(self.masques([("N", "ida", 9), ("N", "idb", 6)], None), ["ida", "idb"])


class LigneAcompleterSansAffectsNul(unittest.TestCase):
    def test_sans_affects_nul_de_la_vue_les_defauts_crees_sont_masques_au_seuil_releve(self):
        """Brut à T = 10 : créés 25, sans affects 5, trouvés 18 et 2 ; la vue au plancher publie 25, null, 18, null. Somme cachée 25 - 18 = 7 sous 10."""
        lignes = [("2026-03-02", True, "A", None, None, 25, None, 20, 10),
                  ("2026-03-02", True, "A", 1, 18, None, None, None, None),
                  ("2026-03-02", True, "A", 2, None, None, None, None, None)]
        cellules = fv.masquer_vue(fv.VUE_PHOTO, NOMS_PHOTO, lignes, 10)
        self.assertIn("masked", cellules[0]["defects_created"])


class PointFixeDeLaRegleComplementaire(unittest.TestCase):
    """Décision du 2026-10-27 : D2 est repassée jusqu'à un point fixe ; la limite de passes atteinte lève une erreur, rien n'est publié."""
    LIGNES = [("2026-03-02", True, "A", None, None, 20, 8, 20, 10),
              ("2026-03-02", True, "A", 1, 12, None, None, None, None)]

    def test_la_limite_se_calcule_depuis_le_nombre_de_semaines_de_la_serie(self):
        """2 x W + 1 : au plus 2 x W passes qui changent (deux cellules par semaine, la visibilité ne passant que de vrai à faux), puis une stable."""
        for semaines in (0, 1, 2, 9, 30):
            self.assertEqual(fv.passes_max(semaines), 2 * semaines + 1)

    def test_deux_passes_masquent_sans_affects_puis_les_crees(self):
        cellules = fv.masquer_vue(fv.VUE_PHOTO, NOMS_PHOTO, self.LIGNES, 5)
        self.assertEqual(("masked" in cellules[0]["defects_without_affects"], "masked" in cellules[0]["defects_created"]), (True, True))

    def test_limite_atteinte_erreur_et_rien_de_publie(self):
        with unittest.mock.patch.object(fv, "passes_max", lambda semaines: 1):
            with self.assertRaises(fv.MasquageInstable):
                fv.masquer_vue(fv.VUE_PHOTO, NOMS_PHOTO, self.LIGNES, 5)

    def test_limite_suffisante_pas_d_erreur(self):
        with unittest.mock.patch.object(fv, "passes_max", lambda semaines: 3):
            fv.masquer_vue(fv.VUE_PHOTO, NOMS_PHOTO, self.LIGNES, 5)

    def test_serie_longue_de_trente_semaines_passe(self):
        # M3 (R-20261104-6) : deux versions par semaine (donnée cohérente : le trouvé 'crees - sans + 10' d'une seule version dépassait les défauts
        # distincts), donc 90 lignes au lieu de 60 ; les trouvés valent D et 10, leur somme D + 10 est celle d'avant.
        lignes = []
        for k in range(30):
            semaine = f"2026-{1 + k // 4:02d}-{1 + 7 * (k % 4):02d}"
            crees, sans = 40 + 10 * k, 5
            lignes += [(semaine, True, "A", None, None, crees, sans, 20, 10), (semaine, True, "A", 1, crees - sans, None, None, None, None),
                       (semaine, True, "A", 2, 10, None, None, None, None)]
        cellules = fv.masquer_vue(fv.VUE_PHOTO, NOMS_PHOTO, lignes, 5)
        self.assertEqual(len(cellules), 90)
        self.assertNotIn("masked", cellules[0]["defects_created"])


if __name__ == "__main__":
    unittest.main()
