"""Option --open de tools/flow_board.py : la page écrite est ouverte dans le navigateur, sans navigateur réel.

    uv run --with pyyaml --with numpy python -m unittest discover -s tests/flow_board -v

La génération (ecrire_page) et le navigateur (webbrowser.open) sont remplacés : aucun rapport, aucun fichier réel.
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent / "flux_jira"))
sys.path.insert(0, str(ICI.parent.parent / "tools"))
import flow_board as tf  # noqa: E402


class Ouverture(unittest.TestCase):
    def lancer(self, *argv: str):
        with tempfile.TemporaryDirectory() as d:
            page = Path(d) / "tableau.html"
            page.write_text("<html></html>", encoding="utf-8")
            sortie, erreur = io.StringIO(), io.StringIO()
            with mock.patch.object(tf, "ecrire_page", return_value=page) as ecrire, \
                    mock.patch.object(tf.webbrowser, "open") as ouvrir, \
                    contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
                code = tf.main(list(argv))
            return code, ecrire, ouvrir, page, sortie.getvalue()

    def test_sans_option_la_page_n_est_pas_ouverte(self):
        code, ecrire, ouvrir, _, sortie = self.lancer()
        self.assertEqual(code, 0)
        ecrire.assert_called_once()
        ouvrir.assert_not_called()
        self.assertIn("Tableau de bord :", sortie)

    def test_open_ouvre_la_page_ecrite(self):
        code, ecrire, ouvrir, page, _ = self.lancer("--open")
        self.assertEqual(code, 0)
        ecrire.assert_called_once()
        ouvrir.assert_called_once_with(page.as_uri())          # l'adresse file:// du fichier qui vient d'être écrit

    def test_open_avec_les_autres_options(self):
        code, ecrire, ouvrir, page, _ = self.lancer("--language", "fr", "--anonymous", "--open")
        self.assertEqual(code, 0)
        self.assertEqual(ecrire.call_args.args[:2], ("fr", True))
        ouvrir.assert_called_once_with(page.as_uri())

    def test_open_n_ouvre_rien_si_la_generation_echoue(self):
        with mock.patch.object(tf, "ecrire_page", side_effect=tf.Arret("bibliothèque absente")), \
                mock.patch.object(tf.webbrowser, "open") as ouvrir, \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(tf.main(["--open"]), 1)
        ouvrir.assert_not_called()


if __name__ == "__main__":
    unittest.main()
