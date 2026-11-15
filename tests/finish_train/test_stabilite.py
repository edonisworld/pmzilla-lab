"""
finish-single-b3-b6, B3 (conception D4 à D7, tâche 2.1) : la stabilité d'un worktree après le runner est jugée par UN module, tools/finish_stability.sh,
que le train (tools/finish_train.sh) source seul : la fin unitaire (tools/finish_worktree.sh, enveloppe du train depuis B78) est retirée par
finish-single-b7-b9 (B9, tâche 1.1).

Trois étages :
  - le module lui-même, dans un vrai bash, un vrai dépôt Git, un vrai lsof et de vrais enfants (rien n'est imprimé, aucun exit, échec d'outil = modifié) ;
  - le train, de bout en bout, avec un vrai enfant laissé dans le worktree d'intégration (code 71, nom nettoyé) ;
  - des tests statiques (seul le module appelle lsof et juge la date de changement des dossiers) et une PARITÉ réduite à son côté train : la table
    TABLE_PARITE ci-dessous donne, pour chaque scénario, le verdict attendu ; le module et le train (ici) doivent la suivre (le côté de la fin unitaire,
    joué par la suite shell retirée, est retiré avec elle).

Faux déclarés (règle R-20261028-26) : un faux lsof qui échoue ou qui ne nomme pas l'appelant (un vrai lsof ne se laisse pas faire échouer) ; un faux ps qui
rend un nom de commande à caractères interdits (un vrai processus ne se laisse pas nommer ainsi de façon fiable). Risque non couvert par ces deux faux :
la forme exacte de la sortie du vrai lsof ou du vrai ps sur une autre version de macOS (les autres tests de ce fichier, avec le vrai lsof et le vrai ps, la couvrent).
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_train import AvecTrain, BASH, OUTILS, RACINE, conserve  # noqa: E402

MODULE = OUTILS / "finish_stability.sh"
TRAIN = OUTILS / "finish_train.sh"

# scénario -> verdict attendu du module et du train (code 0 ou 71)
TABLE_PARITE = {
    "rien": "stable",                          # le runner ne touche rien
    "ignores": "stable",                       # des fichiers que Git ignore, créés dans un dossier suivi
    "ignores_et_passager": "stable",           # LIMITE CONNUE (D4) : le passager non ignoré est caché par l'ajout ignoré du même dossier
    "ignores_puis_retires": "modifie",         # créés puis retirés : liste identique, date changée (conséquence acceptée)
    "passager_non_ignore": "modifie",          # créé puis supprimé, non ignoré
    "non_suivi": "modifie",                    # un fichier non suivi laissé
}
# le mode du faux runner du train qui joue chaque scénario (tests/finish_train/aide_train.py, FAUX_RUNNER)
MODE_TRAIN = {"rien": "vert", "ignores": "ignores_crees", "ignores_et_passager": "limite_passager", "ignores_puis_retires": "ignores_supprimes",
              "passager_non_ignore": "passager_non_ignore", "non_suivi": "modifie_non_suivi"}


def code_sans_commentaires(chemin: Path) -> str:
    return "\n".join(l for l in chemin.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#"))


def env_propre(extra=None) -> dict:
    env = {**conserve(), "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"}
    env.update(extra or {})
    return env


class Depot:
    """Un vrai dépôt Git jetable avec un dossier suivi et un .gitignore (caches Python)."""

    def __init__(self, dossier: Path):
        self.racine = dossier / "depot"
        self.racine.mkdir()
        (self.racine / "dossier").mkdir()
        (self.racine / "f.txt").write_text("base\n", encoding="utf-8")
        (self.racine / "dossier" / "a.txt").write_text("a\n", encoding="utf-8")
        (self.racine / ".gitignore").write_text("__pycache__/\n*.pyc\n", encoding="utf-8")
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("-c", "user.email=t@example.org", "-c", "user.name=t", "commit", "-q", "-m", "initial")

    def git(self, *args):
        fait = subprocess.run(["git", *args], cwd=self.racine, env=env_propre(), capture_output=True, text=True)
        assert fait.returncode == 0, fait.stderr
        return fait.stdout

    def muter(self, scenario: str):
        r = self.racine
        if scenario == "rien":
            return
        if scenario == "ignores":
            (r / "__pycache__").mkdir()
            (r / "__pycache__" / "m.pyc").write_text("x", encoding="utf-8")
        elif scenario == "ignores_et_passager":
            (r / "passager.txt").write_text("x", encoding="utf-8")
            (r / "__pycache__").mkdir()
            (r / "__pycache__" / "m.pyc").write_text("x", encoding="utf-8")
            (r / "passager.txt").unlink()
        elif scenario == "ignores_puis_retires":
            (r / "__pycache__").mkdir()
            (r / "__pycache__" / "m.pyc").write_text("x", encoding="utf-8")
            shutil.rmtree(r / "__pycache__")
        elif scenario == "passager_non_ignore":
            (r / "passager.txt").write_text("x", encoding="utf-8")
            (r / "passager.txt").unlink()
        elif scenario == "non_suivi":
            (r / "nouveau.txt").write_text("x", encoding="utf-8")
        else:
            raise AssertionError(scenario)


def sonde(corps: str, cwd=None, extra=None):
    """Source le module dans un bash du système puis joue `corps`. Rend le processus terminé (sortie et erreur séparées)."""
    return subprocess.run([BASH, "-c", f'. "{MODULE}"\n{corps}'], cwd=cwd or RACINE, env=env_propre(extra), capture_output=True, text=True, timeout=120)


class Etage1Module(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dossier = Path(self.temp.name).resolve()
        self.depot = Depot(self.dossier)

    def verdict(self, scenario: str) -> int:
        """0 stable, 1 modifié : repère, marge d'une seconde, relevé, mutation, verdict (l'ordre exact des deux appelants)."""
        repere = self.dossier / "repere"
        releve = self.dossier / "releve"
        repere.write_text("", encoding="utf-8")
        time.sleep(1.1)
        r = sonde(f'fs_snapshot "{self.depot.racine}"; printf %s "$FS_SNAP" > "{releve}"')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.depot.muter(scenario)
        r = sonde(f'fs_verdict "{self.depot.racine}" "{repere}" "$(cat "{releve}")"; echo $?')
        self.assertEqual(r.stderr, "", "le module n'imprime rien sur l'erreur")
        self.assertRegex(r.stdout, r"^[01]\n$", "le module n'imprime rien d'autre que le code du test")
        return int(r.stdout.strip())

    def test_chaque_scenario_de_la_table_de_parite(self):
        for scenario, attendu in TABLE_PARITE.items():
            with self.subTest(scenario=scenario):
                self.setUp()
                self.assertEqual("stable" if self.verdict(scenario) == 0 else "modifie", attendu)

    def test_le_module_n_imprime_rien_et_ne_sort_pas_du_shell(self):
        r = sonde(f'cd /; avant=$(pwd); opts=$-\n'
                  f'fs_snapshot "{self.depot.racine}"\n'
                  f'fs_verdict "{self.depot.racine}" "{self.dossier}/absent" "$FS_SNAP"\n'
                  f'fs_processes "{self.depot.racine}"\n'
                  f'[ "$(pwd)" = "$avant" ] && [ "$opts" = "$-" ] && echo FIN')
        self.assertEqual(r.stdout, "FIN\n", "ni sortie parasite, ni exit, ni changement de dossier ou d'options")
        self.assertEqual(r.stderr, "")

    def test_fail_closed_sur_un_depot_illisible(self):
        autre = self.dossier / "pas-un-depot"
        autre.mkdir()
        r = sonde(f'fs_snapshot "{autre}"; echo "rc=$? snap=$FS_SNAP"\n'
                  f'fs_verdict "{autre}" "{self.dossier}/repere" "$FS_SNAP"; echo "v=$?"\n'
                  f'fs_verdict "{self.depot.racine}" "{self.dossier}/repere" erreur; echo "e=$?"')
        self.assertEqual(r.stdout.split(), ["rc=1", "snap=erreur", "v=1", "e=1"], r.stdout + r.stderr)

    def test_un_enfant_reel_dans_le_worktree_est_trouve_avec_son_nom_nettoye(self):
        enfant = subprocess.Popen(["sleep", "600"], cwd=self.depot.racine, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(enfant.kill)
        r = sonde(f'fs_processes "{self.depot.racine}"; echo "rc=$?"; echo "p=$FS_PROCESSES"')
        self.assertEqual(r.stdout.splitlines(), ["rc=1", f"p={enfant.pid} sleep"], r.stdout + r.stderr)

    def test_un_enfant_dans_un_sous_dossier_est_trouve_et_un_dossier_voisin_ne_l_est_pas(self):
        voisin = self.dossier / "depot-voisin"
        voisin.mkdir()
        proche = subprocess.Popen(["sleep", "600"], cwd=self.depot.racine / "dossier", stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        loin = subprocess.Popen(["sleep", "600"], cwd=voisin, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(proche.kill)
        self.addCleanup(loin.kill)
        r = sonde(f'fs_processes "{self.depot.racine}"; echo "rc=$?"; echo "p=$FS_PROCESSES"')
        self.assertEqual(r.stdout.splitlines(), ["rc=1", f"p={proche.pid} sleep"], r.stdout + r.stderr)

    def test_aucun_autre_processus_rend_0(self):
        r = sonde(f'fs_processes "{self.depot.racine}"; echo "rc=$?"; echo "p=$FS_PROCESSES"')
        self.assertEqual(r.stdout.splitlines(), ["rc=0", "p="], r.stdout + r.stderr)

    def test_un_worktree_sale_au_releve_donne_erreur_et_un_verdict_modifie(self):
        # finish-single-b3-b6 D4 : la propreté juste avant le runner est dans le module (une seule règle pour les deux fins)
        (self.depot.racine / "sale.txt").write_text("x", encoding="utf-8")
        r = sonde(f'fs_snapshot "{self.depot.racine}"; echo "rc=$? snap=$FS_SNAP"; fs_verdict "{self.depot.racine}" "{self.dossier}/repere" "$FS_SNAP"; echo "v=$?"')
        self.assertEqual(r.stdout.split(), ["rc=1", "snap=erreur", "v=1"], r.stdout + r.stderr)

    def test_le_module_tourne_sous_set_u_sans_variable_non_liee(self):
        r = sonde(f'set -u\nfs_snapshot "{self.depot.racine}" || echo KO1\nfs_verdict "{self.depot.racine}" "{self.dossier}/absent" "$FS_SNAP"; echo "v=$?"\n'
                  f'fs_processes "{self.depot.racine}"; echo "p=$?"')
        self.assertEqual(r.stderr, "", "aucune variable non liée sous set -u")
        self.assertNotIn("KO1", r.stdout)
        self.assertRegex(r.stdout, r"v=[01]\np=[012]\n")

    def test_lsof_absent_du_path_est_une_verification_impossible(self):
        vide = self.dossier / "path-vide"
        vide.mkdir()
        r = sonde(f'fs_processes "{self.depot.racine}"; echo "rc=$? p=$FS_PROCESSES"', extra={"PATH": str(vide)})
        self.assertEqual(r.stdout.strip(), "rc=2 p=", r.stdout + r.stderr)

    def faux_dossier(self, nom: str, texte: str) -> str:
        d = self.dossier / nom
        d.mkdir(exist_ok=True)
        (d / nom.split("-")[1]).write_text(texte, encoding="utf-8")
        (d / nom.split("-")[1]).chmod(0o755)
        return f"{d}:{os.environ.get('PATH', '')}"

    def test_verification_impossible_quand_lsof_echoue_ou_ne_nomme_pas_l_appelant(self):
        # faux lsof déclaré : un vrai lsof ne se laisse pas faire échouer
        for nom, texte in (("faux-lsof-1", "#!/bin/sh\nexit 1\n"), ("faux-lsof-2", "#!/bin/sh\nprintf 'p1\\nn/\\n'\n")):
            with self.subTest(faux=nom):
                chemin = self.faux_dossier(nom, texte)
                r = sonde(f'fs_processes "{self.depot.racine}"; echo "rc=$? p=$FS_PROCESSES"', extra={"PATH": chemin})
                self.assertEqual(r.stdout.strip(), "rc=2 p=", r.stdout + r.stderr)
                shutil.rmtree(self.dossier / nom)

    def test_nom_a_caracteres_interdits_nettoye_et_nom_vide_remplace(self):
        # faux ps déclaré : seul « -o pid=,comm= -p N » est truqué, tout autre appel passe au vrai ps
        enfant = subprocess.Popen(["sleep", "600"], cwd=self.depot.racine, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(enfant.kill)
        for comm, attendu in (("/opt/zsh;rm -rf $(id)<z>|", "zshrm -rf idz"), ("/opt/", "?"), ("/x/a b/long nom.sh", "long nom.sh")):
            with self.subTest(comm=comm):
                chemin = self.faux_dossier("faux-ps", f"#!/bin/sh\nif [ \"$1 $2\" = '-o pid=,comm=' ]; then printf '%6s %s\\n' \"$4\" '{comm}'; else exec /bin/ps \"$@\"; fi\n")
                r = sonde(f'fs_processes "{self.depot.racine}"; echo "rc=$?"; echo "p=$FS_PROCESSES"', extra={"PATH": chemin})
                self.assertEqual(r.stdout.splitlines(), ["rc=1", f"p={enfant.pid} {attendu}"], r.stdout + r.stderr)
                shutil.rmtree(self.dossier / "faux-ps")


class Etage2Train(AvecTrain):
    def test_un_enfant_reel_laisse_dans_le_worktree_d_integration_donne_71_avec_le_nom_nettoye(self):
        self.t.branche("feat/x", worktree=False)
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_PROCESSUS_ICI": "1"}, entree="o\n")
        m = re.search(r"runner non concluant \(code 0\) : processus dans le worktree d'intégration \((\d+) sleep\) ; rien n'est fusionné", r.texte)
        self.assertIsNotNone(m, r.texte)
        self.assertEqual(r.code, 71, r.texte)
        self.assertEqual(m.group(1), (self.t.etat / "pid-sleep").read_text(encoding="utf-8").strip())

    def test_un_nom_a_caracteres_interdits_est_affiche_nettoye_au_train(self):
        # faux ps déclaré (voir l'en-tête) ; le train, l'admission et le nettoyage lisent le même module
        faux = Path(self.temp.name) / "faux-ps"
        faux.mkdir()
        (faux / "ps").write_text("#!/bin/sh\nif [ \"$1 $2\" = '-o pid=,comm=' ]; then printf '%6s %s\\n' \"$4\" '/opt/zsh;rm -rf $(id)<z>|'; else exec /bin/ps \"$@\"; fi\n", encoding="utf-8")
        (faux / "ps").chmod(0o755)
        chemin = f"{faux}:{self.t.bin}:{self.t.bin_lsof}:{os.environ.get('PATH', '')}"
        self.t.branche("feat/x", worktree=False)
        r = self.t.lance("feat/x", extra={"PATH": chemin, "FAKE_RUNNER_PROCESSUS_ICI": "1"}, entree="o\n")
        pid = (self.t.etat / "pid-sleep").read_text(encoding="utf-8").strip()
        self.assertEqual(r.code, 71, r.texte)
        self.assertIn(f"processus dans le worktree d'intégration ({pid} zshrm -rf idz)", r.texte)
        self.assertNotIn("zsh;rm", r.texte)
        self.assertNotIn("$(id)", r.texte)

    def test_un_worktree_sale_juste_avant_le_releve_donne_71(self):
        # finish-single-b3-b6 D4 : un fichier non suivi laissé AVANT le relevé rend le relevé « erreur », donc « modifié ». Le relevé précède maintenant le
        # passage du conteneur : le faux git laisse le fichier juste après la création du worktree d'intégration (FAKE_WORKTREE_ADD_SALE, revue Opus)
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", extra={"FAKE_WORKTREE_ADD_SALE": "1"}, entree="o\n")
        self.code(r, 71, "runner non concluant (code 0) : worktree d'intégration modifié pendant le runner ; rien n'est fusionné")
        self.assertEqual(len(self.t.ci_appels()), 1, "le passage du conteneur était vert : seul le relevé initial en erreur rend le train non concluant")

    def test_un_worktree_sale_par_le_passage_du_conteneur_donne_71(self):
        # le cas d'après le relevé (le faux ci_local salit le dossier pendant le passage) : détecté à la fin
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", extra={"FAUX_CI_SALE": "1"}, entree="o\n")
        self.code(r, 71, "runner non concluant (code 0) : worktree d'intégration modifié pendant le runner ; rien n'est fusionné")

    def test_une_passe_mac_sans_sa_ligne_donne_71_meme_si_le_conteneur_a_ecrit_sa_preuve(self):
        # neuf (D9, Q219, recommandation du plan appliquée par défaut) : la condition « empreinte réécrite » vaut pour la ligne de la passe Mac ;
        # la preuve du conteneur seule ne suffit pas
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_MODE": "sans_empreinte"}, entree="o\n")
        self.assertEqual(r.code, 71, r.texte)
        self.assertEqual(self.t.ci_appels(), [""])

    def test_une_preuve_du_conteneur_aux_phases_inexactes_donne_71(self):
        # revue croisée tranche 2 (D6) : la ligne de ci/preuves de l'arbre du train, réécrite après le repère, doit porter EXACTEMENT « portable,base,e2e » ;
        # un autre ordre ou une phase en plus donne 71 (FAUX_CI_PREUVE_PHASES : le faux ci_local écrit cette liste à la place)
        for phases in ("e2e,portable,base", "portable,base,e2e,autre"):
            with self.subTest(phases=phases):
                self.setUp()
                self.t.branche("feat/x")
                r = self.t.lance("feat/x", extra={"FAUX_CI_PREUVE_PHASES": phases}, entree="o\n")
                self.code(r, 71, "runner non concluant (code 0) : preuve du conteneur absente, différente de l'arbre du train, "
                                 "sans exactement portable,base,e2e ou non réécrite ; rien n'est fusionné")

    def test_chaque_scenario_de_la_table_de_parite_donne_le_code_attendu(self):
        for scenario, attendu in TABLE_PARITE.items():
            with self.subTest(scenario=scenario):
                self.setUp()
                self.t.branche("feat/x", {"mothra/package.json": "{}\n", "mothra/front/package.json": "{}\n"})
                r = self.t.lance("feat/x", extra={"FAKE_RUNNER_MODE": MODE_TRAIN[scenario]}, entree="n\n")
                self.assertEqual(r.code, 0 if attendu == "stable" else 71, f"{scenario}\n{r.texte}")


class Etage3Statique(unittest.TestCase):
    NOMS_RETIRES = ("tracked_dirs", "dirs_verdict", "ls_dir", "ls_norm", "dir_snapshot", "procs_in", "lsof_refresh", "stability_dirs",
                    "dossiers_suivis", "listage_processus", "nommer_processus")

    def test_le_module_existe_sans_exit_ni_impression(self):
        self.assertTrue(MODULE.exists(), "tools/finish_stability.sh est à écrire (D4)")
        code = code_sans_commentaires(MODULE)
        self.assertIsNone(re.search(r"\bexit\b", code), "le module n'a aucun exit")
        for fonction in ("fs_snapshot", "fs_verdict", "fs_processes"):
            self.assertRegex(code, rf"(?m)^{fonction}\(\) \{{")

    def test_seul_le_module_appelle_lsof(self):
        self.assertIsNotNone(re.search(r"(^|[^_a-z])lsof\s+-", code_sans_commentaires(MODULE)), "le module appelle lsof")
        for fichier in sorted(OUTILS.glob("finish_*.sh")):
            if fichier == MODULE:
                continue
            self.assertIsNone(re.search(r"(^|[^_a-z])lsof\s+-", code_sans_commentaires(fichier)), f"{fichier.name} appelle lsof")

    def test_seul_le_module_juge_la_date_de_changement_des_dossiers(self):
        # -cnewer reste dans les appelants pour l'empreinte du runner seulement (la fraîcheur de l'empreinte, D4 : elle reste dans chaque appelant)
        for fichier in (TRAIN,):
            for ligne in code_sans_commentaires(fichier).splitlines():
                if "-cnewer" in ligne:
                    self.assertTrue("$fp" in ligne or "EMPREINTE_WT" in ligne, f"{fichier.name} : -cnewer hors de l'empreinte : {ligne.strip()}")
        self.assertIn("-cnewer", code_sans_commentaires(MODULE))

    def test_le_train_source_le_module_et_n_a_plus_de_copie(self):
        code = code_sans_commentaires(TRAIN)
        self.assertIn("finish_stability.sh", code, "le train ne source pas le module")
        for nom in self.NOMS_RETIRES:
            self.assertIsNone(re.search(rf"(?m)^\s*{nom}\(\)", code), f"le train définit encore {nom}")

    def test_le_train_ne_source_ni_ne_lance_le_chemin_allege(self):
        # finish-single-b7-b9, B9 (D8, tâche 1.1) : voie allégée retirée ; nouveau test (plus strict) : le train ne nomme ni tools/light_finish.sh ni
        # tools/light_validate.py ; l'écriture de pmzilla-main-validated par le train vient de tools/finish_env.sh, qu'il source
        code = code_sans_commentaires(TRAIN)
        self.assertNotIn("light_finish.sh", code)
        self.assertNotIn("light_validate.py", code)
        self.assertIn("finish_env.sh", code, "le train source le module qui porte record_main_validated")
        self.assertFalse((OUTILS / "light_finish.sh").exists())
        self.assertFalse((OUTILS / "light_validate.py").exists())

    def test_le_train_compare_le_node_par_le_module(self):
        # D16 : le code 80 du train n'a pas sa propre comparaison de versions ; il appelle « finish_checks.py node-match »
        # (rétabli par B9 depuis tests/finish_checks/test_delegation.py, ScriptSansControle, revue 4.7 ; assertions inchangées)
        train = code_sans_commentaires(TRAIN)
        self.assertIn("finish_checks.py", train)
        self.assertRegex(train, r"finish_checks\.py\"? node-match ")
        self.assertNotIn('"${found#"$want".}"', train)


if __name__ == "__main__":
    unittest.main()
