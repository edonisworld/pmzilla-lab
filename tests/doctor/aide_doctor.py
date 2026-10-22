"""Fixture commun de la suite tests/doctor (design D11) : un faux laboratoire dans un dossier temporaire, en bonne santé par défaut.

Chaque sonde du doctor est redirigée : données, journaux, date, heure et dossier personnel par variables d'environnement ;
Ollama par un faux serveur local ; la base par un socket local ; launchctl, git et osascript par des doublures placées en tête du
PATH (journal des appels dans $STUB_LOG) ; `security`, `psql` et `docker` par des doublures qui échouent et qui ne doivent jamais
être appelées. Aucun réseau, aucun Docker, aucun Trousseau, aucune vraie session launchd. Rien n'est écrit hors du dossier temporaire.
"""
import atexit
import contextlib
import io
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[2]
TOOLS = RACINE / "tools"
DOCTOR = TOOLS / "doctor.py"
sys.path.insert(0, str(TOOLS))

import doctor  # noqa: E402

SENTINELLE = "SENTINELLE-CONTENU-DE-SAUVEGARDE-9f3a"
AUJOURDHUI = "2026-10-14"
HEURE = "10:00"
SCHEMAS = ("knowledge", "cases", "flow", "quality-sans-texte")   # les dumps de tools/db_backup.sh, dump partiel de quality compris
MODELES = {"embedding": None, "watch triage": None}   # remplis par modeles_du_depot()


def modeles_du_depot() -> list[str]:
    """Les noms de modèles que le doctor doit trouver : ceux des constantes du dépôt (jamais écrits en dur dans les tests)."""
    import install_lab_context
    return [nom for _, nom, _ in install_lab_context.modeles_ollama(RACINE)]


def gabarits_launchd() -> list[str]:
    return sorted(p.stem for p in (TOOLS).glob("com.pmzilla.*.plist"))


_MODELE = []


def modele_du_depot() -> Path:
    """Le dépôt principal du faux laboratoire et son dossier d'exécution (worktree détaché au sommet de main, D3), construits une
    seule fois par processus dans un dossier temporaire, puis copiés par test."""
    if not _MODELE:
        racine = Path(tempfile.mkdtemp(prefix="doctor-modele."))
        atexit.register(shutil.rmtree, racine, ignore_errors=True)
        principal = racine / "PMZilla-Lab" / "workspace"
        principal.mkdir(parents=True)
        git(principal, "init", "-q", "-b", "main")
        (principal / "a.txt").write_text("a", encoding="utf-8")
        git(principal, "add", "a.txt")
        git(principal, "commit", "-q", "-m", "initial", env={"GIT_COMMITTER_DATE": "2026-10-13T08:00:00", "GIT_AUTHOR_DATE": "2026-10-13T08:00:00"})
        git(principal, "worktree", "add", "-q", "--detach", str(racine / "PMZilla-Lab" / "run"), "main")
        _MODELE.append(racine)
    return _MODELE[0]


class FauxOllama:
    def __init__(self, modeles):
        self.modeles = list(modeles)
        self.requetes: list[tuple[str, str]] = []
        fixture = self

        class Gestionnaire(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _repondre(self):
                fixture.requetes.append((self.command, self.path))
                if self.command == "GET" and self.path == "/api/tags":
                    corps = json.dumps({"models": [{"name": m} for m in fixture.modeles]}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(corps)
                else:
                    self.send_response(404)
                    self.end_headers()

            do_GET = do_POST = do_DELETE = do_PUT = _repondre

        self.serveur = ThreadingHTTPServer(("127.0.0.1", 0), Gestionnaire)
        self.port = self.serveur.server_address[1]
        self.fil = threading.Thread(target=lambda: self.serveur.serve_forever(poll_interval=0.01), daemon=True)
        self.fil.start()
        self.actif = True

    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def arreter(self):
        if self.actif:
            self.serveur.shutdown()
            self.serveur.server_close()
            self.actif = False


def git(dossier, *args, env=None, check=True):
    environnement = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                     "GIT_COMMITTER_EMAIL": "t@t", **(env or {})}
    return subprocess.run(["git", "-C", str(dossier), *args], capture_output=True, text=True, env=environnement, check=check)


class Labo(unittest.TestCase):
    """Classe de base : un laboratoire en bonne santé dans self.base, que chaque test dégrade d'un seul point."""

    TACHES = "une"      # tâches launchd installées dans l'état sain : « une » (chaque contrôle lance une doublure par tâche) ou « toutes »

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="doctor-test."))
        self.addCleanup(shutil.rmtree, self.base, ignore_errors=True)
        self.maison = self.base / "maison"
        self.donnees = self.maison / ".pmzilla-lab"
        self.journaux = self.maison / "Library" / "Logs"
        self.agents = self.maison / "Library" / "LaunchAgents"
        self.bin = self.base / "bin"
        self.journal_appels = self.base / "appels.log"
        self.flux = self.base / "flux.yaml"
        self.principal = self.maison / "PMZilla-Lab" / "workspace"   # le dossier du lab (parent) porte le dossier d'exécution par défaut
        for d in (self.donnees, self.journaux, self.agents, self.bin):
            d.mkdir(parents=True)
        self.journal_appels.write_text("", encoding="utf-8")
        self.non_charges = self.base / "non-charges"
        self.non_charges.mkdir()
        self._doublures()
        self._depot_principal()
        self.ollama = FauxOllama(modeles_du_depot())
        self.addCleanup(self.ollama.arreter)
        self._base_de_donnees()
        self._etat_sain()

    # --- doublures et services factices -------------------------------------------------------------------------------
    def _doublures(self):
        git_reel = shutil.which("git")
        scripts = {
            "launchctl": 'echo "launchctl $*" >> "$STUB_LOG"\n'
                         'if [ "$1" = print ]; then label="${2##*/}"; [ -e "$STUB_NON_CHARGES/$label" ] && exit 113; exit 0; fi\nexit 0\n',
            "osascript": 'echo "osascript $*" >> "$STUB_LOG"\nexit 0\n',
            "git": f'echo "git $*" >> "$STUB_LOG"\nexec "{git_reel}" "$@"\n',
        }
        for nom in ("security", "psql", "docker", "pg_dump", "curl"):
            scripts[nom] = f'echo "INTERDIT {nom} $*" >> "$STUB_LOG"\nexit 1\n'
        for nom, corps in scripts.items():
            chemin = self.bin / nom
            chemin.write_text("#!/bin/sh\n" + corps, encoding="utf-8")
            chemin.chmod(0o755)

    def _depot_principal(self):
        """Copie du modèle (construit une fois par processus) à l'emplacement du lab, puis réparation des chemins absolus du worktree."""
        self.run = self.maison / "PMZilla-Lab" / "run"
        shutil.copytree(modele_du_depot() / "PMZilla-Lab", self.maison / "PMZilla-Lab", symlinks=True)
        git(self.principal, "worktree", "repair", str(self.run))

    def avancer_main(self, jour="2026-10-13"):
        """Un nouveau commit sur main, dans le dépôt principal : le dossier d'exécution est alors en retard."""
        (self.principal / "b.txt").write_text("b", encoding="utf-8")
        git(self.principal, "add", "b.txt")
        git(self.principal, "commit", "-q", "-m", "suite", env={"GIT_COMMITTER_DATE": f"{jour}T09:00:00", "GIT_AUTHOR_DATE": f"{jour}T09:00:00"})

    def ajouter_branche(self, nom, jour="2026-10-13", fusionnee=False, worktree=False):
        """Branche locale : fusionnée dans main (pointe sur main) ou avec un commit propre daté de `jour` ; avec ou sans worktree."""
        date = {"GIT_COMMITTER_DATE": f"{jour}T08:00:00", "GIT_AUTHOR_DATE": f"{jour}T08:00:00"}
        if worktree:
            dossier = self.base / f"wt-{nom.replace('/', '-')}"
            git(self.principal, "worktree", "add", "-q", "-b", nom, str(dossier), "main")
        else:
            dossier = None
            git(self.principal, "branch", nom, "main")
        if not fusionnee:
            cible = dossier or self.base / f"tmp-{nom.replace('/', '-')}"
            if not dossier:
                git(self.principal, "worktree", "add", "-q", str(cible), nom)
            (cible / f"{nom.replace('/', '-')}.txt").write_text(nom, encoding="utf-8")
            git(cible, "add", "-A")
            git(cible, "commit", "-q", "-m", nom, env=date)
            if not dossier:
                git(self.principal, "worktree", "remove", "--force", str(cible))
        return dossier

    def _base_de_donnees(self):
        # Le faux port accepte et referme chaque connexion : sans accept, la file d'attente (listen) se remplissait au fil des
        # lancements d'un même test et une connexion finissait refusée (test de parité à 8 lancements, rouge par intermittence).
        self.socket_base = socket.socket()
        self.socket_base.bind(("127.0.0.1", 0))
        self.socket_base.listen(64)
        self.port_base = self.socket_base.getsockname()[1]
        threading.Thread(target=self._accepter_base, args=(self.socket_base,), daemon=True).start()
        self.addCleanup(self.fermer_base)

    @staticmethod
    def _accepter_base(serveur):
        while True:
            try:
                connexion, _ = serveur.accept()
            except OSError:      # socket fermé par fermer_base : fin du fil
                return
            connexion.close()

    def fermer_base(self):
        # shutdown() avant close() : sous Linux, close() d'un socket en écoute pendant un accept() bloqué ne libère pas le port,
        # que le doctor voyait encore ouvert (premier passage de la CI locale, 2026-10-20).
        try:
            self.socket_base.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.socket_base.close()
        except OSError:
            pass

    # --- l'état sain --------------------------------------------------------------------------------------------------
    def _etat_sain(self):
        self.ecrire_journal_veille(AUJOURDHUI, "07:10", "ok")
        self.ecrire_repere("termine")
        self.ecrire_sauvegarde(AUJOURDHUI, SCHEMAS)
        self.ecrire_hors_mac(derniere_reussite="2026-10-13")
        self.ecrire_flux("2027-06-01")
        gabarits = gabarits_launchd()
        for etiquette in (gabarits if self.TACHES == "toutes" else gabarits[:1]):
            self.installer_tache(etiquette)

    def installer_tache(self, etiquette, charge=True):
        (self.agents / f"{etiquette}.plist").write_text("<plist/>", encoding="utf-8")
        marque = self.non_charges / etiquette
        if charge:
            marque.unlink(missing_ok=True)
        else:
            marque.write_text("", encoding="utf-8")

    def desinstaller_tache(self, etiquette):
        (self.agents / f"{etiquette}.plist").unlink(missing_ok=True)

    def ecrire_journal_veille(self, jour, heure, fin, supplement=""):
        """fin : « ok », « echec », « base » (injoignable), « tables » (absentes) ou « encours »."""
        lignes = [f"=== {jour} {heure} ==="]
        if fin == "base":
            lignes += [f"Base de données injoignable à {heure} : collecte, pré-tri, listes à lire et indexation du jour sautés, rien n'est écrit ailleurs."]
        elif fin == "tables":
            lignes += ["Tables de la veille absentes : collecte, pré-tri, listes à lire et indexation du jour sautés."]
        if supplement:
            lignes.append(supplement)
        if fin == "ok":
            lignes.append("=== Veille terminée sans erreur ===")
        elif fin in ("echec", "base", "tables"):
            etape = "base de données" if fin != "echec" else "collecte"
            lignes.append(f"=== Veille terminée avec 1 étape(s) en échec : {etape} ===")
        chemin = self.journaux / "pmzilla-watch.log"
        ancien = chemin.read_text(encoding="utf-8") if chemin.exists() else ""
        chemin.write_text(ancien + "\n".join(lignes) + "\n", encoding="utf-8")

    def ecrire_repere(self, etat, jour=AUJOURDHUI, **champs):
        """Repère du passage du jour (design D2), dans le dossier de données ; etat : commence, termine, echoue, reporte, interrompu."""
        repere = {"date": jour, "declencheur": "calendrier", "debut": "07:10", "fin": "07:40", "etat": etat, "code": 0,
                  "notifie": False, "essais": 0, "reprises": 0, **champs}
        (self.donnees / "veille-du-jour.json").write_text(json.dumps(repere), encoding="utf-8")

    def supprimer_repere(self):
        (self.donnees / "veille-du-jour.json").unlink(missing_ok=True)

    def poser_verrou(self):
        (self.donnees / "veille.verrou").mkdir(exist_ok=True)

    def vider_journal_veille(self):
        (self.journaux / "pmzilla-watch.log").unlink(missing_ok=True)

    def ecrire_sauvegarde(self, jour, schemas, suffixe=".dump"):
        dossier = self.donnees / "sauvegardes" / f"db-{jour}"
        dossier.mkdir(parents=True, exist_ok=True)
        for schema in schemas:
            (dossier / f"{schema}{suffixe}").write_text(SENTINELLE, encoding="utf-8")
        return dossier

    def ecrire_hors_mac(self, derniere_reussite="2026-10-13", configure=True):
        dossier = self.donnees / "offsite"
        shutil.rmtree(dossier, ignore_errors=True)
        if not configure:
            return
        dossier.mkdir(parents=True)
        (dossier / "configuration").write_text("volume=" + SENTINELLE + "\n", encoding="utf-8")
        (dossier / "statut").write_text(
            f"copy derniere_reussite={derniere_reussite} resultat=ok date=2026-10-13\nserie-db derniere_copie=db-2026-10-13\n"
            f"restore-test derniere_reussite=- resultat=ok date=2026-10-01\n", encoding="utf-8")

    def ecrire_flux(self, expiration, extra=""):
        lignes = []
        if expiration is not None:
            lignes.append(f"jira_token_expires: {expiration}")
        self.flux.write_text("\n".join(lignes) + "\n" + extra, encoding="utf-8")

    # --- lancement ----------------------------------------------------------------------------------------------------
    def environnement(self, **extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("DOCTOR_", "PMZILLA_LAB_"))}
        env.update({
            "HOME": str(self.maison), "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}", "STUB_LOG": str(self.journal_appels),
            "STUB_NON_CHARGES": str(self.non_charges), "PMZILLA_LAB_DATA": str(self.donnees), "PMZILLA_LAB_LOGS": str(self.journaux),
            "PMZILLA_LAB_TODAY": AUJOURDHUI, "PMZILLA_LAB_NOW": HEURE, "PMZILLA_LAB_WORKSPACE": str(self.principal),
            "PMZILLA_LAB_DB_PORT": str(self.port_base), "DOCTOR_OLLAMA_URL": self.ollama.url(), "DOCTOR_FLUX": str(self.flux),
            "DOCTOR_DISK_FREE_GB": "100", "UV_OFFLINE": "1",
        })
        env.update({k: str(v) for k, v in extra.items()})
        return env

    def lancer(self, *args, env=None, reel=False):
        """Lance le doctor. Par défaut dans le processus (point d'entrée `main`, environnement remplacé, sorties captées, dossier
        courant = la base temporaire) ; `reel=True` : un vrai processus, pour ce qui vise le lancement lui-même."""
        environnement = self.environnement(**(env or {}))
        if reel:
            return subprocess.run([sys.executable, str(DOCTOR), *args], capture_output=True, text=True, timeout=60,
                                  env=environnement, cwd=str(self.base))
        sortie, erreur = io.StringIO(), io.StringIO()
        courant = os.getcwd()
        os.chdir(self.base)
        try:
            with mock.patch.dict(os.environ, environnement, clear=True), \
                    contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreur):
                try:
                    code = doctor.main(list(args))
                except SystemExit as sortie_demandee:
                    code = sortie_demandee.code
        finally:
            os.chdir(courant)
        return subprocess.CompletedProcess([str(DOCTOR), *args], code, sortie.getvalue(), erreur.getvalue())

    def resultat_json(self, *args, env=None):
        p = self.lancer("--json", *args, env=env)
        return p, (json.loads(p.stdout) if p.stdout.strip().startswith("{") else None)

    def niveau(self, controle, *args, env=None):
        p, donnees = self.resultat_json(*args, env=env)
        self.assertIsNotNone(donnees, p.stdout + p.stderr)
        entrees = [c for c in donnees["checks"] if c["id"] == controle]
        self.assertEqual(len(entrees), 1, f"{controle} : {len(entrees)} entrée(s) dans {[c['id'] for c in donnees['checks']]}")
        return entrees[0]["level"], entrees[0], p

    def appels(self) -> list[str]:
        return self.journal_appels.read_text(encoding="utf-8").splitlines()

    def fichiers(self) -> dict[str, float]:
        """Empreinte (chemin -> date de modification) de tout ce qui est sous la base temporaire, sauf le journal des doublures."""
        return {str(p): p.stat().st_mtime_ns for p in self.base.rglob("*") if p.is_file() and p != self.journal_appels}
