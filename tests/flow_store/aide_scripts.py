"""Aide des tests de bout en bout des outils de rapport sur la base jetable (change database-only, D11).

    bash tools/dbtest.sh flow_store          (instance jetable : installation.md, 14.5 ; sautés sans elle)

Les outils lisent la base seule : plus de comparaison avec une voie CSV (les tests de parité ont été retirés avec elle). Ce module ne
garde que les aides communes : lancer un outil sur un dossier de flux isolé (PMZILLA_LAB_WORKSPACE), lire les rapports écrits, un dossier
temporaire par test. La variable de session Claude Code est retirée de l'environnement des sous-processus : ces tests se lancent depuis
le Terminal de l'utilisateur, où statuses, compute, diagnose et cycles sont permis.
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import aide_base as base

TOOLS = base.TOOLS
FLUX = TOOLS / "flux_jira.py"
DEPENDANCES = TOOLS / "dependencies_jira.py"
AUJOURDHUI = dt.date.today().isoformat()
FAUX_MOT_DE_PASSE = "FauxMotDePasse-5d2a77c1"


def lancer(script: Path, workspace: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    environnement = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    environnement.update({"PMZILLA_LAB_WORKSPACE": str(workspace), **(env or {})})
    return subprocess.run(["uv", "run", str(script), *args], env=environnement, capture_output=True, text=True)


def rapports(workspace: Path) -> dict[str, str]:
    dossier = workspace / "Flux-Lab" / "rapports"
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(dossier.iterdir())}


class AvecDossier(unittest.TestCase):
    def dossier(self) -> Path:
        chemin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, chemin, ignore_errors=True)
        return chemin
