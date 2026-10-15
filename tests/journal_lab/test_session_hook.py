"""Hook de début de session : .claude/settings.json déclare deux commandes SessionStart, dans cet ordre
(rappel des revues dues, puis rappel de la file GitHub de la spec github-roadmap), et aucun autre hook.

    python3 -m unittest discover -s tests/journal_lab -v
"""
import json
import unittest
from pathlib import Path

REGLAGES = Path(__file__).resolve().parents[2] / ".claude" / "settings.json"
COMMANDES = [
    "uv run tools/journal_lab.py experiment due --session-hook",
    "uv run tools/roadmap.py reminder --session-hook",
]


class HookDeSession(unittest.TestCase):
    def setUp(self):
        self.hooks = json.loads(REGLAGES.read_text(encoding="utf-8")).get("hooks", {})

    def test_session_start_lance_les_deux_rappels_dans_l_ordre(self):
        groupes = self.hooks.get("SessionStart", [])
        commandes = [h.get("command") for g in groupes for h in g.get("hooks", []) if h.get("type") == "command"]
        self.assertEqual(commandes, COMMANDES)

    def test_aucun_autre_hook_n_est_declare(self):
        self.assertEqual(list(self.hooks), ["SessionStart"])


if __name__ == "__main__":
    unittest.main()
