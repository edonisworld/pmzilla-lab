"""Change train-auto-launchd-env, D8 : l'arrêt du train automatique ouvre le résumé du matin (ligne juste après le titre, même ligne dans la notification,
clé JSON `train_stop` pendant l'arrêt seulement), lu par `train_auto.stop_info()` seul. Les codes de sortie ne changent pas.
Remplace : rien. Retrait : avec le passage automatique (R-166).
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide import Labo  # noqa: E402

FR_ARRETE = "Train automatique arrêté depuis 2026-11-07 21:04, raison 65"
EN_ARRETE = "Automatic train stopped since 2026-11-07 21:04, reason 65"


FR_ILLISIBLE = "Train automatique arrêté (date et raison illisibles)"
EN_ILLISIBLE = "Automatic train stopped (date and reason unreadable)"


class ArretDuTrain(Labo):
    def arreter(self, raison="65", paris="2026-11-07 21:04", enregistrement=True):
        dossier = self.donnees / "train-auto"      # le dossier du train automatique, où stop_info() lit
        dossier.mkdir(exist_ok=True)
        (dossier / "arret").write_text("", encoding="utf-8")
        if enregistrement:
            r = {"type": "arret", "paris": paris}
            if raison is not None:
                r["raison"] = raison
            (dossier / "journal.jsonl").write_text(json.dumps(r) + "\n", encoding="utf-8")

    def lignes(self, *argv):
        code, sortie, erreur = self.lancer(*argv)
        self.assertEqual(code, 0)
        self.assertNotIn("Traceback", sortie + erreur)
        return sortie.splitlines()

    def test_la_ligne_suit_le_titre_en_francais(self):
        self.arreter()
        lignes = self.lignes()
        self.assertEqual(lignes[1], FR_ARRETE)
        self.assertEqual(len(lignes), 6)

    def test_la_ligne_suit_le_titre_en_anglais(self):
        self.arreter()
        self.assertEqual(self.lignes("--language", "en")[1], EN_ARRETE)

    def test_raison_nulle(self):
        self.arreter(raison=None)
        self.assertEqual(self.lignes()[1], "Train automatique arrêté depuis 2026-11-07 21:04, raison non donnée")
        self.assertEqual(self.lignes("--language", "en")[1], "Automatic train stopped since 2026-11-07 21:04, reason not given")

    def test_forme_illisible(self):
        self.arreter(enregistrement=False)
        self.assertEqual(self.lignes()[1], "Train automatique arrêté (date et raison illisibles)")
        self.assertEqual(self.lignes("--language", "en")[1], "Automatic train stopped (date and reason unreadable)")

    def test_raison_avec_barre_oblique_donne_la_forme_illisible(self):
        self.arreter(raison="/Users/x/journal")
        self.assertEqual(self.lignes()[1], FR_ILLISIBLE)
        self.assertEqual(self.lignes("--language", "en")[1], EN_ILLISIBLE)
        self.assertEqual(json.loads(self.lancer("--json")[1])["train_stop"], {"state": "unreadable", "date": None, "reason": None})
        self.tout_connu()
        self.lancer_planifie()
        [appel] = self.notifications()
        self.assertTrue(appel[-1].startswith(FR_ILLISIBLE + " ; "), appel[-1])
        self.assertNotIn("/", appel[-1])

    def test_raison_avec_saut_de_ligne_donne_la_forme_illisible(self):
        self.arreter(raison="65\nligne en trop")
        lignes = self.lignes()
        self.assertEqual(lignes[1], FR_ILLISIBLE)
        self.assertEqual(len(lignes), 6)
        self.assertNotIn("en trop", "\n".join(lignes))
        self.assertEqual(json.loads(self.lancer("--json")[1])["train_stop"], {"state": "unreadable", "date": None, "reason": None})

    def test_raisons_permises(self):
        for raison in ("65", "manuel"):
            with self.subTest(raison=raison):
                self.arreter(raison=raison)
                self.assertEqual(self.lignes()[1], "Train automatique arrêté depuis 2026-11-07 21:04, raison " + raison)

    def test_sans_arret_ni_ligne_ni_cle(self):
        for argv in ((), ("--language", "en")):
            with self.subTest(argv=argv):
                lignes = self.lignes(*argv)
                self.assertEqual(len(lignes), 5)
                self.assertFalse([l for l in lignes if l.startswith("Train automatique") or l.startswith("Automatic train")])
        self.assertNotIn("train_stop", json.loads(self.lancer("--json")[1]))

    def test_json_pendant_l_arret(self):
        self.arreter()
        self.assertEqual(json.loads(self.lancer("--json")[1])["train_stop"], {"state": "stopped", "date": "2026-11-07 21:04", "reason": "65"})

    def test_json_illisible(self):
        self.arreter(enregistrement=False)
        self.assertEqual(json.loads(self.lancer("--json")[1])["train_stop"], {"state": "unreadable", "date": None, "reason": None})

    def test_stop_info_inconnu_ou_import_impossible(self):
        inconnu = {"format": 1, "state": "inconnu", "date": None, "raison": None}
        with mock.patch("train_auto.stop_info", return_value=inconnu):
            lignes = self.lignes()
            self.assertEqual(len(lignes), 5)
            self.assertEqual(json.loads(self.lancer("--json")[1])["train_stop"], {"state": "unknown"})
        with mock.patch.dict(sys.modules, {"train_auto": None}):
            lignes = self.lignes()
            self.assertEqual(len(lignes), 5)
            self.assertEqual(json.loads(self.lancer("--json")[1])["train_stop"], {"state": "unknown"})

    def test_stop_info_qui_leve_est_inconnu(self):
        with mock.patch("train_auto.stop_info", side_effect=RuntimeError("secret")):
            code, sortie, erreur = self.lancer()
            self.assertEqual(code, 0)
            self.assertEqual(len(sortie.splitlines()), 5)
            self.assertNotIn("secret", sortie + erreur)

    def test_aucun_chemin_dans_la_ligne(self):
        self.arreter()
        self.assertNotIn(str(self.donnees), "\n".join(self.lignes()))

    def test_la_notification_commence_par_la_ligne(self):
        self.tout_connu()
        self.arreter()
        code, _, _ = self.lancer_planifie()
        self.assertEqual(code, 0)
        [appel] = self.notifications()
        self.assertTrue(appel[-1].startswith(FR_ARRETE + " ; "), appel[-1])
        self.assertNotIn("/", appel[-1])

    def test_la_notification_anglaise(self):
        self.tout_connu()
        self.arreter()
        self.lancer_planifie("--language", "en")
        [appel] = self.notifications()
        self.assertTrue(appel[-1].startswith(EN_ARRETE + " ; "), appel[-1])

    def test_arret_et_copies_figees_ensemble(self):
        self.arreter()
        (self.donnees / "outils-figes-en-retard").write_text("a" * 40 + " bash rafraichir.sh\n", encoding="utf-8")
        lignes = self.lignes()
        self.assertEqual(lignes[1], FR_ARRETE)
        self.assertIn("en retard sur main", lignes[-1])
        self.assertEqual(len(lignes), 7)

    def test_codes_de_sortie_inchanges(self):
        self.tout_connu()
        self.arreter()
        self.assertEqual(self.lancer_planifie()[0], 0)
        self.assertEqual(self.lancer_planifie()[0], 3)
        (self.donnees / "resume-du-matin-coupe").write_text("", encoding="utf-8")
        self.assertEqual(self.lancer_planifie()[0], 4)
        (self.donnees / "resume-du-matin-coupe").unlink()
        self.memoire().unlink()
        self.assertEqual(self.lancer_planifie(STUB_EXIT="1")[0], 1)


if __name__ == "__main__":
    unittest.main()
