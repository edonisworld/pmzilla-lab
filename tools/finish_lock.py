"""PMZilla Lab : lecture du verrou de fin de branche (change multi-session-piloting, design D5, D6 et D7). Module importé (lancé seulement par `refuse` et `debloquer`, ci-dessous).

Le verrou est un dossier `pmzilla-fin-en-cours` du dossier Git commun, créé et retiré par le script de fin (tools/finish_train.sh, qui
source tools/finish_lock.sh ; les fins unitaires qui le sourçaient sont retirées par B9). Il contient `pid`, `debut` (secondes), `branche` et `jeton`. Ce module le LIT
seulement : l'outil de pilotage et le hook pre-commit l'importent ; il ne crée, ne retire ni ne modifie jamais le verrou. Seule exception,
la sous-commande `debloquer` de l'auteur (fonction unlock, refusée en session) : `python3 tools/finish_lock.py debloquer` retire un verrou
périmé, jamais un verrou tenu.

Tenu ou périmé : même règle que les repères de passage de tools/run_worktree.sh. Périmé quand le processus n'existe plus, quand le verrou est
plus vieux que PMZILLA_FINISH_LOCK_MAX_AGE secondes (21600 par défaut), ou quand le dossier n'a pas de pid lisible depuis plus de dix secondes.

Gel ciblé (change autonomous-trains-merge, design D18). Le train écrit dans le verrou, sous son jeton et avant toute construction, le fichier
`gel` : une ligne `B <branche>` par branche du train, une ligne `W <dossier>` par worktree gelé (celui de chaque branche et le worktree
d'intégration `wt-train-*`), puis la ligne `fin` (le fichier est écrit puis renommé : il est complet ou absent). `freeze_scope(common)` le lit :
{"held", "branches", "worktrees"} plus "stale", "readable", "branch", "start", "token". Un verrou tenu sans liste lisible vaut « tout gelé »
(échec fermé). `freezes(...)` est la règle unique des quatre lecteurs (le hook pre-commit, le lanceur de tests tests/run_all.sh,
`ci_local.sh run`, `pilot.py freeze`) : elle refuse seulement quand le verrou est tenu, que l'appelant n'en porte pas le jeton et que sa liste n'est
pas lisible, que le worktree de l'appelant y figure, ou (lecteurs qui écrivent) que l'action écrit main, le dossier d'exécution ou la liste prête.
Les lecteurs shell l'appellent par la commande suivante (seul usage en ligne de commande) :

    python3 tools/finish_lock.py refuse --common .git --worktree .   0 libre, 4 gelé (la branche du verrou sur la sortie), 2 usage

(option `--protected` en plus : l'action écrit main, le dossier d'exécution ou la liste prête.)

`blocking()` décrit le gel
général (design D18). Les hooks pre-merge-commit et reference-transaction ne l'appellent plus : ils décident sur une seule lecture du verrou
(read_lock), en échec fermé (audit #629, groupe O3 ; R-20261107-30, point 6). La garde npm ne lit pas ce module.
Remplace : le gel général de multi-session-piloting D7 (le verrou vivant gelait tous les worktrees) pour ces quatre lecteurs. Retrait : permanent ;
un gel plus large que cette règle est un défaut, jamais un retour au gel général (R-20261101-123).
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

LOCK_NAME = "pmzilla-fin-en-cours"
LIST_NAME = "gel"
LIST_END = "fin"
DEFAULT_MAX_AGE = 21600
FRESH_SECONDS = 10


def _read(chemin):
    try:
        return Path(chemin).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def max_age():
    try:
        return int(os.environ.get("PMZILLA_FINISH_LOCK_MAX_AGE", DEFAULT_MAX_AGE))
    except ValueError:
        return DEFAULT_MAX_AGE


def is_stale(dossier, now, age_max=None):
    """Périmé : processus mort, plus vieux que age_max (par défaut max_age(), donc la variable), ou sans pid lisible depuis plus de dix secondes.
    Un pid ou un début qui ne se lit pas comme un entier (OverflowError, ValueError) rend faux, sans trace."""
    dossier = Path(dossier)
    pid = _read(dossier / "pid")
    try:
        mtime = int(dossier.stat().st_mtime)
    except OSError:
        mtime = None
    if not pid.isdigit():
        return mtime is not None and int(time.time()) - mtime > FRESH_SECONDS
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return True
    except (OverflowError, ValueError):
        return False
    except OSError:
        pass
    debut = _read(dossier / "debut")
    try:
        if debut.isdigit():
            age = now - int(debut)
        elif mtime is not None:
            age = int(time.time()) - mtime
        else:
            return False
    except (OverflowError, ValueError):
        return False
    return age > (max_age() if age_max is None else age_max)


def read_lock(common, now=None):
    """None sans verrou ; sinon un dictionnaire : branch, start (secondes ou None), token, stale."""
    dossier = Path(common) / LOCK_NAME
    if not dossier.is_dir():
        return None
    now = int(time.time()) if now is None else now
    debut = _read(dossier / "debut")
    return {"branch": _read(dossier / "branche") or "?", "start": int(debut) if debut.isdigit() else None,
            "token": _read(dossier / "jeton"), "stale": is_stale(dossier, now)}


def owner_dead(common):
    """Preuve positive que la fin a disparu : le pid du verrou est lisible et le processus n'existe plus. Un verrou périmé par l'âge, un pid
    illisible ou un processus qui vit ne prouvent rien (False). Lu par les hooks pre-merge-commit et reference-transaction (A-42, #629).
    Remplace : la péremption seule comme preuve dans ces deux hooks. Retrait : permanent."""
    pid = _read(Path(common) / LOCK_NAME / "pid")
    if not pid.isdigit():
        return False
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return True
    except (OSError, OverflowError, ValueError):
        return False
    return False


def clock_text(debut):
    return time.strftime("%H:%M", time.localtime(debut if debut is not None else time.time()))


def blocking(common, token, now=None):
    """Le verrou vivant d'un autre processus (dictionnaire), ou None : pas de verrou, verrou périmé, ou jeton de l'appelant égal au sien.
    Gel GÉNÉRAL (design D18). Plus appelée par les hooks pre-merge-commit et reference-transaction depuis O3 (une seule lecture du verrou) ;
    gardée pour un test de la portée du gel (suite pilot). Retrait : au désherbage d'Hydra, avec ce test, si aucun lecteur ne l'a reprise."""
    verrou = read_lock(common, now)
    if verrou is None or verrou["stale"]:
        return None
    if token and token == verrou["token"]:
        return None
    return verrou


def _read_list(dossier):
    """(branches, worktrees) de la liste `gel` du verrou, ou None quand elle est absente, incomplète ou mal formée (échec fermé)."""
    try:
        lignes = (Path(dossier) / LIST_NAME).read_text(encoding="utf-8").split("\n")
    except (OSError, ValueError):
        return None
    lignes = [ligne for ligne in lignes if ligne != ""]
    if not lignes or lignes[-1] != LIST_END:
        return None
    branches, worktrees = [], []
    for ligne in lignes[:-1]:
        if ligne.startswith("B ") and len(ligne) > 2:
            branches.append(ligne[2:])
        elif ligne.startswith("W ") and len(ligne) > 2:
            worktrees.append(ligne[2:])
        else:
            return None
    return branches, worktrees


def freeze_scope(common, now=None):
    """Le gel CIBLÉ du verrou de fin (change autonomous-trains-merge, design D18 point 2). Lecture seule, seule fonction que lisent les quatre
    lecteurs du gel. Rend {"held", "branches", "worktrees"} plus : "stale" (verrou périmé, donc non tenu), "readable" (la liste du train est
    lisible), "branch", "start" et "token" (ceux du verrou). Un verrou tenu sans liste lisible vaut « tout gelé » : held vrai, readable faux
    (échec fermé). Remplace : le gel général, où la présence du verrou vivant suffisait. Retrait : permanent (un gel plus large est un défaut)."""
    scope = {"held": False, "stale": False, "readable": True, "branch": "", "start": None, "token": "", "branches": [], "worktrees": []}
    verrou = read_lock(common, now)
    if verrou is None:
        return scope
    scope.update(branch=verrou["branch"], start=verrou["start"], token=verrou["token"])
    if verrou["stale"]:
        scope["stale"] = True
        return scope
    scope["held"] = True
    liste = _read_list(Path(common) / LOCK_NAME)
    if liste is None:
        scope["readable"] = False
    else:
        scope["branches"], scope["worktrees"] = liste
    return scope


def _real(chemin):
    try:
        return os.path.realpath(chemin)
    except (OSError, ValueError):
        return str(chemin)


def _current_branch(worktree):
    """La branche courante du worktree, ou "" (tête détachée, Git illisible)."""
    try:
        fait = subprocess.run(["git", "-C", str(worktree), "symbolic-ref", "-q", "--short", "HEAD"], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return ""
    return fait.stdout.decode(errors="replace").strip() if fait.returncode == 0 else ""


# Remplace / Retrait : la règle de writes_protected (main ou tête détachée = écrit un chemin protégé) est inchangée, ajoutée au gel ciblé du
# change autonomous-trains-merge (D18 point 3). Retrait : permanent, avec le gel ciblé (tombe avec lui).
def writes_protected(worktree):
    """Vrai quand le worktree écrit main, le dossier d'exécution ou la liste prête : sa tête n'est pas une branche de travail (main ou tête
    détachée, comme le dossier d'exécution). Une lecture de Git impossible vaut vrai (échec fermé)."""
    try:
        fait = subprocess.run(["git", "-C", str(worktree), "symbolic-ref", "-q", "--short", "HEAD"], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return True
    return fait.returncode != 0 or fait.stdout.decode().strip() in ("", "main")


def freezes(common, worktree, token, protected=False, now=None, writes_ready_list=False, scope=None):
    """Le gel ciblé s'applique-t-il à l'appelant ? Rend le dictionnaire de freeze_scope() quand oui, None sinon (design D18 point 3).
    Refuse seulement quand le verrou est tenu, que l'appelant n'en porte pas le jeton et que : writes_ready_list (l'action écrit la liste
    prête : train_ready add, drop et prune, gelée quel que soit le worktree), ou la liste n'est pas lisible, ou le worktree de l'appelant est
    dans la liste, ou (protected) l'action écrit main ou le dossier d'exécution. Ne crée, ne retire ni ne modifie jamais le verrou.
    Remplace : rien (paramètre ajouté, faux par défaut). Retrait : permanent, avec le gel ciblé."""
    # R-20261108-11 : la décision et le message viennent de la même lecture du verrou. Remplace : la seconde lecture du verrou dans
    # freeze_state. Retrait : permanent, avec le gel ciblé (un état lu en deux fois est un défaut). `scope` : le dictionnaire déjà lu par l'appelant ; sans lui, freezes() lit le verrou.
    if scope is None:
        scope = freeze_scope(common, now)
    if not scope["held"]:
        return None
    if token and token == scope["token"]:
        return None
    if writes_ready_list:
        return scope
    if not scope["readable"]:
        return scope
    if _real(worktree) in {_real(w) for w in scope["worktrees"]}:
        return scope
    if scope["branches"] and _current_branch(worktree) in scope["branches"]:
        return scope   # worktree créé après coup sur une branche du train : gelé sans ligne W
    if protected and writes_protected(worktree):
        return scope
    return None


UNLOCK_COMMAND = "python3 tools/finish_lock.py debloquer"


def unlock(common):
    """Déblocage RÉSERVÉ À L'AUTEUR (A-42 de #629, R-20261107-30 point 5) : retire le dossier du verrou quand il est périmé (processus mort,
    plus vieux que le maximum, ou sans pid lisible) ; un verrou tenu (processus vivant, dans l'âge) n'est jamais retiré (attendre sa fin :
    pilot.py freeze --wait 60). Un verrou plus vieux que le maximum est retiré même si son processus vit encore : unlock affiche alors
    d'abord « processus <pid> encore vivant » avant le retrait, sans question. Seul
    endroit de ce module qui écrit ; refusé en session (marqueur de session posé, même vide : code 6 sur la sortie d'erreur, comme
    tools/posture_evals.py). Codes : 0 retiré ou aucun verrou, 1 verrou tenu ou retrait impossible, 6 refusé en session. La durée du verrou se
    compte avec DEFAULT_MAX_AGE, jamais avec PMZILLA_FINISH_LOCK_MAX_AGE (une variable ne rend pas un verrou tenu périmé). Retrait sûr : le
    dossier est d'abord renommé vers un nom unique ; son identité (inode) et son jeton sont revérifiés, et sa péremption seulement s'il porte un
    pid lisible ; puis il est supprimé. Si l'un a changé, il est remis en place et le code est 1.
    Remplace : l'absence de commande de retrait (le verrou périmé passait seul dans les crochets). Retrait : permanent."""
    if "CLAUDECODE" in os.environ:
        print("finish_lock : déblocage refusé en session Claude Code (commande réservée à l'auteur, dans son Terminal)", file=sys.stderr)
        return 6
    dossier = Path(common) / LOCK_NAME
    verrou = read_lock(common)
    if verrou is None:
        print("finish_lock : aucun verrou de fin à retirer")
        return 0
    pid = _read(dossier / "pid")
    # La péremption est jugée UNE fois, avant le renommage : sans pid lisible elle repose sur le mtime du dossier, qu'un renommage peut
    # toucher selon le système de fichiers ; la relire après renommage ferait paraître le verrou frais. Remplace : la relecture de ce mtime
    # sur le dossier renommé. Retrait : permanent (le mtime relu après renommage n'est pas une mesure fiable).
    if not is_stale(dossier, int(time.time()), DEFAULT_MAX_AGE):
        if pid.isdigit():
            print(f"finish_lock : le verrou de fin ({verrou['branch']}) est tenu par un processus vivant, non retiré ; attendre sa fin "
                  "(uv run tools/pilot.py freeze --wait 60)")
        else:
            print(f"finish_lock : le verrou de fin ({verrou['branch']}) a un pid illisible et date de moins de {FRESH_SECONDS} s, non retiré ; "
                  "attendre sa fin (uv run tools/pilot.py freeze --wait 60)")
        return 1
    if pid.isdigit() and not owner_dead(common):
        # périmé par l'âge alors que le processus vit : le retrait est voulu, mais l'auteur doit le savoir avant qu'il ait lieu
        print(f"finish_lock : processus {pid} encore vivant (verrou plus vieux que {DEFAULT_MAX_AGE} s), retiré quand même")
    # Identité du dossier jugé (périphérique, inode) : un renommage la garde, un dossier recréé entre la décision et le renommage en a une
    # autre. Ferme la course d'un verrou sans jeton remplacé par le mkdir d'une fin neuve. Remplace : la relecture du mtime, qui fermait
    # cette course selon le système de fichiers. Retrait : permanent.
    try:
        identite = (os.stat(dossier).st_dev, os.stat(dossier).st_ino)
    except OSError as erreur:
        print(f"finish_lock : verrou de fin non retiré, dossier illisible ({type(erreur).__name__})")
        return 1
    retrait = Path(common) / f"pmzilla-fin-retrait-{os.getpid()}-{time.time_ns()}"
    try:
        os.rename(dossier, retrait)
    except OSError as erreur:
        print(f"finish_lock : verrou de fin non retiré, renommage impossible ({type(erreur).__name__})")
        return 1
    # Le jeton est toujours revérifié, et l'identité du dossier ; sans pid lisible, la péremption d'avant renommage tient (jamais relue sur
    # le mtime) ; un pid apparu depuis oblige à revérifier la péremption.
    try:
        meme_dossier = (os.stat(retrait).st_dev, os.stat(retrait).st_ino) == identite
    except OSError:
        meme_dossier = False
    change = not meme_dossier or _read(retrait / "jeton") != verrou["token"] or (
        _read(retrait / "pid").isdigit() and not is_stale(retrait, int(time.time()), DEFAULT_MAX_AGE))
    if change:
        try:
            os.rename(retrait, dossier)
        except OSError:
            print(f"finish_lock : le verrou de fin a changé pendant le retrait et n'a pas pu être remis en place (conservé sous {retrait.name})")
            return 1
        print("finish_lock : le verrou de fin a changé pendant le retrait, remis en place, non retiré")
        return 1
    try:
        shutil.rmtree(retrait)
    except OSError as erreur:
        print(f"finish_lock : suppression du verrou de fin périmé impossible ({type(erreur).__name__}), reste sous {retrait.name}")
        return 1
    print(f"finish_lock : verrou de fin périmé ({verrou['branch']}) retiré")
    return 0


def main(argv):
    """Lecture pour les lecteurs shell (le lanceur de tests, ci_local.sh) : une seule règle, celle de freezes().

        python3 -I tools/finish_lock.py refuse --common <dossier Git commun> --worktree <dossier> [--protected]

    Le jeton de l'appelant est lu dans FINISH_LOCK_TOKEN. Sortie 0 : libre (la sortie standard dit « perime » quand le verrou est périmé) ;
    4 : gelé (la sortie standard donne la branche du verrou) ; 2 : usage."""
    args = list(argv)
    if args and args[0] == "debloquer":   # sous-commande de l'auteur : python3 tools/finish_lock.py debloquer [--common <dossier>]
        if len(args) == 3 and args[1] == "--common":
            return unlock(args[2])
        if len(args) != 1:
            return 2
        try:
            commun = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], capture_output=True, check=True,
                                    text=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            print("finish_lock : dossier Git commun illisible (lancer depuis le dépôt, ou indiquer --common <dossier>)")
            return 2
        return unlock(commun)
    if not args or args[0] != "refuse":
        return 2
    args = args[1:]
    protege = "--protected" in args
    args = [a for a in args if a != "--protected"]
    if len(args) != 4 or args[0] != "--common" or args[2] != "--worktree":
        return 2
    scope = freeze_scope(args[1])
    if scope["stale"]:
        print("perime")
        return 0
    if freezes(args[1], args[3], os.environ.get("FINISH_LOCK_TOKEN", ""), protege) is not None:
        print(scope["branch"])
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
