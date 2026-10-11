# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=1.2,<2", "numpy", "httpx", "pyyaml", "psycopg[binary]"]
# ///
"""
PMZilla Lab — library server.

Gives Claude Code access to the digital library (Markdown files produced by
convert_books.py and sorted by ventiler_collections.py) through an MCP server.

Two commands:

    uv run pmzilla_lab_library.py index <collections_dir> [<collections_dir> ...]
        Builds or updates the local index (incremental: only new or changed
        books are re-embedded). Each <collections_dir> holds one sub-folder per
        collection, e.g. ~/PMZilla-Lab/workspace/Bibliotheque-Lab ~/PMZilla-Lab/workspace/Watch-Lab. Always pass every
        folder: a file missing from all of them is removed from the index.

    uv run pmzilla_lab_library.py index <collections_dir> [...] --recompute <book> [<book> ...]
        Same, and re-embeds the designated books even when their Markdown is unchanged (e.g. after the
        passage format changed). A book is a file name with or without extension, or a path ending with
        one; "@list.txt" reads a list (one book per line, # = comment). An unknown or ambiguous book
        stops everything before the index is touched. It makes no backup of the index.

    uv run pmzilla_lab_library.py rename-collection <old> <new> [--dry-run]
        Renames a collection inside the index, in place, in one transaction, without touching a vector (the
        file name, the hash and the passages do not change; the full-text table does not hold collections).
        Prints the counts; --dry-run only prints them. Idempotent. Example: rename-collection veille watch.

    uv run pmzilla_lab_library.py serve [--backend sqlite|postgres]
        Starts the MCP server on stdio (Claude Code launches it itself). The backend is the PostgreSQL schema `knowledge`
        (default since the lot 4 switch) or the local SQLite index (fallback for one month; lot 4 of the database, tools/knowledge_library.py, read-only
        role pmzilla_knowledge_ro); PMZILLA_LAB_BACKEND gives the same choice when the option is absent. The four
        library tools are the same on both. Three more tools, read-only, serve the cases module (search_cases,
        search_experiments, list_due_reviews): seven tools in all. They answer from the cases database (schema
        `cases`, role pmzilla_cases_ro, database PMZILLA_LAB_CASES_DBNAME when set), opened at the first call; they return
        an error object on the SQLite backend or when that database does not answer, and the four library tools never depend on it. `index` and `rename-collection` always work on the SQLite index.

Search is hybrid: semantic (bge-m3 embeddings through Ollama, computed on this
Mac) and keyword (SQLite FTS5), merged by reciprocal rank fusion. Only the
passages returned by a search ever reach Claude.

Environment variables (all optional):
    PMZILLA_LAB_BACKEND   sqlite | postgres       (default postgres since lot 4; sqlite = fallback for one month; the `serve --backend` option wins)
    PMZILLA_LAB_DATA      index folder            (default ~/.pmzilla-lab)
    PMZILLA_LAB_OLLAMA    Ollama base URL         (default http://localhost:11434)
    PMZILLA_LAB_MODEL     embedding model         (default bge-m3)
    PMZILLA_LAB_CATALOGUE book catalogue          (default ~/PMZilla-Lab/workspace/tools/book_catalog.yaml)

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
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import httpx
import numpy as np

from watch_paths import OWN_COLLECTION

DATA_DIR = Path(os.environ.get("PMZILLA_LAB_DATA", "~/.pmzilla-lab")).expanduser()
DB_PATH = DATA_DIR / "library.sqlite"
OLLAMA_URL = os.environ.get("PMZILLA_LAB_OLLAMA", "http://localhost:11434").rstrip("/")
EMBED_MODEL = os.environ.get("PMZILLA_LAB_MODEL", "bge-m3")
CATALOGUE_PATH = Path(os.environ.get(
    "PMZILLA_LAB_CATALOGUE", "~/PMZilla-Lab/workspace/tools/book_catalog.yaml")).expanduser()

CHUNK_TARGET = 1500   # characters per passage, roughly
CHUNK_OVERLAP = 150   # characters repeated from the previous passage
EMBED_BATCH = 32
RRF_K = 60            # reciprocal rank fusion constant
CANDIDATES = 50       # candidates taken from each search before fusion
# Freshness: a small bonus for watch articles, halved every FRESHNESS_HALF_LIFE days. It only
# reorders passages that are close in relevance (one rank of fusion is worth about 0.0003 near the
# top), and breaks exact ties. Books and the personal collection do not age: they get the neutral value
# of a six-month-old article, so a recent article passes them at equal relevance and an old one
# falls behind them.
FRESHNESS_BONUS = float(os.environ.get("PMZILLA_LAB_FRESHNESS", "0.001"))
FRESHNESS_HALF_LIFE = 180
FRESHNESS_COLLECTIONS = {"watch"}
KINDS = ("texte", "figure")        # kinds of passage
DEFAULT_TYPES = ("texte",)         # search returns running text only unless `types` asks for figures


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id          INTEGER PRIMARY KEY,
    file_name   TEXT UNIQUE NOT NULL,   -- e.g. "Leading Change.md"
    title       TEXT NOT NULL,
    sha256      TEXT NOT NULL,
    collections TEXT NOT NULL,          -- "|"-separated collection names
    model       TEXT NOT NULL,
    indexed_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    id        INTEGER PRIMARY KEY,
    book_id   INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    position  INTEGER NOT NULL,         -- order of the passage in the book
    section   TEXT NOT NULL,            -- heading path, e.g. "Part I > Chapter 3"
    text      TEXT NOT NULL,
    embedding BLOB NOT NULL,            -- float16, L2-normalised
    kind      TEXT NOT NULL DEFAULT 'texte',   -- 'texte' or 'figure'
    ref       TEXT NOT NULL DEFAULT '{}'       -- JSON; figures: id, label, page, section, image (a path, as text)
);
CREATE INDEX IF NOT EXISTS chunks_book ON chunks(book_id, position);
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text, section, content='chunks', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text, section) VALUES (new.id, new.text, new.section);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text, section)
    VALUES ('delete', old.id, old.text, old.section);
END;
"""


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(SCHEMA)
    columns = {row[1] for row in db.execute("PRAGMA table_info(books)")}
    if "meta" not in columns:  # index created before the article metadata (url, author, published)
        db.execute("ALTER TABLE books ADD COLUMN meta TEXT NOT NULL DEFAULT '{}'")
        db.commit()
    migrate_chunks(db)
    return db


def migrate_chunks(db: sqlite3.Connection) -> None:
    """Adds `kind` and `ref` to an index created before the figures. Existing passages become text passages;
    nothing is recomputed or lost."""
    columns = {row[1] for row in db.execute("PRAGMA table_info(chunks)")}
    if "kind" not in columns:
        db.execute("ALTER TABLE chunks ADD COLUMN kind TEXT NOT NULL DEFAULT 'texte'")
    if "ref" not in columns:
        db.execute("ALTER TABLE chunks ADD COLUMN ref TEXT NOT NULL DEFAULT '{}'")
    db.execute("CREATE INDEX IF NOT EXISTS chunks_kind ON chunks(kind)")
    db.commit()


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


def index(collections_dirs: list[Path], force: list[str] | None = None) -> None:
    found: dict[str, dict] = {}
    for collections_dir in collections_dirs:
        collections_dir = collections_dir.expanduser().resolve()
        if not collections_dir.is_dir():
            raise SystemExit(f"Not a folder: {collections_dir}")
        books = scan(collections_dir)
        print(f"{len(books)} files found in {collections_dir}")
        for file_name, info in books.items():
            entry = found.setdefault(file_name, {"path": info["path"], "collections": set()})
            entry["collections"] |= info["collections"]
    forced = select_forced(force, found) if force else set()   # checked before the index is touched
    db = connect()
    catalogue = load_catalogue()

    known = {row[0]: row for row in db.execute(
        "SELECT file_name, sha256, collections, model, meta, title FROM books")}
    for file_name in set(known) - set(found):
        db.execute("DELETE FROM books WHERE file_name = ?", (file_name,))
        print(f"  removed: {file_name}")
    db.commit()

    started = time.time()
    done = skipped = 0
    for number, (file_name, info) in enumerate(sorted(found.items()), 1):
        text = info["path"].read_text(encoding="utf-8", errors="replace")
        digest = hashlib.sha256(text.encode()).hexdigest()
        collections = "|".join(sorted(info["collections"]))
        title, body = read_title(text, Path(file_name).stem)
        meta_dict = read_meta(text)
        entry = catalogue.get(unicodedata.normalize("NFC", file_name))
        if entry:  # the catalogue wins over what the file says
            title = str(entry.get("titre") or title)
            meta_dict["author"] = (", ".join(str(a) for a in entry["auteurs"])
                                   if entry.get("auteurs") else "auteur non indiqué")
        meta = json.dumps(meta_dict, ensure_ascii=False, sort_keys=True)
        previous = known.get(file_name)
        if previous and previous[1] == digest and previous[3] == EMBED_MODEL and file_name not in forced:
            if previous[2] != collections or previous[4] != meta or previous[5] != title:  # no re-embedding needed
                db.execute("UPDATE books SET collections = ?, meta = ?, title = ? WHERE file_name = ?",
                           (collections, meta, title, file_name))
                db.commit()
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
        matrix = np.vstack(vectors) if vectors else np.zeros((0, 1), dtype=np.float32)

        db.execute("DELETE FROM books WHERE file_name = ?", (file_name,))
        cursor = db.execute(
            "INSERT INTO books (file_name, title, sha256, collections, model, indexed_at, meta) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (file_name, title, digest, collections, EMBED_MODEL, time.time(), meta),
        )
        db.executemany(
            "INSERT INTO chunks (book_id, position, section, text, embedding, kind, ref) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (cursor.lastrowid, position, p.section, p.text, matrix[position].astype(np.float16).tobytes(),
                 p.kind, json.dumps(p.ref or {}, ensure_ascii=False, sort_keys=True))
                for position, p in enumerate(passages)
            ],
        )
        db.commit()  # one book at a time: an interrupted run resumes where it stopped
        done += 1

    total = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    print(
        f"\nIndexed: {done} · unchanged: {skipped} · passages in the index: {total} · "
        f"{(time.time() - started) / 60:.1f} min\nIndex: {DB_PATH}"
    )


def rename_collection(old: str, new: str, dry_run: bool = False) -> dict[str, int]:
    """Renames a collection in the index, in place: only books.collections changes (one transaction). The
    vectors, the passages, the hash and the file name are untouched, and chunks_fts holds the text and the
    section only, so nothing is recomputed. Idempotent: a second run finds nothing to rename."""
    if not old or not new or "|" in old or "|" in new:
        raise SystemExit("rename-collection needs two collection names, without '|'.")
    if not DB_PATH.exists():
        raise SystemExit(f"No index at {DB_PATH}. Run the 'index' command first.")
    db = connect()
    books = passages = both = 0
    changes = []
    for book_id, names in db.execute("SELECT id, collections FROM books"):
        parts = names.split("|")
        if old not in parts:
            continue
        renamed = "|".join(sorted({new if part == old else part for part in parts}))
        both += new in parts
        books += 1
        passages += db.execute("SELECT COUNT(*) FROM chunks WHERE book_id = ?", (book_id,)).fetchone()[0]
        changes.append((renamed, book_id))
    if not dry_run and changes:
        with db:   # one transaction
            db.executemany("UPDATE books SET collections = ? WHERE id = ?", changes)
    verb = "would be renamed" if dry_run else "renamed"
    print(f"Collection '{old}' -> '{new}': {books} books ({passages} passages) {verb}"
          + (f", of which {both} already in '{new}'" if both else "")
          + ("." if books else " (nothing to do)."))
    print("Vectors recomputed: 0. Index: " + str(DB_PATH))
    return {"books": books, "passages": passages, "already": both}


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class Library:
    """Loads the index once; vectors stay in memory for fast semantic search. The index is reloaded
    when it changes on disk (daily watch collection), so no restart is needed."""

    def __init__(self) -> None:
        if not DB_PATH.exists():
            raise SystemExit(f"No index at {DB_PATH}. Run the 'index' command first.")
        self.db = connect()
        self.db.row_factory = sqlite3.Row
        self._load()

    def _load(self) -> None:
        self.loaded_at = DB_PATH.stat().st_mtime
        # publication date and collections of each passage's document, for the date filter and the
        # freshness bonus (books have no date)
        self.chunk_info: dict[int, tuple[set[str], str]] = {}
        self.kinds: dict[int, str] = {}
        for row in self.db.execute(
            "SELECT c.id, b.collections, b.meta, c.kind FROM chunks c JOIN books b ON b.id = c.book_id"
        ):
            published = str(json.loads(row["meta"] or "{}").get("published", ""))[:10]
            self.chunk_info[row["id"]] = (set(row["collections"].split("|")), published)
            self.kinds[row["id"]] = row["kind"]
        rows = self.db.execute("SELECT id, embedding FROM chunks ORDER BY id").fetchall()
        self.ids = np.array([row["id"] for row in rows], dtype=np.int64)
        self.vectors = (
            np.vstack([np.frombuffer(row["embedding"], dtype=np.float16) for row in rows]).astype(np.float32)
            if rows else np.zeros((0, 1), dtype=np.float32)
        )

    def refresh(self) -> None:
        if DB_PATH.stat().st_mtime > self.loaded_at:
            self._load()

    def _collection_filter(self, collections: list[str] | None) -> set[int] | None:
        """Passages of the books that belong to at least one of the given collections."""
        if not collections:
            return None
        wanted = set(collections)
        rows = self.db.execute(
            "SELECT c.id, b.collections FROM chunks c JOIN books b ON b.id = c.book_id"
        ).fetchall()
        return {row["id"] for row in rows if wanted & set(row["collections"].split("|"))}

    @staticmethod
    def check_types(types: list[str] | tuple[str, ...] | str | None) -> tuple[str, ...]:
        """Validated kinds of passage to search; running text only by default."""
        if types is None:
            return DEFAULT_TYPES
        wanted = (types,) if isinstance(types, str) else tuple(types)
        unknown = sorted(set(wanted) - set(KINDS))
        if unknown or not wanted:
            raise ValueError(f"Unknown types: {unknown or list(wanted)}. Known: {list(KINDS)}")
        return tuple(dict.fromkeys(wanted))

    def _type_filter(self, types: tuple[str, ...], allowed: set[int] | None) -> set[int] | None:
        """Passages of the wanted kinds (None = no restriction: every kind is wanted)."""
        if set(types) == set(KINDS):
            return allowed
        return {cid for cid, kind in self.kinds.items() if kind in types and (allowed is None or cid in allowed)}

    def _semantic(self, query: str, allowed: set[int] | None) -> list[int]:
        if not len(self.ids):
            return []
        scores = self.vectors @ embed([query])[0]
        # equal relevance (to 3 decimals): the most recent watch article first
        fresh = np.array([self._freshness(int(i), dt.date.today()) for i in self.ids])
        order = np.lexsort((-fresh, -np.round(scores, 3)))
        ranked = [int(self.ids[i]) for i in order if allowed is None or int(self.ids[i]) in allowed]
        return ranked[:CANDIDATES]

    def _keyword(self, query: str, allowed: set[int] | None, types: tuple[str, ...] = KINDS) -> list[int]:
        words = re.findall(r"\w+", query, flags=re.UNICODE)
        if not words:
            return []
        expression = " OR ".join(f'"{word}"' for word in words)
        marks = ", ".join("?" for _ in types)
        rows = self.db.execute(
            "SELECT chunks_fts.rowid AS rowid, bm25(chunks_fts) AS score FROM chunks_fts "
            "JOIN chunks ON chunks.id = chunks_fts.rowid "
            f"WHERE chunks_fts MATCH ? AND chunks.kind IN ({marks}) ORDER BY bm25(chunks_fts) LIMIT ?",
            (expression, *types, CANDIDATES * 4),
        ).fetchall()
        today = dt.date.today()
        # equal relevance (to 3 decimals): the most recent watch article first
        rows = sorted(rows, key=lambda row: (round(row["score"], 3), -self._freshness(row["rowid"], today)))
        ranked = [row["rowid"] for row in rows if allowed is None or row["rowid"] in allowed]
        return ranked[:CANDIDATES]

    def _since_filter(self, since: str, allowed: set[int] | None) -> set[int]:
        """Passages of documents published on or after `since`. Undated documents (books) are kept:
        the filter only drops articles that are too old."""
        base = allowed if allowed is not None else set(self.chunk_info)
        return {cid for cid in base if not self.chunk_info.get(cid, (set(), ""))[1]
                or self.chunk_info[cid][1] >= since}

    def _freshness(self, chunk_id: int, today: dt.date) -> float:
        neutral = FRESHNESS_BONUS * 0.5
        collections, published = self.chunk_info.get(chunk_id, (set(), ""))
        if not published or not (collections & FRESHNESS_COLLECTIONS) or OWN_COLLECTION in collections:
            return neutral
        try:
            age = max(0, (today - dt.date.fromisoformat(published)).days)
        except ValueError:
            return neutral
        return FRESHNESS_BONUS * 0.5 ** (age / FRESHNESS_HALF_LIFE)

    def search(self, query: str, collections: list[str] | None, limit: int,
               since: str | None = None, types: list[str] | None = None, component: str = "hybrid") -> list[dict]:
        """Hybrid search. `types` ("texte", "figure") restricts the kind of passage: running text only by default;
        a figure passage is a caption (and useful alternative text) with a `ref` that carries the path of the
        image as plain text. `component` ("vector", "text") keeps one of the two rankings only: used by the parity
        tool (tools/library_parity.py) to measure each way separately; the MCP tools never pass it."""
        kinds = self.check_types(types)
        self.refresh()
        allowed = self._collection_filter(collections)
        if since:
            allowed = self._since_filter(since, allowed)
        allowed = self._type_filter(kinds, allowed)
        fused: dict[int, float] = {}
        if component not in ("hybrid", "vector", "text"):
            raise ValueError(f"Unknown component: {component!r}. Known: hybrid, vector, text")
        rankings = ((self._semantic(query, allowed) if component in ("hybrid", "vector") else []),
                    (self._keyword(query, allowed, kinds) if component in ("hybrid", "text") else []))
        for ranking in rankings:
            for rank, chunk_id in enumerate(ranking):
                fused[chunk_id] = fused.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank + 1)
        today = dt.date.today()
        for chunk_id in fused:
            fused[chunk_id] += self._freshness(chunk_id, today)
        best = sorted(fused, key=fused.get, reverse=True)[:limit]
        return [self._describe(chunk_id, score=round(fused[chunk_id], 4)) for chunk_id in best]

    def _describe(self, chunk_id: int, **extra) -> dict:
        row = self.db.execute(
            "SELECT c.id, c.position, c.section, c.text, c.kind, c.ref, b.title, b.file_name, b.collections, b.meta "
            "FROM chunks c JOIN books b ON b.id = c.book_id WHERE c.id = ?",
            (chunk_id,),
        ).fetchone()
        described = {
            "passage_id": row["id"],
            "book": row["title"],
            **json.loads(row["meta"] or "{}"),  # url, author, published: watch and personal-collection articles
            "file": row["file_name"],
            "section": row["section"],
            "position": row["position"],
            "collections": sorted(set(row["collections"].split("|"))),
            "kind": row["kind"],
            **extra,
            "text": row["text"],
        }
        if row["kind"] == "figure":  # id, label, page, section, image: the image path is only text
            described["ref"] = json.loads(row["ref"] or "{}")
        return described

    def read(self, passage_id: int, before: int, after: int) -> dict:
        anchor = self.db.execute("SELECT book_id, position FROM chunks WHERE id = ?", (passage_id,)).fetchone()
        if anchor is None:
            return {"error": f"Unknown passage_id {passage_id}. Use an id returned by search_library."}
        rows = self.db.execute(
            "SELECT id FROM chunks WHERE book_id = ? AND position BETWEEN ? AND ? ORDER BY position",
            (anchor["book_id"], anchor["position"] - before, anchor["position"] + after),
        ).fetchall()
        passages = [self._describe(row["id"]) for row in rows]
        return {
            "book": passages[0]["book"],
            **{k: passages[0][k] for k in META_FIELDS if k in passages[0]},
            "file": passages[0]["file"],
            "passages": [{k: p[k] for k in ("passage_id", "kind", "section", "position", "ref", "text") if k in p}
                         for p in passages],
        }

    def collections(self) -> dict[str, int]:
        self.refresh()
        counts: dict[str, int] = {}
        for (names,) in self.db.execute("SELECT collections FROM books"):
            for name in set(names.split("|")):   # a book counts once per collection name
                counts[name] = counts.get(name, 0) + 1
        return dict(sorted(counts.items()))

    def books(self, collection: str | None) -> list[dict]:
        rows = self.db.execute(
            "SELECT b.title, b.file_name, b.collections, COUNT(c.id) AS passages, "
            "COALESCE(SUM(c.kind = 'figure'), 0) AS figures "
            "FROM books b LEFT JOIN chunks c ON c.book_id = b.id GROUP BY b.id ORDER BY b.title"
        ).fetchall()
        return [
            {"book": r["title"], "file": r["file_name"],
             "collections": sorted(set(r["collections"].split("|"))),
             "passages": r["passages"], "figures": r["figures"]}
            for r in rows
            if not collection or collection in set(r["collections"].split("|"))
        ]


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------

BACKENDS = ("sqlite", "postgres")


def choose_backend(option: str | None = None) -> str:
    """Backend of `serve`: the option, else PMZILLA_LAB_BACKEND, else postgres (SQLite stays available with --backend sqlite). Anything else stops with a message."""
    backend = option or os.environ.get("PMZILLA_LAB_BACKEND") or "postgres"
    if backend not in BACKENDS:
        raise SystemExit(f"Unknown backend '{backend}'. Known: {', '.join(BACKENDS)}.")
    return backend


def open_library(backend: str):
    """The library object of a backend; postgres never falls back on sqlite when the database does not answer."""
    if backend == "postgres":
        import knowledge_library
        return knowledge_library.PostgresLibrary()
    return Library()


def make_cases_reader():
    """The cases reader of the server (design.md 4 of db-lot2): no connection until its first call. Module-level so that tests patch it."""
    import cases_store
    return cases_store.CasesReader()


def serve(backend: str | None = None) -> None:
    from mcp.server.fastmcp import FastMCP

    backend = choose_backend(backend)
    library = open_library(backend)
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
        if collections:
            refused = unknown_collections_error(collections)
            if refused:
                return refused
        if since:
            try:
                dt.date.fromisoformat(since)
            except ValueError:
                return {"error": f"since must be a date YYYY-MM-DD, got {since!r}"}
        try:
            found = library.search(query, collections, max(1, min(limit, 20)), since, types)
            return found
        except ValueError as error:
            return {"error": str(error)}

    @server.tool()
    def read_passage(passage_id: int, before: int = 1, after: int = 2) -> dict:
        """Read a passage returned by search_library together with the passages around it in the
        same book (before/after: how many neighbouring passages, up to 5 each). Use it when a
        result is central and you need the full argument, not only the excerpt. Each passage has a
        `kind` ("texte" or "figure"); a figure passage also has its `ref`."""
        return library.read(passage_id, max(0, min(before, 5)), max(0, min(after, 5)))

    @server.tool()
    def list_collections() -> dict[str, int | str]:
        """List the collections of the library with their number of books."""
        return dict(library.collections())

    @server.tool()
    def list_books(collection: str | None = None) -> list[dict]:
        """List the books in the library with their collections and size. Use it to know what the
        library covers or to pick a collection to search in. An unknown collection name, including the
        former name "veille" (use "watch"), returns an error object."""
        refused = unknown_collections_error([collection]) if collection else None
        if refused:
            return [refused]
        return library.books(collection)

    cases: list = []   # the cases reader, created at the first cases call: the library tools never depend on it

    def cases_answer(call, query: str | None = None):
        """Runs `call(reader)`; every refusal is an error object, never a stop of the server."""
        import cases_store
        if backend != "postgres":
            return {"error": "the cases module requires the PostgreSQL backend"}
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


def main() -> None:
    import flux_config
    sys.argv[1:] = flux_config.refuse_old_options(sys.argv[1:], {"--recalculer": "--recompute"})
    if len(sys.argv) >= 3 and sys.argv[1] == "index":
        args = sys.argv[2:]
        force = None
        if "--recompute" in args:
            position = args.index("--recompute")
            args, force = args[:position], args[position + 1:]
            if not force:
                sys.exit("--recompute needs at least one book (or @list.txt).")
        if not args:
            sys.exit("index needs at least one collections folder before --recompute.")
        index([Path(arg) for arg in args], force)
    elif len(sys.argv) in (4, 5) and sys.argv[1] == "rename-collection":
        extra = sys.argv[4:]
        if extra not in ([], ["--dry-run"]):
            sys.exit("Usage: rename-collection <old> <new> [--dry-run]")
        rename_collection(sys.argv[2], sys.argv[3], bool(extra))
    elif len(sys.argv) >= 2 and sys.argv[1] == "serve":
        extra = sys.argv[2:]
        if extra and not (len(extra) == 2 and extra[0] == "--backend"):
            sys.exit("Usage: serve [--backend sqlite|postgres]")
        serve(extra[1] if extra else None)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
