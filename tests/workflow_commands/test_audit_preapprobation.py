"""Commande /audit (.claude/commands/audit.md) : son en-tête ne pré-approuve ni un one-liner Python (`python -c`, `python -I -c`,
sous toute forme de lanceur) ni `find`. Aucune règle deny n'arrête `python -c` ni `find -exec` : une entrée pré-approuvée laisserait
un one-liner lire un chemin protégé sans demande d'accord (audit du 2026-10-20, R12). Aucun accès extérieur.

    python3 -m unittest discover -s tests/workflow_commands -v
"""
import re
import unittest
from pathlib import Path

AUDIT = Path(__file__).resolve().parents[2] / ".claude" / "commands" / "audit.md"

# Un one-liner Python : python, python3 ou python3.x, précédé ou non d'un lanceur (uv run, --with …), avec -c, éventuellement après -I ou
# d'autres options courtes.
PYTHON_C = re.compile(r"\bpython(\d(\.\d+)?)?\b(\s+-[A-Za-z]+)*\s+-[A-Za-z]*c\b")
FIND = re.compile(r"Bash\(\s*find\b")


def en_tete() -> str:
    texte = AUDIT.read_text(encoding="utf-8")
    morceaux = texte.split("---", 2)
    return morceaux[1] if len(morceaux) == 3 else ""


def outils_permis() -> list:
    for ligne in en_tete().splitlines():
        if ligne.startswith("allowed-tools:"):
            return [o.strip() for o in re.split(r",\s*(?![^()]*\))", ligne.partition(":")[2]) if o.strip()]
    return []


class LaGardeElleMeme(unittest.TestCase):
    """Les motifs reconnaissent les formes visées et laissent passer les autres."""

    def test_formes_python_c_reconnues(self):
        for texte in ("Bash(uv run --with pyyaml python -I -c:*)", "Bash(python3 -c:*)", "Bash(python -c:*)",
                      "Bash(uv run python -c:*)", "Bash(python3.12 -I -c:*)", "Bash(python -Ic:*)"):
            self.assertTrue(PYTHON_C.search(texte), texte)

    def test_formes_permises_non_reconnues(self):
        for texte in ("Bash(uv run tools/identifiants_personnels.py:*)", "Bash(git log:*)", "Bash(python3 -m unittest:*)"):
            self.assertFalse(PYTHON_C.search(texte), texte)

    def test_find_reconnu(self):
        self.assertTrue(FIND.search("Bash(find:*)"))
        self.assertTrue(FIND.search("Bash( find .:*)"))
        self.assertFalse(FIND.search("Bash(git grep:*)"))


class EnTeteDeAudit(unittest.TestCase):

    def test_l_en_tete_est_lu(self):
        self.assertTrue(outils_permis(), "allowed-tools introuvable dans l'en-tête de audit.md")

    def test_aucun_one_liner_python_pre_approuve(self):
        fautifs = [o for o in outils_permis() if PYTHON_C.search(o)]
        self.assertEqual(fautifs, [], "un one-liner Python ne se pré-approuve pas : il demande l'accord de l'utilisateur")

    def test_find_n_est_pas_pre_approuve(self):
        fautifs = [o for o in outils_permis() if FIND.search(o)]
        self.assertEqual(fautifs, [], "find ne se pré-approuve pas (find -exec n'est arrêté par aucune règle deny)")


if __name__ == "__main__":
    unittest.main()
