"""
Tests du lanceur tests/run_all.sh sur un faux dépôt : suites qui réussissent, suite qui échoue, filtre par nom,
tests shell, aucune suite.

    python3 -m unittest discover -s tests/run_all -v

Le lanceur est pointé sur un dossier temporaire (RUN_ALL_ROOT) et sans dépendances supplémentaires (RUN_ALL_DEPS
vide) ; il ne lance jamais les vraies suites.
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
SUITE_KO = ("import unittest\nclass T(unittest.TestCase):\n    def test_a(self): pass\n"
            "    def test_casse(self): self.assertEqual(1, 2)\n")
SHELL_OK = 'echo "ok : un"\necho "ok : deux"\necho "2 réussis, 0 échec(s)"\n'
SHELL_KO = 'echo "ECHEC : un"\necho "1 réussis, 1 échec(s)"\nexit 1\n'


class Lanceur(unittest.TestCase):
    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)

    def suite(self, nom: str, texte: str) -> None:
        dossier = self.racine / "tests" / nom
        dossier.mkdir(parents=True)
        (dossier / f"test_{nom}.py").write_text(texte)

    def shell(self, relatif: str, texte: str) -> None:
        chemin = self.racine / "tests" / relatif
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte)

    def tous_les_shells(self, sauf=()):
        """Crée, avec un contenu qui réussit, tous les scripts shell que le lanceur liste (sauf ceux dits)."""
        listes = re.findall(r"(tests/\S+\.sh):", RUN_ALL.read_text(encoding="utf-8"))
        for chemin in listes:
            if chemin not in sauf:
                self.shell(chemin[len("tests/"):], SHELL_OK)
        return listes

    def lancer(self, *arguments, **variables):
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS")}
        env.update({"RUN_ALL_ROOT": str(self.racine), "RUN_ALL_DEPS": ""}, **variables)
        return subprocess.run(["bash", str(RUN_ALL), *arguments], env=env, capture_output=True, text=True, timeout=120)

    def test_tout_reussit_total_et_code_zero(self):
        self.suite("alpha", SUITE_OK)
        self.suite("beta", SUITE_OK)
        listes = self.tous_les_shells()
        resultat = self.lancer()
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("alpha", resultat.stdout)
        self.assertRegex(resultat.stdout, r"alpha\s+2 tests · OK")
        self.assertRegex(resultat.stdout, r"hooks \(shell\)\s+2 tests · OK")
        self.assertIn(f"TOTAL : {4 + 2 * len(listes)} tests dans {2 + len(listes)} suites · tous réussis", resultat.stdout)

    def test_entrees_du_juge_changees_affichees_clairement_en_tete(self):
        self.suite("alpha", SUITE_OK)
        resultat = self.lancer("alpha", PMZILLA_ENTREES_JUGE_CHANGEES="1")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        premieres = resultat.stdout.splitlines()[:2]
        self.assertIn("ATTENTION : PMZILLA_ENTREES_JUGE_CHANGEES=1", premieres[0])
        self.assertIn("IGNORÉ", premieres[0])
        self.assertIn("Entrées du juge modifiées", premieres[1])           # ce que le message du commit doit dire
        self.assertIn("TOTAL : 2 tests dans 1 suites · tous réussis", resultat.stdout)

    def test_sans_la_variable_aucun_avertissement(self):
        self.suite("alpha", SUITE_OK)
        resultat = self.lancer("alpha")
        self.assertNotIn("PMZILLA_ENTREES_JUGE_CHANGEES", resultat.stdout)
        resultat = self.lancer("alpha", PMZILLA_ENTREES_JUGE_CHANGEES="0")
        self.assertNotIn("ATTENTION", resultat.stdout)

    def test_une_suite_en_echec_code_non_nul_et_diagnostic(self):
        self.suite("alpha", SUITE_OK)
        self.suite("casse", SUITE_KO)
        resultat = self.lancer("alpha", "casse")
        self.assertEqual(resultat.returncode, 1)
        self.assertRegex(resultat.stdout, r"casse\s+2 tests · ÉCHEC")
        self.assertIn("AssertionError", resultat.stdout)          # la fin de la sortie de la suite est affichée
        self.assertIn("TOTAL : 4 tests dans 2 suites · 1 suite(s) en échec : casse", resultat.stdout)
        self.assertRegex(resultat.stdout, r"alpha\s+2 tests · OK")   # les suites réussies sont quand même listées

    def test_un_test_shell_en_echec(self):
        self.suite("alpha", SUITE_OK)
        self.shell("installation/test_install_links.sh", SHELL_KO)
        resultat = self.lancer("alpha", "installation")
        self.assertEqual(resultat.returncode, 1)
        self.assertRegex(resultat.stdout, r"installation \(shell\)\s+2 tests · ÉCHEC")
        self.assertIn("en échec : installation", resultat.stdout)

    def test_filtre_par_nom(self):
        self.suite("alpha", SUITE_OK)
        self.suite("casse", SUITE_KO)
        resultat = self.lancer("alpha")
        self.assertEqual(resultat.returncode, 0)
        self.assertIn("TOTAL : 2 tests dans 1 suites · tous réussis", resultat.stdout)
        self.assertNotIn("casse", resultat.stdout)

    def test_nom_inconnu_ou_depot_sans_suite(self):
        self.suite("alpha", SUITE_OK)
        resultat = self.lancer("inconnue")
        self.assertEqual(resultat.returncode, 2)
        self.assertIn("Aucune suite trouvée", resultat.stdout)
        vide = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, vide, True)
        (vide / "tests").mkdir()
        self.racine = vide
        self.assertEqual(self.lancer("inconnue").returncode, 2)

    def test_suite_qui_ne_se_lance_pas_est_un_echec(self):
        self.suite("cassee", "import module_qui_n_existe_pas\n")
        resultat = self.lancer("cassee")
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("ÉCHEC", resultat.stdout)

    def test_bavard_affiche_la_sortie_complete(self):
        self.suite("alpha", SUITE_OK)
        self.assertIn("Ran 2 tests", self.lancer("-v").stdout)
        self.assertNotIn("Ran 2 tests", self.lancer().stdout)

    def test_suite_shell_listee_mais_absente_est_un_echec_nomme(self):
        self.suite("alpha", SUITE_OK)
        self.tous_les_shells(sauf=("tests/hooks/test_pre_commit.sh",))   # listé mais absent
        resultat = self.lancer()
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertIn("test_pre_commit.sh", resultat.stdout)
        self.assertRegex(resultat.stdout, r"1 suite\(s\) en échec : .*hooks")

    def test_suite_shell_absente_sans_effet_si_le_filtre_vise_une_autre_suite(self):
        self.suite("alpha", SUITE_OK)
        resultat = self.lancer("alpha")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("TOTAL : 2 tests dans 1 suites", resultat.stdout)

    def test_filtre_sur_une_suite_shell_absente_ne_cache_pas_l_echec(self):
        self.suite("alpha", SUITE_OK)
        resultat = self.lancer("hooks")   # seul « hooks » est demandé : son script est absent
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertIn("test_pre_commit.sh", resultat.stdout)


class EmpreinteDeCommit(unittest.TestCase):
    """PMZILLA_NO_EVALS fait refuser le lancement ; un lancement complet et vert écrit l'empreinte de l'index."""

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)
        dossier = self.racine / "tests" / "alpha"
        dossier.mkdir(parents=True)
        (dossier / "test_alpha.py").write_text(SUITE_OK)
        for chemin in re.findall(r"(tests/\S+\.sh):", RUN_ALL.read_text(encoding="utf-8")):
            cible = self.racine / chemin
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_text(SHELL_OK)
        self.git("init", "-q")
        self.git("add", "-A")

    def git(self, *arguments):
        return subprocess.run(["git", *arguments], cwd=self.racine, capture_output=True, text=True, check=True).stdout.strip()

    def lancer(self, *arguments, **variables):
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS")}
        env.update({"RUN_ALL_ROOT": str(self.racine), "RUN_ALL_DEPS": ""}, **variables)
        return subprocess.run(["bash", str(RUN_ALL), *arguments], env=env, capture_output=True, text=True, timeout=120)

    @property
    def empreinte(self):
        return self.racine / ".git" / "pmzilla-run-all-ok"

    def test_variable_definie_refus_sans_rien_lancer(self):
        resultat = self.lancer(PMZILLA_NO_EVALS="1")
        self.assertEqual(resultat.returncode, 2, resultat.stdout)
        self.assertIn("réservée à git commit", resultat.stdout)
        self.assertNotIn("TOTAL", resultat.stdout)
        self.assertFalse(self.empreinte.exists())

    def test_variable_definie_mais_vide_refusee_aussi(self):
        self.assertEqual(self.lancer(PMZILLA_NO_EVALS="").returncode, 2)

    def test_lancement_complet_vert_ecrit_l_empreinte_de_l_index(self):
        resultat = self.lancer()
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertEqual(self.empreinte.read_text().strip(), self.git("write-tree"))

    def test_lancement_en_echec_n_ecrit_rien_et_efface_l_ancienne_empreinte(self):
        self.assertEqual(self.lancer().returncode, 0)
        (self.racine / "tests" / "casse").mkdir()
        (self.racine / "tests" / "casse" / "test_casse.py").write_text(SUITE_KO)
        self.assertEqual(self.lancer().returncode, 1)
        self.assertFalse(self.empreinte.exists())

    def test_lancement_filtre_n_ecrit_rien(self):
        self.assertEqual(self.lancer("alpha").returncode, 0)
        self.assertFalse(self.empreinte.exists())

    def test_hors_depot_git_le_lancement_reussit_sans_empreinte(self):
        shutil.rmtree(self.racine / ".git")
        env_racine = self.lancer()
        self.assertEqual(env_racine.returncode, 0, env_racine.stdout)


class LancementCible(unittest.TestCase):
    """--staged : le sélecteur choisit les suites d'après l'index ; empreinte ciblée séparée de l'empreinte complète."""

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)
        for nom in ("alpha", "beta"):
            dossier = self.racine / "tests" / nom
            dossier.mkdir(parents=True)
            (dossier / f"test_{nom}.py").write_text(SUITE_OK)
        for chemin in re.findall(r"(tests/\S+\.sh):", RUN_ALL.read_text(encoding="utf-8")):
            cible = self.racine / chemin
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_text(SHELL_OK)
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("-c", "user.email=t@example.org", "-c", "user.name=test", "commit", "-q", "-m", "base")

    def git(self, *arguments):
        return subprocess.run(["git", *arguments], cwd=self.racine, capture_output=True, text=True, check=True).stdout.strip()

    def lancer(self, *arguments):
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS")}
        env.update({"RUN_ALL_ROOT": str(self.racine), "RUN_ALL_DEPS": ""})
        return subprocess.run(["bash", str(RUN_ALL), *arguments], env=env, capture_output=True, text=True, timeout=120)

    def indexer(self, relatif, texte):
        chemin = self.racine / relatif
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte)
        self.git("add", "-A")

    @property
    def complete(self):
        return self.racine / ".git" / "pmzilla-run-all-ok"

    @property
    def ciblee(self):
        return self.racine / ".git" / "pmzilla-run-targeted-ok"

    def test_lancement_cible_vert_ecrit_l_empreinte_ciblee_seulement(self):
        self.indexer("tests/alpha/test_alpha.py", SUITE_OK + "\n")
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("select_suites : alpha", resultat.stdout)
        self.assertRegex(resultat.stdout, r"alpha\s+2 tests · OK")
        self.assertNotRegex(resultat.stdout, r"beta\s+2 tests")                 # la suite non sélectionnée ne tourne pas
        self.assertEqual(self.ciblee.read_text().strip(), self.git("write-tree"))
        self.assertFalse(self.complete.exists())

    def test_lancement_cible_en_echec_efface_l_empreinte_ciblee_et_sort_en_1(self):
        self.indexer("tests/alpha/test_alpha.py", SUITE_OK + "\n")
        self.assertEqual(self.lancer("--staged").returncode, 0)
        self.assertTrue(self.ciblee.exists())
        self.indexer("tests/alpha/test_alpha.py", SUITE_KO)
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertFalse(self.ciblee.exists())

    def test_lancement_cible_ne_touche_pas_l_empreinte_complete(self):
        self.assertEqual(self.lancer().returncode, 0)
        ancienne = self.complete.read_text()
        self.indexer("tests/alpha/test_alpha.py", SUITE_OK + "\n")
        self.assertEqual(self.lancer("--staged").returncode, 0)
        self.assertEqual(self.complete.read_text(), ancienne)

    def test_fichier_inconnu_fait_passer_en_execution_complete(self):
        self.indexer("tools/orphelin.py", "pass\n")
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("exécution complète requise : tools/orphelin.py", resultat.stdout)
        self.assertRegex(resultat.stdout, r"beta\s+2 tests · OK")                 # toutes les suites tournent
        self.assertEqual(self.complete.read_text().strip(), self.git("write-tree"))
        self.assertFalse(self.ciblee.exists())

    def test_lancement_filtre_n_ecrit_ni_n_efface_rien(self):
        self.ciblee.write_text("ancienne\n")
        self.complete.write_text("autre\n")
        self.assertEqual(self.lancer("alpha").returncode, 0)
        self.assertEqual(self.ciblee.read_text(), "ancienne\n")
        self.assertEqual(self.complete.read_text(), "autre\n")

    def test_option_combinee_avec_des_noms_est_refusee(self):
        resultat = self.lancer("--staged", "alpha")
        self.assertEqual(resultat.returncode, 2)
        self.assertIn("ne se combine pas", resultat.stdout)

    def test_selecteur_en_echec_fait_un_passage_complet_avec_empreinte_complete(self):
        # Le lanceur cherche le sélecteur à côté de lui (tools/select_suites.py relatif au script) : on en copie un exemplaire
        # dans le faux dépôt, avec un faux sélecteur qui échoue (code 5, ni 0 ni 3).
        shutil.copy(RUN_ALL, self.racine / "tests" / "run_all.sh")
        (self.racine / "tools").mkdir(exist_ok=True)
        (self.racine / "tools" / "select_suites.py").write_text("import sys\nprint('panne simulee')\nsys.exit(5)\n")
        self.git("add", "-A")
        self.ciblee.write_text("ancienne\n")
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS")}
        env.update({"RUN_ALL_ROOT": str(self.racine), "RUN_ALL_DEPS": ""})
        resultat = subprocess.run(["bash", str(self.racine / "tests" / "run_all.sh"), "--staged"], env=env, capture_output=True,
                                  text=True, timeout=120)
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("le sélecteur a échoué (code 5) : exécution complète", resultat.stdout)
        self.assertRegex(resultat.stdout, r"alpha\s+2 tests · OK")                # toutes les suites tournent
        self.assertRegex(resultat.stdout, r"beta\s+2 tests · OK")
        self.assertEqual(self.complete.read_text().strip(), self.git("write-tree"))   # empreinte complète écrite
        self.assertFalse(self.ciblee.exists())                                       # et pas d'empreinte ciblée


class ScriptsShellDuDepot(unittest.TestCase):
    """Tout script shell de test du vrai dossier tests/ est listé dans le lanceur ou déclaré auxiliaire."""

    def test_chaque_script_shell_est_liste_ou_declare_auxiliaire(self):
        tests = RUN_ALL.parent
        texte = RUN_ALL.read_text(encoding="utf-8")
        auxiliaires = set(re.findall(r"^#\s*AUXILIAIRE\s+(\S+)", texte, re.M))
        oublies = []
        for script in sorted(tests.glob("*/*.sh")):
            relatif = f"tests/{script.parent.name}/{script.name}"
            if f"{relatif}:" not in texte and relatif not in auxiliaires:
                oublies.append(relatif)
        self.assertEqual(oublies, [], f"script(s) de test shell ni listé(s) ni déclaré(s) auxiliaire(s) : {oublies}")

    def test_les_auxiliaires_declares_existent(self):
        texte = RUN_ALL.read_text(encoding="utf-8")
        for relatif in re.findall(r"^#\s*AUXILIAIRE\s+(\S+)", texte, re.M):
            self.assertTrue((RUN_ALL.parents[1] / relatif).is_file(), relatif)


if __name__ == "__main__":
    unittest.main()
