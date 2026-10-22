"""Noms des colonnes des réglages, sans base (R-103).

Cause observée le 2026-10-20 : `history_jira.py check` (avec ou sans --key) lit les réglages de flux.yaml tels quels, sans les colonnes
par défaut que flux_jira.py ajoute ; la lecture des tickets de la base cherchait alors la clé « colonnes » et s'arrêtait sur une KeyError.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import flow_store  # noqa: E402


class NomsColonnes(unittest.TestCase):
    def test_reglages_sans_colonnes(self):
        self.assertEqual(flow_store.noms_colonnes({}), {})

    def test_colonnes_vides(self):
        self.assertEqual(flow_store.noms_colonnes({"colonnes": None}), {})

    def test_premier_nom_de_chaque_colonne(self):
        reglages = {"colonnes": {"cle": ["Issue key", "Clé"], "etat": ["Status"], "vide": []}}
        self.assertEqual(flow_store.noms_colonnes(reglages), {"cle": "Issue key", "etat": "Status"})


if __name__ == "__main__":
    unittest.main()
