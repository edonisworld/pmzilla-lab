"""
Section bibliothèque du tableau de bord sur une base jetable chargée avec la bibliothèque inventée (pg_demo).

    bash tools/dbtest.sh dashboard

Sautée sans base. Le lecteur réel (`fetch_library_books`) lit sous le rôle pmzilla_knowledge_ro ; aucune base réelle n'est jointe.
"""
import datetime as dt
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tests" / "library_backend"))
import pg_demo                  # noqa: E402  (ajoute tools/, tests/db et tests/fixtures_library au chemin)
import dashboard                # noqa: E402
import watch_paths              # noqa: E402


class BibliothequeSurBaseJetable(unittest.TestCase):
    def setUp(self):
        self.base = pg_demo.ThrowawayDatabase(self)      # saute le test sans base
        dashboard.set_language("fr")

    def test_lecteur_compte_les_livres_et_exclut_veille_et_collection_personnelle(self):
        rows = dashboard.fetch_library_books(connect=self.base.connect)
        self.assertEqual(len(rows), len(pg_demo.demo.BOOKS))
        livres = {name: meta for name, (title, coll, meta) in pg_demo.demo.BOOKS.items()
                  if not {"watch", "veille", watch_paths.OWN_COLLECTION} & set(coll.split("|"))}
        passages = sum(1 for chunk in pg_demo.demo.CHUNKS if chunk[0] in livres)
        html = dashboard.livres_block(lambda: rows)
        self.assertIn(f"<b>{len(livres)}</b> livres, {passages} passages", html)
        self.assertNotIn("billet", html.lower())
        articles = sum(1 for _, coll, _ in pg_demo.demo.BOOKS.values() if "watch" in coll.split("|"))
        self.assertIn(f"Articles de la veille sur {articles} : <b>0</b> sans auteur ni site, <b>0</b> affichés",
                      dashboard.articles_sans_auteur_block(lambda: rows))

    def test_comptes_de_la_veille_par_nom_exact_de_collection(self):
        veille = {name for name, (_, coll, _) in pg_demo.demo.BOOKS.items() if {"watch", "veille"} & set(coll.split("|"))}
        passages = sum(1 for chunk in pg_demo.demo.CHUNKS if chunk[0] in veille)
        self.assertEqual(dashboard.fetch_watch_counts(connect=self.base.connect), {"articles": len(veille), "passages": passages})
        self.assertIn(f"<b>{len(veille)}</b>", dashboard.veille_base_block(lambda: dashboard.fetch_watch_counts(connect=self.base.connect)))

    def test_partages_et_selections_sous_le_role_de_lecture(self):
        ecriture = self.base._raw()
        ecriture.execute("SET ROLE pmzilla_knowledge")
        ecriture.execute("INSERT INTO knowledge.triage_daily_picks VALUES ('2026-10-08', 'f1.md')")
        ecriture.execute("INSERT INTO knowledge.triage_shared VALUES ('f1.md', 'u1', '2026-10-09', '2026-10-10'), "
                         "('f2.md', 'u2', '2026-10-09', '2026-10-10'), ('f3.md', 'u3', '2026-09-01', '2026-09-02')")
        ecriture.commit()
        lu = dashboard.fetch_shares(dt.date(2026, 10, 12), connect=self.base.connect)
        self.assertEqual(lu, {"total": 3, "recent": 2, "first_pick": "2026-10-08", "evaluable": 2, "hits": 1})

    def test_partages_sans_selection(self):
        lu = dashboard.fetch_shares(dt.date(2026, 10, 12), connect=self.base.connect)
        self.assertEqual(lu, {"total": 0, "recent": 0, "first_pick": None, "evaluable": 0, "hits": 0})

    def test_auteur_derive_de_meta(self):
        rows = dashboard.fetch_library_books(connect=self.base.connect)
        auteurs = {row["title"]: row["author"] for row in rows}
        for title, _, meta in pg_demo.demo.BOOKS.values():
            self.assertEqual(auteurs[title], meta.get("author"))


if __name__ == "__main__":
    unittest.main()
