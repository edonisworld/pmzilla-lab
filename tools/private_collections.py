#!/usr/bin/env python3
"""PMZilla Lab : les collections privées de la bibliothèque (organisation-context, design D3 et D11).

Une collection privée n'est cherchée que lorsqu'on la nomme, et rien d'elle ne quitte le Mac : ni passage, ni titre, ni en-tête.
Ce module est la seule définition de leurs noms : l'indexeur, le serveur, l'outil de contexte et les tests d'édition importent la
constante ; aucun autre fichier de tools/ n'écrit le nom en littéral (tests/private_collections le vérifie).

    CONTEXT_COLLECTION   la collection des notes de contexte de l'organisation
    PRIVATE_COLLECTIONS  l'ensemble des collections privées
    without_private      retire les collections privées d'une liste de noms
    shareable            faux pour un livre dont au moins une collection est privée

Bibliothèque standard seulement.
"""
from __future__ import annotations

CONTEXT_COLLECTION = "contexte"
PRIVATE_COLLECTIONS = frozenset({CONTEXT_COLLECTION})


def without_private(names) -> list[str]:
    """Les noms de la liste sans les collections privées, dans l'ordre d'origine."""
    return [name for name in names if name not in PRIVATE_COLLECTIONS]


def shareable(book_collections) -> bool:
    """Vrai quand aucune collection du livre n'est privée : seul un tel livre peut quitter le Mac (envoi futur, R-24)."""
    return not (set(book_collections) & PRIVATE_COLLECTIONS)
