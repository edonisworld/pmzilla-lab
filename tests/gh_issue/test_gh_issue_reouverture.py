"""
Tests de tools/gh_issue.py : reopen-idea et reopen-feature (groupe 7, change gh-issue-autonomy, design D8). Même faux gh que
test_gh_issue.py.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q -f
"""
import json
import unittest

from test_gh_issue import Base, NAME, rm

MARQUEUR = "<!-- roadmap-reopened -->"


class Reouverture(Base):
    def idee(self, state="open", milestone=None):
        return self.add_issue("R-1", "Une idée", ["type:idea"], body=f"{rm.idea_marker('une-idee')}\n\ntexte", state=state,
                              milestone=milestone)

    def raw(self, n):
        return next(i for i in self.load()["issues"] if i["number"] == n)

    def commentaires(self, n):
        return [c["body"] for c in self.load().get("comments", []) if c["issue"] == n]

    def feature_fermee(self, n=1, milestone="Hydra", **kw):
        return self.add_feature(n, state="closed", status="Done", milestone=milestone, done_on="2026-10-01", **kw)

    # --- reopen-idea -------------------------------------------------------------------------------------------------

    def test_idee_commentaire_puis_reouverture(self):
        idee = self.idee(state="closed")
        n = idee["number"]
        code, out, err = self.run_cli("reopen-idea", str(n), "--reason", "fermée par erreur")
        self.assertEqual(code, 0, err)
        self.assertIn(f"reopened #{n}", out)
        self.assertEqual(self.commentaires(n), [f"{MARQUEUR}\nReopened: fermée par erreur"])
        self.assertEqual(self.raw(n)["state"], "open")
        ecritures = self.calls(writes_only=True)
        self.assertIn("comments", " ".join(ecritures[0]["args"]))
        self.assertIn("PATCH", ecritures[1]["args"])

    def test_idee_deja_ouverte_rien_a_faire(self):
        idee = self.idee()
        code, out, err = self.run_cli("reopen-idea", f"#{idee['number']}", "--reason", "x")
        self.assertEqual(code, 0, err)
        self.assertIn(f"nothing to do: #{idee['number']} is already open", out)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_idee_refus_sans_ecriture(self):
        idee = self.idee(state="closed")
        n = str(idee["number"])
        autre = self.add_issue("R-9", "x", [], body="rien", state="closed")
        cas = [("motif vide", (n, "--reason", "  "), 2, "usage:"),
               ("pas une idée", (str(autre["number"]), "--reason", "x"), 7, "not an idea"),
               ("numéro mal formé", ("abc", "--reason", "x"), 2, "usage:"),
               ("garde", (n, "--reason", f"voir {NAME}"), 3, "sensitive name")]
        for nom, argv, code_attendu, message in cas:
            with self.subTest(nom):
                code, out, err = self.run_cli("reopen-idea", *argv)
                self.assertEqual(code, code_attendu, err)
                self.assertIn(message, err)
                self.no_leak(out, err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_idee_jalon_ferme(self):
        idee = self.idee(state="closed", milestone="Tarasque")
        code, _, err = self.run_cli("reopen-idea", str(idee["number"]), "--reason", "x")
        self.assertEqual(code, 7, err)
        self.assertIn("closed milestone: a reopened issue would sit in it; nothing was sent", err)
        self.assertEqual(self.calls(writes_only=True), [])

    # --- reopen-feature ----------------------------------------------------------------------------------------------

    def test_feature_done_on_retire_et_status_todo(self):
        f = self.feature_fermee(1)
        code, out, err = self.run_cli("reopen-feature", "R-1", "--reason", "fermée par erreur")
        self.assertEqual(code, 0, err)
        self.assertIn("reopened R-1", out)
        corps = self.raw(f["number"])
        self.assertEqual(corps["state"], "open")
        self.assertNotIn("done_on", rm.parse_block(corps["body"]))
        self.assertEqual(self.status_of("R-1"), "Todo")
        self.assertEqual(self.commentaires(f["number"]), [f"{MARQUEUR}\nReopened: fermée par erreur"])
        self.assertEqual(rm.validate_block(rm.parse_block(corps["body"]), is_open=True, marker_key="R-1"), [])

    def test_feature_rang_libre_attribue_et_rang_pris_refuse(self):
        self.add_feature(2, rank=20)
        f = self.feature_fermee(1)
        self.assertEqual(self.run_cli("reopen-feature", "R-1", "--reason", "x")[0], 0)
        rang = rm.parse_block(self.raw(f["number"])["body"])["rank"]
        self.assertNotEqual(rang, 20)
        bloc = {"id": "R-3", "theme": "outillage", "estimate": "1h", "method": "openspec", "model": "sonnet", "conditions": "",
                "rank": 20, "done_on": "2026-10-01"}
        g = self.add_issue("R-3", "R-3 · Feature 3", ["type:feature", "theme:outillage"], state="closed", milestone="Hydra", block=bloc)
        code, _, err = self.run_cli("reopen-feature", "R-3", "--reason", "x")
        self.assertEqual(code, 7, err)
        self.assertIn("rank already used by R-2", err)
        self.assertIn("edit R-3 --set rank=<free>", err)
        self.assertEqual(self.raw(g["number"])["state"], "closed")

    def test_feature_deja_ouverte(self):
        self.add_feature(1, status="Todo")
        code, out, err = self.run_cli("reopen-feature", "R-1", "--reason", "x")
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do: R-1 is already open", out)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_feature_refus_sans_ecriture(self):
        self.feature_fermee(1)
        self.feature_fermee(2, milestone="Tarasque")
        cas = [("motif vide", ("R-1", "--reason", ""), 2, "usage:"),
               ("clé inconnue", ("R-9", "--reason", "x"), 7, "unknown identifier R-9"),
               ("clé mal formée", ("abc", "--reason", "x"), 2, "usage:"),
               ("jalon fermé", ("R-2", "--reason", "x"), 7, "closed milestone: a reopened issue would sit in it; nothing was sent"),
               ("garde", ("R-1", "--reason", f"{NAME} l'a demandé"), 3, "sensitive name")]
        for nom, argv, code_attendu, message in cas:
            with self.subTest(nom):
                code, out, err = self.run_cli("reopen-feature", *argv)
                self.assertEqual(code, code_attendu, err)
                self.assertIn(message, err)
                self.no_leak(out, err)
        self.assertEqual(self.calls(writes_only=True), [])

    # --- reprise après une coupure (B1, N4) --------------------------------------------------------------------------

    def coupure(self, apres):
        self.st = self.load()
        self.st["mode"] = {"offline_after_writes": apres}
        self.save()

    def reseau_revenu(self):
        self.st = self.load()
        self.st["mode"] = {}
        self.save()

    def test_feature_etat_et_corps_dans_une_seule_requete(self):
        self.feature_fermee(1)
        self.assertEqual(self.run_cli("reopen-feature", "R-1", "--reason", "x")[0], 0)
        patchs = [json.loads(c["stdin"]) for c in self.calls(writes_only=True) if "PATCH" in c["args"]]
        self.assertEqual(len(patchs), 1)
        self.assertEqual(patchs[0]["state"], "open")
        self.assertNotIn("done_on", rm.parse_block(patchs[0]["body"]))

    def test_feature_relance_apres_coupure_avant_le_status(self):
        f = self.feature_fermee(1)
        self.coupure(2)      # commentaire et PATCH partis, le Status n'a pas pu l'être
        code, _, _ = self.run_cli("reopen-feature", "R-1", "--reason", "x")
        self.assertNotEqual(code, 0)
        self.assertEqual(self.raw(f["number"])["state"], "open")
        self.assertEqual(self.status_of("R-1"), "Done")
        self.reseau_revenu()
        code, out, err = self.run_cli("reopen-feature", "R-1", "--reason", "x")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.status_of("R-1"), "Todo")
        self.assertEqual(len(self.commentaires(f["number"])), 1)
        self.assertNotIn("done_on", rm.parse_block(self.raw(f["number"])["body"]))
        code, out, err = self.run_cli("reopen-feature", "R-1", "--reason", "x")      # puis plus rien à faire
        self.assertIn("nothing to do: R-1 is already open", out)

    def test_feature_ouverte_avec_done_on_reste_est_nettoyee(self):
        f = self.add_feature(1, status="Done", done_on="2026-10-01")
        code, out, err = self.run_cli("reopen-feature", "R-1", "--reason", "x")
        self.assertEqual(code, 0, err)
        self.assertNotIn("done_on", rm.parse_block(self.raw(f["number"])["body"]))
        self.assertEqual(self.status_of("R-1"), "Todo")
        self.assertEqual(self.commentaires(f["number"]), [])      # rien n'est reposté : l'issue était déjà ouverte

    def relance_sans_second_commentaire(self, issue, *argv):
        self.coupure(1)      # le commentaire part, la réouverture non
        code, _, _ = self.run_cli(*argv, "--reason", "motif")
        self.assertNotEqual(code, 0)
        self.assertEqual(self.raw(issue["number"])["state"], "closed")
        self.reseau_revenu()
        code, _, err = self.run_cli(*argv, "--reason", "motif")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.raw(issue["number"])["state"], "open")
        self.assertEqual(len(self.commentaires(issue["number"])), 1)

    def test_commentaire_de_reouverture_non_reposte_idee(self):
        idee = self.idee(state="closed")
        self.relance_sans_second_commentaire(idee, "reopen-idea", str(idee["number"]))

    def test_commentaire_de_reouverture_non_reposte_feature(self):
        f = self.feature_fermee(1)
        self.relance_sans_second_commentaire(f, "reopen-feature", "R-1")

    def test_deuxieme_reouverture_pour_un_autre_motif_commente_a_nouveau(self):
        idee = self.idee(state="closed")
        n = str(idee["number"])
        self.assertEqual(self.run_cli("reopen-idea", n, "--reason", "premier motif")[0], 0)
        self.assertEqual(self.run_cli("close-idea", n)[0], 0)
        self.assertEqual(self.run_cli("reopen-idea", n, "--reason", "second motif")[0], 0)
        self.assertEqual(len(self.commentaires(idee["number"])), 2)

    def test_feature_pas_de_status_done_garde_son_status(self):
        f = self.add_feature(1, state="closed", status="In progress", done_on="2026-10-01")
        self.assertEqual(self.run_cli("reopen-feature", "R-1", "--reason", "x")[0], 0)
        self.assertEqual(self.status_of("R-1"), "In progress")


if __name__ == "__main__":
    unittest.main()
