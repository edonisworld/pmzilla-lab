"""Correspondance posture -> domaines de la bibliothèque : l'outil et le tableau des postures de CLAUDE.md : tâche 3.3."""
import re
import unittest
from pathlib import Path

import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parents[2] / "tools"))
import book_usage  # noqa: E402

RACINE = Path(__file__).resolve().parents[2]


def table_des_postures(texte: str) -> dict:
    """{posture : domaines} lu dans la table « The five postures » (colonne « Library domains »)."""
    domaines = {}
    for ligne in texte.splitlines():
        cellules = [c.strip() for c in ligne.strip().strip("|").split("|")]
        if len(cellules) == 4 and cellules[0] in ("Discovery", "Delivery", "Scaling", "Facilitation", "Critic"):
            domaines[cellules[0]] = tuple(re.findall(r"`([^`]+)`", cellules[3]))
    return domaines


def ecarts_de_domaines(lu: dict) -> list:
    return [p for p in book_usage.POSTURES if sorted(book_usage.DOMAINS[p]) != sorted(lu.get(p, ()))]


class Correspondance(unittest.TestCase):
    def test_le_tableau_de_claude_md_est_lu(self):
        lu = table_des_postures((RACINE / "CLAUDE.md").read_text(encoding="utf-8"))
        self.assertEqual(set(lu), {"Discovery", "Delivery", "Scaling", "Facilitation", "Critic"})
        self.assertEqual(lu["Delivery"], ("flow", "tech"))

    def test_la_correspondance_de_l_outil_suit_claude_md(self):
        lu = table_des_postures((RACINE / "CLAUDE.md").read_text(encoding="utf-8"))
        ecarts = ecarts_de_domaines(lu)
        self.assertEqual(ecarts, [], f"posture(s) dont les domaines diffèrent de CLAUDE.md : {ecarts}")

    def test_ecart_nomme(self):
        lu = {"Discovery": ("produit",), "Delivery": ("flow", "tech"), "Scaling": ("flow",), "Facilitation": ("facilitation",)}
        self.assertEqual(ecarts_de_domaines(lu), ["Scaling"])
        self.assertEqual(table_des_postures("| a | b | c | d | e |\n"), {})
