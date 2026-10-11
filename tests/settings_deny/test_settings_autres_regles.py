"""
Tests des réglages de .claude/settings.json autres que les règles « deny » : aucune règle allow / ask, aucune autre permission,
et le seul hook attendu.

    python3 -m unittest discover -s tests/settings_deny -v
"""
import json
import unittest
from pathlib import Path

REGLAGES = json.loads((Path(__file__).resolve().parents[2] / ".claude" / "settings.json").read_text(encoding="utf-8"))

HOOKS_ATTENDUS = {"SessionStart": [{"hooks": [{"type": "command", "command": "uv run tools/journal_lab.py experiment due --session-hook"}]}]}


class AutresRegles(unittest.TestCase):
    def test_seules_les_cles_permissions_et_hooks(self):
        self.assertEqual(sorted(REGLAGES), ["hooks", "permissions"])

    def test_aucune_regle_hors_deny(self):
        self.assertEqual(sorted(REGLAGES["permissions"]), ["deny"], "toute règle allow, ask ou autre permission doit être attendue ici")

    def test_aucune_regle_allow_ni_ask(self):
        for cle in ("allow", "ask", "defaultMode", "additionalDirectories"):
            self.assertNotIn(cle, REGLAGES["permissions"])

    def test_le_seul_hook_est_celui_de_debut_de_session(self):
        self.assertEqual(REGLAGES["hooks"], HOOKS_ATTENDUS)


if __name__ == "__main__":
    unittest.main()
