"""
Tests de tools/gh_issue.py : commenter et fermer une idée (#244, point F). Même faux gh que test_gh_issue.py.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q -f
"""
import json
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from test_gh_issue import Base, NAME, g


class CommenterEtFermerUneIdee(Base):
    def setUp(self):
        super().setUp()
        self.body_file = Path(self.tmp.name) / "texte.md"
        self.body_file.write_text("Une note sur l'idée.", encoding="utf-8")
        self.run_cli("new-idea", "--title", "Une idée à suivre", "--body", "Résumé court.")
        self.st = self.load()      # le faux GitHub a écrit l'idée : repartir de son état

    def comment_posts(self, n):
        return [c for c in self.calls(writes_only=True) if f"issues/{n}/comments" in " ".join(c["args"])]

    def test_commenter_une_idee(self):
        code, out, err = self.run_cli("comment-idea", "#1", "--body-file", str(self.body_file))
        self.assertEqual(code, 0, err)
        self.assertIn("gh_issue: commented idea #1", out)
        posts = self.comment_posts(1)
        self.assertEqual(len(posts), 1)
        self.assertEqual(json.loads(posts[0]["stdin"]), {"body": "Une note sur l'idée."})

    def test_commenter_refuse_ce_qui_n_est_pas_une_idee(self):
        self.add_feature(5)           # issue n°2
        n = len(self.calls(writes_only=True))
        for num in ("2", "99"):
            code, _, err = self.run_cli("comment-idea", num, "--body-file", str(self.body_file))
            self.assertEqual(code, 7, num)
        self.assertEqual(self.run_cli("comment-idea", "abc", "--body-file", str(self.body_file))[0], 2)
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_commenter_fichier_illisible(self):
        self.assertEqual(self.run_cli("comment-idea", "1", "--body-file", str(self.body_file.with_name("absent.md")))[0], 2)

    def test_commenter_garde_fou(self):
        self.body_file.write_text(f"Voir {NAME}.", encoding="utf-8")
        n = len(self.calls(writes_only=True))
        code, out, err = self.run_cli("comment-idea", "1", "--body-file", str(self.body_file))
        self.assertEqual(code, 3)
        self.no_leak(out, err)
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_fermer_une_idee_avec_commentaire(self):
        code, out, err = self.run_cli("close-idea", "1", "--comment-file", str(self.body_file))
        self.assertEqual(code, 0, err)
        self.assertIn("gh_issue: closed idea #1", out)
        self.assertEqual(self.load()["issues"][0]["state"], "closed")
        self.assertEqual(len(self.comment_posts(1)), 1)
        n = len(self.calls(writes_only=True))
        code, out, _ = self.run_cli("close-idea", "1", "--comment-file", str(self.body_file))
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_fermer_sans_commentaire(self):
        self.assertEqual(self.run_cli("close-idea", "#1")[0], 0)
        self.assertEqual(self.load()["issues"][0]["state"], "closed")
        self.assertEqual(self.comment_posts(1), [])

    def test_fermer_refuse_une_feature(self):
        self.add_feature(5)
        n = len(self.calls(writes_only=True))
        code, _, err = self.run_cli("close-idea", "2")
        self.assertEqual(code, 7)
        self.assertIn("not an idea", err)
        self.assertEqual(self.load()["issues"][1]["state"], "open")
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def test_fermer_garde_fou_avant_toute_ecriture(self):
        self.body_file.write_text(NAME, encoding="utf-8")
        n = len(self.calls(writes_only=True))
        code, _, _ = self.run_cli("close-idea", "1", "--comment-file", str(self.body_file))
        self.assertEqual(code, 3)
        self.assertEqual(self.load()["issues"][0]["state"], "open")
        self.assertEqual(len(self.calls(writes_only=True)), n)

    def enveloppe_ecritures(self, expirent=True):
        """Remplace le lanceur de processus : une écriture (appel avec entrée) lève TimeoutExpired, le reste est délégué."""
        vrai = g.subprocess.run
        tentatives = []

        def lance(cmd, *args, **kwargs):
            if "input" in kwargs:
                tentatives.append(cmd)
                if expirent:
                    raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))
            return vrai(cmd, *args, **kwargs)

        q = mock.patch.object(g.subprocess, "run", lance)
        q.start()
        self.addCleanup(q.stop)
        return tentatives

    def test_fermer_etat_inconnu_code_8(self):
        tentatives = self.enveloppe_ecritures()
        code, _, err = self.run_cli("close-idea", "1")
        self.assertEqual(code, 8)
        self.assertIn("state unknown", err)
        self.assertEqual(self.load()["issues"][0]["state"], "open")
        self.assertEqual(len(tentatives), 1)
        code, _, err = self.run_cli("comment-idea", "1", "--body-file", str(self.body_file))
        self.assertEqual(code, 8)
        self.assertEqual(len(tentatives), 2)


if __name__ == "__main__":
    unittest.main()
