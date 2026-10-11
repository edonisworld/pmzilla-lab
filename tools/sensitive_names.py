#!/usr/bin/env python3
"""Garde des noms sensibles du module des cas (design.md 3.5).

Fonctions pures, mêmes règles de correspondance que le hook pre-commit : mot entier (un nom collé à une lettre, un
chiffre ou un tiret bas ne correspond pas ; un nom qui commence ou finit par un symbole correspond), casse ignorée sauf
pour les noms de 3 caractères ou moins et les sigles entièrement en majuscules, comparés en respectant la casse.

`load_names` lit un nom par ligne (lignes vides et lignes commençant par « # » ignorées). Fichier absent, illisible, ou
sans aucun nom : `SensitiveNamesUnavailable`, avec `reason` valant `missing`, `unreadable` ou `empty` ; jamais une liste
vide. Le message nomme le chemin, jamais le contenu. Chemin : `Flux-Lab/noms-sensibles.txt` sous l'espace de travail,
remplaçable par PMZILLA_LAB_SENSITIVE_NAMES. `find_field` renvoie le nom du champ concerné, jamais le nom trouvé.
"""
import os
import re
from pathlib import Path

MOT = "A-Za-z0-9_"
RACINE = Path(__file__).resolve().parents[1]


class SensitiveNamesUnavailable(Exception):
    def __init__(self, reason, path):
        self.reason = reason
        self.path = Path(path)
        detail = {"missing": "liste absente", "unreadable": "liste illisible", "empty": "liste sans aucun nom"}[reason]
        super().__init__(f"{detail} : {self.path}")


def default_path() -> Path:
    return Path(os.environ.get("PMZILLA_LAB_SENSITIVE_NAMES") or RACINE / "Flux-Lab" / "noms-sensibles.txt")


def parse_names(texte: str) -> list:
    """Un nom par ligne ; lignes vides et lignes commençant par « # » ignorées. Seule lecture de la liste, partagée avec le hook pre-commit."""
    return [l.strip() for l in texte.lstrip("\ufeff").splitlines() if l.strip() and not l.strip().startswith("#")]


def load_names(path=None) -> list:
    chemin = Path(path) if path is not None else default_path()
    if not chemin.exists():
        raise SensitiveNamesUnavailable("missing", chemin)
    try:
        texte = chemin.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        raise SensitiveNamesUnavailable("unreadable", chemin) from None
    noms = parse_names(texte)
    if not noms:
        raise SensitiveNamesUnavailable("empty", chemin)
    return noms


def _sensible_a_la_casse(nom):
    return len(nom) <= 3 or (nom == nom.upper() and nom != nom.lower())


def _compiler(noms, drapeaux):
    if not noms:
        return None
    motifs = sorted(noms, key=len, reverse=True)
    return re.compile(rf"(?<![{MOT}])(?:" + "|".join(re.escape(n) for n in motifs) + rf")(?![{MOT}])", drapeaux)


def _motifs(names):
    noms = {n.strip() for n in names if n and n.strip()}
    exacts = {n for n in noms if _sensible_a_la_casse(n)}
    return [m for m in (_compiler(exacts, 0), _compiler(noms - exacts, re.IGNORECASE)) if m]


def patterns(names) -> list:
    """Motifs compilés d'une liste de noms (seule compilation, partagée avec le hook pre-commit)."""
    return _motifs(names)


def line_matches(motifs, ligne: str) -> bool:
    return any(m.search(ligne) for m in motifs)


def find_field(fields: dict, names):
    """Nom du premier champ dont la valeur contient un nom listé, sinon None. Ne renvoie jamais le nom trouvé."""
    motifs = _motifs(names)
    for champ, valeur in fields.items():
        if line_matches(motifs, str(valeur)):
            return champ
    return None
