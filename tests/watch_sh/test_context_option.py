"""
La veille quotidienne et les notes de contexte (organisation-context, design D6 ; tâche 4.3) : tools/watch.sh passe l'option --context à
l'étape d'indexation quand le dossier de contexte a un sous-dossier de notes, sinon le dit dans le journal. Faux `uv` de test_watch_sh.py.

    python3 -m unittest discover -s tests/watch_sh -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_watch_sh import SCRIPT, Base  # noqa: E402

LIGNE_ABSENT = "dossier de contexte absent : notes de contexte inchangées"


class OptionDeContexte(Base):
    def dossier_de_contexte(self, avec_notes=True) -> Path:
        dossier = self.home / "PMZilla-Lab" / "contexte"      # le défaut du module partagé : « contexte » sous le dossier du lab
        (dossier / "originaux").mkdir(parents=True)
        if avec_notes:
            (dossier / "notes").mkdir()
        return dossier

    def ligne_d_indexation(self) -> str:
        [ligne] = [l for l in self.complets.read_text().splitlines() if "pmzilla_lab_library.py index" in l]
        return ligne

    def test_option_passee_quand_le_dossier_de_notes_existe(self):
        dossier = self.dossier_de_contexte()
        resultat, appels = self.lancer()
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        ligne = self.ligne_d_indexation()
        self.assertIn(f"--context {dossier}", ligne)
        self.assertIn("Bibliotheque-Lab", ligne)
        self.assertNotIn("originaux", self.complets.read_text() + self.appels.read_text())
        self.assertNotIn(LIGNE_ABSENT, resultat.stdout)
        self.assertIn("Veille terminée sans erreur", resultat.stdout)

    def test_option_passee_avec_le_dossier_donne_par_la_variable(self):
        autre = self.home / "ailleurs"
        (autre / "notes").mkdir(parents=True)
        resultat, _ = self.lancer(PMZILLA_LAB_CONTEXT=str(autre))
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertIn(f"--context {autre}", self.ligne_d_indexation())

    def test_dossier_absent_pas_d_option_une_ligne_au_journal_et_meme_issue(self):
        resultat, appels = self.lancer()
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertNotIn("--context", self.ligne_d_indexation())
        self.assertIn(LIGNE_ABSENT, resultat.stdout)
        self.assertIn("Veille terminée sans erreur", resultat.stdout)
        self.assertEqual(self.notifications, [])

    def test_dossier_sans_notes_vaut_dossier_absent(self):
        self.dossier_de_contexte(avec_notes=False)
        resultat, _ = self.lancer()
        self.assertNotIn("--context", self.ligne_d_indexation())
        self.assertIn(LIGNE_ABSENT, resultat.stdout)

    def test_note_refusee_par_l_indexeur_compte_comme_une_indexation_en_echec(self):
        self.dossier_de_contexte()
        resultat, appels = self.lancer(echec="pmzilla_lab_library.py index")
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("indexation", resultat.stdout.rsplit("Veille terminée", 1)[-1])

    def test_le_script_ne_nomme_jamais_les_originaux(self):
        texte = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("originaux", texte)
        self.assertNotIn("Contexte-Lab", texte)


if __name__ == "__main__":
    unittest.main()
