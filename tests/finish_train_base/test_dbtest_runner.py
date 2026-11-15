"""
Tâche 2.8 (change finish-train-v1) puis tranche 3 de ci-local-runner (12.3, conception D9) : le passage du conteneur (FINISH_TRAIN_CI, qui remplace
l'appel à ci_local.sh run) puis la passe Mac (FINISH_TRAIN_RUNNER, bash tests/run_all.sh --mac) du train. Le train ne lance plus dbtest : la preuve de
la base est la phase base du passage (code 69), le conteneur indisponible donne 71. La lecture du résultat de la passe Mac : vert, rouge (suites
nommées), non concluant. Aucun verdict ni aucune empreinte écrits avant ce lancement n'est réutilisé.

Convention du faux ci_local (brief de la tranche 3, portée par la fixture) : FINISH_TRAIN_CI, FAUX_CI_LIGNES (lignes imprimées, séparées par des
sauts de ligne), FAUX_CI_CODE (code de sortie, 0 par défaut), journal $ETAT/ci-appels (les arguments de chaque appel). Les tests de sécurité et
ceux qui ont besoin du dossier courant, de l'entrée ou de l'environnement du passage posent leur propre faux (« espion ») dans le dossier d'état.
"""
import unittest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "finish_train"))   # l'aide commune est dans tests/finish_train
from aide_train import AvecTrain, RESERVEES  # noqa: E402

BASE_DB = {"db/001.sql": "SELECT 2;\n"}

# les lignes d'un passage vert de D2 (trois phases, puis la dernière ligne de ci_local)
LIGNES_VERTES = ["ci_passage : phase portable : verte · 1 s", "ci_passage : phase base : verte · 1 s", "ci_passage : phase e2e : verte · 1 s",
                 "ci_local : verdict vert (arbre abc1234, image def5678, 3 suites, 0 suites Mac non lancées)"]
TEMOIN = "temoin-de-l-appelant-"
# variables de l'appelant (l'auteur) qui ne doivent atteindre ni le passage du conteneur ni la passe Mac : base, mots de passe, jetons réservés
NOMS_TEMOINS = ("DBTEST_PORT", "DBTEST_SONDE", "DBTEST_RECORD", "DBTEST_E2E_PASSE", "DBTEST_ATTENTE", "PMZILLA_LAB_DB_PASSWORD",
                "PMZILLA_LAB_DB_PORT", "PMZILLA_LAB_DB_HOST", "FINISH_TRAIN_AUTRE",
                # CI_LOCAL_* de l'appelant (R-20261101-118, correction de la seconde revue) : les fichiers de preuves et de verdicts de ci_local.sh ne
                # doivent pas être redirigés vers un fichier de l'appelant depuis le passage du conteneur ; la valeur témoin est cherchée dans l'environnement du faux
                "CI_LOCAL_PREUVES", "CI_LOCAL_VERDICTS") + tuple(RESERVEES)
PREFIXES_INTERDITS = ("DBTEST_", "PMZILLA_LAB_DB_", "FINISH_TRAIN_", "CI_LOCAL_")


def temoins() -> dict:
    return {nom: TEMOIN + nom for nom in NOMS_TEMOINS}


def cles_env(texte: str) -> list:
    return [l.split("=", 1)[0] for l in texte.splitlines() if "=" in l]


class AvecConteneur(AvecTrain):
    def preecrire_preuve_conteneur(self, arbre: str) -> Path:
        """Écrit AVANT le train la ligne de preuve du conteneur de cet arbre dans ci/preuves du dossier de données (`<arbre> TAB cle TAB portable,base,e2e`)."""
        fichier = self.t.data / "ci" / "preuves"
        fichier.parent.mkdir(parents=True, exist_ok=True)
        with open(fichier, "a", encoding="utf-8") as f:
            f.write(f"{arbre}\tcle-pre-ecrite\tportable,base,e2e\n")
        return fichier

    def ci_appels(self) -> list:
        f = self.t.etat / "ci-appels"
        return f.read_text(encoding="utf-8").splitlines() if f.exists() else []

    def faux_ci(self, nom: str, corps: str) -> str:
        """Écrit un faux passage du conteneur dans le dossier d'état et rend la commande de substitution."""
        chemin = self.t.etat / nom
        # sur un passage vert, comme le vrai : la ligne de preuve « <arbre HEAD> TAB cle-factice TAB portable,base,e2e » dans $PMZILLA_LAB_DATA/ci/preuves
        # (même format que la fixture aide_train.py ; revue Opus point 1) et les trois lignes de phase verte (Q226, R-20261101-116)
        preuve = ('if [ "${FAUX_CI_CODE:-0}" = 0 ] && [ -n "${PMZILLA_LAB_DATA:-}" ]; then mkdir -p "$PMZILLA_LAB_DATA/ci"; '
                  'printf \'%s\\t%s\\t%s\\n\' "$(git rev-parse \'HEAD^{tree}\')" cle-factice portable,base,e2e >> "$PMZILLA_LAB_DATA/ci/preuves"; fi\n')
        chemin.write_text("#!/bin/bash\n" + corps + preuve + "".join(f'echo "{l}"\n' for l in LIGNES_VERTES) + 'exit "${FAUX_CI_CODE:-0}"\n', encoding="utf-8")
        return f"bash {chemin}"

    def espion(self) -> str:
        """Un faux passage vert qui note son dossier, son entrée, le jeton, ses arguments et tout son environnement."""
        e = self.t.etat
        return self.faux_ci("ci-espion",
                            f'echo "ci pwd=$(pwd -P) args=[$*] stdin=[$(cat)] jeton=${{FINISH_LOCK_TOKEN:+present}} dbvars=[$(compgen -e DBTEST_ | tr \'\\n\' \' \')]" '
                            f'>> "{e}/ci-espion-appels"\nenv | sort >> "{e}/ci-espion-env.txt"\n')

    def sans_temoin(self, texte: str, qui: str):
        self.assertNotIn(TEMOIN, texte, f"une variable de l'appelant (valeur témoin) atteint {qui}")
        cles = cles_env(texte)
        for cle in cles:
            for prefixe in PREFIXES_INTERDITS:
                self.assertFalse(cle.startswith(prefixe), f"{cle} atteint {qui}")
        for nom in NOMS_TEMOINS:
            self.assertNotIn(nom, cles, f"{nom} atteint {qui}")


class PassageConteneur(AvecConteneur):
    def test_ci_tourne_une_fois_meme_avec_une_ligne_dbtest_deja_presente_pour_l_arbre_du_train(self):
        # réécrit (ex test_dbtest_tourne_meme_avec_une_ligne_deja_presente...) : un verdict antérieur n'évite pas le passage ; dbtest n'est plus lancé
        # pmzilla-dbtest-ok n'est plus lu par le train : la preuve pré-écrite est celle du conteneur (ci/preuves), la seule que le train lit pour la phase base
        self.t.branche("feat/x", BASE_DB)
        fichier = self.preecrire_preuve_conteneur(self.t.arbre("feat/x"))
        r = self.t.lance("feat/x", entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(len(self.ci_appels()), 1, "la preuve pré-écrite n'évite pas le passage")
        lignes = [l for l in fichier.read_text(encoding="utf-8").splitlines() if l.startswith(self.t.arbre("feat/x") + "\t")]
        self.assertEqual(len(lignes), 2, "la ligne pré-écrite reste et le passage a écrit la sienne (réécriture après le repère)")
        self.assertEqual(self.t.appels("dbtest"), [])
        self.contient(r, "runner complet vert sur l'arbre du train")

    def test_ci_tourne_dans_le_worktree_d_integration_entree_fermee_avec_le_jeton(self):
        # réécrit (ex test_dbtest_tourne_dans_le_worktree_d_integration...)
        self.t.branche("feat/x", BASE_DB)
        r = self.t.lance("feat/x", extra={"FINISH_TRAIN_CI": self.espion()}, entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        (ligne,) = (self.t.etat / "ci-espion-appels").read_text(encoding="utf-8").splitlines()
        self.assertIn("pwd=", ligne)
        self.assertIn("/wt-train-", ligne.split(" args=")[0])
        self.assertIn("args=[]", ligne, "FINISH_TRAIN_CI remplace la commande entière : aucun argument ajouté (la commande par défaut « run » est testée par la sonde par défaut)")
        self.assertIn("stdin=[]", ligne)
        self.assertIn("jeton=present", ligne)

    def test_ci_ne_recoit_aucune_variable_de_l_appelant(self):
        # réécrit (test de sécurité, R-20261101-115 ; ex test_dbtest_ne_recoit_aucune_variable_dbtest...) : valeur témoin posée chez l'appelant,
        # cherchée dans les arguments et dans tout l'environnement que reçoit le faux passage
        self.t.branche("feat/x", BASE_DB)
        r = self.t.lance("feat/x", extra={**temoins(), "FINISH_TRAIN_CI": self.espion()}, entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        (ligne,) = (self.t.etat / "ci-espion-appels").read_text(encoding="utf-8").splitlines()
        self.assertIn("dbvars=[]", ligne)
        self.assertNotIn(TEMOIN, ligne, "une variable de l'appelant est passée en argument")
        self.sans_temoin((self.t.etat / "ci-espion-env.txt").read_text(encoding="utf-8"), "le passage du conteneur")

    def test_ci_par_defaut_est_celui_de_main_lance_depuis_le_worktree_d_integration(self):
        # réécrit (ex test_dbtest_par_defaut_est_celui_de_l_arbre_du_train..., FINISH_TRAIN_DBTEST à None) : sans FINISH_TRAIN_CI, le train lance
        # « ci_local.sh run » depuis le worktree d'intégration, entrée fermée, avec le jeton et sans variable de l'appelant (valeur témoin)
        sonde = self.t.remplir(
            "#!/bin/bash\n"
            'ETAT="@ETAT@"\n'
            'echo "ci-defaut script=$0 pwd=$(pwd -P) args=[$*] stdin=[$(cat)] jeton=${FINISH_LOCK_TOKEN:+present} '
            "dbvars=[$(compgen -e DBTEST_ | tr '\\n' ' ')]\" >> \"$ETAT/appels.log\"\n"
            'env | sort > "$ETAT/env-ci-defaut.txt"\n'
            # preuve d'un passage vert (revue Opus point 1) : sans elle la stabilité donnerait 71
            'mkdir -p "$PMZILLA_LAB_DATA/ci"\n'
            "printf '%s\\t%s\\t%s\\n' \"$(git rev-parse 'HEAD^{tree}')\" cle-factice portable,base,e2e >> \"$PMZILLA_LAB_DATA/ci/preuves\"\n"
            + "".join(f'echo "{l}"\n' for l in LIGNES_VERTES) + "exit 0\n")
        self.t.commit_main({"tools/ci_local.sh": sonde}, pousser=True)
        self.t.mettre_a_jour_run()
        self.t.branche("feat/x", BASE_DB)
        r = self.t.lance("feat/x", extra={**temoins(), "FINISH_TRAIN_CI": None}, entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        (ligne,) = self.t.appels("ci-defaut")
        # origine du script (spec ci-local-runner, design D9 « Commands » : la commande par défaut est `bash "$SCRIPT_DIR/ci_local.sh" run`, SCRIPT_DIR étant le dossier
        # de l'arbre d'exécution qui porte le finish_train.sh lancé ; principe de B6 de D7 : le code qui juge est celui de main, jamais celui de l'arbre testé)
        script = ligne.split("script=")[1].split(" pwd=")[0]
        self.assertEqual(Path(script).resolve(), (self.t.run / "tools" / "ci_local.sh").resolve(), "le script lancé est celui de l'arbre d'exécution")
        self.assertNotIn("/wt-train-", script, "le script lancé n'est pas celui du worktree d'intégration (l'arbre testé)")
        self.assertIn("/wt-train-", ligne.split(" pwd=")[1].split(" args=")[0], "le dossier courant est le worktree d'intégration")
        self.assertIn("args=[run]", ligne)
        self.assertIn("stdin=[]", ligne)
        self.assertIn("jeton=present", ligne)
        self.assertIn("dbvars=[]", ligne)
        self.sans_temoin((self.t.etat / "env-ci-defaut.txt").read_text(encoding="utf-8"), "le passage du conteneur par défaut")

    def test_base_rouge(self):
        # réécrit (ex test_dbtest_rouge) : la preuve de la base est la phase base du passage (D9, code 69)
        self.t.branche("feat/x", BASE_DB)
        avant = self.t.instantane()
        lignes = "\n".join(["ci_passage : phase portable : verte · 1 s", "ci_passage : phase base : rouge · 2 s : suite_db",
                            "ci_passage : phase e2e : sautée (phase précédente rouge)",
                            "ci_local : verdict rouge (arbre abc1234, image def5678) : suite_db"])
        r = self.t.lance("feat/x", extra={"FAUX_CI_LIGNES": lignes, "FAUX_CI_CODE": "1"}, entree="o\n")
        self.code(r, 69, "phase base du conteneur rouge sur l'arbre du train ; rien n'est fusionné")
        self.rien_ne_change(avant)
        self.assertEqual(self.t.appels("runner"), [])
        self.assertEqual(self.t.appels("dbtest"), [])

    def test_conteneur_indisponible_code_3(self):
        # neuf (D9, Q170) : aucune route de secours
        self.t.branche("feat/x")
        avant = self.t.instantane()
        r = self.t.lance("feat/x", extra={"FAUX_CI_LIGNES": "ci_local : conteneur indisponible", "FAUX_CI_CODE": "3"}, entree="o\n")
        self.code(r, 71, "runner non concluant : conteneur indisponible (code 3) ; rien n'est fusionné")
        self.rien_ne_change(avant)
        self.assertEqual(self.t.appels("runner"), [])

    def test_conteneur_indisponible_code_5(self):
        self.t.branche("feat/x")
        avant = self.t.instantane()
        r = self.t.lance("feat/x", extra={"FAUX_CI_LIGNES": "ci_local : image absente", "FAUX_CI_CODE": "5"}, entree="o\n")
        self.code(r, 71, "runner non concluant : conteneur indisponible (code 5) ; rien n'est fusionné")
        self.rien_ne_change(avant)
        self.assertEqual(self.t.appels("runner"), [])

    def test_ci_tourne_aussi_quand_le_code_de_la_base_est_inchange(self):
        # réécrit (ex test_dbtest_sans_objet_quand_le_code_de_la_base_est_inchange) : le passage tourne dans tout train, dbtest jamais
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(len(self.ci_appels()), 1)
        self.assertEqual(self.t.appels("dbtest"), [])

    def test_ci_avant_la_passe_mac(self):
        # réécrit (ex test_dbtest_avant_le_runner) : le journal du faux passage est écrit avant l'environnement noté au départ de la passe Mac
        self.t.branche("feat/x", BASE_DB)
        r = self.t.lance("feat/x", entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(len(self.ci_appels()), 1)
        self.assertEqual(len(self.t.appels("runner")), 1)
        ci = (self.t.etat / "ci-appels").stat().st_mtime_ns
        runner = (self.t.etat / "env-runner.txt").stat().st_mtime_ns
        self.assertLess(ci, runner, "le passage du conteneur précède la passe Mac")


class Runner(AvecConteneur):
    def un(self, mode, **extra):
        self.t.branche("feat/x")
        avant = self.t.instantane()
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_MODE": mode, **extra}, entree="o\n")
        return r, avant

    def test_runner_complet_vert_dans_le_worktree_d_integration(self):
        # réécrit : la passe Mac est « run_all.sh --mac » (le passage du conteneur la précède)
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "lancement du runner complet dans le worktree d'intégration", "runner complet vert sur l'arbre du train")
        (ligne,) = self.t.appels("runner")
        self.assertIn("/wt-train-", ligne)
        self.assertIn("args=[]", ligne, "FINISH_TRAIN_RUNNER posé remplace la commande entière : rien n'est ajouté, ni nom de suite ni option (« --mac » est testé avec la commande par défaut)")
        self.assertIn("stdin=[]", ligne)

    def test_runner_rouge_nomme_les_suites_de_la_ligne_total(self):
        r, avant = self.un("rouge")
        self.code(r, 70, "train rouge : suites en échec : suite_a suite_b ; rien n'est fusionné",
                  "retirer de la liste la branche qui casse ces suites, puis relancer la ligne")
        # Q232 (a), R-20261101-118 : l'étape de la passe Mac s'appelle « passe Mac » (ex « runner ») : changement de valeur attendue autorisé par cette réponse
        self.assertIn("===== arrêt à passe Mac : ", r.texte)
        self.assertNotIn("===== arrêt à runner", r.texte)
        self.rien_ne_change(avant)

    def test_runner_sortie_4_gel(self):
        r, avant = self.un("code4")
        self.code(r, 71, "runner non concluant (code 4) : fin de branche en cours (gel) ; rien n'est fusionné")
        self.absent(r, "suites en échec")
        self.rien_ne_change(avant)

    def test_runner_sortie_6_refus_du_lanceur(self):
        r, avant = self.un("code6")
        self.code(r, 71, "runner non concluant (code 6) : lancement refusé par le lanceur ; rien n'est fusionné")
        self.absent(r, "suites en échec")
        self.rien_ne_change(avant)

    def test_runner_sortie_1_sans_ligne_total(self):
        r, avant = self.un("code1_sans_total")
        self.code(r, 71, "runner non concluant (code 1) : ligne TOTAL absente ; rien n'est fusionné")
        self.absent(r, "suites en échec")
        self.rien_ne_change(avant)

    def test_worktree_modifie_pendant_le_runner_fichier_suivi(self):
        r, avant = self.un("modifie_suivi")
        self.code(r, 71, "runner non concluant (code 0) : worktree d'intégration modifié pendant le runner ; rien n'est fusionné")
        # Q232 (a), R-20261101-118 : la stabilité après la passe Mac porte l'étape « passe Mac » (ex « runner ») : valeur attendue changée par cette réponse
        self.assertIn("===== arrêt à passe Mac : ", r.texte)
        self.assertNotIn("===== arrêt à runner", r.texte)
        # le worktree d'intégration modifié n'est jamais forcé : il reste, listé par Git ; les références ne bougent pas
        self.assertEqual(self.t.instantane()["refs"], avant["refs"])
        self.assertEqual(self.t.distant_main(), self.t.main())

    def test_worktree_modifie_pendant_le_runner_fichier_non_suivi(self):
        r, _ = self.un("modifie_non_suivi")
        self.code(r, 71, "runner non concluant (code 0) : worktree d'intégration modifié pendant le runner")

    def test_fichier_suivi_reecrit_avec_le_meme_contenu_seul_le_ctime_change(self):
        # revue de u5, B-1 : le contrôle de la date de changement d'état (D10, règle c) voit une réécriture à l'identique, que git status ne voit pas
        r, avant = self.un("reecrit_meme_contenu")
        self.code(r, 71, "runner non concluant (code 0) : worktree d'intégration modifié pendant le runner ; rien n'est fusionné")
        self.assertEqual(self.t.instantane()["refs"], avant["refs"])
        self.assertEqual(self.t.distant_main(), self.t.main())

    def test_fichiers_et_dossiers_ignores_crees_pendant_le_runner_ne_le_rendent_pas_non_concluant(self):
        # défaut du 2026-10-27 : __pycache__ et mothra/front/dist/ créés par le runner changent la date des dossiers parents d'un worktree neuf
        # mothra/ et mothra/front/ sont des dossiers suivis (ils portent un fichier suivi) : leur date change quand dist/ apparaît
        self.t.branche("feat/x", {"mothra/package.json": "{}\n", "mothra/front/package.json": "{}\n"})
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_MODE": "ignores_crees"}, entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        self.absent(r, "runner non concluant")

    def test_fichier_ignore_cree_puis_supprime_pendant_le_runner(self):
        # conséquence acceptée (décision du 2026-10-28) : la date du dossier a changé, sa liste est identique : modifié
        r, _ = self.un("ignores_supprimes")
        self.code(r, 71, "runner non concluant (code 0) : worktree d'intégration modifié pendant le runner ; rien n'est fusionné")

    def test_fichier_non_ignore_cree_puis_supprime_pendant_le_runner(self):
        r, _ = self.un("passager_non_ignore")
        self.code(r, 71, "runner non concluant (code 0) : worktree d'intégration modifié pendant le runner ; rien n'est fusionné")

    def test_dossier_suivi_renomme_puis_remis_pendant_le_runner(self):
        r, _ = self.un("dossier_renomme_remis")
        self.code(r, 71, "runner non concluant (code 0) : worktree d'intégration modifié pendant le runner ; rien n'est fusionné")

    def test_limite_connue_fichier_passager_cache_par_un_ajout_ignore_du_meme_dossier(self):
        # LIMITE CONNUE, documentée (décision du 2026-10-28) : un fichier passager non ignoré, créé puis supprimé dans un dossier qui a aussi reçu un
        # ajout ignoré, n'est pas vu (la liste ne montre que l'ajout ignoré). Ce test montre la limite ; il ne la recommande pas.
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_MODE": "limite_passager"}, entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        self.absent(r, "runner non concluant")

    def test_echec_de_git_check_ignore_apres_le_premier_releve(self):
        # tout échec d'outil donne « modifié » : git check-ignore échoue (code 128, posé par le runner factice) alors qu'un ajout est à juger
        self.t.branche("feat/x", {"mothra/package.json": "{}\n", "mothra/front/package.json": "{}\n"})
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_MODE": "ignores_crees", "FAKE_RUNNER_CHECK_IGNORE_CODE": "128"}, entree="o\n")
        self.code(r, 71, "runner non concluant (code 0) : worktree d'intégration modifié pendant le runner ; rien n'est fusionné")

    def rendre_db_listable_a_la_fin(self):
        # le runner ou le faux passage passe db en 311 dans le worktree d'intégration (gardé après un 71) : remis avant le nettoyage du dossier jetable
        def remettre():
            for p in self.t.worktrees.glob("wt-train-*"):
                if (p / "db").exists():
                    (p / "db").chmod(0o755)
        self.addCleanup(remettre)

    def test_dossier_vide_cree_pendant_le_runner_est_un_ajout_non_ignore(self):
        # revue M1 : la vérification « ajout non ignoré » (git check-ignore) est atteinte par un ajout que git status ne voit pas
        r, _ = self.un("dossier_vide_cree")
        self.code(r, 71, "runner non concluant (code 0) : worktree d'intégration modifié pendant le runner ; rien n'est fusionné")

    def test_dossier_cree_qui_ne_contient_que_des_fichiers_ignores_est_un_ajout_non_ignore(self):
        r, _ = self.un("dossier_tout_ignore_cree")
        self.code(r, 71, "runner non concluant (code 0) : worktree d'intégration modifié pendant le runner ; rien n'est fusionné")

    def test_ls_echoue_apres_le_runner(self):
        # revue m4 : un dossier suivi que ls ne peut plus lister (chmod 311 par le runner) : tout échec d'outil donne « modifié »
        self.rendre_db_listable_a_la_fin()
        r, _ = self.un("ls_echoue")
        self.code(r, 71, "runner non concluant (code 0) : worktree d'intégration modifié pendant le runner ; rien n'est fusionné")

    def test_releve_initial_en_erreur(self):
        # réécrit (ex FAKE_DBTEST_MODE ls_echoue ; revue m4 ; revue Opus point 7) : le premier relevé précède le passage du conteneur, donc le déclencheur
        # agit AVANT lui : le faux git rend « db » non listable juste après la création du worktree d'intégration. Le relevé vaut « erreur » (DIR_SNAP) et
        # le train n'est jamais concluant, alors que le passage du conteneur et la passe Mac sont verts (le passage ne touche à rien)
        self.rendre_db_listable_a_la_fin()
        self.t.branche("feat/x", BASE_DB)
        r = self.t.lance("feat/x", extra={"FAKE_WORKTREE_ADD_DB_ILLISIBLE": "1"}, entree="o\n")
        self.assertEqual(len(self.ci_appels()), 1, "le passage du conteneur a tourné et était vert : seul le premier relevé en erreur rend le train non concluant")
        self.code(r, 71, "runner non concluant (code 0) : worktree d'intégration modifié pendant le runner ; rien n'est fusionné")

    def test_git_ls_files_en_echec_au_premier_releve(self):
        # revue m5 : l'échec de git ls-files (dans tracked_dirs) n'est pas avalé : le relevé vaut « erreur »
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", extra={"FAKE_LS_FILES_AVANT_RUNNER": "1"}, entree="o\n")
        self.code(r, 71, "runner non concluant (code 0) : worktree d'intégration modifié pendant le runner ; rien n'est fusionné")

    def test_fichier_suivi_renomme_pendant_le_runner(self):
        r, avant = self.un("renomme_suivi_definitif")
        self.code(r, 71, "runner non concluant (code 0) : worktree d'intégration modifié pendant le runner ; rien n'est fusionné")
        self.assertEqual(self.t.instantane()["refs"], avant["refs"])

    def test_fichier_suivi_renomme_puis_remis_pendant_le_runner(self):
        r, _ = self.un("renomme_suivi")
        self.code(r, 71, "runner non concluant (code 0) : worktree d'intégration modifié pendant le runner ; rien n'est fusionné")

    def test_dossier_suivi_recree_pendant_le_runner(self):
        # seul l'inode du dossier « openspec » change (aucune date de fichier) : la liste « inode nom » de la racine voit une entrée d'un autre inode
        r, _ = self.un("dossier_recree")
        self.code(r, 71, "runner non concluant (code 0) : worktree d'intégration modifié pendant le runner ; rien n'est fusionné")

    def test_runner_sortie_7_dependances_npm_avec_la_ligne_lancer(self):
        # revue de u5, m-5 : une raison juste, et la ligne « lancer : » du runner est transmise
        r, avant = self.un("code7")
        self.code(r, 71, "runner non concluant (code 7) : dépendances npm à mettre en conformité (ligne « lancer : » ci-dessus) ; rien n'est fusionné")
        self.assertIn("\nlancer : cd mothra/serveur && npm ci\n", r.texte)
        self.absent(r, "ligne TOTAL absente", "suites en échec")
        self.rien_ne_change(avant)

    def test_verification_des_processus_impossible_avant_le_runner(self):
        # décision du 2026-10-27 (D10, D14, D18) : lsof impossible avant le runner : 71, le runner ne tourne pas ; branche sans worktree (aucune
        # vérification à l'admission)
        self.t.branche("feat/x", worktree=False)
        avant = self.t.instantane()
        r = self.t.lance("feat/x", extra={"FAKE_LSOF_MODE": "casse"}, entree="o\n")
        self.code(r, 71, "runner non concluant : processus dans le worktree (vérification impossible) ; rien n'est fusionné")
        self.assertEqual(self.t.appels("runner"), [])
        # le worktree d'intégration reste (la vérification est impossible à la sortie aussi), les références ne bougent pas
        self.assertEqual(self.t.instantane()["refs"], avant["refs"])
        self.assertEqual(self.t.main(), self.t.distant_main())
        self.assertIn("processus dans le worktree (vérification impossible)", r.texte.split("worktree gardé")[-1])

    def test_verification_des_processus_impossible_apres_le_runner(self):
        self.t.branche("feat/x", worktree=False)
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_LSOF_MODE": "casse"}, entree="o\n")
        self.code(r, 71, "runner non concluant (code 0) : processus dans le worktree (vérification impossible) ; rien n'est fusionné")
        self.assertEqual(len(self.t.appels("runner")), 1)

    def test_liste_des_processus_qui_ne_montre_pas_le_script_apres_le_runner(self):
        self.t.branche("feat/x", worktree=False)
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_LSOF_MODE": "sans_moi"}, entree="o\n")
        self.code(r, 71, "runner non concluant (code 0) : processus dans le worktree (vérification impossible) ; rien n'est fusionné")

    def test_empreinte_absente(self):
        r, avant = self.un("sans_empreinte")
        self.code(r, 71, "runner non concluant (code 0) : empreinte du runner absente, différente de l'arbre du train ou non réécrite ; rien n'est fusionné")
        self.assertIn("===== arrêt à passe Mac : ", r.texte)   # Q232 (a), R-20261101-118 (ex « runner »)
        self.rien_ne_change(avant)

    def test_empreinte_d_un_autre_arbre(self):
        r, _ = self.un("autre_empreinte")
        self.code(r, 71, "runner non concluant (code 0) : empreinte du runner absente, différente de l'arbre du train ou non réécrite")

    def test_empreinte_ecrite_avant_le_lancement_et_non_reecrite(self):
        # réécrit (ex FAKE_DBTEST_FORGE_EMPREINTE : dbtest ne précède plus la passe) : la ligne exacte de l'arbre du train est déjà dans l'empreinte Mac
        # (et dans l'empreinte historique) avant le lancement ; la passe Mac ne la réécrit pas : sa date est trop ancienne
        self.t.branche("feat/x")
        arbre = self.t.arbre("feat/x")
        self.t.fichier_empreinte().write_text(arbre + "\n", encoding="utf-8")
        with open(self.t.commun() / "pmzilla-run-mac-ok", "a", encoding="utf-8") as f:
            f.write(arbre + "\n")
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_MODE": "sans_empreinte"}, entree="o\n")
        self.code(r, 71, "runner non concluant (code 0) : empreinte du runner absente, différente de l'arbre du train ou non réécrite")

    PHRASE_PREUVE_CONTENEUR = ("runner non concluant (code 0) : preuve du conteneur absente, différente de l'arbre du train, "
                               "sans exactement portable,base,e2e ou non réécrite")

    def test_conteneur_vert_sans_ligne_de_preuve_donne_71(self):
        # neuf (remplace les cas 69 et 82 d'origine « vert sans ligne », retirés avec leur mécanisme ; R-20261101-114, stabilité Q219) : le conteneur sort 0 avec
        # les trois phases vertes, mais n'écrit aucune ligne dans ci/preuves (FAUX_CI_SANS_PREUVE) : la stabilité refuse, rien n'est fusionné
        self.t.branche("feat/x", BASE_DB)
        avant = self.t.instantane()
        r = self.t.lance("feat/x", extra={"FAUX_CI_SANS_PREUVE": "1"}, entree="o\n")
        self.code(r, 71, self.PHRASE_PREUVE_CONTENEUR)
        self.assertEqual(len(self.ci_appels()), 1)
        self.rien_ne_change(avant)

    def test_conteneur_vert_avec_une_preuve_non_reecrite_donne_71(self):
        # neuf (même remplacement) : la bonne ligne de l'arbre est déjà dans ci/preuves avant le train, le conteneur ne la réécrit pas (FAUX_CI_SANS_PREUVE) :
        # le fichier est plus ancien que le repère, la preuve d'avant ne compte pas
        self.t.branche("feat/x", BASE_DB)
        self.preecrire_preuve_conteneur(self.t.arbre("feat/x"))
        avant = self.t.instantane()
        r = self.t.lance("feat/x", extra={"FAUX_CI_SANS_PREUVE": "1"}, entree="o\n")
        self.code(r, 71, self.PHRASE_PREUVE_CONTENEUR)
        self.assertEqual(len(self.ci_appels()), 1)
        self.rien_ne_change(avant)

    def test_un_verdict_vert_force_avant_le_lancement_n_evite_pas_le_runner(self):
        self.t.branche("feat/x")
        arbre = self.t.arbre("feat/x")
        self.t.fichier_empreinte().write_text(arbre + "\n", encoding="utf-8")
        with open(self.t.commun() / "pmzilla-run-mac-ok", "a", encoding="utf-8") as f:
            f.write(arbre + "\n")
        self.preecrire_preuve_conteneur(arbre)   # la preuve du conteneur pré-écrite, avec celle de la passe Mac : aucune des deux n'évite le lancement
        with open(self.t.commun() / "pmzilla-main-validated", "a", encoding="utf-8") as f:
            f.write(f"{arbre}\tcomplet\t2099-01-01\t{'0' * 64}\n")
        r = self.t.lance("feat/x", entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(len(self.ci_appels()), 1, "le passage du conteneur tourne quand même")
        self.assertEqual(len(self.t.appels("runner")), 1, "la passe Mac tourne quand même")

    def test_aucune_variable_reservee_n_atteint_le_runner(self):
        self.t.branche("feat/x")
        extra = {nom: "1" for nom in RESERVEES}
        extra["FINISH_TRAIN_AUTRE"] = "1"
        r = self.t.lance("feat/x", extra=extra, entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        env = (self.t.etat / "env-runner.txt").read_text(encoding="utf-8")
        cles = [l.split("=", 1)[0] for l in env.splitlines() if "=" in l]
        for cle in cles:
            self.assertFalse(cle.startswith("FINISH_TRAIN_"), cle)
        for nom in RESERVEES:
            self.assertNotIn(nom, cles)
        self.assertIn("FINISH_LOCK_TOKEN", cles)

    def test_passe_mac_par_defaut_ne_recoit_aucune_variable_de_l_appelant(self):
        # réécrit (test de sécurité, R-20261101-115 ; ex test_runner_par_defaut_ne_recoit_aucune_variable_dbtest_de_l_auteur, T1) : vraie sonde sur la
        # commande par défaut « bash tests/run_all.sh --mac » lancée depuis le worktree d'intégration (tests/run_all.sh est commité sur main et
        # FINISH_TRAIN_RUNNER est retiré). Elle écrit l'empreinte Mac de l'arbre (dossier commun de Git, D7) et la ligne TOTAL comme une passe verte,
        # et sa propre ligne et son environnement hors du worktree d'intégration (le contrôle de stabilité ne doit rien voir). Valeur témoin chez l'appelant.
        sonde = self.t.remplir(
            "#!/bin/bash\n"
            'ETAT="@ETAT@"\n'
            "echo \"runall-arbre pwd=$(pwd -P) args=[$*] dbvars=[$(compgen -e DBTEST_ | tr '\\n' ' ')]\" >> \"$ETAT/appels.log\"\n"
            'env | sort > "$ETAT/env-runall-defaut.txt"\n'
            "git rev-parse 'HEAD^{tree}' >> \"$(git rev-parse --path-format=absolute --git-common-dir)/pmzilla-run-mac-ok\"\n"
            'echo "TOTAL : 1 tests dans 1 suites · tous réussis · durée totale 1 s"\n'
            "exit 0\n")
        self.t.commit_main({"tests/run_all.sh": sonde}, pousser=True)
        self.t.mettre_a_jour_run()
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", extra={**temoins(), "FINISH_TRAIN_RUNNER": None}, entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        (ligne,) = self.t.appels("runall-arbre")
        self.assertIn("/wt-train-", ligne, "la sonde tourne dans le worktree d'intégration")
        self.assertIn("args=[--mac]", ligne)
        self.assertIn("dbvars=[]", ligne)
        env = (self.t.etat / "env-runall-defaut.txt").read_text(encoding="utf-8")
        self.assertNotIn(TEMOIN, env, "une variable de l'appelant atteint la passe Mac par défaut")
        cles = cles_env(env)
        for cle in cles:
            for prefixe in ("DBTEST_", "PMZILLA_LAB_DB_"):
                self.assertFalse(cle.startswith(prefixe), cle)
        for nom in RESERVEES:
            self.assertNotIn(nom, cles)

    def test_aucune_variable_de_l_appelant_n_atteint_le_passage_du_conteneur_ni_la_passe_mac(self):
        # réécrit (test de sécurité, R-20261101-115 ; ex test_aucune_variable_dbtest_de_l_auteur_n_atteint_le_runner) : le train tourne hors session,
        # et transmettrait aux suites les variables de base de l'appelant ; valeur témoin cherchée dans l'environnement du faux passage ET dans celui
        # de la passe Mac (les noms DBTEST_*, PMZILLA_LAB_DB_* et les jetons réservés)
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", extra={**temoins(), "FINISH_TRAIN_CI": self.espion()}, entree="n\n")
        self.assertEqual(r.code, 0, r.texte)
        self.sans_temoin((self.t.etat / "ci-espion-env.txt").read_text(encoding="utf-8"), "le passage du conteneur")
        env = (self.t.etat / "env-runner.txt").read_text(encoding="utf-8")
        self.assertNotIn(TEMOIN, env, "une variable de l'appelant atteint la passe Mac")
        cles = cles_env(env)
        self.assertEqual([c for c in cles if c.startswith("DBTEST_") or c.startswith("PMZILLA_LAB_DB_")], [])


if __name__ == "__main__":
    unittest.main()
