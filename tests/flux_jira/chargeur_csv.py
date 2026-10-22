"""Chargeur de test des fixtures CSV (change database-only, D11, tâches 4.1 et 8.1) : transforme les textes CSV et les caches JSON des
fixtures en structures que rendent les lecteurs de la base (tools/flow_store.py). Importé par les tests seulement : aucun module du
produit ne l'importe, et le produit n'a plus aucun lecteur de CSV ni de cache.

    lire_tickets_flux(settings, chemins)  ->  (tickets, found, illisibles, doublons), comme flow_store.lire_tickets_flux
    lire_dependances(settings, chemins)   ->  le dictionnaire de flow_store.lire_dependances
    lire_historique(settings, chemin)     ->  {CLÉ_MAJUSCULES: [[date ISO, départ, arrivée], ...]}, comme flow_store.lire_historique
    lire_epics_depuis_csv(settings, chemins, chemin_cache)  ->  les éléments de flow_store.lire_epics, depuis un CSV et un cache

Le code de lecture des fichiers (colonnes, dates à la minute, fusion par clé) est celui que les outils de rapport avaient avant le change :
il est ici pour que les calculs de rapport gardent leurs fixtures CSV et tournent sans base de données.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import history_common as commun  # noqa: E402

FORMAT_DATE = "%d/%b/%Y %H:%M"            # format fixe des dates des CSV de l'ancien export de l'API (09/Nov/2017 08:49)
CLE = re.compile(r"\b[A-Z][A-Z0-9_]+-\d+\b")
COLONNES_PAR_DEFAUT_DEPENDANCES = {"cle": ["Issue key"], "type": ["Issue Type"], "etat": ["Status"], "categorie": ["Status Category"],
                                   "cree": ["Created"], "resolu": ["Resolved"], "motif": ["Resolution"],
                                   "debut": ["Status Category Changed"], "equipe": ["Team"], "parent": ["Parent key"]}


def parse_moment(valeur: str) -> dt.datetime | None:
    """Date et heure (à la minute) d'une cellule de CSV, None si elle est vide ou illisible."""
    try:
        return dt.datetime.strptime((valeur or "").strip(), FORMAT_DATE)
    except ValueError:
        return None


def parse_jour(valeur: str) -> dt.date | None:
    moment = parse_moment(valeur)
    return moment.date() if moment else None


# ---------------------------------------------------------------------------
# Tickets du rapport de flux
# ---------------------------------------------------------------------------

def lire_export_flux(chemin: Path, settings: dict) -> tuple[list[dict], dict[str, str | None], int]:
    """Tickets réduits au type, à l'état et aux dates, avec les colonnes trouvées et le nombre de lignes illisibles."""
    with chemin.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        found: dict[str, str | None] = {}
        index: dict[str, int] = {}
        normalized = [h.strip().casefold() for h in header]
        for field, names in settings["colonnes"].items():
            position = next((normalized.index(n.strip().casefold()) for n in names
                             if n.strip().casefold() in normalized), None)
            if position is None and field == "equipe":
                position = next((i for i, h in enumerate(normalized) if "team" in h and h.endswith("(label)")),
                                next((i for i, h in enumerate(normalized) if "team" in h), None))
            found[field] = header[position] if position is not None else None
            if position is not None:
                index[field] = position
        colonnes_equipe = ([i for i, h in enumerate(normalized) if h == normalized[index["equipe"]]]
                           if "equipe" in index else [])
        separateur = settings.get("separateur_equipes") or ";"
        if "etat" not in index or "cree" not in index:
            sys.exit("colonnes introuvables")
        tickets, unreadable = [], 0
        for row in reader:
            def cell(field: str) -> str:
                position = index.get(field)
                return row[position] if position is not None and position < len(row) else ""
            created = parse_jour(cell("cree"))
            if created is None:
                unreadable += 1
                continue
            cle = cell("cle").strip()
            premiere = next((v.strip() for v in cell("equipe").split(separateur) if v.strip()), "")
            equipes = []
            for position in colonnes_equipe:
                for valeur in (row[position].split(separateur) if position < len(row) else []):
                    if valeur.strip() and valeur.strip() not in equipes:
                        equipes.append(valeur.strip())
            tickets.append({
                "cle": cle, "projet": cle.rsplit("-", 1)[0].upper() if "-" in cle else "",
                "categorie": cell("categorie").strip().casefold(), "type": cell("type").strip() or "?",
                "etat": cell("etat").strip(), "cree": created, "resolu": parse_jour(cell("resolu")),
                "resolu_a": parse_moment(cell("resolu")),
                "debut": parse_jour(cell("debut")), "equipe": premiere or "(sans équipe)", "equipes": equipes,
                "motif": cell("motif").strip(),
            })
    return tickets, found, unreadable


def lire_tickets_flux(settings: dict, chemins: list[str]):
    """Un ou plusieurs exports ; avec plusieurs, fusion par clé (le dernier fichier l'emporte)."""
    lus = [lire_export_flux(Path(chemin).expanduser(), settings) for chemin in chemins]
    if len(lus) == 1:
        return lus[0][0], lus[0][1], lus[0][2], 0
    found: dict[str, str | None] = {}
    for _, f, _ in lus:
        for champ, nom in f.items():
            found[champ] = found.get(champ) or nom
    tickets, place, doublons = [], {}, 0
    for fichier_tickets, _, _ in lus:
        for t in fichier_tickets:
            if t["cle"] and t["cle"] in place:
                tickets[place[t["cle"]]] = t
                doublons += 1
            else:
                if t["cle"]:
                    place[t["cle"]] = len(tickets)
                tickets.append(t)
    return tickets, found, sum(u for _, _, u in lus), doublons


# ---------------------------------------------------------------------------
# Tickets et liens de la carte des dépendances
# ---------------------------------------------------------------------------

def colonnes_liens(header: list[str]) -> tuple[list[tuple[int, str, str]], list[int]]:
    """Colonnes typées (index, type, sens) et colonnes de liens sans type (index)."""
    typees, simples = [], []
    for i, h in enumerate(header):
        bas = h.strip().casefold()
        m = re.match(r"(.*?)\((.+)\)\s*$", h.strip())
        est_lien = "link" in bas or "lien" in bas or "lié" in bas or "liés" in bas
        if not est_lien:
            continue
        if m and ("inward" in bas or "outward" in bas or "entrant" in bas or "sortant" in bas):
            sens = "entrant" if ("inward" in bas or "entrant" in bas) else "sortant"
            typees.append((i, m.group(2).strip(), sens))
        else:
            simples.append(i)
    return typees, simples


def lire_export_dependances(chemin: Path, settings: dict) -> dict:
    with chemin.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        normalized = [h.strip().casefold() for h in header]
        index, found = {}, {}
        for field, names in settings["colonnes"].items():
            pos = next((normalized.index(n.strip().casefold()) for n in names if n.strip().casefold() in normalized), None)
            if pos is None and field == "equipe":
                pos = next((i for i, h in enumerate(normalized) if "team" in h and h.endswith("(label)")),
                           next((i for i, h in enumerate(normalized) if "team" in h), None))
            found[field] = header[pos] if pos is not None else None
            if pos is not None:
                index[field] = pos
        if "cle" not in index or "etat" not in index:
            sys.exit("Colonne absente de l'export")
        typees, simples = colonnes_liens(header)
        tickets, liens_bruts = {}, []
        for row in reader:
            def cell(field: str) -> str:
                p = index.get(field)
                return row[p].strip() if p is not None and p < len(row) else ""
            cle = cell("cle")
            if not cle:
                continue
            tickets[cle] = {"type": cell("type") or "?", "etat": cell("etat"), "categorie": cell("categorie").casefold(),
                            "cree": parse_jour(cell("cree")), "resolu": parse_jour(cell("resolu")), "debut": parse_jour(cell("debut")),
                            "motif": cell("motif"), "equipe": cell("equipe") or "(sans équipe)",
                            "parent": (CLE.findall(cell("parent")) or [""])[0]}
            for i, typ, sens in typees:
                if i < len(row):
                    for autre in CLE.findall(row[i]):
                        liens_bruts.append((cle, autre, typ, sens))
            for i in simples:
                if i < len(row):
                    for autre in CLE.findall(row[i]):
                        liens_bruts.append((cle, autre, None, None))
    return {"tickets": tickets, "liens": liens_bruts, "colonnes": found,
            "liens_types": [(header[i], t, s) for i, t, s in typees], "liens_simples": [header[i] for i in simples]}


def lire_dependances(settings: dict, chemins: list[str]) -> dict:
    """Plusieurs exports fusionnés par clé ; la forme du dictionnaire de flow_store.lire_dependances (fichiers : les noms)."""
    total = None
    for chemin in chemins:
        data = lire_export_dependances(Path(chemin).expanduser(), settings)
        taille = len(data["tickets"])
        if total is None:
            total = data
            total["_tailles"] = [taille]
            continue
        total["_tailles"].append(taille)
        total["tickets"].update(data["tickets"])
        total["liens"].extend(data["liens"])
        total["liens_types"].extend(t for t in data["liens_types"] if t not in total["liens_types"])
        total["liens_simples"].extend(t for t in data["liens_simples"] if t not in total["liens_simples"])
        for k, v in data["colonnes"].items():
            total["colonnes"][k] = total["colonnes"].get(k) or v
    total["liens"] = sorted(set(total["liens"]), key=lambda x: (x[0], x[1], x[2] or "", x[3] or ""))
    total["fichiers"] = ["base"]
    total.pop("_tailles", None)
    return total


# ---------------------------------------------------------------------------
# Historique (cache JSON de l'ancienne collecte)
# ---------------------------------------------------------------------------

def lire_historique(settings: dict, chemin: str | None, fuseau: ZoneInfo | None = None):
    """Transitions par clé en majuscules, lues dans un cache JSON de fixture, ramenées dans le fuseau d'export (comme la base)."""
    import lab_paths
    cache = (Path(chemin).expanduser() if chemin
             else lab_paths.resolve_or_exit()["content_root"] / "Flux-Lab" / "historique" / "transitions.json")
    fuseau = fuseau or commun.fuseau_export(settings)
    if not cache.exists():                                   # la base sans historique collecté : aucun ticket « avec historique »
        return {}
    donnees = json.loads(cache.read_text(encoding="utf-8"))      # cache JSON de fixture (le cache de fichier n'existe plus au produit)
    return {str(cle).upper(): [[commun.en_fuseau(d, fuseau), de, vers] for d, de, vers in commun.trier(entree.get("transitions"))]
            for cle, entree in donnees.items() if isinstance(entree, dict)}
