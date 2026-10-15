"""Aides de test du serveur MCP de la bibliothèque : faux FastMCP et surveillance des accès aux fichiers d'un dossier.

Sans base, sans Ollama, sans paquet `mcp`. Utilisé par tests/library_backend et tests/pmzilla_lab_library.
"""
import builtins
import contextlib
import io
import os
import types
from pathlib import Path
from unittest import mock


class FauxFastMCP:
    instance = None

    def __init__(self, name):
        self.tools = {}
        FauxFastMCP.instance = self

    def tool(self):
        def decorate(function):
            self.tools[function.__name__] = function
            return function
        return decorate

    def run(self):
        pass


def modules_mcp() -> dict:
    """Les modules `mcp.server.fastmcp` remplacés par FauxFastMCP (à passer à mock.patch.dict(sys.modules, ...))."""
    modules = {"mcp": types.ModuleType("mcp"), "mcp.server": types.ModuleType("mcp.server"),
               "mcp.server.fastmcp": types.ModuleType("mcp.server.fastmcp")}
    modules["mcp.server.fastmcp"].FastMCP = FauxFastMCP
    return modules


@contextlib.contextmanager
def surveille_dossier(dossier):
    """Note tout accès (ouverture, test d'existence, lecture, listage, création) à un chemin sous `dossier`. Rend la liste des chemins vus."""
    vus: list[str] = []
    cible = str(dossier)

    def fonction(original):
        def enveloppe(chemin, *arguments, **options):
            if cible in str(chemin):
                vus.append(str(chemin))
            return original(chemin, *arguments, **options)
        return enveloppe

    def methode(original):
        def enveloppe(self, *arguments, **options):
            if cible in str(self):
                vus.append(str(self))
            return original(self, *arguments, **options)
        return enveloppe

    with contextlib.ExitStack() as pile:
        pile.enter_context(mock.patch.object(builtins, "open", fonction(builtins.open)))
        pile.enter_context(mock.patch.object(io, "open", fonction(io.open)))
        for nom in ("exists", "isfile", "isdir"):
            pile.enter_context(mock.patch.object(os.path, nom, fonction(getattr(os.path, nom))))
        for nom in ("stat", "listdir", "scandir", "mkdir", "makedirs"):
            pile.enter_context(mock.patch.object(os, nom, fonction(getattr(os, nom))))
        for nom in ("read_bytes", "read_text", "write_bytes", "write_text", "exists", "is_file", "is_dir", "open", "stat", "iterdir",
                    "mkdir", "touch"):
            pile.enter_context(mock.patch.object(Path, nom, methode(getattr(Path, nom))))
        yield vus
