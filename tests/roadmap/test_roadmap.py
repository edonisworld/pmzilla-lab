"""
Tests des fonctions pures du lecteur de la file de travail (tools/roadmap.py) : durées, sélection dans le budget, vue.
Les commandes (mode GitHub) sont testées dans test_roadmap_github.py.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/roadmap -q -f
"""
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import roadmap  # noqa: E402


def job(i, **kw):
    d = {"id": f"R-{i}", "title": f"Travail {i}", "theme": "outillage", "depends_on": [], "conditions": "", "state": "ready",
         "estimate": "1h", "method": "direct-prompt", "model": "tbd"}
    d.update(kw)
    return d


class TestDuree(unittest.TestCase):
    def test_durees_valides(self):
        self.assertEqual(roadmap.duree("45min"), 45)
        self.assertEqual(roadmap.duree("2h"), 120)
        self.assertEqual(roadmap.duree("1h30"), 90)

    def test_durees_refusees(self):
        for d in ("0min", "tbd", "2 heures", "", "h"):
            with self.subTest(d=d):
                self.assertIsNone(roadmap.duree(d))

    def test_affichage(self):
        self.assertEqual(roadmap.affiche_duree(90), "1h30")
        self.assertEqual(roadmap.affiche_duree(120), "2h")
        self.assertEqual(roadmap.affiche_duree(45), "45min")


class TestSelection(unittest.TestCase):
    def test_budget_rempli_dans_l_ordre(self):
        retenus, longs, inconnus, total = roadmap.selection(
            [job(1, estimate="1h"), job(2, estimate="2h"), job(3, estimate="30min"), job(4, estimate="tbd")], 120)
        self.assertEqual([j["id"] for j in retenus], ["R-1", "R-3"])
        self.assertEqual([j["id"] for j in longs], ["R-2"])
        self.assertEqual([j["id"] for j in inconnus], ["R-4"])
        self.assertEqual(total, 90)


class TestVue(unittest.TestCase):
    def test_comptes_et_bloques(self):
        v = roadmap.vue([job(1), job(2, state="blocked", depends_on=["R-1"])], [job(3, state="done", done_on="2026-10-12")])
        self.assertEqual(v["etats"]["done"], 1)
        self.assertEqual([j["id"] for j in v["prets"]], ["R-1"])
        self.assertEqual(v["bloques"][0][1], ["R-1"])
        self.assertEqual(v["semaines"], [("2026-10-12", 1)])


class TestFichiersConnus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.arbre = Path(self.tmp.name)
        for chemin in ("tools/a.py", "tests/x/t.py", "docs/guide.md", "openspec/specs/s/spec.md"):
            (self.arbre / chemin).parent.mkdir(parents=True, exist_ok=True)
            (self.arbre / chemin).write_text("x", encoding="utf-8")
        (self.arbre / "openspec/changes/c").mkdir(parents=True)

    def ecrit(self, tasks="", design=""):
        (self.arbre / "openspec/changes/c/tasks.md").write_text(tasks, encoding="utf-8")
        (self.arbre / "openspec/changes/c/design.md").write_text(design, encoding="utf-8")
        return roadmap.fichiers_connus(self.arbre, "c")

    def test_fichiers_et_dossiers(self):
        self.assertEqual(self.ecrit("Edit `tools/a.py` and `tests/x/`.", "see `docs/guide.md`"),
                         {"tools/a.py", "tests/x", "docs/guide.md"})

    def test_extrait_avec_espace_ignore(self):
        self.assertEqual(self.ecrit("run `bash tools/a.py` then `uv run tests/x/t.py`"), set())

    def test_chemin_absent_ou_interdit(self):
        self.assertEqual(self.ecrit("`tools/nope.py` `/tools/a.py` `~/tools/a.py` `../tools/a.py` `tools/../tools/a.py` `./tools/a.py`"), set())

    def test_openspec_exclu(self):
        self.assertEqual(self.ecrit("`openspec/specs/s/spec.md` `openspec/` `openspec`"), set())

    def test_extrait_de_deux_fichiers(self):
        self.assertEqual(self.ecrit("`tools/a.py`", "`tests/x/t.py`"), {"tools/a.py", "tests/x/t.py"})

    def test_change_absent_ou_archive(self):
        self.assertFalse(roadmap.change_existe(self.arbre, "zzz"))
        self.assertFalse(roadmap.change_existe(self.arbre, "archive"))
        self.assertFalse(roadmap.change_existe(self.arbre, "../c"))
        self.assertTrue(roadmap.change_existe(self.arbre, "c"))


class TestRecoupement(unittest.TestCase):
    def test_regle(self):
        self.assertTrue(roadmap.se_recoupent("tools/a.py", "tools/a.py"))
        self.assertTrue(roadmap.se_recoupent("tools", "tools/a.py"))
        self.assertTrue(roadmap.se_recoupent("tools/a.py", "tools"))
        self.assertFalse(roadmap.se_recoupent("tools", "tools2/a.py"))
        self.assertFalse(roadmap.se_recoupent("tools/a.py", "tools/b.py"))

    def test_fichiers_partages_hors_recoupement(self):
        self.assertFalse(roadmap.fichiers_en_commun({"README.md", "tools/a.py"}, {"README.md", "tools/b.py"}))
        self.assertTrue(roadmap.fichiers_en_commun({"README.md", "tools"}, {"tools/b.py"}))


class TestLancement(unittest.TestCase):
    def feat(self, n, titre, **bloc):
        return {"id": f"R-{n}", "title": titre, "block": bloc}

    def test_openspec_sans_change_cadrage(self):
        l = roadmap.lancement(self.feat(61, "Lot", method="openspec", model="sonnet"))
        self.assertEqual((l["branche"], l["genre"], l["modele"]), ("chore/spec-r61", "cadrage", "opus"))
        self.assertTrue(l["invite"].startswith("Frame R-61 as an OpenSpec change"))
        for interdit in ('"', "$", "`", "\n"):
            self.assertNotIn(interdit, l["invite"])

    def test_openspec_avec_change_execution(self):
        l = roadmap.lancement(self.feat(61, "Lot", method="openspec", change="batch-milestone", model="opus"))
        self.assertEqual((l["branche"], l["genre"], l["modele"], l["invite"]), ("feat/batch-milestone", "exécution", "sonnet", "/start R-61"))

    def test_direct_prompt_modele_et_slug(self):
        l = roadmap.lancement(self.feat(7, "Corriger l'été très long à lire", method="direct-prompt", model="haiku"))
        self.assertEqual((l["branche"], l["genre"], l["modele"], l["invite"]), ("chore/r7-corriger-l-ete-tres", "exécution", "haiku", "/start R-7"))

    def test_direct_prompt_modele_indecis(self):
        self.assertEqual(roadmap.lancement(self.feat(8, "Petit", method="direct-prompt", model="tbd"))["modele"], "sonnet")


if __name__ == "__main__":
    unittest.main()
