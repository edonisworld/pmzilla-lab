# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "psycopg[binary]"]
# ///
"""
PMZilla Lab : carte des dépendances entre équipes, à partir d'un export CSV de Jira, ou de la base (lot 6).

Comme flux_jira.py, le script ne garde que le type, l'état, l'équipe, les dates et les liens de
chaque ticket. Les clés servent seulement à relier les tickets entre eux, en mémoire : elles ne
sont jamais écrites dans le rapport (option --keys pour les afficher dans le Terminal seulement).
Ni titre, ni description, ni personne ne sont lus.

    uv run dependencies_jira.py diagnose <export.csv>
        Colonnes reconnues, format des liens (avec ou sans type), types de liens et leur nombre,
        part des liens qui pointent vers un ticket absent de l'export. Aucune clé affichée.

    uv run dependencies_jira.py compute <export.csv> [--name perimetre] [--weeks 26] [--keys] [--by team|project|mission-team|site]
        Matrice des dépendances entre équipes, blocages en cours, graphe Mermaid, effet des
        dépendances externes sur le lead time. Écrit Flux-Lab/rapports/dependances-<nom>-AAAA-MM-JJ.md
        (et .json). Avec --by mission-team ou --by site, les équipes sont regroupées d'après le référentiel
        d'organisation (Flux-Lab/organisation.yaml) : matrices, blocages et graphe sont entre groupes, les équipes
        que le référentiel ne décrit pas forment le groupe « hors référentiel », une dépendance entre deux équipes
        d'un même groupe est dite interne au groupe. Le rapport porte l'agrégation dans son nom
        (dependances-<nom>-mission-team-AAAA-MM-JJ.md) et ne divise rien par un effectif. Référentiel absent ou
        invalide : code de sortie 1, aucun rapport.

    uv run dependencies_jira.py diagnose|compute --source db [...]
        Lit tickets et liens dans le schéma flow de la base (rôle pmzilla_flow_ro, lecture seule) au lieu d'un export CSV :
        aucun fichier à donner, mêmes options, même rapport pour les mêmes données (le rapport nomme la source « base » à la
        place du fichier). Les dates sont lues dans le fuseau export_timezone de flux.yaml. Défaut : --source csv
        (comportement inchangé, sans psycopg). Base injoignable ou rôle absent : message clair, code de sortie 1.

Réglages : Flux-Lab/flux.yaml, le même que flux_jira.py (format des dates, colonnes, états).
Une clé facultative « blocking_link_types » y liste les types de liens qui comptent comme dépendance.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flux_config as cfg
import history_common as commun
from yaml_strict import charger
from dependencies_jira_messages import CATALOGS
from messages import Messages, add_language_option

WORKSPACE = Path(os.environ.get("PMZILLA_LAB_WORKSPACE", "~/PMZilla-Lab/workspace")).expanduser()
FLUX_DIR = WORKSPACE / "Flux-Lab"
CONFIG_FILE = FLUX_DIR / "flux.yaml"
REPORT_DIR = FLUX_DIR / "rapports"
MIN_ECHANTILLON = 5       # en dessous, pas de comparaison de lead time
SEUIL_ANCIEN = 365        # blocage en cours depuis plus longtemps : probablement un ticket abandonné, à nettoyer
SANS_ENFANT = "sans enfant de livraison"
FENETRE_ACTIVITE = 90     # un Epic ancien est « vivant » si un de ses enfants a bougé dans ces derniers jours
SPECIAUX = {"(hors export)", "(sans équipe)"}
ORGANISATION = "organisation.yaml"     # référentiel d'organisation, dans le dossier de flux
GROUPEMENTS = ("mission-team", "site")  # valeurs de --by qui passent par le référentiel


def plus_frequents(compte) -> list:
    """Comme Counter.most_common(), mais départagé par le nom : l'ordre ne dépend pas de l'ordre de lecture des tickets."""
    return sorted(compte.items(), key=lambda e: (-e[1], str(e[0])))


def special(nom: str) -> bool:
    """Côté sans équipe connue : hors export, ou ticket sans équipe (avec ou sans son projet)."""
    return nom in SPECIAUX or nom.startswith("(sans équipe")


def boucles(aretes: set[tuple[str, str]], longueur_max: int = 4) -> list[list[str]]:
    """Cycles simples entre équipes (a attend b attend … attend a), sans doublon de rotation."""
    succ = defaultdict(set)
    for a, b in aretes:
        succ[a].add(b)
    trouves, vus = [], set()
    def chercher(depart: str, courant: str, chemin: list[str]) -> None:
        for suivant in sorted(succ[courant]):
            if suivant == depart and len(chemin) >= 2:
                cle = frozenset(zip(chemin, chemin[1:] + [depart]))
                if cle not in vus:
                    vus.add(cle)
                    trouves.append(list(chemin))
            elif suivant not in chemin and len(chemin) < longueur_max and suivant > depart:
                chercher(depart, suivant, chemin + [suivant])
    for depart in sorted(succ):
        chercher(depart, depart, [depart])
    return sorted(trouves, key=len)
CLE = re.compile(r"\b[A-Z][A-Z0-9_]+-\d+\b")

DEFAULTS = {
    # noms des colonnes : les en-têtes des CSV de export_jira_api.py
    "colonnes": {
        "cle": ["Issue key"],
        "type": ["Issue Type"],
        "etat": ["Status"],
        # facultatif mais recommandé quand l'export mêle plusieurs workflows : To Do / In Progress / Done
        "categorie": ["Status Category"],
        "cree": ["Created"],
        "resolu": ["Resolved"],
        "motif": ["Resolution"],
        "debut": ["Status Category Changed"],
        "equipe": ["Team"],
        # facultatif : clé du parent (Epic d'une story), pour savoir si un Epic ancien vit encore
        "parent": ["Parent key"],
    },
    "etats_en_cours": ["In Progress", "In Review", "Testing"],
    "etats_a_faire": ["Open", "To Do", "Backlog"],
    "motifs_exclus": ["Rejected", "Won't Do", "Duplicate", "Cannot Reproduce", "Obsolete"],
    # types de liens qui comptent comme dépendance (comparés sans casse, sur le nom exact du type).
    # « bloquants » : le sens sortant se lit « bloque » (A blocks B : B attend A).
    # « attente » : le sens sortant se lit « dépend de » (A depends on B : A attend B).
    # À vérifier dans Jira sur un ticket : le libellé affiché du lien dit le sens.
    "types_bloquants": ["Blocks", "Bloque", "Blocage", "Prerequisite", "Prérequis"],
    "types_attente": ["Depends", "Dependance", "Dépendance", "Dependency"],
    # projets Jira dont les liens ne sont pas des dépendances entre équipes (projet d'anomalies, de support…) :
    # comptés à part, hors de la matrice
    "projets_exclus": [],
    # projets du périmètre étudié (vide : tous les projets de l'export). Les autres projets de l'export
    # servent seulement à connaître l'équipe de l'autre côté d'un lien : leurs dépendances internes
    # ne sont pas comptées, et leur lead time non plus.
    "projets_perimetre": [],
    # types de tickets de niveau portefeuille (épopées, initiatives…). Un lien entre un ticket de ces types et
    # un ticket d'un autre niveau relève de la décomposition du backlog : il sort de la carte, compté à part.
    # Un lien entre deux tickets de niveau portefeuille (épopée bloquée par une épopée) reste une dépendance.
    # portfolio_types dans flux.yaml (l'ancien nom types_exclus est refusé).
    "types_portefeuille": [],
}


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------

def config() -> dict:
    lu = {}
    if CONFIG_FILE.exists():
        lu = cfg.to_internal(charger(CONFIG_FILE.read_text(encoding="utf-8"), "flux.yaml"), "flux.yaml")
    settings = {**DEFAULTS, **lu}
    colonnes = {k: list(v) for k, v in DEFAULTS["colonnes"].items()}
    for k, v in (lu.get("colonnes") or {}).items():
        colonnes[k] = list(v) + [n for n in colonnes.get(k, []) if n not in v]
    settings["colonnes"] = colonnes
    return settings


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


def read_exports(paths: list[str], settings: dict, t: Messages | None = None) -> dict:
    """Plusieurs exports (lots de projets, pour rester sous la limite de Jira) fusionnés par clé."""
    total = None
    for chemin in paths:
        data = read_export(Path(chemin).expanduser(), settings, t)
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
    total["fichiers"] = [Path(c).name for c in paths]
    total["tronques"] = [f"{Path(c).name} ({n})" for c, n in zip(paths, total.get("_tailles", [])) if n and n % 1000 == 0]
    return total


SOURCES = ("csv", "db")


def lire_donnees(args: argparse.Namespace, settings: dict, t: Messages) -> dict:
    """Les données de la source choisie : exports CSV (au moins un fichier) ou schéma flow de la base (import tardif :
    la voie CSV ne charge ni psycopg ni flow_store)."""
    source = args.source or "csv"
    if source not in SOURCES:
        sys.exit(t("source_unknown", value=source, allowed=", ".join(SOURCES)))
    if source == "csv":
        return read_exports(args.export, settings, t)
    if args.export:                                   # des fichiers avec la base : refusés, jamais ignorés en silence
        sys.exit(t("source_db_no_files"))
    try:
        import flow_store
        data = flow_store.lire_dependances(settings)
    except Exception as erreur:
        if type(erreur).__name__ != "ErreurBase":
            raise
        sys.exit(t("db_unreachable", detail=str(erreur)))
    data["fichiers"] = [t("source_name")]
    return data


def read_export(path: Path, settings: dict, t: Messages | None = None) -> dict:
    t = t or Messages(CATALOGS)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        normalized = [h.strip().casefold() for h in header]
        index, found = {}, {}
        for field, names in settings["colonnes"].items():
            pos = next((normalized.index(n.strip().casefold()) for n in names
                        if n.strip().casefold() in normalized), None)
            if pos is None and field == "equipe":
                pos = next((i for i, h in enumerate(normalized) if "team" in h and h.endswith("(label)")),
                           next((i for i, h in enumerate(normalized) if "team" in h), None))
            found[field] = header[pos] if pos is not None else None
            if pos is not None:
                index[field] = pos
        if "cle" not in index or "etat" not in index:
            manque = [n for n, f in ((t("missing_key_column"), "cle"), (t("missing_status_column"), "etat")) if f not in index]
            sys.exit(t("exit_missing_column", missing=", ".join(manque), config=CONFIG_FILE))
        typees, simples = colonnes_liens(header)
        tickets, liens_bruts = {}, []
        for row in reader:
            def cell(field: str) -> str:
                p = index.get(field)
                return row[p].strip() if p is not None and p < len(row) else ""
            cle = cell("cle")
            if not cle:
                continue
            tickets[cle] = {
                "type": cell("type") or "?",
                "etat": cell("etat"),
                "categorie": cell("categorie").casefold(),
                "cree": commun.parse_jour(cell("cree")),
                "resolu": commun.parse_jour(cell("resolu")),
                "debut": commun.parse_jour(cell("debut")),
                "motif": cell("motif"),
                "equipe": cell("equipe") or "(sans équipe)",
                "parent": (CLE.findall(cell("parent")) or [""])[0],
            }
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


def role(typ: str | None, settings: dict) -> str | None:
    """« bloque », « attend » ou None (lien ignoré)."""
    if typ is None:
        return None
    t = typ.strip().casefold()
    if t in (b.casefold() for b in settings["types_bloquants"]):
        return "bloque"
    if t in (b.casefold() for b in settings.get("types_attente", [])):
        return "attend"
    return None


def dependances(data: dict, settings: dict) -> tuple[list[tuple[str, str]], list[tuple[str, str]], str]:
    """(bloquant, bloqué) pour les liens typés bloquants ; paires non orientées pour les liens sans type."""
    orientees, non_orientees = set(), set()
    for cle, autre, typ, sens in data["liens"]:
        if cle == autre:
            continue
        if typ is None:
            non_orientees.add(tuple(sorted((cle, autre))))
        else:
            r = role(typ, settings)
            if r is None:
                continue
            # « bloque » sortant : cle bloque autre ; « attend » sortant : cle attend autre (autre bloque cle)
            cle_bloque = (sens == "sortant") == (r == "bloque")
            orientees.add((cle, autre) if cle_bloque else (autre, cle))
    mode = "orienté" if data["liens_types"] else ("non orienté" if data["liens_simples"] else "aucun")
    return sorted(orientees), sorted(non_orientees), mode


def projet(cle: str) -> str:
    return cle.rsplit("-", 1)[0]


def separer_exclus(paires: list[tuple[str, str]], settings: dict) -> tuple[list, Counter]:
    """Retire les liens qui touchent un projet exclu ; compte ceux-ci par projet et par sens."""
    exclus = {p.strip().upper() for p in settings.get("projets_exclus") or []}
    gardees, comptes = [], Counter()
    for a, b in paires:
        pa, pb = projet(a), projet(b)
        if pa in exclus or pb in exclus:
            if pa in exclus and pb not in exclus:
                comptes[(pa, "attendu par l'export")] += 1
            elif pb in exclus and pa not in exclus:
                comptes[(pb, "attend l'export")] += 1
            else:
                comptes[(pa, "interne")] += 1
        else:
            gardees.append((a, b))
    return gardees, comptes


def dans_perimetre(cle: str, settings: dict) -> bool:
    perimetre = {p.strip().upper() for p in settings.get("projets_perimetre") or []}
    return not perimetre or projet(cle) in perimetre


def garder_perimetre(paires: list[tuple[str, str]], settings: dict) -> list[tuple[str, str]]:
    return [(a, b) for a, b in paires if dans_perimetre(a, settings) or dans_perimetre(b, settings)]


def types_portefeuille(settings: dict) -> set[str]:
    return {t.strip().casefold() for t in (settings.get("types_portefeuille") or settings.get("types_exclus") or [])}


def separer_types(paires: list[tuple[str, str]], tickets: dict, settings: dict) -> tuple[list, Counter]:
    """Retire les liens de décomposition : un côté de niveau portefeuille, l'autre non (ou inconnu)."""
    niveau = types_portefeuille(settings)
    if not niveau:
        return paires, Counter()
    haut = lambda k: k in tickets and tickets[k]["type"].casefold() in niveau
    gardees, comptes = [], Counter()
    for a, b in paires:
        if haut(a) != haut(b) or (haut(a) and b not in tickets) or (haut(b) and a not in tickets):
            comptes[tickets[a]["type"] if haut(a) else tickets[b]["type"]] += 1
        else:
            gardees.append((a, b))
    return gardees, comptes


def vitalite_epics(tickets: dict, paires: list, settings: dict, equipe, aujourdhui: dt.date) -> dict | None:
    """Epics (niveau portefeuille) ouverts depuis plus d'un an et pris dans un lien ouvert entre équipes :
    vivants si un enfant (même parent) a changé de catégorie d'état (s'il est ouvert) ou a été livré (s'il est
    terminé) dans les FENETRE_ACTIVITE derniers jours. Ne comptent pas : une clôture sans livraison (rejet,
    annulation : souvent un nettoyage groupé) et un enfant de niveau portefeuille (RN Task…)."""
    niveau = types_portefeuille(settings)
    if not niveau or not any(t["parent"] for t in tickets.values()):
        return None
    exclus_motifs = {m.casefold() for m in settings["motifs_exclus"]} | {"cancelled", "annulé", "canceled"}
    activite: dict[str, dt.date] = {}  # dernière activité connue des enfants de chaque parent
    avec_enfants: set[str] = set()
    for t in tickets.values():
        if not t["parent"] or t["type"].casefold() in niveau:
            continue
        avec_enfants.add(t["parent"])
        if t["resolu"]:
            d_ = t["resolu"] if t["motif"].casefold() not in exclus_motifs else None
        else:
            d_ = t["debut"]
        if d_ and d_ > activite.get(t["parent"], dt.date.min):
            activite[t["parent"]] = d_
    concernes = set()
    for a, b in paires:
        if a in tickets and b in tickets and equipe(a) != equipe(b) \
                and not termine(tickets[a], settings) and not termine(tickets[b], settings):
            concernes.update((a, b))
    lignes, cles = Counter(), defaultdict(list)
    for k in concernes:
        t = tickets[k]
        depuis = t["debut"] or t["cree"]
        if t["type"].casefold() not in niveau or not depuis or (aujourdhui - depuis).days <= SEUIL_ANCIEN:
            continue
        derniere = activite.get(k)
        etat = ("vivant" if derniere and (aujourdhui - derniere).days <= FENETRE_ACTIVITE
                else "enfants inactifs" if k in avec_enfants else SANS_ENFANT)
        lignes[(equipe(k), etat)] += 1
        cles[etat].append(k)
    return {"lignes": [[e, etat, n] for (e, etat), n in sorted(lignes.items(), key=lambda kv: (kv[0][0], kv[0][1]))],
            "_cles": {etat: sorted(ks) for etat, ks in cles.items()}}


def termine(t: dict, settings: dict) -> bool:
    return t["resolu"] is not None


def livre(t: dict, settings: dict) -> bool:
    return termine(t, settings) and t["motif"] not in settings["motifs_exclus"]


CATEGORIES_EN_COURS = {"in progress", "en cours"}
CATEGORIES_A_FAIRE = {"to do", "à faire", "a faire", "new", "nouveau"}


def en_cours(t: dict, settings: dict) -> bool:
    if termine(t, settings):
        return False
    if t["categorie"]:
        return t["categorie"] in CATEGORIES_EN_COURS
    return t["etat"] in settings["etats_en_cours"]


def a_faire(t: dict, settings: dict) -> bool:
    if termine(t, settings):
        return False
    if t["categorie"]:
        return t["categorie"] in CATEGORIES_A_FAIRE
    return t["etat"] in settings["etats_a_faire"]


# ---------------------------------------------------------------------------
# Commandes
# ---------------------------------------------------------------------------

def appliquer_perimetre(settings: dict, valeur: str | None) -> None:
    """--scope surcharge scope_projects de flux.yaml : « tous », ou des clés séparées par des virgules."""
    if valeur:
        settings["projets_perimetre"] = [] if valeur.strip().lower() == "tous" else \
            [v.strip() for v in valeur.split(",") if v.strip()]


def cmd_diagnostic(args: argparse.Namespace) -> None:
    t = Messages(CATALOGS, args.language)
    settings = config()
    appliquer_perimetre(settings, args.perimetre)
    data = lire_donnees(args, settings, t)
    if len(args.export) > 1:
        print(t("merged_exports", n=len(args.export)))
    tickets = data["tickets"]
    print(t("tickets_read", n=len(tickets)))
    print(t("recognized_columns"))
    for k, v in data["colonnes"].items():
        print(f"  {t('col_' + k):7} -> {v or t('column_missing')}")
    if data["liens_types"]:
        groupes = Counter((typ, sens) for _, typ, sens in data["liens_types"])
        print(t("typed_link_columns", n=len(data["liens_types"]), types=len({typ for typ, _ in groupes})))
    if data["liens_simples"]:
        print(t("untyped_link_columns", names=", ".join(data["liens_simples"])))
    if not data["liens_types"] and not data["liens_simples"]:
        print(t("no_link_columns"))
        return
    sans_type = t("no_type")
    types = Counter(typ or sans_type for _, _, typ, _ in data["liens"])
    print(t("links_by_type"))
    for typ, n in plus_frequents(types):
        r = role(None if typ == sans_type else typ, settings)
        drapeau = (t("flag_no_type") if typ == sans_type else
                   t("flag_blocks") if r == "bloque" else
                   t("flag_depends") if r == "attend" else t("flag_ignored"))
        print(f"  {typ:30} {n:5}  {drapeau}")
    orientees, non_orientees, mode = dependances(data, settings)
    paires, exclus = separer_exclus(garder_perimetre(orientees or non_orientees, settings), settings)
    paires, types_ex = separer_types(paires, tickets, settings)
    for typ, n in plus_frequents(types_ex):
        print(t("decomposition_links", type=typ, n=n))
    if settings.get("projets_perimetre"):
        print(t("scope_line", projects=", ".join(settings["projets_perimetre"]),
                n=sum(1 for k in tickets if dans_perimetre(k, settings))))
    for (proj, sens), n in sorted(exclus.items()):
        print(t("excluded_project_links", project=proj, n=n, side=t(SIDES[sens])))
    hors = sum(1 for a, b in paires if a not in tickets or b not in tickets)
    print(t("mode_line", mode=t(MODES[mode]), n=len(paires), outside=hors))
    if hors:
        dedans = {projet(k) for k in tickets}
        sens = defaultdict(Counter)
        for a, b in paires:   # (bloquant, bloqué) en mode orienté
            if a not in tickets:
                sens[projet(a)][t("export_awaits_it")] += 1
            if b not in tickets:
                sens[projet(b)][t("it_awaits_export")] += 1
        print(t("unknown_projects"))
        for proj, c in sorted(sens.items(), key=lambda kv: (-sum(kv[1].values()), kv[0]))[:15]:
            detail = ", ".join(f"{n} {k}" for k, n in plus_frequents(c)) if mode == "orienté" else ""
            print(f"  {proj:12} {sum(c.values()):5}  {detail}" +
                  (t("project_in_export") if proj in dedans else ""))
    if paires and hors / len(paires) > 0.3:
        print(t("over_30_console"))
    ouverts = [x for x in tickets.values() if not termine(x, settings)]
    inconnus = sorted({x["etat"] for x in ouverts if not en_cours(x, settings) and not a_faire(x, settings)})
    if inconnus:
        print(t("unknown_states", n=sum(1 for x in ouverts if x["etat"] in inconnus), states=", ".join(inconnus)))
        if not data["colonnes"].get("categorie"):
            print(t("hint_status_category"))
    if args.source == "csv" and len(tickets) % 1000 == 0:      # un nombre rond trahit un export tronqué, pas la base
        print(t("round_number", n=len(tickets)))
    sans_equipe = sum(1 for k, x in tickets.items() if x["equipe"] == "(sans équipe)" and dans_perimetre(k, settings))
    print(t("tickets_without_team", n=sans_equipe))


def pcts(values: list[int]) -> dict | None:
    if not values:
        return None
    v = sorted(values)
    def p(q: float) -> int:
        return v[min(len(v) - 1, int(round(q * (len(v) - 1))))]
    return {"n": len(v), "p50": p(0.5), "p85": p(0.85)}


def cmd_calcul(args: argparse.Namespace) -> None:
    t = Messages(CATALOGS, args.language)
    settings = config()
    appliquer_perimetre(settings, args.perimetre)
    referentiel = None
    if args.par in GROUPEMENTS:
        # avant toute lecture des données : référentiel absent ou invalide = code 1 (ErreurConfig), aucun rapport
        import flow_organisation as organisation
        referentiel = organisation.charger_fichier(FLUX_DIR / ORGANISATION)
    data = lire_donnees(args, settings, t)
    tickets = data["tickets"]
    orientees, non_orientees, mode = dependances(data, settings)
    orientees, exclus_o = separer_exclus(garder_perimetre(orientees, settings), settings)
    non_orientees, exclus_n = separer_exclus(garder_perimetre(non_orientees, settings), settings)
    exclus = exclus_o + exclus_n
    orientees, types_o = separer_types(orientees, tickets, settings)
    non_orientees, types_n = separer_types(non_orientees, tickets, settings)
    types_exclus = types_o + types_n
    if mode == "aucun":
        sys.exit(t("exit_no_links"))
    aujourdhui = dt.date.today()
    noms = {k.upper(): v for k, v in (settings.get("noms_projets") or {}).items()}
    if args.par == "projet":
        # par projet : la clé suffit à situer l'autre côté, même absent de l'export
        equipe = lambda k: noms.get(projet(k), projet(k))
    else:
        def equipe(k: str) -> str:
            if k not in tickets:
                return "(hors export)"
            nom = tickets[k]["equipe"]
            # sans équipe : on garde le projet, pour savoir d'où viennent ces tickets
            return f"(sans équipe : {noms.get(projet(k), projet(k))})" if nom == "(sans équipe)" else nom
        if referentiel is not None:
            # par Mission Team ou par site : l'équipe devient son groupe ; les côtés sans équipe connue restent tels quels,
            # les équipes que le référentiel ne décrit pas vont dans « hors référentiel »
            equipe_nom, groupes = equipe, {}
            def equipe(k: str) -> str:
                nom = equipe_nom(k)
                if special(nom):
                    return nom
                if nom not in groupes:
                    groupes[nom] = referentiel.group_of(nom, args.par, args.language or "fr")
                return groupes[nom]

    # 1. Matrice : liens ouverts (côté dépendant non terminé)
    # ouverte : les deux côtés sont dans l'export et aucun n'est terminé ;
    # état inconnu : un côté est absent de l'export (peut-être déjà terminé), l'autre n'est pas terminé
    ouvert = lambda k: k in tickets and not termine(tickets[k], settings)
    niveau = types_portefeuille(settings)
    haut = lambda k: k in tickets and tickets[k]["type"].casefold() in niveau
    matrice, matrice_inconnu, matrice_tous, matrice_haut = Counter(), Counter(), Counter(), Counter()
    if mode == "orienté":
        for bloquant, bloque in orientees:
            paire = (equipe(bloque), equipe(bloquant))
            matrice_tous[paire] += 1
            if ouvert(bloque) and ouvert(bloquant):
                matrice[paire] += 1
                if haut(bloque) and haut(bloquant):
                    matrice_haut[paire] += 1
            elif ouvert(bloque) and bloquant not in tickets:
                matrice_inconnu[paire] += 1
    else:
        for a, b in non_orientees:
            paire = tuple(sorted((equipe(a), equipe(b))))
            matrice_tous[paire] += 1
            if ouvert(a) and ouvert(b):
                matrice[paire] += 1
            elif (ouvert(a) and b not in tickets) or (ouvert(b) and a not in tickets):
                matrice_inconnu[paire] += 1

    # 2. Blocages réels : en cours, attend un élément d'une autre équipe non terminé
    blocages, anciens, inconnus, cles_terminal = defaultdict(list), defaultdict(list), defaultdict(list), []
    ages_paire = defaultdict(list)          # (équipe qui attend, équipe attendue) -> âges des éléments en cours bloqués
    if mode == "orienté":
        for bloquant, bloque in orientees:
            if bloque not in tickets or not en_cours(tickets[bloque], settings):
                continue
            tb = tickets.get(bloquant)
            if tb is not None and termine(tb, settings):
                continue
            if equipe(bloquant) == equipe(bloque):
                continue
            etat_bloquant = "hors export" if tb is None else "pas commencé" if a_faire(tb, settings) else "en cours"
            depuis = tickets[bloque]["debut"] or tickets[bloque]["cree"]
            age = (aujourdhui - depuis).days if depuis else None
            cles_terminal.append((bloque, bloquant, etat_bloquant, age))
            if tb is None:
                inconnus[(equipe(bloque), projet(bloquant))].append(age)
                continue
            if age is not None:
                ages_paire[(equipe(bloque), equipe(bloquant))].append(age)
            if age is not None and age > SEUIL_ANCIEN:
                anciens[(equipe(bloque), equipe(bloquant))].append(age)
            else:
                blocages[(equipe(bloque), equipe(bloquant), etat_bloquant)].append((age, depuis, haut(bloque)))

    # 3. Effet sur le lead time des éléments livrés sur la période
    debut_periode = aujourdhui - dt.timedelta(weeks=args.semaines)
    externes = set()
    if mode == "orienté":
        for bloquant, bloque in orientees:
            if equipe(bloquant) != equipe(bloque) and not special(equipe(bloquant)):
                externes.add(bloque)
    else:
        for a, b in non_orientees:
            if equipe(a) != equipe(b) and not special(equipe(a)) and not special(equipe(b)):
                externes.update((a, b))
    exclus_types = types_portefeuille(settings)
    par_type = defaultdict(lambda: ([], []))
    for k, x in tickets.items():
        if (dans_perimetre(k, settings) and livre(x, settings) and x["cree"] and x["resolu"] >= debut_periode
                and x["type"].casefold() not in exclus_types):
            par_type[x["type"]][0 if k in externes else 1].append((x["resolu"] - x["cree"]).days)
    lt = {"par_type": [[typ, pcts(av), pcts(sa)] for typ, (av, sa) in
                       sorted(par_type.items(), key=lambda kv: (-len(kv[1][0]), kv[0]))]}

    vitalite = vitalite_epics(tickets, orientees if mode == "orienté" else [], settings, equipe, aujourdhui)
    cles_epics = vitalite.pop("_cles", {}) if vitalite else {}

    nom = args.nom
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    # par groupe : aucune liste classée par un chiffre, tout est par ordre de nom
    ordre = plus_frequents if referentiel is None else (lambda compte: sorted(compte.items(), key=lambda e: str(e[0])))
    par_nom = referentiel is not None
    suffixe = "-projets" if args.par == "projet" else f"-{args.par}" if referentiel is not None else ""
    stem = REPORT_DIR / f"dependances-{nom}{suffixe}-{aujourdhui.isoformat()}"
    par_groupe = {}
    if referentiel is not None:
        # résumé de structure (seul endroit où paraît un effectif) et dépendances internes de chaque groupe, ordre par nom
        tickets_groupe = Counter(equipe(k) for k in tickets if dans_perimetre(k, settings))
        internes_groupe = Counter({a: n for (a, b), n in matrice_tous.items() if a == b})
        noms_groupes = sorted({g["group"] for g in referentiel.structure_summary(args.par, args.language or "fr")}
                              | {g for g in tickets_groupe if not special(g)})
        par_groupe = {"structure": referentiel.structure_summary(args.par, args.language or "fr"),
                      "dependances_internes": [[g, internes_groupe.get(g, 0)] for g in noms_groupes]}
    rapport = {
        "nom": nom, "date": aujourdhui.isoformat(), "export": ", ".join(data["fichiers"]), "mode": mode,
        "par": args.par,
        "tronques": data.get("tronques", []),
        "tickets": len(tickets), "semaines": args.semaines,
        "dependances": len(orientees) if mode == "orienté" else len(non_orientees),
        "hors_export": sum(1 for a, b in (orientees or non_orientees) if a not in tickets or b not in tickets),
        "matrice_ouverte": [[a, b, n] for (a, b), n in ordre(matrice)],
        "matrice_portefeuille": [[a, b, n] for (a, b), n in ordre(matrice_haut)],
        "matrice_inconnue": [[a, b, n] for (a, b), n in ordre(matrice_inconnu)],
        "matrice_totale": [[a, b, n] for (a, b), n in ordre(matrice_tous)],
        # une entrée par paire, pour le tableau de bord (graphe) : de = l'équipe qui attend, vers = l'équipe attendue
        "aretes": [{"de": a, "vers": b, "ouvertes": matrice.get((a, b), 0), "inconnues": matrice_inconnu.get((a, b), 0),
                    "toutes": n, "entre_epics": matrice_haut.get((a, b), 0),
                    "bloquees_en_cours": len(ages_paire.get((a, b), [])),
                    "age_bloquees": pcts(ages_paire.get((a, b), [])), "oriente": mode == "orienté"}
                   for (a, b), n in sorted(matrice_tous.items())],
        "equipes_tickets": dict(sorted(Counter(equipe(k) for k in tickets if dans_perimetre(k, settings)).items())),
        "attentes_inconnues": [[a, proj, len(v), pcts([x for x in v if x is not None])]
                               for (a, proj), v in sorted(inconnus.items(), key=lambda kv: (-len(kv[1]), str(kv[0])))],
        "blocages": [[a, b, e, len(v), pcts([x[0] for x in v if x[0] is not None]),
                      max(Counter(x[1] for x in v if x[1] is not None).values(), default=0), sum(1 for x in v if x[2])]
                     for (a, b, e), v in sorted(blocages.items(), key=lambda kv: (str(kv[0]) if par_nom else (-len(kv[1]), str(kv[0]))))],
        "blocages_anciens": [[a, b, len(v), max(v)] for (a, b), v in sorted(anciens.items(), key=lambda kv: (str(kv[0]) if par_nom else (-len(kv[1]), str(kv[0]))))],
        "epics_anciens": vitalite,
        "boucles": boucles({(a, b) for (a, b), n in matrice.items() if n and a != b and not special(a) and not special(b)})
                   if mode == "orienté" else [],
        "tickets_perimetre": sum(1 for k in tickets if dans_perimetre(k, settings)),
        "lead_time": lt,
        "exclus": [[p, sens, n] for (p, sens), n in sorted(exclus.items())],
        "types_exclus": [[t, n] for t, n in plus_frequents(types_exclus)],
        **par_groupe,
    }
    stem.with_suffix(".json").write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
    stem.with_suffix(".md").write_text(rendu(rapport, t), encoding="utf-8")
    print(t("report_line", path=stem.with_suffix(".md")))
    if args.cles and cles_epics:
        douteux = cles_epics.get(SANS_ENFANT, []) + cles_epics.get("enfants inactifs", [])
        if douteux:
            print(t("old_epics_jira", n=len(douteux)))
            print(f"  parent in ({', '.join(sorted(douteux))}) ORDER BY updated DESC")
    if args.cles:
        print(t("blockages_terminal_header"))
        for bloque, bloquant, etat, age in sorted(cles_terminal, key=lambda x: (-(x[3] or 0), str(x[0]), str(x[1]))):
            if referentiel is not None:        # aucun nom de groupe en console
                print(t("blockage_terminal_line_group", blocked=bloque, blocking=bloquant, state=t(STATES[etat]), age=age))
            else:
                print(t("blockage_terminal_line", blocked=bloque, blocked_team=team_label(equipe(bloque), t), blocking=bloquant,
                        blocking_team=team_label(equipe(bloquant), t), state=t(STATES[etat]), age=age))


SIDES = {"attendu par l'export": "side_awaited_by_export", "attend l'export": "side_waits_for_export",
         "interne": "side_internal"}                      # valeurs du JSON (françaises) -> clé du catalogue
STATES = {"hors export": "state_outside_export", "pas commencé": "state_not_started", "en cours": "state_in_progress"}
MODES = {"orienté": "mode_oriented", "non orienté": "mode_unoriented", "aucun": "mode_none"}
SANS_EQUIPE_PROJET = re.compile(r"^\(sans équipe : (.*)\)$")


def team_label(nom: str, t: Messages) -> str:
    """Nom d'équipe tel qu'il s'affiche : les valeurs spéciales du JSON (françaises) sont traduites."""
    if nom == "(hors export)":
        return t("team_outside_export")
    if nom == "(sans équipe)":
        return t("team_without_team")
    m = SANS_EQUIPE_PROJET.match(nom)
    return t("team_without_team_project", project=m.group(1)) if m else nom


def mermaid_id(nom: str, ids: dict) -> str:
    if nom not in ids:
        ids[nom] = f"E{len(ids) + 1}"
    return ids[nom]


def rendu(r: dict, t: Messages | None = None) -> str:
    t = t or Messages(CATALOGS)
    n_ = lambda nom: team_label(nom, t)                      # nom d'équipe affiché
    d_ = lambda v: t("days_value", v=v)
    oriente = r["mode"] == "orienté"
    L = [t("title", name=r["nom"], date=r["date"]), "",
         t("summary", export=r["export"], tickets=r["tickets"], deps=r["dependances"],
           kind=t("kind_oriented" if oriente else "kind_unoriented"), outside=r["hors_export"]), ""]
    if r.get("par") in GROUPEMENTS:
        L += ["\x00GROUPE"]               # remplacé après les échanges de mots : le texte des groupes les évite
    if not oriente:
        L += [t("note_untyped"), ""]
    if r.get("tronques"):
        L += [t("note_truncated", files=", ".join(r["tronques"])), ""]
    for typ, n in r.get("types_exclus", []):
        L += [t("note_decomposition", type=typ, n=n), ""]
    for p, sens, n in r.get("exclus", []):
        L += [t("note_excluded", project=p, n=n, side=t(SIDES[sens])), ""]
    if r["dependances"] and r["hors_export"] / r["dependances"] > 0.3:
        L += [t("note_outside"), ""]

    tous = {(a, b): n for a, b, n in r["matrice_totale"]}
    ouverts = {(a, b): n for a, b, n in r["matrice_ouverte"]}
    inconnues = {(a, b): n for a, b, n in r.get("matrice_inconnue", [])}
    ouverts_ext = {k: n for k, n in ouverts.items() if k[0] != k[1] and n}
    par_groupe_ = r.get("par") in GROUPEMENTS          # pas de « paire la plus chargée » : ce serait un classement
    L += [t("sec_brief"), ""]
    L.append(t("brief_open", n=sum(ouverts_ext.values()), pairs=len(ouverts_ext),
               tickets=r.get("tickets_perimetre", r["tickets"])))
    if inconnues:
        L.append(t("brief_unknown", n=sum(inconnues.values())))
    if ouverts_ext and not par_groupe_:
        (a, b), n = max(ouverts_ext.items(), key=lambda kv: kv[1])
        part = round(100 * n / sum(ouverts_ext.values()))
        L.append(t("brief_busiest_oriented", a=n_(a), b=n_(b), n=n, part=part) if oriente
                 else t("brief_busiest_unoriented", a=n_(a), b=n_(b), n=n, part=part))
    if oriente:
        en_cours_n = sum(x[3] for x in r["blocages"])
        anc = r.get("blocages_anciens", [])
        L.append(t("brief_waiting_old", n=en_cours_n, old=sum(x[2] for x in anc)) if anc
                 else t("brief_waiting", n=en_cours_n))
        if r.get("boucles"):
            L.append(t("brief_loops", n=len(r["boucles"])))
    L += [""]

    L += [t("sec_who"), ""]
    if oriente:
        L += [t("who_reading_oriented"), ""]
    else:
        L += [t("who_reading_unoriented"), ""]
    par_groupe = r.get("par") in GROUPEMENTS          # par groupe : ordre par nom, jamais par un chiffre
    externes = sorted(((a, b) for (a, b) in tous if a != b),
                      key=(lambda p: p) if par_groupe else (lambda p: (-ouverts.get(p, 0), -inconnues.get(p, 0), -tous[p])))
    internes = sum(n for (a, b), n in tous.items() if a == b)
    if externes:
        L += [t("head_matrix_oriented" if oriente else "head_matrix_unoriented"), "|---|---|---|---|---|---|"]
        hauts = {(a, b): n for a, b, n in r.get("matrice_portefeuille", [])}
        L += [f"| {n_(a)} | {n_(b)} | {ouverts.get((a, b), 0)} | {hauts.get((a, b), 0)} | {inconnues.get((a, b), 0)} | {tous[(a, b)]} |"
              for a, b in externes]
    else:
        L += [t("no_externals")]
    if r.get("par") in GROUPEMENTS:
        L += ["", t("internal_dependencies_group", n=internes), ""]
    else:
        L += ["", t("internal_dependencies", n=internes), ""]

    graphe = [(a, b) for a, b in externes if ouverts.get((a, b), 0)]
    if graphe:
        ids: dict = {}
        L += [t("sec_graph"), "", "```mermaid", "graph LR"]
        for a, b in graphe:
            n_o = ouverts[(a, b)]
            if oriente:
                L.append(f'  {mermaid_id(n_(b), ids)}["{n_(b)}"] -->|{n_o}| {mermaid_id(n_(a), ids)}["{n_(a)}"]')
            else:
                L.append(f'  {mermaid_id(n_(a), ids)}["{n_(a)}"] ---|{n_o}| {mermaid_id(n_(b), ids)}["{n_(b)}"]')
        L += ["```", "", t("graph_legend_oriented") if oriente else t("graph_legend_unoriented"), ""]

    if oriente and r.get("boucles"):
        L += [t("sec_loops"), "", t("loops_intro"), ""]
        L += ["- " + t("loop_joiner").join(n_(x) for x in c + [c[0]]) for c in r["boucles"]]
        L += ["", t("loops_closing"), ""]

    if oriente:
        L += [t("sec_blockages"), "", t("blockages_intro"), ""]
        if r["blocages"]:
            L += [t("head_blockages"), "|---|---|---|---|---|---|---|---|"]
            groupes = []
            for ligne in (sorted(r["blocages"], key=lambda x: tuple(map(str, x[:3]))) if par_groupe else r["blocages"]):
                a, b, e, n, p = ligne[:5]
                meme, epics = (ligne[5], ligne[6]) if len(ligne) > 6 else (1, 0)
                drapeau = t("same_date_flag", same=meme, n=n) if n >= 3 and meme >= max(3, n / 2) else ""
                if drapeau:
                    groupes.append(t("pair_waits", a=n_(a), b=n_(b)))
                L.append(f"| {n_(a)} | {n_(b)} | {t(STATES[e])} | {n} | {epics} | {d_(p['p50'] if p else '?')} | "
                         f"{d_(p['p85'] if p else '?')} | {drapeau} |")
            L += ["", t("blockages_note"), ""]
            if groupes:
                L += [t("batch_warning", groups=" ; ".join(groupes)), ""]
        else:
            L += [t("none_waiting"), ""]
        if r.get("attentes_inconnues"):
            L += [t("sec_unknown_waits"), "", t("unknown_waits_intro"), "",
                  t("head_unknown_waits"), "|---|---|---|---|---|"]
            for a, proj, n, p in (sorted(r["attentes_inconnues"], key=lambda x: (str(x[0]), str(x[1])))
                                  if par_groupe else r["attentes_inconnues"]):
                L.append(f"| {n_(a)} | {proj} | {n} | {d_(p['p50'] if p else '?')} | {d_(p['p85'] if p else '?')} |")
            L += [""]
        va = r.get("epics_anciens")
        if va and va["lignes"]:
            par_equipe = defaultdict(Counter)
            for e, etat, n in va["lignes"]:
                par_equipe[e][etat] += n
            total = Counter()
            for c in par_equipe.values():
                total.update(c)
            L += [t("sec_old_epics"), "", t("old_epics_intro", old=SEUIL_ANCIEN, window=FENETRE_ACTIVITE), "",
                  t("old_epics_total", alive=total["vivant"], inactive=total["enfants inactifs"], none=total[SANS_ENFANT]), "",
                  t("head_old_epics"), "|---|---|---|---|"]
            for e, c in sorted(par_equipe.items(), key=lambda kv: kv[0] if par_groupe else (-sum(kv[1].values()), kv[0])):
                L.append(f"| {n_(e)} | {c['vivant']} | {c['enfants inactifs']} | {c[SANS_ENFANT]} |")
            L += [""]
        if r.get("blocages_anciens"):
            L += [t("sec_old_blockages"), "", t("old_blockages_intro", old=SEUIL_ANCIEN), "",
                  t("head_old_blockages"), "|---|---|---|---|"]
            L += [f"| {n_(a)} | {n_(b)} | {n} | {d_(m)} |"
                  for a, b, n, m in (sorted(r["blocages_anciens"], key=lambda x: (str(x[0]), str(x[1])))
                                     if par_groupe else r["blocages_anciens"])]
            L += [""]

    lt = r["lead_time"]
    L += [t("sec_lead_time", weeks=r["semaines"]), "", t("lead_time_intro", min=MIN_ECHANTILLON), ""]
    lignes = [(typ, a, s_) for typ, a, s_ in lt.get("par_type", [])
              if a and s_ and a["n"] >= MIN_ECHANTILLON and s_["n"] >= MIN_ECHANTILLON]
    if lignes:
        L += [t("head_lead_time"), "|---|---|---|---|---|---|---|"]
        L += [f"| {typ} | {a['n']} | {d_(a['p50'])} | {d_(a['p85'])} | {s_['n']} | {d_(s_['p50'])} | {d_(s_['p85'])} |"
              for typ, a, s_ in lignes]
        petits = [typ for typ, a, _ in lignes if a["n"] < 30]
        L += ["", t("lead_time_correlation") + (t("lead_time_fragile", types=", ".join(petits)) if petits else ""), ""]
    else:
        tailles = ", ".join(f"{typ} {a['n'] if a else 0}/{s_['n'] if s_ else 0}" for typ, a, s_ in lt.get("par_type", [])[:5])
        L += [t("lead_time_none", sizes=tailles or t("none_word")), ""]
    texte = "\n".join(L)
    if r.get("par") == "projet":
        for i in range(1, 12):
            texte = texte.replace(t(f"swap_{i}_from"), t(f"swap_{i}_to"))
    elif r.get("par") in GROUPEMENTS:
        cle = {"mission-team": "swap_mt", "site": "swap_site"}[r["par"]]
        for i in range(1, 12):
            texte = texte.replace(t(f"swap_{i}_from"), t(f"{cle}_{i}_to"))
        texte = texte.replace("\x00GROUPE", "\n".join(rendu_groupes(r, t)))
    return texte


def rendu_groupes(r: dict, t: Messages) -> list[str]:
    """Sections propres au rapport par Mission Team ou par site : structure (effectifs), tickets et dépendances internes.
    Groupes par ordre de nom, jamais par un chiffre ; l'effectif ne paraît que dans le tableau de structure."""
    genre = t("kind_mission_team" if r["par"] == "mission-team" else "kind_site")
    internes = dict(r["dependances_internes"])
    L = [t("group_intro", kind=genre), "", t("sec_structure"), "", t("structure_note"), "",
         t("head_structure", kind=genre), "|---|---|---|"]
    L += [f"| {g['group']} | {g['teams']} | {g['headcount']} |" for g in sorted(r["structure"], key=lambda g: g["group"])]
    L += ["", t("sec_group_counts"), "", t("group_internal_intro", kind=genre), "", t("head_group_counts"), "|---|---|---|"]
    L += [f"| {g} | {r['equipes_tickets'].get(g, 0)} | {n} |" for g, n in sorted(internes.items())]
    L += [""]
    return L


OPTIONS_RENOMMEES = {**cfg.OPTIONS_COMMUNES, "--cles": "--keys", "--par": "--by"}
VALEURS_PAR = {"equipe": "team", "projet": "project"}      # anciennes valeurs de --par, refusées


def valeur_by(texte: str) -> str:
    if texte in VALEURS_PAR:
        raise argparse.ArgumentTypeError(f"« {texte} » n'existe plus ; utiliser « {VALEURS_PAR[texte]} ».")
    return texte


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Carte des dépendances entre équipes (export Jira).")
    sub = parser.add_subparsers(dest="commande", required=True)
    d = sub.add_parser("diagnose", help="colonnes et format des liens, sans aucune clé")
    d.add_argument("export", nargs="*", help="un ou plusieurs exports CSV (lots de projets) ; aucun avec --source db")
    d.add_argument("--source", default="csv", metavar="{csv,db}",
                   help="d'où viennent les tickets et les liens : csv (défaut, les exports donnés) ou db (schéma flow de la base)")
    d.add_argument("--scope", dest="perimetre", help="projets du périmètre (clés séparées par des virgules) ou « tous » ; "
                   "remplace scope_projects de flux.yaml")
    add_language_option(d)
    d.set_defaults(func=cmd_diagnostic)
    c = sub.add_parser("compute", help="matrice, blocages, graphe et lead time")
    c.add_argument("export", nargs="*", help="un ou plusieurs exports CSV (lots de projets) ; aucun avec --source db")
    c.add_argument("--source", default="csv", metavar="{csv,db}",
                   help="d'où viennent les tickets et les liens : csv (défaut, les exports donnés) ou db (schéma flow de la base)")
    c.add_argument("--by", dest="par", type=valeur_by, choices=["team", "project", *GROUPEMENTS], default="team",
                   help="agrégation : par équipe (défaut), par projet Jira (plus lisible à l'échelle du produit), "
                        "par Mission Team ou par site (d'après le référentiel d'organisation)")
    c.add_argument("--name", dest="nom", default="perimetre")
    c.add_argument("--weeks", dest="semaines", type=int, default=26)
    c.add_argument("--scope", dest="perimetre", help="projets du périmètre (clés séparées par des virgules) ou « tous » ; "
                   "remplace scope_projects de flux.yaml")
    c.add_argument("--keys", dest="cles", action="store_true", help="affiche les clés des blocages dans le Terminal seulement")
    add_language_option(c)
    c.set_defaults(func=cmd_calcul)
    args = parser.parse_args(cfg.refuse_old_options(sys.argv[1:] if argv is None else argv, OPTIONS_RENOMMEES))
    if args.source == "csv" and not args.export:
        parser.error("the following arguments are required: export")
    if getattr(args, "par", None):
        args.par = {"team": "equipe", "project": "projet", "mission-team": "mission-team", "site": "site"}[args.par]
        # valeurs internes (rapport JSON, noms de fichier)
    args.func(args)


if __name__ == "__main__":
    main()
