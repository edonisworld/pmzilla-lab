"""
PMZilla Lab : couche brute datée de l'export Jira, dans le schéma flow (change jira-data-architecture, R-70, design D3 à D6).

Module de bibliothèque, sans ligne de commande. Trois entités (migration flow_raw_layer) :
  - passage (flow.raw_runs) : un par export réussi, un par amorçage ; instant, nombre de requêtes nommées lues, toutes lues ou non ;
  - visite (flow.raw_run_sightings) : une clé de ticket lue par un passage, après l'écart de conservation ;
  - instantané (flow.raw_issue_snapshots) : les attributs autorisés d'un ticket (projet, type, état, catégorie, dates, résolution,
    story points, parent, équipes dans l'ordre avec leur identifiant d'équipe Jira, liens ou « non suivis »), écrit pour un ticket
    nouveau ou quand son empreinte change, avec les noms de ses versions courantes (fix et affects) et, pour chacune, sa date de sortie et
    son drapeau de sortie, sans autre attribut (base seulement, jamais affichés, aucune valeur).
    Jamais de titre, de description, de personne ni d'étiquette.

Écrit par l'export (MagasinBase.enregistrer, une transaction, sous le rôle d'import) ; lu par la reconstruction de flow_import.py
(`reconstruire`, `amorcer`). La couche brute est en ajout seulement : seule la purge de conservation (flow_retention.py) supprime.
Les fonctions pures (instantane, empreinte, choisir, champs_differents) ne touchent ni la base ni le disque. Aucune sortie ne porte
une clé, un nom d'équipe, un identifiant ni une valeur.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from decimal import Decimal

import flow_delivery

LOT = 500
LOT_CLES = 2000

# Noms neutres des champs comptés par la reconstruction (design D11) ; « ticket » : la ligne vivante manque.
CHAMPS = ("ticket", "status", "status category", "type", "resolution", "dates", "story points", "parent", "team", "teams", "links",
          "versions", "delivery")
GENRES_VERSION = ("fix", "affects")          # les deux genres de versions courantes (change flow-version-share, design D1)

COLONNES_INSTANTANE = ("issue_key", "run_id", "updated_at", "project", "type", "status", "status_category", "created_at",
                       "resolved_at", "resolution", "status_category_changed_at", "story_points", "parent_key", "teams", "links",
                       "content_hash", "current_versions", "delivery", "seeded")


class Refus(Exception):
    """Reconstruction refusée avant toute écriture : `code` est la clé de la phrase fixe, `valeurs` ses champs (des effectifs)."""

    def __init__(self, code: str, **valeurs):
        super().__init__(code)
        self.code, self.valeurs = code, valeurs


# ---------------------------------------------------------------------------------------------------------------------------------
# Fonctions pures
# ---------------------------------------------------------------------------------------------------------------------------------

def _instant(valeur: dt.datetime | None) -> str | None:
    return None if valeur is None else valeur.astimezone(dt.timezone.utc).isoformat()


def _nombre(valeur) -> str | None:
    return None if valeur is None else format(Decimal(str(valeur)).normalize(), "f")


def equipes_instantane(noms: list[str], paires: list[tuple[str, str | None]] | None, separateur: str = ";") -> list[dict]:
    """Équipes d'un instantané, dans l'ordre : nom traduit et identifiant d'équipe Jira (None pour un libellé ou un nom découpé).
    `noms` : les équipes lues dans le CSV (secours quand on n'a pas les paires) ; `paires` : (nom, identifiant) de l'export, un nom
    qui réunit plusieurs équipes autour du séparateur est découpé comme le fait le lecteur du CSV, sans identifiant."""
    if paires is None:
        return [{"name": nom, "jira_team_id": None} for nom in noms]
    equipes: list[dict] = []
    for nom, identifiant in paires:
        morceaux = [m.strip() for m in nom.split(separateur) if m.strip()]
        if len(morceaux) == 1:
            equipes.append({"name": morceaux[0], "jira_team_id": identifiant})
        else:
            equipes += [{"name": m, "jira_team_id": None} for m in morceaux]
    return equipes


def empreinte(instantane: dict) -> str:
    """Empreinte du contenu d'un instantané : attributs, équipes avec identifiants, liens (triés) ; la date de mise à jour en fait
    partie (la reconstruction compare aussi les dates). Stable d'un export à l'autre pour le même contenu."""
    liens = instantane.get("links")
    versions = instantane.get("current_versions")
    contenu = {
        "project": instantane["project"], "type": instantane["type"], "status": instantane["status"],
        "status_category": instantane.get("status_category"), "created_at": _instant(instantane["created_at"]),
        "resolved_at": _instant(instantane.get("resolved_at")), "resolution": instantane.get("resolution"),
        "status_category_changed_at": _instant(instantane.get("status_category_changed_at")),
        "story_points": _nombre(instantane.get("story_points")), "updated_at": _instant(instantane["updated_at"]),
        "parent_key": instantane.get("parent_key"),
        "teams": [[e["name"], e.get("jira_team_id")] for e in instantane.get("teams") or []],
        "links": None if liens is None else sorted([l["target"], l["type"], l["direction"]] for l in liens),
    }
    if versions and any(versions.get(genre) for genre in GENRES_VERSION):          # design D2 : sans nom de version, l'empreinte d'avant
        contenu["versions"] = {genre: sorted(versions.get(genre) or []) for genre in GENRES_VERSION}
        # change version-release-date, design D3 : date de sortie et drapeau de chaque nom, dès qu'il y a un nom de version ; la clé est
        # toujours écrite (None sans attributs suivis) : le premier export après le change réécrit un instantané par ticket avec version
        sortie = versions.get("release")
        contenu["release"] = None if sortie is None else {
            nom: [(sortie[nom] or {}).get("date"), (sortie[nom] or {}).get("released")] for nom in sorted(sortie)}
    if instantane.get("delivery"):          # jira-delivery-fields D3 : sans champ de livraison la clé est absente et l'empreinte d'avant demeure
        contenu["delivery"] = flow_delivery.canonique(instantane["delivery"])
    return hashlib.sha256(json.dumps(contenu, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def instantane(ticket: dict, paires: list[tuple[str, str | None]] | None = None, separateur: str = ";") -> dict:
    """Instantané d'un ticket lu par l'export de l'API (ses clés : cle, projet, type, etat, categorie, cree, resolu, motif, debut,
    points, modifie, parent, equipes, liens). `paires` : (nom, identifiant d'équipe Jira) dans l'ordre des colonnes de l'export."""
    liens = None if ticket["liens"] is None else [{"target": a, "type": t, "direction": d} for a, t, d in ticket["liens"]]
    resultat = {
        "issue_key": ticket["cle"], "updated_at": ticket["modifie"], "project": ticket["projet"], "type": ticket["type"],
        "status": ticket["etat"], "status_category": ticket["categorie"], "created_at": ticket["cree"],
        "resolved_at": ticket["resolu"], "resolution": ticket["motif"], "status_category_changed_at": ticket["debut"],
        "story_points": ticket["points"], "parent_key": ticket["parent"],
        "teams": equipes_instantane(ticket["equipes"], paires, separateur), "links": liens,
        "current_versions": ticket.get("versions"),          # {"fix": [...], "affects": [...]} ou None (non suivi)
        "delivery": ticket.get("delivery"),          # champs de livraison réduits (jira-delivery-fields D1), ou None
    }
    resultat["content_hash"] = empreinte(resultat)
    return resultat


def conserver_livraison(instantanes: dict[str, dict], livraisons: dict[str, dict | None]) -> None:
    """Reprend, pour chaque ticket dont `livraisons` (clé -> partie `delivery` du dernier instantané stocké) porte une entrée, cette partie
    `delivery` dans l'instantané et recalcule son empreinte. Sert à l'export SANS table des champs de livraison (R-20261114-108, décision
    R-20261114-89 C2) : l'empreinte et les lignes courantes de livraison restent celles du dernier export avec table, aucun instantané
    n'est écrit pour cette seule raison et la réconciliation de livraison ne trouve aucun écart. Remplace : rien ; retrait : permanent."""
    for cle, instantane_ in instantanes.items():
        if cle in livraisons:
            instantane_["delivery"] = livraisons[cle]
            instantane_["content_hash"] = empreinte(instantane_)


def choisir(instantanes: dict[str, dict], derniers: dict[str, tuple]) -> list[dict]:
    """Instantanés à écrire : un ticket nouveau, ou dont l'empreinte diffère de son dernier instantané. Jamais un instantané dont
    l'instant de mise à jour précède celui du dernier. `derniers` : clé -> (instant de mise à jour, empreinte)."""
    a_ecrire = []
    for cle, instantane_ in instantanes.items():
        dernier = derniers.get(cle)
        if dernier is None:
            a_ecrire.append(instantane_)
        elif instantane_["updated_at"] < dernier[0]:
            continue
        elif instantane_["content_hash"] != dernier[1]:
            a_ecrire.append(instantane_)
    return a_ecrire


def _noms_dedoubles(equipes: list[dict]) -> list[str]:
    return list(dict.fromkeys(e["name"] for e in equipes))


def champs_differents(snap: dict, vivant: dict | None) -> list[str]:
    """Champs (noms neutres de CHAMPS) où la ligne vivante diffère de l'instantané. `vivant` : None si le ticket n'est pas stocké ;
    sinon status, status_category, type, resolution, created_at, resolved_at, status_category_changed_at, updated_at, story_points,
    parent_key, team (première équipe), teams (noms dans l'ordre), links (ensemble de (cible, type, sens), ou None si on ne compare
    pas les liens). Aucune valeur n'est rendue."""
    if vivant is None:
        return ["ticket"]
    noms = _noms_dedoubles(snap["teams"])
    diff = []
    for champ, cle in (("status", "status"), ("status category", "status_category"), ("type", "type"),
                       ("resolution", "resolution"), ("parent", "parent_key")):
        if (snap[cle] or None) != (vivant[cle] or None):
            diff.append(champ)
    if any(snap[c] != vivant[c] for c in ("created_at", "resolved_at", "status_category_changed_at", "updated_at")):
        diff.append("dates")
    if (None if snap["story_points"] is None else Decimal(str(snap["story_points"]))) != vivant["story_points"]:
        diff.append("story points")
    if (noms[0] if noms else None) != vivant["team"]:
        diff.append("team")
    if noms != vivant["teams"]:
        diff.append("teams")
    if vivant["links"] is not None and snap["links"] is not None and vivant["links"] != {
            (l["target"], l["type"], l["direction"]) for l in snap["links"]}:
        diff.append("links")
    voulues = _versions_voulues(snap)
    if voulues is not None and vivant.get("versions") is not None and voulues != {_complete(v) for v in vivant["versions"]}:
        diff.append("versions")
    if vivant.get("livraison") is not None:          # jira-delivery-fields D3 : les lignes voulues du dernier instantané contre les lignes vivantes
        attendu = flow_delivery.lignes_de(snap["issue_key"], snap.get("delivery"))
        if any(attendu[genre] != lignes for genre, lignes in vivant["livraison"].items()):
            diff.append("delivery")
    return [c for c in CHAMPS if c in diff]


# ---------------------------------------------------------------------------------------------------------------------------------
# Écriture par l'export
# ---------------------------------------------------------------------------------------------------------------------------------

def _par_lots(elements: list, taille: int):
    for debut in range(0, len(elements), taille):
        yield elements[debut:debut + taille]


def _parametres_instantane(i: dict, run_id: int, seeded: bool):
    from psycopg.types.json import Jsonb
    return (i["issue_key"], run_id, i["updated_at"], i["project"], i["type"], i["status"], i["status_category"], i["created_at"],
            i["resolved_at"], i["resolution"], i["status_category_changed_at"], i["story_points"], i["parent_key"],
            Jsonb(i["teams"]), None if i["links"] is None else Jsonb(i["links"]), i["content_hash"],
            None if i.get("current_versions") is None else Jsonb(i["current_versions"]),
            Jsonb(i["delivery"]) if i.get("delivery") else None, seeded)


SQL_INSERTION_INSTANTANE = (
    f"INSERT INTO flow.raw_issue_snapshots ({', '.join(COLONNES_INSTANTANE)}) "
    f"VALUES ({', '.join(['%s'] * len(COLONNES_INSTANTANE))})")
SQL_DERNIERS = ("SELECT DISTINCT ON (issue_key) issue_key, updated_at, content_hash FROM flow.raw_issue_snapshots "
                "WHERE issue_key = ANY(%s) ORDER BY issue_key, run_id DESC")
SQL_DERNIERES_EMPREINTES_VERSION = ("SELECT DISTINCT ON (object_id) object_id, content_hash FROM flow.raw_version_snapshots "
                                    "WHERE object_id = ANY(%s) ORDER BY object_id, run_id DESC")


def empreinte_version(contenu: dict) -> str:
    """Empreinte du contenu d'une version (nom court, état, catégorie, Started, Released) : stable d'un export à l'autre."""
    return hashlib.sha256(json.dumps(contenu, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


class MagasinBase:
    """Magasin de la couche brute dans la base, sous le rôle d'import (connexion ouverte par l'appelant). Une erreur de la base
    remonte telle quelle : l'appelant n'en affiche que le type."""

    def __init__(self, conn):
        self.conn = conn
        self.sans_type = 0          # après un enregistrement avec types_equipes : équipes rencontrées dont la colonne du type est nulle

    def enregistrer(self, *, genre: str, nb_requetes: int, toutes: bool, vus: list[str], instantanes: dict[str, dict],
                    types_equipes: dict[str, str | None] | None = None, versions: dict[str, dict] | None = None,
                    livraison_conservee: bool = False):
        """Écrit un passage, ses visites et les instantanés à ajouter, en UNE transaction (annulée en cas d'erreur).
        `types_equipes` (nom d'équipe -> type ou None, database-only, complément du type d'équipe) : dans la même transaction, crée
        l'équipe qui manque et n'écrit la colonne du type que pour un type connu et différent de celui de la base (jamais un type nul
        par-dessus un type écrit) ; `self.sans_type` compte ensuite les équipes rencontrées au type nul. `versions` (change
        jira-delivery-fields, D3) : objet d'actif -> contenu (nom court, état, catégorie, Started, Released) lu des tickets de version ;
        dans la même transaction, un instantané de version est ajouté quand le contenu diffère du dernier, et la dernière vue des versions
        déjà dérivées avance. Rend (clés vues, instantanés ajoutés)."""
        cur = self.conn.cursor()
        try:
            derniers: dict[str, tuple] = {}
            for lot in _par_lots(list(instantanes), LOT_CLES):
                for cle, instant, empreinte_ in cur.execute(SQL_DERNIERS, (lot,)).fetchall():
                    derniers[cle] = (instant, empreinte_)
            if livraison_conservee:          # export sans table des champs de livraison : la livraison déjà stockée est reprise telle quelle
                livraisons: dict[str, dict | None] = {}
                for lot in _par_lots(list(instantanes), LOT_CLES):
                    for cle, livraison in cur.execute(SQL_DERNIERES_LIVRAISONS_DES_CLES, (lot,)).fetchall():
                        livraisons[cle] = livraison
                conserver_livraison(instantanes, livraisons)
            a_ajouter = choisir(instantanes, derniers)
            run_id = cur.execute("INSERT INTO flow.raw_runs (kind, queries_searched, all_queries) VALUES (%s, %s, %s) RETURNING id",
                                 (genre, nb_requetes, toutes)).fetchone()[0]
            uniques = list(dict.fromkeys(vus))
            for lot in _par_lots(uniques, 5000):
                cur.execute("INSERT INTO flow.raw_run_sightings (run_id, issue_key) SELECT %s::bigint, unnest(%s::text[])", (run_id, lot))
            for lot in _par_lots(a_ajouter, LOT):
                cur.executemany(SQL_INSERTION_INSTANTANE, [_parametres_instantane(i, run_id, False) for i in lot])
            if types_equipes is not None:
                self.sans_type = self._ecrire_types(cur, types_equipes)
            if versions:
                self._ecrire_versions(cur, run_id, versions)
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise
        return len(uniques), len(a_ajouter)

    @staticmethod
    def _ecrire_versions(cur, run_id: int, versions: dict[str, dict]) -> int:
        """Un instantané par objet dont le contenu diffère du dernier (ajout seulement), puis la dernière vue des références déjà dérivées.
        Rend le nombre d'instantanés ajoutés. Aucune clé ni résumé de ticket de version : le contenu porte cinq attributs."""
        from psycopg.types.json import Jsonb
        objets = list(versions)
        derniers = dict(cur.execute(SQL_DERNIERES_EMPREINTES_VERSION, (objets,)).fetchall())
        ajoutes = [(run_id, objet, Jsonb(versions[objet]), empreinte_version(versions[objet])) for objet in objets
                   if derniers.get(objet) != empreinte_version(versions[objet])]
        if ajoutes:
            cur.executemany("INSERT INTO flow.raw_version_snapshots (run_id, object_id, content, content_hash) VALUES (%s, %s, %s, %s)",
                            ajoutes)
        cur.execute("UPDATE flow.release_versions SET last_seen = now() WHERE object_id = ANY(%s)", (objets,))
        return len(ajoutes)

    @staticmethod
    def _ecrire_types(cur, types_equipes: dict[str, str | None]) -> int:
        """Crée les équipes qui manquent (avec leur type connu), met à jour la colonne du type seulement quand un type connu diffère,
        rend le nombre d'équipes rencontrées au type nul après l'écriture."""
        noms = list(types_equipes)
        if not noms:
            return 0
        existantes = dict(cur.execute("SELECT name, team_type FROM flow.teams WHERE name = ANY(%s)", (noms,)).fetchall())
        manquantes = [nom for nom in noms if nom not in existantes]
        if manquantes:
            cur.execute("INSERT INTO flow.teams (name, team_type) SELECT * FROM unnest(%s::text[], %s::text[]) ON CONFLICT (name) DO NOTHING",
                        (manquantes, [types_equipes[nom] for nom in manquantes]))
        changees = [nom for nom, ancien in existantes.items() if types_equipes[nom] is not None and types_equipes[nom] != ancien]
        if changees:
            cur.execute("UPDATE flow.teams t SET team_type = d.team_type FROM unnest(%s::text[], %s::text[]) AS d(name, team_type) "
                        "WHERE t.name = d.name AND t.team_type IS DISTINCT FROM d.team_type",
                        (changees, [types_equipes[nom] for nom in changees]))
        return cur.execute("SELECT count(*) FROM flow.teams WHERE name = ANY(%s) AND team_type IS NULL", (noms,)).fetchone()[0]

    def fermer(self) -> None:
        self.conn.close()


# ---------------------------------------------------------------------------------------------------------------------------------
# Lecture : reconstruction et amorçage (flow_import.py --rebuild), sous le rôle d'import
# ---------------------------------------------------------------------------------------------------------------------------------

SQL_DERNIERS_COMPLETS = (
    "SELECT DISTINCT ON (issue_key) issue_key, project, type, status, status_category, created_at, resolved_at, resolution, "
    "status_category_changed_at, story_points, updated_at, parent_key, teams FROM flow.raw_issue_snapshots "
    "ORDER BY issue_key, run_id DESC")
SQL_DERNIERS_LIENS = ("SELECT DISTINCT ON (issue_key) issue_key, links FROM flow.raw_issue_snapshots WHERE links IS NOT NULL "
                      "ORDER BY issue_key, run_id DESC")
SQL_VIVANT = ("SELECT i.key, i.project, i.type, i.status, i.status_category, i.created_at, i.resolved_at, i.resolution, "
              "i.status_category_changed_at, i.story_points, i.updated_at, i.parent_key, t.name FROM flow.issues i "
              "LEFT JOIN flow.teams t ON t.id = i.team_id")
SQL_EQUIPES_VIVANTES = ("SELECT it.issue_key, t.name FROM flow.issue_teams it JOIN flow.teams t ON t.id = it.team_id "
                        "ORDER BY it.issue_key, it.position")
SQL_LIENS_VIVANTS = "SELECT source_key, target_key, link_type, direction FROM flow.links"
# Versions courantes (change flow-version-share) : le dernier instantané de chaque ticket, même si sa colonne est nulle (un instantané
# d'avant le suivi des versions) ; la dérivation laisse alors les lignes vivantes telles quelles. Puis les lignes vivantes. Les noms ne
# sortent jamais d'ici.
SQL_DERNIERES_VERSIONS = ("SELECT DISTINCT ON (issue_key) issue_key, current_versions FROM flow.raw_issue_snapshots "
                          "ORDER BY issue_key, run_id DESC")
SQL_VERSIONS_VIVANTES = "SELECT issue_key, kind, name, release_date, released FROM flow.issue_current_versions"
# Champs de livraison (change jira-delivery-fields, D3) : la partie `delivery` du dernier instantané de chaque ticket, puis les lignes
# vivantes des tables courantes. Aucune valeur n'en sort.
SQL_DERNIERES_LIVRAISONS_DES_CLES = ("SELECT DISTINCT ON (issue_key) issue_key, delivery FROM flow.raw_issue_snapshots "
                                     "WHERE issue_key = ANY(%s) ORDER BY issue_key, run_id DESC")          # export sans table (conserver_livraison)
SQL_DERNIERES_LIVRAISONS = ("SELECT DISTINCT ON (issue_key) issue_key, delivery FROM flow.raw_issue_snapshots "
                            "ORDER BY issue_key, run_id DESC")          # le DERNIER instantané : un delivery nul vide les lignes du ticket
SQL_LIVRAISON_CHAMPS = ("SELECT issue_key, release_target_id, verification_required_id, product_safety_id, isp_id, code_review_status_id, "
                        "portfolio_rank, customer_commitment, source_commitment, strategic_objective FROM flow.issue_delivery_fields")
SQL_LIVRAISON_SPRINTS = ("SELECT c.issue_key, s.sprint_id, s.state, s.start_date, s.end_date, s.complete_date "
                         "FROM flow.issue_current_sprints c JOIN flow.sprints s ON s.sprint_id = c.sprint_id")
SQL_LIVRAISON_ACTIFS = "SELECT issue_key, kind, object_id FROM flow.issue_current_asset_versions"
SQL_LIVRAISON_OPTIONS = "SELECT issue_key, field, position, option_id FROM flow.issue_delivery_options"          # identifiant d'option seul (R-20261102-51)
SQL_LIVRAISON_DEFAUTS = ("SELECT issue_key, detection_phase_id, detection_phase, detected_by_id, installed_base_id "
                         "FROM flow.issue_defect_fields")          # detection_phase : code fermé ; jamais une valeur libre
CLES_LIVRAISON = (("fields", SQL_LIVRAISON_CHAMPS), ("sprints", SQL_LIVRAISON_SPRINTS), ("assets", SQL_LIVRAISON_ACTIFS),
                  ("options", SQL_LIVRAISON_OPTIONS), ("defect", SQL_LIVRAISON_DEFAUTS))
# Références de version : le dernier instantané de chaque objet (avec l'instant du passage), puis les lignes vivantes.
SQL_DERNIERES_VERSIONS_BRUTES = ("SELECT DISTINCT ON (s.object_id) s.object_id, s.content, r.run_at FROM flow.raw_version_snapshots s "
                                 "JOIN flow.raw_runs r ON r.id = s.run_id ORDER BY s.object_id, s.run_id DESC")
SQL_REFERENCES_VIVANTES = "SELECT object_id, short_name, status, status_category, started, released FROM flow.release_versions"
SQL_VERSIONS_SANS_TICKET = ("SELECT count(DISTINCT a.object_id) FROM flow.issue_current_asset_versions a "
                            "WHERE NOT EXISTS (SELECT 1 FROM flow.release_versions v WHERE v.object_id = a.object_id)")
COLONNES_COMPARAISON = ("project", "type", "status", "status_category", "created_at", "resolved_at", "resolution",
                        "status_category_changed_at", "story_points", "updated_at", "parent_key")


def _derniers_instantanes(cur) -> dict[str, dict]:
    instantanes = {}
    for ligne in cur.execute(SQL_DERNIERS_COMPLETS).fetchall():
        instantanes[ligne[0]] = dict(zip(("issue_key",) + COLONNES_COMPARAISON + ("teams",), ligne))
    for cle, liens in cur.execute(SQL_DERNIERS_LIENS).fetchall():
        instantanes[cle]["links"] = liens
    for instantane_ in instantanes.values():
        instantane_.setdefault("links", None)
        instantane_.setdefault("current_versions", None)
    for cle, versions in cur.execute(SQL_DERNIERES_VERSIONS).fetchall():
        if cle in instantanes and versions is not None:
            instantanes[cle]["current_versions"] = versions
    for instantane_ in instantanes.values():
        instantane_.setdefault("delivery", None)
    for cle, livraison in cur.execute(SQL_DERNIERES_LIVRAISONS).fetchall():
        if cle in instantanes:
            instantanes[cle]["delivery"] = livraison
    return instantanes


def _date_de_sortie(texte) -> dt.date | None:
    """La date de sortie d'un instantané (texte ISO) ; None sans date ou si elle est illisible. Jamais affichée."""
    if isinstance(texte, dt.date):
        return texte
    try:
        return dt.date.fromisoformat(texte) if isinstance(texte, str) else None
    except ValueError:
        return None


def _versions_voulues(snap: dict) -> set[tuple[str, str, dt.date | None, bool | None]] | None:
    """Les versions courantes d'un instantané comme ensemble de (genre, nom, date de sortie, drapeau « sortie »), ou None quand il ne les suit
    pas. Un instantané sans la clé `release` (écrit avant le change version-release-date) donne des attributs nuls (design D4)."""
    versions = snap.get("current_versions")
    if versions is None:
        return None
    sortie = versions.get("release") or {}
    voulues = set()
    for genre in GENRES_VERSION:
        for nom in versions.get(genre) or []:
            attributs = sortie.get(nom) or {}
            drapeau = attributs.get("released")
            voulues.add((genre, nom, _date_de_sortie(attributs.get("date")), drapeau if isinstance(drapeau, bool) else None))
    return voulues


def _complete(version: tuple) -> tuple:
    """Une version vivante (genre, nom) ou (genre, nom, date, drapeau) comme un quadruplet : les attributs absents sont nuls."""
    return tuple(version) + (None,) * (4 - len(version))


def _vivant(cur) -> dict[str, dict]:
    vivant = {}
    for ligne in cur.execute(SQL_VIVANT).fetchall():
        entree = dict(zip(("key",) + COLONNES_COMPARAISON + ("team",), ligne))
        entree.update(teams=[], links=set(), versions=set())
        vivant[ligne[0]] = entree
    for cle, nom in cur.execute(SQL_EQUIPES_VIVANTES).fetchall():
        if cle in vivant:
            vivant[cle]["teams"].append(nom)
    for source, cible, type_, sens in cur.execute(SQL_LIENS_VIVANTS).fetchall():
        if source in vivant:
            vivant[source]["links"].add((cible, type_, sens))
    for cle, genre, nom, date_sortie, sortie in cur.execute(SQL_VERSIONS_VIVANTES).fetchall():
        if cle in vivant:
            vivant[cle]["versions"].add((genre, nom, date_sortie, sortie))
    for entree in vivant.values():
        entree["livraison"] = {genre: set() for genre, _ in CLES_LIVRAISON}
    for genre, sql in CLES_LIVRAISON:
        for ligne in cur.execute(sql).fetchall():
            if ligne[0] in vivant:
                vivant[ligne[0]]["livraison"][genre].add(tuple(ligne))
    return vivant


def _a_comparer(vivant: dict | None, snap: dict) -> dict | None:
    """La ligne vivante telle que champs_differents la lit : les liens ne se comparent que si l'instantané les suit."""
    if vivant is None:
        return None
    return {**vivant, "links": vivant["links"] if snap["links"] is not None else None}


def reconstruire(conn, appliquer: bool = False) -> dict:
    """Compare l'état reconstruit depuis le dernier instantané de chaque ticket aux tables vivantes (tickets, équipes par ticket,
    liens) ; avec `appliquer`, écrit les différences en UNE transaction. Rend {"compares", "changeraient", "champs": {nom: n},
    "modifies"}. Lève Refus avant toute écriture si la couche brute est vide ou si des tickets stockés n'ont aucun instantané.
    Ne touche ni les instants de sortie de l'export, ni les transitions, ni l'indicateur d'historique, ni les périodes ; ne
    supprime aucune équipe ; ne lit pas le référentiel d'organisation."""
    cur = conn.cursor()
    try:
        instantanes = _derniers_instantanes(cur)
        if not instantanes:
            raise Refus("raw_empty")
        vivant = _vivant(cur)
        sans_instantane = sum(1 for cle in vivant if cle not in instantanes)
        if sans_instantane:
            raise Refus("no_snapshot", n=sans_instantane)
        champs: dict[str, int] = {}
        a_changer: list[tuple[str, list[str]]] = []
        for cle, snap in instantanes.items():
            diff = champs_differents(snap, _a_comparer(vivant.get(cle), snap))
            if diff:
                a_changer.append((cle, diff))
                for champ in diff:
                    champs[champ] = champs.get(champ, 0) + 1
        resultat = {"compares": len(instantanes), "changeraient": len(a_changer),
                    "champs": {c: champs[c] for c in CHAMPS if c in champs}, "modifies": 0}
        if appliquer and a_changer:
            _appliquer(cur, [(instantanes[cle], diff) for cle, diff in a_changer], vivant)
            resultat["modifies"] = len(a_changer)
        conn.commit()
        return resultat
    except BaseException:
        conn.rollback()
        raise


def _appliquer(cur, changements: list[tuple[dict, list[str]]], vivant: dict) -> tuple[int, int, int]:
    """Écrit les tickets, leurs équipes et leurs liens qui diffèrent. Les équipes manquantes sont créées, aucune n'est supprimée.
    Rend (équipes créées, liens ajoutés, liens retirés) : des effectifs seulement."""
    noms = list(dict.fromkeys(nom for snap, _ in changements for nom in _noms_dedoubles(snap["teams"])))
    ids = dict(cur.execute("SELECT name, id FROM flow.teams").fetchall())
    manquants = [nom for nom in noms if nom not in ids]
    equipes_creees = liens_ajoutes = liens_retires = 0
    if manquants:
        equipes_creees = cur.execute("INSERT INTO flow.teams (name) SELECT unnest(%s::text[]) ON CONFLICT (name) DO NOTHING",
                                     (manquants,)).rowcount
        ids = dict(cur.execute("SELECT name, id FROM flow.teams").fetchall())
    for snap, diff in changements:
        cle = snap["issue_key"]
        equipes = _noms_dedoubles(snap["teams"])
        cur.execute(
            "INSERT INTO flow.issues AS i (key, project, type, status, status_category, created_at, resolved_at, resolution, "
            "status_category_changed_at, story_points, updated_at, team_id, parent_key) "
            "VALUES (" + ", ".join(["%s"] * 13) + ") "   # marqueurs construits : treize %s à la suite comptent comme un texte de livre pour build_edition
            "ON CONFLICT (key) DO UPDATE SET project = EXCLUDED.project, type = EXCLUDED.type, status = EXCLUDED.status, "
            "status_category = EXCLUDED.status_category, created_at = EXCLUDED.created_at, resolved_at = EXCLUDED.resolved_at, "
            "resolution = EXCLUDED.resolution, status_category_changed_at = EXCLUDED.status_category_changed_at, "
            "story_points = EXCLUDED.story_points, updated_at = EXCLUDED.updated_at, team_id = EXCLUDED.team_id, "
            "parent_key = EXCLUDED.parent_key",
            (cle, snap["project"], snap["type"], snap["status"], snap["status_category"], snap["created_at"],
             snap["resolved_at"], snap["resolution"], snap["status_category_changed_at"], snap["story_points"],
             snap["updated_at"], ids[equipes[0]] if equipes else None, snap["parent_key"]))
        if "ticket" in diff or "teams" in diff or "team" in diff:
            cur.execute("DELETE FROM flow.issue_teams WHERE issue_key = %s", (cle,))
            for position, nom in enumerate(equipes, 1):
                cur.execute("INSERT INTO flow.issue_teams (issue_key, team_id, position) VALUES (%s, %s, %s)",
                            (cle, ids[nom], position))
        if snap["links"] is not None and ("ticket" in diff or "links" in diff):
            voulu = {(l["target"], l["type"], l["direction"]) for l in snap["links"]}
            existant = (vivant.get(cle) or {}).get("links") or set()
            liens_ajoutes += len(voulu - existant)
            liens_retires += len(existant - voulu)
            cur.execute("DELETE FROM flow.links WHERE source_key = %s", (cle,))
            for cible, type_, sens in sorted(voulu, key=str):
                cur.execute("INSERT INTO flow.links (source_key, target_key, link_type, direction) VALUES (%s, %s, %s, %s)",
                            (cle, cible, type_, sens))
        voulues = _versions_voulues(snap)
        if voulues is not None and ("ticket" in diff or "versions" in diff):
            cur.execute("DELETE FROM flow.issue_current_versions WHERE issue_key = %s", (cle,))
            for genre, nom, date_sortie, sortie in sorted(voulues, key=lambda v: (v[0], v[1])):
                cur.execute("INSERT INTO flow.issue_current_versions (issue_key, kind, name, release_date, released) "
                            "VALUES (%s, %s, %s, %s, %s)", (cle, genre, nom, date_sortie, sortie))
        voulues_livraison = flow_delivery.lignes_de(cle, snap.get("delivery"))
        if "delivery" in diff or ("ticket" in diff and any(voulues_livraison.values())):
            _ecrire_livraison(cur, cle, voulues_livraison)
    return equipes_creees, liens_ajoutes, liens_retires


def _ecrire_livraison(cur, cle: str, lignes: dict[str, set]) -> None:
    """Remplace les lignes courantes de livraison d'un ticket par les lignes voulues (jira-delivery-fields D3) : sprints (la ligne de
    flow.sprints d'abord), champs, versions d'actifs, options, champs des défauts. Aucune valeur n'est affichée."""
    for table in ("issue_delivery_fields", "issue_current_sprints", "issue_current_asset_versions", "issue_delivery_options",
                  "issue_defect_fields"):
        cur.execute(f"DELETE FROM flow.{table} WHERE issue_key = %s", (cle,))
    for _, sprint, etat, debut, fin, termine in sorted(lignes["sprints"], key=lambda s: s[1]):
        cur.execute("INSERT INTO flow.sprints (sprint_id, state, start_date, end_date, complete_date) VALUES (%s, %s, %s, %s, %s) "
                    "ON CONFLICT (sprint_id) DO UPDATE SET state = EXCLUDED.state, start_date = EXCLUDED.start_date, "
                    "end_date = EXCLUDED.end_date, complete_date = EXCLUDED.complete_date", (sprint, etat, debut, fin, termine))
        cur.execute("INSERT INTO flow.issue_current_sprints (issue_key, sprint_id) VALUES (%s, %s)", (cle, sprint))
    for ligne in lignes["fields"]:
        cur.execute("INSERT INTO flow.issue_delivery_fields (issue_key, release_target_id, verification_required_id, product_safety_id, "
                    "isp_id, code_review_status_id, portfolio_rank, customer_commitment, source_commitment, strategic_objective) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", ligne)
    for _, genre, objet in sorted(lignes["assets"]):
        cur.execute("INSERT INTO flow.issue_current_asset_versions (issue_key, kind, object_id) VALUES (%s, %s, %s)", (cle, genre, objet))
    for ligne in sorted(lignes["options"], key=lambda o: (o[1], o[2])):
        cur.execute("INSERT INTO flow.issue_delivery_options (issue_key, field, position, option_id) VALUES (%s, %s, %s, %s)",
                    ligne)
    for ligne in lignes["defect"]:
        cur.execute("INSERT INTO flow.issue_defect_fields (issue_key, detection_phase_id, detection_phase, detected_by_id, "
                    "installed_base_id) VALUES (%s, %s, %s, %s, %s)", ligne)


def deriver_versions(cur) -> dict:
    """Références de version (jira-delivery-fields D3, D5) : écrit dans flow.release_versions le dernier instantané de chaque objet de la
    couche brute (création avec l'instant du passage comme première vue, mise à jour des attributs qui diffèrent ; le numéro opaque est
    attribué par la base à la première vue), puis compte les objets de version référencés par un ticket qu'aucune référence ne porte. Rend
    {"versions_ecrites", "versions_sans_ticket"} : des nombres seulement, jamais un identifiant ni un nom."""
    vivantes = {ligne[0]: tuple(ligne[1:]) for ligne in cur.execute(SQL_REFERENCES_VIVANTES).fetchall()}
    ecrites = 0
    for objet, contenu, vu in cur.execute(SQL_DERNIERES_VERSIONS_BRUTES).fetchall():
        voulu = (contenu.get("short_name"), contenu.get("status"), contenu.get("status_category"),
                 _date_de_sortie(contenu.get("started")), _date_de_sortie(contenu.get("released")))
        if objet not in vivantes:
            cur.execute("INSERT INTO flow.release_versions (object_id, short_name, status, status_category, started, released, last_seen) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s)", (objet, *voulu, vu))
            ecrites += 1
        elif vivantes[objet] != voulu:
            cur.execute("UPDATE flow.release_versions SET short_name = %s, status = %s, status_category = %s, started = %s, released = %s "
                        "WHERE object_id = %s", (*voulu, objet))
            ecrites += 1
    sans_ticket = cur.execute(SQL_VERSIONS_SANS_TICKET).fetchone()[0]
    return {"versions_ecrites": ecrites, "versions_sans_ticket": int(sans_ticket)}


class RefusDerivation(Exception):
    """Dérivation refusée avant toute écriture : `code` est la clé de la phrase fixe (jeu incomplet, export vide, trop d'absents)."""

    def __init__(self, code: str, suite: str | None = None, absents: int | None = None, stockes: int | None = None):
        super().__init__(code)
        self.code = code
        self.absents = absents      # refus « trop d'absents » seulement : tickets qui deviendraient absents (R-20261114-69)
        self.stockes = stockes      # idem : tickets stockés non marqués, dénominateur exact de part_absents_depassee
        self.suite = suite          # clé d'une seconde phrase affichée après la première (passage d'export limité à une requête)


def part_absents_depassee(candidats: int, total: int, seuil_pourcent: float) -> bool:
    """Vrai si `candidats` tickets sur `total` dépassent `seuil_pourcent` %. Pure. Rien de stocké : jamais de refus."""
    return total > 0 and candidats * 100 > seuil_pourcent * total


def deriver(conn, *, appliquer: bool = True, marquer_absents: bool = False, seuil_pourcent: float = 20.0,
            retention_jours: int | None = None, maintenant: dt.datetime | None = None) -> dict:
    """Dérive les tables courantes (tickets, équipes par ticket, liens, marques « sorti de l'export ») de la couche brute, en UNE
    transaction (database-only, D4). Sans état « appliqué » : l'import compare le DERNIER instantané de chaque ticket aux lignes
    vivantes (comme `reconstruire`, sans refuser les tickets stockés qui n'ont pas d'instantané : ils restent tels quels) et les
    visites du DERNIER passage d'export aux marques. Un passage plus ancien n'a rien à apporter : son état est celui du dernier.
      - un ticket du dernier passage perd sa marque, avec ou sans l'option ;
      - un ticket marqué disparu par la collecte de l'historique (D15) et revu par le dernier passage perd cette marque aussi, avec ou
        sans l'option : compteur à 0, instant de disparition effacé ; le compteur d'un ticket non marqué disparu reste tel quel ;
      - avec `marquer_absents`, un ticket stocké non marqué et absent du dernier passage reçoit `maintenant` ; refus (RefusDerivation)
        si le dernier passage ne couvre pas toutes les requêtes nommées (`all_queries`) : « jeu incomplet » ; s'il n'a aucune visite :
        « export vide » ; si la part des absents dépasse `seuil_pourcent` : « trop d'absents » ;
      - un instantané d'un ticket résolu depuis plus de `retention_jours` jours est ignoré et compté.
    Sans `appliquer`, les comptes sont calculés et la transaction est annulée. Rend {"compares", "inseres", "modifies", "inchanges",
    "equipes", "liens_ajoutes", "liens_retires", "hors_conservation", "marques", "revenus", "disparus_revus", "rien"} ; `rien` : aucun passage, aucune
    différence, aucune marque à changer."""
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    cur = conn.cursor()
    try:
        instantanes = _derniers_instantanes(cur)
        vivant = _vivant(cur)
        limite = maintenant - dt.timedelta(days=retention_jours) if retention_jours is not None else None
        gardes = {cle: snap for cle, snap in instantanes.items() if limite is None or snap["resolved_at"] is None
                  or snap["resolved_at"] >= limite}
        a_changer = []
        for cle, snap in gardes.items():
            diff = champs_differents(snap, _a_comparer(vivant.get(cle), snap))
            if diff:
                a_changer.append((snap, diff))
        resultat = {"compares": len(gardes), "inseres": sum(1 for _, diff in a_changer if "ticket" in diff),
                    "modifies": len(a_changer), "inchanges": len(gardes) - len(a_changer), "equipes": 0, "liens_ajoutes": 0,
                    "liens_retires": 0, "hors_conservation": len(instantanes) - len(gardes), "marques": 0, "revenus": 0,
                    "disparus_revus": 0}
        resultat["modifies"] -= resultat["inseres"]            # « mis à jour » : les tickets déjà stockés dont un champ diffère
        if a_changer:
            resultat["equipes"], resultat["liens_ajoutes"], resultat["liens_retires"] = _appliquer(cur, a_changer, vivant)
        resultat.update(deriver_versions(cur))          # références de version (jira-delivery-fields) : après les tickets, dans la transaction
        passage = cur.execute("SELECT id, all_queries FROM flow.raw_runs WHERE kind = 'export' ORDER BY id DESC LIMIT 1").fetchone()
        if passage is not None:
            vus = [cle for (cle,) in cur.execute("SELECT issue_key FROM flow.raw_run_sightings WHERE run_id = %s", (passage[0],)).fetchall()]
            for lot in _par_lots(vus, LOT_CLES):
                resultat["revenus"] += cur.execute("UPDATE flow.issues SET out_of_export_at = NULL "
                                                   "WHERE key = ANY(%s::text[]) AND out_of_export_at IS NOT NULL", (lot,)).rowcount
                # D15 complété : un ticket marqué disparu que l'export revoit perd sa marque (compteur à 0, instant effacé) ; le
                # compteur d'un ticket non marqué disparu n'est pas touché (sinon il n'atteindrait jamais la limite)
                resultat["disparus_revus"] += cur.execute("UPDATE flow.issues SET history_not_found = 0, history_gone_at = NULL "
                                                          "WHERE key = ANY(%s::text[]) AND history_gone_at IS NOT NULL", (lot,)).rowcount
            if marquer_absents:
                if not passage[1]:
                    raise RefusDerivation("incomplete_set", "partial_run")          # le dernier passage est un passage --query
                if not vus:
                    raise RefusDerivation("empty_export")
                candidats = cur.execute("SELECT count(*) FROM flow.issues WHERE out_of_export_at IS NULL AND NOT (key = ANY(%s::text[]))",
                                        (vus,)).fetchone()[0]
                total = cur.execute("SELECT count(*) FROM flow.issues WHERE out_of_export_at IS NULL").fetchone()[0]
                if part_absents_depassee(candidats, total, seuil_pourcent):
                    raise RefusDerivation("absent_share_exceeded", absents=candidats, stockes=total)
                resultat["marques"] = cur.execute("UPDATE flow.issues SET out_of_export_at = %s "
                                                  "WHERE out_of_export_at IS NULL AND NOT (key = ANY(%s::text[]))",
                                                  (maintenant, vus)).rowcount
        elif marquer_absents:
            raise RefusDerivation("incomplete_set")          # aucun passage : l'ensemble complet n'existe pas
        resultat["rien"] = ((passage is None and not a_changer and not resultat["versions_ecrites"])
                            or (not a_changer and not resultat["marques"] and not resultat["revenus"]
                                and not resultat["disparus_revus"] and not resultat["versions_ecrites"]))
        if appliquer:
            conn.commit()
        else:
            conn.rollback()
        return resultat
    except BaseException:
        conn.rollback()
        raise


def amorcer(conn) -> int:
    """Écrit, en UNE transaction, un instantané d'amorçage construit depuis la ligne vivante de chaque ticket stocké qui n'en a
    aucun, rattaché à un passage de genre seed. L'instantané porte les noms d'équipe des tables vivantes et aucun identifiant.
    Ne remplace ni ne double jamais un instantané existant. Rend le nombre d'instantanés écrits (0 : rien n'est écrit, pas de passage)."""
    cur = conn.cursor()
    try:
        existants = {cle for (cle,) in cur.execute("SELECT DISTINCT issue_key FROM flow.raw_issue_snapshots").fetchall()}
        vivant = _vivant(cur)
        manquants = [cle for cle in vivant if cle not in existants]
        if not manquants:
            conn.rollback()
            return 0
        run_id = cur.execute("INSERT INTO flow.raw_runs (kind, queries_searched, all_queries) VALUES ('seed', 0, false) "
                             "RETURNING id").fetchone()[0]
        a_ecrire = []
        for cle in manquants:
            ligne = vivant[cle]
            equipes = [{"name": nom, "jira_team_id": None} for nom in ligne["teams"]]
            if not equipes and ligne["team"]:
                equipes = [{"name": ligne["team"], "jira_team_id": None}]
            instantane_ = {
                "issue_key": cle, "updated_at": ligne["updated_at"], "project": ligne["project"], "type": ligne["type"],
                "status": ligne["status"], "status_category": ligne["status_category"], "created_at": ligne["created_at"],
                "resolved_at": ligne["resolved_at"], "resolution": ligne["resolution"],
                "status_category_changed_at": ligne["status_category_changed_at"], "story_points": ligne["story_points"],
                "parent_key": ligne["parent_key"], "teams": equipes,
                "links": [{"target": c, "type": t, "direction": s} for c, t, s in sorted(ligne["links"], key=str)]}
            instantane_["content_hash"] = empreinte(instantane_)
            a_ecrire.append(instantane_)
        for lot in _par_lots(a_ecrire, LOT):
            cur.executemany(SQL_INSERTION_INSTANTANE, [_parametres_instantane(i, run_id, True) for i in lot])
        conn.commit()
        return len(a_ecrire)
    except BaseException:
        conn.rollback()
        raise
