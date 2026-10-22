#!/usr/bin/env python3
"""PMZilla Lab : résolution partagée des dossiers du lab (R-77, design D1, D2, D5). Jumeau shell : tools/lab_paths.sh.

Aucun outil ne calcule lui-même un de ces dossiers. Règle, dans l'ordre :
  - racine du code : le dossier de travail qui porte ce fichier (liens suivis) ; jamais le dossier du lab ni le dossier de contenu ;
  - racine de contenu : PMZILLA_LAB_WORKSPACE quand elle est posée et non vide (un dossier absent est un échec, jamais un repli),
    sinon le parent du dossier Git commun de la racine du code (`git rev-parse --git-common-dir`, délai de 5 secondes, une seule
    ligne absolue), sinon un échec ;
  - dossier du lab : le parent de la racine de contenu ;
  - dossier d'exécution : PMZILLA_LAB_RUN, sinon le dossier `run` du dossier du lab ;
  - dossier de données : PMZILLA_LAB_DATA, sinon le dossier `.pmzilla-lab` du dossier personnel ;
  - dossier des sauvegardes : DB_BACKUP_SAUVEGARDES (la variable du script de sauvegarde) quand elle est posée et non vide, sinon le
    dossier `sauvegardes` du dossier de données ; le module ne le crée, ne le liste et ne l'ouvre jamais ;
  - dossier de contexte (organisation-context, D16) : PMZILLA_LAB_CONTEXT quand elle est posée et non vide, sinon le dossier `contexte`
    du dossier du lab ; le module ne le crée, ne le liste et ne teste rien à l'intérieur ;
  - dossier des worktrees (lab-folder-layout, D1) : PMZILLA_LAB_WORKTREES quand elle est posée et non vide, sinon le dossier `worktrees`
    du dossier du lab ; toujours la dernière ligne imprimée ; le module ne le crée, ne le liste et ne l'ouvre jamais ;
  - fichiers locaux ignorés par Git : `local_file(nom)` donne le chemin absolu (variable posée, sinon place dans la racine de
    contenu) ; le module ne les ouvre jamais, il ne les copie ni ne les lie.

Un échec de résolution lève `LabPathsError` ; `resolve_or_exit` l'écrit sur la sortie d'erreur (jamais un chemin) et sort avec le code 78.

    python3 tools/lab_paths.py

écrit les huit dossiers, une ligne `nom=chemin` chacun (`--lang en` pour les phrases en anglais).
Codes de sortie : 0 dossiers écrits, 78 dossier de contenu introuvable ou PMZILLA_LAB_WORKSPACE sur un dossier absent.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

EXIT_CONFIG = 78
GIT_TIMEOUT = 5

VAR_CONTENT = "PMZILLA_LAB_WORKSPACE"
VAR_RUN = "PMZILLA_LAB_RUN"
VAR_DATA = "PMZILLA_LAB_DATA"
VAR_BACKUPS = "DB_BACKUP_SAUVEGARDES"
VAR_CONTEXT = "PMZILLA_LAB_CONTEXT"
VAR_WORKTREES = "PMZILLA_LAB_WORKTREES"

MESSAGES = {
    "fr": {
        "not_found": "chemins du lab : dossier de contenu introuvable ; poser PMZILLA_LAB_WORKSPACE ou lancer depuis un clone Git du dépôt",
        "missing_folder": "chemins du lab : PMZILLA_LAB_WORKSPACE désigne un dossier absent",
    },
    "en": {
        "not_found": "lab paths: content folder not found; set PMZILLA_LAB_WORKSPACE or run from a Git clone of the repository",
        "missing_folder": "lab paths: PMZILLA_LAB_WORKSPACE names a missing folder",
    },
}

# Registre des fichiers locaux ignorés par Git que des outils lisent (design D5) : nom -> (place sous la racine de contenu, variables
# dans l'ordre de priorité). Le module teste au plus l'existence du dossier ; il n'ouvre jamais ces fichiers.
LOCAL_FILES = {
    "sensitive_names": (("Flux-Lab", "noms-sensibles.txt"), ("PMZILLA_LAB_SENSITIVE_NAMES", "PMZILLA_NOMS")),
    "bmad_replacements": ((".pmzilla", "remplacements-bmad.tsv"), ()),
    "personal_identifiers": ((".pmzilla", "identifiants.txt"), ()),
    "product_versions": (("Flux-Lab", "versions-produit.txt"), ("PMZILLA_LAB_PRODUCT_VERSIONS",)),
    "local_context": ((".pmzilla", "contexte.md"), ()),
    "cases_author": ((".pmzilla", "cases.yaml"), ()),           # auteur du module des cas, lu par tools/cases_store.py
}


class LabPathsError(Exception):
    """Échec de résolution. `key` vaut `not_found` ou `missing_folder` ; le message ne contient jamais de chemin."""

    def __init__(self, key: str, lang: str = "fr"):
        self.key = key
        self.lang = lang if lang in MESSAGES else "fr"
        super().__init__(MESSAGES[self.lang][key])


def code_root(file: str | os.PathLike | None = None) -> Path:
    """Le dossier de travail qui porte le fichier donné (par défaut ce module), liens suivis : le parent de `tools/`."""
    return Path(file if file is not None else __file__).resolve().parents[1]


def _git_common_parent(code: Path) -> Path | None:
    try:
        r = subprocess.run(["git", "-C", str(code), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                           capture_output=True, text=True, timeout=GIT_TIMEOUT, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    lignes = r.stdout.splitlines()
    if r.returncode != 0 or len(lignes) != 1 or not os.path.isabs(lignes[0]):
        return None
    parent = Path(lignes[0]).parent
    return parent if parent.is_dir() else None


def content_root(env=None, code: Path | None = None, lang: str = "fr") -> Path:
    env = os.environ if env is None else env
    voulu = env.get(VAR_CONTENT)
    if voulu:
        dossier = Path(voulu).expanduser()
        if not dossier.is_dir():
            raise LabPathsError("missing_folder", lang)
        return dossier.resolve()
    parent = _git_common_parent(code if code is not None else code_root())
    if parent is None:
        raise LabPathsError("not_found", lang)
    return parent


def lab_folder(content: Path) -> Path:
    return content.parent


def run_tree(content: Path, env=None) -> Path:
    env = os.environ if env is None else env
    voulu = env.get(VAR_RUN)
    return Path(voulu).expanduser() if voulu else lab_folder(content) / "run"


def data_folder(env=None) -> Path:
    env = os.environ if env is None else env
    voulu = env.get(VAR_DATA)
    return Path(voulu).expanduser() if voulu else Path.home() / ".pmzilla-lab"


def backups_folder(env=None) -> Path:
    """Dossier des sauvegardes de la base (safe-branch-finish D4) : même règle que tools/db_backup.sh, jamais créé ni ouvert ici."""
    env = os.environ if env is None else env
    voulu = env.get(VAR_BACKUPS)
    return Path(voulu).expanduser() if voulu else data_folder(env) / "sauvegardes"


def context_folder(content: Path, env=None) -> Path:
    """Dossier de contexte (organisation-context, D16) : la variable quand elle est posée et non vide, sinon `contexte` du dossier du lab.
    Jamais créé, listé ni ouvert ici, ni aucun chemin à l'intérieur."""
    env = os.environ if env is None else env
    voulu = env.get(VAR_CONTEXT)
    return Path(voulu).expanduser() if voulu else lab_folder(content) / "contexte"


def worktrees_folder(content: Path, env=None) -> Path:
    """Dossier des worktrees (lab-folder-layout, D1) : la variable quand elle est posée et non vide, sinon `worktrees` du dossier du lab.
    Jamais créé, listé ni ouvert ici."""
    env = os.environ if env is None else env
    voulu = env.get(VAR_WORKTREES)
    return Path(voulu).expanduser() if voulu else lab_folder(content) / "worktrees"


def local_file(name: str, content: Path, env=None) -> Path:
    """Chemin absolu d'un fichier local du registre : la variable quand elle est posée, sinon sa place sous la racine de contenu."""
    env = os.environ if env is None else env
    place, variables = LOCAL_FILES[name]
    for variable in variables:
        if env.get(variable):
            return Path(env[variable]).expanduser()
    return content.joinpath(*place)


def local_file_or_exit(name: str, env=None, file: str | os.PathLike | None = None, lang: str = "fr") -> Path:
    """Chemin d'un fichier local du registre : la variable du registre quand elle est posée (le dossier de contenu n'est alors pas
    cherché), sinon sa place sous le dossier de contenu ; échec de résolution : message, code 78."""
    env = os.environ if env is None else env
    for variable in LOCAL_FILES[name][1]:
        if env.get(variable):
            return Path(env[variable]).expanduser()
    return local_file(name, resolve_or_exit(env, file, lang)["content_root"], env)


def local_file_for(name: str, code: str | os.PathLike, env=None, lang: str = "fr") -> Path | None:
    """Chemin d'un fichier local du registre pour un outil qui travaille sur un dossier de code donné (`code`, un dépôt ou un arbre).
    La variable du registre quand elle est posée ; sinon la place du fichier sous le dossier de contenu de `code` (variable
    PMZILLA_LAB_WORKSPACE, sinon le dépôt Git commun de `code`). None quand ce dossier est introuvable faute de dépôt Git : le fichier
    est alors absent, et l'outil garde son comportement sans fichier. PMZILLA_LAB_WORKSPACE sur un dossier absent : message, code 78."""
    env = os.environ if env is None else env
    for variable in LOCAL_FILES[name][1]:
        if env.get(variable):
            return Path(env[variable]).expanduser()
    try:
        return local_file(name, content_root(env, Path(code), lang), env)
    except LabPathsError as erreur:
        if erreur.key == "missing_folder":
            print(str(erreur), file=sys.stderr)
            sys.exit(EXIT_CONFIG)
        return None


def resolve(env=None, file: str | os.PathLike | None = None, lang: str = "fr") -> dict:
    """Les huit dossiers (code, contenu, lab, exécution, données, sauvegardes, contexte, worktrees) ; lève LabPathsError."""
    code = code_root(file)
    content = content_root(env, code, lang)
    return {"code_root": code, "content_root": content, "lab_folder": lab_folder(content),
            "run_tree": run_tree(content, env), "data_folder": data_folder(env),
            "backups_folder": backups_folder(env), "context_folder": context_folder(content, env),
            "worktrees_folder": worktrees_folder(content, env)}


def resolve_or_exit(env=None, file: str | os.PathLike | None = None, lang: str = "fr") -> dict:
    """Comme `resolve`, mais écrit le message sur la sortie d'erreur et sort avec le code 78 (design D2)."""
    try:
        return resolve(env, file, lang)
    except LabPathsError as erreur:
        print(str(erreur), file=sys.stderr)
        sys.exit(EXIT_CONFIG)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    lang = "en" if argv[-1:] == ["en"] and argv[-2:-1] == ["--lang"] else "fr"
    dossiers = resolve_or_exit(lang=lang)
    for nom, chemin in dossiers.items():
        print(f"{nom}={chemin}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
