"""Choix de la source de dependencies_jira.py (lire_donnees), en direct, avec un faux flow_store : aucune base, aucune connexion.

    uv run --with pyyaml --with requests python -m unittest discover -s tests/dependencies_jira -v

Le parcours de bout en bout avec la base jetable (mêmes cartes que la voie CSV) est dans tests/flow_store/test_sources_scripts.py.
"""
import argparse
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import dependencies_jira as dj  # noqa: E402
from dependencies_jira_messages import CATALOGS  # noqa: E402
from messages import Messages  # noqa: E402


class ErreurBase(Exception):            # le script reconnaît l'erreur de la base à son nom de classe
    pass


def arret(appel) -> str:
    try:
        appel()
    except SystemExit as sortie:
        return str(sortie.code)
    raise AssertionError("le script aurait dû s'arrêter")


class Source(unittest.TestCase):
    def test_voie_csv_lit_les_exports(self):
        for source in (None, "csv"):
            args = argparse.Namespace(source=source, export=["a.csv"])
            with mock.patch.object(dj, "read_exports", return_value={"fichiers": ["a.csv"]}) as lecture:
                self.assertEqual(dj.lire_donnees(args, {}, Messages(CATALOGS)), {"fichiers": ["a.csv"]})
            self.assertEqual(lecture.call_args.args[0], ["a.csv"])

    def test_source_inconnue(self):
        args = argparse.Namespace(source="ftp", export=[])
        message = arret(lambda: dj.lire_donnees(args, {}, Messages(CATALOGS, "en")))
        self.assertIn('unknown value "ftp"', message)
        self.assertIn("csv, db", message)

    def test_voie_db_nomme_la_source_base_ou_database(self):
        for langue, nom in (("fr", "base"), ("en", "database")):
            args = argparse.Namespace(source="db", export=[])
            lecture = mock.Mock(return_value={"equipes": {}})
            with mock.patch.dict(sys.modules, {"flow_store": types.SimpleNamespace(lire_dependances=lecture)}), \
                    mock.patch.object(dj, "read_exports", side_effect=AssertionError("pas de lecture CSV")):
                donnees = dj.lire_donnees(args, {"x": 1}, Messages(CATALOGS, langue))
            lecture.assert_called_once_with({"x": 1})
            self.assertEqual(donnees["fichiers"], [nom])

    def test_fichiers_refuses_avec_la_base_avant_toute_connexion(self):
        args = argparse.Namespace(source="db", export=["a.csv"])
        for langue, attendu in (("fr", "aucun fichier CSV ne doit être donné"), ("en", "no CSV file may be given")):
            lecture = mock.Mock(side_effect=AssertionError("connexion"))
            with mock.patch.dict(sys.modules, {"flow_store": types.SimpleNamespace(lire_dependances=lecture)}):
                self.assertIn(attendu, arret(lambda: dj.lire_donnees(args, {}, Messages(CATALOGS, langue))))
            lecture.assert_not_called()

    def test_base_injoignable_message_clair(self):
        args = argparse.Namespace(source="db", export=[])
        store = types.SimpleNamespace(lire_dependances=mock.Mock(side_effect=ErreurBase("refusée")))
        with mock.patch.dict(sys.modules, {"flow_store": store}):
            self.assertEqual(arret(lambda: dj.lire_donnees(args, {}, Messages(CATALOGS))),
                             "Base de données : lecture impossible. refusée")


if __name__ == "__main__":
    unittest.main()
