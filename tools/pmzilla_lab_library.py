# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=1.2,<2", "numpy", "httpx", "pyyaml", "psycopg[binary]"]
# ///
"""
PMZilla Lab — library server.

Gives Claude Code access to the digital library (Markdown files produced by
convert_books.py and sorted by ventiler_collections.py) through an MCP server.

Commands:

    uv run pmzilla_lab_library.py index <collections_dir> [<collections_dir> ...]
        Builds or updates the library in the PostgreSQL schema `knowledge` (role pmzilla_knowledge), directly; no file
        of the data folder is created, opened or read. Incremental: only new or changed books are re-embedded, a change of
        collections, title or metadata only updates the book, and each book is written in one transaction (an interrupted
        run leaves complete books only). Each <collections_dir> holds one sub-folder per collection, e.g.
        ~/PMZilla-Lab/workspace/Bibliotheque-Lab ~/PMZilla-Lab/workspace/Watch-Lab. Always pass every folder: a file missing
        from all of them is removed from the database. A folder with the former watch name is stored under the current
        name, with a warning. A book that cannot be written is named and the run exits with code 1 after the others.
        Exit codes: 0 done; 1 folder missing, bad --recompute, embedding failure, wrong vector size, a book not written,
        another run in progress (session advisory lock) or folders without any book while the database holds some; 2 the
        database does not answer (nothing is embedded: start it with bash tools/db_up.sh).

    uv run pmzilla_lab_library.py index <collections_dir> [...] --allow-empty
        Same, and accepts folders without any book: every book of the database is then removed, each one named.

    uv run pmzilla_lab_library.py index <collections_dir> [...] --recompute <book> [<book> ...]
        Same, and re-embeds the designated books even when their Markdown is unchanged (e.g. after the
        passage format changed). A book is a file name with or without extension, or a path ending with
        one; "@list.txt" reads a list (one book per line, # = comment). An unknown or ambiguous book
        stops everything before the database is touched. It first prints a reminder: the restore point is a labelled
        database backup that the user takes before the run (DB_BACKUP_DATE=YYYY-MM-DD-<label> bash tools/db_backup.sh);
        the indexer takes no backup, of a file or of the database, and does not check that one exists.

    uv run pmzilla_lab_library.py rename-collection <old> <new> [--dry-run]
        Renames a collection in the database, in place, in one transaction, without touching a vector (the file
        name, the hash and the passages do not change); the former collection is deleted when no book uses it.
        Prints the counts; --dry-run only prints them. Idempotent. Example: rename-collection veille watch.
        Exit codes: 0 done; 1 another run in progress; 2 the database does not answer.

    uv run pmzilla_lab_library.py probe
        Reads the BM25 index of the database like the search does (role pmzilla_knowledge_ro): one full-text query on
        common words without a filter, one filtered on figure passages, each ending its transaction. Nothing is repaired
        or written, no book text is printed. Exit codes: 0 "BM25 index readable"; 3 "BM25 index unreadable (variant: error
        type)", with the procedure (installation.md, "Damaged BM25 index"); 2 the database does not answer.

    uv run pmzilla_lab_library.py status
        One line of counts of the database (role pmzilla_knowledge_ro): books, passages, figures, collections. Exit 0, or 2
        when the database does not answer.

    uv run pmzilla_lab_library.py serve
        Starts the MCP server on stdio (Claude Code launches it itself). The library is read from the PostgreSQL schema
        `knowledge` (tools/knowledge_library.py, read-only role pmzilla_knowledge_ro) and from nowhere else: there is no
        fallback route. `serve` accepts no argument: `--backend` (any value) and any other extra argument are refused with
        exit code 2; the former variable PMZILLA_LAB_BACKEND is ignored, with one warning line. When the database does not
        answer at start the server stops with exit code 1 and the remedy (bash tools/db_up.sh). Three more tools,
        read-only, serve the cases module (search_cases, search_experiments, list_due_reviews): seven tools in all. They
        answer from the cases database (schema `cases`, role pmzilla_cases_ro, database PMZILLA_LAB_CASES_DBNAME when
        set), opened at the first call; they return an error object when that database does not answer, and the four
        library tools never depend on it.

Search is hybrid: semantic (bge-m3 embeddings through Ollama, computed on this Mac) and keyword (BM25 of the
database), merged by reciprocal rank fusion (tools/hybrid_search.py). Only the passages returned by a search ever reach
Claude.

Environment variables (all optional):
    PMZILLA_LAB_KNOWLEDGE_DBNAME  database of the library, read by the indexer and by the server (default: the installation database; set by the evaluation and the tests)
    PMZILLA_LAB_OLLAMA    Ollama base URL         (default http://localhost:11434)
    PMZILLA_LAB_MODEL     embedding model         (default bge-m3)
    PMZILLA_LAB_CATALOGUE book catalogue          (default book_catalog.yaml beside this file, resolved through links)

Figures: a Markdown block written by convert_books.py (`<!-- figure id=… source=… page=… image="…" -->` followed
by "Légende : …" and "Texte alternatif : …") is never indexed as running text. It becomes a passage of its own
(kind "figure"): the caption, the useful alternative text and, when it can be found, the sentence of the book that
refers to the figure ("Figure 1.2"). Its `ref` carries the figure id, label, page, section, the path of the
image (written as plain text: no tool opens or sends the image) and where the text of the figure comes from:
`legende` (the author's caption) and `texte_alternatif` (the publisher's alternative text), each in its own field,
present only when the block has it. For a PDF, the caption line that the page text
repeats is removed from the text passages, so that it appears only once. `search_library` returns text passages
only unless `types` asks for figures.

Book catalogue: when it has an entry for a file, its title replaces the title found in the
file and its authors become the "author" field returned with every passage (like watch
articles). A change of title or author updates the index without recomputing the vectors.

Exemple :
    uv run tools/pmzilla_lab_library.py status
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import httpx
import numpy as np

from watch_paths import NEW as NEW_NAMES, OLD as OLD_NAMES, OWN_COLLECTION  # noqa: F401  (OWN_COLLECTION: read through this module)

OLLAMA_URL = os.environ.get("PMZILLA_LAB_OLLAMA", "http://localhost:11434").rstrip("/")
EMBED_MODEL = os.environ.get("PMZILLA_LAB_MODEL", "bge-m3")
# Default catalogue: tracked file beside this module's resolved file (the code root: the run tree when launched through a lab-folder link)
CATALOGUE_PATH = Path(os.environ.get(
    "PMZILLA_LAB_CATALOGUE") or Path(__file__).resolve().parent / "book_catalog.yaml").expanduser()

CHUNK_TARGET = 1500   # characters per passage, roughly
CHUNK_OVERLAP = 150   # characters repeated from the previous passage
EMBED_BATCH = 32
KINDS = ("texte", "figure")        # kinds of passage
DEFAULT_TYPES = ("texte",)         # search returns running text only unless `types` asks for figures
# Names of the kinds as the database stores them ("text" for running text), and back. One definition for the indexer,
# which writes the stored name, and for the server, which translates a search and describes a passage.
STORE_KINDS = {"texte": "text", "figure": "figure"}
KIND_NAMES = {stored: kind for kind, stored in STORE_KINDS.items()}


def check_types(types: list[str] | tuple[str, ...] | str | None) -> tuple[str, ...]:
    """Validated kinds of passage to search; running text only by default. Shared by the server and its tests."""
    if types is None:
        return DEFAULT_TYPES
    wanted = (types,) if isinstance(types, str) else tuple(types)
    unknown = sorted(set(wanted) - set(KINDS))
    if unknown or not wanted:
        raise ValueError(f"Unknown types: {unknown or list(wanted)}. Known: {list(KINDS)}")
    return tuple(dict.fromkeys(wanted))


# ---------------------------------------------------------------------------
# Embeddings (Ollama, local)
# ---------------------------------------------------------------------------

def embed(texts: list[str]) -> np.ndarray:
    """Returns L2-normalised float32 vectors, one row per text."""
    response = httpx.post(
        f"{OLLAMA_URL}/api/embed",
        json={"model": EMBED_MODEL, "input": texts},
        timeout=300,
    )
    if response.status_code == 404:
        raise SystemExit(
            f"Ollama does not know the model '{EMBED_MODEL}'. Run: ollama pull {EMBED_MODEL}"
        )
    response.raise_for_status()
    vectors = np.asarray(response.json()["embeddings"], dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0, 1, norms)


# ---------------------------------------------------------------------------
# Splitting a book into passages
# ---------------------------------------------------------------------------

HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


@dataclass
class Passage:
    section: str
    text: str
    kind: str = "texte"            # "texte" or "figure"
    ref: dict | None = None        # figures: id, label, page, section, image (a path as text), source


def read_title(text: str, fallback: str) -> tuple[str, str]:
    """Returns (title, body) — the title comes from the YAML header written by convert_books.py."""
    match = FRONT_MATTER.match(text)
    if not match:
        return fallback, text
    title = fallback
    for line in match.group(1).splitlines():
        if line.startswith("title:"):
            title = line.split(":", 1)[1].strip().strip('"') or fallback
    return title, text[match.end():]


META_FIELDS = ("url", "author", "published", "source")


def read_meta(text: str) -> dict[str, str]:
    """Article metadata from the YAML header written by watch_lab.py (url, author, published,
    source). The header is not part of the indexed passages, so it is stored with the book and
    returned with every passage: a watch article can then always be cited with its link and date."""
    match = FRONT_MATTER.match(text)
    meta: dict[str, str] = {}
    if match:
        for line in match.group(1).splitlines():
            key, _, value = line.partition(":")
            if key.strip() in META_FIELDS and value.strip():
                meta[key.strip()] = value.strip().strip('"')
    if meta.get("source") and not meta.get("author"):
        meta["author"] = f"{meta['source']} (auteur non indiqué)"  # cite the site, never an invented name
    return meta


def load_catalogue() -> dict[str, dict]:
    """Titles and authors of the books, keyed by file name (Unicode-normalised: macOS file names
    are often decomposed). Missing catalogue: empty, the titles found in the files are kept."""
    if not CATALOGUE_PATH.is_file():
        print(f"No book catalogue at {CATALOGUE_PATH}: file titles kept")
        return {}
    import yaml
    data = yaml.safe_load(CATALOGUE_PATH.read_text(encoding="utf-8")) or {}
    return {unicodedata.normalize("NFC", name): entry for name, entry in data.items() if isinstance(entry, dict)}


def clean_heading(raw: str) -> str:
    return re.sub(r"[*_`]+", "", raw).strip()


# A figure block written by convert_books.py: a one-line comment, then "Légende : …" and "Texte alternatif : …".
FIGURE_COMMENT = re.compile(r"^\s*<!--\s*figure\b(.*?)-->\s*$")
FIGURE_START = re.compile(r"^\s*<!--\s*figure\b")
FIGURE_FIELD = re.compile(r'(\w+)=(?:"([^"]*)"|(\S+))')
FIGURE_LINE = re.compile(r"^(Légende|Texte alternatif)\s*:\s*(.*)$")
# same pattern as convert_books.LABEL (a test keeps them identical): « Figure 1.2 », « Fig. 3-4 », « Exhibit 5 »…
LABEL = re.compile(r"^\s*(?:figure|fig\.?|exhibit|illustration|sch[ée]ma|diagramme|diagram|graphique|chart)\s*"
                   r"(?:[A-Z](?=[.\-]?\d)[.\-]?)?\s*\d+(?:\s*[.\-–]\s*\d+)*[a-z]?\b", re.IGNORECASE)
CAPTION_LOOKBACK = 40       # paragraphs scanned backwards, at most, for the page-text copy of a PDF caption
CAPTION_MAX_LINES = 8       # a caption wrapped over at most this many lines of the page text
REFERENCE_MAX = 400         # characters kept from the sentence that refers to a figure


def _plain(text: str) -> str:
    """Comparable form of a line: Markdown emphasis and HTML breaks removed, spaces collapsed, case folded."""
    text = re.sub(r"<br\s*/?>", " ", text)
    return " ".join(unicodedata.normalize("NFKC", re.sub(r"[*_`]+", "", text)).split()).casefold()


def _remove_caption_copy(items: list[list], figure_index: int, caption: str) -> bool:
    """A PDF page repeats the caption in its text, just before the figure block. Removes that copy from the
    nearest preceding paragraph (back to the previous figure block, at most CAPTION_LOOKBACK paragraphs) when it
    is a whole line, or a few consecutive whole lines. Returns True when a copy was removed."""
    wanted = _plain(caption)
    if not wanted:
        return False
    seen = 0
    for index in range(figure_index - 1, -1, -1):
        item = items[index]
        if item[0] == "figure":
            break   # the paragraphs before the previous figure belong to earlier pages
        if item[0] != "para":
            continue
        seen += 1
        if seen > CAPTION_LOOKBACK:
            break
        lines = item[1].split("\n")
        plain = [_plain(line) for line in lines]
        for start in range(len(lines)):
            for stop in range(start + 1, min(len(lines), start + CAPTION_MAX_LINES) + 1):
                if " ".join(p for p in plain[start:stop] if p) == wanted:
                    remaining = [l for position, l in enumerate(lines) if not start <= position < stop]
                    if any(l.strip() for l in remaining):
                        item[1] = "\n".join(remaining).strip()
                    else:
                        items[index] = ["removed"]
                    return True
    return False


def _referring_sentence(items: list[list], figure_index: int, label: str) -> str:
    """The sentence of the book that mentions the figure ("Figure 1.2 shows…"), nearest to the figure block."""
    words = re.escape(" ".join(label.split())).replace(r"\ ", r"\s*")
    pattern = re.compile(r"(?<![\w.])" + words + r"(?!\w|\.\d)", re.IGNORECASE)
    best, best_distance = "", None
    for index, item in enumerate(items):
        if item[0] != "para":
            continue
        text = " ".join(item[1].split())
        match = pattern.search(text)
        if match and (best_distance is None or abs(index - figure_index) < best_distance):
            start = max((m.end() for m in re.finditer(r"[.!?]\s", text[:match.start()])), default=0)
            end = re.search(r"[.!?](?:\s|$)", text[match.end():])
            sentence = text[start:match.end() + (end.end() if end else len(text) - match.end())].strip()
            best, best_distance = sentence[:REFERENCE_MAX], abs(index - figure_index)
    return best


def _figure_passage(item: list, section: str, items: list[list], figure_index: int) -> Passage | None:
    fields, caption, alt = item[1], item[2], item[3]
    if not caption and not alt:
        return None
    match = LABEL.match(caption) if caption else None
    label = " ".join(match.group(0).split()) if match else ""
    lines = [caption] if caption else []
    if alt and alt != caption:
        lines.append(f"Texte alternatif : {alt}")
    sentence = _referring_sentence(items, figure_index, label) if label else ""
    if sentence:
        lines.append(f"Dans le texte : {sentence}")
    ref: dict = {"id": fields.get("id", ""), "section": section}
    if caption:
        ref["legende"] = caption                 # the author's caption, as the book prints it
    if alt and alt != caption:
        ref["texte_alternatif"] = alt            # the publisher's alternative text: never the author's caption
    if label:
        ref["label"] = label
    if str(fields.get("page", "")).isdigit():
        ref["page"] = int(fields["page"])
    if fields.get("image"):
        ref["image"] = fields["image"]   # a path, kept as plain text: nothing here opens or sends the image
    if fields.get("source"):
        ref["source"] = fields["source"]
    if str(fields.get("visuels", "")).isdigit():
        ref["visuels"] = int(fields["visuels"])
    return Passage(section, "\n".join(lines), "figure", ref)


def parse_items(body: str) -> list[list]:
    """The Markdown body as a list of items: ["heading", level, title] | ["para", text] |
    ["figure", fields, caption, alt]. A figure block never becomes a paragraph, even when malformed."""
    items: list[list] = []
    block: list[str] = []
    figure: dict | None = None

    def end_block() -> None:
        if block:
            items.append(["para", "\n".join(block).strip()])
            block.clear()

    def end_figure() -> None:
        nonlocal figure
        if figure is not None:
            items.append(["figure", figure["fields"], figure["caption"], figure["alt"]])
            figure = None

    for line in body.splitlines():
        if FIGURE_START.match(line):   # never running text, even when the comment is malformed
            end_block()
            end_figure()
            comment = FIGURE_COMMENT.match(line)
            if comment:
                fields = {key: quoted or plain for key, quoted, plain in FIGURE_FIELD.findall(comment.group(1))}
                figure = {"fields": fields, "caption": "", "alt": ""}
            continue
        if figure is not None:
            field = FIGURE_LINE.match(line.strip())
            if field:
                figure["caption" if field.group(1) == "Légende" else "alt"] = field.group(2).strip()
                continue
            end_figure()
        heading = HEADING.match(line)
        if heading:
            end_block()
            items.append(["heading", len(heading.group(1)), clean_heading(heading.group(2))])
        elif line.strip():
            block.append(line)
        else:
            end_block()
    end_block()
    end_figure()
    return items


def split_passages(body: str, stats: dict | None = None) -> list[Passage]:
    """Splits on headings, then packs paragraphs into passages of about CHUNK_TARGET characters. A figure block
    (see FIGURE_COMMENT) never becomes running text: it is a passage of its own, at its place in the book; for a PDF,
    the copy of its caption in the page text is removed. `stats`, when given, counts figures and removed copies."""
    items = parse_items(body)
    for index, item in enumerate(items):   # PDF: the caption is also in the page text, keep a single copy
        if item[0] == "figure" and item[1].get("source") == "pdf" and item[2]:
            if _remove_caption_copy(items, index, item[2]) and stats is not None:
                stats["copies_retirees"] = stats.get("copies_retirees", 0) + 1
    items = [item for item in items if item[0] != "removed"]

    passages: list[Passage] = []
    path: list[tuple[int, str]] = []
    paragraphs: list[str] = []

    def section() -> str:
        return " > ".join(title for _, title in path) or "(no heading)"

    def flush() -> None:
        current = ""
        for paragraph in paragraphs:
            if current and len(current) + len(paragraph) > CHUNK_TARGET:
                passages.append(Passage(section(), current.strip()))
                current = current[-CHUNK_OVERLAP:] + "\n\n"
            current += paragraph + "\n\n"
            while len(current) > CHUNK_TARGET * 2:  # a single huge paragraph
                passages.append(Passage(section(), current[:CHUNK_TARGET].strip()))
                current = current[CHUNK_TARGET - CHUNK_OVERLAP:]
        if current.strip():
            passages.append(Passage(section(), current.strip()))
        paragraphs.clear()

    for index, item in enumerate(items):
        if item[0] == "heading":
            flush()
            level, title = item[1], item[2]
            path[:] = [(lvl, t) for lvl, t in path if lvl < level] + [(level, title)]
        elif item[0] == "para":
            paragraphs.append(item[1])
        else:
            flush()
            passage = _figure_passage(item, section(), items, index)
            if passage is not None:
                passages.append(passage)
                if stats is not None:
                    stats["figures"] = stats.get("figures", 0) + 1
    flush()
    return [p for p in passages if p.kind == "figure" or len(p.text) >= 80]  # drop page numbers and debris


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

def scan(collections_dir: Path) -> dict[str, dict]:
    """Groups the .md files by file name: a book sorted into two collections is indexed once."""
    books: dict[str, dict] = {}
    for path in sorted(collections_dir.rglob("*.md")):
        if path.name.startswith("_"):
            continue
        relative = path.relative_to(collections_dir)
        collection = relative.parts[0] if len(relative.parts) > 1 else "(none)"
        entry = books.setdefault(path.name, {"path": path, "collections": set()})
        entry["collections"].add(collection)
    return books


def select_forced(names: list[str], found: dict[str, dict]) -> set[str]:
    """File names (as keys of `found`) of the books designated by --recompute: a file name with or without
    extension, or a path whose last component is one; "@list.txt" for a list (one book per line, # = comment).
    Compared without case, in NFC. An unknown or ambiguous book stops everything before any indexing."""
    def key(text: str) -> str:
        return unicodedata.normalize("NFC", Path(re.sub(r"\.(?:epub|pdf|md)$", "", text.strip(), flags=re.IGNORECASE)
                                                   .rstrip("/")).name).casefold()

    entries: list[str] = []
    for name in names:
        if name.startswith("@"):
            lines = Path(name[1:]).expanduser().read_text(encoding="utf-8").splitlines()
            entries += [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]
        else:
            entries.append(name)
    wanted: set[str] = set()
    problems: list[str] = []
    for entry in entries:
        matches = [file_name for file_name in found if key(file_name) == key(entry)]
        if not matches:
            problems.append(f"unknown book: {entry}")
        elif len(matches) > 1:
            problems.append(f"ambiguous book: {entry} ({', '.join(sorted(matches))})")
        else:
            wanted.add(matches[0])
    if problems:
        raise SystemExit("--recompute: nothing was indexed.\n  " + "\n  ".join(problems))
    return wanted


# ---------------------------------------------------------------------------
# Store: the knowledge schema of the database (design.md D1 of db-direct-indexing)
# ---------------------------------------------------------------------------

KNOWLEDGE_DBNAME_VARIABLE = "PMZILLA_LAB_KNOWLEDGE_DBNAME"   # another database of the instance (evaluation, tests)
WRITE_ROLE = "pmzilla_knowledge"
READ_ROLE = "pmzilla_knowledge_ro"
DIMENSIONS = 1024                  # halfvec(1024) of knowledge.chunks (bge-m3)
INDEX_TARGET = "Index: database, schema knowledge"
RESTORE_POINT_REMINDER = ("Restore point: a labelled database backup taken before this run "
                          "(DB_BACKUP_DATE=YYYY-MM-DD-<label> bash tools/db_backup.sh).")
LOCK_KEY = 7_303_120_037          # session advisory lock of the knowledge library: one writing run at a time


class StoreUnavailable(Exception):
    """The database does not answer (or refuses the connection). The message is an error type, never a secret."""


def unreachable(what: str) -> str:
    """Message of a database that does not answer: no secret, no connection string (design.md D2)."""
    return f"Database unreachable: nothing was {what}. Start it: bash tools/db_up.sh"


def open_store(store, what: str) -> None:
    """Opens the store, then takes the lock of the library. Database down: exit 2; lock held by another run: exit 1."""
    try:
        store.open()
    except StoreUnavailable:
        print(unreachable(what), file=sys.stderr)
        raise SystemExit(2) from None
    try:
        locked = store.try_lock()
    except Exception:
        store.close()
        print(unreachable(what), file=sys.stderr)
        raise SystemExit(2) from None
    if not locked:
        store.close()
        raise SystemExit(f"Another indexing run is in progress: nothing was {what}.")


@dataclass(frozen=True)
class StoredBook:
    file_name: str
    sha256: str
    model: str
    title: str
    meta: dict
    collections: frozenset


@dataclass(frozen=True)
class BookRecord:
    file_name: str
    title: str
    meta: dict
    sha256: str
    model: str
    collections: frozenset


@dataclass(frozen=True)
class PassageRow:
    position: int
    section: str
    text: str
    kind: str                      # "text" or "figure"
    ref: dict
    vector: np.ndarray             # float16, L2-normalised


def knowledge_dbname() -> str | None:
    return os.environ.get(KNOWLEDGE_DBNAME_VARIABLE) or None


def canonical_json(value) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def halfvec_literal(vector: np.ndarray) -> str:
    """Exact halfvec literal of a float16 vector (9 significant digits bring the float16 value back unchanged)."""
    return "[" + ",".join("%.9g" % float(v) for v in np.asarray(vector, dtype=np.float16).astype(np.float32)) + "]"


class KnowledgeStore:
    """The library in the PostgreSQL schema `knowledge`, written under the role pmzilla_knowledge. `connect` returns a new
    connection of the cluster (default: db.connect on PMZILLA_LAB_KNOWLEDGE_DBNAME, else the installation database). Every write
    is one transaction: a book is written whole or not at all."""

    dimensions = DIMENSIONS

    def __init__(self, connect=None) -> None:
        self._connect = connect
        self.conn = None

    def open(self) -> None:
        try:
            if self._connect is None:
                import db
                conn = db.connect(dbname=knowledge_dbname())
            else:
                conn = self._connect()
            conn.execute(f"SET ROLE {WRITE_ROLE}")
            conn.commit()              # the role stays for the session, after every later commit or rollback
        except Exception as error:     # no message of the driver: it may name the server
            raise StoreUnavailable(type(error).__name__) from None
        self.conn = conn

    def close(self) -> None:
        if self.conn is not None:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None

    def try_lock(self) -> bool:
        """Session advisory lock: held until the connection closes, whatever the transactions do."""
        try:
            return bool(self.conn.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_KEY,)).fetchone()[0])
        finally:
            self.conn.commit()

    def _read(self, sql: str, params=()) -> list:
        try:
            return self.conn.execute(sql, params).fetchall()
        finally:
            self.conn.rollback()

    def _write(self, steps) -> None:
        try:
            steps(self.conn)
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def stored_books(self) -> dict[str, StoredBook]:
        rows = self._read(
            "SELECT b.file_name, b.sha256, b.model, b.title, b.meta, ARRAY(SELECT c.name FROM knowledge.book_collections bc "
            "JOIN knowledge.collections c ON c.id = bc.collection_id WHERE bc.book_id = b.id) FROM knowledge.books b")
        return {r[0]: StoredBook(r[0], r[1], r[2], r[3], r[4] or {}, frozenset(r[5] or ())) for r in rows}

    def passage_count(self) -> int:
        return int(self._read("SELECT count(*) FROM knowledge.chunks")[0][0])

    def passage_counts(self) -> dict[str, int]:
        return {r[0]: int(r[1]) for r in self._read(
            "SELECT b.file_name, count(c.id) FROM knowledge.books b LEFT JOIN knowledge.chunks c ON c.book_id = b.id "
            "GROUP BY b.file_name")}

    @staticmethod
    def _memberships(conn, book_id: int, collections) -> None:
        for name in sorted(collections):
            collection_id = conn.execute(
                "INSERT INTO knowledge.collections (name) VALUES (%s) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name "
                "RETURNING id", (name,)).fetchone()[0]
            conn.execute("INSERT INTO knowledge.book_collections (book_id, collection_id) VALUES (%s, %s)",
                         (book_id, collection_id))

    def replace_book(self, record: BookRecord, rows: list[PassageRow]) -> None:
        def steps(conn):
            conn.execute("DELETE FROM knowledge.books WHERE file_name = %s", (record.file_name,))   # passages cascade
            book_id = conn.execute(
                "INSERT INTO knowledge.books (file_name, title, meta, sha256, model, indexed_at) "
                "VALUES (%s, %s, %s::jsonb, %s, %s, now()) RETURNING id",
                (record.file_name, record.title, canonical_json(record.meta), record.sha256, record.model)).fetchone()[0]
            self._memberships(conn, book_id, record.collections)
            with conn.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO knowledge.chunks (book_id, position, section, text, embedding, kind, ref) "
                    "VALUES (%s, %s, %s, %s, %s::halfvec, %s, %s::jsonb)",
                    [(book_id, r.position, r.section, r.text, halfvec_literal(r.vector), r.kind, canonical_json(r.ref))
                     for r in rows])
        self._write(steps)

    def update_book(self, file_name: str, title: str, meta: dict, collections) -> None:
        def steps(conn):
            book_id = conn.execute("UPDATE knowledge.books SET title = %s, meta = %s::jsonb WHERE file_name = %s RETURNING id",
                                   (title, canonical_json(meta), file_name)).fetchone()[0]
            conn.execute("DELETE FROM knowledge.book_collections WHERE book_id = %s", (book_id,))
            self._memberships(conn, book_id, collections)
        self._write(steps)

    def delete_book(self, file_name: str) -> None:
        self._write(lambda conn: conn.execute("DELETE FROM knowledge.books WHERE file_name = %s", (file_name,)))

    @staticmethod
    def _delete_orphans(conn) -> list[str]:
        return sorted(r[0] for r in conn.execute(
            "DELETE FROM knowledge.collections c WHERE NOT EXISTS "
            "(SELECT 1 FROM knowledge.book_collections bc WHERE bc.collection_id = c.id) RETURNING c.name").fetchall())

    def delete_orphan_collections(self) -> list[str]:
        removed: list[str] = []
        self._write(lambda conn: removed.extend(self._delete_orphans(conn)))
        return removed

    def set_collections(self, changes: dict[str, frozenset]) -> None:
        """New memberships of several books, then the orphan collections deleted, in one transaction (rename-collection)."""
        def steps(conn):
            for file_name, names in sorted(changes.items()):
                book_id = conn.execute("SELECT id FROM knowledge.books WHERE file_name = %s", (file_name,)).fetchone()[0]
                conn.execute("DELETE FROM knowledge.book_collections WHERE book_id = %s", (book_id,))
                self._memberships(conn, book_id, names)
            self._delete_orphans(conn)
        self._write(steps)


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

def collection_of(folder: str, warned: set[str]) -> str:
    """Current name of a collection folder: the former watch name is stored under the current one, with a warning (once)."""
    if folder == OLD_NAMES["collection"]:
        if folder not in warned:
            warned.add(folder)
            print(f"Warning: the folder '{folder}' carries the former name of the collection '{NEW_NAMES['collection']}': "
                  f"its books are stored under '{NEW_NAMES['collection']}'.", file=sys.stderr)
        return NEW_NAMES["collection"]
    return folder


def index(collections_dirs: list[Path], force: list[str] | None = None, store=None, allow_empty: bool = False) -> None:
    """Indexes the folders into the knowledge schema of the database (design.md D1): unchanged books are skipped, a book whose
    collections, title or metadata changed is updated without re-embedding, a new or changed book is replaced whole, in one
    transaction. No file of the data folder is created, opened or read. A book that cannot be written is named and the run ends with
    exit code 1 after the other books. Order (design.md D1): folders and --recompute checked, store opened (database down:
    exit 2, before any embedding call), lock taken (another run: exit 1), stored books read, empty-scan guard (folders
    without any book against a filled database: exit 1 unless `allow_empty`), removals, books, orphan collections."""
    if force:   # a reminder only: the indexer never takes a backup and never reads the backup folder (design.md D5)
        print(RESTORE_POINT_REMINDER)
    found: dict[str, dict] = {}
    warned: set[str] = set()
    for collections_dir in collections_dirs:
        collections_dir = collections_dir.expanduser().resolve()
        if not collections_dir.is_dir():
            raise SystemExit(f"Not a folder: {collections_dir}")
        books = scan(collections_dir)
        print(f"{len(books)} files found in {collections_dir}")
        for file_name, info in books.items():
            entry = found.setdefault(file_name, {"path": info["path"], "collections": set()})
            entry["collections"] |= {collection_of(name, warned) for name in info["collections"]}
    forced = select_forced(force, found) if force else set()   # checked before the database is touched
    store = store if store is not None else KnowledgeStore()
    open_store(store, "indexed")
    try:
        _index_into(store, found, forced, allow_empty)
    finally:
        store.close()


def _index_into(store, found: dict[str, dict], forced: set[str], allow_empty: bool) -> None:
    known = store.stored_books()
    if not found and known and not allow_empty:
        raise SystemExit(f"No book found in the folders while the database holds {len(known)}: nothing was removed "
                         "(--allow-empty empties the library).")
    catalogue = load_catalogue()
    for file_name in sorted(set(known) - set(found)):
        store.delete_book(file_name)
        print(f"  removed: {file_name}")

    started = time.time()
    done = skipped = 0
    failed: list[str] = []
    for number, (file_name, info) in enumerate(sorted(found.items()), 1):
        text = info["path"].read_text(encoding="utf-8", errors="replace")
        digest = hashlib.sha256(text.encode()).hexdigest()
        collections = frozenset(info["collections"])
        title, body = read_title(text, Path(file_name).stem)
        meta = read_meta(text)
        entry = catalogue.get(unicodedata.normalize("NFC", file_name))
        if entry:  # the catalogue wins over what the file says
            title = str(entry.get("titre") or title)
            meta["author"] = (", ".join(str(a) for a in entry["auteurs"])
                              if entry.get("auteurs") else "auteur non indiqué")
        previous = known.get(file_name)
        if previous and previous.sha256 == digest and previous.model == EMBED_MODEL and file_name not in forced:
            if (previous.collections != collections or canonical_json(previous.meta) != canonical_json(meta)
                    or previous.title != title):   # no re-embedding needed
                store.update_book(file_name, title, meta, collections)
            skipped += 1
            continue

        figure_stats: dict = {}
        passages = split_passages(body, figure_stats)
        extra = (f" (dont {figure_stats['figures']} figures, {figure_stats.get('copies_retirees', 0)} légendes "
                 f"du texte de page retirées)") if figure_stats.get("figures") else ""
        print(f"[{number}/{len(found)}] {title} — {len(passages)} passages{extra}")
        vectors = []
        for start in range(0, len(passages), EMBED_BATCH):
            batch = passages[start:start + EMBED_BATCH]
            vectors.append(embed([f"{title}\n{p.section}\n{p.text}" for p in batch]))
        matrix = np.vstack(vectors) if vectors else np.zeros((0, store.dimensions), dtype=np.float32)
        if matrix.shape[0] != len(passages) or (passages and matrix.shape[1] != store.dimensions):
            print(f"  not indexed: {file_name}: {matrix.shape[0]} vectors of {matrix.shape[1]} dimensions for "
                  f"{len(passages)} passages, {store.dimensions} dimensions expected", file=sys.stderr)
            failed.append(file_name)
            continue
        rows = [PassageRow(position, p.section, p.text, STORE_KINDS.get(p.kind, p.kind), dict(p.ref or {}),
                           matrix[position].astype(np.float16))
                for position, p in enumerate(passages)]
        record = BookRecord(file_name, title, meta, digest, EMBED_MODEL, collections)
        try:
            store.replace_book(record, rows)   # one book at a time: an interrupted run resumes where it stopped
        except Exception as error:
            print(f"  not indexed: {file_name}: {type(error).__name__}, nothing was written for this book", file=sys.stderr)
            failed.append(file_name)
            continue
        done += 1

    store.delete_orphan_collections()
    total = store.passage_count()
    print(
        f"\nIndexed: {done} · unchanged: {skipped} · passages in the index: {total} · "
        f"{(time.time() - started) / 60:.1f} min\n{INDEX_TARGET}"
    )
    if failed:
        raise SystemExit(f"Not indexed ({len(failed)}): {', '.join(failed)}")


def rename_collection(old: str, new: str, dry_run: bool = False, store=None) -> dict[str, int]:
    """Renames a collection in the database, in place, under the writing role and in one transaction: only the memberships
    change (a book that already holds the new name keeps one membership), the former collection is deleted when no book uses
    it. Passages, vectors, hashes and file names are untouched, so nothing is recomputed. Idempotent: a second run finds
    nothing to rename. Database down: exit 2; another run in progress: exit 1."""
    if not old or not new or "|" in old or "|" in new:
        raise SystemExit("rename-collection needs two collection names, without '|'.")
    store = store if store is not None else KnowledgeStore()
    open_store(store, "renamed")
    try:
        counts = store.passage_counts()
        books = passages = both = 0
        changes: dict[str, frozenset] = {}
        for file_name, book in sorted(store.stored_books().items()):
            if old not in book.collections:
                continue
            both += new in book.collections
            books += 1
            passages += counts.get(file_name, 0)
            changes[file_name] = frozenset(new if name == old else name for name in book.collections)
        if not dry_run and changes:
            store.set_collections(changes)   # one transaction, orphan collections included
    finally:
        store.close()
    verb = "would be renamed" if dry_run else "renamed"
    print(f"Collection '{old}' -> '{new}': {books} books ({passages} passages) {verb}"
          + (f", of which {both} already in '{new}'" if both else "")
          + ("." if books else " (nothing to do)."))
    print(f"Vectors recomputed: 0. {INDEX_TARGET}")
    return {"books": books, "passages": passages, "already": both}


# ---------------------------------------------------------------------------
# Probe of the BM25 index and counts (read-only role; design.md D3, D4)
# ---------------------------------------------------------------------------

PROBE_WORDS = "the flux flow"   # common words (an OR of words, like the search): the probe reads the index, not a rare case
BM25_UNREADABLE = 3
DAMAGED_PROCEDURE = 'Procedure: docs/pmzilla/installation.md, "Damaged BM25 index"'


def _read_connection(connect, what: str):
    """A connection under the read-only role pmzilla_knowledge_ro (database PMZILLA_LAB_KNOWLEDGE_DBNAME when set), or None
    after printing the unreachable message (no secret, no connection string)."""
    try:
        if connect is None:
            import db
            return db.connect(role=READ_ROLE, dbname=knowledge_dbname())
        return connect()
    except Exception:
        print(unreachable(what), file=sys.stderr)
        return None


def bm25_probe(conn) -> str | None:
    """Reads the BM25 index like the search does: without a filter, then filtered on figure passages. None when both queries
    succeed; otherwise "variant: error type". Each query ends its transaction; nothing is repaired or written, and the error
    message itself is never returned (no book text can reach the output)."""
    variants = (("no filter", ""), ("figure kind", " AND c.kind = ANY(%s::text[])"))
    try:
        for name, kind_filter in variants:
            params = (PROBE_WORDS,) + ((["figure"],) if kind_filter else ())
            try:
                conn.execute("SELECT c.id FROM knowledge.chunks c WHERE c.fts_text ||| %s" + kind_filter +
                             " ORDER BY pdb.score(c.id) DESC LIMIT 50", params).fetchall()
            except Exception as error:      # InternalError of a damaged index, but also any other error of the probe
                return f"{name}: {type(error).__name__}"
            finally:
                conn.rollback()             # ends the transaction, also after an error
    except Exception as error:              # rollback impossible: the probe cannot conclude
        return f"probe impossible: {type(error).__name__}"
    return None


def probe(connect=None) -> int:
    """`probe`: 0 readable, 3 unreadable (with the procedure), 2 the database does not answer."""
    conn = _read_connection(connect, "probed")
    if conn is None:
        return 2
    try:
        failure = bm25_probe(conn)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    if failure:
        print(f"BM25 index unreadable ({failure})")
        print(DAMAGED_PROCEDURE)
        return BM25_UNREADABLE
    print("BM25 index readable")
    return 0


def status(connect=None) -> int:
    """`status`: one line of counts (books, passages, figures, collections), never a title, a file name or a text."""
    conn = _read_connection(connect, "read")
    if conn is None:
        return 2
    try:
        books, passages, figures, collections = conn.execute(
            "SELECT (SELECT count(*) FROM knowledge.books), (SELECT count(*) FROM knowledge.chunks), "
            "(SELECT count(*) FROM knowledge.chunks WHERE kind = 'figure'), (SELECT count(*) FROM knowledge.collections)"
        ).fetchone()
        conn.rollback()
    except Exception:
        print(unreachable("read"), file=sys.stderr)
        return 2
    finally:
        try:
            conn.close()
        except Exception:
            pass
    print(f"database: {books} books · {passages} passages · {figures} figures · {collections} collections")
    return 0


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

BACKEND_VARIABLE = "PMZILLA_LAB_BACKEND"     # former choice of route: read by nothing any more, only reported
BACKEND_REFUSED = ("pmzilla-library serve: the --backend option was removed. The library is served from PostgreSQL only. "
                   "Remove the option from the server registration (claude mcp get pmzilla-library shows the command "
                   "line), then restart the session.")
SERVE_USAGE = "Usage: serve (no argument)"
DATABASE_ERROR_HINT = ("If the database is stopped, start it with bash tools/db_up.sh. If it is running, the keyword index may be "
                       'unreadable: see the installation guide, section "Damaged BM25 index".')


def database_error(error: Exception) -> dict:
    """The error object of a library tool whose database query failed: the error type only, never its message (it may hold
    SQL), with the remedy. The server keeps running."""
    return {"error": f"library database error ({type(error).__name__}). {DATABASE_ERROR_HINT}"}


def open_library():
    """The library object of the server: always PostgreSQL, never a fallback when the database does not answer."""
    import knowledge_library
    return knowledge_library.PostgresLibrary()


def make_cases_reader():
    """The cases reader of the server (design.md 4 of db-lot2): no connection until its first call. Module-level so that tests patch it."""
    import cases_store
    return cases_store.CasesReader()


def serve() -> None:
    from mcp.server.fastmcp import FastMCP

    if BACKEND_VARIABLE in os.environ:
        print(f"Warning: {BACKEND_VARIABLE} is ignored: the library is served from PostgreSQL only.", file=sys.stderr)
    library = open_library()
    server = FastMCP("pmzilla-lab-library")
    def unknown_collections_error(names: list[str]) -> dict | None:
        """The error object for collection names that are not in the index, or None. The former name "veille"
        gets no alias: the error says to use "watch"."""
        known = library.collections()
        unknown = sorted(set(names) - set(known))
        if not unknown:
            return None
        hint = " The former name 'veille' is no longer accepted: use 'watch'." if "veille" in unknown else ""
        return {"error": f"Unknown collections: {unknown}. Known: {list(known)}.{hint}"}

    @server.tool()
    def search_library(
        query: str, collections: list[str] | None = None, limit: int = 8, since: str | None = None,
        types: list[str] | None = None,
    ) -> list[dict] | dict:
        """Search the user's digital library (books on product management, agile, lean, organisation
        design, facilitation, software architecture) and return the most relevant passages, each
        with its book, section and passage_id. Phrase the query as an idea or a question, in French
        or English; run several searches with different wordings to explore a topic. Optionally
        restrict to one or more collections (names from list_collections); omit them to search the
        whole library. The collections "watch" (recent articles from followed blogs and
        newsletters) and "own-articles" (the user's own published articles) return, with each passage, the
        article's url, author and published date. Always cite book and section when using a passage, and
        author, title (the "book" field), url and published date for an article. Optionally pass
        `since` (YYYY-MM-DD) to keep only articles published on or after that date, for fast-moving
        topics; books have no date and are not filtered (restrict to collections ["watch"] to get
        articles only). Among passages of similar relevance, recent watch articles come first. The former name
        "veille" is refused: use "watch".
        `types` ("texte", "figure") chooses the kind of passage: running text only by default. With
        ["figure"] (or ["texte", "figure"]) a figure passage is returned as kind "figure": the author's
        caption, the useful alternative text and the sentence that refers to the figure, with a `ref`
        (label such as "Figure 1.2", page, section, `image`, a file path written as plain text, and `legende` /
        `texte_alternatif`, which say whether the text comes from the author's caption or the publisher's alt text).
        You cannot open or see the image and must never describe it: cite the author, title, label,
        section and page, quote the caption as the book writes it, and present any inference about what
        the image shows as your own deduction."""
        try:
            if collections:
                refused = unknown_collections_error(collections)
                if refused:
                    return refused
            if since:
                try:
                    dt.date.fromisoformat(since)
                except ValueError:
                    return {"error": f"since must be a date YYYY-MM-DD, got {since!r}"}
            return library.search(query, collections, max(1, min(limit, 20)), since, types)
        except ValueError as error:
            return {"error": str(error)}
        except Exception as error:       # the database layer, after its single reconnection
            return database_error(error)

    @server.tool()
    def read_passage(passage_id: int, before: int = 1, after: int = 2) -> dict:
        """Read a passage returned by search_library together with the passages around it in the
        same book (before/after: how many neighbouring passages, up to 5 each). Use it when a
        result is central and you need the full argument, not only the excerpt. Each passage has a
        `kind` ("texte" or "figure"); a figure passage also has its `ref`."""
        try:
            return library.read(passage_id, max(0, min(before, 5)), max(0, min(after, 5)))
        except Exception as error:
            return database_error(error)

    @server.tool()
    def list_collections() -> dict[str, int | str]:
        """List the collections of the library with their number of books."""
        try:
            return dict(library.collections())
        except Exception as error:
            return database_error(error)

    @server.tool()
    def list_books(collection: str | None = None) -> list[dict]:
        """List the books in the library with their collections and size. Use it to know what the
        library covers or to pick a collection to search in. An unknown collection name, including the
        former name "veille" (use "watch"), returns an error object."""
        try:
            refused = unknown_collections_error([collection]) if collection else None
            if refused:
                return [refused]
            return library.books(collection)
        except Exception as error:
            return [database_error(error)]

    cases: list = []   # the cases reader, created at the first cases call: the library tools never depend on it

    def cases_answer(call, query: str | None = None):
        """Runs `call(reader)`; every refusal is an error object, never a stop of the server."""
        import cases_store
        if query is not None and not query.strip():
            return {"error": "the question is empty"}
        try:
            if not cases:
                cases.append(make_cases_reader())
            return call(cases[0])
        except cases_store.CasesError as error:
            return {"error": str(error)}

    @server.tool()
    def search_cases(query: str, limit: int = 3) -> list[dict] | dict:
        """Search the closed cases (finished experiments, with their outcome) of the personal cases base, which
        is separate from the library. Phrase the query as the problem at hand, in French or English. Returns up
        to `limit` cases (1 to 10, default 3), possibly none, each with its similarity and score; cases below the
        similarity threshold are dropped. Read-only. Failures come back as {"error": "..."}."""
        return cases_answer(lambda reader: reader.search_cases(query, limit), query)

    @server.tool()
    def search_experiments(query: str, limit: int = 3) -> list[dict] | dict:
        """Search the running experiments of the personal cases base, which is separate from the library.
        Phrase the query as the problem at hand, in French or English. Returns up to `limit` running experiments
        (1 to 10, default 3), possibly none, each with `mine` (true only for the configured author's own
        experiment), its similarity and score. Read-only. Failures come back as {"error": "..."}."""
        return cases_answer(lambda reader: reader.search_experiments(query, limit), query)

    @server.tool()
    def list_due_reviews() -> list[dict] | dict:
        """List the configured author's running experiments whose review date has come, oldest first, each with
        its number, problem, review date, number of postponements and whether a decision is required. Takes no
        argument. Read-only. Without a configured author, or on any other failure, the answer is {"error": "..."}."""
        return cases_answer(lambda reader: reader.list_due_reviews())

    server.run()


def main(store=None, connect=None) -> None:
    """Command line. `store` replaces the database store and `connect` the read-only connection (tests only)."""
    import flux_config
    sys.argv[1:] = flux_config.refuse_old_options(sys.argv[1:], {"--recalculer": "--recompute"})
    if len(sys.argv) >= 3 and sys.argv[1] == "index":
        args = sys.argv[2:]
        allow_empty = "--allow-empty" in args
        args = [arg for arg in args if arg != "--allow-empty"]
        force = None
        if "--recompute" in args:
            position = args.index("--recompute")
            args, force = args[:position], args[position + 1:]
            if not force:
                sys.exit("--recompute needs at least one book (or @list.txt).")
        if not args:
            sys.exit("index needs at least one collections folder before --recompute.")
        index([Path(arg) for arg in args], force, store=store, allow_empty=allow_empty)
    elif len(sys.argv) in (4, 5) and sys.argv[1] == "rename-collection":
        extra = sys.argv[4:]
        if extra not in ([], ["--dry-run"]):
            sys.exit("Usage: rename-collection <old> <new> [--dry-run]")
        rename_collection(sys.argv[2], sys.argv[3], bool(extra), store=store)
    elif len(sys.argv) >= 2 and sys.argv[1] in ("probe", "status"):
        if len(sys.argv) != 2:
            sys.exit(f"Usage: {sys.argv[1]} (no argument)")
        sys.exit((probe if sys.argv[1] == "probe" else status)(connect))
    elif len(sys.argv) >= 2 and sys.argv[1] == "serve":
        extra = sys.argv[2:]
        if any(arg == "--backend" or arg.startswith("--backend=") for arg in extra):
            print(BACKEND_REFUSED, file=sys.stderr)
            sys.exit(2)
        if extra:
            print(SERVE_USAGE, file=sys.stderr)
            sys.exit(2)
        serve()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
