"""
Tests des garde-fous des outils MCP `search_library`, `read_passage`, `list_collections` et `list_books` de `serve()`
(collection inconnue, date invalide, bornes de taille, avertissements donnés une seule fois), et de `load_catalogue`.

    bash tests/run_all.sh pmzilla_lab_library

Sans base, sans Ollama, sans paquet `mcp` : faux FastMCP et fausse bibliothèque ; données inventées.
"""
import contextlib
import io
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import pmzilla_lab_library as library  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_pmzilla_lab_library as base  # noqa: E402


class FauxFastMCP:
    instance = None

    def __init__(self, name):
        self.tools = {}
        FauxFastMCP.instance = self

    def tool(self):
        def decorate(function):
            self.tools[function.__name__] = function
            return function
        return decorate

    def run(self):
        pass


class FausseBibliotheque:
    def __init__(self, erreur=None):
        self.erreur, self.appels, self.lectures = erreur, [], []

    def collections(self):
        return {"produit": 2, "watch": 1}

    def books(self, collection):
        return [{"file": "livre.md"}]

    def search(self, query, collections, limit, since, types):
        self.appels.append((query, collections, limit, since, types))
        if self.erreur:
            raise self.erreur
        return [{"passage_id": 1}]

    def read(self, passage_id, before, after):
        self.lectures.append((passage_id, before, after))
        return {"passage_id": passage_id}


class Garde(unittest.TestCase):
    def serveur(self, **options):
        bibliotheque = FausseBibliotheque(**options)
        modules = {"mcp": types.ModuleType("mcp"), "mcp.server": types.ModuleType("mcp.server"),
                   "mcp.server.fastmcp": types.ModuleType("mcp.server.fastmcp")}
        modules["mcp.server.fastmcp"].FastMCP = FauxFastMCP
        with mock.patch.dict(sys.modules, modules), mock.patch.object(library, "open_library", return_value=bibliotheque):
            library.serve("sqlite")
        return FauxFastMCP.instance.tools, bibliotheque

    def test_collection_inconnue(self):
        outils, bibliotheque = self.serveur()
        reponse = outils["search_library"]("flux", collections=["produit", "inexistante"])
        self.assertIn("Unknown collections: ['inexistante']", reponse["error"])
        self.assertIn("Known:", reponse["error"])
        self.assertEqual(bibliotheque.appels, [])           # la recherche n'a pas eu lieu

    def test_date_invalide(self):
        outils, bibliotheque = self.serveur()
        for since in ("2026-13-45", "hier", "2026/01/01"):
            with self.subTest(since=since):
                reponse = outils["search_library"]("flux", since=since)
                self.assertIn("since must be a date YYYY-MM-DD", reponse["error"])
                self.assertIn(repr(since), reponse["error"])
        self.assertEqual(bibliotheque.appels, [])

    def test_date_valide_transmise(self):
        outils, bibliotheque = self.serveur()
        outils["search_library"]("flux", since="2026-01-31")
        self.assertEqual(bibliotheque.appels[0][3], "2026-01-31")

    def test_limite_bornee_de_1_a_20(self):
        outils, bibliotheque = self.serveur()
        for demandee, attendue in ((0, 1), (-5, 1), (8, 8), (20, 20), (500, 20)):
            outils["search_library"]("flux", limit=demandee)
            self.assertEqual(bibliotheque.appels[-1][2], attendue, demandee)

    def test_voisins_de_read_passage_bornes_de_0_a_5(self):
        outils, bibliotheque = self.serveur()
        outils["read_passage"](4, before=-3, after=99)
        outils["read_passage"](4)
        self.assertEqual(bibliotheque.lectures, [(4, 0, 5), (4, 1, 2)])

    def test_erreur_de_valeur_de_la_recherche_devient_une_erreur(self):
        outils, _ = self.serveur(erreur=ValueError("types inconnus"))
        self.assertEqual(outils["search_library"]("flux", types=["x"]), {"error": "types inconnus"})

    def test_ancien_nom_de_collection_refuse_avec_le_nom_actuel(self):
        outils, bibliotheque = self.serveur()
        reponse = outils["search_library"]("flux", collections=["veille"])
        self.assertIn("Unknown collections: ['veille']", reponse["error"])
        self.assertIn("use 'watch'", reponse["error"])
        self.assertEqual(bibliotheque.appels, [])           # la recherche n'a pas eu lieu
        livres = outils["list_books"]("veille")
        self.assertEqual(len(livres), 1)
        self.assertIn("use 'watch'", livres[0]["error"])

    def test_nom_actuel_sans_message_et_comptes_sans_avertissement(self):
        outils, _ = self.serveur()
        self.assertEqual(outils["search_library"]("flux", collections=["watch"]), [{"passage_id": 1}])
        self.assertEqual(outils["list_books"]("watch"), [{"file": "livre.md"}])
        self.assertEqual(outils["list_collections"](), {"produit": 2, "watch": 1})

    def test_collection_inconnue_autre_que_l_ancien_nom_sans_indication(self):
        outils, _ = self.serveur()
        self.assertNotIn("use '", outils["search_library"]("flux", collections=["inexistante"])["error"])


class Catalogue(unittest.TestCase):
    def charger(self, contenu):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "catalogue.yaml"
            if contenu is not None:
                chemin.write_text(contenu, encoding="utf-8")
            with mock.patch.object(library, "CATALOGUE_PATH", chemin), contextlib.redirect_stdout(io.StringIO()):
                return library.load_catalogue()

    def test_cle_supplementaire_conservee_dans_le_dictionnaire(self):
        catalogue = self.charger("Flux.md:\n  titre: Titre inventé\n  auteurs: [Auteur Un]\n  editeur: Éditeur inventé\n")
        self.assertEqual(catalogue["Flux.md"], {"titre": "Titre inventé", "auteurs": ["Auteur Un"], "editeur": "Éditeur inventé"})

    def test_entree_sans_auteurs_acceptee(self):
        catalogue = self.charger("Flux.md:\n  titre: Sans auteur\n")
        self.assertEqual(catalogue["Flux.md"], {"titre": "Sans auteur"})

    def test_entrees_qui_ne_sont_pas_des_dictionnaires_ignorees(self):
        catalogue = self.charger("Flux.md:\n  titre: Ok\nVide.md:\nTexte.md: juste du texte\n")
        self.assertEqual(list(catalogue), ["Flux.md"])

    def test_noms_normalises_en_nfc(self):
        decompose = "Équipe.md"
        catalogue = self.charger(f"{decompose}:\n  titre: Ok\n")
        self.assertEqual(list(catalogue), ["Équipe.md"])

    def test_catalogue_absent_ou_vide(self):
        self.assertEqual(self.charger(None), {})
        self.assertEqual(self.charger(""), {})


class CatalogueDansLIndex(base.Base):
    """Une clé supplémentaire est ignorée par l'indexation ; seules `titre` et `auteurs` comptent."""

    def test_cle_supplementaire_ignoree_et_auteur_absent_remplace(self):
        self.catalogue.write_text("Flux.md:\n  titre: Titre du catalogue\n  auteurs: [Auteur Un]\n  editeur: Ignoré\n"
                                  "Discovery.md:\n  titre: Sans auteur\n  note: Ignorée\n", encoding="utf-8")
        self.indexer()
        self.assertEqual(self.livres()["Flux.md"][0], "Titre du catalogue")
        self.assertEqual(library.Library().search("kanban", None, 1)[0]["author"], "Auteur Un")
        self.assertEqual(library.Library().search("arbre d'opportunités", ["produit"], 1)[0]["author"], "auteur non indiqué")


if __name__ == "__main__":
    unittest.main()
