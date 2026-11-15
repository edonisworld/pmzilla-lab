"""
Tests de tools/gh_issue.py : edit-milestone, description et échéance d'un jalon (groupe 8, change gh-issue-autonomy, design D9).
Même faux gh que test_gh_issue.py.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q -f
"""
import inspect
import json
import re
import unittest
from pathlib import Path

from test_gh_issue import Base, NAME, g


class EditionDUnJalon(Base):
    def fichier(self, texte, nom="desc.md"):
        p = Path(self.tmp.name) / nom
        p.write_text(texte, encoding="utf-8")
        return str(p)

    def jalon(self, titre):
        return next(m for m in self.load()["milestones"] if m["title"] == titre)

    def patchs_jalon(self):
        return [c for c in self.calls(writes_only=True) if any(a.startswith("repos/") and "/milestones/" in a for a in c["args"])]

    def test_description_et_echeance_en_une_requete(self):
        code, out, err = self.run_cli("edit-milestone", "Hydra", "--description-file", self.fichier("La description\n"), "--due", "2026-11-26")
        self.assertEqual(code, 0, err)
        self.assertIn("edited milestone Hydra", out)
        m = self.jalon("Hydra")
        self.assertEqual(m["description"], "La description")
        self.assertTrue(m["due_on"].startswith("2026-11-26"))
        self.assertEqual((m["title"], m["state"]), ("Hydra", "open"))
        self.assertEqual(len(self.patchs_jalon()), 1)
        self.assertEqual(set(json.loads(self.patchs_jalon()[0]["stdin"])), {"description", "due_on"})

    def test_memes_valeurs_rien_a_faire(self):
        f = self.fichier("La description")
        self.run_cli("edit-milestone", "Hydra", "--description-file", f, "--due", "2026-11-26")
        avant = len(self.calls(writes_only=True))
        code, out, err = self.run_cli("edit-milestone", "Hydra", "--description-file", f, "--due", "2026-11-26")
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.calls(writes_only=True)), avant)

    def test_echeance_comparee_au_jour(self):
        self.st = self.load()
        self.st["milestones"][0]["due_on"] = "2026-11-26T07:00:00Z"      # GitHub rend une heure
        self.save()
        code, out, err = self.run_cli("edit-milestone", "Hydra", "--due", "2026-11-26")
        self.assertEqual(code, 0, err)
        self.assertIn("nothing to do", out)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_une_seule_option(self):
        self.assertEqual(self.run_cli("edit-milestone", "Hydra", "--due", "2026-12-01")[0], 0)
        self.assertEqual(set(json.loads(self.patchs_jalon()[0]["stdin"])), {"due_on"})
        self.assertEqual(self.run_cli("edit-milestone", "Hydra", "--description-file", self.fichier("Texte"))[0], 0)
        self.assertEqual(set(json.loads(self.patchs_jalon()[1]["stdin"])), {"description"})
        self.assertTrue(self.jalon("Hydra")["due_on"].startswith("2026-12-01"))

    def test_no_due_retire_l_echeance(self):
        self.run_cli("edit-milestone", "Hydra", "--due", "2026-12-01")
        code, out, err = self.run_cli("edit-milestone", "Hydra", "--no-due")
        self.assertEqual(code, 0, err)
        self.assertIn("edited milestone Hydra", out)
        self.assertIsNone(self.jalon("Hydra")["due_on"])
        self.assertIn("nothing to do", self.run_cli("edit-milestone", "Hydra", "--no-due")[1])

    def test_refus_code_2_sans_ecriture(self):
        absent = str(Path(self.tmp.name) / "absent.md")
        vide = self.fichier(" \n", "vide.md")
        cas = [("aucune option", ("Hydra",)),
               ("date impossible", ("Hydra", "--due", "2026-02-30")),
               ("date mal formée", ("Hydra", "--due", "26/11/2026")),
               ("due et no-due", ("Hydra", "--due", "2026-11-26", "--no-due")),
               ("fichier absent", ("Hydra", "--description-file", absent)),
               ("fichier vide", ("Hydra", "--description-file", vide)),
               ("dossier", ("Hydra", "--description-file", self.tmp.name))]
        for nom, argv in cas:
            with self.subTest(nom):
                code, _, err = self.run_cli("edit-milestone", *argv)
                self.assertEqual(code, 2, err)
                self.assertIn("usage:", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_jalon_inconnu_ou_ferme_code_7(self):
        code, _, err = self.run_cli("edit-milestone", "Absent", "--due", "2026-11-26")
        self.assertEqual(code, 7, err)
        self.assertIn("unknown milestone", err)
        code, _, err = self.run_cli("edit-milestone", "Tarasque", "--due", "2026-12-01")
        self.assertEqual(code, 7, err)
        self.assertIn("closed milestone: Tarasque is not edited; nothing was sent", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_garde_sur_la_description(self):
        code, out, err = self.run_cli("edit-milestone", "Hydra", "--description-file", self.fichier(f"avec {NAME}"))
        self.assertEqual(code, 3, err)
        self.assertIn("sensitive name in description", err)
        self.no_leak(out, err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_le_code_de_la_commande_ne_pose_que_description_et_echeance(self):
        """Règle restreinte de D9 (le contrôle du texte de l'outil est dans test_gh_issue.py) : la commande n'écrit que ces deux champs."""
        corps = inspect.getsource(g.cmd_edit_milestone)
        self.assertEqual(set(re.findall(r"payload\[\"(\w+)\"\]", corps)), {"description", "due_on"})


if __name__ == "__main__":
    unittest.main()
