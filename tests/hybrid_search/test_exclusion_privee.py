"""
L'exclusion des collections privées dans la recherche (organisation-context, design D5) : tools/hybrid_search.py, option
`exclude_collections`. Sans base : le SQL construit.

    bash tests/run_all.sh hybrid_search
"""
import dataclasses
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "library_backend"))
import pg_demo                  # noqa: E402,F401  (ajoute tools/ au chemin)
import hybrid_search as hs      # noqa: E402

TODAY = dt.date(2026, 7, 1)


def construire(spec=hs.LIBRARY_SPEC, **options):
    return hs.build_query(spec, query="le flux", vector=[0.5, 0.25], today=TODAY, **options)


class Exclusion(unittest.TestCase):
    def test_sans_exclusion_le_sql_ne_change_pas(self):
        sql, params = construire()
        self.assertNotIn("excluded", sql)
        self.assertNotIn("excluded", params)
        self.assertEqual(construire(exclude_collections=None)[0], sql)
        self.assertEqual(construire(exclude_collections=[])[0], sql)

    def test_exclusion_dans_la_portee_et_dans_la_requete_plein_texte(self):
        sql, params = construire(exclude_collections=["contexte"])
        self.assertEqual(params["excluded"], ["contexte"])
        self.assertIn("NOT EXISTS (SELECT 1 FROM knowledge.book_collections", sql)
        self.assertEqual(sql.count("co.name = ANY(%(excluded)s::text[])"), 2)         # portée sémantique et liste des livres du plein texte

    def test_exclusion_et_collection_nommee_se_combinent(self):
        sql, params = construire(collections=["watch"], exclude_collections=["contexte"], since="2026-01-01")
        self.assertEqual((params["collections"], params["excluded"]), (["watch"], ["contexte"]))
        self.assertIn("%(since)s", sql)

    def test_specification_sans_exclusion_ignore_l_option(self):
        spec = dataclasses.replace(hs.LIBRARY_SPEC, collection_exclusion=None)
        sql, params = construire(spec, exclude_collections=["contexte"])
        self.assertNotIn("excluded", params)
        self.assertNotIn("%(excluded)s", sql)

    def test_aucune_valeur_n_est_interpolee(self):
        sql, _ = construire(exclude_collections=["contexte"])
        self.assertNotIn("'contexte'", sql)


if __name__ == "__main__":
    unittest.main()
