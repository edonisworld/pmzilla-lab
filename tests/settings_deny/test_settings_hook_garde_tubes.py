"""Section hooks de .claude/settings.json et garde des tubes (change deny-rules-review, design D9 et tâche 5.3).

Les deux hooks de début de session restent attendus ; une fois posée par l'auteur, la section accepte en plus exactement UNE entrée
de la garde des tubes, sous sa forme PreToolUse (Q4 option B, choisie par l'auteur le 2026-10-19) : matcher Bash, une seule commande
qui nomme tools/pipe_guard.py avec --event pre. La forme PostToolUse (option A) n'est plus admise : un retour à A changerait ce test
en même temps que l'entrée. Tout autre hook fait échouer le test. Avant la pose, le fichier réel passe sans changement.

    python3 -m unittest discover -s tests/settings_deny -v
"""
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REGLAGES = json.loads((Path(__file__).resolve().parents[2] / ".claude" / "settings.json").read_text(encoding="utf-8"))

HOOK_REVUES = {"type": "command", "command": "uv run tools/journal_lab.py experiment due --session-hook"}
HOOK_RAPPEL = {"type": "command", "command": "uv run tools/roadmap.py reminder --session-hook"}
DEBUT_DE_SESSION = [{"hooks": [HOOK_REVUES, HOOK_RAPPEL]}]
EVENEMENT_GARDE = "PreToolUse"       # forme B, seule admise
OPTIONS = {"PostToolUse": "post", "PreToolUse": "pre"}


def entree_garde(evenement: str = EVENEMENT_GARDE) -> list:
    """L'entrée de la garde des tubes sous l'événement donné ; la forme PostToolUse ne sert qu'à vérifier qu'elle est refusée."""
    return [{"matcher": "Bash", "hooks": [{"type": "command",
                                           "command": f'python3 "$CLAUDE_PROJECT_DIR/tools/pipe_guard.py" --event {OPTIONS[evenement]}'}]}]


def constats_hooks(hooks: dict) -> list:
    """Écarts de la section hooks : vide quand elle porte les deux hooks de début de session et, au plus, l'entrée PreToolUse de la
    garde des tubes."""
    trouves = []
    if hooks.get("SessionStart") != DEBUT_DE_SESSION:
        trouves.append("hooks de début de session différents des deux attendus")
    for evenement in sorted(set(hooks) - {"SessionStart"}):
        if evenement == "PostToolUse" and hooks[evenement] == entree_garde("PostToolUse"):
            trouves.append("garde des tubes sous PostToolUse : forme A non admise (D9, forme B choisie)")
        elif evenement != EVENEMENT_GARDE:
            trouves.append(f"hook inattendu : {evenement}")
        elif hooks[evenement] != entree_garde():
            trouves.append(f"entrée de la garde des tubes inattendue sous {evenement}")
    return trouves


class HookGardeDesTubes(unittest.TestCase):
    def avec(self, **ajouts):
        hooks = {"SessionStart": copy.deepcopy(DEBUT_DE_SESSION)}
        hooks.update(ajouts)
        return hooks

    def test_sans_entree_de_garde_passe(self):
        self.assertEqual(constats_hooks(self.avec()), [])

    def test_entree_pre_posee_passe(self):
        self.assertEqual(constats_hooks(self.avec(PreToolUse=entree_garde())), [])

    def test_forme_a_post_n_est_pas_reconnue(self):
        """Forme B choisie le 2026-10-19 : l'entrée PostToolUse exacte de l'ancienne recommandation échoue, seule ou avec la forme B."""
        self.assertEqual(constats_hooks(self.avec(PostToolUse=entree_garde("PostToolUse"))),
                         ["garde des tubes sous PostToolUse : forme A non admise (D9, forme B choisie)"])
        self.assertEqual(constats_hooks(self.avec(PostToolUse=entree_garde("PostToolUse"), PreToolUse=entree_garde())),
                         ["garde des tubes sous PostToolUse : forme A non admise (D9, forme B choisie)"])

    def test_autre_hook_echoue(self):
        self.assertEqual(constats_hooks(self.avec(Stop=entree_garde())), ["hook inattendu : Stop"])
        autre_post = entree_garde("PostToolUse")
        autre_post[0]["matcher"] = "Edit"
        self.assertEqual(constats_hooks(self.avec(PostToolUse=autre_post)), ["hook inattendu : PostToolUse"])

    def test_entree_avec_mauvais_matcher_ou_mauvaise_option_echoue(self):
        mauvais_matcher = entree_garde()
        mauvais_matcher[0]["matcher"] = "Edit"
        mauvaise_option = entree_garde()
        mauvaise_option[0]["hooks"][0]["command"] = mauvaise_option[0]["hooks"][0]["command"].replace("--event pre", "--event post")
        deux_commandes = entree_garde()
        deux_commandes[0]["hooks"].append(HOOK_RAPPEL)
        for entree in (mauvais_matcher, mauvaise_option, deux_commandes):
            with self.subTest(entree=entree):
                self.assertEqual(constats_hooks(self.avec(PreToolUse=entree)),
                                 ["entrée de la garde des tubes inattendue sous PreToolUse"])

    def test_hook_de_debut_de_session_retire_echoue(self):
        hooks = {"SessionStart": [{"hooks": [HOOK_REVUES]}]}
        self.assertEqual(constats_hooks(hooks), ["hooks de début de session différents des deux attendus"])

    def test_le_fichier_reel_passe(self):
        self.assertEqual(constats_hooks(REGLAGES["hooks"]), [])

    def test_les_hooks_admis_par_le_test_strict_sont_ceux_de_d9(self):
        """Le test strict de test_settings_autres_regles.py admet exactement les deux états de D9 : avant la pose, et la forme PreToolUse
        choisie par l'auteur le 2026-10-19 (Q4 option B) ; la forme PostToolUse n'y est pas admise."""
        import test_settings_autres_regles as strict
        attendus = [self.avec(), self.avec(PreToolUse=entree_garde())]
        self.assertNotIn(self.avec(PostToolUse=entree_garde("PostToolUse")), list(strict.HOOKS_ADMIS))
        self.assertEqual(list(strict.HOOKS_ADMIS), attendus)
        for hooks in strict.HOOKS_ADMIS:
            self.assertEqual(constats_hooks(hooks), [])

    def test_le_texte_de_l_entree_posee_est_celui_du_design(self):
        self.assertEqual(entree_garde()[0]["hooks"][0]["command"],
                         'python3 "$CLAUDE_PROJECT_DIR/tools/pipe_guard.py" --event pre')


if __name__ == "__main__":
    unittest.main()
