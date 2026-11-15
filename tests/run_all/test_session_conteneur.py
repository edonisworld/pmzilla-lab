"""
tooling-proof-in-container, T2 (design D1, D3, D4, D8 ; R-20261104-7 P2, P3, P5, P6 ; tâches 6.3, 6.4, 6.5, 6.9) : en session Claude Code, aucune suite
portable ne tourne sur le Mac. `bash tests/run_all.sh <suites>` envoie ses suites portables à `tools/ci_local.sh run --travail`, `--staged` à
`run --index` (mode complet, sans suite, quand le sélecteur exige l'exécution complète), lance ici les seules suites de tests/suites_mac.txt, et
n'écrit l'empreinte ciblée que sur une ligne verte de la preuve d'index du même arbre, une partie Mac verte et un index inchangé. Conteneur
indisponible (codes 3, 5, 6, 7 de ci_local.sh) : code 9, rien n'est lancé ni écrit.

Le lanceur est COPIÉ dans une fausse racine (dépôt Git jetable) avec un faux dossier personnel, un faux tools/ci_local.sh qui note ses appels, un
faux sélecteur, et la vraie tools/preuve_arbre.py : le vrai dossier de données, le vrai Docker et le vrai fichier des preuves d'index ne sont
jamais touchés.

    python3 -m unittest discover -s tests/run_all -v

Remplace : les tests de session qui lançaient les suites portables sur le Mac (SessionClaudeCode : le verrou est retiré avec T2 ; la garde du matin est GARDÉE,
décision de l'auteur du 2026-11-04, T2-1 (a), et ses tests sont restaurés dans test_run_all.py).
Retrait : permanent, tant que la CI est le runner.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

RACINE_DEPOT = Path(__file__).resolve().parents[2]
RUN_ALL = RACINE_DEPOT / "tests" / "run_all.sh"
PREUVE_ARBRE = RACINE_DEPOT / "tools" / "preuve_arbre.py"
APPEL_GETPWUID = "/usr/bin/perl -e 'print((getpwuid($<))[7])'"
SUITE_OK = "import unittest\nclass T(unittest.TestCase):\n    def test_a(self): pass\n    def test_b(self): pass\n"
SUITE_KO = "import unittest\nclass T(unittest.TestCase):\n    def test_a(self): pass\n    def test_casse(self): self.assertEqual(1, 2)\n"
SELECTEUR_DEUX = "import sys\nprint('select_suites : alpha : fichier x')\nprint('select_suites : beta : fichier y')\nsys.exit(0)\n"
SELECTEUR_ALPHA = "import sys\nprint('select_suites : alpha : fichier x')\nsys.exit(0)\n"
SELECTEUR_BETA = "import sys\nprint('select_suites : beta : fichier y')\nsys.exit(0)\n"
SELECTEUR_COMPLET = "import sys\nprint('select_suites : exécution complète exigée')\nsys.exit(3)\n"
FAUX_CI = """#!/bin/bash
# faux tools/ci_local.sh : note ses arguments et son environnement, joue un événement du test, écrit au besoin la ligne de preuve d'index
ici=$(cd "$(dirname "$0")" && pwd)
printf '%s\\n' "$*" >> "$ici/ci_appels"
env | LC_ALL=C sort > "$ici/ci_env"
[ -f "$ici/ci_pendant" ] && bash "$ici/ci_pendant"
code=$(cat "$ici/ci_code" 2>/dev/null || echo 0)
if [ "$code" = 0 ] && [ -f "$ici/ci_ecrit" ] && [ "${1:-}" = run ] && [ "${2:-}" = --index ]; then
  mkdir -p "$PMZILLA_LAB_DATA/ci"
  printf '%s\\tcle\\t%s\\n' "$(git write-tree)" "$(cat "$ici/ci_ecrit")" >> "$PMZILLA_LAB_DATA/ci/preuves-index"
fi
echo "ci_local : faux passage (code $code)"
exit "$code"
"""
FAUX_MATIN = """#!/bin/bash
# faux tools/morning_state.sh (garde du matin légère, GARDÉE par l'auteur : T2-1 (a)) : note ses arguments, rend le code du fichier « m_code » (0 sans lui)
ici=$(cd "$(dirname "$0")" && pwd)
printf '%s\\n' "$*" >> "$ici/m_appels"
echo "morning_state : ligne du faux module"
exit "$(cat "$ici/m_code" 2>/dev/null || echo 0)"
"""
FAUX_PREUVE_ARBRE = """import os, sys
ici = os.path.dirname(os.path.abspath(__file__))
open(os.path.join(ici, 'pa_env'), 'w').write('\\n'.join(f'{k}={v}' for k, v in os.environ.items()))
sys.exit(0)
"""
PHRASE_9 = "run_all : conteneur indisponible (code {c}) : aucune suite portable lancée ; rien n'est écrit"
PHRASE_VOIE = "la preuve passe par le conteneur (bash tools/ci_local.sh run <branche>, puis bash tests/run_all.sh --mac)"


class SessionConteneur(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.base, True)
        self.racine = self.base / "depot"
        for nom, texte in (("alpha", SUITE_OK), ("beta", SUITE_OK), ("gamma", SUITE_OK)):
            (self.racine / "tests" / nom).mkdir(parents=True)
            (self.racine / "tests" / nom / f"test_{nom}.py").write_text(texte)
        (self.racine / "tests" / "suites_shell.txt").write_text("# aucune suite shell dans la fausse racine\n")
        (self.racine / "tests" / "suites_mac.txt").write_text("beta:python # essai : suite propre au Mac\n")
        self.home = self.base / "home"
        self.home.mkdir()
        texte = RUN_ALL.read_text(encoding="utf-8")
        self.assertIn(APPEL_GETPWUID, texte)
        texte = texte.replace("\nSUITES_NPM=(mothra:mothra)\n", "\nSUITES_NPM=()\n")
        (self.racine / "tests" / "run_all.sh").write_text(texte.replace(APPEL_GETPWUID, f"printf %s {str(self.home)!r}"), encoding="utf-8")
        (self.racine / "tools").mkdir()
        shutil.copy(PREUVE_ARBRE, self.racine / "tools" / "preuve_arbre.py")
        shutil.copy(RACINE_DEPOT / "tools" / "lab_paths.py", self.racine / "tools" / "lab_paths.py")   # R-20261105-7 : preuve_arbre.py lit le dossier de données du compte
        self.ci = self.racine / "tools" / "ci_local.sh"
        self.ci.write_text(FAUX_CI)
        (self.racine / "tools" / "morning_state.sh").write_text(FAUX_MATIN)   # le --staged complet garde la garde du matin
        self.donnees = self.home / ".pmzilla-lab"
        self.durees = self.base / "durees.tsv"
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
                    "PMZILLA_FINISH_LOCK_MAX_AGE", "PMZILLA_LAB_DATA", "CI_LOCAL_DOCKER", "CI_LOCAL_PREUVES_INDEX")
        env = {k: v for k, v in os.environ.items() if k not in retirees}
        env.update({"RUN_ALL_DEPS": "", "PMZILLA_LAB_DATA": str(self.donnees), "RUN_ALL_DURATIONS": str(self.durees)})
        if session is not None:
            env["CLAUDECODE"] = session
        env.update(variables)
        env = {k: v for k, v in env.items() if v is not None}
        return subprocess.run(["bash", str(self.racine / "tests" / "run_all.sh"), *arguments], env=env, cwd=self.racine,
                              capture_output=True, text=True, timeout=120)

    def selecteur(self, texte):
        (self.racine / "tools" / "select_suites.py").write_text(texte)

    def appels_ci(self):
        fichier = self.racine / "tools" / "ci_appels"
        return fichier.read_text().splitlines() if fichier.exists() else []

    def poser_code_ci(self, code):
        (self.racine / "tools" / "ci_code").write_text(str(code))

    def preuve_ecrite(self, suites):
        (self.racine / "tools" / "ci_ecrit").write_text(suites)

    def ciblee(self):
        return self.empreintes["pmzilla-run-targeted-ok"]

    def aucune_suite_portable_sur_le_mac(self, resultat):
        self.assertNotRegex(resultat.stdout, r"(alpha|gamma)\s+\d+ tests")

    def intactes(self):
        for nom, chemin in self.empreintes.items():
            self.assertEqual(chemin.read_text(), "a-conserver-" + nom, f"{nom} : ni écrite ni effacée")

    # --- 6.3 : la scission d'un lancement de session

    def test_staged_envoie_ses_suites_portables_avec_run_index_et_lance_les_suites_du_mac_ici(self):
        self.selecteur(SELECTEUR_DEUX)
        self.preuve_ecrite("alpha")
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
        self.assertIn("run_all : suites portables envoyées au conteneur : 1 ; suites propres au Mac lancées ici : 1\n", resultat.stdout)
        self.assertEqual(self.appels_ci(), ["run --index alpha"])
        self.assertRegex(resultat.stdout, r"beta\s+2 tests · OK")
        self.aucune_suite_portable_sur_le_mac(resultat)

    def test_un_lancement_nomme_envoie_ses_suites_portables_avec_run_travail_jamais_run_index(self):
        resultat = self.lancer("alpha", "beta", "gamma")
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
        self.assertIn("run_all : suites portables envoyées au conteneur : 2 ; suites propres au Mac lancées ici : 1\n", resultat.stdout)
        self.assertEqual(self.appels_ci(), ["run --travail alpha gamma"])
        self.assertRegex(resultat.stdout, r"beta\s+2 tests · OK")
        self.aucune_suite_portable_sur_le_mac(resultat)
        self.intactes()

    def test_un_lancement_nomme_de_suites_du_mac_seules_n_appelle_pas_le_conteneur(self):
        resultat = self.lancer("beta")
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
        self.assertIn("run_all : suites portables envoyées au conteneur : 0 ; suites propres au Mac lancées ici : 1\n", resultat.stdout)
        self.assertEqual(self.appels_ci(), [])
        self.intactes()

    def test_un_lancement_nomme_de_suites_portables_seules_ne_lance_rien_sur_le_mac(self):
        resultat = self.lancer("alpha")
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
        self.assertIn("run_all : suites portables envoyées au conteneur : 1 ; suites propres au Mac lancées ici : 0\n", resultat.stdout)
        self.assertEqual(self.appels_ci(), ["run --travail alpha"])
        self.aucune_suite_portable_sur_le_mac(resultat)
        self.assertFalse(self.durees.exists(), "aucune suite lancée ici : aucune ligne de durées")

    def test_staged_exigeant_l_execution_complete_passe_en_mode_complet_et_toute_la_passe_mac(self):
        self.preuve_ecrite("complet")
        for selecteur in (SELECTEUR_COMPLET, "raise SystemExit(7)\n", "print('select_suites : aucune suite à lancer')\n", None):
            if selecteur is None:
                (self.racine / "tools" / "select_suites.py").unlink()
            else:
                self.selecteur(selecteur)
            (self.racine / "tools" / "ci_appels").unlink(missing_ok=True)
            self.durees.unlink(missing_ok=True)
            resultat = self.lancer("--staged")
            self.assertEqual(resultat.returncode, 0, (selecteur, resultat.stdout + resultat.stderr))
            self.assertEqual(self.appels_ci(), ["run --index"], selecteur)
            self.assertRegex(resultat.stdout, r"beta\s+2 tests · OK")
            self.aucune_suite_portable_sur_le_mac(resultat)
            self.assertEqual(self.empreintes["pmzilla-run-all-ok"].read_text(), "a-conserver-pmzilla-run-all-ok", "l'empreinte complète n'est jamais écrite en session")
            self.assertEqual(self.ciblee().read_text().strip(), self.arbre, "seule l'empreinte ciblée peut l'être")

    def test_hors_session_le_ciblé_tourne_sur_le_mac_et_le_script_du_conteneur_n_est_pas_appele(self):
        self.selecteur(SELECTEUR_ALPHA)
        resultat = self.lancer("--staged", session=None)
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
        self.assertRegex(resultat.stdout, r"alpha\s+2 tests · OK")
        self.assertNotIn("envoyées au conteneur", resultat.stdout)
        self.assertEqual(self.appels_ci(), [])
        nommee = self.lancer("alpha", session=None)
        self.assertEqual(nommee.returncode, 0, nommee.stdout)
        self.assertEqual(self.appels_ci(), [])

    def test_le_script_du_conteneur_ne_recoit_ni_variable_de_test_ni_variable_de_l_appelant(self):
        self.lancer("alpha", CI_LOCAL_DOCKER="/bin/false", CI_LOCAL_PREUVES_INDEX=str(self.base / "faux"), CI_LOCAL_VERDICTS="x", CI_LOCAL_PREUVES="y")
        env = dict(l.split("=", 1) for l in (self.racine / "tools" / "ci_env").read_text().splitlines() if "=" in l)
        for nom in ("CI_LOCAL_DOCKER", "CI_LOCAL_PREUVES_INDEX", "CI_LOCAL_VERDICTS", "CI_LOCAL_PREUVES", "CI_LOCAL_COLIMA"):
            self.assertNotIn(nom, env, nom)
        self.assertEqual(env.get("PMZILLA_LAB_DATA"), str(self.donnees), "le dossier de données du compte, jamais celui de l'appelant")

    # --- R-20261105-7 : toute variable CI_LOCAL_* présente est retirée des deux appels (liste lue à l'exécution), PMZILLA_LAB_DATA imposé au dossier du compte

    def faux_preuve_arbre(self):
        # remplace la copie de tools/preuve_arbre.py de la fausse racine par un faux qui note son environnement (rendu vert : 0)
        (self.racine / "tools" / "preuve_arbre.py").write_text(FAUX_PREUVE_ARBRE)

    def environnement_note(self, nom_fichier):
        fichier = self.racine / "tools" / nom_fichier
        self.assertTrue(fichier.exists(), f"{nom_fichier} : l'appel n'a pas eu lieu")
        return dict(l.split("=", 1) for l in fichier.read_text().splitlines() if "=" in l)

    def test_une_variable_ci_local_inventee_de_l_appelant_n_atteint_pas_le_script_du_conteneur(self):
        self.lancer("alpha", CI_LOCAL_INVENTEE="valeur")
        env = self.environnement_note("ci_env")
        self.assertNotIn("CI_LOCAL_INVENTEE", env)

    def test_une_variable_ci_local_inventee_de_l_appelant_n_atteint_pas_l_appel_de_preuve_arbre(self):
        self.selecteur(SELECTEUR_DEUX)
        self.faux_preuve_arbre()
        resultat = self.lancer("--staged", CI_LOCAL_INVENTEE="valeur")
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
        env = self.environnement_note("pa_env")
        self.assertNotIn("CI_LOCAL_INVENTEE", env)
        self.assertEqual(env.get("PMZILLA_LAB_DATA"), str(self.donnees))

    def test_dossier_du_compte_introuvable_preuve_arbre_n_est_pas_appele_et_aucune_empreinte(self):
        # R-20261105-7 : un dossier du compte vide ne retombe jamais sur le dossier personnel de l'appelant
        texte = (self.racine / "tests" / "run_all.sh").read_text(encoding="utf-8")
        (self.racine / "tests" / "run_all.sh").write_text(texte.replace(f"printf %s {str(self.home)!r}", "printf %s ''"), encoding="utf-8")
        self.selecteur(SELECTEUR_DEUX)
        self.faux_preuve_arbre()
        resultat = self.lancer("--staged")
        self.assertFalse((self.racine / "tools" / "pa_env").exists(), "preuve_arbre.py n'est pas appelé")
        self.assertIn("run_all : empreinte ciblée non écrite (preuve du conteneur absente pour cet index)\n", resultat.stdout)
        self.assertFalse(self.ciblee().exists())

    def test_un_dossier_de_donnees_de_l_appelant_est_ignore_par_l_appel_de_preuve_arbre(self):
        self.selecteur(SELECTEUR_DEUX)
        self.faux_preuve_arbre()
        resultat = self.lancer("--staged", PMZILLA_LAB_DATA=str(self.base / "ailleurs"))
        self.assertEqual(resultat.returncode, 0, resultat.stdout + resultat.stderr)
        env = self.environnement_note("pa_env")
        self.assertEqual(env.get("PMZILLA_LAB_DATA"), str(self.donnees), "le dossier de données du compte, jamais celui de l'appelant")

    # --- 6.4 : l'empreinte ciblée d'une session

    def test_empreinte_ecrite_sur_une_ligne_verte_du_meme_arbre_une_partie_mac_verte_un_index_inchange(self):
        self.selecteur(SELECTEUR_DEUX)
        self.preuve_ecrite("alpha")
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn(f"run_all : empreinte ciblée écrite (conteneur et Mac) pour l'index {self.arbre[:12]}\n", resultat.stdout)
        self.assertEqual(self.ciblee().read_text().strip(), self.arbre)
        self.assertEqual(self.empreintes["pmzilla-run-all-ok"].read_text(), "a-conserver-pmzilla-run-all-ok")

    def test_empreinte_ecrite_quand_toutes_les_suites_selectionnees_sont_propres_au_mac(self):
        # T2-5 (a), décision de l'auteur du 2026-11-04 : sans suite portable, pas de ligne de preuve d'index ; l'arbre inchangé et la partie Mac verte restent exigés
        self.selecteur(SELECTEUR_BETA)
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertEqual(self.appels_ci(), [], "aucune suite portable : le conteneur n'est pas appelé")
        self.assertFalse((self.donnees / "ci" / "preuves-index").exists(), "aucune ligne de preuve d'index n'existe pour cet arbre")
        self.assertIn(f"run_all : empreinte ciblée écrite (conteneur et Mac) pour l'index {self.arbre[:12]}\n", resultat.stdout)
        self.assertEqual(self.ciblee().read_text().strip(), self.arbre)

    def test_toutes_les_suites_selectionnees_propres_au_mac_mais_rouges_aucune_empreinte(self):
        # T2-5 (a) : la partie Mac verte reste exigée même sans suite portable
        self.selecteur(SELECTEUR_BETA)
        (self.racine / "tests" / "beta" / "test_beta.py").write_text(SUITE_KO)
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertIn("run_all : empreinte ciblée non écrite (suites propres au Mac rouges)\n", resultat.stdout)
        self.assertFalse(self.ciblee().exists())

    def test_une_ligne_qui_ne_couvre_pas_les_suites_selectionnees_n_est_pas_une_preuve(self):
        self.selecteur(SELECTEUR_DEUX)
        self.preuve_ecrite("gamma")
        resultat = self.lancer("--staged")
        self.assertIn("run_all : empreinte ciblée non écrite (preuve du conteneur absente pour cet index)\n", resultat.stdout)
        self.assertFalse(self.ciblee().exists())

    def test_sans_ligne_de_preuve_pour_l_index_non_ecrite(self):
        self.selecteur(SELECTEUR_DEUX)
        resultat = self.lancer("--staged")   # le faux conteneur est vert mais n'écrit aucune ligne
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("run_all : empreinte ciblée non écrite (preuve du conteneur absente pour cet index)\n", resultat.stdout)
        self.assertFalse(self.ciblee().exists(), "l'ancienne empreinte ciblée a été effacée au départ")

    def test_une_ligne_d_un_autre_arbre_n_est_pas_une_preuve(self):
        self.selecteur(SELECTEUR_DEUX)
        (self.donnees / "ci").mkdir(parents=True)
        (self.donnees / "ci" / "preuves-index").write_text("1" * 40 + "\tcle\tcomplet\n")
        resultat = self.lancer("--staged")
        self.assertIn("(preuve du conteneur absente pour cet index)", resultat.stdout)
        self.assertFalse(self.ciblee().exists())

    def test_la_variable_d_essai_de_l_appelant_ne_fait_pas_une_preuve(self):
        self.selecteur(SELECTEUR_DEUX)
        faux = self.base / "faux-index"
        faux.write_text(f"{self.arbre}\tcle\tcomplet\n")
        resultat = self.lancer("--staged", CI_LOCAL_PREUVES_INDEX=str(faux))
        self.assertIn("(preuve du conteneur absente pour cet index)", resultat.stdout)
        self.assertFalse(self.ciblee().exists())

    def test_index_modifie_pendant_le_passage(self):
        self.selecteur(SELECTEUR_DEUX)
        self.preuve_ecrite("alpha")
        (self.racine / "tools" / "ci_pendant").write_text('echo changé > "$(dirname "$0")/../tests/nouveau.txt"; git add tests/nouveau.txt\n')
        resultat = self.lancer("--staged")
        self.assertIn("run_all : empreinte ciblée non écrite (index modifié pendant le passage)\n", resultat.stdout)
        self.assertFalse(self.ciblee().exists())

    def test_suites_propres_au_mac_rouges(self):
        self.selecteur(SELECTEUR_DEUX)
        self.preuve_ecrite("alpha")
        (self.racine / "tests" / "beta" / "test_beta.py").write_text(SUITE_KO)
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertIn("run_all : empreinte ciblée non écrite (suites propres au Mac rouges)\n", resultat.stdout)
        self.assertFalse(self.ciblee().exists())

    def test_conteneur_rouge_code_1_aucune_empreinte(self):
        self.selecteur(SELECTEUR_DEUX)
        self.poser_code_ci(1)
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertNotEqual(resultat.returncode, 9)
        self.assertFalse(self.ciblee().exists())
        self.assertRegex(resultat.stdout, r"beta\s+2 tests · OK", "la partie Mac tourne : le diagnostic est complet")

    def test_un_conteneur_rouge_est_nomme_dans_la_raison(self):
        # R-20261104-51 Q1 (a) : la raison distincte remplace « preuve du conteneur absente » dans ce seul cas
        self.selecteur(SELECTEUR_DEUX)
        self.poser_code_ci(1)
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertIn("run_all : empreinte ciblée non écrite (conteneur rouge (code 1) : sa sortie est plus haut, les lignes ci_passage et ci_local)\n", resultat.stdout)
        self.assertFalse(self.ciblee().exists())

    def test_un_conteneur_rouge_n_ecrit_pas_d_empreinte_meme_avec_une_ligne_verte_du_meme_arbre(self):
        # une ligne verte d'un passage précédent du même index ne rattrape jamais un conteneur rouge (R-20261104-51)
        self.selecteur(SELECTEUR_DEUX)
        (self.donnees / "ci").mkdir(parents=True)
        (self.donnees / "ci" / "preuves-index").write_text(f"{self.arbre}\tcle\tcomplet\n")
        self.poser_code_ci(1)
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertIn("run_all : empreinte ciblée non écrite (conteneur rouge (code 1) : sa sortie est plus haut, les lignes ci_passage et ci_local)\n", resultat.stdout)
        self.assertFalse(self.ciblee().exists())

    def test_autre_code_du_conteneur_est_un_echec_pas_un_code_9(self):
        # T2-3 (b), décision de l'auteur du 2026-11-04 : un code hors 0, 1, 3, 5, 6, 7 (127 reste un 9) ne lance rien ici, sort en 1 et dit le code
        self.selecteur(SELECTEUR_DEUX)
        for code in (2, 4, 130):
            self.poser_code_ci(code)
            for arguments in (("--staged",), ("alpha", "beta")):
                resultat = self.lancer(*arguments)
                self.assertEqual(resultat.returncode, 1, (code, arguments, resultat.stdout))
                self.assertIn(f"run_all : le script du conteneur a rendu un code inattendu ({code}) : aucune suite lancée ; rien n'est écrit\n", resultat.stdout)
                self.assertNotRegex(resultat.stdout, r"beta\s+\d+ tests", "pas même la suite propre au Mac du même passage")
                self.assertNotIn("TOTAL", resultat.stdout)
                self.assertFalse(self.durees.exists(), "aucune ligne de durées")
                self.intactes()   # ni écrite ni effacée

    # --- garde du matin légère du --staged complet (R-20261102-3, -5), GARDÉE par l'auteur (T2-1 (a)) : avant le conteneur, avant tout effacement d'empreinte

    def test_staged_complet_garde_du_matin_refusee_conteneur_non_appele_empreintes_intactes(self):
        (self.racine / "tools" / "m_code").write_text("1")
        for selecteur in (SELECTEUR_COMPLET, "raise SystemExit(7)\n", "print('select_suites : aucune suite à lancer')\n"):
            self.selecteur(selecteur)
            resultat = self.lancer("--staged")
            self.assertEqual(resultat.returncode, 6, resultat.stdout)
            self.assertIn("run_all : session Claude Code : lancement complet refusé : veille ou sauvegarde du jour en cours "
                          "(morning_state : ligne du faux module)", resultat.stdout)
            self.assertEqual(self.appels_ci(), [], "le conteneur n'est pas appelé sur un refus du matin")
            self.assertFalse(self.durees.exists())
            self.intactes()

    def test_staged_cible_et_nomme_ne_lisent_pas_le_matin(self):
        (self.racine / "tools" / "m_code").write_text("1")
        self.selecteur(SELECTEUR_ALPHA)
        self.assertEqual(self.lancer("--staged").returncode, 0)
        self.assertEqual(self.lancer("alpha").returncode, 0)
        self.assertFalse((self.racine / "tools" / "m_appels").exists(), "le module du matin n'est pas lu")

    def test_un_lancement_nomme_n_ecrit_ni_n_efface_l_empreinte_ciblee(self):
        self.preuve_ecrite("alpha")
        resultat = self.lancer("alpha", "beta")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.intactes()

    # --- 6.5 : conteneur indisponible, code 9, rien n'est lancé ni écrit

    def test_code_9_pour_chacun_des_codes_3_5_6_7_du_script_du_conteneur(self):
        self.selecteur(SELECTEUR_DEUX)
        for code in (3, 5, 6, 7):
            self.poser_code_ci(code)
            for arguments in (("--staged",), ("alpha", "beta")):
                (self.racine / "tools" / "ci_appels").unlink(missing_ok=True)
                resultat = self.lancer(*arguments)
                self.assertEqual(resultat.returncode, 9, (code, arguments, resultat.stdout))
                self.assertIn(PHRASE_9.format(c=code) + "\n", resultat.stdout)
                self.assertEqual(len(self.appels_ci()), 1, "le conteneur est appelé une fois")
                self.aucune_suite_portable_sur_le_mac(resultat)
                self.assertNotRegex(resultat.stdout, r"beta\s+\d+ tests", "pas même la suite propre au Mac du même passage")
                self.assertNotIn("TOTAL", resultat.stdout)
                self.assertFalse(self.durees.exists(), "aucune ligne de durées")
                self.intactes()

    def test_code_9_pour_le_code_8_place_libre_insuffisante_du_script_du_conteneur(self):
        # ci-local-image-prune, D6 : le code 8 de tools/ci_local.sh (place libre insuffisante) est un « conteneur indisponible » comme 3, 5, 6 et 7
        self.selecteur(SELECTEUR_DEUX)
        self.poser_code_ci(8)
        for arguments in (("--staged",), ("alpha", "beta")):
            (self.racine / "tools" / "ci_appels").unlink(missing_ok=True)
            resultat = self.lancer(*arguments)
            self.assertEqual(resultat.returncode, 9, (arguments, resultat.stdout))
            self.assertIn("run_all : conteneur indisponible (code 8) : aucune suite portable lancée ; rien n'est écrit\n", resultat.stdout)
            self.assertEqual(len(self.appels_ci()), 1, "le conteneur est appelé une fois")
            self.aucune_suite_portable_sur_le_mac(resultat)
            self.assertNotIn("TOTAL", resultat.stdout)
            self.assertFalse(self.durees.exists(), "aucune ligne de durées")
            self.intactes()

    def test_code_9_ne_note_aucune_empreinte_meme_sans_suite_portable_a_envoyer_au_prealable(self):
        self.selecteur(SELECTEUR_ALPHA)
        self.poser_code_ci(5)
        resultat = self.lancer("--staged")
        self.assertEqual(resultat.returncode, 9, resultat.stdout)
        self.assertEqual(self.ciblee().read_text(), "a-conserver-pmzilla-run-targeted-ok", "pas même effacée")

    def test_script_du_conteneur_absent_code_9_avec_le_code_127(self):
        self.ci.unlink()
        resultat = self.lancer("alpha")
        self.assertEqual(resultat.returncode, 9, resultat.stdout)
        self.assertIn(PHRASE_9.format(c=127) + "\n", resultat.stdout)

    def test_codes_0_et_1_ne_donnent_jamais_9(self):
        self.selecteur(SELECTEUR_DEUX)
        for code, attendu in ((0, 0), (1, 1)):
            self.poser_code_ci(code)
            for arguments in (("--staged",), ("alpha", "beta")):
                self.assertEqual(self.lancer(*arguments).returncode, attendu, (code, arguments))

    # --- gardes de session de --staged : la racine injectée et le dossier de données ne peuvent pas fabriquer une preuve

    def test_racine_injectee_refusee_pour_un_staged_complet_empreintes_intactes(self):
        for selecteur in (SELECTEUR_COMPLET, "raise SystemExit(7)\n", "print('select_suites : aucune suite à lancer')\n"):
            self.selecteur(selecteur)
            resultat = self.lancer("--staged", RUN_ALL_ROOT=str(self.racine))
            self.assertEqual(resultat.returncode, 6, resultat.stdout)
            self.assertIn("run_all : session Claude Code : RUN_ALL_ROOT posée pour un lancement complet, lancement refusé", resultat.stdout)
            self.assertEqual(self.appels_ci(), [])
            self.intactes()

    def test_dossier_de_donnees_different_refuse_pour_un_staged_complet_empreintes_intactes(self):
        for selecteur in (SELECTEUR_COMPLET, "raise SystemExit(7)\n", "print('select_suites : aucune suite à lancer')\n"):
            self.selecteur(selecteur)
            resultat = self.lancer("--staged", PMZILLA_LAB_DATA=str(self.base / "ailleurs"))
            self.assertEqual(resultat.returncode, 6, resultat.stdout)
            self.assertIn("run_all : session Claude Code : PMZILLA_LAB_DATA différente du dossier de données du compte", resultat.stdout)
            self.assertEqual(self.appels_ci(), [])
            self.assertFalse((self.base / "ailleurs").exists())
            self.intactes()

    def test_un_staged_cible_garde_le_dossier_du_compte_meme_avec_un_autre_dossier_de_donnees_en_variable(self):
        self.selecteur(SELECTEUR_DEUX)
        self.preuve_ecrite("alpha")
        resultat = self.lancer("--staged", PMZILLA_LAB_DATA=str(self.base / "ailleurs"))
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertFalse((self.base / "ailleurs").exists(), "rien n'est écrit dans le dossier choisi par l'appelant")
        self.assertEqual(self.ciblee().read_text().strip(), self.arbre, "la preuve est lue dans le dossier du compte")

    def test_dossier_de_donnees_du_compte_et_formes_equivalentes_permis(self):
        self.selecteur(SELECTEUR_COMPLET)
        self.preuve_ecrite("complet")
        for valeur in (None, str(self.donnees), str(self.donnees) + "/", "", str(self.home) + "/./.pmzilla-lab"):
            self.assertEqual(self.lancer("--staged", PMZILLA_LAB_DATA=valeur).returncode, 0, valeur)

    # --- 6.9 : les trous de la revue de T1

    def test_les_lancements_permis_en_session_ont_leur_code_exact(self):
        self.selecteur(SELECTEUR_ALPHA)
        self.preuve_ecrite("alpha")
        attendus = (("alpha", 0), ("--mac", 0), ("--staged", 0))   # --portable : refusé en session (T2-2), test suivant
        for argument, code in attendus:
            resultat = self.lancer(argument)
            self.assertEqual(resultat.returncode, code, (argument, resultat.stdout + resultat.stderr))
            self.assertNotIn("refusé en session", resultat.stdout, argument)

    def test_portable_refuse_en_session_code_6_avec_la_voie_du_conteneur(self):
        # T2-2 (a), décision de l'auteur du 2026-11-04 : --portable ferait tourner des suites portables sur le Mac en session
        resultat = self.lancer("--portable")
        self.assertEqual(resultat.returncode, 6, resultat.stdout)
        self.assertEqual(resultat.stdout, "run_all : --portable refusé en session : " + PHRASE_VOIE + "\n")
        self.assertEqual(self.appels_ci(), [])
        self.assertFalse(self.durees.exists())
        self.intactes()

    def test_v_seul_en_session_est_un_lancement_complet_nu_refuse(self):
        resultat = self.lancer("-v")
        self.assertEqual(resultat.returncode, 6, resultat.stdout)
        self.assertEqual(resultat.stdout, "run_all : lancement complet refusé en session : " + PHRASE_VOIE + "\n")
        self.assertEqual(self.appels_ci(), [])
        self.intactes()

    def test_branch_combine_avec_une_autre_option_en_session_est_un_usage_code_2(self):
        for arguments in (("--branch", "alpha"), ("--branch", "--staged"), ("--branch", "--portable"), ("--branch", "--mac")):
            resultat = self.lancer(*arguments)
            self.assertEqual(resultat.returncode, 2, (arguments, resultat.stdout))
            self.assertIn("run_all : --branch ne se combine pas avec", resultat.stdout)
            self.assertNotIn("refusé en session", resultat.stdout)
        self.intactes()

    # --- 6.8 / 7.3 : ce qui tombe avec le verrou de session (D3)

    def test_le_lanceur_n_a_plus_ni_verrou_de_session_ni_garde_du_runner(self):
        # La garde du matin légère n'est PAS retirée (décision de l'auteur du 2026-11-04, T2-1 (a)) : « morning_state » n'est plus un motif interdit
        texte = RUN_ALL.read_text(encoding="utf-8")
        code = "\n".join(l for l in texte.splitlines() if not l.lstrip().startswith("#"))
        for motif in ("runner_guard", "prendre_verrou_session", "garde_lancement_complet_session", "verrous/run-all-session",
                      "RUN_ALL_GUARD_LOCK", "RUN_ALL_GUARD_WAIT"):
            self.assertNotIn(motif, code, motif)
        self.assertIn('"$LANCEUR_DIR/../tools/morning_state.sh" runner 2>&1', code)
        self.assertNotIn("tools/runner_guard.sh", texte, "l'en-tête ne renvoie plus à la garde retirée")
        self.assertFalse((RACINE_DEPOT / "tools" / "runner_guard.sh").exists())

    def test_aucun_fichier_suivi_ne_lit_plus_les_variables_de_la_garde_retiree(self):
        # Contrepartie du retrait de la classe EnSession et des tests de refus de RUN_ALL_GUARD_LOCK / RUN_ALL_GUARD_WAIT (mécanisme disparu avec
        # la garde du code 8, R-20261104-7 P2, REMOVED « The guard's test variables are refused in a session ») : aucun fichier suivi, hors
        # commentaires et hors les tests qui les nomment comme motifs interdits, ne lit plus ces deux variables (validé par le chat, 2026-11-04).
        fichiers = subprocess.run(["git", "-C", str(RACINE_DEPOT), "ls-files"], capture_output=True, text=True, check=True).stdout.split()
        self.assertIn("tests/run_all.sh", fichiers, "la liste des fichiers suivis est lue (sinon le test passerait à vide)")
        permis = {"tests/run_all/test_session_conteneur.py"}
        trouves = []
        for nom in fichiers:
            if nom in permis or nom.startswith("openspec/") or nom.endswith((".md", ".png", ".svg", ".ico", ".woff2", ".json.gz")):
                continue
            chemin = RACINE_DEPOT / nom
            try:
                texte = chemin.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for numero, ligne in enumerate(texte.splitlines(), 1):
                code = ligne.split("#", 1)[0] if nom.endswith((".sh", ".py", ".txt", ".yaml", ".yml", ".toml")) else ligne
                if "RUN_ALL_GUARD_LOCK" in code or "RUN_ALL_GUARD_WAIT" in code:
                    trouves.append(f"{nom}:{numero}")
        self.assertEqual(trouves, [], "variables de la garde retirée encore lues : " + ", ".join(trouves))

    def test_l_en_tete_dit_le_code_9_et_ce_qui_est_retire(self):
        texte = RUN_ALL.read_text(encoding="utf-8")
        entete = texte[:texte.index("set -u")]
        self.assertRegex(entete, r"9 session Claude Code : conteneur indisponible")
        self.assertRegex(entete, r"(?i)retir")
        self.assertIn("conteneur indisponible (code <c>) : aucune suite portable lancée ; rien n'est écrit", entete)
        self.assertNotRegex(entete, r"8 lancement ciblé, filtré")

    def test_les_pretest_de_mothra_n_appellent_plus_la_garde(self):
        for chemin in ("mothra/package.json", "mothra/contract/package.json", "mothra/front/package.json", "mothra/server/package.json"):
            self.assertNotIn("runner_guard", (RACINE_DEPOT / chemin).read_text(encoding="utf-8"), chemin)


if __name__ == "__main__":
    unittest.main()
