# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pyyaml", "psycopg[binary]"]
# ///
"""
PMZilla Lab : import incrémental des exports Jira dans le schéma flow de la base (lot 6, Jira en base).

    uv run tools/flow_import.py <export.csv>... [--history [CACHE]] [--dry-run] [--language fr|en]

Les exports sont ceux de export_jira_api.py (voie unique ; aucun CSV manuel). Plusieurs fichiers : fusion par clé, le
dernier l'emporte. Sans --history, aucune transition n'est importée ; avec --history, le cache de history_jira.py
(Flux-Lab/historique/transitions.json par défaut) l'est.

Ce que l'outil écrit, dans le schéma flow, sous le rôle pmzilla_flow, en une seule transaction (annulée en cas d'erreur) :
  - flow.teams : une équipe par valeur du champ équipe, créée à la volée ;
  - flow.issues : INSERT ... ON CONFLICT (key) DO UPDATE, seulement si un champ diffère de la valeur entrante ;
  - flow.issue_teams et flow.links : la différence seulement (un ticket sans colonne de liens dans l'export garde ses liens) ;
  - flow.transitions : INSERT ... ON CONFLICT DO NOTHING, jamais de suppression ; les transitions d'une clé absente de
    flow.issues sont ignorées.
Un ticket absent du nouvel export n'est pas supprimé. Une colonne Updated absente ou illisible fait refuser l'export
avant toute écriture (code de sortie 1), sans repli sur l'instant de l'import.

Ce que l'outil n'affiche jamais : aucune clé de ticket, aucun nom d'équipe, aucune valeur de champ, y compris dans les
erreurs. La sortie ne compte que des effectifs (tickets lus, insérés, mis à jour, inchangés, écartés ; équipes créées ;
liens ajoutés ; transitions ajoutées, ignorées, illisibles). Une erreur de la base est réduite au nom de son type.

--dry-run calcule les mêmes comptes dans la base et annule la transaction : rien n'est écrit.

Seul l'utilisateur lance cet outil sur les vraies données : Claude Code ne le lance jamais (règles deny de
.claude/settings.json). Les tests passent par une base jetable et des données inventées.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import db                                               # noqa: E402
import flow_export_reader as lecteur                    # noqa: E402
import flux_jira                                        # noqa: E402
import history_common as commun                         # noqa: E402
from flow_import_messages import CATALOGS               # noqa: E402
from messages import Messages, add_language_option      # noqa: E402

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


def importer(conn, donnees: dict, cache: dict[str, dict] | None, zone, dry_run: bool = False) -> dict:
    """Écrit (ou, en essai à blanc, calcule puis annule) l'import dans une seule transaction. Rend les comptes."""
    tickets = donnees["tickets"]
    comptes = {"read": len(tickets), "unreadable": donnees["illisibles"]}
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
    parser.add_argument("--dry-run", action="store_true", help="calcule les comptes dans la base, annule, n'écrit rien")
    add_language_option(parser)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    t = Messages(CATALOGS, args.language)
    try:
        reglages = flux_jira.config(Messages(flux_jira.CATALOGS, args.language))
        zone = lecteur.fuseau(reglages)
        donnees = lecteur.lire_exports(args.export, reglages)
    except lecteur.ErreurExport as erreur:
        sys.exit(_echec(t(erreur.code, **erreur.valeurs)))
    cache = None
    if args.history is not None:
        cache = charger_cache(Path(args.history).expanduser() if args.history else flux_jira.HISTORIQUE_DEFAUT, t)
    conn = None
    try:
        conn = db.connect()
        comptes = importer(conn, donnees, cache, zone, args.dry_run)
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
