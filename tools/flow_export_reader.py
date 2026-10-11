"""
PMZilla Lab : lecture des CSV de export_jira_api.py pour l'import en base (lot 6, schéma flow).

Rend, pour chaque ticket, une ligne prête pour la base (dates en instants avec fuseau, équipes, liens, story points),
selon le contrat commun du lot 6. Aucune base, aucun réseau : la fonction `lire_exports` ne lit que des fichiers CSV.
Les colonnes et le fuseau viennent de flux.yaml (flux_jira.config), le format des dates est fixe
(history_common.FORMAT_DATE) ; les fonctions de lecture existantes sont réutilisées (history_common.parse_jour, parse_moment ; dependencies_jira.colonnes_liens, CLE).

Un export dont la colonne Updated manque, ou dont une valeur Updated est illisible, est refusé : ErreurExport, dont le
message ne contient que le nom du fichier et le nom de la colonne, jamais une valeur ni une clé de ticket. Il n'y a pas
de repli sur l'instant de l'import (l'import incrémental repose sur cette date).
"""
from __future__ import annotations

import csv
import datetime as dt
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dependencies_jira as dependances   # noqa: E402
import history_common as commun          # noqa: E402

FUSEAU_PAR_DEFAUT = "Europe/Paris"
# colonnes que flux.yaml ne connaît pas par défaut (réglables dans la section colonnes de flux.yaml)
COLONNES_SUPPLEMENTAIRES = {
    "modifie": ["Updated"],
    "story_points": ["Story Points"],
    "parent": ["Parent key"],
}
NOMS_DE_COLONNE = {"cle": "Key", "etat": "Status", "cree": "Created", "modifie": "Updated"}
OBLIGATOIRES = ("cle", "etat", "cree", "modifie")


class ErreurExport(Exception):
    """Export inutilisable. `code` est la clé du message du catalogue, `valeurs` ses champs (nom de fichier et nom de
    colonne seulement)."""

    def __init__(self, code: str, **valeurs):
        super().__init__(code)
        self.code = code
        self.valeurs = valeurs


def fuseau(settings: dict) -> ZoneInfo:
    """Fuseau des dates du CSV (réglage export_timezone, Europe/Paris par défaut), comme export_jira_api.py."""
    nom = str(settings.get("export_fuseau") or FUSEAU_PAR_DEFAUT).strip()
    try:
        return ZoneInfo(nom)
    except (ZoneInfoNotFoundError, ValueError):
        raise ErreurExport("timezone_unknown") from None


def instant(valeur: str, zone: ZoneInfo) -> dt.datetime | None:
    """Date d'une cellule de l'export en instant (date locale du fuseau d'export). None si la cellule est vide ou
    illisible."""
    moment = commun.parse_moment(valeur)
    return moment.replace(tzinfo=zone) if moment else None


def points(valeur: str) -> Decimal | None:
    """Story points : nombre entier ou décimal (virgule acceptée) ; vide ou illisible : None."""
    texte = (valeur or "").strip().replace(",", ".")
    if not texte:
        return None
    try:
        nombre = Decimal(texte)
    except InvalidOperation:
        return None
    return nombre if nombre.is_finite() else None


def colonnes_de(settings: dict) -> dict[str, list[str]]:
    return {**COLONNES_SUPPLEMENTAIRES, **settings["colonnes"]}


def lire_export(chemin: Path, settings: dict) -> tuple[dict[str, dict], int, bool]:
    """(tickets par clé, nombre de lignes illisibles écartées, présence de colonnes de liens). Lève ErreurExport."""
    zone = fuseau(settings)
    nom_fichier = chemin.name
    try:
        handle = chemin.open(encoding="utf-8-sig", newline="")
    except OSError:
        raise ErreurExport("file_unreadable", file=nom_fichier) from None
    with handle:
        lecteur = csv.reader(handle)
        entete = next(lecteur, None)
        if entete is None:
            raise ErreurExport("file_empty", file=nom_fichier)
        normalises = [h.strip().casefold() for h in entete]
        index: dict[str, int] = {}
        for champ, noms in colonnes_de(settings).items():
            position = next((normalises.index(n.strip().casefold()) for n in noms
                             if n.strip().casefold() in normalises), None)
            if position is None and champ == "equipe":
                position = next((i for i, h in enumerate(normalises) if "team" in h and h.endswith("(label)")),
                                next((i for i, h in enumerate(normalises) if "team" in h), None))
            if position is not None:
                index[champ] = position
        for champ in OBLIGATOIRES:
            if champ not in index:
                raise ErreurExport("column_missing", file=nom_fichier, column=NOMS_DE_COLONNE[champ])
        colonnes_equipe = ([i for i, h in enumerate(normalises) if h == normalises[index["equipe"]]]
                           if "equipe" in index else [])
        separateur = settings.get("separateur_equipes") or ";"
        typees, simples = dependances.colonnes_liens(entete)
        nom_modifie = entete[index["modifie"]]
        tickets: dict[str, dict] = {}
        illisibles = 0
        for ligne in lecteur:
            def cellule(champ: str) -> str:
                position = index.get(champ)
                return ligne[position].strip() if position is not None and position < len(ligne) else ""
            cle = cellule("cle")
            cree = instant(cellule("cree"), zone)
            if not cle or cree is None:
                illisibles += 1
                continue
            modifie = instant(cellule("modifie"), zone)
            if modifie is None:
                raise ErreurExport("updated_unreadable", file=nom_fichier, column=nom_modifie)
            equipes: list[str] = []
            for position in colonnes_equipe:
                for valeur in (ligne[position].split(separateur) if position < len(ligne) else []):
                    if valeur.strip() and valeur.strip() not in equipes:
                        equipes.append(valeur.strip())
            liens: list[tuple[str, str, str | None]] = []
            for i, type_lien, sens in typees:
                if i < len(ligne):
                    for autre in dependances.CLE.findall(ligne[i]):
                        liens.append((autre, type_lien, "inward" if sens == "entrant" else "outward"))
            for i in simples:
                if i < len(ligne):
                    for autre in dependances.CLE.findall(ligne[i]):
                        liens.append((autre, "", None))
            tickets[cle] = {
                "cle": cle,
                "projet": cle.rsplit("-", 1)[0].upper() if "-" in cle else "",
                "type": cellule("type") or "?",
                "etat": cellule("etat"),
                "categorie": cellule("categorie") or None,
                "cree": cree,
                "resolu": instant(cellule("resolu"), zone),
                "motif": cellule("motif") or None,
                "debut": instant(cellule("debut"), zone),
                "points": points(cellule("story_points")),
                "modifie": modifie,
                "parent": (dependances.CLE.findall(cellule("parent")) or [None])[0],
                "equipes": equipes,
                # None : l'export n'a aucune colonne de liens, les liens déjà en base ne sont pas touchés
                "liens": list(dict.fromkeys(liens)) if (typees or simples) else None,
            }
    return tickets, illisibles, bool(typees or simples)


def lire_exports(chemins: list[str], settings: dict) -> dict:
    """Un ou plusieurs exports, fusionnés par clé (le dernier fichier l'emporte). Rend
    {"tickets": [lignes], "illisibles": n, "colonnes_liens": bool}."""
    fusion: dict[str, dict] = {}
    illisibles, avec_liens = 0, False
    for chemin in chemins:
        tickets, ecartes, liens = lire_export(Path(chemin).expanduser(), settings)
        fusion.update(tickets)
        illisibles += ecartes
        avec_liens = avec_liens or liens
    return {"tickets": list(fusion.values()), "illisibles": illisibles, "colonnes_liens": avec_liens}
