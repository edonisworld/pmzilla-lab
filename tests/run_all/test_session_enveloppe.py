"""
bash-sandbox-n2, K4 (design D10 et D12 ; tâches 9.1 et 9.4) : en session, une fois l'enveloppe figée de la CI locale présente
(~/.pmzilla-lab/outils-figes/ci_local.sh), le lanceur ne lance plus le conteneur : il lance les suites propres au Mac, puis dit l'appel que la session
doit faire par l'enveloppe (code 10). Sans enveloppe, ou hors session, le chemin d'avant ne change pas.

 - lancement nommé : les suites propres au Mac, puis la ligne « run --travail » et le code 10 ; une suite du Mac rouge garde le code 1 et la ligne ;
 - --staged sans ligne verte de la preuve d'index : la ligne « run --index », « aucune empreinte écrite ni effacée », aucune suite, code 10 ;
 - --staged avec cette ligne : les suites propres au Mac et l'empreinte ciblée, comme avant ;
 - R-20261111-48 : le chemin de l'enveloppe est le dossier personnel de la base des comptes (jamais « ~ » ni HOME) ; l'argument du worktree s'écrit avec « ~ » ;
 - 9.4 : la sortie gardée d'une suite rouge passe au dossier temporaire de la session quand le dossier du compte est refusé, avec une ligne qui le dit ;
   les journaux de session restent en échec doux, une ligne, code inchangé. Le fichier géré du bac à sable ne décide que de la forme de la ligne imprimée (R-20261111-54).

Le lanceur est COPIÉ dans une fausse racine (dépôt Git jetable, sous un faux dossier personnel) comme dans test_session_conteneur.py : le vrai dossier de
données, le vrai Docker et le vrai fichier des preuves d'index ne sont jamais touchés. L'enveloppe est fausse : elle ne fait que noter ses appels.

    python3 -m unittest discover -s tests/run_all -v

Remplace : rien. Retrait : avec la décision D10 de bash-sandbox-n2 (permanent tant que les sessions tournent sous le bac à sable).
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

RACINE_DEPOT = Path(__file__).resolve().parents[2]
RUN_ALL = RACINE_DEPOT / "tests" / "run_all.sh"
APPEL_GETPWUID = "/usr/bin/perl -e 'print((getpwuid($<))[7])'"
CHEMIN_GERE = "/Library/Application Support/ClaudeCode/managed-settings.d/50-pmzilla-bac-a-sable.json"
SUITE_OK = "import unittest\nclass T(unittest.TestCase):\n    def test_a(self): pass\n    def test_b(self): pass\n"
SUITE_KO = "import unittest\nclass T(unittest.TestCase):\n    def test_a(self): pass\n    def test_casse(self): self.assertEqual(1, 2)\n"
SELECTEUR_DEUX = "import sys\nprint('select_suites : alpha : fichier x')\nprint('select_suites : beta : fichier y')\nsys.exit(0)\n"
SELECTEUR_BETA = "import sys\nprint('select_suites : beta : fichier y')\nsys.exit(0)\n"
SELECTEUR_COMPLET = "import sys\nprint('select_suites : exécution complète exigée')\nsys.exit(3)\n"
FAUX_CI = """#!/bin/bash
# faux tools/ci_local.sh : note ses appels ; ne doit jamais être lancé par le lanceur quand l'enveloppe est présente
ici=$(cd "$(dirname "$0")" && pwd)
printf '%s\\n' "$*" >> "$ici/ci_appels"
exit 0
"""
FAUSSE_ENVELOPPE = """#!/bin/bash
# fausse enveloppe figée : note ses appels ; le lanceur ne la lance jamais
printf '%s\\n' "$*" >> "$(dirname "$0")/appels"
exit 0
"""
FAUX_MATIN = """#!/bin/bash
exit 0
"""
# R-20261111-22 (tâche 19.8) : la forme unique remplace `bash ~/…` ; R-20261111-48 : le chemin de l'enveloppe est le dossier personnel de la base des comptes (ici le faux
# dossier personnel du test, que le test substitue à getpwuid), jamais `~` : la ligne attendue se construit avec lui (Base.ligne_appel).
PREFIXE_APPEL_ENV = "/bin/bash --noprofile --norc -p "
SUITE_APPEL_ENV = "/.pmzilla-lab/outils-figes/ci_local.sh run"
PREFIXE_LIGNE = "run_all : suites portables à lancer d'abord, seules, par l'enveloppe : "
FIN_AUCUNE_EMPREINTE = "run_all : aucune empreinte écrite ni effacée"


class Base(unittest.TestCase):
    """Fausse racine sous un faux dossier personnel : ~/PMZilla-Lab/worktrees/wt-essai, avec ou sans enveloppe."""

    avec_enveloppe = True

    def setUp(self):
        self.base = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.base, True)
        self.home = self.base / "home"
        self.racine = self.home / "PMZilla-Lab" / "worktrees" / "wt-essai"
        for nom, texte in (("alpha", SUITE_OK), ("beta", SUITE_OK), ("gamma", SUITE_OK), ("casse", SUITE_KO)):
            (self.racine / "tests" / nom).mkdir(parents=True)
            (self.racine / "tests" / nom / f"test_{nom}.py").write_text(texte)
        (self.racine / "tests" / "suites_shell.txt").write_text("# aucune suite shell dans la fausse racine\n")
        (self.racine / "tests" / "suites_mac.txt").write_text("beta:python # essai : suite propre au Mac\ncasse:python # essai : suite propre au Mac, rouge\n")
        texte = RUN_ALL.read_text(encoding="utf-8")
        self.assertIn(APPEL_GETPWUID, texte)
        texte = texte.replace("\nSUITES_NPM=(mothra:mothra)\n", "\nSUITES_NPM=()\n")
        self.gere = self.base / "fichier-gere.json"   # R-20261111-54 : le faux fichier géré du bac à sable (présent par défaut), substitué au chemin réel dans la copie
        self.assertIn(CHEMIN_GERE, texte)
        texte = texte.replace(CHEMIN_GERE, str(self.gere))
        (self.racine / "tests" / "run_all.sh").write_text(texte.replace(APPEL_GETPWUID, f"printf %s {str(self.home)!r}"), encoding="utf-8")
        (self.racine / "tools").mkdir()
        shutil.copy(RACINE_DEPOT / "tools" / "preuve_arbre.py", self.racine / "tools" / "preuve_arbre.py")
        shutil.copy(RACINE_DEPOT / "tools" / "lab_paths.py", self.racine / "tools" / "lab_paths.py")
        (self.racine / "tools" / "ci_local.sh").write_text(FAUX_CI)
        (self.racine / "tools" / "morning_state.sh").write_text(FAUX_MATIN)
        self.donnees = self.home / ".pmzilla-lab"
        self.donnees.mkdir(parents=True)
        self.enveloppe_appels = self.donnees / "outils-figes" / "appels"
        if self.avec_enveloppe:
            (self.donnees / "outils-figes").mkdir()
            (self.donnees / "outils-figes" / "ci_local.sh").write_text(FAUSSE_ENVELOPPE)
        self.gere.write_text("{}\n")
        self.durees = self.base / "durees.tsv"
        self.tmp_session = self.base / "tmp-session"
        self.tmp_session.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("add", "-A")
        self.git("-c", "user.email=t@example.org", "-c", "user.name=test", "commit", "-q", "-m", "base")
        (self.racine / "tests" / "alpha" / "test_alpha.py").write_text(SUITE_OK + "\n")   # un index qui diffère de HEAD
        self.git("add", "-A")
        self.arbre = self.git("write-tree")
        self.empreintes = {nom: self.racine / ".git" / nom for nom in ("pmzilla-run-all-ok", "pmzilla-run-targeted-ok", "pmzilla-run-branch-ok")}
        for nom, chemin in self.empreintes.items():
            chemin.write_text("a-conserver-" + nom)

    def git(self, *arguments):
        return subprocess.run(["git", *arguments], cwd=self.racine, capture_output=True, text=True, check=True).stdout.strip()

    def lancer(self, *arguments, session="1", **variables):
        retirees = ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS", "RUN_ALL_ROOT", "FINISH_LOCK_TOKEN", "DBTEST_PORT", "CLAUDECODE",
                    "PMZILLA_FINISH_LOCK_MAX_AGE", "PMZILLA_LAB_DATA", "CI_LOCAL_DOCKER", "CI_LOCAL_PREUVES_INDEX", "RUN_ALL_RED_DIR", "SANDBOX_RUNTIME")
        env = {k: v for k, v in os.environ.items() if k not in retirees}
        env.update({"RUN_ALL_DEPS": "", "PMZILLA_LAB_DATA": str(self.donnees), "RUN_ALL_DURATIONS": str(self.durees), "TMPDIR": str(self.tmp_session)})
        if session is not None:
            env["CLAUDECODE"] = session
        env.update(variables)
        env = {k: v for k, v in env.items() if v is not None}
        return subprocess.run(["bash", str(self.racine / "tests" / "run_all.sh"), *arguments], env=env, cwd=self.racine,
                              capture_output=True, text=True, timeout=120)

    def selecteur(self, texte):
        (self.racine / "tools" / "select_suites.py").write_text(texte)

    def preuve(self, suites):
        (self.donnees / "ci").mkdir(parents=True, exist_ok=True)
        with open(self.donnees / "ci" / "preuves-index", "a", encoding="utf-8") as f:
            f.write(f"{self.arbre}\tcle\t{suites}\n")

    def appels(self):
        """Tout appel noté par un faux script de CI : celui du dépôt ou l'enveloppe. Le lanceur ne doit en faire aucun."""
        notes = []
        for fichier in (self.racine / "tools" / "ci_appels", self.enveloppe_appels):
            if fichier.exists():
                notes += fichier.read_text().splitlines()
        return notes

    def ciblee(self):
        return self.empreintes["pmzilla-run-targeted-ok"]

    def intactes(self):
        for nom, chemin in self.empreintes.items():
            self.assertEqual(chemin.read_text(), "a-conserver-" + nom, f"{nom} : ni écrite ni effacée")

    def ligne_appel(self, mode, suites):
        fin = (" " + " ".join(suites)) if suites else ""
        return f"{PREFIXE_LIGNE}{PREFIXE_APPEL_ENV}{self.home}{SUITE_APPEL_ENV} {mode} --worktree ~/PMZilla-Lab/worktrees/wt-essai{fin}\n"


class LancementNomme(Base):
    def test_suites_du_mac_puis_la_ligne_d_appel_et_le_code_10(self):
        resultat = self.lancer("alpha", "beta", "gamma")
        self.assertEqual(resultat.returncode, 10, resultat.stdout + resultat.stderr)
        self.assertRegex(resultat.stdout, r"beta\s+2 tests · OK")
        self.assertNotRegex(resultat.stdout, r"(alpha|gamma)\s+\d+ tests")
        ligne = self.ligne_appel("--travail", ["alpha", "gamma"])
        self.assertIn(ligne, resultat.stdout)
        self.assertGreater(resultat.stdout.index(ligne), resultat.stdout.index("beta"), "les suites du Mac passent avant la ligne")
        self.assertEqual(self.appels(), [], "le lanceur ne lance ni le script de la CI ni l'enveloppe")
        self.intactes()

    def test_le_chemin_de_l_enveloppe_est_le_dossier_personnel_de_la_base_des_comptes_et_le_worktree_garde_le_tilde(self):
        """R-20261111-48 : le chemin de l'enveloppe porte le dossier personnel lu par getpwuid (ici le faux dossier du test), jamais `~` ; l'argument du worktree garde
        `~/PMZilla-Lab/worktrees/<n>` et ne nomme ni le dossier personnel ni la racine."""
        resultat = self.lancer("alpha")
        self.assertEqual(resultat.returncode, 10, resultat.stdout)
        self.assertIn(f"-p {self.home}/.pmzilla-lab/outils-figes/ci_local.sh run --travail ", resultat.stdout)
        self.assertNotIn("-p ~/", resultat.stdout)
        self.assertNotIn(f"{self.home}/PMZilla-Lab", resultat.stdout)
        self.assertNotIn(str(self.racine), resultat.stdout)
        self.assertIn("--worktree ~/PMZilla-Lab/worktrees/wt-essai alpha\n", resultat.stdout)

    def test_le_meme_chemin_avec_home_change_par_l_appelant(self):
        """R-20261111-48 : HOME modifié dans l'environnement du lanceur ne déplace pas le chemin de l'enveloppe."""
        resultat = self.lancer("alpha", HOME=str(self.base / "autre-maison"))
        self.assertEqual(resultat.returncode, 10, resultat.stdout)
        self.assertIn(self.ligne_appel("--travail", ["alpha"]), resultat.stdout)
        self.assertNotIn("autre-maison", resultat.stdout)

    def test_suites_portables_seules_rien_sur_le_mac_et_aucune_ligne_de_durees(self):
        resultat = self.lancer("alpha", "gamma")
        self.assertEqual(resultat.returncode, 10, resultat.stdout)
        self.assertIn(self.ligne_appel("--travail", ["alpha", "gamma"]), resultat.stdout)
        self.assertFalse(self.durees.exists(), "aucune suite lancée ici : aucune ligne de durées")
        self.assertEqual(self.appels(), [])

    def test_une_suite_du_mac_rouge_garde_le_code_1_et_la_ligne_est_imprimee(self):
        resultat = self.lancer("alpha", "casse")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertIn(self.ligne_appel("--travail", ["alpha"]), resultat.stdout)
        self.assertIn("1 suite(s) en échec : casse", resultat.stdout)
        self.assertEqual(self.appels(), [])

    def test_suites_du_mac_seules_pas_de_ligne_et_code_0(self):
        resultat = self.lancer("beta")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertNotIn(PREFIXE_LIGNE, resultat.stdout)
        self.assertEqual(self.appels(), [])

    def test_aucune_empreinte_n_est_touchee(self):
        self.lancer("alpha", "beta")
        self.intactes()


class FichierGereAbsent(Base):
    """R-20261111-54 : un seul signal, le fichier géré du bac à sable. Présent : l'appel par l'enveloppe (tous les tests ci-dessus, qui le posent par défaut). Absent :
    la commande directe de la CI locale, sans `--worktree`, même quand la copie figée de l'enveloppe est là ; le code 10 et le reste ne changent pas.
    Remplace : R-20261110-20 (Q7, deux signaux). Retrait : avec le bac à sable."""

    def absent(self):
        """Le faux fichier géré (chemin substitué dans la copie du lanceur) est retiré."""
        self.gere.unlink()

    def test_nomme_sans_fichier_gere_la_commande_directe_et_le_code_10(self):
        self.absent()
        resultat = self.lancer("alpha", "beta", "gamma")
        self.assertEqual(resultat.returncode, 10, resultat.stdout + resultat.stderr)
        self.assertIn("run_all : suites portables à lancer d'abord, seules, en commande directe : bash tools/ci_local.sh run --travail alpha gamma\n", resultat.stdout)
        self.assertNotIn(PREFIXE_LIGNE, resultat.stdout)
        self.assertNotIn("à lancer d'abord, seules, par l'enveloppe", resultat.stdout)
        self.assertNotIn("outils-figes", resultat.stdout)
        self.assertNotIn("--worktree", resultat.stdout)
        self.assertEqual(self.appels(), [], "le lanceur ne lance toujours ni le script de la CI ni l'enveloppe")
        self.intactes()

    def test_staged_sans_fichier_gere_la_commande_directe_run_index(self):
        self.selecteur(SELECTEUR_DEUX)
        self.absent()
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 10, resultat.stdout + resultat.stderr)
        self.assertIn("run_all : suites portables à lancer d'abord, seules, en commande directe : bash tools/ci_local.sh run --index alpha\n", resultat.stdout)
        self.assertNotIn(PREFIXE_LIGNE, resultat.stdout)
        self.assertNotIn("à lancer d'abord, seules, par l'enveloppe", resultat.stdout)
        self.assertIn(FIN_AUCUNE_EMPREINTE, resultat.stdout)
        self.intactes()

    def test_avec_fichier_gere_la_forme_de_l_enveloppe_reste_imprimee(self):
        resultat = self.lancer("alpha")
        self.assertEqual(resultat.returncode, 10, resultat.stdout)
        self.assertIn(self.ligne_appel("--travail", ["alpha"]), resultat.stdout)
        self.assertNotIn("en commande directe", resultat.stdout)

    def test_le_chemin_reel_du_fichier_gere_est_une_constante_du_lanceur(self):
        """R-20261112-19 : plus de variable de contournement ; le chemin du système est écrit en dur."""
        texte = RUN_ALL.read_text(encoding="utf-8")
        self.assertIn(f'FICHIER_GERE="{CHEMIN_GERE}"', texte)
        self.assertNotIn("RUN_ALL_FICHIER_GERE", texte)


class StagedAvecEnveloppe(Base):
    def test_sans_ligne_de_preuve_la_ligne_run_index_rien_n_est_lance_ni_ecrit_ni_efface(self):
        self.selecteur(SELECTEUR_DEUX)
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 10, resultat.stdout + resultat.stderr)
        self.assertIn(self.ligne_appel("--index", ["alpha"]), resultat.stdout)
        self.assertIn(FIN_AUCUNE_EMPREINTE + "\n", resultat.stdout)
        self.assertLess(resultat.stdout.index(PREFIXE_LIGNE), resultat.stdout.index(FIN_AUCUNE_EMPREINTE))
        self.assertNotRegex(resultat.stdout, r"(alpha|beta|gamma)\s+\d+ tests")
        self.assertFalse(self.durees.exists(), "aucune suite lancée : aucune ligne de durées")
        self.assertEqual(self.appels(), [])
        self.intactes()   # l'empreinte ciblée précédente n'est pas effacée

    def test_une_ligne_qui_ne_couvre_pas_les_suites_n_est_pas_une_preuve(self):
        self.selecteur(SELECTEUR_DEUX)
        self.preuve("gamma")
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 10, resultat.stdout)
        self.assertIn(FIN_AUCUNE_EMPREINTE, resultat.stdout)
        self.intactes()

    def test_une_ligne_d_un_autre_arbre_n_est_pas_une_preuve(self):
        self.selecteur(SELECTEUR_DEUX)
        (self.donnees / "ci").mkdir()
        (self.donnees / "ci" / "preuves-index").write_text("1" * 40 + "\tcle\tcomplet\n")
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 10, resultat.stdout)
        self.intactes()

    def test_avec_la_ligne_verte_les_suites_du_mac_tournent_et_l_empreinte_ciblee_est_ecrite(self):
        self.selecteur(SELECTEUR_DEUX)
        self.preuve("alpha")
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
        self.assertRegex(resultat.stdout, r"beta\s+2 tests · OK")
        self.assertNotRegex(resultat.stdout, r"(alpha|gamma)\s+\d+ tests")
        self.assertNotIn(PREFIXE_LIGNE, resultat.stdout)
        self.assertNotIn(FIN_AUCUNE_EMPREINTE, resultat.stdout)
        self.assertIn(f"run_all : empreinte ciblée écrite (conteneur et Mac) pour l'index {self.arbre[:12]}\n", resultat.stdout)
        self.assertEqual(self.ciblee().read_text().strip(), self.arbre)
        self.assertEqual(self.empreintes["pmzilla-run-all-ok"].read_text(), "a-conserver-pmzilla-run-all-ok", "jamais l'empreinte complète")
        self.assertEqual(self.appels(), [], "le lanceur ne lance ni le script de la CI ni l'enveloppe")

    def test_ligne_verte_et_suite_du_mac_rouge_aucune_empreinte(self):
        self.selecteur("import sys\nprint('select_suites : alpha : fichier x')\nprint('select_suites : casse : fichier y')\nsys.exit(0)\n")
        self.preuve("alpha")
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertIn("run_all : empreinte ciblée non écrite (suites propres au Mac rouges)\n", resultat.stdout)
        self.assertFalse(self.ciblee().exists())

    def test_toutes_les_suites_du_mac_ecrivent_l_empreinte_sans_ligne_de_preuve(self):
        self.selecteur(SELECTEUR_BETA)
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertNotIn(PREFIXE_LIGNE, resultat.stdout)
        self.assertEqual(self.ciblee().read_text().strip(), self.arbre)
        self.assertEqual(self.appels(), [])

    def test_execution_complete_sans_ligne_complet_la_ligne_run_index_sans_suite(self):
        self.selecteur(SELECTEUR_COMPLET)
        self.preuve("alpha")   # une ligne qui ne dit pas « complet » n'est pas une preuve du mode complet
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 10, resultat.stdout + resultat.stderr)
        self.assertIn(self.ligne_appel("--index", []), resultat.stdout)
        self.assertIn(FIN_AUCUNE_EMPREINTE + "\n", resultat.stdout)
        self.assertNotRegex(resultat.stdout, r"beta\s+\d+ tests")
        self.assertEqual(self.appels(), [])
        self.intactes()

    def test_execution_complete_avec_la_ligne_complet_toute_la_passe_mac_puis_l_empreinte_ciblee(self):
        self.selecteur(SELECTEUR_COMPLET)
        self.preuve("complet")
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)   # « casse » est une suite du Mac rouge de la fausse racine : la passe Mac est complète
        self.assertRegex(resultat.stdout, r"beta\s+2 tests · OK")
        self.assertRegex(resultat.stdout, r"casse\s+\d+ tests")
        self.assertNotIn(PREFIXE_LIGNE, resultat.stdout)
        self.assertEqual(self.appels(), [])


class CheminInchange(Base):
    def test_hors_session_rien_ne_change_meme_avec_l_enveloppe(self):
        resultat = self.lancer("alpha", "beta", session=None)
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertRegex(resultat.stdout, r"alpha\s+2 tests · OK")
        self.assertNotIn(PREFIXE_LIGNE, resultat.stdout)
        self.assertEqual(self.appels(), [])


class SansEnveloppe(Base):
    avec_enveloppe = False

    def test_le_chemin_d_avant_reste_le_script_de_la_ci_est_appele(self):
        resultat = self.lancer("alpha", "beta")
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
        self.assertIn("run_all : suites portables envoyées au conteneur : 1 ; suites propres au Mac lancées ici : 1\n", resultat.stdout)
        self.assertEqual((self.racine / "tools" / "ci_appels").read_text().splitlines(), ["run --travail alpha"])
        self.assertNotIn(PREFIXE_LIGNE, resultat.stdout)

    def test_staged_sans_enveloppe_appelle_run_index_comme_avant(self):
        self.selecteur(SELECTEUR_DEUX)
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
        self.assertEqual((self.racine / "tools" / "ci_appels").read_text().splitlines(), ["run --index alpha"])
        self.assertNotIn(FIN_AUCUNE_EMPREINTE, resultat.stdout)


class SortieDesSuitesRougesEtJournaux(Base):
    """Tâche 9.4 : le dossier du compte est refusé en écriture sous le bac à sable ; le fichier géré du bac à sable ne décide que de la forme de la ligne imprimée (R-20261111-54), l'écriture refusée déclenche le repli."""

    avec_enveloppe = False

    def bloquer(self, chemin):
        chemin.write_text("un fichier, pas un dossier\n")

    def test_sortie_rouge_refusee_dans_le_dossier_du_compte_va_au_dossier_temporaire_de_la_session(self):
        self.bloquer(self.donnees / "suites-rouges")
        resultat = self.lancer("casse")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        gardes = sorted((self.tmp_session / "pmzilla-suites-rouges").glob("rouge-*.txt"))
        self.assertEqual(len(gardes), 1, resultat.stdout)
        self.assertIn("=== casse : ÉCHEC (code 1)", gardes[0].read_text(encoding="utf-8"))
        self.assertIn("run_all : sortie des suites rouges non gardée (écriture impossible)", resultat.stdout)
        self.assertIn(f"copie dans le dossier temporaire de la session : pmzilla-suites-rouges/{gardes[0].name}\n", resultat.stdout)
        self.assertNotIn("sortie des suites rouges gardée", resultat.stdout)
        self.assertNotIn(str(self.tmp_session), resultat.stdout)
        # la trace de la suite rouge nomme son propre fichier ; les lignes du lanceur, jamais le dossier du compte
        self.assertEqual([l for l in resultat.stdout.splitlines() if l.startswith("run_all :") and str(self.home) in l], [])

    def test_dossier_du_compte_ecrit_le_repli_n_est_pas_utilise(self):
        resultat = self.lancer("casse")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertEqual(len(list((self.donnees / "suites-rouges").glob("rouge-*.txt"))), 1)
        self.assertFalse((self.tmp_session / "pmzilla-suites-rouges").exists())
        self.assertIn("run_all : sortie des suites rouges gardée : ~/.pmzilla-lab/suites-rouges/rouge-", resultat.stdout)

    def test_les_deux_ecritures_refusees_une_seule_ligne_et_le_code_ne_change_pas(self):
        self.bloquer(self.donnees / "suites-rouges")
        self.bloquer(self.tmp_session / "pmzilla-suites-rouges")
        resultat = self.lancer("casse")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertIn("run_all : sortie des suites rouges non gardée (écriture impossible)\n", resultat.stdout)
        self.assertNotIn("copie dans le dossier temporaire", resultat.stdout)

    def test_un_passage_vert_n_ecrit_rien_dans_le_dossier_temporaire(self):
        self.bloquer(self.donnees / "suites-rouges")
        resultat = self.lancer("beta")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertFalse((self.tmp_session / "pmzilla-suites-rouges").exists())

    def test_les_dix_derniers_fichiers_du_dossier_temporaire_au_plus(self):
        self.bloquer(self.donnees / "suites-rouges")
        repli = self.tmp_session / "pmzilla-suites-rouges"
        repli.mkdir()
        anciens = [repli / f"rouge-2000-01-01T0000{k:02d}-1.txt" for k in range(12)]
        for ancien in anciens:
            ancien.write_text("ancien\n")
        resultat = self.lancer("casse")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertEqual(len(list(repli.glob("rouge-*.txt"))), 10)
        self.assertTrue(all(not a.exists() for a in anciens[:3]))

    def test_journal_de_session_refuse_une_ligne_et_le_code_ne_change_pas(self):
        # avec l'enveloppe, le lanceur écrit une ligne au journal de session avant le code 10 : le dossier du journal est un fichier
        (self.donnees / "outils-figes").mkdir()
        (self.donnees / "outils-figes" / "ci_local.sh").write_text(FAUSSE_ENVELOPPE)
        self.bloquer(self.donnees / "journal")
        resultat = self.lancer("alpha", "beta")
        self.assertEqual(resultat.returncode, 10, resultat.stdout)
        lignes = [l for l in resultat.stdout.splitlines() if "journaux de session non écrits" in l]
        self.assertEqual(lignes, ["run_all : journaux de session non écrits (écriture impossible)"], resultat.stdout)
        # R-20261111-48 : le dossier personnel n'apparaît plus que dans le chemin de l'enveloppe de la ligne d'appel (code 10), nulle part ailleurs.
        hors_ligne_d_appel = "\n".join(l for l in resultat.stdout.splitlines() if not l.startswith(PREFIXE_LIGNE))
        self.assertNotIn(str(self.home), hors_ligne_d_appel)

    def test_durees_refusees_une_ligne_et_le_code_ne_change_pas(self):
        self.bloquer(self.base / "bloc")
        resultat = self.lancer("beta", RUN_ALL_DURATIONS=str(self.base / "bloc" / "durees.tsv"))
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertEqual([l for l in resultat.stdout.splitlines() if "durées non enregistrées" in l], ["run_all : durées non enregistrées (écriture impossible)"])


class RevueK4(Base):
    """Revue Opus 10.1 de K4 : constat 6 (le repli ne vaut que pour le dossier de données, jamais pour RUN_ALL_RED_DIR) et constat 9 (journaliser avant
    d'imprimer la ligne d'appel, pour que les lignes de D12 restent les dernières)."""

    def bloquer(self, chemin):
        chemin.write_text("un fichier, pas un dossier\n")

    def test_constat_6_avec_run_all_red_dir_refuse_rien_n_est_ecrit_dans_le_dossier_temporaire(self):
        self.bloquer(self.donnees / "bloc")
        resultat = self.lancer("casse", RUN_ALL_RED_DIR=str(self.donnees / "bloc" / "suites-rouges"))
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertIn("run_all : sortie des suites rouges non gardée (écriture impossible)\n", resultat.stdout)
        self.assertNotIn("copie dans le dossier temporaire", resultat.stdout)
        self.assertFalse((self.tmp_session / "pmzilla-suites-rouges").exists())

    def test_constat_9_la_ligne_d_appel_travail_reste_la_derniere_meme_quand_le_journal_est_refuse(self):
        self.bloquer(self.donnees / "journal")
        resultat = self.lancer("alpha", "beta")
        self.assertEqual(resultat.returncode, 10, resultat.stdout)
        self.assertIn("run_all : journaux de session non écrits (écriture impossible)", resultat.stdout)
        self.assertEqual(resultat.stdout.rstrip("\n").splitlines()[-1], self.ligne_appel("--travail", ["alpha"]).rstrip("\n"))

    def test_constat_9_la_ligne_d_appel_index_vient_apres_la_panne_du_journal(self):
        self.selecteur(SELECTEUR_DEUX)
        self.bloquer(self.donnees / "journal")
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 10, resultat.stdout)
        panne = resultat.stdout.index("run_all : journaux de session non écrits")
        self.assertLess(panne, resultat.stdout.index(PREFIXE_LIGNE))
        self.assertEqual(resultat.stdout.rstrip("\n").splitlines()[-1], FIN_AUCUNE_EMPREINTE)


if __name__ == "__main__":
    unittest.main()
