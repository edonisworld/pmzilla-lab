"""
tools/preuve_arbre.py (ci-local-runner, design D8, tâche 12.2) : `preuve(arbre, worktree)` dans chaque cas, et sa ligne de commande (python3 -I).
Ordre : complete, conteneur, ciblee, aucune. Vrais enfants : l'outil, Git sur un dépôt jetable ; le dossier de données est un dossier jetable
(PMZILLA_LAB_DATA), jamais le vrai ci/preuves.
Remplace : rien (fonction neuve ; les deux lectures d'empreinte de train_ready.py y ont été déplacées). Retrait : `ciblee` tombe avec D10.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
OUTIL = RACINE / "tools" / "preuve_arbre.py"
sys.path.insert(0, str(RACINE / "tools"))
import preuve_arbre  # noqa: E402

TROIS = "portable,base,e2e"


class AvecDepot(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.base, True)
        self.depot = self.base / "depot"
        self.depot.mkdir()
        self.git("init", "-q", "-b", "main")
        (self.depot / "f.txt").write_text("un\n")
        self.git("add", "-A")
        self.git("-c", "user.email=t@example.org", "-c", "user.name=test", "commit", "-q", "-m", "base")
        self.arbre = self.git("rev-parse", "HEAD^{tree}")
        self.donnees = self.base / "donnees"
        (self.donnees / "ci").mkdir(parents=True)
        self.preuves = self.donnees / "ci" / "preuves"
        self.mac = self.depot / ".git" / "pmzilla-run-mac-ok"

    def git(self, *arguments):
        return subprocess.run(["git", *arguments], cwd=self.depot, capture_output=True, text=True, check=True).stdout.strip()

    def ecrire_complete(self, arbre=None):
        (self.depot / ".git" / "pmzilla-run-all-ok").write_text((arbre or self.arbre) + "\n")

    def ecrire_branche(self, arbre=None, suites="alpha,beta"):
        (self.depot / ".git" / "pmzilla-run-branch-ok").write_text(f"{arbre or self.arbre}\t{suites}\n")

    def ecrire_preuves(self, phases=TROIS, arbre=None):
        self.preuves.write_text(f"{arbre or self.arbre}\tcle\t{phases}\n")

    def ecrire_mac(self, arbre=None):
        self.mac.write_text((arbre or self.arbre) + "\n")

    def preuve(self, worktree=True):
        return preuve_arbre.preuve(self.arbre, worktree=self.depot if worktree else None, preuves=self.preuves, mac=self.mac)

    def cli(self, *arguments, donnees=True):
        env = {k: v for k, v in os.environ.items() if not k.startswith("PMZILLA_LAB_")}
        if donnees:
            env["PMZILLA_LAB_DATA"] = str(self.donnees)
        return subprocess.run([sys.executable, "-I", str(OUTIL), *arguments], cwd=self.depot, env=env, capture_output=True, text=True, timeout=60,
                              stdin=subprocess.DEVNULL)


class Preuve(AvecDepot):
    def test_aucune_preuve(self):
        self.assertIsNone(self.preuve())

    def test_complete(self):
        self.ecrire_complete()
        self.assertEqual(self.preuve(), "complete")

    def test_complete_d_un_autre_arbre_n_est_pas_une_preuve(self):
        self.ecrire_complete("1" * 40)
        self.assertIsNone(self.preuve())

    def test_complete_mal_formee_n_est_pas_une_preuve(self):
        self.ecrire_complete("pas-un-arbre")
        self.assertIsNone(self.preuve())

    def test_conteneur(self):
        self.ecrire_preuves()
        self.ecrire_mac()
        self.assertEqual(self.preuve(), "conteneur")

    def test_conteneur_se_lit_sans_worktree(self):
        self.ecrire_preuves()
        self.ecrire_mac()
        self.assertEqual(preuve_arbre.preuve(self.arbre, preuves=self.preuves, mac=self.mac), "conteneur")

    def test_conteneur_sans_ligne_mac(self):
        self.ecrire_preuves()
        self.assertIsNone(self.preuve())

    def test_ligne_mac_sans_conteneur(self):
        self.ecrire_mac()
        self.assertIsNone(self.preuve())

    def test_conteneur_exige_les_trois_phases(self):
        self.ecrire_mac()
        for phases in ("portable,base", "portable,e2e", "base,e2e", "portable", ""):
            with self.subTest(phases=phases):
                self.ecrire_preuves(phases)
                self.assertIsNone(self.preuve())

    def test_conteneur_exige_exactement_portable_base_e2e(self):
        # revue croisée tranche 2 (D6) : le troisième champ est EXACTEMENT « portable,base,e2e » ; un autre ordre ou une phase en plus n'est pas une preuve
        self.ecrire_mac()
        for phases in ("e2e,portable,base", "portable,base,e2e,autre", "portable,base,e2e,e2e", "portable, base, e2e"):
            with self.subTest(phases=phases):
                self.ecrire_preuves(phases)
                self.assertIsNone(self.preuve())

    def test_la_derniere_ligne_de_l_arbre_decide(self):
        self.ecrire_mac()
        self.preuves.write_text(f"{self.arbre}\tcle\t{TROIS}\n{self.arbre}\tcle\tportable,base\n")
        self.assertIsNone(self.preuve())

    def test_conteneur_d_un_autre_arbre(self):
        self.ecrire_preuves(arbre="2" * 40)
        self.ecrire_mac("2" * 40)
        self.assertIsNone(self.preuve())

    def test_ligne_de_preuves_mal_formee_est_ignoree(self):
        self.ecrire_mac()
        self.preuves.write_text(f"{self.arbre}\t{TROIS}\n")   # deux champs
        self.assertIsNone(self.preuve())

    def test_une_ligne_ne_suffit_pas_entre_plusieurs_arbres(self):
        self.ecrire_mac()
        self.preuves.write_text(f"{'3' * 40}\tcle\t{TROIS}\n{self.arbre}\tcle\t{TROIS}\n")
        self.assertEqual(self.preuve(), "conteneur")

    def test_ciblee(self):
        self.ecrire_branche()
        self.assertEqual(self.preuve(), "ciblee")

    def test_ciblee_demande_un_worktree(self):
        self.ecrire_branche()
        self.assertIsNone(preuve_arbre.preuve(self.arbre, preuves=self.preuves, mac=self.mac))

    def test_ciblee_d_un_autre_arbre(self):
        self.ecrire_branche("4" * 40)
        self.assertIsNone(self.preuve())

    def test_ordre_complete_puis_conteneur_puis_ciblee(self):
        self.ecrire_branche()
        self.assertEqual(self.preuve(), "ciblee")
        self.ecrire_preuves()
        self.ecrire_mac()
        self.assertEqual(self.preuve(), "conteneur")
        self.ecrire_complete()
        self.assertEqual(self.preuve(), "complete")

    def test_l_empreinte_ciblee_par_commit_n_est_jamais_lue(self):
        (self.depot / ".git" / "pmzilla-run-targeted-ok").write_text(self.arbre + "\n")
        self.assertIsNone(self.preuve())

    def test_arbre_mal_forme_est_un_calcul_impossible(self):
        for arbre in ("", "abc", "G" * 40, None):
            with self.subTest(arbre=arbre), self.assertRaises(preuve_arbre.PreuveImpossible):
                preuve_arbre.preuve(arbre, worktree=self.depot, preuves=self.preuves, mac=self.mac)

    def test_git_en_echec_pour_le_fichier_mac_est_un_calcul_impossible(self):
        self.ecrire_preuves()
        with self.assertRaises(preuve_arbre.PreuveImpossible):
            preuve_arbre.preuve(self.arbre, worktree=self.base / "absent", preuves=self.preuves)

    def test_fichier_de_preuves_absent_n_est_pas_une_preuve(self):
        self.ecrire_mac()
        self.assertIsNone(self.preuve())


class LigneDeCommande(AvecDepot):
    def test_conteneur_code_0(self):
        self.ecrire_preuves()
        self.ecrire_mac()
        r = self.cli(self.arbre, "--worktree", str(self.depot))
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "conteneur"), r.stderr)

    def test_complete_code_0(self):
        self.ecrire_complete()
        r = self.cli(self.arbre, "--worktree", str(self.depot))
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "complete"), r.stderr)

    def test_ciblee_est_dite_ciblee_code_0(self):
        # le crochet pre-push n'accepte que complete et conteneur : le mot est le contrat
        self.ecrire_branche()
        r = self.cli(self.arbre, "--worktree", str(self.depot))
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "ciblee"), r.stderr)

    def test_aucune_preuve_code_1(self):
        r = self.cli(self.arbre, "--worktree", str(self.depot))
        self.assertEqual((r.returncode, r.stdout.strip()), (1, "aucune"), r.stderr)

    def test_arbre_mal_forme_code_2(self):
        r = self.cli("pas-un-arbre", "--worktree", str(self.depot))
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertEqual(r.stdout, "")

    def test_usage_code_2(self):
        for arguments in ((), (self.arbre, "--worktree"), (self.arbre, "autre")):
            with self.subTest(arguments=arguments):
                r = self.cli(*arguments)
                self.assertEqual(r.returncode, 2, r.stdout)
                self.assertEqual(r.stdout, "")

    def test_conteneur_sans_worktree_utilise_le_dossier_courant(self):
        self.ecrire_preuves()
        self.ecrire_mac()
        r = self.cli(self.arbre)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "conteneur"), r.stderr)

    def test_le_dossier_de_donnees_vient_de_pmzilla_lab_data(self):
        self.ecrire_preuves()
        self.ecrire_mac()
        autre = self.base / "autre"
        autre.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith("PMZILLA_LAB_")}
        env["PMZILLA_LAB_DATA"] = str(autre)
        r = subprocess.run([sys.executable, "-I", str(OUTIL), self.arbre], cwd=self.depot, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual((r.returncode, r.stdout.strip()), (1, "aucune"), r.stderr)

    def test_le_module_n_ecrit_rien(self):
        self.ecrire_preuves()
        self.ecrire_mac()
        avant = sorted(str(p.relative_to(self.base)) for p in self.base.rglob("*") if ".git/objects" not in str(p) and ".git/index" not in str(p))
        self.cli(self.arbre, "--worktree", str(self.depot))
        apres = sorted(str(p.relative_to(self.base)) for p in self.base.rglob("*") if ".git/objects" not in str(p) and ".git/index" not in str(p))
        self.assertEqual(avant, apres)


class PreuveDIndex(AvecDepot):
    """tooling-proof-in-container, T2, D1 et R-20261104-7 P5 (i) et (ii) : la recherche d'un arbre dans le fichier des preuves d'index
    (ci/preuves-index du dossier de données, ou CI_LOCAL_PREUVES_INDEX) est UNE fonction de ce module, avec sa ligne de commande
    `--index <arbre> [--suites a,b]`. Ligne : <arbre><tab><clé d'image><tab><suites séparées par des virgules, ou « complet »>, sans champ de verdict.
    Remplace : rien (le runner de session lisait l'arbre sans preuve du conteneur). Retrait : permanent tant que le pre-commit exige un passage vert de l'index."""

    def setUp(self):
        super().setUp()
        self.index = self.donnees / "ci" / "preuves-index"

    def ecrire_index(self, suites, arbre=None):
        with self.index.open("a") as f:
            f.write(f"{arbre or self.arbre}\tcle\t{suites}\n")

    def trouvee(self, *suites, arbre=None):
        return preuve_arbre.index_proven(arbre or self.arbre, suites, self.index)

    def test_fichier_absent_n_est_pas_une_preuve(self):
        self.assertFalse(self.trouvee("alpha"))

    def test_une_ligne_dont_les_suites_couvrent_la_demande(self):
        self.ecrire_index("alpha,beta")
        self.assertTrue(self.trouvee("alpha"))
        self.assertTrue(self.trouvee("beta", "alpha"))
        self.assertFalse(self.trouvee("alpha", "gamma"), "une suite non couverte n'est pas prouvée")

    def test_la_ligne_complet_couvre_toute_demande(self):
        self.ecrire_index("complet")
        self.assertTrue(self.trouvee("alpha", "gamma"))
        self.assertTrue(self.trouvee())

    def test_une_liste_qui_nomme_complet_ne_prouve_pas_le_mode_complet(self):
        self.ecrire_index("alpha,complet")
        self.assertFalse(self.trouvee("complet"))
        self.assertTrue(self.trouvee("alpha"))

    def test_une_demande_sans_suite_exige_au_moins_une_ligne_de_l_arbre(self):
        self.assertFalse(self.trouvee())
        self.ecrire_index("alpha")
        self.assertTrue(self.trouvee())

    def test_l_arbre_doit_etre_le_meme(self):
        self.ecrire_index("complet", arbre="1" * 40)
        self.assertFalse(self.trouvee("alpha"))

    def test_plusieurs_lignes_pour_un_arbre_une_suffit(self):
        self.ecrire_index("alpha")
        self.ecrire_index("beta")
        self.assertTrue(self.trouvee("beta"))
        self.assertFalse(self.trouvee("alpha", "beta"), "les lignes ne s'additionnent pas : une seule doit couvrir toute la demande")

    def test_ligne_mal_formee_ignoree(self):
        self.index.write_text(f"{self.arbre}\tcle\n{self.arbre}\tcle\talpha\textra\nnimporte\tcle\tcomplet\n")
        self.assertFalse(self.trouvee("alpha"))

    def test_ligne_de_commande_trouvee_code_0_et_mot(self):
        self.ecrire_index("alpha,beta")
        r = self.cli("--index", self.arbre, "--suites", "alpha,beta")
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "conteneur-index"), r.stderr)

    def test_ligne_de_commande_absente_code_1(self):
        r = self.cli("--index", self.arbre, "--suites", "alpha")
        self.assertEqual((r.returncode, r.stdout.strip()), (1, "aucune"), r.stderr)

    def test_ligne_de_commande_sans_suites_demande_une_ligne(self):
        self.ecrire_index("alpha")
        r = self.cli("--index", self.arbre)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "conteneur-index"), r.stderr)

    def test_variable_d_essai_nomme_le_fichier(self):
        autre = self.base / "autre-index"
        autre.write_text(f"{self.arbre}\tcle\tcomplet\n")
        env = {k: v for k, v in os.environ.items() if not k.startswith("PMZILLA_LAB_")}
        env["PMZILLA_LAB_DATA"] = str(self.donnees)
        env["CI_LOCAL_PREUVES_INDEX"] = str(autre)
        r = subprocess.run([sys.executable, "-I", str(OUTIL), "--index", self.arbre, "--suites", "alpha"], cwd=self.depot, env=env,
                           capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "conteneur-index"), r.stderr)

    def test_usage_code_2(self):
        for arguments in (("--index",), ("--index", "pas-un-arbre"), ("--index", self.arbre, "--suites"), ("--index", self.arbre, "x"),
                          ("--suites", "a,b")):
            r = self.cli(*arguments)
            self.assertEqual(r.returncode, 2, (arguments, r.stdout))
            self.assertEqual(r.stdout, "")

    def test_suite_hors_motif_refusee(self):
        r = self.cli("--index", self.arbre, "--suites", "a;b")
        self.assertEqual(r.returncode, 2, r.stdout)

    def test_la_forme_sans_option_ne_lit_pas_le_fichier_d_index(self):
        self.ecrire_index("complet")
        r = self.cli(self.arbre)
        self.assertEqual((r.returncode, r.stdout.strip()), (1, "aucune"), "preuve() ne compte pas la preuve d'index : elle n'est pas une preuve de commit")


if __name__ == "__main__":
    unittest.main()
