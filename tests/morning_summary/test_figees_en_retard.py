"""R-20261110-03, -04 : le résumé du matin signale « copies figées en retard sur main » avec la commande exacte de rafraîchissement que contient la note
`outils-figes-en-retard` du dossier de données ; note absente : aucune ligne ; note illisible : une ligne qui le dit, sans trace Python.
Remplace : rien. Retrait : avec le bac à sable.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide import Labo  # noqa: E402

COMMANDE = 'cd "/espace/travail" && bash tools/outils_figes/rafraichir.sh "/espace/travail" "/donnees/outils-figes"'
SOMMET = "a" * 40


class FigeesEnRetard(Labo):
    def note(self, texte):
        (self.donnees / "outils-figes-en-retard").write_text(texte, encoding="utf-8")

    def lignes(self, *argv):
        code, sortie, erreur = self.lancer(*argv)
        self.assertEqual(code, 0)
        self.assertNotIn("Traceback", sortie + erreur)
        return sortie.splitlines()

    def test_avec_la_note_une_ligne_et_la_commande_exacte_en_francais(self):
        self.note(f"{SOMMET} {COMMANDE}\n")
        lignes = self.lignes()
        retard = [l for l in lignes if "en retard sur main" in l]
        self.assertEqual(len(retard), 1)
        self.assertIn("Copies figées en retard sur main", retard[0])
        self.assertTrue(retard[0].endswith(COMMANDE), retard[0])
        self.assertEqual(lignes[-1], retard[0])

    def test_avec_la_note_une_ligne_et_la_commande_exacte_en_anglais(self):
        self.note(f"{SOMMET} {COMMANDE}\n")
        lignes = self.lignes("--language", "en")
        retard = [l for l in lignes if "behind main" in l]
        self.assertEqual(len(retard), 1)
        self.assertTrue(retard[0].endswith(COMMANDE), retard[0])
        self.assertNotIn("en retard", retard[0])

    def test_sans_la_note_aucune_ligne(self):
        for argv in ((), ("--language", "en")):
            with self.subTest(argv=argv):
                lignes = self.lignes(*argv)
                self.assertEqual(len(lignes), 5)       # le titre et les quatre parties habituelles
                self.assertFalse([l for l in lignes if "main" in l])

    def test_note_illisible_une_ligne_qui_le_dit_sans_trace(self):
        for contenu in (b"\xff\xfe\x00\x80", b"", b"sommet-seul\n"):
            with self.subTest(contenu=contenu):
                (self.donnees / "outils-figes-en-retard").write_bytes(contenu)
                lignes = self.lignes()
                self.assertEqual(lignes[-1], "Copies figées en retard sur main : note illisible")
                lignes = self.lignes("--language", "en")
                self.assertEqual(lignes[-1], "Frozen copies behind main: note unreadable")

    def test_note_en_dossier_est_illisible(self):
        (self.donnees / "outils-figes-en-retard").mkdir()
        self.assertEqual(self.lignes()[-1], "Copies figées en retard sur main : note illisible")

    def test_la_notification_ne_porte_aucun_chemin_et_la_sortie_garde_la_commande(self):
        # R-20261110-04 : la commande exacte reste dans la sortie texte ; le corps de la notification est une phrase sans chemin.
        self.tout_connu()
        self.note(f"{SOMMET} {COMMANDE}\n")
        code, sortie, _ = self.lancer_planifie()
        self.assertEqual(code, 0)
        self.assertIn(COMMANDE, sortie)
        [appel] = self.notifications()
        corps = appel[-1]
        self.assertIn("Copies figées en retard sur main : commande dans le résumé du Terminal", corps)
        self.assertNotIn("/", corps)
        self.assertNotIn("rafraichir", corps)
        self.assertNotIn(COMMANDE, corps)

    def test_la_notification_anglaise_ne_porte_aucun_chemin(self):
        self.tout_connu()
        self.note(f"{SOMMET} {COMMANDE}\n")
        code, sortie, _ = self.lancer_planifie("--language", "en")
        self.assertEqual(code, 0)
        self.assertIn(COMMANDE, sortie)
        [appel] = self.notifications()
        corps = appel[-1]
        self.assertIn("Frozen copies behind main: command in the Terminal summary", corps)
        self.assertNotIn("/", corps)

    def test_le_json_porte_la_partie(self):
        self.note(f"{SOMMET} {COMMANDE}\n")
        code, sortie, _ = self.lancer("--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(sortie)["frozen"], {"state": "late", "command": COMMANDE})


if __name__ == "__main__":
    unittest.main()
