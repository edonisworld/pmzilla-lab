"""Couche brute datée du schéma flow (change jira-data-architecture, D2, D3, D13 ; spec database-roles-views « Raw layer tables in
the flow schema » et « Limited roles log in with their own password, never the superuser's »). Tâche 4.4 (rouge d'abord).

    uv run --with "psycopg[binary]" python -m unittest discover -s tests/db -v

Les tests sans base (classe SansBase) tournent toujours : lecture du fichier de migration et dérivation des noms du Trousseau.
Les autres utilisent la base jetable de test_flow_schema.py (même fixture) et sont sautés sans elle (bash tools/dbtest.sh db).
La migration est retrouvée par sa description (flow_raw_layer), pas par son numéro : celui-ci change quand une autre migration
fusionne avant elle. Données inventées : tickets PROJ-n, équipes Alpha et Beta.
"""
import re
import unittest

import test_db as base          # noqa: E402,F401
from test_db import db          # noqa: E402
import test_flow_schema as fs   # noqa: E402

TABLES_BRUTES = ("raw_runs", "raw_run_sightings", "raw_issue_snapshots")       # l'ordre des dépendances
NOMS_INTERDITS = {"title", "summary", "description", "assignee", "reporter", "creator", "author", "comment", "comments",
                  "po", "person", "person_name", "name_of_person"}
ROLE_IMPORT = "pmzilla_flow"


def fichier_migration():
    candidats = [m for m in db.lister_migrations() if m.nom.endswith("_flow_raw_layer.sql")]
    return candidats[0] if len(candidats) == 1 else None


class SansBase(unittest.TestCase):
    def test_migration_presente_sans_donnee_ni_mot_de_passe_ni_role(self):
        migration = fichier_migration()
        self.assertIsNotNone(migration, "une migration *_flow_raw_layer.sql est attendue")
        texte = migration.chemin.read_text(encoding="utf-8")
        self.assertRegex(texte.splitlines()[0], r"^-- Schéma touché : flow")
        sans_commentaires = re.sub(r"--[^\n]*", "", texte)
        self.assertNotRegex(sans_commentaires, r"(?im)^\s*INSERT\s+INTO")           # aucune donnée
        self.assertNotRegex(sans_commentaires, r"(?i)\bPASSWORD\b")                  # aucun mot de passe
        self.assertNotRegex(sans_commentaires, r"(?i)\b(CREATE|ALTER|DROP)\s+ROLE\b")        # aucun rôle créé, changé ni retiré
        self.assertNotRegex(sans_commentaires, r"(?i)\bLOGIN\b")

    def test_migration_cree_les_trois_tables_et_ne_les_donne_qu_au_role_d_import(self):
        texte = fichier_migration().chemin.read_text(encoding="utf-8")
        for table in TABLES_BRUTES:
            self.assertIn(f"flow.{table}", texte)
        self.assertRegex(texte, r"(?is)GRANT\s+SELECT,\s*INSERT,\s*DELETE\s+ON\s+[^;]*TO\s+pmzilla_flow\s*;")
        self.assertRegex(texte, r"(?is)REVOKE\s+ALL\s+ON\s+[^;]*FROM\s+[^;]*pmzilla_flow_ro")
        self.assertNotRegex(texte, r"(?is)GRANT[^;]*(pmzilla_flow_ro|pmzilla_flow_views)")

    def test_le_role_d_import_peut_avoir_un_mot_de_passe_avec_son_propre_trousseau(self):
        self.assertIn(ROLE_IMPORT, db.ROLES_AVEC_MOT_DE_PASSE)
        self.assertEqual(db.service_du_role(ROLE_IMPORT), "pmzilla-lab-db-pmzilla_flow")
        self.assertEqual(db.variable_du_role(ROLE_IMPORT), "PMZILLA_LAB_DB_PASSWORD_PMZILLA_FLOW")
        self.assertNotEqual(db.service_du_role(ROLE_IMPORT), db.service_du_role(None))
        self.assertNotEqual(db.variable_du_role(ROLE_IMPORT), db.variable_du_role(None))
        for autre in db.ROLES_AVEC_MOT_DE_PASSE:
            if autre != ROLE_IMPORT:
                self.assertNotEqual(db.service_du_role(ROLE_IMPORT), db.service_du_role(autre))
                self.assertNotEqual(db.variable_du_role(ROLE_IMPORT), db.variable_du_role(autre))

    def test_les_roles_d_ecriture_de_la_bibliotheque_et_le_proprietaire_restent_refuses(self):
        for role in ("pmzilla_knowledge", "pmzilla_owner", "postgres", "pmzilla_flow_ro"):
            self.assertNotIn(role, db.ROLES_AVEC_MOT_DE_PASSE)
            with self.assertRaises(db.ErreurBase):          # refusé avant toute connexion
                db.connect("postgresql://postgres@127.0.0.1/x", password="x", role=role)
            with self.assertRaises(db.ErreurBase):
                db.definir_mot_de_passe(None, role, "MotDePasseInvente-12")


class SchemaBrut(unittest.TestCase):
    """Même base jetable que SchemaFlow (migrations appliquées, base supprimée à la fin)."""
    setUp = fs.SchemaFlow.setUp
    _supprimer = fs.SchemaFlow._supprimer
    conn = fs.SchemaFlow.conn
    essaie = fs.SchemaFlow.essaie

    def inserer_passage(self, c, genre="export"):
        return c.execute("INSERT INTO flow.raw_runs (kind, queries_searched, all_queries) VALUES (%s, 2, true) RETURNING id",
                         (genre,)).fetchone()[0]

    def test_les_trois_tables_existent_et_sont_vides(self):
        c = self.conn()
        for table in TABLES_BRUTES:
            self.assertEqual(c.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'flow' "
                                       "AND table_name = %s", (table,)).fetchone()[0], 1, table)
            self.assertEqual(c.execute(f"SELECT count(*) FROM flow.{table}").fetchone()[0], 0, table)

    def test_aucun_nom_de_colonne_interdit_et_aucune_colonne_d_etiquette(self):
        c = self.conn()
        colonnes = c.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'flow' "
                             "AND table_name = ANY(%s)", (list(TABLES_BRUTES),)).fetchall()
        self.assertTrue(colonnes)
        for table, colonne in colonnes:
            self.assertNotIn(colonne.lower(), NOMS_INTERDITS, (table, colonne))
            self.assertNotIn("label", colonne.lower(), (table, colonne))
            self.assertNotIn("version", colonne.lower(), (table, colonne))
        etiquettes = c.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'flow' "
                               "AND column_name ILIKE '%label%'").fetchall()
        self.assertEqual({t for t, _ in etiquettes}, {fs.TABLE_ETIQUETTES})            # seule table des périodes déclarées

    def test_genre_du_passage_contraint(self):
        c = self.conn()
        c.execute(f"SET ROLE {ROLE_IMPORT}")
        for genre in ("export", "seed", "history"):
            self.inserer_passage(c, genre)
        with self.assertRaises(db.psycopg.errors.CheckViolation):
            with c.transaction():
                self.inserer_passage(c, "autre")
        c.execute("RESET ROLE")

    def test_le_role_d_import_insere_et_lit_mais_ne_modifie_pas(self):
        c = self.conn()
        c.execute(f"SET ROLE {ROLE_IMPORT}")
        passage = self.inserer_passage(c)
        c.execute("INSERT INTO flow.raw_run_sightings (run_id, issue_key) VALUES (%s, 'PROJ-1')", (passage,))
        c.execute("INSERT INTO flow.raw_issue_snapshots (issue_key, run_id, updated_at, project, type, status, created_at, "
                  "content_hash) VALUES ('PROJ-1', %s, now(), 'PROJ', 'Story', 'Open', now(), 'h')", (passage,))
        self.assertEqual(c.execute("SELECT count(*) FROM flow.raw_issue_snapshots").fetchone()[0], 1)
        for sql in ("UPDATE flow.raw_runs SET all_queries = false", "UPDATE flow.raw_run_sightings SET issue_key = 'PROJ-2'",
                    "UPDATE flow.raw_issue_snapshots SET status = 'Done'"):
            with self.assertRaises(db.psycopg.errors.InsufficientPrivilege):
                with c.transaction():
                    c.execute(sql)
        c.execute("RESET ROLE")

    def test_un_passage_et_un_ticket_n_ont_qu_un_instantane_et_une_visite(self):
        c = self.conn()
        c.execute(f"SET ROLE {ROLE_IMPORT}")
        passage = self.inserer_passage(c)
        c.execute("INSERT INTO flow.raw_run_sightings (run_id, issue_key) VALUES (%s, 'PROJ-1')", (passage,))
        with self.assertRaises(db.psycopg.errors.UniqueViolation):
            with c.transaction():
                c.execute("INSERT INTO flow.raw_run_sightings (run_id, issue_key) VALUES (%s, 'PROJ-1')", (passage,))
        with self.assertRaises(db.psycopg.errors.ForeignKeyViolation):
            with c.transaction():
                c.execute("INSERT INTO flow.raw_run_sightings (run_id, issue_key) VALUES (-1, 'PROJ-1')")
        c.execute("RESET ROLE")

    def test_equipes_et_liens_en_json_avec_identifiant_jira(self):
        c = self.conn()
        c.execute(f"SET ROLE {ROLE_IMPORT}")
        passage = self.inserer_passage(c)
        c.execute("INSERT INTO flow.raw_issue_snapshots (issue_key, run_id, updated_at, project, type, status, created_at, "
                  "content_hash, teams, links) VALUES ('PROJ-1', %s, now(), 'PROJ', 'Story', 'Open', now(), 'h', "
                  "%s::jsonb, NULL)", (passage, '[{"name": "Alpha", "jira_team_id": "11"}, {"name": "Beta", "jira_team_id": null}]'))
        equipes, liens = c.execute("SELECT teams, links FROM flow.raw_issue_snapshots").fetchone()
        self.assertEqual([e["jira_team_id"] for e in equipes], ["11", None])
        self.assertIsNone(liens)                              # « non suivis »
        with self.assertRaises(db.psycopg.errors.CheckViolation):
            with c.transaction():
                c.execute("INSERT INTO flow.raw_issue_snapshots (issue_key, run_id, updated_at, project, type, status, created_at, "
                          "content_hash, teams) VALUES ('PROJ-2', %s, now(), 'PROJ', 'Story', 'Open', now(), 'h', '{}'::jsonb)",
                          (passage,))
        c.execute("RESET ROLE")

    def test_ni_le_role_en_lecture_seule_ni_le_role_des_vues_ne_les_lisent(self):
        c = self.conn()
        for role in ("pmzilla_flow_ro", "pmzilla_flow_views", "pmzilla_cases", "pmzilla_knowledge_ro"):
            for table in TABLES_BRUTES:
                self.assertFalse(self.essaie(c, role, f"SELECT * FROM flow.{table}"), (role, table))
        for table in TABLES_BRUTES:
            self.assertTrue(self.essaie(c, ROLE_IMPORT, f"SELECT * FROM flow.{table}"), table)

    def test_le_role_d_import_ne_lit_rien_hors_de_flow(self):
        c = self.conn()
        for table in ("cases.experiments", "knowledge.books"):
            self.assertFalse(self.essaie(c, ROLE_IMPORT, f"SELECT * FROM {table}"), table)
        self.assertFalse(self.essaie(c, ROLE_IMPORT, "CREATE TABLE public.interdit (id int)"))

    def test_les_quatre_vues_ne_lisent_pas_la_couche_brute(self):
        c = self.conn()
        for vue in fs.VUES:
            definition = c.execute("SELECT pg_get_viewdef(%s::regclass)", (f"flow.{vue}",)).fetchone()[0]
            self.assertNotIn("raw_", definition, vue)

    def test_le_mot_de_passe_du_role_d_import_est_accepte_par_le_poseur(self):
        """Le poseur accepte le rôle et le rend capable de se connecter ; un mot de passe trop court est refusé."""
        c = self.conn()
        with self.assertRaises(db.ErreurBase):
            db.definir_mot_de_passe(c, ROLE_IMPORT, "court")
        # Le rôle est partagé par l'instance (migration 0001) : on ne lui pose pas de mot de passe réel ici ; le poseur est exercé
        # avec un rôle jetable de la liste dans test_flow_schema (test_connexion_sous_un_role_limite_avec_son_propre_mot_de_passe).


if __name__ == "__main__":
    unittest.main()
