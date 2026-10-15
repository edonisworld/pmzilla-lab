"""
Tests des gabarits launchd de la veille (change watch-catch-up, design D1, D5, D7, D10) : gabarit du rattrapage, option
--if-due du gabarit du calendrier, heure d'échéance de watch.sh égale à l'heure du calendrier.

    python3 -W ignore -m unittest discover -s tests/watch_sh -p "test_plist_rattrapage.py" -q -f
"""
import plistlib
import re
import subprocess
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / "tools"
GABARIT_RATTRAPAGE = TOOLS / "com.pmzilla.watch-catchup.plist"
GABARIT_CALENDRIER = TOOLS / "com.pmzilla.watch.plist"
SCRIPT = TOOLS / "watch.sh"


def rendre(chemin: Path) -> dict:
    texte = chemin.read_text(encoding="utf-8")
    rendu = subprocess.run(["sed", "s|__HOME__|/home/essai|g"], input=texte, text=True, capture_output=True).stdout
    return plistlib.loads(rendu.encode())


class GabaritRattrapage(unittest.TestCase):
    def setUp(self):
        self.texte = GABARIT_RATTRAPAGE.read_text(encoding="utf-8")
        self.donnees = rendre(GABARIT_RATTRAPAGE)

    def test_etiquette(self):
        self.assertEqual(self.donnees["Label"], "com.pmzilla.watch-catchup")

    def test_meme_lien_que_le_gabarit_du_calendrier_puis_l_option(self):
        calendrier = rendre(GABARIT_CALENDRIER)
        self.assertEqual(self.donnees["ProgramArguments"][:2], ["/bin/zsh", "/home/essai/PMZilla-Lab/watch.sh"])
        self.assertEqual(self.donnees["ProgramArguments"][:2], calendrier["ProgramArguments"][:2])
        self.assertEqual(self.donnees["ProgramArguments"][2:], ["--catch-up"])

    def test_lancement_au_chargement_et_intervalle_d_une_heure(self):
        self.assertIs(self.donnees["RunAtLoad"], True)
        self.assertEqual(self.donnees["StartInterval"], 3600)

    def test_ni_calendrier_ni_keep_alive(self):
        self.assertNotIn("StartCalendarInterval", self.donnees)
        self.assertNotIn("KeepAlive", self.donnees)

    def test_journal_de_la_veille_pour_les_deux_sorties(self):
        self.assertEqual(self.texte.count("<string>__HOME__/Library/Logs/pmzilla-watch.log</string>"), 2)
        self.assertEqual(self.donnees["StandardOutPath"], "/home/essai/Library/Logs/pmzilla-watch.log")
        self.assertEqual(self.donnees["StandardErrorPath"], "/home/essai/Library/Logs/pmzilla-watch.log")

    def test_aucun_chemin_reel_ni_ancien_nom(self):
        self.assertNotIn("/Users/", self.texte)
        self.assertNotIn("veille", self.texte.lower())

    def test_rendu_valide(self):
        self.assertNotIn("__HOME__", subprocess.run(["sed", "s|__HOME__|/home/essai|g"], input=self.texte, text=True,
                                                    capture_output=True).stdout)


class GabaritCalendrier(unittest.TestCase):
    def test_option_if_due_apres_le_lien(self):
        donnees = rendre(GABARIT_CALENDRIER)
        self.assertEqual(donnees["ProgramArguments"], ["/bin/zsh", "/home/essai/PMZilla-Lab/watch.sh", "--if-due"])

    def test_aucun_chemin_reel_ni_ancien_nom(self):
        texte = GABARIT_CALENDRIER.read_text(encoding="utf-8")
        self.assertNotIn("/Users/", texte)
        self.assertNotIn("veille", texte.lower())


class HeureDue(unittest.TestCase):
    def test_constante_de_watch_sh_egale_a_l_heure_du_calendrier(self):
        script = SCRIPT.read_text(encoding="utf-8")
        trouve = re.search(r'^HEURE_DUE="(\d{2}):(\d{2})"$', script, re.M)
        self.assertIsNotNone(trouve, 'watch.sh doit contenir une ligne exacte HEURE_DUE="HH:MM"')
        calendrier = rendre(GABARIT_CALENDRIER)["StartCalendarInterval"]
        self.assertEqual((int(trouve.group(1)), int(trouve.group(2))), (calendrier["Hour"], calendrier["Minute"]))


if __name__ == "__main__":
    unittest.main()
