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
        pas. Historique confirmé seulement (R-20261113-36) : un ticket n'est noté, et son indicateur « avec historique » posé, que si
        son historique est confirmé, c'est-à-dire présent dans la réponse groupée ou relu par ticket. Un ticket rendu par la recherche
        des clés mais absent de la réponse groupée (aucun changement sur les champs demandés, ou réponse tronquée : l'absence ne le
        dit pas) est relu par le repli par ticket ; si la relecture donne un historique vide, c'est confirmé ; si elle échoue, le
        ticket n'est pas noté (rien n'est écrit pour lui, aucune période n'est réécrite), une erreur passagère est comptée et il est
        réinterrogé au passage suivant. Un jeton de page répété, dans la recherche des clés comme dans la lecture groupée, est une
        erreur passagère du lot entier (rien noté pour le lot, tous ses tickets comptés, aucun 404 compté), jamais une fin silencieuse ;
        elle s'affiche « pagination répétée : N » dans le détail des erreurs. Dans la lecture des valeurs courantes, un jeton répété
        laisse les valeurs courantes absentes : les périodes du ticket ne sont alors pas touchées (rien à changer). La ligne « tickets
        relus par ticket : N » (nombre seul, seulement si N > 0) compte les tickets relus par le repli. Les transitions de statut à date illisible sont
        écartées et comptées : la ligne « transitions de statut à date illisible écartées : N » n'est affichée que si N n'est pas nul,
        le nombre seul, jamais une clé. Remplace : l'enregistrement d'un ticket absent de la réponse groupée comme « sans transition »
        (indicateur posé, périodes réécrites depuis la création) et la fin silencieuse sur un jeton répété. Retrait : permanent, c'est
        la règle de la collecte. Une erreur d'accès (401, 403)
        ou de la base annule tout. --team
        filtre sur une équipe (le nom n'est donné qu'en argument). Un fichier d'export donné est refusé (code 2). Sortie : nombre de
        tickets traités, de transitions et d'erreurs, jamais une clé ni un nom, puis « historique écrit : T transitions ajoutées,
        P périodes écrites ». --strict : erreurs passagères de collecte (hors accès refusé ; les 404 ne comptent pas), rapport habituel puis
        sortie avec le code 3.

    uv run tools/history_jira.py check [--team <nom>] [--key <clé>] [--since AAAA-MM-JJ]
        Ne contacte pas Jira. Lit la base (rôle en lecture seule) et compare, pour chaque ticket avec historique, le dernier état de
        l'historique à l'état stocké. Ventilation des incohérents (R-20261113-50 à -52), effectifs et noms d'état (paires) seulement,
        jamais une clé, un titre, une personne ni une équipe (sauf --key, qui n'affiche que ce ticket, dans le Terminal) : livrés ou non
        livrés ; avec --since (date du jour du fuseau d'export, le jour même compte « depuis »), dernière transition de l'historique
        avant ou depuis cette date (sans l'option, cette seconde ventilation n'est pas faite ; date mal formée : message, code 2 ;
        date postérieure à aujourd'hui : un avertissement d'une ligne ; avec --key : refusé, code 2, avant toute lecture ; l'ancien nom
        --depuis est refusé, code 2, avec le nom actuel, R-20261114-01) ; refus de --since avec --key : remplace l'option validée puis
        ignorée sans le dire, retrait permanent (--key n'affiche qu'un ticket, sans ventilation) ; avertissement de date future :
        remplace rien, retrait permanent (une date future vide la ventilation « depuis » sans erreur) ; refus de --depuis : mécanisme
        commun OPTIONS_RENOMMEES, même retrait que les autres renommages ;
        paires (dernier état de l'historique -> état stocké) par effectif décroissant, 10 premières puis « autres : N » ; état stocké
        déjà traversé ou jamais vu dans l'historique du ticket (un statut renommé ou un historique en retard se distingue ainsi d'un
        historique tronqué) ; combien ont leurs deux dernières transitions au même horodatage (un ticket à une seule transition ou à
        date illisible n'est pas compté) et combien ont une date de mise à jour du ticket postérieure à leur dernière transition (indice
        possible d'une transition manquante : toute modification du ticket, commentaire, champ ou lien, déplace cette date ; lue par un lecteur à part de flow_store, R-20261114-25 à -27). Une dernière transition à date illisible est comptée à part (« date de dernière transition illisible : N », seulement si N > 0 et avec --since).
        Sortie : effectifs et noms d'état (cohérents, incohérents, non comparables sans transition,
        transitions par ticket en tranches 0, 1, 2-4, 5-9, 10 et plus, tickets livrés sans transition), puis pour
        les tickets livrés : état de départ de la première transition connue, transitions par ticket, segments
        traversés et états traversés (un historique tronqué au début se voit à un état de départ qui n'est pas
        l'état initial du workflow). --key <clé> affiche seulement la suite des états de ce ticket, avec leurs
        dates et sans auteur, pour la comparer à l'onglet Historique de Jira : Terminal seulement, la clé y figure.
        À lancer par l'utilisateur seul : refusé dans une session Claude Code (code 3). Aucune base sans historique : code 1.
        L'ancienne option --dormants (export CSV des dormants) est refusée : les dormants se déduisent de l'historique
        (flux_jira.py --dormant-from-history).

Client en lecture seule (change jira-read-only-client) : chaque requête est contrôlée avant l'adresse, avant toute reprise et avant tout
appel. Seules sont envoyées les lectures de la liste (GET : informations du site sans authentification, recherche de tickets, historique
d'un ticket, champs ; POST : seulement la recherche de tickets et l'historique groupé). Une requête refusée arrête avec le code 5 et une
phrase fixe, en entier (écriture interdite, hors de la liste des lectures permises, option non permise) ; elle ne nomme que la méthode, et
`collect` n'écrit alors rien. Garde du périmètre : une recherche n'est admise que limitée aux projets de scope_projects ; les projets de
forbidden_projects sont toujours refusés ; la réponse est filtrée (tickets hors des projets déclarés écartés et comptés, liens, parent et
sous-tâches réduits à la clé et au type). Un refus de la garde, ou un de ces deux réglages absent, vide ou illisible (aucun client, aucun
appel), arrête avec le code 6 et sa phrase fixe. Codes 5 et 6 : jamais un autre motif ; avec 0 (fait), 1 (erreur), 2 (usage) et 3
(prérequis refusé ou option stricte), ce sont les codes de sortie de `test` et `collect`.

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
import flow_delivery
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
PAGINATION_REPETEE = -1       # pseudo-code d'une erreur passagère : un jeton de page répété (jamais un code HTTP réel)
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
        super().__init__(t("repeated_pagination") if code == PAGINATION_REPETEE
                         else t("http_code", code=code) if code else t("network_error"))
        self.code = code


CODE_REFUS = 5            # requête refusée par la liste des lectures permises (jira-read-only-client, D4) ; jamais un autre motif
CODE_PERIMETRE = 6        # requête ou réglage refusé par la garde du périmètre (D10) ; jamais un autre motif


class RequeteRefusee(ErreurSimple):
    """Requête hors de la liste des lectures permises (design D3) : erreur simple, jamais une erreur HTTP (elle ne serait pas comptée
    comme passagère). `genre` : « write », « read » ou « option » ; le message est la phrase fixe, qui ne nomme que la méthode."""

    def __init__(self, genre: str, methode: str = "?"):
        self.genre, self.methode = genre, methode
        super().__init__(t({"write": "refused_write", "read": "refused_read", "option": "refused_option"}[genre], method=methode))


class RequeteHorsPerimetre(ErreurSimple):
    """Requête ou réglage refusé par la garde du périmètre (design D10) : classe distincte de la précédente pour avoir son code 6.
    `genre` : « scope » (requête hors des projets déclarés, projet refusé compris) ou « setting » (réglage absent, vide ou
    illisible : seule la clé du réglage est nommée, jamais une valeur) ; « unreadable » : réglage présent mais illisible ou en recouvrement
    (version_reference_project, change jira-delivery-fields D4/D12)."""

    def __init__(self, genre: str, reglage: str = ""):
        self.genre, self.reglage = genre, reglage
        super().__init__(t("refused_setting", setting=reglage) if genre == "setting"
                         else t("refused_setting_unreadable", setting=reglage) if genre == "unreadable" else t("refused_scope"))


def masquer(texte: str) -> str:
    return texte.replace(_JETON, "***") if _JETON else texte


def afficher(texte: str = "") -> None:
    print(masquer(texte))


# ---------------------------------------------------------------------------
# Réglages et jeton
# ---------------------------------------------------------------------------

OPTIONS_RENOMMEES = {**flux_config.OPTIONS_COMMUNES, "--cle": "--key", "--rafraichir": "--refresh", "--depuis": "--since"}


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

# Liste des lectures permises (jira-read-only-client, design D1) : des données immuables, vérifiées avant l'adresse, avant toute reprise et
# avant tout appel. Chaque entrée : (méthode, motif du chemin, authentification requise). Aucun motif ne porte de joker ouvert.
CLE_TICKET = r"[A-Z][A-Z0-9_]*-[0-9]+"           # les clés de Jira sont en majuscules : une clé en minuscules est refusée
LECTURES = (
    ("GET", r"/_edge/tenant_info", False),
    ("GET", r"/rest/api/3/search/jql", True),
    ("GET", rf"/rest/api/3/issue/{CLE_TICKET}/changelog", True),
    ("GET", r"/rest/api/3/field/search", True),
    ("GET", r"/rest/api/3/field", True),
    ("POST", r"/rest/api/3/search/jql", True),
    ("POST", r"/rest/api/3/changelog/bulkfetch", True),
)
NATURES = ("tenant", "search", "changelog", "fields", "fields", "search", "bulk")      # une par entrée de LECTURES
_LECTURES = tuple((m, re.compile(p), a, n) for (m, p, a), n in zip(LECTURES, NATURES))
_CLE_TICKET = re.compile(CLE_TICKET)
OPTIONS_PERMISES = ("params", "json")
VERBES_HTTP = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE", "CONNECT"})


def lectures_autorisees() -> list[tuple[str, str, bool]]:
    """La liste des lectures permises, en données : (méthode, motif du chemin, authentification requise)."""
    return [(m, p, a) for m, p, a in LECTURES]


def _chemin_sain(chemin) -> bool:
    """Un chemin commence par « / » et ne porte ni requête, ni fragment, ni caractère encodé, ni « \\ », ni « // », ni « .. »."""
    return (isinstance(chemin, str) and chemin.startswith("/") and not any(c in chemin for c in "?#%\\")
            and "//" not in chemin and ".." not in chemin)


def verifier_requete(methode, chemin, authentifie: bool, kwargs: dict, perimetre=None) -> str:
    """Contrôle d'une requête avant tout : liste des lectures permises (code 5), options (code 5), puis périmètre (code 6, seulement
    si `perimetre` = (projets déclarés, projets refusés) est donné). Rend la nature de la requête (« search », « changelog », ...).
    Lève RequeteRefusee ou RequeteHorsPerimetre ; ne nomme jamais le chemin, une clé ni une valeur d'argument."""
    nom = methode.upper() if isinstance(methode, str) else "?"
    if nom not in VERBES_HTTP:          # un nom hors de l'ensemble fermé des verbes ne s'imprime jamais (revue 7.1)
        nom = "?"
    trouvee = None
    refus_authentification = False
    if _chemin_sain(chemin):
        for m, motif, auth, nature in _LECTURES:
            if m == nom and motif.fullmatch(chemin):
                if auth == authentifie:
                    trouvee = nature
                else:
                    refus_authentification = True
                break
    if trouvee is None:
        raise RequeteRefusee("read" if (nom == "GET" or refus_authentification) else "write", nom)
    if any(cle not in OPTIONS_PERMISES for cle in kwargs):
        raise RequeteRefusee("option", nom)
    if perimetre is not None:
        projets, interdits = perimetre[0], perimetre[1]
        reference = perimetre[2] if len(perimetre) > 2 else None
        if trouvee == "search":
            donnees = kwargs.get("params" if nom == "GET" else "json")
            verifier_perimetre(donnees.get("jql") if isinstance(donnees, dict) else None, projets, interdits, reference)
        elif trouvee == "changelog":
            _verifier_cle(chemin.split("/")[5], projets, interdits)
        elif trouvee == "bulk":
            corps = kwargs.get("json")
            cles = corps.get("issueIdsOrKeys") if isinstance(corps, dict) else None
            if not isinstance(cles, list) or not cles:
                raise RequeteHorsPerimetre("scope")
            for cle in cles:                       # un identifiant numérique n'est pas une clé : refusé (R-20261028-105)
                _verifier_cle(cle, projets, interdits)
    return trouvee


# Garde du périmètre (design D8 à D11)

_NOM_PROJET = r'(?:"[A-Za-z][A-Za-z0-9_]*"|[A-Za-z][A-Za-z0-9_]*)'
_NOM_CLE = r'(?:"' + CLE_TICKET + r'"|' + CLE_TICKET + r')'
_TETE = re.compile(
    rf'(?is)(?:project\s*=\s*(?P<p1>{_NOM_PROJET})'
    rf'|project\s+in\s*\((?P<pl>\s*{_NOM_PROJET}(?:\s*,\s*{_NOM_PROJET})*\s*)\)'
    rf'|key\s*=\s*(?P<k1>{_NOM_CLE})'
    rf'|key\s+in\s*\((?P<kl>\s*{_NOM_CLE}(?:\s*,\s*{_NOM_CLE})*\s*)\))')
_ET_GROUPE = re.compile(r'(?is)AND\s*\(')
_ORDRE = re.compile(r'(?is)ORDER\s+BY\s+[^()\\]+')
_MOTS = re.compile(r'[A-Za-z0-9_]+(?:-[0-9]+)?')


def _projet_de(cle: str) -> str:
    return cle.rsplit("-", 1)[0]


def _bas(valeurs) -> set[str]:
    return {v.casefold() for v in valeurs}


def _verifier_cle(cle, projets, interdits) -> None:
    """Une clé de ticket doit être bien formée et d'un projet déclaré, jamais d'un projet refusé (sans casse pour ces derniers)."""
    if not isinstance(cle, str) or not _CLE_TICKET.fullmatch(cle):
        raise RequeteHorsPerimetre("scope")
    projet = _projet_de(cle)
    if projet.casefold() in _bas(interdits) or projet not in projets:
        raise RequeteHorsPerimetre("scope")


def _fin_du_groupe(texte: str, debut: int) -> int | None:
    """Position qui suit la parenthèse fermante du groupe ouvert juste avant `debut`, les chaînes entre guillemets ignorées ; None si
    le groupe ne se ferme pas."""
    profondeur, i, guillemet = 1, debut, None
    while i < len(texte):
        c = texte[i]
        if guillemet:
            if c == "\\":
                if texte[i + 1:i + 2] in ("u", "U"):       # un échappement \u pourrait cacher une clé refusée : refusé (revue 7.1)
                    raise RequeteHorsPerimetre("scope")
                i += 1
            elif c == guillemet:
                guillemet = None
        elif c == "\\":                                    # « \ » hors d'une chaîne citée : refusé (revue 7.1, B1)
            raise RequeteHorsPerimetre("scope")
        elif c in "\"'":
            guillemet = c
        elif c == "(":
            profondeur += 1
        elif c == ")":
            profondeur -= 1
            if profondeur == 0:
                return i + 1
        i += 1
    return None


def recherche_versions(reference: str) -> str:
    """La recherche de forme fixe des tickets de version (change jira-delivery-fields, D4) : construite par le code depuis la clé du réglage
    version_reference_project, comparée LITTÉRALEMENT par le client. Règle nouvelle ; remplace : rien (périmètre limité à scope_projects) ;
    retrait : avec la source des versions de R-20261102-21."""
    return f'project = {reference} AND issuetype = "Version"'


def verifier_perimetre(jql, projets, interdits, reference=None) -> None:
    """Une recherche n'est admise que sous la forme du design D8 : une clause de tête (projets ou clés déclarés), puis au plus un groupe
    entre parenthèses relié par AND, puis au plus un ORDER BY. Un projet refusé cité n'importe où (chaînes comprises) est refusé avant
    tout. Exception (jira-delivery-fields D4) : avec la clé du projet de référence des versions, la recherche de forme fixe de
    `recherche_versions` passe, et elle seule ; toute autre recherche qui nomme cette clé est refusée comme un projet non déclaré. Ne rend
    rien ; ne montre ni la requête, ni une clé, ni un projet."""
    if not isinstance(jql, str):
        raise RequeteHorsPerimetre("scope")
    refuses = _bas(interdits)
    for mot in _MOTS.findall(jql):
        bas = mot.casefold()
        if bas in refuses or (re.fullmatch(r"(.+)-[0-9]+", bas) and _projet_de(bas) in refuses):
            raise RequeteHorsPerimetre("scope")
    if reference and jql == recherche_versions(reference):
        return
    texte = jql.strip()
    tete = _TETE.match(texte)
    if tete is None:
        raise RequeteHorsPerimetre("scope")
    for cle_groupe, est_cle in (("p1", False), ("k1", True), ("pl", False), ("kl", True)):
        valeur = tete.group(cle_groupe)
        if valeur is None:
            continue
        for element in valeur.split(","):
            element = element.strip().strip('"')
            if (_projet_de(element) if est_cle else element) not in projets:
                raise RequeteHorsPerimetre("scope")
    reste = texte[tete.end():].strip()
    if reste:
        groupe = _ET_GROUPE.match(reste)
        if groupe:
            fin = _fin_du_groupe(reste, groupe.end())
            reste = "" if fin is None else reste[fin:].strip()
            if fin is None:
                raise RequeteHorsPerimetre("scope")
        if reste and not _ORDRE.fullmatch(reste):
            raise RequeteHorsPerimetre("scope")


def _interdit(cle, interdits) -> bool:
    return isinstance(cle, str) and bool(_CLE_TICKET.fullmatch(cle)) and _projet_de(cle).casefold() in _bas(interdits)


def _reduit(ticket) -> dict | None:
    """Un ticket lié, parent ou sous-tâche réduit à sa clé et au nom de son type ; clé absente ou mal formée : None."""
    cle = ticket.get("key") if isinstance(ticket, dict) else None
    if not isinstance(cle, str) or not _CLE_TICKET.fullmatch(cle):
        return None
    type_ = (((ticket.get("fields") or {}).get("issuetype") or {}).get("name")) if isinstance(ticket.get("fields"), dict) else None
    return {"key": cle, "fields": {"issuetype": {"name": type_}} if isinstance(type_, str) else {}}


def filtrer_recherche(corps, projets, interdits, reference=None, autres_types: list | None = None) -> tuple[dict, int]:
    """Réponse d'une recherche de tickets filtrée (design D9, D11) : un ticket dont la clé manque, est mal formée ou n'est pas d'un
    projet déclaré (ou est d'un projet refusé) est retiré ; liens, parent et sous-tâches sont réduits à la clé et au type, ou retirés
    s'ils sont d'un projet refusé. Rend (réponse, nombre de retraits) : un nombre, jamais une clé.
    Dans la réponse de la recherche de versions SEULE (`reference` donné par l'appelant qui a vérifié la forme fixe), un ticket du projet de
    référence dont le type est « Version » est gardé ; un autre type est retiré et compté à part (`autres_types` : liste à un élément
    incrémenté). Ailleurs (reference None) un ticket du projet de référence n'est pas d'un projet déclaré : retiré."""
    if not isinstance(corps, dict):
        return {}, 0
    retires = 0
    gardes = []
    for ticket in corps.get("issues") if isinstance(corps.get("issues"), list) else []:
        cle = ticket.get("key") if isinstance(ticket, dict) else None
        if (reference and isinstance(cle, str) and _CLE_TICKET.fullmatch(cle) and _projet_de(cle) == reference
                and not _interdit(cle, interdits)):
            type_ = (((ticket.get("fields") or {}).get("issuetype") or {}).get("name")) if isinstance(ticket.get("fields"), dict) else None
            if type_ != "Version":
                if autres_types is not None:
                    autres_types[0] += 1
                continue
        elif (not isinstance(cle, str) or not _CLE_TICKET.fullmatch(cle) or _projet_de(cle) not in projets
                or _interdit(cle, interdits)):
            retires += 1
            continue
        champs = dict(ticket["fields"]) if isinstance(ticket.get("fields"), dict) else None
        if champs is not None:
            if isinstance(champs.get("issuelinks"), list):
                liens = []
                for lien in champs["issuelinks"]:
                    if not isinstance(lien, dict):
                        continue
                    nouveau = {c: v for c, v in lien.items() if c not in ("inwardIssue", "outwardIssue")}
                    retire = False
                    for cote in ("inwardIssue", "outwardIssue"):
                        if cote in lien:
                            lie = _reduit(lien[cote])
                            if lie is None or _interdit(lie["key"], interdits):
                                retire = True
                                break
                            nouveau[cote] = lie
                    if retire:
                        retires += 1
                    else:
                        liens.append(nouveau)
                champs["issuelinks"] = liens
            if isinstance(champs.get("parent"), dict):
                parent = _reduit(champs["parent"])
                if parent is None or _interdit(parent["key"], interdits):
                    del champs["parent"]
                    retires += 1
                else:
                    champs["parent"] = parent
            if isinstance(champs.get("subtasks"), list):
                taches = []
                for tache in champs["subtasks"]:
                    reduite = _reduit(tache)
                    if reduite is None or _interdit(reduite["key"], interdits):
                        retires += 1
                    else:
                        taches.append(reduite)
                champs["subtasks"] = taches
        garde = dict(ticket)
        if champs is not None:
            garde["fields"] = champs
        gardes.append(garde)
    return {**corps, "issues": gardes}, retires


MARQUEUR_REFUSE = "[ticket-refusé]"


def remplacer_references(valeur, interdits) -> tuple[object, int]:
    """Design D11 : dans toutes les chaînes d'une réponse, à toute profondeur (dict, liste, chaînes imbriquées), toute chaîne
    `<clé d'un projet refusé>-<chiffres>`, sans casse, avec une borne de mot avant la clé (rien après les chiffres), devient `[ticket-refusé]`. Rend (valeur, nombre de
    remplacements effectifs) : un nombre, jamais une clé."""
    if not interdits:
        return valeur, 0
    motif = re.compile(r"(?<![A-Za-z0-9_])(?:" + "|".join(re.escape(c) for c in sorted(interdits)) + r")-[0-9]+", re.IGNORECASE)

    def aller(v) -> tuple[object, int]:
        if isinstance(v, str):
            return motif.subn(MARQUEUR_REFUSE, v)
        if isinstance(v, list):
            sortie, total = [], 0
            for element in v:
                nouveau, n = aller(element)
                sortie.append(nouveau)
                total += n
            return sortie, total
        if isinstance(v, dict):
            sortie, total = {}, 0
            for cle, element in v.items():
                nouveau, n = aller(element)
                sortie[cle] = nouveau
                total += n
            return sortie, total
        return v, 0

    return aller(valeur)


class ReponseFiltree:
    """Réponse d'une recherche telle que le client la rend : le code, les en-têtes et le corps filtré ; le corps brut ne sort pas."""

    def __init__(self, reponse, corps, lisible: bool = True):
        self.status_code, self.headers = reponse.status_code, reponse.headers
        self._corps, self._lisible = corps, lisible

    def json(self):
        if not self._lisible:
            raise ValueError("réponse illisible")
        return self._corps


def _liste_de_cles(valeur, reglage: str) -> tuple[str, ...]:
    """Liste de clés de projet d'un réglage de la garde : absente, vide, pas une liste, ou avec une entrée vide ou qui n'est pas une
    clé de projet : refus qui nomme le réglage, jamais sa valeur."""
    if not isinstance(valeur, (list, tuple)) or not valeur:
        raise RequeteHorsPerimetre("setting", reglage)
    cles = []
    for element in valeur:
        if not isinstance(element, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", element.strip()):
            raise RequeteHorsPerimetre("setting", reglage)
        cles.append(element.strip())
    return tuple(cles)


def reglages_garde(settings: dict) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(projets déclarés, projets refusés) des réglages : `forbidden_projects` d'abord, puis `scope_projects` ; sans l'un des deux, aucun
    client n'existe et aucun appel n'est fait. Aucun repli, aucune liste par défaut."""
    interdits = _liste_de_cles(settings.get("forbidden_projects"), "forbidden_projects")
    projets = _liste_de_cles(settings.get("projets_perimetre"), "scope_projects")
    return projets, interdits


class Client:
    """Appels à Jira avec délais d'attente, reprises à attente croissante et respect de Retry-After. Toute requête est contrôlée avant
    l'adresse, avant la boucle de reprise et avant la session : liste des lectures permises, puis périmètre (`projets` déclarés,
    `interdits` refusés) ; la réponse d'une recherche est filtrée avant d'être rendue (`tickets_hors_perimetre` : un nombre)."""

    def __init__(self, base: str, auth: tuple[str, str] | None = None, sleep=None, projets=(), interdits=(), reference=None):
        self.base = base.rstrip("/")
        self.reference = reference          # clé du projet de référence des versions (jira-delivery-fields D4), ou None
        self.autres_types_reference = 0     # tickets d'un autre type écartés de la réponse de la recherche de versions (un nombre)
        self.auth = auth
        self.sleep = sleep or (lambda secondes: time.sleep(secondes))
        self.projets = frozenset(projets)
        self.interdits = frozenset(interdits)
        self.tickets_hors_perimetre = 0
        self.references_remplacees = 0      # D11 : références à un ticket refusé remplacées dans les chaînes rendues (un nombre)
        self.session = requests.Session()

    def _filtrer(self, r, nature: str = "search", versions: bool = False):
        """Recherche : filtre D9 puis remplacement D11. Toute autre nature : remplacement D11 seul, sur une réponse 2xx lisible
        (une autre réponse est rendue telle quelle, comme avant). `versions` : la requête est la recherche de forme fixe des tickets de version."""
        if nature != "search" and not (200 <= r.status_code < 300):
            return r
        if r.status_code >= 400:
            return ReponseFiltree(r, {})
        try:
            corps = r.json()
        except ValueError:
            return r if nature != "search" else ReponseFiltree(r, None, lisible=False)
        filtre = corps
        if nature == "search":
            ecartes = [0]
            filtre, retires = filtrer_recherche(corps, self.projets, self.interdits, self.reference if versions else None, ecartes)
            self.tickets_hors_perimetre += retires
            self.autres_types_reference += ecartes[0]
        filtre, remplaces = remplacer_references(filtre, self.interdits)
        self.references_remplacees += remplaces
        return ReponseFiltree(r, filtre)

    def requete(self, methode: str, chemin: str, **kwargs) -> requests.Response:
        nature = verifier_requete(methode, chemin, self.auth is not None, kwargs, (self.projets, self.interdits, self.reference))
        methode = methode.upper()
        donnees = kwargs.get("params" if methode == "GET" else "json")
        versions = bool(self.reference) and nature == "search" and isinstance(donnees, dict) \
            and donnees.get("jql") == recherche_versions(self.reference)
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
                return self._filtrer(r, nature, versions)
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


def reference_des_versions(settings: dict, projets) -> str | None:
    """Clé du projet de référence des versions (réglage version_reference_project, hors Git ; change jira-delivery-fields D4) : None si le
    réglage est absent ou vide. Une valeur qui n'est pas une seule clé de projet, ou une clé aussi déclarée dans scope_projects, arrête
    avec le code 6 et la phrase du réglage (jamais sa valeur), avant tout appel à Jira. Une clé de forbidden_projects est refusée plus
    tard par la règle des projets refusés."""
    brut = settings.get("version_reference_project")
    if brut is None or (isinstance(brut, str) and not brut.strip()):
        return None
    if not isinstance(brut, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", brut.strip()) or brut.strip() in projets:
        raise RequeteHorsPerimetre("unreadable", "version_reference_project")
    return brut.strip()


def construire_client(settings: dict, avec_reference: bool = False) -> Client:
    """Client de la passerelle api.atlassian.com/ex/jira/<cloudId>, le cloudId venant des réglages. Les refus de réglage
    (classic, cloudId) précèdent la lecture du Trousseau ; aucun appel authentifié ne va à l'adresse du site. `avec_reference` (l'export
    seul) : le client admet la recherche de forme fixe des tickets de version du projet de référence."""
    global _JETON
    _, email, _ = reglages_jira(settings)
    cloud_id = identifiant_cloud(settings)
    verifier_url(API_ATLASSIAN)
    projets, interdits = reglages_garde(settings)       # sans l'une des deux listes : code 6, avant le Trousseau et tout appel
    reference = reference_des_versions(settings, projets) if avec_reference else None
    jeton = lire_jeton()
    _JETON = jeton
    return Client(f"{API_ATLASSIAN}/ex/jira/{cloud_id}", (email, jeton), projets=projets, interdits=interdits, reference=reference)


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


def lire_maj_de_la_base(settings: dict) -> dict:
    """{CLÉ_MAJUSCULES: date de dernière mise à jour du ticket ou None}, même rôle en lecture seule que lire_donnees_de_la_base (lecteur
    à part de flow_store, pour ne pas changer les lignes lues par les rapports). Une base injoignable arrête avec le code 1."""
    import flow_store
    try:
        return flow_store.lire_maj_tickets(settings)
    except Exception as erreur:
        if type(erreur).__name__ != "ErreurBase":
            raise
        raise ErreurSimple(str(erreur)) from None


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


def historiques_groupes(client: Client, cles: list[str]) -> tuple[dict[str, list[dict]], list[str], set[str]]:
    """Historiques d'un lot de tickets avec l'API groupée. Retourne les historiques par clé (en majuscules), les clés que
    Jira ne renvoie pas (supprimées, sans accès) et l'ensemble des clés (en majuscules) que la réponse groupée a réellement
    portées : un ticket rendu par la recherche mais absent de cet ensemble n'a pas d'historique confirmé (aucun changement sur les
    champs demandés, ou réponse tronquée) et doit être relu par ticket (R-20261113-36). La réponse groupée ne porte que
    l'identifiant : un appel de recherche, limité aux clés, fait la correspondance. Un jeton de page répété, dans la recherche des clés
    comme dans la lecture groupée, lève ErreurHTTP(PAGINATION_REPETEE) : erreur passagère du lot, jamais une fin silencieuse."""
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
        if not suivant:
            break
        if suivant == jeton_page:           # même décision que la lecture groupée (R-20261113-36) : des clés perdues ne sont pas des 404
            raise ErreurHTTP(PAGINATION_REPETEE)
        jeton_page = suivant
    resultat: dict[str, list[dict]] = {str(cle).upper(): [] for cle in id_vers_cle.values()}
    confirmes: set[str] = set()
    if id_vers_cle:
        jeton_page = None
        while True:
            # des clés, jamais des identifiants numériques : la garde du périmètre vérifie le projet de chacune (R-20261028-105) ;
            # la correspondance identifiant -> clé reste celle de la recherche
            # jira-delivery-fields D2 : le sprint, les versions visée et livrée (et les versions d'épic déclarées historisées) rejoignent la
            # liste ; les champs propres aux défauts n'y sont jamais (R-20261102-33)
            corps = {"issueIdsOrKeys": list(id_vers_cle.values()),
                     "fieldIds": ["status", "labels", "fixVersions"] + flow_delivery.champs_historises(), "maxResults": 1000}
            if jeton_page:
                corps["nextPageToken"] = jeton_page
            reponse = client.json("POST", "/rest/api/3/changelog/bulkfetch", json=corps)
            for fiche in reponse.get("issueChangeLogs") or []:
                cle = id_vers_cle.get(str(fiche.get("issueId")))
                if cle:
                    resultat[str(cle).upper()] += fiche.get("changeHistories") or []
                    confirmes.add(str(cle).upper())
            suivant = reponse.get("nextPageToken")
            if not suivant:
                break
            if suivant == jeton_page:           # une réponse qui boucle est tronquée : erreur passagère du lot, pas une fin
                raise ErreurHTTP(PAGINATION_REPETEE)
            jeton_page = suivant
    return resultat, [c for c in cles if c.upper() not in resultat], confirmes


def valeurs_courantes(client: Client, cles: list[str], avec_etiquettes: bool) -> dict[str, dict]:
    """Versions correctives et étiquettes courantes d'un lot de tickets (database-only, D5 : l'export ne les demande plus), par clé en
    majuscules : {"versions": [noms], "etiquettes": [étiquettes]}. Les étiquettes ne sont demandées qu'avec des étiquettes déclarées ;
    l'appelant ne garde que les déclarées. Un ticket que Jira ne renvoie pas n'a pas d'entrée."""
    jql = "key in (" + ",".join(cles) + ")"
    champs = ["fixVersions"] + (["labels"] if avec_etiquettes else []) + flow_delivery.champs_historises()
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
                "etiquettes": list(dict.fromkeys(e.strip() for e in etiquettes if e.strip())),
                **flow_delivery.courantes_de(fields)}          # sprints et actifs courants : identifiants seuls
        suivant = reponse.get("nextPageToken")
        if not suivant or suivant == jeton_page:
            return valeurs
        jeton_page = suivant


# ---------------------------------------------------------------------------
# Commandes
# ---------------------------------------------------------------------------

# clé de repli de la sonde de l'historique quand la recherche ne rend aucun ticket : « <premier projet déclaré>-1 » (cmd_test)


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
    projets, _ = reglages_garde(settings)      # une liste absente ou vide : code 6, avant tout appel (la lecture du cloudId comprise)
    premier = projets[0]
    # seul `test` lit le cloudId du site, sans authentification : un autre identifiant enverrait les appels à un autre tenant
    if str(Client(site).json("GET", "/_edge/tenant_info").get("cloudId") or "") != cloud_id:
        raise ErreurSimple(t("cloud_id_mismatch"))
    client = construire_client(settings)
    ticket = None
    resultats: list[tuple[str, int]] = []
    # R-20261028-111 : la sonde de recherche est de la forme acceptée, sur le premier projet déclaré
    r = client.requete("GET", "/rest/api/3/search/jql",
                       params={"jql": f"project = {premier} ORDER BY created DESC", "maxResults": 1, "fields": "key"})
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
    code = sonder(client, "GET", f"/rest/api/3/issue/{quote(str(ticket or f'{premier}-1'))}/changelog", params={"maxResults": 1})
    resultats.append(("history", 200 if code == 404 and not ticket else code))
    resultats.append(("fields", sonder(client, "GET", "/rest/api/3/field/search", params={"maxResults": 1})))
    afficher(t("connection_ok"))
    for ressource, code in resultats:
        statut = t("access_ok") if code == 200 else (code or t("network_short"))
        afficher(t("access_line", resource=ressource, status=statut))
    refus = any(code != 200 for _, code in resultats)
    if client.tickets_hors_perimetre:
        afficher(t("out_of_scope_count", count=client.tickets_hors_perimetre))
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
    transitions, illisibles = [], 0
    for date, depart, arrivee in brut["transitions"]:
        instant = commun.instant_de_transition(date, fuseau)
        if instant is not None:
            transitions.append((instant, depart, arrivee))
        else:                                       # une date illisible est écartée, comme pour les événements de période, et comptée
            illisibles += 1
    courantes = brut["courantes"]
    etiquettes = versions = sprints = actifs = None
    if courantes is not None:
        cree = ticket["cree"]
        versions = commun.construire_periodes(brut["versions"], courantes["versions"], cree, fuseau)
        if declarees:
            etiquettes = commun.construire_periodes(brut["etiquettes"], [e for e in courantes["etiquettes"] if e in declarees],
                                                    cree, fuseau, declarees)
        # champs de livraison (jira-delivery-fields D2) : périodes bâties comme celles des versions correctives ; une valeur courante
        # absente de la réponse de Jira n'est pas un champ vide, les périodes du champ ne sont alors pas touchées
        if "sprints" in courantes:
            sprints = commun.construire_periodes(brut.get("sprints") or [], courantes["sprints"], cree, fuseau)
        if "actifs" in courantes:
            presentes = [f"{genre}:{objet}" for genre, objets in courantes["actifs"].items() for objet in objets]
            actifs = commun.construire_periodes(brut.get("actifs") or [], presentes, cree, fuseau)
    return {"transitions": transitions, "etiquettes": etiquettes, "versions": versions, "sprints": sprints, "actifs": actifs,
            "transitions_illisibles": illisibles}


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
    reglages_garde(settings)          # les deux listes de la garde d'abord, même sans rien à interroger (revue 7.1) : code 6 sinon
    if not flow_delivery.configurer(flux_config.delivery_fields(settings)):          # table de flux.yaml, hors Git (R-20261114-108, même logique que A-92)
        afficher(t("collect_no_delivery_fields"))          # sans table : ni sprint ni version d'actif collectés, la collecte se poursuit (code inchangé)
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
    relus = 0                             # tickets absents de la réponse groupée, relus par ticket (R-20261113-36)
    bruts: dict[str, tuple[dict, dict]] = {}          # clé -> (ticket, résultat brut de Jira) ; rien n'est écrit avant la fin
    introuvables: list[str] = []          # tickets que Jira ne trouve pas (404) à ce passage : seuls ceux-là comptent, pas les erreurs passagères

    evenements_livraison = illisibles = 0

    def noter(ticket: dict, historiques: list[dict], courantes: dict | None) -> None:
        nonlocal traites, nouvelles_transitions, evenements_livraison, illisibles
        transitions, versions, etiquettes = evenements_de(historiques, declarees)
        sprints_ev, actifs_ev, ill = flow_delivery.evenements_de_livraison(historiques)
        bruts[ticket["cle"]] = (ticket, {"transitions": transitions, "versions": versions, "etiquettes": etiquettes,
                                         "sprints": commun.trier_evenements(sprints_ev), "actifs": commun.trier_evenements(actifs_ev),
                                         "courantes": courantes})
        traites += 1
        nouvelles_transitions += len(transitions)
        evenements_livraison += len(sprints_ev) + len(actifs_ev)
        illisibles += ill

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
                    historiques, absents, confirmes = historiques_groupes(client, [t["cle"] for t in lot])
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
                    restants = []
                    for ticket in lot:
                        majuscules = ticket["cle"].upper()
                        if majuscules not in historiques:
                            introuvables.append(ticket["cle"])          # Jira ne le renvoie pas : un 404, pas une erreur passagère
                        elif majuscules in confirmes:
                            noter(ticket, historiques[majuscules], courantes.get(majuscules))
                        else:
                            # rendu par la recherche, absent de la réponse groupée : « aucun changement » ou réponse tronquée, l'absence ne
                            # le dit pas. Relu par ticket (R-20261113-36) ; s'il échoue, le ticket n'est pas noté : aucun indicateur
                            # « avec historique », aucune période réécrite, il est réinterrogé au passage suivant
                            restants.append(ticket)
                    relus += len(restants)
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
    detail = (" (" + ", ".join(t("error_detail_repeated", count=n) if c == PAGINATION_REPETEE
                               else t("error_detail_item", code=c or t("network_short"), count=n)
                               for c, n in sorted(erreurs.items())) + ")") if erreurs else ""
    afficher(t("collect_summary", mode=mode, processed=traites, transitions=nouvelles_transitions,
               errors=sum(erreurs.values()), detail=detail))
    if relus:          # le nombre seul, jamais une clé ; rien n'est affiché à zéro
        afficher(t("collect_reread_single", count=relus))
    if client.tickets_hors_perimetre:
        afficher(t("out_of_scope_count", count=client.tickets_hors_perimetre))
    # champs de livraison (jira-delivery-fields D2, D12) : des nombres et des noms de genre fixes, jamais un identifiant
    afficher(t("collect_delivery_events", count=evenements_livraison))
    afficher(t("collect_delivery_unreadable", count=illisibles))          # toujours, même 0 (R-20261102-36)
    if introuvables:
        afficher(t("collect_not_found", count=len(introuvables)))
    if arret is not None:         # erreur d'accès : rien n'est écrit (une seule transaction, annulée)
        afficher(t("collect_stopped", code=arret))
        sys.exit(1)
    resultats = {cle: resultat_pret(ticket, brut, declarees, fuseau) for cle, (ticket, brut) in bruts.items()}
    transitions_illisibles = sum(resultat.pop("transitions_illisibles") for resultat in resultats.values())
    if transitions_illisibles:          # le nombre seul, jamais une clé ni une date (R-20261113-36) ; rien n'est affiché à zéro
        afficher(t("collect_transitions_unreadable", count=transitions_illisibles))
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


def transitions_meme_statut(transitions: list) -> int:
    """Nombre de transitions [date, de, vers] dont le statut de départ et le statut d'arrivée ont le même nom (espaces et casse
    ignorés ; un statut vide n'est jamais compté). Elles restent stockées ; elles sont dénombrées à part (idée 436) et écartées de la
    répartition des transitions par ticket (idée 492). Elles ne changent ni les segments traversés ni les temps par segment : une visite
    de segment regroupe les périodes contiguës d'un même segment, et les durées sont des différences de dates."""
    return len(transitions) - len(commun.sans_meme_statut(transitions))


def date_depuis(texte: str | None) -> dt.date | None:
    """Date de --since (AAAA-MM-JJ, jour du fuseau d'export) ; absente : None. Mal formée : message et code 2."""
    if texte is None:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", texte):
        try:
            return dt.date.fromisoformat(texte)
        except ValueError:
            pass
    afficher(t("error_line", message=t("since_invalid", value=texte)))
    sys.exit(2)


PAIRES_AFFICHEES = 10


def instants_des_dernieres_transitions(transitions: list, zone) -> tuple[dt.datetime | None, dt.datetime | None]:
    """(instant de l'avant-dernière transition, instant de la dernière) ; None pour une date illisible, et pour l'avant-dernière quand
    le ticket n'a qu'une transition. Les dates de la base portent un décalage ; `zone` ne sert qu'à une date qui n'en a pas."""
    derniere = commun.instant_de_transition(transitions[-1][0], zone)
    avant = commun.instant_de_transition(transitions[-2][0], zone) if len(transitions) >= 2 else None
    return avant, derniere


def afficher_incoherents(fiches: list[tuple[bool, list, str | None, dt.datetime | None]], depuis: dt.date | None, fuseau) -> None:
    """Ventilation des incohérents (R-20261113-50 à -52), effectifs et noms d'état (paires) seulement : livré ou non, puis (avec --since)
    dernière transition de l'historique avant ou depuis cette date (jour du fuseau d'export ; le jour même compte « depuis ») ; paires
    (dernier état de l'historique, état stocké) triées par effectif décroissant, 10 premières puis « autres » ; état stocké déjà
    traversé ou jamais vu ; puis (R-20261114-25 à -27) combien ont leurs deux dernières transitions au même instant (un ticket à une
    seule transition ou une date illisible n'est pas compté) et combien ont une date de mise à jour postérieure à leur dernière
    transition (indice possible d'une transition manquante, toute modification du ticket compte ; sans date de mise à jour ou à date illisible : pas compté). `fiches` : (livré,
    transitions [date, départ, arrivée], état stocké, date de mise à jour du ticket). Jamais une clé, un titre, une personne ni une
    équipe (sauf --key, qui n'affiche que ce ticket dans le Terminal, hors de cette fonction)."""
    compte = {(livre, place): 0 for livre in (True, False) for place in ("avant", "depuis", "illisible")}
    paires: Counter = Counter()
    affichage: dict[tuple, tuple[str, str]] = {}
    traverses = jamais = memes_instants = maj_posterieure = 0
    zone = fuseau or dt.timezone.utc          # sans --since, le fuseau n'est pas calculé : les dates de la base portent leur décalage
    inconnu = t("unknown_state")
    for livre, transitions, stocke, maj in fiches:
        avant_derniere, derniere_instant = instants_des_dernieres_transitions(transitions, zone)
        if avant_derniere is not None and derniere_instant is not None and avant_derniere == derniere_instant:
            memes_instants += 1
        if maj is not None and derniere_instant is not None:
            maj_posterieure += (maj if maj.tzinfo else maj.replace(tzinfo=zone)) > derniere_instant
        place = "avant"          # sans --since, la date n'est pas lue (le fuseau n'est pas non plus calculé)
        if depuis is not None:
            derniere = commun.instant_de_transition(transitions[-1][0], fuseau)
            place = ("illisible" if derniere is None
                     else "depuis" if derniere.astimezone(fuseau).date() >= depuis else "avant")
        compte[(livre, place)] += 1
        arrivee = (transitions[-1][2] or "").strip()
        cible = (stocke or "").strip()
        cle = (arrivee.casefold(), cible.casefold())
        paires[cle] += 1
        affichage.setdefault(cle, (arrivee or inconnu, cible or inconnu))
        vus = {(e or "").strip().casefold() for tr in transitions for e in (tr[1], tr[2])}
        if cible.casefold() in vus:
            traverses += 1
        else:
            jamais += 1
    livres = sum(compte[(True, place)] for place in ("avant", "depuis", "illisible"))
    non_livres = sum(compte[(False, place)] for place in ("avant", "depuis", "illisible"))
    if depuis is None:
        afficher(t("check_split", delivered=livres, not_delivered=non_livres))
    else:
        afficher(t("check_split_since", delivered=livres, date=depuis.isoformat(), delivered_before=compte[(True, "avant")],
                   delivered_since=compte[(True, "depuis")], not_delivered=non_livres,
                   not_delivered_before=compte[(False, "avant")], not_delivered_since=compte[(False, "depuis")]))
        illisibles = compte[(True, "illisible")] + compte[(False, "illisible")]
        if illisibles:          # le nombre seul, rien n'est affiché à zéro
            afficher(t("check_split_unreadable", count=illisibles))
    classees = sorted(paires.items(), key=lambda element: (-element[1], affichage[element[0]]))
    morceaux = [f"{affichage[cle][0]} -> {affichage[cle][1]} {n}" for cle, n in classees[:PAIRES_AFFICHEES]]
    reste = sum(n for _, n in classees[PAIRES_AFFICHEES:])
    if reste:
        morceaux.append(t("check_pairs_other", count=reste))
    afficher(t("check_pairs", pairs=t("list_separator").join(morceaux) or t("check_pairs_none")))
    afficher(t("check_stored_seen", crossed=traverses, never=jamais))
    afficher(t("check_last_two_same", same=memes_instants, updated_later=maj_posterieure))


def cmd_check(args: argparse.Namespace) -> None:
    """Compare, pour chaque ticket avec historique, le dernier état de l'historique à l'état stocké (base, rôle en lecture seule).
    Effectifs et noms d'état (paires) seulement, jamais une clé, un titre, une personne ni une équipe (sauf avec --key, qui n'affiche
    que ce ticket, dans le Terminal). --since avec --key : refusé (code 2) avant toute lecture de réglage ou de base."""
    if VARIABLE_CLAUDE_CODE in os.environ:          # utilisateur seul : refus avant toute lecture de réglage (design D12)
        afficher(t("session_refused"))
        sys.exit(3)
    refuser_fichier_d_export(args)
    if args.dormants is not None:
        raise ErreurSimple(t("dormants_removed"))
    if args.depuis is not None and args.cle:          # refus (code 2) avant toute lecture de réglage ou de base (R-20261114-01)
        afficher(t("error_line", message=t("since_with_key")))
        sys.exit(2)
    depuis = date_depuis(args.depuis)          # refus (code 2) avant toute lecture de réglage ou de base
    settings = reglages()
    base, historique = lire_donnees_de_la_base(settings)
    if args.cle:
        afficher_ticket(args.cle, historique, base)
        return
    if not historique:
        raise ErreurSimple(t("no_history_in_db"))
    fuseau = fuseau_des_reglages(settings) if depuis else None        # le fuseau ne sert qu'à la ventilation --since
    if depuis is not None and depuis > dt.datetime.now(fuseau).date():          # un avertissement, pas une erreur (R-20261114-01)
        afficher(t("since_future", date=depuis.isoformat()))
    mises_a_jour = lire_maj_de_la_base(settings)          # après les refus et le retour de --key : lecture seule, une requête de plus
    tickets, lus, ecartes, hors_equipe = selectionner(args, base, settings)
    incoherents_fiches: list[tuple[bool, list, str | None, dt.datetime | None]] = []   # (livré, transitions, état stocké, mise à jour)
    coherents = incoherents = sans_transition = absents = livres = livres_sans = 0
    livres_fiches: list[list] = []
    repartition = Counter()
    memes_statuts = 0
    for tk in tickets:
        transitions = historique.get(tk["cle"].upper())      # même appariement des clés que flux_jira.py
        if transitions is None:
            absents += 1
            continue
        memes = transitions_meme_statut(transitions)
        repartition[tranche(len(transitions) - memes)] += 1          # les transitions vers un statut de même nom n'y comptent pas
        memes_statuts += memes
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
            incoherents_fiches.append((bool(tk["resolu"]), transitions, tk["etat"], mises_a_jour.get(tk["cle"].upper())))
    afficher(t("check_retained", retained=len(tickets), missing=absents))
    afficher(t("check_consistency", consistent=coherents, inconsistent=incoherents, not_comparable=sans_transition))
    afficher_incoherents(incoherents_fiches, depuis, fuseau)
    afficher(t("check_buckets", buckets=tranches_texte(repartition)))
    afficher(t("check_same_status", count=memes_statuts))
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
        nombres[tranche(len(commun.sans_meme_statut(transitions)))] += 1
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
    controle.add_argument("--since", dest="depuis", metavar="AAAA-MM-JJ",
                          help="ventile les incohérents selon la date de leur dernière transition : avant ou depuis ce jour "
                               "(jour du fuseau d'export ; le jour même compte « depuis »)")
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
    except RequeteRefusee as erreur:         # avant ErreurSimple : la phrase fixe en entier, le code 5 (design D4)
        afficher(t("error_line", message=erreur))
        sys.exit(CODE_REFUS)
    except RequeteHorsPerimetre as erreur:   # code 6 (design D10)
        afficher(t("error_line", message=erreur))
        sys.exit(CODE_PERIMETRE)
    except ErreurSimple as erreur:
        afficher(t("error_line", message=erreur))
        sys.exit(1)
    except Exception as erreur:       # aucun détail : un message de bibliothèque pourrait citer une adresse
        afficher(t("unexpected_error", name=type(erreur).__name__))
        sys.exit(1)


if __name__ == "__main__":
    main()
