"""
La valeur « collection » d'une source nomme un dossier : un seul composant de chemin sûr (audit #629, A-91 ; R-20261109-19).

    uv run --with feedparser --with trafilatura --with httpx --with pyyaml --with beautifulsoup4 \
        --with markdownify python -m unittest discover -s tests/watch_lab -v

Motif accepté : ^[a-z0-9][a-z0-9-]*$. Refus (ErreurConfig) au chargement des sources et dans collection_dir. La collection par défaut et
own-articles passent. Aucun appel réseau, aucun dossier de contenu : sources dans un dossier temporaire.
"""
import argparse
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import watch_lab as veille  # noqa: E402
import watch_paths  # noqa: E402
from yaml_strict import ErreurConfig  # noqa: E402

REFUSEES = ["..", "a/b", "/etc", "", "../x", "A", "-a", ".", "a b", "a\\b"]


class CollectionBornee(unittest.TestCase):
    def test_collection_dir_refuse_une_valeur_hors_motif(self):
        for valeur in REFUSEES:
            with self.subTest(valeur=valeur):
                with self.assertRaises(ErreurConfig):
                    veille.collection_dir({"key": "k", "collection": valeur})

    def test_collection_dir_accepte_defaut_et_own_articles(self):
        self.assertEqual(veille.collection_dir({"key": "k"}), veille.WATCH_DIR / veille.ARTICLES_DIR.name)
        self.assertEqual(veille.collection_dir({"key": "k", "collection": None}), veille.WATCH_DIR / veille.ARTICLES_DIR.name)
        self.assertEqual(veille.collection_dir({"key": "k", "collection": veille.ARTICLES_DIR.name}),
                         veille.WATCH_DIR / veille.ARTICLES_DIR.name)
        self.assertEqual(veille.collection_dir({"key": "k", "collection": watch_paths.OWN_COLLECTION}),
                         veille.WATCH_DIR / "own-articles")

    def test_chargement_refuse_une_collection_hors_motif(self):
        for valeur in ("..", "a/b", "/etc"):
            with self.subTest(valeur=valeur), tempfile.TemporaryDirectory() as tmp:
                dossier = Path(tmp)
                (dossier / "sources.local.yaml").write_text(
                    f"sources:\n  - key: k\n    name: K\n    collection: \"{valeur}\"\n", encoding="utf-8")
                with mock.patch.object(veille, "SOURCES_FILE", dossier / "sources.yaml"), \
                        mock.patch.object(veille, "local_config_dir", return_value=dossier):
                    with self.assertRaises(ErreurConfig):
                        veille.load_sources()

    def test_chargement_accepte_own_articles(self):
        with tempfile.TemporaryDirectory() as tmp:
            dossier = Path(tmp)
            (dossier / "sources.local.yaml").write_text(
                "sources:\n  - key: k\n    name: K\n    collection: own-articles\n", encoding="utf-8")
            with mock.patch.object(veille, "SOURCES_FILE", dossier / "sources.yaml"), \
                    mock.patch.object(veille, "local_config_dir", return_value=dossier):
                self.assertEqual([s["key"] for s in veille.load_sources()], ["k"])

    def test_import_medium_refuse_avant_d_ouvrir_la_base(self):
        for valeur in ("../x", "a/b", ""):
            with self.subTest(valeur=valeur):
                args = argparse.Namespace(source="k", collection=valeur, export="inexistant.zip", min_chars=1)
                with mock.patch.object(veille, "open_store",
                                       side_effect=AssertionError("open_store appelé avant le refus")) as ouvre, \
                        mock.patch.object(veille, "load_sources", return_value=[]):
                    with self.assertRaises(ErreurConfig):
                        veille.import_medium(args)
                ouvre.assert_not_called()


if __name__ == "__main__":
    unittest.main()
