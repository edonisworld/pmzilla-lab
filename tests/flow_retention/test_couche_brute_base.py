"""La couche brute sous la règle de conservation, sur la base jetable (change jira-data-architecture, D6 ; spec jira-flow-retention
« Raw layer under the rule »). Tâche 4.7, partie avec base : sautée sans elle (bash tools/dbtest.sh flow_retention).

    bash tools/dbtest.sh flow_retention

Les scénarios de la spec : un ticket résolu hors règle perd ses instantanés avec lui ; un ticket ouvert aux instantanés plus vieux que
l'âge maximal garde le dernier ; les passages restent ; l'essai ne supprime rien. Données inventées (PROJ-n).
"""
import unittest

from aide_flow_retention import AUJOURDHUI
from test_base import AvecBase, fr


class CoucheBrute(AvecBase):
    def passage(self, jours: int, genre: str = "export") -> int:
        return self.conn.execute(
            "INSERT INTO flow.raw_runs (kind, run_at, queries_searched, all_queries) "
            "VALUES (%s, %s::timestamptz - make_interval(days => %s), 1, true) RETURNING id",
            (genre, f"{AUJOURDHUI}T12:00:00+00", jours)).fetchone()[0]

    def instantane(self, cle: str, passage: int) -> None:
        self.conn.execute(
            "INSERT INTO flow.raw_issue_snapshots (issue_key, run_id, updated_at, project, type, status, created_at, content_hash) "
            "VALUES (%s, %s, now(), 'PROJ', 'Story', 'X', '2020-01-01', %s)", (cle, passage, f"h{passage}"))

    def visite(self, cle: str, passage: int) -> None:
        self.conn.execute("INSERT INTO flow.raw_run_sightings (run_id, issue_key) VALUES (%s, %s)", (passage, cle))

    def n(self, table: str, cle: str | None = None) -> int:
        self.conn.rollback()
        self.conn.execute("SET ROLE pmzilla_flow")
        if cle is None:
            return self.conn.execute(f"SELECT count(*) FROM flow.{table}").fetchone()[0]
        return self.conn.execute(f"SELECT count(*) FROM flow.{table} WHERE issue_key = %s", (cle,)).fetchone()[0]

    def jeu_de_deux_tickets(self):
        self.ticket("PROJ-1", jours_resolu=400)                  # résolu hors règle
        self.ticket("PROJ-2")                                    # ouvert, encore dans l'export
        p1, p2, p3 = self.passage(500), self.passage(450), self.passage(2)
        for passage in (p1, p2):
            self.instantane("PROJ-1", passage)
            self.visite("PROJ-1", passage)
        for passage in (p1, p2, p3):
            self.instantane("PROJ-2", passage)
            self.visite("PROJ-2", passage)
        self.conn.commit()
        return p1, p2, p3

    def test_ticket_resolu_hors_regle_deux_instantanes_comptes_puis_supprimes_avec_lui(self):
        self.ticket("PROJ-1", jours_resolu=400)
        p1, p2 = self.passage(3), self.passage(2)                # récents : seule l'horloge du ticket les met hors règle
        for passage in (p1, p2):
            self.instantane("PROJ-1", passage)
            self.visite("PROJ-1", passage)
        self.conn.commit()
        code, sortie, erreur = self.lancer_base("check", "--language", "en")
        self.assertEqual(code, 4, erreur)
        self.assertIn("raw layer: 2 snapshots out of rule", sortie.splitlines())
        code, _, erreur = self.lancer_base("purge", "--apply", "--language", "en")
        self.assertEqual(code, 0, erreur)
        self.assertEqual((self.n("raw_issue_snapshots", "PROJ-1"), self.n("raw_run_sightings", "PROJ-1")), (0, 0))
        self.assertEqual(self.cles(), [])
        self.assertEqual(self.n("raw_runs"), 2)                  # les passages restent

    def test_ticket_ouvert_aux_vieux_instantanes_le_dernier_reste(self):
        self.ticket("PROJ-2")
        passages = [self.passage(jours) for jours in (600, 500, 400)]       # tous plus vieux que l'âge maximal, aucun plus récent
        for passage in passages:
            self.instantane("PROJ-2", passage)
            self.visite("PROJ-2", passage)
        self.conn.commit()
        code, sortie, _ = self.lancer_base("check", "--language", "en")
        self.assertEqual(code, 4)
        self.assertIn("raw layer: 2 snapshots out of rule", sortie.splitlines())
        self.assertEqual(self.lancer_base("purge", "--apply")[0], 0)
        self.assertEqual(self.n("raw_issue_snapshots", "PROJ-2"), 1)
        self.assertEqual(self.n("raw_run_sightings", "PROJ-2"), 1)
        restant = self.conn.execute("SELECT run_id FROM flow.raw_issue_snapshots WHERE issue_key = 'PROJ-2'").fetchone()[0]
        self.assertEqual(restant, passages[-1])
        self.assertEqual(self.n("raw_runs"), 3)
        self.assertEqual(self.lancer_base("check")[0], 0)                  # un contrôle après la purge sort 0

    def test_deux_tickets_chacun_sa_regle(self):
        p1, p2, p3 = self.jeu_de_deux_tickets()
        self.assertEqual(self.lancer_base("purge", "--apply")[0], 0)
        self.assertEqual(self.n("raw_issue_snapshots", "PROJ-1"), 0)        # le ticket résolu hors règle a tout perdu
        self.assertEqual(self.n("raw_issue_snapshots", "PROJ-2"), 1)        # 500 et 450 jours : plus vieux que l'âge maximal ; le dernier reste
        self.assertEqual(self.n("raw_run_sightings", "PROJ-2"), 1)

    def test_essai_ne_supprime_rien(self):
        self.jeu_de_deux_tickets()
        avant = (self.n("raw_issue_snapshots"), self.n("raw_run_sightings"), self.n("raw_runs"))
        code, sortie, _ = self.lancer_base("purge", "--language", "en")
        self.assertEqual(code, 0)
        self.assertIn("raw layer:", sortie)
        self.assertEqual((self.n("raw_issue_snapshots"), self.n("raw_run_sightings"), self.n("raw_runs")), avant)

    def test_des_visites_seules_hors_regle_sont_comptees_et_purgees(self):
        """Un ticket ouvert, un seul instantané (le dernier, gardé) et quatre visites : les trois plus vieilles que l'âge maximal partent."""
        self.ticket("PROJ-2")
        passages = [self.passage(jours) for jours in (600, 500, 400, 2)]
        self.instantane("PROJ-2", passages[0])
        for passage in passages:
            self.visite("PROJ-2", passage)
        self.conn.commit()
        code, sortie, erreur = self.lancer_base("check", "--language", "en")
        self.assertEqual(code, 4, erreur)                                       # aucun instantané hors règle, pourtant le contrôle sort 4
        self.assertIn("raw layer: 0 snapshots out of rule", sortie.splitlines())
        self.assertTrue(sortie.rstrip().endswith("retention check: 3 items out of rule"), sortie)
        self.assertEqual(self.lancer_base("purge", "--apply")[0], 0)
        self.assertEqual(self.n("raw_run_sightings", "PROJ-2"), 1)              # la dernière visite reste
        self.assertEqual(self.n("raw_issue_snapshots", "PROJ-2"), 1)
        self.assertEqual(self.n("raw_runs"), 4)
        self.assertEqual(self.lancer_base("check")[0], 0)

    def test_une_cle_absente_de_flow_issues_perd_son_dernier_instantane_au_bout_d_un_an(self):
        """L'horloge d'un ticket passe par flow.issues : sans ligne, la date de la dernière visite plus la conservation la remplace."""
        for cle, jours in (("PROJ-8", 400), ("PROJ-9", 2)):                    # aucune des deux clés n'est dans flow.issues
            passage = self.passage(jours)
            self.instantane(cle, passage)
            self.visite(cle, passage)
        self.conn.commit()
        code, sortie, erreur = self.lancer_base("check", "--language", "en")
        self.assertEqual(code, 4, erreur)
        self.assertIn("raw layer: 1 snapshots out of rule", sortie.splitlines())
        self.assertEqual(self.lancer_base("purge", "--apply")[0], 0)
        self.assertEqual((self.n("raw_issue_snapshots", "PROJ-8"), self.n("raw_run_sightings", "PROJ-8")), (0, 0))
        self.assertEqual((self.n("raw_issue_snapshots", "PROJ-9"), self.n("raw_run_sightings", "PROJ-9")), (1, 1))   # récente : reste
        self.assertEqual(self.n("raw_runs"), 2)

    def test_le_role_d_import_peut_supprimer_la_couche_brute(self):
        passage = self.passage(5)
        self.instantane("PROJ-1", passage)
        self.conn.commit()
        self.conn.execute("SET ROLE pmzilla_flow")
        self.conn.execute("DELETE FROM flow.raw_issue_snapshots")
        self.conn.commit()          # sans validation, le rollback par lequel n() commence annulerait la suppression avant le comptage
        self.assertEqual(self.n("raw_issue_snapshots"), 0)


if __name__ == "__main__":
    unittest.main()
