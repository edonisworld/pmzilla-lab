"""
Aide des tests de tools/finish_checks.py (change finish-train-foundations, groupe 3) : un dépôt Git jetable avec un dépôt distant nu pour
« origin », des copies de modules de tools/ (la fin unitaire tools/finish_branch.sh, retirée par B9, n'y est plus), une copie du module de contrôles, de fausses listes et de
faux dossiers de données. Bibliothèque standard seulement, plus Git et le bash du système. Aucun réseau, aucune base, aucun vrai nom.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
OUTILS = RACINE / "tools"
BASH = "/bin/bash" if os.access("/bin/bash", os.X_OK) else "bash"

# modules que la fin unitaire sourçait ou lançait en mode vérification, gardés comme copies du dépôt jetable (finish_branch.sh, light_finish.sh et
# light_validate.py, retirés par B9, n'y sont plus)
COPIES_SCRIPT = ("run_worktree.sh", "lab_paths.sh", "finish_env.sh", "finish_lock.sh", "finish_merge.sh",
                 "select_suites.py", "morning_state.sh", "posture_eval_fingerprint.py")
# le module de contrôles et ce qu'il importe
COPIES_MODULE = ("finish_checks.py", "lab_paths.py", "posture_eval_fingerprint.py")

LISTE_E2E = "finish_e2e_paths.txt"
LISTE_DB = "finish_db_paths.txt"   # la liste des chemins de la base (finish-single-b3-b6, D15) : lue par le contrôle 14 du module
LISTE_RUNNER = "finish_runner_paths.txt"   # la liste des chemins du runner et de la preuve (autonomous-trains-merge, D3)
LISTE_JEU = "# liste fictive des fichiers évalués\nCLAUDE.md\n.claude/skills/pmzilla-*\ntests/postures/vocabulaire.yaml\ntests/postures/memoire\n"
LISTE_PROTEGEE = ("# liste fictive de l'outillage protégé\ntools/hooks/\ntools/finish_branch.sh\ntools/finish_protected.txt\n"
                  "tests/run_all.sh\n")


def environnement(dossier: Path) -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("FINISH_", "PMZILLA_", "GIT_")) and k != "CLAUDECODE"}
    env.update({"GIT_CONFIG_GLOBAL": str(dossier / "gitconfig"), "GIT_CONFIG_SYSTEM": "/dev/null", "GIT_TERMINAL_PROMPT": "0",
                "PMZILLA_LAB_DATA": str(dossier / "data"), "FINISH_BRANCH_RECORDS": str(dossier / "data" / "essais"),
                "PMZILLA_LAB_SENSITIVE_NAMES": str(dossier / "noms-fictifs.txt")})
    return env


class Depot:
    """Dépôt de travail (branche main, poussée sur « origin », un dépôt nu) et ses faux dossiers, dans un dossier temporaire."""

    def __init__(self, dossier: Path, liste_jeu: bool = True, protegee: bool = True, module: bool = True, script: bool = True,
                 liste_e2e: bool = True, liste_db: bool = True, liste_runner: bool = True):
        self.dossier = Path(dossier)
        self.travail = self.dossier / "travail"
        self.distant = self.dossier / "distant.git"
        self.data = self.dossier / "data"
        self.env = environnement(self.dossier)
        (self.dossier / "noms-fictifs.txt").write_text("Vexillonia\n", encoding="utf-8")
        (self.dossier / "gitconfig").write_text("[user]\n\temail = t@example.org\n\tname = test\n[init]\n\tdefaultBranch = main\n",
                                                encoding="utf-8")
        self.data.mkdir()
        (self.data / "essais").mkdir()
        self.git("init", "-q", "--bare", str(self.distant), cwd=self.dossier)
        self.git("init", "-q", str(self.travail), cwd=self.dossier)
        self.git("remote", "add", "origin", str(self.distant))
        fichiers = {
            "tools/outil.sh": "base\n", "CLAUDE.md": "c\n", ".claude/skills/pmzilla-x/SKILL.md": "s\n",
            "tests/postures/vocabulaire.yaml": "v\n", "tests/postures/memoire/m.md": "m\n", "tests/run_all.sh": "r\n",
            "openspec/changes/archive/.gitkeep": "a\n", "openspec/changes/a/p.md": "a\n", "openspec/changes/b/p.md": "b\n",
            "db/001.sql": "SELECT 1;\n", "tools/db_x.py": "x = 1\n", "tools/hooks/pre-commit": "#!/bin/sh\n", ".gitignore": "ignore.log\n",
        }
        if liste_jeu:
            fichiers["tests/postures/fichiers-evalues.txt"] = LISTE_JEU
        if protegee:
            fichiers["tools/finish_protected.txt"] = LISTE_PROTEGEE
        for nom, contenu in fichiers.items():
            self.ecrire(nom, contenu)
        if liste_e2e:   # entrée d'essai seulement (finish-e2e-proof-shared, décision R-20261029-29) : la vraie liste des chemins d'interface
            self.copier(OUTILS / LISTE_E2E, f"tools/{LISTE_E2E}")
        if liste_db:    # entrée d'essai seulement (finish-single-b3-b6, D15) : la vraie liste des chemins de la base
            self.copier(OUTILS / LISTE_DB, f"tools/{LISTE_DB}")
        if liste_runner:   # entrée d'essai seulement (autonomous-trains-merge, D3 ; R-20261106-32) : la vraie liste des chemins du runner et de la preuve, que « branch » lit
            self.copier(OUTILS / LISTE_RUNNER, f"tools/{LISTE_RUNNER}")
        if script:
            for nom in COPIES_SCRIPT:
                self.copier(OUTILS / nom, f"tools/{nom}")
        if module:
            for nom in COPIES_MODULE:
                self.copier(OUTILS / nom, f"tools/{nom}")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "initial")
        self.git("push", "-q", "origin", "main")

    # --- Git
    def git(self, *args, cwd=None, verifie=True):
        fait = subprocess.run(["git", *args], cwd=cwd or self.travail, env=self.env, capture_output=True, text=True)
        if verifie and fait.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} : {fait.stderr}")
        return fait.stdout.strip()

    def ecrire(self, chemin: str, contenu: str):
        fichier = self.travail / chemin
        fichier.parent.mkdir(parents=True, exist_ok=True)
        fichier.write_text(contenu, encoding="utf-8")

    def copier(self, source: Path, chemin: str):
        fichier = self.travail / chemin
        fichier.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source, fichier)

    def commit(self, fichiers: dict, message: str = "travail"):
        """Écrit les fichiers (contenu None : suppression), les ajoute et commite."""
        for chemin, contenu in fichiers.items():
            if contenu is None:
                (self.travail / chemin).unlink()
            else:
                self.ecrire(chemin, contenu)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def branche(self, nom: str, fichiers: dict, depuis: str = "main", revenir: bool = True):
        """Crée la branche depuis `depuis`, y commite les fichiers, puis revient sur main."""
        self.git("checkout", "-q", "-b", nom, depuis)
        sommet = self.commit(fichiers, f"travail de {nom}")
        if revenir:
            self.git("checkout", "-q", "main")
        return sommet

    def commun(self) -> Path:
        return Path(self.git("rev-parse", "--path-format=absolute", "--git-common-dir"))

    def arbre(self, rev: str) -> str:
        return self.git("rev-parse", f"{rev}^{{tree}}")

    def enregistrer_dbtest(self, arbre: str):
        with open(self.commun() / "pmzilla-dbtest-ok", "a", encoding="utf-8") as f:
            f.write(arbre + "\n")

    def enregistrer_e2e(self, arbre: str):
        with open(self.commun() / "pmzilla-e2e-ok", "a", encoding="utf-8") as f:
            f.write(arbre + "\n")

    def enregistrer_essai(self, nom: str, base: str, empreinte: str = None, dossier_essais=None, **champs):
        """Écrit un enregistrement complet, validant, non rejugé, en français ; `champs` remplace ou ajoute des clés."""
        donnees = {"date": nom, "base": base, "langue": "fr", "complet": True, "validant": True, "rejuge": False,
                   "cas": [{"id": "c1", "verifications": [{"critere": "a", "ok": True}, {"critere": "b", "ok": False}]}]}
        if empreinte:
            donnees["evaluated_fingerprint"] = empreinte
        donnees.update(champs)
        dossier = Path(dossier_essais or self.data / "essais") / nom
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "resultats.json").write_text(json.dumps(donnees), encoding="utf-8")

    def empreinte(self, rev: str) -> str:
        sys.path.insert(0, str(OUTILS))
        try:
            import posture_eval_fingerprint
            specs = posture_eval_fingerprint.read_list(LISTE_JEU)
            return posture_eval_fingerprint.fingerprint(self.travail, rev, specs)
        finally:
            sys.path.remove(str(OUTILS))

    # --- lancements
    def module(self, *args, repo=None, env=None):
        fait = subprocess.run([sys.executable, "-I", str(self.travail / "tools" / "finish_checks.py"), *args, "--repo", str(repo or self.travail)],
                              cwd=self.travail, env=env or self.env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        return fait.returncode, fait.stdout, fait.stderr

    def json_branche(self, branche: str, env=None):
        code, sortie, erreur = self.module("branch", branche, "--json", env=env)
        return code, json.loads(sortie)


class AvecDepot(unittest.TestCase):
    """Base des tests : un dépôt jetable par test (les options sont celles de Depot)."""
    OPTIONS: dict = {}

    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)
        self.depot = Depot(Path(self.dossier.name), **self.OPTIONS)

    def verdicts(self, resultat: dict) -> dict:
        return {c["id"]: c["verdict"] for c in resultat["controls"]}
