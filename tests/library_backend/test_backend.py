"""
Tests du choix de la voie de la bibliothèque (SQLite ou PostgreSQL) et de tools/knowledge_library.py (PostgresLibrary).

    bash tests/run_all.sh library_backend

Sans base : choix de la voie (option, variable, refus), forme des réponses (même dictionnaire que `Library._describe`), traduction
des paramètres de recherche, message clair si la base ne répond pas, configuration MCP du jeu d'essai. Avec une base jetable (sautés
si elle manque) : suite de contrat jouée sur les deux voies avec la bibliothèque inventée. Aucun appel à Ollama, aucune lecture de
la vraie bibliothèque ni de la vraie base.
"""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
import pg_demo                  # noqa: E402  (ajoute tools/, tests/db et tests/fixtures_library au chemin)
import demo_library as demo     # noqa: E402
import hybrid_search            # noqa: E402
import watch_paths             # noqa: E402
import knowledge_library as kl  # noqa: E402
import pmzilla_lab_library as library  # noqa: E402
import db                       # noqa: E402

TODAY = dt.date.today()


class Voie(unittest.TestCase):
    def test_defaut_postgres_option_et_variable(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PMZILLA_LAB_BACKEND", None)
            self.assertEqual(library.choose_backend(None), "postgres")
            self.assertEqual(library.choose_backend("postgres"), "postgres")
            os.environ["PMZILLA_LAB_BACKEND"] = "postgres"
            self.assertEqual(library.choose_backend(None), "postgres")
            self.assertEqual(library.choose_backend("sqlite"), "sqlite")      # l'option l'emporte sur la variable

    def test_voie_inconnue_refusee(self):
        with self.assertRaises(SystemExit) as cm:
            library.choose_backend("mysql")
        self.assertIn("mysql", str(cm.exception))
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_BACKEND": "autre"}):
            with self.assertRaises(SystemExit):
                library.choose_backend(None)

    def test_open_library_postgres_sans_repli_sur_sqlite(self):
        with mock.patch.object(kl, "default_connect", side_effect=SystemExit("base muette")):
            with self.assertRaises(SystemExit) as cm:
                library.open_library("postgres")
        self.assertIn("base muette", str(cm.exception))

    def test_base_qui_ne_repond_pas_message_clair_sans_secret(self):
        with mock.patch.object(db, "connect", side_effect=db.ErreurBase("Connexion à la base impossible : refusée.")):
            with self.assertRaises(SystemExit) as cm:
                kl.default_connect()
        self.assertIn("Connexion à la base impossible", str(cm.exception))
        self.assertIn("--backend sqlite", str(cm.exception))

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

    def test_serve_accepte_l_option_backend(self):
        with mock.patch.object(library, "serve") as serve, mock.patch.object(sys, "argv", ["x", "serve", "--backend", "postgres"]):
            library.main()
        serve.assert_called_once_with("postgres")
        with mock.patch.object(library, "serve") as serve, mock.patch.object(sys, "argv", ["x", "serve"]):
            library.main()
        serve.assert_called_once_with(None)
        with mock.patch.object(library, "serve"), mock.patch.object(sys, "argv", ["x", "serve", "--bidon"]):
            with self.assertRaises(SystemExit):
                library.main()


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

    def test_defaut_inchange(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PMZILLA_LAB_BACKEND", None)
            self.assertEqual(self.args()[-1], "serve")
            self.assertNotIn("--backend", self.args())

    def test_voie_transmise(self):
        self.assertEqual(self.args(backend="postgres")[-2:], ["--backend", "postgres"])
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_BACKEND": "postgres"}):
            self.assertEqual(self.args()[-2:], ["--backend", "postgres"])

    def test_bibliotheque_jetable_d_un_cas_lue_dans_la_base_jetable(self):
        for voie in (None, "sqlite", "postgres"):
            with self.subTest(voie=voie):
                serveur = self.serveur(knowledge_dbname="pmzilla_eval_inventee", backend=voie, label="bibliotheque-c1")
                self.assertEqual(serveur["args"][-2:], ["--backend", "postgres"])
                self.assertEqual(serveur["env"], {"PMZILLA_LAB_KNOWLEDGE_DBNAME": "pmzilla_eval_inventee"})
                self.assertNotIn("PMZILLA_LAB_DATA", serveur["env"])


class Forme(unittest.TestCase):
    """PostgresLibrary rend le dictionnaire de Library._describe, à partir des lignes que PostgreSQL rendrait."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        chemin = Path(self.tmp.name) / "library.sqlite"
        demo.build_sqlite(chemin)
        for patch in (mock.patch.object(library, "DATA_DIR", Path(self.tmp.name)), mock.patch.object(library, "DB_PATH", chemin),
                      mock.patch.object(library, "embed", demo.fake_embed)):
            patch.start()
            self.addCleanup(patch.stop)
        self.lib = library.Library()

    def ligne(self, chunk_id):
        """La ligne que `_describe_many` fabrique, tirée de l'index SQLite (kind rendu `text`)."""
        row = self.lib.db.execute("SELECT c.id, c.position, c.section, c.text, c.kind, c.ref, b.title, b.file_name, b.meta, b.collections "
                                  "FROM chunks c JOIN books b ON b.id = c.book_id WHERE c.id = ?", (chunk_id,)).fetchone()
        return {"id": row["id"], "position": row["position"], "section": row["section"], "text": row["text"],
                "kind": kl.PG_KINDS[row["kind"]], "ref": json.loads(row["ref"]), "title": row["title"], "file": row["file_name"],
                "meta": json.loads(row["meta"]), "names": row["collections"].split("|")}

    def test_meme_dictionnaire_que_la_voie_sqlite(self):
        for (chunk_id,) in self.lib.db.execute("SELECT id FROM chunks"):
            with self.subTest(passage=chunk_id):
                attendu = self.lib._describe(chunk_id, score=0.0123)
                self.assertEqual(kl.PostgresLibrary._shape(self.ligne(chunk_id), score=0.0123), attendu)

    def test_figure_porte_sa_ref_et_le_texte_non(self):
        figures = [i for (i,) in self.lib.db.execute("SELECT id FROM chunks WHERE kind = 'figure' ORDER BY id")]
        texte = kl.PostgresLibrary._shape(self.ligne(1))
        self.assertNotIn("ref", texte)
        self.assertEqual(texte["kind"], "texte")
        figure = kl.PostgresLibrary._shape(self.ligne(figures[0]))
        self.assertEqual(figure["kind"], "figure")
        self.assertEqual(figure["ref"]["label"], "Figure 1.1")


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

    def test_types_inconnus_refuses_comme_en_sqlite(self):
        with self.assertRaises(ValueError):
            self.lib.search("flux", None, 8, None, ["video"])

    def test_refresh_ne_fait_rien(self):
        self.assertIsNone(self.lib.refresh())


class AvecBase(Forme):
    """Suite de contrat : les deux voies sur les mêmes données (sautés sans base)."""

    def setUp(self):
        super().setUp()
        self.pg = pg_demo.ThrowawayDatabase(self)
        self.postgres = kl.PostgresLibrary(connect=self.pg.connect, embed=demo.fake_embed, today=TODAY)

    def cles(self, resultats):
        return [(r["file"], r["position"]) for r in resultats]

    def test_memes_formes_et_memes_resultats(self):
        cas = [("le flux de travail", None, None), ("hypothesis experiment", ["produit"], None), ("délai", None, ["figure"]),
               ("prévision", ["watch"], None), ("équipe", None, ["texte", "figure"]),
               ("coaching", [watch_paths.OWN_COLLECTION], None)]
        for question, collections, types in cas:
            with self.subTest(question=question, collections=collections, types=types):
                a = self.lib.search(question, collections, 14, None, types)
                b = self.postgres.search(question, collections, 14, None, types)
                self.assertEqual(set(self.cles(a)), set(self.cles(b)))
                self.assertEqual(self.cles(a)[:1], self.cles(b)[:1])
                for x, y in zip(sorted(a, key=lambda r: (r["file"], r["position"])), sorted(b, key=lambda r: (r["file"], r["position"]))):
                    self.assertEqual(set(x), set(y))
                    for cle in ("book", "file", "section", "position", "collections", "kind", "text", "url", "author", "published"):
                        self.assertEqual(x.get(cle), y.get(cle), cle)
                    self.assertEqual(x.get("ref"), y.get("ref"))
                    self.assertIsInstance(y["passage_id"], int)

    def test_since_garde_les_livres(self):
        depuis = (TODAY - dt.timedelta(days=5)).isoformat()
        a = self.cles(self.lib.search("prévision", None, 14, depuis))
        b = self.cles(self.postgres.search("prévision", None, 14, depuis))
        self.assertEqual(set(a), set(b))
        self.assertNotIn(("billet-ancien.md", 0), b)

    def test_collections_et_livres_sans_alias(self):
        self.assertEqual(self.postgres.collections(), self.lib.collections())
        self.assertFalse(hasattr(self.postgres, "stored_aliases"))
        self.assertEqual(self.postgres.books(None), self.lib.books(None))
        self.assertEqual(self.postgres.books("veille"), self.lib.books("veille"))     # l'ancien nom n'est plus un alias
        self.assertEqual(self.postgres.books("flow"), self.lib.books("flow"))

    def test_lecture_autour_d_un_passage(self):
        question = "figure délai travail en cours"
        pg = self.postgres.search(question, None, 1)[0]
        trouve = self.postgres.read(pg["passage_id"], 1, 1)
        sqlite_id = next(r["passage_id"] for r in self.lib.search(question, None, 14) if (r["file"], r["position"]) == (pg["file"], pg["position"]))
        attendu = self.lib.read(sqlite_id, 1, 1)
        self.assertEqual(trouve["file"], attendu["file"])
        self.assertEqual(trouve["book"], attendu["book"])
        self.assertEqual([p["position"] for p in trouve["passages"]], [p["position"] for p in attendu["passages"]])
        for x, y in zip(trouve["passages"], attendu["passages"]):
            self.assertEqual({k: v for k, v in x.items() if k != "passage_id"}, {k: v for k, v in y.items() if k != "passage_id"})

    def test_passage_inconnu(self):
        erreur = self.postgres.read(10 ** 9, 1, 1)["error"]
        self.assertIn("Unknown passage_id", erreur)
        self.assertEqual(erreur, self.lib.read(10 ** 9, 1, 1)["error"])

    def test_le_role_de_lecture_ne_peut_pas_ecrire(self):
        conn = self.pg.connect()
        with self.assertRaises(Exception):
            conn.execute("DELETE FROM knowledge.chunks")
        conn.rollback()


if __name__ == "__main__":
    unittest.main()
