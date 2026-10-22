"""Reconstruction depuis la couche brute sur la base jetable (changes jira-data-architecture, D4, D5, et database-only, D16, tâche 14.5 ;
spec jira-flow-raw-layer). Partie avec base : sautée sans elle (bash tools/dbtest.sh flow_import), écrite pour être exécutée par l'auteur.

    bash tools/dbtest.sh flow_import

Réécriture des dix tests du fichier du même nom supprimé avec l'import des fichiers CSV (commit 5a1fa5c1). Aucun fichier, aucun CSV : les
tickets viennent de passages d'export écrits dans la couche brute par flow_raw.MagasinBase sous le rôle d'import (l'écriture de l'export
rejouée sans Jira), puis dérivés vers les tables courantes par flow_raw.deriver (ce que flow_import.py appelle) ; `--rebuild` est lancé
par flow_import.main sur la base jetable. Données inventées (PROJ-n, équipes Alpha et Beta). Ce qui a changé de forme est dit au test.
"""
import contextlib
import datetime as dt
import io
import unittest
from unittest import mock

from test_derivation_base import aide, db, flow_raw, instantane
import flow_import

UTC = dt.timezone.utc
CONNECT_REEL = db.connect


class AvecCoucheBrute(aide.AvecBase):
    """Base jetable migrée ; le jeu de trois tickets est écrit comme un export puis dérivé (ancien « exporter_puis_importer »)."""

    def setUp(self):
        aide.AvecBase.setUp(self)
        self.role = CONNECT_REEL(self.url, password=aide.MOT_DE_PASSE)
        self.role.execute("SET ROLE pmzilla_flow")
        self.addCleanup(self.role.close)

    # --- le jeu ----------------------------------------------------------------------------------------------------------
    def instantanes_du_jeu(self):
        """PROJ-1 (lien Blocks vers PROJ-2), PROJ-2 (équipes Beta puis Alpha), PROJ-3 résolu. Aucun identifiant d'équipe Jira, comme les
        anciennes lignes de CSV sans objet d'équipe. La résolution est relative au jour du test (30 jours) : une date fixe sortirait de la
        règle de conservation d'un an."""
        resolu = dt.datetime.now(UTC) - dt.timedelta(days=30)

        def sans_id(*noms):
            return [{"name": n, "jira_team_id": None} for n in noms]
        return {
            "PROJ-1": instantane("PROJ-1", status="In Progress", status_category="In Progress", teams=sans_id("Alpha"),
                                 links=[{"target": "PROJ-2", "type": "Blocks", "direction": "outward"}]),
            "PROJ-2": instantane("PROJ-2", status="In Progress", status_category="In Progress", teams=sans_id("Beta", "Alpha")),
            "PROJ-3": instantane("PROJ-3", status="Done", status_category="Done", resolved_at=resolu, resolution="Done",
                                 teams=sans_id("Alpha"))}

    def exporter(self, instantanes, toutes=True):
        """Un passage d'export qui voit ces tickets et écrit leurs instantanés (sous le rôle d'import)."""
        flow_raw.MagasinBase(self.role).enregistrer(genre="export", nb_requetes=1, toutes=toutes, vus=list(instantanes),
                                                    instantanes=dict(instantanes))

    def exporter_puis_importer(self):
        """Rejoue l'export (couche brute) puis l'import des tables courantes depuis cette couche."""
        instantanes = self.instantanes_du_jeu()
        self.exporter(instantanes)
        flow_raw.deriver(self.role)
        return instantanes

    def vider_la_couche_brute(self):
        """Tables courantes sans couche brute : l'état d'une base importée avant que la couche brute existe (remplace l'ancien import
        d'un CSV seul, qui n'écrivait pas la couche brute)."""
        self.alterer("DELETE FROM flow.raw_issue_snapshots", "DELETE FROM flow.raw_run_sightings", "DELETE FROM flow.raw_runs")

    # --- lecture et altération ----------------------------------------------------------------------------------------
    def alterer(self, *requetes):
        self.conn.rollback()
        self.conn.execute("SET ROLE pmzilla_flow")
        for sql in requetes:
            self.conn.execute(sql)
        self.conn.execute("RESET ROLE")
        self.conn.commit()

    def un(self, sql, params=None):
        self.conn.rollback()
        return self.conn.execute(sql, params).fetchone()

    def tout(self, sql, params=None):
        self.conn.rollback()
        return self.conn.execute(sql, params).fetchall()

    def nombre(self, table):
        return self.un(f"SELECT count(*) FROM flow.{table}")[0]

    def etat_brut(self):
        return {t: self.tout(f"SELECT * FROM flow.{t} ORDER BY 1, 2") for t in ("raw_runs", "raw_run_sightings", "raw_issue_snapshots")}

    def reconstruction(self, *options, langue="en"):
        """flow_import.main --rebuild sur la base jetable : (code, sortie, erreur)."""
        sortie, erreur = io.StringIO(), io.StringIO()
        code = 0

        def connexion(*args, **kw):
            c = CONNECT_REEL(self.url, password=aide.MOT_DE_PASSE)
            c.execute("SET ROLE pmzilla_flow")
            return c
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur), \
                mock.patch.object(db, "connect", side_effect=connexion):
            try:
                flow_import.main(["--rebuild", *options, "--language", langue])
            except SystemExit as arret:
                code = arret.code if isinstance(arret.code, int) else (0 if arret.code is None else 1)
        return code, sortie.getvalue(), erreur.getvalue()


class ApresUnExport(AvecCoucheBrute):
    def test_juste_apres_un_export_et_l_import_aucune_difference(self):
        self.exporter_puis_importer()
        code, sortie, erreur = self.reconstruction()
        self.assertEqual(code, 0, erreur)
        self.assertEqual(sortie.splitlines(), ["rebuild: 3 tickets compared, 0 would change", "rebuild dry run: nothing written"])

    def test_ligne_alteree_comptee_sans_valeur_puis_restauree(self):
        self.exporter_puis_importer()
        self.alterer("UPDATE flow.issues SET status = 'Zzz-altere' WHERE key = 'PROJ-1'")
        code, sortie, _ = self.reconstruction()
        self.assertEqual(code, 0)
        self.assertIn("rebuild: 3 tickets compared, 1 would change", sortie)
        self.assertIn("rebuild: status differs: 1", sortie)
        self.assertNotIn("Zzz", sortie)
        self.assertEqual(self.un("SELECT status FROM flow.issues WHERE key = 'PROJ-1'")[0], "Zzz-altere")     # essai à blanc
        avant = self.etat_brut()
        code, sortie, _ = self.reconstruction("--apply")
        self.assertEqual(code, 0)
        self.assertEqual(sortie.splitlines()[-1], "rebuild done: 1 tickets changed")
        self.assertEqual(self.un("SELECT status FROM flow.issues WHERE key = 'PROJ-1'")[0], "In Progress")
        self.assertEqual(self.etat_brut(), avant)                            # ajout seulement : la couche brute n'a pas bougé
        self.assertIn("0 would change", self.reconstruction()[1])

    def test_equipes_et_liens_restaures(self):
        self.exporter_puis_importer()
        self.alterer("DELETE FROM flow.issue_teams WHERE issue_key = 'PROJ-2'", "DELETE FROM flow.links WHERE source_key = 'PROJ-1'")
        code, sortie, _ = self.reconstruction("--apply")
        self.assertEqual(code, 0)
        self.assertIn("rebuild: teams differs: 1", sortie)
        self.assertIn("rebuild: links differs: 1", sortie)
        self.assertEqual([r[0] for r in self.tout("SELECT t.name FROM flow.issue_teams it JOIN flow.teams t ON t.id = it.team_id "
                                                    "WHERE it.issue_key = 'PROJ-2' ORDER BY it.position")], ["Beta", "Alpha"])
        self.assertEqual(self.tout("SELECT target_key FROM flow.links WHERE source_key = 'PROJ-1'"), [("PROJ-2",)])
        self.assertIn("0 would change", self.reconstruction()[1])

    def test_marque_de_sortie_de_l_export_inchangee(self):
        self.exporter_puis_importer()
        self.alterer("UPDATE flow.issues SET out_of_export_at = now() - interval '3 days', status = 'Zzz' WHERE key = 'PROJ-1'")
        avant = self.un("SELECT out_of_export_at FROM flow.issues WHERE key = 'PROJ-1'")[0]
        self.assertEqual(self.reconstruction("--apply")[0], 0)
        self.assertEqual(self.un("SELECT out_of_export_at FROM flow.issues WHERE key = 'PROJ-1'")[0], avant)

    def test_liens_non_suivis_gardent_les_derniers_liens(self):
        instantanes = self.exporter_puis_importer()
        sans_liens = dict(instantanes["PROJ-1"], links=None, status="Done")
        sans_liens["content_hash"] = flow_raw.empreinte(sans_liens)
        self.exporter({"PROJ-1": sans_liens})                              # nouvel export sans colonne de liens
        self.alterer("UPDATE flow.issues SET status = 'Done' WHERE key = 'PROJ-1'")
        self.assertEqual(self.reconstruction("--apply")[0], 0)
        self.assertEqual(self.tout("SELECT target_key FROM flow.links WHERE source_key = 'PROJ-1'"), [("PROJ-2",)])

    def test_erreur_pendant_l_application_annule_tout(self):
        self.exporter_puis_importer()
        self.alterer("UPDATE flow.issues SET status = 'Zzz-altere' WHERE key = 'PROJ-1'")

        def echoue(cur, changements, vivant):
            cur.execute("UPDATE flow.issues SET status = 'Moitie' WHERE key = 'PROJ-1'")
            raise RuntimeError("ZZSECRET")
        with mock.patch.object(flow_raw, "_appliquer", echoue):
            code, sortie, erreur = self.reconstruction("--apply")
        self.assertEqual(code, 1)
        self.assertIn("RuntimeError", erreur)
        self.assertNotIn("ZZSECRET", sortie + erreur)
        self.assertEqual(self.un("SELECT status FROM flow.issues WHERE key = 'PROJ-1'")[0], "Zzz-altere")


class RefusEtAmorcage(AvecCoucheBrute):
    def test_couche_brute_vide(self):
        """Forme changée : l'ancien test importait un CSV, qui ne touchait pas la couche brute. Les tables courantes sont dérivées d'un
        export puis la couche brute est vidée : même état (tickets stockés, couche brute vide)."""
        self.exporter_puis_importer()
        self.vider_la_couche_brute()
        for langue, phrase in (("en", "raw layer empty: rebuild refused"), ("fr", "couche brute vide : reconstruction refusée")):
            code, sortie, erreur = self.reconstruction(langue=langue)
            self.assertEqual(code, 1)
            self.assertIn(phrase, sortie + erreur)
        self.assertEqual(self.nombre("raw_runs"), 0)

    def test_tickets_sans_instantane(self):
        """Forme changée : l'ancien test écrivait la couche brute de deux tickets puis important un CSV de trois. Ici les trois sont
        dérivés d'un export, puis les instantanés (et les visites) de PROJ-3 sont retirés : PROJ-3 est stocké sans instantané."""
        self.exporter_puis_importer()
        self.alterer("DELETE FROM flow.raw_run_sightings WHERE issue_key = 'PROJ-3'",
                     "DELETE FROM flow.raw_issue_snapshots WHERE issue_key = 'PROJ-3'")
        code, sortie, erreur = self.reconstruction()
        self.assertEqual(code, 1)
        self.assertIn("tickets without snapshot: 1, rebuild refused", sortie + erreur)

    def test_amorcage_puis_reconstruction_sans_difference(self):
        """Forme changée : même état de départ que test_couche_brute_vide (tables courantes sans couche brute) au lieu d'un CSV seul."""
        self.exporter_puis_importer()
        self.vider_la_couche_brute()                                       # importée avant que la couche brute existe
        code, sortie, erreur = self.reconstruction("--seed")
        self.assertEqual(code, 0, erreur)
        self.assertEqual(sortie.splitlines()[0], "seed: 3 snapshots built from the live tables")
        self.assertIn("rebuild: 3 tickets compared, 0 would change", sortie)
        self.assertEqual(self.tout("SELECT kind FROM flow.raw_runs"), [("seed",)])
        self.assertEqual(self.tout("SELECT DISTINCT seeded FROM flow.raw_issue_snapshots"), [(True,)])
        equipes = self.tout("SELECT teams FROM flow.raw_issue_snapshots WHERE issue_key = 'PROJ-2'")[0][0]
        self.assertEqual([e["name"] for e in equipes], ["Beta", "Alpha"])
        self.assertEqual([e["jira_team_id"] for e in equipes], [None, None])
        self.assertEqual(self.reconstruction("--seed")[1].splitlines()[0], "seed: 0 snapshots built from the live tables")
        self.assertEqual(self.nombre("raw_runs"), 1)                           # jamais de second amorçage

    def test_le_prochain_export_ajoute_un_instantane_avec_les_identifiants(self):
        """Forme changée : même état de départ ; le nouvel export vient de instantane() avec identifiants au lieu de
        export_jira_api.instantanes_des_lignes sur le CSV."""
        instantanes = self.exporter_puis_importer()
        self.vider_la_couche_brute()
        self.reconstruction("--seed")
        avec_ids = dict(instantanes["PROJ-1"], teams=[{"name": "Alpha", "jira_team_id": "11"}])
        avec_ids["content_hash"] = flow_raw.empreinte(avec_ids)
        self.exporter({"PROJ-1": avec_ids})
        self.assertEqual(self.tout("SELECT count(*) FROM flow.raw_issue_snapshots WHERE issue_key = 'PROJ-1'"), [(2,)])


if __name__ == "__main__":
    unittest.main()
