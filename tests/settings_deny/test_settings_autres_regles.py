"""
Tests des réglages de .claude/settings.json autres que les règles « deny » : aucune règle ask, une seule règle allow admise une fois les règles du
contexte reposées (celle de `story_quality.py grid`, une fois posée ; avant, s'y ajoute la règle transitoire ANCIENNE_REGLE_ALLOW),
aucune autre permission,
et les deux hooks de début de session attendus (revues dues, rappel de la file), plus, une fois posée par l'auteur, l'entrée
de la garde des tubes (change deny-rules-review, D9), dans l'état d'après P2 (trois gardes ; design D12 de session-guard-n1) seulement : l'admission
de l'ancien état (deux gardes, `python3` sans -I) est retirée par la tâche 14.1.

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
# Décision de l'auteur du 2026-10-26 (session-runner) : une règle allow de plus, exacte et sans argument, pour le runner complet de la session
# (test_settings_deny_session_runner.py) ; ses gardes de session sont dans le lanceur lui-même. Avant sa pose le fichier passe sans changement.
REGLE_RUNNER = "Bash(bash tests/run_all.sh)"
RUNNER_POSE = REGLE_RUNNER in REGLAGES["permissions"].get("allow", [])
ALLOW_ATTENDU = ([] if reposee() else [ANCIENNE_REGLE_ALLOW]) + ([REGLE_GRID] if GRID_POSEE else []) + ([REGLE_RUNNER] if RUNNER_POSE else [])
CLES_PERMISSIONS = ["allow", "deny"] if ALLOW_ATTENDU else ["deny"]

HOOK_REVUES = {"type": "command", "command": "uv run tools/journal_lab.py experiment due --session-hook"}
HOOK_RAPPEL = {"type": "command", "command": "uv run tools/roadmap.py reminder --session-hook"}  # change github-roadmap, D16
HOOKS_ATTENDUS = {"SessionStart": [{"hooks": [HOOK_REVUES, HOOK_RAPPEL]}]}


def avec_garde_des_tubes(evenement: str, option: str) -> dict:
    """Change deny-rules-review, D9 : la section hooks avec l'entrée de la garde des tubes dans l'ANCIEN état (deux gardes, `python3` sans -I). Cet état
    n'est plus admis (tâche 14.1) ; la fonction ne sert qu'à vérifier qu'il est refusé."""
    commande = f'python3 "$CLAUDE_PROJECT_DIR/tools/pipe_guard.py" --event {option}'
    npm = {"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR/tools/npm_guard.py"', "onFailure": "block", "timeout": 10}  # R-133, R-134
    return {**HOOKS_ATTENDUS, evenement: [{"matcher": "Bash", "hooks": [{"type": "command", "command": commande}, npm]}]}


def avec_les_trois_gardes() -> dict:
    """Change session-guard-n1, tâche 8.3, design D12 : l'état après P2, tel que l'écrit le fichier d'étape session-guard-n1-p2.zsh. Une seule entrée PreToolUse, matcher
    Bash, dans cet ordre la garde des tubes, la garde npm, la garde de session, les trois par `python3 -I` et `$HOME` littéral ; `onFailure: block` et un
    délai de 10 s pour la garde npm et la garde de session.
    Source : APRES_P2 du fichier d'étape session-guard-n1-p2.zsh (copié ici à la main). Un écart est détecté par
    test_les_hooks_admis_par_le_test_strict_sont_ceux_de_d9_et_de_d12 (test_settings_hook_garde_tubes.py, qui redéfinit la forme de son côté) et, P2 étant
    posé, par test_les_seuls_hooks_sont_les_deux_de_debut_de_session sur le .claude/settings.json réel ; la commande `strict` du fichier d'étape ne se
    relance plus (arrêt en code 3 à l'étape 1)."""
    espace = "$HOME/PMZilla-Lab/workspace"
    gardes = [{"type": "command", "command": f'python3 -I "{espace}/tools/pipe_guard.py" --event pre'},
              {"type": "command", "command": f'python3 -I "{espace}/tools/npm_guard.py"', "onFailure": "block", "timeout": 10},
              {"type": "command", "command": f'python3 -I "{espace}/tools/garde_session.py"', "onFailure": "block", "timeout": 10}]
    return {**HOOKS_ATTENDUS, "PreToolUse": [{"matcher": "Bash", "hooks": gardes}]}


# Sans entrée (avant la pose, tâche 6.2 de deny-rules-review) : les deux hooks de début de session ; avec : en plus l'entrée de l'état d'après P2
# (trois gardes ; tâche 8.3 de session-guard-n1, R-20261107-26, Q3 et P2 ; design D12), sous la forme PreToolUse seulement (choix de l'auteur du
# 2026-10-19, Q4 option B ; la forme PostToolUse n'est pas admise). Tout ou rien : un mélange des deux formes n'est pas dans la liste ;
# test_settings_hook_garde_tubes.py nomme la garde en faute. L'ancien état (deux gardes, `python3` sans -I) a été retiré de la liste par la tâche 14.1.
# Le fichier d'étape de P2 lit cette constante.
HOOKS_ADMIS = (HOOKS_ATTENDUS, avec_les_trois_gardes())


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
        """Plus, une fois posée, l'entrée exacte des gardes dans l'état de D12 après P2 (tâche 8.3, tout ou rien ; l'ancien état est refusé depuis la
        tâche 14.1) ; tout autre hook échoue."""
        from test_settings_hook_garde_tubes import constats_hooks   # import tardif : ce module importe celui-ci
        self.assertIn(REGLAGES["hooks"], HOOKS_ADMIS, "section hooks hors de l'état de D12 (sans entrée ou trois gardes, tout ou rien) : "
                      + "; ".join(constats_hooks(REGLAGES["hooks"])))

    def test_seul_l_etat_de_d12_est_admis_l_ancien_etat_et_les_melanges_sont_refuses(self):
        """Tâche 14.1 (suite de la 8.3 ; R-20261107-26, Q3 et P2) : l'état après P2 est dans la liste ; l'ancien état (deux gardes, `python3` sans -I)
        n'y est plus ; un mélange (une garde dans chaque état, la garde de session seule ou manquante) n'y est pas non plus.
        Ancien attendu : assertIn(ancien, HOOKS_ADMIS). Nouvel attendu : assertNotIn(ancien, HOOKS_ADMIS)."""
        ancien, nouveau = avec_garde_des_tubes("PreToolUse", "pre"), avec_les_trois_gardes()
        self.assertNotIn(ancien, HOOKS_ADMIS)
        self.assertIn(nouveau, HOOKS_ADMIS)
        gardes_anciennes, gardes_nouvelles = ancien["PreToolUse"][0]["hooks"], nouveau["PreToolUse"][0]["hooks"]
        for gardes in ([gardes_nouvelles[0], gardes_anciennes[1]], [gardes_anciennes[0], gardes_nouvelles[1]], gardes_nouvelles[:2],
                       gardes_anciennes + gardes_nouvelles[2:], [gardes_nouvelles[1], gardes_nouvelles[0], gardes_nouvelles[2]]):
            with self.subTest(gardes=gardes):
                self.assertNotIn({**HOOKS_ATTENDUS, "PreToolUse": [{"matcher": "Bash", "hooks": gardes}]}, HOOKS_ADMIS)


if __name__ == "__main__":
    unittest.main()
