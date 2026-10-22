"""PMZilla Lab : sous-commande `collect` de tools/story_quality.py (change story-quality-audit, design D3, D4, D9, D14 et D16).

    uv run tools/story_quality.py collect [--query <nom>] [--language fr|en]

Lancée par l'utilisateur seul, dans le Terminal : le répartiteur la refuse dans une session Claude Code (code 3) avant toute lecture.
Ordre : réglages (bloc story_quality de Flux-Lab/flux.yaml, lecture stricte), liste des noms sensibles, référentiel d'organisation,
base (schéma quality), client Jira (jeton du Trousseau, passerelle api.atlassian.com), contrôle des champs configurés contre la liste des
champs de Jira (un champ de personne arrête avec le code 3 avant la lecture du moindre ticket), lecture des requêtes nommées, nettoyage,
écriture en UNE transaction.

Couche 1 de D4 : la requête ne demande que le titre, la description, le champ des critères d'acceptation configuré, le type, le statut, le
champ d'équipe configuré, le parent, la création, la mise à jour et la date de résolution. Jamais un responsable, un rapporteur, un
créateur, des observateurs, des votes, des commentaires, des pièces jointes, un journal de travail ni l'historique des changements.
Couche 2 : chaque texte est nettoyé (tools/story_quality_scrub.py) avant d'être stocké.

Seuls les éléments dont le type est associé à story ou epic sont stockés. Un élément résolu depuis plus longtemps que la durée de
conservation n'est pas stocké : il est compté. Un passage sur toutes les requêtes du bloc marque sortis de la collecte les éléments
stockés qu'il ne voit plus et retire la marque de ceux qui reviennent ; un passage limité à une requête (--query) ne marque rien. Pour
chaque équipe vue, le drapeau « un seul PO » du référentiel est copié dans les attributs d'équipe, et aucune autre valeur du référentiel.

La sortie ne porte que des effectifs et les phrases de D14 : jamais une clé, une équipe, un titre, un texte, une valeur de champ ni le
jeton. Aucun fichier n'est écrit. Codes : 0 fait ; 1 erreur (Jira, base, réglages illisibles) ; 2 usage ; 3 prérequis refusé (bloc absent,
plafond invalide, champ de personne configuré, liste des noms sensibles indisponible).
"""
from __future__ import annotations

import datetime as dt
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_jira_api as eja  # noqa: E402
import flux_config  # noqa: E402
import history_common as commun  # noqa: E402
import history_jira as hj  # noqa: E402
import sensitive_names  # noqa: E402
import story_quality_scrub as scrub  # noqa: E402
import story_quality_store as store  # noqa: E402
from yaml_strict import ErreurConfig  # noqa: E402

NAMES_VARIABLE = "PMZILLA_LAB_SENSITIVE_NAMES"
CLE_CRITERES = "story_quality.acceptance_criteria_field"
CLE_EQUIPE = "export_team_field"
# champs jamais demandés, quels que soient les réglages (design D4, couche 1) : le test de garde des champs s'en sert aussi
CHAMPS_INTERDITS = frozenset({"assignee", "reporter", "creator", "watches", "watchers", "votes", "comment", "attachment", "worklog",
                              "changelog", "*all", "*navigable"})
TYPES_DE_PERSONNE = ("userpicker", "multiuserpicker", "people", "participants", "sd-approvals")


class Refus(Exception):
    """Arrêt avec une phrase du catalogue et un code (jamais une valeur de Jira ni des réglages)."""

    def __init__(self, cle: str, code: int, **valeurs):
        super().__init__(cle)
        self.cle, self.code, self.valeurs = cle, code, valeurs


def champs_demandes(criteres: str | None, equipe: str | None) -> list[str]:
    """Liste exacte des champs demandés à Jira (design D4, couche 1)."""
    champs = ["summary", "description"] + ([criteres] if criteres else []) + ["issuetype", "status"]
    champs += ([equipe] if equipe else []) + ["parent", "created", "updated", "resolutiondate"]
    return list(dict.fromkeys(champs))


def est_champ_de_personne(definition: dict) -> bool:
    schema = definition.get("schema") if isinstance(definition.get("schema"), dict) else {}
    genre, elements, propre = schema.get("type"), schema.get("items"), str(schema.get("custom") or "")
    return genre == "user" or (genre == "array" and elements == "user") or any(propre.endswith(":" + t) for t in TYPES_DE_PERSONNE)


def verifier_champs(client, configures: dict[str, str]) -> None:
    """Contrôle des identifiants de champ configurés (clé de réglage -> identifiant) contre la liste des champs de Jira : un champ de
    personne (utilisateur ou liste d'utilisateurs) arrête avec le code 3 en nommant la clé du réglage, jamais l'identifiant."""
    if not configures:
        return
    liste = client.json("GET", "/rest/api/3/field")
    par_id = {str(d.get("id")): d for d in liste if isinstance(d, dict)} if isinstance(liste, list) else {}
    for cle, identifiant in configures.items():
        if identifiant in CHAMPS_INTERDITS or est_champ_de_personne(par_id.get(identifiant) or {}):
            raise Refus("person_field_refused", 3, key=cle)


def instant(valeur, fuseau) -> dt.datetime | None:
    """Date ISO de l'API en instant avec fuseau (une date sans décalage prend le fuseau d'export) ; illisible ou absente : None."""
    if not valeur:
        return None
    try:
        d = dt.datetime.fromisoformat(str(valeur))
    except ValueError:
        return None
    return d if d.tzinfo is not None else d.replace(tzinfo=fuseau)


def forme_de_nom(nom: str) -> str:
    """Forme de comparaison d'un nom d'équipe : NFC, sans casse, espaces (insécables compris) réduits à un."""
    return " ".join(unicodedata.normalize("NFC", str(nom)).casefold().split())


def equipes_de(valeur, correspondance: dict[str, str] | None) -> list[str]:
    """Équipes d'un élément : libellés pris tels quels, identifiants traduits par le référentiel ou le catalogue (inconnus : la
    désignation fixe « (équipe inconnue) »). Une forme de valeur inexploitable ne donne aucune équipe (la valeur n'est jamais écrite)."""
    noms = eja.libelles(valeur)
    if noms is not None:
        return list(dict.fromkeys(noms))
    ids = eja.identifiants(valeur)
    if ids is None:
        return []
    return list(dict.fromkeys((correspondance or {}).get(i, eja.EQUIPE_INCONNUE) for i in dict.fromkeys(ids)))


def construire(ticket: dict, genre: str, champs_sq: dict, champ_equipe: str | None, correspondance, nettoyeur, fuseau) -> store.Element | None:
    champs = ticket.get("fields") or {}
    cree, modifie = instant(champs.get("created"), fuseau), instant(champs.get("updated"), fuseau)
    if cree is None or modifie is None:
        return None
    titre, n1 = nettoyeur.nettoyer(champs.get("summary"))
    description, n2 = nettoyeur.nettoyer(champs.get("description"))
    criteres_id = champs_sq["acceptance_criteria_field"]
    criteres, n3 = nettoyeur.nettoyer(champs.get(criteres_id)) if criteres_id else ("", 0)
    statut = champs.get("status") or {}
    return store.Element(
        key=str(ticket.get("key")), kind=genre, parent_key=(champs.get("parent") or {}).get("key") or None,
        status_category=(statut.get("statusCategory") or {}).get("key") or None, created_at=cree, updated_at=modifie,
        resolved_at=instant(champs.get("resolutiondate"), fuseau),
        teams=equipes_de(champs.get(champ_equipe), correspondance) if champ_equipe else [],
        title=titre, description=description, acceptance_criteria=criteres,
        content_hash=scrub.empreinte(titre, description, criteres), replacements=n1 + n2 + n3)


def lancer(args, environ, t) -> int:
    """Sous-commande collect (la session a déjà été refusée par le répartiteur). Rend le code de sortie."""
    eja.set_language(args.language)                  # langue de l'export et de history_jira, pour leurs messages d'erreur
    try:
        return _collecter(args, environ, t)
    except Refus as refus:
        print(phrase(t, refus.cle, **refus.valeurs), file=sys.stderr)
        return refus.code


def phrase(t, cle: str, **valeurs) -> str:
    """Phrase du catalogue. Passe à côté de Messages.__call__, dont le premier paramètre s'appelle déjà `key` : la phrase du champ de
    personne de D14 a un champ {key} (le nom de la clé de réglage)."""
    texte = t.catalogs[t.language].get(cle) or t.catalogs["fr"][cle]
    return texte.format(**valeurs) if valeurs else texte


def _collecter(args, environ, t) -> int:
    try:
        settings = hj.reglages()
    except flux_config.ErreurPlafond:
        raise Refus("cap_invalid", 3) from None
    except ErreurConfig as erreur:
        raise Refus("settings_unreadable", 1, detail=str(erreur)) from None
    sq = flux_config.story_quality(settings)
    if sq is None:
        raise Refus("settings_block_missing", 3)
    requetes = sq["queries"]
    if args.query is not None:
        requetes = [(nom, jql) for nom, jql in requetes if nom == args.query]
        if not requetes:
            raise Refus("usage", 2, what="--query")
    complet = args.query is None
    try:
        jours = flux_config.retention_days(settings)
        fuseau = commun.fuseau_export(settings)
    except (ErreurConfig, commun.ErreurFuseau) as erreur:
        raise Refus("settings_unreadable", 1, detail=str(erreur) if isinstance(erreur, ErreurConfig) else "export_timezone") from None
    champ_equipe = str(settings.get("export_champ_equipe") or "").strip() or None
    if champ_equipe and not re.fullmatch(r"[A-Za-z0-9_]+", champ_equipe):
        raise Refus("settings_unreadable", 1, detail=CLE_EQUIPE)
    try:
        nettoyeur = scrub.Nettoyeur(sensitive_names.load_names(environ.get(NAMES_VARIABLE) or None))
    except (sensitive_names.SensitiveNamesUnavailable, ValueError):
        raise Refus("collect_names_unavailable", 3) from None
    try:
        traduction = eja.resoudre_traduction()
    except ErreurConfig as erreur:
        raise Refus("settings_unreadable", 1, detail=str(erreur)) from None
    try:
        magasin = store.ouvrir()
    except store.ErreurMagasin:
        raise Refus("db_unreachable", 1) from None
    try:
        return _lire_et_ecrire(t, settings, sq, requetes, complet, jours, fuseau, champ_equipe, nettoyeur, traduction, magasin)
    finally:
        magasin.fermer()


def _lire_et_ecrire(t, settings, sq, requetes, complet, jours, fuseau, champ_equipe, nettoyeur, traduction, magasin) -> int:
    configures = {cle: v for cle, v in ((CLE_CRITERES, sq["acceptance_criteria_field"]), (CLE_EQUIPE, champ_equipe)) if v}
    champs = champs_demandes(sq["acceptance_criteria_field"], champ_equipe)
    tickets: dict[str, dict] = {}
    try:
        client = hj.construire_client(settings)
        verifier_champs(client, configures)
        for _, jql in requetes:
            lus, _ = eja.interroger(client, jql, champs)
            for ticket in lus:
                tickets.setdefault(str(ticket.get("key")), ticket)
    except (hj.ErreurSimple, hj.ErreurHTTP) as erreur:
        raise Refus("jira_error", 1, detail=hj.masquer(str(erreur))) from None
    genres = sq["kinds"]
    retenus = {cle: tk for cle, tk in tickets.items() if ((tk.get("fields") or {}).get("issuetype") or {}).get("name") in genres}
    vus = list(retenus)
    gardes, ecartes = eja.ecarter_hors_conservation(list(retenus.values()), jours, hj.aujourd_hui(), fuseau)
    correspondance = traduction.correspondance
    elements = []
    illisibles = 0
    for ticket in gardes:
        genre = genres[((ticket.get("fields") or {}).get("issuetype") or {}).get("name")]
        element = construire(ticket, genre, sq, champ_equipe, correspondance, nettoyeur, fuseau)
        if element is None:
            illisibles += 1
        else:
            elements.append(element)
    drapeaux = {forme_de_nom(e.nom): e.single_po for e in traduction.referentiel.teams.values()} if traduction.referentiel else {}
    absentes = {forme_de_nom(equipe) for e in elements for equipe in e.teams if forme_de_nom(equipe) not in drapeaux}
    for e in elements:                       # la désignation « (équipe inconnue) » est comptée, jamais écrite
        e.teams = [equipe for equipe in e.teams if equipe != eja.EQUIPE_INCONNUE]
    attributs = {equipe: bool(drapeaux.get(forme_de_nom(equipe), False)) for e in elements for equipe in e.teams}
    try:
        marques, revenus = magasin.enregistrer_collecte(elements, attributs, complet, vus)
    except Exception as erreur:              # la transaction est annulée par le magasin ; seul le type est écrit
        raise Refus("db_error", 1, kind=type(erreur).__name__) from None
    print(t("collect_done", n=len(elements), r=sum(e.replacements for e in elements)))
    print(t("past_retention", n=ecartes))
    if illisibles:
        print(t("unreadable_dates", n=illisibles))
    if absentes:
        print(t("teams_not_in_referential", n=len(absentes)))
    if complet:
        print(t("out_of_collection", n=marques, m=revenus))
    return 0
