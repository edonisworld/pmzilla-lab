# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "psycopg[binary]"]
# ///
"""
PMZilla Lab : usage des livres par les postures (R-52).

Quels livres les postures reçoivent, lisent et citent vraiment, lesquels ne servent jamais, et combien de fois chaque posture écrit
« hors bibliothèque ». Comptes agrégés seulement : jamais un texte, une requête, un identifiant de passage ni un nom.

    uv run tools/book_usage.py collect [--delay SECONDES]
    uv run tools/book_usage.py report [--since AAAA-MM-JJ] [--until AAAA-MM-JJ]

collect : lit les transcriptions des séances Claude Code du dossier de projet du workspace (le serveur de la bibliothèque n'écrit
    aucune trace de ses appels) et ajoute au registre local, pour chaque tour terminé qui n'y est pas encore, un enregistrement
    agrégé : jour, compartiment de posture, comptes par livre (passages renvoyés, lus, cité ou non), nombre de formules « hors
    bibliothèque ». Un tour déjà compté ne l'est jamais deux fois ; une transcription modifiée depuis moins de --delay secondes
    (600 par défaut) est laissée à un passage suivant. Les transcriptions ne sont ni copiées ni modifiées.
report : lit le registre et la liste des livres de la base de la bibliothèque (rôle de lecture seule, délai de connexion de 2 s) et écrit
    un rapport Markdown en français dans _bmad-output/pmzilla/usage-livres/usage-livres-AAAA-MM-JJ.md (dossier ignoré par Git).

Lu : les transcriptions du dossier de projet configuré, le registre, la base (livres, titres de catalogue, collections).
Écrit : le registre ~/.pmzilla-lab/usage-livres/registre.jsonl (droits du propriétaire seul) et le rapport. Jamais : les dossiers de
livres, d'images, de veille, la mémoire des agents, le réseau, une écriture en base.

Seul l'utilisateur lance cet outil, dans le Terminal : les transcriptions contiennent toutes les conversations (règle `deny` de
.claude/settings.json, design.md D8). Codes de sortie : 0 fait, 1 erreur d'usage (option inconnue, date invalide, début après fin),
2 source inutilisable (dossier des transcriptions, registre ou base).

Variables d'environnement (pour les tests) : PMZILLA_LAB_WORKSPACE, PMZILLA_LAB_DATA, PMZILLA_LAB_TRANSCRIPTS (dossiers de projet,
séparés par « : » ; par défaut ~/.claude/projects/<workspace>), PMZILLA_LAB_KNOWLEDGE_DBNAME (comme le tableau de bord).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import book_usage_transcripts as transcripts
import watch_paths

import yaml

REPO = Path(__file__).resolve().parents[1]
VOCABULARY_FILE = REPO / "tests" / "postures" / "vocabulaire.yaml"
RECORD_VERSION = 1
KNOWLEDGE_ROLE = "pmzilla_knowledge_ro"
KNOWLEDGE_TIMEOUT_SECONDS = 2
DEFAULT_DELAY_SECONDS = 600
POSTURES = ("Discovery", "Delivery", "Scaling", "Facilitation")
# Domaines de la bibliothèque (collections) de chaque posture : la table des postures de CLAUDE.md (un test les compare).
DOMAINS = {"Discovery": ("produit",), "Delivery": ("flow", "tech"), "Scaling": ("organisation", "flow"), "Facilitation": ("facilitation",)}
MULTIPLE, NONE, CRITIC = "plusieurs postures", "sans posture", "Critic"
BUCKET_ORDER = (*POSTURES, MULTIPLE, NONE, CRITIC)
EXCLUDED_COLLECTIONS = {watch_paths.NEW["collection"], watch_paths.OLD["collection"], watch_paths.OWN_COLLECTION}
# Formules de bascule de CLAUDE.md (« [Switch to Scaling] », « [Bascule vers Scaling] ») : les noms de posture qui les suivent comptent.
SWITCH_PATTERNS = (r"\[\s*Switch to\s+([^\]]+?)\s*\]", r"\[\s*Bascule vers\s+([^\]]+?)\s*\]")
DATE_FORMAT = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_vocabulary: dict = {}


class LedgerError(Exception):
    """Registre illisible : porte le seul type de l'erreur d'origine."""


def vocabulary() -> dict:
    if not _vocabulary:
        _vocabulary.update(yaml.safe_load(VOCABULARY_FILE.read_text(encoding="utf-8")) or {})
    return _vocabulary


# ---------------------------------------------------------------------------
# Emplacements
# ---------------------------------------------------------------------------

def workspace() -> Path:
    return Path(os.environ.get("PMZILLA_LAB_WORKSPACE") or "~/PMZilla-Lab/workspace").expanduser()


def data_dir() -> Path:
    return Path(os.environ.get("PMZILLA_LAB_DATA") or "~/.pmzilla-lab").expanduser()


def ledger_path() -> Path:
    return data_dir() / "usage-livres" / "registre.jsonl"


def report_dir() -> Path:
    return workspace() / "_bmad-output" / "pmzilla" / "usage-livres"


def project_folders() -> list[Path]:
    """Dossiers de projet à lire (configurés) ; par défaut le seul workspace : ~/.claude/projects/<chemin aux caractères non alphanumériques en « - »>."""
    configured = os.environ.get("PMZILLA_LAB_TRANSCRIPTS")
    if configured:
        return [Path(p).expanduser() for p in configured.split(os.pathsep) if p]
    return [Path("~/.claude/projects").expanduser() / re.sub(r"[^A-Za-z0-9]", "-", str(workspace()))]


# ---------------------------------------------------------------------------
# Registre
# ---------------------------------------------------------------------------

def read_ledger() -> list[dict]:
    path = ledger_path()
    if not path.exists():
        return []
    records = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                if not isinstance(record, dict) or not isinstance(record.get("turn"), str):
                    raise ValueError("record")
                records.append(record)
    except (OSError, ValueError) as error:       # UnicodeDecodeError et JSONDecodeError sont des ValueError
        raise LedgerError(type(error).__name__) from None
    return records


def append_ledger(records: list[dict]) -> None:
    if not records:
        return
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    payload = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records).encode("utf-8")
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        os.write(descriptor, payload)
    finally:
        os.close(descriptor)


def turn_key(session: str, index: int, suffix: str = "") -> str:
    """Clé à sens unique d'un tour : SHA-256 de la séance et du rang du tour (l'identifiant de séance n'est jamais écrit)."""
    return hashlib.sha256(f"{session}:{index}{suffix}".encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Comptes d'un tour
# ---------------------------------------------------------------------------

def normalise(text: str) -> str:
    stripped = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", stripped.lower()).split())


def postures_named(text: str) -> list[str]:
    """Postures (hors Critic) annoncées par une balise ou une bascule, noms exacts, sans doublon."""
    vocab = vocabulary()
    exact = set(vocab["posture_names"]) - {CRITIC}
    found: list[str] = []
    patterns = [vocab[language]["posture_tag_pattern"] for language in ("fr", "en")] + list(SWITCH_PATTERNS)
    for pattern in patterns:
        for name in re.findall(pattern, text, re.IGNORECASE):
            name = name.strip()
            if name in exact and name not in found:
                found.append(name)
    return found


def bucket_of(text: str) -> str:
    named = postures_named(text)
    return named[0] if len(named) == 1 else MULTIPLE if named else NONE


def outside_count(text: str) -> int:
    vocab = vocabulary()
    return sum(len(re.findall(vocab[language]["out_of_library_pattern"], text, re.IGNORECASE)) for language in ("fr", "en"))


def names_book(title: str, text: str) -> bool:
    """Le texte nomme le livre : titre du catalogue, ou sa partie avant les deux-points, sans casse ni accents."""
    haystack = f" {normalise(text)} "
    candidates = {normalise(title), normalise(title.split(":")[0])} - {""}
    return any(f" {c} " in haystack for c in candidates)


def count_books(calls: list, answer: str) -> dict:
    """{fichier : {returned, read, cited}} des appels d'un compartiment ; livres seulement (articles écartés, jamais notés)."""
    articles = set()
    for call in calls:
        for item in call.results:
            if isinstance(item.get("file"), str) and ("url" in item or EXCLUDED_COLLECTIONS & set(item.get("collections") or [])):
                articles.add(item["file"])
    stats: dict[str, dict] = {}
    titles: dict[str, str] = {}
    for call in calls:
        for item in call.results:
            name = item.get("file")
            if not isinstance(name, str) or name in articles:
                continue
            entry = stats.setdefault(name, {"returned": 0, "read": 0, "cited": 0})
            entry["returned" if call.name == transcripts.SEARCH_TOOL else "read"] += 1
            if isinstance(item.get("book"), str):
                titles[name] = item["book"]
    for name, entry in stats.items():
        if titles.get(name) and names_book(titles[name], answer):
            entry["cited"] = 1
    return stats


def day_of(turn) -> str | None:
    return turn.day if DATE_FORMAT.match(turn.day or "") else None


def turn_records(turn) -> list[dict]:
    """Enregistrements d'un tour : celui du compartiment de posture, et celui de Critic quand son sous-agent a travaillé."""
    text = "\n".join(turn.main_texts)
    records = [{"turn": turn_key(turn.session, turn.index), "day": turn.day, "bucket": bucket_of(text),
                "books": count_books(turn.main_calls, text), "outside_library": outside_count(text), "version": RECORD_VERSION}]
    if turn.critic_active and (turn.side_calls or any(t.strip() for t in turn.side_texts)):
        final = next((t for t in reversed(turn.side_texts) if t.strip()), "")
        records.append({"turn": turn_key(turn.session, turn.index, ":critic"), "day": turn.day, "bucket": CRITIC,
                        "books": count_books(turn.side_calls, final), "outside_library": outside_count(final), "version": RECORD_VERSION})
    return records


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------

def read_sessions(folders: list[Path], now: float, delay: float) -> tuple[dict, int, int]:
    """({séance : enregistrements}, fichiers lus, éléments illisibles). Fichier trop récent : laissé pour un passage suivant."""
    sessions: dict[str, list] = {}
    read = unreadable = 0
    for folder in folders:
        for path in sorted(folder.rglob("*.jsonl")):
            try:
                if now - path.stat().st_mtime < delay:
                    continue
                records = []
                with open(path, encoding="utf-8") as stream:
                    for line in stream:
                        if not line.strip():
                            continue
                        try:
                            record = transcripts.normalise(json.loads(line), path.stem)
                        except ValueError:
                            unreadable += 1
                            continue
                        if record is not None:
                            records.append(record)
            except (OSError, UnicodeDecodeError):
                unreadable += 1
                continue
            read += 1
            for record in records:
                sessions.setdefault(record.session, []).append(record)
    return sessions, read, unreadable


def collect(delay: float, now: float) -> int:
    folders = [f for f in project_folders() if f.is_dir()]
    if not folders:
        print("Dossier des transcriptions introuvable")
        return 2
    try:
        known = {r["turn"] for r in read_ledger()}
    except LedgerError as error:
        print(f"Registre illisible ({error})")
        return 2
    sessions, files_read, unreadable = read_sessions(folders, now, delay)
    added: list[dict] = []
    turns_added = already = 0
    for session in sorted(sessions):
        for turn in transcripts.turns_of(sessions[session]):
            if not turn.complete:
                continue
            if day_of(turn) is None:
                unreadable += 1
                continue
            records = turn_records(turn)
            if records[0]["turn"] in known:
                already += 1
            else:
                turns_added += 1
            for record in records:
                if record["turn"] not in known:
                    known.add(record["turn"])
                    added.append(record)
    append_ledger(added)
    print(f"Transcriptions lues : {files_read}, tours ajoutés : {turns_added}, déjà comptés : {already}, illisibles : {unreadable}")
    return 0


# ---------------------------------------------------------------------------
# Liste des livres
# ---------------------------------------------------------------------------

LIBRARY_SQL = ("SELECT b.title, b.file_name, ARRAY(SELECT co.name FROM knowledge.book_collections bc "
               "JOIN knowledge.collections co ON co.id = bc.collection_id WHERE bc.book_id = b.id) FROM knowledge.books b ORDER BY b.title")


def connect_knowledge():
    """Connexion réelle : rôle de lecture seule, délai court ; base nommée par PMZILLA_LAB_KNOWLEDGE_DBNAME si elle est posée."""
    import db
    return db.connect(role=KNOWLEDGE_ROLE, timeout=KNOWLEDGE_TIMEOUT_SECONDS, dbname=os.environ.get("PMZILLA_LAB_KNOWLEDGE_DBNAME") or None)


def fetch_books(connect=None) -> list[dict]:
    """Livres de la bibliothèque (veille et collection personnelle exclues par nom exact) : {title, file, collections}.
    Lève si la base ne répond pas ; `connect` est injectable (tests) ; la connexion est toujours fermée."""
    conn = (connect or connect_knowledge)()
    try:
        rows = conn.execute(LIBRARY_SQL).fetchall()
    finally:
        conn.close()
    return [{"title": title, "file": file, "collections": list(names or [])}
            for title, file, names in rows if not EXCLUDED_COLLECTIONS & set(names or [])]


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def cell(value) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def table(headers: list[str], rows: list[list]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(cell(c) for c in row) + " |" for row in rows]
    return lines


def aggregate(records: list[dict], books: dict[str, dict]) -> tuple[dict, dict, dict]:
    """(par livre, par compartiment, livres cités par compartiment), sur les livres de la bibliothèque seulement."""
    per_book = {f: {"returned": 0, "read": 0, "cited": 0, "turns": 0} for f in books}
    per_bucket: dict[str, dict] = {}
    cited_by: dict[str, set] = {}
    for record in records:
        bucket = record.get("bucket", NONE)
        entry = per_bucket.setdefault(bucket, {"turns": 0, "returned": 0, "read": 0, "cited": 0, "outside": 0, "outside_turns": 0})
        entry["turns"] += 1
        outside = int(record.get("outside_library") or 0)
        entry["outside"] += outside
        entry["outside_turns"] += 1 if outside else 0
        for name, counts in (record.get("books") or {}).items():
            if name not in per_book:
                continue
            for key in ("returned", "read", "cited"):
                per_book[name][key] += int(counts.get(key) or 0)
                entry[key] += int(counts.get(key) or 0)
            per_book[name]["turns"] += 1
            if counts.get("cited"):
                cited_by.setdefault(bucket, set()).add(name)
    return per_book, per_bucket, cited_by


def build_report(records: list[dict], first_day: str | None, books_list: list[dict], since: str | None, until: str | None) -> str:
    books = {b["file"]: b for b in books_list}
    in_period = [r for r in records if (not since or r.get("day", "") >= since) and (not until or r.get("day", "") <= until)]
    per_book, per_bucket, cited_by = aggregate(in_period, books)
    days = sorted(r.get("day", "") for r in in_period)
    start = since or (days[0] if days else "aucune date")
    end = until or (days[-1] if days else "aucune date")
    posture_turns = sum(1 for r in in_period if r.get("bucket") != CRITIC)
    lines = ["# Usage des livres par les postures", "", f"Période : {start} à {end}, {posture_turns} tours de posture",
             f"Données disponibles depuis le {first_day or 'aucune donnée'}", ""]
    if not in_period:
        lines += ["Aucun tour de posture dans la période", ""]
    title = lambda f: books[f]["title"]
    colls = lambda f: ", ".join(books[f]["collections"])

    lines += ["## Par livre", ""]
    used = sorted((f for f, c in per_book.items() if c["returned"] or c["read"] or c["cited"]),
                  key=lambda f: (-per_book[f]["cited"], -per_book[f]["read"], title(f)))
    lines += table(["Titre", "Fichier", "Collections", "Passages renvoyés", "Passages lus", "Citations", "Tours"],
                   [[title(f), f, colls(f), per_book[f]["returned"], per_book[f]["read"], per_book[f]["cited"], per_book[f]["turns"]] for f in used])

    lines += ["", "## Par posture", ""]
    buckets = [b for b in BUCKET_ORDER if b in per_bucket] + sorted(set(per_bucket) - set(BUCKET_ORDER))
    lines += table(["Compartiment", "Tours", "Passages renvoyés", "Passages lus", "Citations", "Livres cités", "Formules hors bibliothèque"],
                   [[b, per_bucket[b]["turns"], per_bucket[b]["returned"], per_bucket[b]["read"], per_bucket[b]["cited"],
                     len(cited_by.get(b, ())), per_bucket[b]["outside"]] for b in buckets])

    lines += ["", "## Livres jamais cités", ""]
    never_cited = sorted((f for f in books if not per_book[f]["cited"]), key=title)
    lines += table(["Titre", "Fichier", "Collections", "Passages lus"], [[title(f), f, colls(f), per_book[f]["read"]] for f in never_cited])

    lines += ["", "## Livres jamais lus ni cités", ""]
    never_used = sorted((f for f in books if not per_book[f]["read"] and not per_book[f]["cited"]), key=title)
    lines += table(["Titre", "Fichier", "Collections", "Passages renvoyés"], [[title(f), f, colls(f), per_book[f]["returned"]] for f in never_used])

    lines += ["", "## Livres du domaine jamais cités, par posture", ""]
    for posture in POSTURES:
        domain = set(DOMAINS[posture])
        missing = sorted((f for f in books if domain & set(books[f]["collections"]) and f not in cited_by.get(posture, ())), key=title)
        lines += [f"### {posture}", "", f"Domaines : {', '.join(DOMAINS[posture])}", ""]
        lines += [f"- {title(f)} ({f})" for f in missing] if missing else ["Tous les livres du domaine ont été cités."]
        lines.append("")

    lines += ["## Lacunes par posture", ""]
    lines += table(["Compartiment", "Tours avec la formule", "Formules"], [[b, per_bucket[b]["outside_turns"], per_bucket[b]["outside"]] for b in buckets])
    return "\n".join(lines) + "\n"


def valid_date(value: str) -> bool:
    if not DATE_FORMAT.match(value):
        return False
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def report(since: str | None, until: str | None, now: float, read_books=None) -> int:
    for value in (since, until):
        if value is not None and not valid_date(value):
            print(f"Date invalide : {value}")
            return 1
    if since and until and since > until:
        print("Période vide : début après fin")
        return 1
    try:
        records = read_ledger()
    except LedgerError as error:
        print(f"Registre illisible ({error})")
        return 2
    try:
        books = (read_books or fetch_books)()
    except Exception as error:      # le type seul : le message pourrait porter un chemin ou un extrait
        print(f"Bibliothèque injoignable ({type(error).__name__})")
        return 2
    first_day = min((r.get("day", "") for r in records), default=None) or None
    text = build_report(records, first_day, books, since, until)
    folder = report_dir()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"usage-livres-{dt.date.fromtimestamp(now).isoformat()}.md"
    temporary = target.with_suffix(".md.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, target)
    print(f"Rapport écrit : {target}")
    return 0


# ---------------------------------------------------------------------------
# Ligne de commande
# ---------------------------------------------------------------------------

class Parser(argparse.ArgumentParser):
    def error(self, message):       # erreur d'usage : code 1 (argparse sortirait avec 2, réservé aux sources inutilisables)
        self.print_usage(sys.stderr)
        sys.stderr.write(f"{self.prog} : option ou argument invalide\n")
        raise SystemExit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = Parser(prog="book_usage.py", description="Usage des livres par les postures : comptes agrégés (R-52).")
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("collect", help="ajoute au registre les tours terminés des transcriptions du workspace")
    one.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS, help="secondes sans modification avant de lire une transcription (600)")
    two = sub.add_parser("report", help="écrit le rapport d'usage en Markdown")
    two.add_argument("--since", help="premier jour compté (AAAA-MM-JJ)")
    two.add_argument("--until", help="dernier jour compté (AAAA-MM-JJ)")
    return parser


def main(argv=None, now: float | None = None, read_books=None) -> int:
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as stop:
        return int(stop.code or 0)
    moment = time.time() if now is None else now
    if args.command == "collect":
        return collect(args.delay, moment)
    return report(args.since, args.until, moment, read_books)


if __name__ == "__main__":
    sys.exit(main())
