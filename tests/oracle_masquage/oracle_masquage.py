"""Oracle de masquage (change masking-sums, R-144, conception D8) : assistant pur, sans dépendance.

Sur de petites tables brutes (2 à 4 équipes, 2 à 5 colonnes, cellules de 0 à 12), il énumère toutes les tables brutes dont l'image publiée
sous la règle est égale à l'image observée, puis signale les fuites du critère D1 : une cellule masquée (ou une somme de cellules masquées)
qui n'a qu'une seule valeur possible, et une somme déductible sous le seuil. Il rend aussi la largeur de chaque cellule masquée
(plus grande valeur possible moins la plus petite : 0 = valeur exacte, 1 = « 4 ou 5 »).

Une règle est une fonction `publier(table, seuil) -> image` : la table est un tuple de lignes (tuples de comptes), l'image a la même forme,
une cellule masquée valant None. L'attaquant connaît la règle et lit l'image : la table brute est possible si et seulement si son image
est celle observée.

Limite assumée : l'énumération est exhaustive, de l'ordre de |valeurs| ** (lignes x colonnes) tables. Au-delà de quelques cellules, passer un
domaine réduit (`valeurs`) ou une fonction `elaguer(lignes_partielles) -> bool` qui écarte un préfixe de lignes impossible (par exemple une
ligne dont l'image ne peut pas être l'image observée) ; l'oracle ne devine jamais un domaine.
"""
from __future__ import annotations

import itertools
from typing import Callable, Iterable, Sequence

VALEURS = range(13)

Table = tuple
Image = tuple


def _lignes_candidates(forme: Sequence[int], valeurs: Sequence[int], elaguer: Callable | None, prefixe: tuple = ()):
    """Toutes les tables de la forme donnée (liste des largeurs de ligne), par retour arrière sur les lignes."""
    if len(prefixe) == len(forme):
        yield prefixe
        return
    for ligne in itertools.product(valeurs, repeat=forme[len(prefixe)]):
        suite = prefixe + (ligne,)
        if elaguer is not None and not elaguer(suite):
            continue
        yield from _lignes_candidates(forme, valeurs, elaguer, suite)


def tables_compatibles(publier: Callable[[Table, int], Image], brut: Table, seuil: int, valeurs: Iterable[int] = VALEURS,
                       elaguer: Callable | None = None) -> list[Table]:
    """Les tables brutes dont l'image est celle de `brut`."""
    observe = publier(brut, seuil)
    forme = [len(ligne) for ligne in brut]
    return [t for t in _lignes_candidates(forme, tuple(valeurs), elaguer) if publier(t, seuil) == observe]


def cellules_masquees(image: Image) -> list[tuple[int, int]]:
    return [(i, j) for i, ligne in enumerate(image) for j, v in enumerate(ligne) if v is None]


def tables_compatibles_masquees(publier: Callable[[Table, int], Image], brut: Table, seuil: int, domaine: Iterable[int],
                                coherente: Callable | None = None, elaguer: Callable | None = None) -> list[Table]:
    """Variante pour les unités trop grandes pour énumérer toute la table (change masking-sums, groupe 6, D8 amendée le 2026-10-28) : seules les
    cellules brutes masquées dans l'image observée sont énumérées, sur `domaine` (plus large que tout ce que le tirage peut produire, plus le seuil, pour
    que le bord du domaine ne fixe jamais une cellule) ; les cellules publiées sont fixées à leur valeur. Une cellule masquée est une cellule de `brut`
    (les lignes de `brut`) dont l'image est None ; l'image peut avoir d'autres lignes (le produit, dérivé des lignes de `brut`). `coherente(table)` dit
    si une table brute est une table possible des données (relations vraies) ; `elaguer(table_partielle)` écarte un préfixe impossible (les cellules pas
    encore posées valent None). Une table est compatible quand elle est cohérente et que son image est l'image observée."""
    observe = publier(brut, seuil)
    inconnues = [(i, j) for i, ligne in enumerate(observe[:len(brut)]) for j, v in enumerate(ligne) if v is None]
    domaine = tuple(domaine)
    ensemble = set(inconnues)
    depart = tuple(tuple(None if (i, j) in ensemble else v for j, v in enumerate(ligne)) for i, ligne in enumerate(brut))
    resultats: list[Table] = []

    def poser(k: int, table: Table) -> None:
        if k == len(inconnues):
            if (coherente is None or coherente(table)) and publier(table, seuil) == observe:
                resultats.append(table)
            return
        i, j = inconnues[k]
        for v in domaine:
            ligne = table[i][:j] + (v,) + table[i][j + 1:]
            suite = table[:i] + (ligne,) + table[i + 1:]
            if elaguer is None or elaguer(suite):
                poser(k + 1, suite)
    poser(0, depart)
    return resultats


def analyser_masquees(publier: Callable[[Table, int], Image], brut: Table, seuil: int, domaine: Iterable[int], complet: Callable[[Table], Table],
                      coherente: Callable | None = None, elaguer: Callable | None = None, quantites: Callable | None = None) -> dict:
    """Analyse d'une unité par ses seules cellules masquées. `complet(table)` rend la table brute à la forme de l'image (les lignes dérivées, comme le
    produit, ajoutées), pour lire la valeur possible de chaque cellule masquée de l'image. `quantites(table)` rend des quantités cachées que le critère
    protège aussi (un excès, par exemple) : {nom: valeur}. Rend {"compatibles", "intervalles", "largeurs", "fuites", "etroites", "plus_etroite",
    "quantites"}. Fuites : une cellule masquée ou une quantité cachée sous le seuil qui n'a qu'une seule valeur possible."""
    compatibles = tables_compatibles_masquees(publier, brut, seuil, domaine, coherente, elaguer)
    observe = publier(brut, seuil)
    complets = [complet(t) for t in compatibles]
    intervalles, largeurs, fuites = {}, {}, []
    for i, j in cellules_masquees(observe):
        possibles = {c[i][j] for c in complets}
        if not possibles:
            continue
        intervalles[(i, j)] = (min(possibles), max(possibles))
        largeurs[(i, j)] = max(possibles) - min(possibles)
        if largeurs[(i, j)] == 0:
            fuites.append(f"valeur unique : cellule {(i, j)} = {min(possibles)}")
    sorties_quantites: dict = {}
    if quantites is not None and compatibles:
        par_nom: dict = {}
        for t in compatibles:
            for nom, valeur in quantites(t).items():
                par_nom.setdefault(nom, set()).add(valeur)
        for nom, possibles in par_nom.items():
            sorties_quantites[nom] = (min(possibles), max(possibles))
            if len(possibles) == 1 and next(iter(possibles)) < seuil:
                fuites.append(f"quantité cachée sous le seuil à valeur unique : {nom} = {next(iter(possibles))}")
    return {"compatibles": len(compatibles), "intervalles": intervalles, "largeurs": largeurs, "fuites": fuites,
            "etroites": sum(1 for w in largeurs.values() if w == 1),
            "plus_etroite": min(largeurs.values()) if largeurs else None, "quantites": sorties_quantites}


def analyser(publier: Callable[[Table, int], Image], brut: Table, seuil: int, valeurs: Iterable[int] = VALEURS,
             elaguer: Callable | None = None, taille_max_somme: int | None = None, cellules_en_plus: Callable | None = None) -> dict:
    """Analyse de la publication de `brut` : {"compatibles": nombre de tables, "intervalles": {(i, j): (min, max)}, "largeurs": {(i, j): max - min},
    "fuites": [description, ...], "etroites": nombre de cellules d'une unité de large, "plus_etroite": plus petite largeur ou None}.
    Fuites : « valeur unique » (une cellule masquée n'a qu'une valeur), « somme unique sous le seuil » (une somme d'au moins deux cellules masquées
    n'a qu'une valeur, et elle est sous le seuil). Une somme unique au seuil ou au-dessus est permise."""
    valeurs = tuple(valeurs)
    compatibles = tables_compatibles(publier, brut, seuil, valeurs, elaguer)
    image = publier(brut, seuil)
    masquees = cellules_masquees(image)
    if cellules_en_plus is not None:    # change masking-sums D17 : `cellules_en_plus(image)` rend d'autres cellules à analyser (les lignes retirées, « absentes »)
        masquees = masquees + [c for c in cellules_en_plus(image) if c not in masquees]
    intervalles, largeurs, fuites = {}, {}, []
    for i, j in masquees:
        possibles = {t[i][j] for t in compatibles}
        intervalles[(i, j)] = (min(possibles), max(possibles))
        largeurs[(i, j)] = max(possibles) - min(possibles)
        if largeurs[(i, j)] == 0:
            fuites.append(f"valeur unique : cellule {(i, j)} = {min(possibles)}")
    limite = len(masquees) if taille_max_somme is None else min(taille_max_somme, len(masquees))
    for taille in range(2, limite + 1):
        for groupe in itertools.combinations(masquees, taille):
            sommes = {sum(t[i][j] for i, j in groupe) for t in compatibles}
            if len(sommes) == 1 and next(iter(sommes)) < seuil:
                fuites.append(f"somme unique sous le seuil : cellules {groupe} = {next(iter(sommes))}")
    return {"compatibles": len(compatibles), "intervalles": intervalles, "largeurs": largeurs, "fuites": fuites,
            "etroites": sum(1 for w in largeurs.values() if w == 1),
            "plus_etroite": min(largeurs.values()) if largeurs else None}
