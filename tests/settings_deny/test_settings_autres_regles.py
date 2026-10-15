"""
Tests des réglages de .claude/settings.json autres que les règles « deny » : aucune règle allow / ask, aucune autre permission,
et les deux hooks de début de session attendus (revues dues, rappel de la file).

    python3 -m unittest discover -s tests/settings_deny -v
"""
import json
import unittest
from pathlib import Path

REGLAGES = json.loads((Path(__file__).resolve().parents[2] / ".claude" / "settings.json").read_text(encoding="utf-8"))

# Seule règle allow admise : le pont provisoire vers les notes de contexte (en attendant R-59). Les originaux restent en deny.
ALLOW_ATTENDU = ["Read(~/PMZilla-Lab/Contexte-Lab/notes/**)"]

HOOK_REVUES = {"type": "command", "command": "uv run tools/journal_lab.py experiment due --session-hook"}
HOOK_RAPPEL = {"type": "command", "command": "uv run tools/roadmap.py reminder --session-hook"}  # change github-roadmap, D16
HOOKS_ATTENDUS = {"SessionStart": [{"hooks": [HOOK_REVUES, HOOK_RAPPEL]}]}


class AutresRegles(unittest.TestCase):
    def test_seules_les_cles_permissions_et_hooks(self):
        self.assertEqual(sorted(REGLAGES), ["hooks", "permissions"])

    def test_aucune_regle_hors_deny(self):
        self.assertEqual(sorted(REGLAGES["permissions"]), ["allow", "deny"], "toute règle allow, ask ou autre permission doit être attendue ici")

    def test_seule_la_regle_allow_des_notes_de_contexte(self):
        self.assertEqual(REGLAGES["permissions"]["allow"], ALLOW_ATTENDU)
        for cle in ("ask", "defaultMode", "additionalDirectories"):
            self.assertNotIn(cle, REGLAGES["permissions"])

    def test_les_originaux_du_contexte_sont_refuses_en_lecture(self):
        deny = REGLAGES["permissions"]["deny"]
        self.assertIn("Read(~/PMZilla-Lab/Contexte-Lab/originaux/**)", deny)
        self.assertIn("Read(**/Contexte-Lab/originaux/**)", deny)

    def test_le_rappel_de_la_file_est_a_cote_du_hook_des_revues(self):
        commandes = [h["command"] for g in REGLAGES["hooks"].get("SessionStart", []) for h in g["hooks"]]
        self.assertIn(HOOK_REVUES["command"], commandes)
        self.assertIn(HOOK_RAPPEL["command"], commandes, "le hook de rappel de la file (roadmap.py reminder --session-hook) manque")

    def test_les_seuls_hooks_sont_les_deux_de_debut_de_session(self):
        self.assertEqual(REGLAGES["hooks"], HOOKS_ATTENDUS)


if __name__ == "__main__":
    unittest.main()
