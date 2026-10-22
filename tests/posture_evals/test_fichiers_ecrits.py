"""
Fichiers écrits par la séance (`changed_files`) : un livrable gardé sous `_bmad-output/` est vu même quand Git
l'ignore (`_bmad-output/pmzilla/internes/`), sans ramasser les dossiers d'outillage ignorés (.venv, caches,
sanctum de la mémoire).

    uv run --with pyyaml python -m unittest discover -s tests/posture_evals -p test_fichiers_ecrits.py -v

Aucune séance, aucun worktree : un dépôt Git jetable dans un dossier temporaire joue la copie, un autre dossier
le workspace.
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import posture_evals as essai  # noqa: E402

IGNORES = "\n".join([
    ".venv/",
    "__pycache__/",
    "/_bmad/memory/",
    "/_bmad-output/pmzilla/internes/",
    "/_bmad-output/essais/",
    "",
])


def ecrire(chemin: Path, texte: str) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte, encoding="utf-8")


class FichiersEcritsIgnores(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.copie = self.tmp / "copie"
        self.workspace = self.tmp / "workspace"
        self.workspace.mkdir()
        ecrire(self.copie / ".gitignore", IGNORES)
        ecrire(self.copie / "CLAUDE.md", "instructions")
        for commande in (["init", "-q"], ["add", "-A"],
                         ["-c", "user.email=essai@example.invalid", "-c", "user.name=essai", "commit", "-q", "-m", "départ"]):
            subprocess.run(["git", *commande], cwd=self.copie, check=True, capture_output=True)
        patch = mock.patch.object(essai, "WORKSPACE", self.workspace)
        patch.start()
        self.addCleanup(patch.stop)

    def test_livrable_gardé_dans_un_dossier_ignoré_est_vu(self):
        ecrire(self.copie / "_bmad-output" / "pmzilla" / "internes" / "2026-10-20-audit.md", "verdicts")
        fichiers = essai.changed_files(self.copie)
        self.assertEqual(fichiers, {"_bmad-output/pmzilla/internes/2026-10-20-audit.md": "verdicts"})

    def test_fichiers_suivis_ou_non_suivis_toujours_vus(self):
        ecrire(self.copie / "CLAUDE.md", "instructions modifiées")
        ecrire(self.copie / "_bmad-output" / "pmzilla" / "2026-10-20-plan.md", "plan")
        fichiers = essai.changed_files(self.copie)
        self.assertEqual(set(fichiers), {"CLAUDE.md", "_bmad-output/pmzilla/2026-10-20-plan.md"})

    def test_outillage_ignoré_hors_bmad_output_non_ramassé(self):
        ecrire(self.copie / ".venv" / "lib" / "site.py", "outil")
        ecrire(self.copie / "tools" / "__pycache__" / "x.pyc", "cache")
        ecrire(self.copie / "_bmad" / "memory" / "pmzilla-delivery-bmad" / "MEMORY.md", "sanctum")
        self.assertEqual(essai.changed_files(self.copie), {})

    def test_caches_sous_bmad_output_non_ramassés(self):
        ecrire(self.copie / "_bmad-output" / "pmzilla" / "__pycache__" / "x.pyc", "cache")
        ecrire(self.copie / "_bmad-output" / "pmzilla" / "internes" / ".DS_Store", "finder")
        self.assertEqual(essai.changed_files(self.copie), {})

    def test_fichier_ignoré_identique_au_workspace_non_compté(self):
        nom = "_bmad-output/pmzilla/internes/ancien.md"
        ecrire(self.copie / nom, "déjà là")
        ecrire(self.workspace / nom, "déjà là")
        self.assertEqual(essai.changed_files(self.copie), {})

    def test_fichier_posé_au_départ_non_compté(self):
        nom = "_bmad-output/pmzilla/internes/posé.md"
        ecrire(self.copie / nom, "posé")
        self.assertEqual(essai.changed_files(self.copie, {nom: "posé"}), {})


if __name__ == "__main__":
    unittest.main()
