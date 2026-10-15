"""
Fin d'un passage planifié de tools/watch.sh : appel du résumé du matin (change morning-summary, R-50, design D1 et D9, tâche 5.1).

    python3 -m unittest discover -s tests/watch_sh -v

Même mise en place que test_watch_sh.py (faux HOME, faux uv, faux osascript). Le faux uv note l'appel du script du résumé à part
(`appels_resume`), copie le repère du jour tel qu'il est à cet instant, et rend RESUME_CODE (0 par défaut) ; à 0 il note aussi une
notification « osascript résumé du matin » (le vrai script en envoie une). Aucun vrai résumé, aucune vraie notification.
"""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_watch_sh as base  # noqa: E402

FIN_ECHEC_2 = "=== Veille terminée avec 2 étape(s) en échec : collecte, indexation ==="
DEUX_ECHECS = "watch_lab.py collect,pmzilla_lab_library.py index"


class Resume(base.Base):
    # les aides du passage planifié de la classe Rattrapage, empruntées sans reprendre ses tests
    instant = staticmethod(base.Rattrapage.instant)
    planifie = base.Rattrapage.planifie
    manuel = base.Rattrapage.manuel
    ecrire_repere = base.Rattrapage.ecrire_repere
    lire = base.Rattrapage.lire

    def setUp(self):
        super().setUp()
        self.donnees = self.home / ".pmzilla-lab"
        self.fichier_repere = self.donnees / "veille-du-jour.json"
        self.ZONE = base.Rattrapage.ZONE

    def appels_du_resume(self):
        return self.appels_resume.read_text(encoding="utf-8").splitlines() if self.appels_resume.exists() else []

    def notifications_du_resume(self):
        return [n for n in self.notifications if n.startswith("osascript résumé du matin")]

    def notifications_propres(self):
        return [n for n in self.notifications if not n.startswith("osascript résumé du matin")]

    # -- l'appel ------------------------------------------------------------------------------------------------------
    def test_passage_du_calendrier_termine_un_appel_apres_le_repere_final_et_le_tableau_de_bord(self):
        resultat, appels = self.planifie()
        self.assertEqual(resultat.returncode, 0)
        lignes = self.appels_du_resume()
        self.assertEqual(len(lignes), 1)
        chemin = lignes[0].split(" ")[0]
        self.assertEqual(chemin, str(self.home / "PMZilla-Lab" / "morning_summary.py"))        # par le lien du dossier du labo
        self.assertIn("--notify --failed-steps  | NOTIFY=1", lignes[0])                        # étapes vides, variable du planificateur
        repere = json.loads((self.home / "repere-a-l-appel.json").read_text(encoding="utf-8"))
        self.assertEqual((repere["etat"], repere["code"], repere["fin"] != ""), ("termine", 0, True))
        self.assertEqual(appels[-1], "dashboard.py")
        self.assertEqual(self.notifications_propres(), [])
        self.assertEqual(len(self.notifications_du_resume()), 1)             # la seule notification du passage est celle du résumé

    def test_passage_de_rattrapage_meme_appel(self):
        resultat, _ = self.planifie(option="--catch-up")
        self.assertEqual(resultat.returncode, 0)
        self.assertEqual(len(self.appels_du_resume()), 1)
        self.assertIn("NOTIFY=1", self.appels_du_resume()[0])

    def test_passage_repris_apres_interruption_compte_comme_un_autre(self):
        self.ecrire_repere(etat="commence", code=None, reprises=0)
        resultat, _ = self.planifie()
        self.assertEqual(resultat.returncode, 0)
        self.assertEqual(len(self.appels_du_resume()), 1)

    def test_echec_avec_deux_etapes_le_resume_est_l_unique_notification(self):
        resultat, _ = self.planifie(echec=DEUX_ECHECS)
        self.assertEqual(resultat.returncode, 1)
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("résumé du matin", self.notifications[0])
        lignes = self.appels_du_resume()
        self.assertEqual(len(lignes), 1)
        self.assertIn("--notify --failed-steps collecte, indexation | NOTIFY=1", lignes[0])     # dans l'ordre
        self.assertTrue(resultat.stdout.rstrip().endswith(FIN_ECHEC_2))
        repere = json.loads((self.home / "repere-a-l-appel.json").read_text(encoding="utf-8"))
        self.assertEqual((repere["etat"], repere["code"]), ("echoue", 1))

    def test_le_tableau_de_bord_en_echec_n_empeche_pas_le_resume(self):
        resultat, _ = self.planifie(echec="dashboard.py")
        self.assertEqual(resultat.returncode, 0)
        self.assertIn("Tableau de bord non généré", resultat.stdout)
        self.assertEqual(len(self.appels_du_resume()), 1)
        self.assertEqual(self.notifications_propres(), [])

    # -- pas d'appel ------------------------------------------------------------------------------------------------
    def test_jour_reporte_base_injoignable_pas_d_appel(self):
        resultat, _ = self.planifie(echec="watch_lab.py check-db", ECHEC_CODE="4")
        self.assertEqual(resultat.returncode, 1)
        self.assertEqual(self.lire()["etat"], "reporte")
        self.assertEqual(self.appels_du_resume(), [])
        self.assertEqual(len(self.notifications), 1)                   # la notification de report, une seule
        self.assertNotIn("résumé", self.notifications[0])

    def test_jour_reporte_reseau_absent_pas_d_appel(self):
        resultat, _ = self.planifie(echec="watch_lab.py check-network", ECHEC_CODE="1")
        self.assertEqual(self.lire()["etat"], "reporte")
        self.assertEqual(self.appels_du_resume(), [])

    def test_lancement_manuel_pas_d_appel_et_notification_d_echec_conservee(self):
        resultat, _ = self.manuel(echec="watch_lab.py collect")
        self.assertEqual(resultat.returncode, 1)
        self.assertEqual(self.appels_du_resume(), [])
        self.assertEqual(len(self.notifications), 1)
        self.assertIn("Étape(s) en échec : collecte", self.notifications[0])

    def test_lancement_manuel_reussi_pas_d_appel(self):
        resultat, _ = self.manuel()
        self.assertEqual((resultat.returncode, self.appels_du_resume(), self.notifications), (0, [], []))

    def test_rien_a_faire_pas_d_appel(self):
        self.ecrire_repere(etat="termine")
        resultat, appels = self.planifie()
        self.assertEqual((resultat.returncode, appels, self.appels_du_resume(), self.notifications), (0, [], [], []))
        resultat, appels = self.planifie(heure="05:00")            # avant l'heure due
        self.assertEqual((appels, self.appels_du_resume()), ([], []))

    def test_passage_interrompu_et_deja_repris_pas_d_appel(self):
        self.ecrire_repere(etat="commence", code=None, reprises=1)
        resultat, appels = self.planifie()
        self.assertEqual((resultat.returncode, appels, self.appels_du_resume()), (0, [], []))

    def test_repere_impossible_a_ecrire_pas_d_appel(self):
        self.donnees.mkdir(parents=True, exist_ok=True)
        self.donnees.chmod(0o500)
        self.addCleanup(self.donnees.chmod, 0o700)
        if os.access(self.donnees, os.W_OK):
            self.skipTest("l'utilisateur du test écrit malgré les droits (administrateur)")
        resultat, appels = self.planifie()
        self.assertEqual((resultat.returncode, appels, self.appels_du_resume()), (4, [], []))

    # -- le résumé échoue ou est coupé ----------------------------------------------------------------------------------
    def test_resume_en_echec_la_notification_d_echec_part_comme_avant(self):
        for code in ("1", "2", "3", "4", "127"):
            with self.subTest(code=code):
                self.appels_resume.unlink(missing_ok=True)
                self.appels.unlink(missing_ok=True)
                self.fichier_repere.unlink(missing_ok=True)
                resultat, _ = self.planifie(echec=DEUX_ECHECS, RESUME_CODE=code)
                self.assertEqual(resultat.returncode, 1)
                self.assertEqual(len(self.appels_du_resume()), 1)
                self.assertEqual(len(self.notifications), 1)
                self.assertIn(f"Étape(s) en échec : collecte, indexation. Voir ~/Library/Logs/pmzilla-watch.log", self.notifications[0])
                self.assertTrue(resultat.stdout.count(FIN_ECHEC_2) == 1)

    def test_resume_coupe_sur_un_passage_reussi_aucune_notification(self):
        resultat, _ = self.planifie(RESUME_CODE="4")
        self.assertEqual((resultat.returncode, self.notifications), (0, []))
        self.assertEqual(len(self.appels_du_resume()), 1)

    def test_resume_en_echec_sur_un_passage_reussi_code_0_et_une_ligne_au_journal(self):
        for code in ("1", "3"):
            self.fichier_repere.unlink(missing_ok=True)
            resultat, _ = self.planifie(RESUME_CODE=code)
            self.assertEqual((resultat.returncode, self.notifications), (0, []))
            self.assertIn(f"Résumé du matin non envoyé (code {code})", resultat.stdout)

    def test_le_code_de_sortie_et_la_ligne_de_fin_ne_changent_pas(self):
        resultat, _ = self.planifie()
        self.assertIn("=== Veille terminée sans erreur ===", resultat.stdout)
        self.assertEqual(resultat.returncode, 0)
        self.assertEqual(self.lire()["etat"], "termine")


if __name__ == "__main__":
    unittest.main()
