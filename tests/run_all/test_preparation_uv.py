"""
tests/run_all.sh prépare les environnements uv des scripts à dépendances en ligne AVANT la phase parallèle (R-20261101-104, la course du cache uv
entre deux uv run concurrents du même script) : un « uv sync --script » par script, l'un après l'autre, jamais le script lui-même.

    python3 -m unittest discover -s tests/run_all -v

Le lanceur est pointé sur un dossier temporaire (RUN_ALL_ROOT) ; un faux uv placé devant le vrai dans le PATH note chaque appel dans un journal,
répond aux « sync » sans rien installer (code réglable, un échec n'est qu'un avertissement) et passe les « run » au vrai uv, comme test_run_all.py.
"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

DEPOT = Path(__file__).resolve().parents[2]
RUN_ALL = DEPOT / "tests" / "run_all.sh"
SUITE_OK = "import unittest\nclass T(unittest.TestCase):\n    def test_a(self): pass\n    def test_b(self): pass\n"
SCRIPT_A_BLOC = ('# /// script\n# requires-python = ">=3.11"\n# dependencies = ["pyyaml"]\n# ///\n'
                 'from pathlib import Path\nPath("{marqueur}").write_text("lance")\n')
FAUX_UV = """#!/bin/sh
printf '%s\\n' "$*" >> "$FAUX_UV_JOURNAL"
case "$1" in
  sync)
    printf 'debut %s\\n' "$3" >> "$FAUX_UV_JOURNAL.evenements"
    sleep 0.2
    if [ -n "${FAUX_UV_CREE_VERROU:-}" ]; then : > "$3.lock"; fi
    printf 'fin %s\\n' "$3" >> "$FAUX_UV_JOURNAL.evenements"
    exit "${FAUX_UV_SYNC_CODE:-0}" ;;
  run) shift; exec "$VRAI_UV" run "$@" ;;
esac
exit 0
"""


class PreparationDesEnvironnementsUv(unittest.TestCase):
    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.base = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)
        self.addCleanup(shutil.rmtree, self.base, True)
        self.vrai_uv = shutil.which("uv")
        if self.vrai_uv is None:
            self.skipTest("uv absent du PATH")
        self.bin = self.base / "bin"
        self.bin.mkdir()
        (self.bin / "uv").write_text(FAUX_UV)
        (self.bin / "uv").chmod(0o755)
        self.journal = self.base / "uv-journal.txt"
        self.durees = self.base / "durees.tsv"
        self.marqueur = self.base / "script-lance"
        for nom in ("alpha", "beta"):
            dossier = self.racine / "tests" / nom
            dossier.mkdir(parents=True)
            (dossier / f"test_{nom}.py").write_text(SUITE_OK)
        # La sélection ne lit que les fichiers suivis : la racine factice est un dépôt Git (les fichiers ajoutés à l'index suffisent).
        subprocess.run(["git", "init", "-q"], cwd=self.racine, check=True)

    def script(self, chemin, verrou=False):
        fichier = self.racine / chemin
        fichier.parent.mkdir(parents=True, exist_ok=True)
        fichier.write_text(SCRIPT_A_BLOC.format(marqueur=self.marqueur))
        if verrou:
            Path(f"{fichier}.lock").write_text("version = 1\n")
        subprocess.run(["git", "add", "-A"], cwd=self.racine, check=True)

    def lancer(self, *arguments, **variables):
        # Les variables de la garde du runner (verrou de session) ne sont plus posées : T2 de R-182 retire cette garde (R-20261104-7 P2).
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS", "CLAUDECODE",
                                                                "RUN_ALL_JOBS", "DBTEST_PORT")}
        env.update({"RUN_ALL_ROOT": str(self.racine), "RUN_ALL_DEPS": "", "RUN_ALL_DURATIONS": str(self.durees), "RUN_ALL_JOBS": "2",
                    "PATH": f"{self.bin}{os.pathsep}{env['PATH']}", "FAUX_UV_JOURNAL": str(self.journal), "VRAI_UV": self.vrai_uv,
                    "TMPDIR": str(self.base)}, **variables)
        return subprocess.run(["bash", str(RUN_ALL), *arguments], env=env, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)

    def appels(self):
        return self.journal.read_text().splitlines() if self.journal.exists() else []

    def test_la_preparation_precede_la_phase_parallele_un_script_apres_l_autre(self):
        self.script("tools/outil_a.py")
        self.script("tools/outil_b.py")
        resultat = self.lancer("alpha", "beta")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        appels = self.appels()
        syncs = [k for k, a in enumerate(appels) if a.startswith("sync ")]
        runs = [k for k, a in enumerate(appels) if a.startswith("run ")]
        self.assertEqual([appels[k] for k in syncs], ["sync --script tools/outil_a.py", "sync --script tools/outil_b.py"])   # ordre trié, sans --frozen
        self.assertEqual(len(runs), 2, appels)                                                                             # une par suite
        self.assertLess(max(syncs), min(runs), appels)                                                                     # toute la préparation d'abord
        evenements = Path(f"{self.journal}.evenements").read_text().splitlines()   # un sync à la fois : jamais deux débuts d'affilée
        self.assertEqual(evenements, ["debut tools/outil_a.py", "fin tools/outil_a.py", "debut tools/outil_b.py", "fin tools/outil_b.py"])
        self.assertIn("run_all : environnements uv préparés : 2 script(s)", resultat.stdout)
        self.assertLess(resultat.stdout.index("environnements uv préparés"), resultat.stdout.index("alpha  "))

    def test_aucun_appel_du_script_lui_meme(self):
        self.script("tools/outil_a.py")
        resultat = self.lancer("alpha", "beta")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertFalse(self.marqueur.exists())
        self.assertFalse(any("outil_a.py" in a and not a.startswith("sync --script ") for a in self.appels()), self.appels())

    def test_un_verrou_suivi_est_utilise_tel_quel_avec_frozen(self):
        self.script("tools/outil_a.py", verrou=True)
        self.lancer("alpha", "beta")
        self.assertIn("sync --script tools/outil_a.py --frozen", self.appels())
        self.assertTrue((self.racine / "tools" / "outil_a.py.lock").exists())   # le verrou suivi n'est jamais retiré

    def test_un_verrou_cree_par_la_preparation_est_retire(self):
        self.script("tools/outil_a.py")
        resultat = self.lancer("alpha", "beta", FAUX_UV_CREE_VERROU="1")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertFalse((self.racine / "tools" / "outil_a.py.lock").exists())

    def test_une_preparation_en_echec_donne_un_avertissement_les_suites_partent_et_la_ligne_total_le_nomme(self):
        self.script("tools/outil_a.py")
        self.script("tools/outil_b.py")
        resultat = self.lancer("alpha", "beta", FAUX_UV_SYNC_CODE="3")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)                       # le code de sortie ne change pas
        self.assertIn("run_all : avertissement : préparation uv en échec : tools/outil_a.py (code 3)", resultat.stdout)
        syncs = [a for a in self.appels() if a.startswith("sync ")]
        self.assertEqual(syncs, ["sync --script tools/outil_a.py", "sync --script tools/outil_b.py"])   # les autres scripts sont préparés
        self.assertEqual(len([a for a in self.appels() if a.startswith("run ")]), 2)    # aucune suite sautée
        self.assertRegex(resultat.stdout, r"alpha +2 tests · OK")
        total = next(l for l in resultat.stdout.splitlines() if l.startswith("TOTAL :"))
        self.assertIn("tous réussis", total)
        self.assertTrue(total.endswith(" · avertissement : préparation uv en échec : tools/outil_a.py, tools/outil_b.py"), total)
        self.assertIn("\tpreparation\tuv\t", self.durees.read_text())
        self.assertIn("\téchec\t", self.durees.read_text())

    def test_sans_echec_la_ligne_total_n_a_pas_d_avertissement(self):
        self.script("tools/outil_a.py")
        resultat = self.lancer("alpha", "beta")
        self.assertNotIn("avertissement", resultat.stdout)

    def test_la_duree_de_la_preparation_est_ecrite_dans_le_fichier_des_durees(self):
        self.script("tools/outil_a.py")
        resultat = self.lancer("alpha", "beta")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        lignes = [l.split("\t") for l in self.durees.read_text().splitlines() if "\tpreparation\t" in l]
        self.assertEqual(len(lignes), 1, self.durees.read_text())
        champs = lignes[0]
        self.assertEqual(len(champs), 10)
        self.assertEqual((champs[4], champs[5], champs[8]), ("preparation", "uv", "ok"))
        self.assertRegex(champs[6], r"^\d+\.\d$")
        self.assertIn("préparation uv", resultat.stdout)   # dans la liste des plus lentes

    def test_en_serie_ou_sans_script_a_bloc_rien_n_est_prepare(self):
        self.script("tools/outil_a.py")
        resultat = self.lancer("alpha", "beta", RUN_ALL_JOBS="1")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertFalse([a for a in self.appels() if a.startswith("sync ")])
        self.assertNotIn("environnements uv", resultat.stdout)
        (self.racine / "tools" / "outil_a.py").unlink()
        sans = self.lancer("alpha", "beta")
        self.assertFalse([a for a in self.appels() if a.startswith("sync ")])
        self.assertNotIn("environnements uv", sans.stdout)

    def test_les_trois_selections_de_scripts_donnent_le_meme_ensemble_sur_l_arbre_du_depot(self):
        # Gap-detector. Source unique : l'étape de préparation de ci/Dockerfile (ligne 53), qui construit l'image à partir d'une archive git, donc des
        # seuls fichiers suivis. Les deux autres lectures la suivent : la clé de l'image (scripts_pep723 de tools/ci_local.sh) et la préparation de
        # tests/run_all.sh (scripts_uv_suivis). Chaque commande est extraite du texte de son fichier, puis lancée sur l'arbre du dépôt.
        def lancer(commande):
            sortie = subprocess.run(["bash", "-c", commande], cwd=DEPOT, capture_output=True, text=True, check=True).stdout
            return sorted(l for l in sortie.splitlines() if l)

        suivis = set(lancer("git ls-files"))
        dockerfile = re.search(r"\$\(grep -rl --include='\*\.py' '\^# /// script' ([^)]+)\)", (DEPOT / "ci" / "Dockerfile").read_text(encoding="utf-8"))
        self.assertIsNotNone(dockerfile)
        image = sorted(set(lancer(f"grep -rl --include='*.py' '^# /// script' {dockerfile.group(1)}")) & suivis)
        ci_local = re.search(r"git grep -l '\^# /// script' \"\$c\" -- ([^|]+?) 2>/dev/null", (DEPOT / "tools" / "ci_local.sh").read_text(encoding="utf-8"))
        self.assertIsNotNone(ci_local)
        # --cached avant le motif (après, git le lit comme une révision et échoue) ; pipefail : un git grep en échec fait échouer le test, jamais une liste vide
        cle = lancer(f"set -o pipefail; git grep --cached -l '^# /// script' -- {ci_local.group(1)} | LC_ALL=C sort")
        fonction = re.search(r"^scripts_uv_suivis\(\) \{.*?^\}$", RUN_ALL.read_text(encoding="utf-8"), re.S | re.M)
        self.assertIsNotNone(fonction)
        lanceur = lancer(fonction.group(0) + "\nscripts_uv_suivis")
        self.assertTrue(image)
        self.assertEqual(lanceur, image)
        self.assertEqual(cle, image)


if __name__ == "__main__":
    unittest.main()
