"""
Tests de tools/gh_issue.py : commande horizon, champ Horizon du Project (groupe 4, change gh-issue-autonomy, design D4).
Le faux Project reçoit un champ Horizon (single select V2, V3, V4, Plus tard). Même faux gh que test_gh_issue.py.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q -f
"""
import unittest

from test_gh_issue import Base, rm

HORIZONS = [{"id": "h1", "name": "V2"}, {"id": "h2", "name": "V3"}, {"id": "h3", "name": "V4"}, {"id": "h4", "name": "Plus tard"}]
PHRASE_6 = "Project has no Horizon field or its options are incomplete; nothing was sent"


class Horizon(Base):
    def setUp(self):
        super().setUp()
        self.avec_champ()
        self.add_feature(1, status="Todo")
        self.st = self.load()
        self.tache = self.add_issue("R-1/u1", "R-1 · Étape", ["type:task", "owner:user"], milestone="Hydra")
        self.idee = self.add_issue("R-1", "Une idée", ["type:idea"], body=f"{rm.idea_marker('une-idee')}\n\ntexte")
        self.fermee = self.add_feature(2, state="closed", status="Done", done_on="2026-10-01")

    def avec_champ(self, options=HORIZONS):
        self.st = self.load()
        self.st["project"]["horizon_field_id"] = "F_H"
        self.st["project"]["horizon_options"] = options
        self.save()

    def sans_champ(self):
        self.st = self.load()
        self.st["project"].pop("horizon_field_id", None)
        self.save()

    def item(self, n):
        return next((i for i in self.load()["project"]["items"] if i["number"] == n), None)

    # --- lecture -----------------------------------------------------------------------------------------------------

    def test_lecture_none_puis_valeur(self):
        code, out, err = self.run_cli("horizon", "R-1")
        self.assertEqual(code, 0, err)
        self.assertIn("gh_issue: horizon R-1 none", out)
        self.assertEqual(self.run_cli("horizon", "R-1", "V3")[0], 0)
        code, out, err = self.run_cli("horizon", "R-1")
        self.assertIn("gh_issue: horizon R-1 V3", out)

    def test_la_lecture_n_ecrit_rien(self):
        self.run_cli("horizon", "R-1")
        self.run_cli("horizon", str(self.idee["number"]))
        self.assertEqual(self.calls(writes_only=True), [])

    def test_lecture_d_une_issue_fermee_admise(self):
        code, out, err = self.run_cli("horizon", "R-2")
        self.assertEqual(code, 0, err)
        self.assertIn("horizon R-2 none", out)

    # --- écriture ----------------------------------------------------------------------------------------------------

    def test_ecriture_sur_une_feature(self):
        code, out, err = self.run_cli("horizon", "R-1", "V2")
        self.assertEqual(code, 0, err)
        self.assertIn("horizon R-1 V2", out)
        self.assertEqual(self.item(self.number_of("R-1"))["horizon"], "V2")
        self.assertEqual(self.status_of("R-1"), "Todo")      # le Status reste
        for c in self.calls(writes_only=True):
            self.assertIn("graphql", c["args"])      # aucune requête REST d'écriture

    def test_valeur_avec_espace(self):
        self.assertEqual(self.run_cli("horizon", "R-1", "Plus tard")[0], 0)
        self.assertEqual(self.item(self.number_of("R-1"))["horizon"], "Plus tard")

    def test_valeur_passee_par_la_garde_des_noms(self):
        self.names.write_text("# fixture\nzorglub\nV3\n", encoding="utf-8")      # une valeur que la liste de noms sensibles retiendrait
        code, out, err = self.run_cli("horizon", "R-1", "V3")
        self.assertEqual(code, 3, err)
        self.assertIn("sensitive name in horizon", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_status_ne_demande_jamais_horizon(self):
        self.assertEqual(self.run_cli("status", "R-1", "Ready")[0], 0)
        for c in self.calls():
            self.assertNotIn("Horizon", c["stdin"] or "")

    def test_issue_ni_feature_ni_idee_message_juste(self):
        autre = self.add_issue("R-9", "Autre", [], body="rien")
        code, _, err = self.run_cli("horizon", str(autre["number"]))
        self.assertEqual(code, 2, err)
        self.assertIn("usage: horizon works on a feature or an idea", err)
        self.assertNotIn("task", err)

    def test_idee_ajoutee_au_project(self):
        n = self.idee["number"]
        self.assertIsNone(self.item(n))
        code, out, err = self.run_cli("horizon", f"#{n}", "V4")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.item(n)["horizon"], "V4")
        self.assertIsNone(self.item(n).get("status"))      # le Status de l'idée reste vide
        code, out, err = self.run_cli("horizon", str(n))
        self.assertIn("V4", out)

    def test_meme_valeur_rien_a_faire(self):
        self.run_cli("horizon", "R-1", "V2")
        avant = len(self.calls(writes_only=True))
        code, out, err = self.run_cli("horizon", "R-1", "V2")
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.calls(writes_only=True)), avant)

    def test_changement_de_valeur(self):
        self.run_cli("horizon", "R-1", "V2")
        self.assertEqual(self.run_cli("horizon", "R-1", "V3")[0], 0)
        self.assertEqual(self.item(self.number_of("R-1"))["horizon"], "V3")

    # --- refus -------------------------------------------------------------------------------------------------------

    def test_tache_refusee_code_2(self):
        for argv in (("horizon", "R-1/u1"), ("horizon", str(self.tache["number"])), ("horizon", str(self.tache["number"]), "V2")):
            with self.subTest(argv):
                code, _, err = self.run_cli(*argv)
                self.assertEqual(code, 2, err)
                self.assertIn("usage: horizon works on a feature or an idea; a task follows its feature", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_issue_fermee_en_ecriture_code_7(self):
        code, _, err = self.run_cli("horizon", "R-2", "V2")
        self.assertEqual(code, 7, err)
        self.assertIn("R-2 is closed; its horizon is not changed", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_valeur_inconnue_code_2(self):
        code, _, err = self.run_cli("horizon", "R-1", "V9")
        self.assertEqual(code, 2, err)
        self.assertIn("usage: horizon must be one of V2, V3, V4, Plus tard", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_issue_inconnue_code_7(self):
        code, _, err = self.run_cli("horizon", "999")
        self.assertEqual(code, 7, err)
        code, _, err = self.run_cli("horizon", "R-77")
        self.assertEqual(code, 7, err)

    def test_champ_absent_code_6_et_status_toujours_utilisable(self):
        self.sans_champ()
        for argv in (("horizon", "R-1"), ("horizon", "R-1", "V2")):
            with self.subTest(argv):
                code, _, err = self.run_cli(*argv)
                self.assertEqual(code, 6, err)
                self.assertIn(PHRASE_6, err)
        self.assertEqual(self.calls(writes_only=True), [])
        code, out, err = self.run_cli("status", "R-1", "Ready")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.status_of("R-1"), "Ready")

    def test_option_manquante_code_6(self):
        self.avec_champ(HORIZONS[:3])      # sans « Plus tard »
        code, _, err = self.run_cli("horizon", "R-1", "V2")
        self.assertEqual(code, 6, err)
        self.assertIn(PHRASE_6, err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_les_autres_commandes_ignorent_le_champ(self):
        self.sans_champ()
        code, _, err = self.run_cli("status", "R-1", "In progress")
        self.assertEqual(code, 0, err)


if __name__ == "__main__":
    unittest.main()
