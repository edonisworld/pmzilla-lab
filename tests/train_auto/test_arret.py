"""
Tâche 2.7 (change autonomous-trains-observe) : l'arrêt d'urgence, le verrou propre du passage, l'erreur inattendue et les codes de sortie de D11.
"""
import fcntl
import io
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from aide_auto import AvecAuto, RACINE, epoch

sys.path.insert(0, str(RACINE / "tools"))
import train_auto  # noqa: E402


class Arret(AvecAuto):
    def fichier_arret(self):
        return self.dossier_train() / "arret"

    def test_arret_permis_en_session(self):
        r = self.auto("arret", extra={"CLAUDECODE": "1"})
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("train_auto : arrêt posé", r.sortie)
        self.assertTrue(self.fichier_arret().exists())
        self.assertEqual(self.journal()[-1]["type"], "arret")
        self.assertEqual(self.journal()[-1]["caller"], "session")
        r = self.passage()
        self.assertIn("train_auto : arrêté (arrêt d'urgence actif)", r.sortie)

    def test_reprendre_refuse_en_session(self):
        self.auto("arret")
        r = self.auto("reprendre", extra={"CLAUDECODE": "1"})
        self.assertEqual(r.code, 3, r.texte)
        self.assertIn("train_auto : session Claude Code, lancement refusé", r.texte)
        self.assertTrue(self.fichier_arret().exists())
        self.assertEqual([x["type"] for x in self.journal()], ["arret"])

    def test_reprendre_par_l_auteur_leve_l_arret(self):
        self.auto("arret")
        r = self.auto("reprendre")
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("train_auto : arrêt levé", r.sortie)
        self.assertFalse(self.fichier_arret().exists())
        self.assertEqual([x["type"] for x in self.journal()], ["arret", "reprendre"])
        r = self.passage(now=epoch(7, 0))   # D13 (passages toutes les heures de 8 h à 21 h) : 7 h reste hors fenêtre
        self.assertIn("hors fenêtre", r.sortie)   # le passage ne s'arrête plus sur l'arrêt

    def test_un_fichier_d_arret_supprime_a_la_main_est_recree(self):
        self.auto("arret")
        self.fichier_arret().unlink()
        r = self.passage()
        self.assertEqual(r.code, 0, r.texte)
        self.assertIn("train_auto : arrêt disparu sans « reprendre » : recréé", r.sortie)
        self.assertIn("train_auto : arrêté (arrêt d'urgence actif)", r.sortie)
        self.assertTrue(self.fichier_arret().exists())
        d = self.dernier()
        self.assertEqual((d["decision"], d["raison"]), ("arrete", "arret-disparu"))
        # et il reste arrêté tant que « reprendre » n'est pas passé
        self.fichier_arret().unlink()
        self.assertIn("arrêt disparu", self.passage().sortie)

    def test_reprendre_apres_un_arret_efface_la_memoire_de_l_arret(self):
        self.auto("arret")
        self.auto("reprendre")
        r = self.passage(now=epoch(7, 0))
        self.assertNotIn("arrêt disparu", r.sortie)

    # --- le verrou propre du passage
    def test_un_second_passage_sort_en_5_sans_rien_ecrire(self):
        self.dossier_train().mkdir(parents=True)
        fd = os.open(self.dossier_train() / "passage.lock", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            r = self.passage()
        finally:
            os.close(fd)
        self.assertEqual(r.code, 5, r.texte)
        self.assertIn("train_auto : un autre passage est en cours", r.texte)
        self.assertEqual(self.journal(), [])
        self.assertIsNone(self.etat())
        # le verrou libéré, le passage suivant passe
        self.assertEqual(self.passage(now=epoch(7, 0)).code, 0)

    # --- erreur inattendue et codes
    def test_erreur_inattendue_sort_en_6_avec_le_type_seulement(self):
        sortie, erreur = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, self.environnement(epoch()), clear=True), mock.patch.object(train_auto, "decide",
                                                                                                        side_effect=RuntimeError("secret-de-l-erreur")):
            with redirect_stdout(sortie), redirect_stderr(erreur):
                code = train_auto.main(["pass"])
        self.assertEqual(code, 6)
        self.assertIn("train_auto : erreur inattendue (RuntimeError)", erreur.getvalue())
        self.assertNotIn("secret-de-l-erreur", sortie.getvalue() + erreur.getvalue())
        self.assertNotIn("Traceback", sortie.getvalue() + erreur.getvalue())

    def test_chaque_code_de_sortie_de_la_conception_est_atteint(self):
        atteints = set()
        atteints.add(self.passage(now=epoch(7, 0)).code)                                         # 0 : un passage qui attend
        atteints.add(self.auto("bogus").code)                                                       # 2 : usage
        atteints.add(self.passage(extra={"CLAUDECODE": "1"}).code)                                  # 3 : session
        fichier = self.t.dossier / "un-fichier"
        fichier.write_text("x", encoding="utf-8")
        atteints.add(self.passage(extra={"PMZILLA_LAB_DATA": str(fichier)}).code)                   # 4 : dossier de données inutilisable
        self.dossier_train().mkdir(parents=True, exist_ok=True)
        fd = os.open(self.dossier_train() / "passage.lock", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            atteints.add(self.passage().code)                                                       # 5 : un autre passage
        finally:
            os.close(fd)
        with mock.patch.dict(os.environ, self.environnement(epoch()), clear=True), mock.patch.object(train_auto, "decide", side_effect=ValueError("x")):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                atteints.add(train_auto.main(["pass"]))                                             # 6 : erreur inattendue
        self.assertEqual(atteints, {0, 2, 3, 4, 5, 6})
        # les codes déclarés dans l'en-tête sont exactement ceux-là
        entete = train_auto.__doc__
        for code in (0, 2, 3, 4, 5, 6):
            self.assertIn(f"{code} ", entete)

    def test_chemins_du_lab_introuvables_sort_en_4(self):
        r = self.passage(extra={"PMZILLA_LAB_WORKSPACE": str(self.t.dossier / "absent")})
        self.assertEqual(r.code, 4, r.texte)


if __name__ == "__main__":
    unittest.main()
