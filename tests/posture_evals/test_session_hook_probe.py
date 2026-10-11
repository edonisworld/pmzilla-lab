"""Sonde : les séances d'évaluation (`claude -p`) lancent-elles les hooks SessionStart, avec l'environnement de la séance ?

Un seul test, sauté sauf PMZILLA_LAB_HOOK_PROBE=1 (il démarre une séance payante).
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import posture_evals as essai  # noqa: E402

HOOK = 'printf \'%s\' "$PMZILLA_LAB_CASES_DBNAME" > "$PMZILLA_LAB_HOOK_PROBE_MARKER"'


class SondeHookSessionStart(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("PMZILLA_LAB_HOOK_PROBE") == "1",
                         "set PMZILLA_LAB_HOOK_PROBE=1 to run (starts one paid session)")
    def test_le_hook_session_start_tourne_avec_l_environnement_de_la_seance(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            copie, autre = Path(d1), Path(d2)
            (copie / ".claude").mkdir()
            reglages = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": HOOK}]}]}}
            (copie / ".claude" / "settings.json").write_text(json.dumps(reglages), encoding="utf-8")
            mcp = autre / "mcp.json"
            mcp.write_text(json.dumps({"mcpServers": {}}), encoding="utf-8")
            marqueur = autre / "marqueur.txt"
            environnement = {"PMZILLA_LAB_CASES_DBNAME": "pmzilla_eval_probe",
                             "PMZILLA_LAB_HOOK_PROBE_MARKER": str(marqueur)}
            # run_session ne prend pas d'environnement : le sous-processus hérite de os.environ
            with mock.patch.dict(os.environ, environnement):
                essai.run_session("Reply with the single word OK.", copie, mcp, None, autre / "trace.jsonl", False)
            self.assertTrue(marqueur.exists(), "le hook SessionStart n'a pas tourné")
            self.assertEqual(marqueur.read_text(encoding="utf-8"), "pmzilla_eval_probe")


if __name__ == "__main__":
    unittest.main()
