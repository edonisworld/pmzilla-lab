"""
MasquageInstable rattrapée par main de tools/flow_views.py (audit #629, A-89 ; R-20261109-19).

    uv run --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/flow_views -v

Sans base : lignes_publiees et cellules_masquees sont remplacés par des doubles qui lèvent MasquageInstable. Sortie attendue : code 4, une phrase fixe
du catalogue sur la sortie d'erreur, rien sur la sortie standard, ni le texte de l'exception ni trace Python. Le masquage reste un échec fermé.
"""
import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import flow_views as fv  # noqa: E402

TEXTE_TEMOIN = "ZzTexteDeLExceptionDistinctif"
PHRASE = {"fr": "Masquage instable : rien n'est publié.", "en": "Unstable masking: nothing is published."}


def double_leve(*args, **kwargs):
    raise fv.MasquageInstable(TEXTE_TEMOIN)


def lancer(argv, langue):
    sortie, erreur = io.StringIO(), io.StringIO()
    with mock.patch.object(fv, "seuil_configure", return_value=fv.PLANCHER), \
            mock.patch.object(fv, "lire_avec_liees", return_value=(["team", "tickets"], [("A", 9)], {})), \
            mock.patch.object(fv, "lire", return_value=(["team", "tickets"], [("A", 9)])), \
            mock.patch.object(fv, "lignes_publiees", side_effect=double_leve), \
            mock.patch.object(fv, "cellules_masquees", side_effect=double_leve), \
            contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
        code = fv.main(["--language", langue] + argv)
    return code, sortie.getvalue(), erreur.getvalue()


class MasquageInstableSortie(unittest.TestCase):
    def verifier(self, argv, langue):
        code, sortie, erreur = lancer(argv, langue)
        self.assertEqual(code, 4)
        self.assertEqual(sortie, "")
        self.assertEqual(erreur.strip(), PHRASE[langue])
        self.assertNotIn(TEXTE_TEMOIN, erreur)
        self.assertNotIn("Traceback", erreur)

    def test_show_francais(self):
        self.verifier(["show", "v_team_status"], "fr")

    def test_show_anglais(self):
        self.verifier(["show", "v_team_status"], "en")

    def test_masked_cells_francais(self):
        self.verifier(["masked-cells"], "fr")

    def test_masked_cells_anglais(self):
        self.verifier(["masked-cells"], "en")


if __name__ == "__main__":
    unittest.main()
