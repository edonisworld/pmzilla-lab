"""
Tests de tools/gh_issue.py : sous-commande new-task (tâche utilisateur autonome R-<n>/u<k>, sans tasks.md). Même faux gh que
test_gh_issue.py.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q -f
"""
import json
import unittest
from pathlib import Path

from test_gh_issue import Base, NAME, FAKE_KEY
import roadmap_model as rm


class NewTask(Base):
    def setUp(self):
        super().setUp()
        self.body_file = Path(self.tmp.name) / "tache.md"
        self.body_file.write_text("Relire le brouillon\net valider.\n", encoding="utf-8")
        self.add_feature(1)

    def task(self, *extra, title="Valider le brouillon", key="R-1"):
        return self.run_cli("new-task", key, "--title", title, "--body-file", str(self.body_file), *extra)

    def labels(self, key):
        return sorted(l["name"] for l in self.issue(key)["labels"])

    def test_cree_la_tache_liee_a_la_feature_dans_son_jalon(self):
        code, out, err = self.task()
        self.assertEqual(code, 0, err)
        self.assertIn("gh_issue: created R-1/u1 (#2)", out)
        issue = self.issue("R-1/u1")
        self.assertEqual(issue["title"], "R-1 · Valider le brouillon")
        self.assertEqual(issue["body"], f"{rm.marker('R-1/u1')}\n\nRelire le brouillon\net valider.")
        self.assertEqual(self.labels("R-1/u1"), ["owner:user", "type:task"])
        self.assertEqual(self.milestone_of("R-1/u1"), "Hydra")
        self.assertEqual(self.load()["sub"][str(self.number_of("R-1"))], [issue["number"]])

    def test_jalon_explicite_existant(self):
        code, _, err = self.task("--milestone", "Namazu")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.milestone_of("R-1/u1"), "Namazu")

    def test_jalon_explicite_inconnu_code_7_rien_envoye(self):
        code, _, err = self.task("--milestone", "Absent")
        self.assertEqual(code, 7)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_label_produit_de_la_feature(self):
        self.run_cli("edit", "R-1", "--product", "mothra")
        self.assertEqual(self.task()[0], 0)
        self.assertEqual(self.labels("R-1/u1"), ["owner:user", "product:mothra", "type:task"])

    def test_numero_suivant_sans_collision_avec_g_et_t(self):
        self.add_issue("R-1/g1", "R-1 · 1. Groupe", ["type:task", "owner:user"])
        self.add_issue("R-1/t2.2", "R-1 · 2.2 (user step)", ["type:task", "owner:user"])
        self.assertEqual(self.task(title="Une")[0], 0)
        self.assertEqual(self.task(title="Deux")[0], 0)
        self.assertEqual(self.issue("R-1/u2")["title"], "R-1 · Deux")
        self.add_feature(2)
        self.assertEqual(self.task(title="Autre feature", key="R-2")[0], 0)
        self.assertEqual(self.issue("R-2/u1")["title"], "R-2 · Autre feature")

    def test_relance_meme_titre_sans_doublon(self):
        self.task()
        n = len(self.calls(writes_only=True))
        code, out, _ = self.task()
        self.assertEqual(code, 0)
        self.assertIn("already exists: R-1/u1", out)
        self.assertEqual(len(self.calls(writes_only=True)), n)
        self.assertEqual(len([i for i in self.load()["issues"] if i["body"].startswith("<!-- roadmap-id: R-1/u")]), 1)

    def test_feature_inconnue_ou_cle_mal_formee(self):
        self.assertEqual(self.task(key="R-9")[0], 7)
        self.assertEqual(self.task(key="R-1/g1")[0], 2)
        self.assertEqual(self.task(key="x")[0], 2)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_titre_vide_ou_deja_prefixe_et_fichier_invalide_code_2(self):
        for titre in (" ", "R-1 · Déjà préfixé"):
            self.assertEqual(self.task(title=titre)[0], 2, titre)
        vide = Path(self.tmp.name) / "vide.md"
        vide.write_text("\n", encoding="utf-8")
        for chemin in (vide, Path(self.tmp.name) / "absent.md"):
            code, _, err = self.run_cli("new-task", "R-1", "--title", "T", "--body-file", str(chemin))
            self.assertEqual(code, 2)
            self.assertIn("usage", err)
        self.assertEqual(self.run_cli("new-task", "R-1", "--title", "T")[0], 2)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_garde_sur_titre_et_corps(self):
        code, out, err = self.task(title=f"Avec {NAME}")
        self.assertEqual(code, 3)
        self.no_leak(out, err)
        for texte in (f"Voir {NAME}.", f"Voir le ticket {FAKE_KEY}."):
            self.body_file.write_text(texte, encoding="utf-8")
            code, out, err = self.task()
            self.assertEqual(code, 3, texte)
            self.no_leak(out, err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_close_step_accepte_la_cle_u(self):
        self.task()
        code, out, err = self.run_cli("close-step", "R-1/u1")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.issue("R-1/u1")["state"], "closed")
        self.assertIn("nothing to do", self.run_cli("close-step", "R-1/u1")[1])
        self.assertEqual(self.run_cli("close-step", "R-1/u9")[0], 7)

    def test_sync_tasks_ne_touche_pas_la_tache(self):
        self.add_feature(3, change="demo")
        self.task(key="R-3")
        self.run_cli("sync-tasks", "R-3")
        self.assertEqual(self.issue("R-3/u1")["state"], "open")


class CleU(unittest.TestCase):
    def test_parse_key(self):
        self.assertEqual(rm.parse_key("R-12/u3"), ("user-task", 12, "3"))
        self.assertEqual(rm.user_task_key(12, 3), "R-12/u3")
        self.assertEqual(rm.parse_marker("<!-- roadmap-id: R-12/u3 -->\n\nx"), "R-12/u3")
        for mauvaise in ("R-12/u", "R-12/u1.2", "R-12/x3"):
            with self.assertRaises(ValueError):
                rm.parse_key(mauvaise)


if __name__ == "__main__":
    unittest.main()
