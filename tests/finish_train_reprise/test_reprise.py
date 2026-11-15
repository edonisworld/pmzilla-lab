"""
Tâche 2.11 (change finish-train-v1) : la reprise à partir de l'état des références seulement (conception D5, code 79 ; décision de l'auteur du
2026-10-26 sur la question ouverte 1). S1 : main local porte le train, rien n'est poussé. S2 : le train est poussé. Tout autre état est refusé sans rien
toucher, après la vérification de pureté de la chaîne.

Lecture retenue pour les codes 63 et 79 (voir le rapport du groupe 2) : main local en avance sur origin/main alors qu'AUCUNE branche de la liste n'y est
fusionnée donne 63 (tâche 2.4) ; main local qui porte, tout ou partie, des fusions de la liste, ou le train plus autre chose, donne 79.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "finish_train"))   # l'aide commune est dans tests/finish_train
from aide_train import AvecTrain, jeton, E2, E3, E4  # noqa: E402

REPRISE_S1 = "reprise : main porte déjà le train des 2 branche(s) (sommet "
REPRISE_S2 = "reprise : le train est déjà poussé ; reprise au nettoyage"
ARRET = "===== arrêt à "


class ReprisePush(AvecTrain):
    def test_apres_un_74_la_relance_ne_fait_que_pousser(self):
        x, y = self.deux_branches()
        self.t.etat_fusionne_localement(x, y)
        runners, dbtests = len(self.t.appels("runner")), len(self.t.appels("dbtest"))
        matin = len(self.t.appels("garde-du-matin"))
        fichier_ci = self.t.etat / "ci-appels"
        ci = fichier_ci.read_text(encoding="utf-8") if fichier_ci.exists() else ""
        empreinte = self.t.fichier_empreinte()
        # réécrit (R-20261101-118, Q233 a) : une commande de test posée n'écrit plus l'empreinte de l'espace de travail ; « aucune empreinte réécrite » se garde
        # telle quelle : l'état du fichier (contenu et date s'il existe, absent sinon) est identique avant et après la reprise
        etat_fp = lambda: (empreinte.read_text(encoding="utf-8"), empreinte.stat().st_mtime_ns) if empreinte.exists() else None   # noqa: E731
        avant_fp = etat_fp()
        sommet = self.t.main()
        r = self.t.lance(x, y)
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, REPRISE_S1 + sommet[:12] + ") ; noms, secrets, contrôles par branche et garde du matin refaits ; reprise au push",
                      "main poussé vers origin", "terminé : main ")
        self.absent(r, "Terminer le train", "construit : sommet", "lancement du runner complet", "passage dbtest requis",
                    "passage du conteneur requis")   # la phrase neuve du contrôle 14 (R-20261101-116) : aussi absente à la reprise
        self.assertEqual((len(self.t.appels("runner")), len(self.t.appels("dbtest"))), (runners, dbtests), "ni runner ni dbtest")
        self.assertEqual(fichier_ci.read_text(encoding="utf-8") if fichier_ci.exists() else "", ci, "ni passage de la CI locale")
        self.assertGreater(len(self.t.appels("garde-du-matin")), matin, "la garde du matin est refaite")
        self.assertEqual(etat_fp(), avant_fp, "aucune empreinte réécrite")
        self.assertIsNone(avant_fp, "précondition (Q233 a) : la commande de test posée n'a pas écrit l'empreinte pendant le train refusé")
        self.assertFalse(empreinte.exists(), "la reprise n'écrit aucune empreinte de l'espace de travail (Q233 a, R-20261101-118)")
        self.assertEqual(self.t.main(), self.t.distant_main())
        self.assertEqual(self.t.main(), sommet)
        self.assertEqual(self.t.appels("prepush-runner"), [])

    def test_la_reprise_est_dans_le_journal(self):
        x, y = self.deux_branches()
        self.t.etat_fusionne_localement(x, y)
        self.t.lance(x, y)
        self.assertIn(REPRISE_S1, self.t.journaux()[-1].read_text(encoding="utf-8"))

    def test_empreinte_manquante_le_crochet_refuse_et_rien_n_est_pousse(self):
        x, y = self.deux_branches()
        self.t.etat_fusionne_localement(x, y)
        ancien = self.t.distant_main()
        # réécrit (R-20261101-118, Q233 a) : l'empreinte n'est plus écrite avec une commande de test posée (missing_ok), et le crochet a la voie du conteneur
        # (D8) : les deux fichiers de cette preuve sont retirés aussi, pour que le crochet n'ait AUCUNE preuve et refuse, comme avant
        self.t.fichier_empreinte().unlink(missing_ok=True)
        (self.t.commun() / "pmzilla-run-mac-ok").unlink(missing_ok=True)
        (self.t.data / "ci" / "preuves").unlink(missing_ok=True)
        r = self.t.lance(x, y)
        self.code(r, 74, "push refusé : le train est fusionné dans main local seulement ; relancer la même ligne pour pousser")
        self.contient(r, "aucune empreinte complète pour l'arbre poussé")
        self.assertEqual(self.t.distant_main(), ancien)
        self.assertIsNone(self.t.empreinte(), "la reprise n'écrit jamais d'empreinte")

    def test_scan_refait_en_reprise(self):
        self.t.branche("feat/x", {"docs/a.txt": f"token = {jeton()}\n"}, suite=[{"docs/a.txt": None}])
        self.t.branche("feat/y")
        self.t.poser_main(self.t.construire_train(["feat/x", "feat/y"]))
        avant = self.t.instantane()
        r = self.t.lance("feat/x", "feat/y")
        self.code(r, 65, "contenu refusé : le contrôle des noms et des secrets a trouvé 1 secret(s)")
        self.rien_ne_change(avant)

    def test_controles_par_branche_refaits_en_reprise(self):
        x, y = self.deux_branches()
        self.t.poser_main(self.t.construire_train([x, y]))
        (self.t.dossier_worktree(y) / "sale.txt").write_text("x\n", encoding="utf-8")
        r = self.t.lance(x, y)
        self.assertEqual(r.code, 62, r.texte)
        self.contient(r, "feat/y : worktree pas propre")

    def test_garde_du_matin_refaite_en_reprise(self):
        x, y = self.deux_branches()
        self.t.poser_main(self.t.construire_train([x, y]))
        r = self.t.lance(x, y, extra={"FAKE_MORNING_MODE": "refuse"})
        self.code(r, 66, "veille ou sauvegarde du jour en cours")   # R-20261102-3 et R-20261102-5, réécrit (phrase de D4, même rigueur)

    def test_chaine_construite_a_la_main_comme_le_script_est_acceptee(self):
        # la vérification de pureté accepte exactement ce que le script construit ; sans empreinte, le crochet arrête ensuite au push
        x, y = self.deux_branches()
        self.t.poser_main(self.t.construire_train([x, y]))
        r = self.t.lance(x, y)
        self.assertEqual(r.code, 74, r.texte)
        self.contient(r, REPRISE_S1)


class ApresLePush(AvecTrain):
    def test_la_relance_ne_fait_que_nettoyer_et_mettre_a_jour_le_dossier_d_execution(self):
        x, y = self.deux_branches()
        self.t.etat_pousse(x, y)
        wt = self.t.dossier_worktree(x)
        (wt / "ecrit-apres.sentinelle").unlink()
        runners, majs = len(self.t.appels("runner")), len(self.t.appels("update appelé"))
        valides = self.t.lignes_validees()
        r = self.t.lance(x, y)
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, REPRISE_S2, f"worktree retiré : {wt}", "branche supprimée : feat/x")
        self.absent(r, "arbre de main enregistré", "non enregistré", "Terminer le train")
        self.assertEqual(self.t.lignes_validees(), valides, "aucune ligne « main validé » dans une reprise")
        self.assertEqual(len(self.t.appels("runner")), runners)
        self.assertEqual(len(self.t.appels("update appelé")), majs + 1)
        self.assertFalse(wt.exists())

    def test_une_branche_deja_supprimee_par_un_nettoyage_precedent_est_acceptee(self):
        x, y = self.deux_branches()
        r = self.t.lance(x, y, extra={"FAKE_RUN_UPDATE": "echec"}, entree="o\n")
        self.assertEqual(r.code, 75, r.texte)
        self.assertEqual(self.t.git("branch", "--list", "feat/*"), "", "les branches ont été supprimées")
        r = self.t.lance(x, y)
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, REPRISE_S2, "dossier d'exécution mis à jour")


class ReprisRefusee(AvecTrain):
    def refuse(self, r, avant):
        self.assertEqual(r.code, 79, r.texte)
        self.contient(r, "reprise refusée : main ", " porte tout ou partie des fusions des branches données sans être le train pur sur origin/main ",
                      " ; rien n'est touché")
        self.rien_ne_change(avant)
        self.assertTrue(f"{ARRET}état des références : références dans aucun état connu ; rien n'est touché =====" in self.t.journaux()[-1].read_text(encoding="utf-8"))

    def test_commit_etranger_sur_main_local(self):
        x, y = self.deux_branches()
        self.t.etat_fusionne_localement(x, y)
        self.t.commit_main({"tools/etranger.sh": "e\n"}, "commit étranger")
        avant = self.t.instantane()
        r = self.t.lance(x, y)
        self.assertIn(f"main {self.t.main()[:12]} ", r.texte)
        self.refuse(r, avant)

    def defaut(self, nom):
        x, y = self.deux_branches()
        self.t.poser_main(self.t.construire_train([x, y], defaut=nom))
        avant = self.t.instantane()
        self.refuse(self.t.lance(x, y), avant)

    def test_commit_du_train_avec_un_troisieme_parent(self):
        self.defaut("troisieme_parent")

    def test_commit_du_train_au_message_change(self):
        self.defaut("message")

    def test_commit_du_train_avec_un_en_tete_en_plus(self):
        self.defaut("entete")

    def test_commit_du_train_sous_une_autre_identite(self):
        self.defaut("identite")

    def test_commit_du_train_dont_l_arbre_n_est_pas_celui_de_merge_tree(self):
        self.defaut("arbre")

    def test_liste_partiellement_fusionnee(self):
        x, y = self.deux_branches()
        self.t.etat_fusionne_localement(x)
        avant = self.t.instantane()
        self.refuse(self.t.lance(x, y), avant)

    def test_branche_deplacee_dans_l_etat_fusionne_localement(self):
        x, y = self.deux_branches()
        self.t.etat_fusionne_localement(x, y)
        self.t.valider(self.t.dossier_worktree(x), {"tools/plus.sh": "p\n"}, "après le train")
        avant = self.t.instantane()
        self.refuse(self.t.lance(x, y), avant)

    def test_train_complet_plus_un_commit_etranger_est_79(self):
        x, y = self.deux_branches()
        self.t.poser_main(self.t.construire_train([x, y]))
        self.t.commit_main({"tools/etranger.sh": "e\n"}, "commit étranger")
        avant = self.t.instantane()
        self.refuse(self.t.lance(x, y), avant)

    def test_le_graphe_decide_jamais_le_message_un_message_sans_sommet_ancetre_n_est_pas_compte(self):
        # décision du 2026-10-27 (D4) : un commit fait à la main avec le message « Merge branch '<b>' » dont le sommet noté n'est pas un ancêtre de
        # main local ne compte pas : main local diffère d'origin/main sans fusion de la liste, donc 63 et non 79
        x, y = self.deux_branches()
        self.t.commit_main({"tools/hasard.sh": "h\n"}, f"Merge branch '{x}'")
        local, distant = self.t.main(), self.t.origin_main()
        r = self.t.lance(x, y)
        self.code(r, 63, f"base non établie : main local {local[:12]} diffère d'origin/main {distant[:12]}")
        self.assertEqual(self.t.main(), local)

    def test_le_graphe_decide_jamais_le_message_un_sommet_ancetre_sans_ce_message_est_compte(self):
        # le sommet noté de la branche est un ancêtre de main local par un commit sans le message « Merge branch » : compté, donc 79
        x, y = self.deux_branches()
        self.t.poser_main(self.t.sommet(x))
        avant = self.t.instantane()
        self.refuse(self.t.lance(x, y), avant)

    def test_chaine_dont_la_fusion_de_controle_ne_sort_pas_en_zero_n_est_pas_le_train(self):
        # revue de u5, m-6 : la vérification de pureté exige que merge-tree sorte en 0 ; le faux Git rend la vraie sortie puis le code 1
        x, y = self.deux_branches()
        self.t.poser_main(self.t.construire_train([x, y]))
        avant = self.t.instantane()
        self.refuse(self.t.lance(x, y, extra={"FAKE_MERGE_TREE_RC_APRES": "1"}), avant)


class PositionDuDossierDExecution(AvecTrain):
    """Décision du 2026-10-27 (D1, D5, D24, tâche 2.16) : en reprise, le dossier d'exécution est accepté sur origin/main (S1) ou sur la base du train
    déjà poussé (S2) ; toute autre position est refusée à la détection de l'état avec l'état réel."""

    def test_s1_dossier_d_execution_sur_origin_main_est_accepte(self):
        x, y = self.deux_branches()
        self.t.etat_fusionne_localement(x, y)
        self.assertNotEqual(self.t.main(), self.t.origin_main())
        self.assertEqual(self.t.git("rev-parse", "HEAD", cwd=self.t.run), self.t.origin_main())
        r = self.t.lance(x, y)
        self.assertEqual(r.code, 0, r.texte)

    def test_s2_dossier_d_execution_sur_la_base_du_train_est_accepte(self):
        x, y = self.deux_branches()
        base = self.t.main()
        self.t.etat_pousse(x, y)
        (self.t.dossier_worktree(x) / "ecrit-apres.sentinelle").unlink()
        self.t.detacher_le_dossier_d_execution(base)
        r = self.t.lance(x, y)
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, REPRISE_S2)

    def refuse_a_la_detection(self, r, etat):
        sha = self.t.git("rev-parse", "HEAD", cwd=self.t.run)
        self.code(r, 61, f"lancement refusé : dossier d'exécution détaché sur {sha[:12]}, ni main local, ni origin/main, ni la base du train déjà poussé")
        self.assertIn(f"===== arrêt à état des références : {etat} =====", r.texte)

    def test_s0_autre_position_donne_l_etat_e2(self):
        x, y = self.deux_branches()
        self.t.detacher_le_dossier_d_execution(self.t.commit_sans_lien())
        self.refuse_a_la_detection(self.t.lance(x, y), E2)

    def test_s1_autre_position_donne_l_etat_e3(self):
        x, y = self.deux_branches()
        self.t.etat_fusionne_localement(x, y)
        self.t.detacher_le_dossier_d_execution(self.t.commit_sans_lien())
        avant_main = self.t.main()
        self.refuse_a_la_detection(self.t.lance(x, y), E3)
        self.assertEqual(self.t.main(), avant_main)

    def test_s2_autre_position_donne_l_etat_e4(self):
        x, y = self.deux_branches()
        self.t.etat_pousse(x, y)
        self.t.detacher_le_dossier_d_execution(self.t.commit_sans_lien())
        self.refuse_a_la_detection(self.t.lance(x, y), E4)


if __name__ == "__main__":
    unittest.main()
