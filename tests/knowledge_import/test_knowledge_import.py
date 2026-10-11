"""
Tests de tools/knowledge_import.py (lot 4) sur la bibliothèque inventée de tests/fixtures_library/demo_library.py.

    uv run --with "psycopg[binary]" --with numpy --with httpx --with pyyaml python -m unittest discover -s tests/knowledge_import -v

Sans base : lecture seule de SQLite, empreintes, aller-retour float16 <-> halfvec, collections canoniques, plan, dry-run (fausse
connexion), messages. Avec base : base jetable pmzilla_test_<hex> (créée, migrée, supprimée dans tous les cas, jamais les schémas réels),
sautée si la base manque. Aucun texte de livre réel, aucun appel à Ollama.
"""
import contextlib
import io
import secrets
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import psycopg
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(RACINE / "tests" / "fixtures_library"))
sys.path.insert(0, str(RACINE / "tests" / "db"))
import knowledge_import as ki  # noqa: E402
import watch_paths  # noqa: E402
import demo_library as demo  # noqa: E402
import test_db as base  # noqa: E402  (connexion, BASE_DISPONIBLE, mot de passe de test)
from test_db import db  # noqa: E402


def lancer(*arguments, fabrique=None):
    sortie, erreurs = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreurs):
        code = ki.main(list(arguments), fabrique=fabrique)
    return code, sortie.getvalue() + erreurs.getvalue()


class FausseConnexion:
    """Remplace une connexion PostgreSQL : enregistre les ordres SQL, rend des lignes prévues pour les lectures."""

    def __init__(self, livres=()):
        self.ordres = []
        self.read_only = False
        self.livres = list(livres)

    def execute(self, sql, params=None):
        self.ordres.append(" ".join(sql.split()))
        resultat = FausseConnexion.Resultat([])
        if "FROM knowledge.books b" in sql:
            resultat = FausseConnexion.Resultat(self.livres)
        return resultat

    def commit(self):
        self.ordres.append("COMMIT")

    def rollback(self):
        self.ordres.append("ROLLBACK")

    def close(self):
        pass

    class Resultat(list):
        def fetchone(self):
            return self[0] if self else None


class SansBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.chemin = Path(self.tmp.name) / "library.sqlite"
        self.comptes = demo.build_sqlite(self.chemin)

    def test_copie_dans_l_ordre_des_identifiants_sqlite_empreinte_par_position(self):
        """Les égalités de classement se départagent par id : la copie suit l'ordre des identifiants SQLite (un passage ajouté après coup, de
        position 0, vient en dernier), alors que l'empreinte reste calculée par position, comparable des deux côtés."""
        écriture = sqlite3.connect(self.chemin)
        livre_id = écriture.execute("SELECT id FROM books WHERE file_name = 'discovery-notes.md'").fetchone()[0]
        écriture.execute("INSERT INTO chunks (book_id, position, section, text, embedding, kind, ref) VALUES (?, 0, 'Ajout', 'Passage ajouté', ?, 'texte', '{}')",
                         (livre_id, demo.chunk_blob(1.0)))
        écriture.commit()
        écriture.close()
        connexion = ki.ouvrir_sqlite(self.chemin)
        par_id = [(p[0], p[1]) for p in ki.passages_sqlite(connexion, livre_id, par_identifiant=True)]
        par_position = [(p[0], p[1]) for p in ki.passages_sqlite(connexion, livre_id)]
        connexion.close()
        self.assertEqual([p for p, _ in par_id], [0, 1, 2, 3, 0])            # l'ajout, de position 0, vient en dernier
        self.assertEqual(par_id[-1][1], "Ajout")
        self.assertEqual([p for p, _ in par_position], [0, 0, 1, 2, 3])      # l'empreinte, elle, suit la position puis l'identifiant
        self.assertEqual(par_position[1][1], "Ajout")

    def test_sqlite_ouvert_en_lecture_seule(self):
        connexion = ki.ouvrir_sqlite(self.chemin)
        with self.assertRaises(sqlite3.OperationalError):
            connexion.execute("DELETE FROM chunks")
        with self.assertRaises(sqlite3.OperationalError):
            connexion.execute("INSERT INTO books (file_name, title, sha256, collections, model, indexed_at) VALUES ('x','x','x','x','x',0)")
        connexion.close()

    def test_index_introuvable(self):
        with self.assertRaises(ki.ErreurImport):
            ki.ouvrir_sqlite(Path(self.tmp.name) / "absent.sqlite")

    def test_livres_sqlite_collections_canoniques_et_comptes(self):
        connexion = ki.ouvrir_sqlite(self.chemin)
        livres = ki.livres_sqlite(connexion)
        connexion.close()
        self.assertEqual(set(livres), set(demo.BOOKS))
        self.assertEqual(livres["billet-recent.md"].collections, frozenset({"watch"}))
        self.assertEqual(livres["article-propre.md"].collections, frozenset({watch_paths.OWN_COLLECTION, "watch"}))
        self.assertEqual(sum(l.passages for l in livres.values()), self.comptes["chunks"])
        self.assertEqual(sum(l.figures for l in livres.values()), self.comptes["figures"])
        self.assertEqual(ki.comptes_collections(livres), self.comptes["collections"])
        self.assertEqual(ki.collections_canoniques("flow|watch|"), frozenset({"flow", "watch"}))

    def test_aller_retour_float16_litteral_halfvec(self):
        generateur = np.random.default_rng(7)
        speciaux = np.array([0.0, -0.0, 1.0, -1.0, 2.0 ** -24, -(2.0 ** -24), 2.0 ** -14, 65504.0, -65504.0, 1 / 3, 0.1, 6.1e-5, 0.999], dtype=np.float32)
        vecteurs = [np.resize(speciaux, ki.DIMENSIONS).astype(np.float16)]
        vecteurs += [(generateur.standard_normal(ki.DIMENSIONS) * s).astype(np.float16) for s in (1.0, 0.03, 1e-4, 100.0)]
        unitaire = generateur.standard_normal(ki.DIMENSIONS)
        vecteurs.append((unitaire / np.linalg.norm(unitaire)).astype(np.float16))
        for vecteur in vecteurs:
            blob = vecteur.tobytes()
            self.assertEqual(ki.litteral_vers_blob(ki.blob_vers_litteral(blob)), blob)

    def test_vecteur_de_mauvaise_taille_refuse_sans_texte(self):
        with self.assertRaises(ki.ErreurImport) as contexte:
            ki.blob_vers_litteral(b"\x00" * 10)
        self.assertIn("dimensions", str(contexte.exception))

    def test_empreinte(self):
        v = demo.chunk_blob(0.5)
        base_ = [(0, "S", "t", "texte", {"b": 1, "a": 2}, v), (1, "S", "u", "texte", {}, v)]
        meme = [(0, "S", "t", "text", {"a": 2, "b": 1}, v), (1, "S", "u", "text", {}, v)]       # kind texte = text, ordre des clés sans effet
        self.assertEqual(ki.empreinte(base_), ki.empreinte(meme))
        self.assertNotEqual(ki.empreinte(base_), ki.empreinte(list(reversed(base_))))
        modifie = [(0, "S", "t2", "texte", {"b": 1, "a": 2}, v), base_[1]]
        self.assertNotEqual(ki.empreinte(base_), ki.empreinte(modifie))
        autre_vecteur = [(0, "S", "t", "texte", {"b": 1, "a": 2}, demo.chunk_blob(0.51)), base_[1]]
        self.assertNotEqual(ki.empreinte(base_), ki.empreinte(autre_vecteur))
        self.assertNotEqual(ki.empreinte(base_), ki.empreinte(base_[:1]))

    def test_empreinte_sqlite_stable_d_un_appel_a_l_autre(self):
        connexion = ki.ouvrir_sqlite(self.chemin)
        livre = ki.livres_sqlite(connexion)["atelier-des-flux.md"]
        self.assertEqual(ki.empreinte_sqlite(connexion, livre), ki.empreinte_sqlite(connexion, livre))
        connexion.close()

    def test_plan(self):
        def sq(nom, sha="s", passages=2):
            return ki.LivreSqlite(1, nom, "T", sha, "m", 100.0, "{}", frozenset({"flow"}), passages, 0)

        def pg(nom, sha="s", passages=2):
            return ki.LivrePg(1, nom, "T", sha, "m", 100.4, "{}", frozenset({"flow"}), passages, 0)
        livres_sq = {"a": sq("a"), "b": sq("b", sha="nouveau"), "c": sq("c"), "d": sq("d", passages=3)}
        livres_pg = {"a": pg("a"), "b": pg("b"), "d": pg("d"), "e": pg("e")}
        plan = ki.etablir_plan(None, None, livres_sq, livres_pg, deep=False, garder_retires=False)
        self.assertEqual((plan.ajouter, plan.remplacer, plan.supprimer, plan.inchanges), (["c"], ["b", "d"], ["e"], ["a"]))
        self.assertEqual(plan.resume(), "1 à ajouter, 2 à remplacer, 1 à supprimer, 1 inchangés")
        garde = ki.etablir_plan(None, None, livres_sq, livres_pg, deep=False, garder_retires=True)
        self.assertEqual(garde.supprimer, [])

    def test_dry_run_connexion_en_lecture_seule_et_aucun_ordre_d_ecriture(self):
        fausse = FausseConnexion()
        code, sortie = lancer("import", "--dry-run", "--sqlite", str(self.chemin), fabrique=lambda nom: fausse)
        self.assertEqual(code, 0)
        self.assertIn("5 à ajouter, 0 à remplacer, 0 à supprimer, 0 inchangés", sortie)
        self.assertIn("Rien n'a été écrit", sortie)
        self.assertTrue(fausse.read_only)
        for ordre in fausse.ordres:
            self.assertTrue(ordre.startswith("SELECT"), ordre)
        for chunk in demo.CHUNKS:
            self.assertNotIn(chunk[3], sortie)                      # aucun texte de livre dans la sortie

    def test_index_sqlite_vide_face_a_une_base_remplie_refuse(self):
        vide = Path(self.tmp.name) / "vide.sqlite"
        import pmzilla_lab_library as library
        connexion = sqlite3.connect(vide)
        connexion.executescript(library.SCHEMA)
        connexion.close()
        ligne = (1, "x.md", "X", "abc", "bge-m3", 1.0, {}, 0, 0)
        fausse = FausseConnexion(livres=[ligne])
        code, sortie = lancer("import", "--dry-run", "--sqlite", str(vide), fabrique=lambda nom: fausse)
        self.assertEqual(code, 1)
        self.assertIn("--allow-empty", sortie)

    def test_base_injoignable_code_2_et_message(self):
        def inaccessible(nom):
            raise db.ErreurBase("Connexion à la base impossible : refusée.")
        for commande in (["import", "--dry-run"], ["import"], ["verify"], ["status"]):
            code, sortie = lancer(*commande, "--sqlite", str(self.chemin), fabrique=inaccessible)
            self.assertEqual(code, 2, commande)
            self.assertIn("bash tools/db_up.sh", sortie)

    def test_sqlite_introuvable_code_1(self):
        code, sortie = lancer("verify", "--sqlite", str(Path(self.tmp.name) / "absent.sqlite"), fabrique=lambda nom: FausseConnexion())
        self.assertEqual(code, 1)
        self.assertIn("introuvable", sortie)

    def test_aucune_importation_d_embed_ni_d_appel_reseau(self):
        source = (RACINE / "tools" / "knowledge_import.py").read_text(encoding="utf-8")
        self.assertNotIn("embed(", source)
        self.assertNotIn("httpx.", source)
        self.assertNotIn("PASSWORD", source.replace("mot de passe", ""))


class ConnexionSonde(FausseConnexion):
    """Fausse connexion dont les requêtes plein texte (sonde BM25) réussissent ou lèvent l'erreur demandée ; `quand` : fragment de SQL qui la déclenche."""

    def __init__(self, erreur=None, quand="fts_text"):
        super().__init__()
        self.erreur, self.quand, self.requetes = erreur, quand, []

    def execute(self, sql, params=None):
        resultat = super().execute(sql, params)
        if "fts_text" in sql:
            self.requetes.append((" ".join(sql.split()), params))
            if self.erreur and self.quand in sql:
                raise self.erreur
            resultat.fetchall = lambda: [(1,)]
        return resultat


class SondeBm25(unittest.TestCase):
    """Sonde de l'index BM25 de verify (sans base) : succès, InternalError d'un index abîmé, autre erreur, et codes de sortie."""
    ABIME = psycopg.errors.InternalError_("bitmap intersection stream (consumer 0, segment 7) claimed twice")

    def verify(self, connexion):
        with mock.patch.object(ki, "livres_sqlite", return_value={}), mock.patch.object(ki, "livres_pg", return_value={}):
            return lancer("verify", "--sqlite", str(self.chemin), fabrique=lambda nom: connexion)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.chemin = Path(self.tmp.name) / "library.sqlite"
        demo.build_sqlite(self.chemin)

    def test_succes_deux_requetes_sous_le_role_de_lecture_et_code_0(self):
        connexion = ConnexionSonde()
        code, sortie = self.verify(connexion)
        self.assertEqual(code, 0, sortie)
        self.assertIn("index BM25 lisible", sortie)
        self.assertEqual(len(connexion.requetes), 2)
        self.assertNotIn("c.kind", connexion.requetes[0][0])                       # sans filtre de type
        self.assertIn("c.kind = ANY", connexion.requetes[1][0])                    # puis filtrée par type
        self.assertEqual(connexion.requetes[1][1][1], ["figure"])
        self.assertIn("SET ROLE pmzilla_knowledge_ro", connexion.ordres)           # le rôle de lecture habituel
        self.assertGreaterEqual(connexion.ordres.count("ROLLBACK"), 2)             # le rôle est défait après chaque requête

    def test_internal_error_index_bm25_illisible_code_3(self):
        connexion = ConnexionSonde(self.ABIME, quand="c.kind")                       # seule la requête filtrée par type échoue, comme sur la vraie base
        code, sortie = self.verify(connexion)
        self.assertEqual(code, ki.CODE_BM25_ILLISIBLE)
        self.assertEqual(ki.CODE_BM25_ILLISIBLE, 3)
        self.assertIn("index BM25 illisible", sortie)
        self.assertIn("type figure : InternalError_", sortie)
        self.assertIn("claimed twice", sortie)
        self.assertIn("Damaged BM25 index", sortie)
        self.assertNotIn("Vérification réussie", sortie)
        self.assertEqual(connexion.ordres[-1], "ROLLBACK")                          # la transaction en erreur est annulée

    def test_autre_erreur_de_la_sonde_meme_echec_nomme(self):
        code, sortie = self.verify(ConnexionSonde(RuntimeError("boum")))
        self.assertEqual(code, 3)
        self.assertIn("index BM25 illisible", sortie)
        self.assertIn("sans filtre : RuntimeError (boum)", sortie)

    def test_ecart_de_copie_seul_garde_le_code_1(self):
        connexion = ConnexionSonde()
        with mock.patch.object(ki, "livres_pg", return_value={}):                     # SQLite a des livres, la base aucun
            code, sortie = lancer("verify", "--sqlite", str(self.chemin), fabrique=lambda nom: connexion)
        self.assertEqual(code, 1)
        self.assertNotIn("index BM25 illisible", sortie)

    def test_index_illisible_et_ecart_les_deux_affiches_code_3(self):
        with mock.patch.object(ki, "livres_pg", return_value={}):
            code, sortie = lancer("verify", "--sqlite", str(self.chemin), fabrique=lambda nom: ConnexionSonde(self.ABIME))
        self.assertEqual(code, 3)
        self.assertIn("index BM25 illisible", sortie)
        self.assertIn("écart(s)", sortie)


class Vecteurs(unittest.TestCase):
    """verify --vectors : comparaison des vecteurs relus (sans base ; les fonctions ne manipulent que des nombres)."""

    def test_vecteurs_identiques(self):
        v = demo.vector(0.3)
        m = ki.comparer_vecteurs([(v, v.copy()), (demo.vector(1.1), demo.vector(1.1))])
        self.assertEqual((m["n"], m["ecart_max"], m["nuls"]), (2, 0.0, 0))
        self.assertAlmostEqual(m["cosinus_min"], 1.0, places=6)
        self.assertAlmostEqual(m["norme_min"], 1.0, places=5)

    def test_ecart_et_cosinus_detectes(self):
        a = demo.vector(0.3)
        b = demo.vector(0.3 + 0.2)               # un décodage faux (octets mal lus, dimension décalée) change l'angle
        m = ki.comparer_vecteurs([(a, b)])
        self.assertGreater(m["ecart_max"], 0.1)
        self.assertLess(m["cosinus_min"], 0.99)

    def test_vecteur_nul_signale_et_cosinus_negatif_si_un_seul_est_nul(self):
        zero = np.zeros(demo.DIMENSIONS, dtype=np.float32)
        m = ki.comparer_vecteurs([(zero, zero.copy())])
        self.assertEqual(m["nuls"], 1)
        self.assertEqual(m["cosinus_min"], 1.0)            # deux vecteurs nuls identiques : pas d'écart
        m = ki.comparer_vecteurs([(zero, demo.vector(0.3))])
        self.assertEqual(m["cosinus_min"], -1.0)
        self.assertEqual(ki.comparer_vecteurs([])["n"], 0)

    def test_normes_extremes_d_un_vecteur_non_normalise(self):
        grand = 2 * demo.vector(0.3)
        m = ki.comparer_vecteurs([(grand, grand.copy()), (demo.vector(0.1), demo.vector(0.1))])
        self.assertAlmostEqual(m["norme_max"], 2.0, places=5)
        self.assertAlmostEqual(m["norme_min"], 1.0, places=5)

    def test_resume_sans_texte(self):
        texte = ki.resume_vecteurs(ki.comparer_vecteurs([(demo.vector(0.3), demo.vector(0.3))]))
        self.assertIn("écart maximal 0", texte)
        self.assertIn("cosinus minimal 1.000000000", texte)
        self.assertIn("vecteurs nuls ou non finis : 0", texte)

    def test_option_vectors_et_seed_de_la_ligne_de_commande(self):
        args = ki.analyseur().parse_args(["verify", "--vectors", "50", "--seed", "3"])
        self.assertEqual((args.vectors, args.seed), (50, 3))
        self.assertEqual(ki.analyseur().parse_args(["verify"]).vectors, 0)


class AvecBase(unittest.TestCase):
    def setUp(self):
        if not base.BASE_DISPONIBLE:
            self.skipTest(base.MESSAGE_SAUT)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.chemin = Path(self.tmp.name) / "library.sqlite"
        self.comptes = demo.build_sqlite(self.chemin)
        self.nom_base = "pmzilla_test_" + secrets.token_hex(6)
        self.admin = db.connect(base.URL_BASE, password=base.MOT_DE_PASSE, autocommit=True)
        self.addCleanup(self._supprimer)
        self.admin.execute(f'CREATE DATABASE "{self.nom_base}"')
        self.url = base.url_vers(self.nom_base)
        self.ouvertes = []
        c = self.conn()
        db.migrer(c, db.lister_migrations(db.DOSSIER_MIGRATIONS))
        c.commit()
        c.autocommit = True

    def _supprimer(self):
        for c in self.ouvertes:
            with contextlib.suppress(Exception):
                c.close()
        with contextlib.suppress(Exception):
            self.admin.execute(f'DROP DATABASE IF EXISTS "{self.nom_base}" WITH (FORCE)')
        self.admin.close()

    def conn(self):
        c = db.connect(self.url, password=base.MOT_DE_PASSE)
        self.ouvertes.append(c)
        return c

    def fabrique(self, nom):
        return db.connect(self.url, password=base.MOT_DE_PASSE)

    def lancer(self, *arguments):
        return lancer(*arguments, "--sqlite", str(self.chemin), fabrique=self.fabrique)

    def lecture(self, sql, params=None):
        return self.ouvertes[0].execute(sql, params).fetchall()

    def modifier_sqlite(self, *ordres):
        connexion = sqlite3.connect(self.chemin)
        for ordre in ordres:
            connexion.execute(*ordre) if isinstance(ordre, tuple) else connexion.execute(ordre)
        connexion.commit()
        connexion.close()

    def test_verify_vectors_apres_import(self):
        self.assertEqual(self.lancer("import")[0], 0)
        code, sortie = self.lancer("verify", "--vectors", "20", "--seed", "1")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Vecteurs relus : 20", sortie)
        self.assertIn("écart maximal 0", sortie)
        import re
        cosinus = float(re.search(r"cosinus minimal ([0-9.]+)", sortie).group(1))
        self.assertGreaterEqual(cosinus, 0.9999)          # des vecteurs identiques, en float32 : 0,99999995 et non exactement 1

    def test_verify_vectors_detecte_un_vecteur_altere(self):
        self.assertEqual(self.lancer("import")[0], 0)
        autre = "[" + ",".join(["0", "1"] + ["0"] * 1022) + "]"
        self.ouvertes[0].execute("UPDATE knowledge.chunks SET embedding = %s::halfvec", (autre,))     # tous les vecteurs sont faux
        code, sortie = self.lancer("verify", "--vectors", "20", "--seed", "1")
        self.assertEqual(code, 1, sortie)
        self.assertIn("vecteurs : écart maximal", sortie)

    def test_premier_import_comptes_et_verification(self):
        code, sortie = self.lancer("import")
        self.assertEqual(code, 0, sortie)
        self.assertIn("5 à ajouter", sortie)
        self.assertEqual(self.lecture("SELECT count(*) FROM knowledge.books")[0][0], self.comptes["books"])
        self.assertEqual(self.lecture("SELECT count(*) FROM knowledge.chunks")[0][0], self.comptes["chunks"])
        self.assertEqual(self.lecture("SELECT count(*) FROM knowledge.chunks WHERE kind = 'figure'")[0][0], self.comptes["figures"])
        self.assertEqual({r[0] for r in self.lecture("SELECT name FROM knowledge.collections")}, set(self.comptes["collections"]))
        self.assertEqual({r[0] for r in self.lecture("SELECT DISTINCT kind FROM knowledge.chunks")}, {"text", "figure"})
        code, sortie = self.lancer("verify")
        self.assertEqual(code, 0, sortie)
        self.assertIn("empreintes identiques", sortie)

    def test_copie_fidele_vecteur_ref_et_meta(self):
        self.lancer("import")
        sq = ki.ouvrir_sqlite(self.chemin)
        attendu = {(l, p): bytes(b) for l, p, b in sq.execute(
            "SELECT b.file_name, c.position, c.embedding FROM chunks c JOIN books b ON b.id = c.book_id")}
        sq.close()
        for nom, position, vecteur in self.lecture(
                "SELECT b.file_name, c.position, c.embedding::text FROM knowledge.chunks c JOIN knowledge.books b ON b.id = c.book_id"):
            self.assertEqual(ki.litteral_vers_blob(vecteur), attendu[(nom, position)], (nom, position))
        ref = self.lecture("SELECT ref FROM knowledge.chunks c JOIN knowledge.books b ON b.id = c.book_id "
                           "WHERE b.file_name = 'atelier-des-flux.md' AND c.kind = 'figure'")[0][0]
        self.assertEqual(ref["label"], "Figure 1.1")
        meta = self.lecture("SELECT meta, author, published_on FROM knowledge.books WHERE file_name = 'billet-recent.md'")[0]
        self.assertEqual(meta[0]["url"], "https://exemple.test/billet-recent")
        self.assertEqual(meta[1], "Blog Fictif")
        self.assertEqual(meta[2], demo.today_minus(3))

    def test_second_import_ne_change_rien(self):
        self.lancer("import")
        avant = self.lecture("SELECT id FROM knowledge.chunks ORDER BY id")
        code, sortie = self.lancer("import")
        self.assertEqual(code, 0)
        self.assertIn("0 à ajouter, 0 à remplacer, 0 à supprimer, 5 inchangés", sortie)
        self.assertEqual(self.lecture("SELECT id FROM knowledge.chunks ORDER BY id"), avant)       # aucun passage recréé
        code, sortie = self.lancer("import", "--deep")
        self.assertIn("5 inchangés", sortie)

    def test_livre_modifie_remplace_en_entier(self):
        self.lancer("import")
        self.modifier_sqlite(("UPDATE books SET sha256 = 'nouveau' WHERE file_name = 'billet-recent.md'",),
                             ("UPDATE chunks SET text = 'Texte inventé remplacé.' WHERE book_id = (SELECT id FROM books WHERE file_name = 'billet-recent.md') AND position = 0",))
        code, sortie = self.lancer("import")
        self.assertEqual(code, 0, sortie)
        self.assertIn("1 à remplacer", sortie)
        self.assertIn("4 inchangés", sortie)
        self.assertEqual(self.lecture("SELECT sha256 FROM knowledge.books WHERE file_name = 'billet-recent.md'")[0][0], "nouveau")
        textes = {r[0] for r in self.lecture("SELECT text FROM knowledge.chunks c JOIN knowledge.books b ON b.id = c.book_id WHERE b.file_name = 'billet-recent.md'")}
        self.assertIn("Texte inventé remplacé.", textes)
        self.assertEqual(self.lecture("SELECT count(*) FROM knowledge.chunks")[0][0], self.comptes["chunks"])
        self.assertEqual(self.lancer("verify")[0], 0)

    def test_livre_retire_supprime_sauf_keep_removed(self):
        self.lancer("import")
        self.modifier_sqlite("DELETE FROM chunks WHERE book_id = (SELECT id FROM books WHERE file_name = 'billet-ancien.md')",
                             "DELETE FROM books WHERE file_name = 'billet-ancien.md'")
        code, sortie = self.lancer("import", "--keep-removed")
        self.assertEqual(code, 0, sortie)
        self.assertIn("0 à supprimer", sortie)
        self.assertEqual(self.lecture("SELECT count(*) FROM knowledge.books")[0][0], 5)
        code, sortie = self.lancer("import")
        self.assertIn("1 à supprimer", sortie)
        self.assertEqual(self.lecture("SELECT count(*) FROM knowledge.books")[0][0], 4)
        self.assertEqual(self.lecture("SELECT count(*) FROM knowledge.chunks WHERE book_id NOT IN (SELECT id FROM knowledge.books)")[0][0], 0)
        self.assertEqual(self.lancer("verify")[0], 0)

    def test_collection_orpheline_retiree(self):
        self.lancer("import")
        self.modifier_sqlite("UPDATE books SET collections = 'watch' WHERE file_name = 'article-propre.md'")
        self.lancer("import")
        self.assertNotIn(watch_paths.OWN_COLLECTION, {r[0] for r in self.lecture("SELECT name FROM knowledge.collections")})

    def test_verify_echoue_apres_alteration_et_import_deep_repare(self):
        self.lancer("import")
        self.ouvertes[0].execute("UPDATE knowledge.chunks SET text = 'altéré' WHERE book_id = "
                                 "(SELECT id FROM knowledge.books WHERE file_name = 'discovery-notes.md') AND position = 1")
        code, sortie = self.lancer("verify")
        self.assertEqual(code, 1)
        self.assertIn("discovery-notes.md", sortie)
        self.assertIn("empreinte", sortie)
        self.assertNotIn("altéré", sortie)
        code, sortie = self.lancer("import")                              # sans --deep : comptes identiques, rien vu
        self.assertIn("5 inchangés", sortie)
        code, sortie = self.lancer("import", "--deep")
        self.assertIn("1 à remplacer", sortie)
        self.assertEqual(self.lancer("verify")[0], 0)

    def test_verify_signale_un_livre_absent_et_un_vecteur_altere(self):
        self.lancer("import")
        self.ouvertes[0].execute("DELETE FROM knowledge.books WHERE file_name = 'billet-ancien.md'")
        code, sortie = self.lancer("verify")
        self.assertEqual(code, 1)
        self.assertIn("absent de la base : billet-ancien.md", sortie)

    def test_dry_run_n_ecrit_rien(self):
        code, sortie = self.lancer("import", "--dry-run")
        self.assertEqual(code, 0, sortie)
        self.assertIn("5 à ajouter", sortie)
        for table in ("books", "chunks", "collections", "book_collections"):
            self.assertEqual(self.lecture(f"SELECT count(*) FROM knowledge.{table}")[0][0], 0, table)
        self.lancer("import")
        self.modifier_sqlite("DELETE FROM chunks WHERE book_id = (SELECT id FROM books WHERE file_name = 'billet-ancien.md')",
                             "DELETE FROM books WHERE file_name = 'billet-ancien.md'",
                             "UPDATE books SET sha256 = 'autre' WHERE file_name = 'discovery-notes.md'")
        code, sortie = self.lancer("import", "--dry-run")
        self.assertIn("1 à remplacer, 1 à supprimer", sortie)
        self.assertEqual(self.lecture("SELECT count(*) FROM knowledge.books")[0][0], 5)
        self.assertEqual(self.lecture("SELECT sha256 FROM knowledge.books WHERE file_name = 'discovery-notes.md'")[0][0],
                         __import__("hashlib").sha256(b"discovery-notes.md").hexdigest())

    def test_index_vide_refuse_sans_allow_empty(self):
        self.lancer("import")
        self.modifier_sqlite("DELETE FROM chunks", "DELETE FROM books")
        code, sortie = self.lancer("import")
        self.assertEqual(code, 1)
        self.assertEqual(self.lecture("SELECT count(*) FROM knowledge.books")[0][0], 5)
        code, sortie = self.lancer("import", "--allow-empty")
        self.assertEqual(code, 0)
        self.assertEqual(self.lecture("SELECT count(*) FROM knowledge.books")[0][0], 0)

    def test_echec_de_copie_ne_laisse_rien_de_partiel(self):
        self.modifier_sqlite("UPDATE chunks SET embedding = x'0102' WHERE book_id = (SELECT id FROM books WHERE file_name = 'billet-ancien.md') AND position = 1")
        code, sortie = self.lancer("import")
        self.assertEqual(code, 1)
        self.assertIn("billet-ancien.md", sortie)
        self.assertEqual(self.lecture("SELECT count(*) FROM knowledge.books WHERE file_name = 'billet-ancien.md'")[0][0], 0)
        self.assertEqual(self.lecture("SELECT count(*) FROM knowledge.chunks c WHERE NOT EXISTS (SELECT 1 FROM knowledge.books b WHERE b.id = c.book_id)")[0][0], 0)

    def test_status_comptes_seulement(self):
        self.lancer("import")
        code, sortie = self.lancer("status")
        self.assertEqual(code, 0)
        self.assertIn("Base : 5 livres, 14 passages, 2 figures, 5 collections.", sortie)
        self.assertIn("SQLite : 5 livres, 14 passages, 2 figures, 5 collections.", sortie)


if __name__ == "__main__":
    unittest.main()
