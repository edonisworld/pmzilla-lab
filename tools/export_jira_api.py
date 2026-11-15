# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "requests", "psycopg[binary]"]
# ///
"""
PMZilla Lab : export des tickets par l'API Jira, écrit directement dans la couche brute datée du schéma flow (change database-only).

Aucun fichier n'est écrit : flow_import.py dérive les tables courantes de la couche brute, et tous les lecteurs lisent la base.

    uv run tools/export_jira_api.py diagnose
        Interroge une page de la requête jql_export et dit ce que l'API renvoie pour le champ d'équipe : la forme des
        valeurs (texte, liste, objet et noms de ses clés), jamais une valeur. À lancer d'abord, une fois.

    uv run tools/export_jira_api.py fields --search <texte>
        Appelle GET /rest/api/3/field et affiche seulement l'identifiant et le nom des champs dont le nom contient le
        texte (sans tenir compte de la casse) : de quoi retrouver le customfield_NNNNN de « [G] Team/s » pour le
        réglage export_team_field. Aucune valeur de champ, aucun ticket n'est lu.

    uv run tools/export_jira_api.py fields --project <clé> --field <identifiant> [--field <identifiant> ...]
        Sur les 500 derniers tickets créés du projet (taille de l'échantillon affichée), compte combien de
        tickets ont chaque champ rempli (les champs système components, fixVersions et versions compris). Affiche seulement l'identifiant du champ, son
        nom et le compte, avec la taille de l'échantillon : jamais une valeur, jamais une clé de ticket. Lancée par l'auteur
        seulement (règles deny de la sous-commande fields).

    uv run tools/export_jira_api.py export [--query NOM] [--full] [--strict-teams]
        Exécute les requêtes JQL nommées du réglage jql_exports (ou jql_export) de Flux-Lab/flux.yaml, pagination complète
        (nextPageToken), et écrit UN passage de la couche brute (voir plus bas). Chaque passage lit en entier tous les tickets de chaque
        requête (aucune recherche sur la date de mise à jour, aucun instant d'un passage antérieur) : --full force cette lecture
        complète, qui est déjà le comportement par défaut, et ne change rien (l'option reste acceptée pour qu'un export incrémental
        puisse venir sans changer l'interface). --output est retirée (code 2) : l'export n'écrit aucun fichier. Les attributs lus :
        clé, type, état, catégorie d'état, dates de création, de résolution, de changement de catégorie et de mise à jour (instants
        du fuseau export_timezone, à la minute), résolution, clé du parent, story points si le réglage export_points_field est donné,
        équipes (dans l'ordre), liens et noms des versions courantes (fixVersions et versions) avec, pour chaque version, sa date de sortie et son drapeau de sortie
        (releaseDate, released : aucun autre attribut de version), en base seulement, jamais affichés, aucune valeur. Les
        étiquettes ne sont pas demandées (la collecte de l'historique s'en charge),
        ni la colonne de vérification (aucun lecteur ne s'en sert). Aucun titre, aucune description, aucune personne n'est demandé à
        Jira. Sortie : des nombres, jamais une clé ni un nom.
        Si le champ d'équipe ne renvoie pas un libellé (identifiant d'objet Assets, UUID), il traduit l'identifiant par le
        référentiel d'organisation (Flux-Lab/organisation.yaml, clé jira_team_ids de chaque équipe) ET le catalogue des équipes
        Jira (Flux-Lab/equipes-jira.yaml, copie complète d'Assets) lus ensemble : le nom du référentiel d'abord, sinon le
        libellé du catalogue ; un identifiant dans les deux fichiers est accepté. L'ancienne table equipes-assets.yaml n'est
        plus jamais lue : une phrase demande de la supprimer tant que le fichier existe. Les équipes hors organisation (dans
        le catalogue seulement) et les tickets sur des équipes obsolètes sont comptés à part. Un identifiant dans aucune des
        deux sources s'écrit « (équipe inconnue) » ; leur nombre, celui des tickets touchés et leurs identifiants (jamais un
        libellé) s'affichent, triés. Sans aucun identifiant dans les deux sources, rien n'est écrit : le script s'arrête et
        donne la structure des deux fichiers (diagnose montre la forme du champ). Un fichier illisible ou une entrée du
        catalogue nommée comme une équipe du référentiel avec un identifiant hors référentiel arrête l'export. Le nombre
        d'équipes du référentiel sans ticket dans l'export s'affiche (jamais un nom). L'API Assets n'est jamais appelée.
        Conservation (retention.period_days, un an au plus, refusé au-delà avant tout appel) : un ticket résolu depuis plus
        longtemps n'est ni vu ni écrit, le nombre s'affiche.
        Couche brute datée (changes jira-data-architecture et database-only) : `export` écrit, dans le schéma flow de la base et en UNE
        transaction, un passage (instant, nombre de requêtes nommées lues, toutes lues ou non), les clés des tickets lus (visites) et,
        pour un ticket nouveau ou dont le contenu a changé, un instantané de ses attributs autorisés (équipes dans l'ordre, avec leur
        identifiant d'équipe Jira quand le champ en renvoie un, y compris un identifiant dans aucune des deux sources ; liens). Jamais de
        titre, de description, de personne ni d'étiquette ; les versions courantes y sont, par genre, avec leur date de sortie et leur drapeau de
        sortie, sans jamais être affichés ni aucune valeur. Dans la même transaction, le type de chaque équipe rencontrée
        s'écrit dans flow.teams (type du catalogue, ou type effectif de l'équipe du référentiel : forcé, sinon déduit du catalogue ;
        jamais deviné ; une équipe créée si elle manque ; la colonne n'est mise à jour que si le type diffère) et la ligne « équipes
        sans type : N » (un effectif, jamais un libellé) s'affiche. Une erreur de Jira ou de la base ne laisse aucun passage. L'outil
        se connecte à la base AVANT le premier appel à Jira, sous le rôle d'import pmzilla_flow avec son propre mot de passe (Trousseau
        pmzilla-lab-db-pmzilla_flow, puis PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW ; à poser avec `db.py role-password pmzilla_flow`) : mot
        de passe absent ou base injoignable, code 1, aucun appel à Jira. `diagnose` et `fields` ne se connectent pas. Une erreur de la
        base n'affiche que son type. La ligne « couche brute : N tickets vus, M instantanés ajoutés » (des effectifs seulement) clôt les
        comptes.
        --strict-teams (suivi mensuel en une commande) : quand au moins un identifiant d'équipe est dans aucune des deux sources
        (référentiel, catalogue), les lignes habituelles s'affichent, puis la phrase « identifiants d'équipe inconnus : export
        incomplet » et la sortie avec le code 3, SANS rien écrire dans la couche brute (sans l'option, le code reste 0 et le passage
        est écrit). Une équipe du catalogue, obsolète ou non, ne rend jamais l'export incomplet.

    Client Jira en lecture seule (diagnose, fields, export ; change jira-read-only-client) : seules les lectures de la liste de
        history_jira.py sont envoyées. Une requête refusée arrête avec le code 5 et la phrase fixe en entier (écriture interdite, ou
        hors de la liste des lectures permises, ou option non permise), rien n'est enregistré. La garde du périmètre n'admet que des
        recherches limitées aux projets de scope_projects, refuse ceux de forbidden_projects, filtre les réponses (tickets hors des
        projets déclarés écartés et comptés : « tickets hors des projets déclarés écartés : N », seulement au-dessus de zéro ; liens,
        parent et sous-tâches réduits à la clé et au type) : un refus de la garde, ou un de ces deux réglages absent, vide ou illisible
        (aucun appel à Jira), arrête avec le code 6. Codes 5 et 6 : jamais un autre motif.

    uv run tools/export_jira_api.py extract-teams [--language fr|en]
        Utilisateur seul, dans le Terminal (refusé dans une session Claude Code, code 3, avant toute lecture). Aucun appel à Jira,
        aucune base. Écrit Flux-Lab/equipes-lisibles.yaml (droits 600, remplacé à chaque lancement, hors Git) depuis les lecteurs
        stricts du référentiel et du catalogue : par équipe, son nom, ses identifiants d'équipe Jira, son type, le drapeau « sans
        identifiant » (référentiel) ou « obsolète » et « hors référentiel » (catalogue), et la date. Ni effectif, ni site, ni
        département, ni Mission Team, ni commentaire. Une source refusée ou aucune source : code 1, rien n'est écrit ; une seule
        source absente : l'autre est extraite. La sortie ne montre que des nombres, jamais un nom.

    uv run tools/export_jira_api.py check-teams [--language fr|en]
        Utilisateur seul, dans le Terminal (refusé dans une session Claude Code, code 3, avant toute lecture). Aucun appel à Jira.
        Contrôle le référentiel, le catalogue, l'ancienne table (identifiants non couverts : code 4) et recoupe le référentiel avec
        la dernière liste Assets (date du nom) : jamais un libellé, des nombres, des identifiants et des chemins de clé.

    uv run tools/export_jira_api.py migrate-teams --from-assets Flux-Lab/equipes-assets-complet-AAAA-MM-JJ.csv [--language fr|en]
        Utilisateur seul, dans le Terminal (refusé dans une session Claude Code). Aucun appel à Jira. Écrit une fois le catalogue
        (Flux-Lab/equipes-jira.yaml, droits 600) depuis la liste Assets complète : une entrée par libellé, son type, `obsolete: true`
        quand tous ses objets sont inactifs ou abandonnés ; propose les libellés distinctifs à ajouter à la liste des noms sensibles.

    uv run tools/export_jira_api.py review-teams --add IDENTIFIANT [IDENTIFIANT ...] [--language fr|en]
        Utilisateur seul, dans le Terminal (refusé dans une session Claude Code, code 3, avant toute lecture). Aucun appel à Jira.
        Ajoute plusieurs identifiants à la liste de revue des entrées extérieures (Flux-Lab/equipes-revues.yaml, droits 600, des
        identifiants seulement) : chacun doit être porté par une entrée du catalogue et listé par aucune équipe du référentiel, sinon
        toute la commande est refusée (code 1) et rien n'est écrit. Sans --add, ou avec une autre option : code 2. check-teams sépare
        les entrées vues sur des tickets en « déjà revues » et « à revoir » avec cette liste ; migrate-teams ne la touche jamais.

Les sous-commandes teams-table et compare (qui reposaient sur l'export manuel CSV) sont retirées : les lancer affiche
la voie à suivre. La traduction des équipes se complète dans le référentiel et le catalogue (check-teams, migrate-teams) ; la comparaison de deux
rapports est dans flow_compare.py.

Réglages (Flux-Lab/flux.yaml), en plus de jira_site, jira_email et jira_token_type :
    jql_export          requête JQL de l'export (obligatoire pour diagnose et export, sauf si jql_exports existe)
    jql_exports         requêtes nommées (nom: requête JQL) ; `export` les lit toutes dans un passage,
                        `export --query NOM` une seule (un passage qui ne compte pas comme jeu complet pour la marque « sorti de
                        l'export ») ; prime sur jql_export
    export_team_field identifiant du champ « [G] Team/s » (customfield_NNNNN) ; absent : export sans équipe
    export_team_header  ancien réglage du nom des colonnes d'équipe, toujours accepté, sans effet (l'export n'écrit plus de colonne)
    export_verification_field, export_verification_header : anciens réglages de la colonne « Verification Required », toujours
                        acceptés, sans effet (aucun lecteur ne s'en sert : le champ n'est plus demandé à Jira)
    export_points_field identifiant du champ des story points (customfield_NNNNN, à retrouver avec
                        `fields --search "Story point"`), ou liste d'identifiants (la valeur prend le premier champ
                        non vide, dans l'ordre de la liste ; pour chaque identifiant, `export` affiche le nombre de
                        tickets où il est rempli et celui où un autre est rempli avec une valeur différente, jamais une
                        valeur) ; absent : pas de story points. Valeur enregistrée
                        telle que renvoyée (entier ou décimal) ; nulle si absente ; une valeur non numérique est comptée,
                        jamais affichée
    export_timezone       fuseau des dates enregistrées (par défaut Europe/Paris, comme l'export manuel)

Les accès à Jira, le jeton (Trousseau macOS, jamais affiché) et les reprises viennent de history_jira.py, que ce
script importe : un seul code d'accès à Jira. Ce script est séparé de history_jira.py parce qu'il lit d'autres
champs (état courant, dates, parent, liens, équipe) que le seul historique des états de cette collecte.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
import time
from dataclasses import dataclass
from decimal import Decimal
from zoneinfo import ZoneInfo
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flux_config
import flow_organisation
import export_jira_api_equipes as equipes
import sensitive_names
from yaml_strict import charger
import flow_raw
import flow_delivery
import history_common as commun
import history_jira as hj
from export_jira_api_messages import CATALOGS
from messages import Messages, add_language_option

OPTIONS_RENOMMEES = {**flux_config.OPTIONS_COMMUNES, "--cherche": "--search", "--requete": "--query"}

PAGE = 100
ECHANTILLON_REMPLISSAGE = 500        # fields --project --field : nombre maximal de derniers tickets créés comptés
CLE_PROJET = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,49}")
CHAMP_ADMIS = re.compile(r"customfield_[0-9]+|components|fixVersions|versions")      # jamais un champ système de texte ou de personne
# Champs demandés à Jira : les versions courantes (fixVersions, versions : validées le 2026-10-23, change flow-version-share), ni
# étiquettes (la collecte de l'historique les demande), ni colonne de vérification, ni titre ni personne (database-only, D5 et spec
# jira-flow-export « No sensitive field requested or printed »)
CHAMPS_DE_BASE = ["issuetype", "status", "created", "resolutiondate", "resolution", "statuscategorychangedate",
                  "parent", "issuelinks", "updated", "fixVersions", "versions"]
CLES_LIBELLE = ("name", "value", "label", "displayName", "title")
IDENTIFIANT = re.compile(r"\d+|[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}")

EQUIPE_INCONNUE = "(équipe inconnue)"      # nom d'équipe enregistré pour un identifiant inconnu : donnée, identique dans les deux langues
NOM_TABLE = "equipes-assets.yaml"
NOM_REFERENTIEL = "organisation.yaml"
NOM_CATALOGUE = "equipes-jira.yaml"
NOM_REVUE = "equipes-revues.yaml"
RETIREES = {"teams-table": "retired_teams_table", "compare": "retired_compare"}     # sous-commandes retirées -> message

_MESSAGES = Messages(CATALOGS, "fr")
_LANGUE = "fr"


def set_language(language: str) -> None:
    """Langue des messages et des sorties (français par défaut), pour ce script et pour history_jira.py qu'il importe."""
    global _MESSAGES, _LANGUE
    _MESSAGES = Messages(CATALOGS, language)
    _LANGUE = language
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
    """Sources de traduction des identifiants d'équipe lues ensemble (design D1) : `correspondance` identifiant -> nom (le nom
    de l'équipe du référentiel, sinon le libellé du catalogue ; None sans aucun identifiant), le référentiel et le catalogue
    lus, la présence du fichier de l'ancienne table (jamais lue ici), les identifiants du catalogue qu'aucune équipe du
    référentiel ne liste (équipes hors organisation) et ceux que le catalogue marque obsolètes (référentiel compris)."""
    correspondance: dict[str, str] | None
    referentiel: flow_organisation.Referentiel | None
    catalogue: flow_organisation.Catalogue
    table_presente: bool
    exterieurs: frozenset = frozenset()
    obsoletes: frozenset = frozenset()


def resoudre_traduction() -> Traduction:
    """Référentiel et catalogue lus ensemble : le nom du référentiel d'abord, sinon le libellé du catalogue ; un identifiant
    dans les deux fichiers est accepté. L'ancienne table n'est jamais lue. Un fichier illisible ou une règle entre les deux
    sources refusée arrête (`ErreurConfig`, chemin et ligne sans valeur). Sans aucun identifiant : `correspondance` est None."""
    referentiel = flow_organisation.charger_si_present(hj.FLUX_DIR / NOM_REFERENTIEL, _LANGUE)
    catalogue = flow_organisation.charger_catalogue_si_present(hj.FLUX_DIR / NOM_CATALOGUE, _LANGUE)
    if referentiel is not None:
        flow_organisation.verifier_sources(referentiel, catalogue, _LANGUE)
    identifiants = [i for e in catalogue.entrees for i in e.jira_ids]
    if referentiel is not None:
        identifiants += [i for e in referentiel.teams.values() for i in e.jira_ids]
    # une seule traduction identifiant -> nom : flow_organisation.nom_traduit (référentiel d'abord, sinon libellé du catalogue)
    correspondance = {i: flow_organisation.nom_traduit(i, referentiel, catalogue) for i in dict.fromkeys(identifiants)}
    exterieurs = frozenset(i for i in catalogue.ids if referentiel is None or referentiel.team_for_jira_id(i) is None)
    obsoletes = frozenset(i for i in catalogue.ids if catalogue.est_obsolete(i))
    return Traduction(correspondance or None, referentiel, catalogue, (hj.FLUX_DIR / NOM_TABLE).exists(), exterieurs, obsoletes)


def structures_des_sources() -> dict[str, str]:
    """Structure (clés seules) du référentiel et du catalogue, pour la phrase « aucune source d'équipes »."""
    if _LANGUE == "en":
        return {"referential": flow_organisation.STRUCTURE_EN, "catalogue": flow_organisation.STRUCTURE_CATALOGUE_EN}
    return {"referential": flow_organisation.STRUCTURE, "catalogue": flow_organisation.STRUCTURE_CATALOGUE}


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
    """(texte du nombre, valeur non numérique). Un nombre s'enregistre tel que renvoyé ; absent ou null : texte vide ;
    toute autre forme (texte, booléen, objet) : texte vide, signalée, sans jamais afficher la valeur."""
    if valeur is None:
        return "", False
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
        return str(valeur), False
    return "", True


def noms_de_versions(valeur) -> list[str]:
    """Noms des versions d'un champ de versions de Jira, dans l'ordre et l'orthographe renvoyés ; un nom vide ou répété est ignoré.
    Jamais affiché."""
    noms: list[str] = []
    for version in valeur if isinstance(valeur, list) else []:
        nom = str((version or {}).get("name") or "").strip() if isinstance(version, dict) else ""
        if nom and nom not in noms:
            noms.append(nom)
    return noms


def attributs_de_sortie(*valeurs) -> dict[str, dict]:
    """Date de sortie et drapeau « sortie » de chaque version des champs de versions de Jira (change version-release-date, design D1, D2) :
    {nom: {"date": date ISO ou None, "released": booléen ou None}}. Seuls `releaseDate` et `released` sont lus, aucun autre attribut de
    l'objet ; une valeur de forme inattendue donne None. Un nom présent dans les deux champs garde les valeurs du premier objet qui en
    porte. Jamais affiché."""
    attributs: dict[str, dict] = {}
    for valeur in valeurs:
        for version in valeur if isinstance(valeur, list) else []:
            if not isinstance(version, dict):
                continue
            nom = str(version.get("name") or "").strip()
            if not nom:
                continue
            date = version.get("releaseDate")
            try:
                date = dt.date.fromisoformat(date).isoformat() if isinstance(date, str) else None
            except ValueError:
                date = None
            sortie = version.get("released")
            lu = {"date": date, "released": sortie if isinstance(sortie, bool) else None}
            if nom not in attributs:
                attributs[nom] = lu
    return attributs


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
# Instantanés de la couche brute (database-only, D1 et D3)
# ---------------------------------------------------------------------------

def fuseau_export(settings: dict) -> ZoneInfo:
    """Fuseau des dates enregistrées : la règle partagée de history_common (idée #169, D9) ; un fuseau inconnu garde le message
    et la sortie de l'export (arrêt avant tout appel à Jira)."""
    try:
        return commun.fuseau_export(settings)
    except commun.ErreurFuseau as erreur:
        raise Arret(t("timezone_invalid", name=erreur.nom, example=commun.FUSEAU_PAR_DEFAUT)) from None


def instant_api(valeur, fuseau: dt.tzinfo) -> dt.datetime | None:
    """Date ISO de l'API (2017-11-09T08:49:00.000+0100) en instant du fuseau d'export, à la minute (la précision de l'export
    manuel, que la couche brute garde pour que les rapports restent les mêmes). Une date sans décalage garde son heure locale.
    Illisible ou absente : None."""
    if not valeur:
        return None
    try:
        d = dt.datetime.fromisoformat(str(valeur))
    except ValueError:
        return None
    d = d.astimezone(fuseau) if d.tzinfo is not None else d.replace(tzinfo=fuseau)
    return d.replace(second=0, microsecond=0)


def liens_de(ticket: dict) -> list[tuple[str, str, str]]:
    """Liens du ticket, sans doublon : (clé liée, type de lien, sens). Le sens est « outward » pour un lien « outwardIssue » (ce
    ticket bloque l'autre) et « inward » pour « inwardIssue »."""
    sortie: list[tuple[str, str, str]] = []
    for lien in (ticket.get("fields") or {}).get("issuelinks") or []:
        type_ = str((lien.get("type") or {}).get("name") or "").strip()
        for sens, cle_api in (("outward", "outwardIssue"), ("inward", "inwardIssue")):
            autre = (lien.get(cle_api) or {}).get("key")
            if autre and type_:
                sortie.append((str(autre), type_, sens))
    return list(dict.fromkeys(sortie))


def nombre_points(texte: str) -> Decimal | None:
    """Story points enregistrés : le nombre du premier champ renseigné, en décimal ; vide : None."""
    return Decimal(texte) if texte else None


def construire_instantanes(tickets: list[dict], champ_equipe: str | None, table: dict[str, str] | None = None,
                           fuseau: dt.tzinfo | None = None, champ_points: str | list[str] | None = None,
                           exterieurs: frozenset = frozenset(), obsoletes: frozenset = frozenset(),
                           separateur: str = ";", types_defauts=()) -> tuple[dict[str, dict], dict]:
    """Instantanés de la couche brute (clé -> instantané de flow_raw) des tickets lus, et quelques effectifs. Un libellé d'équipe
    est pris tel quel ; un identifiant d'objet se traduit par `table` (identifiant -> nom ; absent : « (équipe inconnue) »,
    compté). Lève Arret si le champ d'équipe n'est ni un libellé ni un identifiant traduisible. Un ticket sans date de création ou de
    mise à jour lisible n'a pas d'instantané (Jira renvoie toujours les deux).
    Champs de livraison (change jira-delivery-fields, D1) : réduits à leur forme stockée dans la partie `delivery` de l'instantané ; les champs
    des défauts ne sont gardés que pour les types de `types_defauts` ; un champ d'option n'est gardé que par son identifiant d'option
    (R-20261102-51), les engagements et l'objectif stratégique par leur seule présence (R-20261102-50)."""
    fuseau = fuseau or dt.timezone.utc
    equipes = {}
    paires_equipes: dict[str, list[tuple[str, str | None]]] = {}      # par ticket : (nom écrit, identifiant d'équipe Jira ou None)
    inconnus: Counter = Counter()
    tickets_inconnus: set[str] = set()
    exterieurs_vus: set[str] = set()          # identifiants du catalogue hors référentiel vus, et leurs tickets
    tickets_exterieurs: set[str] = set()
    tickets_obsoletes: set[str] = set()
    traduits = False
    if champ_equipe:
        for ticket in tickets:
            valeur = (ticket.get("fields") or {}).get(champ_equipe)
            noms = libelles(valeur)
            paires = [(nom, None) for nom in noms or []]
            if noms is None:
                ids = identifiants(valeur) if table is not None else None
                if ids is None:
                    formes, _ = analyser_equipes(tickets, champ_equipe)
                    raise Arret(t("team_label_options", form=", ".join(t("form_count", form=f, count=n) for f, n in sorted(formes.items())),
                                  **structures_des_sources()))
                traduits = traduits or bool(ids)
                noms = []
                paires = []
                for identifiant in dict.fromkeys(ids):
                    if identifiant in table:
                        noms.append(table[identifiant])
                        if identifiant in exterieurs:
                            exterieurs_vus.add(identifiant)
                            tickets_exterieurs.add(str(ticket["key"]))
                        if identifiant in obsoletes:
                            tickets_obsoletes.add(str(ticket["key"]))
                    else:
                        noms.append(EQUIPE_INCONNUE)
                        inconnus[identifiant] += 1
                        tickets_inconnus.add(str(ticket["key"]))
                    paires.append((noms[-1], identifiant))
            equipes[str(ticket["key"])] = noms
            paires_equipes[str(ticket["key"])] = paires
    champs_points = [champ_points] if isinstance(champ_points, str) else list(champ_points or [])
    par_champ = {c: [0, 0] for c in champs_points}          # champ -> [tickets renseignés, tickets en désaccord avec un autre champ]
    points_renseignes = points_invalides = 0
    instantanes: dict[str, dict] = {}
    for ticket in tickets:
        cle, champs = str(ticket["key"]), ticket.get("fields") or {}
        texte = ""
        if champs_points:
            lus = [texte_points(champs.get(c)) for c in champs_points]
            points_invalides += sum(invalide for _, invalide in lus)
            remplis = {c: valeur for c, (valeur, _) in zip(champs_points, lus) if valeur}
            for c in remplis:
                par_champ[c][0] += 1
                if any(float(v) != float(remplis[c]) for autre, v in remplis.items() if autre != c):
                    par_champ[c][1] += 1
            texte = next(iter(remplis.values()), "")           # première valeur non vide, dans l'ordre de la liste
            points_renseignes += bool(texte)
        cree, modifie = instant_api(champs.get("created"), fuseau), instant_api(champs.get("updated"), fuseau)
        if cree is None or modifie is None:
            continue
        statut = champs.get("status") or {}
        ticket_lu = {
            "cle": cle, "projet": cle.rsplit("-", 1)[0].upper() if "-" in cle else "",
            "type": (champs.get("issuetype") or {}).get("name") or "?", "etat": statut.get("name") or "",
            "categorie": (statut.get("statusCategory") or {}).get("name") or None, "cree": cree,
            "resolu": instant_api(champs.get("resolutiondate"), fuseau),
            "motif": (champs.get("resolution") or {}).get("name") or None,
            "debut": instant_api(champs.get("statuscategorychangedate"), fuseau),
            "points": nombre_points(texte), "modifie": modifie, "parent": (champs.get("parent") or {}).get("key") or None,
            "equipes": equipes.get(cle, []), "liens": liens_de(ticket),
            "delivery": flow_delivery.livraison_de(champs, (champs.get("issuetype") or {}).get("name") or "", types_defauts),
            "versions": {"fix": noms_de_versions(champs.get("fixVersions")), "affects": noms_de_versions(champs.get("versions")),
                         "release": attributs_de_sortie(champs.get("fixVersions"), champs.get("versions"))}}
        instantanes[cle] = flow_raw.instantane(ticket_lu, paires_equipes.get(cle), separateur)
    vues = {nom for noms in equipes.values() for nom in noms if nom != EQUIPE_INCONNUE}
    return instantanes, {"inconnus_distincts": len(inconnus), "inconnus_ids": sorted(inconnus), "inconnus_tickets": len(tickets_inconnus),
                         "exterieurs_distincts": len(exterieurs_vus), "exterieurs_tickets": len(tickets_exterieurs),
                         "obsoletes_tickets": len(tickets_obsoletes),
                         "table_utilisee": table is not None, "traduction_utilisee": traduits, "equipes_vues": vues,
                         "equipes_paires": paires_equipes,
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


def type_de_l_identifiant(identifiant: str, traduction: "Traduction") -> str | None:
    """Type d'équipe d'un identifiant d'équipe Jira (complément « Complement: team type column » de database-only) : le type effectif
    de l'équipe du référentiel qui le liste (forcé, sinon déduit du catalogue), sinon le type de l'entrée du catalogue, sinon None.
    Jamais deviné : ni d'une étiquette, ni d'une autre équipe."""
    referentiel = traduction.referentiel
    if referentiel is not None:
        nom = referentiel.team_for_jira_id(identifiant)
        if nom is not None:
            return flow_organisation.type_effectif(referentiel.teams[nom], traduction.catalogue)
    entree = traduction.catalogue.entree_pour(identifiant)
    return entree.type if entree is not None else None


def types_des_equipes(instantanes: dict[str, dict], traduction: "Traduction") -> dict[str, str | None]:
    """Nom d'équipe -> type (None sans type connu), pour les équipes des instantanés. Une équipe sans identifiant (libellé) n'a pas de
    type ; une équipe vue avec et sans identifiant garde le type de celle qui en a un."""
    types: dict[str, str | None] = {}
    for instantane in instantanes.values():
        for equipe in instantane["teams"]:
            nom, identifiant = equipe["name"], equipe.get("jira_team_id")
            type_ = type_de_l_identifiant(identifiant, traduction) if identifiant else None
            if types.get(nom) is None:
                types[nom] = type_
    return types


# ---------------------------------------------------------------------------
# Couche brute datée (changes jira-data-architecture et database-only)
# ---------------------------------------------------------------------------

ROLE_IMPORT = "pmzilla_flow"


def ouvrir_magasin():
    """Magasin de la couche brute : connexion de la base sous le rôle d'import, avec son propre mot de passe (Trousseau, puis
    variable d'environnement), avant tout appel à Jira. Lève Arret avec la phrase fixe si le mot de passe manque ou si la base ne
    répond pas : jamais de mot de passe, d'adresse ni de détail de la base dans le message."""
    import db
    if db.lire_mot_de_passe(role=ROLE_IMPORT) is None:
        raise Arret(t("raw_password_missing"))
    try:
        return flow_raw.MagasinBase(db.connect(role=ROLE_IMPORT))
    except db.ErreurBase:
        raise Arret(t("raw_db_unreachable")) from None


# ---------------------------------------------------------------------------
# Commandes
# ---------------------------------------------------------------------------

def afficher_hors_perimetre(client) -> None:
    """La ligne du nombre de tickets écartés hors des projets déclarés (design D9) : seulement au-dessus de zéro, jamais une clé."""
    if client.tickets_hors_perimetre:
        hj.afficher(hj.t("out_of_scope_count", count=client.tickets_hors_perimetre))


def cmd_diagnose(args: argparse.Namespace) -> None:
    settings, requetes, champ, _ = reglages_export()
    jql = requetes[0][1]          # la première requête suffit à voir la forme du champ
    if not champ:
        raise Arret(t("diagnose_no_field"))
    client = hj.construire_client(settings)
    tickets, _ = interroger(client, jql, [champ], une_page=True)
    hj.afficher(t("diagnose_page", count=len(tickets)))
    afficher_hors_perimetre(client)
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
        referentiel = traduction.referentiel.jira_ids_count if traduction.referentiel is not None else 0
        hj.afficher(t("diagnose_labels_sources"))
        hj.afficher(t("diagnose_sources", referential=referentiel, catalogue=len(traduction.catalogue.ids)))    # effectifs seulement
        if traduction.table_presente:
            hj.afficher(t("table_deprecated"))
    else:
        hj.afficher(t("diagnose_labels_no"))
        hj.afficher(t("team_label_options", form=", ".join(sorted(formes)), **structures_des_sources()))
        if (hj.FLUX_DIR / NOM_TABLE).exists():
            hj.afficher(t("table_deprecated"))
        sys.exit(1)


def est_rempli(valeur) -> bool:
    """Vrai si la valeur du champ est renseignée. Absent, None, texte d'espaces, liste vide, objet sans value, name ni id (non
    vide) et document ADF sans contenu : non remplis ; nombre ou booléen (0 et False compris) : remplis. Le contenu n'est jamais gardé."""
    if valeur is None:
        return False
    if isinstance(valeur, str):
        return bool(valeur.strip())
    if isinstance(valeur, (list, tuple)):
        return len(valeur) > 0
    if isinstance(valeur, dict):
        if valeur.get("type") == "doc":
            return bool(valeur.get("content"))
        return any(est_rempli(valeur.get(cle)) for cle in ("value", "name", "id"))
    return True


def valider_remplissage(args: argparse.Namespace) -> tuple[str, list[str]]:
    """Contrôles de forme, avant la lecture du jeton et tout appel : clé de projet, champs non vides, identifiants admis
    (customfield_NNNNN, components, fixVersions et versions seulement). Rend la clé et les champs demandés, sans doublon, dans l'ordre."""
    projet = (args.projet or "").strip()
    if not CLE_PROJET.fullmatch(projet):
        raise Arret(t("fields_project_invalid"))
    bruts = [f.strip() for f in args.champs_demandes]
    if not bruts or any(not f for f in bruts):
        raise Arret(t("fields_field_empty"))
    refuses = [f for f in bruts if not CHAMP_ADMIS.fullmatch(f)]
    if refuses:
        raise Arret(t("fields_field_not_allowed", ids=", ".join(dict.fromkeys(refuses))))
    return projet, list(dict.fromkeys(bruts))


def est_champ_de_personne(champ: dict) -> bool:
    schema = champ.get("schema") if isinstance(champ.get("schema"), dict) else {}
    return "user" in (schema.get("type"), schema.get("items"))


def cmd_remplissage(args: argparse.Namespace) -> None:
    """Pour chaque --field : le nombre de tickets où il est rempli, sur les derniers tickets créés du projet. Sortie : identifiant,
    nom, compte et taille de l'échantillon, jamais une valeur ni une clé de ticket."""
    projet, demandes = valider_remplissage(args)
    client = hj.construire_client(hj.reglages())
    champs = client.json("GET", "/rest/api/3/field")
    if not isinstance(champs, list):
        raise Arret(t("fields_unexpected"))
    connus = {str(c.get("id") or ""): c for c in champs if isinstance(c, dict)}
    inconnus = [f for f in demandes if f not in connus]
    if inconnus:
        raise Arret(t("fields_unknown", ids=", ".join(inconnus)))
    personnes = [f for f in demandes if est_champ_de_personne(connus[f])]
    if personnes:
        raise Arret(t("fields_field_person", ids=", ".join(personnes)))
    noms = {f: str(connus[f].get("name") or "") for f in demandes}
    limite = ECHANTILLON_REMPLISSAGE
    jql = f'project = "{projet}" ORDER BY created DESC'
    remplis, vus, jeton = Counter(), 0, None
    while vus < limite:
        corps = {"jql": jql, "fields": demandes, "maxResults": min(PAGE, limite - vus)}
        if jeton:
            corps["nextPageToken"] = jeton
        reponse = client.json("POST", "/rest/api/3/search/jql", json=corps)
        for ticket in (reponse.get("issues") or [])[:limite - vus]:
            vus += 1
            valeurs = ticket.get("fields") or {}
            for f in demandes:
                if est_rempli(valeurs.get(f)):
                    remplis[f] += 1
        suivant = reponse.get("nextPageToken")
        if not suivant or suivant == jeton or not reponse.get("issues"):
            break
        jeton = suivant
        time.sleep(hj.PAUSE)
    hj.afficher(t("fields_sample", project=projet, count=vus, limit=limite))
    for f in demandes:
        hj.afficher(f"  {f}  {noms[f]}  {remplis[f]}/{vus}")
    afficher_hors_perimetre(client)


def cmd_champs(args: argparse.Namespace) -> None:
    """Identifiant et nom des champs dont le nom contient le texte cherché, ou (--project et --field) le nombre de tickets où des
    champs sont remplis. Rien d'autre n'est affiché ni gardé."""
    if args.cherche is None:
        return cmd_remplissage(args)
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


def cmd_export(args: argparse.Namespace) -> None:
    """Export des tickets : un passage de la couche brute datée, écrit en une transaction ou pas du tout (database-only, D1 et D3).
    Une erreur de Jira ou de la base ne laisse aucun passage, aucune visite ni aucun instantané ; aucun fichier n'est écrit."""
    pile: dict = {"magasin": None}
    try:
        _export(args, pile)
    finally:
        if pile["magasin"] is not None:
            pile["magasin"].fermer()


def lire_versions(client, settings: dict, filtre: "flow_delivery.FiltreOptions | None" = None) -> dict[str, dict] | None:
    """Recherche unique des tickets de type Version du projet de référence des versions (jira-delivery-fields D4, D5) : {objet d'actif:
    contenu} joint par flow_delivery.joindre_versions, ou None quand le réglage est absent (ligne fixe, aucune recherche). La forme de la
    recherche est celle que le client compare littéralement ; sa réponse ne garde que des tickets de type Version. Les lignes de compte (D12)
    sont des nombres. Aucune clé de ticket de version, aucun résumé, aucun identifiant ne sort ni n'est stocké."""
    if client.reference is None:
        hj.afficher(t("export_no_version_project"))
        return None
    if not flow_delivery.versions_configurees():          # sans l'objet d'actif des tickets de version, pas de jointure : aucune recherche
        if flow_delivery.table_configuree():          # table absente : la ligne de l'export l'a déjà dit
            hj.afficher(t("export_no_version_fields"))
        return None
    avant = client.autres_types_reference
    tickets, _ = interroger(client, hj.recherche_versions(client.reference), flow_delivery.champs_versions())
    lus = [flow_delivery.version_de_ticket(ticket.get("fields") or {}, filtre) for ticket in tickets]
    contenus, comptes = flow_delivery.joindre_versions(lus)
    hj.afficher(t("export_version_tickets", count=comptes["lus"]))
    if client.autres_types_reference - avant:
        hj.afficher(t("export_version_other_type", count=client.autres_types_reference - avant))
    if comptes["sans_actif"]:
        hj.afficher(t("export_version_no_asset", count=comptes["sans_actif"]))
    if comptes["plusieurs_actifs"]:
        hj.afficher(t("export_version_several_assets", count=comptes["plusieurs_actifs"]))
    if comptes["conflits"]:
        hj.afficher(t("export_version_conflicts", count=comptes["conflits"]))
    return contenus


def _export(args: argparse.Namespace, pile: dict) -> None:
    if args.sortie is not None:          # option retirée : avant tout appel à Jira et toute connexion
        hj.afficher(t("error_line", message=t("output_retired")))
        sys.exit(2)
    settings, requetes, champ, _ = reglages_export()
    fuseau = fuseau_export(settings)       # réglage invalide : arrêt avant tout appel à Jira
    champ_points = reglage_points(settings)
    jours_conservation = flux_config.retention_days(settings)       # au-delà d'un an : refus avant tout appel
    requetes = choisir_requetes(requetes, args.requete)
    separateur = settings.get("separateur_equipes") or ";"
    traduction = resoudre_traduction() if champ else Traduction(None, None, flow_organisation.Catalogue(), False)   # refus : avant Jira
    pile["magasin"] = ouvrir_magasin()          # mot de passe absent ou base injoignable : arrêt avant tout appel à Jira (D4, D13)
    filtre = flow_delivery.FiltreOptions()
    try:
        filtre.charger()          # garde neuve (R-20261102-41, Q326) : liste des noms sensibles chargée AVANT le premier appel à Jira ; remplace : rien ;
    except sensitive_names.SensitiveNamesUnavailable:          # retrait : permanent tant qu'un nom court de version est stocké (R-20261102-51)
        raise Arret(t("sensitive_list_unavailable")) from None          # jamais le chemin ni le contenu de la liste
    client = hj.construire_client(settings, avec_reference=True)          # réglage de la référence des versions illisible : code 6, avant tout appel
    types_defauts = flux_config.defect_types(settings)
    avec_table = flow_delivery.configurer(flux_config.delivery_fields(settings))          # table de flux.yaml, hors Git (R-20261114-108, même logique que A-92)
    if not avec_table:
        hj.afficher(t("export_no_delivery_fields"))          # sans table : aucun champ demandé, livraison déjà stockée conservée (R-20261114-89 C2)
    equipes_inconnues = avertie = False
    equipes_vues: set[str] = set()
    instantanes: dict[str, dict] = {}          # couche brute : le dernier passage de requête l'emporte pour un ticket lu deux fois
    vus: list[str] = []
    for nom, jql in requetes:
        etiquette = f"[{nom}] " if nom else ""
        # lecture complète à chaque passage (D3 (c)) : aucune condition sur la date de mise à jour, aucun instant d'un passage antérieur
        tickets, pages = interroger(client, jql, CHAMPS_DE_BASE + ([champ] if champ else []) + champ_points
                                    + flow_delivery.champs_demandes())
        tickets, hors_conservation = ecarter_hors_conservation(tickets, jours_conservation, hj.aujourd_hui(), fuseau)
        instantanes_requete, effectifs = construire_instantanes(tickets, champ, traduction.correspondance, fuseau, champ_points,
                                                                traduction.exterieurs, traduction.obsoletes, separateur,
                                                                types_defauts)
        equipes_vues |= effectifs["equipes_vues"]
        instantanes.update(instantanes_requete)
        vus += [str(ticket["key"]) for ticket in tickets]
        hj.afficher(t("export_summary", label=etiquette, tickets=len(tickets), pages=pages))
        if hors_conservation:
            hj.afficher(t("export_past_retention", label=etiquette, count=hors_conservation))
        if not champ:
            hj.afficher(t("export_no_team_column", label=etiquette))
        if effectifs["points_renseignes"] is not None:
            hj.afficher(t("export_points", label=etiquette, filled=effectifs["points_renseignes"], total=len(tickets)))
            for identifiant, (remplis, desaccords) in effectifs["points_par_champ"].items():
                hj.afficher(t("export_points_field", label=etiquette, field=identifiant, filled=remplis, total=len(tickets),
                              conflicts=desaccords))
            if effectifs["points_invalides"]:
                hj.afficher(t("export_points_invalid", label=etiquette, count=effectifs["points_invalides"]))
        if effectifs["traduction_utilisee"] and traduction.table_presente and not avertie:
            avertie = True
            hj.afficher(t("table_deprecated"))      # l'ancienne table n'est jamais lue : la phrase demande de la supprimer
        if effectifs["exterieurs_tickets"]:          # nombres seulement : jamais un libellé
            hj.afficher(t("export_outside", label=etiquette, identifiers=effectifs["exterieurs_distincts"],
                          tickets=effectifs["exterieurs_tickets"]))
        if effectifs["obsoletes_tickets"]:
            hj.afficher(t("export_obsolete", label=etiquette, tickets=effectifs["obsoletes_tickets"]))
        if effectifs["inconnus_tickets"]:
            equipes_inconnues = True
            hj.afficher(t("export_unknown_teams", label=etiquette, identifiers=effectifs["inconnus_distincts"],
                          tickets=effectifs["inconnus_tickets"]))
            hj.afficher(t("export_unknown_ids", label=etiquette, ids=t("list_separator").join(effectifs["inconnus_ids"])))
    versions = lire_versions(client, settings, filtre)          # une recherche de forme fixe, ou rien sans le réglage (D4)
    if filtre.remplacees:          # un nombre, jamais une valeur (jira-delivery-fields D1, D12) ; ne compte plus que les noms courts de version
        hj.afficher(t("export_option_filter", count=filtre.remplacees))
    afficher_hors_perimetre(client)
    if traduction.referentiel is not None:        # contrôle du référentiel : un nombre, jamais un nom (design D17)
        sans_ticket = sum(1 for nom in traduction.referentiel.teams if nom not in equipes_vues)
        if sans_ticket:
            hj.afficher(t("export_referential_idle", count=sans_ticket))
    if args.strict_equipes and equipes_inconnues:        # option stricte (orchestrateur du suivi mensuel) : le mois est incomplet, rien n'est écrit
        hj.afficher(t("export_strict_teams"))
        sys.exit(3)
    types = types_des_equipes(instantanes, traduction)
    ecriture_versions = {} if versions is None else {"versions": versions}          # absent sans le réglage : appel inchangé
    if not avec_table:          # sans table : la partie `delivery` du dernier instantané est reprise, rien n'est effacé ni réécrit pour cette raison
        ecriture_versions["livraison_conservee"] = True
    nb_vus, ajoutes = pile["magasin"].enregistrer(genre="export", nb_requetes=len(requetes), toutes=args.requete is None,
                                                       vus=vus, instantanes=instantanes, types_equipes=types, **ecriture_versions)
    hj.afficher(t("export_teams_without_type", count=pile["magasin"].sans_type))          # un effectif, jamais un libellé
    hj.afficher(t("export_raw_layer", seen=nb_vus, added=ajoutes))      # des effectifs seulement : ni clé, ni équipe, ni valeur


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Export des tickets Jira par l'API, écrit dans la couche brute de la base (teams-table et compare sont retirées)")
    commandes = parser.add_subparsers(dest="commande", required=True,
                                      metavar="{diagnose,fields,export,check-teams,migrate-teams,review-teams,extract-teams}")
    commandes.add_parser("diagnose", help="forme des valeurs du champ d'équipe (jamais les valeurs)")
    champs = commandes.add_parser("fields", help="identifiant et nom des champs dont le nom contient un texte ; avec --project et "
                                                 "--field, compte les tickets où des champs sont remplis")
    champs.add_argument("--search", dest="cherche", metavar="TEXTE", help="texte cherché dans le nom des champs (sans casse)")
    champs.add_argument("--project", dest="projet", metavar="CLE",
                        help=f"avec --field : projet dont les {ECHANTILLON_REMPLISSAGE} derniers tickets créés sont comptés")
    champs.add_argument("--field", dest="champs_demandes", action="append", default=[], metavar="IDENTIFIANT",
                        help="avec --project : champ dont on compte les tickets où il est rempli (répétable ; components, fixVersions et versions admis)")
    export = commandes.add_parser("export", help="écrit un passage de la couche brute datée (jql_exports, ou jql_export)")
    export.add_argument("--query", dest="requete", metavar="NOM", help="ne lance que cette requête de jql_exports (par défaut : toutes)")
    export.add_argument("--full", action="store_true",
                        help="force la lecture complète de chaque requête (c'est déjà le comportement par défaut : aucun changement)")
    export.add_argument("--output", dest="sortie", help=argparse.SUPPRESS)          # retirée : refusée avec le code 2
    export.add_argument("--strict-teams", dest="strict_equipes", action="store_true",
                        help="identifiants d'équipe dans aucune des deux sources (référentiel, catalogue) : sort avec le code 3 sans rien écrire")
    commandes.add_parser("check-teams", help="contrôle le référentiel, le catalogue et l'ancienne table (utilisateur seul, hors "
                                             "session Claude Code)")
    migrer = commandes.add_parser("migrate-teams", help="écrit le catalogue depuis la liste Assets complète (utilisateur seul, hors "
                                                        "session Claude Code)")
    migrer.add_argument("--from-assets", dest="liste", required=True, metavar="FICHIER",
                        help="equipes-assets-complet-AAAA-MM-JJ.csv du dossier des flux")
    revoir = commandes.add_parser("review-teams", help="ajoute des identifiants à la liste de revue des entrées extérieures "
                                                       "(utilisateur seul, hors session Claude Code)")
    revoir.add_argument("--add", dest="ajouter", required=True, nargs="+", metavar="IDENTIFIANT",
                        help="un ou plusieurs identifiants du catalogue, hors référentiel (tout ou rien)")
    commandes.add_parser("extract-teams", help="écrit l'extrait des noms d'équipes lisible (utilisateur seul, hors session Claude Code)")
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
    if args.commande == "fields":
        if args.cherche is None and not (args.projet and args.champs_demandes):
            parser.error(t("fields_options_missing"))
        if args.cherche is not None and (args.projet or args.champs_demandes):
            parser.error(t("fields_options_combined"))
    try:
        if args.commande in ("check-teams", "migrate-teams", "review-teams", "extract-teams"):
            commande = {"check-teams": equipes.cmd_check_teams, "migrate-teams": equipes.cmd_migrate_teams,
                        "review-teams": equipes.cmd_review_teams, "extract-teams": equipes.cmd_extract_teams}[args.commande]
            commande(sys.modules[__name__], args)
        else:
            {"diagnose": cmd_diagnose, "fields": cmd_champs, "export": cmd_export}[args.commande](args)
    except flow_organisation.ErreurConfig as erreur:
        # refus du référentiel, du catalogue ou de la liste de revue (names-and-team-review, D9) : sortie d'erreur, préfixe des autres
        # refus de l'export, guillemets droits en anglais, phrase inchangée, aucune valeur
        message = str(erreur)
        if _LANGUE == "en":
            message = message.replace("« ", '"').replace(" »", '"').replace("«", '"').replace("»", '"')
        print(hj.masquer(t("error_line", message=message)), file=sys.stderr)
        sys.exit(1)
    except SystemExit:
        raise
    except hj.ErreurHTTP as erreur:
        hj.afficher(str(erreur))
        sys.exit(1)
    except hj.RequeteRefusee as erreur:          # la phrase fixe en entier, code 5 (jira-read-only-client, D3 et D4) : rien n'est enregistré
        hj.afficher(t("error_line", message=erreur))
        sys.exit(hj.CODE_REFUS)
    except hj.RequeteHorsPerimetre as erreur:    # code 6 (garde du périmètre, D10) : rien n'est enregistré
        hj.afficher(t("error_line", message=erreur))
        sys.exit(hj.CODE_PERIMETRE)
    except (hj.ErreurSimple, Arret) as erreur:
        hj.afficher(t("error_line", message=erreur))
        sys.exit(1)
    except Exception as erreur:       # aucun détail : un message de bibliothèque pourrait citer une adresse
        hj.afficher(t("unexpected_error", name=type(erreur).__name__))
        sys.exit(1)


if __name__ == "__main__":
    main()
