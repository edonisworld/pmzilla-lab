"""
Tests de la migration du schéma `quality` (change story-quality-audit, R-78, design D2, D8 et « Data model » ; spec database-roles-views,
exigences ajoutées). Aucune donnée dans la migration ; le contenu des stories vit seulement dans ce schéma.

    uv run --with "psycopg[binary]" python -m unittest discover -s tests/db -v

Les tests sans base (classe SansBase) tournent toujours : lecture du fichier de migration. Les autres utilisent une base jetable
pmzilla_test_<hex> (même fixture que test_flow_schema.py) et sont sautés quand aucune base n'est disponible (bash tools/dbtest.sh db).
Données inventées : clés PROJ-n, équipes Alpha et Beta, critères c1 et c2, aucun texte réel.

Tâche 3.27 (design D10, paragraphe du 2026-10-21) : la classe VerdictsSansTexteDeStory remplit une base jetable par l'outil réel `analyse`
et le faux serveur d'analyse de tests/story_quality/aide_analyse.py, avec des textes de story sentinelles que le faux moteur renvoie de
toutes les façons possibles ; aucune colonne d'une ligne de verdict ne doit en contenir un extrait. Sautée sans base jetable :
bash tools/dbtest.sh db story_quality
"""
import contextlib
import datetime as dt
import json
import re
import secrets
import sys
import unittest
from pathlib import Path

import test_db as base          # noqa: E402
from test_db import db          # noqa: E402

sys.path.append(str(Path(__file__).resolve().parents[1] / "story_quality"))     # aides du faux serveur d'analyse (après tests/db)
from aide_analyse import EspaceAnalyse                                          # noqa: E402
from aide_story_quality import EQUIPE_A, IDENTIFIANT_SURCOUCHE                  # noqa: E402
import story_quality_audit_store as audit_store                                 # noqa: E402
import story_quality_scrub as scrub                                             # noqa: E402
import story_quality_store as store                                             # noqa: E402

MIGRATION = "0010_quality_schema.sql"
TABLES = {"items", "item_teams", "team_attributes", "team_reviews", "contents", "assessments", "overlay_versions", "coaching_feedback"}
VUES = {"quality_by_team", "quality_coverage_by_team", "quality_by_product"}
MOTS_INTERDITS = {"assignee", "reporter", "creator", "author", "comment", "comments", "owner", "person", "user", "account", "email",
                  "e", "mail", "summary", "labels"}
# « po » n'est interdit que comme nom entier (comme dans le schéma flow) : le drapeau d'équipe `single_po` (D8) est la seule colonne qui le porte.
NOMS_INTERDITS = {"po", "name_of_person", "product_owner", "person_name", "user_name", "account_id", "e_mail"}
DRAPEAU_UN_SEUL_PO = "single_po"
TEXTE_LIBRE = {"title", "description", "acceptance_criteria", "feedback"}           # les seules colonnes de texte libre
TABLES_DE_TEXTE = {"contents", "coaching_feedback"}
COLONNES_TEXTE_IDENTIFIANTS = {                                                   # texte court : identifiants, codes, empreintes, jamais un texte de story
    "key", "kind", "parent_key", "status_category", "item_key", "team", "content_hash", "core_grid_id", "core_grid_version",
    "overlay_id", "overlay_version", "criterion_code", "origin", "link", "verdict",
    "version"}                                                                     # overlay_versions.version : numéro de version, comme overlay_version


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

    # --- jeu de données -------------------------------------------------------------------------------------------------
    def item(self, c, cle, equipes=("Alpha",), kind="story", acceptation="critère", sorti=False):
        """Une story et ses équipes, sous le rôle de lecture-écriture."""
        c.execute("SET ROLE pmzilla_quality")
        c.execute("INSERT INTO quality.items (key, kind, created_at, updated_at, out_of_collection_at) "
                  "VALUES (%s, %s, now() - interval '30 days', now(), CASE WHEN %s THEN now() ELSE NULL END)", (cle, kind, sorti))
        for position, equipe in enumerate(equipes, start=1):
            c.execute("INSERT INTO quality.item_teams (item_key, team, position) VALUES (%s, %s, %s)", (cle, equipe, position))
        c.execute("INSERT INTO quality.contents (item_key, title, description, acceptance_criteria, content_hash) "
                  "VALUES (%s, 'zztitre', 'zzdescription', %s, 'h')", (cle, acceptation))
        c.execute("RESET ROLE")

    def verdict(self, c, cle, code="c1", verdict="met", sample=False, coeur="1", surcouche=("", ""), origine="core", lien="refinement",
                instant="now()"):
        """Un verdict. `instant` est une expression SQL fixe du test, jamais une saisie."""
        c.execute("SET ROLE pmzilla_quality")
        c.execute("INSERT INTO quality.assessments (item_key, core_grid_id, core_grid_version, overlay_id, overlay_version, criterion_code, "
                  f"origin, link, verdict, sample, analysed_at) VALUES (%s, 'g', %s, %s, %s, %s, %s, %s, %s, %s, {instant})",
                  (cle, coeur, surcouche[0], surcouche[1], code, origine, lien, verdict, sample))
        c.execute("RESET ROLE")

    def lot(self, c, equipe, n, prefixe, verdicts=("met",), **options):
        """`n` stories de l'équipe, chacune avec un verdict c1 pris tour à tour dans `verdicts`."""
        for i in range(n):
            cle = f"{prefixe}-{i}"
            self.item(c, cle, (equipe,))
            self.verdict(c, cle, verdict=verdicts[i % len(verdicts)], **options)

    def lire(self, c, vue, role="pmzilla_quality_views", colonnes="*", ordre="1"):
        c.execute(f"SET ROLE {role}")
        try:
            return c.execute(f"SELECT {colonnes} FROM quality.{vue} ORDER BY {ordre}").fetchall()
        finally:
            c.execute("RESET ROLE")

    def colonnes_de(self, c, vue):
        c.execute("SET ROLE pmzilla_quality_views")
        try:
            return [d.name for d in c.execute(f"SELECT * FROM quality.{vue} LIMIT 0").description]
        finally:
            c.execute("RESET ROLE")

    def refuse(self, c, role, sql, params=()):
        """Vrai si la requête est refusée pour droits insuffisants (la transaction est annulée à sa place)."""
        try:
            with c.transaction():
                c.execute(f"SET LOCAL ROLE {role}")
                c.execute(sql, params)
                c.execute("RESET ROLE")             # un succès ne laisse pas le rôle posé pour la suite de la transaction
            return False
        except db.psycopg.errors.InsufficientPrivilege:
            return True


class StructureEtColonnes(BaseJetable):
    def noms(self, c, type_objet):
        return {r[0] for r in c.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                                        "WHERE n.nspname = 'quality' AND c.relkind = %s", (type_objet,))}

    def test_huit_tables_proprietaire_et_vides(self):
        c = self.conn()
        self.assertEqual(self.noms(c, "r"), TABLES)
        proprietaires = {r[0] for r in c.execute("SELECT DISTINCT pg_get_userbyid(c.relowner) FROM pg_class c JOIN pg_namespace n "
                                                  "ON n.oid = c.relnamespace WHERE n.nspname = 'quality'")}
        self.assertEqual(proprietaires, {"pmzilla_owner"})
        for table in TABLES:
            self.assertEqual(c.execute(f"SELECT count(*) FROM quality.{table}").fetchone()[0], 0, table)

    def test_exactement_trois_vues(self):
        self.assertEqual(self.noms(self.conn(), "v"), VUES)

    def test_le_schema_flow_est_inchange(self):
        c = self.conn()
        tables = {r[0] for r in c.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                                          "WHERE n.nspname = 'flow' AND c.relkind = 'r'")}
        # La migration 0010 ne touche pas au schéma flow : ses tables sont celles de 0002 à 0009 (dont la couche brute de R-70).
        self.assertEqual(tables, {"teams", "issues", "issue_teams", "transitions", "links", "issue_label_periods", "issue_version_periods",
                                  "raw_runs", "raw_run_sightings", "raw_issue_snapshots"})
        lignes = c.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'flow'").fetchall()
        colonnes = {col for _, col in lignes}
        self.assertFalse(colonnes & TEXTE_LIBRE)
        self.assertNotIn("feedback", colonnes)
        # content_hash n'existe dans flow que pour les instantanés de la couche brute (R-70, empreinte d'un ticket, jamais un texte).
        self.assertEqual({t for t, col in lignes if col == "content_hash"}, {"raw_issue_snapshots"})

    def test_aucun_nom_de_colonne_interdit(self):
        c = self.conn()
        for table, colonne in c.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'quality'"):
            nom = colonne.lower()
            self.assertNotIn(nom, NOMS_INTERDITS, f"{table}.{colonne}")
            self.assertEqual(set(nom.split("_")) & MOTS_INTERDITS, set(), f"{table}.{colonne} : nom de personne ou de compte")

    def test_le_drapeau_d_un_seul_po_est_un_booleen_d_equipe_et_la_seule_colonne_po(self):
        c = self.conn()
        # Tables seulement : la vue de couverture reprend le drapeau en clair (test des vues plus bas).
        lignes = c.execute("SELECT table_name, column_name, data_type, is_nullable, column_default FROM information_schema.columns "
                           "WHERE table_schema = 'quality' AND column_name = %s AND table_name IN (SELECT table_name FROM "
                           "information_schema.tables WHERE table_schema = 'quality' AND table_type = 'BASE TABLE')",
                           (DRAPEAU_UN_SEUL_PO,)).fetchall()
        self.assertEqual([(t, d, n) for t, _, d, n, _ in lignes], [("team_attributes", "boolean", "NO")])
        self.assertEqual(lignes[0][4], "false")                                   # une équipe n'est à un seul PO que si l'utilisateur le déclare
        autres = [col for _, col in c.execute("SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'quality'")
                  if "po" in col.split("_") and col != DRAPEAU_UN_SEUL_PO]
        self.assertEqual(autres, [])

    def test_texte_libre_seulement_dans_les_contenus_et_les_retours_de_coaching(self):
        c = self.conn()
        # Tables seulement : les colonnes des vues ont leur propre test (« les vues ne portent ni clé ni texte ni personne »).
        lignes = c.execute("SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = 'quality' "
                           "AND table_name IN (SELECT table_name FROM information_schema.tables WHERE table_schema = 'quality' "
                           "AND table_type = 'BASE TABLE')").fetchall()
        libres = {(t, col) for t, col, _ in lignes if col in TEXTE_LIBRE}
        self.assertEqual(libres, {("contents", "title"), ("contents", "description"), ("contents", "acceptance_criteria"),
                                  ("coaching_feedback", "feedback")})
        for table, colonne, type_donnee in lignes:
            if type_donnee == "text" and table not in TABLES_DE_TEXTE:
                self.assertIn(colonne, COLONNES_TEXTE_IDENTIFIANTS, f"{table}.{colonne} : colonne de texte hors des contenus")
        contenus = {col for t, col, _ in lignes if t == "contents"}
        self.assertEqual(contenus, {"item_key", "title", "description", "acceptance_criteria", "content_hash", "replacements"})

    def test_le_retour_de_coaching_est_borne(self):
        c = self.conn()
        self.item(c, "PROJ-1")
        c.execute("SET ROLE pmzilla_quality")
        c.execute("INSERT INTO quality.coaching_feedback (item_key, core_grid_id, core_grid_version, criterion_code, verdict, feedback) "
                  "VALUES ('PROJ-1', 'g', '1', 'c1', 'met', %s)", ("a" * 100,))
        with self.assertRaises(db.psycopg.errors.CheckViolation):
            with c.transaction():
                c.execute("INSERT INTO quality.coaching_feedback (item_key, core_grid_id, core_grid_version, criterion_code, verdict, "
                          "feedback) VALUES ('PROJ-1', 'g', '1', 'c1', 'met', %s)", ("a" * 5000,))
        c.execute("RESET ROLE")

    def test_attributs_d_equipe_et_relectures_sans_personne(self):
        c = self.conn()
        colonnes = {t: {col for tt, col in c.execute("SELECT table_name, column_name FROM information_schema.columns "
                                                      "WHERE table_schema = 'quality'") if tt == t} for t in ("team_attributes", "team_reviews")}
        self.assertEqual(colonnes["team_attributes"], {"team", "single_po"})
        self.assertEqual(colonnes["team_reviews"], {"id", "team", "reviewed_at", "sample_size"})
        c.execute("SET ROLE pmzilla_quality")
        with self.assertRaises(db.psycopg.errors.CheckViolation):
            with c.transaction():
                c.execute("INSERT INTO quality.team_reviews (team, sample_size) VALUES ('Alpha', 0)")
        c.execute("RESET ROLE")

    def test_la_version_d_une_surcouche_est_unique(self):
        c = self.conn()
        c.execute("SET ROLE pmzilla_quality")
        c.execute("INSERT INTO quality.overlay_versions (overlay_id, version, content_hash) VALUES ('o', '1', 'h1')")
        c.execute("INSERT INTO quality.overlay_versions (overlay_id, version, content_hash) VALUES ('o', '2', 'h2')")
        c.execute("INSERT INTO quality.overlay_versions (overlay_id, version, content_hash) VALUES ('autre', '1', 'h3')")
        with self.assertRaises(db.psycopg.errors.UniqueViolation):
            with c.transaction():
                c.execute("INSERT INTO quality.overlay_versions (overlay_id, version, content_hash) VALUES ('o', '1', 'h9')")
        colonnes = {r[0] for r in c.execute("SELECT column_name FROM information_schema.columns "
                                            "WHERE table_schema = 'quality' AND table_name = 'overlay_versions'")}
        self.assertEqual(colonnes, {"overlay_id", "version", "content_hash", "first_used_at"})
        c.execute("RESET ROLE")


class ContraintesEtCascade(BaseJetable):
    def test_la_marque_d_echantillon_est_obligatoire(self):
        c = self.conn()
        self.item(c, "PROJ-1")
        c.execute("SET ROLE pmzilla_quality")
        with self.assertRaises(db.psycopg.errors.NotNullViolation):
            with c.transaction():
                c.execute("INSERT INTO quality.assessments (item_key, core_grid_id, core_grid_version, criterion_code, origin, link, verdict) "
                          "VALUES ('PROJ-1', 'g', '1', 'c1', 'core', 'refinement', 'met')")
        c.execute("RESET ROLE")

    def test_les_quatre_verdicts_seulement(self):
        c = self.conn()
        self.item(c, "PROJ-1")
        for i, code in enumerate(("met", "not_met", "not_applicable", "undetermined")):
            self.verdict(c, "PROJ-1", code=f"c{i}", verdict=code)
        for faux in ("maybe", "", "MET"):
            with self.assertRaises(db.psycopg.errors.CheckViolation, msg=faux):
                with c.transaction():
                    self.verdict(c, "PROJ-1", code="cx", verdict=faux)

    def test_l_origine_est_le_socle_ou_une_regle_de_l_organisation(self):
        c = self.conn()
        self.item(c, "PROJ-1")
        self.verdict(c, "PROJ-1", code="c1", origine="core")
        self.verdict(c, "PROJ-1", code="c2", origine="organisation_rule")
        with self.assertRaises(db.psycopg.errors.CheckViolation):
            with c.transaction():
                self.verdict(c, "PROJ-1", code="c3", origine="team_rule")

    def test_le_lien_dans_la_chaine_est_l_un_des_quatre(self):
        c = self.conn()
        self.item(c, "PROJ-1")
        for i, lien in enumerate(("ticket_template", "discovery_workflow_step", "definition_of_ready", "refinement")):
            self.verdict(c, "PROJ-1", code=f"c{i}", lien=lien)
        with self.assertRaises(db.psycopg.errors.CheckViolation):
            with c.transaction():
                self.verdict(c, "PROJ-1", code="cx", lien="autre")

    def test_les_versions_du_socle_et_de_la_surcouche_accompagnent_chaque_ligne(self):
        c = self.conn()
        self.item(c, "PROJ-1")
        for table in ("assessments", "coaching_feedback"):
            ligne = {r[0]: (r[1], r[2]) for r in c.execute(
                "SELECT column_name, is_nullable, column_default FROM information_schema.columns "
                "WHERE table_schema = 'quality' AND table_name = %s", (table,))}
            for colonne in ("core_grid_id", "core_grid_version", "overlay_id", "overlay_version"):
                self.assertIn(colonne, ligne, f"{table}.{colonne}")
                self.assertEqual(ligne[colonne][0], "NO", f"{table}.{colonne} nullable")
            self.assertIsNone(ligne["core_grid_id"][1])                       # le socle est toujours donné
            self.assertIsNone(ligne["core_grid_version"][1])
            self.assertIn("''", ligne["overlay_id"][1])                       # vide quand il n'y a pas de surcouche
            self.assertIn("''", ligne["overlay_version"][1])
        c.execute("SET ROLE pmzilla_quality")
        with self.assertRaises(db.psycopg.errors.NotNullViolation):
            with c.transaction():
                c.execute("INSERT INTO quality.assessments (item_key, core_grid_id, criterion_code, origin, link, verdict, sample) "
                          "VALUES ('PROJ-1', 'g', 'c1', 'core', 'refinement', 'met', false)")
        with self.assertRaises(db.psycopg.errors.CheckViolation):             # un identifiant de surcouche sans version, ou l'inverse
            with c.transaction():
                self.verdict(c, "PROJ-1", surcouche=("o", ""))
        c.execute("RESET ROLE")

    def test_cascade_a_la_suppression_d_un_item(self):
        c = self.conn()
        self.item(c, "PROJ-1", ("Alpha", "Beta"))
        self.item(c, "PROJ-2")
        for cle in ("PROJ-1", "PROJ-2"):
            self.verdict(c, cle)
            self.verdict(c, cle, code="c9", sample=True)
        c.execute("SET ROLE pmzilla_quality")
        for cle in ("PROJ-1", "PROJ-2"):
            c.execute("INSERT INTO quality.coaching_feedback (item_key, core_grid_id, core_grid_version, criterion_code, verdict, feedback) "
                      "VALUES (%s, 'g', '1', 'c1', 'met', 'retour')", (cle,))
        c.execute("DELETE FROM quality.items WHERE key = 'PROJ-1'")
        for table in ("item_teams", "contents", "assessments", "coaching_feedback"):
            self.assertEqual(c.execute(f"SELECT count(*) FROM quality.{table} WHERE item_key = 'PROJ-1'").fetchone()[0], 0, table)
            self.assertGreater(c.execute(f"SELECT count(*) FROM quality.{table} WHERE item_key = 'PROJ-2'").fetchone()[0], 0, table)
        c.execute("RESET ROLE")

    def test_une_cle_etrangere_inconnue_est_refusee(self):
        c = self.conn()
        c.execute("SET ROLE pmzilla_quality")
        with self.assertRaises(db.psycopg.errors.ForeignKeyViolation):
            with c.transaction():
                c.execute("INSERT INTO quality.item_teams (item_key, team, position) VALUES ('NOPE-1', 'Alpha', 1)")
        c.execute("RESET ROLE")


class DroitsDesRoles(BaseJetable):
    def test_le_role_des_vues_lit_les_trois_vues_et_aucune_table(self):
        c = self.conn()
        for vue in VUES:
            self.assertFalse(self.refuse(c, "pmzilla_quality_views", f"SELECT * FROM quality.{vue}"), vue)
        for table in TABLES:
            self.assertTrue(self.refuse(c, "pmzilla_quality_views", f"SELECT * FROM quality.{table}"), table)

    def test_le_role_des_vues_n_ecrit_ni_ne_cree_ni_ne_lit_ailleurs(self):
        c = self.conn()
        self.assertTrue(self.refuse(c, "pmzilla_quality_views", "INSERT INTO quality.items (key, kind, created_at, updated_at) "
                                    "VALUES ('PROJ-1', 'story', now(), now())"))
        self.assertTrue(self.refuse(c, "pmzilla_quality_views", "CREATE TABLE quality.interdit (id int)"))
        self.assertTrue(self.refuse(c, "pmzilla_quality_views", "CREATE TABLE public.interdit (id int)"))
        for ailleurs in ("flow.issues", "flow.v_team_status", "cases.experiments", "knowledge.books"):
            self.assertTrue(self.refuse(c, "pmzilla_quality_views", f"SELECT * FROM {ailleurs}"), ailleurs)

    def test_les_roles_lecture_ecriture_et_lecture_seule(self):
        c = self.conn()
        self.item(c, "PROJ-1")
        self.assertFalse(self.refuse(c, "pmzilla_quality", "SELECT * FROM quality.contents"))
        self.assertFalse(self.refuse(c, "pmzilla_quality_ro", "SELECT * FROM quality.contents"))
        self.assertTrue(self.refuse(c, "pmzilla_quality_ro", "DELETE FROM quality.items"))
        self.assertTrue(self.refuse(c, "pmzilla_quality", "CREATE TABLE quality.interdit (id int)"))
        self.assertTrue(self.refuse(c, "pmzilla_quality", "DROP TABLE quality.items"))
        self.assertTrue(self.refuse(c, "pmzilla_quality", "SELECT * FROM flow.issues"))
        self.assertTrue(self.refuse(c, "pmzilla_quality_ro", "SELECT * FROM flow.issues"))

    def test_aucun_role_d_un_autre_schema_ne_lit_quality(self):
        c = self.conn()
        self.item(c, "PROJ-1")
        for role in ("pmzilla_flow", "pmzilla_flow_ro", "pmzilla_flow_views", "pmzilla_cases", "pmzilla_cases_ro", "pmzilla_knowledge",
                     "pmzilla_knowledge_ro"):
            self.assertTrue(self.refuse(c, role, "SELECT * FROM quality.contents"), role)
            self.assertTrue(self.refuse(c, role, "SELECT * FROM quality.quality_by_product"), role)

    def test_le_role_des_vues_existe_apres_migration(self):
        """Son attribut de connexion n'est pas vérifié ici : le rôle est partagé par l'instance et role-password le rend avec connexion.
        Que la migration ne le crée qu'en NOLOGIN est vérifié sans base (test_db.py et SansBase ci-dessous)."""
        c = self.conn()
        for role in ("pmzilla_quality", "pmzilla_quality_ro", "pmzilla_quality_views"):
            self.assertEqual(c.execute("SELECT count(*) FROM pg_roles WHERE rolname = %s", (role,)).fetchone()[0], 1, role)


class Vues(BaseJetable):
    def test_les_vues_ne_portent_ni_cle_ni_texte_ni_personne(self):
        c = self.conn()
        for vue in VUES:
            colonnes = set(self.colonnes_de(c, vue))
            self.assertFalse(colonnes & (TEXTE_LIBRE | {"key", "item_key", "parent_key", "content_hash"}), vue)
            for colonne in colonnes:
                self.assertEqual(set(colonne.split("_")) & MOTS_INTERDITS, set(), f"{vue}.{colonne}")

    def test_cellule_sous_le_minimum_masquee(self):
        c = self.conn()
        self.lot(c, "Alpha", 3, "A", verdicts=("met",))
        self.lot(c, "Beta", 12, "B", verdicts=("met", "not_met"))
        c.commit()
        lignes = {r[0]: r for r in self.lire(c, "quality_by_team", colonnes="team, audited, met, not_met, not_applicable, undetermined")}
        self.assertEqual(lignes["Alpha"][1:], (None, None, None, None, None))      # trois stories : tout est masqué
        # douze stories : les zéros sont masqués, et leur somme nulle les redonnerait : le plus petit compte visible (met, à égalité) aussi (0016)
        self.assertEqual(lignes["Beta"][1:], (12, None, 6, None, None))

    def test_la_vue_par_equipe_porte_l_origine_et_le_lien(self):
        c = self.conn()
        self.lot(c, "Alpha", 6, "A", origine="organisation_rule", lien="definition_of_ready")
        c.commit()
        ligne = self.lire(c, "quality_by_team", colonnes="team, item_kind, criterion_code, origin, link")[0]
        self.assertEqual(ligne, ("Alpha", "story", "c1", "organisation_rule", "definition_of_ready"))

    def test_les_retours_de_coaching_ne_changent_aucun_compte(self):
        c = self.conn()
        self.lot(c, "Alpha", 6, "A", verdicts=("met", "not_met"))
        c.commit()
        avant = {v: self.lire(c, v) for v in VUES}
        c.execute("SET ROLE pmzilla_quality")
        for i in range(6):
            c.execute("INSERT INTO quality.coaching_feedback (item_key, core_grid_id, core_grid_version, criterion_code, verdict, feedback) "
                      "VALUES (%s, 'g', '1', 'c1', 'not_met', 'retour')", (f"A-{i}",))
            c.execute("INSERT INTO quality.coaching_feedback (item_key, core_grid_id, core_grid_version, criterion_code, verdict, feedback) "
                      "VALUES (%s, 'g', '1', 'cz', 'met', 'retour')", (f"A-{i}",))
        c.execute("RESET ROLE")
        c.commit()
        self.assertEqual({v: self.lire(c, v) for v in VUES}, avant)

    def test_les_verdicts_d_echantillon_ne_comptent_pas(self):
        c = self.conn()
        self.lot(c, "Alpha", 6, "A", verdicts=("met",))
        c.commit()
        avant = {v: self.lire(c, v) for v in VUES}
        for i in range(6):
            self.item(c, f"S-{i}", ("Alpha",))
            self.verdict(c, f"S-{i}", verdict="not_met", sample=True)           # six autres stories, verdicts d'échantillon seulement
            self.verdict(c, f"A-{i}", code="cs", verdict="not_met", sample=True)
        c.commit()
        apres = {v: self.lire(c, v) for v in VUES}
        self.assertEqual(apres["quality_by_team"], avant["quality_by_team"])
        self.assertEqual(apres["quality_by_product"], avant["quality_by_product"])
        couverture = self.lire(c, "quality_coverage_by_team", colonnes="team, collected, audited")
        self.assertEqual(couverture, [("Alpha", 12, 6)])                         # les six stories d'échantillon sont collectées, non auditées

    def test_les_items_sortis_de_la_collecte_sont_ecartes(self):
        c = self.conn()
        self.lot(c, "Alpha", 6, "A")
        for i in range(6):
            self.item(c, f"X-{i}", ("Alpha",), sorti=True)
            self.verdict(c, f"X-{i}", verdict="not_met")
        c.commit()
        self.assertEqual(self.lire(c, "quality_by_team", colonnes="audited, met, not_met"), [(6, None, None)])   # complément (0016)
        self.assertEqual(self.lire(c, "quality_by_product", colonnes="audited"), [(6,)])
        # tout est audité : collectés moins audités vaudrait 0, les collectés sont masqués (0016)
        self.assertEqual(self.lire(c, "quality_coverage_by_team", colonnes="collected, audited"), [(None, 6)])

    def test_seules_les_versions_courantes_comptent(self):
        c = self.conn()
        self.lot(c, "Alpha", 6, "A", coeur="1", instant="now() - interval '2 days'")           # anciennes versions
        self.lot(c, "Beta", 6, "B", coeur="2", instant="now() - interval '1 day'")             # version courante : la plus récente
        c.commit()
        self.assertEqual(self.lire(c, "quality_by_team", colonnes="team, audited"), [("Beta", 6)])
        self.assertEqual(self.lire(c, "quality_by_product", colonnes="audited"), [(6,)])
        self.assertEqual(self.lire(c, "quality_coverage_by_team", colonnes="team, collected, audited"),
                         [("Alpha", 6, None), ("Beta", None, 6)])                            # la couverture dit combien sont audités à la paire courante

    def test_une_nouvelle_version_de_surcouche_rend_les_anciens_verdicts_muets(self):
        c = self.conn()
        self.lot(c, "Alpha", 6, "A", surcouche=("o", "1"), instant="now() - interval '2 days'")
        c.commit()
        self.assertEqual(self.lire(c, "quality_by_team", colonnes="audited"), [(6,)])
        for i in range(2):                                                                   # deux items réaudités à la version 2 : elle devient courante
            self.verdict(c, f"A-{i}", surcouche=("o", "2"))
        c.commit()
        self.assertEqual(self.lire(c, "quality_by_team", colonnes="audited"), [(None,)])    # deux sont masqués, quatre restent à auditer
        self.assertEqual(self.lire(c, "quality_coverage_by_team", colonnes="collected, audited"), [(6, None)])

    def test_sans_aucun_verdict_les_vues_de_resultats_sont_vides(self):
        c = self.conn()
        self.item(c, "PROJ-1")
        c.commit()
        self.assertEqual(self.lire(c, "quality_by_team"), [])
        self.assertEqual(self.lire(c, "quality_by_product"), [])
        self.assertEqual(self.lire(c, "quality_coverage_by_team", colonnes="team, collected, audited"), [("Alpha", None, None)])

    def test_la_couverture_compte_les_criteres_d_acceptation_vides(self):
        c = self.conn()
        for i in range(12):
            self.item(c, f"V-{i}", ("Alpha",), acceptation="" if i < 5 else "critère")
        c.commit()
        self.assertEqual(self.lire(c, "quality_coverage_by_team", colonnes="collected, empty_acceptance_criteria"), [(12, 5)])
        for i in range(12, 15):                                                              # 15 collectés, 5 vides : la différence reste de 5 et plus
            self.item(c, f"V-{i}", ("Alpha",))
        c.commit()
        self.assertEqual(self.lire(c, "quality_coverage_by_team", colonnes="collected, empty_acceptance_criteria"), [(15, 5)])
        self.item(c, "V-W", ("Beta",), acceptation="")
        for i in range(6):                                                                   # Beta : 6 collectés dont 5 vides, différence 1 : vides masqués (0016)
            self.item(c, f"V-B{i}", ("Beta",), acceptation="" if i < 4 else "critère")
        c.commit()
        self.assertEqual(self.lire(c, "quality_coverage_by_team", colonnes="team, collected, empty_acceptance_criteria"),
                         [("Alpha", 15, 5), ("Beta", 7, None)])

    def test_le_drapeau_d_un_seul_po_est_en_clair_et_ne_change_aucun_compte(self):
        c = self.conn()
        self.lot(c, "Alpha", 6, "A", verdicts=("met", "not_met"))
        self.lot(c, "Beta", 2, "B")
        c.commit()
        comptes = "team, item_kind, collected, audited, empty_acceptance_criteria"
        avant = (self.lire(c, "quality_coverage_by_team", colonnes=comptes), self.lire(c, "quality_by_team"))
        self.assertEqual(self.lire(c, "quality_coverage_by_team", colonnes="team, single_po"), [("Alpha", False), ("Beta", False)])
        c.execute("SET ROLE pmzilla_quality")
        c.execute("INSERT INTO quality.team_attributes (team, single_po) VALUES ('Beta', true), ('Alpha', false)")
        c.execute("RESET ROLE")
        c.commit()
        self.assertEqual(self.lire(c, "quality_coverage_by_team", colonnes="team, single_po"), [("Alpha", False), ("Beta", True)])
        self.assertEqual((self.lire(c, "quality_coverage_by_team", colonnes=comptes), self.lire(c, "quality_by_team")), avant)
        # le drapeau d'une équipe dont les comptes sont masqués reste lisible : il n'est jamais masqué
        beta = self.lire(c, "quality_coverage_by_team", colonnes="team, collected, single_po", ordre="team")[1]
        self.assertEqual(beta, ("Beta", None, True))


class VueDuProduit(BaseJetable):
    def test_aucune_colonne_ne_nomme_ni_n_identifie_une_equipe(self):
        c = self.conn()
        colonnes = self.colonnes_de(c, "quality_by_product")
        self.assertEqual(colonnes, ["item_kind", "criterion_code", "origin", "link", "audited", "met", "not_met", "not_applicable",
                                    "undetermined", "core_grid_version", "overlay_version"])                # versions : migration 0016
        self.assertFalse({"team", "team_id", "equipe"} & set(colonnes))

    def test_un_item_de_deux_equipes_compte_une_fois(self):
        c = self.conn()
        self.lot(c, "Alpha", 11, "A")
        self.lot(c, "Beta", 5, "B")                     # Beta assez grande : une seule petite équipe masquerait la ligne du produit (D18, 0016)
        self.item(c, "AB-1", ("Alpha", "Beta"))
        self.verdict(c, "AB-1")
        c.commit()
        # dix-sept, pas dix-huit ; met masqué par le complément (les trois zéros de la ligne)
        self.assertEqual(self.lire(c, "quality_by_product", colonnes="audited, met"), [(17, None)])
        par_equipe = {r[0]: r[1] for r in self.lire(c, "quality_by_team", colonnes="team, audited")}
        self.assertEqual(par_equipe, {"Alpha": 12, "Beta": 6})                                              # l'item est bien chez les deux équipes

    def test_trois_stories_seulement_donnent_des_cellules_masquees(self):
        c = self.conn()
        self.lot(c, "Alpha", 2, "A")
        self.lot(c, "Beta", 1, "B")
        c.commit()
        self.assertEqual(self.lire(c, "quality_by_product", colonnes="audited, met, not_met, not_applicable, undetermined"),
                         [(None, None, None, None, None)])

    def test_epics_et_stories_sont_comptees_a_part(self):
        c = self.conn()
        self.lot(c, "Alpha", 6, "A")
        for i in range(6):
            self.item(c, f"E-{i}", ("Alpha",), kind="epic")
            self.verdict(c, f"E-{i}", verdict="not_met")
        c.commit()
        self.assertEqual(self.lire(c, "quality_by_product", colonnes="item_kind, audited, met, not_met", ordre="item_kind"),
                         [("epic", 6, None, None), ("story", 6, None, None)])                 # complément : trois zéros masqués (0016)


# --- Tâche 3.27 : aucune colonne de verdict ne garde un extrait de texte de story -----------------------------------------------------
COLONNES_VERDICT = {"id", "item_key", "core_grid_id", "core_grid_version", "overlay_id", "overlay_version", "criterion_code", "origin",
                    "link", "verdict", "sample", "analysed_at", "content_hash"}     # 0010, plus content_hash (0015) ; toute autre : à revoir
PREFIXE_SENTINELLE = "zzq"                                                          # chaque mot des textes de story commence ainsi
INSTANT_COLLECTE = dt.datetime(2026, 9, 1, 10, 0, tzinfo=dt.timezone.utc)
CODES_EFFECTIFS = {"story": ["story-un", "story-trois", "orga-role"], "epic": ["epic-un", "epic-deux", "orga-objectif"]}  # avec la surcouche


def textes_sentinelles(i: int) -> tuple[str, str, str]:
    """(titre, description, critères d'acceptation) de l'élément n° i : des mots distinctifs seulement, tous préfixés."""
    return (f"zzqtitre{i} zzqquetzal{i}", f"zzqdescription{i} zzqbrontosaure{i} zzqphrase{i}", f"zzqcritere{i} zzqxylophone{i}")


def mots_sentinelles(i: int) -> list[str]:
    return " ".join(textes_sentinelles(i)).split()


class VerdictsSansTexteDeStory(EspaceAnalyse):
    """Base jetable remplie par `analyse` (outil réel, faux serveur d'analyse, fausse clé) : sept éléments aux textes sentinelles, une
    surcouche, un audit puis un échantillon. Le faux moteur renvoie le texte de la story dans chaque champ qu'il peut remplir (retour,
    citation, verdict, code de critère, champs inconnus, texte brut). Aucune colonne de quality.assessments n'en garde un extrait."""

    # Mode de réponse du faux moteur, par numéro d'élément (le 7 est une epic).
    MODES = {1: "champs_en_plus", 2: "verdict_texte", 3: "critere_texte", 4: "texte_brut", 5: "code_colle", 6: "colonnes_imitees",
             7: "champs_en_plus"}

    def setUp(self):
        if not base.BASE_DISPONIBLE:
            self.skipTest(base.MESSAGE_SAUT)
        super().setUp()
        self.nom_base = "pmzilla_test_" + secrets.token_hex(6)
        self.admin = db.connect(base.URL_BASE, password=base.MOT_DE_PASSE, autocommit=True)
        self.ouvertes = []
        self.addCleanup(self._supprimer)
        self.admin.execute(f'CREATE DATABASE "{self.nom_base}"')
        self.url = base.url_vers(self.nom_base)
        migration = db.connect(self.url, password=base.MOT_DE_PASSE)
        db.migrer(migration, db.lister_migrations(db.DOSSIER_MIGRATIONS))
        migration.commit()
        migration.close()
        self.verif = self._connexion(autocommit=True)
        self.cles = {i: f"ZZA-{i:03d}" for i in self.MODES}
        elements = []
        for i, cle in self.cles.items():
            titre, description, criteres = textes_sentinelles(i)
            elements.append(store.Element(key=cle, kind="epic" if i == 7 else "story", parent_key=None, status_category="new",
                                          created_at=INSTANT_COLLECTE, updated_at=INSTANT_COLLECTE, resolved_at=None, teams=[EQUIPE_A],
                                          title=titre, description=description, acceptance_criteria=criteres,
                                          content_hash=scrub.empreinte(titre, description, criteres), replacements=0))
        self.nouveau_magasin()
        self.analyse.enregistrer_collecte(elements, {}, complet=True)
        self.analyse.enregistrer_relecture(EQUIPE_A, 3)                    # porte de relecture ouverte pour l'équipe
        self.surcouche()                                                   # colonnes de surcouche remplies
        self.moteur.fabriquer = self.reponse_hostile

    def _connexion(self, autocommit=False):
        c = db.connect(self.url, password=base.MOT_DE_PASSE, autocommit=autocommit)
        self.ouvertes.append(c)
        return c

    def _supprimer(self):
        for c in self.ouvertes:
            with contextlib.suppress(Exception):
                c.close()
        with contextlib.suppress(Exception):
            self.admin.execute(f'DROP DATABASE IF EXISTS "{self.nom_base}" WITH (FORCE)')
        self.admin.close()

    def nouveau_magasin(self):
        """Le vrai magasin de `analyse` sur la base jetable, sous le rôle de lecture-écriture ; `analyse` le ferme à la fin du lancement."""
        c = self._connexion()
        c.execute(f"SET ROLE {store.ROLE}")
        c.commit()
        self.analyse = audit_store.MagasinAnalyse(c)

    def lancer(self, *argv, **options):
        self.nouveau_magasin()
        return super().lancer(*argv, **options)

    def reponse_hostile(self, requete: dict) -> str:
        document = json.loads(requete["messages"][0]["content"])
        texte = " ".join((document["title"], document["description"], document["acceptance_criteria"]))
        i = int(re.match(r"zzqtitre(\d+)", document["title"]).group(1))
        codes = [c["code"] for c in document["criteria"]]
        mode = self.MODES[i]
        if mode == "texte_brut":
            return texte
        if mode == "verdict_texte":
            lignes = [{"criterion": c, "verdict": document["title"]} for c in codes]
        elif mode == "critere_texte":
            lignes = [{"criterion": document["description"], "verdict": "met"}]
        elif mode == "code_colle":
            lignes = [{"criterion": f"{c} {document['title']}", "verdict": "met"} for c in codes]
        elif mode == "colonnes_imitees":
            lignes = [{"criterion": c, "verdict": "met", "item_key": texte, "origin": texte, "link": texte, "content_hash": texte,
                       "core_grid_id": texte, "overlay_id": texte, "sample": texte} for c in codes]
        else:
            lignes = [{"criterion": c, "verdict": "not_met", "feedback": texte, "quote": document["acceptance_criteria"],
                       "evidence": document["description"]} for c in codes]
        return json.dumps({"verdicts": lignes, "explanation": texte, "summary": document["title"]}, ensure_ascii=False)

    def lignes(self):
        noms = [d.name for d in self.verif.execute("SELECT * FROM quality.assessments LIMIT 0").description]
        return noms, self.verif.execute("SELECT * FROM quality.assessments ORDER BY id").fetchall()

    def test_aucune_colonne_de_verdict_ne_garde_un_extrait_de_story(self):
        code, _, erreur = self.lancer("analyse")
        self.assertEqual(code, 0, erreur)
        code, _, erreur = self.lancer("analyse", "--sample", "3")
        self.assertEqual(code, 0, erreur)
        envoye = json.dumps(self.moteur.requetes, ensure_ascii=False)
        for i in self.MODES:                                                   # les sentinelles sont bien parties au moteur
            for mot in mots_sentinelles(i):
                self.assertIn(mot, envoye)
        noms, lignes = self.lignes()
        self.assertEqual(set(noms), COLONNES_VERDICT)                          # une colonne nouvelle oblige à refaire la preuve
        self.assertEqual(sum(1 for ligne in lignes if not ligne[noms.index("sample")]), 21)    # sept éléments, trois critères chacun
        self.assertEqual(sum(1 for ligne in lignes if ligne[noms.index("sample")]), 9)         # trois éléments d'échantillon
        tous_les_mots = [m for i in self.MODES for m in mots_sentinelles(i)]
        for ligne in lignes:
            for nom, valeur in zip(noms, ligne):
                texte = "" if valeur is None else str(valeur).casefold()
                self.assertNotIn(PREFIXE_SENTINELLE, texte, f"assessments.{nom}")
                for mot in tous_les_mots:
                    self.assertNotIn(mot.casefold(), texte, f"assessments.{nom}")
        for (ligne_json,) in self.verif.execute("SELECT row_to_json(a)::text FROM quality.assessments a"):
            self.assertNotIn(PREFIXE_SENTINELLE, ligne_json.casefold())

    def test_chaque_colonne_ne_porte_que_sa_valeur_attendue(self):
        self.lancer("analyse")
        self.lancer("analyse", "--sample", "3")
        noms, lignes = self.lignes()
        par_cle = {cle: i for i, cle in self.cles.items()}
        for ligne in lignes:
            v = dict(zip(noms, ligne))
            i = par_cle[v["item_key"]]                                         # une clé d'élément collecté, rien d'autre
            genre = "epic" if i == 7 else "story"
            self.assertEqual((v["core_grid_id"], v["core_grid_version"]), ("socle-fictif", "3"))
            self.assertEqual((v["overlay_id"], v["overlay_version"]), (IDENTIFIANT_SURCOUCHE, "2"))
            self.assertIn(v["criterion_code"], CODES_EFFECTIFS[genre])         # code de la grille, jamais celui que le moteur a écrit
            self.assertEqual(v["origin"], "organisation_rule" if v["criterion_code"].startswith("orga-") else "core")
            self.assertIn(v["link"], ("ticket_template", "discovery_workflow_step", "definition_of_ready", "refinement"))
            self.assertIn(v["verdict"], ("met", "not_met", "not_applicable", "undetermined"))
            self.assertIsInstance(v["sample"], bool)
            self.assertIsInstance(v["analysed_at"], dt.datetime)
            self.assertEqual(v["content_hash"], scrub.empreinte(*textes_sentinelles(i)))   # condensé du texte envoyé, jamais un extrait
            self.assertRegex(v["content_hash"], r"^[0-9a-f]{64}$")
            # champs inconnus ignorés ; toute réponse où le texte prend la place d'un code est refusée (tout « undetermined »)
            attendu = {"champs_en_plus": "not_met", "colonnes_imitees": "met"}.get(self.MODES[i], "undetermined")
            self.assertEqual(v["verdict"], attendu, f"élément {i} ({self.MODES[i]})")


class SansBase(unittest.TestCase):
    """Sans base : lecture du fichier de migration (toujours exécutés). Le numéro 0010 est confirmé depuis la fusion de R-70 (0009), le 2026-10-17."""

    def test_l_ecriture_des_verdicts_ne_nomme_que_les_colonnes_sans_texte(self):
        """Tâche 3.27, partie statique : le seul INSERT de quality.assessments (story_quality_audit_store.SQL_VERDICT) nomme les colonnes
        de COLONNES_VERDICT, moins l'identifiant et l'instant posés par la base ; 0015 n'ajoute que content_hash."""
        colonnes = re.search(r"INSERT INTO quality\.assessments \(([^)]*)\)", audit_store.SQL_VERDICT).group(1)
        self.assertEqual({c.strip() for c in colonnes.split(",")}, COLONNES_VERDICT - {"id", "analysed_at"})
        ajout = (db.DOSSIER_MIGRATIONS / "0015_quality_assessment_content_hash.sql").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"(?im)^ALTER TABLE quality\.assessments ADD COLUMN (\w+)", ajout), ["content_hash"])

    def texte(self):
        return (db.DOSSIER_MIGRATIONS / MIGRATION).read_text(encoding="utf-8")

    def sans_commentaires(self):
        return "\n".join(ligne.split("--")[0] for ligne in self.texte().splitlines())

    def test_migration_presente_apres_la_0008_et_premiere_ligne(self):
        fichiers = sorted(p.name for p in db.DOSSIER_MIGRATIONS.glob("*.sql"))
        self.assertIn(MIGRATION, fichiers)
        self.assertGreater(fichiers.index(MIGRATION), fichiers.index("0008_flow_gdpr.sql"))
        self.assertRegex(self.texte().splitlines()[0], r"^-- Schéma touché : quality")

    def test_aucune_donnee_ni_mot_de_passe_ni_role_avec_connexion(self):
        texte = self.sans_commentaires()
        self.assertNotRegex(texte, r"(?im)^\s*(INSERT\s+INTO|UPDATE\s|DELETE\s+FROM|COPY\s)")
        self.assertNotRegex(texte.upper(), r"PASSWORD|ALTER\s+ROLE|DROP\s+ROLE")
        self.assertNotRegex(texte, r"(?<!NO)LOGIN")
        for creation in re.findall(r"CREATE ROLE[^;']*", texte):
            self.assertIn("NOLOGIN", creation)
        for role in ("pmzilla_quality", "pmzilla_quality_ro", "pmzilla_quality_views"):
            self.assertIn(role, texte)

    def test_objets_crees_sous_le_proprietaire(self):
        texte = self.texte()
        self.assertRegex(texte, r"(?m)^SET LOCAL ROLE pmzilla_owner;")
        premiere_creation = min(texte.index(f"CREATE {objet}") for objet in ("TABLE", "VIEW", "FUNCTION"))
        self.assertLess(texte.index("SET LOCAL ROLE pmzilla_owner"), premiere_creation)
        self.assertRegex(texte, r"CREATE SCHEMA (IF NOT EXISTS )?quality AUTHORIZATION pmzilla_owner")
        self.assertRegex(texte, r"REVOKE ALL ON SCHEMA quality FROM PUBLIC")

    def test_huit_tables_et_trois_vues(self):
        texte = self.texte()
        tables = set(re.findall(r"CREATE TABLE quality\.([a-z_]+)", texte))
        self.assertEqual(tables, TABLES)
        self.assertEqual(set(re.findall(r"CREATE (?:OR REPLACE )?VIEW quality\.([a-z_]+)", texte)), VUES)

    def test_le_role_des_vues_ne_recoit_que_les_trois_vues(self):
        texte = self.sans_commentaires()
        accordes = [g for g in re.findall(r"(?is)GRANT\b.*?;", texte) if "pmzilla_quality_views" in g]
        for accord in accordes:
            self.assertNotRegex(accord, r"(?i)\bON\s+(ALL\s+)?TABLES|\bON\s+quality\.(" + "|".join(sorted(TABLES)) + r")\b", accord)
            self.assertNotRegex(accord, r"(?i)INSERT|UPDATE|DELETE|CREATE", accord)
        texte_accords = " ".join(accordes)
        for vue in VUES:
            self.assertIn(f"quality.{vue}", texte_accords)
        self.assertNotRegex(texte, r"(?i)DEFAULT PRIVILEGES[^;]*pmzilla_quality_views")

    def test_les_roles_de_lecture_ecriture_et_de_lecture_seule_ont_leurs_droits(self):
        texte = self.sans_commentaires()
        self.assertRegex(texte, r"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA quality TO pmzilla_quality;")
        self.assertRegex(texte, r"GRANT SELECT ON ALL TABLES IN SCHEMA quality TO pmzilla_quality_ro;")

    def test_les_cles_etrangeres_partent_en_cascade(self):
        texte = self.texte()
        for table in ("item_teams", "contents", "assessments", "coaching_feedback"):
            bloc = re.search(rf"CREATE TABLE quality\.{table} \((.*?)\n\);", texte, re.S)
            self.assertIsNotNone(bloc, table)
            self.assertIn("REFERENCES quality.items (key) ON DELETE CASCADE", bloc.group(1), table)

    def test_la_migration_ne_touche_pas_aux_autres_schemas(self):
        texte = self.sans_commentaires()
        for schema in ("flow", "cases", "knowledge"):
            self.assertNotRegex(texte, rf"(?i)\b{schema}\.[a-z_]+")


if __name__ == "__main__":
    unittest.main()
