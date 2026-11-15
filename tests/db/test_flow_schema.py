"""
Tests de la migration 0002 (schéma flow, lot 6) et du rôle limité aux vues, sur une base jetable.

    uv run --with "psycopg[binary]" python -m unittest discover -s tests/db -v

Aucune donnée réelle : tickets inventés (PROJ-1, ...), équipes inventées. Les tests avec base sont sautés si Docker ne tourne pas.
"""
import contextlib
import re
import secrets
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import test_db as base          # noqa: E402  (même dossier : connexion, base jetable, mot de passe)
from test_db import db          # noqa: E402

INTERDITES = {"summary", "title", "description", "assignee", "reporter", "creator", "author", "labels", "comment", "name_of_person",
              "po", "product_owner", "person"}          # R-58 (D3, D20) : ni PO ni donnée personnelle
TABLES_BRUTES = {"raw_runs", "raw_run_sightings", "raw_issue_snapshots",
                 "raw_version_snapshots"}      # couche brute datée (change jira-data-architecture) ; raw_version_snapshots : jira-delivery-fields, R-20261102-16 à -36 (0032)
TABLES_LIVRAISON = {"issue_delivery_fields", "sprints", "issue_current_sprints", "issue_current_asset_versions", "issue_delivery_options",
                    "issue_defect_fields", "issue_sprint_periods", "issue_asset_version_periods",
                    "release_versions"}      # champs de livraison (jira-delivery-fields, R-20261102-16 à -36, migration 0032)
TABLES_PHOTO = {"version_photo_versions", "version_photo_runs", "version_photo_weeks", "version_photo_rows",
                "version_photo_n"}                          # magasin des photos de qualité par version (migration 0019, change version-quality-photo)
TABLES_REFERENTIEL = {"ref_cycles", "ref_labels", "ref_dw_columns", "ref_dw_statuses", "ref_state",
                      "ref_flow_statuses", "ref_unplanned_types", "ref_blocking_link_types"}   # référentiel des cycles (change cycle-referential-schema, décision R-20261028-91) et ses définitions (change flow-definitions-referential, décision R-20261029-09)
TABLES = {"teams", "issues", "issue_teams", "transitions", "links", "issue_label_periods", "issue_version_periods",
          "issue_current_versions"} | TABLES_BRUTES | TABLES_PHOTO | TABLES_REFERENTIEL | TABLES_LIVRAISON      # issue_current_versions : migration 0017 (change flow-version-share)
TABLE_ETIQUETTES = "issue_label_periods"                  # périodes d'étiquettes déclarées (migration 0008)
TABLE_ETIQUETTES_REFERENTIEL = "ref_labels"               # seconde et dernière table d'étiquettes, sans ticket (décision R-20261028-91, change cycle-referential-schema)
TABLE_VERSIONS = "issue_version_periods"                  # périodes de fixVersion (migration 0008)
VUES = {"v_team_status", "v_team_weekly_resolved", "v_team_open_age", "v_team_dependencies"}      # les quatre vues agrégées du rôle des vues
VUES_NOMS = {"v_teams", "v_team_jira_ids"}               # les deux vues des noms d'équipe, rôle des vues (migration 0014, change team-names-readable) ; à part de VUES
                                                         # car v_teams lit le type d'équipe et v_team_jira_ids la couche brute, ce que d'autres tests refusent aux quatre
VUE_EQUIPES_VUES = "v_team_tickets_seen"                  # revue du catalogue de check-teams : rôle en lecture seule seulement (migration 0013, D13)
VUE_PART_VERSIONS = "v_team_fix_version_share"           # part des items terminés avec une fix version, rôle des vues (migration 0018, change flow-version-share)
VUES_PHOTO = {"v_version_quality_photo", "v_team_fix_version_lag"}   # photo de qualité par version et retard de la fix version, rôle des vues (migration 0020, change version-quality-photo)
VUES_TRANCHE_1 = {"v_team_lead_time_throughput", "v_task_without_team_share", "v_team_ready_queue", "v_team_blocked_share", "v_unplanned_share"}   # cinq vues agrégées de la tranche 1 de Mothra, rôle des vues (migration 0026, tâche 15.1)
VUE_INTERNE_T3 = "v_t3_withheld"                        # vue interne de la relation T3 (masking-sums D17, migration 0030) : aucun rôle n'y a de droit
VUE_FLUX = {"v_team_flow_inout"}                          # créés et finis par équipe et trimestre clos, rôle des vues (migration 0031, mothra-slices 36.1)
VUE_COUVERTURE = {"v_team_delivery_fields_coverage"}      # couverture des champs de livraison, rôle des vues (migration 0033, jira-delivery-fields, R-20261102-16 à -36)
VUES_DU_SCHEMA = VUES | VUES_NOMS | {VUE_EQUIPES_VUES, VUE_PART_VERSIONS} | VUES_PHOTO | VUES_TRANCHE_1 | {VUE_INTERNE_T3} | VUE_FLUX | VUE_COUVERTURE


class SchemaFlow(unittest.TestCase):
    def setUp(self):
        if not base.BASE_DISPONIBLE:
            self.skipTest(base.MESSAGE_SAUT)
        self.nom_base = "pmzilla_test_" + secrets.token_hex(6)
        self.admin = db.connect(base.URL_BASE, password=base.MOT_DE_PASSE, autocommit=True)
        self.addCleanup(self._supprimer)
        self.admin.execute(f'CREATE DATABASE "{self.nom_base}"')
        self.url = base.url_vers(self.nom_base)
        self.ouvertes = []
        c = self.conn()
        db.migrer(c, db.lister_migrations(db.DOSSIER_MIGRATIONS))
        c.commit()

    def _supprimer(self):
        for c in self.ouvertes:
            with contextlib.suppress(Exception):
                c.close()
        with contextlib.suppress(Exception):
            self.admin.execute(f'DROP DATABASE IF EXISTS "{self.nom_base}" WITH (FORCE)')
        self.admin.close()

    def conn(self):
        c = db.connect(self.url, password=base.MOT_DE_PASSE)
        self.ouvertes.append(c)
        return c

    def jeu(self, c):
        """Dix tickets de l'équipe Alpha (assez pour franchir le masquage), deux de l'équipe Beta (masqués)."""
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.teams (name) VALUES ('Alpha'), ('Beta')")
        for i in range(10):
            c.execute("INSERT INTO flow.issues (key, project, type, status, status_category, created_at, resolved_at, updated_at, team_id) "
                      "VALUES (%s, 'PROJ', 'Story', 'Closed', 'Done', now() - interval '40 days', now() - interval '3 days', now(), 1)",
                      (f"PROJ-{i}",))
        for i in range(10, 12):
            c.execute("INSERT INTO flow.issues (key, project, type, status, status_category, created_at, updated_at, team_id) "
                      "VALUES (%s, 'PROJ', 'Story', 'Open', 'To Do', now() - interval '2 days', now(), 2)", (f"PROJ-{i}",))
        c.execute("INSERT INTO flow.links (source_key, target_key, link_type, direction) VALUES ('PROJ-10', 'PROJ-0', 'Blocks', 'outward')")
        c.execute("RESET ROLE")
        c.commit()

    def test_tables_vues_et_colonnes(self):
        c = self.conn()
        noms = {r[0] for r in c.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                                        "WHERE n.nspname = 'flow' AND c.relkind = 'r'")}
        self.assertEqual(TABLES, noms)                    # les sept tables et les trois de la couche brute, pas une de plus
        vues = {r[0] for r in c.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                                        "WHERE n.nspname = 'flow' AND c.relkind = 'v'")}
        self.assertEqual(vues, VUES_DU_SCHEMA)            # les quatre vues agrégées plus celle des équipes vues
        colonnes = {r[0].lower() for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'flow'")}
        self.assertEqual(colonnes & INTERDITES, set())
        issues = {r[0] for r in c.execute("SELECT column_name FROM information_schema.columns "
                                          "WHERE table_schema = 'flow' AND table_name = 'issues'")}
        self.assertLessEqual({"key", "project", "type", "status", "status_category", "created_at", "resolved_at", "resolution",
                              "status_category_changed_at", "story_points", "updated_at", "team_id", "parent_key",
                              "has_history", "out_of_export_at"}, issues)

    def test_aucune_colonne_po_ni_personnelle_et_etiquette_dans_une_seule_table(self):
        c = self.conn()
        lignes = c.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'flow'").fetchall()
        for table, colonne in lignes:
            nom = colonne.lower()
            self.assertNotIn(nom, INTERDITES, f"{table}.{colonne}")
            self.assertFalse(set(nom.split("_")) & {"po", "owner", "person", "assignee", "reporter", "creator", "author", "email", "account"},
                             f"{table}.{colonne} : colonne PO ou personnelle")
        avec_etiquette = {t for t, col in lignes if "label" in col.lower()}
        self.assertEqual(avec_etiquette, {TABLE_ETIQUETTES, TABLE_ETIQUETTES_REFERENTIEL})
        for table in (TABLE_ETIQUETTES, TABLE_VERSIONS):
            colonnes = {col for t, col in lignes if t == table}
            self.assertLessEqual({"issue_key", "added_at", "removed_at"}, colonnes, table)

    def test_instant_sorti_de_l_export_nullable(self):
        c = self.conn()
        ligne = c.execute("SELECT data_type, is_nullable FROM information_schema.columns "
                          "WHERE table_schema = 'flow' AND table_name = 'issues' AND column_name = 'out_of_export_at'").fetchone()
        self.assertIsNotNone(ligne, "colonne flow.issues.out_of_export_at absente")
        self.assertEqual(ligne, ("timestamp with time zone", "YES"))
        self.jeu(c)
        c.execute("SET ROLE pmzilla_flow")
        self.assertIsNone(c.execute("SELECT out_of_export_at FROM flow.issues WHERE key = 'PROJ-0'").fetchone()[0])
        c.execute("RESET ROLE")

    def test_drapeau_d_historique_inchange(self):
        c = self.conn()
        ligne = c.execute("SELECT data_type, is_nullable, column_default FROM information_schema.columns "
                          "WHERE table_schema = 'flow' AND table_name = 'issues' AND column_name = 'has_history'").fetchone()
        self.assertEqual(ligne, ("boolean", "NO", "false"))
        self.jeu(c)
        c.execute("SET ROLE pmzilla_flow")
        self.assertEqual(c.execute("SELECT has_history FROM flow.issues WHERE key = 'PROJ-0'").fetchone(), (False,))
        c.execute("UPDATE flow.issues SET has_history = true WHERE key = 'PROJ-0'")
        self.assertEqual(c.execute("SELECT has_history FROM flow.issues WHERE key = 'PROJ-0'").fetchone(), (True,))
        with self.assertRaises(db.psycopg.errors.NotNullViolation):
            with c.transaction():
                c.execute("UPDATE flow.issues SET has_history = NULL WHERE key = 'PROJ-0'")
        c.execute("RESET ROLE")

    def test_suppression_en_cascade_d_une_issue_et_de_ses_dependances(self):
        c = self.conn()
        self.jeu(c)
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.issue_teams (issue_key, team_id, position) VALUES ('PROJ-0', 1, 1), ('PROJ-0', 2, 2)")
        c.execute("INSERT INTO flow.transitions (issue_key, transitioned_at, from_status, to_status) VALUES ('PROJ-0', now(), NULL, 'Open')")
        c.execute(f"INSERT INTO flow.{TABLE_ETIQUETTES} (issue_key, label, added_at) VALUES ('PROJ-0', 'etiquette-a', now())")
        c.execute(f"INSERT INTO flow.{TABLE_VERSIONS} (issue_key, version, added_at) VALUES ('PROJ-0', 'version-a', now())")
        c.execute("INSERT INTO flow.links (source_key, target_key, link_type, direction) VALUES ('PROJ-0', 'PROJ-1', 'Relates', 'outward')")
        c.execute("DELETE FROM flow.issues WHERE key = 'PROJ-0'")
        for table, colonne in (("issue_teams", "issue_key"), ("transitions", "issue_key"), (TABLE_ETIQUETTES, "issue_key"),
                               (TABLE_VERSIONS, "issue_key"), ("links", "source_key")):
            self.assertEqual(c.execute(f"SELECT count(*) FROM flow.{table} WHERE {colonne} = 'PROJ-0'").fetchone()[0], 0, table)
        self.assertEqual(c.execute("SELECT count(*) FROM flow.issues WHERE key = 'PROJ-1'").fetchone()[0], 1)
        c.execute("RESET ROLE")

    def test_les_vues_ne_montrent_aucune_cle(self):
        c = self.conn()
        for vue in VUES_DU_SCHEMA:
            colonnes = {r[0] for r in c.execute("SELECT column_name FROM information_schema.columns "
                                                "WHERE table_schema = 'flow' AND table_name = %s", (vue,))}
            self.assertFalse({c_ for c_ in colonnes if "key" in c_}, f"{vue} : {colonnes}")

    def test_contraintes_et_doublons(self):
        c = self.conn()
        self.jeu(c)
        c.execute("SET ROLE pmzilla_flow")
        c.execute("INSERT INTO flow.transitions (issue_key, transitioned_at, from_status, to_status) "
                  "VALUES ('PROJ-0', '2026-03-01T09:00:00+02:00', NULL, 'Open')")
        with self.assertRaises(db.psycopg.errors.UniqueViolation):
            with c.transaction():
                c.execute("INSERT INTO flow.transitions (issue_key, transitioned_at, from_status, to_status) "
                          "VALUES ('PROJ-0', '2026-03-01T07:00:00+00:00', NULL, 'Open')")      # même instant, autre fuseau
        with self.assertRaises(db.psycopg.errors.UniqueViolation):
            with c.transaction():
                c.execute("INSERT INTO flow.links (source_key, target_key, link_type, direction) "
                          "VALUES ('PROJ-10', 'PROJ-0', 'Blocks', 'outward')")
        with self.assertRaises(db.psycopg.errors.CheckViolation):
            with c.transaction():
                c.execute("INSERT INTO flow.links (source_key, target_key, link_type, direction) "
                          "VALUES ('PROJ-10', 'PROJ-1', 'Blocks', 'sideways')")
        with self.assertRaises(db.psycopg.errors.ForeignKeyViolation):
            with c.transaction():
                c.execute("INSERT INTO flow.transitions (issue_key, transitioned_at, to_status) VALUES ('NOPE-1', now(), 'Open')")

    def essaie(self, c, role, sql):
        try:
            with c.transaction():
                c.execute(f"SET LOCAL ROLE {role}")
                c.execute(sql)
                return c.execute("SELECT 1").fetchone() is not None
        except db.psycopg.errors.InsufficientPrivilege:
            return False

    def test_droits_des_roles_sur_flow(self):
        c = self.conn()
        self.jeu(c)
        self.assertTrue(self.essaie(c, "pmzilla_flow", "SELECT * FROM flow.issues"))
        self.assertTrue(self.essaie(c, "pmzilla_flow_ro", "SELECT * FROM flow.issues"))
        self.assertFalse(self.essaie(c, "pmzilla_flow_ro", "DELETE FROM flow.issues"))
        self.assertFalse(self.essaie(c, "pmzilla_cases", "SELECT * FROM flow.issues"))
        self.assertFalse(self.essaie(c, "pmzilla_knowledge_ro", "SELECT * FROM flow.links"))

    def test_le_role_des_vues_ne_lit_que_les_vues(self):
        c = self.conn()
        self.jeu(c)
        for vue in VUES | VUES_NOMS | {VUE_PART_VERSIONS} | VUES_PHOTO | VUES_TRANCHE_1 | VUE_COUVERTURE:
            self.assertTrue(self.essaie(c, "pmzilla_flow_views", f"SELECT * FROM flow.{vue}"), vue)
        for table in TABLES:
            self.assertFalse(self.essaie(c, "pmzilla_flow_views", f"SELECT * FROM flow.{table}"), table)
        self.assertFalse(self.essaie(c, "pmzilla_flow_views", f"SELECT * FROM flow.{VUE_EQUIPES_VUES}"))      # réservée au rôle en lecture seule
        self.assertFalse(self.essaie(c, "pmzilla_flow_views", "INSERT INTO flow.teams (name) VALUES ('X')"))
        self.assertFalse(self.essaie(c, "pmzilla_flow_views", "SELECT * FROM cases.experiments"))
        self.assertFalse(self.essaie(c, "pmzilla_flow_views", "SELECT * FROM knowledge.books"))
        self.assertFalse(self.essaie(c, "pmzilla_flow_views", "CREATE TABLE flow.interdit (id int)"))

    def test_masquage_des_cellules_de_moins_de_cinq(self):
        c = self.conn()
        self.jeu(c)
        c.execute("SET ROLE pmzilla_flow_views")
        lignes = {(r[0], r[1]): r[2] for r in c.execute("SELECT team, status_category, tickets FROM flow.v_team_status")}
        self.assertEqual(lignes[("Alpha", "Done")], 10)
        self.assertIsNone(lignes[("Beta", "To Do")])             # 2 tickets : masqué
        liens = c.execute("SELECT links FROM flow.v_team_dependencies").fetchall()
        self.assertEqual(liens, [(None,)])                        # un seul lien : masqué
        semaine = c.execute("SELECT tickets FROM flow.v_team_weekly_resolved").fetchall()
        self.assertEqual(sorted(x[0] for x in semaine if x[0] is not None), [10])
        c.execute("RESET ROLE")

    def test_connexion_sous_un_role_limite_avec_son_propre_mot_de_passe(self):
        role = "pmzilla_test_" + secrets.token_hex(4)
        secret = "MotDePasseDeTest-" + secrets.token_hex(6)
        def retirer():          # la base d'abord (elle porte les droits du rôle), puis le rôle
            self._supprimer()
            with db.connect(base.URL_BASE, password=base.MOT_DE_PASSE, autocommit=True) as nettoyage:
                nettoyage.execute(f'DROP ROLE IF EXISTS "{role}"')
        self.addCleanup(retirer)
        self.admin.execute(f'CREATE ROLE "{role}" NOLOGIN')
        self.admin.execute(f'GRANT CONNECT ON DATABASE "{self.nom_base}" TO "{role}"')
        c = self.conn()
        with self.assertRaises(db.ErreurBase):                    # un rôle hors liste est refusé
            db.definir_mot_de_passe(c, role, secret)
        with self.assertRaises(db.ErreurBase):
            db.definir_mot_de_passe(c, role, "court", autorises=(role,))
        db.definir_mot_de_passe(c, role, secret, autorises=(role,))
        with unittest.mock.patch.object(db, "ROLES_AVEC_MOT_DE_PASSE", (role,)):
            limite = db.connect(self.url, password=secret, role=role)
            self.ouvertes.append(limite)
            self.assertEqual(limite.execute("SELECT current_user").fetchone()[0], role)
            with self.assertRaises(db.ErreurBase) as cm:
                db.connect(self.url, password="mauvais", role=role)
            self.assertNotIn(secret, str(cm.exception))
        with self.assertRaises(db.ErreurBase):                    # rôle non listé : refus avant toute connexion
            db.connect(self.url, password=secret, role=role)

    def test_le_role_des_vues_existe_apres_migration(self):
        """Son attribut de connexion n'est pas vérifié ici : le rôle est partagé par l'instance et role-password le rend LOGIN. Que la
        migration ne le crée qu'en NOLOGIN est vérifié sans base (test_db.py, test_aucune_migration_ne_cree_de_role_avec_connexion…)."""
        c = self.conn()
        self.assertEqual(c.execute("SELECT count(*) FROM pg_roles WHERE rolname = 'pmzilla_flow_views'").fetchone()[0], 1)


class SansBase(unittest.TestCase):
    def test_migration_0002_presente_et_sans_donnee(self):
        noms = [m.nom for m in db.lister_migrations()]
        self.assertIn("0002_flow_schema.sql", noms)
        texte = (db.DOSSIER_MIGRATIONS / "0002_flow_schema.sql").read_text(encoding="utf-8")
        self.assertNotRegex(texte, r"(?im)^\s*INSERT\s+INTO")          # une migration ne contient aucune donnée
        self.assertNotRegex(texte, r"(?i)password\s+'")                  # ni mot de passe posé

    def test_role_password_n_accepte_que_les_roles_de_lecture_limitee(self):
        self.assertEqual(db.ROLES_AVEC_MOT_DE_PASSE,
                         ("pmzilla_flow_views", "pmzilla_knowledge_ro", "pmzilla_cases_ro", "pmzilla_cases", "pmzilla_flow",
                          "pmzilla_quality_views", "pmzilla_mothra",
                          "pmzilla_mothra_views"))     # + pmzilla_mothra : tâche 16.1, ADR 0006 accepté le 2026-10-27 ; + pmzilla_mothra_views : R-20261107-26 décision 3 (a), A-80
        self.assertEqual(db.service_du_role("pmzilla_cases_ro"), "pmzilla-lab-db-pmzilla_cases_ro")
        self.assertEqual(db.variable_du_role("pmzilla_cases_ro"), "PMZILLA_LAB_DB_PASSWORD_PMZILLA_CASES_RO")
        self.assertEqual(db.service_du_role("pmzilla_cases"), "pmzilla-lab-db-pmzilla_cases")
        self.assertEqual(db.variable_du_role("pmzilla_cases"), "PMZILLA_LAB_DB_PASSWORD_PMZILLA_CASES")
        self.assertNotEqual(db.service_du_role("pmzilla_cases"), db.service_du_role("pmzilla_cases_ro"))
        self.assertNotEqual(db.variable_du_role("pmzilla_cases"), db.variable_du_role("pmzilla_cases_ro"))
        self.assertEqual(db.service_du_role("pmzilla_knowledge_ro"), "pmzilla-lab-db-pmzilla_knowledge_ro")
        self.assertEqual(db.variable_du_role("pmzilla_knowledge_ro"), "PMZILLA_LAB_DB_PASSWORD_PMZILLA_KNOWLEDGE_RO")
        self.assertEqual(db.service_du_role("pmzilla_flow_views"), "pmzilla-lab-db-pmzilla_flow_views")
        self.assertEqual(db.variable_du_role("pmzilla_flow_views"), "PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW_VIEWS")
        with self.assertRaises(db.ErreurBase):
            db.connect("postgresql://postgres@127.0.0.1/x", password="x", role="postgres")


if __name__ == "__main__":
    unittest.main()
