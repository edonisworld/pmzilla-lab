# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "numpy", "psycopg[binary]"]
# ///
"""
PMZilla Lab : métriques de flux à partir d'un export CSV de Jira, ou de la base (lot 6).

Le script lit uniquement le type, l'état et les dates de chaque ticket. La clé, le titre, la
description et les personnes ne sont jamais conservés ni écrits : les rapports ne contiennent que
des agrégats (percentiles, débit par semaine, prévisions). C'est ce rapport, et lui seul, que la
posture Delivery lit.

    uv run flux_jira.py statuses <export.csv>...
        Colonnes reconnues, période couverte, et liste des états et des types avec leur nombre de
        tickets : de quoi remplir les listes d'états de flux.yaml. Plusieurs exports (lots de
        projets, pour rester sous la limite de Jira) sont fusionnés par clé si la colonne Key est
        présente.

    uv run flux_jira.py compute <export.csv>... [--name equipe] [--weeks 26] [--target N]
                                            [--target-date AAAA-MM-JJ] [--types Story,Bug]
        Lead time, débit par semaine, WIP et âge des éléments en cours, prévisions Monte Carlo.
        Écrit Flux-Lab/rapports/flux-<nom>-AAAA-MM-JJ.md (et .json). S'il existe un rapport plus
        ancien du même nom, la comparaison avec lui suit automatiquement (--no-comparison pour
        l'éviter).

    uv run flux_jira.py compute <export.csv>... --points
        Écrit aussi Flux-Lab/tableaux/points-<nom>-AAAA-MM-JJ.json : un point par ticket en cours (équipe, état, segment, âge,
        âge dans le segment, nature actif / attente / dormant), sans clé ni titre, pour l'Aging WIP du tableau de bord
        (fichier hors Git, permissions 600). Segment et âge dans le segment : seulement avec --history.

    uv run flux_jira.py compute <export.csv>... --scope ABC,DEF
        Ne garde que les tickets des projets listés (clés séparées par des virgules, ou « tous » : aucun filtre), comme
        dependencies_jira.py. Sans l'option, tous les tickets de l'export sont lus (flux.yaml n'est pas consulté pour ce
        réglage) et le rapport est identique à celui d'avant. Avec elle, le rapport indique le périmètre en tête.

    uv run flux_jira.py compute <export.csv>... --dormant-from-history [--history cache.json]
        Sépare le travail dormant : le script déduit les dormants du cache
        d'historique (non terminé, créé il y a au moins 365 jours, aucun changement d'état depuis au moins 365 jours,
        d'après la date de la dernière transition, ou de la création s'il n'y en a aucune). Un ticket sans historique
        dans le cache n'est pas compté dormant. Le rapport sépare alors le WIP actif, le WIP en attente et le WIP
        dormant (un ticket dormant sort des deux autres), et le « à faire » dormant du « à faire » vivant. Sans
        l'option, le rapport est inchangé. L'ancienne option --dormants (export CSV des dormants) est refusée.

    uv run flux_jira.py compute <export.csv>... --history [cache.json]
        Ajoute la section « Temps par segment » à partir de l'historique des états collecté par
        history_jira.py (Flux-Lab/historique/transitions.json par défaut) : temps cumulé par état puis par
        segment (réglage « segments » de flux.yaml), tickets sortis d'un segment pendant la période, âge dans
        le segment, lead time de livraison depuis le point d'engagement, efficacité de flux, couverture. Les
        durées sont en jours calendaires (différences de dates). Sans l'option, le rapport est inchangé.

    uv run flux_jira.py statuses|compute --source db [...]
        Lit les tickets dans le schéma flow de la base (rôle pmzilla_flow_ro, lecture seule) au lieu d'un export CSV :
        aucun fichier à donner, mêmes options, même rapport pour les mêmes données. Avec --source db, --history lit les
        transitions de la base (sans cache de fichier ; la valeur donnée à l'option, s'il y en a une, est ignorée). Les dates
        sont lues dans le fuseau export_timezone de flux.yaml. Défaut : --source csv (comportement inchangé, sans psycopg).
        Base injoignable ou rôle absent : message clair, code de sortie 1, sans mot de passe.

    uv run flux_jira.py compare --name equipe [--before AAAA-MM-JJ] [--after AAAA-MM-JJ]
        Compare deux rapports du même périmètre (par défaut les deux plus récents) : ce qui a
        bougé (débit des semaines nouvelles, lead time, WIP, vieillissement, équipes, clôtures
        groupées, prévisions). Écrit Flux-Lab/rapports/evolution-<nom>-AAAA-MM-JJ.md (et .json).

Réglages : Flux-Lab/flux.yaml (créé au premier lancement) : format des dates, noms des colonnes,
états « en cours » et « à faire ». Les exports CSV vont dans Flux-Lab/exports/ : le dossier
Flux-Lab est exclu de Git, et Claude Code n'a pas le droit de lire les exports.

Export multi-projets (plusieurs workflows) : si l'export a la colonne « Status Category », elle
décide de « en cours » (In Progress) et « à faire » (To Do) ; in_progress_states et todo_states ne
servent alors qu'aux tickets sans catégorie. Les tickets des types listés dans portfolio_types
(épopées, initiatives) et des projets listés dans excluded_projects (colonne Key) sortent du débit, du
lead time, du WIP et des prévisions, et le rapport dit combien ont été écartés. Ces réglages sont
ceux de dependencies_jira.py. Sans eux, le comportement est inchangé.

Fermetures groupées : avec une colonne de clé et l'heure dans la date de résolution, le rapport compte, par projet, les
tickets livrés (motif de résolution listé dans batch_closure_resolutions, « Done » par défaut) dont la résolution tombe
dans la même minute que celle d'au moins batch_closure_threshold - 1 autres du même projet (5 par défaut), avec leur
part dans le débit du projet. Un compte seulement : ces tickets restent dans le débit, le lead time et les prévisions.
L'option --batch-closure-resolutions « Done,Accepted & Released » (ou « tous » pour tous les motifs livrés) remplace
batch_closure_resolutions pour ce calcul, sans toucher à flux.yaml.

Fenêtre d'export : quand une requête d'export de flux.yaml (jql_export, jql_exports) filtre « resolved >= -Nw », la fenêtre
commence N semaines avant la date du calcul ; la première semaine de la période est alors tronquée (les éléments résolus
avant la fenêtre manquent) et « Arrivées et sorties » le dit : elle est à exclure des comparaisons.

États d'attente : waiting_states (facultatif) liste des états ou des motifs (« Ready for » en préfixe,
« On Hold » en suffixe) dont les éléments restent dans le WIP total mais sont comptés à part, comme files
d'attente. Le rapport montre alors le WIP actif, le WIP en attente et la part d'attente (par équipe aussi).
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flux_config as cfg
from yaml_strict import charger
import flow_glossary as glossaire
from flux_jira_messages import CATALOGS
from messages import DEFAULT_LANGUAGE, Messages, add_language_option

T_FR = Messages(CATALOGS, "fr")      # langue par défaut des fonctions appelées par d'autres scripts (segment_sample, flow_board)


def langue_demandee(argv: list[str] | None = None) -> str:
    """Langue lue dans la ligne de commande (`--language en`, `--language=en`), pour les messages
    émis avant l'analyse des options. Français si absente ou inconnue."""
    argv = sys.argv[1:] if argv is None else argv
    for i, argument in enumerate(argv):
        nom, egal, valeur = argument.partition("=")
        if nom == "--language":
            valeur = valeur if egal else (argv[i + 1] if i + 1 < len(argv) else "")
            return valeur if valeur in CATALOGS else DEFAULT_LANGUAGE
    return DEFAULT_LANGUAGE


try:
    import history_common as commun
except ImportError:
    sys.exit(Messages(CATALOGS, langue_demandee())("history_common_missing"))

WORKSPACE = Path(os.environ.get("PMZILLA_LAB_WORKSPACE", "~/PMZilla-Lab/workspace")).expanduser()
FLUX_DIR = WORKSPACE / "Flux-Lab"
CONFIG_FILE = FLUX_DIR / "flux.yaml"
REPORT_DIR = FLUX_DIR / "rapports"
HISTORIQUE_DEFAUT = FLUX_DIR / "historique" / "transitions.json"
SIMULATIONS = 10_000
PERCENTILES = (50, 70, 85, 95)

# Seuils de la comparaison entre deux rapports : au-delà, l'écart est signalé dans « Ce qui a bougé ».
# Ils servent à trier ce qui mérite une question aux équipes, pas à juger : un écart signalé est une
# hypothèse à vérifier, un écart sous le seuil n'est pas une preuve de stabilité.
SEUIL_DEBIT = 0.25          # débit moyen des semaines nouvelles contre les semaines d'avant
SEUIL_DEBIT_EQUIPE = 0.30   # même chose par équipe (séries plus petites, donc plus bruitées)
SEUIL_LEAD_TIME = 0.20      # lead time P85
SEUIL_WIP = 0.20            # nombre d'éléments en cours, et loi de Little
SEUIL_DORMANT_JOURS = 365   # seuil des dormants déduits de l'historique (history_common.SEUIL_DORMANT_JOURS)
FENETRE_REGROUPEMENT = 8    # dernières semaines de chaque rapport pour repérer les clôtures groupées
SEUIL_REGROUPEMENT = 0.60   # part des clôtures tombées sur les 2 meilleures semaines de la fenêtre
MIN_REGROUPEMENT = 5        # en dessous de ce nombre de clôtures dans la fenêtre, pas de verdict
MIN_VIEILLISSEMENT_EQUIPE = 3   # hausse minimale des éléments de plus de 90 jours d'une équipe pour la signaler

DEFAULT_CONFIG = {
    # noms possibles de chaque colonne utile : les en-têtes des CSV de export_jira_api.py (le premier trouvé est utilisé)
    "colonnes": {
        "type": ["Issue Type"],
        "etat": ["Status"],
        # facultatif : la catégorie d'état Jira (To Do, In Progress, Done), qui classe les états de tous les workflows
        "categorie": ["Status Category"],
        # facultatif : la clé du ticket, pour fusionner plusieurs exports et reconnaître le projet
        "cle": ["Issue key"],
        "cree": ["Created"],
        "resolu": ["Resolved"],
        "motif": ["Resolution"],
        "debut": ["Status Category Changed"],
        # facultatif : l'équipe (en-tête export_team_header, « Team » par défaut), pour une répartition par équipe
        "equipe": ["Team"],
        # à défaut, la première colonne dont le nom contient « team » et finit par « (Label) »
        # (champ personnalisé multi-valeurs : Jira répète la colonne, la première est l'équipe principale)
    },
    # états dans lesquels un ticket est « en cours » (à remplir avec la commande statuses)
    "etats_en_cours": ["In Progress", "In Review", "Testing"],
    # états « à faire » : ni commencés ni terminés (le reste, avec une date de résolution, est terminé)
    "etats_a_faire": ["Open", "To Do", "Backlog"],
    # motifs de clôture qui ne sont pas une livraison : exclus du débit, du lead time et des prévisions
    "motifs_exclus": ["Rejected", "Won't Do", "Duplicate", "Cannot Reproduce", "Obsolete"],
    # types de niveau portefeuille (épopées, initiatives…) : écartés du débit, du lead time, du WIP et des
    # prévisions (même réglage que dependencies_jira.py)
    "types_portefeuille": [],
    # projets Jira écartés de la même façon (anomalies, support…), reconnus par la clé du ticket
    "projets_exclus": [],
    # facultatif : états (ou motifs de préfixe ou de suffixe, comme « Ready for » et « On Hold ») dont les éléments
    # en cours sont comptés à part, comme files d'attente. Vide : aucun comptage à part.
    "etats_attente": [],
    # segments du flux (option --history) : chaque segment regroupe des états ; un état hors segment n'entre
    # dans aucun segment. Les noms d'états se comparent sans casse.
    "segments": commun.SEGMENTS_PAR_DEFAUT,
    # séparateur des équipes dans une cellule qui en contient plusieurs (comptage des tickets à plusieurs équipes)
    "separateur_equipes": ";",
    # segments hors calcul : leurs états sont connus (ils ne sont pas signalés comme oubliés) mais aucun temps n'est
    # calculé pour eux. Le réglage remplace la valeur par défaut en entier.
    "segments_hors_calcul": commun.SEGMENTS_HORS_CALCUL_PAR_DEFAUT,
    # point d'engagement du lead time de livraison : l'entrée dans ce segment (par défaut, « pret »)
    "point_engagement": "pret",
    # fermetures groupées : nombre de tickets d'un même projet résolus dans la même minute à partir duquel ils forment
    # une fermeture groupée (section « Fermetures groupées » du rapport, un compte seulement)
    "seuil_fermetures_groupees": 5,
    # motifs de résolution suivis (sans casse) ; liste vide : tous les motifs comptés comme livrés
    "motifs_fermetures_groupees": ["Done"],
}
SEUIL_COUVERTURE = 0.90     # en dessous, la couverture de l'historique est signalée comme insuffisante

# catégories d'état Jira (comparées sans casse) : celles qui décident de « en cours » et « à faire »
CATEGORIES_EN_COURS = {"in progress", "en cours"}
CATEGORIES_A_FAIRE = {"to do", "à faire", "a faire", "new", "nouveau"}
SEUIL_NOTE_EQUIPES = 10     # au-delà de ce nombre d'équipes dans le rapport, la note ci-dessus est ajoutée


# ---------------------------------------------------------------------------
# Langue : libellés de données que le JSON garde en français (clés et valeurs), rendus dans la langue du rapport
# ---------------------------------------------------------------------------

SANS_EQUIPE = "(sans équipe)"        # valeur interne (clé des rapports JSON), affichée dans la langue du rapport
SANS_MOTIF = "(vide)"
ETAT_INCONNU = "(inconnu)"
SUFFIXE_SANS_EQUIPE = ", tickets sans équipe exclus"


def libelle_equipe(equipe: str, tr=None) -> str:
    return (tr or T_FR)("no_team") if equipe == SANS_EQUIPE else equipe


def libelle_motif(motif: str, tr=None) -> str:
    return (tr or T_FR)("empty_value") if motif == SANS_MOTIF else motif


def libelle_etat(etat: str, tr=None) -> str:
    return (tr or T_FR)("unknown_state") if etat == ETAT_INCONNU else etat


def libelle_segment(segment: str, tr=None) -> str:
    tr = tr or T_FR
    cle = f"segment_{segment}"
    return tr(cle) if cle in CATALOGS["fr"] else segment


def libelle_types(types: str, tr=None) -> str:
    """Types du rapport JSON (« tous » ou une liste, avec le suffixe des tickets sans équipe) dans la langue du rapport."""
    tr = tr or T_FR
    suffixe = ""
    if types.endswith(SUFFIXE_SANS_EQUIPE):
        types, suffixe = types[:-len(SUFFIXE_SANS_EQUIPE)], tr("types_no_team_suffix")
    return (tr("types_all") if types == "tous" else types) + suffixe


def libelle_base(base: str, tr=None) -> str:
    return (tr or T_FR)("base_start" if base == "début" else "base_creation")


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------

def config(tr=None) -> dict:
    tr = tr or T_FR
    FLUX_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(yaml.safe_dump(cfg.to_public(DEFAULT_CONFIG), allow_unicode=True, sort_keys=False),
                               encoding="utf-8")
        print(tr("settings_created", path=CONFIG_FILE))
    lu = cfg.to_internal(charger(CONFIG_FILE.read_text(encoding="utf-8"), "flux.yaml"), "flux.yaml")
    settings = {**DEFAULT_CONFIG, **lu}
    settings["colonnes"] = {**DEFAULT_CONFIG["colonnes"], **(settings.get("colonnes") or {})}
    return settings


def read_export(path: Path, settings: dict, tr=None) -> tuple[list[dict], dict[str, str | None], int]:
    """Tickets réduits au type, à l'état et aux dates. Rien d'autre n'est gardé en mémoire."""
    tr = tr or T_FR
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        found: dict[str, str | None] = {}
        index: dict[str, int] = {}
        # noms comparés sans casse ni espaces superflus : « Status category changed » = « Status Category Changed »
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
        # un champ à plusieurs valeurs (« [G] Team/s ») peut s'exporter en plusieurs colonnes de même nom
        colonnes_equipe = ([i for i, h in enumerate(normalized) if h == normalized[index["equipe"]]]
                           if "equipe" in index else [])
        separateur = settings.get("separateur_equipes") or ";"
        if "etat" not in index or "cree" not in index:
            sys.exit(tr("columns_not_found", path=CONFIG_FILE))
        tickets, unreadable = [], 0
        for row in reader:
            def cell(field: str) -> str:
                position = index.get(field)
                return row[position] if position is not None and position < len(row) else ""
            created = commun.parse_jour(cell("cree"))
            if created is None:
                unreadable += 1
                continue
            cle = cell("cle").strip()
            equipes = []
            for position in colonnes_equipe:
                for valeur in (row[position].split(separateur) if position < len(row) else []):
                    if valeur.strip() and valeur.strip() not in equipes:
                        equipes.append(valeur.strip())
            tickets.append({
                "cle": cle,
                "projet": cle.rsplit("-", 1)[0].upper() if "-" in cle else "",
                "categorie": cell("categorie").strip().casefold(),
                "type": cell("type").strip() or "?",
                "etat": cell("etat").strip(),
                "cree": created,
                "resolu": commun.parse_jour(cell("resolu")),
                "resolu_a": commun.parse_moment(cell("resolu")),     # à la minute (fermetures groupées)
                "debut": commun.parse_jour(cell("debut")),
                "equipe": cell("equipe").strip() or "(sans équipe)",   # attribution : première colonne, cellule entière
                "equipes": equipes,                                      # toutes les équipes du ticket (comptage seulement)
                "motif": cell("motif").strip(),
            })
    return tickets, found, unreadable


def read_exports(paths: list[str], settings: dict, tr=None) -> tuple[list[dict], dict[str, str | None], int, int]:
    """Un ou plusieurs exports. Avec plusieurs, fusion par clé si la colonne Key est présente (le dernier
    fichier l'emporte) ; sans clé, les fichiers sont simplement mis bout à bout. Retourne aussi le nombre
    de tickets en double retirés."""
    lus = [read_export(Path(chemin).expanduser(), settings, tr) for chemin in paths]
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


SOURCES = ("csv", "db")


def lire_source(valeur: str | None, tr=None) -> str:
    """--source : « csv » (défaut) ou « db ». Toute autre valeur arrête le script avec un message."""
    tr = tr or T_FR
    source = valeur or "csv"
    if source not in SOURCES:
        sys.exit(tr("source_unknown", value=source, allowed=", ".join(SOURCES)))
    return source


def lire_tickets(args: argparse.Namespace, settings: dict, tr=None) -> tuple[list[dict], dict[str, str | None], int, int]:
    """Les tickets de la source choisie : exports CSV (au moins un fichier) ou schéma flow de la base."""
    tr = tr or T_FR
    if lire_source(args.source, tr) == "csv":
        return read_exports(args.export, settings, tr)
    if args.export:                                   # des fichiers avec la base : refusés, jamais ignorés en silence
        sys.exit(tr("source_db_no_files"))
    return depuis_la_base(lambda store: store.lire_tickets_flux(settings), tr)


def depuis_la_base(lecture, tr):
    """Appelle une lecture de flow_store (import tardif : la voie CSV ne charge pas psycopg)."""
    try:
        import flow_store
        return lecture(flow_store)
    except Exception as erreur:
        if type(erreur).__name__ != "ErreurBase":
            raise
        sys.exit(tr("db_unreachable", detail=str(erreur)))


def lire_historique_source(args: argparse.Namespace, settings: dict, tr=None) -> dict[str, list]:
    """Transitions par clé : cache de fichier (défaut) ou schéma flow de la base."""
    tr = tr or T_FR
    if args.source == "db":
        return depuis_la_base(lambda store: store.lire_historique(settings), tr)
    return charger_historique(Path(args.historique).expanduser() if args.historique else HISTORIQUE_DEFAUT, tr)


def par_effectif(compte) -> dict:
    """Dictionnaire ordonné par effectif décroissant puis par nom : l'ordre ne dépend jamais de l'ordre de lecture des tickets."""
    return dict(sorted(compte.items(), key=lambda e: (-e[1], str(e[0]))))


def ecarter(tickets: list[dict], settings: dict, a_une_cle: bool) -> tuple[list[dict], dict]:
    """Retire les tickets des types de niveau portefeuille et des projets exclus. Retourne les tickets gardés et
    ce qui a été écarté (total, par type, par projet)."""
    types, projets = commun.ensembles_exclus(settings, a_une_cle)
    if not types and not projets:
        return tickets, {}
    gardes, par_type, par_projet, total = [], Counter(), Counter(), 0
    for t in tickets:
        par_le_type = t["type"].casefold() in types
        par_le_projet = bool(t["projet"]) and t["projet"] in projets
        if par_le_type or par_le_projet:
            total += 1
            if par_le_type:
                par_type[t["type"]] += 1
            if par_le_projet:
                par_projet[t["projet"]] += 1
        else:
            gardes.append(t)
    if not total:
        return gardes, {}
    return gardes, {"total": total, "par_type": par_effectif(par_type), "par_projet": par_effectif(par_projet)}


def classeur(settings: dict, avec_categorie: bool):
    """Fonctions « en cours » et « à faire ». Avec la colonne de catégorie d'état, elle décide ; les listes de
    flux.yaml ne servent qu'aux tickets sans catégorie (ou si la colonne est absente)."""
    en_cours, a_faire = set(settings["etats_en_cours"]), set(settings["etats_a_faire"])

    def est_en_cours(t: dict) -> bool:
        if avec_categorie and t["categorie"]:
            return t["categorie"] in CATEGORIES_EN_COURS
        return t["etat"] in en_cours

    def est_a_faire(t: dict) -> bool:
        if avec_categorie and t["categorie"]:
            return t["categorie"] in CATEGORIES_A_FAIRE
        return t["etat"] in a_faire

    return est_en_cours, est_a_faire


def attente(settings: dict):
    """Fonction « cet élément est dans un état d'attente », ou None si waiting_states est vide. Un état correspond
    s'il est égal à une entrée, ou commence ou finit par elle (sans casse)."""
    motifs = [m.strip().casefold() for m in (settings.get("etats_attente") or []) if str(m).strip()]
    if not motifs:
        return None

    def est_attente(t: dict) -> bool:
        etat = t["etat"].strip().casefold()
        return any(etat == m or etat.startswith(m) or etat.endswith(m) for m in motifs)

    return est_attente


# ---------------------------------------------------------------------------
# Calculs
# ---------------------------------------------------------------------------

def percentiles(values: list[float]) -> dict[int, float]:
    if not values:
        return {}
    return {p: float(np.percentile(values, p)) for p in PERCENTILES}


def week_start(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=day.weekday())


def weekly_throughput(done: list[dict], first_week: dt.date, last_week: dt.date) -> list[int]:
    counts = Counter(week_start(t["resolu"]) for t in done)
    weeks, current = [], first_week
    while current <= last_week:
        weeks.append(counts.get(current, 0))
        current += dt.timedelta(days=7)
    return weeks


def charger_historique(chemin: Path, tr=None) -> dict[str, list]:
    """Transitions de statut par clé (en majuscules), lues dans le cache de history_jira.py."""
    tr = tr or T_FR
    if not chemin.exists():
        sys.exit(tr("history_cache_missing", path=chemin))
    try:
        donnees = commun.lire_cache(chemin)
    except commun.CacheIllisible:
        sys.exit(tr("history_cache_unreadable"))
    return {str(cle).upper(): entree["transitions"] for cle, entree in donnees.items()}


date_de = commun.date_calendaire


def chronologie(t: dict, transitions: list, aujourdhui: dt.date) -> list[tuple[str, dt.date, dt.date]]:
    """Périodes (état, début, fin) d'un ticket, de sa création à sa résolution (ou à la date du calcul s'il est
    ouvert), état initial compris. Les durées sont des différences de dates : des jours calendaires."""
    evenements = sorted(((date_de(d), de, vers) for d, de, vers in transitions if date_de(d)), key=lambda e: e[0])
    fin = t["resolu"] or aujourdhui
    if evenements and evenements[0][1]:
        etat = evenements[0][1]
    else:
        etat = t["etat"] if not evenements else "(inconnu)"
    periodes, debut = [], t["cree"]
    for date, _, vers in evenements:
        date = max(date, debut)
        periodes.append((etat, debut, date))
        etat, debut = vers or "(inconnu)", date
    periodes.append((etat, debut, max(fin, debut)))
    return periodes


def visites(periodes: list, segment_de: dict[str, str], ouvert: bool) -> list[dict]:
    """Visites de segment : suite de périodes contiguës dans un même segment (passer d'un état à un autre du
    même segment ne termine pas la visite). Une visite en cours est celle qui contient la dernière période d'un
    ticket ouvert."""
    resultat = []
    for i, (etat, debut, fin) in enumerate(periodes):
        segment = segment_de.get(etat.strip().casefold())
        if segment is None:
            continue
        if resultat and resultat[-1]["segment"] == segment and resultat[-1]["dernier"] == i - 1:
            resultat[-1].update(fin=fin, dernier=i, jours=resultat[-1]["jours"] + (fin - debut).days)
        else:
            resultat.append({"segment": segment, "debut": debut, "fin": fin, "premier": i, "dernier": i,
                             "jours": (fin - debut).days})
    for visite in resultat:
        visite["en_cours"] = ouvert and visite["dernier"] == len(periodes) - 1
    return resultat


def minutes_groupees(done: list[dict], seuil: int, motifs: set[str]) -> tuple[list[dict], Counter]:
    """Règle des fermetures groupées, partagée avec segment_sample.py --exclude-batch-closures : parmi les tickets livrés
    `done` (restreints aux motifs de résolution `motifs`, en minuscules ; vide, tous), les couples (projet, minute de
    résolution) qui réunissent au moins `seuil` tickets. Retourne les tickets suivis et le compteur de ces couples."""
    suivis = [t for t in done if not motifs or t["motif"].casefold() in motifs]
    minutes = Counter((t["projet"], t["resolu_a"]) for t in suivis if t["projet"] and t["resolu_a"])
    return suivis, Counter({couple: n for couple, n in minutes.items() if n >= seuil})


def tickets_en_fermeture_groupee(done: list[dict], seuil: int, motifs: set[str]) -> list[dict]:
    """Les tickets de `done` résolus dans une fermeture groupée (même règle que fermetures_groupees)."""
    suivis, groupes = minutes_groupees(done, seuil, motifs)
    return [t for t in suivis if (t["projet"], t["resolu_a"]) in groupes]


def fermetures_groupees(done: list[dict], seuil: int, motifs: set[str]) -> dict:
    """Par projet, les tickets livrés résolus dans la même minute que d'autres du même projet, quand ils sont au moins
    `seuil` : nombre de groupes, de tickets, plus grand groupe, et part des tickets livrés du projet. Un compte
    seulement : rien n'est retiré du débit. `motifs` (minuscules) restreint aux motifs de résolution voulus ; vide, tous
    les tickets livrés comptent. Les tickets sans clé de projet ou sans heure de résolution sont comptés à part."""
    suivis, minutes = minutes_groupees(done, seuil, motifs)
    sans_heure = sum(1 for t in suivis if t["resolu"] and not t["resolu_a"])
    livres = Counter(t["projet"] for t in done if t["projet"])
    par_projet: dict[str, dict] = {}
    for (projet, _), n in sorted(minutes.items(), key=lambda e: (e[0][0], -e[1], e[0][1])):
        d = par_projet.setdefault(projet, {"groupes": 0, "tickets": 0, "plus_grand": 0})
        d["groupes"] += 1
        d["tickets"] += n
        d["plus_grand"] = max(d["plus_grand"], n)
    for projet, d in par_projet.items():
        d["livres"] = livres[projet]
        d["part"] = d["tickets"] / livres[projet] if livres[projet] else None
    tickets = sum(d["tickets"] for d in par_projet.values())
    return {"seuil": seuil, "motifs": sorted(motifs) if motifs else [], "sans_heure": sans_heure,
            "total": {"groupes": sum(d["groupes"] for d in par_projet.values()), "tickets": tickets,
                      "livres": len(done), "part": tickets / len(done) if done else None},
            "par_projet": dict(sorted(par_projet.items(), key=lambda e: (-e[1]["tickets"], e[0])))}


def fenetre_export(settings: dict, today: dt.date, first_week: dt.date) -> dict | None:
    """Fenêtre glissante des requêtes d'export de flux.yaml (« resolved >= -Nw »), si elle tronque le début de la période.
    La date du calcul sert de date d'export. Retourne le filtre, le début de la fenêtre et le nombre de jours de la
    première semaine qui manquent, ou None si aucune requête n'a de fenêtre ou si la période commence après son début."""
    requetes = [settings.get("jql_export"), *(settings.get("jql_exports") or {}).values()]
    semaines = [int(m.group(1)) for r in requetes if r
                for m in [re.search(r"resolved\s*>=?\s*-\s*(\d+)\s*w", str(r), re.IGNORECASE)] if m]
    if not semaines:
        return None
    n = min(semaines)
    debut = today - dt.timedelta(days=7 * n)
    if debut <= first_week:
        return None
    return {"filtre": f"resolved >= -{n}w", "debut": debut.isoformat(), "semaine": first_week.isoformat(),
            "jours_manquants": (debut - first_week).days}


def stats_jours(valeurs: list[float]) -> dict:
    if not valeurs:
        return {"n": 0, "p50": None, "p85": None, "moyenne": None}
    p = percentiles(valeurs)
    return {"n": len(valeurs), "p50": p[50], "p85": p[85], "moyenne": float(np.mean(valeurs))}


def temps_par_segment(tickets: list[dict], done: list[dict], wip: list[dict], periodes: dict[int, list],
                      segment_de: dict[str, str], segments: list[str], engagement: str, est_attente,
                      debut_periode: dt.date, fin_periode: dt.date, aujourdhui: dt.date) -> dict:
    """Agrégats d'un ensemble de tickets : tickets sortis de chaque segment pendant la période, âge dans le
    segment, lead time de livraison depuis le point d'engagement, efficacité de flux, couverture."""
    sortis = {s: [] for s in segments}
    dedans = {s: [] for s in segments}
    for t in tickets:
        periodes_t = periodes.get(id(t))
        if periodes_t is None:
            continue
        vues = visites(periodes_t, segment_de, ouvert=not t["resolu"])
        for segment in segments:
            terminees = [v for v in vues if v["segment"] == segment and not v["en_cours"]]
            if any(debut_periode <= v["fin"] <= fin_periode for v in terminees):
                sortis[segment].append(sum(v["jours"] for v in terminees))
            dedans[segment] += [v["jours"] for v in vues if v["segment"] == segment and v["en_cours"]]
    depuis_engagement, depuis_creation, efficacites, sans_engagement = [], [], [], 0
    actif_total = duree_totale = 0
    for t in done:
        periodes_t = periodes.get(id(t))
        if periodes_t is None or not t["resolu"]:
            continue
        entree = next((debut for etat, debut, _ in periodes_t if segment_de.get(etat.strip().casefold()) == engagement),
                      None)
        if entree is None:
            sans_engagement += 1
            continue
        depuis_engagement.append(max(0, (t["resolu"] - entree).days))
        depuis_creation.append((t["resolu"] - t["cree"]).days)
        if est_attente:
            actif = total = 0
            for etat, debut, fin in periodes_t:
                recouvrement = (min(fin, t["resolu"]) - max(debut, entree)).days
                if recouvrement > 0:
                    total += recouvrement
                    if not est_attente({"etat": etat}):
                        actif += recouvrement
            if total > 0:
                efficacites.append(actif / total)
                actif_total, duree_totale = actif_total + actif, duree_totale + total
    avec = sum(1 for t in done + wip if id(t) in periodes)
    total_tickets = len(done) + len(wip)
    return {
        "couverture": {"avec": avec, "total": total_tickets, "part": avec / total_tickets if total_tickets else None},
        "sortis": {s: stats_jours(v) for s, v in sortis.items()},
        "dans_le_segment": {s: {k: v for k, v in stats_jours(a).items() if k != "moyenne"} for s, a in dedans.items()},
        "lead_time_livraison": {"n": len(depuis_engagement), "sans_engagement": sans_engagement,
                                "depuis_engagement": percentiles(depuis_engagement),
                                "depuis_creation": percentiles(depuis_creation)},
        "efficacite": ({"n": len(efficacites), "p50": float(np.percentile(efficacites, 50)),
                        "agregee": actif_total / duree_totale} if efficacites else None),
    }


def cfd_hebdomadaire(tickets: list[dict], livres: set[int], periodes: dict[int, list], segment_de: dict[str, str],
                     segments: list[str], first_week: dt.date, last_week: dt.date) -> dict:
    """Données du diagramme de flux cumulé, à la fin de chaque semaine (dimanche) : tickets livrés (cumul), tickets dans
    chaque segment calculé, tickets créés pas encore engagés dans un segment (« a_faire »). Un ticket clos sans
    livraison sort du diagramme. Seuls les tickets dont l'historique est connu sont comptés (le nombre des autres est
    donné). Aucun identifiant de ticket."""
    semaines, fins = [], []
    jour = first_week
    while jour <= last_week:
        semaines.append(jour.isoformat())
        fins.append(jour + dt.timedelta(days=6))
        jour += dt.timedelta(days=7)
    avec = [t for t in tickets if id(t) in periodes]
    livres_cumules = [0] * len(fins)
    a_faire = [0] * len(fins)
    stock = {seg: [0] * len(fins) for seg in segments}
    for t in avec:
        for i, fin in enumerate(fins):
            if t["cree"] > fin:
                continue
            if t["resolu"] and t["resolu"] <= fin:
                if id(t) in livres:
                    livres_cumules[i] += 1
                continue
            etat = next((e for e, debut, f in periodes[id(t)] if debut <= fin < f), None)
            segment = segment_de.get((etat or "").strip().casefold())
            if segment in stock:
                stock[segment][i] += 1
            else:
                a_faire[i] += 1
    return {"semaines": semaines, "livres": livres_cumules, "segments": stock, "a_faire": a_faire,
            "tickets": len(avec), "sans_historique": len(tickets) - len(avec)}


def weekly_arrivals(items: list[dict], first_week: dt.date, last_week: dt.date) -> list[int]:
    """Tickets créés par semaine, sur les mêmes semaines que le débit."""
    counts = Counter(week_start(t["cree"]) for t in items)
    weeks, current = [], first_week
    while current <= last_week:
        weeks.append(counts.get(current, 0))
        current += dt.timedelta(days=7)
    return weeks


def forecast_when(throughput: list[int], items: int, rng: np.random.Generator) -> dict[int, int] | None:
    """Nombre de semaines pour terminer `items` éléments, en tirant au hasard des semaines passées."""
    if items <= 0 or not throughput or max(throughput) == 0:
        return None
    samples = np.array(throughput)
    weeks_needed = np.empty(SIMULATIONS, dtype=int)
    for run in range(SIMULATIONS):
        total, weeks = 0, 0
        while total < items and weeks < 520:
            total += samples[rng.integers(len(samples))]
            weeks += 1
        weeks_needed[run] = weeks
    return {p: int(np.ceil(np.percentile(weeks_needed, p))) for p in (50, 85, 95)}


def forecast_how_many(throughput: list[int], weeks: int, rng: np.random.Generator) -> dict[int, int] | None:
    """Nombre d'éléments terminés en `weeks` semaines (85 % de chances d'en finir au moins autant)."""
    if weeks <= 0 or not throughput:
        return None
    samples = np.array(throughput)
    totals = samples[rng.integers(len(samples), size=(SIMULATIONS, weeks))].sum(axis=1)
    # « au moins N avec 85 % de chances » = 15e percentile
    return {85: int(np.percentile(totals, 15)), 50: int(np.percentile(totals, 50)),
            95: int(np.percentile(totals, 5))}


# ---------------------------------------------------------------------------
# Commandes
# ---------------------------------------------------------------------------

def cmd_statuts(args: argparse.Namespace) -> None:
    tr = Messages(CATALOGS, args.language)
    settings = config(tr)
    tickets, found, unreadable, doublons = lire_tickets(args, settings, tr)
    if len(args.export) > 1:
        print(tr("merged_exports", n=len(args.export))
              + (tr("merged_duplicates", n=doublons) if found.get("cle") else tr("merged_no_key")))
    print(tr("columns_used"))
    for field, label in (("type", tr("col_type")), ("etat", tr("col_status")), ("equipe", tr("col_team")),
                         ("cree", tr("col_created")), ("resolu", tr("col_resolved")), ("debut", tr("col_start"))):
        print(f"  {label:<36} {found[field] or tr('col_absent')}")
    for field, label in (("categorie", tr("col_category")), ("cle", tr("col_key"))):
        if found.get(field):
            print(f"  {label:<36} {found[field]}")
    if unreadable:
        print(tr("unreadable_dates", n=unreadable, path=CONFIG_FILE))
    if not tickets:
        return
    print(tr("tickets_summary", n=len(tickets), first=min(t['cree'] for t in tickets),
             last=max(t['cree'] for t in tickets)))
    resolved = [t["resolu"] for t in tickets if t["resolu"]]
    if resolved:
        print(tr("resolved_summary", n=len(resolved), first=min(resolved), last=max(resolved)))
    print(tr("states_header"))
    est_en_cours, est_a_faire = classeur(settings, bool(found.get("categorie")))
    est_attente_st = attente(settings)
    for state, count in par_effectif(Counter(t["etat"] for t in tickets)).items():
        same = [t for t in tickets if t["etat"] == state]
        tag = (tr("tag_in_progress") if all(est_en_cours(t) for t in same)
               else tr("tag_todo") if all(est_a_faire(t) for t in same)
               else tr("tag_done_or_unclassified") if not any(est_en_cours(t) or est_a_faire(t) for t in same)
               else tr("tag_mixed"))
        if est_attente_st and est_attente_st({"etat": state}) and tag in (tr("tag_in_progress"), tr("tag_mixed")):
            tag += tr("tag_waiting")
        print(f"  {count:>5}  {state}  ({tag})")
    _, ecartes = ecarter(tickets, settings, bool(found.get("cle")))
    if ecartes:
        print(tr("statuses_excluded", total=ecartes["total"])
              + "".join(tr(cle) + ", ".join(f"{a} {n}" for a, n in v.items())
                        for cle, v in (("excluded_part_type", ecartes["par_type"]),
                                       ("excluded_part_project", ecartes["par_projet"])) if v) + ".")
    print(tr("types_header"))
    for kind, count in par_effectif(Counter(t["type"] for t in tickets)).items():
        print(f"  {count:>5}  {kind}")
    if not found["resolu"]:
        print(tr("no_resolved_column"))


def lire_perimetre(valeur: str | None, tr=None) -> list[str] | None:
    """--scope : « tous » ou « all » (None : aucun filtre) ou des clés de projet séparées par des virgules."""
    tr = tr or T_FR
    if valeur is None:
        return None
    if valeur.strip().lower() in ("tous", "all"):
        return []
    projets = list(dict.fromkeys(v.strip().upper() for v in valeur.split(",") if v.strip()))
    if not projets:
        sys.exit(tr("scope_needs_projects"))
    return projets


def cmd_calcul(args: argparse.Namespace) -> None:
    tr = Messages(CATALOGS, args.language)
    if args.dormants is not None:
        sys.exit(tr("dormants_removed"))
    settings = config(tr)
    perimetre = lire_perimetre(args.perimetre, tr)
    tickets, found, _, doublons = lire_tickets(args, settings, tr)
    if not found["resolu"]:
        sys.exit(tr("resolved_column_missing"))
    perimetre_retenu = None
    if perimetre is not None:
        lus = len(tickets)
        if perimetre:
            if not found.get("cle"):
                sys.exit(tr("scope_no_key_column"))
            tickets = [t for t in tickets if t["projet"] in set(perimetre)]
            absents = len(set(perimetre) - {t["projet"] for t in tickets})
            if not tickets:
                sys.exit(tr("scope_no_ticket"))
            print(tr("scope_summary", kept=len(tickets), read=lus, missing=absents))
        perimetre_retenu = {"projets": perimetre or "tous", "tickets_lus": lus, "tickets_retenus": len(tickets)}
    cles_dormantes: set[str] | None = None
    sans_historique = 0
    if args.dormants_historique:
        if not found.get("cle"):
            sys.exit(tr("dormant_history_no_key"))
        cache_dormants = lire_historique_source(args, settings, tr)
        aujourdhui_dormants = dt.date.fromisoformat(args.aujourdhui) if args.aujourdhui else dt.date.today()
        cles_dormantes, sans_historique = commun.dormants_selon_historique(
            ((t["cle"], t["cree"], bool(t["resolu"])) for t in tickets), cache_dormants, aujourdhui_dormants)
    tickets, ecartes = ecarter(tickets, settings, bool(found.get("cle")))
    if args.types:
        kinds = {k.strip() for k in args.types.split(",")}
        tickets = [t for t in tickets if t["type"] in kinds]
    if args.equipes_seulement:
        if not found.get("equipe"):
            sys.exit(tr("teams_only_no_team"))
        tickets = [t for t in tickets if t["equipe"] != "(sans équipe)"]
    today = dt.date.fromisoformat(args.aujourdhui) if args.aujourdhui else dt.date.today()
    last_week = week_start(today) - dt.timedelta(days=7)          # dernière semaine complète
    first_week = last_week - dt.timedelta(weeks=args.semaines - 1)
    avec_categorie = bool(found.get("categorie"))
    est_en_cours, est_a_faire = classeur(settings, avec_categorie)
    est_attente = attente(settings)

    # l'export peut commencer après le début de la période (JQL « resolved >= -26w ») : les semaines
    # antérieures à la première résolution de l'export ne sont pas des semaines à zéro, on les retire
    resolved = [t["resolu"] for t in tickets if t["resolu"]]
    if resolved:
        first_week = max(first_week, week_start(min(resolved)))
    excluded_motifs = {m.casefold() for m in settings.get("motifs_exclus") or []}
    closed = [t for t in tickets if t["resolu"] and first_week <= week_start(t["resolu"]) <= last_week]
    done = [t for t in closed if t["motif"].casefold() not in excluded_motifs]
    not_delivered = par_effectif(Counter(t["motif"] for t in closed if t["motif"].casefold() in excluded_motifs))
    seuil_fermetures = settings.get("seuil_fermetures_groupees")
    if not isinstance(seuil_fermetures, int) or isinstance(seuil_fermetures, bool) or seuil_fermetures < 2:
        sys.exit(tr("batch_threshold_invalid"))
    if args.motifs_fermetures is not None:       # l'option remplace le réglage, sans toucher à flux.yaml
        voulus = [m.strip() for m in args.motifs_fermetures.split(",") if m.strip()]
        if not voulus:
            sys.exit(tr("batch_resolutions_empty"))
        motifs_fermetures = (set() if [m.casefold() for m in voulus] in (["tous"], ["all"])
                             else {m.casefold() for m in voulus})
    else:
        motifs_fermetures = {str(m).casefold() for m in settings.get("motifs_fermetures_groupees") or []}
    fermetures = fermetures_groupees(done, seuil_fermetures, motifs_fermetures) if found.get("cle") else None
    wip = [t for t in tickets if not t["resolu"] and est_en_cours(t)]
    todo = [t for t in tickets if not t["resolu"] and est_a_faire(t)]
    unclassified = Counter(t["etat"] for t in tickets
                           if not t["resolu"] and not (est_en_cours(t) or est_a_faire(t)))

    est_dormant = (lambda t: t["cle"].upper() in cles_dormantes) if cles_dormantes is not None else None
    if est_dormant:
        dormants_wip = [t for t in wip if est_dormant(t)]
        dormants_todo = [t for t in todo if est_dormant(t)]
        print(tr("dormant_history_summary", dormant=len(cles_dormantes), no_history=sans_historique,
                 wip=len(dormants_wip), todo=len(dormants_todo)))

    def repartition(items: list[dict]) -> dict:
        """Actif, en attente et dormant : un ticket dormant sort des deux autres catégories."""
        dormants = [t for t in items if est_dormant(t)]
        vivants = [t for t in items if not est_dormant(t)]
        en_attente = [t for t in vivants if est_attente and est_attente(t)]
        n = len(items)
        parts = {k: (v / n if n else None) for k, v in
                 (("actif", len(vivants) - len(en_attente)), ("attente", len(en_attente)), ("dormant", len(dormants)))}
        return {"actif": len(vivants) - len(en_attente), "attente": len(en_attente), "dormant": len(dormants),
                "parts": parts}

    lead = [(t["resolu"] - t["cree"]).days for t in done]
    throughput = weekly_throughput(done, first_week, last_week)
    # arrivées : tous les tickets créés pendant la période, rejetés compris (mêmes types et mêmes exclusions que le débit)
    arrived = [t for t in tickets if first_week <= week_start(t["cree"]) <= last_week]
    arrivals = weekly_arrivals(arrived, first_week, last_week)
    arrivals_by_team = {}
    if found.get("equipe"):
        for team in sorted({t["equipe"] for t in arrived + done}):
            n_in = sum(1 for t in arrived if t["equipe"] == team)
            n_out = sum(1 for t in done if t["equipe"] == team)
            arrivals_by_team[team] = {"arrivees": n_in, "sorties": n_out, "difference": n_in - n_out}
    ages_from_start = [(today - t["debut"]).days for t in wip if t["debut"]]
    ages_from_creation = [(today - t["cree"]).days for t in wip]
    lead_p = percentiles(lead)
    rng = np.random.default_rng(42)
    # avec --dormants, la loi de Little et la prévision portent sur le WIP non dormant (actif + en attente) ;
    # le résultat sur le WIP total est donné à part, pour comparaison
    wip_courant = [t for t in wip if not est_dormant(t)] if est_dormant else wip
    objectif = args.objectif if args.objectif is not None else len(wip_courant)
    when = forecast_when(throughput, objectif, rng)
    target = dt.date.fromisoformat(args.date_cible) if args.date_cible else None
    how_many = forecast_how_many(throughput, max(0, (target - today).days // 7), rng) if target else None

    by_type = {}
    for kind in sorted({t["type"] for t in done}):
        values = [(t["resolu"] - t["cree"]).days for t in done if t["type"] == kind]
        by_type[kind] = {"termines": len(values), "lead_time": percentiles(values)}

    reference_age = ages_from_start if len(ages_from_start) == len(wip) and wip else ages_from_creation
    # âge par état (depuis le début si connu, sinon depuis la création) et seuils de vieillissement
    def age_of(t: dict) -> int:
        return (today - (t["debut"] or t["cree"])).days
    by_state = {}
    for state in sorted({t["etat"] for t in wip}, key=lambda s: (-sum(1 for t in wip if t["etat"] == s), s)):
        ages = [age_of(t) for t in wip if t["etat"] == state]
        by_state[state] = {"elements": len(ages), "age": percentiles(ages),
                           "plus_de_90_j": sum(1 for a in ages if a > 90),
                           "plus_de_365_j": sum(1 for a in ages if a > 365)}
        if est_dormant:
            by_state[state]["dormants"] = sum(1 for t in wip if t["etat"] == state and est_dormant(t))
    # files avant engagement : âge des éléments « à faire » par état. Depuis la création (toujours connu)
    # et depuis le dernier changement de catégorie d'état (Status Category Changed), qui marque l'entrée
    # dans la catégorie « En cours » de Jira pour les états d'analyse ou de définition
    todo_by_state = {}
    for state in sorted({t["etat"] for t in todo}, key=lambda s: (-sum(1 for t in todo if t["etat"] == s), s)):
        items = [t for t in todo if t["etat"] == state]
        created = [(today - t["cree"]).days for t in items]
        moved = [(today - t["debut"]).days for t in items if t["debut"]]
        todo_by_state[state] = {"elements": len(items), "age_creation": percentiles(created),
                                "age_categorie": percentiles(moved) if moved else None,
                                "plus_de_90_j": sum(1 for a in created if a > 90),
                                "plus_de_365_j": sum(1 for a in created if a > 365)}
        if est_dormant:
            todo_by_state[state]["dormants"] = sum(1 for t in items if est_dormant(t))
    thresholds = {f"plus_de_{d}_j": sum(1 for t in wip if age_of(t) > d) for d in (30, 90, 180, 365, 730)}
    teams = {}
    if found.get("equipe"):
        weeks = max(1, len(throughput))
        for team in sorted({t["equipe"] for t in done + wip}):
            team_done = [t for t in done if t["equipe"] == team]
            team_wip = [t for t in wip if t["equipe"] == team]
            teams[team] = {
                "termines": len(team_done), "debit_moyen": len(team_done) / weeks,
                "lead_time": percentiles([(t["resolu"] - t["cree"]).days for t in team_done]),
                "wip": len(team_wip), "age_wip": percentiles([age_of(t) for t in team_wip]),
                "wip_plus_de_90_j": sum(1 for t in team_wip if age_of(t) > 90),
                "debit_par_semaine": weekly_throughput(team_done, first_week, last_week),
                "arrivees_par_semaine": weekly_arrivals([t for t in arrived if t["equipe"] == team], first_week, last_week),
            }
            if est_attente:
                en_attente = sum(1 for t in team_wip if est_attente(t))
                teams[team]["wip_attente"] = en_attente
                teams[team]["part_attente"] = en_attente / len(team_wip) if team_wip else None
            if est_dormant:
                teams[team]["wip_repartition"] = repartition(team_wip)
                a_faire_equipe = [t for t in todo if t["equipe"] == team]
                teams[team]["a_faire"] = len(a_faire_equipe)
                teams[team]["a_faire_dormant"] = sum(1 for t in a_faire_equipe if est_dormant(t))
    over_p85 = sum(1 for a in reference_age if lead_p and a > lead_p[85])
    def little_de(n: int) -> float | None:
        return (n / (sum(throughput) / len(throughput)) * 7) if throughput and sum(throughput) else None
    little = little_de(len(wip_courant))

    segments_calcules = None
    if args.historique is not None:
        if not found.get("cle"):
            sys.exit(tr("history_no_key"))
        histoires = lire_historique_source(args, settings, tr)
        segment_de, noms_segments = commun.table_segments(settings)
        table = {nom: None for nom in noms_segments}
        engagement = settings.get("point_engagement") or "pret"
        if engagement not in table:
            sys.exit(tr("commitment_unknown", point=engagement, segments=", ".join(
                nom if tr.language == DEFAULT_LANGUAGE else cfg.SEGMENTS.get(nom, nom) for nom in noms_segments)))
        periodes = {id(t): chronologie(t, histoires[t["cle"].upper()], today)
                    for t in tickets if t["cle"] and t["cle"].upper() in histoires}
        illisibles = sum(1 for t in tickets if t["cle"] and any(
            date_de(trans[0]) is None for trans in histoires.get(t["cle"].upper(), [])))
        if illisibles:
            print(tr("unreadable_transition_dates", n=illisibles))
        fin_periode = last_week + dt.timedelta(days=6)
        calcul = lambda sous, sous_done, sous_wip: temps_par_segment(
            sous, sous_done, sous_wip, periodes, segment_de, noms_segments, engagement, est_attente, first_week,
            fin_periode, today)
        hors_segment = Counter(etat for liste in periodes.values() for etat in {e for e, _, _ in liste}
                               if etat.strip().casefold() not in segment_de)
        livres_ids = {id(t) for t in done}
        cfd = lambda sous: cfd_hebdomadaire(sous, livres_ids, periodes, segment_de, noms_segments, first_week, last_week)
        segments_calcules = {
            "parametres": {"segments": noms_segments, "point_engagement": engagement,
                           "efficacite_calculee": bool(est_attente)},
            "cfd": {"global": cfd(tickets),
                    "par_equipe": ({team: cfd([t for t in tickets if t["equipe"] == team])
                                    for team in sorted({t["equipe"] for t in done + wip})} if found.get("equipe") else {})},
            "global": calcul(tickets, done, wip),
            "par_equipe": ({team: calcul([t for t in tickets if t["equipe"] == team],
                                         [t for t in done if t["equipe"] == team],
                                         [t for t in wip if t["equipe"] == team])
                            for team in sorted({t["equipe"] for t in done + wip})} if found.get("equipe") else {}),
            "etats_hors_segment": dict(list(par_effectif(hors_segment).items())[:10]),
        }
        if illisibles:
            segments_calcules["dates_illisibles"] = illisibles
    result = {
        "nom": args.nom, "date": today.isoformat(), "periode": [first_week.isoformat(),
                                                               (last_week + dt.timedelta(days=6)).isoformat()],
        "semaines": len(throughput),
        "types": (args.types or "tous") + (", tickets sans équipe exclus" if args.equipes_seulement else ""),
        "termines": len(done), "debit_par_semaine": throughput,
        "arrivees": len(arrived), "arrivees_par_semaine": arrivals, "arrivees_sorties_par_equipe": arrivals_by_team,
        "clos_sans_livraison": dict(not_delivered),
        "motifs_livres": par_effectif(Counter(t["motif"] or "(vide)" for t in done)),
        "debit": {"moyenne": float(np.mean(throughput)) if throughput else 0,
                  "mediane": float(np.median(throughput)) if throughput else 0,
                  "semaines_a_zero": sum(1 for w in throughput if w == 0)},
        "lead_time_jours": lead_p, "lead_time_par_type": by_type,
        "wip": len(wip), "a_faire": len(todo), "etats_non_classes": par_effectif(unclassified),
        "wip_par_etat": par_effectif(Counter(t["etat"] for t in wip)),
        "age_par_etat": by_state, "age_a_faire_par_etat": todo_by_state, "age_seuils": thresholds, "par_equipe": teams,
        "age_wip_jours": {"depuis_debut": percentiles(ages_from_start) if ages_from_start else None,
                          "depuis_creation": percentiles(ages_from_creation) if ages_from_creation else None,
                          "au_dela_du_lead_time_p85": over_p85,
                          "base": "début" if reference_age is ages_from_start else "création"},
        "little_jours": little,
        "prevision_quand": {"elements": objectif, "semaines": when},
        "prevision_combien": {"date": target.isoformat() if target else None, "elements": how_many},
        "colonnes": {k: v for k, v in found.items() if k not in ("cle", "categorie") or v},
    }
    # champs ajoutés seulement quand ils s'appliquent : un export sans ces réglages donne le même rapport
    if ecartes:
        result["ecartes"] = ecartes
    if perimetre_retenu:
        result["perimetre"] = perimetre_retenu
    plusieurs = [t for t in tickets if len(t.get("equipes") or []) > 1]
    if found.get("equipe") and plusieurs:
        result["tickets_plusieurs_equipes"] = {
            "total": len(plusieurs), "sur": len(tickets),
            "termines": sum(1 for t in plusieurs if t in done), "en_cours": sum(1 for t in plusieurs if t in wip),
            "separateur": settings.get("separateur_equipes") or ";"}
    if est_attente:
        en_attente = [t for t in wip if est_attente(t)]
        result["wip_attente"] = {"actif": len(wip) - len(en_attente), "attente": len(en_attente),
                                 "part": len(en_attente) / len(wip) if wip else None,
                                 "par_etat": par_effectif(Counter(t["etat"] for t in en_attente))}
        for state, data in result["age_par_etat"].items():
            data["attente"] = est_attente({"etat": state})
    if est_dormant:
        result["dormants"] = {"seuil_jours": SEUIL_DORMANT_JOURS, "cles": len(cles_dormantes),
                              "source": "historique", "sans_historique": sans_historique}
        result["wip_repartition"] = repartition(wip)
        result["wip_non_dormant"] = len(wip_courant)
        result["little_jours_wip_total"] = little_de(len(wip))
        if args.objectif is None:      # avec --target, la prévision est la même sur les deux périmètres
            result["prevision_quand_wip_total"] = {"elements": len(wip),
                                                   "semaines": forecast_when(throughput, len(wip),
                                                                             np.random.default_rng(42))}
        todo_dormant = len(dormants_todo)
        result["a_faire_repartition"] = {"vivant": len(todo) - todo_dormant, "dormant": todo_dormant,
                                         "part_dormant": todo_dormant / len(todo) if todo else None}
    if fermetures is not None:
        result["fermetures_groupees"] = fermetures
    fenetre = fenetre_export(settings, today, first_week)
    if fenetre:
        result["fenetre_export"] = fenetre
    if segments_calcules:
        result["temps_par_segment"] = segments_calcules
    if avec_categorie:
        result["classement"] = "catégorie d'état"
    if len(args.export) > 1:
        result["exports"] = {"fichiers": len(args.export), "doublons_retires": doublons if found.get("cle") else None}
    write_report(result, tr)
    if args.points:
        ecrire_points(args.nom, today, wip, age_of, est_dormant, est_attente,
                      periodes if args.historique is not None else None,
                      segment_de if args.historique is not None else None,
                      noms_segments if args.historique is not None else [],
                      "début" if reference_age is ages_from_start else "création", tr)
    if not args.sans_comparaison:
        reports = find_reports(args.nom)
        earlier = [day for day in reports if day < result["date"]]
        if earlier:
            print("\n" + "=" * 72 + "\n")
            compare(load_report(reports[earlier[-1]]), load_report(reports[result["date"]]), tr)


def fmt_p(values: dict | None, unit: str | None = None, tr=None) -> str:
    tr = tr or T_FR
    if not values:
        return tr("na")
    unit = tr("days_suffix") if unit is None else unit
    return " · ".join(f"P{p} {round(v)}{unit}" for p, v in sorted(values.items()))


def lecture_lines(r: dict, tr=None) -> list[str]:
    """Section fixe « Comment lire ce rapport » : définitions en phrases courtes. Seuls les exemples sont
    calculés, à partir des chiffres du rapport lui-même."""
    tr = tr or T_FR
    age = r["age_wip_jours"]
    ages = age["depuis_debut"] if age["base"] == "début" else age["depuis_creation"]
    lead = r["lead_time_jours"]
    exemples = []
    if ages and pct(ages, 85) is not None:
        n = round(pct(ages, 85))
        exemples.append(tr("example_age", n=n))
    if lead and pct(lead, 85) is not None:
        n = round(pct(lead, 85))
        exemples.append(tr("example_lead", n=n))
    definitions = glossaire.lignes_rapport(tr.language, segments=bool(r.get("temps_par_segment")),
                                           fermetures=bool(r.get("fermetures_groupees")))
    lines = [tr("reading_heading"), ""] + definitions
    ts = r.get("temps_par_segment")
    if ts:
        efficacite = ts["global"]["efficacite"]
        if efficacite:
            n = round(100 * efficacite["agregee"])
            exemples.append(tr("example_efficiency", n=n, rest=100 - n))
    if exemples:
        lines += ["", tr("examples_intro")] + [f"- {e[0].upper()}{e[1:]}" for e in exemples]
    return lines


def j(valeur: float | None, decimales: int = 0, tr=None) -> str:
    tr = tr or T_FR
    return tr("na") if valeur is None else f"{valeur:.{decimales}f}{tr('days_suffix')}"


def pourcent(valeur: float | None, tr=None) -> str:
    tr = tr or T_FR
    return tr("na") if valeur is None else tr("pct", value=round(100 * valeur))


def segments_lines(r: dict, tr=None) -> list[str]:
    """Section « Temps par segment », au global et par équipe, sans classement."""
    tr = tr or T_FR
    ts = r["temps_par_segment"]
    g = ts["global"]
    segments = ts["parametres"]["segments"]
    nom = lambda s: libelle_segment(s, tr)
    lines = ["", tr("segments_heading"), "", tr("segments_intro"), ""]
    c = g["couverture"]
    lines.append(tr("segments_coverage", covered=c["avec"], total=c["total"], share=pourcent(c["part"], tr)))
    if c["part"] is not None and c["part"] < SEUIL_COUVERTURE:
        lines.append(tr("segments_coverage_low"))
    if ts.get("dates_illisibles"):
        lines.append(tr("segments_unreadable", n=ts["dates_illisibles"]))
    if ts.get("etats_hors_segment"):
        lines.append(tr("segments_outside", list=", ".join(f"{libelle_etat(e, tr)} {n}"
                                                            for e, n in ts["etats_hors_segment"].items())))
    lines += ["", tr("segments_exited_heading"), "", tr("segments_exited_table"), "|---|---|---|---|---|"]
    for s_ in segments:
        d = g["sortis"][s_]
        lines.append(f"| {nom(s_)} | {d['n']} | {j(d['p50'], tr=tr)} | {j(d['p85'], tr=tr)} | {j(d['moyenne'], 1, tr)} |")
    lines += ["", tr("segments_inside_heading"), "", tr("segments_inside_table"), "|---|---|---|---|"]
    for s_ in segments:
        d = g["dans_le_segment"][s_]
        lines.append(f"| {nom(s_)} | {d['n']} | {j(d['p50'], tr=tr)} | {j(d['p85'], tr=tr)} |")
    ltl = g["lead_time_livraison"]
    eng = nom(ts["parametres"]["point_engagement"])
    lines += ["", tr("lead_delivery_heading"), "",
              tr("lead_delivery_intro", segment=eng, n=ltl["n"], without=ltl["sans_engagement"]), ""]
    lines.append(tr("lead_from_commitment", p=fmt_p(ltl["depuis_engagement"], tr=tr)))
    lines.append(tr("lead_from_creation", p=fmt_p(ltl["depuis_creation"], tr=tr)))
    lines += ["", tr("efficiency_heading"), ""]
    e = g["efficacite"]
    if not ts["parametres"]["efficacite_calculee"]:
        lines.append(tr("efficiency_no_waiting"))
    elif e is None:
        lines.append(tr("efficiency_no_ticket"))
    else:
        lines.append(tr("efficiency_value", p50=pourcent(e["p50"], tr), n=e["n"], aggregate=pourcent(e["agregee"], tr)))
    if r.get("temps_par_segment", {}).get("par_equipe"):
        equipes = ts["par_equipe"]
        lines += ["", tr("by_team_subheading"), "", tr("segments_team_table"), "|---|---|---|---|---|---|---|"]
        for team, d in equipes.items():
            lt, ef = d["lead_time_livraison"], d["efficacite"]
            lines.append(f"| {libelle_equipe(team, tr)} | {pourcent(d['couverture']['part'], tr)} | {lt['n']} | "
                         f"{j(lt['depuis_engagement'].get(50), tr=tr)} | {j(lt['depuis_engagement'].get(85), tr=tr)} | "
                         f"{pourcent(ef['p50'], tr) if ef else tr('na')} | {pourcent(ef['agregee'], tr) if ef else tr('na')} |")
        entete = f"| {tr('team_column')} | " + " | ".join(nom(s_) for s_ in segments) + " |"
        lines += ["", tr("segments_team_exited"), "", entete, "|---|" + "---|" * len(segments)]
        for team, d in equipes.items():
            lines.append(f"| {libelle_equipe(team, tr)} | " + " | ".join(f"{d['sortis'][s_]['n']} · {j(d['sortis'][s_]['p50'], tr=tr)}" for s_ in segments) + " |")
        lines += ["", tr("segments_team_inside"), "", entete, "|---|" + "---|" * len(segments)]
        for team, d in equipes.items():
            lines.append(f"| {libelle_equipe(team, tr)} | " + " | ".join(f"{d['dans_le_segment'][s_]['n']} · {j(d['dans_le_segment'][s_]['p50'], tr=tr)}" for s_ in segments) + " |")
        lines += ["", tr("small_sample_note")]
        if len(equipes) > SEUIL_NOTE_EQUIPES:
            lines += ["", tr("teams_note")]
        else:
            lines += ["", tr("teams_not_compared")]
    return lines


def signe(n: int) -> str:
    return f"{n:+d}" if n else "0"


def fermetures_lines(r: dict, tr=None) -> list[str]:
    """Section « Fermetures groupées » : un compte par projet, rien n'est retiré du débit. Absente sans colonne de clé."""
    tr = tr or T_FR
    f = r.get("fermetures_groupees")
    if f is None:
        return []
    suivis = tr("batch_followed_motifs", list=", ".join(f["motifs"])) if f["motifs"] else tr("batch_all_motifs")
    lines = [tr("batch_heading"), "",
             tr("batch_intro", followed=suivis, others=f["seuil"] - 1, threshold=f["seuil"]), ""]
    t = f["total"]
    if not f["par_projet"]:
        lines.append(tr("batch_none", n=t["livres"]))
    else:
        lines += [tr("batch_table"), "|---|---|---|---|---|---|"]
        for projet, d in f["par_projet"].items():
            lines.append(f"| {projet} | {d['tickets']} | {d['groupes']} | {d['plus_grand']} | {d['livres']} | "
                         f"{pourcent(d['part'], tr)} |")
        lines.append(f"| **{tr('total_label')}** | **{t['tickets']}** | **{t['groupes']}** | | **{t['livres']}** | "
                     f"**{pourcent(t['part'], tr)}** |")
    if f["sans_heure"]:
        lines += ["", tr("batch_no_time", n=f["sans_heure"])]
    return lines + [""]


def arrivees_lines(r: dict, tr=None) -> list[str]:
    """Section « Arrivées et sorties » : tickets créés et éléments terminés, semaine par semaine."""
    tr = tr or T_FR
    arrivals, sorties = r["arrivees_par_semaine"], r["debit_par_semaine"]
    first = dt.date.fromisoformat(r["periode"][0])
    total_in, total_out = sum(arrivals), sum(sorties)
    n = max(1, len(arrivals))
    lines = [tr("arrivals_heading"), "", tr("arrivals_intro"), "", tr("arrivals_table"), "|---|---|---|---|"]
    for i, (a, o) in enumerate(zip(arrivals, sorties)):
        lines.append(f"| {first + dt.timedelta(weeks=i)} | {a} | {o} | {signe(a - o)} |")
    lines += [f"| **{tr('total_label')}** | **{total_in}** | **{total_out}** | **{signe(total_in - total_out)}** |", "",
              tr("average_per_week", arrivals=f"{total_in / n:.1f}", departures=f"{total_out / n:.1f}"),
              tr("arrivals_note")]
    fe = r.get("fenetre_export")
    if fe:
        manque = (tr("missing_first_days", n=fe["jours_manquants"]) if fe["jours_manquants"] < 7
                  else tr("missing_whole_week"))
        lines += ["", tr("truncated_first_week", filter=fe["filtre"], start=fe["debut"], missing=manque,
                         week=fe["semaine"])]
    if r.get("arrivees_sorties_par_equipe"):
        lines += ["", tr("by_team_subheading"), "", tr("arrivals_team_table"), "|---|---|---|---|"]
        for team, d in r["arrivees_sorties_par_equipe"].items():
            lines.append(f"| {libelle_equipe(team, tr)} | {d['arrivees']} | {d['sorties']} | {signe(d['difference'])} |")
        if len(r["arrivees_sorties_par_equipe"]) > SEUIL_NOTE_EQUIPES:
            lines += ["", tr("teams_note")]
    return lines + [""]


def ecrire_points(nom: str, aujourdhui: dt.date, wip: list[dict], age_of, est_dormant, est_attente,
                  periodes: dict | None, segment_de: dict | None, segments: list[str], base: str, tr=None) -> None:
    """Points de l'Aging WIP du tableau de bord : un par ticket en cours (équipe, état, segment, âge, âge dans le
    segment, nature), sans clé ni titre. Fichier à part, Flux-Lab/tableaux/points-<nom>-AAAA-MM-JJ.json (hors Git,
    permissions 600) : les rapports restent des agrégats. Segment et âge dans le segment : seulement avec
    --history."""
    points = []
    for t in wip:
        segment = age_segment = None
        if periodes is not None and id(t) in periodes:
            courante = [v for v in visites(periodes[id(t)], segment_de, ouvert=True) if v["en_cours"]]
            if courante:
                segment, age_segment = courante[0]["segment"], courante[0]["jours"]
        nature = ("dormant" if est_dormant and est_dormant(t) else
                  "attente" if est_attente and est_attente(t) else "actif")
        points.append({"equipe": t["equipe"], "etat": t["etat"], "segment": segment, "age": age_of(t),
                       "age_segment": age_segment, "nature": nature})
    points.sort(key=lambda p: (p["equipe"], p["etat"], p["age"]))
    contenu = {"nom": nom, "date": aujourdhui.isoformat(), "base_age": base, "segments": segments, "points": points}
    dossier = FLUX_DIR / "tableaux"
    dossier.mkdir(parents=True, exist_ok=True)
    os.chmod(dossier, 0o700)
    chemin = dossier / f"points-{nom or 'serie'}-{aujourdhui.isoformat()}.json"
    chemin.write_text(json.dumps(contenu, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(chemin, 0o600)
    print((tr or T_FR)("points_written", n=len(points), path=chemin))


def write_report(r: dict, tr=None) -> None:
    tr = tr or T_FR
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"flux-{r['nom']}-{r['date']}" if r["nom"] else f"flux-{r['date']}"      # nom de fichier : le même dans toutes les langues
    when, how = r["prevision_quand"], r["prevision_combien"]
    deb = r["debit"]
    aucun = tr("none_word")
    lines = [
        tr("report_title", name=tr("name_suffix", name=r["nom"]) if r["nom"] else "", date=r["date"]),
        "",
        tr("report_period", start=r["periode"][0], end=r["periode"][1], weeks=r["semaines"],
           types=libelle_types(r["types"], tr)),
        "",
    ]
    if r.get("perimetre"):
        pm = r["perimetre"]
        lines += [tr("scope_line",
                     scope=(tr("scope_all") if pm["projets"] == "tous" else tr("scope_projects", list=", ".join(pm["projets"]))),
                     kept=pm["tickets_retenus"], read=pm["tickets_lus"]), ""]
    if r.get("exports"):
        e = r["exports"]
        lines += [tr("merge_by_key", n=e["fichiers"], dups=e["doublons_retires"]) if e["doublons_retires"] is not None
                  else tr("merge_no_key", n=e["fichiers"]), ""]
    if r.get("ecartes"):
        ec = r["ecartes"]
        lines += [tr("excluded_line", total=ec["total"])
                  + "".join(tr(cle) + ", ".join(f"{a} {n}" for a, n in v.items())
                            for cle, v in (("excluded_part_type", ec["par_type"]),
                                           ("excluded_part_project", ec["par_projet"])) if v) + ".", ""]
    lines += [
        tr("throughput_heading"),
        tr("throughput_total", n=r["termines"], avg=f"{deb['moyenne']:.1f}", median=f"{deb['mediane']:.0f}",
           zero=deb["semaines_a_zero"]),
        tr("throughput_series", series=", ".join(map(str, r["debit_par_semaine"]))),
        tr("throughput_reasons", list=", ".join(f"{libelle_motif(m, tr)} {n}" for m, n in r["motifs_livres"].items()) or aucun),
        tr("closed_undelivered", list=", ".join(f"{m} {n}" for m, n in r["clos_sans_livraison"].items()) or aucun),
        "",
        *arrivees_lines(r, tr),
        *fermetures_lines(r, tr),
        tr("leadtime_heading"),
        tr("leadtime_all_types", p=fmt_p(r["lead_time_jours"], tr=tr)),
    ]
    for kind, data in r["lead_time_par_type"].items():
        lines.append(tr("leadtime_by_type", kind=kind, n=data["termines"], p=fmt_p(data["lead_time"], tr=tr)))
    age = r["age_wip_jours"]
    base = libelle_base(age["base"], tr)
    lines += [
        "",
        tr("wip_heading"),
        tr("wip_line", wip=r["wip"], states=", ".join(f"{s} {n}" for s, n in r["wip_par_etat"].items()) or aucun,
           todo=r["a_faire"]),
        tr("age_from_start", p=fmt_p(age["depuis_debut"], tr=tr)),
        tr("age_from_creation", p=fmt_p(age["depuis_creation"], tr=tr)),
        tr("age_over_p85", n=age["au_dela_du_lead_time_p85"], base=base),
    ]
    seuils = r["age_seuils"]
    lines.append(tr("age_thresholds", a=seuils["plus_de_30_j"], b=seuils["plus_de_90_j"], c=seuils["plus_de_180_j"],
                    d=seuils["plus_de_365_j"], e=seuils["plus_de_730_j"]))
    if r.get("dormants"):
        d, w, f = r["dormants"], r["wip_repartition"], r["a_faire_repartition"]
        lines.append(tr("wip_split", active=w["actif"], active_share=pourcent(w["parts"]["actif"], tr),
                        waiting=w["attente"], waiting_share=pourcent(w["parts"]["attente"], tr),
                        dormant=w["dormant"], dormant_share=pourcent(w["parts"]["dormant"], tr), total=r["wip"]))
        lines.append(tr("todo_split", alive=f["vivant"], dormant=f["dormant"], share=pourcent(f["part_dormant"], tr),
                        total=r["a_faire"]))
        lines.append(tr("dormant_note_history", days=d["seuil_jours"], n=d.get("sans_historique", 0)))
    elif r.get("wip_attente"):
        w = r["wip_attente"]
        lines.append(tr("wip_waiting_split", active=w["actif"], waiting=w["attente"],
                        list=", ".join(f"{s} {n}" for s, n in w["par_etat"].items()) or aucun,
                        share=pourcent(w["part"], tr), total=r["wip"]))
    if r.get("classement"):
        lines.append(tr("category_classification"))
    nature = bool(r.get("wip_attente"))
    dorm = bool(r.get("dormants"))
    lines += ["", tr("age_by_state_heading", base=base), "",
              f"| {tr('age_state_col_state')} | " + (f"{tr('age_state_col_nature')} | " if nature else "") + tr("age_state_cols")
              + (tr("age_state_cols_dormant") if dorm else ""),
              "|---|" + ("---|" if nature else "") + "---|---|---|---|---|" + ("---|---|" if dorm else "")]
    for state, data in r["age_par_etat"].items():
        p = data["age"]
        lines.append(f"| {state} | " + ((tr("nature_waiting") if data.get("attente") else tr("nature_active")) + " | " if nature else "")
                     + f"{data['elements']} | {round(p[50]) if p else tr('na')}{tr('days_suffix')} | "
                     f"{round(p[85]) if p else tr('na')}{tr('days_suffix')} | {data['plus_de_90_j']} | {data['plus_de_365_j']} |"
                     + (f" {data['dormants']} | {tr('pct', value=round(100 * data['dormants'] / data['elements']))} |" if dorm else ""))
    lines.append("")
    if r.get("age_a_faire_par_etat"):
        lines += [tr("queues_heading"), "", tr("queues_intro"), "",
                  tr("queues_table") + (tr("queues_table_dormant") if dorm else ""),
                  "|---|---|---|---|---|---|---|" + ("---|" if dorm else "")]
        for state, d in r["age_a_faire_par_etat"].items():
            pc, pm = d["age_creation"], d["age_categorie"]
            def day(p: dict | None, k: int) -> str:
                v = pct(p, k)
                return f"{round(v)}{tr('days_suffix')}" if v is not None else tr("na")
            lines.append(f"| {state} | {d['elements']} | {day(pc, 50)} | {day(pc, 85)} | {day(pm, 50)} | "
                         f"{d['plus_de_90_j']} | {d['plus_de_365_j']} |" + (f" {d['dormants']} |" if dorm else ""))
        lines.append("")
    if r["little_jours"] is not None:
        if r.get("dormants"):
            total = r.get("little_jours_wip_total")
            lines.append(tr("little_dormant", n=r["wip_non_dormant"], days=f"{r['little_jours']:.0f}")
                         + (tr("little_dormant_total", wip=r["wip"], days=f"{total:.0f}") if total is not None else ""))
        else:
            lines.append(tr("little", days=f"{r['little_jours']:.0f}"))
    if r["etats_non_classes"]:
        lines.append(tr("unclassified_states", list=", ".join(f"{s} {n}" for s, n in r["etats_non_classes"].items())))
    if r.get("par_equipe"):
        att = bool(r.get("wip_attente")) and not dorm
        lines += ["", tr("by_team_heading"), "",
                  tr("team_table") + (tr("team_table_waiting") if att else "") + (tr("team_table_dormant") if dorm else ""),
                  "|---|---|---|---|---|---|---|---|" + ("---|---|" if att else "") + ("---|" * 8 if dorm else "")]
        for team, d in r["par_equipe"].items():
            lt, ag = d["lead_time"], d["age_wip"]
            def days(p: dict, k: int) -> str:
                return f"{round(p[k])}{tr('days_suffix')}" if p else tr("na")
            extra = ""
            if att:
                extra = f" {d.get('wip_attente', 0)} | {pourcent(d.get('part_attente'), tr)} |"
            if dorm and d.get("wip_repartition"):
                w = d["wip_repartition"]

                def pp(k: str) -> str:
                    return pourcent(w["parts"][k], tr)
                extra = (f" {w['actif']} | {w['attente']} | {w['dormant']} | {pp('actif')} | {pp('attente')} | "
                         f"{pp('dormant')} | {d['a_faire']} | {d['a_faire_dormant']} |")
            lines.append(f"| {libelle_equipe(team, tr)} | {d['termines']} | {d['debit_moyen']:.1f} | {days(lt, 50)} | {days(lt, 85)} | "
                         f"{d['wip']} | {days(ag, 50)} | {d['wip_plus_de_90_j']} |" + extra)
        if len(r["par_equipe"]) > SEUIL_NOTE_EQUIPES:
            lines += ["", tr("teams_note")]
        lines += ["", tr("done_per_week_intro"), ""]
        for team, d in r["par_equipe"].items():
            lines.append(tr("team_series", team=libelle_equipe(team, tr), series=", ".join(map(str, d["debit_par_semaine"]))))
        lines.append("")
        pe = r.get("tickets_plusieurs_equipes")
        if pe:
            lines += [tr("multi_team_tickets", total=pe["total"], of=pe["sur"], done=pe["termines"], wip=pe["en_cours"],
                         sep=pe["separateur"]), ""]
    if r.get("temps_par_segment"):
        lines += segments_lines(r, tr)
    lines += ["", tr("forecast_heading")]
    if when["semaines"]:
        w = when["semaines"]
        lines.append(tr("forecast_when", n=when["elements"],
                        qualifier=(tr("forecast_qualifier_nondormant")
                                   if r.get("dormants") and "prevision_quand_wip_total" in r else ""),
                        p50=w[50], p85=w[85], p95=w[95]))
        tot = r.get("prevision_quand_wip_total")
        if tot and tot["semaines"]:
            wt = tot["semaines"]
            lines.append(tr("forecast_total_note", n=tot["elements"], p50=wt[50], p85=wt[85], p95=wt[95]))
    if how["elements"]:
        h = how["elements"]
        lines.append(tr("forecast_how_many", date=how["date"], p85=h[85], p50=h[50], p95=h[95]))
    lines += ["", *lecture_lines(r, tr), ""]
    lines += [tr("limits_heading"), tr("limit_leadtime"), tr("limit_forecast")]
    if not r["colonnes"].get("debut"):
        lines.append(tr("limit_no_start"))
    (REPORT_DIR / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (REPORT_DIR / f"{stem}.json").write_text(json.dumps(r, ensure_ascii=False, indent=2, default=str),
                                             encoding="utf-8")
    print("\n".join(lines))
    print(tr("report_path", path=REPORT_DIR / (stem + ".md")))


# ---------------------------------------------------------------------------
# Comparaison de deux rapports du même périmètre
# ---------------------------------------------------------------------------

def find_reports(nom: str) -> dict[str, Path]:
    """Rapports JSON d'un périmètre, par date croissante. « alpha » ne prend pas « alpha-recent »."""
    prefix = f"flux-{nom}-" if nom else "flux-"
    pattern = re.compile(rf"^{re.escape(prefix)}(\d{{4}}-\d{{2}}-\d{{2}})\.json$")
    found: dict[str, Path] = {}
    if REPORT_DIR.exists():
        for path in REPORT_DIR.glob("*.json"):
            match = pattern.match(path.name)
            if match:
                found[match.group(1)] = path
    return dict(sorted(found.items()))


def load_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pct(values: dict | None, p: int) -> float | None:
    """Percentile p d'un rapport relu (les clés deviennent des chaînes en JSON)."""
    if not values:
        return None
    value = values.get(str(p), values.get(p))
    return float(value) if value is not None else None


def ratio(before: float | None, after: float | None) -> float | None:
    if before is None or after is None or before == 0:
        return None
    return (after - before) / before


def delta(before: float | None, after: float | None, unit: str = "", digits: int = 0, tr=None) -> str:
    """« 12 → 9 (-25 %) » ; n/d pour une valeur absente."""
    na = (tr or T_FR)("na")

    def show(x: float | None) -> str:
        return na if x is None else f"{x:.{digits}f}{unit}"
    change = ratio(before, after)
    return f"{show(before)} → {show(after)}" + (f" ({change:+.0%})" if change is not None else "")


def dated(report: dict, series: list[int] | None = None) -> list[tuple[dt.date, int]]:
    """Série hebdomadaire d'un rapport, chaque semaine avec son lundi."""
    start = dt.date.fromisoformat(report["periode"][0])
    values = report["debit_par_semaine"] if series is None else series
    return [(start + dt.timedelta(weeks=i), n) for i, n in enumerate(values)]


def recent_throughput(before: list[tuple[dt.date, int]], after: list[tuple[dt.date, int]]) -> dict | None:
    """Débit des semaines apparues depuis le rapport précédent, contre les dernières semaines de celui-ci
    (au moins 4, pour ne pas comparer une semaine à une semaine)."""
    if not before or not after:
        return None
    new = [n for day, n in after if day > before[-1][0]]
    if not new:
        return None
    prior = [n for _, n in before[-max(len(new), 4):]]
    return {"semaines_nouvelles": len(new), "moyenne_nouvelles": float(np.mean(new)),
            "semaines_avant": len(prior), "moyenne_avant": float(np.mean(prior))}


def grouping(series: list[int]) -> dict | None:
    """Clôtures groupées : part des éléments terminés tombés sur les 2 meilleures semaines de la fenêtre."""
    window = series[-FENETRE_REGROUPEMENT:]
    total = sum(window)
    if total < MIN_REGROUPEMENT:
        return None
    share = sum(sorted(window, reverse=True)[:2]) / total
    return {"clotures": total, "part_2_meilleures": share,
            "semaines_a_zero": sum(1 for n in window if n == 0), "groupe": share >= SEUIL_REGROUPEMENT}


def show_grouping(g: dict | None, tr=None) -> str:
    tr = tr or T_FR
    if g is None:
        return tr("na")
    return f"{g['part_2_meilleures']:.0%}" + (tr("grouped_suffix") if g["groupe"] else "")


def compare(before: dict, after: dict, tr=None) -> None:
    """Écrit evolution-<nom>-AAAA-MM-JJ.md (dans la langue demandée) et .json (signaux et notes toujours en français :
    le format de données ne change pas avec la langue), puis affiche le rapport."""
    tr = tr or T_FR
    lines, signals, notes, recent = _comparer(before, after, tr)
    if tr.language != DEFAULT_LANGUAGE:
        _, signals, notes, _ = _comparer(before, after, T_FR)
    nom = after.get("nom", "")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"evolution-{nom}-{after['date']}" if nom else f"evolution-{after['date']}"
    (REPORT_DIR / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary = {"nom": nom, "avant": before["date"], "apres": after["date"], "signaux": signals,
               "comparabilite": notes, "debit_recent": recent}
    (REPORT_DIR / f"{stem}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n".join(lines))
    print(tr("evo_path", path=REPORT_DIR / (stem + ".md")))


def _comparer(before: dict, after: dict, tr) -> tuple[list[str], list[str], list[str], dict | None]:
    """Rapport Markdown de la comparaison dans la langue de `tr` : (lignes, signaux, notes de comparabilité, débit récent)."""
    if "date" not in before or "date" not in after:
        sys.exit(tr("compare_no_date"))
    if before["date"] >= after["date"]:
        sys.exit(tr("compare_date_order", before=before["date"], after=after["date"]))
    nom = after.get("nom", "")
    gap = (dt.date.fromisoformat(after["date"]) - dt.date.fromisoformat(before["date"])).days
    signals: list[str] = []
    notes: list[str] = []
    # un rapport d'un ancien format peut n'avoir pas toutes les clés : la section qui en dépend est sautée, avec
    # une ligne qui dit pourquoi, au lieu d'arrêter la comparaison
    manques: dict[str, str] = {}
    SECTIONS = ("Débit", "Lead time", "Travail en cours", "Vieillissement", "Prévisions")
    NOMS_SECTIONS = {"Débit": "section_throughput", "Lead time": "section_lead_time", "Travail en cours": "section_wip",
                     "Vieillissement": "section_aging", "Prévisions": "section_forecasts", "Types retenus": "section_types",
                     "Fenêtres": "section_windows", "États en cours": "section_states"}
    jours = tr("days_suffix")
    tendance = lambda change: tr("trend_up" if change > 0 else "trend_down")

    def requis(section: str, *cles: str) -> bool:
        absentes = [tr("report_missing_keys", when=tr(quand), date=r.get("date", "?"),
                       keys=", ".join(c for c in cles if c not in r))
                    for quand, r in (("report_previous", before), ("report_new", after)) if any(c not in r for c in cles)]
        if absentes:
            manques[section] = tr("section_not_compared", section=tr(NOMS_SECTIONS[section]), details=" ; ".join(absentes))
        return not absentes

    def ligne_manque(section: str) -> list[str]:
        return [f"- {manques[section]}"] if section in manques else []

    # comparabilité : un écart qui vient d'un changement de réglage n'est pas un changement du flux
    if requis("Types retenus", "types") and before["types"] != after["types"]:
        notes.append(tr("note_types_differ", before=libelle_types(before["types"], tr),
                        after=libelle_types(after["types"], tr)))
    projets_avant = (before.get("perimetre") or {}).get("projets")
    projets_apres = (after.get("perimetre") or {}).get("projets")
    if projets_avant != projets_apres:
        def libelle(projets) -> str:
            return (tr("scope_unspecified") if projets is None
                    else (tr("all_word") if projets == "tous" else projets) if isinstance(projets, str)
                    else ", ".join(projets))
        notes.append(tr("note_scope_differs", before=libelle(projets_avant), after=libelle(projets_apres)))
    if requis("Fenêtres", "semaines") and before["semaines"] != after["semaines"]:
        notes.append(tr("note_windows", before=before["semaines"], after=after["semaines"]))
    if bool((before.get("colonnes") or {}).get("debut")) != bool((after.get("colonnes") or {}).get("debut")):
        notes.append(tr("note_start_column"))
    ok_etats = requis("États en cours", "wip_par_etat")
    states_before = set(before["wip_par_etat"]) if ok_etats else set()
    states_after = set(after["wip_par_etat"]) if ok_etats else set()
    if states_after - states_before:
        notes.append(tr("note_states_appeared", list=", ".join(sorted(states_after - states_before))))
    if states_before - states_after:
        notes.append(tr("note_states_gone", list=", ".join(sorted(states_before - states_after))))

    # débit
    ok_debit = requis("Débit", "periode", "debit_par_semaine", "debit")
    recent = recent_throughput(dated(before), dated(after)) if ok_debit else None
    if recent:
        change = ratio(recent["moyenne_avant"], recent["moyenne_nouvelles"])
        if change is not None and abs(change) >= SEUIL_DEBIT:
            signals.append(tr("signal_throughput", trend=tendance(change), new=recent["moyenne_nouvelles"],
                              n=recent["semaines_nouvelles"], old=recent["moyenne_avant"],
                              m=recent["semaines_avant"], change=change))
    elif ok_debit:
        notes.append(tr("note_no_new_week"))

    # lead time
    ok_lead = requis("Lead time", "lead_time_jours", "lead_time_par_type")
    lt_b = pct(before["lead_time_jours"], 85) if ok_lead else None
    lt_a = pct(after["lead_time_jours"], 85) if ok_lead else None
    change = ratio(lt_b, lt_a)
    if change is not None and abs(change) >= SEUIL_LEAD_TIME:
        signals.append(tr("signal_lead", trend=tendance(change), before=lt_b, after=lt_a, change=change))

    # travail en cours et loi de Little
    ok_wip = requis("Travail en cours", "wip", "a_faire")
    change = ratio(before["wip"], after["wip"]) if ok_wip else None
    if change is not None and abs(change) >= SEUIL_WIP:
        signals.append(tr("signal_wip", trend=tendance(change), before=before["wip"], after=after["wip"], change=change))
    change = ratio(before.get("little_jours"), after.get("little_jours"))
    if change is not None and abs(change) >= SEUIL_WIP:
        signals.append(tr("signal_little", after=after["little_jours"], before=before["little_jours"], change=change))

    # vieillissement (comptes nets : le script ne garde aucun identifiant de ticket)
    ok_age = requis("Vieillissement", "age_seuils", "age_wip_jours") and all(
        "au_dela_du_lead_time_p85" in r["age_wip_jours"] and all(f"plus_de_{d}_j" in r["age_seuils"] for d in (30, 90, 180, 365, 730))
        for r in (before, after))
    if not ok_age and "Vieillissement" not in manques:
        manques["Vieillissement"] = tr("aging_not_compared")
    if ok_age:
        for key, label in (("plus_de_90_j", "90"), ("plus_de_365_j", "365")):
            b, a = before["age_seuils"][key], after["age_seuils"][key]
            if a > b:
                signals.append(tr("signal_more_old", label=label, before=b, after=a))
        b, a = before["age_wip_jours"]["au_dela_du_lead_time_p85"], after["age_wip_jours"]["au_dela_du_lead_time_p85"]
        if a > b:
            signals.append(tr("signal_more_over_p85", before=b, after=a))

    # files avant engagement (rapports récents seulement : la clé n'existe pas dans les anciens)
    todo_b, todo_a = before.get("age_a_faire_par_etat") or {}, after.get("age_a_faire_par_etat") or {}
    if todo_a and not todo_b:
        notes.append(tr("note_queues_missing"))
    for state in sorted(set(todo_b) & set(todo_a)):
        b, a = todo_b[state]["plus_de_90_j"], todo_a[state]["plus_de_90_j"]
        if a - b >= MIN_VIEILLISSEMENT_EQUIPE:
            signals.append(tr("signal_queue_old", state=state, before=b, after=a))
        change = ratio(todo_b[state]["elements"], todo_a[state]["elements"])
        if change is not None and abs(change) >= SEUIL_WIP and abs(todo_a[state]["elements"] - todo_b[state]["elements"]) >= MIN_VIEILLISSEMENT_EQUIPE:
            signals.append(tr("signal_queue_size", state=state, trend=tendance(change),
                              before=todo_b[state]["elements"], after=todo_a[state]["elements"], change=change))

    # équipes
    teams_b, teams_a = before.get("par_equipe") or {}, after.get("par_equipe") or {}
    team_rows = []
    for team in sorted(set(teams_b) | set(teams_a)):
        tb, ta = teams_b.get(team), teams_a.get(team)
        nom_equipe = libelle_equipe(team, tr)
        if tb is None or ta is None:
            notes.append(tr("note_team_one_report", team=nom_equipe))
            continue
        cles_equipe = ("debit_par_semaine", "lead_time", "wip", "wip_plus_de_90_j")
        if any(c not in r for r in (tb, ta) for c in cles_equipe) or "periode" not in before or "periode" not in after:
            notes.append(tr("note_team_not_compared", team=nom_equipe))
            continue
        rec = recent_throughput(dated(before, tb["debit_par_semaine"]), dated(after, ta["debit_par_semaine"]))
        g_b, g_a = grouping(tb["debit_par_semaine"]), grouping(ta["debit_par_semaine"])
        team_rows.append((team, tb, ta, rec, g_b, g_a))
        if rec and max(rec["moyenne_avant"], rec["moyenne_nouvelles"]) >= 1:
            change = ratio(rec["moyenne_avant"], rec["moyenne_nouvelles"])
            if change is not None and abs(change) >= SEUIL_DEBIT_EQUIPE:
                signals.append(tr("signal_team_throughput", team=nom_equipe, trend=tendance(change),
                                  before=rec["moyenne_avant"], after=rec["moyenne_nouvelles"], change=change))
            elif rec["moyenne_avant"] > 0 and rec["moyenne_nouvelles"] == 0:
                signals.append(tr("signal_team_zero", team=nom_equipe))
        if ta["wip_plus_de_90_j"] - tb["wip_plus_de_90_j"] >= MIN_VIEILLISSEMENT_EQUIPE:
            signals.append(tr("signal_team_aging", team=nom_equipe, before=tb["wip_plus_de_90_j"],
                              after=ta["wip_plus_de_90_j"]))
        if g_a and g_a["groupe"] and not (g_b and g_b["groupe"]):
            signals.append(tr("signal_team_grouped", team=nom_equipe, window=FENETRE_REGROUPEMENT,
                              share=g_a["part_2_meilleures"]))
        if g_b and g_b["groupe"] and g_a and not g_a["groupe"]:
            signals.append(tr("signal_team_ungrouped", team=nom_equipe, before=g_b["part_2_meilleures"],
                              after=g_a["part_2_meilleures"]))

    # rapport
    lines = [
        tr("evo_title", name=tr("name_suffix", name=nom) if nom else "", before=before["date"], after=after["date"]),
        "",
        tr("evo_intro", before=before["date"], after=after["date"], gap=gap),
        "",
        tr("evo_moved_heading"),
        "",
    ]
    lines += [f"- {s}" for s in signals] or [tr("evo_no_signal")]
    lines += ["", tr("evo_thresholds", throughput=SEUIL_DEBIT, team_throughput=SEUIL_DEBIT_EQUIPE, lead=SEUIL_LEAD_TIME,
                     wip=SEUIL_WIP, min_aging=MIN_VIEILLISSEMENT_EQUIPE, share=SEUIL_REGROUPEMENT,
                     window=FENETRE_REGROUPEMENT)]
    ok_prev = requis("Prévisions", "prevision_quand", "prevision_combien")
    notes += [m for sec, m in manques.items() if sec not in SECTIONS]
    sautees = [sec for sec in SECTIONS if sec in manques]
    if sautees:
        notes.append(tr("evo_partial", list=", ".join(tr(NOMS_SECTIONS[sec]) for sec in sautees)))
    if notes:
        lines += ["", tr("evo_comparability_heading"), ""] + [f"- {n}" for n in notes]
    lines += ["", tr("throughput_heading"), ""] + ligne_manque("Débit")
    if ok_debit:
        if recent:
            lines.append(tr("evo_new_weeks", n=recent["semaines_nouvelles"], new=recent["moyenne_nouvelles"],
                            old=recent["moyenne_avant"], m=recent["semaines_avant"]))
        lines += [tr("evo_mean", delta=delta(before["debit"]["moyenne"], after["debit"]["moyenne"], digits=1, tr=tr),
                     before=before["debit"]["semaines_a_zero"], after=after["debit"]["semaines_a_zero"]),
                  tr("evo_series", series=", ".join(map(str, after["debit_par_semaine"])))]
    lines += ["", tr("leadtime_heading"), ""] + ligne_manque("Lead time")
    if ok_lead:
        lines += [tr("evo_lead_table"), "|---|---|---|",
                  f"| {tr('evo_all_types')} | {delta(pct(before['lead_time_jours'], 50), pct(after['lead_time_jours'], 50), jours, tr=tr)} | "
                  f"{delta(lt_b, lt_a, jours, tr=tr)} |"]
        types_b, types_a = before["lead_time_par_type"], after["lead_time_par_type"]
        for kind in sorted(set(types_b) | set(types_a)):
            lb, la = (types_b.get(kind) or {}).get("lead_time"), (types_a.get(kind) or {}).get("lead_time")
            lines.append(f"| {kind} | {delta(pct(lb, 50), pct(la, 50), jours, tr=tr)} | {delta(pct(lb, 85), pct(la, 85), jours, tr=tr)} |")
    lines += ["", tr("wip_heading"), ""] + ligne_manque("Travail en cours")
    if ok_wip:
        lines += [tr("evo_wip", wip=delta(before["wip"], after["wip"], tr=tr), todo=delta(before["a_faire"], after["a_faire"], tr=tr)),
                  tr("evo_little", delta=delta(before.get("little_jours"), after.get("little_jours"), jours, tr=tr))]
    if ok_etats:
        lines += ["", tr("evo_state_table"), "|---|---|---|"]
        for state in sorted(states_before | states_after,
                            key=lambda s: (-(after["wip_par_etat"].get(s, 0) + before["wip_par_etat"].get(s, 0)), s)):
            lines.append(f"| {state} | {before['wip_par_etat'].get(state, 0)} | {after['wip_par_etat'].get(state, 0)} |")
    lines += ["", tr("evo_aging_heading"), ""] + ligne_manque("Vieillissement")
    if ok_age:
        sb, sa = before["age_seuils"], after["age_seuils"]
        lines += [tr("evo_aging_table"), "|---|---|---|"]
        for days in (30, 90, 180, 365, 730):
            lines.append(f"| {tr('evo_days_row', days=days)} | {sb[f'plus_de_{days}_j']} | {sa[f'plus_de_{days}_j']} |")
        lines.append(f"| {tr('evo_over_p85_row')} | {before['age_wip_jours']['au_dela_du_lead_time_p85']} | "
                     f"{after['age_wip_jours']['au_dela_du_lead_time_p85']} |")
    if todo_b and todo_a:
        lines += ["", tr("evo_queues_heading"), "", tr("evo_queues_table"), "|---|---|---|---|"]
        for state in sorted(set(todo_b) | set(todo_a),
                            key=lambda s: (-((todo_a.get(s) or {}).get("elements", 0) + (todo_b.get(s) or {}).get("elements", 0)), s)):
            tb, ta = todo_b.get(state) or {}, todo_a.get(state) or {}
            lines.append(f"| {state} | {delta(tb.get('elements'), ta.get('elements'), tr=tr)} | "
                         f"{delta(pct(tb.get('age_creation'), 50), pct(ta.get('age_creation'), 50), jours, tr=tr)} | "
                         f"{tb.get('plus_de_90_j', tr('na'))} → {ta.get('plus_de_90_j', tr('na'))} |")
    if team_rows:
        lines += ["", tr("by_team_heading"), "", tr("evo_team_table"), "|---|---|---|---|---|---|"]
        for team, tb, ta, rec, g_b, g_a in team_rows:
            debit = delta(rec["moyenne_avant"], rec["moyenne_nouvelles"], digits=1, tr=tr) if rec else tr("na")
            lines.append(f"| {libelle_equipe(team, tr)} | {debit} | {delta(pct(tb['lead_time'], 85), pct(ta['lead_time'], 85), jours, tr=tr)} | "
                         f"{delta(tb['wip'], ta['wip'], tr=tr)} | {tb['wip_plus_de_90_j']} → {ta['wip_plus_de_90_j']} | "
                         f"{show_grouping(g_b, tr)} → {show_grouping(g_a, tr)} |")
        lines += ["", tr("evo_group_note", window=FENETRE_REGROUPEMENT, min=MIN_REGROUPEMENT)]
    lines += ["", tr("evo_forecasts_heading"), ""]
    if ok_prev:
        wb, wa = before["prevision_quand"], after["prevision_quand"]
        if wb.get("semaines") and wa.get("semaines"):
            if wb["elements"] == wa["elements"]:
                lines.append(tr("evo_forecast_same", n=wa["elements"],
                                delta=delta(pct(wb["semaines"], 85), pct(wa["semaines"], 85), tr("weeks_suffix"), tr=tr)))
            else:
                lines.append(tr("evo_forecast_diff", before_n=wb["elements"], before_weeks=pct(wb["semaines"], 85),
                                after_n=wa["elements"], after_weeks=pct(wa["semaines"], 85)))
        hb, ha = before["prevision_combien"], after["prevision_combien"]
        if hb.get("elements") and ha.get("elements") and hb.get("date") == ha.get("date"):
            lines.append(tr("evo_forecast_how_many", date=ha["date"],
                            delta=delta(pct(hb["elements"], 85), pct(ha["elements"], 85), tr=tr)))
        if lines[-1] == "":
            lines.append(tr("evo_forecast_none"))
    else:
        lines += ligne_manque("Prévisions")
    lines += ["", tr("limits_heading"), "", tr("evo_limit_overlap"), tr("evo_limit_net"), tr("evo_limit_teams")]
    return lines, signals, notes, recent


def cmd_comparer(args: argparse.Namespace) -> None:
    tr = Messages(CATALOGS, args.language)
    reports = find_reports(args.nom)
    label = args.nom or tr("no_name_label")
    if len(reports) < 2:
        sys.exit(tr("compare_need_two", label=label, dir=REPORT_DIR, found=", ".join(reports) or tr("none_word")))
    after_day = args.apres or list(reports)[-1]
    if after_day not in reports:
        sys.exit(tr("compare_no_report_for", label=label, day=after_day, list=", ".join(reports)))
    earlier = [day for day in reports if day < after_day]
    before_day = args.avant or (earlier[-1] if earlier else None)
    if before_day not in reports:
        sys.exit(tr("compare_no_earlier", label=label, day=after_day, list=", ".join(reports)))
    compare(load_report(reports[before_day]), load_report(reports[after_day]), tr)


OPTIONS_RENOMMEES = {**cfg.OPTIONS_COMMUNES, "--equipes-seulement": "--teams-only", "--sans-comparaison": "--no-comparison",
                     "--objectif": "--target", "--date-cible": "--target-date",
                     "--dormants-historique": "--dormant-from-history", "--motifs-fermetures": "--batch-closure-resolutions",
                     "--avant": "--before", "--apres": "--after"}


def cmd_config(args: argparse.Namespace) -> None:
    """config migrate : réécrit Flux-Lab/flux.yaml avec les noms anglais. À lancer par l'utilisateur (le fichier reste en
    place, l'ancien est gardé à côté). N'affiche que des noms de réglages, jamais une valeur."""
    tr = Messages(CATALOGS, args.language)
    if not CONFIG_FILE.exists():
        sys.exit(tr("config_not_found", path=CONFIG_FILE))
    try:
        changements = cfg.migrate_file(CONFIG_FILE, dry_run=args.dry_run)
    except cfg.MigrationConflict as conflit:
        print(tr("config_conflict", name=CONFIG_FILE.name, n=len(conflit.conflits)))
        for phrase in conflit.conflits:
            print(f"  {phrase}")
        print(tr("config_conflict_hint"))
        if args.dry_run and conflit.changements:
            print(tr("config_would_change", name=CONFIG_FILE.name, n=len(conflit.changements)))
            for changement in conflit.changements:
                print(f"  {changement}")
        sys.exit(1)
    if not changements:
        print(tr("config_nothing"))
        return
    print(tr("config_would_change" if args.dry_run else "config_changed", name=CONFIG_FILE.name, n=len(changements)))
    for changement in changements:
        print(f"  {changement}")
    if not args.dry_run:
        print(tr("config_old_kept", name=CONFIG_FILE.name))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Métriques de flux à partir d'un export Jira")
    commands = parser.add_subparsers(dest="command", required=True)
    states = commands.add_parser("statuses", help="colonnes, période, états et types de l'export")
    states.add_argument("export", nargs="*", help="un ou plusieurs exports CSV (lots de projets) ; aucun avec --source db")
    states.add_argument("--source", default="csv", metavar="{csv,db}",
                        help="d'où viennent les tickets : csv (défaut, les exports donnés) ou db (schéma flow de la base)")
    add_language_option(states)
    calc = commands.add_parser("compute", help="lead time, débit, WIP, âge, prévisions")
    calc.add_argument("export", nargs="*", help="un ou plusieurs exports CSV (lots de projets) ; aucun avec --source db")
    calc.add_argument("--source", default="csv", metavar="{csv,db}",
                      help="d'où viennent les tickets : csv (défaut, les exports donnés) ou db (schéma flow de la base ; "
                           "--history lit alors les transitions de la base)")
    calc.add_argument("--name", dest="nom", default="", help="nom court de l'équipe ou du périmètre, pour le rapport")
    calc.add_argument("--weeks", dest="semaines", type=int, default=26, help="semaines complètes analysées (défaut 26)")
    calc.add_argument("--target", dest="objectif", type=int, help="éléments à terminer pour la prévision (défaut : le WIP)")
    calc.add_argument("--target-date", dest="date_cible", help="date (AAAA-MM-JJ) pour la prévision « combien d'ici là »")
    calc.add_argument("--scope", dest="perimetre", help="projets du périmètre (clés séparées par des virgules) ou « tous » ; sans "
                                          "l'option, tous les tickets de l'export (flux.yaml n'est pas lu pour ce réglage)")
    calc.add_argument("--types", help="types de tickets retenus, séparés par des virgules")
    calc.add_argument("--teams-only", dest="equipes_seulement", action="store_true",
                      help="exclure les tickets sans équipe (flux à part, absent du WIP)")
    calc.add_argument("--no-comparison", dest="sans_comparaison", action="store_true",
                      help="ne pas comparer avec le rapport précédent du même nom")
    calc.add_argument("--dormants", nargs="?", const="", default=None, help=argparse.SUPPRESS)   # supprimée : refusée avec un message
    calc.add_argument("--dormant-from-history", dest="dormants_historique", action="store_true",
                      help="déduit les dormants de l'historique des états (cache de --history, ou celui par défaut) "
                           "(seule voie pour séparer le travail dormant)")
    calc.add_argument("--history", dest="historique", nargs="?", const="", default=None, metavar="CACHE",
                      help="ajoute la section « Temps par segment » à partir de l'historique des états collecté par "
                           "history_jira.py (défaut : Flux-Lab/historique/transitions.json)")
    calc.add_argument("--points", action="store_true",
                      help="écrit aussi Flux-Lab/tableaux/points-<nom>-AAAA-MM-JJ.json : un point par ticket en cours "
                           "(équipe, état, segment, âge, nature), sans clé, pour le tableau de bord (hors Git)")
    calc.add_argument("--batch-closure-resolutions", dest="motifs_fermetures", metavar="MOTIFS",
                      help="motifs de résolution suivis par la section « Fermetures groupées », séparés par des virgules "
                           "(« Done,Accepted & Released »), ou « tous » pour tous les motifs livrés ; remplace "
                           "batch_closure_resolutions de flux.yaml pour ce calcul")
    calc.add_argument("--today", dest="aujourdhui", help=argparse.SUPPRESS)   # pour les tests
    add_language_option(calc)
    comp = commands.add_parser("compare", help="ce qui a bougé entre deux rapports du même périmètre")
    comp.add_argument("--name", dest="nom", default="", help="nom du périmètre, comme dans compute --name")
    comp.add_argument("--before", dest="avant", help="date (AAAA-MM-JJ) du rapport de départ (défaut : celui qui précède --after)")
    comp.add_argument("--after", dest="apres", help="date (AAAA-MM-JJ) du rapport d'arrivée (défaut : le plus récent)")
    add_language_option(comp)
    conf = commands.add_parser("config", help="réglages de flux.yaml")
    conf_commands = conf.add_subparsers(dest="config_command", required=True)
    migrate = conf_commands.add_parser("migrate", help="réécrit Flux-Lab/flux.yaml avec les noms anglais (à lancer par "
                                                       "l'utilisateur, jamais par Claude Code)")
    migrate.add_argument("--dry-run", action="store_true", help="dit ce qui changerait, sans rien écrire")
    add_language_option(migrate)
    args = parser.parse_args(cfg.refuse_old_options(sys.argv[1:] if argv is None else argv, OPTIONS_RENOMMEES))
    if args.command in ("statuses", "compute") and args.source == "csv" and not args.export:
        parser.error("the following arguments are required: export")
    {"statuses": cmd_statuts, "compute": cmd_calcul, "compare": cmd_comparer, "config": cmd_config}[args.command](args)


if __name__ == "__main__":
    main()
