# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "requests"]
# ///
"""
PMZilla Lab : collecte de l'historique des états des tickets Jira (étape 1 de la mesure du temps par état).

Seul le champ « status » est lu dans l'historique de chaque ticket : la date de la transition, l'état de
départ et l'état d'arrivée. L'auteur et tous les autres champs sont écartés dès la lecture de la réponse :
ils ne sont ni gardés, ni écrits, ni affichés. Les chiffres qui en sortiront sont agrégés par équipe, sans
aucune donnée individuelle.

    uv run tools/history_jira.py test
        Vérifie la connexion. N'affiche que « connexion OK » ou le code HTTP, jamais un nom ni une adresse.

    uv run tools/history_jira.py collect <export.csv>... [--team <nom>] [--refresh]
        Lit les clés des exports (en mémoire seulement), puis récupère l'historique du champ status de chacune.
        Utilise l'API de récupération groupée des historiques si l'instance l'offre, sinon l'historique
        ticket par ticket. Délais d'attente, reprises avec attente croissante, Retry-After respecté (429).
        Cache local dans Flux-Lab/historique/ (hors Git, illisible par Claude Code), incrémental : une relance
        ne réinterroge que les tickets non terminés ou absents du cache. --team filtre l'export sur une
        équipe (le nom n'est donné qu'en argument) : validation sur une équipe avant toute la série.
        Sortie : nombre de tickets traités, de transitions et d'erreurs, jamais une clé ni un nom.
        --refresh réinterroge tous les tickets retenus, en ignorant le cache.

    uv run tools/history_jira.py check <export.csv>... [--team <nom>] [--key <clé>]
        Ne contacte pas Jira. Compare, pour chaque ticket du cache, le dernier état de l'historique à la colonne
        Status de l'export. Sortie : effectifs seulement (cohérents, incohérents, non comparables sans transition,
        transitions par ticket en tranches 0, 1, 2-4, 5-9, 10 et plus, tickets livrés sans transition), puis pour
        les tickets livrés : état de départ de la première transition connue, transitions par ticket, segments
        traversés et états traversés (un historique tronqué au début se voit à un état de départ qui n'est pas
        l'état initial du workflow). --key <clé> affiche seulement la suite des états de ce ticket, avec leurs
        dates et sans auteur, pour la comparer à l'onglet Historique de Jira : Terminal seulement, la clé y figure.
        L'ancienne option --dormants (export CSV des dormants) est refusée : les dormants se déduisent de l'historique
        (flux_jira.py --dormant-from-history).

Réglages (Flux-Lab/flux.yaml) : jira_site (https://<site>.atlassian.net), jira_email, jira_token_type (« scoped »
pour un jeton à droits limités, « classic » sinon). Un jeton « scoped » passe par
https://api.atlassian.com/ex/jira/<cloudId>, le cloudId étant lu sur <site>/_edge/tenant_info.

Le jeton est lu uniquement dans le Trousseau macOS (security find-generic-password -s pmzilla-jira -w). Il
n'est jamais affiché, journalisé, écrit dans un fichier ni inclus dans un message d'erreur. Les types
portfolio_types et les projets excluded_projects de flux.yaml sont écartés, comme pour les rapports de flux.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
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
import flux_config
from yaml_strict import charger
import history_common as commun
from history_jira_messages import CATALOGS
from messages import Messages, add_language_option

WORKSPACE = Path(os.environ.get("PMZILLA_LAB_WORKSPACE", "~/PMZilla-Lab/workspace")).expanduser()
FLUX_DIR = WORKSPACE / "Flux-Lab"
CONFIG_FILE = FLUX_DIR / "flux.yaml"
CACHE_DIR = FLUX_DIR / "historique"
CACHE_FILE = CACHE_DIR / "transitions.json"

SERVICE_TROUSSEAU = "pmzilla-jira"
API_ATLASSIAN = "https://api.atlassian.com"
TIMEOUT = (10, 60)            # connexion, lecture (secondes)
MAX_TENTATIVES = 6
ATTENTE_INITIALE = 2.0        # secondes, doublées à chaque reprise
ATTENTE_MAX = 120.0
PAUSE = 0.1                   # entre deux appels
LOT_GROUPE = 100              # tickets par requête groupée
SAUVEGARDE_TOUTES = 200       # tickets traités entre deux écritures du cache
CODES_FATALS = {401, 403}     # une erreur d'accès n'a aucune raison de se réparer sur le ticket suivant
CODES_ABSENCE_API = {404, 405, 501}   # l'API groupée n'existe pas sur cette instance

COLONNES = {      # les en-têtes des CSV de export_jira_api.py
    "cle": ["Issue key"],
    "type": ["Issue Type"],
    "resolu": ["Resolved"],
    "cree": ["Created"],
    "etat": ["Status"],
    "equipe": ["Team"],
}

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
    manquants = [k for k in ("jira_site", "jira_email", "jira_jeton") if not str(settings.get(k) or "").strip()]
    if manquants:
        raise ErreurSimple(t("settings_missing", file=CONFIG_FILE, names=", ".join(flux_config.TOP.get(k, k) for k in manquants)))
    site, email, mode = (str(settings[k]).strip() for k in ("jira_site", "jira_email", "jira_jeton"))
    if mode not in ("scopes", "classique"):
        raise ErreurSimple(t("token_type_invalid"))
    verifier_url(site)
    return site.rstrip("/"), email, mode


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
    global _JETON
    site, email, mode = reglages_jira(settings)
    jeton = lire_jeton()
    _JETON = jeton
    if mode == "scopes":
        # le cloudId se lit sur le site, sans authentification ; les appels passent par api.atlassian.com
        infos = Client(site).json("GET", "/_edge/tenant_info")
        cloud_id = str(infos.get("cloudId") or "")
        if not re.fullmatch(r"[0-9A-Za-z-]+", cloud_id):
            raise ErreurSimple(t("cloud_id_not_found"))
        verifier_url(API_ATLASSIAN)
        return Client(f"{API_ATLASSIAN}/ex/jira/{cloud_id}", (email, jeton))
    return Client(site, (email, jeton))


# ---------------------------------------------------------------------------
# Export, cache
# ---------------------------------------------------------------------------

def lire_exports(chemins: list[str], settings: dict) -> list[dict]:
    """Clés, type, équipe et indicateur « terminé » (date de résolution présente). Rien d'autre n'est gardé."""
    colonnes = {**COLONNES, **(settings.get("colonnes") or {})}
    par_cle: dict[str, dict] = {}
    for chemin in chemins:
        with Path(chemin).expanduser().open(encoding="utf-8-sig", newline="") as f:
            lecteur = csv.reader(f)
            entete = next(lecteur)
            normalises = [h.strip().casefold() for h in entete]

            def position(champ: str) -> int | None:
                trouve = next((normalises.index(n.strip().casefold()) for n in colonnes.get(champ, [])
                               if n.strip().casefold() in normalises), None)
                if trouve is None and champ == "equipe":
                    trouve = next((i for i, h in enumerate(normalises) if "team" in h and h.endswith("(label)")),
                                  next((i for i, h in enumerate(normalises) if "team" in h), None))
                return trouve
            idx = {champ: position(champ) for champ in COLONNES}
            # un champ à plusieurs valeurs s'exporte parfois en plusieurs colonnes de même nom
            colonnes_equipe = ([i for i, h in enumerate(normalises) if h == normalises[idx["equipe"]]]
                               if idx["equipe"] is not None else [])
            separateur = settings.get("separateur_equipes") or ";"
            if idx["cle"] is None:
                raise ErreurSimple(t("key_column_not_found"))
            for ligne in lecteur:
                def cellule(champ: str) -> str:
                    p = idx[champ]
                    return ligne[p].strip() if p is not None and p < len(ligne) else ""
                cle = cellule("cle")
                if not cle:
                    continue
                equipes = []
                for p in colonnes_equipe:
                    for valeur in (ligne[p].split(separateur) if p < len(ligne) else []):
                        if valeur.strip() and valeur.strip() not in equipes:
                            equipes.append(valeur.strip())
                par_cle[cle.upper()] = {"equipes": equipes, "cle": cle, "projet": cle.rsplit("-", 1)[0].upper() if "-" in cle else "",
                                        "type": cellule("type"), "termine": bool(cellule("resolu")),
                                        "etat": cellule("etat") if idx["etat"] is not None else None,
                                        "cree": commun.parse_jour(cellule("cree")),
                                        "equipe": cellule("equipe") if idx["equipe"] is not None else None}
    return list(par_cle.values())


def ecarter(tickets: list[dict], settings: dict) -> tuple[list[dict], int]:
    types, projets = commun.ensembles_exclus(settings)
    gardes = [t for t in tickets if t["type"].casefold() not in types and t["projet"] not in projets]
    return gardes, len(tickets) - len(gardes)


def charger_cache() -> dict:
    if not CACHE_FILE.exists():
        return {}
    try:
        return commun.lire_cache(CACHE_FILE)
    except commun.CacheIllisible:
        raise ErreurSimple(t("cache_unreadable")) from None


def sauver_cache(cache: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CACHE_DIR, 0o700)
    temporaire = CACHE_FILE.with_suffix(".tmp")
    temporaire.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.chmod(temporaire, 0o600)
    os.replace(temporaire, CACHE_FILE)


# ---------------------------------------------------------------------------
# Historique : seules la date, l'état de départ et l'état d'arrivée sont gardés
# ---------------------------------------------------------------------------

def transitions_de(historiques: list[dict]) -> list[list]:
    """Extrait [date, de, vers] des seuls éléments du champ status. L'auteur et les autres champs sont ignorés."""
    sortie = []
    for historique in historiques or []:
        date = commun.normaliser_date(historique.get("created"))
        for element in historique.get("items") or []:
            if element.get("fieldId") == "status" or element.get("field") == "status":
                sortie.append([date, element.get("fromString"), element.get("toString")])
    return sorted(sortie, key=lambda t: commun.instant(t[0]))      # tri stable : à instant égal, l'ordre de l'API est gardé


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
            corps = {"issueIdsOrKeys": list(id_vers_cle), "fieldIds": ["status"], "maxResults": 1000}
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


# ---------------------------------------------------------------------------
# Commandes
# ---------------------------------------------------------------------------

def cmd_test(args: argparse.Namespace) -> None:
    client = construire_client(reglages())
    r = client.requete("GET", "/rest/api/3/search/jql",
                       params={"jql": "created >= -1d", "maxResults": 1, "fields": "key"})
    if r.status_code == 200:
        afficher(t("connection_ok"))
        return
    afficher(t("http_code", code=r.status_code))
    sys.exit(1)


def selectionner(args: argparse.Namespace, settings: dict) -> tuple[list[dict], int, int, int]:
    """Tickets de l'export après écartement des types et projets exclus et filtre d'équipe : (tickets, lus,
    écartés, hors équipe)."""
    tickets = lire_exports(args.export, settings)
    lus = len(tickets)
    tickets, ecartes = ecarter(tickets, settings)
    hors_equipe = 0
    if args.equipe:
        if not any(t["equipe"] is not None for t in tickets):
            raise ErreurSimple(t("team_no_column"))
        voulue = args.equipe.strip().casefold()
        avant = len(tickets)
        tickets = [t for t in tickets if voulue in {e.casefold() for e in t["equipes"]}]
        hors_equipe = avant - len(tickets)
        if not tickets:
            raise ErreurSimple(t("team_no_match"))
    return tickets, lus, ecartes, hors_equipe


def cmd_collect(args: argparse.Namespace) -> None:
    settings = reglages()
    tickets, lus, ecartes, hors_equipe = selectionner(args, settings)
    cache = charger_cache()
    if args.rafraichir:
        en_cache, a_interroger = [], list(tickets)
    else:
        en_cache = [t for t in tickets if cache.get(t["cle"], {}).get("termine")]
        a_interroger = [t for t in tickets if not cache.get(t["cle"], {}).get("termine")]
    afficher(t("collect_read_team", read=lus, discarded=ecartes, off_team=hors_equipe) if args.equipe
             else t("collect_read", read=lus, discarded=ecartes))
    afficher(t("collect_cache_ignored", todo=len(a_interroger)) if args.rafraichir
             else t("collect_cached", cached=len(en_cache), todo=len(a_interroger)))
    if not a_interroger:
        return

    client = construire_client(settings)
    groupe: bool | None = None            # None : pas encore essayé
    traites, nouvelles_transitions, erreurs = 0, 0, Counter()
    derniere_sauvegarde, arret = 0, None

    def enregistrer(ticket: dict, historiques: list[dict]) -> None:
        nonlocal traites, nouvelles_transitions
        transitions = transitions_de(historiques)
        cache[ticket["cle"]] = {"termine": ticket["termine"], "transitions": transitions}
        traites += 1
        nouvelles_transitions += len(transitions)

    try:
        for debut in range(0, len(a_interroger), LOT_GROUPE):
            lot = a_interroger[debut:debut + LOT_GROUPE]
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
                            enregistrer(ticket, historiques[ticket["cle"].upper()])
                        else:
                            erreurs[404] += 1
                    restants = []
            for ticket in restants:
                try:
                    enregistrer(ticket, historiques_ticket(client, ticket["cle"]))
                except ErreurHTTP as erreur:
                    if erreur.code in CODES_FATALS:
                        raise
                    erreurs[erreur.code] += 1
                time.sleep(PAUSE)
            time.sleep(PAUSE)
            if traites - derniere_sauvegarde >= SAUVEGARDE_TOUTES:
                sauver_cache(cache)
                derniere_sauvegarde = traites
    except ErreurHTTP as erreur:
        arret = erreur.code
    finally:
        if traites:
            sauver_cache(cache)

    mode = t("mode_bulk") if groupe else t("mode_single")
    detail = (" (" + ", ".join(t("error_detail_item", code=c or t("network_short"), count=n)
                               for c, n in sorted(erreurs.items())) + ")") if erreurs else ""
    afficher(t("collect_summary", mode=mode, processed=traites, transitions=nouvelles_transitions,
               errors=sum(erreurs.values()), detail=detail))
    if arret is not None:
        afficher(t("collect_stopped", code=arret))
        sys.exit(1)


def tranches() -> tuple[str, ...]:
    return ("0", "1", "2-4", "5-9", t("bucket_10_plus"))


def tranche(n: int) -> str:
    return "0" if n == 0 else "1" if n == 1 else "2-4" if n <= 4 else "5-9" if n <= 9 else t("bucket_10_plus")


def tranches_texte(repartition: Counter) -> str:
    return t("list_separator").join(t("bucket_item", bucket=c, count=repartition[c]) for c in tranches())


def afficher_ticket(cle: str, cache: dict, export: list[dict]) -> None:
    """Suite des états d'un ticket avec leurs dates, sans auteur : à comparer à l'onglet Historique de Jira.
    Terminal seulement (la clé y figure)."""
    fiche = cache.get(next((c for c in cache if c.upper() == cle.upper()), cle))
    if fiche is None:
        raise ErreurSimple(t("ticket_not_in_cache"))
    transitions = fiche.get("transitions") or []
    afficher(t("ticket_transitions", ticket=cle, count=len(transitions)))
    inconnu = t("unknown_state")
    if transitions:
        afficher(t("ticket_start", state=transitions[0][1] or inconnu))
    for date, de, vers in transitions:
        lisible = str(date if date is not None else "?").replace("T", " ").replace(".000", "")
        afficher(f"  {lisible:<24}  {de or inconnu}  ->  {vers or inconnu}")
    ligne = next((x for x in export if x["cle"].upper() == cle.upper()), None)
    if ligne is not None and ligne.get("etat") is not None:
        afficher(t("ticket_export_state", state=ligne["etat"]))


def cmd_check(args: argparse.Namespace) -> None:
    """Compare, pour chaque ticket du cache, le dernier état de l'historique à l'état de l'export. Aucune clé, aucun
    nom : seulement des effectifs (sauf avec --key, qui n'affiche que ce ticket, dans le Terminal)."""
    if args.dormants is not None:
        raise ErreurSimple(t("dormants_removed"))
    settings = reglages()
    if args.cle:
        export = lire_exports(args.export, settings) if args.export else []
        afficher_ticket(args.cle, charger_cache(), export)
        return
    if not args.export:
        raise ErreurSimple(t("check_needs_export"))
    tickets, lus, ecartes, hors_equipe = selectionner(args, settings)
    if not any(t["etat"] is not None for t in tickets):
        raise ErreurSimple(t("no_status_column"))
    cache = {c.upper(): f for c, f in charger_cache().items()}      # même appariement des clés que flux_jira.py
    coherents = incoherents = sans_transition = absents = livres = livres_sans = 0
    livres_fiches: list[list] = []
    dates_illisibles = 0
    repartition = Counter()
    for tk in tickets:
        fiche = cache.get(tk["cle"].upper())
        if fiche is None:
            absents += 1
            continue
        transitions = fiche.get("transitions") or []
        dates_illisibles += sum(1 for tr in transitions if commun.date_calendaire(tr[0]) is None)
        repartition[tranche(len(transitions))] += 1
        if tk["termine"]:
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
    afficher(t("check_unreadable_dates_flux" if dates_illisibles else "check_unreadable_dates", count=dates_illisibles))
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
    collecte = commandes.add_parser("collect", help="collecte l'historique du champ status des tickets d'un export")
    collecte.add_argument("export", nargs="+", help="un ou plusieurs exports CSV (lots de projets)")
    collecte.add_argument("--team", dest="equipe", help="ne collecter que cette équipe (nom donné seulement ici)")
    collecte.add_argument("--refresh", dest="rafraichir", action="store_true",
                          help="réinterroger tous les tickets retenus, en ignorant le cache")
    controle = commandes.add_parser("check", help="compare le cache à l'état de l'export (effectifs seulement)")
    controle.add_argument("export", nargs="*", help="un ou plusieurs exports CSV (avec la colonne Status)")
    controle.add_argument("--dormants", nargs="?", const="", default=None, help=argparse.SUPPRESS)   # supprimée : refusée avec un message
    controle.add_argument("--key", dest="cle", help="affiche la suite des états de ce ticket, avec leurs dates (Terminal seulement)")
    controle.add_argument("--team", dest="equipe", help="ne contrôler que cette équipe (nom donné seulement ici)")
    for sous_parseur in (test, collecte, controle):
        add_language_option(sous_parseur)
    args = parser.parse_args(flux_config.refuse_old_options(sys.argv[1:] if argv is None else argv, OPTIONS_RENOMMEES))
    set_language(args.language)
    try:
        {"test": cmd_test, "collect": cmd_collect, "check": cmd_check}[args.commande](args)
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
