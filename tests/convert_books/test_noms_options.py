"""convert_books.py : options en anglais, anciens noms refusés avec le nom actuel (lot 8).

Les fonctions de conversion sont remplacées par des enregistreurs : aucun livre n'est ouvert."""
import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import convert_books as cb  # noqa: E402


def lancer(*arguments):
    """Retourne (appels, erreur, code de sortie ou None)."""
    erreur = io.StringIO()
    appels = []
    code = None
    with mock.patch.object(sys, "argv", ["convert_books.py", *arguments]), contextlib.redirect_stderr(erreur), \
            mock.patch.object(cb, "figure_statistics", lambda a: appels.append(("stats", a))), \
            mock.patch.object(cb, "convert_one", lambda a: appels.append(("one", a))):
        try:
            cb.main()
        except SystemExit as stop:
            code = stop.code
    return appels, erreur.getvalue(), code


class Options(unittest.TestCase):
    def test_nouveaux_noms_sans_message(self):
        appels, erreur, code = lancer("--figure-statistics", "livres")
        self.assertEqual(appels, [("stats", ["livres"])])
        self.assertEqual((erreur, code), ("", None))
        appels, erreur, code = lancer("livres", "md", "--convert-book", "B", "--to", "X.md")
        self.assertEqual(appels, [("one", ["livres", "md", "--convert-book", "B", "--to", "X.md"])])
        self.assertEqual((erreur, code), ("", None))

    def test_anciens_noms_refuses_avec_le_nom_actuel(self):
        for ancien, actuel, arguments in (
                ("--statistiques-figures", "--figure-statistics", ("--statistiques-figures", "livres")),
                ("--convertir-livre", "--convert-book", ("livres", "md", "--convertir-livre", "B")),
                ("--vers", "--to", ("livres", "md", "--convert-book", "B", "--vers", "X.md")),
                ("--refaire-figures", "--redo-figures", ("livres", "md", "--refaire-figures")),
                ("--simuler", "--dry-run", ("livres", "md", "--simuler"))):
            with self.subTest(ancien=ancien):
                appels, erreur, code = lancer(*arguments)
                self.assertEqual(code, 2)
                self.assertEqual(appels, [])                 # rien n'a été converti
                self.assertIn(f"« {ancien} »", erreur)
                self.assertIn(f"« {actuel} »", erreur)

    def test_ancien_nom_avec_valeur_collee_refuse(self):
        appels, erreur, code = lancer("livres", "md", "--vers=X.md")
        self.assertEqual((appels, code), ([], 2))
        self.assertIn("« --to »", erreur)

    def test_recalculer_de_l_indexation_refuse(self):
        import pmzilla_lab_library as lib
        recu = []
        erreur = io.StringIO()
        with mock.patch.object(sys, "argv", ["pmzilla_lab_library.py", "index", "dossier", "--recalculer", "livre.md"]), \
                mock.patch.object(lib, "index", lambda dossiers, force: recu.append((dossiers, force))), \
                contextlib.redirect_stderr(erreur), self.assertRaises(SystemExit) as stop:
            lib.main()
        self.assertEqual(stop.exception.code, 2)
        self.assertEqual(recu, [])                            # rien n'est recalculé
        self.assertIn("« --recalculer »", erreur.getvalue())
        self.assertIn("« --recompute »", erreur.getvalue())


if __name__ == "__main__":
    unittest.main()
