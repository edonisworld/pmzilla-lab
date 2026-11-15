"""Section hooks de .claude/settings.json et garde des tubes (change deny-rules-review, design D9 et tâche 5.3).

Les deux hooks de début de session restent attendus ; une fois posée par l'auteur, la section accepte en plus exactement UNE entrée
PreToolUse (Q4 option B, choisie par l'auteur le 2026-10-19) : matcher Bash. Depuis la tâche 8.3 de session-guard-n1 (design D12, R-20261107-26) l'entrée
admet, tout ou rien, l'état d'après P2 : trois gardes (tubes, npm avec onFailure block et timeout 10, session) lancées par python3 -I et $HOME ; un
mélange des deux états est refusé en nommant la garde. Depuis la tâche 14.1, l'ancien état (deux gardes, tubes puis npm, lancées par python3 sans -I
sur la variable du dossier du projet) est refusé lui aussi, en nommant la garde. La forme PostToolUse (option A) n'est plus admise : un retour à A changerait ce test en même temps que l'entrée. Tout
autre hook, toute entrée à une seule commande, avec un élément en trop ou différent, fait échouer le test. Avant la pose, le fichier
réel sans entrée PreToolUse passe sans changement.

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
HOOK_NPM = {"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR/tools/npm_guard.py"', "onFailure": "block", "timeout": 10}
EVENEMENT_GARDE = "PreToolUse"       # forme B, seule admise
OPTIONS = {"PostToolUse": "post", "PreToolUse": "pre"}

# Change session-guard-n1, tâches 8.3 et 14.1, design D12 (R-20261107-26, Q3 et P2 ; question ouverte 4) : l'entrée PreToolUse n'admet qu'UN état, tout ou rien :
# « nouveau » (l'état de D12 après P2 : trois gardes, python3 -I et $HOME littéral, la garde de session en dernier). L'état « ancien » (avant P2 : deux
# gardes, python3 sur la variable du dossier du projet) n'est plus admis depuis la tâche 14.1 ; il reste défini ici pour être refusé en nommant la garde.
ESPACE = "$HOME/PMZilla-Lab/workspace"
HOOK_TUBES_NOUVEAU = {"type": "command", "command": f'python3 -I "{ESPACE}/tools/pipe_guard.py" --event pre'}
HOOK_NPM_NOUVEAU = {"type": "command", "command": f'python3 -I "{ESPACE}/tools/npm_guard.py"', "onFailure": "block", "timeout": 10}
HOOK_SESSION_NOUVEAU = {"type": "command", "command": f'python3 -I "{ESPACE}/tools/garde_session.py"', "onFailure": "block", "timeout": 10}
ETATS = ("ancien", "nouveau")
SCRIPTS = (("pipe_guard.py", "garde des tubes"), ("npm_guard.py", "garde npm"), ("garde_session.py", "garde de session"))


def gardes_de_l_etat(etat: str = "ancien", evenement: str = EVENEMENT_GARDE) -> list:
    """Les commandes de l'entrée dans l'ordre : l'ancien état n'a que deux gardes, le nouveau en a trois."""
    if etat == "nouveau":
        return [dict(HOOK_TUBES_NOUVEAU), dict(HOOK_NPM_NOUVEAU), dict(HOOK_SESSION_NOUVEAU)]
    return [{"type": "command", "command": f'python3 "$CLAUDE_PROJECT_DIR/tools/pipe_guard.py" --event {OPTIONS[evenement]}'}, dict(HOOK_NPM)]


def entree_garde(evenement: str = EVENEMENT_GARDE, etat: str = "ancien") -> list:
    """L'entrée de la garde des tubes sous l'événement donné ; la forme PostToolUse ne sert qu'à vérifier qu'elle est refusée."""
    return [{"matcher": "Bash", "hooks": gardes_de_l_etat(etat, evenement)}]


def etat_de_la_garde(commandes: list, script: str) -> str:
    """« ancien », « nouveau », « autre » ou « absente » pour la garde de ce script, d'après la commande qui la nomme."""
    trouvees = [h for h in commandes if isinstance(h, dict) and script in str(h.get("command", ""))]
    if not trouvees:
        return "absente"
    for etat in ETATS:
        if any(h in gardes_de_l_etat(etat) for h in trouvees):
            return etat
    return "autre"


def gardes_fautives(entree: list) -> list:
    """Pour une entrée qui porte au moins une garde de l'état nouveau sans être l'état nouveau exact : les gardes en faute, nommées. L'état de
    référence est celui de la garde des tubes (la seule présente dans les deux états) ; toute autre garde qui n'est pas dans cet état est nommée, avec
    son état ; un ordre différent est nommé aussi."""
    commandes = entree[0].get("hooks", []) if entree and isinstance(entree[0], dict) else []
    reference = etat_de_la_garde(commandes, SCRIPTS[0][0])
    fautes = []
    for script, nom in SCRIPTS:
        etat = etat_de_la_garde(commandes, script)
        attendu = reference if reference in ETATS else "nouveau"
        if etat == "absente" and attendu == "ancien" and script == "garde_session.py":
            continue        # l'ancien état n'a pas de garde de session
        if etat != attendu:
            fautes.append(f"{nom} ({'dans l’ancien état' if etat == 'ancien' else 'dans l’état nouveau' if etat == 'nouveau' else etat})")
    if reference == "ancien" and etat_de_la_garde(commandes, SCRIPTS[1][0]) == "nouveau" and etat_de_la_garde(commandes, SCRIPTS[2][0]) == "nouveau":
        fautes.insert(0, "garde des tubes (dans l’ancien état)")   # la garde de référence est elle-même en faute quand les deux autres sont à jour
    if len(entree) != 1:
        fautes.append("plusieurs entrées PreToolUse")
    if entree and isinstance(entree[0], dict) and entree[0].get("matcher") != "Bash":
        fautes.append("matcher différent de Bash")
    if not fautes and entree[0].get("hooks") != gardes_de_l_etat(reference if reference in ETATS else "nouveau"):
        fautes.append("ordre ou contenu des gardes")
    return fautes


def constat_entree(entree: list) -> str:
    """Le constat d'une entrée PreToolUse qui n'est pas l'état exact de D12 : l'ancien état exact est refusé en nommant ses gardes (tâche 14.1) ;
    mélange nommé si une garde de l'état nouveau y figure, sinon le constat historique."""
    if entree == entree_garde(etat="ancien"):
        return ("entrée des gardes dans l’ancien état, non admis depuis la tâche 14.1 (D12), garde en faute : "
                "garde des tubes (dans l’ancien état), garde npm (dans l’ancien état)")
    commandes = entree[0].get("hooks", []) if entree and isinstance(entree[0], dict) else []
    if any(etat_de_la_garde(commandes, s) == "nouveau" for s, _ in SCRIPTS):
        return "entrée des gardes en forme mélangée (D12), garde en faute : " + ", ".join(gardes_fautives(entree))
    return "entrée de la garde des tubes inattendue sous " + EVENEMENT_GARDE


def constats_hooks(hooks: dict) -> list:
    """Écarts de la section hooks : vide quand elle porte les deux hooks de début de session et, au plus, l'entrée PreToolUse de la
    garde des tubes, dans l'état de D12 après P2 seulement (tout ou rien ; l'ancien état est refusé depuis la tâche 14.1)."""
    trouves = []
    if hooks.get("SessionStart") != DEBUT_DE_SESSION:
        trouves.append("hooks de début de session différents des deux attendus")
    for evenement in sorted(set(hooks) - {"SessionStart"}):
        if evenement == "PostToolUse" and hooks[evenement] == entree_garde("PostToolUse"):
            trouves.append("garde des tubes sous PostToolUse : forme A non admise (D9, forme B choisie)")
        elif evenement != EVENEMENT_GARDE:
            trouves.append(f"hook inattendu : {evenement}")
        elif hooks[evenement] != entree_garde(etat="nouveau"):
            trouves.append(constat_entree(hooks[evenement]))
    return trouves


class HookGardeDesTubes(unittest.TestCase):
    def avec(self, **ajouts):
        hooks = {"SessionStart": copy.deepcopy(DEBUT_DE_SESSION)}
        hooks.update(ajouts)
        return hooks

    def test_sans_entree_de_garde_passe(self):
        self.assertEqual(constats_hooks(self.avec()), [])

    def test_entree_pre_posee_passe(self):
        """Tâche 14.1. Ancien attendu : l'entrée de l'ancien état (entree_garde()) passe, constats []. Nouvel attendu : seule l'entrée de l'état de D12
        passe, constats []."""
        self.assertEqual(constats_hooks(self.avec(PreToolUse=entree_garde(etat="nouveau"))), [])

    def test_l_ancien_etat_est_refuse_en_nommant_la_garde(self):
        """Tâche 14.1 : l'entrée de l'ancien état (deux gardes, python3 sans -I) n'est plus admise ; le constat nomme les gardes en faute."""
        constats = constats_hooks(self.avec(PreToolUse=entree_garde()))
        self.assertEqual(len(constats), 1, constats)
        self.assertIn("ancien état", constats[0])
        self.assertIn("garde des tubes", constats[0])
        self.assertIn("garde npm", constats[0])

    def test_forme_a_post_n_est_pas_reconnue(self):
        """Forme B choisie le 2026-10-19 : l'entrée PostToolUse exacte de l'ancienne recommandation échoue, seule ou avec la forme B."""
        self.assertEqual(constats_hooks(self.avec(PostToolUse=entree_garde("PostToolUse"))),
                         ["garde des tubes sous PostToolUse : forme A non admise (D9, forme B choisie)"])
        self.assertEqual(constats_hooks(self.avec(PostToolUse=entree_garde("PostToolUse"), PreToolUse=entree_garde(etat="nouveau"))),
                         ["garde des tubes sous PostToolUse : forme A non admise (D9, forme B choisie)"])

    def test_forme_a_post_avec_l_ancien_etat_donne_deux_constats(self):
        """Tâche 14.1 : la forme A, puis l'ancien état (refusé), dans cet ordre."""
        constats = constats_hooks(self.avec(PostToolUse=entree_garde("PostToolUse"), PreToolUse=entree_garde()))
        self.assertEqual(len(constats), 2, constats)
        self.assertEqual(constats[0], "garde des tubes sous PostToolUse : forme A non admise (D9, forme B choisie)")
        self.assertIn("ancien état", constats[1])

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
        commande_en_trop = entree_garde()
        commande_en_trop[0]["hooks"].append(HOOK_RAPPEL)
        sans_npm = entree_garde()
        del sans_npm[0]["hooks"][1]
        sans_pipe = entree_garde()
        del sans_pipe[0]["hooks"][0]
        ordre_inverse = entree_garde()
        ordre_inverse[0]["hooks"].reverse()
        sans_on_failure = entree_garde()
        del sans_on_failure[0]["hooks"][1]["onFailure"]
        on_failure_autre = entree_garde()
        on_failure_autre[0]["hooks"][1]["onFailure"] = "continue"
        autre_timeout = entree_garde()
        autre_timeout[0]["hooks"][1]["timeout"] = 30
        sans_timeout = entree_garde()
        del sans_timeout[0]["hooks"][1]["timeout"]
        autre_commande_npm = entree_garde()
        autre_commande_npm[0]["hooks"][1]["command"] = 'python3 "$CLAUDE_PROJECT_DIR/tools/pipe_guard.py"'
        for entree in (mauvais_matcher, mauvaise_option, commande_en_trop, sans_npm, sans_pipe, ordre_inverse, sans_on_failure,
                       on_failure_autre, autre_timeout, sans_timeout, autre_commande_npm):
            with self.subTest(entree=entree):
                self.assertEqual(constats_hooks(self.avec(PreToolUse=entree)),
                                 ["entrée de la garde des tubes inattendue sous PreToolUse"])

    def test_mutations_de_l_etat_de_d12_sont_refusees_en_nommant_la_garde(self):
        """Tâche 14.1 : les mutations du test d'entrée, faites sur l'état de D12 (ajouté, sans retirer celles de l'ancien état)."""
        nouveau = gardes_de_l_etat("nouveau")
        sans_on_failure = {k: v for k, v in nouveau[1].items() if k != "onFailure"}
        sans_timeout = {k: v for k, v in nouveau[1].items() if k != "timeout"}
        cas = {
            "npm sans onFailure": ([nouveau[0], sans_on_failure, nouveau[2]], "garde npm (autre)"),
            "npm avec onFailure continue": ([nouveau[0], {**nouveau[1], "onFailure": "continue"}, nouveau[2]], "garde npm (autre)"),
            "npm sans timeout": ([nouveau[0], sans_timeout, nouveau[2]], "garde npm (autre)"),
            "npm absente": ([nouveau[0], nouveau[2]], "garde npm (absente)"),
            "tubes absente": ([nouveau[1], nouveau[2]], "garde des tubes (absente)"),
            "session avec un autre timeout": ([nouveau[0], nouveau[1], {**nouveau[2], "timeout": 30}], "garde de session (autre)"),
            "session avec un autre onFailure": ([nouveau[0], nouveau[1], {**nouveau[2], "onFailure": "continue"}], "garde de session (autre)"),
        }
        for nom, (gardes, mot) in cas.items():
            with self.subTest(mutation=nom):
                constats = constats_hooks(self.avec(PreToolUse=[{"matcher": "Bash", "hooks": gardes}]))
                self.assertEqual(len(constats), 1, constats)
                self.assertIn("forme mélangée (D12)", constats[0])
                self.assertIn(mot, constats[0])

    def test_l_absence_de_npm_guard_est_refusee(self):
        sans_npm = entree_garde()
        del sans_npm[0]["hooks"][1]
        self.assertEqual(constats_hooks(self.avec(PreToolUse=sans_npm)), ["entrée de la garde des tubes inattendue sous PreToolUse"])

    def test_l_absence_d_on_failure_est_refusee(self):
        entree = entree_garde()
        del entree[0]["hooks"][1]["onFailure"]
        self.assertEqual(constats_hooks(self.avec(PreToolUse=entree)), ["entrée de la garde des tubes inattendue sous PreToolUse"])

    def test_un_timeout_different_est_refuse(self):
        entree = entree_garde()
        entree[0]["hooks"][1]["timeout"] = 5
        self.assertEqual(constats_hooks(self.avec(PreToolUse=entree)), ["entrée de la garde des tubes inattendue sous PreToolUse"])

    def test_hook_de_debut_de_session_retire_echoue(self):
        hooks = {"SessionStart": [{"hooks": [HOOK_REVUES]}]}
        self.assertEqual(constats_hooks(hooks), ["hooks de début de session différents des deux attendus"])

    def test_le_fichier_reel_passe(self):
        self.assertEqual(constats_hooks(REGLAGES["hooks"]), [])

    def test_les_hooks_admis_par_le_test_strict_sont_ceux_de_d9_et_de_d12(self):
        """Le test strict de test_settings_autres_regles.py admet exactement : sans entrée, et l'état de D12 après P2 (tâche 8.3 de session-guard-n1,
        R-20261107-26, Q3 et P2) ; l'ancien état (forme PreToolUse de l'auteur du 2026-10-19, Q4 option B) n'y est plus admis depuis la tâche 14.1 ;
        la forme PostToolUse n'y est pas admise. Ancien attendu : trois états (sans entrée, ancien, nouveau). Nouvel attendu : deux (sans entrée, nouveau)."""
        import test_settings_autres_regles as strict
        attendus = [self.avec(), self.avec(PreToolUse=entree_garde(etat="nouveau"))]
        self.assertNotIn(self.avec(PreToolUse=entree_garde()), list(strict.HOOKS_ADMIS))
        self.assertNotIn(self.avec(PostToolUse=entree_garde("PostToolUse")), list(strict.HOOKS_ADMIS))
        self.assertEqual(list(strict.HOOKS_ADMIS), attendus)
        for hooks in strict.HOOKS_ADMIS:
            self.assertEqual(constats_hooks(hooks), [])

    def test_seul_l_etat_de_d12_passe_l_ancien_etat_est_refuse(self):
        """Tâche 14.1 (suite de la 8.3). Ancien attendu : l'ancien état et l'état de D12 passent, constats [] chacun. Nouvel attendu : l'état de D12
        passe ; l'ancien état donne un constat qui nomme la garde des tubes et la garde npm."""
        self.assertEqual(constats_hooks(self.avec(PreToolUse=entree_garde(etat="nouveau"))), [])
        constats = constats_hooks(self.avec(PreToolUse=entree_garde(etat="ancien")))
        self.assertEqual(len(constats), 1, constats)
        self.assertIn("garde des tubes (dans l’ancien état)", constats[0])
        self.assertIn("garde npm (dans l’ancien état)", constats[0])

    def test_l_etat_de_d12_est_celui_du_fichier_d_etape_de_p2(self):
        """Forme exacte après P2, caractère pour caractère : matcher Bash, trois gardes dans cet ordre, `$HOME` littéral, `python3 -I`, `onFailure`
        block et délai 10 pour les gardes npm et de session (fichier d'étape session-guard-n1-p2.zsh, design D2 et D12)."""
        self.assertEqual(entree_garde(etat="nouveau"), [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": 'python3 -I "$HOME/PMZilla-Lab/workspace/tools/pipe_guard.py" --event pre'},
            {"type": "command", "command": 'python3 -I "$HOME/PMZilla-Lab/workspace/tools/npm_guard.py"', "onFailure": "block", "timeout": 10},
            {"type": "command", "command": 'python3 -I "$HOME/PMZilla-Lab/workspace/tools/garde_session.py"', "onFailure": "block", "timeout": 10}]}])

    def test_une_forme_melangee_est_refusee_en_nommant_la_garde(self):
        """Tâche 8.3, tout ou rien : une garde dans chaque état, une garde manquante ou un ordre différent est refusé, et le constat nomme la garde."""
        ancien, nouveau = gardes_de_l_etat("ancien"), gardes_de_l_etat("nouveau")
        cas = {
            "tubes nouvelle, npm ancienne, session absente": ([nouveau[0], ancien[1]], ["garde npm", "garde de session (absente)"]),
            "tubes ancienne, npm nouvelle": ([ancien[0], nouveau[1]], ["garde npm (dans l’état nouveau)"]),
            "tubes et npm anciennes, session nouvelle": ([ancien[0], ancien[1], nouveau[2]], ["garde de session (dans l’état nouveau)"]),
            "tubes et npm nouvelles, session absente": ([nouveau[0], nouveau[1]], ["garde de session (absente)"]),
            "tubes ancienne, npm et session nouvelles": ([ancien[0], nouveau[1], nouveau[2]],
                                                         ["garde des tubes (dans l’ancien état)", "garde npm", "garde de session"]),
            "tubes nouvelle, npm nouvelle, session ancienne forme": (
                [nouveau[0], nouveau[1], {"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR/tools/garde_session.py"',
                                          "onFailure": "block", "timeout": 10}], ["garde de session (autre)"]),
            "session sans onFailure": ([nouveau[0], nouveau[1], {"type": "command", "command": nouveau[2]["command"], "timeout": 10}],
                                       ["garde de session (autre)"]),
            "npm avec un autre délai": ([nouveau[0], {**nouveau[1], "timeout": 30}, nouveau[2]], ["garde npm (autre)"]),
            "tubes avec la variable du dossier du projet": ([{**nouveau[0], "command": ancien[0]["command"]}, nouveau[1], nouveau[2]],
                                                            ["garde npm (dans l’état nouveau)", "garde de session (dans l’état nouveau)"]),
            "tubes avec une autre option": ([{**nouveau[0], "command": nouveau[0]["command"].replace("--event pre", "--event post")},
                                             nouveau[1], nouveau[2]], ["garde des tubes (autre)"]),
        }
        for nom, (gardes, mots) in cas.items():
            with self.subTest(forme=nom):
                constats = constats_hooks(self.avec(PreToolUse=[{"matcher": "Bash", "hooks": gardes}]))
                self.assertEqual(len(constats), 1, constats)
                self.assertIn("forme mélangée", constats[0])
                for mot in mots:
                    self.assertIn(mot, constats[0])

    def test_un_ordre_different_des_trois_gardes_est_refuse(self):
        nouveau = gardes_de_l_etat("nouveau")
        constats = constats_hooks(self.avec(PreToolUse=[{"matcher": "Bash", "hooks": [nouveau[1], nouveau[0], nouveau[2]]}]))
        self.assertEqual(len(constats), 1, constats)
        self.assertIn("forme mélangée", constats[0])
        self.assertIn("ordre ou contenu des gardes", constats[0])

    def test_une_quatrieme_commande_apres_l_etat_nouveau_est_refusee(self):
        entree = entree_garde(etat="nouveau")
        entree[0]["hooks"].append(HOOK_RAPPEL)
        constats = constats_hooks(self.avec(PreToolUse=entree))
        self.assertEqual(len(constats), 1, constats)
        self.assertIn("ordre ou contenu des gardes", constats[0])

    def test_le_nouvel_etat_avec_un_autre_matcher_est_refuse(self):
        entree = entree_garde(etat="nouveau")
        entree[0]["matcher"] = "Edit"
        constats = constats_hooks(self.avec(PreToolUse=entree))
        self.assertEqual(len(constats), 1, constats)
        self.assertIn("forme mélangée", constats[0])
        self.assertIn("matcher différent de Bash", constats[0])

    def test_deux_entrees_pretooluse_dont_l_etat_nouveau_exact_sont_refusees(self):
        supplementaire = {"matcher": "Edit", "hooks": [dict(HOOK_RAPPEL)]}
        constats = constats_hooks(self.avec(PreToolUse=entree_garde(etat="nouveau") + [supplementaire]))
        self.assertEqual(len(constats), 1, constats)
        self.assertIn("forme mélangée", constats[0])
        self.assertIn("plusieurs entrées PreToolUse", constats[0])

    def test_le_texte_de_l_entree_posee_est_celui_du_design(self):
        """Texte de l'ancien état (avant P2), gardé pour que le refus de la tâche 14.1 porte sur la forme exacte."""
        self.assertEqual(entree_garde()[0]["hooks"][0]["command"],
                         'python3 "$CLAUDE_PROJECT_DIR/tools/pipe_guard.py" --event pre')
        self.assertEqual(entree_garde()[0]["hooks"][1],
                         {"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR/tools/npm_guard.py"', "onFailure": "block", "timeout": 10})
        self.assertEqual(len(entree_garde()[0]["hooks"]), 2)


if __name__ == "__main__":
    unittest.main()
