"""
Test de bout en bout (base jetable, sauté sans mot de passe) du plein texte BM25 quand la collection ou la date écarte tous les meilleurs candidats.

    bash tools/dbtest.sh hybrid_search

Comportement voulu (change filter-before-keyword-limit) : la collection, la date et le type de passage s'appliquent AVANT la limite des 200 meilleurs
passages du plein texte (4 x CANDIDATES). Même si ces 200 sont tous hors collection (ou trop anciens), la liste plein texte contient les meilleurs
passages de la collection (ou de la période). Sans restriction, le résultat est celui d'avant. Remplace test_filtre_apres_limite.py, qui fixait
l'ancien comportement (liste vide).
"""
import datetime as dt
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tests" / "library_backend"))
import pg_demo                  # noqa: E402  (ajoute tools/, tests/db et tests/fixtures_library au chemin)
import demo_library as demo     # noqa: E402
import hybrid_search as hs      # noqa: E402

TODAY = dt.date.today()
MOT = "zorglub"      # mot inventé : absent de la bibliothèque inventée


class FiltreAvantLaLimite(unittest.TestCase):
    def setUp(self):
        self.pg = pg_demo.ThrowawayDatabase(self)
        brut = self.pg._raw()
        brut.execute("SET ROLE pmzilla_knowledge")
        bruit = brut.execute("INSERT INTO knowledge.collections (name) VALUES ('bruit') RETURNING id").fetchone()[0]
        produit = brut.execute("SELECT id FROM knowledge.collections WHERE name = 'produit'").fetchone()[0]
        vecteur = pg_demo.literal_of(demo.vector(0.9))

        def livre(nom, collection, date):
            identifiant = brut.execute(
                "INSERT INTO knowledge.books (file_name, title, meta, sha256, model, indexed_at) VALUES (%s, %s, jsonb_build_object('published', %s::text), 'x', 'bge-m3', now()) RETURNING id",
                (nom, nom, date)).fetchone()[0]
            brut.execute("INSERT INTO knowledge.book_collections VALUES (%s, %s)", (identifiant, collection))
            return identifiant

        def passage(livre_id, position, texte):
            brut.execute("INSERT INTO knowledge.chunks (book_id, position, section, text, embedding) VALUES (%s, %s, 'Début', %s, %s::halfvec)",
                         (livre_id, position, texte, vecteur))

        gros = livre("bruit.md", bruit, "2020-01-01")
        for position in range(4 * hs.CANDIDATES + 10):         # plus que la limite de 200 : ils occupent tout le haut du classement
            passage(gros, position, f"{MOT} {MOT} {MOT} {MOT}")
        self.cible = livre("cible.md", produit, "2026-05-01")
        passage(self.cible, 0, f"Un passage de la collection produit qui cite {MOT} une seule fois, au milieu d'un texte plus long que les autres.")
        brut.execute("RESET ROLE")
        brut.commit()
        self.conn = self.pg.connect()
        self.fichiers = dict(self.conn.execute("SELECT c.id, b.file_name FROM knowledge.chunks c JOIN knowledge.books b ON b.id = c.book_id").fetchall())
        self.conn.rollback()

    def chercher(self, **options):
        vecteur = demo.fake_embed([MOT])[0]
        trouves = hs.hybrid_search(self.conn, hs.LIBRARY_SPEC, query=MOT, vector=vecteur, today=TODAY, kinds=["text"], **options)
        return [self.fichiers[i] for i, _ in trouves]

    def test_sans_filtre_le_plein_texte_ne_rend_que_le_bruit(self):
        fichiers = self.chercher(limit=8, component="text")
        self.assertEqual(set(fichiers), {"bruit.md"})

    def test_collection_qui_ne_tient_aucun_des_meilleurs_passages_a_sa_liste_plein_texte(self):
        self.assertEqual(self.chercher(limit=8, component="text", collections=["produit"]), ["cible.md"])

    def test_date_qui_ecarte_tous_les_meilleurs_passages_garde_les_plus_recents(self):
        self.assertEqual(self.chercher(limit=8, component="text", since="2026-01-01"), ["cible.md"])

    def test_collection_et_date_ensemble(self):
        self.assertEqual(self.chercher(limit=8, component="text", collections=["produit"], since="2026-01-01"), ["cible.md"])
        self.assertEqual(self.chercher(limit=8, component="text", collections=["bruit"], since="2026-01-01"), [])       # bruit est trop ancien

    def test_collection_inconnue_liste_vide(self):
        self.assertEqual(self.chercher(limit=8, component="text", collections=["inconnue"]), [])

    def test_hybride_repond_quand_meme_depuis_la_collection_filtree(self):
        fichiers = self.chercher(limit=8, collections=["produit"])
        self.assertTrue(fichiers)
        self.assertNotIn("bruit.md", fichiers)
        livres_produit = {nom for (nom, _t, _c, _m) in demo_produit()}
        self.assertTrue(set(fichiers) <= livres_produit | {"cible.md"})


def demo_produit():
    """(fichier, titre, collections, meta) des livres de la bibliothèque inventée qui sont dans « produit »."""
    return [(f, t, c, m) for f, (t, c, m) in demo.BOOKS.items() if "produit" in c.split("|")]


if __name__ == "__main__":
    unittest.main()
