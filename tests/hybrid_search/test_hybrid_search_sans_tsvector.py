"""
Tests de tools/hybrid_search.py : spécification sans colonne plein-texte héritée (db-lot2, groupe 1).

    bash tests/run_all.sh hybrid_search

Sans base : le SQL de LIBRARY_SPEC est comparé au texte d'avant le changement ; une spécification sans `tsvector_expr` est
construite et le plein texte « tsvector » refusé. Avec une base jetable (sautée si elle manque) : la même spécification
est jouée en BM25 sur la bibliothèque inventée.
"""
import dataclasses
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "library_backend"))
import pg_demo                  # noqa: E402  (ajoute tools/, tests/db et tests/fixtures_library au chemin)
import demo_library as demo     # noqa: E402
import hybrid_search as hs      # noqa: E402

TODAY = dt.date(2026, 7, 1)

# Texte SQL de LIBRARY_SPEC relevé AVANT la modification de hybrid_search.py (requête « le flux », vecteur [0.5, 0.25], today = 2026-07-01).
SQL_OPTIONS_PAR_DEFAUT = "\nWITH scope AS NOT MATERIALIZED (\n    SELECT c.id AS id, c.embedding AS vec, c.search_vector AS tsv,\n           (CASE WHEN b.published_on IS NULL OR b.published_on !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' OR NOT (ARRAY(SELECT CASE co.name WHEN 'veille' THEN 'watch' ELSE co.name END FROM knowledge.book_collections bc JOIN knowledge.collections co ON co.id = bc.collection_id WHERE bc.book_id = b.id) && ARRAY['watch']::text[]) OR '@OWN@' = ANY(ARRAY(SELECT CASE co.name WHEN 'veille' THEN 'watch' ELSE co.name END FROM knowledge.book_collections bc JOIN knowledge.collections co ON co.id = bc.collection_id WHERE bc.book_id = b.id)) THEN 0.0005 ELSE 0.001 * power(0.5::float8, GREATEST(0, (%(today)s::date - (b.published_on)::date))::float8 / 180.0) END) AS fresh\n    FROM knowledge.chunks c JOIN knowledge.books b ON b.id = c.book_id\n    \n),\nsem AS (\n    SELECT id, rank FROM (\n        SELECT id, row_number() OVER (ORDER BY round(score::numeric, 3) DESC, fresh DESC, id) - 1 AS rank\n        FROM (SELECT id, fresh, -(vec <#> %(qvec)s::halfvec) AS score FROM scope ORDER BY vec <=> %(qvec)s::halfvec LIMIT 50) t\n    ) r WHERE rank < 50\n),\nhits AS (\n    SELECT c.id AS id, pdb.score(c.id) AS raw\n    FROM knowledge.chunks c\n    WHERE c.fts_text ||| %(bm25_query)s\n    ORDER BY pdb.score(c.id) DESC\n    LIMIT 200\n),\nkw AS (\n    SELECT id, rank FROM (\n        SELECT s.id, row_number() OVER (ORDER BY round(h.raw::numeric, 3) DESC, s.fresh DESC, s.id) - 1 AS rank\n        FROM hits h JOIN scope s ON s.id = h.id\n    ) r WHERE rank < 50\n),\nfused AS (\n    SELECT id, sum(1.0::float8 / (60 + rank + 1)) AS rrf\n    FROM (SELECT id, rank FROM sem UNION ALL SELECT id, rank FROM kw) u\n    GROUP BY id\n)\nSELECT f.id, f.rrf + s.fresh AS score\nFROM fused f JOIN scope s ON s.id = f.id\nLEFT JOIN sem ON sem.id = f.id\nLEFT JOIN kw ON kw.id = f.id\nORDER BY score DESC, sem.rank ASC NULLS LAST, kw.rank ASC NULLS LAST, f.id\nLIMIT 8\n"

# Une collection, une borne de date, le type de passage « figure ». Seule la requête `hits` du plein texte a changé depuis (change filter-before-keyword-limit :
# la liste des livres de la collection et de la date, avant la limite de 200) ; le reste du texte est celui d'avant.
SQL_COLLECTION_DATE_FIGURE = "\nWITH scope AS NOT MATERIALIZED (\n    SELECT c.id AS id, c.embedding AS vec, c.search_vector AS tsv,\n           (CASE WHEN b.published_on IS NULL OR b.published_on !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' OR NOT (ARRAY(SELECT CASE co.name WHEN 'veille' THEN 'watch' ELSE co.name END FROM knowledge.book_collections bc JOIN knowledge.collections co ON co.id = bc.collection_id WHERE bc.book_id = b.id) && ARRAY['watch']::text[]) OR '@OWN@' = ANY(ARRAY(SELECT CASE co.name WHEN 'veille' THEN 'watch' ELSE co.name END FROM knowledge.book_collections bc JOIN knowledge.collections co ON co.id = bc.collection_id WHERE bc.book_id = b.id)) THEN 0.0005 ELSE 0.001 * power(0.5::float8, GREATEST(0, (%(today)s::date - (b.published_on)::date))::float8 / 180.0) END) AS fresh\n    FROM knowledge.chunks c JOIN knowledge.books b ON b.id = c.book_id\n    WHERE EXISTS (SELECT 1 FROM knowledge.book_collections bc JOIN knowledge.collections co ON co.id = bc.collection_id WHERE bc.book_id = b.id AND co.name = ANY(%(collections)s::text[])) AND (b.published_on IS NULL OR b.published_on >= %(since)s) AND c.kind = ANY(%(kinds)s::text[])\n),\nsem AS (\n    SELECT id, rank FROM (\n        SELECT id, row_number() OVER (ORDER BY round(score::numeric, 3) DESC, fresh DESC, id) - 1 AS rank\n        FROM (SELECT id, fresh, -(vec <#> %(qvec)s::halfvec) AS score FROM scope ORDER BY vec <=> %(qvec)s::halfvec LIMIT 50) t\n    ) r WHERE rank < 50\n),\nhits AS (\n    SELECT c.id AS id, pdb.score(c.id) AS raw\n    FROM knowledge.chunks c\n    WHERE c.fts_text ||| %(bm25_query)s AND c.kind = ANY(%(kinds)s::text[]) AND c.book_id IN (SELECT b.id FROM knowledge.books b WHERE EXISTS (SELECT 1 FROM knowledge.book_collections bc JOIN knowledge.collections co ON co.id = bc.collection_id WHERE bc.book_id = b.id AND co.name = ANY(%(collections)s::text[])) AND (b.published_on IS NULL OR b.published_on >= %(since)s))\n    ORDER BY pdb.score(c.id) DESC\n    LIMIT 200\n),\nkw AS (\n    SELECT id, rank FROM (\n        SELECT s.id, row_number() OVER (ORDER BY round(h.raw::numeric, 3) DESC, s.fresh DESC, s.id) - 1 AS rank\n        FROM hits h JOIN scope s ON s.id = h.id\n    ) r WHERE rank < 50\n),\nfused AS (\n    SELECT id, sum(1.0::float8 / (60 + rank + 1)) AS rrf\n    FROM (SELECT id, rank FROM sem UNION ALL SELECT id, rank FROM kw) u\n    GROUP BY id\n)\nSELECT f.id, f.rrf + s.fresh AS score\nFROM fused f JOIN scope s ON s.id = f.id\nLEFT JOIN sem ON sem.id = f.id\nLEFT JOIN kw ON kw.id = f.id\nORDER BY score DESC, sem.rank ASC NULLS LAST, kw.rank ASC NULLS LAST, f.id\nLIMIT 8\n"


def _construire(spec, **options):
    return hs.build_query(spec, query="le flux", vector=[0.5, 0.25], today=TODAY, **options)


SPEC_SANS_TSVECTOR = dataclasses.replace(hs.LIBRARY_SPEC, tsvector_expr=None)


class RequeteDeLaBibliothequeInchangee(unittest.TestCase):
    def test_sql_par_defaut_identique(self):
        sql, _ = _construire(hs.LIBRARY_SPEC)
        self.assertEqual(sql, SQL_OPTIONS_PAR_DEFAUT.replace("@OWN@", hs.OWN_COLLECTION))

    def test_sql_collection_date_et_figure_identique_sauf_la_liste_des_livres_du_plein_texte(self):
        sql, _ = _construire(hs.LIBRARY_SPEC, collections=["flow"], since="2026-01-01", kinds=["figure"])
        self.assertEqual(sql, SQL_COLLECTION_DATE_FIGURE.replace("@OWN@", hs.OWN_COLLECTION))


class SpecificationSansTsvector(unittest.TestCase):
    def test_valeur_par_defaut_et_ordre_des_champs(self):
        spec = hs.HybridSpec(from_sql="t x", id_expr="x.id", vector_expr="x.v")
        self.assertIsNone(spec.tsvector_expr)
        self.assertEqual(hs.LIBRARY_SPEC.tsvector_expr, "c.search_vector")

    def test_portee_avec_tsv_nul(self):
        sql, _ = _construire(SPEC_SANS_TSVECTOR)
        self.assertIn("NULL::tsvector AS tsv", sql)
        self.assertNotIn("search_vector", sql)

    def test_plein_texte_tsvector_refuse(self):
        with self.assertRaises(ValueError):
            _construire(SPEC_SANS_TSVECTOR, fulltext="tsvector")

    def test_bm25_construit(self):
        sql, params = _construire(SPEC_SANS_TSVECTOR, fulltext="bm25")
        self.assertIn("|||", sql)
        self.assertNotIn("ts_rank_cd", sql)
        self.assertIn("bm25_query", params)


class SpecificationSansTsvectorAvecBase(unittest.TestCase):
    """Jouée sur la bibliothèque inventée d'une base jetable (sautée sans base)."""

    def setUp(self):
        self.pg = pg_demo.ThrowawayDatabase(self)
        self.conn = self.pg.connect()

    def test_bm25_rend_les_memes_resultats_qu_avec_la_colonne(self):
        vecteur = demo.fake_embed(["le flux de travail"])[0]
        options = dict(query="le flux de travail", vector=vecteur, today=TODAY, limit=8, kinds=["text"])
        sans = hs.hybrid_search(self.conn, SPEC_SANS_TSVECTOR, **options)
        avec = hs.hybrid_search(self.conn, hs.LIBRARY_SPEC, **options)
        self.assertTrue(sans)
        self.assertEqual(sans, avec)


if __name__ == "__main__":
    unittest.main()
