"""Modèle launchd de la sauvegarde quotidienne de la base : tools/com.pmzilla.db-backup.plist.

Le fichier est un modèle : aucun chemin réel, __HOME__ remplacé par sed à l'installation. Le test ne lance ni launchctl
ni le script ; il lit le modèle et le rend en mémoire.
"""
import plistlib
import re
import subprocess
import unittest
import xml.dom.minidom
from pathlib import Path

PLIST = Path(__file__).resolve().parents[2] / "tools" / "com.pmzilla.db-backup.plist"
WATCH = PLIST.with_name("com.pmzilla.watch.plist")


class ModelePlist(unittest.TestCase):
    def setUp(self):
        self.texte = PLIST.read_text(encoding="utf-8")

    def rendu(self, home="/home/essai"):
        sortie = subprocess.run(["sed", f"s|__HOME__|{home}|g", str(PLIST)], capture_output=True, text=True, check=True).stdout
        return plistlib.loads(sortie.encode())

    def test_xml_bien_forme(self):
        xml.dom.minidom.parseString(self.texte.encode("utf-8"))
        self.assertTrue(self.texte.startswith('<?xml version="1.0" encoding="UTF-8"?>'))

    def test_modele_lu_par_plistlib_apres_rendu(self):
        donnees = self.rendu()
        self.assertEqual(donnees["Label"], "com.pmzilla.db-backup")

    def test_chaque_jour_a_7h45_apres_la_collecte_de_7h10(self):
        planning = self.rendu()["StartCalendarInterval"]
        self.assertEqual(planning, {"Hour": 7, "Minute": 45})   # pas de Weekday : tous les jours
        veille = plistlib.loads(WATCH.read_text(encoding="utf-8").replace("__HOME__", "/h").encode())["StartCalendarInterval"]
        self.assertGreater((planning["Hour"], planning["Minute"]), (veille["Hour"], veille["Minute"]))

    def test_chemins_avec_home_et_aucun_chemin_reel(self):
        self.assertIn("<string>__HOME__/PMZilla-Lab/db_backup.sh</string>", self.texte)
        self.assertEqual(self.texte.count("<string>__HOME__/Library/Logs/pmzilla-db-backup.log</string>"), 2)
        self.assertNotIn("/Users/", self.texte)
        reste = re.findall(r"<string>(/[^<]*)</string>", self.texte)
        self.assertEqual([c for c in reste if not c.startswith(("/bin/", "__HOME__"))], [])

    def test_rendu_sans_residu_et_chemins_attendus(self):
        donnees = self.rendu("/home/essai")
        self.assertEqual(donnees["ProgramArguments"], ["/bin/bash", "/home/essai/PMZilla-Lab/db_backup.sh"])
        self.assertEqual(donnees["StandardOutPath"], "/home/essai/Library/Logs/pmzilla-db-backup.log")
        self.assertEqual(donnees["StandardErrorPath"], donnees["StandardOutPath"])
        self.assertNotIn("__HOME__", repr(donnees))

    def test_le_programme_est_le_lien_du_dossier_du_labo_sans_dossier_de_code(self):
        """Change run-worktree : le modèle lance ~/PMZilla-Lab/db_backup.sh (lien), jamais un dossier de code."""
        programme = self.rendu("/home/essai")["ProgramArguments"][1]
        self.assertEqual(programme, "/home/essai/PMZilla-Lab/db_backup.sh")
        for dossier in ("/workspace/", "/run/", "/tools/"):
            self.assertNotIn(dossier, programme)

    def test_notification_activee_et_aucun_secret(self):
        env = self.rendu()["EnvironmentVariables"]
        self.assertEqual(env["DB_BACKUP_NOTIFIER"], "1")
        self.assertNotIn("PASSWORD", self.texte.upper())
        self.assertNotIn("security find-generic-password", self.texte)

    def test_pas_de_demarrage_a_la_charge(self):
        """Un bootstrap ne doit pas lancer une sauvegarde hors horaire ; le rattrapage au réveil vient de StartCalendarInterval."""
        donnees = self.rendu()
        self.assertNotIn("RunAtLoad", donnees)
        self.assertNotIn("KeepAlive", donnees)


if __name__ == "__main__":
    unittest.main()
