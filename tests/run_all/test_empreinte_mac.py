"""tests/run_all.sh --mac : empreinte du Mac (ci-local-runner, design D7, tâche 12.1).

    python3 -m unittest discover -s tests/run_all -v

--mac vert, worktree propre au départ et à la fin, arbre de HEAD inchangé : l'arbre est ajouté à pmzilla-run-mac-ok du dossier Git commun
(une ligne par arbre, propriétaire seul, ligne retirée au départ). Jamais lue par pre-commit. Vrais enfants : le lanceur, Git et unittest sur un
faux dépôt temporaire (RUN_ALL_ROOT).

Remplace : rien (--mac n'écrivait aucune empreinte). Retrait : tombe avec D7, quand tests/suites_mac.txt ne liste plus aucune suite.
"""
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

RUN_ALL = Path(__file__).resolve().parents[1] / "run_all.sh"
DEPOT = RUN_ALL.parents[1]
SUITE_OK = "import unittest\nclass T(unittest.TestCase):\n    def test_a(self): pass\n"
SUITE_KO = "import unittest\nclass T(unittest.TestCase):\n    def test_casse(self): self.assertEqual(1, 2)\n"
SHELL_OK = 'echo "ok : un"\necho "1 réussis, 0 échec(s)"\n'
LISTE = "# suites propres au Mac\nbeta:python # raison de beta\n"


def scripts_shell():
    chemins = []
    for ligne in (RUN_ALL.parent / "suites_shell.txt").read_text(encoding="utf-8").splitlines():
        mots = ligne.split("#", 1)[0].split()
        if mots:
            chemins.append(mots[0])
    return chemins


class EmpreinteMac(unittest.TestCase):
    def setUp(self):
        self.racine = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.racine, True)
        for nom in ("alpha", "beta"):
            self.ecrire(f"tests/{nom}/test_{nom}.py", SUITE_OK)
        for chemin in scripts_shell():
            self.ecrire(chemin, SHELL_OK)
        self.ecrire("tests/suites_mac.txt", LISTE)
        self.git("init", "-q")
        self.git("add", "-A")
        self.valider("base")

    def git(self, *arguments):
        return subprocess.run(["git", *arguments], cwd=self.racine, capture_output=True, text=True, check=True).stdout.strip()

    def valider(self, message):
        self.git("-c", "user.email=t@example.org", "-c", "user.name=test", "commit", "-q", "-m", message)

    def ecrire(self, relatif, texte):
        chemin = self.racine / relatif
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte)

    def lancer(self, *arguments):
        env = {k: v for k, v in os.environ.items() if k not in ("PMZILLA_ENTREES_JUGE_CHANGEES", "PMZILLA_NO_EVALS", "DBTEST_PORT", "CLAUDECODE")}
        env.update({"RUN_ALL_ROOT": str(self.racine), "RUN_ALL_DEPS": "", "RUN_ALL_JOBS": "1"})
        return subprocess.run(["bash", str(RUN_ALL), *arguments], env=env, capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)

    @property
    def fichier(self):
        return self.racine / ".git" / "pmzilla-run-mac-ok"

    @property
    def arbre(self):
        return self.git("rev-parse", "HEAD^{tree}")

    def test_vert_sur_arbre_propre_ecrit_l_arbre_une_seule_fois(self):
        resultat = self.lancer("--mac")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertEqual(self.fichier.read_text().splitlines(), [self.arbre])
        phrase = re.search(r"(?m)^run_all : empreinte Mac écrite pour l'arbre (\S+)$", resultat.stdout)
        self.assertIsNotNone(phrase, resultat.stdout)
        self.assertTrue(self.arbre.startswith(phrase.group(1)))
        self.assertGreater(resultat.stdout.index("run_all : empreinte Mac écrite"), resultat.stdout.index("TOTAL :"))
        self.assertEqual(self.lancer("--mac").returncode, 0)
        self.assertEqual(self.fichier.read_text().splitlines(), [self.arbre])          # une ligne par arbre

    def test_fichier_lisible_par_son_proprietaire_seul(self):
        self.assertEqual(self.lancer("--mac").returncode, 0)
        self.assertEqual(stat.S_IMODE(self.fichier.stat().st_mode) & 0o077, 0)

    def test_les_lignes_des_autres_arbres_restent(self):
        self.fichier.write_text("autre-arbre\n")
        self.assertEqual(self.lancer("--mac").returncode, 0)
        self.assertEqual(self.fichier.read_text().splitlines(), ["autre-arbre", self.arbre])

    def test_rouge_retire_la_ligne_de_l_arbre_et_n_ecrit_rien(self):
        self.fichier.write_text(f"autre-arbre\n{self.arbre}\n")
        self.ecrire("tests/beta/test_beta.py", SUITE_KO)
        self.git("add", "-A")
        self.valider("rouge")
        self.fichier.write_text(f"autre-arbre\n{self.arbre}\n")
        resultat = self.lancer("--mac")
        self.assertEqual(resultat.returncode, 1, resultat.stdout)
        self.assertEqual(self.fichier.read_text().splitlines(), ["autre-arbre"])       # la ligne de l'arbre testé a disparu au départ
        self.assertNotIn("empreinte Mac", resultat.stdout)

    def test_arbre_non_propre_au_depart_n_ecrit_rien_et_dit_la_raison(self):
        self.ecrire("fichier_sale.txt", "x\n")
        resultat = self.lancer("--mac")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertFalse(self.fichier.exists())
        self.assertIn("run_all : empreinte Mac non écrite (arbre non propre)", resultat.stdout)

    def test_arbre_modifie_pendant_le_passage_n_ecrit_rien(self):
        # Une suite de la liste salit le worktree pendant le passage : propre au départ, plus propre à la fin.
        self.ecrire("tests/beta/test_beta.py", SUITE_OK + f"\nopen({str(self.racine / 'salissure.txt')!r}, 'w').write('x')\n")
        self.git("add", "-A")
        self.valider("suite qui salit")
        resultat = self.lancer("--mac")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertFalse(self.fichier.exists())
        self.assertIn("run_all : empreinte Mac non écrite (arbre non propre)", resultat.stdout)

    def test_hors_depot_git_dit_la_raison(self):
        shutil.rmtree(self.racine / ".git")
        resultat = self.lancer("--mac")
        self.assertEqual(resultat.returncode, 0, resultat.stdout)
        self.assertIn("run_all : empreinte Mac non écrite (hors dépôt Git)", resultat.stdout)

    def test_ni_portable_ni_complet_n_ecrit_l_empreinte_mac(self):
        self.assertEqual(self.lancer("--portable").returncode, 0)
        self.assertFalse(self.fichier.exists())
        self.assertEqual(self.lancer("alpha").returncode, 0)
        self.assertFalse(self.fichier.exists())
        self.assertNotIn("empreinte Mac", self.lancer("--portable").stdout)

    def test_un_lancement_mac_n_ecrit_pas_les_empreintes_de_pre_commit(self):
        self.assertEqual(self.lancer("--mac").returncode, 0)
        for nom in ("pmzilla-run-all-ok", "pmzilla-run-targeted-ok", "pmzilla-run-branch-ok"):
            self.assertFalse((self.racine / ".git" / nom).exists(), nom)

    def test_pre_commit_et_pre_push_de_commit_ne_lisent_pas_le_fichier_du_mac(self):
        # Le fichier du Mac n'est lu que par tools/preuve_arbre.py (preuve « conteneur ») : pre-commit ne le nomme pas.
        self.assertNotIn("pmzilla-run-mac-ok", (DEPOT / "tools" / "hooks" / "pre-commit").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
