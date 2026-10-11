"""tools/messages.py : catalogues par langue, repli sur le français, contrôle de cohérence. Aucun accès extérieur."""
import argparse
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import messages  # noqa: E402

CATALOGS = {"fr": {"hello": "Bonjour {name}", "plain": "Texte {{littéral}}", "only_fr": "Seulement français"},
            "en": {"hello": "Hello {name}", "plain": "Text {{literal}}"}}


class TestMessages(unittest.TestCase):
    def test_langue_choisie(self):
        self.assertEqual(messages.Messages(CATALOGS, "fr")("hello", name="A"), "Bonjour A")
        self.assertEqual(messages.Messages(CATALOGS, "en")("hello", name="A"), "Hello A")

    def test_accolades_doublees_rendues_comme_str_format(self):
        self.assertEqual(messages.Messages(CATALOGS, "en")("plain"), "Text {literal}")

    def test_repli_sur_le_francais(self):
        self.assertEqual(messages.Messages(CATALOGS, "en")("only_fr"), "Seulement français")

    def test_cle_inconnue_partout(self):
        with self.assertRaises(KeyError):
            messages.Messages(CATALOGS, "en")("nope")

    def test_langue_inconnue(self):
        with self.assertRaises(ValueError):
            messages.Messages(CATALOGS, "de")

    def test_check_catalogs(self):
        problemes = messages.check_catalogs(CATALOGS)
        self.assertEqual(problemes, ["en : clé « only_fr » absente"])
        faux = {"fr": {"a": "x {n}"}, "en": {"a": "x {m}", "b": "y"}}
        self.assertEqual(len(messages.check_catalogs(faux)), 2)

    def test_option_language(self):
        parser = argparse.ArgumentParser()
        messages.add_language_option(parser)
        self.assertEqual(parser.parse_args([]).language, "fr")
        self.assertEqual(parser.parse_args(["--language", "en"]).language, "en")
        with self.assertRaises(SystemExit):
            parser.parse_args(["--language", "de"])


if __name__ == "__main__":
    unittest.main()
