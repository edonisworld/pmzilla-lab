"""Fixture commun de la suite tests/pilot (change multi-session-piloting, design D11).

Un faux laboratoire dans un dossier temporaire : un dépôt « ws » (l'espace de travail) avec un dépôt distant nu, trois worktrees liés
(propre, sale, fusionné), un dossier d'exécution détaché, un faux instantané du lecteur de la file, une fausse liste de noms sensibles,
un faux fichier d'identifiants, une fausse liste de processus (PILOT_LSOF), une horloge (PILOT_NOW) et un intervalle de sondage
(PILOT_POLL_SECONDS) imposés. Un faux `gh` en tête du PATH note chaque appel dans $GH_LOG (aucun appel attendu).
Rien n'est lu ni écrit hors du dossier temporaire : jamais le vrai espace de travail, le vrai dossier Git commun, le vrai instantané
ni la vraie liste de noms sensibles.
"""
import atexit
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
PILOT = RACINE / "tools" / "pilot.py"
SOURCES = (RACINE / "tools" / "pilot.py", RACINE / "tools" / "pilot_messages.py")
sys.path.insert(0, str(RACINE / "tools"))

NOM_SENSIBLE = "Zorglub-Fictif"           # nom de la fausse liste
IDENTIFIANT = "identifiant-fictif-7q"      # identifiant du faux fichier d'identifiants
CLE_TICKET = "ABCD-123"
BRANCHE_PROPRE = "chore/spec-r12"
BRANCHE_SALE = "feat/demo-change"
BRANCHE_FUSIONNEE = "chore/r7-fini"
NOM_LOCK = "pmzilla-fin-en-cours"
JETON = "jeton-de-test-0123456789abcdef"

_TMP = []
atexit.register(lambda: [shutil.rmtree(d, ignore_errors=True) for d in _TMP])


def git(dossier, *args, env=None, check=True):
    e = dict(os.environ)
    e.update({"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
              "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.org", "GIT_COMMITTER_NAME": "t",
              "GIT_COMMITTER_EMAIL": "t@example.org", "GIT_TERMINAL_PROMPT": "0"})
    for v in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        e.pop(v, None)
    if env:
        e.update(env)
    r = subprocess.run(["git", "-C", str(dossier), *args], capture_output=True, text=True, env=e, stdin=subprocess.DEVNULL)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} : {r.stderr}")
    return r.stdout.strip()


def processus_mort():
    """Numéro d'un processus qui n'existe plus."""
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


class Labo:
    def __init__(self):
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="pilot-test-")))
        _TMP.append(str(self.tmp))
        self.lab = self.tmp / "lab"
        self.ws = self.lab / "ws"
        self.run = self.lab / "run"
        self.distant = self.tmp / "distant.git"
        self.donnees = self.tmp / "donnees"
        self.contenu_factice = self.tmp / "contenu"
        self.noms = self.tmp / "noms.txt"
        self.bin = self.tmp / "bin"
        self.gh_log = self.tmp / "gh.log"
        self.lsof = self.tmp / "lsof.txt"
        for d in (self.lab, self.donnees, self.contenu_factice / ".pmzilla", self.bin):
            d.mkdir(parents=True, exist_ok=True)
        self.noms.write_text(f"# fausse liste\n{NOM_SENSIBLE}\n", encoding="utf-8")
        (self.contenu_factice / ".pmzilla" / "identifiants.txt").write_text(IDENTIFIANT + "\n", encoding="utf-8")
        faux_gh = self.bin / "gh"
        faux_gh.write_text(f'#!/bin/sh\necho "gh $*" >> "{self.gh_log}"\nexit 1\n', encoding="utf-8")
        faux_gh.chmod(0o755)
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.distant)], check=True, capture_output=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.ws)], check=True, capture_output=True)
        (self.ws / "base.txt").write_text("base\n", encoding="utf-8")
        git(self.ws, "add", ".")
        git(self.ws, "commit", "-q", "-m", "base")
        git(self.ws, "remote", "add", "origin", str(self.distant))
        git(self.ws, "push", "-q", "origin", "main")
        self.commun = Path(git(self.ws, "rev-parse", "--path-format=absolute", "--git-common-dir"))
        self.wt_propre = self.lab / "wt-propre"
        self.wt_sale = self.lab / "wt-sale"
        self.wt_fusionne = self.lab / "wt-fusionne"
        git(self.ws, "worktree", "add", "-q", "-b", BRANCHE_PROPRE, str(self.wt_propre))
        (self.wt_propre / "propre.txt").write_text("p\n", encoding="utf-8")
        git(self.wt_propre, "add", ".")
        git(self.wt_propre, "commit", "-q", "-m", "travail propre")
        git(self.ws, "worktree", "add", "-q", "-b", BRANCHE_SALE, str(self.wt_sale))
        (self.wt_sale / "sale-un.txt").write_text("1\n", encoding="utf-8")
        (self.wt_sale / "sale-deux.txt").write_text("2\n", encoding="utf-8")
        git(self.ws, "worktree", "add", "-q", "-b", BRANCHE_FUSIONNEE, str(self.wt_fusionne))
        (self.wt_fusionne / "fini.txt").write_text("f\n", encoding="utf-8")
        git(self.wt_fusionne, "add", ".")
        git(self.wt_fusionne, "commit", "-q", "-m", "travail fini")
        git(self.ws, "merge", "-q", "--no-ff", "-m", "fusion", BRANCHE_FUSIONNEE)
        git(self.ws, "worktree", "add", "-q", "--detach", str(self.run), "main")
        self.ecrire_instantane()
        self.ecrire_lsof("")

    # --- décor -------------------------------------------------------------------------------------------------------------
    def ecrire_instantane(self, change="demo-change", numero=30):
        corps = f"```yaml\nid: R-{numero}\nchange: {change}\n```\n"
        issues = [{"number": 300 + numero, "title": f"R-{numero} · Démonstration", "body": corps, "state": "open", "labels": [],
                   "milestone": None, "parent": None, "blocked_by": [], "status": "In progress", "reason": ""}]
        (self.donnees / "roadmap-cache.json").write_text(
            json.dumps({"date": "2026-10-18", "issues": issues, "milestones": {}}), encoding="utf-8")

    def retirer_instantane(self):
        (self.donnees / "roadmap-cache.json").unlink()

    def ecrire_lsof(self, contenu):
        """Contenu imprimé par la fausse liste de processus (lignes p… et n… de lsof -F pn)."""
        self.lsof.write_text(contenu, encoding="utf-8")

    def lsof_commande(self):
        return f"cat {self.lsof}"

    def poser_verrou(self, pid=None, branche="feat/autre", debut=None, jeton=JETON, racine=None):
        dossier = (racine or self.commun) / NOM_LOCK
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "pid").write_text(f"{os.getpid() if pid is None else pid}\n", encoding="utf-8")
        (dossier / "debut").write_text(f"{int(time.time()) if debut is None else debut}\n", encoding="utf-8")
        (dossier / "branche").write_text(branche + "\n", encoding="utf-8")
        (dossier / "jeton").write_text(jeton + "\n", encoding="utf-8")
        return dossier

    def retirer_verrou(self):
        shutil.rmtree(self.commun / NOM_LOCK, ignore_errors=True)

    # --- lancement -----------------------------------------------------------------------------------------------------------
    def env(self, **extra):
        e = dict(os.environ)
        for v in ("FINISH_LOCK_TOKEN", "PMZILLA_FINISH_LOCK_MAX_AGE", "PILOT_NOW", "PILOT_LSOF", "PILOT_POLL_SECONDS",
                  "PILOT_WAIT_UNIT_SECONDS", "PMZILLA_LAB_RUN", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
            e.pop(v, None)
        e.update({
            "PATH": f"{self.bin}:{e.get('PATH', '')}",
            "PMZILLA_LAB_DATA": str(self.donnees),
            "PMZILLA_LAB_SENSITIVE_NAMES": str(self.noms),
            "PMZILLA_LAB_WORKSPACE": str(self.contenu_factice),
            "PILOT_LSOF": self.lsof_commande(),
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull, "GIT_TERMINAL_PROMPT": "0",
            "HOME": str(self.tmp / "maison"),
        })
        e.update(extra)
        return {k: v for k, v in e.items() if v is not None}

    def pilot(self, *args, cwd=None, env=None, timeout=60):
        r = subprocess.run([sys.executable, str(PILOT), *args], cwd=str(cwd or self.ws), capture_output=True, text=True,
                           env=env if env is not None else self.env(), stdin=subprocess.DEVNULL, timeout=timeout)
        return r

    def popen(self, *args, cwd=None, env=None):
        return subprocess.Popen([sys.executable, str(PILOT), *args], cwd=str(cwd or self.ws), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, env=env if env is not None else self.env(), stdin=subprocess.DEVNULL)

    # --- empreintes ------------------------------------------------------------------------------------------------------------
    def etat_git(self):
        """Condensé de tout ce que le dépôt commun garde (références, index, configuration, empreintes), notes et verrou exclus."""
        h = hashlib.sha256()
        for racine, dossiers, fichiers in os.walk(self.commun):
            dossiers[:] = sorted(d for d in dossiers if d not in ("pmzilla-notes", NOM_LOCK))
            for f in sorted(fichiers):
                chemin = Path(racine) / f
                h.update(str(chemin.relative_to(self.commun)).encode())
                try:
                    h.update(chemin.read_bytes())
                except OSError:
                    pass
        for wt in (self.ws, self.wt_propre, self.wt_sale, self.wt_fusionne):
            gitfile = wt / ".git"
            if gitfile.is_file():
                h.update(gitfile.read_bytes())
        return h.hexdigest()

    def appels_gh(self):
        return self.gh_log.read_text(encoding="utf-8") if self.gh_log.exists() else ""

    def fichiers_notes(self):
        d = self.commun / "pmzilla-notes"
        return sorted(p.name for p in d.iterdir()) if d.is_dir() else []

    def heure(self, debut):
        return time.strftime("%H:%M", time.localtime(debut))
