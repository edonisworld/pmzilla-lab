"""
tests/run_all.sh garde la sortie de chaque suite rouge (R-20261101-01, Q136 (a)) : un fichier par passage rouge dans un dossier de données
(RUN_ALL_RED_DIR pour ces tests, un faux dossier), rien sur un vert, dix fichiers au plus, et une écriture impossible ne change pas le code de sortie.

    python3 -m unittest discover -s tests/run_all -v

Le lanceur est pointé sur un dossier temporaire (RUN_ALL_ROOT) sans dépendances supplémentaires (RUN_ALL_DEPS vide), comme test_run_all.py.
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

RUN_ALL = Path(__file__).resolve().parents[1] / "run_all.sh"
SUITE_OK = "import unittest\nclass T(unittest.TestCase):\n    def test_a(self): pass\n    def test_b(self): pass\n"
SUITE_KO = ("import unittest\nclass T(unittest.TestCase):\n    def test_a(self): pass\n"
            "    def test_casse(self): self.assertEqual(1, 2)\n")


class SortieDesSuitesRouges(unittest.TestCase):
    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.donnees = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.addCleanup(shutil.rmtree, self.donnees, True)
        self.rouges = self.donnees / "suites-rouges"

    def suite(self, nom, texte):
        dossier = self.racine / "tests" / nom
        dossier.mkdir(parents=True)
        (dossier / f"test_{nom}.py").write_text(texte)

    def lancer(self, *arguments, **variables):
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS", "CLAUDECODE")}
        env.update({"RUN_ALL_ROOT": str(self.racine), "RUN_ALL_DEPS": "", "RUN_ALL_RED_DIR": str(self.rouges)}, **variables)
        return subprocess.run(["bash", str(RUN_ALL), *arguments], env=env, capture_output=True, text=True, timeout=120)

    def fichiers(self):
        return sorted(self.rouges.glob("rouge-*.txt")) if self.rouges.is_dir() else []

    def test_un_passage_rouge_ecrit_une_copie_et_dit_son_chemin(self):
        self.suite("alpha", SUITE_OK)
        self.suite("casse", SUITE_KO)
        resultat = self.lancer("alpha", "casse")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        fichiers = self.fichiers()
        self.assertEqual(len(fichiers), 1, resultat.stdout)
        texte = fichiers[0].read_text(encoding="utf-8")
        self.assertIn("=== casse : ÉCHEC (code 1)", texte)       # nom de la suite et verdict
        self.assertIn("AssertionError", texte)                    # la sortie de la suite rouge
        self.assertIn("mode : filtré", texte)                     # mode du lancement
        self.assertRegex(texte, r"lancement : \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
        self.assertNotIn("=== alpha", texte)                      # la suite verte n'y est pas
        # Racine injectée avec RUN_ALL_RED_DIR : le nom du fichier seul, jamais le chemin absolu (qui contient le nom du compte).
        self.assertIn(f"run_all : sortie des suites rouges gardée : {fichiers[0].name}\n", resultat.stdout)
        self.assertNotIn(str(self.donnees), resultat.stdout)

    def test_un_passage_vert_n_ecrit_rien(self):
        self.suite("alpha", SUITE_OK)
        resultat = self.lancer("alpha")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertEqual(self.fichiers(), [])
        self.assertFalse(self.rouges.exists())
        self.assertNotIn("sortie des suites rouges", resultat.stdout)

    def test_dix_fichiers_au_plus_les_plus_anciens_effaces(self):
        self.suite("casse", SUITE_KO)
        self.rouges.mkdir(parents=True)
        anciens = [self.rouges / f"rouge-2000-01-01T0000{k:02d}-1.txt" for k in range(12)]
        for ancien in anciens:
            ancien.write_text("ancien\n")
        resultat = self.lancer("casse")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        fichiers = self.fichiers()
        self.assertEqual(len(fichiers), 10, [f.name for f in fichiers])
        self.assertTrue(all(not a.exists() for a in anciens[:3]))   # les trois plus anciens sont partis
        self.assertTrue(all(a.exists() for a in anciens[3:]))
        self.assertIn("=== casse", fichiers[-1].read_text(encoding="utf-8"))   # le nouveau est le dernier

    def test_une_ecriture_impossible_ne_change_pas_le_code_de_sortie(self):
        self.suite("casse", SUITE_KO)
        bloc = self.donnees / "bloc"
        bloc.write_text("un fichier, pas un dossier\n")
        resultat = self.lancer("casse", RUN_ALL_RED_DIR=str(bloc / "suites-rouges"))
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertIn("run_all : sortie des suites rouges non gardée (écriture impossible)", resultat.stdout)
        self.assertNotIn("sortie des suites rouges gardée", resultat.stdout)
        self.assertIn("TOTAL : 2 tests dans 1 suites · 1 suite(s) en échec : casse", resultat.stdout)

    def test_sans_la_variable_une_racine_injectee_n_ecrit_rien(self):
        self.suite("casse", SUITE_KO)
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_NO_EVALS", "CLAUDECODE", "RUN_ALL_RED_DIR")}
        env.update({"RUN_ALL_ROOT": str(self.racine), "RUN_ALL_DEPS": "", "PMZILLA_LAB_DATA": str(self.donnees / "lab")})
        resultat = subprocess.run(["bash", str(RUN_ALL), "casse"], env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertNotIn("sortie des suites rouges", resultat.stdout)
        self.assertFalse((self.donnees / "lab").exists())            # aucun dossier créé
        self.assertEqual(list(self.donnees.iterdir()), [])
        self.assertEqual(list(self.racine.rglob("suites-rouges")), [])

    def test_delai_depasse_est_garde_avec_son_etiquette(self):
        self.suite("dort", "import time, unittest\nclass T(unittest.TestCase):\n    def test_a(self): time.sleep(60)\n")
        resultat = self.lancer("dort", RUN_ALL_SUITE_TIMEOUT="1")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        fichiers = self.fichiers()
        self.assertEqual(len(fichiers), 1, resultat.stdout)
        texte = fichiers[0].read_text(encoding="utf-8")
        self.assertIn("=== dort : ÉCHEC : délai dépassé (1 s)", texte)
        self.assertNotIn("ÉCHEC (code", texte)

    def test_script_absent_est_garde_et_ecrit_le_fichier_meme_seul(self):
        self.suite("alpha", SUITE_OK)
        resultat = self.lancer("hooks")   # suite shell listée dans tests/suites_shell.txt, script absent de la racine injectée : la seule rouge
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        fichiers = self.fichiers()
        self.assertEqual(len(fichiers), 1, resultat.stdout)
        self.assertIn("=== hooks (shell) : script absent", fichiers[0].read_text(encoding="utf-8"))


# Même appel que tests/run_all/test_run_all.py (APPEL_GETPWUID) : le lanceur copié lit un faux dossier personnel au lieu de celui du compte.
APPEL_GETPWUID = "/usr/bin/perl -e 'print((getpwuid($<))[7])'"


class DossierParDefaut(unittest.TestCase):
    """Sans RUN_ALL_RED_DIR ni racine injectée : suites-rouges/ sous PMZILLA_LAB_DATA hors session, sous le dossier du compte (faux home) en
    session ; droits 0700 du dossier et 0600 du fichier. Le lanceur est COPIÉ dans une fausse racine, comme dans test_run_all.py."""

    def setUp(self):
        self.base = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.base, True)
        self.racine = self.base / "depot"
        (self.racine / "tests" / "casse").mkdir(parents=True)
        (self.racine / "tests" / "casse" / "test_casse.py").write_text(SUITE_KO)
        (self.racine / "tools").mkdir()
        subprocess.run(["git", "init", "-q", str(self.racine)], check=True, capture_output=True)
        shutil.copy(RUN_ALL.parent / "suites_shell.txt", self.racine / "tests" / "suites_shell.txt")
        # T2 : en session, seules les suites propres au Mac tournent ici ; « casse » en est une, pour que le cas de session lance toujours la suite rouge
        (self.racine / "tests" / "suites_mac.txt").write_text("casse:python # essai : suite propre au Mac\n")
        shutil.copy(RUN_ALL.parents[1] / "tools" / "lab_paths.sh", self.racine / "tools" / "lab_paths.sh")
        self.home = self.base / "home"
        self.home.mkdir()

    def copier(self, session):
        texte = RUN_ALL.read_text(encoding="utf-8")
        if session:
            self.assertIn(APPEL_GETPWUID, texte)
            texte = texte.replace(APPEL_GETPWUID, f"printf %s {str(self.home)!r}")
        self.assertIn("\nSUITES_NPM=(mothra:mothra)\n", texte)
        texte = texte.replace("\nSUITES_NPM=(mothra:mothra)\n", "\nSUITES_NPM=()\n")
        (self.racine / "tests" / "run_all.sh").write_text(texte, encoding="utf-8")

    def lancer(self, session, **variables):
        retirees = ("RUN_ALL_ROOT", "RUN_ALL_RED_DIR", "PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS", "CLAUDECODE",
                    "FINISH_LOCK_TOKEN", "DBTEST_PORT", "PMZILLA_FINISH_LOCK_MAX_AGE", "PMZILLA_LAB_DATA")
        env = {k: v for k, v in os.environ.items() if k not in retirees}
        env.update({"RUN_ALL_DEPS": "", "RUN_ALL_DURATIONS": str(self.base / "durees.tsv")})
        if session:
            env["CLAUDECODE"] = "1"
        env.update(variables)
        return subprocess.run(["bash", str(self.racine / "tests" / "run_all.sh"), "casse"], env=env, cwd=self.racine,
                              capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)

    def test_hors_session_le_dossier_est_sous_le_dossier_de_donnees(self):
        self.copier(session=False)
        contenu = self.base / "contenu"
        contenu.mkdir()
        donnees = self.base / "donnees"
        resultat = self.lancer(False, PMZILLA_LAB_WORKSPACE=str(contenu), PMZILLA_LAB_DATA=str(donnees))
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        rouges = donnees / "suites-rouges"
        fichiers = sorted(rouges.glob("rouge-*.txt"))
        self.assertEqual(len(fichiers), 1, resultat.stdout)
        self.assertEqual(rouges.stat().st_mode & 0o777, 0o700)
        self.assertEqual(fichiers[0].stat().st_mode & 0o777, 0o600)
        self.assertIn("=== casse : ÉCHEC (code 1)", fichiers[0].read_text(encoding="utf-8"))
        self.assertIn(f"run_all : sortie des suites rouges gardée : {fichiers[0].name}\n", resultat.stdout)   # dossier hors compte : nom seul
        self.assertNotIn(str(donnees), resultat.stdout)

    def test_en_session_le_dossier_est_celui_du_compte_et_le_chemin_affiche_est_avec_tilde(self):
        self.copier(session=True)
        resultat = self.lancer(True)
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        rouges = self.home / ".pmzilla-lab" / "suites-rouges"
        fichiers = sorted(rouges.glob("rouge-*.txt"))
        self.assertEqual(len(fichiers), 1, resultat.stdout)
        self.assertEqual(rouges.stat().st_mode & 0o777, 0o700)
        self.assertEqual(fichiers[0].stat().st_mode & 0o777, 0o600)
        self.assertIn(f"run_all : sortie des suites rouges gardée : ~/.pmzilla-lab/suites-rouges/{fichiers[0].name}\n", resultat.stdout)
        self.assertNotIn(str(self.home), resultat.stdout)


if __name__ == "__main__":
    unittest.main()
