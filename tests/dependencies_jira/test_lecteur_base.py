"""dependencies_jira.py lit la base seule (change database-only, D6) : lecture, refus d'usage, session, exclusion.

    uv run --with pyyaml --with requests python -m unittest discover -s tests/dependencies_jira -v

Un faux flow_store rend les structures des fixtures CSV (chargeur de test) : aucune base, aucune connexion. Le parcours de bout en bout avec
la base jetable est dans tests/flow_store/.
"""
import argparse
import contextlib
import io
import json
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.append(str(RACINE / "tests" / "flux_jira"))      # à la fin : test_language existe aussi là-bas
import chargeur_csv as chargeur  # noqa: E402
import dependencies_jira as dj  # noqa: E402
from dependencies_jira_messages import CATALOGS  # noqa: E402
from messages import Messages  # noqa: E402
from test_dependencies_jira import AUJOURDHUI, Base, t  # noqa: E402


class ErreurBase(Exception):            # le script reconnaît l'erreur de la base à son nom de classe
    pass


def arret(appel):
    try:
        appel()
    except SystemExit as sortie:
        return sortie.code
    raise AssertionError("le script aurait dû s'arrêter")


class Lecture(unittest.TestCase):
    def test_lit_la_base_avec_les_reglages_et_nomme_la_source(self):
        for langue, nom in (("fr", "base"), ("en", "database")):
            lecture = mock.Mock(return_value={"equipes": {}})
            with mock.patch.dict(sys.modules, {"flow_store": types.SimpleNamespace(lire_dependances=lecture)}):
                donnees = dj.lire_donnees(argparse.Namespace(), {"x": 1}, Messages(CATALOGS, langue))
            lecture.assert_called_once_with({"x": 1})
            self.assertEqual(donnees["fichiers"], [nom])

    def test_base_injoignable_message_clair(self):
        store = types.SimpleNamespace(lire_dependances=mock.Mock(side_effect=ErreurBase("refusée")))
        with mock.patch.dict(sys.modules, {"flow_store": store}):
            self.assertEqual(arret(lambda: dj.lire_donnees(argparse.Namespace(), {}, Messages(CATALOGS))),
                             "Base de données : lecture impossible. refusée")

    def test_autre_erreur_non_masquee(self):
        store = types.SimpleNamespace(lire_dependances=mock.Mock(side_effect=KeyError("x")))
        with mock.patch.dict(sys.modules, {"flow_store": store}):
            with self.assertRaises(KeyError):
                dj.lire_donnees(argparse.Namespace(), {}, Messages(CATALOGS))

    def test_aucun_conseil_de_troncature(self):
        """Q9 : un nombre rond de tickets ne déclenche plus l'avertissement d'export tronqué (la lecture de la base est complète)."""
        self.assertNotIn("round_number", CATALOGS["fr"])
        self.assertNotIn("note_truncated", CATALOGS["en"])


class Refus(unittest.TestCase):
    """verifier_usage : avant toute lecture, sans nommer de fichier ni de valeur."""

    def setUp(self):
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("CLAUDECODE", None)

    def test_source_refusee_quelle_que_soit_la_valeur(self):
        for valeur in ("db", "csv", "ftp", ""):
            args = argparse.Namespace(source=valeur, export=[])
            with contextlib.redirect_stderr(io.StringIO()) as erreur:
                code = arret(lambda: dj.verifier_usage(args, Messages(CATALOGS)))
            self.assertEqual(code, 2)
            self.assertEqual(erreur.getvalue().strip(), "--source est retirée : la base est la seule source")

    def test_source_refusee_en_anglais(self):
        args = argparse.Namespace(source="db", export=[])
        with contextlib.redirect_stderr(io.StringIO()) as erreur:
            self.assertEqual(arret(lambda: dj.verifier_usage(args, Messages(CATALOGS, "en"))), 2)
        self.assertIn("--source is retired: the database is the only source", erreur.getvalue())

    def test_fichier_d_export_refuse_sans_le_nommer(self):
        for langue, phrase in (("fr", "les fichiers d'export ne sont plus lus : la base est la seule source"),
                               ("en", "export files are no longer read: the database is the only source")):
            args = argparse.Namespace(source=None, export=["secret-nom.csv"])
            with contextlib.redirect_stderr(io.StringIO()) as erreur:
                self.assertEqual(arret(lambda: dj.verifier_usage(args, Messages(CATALOGS, langue))), 2)
            self.assertIn(phrase, erreur.getvalue())
            self.assertNotIn("secret-nom", erreur.getvalue())

    def test_session_claude_code_refusee_code_3_avant_le_reste(self):
        for langue, phrase in (("fr", "Refusé dans une session Claude Code"), ("en", "Refused inside a Claude Code session")):
            args = argparse.Namespace(source="db", export=["a.csv"])
            with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}), contextlib.redirect_stdout(io.StringIO()) as sortie:
                self.assertEqual(arret(lambda: dj.verifier_usage(args, Messages(CATALOGS, langue))), 3)
            self.assertIn(phrase, sortie.getvalue())

    def test_session_variable_vide_refuse_aussi(self):
        with mock.patch.dict(os.environ, {"CLAUDECODE": ""}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(arret(lambda: dj.verifier_usage(argparse.Namespace(source=None, export=[]), Messages(CATALOGS))), 3)

    def test_main_refuse_avant_de_lire_les_reglages(self):
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}), \
                mock.patch.object(dj, "config", side_effect=AssertionError("réglage lu")), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(arret(lambda: dj.main(["compute"])), 3)
            self.assertEqual(arret(lambda: dj.main(["diagnose"])), 3)

    def test_main_refuse_source_et_fichiers_avant_la_base(self):
        store = types.SimpleNamespace(lire_dependances=mock.Mock(side_effect=AssertionError("connexion")))
        with mock.patch.dict(sys.modules, {"flow_store": store}), mock.patch.dict(os.environ), \
                contextlib.redirect_stderr(io.StringIO()):
            os.environ.pop("CLAUDECODE", None)
            self.assertEqual(arret(lambda: dj.main(["compute", "--source", "db"])), 2)
            self.assertEqual(arret(lambda: dj.main(["diagnose", "a.csv"])), 2)
        store.lire_dependances.assert_not_called()


class ExclusionAvecLaBase(Base):
    """R-72 : la liste exclue de la carte s'applique après la lecture de la base, qui rend tous les liens."""

    TICKETS = [
        t("AAA-1", "Eq-Alpha", sortants=["BBB-1"]), t("BBB-1", "Eq-Beta", entrants=["AAA-1"]),
        t("AAA-2", "Eq-Alpha", sortants=["XXA-1"]), t("XXA-1", "Eq-Gamma", entrants=["AAA-2"]),
        t("AAA-3", "Eq-Alpha", sortants=["XXB-1"]), t("XXB-1", "Eq-Gamma", entrants=["AAA-3"]),
    ]

    def rapport_db(self, *extra: str) -> dict:
        export = self.csv(self.TICKETS, nom="base.csv")
        donnees = chargeur.lire_export_dependances(Path(export), dj.config())
        magasin = types.SimpleNamespace(lire_dependances=lambda settings: dict(donnees))
        racine = self.ws / "Flux-Lab"
        with mock.patch.dict(sys.modules, {"flow_store": magasin}), mock.patch.dict(os.environ), \
                mock.patch.object(dj, "FLUX_DIR", racine), mock.patch.object(dj, "CONFIG_FILE", racine / "flux.yaml"), \
                mock.patch.object(dj, "REPORT_DIR", racine / "rapports"), contextlib.redirect_stdout(io.StringIO()):
            os.environ.pop("CLAUDECODE", None)
            dj.main(["compute", "--name", "db", *extra])
        fichier = racine / "rapports" / f"dependances-db-{AUJOURDHUI.isoformat()}.json"
        return json.loads(fichier.read_text(encoding="utf-8"))

    def test_sources_de_la_liste_exclue(self):
        cas = (("excluded_projects: [XXA]\n", (), "reglage_commun"),
               ("excluded_projects: [XXA]\ndependency_excluded_projects: [XXB]\n", (), "reglage_carte"),
               ("dependency_excluded_projects: [XXB]\n", ("--exclude", "XXA,XXB"), "option"),
               ("excluded_projects: [XXA]\n", ("--exclude", "none"), "option"))
        for reglage, option, source in cas:
            with self.subTest(source=source, option=option):
                self.reglages(reglage)
                r_db = self.rapport_db(*option)
                self.assertEqual(r_db["exclus_source"], source)
                self.assertNotIn("tronques", r_db)


if __name__ == "__main__":
    unittest.main()
