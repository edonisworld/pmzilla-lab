"""`pilot.py gestes` et la ligne de `status` (R-160, P4) : lecture seule de la file des gestes de l'auteur, fichier factice
dans le dossier temporaire du test (variable PILOT_GESTES), jamais le vrai fichier. Écrits avant le code.

    python3 -W ignore -m unittest discover -s tests/pilot -q
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aide_pilot as A  # noqa: E402

FICHIER = """# File des gestes de l'auteur (fictive)

Tenue par la session.

## En attente

| # | Geste | Commande | Débloque | Décision |
|---|---|---|---|---|
| G1 | dbtest du lot | `bash tools/dbtest.sh && echo a | cat` | fin du lot | R-1 |
| G2 | Répondre aux décisions | réponses dans un fichier | fin de D1 | — |
| ~~G3~~ | geste barré | ~~x~~ | rien | R-3 |

## Faits

| # | Geste | Résultat donné par l'auteur |
|---|---|---|
| G0 | geste ancien | fait (2026-10-28) |
"""


class Gestes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.labo = A.Labo()

    def setUp(self):
        self.labo.ecrire_gestes(FICHIER)

    def test_liste_les_gestes_en_attente_seulement(self):
        r = self.labo.pilot("gestes")
        self.assertEqual(r.returncode, 0, r.stderr)
        lignes = r.stdout.splitlines()
        self.assertEqual(lignes[0], "pilot : 2 geste(s) en attente")
        self.assertIn("G1 | dbtest du lot", r.stdout)
        self.assertIn("G2 | Répondre aux décisions", r.stdout)
        self.assertNotIn("G3", r.stdout)
        self.assertNotIn("G0", r.stdout)

    def test_commande_decision_et_debloque(self):
        r = self.labo.pilot("gestes")
        self.assertIn("commande : bash tools/dbtest.sh && echo a | cat", r.stdout)
        self.assertIn("débloque : fin du lot", r.stdout)
        self.assertIn("décision : R-1", r.stdout)

    def test_langue_anglaise(self):
        r = self.labo.pilot("--language", "en", "gestes")
        self.assertEqual(r.stdout.splitlines()[0], "pilot: 2 pending gesture(s)")
        self.assertIn("command: bash tools/dbtest.sh", r.stdout)

    def test_aucun_geste_en_attente(self):
        self.labo.ecrire_gestes("## En attente\n\n| # | Geste | Commande | Débloque | Décision |\n|---|---|---|---|---|\n\n## Faits\n")
        r = self.labo.pilot("gestes")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "pilot : aucun geste en attente")

    def test_fichier_absent_code_9(self):
        self.labo.retirer_gestes()
        r = self.labo.pilot("gestes")
        self.assertEqual(r.returncode, 9)
        self.assertIn("file des gestes introuvable", r.stderr)
        self.assertNotIn(str(self.labo.tmp), r.stderr)

    def test_sans_section_en_attente_code_9(self):
        self.labo.ecrire_gestes("# autre chose\n")
        r = self.labo.pilot("gestes")
        self.assertEqual(r.returncode, 9)

    def test_lecture_seule(self):
        avant = self.labo.gestes.read_bytes()
        etat = self.labo.etat_git()
        self.labo.pilot("gestes")
        self.labo.pilot("status")
        self.assertEqual(self.labo.gestes.read_bytes(), avant)
        self.assertEqual(self.labo.etat_git(), etat)

    def test_status_ajoute_une_ligne_de_compte(self):
        r = self.labo.pilot("status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("gestes en attente : 2", r.stdout.splitlines())
        self.assertNotIn("dbtest", r.stdout)

    def test_status_sans_fichier_n_ajoute_rien(self):
        self.labo.retirer_gestes()
        r = self.labo.pilot("status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("gestes en attente", r.stdout)

    def test_status_sans_fichier_valide_n_ajoute_rien(self):
        self.labo.ecrire_gestes("# autre chose\n")
        r = self.labo.pilot("status")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("gestes en attente", r.stdout)


if __name__ == "__main__":
    unittest.main()
