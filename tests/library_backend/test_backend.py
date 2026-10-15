"""
Tests de la voie unique de la bibliothèque (PostgreSQL) : `serve` refuse toute option, base muette au démarrage, erreur de base pendant un outil,
et tools/knowledge_library.py (PostgresLibrary).

    bash tests/run_all.sh library_backend

Sans base : refus de `--backend` (code 2) et de tout argument en trop, variable PMZILLA_LAB_BACKEND ignorée avec un avertissement, message
clair si la base ne répond pas (code 1, aucun fichier), objet d'erreur d'un outil dont la requête échoue, une seule variable pour la base de la
bibliothèque, forme des réponses calculée sur les lignes de la bibliothèque inventée, traduction des paramètres de recherche, configuration MCP
du jeu d'essai. Avec une base jetable (sautés si elle manque) : la bibliothèque inventée chargée par de simples INSERT, comparée aux valeurs
figées de tests/fixtures_library/demo_expected.py. Aucun appel à Ollama, aucune lecture de la vraie bibliothèque ni de la vraie base.
"""
import contextlib
import datetime as dt
import io
import json
import os
import re
import secrets
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
import pg_demo                  # noqa: E402  (ajoute tools/, tests/db et tests/fixtures_library au chemin)
import demo_library as demo     # noqa: E402
import demo_expected as attendu  # noqa: E402
import hybrid_search            # noqa: E402
import watch_paths             # noqa: E402
import knowledge_library as kl  # noqa: E402
import pmzilla_lab_library as library  # noqa: E402
import db                       # noqa: E402
from aides_serveur import modules_mcp, surveille_dossier, FauxFastMCP  # noqa: E402

TODAY = dt.date.today()


def code_de_sortie(arret: SystemExit) -> int:
    """Code de sortie du processus pour un SystemExit : un message vaut 1."""
    code = arret.code
    return 0 if code is None else (1 if isinstance(code, str) else int(code))


class Voie(unittest.TestCase):
    """`serve` n'accepte aucun argument ; la base est la seule voie ; aucun fichier du dossier de données n'est touché."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.donnees = Path(self.tmp.name) / "donnees"
        self.donnees.mkdir()
        (self.donnees / "library.sqlite").write_bytes(b"pas une base")            # fichier d'attente : il doit rester ignoré
        patch = mock.patch.dict(os.environ, {"PMZILLA_LAB_DATA": str(self.donnees)})
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("PMZILLA_LAB_BACKEND", None)

    def contenu(self):
        return sorted((p.name, p.stat().st_size) for p in self.donnees.iterdir())

    def lancer(self, *arguments):
        """`main()` avec ces arguments ; rend (code de sortie ou None, sortie d'erreur, chemins du dossier de données vus)."""
        erreurs = io.StringIO()
        avant = self.contenu()
        with surveille_dossier(self.donnees) as vus, contextlib.redirect_stderr(erreurs), \
                mock.patch.object(sys, "argv", ["pmzilla_lab_library.py", *arguments]):
            try:
                library.main()
                code = None
            except SystemExit as arret:
                code = code_de_sortie(arret)
        self.assertEqual(self.contenu(), avant)                       # aucun fichier créé, changé ni supprimé
        return code, erreurs.getvalue(), vus

    def test_serve_refuse_toute_option_backend_avec_le_code_2(self):
        formes = (["--backend", "sqlite"], ["--backend", "postgres"], ["--backend", "mysql"], ["--backend"], ["--backend", ""],
                  ["--backend=sqlite"], ["--backend=postgres"])
        for arguments in formes:
            with self.subTest(arguments=arguments), mock.patch.object(library, "serve") as serve:
                code, erreurs, vus = self.lancer("serve", *arguments)
                self.assertEqual(code, 2)
                self.assertIn("the --backend option was removed", erreurs)
                self.assertIn("PostgreSQL only", erreurs)
                self.assertIn("claude mcp get pmzilla-library", erreurs)          # le remède : retirer l'option de l'enregistrement
                serve.assert_not_called()
                self.assertEqual(vus, [])                                         # aucun fichier du dossier de données ouvert

    def test_serve_refuse_tout_autre_argument_avec_le_code_2(self):
        for arguments in (["--bidon"], ["postgres"], ["--dry-run", "x"]):
            with self.subTest(arguments=arguments), mock.patch.object(library, "serve") as serve:
                code, erreurs, vus = self.lancer("serve", *arguments)
                self.assertEqual(code, 2)
                self.assertIn("Usage: serve", erreurs)
                self.assertNotIn("--backend option was removed", erreurs)
                serve.assert_not_called()
                self.assertEqual(vus, [])

    def test_serve_sans_argument_demarre_le_serveur(self):
        with mock.patch.object(library, "serve") as serve:
            code, erreurs, vus = self.lancer("serve")
        self.assertIsNone(code)
        serve.assert_called_once_with()
        self.assertEqual((erreurs, vus), ("", []))

    def serveur(self, valeur_de_la_variable=None, **options):
        """`serve()` complet avec un faux FastMCP et une bibliothèque simulée ; rend (ouverture de la bibliothèque, erreurs, chemins vus)."""
        erreurs = io.StringIO()
        if valeur_de_la_variable is not None:
            os.environ["PMZILLA_LAB_BACKEND"] = valeur_de_la_variable
        with mock.patch.dict(sys.modules, modules_mcp()), \
                mock.patch.object(library, "open_library", return_value=object(), **options) as ouverture, \
                surveille_dossier(self.donnees) as vus, contextlib.redirect_stderr(erreurs):
            library.serve()
        return ouverture, erreurs.getvalue(), vus

    def test_ancienne_variable_ignoree_avec_un_avertissement_et_la_voie_postgresql(self):
        for valeur in ("sqlite", "postgres", "autre"):
            with self.subTest(valeur=valeur):
                ouverture, erreurs, vus = self.serveur(valeur)
                self.assertEqual(len(erreurs.splitlines()), 1)
                self.assertIn("PMZILLA_LAB_BACKEND is ignored", erreurs)
                ouverture.assert_called_once_with()                               # la bibliothèque PostgreSQL, sans choix de voie
                self.assertEqual(vus, [])

    def test_sans_la_variable_aucun_avertissement(self):
        ouverture, erreurs, vus = self.serveur()
        self.assertEqual(erreurs, "")
        ouverture.assert_called_once_with()

    def test_base_muette_au_demarrage_message_de_db_et_remede_code_1_aucun_fichier(self):
        with mock.patch.object(db, "connect", side_effect=db.ErreurBase("Connexion à la base impossible : refusée.")):
            with mock.patch.dict(sys.modules, modules_mcp()):
                avant = self.contenu()
                with surveille_dossier(self.donnees) as vus, self.assertRaises(SystemExit) as arret:
                    library.serve()
        message = str(arret.exception.code)
        self.assertEqual(code_de_sortie(arret.exception), 1)
        self.assertIn("Connexion à la base impossible : refusée.", message)          # le texte de db.py, repris tel quel
        self.assertIn("no fallback", message)
        self.assertIn("bash tools/db_up.sh", message)
        self.assertNotRegex(message.lower(), r"sqlite|--backend|password=")
        self.assertEqual(vus, [])                                                    # ni ouvert, ni créé, ni testé
        self.assertEqual(self.contenu(), avant)

    def test_base_muette_au_demarrage_par_main_code_1(self):
        with mock.patch.object(db, "connect", side_effect=db.ErreurBase("Connexion à la base impossible : refusée.")), \
                mock.patch.dict(sys.modules, modules_mcp()):
            code, erreurs, vus = self.lancer("serve")
        self.assertEqual(code, 1)
        self.assertEqual(vus, [])

    def test_open_library_sans_repli(self):
        with mock.patch.object(kl, "default_connect", side_effect=SystemExit("base muette")):
            with self.assertRaises(SystemExit) as cm:
                library.open_library()
        self.assertIn("base muette", str(cm.exception))

    def test_la_voie_de_fichier_n_existe_plus(self):
        for nom in ("Library", "BACKENDS", "choose_backend", "connect", "migrate_chunks", "SCHEMA", "DB_PATH", "DATA_DIR"):
            self.assertFalse(hasattr(library, nom), nom)
        self.assertNotRegex(Path(library.__file__).read_text(encoding="utf-8"), r"(?m)^\s*(?:import|from)\s+sqlite3\b")

    def test_base_qui_ne_repond_pas_message_clair_sans_secret(self):
        with mock.patch.object(db, "connect", side_effect=db.ErreurBase("Connexion à la base impossible : refusée.")):
            with self.assertRaises(SystemExit) as cm:
                kl.default_connect()
        message = str(cm.exception)
        self.assertIn("Connexion à la base impossible", message)
        self.assertIn("no fallback", message)
        self.assertIn("bash tools/db_up.sh", message)
        self.assertNotIn("--backend", message)

    def test_connexion_sous_le_role_de_lecture(self):
        with mock.patch.dict(os.environ), mock.patch.object(db, "connect", return_value=object()) as connect:
            os.environ.pop("PMZILLA_LAB_KNOWLEDGE_DBNAME", None)
            kl.default_connect()
        connect.assert_called_once_with(role="pmzilla_knowledge_ro", dbname=None)

    def test_base_nommee_par_la_variable(self):
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_KNOWLEDGE_DBNAME": "pmzilla_eval_inventee"}), \
                mock.patch.object(db, "connect", return_value=object()) as connect:
            kl.default_connect()
        connect.assert_called_once_with(role="pmzilla_knowledge_ro", dbname="pmzilla_eval_inventee")

    def test_base_nommee_muette_sans_repli_sur_celle_de_l_installation(self):
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_KNOWLEDGE_DBNAME": "pmzilla_eval_inventee"}), \
                mock.patch.object(db, "connect", side_effect=db.ErreurBase("Connexion à la base impossible : refusée.")) as connect:
            with self.assertRaises(SystemExit) as cm:
                kl.default_connect()
        self.assertEqual(connect.call_count, 1)                               # une seule tentative, sur la base nommée
        self.assertEqual(connect.call_args.kwargs["dbname"], "pmzilla_eval_inventee")
        self.assertIn("Connexion à la base impossible", str(cm.exception))

    def test_une_seule_variable_pour_la_base_de_la_bibliotheque_serveur_et_indexeur(self):
        """Tâche 3.7 : le serveur et l'indexeur lisent la même variable PMZILLA_LAB_KNOWLEDGE_DBNAME ; aucune seconde variable."""
        nom = "PMZILLA_LAB_KNOWLEDGE_DBNAME"
        self.assertEqual((kl.DBNAME_VARIABLE, library.KNOWLEDGE_DBNAME_VARIABLE), (nom, nom))
        with mock.patch.dict(os.environ, {nom: "pmzilla_eval_inventee"}):
            self.assertEqual(library.knowledge_dbname(), "pmzilla_eval_inventee")                   # l'indexeur
            with mock.patch.object(db, "connect", return_value=mock.MagicMock()) as connect:
                library.KnowledgeStore().open()
            self.assertEqual(connect.call_args.kwargs["dbname"], "pmzilla_eval_inventee")
            with mock.patch.object(db, "connect", return_value=object()) as connect:
                kl.default_connect()                                                                # le serveur
            self.assertEqual(connect.call_args.kwargs["dbname"], "pmzilla_eval_inventee")
        for outil in (library.__file__, kl.__file__):
            variables = set(re.findall(r"PMZILLA_LAB_\w*DBNAME", Path(outil).read_text(encoding="utf-8")))
            self.assertLessEqual(variables, {nom, "PMZILLA_LAB_CASES_DBNAME"}, outil)             # celle des cas est l'autre module

    def test_les_noms_de_genre_sont_definis_une_fois(self):
        """Tâche 3.4 : l'indexeur et le serveur partagent les noms de genre et la validation des types (fonctions du module)."""
        self.assertIs(kl.PG_KINDS, library.STORE_KINDS)
        self.assertIs(kl.STORE_NAMES, library.KIND_NAMES)
        self.assertEqual(library.KIND_NAMES, {"text": "texte", "figure": "figure"})
        self.assertEqual(library.check_types(None), ("texte",))
        self.assertEqual(library.check_types("figure"), ("figure",))
        self.assertEqual(library.check_types(["figure", "texte", "figure"]), ("figure", "texte"))
        for invalide in (["image"], ["texte", "photo"], []):
            with self.assertRaises(ValueError):
                library.check_types(invalide)
        with self.assertRaises(ValueError) as cm:
            library.check_types(["video"])
        self.assertIn("Known: ['texte', 'figure']", str(cm.exception))


class OperationalError(Exception):
    """Porte le nom que PostgresLibrary reconnaît pour une connexion perdue (psycopg.OperationalError)."""


class InternalError(Exception):
    """Porte le nom d'une erreur de la base qui n'est pas une connexion perdue (index BM25 illisible)."""


class UsineDeConnexions:
    """Fausse base : `erreur` est levée à chaque requête tant qu'elle est posée ; `lignes` est la réponse sinon."""

    def __init__(self):
        self.erreur, self.lignes, self.connexions, self.pannes = None, [], 0, 0      # pannes : requêtes à perdre la connexion avant de réussir

    def connect(self):
        self.connexions += 1
        return ConnexionFausse(self)


class ConnexionFausse:
    closed = False

    def __init__(self, usine):
        self.usine = usine

    def cursor(self):
        return CurseurFaux(self.usine)

    def rollback(self):
        pass


class CurseurFaux:
    def __init__(self, usine):
        self.usine = usine

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        if self.usine.pannes > 0:
            self.usine.pannes -= 1
            raise OperationalError("connexion coupée")
        if self.usine.erreur:
            raise self.usine.erreur

    def fetchall(self):
        return self.usine.lignes


class ErreurDeBaseDansUnOutil(unittest.TestCase):
    """Tâche 3.3 : l'objet d'erreur des quatre outils de la bibliothèque (design D3), après la seule reprise de connexion."""

    SECRET = "SELECT secret_colonne FROM knowledge.chunks"

    def setUp(self):
        self.usine = UsineDeConnexions()
        self.lib = kl.PostgresLibrary(connect=self.usine.connect, embed=demo.fake_embed, today=TODAY)
        self.addCleanup(mock.patch.stopall)
        mock.patch.dict(sys.modules, modules_mcp()).start()
        mock.patch.object(library, "open_library", return_value=self.lib).start()
        library.serve()
        self.outils = FauxFastMCP.instance.tools
        self.appels = {
            "search_library": lambda: self.outils["search_library"]("flux"),
            "read_passage": lambda: self.outils["read_passage"](1),
            "list_collections": lambda: self.outils["list_collections"](),
            "list_books": lambda: self.outils["list_books"](),
        }

    def verifier(self, reponse):
        """La forme de la réponse d'erreur : le type seul, les trois phrases clés, rien de la base."""
        if isinstance(reponse, list):                       # list_books répond une liste d'un objet d'erreur
            self.assertEqual(len(reponse), 1)
            reponse = reponse[0]
        self.assertEqual(list(reponse), ["error"])
        message = reponse["error"]
        for phrase in ("library database error", "bash tools/db_up.sh", "Damaged BM25 index"):
            self.assertIn(phrase, message)
        self.assertNotIn("secret_colonne", message)          # jamais le message de l'erreur, qui peut porter du SQL
        self.assertNotIn("SELECT", message)
        return message

    def test_erreur_de_requete_les_quatre_outils_repondent_un_objet_d_erreur_avec_le_type_seul(self):
        self.usine.erreur = InternalError(self.SECRET)
        with mock.patch.object(hybrid_search, "hybrid_search", side_effect=InternalError(self.SECRET)):
            for nom, appel in self.appels.items():
                with self.subTest(outil=nom):
                    self.assertIn("(InternalError)", self.verifier(appel()))

    def test_le_serveur_continue_et_l_appel_suivant_est_servi(self):
        self.usine.erreur = InternalError(self.SECRET)
        self.verifier(self.appels["list_collections"]())
        self.usine.erreur = None
        self.usine.lignes = [(["flow"],), (["flow", "tech"],)]
        self.assertEqual(self.appels["list_collections"](), {"flow": 2, "tech": 1})
        with mock.patch.object(hybrid_search, "hybrid_search", side_effect=InternalError(self.SECRET)):
            self.verifier(self.appels["search_library"]())
        with mock.patch.object(hybrid_search, "hybrid_search", return_value=[]):
            self.assertEqual(self.appels["search_library"](), [])

    def test_connexion_perdue_une_seule_reprise_puis_l_objet_d_erreur(self):
        self.usine.erreur = OperationalError("connexion coupée " + self.SECRET)
        for nom in ("read_passage", "list_collections", "list_books"):
            with self.subTest(outil=nom):
                depart = self.usine.connexions
                self.assertIn("(OperationalError)", self.verifier(self.appels[nom]()))
                self.assertEqual(self.usine.connexions - depart, 1)       # une seule reconnexion, jamais une boucle
        self.usine.erreur = None
        self.usine.lignes = [(["flow"],)]
        self.assertEqual(self.appels["list_collections"](), {"flow": 1})  # le serveur tourne toujours

    def test_connexion_perdue_une_fois_reprise_reussie_sans_objet_d_erreur(self):
        self.usine.pannes = 1
        self.usine.lignes = [(["flow"],)]
        self.assertEqual(self.appels["list_collections"](), {"flow": 1})

    def test_recherche_connexion_perdue_deux_fois_objet_d_erreur_et_exactement_une_reprise(self):
        depart = self.usine.connexions
        with mock.patch.object(hybrid_search, "hybrid_search", side_effect=OperationalError("coupée")) as recherche:
            self.assertIn("(OperationalError)", self.verifier(self.appels["search_library"]()))
        self.assertEqual(recherche.call_count, 2)                       # l'essai et sa seule reprise
        self.assertEqual(self.usine.connexions - depart, 1)             # une seule reconnexion
        with mock.patch.object(hybrid_search, "hybrid_search", return_value=[]):
            self.assertEqual(self.appels["search_library"](), [])

    def test_recherche_connexion_perdue_une_fois_reprise_reussie(self):
        with mock.patch.object(hybrid_search, "hybrid_search", side_effect=[OperationalError("coupée"), []]) as recherche:
            self.assertEqual(self.appels["search_library"](), [])
        self.assertEqual(recherche.call_count, 2)

    def test_une_erreur_de_valeur_reste_une_erreur_de_valeur_pas_une_erreur_de_base(self):
        reponse = self.outils["search_library"]("flux", types=["video"])
        self.assertIn("Unknown types", reponse["error"])
        self.assertNotIn("library database error", reponse["error"])
        self.assertIn("error", self.outils["search_library"]("flux", since="hier"))

    def test_la_base_qui_tombe_pendant_la_verification_des_collections(self):
        self.usine.erreur = InternalError(self.SECRET)
        self.verifier(self.outils["search_library"]("flux", collections=["flow"]))
        self.verifier(self.outils["list_books"]("flow"))


class ConfigurationMcp(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(RACINE / "tools"))
        import posture_evals as essai
        self.essai = essai
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def serveur(self, **options):
        chemin = self.essai.mcp_config(Path(self.tmp.name), **options)
        return json.loads(chemin.read_text())["mcpServers"]["pmzilla-library"]

    def args(self, **options):
        return self.serveur(**options)["args"]

    def test_defaut_sans_voie(self):
        self.assertEqual(self.args()[-1], "serve")
        self.assertNotIn("--backend", self.args())

    def test_ancienne_variable_non_lue(self):
        avant = self.args()
        for valeur in ("sqlite", "postgres"):
            with mock.patch.dict(os.environ, {"PMZILLA_LAB_BACKEND": valeur}):
                self.assertEqual(self.args(), avant)

    def test_plus_de_parametre_voie(self):
        with self.assertRaises(TypeError):
            self.essai.mcp_config(Path(self.tmp.name), backend="postgres")
        self.assertFalse(hasattr(self.essai, "library_backend"))

    def test_bibliotheque_jetable_d_un_cas_lue_dans_la_base_jetable(self):
        serveur = self.serveur(knowledge_dbname="pmzilla_eval_inventee", label="bibliotheque-c1")
        self.assertNotIn("--backend", serveur["args"])
        self.assertEqual(serveur["env"], {"PMZILLA_LAB_KNOWLEDGE_DBNAME": "pmzilla_eval_inventee"})
        self.assertNotIn("PMZILLA_LAB_DATA", serveur["env"])


def ligne(fichier: str, position: int) -> dict:
    """La ligne que `_describe_many` fabrique pour un passage de la bibliothèque inventée (genre rendu `text`, collections en liste)."""
    titre, collections, meta = demo.BOOKS[fichier]
    for numero, (nom, pos, section, texte, _angle, genre, ref) in enumerate(demo.CHUNKS, 1):
        if (nom, pos) == (fichier, position):
            return {"id": numero, "position": pos, "section": section, "text": texte, "kind": kl.PG_KINDS[genre], "ref": ref,
                    "title": titre, "file": fichier, "meta": meta, "names": collections.split("|")}
    raise KeyError((fichier, position))


class Forme(unittest.TestCase):
    """PostgresLibrary rend le dictionnaire figé par les tests, à partir des lignes que PostgreSQL rendrait (sans base)."""

    def test_dictionnaire_de_chaque_passage_de_la_bibliotheque_inventee(self):
        self.assertEqual(len(attendu.SHAPES), len(demo.CHUNKS))
        for (fichier, position), forme in attendu.SHAPES.items():
            with self.subTest(fichier=fichier, position=position):
                decrit = kl.PostgresLibrary._shape(ligne(fichier, position), score=0.0123)
                decrit.pop("passage_id")                          # propre à chaque base
                self.assertEqual(decrit, forme)

    def test_figure_porte_sa_ref_et_le_texte_non(self):
        texte = kl.PostgresLibrary._shape(ligne("atelier-des-flux.md", 0))
        self.assertNotIn("ref", texte)
        self.assertEqual(texte["kind"], "texte")
        figure = kl.PostgresLibrary._shape(ligne("atelier-des-flux.md", 3))
        self.assertEqual(figure["kind"], "figure")
        self.assertEqual(figure["ref"]["label"], "Figure 1.1")
        self.assertEqual([c["kind"] for c in (kl.PostgresLibrary._shape(ligne(f, p)) for f, p in attendu.SHAPES)].count("figure"), 2)

    def test_collections_triees_et_canoniques(self):
        decrit = kl.PostgresLibrary._shape(ligne("article-propre.md", 0))
        self.assertEqual(decrit["collections"], sorted([watch_paths.OWN_COLLECTION, "watch"]))


def par_score(resultats):
    """[(score, ensemble des passages)] : les résultats groupés par score arrondi égal, dans l'ordre rendu.

    Choix : à score arrondi égal, l'ordre dépend du départage de la fusion (rang vectoriel, rang plein texte, identifiant). Les valeurs figées
    viennent d'une autre implémentation du plein texte (FTS5), dont les rangs de mots rares peuvent différer d'un cran d'un moteur à l'autre
    sans changer un score. Le contrat figé est donc : la suite des scores, dans l'ordre, et, pour chaque niveau de score, l'ensemble des
    passages (un groupe d'un passage reste un ordre exact). La position de la tête de liste est vérifiée à part quand elle est seule de son niveau.
    """
    groupes = []
    for fichier, position, score in resultats:
        if groupes and groupes[-1][0] == score:
            groupes[-1][1].add((fichier, position))
        else:
            groupes.append((score, {(fichier, position)}))
    return groupes


class ValeursFigees(unittest.TestCase):
    """La bibliothèque inventée dans une base jetable, lue par PostgresLibrary, rend les valeurs figées de demo_expected (sautés sans base).
    Les valeurs ont été capturées le 2026-10-14 sur l'ancienne voie de fichier, avant son retrait (tâche 1.3 de remove-sqlite)."""

    BALAYAGE = "ann"

    def setUp(self):
        self.pg = pg_demo.ThrowawayDatabase(self)            # saute le test sans base
        self.lib = kl.PostgresLibrary(connect=self.pg.connect, embed=demo.fake_embed, today=TODAY, scan=self.BALAYAGE)

    def recherche(self, question, collections, limite, jours, types, composante):
        collections = [attendu.OWN if c == "OWN" else c for c in collections] if collections else collections
        depuis = (TODAY - dt.timedelta(days=jours)).isoformat() if jours else None
        return [(r["file"], r["position"], r["score"]) for r in self.lib.search(question, collections, limite, depuis, types, component=composante)]

    def test_recherches(self):
        for cas, resultats in attendu.SEARCHES:
            with self.subTest(cas=cas):
                trouve = self.recherche(*cas)
                self.assertEqual(par_score(trouve), par_score(resultats))
                self.assertEqual([score for _, _, score in trouve], [score for _, _, score in resultats])
                self.assertEqual(len(trouve), len(resultats))

    def test_groupes_d_un_passage_gardent_l_ordre_exact(self):
        for cas, resultats in attendu.SEARCHES:
            with self.subTest(cas=cas):
                trouve = self.recherche(*cas)
                seuls = [score for score, groupe in par_score(resultats) if len(groupe) == 1]
                for score in seuls:
                    self.assertEqual([c for c in trouve if c[2] == score], [c for c in resultats if c[2] == score])

    def test_formes(self):
        for (fichier, position), forme in attendu.SHAPES.items():
            with self.subTest(fichier=fichier, position=position):
                (chunk_id,) = self.lib._query("SELECT c.id FROM knowledge.chunks c JOIN knowledge.books b ON b.id = c.book_id "
                                              "WHERE b.file_name = %s AND c.position = %s", (fichier, position))[0]
                decrit = kl.PostgresLibrary._shape(self.lib._describe_many([chunk_id])[chunk_id], score=0.0123)
                self.assertIsInstance(decrit.pop("passage_id"), int)
                self.assertEqual(decrit, forme)

    def test_listes_et_lecture(self):
        self.assertEqual(self.lib.collections(), attendu.COLLECTIONS)
        for collection, livres in attendu.BOOKS.items():
            self.assertEqual(self.lib.books(collection), livres)
        tete = self.lib.search("figure délai travail en cours", None, 1)[0]
        cle, lecture = attendu.READ_AROUND
        self.assertEqual((tete["file"], tete["position"]), cle)
        trouve = self.lib.read(tete["passage_id"], 1, 1)
        for passage in trouve["passages"]:
            passage.pop("passage_id")
        self.assertEqual(trouve, lecture)
        self.assertEqual(self.lib.read(10 ** 9, 1, 1)["error"], attendu.UNKNOWN_PASSAGE_ERROR.format(10 ** 9))

    def test_bibliotheque_inventee_chargee(self):
        comptes = demo.expected_counts()
        self.assertEqual(self.lib._query("SELECT count(*) FROM knowledge.books")[0][0], comptes["books"])
        self.assertEqual(self.lib._query("SELECT count(*) FROM knowledge.chunks")[0][0], comptes["chunks"])
        self.assertEqual(self.lib._query("SELECT count(*) FROM knowledge.chunks WHERE kind = 'figure'")[0][0], comptes["figures"])


class ValeursFigeesBalayageExact(ValeursFigees):
    """Les mêmes valeurs par le balayage exact : le corpus est petit, l'index approché rend les mêmes passages."""

    BALAYAGE = "exact"


class FausseBase:
    def rollback(self):
        pass


class Parametres(unittest.TestCase):
    """Ce que PostgresLibrary demande à la recherche SQL, sans base."""

    def setUp(self):
        self.captured = {}

        def fake(conn, spec, **options):
            self.captured = options
            return []
        patch = mock.patch.object(hybrid_search, "hybrid_search", side_effect=fake)
        patch.start()
        self.addCleanup(patch.stop)
        self.lib = kl.PostgresLibrary(connect=FausseBase, embed=demo.fake_embed, scan="ann", today=TODAY)

    def test_types_et_collections_traduits(self):
        self.lib.search("flux", None, 8)
        self.assertEqual(self.captured["kinds"], ["text"])
        self.assertIsNone(self.captured["collections"])
        self.lib.search("flux", ["watch"], 8, "2026-01-01", ["texte", "figure"])
        self.assertIsNone(self.captured["kinds"])                                # tous les types : pas de filtre
        self.assertEqual(self.captured["collections"], ["watch"])
        self.assertEqual(self.captured["since"], "2026-01-01")
        self.lib.search("flux", ["flow"], 8, None, ["figure"])
        self.assertEqual((self.captured["collections"], self.captured["kinds"]), (["flow"], ["figure"]))
        self.assertEqual(self.captured["scan"], "ann")

    def test_defaut_ann_ef_search_400(self):
        voie = kl.PostgresLibrary(connect=FausseBase, embed=demo.fake_embed, today=TODAY)
        self.assertEqual((voie.scan, voie.ef_search), ("ann", 400))

    def test_ef_search_transmis_a_la_recherche(self):
        self.lib.search("flux", None, 8)
        self.assertEqual(self.captured["ef_search"], kl.hybrid_search.EF_SEARCH)
        self.lib.ef_search = 400
        self.lib.search("flux", None, 8)
        self.assertEqual(self.captured["ef_search"], 400)

    def test_types_inconnus_refuses(self):
        with self.assertRaises(ValueError):
            self.lib.search("flux", None, 8, None, ["video"])

    def test_refresh_ne_fait_rien(self):
        self.assertIsNone(self.lib.refresh())


class AvecBase(unittest.TestCase):
    """Contrat de PostgresLibrary sur la bibliothèque inventée d'une base jetable (sautés sans base)."""

    def setUp(self):
        self.pg = pg_demo.ThrowawayDatabase(self)
        self.postgres = kl.PostgresLibrary(connect=self.pg.connect, embed=demo.fake_embed, today=TODAY)

    def cles(self, resultats):
        return [(r["file"], r["position"]) for r in resultats]

    def test_resultats_decrits_comme_les_valeurs_figees(self):
        cas = [("le flux de travail", None, None), ("hypothesis experiment", ["produit"], None), ("délai", None, ["figure"]),
               ("prévision", ["watch"], None), ("équipe", None, ["texte", "figure"]),
               ("coaching", [watch_paths.OWN_COLLECTION], None)]
        for question, collections, types in cas:
            with self.subTest(question=question, collections=collections, types=types):
                trouve = self.postgres.search(question, collections, 14, None, types)
                self.assertTrue(trouve)
                for resultat in trouve:
                    self.assertIsInstance(resultat.pop("passage_id"), int)
                    score = resultat.pop("score")
                    forme = dict(attendu.SHAPES[(resultat["file"], resultat["position"])])
                    forme.pop("score")                                       # 0.0123 : valeur de convention des formes figées
                    self.assertEqual(resultat, forme)
                    self.assertGreater(score, 0)

    def test_since_garde_les_livres(self):
        depuis = (TODAY - dt.timedelta(days=5)).isoformat()
        trouve = self.cles(self.postgres.search("prévision", None, 14, depuis))
        self.assertNotIn(("billet-ancien.md", 0), trouve)
        self.assertIn(("atelier-des-flux.md", 1), trouve)                    # un livre n'a pas de date : gardé

    def test_collections_et_livres_sans_alias(self):
        self.assertFalse(hasattr(self.postgres, "stored_aliases"))
        self.assertEqual(self.postgres.books("veille"), [])                  # l'ancien nom n'est plus un alias
        self.assertEqual([b["file"] for b in self.postgres.books("flow")], ["atelier-des-flux.md"])
        self.assertEqual(len(self.postgres.books(None)), len(demo.BOOKS))

    def test_passage_inconnu(self):
        self.assertIn("Unknown passage_id", self.postgres.read(10 ** 9, 1, 1)["error"])

    def test_le_role_de_lecture_ne_peut_pas_ecrire(self):
        conn = self.pg.connect()
        with self.assertRaises(Exception):
            conn.execute("DELETE FROM knowledge.chunks")
        conn.rollback()

    def test_le_serveur_lit_la_base_nommee_par_la_variable(self):
        """La base jetable est lue par `default_connect` quand la variable la nomme, jamais celle de l'installation.

        `default_connect` se connecte sous le rôle de lecture lui-même, et les migrations créent ce rôle en NOLOGIN, sans mot de passe :
        le test lui en pose un le temps du passage, puis le remet comme il l'a trouvé (le rôle est partagé par l'instance). Un rôle déjà
        ouvert à la connexion n'est pas touché."""
        role = "pmzilla_knowledge_ro"
        ouvert = self.pg.admin.execute("SELECT rolcanlogin FROM pg_roles WHERE rolname = %s", (role,)).fetchone()[0]
        environnement = {"PMZILLA_LAB_KNOWLEDGE_DBNAME": self.pg.name}
        if not ouvert:
            secret = secrets.token_urlsafe(24)
            self.addCleanup(lambda: self.pg.admin.execute(f'ALTER ROLE "{role}" NOLOGIN PASSWORD NULL'))
            db.definir_mot_de_passe(self.pg.admin, role, secret)
            environnement[db.variable_du_role(role)] = secret
        with mock.patch.dict(os.environ, environnement):
            conn = kl.default_connect()
        self.addCleanup(conn.close)
        self.assertEqual(conn.execute("SELECT current_database()").fetchone()[0], self.pg.name)
        self.assertEqual(conn.execute("SELECT current_user").fetchone()[0], "pmzilla_knowledge_ro")


if __name__ == "__main__":
    unittest.main()
