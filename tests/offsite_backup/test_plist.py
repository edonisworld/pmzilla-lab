"""Modèles launchd de la copie hors du Mac et de son test de restauration : tools/com.pmzilla.offsite-copy.plist et
tools/com.pmzilla.offsite-restore-test.plist.

Les fichiers sont des modèles : aucun chemin réel, __HOME__ remplacé par sed à l'installation. Le test ne lance ni launchctl ni le
script ; il lit les modèles et les rend en mémoire (sur le modèle de tests/db_backup_plist).
"""
import plistlib
import re
import subprocess
import unittest
import xml.dom.minidom
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
COPIE = TOOLS / "com.pmzilla.offsite-copy.plist"
TEST = TOOLS / "com.pmzilla.offsite-restore-test.plist"
SAUVEGARDE_BASE = TOOLS / "com.pmzilla.db-backup.plist"
MODELES = {COPIE: ("com.pmzilla.offsite-copy", "copy"), TEST: ("com.pmzilla.offsite-restore-test", "restore-test")}


def rendu(chemin: Path, home="/home/essai"):
    sortie = subprocess.run(["sed", f"s|__HOME__|{home}|g", str(chemin)], capture_output=True, text=True, check=True).stdout
    return plistlib.loads(sortie.encode())


def heure(planning):
    return (planning["Hour"], planning["Minute"])


class Modeles(unittest.TestCase):
    def test_xml_bien_forme_et_lu_par_plistlib_apres_rendu(self):
        for chemin, (etiquette, _) in MODELES.items():
            with self.subTest(chemin.name):
                texte = chemin.read_text(encoding="utf-8")
                xml.dom.minidom.parseString(texte.encode("utf-8"))
                self.assertTrue(texte.startswith('<?xml version="1.0" encoding="UTF-8"?>'))
                self.assertEqual(rendu(chemin)["Label"], etiquette)

    def test_chaque_jour_apres_le_travail_precedent(self):
        """La copie passe après la sauvegarde de la base ; le test de restauration après la copie."""
        sauvegarde = heure(rendu(SAUVEGARDE_BASE)["StartCalendarInterval"])
        copie = rendu(COPIE)["StartCalendarInterval"]
        test = rendu(TEST)["StartCalendarInterval"]
        self.assertEqual(set(copie), {"Hour", "Minute"})   # pas de Weekday ni de Day : tous les jours
        self.assertEqual(set(test), {"Hour", "Minute"})
        self.assertGreater(heure(copie), sauvegarde)
        self.assertGreater(heure(test), heure(copie))

    def test_declenchement_au_montage_d_un_volume(self):
        for chemin in MODELES:
            self.assertIs(rendu(chemin)["StartOnMount"], True, chemin.name)

    def test_pas_de_demarrage_a_la_charge_ni_de_relance_permanente(self):
        for chemin in MODELES:
            donnees = rendu(chemin)
            self.assertNotIn("RunAtLoad", donnees, chemin.name)
            self.assertNotIn("KeepAlive", donnees, chemin.name)

    def test_script_et_sous_commande(self):
        for chemin, (_, sous) in MODELES.items():
            donnees = rendu(chemin, "/home/essai")
            self.assertEqual(donnees["ProgramArguments"],
                             ["/bin/bash", "/home/essai/PMZilla-Lab/offsite_backup.sh", sous], chemin.name)

    def test_le_programme_est_le_lien_du_dossier_du_labo_sans_dossier_de_code(self):
        """Change run-worktree : chaque modèle lance ~/PMZilla-Lab/offsite_backup.sh (lien), seul HOME est un chemin d'utilisateur."""
        for chemin in MODELES:
            programme = rendu(chemin, "/home/essai")["ProgramArguments"][1]
            self.assertEqual(programme, "/home/essai/PMZilla-Lab/offsite_backup.sh", chemin.name)
            for dossier in ("/workspace/", "/run/", "/tools/"):
                self.assertNotIn(dossier, programme, chemin.name)

    def test_un_journal_par_tache_et_erreurs_dans_le_meme(self):
        journaux = []
        for chemin in MODELES:
            donnees = rendu(chemin, "/home/essai")
            self.assertTrue(donnees["StandardOutPath"].startswith("/home/essai/Library/Logs/pmzilla-offsite-"), chemin.name)
            self.assertEqual(donnees["StandardErrorPath"], donnees["StandardOutPath"])
            journaux.append(donnees["StandardOutPath"])
        self.assertEqual(len(set(journaux)), 2)

    def test_notification_activee(self):
        for chemin in MODELES:
            self.assertEqual(rendu(chemin)["EnvironmentVariables"], {"OFFSITE_NOTIFIER": "1"}, chemin.name)

    def test_aucun_secret_aucun_identifiant_aucun_chemin_reel(self):
        for chemin in MODELES:
            with self.subTest(chemin.name):
                texte = chemin.read_text(encoding="utf-8")
                self.assertNotIn("PASSWORD", texte.upper().replace("AUCUN MOT DE PASSE", ""))
                self.assertNotIn("security", texte)
                self.assertNotIn("Keychain", texte)
                self.assertNotIn("Trousseau find", texte)
                self.assertNotIn("/Users/", texte)
                self.assertNotIn("VolumeUUID", texte)
                self.assertIsNone(re.search(r"[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}", texte, re.I))
                self.assertNotIn("__HOME__", repr(rendu(chemin)))
                reste = re.findall(r"<string>(/[^<]*)</string>", texte)
                self.assertEqual([c for c in reste if not c.startswith("/bin/")], [])
                for chemin_utilisateur in re.findall(r"<string>(__HOME__[^<]*)</string>", texte):
                    self.assertTrue(chemin_utilisateur.startswith(("__HOME__/PMZilla-Lab/", "__HOME__/Library/Logs/")), chemin_utilisateur)


if __name__ == "__main__":
    unittest.main()
