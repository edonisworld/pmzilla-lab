"""Magasin de la collecte de l'historique sur la base jetable, sous le rôle d'import (change database-only, D5 ; spec jira-flow-history
« History written in one transaction, no cache file »). Tâche 4.3, partie avec base : sautée sans elle (bash tools/dbtest.sh
history_jira), écrite pour être exécutée par l'auteur.

    bash tools/dbtest.sh history_jira

Le vrai magasin (history_store.MagasinHistorique) lit les tickets du schéma flow et y écrit les transitions, l'indicateur « avec
historique », les périodes d'étiquettes déclarées et de versions, et le passage « history », en une transaction. Données inventées.
"""
import datetime as dt
import importlib.util
import unittest
from pathlib import Path

ICI = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("aide_base_flow_store", ICI.parent / "flow_store" / "aide_base.py")
aide = importlib.util.module_from_spec(_spec)           # la base jetable de flow_store, sans mettre son dossier sur le chemin d'import
_spec.loader.exec_module(aide)
import db  # noqa: E402
import history_store  # noqa: E402

def instant(texte: str) -> dt.datetime:
    return dt.datetime.fromisoformat(texte)


class MagasinHistoriqueEnBase(aide.AvecBase):
    def setUp(self):
        aide.AvecBase.setUp(self)
        c = self.conn
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.teams (name) VALUES ('Alpha'), ('Beta')")
        for cle, equipe, resolu in (("PROJ-1", 1, "2026-09-10T10:00:00+02:00"), ("PROJ-2", 2, None), ("PROJ-3", 1, None)):
            c.execute("INSERT INTO flow.issues (key, project, type, status, created_at, resolved_at, updated_at, team_id) "
                      "VALUES (%s, 'PROJ', 'Story', 'Open', '2026-01-02T09:00:00+01:00', %s, '2026-09-20T09:00:00+02:00', %s)",
                      (cle, resolu, equipe))
            c.execute("INSERT INTO flow.issue_teams (issue_key, team_id, position) VALUES (%s, %s, 1)", (cle, equipe))
        c.execute("UPDATE flow.issues SET out_of_export_at = now() WHERE key = 'PROJ-3'")        # sorti de l'export : jamais interrogé
        c.execute("RESET ROLE")
        c.commit()
        self.magasins = []

    def magasin(self):
        connexion = db.connect(self.url, password=aide.MOT_DE_PASSE)
        connexion.execute("SET ROLE pmzilla_flow")
        magasin = history_store.MagasinHistorique(connexion)
        self.magasins.append(magasin)
        self.addCleanup(lambda: magasin.conn.closed or magasin.fermer())
        return magasin

    def compte(self, table):
        self.conn.rollback()
        return self.conn.execute(f"SELECT count(*) FROM flow.{table}").fetchone()[0]

    RESULTATS = {
        "PROJ-1": {"transitions": [(instant("2026-03-01T09:00:00+02:00"), "Open", "In Progress"),
                                   (instant("2026-03-05T09:00:00+02:00"), "In Progress", "Done")],
                   "etiquettes": [("cyc-a", instant("2026-03-01T09:00:00+02:00"), instant("2026-03-03T09:00:00+02:00"))],
                   "versions": [("V-1", instant("2026-01-02T09:00:00+01:00"), None)]},
        "PROJ-2": {"transitions": [], "etiquettes": None, "versions": []},
    }

    def test_les_tickets_a_interroger_ne_portent_ni_titre_ni_personne_et_excluent_les_sortis_de_l_export(self):
        tickets = {t["cle"]: t for t in self.magasin().tickets()}
        self.assertEqual(set(tickets), {"PROJ-1", "PROJ-2"})
        self.assertEqual(set(tickets["PROJ-1"]), {"cle", "projet", "type", "cree", "resolu", "maj", "a_historique", "equipes"})
        self.assertEqual((tickets["PROJ-1"]["equipes"], tickets["PROJ-1"]["a_historique"]), (["Alpha"], False))
        self.assertIsNone(tickets["PROJ-2"]["resolu"])

    def test_une_collecte_ecrit_transitions_drapeaux_periodes_et_passage(self):
        magasin = self.magasin()
        self.assertIsNone(magasin.derniere_collecte())
        self.assertEqual(magasin.enregistrer(self.RESULTATS, 0), (2, 2))
        self.assertEqual((self.compte("transitions"), self.compte("issue_label_periods"), self.compte("issue_version_periods")), (2, 1, 1))
        self.assertEqual(self.conn.execute("SELECT key FROM flow.issues WHERE has_history ORDER BY key").fetchall(),
                         [("PROJ-1",), ("PROJ-2",)])
        self.assertEqual(self.conn.execute("SELECT kind, queries_searched, all_queries FROM flow.raw_runs").fetchall(),
                         [("history", 0, False)])
        self.assertIsNotNone(self.magasin().derniere_collecte())

    def test_une_seconde_collecte_n_ajoute_ni_transition_ni_periode(self):
        magasin = self.magasin()
        magasin.enregistrer(self.RESULTATS, 0)
        self.assertEqual(self.magasin().enregistrer(self.RESULTATS, 0), (0, 0))
        self.assertEqual((self.compte("transitions"), self.compte("issue_label_periods")), (2, 1))

    def test_une_collecte_en_erreur_enregistre_son_passage_avec_le_nombre_d_erreurs_sans_avancer_la_collecte_reussie(self):
        """Change (bug du 404 permanent) : avant, un passage avec erreurs n'était pas enregistré. Il l'est, avec son nombre d'erreurs ;
        seul un passage sans erreur avance la dernière collecte réussie."""
        self.magasin().enregistrer(self.RESULTATS, 3, None, 2)
        self.assertEqual(self.conn.execute("SELECT kind, errors, not_found FROM flow.raw_runs").fetchall(), [("history", 3, 2)])
        self.assertEqual(self.compte("transitions"), 2)
        self.assertIsNone(self.magasin().derniere_collecte())
        self.magasin().enregistrer({}, 0, None, 4)                # des 404 seuls : collecte réussie
        self.assertIsNotNone(self.magasin().derniere_collecte())

    def test_les_404_consecutifs_sont_comptes_remis_a_zero_et_marques_disparus(self):
        magasin = self.magasin()
        self.assertEqual(magasin.introuvables(), ({}, set()))
        magasin.enregistrer({}, 1, {"PROJ-2": (1, False)})
        self.assertEqual(self.magasin().introuvables(), ({"PROJ-2": 1}, set()))
        self.magasin().enregistrer({}, 1, {"PROJ-2": (3, True)})
        self.assertEqual(self.magasin().introuvables(), ({"PROJ-2": 3}, {"PROJ-2"}))
        self.assertEqual(self.conn.execute("SELECT history_gone_at IS NOT NULL FROM flow.issues WHERE key = 'PROJ-2'").fetchone(), (True,))
        self.magasin().enregistrer({}, 0, {"PROJ-2": (0, False)})
        self.assertEqual(self.magasin().introuvables(), ({}, set()))
        self.assertEqual(self.conn.execute("SELECT history_gone_at FROM flow.issues WHERE key = 'PROJ-2'").fetchone(), (None,))

    def test_la_date_de_disparition_ne_bouge_pas_si_le_ticket_reste_disparu(self):
        self.magasin().enregistrer({}, 1, {"PROJ-2": (3, True)})
        premiere = self.conn.execute("SELECT history_gone_at FROM flow.issues WHERE key = 'PROJ-2'").fetchone()[0]
        self.conn.rollback()
        self.magasin().enregistrer({}, 1, {"PROJ-2": (4, True)})
        self.assertEqual(self.conn.execute("SELECT history_gone_at FROM flow.issues WHERE key = 'PROJ-2'").fetchone()[0], premiere)

    def test_un_ticket_sorti_de_l_export_n_est_pas_dans_le_suivi_et_un_inconnu_est_ignore(self):
        self.magasin().enregistrer({}, 1, {"PROJ-3": (3, True), "ZZZ-9": (3, True)})
        self.assertEqual(self.magasin().introuvables(), ({}, set()))

    def test_une_erreur_du_suivi_annule_aussi_les_transitions_et_le_passage(self):
        with self.assertRaises(Exception):
            self.magasin().enregistrer(self.RESULTATS, 0, {"PROJ-2": (-1, False)})          # refusé par la contrainte de la colonne
        self.assertEqual((self.compte("transitions"), self.compte("raw_runs")), (0, 0))

    def test_une_periode_qui_n_est_plus_voulue_est_retiree_pour_un_ticket_interroge(self):
        self.magasin().enregistrer(self.RESULTATS, 0)
        suivant = {"PROJ-1": {"transitions": [], "etiquettes": [], "versions": [("V-2", instant("2026-01-02T09:00:00+01:00"), None)]}}
        self.magasin().enregistrer(suivant, 0)
        self.conn.rollback()
        self.assertEqual(self.conn.execute("SELECT version FROM flow.issue_version_periods").fetchall(), [("V-2",)])
        self.assertEqual(self.compte("issue_label_periods"), 0)

    def test_etiquettes_non_suivies_laissent_les_periodes_en_place(self):
        self.magasin().enregistrer(self.RESULTATS, 0)
        sans_suivi = {"PROJ-1": {"transitions": [], "etiquettes": None, "versions": [("V-1", instant("2026-01-02T09:00:00+01:00"), None)]}}
        self.magasin().enregistrer(sans_suivi, 0)
        self.assertEqual(self.compte("issue_label_periods"), 1)

    def test_une_erreur_annule_toute_l_ecriture(self):
        invalide = {**self.RESULTATS, "PROJ-2": {"transitions": [], "etiquettes": [("cyc-a", None, None)], "versions": []}}
        with self.assertRaises(Exception):
            self.magasin().enregistrer(invalide, 0)
        self.assertEqual((self.compte("transitions"), self.compte("raw_runs"), self.compte("issue_label_periods")), (0, 0, 0))
        self.assertEqual(self.conn.execute("SELECT count(*) FROM flow.issues WHERE has_history").fetchone()[0], 0)

    def test_un_ticket_inconnu_de_la_base_est_ignore(self):
        resultats = {"ZZZ-9": {"transitions": [(instant("2026-03-01T09:00:00+02:00"), "Open", "Done")], "etiquettes": [], "versions": []}}
        self.assertEqual(self.magasin().enregistrer(resultats, 0), (0, 0))
        self.assertEqual(self.compte("transitions"), 0)

    def test_le_role_d_import_ne_lit_rien_hors_de_flow(self):
        connexion = self.magasin().conn
        with self.assertRaises(db.psycopg.errors.InsufficientPrivilege):
            connexion.execute("SELECT * FROM knowledge.books")


if __name__ == "__main__":
    unittest.main()
