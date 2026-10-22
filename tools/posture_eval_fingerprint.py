"""
PMZilla Lab : empreinte des fichiers évalués par le jeu d'essai des postures (change posture-evals-on-branch-tip, D2 et D7).

    python3 tools/posture_eval_fingerprint.py HEAD CLAUDE.md

Arguments : une révision, puis une ou plusieurs spécifications de chemin ; à lancer depuis la racine du dépôt (finish_branch.sh l'appelle avec -I).

Entrée : l'arbre de la révision et les spécifications de chemin Git (celles de tests/postures/fichiers-evalues.txt, relatives à
la racine du dépôt, `*` compris). Lignes : « <mode> <identifiant de contenu> <chemin> » de chaque fichier de l'arbre qui
correspond, triées par chemin ; empreinte : « v1: » suivi du SHA-256 de ces lignes jointes par des sauts de ligne (aucun fichier :
l'empreinte du texte vide, préfixée). Elle ne contient ni chemin, ni nom, ni contenu en clair. Module partagé par
tools/posture_evals.py et tools/finish_branch.sh (contrôle 6) : bibliothèque standard seulement, aucune base, aucun réseau.
Sortie du script : l'empreinte seule, code 2 sans chemin ou sur une erreur Git.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PREFIX = "v1:"


def read_list(text: str) -> list[str]:
    """Les entrées d'une liste de chemins évalués : ni lignes vides ni commentaires."""
    return [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def _git(repo: Path, *args: str, env: dict | None = None) -> bytes:
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, env=env)
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} : {done.stderr.decode(errors='replace').strip()}")
    return done.stdout


def lines(repo: Path, revision: str, specs: list[str]) -> list[str]:
    """Les lignes « mode identifiant chemin » des fichiers de l'arbre de `revision` qui correspondent aux spécifications."""
    if not specs:
        raise ValueError("aucun chemin évalué")
    tree = _git(repo, "rev-parse", "--verify", "-q", f"{revision}^{{tree}}").decode().strip()
    with tempfile.TemporaryDirectory() as folder:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(folder) / "index")}
        env.pop("GIT_LITERAL_PATHSPECS", None)
        _git(repo, "read-tree", tree, env=env)
        raw = _git(repo, "ls-files", "-s", "-z", "--", *specs, env=env)
    entries = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        head, _, path = item.partition(b"\t")
        mode, identifier, _stage = head.decode().split(" ")
        entries.append((path, f"{mode} {identifier} {path.decode(errors='surrogateescape')}"))
    return [line for _, line in sorted(entries)]


def fingerprint(repo: Path, revision: str, specs: list[str]) -> str:
    text = "\n".join(lines(Path(repo), revision, specs))
    return PREFIX + hashlib.sha256(text.encode("utf-8", errors="surrogateescape")).hexdigest()


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage : posture_eval_fingerprint.py <révision> <chemin>...", file=sys.stderr)
        return 2
    try:
        print(fingerprint(Path.cwd(), argv[0], argv[1:]))
    except (RuntimeError, ValueError) as error:
        print(f"posture_eval_fingerprint : {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
