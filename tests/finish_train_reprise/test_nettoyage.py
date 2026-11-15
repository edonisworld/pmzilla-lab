"""
Tâche 2.10 (change finish-train-v1) : le nettoyage, la vérification finale et la mise à jour du dossier d'exécution (conception D14, D15 et D2 ;
codes 0 et 75). Rien n'est jamais forcé ni élagué ; avant chaque retrait, fichiers ignorés et processus sont revérifiés ; la mise à jour du dossier
d'exécution est la dernière action, et le script qui tourne ne change pas quand sa copie est remplacée pendant la mise à jour.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "finish_train"))   # l'aide commune est dans tests/finish_train
from aide_train import AvecTrain  # noqa: E402


class Retraits(AvecTrain):
    def test_worktrees_retires_sans_force_dans_l_ordre(self):
        x, y = self.deux_branches()
        r = self.t.lance(x, y, entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        for nom in (x, y):
            self.assertFalse(self.t.dossier_worktree(nom).exists())
        self.assertEqual(self.t.worktrees_train(), [])
        lignes = re.findall(r"worktree retiré : (\S+)", r.texte)
        self.assertEqual(lignes[:2], [str(self.t.dossier_worktree(x)), str(self.t.dossier_worktree(y))], "les branches dans l'ordre de la liste")
        self.assertIn("/wt-train-", lignes[2], "puis le worktree d'intégration")
        for ligne in self.t.journal_git():
            if "worktree remove" in ligne:
                self.assertNotIn("--force", ligne)
                self.assertNotRegex(ligne, r" -f( |$)")
            self.assertNotIn("worktree prune", ligne)
            self.assertFalse(ligne.startswith("reset"), ligne)

    def test_branches_supprimees_par_git_branch_d_seulement(self):
        x, y = self.deux_branches()
        r = self.t.lance(x, y, entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "branche supprimée : feat/x", "branche supprimée : feat/y")
        suppressions = []
        for ligne in self.t.journal_git():
            m = re.search(r"(?:^|\s)branch\s+(-[dD]|--delete(?:\s+--force)?)\s+(\S+)$", ligne)
            if m:
                suppressions.append((m.group(1), m.group(2)))
        self.assertEqual(sorted(suppressions), [("-d", "feat/x"), ("-d", "feat/y")])
        self.assertEqual(self.t.git("branch", "--list", "feat/*"), "")

    def test_branche_distante_du_meme_nom_supprimee(self):
        x, y = self.deux_branches()
        self.t.git("push", "-q", "origin", x)
        r = self.t.lance(x, y, entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "branche distante supprimée : feat/x")
        self.absent(r, "branche distante supprimée : feat/y")
        self.assertEqual(self.t.git("ls-remote", "--heads", str(self.t.distant), x), "")

    def test_branche_distante_dont_le_sommet_n_est_pas_dans_main_est_gardee(self):
        # revue de u5, m-11 : un commit poussé ailleurs sur la branche distante ne se perd jamais
        x, y = self.deux_branches()
        self.t.git("push", "-q", "origin", x)
        autre = self.t.cloner_ailleurs()
        self.t.git("checkout", "-q", x, cwd=autre)
        self.t.valider(autre, {"tools/plus.sh": "p\n"}, "poussé ailleurs sur la branche")
        self.t.git("push", "-q", "origin", x, cwd=autre)
        r = self.t.lance(x, y, entree="o\n")
        self.assertEqual(r.code, 75, r.texte)
        self.contient(r, "branche gardée : feat/x : branche distante pas contenue dans main")
        self.absent(r, "branche distante supprimée : feat/x")
        self.assertNotEqual(self.t.git("ls-remote", "--heads", str(self.t.distant), x), "")

    def test_verification_finale_main_est_le_sommet_du_train(self):
        # revue de u5, m-10 : un main déplacé pendant le nettoyage est signalé par la vérification finale
        x, y = self.deux_branches()
        r = self.t.lance(x, y, extra={"FAKE_MAIN_APRES_BRANCH_D": "1"}, entree="o\n")
        self.assertEqual(r.code, 75, r.texte)
        self.contient(r, "vérification finale : main local n'est pas le sommet du train")

    def test_verification_finale_et_ligne_de_fin(self):
        x, y = self.deux_branches()
        ancien = self.t.main()
        r = self.t.lance(x, y, entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(self.t.git("branch", "--show-current"), "main")
        self.assertEqual(self.t.git("status", "--porcelain"), "")
        self.assertFalse((self.t.commun() / "MERGE_HEAD").exists())
        self.assertEqual(self.t.main(), self.t.origin_main())
        self.assertEqual(self.t.main(), self.t.distant_main())
        self.contient(r, f"terminé : main {ancien[:12]} -> {self.t.main()[:12]}, 2 branche(s)")


class Gardes(AvecTrain):
    def test_fichier_ignore_ecrit_apres_l_admission(self):
        x, y = self.deux_branches()
        wt = self.t.dossier_worktree(x)
        r = self.t.lance(x, y, extra={"FAKE_RUNNER_IGNORE_DANS": str(wt)}, entree="o\n")
        self.assertEqual(r.code, 75, r.texte)
        self.contient(r, "train fusionné et poussé, fin incomplète :", f"worktree gardé : {wt} : fichiers ignorés qui seraient perdus (1)",
                      "branche gardée : feat/x : ")
        self.absent(r, "ecrit-apres")
        self.assertTrue(wt.exists())
        self.assertNotEqual(self.t.git("branch", "--list", x), "")
        self.assertFalse(self.t.dossier_worktree(y).exists(), "l'autre branche est nettoyée")
        self.assertEqual(self.t.git("branch", "--list", y), "")
        self.assertEqual(self.t.main(), self.t.distant_main(), "le train est poussé")

    def test_processus_dans_un_worktree_au_nettoyage(self):
        x, y = self.deux_branches()
        wt = self.t.dossier_worktree(x)
        r = self.t.lance(x, y, extra={"FAKE_RUNNER_PROCESSUS_DANS": str(wt)}, entree="o\n")
        self.assertEqual(r.code, 75, r.texte)
        pid = (self.t.etat / "pid-sleep").read_text(encoding="utf-8").strip()
        self.contient(r, f"worktree gardé : {wt} : processus dans le worktree ({pid} sleep)")
        self.assertTrue(wt.exists())

    def verification_impossible_au_nettoyage(self, mode):
        # décision du 2026-10-27 (D14, D18, tâche 2.19) : le faux lsof répond normalement à l'admission puis, après le push, échoue (« casse ») ou
        # donne une liste qui ne montre pas le script (« sans_moi ») : les worktrees et leurs branches restent, avec le motif, code 75
        x, y = self.deux_branches()
        (self.t.etat / "lsof-mode-apres-push").write_text(mode, encoding="utf-8")
        r = self.t.lance(x, y, entree="o\n")
        self.assertEqual(r.code, 75, r.texte)
        for nom in (x, y):
            wt = self.t.dossier_worktree(nom)
            self.contient(r, f"worktree gardé : {wt} : processus dans le worktree (vérification impossible)")
            self.assertTrue(wt.exists())
            self.assertNotEqual(self.t.git("branch", "--list", nom), "")
        self.assertEqual(self.t.main(), self.t.distant_main(), "le train est poussé")

    def test_verification_des_processus_impossible_au_nettoyage_lsof_en_echec(self):
        self.verification_impossible_au_nettoyage("casse")

    def test_verification_des_processus_impossible_au_nettoyage_liste_sans_le_script(self):
        self.verification_impossible_au_nettoyage("sans_moi")

    def test_fichiers_ignores_exceptions_ne_gardent_pas_le_worktree(self):
        self.t.branche("feat/x")
        wt = self.t.dossier_worktree("feat/x")
        (wt / "__pycache__").mkdir()
        (wt / "__pycache__" / "m.pyc").write_bytes(b"x")
        r = self.t.lance("feat/x", entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.assertFalse(wt.exists())


class MiseAJourDuDossierDExecution(AvecTrain):
    def test_une_fois_et_en_dernier(self):
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.assertEqual(len(self.t.appels("update appelé")), 1)
        self.assertEqual(self.t.git("rev-parse", "HEAD", cwd=self.t.run), self.t.main())
        self.assertLess(r.texte.index("branche supprimée"), r.texte.index("dossier d'exécution mis à jour"))
        self.assertLess(r.texte.index("dossier d'exécution mis à jour"), r.texte.index("terminé : main "))
        journal = self.t.journal_git()
        self.assertEqual(journal[-1], "### update", "aucune commande Git après la mise à jour du dossier d'exécution")

    def test_dossier_d_execution_absent_est_une_information(self):
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", extra={"FAKE_RUN_UPDATE": "absent"}, entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "dossier d'exécution absent, rien à mettre à jour")

    def test_sortie_7_ajoute_une_cause_au_75(self):
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", extra={"FAKE_RUN_UPDATE": "echec"}, entree="o\n")
        self.assertEqual(r.code, 75, r.texte)
        self.contient(r, "train fusionné et poussé, fin incomplète :", "dossier d'exécution non mis à jour",
                      "Pour le mettre à jour : bash tools/run_worktree.sh update")
        self.assertEqual(self.t.main(), self.t.distant_main())

    def test_la_copie_du_script_remplacee_pendant_la_mise_a_jour_ne_change_pas_la_fin(self):
        self.t.branche("feat/x")
        r = self.t.lance("feat/x", extra={"FAKE_RUN_UPDATE": "remplace"}, entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "terminé : main ")
        self.absent(r, "SCRIPT-REMPLACE")
        self.assertRegex(self.t.log().splitlines()[-1], r"^===== fin du train : code 0 \(fusionné\), .* Paris =====$")
        self.assertIn("SCRIPT-REMPLACE", (self.t.run / "tools" / "finish_train.sh").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
