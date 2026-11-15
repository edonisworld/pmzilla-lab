"""
Les règles de masquage lisent leurs bornes dans BORNES (revue R-144, M3) et la vue de la part du verdict passe par masquer_vue (m5).

    uv run --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/flow_views -q -f

Pour chaque règle, un cas où la décision change quand on change la borne de BORNES (lo ou drapeau de complément) : une règle qui coderait
« seuil - 1 » ou le drapeau en dur ne réagirait pas. Chiffres inventés.
"""
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402

NOMS_RETARD = ["team", "quarter_start", "items", *fv.SEAUX_RETARD]
NOMS_EQUIPES = ["team", "team_type", "tickets"]
NOMS_IDS = ["team", "jira_team_id", "tickets"]
NOMS_PHOTO = ["week_start", "n_adopted", "team", "version_no", "found", "defects_created", "defects_without_affects", "resolved_week",
              "resolved_week_defects"]


def masquees(sorties, colonnes):
    return [[i, c] for i, cellules in enumerate(sorties) for c in colonnes if "masked" in cellules[c]]


def retard(items, tranches):
    ligne = ("A", "2026-04-01", items, *tranches)
    return masquees(fv.masquer_vue(fv.VUE_RETARD, NOMS_RETARD, [ligne], 5), fv.SEAUX_RETARD)


def avec_bornes(vue, colonnes, borne):
    """BORNES où toutes les colonnes données de la vue ont la borne donnée (lo, complément)."""
    return mock.patch.dict(fv.BORNES, {vue: {**fv.BORNES[vue], **{c: borne for c in colonnes}}})


class RetardLitBornes(unittest.TestCase):
    def test_le_drapeau_de_complement_est_lu_dans_bornes(self):
        # items 26 = 6 + 5 + 5 + deux tranches masquées de somme 10 : avec le complément, la borne haute est max(4, 5) = 5 et 10 = 2 x 5
        tranches = [None, None, 6, 5, 5]
        self.assertEqual(retard(26, tranches), [[0, "before_or_at_resolution"], [0, "within_7_days"], [0, "later"], [0, "no_history"]])
        with avec_bornes(fv.VUE_RETARD, fv.SEAUX_RETARD, (0, False)):                  # sans complément : borne haute 4, 10 n'est pas 8
            self.assertEqual(retard(26, tranches), [[0, "before_or_at_resolution"], [0, "within_7_days"]])

    def test_la_borne_basse_est_lue_dans_bornes(self):
        tranches = [None, None, 6, 6, 6]                                                  # S = 10 ; borne haute 4 sans complément
        with avec_bornes(fv.VUE_RETARD, fv.SEAUX_RETARD, (0, False)):
            self.assertEqual(retard(28, tranches), [[0, "before_or_at_resolution"], [0, "within_7_days"]])
        with avec_bornes(fv.VUE_RETARD, fv.SEAUX_RETARD, (5, False)):                    # deux cellules de borne basse 5 : 10 = somme des bornes basses
            self.assertIn([0, "within_30_days"], retard(28, tranches))


class IdentifiantsLitBornes(unittest.TestCase):
    def sorties(self):
        equipes = [("N", None, 14)]
        ids = [("N", "id1", None), ("N", "id2", None), ("N", "id3", 6)]
        liees = {"v_teams": (NOMS_EQUIPES, equipes)}
        return masquees(fv.masquer_vue("v_team_jira_ids", NOMS_IDS, ids, 5, liees=liees), ["tickets"])

    def test_le_drapeau_de_complement_est_lu_dans_bornes(self):
        self.assertEqual(self.sorties(), [[0, "tickets"], [1, "tickets"]])                 # la borne haute est 6 : 8 n'est pas 12
        with avec_bornes("v_team_jira_ids", ("tickets",), (1, False)):                    # borne haute 4 : 8 = 2 x 4, le 6 est masqué à son tour
            self.assertEqual(self.sorties(), [[0, "tickets"], [1, "tickets"], [2, "tickets"]])


class PhotoLitBornes(unittest.TestCase):
    def sorties(self, creees, sans):
        lignes = [("2026-03-02", True, "A", None, None, creees, sans, 20, 10),
                  ("2026-03-02", True, "A", 1, None, None, None, None, None),
                  ("2026-03-02", True, "A", 2, None, None, None, None, None)]
        return masquees(fv.masquer_vue(fv.VUE_PHOTO, NOMS_PHOTO, lignes, 5), ["defects_created", "defects_without_affects"])

    def test_la_borne_basse_des_trouves_est_lue_dans_bornes(self):
        self.assertEqual(self.sorties(32, 22), [])                                         # 10 n'est ni 0 ni 8
        with avec_bornes(fv.VUE_PHOTO, ("found",), (5, False)):                           # deux termes de borne basse 5 : 10 = somme des bornes basses
            self.assertEqual(self.sorties(32, 22), [[0, "defects_without_affects"]])

    def test_somme_des_bornes_hautes_du_cas_b1(self):
        self.assertEqual(self.sorties(30, 22), [[0, "defects_without_affects"]])           # 8 = 2 x 4


class VerdictPartPasseParMasquerVue(unittest.TestCase):
    NOMS = ["team", "quarter_start", "items", "with_fix_version", "share_percent"]
    TRIMESTRES = (date(2025, 10, 1), date(2026, 1, 1), date(2026, 4, 1), date(2026, 7, 1))
    REFERENCE = date(2026, 10, 27)

    def lignes(self):
        return [("A", q, 40, 20, 50.0) for q in self.TRIMESTRES]

    def test_verdict_part_applique_masquer_vue_a_la_vue_de_la_part(self):
        with mock.patch.object(fv, "masquer_vue", wraps=fv.masquer_vue) as espion:
            fv.verdict_part(self.NOMS, self.lignes(), 40, 5, reference=self.REFERENCE)
        self.assertTrue(espion.called, "verdict_part lit la vue de la part sans passer par masquer_vue")
        self.assertEqual(espion.call_args.args[0], fv.VUE_PART)

    def test_une_cellule_que_masquer_vue_masque_n_entre_pas_dans_le_verdict(self):
        """Seuil relevé à 25 : les 20 avec fix version et les 20 sans sont sous le seuil, la part n'établit rien ; au seuil 5 elle établit."""
        self.assertEqual(fv.verdict_part(self.NOMS, self.lignes(), 40, 5, reference=self.REFERENCE)["verdict"], "homogeneous")
        self.assertEqual(fv.verdict_part(self.NOMS, self.lignes(), 40, 25, reference=self.REFERENCE)["verdict"], "not_established")


if __name__ == "__main__":
    unittest.main()
