"""
Run-worktree D5 (tâche 7.3) : le catalogue des livres par défaut est lu à côté du fichier résolu de pmzilla_lab_library.py (le dossier de
code), jamais dans un chemin fixe du dépôt de développement. Dossier d'exécution factice dans un dossier temporaire, lien du dossier du
laboratoire, faux HOME.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"

SONDE = """
import importlib.util, sys
sys.path.insert(0, sys.argv[2])
spec = importlib.util.spec_from_file_location("pmzilla_lab_library", sys.argv[1])
m = importlib.util.module_from_spec(spec); sys.modules["pmzilla_lab_library"] = m; spec.loader.exec_module(m)
print(m.CATALOGUE_PATH)
"""


class CatalogueParDefaut(unittest.TestCase):
    def setUp(self):
        self.racine = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.run = self.racine / "run"
        (self.run / "tools").mkdir(parents=True)
        for nom in ("pmzilla_lab_library.py", "watch_paths.py"):
            shutil.copy(TOOLS / nom, self.run / "tools" / nom)
        (self.run / "tools" / "book_catalog.yaml").write_text("books: []\n", encoding="utf-8")
        (self.racine / "PMZilla-Lab" / "workspace" / "tools").mkdir(parents=True)            # le chemin fixe d'avant : un autre catalogue
        (self.racine / "PMZilla-Lab" / "workspace" / "tools" / "book_catalog.yaml").write_text("books: []\n", encoding="utf-8")
        self.lien = self.racine / "PMZilla-Lab" / "pmzilla_lab_library.py"
        self.lien.symlink_to(self.run / "tools" / "pmzilla_lab_library.py")

    def chemin(self, fichier: Path, **env) -> str:
        e = {k: v for k, v in os.environ.items() if not k.startswith("PMZILLA_")}
        e.update(HOME=str(self.racine), **env)
        r = subprocess.run([sys.executable, "-c", SONDE, str(fichier), str(self.run / "tools")], env=e, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip().splitlines()[-1]

    def test_le_catalogue_est_a_cote_du_fichier_du_dossier_d_execution(self):
        self.assertEqual(self.chemin(self.run / "tools" / "pmzilla_lab_library.py"), str(self.run / "tools" / "book_catalog.yaml"))

    def test_lance_par_son_lien_le_catalogue_est_celui_de_la_cible(self):
        self.assertEqual(self.chemin(self.lien), str(self.run / "tools" / "book_catalog.yaml"))

    def test_la_variable_garde_la_priorite(self):
        autre = self.racine / "autre.yaml"
        self.assertEqual(self.chemin(self.lien, PMZILLA_LAB_CATALOGUE=str(autre)), str(autre))


if __name__ == "__main__":
    unittest.main()
