"""Une seule lecture du verrou dans pilot.freeze_state (R-20261108-11) : la décision et le message viennent de la même lecture.
Test déterministe, sans sous-processus : freeze_scope est remplacé par un faux qui rend « tenu » au premier appel puis « libre » aux suivants.

    python3 -W ignore -m unittest discover -s tests/pilot -p test_pilot_une_lecture.py -q
"""
import io
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aide_pilot  # noqa: E402,F401  (met tools/ dans sys.path)
import finish_lock  # noqa: E402
import pilot  # noqa: E402

TOP = os.path.realpath("/")   # worktree de l'appelant : la racine, dont le chemin réel est lui-même


def portee(tenu):
    return {"held": tenu, "stale": False, "readable": True, "branch": "feat/autre", "start": 1000, "token": "jeton-train",
            "worktrees": [TOP] if tenu else [], "branches": []}


class UneSeuleLecture(unittest.TestCase):
    def test_verrou_disparu_entre_les_deux_lectures(self):
        appels = []

        def faux_scope(common, now=None):
            appels.append(1)
            return portee(len(appels) == 1)

        t = pilot.Messages(pilot.CATALOGS, "fr")
        with mock.patch.object(finish_lock, "freeze_scope", faux_scope), \
                mock.patch.object(pilot, "git", lambda *a, **k: (0, TOP + "\n")), \
                mock.patch.dict(os.environ, {"FINISH_LOCK_TOKEN": ""}):
            etat, verrou = pilot.freeze_state("/commun")
        self.assertEqual(len(appels), 1, "le verrou n'est lu qu'une fois")
        self.assertEqual(etat, "tenu", "jamais freeze_other avec un verrou absent : la décision suit la première lecture")
        self.assertEqual(verrou["branch"], "feat/autre")
        sortie, erreur = io.StringIO(), io.StringIO()
        with redirect_stderr(erreur), redirect_stdout(sortie):
            code = pilot.freeze_report(etat, verrou, t)
        self.assertEqual(code, 4)
        self.assertEqual(sortie.getvalue(), "", "aucun message freeze_other (stdout)")
        self.assertIn("feat/autre", erreur.getvalue(), "le message tenu vient de la même lecture que la décision")

    def test_freezes_avec_scope_ne_relit_pas_le_verrou(self):
        faux = mock.Mock(side_effect=AssertionError("freeze_scope ne doit pas être appelé"))
        with mock.patch.object(finish_lock, "freeze_scope", faux):
            rendu = finish_lock.freezes("/commun", TOP, "", scope=portee(True))
            libre = finish_lock.freezes("/commun", TOP, "", scope=portee(False))
        self.assertIsNotNone(rendu)
        self.assertIsNone(libre)
        faux.assert_not_called()

    def test_sans_scope_freezes_lit_le_verrou(self):
        faux = mock.Mock(return_value=portee(False))
        with mock.patch.object(finish_lock, "freeze_scope", faux):
            self.assertIsNone(finish_lock.freezes("/commun", TOP, ""))
        faux.assert_called_once()


if __name__ == "__main__":
    unittest.main()
