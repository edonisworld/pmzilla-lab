"""
Tests de la migration du schéma `mothra` (change mothra-slices, tâche 16.1, design D17, D21, D26, D31 ; ADR 0006 ; spec database-roles-views,
exigences « The mothra schema holds Mothra's own storage without secret or name » et « The Mothra storage role writes only in its schema »).

    bash tools/dbtest.sh db        (passe de l'auteur : les modules de tests/db ne sont pas lancés par une session)

Les tests sans base (classe SansBase) tournent toujours : lecture du fichier de migration et du setter de mots de passe. Les autres
utilisent une base jetable pmzilla_test_<hex> et sont sautés sans base disponible (DBTEST_PORT). Données inventées : identifiants
pseudonymes u1 et u2, aucune donnée réelle.
"""
import contextlib
import re
import secrets
import unittest

import test_db as base          # noqa: E402
from test_db import db          # noqa: E402

try:
    import psycopg
    from psycopg import errors
except ImportError:             # pragma: no cover : psycopg est toujours fourni par le lanceur
    psycopg = None

ROLE = "pmzilla_mothra"
TABLES = {"users", "sheets", "published_versions", "threshold_history"}
TABLES_FIGEES = ("published_versions", "threshold_history")
COLONNES_INTERDITES = re.compile(r"(?i)(^|_)(name|names|e_?mail|mail|password|passwd|secret|key|title|description|attendees|attendee|"
                                 r"assignee|reporter|person)($|_)")
SCHEMAS_HORS_MOTHRA = ("flow", "quality", "cases", "knowledge")
AUTRES_ROLES_REFUSES = ("pmzilla_flow_views", "pmzilla_quality_views", "pmzilla_flow")
EMPREINTE = "a" * 64


def migration_mothra():
    candidates = [m for m in db.lister_migrations() if re.fullmatch(r"\d{4}_mothra_schema\.sql", m.nom)]
    return candidates[0] if len(candidates) == 1 else None


class SansBase(unittest.TestCase):
    def texte(self):
        migration = migration_mothra()
        self.assertIsNotNone(migration, "une seule migration 'mothra_schema' attendue")
        return migration.chemin.read_text(encoding="utf-8")

    def sans_commentaires(self):
        return "\n".join(ligne.split("--", 1)[0] for ligne in self.texte().splitlines())

    def test_numero_libre_suite_continue_et_premiere_ligne(self):
        migrations = db.lister_migrations()
        migration = migration_mothra()
        self.assertGreaterEqual(migration.numero, 23)                              # le prochain numéro libre de main à la création (0022 était le dernier)
        self.assertEqual([m.numero for m in migrations], list(range(1, len(migrations) + 1)))
        self.assertRegex(self.texte().splitlines()[0], r"^-- Schéma touché : mothra")

    def test_aucune_donnee_aucun_mot_de_passe_aucune_connexion(self):
        code = self.sans_commentaires()
        self.assertNotRegex(code, r"(?im)^\s*INSERT\s+INTO")
        self.assertNotRegex(code.upper(), r"PASSWORD|ALTER\s+ROLE|DROP\s+ROLE")
        self.assertNotRegex(code, r"(?<!NO)LOGIN")
        creation = re.search(r"CREATE ROLE pmzilla_mothra[^;]*;", code)
        self.assertIsNotNone(creation)
        self.assertIn("NOLOGIN", creation.group(0))

    def test_le_schema_appartient_au_proprietaire_et_se_ferme_au_public(self):
        code = self.sans_commentaires()
        self.assertRegex(code, r"CREATE SCHEMA IF NOT EXISTS mothra AUTHORIZATION pmzilla_owner")
        self.assertRegex(code, r"REVOKE ALL ON SCHEMA mothra FROM PUBLIC")
        self.assertRegex(code, r"GRANT USAGE ON SCHEMA mothra TO pmzilla_mothra\s*;")

    def test_les_colonnes_ne_portent_ni_secret_ni_nom(self):
        code = self.sans_commentaires()
        colonnes = []
        for corps in re.findall(r"CREATE TABLE mothra\.(\w+) \((.*?)\n\);", code, flags=re.S):
            self.assertIn(corps[0], TABLES)
            for ligne in corps[1].splitlines():
                trouve = re.match(r"\s+(\w+)\s+\w+", ligne)
                if trouve and trouve.group(1).upper() not in {"CHECK", "UNIQUE", "PRIMARY", "FOREIGN", "CONSTRAINT"}:
                    colonnes.append((corps[0], trouve.group(1)))
        self.assertTrue(colonnes)
        for table, colonne in colonnes:
            self.assertIsNone(COLONNES_INTERDITES.search(colonne), f"{table}.{colonne}")
        historique = {c for t, c in colonnes if t == "threshold_history"}
        self.assertEqual(historique, {"id", "threshold_code", "value", "set_on", "set_by"})      # valeur, date, auteur : pas de participants

    def test_les_droits_accordes_sont_ceux_de_l_adr_0006(self):
        code = " ".join(self.sans_commentaires().split())
        accordes = dict(re.findall(r"GRANT ([A-Z, ]+) ON ([\w., ]+) TO pmzilla_mothra ;", code.replace(";", " ;")))
        par_table = {}
        for droits, tables in accordes.items():
            if droits == "USAGE":                                        # le droit d'usage du schéma, vérifié à part
                continue
            for table in tables.split(","):
                par_table[table.strip().removeprefix("mothra.")] = set(d.strip() for d in droits.split(","))
        self.assertEqual(par_table["published_versions"], {"SELECT", "INSERT"})
        self.assertEqual(par_table["threshold_history"], {"SELECT", "INSERT"})
        self.assertEqual(par_table["sheets"], {"SELECT", "INSERT", "UPDATE"})
        self.assertEqual(par_table["users"], {"SELECT", "INSERT", "UPDATE", "DELETE"})
        self.assertEqual(set(par_table), TABLES)
        self.assertNotRegex(code, r"(?i)GRANT[^;]*\b(CREATE|ALL)\b")
        self.assertNotRegex(code, r"(?i)GRANT[^;]*TO[^;]*(pmzilla_flow|pmzilla_quality|pmzilla_cases|pmzilla_knowledge|PUBLIC)")

    def test_les_tables_figees_n_ont_aucune_cle_etrangere_vers_users(self):
        code = self.sans_commentaires()
        self.assertNotRegex(code, r"REFERENCES mothra\.users")

    def test_le_role_du_stockage_est_dans_la_liste_fermee_du_setter_avec_son_propre_secret(self):
        self.assertIn(ROLE, db.ROLES_AVEC_MOT_DE_PASSE)
        self.assertEqual(db.service_du_role(ROLE), "pmzilla-lab-db-pmzilla_mothra")
        self.assertEqual(db.variable_du_role(ROLE), "PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA")
        for autre in db.ROLES_AVEC_MOT_DE_PASSE:
            if autre != ROLE:
                self.assertNotEqual(db.service_du_role(ROLE), db.service_du_role(autre))
                self.assertNotEqual(db.variable_du_role(ROLE), db.variable_du_role(autre))
        self.assertNotEqual(db.service_du_role(ROLE), db.SERVICE_TROUSSEAU)

    def test_la_liste_fermee_reste_fermee_pour_les_roles_d_ecriture_et_le_proprietaire(self):
        for refuse in ("pmzilla_owner", "pmzilla_knowledge", "pmzilla_quality", "postgres", "pmzilla_mothra_ro"):
            self.assertNotIn(refuse, db.ROLES_AVEC_MOT_DE_PASSE)
            with self.assertRaises(db.ErreurBase):
                db.definir_mot_de_passe(None, refuse, "MotDePasseInvente-12")


class BaseJetable(unittest.TestCase):
    """Base jetable migrée (toutes les migrations du dépôt), supprimée à la fin."""

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

    def execute(self, c, role, sql, params=None):
        """Exécute sous le rôle, dans sa propre transaction : le rôle est posé en local à chaque tentative (un refus défait la
        transaction, donc le SET ROLE : modèle de tests/db/test_quality_schema.py)."""
        with c.transaction():
            c.execute(f"SET LOCAL ROLE {role}")
            return c.execute(sql, params)

    def refuse(self, c, role, sql, params=None):
        """La requête est refusée pour privilège insuffisant."""
        with self.assertRaises(errors.InsufficientPrivilege, msg=sql):
            self.execute(c, role, sql, params)

    def prepare(self):
        """Une ligne par table, posée sous le propriétaire (le jeu d'essai n'est pas écrit par le rôle testé)."""
        c = self.conn()
        c.execute("SET ROLE pmzilla_owner")
        c.execute("INSERT INTO mothra.users (id, role) VALUES ('u1', 'author'), ('u2', 'reviewer')")
        c.execute("INSERT INTO mothra.sheets (kind, created_by) VALUES ('h5', 'u1')")
        c.execute("INSERT INTO mothra.published_versions (sheet_id, version, content, fingerprint, published_by) "
                  "VALUES (1, 1, '{}', %s, 'u1')", (EMPREINTE,))
        c.execute("INSERT INTO mothra.threshold_history (threshold_code, value, set_on, set_by) VALUES ('t1', 1.5, '2026-10-28', 'u1')")
        c.commit()


class DroitsDuStockage(BaseJetable):
    def test_matrice_des_droits_du_role_de_stockage(self):
        self.prepare()
        c = self.conn()
        for table in TABLES:
            self.execute(c, ROLE, f"SELECT count(*) FROM mothra.{table}")           # select accepté sur chaque table, users comprise (S3)
        # insertion seule sur les tables figées
        self.execute(c, ROLE, "INSERT INTO mothra.published_versions (sheet_id, version, content, fingerprint, published_by) "
                              "VALUES (1, 2, '{}', %s, 'u1')", (EMPREINTE,))
        self.execute(c, ROLE, "INSERT INTO mothra.threshold_history (threshold_code, value, set_on, set_by) VALUES ('t1', 2, '2026-10-29', 'u1')")
        for table, colonne in (("published_versions", "published_by"), ("threshold_history", "set_by")):
            self.refuse(c, ROLE, f"UPDATE mothra.{table} SET {colonne} = {colonne}")       # colonne ordinaire : pas une colonne d'identité
            self.refuse(c, ROLE, f"DELETE FROM mothra.{table}")
        # sheets : select, insert, update, pas de delete
        self.execute(c, ROLE, "INSERT INTO mothra.sheets (kind, created_by) VALUES ('h1', 'u1')")
        self.execute(c, ROLE, "UPDATE mothra.sheets SET state = 'reviewed', reviewed_by = 'u2' WHERE id = 1")
        self.refuse(c, ROLE, "DELETE FROM mothra.sheets")
        # users : delete accepté (purge), seul endroit
        self.execute(c, ROLE, "DELETE FROM mothra.users WHERE id = 'u2'")
        self.assertEqual(self.execute(c, ROLE, "SELECT count(*) FROM mothra.users").fetchone()[0], 1)

    def test_aucun_droit_hors_du_schema_mothra_et_aucun_ddl(self):
        c = self.conn()
        for schema, objet in (("flow", "issues"), ("flow", "v_team_status"), ("quality", "items"), ("quality", "quality_by_team"),
                              ("cases", "cases"), ("knowledge", "books")):
            self.refuse(c, ROLE, f"SELECT 1 FROM {schema}.{objet}")
        self.refuse(c, ROLE, "CREATE TABLE mothra.zz (a int)")
        self.refuse(c, ROLE, "CREATE TABLE public.zz (a int)")
        self.refuse(c, ROLE, "ALTER TABLE mothra.users ADD COLUMN zz int")
        self.refuse(c, ROLE, "DROP TABLE mothra.users")
        self.refuse(c, ROLE, "TRUNCATE mothra.users")

    def test_les_autres_roles_sont_refuses_sur_chaque_table_de_mothra(self):
        self.prepare()
        c = self.conn()
        for role in AUTRES_ROLES_REFUSES:
            for table in TABLES:
                self.refuse(c, role, f"SELECT 1 FROM mothra.{table}")
                self.refuse(c, role, f"INSERT INTO mothra.{table} DEFAULT VALUES")

    def test_seuls_le_proprietaire_et_le_role_de_stockage_ont_un_privilege_sur_mothra(self):
        c = self.conn()
        detenteurs = {r[0] for r in c.execute(
            "SELECT DISTINCT r.rolname FROM pg_roles r WHERE r.rolname LIKE 'pmzilla\\_%' AND "
            "(has_schema_privilege(r.oid, 'mothra', 'USAGE') OR has_schema_privilege(r.oid, 'mothra', 'CREATE') OR EXISTS ("
            "  SELECT 1 FROM pg_class t JOIN pg_namespace n ON n.oid = t.relnamespace WHERE n.nspname = 'mothra' AND t.relkind IN ('r', 'v', 'S') AND "
            "  (has_table_privilege(r.oid, t.oid, 'SELECT') OR has_table_privilege(r.oid, t.oid, 'INSERT'))))").fetchall()}
        self.assertEqual(detenteurs, {"pmzilla_owner", ROLE})
        self.assertIsNone(c.execute("SELECT 1 FROM pg_roles WHERE rolname = 'pmzilla_mothra_ro'").fetchone())      # aucun rôle de lecture seule
        self.assertFalse(c.execute("SELECT has_schema_privilege('public', 'mothra', 'USAGE')").fetchone()[0])

    def test_pas_de_connexion_avant_le_setter(self):
        # Les rôles sont ceux de TOUTE l'instance : un login posé sur ce rôle (par le setter, ou par les tests npm de la base jetable, qui le
        # retirent à leur fin) rend le cas sans objet ; il est alors sauté, non échoué.
        c = self.conn()
        peut = c.execute("SELECT rolcanlogin FROM pg_roles WHERE rolname = %s", (ROLE,)).fetchone()[0]
        if peut:
            self.skipTest("le rôle de stockage a déjà un login sur cette instance (setter ou test npm en cours)")
        with self.assertRaises(db.ErreurBase):
            db.connect(self.url, password="MotDePasseInvente-12", role=ROLE)

    def test_les_textes_libres_sont_bornes_et_ont_une_langue(self):
        c = self.conn()
        self.execute(c, ROLE, "INSERT INTO mothra.sheets (kind, created_by, effect_text, effect_lang) VALUES ('h5', 'u1', %s, 'fr')", ("x" * 500,))
        for sql in ("INSERT INTO mothra.sheets (kind, created_by, effect_text, effect_lang) VALUES ('h5', 'u1', %s, 'fr')",
                    "INSERT INTO mothra.sheets (kind, created_by, effect_text) VALUES ('h5', 'u1', %s)"):
            with self.assertRaises(errors.CheckViolation):
                self.execute(c, ROLE, sql, ("x" * 501 if "lang" in sql else "x",))
        with self.assertRaises(errors.CheckViolation):
            self.execute(c, ROLE, "INSERT INTO mothra.users (id, role) VALUES ('u3', 'admin')")


if __name__ == "__main__":
    unittest.main()
