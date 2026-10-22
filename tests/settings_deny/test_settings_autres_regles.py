"""
Tests des réglages de .claude/settings.json autres que les règles « deny » : aucune règle ask, une seule règle allow admise une fois les règles du
contexte reposées (celle de `story_quality.py grid`, une fois posée ; avant, s'y ajoute la règle transitoire ANCIENNE_REGLE_ALLOW),
aucune autre permission,
et les deux hooks de début de session attendus (revues dues, rappel de la file), plus, une fois posée par l'auteur, l'entrée
de la garde des tubes (change deny-rules-review, D9).

    python3 -m unittest discover -s tests/settings_deny -v
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from etat_contexte import ANCIEN_DOSSIER, ANCIENNE_REGLE_ALLOW, DOSSIER, reposee  # noqa: E402

REGLAGES = json.loads((Path(__file__).resolve().parents[2] / ".claude" / "settings.json").read_text(encoding="utf-8"))

# Organisation-context (design D10, D16) : avant la tâche 9.3 de l'auteur, seule règle allow admise = le pont provisoire vers les notes de
# contexte (sous l'ancien nom du dossier) ; après, aucune règle allow : les notes ne se lisent que par la bibliothèque. Les originaux restent en deny.
# Ces tests passent dans les deux états ; test_settings_deny_contexte.py refuse l'état mélangé.
# Décision de l'auteur du 2026-10-20 (lot 7, mothra-session-guards) : une seule règle allow admise en plus, celle de `story_quality.py grid`
# (test_settings_deny_story_quality_grid.py), posée avec le bloc du lot 7 ; avant sa pose le fichier passe sans changement.
REGLE_GRID = "Bash(uv run tools/story_quality.py grid*)"
GRID_POSEE = REGLE_GRID in REGLAGES["permissions"].get("allow", [])
ALLOW_ATTENDU = ([] if reposee() else [ANCIENNE_REGLE_ALLOW]) + ([REGLE_GRID] if GRID_POSEE else [])
CLES_PERMISSIONS = ["allow", "deny"] if ALLOW_ATTENDU else ["deny"]

HOOK_REVUES = {"type": "command", "command": "uv run tools/journal_lab.py experiment due --session-hook"}
HOOK_RAPPEL = {"type": "command", "command": "uv run tools/roadmap.py reminder --session-hook"}  # change github-roadmap, D16
HOOKS_ATTENDUS = {"SessionStart": [{"hooks": [HOOK_REVUES, HOOK_RAPPEL]}]}


def avec_garde_des_tubes(evenement: str, option: str) -> dict:
    """Change deny-rules-review, D9 : la section hooks une fois posée l'entrée de la garde des tubes."""
    commande = f'python3 "$CLAUDE_PROJECT_DIR/tools/pipe_guard.py" --event {option}'
    return {**HOOKS_ATTENDUS, evenement: [{"matcher": "Bash", "hooks": [{"type": "command", "command": commande}]}]}


# Avant la pose (tâche 6.2 de deny-rules-review) : les deux hooks de début de session ; après : en plus l'entrée exacte de D9, sous la
# forme PreToolUse seulement (choix de l'auteur du 2026-10-19, Q4 option B). La forme PostToolUse n'est pas admise : un retour à A
# changerait ce test en même temps que l'entrée.
HOOKS_ADMIS = (HOOKS_ATTENDUS, avec_garde_des_tubes("PreToolUse", "pre"))


class AutresRegles(unittest.TestCase):
    def test_seules_les_cles_permissions_et_hooks(self):
        self.assertEqual(sorted(REGLAGES), ["hooks", "permissions"])

    def test_aucune_regle_hors_deny(self):
        self.assertEqual(sorted(REGLAGES["permissions"]), CLES_PERMISSIONS, "toute règle allow, ask ou autre permission doit être attendue ici")

    def test_seule_la_regle_allow_des_notes_de_contexte_avant_la_reprise_aucune_apres(self):
        self.assertEqual(REGLAGES["permissions"].get("allow", []), ALLOW_ATTENDU)
        for cle in ("ask", "defaultMode", "additionalDirectories"):
            self.assertNotIn(cle, REGLAGES["permissions"])

    def test_la_regle_allow_des_notes_est_retiree_quand_les_regles_sont_reposees(self):
        """Spec tooling-permission-guards, « Former context allow rule left » : reposées, les règles n'ont plus d'allow."""
        if reposee():
            self.assertNotIn(ANCIENNE_REGLE_ALLOW, REGLAGES["permissions"].get("allow", []))

    def test_les_originaux_du_contexte_sont_refuses_en_lecture(self):
        deny = REGLAGES["permissions"]["deny"]
        nom = DOSSIER if reposee() else ANCIEN_DOSSIER
        self.assertIn(f"Read(~/PMZilla-Lab/{nom}/originaux/**)", deny)
        self.assertIn(f"Read(**/{nom}/originaux/**)", deny)

    def test_le_rappel_de_la_file_est_a_cote_du_hook_des_revues(self):
        commandes = [h["command"] for g in REGLAGES["hooks"].get("SessionStart", []) for h in g["hooks"]]
        self.assertIn(HOOK_REVUES["command"], commandes)
        self.assertIn(HOOK_RAPPEL["command"], commandes, "le hook de rappel de la file (roadmap.py reminder --session-hook) manque")

    def test_les_seuls_hooks_sont_les_deux_de_debut_de_session(self):
        """Plus, une fois posée, l'entrée exacte de la garde des tubes (deny-rules-review, D9) ; tout autre hook échoue."""
        self.assertIn(REGLAGES["hooks"], HOOKS_ADMIS)


if __name__ == "__main__":
    unittest.main()
