# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "requests"]
# ///
"""
PMZilla Lab : export des tickets par l'API Jira, au format CSV de l'export Jira « visible fields ».

C'est la source des CSV : flux_jira.py, dependencies_jira.py et flow_import.py lisent le CSV écrit ici.

    uv run tools/export_jira_api.py diagnose
        Interroge une page de la requête jql_export et dit ce que l'API renvoie pour le champ d'équipe : la forme des
        valeurs (texte, liste, objet et noms de ses clés), jamais une valeur. À lancer d'abord, une fois.

    uv run tools/export_jira_api.py fields --search <texte>
        Appelle GET /rest/api/3/field et affiche seulement l'identifiant et le nom des champs dont le nom contient le
        texte (sans tenir compte de la casse) : de quoi retrouver le customfield_NNNNN de « [G] Team/s » pour le
        réglage export_team_field. Aucune valeur de champ, aucun ticket n'est lu.

    uv run tools/export_jira_api.py export [--output <fichier.csv>] [--strict-teams]
        Exécute la requête JQL du réglage jql_export (Flux-Lab/flux.yaml), pagination complète (nextPageToken), et écrit
        un CSV (par défaut Flux-Lab/exports/api-AAAA-MM-JJ.csv, permissions 600) : Issue key, Issue Type, Status,
        Status Category, Created, Resolved, Resolution, Status Category Changed, Parent key, Updated (toujours écrite :
        l'import en base, outil flow_import.py, l'exige), une colonne « Story Points » si le réglage export_points_field
        est donné, une colonne d'équipe par équipe du ticket (en-tête répété), une colonne « Verification Required » si le réglage
        export_verification_field est donné (aucun autre usage pour l'instant), une colonne « Inward/Outward issue
        link (<type>) » par lien (en-tête répété). Les dates s'écrivent au format 09/Nov/2017 08:49. Aucun titre, aucune description,
        aucune personne n'est demandé à Jira. Sortie : des nombres, jamais une clé ni un nom.
        Si le champ d'équipe ne renvoie pas un libellé (identifiant d'objet Assets, UUID), il traduit l'identifiant par les
        identifiants Jira du référentiel d'organisation (Flux-Lab/organisation.yaml, clé jira_team_ids de chaque équipe ;
        design D5). Tant que le référentiel n'a aucun identifiant, l'ancienne table Flux-Lab/equipes-assets.yaml, écrite à la
        main (clé « equipes » : identifiant -> libellé), est lue à la place avec l'avertissement de dépréciation ; dès qu'un
        identifiant est dans le référentiel, la table est ignorée avec le même avertissement (à supprimer). Un identifiant
        absent de la source s'écrit « (équipe inconnue) », leur nombre, celui des tickets touchés et leurs identifiants
        (jamais un libellé) s'affichent, triés. Les clés « conflits » et « appuis » des anciennes tables sont ignorées. Sans
        référentiel ni table, rien n'est écrit : le script s'arrête et donne la structure du référentiel à remplir (diagnose
        montre la forme du champ). Un référentiel ou une table illisible arrête l'export. Le nombre d'équipes du référentiel
        sans ticket dans l'export s'affiche (jamais un nom). L'API Assets n'est jamais appelée. Un ticket à plusieurs
        équipes a une colonne d'équipe par équipe.
        Étiquettes et versions (jira-flow-labels) : avec le bloc declared_labels des réglages, le champ labels est demandé et
        seules les étiquettes déclarées s'écrivent, dans des colonnes « Declared Label » répétées ; les versions correctives
        (fixVersions, toujours demandées) s'écrivent dans des colonnes « Fix Version » répétées. Ces colonnes viennent après
        « Verification Required » et avant les colonnes de liens ; l'en-tête simple « Labels » et toute colonne de personne
        ne sont jamais écrits. Les étiquettes non déclarées sont comptées puis jetées : le nombre de celles qui commencent par un
        préfixe déclaré et celui des éléments d'up-merge aux deux étiquettes s'affichent, jamais une étiquette ni une version.
        Conservation (retention.period_days, un an au plus, refusé au-delà avant tout appel) : un ticket résolu depuis plus
        longtemps n'est pas écrit, le nombre s'affiche.
        --strict-teams (suivi mensuel en une commande) : quand au moins un identifiant d'équipe manque dans la source de
        traduction (référentiel, ou table en repli), le fichier est écrit et les lignes habituelles s'affichent, puis la phrase
        « identifiants d'équipe inconnus : export incomplet » et la sortie avec le code 3 (sans l'option, le code reste 0).

Les sous-commandes teams-table et compare (qui reposaient sur l'export manuel CSV) sont retirées : les lancer affiche
la voie à suivre. Flux-Lab/equipes-assets.yaml se complète à la main ; la comparaison base contre CSV est dans
flow_compare.py.

Réglages (Flux-Lab/flux.yaml), en plus de jira_site, jira_email et jira_token_type :
    jql_export          requête JQL de l'export (obligatoire pour diagnose et export, sauf si jql_exports existe)
    jql_exports         requêtes nommées (nom: requête JQL) ; `export` écrit un fichier par requête
                        (api-NOM-AAAA-MM-JJ.csv), `export --query NOM` une seule ; prime sur jql_export
    export_team_field identifiant du champ « [G] Team/s » (customfield_NNNNN) ; absent : export sans colonne d'équipe
    export_team_header  en-tête des colonnes d'équipe écrites (par défaut « Team »)
    export_verification_field identifiant du champ « Verification Required » (customfield_NNNNN, à retrouver avec
                        `fields --search "Verification Required"`) ; absent : export sans cette colonne
    export_verification_header en-tête de cette colonne (par défaut « Verification Required »)
    export_points_field identifiant du champ des story points (customfield_NNNNN, à retrouver avec
                        `fields --search "Story point"`), ou liste d'identifiants (la colonne prend la première valeur
                        non vide, dans l'ordre de la liste ; pour chaque identifiant, `export` affiche le nombre de
                        tickets où il est rempli et celui où un autre est rempli avec une valeur différente, jamais une
                        valeur) ; absent : export sans colonne « Story Points ». Valeur écrite
                        telle que renvoyée (entier ou décimal) ; vide si absente ; une valeur non numérique s'écrit vide
                        et est comptée, jamais affichée
    export_timezone       fuseau des dates du CSV (par défaut Europe/Paris, comme l'export manuel)

Les accès à Jira, le jeton (Trousseau macOS, jamais affiché) et les reprises viennent de history_jira.py, que ce
script importe : un seul code d'accès à Jira. Ce script est séparé de history_jira.py parce qu'il lit d'autres
champs (état courant, dates, parent, liens, équipe) que le seul historique des états de cette collecte.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
import sys
import time
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flux_config
import flow_organisation
from yaml_strict import charger
import history_jira as hj
from export_jira_api_messages import CATALOGS
from messages import Messages, add_language_option

OPTIONS_RENOMMEES = {**flux_config.OPTIONS_COMMUNES, "--cherche": "--search", "--requete": "--query"}

PAGE = 100
MOIS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
CHAMPS_DE_BASE = ["issuetype", "status", "created", "resolutiondate", "resolution", "statuscategorychangedate",
                  "parent", "issuelinks", "updated", "fixVersions"]     # fixVersions : lu à chaque export (jira-flow-labels)
CHAMP_ETIQUETTES = "labels"          # demandé seulement si des étiquettes déclarées sont réglées
ENTETE_ETIQUETTE = "Declared Label"      # en-têtes anglais dans les deux langues (design D19)
ENTETE_VERSION = "Fix Version"
ENTETES_DE_BASE = ["Issue key", "Issue Type", "Status", "Status Category", "Created", "Resolved", "Resolution",
                   "Status Category Changed", "Parent key", "Updated"]
ENTETE_POINTS = "Story Points"
CLES_LIBELLE = ("name", "value", "label", "displayName", "title")
IDENTIFIANT = re.compile(r"\d+|[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}")

EQUIPE_INCONNUE = "(équipe inconnue)"      # écrit dans le CSV : format de données, identique dans les deux langues
NOM_TABLE = "equipes-assets.yaml"
NOM_REFERENTIEL = "organisation.yaml"
RETIREES = {"teams-table": "retired_teams_table", "compare": "retired_compare"}     # sous-commandes retirées -> message

_MESSAGES = Messages(CATALOGS, "fr")


def set_language(language: str) -> None:
    """Langue des messages et des sorties (français par défaut), pour ce script et pour history_jira.py qu'il importe."""
    global _MESSAGES
    _MESSAGES = Messages(CATALOGS, language)
    hj.set_language(language)


def t(key: str, **values) -> str:
    return _MESSAGES(key, **values)


class Arret(Exception):
    """Arrêt volontaire avec un message sûr à afficher (aucune donnée de Jira)."""


# ---------------------------------------------------------------------------
# Champ d'équipe : on n'accepte qu'un libellé
# ---------------------------------------------------------------------------

def libelles(valeur) -> list[str] | None:
    """Libellés d'équipe d'une valeur de champ, ou None si la valeur n'est pas un libellé (identifiant seul,
    objet sans clé de libellé). Les formes acceptées : texte, objet à clé name/value/label/displayName/title, liste."""
    if valeur is None or valeur == "" or valeur == []:
        return []
    if isinstance(valeur, str):
        texte = valeur.strip()
        return None if IDENTIFIANT.fullmatch(texte) else [texte]
    if isinstance(valeur, dict):
        for cle in CLES_LIBELLE:
            if isinstance(valeur.get(cle), str) and valeur[cle].strip():
                return libelles(valeur[cle])
        return None
    if isinstance(valeur, list):
        sortie: list[str] = []
        for element in valeur:
            partie = libelles(element)
            if partie is None:
                return None
            sortie += partie
        return sortie
    return None


def identifiants(valeur) -> list[str] | None:
    """Identifiants d'objet d'une valeur de champ (objets Assets : objectId, à défaut id), ou None si la valeur n'en
    porte pas. Un texte ou un nombre est pris tel quel."""
    if valeur is None or valeur == "" or valeur == []:
        return []
    if isinstance(valeur, bool):
        return None
    if isinstance(valeur, (str, int)):
        return [str(valeur).strip()] if str(valeur).strip() else []
    if isinstance(valeur, dict):
        for cle in ("objectId", "id"):
            v = valeur.get(cle)
            if isinstance(v, (str, int)) and not isinstance(v, bool) and str(v).strip():
                return [str(v).strip()]
        return None
    if isinstance(valeur, list):
        sortie: list[str] = []
        for element in valeur:
            partie = identifiants(element)
            if partie is None:
                return None
            sortie += partie
        return sortie
    return None


def charger_table() -> dict[str, str] | None:
    """Table identifiant -> libellé (Flux-Lab/equipes-assets.yaml, clé « equipes »), None si le fichier n'existe pas."""
    chemin = hj.FLUX_DIR / NOM_TABLE
    if not chemin.exists():
        return None
    try:
        donnees = charger(chemin.read_text(encoding="utf-8"), chemin.name) or {}
    except (OSError, hj.yaml.YAMLError):
        raise Arret(t("table_unreadable", table=NOM_TABLE)) from None
    table = donnees.get("equipes") if isinstance(donnees, dict) else None
    return {str(k): str(v) for k, v in (table or {}).items()}


@dataclass
class Traduction:
    """Source de traduction des identifiants d'équipe (design D4, D5) : `correspondance` identifiant -> nom (None sans
    source), `source` « referentiel » ou « table » (None sans source), le référentiel lu (None s'il n'existe pas) et la
    présence du fichier de l'ancienne table (à supprimer quand le référentiel porte des identifiants)."""
    correspondance: dict[str, str] | None
    source: str | None
    referentiel: flow_organisation.Referentiel | None
    table_presente: bool


def resoudre_traduction() -> Traduction:
    """Source de traduction : les identifiants Jira du référentiel d'organisation s'il en porte au moins un (l'ancienne table
    est alors ignorée, sans être lue) ; sinon l'ancienne table ; sinon aucune. Un référentiel ou une table illisible arrête
    (`ErreurConfig` ou `Arret`, sans valeur)."""
    referentiel = flow_organisation.charger_si_present(hj.FLUX_DIR / NOM_REFERENTIEL)
    table_presente = (hj.FLUX_DIR / NOM_TABLE).exists()
    if referentiel is not None and referentiel.has_jira_ids:
        correspondance = {i: e.nom for e in referentiel.teams.values() for i in e.jira_ids}
        return Traduction(correspondance, "referentiel", referentiel, table_presente)
    table = charger_table()
    return Traduction(table, "table" if table is not None else None, referentiel, table is not None)


def forme(valeur) -> str:
    """Forme d'une valeur, jamais son contenu : type, et noms des clés d'un objet."""
    if valeur is None:
        return t("form_empty")
    if isinstance(valeur, str):
        return t("form_text_id") if IDENTIFIANT.fullmatch(valeur.strip()) else t("form_text")
    if isinstance(valeur, dict):
        return t("form_object", keys=", ".join(sorted(str(k) for k in valeur)))
    if isinstance(valeur, list):
        return t("form_empty_list") if not valeur else t("form_list_of", forms=" / ".join(sorted({forme(v) for v in valeur})))
    return type(valeur).__name__


def analyser_equipes(tickets: list[dict], champ: str) -> tuple[Counter, bool]:
    """(effectifs par forme de valeur, tous les libellés sont exploitables)."""
    formes, exploitable = Counter(), True
    for ticket in tickets:
        valeur = (ticket.get("fields") or {}).get(champ)
        formes[forme(valeur)] += 1
        if libelles(valeur) is None:
            exploitable = False
    return formes, exploitable


# ---------------------------------------------------------------------------
# Requête
# ---------------------------------------------------------------------------

def requetes_export(settings: dict) -> list[tuple[str | None, str]]:
    """Requêtes de l'export : celles de jql_exports (nom -> JQL, dans l'ordre du fichier), sinon jql_export (sans nom)."""
    nommees = settings.get("jql_exports")
    if nommees:
        if not isinstance(nommees, dict):
            raise Arret(t("jql_exports_not_dict"))
        requetes = []
        for nom, jql in nommees.items():
            nom, jql = str(nom).strip(), str(jql or "").strip()
            if not re.fullmatch(r"[A-Za-z0-9_-]+", nom):
                raise Arret(t("jql_name_invalid"))
            if not jql:
                raise Arret(t("jql_empty", name=nom))
            requetes.append((nom, jql))
        return requetes
    jql = str(settings.get("jql_export") or "").strip()
    if not jql:
        raise Arret(t("jql_missing", file=hj.CONFIG_FILE))
    return [(None, jql)]


def reglages_export() -> tuple[dict, list[tuple[str | None, str]], str | None, str]:
    settings = hj.reglages()
    requetes = requetes_export(settings)
    champ = str(settings.get("export_champ_equipe") or "").strip() or None
    if champ and not re.fullmatch(r"[A-Za-z0-9_]+", champ):
        raise Arret(t("team_field_invalid"))
    return settings, requetes, champ, str(settings.get("export_entete_equipe") or "Team")


def reglage_verification(settings: dict) -> tuple[str | None, str]:
    """(identifiant du champ « Verification Required », en-tête de la colonne). Sans identifiant : pas de colonne."""
    champ = str(settings.get("export_champ_verification") or "").strip() or None
    if champ and not re.fullmatch(r"[A-Za-z0-9_]+", champ):
        raise Arret(t("verification_field_invalid"))
    return champ, str(settings.get("export_entete_verification") or "Verification Required")


def reglage_points(settings: dict) -> list[str]:
    """Identifiants du champ des story points (export_points_field : un identifiant, ou une liste dans l'ordre de préférence).
    Sans identifiant : liste vide, pas de colonne. Un doublon est ignoré."""
    brut = settings.get("export_points_field")
    valeurs = brut if isinstance(brut, (list, tuple)) else [brut]
    champs: list[str] = []
    for valeur in valeurs:
        champ = str(valeur or "").strip()
        if not champ:
            continue
        if not re.fullmatch(r"[A-Za-z0-9_]+", champ):
            raise Arret(t("points_field_invalid"))
        if champ not in champs:
            champs.append(champ)
    return champs


def texte_points(valeur) -> tuple[str, bool]:
    """(texte de la cellule, valeur non numérique). Un nombre s'écrit tel que renvoyé ; absent ou null : cellule vide ;
    toute autre forme (texte, booléen, objet) : cellule vide, signalée, sans jamais afficher la valeur."""
    if valeur is None:
        return "", False
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
        return str(valeur), False
    return "", True


def texte_verification(valeur) -> str:
    """Texte d'une valeur du champ : booléen (« true » ou « false »), nombre, texte, ou libellé(s) d'un objet ou d'une
    liste séparés par « ; ». Une forme sans libellé s'écrit vide : aucune valeur inventée, aucune valeur affichée."""
    if valeur is None:
        return ""
    if isinstance(valeur, bool):
        return "true" if valeur else "false"
    if isinstance(valeur, (int, float)):
        return str(valeur)
    if isinstance(valeur, str):
        return valeur.strip()
    return "; ".join(libelles(valeur) or [])


def interroger(client, jql: str, champs: list[str], une_page: bool = False) -> tuple[list[dict], int]:
    """Tickets de la requête, toutes les pages (nextPageToken). Retourne les tickets (sans doublon) et le nombre de pages."""
    tickets, vus, pages, jeton = [], set(), 0, None
    while True:
        corps = {"jql": jql, "fields": champs, "maxResults": PAGE}
        if jeton:
            corps["nextPageToken"] = jeton
        reponse = client.json("POST", "/rest/api/3/search/jql", json=corps)
        pages += 1
        for ticket in reponse.get("issues") or []:
            cle = str(ticket.get("key") or "").upper()
            if cle and cle not in vus:
                vus.add(cle)
                tickets.append(ticket)
        suivant = reponse.get("nextPageToken")
        if une_page or not suivant or suivant == jeton:
            return tickets, pages
        jeton = suivant
        time.sleep(hj.PAUSE)


# ---------------------------------------------------------------------------
# Écriture du CSV
# ---------------------------------------------------------------------------

FUSEAU_PAR_DEFAUT = "Europe/Paris"


def fuseau_export(settings: dict) -> ZoneInfo:
    """Fuseau des dates du CSV (réglage export_timezone, Europe/Paris par défaut), comme l'export manuel."""
    nom = str(settings.get("export_fuseau") or FUSEAU_PAR_DEFAUT).strip()
    try:
        return ZoneInfo(nom)
    except (ZoneInfoNotFoundError, ValueError):
        raise Arret(t("timezone_invalid", name=nom, example=FUSEAU_PAR_DEFAUT))


def date_csv(valeur, fuseau: dt.tzinfo | None = None) -> str:
    """Date ISO de l'API (2017-11-09T08:49:00.000+0100) au format de l'export manuel (09/Nov/2017 08:49), mois en
    anglais sans dépendre de la langue du poste. Avec un fuseau, l'heure est convertie dans ce fuseau ; sans, elle
    garde le décalage d'origine."""
    if not valeur:
        return ""
    try:
        d = dt.datetime.fromisoformat(str(valeur))
    except ValueError:
        return ""
    if fuseau is not None and d.tzinfo is not None:
        d = d.astimezone(fuseau)
    return f"{d.day:02d}/{MOIS[d.month - 1]}/{d.year} {d.hour:02d}:{d.minute:02d}"


def liens_de(ticket: dict) -> dict[tuple[str, str], list[str]]:
    """Clés liées, par (sens, type de lien). Le sens est celui de l'export manuel : un lien « outwardIssue » est
    « Outward issue link » (ce ticket bloque l'autre), « inwardIssue » est « Inward issue link »."""
    sortie: dict[tuple[str, str], list[str]] = {}
    for lien in (ticket.get("fields") or {}).get("issuelinks") or []:
        type_ = str((lien.get("type") or {}).get("name") or "").strip()
        for sens, cle_api in (("Outward", "outwardIssue"), ("Inward", "inwardIssue")):
            autre = (lien.get(cle_api) or {}).get("key")
            if autre and type_:
                sortie.setdefault((sens, type_), []).append(str(autre))
    return sortie


def etiquettes_du_ticket(champs_ticket: dict) -> list[str]:
    """Étiquettes du champ labels (texte non vide), sans doublon, dans l'ordre de l'API."""
    valeurs = champs_ticket.get(CHAMP_ETIQUETTES) or []
    return list(dict.fromkeys(e.strip() for e in valeurs if isinstance(e, str) and e.strip()))


def versions_du_ticket(champs_ticket: dict) -> list[str]:
    """Noms des versions correctives du ticket, sans doublon, dans l'ordre de l'API."""
    noms = [(v or {}).get("name") for v in champs_ticket.get("fixVersions") or [] if isinstance(v, dict)]
    return list(dict.fromkeys(n.strip() for n in noms if isinstance(n, str) and n.strip()))


def construire_csv(tickets: list[dict], champ_equipe: str | None, entete_equipe: str,
                   table: dict[str, str] | None = None, fuseau: dt.tzinfo | None = None,
                   champ_verification: str | None = None,
                   entete_verification: str = "Verification Required",
                   champ_points: str | list[str] | None = None,
                   etiquettes: dict | None = None) -> tuple[list[list[str]], dict]:
    """Lignes du CSV (en-têtes comprises) et quelques effectifs. Un libellé est écrit tel quel ; un identifiant d'objet se
    traduit par `table` (identifiant -> nom ; absent : « (équipe inconnue) », compté). Lève Arret si le champ d'équipe n'est
    ni un libellé ni un identifiant traduisible. `etiquettes` (rôle -> {prefix, labels}, lecteur declared_labels) : seules les
    étiquettes déclarées s'écrivent, dans des colonnes « Declared Label » ; les autres sont comptées puis jetées. Les versions
    correctives s'écrivent dans des colonnes « Fix Version ». Les deux familles viennent après la colonne de vérification."""
    equipes = {}
    inconnus: Counter = Counter()
    tickets_inconnus: set[str] = set()
    traduits = False
    if champ_equipe:
        for ticket in tickets:
            valeur = (ticket.get("fields") or {}).get(champ_equipe)
            noms = libelles(valeur)
            if noms is None:
                ids = identifiants(valeur) if table is not None else None
                if ids is None:
                    formes, _ = analyser_equipes(tickets, champ_equipe)
                    raise Arret(t("team_label_options", form=", ".join(t("form_count", form=f, count=n) for f, n in sorted(formes.items()))))
                traduits = traduits or bool(ids)
                noms = []
                for identifiant in dict.fromkeys(ids):
                    if identifiant in table:
                        noms.append(table[identifiant])
                    else:
                        noms.append(EQUIPE_INCONNUE)
                        inconnus[identifiant] += 1
                        tickets_inconnus.add(str(ticket["key"]))
            equipes[str(ticket["key"])] = noms
    nb_equipes = max([1] + [len(v) for v in equipes.values()]) if champ_equipe else 0
    colonnes_liens: Counter = Counter()          # (sens, type) -> nombre maximal de liens d'un ticket
    liens = {}
    for ticket in tickets:
        liens[str(ticket["key"])] = liens_de(ticket)
        for cle, valeurs in liens[str(ticket["key"])].items():
            colonnes_liens[cle] = max(colonnes_liens[cle], len(valeurs))
    ordre_liens = sorted(colonnes_liens)
    # étiquettes : déclarées gardées par ticket, non déclarées comptées puis oubliées (jamais gardées ni affichées)
    declarees = {e for contenu in (etiquettes or {}).values() for e in contenu["labels"]}
    prefixes = tuple(contenu["prefix"] for contenu in (etiquettes or {}).values())
    up_merge = set((etiquettes or {}).get("up_merge", {}).get("labels", ()))
    gardees: dict[str, list[str]] = {}
    proches: set[str] = set()
    tickets_proches = deux_up_merge = 0
    for ticket in tickets:
        brutes = etiquettes_du_ticket(ticket.get("fields") or {}) if etiquettes else []
        gardees[str(ticket["key"])] = [e for e in brutes if e in declarees]
        voisines = {e for e in brutes if e not in declarees and e.startswith(prefixes)}
        proches |= voisines
        tickets_proches += bool(voisines)
        deux_up_merge += len(up_merge) == 2 and up_merge <= set(brutes)
    versions = {str(ticket["key"]): versions_du_ticket(ticket.get("fields") or {}) for ticket in tickets}
    nb_etiquettes = max([0] + [len(v) for v in gardees.values()])
    nb_versions = max([0] + [len(v) for v in versions.values()])
    champs_points = [champ_points] if isinstance(champ_points, str) else list(champ_points or [])
    par_champ = {c: [0, 0] for c in champs_points}          # champ -> [tickets renseignés, tickets en désaccord avec un autre champ]
    entetes = (list(ENTETES_DE_BASE) + ([ENTETE_POINTS] if champs_points else []) + [entete_equipe] * nb_equipes
               + ([entete_verification] if champ_verification else [])
               + [ENTETE_ETIQUETTE] * nb_etiquettes + [ENTETE_VERSION] * nb_versions)
    verification_renseignes = points_renseignes = points_invalides = 0
    for sens, type_ in ordre_liens:
        entetes += [f"{sens} issue link ({type_})"] * colonnes_liens[(sens, type_)]
    lignes = [entetes]
    for ticket in tickets:
        cle, champs = str(ticket["key"]), ticket.get("fields") or {}
        statut = champs.get("status") or {}
        ligne = [cle, (champs.get("issuetype") or {}).get("name") or "", statut.get("name") or "",
                 (statut.get("statusCategory") or {}).get("name") or "", date_csv(champs.get("created"), fuseau),
                 date_csv(champs.get("resolutiondate"), fuseau), (champs.get("resolution") or {}).get("name") or "",
                 date_csv(champs.get("statuscategorychangedate"), fuseau), (champs.get("parent") or {}).get("key") or "",
                 date_csv(champs.get("updated"), fuseau)]
        if champs_points:
            lus = [texte_points(champs.get(c)) for c in champs_points]
            points_invalides += sum(invalide for _, invalide in lus)
            remplis = {c: texte for c, (texte, _) in zip(champs_points, lus) if texte}
            for c in remplis:
                par_champ[c][0] += 1
                if any(float(v) != float(remplis[c]) for autre, v in remplis.items() if autre != c):
                    par_champ[c][1] += 1
            texte = next(iter(remplis.values()), "")           # première valeur non vide, dans l'ordre de la liste
            points_renseignes += bool(texte)
            ligne.append(texte)
        noms = equipes.get(cle, [])
        ligne += noms + [""] * (nb_equipes - len(noms))
        if champ_verification:
            texte = texte_verification(champs.get(champ_verification))
            verification_renseignes += bool(texte)
            ligne.append(texte)
        ligne += gardees[cle] + [""] * (nb_etiquettes - len(gardees[cle]))
        ligne += versions[cle] + [""] * (nb_versions - len(versions[cle]))
        for sens, type_ in ordre_liens:
            valeurs = liens[cle].get((sens, type_), [])
            ligne += valeurs + [""] * (colonnes_liens[(sens, type_)] - len(valeurs))
        lignes.append(ligne)
    vues = {nom for noms in equipes.values() for nom in noms if nom != EQUIPE_INCONNUE}
    return lignes, {"inconnus_distincts": len(inconnus), "inconnus_ids": sorted(inconnus), "inconnus_tickets": len(tickets_inconnus),
                    "table_utilisee": table is not None, "traduction_utilisee": traduits, "equipes_vues": vues,
                    "colonnes_equipe": nb_equipes, "types_de_liens": len({t for _, t in ordre_liens}),
                    "colonnes_de_liens": sum(colonnes_liens.values()), "colonnes": len(entetes),
                    "proches_distinctes": len(proches), "proches_tickets": tickets_proches, "deux_up_merge": deux_up_merge,
                    "verification_renseignes": verification_renseignes if champ_verification else None,
                    "points_renseignes": points_renseignes if champs_points else None,
                    "points_par_champ": par_champ,
                    "points_invalides": points_invalides}


def ecarter_hors_conservation(tickets: list[dict], jours: int, aujourdhui: dt.date,
                              fuseau: dt.tzinfo | None = None) -> tuple[list[dict], int]:
    """(tickets à écrire, nombre de tickets écartés). Un ticket résolu depuis plus de `jours` jours est écarté (design D1) ;
    un ticket sans date de résolution, ou à date illisible, est gardé. Jamais de clé en retour."""
    limite = aujourdhui - dt.timedelta(days=jours)
    gardes = []
    for ticket in tickets:
        brute = (ticket.get("fields") or {}).get("resolutiondate")
        try:
            resolu = dt.datetime.fromisoformat(str(brute)) if brute else None
        except ValueError:
            resolu = None
        if resolu is not None and fuseau is not None and resolu.tzinfo is not None:
            resolu = resolu.astimezone(fuseau)
        if resolu is not None and resolu.date() < limite:
            continue
        gardes.append(ticket)
    return gardes, len(tickets) - len(gardes)


def ecrire_csv(chemin: Path, lignes: list[list[str]]) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_suffix(".tmp")
    with temporaire.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(lignes)
    os.chmod(temporaire, 0o600)
    os.replace(temporaire, chemin)


# ---------------------------------------------------------------------------
# Commandes
# ---------------------------------------------------------------------------

def cmd_diagnose(args: argparse.Namespace) -> None:
    settings, requetes, champ, _ = reglages_export()
    jql = requetes[0][1]          # la première requête suffit à voir la forme du champ
    if not champ:
        raise Arret(t("diagnose_no_field"))
    client = hj.construire_client(settings)
    tickets, _ = interroger(client, jql, [champ], une_page=True)
    hj.afficher(t("diagnose_page", count=len(tickets)))
    if not tickets:
        raise Arret(t("diagnose_no_ticket"))
    if not any(champ in (t.get("fields") or {}) for t in tickets):
        raise Arret(t("diagnose_field_absent"))
    formes, exploitable = analyser_equipes(tickets, champ)
    hj.afficher(t("diagnose_forms", forms=t("list_separator").join(f"{f} {n}" for f, n in sorted(formes.items()))))
    if exploitable:
        hj.afficher(t("diagnose_labels_yes"))
    elif (traduction := resoudre_traduction()).correspondance is not None and all(
            identifiants((t.get("fields") or {}).get(champ)) is not None for t in tickets):
        if traduction.source == "referentiel":      # source et effectif seulement : ni identifiant ni nom
            hj.afficher(t("diagnose_labels_referential", count=len(traduction.correspondance)))
        else:
            hj.afficher(t("diagnose_labels_table", table=NOM_TABLE, count=len(traduction.correspondance)))
        if traduction.table_presente:
            hj.afficher(t("table_deprecated"))
    else:
        hj.afficher(t("diagnose_labels_no"))
        hj.afficher(t("team_label_options", form=", ".join(sorted(formes))))
        sys.exit(1)


def cmd_champs(args: argparse.Namespace) -> None:
    """Identifiant et nom des champs dont le nom contient le texte cherché. Rien d'autre n'est affiché ni gardé."""
    cherche = args.cherche.strip().casefold()
    if not cherche:
        raise Arret(t("fields_search_empty"))
    client = hj.construire_client(hj.reglages())
    champs = client.json("GET", "/rest/api/3/field")
    if not isinstance(champs, list):
        raise Arret(t("fields_unexpected"))
    trouves = sorted(((str(c.get("id") or ""), str(c.get("name") or "")) for c in champs
                      if isinstance(c, dict) and cherche in str(c.get("name") or "").casefold()),
                     key=lambda c: (c[1].casefold(), c[0]))
    hj.afficher(t("fields_count", count=len(trouves), total=len(champs)))
    for identifiant, nom in trouves:
        hj.afficher(f"  {identifiant}  {nom}")


def choisir_requetes(requetes: list[tuple[str | None, str]], nom: str | None) -> list[tuple[str | None, str]]:
    """Toutes les requêtes, ou seulement celle de `--query`. Nom inconnu : arrêt avec les noms disponibles."""
    if nom is None:
        return requetes
    noms = [n for n, _ in requetes if n]
    if not noms:
        raise Arret(t("query_needs_named"))
    choisies = [r for r in requetes if r[0] == nom]
    if not choisies:
        raise Arret(t("query_unknown", name=nom, names=", ".join(noms)))
    return choisies


def nom_fichier_export(nom: str | None, jour: str) -> str:
    """Nom du CSV écrit par défaut : api-[NOM-]AAAA-MM-JJ.csv (tools/flow_monthly.py construit les mêmes chemins, un test les épingle)."""
    return f"api-{nom + '-' if nom else ''}{jour}.csv"


def cmd_export(args: argparse.Namespace) -> None:
    settings, requetes, champ, entete = reglages_export()
    fuseau = fuseau_export(settings)       # réglage invalide : arrêt avant tout appel à Jira
    champ_verification, entete_verification = reglage_verification(settings)
    champ_points = reglage_points(settings)
    jours_conservation = flux_config.retention_days(settings)       # au-delà d'un an : refus avant tout appel
    etiquettes = flux_config.declared_labels(settings)
    requetes = choisir_requetes(requetes, args.requete)
    if args.sortie and len(requetes) > 1:
        raise Arret(t("output_single_query"))
    traduction = resoudre_traduction() if champ else Traduction(None, None, None, False)      # illisible : arrêt avant Jira
    client = hj.construire_client(settings)
    equipes_inconnues = avertie = False
    equipes_vues: set[str] = set()
    for nom, jql in requetes:
        etiquette = f"[{nom}] " if nom else ""
        tickets, pages = interroger(client, jql, CHAMPS_DE_BASE + ([champ] if champ else [])
                                    + ([CHAMP_ETIQUETTES] if etiquettes else [])
                                    + ([champ_verification] if champ_verification else [])
                                    + champ_points)
        tickets, hors_conservation = ecarter_hors_conservation(tickets, jours_conservation, hj.aujourd_hui(), fuseau)
        lignes, effectifs = construire_csv(tickets, champ, entete, traduction.correspondance, fuseau, champ_verification,
                                           entete_verification, champ_points, etiquettes)
        equipes_vues |= effectifs["equipes_vues"]
        fichier = nom_fichier_export(nom, dt.date.today().isoformat())
        sortie = Path(args.sortie).expanduser() if args.sortie else hj.FLUX_DIR / "exports" / fichier
        ecrire_csv(sortie, lignes)
        hj.afficher(t("export_summary", label=etiquette, tickets=len(tickets), pages=pages, columns=effectifs["colonnes"],
                      team_columns=effectifs["colonnes_equipe"], link_columns=effectifs["colonnes_de_liens"],
                      link_types=effectifs["types_de_liens"]))
        if hors_conservation:
            hj.afficher(t("export_past_retention", label=etiquette, count=hors_conservation))
        if not champ:
            hj.afficher(t("export_no_team_column", label=etiquette))
        if effectifs["verification_renseignes"] is not None:
            hj.afficher(t("export_verification", label=etiquette, header=entete_verification,
                          filled=effectifs["verification_renseignes"], total=len(tickets)))
        if effectifs["points_renseignes"] is not None:
            hj.afficher(t("export_points", label=etiquette, header=ENTETE_POINTS,
                          filled=effectifs["points_renseignes"], total=len(tickets)))
            for identifiant, (remplis, desaccords) in effectifs["points_par_champ"].items():
                hj.afficher(t("export_points_field", label=etiquette, field=identifiant, filled=remplis, total=len(tickets),
                              conflicts=desaccords))
            if effectifs["points_invalides"]:
                hj.afficher(t("export_points_invalid", label=etiquette, count=effectifs["points_invalides"]))
        if effectifs["proches_distinctes"]:        # nombres seulement : jamais une étiquette
            hj.afficher(t("export_lookalike_labels", label=etiquette, count=effectifs["proches_distinctes"]))
            hj.afficher(t("export_lookalike_tickets", label=etiquette, tickets=effectifs["proches_tickets"]))
        if effectifs["deux_up_merge"]:
            hj.afficher(t("export_two_up_merge", label=etiquette, count=effectifs["deux_up_merge"]))
        if effectifs["traduction_utilisee"] and traduction.table_presente and not avertie:
            avertie = True
            hj.afficher(t("table_deprecated"))      # table lue en repli, ou ignorée parce que le référentiel porte des identifiants
        if effectifs["inconnus_tickets"]:
            equipes_inconnues = True
            ref = traduction.source == "referentiel"
            hj.afficher(t("export_unknown_teams_referential" if ref else "export_unknown_teams", label=etiquette,
                          identifiers=effectifs["inconnus_distincts"], tickets=effectifs["inconnus_tickets"],
                          unknown=EQUIPE_INCONNUE, table=NOM_TABLE))
            hj.afficher(t("export_unknown_ids_referential" if ref else "export_unknown_ids", label=etiquette, table=NOM_TABLE,
                          ids=t("list_separator").join(effectifs["inconnus_ids"])))
        hj.afficher(t("export_written", label=etiquette, name=sortie.name))
    if traduction.referentiel is not None:        # contrôle du référentiel : un nombre, jamais un nom (design D17)
        sans_ticket = sum(1 for nom in traduction.referentiel.teams if nom not in equipes_vues)
        if sans_ticket:
            hj.afficher(t("export_referential_idle", count=sans_ticket))
    if args.strict_equipes and equipes_inconnues:        # option stricte (orchestrateur du suivi mensuel) : le fichier est écrit, le mois est incomplet
        hj.afficher(t("export_strict_teams"))
        sys.exit(3)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Export des tickets Jira par l'API, au format CSV de l'export Jira (teams-table et compare sont retirées)")
    commandes = parser.add_subparsers(dest="commande", required=True, metavar="{diagnose,fields,export}")
    commandes.add_parser("diagnose", help="forme des valeurs du champ d'équipe (jamais les valeurs)")
    champs = commandes.add_parser("fields", help="identifiant et nom des champs dont le nom contient un texte")
    champs.add_argument("--search", dest="cherche", required=True, metavar="TEXTE", help="texte cherché dans le nom des champs (sans casse)")
    export = commandes.add_parser("export", help="écrit un CSV par requête (jql_exports, ou jql_export)")
    export.add_argument("--query", dest="requete", metavar="NOM", help="ne lance que cette requête de jql_exports (par défaut : toutes)")
    export.add_argument("--output", dest="sortie", help="fichier CSV à écrire, avec une seule requête (par défaut "
                                         "Flux-Lab/exports/api-[NOM-]AAAA-MM-JJ.csv)")
    export.add_argument("--strict-teams", dest="strict_equipes", action="store_true",
                        help="identifiants d'équipe absents de la source de traduction : écrit le fichier puis sort avec le code 3")
    for retiree in RETIREES:        # déclarées pour répondre par la voie à suivre, cachées de l'aide
        sous = commandes.add_parser(retiree)          # sans help : absente de la liste de l'aide
        sous.add_argument("ignores", nargs="*")
    for sous_parseur in commandes.choices.values():
        add_language_option(sous_parseur)
    args, inconnus = parser.parse_known_args(flux_config.refuse_old_options(sys.argv[1:] if argv is None else argv, OPTIONS_RENOMMEES))
    set_language(args.language)
    if args.commande in RETIREES:
        hj.afficher(t("error_line", message=t(RETIREES[args.commande])))
        sys.exit(2)
    if inconnus:
        parser.error("unrecognized arguments: " + " ".join(inconnus))
    try:
        {"diagnose": cmd_diagnose, "fields": cmd_champs, "export": cmd_export}[args.commande](args)
    except SystemExit:
        raise
    except hj.ErreurHTTP as erreur:
        hj.afficher(str(erreur))
        sys.exit(1)
    except (hj.ErreurSimple, Arret) as erreur:
        hj.afficher(t("error_line", message=erreur))
        sys.exit(1)
    except Exception as erreur:       # aucun détail : un message de bibliothèque pourrait citer une adresse
        hj.afficher(t("unexpected_error", name=type(erreur).__name__))
        sys.exit(1)


if __name__ == "__main__":
    main()
