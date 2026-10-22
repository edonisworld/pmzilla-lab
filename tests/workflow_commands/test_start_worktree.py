"""finish-under-lock, D7 et D18 (tâches 9.1 et 9.3) : /start crée le worktree du job et passe la main à une session ouverte dedans ;
/implement refuse de démarrer dans l'espace de travail sur main ; la passation donne toujours la fin en worktree."""
import re
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
START = RACINE / ".claude" / "commands" / "start.md"
IMPLEMENT = RACINE / ".claude" / "commands" / "implement.md"


def entete_et_corps(chemin: Path) -> tuple[str, str]:
    texte = chemin.read_text(encoding="utf-8")
    morceaux = texte.split("---", 2)
    return morceaux[1], morceaux[2]


def outils_permis(entete: str) -> str:
    trouve = re.search(r"^allowed-tools:(.*)$", entete, re.M)
    return trouve.group(1) if trouve else ""


class StartEnWorktree(unittest.TestCase):
    def setUp(self):
        self.entete, self.corps = entete_et_corps(START)

    def test_entete_permet_le_script_de_worktree_et_pas_checkout(self):
        outils = outils_permis(self.entete)
        self.assertIn("Bash(bash tools/worktree.sh:*)", outils)
        self.assertNotIn("git checkout -b", outils)

    def test_corps_cree_le_worktree_et_s_arrete(self):
        self.assertIn("bash tools/worktree.sh <branch>", self.corps)
        self.assertIn("never `git checkout -b`", self.corps)
        self.assertRegex(self.corps, r"then stop\.")
        self.assertIn("`/start <id>`", self.corps)
        self.assertIn("Do no work in the worktree from the workspace session", self.corps)

    def test_refus_du_script_de_worktree(self):
        self.assertIn("If the worktree script refuses, report its refusal line and stop without changing the Status", self.corps)

    def test_passation_donne_toujours_la_fin_en_worktree(self):
        passation = self.corps.split("## 5. Hand over", 1)[1].split("##", 1)[0]
        self.assertIn("`bash tools/finish_worktree.sh <branch>`", passation)
        self.assertIn("for every job", passation)
        self.assertNotIn("`bash tools/finish_branch.sh`", passation)


class ImplementRefuseDansLEspace(unittest.TestCase):
    def setUp(self):
        self.entete, self.corps = entete_et_corps(IMPLEMENT)

    def test_refus_sur_main_dans_l_espace(self):
        self.assertIn("If the current branch is `main` in the workspace, refuse", self.corps)
        self.assertIn("bash tools/worktree.sh feat/<change>", self.corps)
        self.assertIn("write nothing and change no Status", self.corps)

    def test_entete_sans_checkout(self):
        self.assertNotIn("git checkout -b", outils_permis(self.entete))


if __name__ == "__main__":
    unittest.main()
