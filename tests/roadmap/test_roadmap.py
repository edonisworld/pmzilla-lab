"""
Tests des fonctions pures du lecteur de la file de travail (tools/roadmap.py) : durées, sélection dans le budget, vue.
Les commandes (mode GitHub) sont testées dans test_roadmap_github.py.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/roadmap -q -f
"""
import datetime
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


def feat_cycle(n, status, **bloc):
    return {"id": f"R-{n}", "open": True, "status": status, "block": bloc}


class TestSignalementsCycle(unittest.TestCase):
    """Fonction pure `signalements_cycle` (change github-status-lifecycle, design D3 à D5)."""

    def sig(self, feats, branches=frozenset(), sur_main=frozenset()):
        return roadmap.signalements_cycle(feats, set(branches), set(sur_main))

    def test_en_cours_sans_branche(self):
        self.assertEqual(self.sig([feat_cycle(7, "In progress")], {"main", "feat/autre"}),
                         [{"id": "R-7", "kind": "in_progress_without_branch", "change": None}])

    def test_branche_du_change_ou_jeton_d_identifiant(self):
        self.assertEqual(self.sig([feat_cycle(7, "In progress", change="c")], {"feat/c"}), [])
        self.assertEqual(self.sig([feat_cycle(7, "In progress", change="c")], {"spec/c"}), [])
        self.assertEqual(self.sig([feat_cycle(65, "In progress")], {"chore/r65-fixes"}), [])
        self.assertEqual(self.sig([feat_cycle(65, "In progress")], {"chore/spec-r65"}), [])
        self.assertEqual(self.sig([feat_cycle(65, "In progress")], {"chore/r65"}), [])

    def test_r650_n_est_pas_r65(self):
        self.assertEqual([s["kind"] for s in self.sig([feat_cycle(65, "In progress")], {"chore/r650-x", "chore/xr65-y"})],
                         ["in_progress_without_branch"])

    def test_main_ne_compte_pas_comme_branche(self):
        self.assertEqual([s["kind"] for s in self.sig([feat_cycle(7, "In progress", change="main")], {"main"})],
                         ["in_progress_without_branch"])

    def test_ready_change_absent_de_main(self):
        self.assertEqual(self.sig([feat_cycle(7, "Ready", method="openspec", change="c")]),
                         [{"id": "R-7", "kind": "ready_change_not_on_main", "change": "c"}])
        self.assertEqual(self.sig([feat_cycle(7, "Ready", method="openspec", change="c")], sur_main={"c"}), [])

    def test_ready_openspec_sans_change(self):
        self.assertEqual(self.sig([feat_cycle(7, "Ready", method="openspec")]),
                         [{"id": "R-7", "kind": "ready_without_change", "change": None}])

    def test_ready_direct_prompt_sans_change_sans_signal(self):
        self.assertEqual(self.sig([feat_cycle(7, "Ready", method="direct-prompt")]), [])

    def test_nom_de_change_non_sur_donne_aucun_change(self):
        for nom in ("a/b", "..", "archive", "a.b"):
            with self.subTest(nom=nom):
                self.assertEqual([s["kind"] for s in self.sig([feat_cycle(7, "Ready", method="openspec", change=nom)], sur_main={nom})],
                                 ["ready_change_not_on_main"])

    def test_features_fermees_ou_autres_status_ignorees(self):
        fermee = feat_cycle(1, "In progress")
        fermee["open"] = False
        self.assertEqual(self.sig([fermee, feat_cycle(2, "Todo", method="openspec"), feat_cycle(3, "Done")]), [])

    def test_ordre_du_rang_conserve(self):
        sig = self.sig([feat_cycle(9, "Ready", method="openspec"), feat_cycle(2, "In progress")])
        self.assertEqual([s["id"] for s in sig], ["R-9", "R-2"])

    def test_git_illisible(self):
        feats = [feat_cycle(7, "In progress"), feat_cycle(8, "Ready", method="openspec")]
        self.assertEqual(roadmap.signalements_cycle(feats, None, set()), [{"kind": "git_unreadable"}])
        self.assertEqual(roadmap.signalements_cycle(feats, set(), None), [{"kind": "git_unreadable"}])


class TestProposable(unittest.TestCase):
    """Fonction pure `proposable` (design D5, D11) : genre d'une feature proposable, ou None."""

    JOUR = datetime.date(2026, 10, 13)

    def prop(self, status="Ready", ouvert=True, blockers=(), etat=None, **bloc):
        f = {"id": "R-1", "open": ouvert, "status": status, "block": bloc, "blockers": list(blockers)}
        return roadmap.proposable(f, self.JOUR, etat if etat is not None else {})

    def test_ready_quelle_que_soit_la_methode(self):
        self.assertEqual(self.prop(method="openspec", change="c"), "ready")
        self.assertEqual(self.prop(method="direct-prompt"), "ready")

    def test_todo_direct_prompt(self):
        self.assertEqual(self.prop("Todo", method="direct-prompt"), "todo_direct")

    def test_todo_openspec_sans_change_est_un_cadrage(self):
        self.assertEqual(self.prop("Todo", method="openspec"), "todo_framing")

    def test_todo_openspec_avec_change_jamais(self):
        self.assertIsNone(self.prop("Todo", method="openspec", change="c"))

    def test_todo_direct_prompt_avec_change_jamais(self):
        # spec workflow-roadmap, « The reader proposes a batch on a milestone » : un Todo dont le change est nommé n'est jamais retenu (D11)
        self.assertIsNone(self.prop("Todo", method="direct-prompt", change="c"))

    def test_autres_status_et_features_fermees(self):
        self.assertIsNone(self.prop("In progress", method="direct-prompt"))
        self.assertIsNone(self.prop("Done", method="direct-prompt"))
        self.assertIsNone(self.prop("Ready", ouvert=False))

    def test_bloqueur_ouvert_ou_date_future(self):
        self.assertIsNone(self.prop("Todo", blockers=["R-2"], etat={"R-2": True}, method="direct-prompt"))
        self.assertEqual(self.prop("Todo", blockers=["R-2"], etat={"R-2": False}, method="direct-prompt"), "todo_direct")
        self.assertIsNone(self.prop(not_before=datetime.date(2026, 10, 14), method="direct-prompt"))
        self.assertEqual(self.prop(not_before=datetime.date(2026, 10, 13), method="direct-prompt"), "ready")


if __name__ == "__main__":
    unittest.main()
