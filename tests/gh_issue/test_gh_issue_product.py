"""
Tests de tools/gh_issue.py : option --product (label product:mothra) pour new-feature, new-idea, edit, edit-idea,
ensure-labels et sync-tasks. Même faux gh que test_gh_issue.py.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/gh_issue -q -f
"""
import json
import unittest

from test_gh_issue import Base, NAME

MOTHRA = "product:mothra"


def noms(issue):
    return sorted(l["name"] for l in issue["labels"])


class Creation(Base):
    def test_new_feature_pose_le_label(self):
        code, out, err = self.run_cli("new-feature", "--title", "Écran", "--theme", "outillage", "--milestone", "Hydra",
                                      "--product", "mothra")
        self.assertEqual(code, 0, err)
        self.assertIn(MOTHRA, noms(self.issue("R-1")))
        self.assertIn(MOTHRA, [l["name"] for l in self.load()["labels"]])

    def test_new_feature_sans_option_pas_de_label(self):
        self.run_cli("new-feature", "--title", "Écran", "--theme", "outillage", "--milestone", "Hydra")
        self.assertEqual([l for l in noms(self.issue("R-1")) if l.startswith("product:")], [])

    def test_produit_inconnu_refuse(self):
        for cmd in (("new-feature", "--title", "X", "--theme", "outillage", "--milestone", "Hydra"),
                    ("new-idea", "--title", "X", "--body", "Texte.")):
            code, _, err = self.run_cli(*cmd, "--product", "autre")
            self.assertEqual(code, 2, cmd)
            self.assertIn("usage", err)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_new_idea_pose_le_label(self):
        code, out, err = self.run_cli("new-idea", "--title", "Idée Mothra", "--body", "Résumé.", "--value", "2",
                                      "--product", "mothra")
        self.assertEqual(code, 0, err)
        self.assertEqual(sorted(l["name"] for l in self.load()["issues"][0]["labels"]), [MOTHRA, "type:idea", "value:2"])


class Edition(Base):
    def test_edit_pose_puis_retire(self):
        self.add_feature(1)
        code, out, err = self.run_cli("edit", "R-1", "--product", "mothra")
        self.assertEqual(code, 0, err)
        self.assertEqual(noms(self.issue("R-1")), [MOTHRA, "theme:outillage", "type:feature"])
        n = len(self.calls(writes_only=True))
        code, out, _ = self.run_cli("edit", "R-1", "--product", "mothra")
        self.assertIn("nothing to do", out)
        self.assertEqual(len(self.calls(writes_only=True)), n)
        code, out, err = self.run_cli("edit", "R-1", "--product", "none")
        self.assertEqual(code, 0, err)
        self.assertEqual(noms(self.issue("R-1")), ["theme:outillage", "type:feature"])
        code, out, _ = self.run_cli("edit", "R-1", "--product", "none")
        self.assertIn("nothing to do", out)

    def test_edit_produit_inconnu_refuse(self):
        self.add_feature(1)
        code, _, err = self.run_cli("edit", "R-1", "--product", "autre")
        self.assertEqual(code, 2)
        self.assertEqual(self.calls(writes_only=True), [])

    def test_edit_conserve_le_label_quand_le_theme_change(self):
        self.add_feature(1)
        self.run_cli("edit", "R-1", "--product", "mothra")
        self.run_cli("edit", "R-1", "--set", "theme=veille")
        self.assertEqual(noms(self.issue("R-1")), [MOTHRA, "theme:veille", "type:feature"])

    def test_edit_idea_pose_et_retire(self):
        self.run_cli("new-idea", "--title", "Une idée", "--body", "Résumé.", "--value", "1")
        code, _, err = self.run_cli("edit-idea", "1", "--product", "mothra")
        self.assertEqual(code, 0, err)
        self.assertEqual(sorted(l["name"] for l in self.load()["issues"][0]["labels"]), [MOTHRA, "type:idea", "value:1"])
        code, _, err = self.run_cli("edit-idea", "1", "--value", "3")
        self.assertEqual(sorted(l["name"] for l in self.load()["issues"][0]["labels"]), [MOTHRA, "type:idea", "value:3"])
        code, _, err = self.run_cli("edit-idea", "1", "--product", "none")
        self.assertEqual(code, 0, err)
        self.assertEqual(sorted(l["name"] for l in self.load()["issues"][0]["labels"]), ["type:idea", "value:3"])

    def test_edit_idea_seul_product_suffit(self):
        self.run_cli("new-idea", "--title", "Une idée", "--body", "Résumé.")
        self.assertEqual(self.run_cli("edit-idea", "1")[0], 2)
        self.assertEqual(self.run_cli("edit-idea", "1", "--product", "autre")[0], 2)


class EtiquettesEtSync(Base):
    def test_ensure_labels_cree_le_label_avec_couleur_et_description(self):
        code, out, err = self.run_cli("ensure-labels")
        self.assertEqual(code, 0, err)
        posts = [json.loads(c["stdin"]) for c in self.calls(writes_only=True) if "labels" in " ".join(c["args"])]
        mothra = next(p for p in posts if p["name"] == MOTHRA)
        self.assertTrue(mothra["color"])
        self.assertTrue(mothra["description"])
        self.assertNotIn("description", next(p for p in posts if p["name"] == "type:feature"))

    def test_sync_tasks_recopie_le_label_sur_les_taches(self):
        self.add_feature(1, change="demo")
        self.run_cli("edit", "R-1", "--product", "mothra")
        code, out, err = self.run_cli("sync-tasks", "R-1")
        self.assertEqual(code, 0, err)
        for k in ("R-1/g1", "R-1/g2", "R-1/t2.2", "R-1/g3"):
            self.assertIn(MOTHRA, noms(self.issue(k)), k)
        self.assertEqual(noms(self.issue("R-1/g1")), ["model:haiku", MOTHRA, "type:task"])

    def test_sync_tasks_sans_produit_ne_pose_rien(self):
        self.add_feature(1, change="demo")
        self.run_cli("sync-tasks", "R-1")
        for k in ("R-1/g1", "R-1/g2", "R-1/t2.2", "R-1/g3"):
            self.assertEqual([l for l in noms(self.issue(k)) if l.startswith("product:")], [], k)

    def test_garde_sur_le_titre_inchange_avec_le_produit(self):
        code, out, err = self.run_cli("new-feature", "--title", f"{NAME} Écran", "--theme", "outillage",
                                      "--milestone", "Hydra", "--product", "mothra")
        self.assertEqual(code, 3)
        self.assertEqual(self.calls(writes_only=True), [])


if __name__ == "__main__":
    unittest.main()
