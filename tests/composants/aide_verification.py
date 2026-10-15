"""Aide des tests de `composants.py check` : faux serveur en boucle locale, fausses commandes qui enregistrent leurs appels, faux
dossier de données et date injectée (design.md D15). Aucune vraie source n'est jamais contactée.
"""
import hashlib
import json
import os
import shutil
import stat
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from aide_composants import AvecDepot, lancer

DIGEST_IMAGE = "sha256:" + "a" * 64
MANIFESTE_MODELE_A = b'{"schemaVersion":2,"layers":["modele-a"]}'
MANIFESTE_MODELE_B = b'{"schemaVersion":2,"layers":["modele-b"]}'


def sha(octets: bytes) -> str:
    return hashlib.sha256(octets).hexdigest()


def pypi(versions: dict[str, bool]) -> dict:
    """Document PyPI : {version: retirée (yanked)}."""
    return {"info": {}, "releases": {v: [{"filename": f"x-{v}.whl", "yanked": y}] for v, y in versions.items()}}


def npm(latest: str, versions: list[str]) -> dict:
    return {"dist-tags": {"latest": latest}, "versions": {v: {} for v in versions}}


def routes_a_jour() -> dict:
    """Chaque composant du faux dépôt à jour : aucune nouveauté."""
    r = {
        "/pypi/numpy/json": pypi({"2.0.0": False, "2.1.0": False}),
        "/pypi/psycopg/json": pypi({"3.2.1": False}),
        "/pypi/pyyaml/json": pypi({"6.0.2": False, "6.0.3": False}),
        "/npm/bmad-method": npm("6.1.0", ["6.0.0", "6.1.0"]),
        "/npm/ext-paquet": npm("2.0.0", ["2.0.0"]),
        "/npm/graphes": npm("5.6.0", ["5.6.0"]),
        "/npm/@anthropic-ai%2Fclaude-code": npm("2.0.0", ["2.0.0"]),
        "/npm/@fission-ai%2Fopenspec": npm("1.0.0", ["1.0.0"]),
        "/github/repos/Homebrew/brew/releases": [{"tag_name": "4.6.0", "draft": False, "prerelease": False}],
        "/hub/repositories/exemple/base/tags": {"results": [{"name": "1.2.0-pg18"}, {"name": "latest"}], "next": None},
        "/hub/repositories/exemple/base/tags/1.2.0-pg18": {"name": "1.2.0-pg18", "digest": DIGEST_IMAGE},
        "/ollama-registry/library/modele-a/manifests/latest": MANIFESTE_MODELE_A,
        "/ollama-registry/library/modele-b/manifests/7b": MANIFESTE_MODELE_B,
        "/ollama-local/api/tags": {"models": [{"name": "modele-a:latest", "digest": sha(MANIFESTE_MODELE_A)},
                                              {"name": "modele-b:7b", "digest": sha(MANIFESTE_MODELE_B)}]},
    }
    r["/node/index.json"] = [{"version": "v24.1.0", "lts": "Krypton"}, {"version": "v24.0.0", "lts": False}]
    for outil, version in {"uv": "0.13.0", "colima": "0.9.0", "docker": "28.0.0",
                           "docker-compose": "2.39.0"}.items():
        r[f"/brew/formula/{outil}.json"] = {"name": outil, "versions": {"stable": version}, "revision": 0}
    r["/brew/cask/ollama-app.json"] = {"token": "ollama-app", "version": "0.12.0"}   # la cask « ollama » n'existe plus (404)
    return r


VERSIONS_LOCALES = {"brew": "Homebrew 4.6.0", "git": "git version 2.50.0 (Apple Git-157)", "uv": "uv 0.13.0 (Homebrew 2026-10-09)",
                    "node": "v24.1.0", "colima": "colima version 0.9.0", "docker": "Docker version 28.0.0, build x",
                    "docker-compose": "Docker Compose version v2.39.0", "ollama": "ollama version is 0.12.0",
                    "claude": "2.0.0 (Claude Code)", "openspec": "1.0.0"}

UV_PYTHON_LIST = "cpython-3.14.0-macos-aarch64-none    <download available>\ncpython-3.13.5-macos-aarch64-none    /x/python3\n"


class FauxServeur:
    """Serveur HTTP en boucle locale : chemin -> corps (dict/list en JSON, bytes tels quels), statut, délai ; journal des requêtes."""

    def __init__(self, routes: dict):
        self.routes = dict(routes)
        self.statuts: dict[str, int] = {}
        self.delais: dict[str, float] = {}
        self.requetes: list[tuple[str, dict]] = []
        serveur = self

        class Gestion(BaseHTTPRequestHandler):
            def do_GET(self):
                chemin = self.path.split("?")[0]
                serveur.requetes.append((chemin, dict(self.headers)))
                time.sleep(serveur.delais.get(chemin, 0))
                if chemin not in serveur.routes:
                    self.send_response(404)
                    self.end_headers()
                    return
                corps = serveur.routes[chemin]
                octets = corps if isinstance(corps, bytes) else json.dumps(corps).encode()
                self.send_response(serveur.statuts.get(chemin, 200))
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                try:
                    self.wfile.write(octets)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *a):
                pass

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Gestion)
        self.http.daemon_threads = True
        self.fil = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.fil.start()

    @property
    def base(self) -> str:
        return f"http://127.0.0.1:{self.http.server_port}"

    def arreter(self):
        self.http.shutdown()
        self.http.server_close()


FAUSSE_COMMANDE = """#!/bin/bash
echo "$(basename "$0") $*" >> "{journal}"
nom=$(basename "$0")
case "$nom $1 $2" in
  "uv python list") cat "{dossier}/uv-python-list.txt"; exit 0 ;;
  "uv lock --help") cat "{dossier}/uv-lock-help.txt"; exit 0 ;;
esac
if [ "$nom" = uv ] && [ "$1" = lock ]; then
  script=""; prec=""
  for a in "$@"; do [ "$prec" = "--script" ] && script="$a"; prec="$a"; done
  base=$(basename "$script" .py)
  [ -f "{dossier}/uv-echec-$base" ] && {{ echo "error: resolution failed" >&2; exit 2; }}
  [ -f "{dossier}/uv-ecrase" ] && echo "lock réécrit" > "$script.lock"
  [ -f "{dossier}/uv-sortie-$base" ] && cat "{dossier}/uv-sortie-$base" >&2
  exit 0
fi
if [ -f "{dossier}/version-$nom" ]; then cat "{dossier}/version-$nom"; exit 0; fi
exit 0
"""


class AvecSources(AvecDepot):
    """Faux dépôt, faux serveur, fausses commandes sur le PATH, faux dossier de données, faux HOME."""

    OUTILS = ("uv", "brew", "git", "node", "colima", "docker", "docker-compose", "ollama", "claude", "openspec", "npm")

    def setUp(self):
        super().setUp()
        self.serveur = FauxServeur(routes_a_jour())
        self.addCleanup(self.serveur.arreter)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.donnees = self.tmp / "donnees"
        self.maison = self.tmp / "maison"
        self.maison.mkdir()
        self.journal = self.tmp / "appels.log"
        self.journal.touch()
        (self.bin / "uv-python-list.txt").write_text(UV_PYTHON_LIST)
        (self.bin / "uv-lock-help.txt").write_text("Options:\n      --dry-run          Perform a dry run\n      --script <SCRIPT>\n")
        for outil in self.OUTILS:
            self.fausse_commande(outil)
        for commande, sortie in VERSIONS_LOCALES.items():
            (self.bin / f"version-{commande}").write_text(sortie + "\n")
        self.aujourdhui = "2026-10-12"   # un lundi

    def fausse_commande(self, nom: str):
        chemin = self.bin / nom
        chemin.write_text(FAUSSE_COMMANDE.format(journal=self.journal, dossier=self.bin))
        chemin.chmod(chemin.stat().st_mode | stat.S_IXUSR)

    def retirer_commande(self, nom: str):
        (self.bin / nom).unlink()

    def env(self, **autres) -> dict:
        b = self.serveur.base
        e = {"PATH": f"{self.bin}:/usr/bin:/bin", "HOME": str(self.maison), "PMZILLA_LAB_DATA": str(self.donnees),
             "PMZILLA_LAB_TODAY": self.aujourdhui, "PMZILLA_COMPOSANTS_PYPI": f"{b}/pypi", "PMZILLA_COMPOSANTS_NPM": f"{b}/npm",
             "PMZILLA_COMPOSANTS_HOMEBREW": f"{b}/brew", "PMZILLA_COMPOSANTS_GITHUB": f"{b}/github",
             "PMZILLA_COMPOSANTS_DOCKER_HUB": f"{b}/hub", "PMZILLA_COMPOSANTS_OLLAMA_REGISTRY": f"{b}/ollama-registry",
             "PMZILLA_COMPOSANTS_OLLAMA_LOCAL": f"{b}/ollama-local", "PMZILLA_COMPOSANTS_NODE": f"{b}/node", "PMZILLA_COMPOSANTS_TIMEOUT": "2"}
        e.update(autres)
        return e

    def verifier(self, *options: str, **env) -> tuple[int, str, str]:
        return lancer(["check", "--root", str(self.depot.racine), *options], env=self.env(**env))

    def etat(self) -> dict:
        return json.loads((self.donnees / "composants-etat.json").read_text())

    def appels(self) -> list[str]:
        return self.journal.read_text().splitlines()

    def ecrire_etat(self, etat: dict):
        self.donnees.mkdir(exist_ok=True)
        (self.donnees / "composants-etat.json").write_text(json.dumps(etat))
