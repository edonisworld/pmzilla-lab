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

INTERDITES = {"summary", "title", "description", "assignee", "reporter", "creator", "author", "labels", "comment", "name_of_person"}
TABLES = {"teams", "issues", "issue_teams", "transitions", "links"}
VUES = {"v_team_status", "v_team_weekly_resolved", "v_team_open_age", "v_team_dependencies"}


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
        self.assertLessEqual(TABLES, noms)
        vues = {r[0] for r in c.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                                        "WHERE n.nspname = 'flow' AND c.relkind = 'v'")}
        self.assertEqual(vues, VUES)
        colonnes = {r[0].lower() for r in c.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'flow'")}
        self.assertEqual(colonnes & INTERDITES, set())
        issues = {r[0] for r in c.execute("SELECT column_name FROM information_schema.columns "
                                          "WHERE table_schema = 'flow' AND table_name = 'issues'")}
        self.assertLessEqual({"key", "project", "type", "status", "status_category", "created_at", "resolved_at", "resolution",
                              "status_category_changed_at", "story_points", "updated_at", "team_id", "parent_key"}, issues)

    def test_les_vues_ne_montrent_aucune_cle(self):
        c = self.conn()
        for vue in VUES:
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
        for vue in VUES:
            self.assertTrue(self.essaie(c, "pmzilla_flow_views", f"SELECT * FROM flow.{vue}"), vue)
        for table in TABLES:
            self.assertFalse(self.essaie(c, "pmzilla_flow_views", f"SELECT * FROM flow.{table}"), table)
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
                         ("pmzilla_flow_views", "pmzilla_knowledge_ro", "pmzilla_cases_ro", "pmzilla_cases"))
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
