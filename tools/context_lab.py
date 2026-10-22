#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""PMZilla Lab : l'outil des notes de contexte de l'organisation (change organisation-context, design D1, D2, D7, D9).

Le dossier de contexte vit hors de tout arbre Git (par défaut le dossier `contexte` du dossier du lab, variable PMZILLA_LAB_CONTEXT,
résolu par tools/lab_paths.py seulement). Il porte deux sous-dossiers réservés à leur propriétaire (mode 700, fichiers 600) :
`originaux/`, que seul l'utilisateur ouvre (cet outil n'y liste, n'y ouvre, n'y teste aucun chemin), et `notes/`, les notes distillées
(Markdown, une par fichier, à plat), la seule partie que le système lit, par la bibliothèque.

    uv run tools/context_lab.py init [--yes]        crée les deux sous-dossiers, après confirmation
    uv run tools/context_lab.py add                 lit un brouillon de note (en-tête et corps) sur l'entrée standard, le contrôle, l'écrit
    uv run tools/context_lab.py check               contrôle chaque note (en-tête, confidentialité, une seule carte)
    uv run tools/context_lab.py list                les mêmes lignes, sans le contrôle de confidentialité
    uv run tools/context_lab.py review <fichier> <AAAA-MM-JJ>   remplace la date de revue d'une note, rien d'autre

En-tête de chaque note (front matter YAML, clés en anglais) : title, date, nature (declarative ou measured), source, review (postérieure
à date) et, pour la carte seulement, kind: map. Nom du fichier : AAAA-MM-JJ-<slug>.md, ou carte-contexte.md pour la carte.

Contrôle de confidentialité (add, check, review, l'indexeur et le réveil des postures) : le détecteur d'identifiants personnels, la liste
des noms sensibles et les noms distinctifs de l'extrait des noms d'équipes voisin de la liste, lu en local, moins la liste des noms
génériques (change context-index-name-guard, D4), appariés comme le fait le hook pre-commit (tools/sensitive_names.py). Une correspondance
refuse la note avec « personal identifier in line <n> », « sensitive name in line <n> » ou « extract team name in line <n> » : le numéro de
ligne seulement, jamais la valeur. La liste reste exigée : vide, elle est indisponible même avec un extrait. Aucune sous-commande n'écrit
une ligne du corps d'une note. Au réveil, la carte n'est imprimée qu'après ce contrôle ; sinon « context map not shown: <raison> » (D5).

Codes de sortie : 0 fait (check : aucune note invalide ; une note à revoir n'est pas une erreur) ; 1 check : au moins une note invalide ;
2 usage, dossier de contexte dans un arbre Git ou dans l'espace de travail, ancien dossier encore présent ; 3 en-tête invalide ;
4 la note existe ; 5 identifiant personnel ou nom sensible dans la note ; 6 dossier de contexte introuvable, liste des noms sensibles
indisponible ; 78 chemins du lab introuvables. Messages en anglais, préfixés « context_lab: ».
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_paths  # noqa: E402
import sensitive_names  # noqa: E402

PREFIX = "context_lab: "
MAP_NAME = "carte-contexte.md"
MAP_LINE_CAP = 80                      # lignes du corps de la carte imprimées au réveil des postures (design D9)
NATURES = ("declarative", "measured")
REQUIRED = ("title", "date", "nature", "source", "review")
FRONT_MATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)
DATE_FORM = re.compile(r"\A\d{4}-\d{2}-\d{2}\Z")
# L'ancien dossier du lab (design D16) : écrit en deux morceaux, aucun fichier de tools/ ne le porte en littéral.
FORMER_FOLDER = "Contexte" + "-Lab"

EXIT_OK, EXIT_INVALID_NOTE, EXIT_USAGE, EXIT_HEADER, EXIT_EXISTS, EXIT_PRIVATE, EXIT_MISSING = 0, 1, 2, 3, 4, 5, 6


class Refusal(Exception):
    """Un refus : message (sans le préfixe) et code de sortie."""

    def __init__(self, message: str, code: int):
        super().__init__(message)
        self.message, self.code = message, code


# -- en-tête ------------------------------------------------------------------------------------------------------------------------

def parse_header(text: str) -> tuple[dict | None, str]:
    """(champs, corps) d'une note ; champs None sans front matter. Lecture « clé: valeur » ligne à ligne, guillemets retirés."""
    match = FRONT_MATTER.match(text)
    if not match:
        return None, text
    fields: dict = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        key = key.strip()
        if sep and key and not line.startswith((" ", "\t", "#")):
            value = re.sub(r"\s+#.*$", "", value).strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1].strip()
            fields.setdefault(key, value)
    return fields, text[match.end():]


def _valid_date(value: str) -> dt.date | None:
    if not DATE_FORM.match(value):
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def header_problem(fields: dict | None) -> str | None:
    """La première règle de D2 enfreinte (sa phrase clé), ou None. L'ordre est celui du design."""
    if fields is None:
        return "header missing"
    for name in REQUIRED:
        if not fields.get(name):
            return f"header field missing: {name}"
    for name in ("date", "review"):
        if _valid_date(fields[name]) is None:
            return f"header field not a date: {name}"
    if fields["nature"] not in NATURES:
        return "nature must be declarative or measured"
    if _valid_date(fields["review"]) <= _valid_date(fields["date"]):
        return "review date must be after the note date"
    if "kind" in fields and fields["kind"] != "map":
        return "kind must be map"
    return None


def slug(title: str) -> str:
    text = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "note"


def file_name_for(fields: dict) -> str:
    return MAP_NAME if fields.get("kind") == "map" else f"{fields['date']}-{slug(fields['title'])}.md"


# -- confidentialité ----------------------------------------------------------------------------------------------------------------

def confidentiality_problem(text: str, patterns: list, identifiers: list[str], extract_patterns: list = ()) -> str | None:
    """« personal identifier in line n », « sensitive name in line n » ou « extract team name in line n » pour la première ligne qui
    correspond ; jamais la valeur."""
    for number, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        if any(identifier in low for identifier in identifiers):
            return f"personal identifier in line {number}"
        if sensitive_names.line_matches(patterns, line):
            return f"sensitive name in line {number}"
        if sensitive_names.line_matches(extract_patterns, line):
            return f"extract team name in line {number}"
    return None


class Guard:
    """Les moyens du contrôle de confidentialité : motifs des noms sensibles (liste lue en place), motifs des noms distinctifs de l'extrait
    des noms d'équipes voisin de la liste (lu en local, moins la liste des noms génériques ; change context-index-name-guard, D4) et
    identifiants personnels. La liste reste exigée : absente, illisible ou vide, la garde est indisponible, même avec un extrait.

    `list_path` remplace le chemin de la liste (l'indexeur le résout depuis le dossier de code) ; None avec `content_root` None : liste
    absente. `code_root` : le dossier de code dont les identifiants personnels sont lus (par défaut celui de ce module)."""

    def __init__(self, env, content_root: Path | None, identifiers=None, list_path: Path | None = None, code_root: Path | None = None):
        self.env, self.content_root, self.injected, self.code_root = env, content_root, identifiers, code_root
        self.patterns: list | None = None
        self.extract_patterns: list = []
        self.unavailable = False
        self._identifiers: list[str] | None = None
        path = list_path
        if path is None and content_root is not None:
            path = lab_paths.local_file("sensitive_names", content_root, env)
        if path is None:
            self.unavailable = True
            return
        try:
            self.patterns = sensitive_names.patterns(sensitive_names.load_names(path))
        except sensitive_names.SensitiveNamesUnavailable:
            self.unavailable = True
            return
        self.extract_patterns = sensitive_names.patterns(sensitive_names.extract_names(Path(path).parent / sensitive_names.NOM_EXTRAIT))

    def identifiers(self) -> list[str]:
        if self.injected is not None:
            return [i.lower() for i in self.injected if i]
        if self._identifiers is None:
            import identifiants_personnels
            self._identifiers = identifiants_personnels.identifiants(self.code_root or lab_paths.code_root())
        return self._identifiers

    def problem(self, text: str) -> str | None:
        return confidentiality_problem(text, self.patterns or [], self.identifiers(), self.extract_patterns)


# -- dossier -------------------------------------------------------------------------------------------------------------------------

def today_paris(env=None) -> dt.date:
    """La date du jour à Paris ; PMZILLA_LAB_TODAY (AAAA-MM-JJ) la remplace, pour les tests."""
    env = os.environ if env is None else env
    forced = _valid_date(env.get("PMZILLA_LAB_TODAY", ""))
    if forced:
        return forced
    from zoneinfo import ZoneInfo
    return dt.datetime.now(ZoneInfo("Europe/Paris")).date()


def _inside_git_work_tree(folder: Path) -> bool:
    probe = folder
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        done = subprocess.run(["git", "-C", str(probe), "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True,
                              timeout=5, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0 and done.stdout.strip() == "true"


def locate(env) -> tuple[Path, dict]:
    """(dossier de contexte, dossiers du lab) après les refus communs à toute sous-commande (design D1, D16)."""
    folders = lab_paths.resolve_or_exit(env)
    folder = folders["context_folder"]
    if os.path.lexists(folders["lab_folder"] / FORMER_FOLDER):
        raise Refusal("former context folder still present: finish the move", EXIT_USAGE)
    under = [folders["content_root"], folders["code_root"]]
    resolved = Path(os.path.abspath(folder))
    if _inside_git_work_tree(folder) or any(resolved == r or r in resolved.parents for r in map(Path, under)):
        raise Refusal("context folder inside a Git work tree, refused", EXIT_USAGE)
    return folder, folders


def notes_folder(folder: Path) -> Path:
    return folder / "notes"


def require_notes(folder: Path) -> Path:
    notes = notes_folder(folder)
    if not folder.is_dir() or not notes.is_dir():
        raise Refusal("context folder not found: run init", EXIT_MISSING)
    return notes


def note_files(notes: Path) -> list[Path]:
    return sorted(p for p in notes.glob("*.md") if p.is_file() and not p.name.startswith("_"))


def read_note(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


# -- lignes de sortie ------------------------------------------------------------------------------------------------------------------

def survey(notes: Path, today: dt.date, guard: Guard | None) -> list[dict]:
    """Un enregistrement par note : file, date, nature, review, state (ok, stale, invalid: <raison>). Aucune ligne du corps."""
    rows = []
    maps = []
    for path in note_files(notes):
        text = read_note(path)
        fields, _ = parse_header(text)
        problem = header_problem(fields)
        if problem is None and guard is not None and not guard.unavailable:
            problem = guard.problem(text)
        row = {"file": path.name, "date": (fields or {}).get("date") or "-", "nature": (fields or {}).get("nature") or "-",
               "review": (fields or {}).get("review") or "-", "problem": problem, "kind": (fields or {}).get("kind")}
        if problem is None and row["kind"] == "map":
            maps.append(row)
        rows.append(row)
    maps.sort(key=lambda r: (r["file"] != MAP_NAME, r["file"]))
    for extra in maps[1:]:
        extra["problem"] = "more than one context map"
    for row in rows:
        if row["problem"]:
            row["state"] = f"invalid: {row['problem']}"
        else:
            row["state"] = "stale" if _valid_date(row["review"]) < today else "ok"
    return rows


def print_survey(rows: list[dict], out) -> None:
    for row in rows:
        print(f"{row['file']}  {row['date']}  {row['nature']}  {row['review']}  {row['state']}", file=out)
    stale = sum(r["state"] == "stale" for r in rows)
    invalid = sum(r["state"].startswith("invalid") for r in rows)
    print(f"{len(rows)} notes, {stale} stale, {invalid} invalid", file=out)


# -- la carte (réveil des postures, design D9) -------------------------------------------------------------------------------------------

def map_lines(folder: Path | None, today: dt.date, guard: Guard | None = None, cap: int = MAP_LINE_CAP) -> list[str]:
    """Les lignes de la section « carte du contexte » du réveil : lit le fichier de la carte et rien d'autre du dossier. Après l'en-tête,
    le contrôle de confidentialité (change context-index-name-guard, D5) : une correspondance ou une liste indisponible (garde absente
    comprise) donnent « context map not shown: <raison> », sans aucune ligne du corps ni le nom trouvé."""
    if folder is None or not Path(folder).is_dir():
        return ["no context folder"]
    path = Path(folder) / "notes" / MAP_NAME
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ["no context map"]
    fields, body = parse_header(text)
    problem = header_problem(fields)
    if problem is not None:
        return [f"context map invalid: {problem}"]
    if fields.get("kind") != "map":
        return ["no context map"]
    if guard is None or guard.unavailable:
        return ["context map not shown: sensitive-names list unavailable"]
    problem = guard.problem(text)
    if problem is not None:
        return [f"context map not shown: {problem}"]
    stale = _valid_date(fields["review"]) < today
    head = f"Context map: {fields['date']} · {fields['nature']} · review {fields['review']}"
    if stale:
        head += f" · STALE (review due since {fields['review']})"
    lines = body.strip("\n").splitlines()
    shown = lines[:cap]
    if len(lines) > cap:
        shown.append("(map truncated)")
    return [head, *shown]


def wake_map_lines(project_root, env=None, today=None) -> list[str]:
    """La section « carte du contexte » pour le script de réveil d'une posture : le dossier de contexte par les modules partagés des chemins
    du lab (celui du dossier de code donné), puis `map_lines` avec la garde de ce dossier (liste et extrait lus en place, identifiants
    personnels du dossier de code). Un dossier de contenu introuvable vaut un dossier de contexte absent."""
    env = os.environ if env is None else env
    try:
        folders = lab_paths.resolve(env, file=Path(project_root) / "tools" / "lab_paths.py")
    except lab_paths.LabPathsError:
        return ["no context folder"]
    guard = Guard(env, folders["content_root"], code_root=Path(project_root))
    return map_lines(folders["context_folder"], today or today_paris(env), guard)


# -- sous-commandes ---------------------------------------------------------------------------------------------------------------------

def cmd_init(folder: Path, args, stdin, out) -> int:
    if not args.yes:
        print("Create the context folder with its originals and notes folders (owner only)? [y/N] ", end="", file=out)
        answer = stdin.readline().strip().lower()
        if answer not in ("y", "yes"):
            print("context folder not created", file=out)
            return EXIT_OK
    for path in (folder, folder / "originaux", folder / "notes"):
        try:
            os.mkdir(path, 0o700)
        except FileExistsError:
            pass
        os.chmod(path, 0o700)
    print("context folder ready: originaux and notes, owner only", file=out)
    return EXIT_OK


def cmd_add(folder: Path, guard: Guard, stdin, out) -> int:
    notes = require_notes(folder)
    text = stdin.read()
    fields, _ = parse_header(text)
    problem = header_problem(fields)
    if problem:
        raise Refusal(problem, EXIT_HEADER)
    if guard.unavailable:
        raise Refusal("sensitive-names list unavailable: nothing written", EXIT_MISSING)
    problem = guard.problem(text)
    if problem:
        raise Refusal(problem, EXIT_PRIVATE)
    name = file_name_for(fields)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(notes / name, flags, 0o600)
    except FileExistsError:
        raise Refusal(f"note exists, not overwritten: {name}", EXIT_EXISTS) from None
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    print(f"{PREFIX}note written: {name} (indexed at the next daily run)", file=out)
    return EXIT_OK


def cmd_review(folder: Path, guard: Guard, name: str, date: str, out) -> int:
    notes = require_notes(folder)
    if "/" in name or "\\" in name or name.startswith(".") or not (notes / name).is_file():
        raise Refusal(f"unknown note: {name}", EXIT_USAGE)
    if _valid_date(date) is None:
        raise Refusal("header field not a date: review", EXIT_HEADER)
    path = notes / name
    text = read_note(path)
    fields, _ = parse_header(text)
    problem = header_problem(fields)
    if problem:
        raise Refusal(problem, EXIT_HEADER)
    if _valid_date(date) <= _valid_date(fields["date"]):
        raise Refusal("review date must be after the note date", EXIT_HEADER)
    if guard.unavailable:
        raise Refusal("sensitive-names list unavailable: nothing written", EXIT_MISSING)
    problem = guard.problem(text)
    if problem:
        raise Refusal(problem, EXIT_PRIVATE)
    raw = path.read_bytes().decode("utf-8")
    match = FRONT_MATTER.match(raw)
    header = match.group(0)
    new_header, count = re.subn(r"(?m)^review:[^\r\n]*", f"review: {date}", header, count=1)
    if count != 1:
        raise Refusal("header field missing: review", EXIT_HEADER)
    updated = (new_header + raw[match.end():]).encode("utf-8")
    handle, temporary = tempfile.mkstemp(dir=notes, prefix="_tmp-")
    try:
        with os.fdopen(handle, "wb") as out_file:
            out_file.write(updated)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise
    print(f"{PREFIX}review date updated: {name}", file=out)
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="context_lab.py", description="Notes de contexte de l'organisation (organisation-context).")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="crée les deux sous-dossiers, après confirmation")
    init.add_argument("--yes", action="store_true", help="sans confirmation (tests)")
    sub.add_parser("add", help="écrit une note lue sur l'entrée standard")
    sub.add_parser("check", help="contrôle chaque note")
    sub.add_parser("list", help="liste les notes, sans le contrôle de confidentialité")
    review = sub.add_parser("review", help="remplace la date de revue d'une note")
    review.add_argument("file")
    review.add_argument("date")
    return parser


def main(argv=None, env=None, stdin=None, out=None, err=None, today=None, identifiers=None) -> int:
    """Ligne de commande. `env`, `stdin`, `out`, `err`, `today` (datetime.date) et `identifiers` remplacent l'environnement réel (tests)."""
    env = os.environ if env is None else env
    stdin = sys.stdin if stdin is None else stdin
    out = sys.stdout if out is None else out
    err = sys.stderr if err is None else err
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as stop:
        return int(stop.code or 0)
    try:
        folder, folders = locate(env)
        if args.command == "init":
            return cmd_init(folder, args, stdin, out)
        notes = require_notes(folder)
        day = today or today_paris(env)
        guard = Guard(env, folders["content_root"], identifiers) if args.command != "list" else None
        if args.command == "add":
            return cmd_add(folder, guard, stdin, out)
        if args.command == "review":
            return cmd_review(folder, guard, args.file, args.date, out)
        rows = survey(notes, day, guard)
        print_survey(rows, out)
        if args.command == "check" and guard.unavailable:
            print(f"{PREFIX}sensitive-names list unavailable: confidentiality not checked", file=err)
            return EXIT_INVALID_NOTE
        invalid = any(r["state"].startswith("invalid") for r in rows)
        return EXIT_INVALID_NOTE if args.command == "check" and invalid else EXIT_OK
    except Refusal as refusal:
        print(f"{PREFIX}{refusal.message}", file=err)
        return refusal.code


if __name__ == "__main__":
    sys.exit(main())
