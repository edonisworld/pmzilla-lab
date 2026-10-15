"""
PMZilla Lab : contexte commun des étapes du script d'installation (change install-script, design D7, D12, D14 à D17).

Module importé par tools/install_lab.py et par les modules d'étapes (install_lab_*.py). Il ne se lance pas seul.

Règles que ce module impose à toutes les étapes :
  - les commandes sont appelées par leur nom (résolu par le PATH), jamais par un chemin absolu ;
  - une sonde (probe) ne change rien et tourne aussi en passage à blanc ; une action passe par act() ou ecrire() : confirmation
    (défaut non), ou simple affichage en passage à blanc ;
  - aucun mot de passe, aucun jeton : ce module n'appelle jamais la commande du Trousseau.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

PREFIXE = "install_lab: "
VARIABLE_RACINE = "INSTALL_LAB_ROOT"                    # remplace la racine du dépôt (tests)
VARIABLE_APPLICATIONS = "INSTALL_LAB_APPLICATIONS"      # remplace les dossiers d'applications, séparés par « : » (tests)
VARIABLE_SANS_TERMINAL = "INSTALL_LAB_TEST_NO_TTY_CHECK"  # pour les tests seulement : accepte une entrée standard qui n'est pas un terminal

# états d'une étape
FAIT = "done"
DEJA = "already"
REFUSE = "declined"
REPORTE = "deferred"
MANUEL = "manual"
ECHEC = "failed"
A_BLANC = "dry"          # passage à blanc : l'étape agirait
NON_LANCE = "not run"


@dataclass
class Resultat:
    etat: str
    detail: str = ""     # raison du report, commande manuelle, commande en échec


@dataclass
class Etape:
    """Une étape du tableau de l'orchestrateur (design D13, D14). `sonde(ctx)` rend True si l'étape est déjà faite (lecture seule) ;
    `executer(ctx)` rend un Resultat. `modes` : les modes qui ont cette étape (aujourd'hui « fresh » seulement). `depend` : noms des
    étapes qui doivent être faites (ou déjà faites) avant ; pour une étape lancée seule, leur sonde est interrogée."""
    nom: str
    modes: tuple
    depend: tuple
    sonde: object        # Callable[[Contexte], bool]
    executer: object     # Callable[[Contexte], Resultat]
    apres_tout: bool = False   # étape de fin (check) : reportée si une étape du même passage n'est ni faite ni déjà faite


@dataclass
class Contexte:
    racine: Path                       # racine du dépôt (le clone)
    maison: Path                       # dossier personnel de l'utilisateur
    mode: str = "fresh"
    a_blanc: bool = False
    etat: dict = field(default_factory=dict)       # drapeaux partagés entre étapes (runtime_ok, ollama_ok, base_ok, liens_ok...)
    manuel: list = field(default_factory=list)     # commandes manuelles à afficher en fin de passage
    reportes: list = field(default_factory=list)   # raisons de report à lister dans le rapport (ex. "backup job not installed")

    # --- affichage -------------------------------------------------------------------------------------------------------
    def dire(self, message: str) -> None:
        print(PREFIXE + message, flush=True)

    def dire_etape(self, etape: str, message: str) -> None:
        self.dire(f"step {etape}: {message}")

    # --- recherche de commandes (jamais de chemin fixe) --------------------------------------------------------------------
    def trouver(self, nom: str) -> str | None:
        return shutil.which(nom)

    def application_presente(self, nom: str) -> bool:
        """Une application macOS (ex. « Ollama.app ») est dans /Applications ou ~/Applications ; INSTALL_LAB_APPLICATIONS les remplace (tests)."""
        remplace = os.environ.get(VARIABLE_APPLICATIONS)
        dossiers = [Path(d) for d in remplace.split(":") if d] if remplace is not None else [Path(os.sep) / "Applications", self.maison / "Applications"]
        return any((d / nom).exists() for d in dossiers)

    # --- sondes : lecture seule, tournent aussi en passage à blanc -----------------------------------------------------------
    def sonde(self, commande: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
        """Lance une commande de lecture seule ; sortie capturée. Commande introuvable : code 127 (jamais d'exception)."""
        try:
            return subprocess.run(commande, cwd=cwd or self.racine, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            return subprocess.CompletedProcess(commande, 127, "", f"{commande[0]}: command not found")

    def sonde_ok(self, commande: list[str], cwd: Path | None = None) -> bool:
        return self.sonde(commande, cwd).returncode == 0

    # --- actions : confirmées, jamais sans demander ---------------------------------------------------------------------------
    def confirmer(self, etape: str, action: str) -> bool:
        """Pose la question y/N ; seuls y et yes (casse libre) acceptent. Fin de fichier : refus."""
        try:
            reponse = input(f"{PREFIXE}step {etape}: {action}? [y/N] ")
        except EOFError:
            return False
        return reponse.strip().lower() in ("y", "yes")

    def act(self, etape: str, description: str, commande: list[str], cwd: Path | None = None, montrer_sortie: bool = True,
            echec_tolere: bool = False) -> Resultat:
        """Action qui change la machine. Passage à blanc : affiche « dry run: would run » et rend A_BLANC. Sinon demande confirmation,
        puis lance la commande (sortie des scripts appelés affichée telle quelle). Rend FAIT, REFUSE ou ECHEC (detail = la commande).
        echec_tolere=True : un code non nul rend ECHEC sans message « failed » (l'appelant vérifie lui-même le résultat, ex. l'erreur
        « Bootstrap failed: 5 » de launchctl, inoffensive quand l'état de la tâche répond ensuite)."""
        texte = shlex.join(commande)
        if self.a_blanc:
            self.dire(f"dry run: would run {texte}")
            return Resultat(A_BLANC, texte)
        if not self.confirmer(etape, f"{description} (run {texte})"):
            self.dire_etape(etape, "declined")
            return Resultat(REFUSE, texte)
        try:
            termine = subprocess.run(commande, cwd=cwd or self.racine, capture_output=not montrer_sortie, text=True, check=False)
        except FileNotFoundError:
            self.dire_etape(etape, f"failed: {texte}")
            return Resultat(ECHEC, texte)
        if termine.returncode != 0:
            if not echec_tolere:
                self.dire_etape(etape, f"failed: {texte}")
            return Resultat(ECHEC, texte)
        return Resultat(FAIT, texte)

    def ecrire(self, etape: str, description: str, chemin: Path, contenu: str) -> Resultat:
        """Écrit un fichier sous la maison de l'utilisateur, après confirmation. Passage à blanc : rien n'est écrit."""
        if self.a_blanc:
            self.dire(f"dry run: would run write {chemin}")
            return Resultat(A_BLANC, f"write {chemin}")
        if not self.confirmer(etape, f"{description} (write {chemin})"):
            self.dire_etape(etape, "declined")
            return Resultat(REFUSE, f"write {chemin}")
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(contenu, encoding="utf-8")
        return Resultat(FAIT, f"write {chemin}")

    def action_manuelle(self, commande: str, explication: str = "") -> None:
        """Enregistre une action que l'utilisateur doit faire lui-même (jamais lancée) et l'affiche."""
        self.dire("manual action needed: " + explication if explication else "manual action needed:")
        self.dire("    " + commande)
        self.manuel.append(commande)


def racine_du_depot(fichier: str) -> Path:
    """Racine du dépôt : INSTALL_LAB_ROOT (tests) ou le dossier parent de tools/."""
    valeur = os.environ.get(VARIABLE_RACINE)
    return Path(valeur).resolve() if valeur else Path(fichier).resolve().parents[1]


def entree_est_un_terminal() -> bool:
    return sys.stdin.isatty() or bool(os.environ.get(VARIABLE_SANS_TERMINAL))


# --- valeurs lues dans les fichiers de configuration du dépôt (une seule source, design D10 et questions ouvertes 1 et 2) ----------------------
def lire_constante(fichier: Path, nom: str):
    """Lit la valeur littérale de `nom = ...` au niveau du module d'un fichier Python, sans l'importer (db.py demande psycopg).
    Accepte un littéral, ou un appel `os.environ.get("VARIABLE", "valeur")` dont la valeur par défaut est rendue.
    Rend None si le fichier ou la constante est introuvable."""
    import ast
    try:
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None
    for noeud in arbre.body:
        if isinstance(noeud, ast.Assign) and any(isinstance(c, ast.Name) and c.id == nom for c in noeud.targets):
            valeur = noeud.value
            if isinstance(valeur, ast.Call) and len(valeur.args) >= 2:
                valeur = valeur.args[-1]
            try:
                return ast.literal_eval(valeur)
            except ValueError:
                return None
    return None


def roles_de_la_base(racine: Path) -> list[str]:
    """Rôles qui ont un mot de passe : la liste de tools/db.py fait foi."""
    valeur = lire_constante(racine / "tools" / "db.py", "ROLES_AVEC_MOT_DE_PASSE")
    return list(valeur) if valeur else []


def service_trousseau_de_la_base(racine: Path) -> str | None:
    """Service du Trousseau du mot de passe de la base, tel que configuré dans tools/db.py (affiché, jamais lu)."""
    valeur = lire_constante(racine / "tools" / "db.py", "SERVICE_TROUSSEAU")
    return valeur if isinstance(valeur, str) else None


def modele_de_veille(racine: Path) -> str | None:
    """Modèle Ollama du pré-tri de la veille : ligne `model:` de watch/tri.yaml."""
    import re
    try:
        texte = (racine / "watch" / "tri.yaml").read_text(encoding="utf-8")
    except OSError:
        return None
    trouve = re.search(r"^model:\s*([^\s#]+)", texte, re.M)
    return trouve.group(1) if trouve else None


def modeles_ollama(racine: Path) -> list[tuple[str, str, str]]:
    """(rôle, nom, taille approximative) des modèles à tirer. Les noms viennent de la configuration du dépôt ; la taille est celle
    du guide d'installation pour le rôle (indicative). Un nom introuvable est omis : l'étape qui appelle doit alors échouer en le disant."""
    liste = []
    embedding = lire_constante(racine / "tools" / "pmzilla_lab_library.py", "EMBED_MODEL")
    if isinstance(embedding, str):
        liste.append(("embedding", embedding, "about 1.2 GB"))
    veille = modele_de_veille(racine)
    if veille:
        liste.append(("watch triage", veille, "about 18 GB"))
    return liste


def runtime_conteneur_repond(ctx: Contexte) -> bool:
    """Sonde partagée : un moteur de conteneurs répond (Docker Desktop ou Colima démarré)."""
    return ctx.sonde_ok(["docker", "info"])
