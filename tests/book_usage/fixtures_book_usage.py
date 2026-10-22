"""Aides des tests de tools/book_usage.py : transcriptions JSON Lines SYNTHÉTIQUES, jamais une vraie transcription.

La structure suit le format documenté de Claude Code (voir l'en-tête de tools/book_usage_transcripts.py, qui est l'unique endroit du
code qui la connaît ; ce fichier est l'unique endroit des tests). Chaque champ de texte porte une valeur sentinelle : aucune ne doit
jamais apparaître dans le registre, le rapport ni la console.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "tools"))
import book_usage  # noqa: E402

SENT_USER = "SENTINELLE-MESSAGE-UTILISATEUR"
SENT_QUERY = "SENTINELLE-REQUETE-DE-RECHERCHE"
SENT_PASSAGE = "SENTINELLE-TEXTE-DE-PASSAGE"
SENT_SECTION = "SENTINELLE-SECTION"
SENT_ANSWER = "SENTINELLE-TEXTE-DE-REPONSE"
SENT_AFTER = "SENTINELLE-SUITE-DE-LA-FORMULE"
FAKE_PERSON = "Zorbaz Quillon"        # nom de personne inventé, sentinelle
SESSION = "session-sentinelle-7f3a"
PASSAGE_ID = 987654
SENTINELS = (SENT_USER, SENT_QUERY, SENT_PASSAGE, SENT_SECTION, SENT_ANSWER, SENT_AFTER, FAKE_PERSON, SESSION, str(PASSAGE_ID))

# Livres inventés de la bibliothèque : fichier -> (titre du catalogue, collections)
BOOKS = {
    "flux-et-valeur.md": ("Flux et valeur : mesurer sans trahir", ["flow"]),
    "decouvrir-le-besoin.md": ("Découvrir le besoin", ["produit"]),
    "equipes-reseau.md": ("Équipes en réseau", ["organisation", "flow"]),
    "ateliers-vivants.md": ("Ateliers vivants", ["facilitation"]),
    "jamais-ouvert.md": ("Livre jamais ouvert", ["tech"]),
}
ARTICLE_FILES = {"billet-veille.md": ("Billet de la veille", ["watch"]), "billet-perso.md": ("Billet personnel", ["own-articles"])}

TS = "2026-10-05T09:%02d:00.000Z"


def hit(file, passage_id=PASSAGE_ID, kind="texte"):
    titles = {**BOOKS, **ARTICLE_FILES}
    title, collections = titles[file]
    return {"passage_id": passage_id, "book": title, "file": file, "section": SENT_SECTION, "position": 4,
            "collections": collections, "kind": kind, "score": 0.5, "text": SENT_PASSAGE}


class Transcript:
    """Une séance : appelez user/assistant/call/result dans l'ordre ; write() écrit le fichier JSON Lines."""

    def __init__(self, session=SESSION):
        self.session = session
        self.lines = []
        self.minute = 0
        self.next_id = 0

    def _stamp(self):
        self.minute += 1
        return TS % self.minute

    def _add(self, kind, content, sidechain=False, **extra):
        record = {"type": kind, "isSidechain": sidechain, "sessionId": self.session, "uuid": f"u{len(self.lines)}",
                  "parentUuid": f"u{len(self.lines) - 1}" if self.lines else None, "timestamp": self._stamp(),
                  "message": {"role": kind, "content": content}}
        record.update(extra)
        self.lines.append(record)

    def user(self, text=SENT_USER):
        self._add("user", text)
        return self

    def say(self, text, sidechain=False):
        self._add("assistant", [{"type": "text", "text": text}], sidechain)
        return self

    def call(self, name, tool_input=None, sidechain=False):
        self.next_id += 1
        identifier = f"toolu_{self.next_id:04d}"
        self._add("assistant", [{"type": "tool_use", "id": identifier, "name": name, "input": tool_input or {}}], sidechain)
        return identifier

    def result(self, identifier, payload, sidechain=False, as_array=False):
        """payload : liste (un bloc texte JSON par élément, ou un seul bloc portant le tableau) ou objet."""
        if isinstance(payload, list) and not as_array:
            blocks = [{"type": "text", "text": json.dumps(item)} for item in payload]
        else:
            blocks = [{"type": "text", "text": json.dumps(payload)}]
        self._add("user", [{"type": "tool_result", "tool_use_id": identifier, "content": blocks}], sidechain)
        return self

    def search(self, hits, sidechain=False, as_array=False):
        identifier = self.call("mcp__pmzilla-library__search_library", {"query": SENT_QUERY}, sidechain)
        return self.result(identifier, hits, sidechain, as_array)

    def read(self, file, sidechain=False, article=False):
        identifier = self.call("mcp__pmzilla-library__read_passage", {"passage_id": PASSAGE_ID}, sidechain)
        title, _ = {**BOOKS, **ARTICLE_FILES}[file]
        payload = {"book": title, "file": file, "passages": [{"passage_id": PASSAGE_ID, "kind": "texte", "section": SENT_SECTION,
                                                               "position": 4, "text": SENT_PASSAGE}]}
        if article:
            payload["url"] = "https://example.org/billet"
        return self.result(identifier, payload, sidechain)

    def launch_critic(self):
        return self.call("Agent", {"subagent_type": "pmzilla-critic", "description": SENT_QUERY, "prompt": SENT_QUERY})

    def text_result(self, identifier, content):
        """tool_result dont le contenu est du texte libre : chaîne, ou liste de blocs text."""
        if isinstance(content, list):
            content = [{"type": "text", "text": t} for t in content]
        self._add("user", [{"type": "tool_result", "tool_use_id": identifier, "content": content}])
        return self

    def launch_other(self):
        return self.call("Task", {"subagent_type": "Explore", "prompt": SENT_QUERY})

    def raw(self, line):
        self.lines.append(line)
        return self

    def write(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(l if isinstance(l, str) else json.dumps(l) for l in self.lines) + "\n", encoding="utf-8")
        return path


def simple_turn(transcript, text, files=("flux-et-valeur.md",), read=(), user=SENT_USER):
    """Un tour complet : message, une recherche qui renvoie un passage par fichier, des lectures, la réponse."""
    transcript.user(user)
    transcript.search([hit(f) for f in files])
    for f in read:
        transcript.read(f)
    transcript.say(text)
    return transcript


class Base(unittest.TestCase):
    """Espace de travail jetable : transcriptions, données, workspace ; horloge injectée ; aucun accès au vrai dossier de l'utilisateur."""

    NOW = 1_800_000_000.0           # horloge injectée (époque) ; les transcriptions ont NOW - 1 jour par défaut

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        tmp = Path(self._tmp.name).resolve()   # chemins résolus : le module partagé résout le dossier de contenu
        self.projects = tmp / "projets" / "workspace"
        self.other = tmp / "projets" / "copie-jetable"
        self.data = tmp / "data"
        self.workspace = tmp / "workspace"
        self.workspace.mkdir()     # le module partagé refuse un dossier de contenu absent (code 78)
        self.env = {"PMZILLA_LAB_TRANSCRIPTS": str(self.projects), "PMZILLA_LAB_DATA": str(self.data),
                    "PMZILLA_LAB_WORKSPACE": str(self.workspace)}
        self._old = {k: os.environ.get(k) for k in self.env}
        os.environ.update(self.env)
        self.addCleanup(self._restore)

    def _restore(self):
        for key, value in self._old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    @property
    def ledger(self):
        return self.data / "usage-livres" / "registre.jsonl"

    def records(self):
        if not self.ledger.exists():
            return []
        return [json.loads(l) for l in self.ledger.read_text(encoding="utf-8").splitlines() if l.strip()]

    def put(self, transcript, name="s1.jsonl", folder=None, age=86400):
        path = transcript.write((folder or self.projects) / name)
        os.utime(path, (self.NOW - age, self.NOW - age))
        return path

    def run_tool(self, *argv, read_books=None):
        """(code, sortie console) de book_usage.main avec l'horloge injectée."""
        import contextlib
        import io
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = book_usage.main(list(argv), now=self.NOW, read_books=read_books)
        return code, out.getvalue()

    def library(self):
        return lambda: [{"title": t, "file": f, "collections": c} for f, (t, c) in BOOKS.items()]

    def collect(self):
        return self.run_tool("collect")

    def report(self, *argv):
        code, out = self.run_tool("report", *argv, read_books=self.library())
        return code, out

    def report_text(self):
        folder = self.workspace / "_bmad-output" / "pmzilla" / "usage-livres"
        files = sorted(folder.glob("usage-livres-*.md"))
        return files[-1].read_text(encoding="utf-8") if files else ""
