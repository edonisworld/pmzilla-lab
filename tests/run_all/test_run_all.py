"""
Tests du lanceur tests/run_all.sh sur un faux dépôt : suites qui réussissent, suite qui échoue, filtre par nom,
tests shell, aucune suite.

    python3 -m unittest discover -s tests/run_all -v

Le lanceur est pointé sur un dossier temporaire (RUN_ALL_ROOT) et sans dépendances supplémentaires (RUN_ALL_DEPS
vide) ; il ne lance jamais les vraies suites.
"""
import ast
import json
import os
import pwd
import re
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

RUN_ALL = Path(__file__).resolve().parents[1] / "run_all.sh"

# Session Claude Code (session-runner, M3 du second regard) : le marqueur CLAUDECODE est retiré de l'environnement de la suite, que chaque
# lanceur copie ; seuls les cas de session (classe SessionClaudeCode) le posent. Sans cela, la suite lancée dans une session verrait le
# lanceur en mode session (code 6 sur une racine injectée) et rougirait en session, verte au Terminal.
os.environ.pop("CLAUDECODE", None)
# La garde des lancements non complets (tools/runner_guard.sh, variables RUN_ALL_GUARD_LOCK et RUN_ALL_GUARD_WAIT) est retirée avec le verrou de session
# (tooling-proof-in-container, T2, R-20261104-7 P2) : ce module ne pose plus de faux verrou.

def empreinte_du_journal_reel():
    """((taille, date) du journal de session, noms des entrées de présence dont le pid est un ENFANT de ce module) du VRAI dossier de données du
    compte ; None pour ce qui n'existe pas : stat et liste de noms seulement, jamais lu. Les entrées des autres lancements (un runner complet
    ou un lancement ciblé d'un agent en même temps) ne comptent pas : seules celles que ce module aurait laissées par un test comptent."""
    reel = Path(pwd.getpwuid(os.getuid()).pw_dir) / ".pmzilla-lab" / "journal"
    try:
        etat = (reel / "run-all-session.tsv").stat()
        session = (etat.st_size, etat.st_mtime_ns)
    except OSError:
        session = None
    enfants = []
    try:
        noms = [p.name for p in (reel / "run-all-presence").iterdir() if p.name.isdigit()]
    except OSError:
        noms = []
    for nom in sorted(noms):
        parent = subprocess.run(["ps", "-o", "ppid=", "-p", nom], capture_output=True, text=True).stdout.strip()
        if parent == str(os.getpid()):
            enfants.append(nom)
    return (session, tuple(enfants))


EMPREINTE_AVANT = None


def setUpModule():
    global EMPREINTE_AVANT
    EMPREINTE_AVANT = empreinte_du_journal_reel()


def tearDownModule():
    """Garde : aucun test de ce module n'écrit dans le vrai dossier de données du compte (le journal de session y recevrait une ligne
    « refusé » ou « lancé » fausse). Un autre lancement complet de session qui tournerait en même temps la ferait aussi échouer : à relancer."""
    apres = empreinte_du_journal_reel()
    if apres != EMPREINTE_AVANT:
        raise AssertionError(f"le journal de session du vrai dossier de données a changé pendant la suite (avant {EMPREINTE_AVANT}, après {apres})")


SUITE_OK = "import unittest\nclass T(unittest.TestCase):\n    def test_a(self): pass\n    def test_b(self): pass\n"
SUITE_KO =("import unittest\nclass T(unittest.TestCase):\n    def test_a(self): pass\n"
            "    def test_casse(self): self.assertEqual(1, 2)\n")
SHELL_OK = 'echo "ok : un"\necho "ok : deux"\necho "2 réussis, 0 échec(s)"\n'
SHELL_KO = 'echo "ECHEC : un"\necho "1 réussis, 1 échec(s)"\nexit 1\n'
FAUX_MOT_DE_PASSE = "faux-mot-" + "de-passe"   # fabriqués à l'exécution : aucun littéral pour la garde des secrets
FAUX_ROLE = "faux-" + "role"
LISTE_SHELL = "tests/suites_shell.txt"


def suites_shell_du_depot():
    """[(chemin, nom, interprète)] de tests/suites_shell.txt, dans l'ordre du fichier (commentaires et lignes vides ignorés)."""
    entrees = []
    for ligne in (RUN_ALL.parent / "suites_shell.txt").read_text(encoding="utf-8").splitlines():
        mots = ligne.split("#", 1)[0].split()
        if mots:
            entrees.append(tuple(mots))
    return entrees


def scripts_shell():
    """Les chemins des scripts de test shell que le lanceur liste (tests/suites_shell.txt)."""
    return [chemin for chemin, _, _ in suites_shell_du_depot()]


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
        listes = scripts_shell()
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
        tests = 4 + 2 * len(listes)   # un faux script par suite shell (le tableau MORCEAUX est retiré, B9) : ses 2 tests comptent une fois chacun
        self.assertIn(f"TOTAL : {tests} tests dans {2 + len(listes)} suites · tous réussis", resultat.stdout)

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

    def test_suite_python_rouge_liste_les_quatre_echecs_avant_l_extrait_de_fin(self):
        cas = "".join(f"    def test_casse{k}(self): self.fail('cause{k}\\n' + 'bruit\\n' * 12)\n" for k in range(1, 4))
        self.suite("casse", "import unittest\nclass T(unittest.TestCase):\n" + cas
                   + "    def test_erreur4(self): raise ValueError('cause4')\n")
        resultat = self.lancer("casse")
        self.assertEqual(resultat.returncode, 1)
        sortie = resultat.stdout
        debut = sortie.index("Tous les échecs de la suite :")
        self.assertLess(debut, sortie.index("Traceback"))          # la liste précède l'extrait de fin
        liste = sortie[debut:sortie.index("Traceback")]
        for k in range(1, 4):
            self.assertRegex(liste, rf"FAIL: test_casse{k} \(.*T.*\)\n\s+AssertionError: cause{k}\n")
        self.assertRegex(liste, r"ERROR: test_erreur4 \(.*T.*\)\n\s+ValueError: cause4\n")

    def test_suite_shell_rouge_liste_les_quatre_echecs_avant_l_extrait_de_fin(self):
        lignes = "".join(f'echo "ECHEC : cas {k}"\n' for k in (1, 2)) + 'echo "not ok 3 - cas 3"\n' + 'echo "ÉCHEC : cas 4"\n'
        self.shell("installation/test_install_links.sh", lignes + 'echo "0 réussis, 4 échec(s)"\nexit 1\n')
        resultat = self.lancer("installation")
        self.assertEqual(resultat.returncode, 1)
        sortie = resultat.stdout
        debut = sortie.index("Tous les échecs de la suite :")
        liste = sortie[debut:sortie.index("0 réussis")]
        for ligne in ("ECHEC : cas 1", "ECHEC : cas 2", "not ok 3 - cas 3", "ÉCHEC : cas 4"):
            self.assertIn(ligne, liste)

    def test_suite_verte_n_affiche_aucune_liste_d_echecs(self):
        self.suite("alpha", SUITE_OK)
        self.assertNotIn("Tous les échecs", self.lancer("alpha").stdout)

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
        for chemin in scripts_shell():
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
        for chemin in scripts_shell():
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
        for chemin in scripts_shell():
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
        shutil.copy(RUN_ALL.parent / "suites_shell.txt", self.racine / "tests" / "suites_shell.txt")
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
        for chemin in scripts_shell():
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
        for chemin in scripts_shell():
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
        self.assertEqual(len(lignes) - 1, 2 + len(scripts_shell()))
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
        shutil.copy(RUN_ALL.parent / "suites_shell.txt", self.racine / "tests" / "suites_shell.txt")
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
        for chemin in scripts_shell():
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
                                                                "DBTEST_PORT", "RUN_ALL_SUITE_TIMEOUT", "PYTHONDONTWRITEBYTECODE",
                                                                "RUN_ALL_DURATIONS")}
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
        # run-all-faster-and-guarded (D1, D2) : les lignes d'ordre et de chevauchement s'ajoutent à la ligne des tâches avec plus d'une tâche
        sans_ligne = [l for l in self.normalise(deux.stdout) if "suites à la fois" not in l and "chevauchement" not in l and "ordre de départ" not in l]
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
        # run-all-faster-and-guarded (D2) : « run_all » peut maintenant chevaucher la fin de la phase en parallèle ; ce test garde le passage en série
        # d'avant, que RUN_ALL_OVERLAP=0 rend (le chevauchement a ses propres tests plus bas, classe ChevauchementDeLaPhaseEnSerie).
        resultat = self.lancer("alpha", "beta", "run_all", "dbtest", "hooks", RUN_ALL_JOBS="4", RUN_ALL_OVERLAP="0")
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
        self.assertEqual(lignes, ["alpha", "beta", "run_all", "dbtest", "hooks"])   # ordre de déclaration (R-130 : chemins triés, db_scripts avant hooks)

    def test_avec_la_base_jetable_chaque_suite_tourne_seule(self):
        self.suites_notees("alpha", "beta", duree=1.0)
        resultat = self.lancer("alpha", "beta", RUN_ALL_JOBS="4", DBTEST_PORT="55432")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertFalse(self.se_chevauchent("alpha", "beta"))
        self.assertNotIn("suites à la fois", resultat.stdout)

    def test_la_plus_longue_suite_declaree_part_dans_la_premiere_vague_mais_pas_avec_une_tache(self):
        self.suites_notees("alpha", "beta", "script_dependencies", duree=2.0)
        durees = self.ecrire_durees({("alpha", "python"): [50], ("beta", "python"): [2], ("script_dependencies", "python"): [90]})   # R-20261029-31 : la plus longue selon les durées mesurées
        resultat = self.lancer("alpha", "beta", "script_dependencies", RUN_ALL_JOBS="2", RUN_ALL_DURATIONS=str(durees))
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertLess(self.intervalle("script_dependencies")[0], self.intervalle("beta")[0])   # alpha et elle d'abord, beta ensuite
        lignes = [l.split()[0] for l in resultat.stdout.splitlines() if self.LIGNE_DE_SUITE.match(l)]
        self.assertEqual(lignes, ["alpha", "beta", "script_dependencies"])   # mais les lignes restent dans l'ordre de déclaration
        un = self.lancer("alpha", "beta", "script_dependencies", RUN_ALL_JOBS="1")                  # une tâche : ordre d'aujourd'hui
        self.assertEqual(un.returncode, 0, un.stdout)
        self.assertLess(self.intervalle("alpha")[0], self.intervalle("script_dependencies")[0])

    # Ordre de départ selon les durées mesurées (run-all-faster-and-guarded, D1, tâche 2.3). Il remplace le test de la liste statique
    # PREMIERES_SUITES (test_les_suites_longues_declarees_partent_en_premier_dans_l_ordre_de_la_liste_mais_pas_avec_une_tache, R-139) : la liste est
    # retirée, la décision R-20261029-29 (change validé) couvre ce remplacement. Les heures de départ ne sont comparées qu'entre elles.

    ENTETE_DUREES = "lancement\tidentifiant\tgenre\tposte\tsuite\ttype\tsecondes\tsecondes_unittest\tverdict\traison\n"

    def ecrire_durees(self, mesures, nom="durees-mesurees.tsv"):
        """Faux fichier des durées : {(suite, type) : [secondes, …]}, une ligne verte d'un passage complet par valeur."""
        lignes = [self.ENTETE_DUREES]
        for (suite, genre), valeurs in mesures.items():
            lignes += [f"2026-10-29T10:00:00\tid\tcomplet\tespace\t{suite}\t{genre}\t{v}\t\tok\t\n" for v in valeurs]
        chemin = self.notes / nom
        chemin.write_text("".join(lignes), encoding="utf-8")
        return chemin

    def debut(self, nom):
        return self.intervalle(nom)[0]

    def test_les_suites_mesurees_partent_par_estimation_decroissante_et_les_lignes_gardent_l_ordre_declare(self):
        self.suites_notees("alpha", "beta", "gamma", duree=1.0)
        durees = self.ecrire_durees({("alpha", "python"): [1, 1, 1], ("beta", "python"): [9, 9, 9], ("gamma", "python"): [5, 5, 5]})
        resultat = self.lancer("alpha", "beta", "gamma", RUN_ALL_JOBS="2", RUN_ALL_DURATIONS=str(durees))
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertLess(self.debut("beta"), self.debut("alpha"))      # la plus longue estimée part avant la plus courte, déclarée avant elle
        self.assertLess(self.debut("gamma"), self.debut("alpha"))     # deux tâches : alpha attend qu'une des deux libère sa place
        lignes = [l.split()[0] for l in resultat.stdout.splitlines() if self.LIGNE_DE_SUITE.match(l)]
        self.assertEqual(lignes, ["alpha", "beta", "gamma"])
        self.assertIn("run_all : ordre de départ selon les durées mesurées (3 suites mesurées, 0 sans mesure)", resultat.stdout)

    def test_une_suite_sans_mesure_part_avant_toutes_les_suites_mesurees(self):
        self.suites_notees("alpha", "beta", "gamma", duree=1.0)
        durees = self.ecrire_durees({("alpha", "python"): [100], ("beta", "python"): [50]})   # gamma : aucune ligne verte d'un passage complet
        resultat = self.lancer("alpha", "beta", "gamma", RUN_ALL_JOBS="2", RUN_ALL_DURATIONS=str(durees))
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertLess(self.debut("gamma"), self.debut("beta"))      # gamma d'abord, puis alpha ; beta attend une place
        self.assertLess(self.debut("alpha"), self.debut("beta"))
        self.assertIn("(2 suites mesurées, 1 sans mesure)", resultat.stdout)

    def test_les_suites_sans_mesure_gardent_entre_elles_l_ordre_declare(self):
        for nom, duree in (("alpha", 1.0), ("beta", 2.0), ("delta", 0.5), ("gamma", 1.0)):
            self.suite(nom, suite_notee(self.notes, nom, duree))
        durees = self.ecrire_durees({("alpha", "python"): [100]})   # beta, delta, gamma sans mesure : d'abord, dans l'ordre déclaré (dossiers triés) ; alpha, mesurée, après
        resultat = self.lancer("alpha", "beta", "delta", "gamma", RUN_ALL_JOBS="2", RUN_ALL_DURATIONS=str(durees))
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        # deux tâches : beta et delta partent ensemble, gamma prend la place de delta (la première libérée), alpha celle de gamma
        self.assertLess(self.debut("delta"), self.debut("gamma"))
        self.assertLess(self.debut("gamma"), self.debut("alpha"))
        self.assertLess(self.debut("beta"), self.debut("alpha"))
        self.assertIn("(1 suites mesurées, 3 sans mesure)", resultat.stdout)

    def test_les_lignes_en_echec_ne_comptent_pas_dans_l_estimation(self):
        self.suites_notees("alpha", "beta", duree=1.0)
        durees = self.ecrire_durees({("alpha", "python"): [1], ("beta", "python"): [2]})
        with durees.open("a", encoding="utf-8") as f:   # une durée énorme, mais rouge : sans effet sur l'ordre
            f.write("2026-10-29T10:00:00\tid\tcomplet\tespace\talpha\tpython\t999\t\téchec\t\n")
        resultat = self.lancer("alpha", "beta", RUN_ALL_JOBS="2", RUN_ALL_DURATIONS=str(durees))
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("(2 suites mesurées, 0 sans mesure)", resultat.stdout)

    def test_ordre_declare_avec_une_tache_ou_la_base_jetable_et_aucune_ligne_d_ordre(self):
        self.suites_notees("alpha", "beta", duree=0.5)
        durees = self.ecrire_durees({("alpha", "python"): [1], ("beta", "python"): [9]})
        for variables in ({"RUN_ALL_JOBS": "1"}, {"RUN_ALL_JOBS": "4", "DBTEST_PORT": "55432"}):
            with self.subTest(variables=variables):
                resultat = self.lancer("alpha", "beta", RUN_ALL_DURATIONS=str(durees), **variables)
                self.assertEqual(resultat.returncode, 0, resultat.stdout)
                self.assertLess(self.debut("alpha"), self.debut("beta"))   # ordre déclaré, malgré une estimation plus longue pour beta
                self.assertNotIn("ordre de départ", resultat.stdout)

    def test_fichier_inutilisable_ordre_declare_et_une_ligne_qui_le_dit(self):
        self.suites_notees("alpha", "beta", duree=0.2)
        absent = self.notes / "absent.tsv"
        vide = self.notes / "vide.tsv"
        vide.write_text("", encoding="utf-8")
        sans_ligne_verte = self.ecrire_durees({}, nom="entete-seul.tsv")
        for fichier in (absent, vide, sans_ligne_verte):
            with self.subTest(fichier=fichier.name):
                resultat = self.lancer("alpha", "beta", RUN_ALL_JOBS="2", RUN_ALL_DURATIONS=str(fichier))
                self.assertEqual(resultat.returncode, 0, resultat.stdout)
                self.assertEqual(resultat.stdout.count("run_all : ordre de départ déclaré (durées indisponibles)"), 1, resultat.stdout)
                self.assertNotIn("selon les durées mesurées", resultat.stdout)

    def test_racine_injectee_sans_variable_des_durees_ordre_declare_sans_ligne(self):
        self.suites_notees("alpha", "beta", duree=0.2)
        resultat = self.lancer("alpha", "beta", RUN_ALL_JOBS="2")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertNotIn("ordre de départ", resultat.stdout)

    def test_la_ligne_d_ordre_est_ecrite_une_fois_avant_la_premiere_suite(self):
        self.suites_notees("alpha", "beta", duree=0.2)
        durees = self.ecrire_durees({("alpha", "python"): [3], ("beta", "python"): [4]})
        resultat = self.lancer("alpha", "beta", RUN_ALL_JOBS="2", RUN_ALL_DURATIONS=str(durees))
        ligne = "run_all : ordre de départ selon les durées mesurées (2 suites mesurées, 0 sans mesure)"
        self.assertEqual(resultat.stdout.count(ligne), 1, resultat.stdout)
        self.assertLess(resultat.stdout.index(ligne), resultat.stdout.index("alpha  "))

    def test_les_durees_de_l_ordre_ne_sont_jamais_ecrites_par_le_calcul_lui_meme(self):
        self.suites_notees("alpha", "beta", duree=0.2)
        durees = self.ecrire_durees({("alpha", "python"): [3], ("beta", "python"): [4]})
        avant = durees.read_text(encoding="utf-8")
        self.lancer("alpha", "beta", RUN_ALL_JOBS="2", RUN_ALL_DURATIONS=str(durees))
        apres = durees.read_text(encoding="utf-8")
        self.assertTrue(apres.startswith(avant))                       # seules les lignes des suites de ce lancement s'ajoutent
        self.assertEqual(len(apres.splitlines()) - len(avant.splitlines()), 2)

    # Le découpage en morceaux est retiré (B9) ; une suite ne reçoit jamais la variable de morceau de l'appelant.

    def test_une_suite_non_decoupee_ne_recoit_jamais_la_variable_de_morceau(self):
        self.shell("hooks/test_pre_commit.sh", f'printf "%s\\n" "${{FINISH_MORCEAU-absent}}" > "{self.notes}/hooks.valeur"\necho "2 réussis, 0 échec(s)"\n')
        resultat = self.lancer("hooks", RUN_ALL_JOBS="2", FINISH_MORCEAU="2/4")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertEqual((self.notes / "hooks.valeur").read_text().strip(), "absent")

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
        for chemin in scripts_shell():
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
        shells = {nom: chemin for chemin, nom, _ in suites_shell_du_depot()}
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


def lignes_du_tableau(texte: str, nom: str):
    """Les lignes utiles (ni vides ni commentaire seul) du tableau bash « NOM=( … ) » de tests/run_all.sh ; None s'il manque."""
    bloc = re.search(rf"^{nom}=\(\n(.*?)^\)", texte, re.M | re.S)
    if bloc is None:
        return None
    return [l for l in bloc.group(1).splitlines() if l.strip() and not l.strip().startswith("#")]


def suite_existe(nom: str, genre: str, racine: Path) -> bool:
    if genre == "python":
        return bool(list((racine / "tests" / nom).glob("test_*.py")))
    chemins = {n: c for c, n, _ in suites_shell_du_depot()}
    return nom in chemins and (racine / chemins[nom]).is_file()


def defauts_sans_chevauchement(texte: str, racine: Path) -> list:
    """Défauts de la liste SANS_CHEVAUCHEMENT (run-all-faster-and-guarded, D2) : entrée mal formée, entrée sans raison, entrée d'une suite
    absente de ce genre, entrée en double. Chaque défaut nomme l'entrée."""
    lignes = lignes_du_tableau(texte, "SANS_CHEVAUCHEMENT")
    if lignes is None:
        return ["tableau SANS_CHEVAUCHEMENT absent"]
    defauts, vues = [], set()
    for ligne in lignes:
        m = re.match(r"^\s*([\w-]+):(python|shell)(?:\s+#\s*(\S.*))?$", ligne)
        if not m:
            defauts.append(f"entrée mal formée : {ligne.strip()}")
            continue
        nom, genre, raison = m.groups()
        if not raison or len(raison.strip()) <= 10:
            defauts.append(f"{nom}:{genre} sans raison")
        if not suite_existe(nom, genre, racine):
            defauts.append(f"{nom}:{genre} : aucune suite de ce nom de ce genre")
        if (nom, genre) in vues:
            defauts.append(f"{nom}:{genre} en double")
        vues.add((nom, genre))
    return defauts


def defauts_modes_en_serie(texte: str) -> list:
    """Défauts de MODE_SERIE : chaque entrée de EN_SERIE a exactement un mode (chevauche ou seule), chaque mode nomme une entrée de EN_SERIE."""
    serie = lignes_du_tableau(texte, "EN_SERIE")
    modes = lignes_du_tableau(texte, "MODE_SERIE")
    if serie is None or modes is None:
        return ["tableau EN_SERIE ou MODE_SERIE absent"]
    entrees = [re.match(r"^\s*([\w-]+):(python|shell)", l).groups() for l in serie]
    defauts, par_suite = [], {}
    for ligne in modes:
        m = re.match(r"^\s*([\w-]+):(python|shell):(chevauche|seule)\s*(#.*)?$", ligne)
        if not m:
            defauts.append(f"mode mal formé : {ligne.strip()}")
            continue
        par_suite.setdefault((m.group(1), m.group(2)), []).append(m.group(3))
    for nom, genre in entrees:
        if len(par_suite.get((nom, genre), [])) != 1:
            defauts.append(f"{nom}:{genre} sans mode, ou avec plusieurs")
    for nom, genre in par_suite:
        if (nom, genre) not in entrees:
            defauts.append(f"{nom}:{genre} : mode d'une suite qui n'est pas dans EN_SERIE")
    return defauts


class ListeSansChevauchement(unittest.TestCase):
    """Run-all-faster-and-guarded, D2 (tâche 2.5) : la liste des suites qui ne chevauchent jamais et les modes de la liste en série."""

    TEXTE = RUN_ALL.read_text(encoding="utf-8")
    RACINE = RUN_ALL.parents[1]

    def test_la_liste_du_depot_n_a_aucun_defaut(self):
        self.assertEqual(defauts_sans_chevauchement(self.TEXTE, self.RACINE), [])

    def test_la_liste_du_depot_n_est_pas_vide(self):
        self.assertTrue(lignes_du_tableau(self.TEXTE, "SANS_CHEVAUCHEMENT"))

    def test_une_entree_inconnue_ou_sans_raison_est_nommee(self):
        faux = "SANS_CHEVAUCHEMENT=(\n  ci_local:shell  # cas de signal : sondage de 20 tours\n  inconnue:shell  # une raison assez longue\n  hooks:shell\n)\n"
        defauts = defauts_sans_chevauchement(faux, self.RACINE)
        self.assertIn("inconnue:shell : aucune suite de ce nom de ce genre", defauts)
        self.assertIn("hooks:shell sans raison", defauts)
        self.assertEqual(len(defauts), 2, defauts)

    # Suites finish_* : chacune est dans SANS_CHEVAUCHEMENT ou dans cette liste nommée, avec ce qu'elle remplace et sa condition de retrait
    # (R-20261029-40, point 3). Une entrée de la liste ne doit plus être dans SANS_CHEVAUCHEMENT.
    FINISH_SANS_ATTENTE = {
        ("finish_checks", "python"): "aucune attente ni fenêtre de temps (lecture de listes et de dépôts factices). Remplace : rien. "
                                     "Retrait : quand un de ses tests ajoute une attente bornée ou une mesure de durée (elle passe alors dans SANS_CHEVAUCHEMENT).",
        ("finish_codes", "python"): "aucune attente, seulement des délais de sécurité de 120 s sur des lancements de script. Remplace : rien. "
                                     "Retrait : quand un de ses tests ajoute une attente bornée ou une mesure de durée (elle passe alors dans SANS_CHEVAUCHEMENT).",
    }

    def suites_finish(self):
        python = {(d.name, "python") for d in (self.RACINE / "tests").glob("finish_*") if list(d.glob("test_*.py"))}
        shell = {(nom, "shell") for _, nom, _ in suites_shell_du_depot() if nom.startswith("finish_")}
        return python | shell

    def test_chaque_suite_finish_est_sans_chevauchement_ou_exemptee_avec_sa_raison(self):
        declarees = {tuple(re.match(r"^\s*([\w-]+):(python|shell)", l).groups()) for l in lignes_du_tableau(self.TEXTE, "SANS_CHEVAUCHEMENT")}
        for suite in sorted(self.suites_finish()):
            self.assertTrue(suite in declarees or suite in self.FINISH_SANS_ATTENTE, f"{suite[0]}:{suite[1]} : ni dans SANS_CHEVAUCHEMENT ni dans FINISH_SANS_ATTENTE")
        for suite, raison in self.FINISH_SANS_ATTENTE.items():
            self.assertIn(suite, self.suites_finish(), f"{suite} : aucune suite de ce nom, retirer l'exemption")
            self.assertNotIn(suite, declarees, f"{suite} : à la fois exemptée et dans SANS_CHEVAUCHEMENT")
            self.assertIn("Remplace :", raison)
            self.assertIn("Retrait :", raison)

    def test_chaque_entree_de_la_liste_en_serie_a_un_mode(self):
        self.assertEqual(defauts_modes_en_serie(self.TEXTE), [])

    def test_une_entree_en_serie_sans_mode_ou_un_mode_orphelin_est_nomme(self):
        faux = "EN_SERIE=(\n  run_all:python  # une raison\n  dbtest:shell  # une raison\n)\nMODE_SERIE=(\n  run_all:python:chevauche\n  autre:shell:seule\n)\n"
        defauts = defauts_modes_en_serie(faux)
        self.assertIn("dbtest:shell sans mode, ou avec plusieurs", defauts)
        self.assertIn("autre:shell : mode d'une suite qui n'est pas dans EN_SERIE", defauts)

    def test_run_all_chevauche_et_dbtest_est_seule(self):
        modes = {tuple(l.split("#")[0].strip().split(":")[:2]): l.split("#")[0].strip().split(":")[2] for l in lignes_du_tableau(self.TEXTE, "MODE_SERIE")}
        self.assertEqual(modes[("run_all", "python")], "chevauche")
        self.assertEqual(modes[("dbtest", "shell")], "seule")


class ChevauchementDeLaPhaseEnSerie(unittest.TestCase):
    """Run-all-faster-and-guarded, D2 (tâche 2.4) : « run_all » chevauche la fin de la phase en parallèle sous quatre conditions ; « dbtest »
    part seule et en dernier ; RUN_ALL_OVERLAP=0, une tâche et la base jetable gardent le passage en série. Les heures de début et de fin sont
    comparées entre elles seulement, jamais à une horloge ni à un seuil."""

    suite = Lanceur.suite
    shell = Lanceur.shell
    env = SuitesEnParallele.env
    lancer = SuitesEnParallele.lancer
    lire = SuitesEnParallele.lire
    intervalle = SuitesEnParallele.intervalle
    se_chevauchent = SuitesEnParallele.se_chevauchent
    LIGNE_DE_SUITE = SuitesEnParallele.LIGNE_DE_SUITE
    setUp = SuitesEnParallele.setUp

    def notee(self, nom, duree):
        self.suite(nom, suite_notee(self.notes, nom, duree))

    def debut(self, nom):
        return self.intervalle(nom)[0]

    def fin(self, nom):
        return self.intervalle(nom)[1]

    def en_cours_au_depart_de(self, nom, autres):
        """Les suites de `autres` qui tournent à l'instant où `nom` démarre."""
        t = self.debut(nom)
        return [a for a in autres if self.debut(a) < t < self.fin(a)]

    def lignes_de_suites(self, resultat):
        return [l.split()[0] for l in resultat.stdout.splitlines() if self.LIGNE_DE_SUITE.match(l)]

    def test_run_all_part_pendant_la_queue_de_la_phase_en_parallele(self):
        self.notee("alpha", 3.0)    # la longue : encore là quand beta a fini
        self.notee("beta", 0.3)
        self.notee("run_all", 0.5)
        resultat = self.lancer("alpha", "beta", "run_all", RUN_ALL_JOBS="2")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertLess(self.debut("run_all"), self.fin("alpha"))       # il chevauche la fin de alpha
        self.assertGreaterEqual(self.debut("run_all"), self.fin("beta"))  # mais seulement une fois beta finie : au plus la moitié des tâches
        self.assertLessEqual(self.debut("alpha"), self.debut("run_all"))
        self.assertLessEqual(self.debut("beta"), self.debut("run_all"))   # toutes les suites en parallèle avaient démarré
        self.assertEqual(self.lignes_de_suites(resultat), ["alpha", "beta", "run_all"])   # les lignes gardent l'ordre déclaré
        self.assertIn("run_all : chevauchement de la phase en série : run_all ; jamais avec : aucune", resultat.stdout)

    def test_la_ligne_de_chevauchement_suit_la_ligne_des_taches(self):
        self.notee("alpha", 0.2)
        self.notee("run_all", 0.2)
        lignes = self.lancer("alpha", "run_all", RUN_ALL_JOBS="2").stdout.splitlines()
        i = lignes.index("run_all : 2 suites à la fois, puis en série : run_all")
        self.assertTrue(lignes[i + 1].startswith("run_all : chevauchement de la phase en série :"), lignes[i + 1])

    def test_pas_de_chevauchement_quand_plus_de_la_moitie_des_taches_tournent(self):
        for nom in ("alpha", "beta", "gamma"):
            self.notee(nom, 2.0)
        self.notee("run_all", 0.5)
        resultat = self.lancer("alpha", "beta", "gamma", "run_all", RUN_ALL_JOBS="4")   # moitié : 2 ; trois tournent ensemble
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertLessEqual(len(self.en_cours_au_depart_de("run_all", ("alpha", "beta", "gamma"))), 2)
        self.assertGreaterEqual(self.debut("run_all"), min(self.fin(n) for n in ("alpha", "beta", "gamma")))

    def test_jamais_pendant_une_suite_de_la_liste_sans_chevauchement(self):
        self.notee("beta", 0.3)
        self.notee("run_all", 0.5)
        self.shell("ci_local/test_ci_local.sh", shell_note(self.notes, "ci_local", 3))   # ci_local:shell est dans SANS_CHEVAUCHEMENT
        resultat = self.lancer("beta", "ci_local", "run_all", RUN_ALL_JOBS="2")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertFalse(self.se_chevauchent("run_all", "ci_local"))
        self.assertGreaterEqual(self.debut("run_all"), self.fin("ci_local"))
        self.assertIn("jamais avec : ci_local", resultat.stdout)

    def test_dbtest_part_apres_toutes_les_autres_suites_et_seule(self):
        self.notee("alpha", 1.0)
        self.notee("beta", 0.3)
        self.notee("run_all", 0.5)
        self.shell("db_scripts/test_dbtest.sh", shell_note(self.notes, "dbtest", 0.5))
        resultat = self.lancer("alpha", "beta", "run_all", "dbtest", RUN_ALL_JOBS="2")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        for autre in ("alpha", "beta", "run_all"):
            self.assertFalse(self.se_chevauchent("dbtest", autre), autre)
            self.assertLessEqual(self.fin(autre), self.debut("dbtest"), autre)
        self.assertEqual(self.lignes_de_suites(resultat), ["alpha", "beta", "run_all", "dbtest"])

    def test_aucune_suite_en_parallele_ne_part_apres_run_all(self):
        for nom, duree in (("alpha", 2.0), ("beta", 0.3), ("gamma", 0.3), ("delta", 0.3)):
            self.notee(nom, duree)
        self.notee("run_all", 0.5)
        resultat = self.lancer("alpha", "beta", "delta", "gamma", "run_all", RUN_ALL_JOBS="2")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        for nom in ("alpha", "beta", "gamma", "delta"):
            self.assertLessEqual(self.debut(nom), self.debut("run_all"), nom)

    def test_overlap_a_zero_rend_le_passage_en_serie_d_avant(self):
        self.notee("alpha", 2.0)
        self.notee("beta", 0.3)
        self.notee("run_all", 0.3)
        resultat = self.lancer("alpha", "beta", "run_all", RUN_ALL_JOBS="2", RUN_ALL_OVERLAP="0")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertGreaterEqual(self.debut("run_all"), self.fin("alpha"))
        self.assertGreaterEqual(self.debut("run_all"), self.fin("beta"))
        self.assertIn("run_all : chevauchement coupé (RUN_ALL_OVERLAP=0)", resultat.stdout)
        self.assertNotIn("chevauchement de la phase en série", resultat.stdout)

    def test_une_autre_valeur_ou_aucune_laisse_le_chevauchement(self):
        for valeur in ("1", "", "oui"):
            with self.subTest(valeur=valeur):
                shutil.rmtree(self.racine)
                self.racine.mkdir()
                self.notee("alpha", 3.0)
                self.notee("beta", 0.3)
                self.notee("run_all", 0.3)
                resultat = self.lancer("alpha", "beta", "run_all", RUN_ALL_JOBS="2", RUN_ALL_OVERLAP=valeur)
                self.assertEqual(resultat.returncode, 0, resultat.stdout)
                self.assertLess(self.debut("run_all"), self.fin("alpha"))
                self.assertIn("chevauchement de la phase en série", resultat.stdout)

    def test_une_tache_ou_la_base_jetable_aucun_chevauchement_et_aucune_ligne(self):
        self.notee("alpha", 1.0)
        self.notee("run_all", 0.3)
        for variables in ({"RUN_ALL_JOBS": "1"}, {"RUN_ALL_JOBS": "4", "DBTEST_PORT": "55432"}):
            with self.subTest(variables=variables):
                resultat = self.lancer("alpha", "run_all", **variables)
                self.assertEqual(resultat.returncode, 0, resultat.stdout)
                self.assertFalse(self.se_chevauchent("alpha", "run_all"))
                self.assertNotIn("chevauchement", resultat.stdout)


class JournalDesRunnersComplets(unittest.TestCase):
    """Run-all-faster-and-guarded, D4 (tâche 2.8) : une ligne par lancement complet, présence des autres lancements, interruption, purge,
    panne du journal. Faux dossier de données (RUN_ALL_RUNS_JOURNAL sur une racine injectée) : jamais le vrai dossier du compte."""

    ENTETE = "debut\tfin\tsecondes\tverdict\tcontexte\tposte\ttaches\tsuites\tconcurrence\tautres_max\tautres_genres\tcharge_max"

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.donnees = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.donnees, True)
        self.journal = self.donnees / "journal" / "run-all-complets.tsv"
        self.presence = self.donnees / "journal" / "run-all-presence"
        self.tmp_lanceur = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp_lanceur, True)
        self.processus = []
        self.addCleanup(self.tuer)
        for nom in ("alpha", "beta"):
            (self.racine / "tests" / nom).mkdir(parents=True)
            (self.racine / "tests" / nom / f"test_{nom}.py").write_text(SUITE_OK)
        for chemin in scripts_shell():
            cible = self.racine / chemin
            cible.parent.mkdir(parents=True, exist_ok=True)
            cible.write_text(SHELL_OK)
        subprocess.run(["git", "init", "-q"], cwd=self.racine, check=True)
        subprocess.run(["git", "add", "-A"], cwd=self.racine, check=True)

    def tuer(self):
        for p in self.processus:
            if p.poll() is None:
                p.kill()
            p.wait()

    def env(self, **variables):
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS", "RUN_ALL_JOBS", "DBTEST_PORT",
                                                                "RUN_ALL_DURATIONS", "FINISH_LOCK_TOKEN")}
        env.update({"RUN_ALL_ROOT": str(self.racine), "RUN_ALL_DEPS": "", "TMPDIR": str(self.tmp_lanceur), "RUN_ALL_JOBS": "2",
                    "RUN_ALL_RUNS_JOURNAL": str(self.journal)}, **variables)
        return env

    def lancer(self, *arguments, **variables):
        return subprocess.run(["bash", str(RUN_ALL), *arguments], env=self.env(**variables), capture_output=True, text=True, timeout=180,
                              stdin=subprocess.DEVNULL)

    def lignes(self):
        return self.journal.read_text(encoding="utf-8").splitlines() if self.journal.exists() else []

    def champs(self):
        return dict(zip(self.ENTETE.split("\t"), self.lignes()[-1].split("\t")))

    def dormeur(self):
        p = subprocess.Popen(["sleep", "300"])
        self.processus.append(p)
        return p

    def test_un_lancement_seul_ecrit_une_ligne_avec_les_champs_de_d4(self):
        resultat = self.lancer()
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        lignes = self.lignes()
        self.assertEqual(len(lignes), 2, lignes)
        self.assertEqual(lignes[0], self.ENTETE)
        champs = self.champs()
        self.assertRegex(champs["debut"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$")
        self.assertRegex(champs["fin"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$")
        self.assertEqual((champs["verdict"], champs["contexte"], champs["poste"], champs["taches"]), ("vert", "auteur", "espace", "2"))
        self.assertEqual((champs["concurrence"], champs["autres_max"], champs["autres_genres"]), ("seul", "0", ""))
        self.assertEqual(champs["suites"], str(2 + len(scripts_shell())))
        self.assertRegex(champs["charge_max"], r"^(\d+\.\d)?$")
        duree = re.search(r"durée totale (\d+),(\d) s", resultat.stdout)
        self.assertEqual(champs["secondes"], f"{duree.group(1)}.{duree.group(2)}")    # la durée de la ligne est celle de la ligne de total

    def test_une_suite_rouge_donne_le_verdict_rouge(self):
        (self.racine / "tests" / "casse").mkdir()
        (self.racine / "tests" / "casse" / "test_casse.py").write_text(SUITE_KO)
        resultat = self.lancer()
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertEqual(self.champs()["verdict"], "rouge")

    def test_le_contexte_fin_quand_le_jeton_de_fin_est_pose(self):
        self.lancer(FINISH_LOCK_TOKEN="jeton-de-fin-fictif")
        self.assertEqual(self.champs()["contexte"], "fin")

    def test_un_lancement_concurrent_vivant_est_compte_avec_son_genre(self):
        self.presence.mkdir(parents=True)
        (self.presence / str(self.dormeur().pid)).write_text("ciblé\n")
        resultat = self.lancer()
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        champs = self.champs()
        self.assertEqual((champs["concurrence"], champs["autres_max"], champs["autres_genres"]), ("concurrent", "1", "ciblé"))

    def test_une_entree_de_presence_d_un_processus_mort_est_ignoree_et_retiree(self):
        mort = subprocess.Popen(["true"])
        mort.wait()
        self.presence.mkdir(parents=True)
        entree = self.presence / str(mort.pid)
        entree.write_text("filtré\n")
        self.lancer()
        self.assertEqual(self.champs()["concurrence"], "seul")
        self.assertFalse(entree.exists())

    def test_une_entree_de_presence_d_un_pid_d_un_autre_compte_compte_comme_vivante(self):
        # Remplace test_verrou_d_un_pid_d_un_autre_compte_compte_comme_vivant (main :2875, verrou retiré) : processus_vivant reste, la présence la lit.
        # Le pid 1 (launchd / init) rend « Operation not permitted » à kill -0 hors root : un autre compte compte comme vivant, son entrée n'est pas retirée.
        if os.geteuid() == 0:
            self.skipTest("root : kill -0 sur le pid 1 réussit sans EPERM")
        self.presence.mkdir(parents=True)
        entree = self.presence / "1"
        entree.write_text("ciblé\n")
        resultat = self.lancer()
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        champs = self.champs()
        self.assertEqual((champs["concurrence"], champs["autres_max"], champs["autres_genres"]), ("concurrent", "1", "ciblé"))
        self.assertTrue(entree.exists(), "l'entrée d'un processus d'un autre compte n'est pas retirée comme celle d'un mort")

    def test_kill_0_sous_une_autre_langue_compte_toujours_un_pid_d_un_autre_compte_comme_vivant(self):
        # Remplace test_kill_0_sous_une_autre_langue… (main :2990) : LC_ALL=C dans processus_vivant garde le message de permission reconnaissable
        # Limite connue, identique à main (classement 6.7) : sous macOS le message de kill ne dépend pas de la langue, seule l'assertion statique
        # « LC_ALL=C kill -0 » du lanceur protège vraiment ce point.
        if os.geteuid() == 0:
            self.skipTest("root : kill -0 sur le pid 1 réussit sans EPERM")
        self.presence.mkdir(parents=True)
        entree = self.presence / "1"
        entree.write_text("ciblé\n")
        resultat = self.lancer(LC_ALL="fr_FR.UTF-8", LANG="fr_FR.UTF-8")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertEqual(self.champs()["concurrence"], "concurrent")
        self.assertTrue(entree.exists())
        self.assertIn('LC_ALL=C kill -0 "$1"', RUN_ALL.read_text(encoding="utf-8"))

    def test_les_entrees_de_presence_du_lancement_sont_retirees_a_la_sortie(self):
        self.lancer()
        self.assertEqual(list(self.presence.iterdir()) if self.presence.exists() else [], [])

    def test_un_lancement_filtre_laisse_une_entree_de_presence_pendant_qu_il_tourne_puis_la_retire(self):
        vue = self.donnees / "vue.txt"
        (self.racine / "tests" / "voit").mkdir()
        (self.racine / "tests" / "voit" / "test_voit.py").write_text(
            "import os, unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n"
            f"        d = {str(self.presence)!r}\n"
            f"        open({str(vue)!r}, 'w').write(','.join(open(os.path.join(d, n)).read().strip() for n in os.listdir(d)))\n")
        resultat = self.lancer("voit")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertEqual(vue.read_text(), "filtré")
        self.assertEqual(list(self.presence.iterdir()), [])
        self.assertEqual(self.lignes(), [])   # un lancement filtré n'écrit aucune ligne de journal

    def test_un_lancement_interrompu_ecrit_une_ligne_interrompu(self):
        demarre = self.donnees / "demarre"
        (self.racine / "tests" / "dort").mkdir()
        (self.racine / "tests" / "dort" / "test_dort.py").write_text(
            f"import time, unittest\nclass T(unittest.TestCase):\n    def test_a(self):\n        open({str(demarre)!r}, 'w').write('1')\n        time.sleep(60)\n")
        p = subprocess.Popen(["bash", str(RUN_ALL)], env=self.env(), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             preexec_fn=lambda: signal.signal(signal.SIGINT, signal.SIG_DFL))
        self.processus.append(p)
        debut = time.time()
        while time.time() - debut < 60 and not demarre.exists():
            time.sleep(0.1)
        self.assertTrue(demarre.exists(), "la suite qui dort doit avoir démarré")
        p.send_signal(signal.SIGTERM)
        p.wait(timeout=30)
        self.assertEqual(p.returncode, -signal.SIGTERM)
        self.assertEqual(self.champs()["verdict"], "interrompu")
        self.assertEqual(list(self.presence.iterdir()), [])

    def test_aucune_ligne_pour_un_lancement_refuse_avant_sa_premiere_suite(self):
        # code 2 : nombre de tâches invalide
        self.assertEqual(self.lancer(RUN_ALL_JOBS="abc").returncode, 2)
        # code 4 : une fin de branche en cours (verrou de fin vivant d'un autre jeton)
        verrou = self.racine / ".git" / "pmzilla-fin-en-cours"
        verrou.mkdir()
        (verrou / "pid").write_text(str(self.dormeur().pid))
        (verrou / "branche").write_text("feat/autre")
        (verrou / "jeton").write_text("autre-jeton")
        self.assertEqual(self.lancer().returncode, 4)
        shutil.rmtree(verrou)
        # code 5 : des noms qui ne correspondent à aucune suite
        self.assertEqual(self.lancer("inconnue").returncode, 5)
        # code 7 : Node ou node_modules de Mothra à mettre en conformité avant un lancement complet
        (self.racine / "mothra").mkdir()
        (self.racine / "mothra" / ".node-version").write_text("0.0.1\n")
        self.assertEqual(self.lancer(RUN_ALL_SUITES_NPM="mothra:mothra").returncode, 7)
        self.assertEqual(self.lignes(), [])
        self.assertFalse(self.presence.exists() and list(self.presence.iterdir()))

    def test_les_lignes_de_plus_d_un_an_sont_purgees_et_l_entete_reste(self):
        self.journal.parent.mkdir(parents=True)
        recente = "2999-01-01T00:00:00\t2999-01-01T00:10:00\t600.0\tvert\tsession\tespace\t8\t100\tseul\t0\t\t1.0"
        self.journal.write_text("\n".join([self.ENTETE, "2020-01-01T00:00:00\t2020-01-01T00:10:00\t600.0\tvert\tsession\tespace\t8\t100\tseul\t0\t\t1.0",
                                           recente]) + "\n", encoding="utf-8")
        self.assertEqual(self.lancer().returncode, 0)
        lignes = self.lignes()
        self.assertEqual(lignes[0], self.ENTETE)
        self.assertNotIn("2020-01-01", "\n".join(lignes))
        self.assertIn(recente, lignes)
        self.assertEqual(len(lignes), 3)

    def test_la_purge_n_a_lieu_que_si_la_premiere_ligne_de_donnees_a_plus_d_un_an(self):
        self.journal.parent.mkdir(parents=True)
        vieille = "2020-01-01T00:00:00\t2020-01-01T00:10:00\t600.0\tvert\tsession\tespace\t8\t100\tseul\t0\t\t1.0"
        recente = "2999-01-01T00:00:00\t2999-01-01T00:10:00\t600.0\tvert\tsession\tespace\t8\t100\tseul\t0\t\t1.0"
        self.journal.write_text("\n".join([self.ENTETE, recente, vieille]) + "\n", encoding="utf-8")   # la première ligne est récente : rien n'est réécrit
        self.assertEqual(self.lancer().returncode, 0)
        lignes = self.lignes()
        self.assertEqual(lignes[:3], [self.ENTETE, recente, vieille])
        self.assertEqual(len(lignes), 4)

    def test_la_ligne_ne_contient_ni_chemin_ni_nom_de_suite(self):
        self.lancer()
        contenu = self.journal.read_text(encoding="utf-8")
        for texte in (str(self.racine), str(self.donnees), "alpha", "beta", "hooks", "test_"):
            self.assertNotIn(texte, contenu)

    def test_journal_impossible_a_ecrire_une_ligne_apres_le_total_avant_l_empreinte_et_rien_ne_change(self):
        bloc = self.donnees / "fichier"
        bloc.write_text("pas un dossier\n")
        resultat = self.lancer(RUN_ALL_RUNS_JOURNAL=str(bloc / "sous" / "journal.tsv"))
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        lignes = resultat.stdout.splitlines()
        phrase = "run_all : journal des runners complets non écrit (écriture impossible)"
        self.assertEqual(lignes.count(phrase), 1)
        i_total = next(i for i, l in enumerate(lignes) if l.startswith("TOTAL :"))
        i_empreinte = next(i for i, l in enumerate(lignes) if l.startswith("Empreinte de l'index enregistrée"))
        self.assertLess(i_total, lignes.index(phrase))
        self.assertLess(lignes.index(phrase), i_empreinte)
        arbre = subprocess.run(["git", "write-tree"], cwd=self.racine, capture_output=True, text=True).stdout.strip()
        self.assertEqual((self.racine / ".git" / "pmzilla-run-all-ok").read_text().strip(), arbre)
        self.assertNotIn(str(bloc), resultat.stdout)

    def test_racine_injectee_sans_variable_aucun_journal_nulle_part(self):
        resultat = self.lancer(RUN_ALL_RUNS_JOURNAL="", HOME=str(self.donnees), PMZILLA_LAB_DATA=str(self.donnees / "lab"))
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertEqual(list(self.donnees.rglob("*.tsv")), [])
        self.assertFalse((self.donnees / "lab").exists())


LISTE_MAC = "tests/suites_mac.txt"
LIGNE_MAC = re.compile(r"^([\w-]+):(python|shell)\s*(?:#(.*))?$")


PORTABLE_REJEUX = re.compile(r"^#\s*portable après deux rejeux\s*:\s*([\w-]+):shell\s*#\s*\S")


def classement_shell(texte: str) -> tuple:
    """Suites shell propres au Mac (entrées « nom:shell ») et suites shell déclarées « portables après deux rejeux » (D6, R-20261106-2)."""
    mac, portables = set(), set()
    for ligne in texte.splitlines():
        brute = ligne.strip()
        m = LIGNE_MAC.match(brute)
        if m and m.group(2) == "shell":
            mac.add(m.group(1))
        p = PORTABLE_REJEUX.match(brute)
        if p:
            portables.add(p.group(1))
    return mac, portables


def defauts_classement(texte: str, shells: list) -> dict:
    """Défauts du classement des suites shell (D6) : non classées, présentes dans la liste et déclarées portables, portables inconnues."""
    mac, portables = classement_shell(texte)
    return {"non_classees": [s for s in shells if s not in mac and s not in portables],
            "dans_les_deux": sorted(mac & portables),
            "portables_inconnues": sorted(portables - set(shells))}


def defauts_liste_mac(texte: str, racine: Path) -> list:
    """Défauts de la liste des suites propres au Mac (local-ci-container, D3) : entrée d'une suite absente de ce genre, ligne sans raison,
    ligne illisible, entrée en double. Chaque défaut nomme la ligne ou l'entrée. Les suites shell sont celles de tests/suites_shell.txt."""
    shells = {nom: chemin for chemin, nom, _ in suites_shell_du_depot()}
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
    toute suite shell du lanceur est classée : dans la liste, ou dans sa section « portables après deux rejeux » (D6, R-20261106-2)."""

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)
        (self.racine / "tests" / "alpha").mkdir(parents=True)
        (self.racine / "tests" / "alpha" / "test_alpha.py").write_text(SUITE_OK)
        (self.racine / "tests" / "hooks").mkdir(parents=True)
        (self.racine / "tests" / "hooks" / "test_pre_commit.sh").write_text(SHELL_OK)

    def test_liste_du_depot_sans_defaut(self):
        texte = (RUN_ALL.parents[1] / LISTE_MAC).read_text(encoding="utf-8")
        self.assertEqual(defauts_liste_mac(texte, RUN_ALL.parents[1]), [])

    def test_toute_suite_shell_du_lanceur_est_classee(self):
        # R-20261106-2 : remplace test_toute_suite_shell_du_lanceur_est_dans_la_liste (règle « propre au Mac par défaut », remplacée par D6) ;
        # réécriture, pas suppression : aucune suite shell ne reste non classée, et aucune n'est à la fois propre au Mac et portable.
        # Retrait : tombe avec la liste des suites propres au Mac (tests/suites_mac.txt vide, voir son en-tête).
        texte = (RUN_ALL.parents[1] / LISTE_MAC).read_text(encoding="utf-8")
        shells = [nom for _, nom, _ in suites_shell_du_depot()]
        defauts = defauts_classement(texte, shells)
        self.assertEqual(defauts["non_classees"], [])
        self.assertEqual(defauts["dans_les_deux"], [])
        self.assertEqual(defauts["portables_inconnues"], [])

    def test_fixture_classement_shell(self):
        texte = ("hooks:shell # raison\n"
                 "# portable après deux rejeux : worktree:shell # deux rejeux verts\n"
                 "# portable après deux rejeux : sans_trace:shell\n"
                 "# portable après deux rejeux : mal_forme:shellx # deux rejeux verts\n"
                 "# commentaire ordinaire : ci_local:shell\n"
                 "alpha:python # raison\n")
        self.assertEqual(classement_shell(texte), ({"hooks"}, {"worktree"}))

    def test_fixture_negative_defauts_classement(self):
        # revue Opus 11.1 : les trois défauts du classement sont détectés sur un texte fabriqué (suite non classée, suite dans les deux,
        # suite portable inconnue) ; les assertions du test sur le dépôt sont inchangées.
        texte = ("hooks:shell # raison\n"
                 "# portable après deux rejeux : hooks:shell # deux rejeux verts\n"
                 "# portable après deux rejeux : fantome:shell # deux rejeux verts\n")
        self.assertEqual(defauts_classement(texte, ["hooks", "worktree"]),
                         {"non_classees": ["worktree"], "dans_les_deux": ["hooks"], "portables_inconnues": ["fantome"]})
        propre = "hooks:shell # raison\n# portable après deux rejeux : worktree:shell # deux rejeux verts\n"
        self.assertEqual(defauts_classement(propre, ["hooks", "worktree"]),
                         {"non_classees": [], "dans_les_deux": [], "portables_inconnues": []})

    def test_la_liste_contient_ci_local_lock_hooks_et_watch_sh(self):
        texte = (RUN_ALL.parents[1] / LISTE_MAC).read_text(encoding="utf-8")
        for entree in ("ci_local:shell", "lock-hooks:shell", "watch_sh:python"):
            self.assertRegex(texte, rf"(?m)^{re.escape(entree)}\s*#")

    def test_fixture_valide_sans_defaut(self):
        texte = "# commentaire\n\nalpha:python # raison de l'entrée\nhooks:shell # outils BSD et bash 3.2 du Mac\n"
        self.assertEqual(defauts_liste_mac(texte, self.racine), [])

    def test_fixture_suite_absente_nommee(self):
        texte = "beta:python # raison\nhooks:python # raison\ninconnue:shell # raison\n"
        self.assertEqual(defauts_liste_mac(texte, self.racine),
                         ["suite absente : beta:python", "suite absente : hooks:python", "suite absente : inconnue:shell"])

    def test_fixture_sans_raison_nommee(self):
        for ligne in ("alpha:python", "alpha:python #", "alpha:python #   "):
            self.assertEqual(defauts_liste_mac(ligne + "\n", self.racine), [f"sans raison : {ligne.strip()}"], ligne)

    def test_fixture_entree_en_double_nommee(self):
        texte = "alpha:python # une\nalpha:python # deux\n"
        self.assertEqual(defauts_liste_mac(texte, self.racine), ["en double : alpha:python"])

    def test_fixture_ligne_illisible_nommee(self):
        self.assertEqual(defauts_liste_mac("alpha # raison\n", self.racine), ["ligne illisible : alpha # raison"])


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
        for chemin in scripts_shell():
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
        listes = set(scripts_shell())
        oublies = []
        for script in sorted(tests.glob("*/*.sh")):
            relatif = f"tests/{script.parent.name}/{script.name}"
            if relatif not in listes and relatif not in auxiliaires:
                oublies.append(relatif)
        self.assertEqual(oublies, [], f"script(s) de test shell ni listé(s) ni déclaré(s) auxiliaire(s) : {oublies}")

    def test_les_auxiliaires_declares_existent(self):
        texte = RUN_ALL.read_text(encoding="utf-8")
        # Édition publique (manifeste `edition/manifest.yaml` absent) : tests/sandbox_sonde/ n'est pas publié, son auxiliaire n'y existe pas.
        # Remplace : rien. Retrait : tombe quand tests/sandbox_sonde/ est publié. Source : le manifeste ; écart vu dans le dépôt privé par
        # tests/build_edition/test_tests_publies_sans_fichier_exclu.py (ATTENDUS : tests/sandbox_sonde/sonde.sh doit y être exclu).
        def arbre_public() -> bool:
            return not (RUN_ALL.parents[1] / "edition" / "manifest.yaml").is_file()
        for relatif in re.findall(r"^#\s*AUXILIAIRE\s+(\S+)", texte, re.M):
            if arbre_public() and relatif.startswith("tests/sandbox_sonde/"):
                continue
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
        for chemin in scripts_shell():
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

    # --- gel ciblé (autonomous-trains-merge, D18, tâche 6.3) : la liste du verrou décide, par la règle unique de tools/finish_lock.py ---
    def ecrire_liste(self, *worktrees, fin=True):
        lignes = ["B feat/autre"] + [f"W {w}" for w in worktrees] + (["fin"] if fin else [])
        (self.lock / "gel").write_text("\n".join(lignes) + "\n")

    def lier(self, nom):
        """Un worktree lié de branche de travail du dépôt de la fausse racine (le dépôt a besoin d'un commit)."""
        lie = self.racine.parent / (self.racine.name + "-" + nom)
        self.addCleanup(shutil.rmtree, lie, True)
        if subprocess.run(["git", "rev-parse", "-q", "--verify", "HEAD"], cwd=self.racine, capture_output=True).returncode != 0:
            self.git("-c", "user.email=t@example.org", "-c", "user.name=test", "commit", "-q", "-m", "base")
        self.git("worktree", "add", "-q", "-b", nom, str(lie))
        return lie

    def lancer_dans(self, racine, *arguments):
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_NO_EVALS", "FINISH_LOCK_TOKEN", "PMZILLA_FINISH_LOCK_MAX_AGE")}
        env.update({"RUN_ALL_ROOT": str(racine), "RUN_ALL_DEPS": "", "RUN_ALL_DURATIONS": str(self.durees)})
        return subprocess.run(["bash", str(RUN_ALL), *arguments], env=env, capture_output=True, text=True, timeout=120)

    def test_gel_cible_racine_nommee_par_la_liste_refusee(self):
        lie = self.lier("liste")
        self.poser_verrou()
        self.ecrire_liste(lie)
        resultat = self.lancer_dans(lie, "alpha")
        self.assertEqual(resultat.returncode, 4, resultat.stdout)
        self.assertIn(self.PHRASE, resultat.stdout)

    def test_gel_cible_racine_hors_liste_lance_normalement(self):
        lie = self.lier("hors-liste")
        self.poser_verrou()
        self.ecrire_liste(self.racine.parent / "autre-worktree")
        avant = self.etat_verrou()
        resultat = self.lancer_dans(lie, "alpha")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertNotIn("fin de branche en cours", resultat.stdout)
        self.assertIn("TOTAL : 2 tests dans 1 suites · tous réussis", resultat.stdout)
        self.assertEqual(self.etat_verrou(), avant)

    def test_gel_cible_racine_sur_main_ou_detachee_refusee_meme_hors_liste(self):
        lie = self.lier("detache")
        self.git("-C", str(lie), "checkout", "-q", "--detach")
        self.poser_verrou()
        self.ecrire_liste(self.racine.parent / "autre-worktree")
        resultat = self.lancer_dans(lie, "alpha")
        self.assertEqual(resultat.returncode, 4, resultat.stdout)
        self.assertIn(self.PHRASE, resultat.stdout)

    def test_gel_cible_liste_illisible_gele_toute_racine(self):
        lie = self.lier("illisible")
        self.poser_verrou()
        self.ecrire_liste(self.racine.parent / "autre-worktree", fin=False)
        self.assertEqual(self.lancer_dans(lie, "alpha").returncode, 4)

    def test_gel_cible_jeton_de_la_fin_lance_meme_dans_la_liste(self):
        lie = self.lier("jeton")
        self.poser_verrou()
        self.ecrire_liste(lie)
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_NO_EVALS",)}
        env.update({"RUN_ALL_ROOT": str(lie), "RUN_ALL_DEPS": "", "RUN_ALL_DURATIONS": str(self.durees), "FINISH_LOCK_TOKEN": "jeton-de-test"})
        resultat = subprocess.run(["bash", str(RUN_ALL), "alpha"], env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(resultat.returncode, 0, resultat.stdout)

    def test_le_lanceur_n_a_pas_de_regle_de_gel_propre(self):
        """Une seule règle, celle de tools/finish_lock.py : le lanceur n'a plus sa propre lecture de la péremption du verrou."""
        texte = RUN_ALL.read_text(encoding="utf-8")
        code = "\n".join(l for l in texte.splitlines() if not l.lstrip().startswith("#"))
        self.assertNotIn("gel_perime", code)
        self.assertIn("finish_lock.py", code)
        self.assertIn("refuse", code)

    def test_le_texte_du_lanceur_ne_cree_ni_ne_retire_le_verrou(self):
        texte = RUN_ALL.read_text(encoding="utf-8")
        code = "\n".join(l for l in texte.splitlines() if not l.lstrip().startswith("#"))
        for motif in (r"mkdir[^\n]*fin-en-cours", r"rm[^\n]*fin-en-cours", r"rmdir[^\n]*fin-en-cours", r"mv[^\n]*fin-en-cours", r">\s*[^\n]*fin-en-cours"):
            self.assertIsNone(re.search(motif, code), motif)


FAUX_CI_SESSION = """#!/bin/bash
# faux tools/ci_local.sh (T2) : note ses arguments et son environnement à côté de lui, rend le code du fichier « ci_code » (0 sans lui)
ici=$(cd "$(dirname "$0")" && pwd)
printf '%s\\n' "$*" >> "$ici/ci_appels"
env | LC_ALL=C sort > "$ici/ci_env"
echo "ci_local : faux passage"
exit "$(cat "$ici/ci_code" 2>/dev/null || echo 0)"
"""

FAUX_MATIN = """#!/bin/bash
# faux tools/morning_state.sh : note ses arguments et son environnement à côté de lui, rend le code du fichier « code » (0 sans lui)
ici=$(cd "$(dirname "$0")" && pwd)
printf '%s\\n' "$*" >> "$ici/appels"
env | LC_ALL=C sort > "$ici/env"
echo "morning_state : ligne du faux module"
exit "$(cat "$ici/code" 2>/dev/null || echo 0)"
"""

APPEL_GETPWUID = "/usr/bin/perl -e 'print((getpwuid($<))[7])'"
FAUX_SELECTEUR = """import sys
print("select_suites : alpha : fichier nommé par la suite")
sys.exit(0)
"""
FAUX_SELECTEUR_COMPLET = "import sys\nprint('select_suites : exécution complète exigée')\nsys.exit(3)\n"


class SessionClaudeCode(unittest.TestCase):
    """Session Claude Code (session-runner, dossier 2026-10-26-droits-session-push-runner, décisions 1 à 3 de l'auteur ; R-20261102-44 ;
    tooling-proof-in-container T2, R-20261104-7 P2) : un lancement qui devient COMPLET par « --staged » (le complet nu et --branch sont refusés
    en 6 : SessionPreuveParLeConteneur) lit d'abord la garde du matin légère (tools/morning_state.sh runner, sans option, trouvé à côté du lanceur,
    environnement vidé, dossier de données passé explicitement ; code 6 sinon, le conteneur n'est alors pas appelé : GARDÉE par l'auteur, T2-1 (a)),
    puis passe par le conteneur (mode complet de tools/ci_local.sh) ; seul le verrou « un seul runner complet de session » est retiré avec T2
    (ses tests aussi, listés dans le rapport de la tâche 6.7). FINISH_LOCK_TOKEN
    ou DBTEST_PORT posées : code 6 pour tout lancement de session ; RUN_ALL_ROOT et un dossier de données différent de celui du compte :
    code 6 pour un lancement complet de session (--staged devenu complet). Hors session, ciblé ou filtré : rien ne change. Chaque décision est
    notée dans le journal de session du dossier de données (purge à un an).

    Le lanceur est COPIÉ dans une fausse racine (sans RUN_ALL_ROOT) : le faux tools/morning_state.sh et le faux tools/ci_local.sh sont ceux qui
    sont à côté de lui."""

    def setUp(self):
        self.base = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.base, True)
        self.racine = self.base / "depot"
        (self.racine / "tests" / "alpha").mkdir(parents=True)
        (self.racine / "tests" / "alpha" / "test_alpha.py").write_text(SUITE_OK)
        (self.racine / "tests" / "suites_shell.txt").write_text("# aucune suite shell dans la fausse racine\n")
        (self.racine / "tests" / "suites_mac.txt").write_text("# aucune\n")
        # Dossier personnel simulé : le lanceur lit celui du compte par getpwuid ; la copie de la fausse racine remplace ce seul appel par
        # un dossier fixe, pour que les tests n'écrivent jamais dans le vrai dossier de données (garde : tearDownModule).
        self.home = self.base / "home"
        self.home.mkdir()
        texte = RUN_ALL.read_text(encoding="utf-8")
        self.assertIn(APPEL_GETPWUID, texte)
        self.assertIn("\nSUITES_NPM=(mothra:mothra)\n", texte)
        texte = texte.replace("\nSUITES_NPM=(mothra:mothra)\n", "\nSUITES_NPM=()\n")   # la fausse racine n'a pas de dossier mothra
        (self.racine / "tests" / "run_all.sh").write_text(texte.replace(APPEL_GETPWUID, f"printf %s {str(self.home)!r}"), encoding="utf-8")
        (self.racine / "tools").mkdir()
        shutil.copy(RUN_ALL.parent.parent / "tools" / "preuve_arbre.py", self.racine / "tools" / "preuve_arbre.py")
        (self.racine / "tools" / "ci_local.sh").write_text(FAUX_CI_SESSION)   # T2 : les suites portables d'une session vont au conteneur
        self.matin = self.racine / "tools" / "morning_state.sh"
        self.matin.write_text(FAUX_MATIN)   # le --staged complet garde la garde du matin (T2-1 (a))
        self.donnees = self.home / ".pmzilla-lab"
        self.durees = self.base / "durees.tsv"
        self.verrou = self.donnees / "verrous" / "run-all-session"   # retiré avec T2 : les tests vérifient qu'il n'est plus jamais créé
        self.journal = self.donnees / "journal" / "run-all-session.tsv"

    def lancer_staged_complet(self, **variables):
        """R-20261102-44 et R-20261101-115 : en session, le lancement complet NU est refusé en code 6 (tooling-proof-in-container, T1 ; couvert par
        SessionPreuveParLeConteneur). Le contrôle de garde de ces tests (matin, dossier de données, RUN_ALL_ROOT, verrou, journal) s'exerce, aussi
        strict, par un « --staged » qui devient complet (sélecteur « exécution complète exigée » posé ici, explicitement), qui garde cette garde et
        ce verrou jusqu'à T2. Les appels sont écrits « self.lancer_staged_complet(…) » : ils disent ce qu'ils lancent."""
        self.poser_selecteur(FAUX_SELECTEUR_COMPLET)
        return self.lancer("--staged", **variables)

    def lancer(self, *arguments, session="1", lanceur="run_all.sh", **variables):
        env = self.environnement(session, variables)
        return subprocess.run(["bash", str(self.racine / "tests" / lanceur), *arguments], env=env, cwd=self.racine,
                              capture_output=True, text=True, timeout=120)

    def environnement(self, session, variables):
        retirees = ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS", "RUN_ALL_ROOT", "FINISH_LOCK_TOKEN", "DBTEST_PORT", "CLAUDECODE",
                    "PMZILLA_RUN_NOW", "MORNING_NOW", "PMZILLA_RUN_MORNING_START", "PMZILLA_FINISH_LOCK_MAX_AGE", "PMZILLA_LAB_DATA")
        env = {k: v for k, v in os.environ.items() if k not in retirees}
        env.update({"RUN_ALL_DEPS": "", "PMZILLA_LAB_DATA": str(self.donnees), "RUN_ALL_DURATIONS": str(self.durees)})
        if session is not None:
            env["CLAUDECODE"] = session
        env.update(variables)
        return {k: v for k, v in env.items() if v is not None}   # None : variable retirée

    def appels(self):
        """Les appels du faux script du conteneur (tools/ci_local.sh)."""
        fichier = self.racine / "tools" / "ci_appels"
        return fichier.read_text().splitlines() if fichier.exists() else []

    def env_du_ci(self) -> dict:
        lignes = (self.racine / "tools" / "ci_env").read_text().splitlines()
        return dict(l.split("=", 1) for l in lignes if "=" in l)

    def appels_matin(self):
        """Les appels du faux module du matin (tools/morning_state.sh)."""
        fichier = self.racine / "tools" / "appels"
        return fichier.read_text().splitlines() if fichier.exists() else []

    def env_du_matin(self) -> dict:
        lignes = (self.racine / "tools" / "env").read_text().splitlines()
        return dict(l.split("=", 1) for l in lignes if "=" in l)

    def refus_matin(self):
        (self.racine / "tools" / "code").write_text("1")

    def lignes_journal(self):
        return self.journal.read_text().splitlines() if self.journal.exists() else []

    def verifier_refus(self, resultat, phrase):
        self.assertEqual(resultat.returncode, 6, resultat.stdout + resultat.stderr)
        self.assertIn(phrase, resultat.stdout)
        self.assertNotIn("TOTAL", resultat.stdout)
        self.assertNotRegex(resultat.stdout, r"alpha\s+\d+ tests")
        self.assertFalse(self.durees.exists(), "aucune ligne de durées sur un refus")

    # --- garde du matin légère (R-20261102-3 et R-20261102-5 ; GARDÉE par l'auteur, T2-1 (a)) : refus seulement tant que la veille ou la sauvegarde
    # tournent. Restaurée depuis main (test_run_all.py:2567-2624), aussi stricte ; « le conteneur n'est pas appelé » ajouté à chaque refus.

    def test_garde_du_matin_refusee_code_6_sans_suite_ni_duree(self):
        self.refus_matin()
        resultat = self.lancer_staged_complet()   # R-20261102-44, R-20261101-115 : --staged complet (le complet nu est refusé avant le matin)
        self.verifier_refus(resultat, "run_all : session Claude Code : lancement complet refusé : veille ou sauvegarde du jour en cours "
                                      "(morning_state : ligne du faux module)")
        self.assertNotIn("fenêtre du matin", resultat.stdout)
        self.assertFalse(self.verrou.exists(), "aucun verrou de session")
        self.assertEqual(self.appels(), [], "le conteneur n'est pas appelé sur un refus du matin")

    def test_garde_illisible_code_autre_que_1_refus_ferme_sans_dire_en_cours(self):
        # R-20261102-3 et R-20261102-5 : un code 2 ou 78 du module n'est pas « en cours » ; le refus reste fermé (code 6)
        for code in ("2", "78"):
            (self.racine / "tools" / "code").write_text(code)
            resultat = self.lancer_staged_complet()   # R-20261102-44, R-20261101-115
            self.verifier_refus(resultat, f"run_all : session Claude Code : lancement complet refusé : garde du matin illisible (code {code})")
            self.assertNotIn("en cours", resultat.stdout)
            self.assertFalse(self.verrou.exists())
        self.assertEqual(self.appels(), [], "le conteneur n'est pas appelé sur un refus du matin")

    def test_le_module_du_matin_recoit_un_environnement_vide_et_le_dossier_de_donnees(self):
        self.lancer_staged_complet(PMZILLA_RUN_NOW="0", MORNING_NOW="0",   # R-20261102-44, R-20261101-115
 PMZILLA_RUN_MORNING_START="23:59", MORNING_DATA="/x", HOME=str(self.base / "faux"),
                    PATH=f"{self.base}{os.pathsep}{os.environ['PATH']}", TZ="Pacific/Kiritimati", DB_BACKUP_SAUVEGARDES="/y")
        env = self.env_du_matin()
        self.assertEqual(env.get("PMZILLA_LAB_DATA"), str(self.donnees))
        self.assertEqual(env.get("PATH"), "/usr/bin:/bin:/usr/sbin:/sbin")
        self.assertNotEqual(env.get("HOME"), str(self.base / "faux"), "HOME lu par getpwuid, jamais la variable de l'appelant")
        for nom in ("PMZILLA_RUN_NOW", "MORNING_NOW", "PMZILLA_RUN_MORNING_START", "MORNING_DATA", "TZ", "DB_BACKUP_SAUVEGARDES",
                    "CLAUDECODE", "RUN_ALL_DEPS", "RUN_ALL_DURATIONS"):
            self.assertNotIn(nom, env, nom)

    def test_morning_state_absent_a_cote_du_lanceur_refus_ferme(self):
        self.matin.unlink()
        self.verifier_refus(self.lancer_staged_complet(), "lancement complet refusé : tools/morning_state.sh introuvable à côté du lanceur")   # R-20261102-3, -5 : phrase
        self.assertEqual(self.appels(), [], "le conteneur n'est pas appelé sur un refus du matin")

    def test_morning_state_trouve_par_le_chemin_du_lanceur_jamais_par_la_racine(self):
        texte = RUN_ALL.read_text(encoding="utf-8")
        code = "\n".join(l for l in texte.splitlines() if not l.lstrip().startswith("#"))
        self.assertNotIn("$RACINE/tools/morning_state.sh", code)
        self.assertIn('"$LANCEUR_DIR/../tools/morning_state.sh" runner 2>&1', code)   # sans option : R-20261102-3, -5
        self.assertNotIn("--margin", code)

    def test_le_module_du_matin_est_appele_sans_option(self):
        self.lancer_staged_complet()   # R-20261102-44, R-20261101-115
        self.assertEqual(self.appels_matin(), ["runner"])

    def test_staged_complet_passe_par_le_conteneur_en_mode_complet_sans_verrou(self):
        resultat = self.lancer_staged_complet()   # R-20261102-44, R-20261101-115 : c'est un --staged complet
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
        self.assertEqual(self.appels_matin(), ["runner"], "la garde du matin est lue avant le conteneur")
        self.assertEqual(self.appels(), ["run --index"])
        self.assertFalse(self.verrou.parent.exists(), "aucun verrou, aucun dossier de verrous : le verrou de session n'existe plus")
        self.assertNotRegex(resultat.stdout, r"alpha\s+\d+ tests", "aucune suite portable sur le Mac")

    def test_le_conteneur_recoit_le_dossier_de_donnees_du_compte_et_un_environnement_sans_variable_de_test(self):
        self.lancer_staged_complet(CI_LOCAL_DOCKER="/bin/false", CI_LOCAL_PREUVES_INDEX=str(self.base / "faux"), HOME=str(self.base / "faux-home"))
        env = self.env_du_ci()
        self.assertEqual(env.get("PMZILLA_LAB_DATA"), str(self.donnees))
        for nom in ("CI_LOCAL_DOCKER", "CI_LOCAL_PREUVES_INDEX", "CI_LOCAL_VERDICTS", "CI_LOCAL_PREUVES"):
            self.assertNotIn(nom, env, nom)

    # R-20261102-3 et R-20261102-5 : test_la_marge_est_la_duree_mediane_documentee retiré (MARGE_MATIN_SESSION n'existe plus, aucune fenêtre à avancer)
    def test_aucune_marge_ni_fenetre_dans_le_lanceur(self):
        texte = RUN_ALL.read_text(encoding="utf-8")
        code = "\n".join(l for l in texte.splitlines() if not l.lstrip().startswith("#"))
        self.assertNotIn("MARGE_MATIN_SESSION", code)
        self.assertNotIn("fenêtre du matin", code)

    def test_aucun_verrou_n_est_pris_ni_laisse_par_un_lancement_de_session(self):
        for arguments in (("alpha",), ("--staged",)):
            self.lancer(*arguments)
        self.lancer_staged_complet()
        self.assertFalse(self.verrou.exists())
        self.assertFalse((self.donnees / "verrous").exists())

    # --- variables qui déferaient la garde (M1)

    def test_jeton_de_fin_ou_port_de_la_base_jetable_en_session_code_6_meme_filtre(self):
        for variables, nom in (({"FINISH_LOCK_TOKEN": "x"}, "FINISH_LOCK_TOKEN"), ({"DBTEST_PORT": "5432"}, "DBTEST_PORT")):
            # () : complet NU explicite, refusé pour la variable AVANT le refus du conteneur (R-20261102-44, R-20261101-115) ; --staged : ajouté
            for arguments in ((), ("alpha",), ("--staged",)):
                resultat = self.lancer(*arguments, **variables)
                self.assertEqual(resultat.returncode, 6, (nom, arguments, resultat.stdout))
                self.assertIn(f"run_all : session Claude Code : {nom} posée, lancement refusé", resultat.stdout)
                self.assertNotIn("TOTAL", resultat.stdout)
        self.assertEqual(self.appels(), [])

    def test_variables_vides_sans_effet(self):
        resultat = self.lancer("alpha", FINISH_LOCK_TOKEN="", DBTEST_PORT="")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)

    def test_racine_injectee_refusee_pour_un_lancement_complet_de_session(self):
        resultat = self.lancer_staged_complet(RUN_ALL_ROOT=str(self.racine))   # R-20261102-44, R-20261101-115
        self.verifier_refus(resultat, "run_all : session Claude Code : RUN_ALL_ROOT posée pour un lancement complet, lancement refusé")
        self.assertEqual(self.appels(), [])
        filtre = self.lancer("alpha", RUN_ALL_ROOT=str(self.racine))
        self.assertEqual(filtre.returncode, 0, filtre.stdout)

    # --- ce qui ne change pas

    def poser_selecteur(self, texte):
        (self.racine / "tools" / "select_suites.py").write_text(texte)

    def test_cible_filtre_et_mac_ont_leur_code_exact_et_ne_lisent_pas_le_matin(self):
        # T2 (revue de T1, trou 1) : le code exact de chaque forme permise, plus « pas 6 » ; --mac sur une liste vide donne 2 (« Aucune suite trouvée »).
        # --portable n'en fait plus partie : refusé en session (T2-2). Restauré de main (:2714) : le module du matin n'est pas lu, même refusé.
        self.refus_matin()
        self.poser_selecteur(FAUX_SELECTEUR)   # le sélecteur choisit une suite : le lancement --staged reste ciblé
        for arguments, code in ((("alpha",), 0), (("--mac",), 2), (("--staged",), 0)):
            resultat = self.lancer(*arguments)
            self.assertEqual(resultat.returncode, code, (arguments, resultat.stdout))
        self.assertEqual(self.appels_matin(), [], "le module du matin n'est pas lu pour un nommé, --mac et un --staged ciblé")
        self.assertFalse(self.verrou.exists())

    def test_portable_refuse_en_session_code_6_sans_conteneur_ni_matin(self):
        # T2-2 (a), décision de l'auteur du 2026-11-04 : --portable ferait tourner des suites portables sur le Mac en session ; même forme de refus que T1
        self.refus_matin()
        self.poser_selecteur(FAUX_SELECTEUR)
        resultat = self.lancer("--portable")
        self.verifier_refus(resultat, PHRASE_PORTABLE_REFUSE + "\n")
        self.assertEqual(resultat.stdout, PHRASE_PORTABLE_REFUSE + "\n", "la phrase est toute la sortie")
        self.assertEqual(self.appels(), [], "le conteneur n'est pas appelé")
        self.assertEqual(self.appels_matin(), [], "le module du matin n'est pas lu")
        self.assertEqual([tuple(l.split("\t")[1:3]) for l in self.lignes_journal()[1:]], [("refusé", "conteneur-portable")])

    def test_code_inattendu_du_conteneur_ne_lance_rien_et_sort_en_1_avec_le_code(self):
        # T2-3 (b) : un code hors 0, 1, 3, 5, 6, 7 (usage 2, entrée refusée 4, interruption 130) : rien n'est lancé ici, sortie 1, une phrase qui donne le code
        (self.racine / "tests" / "suites_mac.txt").write_text("mac:python # essai : suite propre au Mac\n")   # alpha reste portable (envoyée au conteneur)
        (self.racine / "tests" / "mac").mkdir()
        (self.racine / "tests" / "mac" / "test_mac.py").write_text(SUITE_OK)
        formes = ((("alpha",), FAUX_SELECTEUR), (("--staged",), FAUX_SELECTEUR), (("--staged",), FAUX_SELECTEUR_COMPLET))   # nommé, ciblé, complet
        for code in ("2", "4", "130"):
            (self.racine / "tools" / "ci_code").write_text(code)
            for arguments, selecteur in formes:
                self.poser_selecteur(selecteur)
                resultat = self.lancer(*arguments)
                self.assertEqual(resultat.returncode, 1, (code, arguments, resultat.stdout))
                self.assertIn(f"run_all : le script du conteneur a rendu un code inattendu ({code}) : aucune suite lancée ; rien n'est écrit", resultat.stdout)
                self.assertNotIn("TOTAL", resultat.stdout)
                self.assertNotRegex(resultat.stdout, r"(alpha|mac)\s+\d+ tests")
                self.assertFalse(self.durees.exists(), "aucune ligne de durées : la partie Mac n'a pas tourné")

    def test_code_127_script_du_conteneur_introuvable_reste_un_code_9(self):
        (self.racine / "tools" / "ci_local.sh").unlink()
        resultat = self.lancer("alpha")
        self.assertEqual(resultat.returncode, 9, resultat.stdout)
        self.assertIn("run_all : conteneur indisponible (code 127) : aucune suite portable lancée ; rien n'est écrit", resultat.stdout)

    # --- un lancement ciblé qui retombe en complet est gardé comme un lancement complet (majeur 1) : matin, racine et dossier de données (le verrou
    # est retiré avec T2)

    def test_staged_qui_retombe_en_complet_est_refuse_par_le_matin(self):
        self.refus_matin()
        for selecteur in (None, "raise SystemExit(7)\n", FAUX_SELECTEUR_COMPLET):   # sélecteur absent, en échec, ou « exécution complète »
            if selecteur is not None:
                self.poser_selecteur(selecteur)
            resultat = self.lancer("--staged")
            self.verifier_refus(resultat, "run_all : session Claude Code : lancement complet refusé : veille ou sauvegarde du jour en cours")   # R-20261102-3, -5 : phrase
        self.assertFalse(self.verrou.exists())
        self.assertEqual(self.appels(), [], "le conteneur n'est pas appelé sur un refus du matin")

    def test_staged_qui_retombe_en_complet_est_refuse_par_la_racine_et_les_donnees(self):
        for selecteur in (None, "raise SystemExit(7)\n", FAUX_SELECTEUR_COMPLET):   # sélecteur absent, en échec, ou « exécution complète »
            if selecteur is not None:
                self.poser_selecteur(selecteur)
            self.verifier_refus(self.lancer("--staged", RUN_ALL_ROOT=str(self.racine)), "RUN_ALL_ROOT posée pour un lancement complet")
            self.verifier_refus(self.lancer("--staged", PMZILLA_LAB_DATA=str(self.base / "ailleurs")), "PMZILLA_LAB_DATA")
        self.assertEqual(self.appels(), [], "le conteneur n'est pas appelé sur un refus")

    def test_staged_qui_retombe_en_complet_permis_passe_par_le_conteneur_sans_verrou(self):
        self.poser_selecteur(FAUX_SELECTEUR_COMPLET)
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
        self.assertEqual(self.appels(), ["run --index"])
        self.assertFalse(self.verrou.exists())
        self.assertEqual([l.split("\t")[1:3] for l in self.lignes_journal()[1:]], [["lancé", "conteneur"]])

    def test_staged_refuse_n_efface_aucune_empreinte(self):
        subprocess.run(["git", "init", "-q"], cwd=self.racine, check=True)
        empreinte = self.racine / ".git" / "pmzilla-run-all-ok"
        ciblee = self.racine / ".git" / "pmzilla-run-targeted-ok"
        empreinte.write_text("a")
        ciblee.write_text("b")
        self.poser_selecteur(FAUX_SELECTEUR_COMPLET)
        self.verifier_refus(self.lancer("--staged", RUN_ALL_ROOT=str(self.racine)), "RUN_ALL_ROOT posée pour un lancement complet")
        self.verifier_refus(self.lancer("--staged", PMZILLA_LAB_DATA=str(self.base / "ailleurs")), "PMZILLA_LAB_DATA différente")   # revue de T1, trou 3
        self.refus_matin()
        self.verifier_refus(self.lancer("--staged"), "veille ou sauvegarde du jour en cours")   # R-20261102-3, -5 : phrase (main :2751)
        self.assertEqual(self.appels(), [], "le conteneur n'est pas appelé sur un refus")
        self.assertEqual(empreinte.read_text(), "a", "l'empreinte complète est intacte sur un refus")
        self.assertEqual(ciblee.read_text(), "b", "l'empreinte ciblée est intacte sur un refus")

    # --- PMZILLA_FINISH_LOCK_MAX_AGE lèverait le gel (majeur 2)

    def test_age_maximal_du_verrou_de_fin_non_vide_en_session_code_6(self):
        # () : complet NU explicite, refusé pour la variable AVANT le refus du conteneur (R-20261102-44, R-20261101-115) ; --staged : cas ajouté
        for arguments in ((), ("alpha",), ("--staged",), ("--portable",)):
            resultat = self.lancer(*arguments, PMZILLA_FINISH_LOCK_MAX_AGE="1")
            self.assertEqual(resultat.returncode, 6, (arguments, resultat.stdout))
            self.assertIn("run_all : session Claude Code : PMZILLA_FINISH_LOCK_MAX_AGE posée, lancement refusé", resultat.stdout)
        self.assertEqual(self.appels(), [])
        self.assertEqual(self.lancer("alpha", PMZILLA_FINISH_LOCK_MAX_AGE="").returncode, 0, "vide : sans effet")
        self.assertNotEqual(self.lancer("alpha", session=None, PMZILLA_FINISH_LOCK_MAX_AGE="1").returncode, 6, "hors session : rien ne change")

    # --- dossier de données : celui du compte, jamais celui que choisit l'appelant (majeur 3)

    def test_donnees_variable_absente_ou_egale_au_defaut_permises(self):
        for valeur in (None, str(self.donnees), str(self.donnees) + "/", str(self.home) + "/./.pmzilla-lab", ""):
            resultat = self.lancer_staged_complet(PMZILLA_LAB_DATA=valeur)   # R-20261102-44, R-20261101-115
            self.assertEqual(resultat.returncode, 0, (valeur, resultat.stdout))
            self.assertEqual(self.env_du_ci().get("PMZILLA_LAB_DATA"), str(self.home / ".pmzilla-lab"), "le défaut est passé au script du conteneur")

    def test_donnees_egale_au_defaut_via_un_lien_symbolique_permise(self):
        self.donnees.mkdir()
        lien = self.base / "lien"
        lien.symlink_to(self.donnees)
        self.assertEqual(self.lancer_staged_complet(PMZILLA_LAB_DATA=str(lien)).returncode, 0)   # R-20261102-44, R-20261101-115
        lien_home = self.base / "lien-home"
        lien_home.symlink_to(self.home)
        self.assertEqual(self.lancer_staged_complet(PMZILLA_LAB_DATA=str(lien_home / ".pmzilla-lab")).returncode, 0)
        shutil.rmtree(self.donnees)   # défaut inexistant : forme absolue normalisée, ancêtres résolus
        self.assertEqual(self.lancer_staged_complet(PMZILLA_LAB_DATA=str(lien_home / "sous" / ".." / ".pmzilla-lab")).returncode, 0)

    def test_donnees_differentes_code_6_pour_un_lancement_complet(self):
        for valeur in (str(self.base / "ailleurs"), str(self.home), str(self.donnees) + "-bis", str(self.donnees / "x"), "relatif"):
            resultat = self.lancer_staged_complet(PMZILLA_LAB_DATA=valeur)   # R-20261102-44, R-20261101-115
            self.verifier_refus(resultat, "run_all : session Claude Code : PMZILLA_LAB_DATA différente du dossier de données du compte")
        self.assertEqual(self.appels(), [])
        self.assertFalse(self.verrou.exists())
        autre = self.base / "autre"
        autre.mkdir()
        lien = self.base / "lien-autre"
        lien.symlink_to(autre)
        self.verifier_refus(self.lancer_staged_complet(PMZILLA_LAB_DATA=str(lien)), "PMZILLA_LAB_DATA différente")
        self.assertFalse(list(autre.iterdir()), "rien n'est écrit dans le dossier choisi par l'appelant")

    def test_donnees_avec_tilde_developpe_vers_le_dossier_du_compte_acceptee_si_c_est_le_defaut(self):
        # Décision : un « ~ » ou « ~/ » initial est développé avec le dossier personnel du compte (getpwuid), jamais avec HOME ; accepté
        # quand le résultat est le dossier de données du compte, refusé sinon.
        faux = self.base / "faux"
        faux.mkdir()
        for valeur in ("~/.pmzilla-lab", "~/.pmzilla-lab/", "~/./.pmzilla-lab"):
            resultat = self.lancer_staged_complet(PMZILLA_LAB_DATA=valeur, HOME=str(faux))   # R-20261102-44, R-20261101-115
            self.assertEqual(resultat.returncode, 0, (valeur, resultat.stdout))
        self.durees.unlink(missing_ok=True)
        for valeur in ("~", "~/autre", "~/.pmzilla-lab-bis", "~root/.pmzilla-lab"):
            self.verifier_refus(self.lancer_staged_complet(PMZILLA_LAB_DATA=valeur, HOME=str(faux)), "PMZILLA_LAB_DATA différente")

    def test_staged_reste_cible_avec_un_autre_dossier_de_donnees_ni_matin_ni_verrou(self):
        self.refus_matin()
        self.poser_selecteur(FAUX_SELECTEUR)
        resultat = self.lancer("--staged", PMZILLA_LAB_DATA=str(self.base / "ailleurs"))
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
        self.assertEqual(self.appels_matin(), [], "un lancement ciblé ne lit pas la garde du matin")
        self.assertEqual(self.appels(), ["run --index alpha"], "le ciblé passe par le conteneur sans refus du dossier de données")
        self.assertEqual(self.env_du_ci().get("PMZILLA_LAB_DATA"), str(self.donnees), "le conteneur reçoit le dossier du compte, jamais celui de l'appelant")
        self.assertFalse(self.verrou.exists())
        self.assertFalse((self.base / "ailleurs").exists())

    def test_staged_code_0_et_selection_vide_devient_complet_donc_garde(self):
        self.poser_selecteur("print('select_suites : aucune suite à lancer')\n")   # code 0, aucun nom de suite
        self.verifier_refus(self.lancer("--staged", RUN_ALL_ROOT=str(self.racine)), "RUN_ALL_ROOT posée pour un lancement complet")
        self.refus_matin()
        self.verifier_refus(self.lancer("--staged"), "lancement complet refusé : veille ou sauvegarde du jour en cours")   # R-20261102-3, -5 : phrase (main :2827)
        self.assertEqual(self.appels(), [], "le conteneur n'est pas appelé sur un refus")
        (self.racine / "tools" / "code").write_text("0")
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
        self.assertEqual(self.appels_matin(), ["runner"] * 2)   # R-20261102-3, -5 : plus de marge (deux lectures : refus puis passage)
        self.assertEqual(self.appels(), ["run --index"])   # mode complet : aucune suite nommée
        self.assertFalse(self.verrou.exists())

    def test_donnees_differentes_sans_effet_sur_un_lancement_filtre_ou_hors_session(self):
        self.assertEqual(self.lancer("alpha", PMZILLA_LAB_DATA=str(self.base / "ailleurs")).returncode, 0)
        self.refus_matin()
        self.assertEqual(self.lancer(session=None, PMZILLA_LAB_DATA=str(self.base / "ailleurs")).returncode, 0)

    def test_home_de_l_appelant_falsifie_ne_change_pas_le_defaut(self):
        faux = self.base / "faux"
        faux.mkdir()
        self.verifier_refus(self.lancer_staged_complet(HOME=str(faux), PMZILLA_LAB_DATA=str(faux / ".pmzilla-lab")), "PMZILLA_LAB_DATA différente")   # R-20261102-44, R-20261101-115
        resultat = self.lancer_staged_complet(HOME=str(faux), PMZILLA_LAB_DATA=None)
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertTrue(self.journal.exists(), "le journal est écrit sous le dossier du compte, pas sous HOME")
        self.assertFalse((faux / ".pmzilla-lab").exists())

    def test_lanceur_reel_lit_le_dossier_du_compte_par_getpwuid(self):
        texte = RUN_ALL.read_text(encoding="utf-8")
        code = "\n".join(l for l in texte.splitlines() if not l.lstrip().startswith("#"))
        self.assertIn(APPEL_GETPWUID, code)
        self.assertNotIn("$HOME", code)
        self.assertNotIn("${HOME", code)
        # La ligne d'origine est extraite du vrai lanceur et lancée seule, sous un HOME falsifié : elle rend le dossier personnel du compte.
        # Le lanceur lui-même n'est pas lancé (il écrirait dans le vrai journal du compte).
        lignes = [l for l in texte.splitlines() if APPEL_GETPWUID in l and not l.lstrip().startswith("#")]
        self.assertEqual(len(lignes), 1, lignes)
        faux = self.base / "faux"
        faux.mkdir()
        lue = subprocess.run(["bash", "-c", lignes[0].strip() + '\nprintf %s "$vrai_home"'], env={"HOME": str(faux), "PATH": os.environ["PATH"]},
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(lue.returncode, 0, lue.stderr)
        self.assertEqual(lue.stdout, pwd.getpwuid(os.getuid()).pw_dir)
        self.assertNotEqual(lue.stdout, str(faux))
        copie = (self.racine / "tests" / "run_all.sh").read_text(encoding="utf-8")
        self.assertNotIn(APPEL_GETPWUID, copie, "la copie des tests a bien remplacé l'appel par le faux dossier personnel")
        self.assertIn(f"printf %s {str(self.home)!r}", copie)

    # --- verrou de session : tous ses tests (pid d'un autre compte, plafond, reprise relue, reprise concurrente, trois lanceurs, kill -0 sous une autre
    # langue) sont retirés avec le verrou (tâche 6.7, R-20261029-31) ; test_aucun_verrou_n_est_pris_ni_laisse_par_un_lancement_de_session dit le contraire.

    def test_hors_session_rien_ne_change(self):
        self.refus_matin()
        resultat = self.lancer(session=None)
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertEqual(self.appels(), [])
        self.assertEqual(self.appels_matin(), [], "hors session, le module du matin n'est pas lu (assertion de main rétablie, classement 6.7)")
        self.assertFalse(self.journal.exists())
        hors = self.lancer("alpha", session=None, FINISH_LOCK_TOKEN="x", DBTEST_PORT="5432")
        self.assertNotEqual(hors.returncode, 6, hors.stdout)

    def test_marqueur_vide_compte_comme_une_session(self):
        # T2 : un marqueur vide scinde le lancement comme un marqueur posé (le conteneur est appelé) ; avec une variable refusée, code 6 ; le complet nu :
        # SessionPreuveParLeConteneur
        self.assertEqual(self.lancer("alpha", session="").returncode, 0)
        self.assertEqual(self.appels(), ["run --travail alpha"])
        self.assertEqual(self.lancer_staged_complet(session="", FINISH_LOCK_TOKEN="x").returncode, 6)
        self.refus_matin()   # main :3008 : un marqueur vide lit la garde du matin comme un marqueur posé
        self.assertEqual(self.lancer_staged_complet(session="").returncode, 6)   # R-20261102-44, R-20261101-115 ; le complet nu : SessionPreuveParLeConteneur

    def test_pmzilla_no_evals_garde_son_code_2_avant_la_garde(self):
        self.refus_matin()
        # () : complet NU explicite, code 2 AVANT le refus du conteneur ; --staged : cas ajouté (R-20261102-44, R-20261101-115)
        for arguments in ((), ("--staged",)):
            self.assertEqual(self.lancer(*arguments, PMZILLA_NO_EVALS="1").returncode, 2, arguments)
        self.assertEqual(self.appels(), [])

    # --- journal de session (Q17 : purge à un an)

    def test_journal_une_ligne_par_decision_sans_chemin(self):
        self.lancer_staged_complet()   # R-20261102-44, R-20261101-115
        self.refus_matin()   # main :3020 : le refus du matin est noté au journal
        self.lancer_staged_complet()
        (self.racine / "tools" / "code").write_text("0")
        (self.racine / "tools" / "ci_code").write_text("5")   # conteneur indisponible : code 9, une ligne « refusé »
        self.assertEqual(self.lancer_staged_complet().returncode, 9)
        (self.racine / "tools" / "ci_code").write_text("2")   # T2-3 : code inattendu du conteneur, une ligne « refusé »
        self.assertEqual(self.lancer_staged_complet().returncode, 1)
        self.lancer("alpha", FINISH_LOCK_TOKEN="x")
        lignes = self.lignes_journal()
        self.assertEqual(lignes[0], "date\tverdict\tmotif\tposte")
        corps = [l.split("\t") for l in lignes[1:]]
        self.assertEqual([(c[1], c[2]) for c in corps], [("lancé", "conteneur"), ("refusé", "matin"), ("refusé", "conteneur-indisponible"),
                                                           ("refusé", "conteneur-code-inattendu"), ("refusé", "FINISH_LOCK_TOKEN")])
        for champs in corps:
            self.assertRegex(champs[0], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
            self.assertEqual(champs[3], "espace")
        self.assertNotIn(str(self.base), self.journal.read_text())

    def test_journal_purge_les_lignes_de_plus_d_un_an(self):
        self.journal.parent.mkdir(parents=True)
        self.journal.write_text("date\tverdict\tmotif\tposte\n2020-01-02T08:00:00\tlancé\tcomplet\tespace\n"
                                f"{time.strftime('%Y-%m-%d')}T00:00:01\trefusé\tmatin\tespace\n")
        self.lancer_staged_complet()   # R-20261102-44, R-20261101-115
        lignes = self.lignes_journal()
        self.assertEqual(lignes[0], "date\tverdict\tmotif\tposte")
        self.assertFalse(any(l.startswith("2020-") for l in lignes), lignes)
        self.assertEqual(len(lignes), 3, lignes)

    def test_journal_illisible_n_empeche_pas_le_lancement(self):
        self.journal.parent.mkdir(parents=True)
        self.journal.mkdir()   # un dossier à la place du fichier : écriture impossible, le lancement continue
        resultat = self.lancer_staged_complet()   # R-20261102-44, R-20261101-115
        self.assertEqual(resultat.returncode, 0, resultat.stdout)


PHRASE_VOIE_CONTENEUR = "la preuve passe par le conteneur (bash tools/ci_local.sh run <branche>, puis bash tests/run_all.sh --mac)"
PHRASE_COMPLET_REFUSE = "run_all : lancement complet refusé en session : " + PHRASE_VOIE_CONTENEUR
PHRASE_BRANCHE_REFUSEE = "run_all : --branch refusé en session : " + PHRASE_VOIE_CONTENEUR
PHRASE_PORTABLE_REFUSE = "run_all : --portable refusé en session : " + PHRASE_VOIE_CONTENEUR


class SessionPreuveParLeConteneur(unittest.TestCase):
    """tooling-proof-in-container, T1, D3 (R-20261102-40, R-20261102-44) : en session, un lancement complet NU et --branch donnent le code 6
    avec la phrase exacte, sans suite, sans empreinte écrite ni effacée, sans ligne de durées. Un --staged qui devient complet passe, depuis T2, par le
    mode complet du conteneur (le verrou « un seul runner complet de session » est retiré, Q332 (a)). Hors session, ciblé et filtré : rien ne change.

    Le lanceur est copié dans une fausse racine, avec un faux dossier personnel (comme SessionClaudeCode) : le vrai dossier de données n'est pas touché."""

    def setUp(self):
        self.base = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.base, True)
        self.racine = self.base / "depot"
        (self.racine / "tests" / "alpha").mkdir(parents=True)
        (self.racine / "tests" / "alpha" / "test_alpha.py").write_text(SUITE_OK)
        (self.racine / "tests" / "suites_shell.txt").write_text("# aucune suite shell dans la fausse racine\n")
        (self.racine / "tests" / "suites_mac.txt").write_text("# aucune\n")
        self.home = self.base / "home"
        self.home.mkdir()
        texte = RUN_ALL.read_text(encoding="utf-8")
        self.assertIn(APPEL_GETPWUID, texte)
        texte = texte.replace("\nSUITES_NPM=(mothra:mothra)\n", "\nSUITES_NPM=()\n")
        (self.racine / "tests" / "run_all.sh").write_text(texte.replace(APPEL_GETPWUID, f"printf %s {str(self.home)!r}"), encoding="utf-8")
        (self.racine / "tools").mkdir()
        shutil.copy(RUN_ALL.parent.parent / "tools" / "preuve_arbre.py", self.racine / "tools" / "preuve_arbre.py")
        (self.racine / "tools" / "ci_local.sh").write_text(FAUX_CI_SESSION)   # T2 : le --staged complet et les suites portables vont au conteneur
        (self.racine / "tools" / "morning_state.sh").write_text(FAUX_MATIN)   # pour le --staged complet, qui garde la garde du matin (T2-1 (a))
        self.donnees = self.home / ".pmzilla-lab"
        self.durees = self.base / "durees.tsv"
        subprocess.run(["git", "init", "-q"], cwd=self.racine, check=True)
        self.empreintes = {nom: self.racine / ".git" / nom for nom in ("pmzilla-run-all-ok", "pmzilla-run-targeted-ok", "pmzilla-run-branch-ok")}
        for nom, chemin in self.empreintes.items():
            chemin.write_text("a-conserver-" + nom)

    def lancer(self, *arguments, session="1", **variables):
        retirees = ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS", "RUN_ALL_ROOT", "FINISH_LOCK_TOKEN", "DBTEST_PORT", "CLAUDECODE",
                    "PMZILLA_FINISH_LOCK_MAX_AGE", "PMZILLA_LAB_DATA")
        env = {k: v for k, v in os.environ.items() if k not in retirees}
        env.update({"RUN_ALL_DEPS": "", "PMZILLA_LAB_DATA": str(self.donnees), "RUN_ALL_DURATIONS": str(self.durees)})
        if session is not None:
            env["CLAUDECODE"] = session
        env.update(variables)
        return subprocess.run(["bash", str(self.racine / "tests" / "run_all.sh"), *arguments], env=env, cwd=self.racine,
                              capture_output=True, text=True, timeout=120)

    def poser_selecteur(self, texte):
        (self.racine / "tools" / "select_suites.py").write_text(texte)

    def verifier_refus(self, resultat, phrase, exact=False):
        self.assertEqual(resultat.returncode, 6, resultat.stdout + resultat.stderr)
        self.assertIn(phrase + "\n", resultat.stdout)
        if exact:   # refus du conteneur : la phrase est toute la sortie
            self.assertEqual(resultat.stdout, phrase + "\n")
        self.assertNotIn("TOTAL", resultat.stdout)
        self.assertNotRegex(resultat.stdout, r"alpha\s+\d+ tests")
        self.assertFalse(self.durees.exists(), "aucune ligne de durées sur un refus")
        for nom, chemin in self.empreintes.items():
            self.assertEqual(chemin.read_text(), "a-conserver-" + nom, f"{nom} : ni écrite ni effacée")

    def verifier_refus_conteneur(self, resultat, phrase):
        self.verifier_refus(resultat, phrase, exact=True)
        self.assertFalse((self.racine / "tools" / "ci_appels").exists(), "le script du conteneur n'est pas appelé sur un refus du conteneur (T2 : la garde du runner n'existe plus)")
        self.assertFalse((self.racine / "tools" / "appels").exists(), "le module du matin n'est pas appelé sur un refus du conteneur")

    def test_lancement_complet_refuse_en_session_phrase_exacte(self):
        self.verifier_refus_conteneur(self.lancer(), PHRASE_COMPLET_REFUSE)

    def test_marqueur_vide_compte_comme_une_session(self):
        self.verifier_refus_conteneur(self.lancer(session=""), PHRASE_COMPLET_REFUSE)

    def test_lancement_complet_refuse_meme_avec_un_autre_dossier_de_donnees(self):
        self.verifier_refus_conteneur(self.lancer(PMZILLA_LAB_DATA=str(self.base / "ailleurs")), PHRASE_COMPLET_REFUSE)

    def test_le_refus_du_complet_nu_ne_prend_pas_le_verrou_de_session(self):
        self.verifier_refus_conteneur(self.lancer(), PHRASE_COMPLET_REFUSE)
        self.assertFalse((self.donnees / "verrous").exists())

    def test_branch_refuse_en_session_phrase_exacte(self):
        self.verifier_refus_conteneur(self.lancer("--branch"), PHRASE_BRANCHE_REFUSEE)

    def test_branch_refuse_en_session_sans_lancer_le_selecteur(self):
        self.poser_selecteur("open('selecteur-lance', 'w').write('x')\n")
        self.verifier_refus_conteneur(self.lancer("--branch"), PHRASE_BRANCHE_REFUSEE)
        self.assertFalse((self.racine / "selecteur-lance").exists())

    def test_gel_actif_le_complet_nu_et_branch_sortent_en_6_pas_en_4(self):
        # un verrou de fin vivant : le refus du conteneur vient avant la lecture du gel (code 4), comme les autres refus de session
        gel = self.racine / ".git" / "pmzilla-fin-en-cours"
        gel.mkdir()
        (gel / "pid").write_text(str(os.getpid()))
        (gel / "branche").write_text("une-branche")
        (gel / "jeton").write_text("jeton-de-test")
        self.verifier_refus_conteneur(self.lancer(), PHRASE_COMPLET_REFUSE)
        self.verifier_refus_conteneur(self.lancer("--branch"), PHRASE_BRANCHE_REFUSEE)
        gelee = self.lancer("alpha")
        self.assertEqual(gelee.returncode, 4, "un lancement filtré reste gelé (code 4)")

    # --- R-20261102-44 (Q332 (a)) puis T2 : un --staged qui devient complet passe par le mode complet du conteneur, sans verrou de session

    def test_staged_complet_en_session_passe_par_le_conteneur_sans_verrou(self):
        # sélecteur absent, en échec, « exécution complète exigée » ou sélection vide : le lancement devient complet, appelle le conteneur en mode complet
        for selecteur in (None, "raise SystemExit(7)\n", FAUX_SELECTEUR_COMPLET, "print('select_suites : aucune suite à lancer')\n"):
            if selecteur is not None:
                self.poser_selecteur(selecteur)
            (self.racine / "tools" / "ci_appels").unlink(missing_ok=True)
            resultat = self.lancer("--staged")
            self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
            self.assertNotIn("refusé en session", resultat.stdout)
            self.assertEqual((self.racine / "tools" / "ci_appels").read_text().splitlines(), ["run --index"])
            self.assertFalse((self.donnees / "verrous").exists(), "plus de verrou de session")
            for nom, chemin in self.empreintes.items():
                if nom == "pmzilla-run-all-ok":
                    self.assertEqual(chemin.read_text(), "a-conserver-" + nom, "l'empreinte complète n'est jamais écrite en session")

    def test_staged_complet_en_session_refuse_par_la_garde_du_matin_sans_effacer_d_empreinte(self):
        self.poser_selecteur(FAUX_SELECTEUR_COMPLET)
        (self.racine / "tools" / "code").write_text("1")
        resultat = self.lancer("--staged")
        self.verifier_refus(resultat, "run_all : session Claude Code : lancement complet refusé : veille ou sauvegarde du jour en cours "
                                      "(morning_state : ligne du faux module)")   # restauré de main :3182 (tâche 3.1 de T1)
        self.assertFalse((self.racine / "tools" / "ci_appels").exists(), "le conteneur n'est pas appelé sur un refus du matin")

    def test_portable_refuse_en_session_phrase_exacte(self):
        # T2-2 (a), décision de l'auteur du 2026-11-04 : même forme que le complet nu et --branch (T1)
        self.verifier_refus_conteneur(self.lancer("--portable"), PHRASE_PORTABLE_REFUSE)

    def test_portable_refuse_en_session_avant_le_gel_et_meme_avec_un_marqueur_vide(self):
        gel = self.racine / ".git" / "pmzilla-fin-en-cours"
        gel.mkdir()
        (gel / "pid").write_text(str(os.getpid()))
        (gel / "branche").write_text("une-branche")
        (gel / "jeton").write_text("jeton-de-test")
        self.verifier_refus_conteneur(self.lancer("--portable"), PHRASE_PORTABLE_REFUSE)
        shutil.rmtree(gel)
        self.verifier_refus_conteneur(self.lancer("--portable", session=""), PHRASE_PORTABLE_REFUSE)

    def test_portable_hors_session_ne_change_pas(self):
        resultat = self.lancer("--portable", session=None)
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
        self.assertNotIn("refusé en session", resultat.stdout)

    def test_les_refus_sont_notes_au_journal_de_session_sans_chemin(self):
        self.lancer()
        self.lancer("--branch")
        self.lancer("--portable")
        journal = self.donnees / "journal" / "run-all-session.tsv"
        lignes = journal.read_text().splitlines()
        self.assertEqual([tuple(l.split("\t")[1:3]) for l in lignes[1:]],
                         [("refusé", "conteneur-complet"), ("refusé", "conteneur-branche"), ("refusé", "conteneur-portable")])
        self.assertNotIn(str(self.base), journal.read_text())

    def test_hors_session_un_lancement_complet_n_est_pas_refuse_par_ce_controle(self):
        resultat = self.lancer(session=None)
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
        self.assertNotIn("refusé en session", resultat.stdout)
        self.assertIn("TOTAL : 2 tests dans 1 suites · tous réussis", resultat.stdout)

    def test_hors_session_branch_garde_son_propre_controle_et_pas_la_phrase_de_session(self):
        resultat = self.lancer("--branch", session=None)
        self.assertEqual(resultat.returncode, 2, resultat.stdout)   # pas de branche de travail propre dans la fausse racine
        self.assertNotIn("refusé en session", resultat.stdout)

    def test_hors_session_staged_devenu_complet_tourne(self):
        self.poser_selecteur(FAUX_SELECTEUR_COMPLET)
        resultat = self.lancer("--staged", session=None)
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
        self.assertNotIn("refusé en session", resultat.stdout)

    def test_filtre_mac_et_cible_en_session_inchanges(self):
        self.poser_selecteur(FAUX_SELECTEUR)   # le sélecteur choisit une suite : le lancement --staged reste ciblé
        # T2 (revue de T1, trou 1) : le code exact de chaque forme permise ; --mac sur la liste vide de la fausse racine donne 2 (« Aucune suite trouvée »).
        # --portable n'en fait plus partie : refusé en session (T2-2), test_portable_refuse_en_session_phrase_exacte
        for arguments, code in ((("alpha",), 0), (("--mac",), 2), (("--staged",), 0)):
            resultat = self.lancer(*arguments)
            self.assertEqual(resultat.returncode, code, (arguments, resultat.stdout))
            self.assertNotIn("refusé en session", resultat.stdout, arguments)


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


SUITES_SHELL_D_AVANT = {   # la liste attendue des suites shell (celle qui tenait sur une ligne de run_all.sh avant R-130, tenue à jour) : (chemin, nom, interprète)
    ("tests/hooks/test_pre_commit.sh", "hooks", "sh"), ("tests/hooks/test_post_commit.sh", "post-commit", "sh"),
    ("tests/hooks/test_commit_msg.sh", "commit-msg", "sh"), ("tests/hooks/test_pre_commit_green.sh", "pre-commit-green", "sh"),
    ("tests/hooks/test_pre_push.sh", "pre-push", "sh"), ("tests/hooks/test_lock_hooks.sh", "lock-hooks", "sh"),
    ("tests/hooks/test_echec_ferme.sh", "echec-ferme", "sh"), ("tests/hooks/test_interpreteur_crochets.sh", "interpreteur-crochets", "sh"),
    ("tests/evals_auto/test_evals_auto.sh", "evals_auto", "sh"), ("tests/installation/test_install_links.sh", "installation", "zsh"),
    ("tests/installation/test_install_hooks.sh", "install_hooks", "sh"), ("tests/db_scripts/test_db_scripts.sh", "db_scripts", "bash"),
    ("tests/db_scripts/test_dbtest.sh", "dbtest", "bash"), ("tests/offsite_backup/test_offsite_backup.sh", "offsite_backup", "bash"),
    ("tests/worktree/test_worktree.sh", "worktree", "bash"),
    ("tests/run_worktree/test_run_worktree.sh", "run_worktree", "bash"), ("tests/morning_state/test_morning_state.sh", "morning_state", "bash"),
    ("tests/ci_local/test_ci_local.sh", "ci_local", "bash"), ("tests/branch_sync/test_branch_sync.sh", "branch_sync", "bash"),
    ("tests/fin_piege/test_fin_piege.sh", "fin_piege", "bash"),
}


class ListeDesSuitesShell(unittest.TestCase):
    """R-130 : les suites shell du lanceur sont dans tests/suites_shell.txt, une ligne « chemin nom interprète » par suite, triées par
    chemin ; le lanceur les lit dans l'ordre du fichier et refuse (code 2, numéro de ligne) une ligne mal formée."""
    suite = Lanceur.suite
    shell = Lanceur.shell
    lancer = Lanceur.lancer

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)

    def liste(self, texte):
        (self.racine / "tests").mkdir(parents=True, exist_ok=True)
        (self.racine / LISTE_SHELL).write_text(texte, encoding="utf-8")

    def test_le_fichier_est_trie_par_chemin(self):
        chemins = scripts_shell()
        self.assertEqual(chemins, sorted(chemins), "tests/suites_shell.txt doit rester trié par chemin")

    def test_ni_chemin_ni_nom_en_double(self):
        entrees = suites_shell_du_depot()
        self.assertEqual(len({c for c, _, _ in entrees}), len(entrees))
        self.assertEqual(len({n for _, n, _ in entrees}), len(entrees))

    def test_meme_liste_qu_avant(self):
        self.assertEqual(set(suites_shell_du_depot()), SUITES_SHELL_D_AVANT)
        self.assertEqual(len(suites_shell_du_depot()), len(SUITES_SHELL_D_AVANT))

    def test_chaque_script_liste_existe(self):
        for chemin in scripts_shell():
            self.assertTrue((RUN_ALL.parents[1] / chemin).is_file(), chemin)

    def test_le_lanceur_rend_les_suites_dans_l_ordre_du_fichier(self):
        self.liste("# commentaire\n\ntests/zeta/test_zeta.sh zeta bash   # raison\ntests/alpha/test_alpha.sh alpha bash\n")
        for relatif in ("zeta/test_zeta.sh", "alpha/test_alpha.sh"):
            self.shell(relatif, SHELL_OK)
        resultat = self.lancer()
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertEqual(re.findall(r"(?m)^(\S+) \(shell\)", resultat.stdout), ["zeta", "alpha"])

    def test_le_lanceur_lance_les_suites_du_depot_dans_l_ordre_du_fichier(self):
        for chemin in scripts_shell():
            self.shell(chemin[len("tests/"):], SHELL_OK)
        resultat = self.lancer()
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertEqual(re.findall(r"(?m)^(\S+) \(shell\)", resultat.stdout), [nom for _, nom, _ in suites_shell_du_depot()])

    def test_interprete_de_la_ligne_utilise(self):
        self.liste("tests/zeta/test_zeta.sh zeta zsh\n")
        self.shell("zeta/test_zeta.sh", 'echo "interprete=${ZSH_VERSION:+zsh}"\necho "2 réussis, 0 échec(s)"\n')
        resultat = self.lancer("-v")
        self.assertIn("interprete=zsh", resultat.stdout)

    def test_ligne_mal_formee_refusee_en_2_avec_son_numero(self):
        mal_formees = ["tests/zeta/test_zeta.sh zeta", "tests/zeta/test_zeta.sh zeta bash extra", "tests/zeta/test_zeta.sh zeta fish",
                       "zeta/test_zeta.sh zeta bash", "tests/zeta/test_zeta.py zeta bash", "tests/zeta/test_zeta.sh ze:ta bash"]
        for ligne in mal_formees:
            with self.subTest(ligne=ligne):
                self.liste(f"# en-tête\n\n{ligne}\n")
                resultat = self.lancer()
                self.assertEqual(resultat.returncode, 2, resultat.stdout)
                self.assertIn(f"run_all : {LISTE_SHELL}, ligne 3 mal formée", resultat.stdout)
                self.assertNotIn("TOTAL", resultat.stdout)

    def test_liste_absente_refusee_en_2(self):
        (self.racine / "tests").mkdir()
        shutil.copy(RUN_ALL, self.racine / "tests" / "run_all.sh")   # ni la racine ni le dossier du lanceur n'ont la liste
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS")}
        env.update({"RUN_ALL_ROOT": str(self.racine), "RUN_ALL_DEPS": ""})
        resultat = subprocess.run(["bash", str(self.racine / "tests" / "run_all.sh")], env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(resultat.returncode, 2, resultat.stdout)
        self.assertIn(f"run_all : liste des suites shell illisible ({LISTE_SHELL})", resultat.stdout)


SUITES_NPM = "mothra:mothra"   # la valeur de RUN_ALL_SUITES_NPM par défaut des tests de la classe SuiteNpm
FAUX_NODE = '#!/bin/bash\necho "${FAUX_NODE_VERSION:-v26.12.1}"\n'
# Faux npm : note ses arguments et son environnement, ne contacte rien, rend la sortie du fichier FAUX_NPM_SORTIE avec le code FAUX_NPM_CODE.
FAUX_NPM = """#!/bin/bash
{
  echo "args=$*"
  echo "cwd=$(pwd -P)"
  echo "tmpdir=${TMPDIR:-}"
  echo "stdin=$(cat | wc -c | tr -d ' ')"
  echo "offline=${npm_config_offline:-}"
  printf 'db=%s\\n' "$(env | grep -E '^(PMZILLA_LAB_DB_[A-Z_]*|MOTHRA_DB_[A-Z_]*|DBTEST_PORT)=.+' | cut -d= -f1 | sort | tr '\\n' ' ')"
} >> "$FAUX_NPM_JOURNAL"
cat "$FAUX_NPM_SORTIE"
[ -z "${FAUX_NPM_DORT:-}" ] || sleep "$FAUX_NPM_DORT"
exit "${FAUX_NPM_CODE:-0}"
"""
TAP_DEUX_SAUTS = ("TAP version 13\nok 1 - alpha\nok 2 - beta # SKIP\nok 3 - gamma # SKIP justification\nok 4 - delta\nok 5 - epsilon\n"
                  "1..5\n# tests 5\n# pass 3\n# fail 0\n# cancelled 0\n# skipped 2\n# todo 0\n")
SPEC_UN_SAUT_ET_UN_ECHEC = ("▶ groupe\n  ✔ alpha (0.5ms)\n  ✖ beta (1.2ms)\n  ﹣ gamma (0.1ms) # SKIP\n▶ groupe (3ms)\n"
                            "ℹ tests 3\nℹ suites 1\nℹ pass 1\nℹ fail 1\nℹ cancelled 0\nℹ skipped 1\nℹ todo 0\n")
LOT_UN_SAUT_DEUX_LIGNES = ("TAP version 13\nok 1 - alpha\nok 2 - beta # SKIP\n# tests 2\n# pass 1\n# fail 0\n# skipped 1\n"
                           "TAP version 13\nok 1 - delta\nok 2 - epsilon # SKIP\n# tests 2\n# pass 1\n# fail 0\n# skipped 1\n")


class SuiteNpm(unittest.TestCase):
    """Mothra-slices, groupe 3 (design D9) : le genre de suite « npm », déclaré par la ligne SUITES_NPM=(<dossier>:<nom>) de tests/run_all.sh (les
    tests la remplacent par RUN_ALL_SUITES_NPM). Faux espace de travail, faux Node, faux npm : aucun vrai Node, aucun paquet, aucun réseau."""

    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.bin = self.racine / "faux-bin"
        self.bin.mkdir()
        for nom, texte in (("node", FAUX_NODE), ("npm", FAUX_NPM)):
            (self.bin / nom).write_text(texte)
            (self.bin / nom).chmod(0o755)
        self.journal = self.racine / "npm-journal"
        self.sortie_npm = self.racine / "npm-sortie"
        self.sortie_npm.write_text(TAP_DEUX_SAUTS)
        (self.racine / "tests").mkdir()
        self.espace()

    def espace(self, verrou=None, installe="identique", version="26.12.1"):
        """Un faux espace de travail npm : fichier de version, verrou, et node_modules (identique, different, absent)."""
        dossier = self.racine / "mothra"
        shutil.rmtree(dossier, True)
        (dossier / "node_modules").mkdir(parents=True)
        (dossier / ".node-version").write_text(version + "\n")
        verrou = verrou or {"lockfileVersion": 3, "packages": {
            "": {"name": "mothra"},
            "contract": {"name": "@mothra/contract"},
            "node_modules/@mothra/contract": {"resolved": "contract", "link": True},
            "node_modules/a": {"version": "1.0.0", "resolved": "https://registry.npmjs.org/a/-/a-1.0.0.tgz", "integrity": "sha512-aaa"},
            "node_modules/b": {"version": "2.0.0", "integrity": "sha512-bbb", "optional": True},
        }}
        (dossier / "package-lock.json").write_text(json.dumps(verrou))
        if installe == "absent":
            shutil.rmtree(dossier / "node_modules")
            return
        cache = json.loads(json.dumps(verrou))
        cache["packages"] = {k: v for k, v in cache["packages"].items() if k and not v.get("optional")}
        if installe == "different":
            cache["packages"]["node_modules/a"]["version"] = "1.0.1"
        elif installe == "manquant":
            del cache["packages"]["node_modules/a"]
        elif installe == "en_trop":
            cache["packages"]["node_modules/z"] = {"version": "9.0.0", "integrity": "sha512-zzz"}
        elif installe == "integrite":
            cache["packages"]["node_modules/a"]["integrity"] = "sha512-autre"
        (dossier / "node_modules" / ".package-lock.json").write_text(json.dumps(cache))
        for chemin, entree in cache["packages"].items():
            if "node_modules/" in chemin and not entree.get("link"):   # le contrôle exige aussi le package.json de chaque paquet installé
                (dossier / chemin).mkdir(parents=True, exist_ok=True)
                (dossier / chemin / "package.json").write_text("{}")

    def lancer(self, *arguments, **variables):
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS", "DBTEST_PORT")
               and not k.startswith(("PMZILLA_LAB_DB_", "MOTHRA_DB_"))}
        env.update({"RUN_ALL_ROOT": str(self.racine), "RUN_ALL_DEPS": "", "RUN_ALL_SUITES_NPM": SUITES_NPM,
                    "PATH": f"{self.bin}{os.pathsep}{env['PATH']}", "FAUX_NPM_JOURNAL": str(self.journal), "FAUX_NPM_SORTIE": str(self.sortie_npm)}, **variables)
        return subprocess.run(["bash", str(RUN_ALL), *arguments], env=env, capture_output=True, text=True, timeout=120,
                              stdin=subprocess.DEVNULL, cwd=self.racine)

    def appels_npm(self):
        return self.journal.read_text().splitlines() if self.journal.exists() else []

    def suite_python(self, nom):
        dossier = self.racine / "tests" / nom
        dossier.mkdir(parents=True)
        (dossier / f"test_{nom}.py").write_text(SUITE_DEUX_SAUTS)

    # --- la suite verte, ses sauts, ses lignes
    def test_suite_verte_avec_deux_sauts(self):
        resultat = self.lancer("-v", "mothra")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertRegex(resultat.stdout, r"mothra \(npm\)\s+5 tests · OK \(sautés=2\) · \d+,\d s\n")
        self.assertIn("5 réussis, 0 échec(s)", resultat.stdout.splitlines())
        self.assertEqual([l for l in resultat.stdout.splitlines() if l.startswith("saut : ")], ["saut : beta", "saut : gamma"])
        self.assertIn("Tests sautés : 2 (suites Python 0, branches shell 0, suites npm 2)", resultat.stdout.splitlines())
        self.assertIn("TOTAL : 5 tests dans 1 suites · tous réussis", resultat.stdout)

    def test_sans_option_verbeuse_la_sortie_de_la_suite_n_est_pas_reprise(self):
        resultat = self.lancer("mothra")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertNotIn("saut : beta", resultat.stdout)

    def test_npm_test_lance_dans_le_dossier_de_la_suite_sans_installation_ni_reseau(self):
        resultat = self.lancer("mothra")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        appels = [l for l in self.appels_npm() if l.startswith("args=")]
        self.assertEqual(appels, ["args=test"])
        self.assertIn(f"cwd={(self.racine / 'mothra').resolve()}", self.appels_npm())
        self.assertIn("offline=true", self.appels_npm())

    def test_sortie_au_format_spec_un_saut_et_un_echec(self):
        self.sortie_npm.write_text(SPEC_UN_SAUT_ET_UN_ECHEC)
        resultat = self.lancer("mothra", FAUX_NPM_CODE="1")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertRegex(resultat.stdout, r"mothra \(npm\)\s+3 tests · ÉCHEC \(code 1, 1 échec\(s\), sautés=1\) · \d+,\d s\n")
        self.assertIn("saut : gamma", resultat.stdout)
        self.assertIn("Tests sautés : 1 (suites Python 0, branches shell 0, suites npm 1)", resultat.stdout.splitlines())
        self.assertIn("1 suite(s) en échec : mothra", resultat.stdout)

    def test_les_bilans_de_la_racine_et_des_paquets_s_additionnent(self):
        self.sortie_npm.write_text(LOT_UN_SAUT_DEUX_LIGNES)
        resultat = self.lancer("-v", "mothra")
        self.assertRegex(resultat.stdout, r"mothra \(npm\)\s+4 tests · OK \(sautés=2\)")
        self.assertIn("4 réussis, 0 échec(s)", resultat.stdout.splitlines())

    def test_code_zero_sans_aucun_bilan_est_un_echec_nomme(self):
        self.sortie_npm.write_text("rien de lisible\n")
        resultat = self.lancer("mothra")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertIn("sortie de npm test sans bilan", resultat.stdout)

    # --- les échecs nommés
    def test_dossier_de_la_suite_absent(self):
        shutil.rmtree(self.racine / "mothra")
        resultat = self.lancer("mothra")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertIn("suite npm absente : mothra", resultat.stdout)
        self.assertEqual(self.appels_npm(), [])

    def test_node_modules_absent(self):
        self.espace(installe="absent")
        resultat = self.lancer("mothra")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertIn("dépendances npm absentes ou différentes du verrou : mothra (lancer npm ci dans mothra/)", resultat.stdout)
        self.assertEqual(self.appels_npm(), [])   # ni installation ni test : npm n'est pas appelé

    def test_node_modules_different_du_verrou(self):
        for installe in ("different", "manquant", "en_trop", "integrite"):
            with self.subTest(installe=installe):
                self.espace(installe=installe)
                resultat = self.lancer("mothra")
                self.assertEqual(resultat.returncode, 1, resultat.stdout)
                self.assertIn("dépendances npm absentes ou différentes du verrou : mothra (lancer npm ci dans mothra/)", resultat.stdout)
                self.assertEqual(self.appels_npm(), [])

    def test_paquet_optionnel_non_installe_n_est_pas_un_ecart(self):
        resultat = self.lancer("mothra")   # « b » est optionnel dans le verrou et absent de node_modules
        self.assertEqual(resultat.returncode, 0, resultat.stdout)

    def test_verrou_illisible_est_un_echec_nomme(self):
        (self.racine / "mothra" / "package-lock.json").write_text("{ pas du json")
        resultat = self.lancer("mothra")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertIn("dépendances npm absentes ou différentes du verrou : mothra", resultat.stdout)

    def test_node_different_de_la_version_fixee(self):
        resultat = self.lancer("mothra", FAUX_NODE_VERSION="v25.9.0")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertIn("Node de Mothra différent de la version fixée", resultat.stdout)
        self.assertEqual(self.appels_npm(), [])   # la suite n'est pas lancée

    def test_version_du_fichier_avec_un_v_ou_des_blancs_est_comparee_sans_eux(self):
        self.espace(version="v26.12.1")
        self.assertEqual(self.lancer("mothra").returncode, 0)

    def test_node_introuvable_est_le_meme_echec_nomme(self):
        (self.bin / "node").unlink()
        resultat = self.lancer("mothra", PATH=f"{self.bin}{os.pathsep}/usr/bin{os.pathsep}/bin")   # sans le Node de la machine
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertIn("Node de Mothra différent de la version fixée", resultat.stdout)

    # --- le relais
    def test_delai_depasse_arrete_la_suite(self):
        resultat = self.lancer("mothra", RUN_ALL_SUITE_TIMEOUT="1", FAUX_NPM_DORT="60")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertRegex(resultat.stdout, r"mothra \(npm\)\s+\? tests · ÉCHEC : délai dépassé \(1 s\) · \d+,\d s\n")

    def test_entree_fermee_et_dossier_temporaire_propre(self):
        tmp_lanceur = self.racine / "tmp-lanceur"
        tmp_lanceur.mkdir()
        resultat = self.lancer("mothra", TMPDIR=str(tmp_lanceur))
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        journal = self.appels_npm()
        self.assertIn("stdin=0", journal)
        tmpdir = next(l for l in journal if l.startswith("tmpdir="))[len("tmpdir="):]
        self.assertTrue(tmpdir.startswith(str(tmp_lanceur)) and "pmzilla-suites." in tmpdir, tmpdir)
        self.assertNotEqual(tmpdir, str(tmp_lanceur))
        self.assertFalse(Path(tmpdir).exists())   # retiré à la fin

    def test_variables_de_base_retirees_sauf_dans_le_passage_de_la_base_jetable(self):
        bases = {"PMZILLA_LAB_DB_URL": "postgresql://x@127.0.0.1:5432/p", "PMZILLA_LAB_DB_PORT": "5432", "MOTHRA_DB_URL": "postgresql://x@127.0.0.1:5432/m"}
        self.lancer("mothra", **bases)
        self.assertIn("db=", self.appels_npm())
        self.journal.unlink()
        self.lancer("mothra", DBTEST_PORT="55432", **bases)
        self.assertIn("db=DBTEST_PORT MOTHRA_DB_URL PMZILLA_LAB_DB_PORT PMZILLA_LAB_DB_URL ", self.appels_npm())

    def test_ligne_de_duree_de_type_npm(self):
        durees = self.racine / "durees.tsv"
        resultat = self.lancer("mothra", RUN_ALL_DURATIONS=str(durees))
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        lignes = [l.split("\t") for l in durees.read_text().splitlines()[1:]]
        self.assertEqual([(l[4], l[5], l[8]) for l in lignes], [("mothra", "npm", "ok")])

    # --- la ligne des tests sautés
    def test_sans_suite_npm_la_ligne_des_sautes_est_celle_d_avant(self):
        self.suite_python("alpha")
        resultat = self.lancer("alpha")
        self.assertIn("Tests sautés : 2 (suites Python 2, branches shell 0)", resultat.stdout.splitlines())
        self.assertNotIn("suites npm", resultat.stdout)

    def test_avec_une_suite_python_et_la_suite_npm(self):
        self.suite_python("alpha")
        resultat = self.lancer("alpha", "mothra")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("Tests sautés : 4 (suites Python 2, branches shell 0, suites npm 2)", resultat.stdout.splitlines())

    def test_suite_npm_et_suite_python_de_meme_nom_sont_deux_suites(self):
        self.suite_python("mothra")
        resultat = self.lancer("mothra")
        self.assertRegex(resultat.stdout, r"\nmothra\s+3 tests · OK \(skipped=2\)")
        self.assertRegex(resultat.stdout, r"\nmothra \(npm\)\s+5 tests · OK \(sautés=2\)")

    def test_sans_liste_aucune_suite_npm(self):
        self.suite_python("alpha")
        resultat = self.lancer("alpha", RUN_ALL_SUITES_NPM="")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertNotIn("npm", resultat.stdout)
        self.assertEqual(self.appels_npm(), [])

    def test_lancement_complet_lance_la_suite_npm(self):
        self.suite_python("alpha")
        for chemin in scripts_shell():
            (self.racine / chemin).parent.mkdir(parents=True, exist_ok=True)
            (self.racine / chemin).write_text(SHELL_OK)
        resultat = self.lancer()
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertRegex(resultat.stdout, r"mothra \(npm\)\s+5 tests · OK")

    # --- la sortie de npm, le bilan
    def test_sortie_de_npm_imprimee_en_direct_un_delai_depasse_la_montre(self):
        resultat = self.lancer("mothra", RUN_ALL_SUITE_TIMEOUT="1", FAUX_NPM_DORT="60")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertIn("ÉCHEC : délai dépassé (1 s)", resultat.stdout)
        self.assertIn("ok 1 - alpha", resultat.stdout)   # la sortie de npm, déjà écrite quand le délai tombe

    def test_tests_zero_n_est_pas_vert(self):
        self.sortie_npm.write_text("TAP version 13\n1..0\n# tests 0\n# pass 0\n# fail 0\n# cancelled 0\n# skipped 0\n# todo 0\n")
        resultat = self.lancer("mothra")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertRegex(resultat.stdout, r"mothra \(npm\)\s+\? tests · ÉCHEC : npm test n'a lancé aucun test")

    def test_bilan_reussis_est_tests_moins_echecs_et_annules(self):
        self.sortie_npm.write_text("TAP version 13\nok 1 - alpha\nnot ok 2 - beta\nok 3 - gamma # SKIP\n"
                                   "# tests 4\n# pass 1\n# fail 1\n# cancelled 1\n# skipped 1\n# todo 0\n")
        resultat = self.lancer("-v", "mothra", FAUX_NPM_CODE="1")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertIn("    2 réussis, 2 échec(s)", resultat.stdout.splitlines())   # une suite en échec indente sa sortie
        self.assertRegex(resultat.stdout, r"mothra \(npm\)\s+4 tests · ÉCHEC \(code 1, 2 échec\(s\), sautés=1\)")

    def test_une_ligne_de_bilan_imprimee_par_un_test_n_est_pas_comptee(self):
        self.sortie_npm.write_text("TAP version 13\n# pass 99\n# fail 7\n    # fail 5\nok 1 - alpha\n# tests 1\n# pass 1\n# fail 0\n# cancelled 0\n"
                                   "# skipped 0\n# todo 0\n# pass 40\n")
        resultat = self.lancer("-v", "mothra")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("1 réussis, 0 échec(s)", resultat.stdout.splitlines())
        self.assertRegex(resultat.stdout, r"mothra \(npm\)\s+1 tests · OK")

    def test_bilan_au_format_spec_n_est_lu_qu_en_tete_de_ligne(self):
        self.sortie_npm.write_text("▶ groupe\n  ✔ alpha (0.5ms)\n  ℹ pass 12\n▶ groupe (3ms)\nℹ tests 1\nℹ suites 1\nℹ pass 1\nℹ fail 0\nℹ cancelled 0\n"
                                   "ℹ skipped 0\nℹ todo 0\nℹ duration_ms 12.5\n")
        resultat = self.lancer("-v", "mothra")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("1 réussis, 0 échec(s)", resultat.stdout.splitlines())

    # --- la déclaration
    def test_ligne_mal_formee_refusee_en_2_avec_son_numero(self):
        for entree in ("mothra", "mothra:", ":mothra", "mothra:mothra:extra", "mo.thra:mothra", "../mothra:mothra", "/mothra:mothra"):
            with self.subTest(entree=entree):
                resultat = self.lancer(RUN_ALL_SUITES_NPM=f"mothra:mothra {entree}")
                self.assertEqual(resultat.returncode, 2, resultat.stdout)
                self.assertIn("run_all : SUITES_NPM, entrée 2 mal formée", resultat.stdout)
                self.assertNotIn("TOTAL", resultat.stdout)

    def test_ligne_du_depot_declare_la_suite_mothra_sous_la_forme_que_ci_local_lit(self):
        lignes = [l for l in RUN_ALL.read_text(encoding="utf-8").splitlines() if l.startswith("SUITES_NPM=(")]
        self.assertEqual(lignes, ["SUITES_NPM=(mothra:mothra)"])   # une seule ligne, sans commentaire : tools/ci_local.sh la lit par un motif exact
        self.assertTrue((RUN_ALL.parents[1] / "mothra" / "package.json").is_file())
        self.assertEqual(list(RUN_ALL.parent.glob("suites_npm*")), [])   # la liste à part n'existe plus

    def test_racine_injectee_sans_variable_n_a_aucune_suite_npm(self):
        self.suite_python("alpha")
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS", "DBTEST_PORT", "RUN_ALL_SUITES_NPM")}
        env.update({"RUN_ALL_ROOT": str(self.racine), "RUN_ALL_DEPS": "", "PATH": f"{self.bin}{os.pathsep}{env['PATH']}",
                    "FAUX_NPM_JOURNAL": str(self.journal), "FAUX_NPM_SORTIE": str(self.sortie_npm)})
        resultat = subprocess.run(["bash", str(RUN_ALL), "alpha"], env=env, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertNotIn("npm", resultat.stdout)
        self.assertEqual(self.appels_npm(), [])

    # --- l'arrêt immédiat d'un lancement complet (code 7)
    def complet(self, **variables):
        """Un lancement complet : sans nom de suite, avec le script des suites shell du dépôt remplacé par un faux qui réussit."""
        for chemin in scripts_shell():
            (self.racine / chemin).parent.mkdir(parents=True, exist_ok=True)
            (self.racine / chemin).write_text(SHELL_OK)
        return self.lancer(**variables)

    def test_lancement_complet_node_modules_absent_s_arrete_tout_de_suite_code_7(self):
        self.espace(installe="absent")
        self.suite_python("alpha")
        resultat = self.complet()
        self.assertEqual(resultat.returncode, 7, resultat.stdout)
        racine = str(self.racine)
        self.assertIn(f"run_all : lancer : cd {racine}/mothra && npm ci", resultat.stdout)
        self.assertIn("dépendances npm à mettre en conformité avant un lancement complet", resultat.stdout)
        self.assertNotIn(" tests · ", resultat.stdout)   # aucune suite lancée, aucune ligne de suite
        self.assertNotIn("TOTAL", resultat.stdout)
        self.assertEqual(self.appels_npm(), [])

    def test_lancement_complet_verrou_different_nomme_l_ecart_et_s_arrete(self):
        self.espace(installe="different")
        resultat = self.complet()
        self.assertEqual(resultat.returncode, 7, resultat.stdout)
        self.assertIn("écart : version différente : node_modules/a", resultat.stdout)
        self.assertIn(f"cd {self.racine}/mothra && npm ci", resultat.stdout)

    def test_lancement_complet_node_different_s_arrete_code_7_avec_la_commande(self):
        resultat = self.complet(FAUX_NODE_VERSION="v25.9.0")
        self.assertEqual(resultat.returncode, 7, resultat.stdout)
        self.assertIn("Node 25.9.0 au lieu de 26.12.1, fixé par mothra/.node-version", resultat.stdout)
        self.assertIn(f"cd {self.racine}/mothra && npm ci", resultat.stdout)
        self.assertNotIn(" tests · ", resultat.stdout)

    def test_lancement_complet_qui_s_arrete_n_efface_aucune_empreinte(self):
        subprocess.run(["git", "init", "-q"], cwd=self.racine, check=True)   # le dossier mothra y est déjà ; le lanceur voit ce dépôt, pas celui du worktree
        empreinte = self.racine / ".git" / "pmzilla-run-all-ok"
        empreinte.write_text("arbre-d-avant\n")
        self.espace(installe="absent")
        resultat = self.complet()
        self.assertEqual(resultat.returncode, 7, resultat.stdout)
        self.assertEqual(empreinte.read_text(), "arbre-d-avant\n")

    def test_lancement_nomme_garde_l_echec_nomme_de_la_suite(self):
        self.espace(installe="absent")
        self.suite_python("alpha")
        resultat = self.lancer("alpha")   # une suite Python nommée : ni arrêt immédiat ni suite npm
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        resultat = self.lancer("mothra")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertIn("dépendances npm absentes ou différentes du verrou : mothra", resultat.stdout)

    def test_lancement_complet_dossier_de_la_suite_absent_reste_un_echec_nomme(self):
        shutil.rmtree(self.racine / "mothra")
        resultat = self.complet()
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertIn("suite npm absente : mothra", resultat.stdout)

    def test_staged_devenu_complet_s_arrete_aussi_code_7(self):
        self.espace(installe="absent")
        resultat = self.lancer("--staged")   # la racine factice n'est pas un dépôt Git : le sélecteur échoue, l'exécution devient complète
        self.assertEqual(resultat.returncode, 7, resultat.stdout)
        self.assertIn("exécution complète", resultat.stdout)
        self.assertIn(f"cd {self.racine}/mothra && npm ci", resultat.stdout)
        self.assertNotIn(" tests · ", resultat.stdout)

    def test_le_code_7_est_documente_dans_l_en_tete(self):
        texte = RUN_ALL.read_text(encoding="utf-8")
        self.assertRegex(texte, r"(?m)^# 6 lancement refusé dans une session Claude Code .*, 7 lancement complet arrêté avant la première suite")

    def test_la_suite_npm_est_portable_et_hors_de_la_liste_du_mac(self):
        texte = (RUN_ALL.parent / "suites_mac.txt").read_text(encoding="utf-8")
        self.assertNotRegex(texte, r"(?m)^mothra:")


if __name__ == "__main__":
    unittest.main()
