"""
PMZilla Lab : couche brute datée de l'export Jira, dans le schéma flow (change jira-data-architecture, R-70, design D3 à D6).

Module de bibliothèque, sans ligne de commande. Trois entités (migration flow_raw_layer) :
  - passage (flow.raw_runs) : un par export réussi, un par amorçage ; instant, nombre de requêtes nommées lues, toutes lues ou non ;
  - visite (flow.raw_run_sightings) : une clé de ticket lue par un passage, après l'écart de conservation ;
  - instantané (flow.raw_issue_snapshots) : les attributs autorisés d'un ticket (projet, type, état, catégorie, dates, résolution,
    story points, parent, équipes dans l'ordre avec leur identifiant d'équipe Jira, liens ou « non suivis »), écrit pour un ticket
    nouveau ou quand son empreinte change. Jamais de titre, de description, de personne, d'étiquette ni de version.

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

LOT = 500
LOT_CLES = 2000

# Noms neutres des champs comptés par la reconstruction (design D11) ; « ticket » : la ligne vivante manque.
CHAMPS = ("ticket", "status", "status category", "type", "resolution", "dates", "story points", "parent", "team", "teams", "links")

COLONNES_INSTANTANE = ("issue_key", "run_id", "updated_at", "project", "type", "status", "status_category", "created_at",
                       "resolved_at", "resolution", "status_category_changed_at", "story_points", "parent_key", "teams", "links",
                       "content_hash", "seeded")


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
    }
    resultat["content_hash"] = empreinte(resultat)
    return resultat


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
            Jsonb(i["teams"]), None if i["links"] is None else Jsonb(i["links"]), i["content_hash"], seeded)


SQL_INSERTION_INSTANTANE = (
    f"INSERT INTO flow.raw_issue_snapshots ({', '.join(COLONNES_INSTANTANE)}) "
    f"VALUES ({', '.join(['%s'] * len(COLONNES_INSTANTANE))})")
SQL_DERNIERS = ("SELECT DISTINCT ON (issue_key) issue_key, updated_at, content_hash FROM flow.raw_issue_snapshots "
                "WHERE issue_key = ANY(%s) ORDER BY issue_key, run_id DESC")


class MagasinBase:
    """Magasin de la couche brute dans la base, sous le rôle d'import (connexion ouverte par l'appelant). Une erreur de la base
    remonte telle quelle : l'appelant n'en affiche que le type."""

    def __init__(self, conn):
        self.conn = conn
        self.sans_type = 0          # après un enregistrement avec types_equipes : équipes rencontrées dont la colonne du type est nulle

    def enregistrer(self, *, genre: str, nb_requetes: int, toutes: bool, vus: list[str], instantanes: dict[str, dict],
                    types_equipes: dict[str, str | None] | None = None):
        """Écrit un passage, ses visites et les instantanés à ajouter, en UNE transaction (annulée en cas d'erreur).
        `types_equipes` (nom d'équipe -> type ou None, database-only, complément du type d'équipe) : dans la même transaction, crée
        l'équipe qui manque et n'écrit la colonne du type que pour un type connu et différent de celui de la base (jamais un type nul
        par-dessus un type écrit) ; `self.sans_type` compte ensuite les équipes rencontrées au type nul. Rend (clés vues, instantanés
        ajoutés)."""
        cur = self.conn.cursor()
        try:
            derniers: dict[str, tuple] = {}
            for lot in _par_lots(list(instantanes), LOT_CLES):
                for cle, instant, empreinte_ in cur.execute(SQL_DERNIERS, (lot,)).fetchall():
                    derniers[cle] = (instant, empreinte_)
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
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise
        return len(uniques), len(a_ajouter)

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
    return instantanes


def _vivant(cur) -> dict[str, dict]:
    vivant = {}
    for ligne in cur.execute(SQL_VIVANT).fetchall():
        entree = dict(zip(("key",) + COLONNES_COMPARAISON + ("team",), ligne))
        entree.update(teams=[], links=set())
        vivant[ligne[0]] = entree
    for cle, nom in cur.execute(SQL_EQUIPES_VIVANTES).fetchall():
        if cle in vivant:
            vivant[cle]["teams"].append(nom)
    for source, cible, type_, sens in cur.execute(SQL_LIENS_VIVANTS).fetchall():
        if source in vivant:
            vivant[source]["links"].add((cible, type_, sens))
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
    return equipes_creees, liens_ajoutes, liens_retires


class RefusDerivation(Exception):
    """Dérivation refusée avant toute écriture : `code` est la clé de la phrase fixe (jeu incomplet, export vide, trop d'absents)."""

    def __init__(self, code: str, suite: str | None = None):
        super().__init__(code)
        self.code = code
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
                    raise RefusDerivation("absent_share_exceeded")
                resultat["marques"] = cur.execute("UPDATE flow.issues SET out_of_export_at = %s "
                                                  "WHERE out_of_export_at IS NULL AND NOT (key = ANY(%s::text[]))",
                                                  (maintenant, vus)).rowcount
        elif marquer_absents:
            raise RefusDerivation("incomplete_set")          # aucun passage : l'ensemble complet n'existe pas
        resultat["rien"] = (passage is None and not a_changer) or (not a_changer and not resultat["marques"] and not resultat["revenus"]
                                                                  and not resultat["disparus_revus"])
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
