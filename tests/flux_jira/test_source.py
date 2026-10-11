"""Choix de la source de flux_jira.py (lire_source, lire_tickets), en direct, avec un faux flow_store : aucune base, aucune connexion.

    uv run --with pyyaml --with numpy python -m unittest discover -s tests/flux_jira -v

Le parcours de bout en bout avec la base jetable (mêmes rapports que la voie CSV) est dans tests/flow_store/test_sources_scripts.py.
"""
import argparse
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import flux_jira as fj  # noqa: E402
from flux_jira_messages import CATALOGS  # noqa: E402
from messages import Messages  # noqa: E402


class ErreurBase(Exception):            # le script reconnaît l'erreur de la base à son nom de classe
    pass


def faux_store(lecture=None):
    return types.SimpleNamespace(lire_tickets_flux=lecture or (lambda settings: ([{"cle": "PROJ-1"}], {"PROJ-1": None}, 1, 0)))


def sortie_arretee(appel):
    with unittest.TestCase().assertRaises(SystemExit) as r:
        appel()
    return r.exception.code


class Source(unittest.TestCase):
    def test_defaut_csv(self):
        self.assertEqual(fj.lire_source(None), "csv")
        self.assertEqual(fj.lire_source("csv"), "csv")
        self.assertEqual(fj.lire_source("db"), "db")

    def test_source_inconnue_nomme_la_valeur_et_les_valeurs_acceptees(self):
        for langue, attendu in (("fr", "valeur inconnue « ftp »"), ("en", 'unknown value "ftp"')):
            code = sortie_arretee(lambda: fj.lire_source("ftp", Messages(CATALOGS, langue)))
            self.assertIn(attendu, code)
            self.assertIn("csv, db", code)

    def test_voie_csv_lit_les_exports(self):
        args = argparse.Namespace(source="csv", export=["a.csv"])
        with mock.patch.object(fj, "read_exports", return_value="LU") as lecture:
            self.assertEqual(fj.lire_tickets(args, {}), "LU")
        lecture.assert_called_once()
        self.assertEqual(lecture.call_args.args[0], ["a.csv"])

    def test_voie_db_lit_la_base_avec_les_reglages(self):
        args = argparse.Namespace(source="db", export=[])
        reglages = {"export_timezone": "Europe/Paris"}
        lecture = mock.Mock(return_value=([], {}, 0, 0))
        with mock.patch.dict(sys.modules, {"flow_store": faux_store(lecture)}), \
                mock.patch.object(fj, "read_exports", side_effect=AssertionError("pas de lecture CSV")):
            self.assertEqual(fj.lire_tickets(args, reglages), ([], {}, 0, 0))
        lecture.assert_called_once_with(reglages)

    def test_fichiers_refuses_avec_la_base_avant_toute_lecture(self):
        args = argparse.Namespace(source="db", export=["a.csv"])
        for langue, attendu in (("fr", "aucun fichier CSV ne doit être donné"), ("en", "no CSV file may be given")):
            with mock.patch.dict(sys.modules, {"flow_store": faux_store(mock.Mock(side_effect=AssertionError("connexion")))}):
                code = sortie_arretee(lambda: fj.lire_tickets(args, {}, Messages(CATALOGS, langue)))
            self.assertIn(attendu, code)

    def test_base_injoignable_message_clair(self):
        args = argparse.Namespace(source="db", export=[])
        with mock.patch.dict(sys.modules, {"flow_store": faux_store(mock.Mock(side_effect=ErreurBase("refusée")))}):
            code = sortie_arretee(lambda: fj.lire_tickets(args, {}))
        self.assertEqual(code, "Base de données : lecture impossible. refusée")

    def test_autre_erreur_non_masquee(self):
        args = argparse.Namespace(source="db", export=[])
        with mock.patch.dict(sys.modules, {"flow_store": faux_store(mock.Mock(side_effect=KeyError("x")))}):
            with self.assertRaises(KeyError):
                fj.lire_tickets(args, {})


if __name__ == "__main__":
    unittest.main()
