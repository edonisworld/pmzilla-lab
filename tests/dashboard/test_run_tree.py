"""
Le tableau de bord lit son contenu dans le dossier de contenu (PMZILLA_LAB_WORKSPACE) et ses réglages suivis et scripts dans le dossier
de code, déduit de son propre fichier (run-worktree D2, tâche 7.3).

    uv run --with pyyaml python -m unittest discover -s tests/dashboard -v

Dossier d'exécution factice : une copie de tools/ dans un dossier temporaire (avec le lanceur du faux lecteur à la même place relative),
distincte du dossier de contenu factice. Rien n'est lu dans le vrai dépôt, aucune vraie base n'est jointe.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import test_dashboard as base

TOOLS = Path(__file__).resolve().parents[2] / "tools"


class DossierDExecution(unittest.TestCase):
    def test_reglages_suivis_et_scripts_viennent_du_dossier_de_code_le_contenu_du_dossier_de_contenu(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            env = base.donnees_completes(root)
            ws = root / "workspace"                                    # contenu : journal, rapports, mapping local de l'ancien test
            base.write(ws / "watch" / "tri.yaml", "mode: filtre\n")    # ne doit pas être lu
            run = root / "run"
            shutil.copytree(TOOLS, run / "tools", ignore=shutil.ignore_patterns("__pycache__"))
            (run / "tests" / "dashboard").mkdir(parents=True)
            shutil.copy(base.RUNNER, run / "tests" / "dashboard" / "run_with_fake_library.py")
            base.write(run / "watch" / "tri.yaml", "mode: observation\n")
            base.write(run / "tools" / "mapping_lab.py", "MAPPING = {\n    # À re-télécharger d'une autre source :\n    #   Livre Fictif F (Auteur Fictif) F.\n\n    'x': 'F',\n}\n")
            sortie = root / "page.html"
            env = {**base.without_cases_variables(os.environ), **env, "PMZILLA_LAB_TODAY": "2026-10-12",
                   "PMZILLA_TEST_CODE_ROOT": "derived"}
            resultat = subprocess.run([sys.executable, str(run / "tests" / "dashboard" / "run_with_fake_library.py"), "--output", str(sortie)],
                                      capture_output=True, text=True, env=env, timeout=120)
            self.assertEqual(resultat.returncode, 0, resultat.stderr)
            page = sortie.read_text(encoding="utf-8")
            self.assertIn('<span class="badge warn">observation</span>', page)          # tri.yaml du dossier de code
            self.assertNotIn('<span class="badge ok">filtre</span>', page)
            self.assertIn("<li>Livre Fictif F (Auteur Fictif)</li>", page)           # mapping_lab.py du dossier de code
            self.assertNotIn("Livre Fictif A", page)
            self.assertIn("Décrire la règle", page)                                     # journal : dossier de contenu
            self.assertEqual(sorted(p.name for p in (run).iterdir() if p.name not in ("tools", "tests", "watch")), [])   # rien d'écrit dans le dossier de code


if __name__ == "__main__":
    unittest.main()
