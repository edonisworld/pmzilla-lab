"""PMZilla Lab : dossiers de la veille et leurs noms actuels (plan de la version anglaise, 7.7).

Les dossiers ont changé de nom : `veille/` (sources.yaml, tri.yaml) est devenu `watch/`, `Veille-Lab/` `Watch-Lab/` (son
sous-dossier de collection `veille/` devient `watch/`), `Veille-Ecartes/` `Watch-Excluded/` et `_a-lire.md`
`_to-read.md`. Les anciens noms ne sont plus acceptés : quand seul l'ancien dossier existe, la résolution s'arrête avec
un message qui donne le nom actuel et l'outil de migration `tools/migrate_watch.py` (code de sortie non nul en ligne de
commande). Sinon : le dossier actuel (il sera créé s'il manque).

Une seule logique, importée par watch_lab.py, watch_triage.py et dashboard.py ; watch.sh l'appelle par la ligne de
commande (`python3 watch_paths.py lab|excluded|config|collection <workspace>` écrit le chemin ou le nom à utiliser).
Sans dépendance hors de la bibliothèque standard.

Ce module ne lit aucun dossier de contenu : il ne teste que l'existence des dossiers.

Exemple :
    python3 tools/watch_paths.py lab workspace
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_paths  # noqa: E402


NEW = {"config": "watch", "lab": "Watch-Lab", "excluded": "Watch-Excluded", "collection": "watch", "to_read": "_to-read.md"}
OLD = {"config": "veille", "lab": "Veille-Lab", "excluded": "Veille-Ecartes", "collection": "veille", "to_read": "_a-lire.md"}


OWN_COLLECTION = "own-articles"   # collection personnelle des articles de l'utilisateur (dossier Watch-Lab/own-articles/), la même pour tous


class AncienNom(SystemExit):
    """Seul un dossier à l'ancien nom existe : arrêt propre, le message donne le nom actuel et l'outil de migration."""


def _refuse(old: str, new: str) -> AncienNom:
    return AncienNom(f"PMZilla Lab, erreur : le dossier {old}/ n'est plus pris en charge ; le nom actuel est {new}/. "
                     "Lancer `uv run tools/migrate_watch.py` (une seule fois) pour le migrer.")


def _pick(parent: Path, kind: str) -> Path:
    """Le dossier actuel (existant ou à créer) ; l'ancien seul est refusé."""
    new, old = parent / NEW[kind], parent / OLD[kind]
    if not new.is_dir() and old.is_dir():
        raise _refuse(OLD[kind], NEW[kind])
    return new


class ReglagesSuivis(SystemExit):
    """Enregistrement refusé : le dossier de code est le dossier d'exécution (run-worktree D15)."""


def refuse_depuis_le_dossier_d_execution(code_root: Path, fichier: Path) -> None:
    """sources.yaml et tri.yaml sont suivis par Git : les écrire dans le dossier d'exécution le salirait et bloquerait sa mise à jour.
    Refus (code de sortie 1) quand `code_root` est le dossier d'exécution (PMZILLA_LAB_RUN, par défaut le dossier run du dossier du lab) ou en dépend,
    chemins résolus ; rien n'est écrit."""
    run = lab_paths.resolve_or_exit()["run_tree"].resolve()   # module partagé : PMZILLA_LAB_RUN, sinon le dossier run du lab
    code = Path(code_root).resolve()
    if code == run or run in code.parents:
        raise ReglagesSuivis(f"PMZilla Lab, enregistrement refusé ({Path(fichier).name}) : réglages suivis par Git : "
                             "à modifier depuis le dépôt de développement, puis à commiter.")


def config_dir(workspace: Path) -> Path:
    """Dossier de sources.yaml et tri.yaml : `watch/`, sinon `veille/`."""
    return _pick(Path(workspace), "config")


def lab_dir(workspace: Path) -> Path:
    """Dossier des articles collectés : `Watch-Lab/`, sinon `Veille-Lab/`."""
    return _pick(Path(workspace), "lab")


def excluded_dir(workspace: Path) -> Path:
    """Dossier des articles écartés : `Watch-Excluded/`, sinon `Veille-Ecartes/`."""
    return _pick(Path(workspace), "excluded")


def collection_name(lab: Path) -> str:
    """Nom du sous-dossier de la collection dans le dossier des articles : `watch`. Un sous-dossier `veille` resté seul
    (migration interrompue) est refusé."""
    lab = Path(lab)
    if not (lab / NEW["collection"]).is_dir() and (lab / OLD["collection"]).is_dir():
        raise _refuse(f"{lab.name}/{OLD['collection']}", f"{lab.name}/{NEW['collection']}")
    return NEW["collection"]


def to_read_name(lab: Path) -> str:
    """`_to-read.md`, seul nom de la liste à lire."""
    return NEW["to_read"]


def main(argv: list[str]) -> int:
    usage = "usage : watch_paths.py {lab|excluded|config|collection} <workspace>"
    if len(argv) != 2 or argv[0] not in ("lab", "excluded", "config", "collection"):
        print(usage, file=sys.stderr)
        return 2
    workspace = Path(argv[1])
    try:
        return _run(argv[0], workspace)
    except AncienNom as erreur:
        print(erreur, file=sys.stderr)
        return 1


def _run(what: str, workspace: Path) -> int:
    if what == "collection":
        print(collection_name(lab_dir(workspace)))
    else:
        print({"lab": lab_dir, "excluded": excluded_dir, "config": config_dir}[what](workspace))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
