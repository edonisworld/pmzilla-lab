"""Aide des tests de tools/composants.py : garde réseau (design.md D15), faux dépôt, appel en processus.

La garde fait échouer toute connexion vers une adresse qui n'est pas la boucle locale ; le message nomme le genre de connexion,
jamais l'adresse. Le faux dépôt reproduit chaque source de design.md D2 avec des valeurs inventées.
"""
import contextlib
import importlib.util
import io
import ipaddress
import os
import shutil
import socket
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
SCRIPT = RACINE / "tools" / "composants.py"


def charger_module():
    spec = importlib.util.spec_from_file_location("composants", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["composants"] = module
    spec.loader.exec_module(module)
    return module


composants = charger_module()


class ConnexionInterdite(AssertionError):
    pass


def _boucle_locale(hote) -> bool:
    if hote in ("localhost", "", None):
        return True
    try:
        return ipaddress.ip_address(str(hote).split("%")[0]).is_loopback
    except ValueError:
        return False


@contextlib.contextmanager
def garde_reseau():
    """Toute connexion hors boucle locale lève ConnexionInterdite (genre de connexion nommé, adresse tue)."""
    connect, create, getaddrinfo = socket.socket.connect, socket.create_connection, socket.getaddrinfo

    def garde_connect(self, adresse):
        hote = adresse[0] if isinstance(adresse, tuple) else None
        if self.family in (socket.AF_INET, socket.AF_INET6) and not _boucle_locale(hote):
            raise ConnexionInterdite("connexion réseau interdite dans les tests : socket TCP/UDP hors boucle locale")
        return connect(self, adresse)

    def garde_create(adresse, *a, **k):
        if not _boucle_locale(adresse[0]):
            raise ConnexionInterdite("connexion réseau interdite dans les tests : create_connection hors boucle locale")
        return create(adresse, *a, **k)

    def garde_getaddrinfo(hote, *a, **k):
        if not _boucle_locale(hote):
            raise ConnexionInterdite("connexion réseau interdite dans les tests : résolution de nom hors boucle locale")
        return getaddrinfo(hote, *a, **k)

    socket.socket.connect, socket.create_connection, socket.getaddrinfo = garde_connect, garde_create, garde_getaddrinfo
    try:
        yield
    finally:
        socket.socket.connect, socket.create_connection, socket.getaddrinfo = connect, create, getaddrinfo


class SansReseau(unittest.TestCase):
    """Chaque test tourne sous la garde réseau."""

    def setUp(self):
        super().setUp()
        pile = contextlib.ExitStack()
        pile.enter_context(garde_reseau())
        self.addCleanup(pile.close)


def lancer(argv: list[str], env: dict | None = None) -> tuple[int, str, str]:
    """(code, sortie, erreurs) de composants.main(argv), en processus, sous un environnement complété par env."""
    sortie, erreurs = io.StringIO(), io.StringIO()
    ancien = dict(os.environ)
    os.environ.update(env or {})
    try:
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(erreurs):
            try:
                code = composants.main(argv)
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 2
    finally:
        os.environ.clear()
        os.environ.update(ancien)
    return code, sortie.getvalue(), erreurs.getvalue()


def verrou(paquets: dict[str, str]) -> str:
    texte = 'version = 1\nrevision = 3\nrequires-python = ">=3.11"\n'
    for nom, version in paquets.items():
        texte += f'\n[[package]]\nname = "{nom}"\nversion = "{version}"\nsource = {{ registry = "https://example.invalid/simple" }}\n'
    return texte


def entete(dependances: list[str]) -> str:
    liste = ", ".join(f'"{d}"' for d in dependances)
    return f'# /// script\n# requires-python = ">=3.11"\n# dependencies = [{liste}]\n# ///\n'


GUIDE = textwrap.dedent("""\
    # Installing

    ### Update a Python package of the scripts
    ### Update the Python runtime
    ### Update the database image
    ### Update an Ollama model
    ### Update BMAD
    ### Update the vendored chart library
    ### Update a Homebrew tool
    ### Update git (Xcode Command Line Tools)
    ### Update Node.js (fnm)
    ### Update Claude Code
    ### Update the OpenSpec CLI
    ### Update the CI image
    """)

# Image de la CI locale (local-ci-container D4) : base et uv épinglées par empreinte, Python de .python-version, CLI OpenSpec épinglée.
DIGEST_BASE_CI = "sha256:" + "b" * 64
DIGEST_UV_CI = "sha256:" + "c" * 64
DOCKERFILE_CI = textwrap.dedent(f"""\
    # Image de la CI locale (valeurs inventées).
    FROM node:26-slim@{DIGEST_BASE_CI}
    COPY --from=ghcr.io/astral-sh/uv:0.13.0@{DIGEST_UV_CI} /uv /uvx /usr/local/bin/
    WORKDIR /opt/ci
    COPY .python-version ./
    RUN uv python install
    RUN npm install -g @fission-ai/openspec@1.0.0
    """)

COMPOSE = textwrap.dedent("""\
    # Base de données.
    # Version 1.2.0-pg18, vérifiée le 2026-01-01.
    # Digest de l'index multi-architecture tiré : sha256:""" + "a" * 64 + """
    services:
      db:
        image: exemple/base:1.2.0-pg18
    """)

BMAD = textwrap.dedent("""\
    installation:
      version: 6.1.0
    modules:
      - name: core
        version: 6.1.0
        source: built-in
        npmPackage: null
      - name: ext
        version: v2.0.0
        source: external
        npmPackage: ext-paquet
    """)

PREREQS = textwrap.dedent("""\
    OUTILS = ("git", "uv", "node")
    INSTALLATEUR_CLAUDE = "curl -fsSL https://example.invalid/install.sh | bash"
    def etapes(ctx):
        ctx.act("x", "install", ["brew", "install", "colima", "docker", "docker-compose"])
        ctx.act("x", "start", ["brew", "services", "start", "colima"])
        ctx.act("x", "install", ["brew", "install", "--cask", "ollama-app"])   # cask renommée : le composant garde son nom « ollama »
    """)

INSTALL_SH = "#!/bin/zsh\nfor outil in git uv; do\n  command -v \"$outil\" >/dev/null 2>&1 && continue\ndone\n"

LANCEUR = '#!/bin/bash\nDEPS="${RUN_ALL_DEPS---with numpy --with pyyaml --with "psycopg[binary]"}"\n'

BIBLIOTHEQUE = entete(["numpy"]) + 'import os\nEMBED_MODEL = os.environ.get("PMZILLA_LAB_MODEL", "modele-a")\n'

TRI = entete(["pyyaml"]) + 'DEFAULT_CONFIG = """\\\n# Pré-tri\nmode: observation\nmodel: modele-b:7b        # modèle\nto_read: 5\n"""\n'


def entree(nom, kind, pinned_in, upstream, procedure, channel=None, flags=None) -> dict:
    e = {"name": nom, "kind": kind, "pinned_in": pinned_in}
    if channel:
        e["channel"] = channel
    e.update({"upstream": upstream, "procedure": procedure})
    if flags:
        e["flags"] = flags
    return e


def inventaire_complet() -> list[dict]:
    pp = "Update a Python package of the scripts"
    outils = [entree("homebrew", "tool", "not pinned", "GitHub releases", "Update a Homebrew tool", channel="official installer")]
    outils += [entree("git", "tool", "not pinned", "local version only", "Update git (Xcode Command Line Tools)",
                      channel="Xcode Command Line Tools"),
               entree("node", "tool", "not pinned", "Node.js releases", "Update Node.js (fnm)", channel="fnm")]
    for nom in ("uv", "colima", "docker", "docker-compose"):
        outils.append(entree(nom, "tool", "not pinned", "Homebrew API", "Update a Homebrew tool", channel="Homebrew formula"))
    outils += [entree("ollama", "tool", "not pinned", "Homebrew API", "Update a Homebrew tool", channel="Homebrew cask"),
               entree("claude", "tool", "not pinned", "npm registry", "Update Claude Code", channel="official installer"),
               entree("openspec", "tool", "not pinned", "npm registry", "Update the OpenSpec CLI", channel="npm registry")]
    return ([entree(n, "python-package", "lock files", "PyPI", pp) for n in ("numpy", "psycopg", "pyyaml")]
            + [entree("python", "python-runtime", ".python-version", "uv Python list", "Update the Python runtime"),
               entree("exemple/base", "docker-image", "docker-compose.yml", "Docker Hub tags", "Update the database image",
                      flags=["major-watch-only"]),
               entree("modele-a", "ollama-model", "library tool constant", "Ollama registry", "Update an Ollama model",
                      flags=["requires-reindex"]),
               entree("modele-b", "ollama-model", "sorting configuration", "Ollama registry", "Update an Ollama model"),
               entree("bmad-method", "bmad-module", "BMAD manifest", "npm registry", "Update BMAD"),
               entree("core", "bmad-module", "BMAD manifest", "npm registry", "Update BMAD"),
               entree("ext", "bmad-module", "BMAD manifest", "npm registry", "Update BMAD"),
               entree("graphes", "vendored", "vendor version file", "npm registry", "Update the vendored chart library")]
            + outils)


def entrees_ci() -> list[dict]:
    """Entrées de l'image de la CI locale : la version reste dans ci/Dockerfile (jamais recopiée dans l'inventaire)."""
    return [entree("library/node", "docker-image", "CI Dockerfile", "Docker Hub tags", "Update the CI image"),
            entree("ghcr.io/astral-sh/uv", "docker-image", "CI Dockerfile", "GitHub releases", "Update the CI image"),
            entree("@fission-ai/openspec", "tool", "CI Dockerfile", "npm registry", "Update the CI image")]


class FauxDepot:
    """Arbre de dépôt inventé, une source de chaque sorte (design.md D2) ; inventaire cohérent au départ."""

    def __init__(self, base: Path):
        self.racine = base / "depot"
        self.avec_ci = False
        r = self.racine
        self.ecrire("tools/a.py", entete(["pyyaml", "psycopg[binary]"]) + "print('a')\n")
        self.ecrire("tools/a.py.lock", verrou({"pyyaml": "6.0.3", "psycopg": "3.2.1", "psycopg-binary": "3.2.1"}))
        self.ecrire("tools/b.py", entete(["pyyaml"]) + "print('b')\n")
        self.ecrire("tools/b.py.lock", verrou({"pyyaml": "6.0.2"}))
        self.ecrire("tools/pmzilla_lab_library.py", BIBLIOTHEQUE)
        self.ecrire("tools/pmzilla_lab_library.py.lock", verrou({"numpy": "2.1.0"}))
        self.ecrire("tools/watch_triage.py", TRI)
        self.ecrire("tools/watch_triage.py.lock", verrou({"pyyaml": "6.0.3"}))
        for prive in ("build_edition", "publish_edition", "migrate_watch"):    # outils privés, présents dans le dépôt privé
            self.ecrire(f"tools/{prive}.py", entete(["pyyaml"]) + "print('p')\n")
        self.ecrire("tools/install_lab.sh", INSTALL_SH)
        self.ecrire("tools/install_lab_prereqs.py", PREREQS)
        self.ecrire("tools/vendor/graphes.version", "5.6.0\n")
        self.ecrire(".python-version", "3.14\n")
        self.ecrire("docker-compose.yml", COMPOSE)
        self.ecrire("_bmad/_config/manifest.yaml", BMAD)
        self.ecrire("openspec/config.yaml", "schema: spec-driven\n")
        self.ecrire("tests/run_all.sh", LANCEUR)
        self.ecrire("docs/pmzilla/installation.md", GUIDE)
        self.ecrire_inventaire(inventaire_complet())
        self.fichiers_initiaux = {p: p.read_bytes() for p in r.rglob("*") if p.is_file()}

    def ecrire(self, relatif: str, texte: str):
        chemin = self.racine / relatif
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte, encoding="utf-8")

    def ecrire_inventaire(self, entrees: list[dict], entete_texte: str = "# Inventaire inventé\n"):
        import yaml
        self.ecrire("docs/pmzilla/composants.yaml", entete_texte + yaml.safe_dump({"components": entrees}, sort_keys=False,
                                                                                  allow_unicode=True))

    def modifier_inventaire(self, fonction):
        entrees = inventaire_complet() + (entrees_ci() if self.avec_ci else [])
        fonction(entrees)
        self.ecrire_inventaire(entrees)

    def ajouter_ci(self, dockerfile: str = DOCKERFILE_CI):
        """Ajoute ci/Dockerfile et les trois entrées de l'image de la CI locale (inventaire cohérent)."""
        self.avec_ci = True
        self.ecrire("ci/Dockerfile", dockerfile)
        self.ecrire_inventaire(inventaire_complet() + entrees_ci())

    def changer_dockerfile(self, ancien: str, nouveau: str):
        chemin = self.racine / "ci/Dockerfile"
        texte = chemin.read_text(encoding="utf-8")
        assert ancien in texte, ancien
        chemin.write_text(texte.replace(ancien, nouveau), encoding="utf-8")

    def inchange(self) -> list[str]:
        """Fichiers du faux dépôt changés depuis sa création (vide si rien n'a bougé)."""
        return sorted(str(p.relative_to(self.racine)) for p, contenu in self.fichiers_initiaux.items()
                      if not p.exists() or p.read_bytes() != contenu)


class AvecDepot(SansReseau):
    def setUp(self):
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.depot = FauxDepot(self.tmp)

    def inventaire(self, *options: str) -> tuple[int, str, str]:
        return lancer(["inventory", "--root", str(self.depot.racine), *options])
