"""
Tests de tools/gh_issue.py : --no-milestone de edit, edit-task et edit-idea (groupe 4, change gh-issue-autonomy, design D5).
Même faux gh que test_gh_issue.py.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q -f
"""
import json
import unittest

from test_gh_issue import Base, rm


class SansJalon(Base):
    def setUp(self):
        super().setUp()
        self.add_feature(1, status="Todo")
        self.st = self.load()
        self.ouverte = self.add_issue("R-1/u1", "R-1 · Ouverte", ["type:task", "owner:user"], milestone="Hydra")
        self.fermee = self.add_issue("R-1/g1", "R-1 · Fermée", ["type:task", "owner:user"], state="closed", milestone="Hydra")
        self.idee = self.add_issue("R-1", "Une idée", ["type:idea"], body=f"{rm.idea_marker('une-idee')}\n\ntexte", milestone="Hydra")
        self.st = self.load()
        self.st["sub"] = {str(self.number_of("R-1")): [self.ouverte["number"], self.fermee["number"]]}
        self.save()

    def jalon_de(self, n):
        m = next(i for i in self.load()["issues"] if i["number"] == n)["milestone"]
        return m["title"] if m else None

    def patchs(self):
        return [c for c in self.calls(writes_only=True) if "PATCH" in c["args"]]

    # --- edit R-<n> --------------------------------------------------------------------------------------------------

    def test_feature_et_sous_issues_ouvertes_ou_fermees(self):
        jalons = self.load()["milestones"]
        code, out, err = self.run_cli("edit", "R-1", "--no-milestone")
        self.assertEqual(code, 0, err)
        self.assertIn("removed milestone from R-1", out)
        self.assertIn("removed milestone from 2 sub-issue(s)", out)
        self.assertIsNone(self.milestone_of("R-1"))
        self.assertIsNone(self.jalon_de(self.ouverte["number"]))
        self.assertIsNone(self.jalon_de(self.fermee["number"]))
        self.assertEqual(self.load()["milestones"], jalons)      # le jalon lui-même reste
        for c in self.calls(writes_only=True):
            self.assertFalse(any("/milestones" in a for a in c["args"]))
        for p in self.patchs():
            self.assertIsNone(json.loads(p["stdin"])["milestone"])

    def test_deuxieme_lancement_rien_a_faire(self):
        self.run_cli("edit", "R-1", "--no-milestone")
        avant = len(self.calls(writes_only=True))
        code, out, err = self.run_cli("edit", "R-1", "--no-milestone")
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.calls(writes_only=True)), avant)

    def test_feature_sans_jalon_dont_une_sous_issue_en_a_un(self):
        self.run_cli("edit", "R-1", "--no-milestone")
        self.st = self.load()
        for i in self.st["issues"]:
            if i["number"] == self.ouverte["number"]:
                i["milestone"] = {"title": "Hydra", "number": 1}
        self.save()
        code, out, err = self.run_cli("edit", "R-1", "--no-milestone")
        self.assertEqual(code, 0, err)
        self.assertIn("removed milestone from 1 sub-issue(s)", out)
        self.assertIsNone(self.jalon_de(self.ouverte["number"]))

    def test_avec_un_autre_champ_une_seule_requete_pour_la_feature(self):
        code, _, err = self.run_cli("edit", "R-1", "--no-milestone", "--title", "Nouveau")
        self.assertEqual(code, 0, err)
        feature = self.number_of("R-1")
        payload = next(json.loads(p["stdin"]) for p in self.patchs() if any(a.endswith(f"/issues/{feature}") for a in p["args"]))
        self.assertIn("title", payload)
        self.assertIsNone(payload["milestone"])

    # --- feature fermée (décision R-20261103-36, Q7) -------------------------------------------------------------------

    def test_feature_fermee_garde_son_jalon_code_7(self):
        f = self.add_feature(2, state="closed", status="Done", done_on="2026-10-01")
        t = self.add_issue("R-2/u1", "R-2 · Étape", ["type:task", "owner:user"], state="closed", milestone="Hydra")
        self.st = self.load()
        self.st["sub"][str(f["number"])] = [t["number"]]
        self.save()
        code, out, err = self.run_cli("edit", "R-2", "--no-milestone")
        self.assertEqual(code, 7, err)
        for morceau in ("R-2 is closed: a delivered feature keeps its release's milestone", "reopen-feature R-2 --reason R",
                        "edit R-2 --milestone M", "close it again", "nothing was sent"):
            self.assertIn(morceau, err)
        self.assertEqual(self.calls(writes_only=True), [])
        self.assertEqual(self.milestone_of("R-2"), "Hydra")
        self.assertEqual(self.jalon_de(t["number"]), "Hydra")

    def test_feature_fermee_sans_jalon_code_7_aussi(self):
        self.add_feature(2, state="closed", status="Done", milestone=None, done_on="2026-10-01")
        code, _, err = self.run_cli("edit", "R-2", "--no-milestone")
        self.assertEqual(code, 7, err)      # la fermée est refusée avant tout, comme les autres commandes d'écriture sur une issue fermée
        self.assertEqual(self.calls(writes_only=True), [])

    def test_feature_ouverte_inchangee(self):
        code, out, err = self.run_cli("edit", "R-1", "--no-milestone")
        self.assertEqual(code, 0, err)
        self.assertIsNone(self.milestone_of("R-1"))

    # --- exclusion avec --milestone ----------------------------------------------------------------------------------

    def test_exclusif_avec_milestone_code_2(self):
        for argv in (("edit", "R-1"), ("edit-task", "R-1/u1"), ("edit-idea", str(self.idee["number"]))):
            with self.subTest(argv[0]):
                code, _, err = self.run_cli(*argv, "--milestone", "Namazu", "--no-milestone")
                self.assertEqual(code, 2, err)
                self.assertIn("usage:", err)
        self.assertEqual(self.calls(writes_only=True), [])

    # --- edit-task ---------------------------------------------------------------------------------------------------

    def test_edit_task_retire_le_jalon_d_une_tache_seule(self):
        code, out, err = self.run_cli("edit-task", "R-1/u1", "--no-milestone")
        self.assertEqual(code, 0, err)
        self.assertIn("removed milestone from R-1/u1", out)
        self.assertIsNone(self.jalon_de(self.ouverte["number"]))
        self.assertEqual(self.milestone_of("R-1"), "Hydra")
        self.assertEqual(self.jalon_de(self.fermee["number"]), "Hydra")
        self.assertEqual(len(self.patchs()), 1)
        code, out, err = self.run_cli("edit-task", "R-1/u1", "--no-milestone")
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.patchs()), 1)

    def test_nouvelle_cle_deja_unique_n_empeche_pas_no_milestone(self):
        n = self.ouverte["number"]
        code, out, err = self.run_cli("edit-task", "--numero", str(n), "--nouvelle-cle", "--no-milestone")
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do", out)
        self.assertIn("unique key", out)
        self.assertIsNone(self.jalon_de(n))

    def test_nouvelle_cle_deja_unique_n_empeche_pas_body_file(self):
        from pathlib import Path
        n = self.ouverte["number"]
        f = Path(self.tmp.name) / "corps.md"
        f.write_text("Texte réécrit", encoding="utf-8")
        code, out, err = self.run_cli("edit-task", "--numero", str(n), "--nouvelle-cle", "--body-file", str(f))
        self.assertEqual(code, 0, err)
        self.assertIn("unique key", out)
        corps = next(i for i in self.load()["issues"] if i["number"] == n)["body"]
        self.assertIn("Texte réécrit", corps)
        self.assertEqual(rm.parse_marker(corps), "R-1/u1")

    def test_edit_task_fermee_refusee_code_2(self):
        code, _, err = self.run_cli("edit-task", "R-1/g1", "--no-milestone")
        self.assertEqual(code, 2, err)
        self.assertIn("is closed; edit-task works on an open task", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_edit_task_par_numero(self):
        code, _, err = self.run_cli("edit-task", "--numero", str(self.ouverte["number"]), "--no-milestone")
        self.assertEqual(code, 0, err)
        self.assertIsNone(self.jalon_de(self.ouverte["number"]))

    # --- edit-idea ---------------------------------------------------------------------------------------------------

    def test_edit_idea_retire_le_jalon(self):
        n = str(self.idee["number"])
        code, out, err = self.run_cli("edit-idea", n, "--no-milestone")
        self.assertEqual(code, 0, err)
        self.assertIsNone(self.jalon_de(self.idee["number"]))
        self.assertEqual(len(self.patchs()), 1)
        self.assertEqual(json.loads(self.patchs()[0]["stdin"]), {"milestone": None})
        avant = len(self.calls(writes_only=True))
        code, out, err = self.run_cli("edit-idea", n, "--no-milestone")
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.calls(writes_only=True)), avant)

    def test_edit_idea_avec_un_titre(self):
        code, _, err = self.run_cli("edit-idea", str(self.idee["number"]), "--no-milestone", "--title", "Autre titre")
        self.assertEqual(code, 0, err)
        self.assertEqual(len(self.patchs()), 1)
        self.assertIsNone(self.jalon_de(self.idee["number"]))

    def test_edit_idea_sans_option_message_inchange(self):
        code, _, err = self.run_cli("edit-idea", str(self.idee["number"]))
        self.assertEqual(code, 2, err)


if __name__ == "__main__":
    unittest.main()
