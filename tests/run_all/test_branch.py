"""tests/run_all.sh --branch (change targeted-suites-admission, design D2, groupe 3.2) : le lancement de branche choisit les suites de toute la
différence avec origin/main, les lance sur le sommet propre et écrit l'empreinte de branche.

    python3 -m unittest discover -s tests/run_all -v

Vrais enfants : le lanceur, le vrai sélecteur (tools/select_suites.py, trouvé à côté du lanceur), Git et unittest sur un faux dépôt temporaire (RUN_ALL_ROOT).
Aucun faux : le risque que ce test ne couvre pas est le refus de session de --branch (code 6, R-20261102-40), couvert par SessionPreuveParLeConteneur dans test_run_all.py.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

RUN_ALL = Path(__file__).resolve().parents[1] / "run_all.sh"
SUITE_OK = "import unittest\nclass T(unittest.TestCase):\n    def test_a(self): pass\n    def test_b(self): pass\n"
SUITE_KO = "import unittest\nclass T(unittest.TestCase):\n    def test_casse(self): self.assertEqual(1, 2)\n"
SHELL_OK = 'echo "ok : un"\necho "1 réussis, 0 échec(s)"\n'


def scripts_shell():
    chemins = []
    for ligne in (RUN_ALL.parent / "suites_shell.txt").read_text(encoding="utf-8").splitlines():
        mots = ligne.split("#", 1)[0].split()
        if mots:
            chemins.append(mots[0])
    return chemins


class LancementDeBranche(unittest.TestCase):
    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)
        for nom in ("alpha", "beta", "identifiants_personnels", "secret_scan"):   # les deux dernières : toujours sélectionnées par le vrai sélecteur
            self.ecrire(f"tests/{nom}/test_{nom}.py", SUITE_OK)
        for chemin in scripts_shell():
            self.ecrire(chemin, SHELL_OK)
        self.git("init", "-q")
        self.git("symbolic-ref", "HEAD", "refs/heads/main")
        self.git("add", "-A")
        self.git("-c", "user.email=t@example.org", "-c", "user.name=test", "commit", "-q", "-m", "base")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("checkout", "-q", "-b", "feat/x")

    def git(self, *arguments):
        return subprocess.run(["git", *arguments], cwd=self.racine, capture_output=True, text=True, check=True).stdout.strip()

    def ecrire(self, relatif, texte):
        chemin = self.racine / relatif
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte)

    def valider(self, relatif, texte):
        self.ecrire(relatif, texte)
        self.git("add", "-A")
        self.git("-c", "user.email=t@example.org", "-c", "user.name=test", "commit", "-q", "-m", "change")

    def lancer(self, *arguments, **variables):
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS", "CLAUDECODE")}
        env.update({"RUN_ALL_ROOT": str(self.racine), "RUN_ALL_DEPS": ""}, **variables)
        return subprocess.run(["bash", str(getattr(self, "script", RUN_ALL)), *arguments], env=env, capture_output=True, text=True, timeout=120)

    def poser_selecteur(self, texte):
        """Le lanceur cherche le sélecteur à côté de lui : un exemplaire du lanceur et un faux sélecteur sont commités dans le faux dépôt (revue 2026-10-31)."""
        self.ecrire("tests/run_all.sh", RUN_ALL.read_text(encoding="utf-8"))
        self.ecrire("tests/suites_shell.txt", (RUN_ALL.parent / "suites_shell.txt").read_text(encoding="utf-8"))
        self.ecrire("tools/select_suites.py", texte)
        self.git("add", "-A")
        self.git("-c", "user.email=t@example.org", "-c", "user.name=test", "commit", "-q", "-m", "faux sélecteur")
        self.script = self.racine / "tests" / "run_all.sh"

    @property
    def branche(self):
        return self.racine / ".git" / "pmzilla-run-branch-ok"

    @property
    def complete(self):
        return self.racine / ".git" / "pmzilla-run-all-ok"

    @property
    def ciblee(self):
        return self.racine / ".git" / "pmzilla-run-targeted-ok"

    def test_vert_ecrit_l_empreinte_de_branche_seulement(self):
        self.valider("tests/alpha/test_alpha.py", SUITE_OK + "\n")
        self.complete.write_text("complete-ancienne\n")
        self.ciblee.write_text("ciblee-ancienne\n")
        resultat = self.lancer("--branch")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertRegex(resultat.stdout, r"alpha\s+2 tests · OK")
        self.assertNotRegex(resultat.stdout, r"beta\s+2 tests")                      # la suite non sélectionnée ne tourne pas
        arbre, suites = self.branche.read_text().rstrip("\n").split("\t")
        self.assertEqual(arbre, self.git("rev-parse", "HEAD^{tree}"))
        self.assertIn("alpha", suites.split(","))
        self.assertNotIn("beta", suites.split(","))
        n = int(re.search(r"run_all : empreinte de branche écrite \((\d+) suite\(s\)\)", resultat.stdout).group(1))
        self.assertEqual(n, len(suites.split(",")))
        self.assertGreater(resultat.stdout.index("run_all : empreinte de branche écrite"), resultat.stdout.index("TOTAL :"))
        self.assertEqual(self.complete.read_text(), "complete-ancienne\n")
        self.assertEqual(self.ciblee.read_text(), "ciblee-ancienne\n")

    def test_la_difference_entiere_compte_pas_seulement_le_dernier_commit(self):
        self.valider("tests/alpha/test_alpha.py", SUITE_OK + "\n")
        self.valider("tests/beta/test_beta.py", SUITE_OK + "\n")
        resultat = self.lancer("--branch")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertRegex(resultat.stdout, r"alpha\s+2 tests · OK")
        self.assertRegex(resultat.stdout, r"beta\s+2 tests · OK")

    def test_rouge_laisse_aucune_empreinte_de_branche_meme_une_ancienne(self):
        self.valider("tests/alpha/test_alpha.py", SUITE_OK + "\n")
        self.assertEqual(self.lancer("--branch").returncode, 0)
        self.assertTrue(self.branche.exists())
        self.valider("tests/alpha/test_alpha.py", SUITE_KO)
        resultat = self.lancer("--branch")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertFalse(self.branche.exists())
        self.assertNotIn("empreinte de branche écrite", resultat.stdout)

    def test_refus_sur_main_tete_detachee_et_worktree_sale(self):
        self.valider("tests/alpha/test_alpha.py", SUITE_OK + "\n")
        self.branche.write_text("ancienne\n")
        attendu = "run_all : --branch exige une branche de travail et un worktree propre"
        self.ecrire("fichier_sale.txt", "x\n")                                         # worktree pas propre
        resultat = self.lancer("--branch")
        self.assertEqual(resultat.returncode, 2, resultat.stdout)
        self.assertIn(attendu, resultat.stdout)
        os.unlink(self.racine / "fichier_sale.txt")
        self.git("checkout", "-q", "main")                                              # main
        resultat = self.lancer("--branch")
        self.assertEqual((resultat.returncode, attendu in resultat.stdout), (2, True), resultat.stdout)
        self.git("checkout", "-q", "--detach", "feat/x")                                # tête détachée
        resultat = self.lancer("--branch")
        self.assertEqual((resultat.returncode, attendu in resultat.stdout), (2, True), resultat.stdout)
        self.assertEqual(self.branche.read_text(), "ancienne\n")                       # aucune empreinte touchée
        self.assertNotRegex(resultat.stdout, r"\d+ tests")                             # aucune suite lancée

    def test_refus_des_combinaisons(self):
        self.valider("tests/alpha/test_alpha.py", SUITE_OK + "\n")
        for arguments, option in ((("--branch", "alpha"), "des noms de suites"), (("--branch", "--staged"), "--staged"),
                                  (("--branch", "--portable"), "--portable"), (("--mac", "--branch"), "--mac")):
            with self.subTest(arguments=arguments):
                resultat = self.lancer(*arguments)
                self.assertEqual(resultat.returncode, 2, resultat.stdout)
                self.assertIn(f"run_all : --branch ne se combine pas avec {option}", resultat.stdout)
                self.assertFalse(self.branche.exists())

    def test_refuse_pendant_une_fin_de_branche(self):
        self.valider("tests/alpha/test_alpha.py", SUITE_OK + "\n")
        self.branche.write_text("ancienne\n")
        verrou = self.racine / ".git" / "pmzilla-fin-en-cours"
        verrou.mkdir()
        (verrou / "pid").write_text(str(os.getpid()))                                    # un processus vivant : le gel est tenu
        (verrou / "branche").write_text("feat/autre\n")
        (verrou / "jeton").write_text("jeton-de-la-fin\n")
        resultat = self.lancer("--branch")
        self.assertEqual(resultat.returncode, 4, resultat.stdout)
        self.assertIn("fin de branche en cours", resultat.stdout)
        self.assertEqual(self.branche.read_text(), "ancienne\n")
        self.assertNotRegex(resultat.stdout, r"\d+ tests")

    def test_exigence_d_execution_complete_ecrit_l_empreinte_complete(self):
        self.valider("tools/orphelin.py", "pass\n")                                      # aucune suite ne nomme ce fichier : sélecteur en 3
        self.branche.write_text("ancienne\n")
        resultat = self.lancer("--branch")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("exécution complète requise : tools/orphelin.py", resultat.stdout)
        self.assertRegex(resultat.stdout, r"beta\s+2 tests · OK")                       # toutes les suites tournent
        self.assertEqual(self.complete.read_text().strip(), self.git("rev-parse", "HEAD^{tree}"))
        self.assertFalse(self.branche.exists())                                          # l'ancienne empreinte de branche est effacée
        self.assertNotIn("empreinte de branche écrite", resultat.stdout)

    # --- corrections de la revue du 2026-10-31 (tests neufs)
    def test_selecteur_en_echec_fait_un_lancement_complet_avec_empreinte_complete(self):
        self.poser_selecteur("import sys\nprint('panne simulee')\nsys.exit(2)\n")
        self.branche.write_text("ancienne\n")
        resultat = self.lancer("--branch")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("le sélecteur a échoué (code 2) : exécution complète", resultat.stdout)
        self.assertRegex(resultat.stdout, r"alpha\s+2 tests · OK")
        self.assertRegex(resultat.stdout, r"beta\s+2 tests · OK")
        self.assertEqual(self.complete.read_text().strip(), self.git("rev-parse", "HEAD^{tree}"))
        self.assertFalse(self.branche.exists())
        self.assertNotIn("empreinte de branche écrite", resultat.stdout)

    def test_un_nom_selectionne_qui_n_a_rien_lance_n_ecrit_aucune_empreinte_de_branche(self):
        # point 7 : le sélecteur nomme alpha et une suite inconnue ; une seule suite tourne, l'empreinte ne note donc rien de non lancé
        self.poser_selecteur("print('select_suites : alpha : test')\nprint('select_suites : fantome : test')\n")
        self.branche.write_text("ancienne\n")
        resultat = self.lancer("--branch")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertRegex(resultat.stdout, r"alpha\s+2 tests · OK")
        self.assertIn("run_all : empreinte de branche non écrite (suites lancées : 1, suites sélectionnées : 2)", resultat.stdout)
        self.assertFalse(self.branche.exists())                                          # effacée au départ, jamais réécrite

    # --- R-20261031-67 : l'empreinte de branche se décide sur les ensembles de noms, pas sur les comptes (tests neufs)
    def test_un_nom_de_selection_qui_lance_deux_suites_ecrit_l_empreinte_de_branche(self):
        # « branch_sync » est un dossier Python et une suite shell : un nom, deux suites lancées (3 suites pour 2 noms)
        self.ecrire("tests/branch_sync/test_branch_sync.py", SUITE_OK)
        self.poser_selecteur("print('select_suites : alpha : test')\nprint('select_suites : branch_sync : test')\n")
        self.branche.write_text("ancienne\n")
        resultat = self.lancer("--branch")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertRegex(resultat.stdout, r"TOTAL : \d+ tests dans 3 suites")
        self.assertNotIn("empreinte de branche non écrite", resultat.stdout)
        arbre, suites = self.branche.read_text().rstrip("\n").split("\t")
        self.assertEqual(arbre, self.git("rev-parse", "HEAD^{tree}"))
        self.assertEqual(suites.split(","), ["alpha", "branch_sync"])

    def test_un_nom_qui_lance_deux_suites_seul_compte_une_suite_en_plus_verte_et_l_empreinte_est_ecrite(self):
        self.ecrire("tests/branch_sync/test_branch_sync.py", SUITE_OK)
        self.poser_selecteur("print('select_suites : branch_sync : test')\n")
        resultat = self.lancer("--branch")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertRegex(resultat.stdout, r"TOTAL : \d+ tests dans 2 suites")
        self.assertIn("run_all : empreinte de branche écrite (1 suite(s))", resultat.stdout)
        self.assertEqual(self.branche.read_text().rstrip("\n").split("\t")[1], "branch_sync")

    def test_une_suite_selectionnee_non_lancee_est_nommee_et_refuse_l_empreinte_de_branche(self):
        self.ecrire("tests/branch_sync/test_branch_sync.py", SUITE_OK)
        self.poser_selecteur("print('select_suites : branch_sync : test')\nprint('select_suites : fantome : test')\nprint('select_suites : spectre : test')\n")
        self.branche.write_text("ancienne\n")
        resultat = self.lancer("--branch")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("run_all : empreinte de branche non écrite (suites lancées : 2, suites sélectionnées : 3) ; suites manquantes : fantome, spectre", resultat.stdout)
        self.assertFalse(self.branche.exists())

    def test_comptes_egaux_mais_une_suite_manquante_refuse_comme_avant(self):
        # branch_sync lance 2 suites (python + shell), fantome aucune : 2 lancées, 2 noms ; l'ancien contrôle par comptes aurait écrit l'empreinte
        self.ecrire("tests/branch_sync/test_branch_sync.py", SUITE_OK)
        self.poser_selecteur("print('select_suites : branch_sync : test')\nprint('select_suites : fantome : test')\n")
        resultat = self.lancer("--branch")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("run_all : empreinte de branche non écrite (suites lancées : 2, suites sélectionnées : 2) ; suites manquantes : fantome", resultat.stdout)
        self.assertFalse(self.branche.exists())

    def test_une_suite_en_plus_rouge_laisse_le_runner_rouge_sans_empreinte(self):
        self.ecrire("tests/branch_sync/test_branch_sync.py", SUITE_OK)
        self.ecrire("tests/branch_sync/test_branch_sync.sh", 'echo "ko : un"\necho "0 réussis, 1 échec(s)"\nexit 1\n')
        self.poser_selecteur("print('select_suites : branch_sync : test')\n")
        self.branche.write_text("ancienne\n")
        resultat = self.lancer("--branch")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertNotIn("empreinte de branche écrite", resultat.stdout)
        self.assertFalse(self.branche.exists())

    def test_une_selection_vide_n_ecrit_aucune_empreinte_de_branche(self):
        self.poser_selecteur("print('rien a selectionner')\n")
        self.branche.write_text("ancienne\n")
        resultat = self.lancer("--branch")
        self.assertNotIn("empreinte de branche écrite", resultat.stdout)
        self.assertFalse(self.branche.exists())

    def test_un_worktree_sali_pendant_les_suites_n_ecrit_aucune_empreinte_de_branche(self):
        # point 8 : une suite crée un fichier non suivi dans le worktree ; l'arbre du sommet est le même mais le worktree n'est plus propre
        self.valider("tests/alpha/test_alpha.py", SUITE_OK + f"\nopen({str(self.racine / 'sali.txt')!r}, 'w').write('x')\n")
        resultat = self.lancer("--branch")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("run_all : empreinte de branche non écrite (l'arbre du sommet a changé ou le worktree n'est plus propre)", resultat.stdout)
        self.assertFalse(self.branche.exists())

    def test_le_lancement_complet_et_le_ciblé_n_ecrivent_pas_l_empreinte_de_branche(self):
        self.assertEqual(self.lancer().returncode, 0)
        self.assertTrue(self.complete.exists())
        self.assertFalse(self.branche.exists())


if __name__ == "__main__":
    unittest.main()
