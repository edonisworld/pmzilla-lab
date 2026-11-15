"""
finish-single-b3-b6, B6 (design D20) : un main local strictement en retard sur origin/main est avancé en avance rapide, après le fetch et avant la
détection de l'état des références ; un échec de cette avance rapide donne 63 sans rien changer ; un main divergent ou en avance garde le traitement
d'avant. Dépôts jetables réels : aucune avance rapide n'est simulée (l'échec est un vrai verrou d'index dans l'espace de travail).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "finish_train"))   # l'aide commune est dans tests/finish_train
from aide_train import AvecTrain  # noqa: E402


class AvanceRapide(AvecTrain):
    def pousse_ailleurs(self, fichier="tools/ailleurs.sh"):
        autre = self.t.cloner_ailleurs()
        nouveau = self.t.valider(autre, {fichier: "a\n"}, "poussé ailleurs")
        self.t.git("push", "-q", "origin", "main", cwd=autre)
        return nouveau

    def test_main_en_retard_est_avance_et_l_espace_de_travail_est_mis_a_jour(self):
        self.t.branche("feat/x")
        ancien = self.t.main()
        nouveau = self.pousse_ailleurs()
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, f"finish_train : main local en retard avancé sur origin/main : {ancien[:12]} -> {nouveau[:12]}")
        self.assertEqual(self.t.main(), nouveau)
        self.assertEqual(self.t.git("status", "--porcelain"), "")
        self.assertTrue((self.t.contenu / "tools" / "ailleurs.sh").is_file())
        self.contient(r, f"base origin/main {nouveau[:12]}")

    def test_l_avance_rapide_precede_la_detection_de_l_etat_et_le_train_fusionne_sur_le_nouveau_main(self):
        self.t.branche("feat/x")
        ancien = self.t.main()
        nouveau = self.pousse_ailleurs()
        r = self.t.lance("feat/x", entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.assertLess(r.texte.index("main local en retard avancé"), r.texte.index("train : 1 branche(s)"))
        self.assertEqual(self.t.main(), self.t.origin_main())
        self.assertEqual(self.t.git("rev-list", "--count", f"{nouveau}..main"), "2")
        self.assertNotEqual(self.t.main(), ancien)

    def test_une_avance_rapide_en_echec_donne_63_et_main_reste_ou_il_etait(self):
        # un vrai verrou d'index : « git merge --ff-only » ne peut pas écrire l'index ; l'état propre se lit sans lui
        self.t.branche("feat/x")
        ancien = self.t.main()
        self.pousse_ailleurs()
        (self.t.contenu / ".git" / "index.lock").write_text("", encoding="utf-8")
        r = self.t.lance("feat/x")
        self.code(r, 63, "base non établie : avance rapide de main local en échec ; rien n'est fusionné")
        self.assertEqual(self.t.main(), ancien)
        self.contient(r, "===== arrêt à ")

    def test_un_non_suivi_sous_bmad_output_au_chemin_d_un_fichier_de_la_base_donne_64_avant_l_avance(self):
        # R-20261102-37 (Q313) : l'exception de R-20261102-6 laisse passer le lancement, mais l'avance rapide échouerait ; refus 64 avant, chemins nommés
        self.t.branche("feat/x")
        ancien = self.t.main()
        self.pousse_ailleurs("_bmad-output/pmzilla/livrable.md")
        (self.t.contenu / "_bmad-output" / "pmzilla").mkdir(parents=True)
        (self.t.contenu / "_bmad-output" / "pmzilla" / "livrable.md").write_text("local\n", encoding="utf-8")
        r = self.t.lance("feat/x")
        self.code(r, 64, "fichier non suivi de l'espace de travail au chemin d'un fichier du train : 1 ; le retirer de l'espace de travail puis relancer")
        self.contient(r, "\n_bmad-output/pmzilla/livrable.md\n")   # chemin seul sur sa ligne, comme les chemins en conflit (test_construction)
        self.assertEqual(self.t.main(), ancien)

    def test_un_non_suivi_sous_bmad_output_au_chemin_d_un_fichier_du_train_donne_64_aussi_en_essai(self):
        # R-20261102-37 (Q313) : contrôle juste après la construction du train, avant le runner, y compris en --essai
        self.t.branche("feat/x", {"_bmad-output/pmzilla/livrable.md": "branche\n"})
        (self.t.contenu / "_bmad-output" / "pmzilla").mkdir(parents=True)
        (self.t.contenu / "_bmad-output" / "pmzilla" / "livrable.md").write_text("local\n", encoding="utf-8")
        r = self.t.lance("--essai", "feat/x")
        self.code(r, 64, "fichier non suivi de l'espace de travail au chemin d'un fichier du train : 1 ; le retirer de l'espace de travail puis relancer")
        self.contient(r, "\n_bmad-output/pmzilla/livrable.md\n")

    def test_un_espace_de_travail_qui_a_change_entre_le_lancement_et_l_avance_donne_63(self):
        # revue de B6, C3 : « sur main et propre » est revérifié juste avant l'avance. Faux déclaré : la commande de garde du matin (FINISH_TRAIN_MORNING_CHECK,
        # lancée entre le lancement et l'avance) change l'espace de travail ; risque non couvert : une vraie concurrence, jamais rejouable
        self.t.branche("feat/x")
        ancien = self.t.main()
        self.pousse_ailleurs()
        sale = f"echo x > {self.t.contenu}/sale-tard.txt"
        r = self.t.lance("feat/x", extra={"FINISH_TRAIN_MORNING_CHECK": sale})
        self.code(r, 63, "base non établie : avance rapide de main local en échec ; rien n'est fusionné")
        self.assertEqual(self.t.main(), ancien)

    def test_une_autre_branche_courante_entre_le_lancement_et_l_avance_n_est_jamais_avancee(self):
        self.t.branche("feat/x")
        ancien = self.t.main()
        self.pousse_ailleurs()
        autre = f"git -C {self.t.contenu} checkout -q -b autre"
        r = self.t.lance("feat/x", extra={"FINISH_TRAIN_MORNING_CHECK": autre})
        self.code(r, 63, "base non établie : avance rapide de main local en échec ; rien n'est fusionné")
        self.assertEqual(self.t.main(), ancien)
        self.assertEqual(self.t.rev("refs/heads/autre"), ancien)

    def test_l_avance_rapide_puis_la_reprise_s2_est_un_enchainement_accepte(self):
        # revue de B6, Q3 (a) de l'auteur : si origin/main porte déjà ce train (poussé d'ailleurs), l'avance d'un main en retard mène à l'état S2
        # et au nettoyage ; l'enchaînement est figé
        self.t.branche("feat/x")
        train = self.t.construire_train(["feat/x"])
        self.t.git("push", "-q", "origin", f"{train}:refs/heads/main")
        r = self.t.lance("feat/x", entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "main local en retard avancé sur origin/main", "reprise : le train est déjà poussé")
        self.assertLess(r.texte.index("main local en retard avancé"), r.texte.index("reprise : le train est déjà poussé"))
        self.assertEqual(self.t.main(), train)

    def test_main_en_avance_garde_le_63_d_avant(self):
        self.t.branche("feat/x")
        local = self.t.commit_main({"tools/avance.sh": "a\n"}, "avance locale")
        r = self.t.lance("feat/x")
        self.assertEqual(r.code, 63, r.texte)
        self.absent(r, "main local en retard avancé")
        self.assertEqual(self.t.main(), local)

    def test_main_divergent_garde_le_63_d_avant_sans_avance_rapide(self):
        self.t.branche("feat/x")
        local = self.t.commit_main({"tools/avance.sh": "a\n"}, "avance locale")
        self.pousse_ailleurs()
        r = self.t.lance("feat/x")
        self.assertEqual(r.code, 63, r.texte)
        self.absent(r, "main local en retard avancé")
        self.assertEqual(self.t.main(), local)

    def test_un_main_egal_a_origin_main_n_annonce_aucune_avance(self):
        self.t.branche("feat/x")
        r = self.t.lance("--essai", "feat/x")
        self.assertEqual(r.code, 0, r.texte)
        self.absent(r, "main local en retard avancé")

    def test_main_en_retard_jamais_un_etat_de_reprise(self):
        # le train déjà fusionné dans main local (S1) reste une reprise ; un main en retard n'en est jamais une, même si une branche y figure
        x, y = self.deux_branches()
        self.t.etat_fusionne_localement(x, y)
        r = self.t.lance(x, y, entree="o\n")
        self.assertEqual(r.code, 0, r.texte)
        self.contient(r, "reprise : main porte déjà le train")
        self.absent(r, "main local en retard avancé")


if __name__ == "__main__":
    unittest.main()
