"""tools/select_suites.py : sélection des suites d'après l'index Git, sur un dépôt temporaire. Aucun test réel n'est lancé.

    python3 -m unittest discover -s tests/select_suites -v
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SELECTEUR = Path(__file__).resolve().parents[2] / "tools" / "select_suites.py"
LANCEUR = ('for test in tests/hooks/test_pre_commit.sh:hooks:sh tests/finish_branch/test_finish_branch.sh:finish_branch:bash; do\n'
           '  :\ndone\n')


class Selecteur(unittest.TestCase):
    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.org")
        self.git("config", "user.name", "test")
        self.ecrire("tests/run_all.sh", LANCEUR)
        self.ecrire("tests/alpha/test_alpha.py", "import outil_a\n")                       # nomme tools/outil_a.py
        self.ecrire("tests/beta/test_beta.py", "CHEMIN = 'tools/sous/outil_b.py'\n")      # nomme un chemin
        self.ecrire("tests/identifiants_personnels/test_id.py", "pass\n")
        self.ecrire("tests/hooks/test_pre_commit.sh", "echo hooks\n")
        self.ecrire("tests/finish_branch/test_finish_branch.sh", "echo finish\n")
        self.ecrire("tests/gamma/test_gamma.py", "DONNEES = 'cas.yaml'\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")

    def git(self, *arguments):
        return subprocess.run(["git", *arguments], cwd=self.racine, capture_output=True, text=True, check=True).stdout

    def ecrire(self, relatif, texte="x\n"):
        chemin = self.racine / relatif
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte)

    def indexer(self, *relatifs, texte="y\n"):
        for relatif in relatifs:
            self.ecrire(relatif, texte)
        self.git("add", "-A")

    def selection(self):
        resultat = subprocess.run([sys.executable, str(SELECTEUR), "--root", str(self.racine)], capture_output=True, text=True)
        return resultat.returncode, resultat.stdout

    def suites(self):
        code, sortie = self.selection()
        self.assertEqual(code, 0, sortie)
        return {ligne.split(" : ")[1] for ligne in sortie.splitlines()}

    def test_outil_nomme_par_une_suite(self):
        self.indexer("tools/outil_a.py")
        self.assertEqual(self.suites(), {"alpha", "identifiants_personnels"})

    def test_chaque_ligne_donne_la_raison(self):
        self.indexer("tools/outil_a.py")
        code, sortie = self.selection()
        self.assertIn("select_suites : alpha : tools/outil_a.py (« outil_a » nommé par ses tests)", sortie)
        self.assertIn("select_suites : identifiants_personnels : toujours sélectionnée", sortie)

    def test_chemin_complet_nomme(self):
        self.indexer("tools/sous/outil_b.py")
        self.assertEqual(self.suites(), {"beta", "identifiants_personnels"})

    def test_fichier_de_donnees_nomme_par_son_nom(self):
        self.indexer("tests/postures/cas.yaml")
        self.assertEqual(self.suites(), {"gamma", "identifiants_personnels"})

    def test_chemin_dans_une_suite(self):
        self.indexer("tests/alpha/test_alpha.py")
        self.assertEqual(self.suites(), {"alpha", "identifiants_personnels"})

    def test_script_de_test_shell_liste(self):
        self.indexer("tests/hooks/test_pre_commit.sh")
        self.assertEqual(self.suites(), {"hooks", "identifiants_personnels"})

    def test_documentation_seule_ne_selectionne_que_les_gardes(self):
        self.indexer("docs/pmzilla/x.md", "openspec/changes/c/tasks.md", "CHANGELOG.md", "README.md", "_bmad-output/pmzilla/a.md")
        self.assertEqual(self.suites(), {"identifiants_personnels"})

    def test_fichier_de_code_inconnu_exige_l_execution_complete(self):
        self.indexer("tools/orphelin.py")
        code, sortie = self.selection()
        self.assertEqual(code, 3)
        self.assertIn("select_suites : exécution complète requise : tools/orphelin.py", sortie)

    def test_fichiers_sensibles_exigent_l_execution_complete(self):
        for chemin in ("CLAUDE.md", ".claude/settings.json", "tests/run_all.sh", "tools/hooks/pre-commit", "tools/hooks/pre-push",
                       "tools/select_suites.py"):
            with self.subTest(chemin=chemin):
                self.git("reset", "-q")
                self.indexer(chemin, texte="z\n")
                code, sortie = self.selection()
                self.assertEqual(code, 3, sortie)
                self.assertIn(chemin, sortie)

    def test_fichier_supprime(self):
        self.indexer("tests/alpha/test_alpha_bis.py", texte="pass\n")
        self.git("commit", "-q", "-m", "bis")
        self.git("rm", "-q", "tests/alpha/test_alpha_bis.py")
        self.assertEqual(self.suites(), {"alpha", "identifiants_personnels"})

    def test_suppression_du_dernier_test_d_une_suite_exige_l_execution_complete(self):
        self.git("rm", "-q", "tests/alpha/test_alpha.py")
        self.assertEqual(self.selection()[0], 3)

    def test_fichier_supprime_inconnu_exige_l_execution_complete(self):
        self.indexer("tools/ancien.py")
        self.git("commit", "-q", "-m", "ajout")
        self.git("rm", "-q", "tools/ancien.py")
        self.assertEqual(self.selection()[0], 3)

    def test_fichier_renomme_compte_les_deux_chemins(self):
        self.indexer("tools/outil_a.py")
        self.git("commit", "-q", "-m", "ajout")
        self.git("mv", "tools/outil_a.py", "tools/orphelin.py")
        code, sortie = self.selection()
        self.assertEqual(code, 3)
        self.assertIn("tools/orphelin.py", sortie)

    def test_un_chemin_inconnu_l_emporte_sur_les_autres(self):
        self.indexer("tools/outil_a.py", "tools/orphelin.py")
        code, sortie = self.selection()
        self.assertEqual(code, 3)
        self.assertNotIn("alpha", sortie)

    def test_index_vide_ne_selectionne_que_les_gardes(self):
        self.assertEqual(self.suites(), {"identifiants_personnels"})

    def test_aucun_fichier_ecrit(self):
        self.indexer("tools/outil_a.py")
        avant = sorted(str(p.relative_to(self.racine)) for p in self.racine.rglob("*") if ".git" not in p.parts)
        etat = self.git("status", "--porcelain")
        self.selection()
        apres = sorted(str(p.relative_to(self.racine)) for p in self.racine.rglob("*") if ".git" not in p.parts)
        self.assertEqual(avant, apres)
        self.assertEqual(etat, self.git("status", "--porcelain"))

    def test_hors_depot_git_code_2(self):
        vide = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, vide, True)
        resultat = subprocess.run([sys.executable, str(SELECTEUR), "--root", str(vide)], capture_output=True, text=True)
        self.assertEqual(resultat.returncode, 2)
        self.assertIn("select_suites : pas un dépôt Git", resultat.stderr)

    def test_usage(self):
        resultat = subprocess.run([sys.executable, str(SELECTEUR), "--inconnue"], capture_output=True, text=True)
        self.assertEqual(resultat.returncode, 2)
        self.assertIn("select_suites : usage", resultat.stderr)


if __name__ == "__main__":
    unittest.main()
