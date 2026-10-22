"""
Aide des tests de `story_quality.py report` (change story-quality-audit, tâches 3.10, 3.18, 3.21 et 3.24). Aucune base, aucun Jira,
aucune clé : le lecteur des vues, les réglages, la date, les identifiants personnels et le dossier des rapports sont remplacés. La
surcouche de l'essai est écrite dans le dossier de contexte temporaire (`ecrire`). L'outil réel est appelé dans le processus.
"""
from __future__ import annotations

import copy
import datetime as dt
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aide_story_quality import IDENTIFIANT_FICTIF, Espace  # noqa: E402  (pose aussi tools/ dans sys.path)
import story_quality_report as sr  # noqa: E402
from test_donnees_rapport import ALPHA, BETA, VUE_COUVERTURE, VUE_EQUIPE, VUE_PRODUIT  # noqa: E402,F401

DATE = dt.date(2026, 10, 20)
SEUIL_RECURRENCE = 0.45        # M4 (b) : 9 non satisfaits sur 20 audités pour story-un d'Alpha
SEUIL_MASQUAGE = 5


class EspaceRapport(Espace):
    """Espace de l'aide commune + trois vues de fixture, un dossier de rapports temporaire et des réglages fixes."""

    def setUp(self):
        super().setUp()
        self.rapports = Path(self.temp.name) / "rapports"
        self.environ[sr.REPORTS_VARIABLE] = str(self.rapports)
        self.vues = {"quality_by_team": VUE_EQUIPE, "quality_coverage_by_team": VUE_COUVERTURE, "quality_by_product": VUE_PRODUIT}
        self.vues_lues = []
        self.reglages = (SEUIL_RECURRENCE, SEUIL_MASQUAGE)

        def lire(vue):
            self.vues_lues.append(vue)
            return copy.deepcopy(self.vues[vue])

        for cible, remplacement in (("lire_vue", lire), ("reglages_rapport", lambda t: self.reglages), ("aujourdhui", lambda: DATE),
                                    ("identifiants", lambda: [IDENTIFIANT_FICTIF])):
            patch = mock.patch.object(sr, cible, remplacement)
            patch.start()
            self.addCleanup(patch.stop)

    def fichiers(self):
        return sorted(p.name for p in self.rapports.glob("*")) if self.rapports.exists() else []

    def rapport(self, nom="serie"):
        return (self.rapports / f"qualite-stories-{nom}-2026-10-20.md").read_text(encoding="utf-8")
