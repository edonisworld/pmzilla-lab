"""
Tests du code de sortie de `library_parity.main` (parcours complet) sur deux fausses voies, sans base ni Ollama.

    bash tests/run_all.sh parity

Le service d'embedding est remplacé par celui de la bibliothèque inventée ; les deux voies (SQLite et PostgreSQL) sont des doublures
qui rendent des résultats fixes : le code de sortie ne dépend que du verdict de parité.
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
sys.path.insert(0, str(RACINE / "tests" / "fixtures_library"))
import library_parity as lp          # noqa: E402
import pmzilla_lab_library as library  # noqa: E402
import knowledge_library             # noqa: E402
import demo_library as demo          # noqa: E402


def voie(fichiers):
    """Classe doublure : rend toujours les mêmes huit passages (fichier, position)."""
    class Voie:
        def __init__(self, *args, **options):
            pass

        def search(self, query, collections, limit, since=None, types=None, component="hybrid"):
            return [{"file": f, "position": 0, "text": "texte inventé"} for f in fichiers[:limit]]

        def connection(self):
            raise AssertionError("pas de connexion attendue")
    return Voie


COMMUNS = [f"livre-{i}.md" for i in range(8)]
AUTRES = [f"autre-{i}.md" for i in range(8)]


class CodeDeSortie(unittest.TestCase):
    def lancer(self, sqlite, postgres):
        with tempfile.TemporaryDirectory() as dossier:
            requetes = Path(dossier) / "q.yaml"
            requetes.write_text("queries:\n  - {id: q1, lang: fr, query: le flux}\n  - {id: q2, lang: en, query: flow}\n", encoding="utf-8")
            sortie = io.StringIO()
            with mock.patch.object(library, "embed", demo.fake_embed), \
                    mock.patch.object(library, "Library", voie(sqlite)), \
                    mock.patch.object(knowledge_library, "PostgresLibrary", voie(postgres)), \
                    contextlib.redirect_stdout(sortie):
                code = lp.main(["--queries", str(requetes)])
        return code, sortie.getvalue()

    def test_parite_atteinte_code_0(self):
        code, texte = self.lancer(COMMUNS, COMMUNS)
        self.assertEqual(code, 0)
        self.assertNotIn("PARITÉ NON ATTEINTE", texte)

    def test_parite_non_atteinte_code_1(self):
        code, texte = self.lancer(COMMUNS, AUTRES)
        self.assertEqual(code, 1)
        self.assertIn("PARITÉ NON ATTEINTE", texte)


if __name__ == "__main__":
    unittest.main()
