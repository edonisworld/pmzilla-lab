"""
Run-worktree D2 (tâche 7.3) : watch_triage.py lit tri.yaml (suivi) dans son dossier de code et tri.local.yaml, Watch-Lab et le dossier des
écartés dans le dossier de contenu, PMZILLA_LAB_WORKSPACE. Dossier d'exécution factice : une copie de tools/ dans un sous-processus.
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
import watch_triage as t
print(json.dumps({"config": str(t.CONFIG_FILE), "local": str(t.local_config_file()), "archive": str(t.ARCHIVE_DIR),
                  "reglages": t.config(create=False)}))
"""


class DossierDExecution(unittest.TestCase):
    def setUp(self):
        self.racine = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.run = self.racine / "run"
        shutil.copytree(TOOLS, self.run / "tools", ignore=shutil.ignore_patterns("__pycache__"))
        (self.run / "watch").mkdir()
        (self.run / "watch" / "sources.yaml").write_text("sources: []\n", encoding="utf-8")
        (self.run / "watch" / "tri.yaml").write_text("mode: observation\nrelevance_threshold: 30\n", encoding="utf-8")
        self.contenu = self.racine / "contenu"
        (self.contenu / "watch").mkdir(parents=True)
        (self.contenu / "Watch-Lab").mkdir()
        (self.contenu / "watch" / "tri.yaml").write_text("mode: filtre\n", encoding="utf-8")        # ne doit pas être lu
        (self.contenu / "watch" / "tri.local.yaml").write_text("bluesky: essai.example\n", encoding="utf-8")

    def sonde(self) -> dict:
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PMZILLA_", "VEILLE_LAB_"))}
        env.update(HOME=str(self.racine), PMZILLA_LAB_WORKSPACE=str(self.contenu))
        resultat = subprocess.run([sys.executable, "-c", SONDE, str(self.run / "tools")], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        return json.loads(resultat.stdout.strip().splitlines()[-1])

    def test_tri_yaml_du_dossier_de_code_et_couche_locale_du_contenu(self):
        lu = self.sonde()
        self.assertEqual(lu["config"], str(self.run / "watch" / "tri.yaml"))
        self.assertEqual(lu["local"], str(self.contenu / "watch" / "tri.local.yaml"))
        self.assertEqual(lu["reglages"]["mode"], "observation")                    # pas le « filtre » du dossier de contenu
        self.assertEqual(lu["reglages"]["bluesky"], "essai.example")        # couche locale du contenu

    def test_les_articles_ecartes_vivent_a_cote_de_watch_lab_dans_le_contenu(self):
        self.assertEqual(self.sonde()["archive"], str(self.contenu / "Watch-Excluded" / "watch"))


ECRITURE = """
import sys
sys.path.insert(0, sys.argv[1])
import watch_triage as t
t.set_config("relevance_threshold", 55)
"""

PHRASE = "réglages suivis par Git : à modifier depuis le dépôt de développement, puis à commiter"


class EnregistrementDepuisLeDossierDExecution(unittest.TestCase):
    """Décision D15 : set_config refuse d'écrire tri.yaml quand le dossier de code est le dossier d'exécution."""

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.run = self.racine / "run"
        shutil.copytree(TOOLS, self.run / "tools", ignore=shutil.ignore_patterns("__pycache__"))
        (self.run / "watch").mkdir()
        (self.run / "watch" / "sources.yaml").write_text("sources: []\n", encoding="utf-8")
        (self.run / "watch" / "tri.yaml").write_text("mode: observation\nrelevance_threshold: 30\n", encoding="utf-8")
        self.contenu = self.racine / "contenu"
        (self.contenu / "watch").mkdir(parents=True)
        (self.contenu / "Watch-Lab").mkdir()

    def ecrit(self, code: Path, run: Path):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("PMZILLA_", "VEILLE_LAB_"))}
        env.update(HOME=str(self.racine), PMZILLA_LAB_WORKSPACE=str(self.contenu), PMZILLA_LAB_RUN=str(run))
        return subprocess.run([sys.executable, "-c", ECRITURE, str(code / "tools")], env=env, capture_output=True, text=True, timeout=60)

    def test_refus_depuis_le_dossier_d_execution_fichier_inchange(self):
        fichier = self.run / "watch" / "tri.yaml"
        avant = fichier.read_bytes()
        resultat = self.ecrit(self.run, self.run)
        self.assertNotEqual(resultat.returncode, 0)
        self.assertIn(PHRASE, resultat.stderr)
        self.assertEqual(fichier.read_bytes(), avant)

    def test_depot_de_developpement_l_enregistrement_reste_permis(self):
        shutil.copytree(self.run / "tools", self.contenu / "tools")
        shutil.copy(self.run / "watch" / "tri.yaml", self.contenu / "watch" / "tri.yaml")
        shutil.copy(self.run / "watch" / "sources.yaml", self.contenu / "watch" / "sources.yaml")
        resultat = self.ecrit(self.contenu, self.run)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertIn("relevance_threshold: 55", (self.contenu / "watch" / "tri.yaml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
