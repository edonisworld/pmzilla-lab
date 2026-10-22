# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "requests", "psycopg[binary]"]
# ///
"""
PMZilla Lab : collecte de l'historique des états des tickets Jira, écrite dans la base (change database-only, D5 et D6).

Trois champs sont lus dans l'historique de chaque ticket : « status » (la date de la transition, l'état de départ et
l'état d'arrivée), « Fix Version » (les ajouts et retraits de version, avec leur instant) et, seulement si des étiquettes
sont déclarées (réglage declared_labels), « labels » (les ajouts et retraits des étiquettes déclarées). Les valeurs courantes des
étiquettes déclarées et des versions sont demandées par la collecte elle-même (l'export ne les demande plus). L'auteur, les autres
champs et les étiquettes non déclarées sont écartés dès la lecture de la réponse : ils ne sont ni gardés, ni écrits, ni affichés. Les
chiffres qui en sortiront sont agrégés par équipe, sans aucune donnée individuelle. Aucun fichier d'export n'est lu et aucun cache
n'est écrit : la base (schéma flow) est la seule source et la seule destination.

    uv run tools/history_jira.py test
        Vérifie la connexion. N'affiche que « connexion OK » et une ligne d'accès par ressource, ou le code HTTP, jamais un nom ni une adresse.

    uv run tools/history_jira.py collect [--team <nom>] [--refresh] [--strict]
        Lit dans la base, sous le rôle d'import pmzilla_flow (avec son propre mot de passe, Trousseau pmzilla-lab-db-pmzilla_flow), les
        tickets à interroger : ceux sans historique, ceux non résolus et ceux mis à jour depuis la dernière collecte réussie moins un
        jour (--refresh : tous les tickets retenus). Les tickets résolus depuis plus que la durée de conservation (réglage
        retention.period_days, un an au plus) ne sont pas interrogés : ils sont comptés. Utilise l'API de récupération groupée des
        historiques si l'instance l'offre, sinon l'historique ticket par ticket. Délais d'attente, reprises avec attente croissante,
        Retry-After respecté (429). Écrit en UNE transaction les nouvelles transitions (jamais supprimées ni en double), l'indicateur
        « avec historique », les périodes d'étiquettes déclarées et de versions, le suivi des tickets introuvables et un passage
        « history » enregistré même avec des erreurs, avec le nombre d'erreurs passagères et de 404 (seul un passage sans erreur
        passagère avance la dernière collecte réussie). Un 404 (ticket introuvable) se distingue des erreurs passagères (429, 5xx,
        délai, réseau) : après N passages consécutifs en 404 (réglage history_not_found_limit, 3 par défaut) le ticket est marqué
        disparu et n'est plus interrogé (sauf --refresh) ; un ticket trouvé remet son compteur à zéro, une erreur passagère n'y touche
        pas. Une erreur d'accès (401, 403)
        ou de la base annule tout. --team
        filtre sur une équipe (le nom n'est donné qu'en argument). Un fichier d'export donné est refusé (code 2). Sortie : nombre de
        tickets traités, de transitions et d'erreurs, jamais une clé ni un nom, puis « historique écrit : T transitions ajoutées,
        P périodes écrites ». --strict : erreurs passagères de collecte (hors accès refusé ; les 404 ne comptent pas), rapport habituel puis
        sortie avec le code 3.

    uv run tools/history_jira.py check [--team <nom>] [--key <clé>]
        Ne contacte pas Jira. Lit la base (rôle en lecture seule) et compare, pour chaque ticket avec historique, le dernier état de
        l'historique à l'état stocké. Sortie : effectifs seulement (cohérents, incohérents, non comparables sans transition,
        transitions par ticket en tranches 0, 1, 2-4, 5-9, 10 et plus, tickets livrés sans transition), puis pour
        les tickets livrés : état de départ de la première transition connue, transitions par ticket, segments
        traversés et états traversés (un historique tronqué au début se voit à un état de départ qui n'est pas
        l'état initial du workflow). --key <clé> affiche seulement la suite des états de ce ticket, avec leurs
        dates et sans auteur, pour la comparer à l'onglet Historique de Jira : Terminal seulement, la clé y figure.
        À lancer par l'utilisateur seul : refusé dans une session Claude Code (code 3). Aucune base sans historique : code 1.
        L'ancienne option --dormants (export CSV des dormants) est refusée : les dormants se déduisent de l'historique
        (flux_jira.py --dormant-from-history).

Réglages (Flux-Lab/flux.yaml) : jira_site (https://<site>.atlassian.net), jira_email, jira_cloud_id (identifiant du
site, jamais lu sur le site hors `test`), jira_token_type (« scoped », valeur par défaut : le jeton « classic » est refusé),
jira_token_expires (date AAAA-MM-JJ, non secrète) et jira_token_warning_days. Tous les appels passent par
https://api.atlassian.com/ex/jira/<cloudId>. `test` lit le cloudId du site sans authentification et refuse un identifiant
différent, puis sonde chaque ressource lue (recherche, historique, champs) et signale l'échéance du jeton.

Le jeton est lu uniquement dans le Trousseau macOS (security find-generic-password -s pmzilla-jira -w). Il
n'est jamais affiché, journalisé, écrit dans un fichier ni inclus dans un message d'erreur. Les types
portfolio_types et les projets excluded_projects de flux.yaml sont écartés, comme pour les rapports de flux.
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import quote, urlparse

import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_paths                                  # noqa: E402
import flux_config
from yaml_strict import ErreurConfig, charger
import history_common as commun
from history_jira_messages import CATALOGS
from messages import Messages, add_language_option

WORKSPACE = lab_paths.resolve_or_exit()["content_root"]   # module partagé : variable, sinon dépôt Git du code, sinon code 78
FLUX_DIR = WORKSPACE / "Flux-Lab"
CONFIG_FILE = FLUX_DIR / "flux.yaml"

SERVICE_TROUSSEAU = "pmzilla-jira"
API_ATLASSIAN = "https://api.atlassian.com"
TIMEOUT = (10, 60)            # connexion, lecture (secondes)
MAX_TENTATIVES = 6
ATTENTE_INITIALE = 2.0        # secondes, doublées à chaque reprise
ATTENTE_MAX = 120.0
PAUSE = 0.1                   # entre deux appels
LOT_GROUPE = 100              # tickets par requête groupée
CODES_FATALS = {401, 403}     # une erreur d'accès n'a aucune raison de se réparer sur le ticket suivant
CODES_ABSENCE_API = {404, 405, 501}   # l'API groupée n'existe pas sur cette instance
ROLE_IMPORT = "pmzilla_flow"
VARIABLE_CLAUDE_CODE = "CLAUDECODE"
RECOUVREMENT = dt.timedelta(days=1)     # un ticket mis à jour depuis la dernière collecte réussie moins ce recouvrement est réinterrogé

logging.disable(logging.CRITICAL)   # aucun journal, jamais : ni requests ni urllib3
_JETON: str | None = None           # seulement pour masquer le jeton dans toute sortie


_MESSAGES = Messages(CATALOGS, "fr")


def set_language(language: str) -> None:
    """Langue des messages et des sorties (français par défaut). export_jira_api.py l'appelle aussi : un seul accès à Jira."""
    global _MESSAGES
    _MESSAGES = Messages(CATALOGS, language)


def t(key: str, **values) -> str:
    return _MESSAGES(key, **values)


def nom_segment(nom: str) -> str:
    """Nom d'un segment pour l'affichage : le nom anglais des segments par défaut en anglais, le nom du réglage sinon."""
    return flux_config.SEGMENTS.get(nom, nom) if _MESSAGES.language == "en" else nom


class ErreurSimple(Exception):
    """Erreur dont le message est sûr à afficher (rédigé ici, sans donnée de Jira)."""


class ErreurHTTP(Exception):
    """Réponse en erreur : le seul renseignement gardé est le code (0 : pas de réponse)."""

    def __init__(self, code: int):
        super().__init__(t("http_code", code=code) if code else t("network_error"))
        self.code = code


def masquer(texte: str) -> str:
    return texte.replace(_JETON, "***") if _JETON else texte


def afficher(texte: str = "") -> None:
    print(masquer(texte))


# ---------------------------------------------------------------------------
# Réglages et jeton
# ---------------------------------------------------------------------------

OPTIONS_RENOMMEES = {**flux_config.OPTIONS_COMMUNES, "--cle": "--key", "--rafraichir": "--refresh"}


def reglages() -> dict:
    """Réglages de flux.yaml, sous les noms internes (les noms anglais seuls sont acceptés, les anciens noms sont refusés : flux_config.py)."""
    brut = (charger(CONFIG_FILE.read_text(encoding="utf-8"), "flux.yaml") or {}) if CONFIG_FILE.exists() else {}
    return flux_config.to_internal(brut, "flux.yaml")


def reglages_jira(settings: dict) -> tuple[str, str, str]:
    """(site, email, mode). Le mode à droits limités est le seul : le réglage absent vaut « scopes », « classique » est refusé
    ici, donc avant la lecture du Trousseau et avant tout appel."""
    manquants = [k for k in ("jira_site", "jira_email") if not str(settings.get(k) or "").strip()]
    if manquants:
        raise ErreurSimple(t("settings_missing", file=CONFIG_FILE, names=", ".join(flux_config.TOP.get(k, k) for k in manquants)))
    site, email = (str(settings[k]).strip() for k in ("jira_site", "jira_email"))
    mode = str(settings.get("jira_jeton") or "scopes").strip()
    if mode == "classique":
        raise ErreurSimple(t("classic_refused"))
    if mode != "scopes":
        raise ErreurSimple(t("token_type_invalid"))
    verifier_url(site)
    return site.rstrip("/"), email, mode


def identifiant_cloud(settings: dict) -> str:
    """cloudId de jira_cloud_id. Jamais lu sur le site hors `test` : absent, vide ou avec des caractères de chemin, il arrête
    le script (un identifiant mal formé changerait l'adresse de la passerelle)."""
    identifiant = flux_config.cloud_id(settings)
    if not isinstance(identifiant, str) or not re.fullmatch(r"[0-9A-Za-z-]+", identifiant.strip()):
        raise ErreurSimple(t("cloud_id_not_found"))
    return identifiant.strip()


def aujourd_hui() -> dt.date:
    return dt.date.today()


def verifier_url(url: str) -> None:
    """Le jeton ne part jamais en clair vers une machine distante : https, sauf pour la machine locale."""
    adresse = urlparse(url)
    if adresse.scheme == "https" and adresse.hostname:
        return
    if adresse.scheme == "http" and adresse.hostname in ("127.0.0.1", "localhost"):
        return
    raise ErreurSimple(t("url_not_https"))


def lire_jeton() -> str:
    """Le jeton vient uniquement du Trousseau macOS. Aucune sortie de la commande n'est reprise dans un message."""
    try:
        r = subprocess.run(["security", "find-generic-password", "-s", SERVICE_TROUSSEAU, "-w"],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        raise ErreurSimple(t("token_command_failed")) from None
    jeton = r.stdout.strip() if r.returncode == 0 else ""
    if not jeton:
        raise ErreurSimple(t("token_not_found", service=SERVICE_TROUSSEAU))
    return jeton


# ---------------------------------------------------------------------------
# Appels HTTP
# ---------------------------------------------------------------------------

class Client:
    """Appels à Jira avec délais d'attente, reprises à attente croissante et respect de Retry-After."""

    def __init__(self, base: str, auth: tuple[str, str] | None = None, sleep=None):
        self.base = base.rstrip("/")
        self.auth = auth
        self.sleep = sleep or (lambda secondes: time.sleep(secondes))
        self.session = requests.Session()

    def requete(self, methode: str, chemin: str, **kwargs) -> requests.Response:
        url = self.base + chemin
        attente = ATTENTE_INITIALE
        for tentative in range(MAX_TENTATIVES):
            retry_after = ""
            try:
                r = self.session.request(methode, url, auth=self.auth, timeout=TIMEOUT, allow_redirects=False,
                                         headers={"Accept": "application/json"}, **kwargs)
                code = r.status_code
                retry_after = r.headers.get("Retry-After", "")
            except (requests.ConnectionError, requests.Timeout):
                code = 0
            if code and code != 429 and code < 500:
                return r
            if tentative == MAX_TENTATIVES - 1:
                raise ErreurHTTP(code)
            delai = attente
            if code == 429:
                try:
                    delai = float(retry_after)
                except ValueError:
                    pass
            self.sleep(min(delai, ATTENTE_MAX))
            attente = min(attente * 2, ATTENTE_MAX)
        raise ErreurHTTP(0)     # inatteignable

    def json(self, methode: str, chemin: str, **kwargs) -> dict:
        r = self.requete(methode, chemin, **kwargs)
        if r.status_code >= 400:
            raise ErreurHTTP(r.status_code)
        try:
            return r.json()
        except ValueError:
            raise ErreurSimple(t("response_unreadable")) from None


def construire_client(settings: dict) -> Client:
    """Client de la passerelle api.atlassian.com/ex/jira/<cloudId>, le cloudId venant des réglages. Les refus de réglage
    (classic, cloudId) précèdent la lecture du Trousseau ; aucun appel authentifié ne va à l'adresse du site."""
    global _JETON
    _, email, _ = reglages_jira(settings)
    cloud_id = identifiant_cloud(settings)
    verifier_url(API_ATLASSIAN)
    jeton = lire_jeton()
    _JETON = jeton
    return Client(f"{API_ATLASSIAN}/ex/jira/{cloud_id}", (email, jeton))


# ---------------------------------------------------------------------------
# Base (schéma flow) : tickets à interroger, écriture du résultat
# ---------------------------------------------------------------------------

def ouvrir_magasin():
    """Magasin de la collecte : connexion de la base sous le rôle d'import, avec son propre mot de passe (Trousseau, puis variable
    d'environnement), avant tout appel à Jira. Lève ErreurSimple avec la phrase fixe si le mot de passe manque ou si la base ne répond
    pas : jamais de mot de passe, d'adresse ni de détail de la base dans le message."""
    import db
    import history_store
    if db.lire_mot_de_passe(role=ROLE_IMPORT) is None:
        raise ErreurSimple(t("db_password_missing"))
    try:
        return history_store.MagasinHistorique(db.connect(role=ROLE_IMPORT))
    except db.ErreurBase:
        raise ErreurSimple(t("db_unreachable")) from None


def lire_donnees_de_la_base(settings: dict):
    """(tickets, historique) du rôle en lecture seule, comme les lecteurs de rapport (flow_store, import tardif : psycopg n'est chargé
    que pour la base). `tickets` : un dict par ticket (cle, projet, type, etat, resolu, equipes, ...), `historique` : {CLÉ_MAJUSCULES:
    [[date ISO, départ, arrivée], ...]} des tickets « avec historique ». Une base injoignable arrête avec le code 1."""
    import flow_store
    try:
        tickets = flow_store.lire_tickets_flux(settings)[0]
        historique = flow_store.lire_historique(settings)
    except Exception as erreur:
        if type(erreur).__name__ != "ErreurBase":
            raise
        raise ErreurSimple(str(erreur)) from None
    return tickets, historique


def types_epic_de_portefeuille(settings: dict) -> set[str]:
    """Types d'épic des réglages (en minuscules) qui sont aussi des types de niveau portefeuille : ceux que la collecte interroge
    malgré l'exclusion du portefeuille (epic-flow-report, conception D12)."""
    types, _ = commun.ensembles_exclus(settings)
    return {t.strip().casefold() for t in flux_config.epic_types(settings)} & types


def ecarter(tickets: list[dict], settings: dict) -> tuple[list[dict], int]:
    """(tickets gardés, nombre d'écartés). Les types de niveau portefeuille et les projets exclus sont écartés, avec une exception :
    les types d'épic des réglages sont gardés même de niveau portefeuille, sauf dans un projet exclu (les projets exclus l'emportent)."""
    types, projets = commun.ensembles_exclus(settings)
    epics = types_epic_de_portefeuille(settings)
    gardes = [t for t in tickets if t["projet"] not in projets and (t["type"].casefold() not in types or t["type"].casefold() in epics)]
    return gardes, len(tickets) - len(gardes)


def epics_interroges(tickets: list[dict], settings: dict) -> int | None:
    """Nombre d'épics retenus pour la collecte, ou None quand aucun type d'épic n'est de niveau portefeuille (aucune ligne alors)."""
    epics = types_epic_de_portefeuille(settings)
    return sum(1 for t in tickets if t["type"].casefold() in epics) if epics else None


def fuseau_des_reglages(settings: dict):
    """Fuseau d'export de flux.yaml (règle partagée de history_common) ; un fuseau inconnu arrête avec le message de l'export."""
    try:
        return commun.fuseau_export(settings)
    except commun.ErreurFuseau as erreur:
        raise ErreurSimple(t("timezone_invalid", name=erreur.nom, example=commun.FUSEAU_PAR_DEFAUT)) from None


def a_reinterroger(ticket: dict, derniere_collecte: dt.datetime | None) -> bool:
    """Vrai pour un ticket sans historique, non résolu, ou mis à jour depuis la dernière collecte réussie moins un jour (design D5).
    Sans collecte antérieure, un ticket avec historique et résolu n'a aucune raison d'être réinterrogé."""
    if not ticket["a_historique"] or ticket["resolu"] is None:
        return True
    maj = ticket.get("maj")
    return derniere_collecte is not None and maj is not None and maj > derniere_collecte - RECOUVREMENT


def ecarter_hors_conservation(tickets: list[dict], jours: int, fuseau: dt.tzinfo | None = None) -> tuple[list[dict], int]:
    """(tickets à collecter, nombre de tickets ignorés). Un ticket résolu depuis plus de `jours` jours est ignoré : son
    historique n'est pas demandé (horloge du design D1 : un an après la résolution, jour du fuseau d'export). Un ticket non résolu
    est gardé."""
    limite = aujourd_hui() - dt.timedelta(days=jours)
    gardes = [t for t in tickets if t.get("resolu") is None
              or (t["resolu"].astimezone(fuseau) if fuseau is not None else t["resolu"]).date() >= limite]
    return gardes, len(tickets) - len(gardes)


# ---------------------------------------------------------------------------
# Historique : seules la date, l'état de départ et l'état d'arrivée sont gardés
# ---------------------------------------------------------------------------

def etiquettes_declarees(settings: dict) -> set[str]:
    """Étiquettes déclarées de flux.yaml (declared_labels), tous rôles confondus ; vide sans bloc : aucune étiquette gardée."""
    bloc = flux_config.declared_labels(settings) or {}
    return {etiquette for role in bloc.values() for etiquette in role["labels"]}


def _champ(element: dict, identifiant: str, nom: str) -> bool:
    return element.get("fieldId") == identifiant or element.get("field") == nom


def evenements_de(historiques: list[dict], declarees: set[str] | None = None) -> tuple[list[list], list[list], list[list]]:
    """(transitions, versions, étiquettes) d'un historique. Transitions : [date, de, vers] des seuls éléments du champ status.
    Versions : [date, "add"|"remove", valeur] du champ « Fix Version » (une valeur d'origine est un retrait, une valeur
    d'arrivée un ajout). Étiquettes : mêmes événements pour le champ « labels », déduits par différence d'ensembles entre
    les textes de départ et d'arrivée (étiquettes séparées par des espaces) et limités aux étiquettes `declarees` : sans
    étiquette déclarée, aucune n'est gardée. L'auteur et tous les autres champs sont ignorés."""
    declarees = declarees or set()
    transitions, versions, etiquettes = [], [], []
    for historique in historiques or []:
        date = commun.normaliser_date(historique.get("created"))
        for element in historique.get("items") or []:
            if _champ(element, "status", "status"):
                transitions.append([date, element.get("fromString"), element.get("toString")])
            elif _champ(element, "fixVersions", "Fix Version"):
                if element.get("fromString"):
                    versions.append([date, "remove", element["fromString"]])
                if element.get("toString"):
                    versions.append([date, "add", element["toString"]])
            elif declarees and _champ(element, "labels", "labels"):
                avant, apres = (str(element.get(c) or "").split() for c in ("fromString", "toString"))
                etiquettes += [[date, "remove", e] for e in avant if e not in apres and e in declarees]
                etiquettes += [[date, "add", e] for e in apres if e not in avant and e in declarees]
    return commun.trier(transitions), commun.trier_evenements(versions), commun.trier_evenements(etiquettes)


def historiques_ticket(client: Client, cle: str) -> list[dict]:
    """Historique d'un ticket, page par page (API de base, présente sur toute instance)."""
    historiques, debut = [], 0
    while True:
        page = client.json("GET", f"/rest/api/3/issue/{quote(cle)}/changelog",
                           params={"startAt": debut, "maxResults": 100})
        valeurs = page.get("values") or []
        historiques += valeurs
        debut += len(valeurs)
        # une page vide termine toujours ; sans isLast ni total, on continue jusqu'à la page vide plutôt que de
        # s'arrêter après la première page
        if not valeurs or page.get("isLast") is True:
            return historiques
        total = page.get("total")
        if page.get("isLast") is None and isinstance(total, int) and debut >= total:
            return historiques


def historiques_groupes(client: Client, cles: list[str]) -> tuple[dict[str, list[dict]], list[str]]:
    """Historiques d'un lot de tickets avec l'API groupée. Retourne les historiques par clé (en majuscules) et les clés que
    Jira ne renvoie pas (supprimées, sans accès). La réponse groupée ne porte que l'identifiant : un appel de
    recherche, limité aux clés, fait la correspondance."""
    jql = "key in (" + ",".join(cles) + ")"
    id_vers_cle: dict[str, str] = {}
    jeton_page = None
    while True:
        corps = {"jql": jql, "fields": ["key"], "maxResults": len(cles)}
        if jeton_page:
            corps["nextPageToken"] = jeton_page
        reponse = client.json("POST", "/rest/api/3/search/jql", json=corps)
        for ticket in reponse.get("issues") or []:
            id_vers_cle[str(ticket.get("id"))] = ticket.get("key")
        suivant = reponse.get("nextPageToken")
        if not suivant or suivant == jeton_page:
            break
        jeton_page = suivant
    resultat: dict[str, list[dict]] = {str(cle).upper(): [] for cle in id_vers_cle.values()}
    if id_vers_cle:
        jeton_page = None
        while True:
            corps = {"issueIdsOrKeys": list(id_vers_cle), "fieldIds": ["status", "labels", "fixVersions"], "maxResults": 1000}
            if jeton_page:
                corps["nextPageToken"] = jeton_page
            reponse = client.json("POST", "/rest/api/3/changelog/bulkfetch", json=corps)
            for fiche in reponse.get("issueChangeLogs") or []:
                cle = id_vers_cle.get(str(fiche.get("issueId")))
                if cle:
                    resultat[str(cle).upper()] += fiche.get("changeHistories") or []
            suivant = reponse.get("nextPageToken")
            if not suivant or suivant == jeton_page:
                break
            jeton_page = suivant
    return resultat, [c for c in cles if c.upper() not in resultat]


def valeurs_courantes(client: Client, cles: list[str], avec_etiquettes: bool) -> dict[str, dict]:
    """Versions correctives et étiquettes courantes d'un lot de tickets (database-only, D5 : l'export ne les demande plus), par clé en
    majuscules : {"versions": [noms], "etiquettes": [étiquettes]}. Les étiquettes ne sont demandées qu'avec des étiquettes déclarées ;
    l'appelant ne garde que les déclarées. Un ticket que Jira ne renvoie pas n'a pas d'entrée."""
    jql = "key in (" + ",".join(cles) + ")"
    champs = ["fixVersions"] + (["labels"] if avec_etiquettes else [])
    valeurs: dict[str, dict] = {}
    jeton_page = None
    while True:
        corps = {"jql": jql, "fields": champs, "maxResults": len(cles)}
        if jeton_page:
            corps["nextPageToken"] = jeton_page
        reponse = client.json("POST", "/rest/api/3/search/jql", json=corps)
        for ticket in reponse.get("issues") or []:
            fields = ticket.get("fields") or {}
            versions = [v.get("name") for v in fields.get("fixVersions") or [] if isinstance(v, dict)]
            etiquettes = [e for e in fields.get("labels") or [] if isinstance(e, str)]
            valeurs[str(ticket.get("key")).upper()] = {
                "versions": list(dict.fromkeys(n.strip() for n in versions if isinstance(n, str) and n.strip())),
                "etiquettes": list(dict.fromkeys(e.strip() for e in etiquettes if e.strip()))}
        suivant = reponse.get("nextPageToken")
        if not suivant or suivant == jeton_page:
            return valeurs
        jeton_page = suivant


# ---------------------------------------------------------------------------
# Commandes
# ---------------------------------------------------------------------------

CLE_SONDE = "PROJ-1"        # clé de repli de la sonde de l'historique quand la recherche ne rend aucun ticket


def sonder(client: Client, methode: str, chemin: str, **kwargs) -> int:
    """Code HTTP d'une requête de sonde (0 : pas de réponse). Rien de la réponse n'est lu."""
    try:
        return client.requete(methode, chemin, **kwargs).status_code
    except ErreurHTTP as erreur:
        return erreur.code


def cmd_test(args: argparse.Namespace) -> None:
    """Connexion, puis une requête de lecture par ressource (recherche, historique, champs), chacune limitée à un résultat,
    puis les lignes d'expiration du jeton (date des réglages, jamais lue dans le jeton ni dans Jira)."""
    settings = reglages()
    site, _, _ = reglages_jira(settings)
    cloud_id = identifiant_cloud(settings)
    echeance, delai = flux_config.token_expiry(settings)      # date illisible : refusée par flux_config, avant tout appel
    # seul `test` lit le cloudId du site, sans authentification : un autre identifiant enverrait les appels à un autre tenant
    if str(Client(site).json("GET", "/_edge/tenant_info").get("cloudId") or "") != cloud_id:
        raise ErreurSimple(t("cloud_id_mismatch"))
    client = construire_client(settings)
    ticket = None
    resultats: list[tuple[str, int]] = []
    r = client.requete("GET", "/rest/api/3/search/jql", params={"jql": "created >= -1d", "maxResults": 1, "fields": "key"})
    if r.status_code == 401:       # identifiants refusés : le code seul, sans autre appel
        afficher(t("http_code", code=401))
        sys.exit(1)
    resultats.append(("search", r.status_code))
    if r.status_code == 200:
        try:
            ticket = ((r.json().get("issues") or [{}])[0]).get("key")
        except (ValueError, AttributeError, IndexError):
            ticket = None
    # la clé du ticket ne sert qu'à l'appel : elle n'est jamais affichée ; sans ticket, un 404 sur la clé de repli prouve
    # que la ressource répond (un scope manquant donne 401 ou 403)
    code = sonder(client, "GET", f"/rest/api/3/issue/{quote(str(ticket or CLE_SONDE))}/changelog", params={"maxResults": 1})
    resultats.append(("history", 200 if code == 404 and not ticket else code))
    resultats.append(("fields", sonder(client, "GET", "/rest/api/3/field/search", params={"maxResults": 1})))
    afficher(t("connection_ok"))
    for ressource, code in resultats:
        statut = t("access_ok") if code == 200 else (code or t("network_short"))
        afficher(t("access_line", resource=ressource, status=statut))
    refus = any(code != 200 for _, code in resultats)
    if echeance is None:
        afficher(t("token_expiry_missing"))
    elif echeance < aujourd_hui():
        afficher(t("token_expired"))
    elif (echeance - aujourd_hui()).days <= delai:
        afficher(t("token_expires_soon", days=(echeance - aujourd_hui()).days))
    if refus:
        sys.exit(1)


def refuser_fichier_d_export(args: argparse.Namespace) -> None:
    """Un fichier d'export donné est refusé (design D6) : code 2, avant toute lecture, connexion et appel. Rien de son nom n'est dit."""
    if args.export:
        afficher(t("error_line", message=t("export_files_retired")))
        sys.exit(2)


def selectionner(args: argparse.Namespace, tickets: list[dict], settings: dict) -> tuple[list[dict], int, int, int]:
    """Tickets de la base après écartement des types et projets exclus et filtre d'équipe : (tickets, lus,
    écartés, hors équipe)."""
    lus = len(tickets)
    tickets, ecartes = ecarter(tickets, settings)
    hors_equipe = 0
    if args.equipe:
        if not any(t["equipes"] for t in tickets):
            raise ErreurSimple(t("team_no_column"))
        voulue = args.equipe.strip().casefold()
        avant = len(tickets)
        tickets = [t for t in tickets if voulue in {e.casefold() for e in t["equipes"]}]
        hors_equipe = avant - len(tickets)
        if not tickets:
            raise ErreurSimple(t("team_no_match"))
    return tickets, lus, ecartes, hors_equipe


def resultat_pret(ticket: dict, brut: dict, declarees: set[str], fuseau) -> dict:
    """Résultat d'un ticket interrogé, dans la forme du magasin : transitions (instants avec fuseau), périodes d'étiquettes déclarées
    (None quand les étiquettes ne sont pas suivies, ou que Jira n'a pas rendu les valeurs courantes) et de versions."""
    transitions = []
    for date, depart, arrivee in brut["transitions"]:
        instant = commun.instant_de_transition(date, fuseau)
        if instant is not None:                     # une date illisible est écartée, comme pour les événements de période
            transitions.append((instant, depart, arrivee))
    courantes = brut["courantes"]
    etiquettes = versions = None
    if courantes is not None:
        cree = ticket["cree"]
        versions = commun.construire_periodes(brut["versions"], courantes["versions"], cree, fuseau)
        if declarees:
            etiquettes = commun.construire_periodes(brut["etiquettes"], [e for e in courantes["etiquettes"] if e in declarees],
                                                    cree, fuseau, declarees)
    return {"transitions": transitions, "etiquettes": etiquettes, "versions": versions}


def cmd_collect(args: argparse.Namespace) -> None:
    refuser_fichier_d_export(args)
    settings = reglages()
    jours = flux_config.retention_days(settings)       # au-delà d'un an : refusé ici, avant toute lecture et tout appel
    declarees = etiquettes_declarees(settings)
    fuseau = fuseau_des_reglages(settings)
    magasin = ouvrir_magasin()          # mot de passe absent ou base injoignable : arrêt avant tout appel à Jira
    try:
        collecter(args, settings, jours, declarees, fuseau, magasin)
    finally:
        magasin.fermer()


def collecter(args: argparse.Namespace, settings: dict, jours: int, declarees: set[str], fuseau, magasin) -> None:
    tous = magasin.tickets()
    if not tous:
        raise ErreurSimple(t("no_ticket_in_db"))
    derniere = magasin.derniere_collecte()
    tickets, lus, ecartes, hors_equipe = selectionner(args, tous, settings)
    tickets, hors_conservation = ecarter_hors_conservation(tickets, jours, fuseau)
    limite_404 = flux_config.history_not_found_limit(settings)
    compteurs, disparus = magasin.introuvables()
    ignores_disparus = 0
    if disparus and not args.rafraichir:          # un ticket disparu n'est plus interrogé ; --refresh le réinterroge
        avant = len(tickets)
        tickets = [ticket for ticket in tickets if ticket["cle"] not in disparus]
        ignores_disparus = avant - len(tickets)
    reinterroges = 0
    if args.rafraichir:
        deja, a_interroger = [], list(tickets)
    else:
        deja, a_interroger = [], []
        for ticket in tickets:
            if a_reinterroger(ticket, derniere):
                a_interroger.append(ticket)
                reinterroges += bool(ticket["a_historique"] and ticket["resolu"] is not None)     # terminé et mis à jour
            else:
                deja.append(ticket)
    epics = epics_interroges(tickets, settings)
    if epics is not None:
        afficher(t("collect_epics", count=epics))
    afficher(t("collect_read_team", read=lus, discarded=ecartes, off_team=hors_equipe) if args.equipe
             else t("collect_read", read=lus, discarded=ecartes))
    afficher(t("collect_refresh", todo=len(a_interroger)) if args.rafraichir
             else t("collect_already", done=len(deja), todo=len(a_interroger)))
    if not args.rafraichir and any(ticket.get("maj") for ticket in tickets):
        afficher(t("collect_updated", count=reinterroges))
    afficher(t("past_retention", skipped=hors_conservation))
    if ignores_disparus:
        afficher(t("collect_gone_skipped", count=ignores_disparus))
    resultats: dict[str, dict] = {}
    if not a_interroger:
        ajoutees, periodes = magasin.enregistrer(resultats, 0)          # aucun appel à Jira : seul le passage est écrit
        afficher(t("history_written", transitions=ajoutees, periods=periodes))
        return

    client = construire_client(settings)
    groupe: bool | None = None            # None : pas encore essayé
    traites, nouvelles_transitions, erreurs, arret = 0, 0, Counter(), None
    bruts: dict[str, tuple[dict, dict]] = {}          # clé -> (ticket, résultat brut de Jira) ; rien n'est écrit avant la fin
    introuvables: list[str] = []          # tickets que Jira ne trouve pas (404) à ce passage : seuls ceux-là comptent, pas les erreurs passagères

    def noter(ticket: dict, historiques: list[dict], courantes: dict | None) -> None:
        nonlocal traites, nouvelles_transitions
        transitions, versions, etiquettes = evenements_de(historiques, declarees)
        bruts[ticket["cle"]] = (ticket, {"transitions": transitions, "versions": versions, "etiquettes": etiquettes,
                                         "courantes": courantes})
        traites += 1
        nouvelles_transitions += len(transitions)

    try:
        for debut in range(0, len(a_interroger), LOT_GROUPE):
            lot = a_interroger[debut:debut + LOT_GROUPE]
            try:
                courantes = valeurs_courantes(client, [t["cle"] for t in lot], bool(declarees))
            except ErreurHTTP as erreur:
                if erreur.code in CODES_FATALS:
                    raise
                erreurs[erreur.code] += len(lot)
                continue
            restants = lot
            if groupe is not False:
                try:
                    historiques, absents = historiques_groupes(client, [t["cle"] for t in lot])
                except ErreurHTTP as erreur:
                    if erreur.code in CODES_ABSENCE_API:
                        groupe = False
                    elif erreur.code in CODES_FATALS:
                        raise
                    else:
                        erreurs[erreur.code] += len(lot)
                        restants = []
                else:
                    groupe = True
                    for ticket in lot:
                        if ticket["cle"].upper() in historiques:
                            noter(ticket, historiques[ticket["cle"].upper()], courantes.get(ticket["cle"].upper()))
                        else:
                            introuvables.append(ticket["cle"])          # Jira ne le renvoie pas : un 404, pas une erreur passagère
                    restants = []
            for ticket in restants:
                try:
                    noter(ticket, historiques_ticket(client, ticket["cle"]), courantes.get(ticket["cle"].upper()))
                except ErreurHTTP as erreur:
                    if erreur.code in CODES_FATALS:
                        raise
                    if erreur.code == 404:
                        introuvables.append(ticket["cle"])
                    else:
                        erreurs[erreur.code] += 1
                time.sleep(PAUSE)
            time.sleep(PAUSE)
    except ErreurHTTP as erreur:
        arret = erreur.code

    mode = t("mode_bulk") if groupe else t("mode_single")
    detail = (" (" + ", ".join(t("error_detail_item", code=c or t("network_short"), count=n)
                               for c, n in sorted(erreurs.items())) + ")") if erreurs else ""
    afficher(t("collect_summary", mode=mode, processed=traites, transitions=nouvelles_transitions,
               errors=sum(erreurs.values()), detail=detail))
    if introuvables:
        afficher(t("collect_not_found", count=len(introuvables)))
    if arret is not None:         # erreur d'accès : rien n'est écrit (une seule transaction, annulée)
        afficher(t("collect_stopped", code=arret))
        sys.exit(1)
    resultats = {cle: resultat_pret(ticket, brut, declarees, fuseau) for cle, (ticket, brut) in bruts.items()}
    # suivi des 404 : un ticket trouvé repart de zéro ; un 404 de plus compte ; une erreur passagère ne touche à rien ; à `limite_404`
    # passages consécutifs, le ticket est marqué disparu et n'est plus interrogé
    suivi: dict[str, tuple[int, bool]] = {}
    for cle in bruts:
        if compteurs.get(cle) or cle in disparus:
            suivi[cle] = (0, False)
    nouveaux_disparus = 0
    for cle in introuvables:
        compteur = compteurs.get(cle, 0) + 1
        suivi[cle] = (compteur, compteur >= limite_404)
        nouveaux_disparus += compteur >= limite_404 and cle not in disparus
    retrouves = sum(1 for cle in bruts if cle in disparus)
    # le passage « history » est enregistré même avec des erreurs, avec le nombre d'erreurs passagères et de 404 : seul un passage sans
    # erreur passagère avance la dernière collecte réussie, donc un ticket en erreur passagère reste à interroger ; les 404 ne bloquent rien
    ajoutees, periodes = magasin.enregistrer(resultats, sum(erreurs.values()), suivi, len(introuvables))
    afficher(t("history_written", transitions=ajoutees, periods=periodes))
    if nouveaux_disparus:
        afficher(t("collect_gone_marked", count=nouveaux_disparus))
    if retrouves:
        afficher(t("collect_gone_found", count=retrouves))
    if args.strict and erreurs:          # option stricte (orchestrateur du suivi mensuel) : les résultats sont écrits comme sans l'option
        afficher(t("collect_strict"))
        sys.exit(3)


def tranches() -> tuple[str, ...]:
    return ("0", "1", "2-4", "5-9", t("bucket_10_plus"))


def tranche(n: int) -> str:
    return "0" if n == 0 else "1" if n == 1 else "2-4" if n <= 4 else "5-9" if n <= 9 else t("bucket_10_plus")


def tranches_texte(repartition: Counter) -> str:
    return t("list_separator").join(t("bucket_item", bucket=c, count=repartition[c]) for c in tranches())


def afficher_ticket(cle: str, historique: dict[str, list], tickets: list[dict]) -> None:
    """Suite des états d'un ticket avec leurs dates, sans auteur : à comparer à l'onglet Historique de Jira.
    Terminal seulement (la clé y figure). `historique` : transitions par clé en majuscules, lues dans la base."""
    transitions = historique.get(cle.upper())
    if transitions is None:
        raise ErreurSimple(t("ticket_not_in_db"))
    afficher(t("ticket_transitions", ticket=cle, count=len(transitions)))
    inconnu = t("unknown_state")
    if transitions:
        afficher(t("ticket_start", state=transitions[0][1] or inconnu))
    for date, de, vers in transitions:
        lisible = str(date if date is not None else "?").replace("T", " ").replace(".000", "")
        afficher(f"  {lisible:<24}  {de or inconnu}  ->  {vers or inconnu}")
    ligne = next((x for x in tickets if x["cle"].upper() == cle.upper()), None)
    if ligne is not None and ligne.get("etat") is not None:
        afficher(t("ticket_stored_state", state=ligne["etat"]))


def cmd_check(args: argparse.Namespace) -> None:
    """Compare, pour chaque ticket avec historique, le dernier état de l'historique à l'état stocké (base, rôle en lecture seule). Aucune
    clé, aucun nom : seulement des effectifs (sauf avec --key, qui n'affiche que ce ticket, dans le Terminal)."""
    if VARIABLE_CLAUDE_CODE in os.environ:          # utilisateur seul : refus avant toute lecture de réglage (design D12)
        afficher(t("session_refused"))
        sys.exit(3)
    refuser_fichier_d_export(args)
    if args.dormants is not None:
        raise ErreurSimple(t("dormants_removed"))
    settings = reglages()
    base, historique = lire_donnees_de_la_base(settings)
    if args.cle:
        afficher_ticket(args.cle, historique, base)
        return
    if not historique:
        raise ErreurSimple(t("no_history_in_db"))
    tickets, lus, ecartes, hors_equipe = selectionner(args, base, settings)
    coherents = incoherents = sans_transition = absents = livres = livres_sans = 0
    livres_fiches: list[list] = []
    repartition = Counter()
    for tk in tickets:
        transitions = historique.get(tk["cle"].upper())      # même appariement des clés que flux_jira.py
        if transitions is None:
            absents += 1
            continue
        repartition[tranche(len(transitions))] += 1
        if tk["resolu"]:
            livres += 1
            livres_sans += not transitions
            livres_fiches.append(transitions)
        if not transitions:
            sans_transition += 1
        elif (transitions[-1][2] or "").strip().casefold() == (tk["etat"] or "").strip().casefold():
            coherents += 1
        else:
            incoherents += 1
    afficher(t("check_retained", retained=len(tickets), missing=absents))
    afficher(t("check_consistency", consistent=coherents, inconsistent=incoherents, not_comparable=sans_transition))
    afficher(t("check_buckets", buckets=tranches_texte(repartition)))
    afficher(t("check_delivered", delivered=livres, delivered_without=livres_sans))
    afficher_livres(livres_fiches, settings)


def afficher_livres(fiches: list[list], settings: dict) -> None:
    """Lecture de l'historique des tickets livrés pour repérer un historique tronqué : état de départ de la première
    transition connue (attendu : l'état initial du workflow), nombre de transitions, segments traversés."""
    if not fiches:
        return
    segment_de, calcules = commun.table_segments(settings)
    departs, nombres, segments, etats = Counter(), Counter(), Counter(), Counter()
    inconnu, sans_segment = t("unknown_state"), t("no_segment")
    for transitions in fiches:
        nombres[tranche(len(transitions))] += 1
        if not transitions:
            continue
        departs[transitions[0][1] or inconnu] += 1
        vus = {transitions[0][1]} | {t[2] for t in transitions}
        etats.update(sorted(e for e in vus if e))      # ordre fixe : à effectif égal, l'ordre ne dépend pas du hasard des ensembles
        traverses = commun.segments_traverses(transitions, segment_de, calcules)
        segments.update(traverses)
        if not traverses:
            segments[sans_segment] += 1
    afficher("")
    afficher(t("delivered_header", count=len(fiches)))
    afficher(t("delivered_start_states",
               states=t("list_separator").join(f"{e} {n}" for e, n in departs.most_common()) or t("delivered_none")))
    afficher(t("delivered_buckets", buckets=tranches_texte(nombres)))
    afficher(t("delivered_segments", segments=t("list_separator").join(
        f"{s if s == sans_segment else nom_segment(s)} {segments[s]}" for s in calcules + [sans_segment] if segments[s])))
    afficher(t("delivered_states", states=t("list_separator").join(f"{e} {n}" for e, n in etats.most_common(20))
                                      or t("delivered_none")))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Historique des états des tickets Jira (collecte, étape 1)")
    commandes = parser.add_subparsers(dest="commande", required=True)
    test = commandes.add_parser("test", help="vérifie la connexion (« connexion OK » ou le code HTTP)")
    collecte = commandes.add_parser("collect", help="collecte l'historique des tickets de la base et l'écrit dans la base")
    collecte.add_argument("export", nargs="*", help=argparse.SUPPRESS)          # un fichier d'export est refusé (code 2)
    collecte.add_argument("--team", dest="equipe", help="ne collecter que cette équipe (nom donné seulement ici)")
    collecte.add_argument("--refresh", dest="rafraichir", action="store_true",
                          help="réinterroger tous les tickets retenus, même déjà collectés")
    collecte.add_argument("--strict", action="store_true",
                          help="erreurs de collecte (hors accès refusé) : rapport habituel puis sortie avec le code 3")
    controle = commandes.add_parser("check", help="compare l'historique stocké à l'état stocké des tickets (effectifs seulement)")
    controle.add_argument("export", nargs="*", help=argparse.SUPPRESS)          # un fichier d'export est refusé (code 2)
    controle.add_argument("--dormants", nargs="?", const="", default=None, help=argparse.SUPPRESS)   # supprimée : refusée avec un message
    controle.add_argument("--key", dest="cle", help="affiche la suite des états de ce ticket, avec leurs dates (Terminal seulement)")
    controle.add_argument("--team", dest="equipe", help="ne contrôler que cette équipe (nom donné seulement ici)")
    for sous_parseur in (test, collecte, controle):
        add_language_option(sous_parseur)
    args = parser.parse_args(flux_config.refuse_old_options(sys.argv[1:] if argv is None else argv, OPTIONS_RENOMMEES))
    set_language(args.language)
    try:
        {"test": cmd_test, "collect": cmd_collect, "check": cmd_check}[args.commande](args)
    except ErreurConfig as erreur:       # avant SystemExit, dont elle hérite : le message nomme le réglage, jamais sa valeur
        afficher(t("error_line", message=erreur))
        sys.exit(1)
    except SystemExit:
        raise
    except ErreurHTTP as erreur:
        afficher(str(erreur))
        sys.exit(1)
    except ErreurSimple as erreur:
        afficher(t("error_line", message=erreur))
        sys.exit(1)
    except Exception as erreur:       # aucun détail : un message de bibliothèque pourrait citer une adresse
        afficher(t("unexpected_error", name=type(erreur).__name__))
        sys.exit(1)


if __name__ == "__main__":
    main()
