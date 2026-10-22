"""
Aide commune des tests du script d'installation (change install-script, design D20). Aucun effet réel :

  - HOME factice et racine de dépôt factice (HOME/PMZilla-Lab/workspace) dans un dossier temporaire ;
  - dossier de simulacres en tête du PATH : un simulacre par commande, qui journalise ses arguments dans un fichier d'appels ;
  - versions factices des scripts du dépôt (install_hooks.sh, install_links.sh, db_up.sh) qui journalisent aussi leurs arguments ;
  - l'orchestrateur et l'amorce RÉELS sont lancés, mais ne voient que ce décor (variable INSTALL_LAB_ROOT, HOME, PATH).

Les noms de modèle, de rôles et de service sont volontairement différents de ceux du dépôt (bge-test, gemma-test:1b, roles_test_*) : un test
qui les retrouve dans la sortie prouve que le script les lit dans les fichiers de configuration, et ne les écrit pas en dur.

Une étape qui a besoin d'un comportement particulier écrit son propre simulacre avec fx.simulacre(nom, corps) : le corps est du shell ;
les fichiers d'état partagés sont dans $INSTALL_LAB_ETAT (un fichier vide = « c'est fait »), le journal d'appels dans $INSTALL_LAB_APPELS.
"""
from __future__ import annotations

import hashlib
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE_REELLE = Path(__file__).resolve().parents[2]
TOOLS_REELS = RACINE_REELLE / "tools"
ORCHESTRATEUR = TOOLS_REELS / "install_lab.py"
AMORCE = TOOLS_REELS / "install_lab.sh"
PREFIXE = "install_lab: "

# commandes qui changent l'état de la machine : jamais appelées en passage à blanc (design D14, D16)
CHANGEMENTS = (
    ("brew", "install"), ("brew", "services"), ("brew", "tap"),
    ("ollama", "pull"), ("colima", "start"), ("colima", "stop"),
    ("docker", "compose", "up"), ("docker", "compose", "down"),
    ("launchctl", "bootstrap"), ("launchctl", "bootout"), ("launchctl", "kickstart"),
    ("claude", "mcp", "add"), ("claude", "mcp", "remove"),
    ("git", "clone"), ("curl",), ("xattr", "-c"), ("chmod",),
)
SCRIPTS_SANS_VERIFICATION = ("install_hooks.sh", "install_links.sh")
SOUS_COMMANDES_QUI_CHANGENT = ("create", "update")   # run_worktree.sh : status ne change rien


class Passage:
    """Résultat d'un lancement : code de sortie, sortie standard, erreur, journal d'appels depuis le début du décor."""
    def __init__(self, code: int, sortie: str, erreur: str, appels: list[str]):
        self.code, self.sortie, self.erreur, self.appels = code, sortie, erreur, appels

    @property
    def texte(self) -> str:
        return self.sortie + self.erreur

    def lignes(self) -> list[str]:
        return [l[len(PREFIXE):] if l.startswith(PREFIXE) else l for l in self.sortie.splitlines()]

    def appels_de(self, nom: str) -> list[str]:
        return [a for a in self.appels if a == nom or a.startswith(nom + " ")]


class Decor:
    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="install-lab-test-")).resolve()   # résolu : le module partagé résout le dossier de contenu
        self.maison = self.tmp / "home"
        self.racine = self.maison / "PMZilla-Lab" / "workspace"      # chemin attendu du clone (design D17)
        self.simulacres = self.tmp / "bin"
        self.etat = self.tmp / "etat"
        self.appels = self.tmp / "appels.log"
        for d in (self.maison, self.racine / "tools", self.simulacres, self.etat):
            d.mkdir(parents=True, exist_ok=True)
        self.appels.write_text("", encoding="utf-8")
        self._ecrire_depot_factice()
        # commandes toujours présentes sur une machine neuve (le PATH de repli /usr/bin:/bin ne doit jamais les servir pour de vrai)
        self.simulacre("uname", 'case "$1" in -m) echo arm64 ;; -s) echo Darwin ;; *) echo Darwin ;; esac')
        for nom in ("git", "curl", "xattr", "security"):
            self.simulacre(nom)

    # --- nettoyage --------------------------------------------------------------------------------------------------------
    def nettoyer(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- décor du dépôt factice ---------------------------------------------------------------------------------------------
    def _ecrire_depot_factice(self) -> None:
        tools = self.racine / "tools"
        (self.racine / ".git").mkdir(exist_ok=True)
        (self.racine / "watch").mkdir(exist_ok=True)
        # modèles et rôles lus dans les fichiers de configuration (valeurs factices, différentes de celles du dépôt)
        (tools / "pmzilla_lab_library.py").write_text('EMBED_MODEL = os.environ.get("PMZILLA_LAB_MODEL", "bge-test")\n', encoding="utf-8")
        (self.racine / "watch" / "tri.yaml").write_text("mode: filtre\nmodel: gemma-test:1b  # modèle Ollama\nlanguage: en\n", encoding="utf-8")
        (tools / "db.py").write_text(
            'SERVICE_TROUSSEAU = "pmzilla-test-db"\nROLES_AVEC_MOT_DE_PASSE = ("roles_test_a", "roles_test_b")\n', encoding="utf-8")
        # modèles launchd réels (le rendu est testé sur les vrais gabarits)
        for gabarit in ("com.pmzilla.watch.plist", "com.pmzilla.watch-catchup.plist", "com.pmzilla.db-backup.plist", "com.pmzilla.doctor.plist"):
            shutil.copy(TOOLS_REELS / gabarit, tools / gabarit)
        for nom in ("watch.sh", "db_backup.sh", "install_hooks.sh", "install_links.sh", "db_up.sh"):
            (tools / nom).write_text("#!/bin/sh\n", encoding="utf-8")
        # scripts du dépôt factices : journalisent leurs arguments ; fichiers d'état hooks-ok, links-ok, db-up, db-sans-mot-de-passe
        self._script_depot("install_hooks.sh", "hooks-ok")
        self._script_depot("install_links.sh", "links-ok")
        self._ecrire_db_up()
        self._ecrire_run_worktree()
        self.drapeau("runtree-ok")                       # machine avec dossier d'exécution propre ; un test le retire ou pose runtree-retard

    def _ecrire_run_worktree(self) -> None:
        """run_worktree.sh factice : status rend 0 (runtree-ok), 8 (runtree-retard) ou 4 (rien) ; create pose runtree-ok sauf runtree-create-echec."""
        corps = (
            "#!/bin/sh\n"
            'echo "run_worktree.sh $*" >> "$INSTALL_LAB_APPELS"\n'
            'case "$1" in\n'
            '  status) [ -e "$INSTALL_LAB_ETAT/runtree-retard" ] && exit 8; [ -e "$INSTALL_LAB_ETAT/runtree-ok" ] && exit 0; exit 4 ;;\n'
            '  create) [ -e "$INSTALL_LAB_ETAT/runtree-create-echec" ] && exit 1; : > "$INSTALL_LAB_ETAT/runtree-ok"; exit 0 ;;\n'
            '  *) exit 2 ;;\n'
            'esac\n')
        self._ecrire_executable(self.racine / "tools" / "run_worktree.sh", corps)

    def _script_depot(self, nom: str, drapeau: str) -> None:
        corps = (
            "#!/bin/sh\n"
            f'echo "{nom} $*" >> "$INSTALL_LAB_APPELS"\n'
            f'if [ "$1" = "--verify" ]; then [ -e "$INSTALL_LAB_ETAT/{drapeau}" ] && exit 0; exit 1; fi\n'
            f'[ -e "$INSTALL_LAB_ETAT/{nom}-echec" ] && exit 1\n'
            f': > "$INSTALL_LAB_ETAT/{drapeau}"\nexit 0\n')
        self._ecrire_executable(self.racine / "tools" / nom, corps)

    def _ecrire_db_up(self) -> None:
        corps = (
            "#!/bin/sh\n"
            'echo "db_up.sh $*" >> "$INSTALL_LAB_APPELS"\n'
            '[ -e "$INSTALL_LAB_ETAT/db-sans-mot-de-passe" ] && { echo "Mot de passe de la base introuvable"; exit 3; }\n'
            '[ -e "$INSTALL_LAB_ETAT/db-echec" ] && exit 1\n'
            ': > "$INSTALL_LAB_ETAT/db-up"\nexit 0\n')
        self._ecrire_executable(self.racine / "tools" / "db_up.sh", corps)

    @staticmethod
    def _ecrire_executable(chemin: Path, corps: str) -> None:
        chemin.write_text(corps, encoding="utf-8")
        chemin.chmod(0o755)

    # --- simulacres de commandes ---------------------------------------------------------------------------------------------
    def simulacre(self, nom: str, corps: str = "exit 0") -> None:
        """Crée la commande `nom` en tête du PATH : journalise « nom arguments » puis exécute `corps` (shell)."""
        texte = f'#!/bin/sh\necho "{nom} $*" >> "$INSTALL_LAB_APPELS"\n{corps}\n'
        self._ecrire_executable(self.simulacres / nom, texte)

    def retirer(self, nom: str) -> None:
        (self.simulacres / nom).unlink(missing_ok=True)

    def regles(self, nom: str, regles: list[tuple[str, int, str]], defaut: int = 0) -> None:
        """Simulacre piloté par des règles (motif contenu dans les arguments, code, sortie) ; la première qui correspond gagne."""
        cas = ""
        for motif, code, sortie in regles:
            cas += f'  *"{motif}"*) '
            cas += (f"printf '%s\\n' {shlex.quote(sortie)}; " if sortie else "") + f"exit {code} ;;\n"
        self.simulacre(nom, f'case "$*" in\n{cas}  *) exit {defaut} ;;\nesac')

    def drapeau(self, nom: str, present: bool = True) -> None:
        """Pose ou retire un fichier d'état (hooks-ok, links-ok, db-up, db-sans-mot-de-passe, ...)."""
        chemin = self.etat / nom
        if present:
            chemin.touch()
        else:
            chemin.unlink(missing_ok=True)

    def a_drapeau(self, nom: str) -> bool:
        return (self.etat / nom).exists()

    # --- lancement ------------------------------------------------------------------------------------------------------------
    def environnement(self, extra: dict | None = None, sans_terminal_ok: bool = True) -> dict:
        env = {
            "PATH": f"{self.simulacres}:/usr/bin:/bin", "HOME": str(self.maison), "USER": "testeur", "TMPDIR": str(self.tmp),
            "INSTALL_LAB_ROOT": str(self.racine), "PMZILLA_LAB_WORKSPACE": str(self.racine), "INSTALL_LAB_APPLICATIONS": str(self.tmp / "Applications"), "INSTALL_LAB_APPELS": str(self.appels), "INSTALL_LAB_ETAT": str(self.etat),
            "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
        }
        if sans_terminal_ok:
            env["INSTALL_LAB_TEST_NO_TTY_CHECK"] = "1"
        env.update(extra or {})
        return env

    def lancer(self, *args: str, reponses: str = "", env: dict | None = None, sans_terminal_ok: bool = True) -> Passage:
        """Lance l'orchestrateur réel (python) ; `reponses` : texte envoyé sur l'entrée standard, une réponse par ligne."""
        return self._lancer([sys.executable, "-B", str(ORCHESTRATEUR), *args], reponses, env, sans_terminal_ok)

    def lancer_amorce(self, *args: str, reponses: str = "", env: dict | None = None, depuis: Path | None = None) -> Passage:
        """Lance l'amorce réelle avec zsh. `depuis` : dossier du script (défaut : l'amorce réelle ; mettre la copie du décor pour
        qu'elle trouve la racine factice)."""
        script = depuis or AMORCE
        return self._lancer(["zsh", str(script), *args], reponses, env, True)

    def copier_amorce(self) -> Path:
        """Copie l'amorce réelle dans le dépôt factice et rend son chemin (elle déduit la racine de son emplacement)."""
        cible = self.racine / "tools" / "install_lab.sh"
        shutil.copy(AMORCE, cible)
        cible.chmod(0o755)
        return cible

    def _lancer(self, commande, reponses, env, sans_terminal_ok) -> Passage:
        avant = len(self.lire_appels())
        termine = subprocess.run(commande, input=reponses, capture_output=True, text=True, check=False, cwd=str(self.tmp),
                                 env=self.environnement(env, sans_terminal_ok), timeout=120)
        return Passage(termine.returncode, termine.stdout, termine.stderr, self.lire_appels()[avant:])

    def lire_appels(self) -> list[str]:
        return [l for l in self.appels.read_text(encoding="utf-8").splitlines() if l.strip()]

    # --- empreinte des dossiers factices (passage à blanc : rien ne change) -------------------------------------------------------
    def empreinte(self) -> dict:
        resultat = {}
        for base in (self.maison, self.racine):
            for chemin in sorted(base.rglob("*")):
                if chemin.is_file() and not chemin.is_symlink():
                    resultat[str(chemin)] = hashlib.sha256(chemin.read_bytes()).hexdigest()
                else:
                    resultat[str(chemin)] = "lien" if chemin.is_symlink() else "dossier"
        return resultat

    # --- contrôles réutilisables ----------------------------------------------------------------------------------------------------
    @staticmethod
    def est_changement(appel: str) -> bool:
        mots = appel.split()
        if not mots:
            return False
        for modele in CHANGEMENTS:
            if tuple(mots[:len(modele)]) == modele:
                return True
        if mots[0] in SCRIPTS_SANS_VERIFICATION:
            return "--verify" not in mots
        if mots[0] == "db_up.sh":
            return True
        if mots[0] == "run_worktree.sh":
            return len(mots) > 1 and mots[1] in SOUS_COMMANDES_QUI_CHANGENT
        if mots[0] == "uv" and "migrate" in mots:
            return "--dry-run" not in mots
        return False

    def appels_qui_changent(self, appels: list[str]) -> list[str]:
        return [a for a in appels if self.est_changement(a)]


class CasDeBase(unittest.TestCase):
    """Chaque test a un décor neuf. À la fin : le Trousseau n'a jamais été appelé, quel que soit le scénario (design D10, D20)."""
    def setUp(self):
        self.fx = Decor()
        self.addCleanup(self.fx.nettoyer)

    def tearDown(self):
        self.assertEqual([a for a in self.fx.lire_appels() if a.split()[0] == "security"], [],
                         "le script d'installation ne doit jamais appeler la commande du Trousseau")
