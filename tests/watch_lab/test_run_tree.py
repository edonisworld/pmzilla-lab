"""
Run-worktree D2 (tâche 7.3) : watch_lab.py lit les sources suivies dans son dossier de code (déduit de son propre fichier, liens suivis)
et le contenu (Watch-Lab, sources.local.yaml) dans le dossier de contenu, PMZILLA_LAB_WORKSPACE.

Dossier d'exécution factice : une copie de tools/ dans un dossier temporaire, lancée dans un sous-processus, avec un faux HOME.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"

SONDE = """
import json, sys
sys.path.insert(0, sys.argv[1])
import watch_lab
print(json.dumps({"sources": str(watch_lab.SOURCES_FILE), "local": str(watch_lab.local_sources_file()),
                  "watch_dir": str(watch_lab.WATCH_DIR), "cles": [s["key"] for s in watch_lab.load_sources()]}))
"""


def arbre_d_execution(racine: Path) -> Path:
    run = racine / "run"
    shutil.copytree(TOOLS, run / "tools", ignore=shutil.ignore_patterns("__pycache__"))
    (run / "watch").mkdir()
    (run / "watch" / "sources.yaml").write_text("sources:\n- key: suivie\n  name: Suivie\n  active: true\n", encoding="utf-8")
    (run / "watch" / "tri.yaml").write_text("mode: observation\n", encoding="utf-8")
    return run


class DossierDExecution(unittest.TestCase):
    def setUp(self):
        self.racine = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.run = arbre_d_execution(self.racine)
        self.contenu = self.racine / "contenu"
        (self.contenu / "watch").mkdir(parents=True)
        (self.contenu / "watch" / "sources.local.yaml").write_text("sources:\n- key: locale\n  name: Locale\n", encoding="utf-8")
        (self.contenu / "watch" / "sources.yaml").write_text("sources:\n- key: du-contenu\n  name: X\n", encoding="utf-8")   # ne doit pas être lu
        (self.contenu / "Watch-Lab").mkdir()

    def sonde(self, code: Path) -> dict:
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PMZILLA_", "VEILLE_LAB_"))}
        env.update(HOME=str(self.racine), PMZILLA_LAB_WORKSPACE=str(self.contenu))
        resultat = subprocess.run([sys.executable, "-c", SONDE, str(code / "tools")], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        return json.loads(resultat.stdout.strip().splitlines()[-1])

    def test_sources_suivies_du_dossier_de_code_et_locales_du_contenu(self):
        lu = self.sonde(self.run)
        self.assertEqual(lu["sources"], str(self.run / "watch" / "sources.yaml"))
        self.assertEqual(lu["local"], str(self.contenu / "watch" / "sources.local.yaml"))
        self.assertEqual(lu["watch_dir"], str(self.contenu / "Watch-Lab"))
        self.assertEqual(lu["cles"], ["suivie", "locale"])

    def test_lien_suivi_le_dossier_de_code_est_la_cible(self):
        lien = self.racine / "lab"
        lien.mkdir()
        (lien / "watch_lab.py").symlink_to(self.run / "tools" / "watch_lab.py")
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PMZILLA_", "VEILLE_LAB_"))}
        env.update(HOME=str(self.racine), PMZILLA_LAB_WORKSPACE=str(self.contenu))
        sonde = SONDE.replace("sys.path.insert(0, sys.argv[1])", "sys.path.insert(0, sys.argv[1])\nimport importlib.util\n"
                              "spec = importlib.util.spec_from_file_location('watch_lab', sys.argv[2])")
        sonde = sonde.replace("import watch_lab\n", "watch_lab = importlib.util.module_from_spec(spec); sys.modules['watch_lab'] = watch_lab; "
                              "spec.loader.exec_module(watch_lab)\n")
        resultat = subprocess.run([sys.executable, "-c", sonde, str(self.run / "tools"), str(lien / "watch_lab.py")], env=env,
                                  capture_output=True, text=True, timeout=60)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertEqual(json.loads(resultat.stdout.strip().splitlines()[-1])["sources"], str(self.run / "watch" / "sources.yaml"))

    def test_depot_de_developpement_les_deux_dossiers_n_en_font_qu_un(self):
        shutil.copy(self.run / "watch" / "sources.yaml", self.contenu / "watch" / "sources.yaml")
        shutil.copytree(self.run / "tools", self.contenu / "tools")
        lu = self.sonde(self.contenu)
        self.assertEqual(lu["sources"], str(self.contenu / "watch" / "sources.yaml"))
        self.assertEqual(lu["local"], str(self.contenu / "watch" / "sources.local.yaml"))
        self.assertEqual(lu["cles"], ["suivie", "locale"])


ECRITURE = """
import sys
sys.path.insert(0, sys.argv[1])
import watch_lab
watch_lab.save_sources([{"key": "nouvelle", "name": "Nouvelle", "active": True}])
"""

PHRASE = "réglages suivis par Git : à modifier depuis le dépôt de développement, puis à commiter"


class EnregistrementDepuisLeDossierDExecution(unittest.TestCase):
    """Décision D15 : save_sources refuse d'écrire sources.yaml quand le dossier de code est le dossier d'exécution."""

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.run = arbre_d_execution(self.racine)
        self.contenu = self.racine / "contenu"
        (self.contenu / "watch").mkdir(parents=True)
        (self.contenu / "Watch-Lab").mkdir()

    def ecrit(self, code: Path, run: Path):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PMZILLA_", "VEILLE_LAB_"))}
        env.update(HOME=str(self.racine), PMZILLA_LAB_WORKSPACE=str(self.contenu), PMZILLA_LAB_RUN=str(run))
        return subprocess.run([sys.executable, "-c", ECRITURE, str(code / "tools")], env=env, capture_output=True, text=True, timeout=60)

    def test_refus_depuis_le_dossier_d_execution_fichier_inchange(self):
        fichier = self.run / "watch" / "sources.yaml"
        avant = fichier.read_bytes()
        resultat = self.ecrit(self.run, self.run)
        self.assertNotEqual(resultat.returncode, 0)
        self.assertIn(PHRASE, resultat.stderr)
        self.assertEqual(fichier.read_bytes(), avant)

    def test_refus_aussi_par_un_chemin_de_lien(self):
        lien = self.racine / "lien-run"
        lien.symlink_to(self.run)
        resultat = self.ecrit(self.run, lien)
        self.assertNotEqual(resultat.returncode, 0)
        self.assertIn(PHRASE, resultat.stderr)

    def test_depot_de_developpement_l_enregistrement_reste_permis(self):
        shutil.copytree(self.run / "tools", self.contenu / "tools")
        shutil.copy(self.run / "watch" / "sources.yaml", self.contenu / "watch" / "sources.yaml")
        resultat = self.ecrit(self.contenu, self.run)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertIn("nouvelle", (self.contenu / "watch" / "sources.yaml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
