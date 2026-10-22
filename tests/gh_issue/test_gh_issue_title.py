"""
Tests de tools/gh_issue.py : --title pour edit (features) et edit-idea (idées). Même faux gh que test_gh_issue.py.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q -f
"""
import unittest

from test_gh_issue import Base, NAME


class EditTitreFeature(Base):
    def test_titre_change_et_prefixe_de_cle_ajoute(self):
        self.add_feature(1)
        code, out, err = self.run_cli("edit", "R-1", "--title", "Titre neuf")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.issue("R-1")["title"], "R-1 · Titre neuf")

    def test_titre_deja_prefixe_refuse(self):
        self.add_feature(1)
        code, _, err = self.run_cli("edit", "R-1", "--title", "R-1 · Titre neuf")
        self.assertEqual(code, 2)
        self.assertIn("usage", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_titre_vide_refuse(self):
        self.add_feature(1)
        for vide in ("", "   "):
            code, _, err = self.run_cli("edit", "R-1", "--title", vide)
            self.assertEqual(code, 2, vide)
            self.assertIn("usage", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_garde_refuse_un_nom_sensible(self):
        self.add_feature(1)
        avant = self.issue("R-1")["title"]
        code, out, err = self.run_cli("edit", "R-1", "--title", f"avec {NAME} demain")
        self.assertEqual(code, 3)
        self.assertIn("title", err)
        self.assertNotIn(NAME, out + err)
        self.assertEqual(self.issue("R-1")["title"], avant)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_meme_titre_rien_a_faire(self):
        self.add_feature(1)
        self.run_cli("edit", "R-1", "--title", "Stable")
        n = len(self.calls(writes_only=True))
        code, out, _ = self.run_cli("edit", "R-1", "--title", "Stable")
        self.assertEqual(code, 0)
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.calls(writes_only=True)), n)


class EditTitreIdee(Base):
    def setUp(self):
        super().setUp()
        self.run_cli("new-idea", "--title", "Une idée à suivre", "--body", "Résumé court.")

    def title(self):
        return self.load()["issues"][0]["title"]

    def test_idee_renommee_marqueur_conserve(self):
        corps = self.load()["issues"][0]["body"]
        code, out, err = self.run_cli("edit-idea", "1", "--title", "Idée renommée")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.title(), "Idée renommée")
        self.assertEqual(self.load()["issues"][0]["body"], corps)

    def test_titre_vide_refuse(self):
        n = len(self.calls(writes_only=True))
        code, _, err = self.run_cli("edit-idea", "1", "--title", "  ")
        self.assertEqual(code, 2)
        self.assertIn("usage", err)
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_garde_refuse_un_nom_sensible(self):
        n = len(self.calls(writes_only=True))
        code, out, err = self.run_cli("edit-idea", "1", "--title", f"Idée de {NAME}")
        self.assertEqual(code, 3)
        self.assertIn("title", err)
        self.assertNotIn(NAME, out + err)
        self.assertEqual(self.title(), "Une idée à suivre")
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_meme_titre_rien_a_faire(self):
        n = len(self.calls(writes_only=True))
        code, out, _ = self.run_cli("edit-idea", "1", "--title", "Une idée à suivre")
        self.assertEqual(code, 0)
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.calls(writes_only=True)), n)


if __name__ == "__main__":
    unittest.main()
