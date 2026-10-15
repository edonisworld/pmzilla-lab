"""
Tests du modèle partagé de la file sur GitHub (tools/roadmap_model.py), sans réseau ni gh.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/roadmap_model -q -f
"""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import roadmap_model as m  # noqa: E402

BLOC = {"id": "R-7", "theme": "outillage", "estimate": "1h30", "method": "openspec", "model": "sonnet", "rank": 70,
        "conditions": "", "change": "github-roadmap", "not_before": "2026-11-01"}

TASKS = """# Tasks

Intro text.

## 0. Preconditions [user]

- [ ] 0.1 Commit the edit.

## 1. Tags [model: haiku]

- [x] 1.1 Add tags.
- [x] 1.2 Add more.

## 2. Model [model: sonnet] [parallel]

Files: x.

- [x] 2.1 Tests first.
- [ ] 2.2 [user] User step: check the label.

### Not a group

## 3. Wrap [model: opus]

- [x] 3.1 Done.
"""


class TestMarkers(unittest.TestCase):
    def test_keys(self):
        self.assertEqual(m.feature_key(62), "R-62")
        self.assertEqual(m.group_key(62, 3), "R-62/g3")
        self.assertEqual(m.task_key(62, "2.2"), "R-62/t2.2")

    def test_marker_roundtrip(self):
        for k in ("R-62", "R-62/g3", "R-62/t2.2"):
            self.assertEqual(m.parse_marker(m.marker(k) + "\n\nbody"), k)

    def test_marker_text(self):
        self.assertEqual(m.marker("R-1"), "<!-- roadmap-id: R-1 -->")

    def test_marker_absent_or_not_first(self):
        self.assertIsNone(m.parse_marker("no marker"))
        self.assertIsNone(m.parse_marker("text\n<!-- roadmap-id: R-1 -->"))

    def test_marker_bad_key(self):
        with self.assertRaises(ValueError):
            m.marker("X-1")
        self.assertIsNone(m.parse_marker("<!-- roadmap-id: nope -->"))

    def test_parse_key(self):
        self.assertEqual(m.parse_key("R-62"), ("feature", 62, None))
        self.assertEqual(m.parse_key("R-62/g3"), ("group", 62, "3"))
        self.assertEqual(m.parse_key("R-62/t2.2"), ("task", 62, "2.2"))
        with self.assertRaises(ValueError):
            m.parse_key("R-62/x")


class TestTitles(unittest.TestCase):
    def test_titles(self):
        self.assertEqual(m.feature_title(5, "Hello"), "R-5 · Hello")
        self.assertEqual(m.group_title(5, 2, "Shared model"), "R-5 · 2. Shared model")
        self.assertEqual(m.user_task_title(5, "2.2"), "R-5 · 2.2 (user step)")

    def test_parse_title(self):
        self.assertEqual(m.parse_title("R-5 · Hello"), (5, "Hello"))
        self.assertEqual(m.parse_title("R-5 · 2. Shared model"), (5, "2. Shared model"))
        self.assertIsNone(m.parse_title("R5 - Hello"))
        self.assertIsNone(m.parse_title("R-5 Hello"))
        self.assertIsNone(m.parse_title("R-x · Hello"))


class TestLabels(unittest.TestCase):
    def test_names(self):
        self.assertEqual(m.label_theme("edition"), "theme:edition")
        self.assertEqual(m.label_model("opus"), "model:opus")
        self.assertEqual((m.LABEL_FEATURE, m.LABEL_TASK, m.LABEL_PARALLEL, m.LABEL_USER),
                         ("type:feature", "type:task", "parallel", "owner:user"))

    def test_bad_values(self):
        with self.assertRaises(ValueError):
            m.label_theme("nope")
        with self.assertRaises(ValueError):
            m.label_model("tbd")

    def test_all_labels(self):
        t = m.all_labels()
        self.assertEqual(len(t), 2 + 8 + 3 + 2 + 1)
        self.assertIn("theme:fiabilite", t)


class TestLabelEditionPublique(unittest.TestCase):
    """Étiquette de l'édition publique (edition-publish-tooling, D19)."""

    def test_constante_du_nom(self):
        self.assertEqual(m.LABEL_EDITION_PUBLIC, "edition:public")

    def test_dans_all_labels(self):
        self.assertIn("edition:public", m.all_labels())
        self.assertEqual(m.all_labels().count("edition:public"), 1)


class TestBlock(unittest.TestCase):
    def test_roundtrip(self):
        body = m.marker("R-7") + "\n\n" + m.render_block(BLOC) + "\n\nFree text.\n"
        self.assertEqual(m.parse_block(body), BLOC)

    def test_info_string(self):
        self.assertIn("```roadmap\n", m.render_block(BLOC))

    def test_missing_block(self):
        with self.assertRaises(m.BlockError):
            m.parse_block("nothing")

    def test_two_blocks(self):
        b = m.render_block(BLOC)
        with self.assertRaises(m.BlockError):
            m.parse_block(b + "\n" + b)

    def test_not_a_mapping(self):
        with self.assertRaises(m.BlockError):
            m.parse_block("```roadmap\n- a\n```")

    def test_dates_read_as_strings(self):
        b = m.parse_block(m.render_block(BLOC))
        self.assertEqual(b["not_before"], "2026-11-01")

    def test_valid(self):
        self.assertEqual(m.validate_block(BLOC), [])
        self.assertEqual(m.validate_block(BLOC, marker_key="R-7", theme_label="outillage"), [])

    def test_missing_required(self):
        b = {k: v for k, v in BLOC.items() if k not in ("theme", "model")}
        pb = m.validate_block(b)
        self.assertTrue(any("theme" in p for p in pb))
        self.assertTrue(any("model" in p for p in pb))

    def test_bad_values(self):
        for k, v in (("theme", "x"), ("method", "x"), ("model", "x"), ("estimate", "soon"), ("rank", 0),
                     ("rank", "1"), ("rank", True), ("id", "R7"), ("conditions", 3), ("not_before", "2026-13-01"),
                     ("due", "tomorrow"), ("change", "")):
            self.assertTrue(m.validate_block({**BLOC, k: v}), k)

    def test_estimates(self):
        for e in ("45min", "2h", "1h30", "tbd"):
            self.assertEqual(m.validate_block({**BLOC, "estimate": e}), [], e)

    def test_zero_estimate_rejected(self):
        for e in ("0min", "0h", "0h00", "00min"):
            self.assertTrue(m.validate_block({**BLOC, "estimate": e}), e)

    def test_models(self):
        self.assertEqual(m.validate_block({**BLOC, "model": "tbd"}), [])

    def test_done_on_unknown(self):
        self.assertEqual(m.validate_block({**BLOC, "done_on": "unknown"}), [])
        self.assertTrue(m.validate_block({**BLOC, "started_on": "unknown"}))

    def test_rank_required_when_open_only(self):
        b = {k: v for k, v in BLOC.items() if k != "rank"}
        self.assertTrue(m.validate_block(b))
        self.assertEqual(m.validate_block(b, is_open=False), [])

    def test_unknown_key(self):
        self.assertTrue(m.validate_block({**BLOC, "foo": 1}))

    def test_identity_mismatch(self):
        self.assertTrue(m.validate_block(BLOC, marker_key="R-8"))
        self.assertTrue(m.validate_block(BLOC, theme_label="edition"))


class TestStatus(unittest.TestCase):
    def test_table(self):
        self.assertEqual(m.status_of_state("ready"), ("open", "Ready"))
        self.assertEqual(m.status_of_state("in-progress"), ("open", "In progress"))
        self.assertEqual(m.status_of_state("blocked"), ("open", "Todo"))
        self.assertEqual(m.status_of_state("done"), ("closed", "Done"))

    def test_unknown(self):
        with self.assertRaises(ValueError):
            m.status_of_state("wip")

    def test_statuses(self):
        self.assertEqual(m.STATUSES, ("Todo", "Ready", "In progress", "Done"))


class TestTasksHeadings(unittest.TestCase):
    def test_level3_heading_keeps_current_group(self):
        g = m.parse_tasks("## 1. A [model: haiku]\n\n- [ ] 1.1 x\n\n### Details\n\n- [ ] 1.2 y\n", "d")
        self.assertEqual([t.id for t in g[0].tasks], ["1.1", "1.2"])

    def test_heading_in_code_block_keeps_current_group(self):
        text = "## 1. A [model: haiku]\n\n- [ ] 1.1 x\n\n```sh\n# a comment\n### not a heading\n```\n\n- [ ] 1.2 y\n"
        g = m.parse_tasks(text, "d")
        self.assertEqual([t.id for t in g[0].tasks], ["1.1", "1.2"])

    def test_level2_heading_ends_the_group(self):
        g = m.parse_tasks("## 1. A [model: haiku]\n\n- [ ] 1.1 x\n\n## Notes\n\n- [ ] 9.9 z\n", "d")
        self.assertEqual([t.id for t in g[0].tasks], ["1.1"])

    def test_level1_heading_ends_the_group(self):
        g = m.parse_tasks("## 1. A [model: haiku]\n\n- [ ] 1.1 x\n\n# Other\n\n- [ ] 9.9 z\n", "d")
        self.assertEqual([t.id for t in g[0].tasks], ["1.1"])


class TestTasksParser(unittest.TestCase):
    def setUp(self):
        self.g = m.parse_tasks(TASKS, "demo")

    def test_groups(self):
        self.assertEqual([g.number for g in self.g], [0, 1, 2, 3])
        self.assertEqual([g.title for g in self.g], ["Preconditions", "Tags", "Model", "Wrap"])

    def test_kinds(self):
        self.assertEqual([g.kind for g in self.g], ["user", "agent", "agent", "agent"])
        self.assertEqual([g.model for g in self.g], [None, "haiku", "sonnet", "opus"])
        self.assertEqual([g.parallel for g in self.g], [False, False, True, False])

    def test_tasks(self):
        g2 = self.g[2]
        self.assertEqual([t.id for t in g2.tasks], ["2.1", "2.2"])
        self.assertEqual([t.done for t in g2.tasks], [True, False])
        self.assertEqual([t.user for t in g2.tasks], [False, True])

    def test_user_tasks_of_agent_group(self):
        self.assertEqual([t.id for t in m.user_tasks(self.g[2])], ["2.2"])
        self.assertEqual(m.user_tasks(self.g[1]), [])

    def test_complete(self):
        self.assertTrue(m.group_complete(self.g[1]))
        self.assertFalse(m.group_complete(self.g[2]))
        self.assertFalse(m.group_complete(self.g[0]))
        self.assertTrue(m.group_complete(self.g[3]))
        self.assertTrue(m.task_complete(self.g[2].tasks[0]))
        self.assertFalse(m.task_complete(self.g[2].tasks[1]))

    def test_empty_group_not_complete(self):
        g = m.parse_tasks("## 1. Empty [model: haiku]\n\nNo tasks.\n", "demo")
        self.assertFalse(m.group_complete(g[0]))

    def test_uppercase_x_ticks(self):
        g = m.parse_tasks("## 1. A [user]\n\n- [X] 1.1 Done.\n", "demo")
        self.assertTrue(g[0].tasks[0].done)

    def test_untagged_is_plan_error(self):
        txt = "## 1. A [model: haiku]\n\n- [ ] 1.1 x\n\n## 2. B\n\n- [ ] 2.1 x\n\n## 3. C [parallel]\n"
        with self.assertRaises(m.PlanError) as cm:
            m.parse_tasks(txt, "demo")
        self.assertEqual(cm.exception.change, "demo")
        self.assertEqual(cm.exception.untagged, [2, 3])
        self.assertIn("demo", str(cm.exception))
        self.assertIn("tasks.md groups untagged: 2, 3", str(cm.exception))

    def test_invalid_combinations_are_plan_errors(self):
        for h in ("## 1. A [model: opus] [model: haiku]", "## 1. A [user] [model: opus]", "## 1. A [model: gpt]",
                  "## 1. A [parallel] [user]x"):
            with self.assertRaises(m.PlanError, msg=h):
                m.parse_tasks(h + "\n", "demo")

    def test_user_group_with_parallel(self):
        g = m.parse_tasks("## 4. Check [user] [parallel]\n", "demo")
        self.assertEqual((g[0].kind, g[0].parallel), ("user", True))

    def test_title_keeps_inner_brackets(self):
        g = m.parse_tasks("## 1. Fix [x] thing [model: opus]\n", "demo")
        self.assertEqual(g[0].title, "Fix [x] thing")

    def test_no_groups(self):
        self.assertEqual(m.parse_tasks("# Tasks\n\nnothing\n", "demo"), [])

    def test_tasks_not_leaking_across_groups(self):
        self.assertEqual([t.id for t in self.g[1].tasks], ["1.1", "1.2"])
        self.assertEqual([t.id for t in self.g[3].tasks], ["3.1"])

    def test_real_tasks_file_of_this_change(self):
        p = RACINE / "openspec" / "changes" / "github-roadmap" / "tasks.md"
        if not p.exists():
            self.skipTest("change archived")
        g = m.parse_tasks(p.read_text(encoding="utf-8"), "github-roadmap")
        self.assertGreaterEqual(len(g), 16)
        self.assertEqual(g[0].kind, "user")


class TestRepoFromUrl(unittest.TestCase):
    def test_every_url_form_gives_owner_and_name(self):
        for url in ("git@github.com:owner-x/repo-y.git", "https://github.com/owner-x/repo-y.git", "https://github.com/owner-x/repo-y",
                    "https://github.com/owner-x/repo-y/", "ssh://git@github.com/owner-x/repo-y.git", "  git@github.com:owner-x/repo-y.git\n"):
            self.assertEqual(m.repo_from_url(url), "owner-x/repo-y", url)

    def test_not_a_github_remote(self):
        for url in ("", None, "https://example.org/a/b", "nonsense", "https://github.com/only-owner"):
            self.assertIsNone(m.repo_from_url(url), url)


class TestSettings(unittest.TestCase):
    def test_empty_value_and_empty_text(self):
        for text in ("", "\n", "# comment only\n", "current_release:\n", "current_release: ''\n", "current_release: null\n"):
            self.assertEqual(m.parse_settings(text), {"current_release": ""}, repr(text))

    def test_milestone_name(self):
        self.assertEqual(m.parse_settings("current_release: Hydra\n"), {"current_release": "Hydra"})
        self.assertEqual(m.parse_settings("# c\ncurrent_release: 'Edition 1.2'\n"), {"current_release": "Edition 1.2"})

    def test_refused(self):
        for text in ("- a\n- b\n", "just text", "current_release: [a]\n", "current_release: 3\n", "current_release: ' x'\n",
                     "current_release: Hydra\nother: 1\n", "other: 1\n", "a: [\n"):
            with self.assertRaises(ValueError, msg=text):
                m.parse_settings(text)

    def test_tracked_file_is_valid(self):
        """The value changes at each publication of the edition: the test requires a readable file, not a value."""
        texte = (RACINE / m.SETTINGS_FILE).read_text(encoding="utf-8")
        self.assertIsInstance(m.parse_settings(texte)["current_release"], str)


if __name__ == "__main__":
    unittest.main()
