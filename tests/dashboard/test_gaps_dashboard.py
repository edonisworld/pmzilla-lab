"""
Tests complémentaires du tableau de bord (tools/dashboard.py) : critère d'un passage « partiel » (openspec/test-gaps.md,
posture-evals). Données fictives, aucune source réelle.

    uv run --with pyyaml python -m unittest discover -s tests/dashboard -v
"""
import tempfile
import unittest
from pathlib import Path

import test_dashboard as base

CAS = {"cas-un": ("3/3", "0.10")}


def passages(root: Path, totaux: list[tuple[str, int, int]]) -> dict:
    """Un rapport par (date, réussies, total) ; le dernier de la liste est le plus récent."""
    ws = root / "workspace"
    for i, (date, ok, total) in enumerate(totaux):
        base.write(ws / "_bmad-output" / "essais" / f"essai-{date}-100000.md",
                   base.rapport(date, "100000", f"{i + 1}" * 7, ok, "", CAS, total=total))
    return {"PMZILLA_LAB_WORKSPACE": str(ws), "PMZILLA_LAB_DATA": str(root / "data"), "PMZILLA_LAB_LOGS": str(root / "logs")}


class PassagePartiel(unittest.TestCase):
    def test_un_passage_avec_moins_de_verifications_qu_un_jeu_complet_est_partiel(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = passages(root, [("2026-10-08", 2, 3), ("2026-10-09", 3, 4), ("2026-10-10", 6, 6), ("2026-10-11", 5, 6)])
            resultat, page = base.generer(root, env)
            self.assertEqual(resultat.returncode, 0, resultat.stderr)
            self.assertIn("2 passages partiels écartés", page)        # 3 et 4 vérifications, contre 6 au dernier jeu complet
            self.assertIn("2 derniers passages complets", page)       # seuls les deux passages à 6 vérifications comptent
            self.assertNotIn("1111111", page)                         # les commits des passages partiels ne sont pas montrés
            self.assertNotIn("2222222", page)
            self.assertIn("3333333", page)
            self.assertIn("4444444", page)

    def test_des_passages_tous_au_meme_nombre_de_verifications_ne_sont_pas_partiels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = passages(root, [("2026-10-09", 6, 6), ("2026-10-10", 5, 6), ("2026-10-11", 6, 6)])
            resultat, page = base.generer(root, env)
            self.assertEqual(resultat.returncode, 0, resultat.stderr)
            self.assertNotIn("passage partiel", page)
            self.assertNotIn("passages partiels écartés", page)
            self.assertIn("3 derniers passages complets", page)

    def test_un_passage_avec_plus_de_verifications_que_le_dernier_rapport_est_partiel(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = passages(root, [("2026-10-09", 8, 8), ("2026-10-10", 6, 6), ("2026-10-11", 5, 6)])
            resultat, page = base.generer(root, env)
            self.assertEqual(resultat.returncode, 0, resultat.stderr)
            self.assertIn("1 passage partiel écarté", page)           # 8 vérifications contre 6 au rapport le plus récent
            self.assertNotIn("1111111", page)                         # son commit n'est pas montré
            self.assertIn("2 derniers passages complets", page)
            self.assertIn("2222222", page)


class LecteurReelExperiences(unittest.TestCase):
    """Le lecteur réel se connecte avec le rôle en lecture des cas et un délai court (connexion simulée)."""

    def test_role_de_lecture_et_delai_court(self):
        import sys
        from unittest import mock
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
        import cases_store
        import dashboard
        faux = mock.MagicMock()
        jour = dashboard.dt.date(2026, 10, 10)
        with mock.patch.object(cases_store, "connect_cases", return_value=faux) as connexion, \
                mock.patch.object(cases_store, "running_experiments", return_value=[{"number": 1}]) as lecture:
            lignes = dashboard.fetch_running_experiments("un-role", jour)
        self.assertEqual(lignes, [{"number": 1}])
        connexion.assert_called_once_with(cases_store.ROLE_READ, timeout=dashboard.CASES_TIMEOUT_SECONDS)
        self.assertLessEqual(dashboard.CASES_TIMEOUT_SECONDS, 5)      # délai court
        lecture.assert_called_once_with(faux, "un-role", jour)
        faux.close.assert_called_once_with()                          # connexion fermée

    def test_connexion_fermee_meme_si_la_lecture_echoue(self):
        import sys
        from unittest import mock
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
        import cases_store
        import dashboard
        faux = mock.MagicMock()
        with mock.patch.object(cases_store, "connect_cases", return_value=faux), \
                mock.patch.object(cases_store, "running_experiments", side_effect=RuntimeError("panne")):
            with self.assertRaises(RuntimeError):
                dashboard.fetch_running_experiments("un-role", dashboard.dt.date(2026, 10, 10))
        faux.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
