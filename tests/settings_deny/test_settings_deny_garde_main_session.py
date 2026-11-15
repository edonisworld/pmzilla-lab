"""Règles du fragment 39 : `core.hooksPath` détourné, variables `GIT_CONFIG_*` et écriture forcée de `main` par `git branch`
(décision de l'auteur du 2026-10-27, option A de R-148/u13 ; branche feat/garde-main-session ; spec tooling-git-hooks ;
fichier d'étape de l'auteur qui pose le fragment, nom proposé : 39-garde-main-session.txt).

Constat : le crochet `reference-transaction` (garde de session, u13) refuse en session tout déplacement de `main`, mais deux gestes lui échappent :
 - un `core.hooksPath` détourné (`git -c core.hooksPath=…`, variables `GIT_CONFIG_*`, `git config core.hooksPath …`) fait que Git n'appelle plus le crochet ;
 - `git branch -C <x> main` (copie de branche sur une `main` existante) fait écrire la référence par Git hors transaction : le crochet n'est pas appelé.
Une fois le fragment 39 posé, la session ne peut plus (une règle deny compare le texte de la commande, jamais le dossier ni la branche) :
 - lancer une commande qui contient `hooksPath` (casses `hooksPath`, `hookspath`, `HooksPath`, `HOOKSPATH`, `Hookspath`) ou `GIT_CONFIG_` : refus où que le texte
   figure (règles `Bash(*hooksPath*)`, …, `Bash(*GIT_CONFIG_*)`), message de commit, recherche ou `git config` compris ;
 - écrire `main` de force avec `git branch` : `-M`, `-C`, `-fM`, `-fC`, `-fm`, `-mf`, `-fc`, `-cf`, et `-m`/`-c` (formes longues `--move`/`--copy` comprises) avec `-f`
   (`--force` compris) dans les six ordres possibles autour de `main`, `main` en destination quelle que soit la place des options (avant ou après les noms, comme seul nom
   ou après la source), sous les formes nue, `git -* branch` (`-C <dossier>`, `-c k=v`, `--no-pager`, `--git-dir`), chemin absolu de git, `env`, `cd … &&`, `&&`, `||`, `&`, `|`, `;`
   (modèle du fragment 26 et du générateur du fragment 38). Les formes longues avec `--force` sont déjà refusées par la règle `git *--force*` du fragment 26 : elles sont
   redites ici pour que le fragment 39 se suffise.

VOIE PERMISE : intégrer main : git -C <worktree> rebase main. Restent permis : `git branch -c x y`, `-d x`, `-D x`, `--list`, `-m x y`, `-f x main` (autre branche déplacée de force, vue par le
fragment 38 seulement avec `main` en cible ; permis pour un nom sans segment `-f`, `-m` ou `-c` : `-f fix-merge-x main` et `fix-flaky-ci main` sont refusés, voir EFFETS), `-m x main` et `-c x main` sans force (Git les refuse si `main` existe), `-M x feat/main`, `-M x domain`. Les motifs exigent un mot
qui COMMENCE par `main` (précédé d'un espace) : `git branch -M x mainline` et `git branch -M x main-copie` sont donc REFUSÉS (ils ne passent pas ; choix fait pour refuser aussi
`main;`, `main"` et `main)`), tandis que `feat/main` et `domain` passent.

EFFETS : voir ci-dessous. Écart assumé avec la convention « pas de joker nu » du fragment 26 (comme les fragments 27 et 38) : les règles `hooksPath` et `GIT_CONFIG_`
commencent par `*`, et celles de chaînage (`*& git branch …`, `*| git …`, `*; git …`, `*;git …`, `*&git …`, `*|git …`) aussi (test dédié ci-dessous). Limites déclarées
(LIMITES_CONNUES, chacune prouvée passante) : `git pack-refs --all` (aucune règle : refusé en session par reference-transaction), les casses de `hooksPath` autres que les
cinq refusées, un mot coupé ou cité (`hooks''Path`), `GIT_CONFIG` sans souligné, `main` écrit autrement que le mot isolé (`refs/heads/main`, `'main'`, `"main"`), une grappe d'options
absente de la liste (`-vM`, `-qM`), le retour à la ligne, `$(…)`, les accents graves, la tabulation, un espace double entre git et le verbe, une enveloppe hors liste, `FOO=1 git …`, `sh -c`.

Conception (même motif que test_settings_deny_fusion_run.py) : ce module est écrit AVANT la pose par le fichier d'étape de l'auteur :
 - la matrice s'applique au bloc déclaré, toujours : verte avant comme après ;
 - les tests du fichier réel sont SAUTÉS tant que rien n'est posé, ÉCHOUENT si la pose est partielle (ils nomment ce qui manque) et rejouent la matrice contre les règles
   réelles quand tout est posé ;
 - les commandes permises sont aussi vérifiées contre les règles réelles privées de celles du bloc : le résultat est le même avant et après la pose.
Module séparé du module du fragment 38 (déjà long) : un fragment, un module, une source unique pour le fichier d'étape. Aucune commande n'est lancée ; le test lit
.claude/settings.json, .claude/deny/ORDRE et les fragments existants.

    uv run --with pyyaml python -W ignore -m unittest discover -s tests/settings_deny -q
    python3 tests/settings_deny/test_settings_deny_garde_main_session.py --json           (règles deny du fragment 39)
    python3 tests/settings_deny/test_settings_deny_garde_main_session.py --lignes 39      (le fragment 39, une règle par ligne)
"""
import itertools
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import garde_regles  # noqa: E402
from test_settings_deny_fusion_run import (  # noqa: E402
    CHAINAGES, ESPACE, FORMES_ESPACE, FORMES_GIT, LANCEURS_GIT, WORKTREE, WORKTREE_ABS, Moteur,
)

REGLAGES = RACINE / ".claude" / "settings.json"
DENY = RACINE / ".claude" / "deny"
ORDRE = DENY / "ORDRE"
NOM_39 = "39-garde-main-session.txt"
FRAGMENT_39 = DENY / NOM_39


def pose_declaree() -> bool:
    """Vrai dès que le fragment 39 ou son nom dans ORDRE est là (fichiers suivis, commités avec la pose) : les tests du fichier réel ne sont alors plus sautés."""
    return FRAGMENT_39.is_file() or NOM_39 in ORDRE.read_text(encoding="utf-8").split()


VOIE_PERMISE = "intégrer main : git -C <worktree> rebase main"

# --- core.hooksPath détourné et variables GIT_CONFIG_* ----------------------------------------------------------------------------------
# Une règle par casse raisonnable (le motif est sensible à la casse) ; toute autre casse est une limite déclarée.
CASSES_HOOKSPATH = ("hooksPath", "hookspath", "HooksPath", "HOOKSPATH", "Hookspath")
DENY_HOOKS = tuple(f"Bash(*{casse}*)" for casse in CASSES_HOOKSPATH) + ("Bash(*GIT_CONFIG_*)",)

# --- Écriture forcée de main par git branch ----------------------------------------------------------------------------------------------
# Options seules qui écrivent de force : -M et -C ; -fM, -fC (grappe qui commence par f) ; -fm, -mf, -fc, -cf (rename ou copie groupés avec force).
# `-Mf` et `-Cf` contiennent déjà `-M` et `-C` : pas de règle propre. Le motif est une sous-chaîne, donc `--move` contient `-m` et `--force` contient `-f`.
OPTIONS_SEULES = ("-M", "-C", "-fM", "-fC", "-fm", "-mf", "-fc", "-cf")
RENOMMER_COPIER = ("-m", "-c")
FORCER = "-f"

LANCEURS = LANCEURS_GIT + CHAINAGES


def corps_et_exemples() -> list:
    """Couples (corps de règle après `branch `, texte d'une commande que ce corps est seul à refuser sous le lanceur nu `git`) : source unique des corps.

    `*` ouvre chaque corps (options ou noms avant) ; ` main` exige un mot qui COMMENCE par `main` (espace avant) et la fin du corps est `main*` quand `main` est le
    dernier nom : `main;`, `main"` et `main)` sont donc refusés, mais aussi `mainline` et `main-copie` (effet déclaré) ; `feat/main` et `domain` passent ; `*main *`
    en tête de corps couvre `git branch main -M` et `git branch x main -M`. Six ordres pour (renommer ou copier, forcer, main) : six corps par option de renommage
    ou de copie ; deux corps par option d'écriture forcée seule."""
    couples = []
    for o in OPTIONS_SEULES:
        couples += [(f"*{o}* main*", f"{o} x main"), (f"*main *{o}*", f"x main {o}")]
    for n in RENOMMER_COPIER:
        f = FORCER
        couples += [
            (f"*{n}*{f}* main*", f"{n} {f} x main"), (f"*{f}*{n}* main*", f"{f} {n} x main"),
            (f"*{n}* main *{f}*", f"{n} x main {f}"), (f"*{f}* main *{n}*", f"{f} x main {n}"),
            (f"*main *{n}*{f}*", f"x main {n} {f}"), (f"*main *{f}*{n}*", f"x main {f} {n}"),
        ]
    return couples


CORPS_BRANCH = tuple(corps for corps, _ in corps_et_exemples())


def regles_branch() -> list:
    """Vingt-huit corps sous vingt préfixes (dix lanceurs : nu, chemin absolu de git, env, chemin absolu de env, six chaînages ; chacun nu puis `-*` : `-C <dossier>`,
    `-c k=v`, `--no-pager`, `--git-dir=…`) : 560 règles."""
    regles = []
    for lanceur in LANCEURS:
        for corps in CORPS_BRANCH:
            regles += [f"Bash({lanceur} branch {corps})", f"Bash({lanceur} -* branch {corps})"]
    return regles


DENY_BRANCH = tuple(regles_branch())
REGLES_39 = DENY_HOOKS + DENY_BRANCH


def regles_attendues() -> list:
    """La liste imprimée par --json, contrôlée par la garde partagée (test_settings_deny_listes_declarees)."""
    return list(REGLES_39)


# --- Formes de commande ---------------------------------------------------------------------------------------------------------------

# `{}` reçoit la suite de la commande git (après `git`).
SUITES_BRANCH_REFUSEES = (
    "branch -M x main", "branch -M main", "branch -M x main --", "branch -M main x", "branch -M -- x main", "branch -C x main", "branch -C main", "branch -C x main -f",
    "branch -fM x main", "branch -Mf x main", "branch -fC x main", "branch -Cf x main", "branch -fm x main", "branch -mf x main", "branch -fc x main", "branch -cf x main",
    "branch -m -f x main", "branch -f -m x main", "branch -c -f x main", "branch -f -c x main", "branch -m -f main",
    "branch --move --force x main", "branch --force --move x main", "branch --copy --force x main", "branch --force --copy x main", "branch --move --force main",
    "branch -m x -f main", "branch -c x -f main",
    "branch -m x main -f", "branch -f x main -m", "branch main -m -f", "branch main -f -m", "branch -c x main --force", "branch main --force --copy",
    "branch x main -M", "branch main -M", "branch x main -C", "branch main -C",
)
SUITES_NOYAU = ("branch -M x main", "branch -M main", "branch -C x main", "branch -m -f x main", "branch --copy --force x main", "branch x main -M")
FORMES_AUTRES = FORMES_ESPACE + ("git status |git {}", "git status&git {}", "git status &git {}", "git -c x=y {}", "git --no-pager {}",
                                 "git -c x=y -C " + WORKTREE + " {}", "git status || git -C . {}", "git status | git {}")
BRANCH_REFUSEES = tuple(forme.format(suite) for forme, suite in itertools.product(FORMES_GIT, SUITES_BRANCH_REFUSEES)) + tuple(
    forme.format(suite) for forme, suite in itertools.product(FORMES_AUTRES, SUITES_NOYAU))

# Formes nommées par la consigne de l'auteur, un test chacune.
BRANCH_NUE = ("git branch -M x main", "git branch -M main", "git branch -C x main", "git branch -C main", "git branch -m -f x main", "git branch --copy --force x main")
BRANCH_C_WORKTREE = (f"git -C {WORKTREE} branch -M x main", f"git -C {WORKTREE_ABS} branch -C x main", f"git -C {WORKTREE} branch -M main", "git -C . branch -C x main")
BRANCH_CHEMIN_ABSOLU = ("/usr/bin/git branch -M x main", f"/usr/bin/git -C {WORKTREE} branch -C x main", "/opt/homebrew/bin/git branch -M main")
BRANCH_ENV = ("env GIT_TRACE=1 git branch -M x main", f"env GIT_TRACE=1 git -C {WORKTREE} branch -C x main", "/usr/bin/env GIT_TRACE=1 git branch -C x main",
              f"env PMZILLA_NO_EVALS=1 git -C {WORKTREE_ABS} branch -M main")
BRANCH_CD = (f"cd {WORKTREE} && git branch -M x main", f"cd {WORKTREE}; git branch -C x main", f"cd {ESPACE} && git branch -M main", f"cd {WORKTREE} && git -C . branch -C x main")
BRANCH_CHAINAGES = ("git status && git branch -M x main", "git status || git branch -C x main", "git status | git branch -M main", "git status & git branch -C main",
                    "git status &&git branch -M x main", "git status;git branch -C x main", "git status |git branch -M x main", "git status&git branch -C x main",
                    f"git status || git -C {WORKTREE} branch -M x main", f"git status;git -C {WORKTREE} branch -C x main")
BRANCH_OPTIONS_APRES = ("git branch x main -M", "git branch main -M", "git branch x main -C", "git branch main -C", "git branch -m x main -f", "git branch main -m -f",
                        "git branch -M x main --", "git branch -M main x")
BRANCH_OPTIONS_AVANT = ("git -c x=y branch -M x main", "git --no-pager branch -C x main", f"git --git-dir={WORKTREE_ABS}/.git branch -M main",
                        f"git -c x=y -C {WORKTREE} branch -C x main", "env GIT_TRACE=1 git --git-dir=x branch -M x main")

HOOKS_REFUSEES = (
    "git config core.hooksPath /x", "git config --global core.hookspath /x", "git config core.HooksPath /x", "git config core.HOOKSPATH /x", "git config core.Hookspath /x",
    "git -c core.hooksPath=/x commit -m y", "git --config-env=core.hooksPath=V status", f"git -C {WORKTREE} -c core.hooksPath=/x checkout -B main",
    "env GIT_TRACE=1 git -c core.hookspath=/x branch -M main", "git status && git -c core.hooksPath=/x commit -m y", "cd x; git config core.hooksPath /x",
    "GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=core.hooksPath GIT_CONFIG_VALUE_0=/x git status", "env GIT_CONFIG_GLOBAL=/x git status", "export GIT_CONFIG_SYSTEM=/x; git status",
    "GIT_CONFIG_COUNT=0 git status", "env GIT_CONFIG_NOSYSTEM=1 git status", "/usr/bin/env GIT_CONFIG_KEY_0=x git status",
)

# EFFETS énoncés : commandes qui ne font que nommer le texte (ou lire) et que les règles refusent aussi. Assertés refusés.
EFFETS = (
    "Toute commande qui contient `hooksPath` (casses `hooksPath`, `hookspath`, `HooksPath`, `HOOKSPATH`, `Hookspath`) ou `GIT_CONFIG_` est refusée où que le texte figure : "
    "`git -C <worktree> grep -n hooksPath docs`, `git commit -m \"… hooksPath …\"`, `grep -n GIT_CONFIG_ docs/x.md`, `echo hookspath` ; voie permise : l'outil Grep, l'outil Read, "
    "`git commit -F <fichier du dossier de travail>` pour un message et `tools/gh_issue.py --body-file` pour un corps d'issue",
    "Les règles `git branch` exigent un mot qui commence par `main` avec une option d'écriture forcée (`-M`, `-C`, `-fM`, `-fC`, `-fm`, `-mf`, `-fc`, `-cf`, ou `-m`/`-c` avec `-f`, "
    "`--move`, `--copy` et `--force` compris) : `git branch -M x main`, `git branch -M main x` (renommer `main` ailleurs), `git branch main -M`, `git branch -M x main;`, "
    "`git branch -M x mainline` et `git branch -M x main-copie` sont refusés ; un message de commit ou une recherche qui écrit « && git branch -M x main » ou "
    "« ; git branch -C x main » l'est aussi",
    "Le motif de `-f` et de `-m`/`-c` est une sous-chaîne : `git branch --format=… --merged main` est refusé (`--format` contient `-f`, `--merged` contient `-m`) ; voie permise : "
    "`git for-each-ref --merged main`, ou la même commande sans `--format`",
    "Les noms de branche qui contiennent ces segments sont refusés avec `main` en destination : `git branch fix-flaky-ci main` (création depuis main ; `-f` puis `-c` dans le nom) "
    "et `git branch -f fix-merge-x main` (`-m` dans le nom) sont refusés ; `git branch -f x main` reste permis pour un nom sans segment `-f`, `-m` ou `-c`",
    "Une chaîne qui commence par `git branch` est refusée dès qu'un `-C` puis ` main` suivent, même dans une autre commande : `git branch -d x && git -C <worktree> rebase main` "
    "est refusé (conforme à la règle « une commande par appel » : lancer `git -C <worktree> rebase main` seul)",
    "Restent permis : `git branch -c x y`, `-d x`, `-D x`, `--list`, `-m x y`, `-f x main` (nom sans segment `-f`, `-m` ou `-c`), `-m x main` et `-c x main` sans force (Git les refuse si `main` existe), `-M x feat/main`, "
    "`-M x domain`, `--merged main`, `--no-merged main`, `--show-current` ; voie permise pour intégrer main : « " + VOIE_PERMISE + " »",
)
EFFETS_COMMANDES = (
    f"git -C {WORKTREE} grep -n hooksPath docs", "git commit -m \"documente core.hooksPath\"", "git commit -m \"note GIT_CONFIG_COUNT\"", "grep -n GIT_CONFIG_ docs/x.md",
    "echo hookspath", f"git -C {WORKTREE} log --grep HOOKSPATH", "echo x | grep Hookspath",
    "git commit -m \"x && git branch -M x main\"", "git commit -m \"x; git branch -C x main\"", "git commit -m \"x | git branch -M main\"",
    "git branch --format=%(refname:short) --merged main", f"git -C {WORKTREE} branch --format=%(refname:short) --merged main",
    "git branch --sort=-committerdate --format=x --no-merged main", "git branch -M main x",
    # noms de branche qui contiennent -f, -m, -c ; chaîne qui commence par git branch avec -C puis main
    "git branch fix-flaky-ci main", "git branch -f fix-merge-x main", f"git branch -d x && git -C {WORKTREE} rebase main",
    # le mot qui commence par main : mainline, main-copie, main;, main"
    "git branch -M x mainline", "git branch -M x main-copie", "git branch -M x main;git status", "git branch -M x main; git status", "git branch -C x main|cat",
    "git branch -M x main&&git status", "git branch -M x main)", "git commit -m \"x && git branch -M x main\"", f"git -C {WORKTREE} branch -C x mainline",
)

# Limites connues, DÉCLARÉES : formes que les règles par motif ne voient pas, parce que le motif est sensible à la casse, ancré sur le début de la commande ou sur une
# liste d'enveloppes, ou parce qu'elles ne passent pas par `git branch` avec une option listée. Elles PASSENT aujourd'hui ; ce n'est pas une garantie mais un état connu.
# Défense qui reste : la lecture des commandes par l'auteur, l'instruction de CLAUDE.md et, pour `main`, le crochet reference-transaction. Si une règle les refuse un
# jour, le test échoue et c'est ce tuple qui change.
LIMITES_CONNUES = (
    # git pack-refs --all : aucune règle ; refusé en session par reference-transaction (la même mise à jour), exit en erreur
    "git pack-refs --all", "git pack-refs --all --prune", "git -C ~/PMZilla-Lab/worktrees/wt-feat-x pack-refs --all",
    # core.hooksPath : casses non couvertes (git ne distingue pas la casse de la clé, le motif si), mot coupé ou cité
    "git config core.hooksPATH /x", "git config core.hookSpath /x", "git -c core.HOOKSpath=/x status", "git -c core.hooksPAth=/x status", "git -c core.hooks''Path=/x status",
    "git -c core.hooks\"\"Path=/x status", "git -c core.hook\\sPath=/x status",
    # variables : GIT_CONFIG sans souligné, minuscules (sans effet pour Git, mais le motif ne les voit pas)
    "GIT_CONFIG=/x git status", "git_config_count=1 git status",
    # main écrit autrement que le mot isolé précédé d'un espace
    "git branch -M x refs/heads/main", "git branch -M x 'main'", "git branch -M x \"main\"", "git branch -C x refs/heads/main", "git branch --move --force x refs/heads/main",
    # grappe d'options absente de la liste
    "git branch -vM x main", "git branch -qM x main", "git branch -vC x main", "git branch -qfm x main",
    # espace double, tabulation, retour à la ligne, substitution, accents graves
    "git  branch -M x main", "git\tbranch -M x main", "git branch\t-M x main", "git status\ngit branch -M x main", "$(git branch -M x main)", "echo $(git branch -C x main)",
    "`git branch -M x main`",
    # enveloppes absentes de la liste, affectation de variable, sous-shell, interpréteur, pipe
    "nice git branch -M x main", "time git branch -C x main", "nohup git branch -M main", "command git branch -M x main", "git status && nice git branch -M x main",
    "FOO=1 git branch -M x main", "cd x && env A=1 git branch -M x main", "(git branch -M x main)", "sh -c 'git branch -M x main'", "bash -c \"git branch -C x main\"", "echo main | xargs git branch -M x",
    # alias
    "git bm x main",
)

COMMANDES_PERMISES = (
    # git branch : lecture, création, suppression, renommage ou copie sans force vers un autre nom, ou vers main sans force (Git le refuse si main existe)
    "git branch", "git branch -a", "git branch -vv", "git branch --list", "git branch --show-current", "git branch --merged main", "git branch --no-merged main",
    "git branch --contains abc", "git branch feat/x main", "git branch -d x", "git branch -D x", "git branch -d feat-Mx", "git branch -c x y", "git branch -m x y", "git branch -m x main",
    "git branch -c x main", "git branch -f x main", "git branch -f main-x abc", "git branch -u origin/main", "git branch --set-upstream-to=origin/main",
    # -M et -C vers un autre nom que main (le mot doit COMMENCER par main : `mainline` et `main-copie` sont refusés ; `feat/main` et `domain` passent)
    "git branch -M x feat/main", "git branch -C x feat/main", "git branch -M x domain", "git branch -C x domain",
    "git branch -M x y", "git branch -C x y", "git branch -m -f x y",   # --move --force et --copy --force : déjà refusés par `git *--force*` (fragment 26)
    # sous les autres formes
    f"git -C {WORKTREE} branch -c x y", f"git -C {WORKTREE} branch -d x", f"git -C {WORKTREE} branch --list", f"git -C {WORKTREE_ABS} branch -m x y",
    f"git -C {WORKTREE} branch -M x feat/main", f"git -C {WORKTREE} branch -f x main", f"git -C {WORKTREE} branch --merged main", f"git -C {ESPACE} branch --show-current",
    "env GIT_TRACE=1 git branch -d x", "env GIT_TRACE=1 git branch -M x feat/main", "/usr/bin/git branch -c x y", "/usr/bin/git branch -M x domain",
    f"cd {WORKTREE} && git branch -d x", f"cd {WORKTREE}; git branch -M x feat/main", "git status && git branch -m x y", "git fetch; git branch -c x y",
    # autres commandes git, sans le texte interdit
    "git status", f"git -C {WORKTREE} status", "git log --oneline -5", "git rebase main", f"git -C {WORKTREE} rebase main", "git commit -F docs/message.txt",
    f"git -C {WORKTREE} commit -F docs/message.txt", "git fetch", "git add tests/x.py", "env GIT_TRACE=1 git status", "GIT_TRACE=1 git status",
    "bash tests/run_all.sh settings_deny", "uv run tools/pilot.py freeze --check", "python3 tests/settings_deny/test_settings_deny_garde_main_session.py --json",
)
# Sous-ensemble contrôlé aussi contre les règles RÉELLES privées de celles du bloc (avant la pose, aucune règle d'avant ne doit les refuser).
PERMISES_REELLES = tuple(c for c in COMMANDES_PERMISES if c.startswith(("git branch", f"git -C {WORKTREE} branch", "git status", "git log")))


def commandes_refusees():
    """Toutes les formes que la session ne doit pas exécuter."""
    yield from BRANCH_REFUSEES
    for famille in (BRANCH_NUE, BRANCH_C_WORKTREE, BRANCH_CHEMIN_ABSOLU, BRANCH_ENV, BRANCH_CD, BRANCH_CHAINAGES, BRANCH_OPTIONS_APRES, BRANCH_OPTIONS_AVANT,
                    HOOKS_REFUSEES, EFFETS_COMMANDES):
        yield from famille


class Matrice:
    """Cas communs au bloc REGLES_39 et aux règles réelles ; `self.moteur` est fourni par la classe qui les mélange."""

    def verifier_formes_refusees(self):
        manquantes = [c for c in commandes_refusees() if not self.moteur.interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} forme(s) non refusée(s)")

    def verifier_formes_permises(self):
        refusees = [c for c in COMMANDES_PERMISES if self.moteur.interdite(c)]
        self.assertEqual(refusees, [], "commande(s) permise(s) refusée(s) : règle trop large")


class BlocGardeMainSession(Matrice, unittest.TestCase):
    """Le moteur de motifs appliqué au bloc à poser : vert avant comme après la pose."""

    @classmethod
    def setUpClass(cls):
        cls.moteur = Moteur(REGLES_39)

    def refuses(self, commandes):
        for commande in commandes:
            self.assertTrue(self.moteur.interdite(commande), commande)

    def permises(self, commandes):
        for commande in commandes:
            self.assertFalse(self.moteur.interdite(commande), commande)

    # --- déclaration -----------------------------------------------------------------------------------------------------------------

    def test_le_bloc_est_fait_de_regles_bash_sans_doublon(self):
        self.assertEqual(len(REGLES_39), len(set(REGLES_39)))
        self.assertTrue(all(r.startswith("Bash(") and r.endswith(")") for r in REGLES_39))
        self.assertEqual(garde_regles.constats(REGLES_39), [])

    def test_les_comptes(self):
        self.assertEqual(len(OPTIONS_SEULES) * 2 + len(RENOMMER_COPIER) * 6, 28)
        self.assertEqual(len(CORPS_BRANCH), 28)
        self.assertEqual(len(CORPS_BRANCH), len(set(CORPS_BRANCH)))
        self.assertEqual((len(DENY_HOOKS), len(DENY_BRANCH)), (6, 560))
        self.assertEqual(len(REGLES_39), 566)

    def test_la_garde_partagee_trouve_la_liste(self):
        texte = Path(__file__).read_text(encoding="utf-8")
        self.assertTrue(garde_regles.imprime_json(texte))
        self.assertEqual(garde_regles._liste_du_module(Path(__file__), garde_regles.CONVENTION), list(REGLES_39))

    def test_aucune_regle_write_ni_notebookedit_ni_edit(self):
        self.assertEqual([r for r in REGLES_39 if r.startswith(("Write(", "NotebookEdit(", "Edit("))], [])

    def test_aucun_doublon_avec_les_fragments_existants(self):
        """Aucune règle du bloc n'est déjà dans un autre fragment de .claude/deny/ (ORDRE) ni, hors pose, dans settings.json."""
        autres = set()
        for nom in ORDRE.read_text(encoding="utf-8").split():
            if nom == NOM_39:
                continue
            autres.update(ligne for ligne in (DENY / nom).read_text(encoding="utf-8").splitlines() if ligne.strip())
        self.assertEqual([r for r in REGLES_39 if r in autres], [])
        reglages = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        if not pose_declaree():
            self.assertEqual([r for r in REGLES_39 if r in reglages], [])

    def test_les_regles_a_joker_nu_sont_celles_de_chainage_et_hooks(self):
        """Écart assumé avec la convention du fragment 26 (comme les fragments 27 et 38) : seules ces règles commencent par `*` sans `/`."""
        jokers = sorted(r for r in REGLES_39 if r.startswith("Bash(*") and not r.startswith("Bash(*/"))
        attendus = list(DENY_HOOKS) + [r for r in DENY_BRANCH if r.startswith(("Bash(*&", "Bash(*;", "Bash(*|"))]
        self.assertEqual(jokers, sorted(attendus))

    def test_chaque_regle_branch_exige_un_mot_qui_commence_par_main(self):
        """Le mot `main` est précédé d'un espace (`feat/main` et `domain` passent) ou ouvre le nom suivi d'un espace ; jamais `*main*` sans espace."""
        for corps in CORPS_BRANCH:
            self.assertTrue(" main*" in corps or " main *" in corps or corps.startswith("*main *"), corps)
            self.assertNotIn("*main*", corps)

    def test_les_regles_hooks_nomment_leur_texte(self):
        self.assertEqual(sorted(r for r in DENY_HOOKS if "GIT_CONFIG_" in r), ["Bash(*GIT_CONFIG_*)"])
        for casse in CASSES_HOOKSPATH:
            self.assertIn(f"Bash(*{casse}*)", DENY_HOOKS)
        self.assertEqual(len(set(c.lower() for c in CASSES_HOOKSPATH)), 1)

    # --- un test par refus -----------------------------------------------------------------------------------------------------------

    def test_branch_ecriture_forcee_nue_est_refusee(self):
        self.refuses(BRANCH_NUE)

    def test_branch_avec_c_est_refuse_y_compris_dans_un_worktree(self):
        self.refuses(BRANCH_C_WORKTREE)

    def test_branch_par_chemin_absolu_est_refuse(self):
        self.refuses(BRANCH_CHEMIN_ABSOLU)

    def test_branch_sous_env_est_refuse(self):
        self.refuses(BRANCH_ENV)

    def test_branch_apres_cd_est_refuse(self):
        self.refuses(BRANCH_CD)

    def test_branch_apres_un_chainage_est_refuse(self):
        self.refuses(BRANCH_CHAINAGES)

    def test_branch_avec_options_apres_les_noms_est_refuse(self):
        self.refuses(BRANCH_OPTIONS_APRES)

    def test_branch_avec_options_avant_le_verbe_est_refuse(self):
        self.refuses(BRANCH_OPTIONS_AVANT)

    def test_chaque_suite_sous_chaque_forme_est_refusee(self):
        manquantes = [c for c in BRANCH_REFUSEES if not self.moteur.interdite(c)]
        self.assertEqual(manquantes[:5], [], f"{len(manquantes)} forme(s) non refusée(s)")

    def test_chaque_option_d_ecriture_forcee_est_refusee_avec_main_ou_main_seul(self):
        for option in OPTIONS_SEULES + ("-Mf", "-Cf", "--move --force", "--force --move", "--copy --force", "--force --copy"):
            self.refuses((f"git branch {option} x main", f"git branch {option} main", f"git -C {WORKTREE} branch {option} x main", f"git branch x main {option}"))

    def test_les_casses_de_hookspath_et_git_config_sont_refusees(self):
        self.refuses(HOOKS_REFUSEES)

    def test_chaque_regle_hooks_est_necessaire(self):
        """Sans elle, la commande qui lui est propre passe : aucune des six règles n'est redondante."""
        propres = {f"Bash(*{casse}*)": f"git config core.{casse} /x" for casse in CASSES_HOOKSPATH}
        propres["Bash(*GIT_CONFIG_*)"] = "GIT_CONFIG_COUNT=1 git status"
        for regle, commande in propres.items():
            self.assertIn(regle, REGLES_39)
            self.assertTrue(self.moteur.interdite(commande), commande)
            self.assertFalse(Moteur([r for r in REGLES_39 if r != regle]).interdite(commande), f"règle redondante : {regle}")

    def test_chaque_corps_de_regle_branch_est_necessaire(self):
        """Sous le lanceur nu, sans le corps, la commande qui lui est propre passe : aucun des vingt-huit corps n'est redondant."""
        for corps, suite in corps_et_exemples():
            commande = f"git branch {suite}"
            regle = f"Bash(git branch {corps})"
            self.assertIn(regle, REGLES_39)
            self.assertTrue(self.moteur.interdite(commande), commande)
            self.assertFalse(Moteur([r for r in REGLES_39 if r != regle]).interdite(commande), f"corps redondant : {corps} (commande : {commande})")

    def test_chaque_famille_de_lanceur_est_necessaire(self):
        """Sans la famille (jeu de règles d'un même lanceur), au moins une forme passe : aucune famille n'est morte."""
        familles = {"nu": ("Bash(git branch ", "Bash(git -* branch "), "chemin": ("Bash(*/git ",), "env": ("Bash(env ",),
                    "chemin-env": ("Bash(*/env ",), "chainage": ("Bash(*&", "Bash(*|", "Bash(*;")}
        formes = tuple(BRANCH_NUE + BRANCH_C_WORKTREE + BRANCH_CHEMIN_ABSOLU + BRANCH_ENV + BRANCH_CD + BRANCH_CHAINAGES + BRANCH_OPTIONS_AVANT)
        for nom, prefixes in familles.items():
            reste = Moteur([r for r in REGLES_39 if not (r.startswith(prefixes) and " branch " in r)])
            passent = [c for c in formes if not reste.interdite(c)]
            self.assertTrue(passent, f"famille redondante : {nom}")

    # --- permis, effets et limites ---------------------------------------------------------------------------------------------------

    def test_les_commandes_permises_restent_permises(self):
        self.verifier_formes_permises()

    def test_branch_c_d_list_m_et_vers_un_autre_nom_restent_permis(self):
        self.permises(("git branch -c x y", "git branch -d x", "git branch --list", "git branch -m x y", "git branch -M x feat/main", "git branch -M x domain",
                       "git branch -C x feat/main", f"git -C {WORKTREE} branch -c x y", f"git -C {WORKTREE} branch -m x y"))

    def test_main_suivi_d_un_suffixe_est_refuse_par_choix(self):
        """Le mot qui commence par `main` : `mainline` et `main-copie` sont refusés avec -M ou -C (effet déclaré) ; la limite reste `'main'` et `refs/heads/main`."""
        self.refuses(("git branch -M x mainline", "git branch -M x main-copie", "git branch -C x main-v2", "git branch -M x main;git status"))
        self.permises(("git branch -M x feat/main", "git branch -M x domain"))

    def test_la_voie_permise_est_ecrite_et_permise(self):
        self.assertEqual(VOIE_PERMISE, "intégrer main : git -C <worktree> rebase main")
        self.permises((f"git -C {WORKTREE} rebase main", f"git -C {WORKTREE_ABS} rebase main", "git rebase main"))
        self.assertTrue(any(VOIE_PERMISE in effet for effet in EFFETS))

    def test_les_effets_sont_refuses_et_ecrits(self):
        self.assertGreaterEqual(len(EFFETS), 4)
        self.refuses(EFFETS_COMMANDES)

    def test_les_limites_connues_passent_et_sont_declarees(self):
        """Chaque limite déclarée passe les règles du bloc : le tuple décrit l'état réel, ni plus ni moins."""
        self.assertEqual(len(LIMITES_CONNUES), len(set(LIMITES_CONNUES)))
        refusees = [c for c in LIMITES_CONNUES if self.moteur.interdite(c)]
        self.assertEqual(refusees, [], "limite(s) déclarée(s) maintenant refusée(s) : la retirer de LIMITES_CONNUES")

    def test_pack_refs_reste_une_limite_declaree_sans_regle(self):
        self.assertTrue(any("pack-refs" in c for c in LIMITES_CONNUES))
        self.assertEqual([r for r in REGLES_39 if "pack-refs" in r], [])


class ReglesExistantes(unittest.TestCase):
    """Les commandes permises contre les règles réelles privées de celles du bloc : même résultat avant et après la pose."""

    @classmethod
    def setUpClass(cls):
        deny = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]["deny"]
        cls.moteur = Moteur([r for r in deny if r not in REGLES_39])

    def test_commandes_permises_non_refusees_par_les_regles_d_avant(self):
        self.assertEqual([c for c in PERMISES_REELLES if self.moteur.interdite(c)], [])

    def test_l_ecriture_forcee_de_main_et_hookspath_ne_sont_pas_deja_refuses(self):
        """Garde le sens du bloc : sans lui, ces commandes ne sont pas refusées par une règle d'avant (hors `--force`, déjà refusé par le fragment 26)."""
        for commande in ("git branch -M x main", "git branch -C x main", f"git -C {WORKTREE} branch -M main", "git branch -fm x main", "git branch main -M",
                         "git config core.hooksPath /x", "git -c core.hooksPath=/x status", "GIT_CONFIG_COUNT=1 git status"):
            self.assertFalse(self.moteur.interdite(commande), commande)


class DansLeFichierDeReglages(unittest.TestCase):
    """La pose par l'auteur : sautée avant, échoue si elle est partielle, passe si tout y est."""

    @classmethod
    def setUpClass(cls):
        permissions = json.loads(REGLAGES.read_text(encoding="utf-8"))["permissions"]
        cls.deny = permissions["deny"]
        cls.allow = permissions.get("allow", [])
        cls.manquantes = [r for r in REGLES_39 if r not in cls.deny]

    # Désherbage du 2026-10-28 (D79) : les branches de saut « fragment 39 pas encore posé » sont retirées. Le fragment 39 est dans ORDRE et dans
    # settings.json, la pose est déclarée : ces branches ne se déclenchaient plus, et elles auraient masqué une pose partielle.

    def test_la_pose_declaree_est_complete(self):
        """Le fragment 39 absent d'un côté seulement (fichier sans ORDRE, ou ORDRE sans fichier) est une pose partielle."""
        self.assertTrue(FRAGMENT_39.is_file(), f"{NOM_39} absent de .claude/deny/ alors qu'ORDRE le nomme")
        self.assertIn(NOM_39, ORDRE.read_text(encoding="utf-8").split(), f"{NOM_39} présent sans être dans .claude/deny/ORDRE")

    def test_les_regles_deny_sont_dans_settings_json(self):
        self.assertEqual(self.manquantes, [], f"pose partielle : {len(self.manquantes)} règle(s) de REGLES_39 absente(s) de .claude/settings.json")

    def test_le_fragment_39_est_dans_ordre_apres_la_pose(self):
        self.assertIn(NOM_39, ORDRE.read_text(encoding="utf-8").split(), "fragment 39 absent de .claude/deny/ORDRE")
        lignes = [ligne for ligne in FRAGMENT_39.read_text(encoding="utf-8").splitlines() if ligne.strip()]
        self.assertEqual(lignes, list(REGLES_39))

    def test_aucune_regle_allow_ne_permet_hookspath_git_config_ni_branch_force(self):
        autres = [r for r in self.allow if "hooksPath" in r or "GIT_CONFIG" in r or "git branch -M" in r or "git branch -C" in r or r in ("Bash(git *)", "Bash(*)")]
        self.assertEqual(autres, [])

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
        print("\n".join(regles_attendues()))
    else:
        unittest.main()
