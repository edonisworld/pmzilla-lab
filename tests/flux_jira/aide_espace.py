"""Aide des tests de flux_jira.py lancés dans le processus (R-58, groupe 9) : un dossier de flux jetable, un faux flow_store,
la sortie capturée. Aucun sous-processus, aucune base, aucun appel à Jira.

Le script lit ses chemins dans des variables du module (FLUX_DIR, CONFIG_FILE, REPORT_DIR) : on les redirige vers un dossier
temporaire, comme PMZILLA_LAB_WORKSPACE le fait pour les lancements en sous-processus.
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import chargeur_csv as chargeur  # noqa: E402  (fixtures CSV rendues comme la base les rend)
import flux_jira as fj  # noqa: E402


class AvecEspace(unittest.TestCase):
    """Dossier de flux jetable (self.flux, self.rapports) et lancement de main() dans le processus."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.espace = Path(tmp.name)
        self.flux = self.espace / "Flux-Lab"
        self.flux.mkdir()
        self.rapports = self.flux / "rapports"
        patch = mock.patch.multiple(fj, FLUX_DIR=self.flux, CONFIG_FILE=self.flux / "flux.yaml", REPORT_DIR=self.rapports)
        patch.start()
        self.addCleanup(patch.stop)
        env = mock.patch.dict(os.environ)          # statuses, compute et epics sont refusés dans une session Claude Code
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("CLAUDECODE", None)

    def ecrire(self, nom: str, texte: str) -> Path:
        chemin = self.flux / nom
        chemin.write_text(texte, encoding="utf-8")
        return chemin

    def lancer(self, *argv: str, store=None, brut=False) -> tuple[int | str | None, str, str]:
        """(code de sortie, stdout, stderr). Le faux `store` remplace flow_store (jamais de connexion).

        Pour `statuses` et `compute` sans `store`, les chemins .csv et la valeur de --history sont retirés de la ligne et un faux
        flow_store rend les structures de ces fixtures (chargeur de test, database-only D11), comme la base les rendrait ; avec
        brut=True, la ligne est donnée telle quelle (tests de refus)."""
        argv = list(argv)
        if store is None and not brut and argv and argv[0] in ("statuses", "compute"):
            ligne, csv_donnes, cache, i = [], [], None, 0
            while i < len(argv):
                a = argv[i]
                if a.endswith(".csv"):
                    csv_donnes.append(a)
                elif a == "--history":
                    ligne.append(a)
                    if i + 1 < len(argv) and not argv[i + 1].startswith("-") and not argv[i + 1].endswith(".csv"):
                        cache, i = argv[i + 1], i + 1
                else:
                    ligne.append(a)
                i += 1
            argv = ligne
            cache = cache or str(self.flux / "historique" / "transitions.json")
            store = faux_store(lire_tickets_flux=lambda settings: chargeur.lire_tickets_flux(settings, csv_donnes),
                               lire_historique=lambda settings: chargeur.lire_historique(settings, cache))
        sortie, erreur = io.StringIO(), io.StringIO()
        modules = {"flow_store": store} if store is not None else {}
        code = None
        with mock.patch.dict(sys.modules, modules), contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
            try:
                fj.main(list(argv))
            except SystemExit as arret:
                code = arret.code if arret.code is not None else 0
        return code, sortie.getvalue(), erreur.getvalue()

    def lire_rapport(self, nom: str) -> str:
        return (self.rapports / nom).read_text(encoding="utf-8")


def faux_store(**lecteurs) -> types.SimpleNamespace:
    return types.SimpleNamespace(**lecteurs)
