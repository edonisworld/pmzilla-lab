"""
Tests de tools/sanctum_refresh.py : le sanctum se met à jour depuis les modèles sans toucher au vécu.

    uv run --with pyyaml python -m unittest discover -s tests/sanctum_refresh -v

Racine factice dans un dossier temporaire (copie des skills), vrai init-sanctum.py ; aucun appel réseau.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import sanctum_refresh as refresh  # noqa: E402


class TestRefresh(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.racine = Path(self.temp.name).resolve()
        shutil.copytree(RACINE / ".claude" / "skills", self.racine / ".claude" / "skills",
                        ignore=shutil.ignore_patterns("__pycache__", ".memlog.md"))
        self.sanctum = self.racine / "_bmad" / "memory" / "pmzilla-delivery-bmad"

    def tearDown(self):
        self.temp.cleanup()

    def test_sanctum_absent_est_cree(self):
        refresh.actualiser(self.racine, "delivery")
        self.assertTrue((self.sanctum / "CREED.md").is_file())

    def test_deuxieme_passage_ne_change_rien(self):
        refresh.actualiser(self.racine, "delivery")
        self.assertEqual(refresh.actualiser(self.racine, "delivery"), ([], []))

    def test_aucun_chemin_absolu_dans_le_sanctum_cree_ni_dans_un_ancien_sanctum_rafraichi(self):
        refresh.actualiser(self.racine, "delivery")
        for nom in ("CREED.md", "CAPABILITIES.md"):
            self.assertNotRegex((self.sanctum / nom).read_text(encoding="utf-8"), r"/(Users|home|private)/", nom)
        # un ancien sanctum, dont le CREED et le CAPABILITIES portaient le chemin du workspace, en est débarrassé
        (self.sanctum / "CREED.md").write_text("- `/Users/quelquun/PMZilla-Lab/workspace/` — vieux chemin", encoding="utf-8")
        (self.sanctum / "CAPABILITIES.md").write_text("`/Users/quelquun/PMZilla-Lab/workspace/_bmad-output/`", encoding="utf-8")
        ecrits, _ = refresh.actualiser(self.racine, "delivery")
        self.assertEqual(sorted(ecrits), ["CAPABILITIES.md", "CREED.md"])
        for nom in ("CREED.md", "CAPABILITIES.md"):
            self.assertNotIn("/Users/", (self.sanctum / nom).read_text(encoding="utf-8"), nom)

    def test_un_modele_avec_un_chemin_absolu_arrete_tout_sans_rien_ecrire(self):
        refresh.actualiser(self.racine, "delivery")
        (self.sanctum / "CREED.md").write_text("vieux", encoding="utf-8")
        modele = self.racine / ".claude" / "skills" / "pmzilla-delivery-bmad" / "assets" / "CREED-template.md"
        modele.write_text(modele.read_text(encoding="utf-8") + "\n- `/Users/quelquun/PMZilla-Lab/workspace/`\n", encoding="utf-8")
        with self.assertRaises(SystemExit) as erreur:
            refresh.actualiser(self.racine, "delivery")
        self.assertIn("CREED.md", str(erreur.exception))
        self.assertEqual((self.sanctum / "CREED.md").read_text(encoding="utf-8"), "vieux")

    def test_index_n_est_jamais_reecrit(self):
        refresh.actualiser(self.racine, "delivery")
        (self.sanctum / "INDEX.md").write_text("mon index à moi", encoding="utf-8")
        ecrits, supprimes = refresh.actualiser(self.racine, "delivery")
        self.assertNotIn("INDEX.md", ecrits)
        self.assertEqual((self.sanctum / "INDEX.md").read_text(encoding="utf-8"), "mon index à moi")
        self.assertNotIn("INDEX.md", refresh.FICHIERS)

    def test_modele_modifie_recopie_et_vecu_intact(self):
        refresh.actualiser(self.racine, "delivery")
        for nom, contenu in (("MEMORY.md", "mon vécu"), ("BOND.md", "mon lien"), ("PERSONA.md", "ma persona")):
            (self.sanctum / nom).write_text(contenu, encoding="utf-8")
        (self.sanctum / "sessions").mkdir(exist_ok=True)
        (self.sanctum / "sessions" / "2026-01-01.md").write_text("séance", encoding="utf-8")
        reference = self.racine / ".claude" / "skills" / "pmzilla-delivery-bmad" / "references" / "review-ritual.md"
        reference.write_text(reference.read_text(encoding="utf-8") + "\nLigne nouvelle.\n", encoding="utf-8")
        ecrits, supprimes = refresh.actualiser(self.racine, "delivery")
        self.assertEqual(ecrits, ["references/review-ritual.md"])
        self.assertIn("Ligne nouvelle.", (self.sanctum / "references" / "review-ritual.md").read_text(encoding="utf-8"))
        self.assertEqual((self.sanctum / "MEMORY.md").read_text(encoding="utf-8"), "mon vécu")
        self.assertEqual((self.sanctum / "BOND.md").read_text(encoding="utf-8"), "mon lien")
        self.assertEqual((self.sanctum / "PERSONA.md").read_text(encoding="utf-8"), "ma persona")
        self.assertTrue((self.sanctum / "sessions" / "2026-01-01.md").is_file())

    def test_reference_retiree_du_skill_est_supprimee_du_sanctum(self):
        refresh.actualiser(self.racine, "delivery")
        (self.sanctum / "references" / "ancienne.md").write_text("périmée", encoding="utf-8")
        _, supprimes = refresh.actualiser(self.racine, "delivery")
        self.assertEqual(supprimes, ["references/ancienne.md"])
        self.assertFalse((self.sanctum / "references" / "ancienne.md").exists())

    def test_dry_run_n_ecrit_rien(self):
        refresh.actualiser(self.racine, "delivery")
        (self.sanctum / "CREED.md").write_text("vieux", encoding="utf-8")
        ecrits, _ = refresh.actualiser(self.racine, "delivery", dry_run=True)
        self.assertEqual(ecrits, ["CREED.md"])
        self.assertEqual((self.sanctum / "CREED.md").read_text(encoding="utf-8"), "vieux")


if __name__ == "__main__":
    unittest.main()
