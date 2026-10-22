"""
Tests de tools/gh_issue.py : --body-file pour new-idea et edit-idea (décision de l'auteur du 2026-10-16). Même faux gh que
test_gh_issue.py.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q -f
"""
import json
import unittest
from pathlib import Path

from test_gh_issue import Base, NAME, FAKE_KEY
import roadmap_model as rm


class NewIdeaBodyFile(Base):
    def setUp(self):
        super().setUp()
        self.body_file = Path(self.tmp.name) / "idee.md"
        self.body_file.write_text("Texte de l'idée\nsur deux lignes.\n", encoding="utf-8")

    def writes(self):
        return len(self.calls(writes_only=True))

    def test_cree_l_idee_avec_le_texte_du_fichier(self):
        code, out, err = self.run_cli("new-idea", "--title", "Une idée", "--body-file", str(self.body_file))
        self.assertEqual(code, 0, err)
        self.assertIn("gh_issue: created idea une-idee (#1)", out)
        posts = [c for c in self.calls(writes_only=True) if "issues" in " ".join(c["args"]) and "labels" not in " ".join(c["args"])]
        self.assertEqual(len(posts), 1)
        sent = json.loads(posts[0]["stdin"])
        self.assertEqual(sent["body"], f"{rm.idea_marker('une-idee')}\n\nTexte de l'idée\nsur deux lignes.")
        self.assertIn(rm.LABEL_IDEA, sent["labels"])

    def test_body_et_body_file_ensemble_code_2(self):
        code, _, err = self.run_cli("new-idea", "--title", "Une idée", "--body", "Texte.", "--body-file", str(self.body_file))
        self.assertEqual(code, 2)
        self.assertIn("usage", err)
        self.assertEqual(self.writes(), 0)

    def test_ni_body_ni_body_file_code_2(self):
        code, _, err = self.run_cli("new-idea", "--title", "Une idée")
        self.assertEqual(code, 2)
        self.assertIn("usage", err)
        self.assertEqual(self.writes(), 0)

    def test_fichier_absent_vide_ou_dossier_code_2(self):
        vide = Path(self.tmp.name) / "vide.md"
        vide.write_text(" \n\n", encoding="utf-8")
        dossier = Path(self.tmp.name) / "dossier"
        dossier.mkdir()
        for chemin in (Path(self.tmp.name) / "absent.md", vide, dossier):
            code, _, err = self.run_cli("new-idea", "--title", "Une idée", "--body-file", str(chemin))
            self.assertEqual(code, 2, chemin.name)
            self.assertIn("usage", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_texte_du_fichier_passe_par_le_garde(self):
        for texte in (f"Voir {NAME}.", f"Voir le ticket {FAKE_KEY}."):
            self.body_file.write_text(texte, encoding="utf-8")
            code, out, err = self.run_cli("new-idea", "--title", "Une idée", "--body-file", str(self.body_file))
            self.assertEqual(code, 3, texte)
            self.assertIn("body", err)
            self.assertNotIn(NAME, out + err)
            self.assertNotIn(FAKE_KEY, out + err)
        self.assertEqual(self.calls(writes_only=True), [])


class EditIdeaBodyFile(Base):
    def setUp(self):
        super().setUp()
        self.body_file = Path(self.tmp.name) / "idee.md"
        self.body_file.write_text("Nouveau texte.\n", encoding="utf-8")
        self.run_cli("new-idea", "--title", "Une idée à suivre", "--body", "Résumé court.")
        self.st = self.load()
        self.before = len(self.calls(writes_only=True))

    def new_writes(self):
        return len(self.calls(writes_only=True)) - self.before

    def test_remplace_le_corps_et_garde_le_marqueur(self):
        code, out, err = self.run_cli("edit-idea", "#1", "--body-file", str(self.body_file))
        self.assertEqual(code, 0, err)
        self.assertIn("gh_issue: edited idea #1", out)
        self.assertEqual(self.load()["issues"][0]["body"], f"{rm.idea_marker('une-idee-a-suivre')}\n\nNouveau texte.")
        self.assertEqual(self.new_writes(), 1)

    def test_body_n_existe_pas_pour_edit_idea(self):
        code, _, err = self.run_cli("edit-idea", "1", "--body", "Texte.")
        self.assertEqual(code, 2)
        self.assertIn("usage", err)
        self.assertEqual(self.new_writes(), 0)

    def test_fichier_absent_vide_ou_dossier_code_2(self):
        vide = Path(self.tmp.name) / "vide.md"
        vide.write_text("", encoding="utf-8")
        dossier = Path(self.tmp.name) / "dossier"
        dossier.mkdir()
        for chemin in (Path(self.tmp.name) / "absent.md", vide, dossier):
            code, _, err = self.run_cli("edit-idea", "1", "--body-file", str(chemin))
            self.assertEqual(code, 2, chemin.name)
            self.assertIn("usage", err)
        self.assertEqual(self.new_writes(), 0)

    def test_texte_du_fichier_passe_par_le_garde(self):
        for texte in (f"Voir {NAME}.", f"Voir le ticket {FAKE_KEY}."):
            self.body_file.write_text(texte, encoding="utf-8")
            code, out, err = self.run_cli("edit-idea", "1", "--body-file", str(self.body_file))
            self.assertEqual(code, 3, texte)
            self.assertNotIn(NAME, out + err)
            self.assertNotIn(FAKE_KEY, out + err)
        self.assertEqual(self.new_writes(), 0)
        self.assertIn("Résumé court.", self.load()["issues"][0]["body"])

    def test_refuse_ce_qui_n_est_pas_une_idee(self):
        self.add_feature(5)
        code, _, err = self.run_cli("edit-idea", "2", "--body-file", str(self.body_file))
        self.assertEqual(code, 7)
        self.assertEqual(self.new_writes(), 0)

    def test_combine_avec_valeur_en_une_seule_requete(self):
        code, _, err = self.run_cli("edit-idea", "1", "--value", "2", "--body-file", str(self.body_file))
        self.assertEqual(code, 0, err)
        patches = [c for c in self.calls(writes_only=True) if "PATCH" in c["args"]]
        self.assertEqual(len(patches), 1)
        sent = json.loads(patches[0]["stdin"])
        self.assertIn("body", sent)
        self.assertIn("value:2", sent["labels"])


if __name__ == "__main__":
    unittest.main()
