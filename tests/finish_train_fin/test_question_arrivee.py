"""
Tâche 2.9 (change finish-train-v1) : le résumé, la question, l'essai rapide et l'arrivée dans main (conception D11 à D13, D24 ; codes 0, 73 et 74).
Toute réponse autre que « o » sort en 0 avec le sens de bannière « essai ». L'avance rapide ne vient qu'après une relecture des références, la
seconde garde du matin et l'écriture de l'empreinte de l'espace de travail ; le push se fait sans la variable de contournement du propriétaire.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "finish_train"))   # l'aide commune est dans tests/finish_train
from aide_train import AvecTrain  # noqa: E402

REPONSE_AUTRE = "réponse autre que « o » : rien n'est fusionné ; relancer la même ligne pour terminer le train"
ESSAI = "essai rapide : contrôles passés, sans dbtest ni runner ; rien n'est écrit dans les références"


# faux tools/ci_local.sh commité dans main : trois phases vertes, la preuve du conteneur dans ci/preuves, la dernière ligne au format de ci_local
CI_VERT = ("#!/bin/bash\n"
           'mkdir -p "$PMZILLA_LAB_DATA/ci"\n'
           "printf '%s\\t%s\\t%s\\n' \"$(git rev-parse 'HEAD^{tree}')\" cle-factice portable,base,e2e >> \"$PMZILLA_LAB_DATA/ci/preuves\"\n"
           'echo "ci_passage : phase portable : verte · 1 s"\n'
           'echo "ci_passage : phase base : verte · 1 s"\n'
           'echo "ci_passage : phase e2e : verte · 1 s"\n'
           'echo "ci_local : verdict vert (arbre aaaaaaaaaaaa, image bbbbbbbbbbbb, phases portable,base,e2e, 3 suites, 0 suites Mac non lancées)"\n')


class Reponses(AvecTrain):
    def test_reponses_autres_que_o(self):
        self.t.branche("feat/x")
        for entree in ("n\n", "\n", "", "oui\n", "O\n"):
            with self.subTest(entree=entree):
                avant = self.t.instantane()
                r = self.t.lance("feat/x", entree=entree)
                self.code(r, 0, REPONSE_AUTRE)
                self.contient(r, "Terminer le train (1 branche(s)) ? (o/n) ")
                self.rien_ne_change(avant)
                self.assertIsNone(self.t.empreinte(), "aucune empreinte écrite")
                self.assertEqual(self.t.worktrees_train(), [], "worktree d'intégration retiré")
                lignes = self.t.journaux()[-1].read_text(encoding="utf-8").splitlines()
                self.assertRegex(lignes[-1], r"^===== fin du train : code 0 \(essai\), \d{4}-\d\d-\d\d \d\d:\d\d:\d\d Paris =====$")
                self.assertFalse([l for l in lignes if l.startswith("===== arrêt à")])
                for f in self.t.journaux():
                    f.unlink()

    def test_le_resume_precede_la_question(self):
        x, y = self.deux_branches()
        r = self.t.lance(x, y, entree="n\n")
        self.contient(r, "  1. feat/x : sommet ", "  2. feat/y : sommet ", "commit(s)", "fichier(s)", "fichiers non examinés par le contrôle des noms : ",
                      "Terminer le train (2 branche(s)) ? (o/n) ")
        self.assertLess(r.texte.index("  1. feat/x"), r.texte.index("Terminer le train"))


class Essai(AvecTrain):
    def test_essai_rapide(self):
        self.t.branche("feat/x")
        avant = self.t.instantane()
        r = self.t.lance("--essai", "feat/x")
        self.code(r, 0, ESSAI)
        self.absent(r, "Terminer le train")
        self.rien_ne_change(avant)
        self.assertEqual(self.t.appels("runner"), [])
        self.assertEqual(self.t.appels("dbtest"), [])
        self.assertFalse((self.t.etat / "ci-appels").exists(), "l'essai rapide ne lance pas la CI locale (faux ci_local jamais appelé)")
        self.assertIsNone(self.t.empreinte())
        self.assertEqual([l for l in self.t.journal_git() if "worktree add" in l], [], "aucun worktree n'est créé")
        lignes = self.t.log().splitlines()
        self.assertRegex(lignes[-1], r"^===== fin du train : code 0 \(essai\), .* Paris =====$")

    def test_essai_ne_pose_aucune_question_meme_avec_une_entree(self):
        self.t.branche("feat/x")
        r = self.t.lance("--essai", "feat/x", entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(self.t.main(), self.t.origin_main())


class AvantLAvanceRapide(AvecTrain):
    def test_une_branche_a_bouge(self):
        self.t.branche("feat/x")
        avant_main = self.t.main()
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_BRANCHE_DANS": str(self.t.dossier_worktree("feat/x"))}, entree="o\n")
        self.assertEqual(r.code, 73, r.texte)
        self.assertRegex(r.texte, r"feat/x a bougé depuis le début de la fin \([0-9a-f]{12} → [0-9a-f]{12}\) ; rien n'est fusionné")
        self.assertEqual(self.t.main(), avant_main)
        self.assertEqual(self.t.distant_main(), avant_main)

    def test_origin_main_a_bouge(self):
        self.t.branche("feat/x")
        avant_main = self.t.main()
        autre = self.t.cloner_ailleurs()
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_ORIGIN": str(autre)}, entree="o\n")
        self.code(r, 73, "main ou origin/main a bougé depuis le début de la fin ; rien n'est fusionné")
        self.assertEqual(self.t.main(), avant_main)
        self.assertNotEqual(self.t.distant_main(), avant_main)

    def test_main_local_a_bouge(self):
        self.t.branche("feat/x")
        avant_main = self.t.main()
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_MAIN": "1"}, entree="o\n")
        self.code(r, 73, "main ou origin/main a bougé depuis le début de la fin ; rien n'est fusionné")
        self.assertNotEqual(self.t.main(), avant_main, "le commit étranger reste : le script ne remet rien à zéro")
        self.assertEqual(self.t.distant_main(), avant_main)


class Arrivee(AvecTrain):
    def test_empreinte_ecrite_avec_l_arbre_du_train_juste_avant_l_avance_rapide(self):
        # réécrit (R-20261101-118, Q233 a) : une commande de test posée n'écrit plus l'empreinte ; le test suit donc le vrai chemin par défaut (runner du dépôt
        # et faux tools/ci_local.sh commité dans main, comme test_main_enregistre_comme_valide_complet...), aussi strict qu'avant : mêmes assertions
        self.t.commit_main({"tools/ci_local.sh": CI_VERT}, pousser=True)
        self.t.mettre_a_jour_run()
        x, y = self.deux_branches()
        r = self.t.lance(x, y, extra={"FINISH_TRAIN_RUNNER": None, "FINISH_TRAIN_CI": None}, entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        vue = (self.t.etat / "empreinte-a-l-avance-rapide.txt").read_text(encoding="utf-8").strip()
        self.assertEqual(vue[:12], self.arbre_du_train(r))
        self.contient(r, "empreinte de l'espace de travail écrite pour l'arbre testé")
        self.assertEqual(self.t.empreinte(), self.t.arbre("main"))

    def test_avance_rapide_puis_push_le_crochet_trouve_l_empreinte(self):
        x, y = self.deux_branches()
        ancien = self.t.main()
        r = self.t.lance(x, y, entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.assertRegex(r.texte, rf"main avancé sur le train : {ancien[:12]} -> [0-9a-f]{{12}}")
        self.contient(r, "main poussé vers origin", "terminé : main ")
        self.assertEqual(self.t.main(), self.t.distant_main())
        self.assertEqual(self.t.main(), self.sommet_du_train(r))
        self.assertEqual(len(self.t.appels("pre-push appelé")), 1)
        self.assertEqual(len(self.t.appels("runner")), 1)
        self.assertEqual(self.t.appels("prepush-runner"), [], "aucun second runner : le crochet a trouvé l'empreinte")

    def test_le_push_n_utilise_ni_no_verify_ni_force(self):
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        for ligne in self.t.journal_git():
            if " push " in f" {ligne} " or ligne.startswith("push"):
                self.assertNotIn("--no-verify", ligne)
                self.assertNotIn("--force", ligne)
                self.assertNotIn(" -f", ligne)

    def test_le_push_nomme_le_commit_du_train_et_non_main(self):
        # revue de u5, M-7 : « git push origin <sommet>:refs/heads/main » ; ce qui part est exactement ce qui a été testé
        x, y = self.deux_branches()
        r = self.t.lance(x, y, entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        sommet = self.sommet_du_train(r)
        pushs = [l for l in self.t.journal_git() if " push " in f" {l} " and "--delete" not in l]
        self.assertEqual(len(pushs), 1, pushs)
        self.assertTrue(pushs[0].endswith(f"push origin {sommet}:refs/heads/main"), pushs[0])

    def test_en_reprise_au_push_le_push_nomme_le_sommet_note_de_main(self):
        x, y = self.deux_branches()
        self.t.etat_fusionne_localement(x, y)
        sommet = self.t.main()
        r = self.t.lance(x, y)
        self.assertEqual(r.code, 0, r.texte)
        pushs = [l for l in self.t.journal_git() if " push " in f" {l} " and "--delete" not in l]
        self.assertTrue(pushs[-1].endswith(f"push origin {sommet}:refs/heads/main"), pushs[-1])

    def test_les_variables_d_identite_heritees_ne_touchent_pas_les_commits_du_train(self):
        # revue de u5, M-6 : l'identité du train est celle de la configuration Git de l'auteur
        self.t.branche("feat/x")
        intrus = {"GIT_AUTHOR_NAME": "intrus", "GIT_AUTHOR_EMAIL": "intrus@example.org", "GIT_COMMITTER_NAME": "intrus",
                  "GIT_COMMITTER_EMAIL": "intrus@example.org"}
        r = self.t.lance("feat/x", extra=intrus, entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(self.t.git("log", "-1", "--format=%an <%ae>|%cn <%ce>", "main"), "test <t@example.org>|test <t@example.org>")

    def test_un_jeton_de_verrou_herite_n_est_pas_reconnu(self):
        # revue de u5, m-13 : un train lancé de l'intérieur d'une autre fin (jeton hérité) trouve son verrou tenu : 67
        self.t.branche("feat/x")
        self.t.verrou_etranger()
        r = self.t.lance("feat/x", extra={"FINISH_LOCK_TOKEN": "jeton-d-un-autre"}, entree="o\n")
        self.assertEqual(r.code, 67, r.texte)
        self.assertEqual(self.t.main(), self.t.origin_main())

    def test_aucun_fichier_temporaire_ne_reste_et_le_tube_de_copie_disparait_des_son_ouverture(self):
        # revue de u5, M-3 : tube de copie à nom unique dans le dossier temporaire, supprimé juste après son ouverture
        self.t.branche("feat/x")
        tmp = self.t.dossier / "tmp"
        tmp.mkdir()
        r = self.t.lance("feat/x", extra={"TMPDIR": str(tmp)}, entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(sorted(p.name for p in tmp.iterdir()), [])
        self.assertEqual(list(self.t.logs.glob("*.fifo")), [])

    def test_sans_tube_tout_va_au_journal(self):
        # le tube ne peut pas être créé (dossier temporaire absent) : repli sans copie, tout au journal seulement, la bannière aussi à l'écran
        self.t.branche("feat/x")
        r = self.t.lance("--essai", "feat/x", extra={"TMPDIR": str(self.t.dossier / "absent")})
        self.assertEqual(r.code, 0, r.texte)
        journal = self.t.log()
        self.assertIn("train : 1 branche(s), base origin/main ", journal)
        self.assertRegex(journal.splitlines()[-1], r"^===== fin du train : code 0 \(essai\), .* Paris =====$")
        self.assertIn(journal.splitlines()[-1], r.texte)

    def test_push_refuse(self):
        x, y = self.deux_branches()
        ancien = self.t.main()
        self.t.refuser_le_push()
        r = self.t.lance(x, y, entree="o\n")
        self.code(r, 74, "push refusé : le train est fusionné dans main local seulement ; relancer la même ligne pour pousser")
        self.assertEqual(self.t.distant_main(), ancien)
        self.assertEqual(len(self.t.chaine_premiers_parents("main", ancien)), 2, "main local porte les deux fusions")
        self.assertEqual(self.t.worktrees_train(), [])
        self.assertTrue(self.t.dossier_worktree(x).exists() and self.t.dossier_worktree(y).exists(), "pas de nettoyage avant le push")

    def test_push_sans_la_variable_de_contournement_du_proprietaire(self):
        # l'empreinte de l'espace de travail manque : le crochet doit refuser ; si le script passait la variable de contournement, le push passerait
        x, y = self.deux_branches()
        self.t.etat_fusionne_localement(x, y)
        # réécrit (R-20261101-118, Q233 a) : avec une commande de test posée, l'empreinte de l'espace de travail n'est plus écrite (missing_ok) ; le crochet
        # a aussi la voie du conteneur (D8) : les deux fichiers de cette preuve sont retirés, pour que le crochet n'ait AUCUNE preuve et doive refuser
        self.t.fichier_empreinte().unlink(missing_ok=True)
        (self.t.commun() / "pmzilla-run-mac-ok").unlink(missing_ok=True)
        (self.t.data / "ci" / "preuves").unlink(missing_ok=True)
        r = self.t.lance(x, y, extra={"PMZILLA_SKIP_GREEN_CHECK": "1"}, entree="o\n")
        self.assertEqual(r.code, 74, r.texte)
        self.assertEqual(len(self.t.appels("prepush-runner")), 1, "le crochet a bien fait son contrôle")


class EnregistrementDeMain(AvecTrain):
    def test_main_enregistre_comme_valide_complet_avec_le_runner_et_le_ci_local_du_depot(self):
        # réécrit (ex ...avec_le_runner_du_depot) : l'enregistrement « complet » exige aucune commande de test posée, ni FINISH_TRAIN_RUNNER ni
        # FINISH_TRAIN_CI. Le train lance donc le vrai chemin par défaut : tests/run_all.sh du dépôt (le runner bidon de la fixture, qui écrit aussi la
        # ligne Mac) et un tools/ci_local.sh réel du worktree d'intégration (un faux commité dans main, comme la sonde par défaut de test_passe_e2e),
        # qui imprime les trois phases vertes et écrit la preuve du conteneur. Aussi strict qu'avant : même assertions, plus la variable du conteneur.
        self.t.commit_main({"tools/ci_local.sh": CI_VERT}, pousser=True)
        self.t.mettre_a_jour_run()
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", extra={"FINISH_TRAIN_RUNNER": None, "FINISH_TRAIN_CI": None}, entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "arbre de main enregistré comme validé (complet)")
        self.absent(r, "commande de test posée : FINISH_TRAIN_RUNNER", "commande de test posée : FINISH_TRAIN_CI")
        arbre = self.t.arbre("main")
        lignes = [l.split("\t") for l in self.t.lignes_validees()]
        self.assertIn([arbre, "complet"], [l[:2] for l in lignes])

    def test_la_ligne_de_main_valide_a_quatre_colonnes_date_utc_et_signature_sans_branche_ni_commit(self):
        # finish-single-b7-b9, B9 (revue 4.7, non bloquant 1, R-20261105-32) : le format de l'enregistrement que le train écrit (déplacé de
        # tools/light_finish.sh dans tools/finish_env.sh) n'était plus testé depuis le retrait de la suite de la fin unitaire : quatre colonnes
        # (arbre, genre, date UTC, signature de 64 caractères hexadécimaux ou « inconnue »), ni branche, ni commit
        import re
        self.t.commit_main({"tools/ci_local.sh": CI_VERT}, pousser=True)
        self.t.mettre_a_jour_run()
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", extra={"FINISH_TRAIN_RUNNER": None, "FINISH_TRAIN_CI": None}, entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        arbre = self.t.arbre("main")
        lignes = [l for l in self.t.lignes_validees() if l.split("\t")[0] == arbre]
        self.assertEqual(len(lignes), 1, self.t.lignes_validees())
        colonnes = lignes[0].split("\t")
        self.assertEqual(len(colonnes), 4, lignes[0])
        self.assertEqual(colonnes[1], "complet")
        self.assertRegex(colonnes[2], r"^\d{4}-\d{2}-\d{2}$")
        self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", colonnes[3]) or colonnes[3] == "inconnue", colonnes[3])
        self.assertNotIn("feat/x", lignes[0])
        self.assertNotIn(self.t.git("rev-parse", "main"), lignes[0])

    def une_substitution_ne_fabrique_aucune_preuve(self, extra, phrase_posee, ci_reel):
        # Q233 (a), R-20261101-118 (principe de D8) : une variable de substitution ne fabrique jamais une preuve. Posée, ni l'empreinte
        # pmzilla-run-all-ok de l'espace de travail ni l'enregistrement « complet » de main n'existent ; la ligne dit pourquoi.
        if ci_reel:   # la substitution est celle du runner : le conteneur est le vrai chemin par défaut (un faux tools/ci_local.sh commité dans main)
            self.t.commit_main({"tools/ci_local.sh": CI_VERT}, pousser=True)
            self.t.mettre_a_jour_run()
        self.t.branche("feat/x")
        self.assertFalse(self.t.fichier_empreinte().exists(), "précondition : aucune empreinte de l'espace de travail avant le train")
        r = self.t.lance("feat/x", extra=extra, entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, phrase_posee, "empreinte de l'espace de travail non écrite (commande de test posée)")
        self.absent(r, "empreinte de l'espace de travail écrite pour l'arbre testé", "arbre de main enregistré comme validé (complet)")
        self.assertFalse(self.t.fichier_empreinte().exists(), "pmzilla-run-all-ok de l'espace de travail a été fabriquée par une substitution")
        self.assertEqual(self.t.lignes_validees(), [], "main a été enregistré « complet » malgré une substitution")

    def test_ci_remplace_aucune_empreinte_ni_enregistrement_complet(self):
        self.une_substitution_ne_fabrique_aucune_preuve({"FINISH_TRAIN_RUNNER": None}, "commande de test posée : FINISH_TRAIN_CI", ci_reel=False)

    def test_runner_remplace_aucune_empreinte_ni_enregistrement_complet(self):
        self.une_substitution_ne_fabrique_aucune_preuve({"FINISH_TRAIN_CI": None}, "commande de test posée : FINISH_TRAIN_RUNNER", ci_reel=True)

    def test_main_non_enregistre_quand_le_runner_est_remplace(self):
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "commande de test posée : FINISH_TRAIN_RUNNER", "arbre de main non enregistré (runner remplacé)")
        self.assertEqual(self.t.lignes_validees(), [])


if __name__ == "__main__":
    unittest.main()
