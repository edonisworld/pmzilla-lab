#!/usr/bin/env python3
"""Contrôle de node_modules contre le verrou npm, sans npm, sans Node, sans réseau (mothra-slices, design D9).

    python3 tools/npm_lock_check.py <dossier de l'espace de travail npm>

Compare package-lock.json au verrou caché que npm écrit dans node_modules/.package-lock.json : chaque paquet du verrou qui n'est pas
facultatif doit être installé, à la même version et avec la même empreinte d'intégrité ; un paquet installé que le verrou ne connaît pas est
un écart ; les liens d'espace de travail (« link ») sont ignorés des deux côtés. Un paquet facultatif du verrou peut manquer (autre système), mais
s'il est installé il doit correspondre.

Un paquet installé doit aussi avoir son dossier : <dossier>/<chemin du paquet>/package.json existe (un dossier retiré à la main après
l'installation est un écart, que le verrou caché le croie installé).

Sortie : rien quand tout concorde ; sinon une ligne « écart : <cause> » (le chemin du paquet, jamais son contenu). Aucun fichier n'est écrit,
aucune installation n'est lancée ; ce script ne lit que le verrou, le verrou caché et l'existence des fichiers package.json des paquets.

Codes de sortie : 0 tout concorde ; 1 écart (verrou ou verrou caché absent, illisible ou sans table « packages », paquet absent, version ou
    empreinte différente, paquet inconnu du verrou, dossier de paquet absent) ; 2 usage incorrect.

Exemple :
    python3 tools/npm_lock_check.py mothra
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

CLES_FACULTATIVES = ("optional", "devOptional", "peerOptional")


def lire_paquets(fichier: Path) -> dict | str:
    """La table « packages » d'un verrou, ou un message d'écart (str)."""
    try:
        contenu = json.loads(fichier.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return f"{fichier.name} absent"
    except (OSError, UnicodeDecodeError, ValueError):
        return f"{fichier.name} illisible"
    paquets = contenu.get("packages") if isinstance(contenu, dict) else None
    if not isinstance(paquets, dict):
        return f"{fichier.name} sans table packages"
    return paquets


def est_installable(chemin: str, entree: object) -> bool:
    """Un paquet du verrou que npm ci installe : sous un node_modules, ni lien, ni source d'espace de travail."""
    return "node_modules/" in chemin and isinstance(entree, dict) and not entree.get("link")


def facultatif(entree: dict) -> bool:
    return any(entree.get(cle) for cle in CLES_FACULTATIVES)


def ecart(dossier: Path) -> str | None:
    """La première cause d'écart entre le verrou et node_modules, ou None si tout concorde."""
    verrou = lire_paquets(dossier / "package-lock.json")
    if isinstance(verrou, str):
        return verrou
    installe = lire_paquets(dossier / "node_modules" / ".package-lock.json")
    if isinstance(installe, str):
        return installe
    attendus = {c: e for c, e in verrou.items() if est_installable(c, e)}
    presents = {c: e for c, e in installe.items() if est_installable(c, e)}
    for chemin in sorted(attendus):
        entree = attendus[chemin]
        if chemin not in presents:
            if not facultatif(entree):
                return f"paquet absent : {chemin}"
            continue
        for champ in ("version", "integrity"):
            if entree.get(champ) != presents[chemin].get(champ):
                return f"{champ} différente : {chemin}"
        if not (dossier / chemin / "package.json").is_file():
            return f"dossier du paquet absent : {chemin}"
    for chemin in sorted(presents):
        if chemin not in attendus:
            return f"paquet installé inconnu du verrou : {chemin}"
    return None


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    cause = ecart(Path(argv[0]))
    if cause is None:
        return 0
    print(f"écart : {cause}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
