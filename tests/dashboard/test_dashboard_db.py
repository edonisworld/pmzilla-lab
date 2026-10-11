"""
Section bibliothèque du tableau de bord sur une base jetable chargée avec la bibliothèque inventée (pg_demo).

    bash tools/dbtest.sh dashboard

Sautée sans base. Le lecteur réel (`fetch_library_books`) lit sous le rôle pmzilla_knowledge_ro ; aucune base réelle n'est jointe.
"""
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

    def test_auteur_derive_de_meta(self):
        rows = dashboard.fetch_library_books(connect=self.base.connect)
        auteurs = {row["title"]: row["author"] for row in rows}
        for title, _, meta in pg_demo.demo.BOOKS.values():
            self.assertEqual(auteurs[title], meta.get("author"))


if __name__ == "__main__":
    unittest.main()
