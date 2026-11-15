"""
`read_passage` et la collection privée (décision R-20261107-33, audit #629) : un passage d'une collection privée ne se lit que si l'appel
nomme cette collection, comme la recherche. Sans base, sans Ollama, sans paquet `mcp` : lignes inventées, faux FastMCP.

    bash tests/run_all.sh library_backend
"""
import sys
import unittest
from unittest import mock

import pg_demo                  # noqa: F401  (ajoute tools/, tests/db et tests/fixtures_library au chemin)
import knowledge_library as kl  # noqa: E402
import pmzilla_lab_library as library  # noqa: E402
import private_collections      # noqa: E402
from aides_serveur import FauxFastMCP, modules_mcp  # noqa: E402

PRIVEE = private_collections.CONTEXT_COLLECTION


def ligne(identifiant, position, noms, texte):
    return {"id": identifiant, "position": position, "section": "S", "text": texte, "kind": "text", "ref": {},
            "title": "Titre inventé", "file": "fichier-invente.md", "meta": {}, "names": noms}


def bibliotheque(noms, positions=(0, 1, 2)):
    """Un livre inventé de trois passages (identifiants 10, 11, 12), tous dans les collections `noms`."""
    lib = kl.PostgresLibrary(connect=lambda: object())
    ids = [10 + p for p in positions]

    def requete(sql, params=()):
        if "WHERE id = %s" in sql:
            return [(1, 1)]
        return [(i,) for i in ids]
    lib._query = requete
    lib._describe_many = lambda wanted: {i: ligne(i, i - 10, noms, f"texte inventé {i}") for i in wanted}
    return lib


class LectureDirecte(unittest.TestCase):
    def test_un_passage_prive_est_refuse_sans_collection_nommee(self):
        for nommees in (None, [], ["produit"]):
            with self.subTest(collections=nommees):
                lu = bibliotheque([PRIVEE]).read(11, 1, 1, nommees)
                self.assertEqual(list(lu), ["error"])
                self.assertEqual(lu, self.inconnu(11))

    def inconnu(self, identifiant):
        lib = bibliotheque(["flow"])
        lib._query = lambda sql, params=(): []
        return lib.read(identifiant, 1, 1)

    def test_le_refus_prive_et_l_identifiant_inconnu_ont_exactement_le_meme_message(self):
        """Revue du commit f8cb0ee4 : l'erreur ne dit pas qu'un identifiant existe et appartient à une collection privée."""
        self.assertEqual(bibliotheque([PRIVEE]).read(11, 0, 0), self.inconnu(11))
        self.assertEqual(bibliotheque([PRIVEE]).read(11, 0, 0, ["produit"]), self.inconnu(11))
        self.assertNotIn("private", str(bibliotheque([PRIVEE]).read(11, 0, 0)).lower())

    def test_le_refus_ne_laisse_rien_du_contenu(self):
        lu = bibliotheque([PRIVEE]).read(11, 1, 1)
        for secret in ("texte inventé", "Titre inventé", "fichier-invente.md", "passages", "book", "file"):
            self.assertNotIn(secret, str(lu))

    def test_un_passage_prive_se_lit_quand_la_collection_est_nommee(self):
        lu = bibliotheque([PRIVEE]).read(11, 1, 1, [PRIVEE])
        self.assertNotIn("error", lu)
        self.assertEqual([p["passage_id"] for p in lu["passages"]], [10, 11, 12])

    def test_nommer_une_autre_collection_en_plus_de_la_privee_suffit(self):
        self.assertNotIn("error", bibliotheque([PRIVEE]).read(11, 0, 0, ["produit", PRIVEE]))

    def test_un_livre_dans_une_collection_privee_et_une_autre_exige_la_privee(self):
        self.assertIn("error", bibliotheque(["produit", PRIVEE]).read(11, 0, 0, ["produit"]))
        self.assertNotIn("error", bibliotheque(["produit", PRIVEE]).read(11, 0, 0, [PRIVEE]))

    def test_les_autres_collections_ne_changent_pas(self):
        for nommees in (None, [], ["flow"], ["produit"]):
            with self.subTest(collections=nommees):
                lu = bibliotheque(["flow"]).read(11, 1, 1, nommees)
                self.assertNotIn("error", lu)
                self.assertEqual([p["passage_id"] for p in lu["passages"]], [10, 11, 12])
                self.assertEqual(sorted(lu), ["book", "file", "passages"])

    def test_les_voisins_ne_font_pas_fuiter_un_passage_prive(self):
        """Un passage public dont un voisin serait privé : aucun texte ne sort, ni du passage demandé ni du voisin."""
        lib = bibliotheque(["flow"])
        mixte = {10: ligne(10, 0, ["flow"], "public inventé"), 11: ligne(11, 1, ["flow"], "public inventé 2"),
                 12: ligne(12, 2, [PRIVEE], "voisin privé inventé")}
        lib._describe_many = lambda wanted: {i: mixte[i] for i in wanted}
        lu = lib.read(11, 5, 5)
        self.assertEqual(list(lu), ["error"])
        self.assertNotIn("voisin privé inventé", str(lu))
        self.assertNotIn("public inventé", str(lu))

    def test_les_voisins_demandes_d_un_passage_prive_nomme_restent_ceux_du_meme_livre(self):
        lu = bibliotheque([PRIVEE]).read(11, 5, 5, [PRIVEE])
        self.assertEqual({p["passage_id"] for p in lu["passages"]}, {10, 11, 12})

    def test_un_identifiant_inconnu_garde_son_erreur(self):
        lib = bibliotheque(["flow"])
        lib._query = lambda sql, params=(): []
        self.assertIn("Unknown passage_id", lib.read(99, 0, 0)["error"])


class FausseBibliotheque:
    def __init__(self):
        self.lectures = []

    def collections(self):
        return {"produit": 1, PRIVEE: 1}

    def read(self, passage_id, before, after, collections=None):
        self.lectures.append((passage_id, before, after, collections))
        return {"passage_id": passage_id}


class OutilMcp(unittest.TestCase):
    def outils(self):
        faux = FausseBibliotheque()
        with mock.patch.dict(sys.modules, modules_mcp()), mock.patch.object(library, "open_library", return_value=faux):
            library.serve()
        return FauxFastMCP.instance.tools, faux

    def test_sans_collection_l_appel_est_celui_d_avant(self):
        outils, faux = self.outils()
        outils["read_passage"](4, before=-3, after=99)
        self.assertEqual(faux.lectures, [(4, 0, 5, None)])

    def test_la_collection_nommee_est_transmise(self):
        outils, faux = self.outils()
        outils["read_passage"](4, collections=[PRIVEE])
        self.assertEqual(faux.lectures, [(4, 1, 2, [PRIVEE])])

    def test_une_collection_inconnue_est_refusee_sans_lecture(self):
        outils, faux = self.outils()
        self.assertIn("Unknown collections", outils["read_passage"](4, collections=["inexistante"])["error"])
        self.assertEqual(faux.lectures, [])

    def test_la_description_dit_que_la_collection_privee_se_lit_nommee(self):
        outils, _ = self.outils()
        texte = outils["read_passage"].__doc__
        self.assertIn(f'"{PRIVEE}"', texte)
        self.assertIn("names that collection in `collections`", texte)
        self.assertIn("collections", outils["read_passage"].__annotations__)


if __name__ == "__main__":
    unittest.main()
