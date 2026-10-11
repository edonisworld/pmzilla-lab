"""
Tests des sous-commandes `probe` (sonde de l'index BM25) et `status` (comptes) de tools/pmzilla_lab_library.py (design.md D3 et
D4 de db-direct-indexing). La sonde vient de `knowledge_import.py verify` (anciens tests SondeBm25), sans changement de
comportement.

    bash tests/run_all.sh pmzilla_lab_library

Sans base : fausse connexion qui enregistre les ordres SQL. La classe AvecBase lit la bibliothèque inventée chargée dans une base
jetable (tests/library_backend/pg_demo.py) ; elle est sautée sans base et lancée par l'utilisateur (bash tools/dbtest.sh).
Jamais la vraie base, aucun texte de livre réel.
"""
import contextlib
import io
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

import psycopg

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import db  # noqa: E402
import pmzilla_lab_library as library  # noqa: E402

INJOIGNABLE = "Database unreachable: nothing was {}. Start it: bash tools/db_up.sh"


class FausseConnexion:
    """Remplace une connexion PostgreSQL : enregistre les ordres ; les requêtes plein texte réussissent ou lèvent `erreur` quand
    leur SQL contient `quand` ; la requête de comptes rend `comptes`."""

    def __init__(self, erreur=None, quand="fts_text", comptes=(5, 14, 2, 4)):
        self.erreur, self.quand, self.comptes = erreur, quand, comptes
        self.ordres, self.requetes = [], []

    def execute(self, sql, params=None):
        texte = " ".join(sql.split())
        self.ordres.append(texte)
        if "fts_text" in sql:
            self.requetes.append((texte, params))
            if self.erreur and self.quand in sql:
                raise self.erreur
        return FausseConnexion.Resultat([(1,)] if "fts_text" in sql else [self.comptes])

    def rollback(self):
        self.ordres.append("ROLLBACK")

    def commit(self):
        self.ordres.append("COMMIT")

    def close(self):
        self.ordres.append("CLOSE")

    class Resultat(list):
        def fetchone(self):
            return self[0] if self else None

        def fetchall(self):
            return list(self)


def lancer(fonction, connexion=None, connect=None):
    sortie, erreurs = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreurs):
        code = fonction(connect=connect or (lambda: connexion))
    return code, sortie.getvalue() + erreurs.getvalue()


def refus(*_args, **_kwargs):
    raise db.ErreurBase("Connexion à la base impossible : password=SecretInvente-42 host=serveur.test.")


class Sonde(unittest.TestCase):
    ABIME = psycopg.errors.InternalError_("bitmap intersection stream (consumer 0, segment 7) claimed twice")

    def test_succes_deux_requetes_code_0(self):
        connexion = FausseConnexion()
        code, sortie = lancer(library.probe, connexion)
        self.assertEqual(code, 0, sortie)
        self.assertIn("BM25 index readable", sortie)
        self.assertEqual(len(connexion.requetes), 2)
        self.assertNotIn("c.kind", connexion.requetes[0][0])                 # sans filtre de type
        self.assertIn("c.kind = ANY", connexion.requetes[1][0])              # puis filtrée par type
        self.assertEqual(connexion.requetes[1][1][1], ["figure"])
        self.assertGreaterEqual(connexion.ordres.count("ROLLBACK"), 2)       # chaque requête termine sa transaction

    def test_seulement_deux_lectures_et_les_fins_de_transaction(self):
        for connexion in (FausseConnexion(), FausseConnexion(self.ABIME, quand="c.kind"), FausseConnexion(RuntimeError("x"))):
            lancer(library.probe, connexion)
            autres = [o for o in connexion.ordres if o not in ("ROLLBACK", "CLOSE") and not o.startswith("SELECT c.id FROM")]
            self.assertEqual(autres, [], connexion.ordres)
            for ordre in connexion.ordres:
                for interdit in ("INSERT", "UPDATE", "DELETE", "REINDEX", "CREATE", "DROP", "SET "):
                    self.assertNotIn(interdit, ordre)

    def test_internal_error_index_illisible_code_3(self):
        connexion = FausseConnexion(self.ABIME, quand="c.kind")               # seule la requête filtrée échoue, comme sur la vraie base
        code, sortie = lancer(library.probe, connexion)
        self.assertEqual(code, 3)
        self.assertIn("BM25 index unreadable (figure kind: InternalError_)", sortie)
        self.assertIn('Procedure: docs/pmzilla/installation.md, "Damaged BM25 index"', sortie)
        self.assertNotIn("BM25 index readable", sortie)
        self.assertEqual([o for o in connexion.ordres if o != "CLOSE"][-1], "ROLLBACK")   # la transaction en erreur est annulée

    def test_autre_erreur_meme_echec_nomme(self):
        code, sortie = lancer(library.probe, FausseConnexion(RuntimeError("boum")))
        self.assertEqual(code, 3)
        self.assertIn("BM25 index unreadable (no filter: RuntimeError)", sortie)
        self.assertIn("Damaged BM25 index", sortie)

    def test_aucun_texte_de_livre_dans_la_sortie(self):
        erreur = RuntimeError("Un passage secret du livre inventé : la limite de travail en cours")
        code, sortie = lancer(library.probe, FausseConnexion(erreur))
        self.assertEqual(code, 3)
        self.assertNotIn("passage secret", sortie)
        self.assertNotIn("limite de travail", sortie)

    def test_base_injoignable_code_2_sans_secret(self):
        code, sortie = lancer(library.probe, connect=refus)
        self.assertEqual(code, 2)
        self.assertIn(INJOIGNABLE.format("probed"), sortie)
        for interdit in ("SecretInvente", "serveur.test", "password"):
            self.assertNotIn(interdit, sortie)

    def test_connexion_par_defaut_role_de_lecture_et_base_nommee(self):
        connexion = FausseConnexion()
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_KNOWLEDGE_DBNAME": "pmzilla_test_abc"}), \
                mock.patch.object(db, "connect", return_value=connexion) as connect, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(library.probe(), 0)
        self.assertEqual(connect.call_args.kwargs["role"], "pmzilla_knowledge_ro")
        self.assertEqual(connect.call_args.kwargs["dbname"], "pmzilla_test_abc")
        self.assertIn("CLOSE", connexion.ordres)


class Comptes(unittest.TestCase):
    def test_une_ligne_de_quatre_comptes(self):
        connexion = FausseConnexion(comptes=(5, 14, 2, 4))
        code, sortie = lancer(library.status, connexion)
        self.assertEqual(code, 0)
        self.assertEqual(sortie.strip().splitlines(), ["database: 5 books · 14 passages · 2 figures · 4 collections"])
        self.assertTrue(all(not o.startswith(("INSERT", "UPDATE", "DELETE")) for o in connexion.ordres))
        self.assertIn("CLOSE", connexion.ordres)

    def test_base_injoignable_code_2(self):
        code, sortie = lancer(library.status, connect=refus)
        self.assertEqual(code, 2)
        self.assertIn(INJOIGNABLE.format("read"), sortie)
        self.assertNotIn("SecretInvente", sortie)

    def test_connexion_par_defaut_role_de_lecture(self):
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_KNOWLEDGE_DBNAME": "pmzilla_test_def"}), \
                mock.patch.object(db, "connect", return_value=FausseConnexion()) as connect, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(library.status(), 0)
        self.assertEqual(connect.call_args.kwargs, {"role": "pmzilla_knowledge_ro", "dbname": "pmzilla_test_def"})


class MagasinNomme(unittest.TestCase):
    def test_le_magasin_d_ecriture_ouvre_la_base_nommee(self):
        connexion = FausseConnexion()
        with mock.patch.dict(os.environ, {"PMZILLA_LAB_KNOWLEDGE_DBNAME": "pmzilla_test_ghi"}), \
                mock.patch.object(db, "connect", return_value=connexion) as connect:
            magasin = library.KnowledgeStore()
            magasin.open()
            magasin.close()
        self.assertEqual(connect.call_args.kwargs, {"dbname": "pmzilla_test_ghi"})
        self.assertIn("SET ROLE pmzilla_knowledge", connexion.ordres)

    def test_sans_variable_la_base_de_l_installation(self):
        environnement = {k: v for k, v in os.environ.items() if k != "PMZILLA_LAB_KNOWLEDGE_DBNAME"}
        with mock.patch.dict(os.environ, environnement, clear=True), \
                mock.patch.object(db, "connect", return_value=FausseConnexion()) as connect:
            library.KnowledgeStore().open()
        self.assertIsNone(connect.call_args.kwargs["dbname"])


class LigneDeCommande(unittest.TestCase):
    def principal(self, *arguments, connexion=None):
        sortie = io.StringIO()
        with mock.patch.object(sys, "argv", ["pmzilla_lab_library.py", *arguments]), contextlib.redirect_stdout(sortie), \
                contextlib.redirect_stderr(sortie), self.assertRaises(SystemExit) as arret:
            library.main(connect=lambda: connexion or FausseConnexion())
        return arret.exception.code, sortie.getvalue()

    def test_probe_et_status(self):
        self.assertEqual(self.principal("probe")[0], 0)
        self.assertEqual(self.principal("probe", connexion=FausseConnexion(RuntimeError("x")))[0], 3)
        code, sortie = self.principal("status")
        self.assertEqual(code, 0)
        self.assertIn("database: 5 books", sortie)

    def test_argument_en_trop_refuse(self):
        for arguments in (("probe", "--repair"), ("status", "Bibliotheque-Lab")):
            code, _ = self.principal(*arguments)
            self.assertNotIn(code, (0, None), arguments)


class AvecBase(unittest.TestCase):
    """La sonde et les comptes sur la bibliothèque inventée d'une base jetable (sautée sans base)."""

    def setUp(self):
        sys.path.insert(0, str(RACINE / "tests" / "library_backend"))
        import pg_demo
        self.demo = pg_demo.demo
        self.base = pg_demo.ThrowawayDatabase(self)

    def test_sonde_lisible(self):
        code, sortie = lancer(library.probe, connect=self.base.connect)
        self.assertEqual(code, 0, sortie)
        self.assertIn("BM25 index readable", sortie)

    def test_comptes_de_la_bibliotheque_inventee(self):
        code, sortie = lancer(library.status, connect=self.base.connect)
        self.assertEqual(code, 0, sortie)
        collections = {nom for _, noms, _ in self.demo.BOOKS.values() for nom in noms.split("|")}
        figures = sum(1 for chunk in self.demo.CHUNKS if chunk[5] == "figure")
        self.assertEqual(sortie.strip(), f"database: {len(self.demo.BOOKS)} books · {len(self.demo.CHUNKS)} passages · "
                                         f"{figures} figures · {len(collections)} collections")


if __name__ == "__main__":
    unittest.main()
