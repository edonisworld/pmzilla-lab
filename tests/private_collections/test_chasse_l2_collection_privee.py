"""Reproduction du constat L2 sur knowledge_library (audit-kraken/lots/L2-L4.md, partie L2, moyenne) : `read(passage_id)` et `books(None)` atteignent la
collection privée sans qu'on la nomme (la recherche, elle, l'exclut sans collection nommée).

Test de l'audit #629, groupe O4, attendu vert. Aucune base : `_query` et `_describe_many` sont remplacés par des
lignes inventées.
"""
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import knowledge_library  # noqa: E402
import private_collections  # noqa: E402

PRIVEE = next(iter(private_collections.PRIVATE_COLLECTIONS))


def bibliotheque():
    biblio = knowledge_library.PostgresLibrary(connect=lambda: object())

    def requete(sql, params=()):
        if "FROM knowledge.books b" in sql and "GROUP BY" in sql:
            return [("Note fictive", "2026-01-01-note-fictive.md", [PRIVEE], 3, 0), ("Livre fictif", "livre-fictif.md", ["produit"], 10, 0)]
        if "WHERE id = %s" in sql:
            return [(1, 0)]
        return [(1,)]

    biblio._query = requete
    biblio._describe_many = lambda ids: {i: {"id": i, "position": 0, "section": "s", "text": "texte fictif", "kind": "text", "ref": None,
                                             "title": "Note fictive", "file": "2026-01-01-note-fictive.md",
                                             "meta": {"review_date": "2027-01-01"}, "names": [PRIVEE]} for i in ids}
    return biblio


class ChasseL2CollectionPrivee(unittest.TestCase):
    def test_L2_03_books_sans_collection_n_atteint_pas_la_collection_privee(self):
        livres = bibliotheque().books(None)
        self.assertEqual([l for l in livres if PRIVEE in l["collections"]], [], "books(None) liste un livre de la collection privée")

    def test_L2_03_read_d_un_passage_prive_est_refuse_sans_nommer_la_collection(self):
        resultat = bibliotheque().read(1, 0, 0)
        self.assertTrue("error" in resultat or not resultat.get("passages"), "read(passage_id) rend le texte d'une note privée sans la nommer")


if __name__ == "__main__":
    unittest.main()
