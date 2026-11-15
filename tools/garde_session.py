#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""PMZilla Lab : garde de session, niveau 1 de la correction de l'audit #629 (change session-guard-n1).

Hook Claude Code PreToolUse des appels Bash : refuse, avant leur lancement, les contournements évidents des règles deny et des crochets, chacun
rattaché à sa classe de l'audit (A1 à A6 git, security et lancement des scripts réservés, B gh, C écriture des gardes et des crochets, E variables
de réglage, G docker, H skill en quarantaine). La commande est lue par l'analyseur de tools/npm_guard.py, par un rappel (npm_guard.avec_rappel) :
lanceurs, chaînes `sh -c`, substitutions et listes de commandes comprises. Une analyse en échec refuse seulement si le texte brut contient un mot
surveillé ; les autres gardes et les règles deny s'appliquent ensuite.

    python3 tools/garde_session.py   refusé : une ligne sur la sortie d'erreur, code 2 (le hook la lance par chemin absolu, sous -I)

Sortie (D10) : code 0 pour laisser passer, code 2 pour refuser ; rien sur la sortie standard ; une ligne en français sur la sortie d'erreur,
`garde de session : refusé : <classe> : <forme>. Voie permise : <voie>.`, qui ne reproduit jamais la commande. Entrée illisible ou exception
de la garde, lecture de l'entrée et import du module voisin compris : code 2 (fermé par défaut, Q16). Objet sans tool_name lisible : code 2. Autre outil que
Bash, bien formé, ou commande vide : code 0.

La décision vit dans la fonction pure `decider(commande, contexte) -> Verdict | None` ; la ligne de sortie ne fait que l'imprimer.

Lancée depuis la copie de l'espace de travail, par son chemin absolu et avec `python3 -I` (D2) : le dossier de ce fichier passe en tête de
sys.path avant l'import d'un module voisin, jamais le dossier courant.

Remplace : rien dans les règles deny (les fragments 02, 12, 26 et 39 restent comme doublons, une matrice de tests compare leurs formes à cette
garde, dans la suite garde_session). Retrait : permanent ; les doublons tombent au désherbage du niveau 1, une fois le bac à
sable posé et sa sonde verte deux semaines. Chaque règle ci-dessous dit ce qu'elle remplace et sa condition de retrait.

Limites (réservées au niveau 2, bac à sable) : un programme ou un script qui lance git, gh, security ou docker lui-même, un script écrit puis
lancé, les fonctions et alias définis dans la même commande, l'écart entre le contrôle et le lancement, une écriture par un programme hors de la
liste, les variables posées dans un script, l'accès au shell de Colima.

Bibliothèque standard seulement. Ne lit que l'entrée standard, les fichiers de configuration de Git par `git config` et le fichier docker-compose
du dossier de contenu ; n'écrit aucun fichier ; ne lance que des lectures de Git (git config --get-all, git rev-parse), avec un environnement
réduit à PATH et au vrai HOME.
"""
import json
import os
import pwd
import re
import subprocess
import sys
from typing import NamedTuple

sys.dont_write_bytecode = True   # R-20261111-13 : `python3 -I` ignore PYTHONDONTWRITEBYTECODE ; l'import du module voisin n'écrit aucun .pyc (comme finish_checks.py)
_DOSSIER = os.path.dirname(os.path.realpath(__file__))
if sys.path[:1] != [_DOSSIER]:
    sys.path.insert(0, _DOSSIER)
try:
    import npm_guard  # noqa: E402  (module voisin, chargé depuis le dossier de ce fichier)
except Exception:   # module voisin absent ou cassé : la garde refuse (code 2) au lieu de sortir en 1 sur une trace (revue Opus, constat 14)
    npm_guard = None

INCONNU = getattr(npm_guard, "INCONNU", "\x03")
VARIABLE_BRUTE = re.compile("[" + getattr(npm_guard, "VAR_DEB", "\x01") + getattr(npm_guard, "VARQ_DEB", "\x04") + "]([^"
                            + getattr(npm_guard, "VAR_FIN", "\x02") + "]*)" + getattr(npm_guard, "VAR_FIN", "\x02"))

# --- Messages (D10) -----------------------------------------------------------------------------------------------------------------------
# clé : (classe, forme, voie permise). Les formes sont les phrases clés du design ; les exigences et les tests s'y réfèrent.
FORMES = {
    "A1": ("A1", "git push, send-pack ou http-push", "le train lancé par l'auteur"),
    "A2": ("A2", "sous-commande git inconnue ou alias", "la sous-commande git écrite en toutes lettres"),
    "A3": ("A3", "git qui écrit l'arbre de l'espace de travail ou de run", "la même commande dans un worktree"),
    "A4": ("A4", "security", "aucune en session : le Trousseau reste à l'auteur"),
    "A5": ("A5", "script réservé à l'auteur", "un fichier d'étape de l'auteur"),
    "A6-saute": ("A6", "option qui saute les crochets", "la même commande sans cette option"),
    "A6-reglage": ("A6", "réglage git hors liste blanche", "les clés core.quotepath, color.* et advice.* seulement"),
    "A6-config": ("A6", "git config en écriture", "git config en lecture ; un réglage passe par un fichier d'étape de l'auteur"),
    "A6-variable": ("A6", "variable qui déplace la configuration de git", "la même commande sans cette variable"),
    "A6-hookspath": ("A6", "core.hooksPath défini", "le signaler à l'auteur"),
    "A6-liens": ("A6", "liens des crochets non conformes", "le signaler à l'auteur, qui réinstalle les crochets"),
    "B": ("B", "gh hors liste fermée", "gh issue view ou gh issue list ; pour écrire, tools/gh_issue.py"),
    "B-variable": ("B", "variable de gh", "la même commande sans cette variable"),
    "C3": ("C3", "gh_issue.py hors de la copie de l'espace de travail", "la copie de l'espace de travail, par son chemin"),
    "C": ("C", "écriture du shell vers un chemin protégé",
          "une branche dans un worktree, puis un train ; un réglage passe par un fichier d'étape de l'auteur"),
    "E": ("E", "variable de réglage des gardes", "la même commande sans cette variable"),
    "G": ("G", "docker sur la vraie base, compose du projet, montage de l'hôte ou destruction", "bash tools/ci_local.sh run <branche>"),
    "H": ("H", "skill en quarantaine", "aucune avant le go ou no-go de BMAD 7 et une revue Opus"),
    "entree-illisible": ("—", "entrée illisible", "relancer la commande ; si le refus revient, le signaler"),
    "erreur-interne": ("—", "erreur interne de la garde", "relancer la commande ; si le refus revient, le signaler"),
}


class Verdict(NamedTuple):
    """Décision de refus : la classe de l'audit, la clé de la forme, la forme (phrase clé) et la voie permise."""
    classe: str
    cle: str
    forme: str
    voie: str


# Formes reprises des fragments deny 26 et 39 (R-20261108-01, questions 15 et 16) : ce que ces fragments refusent et que le design D4/D6 ne reprenait pas.
# Table à part de FORMES pour que celle du design (D10) reste exacte. Remplace : les fragments 26 (--force hors de push, git merge, git pull, texte push)
# et 39 (git branch -M|-C … main, texte hooksPath et GIT_CONFIG_), qui restent posés jusqu'au désherbage du niveau 1 (bac à sable posé, sonde verte deux
# semaines). Retrait : permanent pour les formes elles-mêmes ; cette table fusionne dans FORMES au désherbage.
FORMES_REPRISES = {
    "A1-fusion": ("A1", "git merge ou git pull", "git -C <worktree> rebase main ; l'intégration dans main est faite par les scripts de fin que l'auteur lance"),
    "A1-texte": ("A1", "texte push dans une commande git -C", "l'outil Grep ou Read ; git commit -F <fichier> pour un message"),
    "A6-force": ("A6", "option --force, ou ce texte, dans une commande git", "la même commande sans --force ; git commit -F <fichier> pour un message"),
    "A6-main": ("A6", "git branch -M ou -C visant main", "aucune : main n'est jamais renommée ni écrasée en session"),
    "A6-texte": ("A6", "texte core.hooksPath ou GIT_CONFIG_ dans une commande", "l'outil Grep ou Read ; git commit -F <fichier> pour un message"),
    # Revue Opus de la garde (constat 4) : option de git qui lance une commande (rebase --exec, grep -O, --upload-pack, --receive-pack, --exec-path).
    # Remplace : rien (aucun fragment deny ne la voit). Retrait : permanent, tant que le niveau 2 ne bloque pas les processus fils de git.
    "A6-commande": ("A6", "option git qui lance une commande", "la même commande sans cette option"),
    # R-20261108-04, décision 3 (a) : formes de git qui effacent du travail, déplacent HEAD, vident le reflog ou écrivent main sans passer par les crochets.
    # Remplace : rien (les règles deny ne voient que des commandes entières ; git stash reste couvert par elles). Retrait : permanent, tant que le
    # niveau 2 (bac à sable) ne bloque pas l'écriture de l'arbre de travail et des références par les sessions.
    "A6-destructif": ("A6", "git qui efface des fichiers ou des modifications (clean, checkout -f, switch --discard-changes)",
                      "git clean -n pour un essai ; git restore <fichier> dans un worktree"),
    "A6-reset": ("A6", "git reset --soft, --mixed, --keep ou --merge, ou avec un commit (--hard compris)", "git restore --staged <fichier> pour défaire un ajout ; git reset HEAD -- <fichier>"),
    # R-20261109-09 (4 a). Remplace : rien. Retrait : permanent (par cohérence avec `git reset --hard`, refusé sous toutes ses formes dans un worktree).
    "A6-recree": ("A6", "git checkout -B ou git switch -C (recrée une branche existante et déplace sa pointe)",
                  "la session recrée la branche ; git checkout -b <x> ou git switch -c <x> pour un nom neuf"),
    "A6-reflog": ("A6", "git reflog expire, delete, drop ou write", "git reflog ou git reflog show"),
    "A6-fetch": ("A6", "git fetch qui écrit la branche main", "git fetch sans refspec vers main ; main avance par les scripts de fin que l'auteur lance"),
    # R-20261108-07 : PATH modifié devant une commande git qui lance des crochets. Remplace : rien. Retrait : permanent.
    "E-path": ("E", "PATH modifié devant une commande git qui lance des crochets", "la même commande sans changer PATH"),
    # R-20261108-09. Remplace : rien. Retrait : permanent (le bac à sable limite ce qu'un programme atteint, pas quel programme tourne).
    # Défense en profondeur (R-20261108-10) : les crochets ne passent plus par le relais ; /usr/bin/git est aussi un relais xcrun.
    "E-developer-dir": ("E", "DEVELOPER_DIR modifié devant une commande git qui lance des crochets", "la même commande sans changer DEVELOPER_DIR"),
    # R-20261111-21, -29, -30, -32 (design D13) ; R-20261111-48 : la forme est le chemin absolu du dossier personnel (base des comptes), `~` refusé.
    # Remplace : la forme avec `~` de R-20261111-20 et de D13. Retrait : avec le bac à sable (les enveloppes figées ne sont plus exclues).
    "E-enveloppe": ("E", "enveloppe figée hors de la forme admise",
                    "/bin/bash --noprofile --norc -p <dossier personnel>/.pmzilla-lab/outils-figes/<enveloppe>.sh …, seule dans son appel "
                    "(ci_local, gh_issue, flow_views ou worktree)"),
    # R-20261111-33 (design D13). Remplace : rien (l'en-tête de ce fichier liste les fonctions et alias définis dans la même commande parmi ses limites ;
    # cette règle ferme cette limite pour ces noms seulement). Retrait : avec le bac à sable.
    "E-interprete": ("E", "fonction ou alias nommé bash, /bin/bash ou une enveloppe figée",
                     "un nom neutre ; l'enveloppe s'appelle par la forme admise, seule dans son appel"),
}


def verdict(cle: str) -> Verdict:
    classe, forme, voie = FORMES[cle] if cle in FORMES else FORMES_REPRISES[cle]
    return Verdict(classe, cle, forme, voie)


def message(v: Verdict) -> str:
    return f"garde de session : refusé : {v.classe} : {v.forme}. Voie permise : {v.voie}."


# --- Listes fermées -----------------------------------------------------------------------------------------------------------------------

# Chemins protégés (D7), relatifs à l'espace de travail et à l'arbre de run. Source unique : le fragment 41 en est calculé
# (tests/settings_deny/test_settings_deny_gardes.py) et la règle C de cette garde les lit ici. Remplace : rien. Retrait : permanent tant que le fragment 41 existe.
DOSSIERS_PROTEGES = ("tools/hooks", ".claude")
FICHIERS_TOOLS_PROTEGES = (
    "npm_guard.py", "npm_ci_conditions.py", "pipe_guard.py", "garde_session.py", "finish_lock.py", "lab_paths.py", "lab_paths.sh",
    "sensitive_names.py", "secret_scan.py", "commit_names_scan.py", "preuve_arbre.py", "identifiants_personnels.py", "gh_issue.py",
    "roadmap_model.py", "settings_assemble.py",
)
FICHIERS_PROTEGES = tuple(f"tools/{nom}" for nom in FICHIERS_TOOLS_PROTEGES)
REGLAGES_PARTOUT = re.compile(r"settings[^/]*\.json")   # `.claude/settings*.json` dans tout dossier, et celui du dossier personnel

CROCHETS = ("pre-commit", "post-commit", "commit-msg", "pre-push", "pre-merge-commit", "reference-transaction")

# Sous-commandes git admises (D4). Classe lecture : aucune écriture. Classe écriture : contrôle de la configuration effective. Toute autre : refus (A2).
# Ajoutées aux lectures du design, toutes sans écriture : show-ref, merge-base, reflog, check-ignore, check-attr, diff-tree, diff-index,
# diff-files, count-objects, cherry, show-branch (usage courant des sessions, fautes de frappe pour un alias autrement). Retrait : permanent.
GIT_LECTURE = frozenset({
    "status", "log", "show", "diff", "rev-parse", "rev-list", "ls-files", "ls-tree", "grep", "blame", "cat-file", "describe", "shortlog",
    "range-diff", "name-rev", "for-each-ref", "fetch", "version", "help", "show-ref", "merge-base", "reflog", "check-ignore", "check-attr",
    "diff-tree", "diff-index", "diff-files", "count-objects", "cherry", "show-branch",
})
GIT_ECRITURE = frozenset({
    "add", "commit", "rebase", "restore", "reset", "switch", "checkout", "cherry-pick", "revert", "am", "apply", "mv", "rm", "clean", "tag",
    "notes", "stash", "worktree",
})
# `branch` et `config` sont classés d'après leurs options (lecture ou écriture) ; `worktree list` est une lecture.
GIT_POUSSEE = frozenset({"push", "send-pack", "http-push"})
# merge et pull : refusés sous toutes leurs formes (R-20261108-01, question 15 a ; remplace le fragment 26 pour ces formes, retrait : permanent).
GIT_FUSION = frozenset({"merge", "pull"})

GLOBALES_AVEC_VALEUR = frozenset({"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--super-prefix", "--attr-source"})
GLOBALES_SANS_VALEUR = frozenset({
    "-p", "-P", "--paginate", "--no-pager", "--bare", "--literal-pathspecs", "--glob-pathspecs", "--noglob-pathspecs", "--icase-pathspecs",
    "--no-optional-locks", "--no-replace-objects", "--no-advice", "--no-lazy-fetch", "--version", "--help", "-h", "--html-path",
    "--man-path", "--info-path", "--exec-path",
})
REGLAGES_ADMIS = ("core.quotepath",)
PREFIXES_REGLAGES_ADMIS = ("color.", "advice.")

# Variables de réglage des gardes, des crochets et du verrou de fin (classe E, D6). Inventaire de la tâche 3.1, lu dans : tools/hooks/pre-commit (saut du
# contrôle vert, jeton du verrou), pre-merge-commit et reference-transaction (jeton), pre-push (lanceur des suites), post-commit (évaluations),
# tools/finish_lock.py (âge maximal, jeton, nom du verrou), tools/lab_paths.py et lab_paths.sh (dossiers du lab), tools/sensitive_names.py (listes de noms),
# tools/secret_scan.py (marqueur de session), tools/preuve_arbre.py (fichier d'index des preuves), tools/npm_ci_conditions.py (CDPATH), tools/gh_issue.py
# (exécutable gh de remplacement). PMZILLA_NO_EVALS est hors liste : les sessions le posent à chaque commit (CLAUDE.md). Remplace : rien (les règles deny ne
# voient que des commandes entières). Retrait : quand le niveau 2 fait ignorer ces variables aux outils d'une session.
VARIABLES_REGLAGE = frozenset({
    "PMZILLA_SKIP_GREEN_CHECK", "FINISH_LOCK_TOKEN", "FINISH_LOCK_NAME", "PMZILLA_FINISH_LOCK_MAX_AGE", "PRE_PUSH_RUNNER", "PMZILLA_AFTER_COMMIT",
    "PMZILLA_APRES_COMMIT", "PMZILLA_SANS_ESSAI", "PMZILLA_LAB_WORKSPACE", "PMZILLA_LAB_RUN", "PMZILLA_LAB_DATA", "DB_BACKUP_SAUVEGARDES",
    "PMZILLA_LAB_CONTEXT", "PMZILLA_LAB_WORKTREES", "PMZILLA_LAB_SENSITIVE_NAMES", "PMZILLA_NOMS", "PMZILLA_LAB_PRODUCT_VERSIONS",
    "CI_LOCAL_PREUVES_INDEX", "CLAUDECODE", "CDPATH", "PMZILLA_GH",
    # R-20261108-04, décision 2 (a) : PYTHONPATH déplace les modules que chargent les outils lancés par les crochets (même famille que GIT_* et les
    # variables ci-dessus). Remplace : rien (le crochet commit-msg lance ses scanners sous -I, qui l'ignore ; les autres crochets et outils non).
    # Retrait : quand le niveau 2 fait ignorer cette variable aux outils d'une session.
    "PYTHONPATH",
    # R-20261108-05, point 1 : PYTHONHOME et PYTHONUSERBASE déplacent aussi le code chargé par les crochets et les outils lancés sans -I.
    # Remplace : rien. Retrait : permanent.
    "PYTHONHOME", "PYTHONUSERBASE",
    # R-20261108-06, point 3 : PYTHONPLATLIBDIR change le dossier des bibliothèques ; PYTHONWARNINGS peut faire importer un module par sa catégorie.
    # Remplace : rien. Retrait : permanent.
    "PYTHONPLATLIBDIR", "PYTHONWARNINGS",
    # R-20261108-07. Remplace : rien. Retrait : permanent (le bac à sable limite ce qu'un programme atteint, pas quel programme tourne).
    # ZDOTDIR déplace les fichiers de démarrage de zsh, que lit un crochet écrit en zsh ; PYTHONPYCACHEPREFIX déplace le code compilé que charge un
    # programme Python lancé sans -I.
    "ZDOTDIR", "PYTHONPYCACHEPREFIX",
    # R-20261111-16 (R-20261111-13, -15). Remplace : rien. Retrait : permanent tant que les enveloppes figées sont exclues du bac à sable.
    # BASH_ENV et ENV font lire un fichier au premier bash d'une enveloppe, avant sa première ligne ; SHELLOPTS et BASHOPTS règlent ce que ce bash
    # exécute ; PS4 est développée (substitutions comprises) sous `set -x`. Les variables BASH_FUNC_… (préfixe, ci-dessous) et `export -f` passent une
    # fonction exportée, qui remplace une commande appelée par son nom.
    "BASH_ENV", "ENV", "SHELLOPTS", "BASHOPTS", "PS4",
    # R-20261111-23 : FIGE_RELANCE est le marqueur que pose une enveloppe figée avant de se relancer ; le poser avant l'appel la ferait croire déjà
    # relancée. Remplace : rien. Retrait : permanent tant que les enveloppes figées sont exclues du bac à sable.
    "FIGE_RELANCE",
})
NOMS_A_BORNES = frozenset({"ENV", "PS4"})   # noms courts de VARIABLES_REGLAGE : MOTS_SURVEILLES les cherche entre des bornes, pas dans un mot plus long
PREFIXES_REGLAGE = ("DB_BACKUP_", "BASH_FUNC_")   # BASH_FUNC_ : R-20261111-16, même remplace et même retrait que ci-dessus
VARIABLES_GH = frozenset({"GH_TOKEN", "GH_HOST", "GH_CONFIG_DIR"})
VARIABLES_GIT = frozenset({"HOME", "XDG_CONFIG_HOME"})

# Scripts que le fragment 07 refuse (classe A5, tâche 3.2) ; la matrice des doublons compare cette liste au fragment.
SCRIPTS_RESERVES = frozenset({"db_backup.sh", "doctor.sh", "finish_branch.sh", "finish_worktree.sh", "finish_train.sh"})
INTERPRETES_DE_SCRIPT = frozenset({"bash", "sh", "zsh", "dash", "ksh", "source", "."})
ETIQUETTES_LAUNCHCTL = ("com.pmzilla.db-backup", "com.pmzilla.offsite-")

SKILL_EN_QUARANTAINE = "bmad-eval-runner"   # classe H ; tombe avec la quarantaine (go ou no-go de BMAD 7 et revue Opus)

# Mots surveillés quand l'analyseur échoue : le texte brut qui en contient un est refusé.
MOTS_SURVEILLES = re.compile(
    r"(?<![A-Za-z0-9_-])(git|gh|security|docker|colima|limactl|launchctl)(?![A-Za-z0-9_-])|" + re.escape(SKILL_EN_QUARANTAINE)
    + "|" + "|".join(re.escape(s) for s in sorted(SCRIPTS_RESERVES)) + "|" + "|".join(re.escape(v) for v in sorted(VARIABLES_REGLAGE - NOMS_A_BORNES))
    + r"|(?<![A-Za-z0-9_])(?:" + "|".join(sorted(NOMS_A_BORNES)) + r")(?![A-Za-z0-9_])|BASH_FUNC_"
    + r"|GIT_[A-Z_]+|XDG_CONFIG_HOME|GH_TOKEN|GH_HOST|GH_CONFIG_DIR|DB_BACKUP_|\.claude/|tools/hooks|gh_issue\.py|"
    + "|".join(re.escape(f) for f in FICHIERS_TOOLS_PROTEGES))

ECHECS_D_ANALYSE = ("commande illisible", "commande trop imbriquée", "analyse impossible")

DOCKER_AVEC_VALEUR = frozenset({"-H", "--host", "-c", "--context", "--config", "-l", "--log-level", "--tlscacert", "--tlscert", "--tlskey"})
COMPOSE_AVEC_VALEUR = frozenset({"-f", "--file", "-p", "--project-name", "--project-directory", "--profile", "--env-file", "--ansi",
                                 "--parallel", "--progress"})
FICHIERS_COMPOSE = ("docker-compose.yml", "docker-compose.yaml", "compose.yaml", "compose.yml")
GH_AVEC_VALEUR = frozenset({"-R", "--repo", "--hostname"})


# --- Contexte -----------------------------------------------------------------------------------------------------------------------------

def _lire_git(args: list, cwd: str, home: str):
    """Lance une lecture de Git avec un environnement réduit à PATH et au vrai HOME : (code, sortie standard)."""
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": home, "LC_ALL": "C"}
    r = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=5, stdin=subprocess.DEVNULL)
    return r.returncode, r.stdout


def dossier_personnel() -> str:
    """Le dossier personnel de l'utilisateur courant, lu dans la base des comptes (pwd.getpwuid), jamais par HOME ni os.path.expanduser : l'appelant
    peut changer HOME, pas la base des comptes (R-20261111-48, DN2-Q1 (a)). Remplace : os.path.expanduser("~") pour la forme des enveloppes.
    Retrait : avec le bac à sable."""
    return pwd.getpwuid(os.getuid()).pw_dir


class Contexte:
    """Ce que la décision lit hors de la commande : dossier courant de l'appel, dossiers du lab, dossier personnel, fichier docker-compose du
    dossier de contenu. `lecteur_git(args, cwd)` rend (code, sortie) : réel par défaut, remplaçable par un test. `controle_configuration` :
    contrôle de la configuration effective de Git (D4) avant une écriture ; les tests de règles pures le coupent."""

    def __init__(self, cwd=None, espace=None, run=None, home=None, compose=None, lecteur_git=None, controle_configuration=True):
        self.home = os.path.realpath(home or os.path.expanduser("~"))   # comme sur main : les règles qui résolvent `~` ou $HOME (revue C3, R-20261111-52)
        # Le dossier de la FORME des enveloppes (D13) : la base des comptes, brute (sans realpath : une seule forme, R-20261111-52 C4), jamais HOME. Un `home` donné (tests) le fixe.
        self.dossier_forme = home or dossier_personnel()
        # Sans espace donné : la racine du code de ce fichier (la garde est lancée depuis la copie de l'espace de travail, D2), jamais un chemin
        # littéral du dossier personnel (garde des chemins de la suite lab_paths).
        self.espace = os.path.realpath(espace or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.run = os.path.realpath(run or os.path.join(os.path.dirname(self.espace), "run"))
        self.cwd = os.path.realpath(cwd) if cwd else self.espace
        self.compose = compose or os.path.join(self.espace, "docker-compose.yml")
        self.lecteur_git = lecteur_git or (lambda args, cwd: _lire_git(args, cwd, self.home))
        self.controle_configuration = controle_configuration


def contexte_par_defaut(cwd=None) -> Contexte:
    """Les dossiers du lab, lus par tools/lab_paths.py depuis le dossier de ce fichier, sans variable d'environnement (elles pourraient les
    déplacer) ; repli sur la disposition habituelle du dossier personnel si la résolution échoue."""
    espace = run = None
    try:
        import lab_paths
        code = lab_paths.code_root(__file__)
        contenu = lab_paths.content_root({}, code)
        espace, run = str(contenu), str(lab_paths.run_tree(contenu, {}))
    except Exception:
        espace = run = None
    return Contexte(cwd=cwd, espace=espace, run=run)


# --- Outils de lecture des mots -----------------------------------------------------------------------------------------------------------

def nettoyer(mot: str) -> str:
    """Le mot sans marqueurs de l'analyseur : une variable jugée bénigne (HOME…) devient `~`, une valeur inconnue reste INCONNU."""
    mot = mot.replace(npm_guard.BENIGNE_NUE + "/x", "~").replace(npm_guard.BENIGNE_QUOTEE + "/x", "~")
    return re.sub(f"(?<!{INCONNU}){npm_guard.QUOTE}", "", mot)   # QUOTE reste après INCONNU : distingue l'expansion entre guillemets de la nue (git clean -e)


def _inconnu_nu(mot: str) -> bool:
    """Le mot contient une expansion illisible nue (INCONNU sans QUOTE derrière) : le découpage peut la couper en plusieurs mots."""
    return re.search(f"{INCONNU}(?!{npm_guard.QUOTE})", mot) is not None


def base(mot: str) -> str:
    return mot.rsplit("/", 1)[-1].lower()


def remplacer_variables(mot: str, home: str) -> str:
    """Mot brut d'une redirection : HOME vaut le dossier personnel, toute autre variable vaut une valeur inconnue (revue Opus, constat 6). Les
    variables d'un mot brut n'ont pas encore été développées par l'analyseur."""
    return VARIABLE_BRUTE.sub(lambda m: home if m.group(1) == "HOME" else INCONNU, mot)


def fin_nomme_protege(cible: str) -> bool:
    """Cible dont le début est inconnu (variable, substitution) mais dont la fin nomme un chemin protégé : `$X/tools/hooks/pre-commit`,
    `$(pwd)/.claude/settings.json` (revue Opus, constat 7). Le texte qui suit la dernière expansion est lu comme fin de chemin, premier composant
    compris (il peut être plus long que ce qu'on voit). Remplace : rien. Retrait : permanent."""
    reste = cible.rsplit(INCONNU, 1)[-1].lstrip(getattr(npm_guard, "QUOTE", "\x05"))
    parties = [p for p in reste.split("/") if p not in ("", ".")]
    if len(parties) >= 2 and parties[-2] == ".claude" and REGLAGES_PARTOUT.fullmatch(parties[-1]):
        return True
    return any(relatif_protege("/".join(parties[k:])) for k in range(len(parties)))


def cible_protegee(cible: str, cwd, ctx) -> bool:
    """La cible d'écriture (mot déjà nettoyé) est-elle protégée ? Une cible inconnue est lue par sa fin."""
    chemin = resoudre(cible, cwd, ctx.home)
    if chemin is None:
        return fin_nomme_protege(cible)
    return protege(chemin, ctx)


def resoudre(chemin: str, cwd, home: str):
    """Chemin absolu, liens suivis, ou None quand le mot est inconnu (variable, substitution)."""
    if INCONNU in chemin:
        return None
    if chemin == "~" or chemin.startswith("~/"):
        chemin = home + chemin[1:]
    if not chemin.startswith("/"):
        if cwd is None:
            return None
        chemin = cwd + "/" + chemin
    return os.path.realpath(chemin)


def dans(chemin: str, racine: str) -> bool:
    return chemin == racine or chemin.startswith(racine.rstrip("/") + "/")


def relatif_protege(rel: str) -> bool:
    return rel in FICHIERS_PROTEGES or any(rel == d or rel.startswith(d + "/") for d in DOSSIERS_PROTEGES)


def protege(chemin: str, ctx: Contexte) -> bool:
    """Le chemin absolu est-il sous la protection du fragment 41 : fichiers de l'espace de travail et de l'arbre de run, réglages partout."""
    for racine in (ctx.espace, ctx.run):
        if dans(chemin, racine) and relatif_protege(os.path.relpath(chemin, racine)):
            return True
    return bool(REGLAGES_PARTOUT.fullmatch(os.path.basename(chemin))) and os.path.basename(os.path.dirname(chemin)) == ".claude"


def positionnels(args: list, avec_valeur=frozenset()) -> list:
    pos, i = [], 0
    while i < len(args):
        a = args[i]
        if a == "--":
            pos.extend(args[i + 1:])
            break
        if a.startswith("-") and a != "-":
            i += 1 if "=" in a else (2 if a in avec_valeur else 1)
        else:
            pos.append(a)
            i += 1
    return pos


def valeur_option(args: list, noms: tuple) -> list:
    """Valeurs de l'option (`-f x`, `--file x`, `--file=x`) dans l'ordre."""
    valeurs = []
    for i, a in enumerate(args):
        for nom in noms:
            if a == nom and i + 1 < len(args):
                valeurs.append(args[i + 1])
            elif a.startswith(nom + "=") and nom.startswith("--"):
                valeurs.append(a.partition("=")[2])
    return valeurs


def _cible_cd(mot: str, cwd, home: str):
    if mot.startswith("~") and mot != "~" and not mot.startswith("~/"):
        return None   # ~utilisateur, ~+, ~- : dossier inconnu
    return resoudre(mot, cwd, home)


def suivre_cwd(prog: str, args: list, cwd, pile: list, home: str):
    """(dossier courant, pile) après `cd`, `pushd` ou `popd` (revue Opus, constat 5). `cd` saute ses options (-P, -L, -e, --) ; sans argument il va au dossier
    personnel ; `cd -`, une cible inconnue, `pushd` sans cible ou en forme +N, `popd` sur une pile vide rendent un dossier inconnu (None). Remplace : le
    `cd` qui prenait son premier argument tel quel. Retrait : permanent."""
    pile = list(pile)
    options, i = [], 0
    while i < len(args) and args[i].startswith("-") and args[i] != "-":
        if args[i] == "--":
            i += 1
            break
        options.append(args[i])
        i += 1
    reste = args[i:]
    if prog == "popd":
        if options or reste or not pile:
            return None, []
        return pile.pop(), pile
    if prog == "pushd":
        if options or not reste or reste[0] == "-" or re.fullmatch(r"[+-]\d+", reste[0]):
            return None, []
        return _cible_cd(reste[0], cwd, home), pile + [cwd]
    if not reste:
        return home, pile
    if reste[0] == "-":
        return None, pile
    return _cible_cd(reste[0], cwd, home), pile


def _normaliser_git(mots: list) -> list:
    """`git-push`, `git-config`, tout binaire `git-<x>` en un mot vaut `git <x>` (revue Opus, constat 2). Remplace : rien. Retrait : permanent."""
    if mots and re.fullmatch(r"git-[a-z][a-z0-9-]*", base(mots[0])):
        return ["git", base(mots[0])[4:]] + mots[1:]
    return mots


def analyser_python(args: list):
    """(module, chaîne, script) lus comme `python` : `-m MODULE`, `-c CHAÎNE`, sinon le premier mot qui n'est pas une option (`-` : l'entrée standard).
    Les trois valent None quand le programme lit son script sur l'entrée standard sans `-`."""
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            return None, None, (args[i + 1] if i + 1 < len(args) else None)
        if a == "-":
            return None, None, "-"
        if not a.startswith("-"):
            return None, None, a
        if a.startswith("--"):
            i += 2 if a == "--check-hash-based-pycs" else 1
            continue
        lettres = a[1:]
        for k, lettre in enumerate(lettres):
            if lettre in "mc":
                valeur = lettres[k + 1:] or (args[i + 1] if i + 1 < len(args) else "")
                return (valeur, None, None) if lettre == "m" else (None, valeur, None)
            if lettre in "WX":
                if not lettres[k + 1:]:
                    i += 1
                break
        i += 1
    return None, None, None


def python_lit_stdin(mots: list) -> bool:
    """La commande simple est `python` sans script ni -c ni -m, ou avec `-` : elle lit son programme sur l'entrée standard."""
    if not mots or not re.fullmatch(r"python[0-9.]*", base(mots[0])):
        return False
    module, chaine, script = analyser_python(mots[1:])
    return module is None and chaine is None and script in (None, "-")


# --- E-enveloppe et E-interprete (design D13) -----------------------------------------------------------------------------------------------

ENVELOPPES_FIGEES = ("ci_local", "gh_issue", "flow_views", "worktree")
PREFIXE_FORME = "/bin/bash --noprofile --norc -p "
SOUS_DOSSIER_FIGE = "/.pmzilla-lab/outils-figes/"   # après le dossier personnel (R-20261111-48 : jamais `~`)
LISTE_BLANCHE = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._/-:,")   # liste blanche de D13 (retouche 1) ; `=` et `~` ont leurs règles
SHELLS_DE_L_ENVELOPPE = frozenset({"bash", "sh", "zsh", "dash", "ksh", "ash", "source", "."})


def _mot_non_quote_litteral(mot: str) -> bool:
    """Mot non quoté de la forme : lettres ASCII, chiffres et `. _ / - : ,` ; `=` jamais en tête ; `~` seulement comme les deux premiers caractères `~/`."""
    if not mot or mot[0] == "=":
        return False
    if "~" in mot and not (mot.startswith("~/") and mot.count("~") == 1):
        return False
    return all(c in LISTE_BLANCHE or c in "=~" for c in mot)


def _mots_litteraux(texte: str):
    """Les mots de `texte` (séparés par une seule espace hors apostrophes), tous littéraux, ou None. Un mot entre apostrophes (R-20261111-35) : ses
    apostrophes sont le premier et le dernier caractère du mot, son contenu (un caractère au moins) est fait de la liste blanche, de `=`, de `~` et de l'espace."""
    mots, i, n = [], 0, len(texte)
    while i < n:
        if texte[i] == "'":
            j = texte.find("'", i + 1)
            if j == -1:
                return None
            contenu = texte[i + 1:j]
            if not contenu or not all(c in LISTE_BLANCHE or c in "=~ " for c in contenu):
                return None
            if j + 1 < n and texte[j + 1] != " ":
                return None
            mots.append(texte[i:j + 1])
            fin = j + 1
        else:
            j = texte.find(" ", i)
            fin = n if j == -1 else j
            if not _mot_non_quote_litteral(texte[i:fin]):
                return None
            mots.append(texte[i:fin])
        if fin < n:
            i = fin + 1
            if i >= n:
                return None   # espace finale : un mot vide
        else:
            i = n
    return mots


def forme_admise(commande: str, home=None) -> bool:
    """La commande est-elle EXACTEMENT la forme admise : `/bin/bash --noprofile --norc -p <dossier personnel>/.pmzilla-lab/outils-figes/<enveloppe>.sh …`,
    seule, en mots littéraux ? `home` est le dossier personnel de la base des comptes (Contexte.dossier_forme, pwd.getpwuid, brut), jamais HOME : le chemin est comparé en
    texte, un autre chemin, un lien, `..`, `/./` et `//` ne lui sont pas égaux, et la forme avec `~` est refusée (R-20261111-48, DN2-Q1 (a) ; remplace :
    la forme avec `~` et l'admission temporaire du chemin absolu de R-20261111-26, qui devient la forme ; retrait : avec le bac à sable). Sans `home`,
    aucune forme n'est admise. Aucun suffixe n'est admis, `; true` compris (tâche 21.2 ; remplace : l'admission temporaire de `; true` de R-20261111-30 ;
    retrait : permanent tant que la forme est unique)."""
    if not commande.startswith(PREFIXE_FORME):
        return False
    chemin, _, reste = commande[len(PREFIXE_FORME):].partition(" ")
    dossiers = [f"{home}{SOUS_DOSSIER_FIGE}"] if home else []
    if chemin not in {f"{d}{nom}.sh" for d in dossiers for nom in ENVELOPPES_FIGEES}:
        return False
    if " " not in commande[len(PREFIXE_FORME):]:
        return True   # l'enveloppe sans argument
    return bool(reste) and _mots_litteraux(reste) is not None


def _enveloppe_exemptee(mot: str) -> bool:
    """`npm_ci.sh` (la cinquième enveloppe, non exclue) dans son dossier habituel, sans `..`, `/./` ni `//` : son appel par `bash` reste permis."""
    return (mot.startswith(("~/", "/")) and mot.endswith("/.pmzilla-lab/outils-figes/npm_ci.sh")
            and not any(m in mot for m in ("/../", "/./", "//")))


def appelle_enveloppe(mots: list) -> bool:
    """La commande simple (mots nettoyés) appelle-t-elle un chemin du dossier des enveloppes figées, comme programme, ou comme script d'un shell, de `.` ou de
    `source` ? Les lanceurs (env, command, nohup, time…) sont suivis par l'analyseur, qui rappelle la commande qu'ils lancent. Lire une enveloppe (cat, grep…)
    n'est pas l'appeler."""
    if not mots:
        return False
    prog, args = mots[0], mots[1:]
    candidats = []
    if "outils-figes/" in prog:
        candidats = [prog]
    elif base(prog) in SHELLS_DE_L_ENVELOPPE:
        if base(prog) in ("source", "."):
            candidats = [a for a in args if a != "--"][:1]
        else:
            _options, i, c_option, _stdin, motif = npm_guard.lire_options_shell(args)
            if motif:
                candidats = list(args)
            elif not c_option:
                candidats = args[i:i + 1]   # le script ; la chaîne de `-c` est analysée par l'analyseur, qui rappelle ses commandes
    return any("outils-figes/" in m and not _enveloppe_exemptee(m) for m in candidats)


def nom_de_definition_interdit(nom: str) -> bool:
    """Un nom de fonction ou d'alias que D13 interdit : `bash`, `/bin/bash`, ou un chemin du dossier des enveloppes (toute graphie)."""
    return nom in ("bash", "/bin/bash") or "outils-figes/" in nom


def definit_un_nom_interdit(jetons: list) -> bool:
    """Les jetons d'un texte définissent une fonction (`nom() …`, `nom ( ) …`, `function nom … {`, tous les noms lus : zsh admet `function a b {`) ou un
    alias (`functions[nom]=…`, `aliases[nom]=…`) dont le nom est interdit (R-20261111-40 point 2). Remplace : la lecture du seul premier nom après `function`.
    Retrait : permanent."""
    for k, (genre, valeur) in enumerate(jetons):
        if genre != "w":
            continue
        if valeur == "function":
            for genre_nom, nom in jetons[k + 1:]:
                if genre_nom != "w" or nom == "{":
                    break
                if nom_de_definition_interdit(nettoyer(nom)):
                    return True
        affectation = re.match(r"(?:functions|aliases|galiases|saliases)\[(.*)\]\+?=", nettoyer(valeur), re.S)
        if affectation and nom_de_definition_interdit(re.sub(r"['\"\\]", "", affectation.group(1))):
            return True
        if k + 2 < len(jetons) and not valeur.endswith("=") and jetons[k + 1] == ("op", "(") and jetons[k + 2] == ("op", ")") \
                and nom_de_definition_interdit(nettoyer(valeur)):
            return True
        # R-20261111-43 point 4 : `aliases=(nom x)`, `functions+=(nom x)` (affectation composée) et `set -A aliases nom x` (`+A` de même) définissent aussi un nom.
        # Chaque mot de la liste est lu (clé ou valeur : le rang n'est pas jugé). Remplace : rien. Retrait : permanent (zsh définit des noms par ces tableaux tant que la session tourne sous zsh).
        if re.fullmatch(r"(?:functions|aliases|galiases|saliases)\+?=", nettoyer(valeur)) and k + 1 < len(jetons) and jetons[k + 1] == ("op", "("):
            if _mots_interdits_jusqu_a_fermeture(jetons[k + 2:]):
                return True
        if nettoyer(valeur) == "set":
            # R-20261112-19 : les options `-e`, `+x`… avant ou après `-A` sont sautées ; le mot non-option qui suit `-A` est le nom du tableau.
            reste = jetons[k + 1:]
            j = 0
            a_option_a = False
            while j < len(reste) and reste[j][0] == "w" and nettoyer(reste[j][1])[:1] in ("-", "+"):
                if "A" in nettoyer(reste[j][1]):
                    a_option_a = True
                if nettoyer(reste[j][1]) in ("-o", "+o"):   # `-o nom` : le mot suivant est l'argument de l'option, sauté aussi
                    j += 1
                j += 1
            if a_option_a and j < len(reste) and reste[j][0] == "w" \
                    and nettoyer(reste[j][1]) in ("functions", "aliases", "galiases", "saliases"):
                if _mots_interdits_jusqu_a_fermeture(reste[j + 1:]):
                    return True
    return False


def _mots_interdits_jusqu_a_fermeture(jetons: list) -> bool:
    """Un mot de `jetons`, jusqu'au premier opérateur (`)`, `;`, `&&`…), porte un nom que D13 interdit."""
    for genre, mot in jetons:
        if genre != "w":
            break
        mot = nettoyer(mot)
        paire = re.fullmatch(r"\[(.*)\]\+?=(.*)", mot, re.S)   # R-20261112-19 : `[clé]=valeur` d'une liste associative
        if paire and (nom_de_definition_interdit(re.sub(r"['\"\\]", "", paire.group(1))) or nom_de_definition_interdit(paire.group(2))):
            return True
        if nom_de_definition_interdit(mot):
            return True
    return False


def alias_interdit(prog: str, args: list) -> bool:
    """`alias [options] nom=valeur …` dont un nom est interdit (options `-g`, `-s`, `--` comprises)."""
    if prog != "alias":
        return False
    apres_options = False
    for a in args:
        if not apres_options and a == "--":
            apres_options = True
        elif not apres_options and a.startswith("-"):
            continue
        elif nom_de_definition_interdit(a.partition("=")[0]):
            return True
    return False


# --- Collecte : le rappel donné à l'analyseur -----------------------------------------------------------------------------------------------

class Collecte:
    """Reçoit de l'analyseur chaque commande simple, chaque affectation et les jetons de chaque texte ; garde la première décision de refus. Toute
    exception d'une règle devient une erreur interne (refus)."""

    def __init__(self, ctx: Contexte):
        self.ctx = ctx
        self.cwd = ctx.cwd
        self.verdict = None
        self.erreur = False
        self.editeur_en_attente = False   # GIT_EDITOR=true posé, pas encore consommé par la commande qui suit (question 16)
        self.path_modifie = False   # PATH affecté plus tôt dans la même commande (R-20261108-07) : jugé quand une commande git qui lance des crochets suit
        self.developer_dir_modifie = False   # DEVELOPER_DIR affecté plus tôt (R-20261108-09), jugé de la même façon
        self.enveloppe_appelee = False   # une enveloppe figée est appelée quelque part dans la commande (D13) : jugée dans `decider`, sur le texte entier
        self.allexport = False   # `set -a`, `bash -a`… vu dans la commande (R-20261111-23)
        self.fonction_definie = False   # une définition de fonction vue dans la commande (R-20261111-23)
        self.pile = []   # pile de pushd / popd
        self.incertain = False   # posé par l'analyseur avant chaque commande : vrai sous xargs et find -exec (arguments ajoutés à l'exécution)
        self.variables_connues = frozenset({"HOME"})   # lu par l'analyseur : seule HOME vaut le dossier personnel, PWD et les autres sont inconnues

    def _garder(self, cle: str):
        if self.verdict is None:
            self.verdict = verdict(cle)

    def commande(self, mots: list, env: dict):
        try:
            nets = _normaliser_git([nettoyer(m) for m in mots])
            attente, self.editeur_en_attente = self.editeur_en_attente, False
            v = regles_commande(nets, self)
            if nets and regle_allexport(base(nets[0]), nets[1:]):   # R-20261111-23
                self.allexport = True
                if self.fonction_definie or _args_definissent_une_fonction(nets[1:]):
                    v = v or "E"
            v = v or self._regle_path(nets)
            if nets and appelle_enveloppe(nets):
                self.enveloppe_appelee = True
            if nets and alias_interdit(base(nets[0]), nets[1:]):
                v = v or "E-interprete"
            if attente and not est_rebase_continue(nets):
                v = v or "A6-variable"   # GIT_EDITOR=true ne précède que `git rebase --continue`
            if v:
                self._garder(v)
        except Exception:
            self.erreur = True

    def _regle_path(self, nets: list):
        """R-20261108-07. Remplace : rien. Retrait : permanent (le bac à sable limite ce qu'un programme atteint, pas quel programme tourne).
        PATH modifié (affectation, `env PATH=…`, `export PATH=…`, `read PATH`) puis une commande git qui n'est pas une lecture pure : git lance ses
        crochets et ses sous-programmes par PATH. Les commandes sans git, et git en lecture, ne sont pas visées."""
        if not nets:
            return None
        prog = base(nets[0])
        poses = [n.partition("=")[0].rstrip("+").split("[")[0] for n in _noms_poses(prog, nets[1:])]
        if any(n in NOMS_PATH for n in poses):
            self.path_modifie = True
        if any(n in NOMS_DEVELOPER_DIR for n in poses):   # R-20261108-09 : DEVELOPER_DIR est jugé comme PATH. Remplace : rien. Retrait : permanent.
            self.developer_dir_modifie = True
        if (self.path_modifie or self.developer_dir_modifie) and prog == "git":
            sous = decouper_git(nets[1:])[1]
            if sous not in GIT_LECTURE or sous == "fetch":   # fetch met à jour des références : reference-transaction tourne
                return "E-path" if self.path_modifie else "E-developer-dir"
        return None

    def affectation(self, nom: str, valeur: str):
        try:
            if nom in NOMS_PATH:
                self.path_modifie = True
                return
            if nom in NOMS_DEVELOPER_DIR:   # R-20261108-09. Remplace : rien. Retrait : permanent.
                self.developer_dir_modifie = True
                return
            if nom == "GIT_EDITOR":
                # R-20261107-27 point 12, R-20261108-01 question 16 : GIT_EDITOR=true seul est admis, et seulement devant `git rebase --continue` ; toute
                # autre valeur est refusée. Remplace : le refus de toute variable GIT_* pour cette seule variable. Retrait : permanent.
                if nettoyer(valeur) == "true":
                    self.editeur_en_attente = True
                else:
                    self._garder("A6-variable")
                return
            v = regle_affectation(nom)
            if v:
                self._garder(v)
        except Exception:
            self.erreur = True

    def jetons(self, jetons: list):
        try:
            if definit_un_nom_interdit(jetons):   # R-20261111-33 : où qu'elle soit dans la commande
                self._garder("E-interprete")
            if definit_une_fonction(jetons):   # R-20261111-23 : jugé avec `set -a` / `bash -a` vus dans la même commande, quel que soit l'ordre des rappels
                self.fonction_definie = True
                if self.allexport:
                    self._garder("E")
            v = regle_redirections(jetons, self)
            if v:
                self._garder(v)
        except Exception:
            self.erreur = True


# --- Règles ---------------------------------------------------------------------------------------------------------------------------------

def regle_affectation(nom: str):
    """Variables posées par une affectation, `export`, `declare`, `typeset` ou `env NOM=valeur` : toute la commande est refusée, quel que soit le
    programme qui suit (A6 git, B gh, E réglages)."""
    if nom.startswith("GIT_") or nom in VARIABLES_GIT:
        return "A6-variable"
    if nom in VARIABLES_GH:
        return "B-variable"
    if nom in VARIABLES_REGLAGE or nom.startswith(PREFIXES_REGLAGE):
        return "E"
    return None


def est_rebase_continue(mots: list) -> bool:
    """La commande simple (mots nettoyés) est-elle `git [options globales] rebase … --continue` ? Seule commande devant laquelle GIT_EDITOR=true passe."""
    if not mots or base(mots[0]) != "git":
        return False
    _, sous, suite = decouper_git(mots[1:])
    return sous == "rebase" and "--continue" in suite


def _ecrit_vers_protege(cibles: list, c: Collecte) -> bool:
    return any(cible_protegee(cible, c.cwd, c.ctx) for cible in cibles)


ECRITURES_REDIRECTION = (">", ">>", ">|", "&>", "<>")   # `<>` ouvre en lecture et en écriture et crée le fichier ; `&>>` arrive en deux jetons : `&>` puis `>`


def regle_redirections(jetons: list, c: Collecte):
    """Classe C : `>`, `>>`, `>|`, `&>`, `&>>`, `<>` et `>&fichier` (cible non numérique) vers un chemin protégé. Les variables du mot brut sont remplacées
    avant la résolution (HOME seulement, le reste inconnu ; une cible inconnue est lue par sa fin). Un `cd`, `pushd` ou `popd` d'une commande précédente de
    la même liste déplace le dossier courant. C3 : `python` qui lit son programme sur l'entrée standard depuis gh_issue.py (`< gh_issue.py`, ou après un
    tube dont la commande nomme gh_issue.py). Remplace : la lecture des seuls `>`, `>>`, `>|` et `&>` sans variables. Retrait : permanent."""
    cwd, pile = c.cwd, list(c.pile)
    mots, cibles, entrees, mode = [], [], [], None   # mode : "ecrit", "dup", "entree" ou "saute" pour le mot qui suit une redirection
    mention_avant, tube_avant = False, False
    for genre, valeur in list(jetons) + [("op", ";")]:
        if genre == "redir":
            if valeur in ECRITURES_REDIRECTION:
                mode = "ecrit"
            elif valeur == ">&":
                mode = "dup"
            elif valeur == "<":
                mode = "entree"
            else:
                mode = "saute"
        elif genre == "w":
            mot = nettoyer(remplacer_variables(valeur, c.ctx.home))
            if mode == "ecrit" or (mode == "dup" and not re.fullmatch(r"[0-9]+-?|-", mot)):
                cibles.append(mot)
            elif mode == "entree":
                entrees.append(mot)
            elif mode is None:
                mots.append(mot)
            mode = None
        else:   # séparateur : la commande est complète
            for cible in cibles:
                if cible_protegee(cible, cwd, c.ctx):
                    return "C"
            if python_lit_stdin(mots) and (any(base(e) == "gh_issue.py" for e in entrees) or (tube_avant and mention_avant)):
                return "C3"
            mention_avant = (mention_avant and tube_avant) or any(base(m) == "gh_issue.py" for m in mots)
            tube_avant = valeur in ("|", "|&")
            if mots and base(mots[0]) in ("cd", "pushd", "popd"):
                cwd, pile = suivre_cwd(base(mots[0]), mots[1:], cwd, pile, c.ctx.home)
            mots, cibles, entrees, mode = [], [], [], None
    return None


MOTIF_REGLAGE_GIT = re.compile(r"hookspath", re.IGNORECASE)


def regle_texte_de_reglage(mots: list):
    """`core.hooksPath` (toutes casses) ou `GIT_CONFIG_` nommés dans un mot de la commande, quel que soit le programme : le fragment 39 les refuse où que le
    texte figure (R-20261108-01, question 15 a). Sauf `git config` en lecture, que la garde elle-même fait (D4) et dont l'écriture est déjà refusée plus
    haut. Remplace : les deux familles de règles `*hooksPath*` et `*GIT_CONFIG_*` du fragment 39. Retrait : permanent."""
    if not any(MOTIF_REGLAGE_GIT.search(m) or "GIT_CONFIG_" in m for m in mots):
        return None
    if base(mots[0]) == "git" and decouper_git(mots[1:])[1] == "config":
        return None
    return "A6-texte"


def regles_commande(mots: list, c: Collecte):
    """La clé du premier refus pour une commande simple (mots déjà nettoyés), ou None : les règles de la commande, puis le texte de réglage nommé."""
    mots = _normaliser_git(mots)
    return _regles_commande(mots, c) or (regle_texte_de_reglage(mots) if mots else None)


XCRUN_AVEC_VALEUR = frozenset({"-sdk", "--sdk", "-toolchain", "--toolchain"})
NOMS_PATH = frozenset({"PATH", "path"})   # zsh lie le tableau `path` à PATH : `path=(/x)` et `path+=(/x)` changent PATH (R-20261108-07). Remplace : rien. Retrait : permanent.
NOMS_DEVELOPER_DIR = frozenset({"DEVELOPER_DIR"})   # R-20261108-09. Remplace : rien. Retrait : permanent.
COMMANDES_QUI_POSENT = frozenset({"export", "declare", "typeset", "local", "readonly"})
COMMANDES_QUI_LISENT = frozenset({"read", "mapfile", "readarray"})


def regle_variable_posee(prog: str, args: list):
    """Une variable surveillée posée sans `=` puis exportée : `export NOM`, `declare NOM`, `typeset`, `local`, `readonly`, `read NOM`, `mapfile NOM`,
    `printf -v NOM`, `for NOM in …`, `select NOM in …` (revue Opus, constat 9). Le nom est jugé comme celui d'une affectation. Remplace : rien (les
    affectations avec `=` sont jugées par regle_affectation). Retrait : permanent."""
    for nom in _noms_poses(prog, args):
        v = regle_affectation(nom.partition("=")[0].rstrip("+").split("[")[0])
        if v:
            return v
    return None


def regle_fonction_exportee(prog: str, args: list) -> bool:
    """R-20261111-16. Une fonction exportée passe aux programmes lancés ensuite et y remplace une commande appelée par son nom : `export -f` (toute
    grappe d'options qui contient f, `-nf` compris), `declare` ou `typeset` avec les options f et x, ensemble ou séparées, et `env` suivi d'un argument
    BASH_FUNC_… (la forme réelle, `BASH_FUNC_nom%%=() { … }`, que l'analyseur ne lit pas comme une affectation à cause des `%%`). Remplace : rien.
    Retrait : permanent tant que les enveloppes figées sont exclues du bac à sable.
    R-20261111-23 : `-F` compte comme `-f` pour declare et typeset (`-Fx`, `-xF`, `-F -x`) ; `env` : BASH_FUNC_ dans n'importe quel argument (`-S'BASH_FUNC_x%%=…'`
    collé, ou pas en tête de la chaîne) ; un nom de commande qui commence par BASH_FUNC_. Remplace : rien. Retrait : permanent (même condition)."""
    if prog.startswith(PREFIXES_REGLAGE[1].lower()):
        return True   # prog vient de base(), en minuscules
    if prog == "env":
        return any(PREFIXES_REGLAGE[1] in a for a in args)
    if prog not in ("export", "declare", "typeset"):
        return False
    lettres = "".join(a[1:] for a in args if a.startswith("-") and not a.startswith("--") and len(a) > 1)
    if prog == "export":
        return "f" in lettres
    return ("f" in lettres or "F" in lettres) and "x" in lettres


SHELLS_A_OPTION_A = frozenset({"bash", "sh", "zsh", "dash", "ksh", "ash"})   # `ash` : R-20261111-24 (comme INTERPRETES de la garde npm). Remplace : rien. Retrait : permanent


def regle_allexport(prog: str, args: list) -> bool:
    """R-20261111-23. `set -a`, `set -o allexport`, une grappe qui contient a (`set -ea`, `set -ae`), `bash -a`, `bash -o allexport` : tout ce qui est défini
    ensuite est exporté, les fonctions comprises. Seul, `set -a; FOO=x` reste permis ; le refus tombe quand une définition de fonction est aussi dans la
    commande (Collecte, quel que soit l'ordre). Remplace : rien. Retrait : permanent tant que les enveloppes figées sont exclues du bac à sable."""
    if prog != "set" and prog not in SHELLS_A_OPTION_A:
        return False
    # La lecture des options est celle de la garde npm (source unique : npm_guard.lire_options_shell, importée, pas copiée ; accès direct, une absence
    # donne « erreur-interne », échec fermé) : options longues avec ou sans valeur, grappes avec o et O qui prennent leur valeur, options en +.
    options, _suite, _c, _stdin, motif = npm_guard.lire_options_shell(args)
    # Expansion non résolue dans une option : peut valoir `a`. R-20261111-24 : une option longue inconnue (qui peut prendre une valeur) est comptée de même.
    # Refus seulement avec une définition de fonction. Remplace : le non-compte de l'option longue inconnue. Retrait : permanent (même condition).
    if motif in (npm_guard.MOTIF_SHELL_NON_RESOLUE, npm_guard.MOTIF_SHELL_LONGUE_INCONNUE):
        return True
    for signe, lettre, valeur in options:
        if signe != "-":
            continue   # `+a` retire allexport, `+o allexport` aussi
        if lettre == "a":
            return True
        if lettre == "o" and valeur is not None and (valeur == "allexport" or INCONNU in valeur):
            return True
        # R-20261111-24 : `set -o -a` : sans nom, `-o` n'a pas pris `-a` (bash lit l'argument suivant comme une option quand il commence par `-`), qui s'applique.
        if lettre == "o" and valeur is not None and valeur.startswith("-") and len(valeur) > 1 and "a" in valeur[1:]:
            return True
    return False


def _args_definissent_une_fonction(args: list) -> bool:
    """R-20261111-24. Un argument du shell (la chaîne de `-c` en particulier) définit une fonction. L'analyseur de la garde npm s'arrête sur une option longue
    inconnue ou non résolue sans lire la chaîne de `-c` : la garde la découpe ici elle-même. Remplace : rien. Retrait : permanent (même condition)."""
    for a in args:
        try:
            if definit_une_fonction(npm_guard.decouper(a, [])):
                return True
        except Exception:
            continue
    return False


def definit_une_fonction(jetons: list) -> bool:
    """R-20261111-23. Les jetons d'un texte contiennent une définition de fonction : `nom(){`, `nom ( ) {` ou `function nom`. Un mot qui finit par « = »
    suivi de `(` est un tableau (`a=(x y)`), pas une fonction. Remplace : rien. Retrait : permanent (même condition)."""
    for k, (genre, valeur) in enumerate(jetons):
        if genre == "w" and valeur == "function":
            return True
        if genre == "w" and k + 2 < len(jetons) and not valeur.endswith("=") and jetons[k + 1] == ("op", "(") and jetons[k + 2] == ("op", ")"):
            return True
    return False


def _noms_poses(prog: str, args: list) -> list:
    """Les noms de variables que la commande pose sans `=` (voir regle_variable_posee), non jugés."""
    noms = []
    if prog in COMMANDES_QUI_POSENT:
        noms = [a for a in args if not a.startswith("-") and "=" not in a]   # avec « = » : la garde des affectations (GIT_EDITOR=true compris)
    elif prog in COMMANDES_QUI_LISENT:
        noms = list(args)
    elif prog in ("for", "select"):
        noms = args[:1]
    elif prog == "printf":
        for i, a in enumerate(args):
            if a == "-v" and i + 1 < len(args):
                noms.append(args[i + 1])
            elif a.startswith("-v") and len(a) > 2:
                noms.append(a[2:])
    return noms


def _regles_commande(mots: list, c: Collecte):
    """Les règles de la commande simple. Suit `cd`, `pushd` et `popd` pour les commandes suivantes."""
    if not mots:
        return None
    if any(SKILL_EN_QUARANTAINE in m for m in mots):
        return "H"
    prog = base(mots[0])
    args = mots[1:]
    if prog in ("cd", "pushd", "popd"):
        c.cwd, c.pile = suivre_cwd(prog, args, c.cwd, c.pile, c.ctx.home)
        return None
    v = regle_variable_posee(prog, args)
    if v:
        return v
    if regle_fonction_exportee(prog, args):
        return "E"
    if prog == "git":
        return regle_git(args, c)
    if prog == "security" or (prog == "xcrun" and any(base(m) == "security" for m in args)):
        return "A4"
    if prog == "xcrun":
        # xcrun lance la commande qui suit ses options, comme env (revue Opus, constat 3). Remplace : le seul cas `xcrun security`. Retrait : permanent.
        i = 0
        while i < len(args) and args[i].startswith("-") and args[i] != "-":
            i += 2 if args[i] in XCRUN_AVEC_VALEUR else 1
        return regles_commande(args[i:], c) if i < len(args) else None
    if prog == "gh":
        return regle_gh(args)
    v = regle_gh_issue(prog, mots, c)
    if v:
        return v
    v = regle_scripts_reserves(prog, args)
    if v:
        return v
    if prog in ("docker", "docker-compose", "colima", "limactl"):
        return regle_docker(prog, args, c)
    if prog == "unset" and any(a in VARIABLES_REGLAGE or a.startswith(PREFIXES_REGLAGE) for a in args):
        return "E"
    if prog == "env" and _env_retire_reglage(args):
        return "E"
    return regle_ecritures(prog, args, c)


# --- A4/A5 : scripts et launchctl ---------------------------------------------------------------------------------------------------------

def regle_scripts_reserves(prog: str, args: list):
    if prog in SCRIPTS_RESERVES:
        return "A5"
    if prog in INTERPRETES_DE_SCRIPT:
        suite = positionnels([a for a in args if a != "-c"])
        if suite and base(suite[0]) in SCRIPTS_RESERVES:
            return "A5"
    if prog == "launchctl" and any(e in a for a in args for e in ETIQUETTES_LAUNCHCTL):
        return "A5"
    if prog == "launchctl" and positionnels(args)[:1] and positionnels(args)[0] in ("submit", "asuser", "bsexec"):
        return "A5"   # lancent une commande arbitraire (revue Opus, constat 3). Remplace : rien. Retrait : permanent.
    return None


def _env_retire_reglage(args: list) -> bool:
    for i, a in enumerate(args):
        nom = None
        if a in ("-u", "--unset") and i + 1 < len(args):
            nom = args[i + 1]
        elif a.startswith("--unset="):
            nom = a.partition("=")[2]
        elif a.startswith("-u") and len(a) > 2 and not a.startswith("--"):
            nom = a[2:]
        if nom and (nom in VARIABLES_REGLAGE or nom.startswith(PREFIXES_REGLAGE)):
            return True
    return False


# --- B : gh -------------------------------------------------------------------------------------------------------------------------------

def regle_gh(args: list):
    """Liste fermée (Q7) : `gh issue view`, `gh issue list`, `gh --version`. Les options sont lues où qu'elles soient."""
    pos = positionnels(args, GH_AVEC_VALEUR)
    if not pos:
        return None if args == ["--version"] else "B"
    if len(pos) >= 2 and pos[0] == "issue" and pos[1] in ("view", "list"):
        return None
    return "B"


def regle_gh_issue(prog: str, mots: list, c: Collecte):
    """C3 : tools/gh_issue.py se LANCE (exécution directe, ou comme premier argument de python) depuis la copie de l'espace de travail seulement ; le
    lire (cat, grep, git add…) reste permis. Remplace : rien. Retrait : quand la copie figée de gh_issue du niveau 2 (K3) est posée."""
    script = None
    if prog == "gh_issue.py":
        script = mots[0]
    elif re.fullmatch(r"python[0-9.]*", prog):
        module, _, premier = analyser_python(mots[1:])
        if module is not None and module.split(".")[0] == "gh_issue":
            # Remplace : rien. Retrait : permanent.
            return "C3"   # `python3 -m gh_issue` charge le module du dossier courant, quel qu'il soit (revue Opus, constat 10)
        if premier is not None and base(premier) == "gh_issue.py":
            script = premier
    if script is None:
        return None
    chemin = resoudre(script, c.cwd, c.ctx.home)
    return "C3" if chemin is None or chemin != os.path.join(c.ctx.espace, "tools", "gh_issue.py") else None


# --- C : écritures du shell ---------------------------------------------------------------------------------------------------------------

def regle_ecritures(prog: str, args: list, c: Collecte):
    """Classe C (Q10) : tee, cp, mv, rm, ln, sed -i, touch, chmod et dd of= vers un chemin protégé. Remplace : rien. Retrait : quand le niveau 2 pose
    `denyWrite` sur les mêmes chemins et que sa sonde est verte deux semaines."""
    avec_valeur = {"cp": {"-t", "--target-directory", "-S", "--suffix"}, "mv": {"-t", "--target-directory", "-S", "--suffix"},
                   "install": {"-t", "--target-directory", "-m", "-o", "-g"}, "ln": {"-t", "--target-directory", "-S", "--suffix"},
                   "touch": {"-r", "-t", "-d", "-A"}, "sed": {"-e", "-f", "--expression", "--file"}, "truncate": {"-s", "-r"}}
    pos = positionnels(args, frozenset(avec_valeur.get(prog, ())))
    cibles = []
    if prog == "tee":
        cibles = pos
    elif prog in ("cp", "install", "ln"):
        cibles = valeur_option(args, ("-t", "--target-directory")) or pos[-1:]
    elif prog == "mv":
        cibles = valeur_option(args, ("-t", "--target-directory")) + pos
    elif prog in ("rm", "rmdir", "unlink", "touch", "truncate"):
        cibles = pos
    elif prog in ("chmod", "chown", "chgrp"):
        cibles = pos[1:]
    elif prog == "sed":
        en_place = any(a == "--in-place" or a.startswith("--in-place=") or (a.startswith("-") and not a.startswith("--") and "i" in a)
                       for a in args)
        if en_place:
            cibles = pos if any(a in ("-e", "-f") for a in args) else pos[1:]
    elif prog == "dd":
        cibles = [a[3:] for a in args if a.startswith("of=")]
    return "C" if cibles and _ecrit_vers_protege(cibles, c) else None


# --- G : docker -----------------------------------------------------------------------------------------------------------------------------

def nom_du_projet(fichier: str):
    """Nom de projet du fichier docker-compose (clé `name:` de premier niveau), ou None. Lu à chaque appel, jamais copié dans la garde."""
    try:
        with open(fichier, encoding="utf-8") as f:
            texte = f.read()
    except OSError:
        return None
    m = re.search(r"(?m)^name:\s*([A-Za-z0-9._-]+)", texte)
    return m.group(1) if m else None


LETTRES_DOCKER_AVEC_VALEUR = "acehlmpuw"   # options courtes de docker run dont la valeur est la fin de l'amas ou le mot suivant (-v aussi)


def _amas_avec_v(a: str) -> bool:
    """Le mot est un groupe d'options courtes où la lettre v vient avant toute lettre qui prend une valeur : `-v`, `-itv`, `-v/:/h`, `-itv/:/h` (revue Opus,
    constat 11). Remplace : la seule forme `-v` collée à un deux-points. Retrait : permanent."""
    if not a.startswith("-") or a.startswith("--") or len(a) < 2:
        return False
    for lettre in a[1:]:
        if lettre == "v":
            return True
        if lettre in LETTRES_DOCKER_AVEC_VALEUR or not lettre.isalpha():
            return False
    return False


def regle_docker(prog: str, args: list, c: Collecte):
    """Classe G (Q6, A-29, A-50). Refusés : docker run et create avec un montage (volume nommé, dossier de l'hôte, socket de docker compris : plus strict
    que le design, qui ne visait que le volume de la vraie base et les montages de l'hôte, pour que le nom d'un volume ne puisse pas être détourné),
    toute commande compose visant le projet du lab, la destruction (volume rm et prune, system prune --volumes, compose down -v, colima delete,
    limactl delete). Remplace : rien (fragment 10 pour psql et sauvegardes). Retrait : quand le niveau 2 bloque le socket de docker, deux semaines de
    sonde verte."""
    if c.incertain:
        return "G"   # sous xargs ou find -exec, les arguments sont ajoutés à l'exécution : sous-commande et options illisibles (revue Opus, constat 1)
    if prog in ("colima", "limactl"):
        pos = positionnels(args)
        return "G" if pos[:1] == ["delete"] else None
    if prog == "docker-compose":
        return _regle_compose(args, c)
    pos = positionnels(args, DOCKER_AVEC_VALEUR)
    if not pos:
        return None
    sous, suite = pos[0], pos[1:]
    if INCONNU in sous:
        # Remplace : rien. Retrait : permanent.
        return "G"   # sous-commande inconnue (variable, substitution) : `docker $SOUS -v /:/h …`
    if sous == "compose":
        reste = args[args.index("compose") + 1:] if "compose" in args else []
        return _regle_compose(reste, c)
    if sous == "container" and suite[:1]:
        sous, suite = suite[0], suite[1:]
    if sous in ("run", "create"):
        if any(a in ("--volume", "--mount", "--volumes-from") or a.startswith(("--volume=", "--mount=", "--volumes-from=")) or _amas_avec_v(a)
               for a in args):
            return "G"
        if any("docker.sock" in a for a in args):
            return "G"
    if sous == "volume" and suite[:1] and suite[0] in ("rm", "remove", "prune"):
        return "G"
    if sous == "system" and suite[:1] == ["prune"] and "--volumes" in args:
        return "G"
    return None


def _regle_compose(args: list, c: Collecte):
    sous = (positionnels(args, COMPOSE_AVEC_VALEUR) or [""])[0]
    if sous == "down" and any(a in ("-v", "--volumes") for a in args):
        return "G"
    projet = nom_du_projet(c.ctx.compose)
    if projet is None:
        return "G"   # fichier du lab illisible : fermé par défaut
    noms = valeur_option(args, ("-p", "--project-name"))
    if noms:
        return "G" if any(n == projet for n in noms) else None
    if c.cwd is None or any(INCONNU in a for a in args):
        return "G"
    dossiers = valeur_option(args, ("--project-directory",))
    fichiers = valeur_option(args, ("-f", "--file"))
    if fichiers:
        chemin = resoudre(fichiers[0], dossiers[0] if dossiers else c.cwd, c.ctx.home)
        if chemin is None:
            return "G"
        nom = nom_du_projet(chemin) or os.path.basename(os.path.dirname(chemin))
    else:
        dossier = resoudre(dossiers[0], c.cwd, c.ctx.home) if dossiers else c.cwd
        if dossier is None:
            return "G"
        nom = None
        for candidat in FICHIERS_COMPOSE:
            nom = nom_du_projet(os.path.join(dossier, candidat))
            if nom:
                break
        nom = nom or os.path.basename(dossier)
    return "G" if nom == projet else None


# --- Git ------------------------------------------------------------------------------------------------------------------------------------

def _reglage_admis(cle: str) -> bool:
    cle = cle.lower()
    return cle in REGLAGES_ADMIS or cle.startswith(PREFIXES_REGLAGES_ADMIS)


def decouper_git(args: list):
    """(options globales normalisées, sous-commande, mots suivants). Les options globales avant la sous-commande sont retirées ; -C, --git-dir et
    --work-tree sont gardées pour connaître le dépôt visé. Une option globale inconnue donne la sous-commande « ? » (refus A2)."""
    globales = {"C": [], "c": [], "git-dir": None, "work-tree": None, "config-env": False}
    i = 0
    while i < len(args):
        a = args[i]
        if not a.startswith("-") or a == "-":
            return globales, a, args[i + 1:]
        nom, egal, valeur = a.partition("=")
        if nom in GLOBALES_AVEC_VALEUR:
            if not egal:
                if i + 1 >= len(args):
                    return globales, "?", []
                valeur = args[i + 1]
                i += 1
            if nom == "-C":
                globales["C"].append(valeur)
            elif nom == "-c":
                globales["c"].append(valeur)
            elif nom == "--config-env":
                globales["config-env"] = True
            elif nom in ("--git-dir", "--work-tree"):
                globales[nom[2:]] = valeur
        elif nom in GLOBALES_SANS_VALEUR:
            pass
        else:
            return globales, "?", []
        i += 1
    return globales, None, []


LETTRES_AVEC_VALEUR_COMMIT = "mFCct"   # la valeur est la fin de l'amas ou, si la lettre est la dernière, le mot suivant
LETTRES_AVEC_VALEUR_ATTACHEE_COMMIT = "Su"   # la valeur, facultative, est toujours attachée : le mot suivant reste une option


def _commit_saute_les_crochets(mots: list) -> bool:
    """`-n` seul ou dans un amas d'options courtes (`-anm`) ; une lettre qui prend une valeur ferme l'amas."""
    precedent_valeur = False
    for a in mots:
        if a == "--":
            break
        if precedent_valeur:
            precedent_valeur = False
            continue
        if re.fullmatch(r"-[A-Za-z0-9]+", a):
            for k, lettre in enumerate(a[1:]):
                if lettre == "n":
                    return True
                if lettre in LETTRES_AVEC_VALEUR_COMMIT:
                    precedent_valeur = k == len(a) - 2
                    break
                if lettre in LETTRES_AVEC_VALEUR_ATTACHEE_COMMIT:
                    break
    return False


def _config_en_ecriture(mots: list) -> bool:
    ecriture = {"--add", "--unset", "--unset-all", "--replace-all", "--rename-section", "--remove-section", "--edit", "-e"}
    lecture = {"--get", "--get-all", "--get-regexp", "--get-urlmatch", "--list", "-l", "--show-origin", "--show-scope", "--name-only"}
    if any(a in ecriture for a in mots):
        return True
    pos = positionnels(mots, frozenset({"--file", "-f", "--blob", "--default", "--type", "-t", "--file="}))
    if pos[:1] and pos[0] in ("set", "unset", "edit", "rename-section", "remove-section"):
        return True
    if pos[:1] and pos[0] in ("get", "list"):
        return False
    if any(a in lecture for a in mots):
        return False
    return len(pos) >= 2


LONGUES_BRANCH = (
    "--abbrev", "--all", "--color", "--column", "--contains", "--copy", "--create-reflog", "--delete", "--edit-description", "--force", "--format",
    "--ignore-case", "--list", "--merged", "--move", "--no-abbrev", "--no-color", "--no-column", "--no-contains", "--no-merged", "--no-track",
    "--omit-empty", "--points-at", "--quiet", "--recurse-submodules", "--remotes", "--set-upstream", "--set-upstream-to", "--show-current", "--sort",
    "--track", "--unset-upstream", "--verbose",
)


def _canonique_branch(a: str) -> str:
    """Une option longue de `git branch` abrégée (`--mov`, `--forc`, `--cop`) rendue en entier quand le préfixe est sans ambiguïté, comme Git la lit (revue
    Opus, constat 8). Remplace : la lecture des seules formes entières. Retrait : permanent."""
    if not a.startswith("--") or a == "--":
        return a
    nom, egal, valeur = a.partition("=")
    if nom in LONGUES_BRANCH:
        return a
    candidates = [o for o in LONGUES_BRANCH if o.startswith(nom)]
    return candidates[0] + egal + valeur if len(candidates) == 1 else a


def _branche_ecrit(mots: list) -> bool:
    mots = [_canonique_branch(a) for a in mots]
    ecriture = ("-d", "-D", "-m", "-M", "-c", "-C", "-f", "-u", "-t", "--delete", "--move", "--copy", "--force", "--set-upstream-to",
                "--unset-upstream", "--edit-description", "--track", "--no-track", "--set-upstream")
    if any(a == o or (o.startswith("--") and a.startswith(o + "=")) for a in mots for o in ecriture):
        return True
    listage = ("--list", "-l", "--show-current", "--merged", "--no-merged", "--contains", "--no-contains", "--points-at")
    if any(a in listage or a.startswith(tuple(o + "=" for o in listage)) for a in mots):
        return False
    return bool(positionnels(mots, frozenset({"--sort", "--format", "--abbrev", "--color", "--column"})))


def _branche_force_main(mots: list) -> bool:
    """`git branch` avec une écriture forcée (-M, -C, ou -m / -c / --move / --copy avec -f / --force, amas d'options courtes compris) et un mot qui commence
    par `main` ou `refs/heads/main`, dans n'importe quel ordre (fragment 39). Remplace : les règles `git branch … main` du fragment 39. Retrait : permanent."""
    lettres, longues, noms = set(), set(), []
    for a in (_canonique_branch(m) for m in mots):
        if a == "--":
            continue
        if a.startswith("--"):
            longues.add(a.partition("=")[0])
        elif re.fullmatch(r"-[A-Za-z]+", a):
            lettres.update(a[1:])
        elif not a.startswith("-"):
            noms.append(a)
    deplace_ou_copie = bool(lettres & {"m", "c"}) or bool(longues & {"--move", "--copy"})
    force = "f" in lettres or "--force" in longues
    ecriture_forcee = bool(lettres & {"M", "C"}) or (deplace_ou_copie and force)
    if ecriture_forcee and any(INCONNU in n for n in noms):
        return True   # cible inconnue (variable, substitution) : peut être main (revue Opus, constat 8)
    return ecriture_forcee and any(n.lower().startswith(("main", "refs/heads/main", "heads/main")) for n in noms)   # le disque du Mac ne distingue pas Main de main


def _texte_branche_main(args: list) -> bool:
    """La même forme écrite dans un texte d'un mot de la commande git (`git commit -m "x && git branch -M x main"`) : le fragment 39 refuse la chaîne où
    qu'elle figure. Remplace : les règles `*& git branch …`, `*; git branch …` du fragment 39. Retrait : permanent."""
    for a in args:
        for m in re.finditer(r"\bgit\b.*?\bbranch\b(.*)", a, re.DOTALL):
            if _branche_force_main([t for t in re.split(r"[\s;&|()]+", m.group(1)) if t]):
                return True
    return False


def _arbre_vise(globales: dict, c: Collecte):
    """Le dossier de travail visé par la commande git, ou None quand il est inconnu."""
    cwd = c.cwd
    for chemin in globales["C"]:
        cwd = resoudre(chemin, cwd, c.ctx.home)
        if cwd is None:
            return None
    if globales["work-tree"]:
        return resoudre(globales["work-tree"], cwd, c.ctx.home)
    return cwd


def _ecrit_l_arbre(sous: str, mots: list, arbre: str) -> bool:
    pos = positionnels(mots, frozenset({"-b", "-B", "--orphan"}))
    if sous in ("restore", "apply"):
        return True
    if sous == "stash":
        return bool(pos) and pos[0] in ("pop", "apply")
    if sous == "reset":
        # Remplace : la lecture de --hard en toutes lettres. Retrait : permanent.
        return any(a.startswith("--") and _prefixe_long(a.partition("=")[0], "--hard", 3) for a in mots)   # Git lit `--h` comme `--hard`
    if sous == "checkout":
        if any(a in ("-b", "-B", "--orphan") for a in mots):
            return False
        return "--" in mots or len(pos) >= 2 or any(p.startswith(".") or os.path.exists(os.path.join(arbre, p)) for p in pos)
    return False


def verifier_configuration(arbre, ctx: Contexte):
    """Configuration effective de Git avant une écriture (D4) : `git config --get-all core.hooksPath` lu par Git lui-même (tous les niveaux, include.path
    compris) puis les six liens des crochets du dossier Git commun. Un échec de lecture lève : refus. Remplace : rien. Retrait : permanent, les crochets
    tournent hors du bac à sable."""
    if not arbre or not os.path.isdir(arbre):
        return None
    code, sortie = ctx.lecteur_git(["config", "--get-all", "core.hooksPath"], arbre)
    if code not in (0, 1):
        raise RuntimeError("lecture de la configuration impossible")
    if code == 0 and sortie.strip():
        return "A6-hookspath"
    code, sortie = ctx.lecteur_git(["rev-parse", "--path-format=absolute", "--git-common-dir"], arbre)
    if code != 0 or not sortie.strip():
        return None   # pas un dépôt : l'écriture échouera d'elle-même
    commun = sortie.strip()
    for nom in CROCHETS:
        lien = os.path.join(commun, "hooks", nom)
        if not (os.path.islink(lien) and os.readlink(lien) == f"../../tools/hooks/{nom}"):
            return "A6-liens"
    return None


SOUS_COMMANDES_AVEC_EXEC = frozenset({"rebase", "push", "fetch", "ls-remote", "archive", "clone", "pull"})


def _prefixe_long(nom: str, complet: str, mini: int) -> bool:
    """`nom` est une abréviation de l'option longue `complet`, d'au moins `mini` caractères (Git accepte tout préfixe sans ambiguïté)."""
    return len(nom) >= mini and complet.startswith(nom)


def _option_qui_lance(sous: str, args: list, mots: list) -> bool:
    """Option de git qui lance une commande donnée par le texte : `rebase --exec` et `-x`, `grep -O` et `--open-files-in-pager`, `--upload-pack`,
    `--receive-pack`, `--exec` (fetch, push, ls-remote, archive, clone), et `--exec-path=<dossier>` (git lance ses programmes depuis ce dossier). Formes
    collée et séparée, abréviations sans ambiguïté comprises (revue Opus, constat 4). Remplace : rien (`-c core.sshCommand=…` est déjà refusé par la liste
    blanche des réglages). Retrait : permanent."""
    for a in args:
        if a == "--":
            break
        if a.startswith("--exec-path="):
            return True
    lettres_a_valeur = {"rebase": "sXCS", "grep": "efmABC"}.get(sous, "")
    for a in mots:
        if a == "--":
            break
        if a.startswith("--"):
            nom = a.partition("=")[0]
            if _prefixe_long(nom, "--upload-pack", 5) or _prefixe_long(nom, "--receive-pack", 6):
                return True
            if sous in SOUS_COMMANDES_AVEC_EXEC and _prefixe_long(nom, "--exec", 4):
                return True
            if sous == "grep" and _prefixe_long(nom, "--open-files-in-pager", 4):
                return True
        elif a.startswith("-") and a != "-":
            for lettre in a[1:]:
                if (sous == "rebase" and lettre == "x") or (sous == "grep" and lettre == "O"):
                    return True
                if lettre in lettres_a_valeur:
                    break
    return False


def _options_avant_tiret(mots: list):
    """(lettres des amas d'options courtes, noms des options longues sans leur valeur), lus jusqu'à `--`."""
    lettres, longues = set(), set()
    for a in mots:
        if a == "--":
            break
        if a.startswith("--"):
            longues.add(a.partition("=")[0])
        elif re.fullmatch(r"-[A-Za-z]+", a):
            lettres.update(a[1:])
    return lettres, longues


def _destination_main(refspec: str) -> bool:
    """La destination du refspec (après le dernier deux-points) est la branche main, ou peut l'être (motif `*`, valeur inconnue). Le disque du Mac ne
    distingue pas Main de main : comparaison en minuscules."""
    if ":" not in refspec:
        return False
    destination = refspec.rpartition(":")[2].lower()
    if INCONNU in destination:
        return True
    for prefixe in ("refs/heads/", "heads/"):
        if destination.startswith(prefixe):
            reste = destination[len(prefixe):]
            return reste == "main" or "*" in reste
    return destination == "main" or destination == "*"


def _sortie_vers_chemin_protege(mots: list, globales: dict, c: Collecte) -> bool:
    """Une valeur de `--output` (collée `--output=x`, séparée `--output x`, abrégée dès `--outp`) est un chemin protégé. Vaut pour toute sous-commande git.
    Remplace : rien. Retrait : permanent."""
    sorties = []
    for i, a in enumerate(mots):
        if a == "--":
            break
        nom, egal, valeur = a.partition("=")
        if a.startswith("--") and _prefixe_long(nom, "--output", 5):
            if egal:
                sorties.append(valeur)
            elif i + 1 < len(mots):
                sorties.append(mots[i + 1])
    if not sorties:
        return False
    if any(INCONNU in s for s in sorties):
        return True   # valeur illisible (variable, substitution) : elle peut nommer un chemin protégé (R-20261108-06, 4). Remplace : rien. Retrait : permanent.
    arbre = _arbre_vise(globales, c)
    return any(cible_protegee(s, arbre, c.ctx) for s in sorties)


def _clean_en_essai(mots: list) -> bool:
    """`git clean` lu option par option, de gauche à droite, jusqu'à `--` ou `--end-of-options` (ce qui suit est un chemin : un `-n` placé après n'est pas
    un essai) : la valeur de `-e` et de `--exclude` est sautée (séparée, collée `-eX` ou `--exclude=X` ; dans un amas d'options courtes, le reste de
    l'amas après `e` est la valeur), et la dernière occurrence de `-n`, `--dry-run` (abrégé dès `--d`) ou `--no-dry-run` (abrégé dès `--no-d`) décide.
    Un mot illisible (INCONNU : variable, substitution) avant la fin des options rend le résultat faux : repli fermé, car ce mot peut valoir `-f` ou
    `--no-dry-run`. Seule l'expansion entre guillemets (INCONNU suivi de QUOTE : pas de découpage) est exemptée comme valeur de `-e` ou `--exclude`. Sans essai à blanc effectif : faux. Remplace : rien. Retrait : permanent."""
    essai = False
    i = 0
    while i < len(mots):
        a = mots[i]
        i += 1
        if a in ("--", "--end-of-options"):
            break
        if a.startswith("--"):
            nom, egal, _ = a.partition("=")
            if _prefixe_long(nom, "--exclude", 3):
                if egal:
                    valeur = a.partition("=")[2]
                else:
                    valeur = mots[i] if i < len(mots) else ""
                    i += 1
                if _inconnu_nu(valeur):
                    return False   # expansion nue : elle peut se découper en plusieurs mots, dont `--no-dry-run` (R-20261108-06, 1)
            elif INCONNU in a:
                return False
            elif _prefixe_long(nom, "--no-dry-run", 6):
                essai = False
            elif _prefixe_long(nom, "--dry-run", 3):
                essai = True
        elif a.startswith("-") and a != "-":
            for j, lettre in enumerate(a[1:], start=1):
                if lettre == "e":
                    if INCONNU in a[:j]:
                        return False   # un mot illisible avant `e` dans l'amas peut valoir `f` ou une autre lettre : repli fermé
                    if j == len(a) - 1:
                        if _inconnu_nu(mots[i] if i < len(mots) else ""):
                            return False   # valeur : expansion nue (R-20261108-06, 1)
                        i += 1   # la valeur est le mot suivant
                    elif _inconnu_nu(a[j + 1:]):
                        return False
                    break   # sinon, le reste de l'amas est la valeur
                if lettre == "n":
                    essai = True
            else:
                if INCONNU in a:
                    return False
        elif INCONNU in a:
            return False
    return essai


def _regle_reset(mots: list, longues: set):
    """`git reset` ne passe que s'il ne déplace pas HEAD : sans argument, avec `HEAD` seul, avec `HEAD` puis des chemins, ou avec `--` puis des chemins.
    `--soft` (reconnu dès `--s`, la seule option longue de git reset qui commence par s) et `--mixed` (dès `--mi`) sont refusés ; tout autre positionnel
    avant `--` aussi (repli fermé : `git reset <commit>` vaut `--mixed`), de même qu'un mot illisible (INCONNU : variable, substitution) avant `--`.
    `--keep` (dès `--k`) et `--merge` (dès `--me`) sont refusés comme `--soft` ; `--hard` suit la règle des positionnels (R-20261108-05, point 3 : `--hard`
    est refusé sous toutes ses formes dans un worktree, avant d'arriver ici : R-20261108-06, point 2). `--hard` est en outre refusé par le refus A3 de la garde dans l'espace de
    travail principal (reconnu dès `--h`), et par le crochet reference-transaction quand il déplacerait main. Remplace : rien. Retrait : permanent (voir FORMES_REPRISES)."""
    if any(_prefixe_long(o, "--soft", 3) or _prefixe_long(o, "--mixed", 4) or _prefixe_long(o, "--keep", 3) or _prefixe_long(o, "--merge", 4)
           for o in longues):
        return "A6-reset"
    avant_tiret = []
    for a in mots:
        if a == "--":
            break
        if INCONNU in a:
            return "A6-reset"
        if not (a.startswith("-") and a != "-"):
            avant_tiret.append(a)
    return None if not avant_tiret or avant_tiret[0] == "HEAD" else "A6-reset"   # après HEAD, git lit le reste comme des chemins


def _regle_reflog(mots: list):
    """`git reflog` : la sous-commande est le premier mot ; seules `show`, `list`, `exists` et la forme sans sous-commande (rien, une option ou une
    révision) passent. Les sous-commandes qui écrivent (`expire`, `delete`, `drop`, `write`) et une première valeur illisible sont refusées. Remplace :
    rien. Retrait : permanent (voir FORMES_REPRISES)."""
    if not mots:
        return None
    premier = mots[0]
    if INCONNU in premier or premier in ("expire", "delete", "drop", "write"):
        return "A6-reflog"
    return None


def _recree_une_branche(sous: str, mots: list) -> bool:
    """`git checkout -B` et `git switch -C` (et `switch --force-create`, abrégé dès `--force-`) : forme collée (`-Bx`), amas (`-qB`), forme séparée.
    La lettre est cherchée comme Git la lit : la première lettre qui prend une valeur (`b`, `B`) ferme l'amas, ce qui laisse passer `checkout -bBar`.
    Refusé partout, espace de travail principal compris, comme `git reset --hard` (refusé par A3 dans l'espace de travail, par A6-reset dans un worktree).
    R-20261109-09 (4 a). Remplace : rien. Retrait : permanent."""
    recree, avec_valeur = ("B", "bB") if sous == "checkout" else ("C", "cC")
    for a in mots:
        if a == "--":
            break
        if a.startswith("--"):
            if sous == "switch" and _prefixe_long(a.partition("=")[0], "--force-create", 8):
                return True
        elif re.fullmatch(r"-[A-Za-z]+", a):
            for lettre in a[1:]:
                if lettre == recree:
                    return True
                if lettre in avec_valeur:
                    break   # le reste de l'amas est le nom de la branche
    return False


def _regle_destructive(sous: str, mots: list, globales: dict, c: Collecte):
    """Formes de git que la décision R-20261108-04 (3 a) refuse en plus de celles des règles deny : `clean` qui supprime (tout sauf l'essai -n ou
    --dry-run effectif), `checkout -f`, `switch -f` et `--discard-changes`, `reset` qui déplace HEAD, `reflog` qui écrit, `--output` de toute sous-commande
    vers un chemin protégé (classe C), et `fetch` dont un refspec écrit main (avec ou sans +, -u ou --update-head-ok). Les options longues sont lues
    abrégées, comme Git. `git reset --hard` est refusé par le refus A3 de la garde dans l'espace de travail principal, et par le crochet reference-transaction quand il déplacerait main. Remplace : rien (git stash reste aux règles deny). Retrait : permanent (voir FORMES_REPRISES)."""
    lettres, longues = _options_avant_tiret(mots)
    if _sortie_vers_chemin_protege(mots, globales, c):   # --output écrit un fichier : valable pour toute sous-commande (décision R-20261108-04, 3 a)
        return "C"
    if sous == "clean":
        return None if _clean_en_essai(mots) else "A6-destructif"
    if sous in ("checkout", "switch"):
        if "f" in lettres or any(_prefixe_long(o, "--force", 3) for o in longues):
            return "A6-destructif"
        if sous == "switch" and any(_prefixe_long(o, "--discard-changes", 4) for o in longues):
            return "A6-destructif"
        if _recree_une_branche(sous, mots):
            return "A6-recree"
        return None
    if sous == "reset":
        # Reconnaissance abrégée de --hard : remplace la lecture de --hard en toutes lettres. Refus de --hard dans un worktree
        # (R-20261108-06, 2) : remplace rien. Retrait : permanent.
        if any(_prefixe_long(o, "--hard", 3) for o in longues):
            arbre = _arbre_vise(globales, c)
            if arbre is None or dans(arbre, c.ctx.espace) or dans(arbre, c.ctx.run):
                return None   # le refus A3 (écriture de l'arbre de l'espace de travail ou du run) juge `--hard` : sa clé est la plus précise
            return "A6-reset"   # dans un worktree, `--hard` sous toutes ses formes efface le travail non commité (R-20261108-06, 2)
        return _regle_reset(mots, longues)
    if sous == "reflog":
        return _regle_reflog(mots)
    if sous == "fetch":
        positionnels_fetch = positionnels(mots)
        return "A6-fetch" if any(_destination_main(r) for r in positionnels_fetch[1:]) else None
    return None


def regle_git(args: list, c: Collecte):
    globales, sous, mots = decouper_git(args)
    if sous is None:
        # Remplace : rien. Retrait : permanent.
        return "A2" if c.incertain else None   # `git` seul ou `git --version` : options globales seules (sous xargs, la sous-commande vient de l'entrée)
    if sous in GIT_POUSSEE:
        return "A1"
    if c.incertain:
        # Remplace : rien. Retrait : permanent.
        return "A2"   # sous xargs ou find -exec, les arguments sont ajoutés à l'exécution : sous-commande et options illisibles (revue Opus, constat 1)
    if globales["config-env"]:
        return "A6-reglage"
    for reglage in globales["c"]:
        if not _reglage_admis(reglage.partition("=")[0]):
            return "A6-reglage"
    if _option_qui_lance(sous, args, mots):
        return "A6-commande"
    for a in args:
        if a == "--":
            break
        nom = a.partition("=")[0]
        if len(nom) >= 6 and "--no-verify".startswith(nom) and nom.startswith("--no-v"):
            return "A6-saute"
    if sous == "commit" and _commit_saute_les_crochets(mots):
        return "A6-saute"
    # Formes reprises des fragments 26 et 39 (R-20261108-01, question 15 a). Chacune remplace la règle deny du même nom ; retrait : permanent.
    if _texte_branche_main(args) or (sous == "branch" and _branche_force_main(mots)):   # avant --force : la clé la plus précise nomme le refus
        return "A6-main"
    if any("--force" in a for a in args):   # `--force` hors de push, texte compris (le fragment 26 le refuse où qu'il figure dans une commande git)
        return "A6-force"
    if sous in GIT_FUSION:
        return "A1-fusion"
    if (globales["C"] or globales["git-dir"]) and any(re.search(r"(?:^|\s)push", a) for a in mots):   # `git -C <chemin> … push` nommé en texte
        return "A1-texte"
    v = _regle_destructive(sous, mots, globales, c)
    if v:
        return v
    if sous == "config":
        return "A6-config" if _config_en_ecriture(mots) else None
    if sous == "branch":
        ecrit = _branche_ecrit(mots)
    elif sous == "worktree":
        ecrit = bool(mots) and mots[0] != "list"
    elif sous in GIT_LECTURE:
        ecrit = False
    elif sous in GIT_ECRITURE:
        ecrit = True
    else:
        return "A2"
    arbre = _arbre_vise(globales, c)
    if ecrit and arbre is None:
        # Remplace : rien. Retrait : permanent.
        return "A3"   # arbre visé inconnu (`cd "$X"`, `-C "$(…)"`, `cd -`) : il peut être l'espace de travail ou le run (revue Opus, constat 7)
    if arbre and ecrit and _ecrit_l_arbre(sous, mots, arbre):
        if dans(arbre, c.ctx.espace) or dans(arbre, c.ctx.run):
            return "A3"
    if ecrit and c.ctx.controle_configuration:
        return verifier_configuration(arbre, c.ctx)
    return None


# --- Décision et hook ---------------------------------------------------------------------------------------------------------------------

def decider(commande: str, contexte=None):
    """Le verdict de refus de la commande, ou None si elle passe. Pure hors du contrôle de la configuration de Git (lecteur_git du contexte)."""
    ctx = contexte or contexte_par_defaut()
    collecte = Collecte(ctx)
    refus_npm = npm_guard.avec_rappel(commande, collecte)
    if collecte.erreur:
        return verdict("erreur-interne")
    if collecte.verdict:
        return collecte.verdict
    if collecte.editeur_en_attente:   # GIT_EDITOR=true posé sans commande derrière (`export`) : seule la commande qui suit l'admet
        return verdict("A6-variable")
    echec = any(m.startswith(ECHECS_D_ANALYSE) for m in refus_npm)
    # D13 : une enveloppe appelée hors de la forme admise ; une analyse en échec qui nomme le dossier des enveloppes (hors npm_ci.sh) est jugée de même.
    # Après regle_allexport (refus ci-dessus : sa clé garde le pas, R-20261111-32). Le repli lit le texte débarrassé de `'`, `"` et `\` : `outils-fig''es/`
    # désigne le même dossier pour le shell (R-20261111-40 point 1). Remplace : la recherche du seul littéral. Retrait : permanent.
    nu = commande.translate({ord(c): None for c in "'\"\\"})
    if not forme_admise(commande, ctx.dossier_forme) and (collecte.enveloppe_appelee or (echec and re.search(r"outils-figes/(?!npm_ci\.sh(?:[\s;&|)]|$))|pmzilla-lab/+(?:\./+)*outils(?!-figes/npm_ci\.sh(?:[\s;&|)]|$))", nu))):   # R-20261111-43 point 3 : tout `pmzilla-lab/outils…`, fermé par défaut ; remplace le seul `outils-figes/` ; retrait : avec le bac à sable
        return verdict("E-enveloppe")
    if echec and MOTS_SURVEILLES.search(commande):
        return verdict("entree-illisible")
    return None


def _lire_commande(texte: str):
    """(commande, lisible) : lisible faux si l'entrée n'est pas celle d'un appel Bash ; commande None pour un autre outil."""
    try:
        donnees = json.loads(texte)
    except ValueError:
        return None, False
    if not isinstance(donnees, dict):
        return None, False
    nom_de_l_outil = donnees.get("tool_name")
    if not isinstance(nom_de_l_outil, str) or not nom_de_l_outil:
        # Remplace : rien. Retrait : permanent.
        return None, False   # objet sans tool_name lisible (revue Opus, constat 14) : refusé ; un objet bien formé d'un autre outil passe
    if nom_de_l_outil != "Bash":
        return None, True
    entree = donnees.get("tool_input")
    commande = entree.get("command") if isinstance(entree, dict) else None
    if not isinstance(commande, str):
        # Remplace : rien. Retrait : permanent.
        return None, False
    return commande, True


def _cwd_du_hook(texte: str):
    try:
        cwd = json.loads(texte).get("cwd")
    except (ValueError, AttributeError):
        return None
    return cwd if isinstance(cwd, str) and os.path.isdir(cwd) else None


def main(argv: list, entree: str, contexte=None) -> int:
    try:
        commande, lisible = _lire_commande(entree)
        if not lisible:
            v = verdict("entree-illisible")
        elif not commande or not commande.strip():
            return 0
        else:
            v = decider(commande, contexte or contexte_par_defaut(_cwd_du_hook(entree)))
    except Exception:   # RecursionError et MemoryError comprises : dans le doute, refusé
        v = verdict("erreur-interne")
    if v is None:
        return 0
    return refuser(v)


def refuser(v: Verdict) -> int:
    """Imprime la ligne de refus sur la sortie d'erreur et rend le code 2, même si l'impression échoue (tube fermé) : un code 1 laisserait passer la
    commande (revue Opus, constat 14)."""
    try:
        print(message(v), file=sys.stderr)
    except Exception:
        pass
    return 2


def lire_entree(flux):
    """Le texte de l'entrée standard, ou None quand la lecture échoue (octets illisibles, flux fermé)."""
    try:
        return flux.read()
    except Exception:
        return None


USAGE = ("usage: python3 -I tools/garde_session.py < appel.json\n"
         "Hook PreToolUse des appels Bash : lit l'appel (JSON) sur l'entrée standard ; code 0 pour laisser passer, code 2 pour refuser avec une ligne\n"
         "sur la sortie d'erreur. Seule option : --help (classement de script, tests/script_dependencies ; aucune lecture de l'entrée).")

if __name__ == "__main__":
    if sys.argv[1:] in (["--help"], ["-h"]):
        print(USAGE)
        sys.exit(0)
    _texte = lire_entree(sys.stdin)
    sys.exit(refuser(verdict("entree-illisible")) if _texte is None else main(sys.argv[1:], _texte))
