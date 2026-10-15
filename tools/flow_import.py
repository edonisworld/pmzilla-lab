# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pyyaml", "psycopg[binary]"]
# ///
"""
PMZilla Lab : import incrémental des exports Jira dans le schéma flow de la base (lot 6, Jira en base).

    uv run tools/flow_import.py <export.csv>... [--history [CACHE]] [--mark-absent] [--dry-run] [--language fr|en]

Les exports sont ceux de export_jira_api.py (voie unique ; aucun CSV manuel). Plusieurs fichiers : fusion par clé, le
dernier l'emporte. Sans --history, aucune transition n'est importée ; avec --history, le cache de history_jira.py
(Flux-Lab/historique/transitions.json par défaut) l'est.

Ce que l'outil écrit, dans le schéma flow, sous le rôle pmzilla_flow, en une seule transaction (annulée en cas d'erreur) :
  - flow.teams : une équipe par valeur du champ équipe, créée à la volée ;
  - flow.issues : INSERT ... ON CONFLICT (key) DO UPDATE, seulement si un champ diffère de la valeur entrante ;
  - flow.issue_teams et flow.links : la différence seulement (un ticket sans colonne de liens dans l'export garde ses liens) ;
  - flow.transitions : INSERT ... ON CONFLICT DO NOTHING, jamais de suppression ; les transitions d'une clé absente de
    flow.issues sont ignorées ;
  - avec --history, flow.issue_label_periods et flow.issue_version_periods (R-58, design D1, D19, D20) : les périodes des
    étiquettes déclarées et des versions, construites par `construire_periodes` à partir des événements du cache (un ajout
    ouvre une période, un retrait la ferme) et des valeurs de l'export (une valeur présente sans événement ouvre une période
    à la création du ticket). Une étiquette absente des réglages est refusée : seul le nombre de valeurs refusées est
    affiché. Aucune colonne de personne n'est lue (un en-tête PO est ignoré) ; aucune étiquette ni version n'est affichée.
Les lignes d'export des tickets résolus depuis plus que la durée de conservation (réglage retention) ne sont ni insérées ni
mises à jour : elles sont seulement comptées.
Un ticket absent du nouvel export n'est pas supprimé. Il n'est marqué « sorti de l'export » (flow.issues.out_of_export_at, à
l'instant de l'import, sans jamais déplacer une marque existante) qu'avec --mark-absent, et seulement si les fichiers donnés
sont exactement un export de l'API par requête nommée des réglages (jql_exports), tous du même jour (design D8) : sinon code
de sortie 1 avant toute connexion. Un ticket présent dans un import perd sa marque, avec ou sans l'option. Une colonne Updated absente ou illisible fait refuser l'export
avant toute écriture (code de sortie 1), sans repli sur l'instant de l'import.

Ce que l'outil n'affiche jamais : aucune clé de ticket, aucun nom d'équipe, aucune valeur de champ, y compris dans les
erreurs. La sortie ne compte que des effectifs (tickets lus, insérés, mis à jour, inchangés, écartés ; équipes créées ;
liens ajoutés ; transitions ajoutées, ignorées, illisibles ; périodes ; tickets marqués ou revenus ; tickets au-delà de la
conservation ; valeurs d'étiquette refusées). Les lignes « tickets sortis de l'export », « au-delà de la conservation » et
« valeurs refusées » s'affichent à chaque import, avec 0 quand il n'y a rien (l'essai à blanc les calcule aussi, dans sa
transaction annulée). Une erreur de la base est réduite au nom de son type.

--dry-run calcule les mêmes comptes dans la base et annule la transaction : rien n'est écrit.

Seul l'utilisateur lance cet outil sur les vraies données : Claude Code ne le lance jamais (règles deny de
.claude/settings.json). Les tests passent par une base jetable et des données inventées.

Exemple :
    uv run tools/flow_import.py export.csv --dry-run
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db                                               # noqa: E402
import flow_export_reader as lecteur                    # noqa: E402
import flux_config as cfg                               # noqa: E402
import flux_jira                                        # noqa: E402
import history_common as commun                         # noqa: E402
from flow_import_messages import CATALOGS               # noqa: E402
from messages import Messages, add_language_option      # noqa: E402
from yaml_strict import ErreurConfig                    # noqa: E402

ROLE = "pmzilla_flow"
LOT = 2000            # tickets par requête groupée
LOT_TRANSITIONS = 5000

SQL_TICKETS = """
INSERT INTO flow.issues AS i (key, project, type, status, status_category, created_at, resolved_at, resolution,
                              status_category_changed_at, story_points, updated_at, team_id, parent_key)
SELECT * FROM unnest(%s::text[], %s::text[], %s::text[], %s::text[], %s::text[], %s::timestamptz[], %s::timestamptz[],
                     %s::text[], %s::timestamptz[], %s::numeric[], %s::timestamptz[], %s::integer[], %s::text[])
ON CONFLICT (key) DO UPDATE SET
    project = EXCLUDED.project, type = EXCLUDED.type, status = EXCLUDED.status,
    status_category = EXCLUDED.status_category, created_at = EXCLUDED.created_at, resolved_at = EXCLUDED.resolved_at,
    resolution = EXCLUDED.resolution, status_category_changed_at = EXCLUDED.status_category_changed_at,
    story_points = EXCLUDED.story_points, updated_at = EXCLUDED.updated_at, team_id = EXCLUDED.team_id,
    parent_key = EXCLUDED.parent_key
WHERE EXCLUDED.updated_at >= i.updated_at          -- un export plus ancien n'écrase jamais une ligne plus récente
  AND (i.project, i.type, i.status, i.status_category, i.created_at, i.resolved_at, i.resolution,
       i.status_category_changed_at, i.story_points, i.updated_at, i.team_id, i.parent_key)
      IS DISTINCT FROM
      (EXCLUDED.project, EXCLUDED.type, EXCLUDED.status, EXCLUDED.status_category, EXCLUDED.created_at,
       EXCLUDED.resolved_at, EXCLUDED.resolution, EXCLUDED.status_category_changed_at, EXCLUDED.story_points,
       EXCLUDED.updated_at, EXCLUDED.team_id, EXCLUDED.parent_key)
RETURNING (xmax = 0)
"""


# Nom d'un export de l'API : api-[NOM-]AAAA-MM-JJ.csv (export_jira_api.nom_fichier_export ; flow_monthly.chemin_export le reconstruit)
MOTIF_EXPORT = re.compile(r"^api-(?:(?P<nom>.+)-)?(?P<jour>\d{4}-\d{2}-\d{2})\.csv$")
MOTIF_NOM_REQUETE = re.compile(r"^[A-Za-z0-9_-]+$")

# Tables des périodes (noms fixes, jamais issus d'une donnée) : table, colonne de la valeur
TABLES_PERIODES = {"etiquettes": ("flow.issue_label_periods", "label"), "versions": ("flow.issue_version_periods", "version")}


def requetes_nommees(reglages: dict) -> list[str | None] | None:
    """Noms des requêtes exportées des réglages (jql_exports, dans l'ordre), [None] pour l'unique requête sans nom (jql_export),
    None si les réglages n'en donnent aucune d'utilisable (comme flow_monthly._requetes)."""
    nommees = reglages.get("jql_exports")
    if nommees:
        if not isinstance(nommees, dict) or not all(MOTIF_NOM_REQUETE.match(str(n)) for n in nommees):
            return None
        return [str(n) for n in nommees]
    if not str(reglages.get("jql_export") or "").strip():
        return None
    return [None]


def jeu_complet(chemins: list[str], reglages: dict) -> bool:
    """Vrai si les fichiers donnés sont exactement un export de l'API par requête nommée des réglages, tous du même jour
    (design D8). Le jour et la requête se déduisent du nom du fichier (api-[NOM-]AAAA-MM-JJ.csv), comme le fait le suivi mensuel.
    Pure : aucun accès au disque ni à la base."""
    noms = requetes_nommees(reglages)
    if not noms or len(chemins) != len(noms):
        return False
    trouves, jours = [], set()
    for chemin in chemins:
        trouve = MOTIF_EXPORT.match(Path(chemin).name)
        if trouve is None:
            return False
        trouves.append(trouve["nom"])
        jours.add(trouve["jour"])
    return len(jours) == 1 and sorted(trouves, key=str) == sorted(noms, key=str)


def ecarter_hors_conservation(tickets: list[dict], jours: int, maintenant: dt.datetime) -> tuple[list[dict], int]:
    """(tickets à importer, nombre de tickets écartés). Un ticket résolu depuis plus de `jours` jours est écarté : horloge du
    design D1 (un an après la résolution). Un ticket non résolu est gardé. Pure."""
    limite = maintenant - dt.timedelta(days=jours)
    gardes = [t for t in tickets if t["resolu"] is None or t["resolu"] >= limite]
    return gardes, len(tickets) - len(gardes)


def construire_periodes(evenements: list, presentes: list[str] | None, cree: dt.datetime, zone,
                        admises: set[str] | None = None) -> list[tuple[str, dt.datetime, dt.datetime | None]]:
    """Périodes (valeur, posée le, retirée le ou None) d'un ticket, pour les étiquettes déclarées ou pour les versions.
    `evenements` : [date ISO, "add"|"remove", valeur] du cache, déjà triés ; `presentes` : valeurs de l'export du jour
    (None : l'export n'a pas la colonne) ; `cree` : création du ticket ; `admises` : valeurs autorisées (les étiquettes
    déclarées ; None pour les versions). Règles :
      - un « add » ouvre une période (un second « add » sans retrait entre les deux est ignoré), un « remove » la ferme ;
      - un « remove » sans période ouverte ferme une période ouverte à la création du ticket (la valeur était posée avant le
        début du cache) ;
      - une valeur présente dans l'export, sans aucun événement, ouvre une période à la création ;
      - la date de retrait n'est jamais antérieure à celle de pose ; un événement à date illisible est écarté ;
      - une valeur hors de `admises` n'apparaît jamais.
    Pure : aucun accès à la base."""
    ouvertes: dict[str, dt.datetime] = {}
    periodes: list[tuple[str, dt.datetime, dt.datetime | None]] = []
    vues: set[str] = set()
    for evenement in evenements or []:
        date, sens, valeur = evenement
        moment = _instant_transition(date, zone)
        if moment is None or (admises is not None and valeur not in admises):
            continue
        vues.add(valeur)
        if sens == "add":
            ouvertes.setdefault(valeur, moment)
        elif valeur in ouvertes:
            debut = ouvertes.pop(valeur)
            periodes.append((valeur, debut, max(moment, debut)))
        else:
            periodes.append((valeur, cree, max(moment, cree)))
    for valeur in presentes or []:
        if valeur not in vues and (admises is None or valeur in admises):
            ouvertes[valeur] = cree
    periodes.extend((valeur, debut, None) for valeur, debut in ouvertes.items())
    return sorted(periodes, key=lambda p: (p[1], p[0]))


def _par_lots(elements: list, taille: int):
    for debut in range(0, len(elements), taille):
        yield elements[debut:debut + taille]


def _equipes(cur, tickets: list[dict]) -> tuple[dict[str, int], int]:
    """Identifiants des équipes de l'export (créées si besoin) et nombre d'équipes créées."""
    noms = list(dict.fromkeys(nom for t in tickets for nom in t["equipes"]))
    ids = dict(cur.execute("SELECT name, id FROM flow.teams").fetchall())
    manquants = [nom for nom in noms if nom not in ids]
    creees = 0
    if manquants:
        creees = cur.execute("INSERT INTO flow.teams (name) SELECT unnest(%s::text[]) ON CONFLICT (name) DO NOTHING",
                             (manquants,)).rowcount
        ids = dict(cur.execute("SELECT name, id FROM flow.teams").fetchall())
    return ids, creees


def _tickets(cur, tickets: list[dict], ids: dict[str, int]) -> tuple[int, int, int]:
    inseres = modifies = 0
    for lot in _par_lots(tickets, LOT):
        colonnes = [
            [t["cle"] for t in lot], [t["projet"] for t in lot], [t["type"] for t in lot], [t["etat"] for t in lot],
            [t["categorie"] for t in lot], [t["cree"] for t in lot], [t["resolu"] for t in lot],
            [t["motif"] for t in lot], [t["debut"] for t in lot], [t["points"] for t in lot],
            [t["modifie"] for t in lot], [ids[t["equipes"][0]] if t["equipes"] else None for t in lot],
            [t["parent"] for t in lot],
        ]
        for (insere,) in cur.execute(SQL_TICKETS, colonnes).fetchall():
            if insere:
                inseres += 1
            else:
                modifies += 1
    return inseres, modifies, len(tickets) - inseres - modifies


def _equipes_des_tickets(cur, tickets: list[dict], ids: dict[str, int]) -> None:
    cles = [t["cle"] for t in tickets]
    existant: dict[tuple[str, int], int] = {}
    for cle, equipe, position in cur.execute(
            "SELECT issue_key, team_id, position FROM flow.issue_teams WHERE issue_key = ANY(%s)", (cles,)).fetchall():
        existant[(cle, equipe)] = position
    voulu = {(t["cle"], ids[nom]): position for t in tickets for position, nom in enumerate(t["equipes"], 1)}
    retirer = [paire for paire in existant if paire not in voulu]
    ecrire = [(paire, position) for paire, position in voulu.items() if existant.get(paire) != position]
    if retirer:
        cur.execute("DELETE FROM flow.issue_teams WHERE (issue_key, team_id) IN "
                    "(SELECT * FROM unnest(%s::text[], %s::integer[]))",
                    ([c for c, _ in retirer], [e for _, e in retirer]))
    if ecrire:
        cur.execute("INSERT INTO flow.issue_teams (issue_key, team_id, position) "
                    "SELECT * FROM unnest(%s::text[], %s::integer[], %s::smallint[]) "
                    "ON CONFLICT (issue_key, team_id) DO UPDATE SET position = EXCLUDED.position "
                    "WHERE flow.issue_teams.position IS DISTINCT FROM EXCLUDED.position",
                    ([p[0] for p, _ in ecrire], [p[1] for p, _ in ecrire], [pos for _, pos in ecrire]))


def _liens(cur, tickets: list[dict]) -> tuple[int, int]:
    """(ajoutés, retirés). Les tickets dont l'export n'a pas de colonne de liens ne sont pas touchés."""
    suivis = [t for t in tickets if t["liens"] is not None]
    if not suivis:
        return 0, 0
    existant = set(cur.execute(
        "SELECT source_key, target_key, link_type, direction FROM flow.links WHERE source_key = ANY(%s)",
        ([t["cle"] for t in suivis],)).fetchall())
    voulu = {(t["cle"], autre, type_lien, sens) for t in suivis for autre, type_lien, sens in t["liens"]}
    retirer, ajouter = sorted(existant - voulu, key=str), sorted(voulu - existant, key=str)
    if retirer:
        cur.execute("DELETE FROM flow.links l USING unnest(%s::text[], %s::text[], %s::text[], %s::text[]) AS d(s, t, y, w) "
                    "WHERE l.source_key = d.s AND l.target_key = d.t AND l.link_type = d.y "
                    "AND l.direction IS NOT DISTINCT FROM d.w", tuple(list(colonne) for colonne in zip(*retirer)))
    ajoutes = 0
    for lot in _par_lots(ajouter, LOT_TRANSITIONS):
        ajoutes += cur.execute(
            "INSERT INTO flow.links (source_key, target_key, link_type, direction) "
            "SELECT * FROM unnest(%s::text[], %s::text[], %s::text[], %s::text[]) ON CONFLICT DO NOTHING",
            tuple(list(colonne) for colonne in zip(*lot))).rowcount
    return ajoutes, len(retirer)


def _instant_transition(valeur, zone) -> dt.datetime | None:
    try:
        moment = dt.datetime.fromisoformat(str(valeur))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=zone)


def _transitions(cur, cache: dict[str, dict], zone) -> tuple[int, int, int, int]:
    """(ajoutées, ignorées sans ticket, illisibles, tickets nouvellement marqués « avec historique »). Aucune transition n'est jamais
    supprimée. Un ticket est « avec historique » dès que le cache a une entrée pour lui, même sans transition."""
    en_base = {cle.upper(): cle for (cle,) in cur.execute("SELECT key FROM flow.issues").fetchall()}
    lignes: list[tuple] = []
    sans_ticket = illisibles = 0
    avec_entree: list[str] = []
    for cle, entree in cache.items():
        transitions = entree["transitions"]
        vrai = en_base.get(str(cle).upper())
        if vrai is None:
            sans_ticket += len(transitions)
            continue
        avec_entree.append(vrai)
        for transition in transitions:
            try:
                date, depart, arrivee = transition[0], transition[1], transition[2]
            except (TypeError, IndexError, KeyError):
                illisibles += 1
                continue
            moment = _instant_transition(date, zone)
            if moment is None or not arrivee:
                illisibles += 1
                continue
            lignes.append((vrai, moment, depart or None, arrivee))
    ajoutees = 0
    for lot in _par_lots(lignes, LOT_TRANSITIONS):
        ajoutees += cur.execute(
            "INSERT INTO flow.transitions (issue_key, transitioned_at, from_status, to_status) "
            "SELECT * FROM unnest(%s::text[], %s::timestamptz[], %s::text[], %s::text[]) ON CONFLICT DO NOTHING",
            tuple(list(colonne) for colonne in zip(*lot))).rowcount
    marques = 0
    for lot in _par_lots(avec_entree, LOT):
        marques += cur.execute("UPDATE flow.issues SET has_history = true WHERE key = ANY(%s) AND NOT has_history",
                               (lot,)).rowcount
    return ajoutees, sans_ticket, illisibles, marques


def _periodes(cur, tickets: list[dict], cache: dict[str, dict], zone, declarees: set[str]) -> dict[str, int]:
    """Écrit les périodes d'étiquettes déclarées et de versions des tickets de l'import (cache : entrées par clé). Pour un
    ticket dont l'export a la colonne, l'ensemble construit fait foi : les périodes en base qui n'y sont plus sont retirées
    et les retraits sont mis à jour. Pour un ticket dont l'export n'a pas la colonne, on ajoute et on ferme seulement, on ne
    retire rien. Rend le nombre de périodes ajoutées ou modifiées, par nature."""
    cache_maj = {str(cle).upper(): entree for cle, entree in cache.items()}
    ecrites = {"etiquettes": 0, "versions": 0}
    for nature, (table, colonne) in TABLES_PERIODES.items():
        voulu: dict[tuple, dt.datetime | None] = {}
        complets: list[str] = []
        for t in tickets:
            presentes = t.get(nature)
            entree = cache_maj.get(t["cle"].upper()) or {}
            for valeur, debut, fin in construire_periodes(entree.get(nature) or [], presentes, t["cree"], zone,
                                                          declarees if nature == "etiquettes" else None):
                voulu[(t["cle"], valeur, debut)] = fin
            if presentes is not None:
                complets.append(t["cle"])
        if not voulu and not complets:
            continue
        existant: dict[tuple, dt.datetime | None] = {}
        for lot in _par_lots([t["cle"] for t in tickets], LOT):
            for cle, valeur, debut, fin in cur.execute(
                    f"SELECT issue_key, {colonne}, added_at, removed_at FROM {table} WHERE issue_key = ANY(%s::text[])",
                    (lot,)).fetchall():
                existant[(cle, valeur, debut)] = fin
        complets = set(complets)
        a_retirer = [k for k in existant if k not in voulu and k[0] in complets]
        a_ecrire = [(k, fin) for k, fin in voulu.items() if k not in existant or existant[k] != fin]
        for lot in _par_lots(a_retirer, LOT_TRANSITIONS):
            cur.execute(f"DELETE FROM {table} p USING unnest(%s::text[], %s::text[], %s::timestamptz[]) AS d(k, v, a) "
                        f"WHERE p.issue_key = d.k AND p.{colonne} = d.v AND p.added_at = d.a",
                        tuple(list(c) for c in zip(*lot)))
        for lot in _par_lots(a_ecrire, LOT_TRANSITIONS):
            cur.execute(f"INSERT INTO {table} (issue_key, {colonne}, added_at, removed_at) "
                        f"SELECT * FROM unnest(%s::text[], %s::text[], %s::timestamptz[], %s::timestamptz[]) "
                        f"ON CONFLICT (issue_key, {colonne}, added_at) DO UPDATE SET removed_at = EXCLUDED.removed_at",
                        ([k[0] for k, _ in lot], [k[1] for k, _ in lot], [k[2] for k, _ in lot], [fin for _, fin in lot]))
        ecrites[nature] = len(a_ecrire)
    return ecrites


SEUIL_ABSENTS_DEFAUT = 20          # part maximale (en %) de tickets stockés que --mark-absent peut marquer d'un coup


class ErreurSeuilAbsents(Exception):
    """La part de tickets à marquer « sorti de l'export » dépasse le seuil : l'import est annulé (rien n'est écrit)."""


def part_absents_depassee(candidats: int, total: int, seuil_pourcent: float) -> bool:
    """Vrai si `candidats` tickets sur `total` dépassent `seuil_pourcent` %. Pure. Rien de stocké : jamais de refus."""
    return total > 0 and candidats * 100 > seuil_pourcent * total


def _marques(cur, presentes: list[str], marquer: bool, maintenant: dt.datetime,
             seuil_pourcent: float = SEUIL_ABSENTS_DEFAUT) -> tuple[int, int]:
    """(marqués, revenus). Efface la marque de tout ticket présent dans les fichiers (avec ou sans l'option) ; avec
    l'option, marque à l'instant de l'import tout ticket stocké absent de tous les fichiers et non déjà marqué, sauf si
    leur part des tickets stockés dépasse `seuil_pourcent` (lève alors ErreurSeuilAbsents, avant toute marque). Ne déplace
    jamais une marque existante, ne supprime rien."""
    revenus = 0
    for lot in _par_lots(presentes, LOT):
        revenus += cur.execute("UPDATE flow.issues SET out_of_export_at = NULL "
                               "WHERE key = ANY(%s::text[]) AND out_of_export_at IS NOT NULL", (lot,)).rowcount
    marques = 0
    if marquer:
        candidats = cur.execute("SELECT count(*) FROM flow.issues "
                                "WHERE out_of_export_at IS NULL AND NOT (key = ANY(%s::text[]))", (presentes,)).fetchone()[0]
        total = cur.execute("SELECT count(*) FROM flow.issues WHERE out_of_export_at IS NULL").fetchone()[0]
        if part_absents_depassee(candidats, total, seuil_pourcent):
            raise ErreurSeuilAbsents
        marques = cur.execute("UPDATE flow.issues SET out_of_export_at = %s "
                              "WHERE out_of_export_at IS NULL AND NOT (key = ANY(%s::text[]))", (maintenant, presentes)).rowcount
    return marques, revenus


def importer(conn, donnees: dict, cache: dict[str, dict] | None, zone, dry_run: bool = False, *, marquer_absents: bool = False,
             retention_jours: int | None = None, maintenant: dt.datetime | None = None,
             declarees: set[str] | None = None, seuil_absents: float = SEUIL_ABSENTS_DEFAUT) -> dict:
    """Écrit (ou, en essai à blanc, calcule puis annule) l'import dans une seule transaction. Rend les comptes.
    `retention_jours` : durée de conservation (None : aucune ligne écartée) ; `maintenant` : instant de l'import (celui de la
    marque « sorti de l'export »). `declarees` : étiquettes déclarées des réglages, pour filtrer les événements du cache."""
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    presentes = [t["cle"] for t in donnees["tickets"]]
    tickets, hors_conservation = (ecarter_hors_conservation(donnees["tickets"], retention_jours, maintenant)
                                  if retention_jours is not None else (donnees["tickets"], 0))
    comptes = {"read": len(donnees["tickets"]), "unreadable": donnees["illisibles"], "past_retention": hors_conservation,
               "refused": donnees.get("etiquettes_refusees", 0)}
    try:
        cur = conn.cursor()
        cur.execute(f"SET ROLE {ROLE}")
        ids, comptes["teams"] = _equipes(cur, tickets)
        comptes["inserted"], comptes["updated"], comptes["unchanged"] = _tickets(cur, tickets, ids)
        _equipes_des_tickets(cur, tickets, ids)
        comptes["links_added"], comptes["links_removed"] = _liens(cur, tickets)
        if cache is not None:
            (comptes["added"], comptes["orphans"], comptes["transitions_unreadable"],
             comptes["history_marked"]) = _transitions(cur, cache, zone)
            ecrites = _periodes(cur, tickets, cache, zone, declarees or set())
            comptes["label_periods"], comptes["version_periods"] = ecrites["etiquettes"], ecrites["versions"]
        comptes["marked"], comptes["back"] = _marques(cur, presentes, marquer_absents, maintenant, seuil_absents)
        if dry_run:
            conn.rollback()
        else:
            conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return comptes


def afficher(comptes: dict, avec_historique: bool, dry_run: bool, t: Messages) -> None:
    if dry_run:
        print(t("dry_run_notice"))
    print(t("tickets_summary", read=comptes["read"], inserted=comptes["inserted"], updated=comptes["updated"],
            unchanged=comptes["unchanged"], unreadable=comptes["unreadable"]))
    print(t("teams_links_summary", teams=comptes["teams"], links_added=comptes["links_added"],
            links_removed=comptes["links_removed"]))
    if avec_historique:
        print(t("transitions_summary", added=comptes["added"], orphans=comptes["orphans"],
                unreadable=comptes["transitions_unreadable"]))
        print(t("history_marked", marked=comptes["history_marked"]))
    else:
        print(t("no_history_notice"))
    # lignes ajoutées par R-58 (design D19) : toujours à la fin et toujours affichées, avec 0 quand il n'y a rien
    if avec_historique:
        print(t("periods_summary", label_periods=comptes["label_periods"], version_periods=comptes["version_periods"]))
    print(t("labels_refused", refused=comptes["refused"]))
    print(t("past_retention", skipped=comptes["past_retention"]))
    print(t("out_of_export", marked=comptes["marked"], back=comptes["back"]))


def charger_cache(chemin: Path, t: Messages) -> dict[str, dict]:
    if not chemin.exists():
        sys.exit(_echec(t("cache_missing", path=chemin)))
    try:
        return commun.lire_cache(chemin)
    except commun.CacheIllisible:
        sys.exit(_echec(t("cache_unreadable")))


def _echec(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Import incrémental des exports Jira dans le schéma flow de la base")
    parser.add_argument("export", nargs="+", help="un ou plusieurs exports CSV de export_jira_api.py")
    parser.add_argument("--history", nargs="?", const="", default=None, metavar="CACHE",
                        help="importe aussi les transitions du cache de history_jira.py "
                             "(défaut : Flux-Lab/historique/transitions.json)")
    parser.add_argument("--mark-absent", action="store_true",
                        help="marque « sorti de l'export » les tickets stockés absents des fichiers ; exige exactement un "
                             "export de l'API par requête nommée de flux.yaml, tous du même jour")
    parser.add_argument("--max-absent-percent", type=float, default=SEUIL_ABSENTS_DEFAUT, metavar="N",
                        help=f"avec --mark-absent : refuse l'import si plus de N %% des tickets stockés seraient marqués "
                             f"(défaut {SEUIL_ABSENTS_DEFAUT}) ; refuse aussi des exports sans aucune ligne")
    parser.add_argument("--dry-run", action="store_true", help="calcule les comptes dans la base, annule, n'écrit rien")
    add_language_option(parser)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if not 0 <= args.max_absent_percent <= 100:
        parser.error("--max-absent-percent doit être compris entre 0 et 100")
    t = Messages(CATALOGS, args.language)
    try:
        reglages = flux_jira.config(Messages(flux_jira.CATALOGS, args.language))
        retention = cfg.retention_days(reglages)
        zone = lecteur.fuseau(reglages)
        if args.mark_absent and not jeu_complet(args.export, reglages):     # avant toute lecture, écriture ou connexion
            sys.exit(_echec(t("incomplete_set")))
        donnees = lecteur.lire_exports(args.export, reglages, periodes=True)
        if args.mark_absent and not donnees["tickets"]:         # un export vide marquerait tout le stock : avant toute connexion
            sys.exit(_echec(t("empty_export")))
    except lecteur.ErreurExport as erreur:
        sys.exit(_echec(t(erreur.code, **erreur.valeurs)))
    except ErreurConfig as erreur:       # le message nomme le réglage, jamais sa valeur
        sys.exit(_echec(str(erreur)))
    cache = None
    if args.history is not None:
        cache = charger_cache(Path(args.history).expanduser() if args.history else flux_jira.HISTORIQUE_DEFAUT, t)
    conn = None
    try:
        conn = db.connect()
        comptes = importer(conn, donnees, cache, zone, args.dry_run, marquer_absents=args.mark_absent,
                           retention_jours=retention, maintenant=dt.datetime.now(dt.timezone.utc),
                           declarees=lecteur.etiquettes_declarees(reglages), seuil_absents=args.max_absent_percent)
    except ErreurSeuilAbsents:        # l'import est annulé : aucune écriture
        sys.exit(_echec(t("absent_share_exceeded", percent=f"{args.max_absent_percent:g}")))
    except db.ErreurBase as erreur:
        sys.exit(_echec(str(erreur)))
    except Exception as erreur:       # aucun détail : un message de la base pourrait citer une clé ou une valeur
        sys.exit(_echec(t("unexpected_error", name=type(erreur).__name__)))
    finally:
        if conn is not None:
            conn.close()
    afficher(comptes, cache is not None, args.dry_run, t)


if __name__ == "__main__":
    main()
