# /// script
# requires-python = ">=3.11"
# dependencies = ["psycopg[binary]"]
# ///
"""
PMZilla Lab : lecture du schéma flow de la base par les outils de rapport (lot 6, docs/pmzilla/application.md, 5.3 ; change
database-only : la base est la seule source des outils de rapport).

Module de bibliothèque, sans ligne de commande. flux_jira.py, dependencies_jira.py, epic_statuses.py et segment_sample.py
l'importent à la lecture (import tardif : psycopg n'est chargé que pour la base). Les fonctions rendent :

    lire_tickets_flux(settings)  ->  (tickets, found, illisibles, doublons) : les tickets du rapport de flux
    lire_dependances(settings)   ->  le dictionnaire de la carte des dépendances (tickets, liens, colonnes, types de liens)
    lire_historique(settings)    ->  {CLÉ_MAJUSCULES: [[date ISO, départ, arrivée], ...]}, une entrée par ticket « avec historique »
    lire_donnees_cycles(settings, etiquettes_revue)  ->  une liste d'éléments (type, projet, résolution, étiquettes et versions avec
                                 leurs périodes, transitions des tickets à étiquette Epic Review) pour `flux_jira.py cycles`
    lire_epics(settings, motifs_exclus)  ->  un élément par épic (types d'épic des réglages), sans clé, pour `flux_jira.py epics`
                                 (epic-flow-report, conception D13) : instants avec le fuseau d'export, classe de la résolution,
                                 équipes dans l'ordre d'attribution, transitions, périodes des étiquettes déclarées par rôle

Connexion : db.connect() puis SET ROLE pmzilla_flow_ro (lecture seule sur les tables de flow, aucun autre rôle). Une erreur
de connexion ou de rôle est levée en ErreurBase (message sans mot de passe).

Dates : les dates sont lues dans le fuseau du réglage export_timezone (clé interne export_fuseau, Europe/Paris par défaut). La
lecture convertit « timestamptz -> même fuseau -> date naïve ». resolu_a est la date de résolution à la minute.

Les éléments hérités des fichiers reçoivent des valeurs neutres : `found` donne le premier nom de chaque colonne des réglages,
`illisibles` et `doublons` valent 0, `fichiers` vaut ["base"].
Les tickets sont rendus par projet puis par numéro de clé (ordre stable, celui d'un export trié par clé).
Les tickets marqués hors export (out_of_export_at non nul) ne sont rendus par aucun lecteur.
Les tickets sans transition figurent dans l'historique avec une liste vide (historique collecté, ticket jamais déplacé).
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import history_common as commun

ROLE_LECTURE = "pmzilla_flow_ro"
SANS_EQUIPE = "(sans équipe)"
NOM_SOURCE = "base"
SENS_BASE = {"inward": "entrant", "outward": "sortant"}
SENS_ENTETE = {"entrant": "Inward", "sortant": "Outward"}


def _erreur():
    import db
    return db.ErreurBase


def fuseau_export(settings: dict) -> ZoneInfo:
    """Fuseau des dates du CSV : la règle partagée de history_common (idée #169, D9) ; un fuseau inconnu garde l'erreur de base
    qui nomme le réglage et le fuseau."""
    try:
        return commun.fuseau_export(settings)
    except commun.ErreurFuseau as erreur:
        raise _erreur()(f"export_timezone « {erreur.nom} » n'est pas un fuseau horaire connu (exemple : {commun.FUSEAU_PAR_DEFAUT}).") from None


def ouvrir():
    """Connexion en lecture seule : db.connect() puis SET ROLE pmzilla_flow_ro. Import tardif de db (et de psycopg)."""
    import db
    conn = db.connect()
    try:
        conn.execute(f"SET ROLE {ROLE_LECTURE}")
    except Exception as erreur:
        conn.close()
        raise db.ErreurBase(f"Rôle {ROLE_LECTURE} inutilisable : {' '.join(str(erreur).split())}.") from None
    return conn


def _lire(settings: dict, requete: str, parametres: dict | None = None):
    fuseau = fuseau_export(settings)
    conn = ouvrir()
    try:
        return list(conn.execute(requete, {"tz": fuseau.key, **(parametres or {})}))
    except _erreur():
        raise
    except Exception as erreur:
        raise _erreur()(f"Lecture de la base impossible : {' '.join(str(erreur).split())}.") from None
    finally:
        conn.close()


def noms_colonnes(settings: dict) -> dict[str, str]:
    """Premier nom de chaque colonne des réglages : ce que `found` rend à la place des en-têtes d'un fichier. Des réglages sans
    colonnes (ceux de history_jira.py, qui n'ajoute pas les colonnes par défaut de flux_jira.py) donnent un dictionnaire vide (R-103)."""
    return {champ: noms[0] for champ, noms in (settings.get("colonnes") or {}).items() if noms}


REQUETE_TICKETS = """
SELECT i.key, i.project, i.type, i.status, i.status_category,
       i.created_at AT TIME ZONE %(tz)s, i.resolved_at AT TIME ZONE %(tz)s, i.status_category_changed_at AT TIME ZONE %(tz)s,
       i.resolution, i.parent_key, t1.name,
       coalesce((SELECT array_agg(t.name ORDER BY it.position) FROM flow.issue_teams it
                 JOIN flow.teams t ON t.id = it.team_id WHERE it.issue_key = i.key), ARRAY[]::text[])
FROM flow.issues i LEFT JOIN flow.teams t1 ON t1.id = i.team_id
WHERE i.out_of_export_at IS NULL
ORDER BY i.project, length(i.key), i.key
"""

# Les tickets marqués « hors export » (out_of_export_at non nul) sont écartés de chaque lecteur : un rapport de la base égale
# celui des fichiers CSV du jour. Un lien vers un ticket marqué reste dans la liste, sa cible est absente des tickets lus :
# il se lit comme un lien vers un ticket hors export, comme dans la voie CSV. Un lien dont la source est marquée disparaît.
REQUETE_LIENS = (
    "SELECT l.source_key, l.target_key, l.link_type, l.direction FROM flow.links l "
    "JOIN flow.issues s ON s.key = l.source_key WHERE s.out_of_export_at IS NULL"
)
REQUETE_HISTORIQUE = (
    "SELECT i.key, tr.transitioned_at, tr.from_status, tr.to_status FROM flow.issues i "
    "LEFT JOIN flow.transitions tr ON tr.issue_key = i.key WHERE i.has_history AND i.out_of_export_at IS NULL "
    "ORDER BY i.key, tr.transitioned_at, tr.id"
)


def _jour(moment: dt.datetime | None) -> dt.date | None:
    return moment.date() if moment else None


def lire_tickets_flux(settings: dict) -> tuple[list[dict], dict[str, str | None], int, int]:
    tickets = []
    for cle, projet, typ, etat, categorie, cree, resolu, debut, motif, _, equipe, equipes in _lire(settings, REQUETE_TICKETS):
        tickets.append({
            "cle": cle,
            "projet": projet or (cle.rsplit("-", 1)[0].upper() if "-" in cle else ""),
            "categorie": (categorie or "").strip().casefold(),
            "type": (typ or "").strip() or "?",
            "etat": (etat or "").strip(),
            "cree": _jour(cree),
            "resolu": _jour(resolu),
            "resolu_a": resolu.replace(second=0, microsecond=0) if resolu else None,
            "debut": _jour(debut),
            "equipe": equipe or SANS_EQUIPE,
            "equipes": list(equipes) or ([equipe] if equipe else []),
            "motif": (motif or "").strip(),
        })
    return tickets, noms_colonnes(settings), 0, 0


def lire_dependances(settings: dict) -> dict:
    lignes = _lire(settings, REQUETE_TICKETS)
    tickets = {}
    for cle, _, typ, etat, categorie, cree, resolu, debut, motif, parent, equipe, _ in lignes:
        tickets[cle] = {
            "type": (typ or "").strip() or "?",
            "etat": (etat or "").strip(),
            "categorie": (categorie or "").strip().casefold(),
            "cree": _jour(cree),
            "resolu": _jour(resolu),
            "debut": _jour(debut),
            "motif": (motif or "").strip(),
            "equipe": equipe or SANS_EQUIPE,
            "parent": parent or "",
        }
    liens = set()
    typees, simples = set(), False
    for source, cible, typ, sens in _lire(settings, REQUETE_LIENS):
        if typ and sens in SENS_BASE:
            liens.add((source, cible, typ, SENS_BASE[sens]))
            typees.add((typ, SENS_BASE[sens]))
        else:
            liens.add((source, cible, None, None))
            simples = True
    return {
        "tickets": tickets,
        "liens": sorted(liens, key=lambda x: (x[0], x[1], x[2] or "", x[3] or "")),
        "colonnes": noms_colonnes(settings),
        "liens_types": [(f"{SENS_ENTETE[sens]} issue link ({typ})", typ, sens) for typ, sens in sorted(typees)],
        "liens_simples": ["Linked Issues"] if simples else [],
        "fichiers": [NOM_SOURCE],
    }


def lire_historique(settings: dict) -> dict[str, list]:
    """Comme le cache de history_jira.py : une entrée par ticket « avec historique » (une entrée du cache importée, avec ou sans
    transition) ; un ticket sans entrée n'y figure pas, comme dans le cache, pour que la couverture et les dormants soient les mêmes."""
    fuseau = fuseau_export(settings)
    histoire: dict[str, list] = {}
    for cle, moment, depart, arrivee in _lire(settings, REQUETE_HISTORIQUE):
        liste = histoire.setdefault(cle.upper(), [])
        if moment is not None:
            liste.append([commun.en_fuseau(moment.isoformat(), fuseau), depart, arrivee])
    return histoire


# --- lecteurs des cycles (R-58, tâche 9.3) : périodes d'étiquettes et de versions, transitions des épics ---------------------------
# Chaque requête passe par flow.issues et écarte les tickets marqués hors export (out_of_export_at), comme les autres lecteurs.
# Les périodes ne portent que des étiquettes déclarées (jamais d'autre) ; les noms de version ne sortent pas de ce module vers un rapport.

REQUETE_ELEMENTS_CYCLES = """
SELECT i.key, i.project, i.type, i.status, i.resolved_at AT TIME ZONE %(tz)s, i.resolution
FROM flow.issues i
WHERE i.out_of_export_at IS NULL
ORDER BY i.project, length(i.key), i.key
"""
REQUETE_PERIODES_ETIQUETTES = (
    "SELECT p.issue_key, p.label, p.added_at, p.removed_at FROM flow.issue_label_periods p "
    "JOIN flow.issues i ON i.key = p.issue_key WHERE i.out_of_export_at IS NULL ORDER BY p.issue_key, p.added_at, p.label"
)
REQUETE_PERIODES_VERSIONS = (
    "SELECT p.issue_key, p.version, p.added_at, p.removed_at FROM flow.issue_version_periods p "
    "JOIN flow.issues i ON i.key = p.issue_key WHERE i.out_of_export_at IS NULL ORDER BY p.issue_key, p.added_at, p.version"
)
# transitions des seuls tickets qui ont porté une étiquette Epic Review : les autres n'ont pas besoin de statut
REQUETE_TRANSITIONS_REVUE = (
    "SELECT tr.issue_key, tr.transitioned_at, tr.from_status, tr.to_status FROM flow.transitions tr "
    "JOIN flow.issues i ON i.key = tr.issue_key WHERE i.out_of_export_at IS NULL AND tr.issue_key IN "
    "(SELECT p.issue_key FROM flow.issue_label_periods p WHERE p.label = ANY(%(etiquettes_revue)s)) "
    "ORDER BY tr.issue_key, tr.transitioned_at, tr.id"
)


def lire_donnees_cycles(settings: dict, etiquettes_revue: list[str]) -> list[dict]:
    """Éléments pour le rapport des cycles : {"cle", "projet", "type", "etat", "resolu" (jour dans le fuseau d'export),
    "motif", "labels": [(étiquette, ajoutée, retirée)], "versions": [(version, ajoutée, retirée)], "transitions":
    [(instant, départ, arrivée)]}. Les instants sont avec fuseau (timestamptz) ; `retirée` vaut None tant que la période est
    ouverte. Les transitions ne sont lues que pour les tickets qui ont porté une étiquette de `etiquettes_revue`."""
    elements: dict[str, dict] = {}
    for cle, projet, typ, etat, resolu, motif in _lire(settings, REQUETE_ELEMENTS_CYCLES):
        elements[cle] = {"cle": cle, "projet": projet or (cle.rsplit("-", 1)[0].upper() if "-" in cle else ""),
                         "type": (typ or "").strip() or "?", "etat": (etat or "").strip(), "resolu": _jour(resolu),
                         "motif": (motif or "").strip(), "labels": [], "versions": [], "transitions": []}
    for requete, champ, parametres in ((REQUETE_PERIODES_ETIQUETTES, "labels", None),
                                       (REQUETE_PERIODES_VERSIONS, "versions", None),
                                       (REQUETE_TRANSITIONS_REVUE, "transitions", {"etiquettes_revue": list(etiquettes_revue)})):
        if champ == "transitions" and not etiquettes_revue:
            continue
        for cle, a, b, c in _lire(settings, requete, parametres):
            if cle in elements:
                elements[cle][champ].append((a, b, c))
    return list(elements.values())


# --- lecteur des épics (epic-flow-report, conception D13, tâche 5.1) ---------------------------------------------------------------
# Chaque requête passe par flow.issues, écarte les tickets marqués hors export et ne garde que les types d'épic des réglages. La clé ne
# sert qu'à relier les lignes dans ce module et ne sort jamais ; le texte d'une étiquette ne sert qu'à lui trouver son rôle.

REQUETE_EPICS = """
SELECT i.key, i.project, i.type, i.status, i.created_at, i.resolved_at, i.resolution, i.has_history, t1.name
FROM flow.issues i LEFT JOIN flow.teams t1 ON t1.id = i.team_id
WHERE i.out_of_export_at IS NULL AND lower(i.type) = ANY(%(types)s)
ORDER BY i.project, length(i.key), i.key
"""
REQUETE_EQUIPES_EPICS = (
    "SELECT it.issue_key, t.name FROM flow.issue_teams it JOIN flow.teams t ON t.id = it.team_id "
    "JOIN flow.issues i ON i.key = it.issue_key WHERE i.out_of_export_at IS NULL AND lower(i.type) = ANY(%(types)s) "
    "ORDER BY it.issue_key, it.position"
)
REQUETE_TRANSITIONS_EPICS = (
    "SELECT tr.issue_key, tr.transitioned_at, tr.from_status, tr.to_status FROM flow.transitions tr "
    "JOIN flow.issues i ON i.key = tr.issue_key WHERE i.out_of_export_at IS NULL AND lower(i.type) = ANY(%(types)s) "
    "ORDER BY tr.issue_key, tr.transitioned_at, tr.id"
)
REQUETE_PERIODES_EPICS = (
    "SELECT p.issue_key, p.label, p.added_at, p.removed_at FROM flow.issue_label_periods p "
    "JOIN flow.issues i ON i.key = p.issue_key WHERE i.out_of_export_at IS NULL AND lower(i.type) = ANY(%(types)s) "
    "AND p.label = ANY(%(etiquettes)s) ORDER BY p.issue_key, p.added_at, p.label"
)


def roles_des_etiquettes(settings: dict) -> dict[str, dict]:
    """{texte de l'étiquette: {"role", "cycle", "sens"}} pour les étiquettes déclarées de tous les rôles. `cycle` : clé de cycle d'une
    étiquette de cycle (ou None), `sens` : sens d'une étiquette de confirmation (ou None)."""
    import flux_config as cfg
    roles: dict[str, dict] = {}
    for role, contenu in (cfg.declared_labels(settings) or {}).items():
        for etiquette in contenu["labels"]:
            roles[etiquette] = {"role": role, "cycle": (contenu.get("cycle_keys") or {}).get(etiquette),
                                "sens": (contenu.get("meanings") or {}).get(etiquette)}
    return roles


def lire_epics(settings: dict, motifs_exclus) -> list[dict]:
    """Un élément par épic : {"type", "projet", "etat", "cree", "resolu" (instants avec le fuseau d'export), "classe" ("done" ou
    "not_done" d'après `motifs_exclus`, None sans résolution ; jamais le texte de la résolution), "equipes" (ordre d'attribution), "transitions"
    [(instant, départ, arrivée)], "a_historique", "periodes" [{"role", "cycle", "sens", "ajout", "retrait"}]}. Aucune clé, aucun texte
    d'étiquette. `motifs_exclus` : les résolutions « non faites » en minuscules."""
    import flux_config as cfg
    fuseau = fuseau_export(settings)
    parametres = {"types": [t.strip().casefold() for t in cfg.epic_types(settings)]}
    exclus = {m.casefold() for m in motifs_exclus}
    epics: dict[str, dict] = {}
    for cle, projet, typ, etat, cree, resolu, motif, historique, premiere in _lire(settings, REQUETE_EPICS, parametres):
        epics[cle] = {"type": (typ or "").strip() or "?", "projet": projet or (cle.rsplit("-", 1)[0].upper() if "-" in cle else ""),
                      "etat": (etat or "").strip(), "cree": cree.astimezone(fuseau) if cree else None,
                      "resolu": resolu.astimezone(fuseau) if resolu else None,
                      "classe": None if not resolu else ("not_done" if (motif or "").strip().casefold() in exclus else "done"),
                      "equipes": [], "transitions": [], "a_historique": bool(historique), "periodes": [], "_premiere": premiere}
    for cle, nom in _lire(settings, REQUETE_EQUIPES_EPICS, parametres):
        if cle in epics:
            epics[cle]["equipes"].append(nom)
    for cle, instant, depart, arrivee in _lire(settings, REQUETE_TRANSITIONS_EPICS, parametres):
        if cle in epics:
            epics[cle]["transitions"].append((instant.astimezone(fuseau), depart, arrivee))
    roles = roles_des_etiquettes(settings)
    if roles:
        for cle, etiquette, ajout, retrait in _lire(settings, REQUETE_PERIODES_EPICS, {**parametres, "etiquettes": list(roles)}):
            if cle in epics and etiquette in roles:
                epics[cle]["periodes"].append({**roles[etiquette], "ajout": ajout.astimezone(fuseau),
                                               "retrait": retrait.astimezone(fuseau) if retrait else None})
    for epic in epics.values():       # première équipe de l'attribution quand le ticket n'a pas de ligne dans la table des équipes
        premiere = epic.pop("_premiere")
        if not epic["equipes"] and premiere:
            epic["equipes"] = [premiere]
    return list(epics.values())
