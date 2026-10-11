"""
Tests des trois outils MCP du module des cas (search_cases, search_experiments, list_due_reviews) du serveur pmzilla-library.

    bash tests/run_all.sh pmzilla_lab_library

Sans base, sans Ollama, sans paquet `mcp` : le serveur est lancé avec un faux FastMCP qui garde les outils déclarés, et le lecteur
des cas est une doublure (la fabrique `make_cases_reader` est remplacée). Données inventées.
"""
import ast
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import cases_store  # noqa: E402
import db  # noqa: E402
import pmzilla_lab_library as library  # noqa: E402

CAS = {"number": 1, "problem": "p inventé", "similarity": 0.8, "score": 0.03}
EXPERIENCE = {"number": 2, "mine": True, "problem": "q inventé", "similarity": 0.7, "score": 0.02}
REVUE = {"number": 3, "problem": "r inventé", "review_due": "2026-01-01", "postponements": 0, "decision_required": False}


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


class FauxBibliotheque:
    def collections(self):
        return {"produit": 2}

    def books(self, collection):
        return [{"file": "livre.md"}]

    def search(self, query, collections, limit, since, types):
        return [{"passage_id": 1, "text": "passage inventé"}]

    def read(self, passage_id, before, after):
        return {"passage_id": passage_id}


class FauxLecteur:
    def __init__(self, **erreurs):
        self.appels = []
        self.erreurs = erreurs

    def _appel(self, nom, *args, **options):
        self.appels.append((nom, args, options))
        if nom in self.erreurs:
            raise self.erreurs[nom]
        return {"search_cases": [CAS], "search_experiments": [EXPERIENCE], "list_due_reviews": [REVUE]}[nom]

    def search_cases(self, query, limit=3):
        return self._appel("search_cases", query, limit=limit)

    def search_experiments(self, query, limit=3, author=None):
        return self._appel("search_experiments", query, limit=limit)

    def list_due_reviews(self, author=None):
        return self._appel("list_due_reviews")


class Cas(unittest.TestCase):
    def serveur(self, *args, **options):
        """Les patchs durent jusqu'à la fin du test : les outils cherchent la fabrique à chaque appel."""
        patchs = []
        outils, fabrique = serveur(patchs, *args, **options)
        for patch in patchs:
            self.addCleanup(patch.stop)
        return outils, fabrique


def serveur(patchs, backend="postgres", lecteur=None, fabrique=None):
    """Lance serve() avec un faux FastMCP ; renvoie les outils déclarés et la fabrique de lecteur simulée."""
    modules = {"mcp": types.ModuleType("mcp"), "mcp.server": types.ModuleType("mcp.server"),
               "mcp.server.fastmcp": types.ModuleType("mcp.server.fastmcp")}
    modules["mcp.server.fastmcp"].FastMCP = FauxFastMCP
    fabrique = fabrique or mock.Mock(return_value=lecteur)
    patchs.extend([mock.patch.dict(sys.modules, modules), mock.patch.object(library, "open_library", return_value=FauxBibliotheque()),
                   mock.patch.object(library, "make_cases_reader", fabrique)])
    for patch in patchs:
        patch.start()
    library.serve(backend)
    patchs[0].stop()
    del patchs[0]
    return FauxFastMCP.instance.tools, fabrique


class Inventaire(Cas):
    def test_sept_outils_dont_trois_pour_les_cas(self):
        outils, _ = self.serveur(lecteur=FauxLecteur())
        self.assertEqual(sorted(outils), ["list_books", "list_collections", "list_due_reviews", "read_passage",
                                          "search_cases", "search_experiments", "search_library"])

    def test_aucun_outil_n_ecrit(self):
        source = Path(library.__file__).read_text(encoding="utf-8")
        noms = [n.name for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef)
                and any("tool" in ast.unparse(d) for d in n.decorator_list)]
        for nom in noms:
            for verbe in ("start", "note", "postpone", "drop", "close"):
                self.assertNotIn(verbe, nom)


class Reponses(Cas):
    def test_avec_un_faux_lecteur_les_trois_outils_renvoient_des_listes(self):
        lecteur = FauxLecteur()
        outils, fabrique = self.serveur(lecteur=lecteur)
        self.assertEqual(outils["search_cases"]("une question", 5), [CAS])
        self.assertEqual(outils["search_experiments"]("une question"), [EXPERIENCE])
        self.assertEqual(outils["list_due_reviews"](), [REVUE])
        self.assertEqual(lecteur.appels[0], ("search_cases", ("une question",), {"limit": 5}))
        fabrique.assert_called_once_with()      # un seul lecteur par serveur

    def test_le_lecteur_n_est_pas_cree_au_demarrage(self):
        _, fabrique = self.serveur(lecteur=FauxLecteur())
        fabrique.assert_not_called()

    def test_liste_vide_reste_une_liste(self):
        lecteur = FauxLecteur()
        lecteur.search_cases = lambda query, limit=3: []
        outils, _ = self.serveur(lecteur=lecteur)
        self.assertEqual(outils["search_cases"]("une question"), [])

    def test_voie_sqlite_erreur_et_aucun_lecteur(self):
        outils, fabrique = self.serveur(backend="sqlite", lecteur=FauxLecteur())
        for appel in (lambda: outils["search_cases"]("q"), lambda: outils["search_experiments"]("q"), lambda: outils["list_due_reviews"]()):
            self.assertEqual(appel(), {"error": "the cases module requires the PostgreSQL backend"})
        fabrique.assert_not_called()

    def test_requete_vide_refusee_sans_lecteur(self):
        outils, fabrique = self.serveur(lecteur=FauxLecteur())
        for requete in ("", "   "):
            for nom in ("search_cases", "search_experiments"):
                reponse = outils[nom](requete)
                self.assertIsInstance(reponse, dict)
                self.assertIn("empty", reponse["error"])
        fabrique.assert_not_called()

    def test_les_refus_du_lecteur_deviennent_des_objets_erreur(self):
        for code, message in (("author_missing", "no author configured"), ("threshold_not_calibrated", "similarity threshold not calibrated")):
            erreur = cases_store.CasesError(message, code=code)
            outils, _ = self.serveur(lecteur=FauxLecteur(search_cases=erreur, search_experiments=erreur, list_due_reviews=erreur))
            for reponse in (outils["search_cases"]("q"), outils["search_experiments"]("q"), outils["list_due_reviews"]()):
                self.assertEqual(reponse, {"error": message})

    def test_base_des_cas_injoignable_sans_secret_et_vers_db_up(self):
        lecteur = cases_store.CasesReader(connect=None)
        with mock.patch.object(cases_store, "connect_cases", side_effect=db.ErreurBase("refusée par le serveur")):
            outils, _ = self.serveur(lecteur=lecteur)
            reponse = outils["search_cases"]("q")
            self.assertIn("error", reponse)
            self.assertIn("bash tools/db_up.sh", reponse["error"])
            self.assertNotIn("password", reponse["error"].lower())
            self.assertIn("error", outils["list_due_reviews"]())

    def test_fabrique_en_echec_devient_une_erreur(self):
        fabrique = mock.Mock(side_effect=cases_store.CasesError("cases database unreachable: x Start it with: bash tools/db_up.sh"))
        outils, _ = self.serveur(fabrique=fabrique)
        self.assertIn("db_up.sh", outils["search_cases"]("q")["error"])

    def test_les_quatre_outils_de_la_bibliotheque_repondent_base_des_cas_arretee(self):
        fabrique = mock.Mock(side_effect=cases_store.CasesError("cases database unreachable: x Start it with: bash tools/db_up.sh"))
        outils, _ = self.serveur(fabrique=fabrique)
        self.assertEqual(outils["search_library"]("q"), [{"passage_id": 1, "text": "passage inventé"}])
        self.assertEqual(outils["read_passage"](1), {"passage_id": 1})
        self.assertEqual(outils["list_collections"](), {"produit": 2})
        self.assertEqual(outils["list_books"](), [{"file": "livre.md"}])
        fabrique.assert_not_called()


class Fabrique(unittest.TestCase):
    def test_make_cases_reader_renvoie_un_lecteur_sans_connexion(self):
        with mock.patch.object(db, "connect") as connect:
            lecteur = library.make_cases_reader()
        self.assertIsInstance(lecteur, cases_store.CasesReader)
        connect.assert_not_called()

    def test_la_variable_de_base_atteint_db_connect(self):
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_CASES_DBNAME": "pmzilla_test_abc"}), \
                mock.patch.object(db, "connect", return_value=mock.Mock(closed=False)) as connect:
            library.make_cases_reader().connection()
        connect.assert_called_once()
        self.assertEqual(connect.call_args.kwargs["dbname"], "pmzilla_test_abc")
        self.assertEqual(connect.call_args.kwargs["role"], "pmzilla_cases_ro")


if __name__ == "__main__":
    unittest.main()
