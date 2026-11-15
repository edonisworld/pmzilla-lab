"""
Tests de tools/gh_issue.py : --body-file de new-feature, edit R-<n> et edit-task (groupe 5, change gh-issue-autonomy, design D6).
Même faux gh que test_gh_issue.py.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q -f
"""
import json
import unittest
from pathlib import Path

from test_gh_issue import Base, NAME, rm


class CorpsFeatureEtTache(Base):
    def fichier(self, texte, nom="corps.md"):
        p = Path(self.tmp.name) / nom
        p.write_text(texte, encoding="utf-8")
        return str(p)

    def patchs(self):
        return [c for c in self.calls(writes_only=True) if "PATCH" in c["args"]]

    def avec_tache(self):
        self.add_feature(1)
        return self.add_issue("R-1/u1", "R-1 · Étape", ["type:task", "owner:user"], milestone="Hydra")

    # --- new-feature --body-file -------------------------------------------------------------------------------------

    def test_new_feature_texte_apres_le_bloc(self):
        code, out, err = self.run_cli("new-feature", "--title", "T", "--theme", "outillage", "--milestone", "Hydra",
                                      "--body-file", self.fichier("Le texte\n\nde la feature.\n"))
        self.assertEqual(code, 0, err)
        corps = self.issue("R-1")["body"]
        self.assertEqual(rm.parse_marker(corps), "R-1")
        self.assertEqual(rm.parse_block(corps)["id"], "R-1")
        self.assertGreater(corps.index("Le texte"), corps.rindex("```"))      # le texte vient après le bloc
        self.assertIn("Le texte\n\nde la feature.", corps)

    def test_new_feature_sans_option_inchange(self):
        self.assertEqual(self.run_cli("new-feature", "--title", "T", "--theme", "outillage", "--milestone", "Hydra")[0], 0)
        self.assertTrue(self.issue("R-1")["body"].rstrip().endswith("```"))

    # --- edit R-<n> --body-file --------------------------------------------------------------------------------------

    def test_edit_remplace_le_texte_en_gardant_marqueur_et_bloc(self):
        self.add_feature(1)
        self.run_cli("edit", "R-1", "--body-file", self.fichier("Premier texte"))
        avant = rm.parse_block(self.issue("R-1")["body"])
        code, out, err = self.run_cli("edit", "R-1", "--body-file", self.fichier("Second texte"))
        self.assertEqual(code, 0, err)
        corps = self.issue("R-1")["body"]
        self.assertEqual(rm.parse_marker(corps), "R-1")
        self.assertEqual(rm.parse_block(corps), avant)
        self.assertIn("Second texte", corps)
        self.assertNotIn("Premier texte", corps)

    def test_edit_meme_requete_que_les_autres_champs(self):
        self.add_feature(1)
        code, _, err = self.run_cli("edit", "R-1", "--title", "Nouveau", "--set", "estimate=3h", "--body-file", self.fichier("Texte"))
        self.assertEqual(code, 0, err)
        self.assertEqual(len(self.patchs()), 1)
        payload = json.loads(self.patchs()[0]["stdin"])
        self.assertIn("title", payload)
        self.assertIn("Texte", payload["body"])
        self.assertEqual(rm.parse_block(payload["body"])["estimate"], "3h")

    def test_edit_texte_identique_rien_a_faire(self):
        self.add_feature(1)
        f = self.fichier("Texte stable")
        self.assertEqual(self.run_cli("edit", "R-1", "--body-file", f)[0], 0)
        avant = len(self.calls(writes_only=True))
        code, out, err = self.run_cli("edit", "R-1", "--body-file", f)
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.calls(writes_only=True)), avant)

    def test_edit_corps_sans_marqueur_ou_sans_bloc(self):
        self.add_issue("R-1", "R-1 · x", ["type:feature"], body="pas de marqueur ni de bloc", milestone="Hydra")
        code, _, err = self.run_cli("edit", "R-1", "--body-file", self.fichier("x"))
        self.assertEqual(code, 7, err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_edit_feature_sans_bloc(self):
        self.add_issue("R-1", "R-1 · x", ["type:feature"], milestone="Hydra")
        code, _, err = self.run_cli("edit", "R-1", "--body-file", self.fichier("x"))
        self.assertEqual(code, 7, err)
        self.assertIn("invalid block", err)
        self.assertEqual(self.calls(writes_only=True), [])

    # --- edit-task --body-file ---------------------------------------------------------------------------------------

    def test_edit_task_remplace_le_texte_marqueur_garde(self):
        t = self.avec_tache()
        code, out, err = self.run_cli("edit-task", "R-1/u1", "--body-file", self.fichier("Nouveau texte de tâche"))
        self.assertEqual(code, 0, err)
        corps = self.issue("R-1/u1")["body"]
        self.assertEqual(rm.parse_marker(corps), "R-1/u1")
        self.assertIn("Nouveau texte de tâche", corps)
        self.assertEqual(len(self.patchs()), 1)
        self.assertEqual(self.run_cli("edit-task", "R-1/u1", "--body-file", self.fichier("Nouveau texte de tâche"))[0], 0)
        self.assertEqual(len(self.patchs()), 1)

    def test_edit_task_identique_rien_a_faire(self):
        self.avec_tache()
        f = self.fichier("Texte")
        self.run_cli("edit-task", "R-1/u1", "--body-file", f)
        code, out, err = self.run_cli("edit-task", "R-1/u1", "--body-file", f)
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do", out)

    def test_edit_task_fermee_admise(self):
        self.add_feature(1)
        self.add_issue("R-1/u1", "R-1 · Étape", ["type:task", "owner:user"], state="closed", milestone="Hydra")
        code, _, err = self.run_cli("edit-task", "R-1/u1", "--body-file", self.fichier("Texte"))
        self.assertEqual(code, 0, err)
        self.assertIn("Texte", self.issue("R-1/u1")["body"])

    def test_edit_task_par_numero(self):
        t = self.avec_tache()
        code, _, err = self.run_cli("edit-task", "--numero", str(t["number"]), "--body-file", self.fichier("Par numéro"))
        self.assertEqual(code, 0, err)
        self.assertIn("Par numéro", self.issue("R-1/u1")["body"])

    def test_edit_task_sans_marqueur(self):
        self.add_feature(1)
        t = self.add_issue("R-1/u1", "R-1 · Étape", ["type:task", "owner:user"], body="sans marqueur", milestone="Hydra")
        code, _, err = self.run_cli("edit-task", "--numero", str(t["number"]), "--body-file", self.fichier("x"))
        self.assertEqual(code, 7, err)
        self.assertIn("has no roadmap key in its body", err)
        self.assertEqual(self.calls(writes_only=True), [])

    # --- fichiers refusés et garde -----------------------------------------------------------------------------------

    def test_fichiers_refuses_code_2(self):
        self.avec_tache()
        absent = str(Path(self.tmp.name) / "absent.md")
        dossier = self.tmp.name
        vide = self.fichier("  \n", "vide.md")
        binaire = Path(self.tmp.name) / "bin.md"
        binaire.write_bytes(b"\xff\xfe\x00\xff")
        commandes = [("edit", "R-1"), ("edit-task", "R-1/u1")]
        for cmd in commandes:
            for f in (absent, dossier, vide, str(binaire)):
                with self.subTest(cmd=cmd[0], fichier=Path(f).name):
                    code, _, err = self.run_cli(*cmd, "--body-file", f)
                    self.assertEqual(code, 2, err)
                    self.assertIn("usage:", err)
        for f in (absent, vide):
            code, _, err = self.run_cli("new-feature", "--title", "T", "--theme", "outillage", "--milestone", "Hydra", "--body-file", f)
            self.assertEqual(code, 2, err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_garde_sur_le_texte_code_3(self):
        self.avec_tache()
        f = self.fichier(f"voir avec {NAME}")
        for argv in (("edit", "R-1"), ("edit-task", "R-1/u1"),
                     ("new-feature", "--title", "T", "--theme", "outillage", "--milestone", "Hydra")):
            with self.subTest(argv[0]):
                code, out, err = self.run_cli(*argv, "--body-file", f)
                self.assertEqual(code, 3, err)
                self.no_leak(out, err)
        self.assertEqual(self.calls(writes_only=True), [])


if __name__ == "__main__":
    unittest.main()
