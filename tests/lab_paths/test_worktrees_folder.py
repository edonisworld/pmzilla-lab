"""
Le dossier des worktrees dans les modules partagés des chemins du lab (lab-folder-layout, design D1, tâche 4.2) :
tools/lab_paths.py et tools/lab_paths.sh.

    bash tests/run_all.sh lab_paths

Même règle dans les deux langages (PMZILLA_LAB_WORKTREES si posée et non vide, tilde développé, sinon `worktrees` du dossier du lab),
dernière ligne imprimée `worktrees_folder=<chemin>` (huitième : `context_folder` reste septième), jamais créé, listé ni ouvert, et la
fonction shell `lab_paths_worktrees_folder <racine de contenu>` qui répond pour une racine donnée sans interroger Git.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_lab_paths import SHELLS, Lab, lire, reel  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]
OUTILS = RACINE / "tools"
sys.path.insert(0, str(OUTILS))
import lab_paths  # noqa: E402


class TestDossierDesWorktrees(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.lab = Lab(Path(cls._tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_defaut_sous_le_dossier_du_lab_dans_les_deux_langages(self):
        attendu = os.path.join(reel(self.lab.lab), "worktrees")
        py = self.lab.python(self.lab.principal)
        self.assertEqual(py.returncode, 0, py.stderr)
        self.assertEqual(reel(lire(py.stdout)["worktrees_folder"]), attendu)
        for interprete in SHELLS:
            with self.subTest(interprete):
                sh = self.lab.shell(interprete, self.lab.principal)
                self.assertEqual(sh.returncode, 0, sh.stderr)
                self.assertEqual(lire(sh.stdout), lire(py.stdout))

    def test_derniere_ligne_imprimee_et_contexte_septieme(self):
        py = self.lab.python(self.lab.principal)
        lignes = py.stdout.strip().splitlines()
        self.assertEqual(len(lignes), 8)
        self.assertTrue(lignes[-1].startswith("worktrees_folder="))
        self.assertTrue(lignes[6].startswith("context_folder="))
        for interprete in SHELLS:
            sh = self.lab.shell(interprete, self.lab.principal)
            sortie = sh.stdout.strip().splitlines()
            self.assertEqual(len(sortie), 8)
            self.assertTrue(sortie[-1].startswith("worktrees_folder="))
            self.assertTrue(sortie[6].startswith("context_folder="))

    def test_variable_avec_tilde_developpe_dossier_absent_accepte(self):
        extra = {"PMZILLA_LAB_WORKTREES": "~/ailleurs/arbres", "PMZILLA_LAB_WORKSPACE": str(self.lab.principal)}
        attendu = str(self.lab.home / "ailleurs" / "arbres")
        py = self.lab.python(self.lab.copie, **extra)
        self.assertEqual(py.returncode, 0, py.stderr)
        self.assertEqual(lire(py.stdout)["worktrees_folder"], attendu)
        for interprete in SHELLS:
            with self.subTest(interprete):
                sh = self.lab.shell(interprete, self.lab.copie, **extra)
                self.assertEqual(sh.returncode, 0, sh.stderr)
                self.assertEqual(lire(sh.stdout)["worktrees_folder"], attendu)
        self.assertFalse((self.lab.home / "ailleurs").exists())

    def test_variable_vide_vaut_non_posee(self):
        py = self.lab.python(self.lab.principal, PMZILLA_LAB_WORKTREES="")
        self.assertEqual(reel(lire(py.stdout)["worktrees_folder"]), os.path.join(reel(self.lab.lab), "worktrees"))
        for interprete in SHELLS:
            sh = self.lab.shell(interprete, self.lab.principal, PMZILLA_LAB_WORKTREES="")
            self.assertEqual(lire(sh.stdout), lire(py.stdout))

    def test_variable_shell_exportee(self):
        commande = f'. "{self.lab.principal}/tools/lab_paths.sh" && lab_paths_init && printenv LAB_WORKTREES_FOLDER'
        for interprete in SHELLS:
            r = subprocess.run([interprete, "-c", commande], capture_output=True, text=True, env=self.lab.env(), cwd=str(self.lab.tmp))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(reel(r.stdout.strip()), os.path.join(reel(self.lab.lab), "worktrees"))

    def test_dossier_absent_n_est_pas_une_erreur_et_n_est_pas_cree(self):
        extra = {"PMZILLA_LAB_WORKTREES": str(self.lab.tmp / "arbres-jamais-crees")}
        py = self.lab.python(self.lab.principal, **extra)
        self.assertEqual(py.returncode, 0, py.stderr)
        for interprete in SHELLS:
            self.assertEqual(self.lab.shell(interprete, self.lab.principal, **extra).returncode, 0)
        self.assertFalse((self.lab.tmp / "arbres-jamais-crees").exists())
        # le défaut non plus : le dossier du faux lab n'a pas de dossier `worktrees`
        self.lab.python(self.lab.principal)
        self.assertFalse((self.lab.lab / "worktrees").exists())

    def test_fonction_python(self):
        contenu = Path("/x/lab/workspace")
        self.assertEqual(lab_paths.worktrees_folder(contenu, {}), Path("/x/lab/worktrees"))
        self.assertEqual(lab_paths.worktrees_folder(contenu, {lab_paths.VAR_WORKTREES: "/a/b"}), Path("/a/b"))
        self.assertEqual(lab_paths.worktrees_folder(contenu, {lab_paths.VAR_WORKTREES: ""}), Path("/x/lab/worktrees"))
        self.assertEqual(lab_paths.VAR_WORKTREES, "PMZILLA_LAB_WORKTREES")

    def test_cle_de_resolve(self):
        cles = list(lab_paths.resolve({"PMZILLA_LAB_WORKSPACE": str(self.lab.principal)}, OUTILS / "lab_paths.py"))
        self.assertEqual(cles[-1], "worktrees_folder")

    def test_fonction_shell_pour_une_racine_donnee_sans_git(self):
        # une racine de contenu qui n'est pas un dépôt Git (ni même un dossier existant) : la fonction répond, sans lancer Git
        hors_git = self.lab.tmp / "hors-git" / "espace"
        hors_git.mkdir(parents=True, exist_ok=True)
        script = self.lab.copie / "tools" / "lab_paths.sh"        # la copie hors Git du faux lab
        for interprete in SHELLS:
            with self.subTest(interprete):
                commande = f'. "{script}" && lab_paths_worktrees_folder "{hors_git}"'
                r = subprocess.run([interprete, "-c", commande], capture_output=True, text=True, env=self.lab.env(), cwd=str(self.lab.tmp))
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(r.stdout.strip(), str(hors_git.parent / "worktrees"))
        extra = {"PMZILLA_LAB_WORKTREES": "~/arbres"}
        for interprete in SHELLS:
            commande = f'. "{script}" && lab_paths_worktrees_folder "{hors_git}"'
            r = subprocess.run([interprete, "-c", commande], capture_output=True, text=True, env=self.lab.env(**extra), cwd=str(self.lab.tmp))
            self.assertEqual(r.stdout.strip(), str(self.lab.home / "arbres"))


if __name__ == "__main__":
    unittest.main()
