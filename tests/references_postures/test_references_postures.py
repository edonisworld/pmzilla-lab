"""Les références des postures et le sanctum : ce qui doit rester vrai depuis que _bmad/memory/ n'est plus suivi.

    uv run --with pyyaml python -m unittest discover -s tests/references_postures -v

Le skill fait foi (.claude/skills/<posture>/ : modèles, références, scripts). Le sanctum (_bmad/memory/<posture>/) est
créé par init-sanctum.py, reste local et n'est pas suivi par Git. Ces tests vérifient : (1) qu'init-sanctum.py reproduit
les références du skill dans un sanctum neuf ; (2) qu'aucun fichier du sanctum n'est suivi et que .gitignore garde les
entrées du sanctum et du contexte local ; (3) que tools/sanctum_refresh.py est la voie pour remettre un sanctum à jour.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent.parent
POSTURES = ["pmzilla-delivery-bmad", "pmzilla-discovery-bmad", "pmzilla-scaling-bmad", "pmzilla-facilitation-bmad"]


def init_sanctum(posture: str, racine: Path) -> Path:
    skill = RACINE / ".claude" / "skills" / posture
    fait = subprocess.run([sys.executable, str(skill / "scripts" / "init-sanctum.py"), str(racine), str(skill)],
                          capture_output=True, text=True)
    assert fait.returncode == 0, fait.stderr or fait.stdout
    return racine / "_bmad" / "memory" / posture


class TestSanctumNeuf(unittest.TestCase):
    def test_references_du_skill_reproduites_par_init_sanctum(self):
        for posture in POSTURES:
            with self.subTest(posture=posture), tempfile.TemporaryDirectory() as temp:
                sanctum = init_sanctum(posture, Path(temp))
                skill = RACINE / ".claude" / "skills" / posture / "references"
                attendues = sorted(p.name for p in skill.glob("*.md") if p.name != "first-breath.md")
                self.assertGreaterEqual(len(attendues), 5, posture)
                for nom in attendues:
                    copie = sanctum / "references" / nom
                    self.assertTrue(copie.is_file(), f"{nom} absent d'un sanctum neuf")
                    self.assertEqual(copie.read_text(encoding="utf-8"), (skill / nom).read_text(encoding="utf-8"), nom)

    def test_un_sanctum_neuf_a_l_identite_et_le_vecu(self):
        for posture in POSTURES:
            with self.subTest(posture=posture), tempfile.TemporaryDirectory() as temp:
                sanctum = init_sanctum(posture, Path(temp))
                for nom in ("INDEX.md", "PERSONA.md", "CREED.md", "BOND.md", "MEMORY.md", "CAPABILITIES.md"):
                    self.assertTrue((sanctum / nom).is_file(), nom)


class TestSanctumHorsGit(unittest.TestCase):
    def test_aucun_fichier_du_sanctum_n_est_suivi(self):
        suivis = subprocess.run(["git", "ls-files", "_bmad/memory"], cwd=RACINE, capture_output=True, text=True).stdout
        self.assertEqual(suivis.strip(), "", "des fichiers du sanctum sont suivis par Git")

    def test_gitignore_garde_le_sanctum_et_le_contexte_local(self):
        lignes = (RACINE / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("/_bmad/memory/", lignes)
        self.assertIn("/.pmzilla/", lignes)

    def test_le_contexte_local_et_le_sanctum_sont_ignores_par_git(self):
        for chemin in ("_bmad/memory/pmzilla-delivery-bmad/MEMORY.md", ".pmzilla/contexte.md"):
            ignore = subprocess.run(["git", "check-ignore", "-q", chemin], cwd=RACINE).returncode
            self.assertEqual(ignore, 0, f"{chemin} n'est pas ignoré par Git")


if __name__ == "__main__":
    unittest.main()
