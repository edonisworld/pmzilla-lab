"""Aide des tests de `npm ci` (change npm-ci-session) : un dépôt jetable dans un dossier temporaire, avec un dépôt nu pour `origin`, un
worktree lié sous un dossier des worktrees de test (passé en paramètre, jamais par une variable d'environnement) et un faux verrou de fin
dans le dossier Git commun. Aucun test ne lance npm, node ni le réseau : les seules commandes lancées sont des commandes Git sur des
dossiers temporaires.
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import npm_ci_conditions  # noqa: E402
import npm_guard  # noqa: E402

PAQUET = '{\n  "name": "mothra",\n  "scripts": {\n    "test": "node --test"\n  }\n}\n'
VERROU = '{\n  "name": "mothra",\n  "lockfileVersion": 3,\n  "packages": {}\n}\n'
IDENTITE = ["-c", "user.name=test", "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false"]


def env_git():
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def git(dossier, *arguments, ok=True):
    r = subprocess.run(["git", *IDENTITE, "-C", str(dossier), *arguments], capture_output=True, text=True, env=env_git(),
                       stdin=subprocess.DEVNULL, timeout=60)
    if ok and r.returncode != 0:
        raise AssertionError(f"git {arguments} : {r.stderr}")
    return r.stdout


class Depot:
    """Dépôt de travail `repo` (l'espace de travail, worktree principal), origine nue `origine.git`, worktrees de test sous `worktrees/`."""

    def __init__(self, base: Path):
        self.base = Path(os.path.realpath(base))
        self.repo = self.base / "repo"
        self.origine = self.base / "origine.git"
        self.worktrees = self.base / "worktrees"
        self.worktrees.mkdir()
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        self.ecrire(self.repo, "mothra/package.json", PAQUET)
        self.ecrire(self.repo, "mothra/package-lock.json", VERROU)
        self.ecrire(self.repo, "mothra/serveur/package.json", PAQUET)
        self.ecrire(self.repo, "mothra/serveur/package-lock.json", VERROU)
        self.ecrire(self.repo, "mothra/.gitignore", "node_modules/\nprive/\n")
        self.ecrire(self.repo, "README.md", "lab\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "départ")
        # Le dépôt nu sert d'origine déclarée ; refs/remotes/origin/main est posée comme le ferait un fetch, sans aucun transfert.
        subprocess.run(["git", "init", "-q", "--bare", str(self.origine)], check=True, capture_output=True, env=env_git())
        git(self.repo, "remote", "add", "origin", str(self.origine))
        git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        self.wt = self.nouveau_worktree("wt-feat-x", "feat/x")

    def nouveau_worktree(self, nom, branche, dossier=None):
        chemin = (dossier or self.worktrees) / nom
        git(self.repo, "worktree", "add", "-q", "-b", branche, str(chemin), "main")
        return Path(os.path.realpath(chemin))

    @staticmethod
    def ecrire(racine, chemin, texte):
        cible = Path(racine) / chemin
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(texte, encoding="utf-8")

    def valider(self, racine, message="changement"):
        git(racine, "add", "-A")
        git(racine, "commit", "-q", "-m", message)

    @property
    def commun(self):
        return self.repo / ".git"

    def verrou_de_fin(self, vivant=True):
        dossier = self.commun / npm_ci_conditions.NOM_VERROU
        dossier.mkdir()
        (dossier / "pid").write_text(str(os.getpid() if vivant else 2 ** 22 + 12345), encoding="utf-8")
        (dossier / "debut").write_text(str(int(time.time()) if vivant else 1), encoding="utf-8")   # vivant : récent ; périmé : processus absent
        (dossier / "branche").write_text("feat/autre", encoding="utf-8")
        return dossier


class AvecDepot(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.depot = Depot(Path(self._tmp.name))
        self.wt = self.depot.wt
        self.mothra = self.wt / "mothra"

    def entree(self, commande, cwd=None):
        donnees = {"tool_name": "Bash", "tool_input": {"command": commande}}
        if cwd is not None:
            donnees["cwd"] = str(cwd)
        return json.dumps(donnees)

    def lancer(self, commande, cwd="par défaut", worktrees="par défaut"):
        """(code, sortie d'erreur) du crochet, en processus ; le dossier des worktrees de test est un paramètre de main."""
        cwd = self.mothra if cwd == "par défaut" else cwd
        worktrees = self.depot.worktrees if worktrees == "par défaut" else worktrees
        erreur = io.StringIO()
        with contextlib.redirect_stderr(erreur), contextlib.redirect_stdout(io.StringIO()) as sortie:
            code = npm_guard.main([], self.entree(commande, cwd), worktrees=worktrees)
        self.assertEqual(sortie.getvalue(), "")
        return code, erreur.getvalue()
