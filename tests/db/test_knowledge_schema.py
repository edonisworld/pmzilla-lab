"""
Tests de la migration 0004 (schéma knowledge, lot 4) sur une base jetable pmzilla_test_<hex>, et de la bibliothèque inventée commune.

    uv run --with "psycopg[binary]" --with numpy --with httpx python -m unittest discover -s tests/db -v

Les tests avec base ne touchent que la base jetable (créée puis supprimée dans tous les cas), jamais les schémas réels ; ils sont
sautés si la base manque. Aucune donnée réelle : documents et vecteurs inventés (tests/fixtures_library/demo_library.py).
"""
import contextlib
import json
import secrets
import sys
import unittest
from pathlib import Path

import test_db as base          # noqa: E402  (même dossier : connexion, base jetable, mot de passe)
from test_db import db          # noqa: E402

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tests" / "fixtures_library"))
import demo_library as demo     # noqa: E402

from test_watch_schema import TABLES_VEILLE     # noqa: E402

TABLES = {"books", "collections", "book_collections", "chunks"}


class SchemaKnowledge(unittest.TestCase):
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

    def inserer_jeu(self, c):
        c.execute("SET ROLE pmzilla_knowledge")
        c.execute("INSERT INTO knowledge.collections (name) VALUES ('flow'), ('watch')")
        c.execute("INSERT INTO knowledge.books (file_name, title, meta, sha256, model, indexed_at) VALUES "
                  "('a.md', 'Livre A', %s, 'abc', 'bge-m3', now()), ('b.md', 'Billet B', %s, 'def', 'bge-m3', now())",
                  (json.dumps({"author": "Auteur Fictif"}), json.dumps({"author": "Blog", "published": "2026-10-01T08:00:00", "url": "https://exemple.test/b"})))
        c.execute("INSERT INTO knowledge.book_collections VALUES (1, 1), (2, 2)")
        vecteur = "[" + ",".join(["1"] + ["0"] * 1023) + "]"
        c.execute("INSERT INTO knowledge.chunks (book_id, position, section, text, embedding) VALUES "
                  "(1, 0, 'Partie 1 > Équipe', 'Le délai et l''équipe se mesurent', %s::halfvec), "
                  "(2, 0, 'Intro', 'Une prévision honnête', %s::halfvec)", (vecteur, vecteur))
        c.execute("RESET ROLE")
        c.commit()

    def test_tables_colonnes_et_index(self):
        c = self.conn()
        noms = {r[0] for r in c.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                                        "WHERE n.nspname = 'knowledge' AND c.relkind = 'r'")}
        self.assertEqual(noms, TABLES | TABLES_VEILLE)      # les quatre tables de la bibliothèque et les onze de la veille (0007)
        colonnes = {r[0]: r[1] for r in c.execute("SELECT column_name, data_type FROM information_schema.columns "
                                                  "WHERE table_schema = 'knowledge' AND table_name = 'chunks'")}
        self.assertEqual(colonnes["embedding"], "USER-DEFINED")
        self.assertEqual(colonnes["search_vector"], "tsvector")
        self.assertEqual(colonnes["ref"], "jsonb")
        index = {r[0] for r in c.execute("SELECT indexname FROM pg_indexes WHERE schemaname = 'knowledge'")}
        self.assertLessEqual({"chunks_embedding_hnsw", "chunks_search_vector", "chunks_book_position", "chunks_kind", "books_sha256"}, index)
        proprietaires = {r[0] for r in c.execute("SELECT DISTINCT tableowner FROM pg_tables WHERE schemaname = 'knowledge'")}
        self.assertEqual(proprietaires, {"pmzilla_owner"})

    def test_plein_texte_sans_accent_et_colonnes_generees(self):
        c = self.conn()
        self.inserer_jeu(c)
        # « équipe » et « equipe » se retrouvent : même jeton après unaccent
        trouves = c.execute("SELECT book_id FROM knowledge.chunks WHERE search_vector @@ to_tsquery('simple', 'equipe')").fetchall()
        self.assertEqual(trouves, [(1,)])
        # la recherche ignore la casse (comme FTS5) : la configuration `simple` met les mots en minuscules, dans le document
        # comme dans la requête, et unaccent ôte l'accent de la majuscule
        trouves = c.execute("SELECT book_id FROM knowledge.chunks WHERE search_vector @@ to_tsquery('simple', knowledge.immutable_unaccent('ÉQUIPE'))").fetchall()
        self.assertEqual(trouves, [(1,)])
        trouves = c.execute("SELECT book_id FROM knowledge.chunks WHERE search_vector @@ to_tsquery('simple', 'EQUIPE')").fetchall()
        self.assertEqual(trouves, [(1,)])
        ligne = c.execute("SELECT author, published_on FROM knowledge.books ORDER BY id").fetchall()
        self.assertEqual(ligne, [("Auteur Fictif", None), ("Blog", "2026-10-01")])

    def test_index_bm25_accents_casse_et_score(self):
        """Migration 0005 : index BM25 sur fts_text (section + texte), tokenizer simple avec ascii_folding : minuscules, sans accents, sans racinisation."""
        c = self.conn()
        self.inserer_jeu(c)
        colonne = c.execute("SELECT is_generated FROM information_schema.columns WHERE table_schema = 'knowledge' AND table_name = 'chunks' "
                            "AND column_name = 'fts_text'").fetchone()
        self.assertEqual(colonne, ("ALWAYS",))
        definition = c.execute("SELECT indexdef FROM pg_indexes WHERE schemaname = 'knowledge' AND indexname = 'chunks_bm25'").fetchone()[0]
        self.assertIn("fts_text", definition)
        for question in ("equipe", "ÉQUIPE", "équipe"):
            with self.subTest(question=question):
                self.assertEqual(c.execute("SELECT id FROM knowledge.chunks WHERE fts_text ||| %s", (question,)).fetchall(), [(1,)])
        self.assertEqual(c.execute("SELECT id FROM knowledge.chunks WHERE fts_text ||| 'equipe previsions'").fetchall(), [(1,)])   # OU : au moins un mot
        self.assertEqual(c.execute("SELECT id FROM knowledge.chunks WHERE fts_text ||| 'equipes'").fetchall(), [])                # pas de racinisation
        scores = c.execute("SELECT id, pdb.score(id) FROM knowledge.chunks WHERE fts_text ||| 'equipe delai' ORDER BY pdb.score(id) DESC LIMIT 5").fetchall()
        self.assertEqual([i for i, _ in scores], [1])
        self.assertGreater(scores[0][1], 0)

    def test_le_role_de_lecture_peut_chercher_en_bm25(self):
        c = self.conn()
        self.inserer_jeu(c)
        c.execute("SET ROLE pmzilla_knowledge_ro")
        lignes = c.execute("SELECT id, pdb.score(id) FROM knowledge.chunks WHERE fts_text ||| 'equipe' ORDER BY pdb.score(id) DESC LIMIT 5").fetchall()
        self.assertEqual([i for i, _ in lignes], [1])
        c.rollback()

    def test_kind_contraint_et_suppression_en_cascade(self):
        c = self.conn()
        self.inserer_jeu(c)
        with self.assertRaises(Exception):
            c.execute("SET ROLE pmzilla_knowledge")
            c.execute("INSERT INTO knowledge.chunks (book_id, position, section, text, embedding, kind) VALUES "
                      "(1, 9, 's', 't', %s::halfvec, 'texte')", ("[" + ",".join(["1"] + ["0"] * 1023) + "]",))
        c.rollback()
        c.execute("SET ROLE pmzilla_knowledge")
        c.execute("DELETE FROM knowledge.books WHERE id = 1")
        self.assertEqual(c.execute("SELECT count(*) FROM knowledge.chunks").fetchone()[0], 1)
        self.assertEqual(c.execute("SELECT count(*) FROM knowledge.book_collections").fetchone()[0], 1)
        c.rollback()

    def test_droits_du_role_d_acces_et_du_role_de_lecture(self):
        c = self.conn()
        self.inserer_jeu(c)
        c.execute("SET ROLE pmzilla_knowledge_ro")
        self.assertEqual(c.execute("SELECT count(*) FROM knowledge.chunks").fetchone()[0], 2)
        for ordre in ("INSERT INTO knowledge.collections (name) VALUES ('x')", "DELETE FROM knowledge.chunks",
                      "CREATE TABLE knowledge.pirate (x int)"):
            with self.subTest(ordre=ordre):
                with self.assertRaises(Exception):
                    c.execute(ordre)
                c.rollback()
                c.execute("SET ROLE pmzilla_knowledge_ro")
        c.rollback()
        c.execute("SET ROLE pmzilla_knowledge")
        with self.assertRaises(Exception):
            c.execute("CREATE TABLE knowledge.pirate (x int)")
        c.rollback()

    def test_migration_rejouee_sans_effet(self):
        c = self.conn()
        etat = db.migrer(c, db.lister_migrations(db.DOSSIER_MIGRATIONS))
        c.commit()
        self.assertEqual(getattr(etat, "en_attente", []) or [], [])

    def test_aucune_donnee_dans_les_tables_apres_migration(self):
        c = self.conn()
        for table in TABLES:
            self.assertEqual(c.execute(f"SELECT count(*) FROM knowledge.{table}").fetchone()[0], 0)


class SansBase(unittest.TestCase):
    def test_migration_0004_presente_sans_donnee_ni_mot_de_passe(self):
        noms = [m.nom for m in db.lister_migrations()]
        self.assertIn("0004_knowledge_library.sql", noms)
        texte = (db.DOSSIER_MIGRATIONS / "0004_knowledge_library.sql").read_text(encoding="utf-8")
        self.assertNotRegex(texte, r"(?im)^\s*INSERT\s+INTO")
        self.assertNotRegex(texte, r"(?i)password\s+'")
        self.assertRegex(texte.splitlines()[0], r"^-- Schéma touché : knowledge")

    def test_roles_de_lecture_limitee_et_leur_trousseau(self):
        self.assertEqual(db.ROLES_AVEC_MOT_DE_PASSE,
                         ("pmzilla_flow_views", "pmzilla_knowledge_ro", "pmzilla_cases_ro", "pmzilla_cases"))
        self.assertEqual(db.service_du_role("pmzilla_knowledge_ro"), "pmzilla-lab-db-pmzilla_knowledge_ro")

    def test_migration_0005_presente_sans_donnee_et_documentee(self):
        texte = (db.DOSSIER_MIGRATIONS / "0005_knowledge_bm25.sql").read_text(encoding="utf-8")
        self.assertNotRegex(texte, r"(?im)^\s*INSERT\s+INTO")
        self.assertRegex(texte.splitlines()[0], r"^-- Schéma touché : knowledge")
        self.assertIn("pdb.simple('ascii_folding=true')", texte)
        self.assertIn("SET LOCAL max_parallel_maintenance_workers = 0;", texte)
        self.assertLess(texte.index("max_parallel_maintenance_workers"), texte.index("CREATE INDEX"))      # avant la construction de l'index
        self.assertIn("unicode61", texte)                 # l'équivalence avec FTS5 est écrite dans la migration
        self.assertIn("remove_diacritics", texte)

    def test_bibliotheque_inventee_coherente(self):
        comptes = demo.expected_counts()
        self.assertEqual(comptes["books"], 5)
        self.assertEqual(comptes["chunks"], 14)
        self.assertEqual(comptes["figures"], 2)
        for nom, titre_meta in ((n, b) for n, b in demo.BOOKS.items()):
            self.assertTrue(any(c[0] == nom for c in demo.CHUNKS), nom)
        self.assertEqual(demo.fake_embed(["le flux"]).shape, (1, 1024))


if __name__ == "__main__":
    unittest.main()
