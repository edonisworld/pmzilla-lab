# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""
PMZilla Lab : veille des composants (change components-watch, R-41).

    uv run tools/composants.py inventory [--verify]
    uv run tools/composants.py check [--if-due] [--only NOM] [--timeout SECONDES]

`inventory` lit l'inventaire docs/pmzilla/composants.yaml, résout la version utilisée de chaque composant là où elle est fixée
(verrous des scripts, .python-version, docker-compose.yml, manifeste BMAD, fichier de version de tools/vendor, constante de l'outil
de bibliothèque, configuration par défaut du pré-tri) et affiche une ligne par composant : nom · genre · version · où elle est fixée.
Le Node de Mothra (genre node-runtime) est lu dans mothra/.node-version : trois segments numériques, sinon « version de Node de
Mothra invalide » (code 1). Aucun réseau, aucune écriture. `--verify` reconstitue en plus la liste des composants utilisés depuis les sources du dépôt (en-têtes
PEP 723 et verrous de tools/, .python-version, docker-compose.yml, modèles Ollama, prérequis d'installation, manifeste BMAD,
configuration OpenSpec, tools/vendor/, dépendances du lanceur de tests, images et CLI OpenSpec de ci/Dockerfile) et nomme ce qu'il
faut ajouter ou retirer ; il contrôle aussi que l'étiquette de l'image et l'empreinte notée en commentaire vont ensemble, et que
ci/Dockerfile épingle chaque image par étiquette et empreinte sha256, la CLI OpenSpec à version exacte et le Python de .python-version
(une valeur marquée A_REMPLIR est nommée « Valeur à remplir par l'auteur dans ci/Dockerfile »), et que l'étiquette de la base Node
de ci/Dockerfile est égale, exactement, à la version de mothra/.node-version (contrôle sauté, avec sa raison, sans l'un des deux
fichiers). Les dépendances d'un outil privé ne comptent que si
l'outil est présent ; quand l'un manque (édition publique), un paquet de l'inventaire qu'aucune source ne déclare n'est pas signalé.

`check` compare chaque composant à la dernière version publiée (PyPI, registre npm, API de Homebrew, publications GitHub, étiquettes
de Docker Hub, registre d'Ollama ; `uv python list` pour Python ; version locale par --version pour un outil non épinglé ; empreinte
locale d'un modèle par l'API locale d'Ollama, en lecture) et range les nouveautés : mise à jour, version majeure, préversion,
étiquette republiée. Il lance `uv lock --script <copie> --upgrade` (à blanc si uv le permet) sur des copies temporaires de chaque
script et de son verrou. Il n'installe, ne met à jour, ne tire et ne démarre rien, n'écrit aucun fichier du dépôt, n'envoie aucune
authentification et ne relance aucune requête ; une source injoignable rend le composant incomplet, jamais la veille en échec.
Résultat : fichier d'état $PMZILLA_LAB_DATA/composants-etat.json (défaut ~/.pmzilla-lab ; droits du seul propriétaire, écriture
atomique), lu par le tableau de bord. --if-due : seulement si aucune tentative aujourd'hui et si c'est le jour hebdomadaire ou que la
dernière vérification complète a plus de 7 jours (ou n'existe pas). --only NOM : un composant, sans toucher à l'état. Le code 1 dit
une nouveauté pas encore notifiée, ou, le jour hebdomadaire, aucune vérification complète depuis plus de N semaines (au plus une
fois par semaine). Lancé par la veille (tools/watch.sh, avec --if-due) ou par l'utilisateur dans le Terminal ; la session ne le lance
pas (fiche C18).

Variables d'environnement : PMZILLA_LAB_DATA, PMZILLA_LAB_TODAY (AAAA-MM-JJ, tests), PMZILLA_COMPOSANTS_DAY (jour hebdomadaire,
lundi par défaut), PMZILLA_COMPOSANTS_STALE_WEEKS (3 par défaut), PMZILLA_COMPOSANTS_TIMEOUT (secondes, 5 par défaut ; une valeur
invalide vaut le défaut), et pour les tests les adresses de base PMZILLA_COMPOSANTS_PYPI, PMZILLA_COMPOSANTS_NPM,
PMZILLA_COMPOSANTS_HOMEBREW, PMZILLA_COMPOSANTS_GITHUB, PMZILLA_COMPOSANTS_DOCKER_HUB, PMZILLA_COMPOSANTS_OLLAMA_REGISTRY,
PMZILLA_COMPOSANTS_OLLAMA_LOCAL, PMZILLA_COMPOSANTS_NODE.

Codes de sortie
inventory : 0 inventaire lisible (et, avec --verify, cohérent avec les sources), 1 différences ou champs fautifs, 2 usage ou inventaire absent ou illisible
check : 0 rien à notifier, 1 quelque chose à notifier (nouveauté pas encore notifiée, ou trop longtemps sans vérification complète), 2 usage, inventaire invalide, état illisible ou non inscriptible

Option (pour les tests) : --root DOSSIER, racine du dépôt à lire (défaut : le dépôt de ce script).
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import hashlib
import http.client
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parents[1]

INVENTAIRE = "docs/pmzilla/composants.yaml"
GUIDE = "docs/pmzilla/installation.md"
COMPOSE = "docker-compose.yml"
PYTHON_VERSION = ".python-version"
NODE_MOTHRA = "mothra/.node-version"                  # Node de Mothra, une version exacte (change mothra-node-lts)
NOM_NODE_MOTHRA = "node-mothra"
MOTIF_NODE_MOTHRA = re.compile(r"^\d+\.\d+\.\d+$")
APERCU_NODE_MOTHRA = 40                               # caractères cités d'un fichier de version invalide
IMAGE_NODE = "library/node"                           # base Node de ci/Dockerfile, nom rendu par _nom_image
MANIFESTE_BMAD = "_bmad/_config/manifest.yaml"
CONFIG_OPENSPEC = "openspec/config.yaml"
VENDOR = "tools/vendor"
LANCEUR = "tests/run_all.sh"
INSTALL_SH = "tools/install_lab.sh"
INSTALL_PREREQS = "tools/install_lab_prereqs.py"
OUTIL_BIBLIOTHEQUE = "tools/pmzilla_lab_library.py"   # constante EMBED_MODEL (modèle d'embedding)
OUTIL_TRI = "tools/watch_triage.py"                   # DEFAULT_CONFIG, clé model (modèle du pré-tri)
DOCKERFILE_CI = "ci/Dockerfile"                       # image de la CI locale (local-ci-container D4)
LIEU_CI = "CI Dockerfile"
PAQUET_OPENSPEC = "@fission-ai/openspec"              # CLI OpenSpec installée dans l'image de la CI à version exacte
A_REMPLIR = "A_REMPLIR"                               # valeur laissée à l'auteur (empreinte ou version lue hors session)
DEPOTS_GITHUB = {"ghcr.io/astral-sh/uv": "astral-sh/uv"}   # image publiée au rythme des publications GitHub de son outil

# Outils du dépôt privé seulement (le manifeste de l'édition les exclut) : leurs dépendances ne comptent que s'ils sont là.
PRIVES = {"build_edition", "publish_edition", "migrate_watch"}

CHAMPS = ("name", "kind", "pinned_in", "channel", "upstream", "procedure", "flags")
OBLIGATOIRES = ("name", "kind", "pinned_in", "upstream", "procedure")
GENRES = ("python-package", "python-runtime", "node-runtime", "tool", "docker-image", "ollama-model", "bmad-module", "vendored")
LIEUX = ("lock files", ".python-version", NODE_MOTHRA, "docker-compose.yml", "BMAD manifest", "vendor version file",
         "library tool constant", "sorting configuration", LIEU_CI, "not pinned")
CANAUX = ("Homebrew formula", "Homebrew cask", "official installer", "npm registry", "Xcode Command Line Tools", "fnm")
SOURCES = ("PyPI", "uv Python list", "npm registry", "Homebrew API", "GitHub releases", "Docker Hub tags", "Ollama registry",
           "Node.js releases", "local version only")
SUIVI_LOCAL = "local version only"   # version locale relevée, aucune source amont, jamais de nouveauté (git des outils Xcode)
MARQUES = ("requires-reindex", "major-watch-only")
NON_EPINGLE = "non épinglé"
INSTALLATION_BMAD = "bmad-method"   # l'installation BMAD elle-même, nom du paquet npm


class InventaireIllisible(Exception):
    pass


# --- lecture des sources ------------------------------------------------------------------------------------------------------

def normaliser(nom: str) -> str:
    """Nom de paquet normalisé (PEP 503), extras et bornes retirés."""
    nom = re.split(r"[\[<>=!~; @]", nom.strip(), maxsplit=1)[0]
    return re.sub(r"[-_.]+", "-", nom).lower()


def dependances_en_tete(texte: str) -> list[str]:
    """Dépendances directes du bloc `# /// script` (liste sur une ou plusieurs lignes), noms normalisés, dans l'ordre."""
    bloc = re.search(r"^# /// script\n((?:#.*\n)+?)# ///", texte, re.M)
    if not bloc:
        return []
    corps = "\n".join(l[1:] for l in bloc.group(1).splitlines())
    try:
        dependances = tomllib.loads(corps).get("dependencies", [])
    except tomllib.TOMLDecodeError:
        return []
    return [normaliser(d) for d in dependances if isinstance(d, str)]


def paquets_du_verrou(texte: str) -> dict[str, str]:
    """{paquet normalisé: version} d'un verrou de script (tous les paquets, transitifs compris)."""
    try:
        donnees = tomllib.loads(texte)
    except tomllib.TOMLDecodeError:
        return {}
    return {normaliser(p["name"]): str(p.get("version", "?")) for p in donnees.get("package", []) if "name" in p}


def lire(racine: Path, relatif: str) -> str | None:
    chemin = racine / relatif
    try:
        return chemin.read_text(encoding="utf-8") if chemin.is_file() else None
    except (OSError, UnicodeDecodeError):
        return None


def scripts_python(racine: Path) -> list[Path]:
    """Fichiers .py directement sous tools/ (scripts d'entrée et modules), sans les outils privés absents (absents de fait)."""
    dossier = racine / "tools"
    return sorted(dossier.glob("*.py")) if dossier.is_dir() else []


def prive_absent(racine: Path) -> bool:
    return any(not (racine / "tools" / f"{nom}.py").exists() for nom in PRIVES)


def chaine_constante(arbre: ast.AST, nom: str) -> ast.AST | None:
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Assign) and any(isinstance(c, ast.Name) and c.id == nom for c in noeud.targets):
            return noeud.value
    return None


def modele_bibliotheque(racine: Path) -> str | None:
    """Modèle d'embedding : valeur par défaut de EMBED_MODEL (os.environ.get(variable, défaut) ou chaîne) ; structure seulement."""
    texte = lire(racine, OUTIL_BIBLIOTHEQUE)
    if texte is None:
        return None
    try:
        valeur = chaine_constante(ast.parse(texte), "EMBED_MODEL")
    except SyntaxError:
        return None
    if isinstance(valeur, ast.Call) and len(valeur.args) >= 2:
        valeur = valeur.args[1]
    return valeur.value if isinstance(valeur, ast.Constant) and isinstance(valeur.value, str) else None


def modele_tri(racine: Path) -> str | None:
    """Modèle du pré-tri : clé model de la configuration par défaut de l'outil de tri (la copie locale de l'utilisateur, dans le
    dossier de la veille, n'est jamais lue)."""
    texte = lire(racine, OUTIL_TRI)
    if texte is None:
        return None
    try:
        valeur = chaine_constante(ast.parse(texte), "DEFAULT_CONFIG")
        config = yaml.safe_load(valeur.value) if isinstance(valeur, ast.Constant) else None
    except (SyntaxError, yaml.YAMLError):
        return None
    modele = config.get("model") if isinstance(config, dict) else None
    return modele if isinstance(modele, str) else None


def separer_modele(reference: str) -> tuple[str, str]:
    nom, _, etiquette = reference.partition(":")
    return nom, etiquette or "latest"


def node_mothra(racine: Path) -> tuple[str | None, str | None]:
    """(version, problème) du fichier de version de Node de Mothra : (None, None) s'il est absent, (version, None) s'il est valide,
    (None, phrase) sinon. Trois segments numériques, sans préfixe v, borne ni alias (design.md D2). La phrase ne cite que la première
    ligne du contenu, coupée à APERCU_NODE_MOTHRA caractères, suivie de « … » quand il en reste : un fichier invalide n'est jamais
    affiché en entier."""
    texte = lire(racine, NODE_MOTHRA)
    if texte is None:
        return None, None
    texte = texte.strip()
    if MOTIF_NODE_MOTHRA.match(texte):
        return texte, None
    premiere = texte.splitlines()[0].strip() if texte else ""
    apercu = premiere[:APERCU_NODE_MOTHRA]
    if apercu != texte:
        apercu += " …"
    return None, f"version de Node de Mothra invalide : {apercu} (attendu MAJEUR.MINEUR.CORRECTIF)"


def images_compose(racine: Path) -> list[tuple[str, str | None]]:
    """[(image sans étiquette, étiquette ou None)] des lignes `image:` du fichier compose."""
    texte = lire(racine, COMPOSE) or ""
    images = []
    for m in re.finditer(r"^\s*image:\s*[\"']?([^\s\"'#]+)", texte, re.M):
        reference = m.group(1).split("@")[0]
        nom, deux_points, etiquette = reference.rpartition(":")
        if not deux_points or "/" in etiquette:
            nom, etiquette = reference, None
        images.append((nom, etiquette))
    return images


def empreinte_notee(racine: Path) -> tuple[list[str], str | None]:
    """(étiquettes des lignes « Version <étiquette>, … », empreinte sha256 de la ligne « Digest … ») des commentaires du compose."""
    texte = lire(racine, COMPOSE) or ""
    etiquettes = re.findall(r"^#\s*Version\s+([^\s,]+)", texte, re.M)
    digest = re.search(r"^#\s*Digest\b.*?(sha256:[0-9a-f]{64})\b", texte, re.M)
    return etiquettes, digest.group(1) if digest else None


def _nom_image(reference: str) -> tuple[str, str | None, str]:
    """(nom amont, étiquette ou None, empreinte ou '') d'une référence d'image ; le registre Docker Hub (« docker.io/ » ou
    « index.docker.io/ ») est retiré et une image officielle prend « library/ »."""
    reference, _, empreinte = reference.partition("@")
    nom, deux_points, etiquette = reference.rpartition(":")
    if not deux_points or "/" in etiquette:
        nom, etiquette = reference, None
    nom = nom.removeprefix("index.docker.io/").removeprefix("docker.io/")
    if "/" not in nom:
        nom = f"library/{nom}"
    return nom, etiquette, empreinte


def lignes_ci(racine: Path) -> list[str] | None:
    """Instructions de ci/Dockerfile, sans commentaires ni lignes vides ; None sans fichier."""
    texte = lire(racine, DOCKERFILE_CI)
    if texte is None:
        return None
    return [l.strip() for l in texte.splitlines() if l.strip() and not l.strip().startswith("#")]


def images_ci(racine: Path) -> list[tuple[str, str | None, str]]:
    """[(nom, étiquette, empreinte)] des images de ci/Dockerfile (FROM et COPY --from), étapes nommées exclues."""
    etapes, images = set(), []
    for ligne in lignes_ci(racine) or []:
        m = re.match(r"(?i)^FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", ligne)
        reference = None
        if m:
            reference = m.group(1)
            if m.group(2):
                etapes.add(m.group(2).lower())
        elif re.match(r"(?i)^COPY\b", ligne) and (m := re.search(r"--from=(\S+)", ligne)):
            reference = m.group(1)
        if reference and reference.lower() not in etapes and not reference.isdigit():
            images.append(_nom_image(reference))
    return images


def openspec_ci(racine: Path) -> str | None:
    """Version de la CLI OpenSpec installée par ci/Dockerfile ('' sans version) ; None si elle n'y est pas."""
    for ligne in lignes_ci(racine) or []:
        m = re.search(re.escape(PAQUET_OPENSPEC) + r"(?:@(\S+))?", ligne)
        if m:
            return m.group(1) or ""
    return None


def manifeste_bmad(racine: Path) -> dict | None:
    texte = lire(racine, MANIFESTE_BMAD)
    if texte is None:
        return None
    try:
        donnees = yaml.safe_load(texte)
    except yaml.YAMLError:
        return None
    return donnees if isinstance(donnees, dict) else None


def prerequis(racine: Path) -> list[tuple[str, str]]:
    """[(outil, fichier)] des prérequis d'installation : boucle « for outil in … » du script shell, OUTILS, listes « brew install »
    et installateur de Claude Code du module des prérequis."""
    trouves: list[tuple[str, str]] = []
    texte = lire(racine, INSTALL_SH)
    if texte:
        for m in re.finditer(r"^\s*for\s+outil\s+in\s+([^;\n]+);", texte, re.M):
            trouves += [(o, INSTALL_SH) for o in m.group(1).split()]
    texte = lire(racine, INSTALL_PREREQS)
    if texte:
        try:
            arbre = ast.parse(texte)
        except SyntaxError:
            arbre = None
        if arbre is not None:
            outils = chaine_constante(arbre, "OUTILS")
            if isinstance(outils, (ast.Tuple, ast.List)):
                trouves += [(e.value, INSTALL_PREREQS) for e in outils.elts if isinstance(e, ast.Constant)]
            for noeud in ast.walk(arbre):
                if isinstance(noeud, ast.List) and len(noeud.elts) > 2 and all(isinstance(e, ast.Constant) for e in noeud.elts):
                    mots = [e.value for e in noeud.elts]
                    if mots[:2] == ["brew", "install"]:
                        locaux = {amont: local for local, amont in NOMS_HOMEBREW.items()}   # nom amont de la cask -> nom de l'outil
                        trouves += [(locaux.get(m, m), INSTALL_PREREQS) for m in mots[2:] if not str(m).startswith("-")]
            if chaine_constante(arbre, "INSTALLATEUR_CLAUDE") is not None:
                trouves.append(("claude", INSTALL_PREREQS))
    return trouves


def dependances_lanceur(racine: Path) -> list[str]:
    texte = lire(racine, LANCEUR) or ""
    m = re.search(r"^DEPS=.*$", texte, re.M)
    return [normaliser(p) for p in re.findall(r"--with\s+\"?([^\s\"}]+)", m.group(0))] if m else []


def sources_utilisees(racine: Path) -> dict[str, tuple[str, str]]:
    """{nom: (genre, source qui le déclare)} reconstitué depuis les sources du dépôt (design.md D2)."""
    utilises: dict[str, tuple[str, str]] = {}

    def ajouter(nom, genre, source):
        utilises.setdefault(nom, (genre, source))

    for script in scripts_python(racine):
        for paquet in dependances_en_tete(script.read_text(encoding="utf-8", errors="replace")):
            ajouter(paquet, "python-package", f"tools/{script.name}")
    for paquet in dependances_lanceur(racine):
        ajouter(paquet, "python-package", LANCEUR)
    if (racine / PYTHON_VERSION).is_file():
        ajouter("python", "python-runtime", PYTHON_VERSION)
    if (racine / NODE_MOTHRA).is_file():
        ajouter(NOM_NODE_MOTHRA, "node-runtime", NODE_MOTHRA)
    for nom, _ in images_compose(racine):
        ajouter(nom, "docker-image", COMPOSE)
    if modele := modele_bibliotheque(racine):
        ajouter(separer_modele(modele)[0], "ollama-model", OUTIL_BIBLIOTHEQUE)
    if modele := modele_tri(racine):
        ajouter(separer_modele(modele)[0], "ollama-model", OUTIL_TRI)
    if (racine / INSTALL_SH).is_file() or (racine / INSTALL_PREREQS).is_file():
        ajouter("homebrew", "tool", INSTALL_SH)
    for outil, source in prerequis(racine):
        ajouter(outil, "tool", source)
    bmad = manifeste_bmad(racine)
    if bmad:
        if isinstance(bmad.get("installation"), dict):
            ajouter(INSTALLATION_BMAD, "bmad-module", MANIFESTE_BMAD)
        for module in bmad.get("modules") or []:
            if isinstance(module, dict) and module.get("name"):
                ajouter(str(module["name"]), "bmad-module", MANIFESTE_BMAD)
    if (racine / CONFIG_OPENSPEC).is_file():
        ajouter("openspec", "tool", CONFIG_OPENSPEC)
    if (racine / VENDOR).is_dir():
        for fichier in sorted((racine / VENDOR).glob("*.version")):
            ajouter(fichier.stem, "vendored", f"{VENDOR}/{fichier.name}")
    for nom, _, _ in images_ci(racine):
        ajouter(nom, "docker-image", DOCKERFILE_CI)
    if openspec_ci(racine) is not None:
        ajouter(PAQUET_OPENSPEC, "tool", DOCKERFILE_CI)
    return utilises


# --- inventaire ---------------------------------------------------------------------------------------------------------------

@dataclass
class Composant:
    name: str
    kind: str
    pinned_in: str
    upstream: str
    procedure: str
    channel: str | None = None
    flags: list[str] = field(default_factory=list)


def titres_du_guide(racine: Path) -> set[str]:
    texte = lire(racine, GUIDE) or ""
    return {m.group(1).strip() for m in re.finditer(r"^#{1,6}\s+(.+?)\s*#*\s*$", texte, re.M)}


def charger_inventaire(racine: Path) -> tuple[list[Composant], list[str]]:
    """(composants valides, problèmes de format). Lève InventaireIllisible si le fichier manque ou n'est pas une liste."""
    chemin = racine / INVENTAIRE
    try:
        donnees = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
        raise InventaireIllisible(type(e).__name__) from None
    if not isinstance(donnees, dict) or not isinstance(donnees.get("components"), list) or set(donnees) != {"components"}:
        raise InventaireIllisible("structure")
    titres = titres_du_guide(racine)
    problemes, composants, vus = [], [], set()
    for i, entree in enumerate(donnees["components"], 1):
        if not isinstance(entree, dict):
            problemes.append(f"Entrée illisible : n°{i}")
            continue
        nom = str(entree.get("name") or f"n°{i}")
        avant = len(problemes)
        for champ in entree:
            if champ not in CHAMPS:
                problemes.append(f"Champ inconnu : {nom}, {champ}")
        for champ in OBLIGATOIRES:
            if not entree.get(champ):
                problemes.append(f"Champ manquant : {nom}, {champ}")
        if nom in vus:
            problemes.append(f"Composant en double : {nom}")
        vus.add(nom)
        kind, lieu, source = entree.get("kind"), entree.get("pinned_in"), entree.get("upstream")
        if kind and kind not in GENRES:
            problemes.append(f"Genre inconnu : {nom}, {kind}")
        if lieu and lieu not in LIEUX:
            problemes.append(f"Valeur inconnue : {nom}, pinned_in")
        if source and source not in SOURCES:
            problemes.append(f"Valeur inconnue : {nom}, upstream")
        if lieu == "not pinned":
            if not entree.get("channel"):
                problemes.append(f"Champ manquant : {nom}, channel")
            elif entree["channel"] not in CANAUX:
                problemes.append(f"Valeur inconnue : {nom}, channel")
        elif "channel" in entree:
            problemes.append(f"Champ inconnu : {nom}, channel")
        marques = entree.get("flags", [])
        if not isinstance(marques, list) or any(m not in MARQUES for m in marques):
            problemes.append(f"Valeur inconnue : {nom}, flags")
        procedure = entree.get("procedure")
        if procedure and str(procedure).strip() not in titres:
            problemes.append(f"Procédure introuvable dans le guide d'installation : {nom}")
        if len(problemes) == avant:
            composants.append(Composant(name=nom, kind=kind, pinned_in=lieu, upstream=source, procedure=str(procedure),
                                        channel=entree.get("channel"), flags=list(marques)))
    return composants, problemes


# --- versions utilisées -------------------------------------------------------------------------------------------------------

def versions_verrouillees(racine: Path) -> dict[str, dict[str, list[str]]]:
    """{paquet: {version: [scripts]}} lus dans les verrous de tools/."""
    versions: dict[str, dict[str, list[str]]] = {}
    dossier = racine / "tools"
    for verrou in sorted(dossier.glob("*.py.lock")) if dossier.is_dir() else []:
        script = verrou.name[:-len(".py.lock")]
        for paquet, version in paquets_du_verrou(verrou.read_text(encoding="utf-8", errors="replace")).items():
            versions.setdefault(paquet, {}).setdefault(version, []).append(script)
    return versions


class Resolveur:
    """Version utilisée de chaque composant, lue là où elle est fixée (fiche C15) ; None si introuvable."""

    def __init__(self, racine: Path):
        self.racine = racine
        self._verrous = None

    def verrous(self):
        if self._verrous is None:
            self._verrous = versions_verrouillees(self.racine)
        return self._verrous

    def versions_python(self, nom: str) -> dict[str, list[str]]:
        return self.verrous().get(nom, {})

    def version(self, c: Composant) -> str | None:
        if c.pinned_in == "not pinned":
            return None
        if c.pinned_in == "lock files":
            versions = self.versions_python(c.name)
            return max(versions, key=cle_tri_simple) if versions else None
        if c.pinned_in == ".python-version":
            texte = lire(self.racine, PYTHON_VERSION)
            return texte.strip() if texte else None
        if c.pinned_in == NODE_MOTHRA:
            return node_mothra(self.racine)[0]
        if c.pinned_in == "docker-compose.yml":
            return next((etiquette for nom, etiquette in images_compose(self.racine) if nom == c.name), None)
        if c.pinned_in == "BMAD manifest":
            bmad = manifeste_bmad(self.racine) or {}
            if c.name == INSTALLATION_BMAD:
                return str((bmad.get("installation") or {}).get("version") or "") or None
            module = next((m for m in bmad.get("modules") or [] if isinstance(m, dict) and m.get("name") == c.name), None)
            return str(module.get("version")) if module and module.get("version") else None
        if c.pinned_in == "vendor version file":
            texte = lire(self.racine, f"{VENDOR}/{c.name}.version")
            return texte.strip() if texte else None
        if c.pinned_in in ("library tool constant", "sorting configuration"):
            modele = modele_bibliotheque(self.racine) if c.pinned_in == "library tool constant" else modele_tri(self.racine)
            if modele and separer_modele(modele)[0] == c.name:
                return separer_modele(modele)[1]
        if c.pinned_in == LIEU_CI:
            if c.kind == "docker-image":
                return next((etiquette for nom, etiquette, _ in images_ci(self.racine) if nom == c.name), None)
            if c.name == PAQUET_OPENSPEC:
                return openspec_ci(self.racine) or None
        return None

    def affichage(self, c: Composant) -> str:
        if c.pinned_in == "not pinned":
            return NON_EPINGLE
        if c.pinned_in == "lock files":
            versions = self.versions_python(c.name)
            if len(versions) > 1:
                return ", ".join(f"{v} ({', '.join(s)})" for v, s in sorted(versions.items(), key=lambda kv: cle_tri_simple(kv[0])))
        return self.version(c) or "introuvable"


def cle_tri_simple(version: str) -> tuple:
    return tuple(int(n) if n.isdigit() else -1 for n in re.findall(r"\d+|[a-z]+", version.lower()))


# --- vérification de l'inventaire contre les sources ----------------------------------------------------------------------------

def differences(racine: Path, composants: list[Composant]) -> list[str]:
    utilises = sources_utilisees(racine)
    listes = {c.name for c in composants}
    lignes = [f"Composant à ajouter à l'inventaire : {nom} (déclaré dans {source})"
              for nom, (_, source) in sorted(utilises.items()) if nom not in listes]
    tolerer = prive_absent(racine)
    for c in composants:
        if c.name in utilises:
            continue
        if tolerer and c.kind == "python-package":
            continue          # un outil privé absent peut le déclarer (édition publique)
        lignes.append(f"Composant à retirer de l'inventaire : {c.name}")
    lignes += controle_image(racine)
    lignes += controle_ci(racine)
    lignes += controle_node_image(racine)[0]
    return lignes


def controle_node_image(racine: Path) -> tuple[list[str], list[str]]:
    """(écarts, sauts) du contrôle « même Node dans l'image de la CI et dans mothra/.node-version » (mothra-node-lts, design.md D4).
    L'étiquette de la base library/node de ci/Dockerfile, lue par images_ci (préfixes du registre retirés par _nom_image), sans son
    suffixe de variante (-slim), doit être égale, exactement, à la version du fichier. L'empreinte sha256, qui fixe l'image, est
    contrôlée par controle_ci et change avec l'étiquette (procédure « Update the Node of Mothra »). Aucun registre interrogé."""
    absent = DOCKERFILE_CI if lire(racine, DOCKERFILE_CI) is None else NODE_MOTHRA if not (racine / NODE_MOTHRA).is_file() else None
    if absent:
        return [], [f"contrôle Node de l'image sauté : {absent} absent"]
    version, _ = node_mothra(racine)
    if version is None:
        return [], []                      # contenu invalide : déjà signalé par la lecture du fichier
    etiquette = next((e for nom, e, _ in images_ci(racine) if nom == IMAGE_NODE), None)
    image = etiquette.split("-")[0] if etiquette else "introuvable"
    if image != version:
        return [f"Node de l'image de CI différent du Node de Mothra : {image} contre {version}"], []
    return [], []


def controle_ci(racine: Path) -> list[str]:
    """ci/Dockerfile épingle chaque image par étiquette et empreinte sha256, la CLI OpenSpec à version exacte, et installe le Python
    de .python-version (local-ci-container D4). Une valeur marquée A_REMPLIR est nommée à part : l'auteur la lit hors session."""
    lignes = lignes_ci(racine)
    if lignes is None:
        return []
    manque, a_remplir = "Épinglage manquant dans ci/Dockerfile", "Valeur à remplir par l'auteur dans ci/Dockerfile"
    sortie = []
    for nom, etiquette, empreinte in images_ci(racine):
        if not etiquette or etiquette == "latest":
            sortie.append(f"{manque} : {nom} (étiquette absente ou latest)")
        if A_REMPLIR in empreinte:
            sortie.append(f"{a_remplir} : {nom} (empreinte)")
        elif not re.fullmatch(r"sha256:[0-9a-f]{64}", empreinte):
            sortie.append(f"{manque} : {nom} (empreinte sha256 absente)")
    version = openspec_ci(racine)
    if version is not None:
        if A_REMPLIR in version:
            sortie.append(f"{a_remplir} : {PAQUET_OPENSPEC} (version)")
        elif not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", version):
            sortie.append(f"{manque} : {PAQUET_OPENSPEC} (version exacte absente)")
    copie = any(re.match(r"(?i)^COPY\b", l) and PYTHON_VERSION in l.split() for l in lignes)
    autre = any(re.search(r"\buv\s+python\s+install\s+(?!-)\S", l) or re.search(r"\bUV_PYTHON=", l) for l in lignes)
    installe = any(re.search(r"\buv\s+python\s+install\b", l) for l in lignes)
    if not copie or autre or not installe:
        sortie.append(f"Python de {DOCKERFILE_CI} différent de {PYTHON_VERSION} (copier le fichier, puis « uv python install » sans version)")
    return sortie


def controle_image(racine: Path) -> list[str]:
    """L'étiquette de chaque image et l'empreinte notée en commentaire vont ensemble (design.md D9) ; aucun registre interrogé."""
    phrase = "Empreinte de l'image à mettre à jour avec l'étiquette"
    etiquettes, digest = empreinte_notee(racine)
    lignes = []
    for nom, etiquette in images_compose(racine):
        if not etiquette or etiquette == "latest":
            lignes.append(f"{phrase} : {nom} (étiquette absente ou latest)")
        elif digest is None:
            lignes.append(f"{phrase} : {nom} (empreinte absente)")
        elif etiquette not in etiquettes:
            lignes.append(f"{phrase} : {nom} (empreinte notée pour une autre étiquette)")
    return lignes


# --- sémantique des versions (design.md D8) -------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Version:
    texte: str
    cle: tuple
    majeure: tuple
    preversion: bool


PHASES = {"a": 0, "alpha": 0, "b": 1, "beta": 1, "c": 2, "rc": 2, "pre": 2, "preview": 2}
MOTIF_PEP440 = re.compile(r"^v?(\d+(?:\.\d+)*)(?:[-_.]?(a|alpha|b|beta|c|rc|pre|preview)[-_.]?(\d*))?(?:[-_.]?(post|rev|r)[-_.]?(\d*))?"
                          r"(?:[-_.]?dev[-_.]?(\d*))?(?:\+.*)?$", re.I)
MOTIF_SEMVER = re.compile(r"^v?(\d+(?:\.\d+)*)(?:-([0-9A-Za-z.-]+))?(?:\+.*)?$")
MOTIF_IMAGE = re.compile(r"^(\d+(?:\.\d+)*)(?:-((?:rc|beta|alpha|dev)[0-9A-Za-z.]*))?-pg(\d+)$")


def _release(texte: str) -> tuple[int, ...]:
    return tuple(int(n) for n in texte.split("."))


def _majeure(release: tuple[int, ...]) -> tuple:
    """Premier segment ; pour 0.x, le deuxième compte aussi."""
    return release[:2] if release[0] == 0 else release[:1]


def _complete(release: tuple[int, ...], n: int = 4) -> tuple[int, ...]:
    return release + (0,) * (n - len(release))


def lire_version(ecosysteme: str, texte: str, drapeau_preversion: bool = False) -> Version | None:
    """Version lue selon l'écosystème (pep440, python, semver, homebrew, docker) ; None si la forme n'est pas reconnue."""
    texte = str(texte).strip()
    if ecosysteme in ("pep440", "python"):
        m = MOTIF_PEP440.match(texte)
        if not m:
            return None
        release = _release(m.group(1))
        pre = (PHASES[m.group(2).lower()], int(m.group(3) or 0)) if m.group(2) else None
        post = int(m.group(5) or 0) if m.group(4) else -1
        dev = int(m.group(6) or 0) if m.group(6) is not None else None
        cle = (_complete(release), pre if pre else (9, 0), post, dev if dev is not None else 10 ** 9)
        majeure = release[:2] if ecosysteme == "python" else _majeure(release)
        return Version(texte, cle, majeure, bool(pre) or dev is not None or drapeau_preversion)
    if ecosysteme in ("semver", "homebrew"):
        if ecosysteme == "homebrew":
            texte = re.sub(r"_\d+$", "", texte.split(",")[0])
        m = MOTIF_SEMVER.match(texte)
        if not m:
            return None
        release = _release(m.group(1))
        suffixe = m.group(2)
        pre_cle = (0, tuple((0, int(p)) if p.isdigit() else (1, p) for p in suffixe.split("."))) if suffixe else (1, ())
        majeure = release[:1] if ecosysteme == "homebrew" else _majeure(release)
        return Version(texte, (_complete(release), pre_cle), majeure, bool(suffixe) or drapeau_preversion)
    if ecosysteme == "docker":
        m = MOTIF_IMAGE.match(texte)
        if not m:
            return None
        release, ligne = _release(m.group(1)), int(m.group(3))
        return Version(texte, (ligne, _complete(release), 0 if m.group(2) else 1), (ligne, release[0]), bool(m.group(2)))
    return None


@dataclass
class Nouveaute:
    nature: str        # update, major, pre-release, republished
    utilisee: str
    disponible: str


NATURES_FR = {"update": "mise à jour", "major": "version majeure", "pre-release": "préversion", "republished": "étiquette republiée"}


def classer(ecosysteme: str, utilisee: str, candidates: list[tuple[str, bool]]) -> list[Nouveaute]:
    """Nouveautés d'un composant : mise à jour (même majeure), version majeure, préversion plus récente que la stable ; jamais
    une préversion comptée comme mise à jour ni une majeure fondue dans une mise à jour. Une version illisible est ignorée."""
    u = lire_version(ecosysteme, utilisee)
    if u is None:
        return []
    versions = [v for texte, pre in candidates if (v := lire_version(ecosysteme, texte, pre)) is not None]
    stables = [v for v in versions if not v.preversion]
    if ecosysteme == "python" and len(utilisee.split(".")) <= 2:
        # .python-version fixe une série (3.14) : les correctifs de la série suivent d'eux-mêmes
        u = Version(u.texte, max([v.cle for v in stables if v.majeure == u.majeure] + [u.cle]), u.majeure, False)
    resultat = []
    memes = [v for v in stables if v.majeure == u.majeure and v.cle > u.cle]
    if memes:
        resultat.append(Nouveaute("update", utilisee, max(memes, key=lambda v: v.cle).texte))
    majeures = [v for v in stables if v.majeure > u.majeure]
    if majeures:
        resultat.append(Nouveaute("major", utilisee, max(majeures, key=lambda v: v.cle).texte))
    # une image ne compare ses préversions qu'aux étiquettes de sa ligne PostgreSQL
    plancher = max([v.cle for v in stables if ecosysteme != "docker" or v.majeure[0] == u.majeure[0]] + [u.cle])
    if ecosysteme == "docker":
        pres_lignes = [v for v in versions if v.preversion and v.majeure[0] == u.majeure[0] and v.cle > plancher]
        return resultat + ([Nouveaute("pre-release", utilisee, max(pres_lignes, key=lambda v: v.cle).texte)] if pres_lignes else [])
    pres = [v for v in versions if v.preversion and v.cle > plancher]
    if pres:
        resultat.append(Nouveaute("pre-release", utilisee, max(pres, key=lambda v: v.cle).texte))
    return resultat


# --- sources amont (design.md D5) -----------------------------------------------------------------------------------------------

# Adresses de base : constantes du script, remplaçables par une variable d'environnement (tests), jamais par un fichier de réglages.
BASES = {
    "pypi": ("PMZILLA_COMPOSANTS_PYPI", "https://pypi.org/pypi"),
    "npm": ("PMZILLA_COMPOSANTS_NPM", "https://registry.npmjs.org"),
    "homebrew": ("PMZILLA_COMPOSANTS_HOMEBREW", "https://formulae.brew.sh/api"),
    "node": ("PMZILLA_COMPOSANTS_NODE", "https://nodejs.org/dist"),
    "github": ("PMZILLA_COMPOSANTS_GITHUB", "https://api.github.com"),
    "docker_hub": ("PMZILLA_COMPOSANTS_DOCKER_HUB", "https://hub.docker.com/v2"),
    "ollama_registry": ("PMZILLA_COMPOSANTS_OLLAMA_REGISTRY", "https://registry.ollama.ai/v2"),
    "ollama_local": ("PMZILLA_COMPOSANTS_OLLAMA_LOCAL", "http://127.0.0.1:11434"),
}
DEPOT_HOMEBREW = "Homebrew/brew"
PAQUETS_NPM = {"claude": "@anthropic-ai/claude-code", "openspec": "@fission-ai/openspec", INSTALLATION_BMAD: "bmad-method"}
# Nom amont d'un paquet Homebrew quand il diffère du nom de l'outil (la cask « ollama » est devenue « ollama-app »).
NOMS_HOMEBREW = {"ollama": "ollama-app"}
COMMANDES_VERSION = {"homebrew": ["brew", "--version"], "colima": ["colima", "version"]}
DELAI_DEFAUT = 5.0
PAGES_MAX = 10
ACCEPT_MANIFESTE = "application/vnd.docker.distribution.manifest.v2+json"
JOURS = {"monday": 0, "lundi": 0, "tuesday": 1, "mardi": 1, "wednesday": 2, "mercredi": 2, "thursday": 3, "jeudi": 3,
         "friday": 4, "vendredi": 4, "saturday": 5, "samedi": 5, "sunday": 6, "dimanche": 6}
SEMAINES_DEFAUT = 3
FICHIER_ETAT = "composants-etat.json"


class SourceInjoignable(Exception):
    """Une source n'a pas répondu comme attendu ; seul le type d'erreur est gardé (jamais le message ni l'adresse)."""

    def __init__(self, type_erreur: str):
        super().__init__(type_erreur)
        self.type_erreur = type_erreur


def delai(option: str | None, env) -> float:
    for valeur in (option, env.get("PMZILLA_COMPOSANTS_TIMEOUT")):
        if valeur is None:
            continue
        try:
            secondes = float(valeur)
        except ValueError:
            return DELAI_DEFAUT
        return secondes if 0 < secondes <= 120 else DELAI_DEFAUT
    return DELAI_DEFAUT


class Lecteur:
    """Requêtes GET sans authentification ni nouvelle tentative, délai borné."""

    def __init__(self, env, secondes: float):
        self.bases = {cle: env.get(variable) or defaut for cle, (variable, defaut) in BASES.items()}
        self.secondes = secondes

    def brut(self, cle: str, chemin: str, accept: str = "application/json") -> tuple[bytes, dict]:
        if chemin.startswith(("http://", "https://")) and not chemin.startswith(self.bases[cle] + "/"):
            raise SourceInjoignable("ValueError")          # page suivante hors de la base : jamais suivie
        url = chemin if chemin.startswith(("http://", "https://")) else self.bases[cle] + chemin
        requete = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "pmzilla-lab-composants"})
        try:
            with urllib.request.urlopen(requete, timeout=self.secondes) as reponse:
                return reponse.read(), {k.lower(): v for k, v in reponse.headers.items()}
        except urllib.error.HTTPError:
            raise SourceInjoignable("HTTPError") from None
        except (TimeoutError, socket.timeout):
            raise SourceInjoignable("TimeoutError") from None
        except urllib.error.URLError as e:
            raison = e.reason
            raise SourceInjoignable("TimeoutError" if isinstance(raison, (TimeoutError, socket.timeout)) else type(raison).__name__
                                    if isinstance(raison, Exception) else "URLError") from None
        except (OSError, ValueError, http.client.HTTPException) as e:
            raise SourceInjoignable(type(e).__name__) from None

    def json(self, cle: str, chemin: str):
        octets, _ = self.brut(cle, chemin)
        try:
            return json.loads(octets)
        except (ValueError, UnicodeDecodeError):
            raise SourceInjoignable("JSONDecodeError") from None


def _champ(donnees, *cles):
    for cle in cles:
        if not isinstance(donnees, dict) or cle not in donnees:
            raise SourceInjoignable("UnexpectedBody")
        donnees = donnees[cle]
    return donnees


def candidates_pypi(lecteur: Lecteur, nom: str) -> list[tuple[str, bool]]:
    publiees = _champ(lecteur.json("pypi", f"/{urllib.parse.quote(nom)}/json"), "releases")
    resultat = []
    for version, fichiers in publiees.items():
        if fichiers and all(isinstance(f, dict) and f.get("yanked") for f in fichiers):
            continue            # version retirée
        resultat.append((version, False))
    return resultat


def candidates_npm(lecteur: Lecteur, paquet: str) -> list[tuple[str, bool]]:
    document = lecteur.json("npm", "/" + urllib.parse.quote(paquet, safe="@"))
    _champ(document, "dist-tags", "latest")
    return [(v, False) for v in _champ(document, "versions")]


def candidates_homebrew(lecteur: Lecteur, nom: str, cask: bool) -> list[tuple[str, bool]]:
    nom = NOMS_HOMEBREW.get(nom, nom) if cask else nom
    document = lecteur.json("homebrew", f"/{'cask' if cask else 'formula'}/{urllib.parse.quote(nom)}.json")
    return [(str(_champ(document, "version") if cask else _champ(document, "versions", "stable")), False)]


def candidates_node(lecteur: Lecteur) -> list[tuple[str, bool]]:
    """Publications de Node.js (index de la distribution, celui que lit fnm)."""
    publications = lecteur.json("node", "/index.json")
    if not isinstance(publications, list):
        raise SourceInjoignable("UnexpectedBody")
    return [(str(p.get("version", "")).removeprefix("v"), False) for p in publications if isinstance(p, dict)]


def candidates_node_lts(lecteur: Lecteur, utilisee: str) -> list[tuple[str, bool]]:
    """Publications de Node.js retenues pour Node de Mothra : celles de sa ligne, et celles des lignes plus récentes dont une
    publication au moins porte le marqueur LTS ; une ligne « Current » n'est jamais retenue (design.md D3). Une liste sans le
    marqueur LTS est inexploitable."""
    publications = lecteur.json("node", "/index.json")
    if not isinstance(publications, list) or not any(isinstance(p, dict) and "lts" in p for p in publications):
        raise SourceInjoignable("UnexpectedBody")
    lues = [(str(p.get("version", "")).removeprefix("v"), bool(p.get("lts"))) for p in publications if isinstance(p, dict)]
    lignes_lts = {v.split(".")[0] for v, lts in lues if lts}
    ligne = utilisee.split(".")[0]
    return [(v, False) for v, _ in lues if v.split(".")[0] == ligne or v.split(".")[0] in lignes_lts]


def candidates_github(lecteur: Lecteur, depot: str = DEPOT_HOMEBREW) -> list[tuple[str, bool]]:
    publications = lecteur.json("github", f"/repos/{depot}/releases")
    if not isinstance(publications, list):
        raise SourceInjoignable("UnexpectedBody")
    return [(str(p.get("tag_name", "")), bool(p.get("prerelease"))) for p in publications if isinstance(p, dict) and not p.get("draft")]


def etiquettes_docker(lecteur: Lecteur, image: str) -> list[str]:
    chemin, etiquettes = f"/repositories/{image}/tags?page_size=100", []
    for _ in range(PAGES_MAX):
        page = lecteur.json("docker_hub", chemin)
        etiquettes += [str(r.get("name")) for r in _champ(page, "results") if isinstance(r, dict)]
        chemin = page.get("next")
        if not chemin:
            break
    return etiquettes


def empreinte_docker(lecteur: Lecteur, image: str, etiquette: str) -> str:
    return str(_champ(lecteur.json("docker_hub", f"/repositories/{image}/tags/{etiquette}"), "digest"))


def empreinte_registre_ollama(lecteur: Lecteur, modele: str, etiquette: str) -> str:
    nom = modele if "/" in modele else f"library/{modele}"
    octets, entetes = lecteur.brut("ollama_registry", f"/{nom}/manifests/{etiquette}", accept=ACCEPT_MANIFESTE)
    return entetes.get("docker-content-digest", "").removeprefix("sha256:") or hashlib.sha256(octets).hexdigest()


def empreintes_locales_ollama(lecteur: Lecteur) -> dict[str, str]:
    modeles = _champ(lecteur.json("ollama_local", "/api/tags"), "models")
    return {str(m.get("name")): str(m.get("digest", "")).removeprefix("sha256:") for m in modeles if isinstance(m, dict)}


# --- commandes locales ----------------------------------------------------------------------------------------------------------

def executer(commande: list[str], secondes: float, cwd: Path | None = None) -> subprocess.CompletedProcess | None:
    """Commande locale en lecture ; None si l'exécutable est absent."""
    try:
        return subprocess.run(commande, capture_output=True, text=True, timeout=max(secondes, 30), cwd=cwd, stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        return None
    except (subprocess.TimeoutExpired, OSError):
        return subprocess.CompletedProcess(commande, 124, "", "")


def version_locale(nom: str, secondes: float) -> str:
    """Version installée d'un outil non épinglé (« absent » s'il manque) ; lit seulement sa sortie --version."""
    fait = executer(COMMANDES_VERSION.get(nom, [nom, "--version"]), secondes)
    if fait is None:
        return "absent"
    m = re.search(r"(\d+(?:\.\d+)+)", (fait.stdout or "") + " " + (fait.stderr or ""))
    return m.group(1) if m else "illisible"


def versions_python_uv(secondes: float) -> list[tuple[str, bool]]:
    fait = executer(["uv", "python", "list"], secondes)
    if fait is None or fait.returncode != 0:
        raise SourceInjoignable("UvPythonListFailed")
    return [(m.group(1), False) for m in re.finditer(r"^cpython-(\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?)", fait.stdout, re.M)]


def essai_a_blanc(racine: Path, secondes: float) -> dict[str, dict]:
    """Pour chaque verrou de tools/ : copie du script et du verrou dans un dossier temporaire neuf, `uv lock --script <copie> --upgrade`
    (avec --dry-run si uv le connaît), paquets qui changeraient ; jamais un verrou du dépôt passé à une commande qui écrit."""
    aide = executer(["uv", "lock", "--help"], secondes)
    a_blanc = aide is not None and "--dry-run" in (aide.stdout or "")
    resultats = {}
    for verrou in sorted((racine / "tools").glob("*.py.lock")):
        script = verrou.with_name(verrou.name[:-len(".lock")])
        nom = script.stem
        if not script.is_file():
            continue
        with tempfile.TemporaryDirectory(prefix="composants-") as dossier:
            copie = Path(dossier) / script.name
            shutil.copyfile(script, copie)
            shutil.copyfile(verrou, Path(dossier) / verrou.name)
            commande = ["uv", "lock", "--script", str(copie), "--upgrade"] + (["--dry-run"] if a_blanc else [])
            fait = executer(commande, secondes, cwd=Path(dossier))
            if fait is None or fait.returncode != 0:
                resultats[nom] = {"incomplete": "DryRunFailed"}
                continue
            changes = {m.group(1) for m in re.finditer(r"^\s*(?:Update|Updated)\s+(\S+)\s+v?\S+\s+->\s+v?\S+", fait.stderr + fait.stdout, re.M)}
            avant = paquets_du_verrou(verrou.read_text(encoding="utf-8", errors="replace"))
            apres = paquets_du_verrou((Path(dossier) / verrou.name).read_text(encoding="utf-8", errors="replace"))
            changes |= {p for p, v in apres.items() if p in avant and avant[p] != v}
            resultats[nom] = {"to_update": len(changes)}
    return resultats


# --- état (design.md D6) ----------------------------------------------------------------------------------------------------------

class EtatIllisible(Exception):
    pass


def dossier_donnees(env) -> Path:
    return Path(env.get("PMZILLA_LAB_DATA") or Path(env.get("HOME") or Path.home()) / ".pmzilla-lab").expanduser()


def lire_etat(chemin: Path) -> dict:
    if not chemin.exists():
        return {}
    try:
        etat = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise EtatIllisible("JSONDecodeError" if isinstance(e, ValueError) else type(e).__name__) from None
    if not isinstance(etat, dict):
        raise EtatIllisible("UnexpectedBody")
    return etat


def ecrire_etat(chemin: Path, etat: dict) -> None:
    """Écriture atomique (fichier temporaire du même dossier, puis renommage), lisible par le seul propriétaire."""
    chemin.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descripteur, temporaire = tempfile.mkstemp(prefix=".composants-", dir=chemin.parent)
    try:
        os.fchmod(descripteur, 0o600)
        with os.fdopen(descripteur, "w", encoding="utf-8") as f:
            json.dump(etat, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(temporaire, chemin)
    except BaseException:
        Path(temporaire).unlink(missing_ok=True)
        raise


def date_ou_none(texte) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(texte)) if texte else None
    except ValueError:
        return None


def jour_hebdomadaire(env) -> int:
    valeur = str(env.get("PMZILLA_COMPOSANTS_DAY", "")).strip().lower()
    if valeur.isdigit() and int(valeur) < 7:
        return int(valeur)
    return JOURS.get(valeur, 0)


def semaines_max(env) -> int:
    valeur = str(env.get("PMZILLA_COMPOSANTS_STALE_WEEKS", ""))
    return int(valeur) if valeur.isdigit() and int(valeur) > 0 else SEMAINES_DEFAUT


def due(etat: dict, aujourdhui: dt.date, jour: int) -> bool:
    """Due si aucune tentative aujourd'hui et : jour hebdomadaire, ou dernière vérification complète absente ou de plus de 7 jours."""
    if date_ou_none(etat.get("last_attempt")) == aujourdhui:
        return False
    complete = date_ou_none(etat.get("last_complete"))
    return aujourdhui.weekday() == jour or complete is None or (aujourdhui - complete).days > 7


# --- vérification -------------------------------------------------------------------------------------------------------------

@dataclass
class Resultat:
    composant: Composant
    utilisee: str
    nouveautes: list[Nouveaute] = field(default_factory=list)
    incomplet: str | None = None
    suit: str | None = None


def titre_job(nom: str, n: Nouveaute) -> str:
    return f"Mettre à jour {nom} {n.utilisee} → {n.disponible}"


def verifier_composant(c: Composant, racine: Path, resolveur: Resolveur, lecteur: Lecteur, contexte: dict) -> Resultat:
    secondes = lecteur.secondes
    if c.pinned_in == "not pinned":
        utilisee = version_locale(c.name, secondes)
    else:
        utilisee = resolveur.version(c) or "introuvable"
    r = Resultat(c, utilisee)
    if utilisee in ("absent", "introuvable", "illisible"):
        return r
    try:
        if c.kind == "python-package":
            r.nouveautes = classer("pep440", utilisee, candidates_pypi(lecteur, c.name))
        elif c.kind == "python-runtime":
            r.nouveautes = classer("python", utilisee, versions_python_uv(secondes))
        elif c.kind == "node-runtime":
            r.nouveautes = classer("semver", utilisee, candidates_node_lts(lecteur, utilisee))
        elif c.kind == "docker-image" and c.pinned_in == LIEU_CI and c.upstream == "GitHub releases":
            r.nouveautes = classer("semver", utilisee, candidates_github(lecteur, DEPOTS_GITHUB.get(c.name, c.name)))
        elif c.kind == "docker-image" and c.pinned_in == LIEU_CI:
            etiquettes = etiquettes_docker(lecteur, c.name)
            r.nouveautes = classer("docker", utilisee, [(e, False) for e in etiquettes])
            notee = next((e for nom, _, e in images_ci(racine) if nom == c.name), "")
            publiee = empreinte_docker(lecteur, c.name, utilisee)
            if notee and publiee and publiee != notee:
                r.nouveautes.append(Nouveaute("republished", f"{utilisee}@{notee.removeprefix('sha256:')[:12]}",
                                              f"{utilisee}@{publiee.removeprefix('sha256:')[:12]}"))
        elif c.kind == "docker-image":
            etiquettes = etiquettes_docker(lecteur, c.name)
            r.nouveautes = classer("docker", utilisee, [(e, False) for e in etiquettes])
            notee = empreinte_notee(racine)[1]
            publiee = empreinte_docker(lecteur, c.name, utilisee)
            if notee and publiee and publiee != notee:
                r.nouveautes.append(Nouveaute("republished", f"{utilisee}@{notee.removeprefix('sha256:')[:12]}",
                                              f"{utilisee}@{publiee.removeprefix('sha256:')[:12]}"))
        elif c.kind == "ollama-model":
            if "ollama" not in contexte:
                try:
                    contexte["ollama"] = empreintes_locales_ollama(lecteur)
                except SourceInjoignable as e:
                    contexte["ollama"] = e
            if isinstance(contexte["ollama"], SourceInjoignable):
                raise contexte["ollama"]
            locale = contexte["ollama"].get(f"{c.name}:{utilisee}")
            if locale is None:
                r.utilisee = utilisee
                return r                                       # modèle non tiré sur ce Mac : rien à comparer
            distante = empreinte_registre_ollama(lecteur, c.name, utilisee)
            if distante != locale:
                r.nouveautes = [Nouveaute("republished", f"{utilisee}@{locale[:12]}", f"{utilisee}@{distante[:12]}")]
        elif c.kind == "bmad-module":
            paquet = paquet_bmad(racine, c.name)
            if paquet is None:
                r.suit = INSTALLATION_BMAD                        # module intégré : il suit l'installation
                return r
            r.nouveautes = classer("semver", utilisee, candidates_npm(lecteur, paquet))
        elif c.kind == "vendored":
            r.nouveautes = classer("semver", utilisee, candidates_npm(lecteur, c.name))
        elif c.kind == "tool":
            if c.upstream == "Homebrew API":
                r.nouveautes = classer("homebrew", utilisee, candidates_homebrew(lecteur, c.name, c.channel == "Homebrew cask"))
            elif c.upstream == SUIVI_LOCAL:
                pass                                       # suivi informatif : la version locale seule, aucune nouveauté
            elif c.upstream == "Node.js releases":
                r.nouveautes = classer("semver", utilisee, candidates_node(lecteur))
            elif c.upstream == "GitHub releases":
                r.nouveautes = classer("semver", utilisee, candidates_github(lecteur))
            elif c.upstream == "npm registry":
                r.nouveautes = classer("semver", utilisee, candidates_npm(lecteur, PAQUETS_NPM.get(c.name, c.name)))
            else:
                raise SourceInjoignable("UnknownSource")
        else:
            raise SourceInjoignable("UnknownSource")
    except SourceInjoignable as e:
        r.incomplet = e.type_erreur
    return r


def paquet_bmad(racine: Path, nom: str) -> str | None:
    """Paquet npm d'un composant BMAD : l'installation, ou le paquet d'un module externe ; None pour un module intégré."""
    if nom == INSTALLATION_BMAD:
        return PAQUETS_NPM[INSTALLATION_BMAD]
    bmad = manifeste_bmad(racine) or {}
    module = next((m for m in bmad.get("modules") or [] if isinstance(m, dict) and m.get("name") == nom), {})
    return module.get("npmPackage") or None


def commande_check(racine: Path, si_due: bool, seulement: str | None, option_delai: str | None) -> int:
    env = os.environ
    impossible = "Veille des composants impossible"
    try:
        composants, problemes = charger_inventaire(racine)
    except InventaireIllisible:
        composants, problemes = [], ["illisible"]
    if problemes:
        print(f"{impossible} : inventaire invalide")
        return 2
    if seulement and seulement not in {c.name for c in composants}:
        print(f"Composant inconnu de l'inventaire : {seulement}", file=sys.stderr)
        return 2
    chemin = dossier_donnees(env) / FICHIER_ETAT
    try:
        etat = lire_etat(chemin)
    except EtatIllisible as e:
        print(f"{impossible} : état illisible ({e})")
        return 2
    aujourdhui = date_ou_none(env.get("PMZILLA_LAB_TODAY")) or dt.date.today()
    jour = jour_hebdomadaire(env)
    if si_due and not seulement and not due(etat, aujourdhui, jour):
        print("Veille des composants : pas due")
        return 0

    lecteur = Lecteur(env, delai(option_delai, env))
    resolveur = Resolveur(racine)
    contexte: dict = {}
    choisis = [c for c in composants if not seulement or c.name == seulement]
    resultats = [verifier_composant(c, racine, resolveur, lecteur, contexte) for c in choisis]
    scripts = {} if seulement else essai_a_blanc(racine, lecteur.secondes)
    for nom, s in scripts.items():
        if "incomplete" in s:
            texte = (racine / "tools" / f"{nom}.py").read_text(encoding="utf-8", errors="replace")
            concernes = set(dependances_en_tete(texte))
            for r in resultats:
                if r.composant.kind == "python-package" and r.composant.name in concernes and not r.incomplet:
                    r.incomplet = "DryRunFailed"

    nouveautes = [(r, n) for r in resultats for n in r.nouveautes]
    incomplets = [r for r in resultats if r.incomplet]
    deja = {tuple(p) for p in etat.get("notified", []) if isinstance(p, list) and len(p) == 2}
    nouvelles = [(r.composant.name, n.disponible) for r, n in nouveautes if (r.composant.name, n.disponible) not in deja]

    if nouveautes:
        print(f"Veille des composants : {len(nouveautes)} nouveauté(s)")
        for r, n in nouveautes:
            print(f"{r.composant.name} {n.utilisee} → {n.disponible} ({NATURES_FR[n.nature]})")
    for nom, s in sorted(scripts.items()):
        if s.get("to_update"):
            print(f"Dépendances Python : {nom}, {s['to_update']} paquet(s) à mettre à jour")
    for r in incomplets:
        print(f"{r.composant.name} : source injoignable ({r.incomplet})")
    if incomplets:
        print(f"Veille des composants incomplète : {len(incomplets)} source(s) injoignable(s)")
    elif not nouveautes:
        print("Veille des composants : rien de nouveau")
    for r, n in nouveautes:
        marques = "".join(f", {m}" for m in r.composant.flags)
        print(f"Job proposé : {titre_job(r.composant.name, n)} (procédure : {r.composant.procedure}{marques})")

    if seulement:
        return 1 if nouvelles else 0

    complete = not incomplets
    derniere_complete = aujourdhui if complete else date_ou_none(etat.get("last_complete"))
    premiere = date_ou_none(etat.get("first_attempt")) or aujourdhui
    alerte = False
    if not complete and aujourdhui.weekday() == jour:
        reference = derniere_complete or premiere
        ancienne = date_ou_none(etat.get("stale_alert"))
        if (aujourdhui - reference).days > 7 * semaines_max(env) and (ancienne is None or (aujourdhui - ancienne).days >= 7):
            print(f"Aucune vérification complète des composants depuis {(aujourdhui - reference).days // 7} semaine(s)")
            alerte = True
    nouvel_etat = {
        "version": 1,
        "first_attempt": premiere.isoformat(),
        "last_attempt": aujourdhui.isoformat(),
        "last_complete": derniere_complete.isoformat() if derniere_complete else None,
        "complete": complete,
        "unreachable": len(incomplets),
        "stale_weeks": semaines_max(env),
        "stale_alert": aujourdhui.isoformat() if alerte else etat.get("stale_alert"),
        "components": {r.composant.name: {
            "kind": r.composant.kind, "used": r.utilisee, "pinned": r.composant.pinned_in != "not pinned",
            "flags": list(r.composant.flags), "procedure": r.composant.procedure, "incomplete": r.incomplet, "follows": r.suit,
            "novelties": [{"nature": n.nature, "used": n.utilisee, "available": n.disponible, "job": titre_job(r.composant.name, n)}
                          for n in r.nouveautes]} for r in resultats},
        "scripts": scripts,
        "notified": sorted([list(p) for p in deja | set(nouvelles)]),
    }
    try:
        ecrire_etat(chemin, nouvel_etat)
    except OSError as e:
        print(f"{impossible} : état non inscriptible ({type(e).__name__})")
        return 2
    return 1 if nouvelles or alerte else 0


# --- commandes ----------------------------------------------------------------------------------------------------------------

def commande_inventory(racine: Path, verifier: bool) -> int:
    try:
        composants, problemes = charger_inventaire(racine)
    except InventaireIllisible as e:
        print(f"Inventaire illisible : {INVENTAIRE} ({e})", file=sys.stderr)
        return 2
    resolveur = Resolveur(racine)
    for c in composants:
        lieu = f"{c.pinned_in} ({c.channel})" if c.channel else c.pinned_in
        print(f"{c.name} · {c.kind} · {resolveur.affichage(c)} · {lieu}")
    for p in problemes:
        print(p)
    invalide = node_mothra(racine)[1]
    if invalide:
        print(invalide)
        problemes = problemes + [invalide]
    ecarts = differences(racine, composants) if verifier else []
    if verifier:
        for saut in controle_node_image(racine)[1]:
            print(saut)
    for e in ecarts:
        print(e)
    if problemes or ecarts:
        return 1
    if verifier:
        print(f"Inventaire à jour : {len(composants)} composant(s)")
    return 0


def analyseur() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="composants.py", description="Veille des composants : inventaire et vérification des versions")
    sous = p.add_subparsers(dest="commande", required=True)
    inv = sous.add_parser("inventory", help="affiche l'inventaire et la version utilisée de chaque composant (hors réseau)")
    inv.add_argument("--verify", action="store_true", help="compare aussi l'inventaire aux sources du dépôt")
    inv.add_argument("--root", type=Path, default=None, help=argparse.SUPPRESS)
    chk = sous.add_parser("check", help="compare chaque composant à la dernière version publiée, sans rien installer (réseau)")
    chk.add_argument("--if-due", action="store_true", help="seulement si la vérification hebdomadaire est due (veille quotidienne)")
    chk.add_argument("--only", metavar="NOM", default=None, help="un seul composant (vérification à la main, état inchangé)")
    chk.add_argument("--timeout", metavar="SECONDES", default=None, help="délai de chaque requête (défaut 5)")
    chk.add_argument("--root", type=Path, default=None, help=argparse.SUPPRESS)
    return p


def main(argv: list[str] | None = None) -> int:
    args = analyseur().parse_args(argv)
    racine = (args.root or RACINE).resolve()
    if args.commande == "inventory":
        return commande_inventory(racine, args.verify)
    return commande_check(racine, args.if_due, args.only, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
