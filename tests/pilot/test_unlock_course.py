"""Déblocage du verrou de fin : course entre la décision et le renommage (revue Opus de O3, audit #629 ; R-20261107-30 point 5).

Un verrou périmé sans pid ni jeton est jugé retirable ; si, entre la décision et le renommage, une fin neuve recrée le dossier (mkdir, pid et
jeton pas encore écrits), unlock ne doit pas supprimer ce dossier neuf : son identité (inode) diffère, il est remis en place, code 1.
Remplace : rien (cas neuf). Retrait : permanent.
"""
import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import finish_lock  # noqa: E402


class CourseDuDeblocage(unittest.TestCase):
    def setUp(self):
        self.commun = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.commun, True)
        self.dossier = self.commun / finish_lock.LOCK_NAME
        self.dossier.mkdir()
        (self.dossier / "branche").write_text("feat/autre\n", encoding="utf-8")
        os.utime(self.dossier, (1577836800, 1577836800))   # 2020-01-01 : périmé, sans pid lisible ni jeton

    def debloquer(self):
        sortie = io.StringIO()
        with mock.patch.dict(os.environ, {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}, clear=True), redirect_stdout(sortie):
            code = finish_lock.unlock(str(self.commun))
        return code, sortie.getvalue()

    def test_un_verrou_perime_sans_course_est_retire(self):
        code, _ = self.debloquer()
        self.assertEqual(code, 0)
        self.assertFalse(self.dossier.exists())

    def test_un_dossier_recree_avant_le_renommage_est_remis_en_place(self):
        vrai_rename = os.rename
        appels = []

        def rename_avec_course(source, cible):
            if not appels:   # premier renommage (dossier -> retrait) : une fin neuve a recréé le dossier juste avant
                # l'ancien dossier est mis de côté, pas supprimé : un système de fichiers peut réattribuer tout de suite l'inode libéré
                # (constaté dans le conteneur Linux), ce qui ne simulerait plus un dossier neuf
                vrai_rename(self.dossier, self.commun / "ancien-verrou")
                os.mkdir(self.dossier)
            appels.append((source, cible))
            return vrai_rename(source, cible)

        with mock.patch.object(finish_lock.os, "rename", side_effect=rename_avec_course):
            code, sortie = self.debloquer()
        self.assertEqual(code, 1)
        self.assertTrue(self.dossier.is_dir(), "le dossier de la fin neuve doit être remis en place")
        self.assertIn("a changé pendant le retrait", sortie)


if __name__ == "__main__":
    unittest.main()
