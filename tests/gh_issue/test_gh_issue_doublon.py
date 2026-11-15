"""
Tests de tools/gh_issue.py : fermeture en doublon, --duplicate-of de close-idea et close-feature (groupe 6, change
gh-issue-autonomy, design D7). Même faux gh que test_gh_issue.py.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q -f
"""
import json
import unittest
from pathlib import Path

from test_gh_issue import Base, rm

MARQUEUR = "<!-- roadmap-duplicate -->"


class FermetureEnDoublon(Base):
    def idee(self, state="open", slug="une-idee"):
        return self.add_issue("R-1", "Une idée", ["type:idea"], body=f"{rm.idea_marker(slug)}\n\ntexte", state=state)

    def raw(self, n):
        return next(i for i in self.load()["issues"] if i["number"] == n)

    def commentaires(self, n):
        return [c["body"] for c in self.load().get("comments", []) if c["issue"] == n]

    def patchs(self):
        return [json.loads(c["stdin"]) for c in self.calls(writes_only=True) if "PATCH" in c["args"]]

    def cible(self):
        return self.add_issue("R-2", "Autre idée", ["type:idea"], body=f"{rm.idea_marker('autre')}\n\ntexte")

    # --- close-idea --------------------------------------------------------------------------------------------------

    def test_idee_fermee_en_doublon_commentaire_puis_fermeture(self):
        idee, cible = self.idee(), self.cible()
        code, out, err = self.run_cli("close-idea", str(idee["number"]), "--duplicate-of", str(cible["number"]))
        self.assertEqual(code, 0, err)
        self.assertIn(f"closed #{idee['number']} as duplicate of #{cible['number']}", out)
        self.assertEqual(self.commentaires(idee["number"]), [f"{MARQUEUR}\nDuplicate of #{cible['number']}"])
        fermee = self.raw(idee["number"])
        self.assertEqual((fermee["state"], fermee["state_reason"]), ("closed", "duplicate"))
        self.assertEqual(fermee["duplicate_issue_id"], cible["id"])
        ecritures = self.calls(writes_only=True)
        self.assertIn("comments", " ".join(ecritures[0]["args"]))      # le commentaire d'abord
        self.assertIn("PATCH", ecritures[1]["args"])

    def test_idee_rejeu_rien_a_faire(self):
        idee, cible = self.idee(), self.cible()
        self.run_cli("close-idea", str(idee["number"]), "--duplicate-of", str(cible["number"]))
        avant = len(self.calls(writes_only=True))
        code, out, err = self.run_cli("close-idea", str(idee["number"]), "--duplicate-of", str(cible["number"]))
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.calls(writes_only=True)), avant)

    def test_idee_rejeu_poste_le_commentaire_manquant_une_fois(self):
        idee, cible = self.idee(), self.cible()
        self.run_cli("close-idea", str(idee["number"]), "--duplicate-of", str(cible["number"]))
        self.st = self.load()
        self.st["comments"] = []      # une exécution interrompue avant le commentaire
        self.save()
        for _ in range(2):
            code, out, err = self.run_cli("close-idea", str(idee["number"]), "--duplicate-of", str(cible["number"]))
            self.assertEqual(code, 0, err)
            self.assertIn("nothing to do", out)
        self.assertEqual(len(self.commentaires(idee["number"])), 1)
        self.assertEqual(len(self.patchs()), 1)

    def test_idee_fermee_pour_une_autre_raison(self):
        idee, cible = self.idee(state="closed"), self.cible()
        code, _, err = self.run_cli("close-idea", str(idee["number"]), "--duplicate-of", str(cible["number"]))
        self.assertEqual(code, 7, err)
        self.assertIn("is already closed; nothing was sent", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_refus_idee_sans_ecriture(self):
        idee, cible = self.idee(), self.cible()
        n, c = str(idee["number"]), str(cible["number"])
        cas = [("soi-même", (n, "--duplicate-of", n), 2, "cannot be a duplicate of itself"),
               ("cible inconnue", (n, "--duplicate-of", "99"), 7, "unknown issue #99"),
               ("avec comment-file", (n, "--duplicate-of", c, "--comment-file", str(Path(self.tmp.name) / "x")), 2, "usage:"),
               ("valeur non numérique", (n, "--duplicate-of", "abc"), 2, "usage:")]
        for nom, argv, code_attendu, message in cas:
            with self.subTest(nom):
                code, _, err = self.run_cli("close-idea", *argv)
                self.assertEqual(code, code_attendu, err)
                self.assertIn(message, err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_close_idea_sans_option_inchange(self):
        idee = self.idee()
        self.assertEqual(self.run_cli("close-idea", str(idee["number"]))[0], 0)
        self.assertEqual(self.raw(idee["number"])["state_reason"], "completed")

    # --- close-feature -----------------------------------------------------------------------------------------------

    def feature_ouverte(self, n=1, **kw):
        return self.add_feature(n, status="Todo", **kw)

    def test_feature_doublon_sans_done_ni_done_on(self):
        f = self.feature_ouverte(1)
        cible = self.feature_ouverte(2)
        code, out, err = self.run_cli("close-feature", "R-1", "--duplicate-of", str(cible["number"]))
        self.assertEqual(code, 0, err)
        self.assertIn(f"closed R-1 as duplicate of #{cible['number']}", out)
        corps = self.raw(f["number"])
        self.assertEqual((corps["state"], corps["state_reason"]), ("closed", "duplicate"))
        self.assertNotIn("done_on", rm.parse_block(corps["body"]))
        self.assertEqual(self.status_of("R-1"), "Todo")
        self.assertNotIn("edition:public", [l["name"] for l in corps["labels"]])
        self.assertEqual(self.commentaires(f["number"]), [f"{MARQUEUR}\nDuplicate of #{cible['number']}"])

    def test_feature_rejeu_et_commentaire_manquant(self):
        f, cible = self.feature_ouverte(1), self.feature_ouverte(2)
        self.run_cli("close-feature", "R-1", "--duplicate-of", str(cible["number"]))
        self.st = self.load()
        self.st["comments"] = []
        self.save()
        code, out, err = self.run_cli("close-feature", "R-1", "--duplicate-of", str(cible["number"]))
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.commentaires(f["number"])), 1)
        self.assertEqual(self.run_cli("close-feature", "R-1", "--duplicate-of", str(cible["number"]))[0], 0)
        self.assertEqual(len(self.commentaires(f["number"])), 1)

    def test_feature_refus_sans_ecriture(self):
        f, cible = self.feature_ouverte(1), self.feature_ouverte(2)
        n, c = f["number"], str(cible["number"])
        fichier = Path(self.tmp.name) / "c.txt"
        fichier.write_text("x", encoding="utf-8")
        cas = [("soi-même", ("--duplicate-of", str(n)), 2, "cannot be a duplicate of itself"),
               ("cible inconnue", ("--duplicate-of", "99"), 7, "unknown issue #99"),
               ("avec --reason", ("--duplicate-of", c, "--reason", "dropped", "--comment-file", str(fichier)), 2, "usage:"),
               ("avec --after-merge", ("--duplicate-of", c, "--after-merge", "--comment-file", str(fichier)), 2, "usage:"),
               ("avec --edition-public", ("--duplicate-of", c, "--edition-public"), 2, "usage:")]
        for nom, argv, code_attendu, message in cas:
            with self.subTest(nom):
                code, _, err = self.run_cli("close-feature", "R-1", *argv)
                self.assertEqual(code, code_attendu, err)
                self.assertIn(message, err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_feature_sous_issue_ouverte_refusee(self):
        f, cible = self.feature_ouverte(1), self.feature_ouverte(2)
        t = self.add_issue("R-1/u1", "R-1 · Étape", ["type:task", "owner:user"], milestone="Hydra")
        self.st = self.load()
        self.st["sub"] = {str(f["number"]): [t["number"]]}
        self.save()
        code, _, err = self.run_cli("close-feature", "R-1", "--duplicate-of", str(cible["number"]))
        self.assertEqual(code, 7, err)
        self.assertIn("open sub-issues remain:", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_feature_fermee_autrement(self):
        f = self.add_feature(1, state="closed", status="Done", done_on="2026-10-01")
        cible = self.feature_ouverte(2)
        code, _, err = self.run_cli("close-feature", "R-1", "--duplicate-of", str(cible["number"]))
        self.assertEqual(code, 7, err)
        self.assertIn("is already closed; nothing was sent", err)
        self.assertEqual(self.calls(writes_only=True), [])


if __name__ == "__main__":
    unittest.main()
