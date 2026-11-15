"""R-20261110-42 : doctor_state de bout en bout. Le vrai tools/doctor.py (copie des outils dans un dépôt jetable créé par le test) est lancé par
`sys.executable -I --json` dans le dossier d'exécution jetable ; l'état est « vert » quand le crochet reference-transaction y est conforme, « rouge »
sinon. Aucun réseau, aucune base, aucun vrai dossier du lab : les sondes du doctor sont redirigées vers des ports fermés et un dossier personnel jetable."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import train_auto  # noqa: E402


def depot_jetable(base: Path, conforme: bool) -> Path:
    depot = base / "run"
    depot.mkdir()
    shutil.copytree(RACINE / "tools", depot / "tools", ignore=shutil.ignore_patterns("__pycache__"))
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "-C", str(depot), "init", "-q", "-b", "main"], check=True, env=env, capture_output=True)
    if conforme:
        (depot / ".git" / "hooks").mkdir(exist_ok=True)
        (depot / ".git" / "hooks" / "reference-transaction").symlink_to("../../tools/hooks/reference-transaction")
    return depot


def interpreteur_sans_pyyaml():
    """L'interpréteur de base de l'installation courante quand il n'importe pas yaml (celui du doctor lancé nu), sinon None."""
    base = getattr(sys, "_base_executable", None)
    if not base or not os.path.exists(base):
        return None
    essai = subprocess.run([base, "-I", "-c", "import yaml"], capture_output=True)
    return base if essai.returncode != 0 else None


class DoctorEtatReel(unittest.TestCase):
    def setUp(self):
        self.neuf()

    def neuf(self):
        """Un dossier temporaire neuf (créé par le test), pour chaque cas d'un test à plusieurs cas."""
        base = tempfile.TemporaryDirectory(prefix="doctor-etat.")
        self.addCleanup(base.cleanup)
        self.racine = Path(base.name)
        self.maison = self.racine / "maison"
        self.maison.mkdir()

    def doublures(self) -> Path:
        """R-20261110-43 : dossier de doublures, seul dans le PATH du doctor : colima et ci_local répondent sans rien lancer de réel, git est le vrai git."""
        dossier = self.racine / "bin"
        dossier.mkdir(exist_ok=True)
        git_reel = shutil.which("git")
        for nom, corps in (("colima", "exit 0\n"), ("ci_local", "exit 0\n"), ("git", f'exec "{git_reel}" "$@"\n')):
            (dossier / nom).write_text("#!/bin/sh\n" + corps, encoding="utf-8")
            (dossier / nom).chmod(0o755)
        return dossier

    def env(self, depot: Path, **supplement) -> dict:
        bin_ = self.doublures()
        env = {"PATH": str(bin_), "HOME": str(self.maison), "PMZILLA_LAB_DATA": str(self.maison / "d"), "PMZILLA_LAB_LOGS": str(self.maison / "l"),
               "PMZILLA_LAB_WORKSPACE": str(depot), "PMZILLA_LAB_DB_PORT": "1", "DOCTOR_OLLAMA_URL": "http://127.0.0.1:1",
               "DOCTOR_DISK_FREE_GB": "100", "DOCTOR_INTERPRETEUR_CROCHETS": "", "DOCTOR_CI_LOCAL": str(bin_ / "ci_local"),
               "DOCTOR_SANDBOX_FILE": str(self.racine / "absent" / "fichier-gere.json")}
        env.update(supplement)
        return env

    def etat(self, conforme: bool) -> str:
        depot = depot_jetable(self.racine, conforme)
        return train_auto.doctor_state(train_auto.Context(self.env(depot), depot, depot))

    def worktree_lie(self, conforme: bool) -> Path:
        """Le cas de production : le dossier d'exécution est un worktree lié, les crochets sont dans le dépôt commun."""
        depot = depot_jetable(self.racine, conforme)
        sous = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        for args in (["add", "-A", "-f"], ["commit", "-q", "-m", "initial"], ["worktree", "add", "-q", "--detach", str(self.racine / "lie"), "main"]):
            subprocess.run(["git", "-C", str(depot), *args], check=True, env=sous, capture_output=True)
        lie = self.racine / "lie"
        self.assertTrue((lie / ".git").is_file())
        return lie

    def test_vert_quand_le_crochet_est_conforme(self):
        self.assertEqual(self.etat(True), "vert")

    def test_rouge_sans_le_crochet(self):
        self.assertEqual(self.etat(False), "rouge")

    def test_worktree_lie_vert_et_rouge(self):
        for conforme, attendu in ((True, "vert"), (False, "rouge")):
            with self.subTest(conforme=conforme):
                self.neuf()
                lie = self.worktree_lie(conforme)
                self.assertEqual(train_auto.doctor_state(train_auto.Context(self.env(lie), lie, lie)), attendu)

    def test_sans_pyyaml_et_avec_un_path_restreint(self):
        """Le doctor lancé par l'interpréteur nu (sans yaml) rend tout de même l'état du crochet : le contrôle jira est « ignoré », pas le doctor."""
        base = interpreteur_sans_pyyaml()
        if base is None:
            self.skipTest("pas d'interpréteur de base sans pyyaml sur cette machine")
        for conforme, attendu in ((True, "vert"), (False, "rouge")):
            with self.subTest(conforme=conforme):
                self.neuf()
                depot = depot_jetable(self.racine, conforme)
                with mock.patch.object(train_auto.sys, "executable", base):
                    self.assertEqual(train_auto.doctor_state(train_auto.Context(self.env(depot), depot, depot)), attendu)

    def test_les_variables_du_depot_controle_ne_passent_pas_au_doctor(self):
        """Un DOCTOR_CROCHETS_DEPOT ou un GIT_DIR hérités, pointant vers un dépôt conforme, ne donnent pas de faux vert à un dossier d'exécution sans crochet."""
        conforme = self.racine / "conforme"
        conforme.mkdir()
        depot_conforme = depot_jetable(conforme, True)
        sans_crochet = self.racine / "sans"
        sans_crochet.mkdir()
        depot = depot_jetable(sans_crochet, False)
        for nom, valeur in (("DOCTOR_CROCHETS_DEPOT", str(depot_conforme)), ("GIT_DIR", str(depot_conforme / ".git")),
                            ("GIT_COMMON_DIR", str(depot_conforme / ".git")), ("GIT_WORK_TREE", str(depot_conforme))):
            with self.subTest(variable=nom):
                env = self.env(depot, **{nom: valeur})
                self.assertEqual(train_auto.doctor_state(train_auto.Context(env, depot, depot)), "rouge")

    def test_un_avertissement_sur_stderr_laisse_l_etat_vert(self):
        """R-20261110-43 : le JSON est lu sur stdout seul ; ce que le doctor écrit sur stderr ne le rend plus illisible (donc « absent »)."""
        depot = self.racine / "run"
        (depot / "tools").mkdir(parents=True)
        (depot / "tools" / "doctor.py").write_text(
            "import sys\n"
            "sys.stderr.write('Avertissement : quelque chose a ete signale\\n')\n"
            "print('{\"checks\": [{\"id\": \"crochet-reference-transaction\", \"level\": \"ok\"}]}')\n", encoding="utf-8")
        self.assertEqual(train_auto.doctor_state(train_auto.Context(self.env(depot), depot, depot)), "vert")


if __name__ == "__main__":
    unittest.main()
