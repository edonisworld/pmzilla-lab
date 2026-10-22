"""
Tests du lanceur tests/run_all.sh sur un faux dépôt : suites qui réussissent, suite qui échoue, filtre par nom,
tests shell, aucune suite.

    python3 -m unittest discover -s tests/run_all -v

Le lanceur est pointé sur un dossier temporaire (RUN_ALL_ROOT) et sans dépendances supplémentaires (RUN_ALL_DEPS
vide) ; il ne lance jamais les vraies suites.
"""
import ast
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

RUN_ALL = Path(__file__).resolve().parents[1] / "run_all.sh"

SUITE_OK = "import unittest\nclass T(unittest.TestCase):\n    def test_a(self): pass\n    def test_b(self): pass\n"
SUITE_KO = ("import unittest\nclass T(unittest.TestCase):\n    def test_a(self): pass\n"
            "    def test_casse(self): self.assertEqual(1, 2)\n")
SHELL_OK = 'echo "ok : un"\necho "ok : deux"\necho "2 réussis, 0 échec(s)"\n'
SHELL_KO = 'echo "ECHEC : un"\necho "1 réussis, 1 échec(s)"\nexit 1\n'
FAUX_MOT_DE_PASSE = "faux-mot-" + "de-passe"   # fabriqués à l'exécution : aucun littéral pour la garde des secrets
FAUX_ROLE = "faux-" + "role"


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
        # Change light-spec-finish (décision du 2026-10-18, design D11) : un nom qui ne correspond à aucune suite sort avec le code 5 ; il
        # partageait le code 2 des erreurs d'usage, ce qui laissait passer pour vert le lancement d'une suite déclarée mais disparue.
        self.suite("alpha", SUITE_OK)
        resultat = self.lancer("inconnue")
        self.assertEqual(resultat.returncode, 5)
        self.assertIn("run_all : aucune suite ne correspond aux noms donnés (inconnue)", resultat.stdout)
        vide = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, vide, True)
        (vide / "tests").mkdir()
        self.racine = vide
        self.assertEqual(self.lancer("inconnue").returncode, 5)

    def test_nom_inconnu_nomme_les_noms_et_n_ecrit_aucune_duree(self):
        self.suite("alpha", SUITE_OK)
        durees = self.racine / "durees.tsv"
        resultat = self.lancer("inconnue", "autre", RUN_ALL_DURATIONS=str(durees))
        self.assertEqual(resultat.returncode, 5)
        self.assertIn("run_all : aucune suite ne correspond aux noms donnés (inconnue autre)", resultat.stdout)
        self.assertFalse(durees.exists())
        self.assertNotIn("TOTAL", resultat.stdout)

    def test_deux_noms_dont_un_existe_lance_cette_suite(self):
        self.suite("alpha", SUITE_OK)
        resultat = self.lancer("alpha", "inconnue")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("TOTAL : 2 tests dans 1 suites · tous réussis", resultat.stdout)

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


SUITE_LIT_ENTREE = ("import sys, unittest\nclass T(unittest.TestCase):\n"
                    "    def test_a(self): self.assertEqual(sys.stdin.read(), '')\n")
SUITE_DORT = "import time, unittest\nclass T(unittest.TestCase):\n    def test_a(self): time.sleep(60)\n"
SUITE_FILS = ("import os, subprocess, unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n"
              "        p = subprocess.Popen(['sleep', '300'])\n        open(os.environ['FILS_PID'], 'w').write(str(p.pid))\n"
              "        p.wait()\n")


class EntreeEtDelai(unittest.TestCase):
    """Entrée standard fermée par le lanceur ; délai par suite : échec nommé, suivantes lancées, aucun processus restant."""

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)

    def suite(self, nom, texte):
        dossier = self.racine / "tests" / nom
        dossier.mkdir(parents=True)
        (dossier / f"test_{nom}.py").write_text(texte)

    def env(self, **variables):
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS",
                                                                "RUN_ALL_SUITE_TIMEOUT")}
        env.update({"RUN_ALL_ROOT": str(self.racine), "RUN_ALL_DEPS": ""}, **variables)
        return env

    def lancer(self, *arguments, **variables):
        return subprocess.run(["bash", str(RUN_ALL), *arguments], env=self.env(**variables), capture_output=True,
                              text=True, timeout=120, stdin=subprocess.DEVNULL)

    def test_une_suite_qui_lit_son_entree_lit_la_fin_de_fichier(self):
        self.suite("alpha", SUITE_LIT_ENTREE)
        processus = subprocess.Popen(["bash", str(RUN_ALL), "alpha"], env=self.env(), stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)   # entrée ouverte, jamais fermée
        self.addCleanup(processus.kill)
        self.addCleanup(processus.stdin.close)
        self.addCleanup(processus.stdout.close)
        sortie = processus.stdout.read()
        processus.wait(timeout=30)
        self.assertEqual(processus.returncode, 0, sortie)
        self.assertIn("TOTAL : 1 tests dans 1 suites · tous réussis", sortie)

    def test_une_suite_shell_qui_lit_son_entree_lit_la_fin_de_fichier(self):
        chemin = self.racine / "tests" / "installation" / "test_install_links.sh"
        chemin.parent.mkdir(parents=True)
        chemin.write_text('if read -r ligne; then echo "1 réussis, 1 échec(s)"; else echo "1 réussis, 0 échec(s)"; fi\n')
        processus = subprocess.Popen(["bash", str(RUN_ALL), "installation"], env=self.env(), stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.addCleanup(processus.kill)
        self.addCleanup(processus.stdin.close)
        self.addCleanup(processus.stdout.close)
        sortie = processus.stdout.read()
        processus.wait(timeout=30)
        self.assertEqual(processus.returncode, 0, sortie)

    def test_suite_python_trop_lente_est_un_echec_nomme_et_les_autres_passent(self):
        self.suite("alpha", SUITE_OK)
        self.suite("lente", SUITE_DORT)
        resultat = self.lancer(RUN_ALL_SUITE_TIMEOUT="1")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertRegex(resultat.stdout, r"lente\s+\? tests · ÉCHEC : délai dépassé \(1 s\)")
        self.assertRegex(resultat.stdout, r"alpha\s+2 tests · OK")
        self.assertIn("lente (délai dépassé)", resultat.stdout.splitlines()[-1])

    def test_suite_shell_trop_lente_est_un_echec_nomme(self):
        self.suite("alpha", SUITE_OK)
        self.shell_lent = self.racine / "tests" / "hooks" / "test_pre_commit.sh"
        self.shell_lent.parent.mkdir(parents=True)
        self.shell_lent.write_text("sleep 60\n")
        resultat = self.lancer("alpha", "hooks", RUN_ALL_SUITE_TIMEOUT="1")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertRegex(resultat.stdout, r"hooks \(shell\)\s+\? tests · ÉCHEC : délai dépassé \(1 s\)")
        self.assertRegex(resultat.stdout, r"alpha\s+2 tests · OK")
        self.assertIn("1 suite(s) en échec : hooks (délai dépassé)", resultat.stdout)

    def test_aucun_processus_fils_ne_reste_apres_le_delai(self):
        self.suite("fils", SUITE_FILS)
        fichier = self.racine / "fils.pid"
        resultat = self.lancer("fils", RUN_ALL_SUITE_TIMEOUT="1", FILS_PID=str(fichier))
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertIn("délai dépassé", resultat.stdout)
        pid = int(fichier.read_text())
        try:
            os.kill(pid, 0)
            vivant = True
        except ProcessLookupError:
            vivant = False
        if vivant:
            os.kill(pid, 9)
        self.assertFalse(vivant, "le processus fils de la suite arrêtée tourne encore")

    def test_aucune_empreinte_apres_un_delai_depasse(self):
        self.suite("lente", SUITE_DORT)
        for chemin in re.findall(r"(tests/\S+\.sh):", RUN_ALL.read_text(encoding="utf-8")):
            cible = self.racine / chemin
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_text(SHELL_OK)
        subprocess.run(["git", "init", "-q"], cwd=self.racine, check=True)
        subprocess.run(["git", "add", "-A"], cwd=self.racine, check=True)
        resultat = self.lancer(RUN_ALL_SUITE_TIMEOUT="1")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertFalse((self.racine / ".git" / "pmzilla-run-all-ok").exists())

    def test_delai_invalide_sort_en_2_sans_lancer_de_suite(self):
        self.suite("alpha", SUITE_OK)
        for valeur in ("abc", "0", "-5", "1.5", ""):
            resultat = self.lancer("alpha", RUN_ALL_SUITE_TIMEOUT=valeur)
            self.assertEqual(resultat.returncode, 2, (valeur, resultat.stdout))
            self.assertIn(f"run_all : délai par suite invalide ({valeur}) : un nombre entier de secondes est attendu", resultat.stdout)
            self.assertNotIn("TOTAL", resultat.stdout)
            self.assertNotRegex(resultat.stdout, r"alpha\s+2 tests")


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


SUITE_UNE_SECONDE = "import time, unittest\nclass T(unittest.TestCase):\n    def test_a(self): time.sleep(1)\n"
DUREE_FIN_DE_LIGNE = r" · \d+,\d s$"
ENTETE_DUREES = ["lancement", "identifiant", "genre", "poste", "suite", "type", "secondes", "secondes_unittest", "verdict", "raison"]


class MesuresDeDuree(unittest.TestCase):
    """Durée de chaque suite, dix plus lentes, durée totale (test-speed D1, D2) ; les mots-clés existants restent."""

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)

    def suite(self, nom, texte):
        dossier = self.racine / "tests" / nom
        dossier.mkdir(parents=True)
        (dossier / f"test_{nom}.py").write_text(texte)

    def lancer(self, *arguments, path_avant=None, **variables):
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS")}
        env.update({"RUN_ALL_ROOT": str(self.racine), "RUN_ALL_DEPS": ""}, **variables)
        if path_avant:
            env["PATH"] = f"{path_avant}{os.pathsep}{env['PATH']}"
        return subprocess.run(["bash", str(RUN_ALL), *arguments], env=env, capture_output=True, text=True, timeout=120,
                              stdin=subprocess.DEVNULL)

    def lignes_de_suite(self, sortie):
        return [l for l in sortie.splitlines() if re.search(r"\s\d+ tests · |\s\? tests · ", l)]

    def test_chaque_ligne_de_suite_se_termine_par_sa_duree(self):
        self.suite("alpha", SUITE_OK)
        self.suite("casse", SUITE_KO)
        self.suite("lente", SUITE_DORT)
        chemin = self.racine / "tests" / "hooks" / "test_pre_commit.sh"
        chemin.parent.mkdir(parents=True)
        chemin.write_text(SHELL_OK)
        resultat = self.lancer("alpha", "casse", "hooks")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        lignes = self.lignes_de_suite(resultat.stdout)
        self.assertEqual(len(lignes), 3, resultat.stdout)
        for ligne in lignes:
            self.assertRegex(ligne, DUREE_FIN_DE_LIGNE)
        self.assertRegex(resultat.stdout, r"alpha\s+2 tests · OK · \d+,\d s\n")
        self.assertRegex(resultat.stdout, r"hooks \(shell\)\s+2 tests · OK · \d+,\d s\n")
        self.assertRegex(resultat.stdout, r"casse\s+2 tests · ÉCHEC \(code 1\) : .*· \d+,\d s\n")

    def test_la_ligne_d_une_suite_en_delai_garde_ses_mots_cles_et_une_duree(self):
        self.suite("lente", SUITE_DORT)
        resultat = self.lancer(RUN_ALL_SUITE_TIMEOUT="1")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertRegex(resultat.stdout, r"lente\s+\? tests · ÉCHEC : délai dépassé \(1 s\) · \d+,\d s\n")

    def test_la_suite_la_plus_lente_est_listee_en_premier_avant_la_ligne_de_total(self):
        self.suite("rapide", SUITE_OK)
        self.suite("dort", SUITE_UNE_SECONDE)
        resultat = self.lancer("rapide", "dort")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        lignes = resultat.stdout.splitlines()
        i_titre = lignes.index("Suites les plus lentes :")
        i_total = next(i for i, l in enumerate(lignes) if l.startswith("TOTAL :"))
        derniere_suite = max(i for i, l in enumerate(lignes) if re.search(r"\s\d+ tests · OK", l))
        self.assertGreater(i_titre, derniere_suite)
        self.assertLess(i_titre, i_total)
        liste = lignes[i_titre + 1:i_total]
        self.assertEqual(liste[-1], "")                       # la ligne vide précède toujours le total
        liste = liste[:-1]
        self.assertRegex(liste[-1], r"^Tests sautés : 0 \(suites Python 0, branches shell 0\)$")   # test-speed-2, D25
        liste = liste[:-1]
        self.assertEqual(len(liste), 2)
        self.assertRegex(liste[0], r"^  \d+,\d s  dort$")
        self.assertRegex(liste[1], r"^  \d+,\d s  rapide$")
        self.assertGreaterEqual(float(liste[0].split()[0].replace(",", ".")), 1.0)

    def test_une_seule_suite_donne_le_titre_et_une_ligne(self):
        self.suite("alpha", SUITE_OK)
        lignes = self.lancer("alpha").stdout.splitlines()
        i = lignes.index("Suites les plus lentes :")
        self.assertRegex(lignes[i + 1], r"^  \d+,\d s  alpha$")
        self.assertRegex(lignes[i + 2], r"^Tests sautés : 0 \(suites Python 0, branches shell 0\)$")   # test-speed-2, D25
        self.assertEqual(lignes[i + 3], "")
        self.assertTrue(lignes[i + 4].startswith("TOTAL :"))

    def test_au_plus_dix_suites_listees_ex_aequo_dans_l_ordre_du_lancement(self):
        for numero in range(12):
            self.suite(f"s{numero:02d}", SUITE_OK)
        resultat = self.lancer()
        lignes = resultat.stdout.splitlines()
        i = lignes.index("Suites les plus lentes :")
        liste = [l for l in lignes[i + 1:] if l.startswith("  ")]
        self.assertEqual(len(liste), 10, resultat.stdout)
        durees = [float(l.split()[0].replace(",", ".")) for l in liste]
        self.assertEqual(durees, sorted(durees, reverse=True))

    def test_la_ligne_de_total_garde_ses_mots_cles_et_gagne_la_duree_totale(self):
        self.suite("alpha", SUITE_OK)
        self.suite("casse", SUITE_KO)
        ok = self.lancer("alpha")
        self.assertRegex(ok.stdout, r"TOTAL : 2 tests dans 1 suites · tous réussis · durée totale \d+,\d s\n$")
        ko = self.lancer("alpha", "casse")
        self.assertRegex(ko.stdout, r"TOTAL : 4 tests dans 2 suites · 1 suite\(s\) en échec : casse · durée totale \d+,\d s\n$")

    def test_la_ligne_d_empreinte_reste_apres_la_ligne_de_total(self):
        self.suite("alpha", SUITE_OK)
        for chemin in re.findall(r"(tests/\S+\.sh):", RUN_ALL.read_text(encoding="utf-8")):
            cible = self.racine / chemin
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_text(SHELL_OK)
        subprocess.run(["git", "init", "-q"], cwd=self.racine, check=True)
        subprocess.run(["git", "add", "-A"], cwd=self.racine, check=True)
        resultat = self.lancer()
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        lignes = resultat.stdout.splitlines()
        self.assertTrue(lignes[-1].startswith("Empreinte de l'index enregistrée"), lignes[-1])
        self.assertTrue(lignes[-2].startswith("TOTAL :"), lignes[-2])

    def test_sans_perl_les_durees_sont_en_secondes_entieres(self):
        self.suite("alpha", SUITE_OK)
        faux = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, faux, True)
        (faux / "perl").write_text("#!/bin/sh\nexit 1\n")
        (faux / "perl").chmod(0o755)
        resultat = self.lancer("alpha", path_avant=str(faux))
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertRegex(resultat.stdout, r"alpha\s+2 tests · OK · \d+,0 s\n")
        self.assertRegex(resultat.stdout, r"durée totale \d+,0 s\n$")


class FichierDesDurees(unittest.TestCase):
    """Fichier des durées hors Git (test-speed D3, D4) : champs, genres, aucun chemin, jamais d'effet sur l'issue."""

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.sortie = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.sortie, True)
        self.durees = self.sortie / "mesures" / "durees.tsv"
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

    def git(self, *arguments, cwd=None):
        return subprocess.run(["git", *arguments], cwd=cwd or self.racine, capture_output=True, text=True, check=True).stdout.strip()

    def env(self, **variables):
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS",
                                                                "RUN_ALL_DURATIONS", "RUN_ALL_ROOT", "PMZILLA_LAB_WORKSPACE",
                                                                "PMZILLA_LAB_DATA")}
        env.update({"RUN_ALL_ROOT": str(self.racine), "RUN_ALL_DEPS": ""}, **variables)
        return env

    def lancer(self, *arguments, script=RUN_ALL, racine=None, **variables):
        env = self.env(**variables)
        if racine is not None:
            env["RUN_ALL_ROOT"] = str(racine)
        return subprocess.run(["bash", str(script), *arguments], env=env, capture_output=True, text=True, timeout=120,
                              stdin=subprocess.DEVNULL)

    def lignes(self, fichier=None):
        return (fichier or self.durees).read_text(encoding="utf-8").splitlines()

    def champs(self, ligne):
        return ligne.split("\t")

    def test_entete_de_dix_champs_et_une_ligne_par_suite(self):
        resultat = self.lancer(RUN_ALL_DURATIONS=str(self.durees))
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        lignes = self.lignes()
        self.assertEqual(len(self.champs(lignes[0])), 10)
        self.assertEqual(len(lignes) - 1, 2 + len(re.findall(r"tests/\S+\.sh:", RUN_ALL.read_text(encoding="utf-8"))))
        for ligne in lignes[1:]:
            champs = self.champs(ligne)
            self.assertEqual(len(champs), 10, ligne)
            self.assertRegex(champs[0], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$")
            self.assertEqual(champs[2], "complet")
            self.assertEqual(champs[3], "espace")
            self.assertIn(champs[5], ("python", "shell"))
            self.assertRegex(champs[6], r"^\d+\.\d+$")
            self.assertEqual(champs[8], "ok")
            self.assertEqual(champs[9], "")
        self.assertEqual(len({self.champs(l)[1] for l in lignes[1:]}), 1)   # un seul identifiant de lancement

    def test_temps_unittest_des_suites_python_vide_pour_les_suites_shell(self):
        self.lancer(RUN_ALL_DURATIONS=str(self.durees))
        par_suite = {self.champs(l)[4]: self.champs(l) for l in self.lignes()[1:]}
        self.assertEqual(par_suite["alpha"][5], "python")
        self.assertRegex(par_suite["alpha"][7], r"^\d+\.\d+$")
        self.assertEqual(par_suite["hooks"][5], "shell")
        self.assertEqual(par_suite["hooks"][7], "")

    def test_verdicts_echec_et_delai_et_aucune_sortie_de_suite(self):
        (self.racine / "tests" / "casse").mkdir()
        (self.racine / "tests" / "casse" / "test_casse.py").write_text(SUITE_KO)
        (self.racine / "tests" / "lente").mkdir()
        (self.racine / "tests" / "lente" / "test_lente.py").write_text(SUITE_DORT)
        resultat = self.lancer("casse", "lente", RUN_ALL_DURATIONS=str(self.durees), RUN_ALL_SUITE_TIMEOUT="1")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        par_suite = {self.champs(l)[4]: self.champs(l) for l in self.lignes()[1:]}
        self.assertEqual(par_suite["casse"][8], "échec")
        self.assertEqual(par_suite["lente"][8], "délai")
        self.assertEqual(par_suite["lente"][7], "")                                  # pas de ligne « Ran » : temps vide
        self.assertEqual(par_suite["casse"][9], "")
        contenu = self.durees.read_text(encoding="utf-8")
        self.assertNotIn("AssertionError", contenu)
        self.assertNotIn(str(self.racine), contenu)
        self.assertNotIn(str(self.sortie), contenu)

    def test_genres_filtre_et_cible(self):
        self.lancer("alpha", RUN_ALL_DURATIONS=str(self.durees))
        self.assertEqual({self.champs(l)[2] for l in self.lignes()[1:]}, {"filtré"})
        cible = self.sortie / "cible.tsv"
        (self.racine / "tests" / "alpha" / "test_alpha.py").write_text(SUITE_OK + "\n")
        self.git("add", "-A")
        resultat = self.lancer("--staged", RUN_ALL_DURATIONS=str(cible))
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertEqual({self.champs(l)[2] for l in self.lignes(cible)[1:]}, {"ciblé"})

    def test_un_lancement_cible_passe_en_complet_est_note_complet(self):
        (self.racine / "tools").mkdir(exist_ok=True)
        (self.racine / "tools" / "orphelin.py").write_text("pass\n")
        self.git("add", "-A")
        resultat = self.lancer("--staged", RUN_ALL_DURATIONS=str(self.durees))
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertEqual({self.champs(l)[2] for l in self.lignes()[1:]}, {"complet"})

    def test_lancements_successifs_ajoutent_sans_second_entete(self):
        self.lancer("alpha", RUN_ALL_DURATIONS=str(self.durees))
        self.lancer("beta", RUN_ALL_DURATIONS=str(self.durees))
        lignes = self.lignes()
        self.assertEqual(len(lignes), 3)
        self.assertEqual(sum(1 for l in lignes if l.startswith("lancement\t")), 1)

    def test_checkout_worktree_pour_un_worktree_lie(self):
        lie = self.sortie / "lie"
        self.git("worktree", "add", "-q", "-b", "autre", str(lie))
        self.lancer("alpha", racine=lie, RUN_ALL_DURATIONS=str(self.durees))
        self.assertEqual({self.champs(l)[3] for l in self.lignes()[1:]}, {"worktree"})

    def test_racine_injectee_sans_variable_aucun_fichier_nulle_part(self):
        donnees = self.sortie / "donnees"
        resultat = self.lancer(HOME=str(self.sortie), PMZILLA_LAB_DATA=str(donnees))
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertNotIn("durées non enregistrées", resultat.stdout)
        self.assertEqual(list(self.sortie.rglob("*.tsv")), [])
        self.assertFalse(donnees.exists())
        self.assertEqual(list(self.racine.rglob("*.tsv")), [])

    def test_fichier_illisible_en_ecriture_ne_change_ni_le_code_ni_l_empreinte(self):
        bloc = self.sortie / "fichier"
        bloc.write_text("pas un dossier\n")
        resultat = self.lancer(RUN_ALL_DURATIONS=str(bloc / "sous" / "durees.tsv"))
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        lignes = resultat.stdout.splitlines()
        i_total = next(i for i, l in enumerate(lignes) if l.startswith("TOTAL :"))
        self.assertEqual(lignes.count("run_all : durées non enregistrées (écriture impossible)"), 1)
        self.assertLess(lignes.index("run_all : durées non enregistrées (écriture impossible)"), i_total)
        self.assertEqual((self.racine / ".git" / "pmzilla-run-all-ok").read_text().strip(), self.git("write-tree"))
        self.assertNotIn(str(bloc), resultat.stdout)

    def copie_du_lanceur(self, avec_module=True):
        shutil.copy(RUN_ALL, self.racine / "tests" / "run_all.sh")
        if avec_module:
            (self.racine / "tools").mkdir(exist_ok=True)
            shutil.copy(RUN_ALL.parents[1] / "tools" / "lab_paths.sh", self.racine / "tools" / "lab_paths.sh")

    def test_dossier_de_donnees_du_lab_resolu_par_le_module_partage(self):
        self.copie_du_lanceur()
        contenu = self.sortie / "contenu"
        contenu.mkdir()
        donnees = self.sortie / "donnees"
        env = self.env(PMZILLA_LAB_WORKSPACE=str(contenu), PMZILLA_LAB_DATA=str(donnees))
        del env["RUN_ALL_ROOT"]
        resultat = subprocess.run(["bash", str(self.racine / "tests" / "run_all.sh"), "alpha"], env=env, capture_output=True,
                                  text=True, timeout=120, stdin=subprocess.DEVNULL)
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        fichier = donnees / "mesures" / "run_all-durees.tsv"
        self.assertEqual(len(self.lignes(fichier)), 2)
        self.assertEqual((donnees / "mesures").stat().st_mode & 0o777, 0o700)

    def test_dossier_de_donnees_introuvable_une_ligne_sans_chemin_et_code_inchange(self):
        self.copie_du_lanceur(avec_module=False)
        env = self.env()
        del env["RUN_ALL_ROOT"]
        resultat = subprocess.run(["bash", str(self.racine / "tests" / "run_all.sh"), "alpha"], env=env, capture_output=True,
                                  text=True, timeout=120, stdin=subprocess.DEVNULL)
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertEqual(resultat.stdout.count("run_all : durées non enregistrées (dossier de données introuvable)"), 1)
        self.assertNotIn(str(self.racine), resultat.stdout)


class VariablesDeBase(unittest.TestCase):
    """Test-speed-2, D2 : hors passage de la base jetable (DBTEST_PORT absent ou vide), aucune variable PMZILLA_LAB_DB_* n'atteint une suite,
    Python ou shell ; dans le passage de la base jetable, elles passent telles quelles. Les suites notent leur environnement dans un fichier."""

    LIGNE = "run_all : variables PMZILLA_LAB_DB_* retirées de l'environnement des suites (la base jetable passe par tools/dbtest.sh)"
    BASES = {"PMZILLA_LAB_DB_URL": "postgresql://postgres@127.0.0.1:5432/pmzilla", "PMZILLA_LAB_DB_PORT": "5432",
             "PMZILLA_LAB_DB_PASSWORD": FAUX_MOT_DE_PASSE, "PMZILLA_LAB_DB_PASSWORD_FLOW": FAUX_ROLE,
             "PMZILLA_LAB_DB_SECURITY_BIN": "/faux/security"}
    suite = Lanceur.suite
    shell = Lanceur.shell

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.notes = self.racine / "notes"
        self.notes.mkdir()
        self.suite("alpha", "import os, unittest\n"
                   f"open({str(self.notes / 'python')!r}, 'w').write('\\n'.join(sorted(k for k in os.environ if k.startswith('PMZILLA_LAB_DB_') or (k == 'DBTEST_PORT' and os.environ[k]))))\n"
                   "class T(unittest.TestCase):\n    def test_a(self): pass\n")
        self.shell("hooks/test_pre_commit.sh",
                   f'env | grep -E "^(PMZILLA_LAB_DB_[A-Z_]*|DBTEST_PORT)=.+" | cut -d= -f1 | sort > "{self.notes / "shell"}"\n'
                   'echo "1 réussis, 0 échec(s)"\n')

    def lancer(self, *arguments, **variables):
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS", "DBTEST_PORT")
               and not k.startswith("PMZILLA_LAB_DB_")}
        env.update({"RUN_ALL_ROOT": str(self.racine), "RUN_ALL_DEPS": ""}, **variables)
        return subprocess.run(["bash", str(RUN_ALL), *arguments], env=env, capture_output=True, text=True, timeout=120)

    def vues(self):
        return {genre: sorted((self.notes / genre).read_text().split()) for genre in ("python", "shell")}

    def test_les_variables_de_base_n_atteignent_aucune_suite(self):
        resultat = self.lancer("alpha", "hooks", **self.BASES)
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertEqual(self.vues(), {"python": [], "shell": []})
        self.assertEqual(resultat.stdout.count(self.LIGNE), 1)
        self.assertLess(resultat.stdout.index(self.LIGNE), resultat.stdout.index("alpha"))   # avant la première suite
        for valeur in self.BASES.values():
            self.assertNotIn(valeur, resultat.stdout)

    def test_sans_variable_de_base_aucune_ligne(self):
        resultat = self.lancer("alpha", "hooks")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertNotIn("variables PMZILLA_LAB_DB_*", resultat.stdout)

    def test_repere_vide_compte_comme_absent(self):
        resultat = self.lancer("alpha", "hooks", DBTEST_PORT="", **self.BASES)
        self.assertEqual(self.vues(), {"python": [], "shell": []})
        self.assertEqual(resultat.stdout.count(self.LIGNE), 1)

    def test_dans_le_passage_de_la_base_jetable_les_variables_passent_sans_ligne(self):
        resultat = self.lancer("alpha", "hooks", DBTEST_PORT="55432", **self.BASES)
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        attendues = sorted([*self.BASES, "DBTEST_PORT"])
        self.assertEqual(self.vues(), {"python": attendues, "shell": attendues})
        self.assertNotIn("variables PMZILLA_LAB_DB_*", resultat.stdout)

    def test_codes_et_total_inchanges_par_le_retrait(self):
        resultat = self.lancer("alpha", **self.BASES)
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("TOTAL : 1 tests dans 1 suites · tous réussis", resultat.stdout)


SUITE_DEUX_SAUTS = ("import unittest\nclass T(unittest.TestCase):\n    def test_a(self): pass\n"
                    "    @unittest.skip('x')\n    def test_b(self): pass\n    @unittest.skip('y')\n    def test_c(self): pass\n")
SUITE_UN_SAUT_ET_UN_ECHEC = ("import unittest\nclass T(unittest.TestCase):\n    def test_a(self): self.assertEqual(1, 2)\n"
                             "    @unittest.skip('x')\n    def test_b(self): pass\n")
SUITE_DIT_SAUTS_PUIS_DORT = ("import time, unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n"
                             "        print('OK (skipped=5)', flush=True)\n        time.sleep(60)\n")
SHELL_TROIS_SAUTS = ('echo "saut : un"\necho "ok : deux"\necho "saut : trois"\necho "  saut : pas en début de ligne"\n'
                     'echo "saut : quatre"\necho "3 réussis, 0 échec(s)"\n')


class TestsSautes(unittest.TestCase):
    """Test-speed-2, D25 : la ligne « Tests sautés : N (suites Python p, branches shell s) » après la liste des plus lentes et avant la
    ligne vide et le total. Suite Python : le nombre après « skipped= » de sa dernière ligne ; suite shell : les lignes qui commencent par
    « saut : » ; une suite en délai compte 0."""

    LIGNE = r"^Tests sautés : (\d+) \(suites Python (\d+), branches shell (\d+)\)$"
    suite = Lanceur.suite
    shell = Lanceur.shell

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)

    def lancer(self, *arguments, **variables):
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS")}
        env.update({"RUN_ALL_ROOT": str(self.racine), "RUN_ALL_DEPS": ""}, **variables)
        return subprocess.run(["bash", str(RUN_ALL), *arguments], env=env, capture_output=True, text=True, timeout=120,
                              stdin=subprocess.DEVNULL)

    def ligne_des_sauts(self, sortie):
        trouvees = [l for l in sortie.splitlines() if l.startswith("Tests sautés")]
        self.assertEqual(len(trouvees), 1, sortie)
        return trouvees[0]

    def test_somme_des_sauts_python_et_des_lignes_saut_shell(self):
        self.suite("alpha", SUITE_DEUX_SAUTS)
        self.suite("beta", SUITE_DEUX_SAUTS)
        self.shell("hooks/test_pre_commit.sh", SHELL_TROIS_SAUTS)
        resultat = self.lancer("alpha", "beta", "hooks")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertEqual(self.ligne_des_sauts(resultat.stdout), "Tests sautés : 7 (suites Python 4, branches shell 3)")

    def test_zero_quand_rien_n_est_saute(self):
        self.suite("alpha", SUITE_OK)
        resultat = self.lancer("alpha")
        self.assertEqual(self.ligne_des_sauts(resultat.stdout), "Tests sautés : 0 (suites Python 0, branches shell 0)")

    def test_place_apres_les_plus_lentes_et_avant_la_ligne_vide_et_le_total(self):
        self.suite("alpha", SUITE_DEUX_SAUTS)
        lignes = self.lancer("alpha").stdout.splitlines()
        i = lignes.index("Suites les plus lentes :")
        self.assertRegex(lignes[i + 1], r"^  \d+,\d s  alpha$")
        self.assertRegex(lignes[i + 2], self.LIGNE)
        self.assertEqual(lignes[i + 3], "")
        self.assertTrue(lignes[i + 4].startswith("TOTAL : 3 tests dans 1 suites · tous réussis"), lignes[i + 4])

    def test_une_suite_en_echec_compte_ses_sauts(self):
        self.suite("casse", SUITE_UN_SAUT_ET_UN_ECHEC)
        resultat = self.lancer("casse")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertEqual(self.ligne_des_sauts(resultat.stdout), "Tests sautés : 1 (suites Python 1, branches shell 0)")

    def test_une_suite_en_delai_compte_zero(self):
        self.suite("lente", SUITE_DIT_SAUTS_PUIS_DORT)
        self.suite("alpha", SUITE_DEUX_SAUTS)
        resultat = self.lancer("lente", "alpha", RUN_ALL_SUITE_TIMEOUT="1")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertRegex(resultat.stdout, r"lente\s+\? tests · ÉCHEC : délai dépassé")
        self.assertEqual(self.ligne_des_sauts(resultat.stdout), "Tests sautés : 2 (suites Python 2, branches shell 0)")

    def test_une_suite_shell_en_delai_compte_zero(self):
        self.shell("hooks/test_pre_commit.sh", 'echo "saut : un"\nsleep 60\n')
        resultat = self.lancer("hooks", RUN_ALL_SUITE_TIMEOUT="1")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertEqual(self.ligne_des_sauts(resultat.stdout), "Tests sautés : 0 (suites Python 0, branches shell 0)")

    # skips-visible, D1 et D3 : la ligne d'une suite shell montre ses propres sauts, seulement s'il y en a.
    def test_ligne_shell_reussie_avec_sauts_les_montre(self):
        self.shell("hooks/test_pre_commit.sh", 'echo "saut : un"\necho "saut : deux"\necho "3 réussis, 0 échec(s)"\n')
        resultat = self.lancer("hooks")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertRegex(resultat.stdout, r"hooks \(shell\)\s+3 tests · OK \(sautés=2\) · \d+,\d s\n")
        self.assertEqual(self.ligne_des_sauts(resultat.stdout), "Tests sautés : 2 (suites Python 0, branches shell 2)")

    def test_ligne_shell_en_echec_avec_sauts_les_montre(self):
        self.shell("hooks/test_pre_commit.sh", 'echo "saut : un"\necho "1 réussis, 1 échec(s)"\nexit 1\n')
        resultat = self.lancer("hooks")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertRegex(resultat.stdout, r"hooks \(shell\)\s+2 tests · ÉCHEC \(code 1, 1 échec\(s\), sautés=1\) · \d+,\d s\n")
        self.assertEqual(self.ligne_des_sauts(resultat.stdout), "Tests sautés : 1 (suites Python 0, branches shell 1)")

    def test_ligne_shell_sans_saut_reste_comme_avant(self):
        self.shell("hooks/test_pre_commit.sh", SHELL_OK)
        resultat = self.lancer("hooks")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertRegex(resultat.stdout, r"hooks \(shell\)\s+\d+ tests · OK · \d+,\d s\n")
        self.assertNotIn("sautés=", resultat.stdout)

    def test_ligne_shell_en_delai_garde_sa_ligne_de_delai(self):
        self.shell("hooks/test_pre_commit.sh", 'echo "saut : un"\nsleep 60\n')
        resultat = self.lancer("hooks", RUN_ALL_SUITE_TIMEOUT="1")
        self.assertRegex(resultat.stdout, r"hooks \(shell\)\s+\? tests · ÉCHEC : délai dépassé \(1 s\) · \d+,\d s\n")
        self.assertNotIn("sautés=", resultat.stdout)

    def test_lancement_cible_et_lancement_complet_ont_la_ligne(self):
        for nom in ("alpha", "beta"):
            self.suite(nom, SUITE_DEUX_SAUTS)
        for chemin in re.findall(r"(tests/\S+\.sh):", RUN_ALL.read_text(encoding="utf-8")):
            self.shell(chemin[len("tests/"):], SHELL_OK)
        subprocess.run(["git", "init", "-q"], cwd=self.racine, check=True)
        subprocess.run(["git", "add", "-A"], cwd=self.racine, check=True)
        subprocess.run(["git", "-c", "user.email=t@example.org", "-c", "user.name=test", "commit", "-q", "-m", "base"],
                       cwd=self.racine, check=True)
        complet = self.lancer()
        self.assertEqual(self.ligne_des_sauts(complet.stdout), "Tests sautés : 4 (suites Python 4, branches shell 0)")
        (self.racine / "tests" / "alpha" / "test_alpha.py").write_text(SUITE_DEUX_SAUTS + "\n")
        subprocess.run(["git", "add", "tests/alpha/test_alpha.py"], cwd=self.racine, check=True)   # pas les __pycache__ du passage complet
        cible = self.lancer("--staged")
        self.assertEqual(cible.returncode, 0, cible.stdout)
        self.assertIn("select_suites : alpha", cible.stdout)
        self.assertEqual(self.ligne_des_sauts(cible.stdout), "Tests sautés : 2 (suites Python 2, branches shell 0)", cible.stdout)

    def test_la_ligne_ne_change_ni_le_code_ni_le_total_ni_les_lignes_de_suite(self):
        self.suite("alpha", SUITE_DEUX_SAUTS)
        resultat = self.lancer("alpha")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertRegex(resultat.stdout, r"alpha\s+3 tests · OK \(skipped=2\) · \d+,\d s\n")
        self.assertRegex(resultat.stdout, r"TOTAL : 3 tests dans 1 suites · tous réussis · durée totale \d+,\d s\n$")


def suite_notee(notes, nom, duree=0.0):
    """Suite Python factice qui note ses heures de début et de fin, son TMPDIR et son drapeau de bytecode dans le dossier des notes."""
    return ("import os, time, unittest\n"
            f"NOTES = {str(notes)!r}\nNOM = {nom!r}\n"
            "DEBUT = time.time()\n"
            "def tearDownModule():\n"
            "    open(os.path.join(NOTES, NOM + '.fin'), 'w').write(repr(time.time()))\n"
            "class T(unittest.TestCase):\n"
            "    def test_a(self):\n"
            "        open(os.path.join(NOTES, NOM + '.debut'), 'w').write(repr(DEBUT))\n"
            "        t = os.environ.get('TMPDIR', '')\n"
            "        open(os.path.join(NOTES, NOM + '.env'), 'w').write('\\n'.join([t, os.environ.get('PYTHONDONTWRITEBYTECODE', ''), "
            "str(os.path.isdir(t))]))\n"
            f"        time.sleep({duree})\n"
            "    def test_b(self): pass\n")


def shell_note(notes, nom, duree=0):
    """Script shell factice : mêmes notes que suite_notee."""
    return (f'd="{notes}"\nnow() {{ perl -MTime::HiRes=time -e \'printf "%.3f", time()\'; }}\nnow > "$d/{nom}.debut"\n'
            f'printf "%s\\n%s\\n%s\\n" "$TMPDIR" "${{PYTHONDONTWRITEBYTECODE:-}}" "$([ -d "$TMPDIR" ] && echo True || echo False)" > "$d/{nom}.env"\n'
            f'sleep {duree}\nnow > "$d/{nom}.fin"\necho "2 réussis, 0 échec(s)"\n')


class SuitesEnParallele(unittest.TestCase):
    """Test-speed-2, D19 à D23 : nombre de tâches, liste en série, isolement, sortie ordonnée, interruption."""

    suite = Lanceur.suite
    shell = Lanceur.shell
    LIGNE_DE_SUITE = re.compile(r"^(\S+(?: \(shell\))?)\s+(\d+|\?) tests · (.*?)(?: · \d+,\d s)?$")

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.notes = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.notes, True)
        self.tmp_lanceur = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp_lanceur, True)

    def env(self, **variables):
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS", "RUN_ALL_JOBS",
                                                                "DBTEST_PORT", "RUN_ALL_SUITE_TIMEOUT", "PYTHONDONTWRITEBYTECODE")}
        env.update({"RUN_ALL_ROOT": str(self.racine), "RUN_ALL_DEPS": "", "TMPDIR": str(self.tmp_lanceur)}, **variables)
        return env

    def lancer(self, *arguments, **variables):
        return subprocess.run(["bash", str(RUN_ALL), *arguments], env=self.env(**variables), capture_output=True, text=True,
                              timeout=120, stdin=subprocess.DEVNULL)

    def normalise(self, sortie):
        """Les lignes avant la liste des plus lentes, sans les durées ; la ligne de total sans sa durée."""
        lignes = []
        for ligne in sortie.splitlines():
            if ligne == "Suites les plus lentes :":
                break
            ligne = re.sub(r" · \d+,\d s$", "", ligne)
            # La queue d'une suite en échec reprend « Ran 2 tests in 0.001s » d'unittest : durée mesurée, différente d'un lancement à l'autre.
            lignes.append(re.sub(r"\b(in )\d+\.\d+s\b", r"\1<durée>", ligne))
        total = next(l for l in sortie.splitlines() if l.startswith("TOTAL :"))
        return lignes + [re.sub(r" · durée totale \d+,\d s$", "", total)]

    def lire(self, nom, genre):
        return (self.notes / f"{nom}.{genre}").read_text()

    def intervalle(self, nom):
        return float(self.lire(nom, "debut")), float(self.lire(nom, "fin"))

    def se_chevauchent(self, a, b):
        (a0, a1), (b0, b1) = self.intervalle(a), self.intervalle(b)
        return a0 < b1 and b0 < a1

    def suites_notees(self, *noms, duree=1.5):
        for nom in noms:
            self.suite(nom, suite_notee(self.notes, nom, duree))

    # Nombre de tâches (D19)

    def test_une_tache_donne_les_lignes_d_aujourd_hui_dans_l_ordre_de_declaration(self):
        self.suite("beta", SUITE_OK)
        self.suite("alpha", SUITE_OK)
        self.suite("casse", SUITE_KO)
        self.shell("hooks/test_pre_commit.sh", SHELL_OK)
        resultat = self.lancer("alpha", "beta", "casse", "hooks", RUN_ALL_JOBS="1")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        lignes = self.normalise(resultat.stdout)
        self.assertEqual(lignes[:2], [f"{'alpha':<22} {2:>5} tests · OK", f"{'beta':<22} {2:>5} tests · OK"])
        self.assertTrue(lignes[2].startswith(f"{'casse':<22} {2:>5} tests · ÉCHEC (code 1)"), lignes[2])
        self.assertEqual([l for l in lignes if "(shell)" in l], [f"{'hooks (shell)':<22} {2:>5} tests · OK"])
        self.assertNotIn("suites à la fois", resultat.stdout)

    def test_deux_taches_memes_lignes_meme_ordre_meme_quand_les_fins_sont_inversees(self):
        self.suite("alpha", suite_notee(self.notes, "alpha", 2.0))
        self.suite("beta", SUITE_OK)
        self.suite("casse", SUITE_KO)
        self.shell("hooks/test_pre_commit.sh", SHELL_OK)
        une = self.lancer("alpha", "beta", "casse", "hooks", RUN_ALL_JOBS="1")
        deux = self.lancer("alpha", "beta", "casse", "hooks", RUN_ALL_JOBS="2")
        self.assertEqual(deux.returncode, 1, deux.stdout)
        sans_ligne = [l for l in self.normalise(deux.stdout) if "suites à la fois" not in l]
        self.assertEqual(sans_ligne, self.normalise(une.stdout))
        suites = [l.split()[0] for l in self.normalise(deux.stdout) if self.LIGNE_DE_SUITE.match(l)]
        self.assertEqual(suites[:3], ["alpha", "beta", "casse"])

    def test_la_ligne_des_taches_n_est_ecrite_qu_avec_plus_d_une_tache_avant_la_premiere_suite(self):
        self.suite("alpha", SUITE_OK)
        self.suite("run_all", SUITE_OK)
        deux = self.lancer("alpha", "run_all", RUN_ALL_JOBS="3")
        ligne = "run_all : 3 suites à la fois, puis en série : run_all"
        self.assertEqual(deux.stdout.count(ligne), 1, deux.stdout)
        self.assertLess(deux.stdout.index(ligne), deux.stdout.index("alpha  "))
        self.assertNotIn("suites à la fois", self.lancer("alpha", "run_all", RUN_ALL_JOBS="1").stdout)

    def test_la_ligne_sans_suite_en_serie_dit_aucune(self):
        self.suite("alpha", SUITE_OK)
        self.assertIn("run_all : 2 suites à la fois, puis en série : aucune", self.lancer("alpha", RUN_ALL_JOBS="2").stdout)

    def test_nombre_de_taches_invalide_sort_en_2_avant_toute_suite(self):
        self.suite("alpha", SUITE_OK)
        for valeur in ("abc", "0", "-5", "1.5", ""):
            resultat = self.lancer("alpha", RUN_ALL_JOBS=valeur)
            self.assertEqual(resultat.returncode, 2, (valeur, resultat.stdout))
            self.assertIn(f"run_all : nombre de tâches invalide ({valeur}) : un nombre entier positif est attendu", resultat.stdout)
            self.assertNotIn("TOTAL", resultat.stdout)
            self.assertNotRegex(resultat.stdout, r"alpha\s+2 tests")

    def faux_sysctl(self, sortie, code=0, getconf=None):
        """PATH avec un faux sysctl ; getconf=(sortie, code) ajoute un faux getconf (sans lui, le getconf du système reste visible)."""
        faux = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, faux, True)
        (faux / "sysctl").write_text(f'#!/bin/sh\n[ "$1 $2" = "-n hw.logicalcpu" ] || exit 9\necho "{sortie}"\nexit {code}\n')
        (faux / "sysctl").chmod(0o755)
        if getconf is not None:
            (faux / "getconf").write_text(f'#!/bin/sh\n[ "$1" = "_NPROCESSORS_ONLN" ] || exit 9\necho "{getconf[0]}"\nexit {getconf[1]}\n')
            (faux / "getconf").chmod(0o755)
        return f"{faux}{os.pathsep}{os.environ['PATH']}"

    def test_defaut_la_moitie_des_processeurs_logiques_au_moins_un(self):
        self.suite("alpha", SUITE_OK)
        self.assertIn("run_all : 4 suites à la fois", self.lancer("alpha", PATH=self.faux_sysctl("8")).stdout)
        self.assertIn("run_all : 3 suites à la fois", self.lancer("alpha", PATH=self.faux_sysctl("7")).stdout)
        for cpu in ("1", "2"):
            self.assertNotIn("suites à la fois", self.lancer("alpha", PATH=self.faux_sysctl(cpu)).stdout, cpu)
        sans_getconf = ("", 1)
        self.assertNotIn("suites à la fois", self.lancer("alpha", PATH=self.faux_sysctl("8", code=1, getconf=sans_getconf)).stdout)
        self.assertNotIn("suites à la fois", self.lancer("alpha", PATH=self.faux_sysctl("beaucoup", getconf=sans_getconf)).stdout)

    def test_sysctl_illisible_le_nombre_vient_de_getconf_avant_un(self):
        """Local-ci-container, D3 : sous Linux, sysctl échoue ; getconf _NPROCESSORS_ONLN donne le nombre avant le repli à 1."""
        self.suite("alpha", SUITE_OK)
        self.assertIn("run_all : 4 suites à la fois", self.lancer("alpha", PATH=self.faux_sysctl("", code=1, getconf=("8", 0))).stdout)
        self.assertIn("run_all : 4 suites à la fois", self.lancer("alpha", PATH=self.faux_sysctl("beaucoup", getconf=("8", 0))).stdout)
        self.assertNotIn("suites à la fois", self.lancer("alpha", PATH=self.faux_sysctl("", code=1, getconf=("rien", 0))).stdout)
        # sysctl lisible : getconf n'est pas consulté (rien ne change sur le Mac)
        self.assertIn("run_all : 3 suites à la fois", self.lancer("alpha", PATH=self.faux_sysctl("6", getconf=("16", 0))).stdout)

    # Liste en série et chevauchements (D20)

    def test_deux_suites_se_chevauchent_avec_deux_taches_et_pas_avec_une(self):
        self.suites_notees("alpha", "beta", duree=2.0)
        deux = self.lancer("alpha", "beta", RUN_ALL_JOBS="2")
        self.assertEqual(deux.returncode, 0, deux.stdout)
        self.assertTrue(self.se_chevauchent("alpha", "beta"))
        un = self.lancer("alpha", "beta", RUN_ALL_JOBS="1")
        self.assertEqual(un.returncode, 0, un.stdout)
        self.assertFalse(self.se_chevauchent("alpha", "beta"))

    def test_une_suite_en_serie_ne_chevauche_jamais_une_autre_et_passe_apres_toutes_les_autres(self):
        self.suites_notees("alpha", "beta", "run_all", duree=1.5)
        self.shell("db_scripts/test_dbtest.sh", shell_note(self.notes, "dbtest", 1))
        self.shell("hooks/test_pre_commit.sh", shell_note(self.notes, "hooks", 1))
        resultat = self.lancer("alpha", "beta", "run_all", "dbtest", "hooks", RUN_ALL_JOBS="4")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("puis en série : run_all, dbtest", resultat.stdout)
        for autre in ("alpha", "beta", "hooks"):
            self.assertFalse(self.se_chevauchent("run_all", autre), autre)
            self.assertFalse(self.se_chevauchent("dbtest", autre), autre)
            self.assertLessEqual(self.intervalle(autre)[1], self.intervalle("run_all")[0], autre)
        self.assertFalse(self.se_chevauchent("run_all", "dbtest"))
        self.assertLessEqual(self.intervalle("run_all")[1], self.intervalle("dbtest")[0])
        self.assertTrue(self.se_chevauchent("alpha", "beta"))   # et les autres, elles, tournent ensemble
        lignes = [l.split()[0] for l in resultat.stdout.splitlines() if self.LIGNE_DE_SUITE.match(l)]
        self.assertEqual(lignes, ["alpha", "beta", "run_all", "hooks", "dbtest"])   # ordre de déclaration

    def test_avec_la_base_jetable_chaque_suite_tourne_seule(self):
        self.suites_notees("alpha", "beta", duree=1.0)
        resultat = self.lancer("alpha", "beta", RUN_ALL_JOBS="4", DBTEST_PORT="55432")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertFalse(self.se_chevauchent("alpha", "beta"))
        self.assertNotIn("suites à la fois", resultat.stdout)

    def test_la_plus_longue_suite_declaree_part_dans_la_premiere_vague_mais_pas_avec_une_tache(self):
        self.suites_notees("alpha", "beta", "script_dependencies", duree=2.0)
        resultat = self.lancer("alpha", "beta", "script_dependencies", RUN_ALL_JOBS="2")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertLess(self.intervalle("script_dependencies")[0], self.intervalle("beta")[0])   # alpha et elle d'abord, beta ensuite
        lignes = [l.split()[0] for l in resultat.stdout.splitlines() if self.LIGNE_DE_SUITE.match(l)]
        self.assertEqual(lignes, ["alpha", "beta", "script_dependencies"])   # mais les lignes restent dans l'ordre de déclaration
        un = self.lancer("alpha", "beta", "script_dependencies", RUN_ALL_JOBS="1")                  # une tâche : ordre d'aujourd'hui
        self.assertEqual(un.returncode, 0, un.stdout)
        self.assertLess(self.intervalle("alpha")[0], self.intervalle("script_dependencies")[0])

    # Isolement (D21)

    def test_chaque_suite_a_son_tmpdir_et_le_bytecode_coupe_en_parallele_comme_en_serie(self):
        for taches in ("1", "3"):
            with self.subTest(taches=taches):
                shutil.rmtree(self.notes)
                shutil.rmtree(self.racine)
                self.notes.mkdir()
                self.racine.mkdir()
                self.suites_notees("alpha", "beta")
                self.shell("hooks/test_pre_commit.sh", shell_note(self.notes, "hooks"))
                resultat = self.lancer("alpha", "beta", "hooks", RUN_ALL_JOBS=taches)
                self.assertEqual(resultat.returncode, 0, resultat.stdout)
                vues = {nom: self.lire(nom, "env").splitlines() for nom in ("alpha", "beta", "hooks")}
                dossiers = {v[0] for v in vues.values()}
                self.assertEqual(len(dossiers), 3, vues)
                for nom, (dossier, bytecode, existait) in vues.items():
                    self.assertEqual(bytecode, "1", nom)
                    self.assertEqual(existait, "True", nom)
                    self.assertNotEqual(Path(dossier), self.tmp_lanceur, nom)
                    self.assertFalse(Path(dossier).exists(), f"{nom} : son TMPDIR est encore là après le passage")
                self.assertEqual(list(self.tmp_lanceur.iterdir()), [], "le lanceur laisse des fichiers temporaires")

    def test_le_tmpdir_d_une_suite_ne_contient_pas_run_all(self):
        # tests/install_lab/test_check.py refuse tout appel contenant « run_all » : le dossier d'une suite ne doit pas le porter
        self.suites_notees("alpha")
        resultat = self.lancer("alpha", RUN_ALL_JOBS="1")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertNotIn("run_all", self.lire("alpha", "env").splitlines()[0])

    # Sortie ordonnée, durées, clé de suite (D22)

    def test_les_lignes_sortent_des_que_la_suite_et_les_precedentes_ont_fini(self):
        self.suite("alpha", SUITE_OK)
        self.suite("beta", SUITE_DORT)
        processus = subprocess.Popen(["bash", str(RUN_ALL), "alpha", "beta"], env=self.env(RUN_ALL_JOBS="2", RUN_ALL_SUITE_TIMEOUT="8"),
                                     stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.addCleanup(processus.kill)
        self.addCleanup(processus.stdout.close)
        lues = []
        for ligne in iter(processus.stdout.readline, ""):
            lues.append(ligne)
            if ligne.startswith("alpha"):
                break
        self.assertTrue(lues and lues[-1].startswith("alpha"), lues)
        self.assertIsNone(processus.poll(), "la ligne de alpha doit sortir avant la fin de beta")
        processus.stdout.read()
        processus.wait(timeout=30)

    def test_la_sortie_complete_suit_la_ligne_de_sa_suite(self):
        self.suites_notees("alpha", "beta", duree=0.5)
        sortie = self.lancer("-v", "alpha", "beta", RUN_ALL_JOBS="2").stdout
        i_alpha = sortie.index("alpha  ")
        i_ran = sortie.index("Ran 2 tests", i_alpha)
        self.assertLess(i_ran, sortie.index("beta  "))

    def test_un_nom_python_et_un_nom_shell_identiques_tournent_et_apparaissent_tous_les_deux(self):
        self.suite("offsite_backup", SUITE_OK)
        self.shell("offsite_backup/test_offsite_backup.sh", 'echo "5 réussis, 0 échec(s)"\n')
        durees = self.notes / "durees.tsv"
        resultat = self.lancer("offsite_backup", RUN_ALL_JOBS="3", RUN_ALL_DURATIONS=str(durees))
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertRegex(resultat.stdout, r"offsite_backup\s+2 tests · OK")
        self.assertRegex(resultat.stdout, r"offsite_backup \(shell\)\s+5 tests · OK")
        self.assertIn("TOTAL : 7 tests dans 2 suites", resultat.stdout)
        lignes = durees.read_text(encoding="utf-8").splitlines()[1:]
        self.assertEqual([(l.split("\t")[4], l.split("\t")[5]) for l in lignes], [("offsite_backup", "python"), ("offsite_backup", "shell")])

    def test_le_fichier_des_durees_a_une_ligne_par_suite_dans_l_ordre_des_lignes(self):
        self.suite("alpha", suite_notee(self.notes, "alpha", 2.0))
        self.suite("beta", SUITE_OK)
        self.shell("hooks/test_pre_commit.sh", SHELL_OK)
        durees = self.notes / "durees.tsv"
        resultat = self.lancer("alpha", "beta", "hooks", RUN_ALL_JOBS="3", RUN_ALL_DURATIONS=str(durees))
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        lignes = durees.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lignes), 4)
        champs = [l.split("\t") for l in lignes[1:]]
        self.assertEqual([c[4] for c in champs], ["alpha", "beta", "hooks"])
        self.assertEqual({c[8] for c in champs}, {"ok"})
        self.assertEqual(len({c[1] for c in champs}), 1)
        self.assertGreaterEqual(float(champs[0][6]), 2.0)
        self.assertLess(float(champs[1][6]), float(champs[0][6]))    # sa durée propre, pas l'attente de la suite qui la précède

    # Interruption (D23)

    def test_une_interruption_ne_laisse_aucun_processus_de_suite_ni_fichier_temporaire(self):
        for signal_envoye in (signal.SIGTERM, signal.SIGINT):
            with self.subTest(signal=signal_envoye.name):
                notes = self.notes / signal_envoye.name
                notes.mkdir()
                for nom in ("alpha", "beta"):
                    dossier = self.racine / "tests" / nom
                    dossier.mkdir(parents=True, exist_ok=True)
                    (dossier / f"test_{nom}.py").write_text(
                        "import os, subprocess, unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n"
                        f"        open({str(notes / (nom + '.pid'))!r}, 'w').write(str(os.getpid()))\n"
                        "        p = subprocess.Popen(['sleep', '300'])\n"
                        f"        open({str(notes / (nom + '.fils'))!r}, 'w').write(str(p.pid))\n"
                        "        p.wait()\n")
                subprocess.run(["git", "init", "-q"], cwd=self.racine, check=True)
                processus = subprocess.Popen(["bash", str(RUN_ALL), "alpha", "beta"], env=self.env(RUN_ALL_JOBS="3"),
                                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                             # un lanceur parti en arrière-plan d'un shell sans contrôle de tâches hérite de SIGINT ignoré :
                                             # le test pose SIGINT par défaut, comme dans un terminal
                                             preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL))
                self.addCleanup(processus.kill)
                self.addCleanup(processus.stdout.close)
                debut = time.time()
                while time.time() - debut < 30 and len(list(notes.glob("*.fils"))) < 2:
                    time.sleep(0.1)
                pids = [int(p.read_text()) for p in [*notes.glob("*.pid"), *notes.glob("*.fils")]]
                self.addCleanup(lambda pids=pids: [os.kill(p, 9) for p in pids if self.vivant(p)])   # jamais d'orphelin après un test rouge
                self.assertEqual(len(pids), 4, "les deux suites doivent tourner ensemble avant l'interruption")
                processus.send_signal(signal_envoye)
                processus.wait(timeout=30)
                self.assertEqual(processus.returncode, -signal_envoye)              # sort comme un lanceur interrompu aujourd'hui
                debut = time.time()
                vivants = pids
                while vivants and time.time() - debut < 10:
                    vivants = [p for p in vivants if self.vivant(p)]
                    time.sleep(0.1)
                for pid in vivants:
                    os.kill(pid, 9)
                self.assertEqual(vivants, [], "des processus de suite tournent encore après l'interruption")
                self.assertEqual(list(self.tmp_lanceur.iterdir()), [], "le lanceur laisse des fichiers temporaires")
                self.assertFalse((self.racine / ".git" / "pmzilla-run-all-ok").exists())

    @staticmethod
    def vivant(pid):
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False

    # Empreintes, codes, délai, lancement ciblé inchangés

    def depot_complet(self):
        for chemin in re.findall(r"(tests/\S+\.sh):", RUN_ALL.read_text(encoding="utf-8")):
            self.shell(chemin[len("tests/"):], SHELL_OK)
        subprocess.run(["git", "init", "-q"], cwd=self.racine, check=True)
        subprocess.run(["git", "add", "-A"], cwd=self.racine, check=True)

    def test_empreinte_complete_ecrite_apres_un_passage_parallele_vert_et_pas_apres_un_rouge(self):
        self.suite("alpha", SUITE_OK)
        self.suite("beta", SUITE_OK)
        self.depot_complet()
        empreinte = self.racine / ".git" / "pmzilla-run-all-ok"
        vert = self.lancer(RUN_ALL_JOBS="4")
        self.assertEqual(vert.returncode, 0, vert.stdout)
        self.assertEqual(empreinte.read_text().strip(),
                         subprocess.run(["git", "write-tree"], cwd=self.racine, capture_output=True, text=True).stdout.strip())
        self.suite("casse", SUITE_KO)
        subprocess.run(["git", "add", "-A"], cwd=self.racine, check=True)
        rouge = self.lancer(RUN_ALL_JOBS="4")
        self.assertEqual(rouge.returncode, 1, rouge.stdout)
        self.assertFalse(empreinte.exists())
        self.assertIn("1 suite(s) en échec : casse", rouge.stdout)
        self.assertRegex(rouge.stdout, r"alpha\s+2 tests · OK")

    def test_delai_depasse_en_parallele_nomme_la_suite_et_ne_laisse_aucun_processus(self):
        self.suite("lente", SUITE_FILS)
        self.suite("alpha", SUITE_OK)
        fichier = self.notes / "fils.pid"
        resultat = self.lancer("lente", "alpha", RUN_ALL_JOBS="2", RUN_ALL_SUITE_TIMEOUT="2", FILS_PID=str(fichier))
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertRegex(resultat.stdout, r"lente\s+\? tests · ÉCHEC : délai dépassé \(2 s\)")
        self.assertRegex(resultat.stdout, r"alpha\s+2 tests · OK")
        self.assertIn("lente (délai dépassé)", resultat.stdout.splitlines()[-1])
        pid = int(fichier.read_text())
        if self.vivant(pid):
            os.kill(pid, 9)
            self.fail("le processus fils de la suite arrêtée tourne encore")

    def test_lancement_cible_avec_plusieurs_taches(self):
        for nom in ("alpha", "beta"):
            self.suite(nom, SUITE_OK)
        self.depot_complet()
        subprocess.run(["git", "-c", "user.email=t@example.org", "-c", "user.name=test", "commit", "-q", "-m", "base"], cwd=self.racine,
                       check=True)
        (self.racine / "tests" / "alpha" / "test_alpha.py").write_text(SUITE_OK + "\n")
        subprocess.run(["git", "add", "tests/alpha/test_alpha.py"], cwd=self.racine, check=True)
        resultat = self.lancer("--staged", RUN_ALL_JOBS="3")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertRegex(resultat.stdout, r"alpha\s+2 tests · OK")
        self.assertNotRegex(resultat.stdout, r"beta\s+2 tests")
        self.assertTrue((self.racine / ".git" / "pmzilla-run-targeted-ok").exists())


class ListeEnSerie(unittest.TestCase):
    """Test-speed-2, D20 : chaque entrée de la liste en série du lanceur nomme une suite qui existe, du genre dit, avec sa raison."""

    TEXTE = RUN_ALL.read_text(encoding="utf-8")

    def entrees(self):
        bloc = re.search(r"^EN_SERIE=\(\n(.*?)^\)", self.TEXTE, re.M | re.S)
        self.assertIsNotNone(bloc, "le lanceur doit déclarer EN_SERIE=( … )")
        return re.findall(r"^\s*(\w+):(python|shell)\s*(#.*)?$", bloc.group(1), re.M)

    def test_la_liste_contient_au_moins_run_all_et_dbtest(self):
        entrees = {(nom, genre) for nom, genre, _ in self.entrees()}
        self.assertLessEqual({("run_all", "python"), ("dbtest", "shell")}, entrees)

    def test_chaque_entree_nomme_une_suite_existante_du_genre_dit(self):
        racine = RUN_ALL.parents[1]
        shells = dict((m[1], m[0]) for m in re.findall(r"(tests/\S+\.sh):(\w[\w-]*):", self.TEXTE))
        for nom, genre, _ in self.entrees():
            if genre == "python":
                self.assertTrue(list((racine / "tests" / nom).glob("test_*.py")), f"{nom} : aucune suite Python de ce nom")
            else:
                self.assertIn(nom, shells, f"{nom} : aucune suite shell de ce nom dans la liste du lanceur")
                self.assertTrue((racine / shells[nom]).is_file(), shells.get(nom))

    def test_chaque_entree_porte_sa_raison_en_commentaire(self):
        for nom, genre, raison in self.entrees():
            self.assertGreater(len(raison.lstrip("# ").strip()), 10, f"{nom}:{genre} sans raison")

    def test_pas_d_entree_en_double(self):
        paires = [(nom, genre) for nom, genre, _ in self.entrees()]
        self.assertEqual(len(paires), len(set(paires)))


LISTE_MAC = "tests/suites_mac.txt"
LIGNE_MAC = re.compile(r"^([\w-]+):(python|shell)\s*(?:#(.*))?$")


def defauts_liste_mac(texte: str, racine: Path, lanceur: str) -> list:
    """Défauts de la liste des suites propres au Mac (local-ci-container, D3) : entrée d'une suite absente de ce genre, ligne sans raison,
    ligne illisible, entrée en double. Chaque défaut nomme la ligne ou l'entrée."""
    shells = dict((m[1], m[0]) for m in re.findall(r"(tests/\S+\.sh):(\w[\w-]*):", lanceur))
    defauts, vues = [], set()
    for ligne in texte.splitlines():
        brute = ligne.strip()
        if not brute or brute.startswith("#"):
            continue
        m = LIGNE_MAC.match(brute)
        if not m:
            defauts.append(f"ligne illisible : {brute}")
            continue
        nom, genre, raison = m.group(1), m.group(2), (m.group(3) or "").strip()
        entree = f"{nom}:{genre}"
        if not raison:
            defauts.append(f"sans raison : {brute}")
        if entree in vues:
            defauts.append(f"en double : {entree}")
        vues.add(entree)
        if genre == "python":
            if not list((racine / "tests" / nom).glob("test_*.py")):
                defauts.append(f"suite absente : {entree}")
        elif nom not in shells or not (racine / shells[nom]).is_file():
            defauts.append(f"suite absente : {entree}")
    return defauts


class ListeDesSuitesMac(unittest.TestCase):
    """Local-ci-container, D3 : tests/suites_mac.txt nomme des suites qui existent, du genre dit, une fois chacune, avec leur raison ;
    toute suite shell du lanceur y figure (propre au Mac par défaut)."""

    LANCEUR = RUN_ALL.read_text(encoding="utf-8")

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)
        (self.racine / "tests" / "alpha").mkdir(parents=True)
        (self.racine / "tests" / "alpha" / "test_alpha.py").write_text(SUITE_OK)
        (self.racine / "tests" / "hooks").mkdir(parents=True)
        (self.racine / "tests" / "hooks" / "test_pre_commit.sh").write_text(SHELL_OK)

    def test_liste_du_depot_sans_defaut(self):
        texte = (RUN_ALL.parents[1] / LISTE_MAC).read_text(encoding="utf-8")
        self.assertEqual(defauts_liste_mac(texte, RUN_ALL.parents[1], self.LANCEUR), [])

    def test_toute_suite_shell_du_lanceur_est_dans_la_liste(self):
        texte = (RUN_ALL.parents[1] / LISTE_MAC).read_text(encoding="utf-8")
        entrees = {f"{m.group(1)}:{m.group(2)}" for m in (LIGNE_MAC.match(l.strip()) for l in texte.splitlines()) if m}
        shells = re.findall(r"tests/\S+\.sh:(\w[\w-]*):", self.LANCEUR)
        self.assertEqual([s for s in shells if f"{s}:shell" not in entrees], [])

    def test_la_liste_contient_ci_local_lock_hooks_et_watch_sh(self):
        texte = (RUN_ALL.parents[1] / LISTE_MAC).read_text(encoding="utf-8")
        for entree in ("ci_local:shell", "lock-hooks:shell", "watch_sh:python"):
            self.assertRegex(texte, rf"(?m)^{re.escape(entree)}\s*#")

    def test_fixture_valide_sans_defaut(self):
        texte = "# commentaire\n\nalpha:python # raison de l'entrée\nhooks:shell # outils BSD et bash 3.2 du Mac\n"
        self.assertEqual(defauts_liste_mac(texte, self.racine, self.LANCEUR), [])

    def test_fixture_suite_absente_nommee(self):
        texte = "beta:python # raison\nhooks:python # raison\ninconnue:shell # raison\n"
        self.assertEqual(defauts_liste_mac(texte, self.racine, self.LANCEUR),
                         ["suite absente : beta:python", "suite absente : hooks:python", "suite absente : inconnue:shell"])

    def test_fixture_sans_raison_nommee(self):
        for ligne in ("alpha:python", "alpha:python #", "alpha:python #   "):
            self.assertEqual(defauts_liste_mac(ligne + "\n", self.racine, self.LANCEUR), [f"sans raison : {ligne.strip()}"], ligne)

    def test_fixture_entree_en_double_nommee(self):
        texte = "alpha:python # une\nalpha:python # deux\n"
        self.assertEqual(defauts_liste_mac(texte, self.racine, self.LANCEUR), ["en double : alpha:python"])

    def test_fixture_ligne_illisible_nommee(self):
        self.assertEqual(defauts_liste_mac("alpha # raison\n", self.racine, self.LANCEUR), ["ligne illisible : alpha # raison"])


class SuitesPortablesEtMac(unittest.TestCase):
    """Local-ci-container, D3 : --portable lance les suites absentes de tests/suites_mac.txt après la ligne des suites non lancées,
    --mac seulement les suites listées ; ni l'un ni l'autre n'écrit ou n'efface d'empreinte ; --staged ou un nom de suite : code 2."""

    LISTE = "# suites propres au Mac\n\nbeta:python # raison de beta\nhooks:shell # outils BSD et bash 3.2 du Mac\n"

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)
        for nom in ("alpha", "beta"):
            (self.racine / "tests" / nom).mkdir(parents=True)
            (self.racine / "tests" / nom / f"test_{nom}.py").write_text(SUITE_OK)
        for chemin in re.findall(r"(tests/\S+\.sh):", RUN_ALL.read_text(encoding="utf-8")):
            cible = self.racine / chemin
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_text(SHELL_OK)
        (self.racine / LISTE_MAC).write_text(self.LISTE)
        self.git("init", "-q")
        self.git("add", "-A")

    def git(self, *arguments):
        return subprocess.run(["git", *arguments], cwd=self.racine, capture_output=True, text=True, check=True).stdout.strip()

    def lancer(self, *arguments, **variables):
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS", "DBTEST_PORT")}
        env.update({"RUN_ALL_ROOT": str(self.racine), "RUN_ALL_DEPS": "", "RUN_ALL_JOBS": "1"}, **variables)
        return subprocess.run(["bash", str(RUN_ALL), *arguments], env=env, capture_output=True, text=True, timeout=120,
                              stdin=subprocess.DEVNULL)

    def empreintes(self):
        return [self.racine / ".git" / "pmzilla-run-all-ok", self.racine / ".git" / "pmzilla-run-targeted-ok"]

    @staticmethod
    def lancees(sortie):
        return re.findall(r"(?m)^(\S+(?: \(shell\))?)\s+(?:\d+|\?) tests · ", sortie)

    def test_portable_saute_les_suites_listees_et_les_nomme_avant_la_premiere_suite(self):
        resultat = self.lancer("--portable")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        lignes = resultat.stdout.splitlines()
        phrase = "run_all : suites propres au Mac non lancées : 2 (beta:python hooks:shell)"
        self.assertIn(phrase, lignes)
        lancees = self.lancees(resultat.stdout)
        self.assertIn("alpha", lancees)
        self.assertNotIn("beta", lancees)
        self.assertNotIn("hooks (shell)", lancees)
        self.assertIn("post-commit (shell)", lancees)
        premiere = next(n for n, l in enumerate(lignes) if re.match(r"^\S+(?: \(shell\))?\s+(?:\d+|\?) tests · ", l))
        self.assertLess(lignes.index(phrase), premiere)

    def test_mac_ne_lance_que_les_suites_listees(self):
        resultat = self.lancer("--mac")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertEqual(sorted(self.lancees(resultat.stdout)), ["beta", "hooks (shell)"])
        self.assertNotIn("suites propres au Mac non lancées", resultat.stdout)

    def test_ni_portable_ni_mac_n_ecrit_d_empreinte(self):
        for option in ("--portable", "--mac"):
            resultat = self.lancer(option)
            self.assertEqual(resultat.returncode, 0, resultat.stdout)
            for empreinte in self.empreintes():
                self.assertFalse(empreinte.exists(), (option, empreinte.name))

    def test_ni_portable_ni_mac_n_efface_d_empreinte(self):
        for empreinte in self.empreintes():
            empreinte.write_text("arbre-ancien\n")
        for option in ("--portable", "--mac"):
            self.assertEqual(self.lancer(option).returncode, 0)
            for empreinte in self.empreintes():
                self.assertEqual(empreinte.read_text(), "arbre-ancien\n", (option, empreinte.name))

    def test_combinaisons_refusees_en_2_sans_suite(self):
        for arguments in (("--portable", "--staged"), ("--mac", "--staged"), ("--staged", "--mac"), ("--portable", "alpha"),
                          ("alpha", "--mac"), ("--portable", "--mac")):
            resultat = self.lancer(*arguments)
            self.assertEqual(resultat.returncode, 2, (arguments, resultat.stdout))
            self.assertNotIn("TOTAL", resultat.stdout, arguments)
            self.assertEqual(self.lancees(resultat.stdout), [], arguments)

    def test_liste_absente_refusee_en_2(self):
        (self.racine / LISTE_MAC).unlink()
        for option in ("--portable", "--mac"):
            resultat = self.lancer(option)
            self.assertEqual(resultat.returncode, 2, (option, resultat.stdout))
            self.assertIn("run_all : liste des suites propres au Mac illisible (tests/suites_mac.txt)", resultat.stdout)
            self.assertEqual(self.lancees(resultat.stdout), [], option)

    def test_sans_option_la_liste_ne_change_rien(self):
        resultat = self.lancer()
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("beta", self.lancees(resultat.stdout))
        self.assertIn("hooks (shell)", self.lancees(resultat.stdout))
        self.assertNotIn("suites propres au Mac", resultat.stdout)


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


class GelPendantUneFin(unittest.TestCase):
    """Change multi-session-piloting (D7, tâche 5.3) : le lanceur refuse de démarrer (code 4) tant qu'un autre processus tient le verrou de
    fin de branche du dossier Git commun de sa racine ; jeton égal ou verrou périmé : rien ne change ; le lanceur ne touche jamais au verrou."""

    PHRASE = "run_all : fin de branche en cours (feat/autre), lancement refusé"

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
        self.durees = self.racine.parent / (self.racine.name + "-durees.tsv")
        self.addCleanup(lambda: self.durees.unlink(missing_ok=True))
        self.lock = self.racine / ".git" / "pmzilla-fin-en-cours"

    def git(self, *arguments):
        return subprocess.run(["git", *arguments], cwd=self.racine, capture_output=True, text=True, check=True).stdout.strip()

    def poser_verrou(self, pid=None, jeton="jeton-de-test", dossier=None):
        lock = dossier or self.lock
        lock.mkdir(parents=True, exist_ok=True)
        (lock / "pid").write_text(f"{os.getpid() if pid is None else pid}\n")
        (lock / "debut").write_text(f"{int(time.time())}\n")
        (lock / "branche").write_text("feat/autre\n")
        (lock / "jeton").write_text(jeton + "\n")

    def etat_verrou(self):
        return {p.name: p.read_text() for p in sorted(self.lock.iterdir())} if self.lock.is_dir() else None

    def lancer(self, *arguments, jeton=None, **variables):
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS", "FINISH_LOCK_TOKEN",
                                                                  "PMZILLA_FINISH_LOCK_MAX_AGE")}
        if jeton is not None:
            env["FINISH_LOCK_TOKEN"] = jeton
        env.update({"RUN_ALL_ROOT": str(self.racine), "RUN_ALL_DEPS": "", "RUN_ALL_DURATIONS": str(self.durees)}, **variables)
        return subprocess.run(["bash", str(RUN_ALL), *arguments], env=env, capture_output=True, text=True, timeout=120)

    def empreintes(self):
        return {n: (self.racine / ".git" / n).read_text() if (self.racine / ".git" / n).exists() else None
                for n in ("pmzilla-run-all-ok", "pmzilla-run-targeted-ok")}

    def verifier_refus(self, resultat):
        self.assertEqual(resultat.returncode, 4, resultat.stdout)
        self.assertIn(self.PHRASE, resultat.stdout + resultat.stderr)
        self.assertNotIn("alpha", resultat.stdout.replace(self.PHRASE, ""))
        self.assertNotIn("TOTAL", resultat.stdout)
        self.assertFalse(self.durees.exists())

    def test_lancement_filtre_refuse(self):
        self.poser_verrou()
        avant = self.empreintes()
        self.verifier_refus(self.lancer("alpha"))
        self.assertEqual(self.empreintes(), avant)

    def test_lancement_complet_refuse_sans_effacer_ni_ecrire_d_empreinte(self):
        (self.racine / ".git" / "pmzilla-run-all-ok").write_text("ancienne-empreinte\n")
        (self.racine / ".git" / "pmzilla-run-targeted-ok").write_text("ancienne-ciblee\n")
        self.poser_verrou()
        avant = self.empreintes()
        self.verifier_refus(self.lancer())
        self.assertEqual(self.empreintes(), avant)
        self.assertEqual(avant["pmzilla-run-all-ok"], "ancienne-empreinte\n")

    def test_lancement_cible_refuse_sans_effacer_ni_ecrire_d_empreinte(self):
        (self.racine / ".git" / "pmzilla-run-targeted-ok").write_text("ancienne-ciblee\n")
        (self.racine / ".git" / "pmzilla-run-all-ok").write_text("ancienne-empreinte\n")
        self.poser_verrou()
        avant = self.empreintes()
        self.verifier_refus(self.lancer("--staged"))
        self.assertEqual(self.empreintes(), avant)

    def test_jeton_different_ou_absent_refuse(self):
        self.poser_verrou()
        self.verifier_refus(self.lancer("alpha", jeton="un-autre-jeton"))
        self.verifier_refus(self.lancer("alpha"))

    def test_jeton_de_la_fin_rien_ne_change(self):
        self.poser_verrou()
        resultat = self.lancer("alpha", jeton="jeton-de-test")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("TOTAL : 2 tests dans 1 suites · tous réussis", resultat.stdout)
        self.assertNotIn("fin de branche en cours", resultat.stdout)
        self.assertNotIn("périmé", resultat.stdout)

    def test_jeton_de_la_fin_lancement_complet_ecrit_l_empreinte(self):
        self.poser_verrou()
        resultat = self.lancer(jeton="jeton-de-test")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertEqual(self.empreintes()["pmzilla-run-all-ok"].strip(), self.git("write-tree"))

    def test_verrou_perime_ignore_et_dit(self):
        mort = subprocess.Popen(["true"])
        mort.wait()
        self.poser_verrou(pid=mort.pid)
        resultat = self.lancer("alpha")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("run_all : verrou de fin périmé, ignoré", resultat.stdout)
        self.assertIn("TOTAL : 2 tests dans 1 suites · tous réussis", resultat.stdout)

    def test_verrou_trop_vieux_ignore(self):
        self.poser_verrou()
        (self.lock / "debut").write_text(f"{int(time.time()) - 500}\n")
        resultat = self.lancer("alpha", PMZILLA_FINISH_LOCK_MAX_AGE="10")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("verrou de fin périmé, ignoré", resultat.stdout)

    def test_le_verrou_n_est_jamais_touche(self):
        self.poser_verrou()
        avant = self.etat_verrou()
        self.lancer("alpha")
        self.lancer("alpha", jeton="jeton-de-test")
        self.lancer()
        self.assertEqual(self.etat_verrou(), avant)
        mort = subprocess.Popen(["true"])
        mort.wait()
        self.poser_verrou(pid=mort.pid)
        avant = self.etat_verrou()
        self.lancer("alpha")
        self.assertEqual(self.etat_verrou(), avant)

    def test_racine_injectee_sans_verrou_pendant_que_un_autre_depot_en_tient_un(self):
        autre = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, autre, True)
        subprocess.run(["git", "init", "-q", str(autre)], check=True, capture_output=True)
        self.poser_verrou(dossier=autre / ".git" / "pmzilla-fin-en-cours")
        resultat = self.lancer("alpha")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertNotIn("fin de branche en cours", resultat.stdout)

    def test_depot_lie_lit_le_verrou_du_dossier_git_commun(self):
        lie = self.racine.parent / (self.racine.name + "-lie")
        self.addCleanup(shutil.rmtree, lie, True)
        self.git("-c", "user.email=t@example.org", "-c", "user.name=test", "commit", "-q", "-m", "base")
        self.git("worktree", "add", "-q", "-b", "autre", str(lie))
        self.poser_verrou()
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_NO_EVALS", "FINISH_LOCK_TOKEN")}
        env.update({"RUN_ALL_ROOT": str(lie), "RUN_ALL_DEPS": "", "RUN_ALL_DURATIONS": str(self.durees)})
        resultat = subprocess.run(["bash", str(RUN_ALL), "alpha"], env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(resultat.returncode, 4, resultat.stdout)
        self.assertIn(self.PHRASE, resultat.stdout)

    def test_le_texte_du_lanceur_ne_cree_ni_ne_retire_le_verrou(self):
        texte = RUN_ALL.read_text(encoding="utf-8")
        code = "\n".join(l for l in texte.splitlines() if not l.lstrip().startswith("#"))
        for motif in (r"mkdir[^\n]*fin-en-cours", r"rm[^\n]*fin-en-cours", r"rmdir[^\n]*fin-en-cours", r"mv[^\n]*fin-en-cours", r">\s*[^\n]*fin-en-cours"):
            self.assertIsNone(re.search(motif, code), motif)


class GardeBytecode(unittest.TestCase):
    """Un outil lancé avec sys.executable dans un env= reconstruit perd PYTHONDONTWRITEBYTECODE (posé par run_all.sh)
    et écrit tools/__pycache__ : l'appel doit passer -B en deuxième élément (#316)."""

    APPELS = {"run", "Popen", "check_output", "check_call", "call"}
    CIBLE = re.compile(r"TOOLS|OUTILS|tools/|\bSCRIPT\b")

    def _fautifs(self, chemin: Path) -> list[str]:
        arbre = ast.parse(chemin.read_text(encoding="utf-8"), filename=str(chemin))
        trouves = []
        for noeud in ast.walk(arbre):
            if not (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute)
                    and noeud.func.attr in self.APPELS and noeud.args and isinstance(noeud.args[0], ast.List)):
                continue
            elements = noeud.args[0].elts
            if not elements or not (isinstance(elements[0], ast.Attribute) and elements[0].attr == "executable"
                                    and isinstance(elements[0].value, ast.Name) and elements[0].value.id == "sys"):
                continue
            if not any(self.CIBLE.search(ast.unparse(e)) for e in elements[1:]):
                continue
            if not any(k.arg == "env" for k in noeud.keywords):
                continue
            deuxieme = elements[1] if len(elements) > 1 else None
            if not (isinstance(deuxieme, ast.Constant) and deuxieme.value == "-B"):
                trouves.append(f"{chemin}:{noeud.lineno}")
        return trouves

    def test_les_outils_lances_avec_un_env_passent_moins_b(self):
        racine = Path(__file__).resolve().parents[1]
        fautifs = []
        for chemin in sorted(racine.rglob("*.py")):
            if "__pycache__" not in chemin.parts:
                fautifs += self._fautifs(chemin)
        self.assertEqual(fautifs, [], "sys.executable + outil + env= sans -B en deuxième élément : " + ", ".join(fautifs))


if __name__ == "__main__":
    unittest.main()
