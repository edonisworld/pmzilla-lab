# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=1.2,<2", "pyyaml", "httpx", "numpy", "psycopg[binary]"]
# ///
"""
PMZilla Lab — jeu d'essai des postures.

Rejoue les questions de référence de tests/postures/cas.yaml avec Claude Code en mode non
interactif, vérifie que les règles tiennent toujours (posture annoncée, recherche dans la
bibliothèque, citations, questions de contexte, intervention de Critic, aucun nom en mémoire)
et écrit un rapport comparé au passage précédent.

    uv run ~/PMZilla-Lab/posture_evals.py [--cases id1,id2] [--model M] [--judge-model M] [--keep]
                                           [--real-memory] [--cases-file FICHIER] [--prerequisites-only]

Chaque cas tourne dans une copie temporaire du workspace (git worktree), créée à partir de l'état
courant, modifications non commitées comprises, puis effacée : la mémoire des agents n'est jamais
touchée. Dans la copie, le vécu de chaque posture (MEMORY.md, BOND.md, sessions/) est remplacé par la
version neutre de tests/postures/memoire/<posture>/, la structure (CAPABILITIES, références, identité)
restant celle de l'état testé : les passages sont ainsi comparables. Les sanctums sont créés dans la copie
par init-sanctum.py (ils ne sont plus suivis par Git) et le contexte local est un modèle neutre
(tests/postures/contexte-neutre.md déposé en .pmzilla/contexte.md). --real-memory teste avec la
mémoire et le contexte réels ; le rapport indique « mémoire : figée » ou « mémoire : réelle ». Les vérifications automatiques sont lues dans la trace de la séance ; les critères qui
demandent une lecture sont jugés par Claude, avec une justification.

Sorties :
    _bmad-output/essais/essai-AAAA-MM-JJ-HHMMSS.md   rapport : verdicts et justifications seulement
    ~/.pmzilla-lab/essais/AAAA-MM-JJ-HHMMSS/        traces brutes et resultats.json (hors du dépôt)

Prérequis : Ollama lancé (la bibliothèque calcule ses vecteurs avec bge-m3). Les prérequis d'un cas (`prerequisites`) se lisent
dans la base de la bibliothèque, sous le rôle de lecture seule ; --prerequisites-only les vérifie seuls, sans séance ni rapport.
Coût : une séance Claude Code par cas, plus un jugement par cas. À lancer après une modification,
pas tous les jours.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import datetime as dt
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

WORKSPACE = Path(os.environ.get("PMZILLA_LAB_WORKSPACE", "~/PMZilla-Lab/workspace")).expanduser()
TOOLS = Path(os.environ.get("PMZILLA_LAB_TOOLS", "~/PMZilla-Lab")).expanduser()
DATA = Path(os.environ.get("PMZILLA_LAB_DATA", "~/.pmzilla-lab")).expanduser() / "essais"
CASES_FILE = WORKSPACE / "tests" / "postures" / "cas.yaml"
REPORT_DIR = WORKSPACE / "_bmad-output" / "essais"
CLAUDE = os.environ.get("PMZILLA_LAB_CLAUDE", "claude")
DEFAULT_MODEL_LABEL = "défaut"   # aucun --model / --judge-model : le modèle habituel de Claude Code
CASE_TIMEOUT = 900   # secondes par cas
JUDGE_TIMEOUT = 300
DEFAULT_JUDGE_MODEL = "sonnet"   # calibration du 2026-10-09 : 0 verdict différent sur 55 contre le juge par défaut, mêmes traces

# Outils autorisés pendant un essai : la bibliothèque, la lecture, les skills (postures BMAD), les
# sous-agents (Critic) et le script de réveil des agents BMAD (wake.py), qui charge leur mémoire.
# Les écritures restent dans la copie temporaire (acceptEdits). Aucune autre commande Bash, sauf
# avec --with-bash.
ALLOWED_TOOLS = ["mcp__pmzilla-library", "Read", "Glob", "Grep", "Skill", "Agent", "Task",
                 "TodoWrite", "Write", "Edit",
                 "Bash(uv run .claude/skills/*)", "Bash(uv run scripts/wake.py *)",
                 "Bash(cd * && uv run scripts/wake.py *)",
                 "Bash(uv run tools/journal_lab.py *)"]
# Fichiers exclus de Git mais nécessaires aux agents BMAD (configuration locale) : recopiés dans
# chaque copie temporaire, sinon les agents ne retrouvent pas leur mémoire et se croient neufs.
LOCAL_FILES = ["_bmad/custom/config.user.toml"]
# Base de cas jetable (design.md 7.1) : jamais les vrais cas pendant un essai
CASES_EVAL_AUTHOR = "agile-lead-test"                # auteur inventé de toutes les séances
CASES_ABSENT_DBNAME = "pmzilla_eval_absent"          # nom réservé d'une base qui n'existe pas : les outils des cas répondent par une erreur
CASES_DBNAME_VARIABLE = "PMZILLA_LAB_CASES_DBNAME"
CASES_AUTHOR_VARIABLE = "PMZILLA_LAB_CASES_AUTHOR"
CASES_UNAVAILABLE = "cases database unavailable"
CASES_FIXTURES = Path("tests/postures/cases")        # les fichiers de jeu d'essai restent sous ce dossier (design.md 7.2)
CASES_TABLES = "cases.cases, cases.experiment_notes, cases.experiments"
AUTHOR_FILE = Path(".pmzilla") / "cases.yaml"        # jamais dans la copie : l'auteur d'une séance vient de l'environnement
# Bibliothèque lue dans la base (R-37, design.md D11) : prérequis sous le rôle de lecture seule ; bibliothèque jetable d'un cas
# indexée dans la base jetable du passage, désignée au serveur et à l'indexeur par cette variable
KNOWLEDGE_DBNAME_VARIABLE = "PMZILLA_LAB_KNOWLEDGE_DBNAME"
KNOWLEDGE_READ_ROLE = "pmzilla_knowledge_ro"
KNOWLEDGE_TABLES = "knowledge.book_collections, knowledge.chunks, knowledge.books, knowledge.collections"
LIBRARY_UNREACHABLE = "base de la bibliothèque injoignable"
LIBRARY_UNAVAILABLE = "throwaway library unavailable"
PREREQUISITES_MET = "prérequis satisfaits"
INDEX_TIMEOUT = 600   # secondes pour indexer la bibliothèque jetable d'un cas
# Mémoire figée : version neutre du vécu des postures, qui remplace le vécu réel dans la copie
MEMOIRE_FIGEE = Path("tests/postures/memoire")
VECU_FICHIERS = ("MEMORY.md", "BOND.md")
VECU_DOSSIERS = ("sessions",)
# Contexte local de l'utilisateur (importé par CLAUDE.md, hors Git) : la copie reçoit toujours le modèle neutre
CONTEXTE_LOCAL = Path(".pmzilla/contexte.md")
CONTEXTE_NEUTRE = Path("tests/postures/contexte-neutre.md")
# Par langue : la mémoire neutre française est dans memoire/<posture>/, l'anglaise dans memoire/en/<posture>/ ;
# le contexte neutre français est contexte-neutre.md, l'anglais contexte-neutre.en.md
CONTEXTE_NEUTRE_EN = Path("tests/postures/contexte-neutre.en.md")
POSTURE_TAG = re.compile(r"\[\s*Posture\s*:\s*([^\]]+?)\s*\]", re.IGNORECASE)   # tolérante : aucune langue en particulier
# Vocabulaire par langue (balise de posture, mention hors bibliothèque, formules de Critic) : un fichier unique, lu
# aussi par tools/critic_mirror.py. Celui de l'outil lui-même, pas celui de l'état testé.
VOCABULARY_FILE = Path(__file__).resolve().parents[1] / "tests" / "postures" / "vocabulaire.yaml"
LANGUAGES = ("fr", "en")
DEFAULT_LANGUAGE = "fr"


def load_vocabulary(path: Path | None = None) -> dict[str, dict]:
    """Vocabulaire des postures par langue (tests/postures/vocabulaire.yaml)."""
    data = yaml.safe_load((path or VOCABULARY_FILE).read_text(encoding="utf-8")) or {}
    for language in LANGUAGES:
        if language not in data:
            raise SystemExit(f"Langue absente du vocabulaire {path or VOCABULARY_FILE} : {language}")
    return data


def posture_tags(text: str, language: str, vocabulary: dict | None = None) -> list[str]:
    """Postures annoncées par une balise écrite dans le format de `language` (sans doublon, ordre d'apparition)."""
    pattern = re.compile((vocabulary or load_vocabulary())[language]["posture_tag_pattern"], re.IGNORECASE)
    return list(dict.fromkeys(m.strip() for m in pattern.findall(text)))


# ---------------------------------------------------------------------------
# Copie temporaire du workspace
# ---------------------------------------------------------------------------

def git(*args: str, cwd: Path = WORKSPACE, check: bool = True) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} : {result.stderr.strip()}")
    return result.stdout


def snapshot_commit() -> str:
    """Commit de l'état courant (modifications non commitées des fichiers suivis comprises), sans
    toucher au workspace ni à la pile de stash."""
    return git("stash", "create").strip() or git("rev-parse", "HEAD").strip()


def make_copy(target: Path, commit: str, untracked: bool = True) -> None:
    git("worktree", "add", "--detach", str(target), commit)
    # fichiers nouveaux pas encore ajoutés à Git (une posture en cours d'écriture, par exemple)
    for name in (git("ls-files", "--others", "--exclude-standard", "-z").split("\0") if untracked else []):
        if name and name != AUTHOR_FILE.as_posix() and not name.startswith("_bmad-output/essais/"):   # rapports d'essai : inutiles à la séance
            (target / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(WORKSPACE / name, target / name)
    for name in LOCAL_FILES:
        if (WORKSPACE / name).is_file():
            (target / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(WORKSPACE / name, target / name)
    (target / AUTHOR_FILE).unlink(missing_ok=True)     # même s'il est suivi par Git : l'auteur vient de l'environnement seulement


def neutral_memory_dir(language: str) -> Path:
    return MEMOIRE_FIGEE if language == "fr" else MEMOIRE_FIGEE / language


def neutral_postures(neutral: Path, language: str) -> list[Path]:
    """Dossiers des postures dans la mémoire neutre d'une langue (le dossier `en/` n'est pas une posture)."""
    others = {lang for lang in LANGUAGES if lang != DEFAULT_LANGUAGE}
    return sorted(p for p in neutral.iterdir() if p.is_dir() and (language != "fr" or p.name not in others))


def neutral_context(language: str) -> Path:
    return CONTEXTE_NEUTRE if language == "fr" else CONTEXTE_NEUTRE_EN


def freeze_memory(copy: Path, language: str = DEFAULT_LANGUAGE) -> dict[str, str]:
    """Remplace dans la copie le vécu de chaque posture par la version neutre de tests/postures/memoire/
    (fichiers de vécu remplacés, dossier sessions/ retiré), la structure restant celle de l'état testé.
    Renvoie les fichiers posés (chemin relatif, contenu), pour ne pas les compter comme écrits par la séance."""
    neutral = copy / neutral_memory_dir(language)
    if not neutral.is_dir():
        raise SystemExit(f"Mémoire figée introuvable dans l'état testé : {neutral_memory_dir(language)}/ "
                         "(utilisez --real-memory pour tester avec la mémoire réelle)")
    placed: dict[str, str] = {}
    for posture in neutral_postures(neutral, language):
        target = copy / "_bmad" / "memory" / f"pmzilla-{posture.name}-bmad"
        if not target.is_dir():
            raise SystemExit(f"Mémoire de la posture introuvable : {target.relative_to(copy)}")
        for name in VECU_DOSSIERS:
            shutil.rmtree(target / name, ignore_errors=True)
        for name in VECU_FICHIERS:
            source = posture / name
            if source.is_file():
                shutil.copy2(source, target / name)
                placed[str((target / name).relative_to(copy))] = (target / name).read_text(encoding="utf-8", errors="replace")
            else:
                (target / name).unlink(missing_ok=True)
    return placed


def build_sanctums(copy: Path, language: str = DEFAULT_LANGUAGE) -> None:
    """Crée dans la copie le sanctum de chaque posture à partir des modèles du skill (init-sanctum.py), puisque
    _bmad/memory/ n'est plus suivi par Git. Les fichiers de vécu sont ensuite remplacés par freeze_memory."""
    neutral = copy / neutral_memory_dir(language)
    if not neutral.is_dir():
        raise SystemExit(f"Mémoire figée introuvable dans l'état testé : {neutral_memory_dir(language)}/ "
                         "(utilisez --real-memory pour tester avec la mémoire réelle)")
    for posture in [p.name for p in neutral_postures(neutral, language)]:
        skill = copy / ".claude" / "skills" / f"pmzilla-{posture}-bmad"
        if (copy / "_bmad" / "memory" / skill.name).is_dir():
            continue
        done = subprocess.run([sys.executable, str(skill / "scripts" / "init-sanctum.py"), str(copy), str(skill)],
                              capture_output=True, text=True)
        if done.returncode != 0:
            raise SystemExit(f"init-sanctum.py a échoué pour {posture} : {(done.stderr or done.stdout).strip()}")


def redirect_sanctum_paths(copy: Path) -> None:
    """Le sanctum réel écrit en toutes lettres le chemin du workspace (« votre sanctum, lecture et écriture : … »).
    Dans la copie, ces chemins deviennent ceux de la copie : sans cela, une séance qui écrit sa mémoire « comme on le lui
    dit » écrirait dans le sanctum réel au lieu de sa copie."""
    old, new = str(WORKSPACE), str(copy)
    for name in {old, str(WORKSPACE.resolve())}:
        for path in (copy / "_bmad" / "memory").rglob("*"):
            if path.is_file() and path.suffix in (".md", ".py", ".toml", ".yaml"):
                text = path.read_text(encoding="utf-8", errors="replace")
                if name in text:
                    path.write_text(text.replace(name, new), encoding="utf-8")


def sanctum_digest() -> str:
    """Empreinte du sanctum réel (chemins, tailles et contenus), pour vérifier qu'un cas ne l'a pas modifié."""
    digest = hashlib.sha256()
    root = WORKSPACE / "_bmad" / "memory"
    for path in sorted(root.rglob("*")) if root.is_dir() else []:
        if path.is_file():
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def lock_pass(directory: Path):
    """Un seul passage à la fois : un verrou sur un fichier du dossier des essais. Renvoie le fichier ouvert (à garder
    ouvert pendant tout le passage) ou arrête le script si un autre passage tourne."""
    directory.mkdir(parents=True, exist_ok=True)
    handle = open(directory / ".passage.lock", "w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise SystemExit("Un autre passage du jeu d'essai est en cours (verrou " + str(directory / ".passage.lock") + ") : "
                         "attendez sa fin, deux passages en même temps peuvent se gêner.")
    return handle


def prepare_memory(copy: Path, real: bool, language: str = DEFAULT_LANGUAGE) -> dict[str, str]:
    """Mémoire et contexte local de la copie. Par défaut : sanctums créés puis figés, contexte neutre déposé
    (jamais le contexte personnel). Avec real : le sanctum et le contexte réels du workspace, recopiés.
    Renvoie les fichiers posés, pour ne pas les compter comme écrits par la séance."""
    if real:
        if (WORKSPACE / "_bmad" / "memory").is_dir():
            shutil.copytree(WORKSPACE / "_bmad" / "memory", copy / "_bmad" / "memory", dirs_exist_ok=True)
            redirect_sanctum_paths(copy)
        if (WORKSPACE / CONTEXTE_LOCAL).is_file():
            (copy / CONTEXTE_LOCAL).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(WORKSPACE / CONTEXTE_LOCAL, copy / CONTEXTE_LOCAL)
        return {}
    build_sanctums(copy, language)
    placed = freeze_memory(copy, language)
    context = neutral_context(language)
    neutral = copy / context
    if not neutral.is_file():
        neutral = WORKSPACE / context   # état testé antérieur au contexte local : celui du workspace
    if not neutral.is_file():
        raise SystemExit(f"Contexte neutre introuvable : {context}")
    (copy / CONTEXTE_LOCAL).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(neutral, copy / CONTEXTE_LOCAL)
    placed[str(CONTEXTE_LOCAL)] = (copy / CONTEXTE_LOCAL).read_text(encoding="utf-8", errors="replace")
    return placed


class LibraryReader:
    """Lecture des prérequis dans le schéma knowledge (connexion sous le rôle de lecture seule) : des comptes, jamais de texte ;
    chaque requête termine sa transaction."""

    def __init__(self, conn) -> None:
        self.conn = conn

    def _count(self, sql: str, params: tuple) -> int:
        try:
            with self.conn.cursor() as cursor:
                cursor.execute(sql, params)
                return int(cursor.fetchone()[0])
        finally:
            with contextlib.suppress(Exception):
                self.conn.rollback()

    def books_with_title(self, text: str) -> int:
        """Livres dont le titre contient ce texte, sans tenir compte de la casse."""
        return self._count("SELECT count(*) FROM knowledge.books WHERE strpos(lower(title), lower(%s)) > 0", (text,))

    def books_in_collection(self, name: str) -> int:
        """Livres de la collection de ce nom exact."""
        return self._count("SELECT count(DISTINCT bc.book_id) FROM knowledge.book_collections bc "
                           "JOIN knowledge.collections co ON co.id = bc.collection_id WHERE co.name = %s", (name,))

    def passages_on_topic(self, alternatives: list[tuple[str, bool]]) -> int:
        """Passages dont le plein texte (section et texte) correspond à au moins une des alternatives (voir topic_alternatives),
        sans casse ni accents : une alternative `(texte, True)` est une expression exacte (mots voisins, dans l'ordre,
        `phraseto_tsquery`) ; `(texte, False)` demande tous les mots (`plainto_tsquery`). Un passage compte une fois."""
        if not alternatives:
            return 0
        parts = [f"{'phraseto_tsquery' if phrase else 'plainto_tsquery'}('simple', knowledge.immutable_unaccent(%s))"
                 for _, phrase in alternatives]
        return self._count(f"SELECT count(*) FROM knowledge.chunks WHERE search_vector @@ ({' || '.join(parts)})",
                           tuple(text for text, _ in alternatives))

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.conn.close()


def topic_alternatives(topic: str) -> list[tuple[str, bool]]:
    """Alternatives d'un `absent_topic` : séparées par le mot OR en capitales, en paires `(texte, est_expression)`, guillemets
    retirés du texte. Une alternative entièrement écrite entre guillemets est une expression exacte (mots voisins, dans l'ordre) ;
    sans guillemets, elle demande tous ses mots, où que ce soit dans le passage. Sans casse ni accents. Le sujet est présent quand
    une alternative correspond à un passage. Sans OR : une seule alternative."""
    alternatives = []
    for part in re.split(r"\s+OR\s+", topic.strip()):
        part = part.strip()
        phrase = len(part) > 1 and part.startswith('"') and part.endswith('"') and '"' not in part[1:-1]
        text = " ".join(part.replace('"', " ").split())
        if text:
            alternatives.append((text, phrase))
    return alternatives


def open_library_reader(dbname: str | None = None) -> LibraryReader:
    """La base que lit le serveur de la bibliothèque de la séance : celle de l'installation, ou la base jetable `dbname`."""
    import db
    return LibraryReader(db.connect(role=KNOWLEDGE_READ_ROLE, dbname=dbname))


def unmet_prerequisites(rules: list[dict] | None, dbname: str | None = None, reader=None) -> list[str]:
    """Raisons pour lesquelles un cas ne peut pas être évalué avec la bibliothèque que lira sa séance (champ `prerequisites` de
    cas.yaml), lue dans la base (celle de l'installation, ou la base jetable `dbname` d'un cas à bibliothèque jetable). Règles :
    `book` (un titre contient ce texte, sans casse), `collection` avec `minimum` (livres de la collection de ce nom exact),
    `absent_topic` (au plus `maximum`, défaut 0, passages correspondent au sujet, sans casse ni accents ; des
    alternatives séparées par OR en capitales, une seule suffit ; une alternative entre guillemets est une expression exacte,
    mots voisins et dans l'ordre, sans guillemets elle demande tous ses mots). Une base
    qui ne répond pas ou une règle inconnue comptent comme non satisfaites. `reader` : lecteur déjà ouvert (tests)."""
    rules = rules or []
    if not rules:
        return []
    own = reader is None
    if own:
        try:
            reader = open_library_reader(dbname)
        except Exception:      # ErreurBase, psycopg absent… : jamais de détail de connexion dans le rapport
            return [LIBRARY_UNREACHABLE]
    reasons: list[str] = []
    try:
        for rule in rules:
            try:
                if "book" in rule:
                    if not reader.books_with_title(str(rule["book"])):
                        reasons.append(f"livre absent de la bibliothèque : {rule['book']}")
                elif "collection" in rule:
                    minimum = int(rule.get("minimum", 1))
                    n = reader.books_in_collection(str(rule["collection"]))
                    if n < minimum:
                        reasons.append(f"collection {rule['collection']} : {n} livre(s) pour {minimum} attendu(s)")
                elif "absent_topic" in rule:
                    maximum = int(rule.get("maximum", 0))
                    n = reader.passages_on_topic(topic_alternatives(str(rule["absent_topic"])))
                    if n > maximum:
                        reasons.append(f"le sujet « {rule['absent_topic']} » est présent dans la bibliothèque ({n} passages)")
                else:
                    reasons.append(f"prérequis inconnu : {rule}")
            except Exception as error:
                reasons.append(f"prérequis non vérifiable ({type(error).__name__})")
    finally:
        if own:
            reader.close()
    return reasons


def check_prerequisites_only(cases: list[dict]) -> int:
    """`--prerequisites-only` : chaque cas qui a des prérequis, avec ses raisons ou « prérequis satisfaits », contre la base de
    l'installation. Aucune séance, aucun juge, aucune base jetable, aucun rapport. Code de sortie : 0 tout est satisfait, 1 sinon."""
    unmet_any = False
    checked = [case for case in cases if case.get("prerequisites")]
    if not checked:
        print("Aucun cas n'a de prérequis.")
    for case in checked:
        reasons = unmet_prerequisites(case["prerequisites"])
        unmet_any = unmet_any or bool(reasons)
        print(f"{case['id']} : {'; '.join(reasons) if reasons else PREREQUISITES_MET}")
    return 1 if unmet_any else 0


def drop_copy(target: Path) -> None:
    git("worktree", "remove", "--force", str(target), check=False)
    shutil.rmtree(target, ignore_errors=True)
    git("worktree", "prune", check=False)


def changed_files(copy: Path, placed: dict[str, str] | None = None) -> dict[str, str]:
    """Fichiers créés ou modifiés par la séance dans la copie, avec leur contenu. Les fichiers
    identiques à ceux du workspace (modifications non commitées recopiées au départ) et ceux de la
    mémoire figée posés au départ (s'ils n'ont pas été modifiés depuis) sont ignorés."""
    out = {}
    for line in git("status", "--porcelain", "--untracked-files=all", cwd=copy).splitlines():
        name = line[3:].strip().strip('"')
        path, original = copy / name, WORKSPACE / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if original.is_file() and original.read_text(encoding="utf-8", errors="replace") == text:
            continue
        if placed and placed.get(name) == text:
            continue
        out[name] = text
    return out


# ---------------------------------------------------------------------------
# Séance Claude Code et lecture de la trace
# ---------------------------------------------------------------------------

def saved_session(source: Path, case_id: str) -> tuple[list[dict] | None, dict[str, str]]:
    """Trace et fichiers écrits d'un passage précédent, pour rejuger sans nouvelle séance."""
    trace_file = source / f"{case_id}.jsonl"
    if not trace_file.exists():
        return None, {}
    output = trace_file.read_text(encoding="utf-8").split("\n# stderr\n")[0]
    events = []
    for line in output.splitlines():
        if line.strip().startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    files_file = source / f"{case_id}.fichiers.json"
    files = json.loads(files_file.read_text(encoding="utf-8")) if files_file.exists() else {}
    return events, files


def show_tools(source: Path) -> None:
    """Résumé des outils appelés par séance : pour comprendre un échec ou un refus d'outil."""
    if not source.is_dir():
        raise SystemExit(f"Passage introuvable : {source}")
    for trace_file in sorted(source.glob("*.jsonl")):
        events, _ = saved_session(source, trace_file.stem)
        trace = read_trace(events or [])
        print(f"\n## {trace_file.stem}" + (f" · refusés : {', '.join(trace['denied'])}" if trace["denied"] else ""))
        for call in trace["calls"]:
            data = call["input"]
            if call["name"] == "Bash":
                detail = data.get("command", "")
            elif call["name"] == "Skill":
                detail = data.get("skill") or data.get("command") or json.dumps(data, ensure_ascii=False)
            elif call["name"] in ("Agent", "Task"):
                detail = data.get("subagent_type", "")
            elif "search_library" in call["name"]:
                detail = f"{data.get('query', '')} · {data.get('collections') or 'toutes'}"
            else:
                detail = data.get("file_path") or data.get("pattern") or ""
            print(f"- {call['name'].replace('mcp__pmzilla-library__', '')} : {str(detail)[:160]}")
            if call["name"] == "Bash" and call["result"]:
                print("    → " + call["result"].strip().replace("\n", "\n      ")[:1200])


BACKEND_REFUSED = "--backend n'existe plus : la bibliothèque est lue dans PostgreSQL seulement"


def refuse_backend_option(argv: list[str]) -> None:
    """`--backend` (quelle que soit sa valeur) : arrêt avant toute copie, base ou séance, code 2."""
    if any(arg == "--backend" or arg.startswith("--backend=") for arg in argv):
        print(f"PMZilla Lab, erreur : {BACKEND_REFUSED}.", file=sys.stderr)
        raise SystemExit(2)


def check_fixtures(cases: list[dict]) -> None:
    """Chaque `cases_fixture` (du cas et de son bloc `en`) existe et reste sous tests/postures/cases/ ; sinon, refus qui nomme le cas."""
    allowed = (WORKSPACE / CASES_FIXTURES).resolve()
    for case in cases:
        for where, block in (("", case), (" (bloc en)", case.get("en") if isinstance(case.get("en"), dict) else {})):
            value = block.get("cases_fixture")
            if value is None:
                continue
            path = (WORKSPACE / value).resolve() if isinstance(value, str) and value else None
            if path is None or allowed not in path.parents or not path.is_file():
                raise SystemExit(f"Cas {case.get('id', '?')}{where} : cases_fixture « {value} » doit être un fichier existant "
                                 f"sous {CASES_FIXTURES.as_posix()}/")


def cases_environment(dbname: str | None) -> dict[str, str]:
    """Variables de la séance et de la configuration MCP : base jetable et auteur inventé ; sans base jetable, un nom qui n'existe
    pas et un auteur vide (jamais la base réelle)."""
    if dbname:
        return {CASES_DBNAME_VARIABLE: dbname, CASES_AUTHOR_VARIABLE: CASES_EVAL_AUTHOR}
    return {CASES_DBNAME_VARIABLE: CASES_ABSENT_DBNAME, CASES_AUTHOR_VARIABLE: ""}


def create_cases_database() -> str | None:
    """Base jetable `pmzilla_eval_<hex>` de l'instance (connexion du superutilisateur de db.connect), toutes migrations appliquées ;
    None si elle ne peut pas être créée (instance arrêtée)."""
    name = "pmzilla_eval_" + secrets.token_hex(6)
    admin = None
    created = False
    try:
        import db
        admin = db.connect(autocommit=True)
        admin.execute(f'CREATE DATABASE "{name}"')
        created = True
        conn = connect_cases_database(name)
        try:
            db.migrer(conn, db.lister_migrations(db.DOSSIER_MIGRATIONS))
            conn.commit()
        finally:
            conn.close()
        return name
    except Exception as error:
        # ErreurBase (db.py) est déjà réécrite sans secret et nomme le Trousseau et la variable du mot de passe ; toute autre exception : son type seul
        detail = str(error) if type(error).__name__ == "ErreurBase" else type(error).__name__
        print(f"Base de cas jetable indisponible : {detail}", file=sys.stderr)
        if created:
            with contextlib.suppress(Exception):
                drop_cases_database(name)
        return None
    finally:
        if admin is not None:
            with contextlib.suppress(Exception):
                admin.close()


def connect_cases_database(name: str):
    import db
    return db.connect(dbname=name)


def drop_cases_database(name: str) -> None:
    import db
    admin = db.connect(autocommit=True)
    try:
        admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    finally:
        admin.close()


def reset_cases_database(name: str, fixture: Path | None) -> None:
    """Avant un cas : vide les trois tables (numérotation repartie de 1), puis charge le jeu d'essai du cas s'il en a un."""
    import cases_store
    conn = connect_cases_database(name)
    try:
        conn.execute(f"TRUNCATE {CASES_TABLES} RESTART IDENTITY")
        conn.commit()
        if fixture is not None:
            cases_store.load_fixture(conn, cases_store.default_embed, fixture)
    finally:
        conn.close()


def mcp_config(folder: Path, knowledge_dbname: str | None = None,
               cases_env: dict[str, str] | None = None, label: str | None = None) -> Path:
    """Configuration MCP de la bibliothèque. Avec `knowledge_dbname` (bibliothèque jetable d'un cas), le serveur lit cette base
    (PMZILLA_LAB_KNOWLEDGE_DBNAME) ; sinon celle de l'installation. Aucune voie n'est jamais passée au serveur. `label` nomme un fichier à part, pour ne pas écraser celui du passage."""
    config = folder / ("mcp.json" if label is None else f"mcp-{label}.json")
    server = {"command": shutil.which("uv") or "/opt/homebrew/bin/uv",
              "args": ["run", str(TOOLS / "pmzilla_lab_library.py"), "serve"]}
    if knowledge_dbname:
        server["env"] = {KNOWLEDGE_DBNAME_VARIABLE: knowledge_dbname}
    if cases_env:
        server["env"] = {**server.get("env", {}), **cases_env}
    config.write_text(json.dumps({"mcpServers": {"pmzilla-library": server}}, indent=2))
    return config


class LibraryUnavailable(Exception):
    """La bibliothèque jetable d'un cas ne peut pas être préparée : le cas est non évaluable, avec ce message."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"{LIBRARY_UNAVAILABLE} : {detail}" if detail else LIBRARY_UNAVAILABLE)


def reset_case_library(name: str) -> None:
    """Vide les tables de la bibliothèque de la base jetable du passage (jamais celle de l'installation)."""
    conn = connect_cases_database(name)
    try:
        conn.execute(f"TRUNCATE {KNOWLEDGE_TABLES} RESTART IDENTITY")
        conn.commit()
    finally:
        conn.close()


def case_library(case: dict, folder: Path, cases_env: dict[str, str] | None = None, dbname: str | None = None) -> Path | None:
    """Cas à bibliothèque jetable (`library: dossier`, relatif à la racine du workspace : un sous-dossier par collection,
    des articles inventés) : vide la bibliothèque de la base jetable `dbname` du passage, y indexe ce dossier par l'indexeur
    (`pmzilla_lab_library.py index`, la base désignée par PMZILLA_LAB_KNOWLEDGE_DBNAME) et rend la configuration MCP qui la lit.
    Rien n'est écrit dans la base de l'installation. Sans base jetable, ou si l'indexation échoue : LibraryUnavailable."""
    if not case.get("library"):
        return None
    if not dbname:
        raise LibraryUnavailable("")
    try:
        reset_case_library(dbname)
    except Exception as error:
        raise LibraryUnavailable(f"vidage impossible ({type(error).__name__})") from None
    try:
        done = subprocess.run([shutil.which("uv") or "/opt/homebrew/bin/uv", "run", str(TOOLS / "pmzilla_lab_library.py"), "index",
                               str(WORKSPACE / case["library"])], env={**os.environ, KNOWLEDGE_DBNAME_VARIABLE: dbname},
                              capture_output=True, text=True, timeout=INDEX_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise LibraryUnavailable(f"indexation interrompue après {INDEX_TIMEOUT} s") from None
    if done.returncode != 0:
        lines = ((done.stderr or "") + "\n" + (done.stdout or "")).strip().splitlines()
        last = lines[-1].strip() if lines else ""
        raise LibraryUnavailable(f"indexation en échec (code {done.returncode})" + (f" : {last[:200]}" if last else ""))
    return mcp_config(folder, knowledge_dbname=dbname, cases_env=cases_env, label=f"bibliotheque-{case['id']}")


def place_files(case: dict, copy: Path) -> None:
    """Cas à fichiers inventés (`files: [{from, to}]`) : copie chaque fichier de `from` (relatif à la racine du workspace)
    vers `to` (relatif à la copie, dans la copie seulement)."""
    for item in case.get("files") or []:
        target = (copy / item["to"]).resolve()
        if copy.resolve() not in target.parents:
            raise ValueError(f"files : « {item['to']} » sort de la copie")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(WORKSPACE / item["from"], target)


SESSION_NOTE = {
    "fr": "Le dossier de travail est {copy}. Dans les commandes Bash, n'utilise jamais $PWD ni "
          "$(pwd) : écris ce chemin en clair.",
    "en": "The working folder is {copy}. In Bash commands, never use $PWD or "
          "$(pwd): write this path out in full.",
}


def run_session(question: str, copy: Path, mcp: Path, model: str | None, trace: Path, bash: bool,
                language: str = DEFAULT_LANGUAGE, env: dict[str, str] | None = None) -> list[dict]:
    command = [CLAUDE, "-p", question, "--output-format", "stream-json", "--verbose",
               "--permission-mode", "acceptEdits", "--mcp-config", str(mcp), "--strict-mcp-config",
               "--allowedTools", *ALLOWED_TOOLS, *(["Bash"] if bash else []),
               # Claude Code refuse en mode non interactif toute commande qui contient une expansion
               # ($PWD, $(pwd)), même autorisée : on donne le chemin en clair pour le script de réveil
               "--append-system-prompt",
               SESSION_NOTE.get(language, SESSION_NOTE[DEFAULT_LANGUAGE]).format(copy=copy)]
    if model:
        command += ["--model", model]
    try:
        # La séance prend sa copie pour espace de travail : le crochet de début de séance (journal_lab) y cherche l'auteur des cas,
        # jamais dans le .pmzilla/cases.yaml du vrai dépôt (la copie n'en contient pas), pour rester silencieux avec un auteur vide.
        result = subprocess.run(command, cwd=copy, capture_output=True, text=True, timeout=CASE_TIMEOUT,
                                env={**os.environ, "PMZILLA_LAB_WORKSPACE": str(copy), **(env or {})})
        output, error = result.stdout, result.stderr
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        error = f"délai dépassé ({CASE_TIMEOUT} s)"
    trace.write_text(output + ("\n# stderr\n" + error if error else ""), encoding="utf-8")
    events = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events


def read_trace(events: list[dict]) -> dict:
    """Ce que la séance a fait : outils appelés, sections renvoyées par la bibliothèque, réponse."""
    calls, sections, texts, mentions = [], [], [], []
    main_texts, result_texts, last_tool = [], [], -1   # (position, texte) du fil principal ; position du dernier outil
    final = {"result": "", "cost": None, "turns": None, "error": True, "denied": []}
    for position, event in enumerate(events):
        if event.get("type") == "assistant":
            main_thread = not event.get("parent_tool_use_id")
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    calls.append({"name": block.get("name", ""), "input": block.get("input", {}),
                                  "id": block.get("id"), "result": ""})
                    if main_thread:
                        last_tool = position
                elif block.get("type") == "text" and main_thread:
                    texts.append(block.get("text", ""))
                    main_texts.append((position, block.get("text", "")))
        elif event.get("type") == "user":
            for block in event.get("message", {}).get("content", []) or []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    content = block.get("content")
                    raw = content if isinstance(content, str) else " ".join(
                        part.get("text", "") for part in content or [] if isinstance(part, dict))
                    for call in calls:
                        if call["id"] and call["id"] == block.get("tool_use_id"):
                            call["result"] = raw
                    sections += re.findall(r'"section"\s*:\s*"([^"]*)"', raw)
                    # chapitres et parties nommés dans le texte des passages lus : une réponse peut
                    # légitimement les citer même si l'index n'a pas de titre de section
                    plain = raw.replace("\\n", " ")
                    mentions += [m.group(0).strip() for m in re.finditer(
                        r".{0,60}\b(?:chapter|chapitre|part|partie)\s+(?:\d+|[IVXLC]+\b|one|two|three|four|five|six|"
                        r"seven|eight|nine|ten|eleven|twelve).{0,60}", plain, re.IGNORECASE)]
        elif event.get("type") == "result":
            result_texts.append((position, event.get("result") or ""))
            final = {"result": event.get("result") or "", "cost": event.get("total_cost_usd"),
                     "turns": event.get("num_turns"), "error": bool(event.get("is_error")),
                     "denied": [denial_text(d) for d in event.get("permission_denials") or []]}
    answer = final["result"] or "\n\n".join(texts)
    return {"calls": calls, "sections": sorted({s for s in sections if s}), "answer": answer,
            "messages": final_messages(main_texts, result_texts, last_tool), "result_count": len(result_texts),
            "mentions": list(dict.fromkeys(mentions))[:60],
            "all_text": "\n\n".join(texts + [final["result"]]), **final}


def final_messages(main_texts: list[tuple[int, str]], result_texts: list[tuple[int, str]], last_tool: int) -> list[str]:
    """Messages de texte du dernier échange, dans l'ordre : ceux du fil principal après son dernier appel d'outil (les
    phrases d'amorce avant les outils en sont exclues), plus le texte de chaque événement `result`, replacé à la position
    du message d'où il vient quand on la retrouve (un `result` est émis en fin de flux, après des messages plus récents).
    Sans doublon. Quand Critic tourne en arrière-plan, l'analyse et la restitution de Critic sont deux messages."""
    found: dict[str, int] = {text.strip(): position for position, text in main_texts if position > last_tool and text.strip()}
    for position, text in result_texts:
        key = text.strip()
        if key and key not in found:
            origin = [p for p, t in main_texts if t.strip() == key]
            found[key] = origin[-1] if origin else position
    return [text for text, _ in sorted(found.items(), key=lambda item: item[1])]


def denial_text(denial: dict) -> str:
    tool = denial.get("tool_name", "?")
    command = (denial.get("tool_input") or {}).get("command")
    return f"{tool} ({command[:140]})" if command else tool


def is_critic(call: dict) -> bool:
    return call["name"] in ("Agent", "Task") and "pmzilla-critic" in json.dumps(call["input"])


def tool_calls(trace: dict, tool: str) -> list[dict]:
    return [c for c in trace["calls"] if c["name"] == tool or c["name"].endswith("__" + tool)]


# ---------------------------------------------------------------------------
# Vérifications
# ---------------------------------------------------------------------------

def check_posture(expected: str | None, trace: dict, language: str = DEFAULT_LANGUAGE,
                  vocabulary: dict | None = None) -> dict | None:
    if expected is None:
        return None
    vocabulary = vocabulary or load_vocabulary()
    # la balise est en tête de la première réponse ; le dernier message (après Critic, par exemple)
    # ne la répète pas forcément : on cherche dans tout le fil principal
    found = posture_tags(trace["all_text"], language, vocabulary)
    # garde contre la dérive de formule : la balise de l'autre langue fait échouer la vérification
    other = [t for lang in LANGUAGES if lang != language for t in posture_tags(trace["all_text"], lang, vocabulary)]
    # nom exact (lot 5b) : une balise accentuée, traduite ou d'une autre casse échoue, même à côté d'une balise juste
    misspelt = [t for t in found if t not in vocabulary["posture_names"]]
    if expected.lower() == "aucune":
        ok = not found and not other
        detail = "aucune balise" if ok else f"balise trouvée : {', '.join(found + other)}"
    else:
        ok = any(f.lower() == expected.lower() for f in found) and not other and not misspelt
        detail = f"balise : {', '.join(found) or 'absente'}"
        if misspelt:
            expected_tag = vocabulary[language]["posture_tag"].format(posture=_posture_name(expected, vocabulary))
            detail += "".join(f" ; balise mal écrite : {vocabulary[language]['posture_tag'].format(posture=t)} "
                              f"(attendu : {expected_tag})" for t in misspelt)
    if other:
        detail += f" ; balise dans le format de l'autre langue : {', '.join(other)} (attendu : {vocabulary[language]['posture_tag']})"
    return {"critere": f"Posture {expected}", "ok": ok, "justification": detail}


def _posture_name(expected: str, vocabulary: dict) -> str:
    """Le nom exact d'une posture attendue (cas.yaml l'écrit dans n'importe quelle casse)."""
    return next((n for n in vocabulary["posture_names"] if n.lower() == expected.lower()), expected)


PLACEMENT_MARKUP = " \t*_#>"   # gras, italique, titre ou citation autour de la balise : sans effet sur sa place


def check_tag_placement(expected: str | None, trace: dict, language: str = DEFAULT_LANGUAGE,
                        vocabulary: dict | None = None) -> dict | None:
    """Indicateur non bloquant (lot 5b) : la première ligne non vide de la réponse finale commence par la balise attendue,
    au format de la langue. Aucun indicateur sans posture attendue ou pour « aucune ». Pourra devenir bloquant avec
    l'accord de l'utilisateur, après les jeux d'essai du lot 5b."""
    if expected is None or expected.lower() == "aucune":
        return None
    vocabulary = vocabulary or load_vocabulary()
    first = next((line.strip() for line in final_answer(trace).splitlines() if line.strip()), "")
    match = re.match(vocabulary[language]["posture_tag_pattern"], first.lstrip(PLACEMENT_MARKUP))
    ok = bool(match) and match.group(1).strip() == _posture_name(expected, vocabulary)
    return {"critere": "La balise de posture ouvre la réponse", "ok": ok, "indicateur": True,
            "justification": "balise en tête" if ok else f"première ligne : {first[:80]}"}


FORMULA_KEYS = ("out_of_library", "hypothesis", "critic_final_title")


def other_language_formulas(language: str, vocabulary: dict) -> list[str]:
    """Formules fixes (vocabulaire.yaml) des autres langues que `language`, sans celles que la langue partage avec elle."""
    own = {v.casefold() for v in _formulas(vocabulary[language])}
    return [f for lang in LANGUAGES if lang != language for f in _formulas(vocabulary[lang]) if f.casefold() not in own]


def _formulas(values: dict) -> list[str]:
    return [values[k] for k in FORMULA_KEYS] + list(values["source_separation"])


def check_language_formulas(trace: dict, language: str = DEFAULT_LANGUAGE, vocabulary: dict | None = None) -> dict:
    """Indicateur non bloquant, pour tous les cas : la réponse finale ne contient aucune formule fixe de l'autre langue
    (« outside the library » dans une réponse française, « hors bibliothèque » dans une réponse anglaise…). Rapporté à part,
    hors du total (lot 6, décision du 7 octobre) ; la balise de posture a sa propre garde dans `check_posture`."""
    vocabulary = vocabulary or load_vocabulary()
    answer = final_answer(trace).replace("\u2019", "'").casefold()
    hits = [f for f in other_language_formulas(language, vocabulary) if f.replace("\u2019", "'").casefold() in answer]
    return {"critere": "Aucune formule fixe de l'autre langue dans la réponse", "ok": not hits, "indicateur": True,
            "justification": "aucune" if not hits else "formule(s) de l'autre langue : " + " ; ".join(hits)}


def check_single_final(trace: dict) -> dict:
    """Indicateur non bloquant, pour tous les cas : la séance se termine par un seul message final (un seul événement
    `result`, un seul message de texte après le dernier outil). Quand Critic tourne en arrière-plan, la posture écrit son
    analyse puis restitue Critic dans un second message : CLAUDE.md veut un message final unique (Critic au premier plan).
    Pourra devenir bloquant avec l'accord de l'utilisateur."""
    messages, results = trace.get("messages") or [], trace.get("result_count", 1)
    ok = len(messages) <= 1 and results <= 1
    return {"critere": "Un seul message final", "ok": ok, "indicateur": True,
            "justification": "un seul message final" if ok else
            f"{max(len(messages), 1)} messages dans le dernier échange, {results} événement(s) de résultat"}


# ---------------------------------------------------------------------------
# Structure d'une réponse qui s'appuie sur des articles de veille : section « Sources » dernière, dates et lignes
# Sources. Ces conditions sont déterministes : elles sortent du juge (diagnostic des cas instables, 2026-10-07).
# ---------------------------------------------------------------------------

SOURCES_HEADING = re.compile(r"(?im)^\W*(#+\s*)?\**sources\**\s*:?\s*\**\s*$")
LIST_ITEM = re.compile(r"^\s*([-*]|\d+[.)])\s+")
ISO_DATE = re.compile(r"\b(20\d\d-\d\d-\d\d)\b")
SITE_DOMAIN = re.compile(r"\b([a-z0-9-]+)\.(?:com|co|io|org|net|dev|ai|fr)\b")


def final_answer(trace: dict) -> str:
    return trace.get("answer") or trace.get("all_text") or ""


def split_sources(answer: str) -> tuple[str, list[str] | None, list[str]]:
    """(corps, lignes de la liste Sources, lignes qui suivent la liste sans en faire partie). Sans section Sources :
    (réponse, None, [])."""
    headings = list(SOURCES_HEADING.finditer(answer))
    if not headings:
        return answer, None, []
    body, rest = answer[:headings[-1].start()], answer[headings[-1].start():].lstrip().splitlines()[1:]
    # une ligne de Sources est une entrée si elle porte une date ou un lien, avec ou sans puce (CLAUDE.md : « un article
    # par ligne, au format Auteur (ou site), « Titre », AAAA-MM-JJ, lien ») ; une ligne indentée prolonge l'entrée
    # précédente ; tout le reste (livres, sous-titre, question, remarque) suit la liste sans en faire partie.
    is_entry = lambda line: bool(ISO_DATE.search(line) or re.search(r"https?://", line))
    items = [LIST_ITEM.sub("", line).strip() for line in rest if is_entry(line)]
    extra = [line.strip() for line in rest if line.strip() and not is_entry(line) and not re.match(r"^\s{2,}\S", line)]
    return body, items, extra


def _plain(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def source_keys(line: str) -> set[str]:
    """Noms de famille (mots entiers, 4 lettres au moins) et radical du site d'une ligne Sources."""
    head = re.sub(r"\(auteur non indiqué\)", "", re.split(r"[«\"“]", line)[0])
    keys = {"n:" + t.lower() for t in (w.strip(" .,:;()*&") for w in re.split(r"\s+|,|\bet\b", head))
            if len(t) >= 4 and t[0].isupper()}
    for domain in SITE_DOMAIN.findall(line.split("http")[0].lower()):
        if len(_plain(domain)) > 3:
            keys.add("s:" + _plain(domain))
    return keys


def key_in(key: str, text: str) -> bool:
    kind, value = key.split(":", 1)
    if kind == "n":
        return re.search(r"(?<![\wÀ-ÿ])" + re.escape(value) + r"(?![\wÀ-ÿ])", text.lower()) is not None
    return value in _plain(text)


def check_ends_with_sources(trace: dict) -> dict:
    """La section « Sources » est la dernière : après son titre, il n'y a que des lignes de liste."""
    body, items, extra = split_sources(final_answer(trace))
    if items is None:
        return {"critere": "La réponse se termine par une section « Sources »", "ok": False,
                "justification": "aucune section « Sources »"}
    ok = not extra
    return {"critere": "La réponse se termine par une section « Sources »", "ok": ok,
            "justification": f"{len(items)} ligne(s) Sources, rien ne la suit" if ok else
                             f"texte après la liste : « {extra[0][:80]} »" + (f" (+{len(extra) - 1})" if len(extra) > 1 else "")}


def check_dates_in_sources(trace: dict) -> dict:
    """Toute date du texte est la date d'une ligne Sources. Les dates d'un titre (ligne qui commence par « # ») ne
    comptent pas : la période d'une synthèse n'est pas la date d'un article."""
    body, items, _ = split_sources(final_answer(trace))
    body = "\n".join(line for line in body.splitlines() if not line.lstrip().startswith("#"))
    label = "Toute date du texte figure dans Sources"
    if not items:
        return {"critere": label, "ok": False, "justification": "aucune section « Sources » exploitable"}
    known = {d for line in items for d in ISO_DATE.findall(line)}
    missing = sorted({d for d in ISO_DATE.findall(body) if d not in known})
    return {"critere": label, "ok": not missing,
            "justification": "toutes les dates du texte sont dans Sources" if not missing else
                             "dates du texte absentes de Sources : " + ", ".join(missing)}


def check_sources_cited(trace: dict) -> dict:
    """Chaque ligne Sources est citée dans le texte (nom de famille ou site)."""
    body, items, _ = split_sources(final_answer(trace))
    label = "Chaque ligne Sources est citée dans le texte"
    if not items:
        return {"critere": label, "ok": False, "justification": "aucune section « Sources » exploitable"}
    never = [line[:60] for line in items if source_keys(line) and not any(key_in(k, body) for k in source_keys(line))]
    return {"critere": label, "ok": not never,
            "justification": f"{len(items)} ligne(s), toutes citées" if not never else
                             "jamais citée dans le texte : " + " | ".join(never)}


def check_auto(rule: dict, trace: dict, files: dict[str, str]) -> dict:
    """Applique une règle de `verifications`. `non_blocking: true` fait de la vérification un indicateur : rapportée à
    part, elle ne compte ni dans le total ni dans les régressions du bilan."""
    result = _check_auto(rule, trace, files)
    if rule.get("non_blocking"):
        result["indicateur"] = True
    return result


EXIT_NOT_VALIDATING = 3      # passage avec des cas non évaluables : rien n'est validé


def blocking_count(case: dict) -> int:
    """Nombre de vérifications bloquantes d'un cas, jouées ou non : la posture annoncée, les règles et les jugements non marqués non bloquants."""
    return (1 if case.get("posture") is not None else 0) \
        + sum(1 for r in case.get("verifications") or [] if not r.get("non_blocking")) \
        + sum(1 for j in case.get("judgements") or [] if not (isinstance(j, dict) and j.get("non_blocking")))


def expected_total(results: list[dict]) -> int:
    """Total bloquant sur 37 (par exemple) : les vérifications jouées plus celles des cas non évaluables."""
    return sum(len(blocking(c["verifications"])) + (c.get("bloquantes_attendues", 0) if c.get("non_evaluable") else 0) for c in results)


def blocking(checks: list[dict]) -> list[dict]:
    return [c for c in checks if not c.get("indicateur")]


def indicators(checks: list[dict]) -> list[dict]:
    return [c for c in checks if c.get("indicateur")]


def _check_auto(rule: dict, trace: dict, files: dict[str, str]) -> dict:
    if "ends_with_sources" in rule:
        return check_ends_with_sources(trace)
    if "dates_in_sources" in rule:
        return check_dates_in_sources(trace)
    if "sources_cited" in rule:
        return check_sources_cited(trace)
    if "tool" in rule:
        calls = tool_calls(trace, rule["tool"])
        wanted = rule.get("collections")
        if wanted:
            used = {c for call in calls for c in (call["input"].get("collections") or [])}
            ok = bool(used & set(wanted))
            return {"critere": f"{rule['tool']} sur {', '.join(wanted)}", "ok": ok,
                    "justification": f"{len(calls)} appel(s), collections : {', '.join(sorted(used)) or 'aucune précisée'}"}
        return {"critere": f"Appel à {rule['tool']}", "ok": bool(calls),
                "justification": f"{len(calls)} appel(s)"}
    if "critic" in rule:
        called = any(is_critic(c) for c in trace["calls"])
        return {"critere": "Critic appelé" if rule["critic"] else "Critic non appelé",
                "ok": called == bool(rule["critic"]),
                "justification": "pmzilla-critic appelé" if called else "pmzilla-critic non appelé"}
    if "text" in rule:
        ok = re.search(rule["text"], trace["all_text"], re.IGNORECASE) is not None
        return {"critere": f"Contient « {rule['text']} »", "ok": ok,
                "justification": "présent" if ok else "absent"}
    if "without_text" in rule:
        ok = re.search(rule["without_text"], trace["all_text"], re.IGNORECASE) is None
        return {"critere": f"Ne contient pas « {rule['without_text']} »", "ok": ok,
                "justification": "absent" if ok else "présent"}
    if "memory_without" in rule:
        hits = [name for name, text in files.items() if re.search(rule["memory_without"], text)]
        return {"critere": f"Aucun fichier écrit ne contient « {rule['memory_without']} »", "ok": not hits,
                "justification": (f"trouvé dans : {', '.join(hits)}" if hits else
                                  f"{len(files)} fichier(s) écrit(s), motif absent")}
    raise SystemExit(f"Vérification inconnue dans cas.yaml : {rule}")


JUDGE_PROMPT_FR = """Tu évalues la réponse d'un assistant de coaching agile (PMZilla Lab) à une question de test.
Pour chaque critère, écris d'abord une justification d'une ou deux phrases qui cite ou décrit précisément
l'élément de la réponse, puis décide si le critère est rempli. Sois strict : un critère à moitié rempli
ne l'est pas. Juge la réponse telle qu'elle est, sans la compléter.

Question posée :
{question}

Outils appelés pendant la séance :
{calls}

Sections renvoyées par la bibliothèque :
{sections}

Chapitres ou parties nommés dans le texte des passages lus (extraits) :
{mentions}

Réponse de l'assistant :
<<<
{answer}
>>>

Critères :
{criteria}

Réponds uniquement par un objet JSON, sans texte autour :
{{"jugements": [{{"critere": "<texte du critère>", "justification": "<…>", "ok": true}}]}}
"""

JUDGE_PROMPT_EN = """You evaluate the answer of an agile coaching assistant (PMZilla Lab) to a test question.
For each criterion, first write a one or two sentence justification that quotes or precisely describes the
element of the answer, then decide whether the criterion is met. Be strict: a half-met criterion is not met.
Judge the answer as it is, without completing it.

Question asked:
{question}

Tools called during the session:
{calls}

Sections returned by the library:
{sections}

Chapters or parts named in the text of the passages read (excerpts):
{mentions}

Assistant's answer:
<<<
{answer}
>>>

Criteria:
{criteria}

Reply only with a JSON object, with no text around it:
{{"judgements": [{{"criterion": "<text of the criterion>", "justification": "<…>", "ok": true}}]}}
"""

JUDGE_PROMPT = JUDGE_PROMPT_FR   # nom d'avant le choix de langue
JUDGE_PROMPTS = {"fr": JUDGE_PROMPT_FR, "en": JUDGE_PROMPT_EN}
JUDGE_KEYS = {"fr": "jugements", "en": "judgements"}                 # clé de la liste de verdicts attendue
SANCTUM_CRITERION = "Sanctum réel intact"      # jamais rejoué : écrire hors de la copie n'est pas une variation du modèle
JUDGE_MESSAGES = {"fr": "(La réponse comporte {n} messages successifs ; les critères s'appliquent à l'ensemble.)",
                  "en": "(The answer consists of {n} successive messages; the criteria apply to all of them together.)"}


def judged_answer(trace: dict, language: str = DEFAULT_LANGUAGE) -> str:
    """Ce que le juge lit : le dernier message seul quand il n'y en a qu'un (entrée inchangée), sinon tous les messages
    du dernier échange dans l'ordre, séparés par `=== message i/n ===`."""
    messages = trace.get("messages") or []
    if len(messages) <= 1:
        return trace["answer"]
    parts = [f"=== message {i}/{len(messages)} ===\n{text}" for i, text in enumerate(messages, 1)]
    return JUDGE_MESSAGES[language].format(n=len(messages)) + "\n\n" + "\n\n".join(parts)


JUDGE_NONE = {"fr": ("- aucun", "- aucune", "(aucune réponse)"), "en": ("- none", "- none", "(no answer)")}


def judge(case: dict, trace: dict, model: str | None, folder: Path, language: str = DEFAULT_LANGUAGE) -> list[dict]:
    """Un critère jugé est un texte, ou `{text: …, non_blocking: true}` : alors un indicateur, rapporté à part."""
    entries = case.get("judgements") or []
    if not entries:
        return []
    criteria = [c["text"] if isinstance(c, dict) else c for c in entries]
    flagged = [bool(isinstance(c, dict) and c.get("non_blocking")) for c in entries]
    none_calls, none_sections, none_answer = JUDGE_NONE[language]
    calls = "\n".join(f"- {c['name']} {json.dumps(c['input'], ensure_ascii=False)[:200]}"
                      for c in trace["calls"]) or none_calls
    prompt = JUDGE_PROMPTS[language].format(
        question=case["question"], calls=calls, sections="\n".join(f"- {s}" for s in trace["sections"]) or none_sections,
        mentions="\n".join(f"- …{m}…" for m in trace["mentions"]) or none_calls,
        answer=judged_answer(trace, language) or none_answer, criteria="\n".join(f"{i}. {c}" for i, c in enumerate(criteria, 1)))
    command = [CLAUDE, "-p", prompt, "--output-format", "json"]
    if model:
        command += ["--model", model]
    neutral = folder / "juge"   # dossier vide : pas de CLAUDE.md, pas de règles de PMZilla
    neutral.mkdir(exist_ok=True)
    try:
        result = subprocess.run(command, cwd=neutral, capture_output=True, text=True, timeout=JUDGE_TIMEOUT)
        text = json.loads(result.stdout).get("result", "") if result.stdout.strip().startswith("{") else result.stdout
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        text = f"erreur : {exc}"
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        verdicts = json.loads(match.group(0))[JUDGE_KEYS[language]] if match else []
    except (json.JSONDecodeError, KeyError, TypeError):
        verdicts = []
    out = []
    for i, criterion in enumerate(criteria):
        verdict = verdicts[i] if i < len(verdicts) and isinstance(verdicts[i], dict) else {}
        out.append({"critere": criterion, "ok": verdict.get("ok") is True,
                    "justification": verdict.get("justification") or "pas de jugement exploitable",
                    **({"indicateur": True} if flagged[i] else {})})
    return out


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------

def previous_results(current: Path, language: str = DEFAULT_LANGUAGE) -> dict:
    """Résultats du passage précédent dans la même langue (un passage sans champ `langue` est français).
    Un passage non validant (modèle des séances autre que l'habituel) n'est jamais une référence."""
    runs = sorted(p for p in DATA.glob("*/resultats.json") if p.parent != current
                  and json.loads(p.read_text(encoding="utf-8")).get("langue", DEFAULT_LANGUAGE) == language
                  and json.loads(p.read_text(encoding="utf-8")).get("validant", True))
    if not runs:
        return {}
    data = json.loads(runs[-1].read_text(encoding="utf-8"))
    return {(c["id"], v["critere"]): v["ok"] for c in data["cas"] for v in c["verifications"]}


def previous_statuses(current: Path, language: str = DEFAULT_LANGUAGE) -> dict:
    """Statut de chaque cas au dernier passage complet de la même langue (ni rejugement ni passage partiel) :
    sert à signaler une instabilité qui revient. Un passage sans champ `complet` est complet s'il compte 10 cas ou plus."""
    for path in sorted((p for p in DATA.glob("*/resultats.json") if p.parent != current), reverse=True):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("langue", DEFAULT_LANGUAGE) != language or data.get("rejuge") or not data.get("validant", True):
            continue
        if not data.get("complet", len(data.get("cas", [])) >= 10):
            continue
        return {c["id"]: c.get("statut", "reussi") for c in data["cas"]}
    return {}


def model_label(model: str | None) -> str:
    return model or DEFAULT_MODEL_LABEL


def write_report(stamp: str, results: list[dict], before: dict, base: str, memoire: str = "réelle",
                 language: str = DEFAULT_LANGUAGE, retry_cost: float = 0.0, retry_note: str = "",
                 session_model: str | None = None, judge_model: str | None = None) -> Path:
    total = expected_total(results)
    passed = sum(v["ok"] for c in results for v in blocking(c["verifications"]))
    skipped = [c["id"] for c in results if c.get("non_evaluable")]
    regressions = [(c["id"], v["critere"]) for c in results for v in blocking(c["verifications"])
                   if not v["ok"] and before.get((c["id"], v["critere"])) is True]
    ind = [v for c in results for v in indicators(c["verifications"])]
    lines = [f"# Jeu d'essai des postures, {stamp}", "", f"mémoire : {memoire}"
             + (f" · langue : {language}" if language != DEFAULT_LANGUAGE else ""), "",
             f"modèles : sessions {model_label(session_model)} · juge {model_label(judge_model)}", "",
             f"{passed}/{total} vérifications réussies sur {len(results)} cas"
             + (f", dont {len(skipped)} non évaluable(s)" if skipped else "") + ". "
             f"État testé : {base[:10]}. Traces brutes : {DATA / stamp}.", ""]
    if session_model:
        lines += [f"**Passage non validant** : le modèle des séances ({session_model}) diffère du modèle habituel ; "
                  "ce passage ne sert pas de référence pour les régressions, l'instabilité répétée ni la règle d'acceptation.", ""]
    if skipped:
        lines += [f"**Passage non validant** : {len(skipped)} cas non évaluable(s) ({', '.join(skipped)}) ; le total est calculé sur toutes les "
                  "vérifications bloquantes attendues, et ce passage ne sert pas de référence.", ""]
    if ind:
        lines += [f"Indicateurs non bloquants (rapportés à part, hors du décompte) : {sum(v['ok'] for v in ind)}/{len(ind)} réussis.", ""]
    unstable = [c for c in results if c.get("statut") == "instable"]
    confirmed = [c for c in results if c.get("statut") == "echec_confirme"]
    if unstable or confirmed or retry_cost:
        lines += [f"Rejeux automatiques : {len(unstable)} cas instable(s), {len(confirmed)} échec(s) confirmé(s), "
                  f"coût des rejeux {retry_cost:.2f} $.", ""]
    if retry_note:
        lines += [retry_note, ""]
    if regressions:
        lines += ["## Régressions (réussies au passage précédent)", ""]
        lines += [f"- **{case}** : {criterion}" for case, criterion in regressions] + [""]
    if unstable:
        lines += ["## Cas instables (échec isolé, réussite à tous les rejeux : ne compte pas comme régression)", ""]
        for c in unstable:
            n = len(c.get("rejeux") or []) + 1
            failed = " ; ".join(f"{f['critere']}" for f in c.get("premier_echec") or [])
            lines.append(f"- **{c['id']}** : instable (1 échec sur {n}) : {failed}"
                         + (" · **instable répété** : déjà instable au passage complet précédent" if c.get("instable_repete") else ""))
        lines.append("")
    lines += ["## Synthèse", "", "| Cas | Réussies | Posture | Coût | Tours |", "|---|---|---|---|---|"]
    for c in results:
        ok = sum(v["ok"] for v in blocking(c["verifications"]))
        extra = indicators(c["verifications"])
        shown = f"{ok}/{len(blocking(c['verifications']))}" + (f" (+ indicateurs {sum(v['ok'] for v in extra)}/{len(extra)})" if extra else "") \
            + (" · instable" if c.get("statut") == "instable" else (" · échec confirmé" if c.get("statut") == "echec_confirme" else ""))
        cost = f"{c['cost']:.2f} $" if isinstance(c["cost"], (int, float)) else "?"
        lines.append(f"| {c['id']} | {shown} | {c['posture'] or '—'} | {cost} | {c['turns'] or '?'} |")
    lines.append("")
    for c in results:
        lines += [f"## {c['id']}", "", f"> {c['question']}", ""]
        if c.get("non_evaluable"):
            lines += ["**Non évaluable avec la bibliothèque de cette installation** (prérequis du cas) :"]
            lines += [f"- {reason}" for reason in c["non_evaluable"]] + [""]
            continue
        if c.get("statut") == "instable":
            n = len(c.get("rejeux") or []) + 1
            lines += [f"**Instable (1 échec sur {n})** : échec au premier essai, réussite aux {n - 1} rejeux ; les vérifications "
                      "ci-dessous sont celles du dernier rejeu."
                      + (" **Instable répété** : déjà instable au passage complet précédent." if c.get("instable_repete") else ""), ""]
            lines += [f"- Premier échec : {f['critere']} : {f['justification']}" for f in c.get("premier_echec") or []] + [""]
        elif c.get("statut") == "echec_confirme":
            replays = c.get("rejeux") or []
            lines += [f"**Échec confirmé** : {sum(r['ok'] for r in replays)} rejeu(x) réussi(s) sur {len(replays)} joué(s) "
                      "(le premier rejeu en échec arrête la série).", ""]
        if c["error"]:
            lines += ["**La séance a échoué ou dépassé le délai** : voir la trace brute.", ""]
        if c.get("refus"):
            lines += ["Outils refusés pendant la séance (le comportement peut différer d'une vraie séance) :"]
            lines += [f"- {item}" for item in dict.fromkeys(c["refus"])] + [""]
        for v in c["verifications"]:
            mark = "✅" if v["ok"] else "❌"
            was = before.get((c["id"], v["critere"]))
            change = " (régression)" if was is True and not v["ok"] else (" (corrigé)" if was is False and v["ok"] else "")
            kind = " (indicateur, non bloquant)" if v.get("indicateur") else ""
            lines.append(f"- {mark} {v['critere']}{kind}{change} : {v['justification']}")
        lines.append("")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    target = REPORT_DIR / f"essai-{stamp}.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


# ---------------------------------------------------------------------------

# Anciens noms français des options (lot 2 de la version anglaise) : refusés depuis le lot 8.
OLD_OPTIONS = {"--cas": "--cases", "--modele": "--model", "--juge-modele": "--judge-model", "--garder": "--keep",
               "--memoire-reelle": "--real-memory", "--rejuger": "--rejudge", "--outils": "--tools",
               "--etat-commite": "--committed-state", "--avec-bash": "--with-bash", "--langue": "--language"}


def check_options(argv: list[str]) -> list[str]:
    """Refuse les anciens noms d'options (forme `--cas x` ou `--cas=x`) : arrêt avec le code 2 et le nom actuel."""
    import flux_config
    return flux_config.refuse_old_options(argv, OLD_OPTIONS)


# Anciennes clés françaises de cas.yaml (lot 2 de la version anglaise) : refusées depuis le lot 8.
OLD_CASE_KEYS = {"jugements": "judgements", "prerequis": "prerequisites"}
OLD_CHECK_KEYS = {"outil": "tool", "texte": "text", "sans_texte": "without_text", "memoire_sans": "memory_without"}
OLD_PREREQUISITE_KEYS = {"livre": "book", "sujet_absent": "absent_topic"}


def normalize_cases(cases: list[dict]) -> list[dict]:
    """Contrôle les clés de cas.yaml et rend les cas tels quels. Une ancienne clé française (au niveau du cas, dans une
    variante de langue, dans une vérification ou un prérequis) arrête le chargement (code 2) avec un message qui nomme
    le cas et la clé actuelle, que la clé actuelle soit présente ou non."""
    def refuse(mapping: dict, table: dict, where: str) -> None:
        for key in mapping:
            if key in table:
                print(f"PMZilla Lab, erreur : cas {where} : la clé « {key} » n'existe plus ; utiliser « {table[key]} ».",
                      file=sys.stderr)
                raise SystemExit(2)

    for case in cases:
        where = str(case.get("id", "?"))
        refuse(case, OLD_CASE_KEYS, where)
        for language in LANGUAGES:
            if isinstance(case.get(language), dict):
                refuse(case[language], {"jugements": "judgements", "texte": "text"}, f"{where} ({language})")
        for field, table in (("verifications", OLD_CHECK_KEYS), ("prerequisites", OLD_PREREQUISITE_KEYS)):
            if isinstance(case.get(field), list):
                for item in case[field]:
                    if isinstance(item, dict):
                        refuse(item, table, where)
    return cases


def case_for_language(case: dict, language: str) -> dict | None:
    """Le cas dans la langue demandée. Français : le cas lui-même. Autre langue : le cas avec le bloc de cette langue
    (`en:`) appliqué, ou None s'il n'a pas de variante. Le bloc peut donner `question`, `judgements` et `text` (le motif
    de la règle `text` de ses vérifications) ; le reste du cas est repris tel quel."""
    if language == DEFAULT_LANGUAGE:
        return case
    variant = case.get(language)
    if not isinstance(variant, dict):
        return None
    merged = {key: value for key, value in case.items() if key not in LANGUAGES}
    for key in ("question", "judgements", "cases_fixture"):
        if key in variant:
            merged[key] = variant[key]
    if "text" in variant:
        merged["verifications"] = [{**rule, "text": variant["text"]} if "text" in rule else rule
                                   for rule in merged.get("verifications") or []]
    return merged


def compare_runs(first: Path, second: Path) -> str:
    """Verdicts qui diffèrent entre deux passages (par exemple deux jugements des mêmes traces) : cas, vérification,
    bloquante ou non, verdict de chacun. Ni réponse ni justification : seulement l'écart."""
    runs = []
    for folder in (first, second):
        record = folder / "resultats.json"
        if not record.exists():
            raise SystemExit(f"Passage introuvable ou sans résultats : {folder}")
        runs.append(json.loads(record.read_text(encoding="utf-8")))
    verdicts = [{(c["id"], v["critere"]): v for c in run["cas"] for v in c["verifications"]} for run in runs]
    lines = [f"A : {first.name} · modèles sessions {model_label(runs[0].get('modele_sessions'))}, juge {model_label(runs[0].get('modele_juge'))}",
             f"B : {second.name} · modèles sessions {model_label(runs[1].get('modele_sessions'))}, juge {model_label(runs[1].get('modele_juge'))}", ""]
    shown = lambda v: "—" if v is None else ("réussi" if v["ok"] else "échec")
    differing = []
    for key in dict.fromkeys([*verdicts[0], *verdicts[1]]):
        a, b = verdicts[0].get(key), verdicts[1].get(key)
        if a is None or b is None or a["ok"] != b["ok"]:
            kind = "non bloquante" if (a or b).get("indicateur") else "bloquante"
            differing.append(f"- {key[0]} · {key[1]} · {kind} · A {shown(a)} · B {shown(b)}")
    common = len(set(verdicts[0]) & set(verdicts[1]))
    lines += [f"{len(differing)} verdict(s) différent(s) sur {common} vérification(s) communes ou absentes d'un côté."] + differing
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Jeu d'essai des postures de PMZilla Lab")
    parser.add_argument("--cases", help="identifiants des cas à jouer, séparés par des virgules (défaut : tous)")
    parser.add_argument("--cases-file", metavar="FICHIER",
                        help="fichier de cas à la place de tests/postures/cas.yaml (par exemple tests/postures/cas-commandes.yaml, "
                             "les cas des commandes slash, rapportés à part du décompte)")
    parser.add_argument("--model", help="modèle des séances testées (défaut : celui de Claude Code, le modèle habituel) ; "
                                        "un autre modèle rend le passage non validant")
    parser.add_argument("--judge-model", help=f"modèle du juge (défaut : {DEFAULT_JUDGE_MODEL}) ; avec --rejudge, "
                                              "rejuge les traces d'un passage avec ce juge")
    parser.add_argument("--keep", action="store_true", help="garder les copies temporaires pour inspection")
    parser.add_argument("--real-memory", action="store_true",
                        help="tester avec la mémoire réelle des postures au lieu de la mémoire figée de tests/postures/memoire/")
    parser.add_argument("--retries", type=int, default=2, metavar="N",
                        help="rejeux d'un cas dont une vérification bloquante échoue (défaut 2, 0 pour désactiver) : "
                             "il est instable s'il réussit tous les rejeux, en échec confirmé sinon")
    parser.add_argument("--max-retried-cases", type=int, default=3, metavar="N",
                        help="au-delà de N cas en échec dans le passage, aucun rejeu (échec massif ; défaut 3)")
    parser.add_argument("--rejudge", metavar="AAAA-MM-JJ-HHMMSS",
                        help="rejouer seulement les vérifications et le juge sur les traces d'un passage, "
                             "sans nouvelle séance (après une modification de cas.yaml ou du juge)")
    parser.add_argument("--compare", nargs=2, metavar=("A", "B"),
                        help="comparer deux passages (AAAA-MM-JJ-HHMMSS) et lister les verdicts qui diffèrent : cas, "
                             "vérification, bloquante ou non, sans texte de réponse (calibration du juge), sans rien relancer")
    parser.add_argument("--tools", metavar="AAAA-MM-JJ-HHMMSS",
                        help="afficher les outils appelés dans chaque séance d'un passage (commandes Bash, "
                             "skills, recherches), sans rien relancer")
    parser.add_argument("--committed-state", action="store_true",
                        help="tester le dernier commit, sans les modifications en cours (lancement automatique)")
    parser.add_argument("--with-bash", action="store_true",
                        help="autoriser Bash pendant les séances (si le rapport signale des refus de Bash)")
    parser.add_argument("--prerequisites-only", action="store_true",
                        help="vérifier seulement les prérequis des cas du fichier choisi contre la base de l'installation : "
                             "aucune séance, aucun juge, aucun rapport ; code de sortie 0 si tous sont satisfaits, 1 sinon")
    parser.add_argument("--language", choices=LANGUAGES, default=DEFAULT_LANGUAGE,
                        help="langue des cas : fr (défaut, comportement d'avant) ou en (ne rejoue que les cas qui ont une variante `en:`)")
    refuse_backend_option(sys.argv[1:])
    args = parser.parse_args(check_options(sys.argv[1:]))

    if args.tools:
        show_tools(DATA / args.tools)
        return
    if args.compare:
        print(compare_runs(DATA / args.compare[0], DATA / args.compare[1]))
        return
    args.judge_model = args.judge_model or DEFAULT_JUDGE_MODEL
    if args.rejudge and args.model:
        raise SystemExit("--model ne s'applique pas à --rejudge (aucune séance n'est rejouée) ; "
                         "le modèle des séances est celui du passage rejugé. Utiliser --judge-model.")
    cases_file = CASES_FILE
    if args.cases_file:      # relatif : depuis la racine du workspace
        cases_file = WORKSPACE / Path(args.cases_file).expanduser()
    if not cases_file.exists():
        raise SystemExit(f"Cas introuvables : {cases_file}")
    cases = normalize_cases(yaml.safe_load(cases_file.read_text(encoding="utf-8")))
    if args.cases:
        wanted = {x.strip() for x in args.cases.split(",")}
        unknown = wanted - {c["id"] for c in cases}
        if unknown:
            raise SystemExit(f"Cas inconnus : {', '.join(sorted(unknown))}")
        cases = [c for c in cases if c["id"] in wanted]
    language = args.language
    if language != DEFAULT_LANGUAGE:   # les cas sans variante dans cette langue sont listés, pas rejoués
        variants = [(c, case_for_language(c, language)) for c in cases]
        without = [c["id"] for c, variant in variants if variant is None]
        if without:
            print(f"Cas sans variante {language} : {', '.join(without)}")
        cases = [variant for _, variant in variants if variant is not None]
        if not cases:
            print(f"Aucun cas n'a de variante {language} : rien à rejouer.")
            return

    if args.prerequisites_only:      # aucune séance, aucune base jetable, aucun rapport
        if check_prerequisites_only(cases):
            raise SystemExit(1)
        return
    check_fixtures(cases)
    cases_db = None if args.rejudge else create_cases_database()    # un rejugement ne crée aucune base
    try:
        run(args, cases, language, cases_db)
    finally:
        if cases_db:
            drop_cases_database(cases_db)


def run(args, cases: list[dict], language: str, cases_db: str | None) -> None:
    """Le passage : séances, vérifications, jugement, rapport. `cases_db` : base de cas jetable (None : indisponible, ou rejugement)."""
    cases_env = None if args.rejudge else cases_environment(cases_db)
    lock = None if args.rejudge else lock_pass(DATA)   # gardé ouvert jusqu'à la fin du passage
    stamp = dt.datetime.now().strftime("%Y-%m-%d-%H%M%S")
    folder = DATA / stamp
    folder.mkdir(parents=True, exist_ok=True)
    mcp = mcp_config(folder, cases_env=cases_env)
    status_before = git("status", "--porcelain", "--untracked-files=all")
    source = None
    if args.rejudge:
        source = DATA / args.rejudge
        if not source.is_dir():
            raise SystemExit(f"Passage introuvable : {source}")
        previous = source / "resultats.json"
        previous_data = json.loads(previous.read_text(encoding="utf-8")) if previous.exists() else {}
        base = previous_data.get("base", "?")
        memoire = previous_data.get("memoire", "réelle")   # les passages d'avant la mémoire figée utilisaient la mémoire réelle
        session_model = previous_data.get("modele_sessions")   # un rejugement garde le modèle (et le statut) des séances rejugées
        validant = previous_data.get("validant", True)
    elif args.committed_state:
        base = git("rev-parse", "HEAD").strip()
    else:
        base = snapshot_commit()
    if not args.rejudge:
        memoire = "réelle" if args.real_memory else "figée"
        session_model = args.model
        validant = not args.model      # un autre modèle que l'habituel ne valide rien
    results = []
    sanctum_before = None if source else sanctum_digest()

    def evaluate(case: dict, attempt: int = 0, library_mcp: Path | None = None) -> dict | None:
        """Une séance du cas (ou son rejeu numéro `attempt`) et ses vérifications ; None sans trace à rejuger. `library_mcp` :
        configuration de la bibliothèque jetable déjà indexée pour la première séance ; un rejeu la réindexe (un autre cas a pu
        remplir la base jetable entre-temps)."""
        nonlocal sanctum_before
        label = case["id"] + (f".rejeu{attempt}" if attempt else "")
        technical = False      # exception de préparation ou de séance : un incident, pas une variation du modèle
        if source:
            events, files = saved_session(source, case["id"])
            if events is None:
                print("    pas de trace pour ce cas dans le passage indiqué, ignoré")
                return None
            trace = read_trace(events)
        else:
            copy = folder / f"copie-{label}"
            try:
                make_copy(copy, base, untracked=not args.committed_state)
                placed = prepare_memory(copy, args.real_memory, language)
                place_files(case, copy)
                if cases_db:
                    reset_cases_database(cases_db, WORKSPACE / case["cases_fixture"] if case.get("cases_fixture") else None)
                if library_mcp is None:
                    library_mcp = case_library(case, folder, cases_env, cases_db)
                events = run_session(case["question"], copy, library_mcp or mcp, args.model,
                                     folder / f"{label}.jsonl",
                                     args.with_bash, language, env=cases_env)
                trace = read_trace(events)
                files = changed_files(copy, placed)
            except Exception as error:   # un cas qui plante est un échec du cas, pas la fin du passage
                print(f"    ERREUR : {type(error).__name__} : {error}", flush=True)
                events, files = [], {}
                trace = read_trace([])
                trace["error"] = f"{type(error).__name__} : {error}"
                technical = True
            finally:
                if not args.keep:
                    drop_copy(copy)
            (folder / f"{label}.fichiers.json").write_text(
                json.dumps(files, ensure_ascii=False, indent=2), encoding="utf-8")
        checks = [check_posture(case.get("posture"), trace, language)]
        if sanctum_before is not None and sanctum_digest() != sanctum_before:
            # une séance ne doit jamais écrire dans le sanctum réel : c'est un échec, et on repart de l'état modifié
            print("    ATTENTION : le sanctum réel a changé pendant ce cas", flush=True)
            checks.append({"critere": SANCTUM_CRITERION, "ok": False,
                           "justification": "le sanctum réel (_bmad/memory/) a été modifié pendant ce cas : la séance a écrit hors de sa copie"})
            sanctum_before = sanctum_digest()
        checks += [check_auto(rule, trace, files) for rule in case.get("verifications") or []]
        checks.append(check_language_formulas(trace, language))
        checks.append(check_single_final(trace))
        checks.append(check_tag_placement(case.get("posture"), trace, language))
        checks += judge(case, trace, args.judge_model, folder, language)
        checks = [c for c in checks if c]
        found = posture_tags(trace["all_text"], language) or list(dict.fromkeys(m.strip() for m in POSTURE_TAG.findall(trace["all_text"])))
        return {"id": case["id"], "question": case["question"], "verifications": checks,
                        "posture": ", ".join(found), "cost": trace["cost"], "turns": trace["turns"],
                        "error": trace["error"] or not events, "fichiers_ecrits": sorted(files),
                        "refus": trace["denied"], "erreur_technique": technical}

    for number, case in enumerate(cases, 1):
        print(f"[{number}/{len(cases)}] {case['id']} …", flush=True)
        started = time.time()
        unmet, library_mcp = [], None
        if not source and case.get("library"):     # la bibliothèque jetable d'abord : ses prérequis se lisent dans la base jetable
            try:
                library_mcp = case_library(case, folder, cases_env, cases_db)
            except LibraryUnavailable as error:
                unmet = [str(error)]
        if not source and not unmet:
            unmet = unmet_prerequisites(case.get("prerequisites"), dbname=cases_db if case.get("library") else None)
        if not source and case.get("cases_fixture") and not cases_db:
            unmet = [*unmet, CASES_UNAVAILABLE]
        if unmet:
            print(f"    non évaluable ici : {'; '.join(unmet)}")
            results.append({"id": case["id"], "question": case["question"], "verifications": [], "posture": "",
                            "cost": None, "turns": None, "error": False, "fichiers_ecrits": [], "refus": [],
                            "non_evaluable": unmet, "bloquantes_attendues": blocking_count(case)})
            continue
        entry = evaluate(case, library_mcp=library_mcp)
        if entry is None:
            continue
        results.append(entry)
        checks = entry["verifications"]
        ok = sum(c["ok"] for c in blocking(checks))
        extra = indicators(checks)
        print(f"    {ok}/{len(blocking(checks))}" + (f" (+ indicateurs {sum(c['ok'] for c in extra)}/{len(extra)})" if extra else "")
              + f" · {time.time() - started:.0f} s", flush=True)

    retry_cost, retry_note = 0.0, ""
    for entry in results:
        entry["statut"] = "reussi"
    if not source and args.retries > 0:
        failing = [r for r in results if not r.get("non_evaluable") and not r.get("erreur_technique")
                   and any(not v["ok"] for v in blocking(r["verifications"]))
                   and not any(v["critere"] == SANCTUM_CRITERION and not v["ok"] for v in r["verifications"])]
        if len(failing) > args.max_retried_cases:
            retry_note = (f"Aucun rejeu : {len(failing)} cas en échec, plus que le plafond de {args.max_retried_cases} "
                          f"(--max-retried-cases) ; un échec massif n'est pas du bruit.")
            print(retry_note)
        for entry in ([] if retry_note else failing):
            case = next(c for c in cases if c["id"] == entry["id"])
            replays, last_ok = [], None
            for attempt in range(1, args.retries + 1):
                print(f"[rejeu {attempt}/{args.retries}] {case['id']} …", flush=True)
                again = evaluate(case, attempt)
                passed_again = again is not None and not any(not v["ok"] for v in blocking(again["verifications"]))
                cost = again["cost"] if again and isinstance(again.get("cost"), (int, float)) else 0.0
                replays.append({"ok": passed_again, "cout": cost})
                retry_cost += cost
                if not passed_again:
                    break                    # un rejeu en échec suffit : l'échec est confirmé, inutile de payer le suivant
                last_ok = again
            entry["rejeux"] = replays
            if len(replays) == args.retries and all(r["ok"] for r in replays):
                entry["statut"] = "instable"
                entry["premier_echec"] = [{"critere": v["critere"], "justification": v["justification"]}
                                          for v in blocking(entry["verifications"]) if not v["ok"]]
                entry["verifications"] = last_ok["verifications"]      # compté comme réussi, avec la mention « instable »
                entry["tours_rejeu"] = last_ok["turns"]
            else:
                entry["statut"] = "echec_confirme"
            print(f"    {entry['statut']} : {sum(r['ok'] for r in replays)}/{len(replays)} rejeu(x) réussi(s)", flush=True)
    for entry in results:                  # échec non rejoué (rejeux désactivés, plafond, incident, sanctum touché)
        if entry["statut"] == "reussi" and any(not v["ok"] for v in blocking(entry["verifications"])):
            entry["statut"] = "echec"
    last_statuses = {} if source else previous_statuses(folder, language)
    for entry in results:
        if entry["statut"] == "instable":
            entry["instable_repete"] = last_statuses.get(entry["id"]) == "instable"
    before = previous_results(folder, language)
    non_evaluables = [c["id"] for c in results if c.get("non_evaluable")]
    if non_evaluables:
        validant = False         # un cas non évaluable ne valide rien : le total attendu n'a pas été joué en entier
    (folder / "resultats.json").write_text(
        json.dumps({"date": stamp, "base": base, "memoire": memoire, "langue": language, "cas": results,
                    "complet": not args.cases and not args.cases_file, "rejuge": bool(source),
                    "modele_sessions": session_model, "modele_juge": args.judge_model, "validant": validant,
                    "non_evaluables": non_evaluables, "cout_rejeux": round(retry_cost, 4)},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    report = write_report(stamp, results, before, base, memoire, language, retry_cost, retry_note,
                          session_model, args.judge_model)
    def outside_reports(status: str) -> list[str]:
        return [line for line in status.splitlines() if "_bmad-output/essais" not in line]
    if outside_reports(git("status", "--porcelain", "--untracked-files=all")) != outside_reports(status_before):
        print("Attention : le workspace a changé pendant l'essai, vérifiez git status.")
    total = expected_total(results)
    passed = sum(v["ok"] for c in results for v in blocking(c["verifications"]))
    regressions = sum(1 for c in results for v in blocking(c["verifications"])
                      if not v["ok"] and before.get((c["id"], v["critere"])) is True)
    ind = [v for c in results for v in indicators(c["verifications"])]
    print(f"\n{passed}/{total} vérifications réussies · rapport : {report}")
    if ind:
        print(f"Indicateurs non bloquants (hors du décompte) : {sum(v['ok'] for v in ind)}/{len(ind)} réussis")
    unstable = sum(1 for c in results if c.get("statut") == "instable")
    confirmed = sum(1 for c in results if c.get("statut") == "echec_confirme")
    extra = (f" · {unstable} instable(s)" if unstable else "") + (f" · {confirmed} échec(s) confirmé(s)" if confirmed else "") \
        + (f" · rejeux {retry_cost:.2f} $" if retry_cost else "")
    skipped_label = f" · {len(non_evaluables)} non évaluable(s) · passage non validant" if non_evaluables else ""
    print(f"BILAN {passed}/{total}{skipped_label} · {regressions} régression(s){extra} · {report}")
    if non_evaluables:
        print(f"Cas non évaluables : {', '.join(non_evaluables)} (code de sortie {EXIT_NOT_VALIDATING}).")
        raise SystemExit(EXIT_NOT_VALIDATING)


if __name__ == "__main__":
    main()
