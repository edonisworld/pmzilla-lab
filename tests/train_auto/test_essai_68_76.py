"""
Faux 65 du train automatique (design D3, D5 ; tooling-autonomous-trains) : un essai qui sort en 68 (contrôle de contenu impossible) ou en 76 (calcul
impossible, dont `python3` 3.10 ou plus introuvable) est journalisé avec son code et n'arme aucun arrêt ; le 65 l'arme toujours. Le faux finish_train.sh
est celui de la suite (jamais le vrai script de fin).

    bash tests/run_all.sh train_auto
"""
from aide_fusion import AvecFusion


class EssaiSansArret(AvecFusion):
    def test_un_essai_en_68_n_arme_aucun_arret(self):
        r = self.passage_fusion("feat/x", extra={"FAUX_CODE_ESSAI": "68"})
        self.assertFalse((self.dossier_train() / "arret").exists())
        self.assertIsNone(self.dernier()["arret_arme"])
        self.assertEqual(self.dernier()["essai"]["code"], 68)
        self.assertNotIn("arrêt armé après le code 68", r.sortie)

    def test_un_essai_en_76_n_arme_aucun_arret(self):
        r = self.passage_fusion("feat/x", extra={"FAUX_CODE_ESSAI": "76"})
        self.assertFalse((self.dossier_train() / "arret").exists())
        self.assertIsNone(self.dernier()["arret_arme"])
        self.assertEqual(self.dernier()["essai"]["code"], 76)
        self.assertNotIn("arrêt armé après le code 76", r.sortie)

    def test_le_passage_suivant_n_est_pas_arrete_par_un_76(self):
        self.passage_fusion("feat/x", extra={"FAUX_CODE_ESSAI": "76"})
        self.passage_fusion("feat/x", extra={"FAUX_CODE_ESSAI": "76"})
        self.assertEqual(len(self.passages()), 2)
        self.assertNotIn("arrete", [p["decision"] for p in self.passages()])

    def test_un_essai_en_65_arme_toujours_l_arret(self):
        r = self.passage_fusion("feat/x", extra={"FAUX_CODE_ESSAI": "65"})
        self.assertTrue((self.dossier_train() / "arret").exists())
        self.assertEqual(self.dernier()["arret_arme"], 65)
        self.assertIn("train_auto : arrêt armé après le code 65", r.sortie)
