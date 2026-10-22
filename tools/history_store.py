"""
PMZilla Lab : magasin de la collecte de l'historique dans le schéma flow (change database-only, D5).

Module de bibliothèque, sans ligne de commande. history_jira.py `collect` lit ici les tickets à interroger et écrit le résultat,
sous le rôle d'import de flow, en UNE transaction (annulée en cas d'erreur) :
  - les nouvelles transitions de statut (flow.transitions : jamais supprimées, jamais en double) ;
  - l'indicateur « avec historique » de chaque ticket interrogé (flow.issues.has_history) ;
  - les périodes d'étiquettes déclarées et de versions (flow.issue_label_periods, flow.issue_version_periods), construites par
    history_common.construire_periodes ; pour un ticket interrogé dont les valeurs courantes sont connues, l'ensemble construit fait
    foi : une période en base qui n'y figure plus est retirée ;
  - le suivi des 404 : compteur de passages consécutifs où Jira ne trouve pas le ticket (flow.issues.history_not_found) et date de
    disparition (history_gone_at) ; un ticket disparu n'est plus interrogé ;
  - un passage « history » dans flow.raw_runs, enregistré même avec des erreurs, avec le nombre d'erreurs passagères (errors) et de 404
    (not_found) ; la dernière collecte réussie est celle du dernier passage sans erreur passagère (aucune donnée de ticket, aucun nom de requête).
La lecture rend, pour chaque ticket non sorti de l'export, ce qu'il faut pour choisir les tickets à interroger. Aucun titre, aucune
description, aucune personne. Les sorties de ce module ne portent aucune clé, aucun nom d'équipe, aucune valeur.
"""
from __future__ import annotations

import datetime as dt

LOT = 2000
LOT_TRANSITIONS = 5000

TABLES_PERIODES = {"etiquettes": ("flow.issue_label_periods", "label"), "versions": ("flow.issue_version_periods", "version")}

SQL_TICKETS = """
SELECT i.key, i.project, i.type, i.created_at, i.resolved_at, i.updated_at, i.has_history,
       coalesce((SELECT array_agg(t.name ORDER BY it.position) FROM flow.issue_teams it
                 JOIN flow.teams t ON t.id = it.team_id WHERE it.issue_key = i.key), ARRAY[]::text[])
FROM flow.issues i WHERE i.out_of_export_at IS NULL ORDER BY i.key
"""
SQL_DERNIERE_COLLECTE = "SELECT max(run_at) FROM flow.raw_runs WHERE kind = 'history' AND errors = 0"      # un passage avec erreurs n'avance pas
SQL_INTROUVABLES = ("SELECT key, history_not_found, history_gone_at IS NOT NULL FROM flow.issues "
                    "WHERE out_of_export_at IS NULL AND (history_not_found > 0 OR history_gone_at IS NOT NULL)")


def _par_lots(elements: list, taille: int):
    for debut in range(0, len(elements), taille):
        yield elements[debut:debut + taille]


class MagasinHistorique:
    """Magasin de l'historique dans la base, sous le rôle d'import (connexion ouverte par l'appelant). Une erreur de la base remonte
    telle quelle : l'appelant n'en affiche que le type."""

    def __init__(self, conn):
        self.conn = conn

    def tickets(self) -> list[dict]:
        """Les tickets stockés qui ne sont pas sortis de l'export : {"cle", "projet", "type", "cree", "resolu", "maj" (instants avec
        fuseau, ou None), "a_historique", "equipes"}."""
        lignes = self.conn.execute(SQL_TICKETS).fetchall()
        self.conn.rollback()
        return [{"cle": cle, "projet": projet or (cle.rsplit("-", 1)[0].upper() if "-" in cle else ""), "type": (typ or "").strip(),
                 "cree": cree, "resolu": resolu, "maj": maj, "a_historique": bool(historique), "equipes": list(equipes or [])}
                for cle, projet, typ, cree, resolu, maj, historique, equipes in lignes]

    def derniere_collecte(self) -> dt.datetime | None:
        """Instant du dernier passage « history » (la dernière collecte réussie), ou None."""
        instant = self.conn.execute(SQL_DERNIERE_COLLECTE).fetchone()[0]
        self.conn.rollback()
        return instant

    def introuvables(self) -> tuple[dict[str, int], set[str]]:
        """Suivi des 404 : ({clé: passages consécutifs en 404} pour les tickets au compteur non nul, {clés des tickets marqués disparus}).
        Un ticket disparu n'est plus interrogé (sauf --refresh)."""
        lignes = self.conn.execute(SQL_INTROUVABLES).fetchall()
        self.conn.rollback()
        return ({cle: n for cle, n, _ in lignes if n}, {cle for cle, _, disparu in lignes if disparu})

    def enregistrer(self, resultats: dict[str, dict], erreurs: int = 0, suivi: dict[str, tuple[int, bool]] | None = None,
                    introuvables: int = 0) -> tuple[int, int]:
        """Écrit en une transaction les résultats de la collecte. `resultats` : clé -> {"transitions": [(instant avec fuseau, état de
        départ, état d'arrivée)], "etiquettes": [(valeur, ajoutée, retirée ou None)] ou None (étiquettes non suivies), "versions":
        [(valeur, ajoutée, retirée ou None)]}. `erreurs` : nombre d'erreurs passagères de la collecte ; `introuvables` : nombre de réponses
        404. Le passage « history » est enregistré dans tous les cas avec ces deux nombres, mais seul un passage sans erreur passagère
        avance la dernière collecte réussie (les 404 ne la bloquent pas). `suivi` : clé ->
        (passages consécutifs en 404, disparu ou non), pour les seuls tickets dont le suivi change. Rend (transitions ajoutées, périodes
        écrites ou modifiées)."""
        cur = self.conn.cursor()
        try:
            ajoutees = self._transitions(cur, resultats)
            periodes = self._periodes(cur, resultats)
            self._suivi(cur, suivi or {})
            cur.execute("INSERT INTO flow.raw_runs (kind, queries_searched, all_queries, errors, not_found) "
                        "VALUES ('history', 0, false, %s, %s)", (max(0, int(erreurs)), max(0, int(introuvables))))
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise
        return ajoutees, periodes

    @staticmethod
    def _suivi(cur, suivi: dict[str, tuple[int, bool]]) -> None:
        """Compteur de 404 consécutifs et date de disparition. Un ticket qui reste disparu garde sa date ; un ticket trouvé la perd."""
        if not suivi:
            return
        stockees = {cle.upper(): cle for (cle,) in cur.execute("SELECT key FROM flow.issues").fetchall()}
        lignes = [(stockees[cle.upper()], compteur, bool(disparu)) for cle, (compteur, disparu) in suivi.items() if cle.upper() in stockees]
        for lot in _par_lots(lignes, LOT):
            cur.execute("UPDATE flow.issues i SET history_not_found = d.n, "
                        "history_gone_at = CASE WHEN d.g THEN coalesce(i.history_gone_at, now()) ELSE NULL END "
                        "FROM unnest(%s::text[], %s::integer[], %s::boolean[]) AS d(k, n, g) WHERE i.key = d.k",
                        tuple(list(colonne) for colonne in zip(*lot)))

    @staticmethod
    def _transitions(cur, resultats: dict[str, dict]) -> int:
        stockees = {cle.upper(): cle for (cle,) in cur.execute("SELECT key FROM flow.issues").fetchall()}
        lignes: list[tuple] = []
        avec_entree: list[str] = []
        for cle, resultat in resultats.items():
            vrai = stockees.get(cle.upper())
            if vrai is None:
                continue
            avec_entree.append(vrai)
            lignes += [(vrai, instant, depart or None, arrivee) for instant, depart, arrivee in resultat["transitions"] if arrivee]
        ajoutees = 0
        for lot in _par_lots(lignes, LOT_TRANSITIONS):
            ajoutees += cur.execute(
                "INSERT INTO flow.transitions (issue_key, transitioned_at, from_status, to_status) "
                "SELECT * FROM unnest(%s::text[], %s::timestamptz[], %s::text[], %s::text[]) ON CONFLICT DO NOTHING",
                tuple(list(colonne) for colonne in zip(*lot))).rowcount
        for lot in _par_lots(avec_entree, LOT):
            cur.execute("UPDATE flow.issues SET has_history = true WHERE key = ANY(%s) AND NOT has_history", (lot,))
        return ajoutees

    @staticmethod
    def _periodes(cur, resultats: dict[str, dict]) -> int:
        stockees = {cle.upper(): cle for (cle,) in cur.execute("SELECT key FROM flow.issues").fetchall()}
        ecrites = 0
        for nature, (table, colonne) in TABLES_PERIODES.items():
            voulu: dict[tuple, dt.datetime | None] = {}
            complets: set[str] = set()
            for cle, resultat in resultats.items():
                vrai = stockees.get(cle.upper())
                periodes = resultat.get(nature)
                if vrai is None or periodes is None:
                    continue
                complets.add(vrai)
                for valeur, debut, fin in periodes:
                    voulu[(vrai, valeur, debut)] = fin
            if not complets:
                continue
            existant: dict[tuple, dt.datetime | None] = {}
            for lot in _par_lots(sorted(complets), LOT):
                for cle, valeur, debut, fin in cur.execute(
                        f"SELECT issue_key, {colonne}, added_at, removed_at FROM {table} WHERE issue_key = ANY(%s::text[])",
                        (lot,)).fetchall():
                    existant[(cle, valeur, debut)] = fin
            a_retirer = [k for k in existant if k not in voulu]
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
            ecrites += len(a_ecrire)
        return ecrites

    def fermer(self) -> None:
        self.conn.close()
