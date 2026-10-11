"""Hook de début de session : .claude/settings.json déclare le rappel des revues dues, et rien d'autre.

    python3 -m unittest discover -s tests/journal_lab -v
"""
import json
import unittest
from pathlib import Path

REGLAGES = Path(__file__).resolve().parents[2] / ".claude" / "settings.json"
COMMANDE = "uv run tools/journal_lab.py experiment due --session-hook"


class HookDeSession(unittest.TestCase):
    def setUp(self):
        self.hooks = json.loads(REGLAGES.read_text(encoding="utf-8")).get("hooks", {})

    def test_session_start_lance_le_rappel_des_revues_dues(self):
        groupes = self.hooks.get("SessionStart", [])
        commandes = [h.get("command") for g in groupes for h in g.get("hooks", []) if h.get("type") == "command"]
        self.assertEqual(commandes, [COMMANDE])

    def test_aucun_autre_hook_n_est_declare(self):
        self.assertEqual(list(self.hooks), ["SessionStart"])


if __name__ == "__main__":
    unittest.main()
