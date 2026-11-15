"""
Tâche 2.3 (change finish-train-v1) : le verrou de fin (conception D3, codes 66 et 67) et le garde-fou du matin, au départ et juste avant que main
bouge. Le verrou est libéré à chaque sortie : refus, succès, interruption.
"""
import os
import signal
import unittest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "finish_train"))   # l'aide commune est dans tests/finish_train
from aide_train import AvecTrain  # noqa: E402


class Verrou(AvecTrain):
    def test_verrou_tenu_par_un_autre_refus_immediat_sans_rien_changer(self):
        self.t.branche("feat/x")
        verrou = self.t.verrou_etranger("feat/autre")
        avant = self.t.instantane()
        fichiers = {f.name: f.read_text(encoding="utf-8") for f in verrou.iterdir()}
        r = self.t.lance("feat/x")
        self.code(r, 67, "une autre fin de branche est en cours (feat/autre, depuis ")
        self.rien_ne_change(avant)
        self.assertEqual({f.name: f.read_text(encoding="utf-8") for f in verrou.iterdir()}, fichiers)
        self.assertEqual(self.t.appels("runner"), [])
        self.assertEqual(self.t.appels("garde-du-matin"), [])

    def test_verrou_libere_apres_un_refus(self):
        # branche absente : refus à l'admission (62), le verrou a été pris puis libéré
        r = self.t.lance("feat/fantome")
        self.code(r, 62)
        self.assertFalse((self.t.commun() / "pmzilla-fin-en-cours").exists())

    def test_verrou_libere_apres_un_succes(self):
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.assertFalse((self.t.commun() / "pmzilla-fin-en-cours").exists())

    def test_verrou_libere_apres_une_interruption(self):
        self.t.branche("feat/x")
        proc = self.t.demarre("feat/x", extra={"FAKE_RUNNER_MODE": "dort"})
        self.t.attend_fichier("runner-demarre")
        os.killpg(proc.pid, signal.SIGINT)
        self.t.reveille()
        code, _ = self.t.termine(proc)
        self.assertEqual(code, 130)
        self.assertFalse((self.t.commun() / "pmzilla-fin-en-cours").exists())

    def test_le_verrou_pris_porte_le_jeton_du_script_et_le_runner_le_recoit(self):
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        env = (self.t.etat / "env-runner.txt").read_text(encoding="utf-8")
        self.assertIn("FINISH_LOCK_TOKEN=", env)

    def test_le_champ_branche_du_verrou_est_train_pendant_le_runner(self):
        self.t.branche("feat/x")
        proc = self.t.demarre("feat/x", extra={"FAKE_RUNNER_MODE": "dort"})
        self.t.attend_fichier("runner-demarre")
        champ = (self.t.commun() / "pmzilla-fin-en-cours" / "branche").read_text(encoding="utf-8").strip()
        os.killpg(proc.pid, signal.SIGINT)
        self.t.reveille()
        self.t.termine(proc)
        self.assertEqual(champ, "train")


class CrochetReferenceTransaction(AvecTrain):
    """Constat M-8 de la revue de u5 : la fixture installe le vrai crochet reference-transaction (u13) et le module du verrou ; l'avance rapide de main
    passe avec le jeton du script et est refusée quand le verrou vivant porte le jeton d'un autre (D13, D17)."""

    def test_le_crochet_et_le_module_du_verrou_sont_dans_main_du_depot_jetable(self):
        self.assertEqual(self.t.git("ls-files", "tools/hooks/reference-transaction", "tools/finish_lock.py"),
                         "tools/finish_lock.py\ntools/hooks/reference-transaction")
        self.assertTrue((self.t.crochets / "reference-transaction").is_file())

    def test_l_avance_rapide_passe_avec_le_jeton_du_verrou_tenu_par_le_script(self):
        self.t.branche("feat/x")
        debut = self.t.main()
        r = self.t.lance("feat/x", entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.assertNotEqual(self.t.main(), debut)
        self.assertEqual(self.t.main(), self.t.distant_main())
        self.absent(r, "mise à jour de main refusée")

    def test_l_avance_rapide_est_refusee_quand_le_verrou_vivant_est_a_un_autre_jeton(self):
        self.t.branche("feat/x")
        debut = self.t.main()
        distant = self.t.distant_main()
        r = self.t.lance("feat/x", extra={"FAKE_RUNNER_JETON_AUTRE": "1"}, entree="o\n")
        self.code(r, 73, f"avance rapide de main en échec, main inchangé ({debut[:12]}) ; rien n'est fusionné")
        self.assertEqual(self.t.main(), debut)
        self.assertEqual(self.t.distant_main(), distant)
        self.assertEqual(self.t.origin_main(), distant)


class GardeDuMatin(AvecTrain):
    def test_refus_au_depart(self):
        self.t.branche("feat/x")
        avant = self.t.instantane()
        r = self.t.lance("feat/x", extra={"FAKE_MORNING_MODE": "refuse"})
        # R-20261102-3 et R-20261102-5, réécrit (phrases de D4, même rigueur) : 66 seulement tant que la veille ou la sauvegarde tournent
        self.code(r, 66, "veille ou sauvegarde du jour en cours", "relancer la même ligne quand la veille et la sauvegarde sont finies")
        self.absent(r, "fenêtre du matin", "état du matin")
        self.contient(r, "morning_state : refusé (faux garde-fou)", "commande de test posée : FINISH_TRAIN_MORNING_CHECK")
        self.rien_ne_change(avant)
        self.assertEqual(self.t.appels("runner"), [])

    def test_autorise_au_depart_refuse_avant_l_avance_rapide(self):
        self.t.branche("feat/x")
        main = self.t.main()
        r = self.t.lance("feat/x", extra={"FAKE_MORNING_MODE": "refuse_des_le_second"}, entree="o\n")
        self.code(r, 66, "veille ou sauvegarde du jour en cours")   # R-20261102-3 et R-20261102-5, réécrit (phrase de D4)
        self.assertEqual(self.t.appels("garde-du-matin"), ["garde-du-matin appel 1", "garde-du-matin appel 2"])
        self.assertEqual(self.t.main(), main)
        self.assertEqual(self.t.distant_main(), main)
        self.assertEqual(self.t.origin_main(), main)
        self.assertEqual(self.t.worktrees_train(), [])
        self.assertIsNone(self.t.empreinte(), "aucune empreinte de l'espace de travail avant l'avance rapide")

    def test_avertissement_seul_le_train_continue_sans_66(self):
        # R-20261102-3 et R-20261102-5 (scénario « Warnings only » de tooling-finish-train) : garde à 0 avec une ligne d'avertissement
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", extra={"FAKE_MORNING_MODE": "permet_avertit"}, entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.absent(r, "veille ou sauvegarde du jour en cours", "relancer la même ligne quand la veille")
        self.assertGreaterEqual(len(self.t.appels("garde-du-matin")), 2, "la garde est lue aux deux contrôles")

    def test_refus_66_n_imprime_que_la_premiere_ligne_du_garde(self):
        # R-20261102-3 et R-20261102-5 : comme finish_branch, une seule ligne du garde (pas ses avertissements)
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", extra={"FAKE_MORNING_MODE": "refuse_avec_avertissement"})
        self.code(r, 66, "veille ou sauvegarde du jour en cours")
        self.contient(r, "morning_state : refusé (faux garde-fou)")
        self.absent(r, "avertissement : deuxième ligne")

    def test_aucune_variable_n_ecarte_le_refus(self):
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", extra={"FAKE_MORNING_MODE": "refuse", "PMZILLA_SKIP_GREEN_CHECK": "1", "FINISH_BRANCH_FORCE_RUN": "1"})
        self.code(r, 66)


if __name__ == "__main__":
    unittest.main()
