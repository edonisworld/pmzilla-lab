"""
Tests de la migration 0007 (veille et pré-tri dans le schéma knowledge, lot 5) sur une base jetable pmzilla_test_<hex>.

    uv run --with "psycopg[binary]" python -m unittest tests.db.test_watch_schema   (ou discover -s tests/db)

Les tests statiques tournent toujours. Les tests avec base ne touchent que la base jetable (créée puis supprimée dans tous les cas),
jamais les schémas réels ; ils sont sautés si la base manque. Aucune donnée réelle : valeurs inventées.
"""
import contextlib
import re
import secrets
import unittest

import test_db as base          # noqa: E402  (même dossier : connexion, base jetable, mot de passe)
from test_db import db          # noqa: E402

MIGRATION = "0007_knowledge_watch_triage.sql"
TABLES_VEILLE = {
    "watch_articles", "watch_source_runs", "watch_article_links",
    "triage_references", "triage_scores", "triage_forced", "triage_excluded", "triage_shared", "triage_daily_picks",
    "triage_shadow_scores", "triage_calibration",
}
TABLES_BIBLIOTHEQUE = {"books", "collections", "book_collections", "chunks"}
VECTEUR = "[" + ",".join(["1"] + ["0"] * 1023) + "]"


class SansBase(unittest.TestCase):
    def texte(self) -> str:
        return (db.DOSSIER_MIGRATIONS / MIGRATION).read_text(encoding="utf-8")

    def test_la_migration_existe_et_porte_le_prochain_numero(self):
        noms = [m.nom for m in db.lister_migrations()]
        self.assertIn(MIGRATION, noms)
        self.assertEqual(noms, sorted(noms))

    def test_premiere_ligne_schema_touche_knowledge(self):
        self.assertRegex(self.texte().splitlines()[0], r"^-- Schéma touché : knowledge")

    def test_aucune_donnee_aucun_mot_de_passe_aucun_role_modifie(self):
        texte = self.texte()
        code = "\n".join(ligne.split("--")[0] for ligne in texte.splitlines())
        self.assertNotRegex(code, r"(?im)^\s*INSERT\s+INTO")
        self.assertNotRegex(code, r"(?i)password")
        self.assertNotRegex(code, r"(?i)ALTER\s+ROLE")
        self.assertNotRegex(code, r"(?i)CREATE\s+ROLE")

    def test_les_onze_tables_sont_nommees(self):
        creees = set(re.findall(r"(?i)CREATE TABLE knowledge\.(\w+)", self.texte()))
        self.assertEqual(creees, TABLES_VEILLE)
        self.assertEqual(len(creees), 11)

    def test_les_droits_ne_visent_que_les_deux_roles_knowledge(self):
        code = "\n".join(ligne.split("--")[0] for ligne in self.texte().splitlines())
        for role in re.findall(r"(?i)\bTO\s+(\w+)", code):
            self.assertIn(role, {"pmzilla_knowledge", "pmzilla_knowledge_ro"})


class AvecBase(unittest.TestCase):
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

    def conn(self, role=None):
        c = db.connect(self.url, password=base.MOT_DE_PASSE)
        self.ouvertes.append(c)
        if role:
            c.execute(f"SET ROLE {role}")
            c.commit()      # le SET ROLE survit aux rollback
        return c

    def refuse(self, c, ordre, params=None, role=None):
        with self.assertRaises(Exception, msg=ordre):
            c.execute(ordre, params)
        c.rollback()
        if role:
            c.execute(f"SET ROLE {role}")
            c.commit()

    # -- 1.1 : schéma --------------------------------------------------------

    def test_les_onze_tables_existent_au_nom_du_proprietaire_et_vides(self):
        c = self.conn()
        noms = {r[0] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'knowledge'")}
        self.assertEqual(noms, TABLES_BIBLIOTHEQUE | TABLES_VEILLE)
        proprietaires = {r[0] for r in c.execute("SELECT DISTINCT tableowner FROM pg_tables WHERE schemaname = 'knowledge'")}
        self.assertEqual(proprietaires, {"pmzilla_owner"})
        for table in TABLES_VEILLE:
            with self.subTest(table=table):
                self.assertEqual(c.execute(f"SELECT count(*) FROM knowledge.{table}").fetchone()[0], 0)

    def test_types_des_colonnes_principales(self):
        c = self.conn()
        colonnes = {(r[0], r[1]): r[2] for r in c.execute(
            "SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = 'knowledge'")}
        self.assertEqual(colonnes[("watch_articles", "links_extracted")], "boolean")
        self.assertEqual(colonnes[("watch_articles", "published")], "date")
        self.assertEqual(colonnes[("watch_articles", "collected")], "timestamp with time zone")
        self.assertEqual(colonnes[("triage_scores", "criteria")], "jsonb")
        self.assertEqual(colonnes[("triage_scores", "justifications")], "jsonb")
        self.assertEqual(colonnes[("triage_scores", "embedding")], "USER-DEFINED")
        self.assertEqual(colonnes[("triage_references", "embedding")], "USER-DEFINED")
        for nom in ("summary", "why", "is_compilation", "in_themes", "is_promo"):
            self.assertIn(("triage_scores", nom), colonnes)
        for ancien in ("resume", "pourquoi", "compilation", "promo"):
            self.assertNotIn(("triage_scores", ancien), colonnes)
        self.assertEqual(colonnes[("triage_calibration", "exported_at")], "timestamp with time zone")
        self.assertEqual(colonnes[("triage_calibration", "in_themes")], "boolean")

    def test_unicite_article_ombre_et_selection_du_jour(self):
        c = self.conn("pmzilla_knowledge")
        c.execute("INSERT INTO knowledge.watch_articles VALUES ('https://a.test/1', 'a.test', 'Titre A', 'a.md', '2026-10-01', true, now(), false)")
        self.refuse(c, "INSERT INTO knowledge.watch_articles VALUES ('https://a.test/1', 'a.test', 'Autre', 'b.md', NULL, true, now(), false)",
                    role="pmzilla_knowledge")
        c.execute("INSERT INTO knowledge.triage_shadow_scores (url, language) VALUES ('https://a.test/1', 'en')")
        self.refuse(c, "INSERT INTO knowledge.triage_shadow_scores (url, language) VALUES ('https://a.test/1', 'en')", role="pmzilla_knowledge")
        c.execute("INSERT INTO knowledge.triage_shadow_scores (url, language) VALUES ('https://a.test/1', 'fr')")
        c.execute("INSERT INTO knowledge.triage_daily_picks VALUES ('2026-10-01', 'a.md')")
        self.refuse(c, "INSERT INTO knowledge.triage_daily_picks VALUES ('2026-10-01', 'a.md')", role="pmzilla_knowledge")
        c.rollback()

    def test_article_publie_sans_date_accepte(self):
        c = self.conn("pmzilla_knowledge")
        c.execute("INSERT INTO knowledge.watch_articles VALUES ('https://a.test/2', 'a.test', 'T', 'a.md', NULL, false, now(), false)")
        c.rollback()

    def test_lien_cite_d_un_article_inconnu_refuse_et_suppression_en_cascade(self):
        c = self.conn("pmzilla_knowledge")
        self.refuse(c, "INSERT INTO knowledge.watch_article_links VALUES ('https://inconnu.test/x', 'https://cible.test/y')",
                    role="pmzilla_knowledge")
        c.execute("INSERT INTO knowledge.watch_articles VALUES ('https://a.test/1', 'a.test', 'T', 'a.md', NULL, true, now(), true)")
        c.execute("INSERT INTO knowledge.watch_article_links VALUES ('https://a.test/1', 'https://cible.test/y')")
        self.refuse(c, "INSERT INTO knowledge.watch_article_links VALUES ('https://a.test/1', 'https://cible.test/y')",
                    role="pmzilla_knowledge")
        c.execute("INSERT INTO knowledge.watch_articles VALUES ('https://a.test/1', 'a.test', 'T', 'a.md', NULL, true, now(), true)")
        c.execute("INSERT INTO knowledge.watch_article_links VALUES ('https://a.test/1', 'https://cible.test/y')")
        c.execute("DELETE FROM knowledge.watch_articles WHERE url = 'https://a.test/1'")
        self.assertEqual(c.execute("SELECT count(*) FROM knowledge.watch_article_links").fetchone()[0], 0)
        c.rollback()

    def test_index_sur_l_adresse_cible_des_liens(self):
        c = self.conn()
        index = {r[0] for r in c.execute("SELECT indexdef FROM pg_indexes WHERE schemaname = 'knowledge' AND tablename = 'watch_article_links'")}
        self.assertTrue(any("target_url" in d and "article_url" not in d.split("(")[1] for d in index), index)

    def test_calibration_verdict_et_avis_contraints(self):
        c = self.conn("pmzilla_knowledge")
        c.execute("INSERT INTO knowledge.triage_calibration (file, exported_at, verdict) VALUES ('a.md', now(), 'keep')")
        c.execute("INSERT INTO knowledge.triage_calibration (file, exported_at, verdict, opinion, opinion_at) VALUES ('b.md', now(), 'discard', 'keep', now())")
        c.execute("INSERT INTO knowledge.triage_calibration (file, exported_at, verdict, opinion) VALUES ('c.md', now(), 'keep', NULL)")
        self.refuse(c, "INSERT INTO knowledge.triage_calibration (file, exported_at, verdict) VALUES ('d.md', now(), 'maybe')", role="pmzilla_knowledge")
        self.refuse(c, "INSERT INTO knowledge.triage_calibration (file, exported_at, verdict, opinion) VALUES ('e.md', now(), 'keep', 'g')",
                    role="pmzilla_knowledge")
        self.refuse(c, "INSERT INTO knowledge.triage_calibration (file, exported_at, verdict) VALUES (NULL, now(), 'keep')", role="pmzilla_knowledge")
        self.refuse(c, "INSERT INTO knowledge.triage_calibration (file, verdict) VALUES ('f.md', 'keep')", role="pmzilla_knowledge")
        self.refuse(c, "INSERT INTO knowledge.triage_calibration (file, exported_at) VALUES ('g.md', now())", role="pmzilla_knowledge")
        c.rollback()

    def test_migration_rejouee_sans_effet(self):
        c = self.conn()
        etat = db.migrer(c, db.lister_migrations(db.DOSSIER_MIGRATIONS))
        c.commit()
        self.assertEqual(getattr(etat, "en_attente", []) or [], [])

    # -- 1.2 : droits --------------------------------------------------------

    def test_role_lecture_ecriture_ecrit_et_ne_cree_rien(self):
        c = self.conn("pmzilla_knowledge")
        c.execute("INSERT INTO knowledge.watch_articles VALUES ('https://a.test/1', 'a.test', 'T', 'a.md', '2026-10-01', true, now(), false)")
        c.execute("UPDATE knowledge.watch_articles SET links_extracted = true")
        c.execute("INSERT INTO knowledge.triage_scores (file, url, embedding) VALUES ('a.md', 'https://a.test/1', %s::halfvec)", (VECTEUR,))
        c.execute("UPDATE knowledge.triage_scores SET location = 'excluded'")
        c.execute("INSERT INTO knowledge.triage_calibration (file, exported_at, verdict) VALUES ('a.md', now(), 'keep')")
        c.execute("DELETE FROM knowledge.triage_calibration")
        c.execute("DELETE FROM knowledge.triage_scores")
        c.execute("DELETE FROM knowledge.watch_articles")
        for table in sorted(TABLES_VEILLE):
            c.execute(f"SELECT count(*) FROM knowledge.{table}").fetchone()
        c.rollback()
        c.execute("SET ROLE pmzilla_knowledge")
        self.refuse(c, "CREATE TABLE knowledge.pirate (x int)", role="pmzilla_knowledge")
        for table in sorted(TABLES_VEILLE):
            with self.subTest(table=table):
                self.refuse(c, f"ALTER TABLE knowledge.{table} ADD COLUMN pirate int", role="pmzilla_knowledge")
                self.refuse(c, f"DROP TABLE knowledge.{table}", role="pmzilla_knowledge")

    def test_role_de_lecture_lit_et_ne_peut_pas_ecrire(self):
        c = self.conn("pmzilla_knowledge")
        c.execute("INSERT INTO knowledge.triage_scores (file, url, embedding) VALUES ('a.md', 'https://a.test/1', %s::halfvec)", (VECTEUR,))
        c.execute("INSERT INTO knowledge.triage_daily_picks VALUES ('2026-10-01', 'a.md')")
        c.commit()
        c.execute("RESET ROLE")
        c.execute("SET ROLE pmzilla_knowledge_ro")
        c.commit()
        for table in sorted(TABLES_VEILLE):
            with self.subTest(table=table):
                c.execute(f"SELECT count(*) FROM knowledge.{table}").fetchone()
        self.refuse(c, "INSERT INTO knowledge.triage_scores (file, url, embedding) VALUES ('b.md', 'u', %s::halfvec)", (VECTEUR,),
                    role="pmzilla_knowledge_ro")
        self.refuse(c, "DELETE FROM knowledge.triage_daily_picks", role="pmzilla_knowledge_ro")
        self.refuse(c, "UPDATE knowledge.triage_scores SET location = 'x'", role="pmzilla_knowledge_ro")
        self.refuse(c, "CREATE TABLE knowledge.pirate (x int)", role="pmzilla_knowledge_ro")
        self.refuse(c, "DROP TABLE knowledge.triage_scores", role="pmzilla_knowledge_ro")

    def test_roles_des_autres_schemas_refuses(self):
        for role in ("pmzilla_cases", "pmzilla_cases_ro", "pmzilla_flow", "pmzilla_flow_ro", "pmzilla_flow_views"):
            c = self.conn(role)
            for table in sorted(TABLES_VEILLE):
                with self.subTest(role=role, table=table):
                    self.refuse(c, f"SELECT count(*) FROM knowledge.{table}", role=role)


if __name__ == "__main__":
    unittest.main()
