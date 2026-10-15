"""Tâche 4.3 : modèle launchd com.pmzilla.doctor et enveloppeur tools/doctor.sh (doublure de uv, aucun vrai lancement)."""
import os
import plistlib
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_doctor import RACINE, TOOLS, Labo  # noqa: E402

PLIST = TOOLS / "com.pmzilla.doctor.plist"
SCRIPT = TOOLS / "doctor.sh"


def horaire(nom):
    donnees = plistlib.loads((TOOLS / nom).read_text(encoding="utf-8").replace("__HOME__", "/h").encode())
    planning = donnees["StartCalendarInterval"]
    return (planning["Hour"], planning["Minute"])


class Modele(unittest.TestCase):
    def setUp(self):
        self.texte = PLIST.read_text(encoding="utf-8")
        self.donnees = plistlib.loads(self.texte.replace("__HOME__", "/home/essai").encode())

    def test_etiquette_et_commande(self):
        self.assertEqual(self.donnees["Label"], "com.pmzilla.doctor")
        self.assertEqual(self.donnees["ProgramArguments"], ["/bin/bash", "/home/essai/PMZilla-Lab/doctor.sh"])

    def test_chaque_jour_apres_les_taches_de_sauvegarde(self):
        planning = self.donnees["StartCalendarInterval"]
        self.assertNotIn("Weekday", planning)
        for precedent in ("com.pmzilla.db-backup.plist", "com.pmzilla.offsite-copy.plist", "com.pmzilla.watch.plist"):
            self.assertGreater(horaire("com.pmzilla.doctor.plist"), horaire(precedent), precedent)

    def test_ni_demarrage_a_la_charge_ni_relance(self):
        self.assertNotIn("RunAtLoad", self.donnees)
        self.assertNotIn("KeepAlive", self.donnees)

    def test_journal_et_aucun_chemin_reel_ni_secret(self):
        self.assertEqual(self.donnees["StandardOutPath"], "/home/essai/Library/Logs/pmzilla-doctor.log")
        self.assertEqual(self.donnees["StandardErrorPath"], self.donnees["StandardOutPath"])
        self.assertNotIn("/Users/", self.texte)
        self.assertNotIn("PASSWORD", self.texte.upper())
        self.assertNotIn("__HOME__", repr(self.donnees))


class Enveloppeur(Labo):
    def lancer_sh(self, code_doctor=0, code_tableau=0):
        uv = self.bin / "uv"
        uv.write_text('#!/bin/sh\necho "uv $* NOTIFIER=${DOCTOR_NOTIFIER:-}" >> "$STUB_LOG"\n'
                      'case "$*" in *doctor.py*) exit ' + str(code_doctor) + ';; *dashboard.py*) exit ' + str(code_tableau) + ';; esac\nexit 0\n', encoding="utf-8")
        uv.chmod(0o755)
        return subprocess.run(["bash", str(SCRIPT)], capture_output=True, text=True, env=self.environnement(), cwd=str(self.base), timeout=60)

    def appels_uv(self):
        return [a for a in self.appels() if a.startswith("uv ")]

    def test_enregistre_avec_notification_puis_regenere_le_tableau(self):
        p = self.lancer_sh()
        self.assertEqual(p.returncode, 0, p.stderr)
        appels = self.appels_uv()
        self.assertEqual(len(appels), 2)
        self.assertIn("doctor.py --record", appels[0])
        self.assertTrue(appels[0].endswith("NOTIFIER=1"))
        self.assertIn("dashboard.py", appels[1])

    def test_sort_avec_le_code_du_doctor(self):
        self.assertEqual(self.lancer_sh(code_doctor=1).returncode, 1)
        self.assertEqual(len(self.appels_uv()), 2, "le tableau de bord est regénéré même avec un problème")

    def test_echec_du_tableau_de_bord_sans_effet_sur_le_code(self):
        self.assertEqual(self.lancer_sh(code_doctor=0, code_tableau=1).returncode, 0)
        self.assertEqual(self.lancer_sh(code_doctor=1, code_tableau=1).returncode, 1)

    def test_aucune_commande_interdite(self):
        self.lancer_sh()
        self.assertEqual([a for a in self.appels() if a.split(" ")[0] in ("INTERDIT", "security", "psql", "docker", "launchctl")], [])
        source = SCRIPT.read_text(encoding="utf-8")
        for mot in ("security", "psql", "docker", "launchctl"):
            self.assertNotIn(mot, source)


if __name__ == "__main__":
    unittest.main()
