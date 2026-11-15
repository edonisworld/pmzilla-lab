"""tools/select_suites.py --range <base>...<sommet> (change targeted-suites-admission, design D3, groupe 3.1) : mêmes règles que le mode de l'index,
appliquées aux chemins d'une plage ; un dépôt temporaire, de vrais enfants (le sélecteur et Git), aucun faux.

    python3 -m unittest discover -s tests/select_suites -v
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SELECTEUR = Path(__file__).resolve().parents[2] / "tools" / "select_suites.py"
GARDES = {"identifiants_personnels", "secret_scan"}


class SelecteurPlage(unittest.TestCase):
    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.org")
        self.git("config", "user.name", "test")
        self.ecrire("tests/run_all.sh", "#!/bin/bash\n: lanceur factice\n")
        self.ecrire("tests/suites_shell.txt", "# aucune suite shell\n")
        self.ecrire("tests/alpha/test_alpha.py", "import outil_a\n")   # nomme tools/outil_a.py
        self.ecrire("tests/identifiants_personnels/test_id.py", "pass\n")
        self.ecrire("tests/secret_scan/test_secrets.py", "pass\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")   # la base de la plage, comme origin/main d'une branche de travail

    def git(self, *arguments):
        return subprocess.run(["git", *arguments], cwd=self.racine, capture_output=True, text=True, check=True).stdout

    def ecrire(self, relatif, texte="x\n"):
        chemin = self.racine / relatif
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte)

    def valider(self, *relatifs):
        for relatif in relatifs:
            self.ecrire(relatif, "y\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "change")

    def lancer(self, *arguments):
        r = subprocess.run([sys.executable, str(SELECTEUR), "--root", str(self.racine), *arguments], capture_output=True, text=True)
        return r.returncode, r.stdout, r.stderr

    def test_meme_selection_que_le_mode_de_l_index_pour_les_memes_chemins(self):
        self.valider("tools/outil_a.py")
        code, sortie, _ = self.lancer("--range", "origin/main...HEAD")
        self.assertEqual(code, 0, sortie)
        self.assertEqual({ligne.split(" : ")[1] for ligne in sortie.splitlines()}, {"alpha", *GARDES})
        self.git("reset", "-q", "--soft", "origin/main")   # les mêmes chemins, maintenant dans l'index
        code_index, sortie_index, _ = self.lancer()
        self.assertEqual((code_index, sortie_index), (code, sortie))

    def test_chemin_garde_donne_3_et_le_nomme(self):
        self.valider("tools/hooks/pre-commit")
        code, sortie, _ = self.lancer("--range", "origin/main...HEAD")
        self.assertEqual(code, 3, sortie)
        self.assertIn("tools/hooks/pre-commit", sortie)

    def test_chemin_qu_aucune_suite_ne_nomme_donne_3(self):
        self.valider("tools/inconnu.py")
        self.assertEqual(self.lancer("--range", "origin/main...HEAD")[0], 3)

    def test_plage_illisible_donne_2(self):
        code, sortie, erreur = self.lancer("--range", "origin/inexistante...HEAD")
        self.assertEqual(code, 2, sortie)
        self.assertIn("select_suites :", erreur)

    def test_plage_mal_formee_ou_absente_donne_2(self):
        self.assertEqual(self.lancer("--range", "origin/main")[0], 2)
        self.assertEqual(self.lancer("--range")[0], 2)
        self.assertEqual(self.lancer("--range", "--cached...HEAD")[0], 2)

    def test_ne_lit_pas_l_index(self):
        self.valider("tools/outil_a.py")
        self.ecrire("tools/inconnu.py")
        self.git("add", "-A")   # un chemin indexé que la plage ne contient pas
        code, sortie, _ = self.lancer("--range", "origin/main...HEAD")
        self.assertEqual(code, 0, sortie)

    def test_ne_se_combine_pas_avec_les_lecteurs_d_openspec(self):
        self.assertEqual(self.lancer("--range", "origin/main...HEAD", "--openspec-readers")[0], 2)

    def test_n_ecrit_rien(self):
        self.valider("tools/outil_a.py")
        avant = self.git("status", "--porcelain")
        self.lancer("--range", "origin/main...HEAD")
        self.assertEqual(self.git("status", "--porcelain"), avant)


if __name__ == "__main__":
    unittest.main()
