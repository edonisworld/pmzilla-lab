"""
Tests de tools/bmad_remplacements.py : les remplacements imposés aux skills installés se rejouent après l'installeur.

    uv run python -m unittest discover -s tests/bmad_remplacements -v

Racine factice dans un dossier temporaire, textes génériques ; aucun appel réseau.
"""
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import bmad_remplacements as br  # noqa: E402

ANCIEN, NOUVEAU = "alpha-routes.md", "product-routes.md"


class TestRemplacements(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.racine = Path(self.temp.name).resolve()
        self.skill = self.racine / ".claude" / "skills" / "bmad-x" / "SKILL.md"
        self.skill.parent.mkdir(parents=True)
        self.skill.write_text(f"Exemples : `{ANCIEN}`, `{ANCIEN}` et `autre.md`.\n", encoding="utf-8")
        self.regles = self.racine / ".pmzilla" / "remplacements-bmad.tsv"
        self.regles.parent.mkdir()
        self.regles.write_text(f"# commentaire\n\n.claude/skills/bmad-x/SKILL.md\t{ANCIEN}\t{NOUVEAU}\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def lancer(self, *options):
        sortie = io.StringIO()
        with redirect_stdout(sortie):
            code = br.main(["--racine", str(self.racine), *options])
        return code, sortie.getvalue()

    def test_remplace_toutes_les_occurrences(self):
        code, sortie = self.lancer()
        self.assertEqual(code, 0)
        self.assertEqual(self.skill.read_text(encoding="utf-8"), f"Exemples : `{NOUVEAU}`, `{NOUVEAU}` et `autre.md`.\n")
        self.assertIn("2 occurrence(s) remplacé", sortie)

    def test_check_n_ecrit_rien_et_sort_en_1(self):
        avant = self.skill.read_text(encoding="utf-8")
        code, sortie = self.lancer("--check")
        self.assertEqual(code, 1)
        self.assertEqual(self.skill.read_text(encoding="utf-8"), avant)
        self.assertIn("2 occurrence(s) à remplacer", sortie)

    def test_rejouer_ne_change_rien(self):
        self.lancer()
        code, sortie = self.lancer("--check")
        self.assertEqual(code, 0)
        self.assertIn("Aucun remplacement à faire", sortie)

    def test_la_sortie_ne_donne_pas_les_textes(self):
        _, sortie = self.lancer()
        self.assertNotIn(ANCIEN, sortie)
        self.assertNotIn(NOUVEAU, sortie)

    def test_fichier_absent_est_signale(self):
        self.skill.unlink()
        code, sortie = self.lancer("--check")
        self.assertEqual(code, 0)
        self.assertIn("Fichier absent : .claude/skills/bmad-x/SKILL.md", sortie)

    def test_sans_fichier_de_regles_rien_ne_casse(self):
        self.regles.unlink()
        code, sortie = self.lancer()
        self.assertEqual(code, 0)
        self.assertIn("Rien à rejouer", sortie)

    def test_ligne_mal_formee_arrete(self):
        self.regles.write_text("seulement\tdeux\n", encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.lancer()


if __name__ == "__main__":
    unittest.main()
