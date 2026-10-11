"""
Tests de scripts/wake.py des quatre postures : avertissement du contexte local absent, liste hors bibliothèque.

    uv run --with pyyaml python -m unittest discover -s tests/wake_postures -v

Racine factice dans un dossier temporaire (CLAUDE.md, tools/outside_library.py, catalogue fictif) ; wake.py est lancé
avec le Python courant (pyyaml requis, fourni par --with pyyaml).
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
POSTURES = ["delivery", "discovery", "scaling", "facilitation"]


class TestWake(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.racine = Path(self.temp.name)
        (self.racine / "tools").mkdir()
        # wake.py calcule la racine depuis son emplacement (lot 6) : les skills sont copiés dans la racine factice
        shutil.copytree(RACINE / ".claude" / "skills", self.racine / ".claude" / "skills",
                        ignore=shutil.ignore_patterns("__pycache__", "bmad-*"))
        for nom in ("outside_library.py", "references_postures.yaml"):
            shutil.copy2(RACINE / "tools" / nom, self.racine / "tools" / nom)
        (self.racine / "catalogue.yaml").write_text("{}\n", encoding="utf-8")
        (self.racine / "CLAUDE.md").write_text("# Test\n\n@.pmzilla/contexte.md\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def wake(self, posture: str) -> str:
        script = self.racine / ".claude" / "skills" / f"pmzilla-{posture}-bmad" / "scripts" / "wake.py"
        env = {"PATH": "/usr/bin:/bin", "PMZILLA_LAB_CATALOGUE": str(self.racine / "catalogue.yaml")}
        fait = subprocess.run([sys.executable, str(script), str(self.racine)], capture_output=True, text=True, env=env)
        self.assertEqual(fait.returncode, 0, fait.stderr)
        return fait.stdout

    def test_fichier_local_absent_est_signale_pour_chaque_posture(self):
        for posture in POSTURES:
            with self.subTest(posture=posture):
                sortie = self.wake(posture)
                self.assertIn("LOCAL FILE MISSING: .pmzilla/contexte.md", sortie)

    def test_fichier_local_present_pas_d_avertissement(self):
        (self.racine / ".pmzilla").mkdir()
        (self.racine / ".pmzilla" / "contexte.md").write_text("contexte", encoding="utf-8")
        for posture in POSTURES:
            with self.subTest(posture=posture):
                self.assertNotIn("LOCAL FILE MISSING", self.wake(posture))

    def test_la_liste_hors_bibliotheque_est_imprimee_et_calculee(self):
        sortie = self.wake("delivery")
        self.assertIn("WORKS ABSENT FROM THE LIBRARY", sortie)
        self.assertIn("Goldratt, The Goal", sortie)       # catalogue vide : tout est hors bibliothèque

    def test_aucune_formule_hors_bibliotheque_dans_le_reveil(self):
        """Ni « hors bibliothèque » ni « outside the library » : la posture prend la formule de sa langue de réponse
        dans la table de CLAUDE.md (une formule citée au réveil a fait écrire l'anglais dans des réponses françaises)."""
        formules = ("hors bibliothèque", "hors bibliotheque", "outside the library")
        for posture in POSTURES:
            with self.subTest(posture=posture, liste="calculée"):
                sortie = self.wake(posture).casefold()
                self.assertFalse([f for f in formules if f in sortie])
        (self.racine / "catalogue.yaml").unlink()                   # liste non calculée : catalogue introuvable
        sortie = self.wake("delivery").casefold()
        self.assertIn("out-of-library formula of your response language", sortie)
        self.assertFalse([f for f in formules if f in sortie])
        (self.racine / "tools" / "outside_library.py").unlink()  # liste non calculée : module absent
        sortie = self.wake("delivery").casefold()
        self.assertFalse([f for f in formules if f in sortie])

    def test_les_relations_entre_ouvrages_sont_imprimees(self):
        sortie = self.wake("scaling")
        self.assertIn("RELATIONS ENTRE OUVRAGES", sortie)
        self.assertIn("Architecture for Flow : commente Team Topologies", sortie)
        self.assertNotIn("RELATIONS ENTRE OUVRAGES", self.wake("discovery"))

    def test_import_dans_un_bloc_de_code_ou_une_phrase_n_est_pas_un_import(self):
        (self.racine / "CLAUDE.md").write_text("Écris @nom dans la phrase.\n", encoding="utf-8")
        self.assertNotIn("LOCAL FILE MISSING", self.wake("delivery"))

    def test_premier_reveil_signale_aussi_le_fichier_absent(self):
        self.assertIn("MODE: FIRST_BREATH", self.wake("scaling"))
        self.assertIn("LOCAL FILE MISSING", self.wake("scaling"))


if __name__ == "__main__":
    unittest.main()
