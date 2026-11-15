"""Aides communes des tests de la garde de session (change session-guard-n1). Pas de préfixe `test_` : le module n'est pas collecté seul.

Un arbre jetable reproduit la disposition du lab (dossier personnel, espace de travail, arbre de run, worktrees) avec des dossiers réels, pour que les
chemins résolus soient cohérents avec ceux de la garde. Aucune donnée réelle, aucun appel réseau.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import garde_session as g  # noqa: E402

COMPOSE = "name: pmzilla-lab\n\nservices:\n  db:\n    image: exemple\n    volumes:\n      - pgdata:/var/lib/postgresql\n\nvolumes:\n  pgdata:\n"
COMPOSE_AUTRE = COMPOSE.replace("pmzilla-lab", "autre-projet")


class Arbre:
    """Dossier personnel, espace de travail, arbre de run, un worktree et un dossier d'un autre projet compose, dans un dossier jetable."""

    def __init__(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="garde-session-"))
        self.home = os.path.join(self.tmp, "home")
        self.lab = os.path.join(self.home, "PMZilla-Lab")
        self.espace = os.path.join(self.lab, "workspace")
        self.run = os.path.join(self.lab, "run")
        self.wt = os.path.join(self.lab, "worktrees", "wt-feat-essai")
        self.autre = os.path.join(self.tmp, "autre-projet")
        for dossier in (self.espace, self.run, self.wt, self.autre):
            os.makedirs(dossier)
        for dossier, texte in ((self.espace, COMPOSE), (self.wt, COMPOSE), (self.autre, COMPOSE_AUTRE)):
            Path(dossier, "docker-compose.yml").write_text(texte, encoding="utf-8")

    def fermer(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def contexte(self, cwd=None, **options):
        options.setdefault("controle_configuration", False)
        return g.Contexte(cwd=cwd or self.espace, espace=self.espace, run=self.run, home=self.home, **options)

    def cle(self, commande, cwd=None, **options):
        """La clé du refus de la commande (par exemple « A1 »), ou None si elle passe."""
        v = g.decider(commande, self.contexte(cwd, **options))
        return v.cle if v else None
