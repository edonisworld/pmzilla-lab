"""Règles du runner complet et du jeu d'essai des postures pour la session (dossier de décision 2026-10-26-droits-session-push-runner,
décisions 4 à 7, second regard M1, M3, M4, M5, M6, m2, m3, m5 ; fiche d'étape de l'auteur session-runner-reglages ; spec tooling-permission-guards).

Une fois les règles posées, la session peut lancer le runner complet `bash tests/run_all.sh` (règle allow exacte, sans argument, dans
.claude/settings.base.json) : ses gardes de session sont dans le lanceur lui-même (tests/run_all.sh : code 6 tant que la veille ou la sauvegarde tournent (R-20261102-3, R-20261102-5), quand un
autre lancement complet de session tourne, ou quand une variable de contournement est posée). Elle ne peut pas (fragment 37, session-runner) :
 - lancer le jeu d'essai des postures (payant) : `tools/posture_evals.py` sous chaque lanceur, chaque enveloppe (nohup, env, command, time, exec),
   chaque forme de chemin et `python -m posture_evals` ; `tools/evals_auto.sh` sous chaque interpréteur et chaque enveloppe ; `claude -p` et
   `claude --print` (nus, avec options, sous enveloppe, sous `bash -c`) ; `PMZILLA_AFTER_COMMIT=…` devant un commit ;
 - vider l'environnement pour faire disparaître le marqueur de session (`env -i`, `env -`, `env --ignore-environment`, `exec -c`) ;
 - nommer le marqueur de session lui-même (règle `Bash(*<marqueur>*)` : `env -u`, `X=`, `unset`, `export`), que lisent le runner, le jeu d'essai
   (posture_evals.py, evals_auto.sh, post-commit), version_photo.py, db_rehearsal.sh et le crochet pre-commit.
Les refus sont doublés dans les outils eux-mêmes (code 6 en session : posture_evals.py, evals_auto.sh, crochet post-commit, run_all.sh).

EFFETS (M6) : chaque règle qui commence par `*` (le marqueur, `PMZILLA_AFTER_COMMIT=`, le vidage de l'environnement) refuse aussi des commandes
qui ne font que nommer le texte : un message de commit, un corps d'issue, une recherche. Consigne de l'auteur, mot pour mot : voir EFFETS
ci-dessous. Autres effets assumés : `git log -- tools/posture_evals.py` reste permis (les règles de lancement commencent par le lanceur, l'enveloppe
ou le chemin), mais une enveloppe (`time`, `env`…) devant un affichage de `posture_evals.py` ou `evals_auto.sh` est refusée ; `claude mcp add … -p`
et tout `claude … -p` sont refusés ; `env -i` et `exec -c` sont refusés partout, y compris dans une recherche ou un message. Écart assumé avec
la convention « pas de joker nu » du fragment 26 (M5) : trois familles de règles du fragment 37 commencent par `*` (test dédié ci-dessous).

Conception (même motif que test_settings_deny_photo_version.py) : ce module est écrit AVANT la pose par la fiche d'étape de l'auteur :
 - la matrice s'applique aux blocs déclarés, toujours : verte avant comme après ;
 - les tests du fichier réel sont SAUTÉS tant que rien n'est posé, ÉCHOUENT si la pose est partielle (ils nomment ce qui manque) et rejouent la
   matrice contre les règles réelles quand tout est posé (fragment 37 et règle allow) ;
 - les commandes permises sont aussi vérifiées contre les règles réelles privées de celles du bloc : le résultat est le même avant et après la pose.
Aucune commande n'est lancée ; le test lit .claude/settings.json et .claude/deny/ORDRE.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q
    python3 tests/settings_deny/test_settings_deny_session_runner.py --json           (règles deny à poser dans le fragment 37)
    python3 tests/settings_deny/test_settings_deny_session_runner.py --lignes 37      (le fragment 37, une règle par ligne)
    python3 tests/settings_deny/test_settings_deny_session_runner.py --lignes allow   (la règle allow à poser dans .claude/settings.base.json)
"""
import itertools
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import garde_regles  # noqa: E402
from test_settings_deny import motif_en_regex  # noqa: E402

REGLAGES = RACINE / ".claude" / "settings.json"
ORDRE = RACINE / ".claude" / "deny" / "ORDRE"
NOM_37 = "37-session-runner.txt"
MARQUEUR = "CLAUDECODE"

# Consigne de l'auteur du 2026-10-26 (M6), mot pour mot : elle accompagne la règle du marqueur dans EFFETS.
CONSIGNE_MARQUEUR = (
    "un message de commit qui doit citer la variable passe par git commit -F <fichier du dossier de travail> ; un corps d'issue par "
    "tools/gh_issue.py avec --body-file ; une recherche par l'outil Grep. De préférence, écrire « le marqueur de session » plutôt que le nom "
    "de la variable."
)
EFFETS = (
    f"Bash(*{MARQUEUR}*) : refuse toute commande qui contient le nom du marqueur de session, donc aussi un message de commit, un corps d'issue ou une "
    f"recherche qui le cite. Consigne de l'auteur : {CONSIGNE_MARQUEUR}",
    "Bash(*PMZILLA_AFTER_COMMIT=*) : refuse aussi un message de commit ou un corps d'issue qui écrit la variable suivie de « = » ; sans le « = » "
    "(une recherche du nom, `git grep`), la commande reste permise.",
    "Bash(*env -i*), Bash(*env --ignore-environment*), Bash(*env - *), Bash(*exec -c *) : refusent aussi une recherche ou un message qui cite ces formes.",
    "Enveloppes (nohup, env, command, time, exec) devant posture_evals.py, evals_auto.sh ou claude -p : refusées aussi pour un simple affichage "
    "(`time cat tools/posture_evals.py`) : lire le fichier par l'outil Read.",
    "`claude … -p` et `claude … --print` : refusés quelle que soit la sous-commande de claude.",
)

# --- Règle allow (base des réglages) ----------------------------------------------------------------------------------------------------

REGLE_ALLOW = "Bash(bash tests/run_all.sh)"   # forme exacte, sans argument : les formes avec argument restent soumises à la question

# --- Fragment 37 : jeu d'essai et vidage de l'environnement ----------------------------------------------------------------------------

LANCEURS_REGLES = ("uv run", "python", "python3")
PREFIXES_TOOLS = ("tools/", "./tools/", "~/*tools/", "$HOME/*tools/", "/*tools/", "", "./")
ENVELOPPES = ("nohup", "env", "command", "time", "exec")
SHELLS = ("bash", "sh", "zsh")


def regles_de_lancement(script: str, prefixes: tuple) -> list:
    """Forme ancrée de test_settings_deny_photo_version.regles_de_lancement : avec un lanceur, le script précédé d'une barre, nu ou précédé
    d'options ; en lancement direct, le chemin au début. Le joker ne précède jamais le nom sans barre ni espace."""
    regles = []
    for lanceur in LANCEURS_REGLES:
        regles += [f"Bash({lanceur} */{script}*)", f"Bash({lanceur} {script}*)", f"Bash({lanceur} * {script}*)"]
    return regles + [f"Bash({prefixe}{script}*)" for prefixe in prefixes]


# posture_evals.py : les seize formes ancrées, `../tools/…`, chaque enveloppe devant le script (avec chemin ou après un espace),
# `python -m posture_evals` sous chaque lanceur et sous chaque enveloppe
DENY_POSTURE_EVALS = tuple(
    regles_de_lancement("posture_evals.py", PREFIXES_TOOLS)
    + ["Bash(../*tools/posture_evals.py*)"]
    + [f"Bash({e} {forme}posture_evals.py*)" for e in ENVELOPPES for forme in ("*/", "* ", "")]
    + [f"Bash({lanceur}{milieu}-m posture_evals*)" for lanceur in ("python", "python3", "uv run") for milieu in (" ", " * ")]
    + [f"Bash({e} * -m posture_evals*)" for e in ENVELOPPES]
)

# evals_auto.sh : chaque interpréteur ou enveloppe (barre, nu, après options), chaque chemin direct
DENY_EVALS_AUTO = tuple(
    [f"Bash({i} {forme}evals_auto.sh*)" for i in SHELLS + ("uv run",) + ENVELOPPES for forme in ("*/", "", "* ")]
    + [f"Bash({prefixe}evals_auto.sh*)" for prefixe in PREFIXES_TOOLS + ("../*tools/",)]
)

# PMZILLA_AFTER_COMMIT devant un commit : toute affectation (nue, exportée, sous env, entre guillemets)
DENY_AFTER_COMMIT = ("Bash(*PMZILLA_AFTER_COMMIT=*)",)

# claude -p et claude --print : nus, avec options, sous enveloppe (avec ou sans affectations devant), sous bash -c / bash -lc
DENY_CLAUDE_P = tuple(
    [f"Bash({chemin}claude {option})" for chemin in ("", "*/") for option in ("-p*", "--print*", "* -p*", "* --print*")]
    + [f"Bash({e} *claude {option})" for e in ENVELOPPES for option in ("-p*", "--print*", "* -p*", "* --print*")]
    + [f"Bash({s} -*c *claude {option})" for s in SHELLS for option in ("-p*", "--print*", "* -p*", "* --print*")]   # -c, -lc, -ic…
)

# vider l'environnement ferait disparaître le marqueur de session sans le nommer
DENY_ENV_VIDE = ("Bash(*env -i*)", "Bash(*env --ignore-environment*)", "Bash(*env - *)", "Bash(*exec -c *)")

# le marqueur de session lui-même (env -u, X=, unset, export), lu par le runner, le jeu d'essai, version_photo, db_rehearsal et pre-commit
DENY_MARQUEUR = (f"Bash(*{MARQUEUR}*)",)

REGLES_37 = DENY_POSTURE_EVALS + DENY_EVALS_AUTO + DENY_AFTER_COMMIT + DENY_CLAUDE_P + DENY_ENV_VIDE + DENY_MARQUEUR

# Formes de m3 (second regard) qui doivent être refusées, écrites en toutes lettres : le bloc ne peut pas les perdre sans faire échouer le test
FORMES_M3 = (
    "nohup python3 tools/posture_evals.py", "env python3 tools/posture_evals.py --cases x", "command python3 tools/posture_evals.py",
    "time python3 tools/posture_evals.py", "env X=1 uv run tools/posture_evals.py", "python3 -m posture_evals", "python -m posture_evals --keep",
    "uv run python -m posture_evals", "nohup python3 -m posture_evals", "../tools/posture_evals.py", "python3 ../tools/posture_evals.py",
    "env X=1 claude -p x", "bash -c \"claude -p x\"", "sh -c 'claude --print x'", "bash -lc \"claude -p x\"", "nohup claude -p x",
    "time claude -p x", "command claude -p x", "evals_auto.sh", "bash tools/evals_auto.sh", "nohup tools/evals_auto.sh --readme",
    "env X=1 bash tools/evals_auto.sh", "time bash tools/evals_auto.sh", "command bash tools/evals_auto.sh", "PMZILLA_AFTER_COMMIT=evals git commit -m x",
    "PMZILLA_AFTER_COMMIT=all git commit -m x", "export PMZILLA_AFTER_COMMIT=all", "env PMZILLA_AFTER_COMMIT=evals git commit -m x",
)


def regles_attendues() -> list:
    """La liste imprimée par --json, contrôlée par la garde partagée (test_settings_deny_listes_declarees)."""
    return list(REGLES_37)


def regles_allow() -> list:
    return [REGLE_ALLOW]


LANCEURS_PAR_SCRIPT = {
    "posture_evals.py": ("uv run", "uv run --isolated", "uv run --with pyyaml", "uv run -q", "python", "python3", "python3 -I", "python3 -W ignore",
                         "nohup", "nohup python3", "env", "env X=1", "env X=1 Y=2 python3", "command", "time", "time python3", "exec", "exec python3"),
    "evals_auto.sh": ("bash", "sh", "zsh", "bash -x", "uv run", "uv run -q", "nohup", "nohup bash", "env", "env X=1", "env X=1 bash", "command",
                      "time", "time bash", "exec", "exec zsh"),
}
SCRIPTS = tuple(LANCEURS_PAR_SCRIPT)
CHEMINS = ("tools/{s}", "./tools/{s}", "../tools/{s}", "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}",
           "$HOME/PMZilla-Lab/workspace/tools/{s}", "~/PMZilla-Lab/worktrees/wt-feat-x/tools/{s}", "{s}")
CHEMINS_DIRECTS = ("tools/{s}", "./tools/{s}", "/Users/quelquun/PMZilla-Lab/workspace/tools/{s}", "~/PMZilla-Lab/workspace/tools/{s}",
                   "$HOME/PMZilla-Lab/workspace/tools/{s}", "../tools/{s}", "{s}", "./{s}")
OPTIONS = ("", " --cases c1,c2", " --branch feat/x", " --committed-state", " --readme", " --help", " -h")
CLAUDE_P = ("claude -p", "claude -p x", "claude --print x", "claude --model opus -p x", "claude --output-format json -p x", "claude mcp add x -p",
            "/Users/quelquun/.local/bin/claude -p x", "~/.local/bin/claude --print x", "env X=1 claude -p x", "env -u X claude -p x",
            "nohup claude -p x", "time claude --print x", "command claude -p x", "exec claude -p x", "bash -c \"claude -p x\"", "sh -c 'claude --print x'",
            "zsh -c \"claude --model opus -p x\"", "bash -lc \"claude -p x\"", "nohup env X=1 claude -p x", "bash -x -c \"claude -p x\"")
APRES_COMMIT = ("PMZILLA_AFTER_COMMIT=evals git commit -m x", "PMZILLA_AFTER_COMMIT=all git commit -m x", "PMZILLA_AFTER_COMMIT=all git commit --amend",
                "PMZILLA_AFTER_COMMIT=\"evals\" git commit -m x", "PMZILLA_AFTER_COMMIT='all' git commit -m x", "export PMZILLA_AFTER_COMMIT=evals",
                "env PMZILLA_AFTER_COMMIT=all git commit -m x", "PMZILLA_NO_EVALS= PMZILLA_AFTER_COMMIT=evals git commit -m x",
                "git commit -m 'x' && PMZILLA_AFTER_COMMIT=all git commit --amend --no-edit")
ENV_VIDE = ("env -i bash tests/run_all.sh", "env -i HOME=$HOME PATH=$PATH bash tests/run_all.sh", "env - bash tests/run_all.sh",
            "env --ignore-environment bash tests/run_all.sh", "exec -c bash tests/run_all.sh", "cd x && env -i bash tests/run_all.sh",
            "/usr/bin/env -i bash tests/run_all.sh")
MARQUEUR_NOMME = (f"env -u {MARQUEUR} bash tests/run_all.sh", f"{MARQUEUR}= bash tests/run_all.sh", f"{MARQUEUR}=0 bash tests/run_all.sh",
                  f"unset {MARQUEUR}", f"export {MARQUEUR}=", f"echo ${MARQUEUR}", f"git grep -n {MARQUEUR}", f"git commit -m \"cite {MARQUEUR}\"",
                  f"env {MARQUEUR}= bash tests/run_all.sh", f"cd x && unset {MARQUEUR} && bash tests/run_all.sh")

MARQUEUR_COUPE = MARQUEUR[:6] + '""' + MARQUEUR[6:]   # le nom coupé par des guillemets : jamais écrit en toutes lettres, même dans ce fichier

# Limites connues, DÉCLARÉES (revue Opus du 2026-10-26, mineur 5) : formes que les règles par motif ne voient pas, parce que le motif est ancré sur
# le début de la commande ou sur un texte exact. Elles PASSENT aujourd'hui ; ce n'est pas une garantie mais un état connu. Défense qui reste : les
# refus doublés dans les outils eux-mêmes (code 6 en session : posture_evals.py, evals_auto.sh, post-commit, run_all.sh) et la lecture des commandes
# par l'auteur. Si une règle les refuse un jour, le test échoue et c'est ce tuple qui change.
LIMITES_CONNUES = (
    # vider l'environnement par une option que le motif `env -i` ne reconnaît pas
    "env -v -i bash tests/run_all.sh", "env -vi bash tests/run_all.sh", "env -P /bin -i bash tests/run_all.sh", "env  -i bash tests/run_all.sh",
    "exec -lc bash tests/run_all.sh", "exec -a x -c bash tests/run_all.sh",
    # le nom du marqueur coupé par des guillemets : le motif `*<nom>*` ne le reconnaît pas
    f"env -u {MARQUEUR_COUPE} bash tests/run_all.sh",
    # enveloppes que la liste des enveloppes ne contient pas (nohup, env, command, time, exec)
    "nice python3 tools/posture_evals.py", "timeout 600 python3 tools/posture_evals.py", "caffeinate python3 tools/posture_evals.py",
    "xargs python3 tools/posture_evals.py", "nice claude -p x", "timeout 60 claude -p x", "caffeinate claude -p x", "printf x | xargs claude -p",
    # interpréteurs et chemins hors de la liste (python, python3, uv run)
    "python3.12 tools/posture_evals.py", ".venv/bin/python tools/posture_evals.py", ".venv/bin/python tools/evals_auto.sh",
    # options groupées de claude
    "claude -cp x",
    # une copie du lanceur posée ailleurs, avec un faux tools/morning_state.sh à côté : la règle allow ne couvre que la forme exacte (la question
    # reste posée), mais aucune règle deny ne nomme la copie
    "bash /private/tmp/x/tests/run_all.sh",
)

COMMANDES_PERMISES = (
    "bash tests/run_all.sh", "bash tests/run_all.sh --staged", "bash tests/run_all.sh settings_deny", "bash tests/run_all.sh run_all",
    "bash tests/run_all.sh posture_evals", "bash tests/run_all.sh evals_auto", "bash tests/run_all.sh --portable",
    "cat tools/posture_evals.py", "head -40 tools/posture_evals.py", "sed -n 1,60p tools/evals_auto.sh", "grep -n main tools/posture_evals.py",
    "git log --oneline -3 -- tools/posture_evals.py", "git diff -- tools/evals_auto.sh", "git log -- tools/evals_auto.sh",
    "ls tests/posture_evals", "cat tests/posture_evals/test_refus_session.py", "cat tools/hooks/post-commit", "ls tests/evals_auto",
    "python3 tests/posture_evals/test_refus_session.py", "python3 tests/posture_evals/test_branche.py",
    "uv run --with pyyaml python -W ignore -m unittest discover -s tests/posture_evals -q -f",
    "python3 -W ignore -m unittest discover -s tests/run_all -q", "sh tests/evals_auto/test_evals_auto.sh", "sh tests/hooks/test_post_commit.sh",
    "uv run tools/pilot.py freeze --check",
    "python3 tests/settings_deny/test_settings_deny_session_runner.py --json",
    "python3 -W ignore -m unittest discover -s tests/settings_deny -p test_settings_deny_session_runner.py -q",
    "git commit -m \"session-runner : garde du runner\"", "git commit -F docs/message.txt", "env PMZILLA_NO_EVALS=1 git commit -m x",
    "env PMZILLA_NO_EVALS=1 git -C ../wt commit -m x", "git grep -n PMZILLA_AFTER_COMMIT -- tools", "git grep -n posture_evals -- tests",
    "claude --version", "claude mcp list", "claude --help", "env X=1 git status", "env", "time git status", "command -v uv", "exec ls",
    "uv run tools/flow_views.py list",
)


def commandes_refusees():
    """Toutes les formes de lancement du jeu d'essai, de claude -p, du vidage d'environnement et du marqueur que la session ne doit pas exécuter."""
    for script in SCRIPTS:
        for lanceur, chemin, option in itertools.product(LANCEURS_PAR_SCRIPT[script], CHEMINS, OPTIONS):
            yield f"{lanceur} {chemin.format(s=script)}{option}"
    for script, chemin, option in itertools.product(SCRIPTS, CHEMINS_DIRECTS, OPTIONS):
        yield f"{chemin.format(s=script)}{option}"
    yield from FORMES_M3
    yield from CLAUDE_P
    yield from APRES_COMMIT
    yield from ENV_VIDE
    yield from MARQUEUR_NOMME


class Moteur:
    def __init__(self, regles):
        self.motifs = [motif_en_regex(r[len("Bash("):-1]) for r in regles if r.startswith("Bash(")]

    def interdite(self, commande: str) -> bool:
        return any(m.fullmatch(commande) for m in self.motifs)


class Matrice:
    """Cas communs au bloc REGLES_37 et aux règles réelles ; `self.moteur` est fourni par la classe qui les mélange."""

    def verifier_formes_refusees(self):
        manquantes = [c for c in commandes_refusees() if not self.moteur.interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} forme(s) non refusée(s)")

    def verifier_formes_permises(self):
        refusees = [c for c in COMMANDES_PERMISES if self.moteur.interdite(c)]
        self.assertEqual(refusees, [], "commande(s) permise(s) refusée(s) : règle trop large")


class BlocSessionRunner(Matrice, unittest.TestCase):
    """Le moteur de motifs appliqué au bloc à poser : vert avant comme après la pose."""

    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(REGLES_37)

    def test_le_bloc_est_fait_de_regles_bash_sans_doublon(self):
        self.assertEqual(len(REGLES_37), len(set(REGLES_37)))
        self.assertTrue(all(r.startswith("Bash(") and r.endswith(")") for r in REGLES_37))
        self.assertEqual(garde_regles.constats(REGLES_37), [])

    def test_seules_trois_familles_de_regles_commencent_par_un_joker(self):
        """Écart assumé par rapport à la convention « pas de joker nu » du fragment 26 : le marqueur, PMZILLA_AFTER_COMMIT et le vidage de
        l'environnement doivent être vus où qu'ils soient dans la commande."""
        jokers = sorted(r for r in REGLES_37 if r.startswith("Bash(*") and not r.startswith("Bash(*/"))
        self.assertEqual(jokers, sorted(DENY_AFTER_COMMIT + DENY_ENV_VIDE + DENY_MARQUEUR))

    def test_les_regles_du_marqueur_et_de_la_variable_du_jeu_d_essai(self):
        self.assertIn(f"Bash(*{MARQUEUR}*)", REGLES_37)
        self.assertIn("Bash(*PMZILLA_AFTER_COMMIT=*)", REGLES_37)

    def test_les_seize_formes_ancrees_de_posture_evals_sont_la(self):
        attendues = regles_de_lancement("posture_evals.py", PREFIXES_TOOLS)
        self.assertEqual(len(attendues), 16)
        self.assertEqual([r for r in attendues if r not in REGLES_37], [])

    def test_les_formes_du_second_regard_m3_sont_refusees(self):
        for commande in FORMES_M3:
            self.assertTrue(self.moteur.interdite(commande), commande)

    def test_chaque_lanceur_chemin_et_option_sont_refuses(self):
        self.verifier_formes_refusees()

    def test_lecture_suites_et_commits_restent_permis(self):
        self.verifier_formes_permises()

    def test_le_joker_ne_touche_pas_les_scripts_de_test(self):
        for commande in ("python3 tests/posture_evals/test_refus_session.py", "sh tests/evals_auto/test_evals_auto.sh",
                         "bash tests/evals_auto/test_evals_auto.sh", "uv run tests/posture_evals/aide_posture_evals.py",
                         "python3 tests/hooks/test_post_commit.py"):
            self.assertFalse(self.moteur.interdite(commande), commande)

    def test_un_message_de_commit_sans_le_marqueur_ni_les_affectations_passe(self):
        for commande in ('git commit -m "le marqueur de session est refusé au jeu d\'essai"', "git commit -F docs/message.txt",
                         'git -C ../wt commit -m "garde du runner complet en session (code 6)"'):
            self.assertFalse(self.moteur.interdite(commande), commande)

    def test_les_limites_connues_passent_et_sont_declarees(self):
        """Chaque limite déclarée passe les règles du bloc (moteur du bloc seul) : le tuple décrit l'état réel, ni plus ni moins."""
        self.assertEqual(len(LIMITES_CONNUES), len(set(LIMITES_CONNUES)))
        refusees = [c for c in LIMITES_CONNUES if self.moteur.interdite(c)]
        self.assertEqual(refusees, [], "limite(s) déclarée(s) maintenant refusée(s) : la retirer de LIMITES_CONNUES")

    def test_les_limites_connues_ne_nomment_pas_le_marqueur_en_toutes_lettres(self):
        self.assertTrue(all(MARQUEUR not in c for c in LIMITES_CONNUES))
        self.assertIn(MARQUEUR_COUPE, " ".join(LIMITES_CONNUES))

    def test_bash_x_c_claude_p_est_refuse(self):
        self.assertTrue(self.moteur.interdite('bash -x -c "claude -p x"'))

    def test_les_effets_citent_la_consigne_de_l_auteur_mot_pour_mot(self):
        consigne = ("un message de commit qui doit citer la variable passe par git commit -F <fichier du dossier de travail> ; un corps d'issue "
                    "par tools/gh_issue.py avec --body-file ; une recherche par l'outil Grep. De préférence, écrire « le marqueur de session » "
                    "plutôt que le nom de la variable.")
        self.assertEqual(CONSIGNE_MARQUEUR, consigne)
        self.assertTrue(any(consigne in effet for effet in EFFETS))


class ReglesExistantes(unittest.TestCase):
    """Les commandes permises contre les règles réelles privées de celles du bloc : même résultat avant et après la pose."""

    @classmethod
    def setUpClass(cls):
        deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.moteur = Moteur([r for r in deny if r not in REGLES_37])

    def test_commandes_permises_non_refusees_par_les_regles_d_avant(self):
        self.assertEqual([c for c in COMMANDES_PERMISES if self.moteur.interdite(c)], [])

    def test_le_jeu_d_essai_n_est_pas_deja_refuse_par_une_regle_d_avant(self):
        """Garde le sens du bloc : sans lui, le jeu d'essai et claude -p ne sont pas refusés."""
        for commande in ("python3 tools/posture_evals.py", "bash tools/evals_auto.sh", "claude -p x", "PMZILLA_AFTER_COMMIT=evals git commit -m x"):
            self.assertFalse(self.moteur.interdite(commande), commande)


class DansLeFichierDeReglages(unittest.TestCase):
    """La pose par l'auteur : sautée avant, échoue si elle est partielle, passe si tout y est."""

    @classmethod
    def setUpClass(cls):
        permissions = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]
        cls.deny = permissions["deny"]
        cls.allow = permissions.get("allow", [])
        cls.presentes = [r for r in REGLES_37 if r in cls.deny]
        cls.manquantes = [r for r in REGLES_37 if r not in cls.deny]
        cls.allow_pose = REGLE_ALLOW in cls.allow

    # Désherbage du 2026-10-28 (D79) : les branches de saut « fragment 37 pas encore posé » sont retirées. Le fragment 37 est dans settings.json et la règle
    # allow du runner y est : ces branches ne se déclenchaient plus, et elles auraient masqué une pose partielle.

    def test_les_regles_deny_sont_dans_settings_json(self):
        self.assertEqual(self.manquantes, [], f"pose partielle : {len(self.manquantes)} règle(s) de REGLES_37 absente(s) de .claude/settings.json")

    def test_la_regle_allow_du_runner_est_posee_avec_le_fragment(self):
        self.assertTrue(self.allow_pose, f"pose partielle : {REGLE_ALLOW} absente de permissions.allow")

    def test_aucune_regle_allow_ne_couvre_le_jeu_d_essai_ni_l_environnement(self):
        """Une seule règle allow touche le runner : la forme exacte. Aucune ne permet le jeu d'essai, claude -p ou le marqueur."""
        autres = [r for r in self.allow if "posture_evals" in r or "evals_auto" in r or "claude" in r or MARQUEUR in r or "PMZILLA_AFTER_COMMIT" in r]
        self.assertEqual(autres, [])

    def test_le_fragment_37_est_dans_ordre_apres_la_pose(self):
        self.assertIn(NOM_37, ORDRE.read_text(encoding="utf-8").split(), "fragment 37 absent de .claude/deny/ORDRE")
        fragment = RACINE / ".claude" / "deny" / NOM_37
        self.assertTrue(fragment.is_file(), f"{NOM_37} absent")
        lignes = [ligne for ligne in fragment.read_text(encoding="utf-8").splitlines() if ligne.strip()]
        self.assertEqual(lignes, list(REGLES_37))

    def test_la_matrice_des_formes_contre_les_regles_reelles(self):
        if self.manquantes:
            self.fail("règles manquantes : " + " ; ".join(self.manquantes[:10]))
        matrice = type("MatriceReelle", (Matrice, unittest.TestCase), {"moteur": Moteur(self.deny)})("verifier_formes_refusees")
        matrice.verifier_formes_refusees()
        matrice.verifier_formes_permises()


if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps(regles_attendues(), indent=2, ensure_ascii=False))
    elif "--lignes" in sys.argv:
        cible = sys.argv[sys.argv.index("--lignes") + 1]
        print("\n".join(regles_allow() if cible == "allow" else regles_attendues()))
    else:
        unittest.main()
