"""Fixture commun de la suite tests/doctor (design D11) : un faux laboratoire dans un dossier temporaire, en bonne santé par défaut.

Chaque sonde du doctor est redirigée : données, journaux, date, heure et dossier personnel par variables d'environnement ;
Ollama par un faux serveur local ; la base par un socket local ; launchctl, git et osascript par des doublures placées en tête du
PATH (journal des appels dans $STUB_LOG) ; `security`, `psql` et `docker` par des doublures qui échouent et qui ne doivent jamais
être appelées. Aucun réseau, aucun Docker, aucun Trousseau, aucune vraie session launchd. Rien n'est écrit hors du dossier temporaire.
"""
import atexit
import contextlib
import hashlib
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
import sandbox_config  # noqa: E402

SENTINELLE = "SENTINELLE-CONTENU-DE-SAUVEGARDE-9f3a"
AUJOURDHUI = "2026-10-14"
HEURE = "10:00"
SCHEMAS = ("knowledge", "cases", "flow", "quality-sans-texte")   # les dumps de tools/db_backup.sh, dump partiel de quality compris
VERSION_CLAUDE = "2.1.303"   # la version de la doublure `claude`, celle de l'essai du crochet PreToolUse dans l'état sain
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
        racine = Path(tempfile.mkdtemp(prefix="doctor-modele.")).resolve()   # R-20261111-16 : chemin réel (sous macOS /var est un lien vers /private/var)
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


def resume_attendu(avertissements: int = 0, langue: str = "fr") -> str:
    """Le résumé de fin attendu du doctor pour `avertissements` avertissement(s) propres au test.

    Dans l'arbre public de l'édition, le dossier des fichiers gérés n'est pas livré : le contrôle sandbox ajoute alors un avertissement (« fichier géré
    absent »), que le test ne peut pas poser. L'avertissement de plus n'est compté que si la source du fichier géré est absente de l'arbre testé.
    Remplace : rien. Retrait : tombe quand ce dossier est publié ou quand le contrôle sandbox ne signale plus l'absence (R-20261108-03).
    Source : la présence de sandbox_config.SOURCE_RELATIVE à la racine, la même que celle de Labo.ecrire_bac_a_sable."""
    if not (RACINE / sandbox_config.SOURCE_RELATIVE).is_file():
        # La tolérance ne joue que dans l'arbre public (manifeste absent) ; dans le dépôt privé, l'absence de la source est un échec.
        assert not (RACINE / "edition" / "manifest.yaml").is_file(), "la source du fichier géré est absente du dépôt privé (le manifeste de l'édition est présent)"
        avertissements += 1
    if langue == "en":
        return "doctor: all good" if avertissements == 0 else f"doctor: {avertissements} warning(s)"
    return "doctor : tout va bien" if avertissements == 0 else f"doctor : {avertissements} avertissement(s)"


def git(dossier, *args, env=None, check=True):
    environnement = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                     "GIT_COMMITTER_EMAIL": "t@t", **(env or {})}
    return subprocess.run(["git", "-C", str(dossier), *args], capture_output=True, text=True, env=environnement, check=check)


def depot_avec_crochet(dossier, conforme=True):
    """R-20261110-42 : un dépôt jetable dont le crochet reference-transaction est installé comme le fait tools/install_hooks.sh (lien relatif
    ../../tools/hooks/reference-transaction vers un fichier suivi exécutable) ; `conforme=False` : dépôt sans le lien. Le dossier est créé par l'appelant."""
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    git(dossier, "init", "-q", "-b", "main")
    source = dossier / "tools" / "hooks" / "reference-transaction"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    source.chmod(0o755)
    if conforme:
        (dossier / ".git" / "hooks").mkdir(exist_ok=True)
        (dossier / ".git" / "hooks" / "reference-transaction").symlink_to("../../tools/hooks/reference-transaction")
    return dossier


class Labo(unittest.TestCase):
    """Classe de base : un laboratoire en bonne santé dans self.base, que chaque test dégrade d'un seul point."""

    TACHES = "une"      # tâches launchd installées dans l'état sain : « une » (chaque contrôle lance une doublure par tâche) ou « toutes »

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="doctor-test.")).resolve()   # R-20261111-13 : chemin réel (sous macOS /var est un lien vers /private/var)
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
        self.depot_crochets = depot_avec_crochet(self.base / "depot-crochets")   # R-20261110-42 : le crochet conforme, dans l'état sain
        self._etat_sain()

    # --- doublures et services factices -------------------------------------------------------------------------------
    def _doublures(self):
        git_reel = shutil.which("git")
        scripts = {
            "launchctl": 'echo "launchctl $*" >> "$STUB_LOG"\n'
                         'if [ "$1" = print ]; then label="${2##*/}"; [ -e "$STUB_NON_CHARGES/$label" ] && exit 113; exit 0; fi\nexit 0\n',
            "osascript": 'echo "osascript $*" >> "$STUB_LOG"\nexit 0\n',
            "git": f'echo "git $*" >> "$STUB_LOG"\nexec "{git_reel}" "$@"\n',
            "claude": 'echo "claude $*" >> "$STUB_LOG"\n[ -n "${FAUX_CLAUDE_ABSENT:-}" ] && exit 127\n'
                      'echo "${FAUX_CLAUDE_VERSION:-' + VERSION_CLAUDE + '} (Claude Code)"\n',
        }
        # R-20261103-6 (Q9) : contrôle ci-container. colima : tourne (code FAUX_COLIMA_CODE, 0 par défaut) ; ci_local : doublure de
        # `bash tools/ci_local.sh cle` (DOCTOR_CI_LOCAL), image présente par défaut (code FAUX_CI_LOCAL_CODE) ; ni l'un ni l'autre n'appelle Docker.
        scripts["colima"] = 'echo "colima $*" >> "$STUB_LOG"\n[ -n "${FAUX_COLIMA_ABSENT:-}" ] && exit 127\nexit "${FAUX_COLIMA_CODE:-0}"\n'
        scripts["ci_local"] = 'echo "ci_local $*" >> "$STUB_LOG"\nexit "${FAUX_CI_LOCAL_CODE:-0}"\n'
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
        self.ecrire_essai_crochet(VERSION_CLAUDE, "lu")
        self.ecrire_bac_a_sable()
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

    def ecrire_essai_crochet(self, version, verdict):
        """État du dernier essai du crochet PreToolUse (tools/essai_crochet_pretooluse.sh), dans le dossier de données."""
        (self.donnees / "essai-crochet-pretooluse.json").write_text(
            json.dumps({"version": 1, "claude_version": version, "date": "2026-10-13", "verdict": verdict}), encoding="utf-8")

    def ecrire_bac_a_sable(self):
        """État sain du contrôle `sandbox` (change bash-sandbox-n2, D8) : un fichier géré égal à la source suivie dont « ~/ » est développé vers la
        maison factice, de propriétaire l'utilisateur du test et fermé en écriture au groupe et aux autres (le propriétaire root est remplacé par
        DOCTOR_SANDBOX_OWNER_UID), et les outils figés que la source exclut (familles réelles) égaux à leur relevé. Rien n'est écrit hors de la base temporaire."""
        self.fichier_gere = self.base / "gere" / "50-pmzilla-bac-a-sable.json"
        self.fichier_gere.parent.mkdir(parents=True, exist_ok=True)
        # Édition publique : config/gere/ n'est pas livré (R-20261108-03, question 11) ; le doctor dit « absent » et il n'y a rien à poser.
        # Remplace : rien. Retrait : tombe avec R-20261108-03.
        if not (RACINE / sandbox_config.SOURCE_RELATIVE).is_file():
            return
        # R-20261111-49, -51 (C1) : développé avec le dossier personnel de la base des comptes, pas avec la maison factice (HOME du doctor).
        contenu = sandbox_config.etendre(sandbox_config.lire_source(RACINE))
        self.fichier_gere.write_text(json.dumps(contenu, indent=2), encoding="utf-8")
        self.fichier_gere.chmod(0o644)
        self.figes = self.donnees / sandbox_config.DOSSIER_FIGES
        shutil.rmtree(self.figes, ignore_errors=True)
        self.figes.mkdir()
        lignes = []
        # Les familles réelles, tirées de la source comme le fait le code (une seule source des noms).
        for nom in sorted(sandbox_config.noms_figes_attendus(RACINE)):
            texte = f"#!/bin/sh\necho {nom}\n"
            (self.figes / nom).write_text(texte, encoding="utf-8")
            lignes.append(f"{hashlib.sha256(texte.encode()).hexdigest()}  {nom}")
        (self.figes / sandbox_config.RELEVE_FIGES).write_text("\n".join(lignes) + "\n", encoding="utf-8")

    # --- lancement ----------------------------------------------------------------------------------------------------
    def environnement(self, **extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("DOCTOR_", "PMZILLA_LAB_"))}
        env.update({
            "HOME": str(self.maison), "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}", "STUB_LOG": str(self.journal_appels),
            "STUB_NON_CHARGES": str(self.non_charges), "PMZILLA_LAB_DATA": str(self.donnees), "PMZILLA_LAB_LOGS": str(self.journaux),
            "PMZILLA_LAB_TODAY": AUJOURDHUI, "PMZILLA_LAB_NOW": HEURE, "PMZILLA_LAB_WORKSPACE": str(self.principal),
            "PMZILLA_LAB_DB_PORT": str(self.port_base), "DOCTOR_OLLAMA_URL": self.ollama.url(), "DOCTOR_FLUX": str(self.flux),
            "DOCTOR_DISK_FREE_GB": "100", "UV_OFFLINE": "1", "DOCTOR_CI_LOCAL": str(self.bin / "ci_local"),
            # contrôle sandbox : le fichier géré factice, son propriétaire attendu (l'utilisateur du test, pas root) et le minimum de version
            # ramené à celui de la doublure `claude` (VERSION_CLAUDE) ; les tests du contrôle les remplacent un à un.
            "DOCTOR_SANDBOX_FILE": str(self.fichier_gere), "DOCTOR_SANDBOX_OWNER_UID": str(os.getuid()),
            "DOCTOR_SANDBOX_MIN_VERSION": VERSION_CLAUDE, "DOCTOR_CROCHETS_DEPOT": str(self.depot_crochets),
        })
        env.update({k: str(v) for k, v in extra.items()})
        return env

    def lancer(self, *args, env=None, reel=False):
        """Lance le doctor. Par défaut dans le processus (point d'entrée `main`, environnement remplacé, sorties captées, dossier
        courant = la base temporaire) ; `reel=True` : un vrai processus, pour ce qui vise le lancement lui-même."""
        environnement = self.environnement(**(env or {}))
        if reel:
            # R-20261108-10 : variable vide, le doctor ignore le contrôle de l'interpréteur des crochets (le Mac réel n'est jamais lu) ;
            # sauf si le test la fixe lui-même. Remplace : rien. Retrait : avec le contrôle.
            environnement.setdefault("DOCTOR_INTERPRETEUR_CROCHETS", "")
            return subprocess.run([sys.executable, str(DOCTOR), *args], capture_output=True, text=True, timeout=60,
                                  env=environnement, cwd=str(self.base))
        sortie, erreur = io.StringIO(), io.StringIO()
        courant = os.getcwd()
        os.chdir(self.base)
        try:
            # R-20261108-10 : le contrôle de l'interpréteur des crochets lit le Mac ; ici il rend la clé conforme. Remplace : rien. Retrait : avec le contrôle.
            with mock.patch.dict(os.environ, environnement, clear=True), \
                    mock.patch.object(doctor, "verifier_interpreteur", return_value="ok"), \
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
