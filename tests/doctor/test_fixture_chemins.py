"""Le fixture du doctor travaille en chemins réels (R-20261111-13, R-20261111-16).

Sous macOS, TMPDIR passe par un lien (/var -> /private/var) : un dossier temporaire non résolu diffère de ce que
lab_paths.content_root() et train_auto recalculent (chemin réel). Le test impose un TMPDIR qui passe par un lien,
sur toute plateforme, pour que le défaut soit visible hors macOS aussi.

    uv run --with pyyaml python -m unittest discover -s tests/doctor -v
"""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aide_doctor  # noqa: E402
from aide_doctor import Labo  # noqa: E402


def _tmpdir_par_un_lien(testcase) -> Path:
    reel = Path(tempfile.mkdtemp(prefix="doctor-lien-reel.")).resolve()
    testcase.addCleanup(shutil.rmtree, reel, ignore_errors=True)
    lien = reel.parent / (reel.name + "-lien")
    os.symlink(reel, lien)
    testcase.addCleanup(os.unlink, lien)
    return lien


class BaseDuLabo(Labo):
    def setUp(self):
        aide_doctor.modele_du_depot()   # R-20261111-23 : le modèle en cache se construit avant le patch du dossier temporaire, sinon il vit sous un dossier effacé
        lien = _tmpdir_par_un_lien(self)
        patch = mock.patch.object(tempfile, "tempdir", str(lien))
        patch.start()
        self.addCleanup(patch.stop)
        super().setUp()

    def test_la_base_du_fixture_est_un_chemin_reel(self):
        self.assertEqual(self.base, self.base.resolve())


class RacineDuModele(unittest.TestCase):
    def test_la_racine_de_modele_du_depot_est_un_chemin_reel(self):
        lien = _tmpdir_par_un_lien(self)
        with mock.patch.object(tempfile, "tempdir", str(lien)), mock.patch.object(aide_doctor, "_MODELE", []):
            racine = aide_doctor.modele_du_depot()
        self.assertEqual(racine, racine.resolve())


class OrdreDesTests(unittest.TestCase):
    def test_le_modele_en_cache_survit_a_la_base_du_fixture(self):
        """R-20261111-23 : lancé en premier avec un cache vide, BaseDuLabo ne laisse pas aux tests Labo suivants un modèle sous un dossier effacé."""
        with mock.patch.object(aide_doctor, "_MODELE", []):
            resultat = unittest.TestResult()
            unittest.defaultTestLoader.loadTestsFromTestCase(BaseDuLabo).run(resultat)
            self.assertTrue(resultat.wasSuccessful(), resultat.failures + resultat.errors)
            self.assertTrue(aide_doctor.modele_du_depot().exists())


if __name__ == "__main__":
    unittest.main()
