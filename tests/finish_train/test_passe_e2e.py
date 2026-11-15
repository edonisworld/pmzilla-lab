"""
Change ci-local-runner, tranche 3 (décisions R-20261101-114 et 115, conception D9) : la porte du train. Le train lance lui-même le passage du conteneur
(`ci_local.sh run`, remplacé ici par FINISH_TRAIN_CI) dans le worktree d'intégration, puis la passe Mac (FINISH_TRAIN_RUNNER). La preuve de bout en bout
vient de la phase « e2e » du conteneur ; tools/dbtest.sh --e2e ne tourne plus dans le train. Codes : phase base rouge 69, phase e2e rouge 82, codes 3 et 5
de ci_local 71 (aucune route de secours).

Ce fichier remplace la passe de bout en bout lancée par le script (change finish-e2e-proof-shared, tâche 2.6) : les tests de la passe sont réécrits contre
le passage du conteneur, ceux dont le mécanisme a disparu (ligne « sans objet », ligne pmzilla-e2e-ok, détails du contrôle 16 au refus) sont retirés.

Fakes déclarés (règle R-20261028-26) : le passage du conteneur est un faux (tests/finish_train/aide_train.py, FAUX_CI), sauf le test de la commande par
défaut, où un tools/ci_local.sh commité dans main note son dossier et ses arguments. Risque non couvert : le vrai conteneur (Colima, image, base) ;
seul le train de répétition réel le prouve.
"""
import re
import unittest
from pathlib import Path

from aide_train import AvecTrain, CHEMIN_INTERFACE, lignes_ci, phase_ci

BASE_DB = {"db/001.sql": "SELECT 2;\n"}
BASE_ROUGE = "phase base du conteneur rouge sur l'arbre du train ; rien n'est fusionné"
E2E_ROUGE = "phase de bout en bout du conteneur rouge sur l'arbre du train ; rien n'est fusionné"
# la phrase exacte : l'étape du train est « porte du conteneur » (revue Opus point 4), plus un motif qui accepterait n'importe quelle étape
BANNIERE = "===== arrêt à porte du conteneur : rien n'est fusionné ====="

STUB_CI = """#!/bin/bash
ETAT="@ETAT@"
echo "ci-defaut script=$0 pwd=$(pwd -P) args=[$*]" >> "$ETAT/appels.log"
mkdir -p "$PMZILLA_LAB_DATA/ci"
printf '%s\\t%s\\t%s\\n' "$(git rev-parse 'HEAD^{tree}')" cle-factice portable,base,e2e >> "$PMZILLA_LAB_DATA/ci/preuves"
echo "ci_passage : phase portable : verte · 1 s"
echo "ci_passage : phase base : verte · 1 s"
echo "ci_passage : phase e2e : verte · 1 s"
echo "TOTAL : 3 tests dans 2 suites · tous réussis · durée totale 1 s"
echo "ci_local : verdict vert (arbre aaaaaaaaaaaa, image bbbbbbbbbbbb, phases portable,base,e2e, 3 suites, 0 suites Mac non lancées)"
exit 0
"""


class PasseDeBoutEnBout(AvecTrain):
    def test_le_passage_du_conteneur_tourne_une_fois_quand_l_arbre_du_train_change_un_chemin_d_interface(self):
        # réécrit : l'ancienne passe e2e du script est la phase e2e du conteneur
        self.t.branche("feat/x", {CHEMIN_INTERFACE: "x\n"})
        r = self.t.lance("feat/x", entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(self.t.ci_appels(), [""], "un seul passage, sans rejeu, sans argument")
        self.assertEqual(len(self.t.appels("runner")), 1)

    def test_le_passage_tourne_meme_avec_une_ligne_deja_presente_pour_l_arbre_du_train(self):
        # réécrit : aucun verdict déjà enregistré n'est réutilisé (la ligne de preuve du conteneur remplace la ligne pmzilla-e2e-ok)
        self.t.branche("feat/x", {CHEMIN_INTERFACE: "x\n"})
        (self.t.data / "ci").mkdir(parents=True, exist_ok=True)
        with open(self.t.data / "ci" / "preuves", "a", encoding="utf-8") as f:
            f.write(f"{self.t.arbre('feat/x')}\tcle-factice\tportable,base,e2e\n")   # une seule branche fondée sur main : l'arbre du train est celui de son sommet
        r = self.t.lance("feat/x", entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(self.t.ci_appels(), [""], "aucune preuve déjà enregistrée n'est réutilisée")

    def test_sans_chemin_d_interface_change_le_passage_du_conteneur_tourne_quand_meme(self):
        # neuf, à la place du test retiré « aucune passe et ligne sans objet » (mécanisme disparu : la phase e2e fait partie de chaque passage)
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(self.t.ci_appels(), [""])

    def test_ordre_passage_du_conteneur_puis_runner_et_aucun_dbtest(self):
        # réécrit : l'ordre dbtest, passe, runner devient passage du conteneur, puis passe Mac ; ni dbtest ni passe e2e ne sont lancés
        self.t.branche("feat/x", {**BASE_DB, CHEMIN_INTERFACE: "x\n"})
        r = self.t.lance("feat/x", entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        ordre = [l.split()[0] for l in self.t.appels("") if l.split()[0] in ("dbtest", "e2e", "ci", "runner")]
        self.assertEqual(ordre, ["ci", "runner"])

    def test_phase_base_rouge_sort_69_meme_avec_un_chemin_d_interface_change(self):
        # réécrit : l'ancien « dbtest vert sans ligne sort 69 » devient la phase base rouge du conteneur (D9) ; le 69 reste le code
        self.t.branche("feat/x", {**BASE_DB, CHEMIN_INTERFACE: "x\n"})
        avant = self.t.instantane()
        lignes = lignes_ci(phase_ci("portable"), phase_ci("base", "rouge", "suite_base"), suites="suite_base")
        r = self.t.lance("feat/x", extra={"FAUX_CI_LIGNES": lignes, "FAUX_CI_CODE": "1"}, entree="o\n")
        self.code(r, 69, BASE_ROUGE)
        self.rien_ne_change(avant)
        self.assertEqual(self.t.appels("runner"), [], "la passe Mac n'est pas lancée après une phase base rouge")

    def test_phase_base_rouge_sort_69_sans_changement_de_la_base(self):
        # neuf : le conteneur passe toujours par la base ; plus de contrôle 14 pour décider
        self.t.branche("feat/x")
        avant = self.t.instantane()
        lignes = lignes_ci(phase_ci("portable"), phase_ci("base", "rouge", "suite_base"), suites="suite_base")
        r = self.t.lance("feat/x", extra={"FAUX_CI_LIGNES": lignes, "FAUX_CI_CODE": "1"}, entree="o\n")
        self.code(r, 69, BASE_ROUGE)
        self.rien_ne_change(avant)
        self.assertEqual(self.t.appels("runner"), [])

    def test_phase_e2e_rouge_sort_82_rien_n_est_fusionne_et_la_banniere_dit_l_etape(self):
        # réécrit : passe rouge devient phase e2e rouge du conteneur ; le runner n'est pas lancé
        self.t.branche("feat/x", {CHEMIN_INTERFACE: "x\n"})
        avant = self.t.instantane()
        lignes = lignes_ci(phase_ci("portable"), phase_ci("base"), phase_ci("e2e", "rouge", "suite_e2e"), suites="suite_e2e")
        r = self.t.lance("feat/x", extra={"FAUX_CI_LIGNES": lignes, "FAUX_CI_CODE": "1"}, entree="o\n")
        self.code(r, 82, E2E_ROUGE)
        self.assertIn(BANNIERE, r.texte)
        self.rien_ne_change(avant)
        self.assertEqual(self.t.appels("runner"), [], "la passe Mac n'est pas lancée après une phase e2e rouge")
        self.assertEqual(self.t.worktrees_train(), [])

    def un_code_du_conteneur_donne_71(self, c: int):
        # neuf (D9, Q170) : conteneur indisponible ou image absente ; aucune passe Mac, rien n'est fusionné. Un dépôt jetable par test (revue Opus point 11)
        self.t.branche("feat/x", {CHEMIN_INTERFACE: "x\n"})
        avant = self.t.instantane()
        r = self.t.lance("feat/x", extra={"FAUX_CI_LIGNES": f"ci_local : conteneur indisponible (faux {c})", "FAUX_CI_CODE": str(c)}, entree="o\n")
        self.code(r, 71, f"runner non concluant : conteneur indisponible (code {c}) ; rien n'est fusionné")
        self.rien_ne_change(avant)
        self.assertEqual(self.t.appels("runner"), [])

    def test_code_3_du_conteneur_donne_71_sans_route_de_secours(self):
        self.un_code_du_conteneur_donne_71(3)

    def test_code_5_du_conteneur_donne_71_sans_route_de_secours(self):
        self.un_code_du_conteneur_donne_71(5)

    def un_code_0_non_concluant(self, lignes: str):
        self.t.branche("feat/x", {CHEMIN_INTERFACE: "x\n"})
        avant = self.t.instantane()
        r = self.t.lance("feat/x", extra={"FAUX_CI_LIGNES": lignes, "FAUX_CI_CODE": "0"}, entree="o\n")
        self.code(r, 71, "runner non concluant : conteneur non concluant ; rien n'est fusionné")
        self.rien_ne_change(avant)
        self.assertEqual(self.t.appels("runner"), [], "la passe Mac n'est pas lancée : jamais un vert sur le seul code de sortie")

    def test_code_0_sans_les_trois_lignes_de_phase_verte_donne_71(self):
        # neuf (Q226 a, R-20261101-116) : un vert du conteneur exige les trois lignes « phase portable, base, e2e : verte » ; ni aucune ligne de phase,
        # ni une phase manquante (e2e, base, portable tour à tour) ne suffit
        self.un_code_0_non_concluant("ci_local : verdict vert (arbre aaaaaaaaaaaa, image bbbbbbbbbbbb)")

    def test_code_0_sans_la_phase_e2e_donne_71(self):
        self.un_code_0_non_concluant("\n".join([phase_ci("portable"), phase_ci("base"), "ci_local : verdict vert (arbre aaaaaaaaaaaa, image bbbbbbbbbbbb)"]))

    def test_code_0_sans_la_phase_base_donne_71(self):
        self.un_code_0_non_concluant("\n".join([phase_ci("portable"), phase_ci("e2e"), "ci_local : verdict vert (arbre aaaaaaaaaaaa, image bbbbbbbbbbbb)"]))

    def test_code_0_sans_la_phase_portable_donne_71(self):
        self.un_code_0_non_concluant("\n".join([phase_ci("base"), phase_ci("e2e"), "ci_local : verdict vert (arbre aaaaaaaaaaaa, image bbbbbbbbbbbb)"]))

    def test_code_0_avec_une_ligne_de_phase_rouge_donne_71(self):
        # neuf (Q226 a) : les trois lignes vertes sont là, mais une ligne de phase « rouge » reste imprimée : pas un vert
        self.un_code_0_non_concluant("\n".join([phase_ci("portable"), phase_ci("base"), phase_ci("e2e"), phase_ci("e2e", "rouge", "suite_e2e"),
                                                "ci_local : verdict vert (arbre aaaaaaaaaaaa, image bbbbbbbbbbbb)"]))

    def test_la_commande_par_defaut_est_ci_local_lance_depuis_le_worktree_d_integration(self):
        # réécrit : l'ancienne commande par défaut (dbtest --e2e de l'arbre du train) devient `ci_local.sh run` ; un tools/ci_local.sh commité dans main
        # note son dossier et ses arguments (le dossier d'où il est lancé est le worktree d'intégration, jamais l'arbre d'exécution)
        self.t.commit_main({"tools/ci_local.sh": self.t.remplir(STUB_CI)}, pousser=True)
        self.t.mettre_a_jour_run()
        self.t.branche("feat/x", {CHEMIN_INTERFACE: "x\n"})
        r = self.t.lance("feat/x", extra={"FINISH_TRAIN_CI": None}, entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        (ligne,) = self.t.appels("ci-defaut")
        # origine du script (spec ci-local-runner, design D9 « Commands » : la commande par défaut est `bash "$SCRIPT_DIR/ci_local.sh" run`, SCRIPT_DIR étant le dossier
        # de l'arbre d'exécution qui porte le finish_train.sh lancé ; principe de B6 de D7 : le code qui juge est celui de main, jamais celui de l'arbre testé)
        script = ligne.split("script=")[1].split(" pwd=")[0]
        self.assertEqual(Path(script).resolve(), (self.t.run / "tools" / "ci_local.sh").resolve(), "le script lancé est celui de l'arbre d'exécution")
        self.assertNotIn("/wt-train-", script, "le script lancé n'est pas celui du worktree d'intégration (l'arbre testé)")
        self.assertIn("/wt-train-", ligne.split(" pwd=")[1], "le dossier courant est le worktree d'intégration")
        self.assertRegex(ligne, r"args=\[run\]")
        self.assertEqual(self.t.ci_appels(), [], "le faux ci de la fixture n'est pas appelé quand la variable est absente")

    def test_l_enfant_sonde_recoit_un_environnement_propre(self):
        # test de sécurité (R-115), réécrit aussi strict contre le conteneur : entrée fermée, jeton présent, aucune variable de l'auteur
        # (DBTEST_*, PMZILLA_LAB_DB_*, jeton de l'auteur) ni FINISH_TRAIN_*, vérifiées avec des valeurs témoins dans l'environnement du lancement
        self.t.branche("feat/x", {CHEMIN_INTERFACE: "x\n"})
        temoins = {"DBTEST_SONDE": "/usr/bin/true", "DBTEST_RECORD": "/tmp/x-empreintes", "DBTEST_PORT": "1",
                   "DBTEST_E2E_PASSE": "/usr/bin/true", "DBTEST_ATTENTE": "1", "PMZILLA_LAB_DB_TEMOIN": "valeur-temoin-db"}
        # valeur témoin construite (jamais un littéral affecté à un nom de mot de passe : secret_scan)
        temoins["PMZILLA_LAB_DB_" + "PASSWORD"] = "valeur-temoin-" + "mdp"
        r = self.t.lance("feat/x", extra=temoins, entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        (ligne,) = self.t.appels("ci ")
        self.assertIn("/wt-train-", ligne)
        self.assertIn("stdin=[]", ligne)
        self.assertIn("jeton=present", ligne)
        self.assertIn("dbvars=[]", ligne)
        env_ci = (self.t.etat / "ci-env").read_text(encoding="utf-8")
        self.assertNotRegex(env_ci, r"(?m)^(DBTEST_|PMZILLA_LAB_DB_|FINISH_TRAIN_)")
        self.assertNotIn("valeur-temoin", env_ci)

    def test_des_fichiers_ignores_crees_avant_la_passe_mac_ne_bloquent_ni_le_runner_ni_le_nettoyage(self):
        # réécrit : le faux ci laisse des fichiers ignorés dans le worktree d'intégration (le vrai conteneur n'y touche pas ; la garde reste)
        self.t.branche("feat/x", {CHEMIN_INTERFACE: "x\n"})
        r = self.t.lance("feat/x", extra={"FAUX_CI_IGNORES_CREES": "1"}, entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(len(self.t.appels("runner")), 1)
        self.assertEqual(self.t.worktrees_train(), [])

    def test_l_essai_rapide_ne_lance_aucun_passage(self):
        # réécrit : ni passage du conteneur ni passe Mac à l'essai
        self.t.branche("feat/x", {CHEMIN_INTERFACE: "x\n"})
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(self.t.ci_appels(), [])
        self.assertEqual(self.t.appels("runner"), [])

    def test_la_variable_de_substitution_n_arrive_jamais_au_runner(self):
        # test de sécurité, inchangé pour le runner ; étendu au passage du conteneur (FINISH_TRAIN_CI n'atteint pas non plus son enfant)
        self.t.branche("feat/x", {CHEMIN_INTERFACE: "x\n"})
        r = self.t.lance("feat/x", entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        env_runner = (self.t.etat / "env-runner.txt").read_text(encoding="utf-8")
        self.assertNotRegex(env_runner, r"(?m)^FINISH_TRAIN_")
        env_ci = (self.t.etat / "ci-env").read_text(encoding="utf-8")
        self.assertNotRegex(env_ci, r"(?m)^FINISH_TRAIN_")

    def test_le_script_ne_lit_jamais_la_liste_des_chemins_d_interface(self):
        # inchangé : le train ne lit ni la liste ni son ancien nom dans le texte du script
        texte = (self.t.run / "tools" / "finish_train.sh").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"finish_e2e_paths|finish_train_e2e", texte))

    def test_les_anciennes_variables_dbtest_et_e2e_ne_sont_plus_lues(self):
        # neuf (R-114) : FINISH_TRAIN_DBTEST et FINISH_TRAIN_E2E sont retirées, sans avertissement ; posées, elles n'ont aucun effet
        self.t.branche("feat/x", {CHEMIN_INTERFACE: "x\n"})
        # scénario de la spec « Former substitutions set » : de faux enregistreurs (un fichier témoin par appel, en plus d'un échec), jamais appelés
        dbtest, e2e = self.t.etat / "dbtest-enregistre", self.t.etat / "e2e-enregistre"
        r = self.t.lance("feat/x", extra={"FINISH_TRAIN_DBTEST": f"touch {dbtest}; exit 1", "FINISH_TRAIN_E2E": f"touch {e2e}; exit 1"}, entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        self.assertFalse(dbtest.exists(), "FINISH_TRAIN_DBTEST a été exécutée")
        self.assertFalse(e2e.exists(), "FINISH_TRAIN_E2E a été exécutée")
        self.assertNotIn("FINISH_TRAIN_DBTEST", r.texte)
        self.assertNotIn("FINISH_TRAIN_E2E", r.texte)


if __name__ == "__main__":
    unittest.main()
