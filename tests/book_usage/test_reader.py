"""Lecteur de la liste des livres (rôle lecture seule, délai court, exclusions exactes) et surveillance des dossiers : tâche 3.1.

Fausse connexion : aucune base n'est jointe. La classe sur base jetable est dans test_book_usage_db.py (tools/dbtest.sh).
"""
import builtins
import os
import unittest
from pathlib import Path
from unittest import mock

import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parents[2] / "tools"))
import book_usage  # noqa: E402
from fixtures_book_usage import Base, Transcript, simple_turn


class FausseConnexion:
    fermee = False

    def __init__(self, lignes=None, panne=None):
        self.lignes, self.panne, self.requetes = lignes or [], panne, []

    def execute(self, sql, params=()):
        self.requetes.append(sql)
        if self.panne:
            raise self.panne
        return self

    def fetchall(self):
        return self.lignes

    def close(self):
        FausseConnexion.fermee = True


class Lecteur(unittest.TestCase):
    def test_un_dict_par_livre_collections_exclues_par_nom_exact(self):
        lignes = [("Livre A", "a.md", ["flow", "produit"]), ("Billet", "b.md", ["watch"]), ("Ancien", "c.md", ["veille"]),
                  ("Perso", "d.md", ["own-articles"]), ("Mot proche", "e.md", ["watching", "flow"]), ("Sans collection", "f.md", None)]
        livres = book_usage.fetch_books(connect=lambda: FausseConnexion(lignes))
        self.assertEqual([l["file"] for l in livres], ["a.md", "e.md", "f.md"])
        self.assertEqual(livres[0], {"title": "Livre A", "file": "a.md", "collections": ["flow", "produit"]})
        self.assertEqual(livres[2]["collections"], [])

    def test_connexion_fermee_meme_en_cas_d_erreur(self):
        FausseConnexion.fermee = False
        with self.assertRaises(RuntimeError):
            book_usage.fetch_books(connect=lambda: FausseConnexion(panne=RuntimeError("x")))
        self.assertTrue(FausseConnexion.fermee)

    def test_requete_en_lecture_seule_sur_le_schema_knowledge(self):
        conn = FausseConnexion()
        book_usage.fetch_books(connect=lambda: conn)
        self.assertEqual(len(conn.requetes), 1)
        sql = conn.requetes[0].upper()
        self.assertTrue(sql.lstrip().startswith("SELECT"))
        self.assertIn("KNOWLEDGE.BOOKS", sql)
        for mot in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE"):
            self.assertNotIn(mot, sql)

    def test_connexion_reelle_sous_le_role_de_lecture_et_delai_court(self):
        appels = []

        def faux_connect(**kwargs):
            appels.append(kwargs)
            return FausseConnexion()
        with mock.patch("db.connect", faux_connect), mock.patch.dict(os.environ, {"PMZILLA_LAB_KNOWLEDGE_DBNAME": "essai"}):
            book_usage.fetch_books()
        self.assertEqual(appels, [{"role": "pmzilla_knowledge_ro", "timeout": 2, "dbname": "essai"}])


class BaseFactice(Base):
    """Le lecteur réel (sans lecture injectée) sur une base factice : db.connect remplacé, aucune base jointe."""

    def lignes(self):
        return [("Flux et valeur", "flux-et-valeur.md", ["flow"]), ("Un billet", "billet.md", ["watch"])]

    def test_rapport_par_le_lecteur_reel(self):
        self.put(simple_turn(Transcript(), "[Posture: Delivery]\nFlux et valeur.", files=("flux-et-valeur.md",)))
        self.collect()
        appels = []

        def faux_connect(**kwargs):
            appels.append(kwargs)
            return FausseConnexion(self.lignes())
        with mock.patch("db.connect", faux_connect):
            code, _ = self.run_tool("report")
        self.assertEqual(code, 0)
        self.assertEqual([a["role"] for a in appels], ["pmzilla_knowledge_ro"])
        texte = self.report_text()
        self.assertIn("Flux et valeur", texte)
        self.assertNotIn("Un billet", texte)

    def test_base_injoignable_a_la_connexion(self):
        self.put(simple_turn(Transcript(), "[Posture: Delivery]\nFlux et valeur.", files=("flux-et-valeur.md",)))
        self.collect()

        class OperationalError(Exception):
            pass

        def faux_connect(**kwargs):
            raise OperationalError("connection to server at 127.0.0.1 failed: délai dépassé, utilisateur sentinelle")
        with mock.patch("db.connect", faux_connect):
            code, out = self.run_tool("report")
        self.assertEqual(code, 2)
        self.assertIn("Bibliothèque injoignable (OperationalError)", out)
        self.assertNotIn("sentinelle", out)
        self.assertNotIn("127.0.0.1", out)
        self.assertEqual(self.report_text(), "")

    def test_base_injoignable_a_la_requete(self):
        self.put(simple_turn(Transcript(), "[Posture: Delivery]\nFlux et valeur.", files=("flux-et-valeur.md",)))
        self.collect()

        class QueryCanceled(Exception):
            pass
        conn = FausseConnexion(panne=QueryCanceled("canceling statement due to statement timeout sentinelle"))
        FausseConnexion.fermee = False
        with mock.patch("db.connect", lambda **kwargs: conn):
            code, out = self.run_tool("report")
        self.assertEqual(code, 2)
        self.assertIn("Bibliothèque injoignable (QueryCanceled)", out)
        self.assertNotIn("sentinelle", out)
        self.assertTrue(FausseConnexion.fermee)
        self.assertEqual(self.report_text(), "")


class DossiersDeContenu(Base):
    """Des surveillants sur l'ouverture de fichiers : aucun fichier sous les dossiers de contenu n'est ouvert."""

    INTERDITS = ("Bibliotheque-Lab", "Bibliotheque-MD", "Bibliotheque-Images", "Watch-Lab", "Watch-Excluded", "Veille-Lab", "_bmad/memory", "_memory")

    def test_aucun_fichier_de_contenu_ouvert(self):
        t = simple_turn(Transcript(), "[Posture: Delivery]\nFlux et valeur.")
        self.put(t)
        for dossier in ("Bibliotheque-Lab", "Watch-Lab", "Bibliotheque-Images"):
            (self.workspace / dossier).mkdir(parents=True)
            (self.workspace / dossier / "livre.md").write_text("contenu", encoding="utf-8")
        ouverts = []
        vrai_open = builtins.open
        vrai_path_open = Path.open
        vrai_os_open = os.open

        def note(chemin):
            ouverts.append(str(chemin))

        def faux_open(chemin, *a, **k):
            note(chemin)
            return vrai_open(chemin, *a, **k)

        def faux_path_open(self, *a, **k):
            note(self)
            return vrai_path_open(self, *a, **k)

        def faux_os_open(chemin, *a, **k):
            note(chemin)
            return vrai_os_open(chemin, *a, **k)
        with mock.patch.object(builtins, "open", faux_open), mock.patch.object(Path, "open", faux_path_open), \
                mock.patch.object(os, "open", faux_os_open):
            self.collect()
            self.report()
        interdits = [c for c in ouverts if any(d in c for d in self.INTERDITS)]
        self.assertEqual(interdits, [])
        self.assertTrue(ouverts)       # le surveillant voit bien des ouvertures


if __name__ == "__main__":
    unittest.main()
