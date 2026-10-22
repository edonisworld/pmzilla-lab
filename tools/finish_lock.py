"""PMZilla Lab : lecture du verrou de fin de branche (change multi-session-piloting, design D5, D6 et D7). Module importé, jamais lancé.

Le verrou est un dossier `pmzilla-fin-en-cours` du dossier Git commun, créé et retiré par les scripts de fin (tools/finish_branch.sh et
tools/finish_worktree.sh, qui sourcent tools/finish_lock.sh). Il contient `pid`, `debut` (secondes), `branche` et `jeton`. Ce module le LIT
seulement : l'outil de pilotage et le hook pre-commit l'importent ; il ne crée, ne retire ni ne modifie jamais le verrou.

Tenu ou périmé : même règle que les repères de passage de tools/run_worktree.sh. Périmé quand le processus n'existe plus, quand le verrou est
plus vieux que PMZILLA_FINISH_LOCK_MAX_AGE secondes (21600 par défaut), ou quand le dossier n'a pas de pid lisible depuis plus de dix secondes.
"""
import os
import time
from pathlib import Path

LOCK_NAME = "pmzilla-fin-en-cours"
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


def is_stale(dossier, now):
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
    except OSError:
        pass
    debut = _read(dossier / "debut")
    if debut.isdigit():
        age = now - int(debut)
    elif mtime is not None:
        age = int(time.time()) - mtime
    else:
        return False
    return age > max_age()


def read_lock(common, now=None):
    """None sans verrou ; sinon un dictionnaire : branch, start (secondes ou None), token, stale."""
    dossier = Path(common) / LOCK_NAME
    if not dossier.is_dir():
        return None
    now = int(time.time()) if now is None else now
    debut = _read(dossier / "debut")
    return {"branch": _read(dossier / "branche") or "?", "start": int(debut) if debut.isdigit() else None,
            "token": _read(dossier / "jeton"), "stale": is_stale(dossier, now)}


def clock_text(debut):
    return time.strftime("%H:%M", time.localtime(debut if debut is not None else time.time()))


def blocking(common, token, now=None):
    """Le verrou vivant d'un autre processus (dictionnaire), ou None : pas de verrou, verrou périmé, ou jeton de l'appelant égal au sien."""
    verrou = read_lock(common, now)
    if verrou is None or verrou["stale"]:
        return None
    if token and token == verrou["token"]:
        return None
    return verrou
