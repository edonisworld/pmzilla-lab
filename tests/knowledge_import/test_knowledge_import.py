"""
Tests de tools/knowledge_import.py, comparateur de parité (R-37, design.md D6 et D7), sur la bibliothèque inventée de
tests/fixtures_library/demo_library.py.

    uv run --with "psycopg[binary]" --with numpy --with httpx --with pyyaml python -m unittest discover -s tests/knowledge_import -v

Sans base : import refusé sans connexion, lecture seule de SQLite, empreintes (avec et sans vecteurs), comparaison de vecteurs, parité sur
deux index SQLite inventés (l'un tient le rôle de la base), journal de parité dans un dossier de données temporaire. Avec base : base
jetable de tests/library_backend/pg_demo.py (chargée par de simples INSERT), sautée si la base manque. Aucun texte de livre réel, aucun
appel à Ollama, jamais le dossier de données réel.
"""
import contextlib
import datetime as dt
import io
import os
import re
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(RACINE / "tests" / "fixtures_library"))
sys.path.insert(0, str(RACINE / "tests" / "db"))
sys.path.insert(0, str(RACINE / "tests" / "library_backend"))
import knowledge_import as ki  # noqa: E402
import watch_paths  # noqa: E402
import demo_library as demo  # noqa: E402
import test_db as base  # noqa: E402  (BASE_DISPONIBLE, mot de passe de test)
from test_db import db  # noqa: E402
import pg_demo  # noqa: E402

JOUR = dt.date(2026, 10, 6)          # date du jour simulée des comparaisons
DEBUT = dt.date(2026, 10, 1)         # début de la fenêtre de parité
RECENT = dt.datetime(2026, 10, 3, 9, 0).timestamp()      # indexé après le début
LIVRE = "discovery-notes.md"


def lancer(*arguments, fabrique=None, ouvrir_base=None):
    sortie, erreurs = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreurs):
        code = ki.main(list(arguments), fabrique=fabrique, ouvrir_base=ouvrir_base)
    return code, sortie.getvalue() + erreurs.getvalue()


def modifier(chemin, *ordres):
    connexion = sqlite3.connect(chemin)
    for ordre in ordres:
        connexion.execute(*ordre) if isinstance(ordre, tuple) else connexion.execute(ordre)
    connexion.commit()
    connexion.close()


def decaler_vecteurs(chemin, nom, decalage):
    """Remplace les vecteurs d'un livre par ceux de l'angle d'origine décalé (cosinus des deux = cos(decalage))."""
    angles = {position: angle for fichier, position, _, _, angle, _, _ in demo.CHUNKS if fichier == nom}
    ordres = [("UPDATE chunks SET embedding = ? WHERE position = ? AND book_id = (SELECT id FROM books WHERE file_name = ?)",
               (demo.chunk_blob(angle + decalage), position, nom)) for position, angle in angles.items()]
    modifier(chemin, *ordres)


class FausseConnexion:
    """Remplace une connexion PostgreSQL : enregistre les ordres SQL, rend des lignes prévues pour la liste des livres."""

    def __init__(self, livres=()):
        self.ordres = []
        self.read_only = False
        self.livres = list(livres)

    def execute(self, sql, params=None):
        self.ordres.append(" ".join(sql.split()))
        return FausseConnexion.Resultat(self.livres if "FROM knowledge.books b" in sql else [])

    def commit(self):
        self.ordres.append("COMMIT")

    def rollback(self):
        self.ordres.append("ROLLBACK")

    def close(self):
        pass

    class Resultat(list):
        def fetchone(self):
            return self[0] if self else None


class AvecDossierDeDonnees(unittest.TestCase):
    """Dossier de données temporaire (PMZILLA_LAB_DATA), index SQLite inventé dedans."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.donnees = Path(self.tmp.name) / "donnees"
        self.donnees.mkdir()
        environnement = mock.patch.dict(os.environ, {"PMZILLA_LAB_DATA": str(self.donnees)})
        environnement.start()
        self.addCleanup(environnement.stop)
        self.chemin = self.donnees / "library.sqlite"
        self.comptes = demo.build_sqlite(self.chemin)


class SansBase(AvecDossierDeDonnees):
    def test_import_refuse_sans_aucune_connexion(self):
        for options in ([], ["--dry-run"], ["--deep"], ["--keep-removed", "--allow-empty"]):
            appels = []
            with mock.patch.object(ki.db, "connect") as connect, mock.patch.object(ki, "ouvrir_sqlite") as ouvrir_sqlite:
                code, sortie = lancer("import", *options, fabrique=lambda nom: appels.append(nom))
            self.assertEqual(code, 1, options)
            self.assertIn("import retiré : l'indexeur écrit directement dans la base (pmzilla_lab_library.py index)", sortie)
            connect.assert_not_called()
            ouvrir_sqlite.assert_not_called()
            self.assertEqual(appels, [])
        self.assertEqual(sorted(p.name for p in self.donnees.iterdir()), ["library.sqlite"])       # rien n'est écrit

    def test_le_code_de_copie_et_la_sonde_ont_disparu(self):
        for nom in ("commande_import", "copier_livre", "etablir_plan", "sonde_bm25", "CODE_BM25_ILLISIBLE", "ROLE_ECRITURE"):
            self.assertFalse(hasattr(ki, nom), nom)
        source = (RACINE / "tools" / "knowledge_import.py").read_text(encoding="utf-8")
        for fragment in ("fts_text", "INSERT", "DELETE", "UPDATE ", "embed(", "httpx.", "pmzilla_lab_library as"):
            self.assertNotIn(fragment, source)
        self.assertNotIn("PASSWORD", source.replace("mot de passe", ""))

    def test_connexion_de_la_base_en_lecture_seule_sous_le_role_de_lecture(self):
        livre = (1, "x.md", "X", "abc", "bge-m3", 1.0, {}, 0, 0)
        fausse = FausseConnexion(livres=[livre])
        code, sortie = lancer("status", fabrique=lambda nom: fausse)
        self.assertEqual(code, 0, sortie)
        self.assertTrue(fausse.read_only)
        self.assertEqual(fausse.ordres[:2], ["SET ROLE pmzilla_knowledge_ro", "COMMIT"])
        for ordre in fausse.ordres[2:]:
            self.assertTrue(ordre.startswith("SELECT"), ordre)
        self.assertIn("Base : 1 livres, 0 passages, 0 figures, 0 collections.", sortie)
        self.assertIn("SQLite : 5 livres, 14 passages, 2 figures, 5 collections.", sortie)

    def test_sqlite_par_defaut_dans_le_dossier_de_donnees(self):
        self.assertEqual(ki.chemin_sqlite(ki.analyseur().parse_args(["verify"])), self.chemin)

    def test_sqlite_ouvert_en_lecture_seule(self):
        connexion = ki.ouvrir_sqlite(self.chemin)
        with self.assertRaises(sqlite3.OperationalError):
            connexion.execute("DELETE FROM chunks")
        with self.assertRaises(sqlite3.OperationalError):
            connexion.execute("INSERT INTO books (file_name, title, sha256, collections, model, indexed_at) VALUES ('x','x','x','x','x',0)")
        connexion.close()

    def test_index_introuvable(self):
        absent = Path(self.tmp.name) / "absent.sqlite"
        with self.assertRaises(ki.ErreurImport):
            ki.ouvrir_sqlite(absent)
        self.assertFalse(absent.exists())

    def test_livres_sqlite_collections_canoniques_et_comptes(self):
        modifier(self.chemin, "UPDATE books SET collections = 'veille' WHERE file_name = 'billet-ancien.md'")
        cote = ki.CoteSqlite(ki.ouvrir_sqlite(self.chemin))
        livres = cote.livres()
        cote.close()
        self.assertEqual(set(livres), set(demo.BOOKS))
        self.assertEqual(livres["billet-ancien.md"].collections, frozenset({"watch"}))        # ancien nom compté sous le nom actuel
        self.assertEqual(livres["article-propre.md"].collections, frozenset({watch_paths.OWN_COLLECTION, "watch"}))
        self.assertEqual(ki.totaux(livres), {"livres": 5, "passages": self.comptes["chunks"], "figures": self.comptes["figures"],
                                             "collections": 5})
        self.assertEqual(ki.comptes_collections(livres), self.comptes["collections"])
        self.assertEqual(ki.collections_canoniques("flow|watch|"), frozenset({"flow", "watch"}))
        self.assertEqual(ki.collections_canoniques(["veille", "flow"]), frozenset({"flow", "watch"}))

    def test_empreinte(self):
        v = demo.chunk_blob(0.5)
        base_ = [(0, "S", "t", "texte", {"b": 1, "a": 2}, v), (1, "S", "u", "texte", {}, v)]
        meme = [(0, "S", "t", "text", {"a": 2, "b": 1}, v), (1, "S", "u", "text", {}, v)]       # kind texte = text, ordre des clés sans effet
        self.assertEqual(ki.empreinte(base_), ki.empreinte(meme))
        self.assertNotEqual(ki.empreinte(base_), ki.empreinte(list(reversed(base_))))
        modifie = [(0, "S", "t2", "texte", {"b": 1, "a": 2}, v), base_[1]]
        self.assertNotEqual(ki.empreinte(base_), ki.empreinte(modifie))
        self.assertNotEqual(ki.empreinte(base_, vecteurs=False), ki.empreinte(modifie, vecteurs=False))
        autre_vecteur = [(0, "S", "t", "texte", {"b": 1, "a": 2}, demo.chunk_blob(0.51)), base_[1]]
        self.assertNotEqual(ki.empreinte(base_), ki.empreinte(autre_vecteur))
        self.assertEqual(ki.empreinte(base_, vecteurs=False), ki.empreinte(autre_vecteur, vecteurs=False))   # parité : vecteurs ignorés
        self.assertNotEqual(ki.empreinte(base_), ki.empreinte(base_[:1]))

    def test_empreinte_sqlite_stable_d_un_appel_a_l_autre(self):
        cote = ki.CoteSqlite(ki.ouvrir_sqlite(self.chemin))
        livre = cote.livres()["atelier-des-flux.md"]
        self.assertEqual(ki.empreinte(cote.passages(livre)), ki.empreinte(cote.passages(livre)))
        cote.close()

    def test_base_injoignable_code_2_et_message(self):
        def inaccessible(nom):
            raise db.ErreurBase("Connexion à la base impossible : refusée.")
        for commande in (["verify"], ["verify", "--parity", "--since", "2026-10-01"], ["status"]):
            code, sortie = lancer(*commande, fabrique=inaccessible)
            self.assertEqual(code, 2, commande)
            self.assertIn("bash tools/db_up.sh", sortie)
        self.assertFalse((self.donnees / ki.JOURNAL_PARITE).exists())

    def test_sqlite_introuvable_code_1(self):
        code, sortie = lancer("verify", "--sqlite", str(Path(self.tmp.name) / "absent.sqlite"), fabrique=lambda nom: FausseConnexion())
        self.assertEqual(code, 1)
        self.assertIn("introuvable", sortie)

    def test_options_de_la_ligne_de_commande(self):
        args = ki.analyseur().parse_args(["verify", "--vectors", "50", "--seed", "3", "--parity", "--since", "2026-10-01"])
        self.assertEqual((args.vectors, args.seed, args.parity, args.since), (50, 3, True, DEBUT))
        args = ki.analyseur().parse_args(["verify"])
        self.assertEqual((args.vectors, args.parity, args.since), (0, False, None))
        for mauvais in (["verify", "--parity"], ["verify", "--since", "2026-10-01"], ["verify", "--parity", "--since", "01/10/2026"]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                ki.main(mauvais, fabrique=lambda nom: FausseConnexion())


class Parite(AvecDossierDeDonnees):
    """verify --parity sur deux index SQLite inventés : le second tient le rôle de la base (même interface de lecture)."""

    def setUp(self):
        super().setUp()
        self.autre = Path(self.tmp.name) / "base.sqlite"
        demo.build_sqlite(self.autre)
        jour = mock.patch.object(ki, "aujourdhui", return_value=JOUR)
        jour.start()
        self.addCleanup(jour.stop)

    def ouvrir_base(self, nom):
        return ki.CoteSqlite(ki.ouvrir_sqlite(self.autre))

    def verify(self, *options, parite=True):
        arguments = ["verify", *options] + (["--parity", "--since", DEBUT.isoformat()] if parite else [])
        return lancer(*arguments, ouvrir_base=self.ouvrir_base)

    def reindexer(self, chemin, nom=LIVRE, quand=RECENT):
        modifier(chemin, ("UPDATE books SET indexed_at = ? WHERE file_name = ?", (quand, nom)))

    def journal(self):
        return (self.donnees / ki.JOURNAL_PARITE).read_text(encoding="utf-8").splitlines()

    def test_identique_dans_la_tolerance(self):
        self.reindexer(self.chemin)
        self.reindexer(self.autre)
        decaler_vecteurs(self.autre, LIVRE, 0.005)            # cos(0,005) = 0,9999875, au-dessus de la tolérance
        code, sortie = self.verify()
        self.assertEqual(code, 0, sortie)
        self.assertIn("Parité SQLite : identique", sortie)
        self.assertIn("jours identiques consécutifs : 1", sortie)
        self.assertIn("1 livre(s) réindexé(s) des deux côtés, 0 identique(s) à l'octet", sortie)
        self.assertEqual(ki.TOLERANCE_COSINUS, 0.9999)
        lignes = self.journal()
        self.assertEqual(len(lignes), 1)
        self.assertTrue(lignes[0].startswith("2026-10-06 identique livres 5 passages 14 figures 2 collections 5 réindexés 1 "), lignes[0])

    def test_vecteurs_identiques_a_l_octet(self):
        self.reindexer(self.chemin)
        self.reindexer(self.autre)
        code, sortie = self.verify()
        self.assertEqual(code, 0, sortie)
        self.assertIn("1 identique(s) à l'octet", sortie)

    def test_ecart_sous_la_tolerance(self):
        self.reindexer(self.chemin)
        self.reindexer(self.autre)
        decaler_vecteurs(self.autre, LIVRE, 0.05)             # cos(0,05) = 0,99875
        code, sortie = self.verify()
        self.assertEqual(code, 1, sortie)
        self.assertIn("Parité SQLite : écart", sortie)
        self.assertIn("jours identiques consécutifs : 0", sortie)
        self.assertIn("sous la tolérance", sortie)
        self.assertTrue(self.journal()[-1].startswith("2026-10-06 écart "))

    def test_empreinte_sans_vecteurs_pour_un_livre_non_reindexe(self):
        decaler_vecteurs(self.autre, LIVRE, 0.5)              # livres anciens des deux côtés : vecteurs ni comparés ni dans l'empreinte
        code, sortie = self.verify()
        self.assertEqual(code, 0, sortie)
        self.assertIn("aucun vecteur comparé", sortie)
        code, sortie = self.verify(parite=False)              # hors parité, l'empreinte complète voit les vecteurs
        self.assertEqual(code, 1, sortie)
        self.assertIn(f"{LIVRE} : empreinte de contenu différente", sortie)

    def test_livre_reindexe_d_un_seul_cote(self):
        self.reindexer(self.autre)
        decaler_vecteurs(self.autre, LIVRE, 0.5)
        code, sortie = self.verify()
        self.assertEqual(code, 0, sortie)
        self.assertIn("0 livre(s) réindexé(s) des deux côtés", sortie)
        self.assertIn("1 livre(s) réindexé(s) d'un seul côté", sortie)
        modifier(self.autre, ("UPDATE chunks SET text = 'Texte inventé altéré.' WHERE position = 1 AND book_id = "
                              "(SELECT id FROM books WHERE file_name = ?)", (LIVRE,)))
        code, sortie = self.verify()                          # son empreinte sans vecteurs reste comparée
        self.assertEqual(code, 1, sortie)
        self.assertIn(f"{LIVRE} : empreinte de contenu différente", sortie)

    def test_texte_different_nomme_le_livre_sur_la_sortie_jamais_dans_le_journal(self):
        modifier(self.autre, ("UPDATE chunks SET text = 'Texte inventé altéré.' WHERE position = 1 AND book_id = "
                              "(SELECT id FROM books WHERE file_name = ?)", (LIVRE,)))
        code, sortie = self.verify()
        self.assertEqual(code, 1, sortie)
        self.assertIn(LIVRE, sortie)
        self.assertNotIn("Texte inventé altéré.", sortie)
        ligne = self.journal()[-1]
        self.assertRegex(ligne, r"^2026-10-06 écart livres \d+ passages \d+ figures \d+ collections \d+ réindexés \d+ "
                                r"identiques à l'octet \d+ cosinus minimal (aucun|[0-9.]+)$")
        texte = (self.donnees / ki.JOURNAL_PARITE).read_text(encoding="utf-8")
        for nom in demo.BOOKS:
            self.assertNotIn(nom, texte)
            self.assertNotIn(Path(nom).stem, texte)
        for chunk in demo.CHUNKS:
            self.assertNotIn(chunk[3], texte)

    def test_livre_absent_d_un_cote_ecart(self):
        modifier(self.autre, "DELETE FROM chunks WHERE book_id = (SELECT id FROM books WHERE file_name = 'billet-ancien.md')",
                 "DELETE FROM books WHERE file_name = 'billet-ancien.md'")
        code, sortie = self.verify()
        self.assertEqual(code, 1, sortie)
        self.assertIn("absent de la base : billet-ancien.md", sortie)
        self.assertIn("Parité SQLite : écart", sortie)

    def test_jours_consecutifs_depuis_le_journal(self):
        (self.donnees / ki.JOURNAL_PARITE).write_text(
            "2026-10-01 identique livres 5\n2026-10-02 écart livres 5\n2026-10-03 identique livres 5\n"
            "2026-10-05 identique livres 5\n", encoding="utf-8")    # le 4 manque : ni compté ni remis à zéro
        code, sortie = self.verify()
        self.assertEqual(code, 0, sortie)
        self.assertIn("jours identiques consécutifs : 3", sortie)
        decaler_vecteurs(self.autre, LIVRE, 0.05)
        self.reindexer(self.chemin)
        self.reindexer(self.autre)
        code, sortie = self.verify()
        self.assertIn("jours identiques consécutifs : 0", sortie)
        self.assertEqual(len(self.journal()), 6)

    def test_compte_des_jours_distincts(self):
        self.assertEqual(ki.jours_identiques_consecutifs([]), 0)
        self.assertEqual(ki.jours_identiques_consecutifs(["2026-10-01 identique", "2026-10-01 identique", "2026-10-02 identique", ""]), 2)
        self.assertEqual(ki.jours_identiques_consecutifs(["2026-10-01 identique", "2026-10-02 écart"]), 0)

    def test_vectors_en_parite_juge_au_cosinus(self):
        decaler_vecteurs(self.autre, LIVRE, 0.005)
        code, sortie = self.verify("--vectors", "30", "--seed", "1")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Vecteurs relus : 30", sortie)
        code, sortie = self.verify("--vectors", "30", "--seed", "1", parite=False)
        self.assertEqual(code, 1, sortie)

    def test_jamais_de_code_3(self):
        for decalage in (0.0, 0.005, 0.05):
            decaler_vecteurs(self.autre, LIVRE, decalage)
            for parite in (True, False):
                self.assertIn(self.verify(parite=parite)[0], (0, 1))


class Vecteurs(unittest.TestCase):
    """Comparaison des vecteurs relus (sans base ; les fonctions ne manipulent que des nombres)."""

    def test_vecteurs_identiques(self):
        v = demo.vector(0.3)
        m = ki.comparer_vecteurs([(v, v.copy()), (demo.vector(1.1), demo.vector(1.1))])
        self.assertEqual((m["n"], m["ecart_max"], m["nuls"], m["nuls_deux_cotes"]), (2, 0.0, 0, 0))
        self.assertAlmostEqual(m["cosinus_min"], 1.0, places=6)
        self.assertAlmostEqual(m["norme_min"], 1.0, places=5)

    def test_ecart_et_cosinus_detectes(self):
        m = ki.comparer_vecteurs([(demo.vector(0.3), demo.vector(0.5))])
        self.assertGreater(m["ecart_max"], 0.1)
        self.assertLess(m["cosinus_min"], 0.99)

    def test_vecteur_nul_signale_et_cosinus_negatif_si_un_seul_est_nul(self):
        zero = np.zeros(demo.DIMENSIONS, dtype=np.float32)
        m = ki.comparer_vecteurs([(zero, zero.copy())])
        self.assertEqual((m["nuls"], m["nuls_deux_cotes"]), (1, 2))
        self.assertEqual(m["cosinus_min"], 1.0)            # deux vecteurs nuls identiques : pas d'écart
        m = ki.comparer_vecteurs([(demo.vector(0.3), zero)])
        self.assertEqual((m["cosinus_min"], m["nuls"], m["nuls_deux_cotes"]), (-1.0, 0, 1))
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

    def test_aller_retour_litteral_halfvec(self):
        blob = demo.chunk_blob(0.7)
        self.assertEqual(ki.litteral_vers_blob(pg_demo.literal(0.7)), blob)


class AvecBase(AvecDossierDeDonnees):
    """Base jetable chargée par de simples INSERT (pg_demo) face à l'index SQLite inventé (demo_library.build_sqlite)."""

    def setUp(self):
        if not base.BASE_DISPONIBLE:
            self.skipTest(base.MESSAGE_SAUT)
        super().setUp()
        self.base = pg_demo.ThrowawayDatabase(self)
        # pg_demo range « sha-<fichier> » comme sha256 : l'index SQLite inventé prend la même valeur
        modifier(self.chemin, "UPDATE books SET sha256 = 'sha-' || file_name")
        self.admin = self.base._raw()

    def lancer(self, *arguments):
        return lancer(*arguments, fabrique=lambda nom: self.base._raw())

    def ecrire(self, sql, params=None):
        self.admin.execute(sql, params)
        self.admin.commit()

    def test_identique(self):
        code, sortie = self.lancer("verify")
        self.assertEqual(code, 0, sortie)
        self.assertIn("empreintes identiques", sortie)
        self.assertNotIn("BM25", sortie)

    def test_texte_altere(self):
        self.ecrire("UPDATE knowledge.chunks SET text = 'altéré' WHERE position = 1 AND book_id = "
                    "(SELECT id FROM knowledge.books WHERE file_name = 'discovery-notes.md')")
        code, sortie = self.lancer("verify")
        self.assertEqual(code, 1, sortie)
        self.assertIn("discovery-notes.md", sortie)
        self.assertIn("empreinte", sortie)
        self.assertNotIn("altéré", sortie)

    def test_livre_absent(self):
        self.ecrire("DELETE FROM knowledge.books WHERE file_name = 'billet-ancien.md'")
        code, sortie = self.lancer("verify")
        self.assertEqual(code, 1, sortie)
        self.assertIn("absent de la base : billet-ancien.md", sortie)

    def test_option_vectors(self):
        code, sortie = self.lancer("verify", "--vectors", "20", "--seed", "1")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Vecteurs relus : 20", sortie)
        self.assertIn("écart maximal 0", sortie)
        cosinus = float(re.search(r"cosinus minimal ([0-9.]+)", sortie).group(1))
        self.assertGreaterEqual(cosinus, 0.9999)
        autre = "[" + ",".join(["0", "1"] + ["0"] * 1022) + "]"
        self.ecrire("UPDATE knowledge.chunks SET embedding = %s::halfvec", (autre,))
        code, sortie = self.lancer("verify", "--vectors", "20", "--seed", "1")
        self.assertEqual(code, 1, sortie)
        self.assertIn("vecteurs : écart maximal", sortie)

    def test_parite_livres_reindexes_d_un_seul_cote(self):
        # pg_demo indexe « maintenant », l'index SQLite inventé en 2025 : chaque livre est réindexé côté base seulement
        code, sortie = self.lancer("verify", "--parity", "--since", dt.date.today().isoformat())
        self.assertEqual(code, 0, sortie)
        self.assertIn("5 livre(s) réindexé(s) d'un seul côté", sortie)
        self.assertIn("Parité SQLite : identique", sortie)
        self.assertEqual(len((self.donnees / ki.JOURNAL_PARITE).read_text(encoding="utf-8").splitlines()), 1)

    def test_rien_n_est_ecrit_dans_la_base(self):
        connexion = ki.ouvrir_pg(fabrique=lambda nom: self.base._raw())
        with self.assertRaises(Exception):
            connexion.execute("DELETE FROM knowledge.books")
        connexion.rollback()
        self.assertEqual(self.admin.execute("SELECT count(*) FROM knowledge.books").fetchone()[0], len(demo.BOOKS))

    def test_status(self):
        code, sortie = self.lancer("status")
        self.assertEqual(code, 0, sortie)
        self.assertIn("Base : 5 livres, 14 passages, 2 figures, 5 collections.", sortie)
        self.assertIn("SQLite : 5 livres, 14 passages, 2 figures, 5 collections.", sortie)


if __name__ == "__main__":
    unittest.main()
