"""
PMZilla Lab : couche d'accès du module des cas (schéma cases, db-lot2, design.md 2 et 3).

Module de bibliothèque, sans ligne de commande. Il n'ouvre aucune connexion à l'import et n'importe, au niveau du module, que la
bibliothèque standard, hybrid_search et sensitive_names ; tout le reste (db, pmzilla_lab_library, yaml, httpx) est importé à l'usage.
Chaque fonction prend une connexion (les écritures acceptent aussi une fonction qui en ouvre une, appelée seulement après les
refus qui ne demandent pas la base) et, pour les écritures, une fonction `embed(texte) -> vecteur` : les tests injectent des fausses.

    connect_cases(role)                      connexion sous pmzilla_cases_ro ou pmzilla_cases (PMZILLA_LAB_CASES_DBNAME)
    search_cases / search_experiments        recherche hybride (celle de la bibliothèque), seuil de similarité, jamais d'écriture
    due_reviews / running_experiments / show_experiment
    start_experiment / add_note / postpone / drop / close_experiment     écritures, une transaction chacune
    validate_start_draft / validate_note_draft / validate_close_draft   validation pure des brouillons (design.md 3.4)
    resolve_author / require_author          auteur local (variable, puis .pmzilla/cases.yaml)
    CasesReader                              lecteur paresseux du serveur MCP (lecture seule)
    load_fixture                             charge un jeu d'essai inventé (évaluation), sans garde des noms sensibles

Les messages de CasesError ne contiennent jamais de mot de passe ni de nom sensible ; `code` et `field` permettent aux appelants
(journal, serveur MCP) de choisir leur propre message. Les écritures lèvent aussi SensitiveNamesUnavailable (liste des noms
absente, illisible ou vide) avant toute connexion.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import json
import os
import re
from pathlib import Path

import hybrid_search
import lab_paths
import sensitive_names
from hybrid_search import HybridSpec

RACINE = Path(__file__).resolve().parents[1]

DEFAULT_REVIEW_WEEKS = 6
MAX_POSTPONEMENTS = 2
# Seuil de similarité (produit scalaire) provisoire, calibré le 2026-10-09 sur le jeu d'essai inventé par tools/cases_calibration.py
# (design.md 3.7) : low 0.554 (non lié le plus haut), high 0.632 (lié le plus bas), valeur = milieu 0.593 arrondi vers le bas.
# Provisoire, recalibré après les dix premiers vrais cas ; à relancer si un texte de fixture ou l'une des trois questions change.
MIN_SIMILARITY: float | None = 0.59
DEFAULT_LIMIT = 3
MAX_LIMIT = 10
MAX_TEXT_LENGTH = 600   # au-delà, ce n'est plus une note de journal : résumer (ex-journal_lab.LONGUEUR_MAX)

AUTHOR_VARIABLE = "PMZILLA_LAB_CASES_AUTHOR"
DBNAME_VARIABLE = "PMZILLA_LAB_CASES_DBNAME"
ROLE_READ = "pmzilla_cases_ro"
ROLE_WRITE = "pmzilla_cases"

POSTURES = ("discovery", "delivery", "scaling", "facilitation", "none")
OUTCOMES = ("worked", "partly", "failed", "dropped")
CONFIDENCES = ("low", "medium", "high")
STATUSES = ("running", "closed", "dropped")
CONTEXT_KEYS = ("team_type", "team_size", "phase")
DURATION = re.compile(r"^[1-9][0-9]*[dw]$")

START_KEYS = ("problem", "context", "hypotheses", "chosen_path", "references_used", "tested", "expected_signal",
              "success_criterion", "review_due", "posture", "date")
NOTE_KEYS = ("note", "date")
CLOSE_KEYS = ("outcome", "what_got_stuck", "confidence", "drop_reason", "date")

# Recherche : les deux spécifications de design.md 3.2. Aucune expression de date, de collection ni de type : bonus de fraîcheur neutre,
# aucun filtre. Limite connue et acceptée : pour les expériences, le filtre « running » est dans la portée, donc il s'applique après la limite
# de candidats BM25 (la bibliothèque, elle, filtre collection et date avant la limite : change filter-before-keyword-limit) ; les tables sont petites.
CASES_SPEC = HybridSpec(
    from_sql="cases.cases c", id_expr="c.id", vector_expr="c.embedding", tsvector_expr=None,
    bm25_table_sql="cases.cases c", bm25_text_expr="c.fts_text", bm25_id_expr="c.id")
EXPERIMENTS_SPEC = HybridSpec(
    from_sql="(SELECT * FROM cases.experiments WHERE status = 'running' AND embedding IS NOT NULL) e",
    id_expr="e.id", vector_expr="e.embedding", tsvector_expr=None,
    bm25_table_sql="cases.experiments e", bm25_text_expr="e.fts_text", bm25_id_expr="e.id")


class CasesError(Exception):
    """Refus du module des cas. `code` : identifiant stable du refus ; `field` : champ ou numéro concerné (jamais un nom sensible)."""

    def __init__(self, message, code=None, field=None):
        super().__init__(message)
        self.code = code
        self.field = field


# ---------------------------------------------------------------------------
# Connexion, auteur, embedding
# ---------------------------------------------------------------------------

def connect_cases(role, timeout=None):
    """Seul point de connexion du module : PMZILLA_LAB_CASES_DBNAME (facultatif) remplace la base de l'adresse."""
    import db
    return db.connect(role=role, dbname=os.environ.get(DBNAME_VARIABLE) or None,
                      timeout=db.DELAI_CONNEXION if timeout is None else timeout)


def default_workspace() -> Path:
    return lab_paths.resolve_or_exit()["content_root"]   # module partagé : variable, sinon dépôt Git du code, sinon code 78 (R-77)


def resolve_author(workspace=None, environ=None):
    """PMZILLA_LAB_CASES_AUTHOR si non vide, sinon la clé `author` de .pmzilla/cases.yaml ; None si aucun des deux (fichier illisible compris)."""
    env = os.environ if environ is None else environ
    value = (env.get(AUTHOR_VARIABLE) or "").strip()
    if value:
        return value
    # registre des fichiers locaux de tools/lab_paths.py (décision du 2026-10-21, A9), sous l'espace donné ou la racine de contenu
    path = lab_paths.local_file("cases_author", Path(workspace) if workspace is not None else default_workspace(), env)
    try:
        import yaml
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict) or data.get("author") is None:
        return None
    return str(data["author"]).strip() or None


def author_file_label() -> str:
    """Chemin relatif du fichier de l'auteur, tel que le registre des fichiers locaux de tools/lab_paths.py le déclare (seule source)."""
    return Path(*lab_paths.LOCAL_FILES["cases_author"][0]).as_posix()


def require_author(workspace=None, environ=None):
    author = resolve_author(workspace, environ)
    if not author:
        fichier = author_file_label()
        raise CasesError(f"no author configured: set {AUTHOR_VARIABLE} or the key `author` of {fichier}",
                         code="author_missing", field=fichier)
    return author


def default_embed(text):
    """Vecteur L2-normalisé de la fonction d'embedding de la bibliothèque (bge-m3 par Ollama). Import tardif : le serveur MCP n'est pas chargé."""
    import pmzilla_lab_library
    return pmzilla_lab_library.embed([text])[0]


def _embed(embed, text):
    """Appelle `embed(text)` ; Ollama absent ou modèle inconnu devient un refus (rien n'est écrit)."""
    try:
        import httpx
        http_errors = (httpx.HTTPError,)
    except ImportError:
        http_errors = ()
    try:
        return (embed or default_embed)(text)
    except SystemExit:
        raise CasesError("the embedding service must run: Ollama does not know the embedding model", code="embedding_unavailable") from None
    except http_errors:
        raise CasesError("the embedding service must run: Ollama does not answer", code="embedding_unavailable") from None


def embedding_text(problem, chosen_path, tested) -> str:
    return problem + "\n" + (chosen_path or "") + "\n" + tested


# ---------------------------------------------------------------------------
# Validation des brouillons (design.md 3.4)
# ---------------------------------------------------------------------------

def _unknown_keys(raw, allowed):
    if not isinstance(raw, dict):
        raise CasesError("the draft must be a mapping", code="draft_not_mapping")
    unknown = sorted(str(k) for k in raw if k not in allowed)
    if unknown:
        raise CasesError("unknown key: " + ", ".join(unknown), code="unknown_key", field=", ".join(unknown))


def _text(value, field, required=False):
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise CasesError(f"missing field: {field}", code="field_missing", field=field)
        return None
    if not isinstance(value, str):
        raise CasesError(f"field {field} must be text", code="field_type", field=field)
    value = value.strip()
    if len(value) > MAX_TEXT_LENGTH:
        raise CasesError(f"field {field} is longer than {MAX_TEXT_LENGTH} characters", code="field_too_long", field=field)
    return value


def _text_list(value, field):
    if value is None:
        return None
    if not isinstance(value, list):
        raise CasesError(f"field {field} must be a list of text", code="field_type", field=field)
    items = [_text(v, field, required=True) for v in value]
    return items or None


def _date(value, field):
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        raise CasesError(f"field {field} is not a date (YYYY-MM-DD)", code="date_invalid", field=field) from None


def _choice(value, field, allowed, required=False):
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise CasesError(f"missing field: {field}", code="field_missing", field=field)
        return None
    if not isinstance(value, str) or value.strip() not in allowed:
        raise CasesError(f"field {field} must be one of: {', '.join(allowed)}", code="field_value", field=field)
    return value.strip()


def _context(value):
    if not isinstance(value, dict) or not value:
        raise CasesError("field context must be a mapping with at least one of: " + ", ".join(CONTEXT_KEYS),
                         code="field_missing" if not value else "field_type", field="context")
    unknown = sorted(str(k) for k in value if k not in CONTEXT_KEYS)
    if unknown:
        raise CasesError("unknown context key: " + ", ".join(unknown), code="unknown_key", field="context")
    out = {}
    for key, item in value.items():
        if isinstance(item, bool) or not isinstance(item, (str, int, float)):
            raise CasesError(f"field context.{key} must be text", code="field_type", field=f"context.{key}")
        out[key] = _text(str(item), f"context.{key}", required=True)
    return out


def _description(raw):
    """Les champs de description communs au brouillon de lancement et au jeu d'essai (design.md 3.4 et 7.2)."""
    return {
        "problem": _text(raw.get("problem"), "problem", required=True),
        "context": _context(raw.get("context")),
        "hypotheses": _text_list(raw.get("hypotheses"), "hypotheses"),
        "chosen_path": _text(raw.get("chosen_path"), "chosen_path"),
        "references_used": _text_list(raw.get("references_used"), "references_used"),
        "tested": _text(raw.get("tested"), "tested", required=True),
        "expected_signal": _text(raw.get("expected_signal"), "expected_signal", required=True),
        "success_criterion": _text(raw.get("success_criterion"), "success_criterion", required=True),
        "posture": _choice(raw.get("posture"), "posture", POSTURES),
    }


def _check_names(fields, names):
    """Refuse le premier champ qui contient un nom listé ; le message ne nomme que le champ."""
    flat = {}
    for key, value in fields.items():
        if isinstance(value, dict):
            flat.update({f"{key}.{k}": v for k, v in value.items()})
        elif isinstance(value, list):
            flat[key] = "\n".join(value)
        elif value is not None:
            flat[key] = value
    found = sensitive_names.find_field(flat, names)
    if found:
        raise CasesError(f"a sensitive name is written in field {found}", code="sensitive_name", field=found)


def _names(names):
    """La liste donnée, sinon celle du fichier (SensitiveNamesUnavailable si absente, illisible ou vide)."""
    return list(names) if names is not None else sensitive_names.load_names()


def validate_start_draft(draft, today, names):
    """Brouillon de lancement validé : dictionnaire normalisé (dates en datetime.date, review_due par défaut calculée)."""
    _unknown_keys(draft, START_KEYS)
    out = _description(draft)
    started = _date(draft["date"], "date") if draft.get("date") is not None else today
    if started > today:
        raise CasesError("field date is in the future", code="date_future", field="date")
    if draft.get("review_due") is not None:
        review = _date(draft["review_due"], "review_due")
        if review < today:
            raise CasesError("field review_due is in the past", code="date_past", field="review_due")
    else:
        review = started + dt.timedelta(weeks=DEFAULT_REVIEW_WEEKS)
    out["started_on"], out["review_due"] = started, review
    _check_names(out, names)
    return out


def validate_note_draft(draft, today, names):
    _unknown_keys(draft, NOTE_KEYS)
    note = _text(draft.get("note"), "note", required=True)
    noted = _date(draft["date"], "date") if draft.get("date") is not None else today
    if noted > today:
        raise CasesError("field date is in the future", code="date_future", field="date")
    _check_names({"note": note}, names)
    return {"note": note, "noted_on": noted}


def validate_close_draft(draft, today, names, started_on=None):
    _unknown_keys(draft, CLOSE_KEYS)
    outcome = _choice(draft.get("outcome"), "outcome", OUTCOMES, required=True)
    reason = _text(draft.get("drop_reason"), "drop_reason")
    if outcome == "dropped" and not reason:
        raise CasesError("field drop_reason is required when outcome is dropped", code="field_missing", field="drop_reason")
    if outcome != "dropped" and reason:
        raise CasesError("field drop_reason is only for the outcome dropped", code="field_value", field="drop_reason")
    reviewed = _date(draft["date"], "date") if draft.get("date") is not None else today
    if reviewed > today:
        raise CasesError("field date is in the future", code="date_future", field="date")
    if started_on is not None and reviewed < started_on:
        raise CasesError("field date is before the start of the experiment", code="date_before_start", field="date")
    out = {"outcome": outcome, "drop_reason": reason, "what_got_stuck": _text(draft.get("what_got_stuck"), "what_got_stuck"),
           "confidence": _choice(draft.get("confidence"), "confidence", CONFIDENCES), "reviewed_on": reviewed}
    _check_names(out, names)
    return out


def parse_duration(duration):
    """`2w` ou `10d` : nombre de jours. Autre forme : CasesError."""
    if not isinstance(duration, str) or not DURATION.match(duration):
        raise CasesError("duration must be a number of days or weeks, such as 10d or 2w", code="duration_invalid", field="duration")
    return int(duration[:-1]) * (7 if duration[-1] == "w" else 1)


def _limit(limit):
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise CasesError("limit must be an integer", code="limit_invalid", field="limit")
    return max(1, min(limit, MAX_LIMIT))


def _number(number):
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise CasesError(f"experiment number {number!r} is not valid", code="number_invalid", field=str(number))
    return number


def _author(author):
    if not isinstance(author, str) or not author.strip():
        raise CasesError("no author configured", code="author_missing")
    return author.strip()


def _iso(value):
    return value.isoformat() if isinstance(value, dt.date) else value


# ---------------------------------------------------------------------------
# Écritures : une transaction, rien d'écrit en cas d'échec
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def _transaction(conn):
    """Curseur d'une transaction validée à la sortie, annulée sur toute erreur. `conn` : connexion, ou fonction qui en ouvre une (fermée ensuite)."""
    opened = callable(conn)
    connection = conn() if opened else conn
    try:
        with connection.cursor() as cursor:
            yield cursor
        connection.commit()
    except Exception as error:
        with contextlib.suppress(Exception):
            connection.rollback()
        if isinstance(error, CasesError) or type(error).__module__.split(".")[0] != "psycopg":
            raise
        # une erreur de la base peut citer la ligne refusée : on ne garde que son nom et son code
        raise CasesError(f"the database refused the write ({type(error).__name__}, sqlstate {getattr(error, 'sqlstate', None)})",
                         code="database_refused") from None
    finally:
        if opened:
            with contextlib.suppress(Exception):
                connection.close()


def _json(value):
    return None if value is None else json.dumps(value, ensure_ascii=False)


def _vector(embedding):
    return hybrid_search.vector_literal(embedding)


def _insert_experiment(cursor, e, embedding, status="running"):
    cursor.execute(
        "INSERT INTO cases.experiments (author, started_on, posture, status, problem, context, hypotheses, chosen_path, references_used, "
        "tested, expected_signal, success_criterion, review_due, embedding) "
        "VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb, %s, %s, %s, %s, %s::halfvec) RETURNING id",
        (e["author"], e["started_on"], e["posture"], status, e["problem"], _json(e["context"]), _json(e["hypotheses"]), e["chosen_path"],
         _json(e["references_used"]), e["tested"], e["expected_signal"], e["success_criterion"], e["review_due"], _vector(embedding)))
    return cursor.fetchone()[0]


def start_experiment(conn, embed, draft, author, today, names=None) -> int:
    """Crée l'expérience (running) et rend son numéro. Ordre : liste des noms, validation, embedding, puis seulement la base."""
    author = _author(author)
    clean = validate_start_draft(draft, today, _names(names))
    embedding = _embed(embed, embedding_text(clean["problem"], clean["chosen_path"], clean["tested"]))
    with _transaction(conn) as cursor:
        return _insert_experiment(cursor, {**clean, "author": author}, embedding)


def _lock(cursor, number, author):
    """Ligne verrouillée d'une expérience en cours de l'auteur ; sinon CasesError sans rien écrire."""
    cursor.execute("SELECT author, status, started_on FROM cases.experiments WHERE id = %s FOR UPDATE", (number,))
    row = cursor.fetchone()
    if row is None:
        raise CasesError(f"unknown experiment number {number}", code="unknown_experiment", field=str(number))
    if row[0] != author:
        raise CasesError(f"experiment {number} does not belong to the configured author", code="not_author", field=str(number))
    if row[1] != "running":
        raise CasesError(f"experiment {number} is not running", code="not_running", field=str(number))
    return row


def add_note(conn, number, note, noted_on, author, today=None, names=None) -> None:
    number, author = _number(number), _author(author)
    today = today or dt.date.today()
    clean = validate_note_draft({"note": note, **({"date": noted_on} if noted_on is not None else {})}, today, _names(names))
    with _transaction(conn) as cursor:
        started_on = _lock(cursor, number, author)[2]
        if clean["noted_on"] < started_on:
            raise CasesError("the note date is before the start of the experiment", code="date_before_start", field="date")
        cursor.execute("INSERT INTO cases.experiment_notes (experiment_id, noted_on, note) VALUES (%s, %s, %s)",
                       (number, clean["noted_on"], clean["note"]))


def postpone(conn, number, duration, author, today) -> dict:
    """Nouvelle date de bilan : {review_due, postponements}. La troisième reprise est refusée (close ou drop)."""
    number, author = _number(number), _author(author)
    days = parse_duration(duration)
    with _transaction(conn) as cursor:
        _lock(cursor, number, author)
        cursor.execute("SELECT postponements FROM cases.experiments WHERE id = %s", (number,))
        count = cursor.fetchone()[0]
        if count >= MAX_POSTPONEMENTS:
            raise CasesError(f"experiment {number} was already postponed {MAX_POSTPONEMENTS} times: close it or drop it",
                             code="postponement_limit", field=str(number))
        review = today + dt.timedelta(days=days)
        cursor.execute("UPDATE cases.experiments SET review_due = %s, postponements = postponements + 1 WHERE id = %s", (review, number))
    return {"review_due": review.isoformat(), "postponements": count + 1}


def drop(conn, number, author) -> None:
    """Abandon sans leçon : statut dropped, aucun cas."""
    number, author = _number(number), _author(author)
    with _transaction(conn) as cursor:
        _lock(cursor, number, author)
        cursor.execute("UPDATE cases.experiments SET status = 'dropped' WHERE id = %s", (number,))


def close_experiment(conn, number, draft, author, today, names=None) -> int:
    """Crée le cas (copie de l'expérience, notes en historique, même embedding), clôt l'expérience, rend le numéro du cas."""
    number, author = _number(number), _author(author)
    loaded = _names(names)
    validate_close_draft(draft, today, loaded)       # refus sans base ; la date contre le lancement est revérifiée une fois la ligne lue
    with _transaction(conn) as cursor:
        started_on = _lock(cursor, number, author)[2]
        clean = validate_close_draft(draft, today, loaded, started_on=started_on)
        cursor.execute(
            "INSERT INTO cases.cases (experiment_id, author, posture, problem, context, hypotheses, chosen_path, references_used, tested, "
            "expected_signal, success_criterion, launched_on, reviewed_on, history, outcome, drop_reason, what_got_stuck, confidence, embedding) "
            "SELECT e.id, e.author, e.posture, e.problem, e.context, e.hypotheses, e.chosen_path, e.references_used, e.tested, e.expected_signal, "
            "e.success_criterion, e.started_on, %s::date, "
            "COALESCE((SELECT jsonb_agg(jsonb_build_object('noted_on', to_char(n.noted_on, 'YYYY-MM-DD'), 'note', n.note) ORDER BY n.noted_on, n.id) "
            "FROM cases.experiment_notes n WHERE n.experiment_id = e.id), '[]'::jsonb), %s::text, %s::text, %s::text, %s::text, e.embedding "
            "FROM cases.experiments e WHERE e.id = %s RETURNING id",
            (clean["reviewed_on"], clean["outcome"], clean["drop_reason"], clean["what_got_stuck"], clean["confidence"], number))
        case_number = cursor.fetchone()[0]
        cursor.execute("UPDATE cases.experiments SET status = 'closed' WHERE id = %s", (number,))
    return case_number


# ---------------------------------------------------------------------------
# Lectures
# ---------------------------------------------------------------------------

def _read(conn, sql, params=()):
    """Une lecture ; la transaction est annulée ensuite."""
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()
    finally:
        conn.rollback()


def _threshold():
    if MIN_SIMILARITY is None:
        raise CasesError("similarity threshold not calibrated", code="threshold_not_calibrated")
    return MIN_SIMILARITY


CASE_COLUMNS = ("author", "launched_on", "reviewed_on", "posture", "problem", "context", "hypotheses", "chosen_path", "references_used",
                "tested", "expected_signal", "success_criterion", "history", "outcome", "drop_reason", "what_got_stuck", "confidence")
EXPERIMENT_COLUMNS = ("author", "started_on", "review_due", "posture", "problem", "context", "hypotheses", "chosen_path", "tested",
                      "expected_signal", "success_criterion")


def _search(conn, embed, query, limit, spec, sql, columns, shape):
    threshold = _threshold()
    if not isinstance(query, str) or not query.strip():
        raise CasesError("the question is empty", code="query_empty", field="query")
    limit = _limit(limit)
    vector = _embed(embed, query)
    found = hybrid_search.hybrid_search(conn, spec, query=query, vector=vector, limit=MAX_LIMIT)
    if not found:
        return []
    scores = dict(found)
    rows = _read(conn, sql.format(columns=", ".join(columns)), {"qvec": _vector(vector), "ids": [i for i, _ in found]})
    by_id = {row[0]: row for row in rows}
    hits = []
    for identifier, _ in found:
        row = by_id.get(identifier)
        if row is None or row[-1] is None or float(row[-1]) < threshold:
            continue
        hits.append(shape(row, scores[identifier]))
        if len(hits) == limit:
            break
    return hits


def search_cases(conn, embed, query, limit=DEFAULT_LIMIT) -> list:
    def shape(row, score):
        hit = {"number": row[0], **{c: _iso(v) for c, v in zip(CASE_COLUMNS, row[1:-1])}}
        return {**hit, "similarity": round(float(row[-1]), 3), "score": score}
    sql = "SELECT c.id, {columns}, -(c.embedding <#> %(qvec)s::halfvec) FROM cases.cases c WHERE c.id = ANY(%(ids)s::bigint[])"
    return _search(conn, embed, query, limit, CASES_SPEC, sql, [f"c.{c}" for c in CASE_COLUMNS], shape)


def search_experiments(conn, embed, query, author, limit=DEFAULT_LIMIT) -> list:
    own = (author or "").strip()

    def shape(row, score):
        values = {c: _iso(v) for c, v in zip(EXPERIMENT_COLUMNS, row[1:-2])}
        hit = {"number": row[0], "author": values.pop("author"), "mine": bool(own) and row[1] == own}
        hit.update(values)
        return {**hit, "notes_count": row[-2], "similarity": round(float(row[-1]), 3), "score": score}
    sql = ("SELECT e.id, {columns}, (SELECT count(*) FROM cases.experiment_notes n WHERE n.experiment_id = e.id), "
           "-(e.embedding <#> %(qvec)s::halfvec) FROM cases.experiments e WHERE e.id = ANY(%(ids)s::bigint[]) AND e.status = 'running'")
    return _search(conn, embed, query, limit, EXPERIMENTS_SPEC, sql, [f"e.{c}" for c in EXPERIMENT_COLUMNS], shape)


# Une revue est due quand review_due <= aujourd'hui (le jour même compris) : règle unique du lecteur MCP, du journal et du tableau de bord.
DUE_CONDITION = "review_due <= %s"


def is_due(review_due, today) -> bool:
    return review_due <= today


def due_reviews(conn, author, today) -> list:
    rows = _read(conn, "SELECT id, problem, review_due, postponements FROM cases.experiments "
                       f"WHERE author = %s AND status = 'running' AND {DUE_CONDITION} ORDER BY review_due, id", (_author(author), today))
    return [{"number": i, "problem": p, "review_due": _iso(d), "postponements": n, "decision_required": n >= MAX_POSTPONEMENTS}
            for i, p, d, n in rows]


def running_experiments(conn, author, today=None) -> list:
    today = today or dt.date.today()
    rows = _read(conn, "SELECT id, problem, started_on, review_due, postponements FROM cases.experiments "
                       "WHERE author = %s AND status = 'running' ORDER BY review_due, id", (_author(author),))
    return [{"number": i, "problem": p, "started_on": _iso(s), "review_due": _iso(d), "postponements": n, "due": is_due(d, today)}
            for i, p, s, d, n in rows]


def show_experiment(conn, number) -> dict:
    number = _number(number)
    columns = ("author", "status", "started_on", "review_due", "postponements", "posture", "problem", "context", "hypotheses",
               "chosen_path", "references_used", "tested", "expected_signal", "success_criterion")
    rows = _read(conn, f"SELECT {', '.join(columns)} FROM cases.experiments WHERE id = %s", (number,))
    if not rows:
        raise CasesError(f"unknown experiment number {number}", code="unknown_experiment", field=str(number))
    notes = _read(conn, "SELECT noted_on, note FROM cases.experiment_notes WHERE experiment_id = %s ORDER BY noted_on, id", (number,))
    return {"number": number, **{c: _iso(v) for c, v in zip(columns, rows[0])},
            "notes": [{"noted_on": _iso(d), "note": n} for d, n in notes]}


# ---------------------------------------------------------------------------
# Lecteur paresseux du serveur MCP (design.md 4)
# ---------------------------------------------------------------------------

class CasesReader:
    """Connexion en lecture seule ouverte au premier appel, reprise une fois si elle est tombée. Lève CasesError, jamais un secret."""

    def __init__(self, connect=None, embed=None, today=None, author=None):
        self._connect = connect or self._default_connect
        self._embed, self._today, self._author = embed, today, author
        self._conn = None

    @staticmethod
    def _default_connect():
        import db
        try:
            return connect_cases(ROLE_READ)
        except db.ErreurBase as error:
            raise CasesError(f"cases database unreachable: {error} Start it with: bash tools/db_up.sh", code="database_unreachable") from None

    def connection(self):
        if self._conn is None or getattr(self._conn, "closed", False):
            self._conn = self._connect()
        return self._conn

    def _run(self, function):
        for attempt in (1, 2):
            try:
                return function(self.connection())
            except Exception as error:
                if attempt == 2 or type(error).__name__ != "OperationalError":      # connexion perdue : une reprise
                    raise
                self._conn = None

    def author(self):
        return self._author or resolve_author()

    def search_cases(self, query, limit=DEFAULT_LIMIT):
        return self._run(lambda conn: search_cases(conn, self._embed, query, limit))

    def search_experiments(self, query, limit=DEFAULT_LIMIT, author=None):
        who = author or self.author()
        return self._run(lambda conn: search_experiments(conn, self._embed, query, who, limit))

    def list_due_reviews(self, author=None):
        who = author or self._author or require_author()
        return self._run(lambda conn: due_reviews(conn, who, self._today or dt.date.today()))


# ---------------------------------------------------------------------------
# Jeu d'essai de l'évaluation (design.md 7.2)
# ---------------------------------------------------------------------------

FIXTURE_EXPERIMENT_KEYS = ("author", "started_on", "status", "review_due", "notes") + tuple(
    k for k in START_KEYS if k not in ("review_due", "date"))
FIXTURE_CASE_KEYS = ("author", "launched_on", "reviewed_on", "history", "outcome", "drop_reason", "what_got_stuck", "confidence") + (
    "problem", "context", "hypotheses", "chosen_path", "references_used", "tested", "expected_signal", "success_criterion", "posture")


def _fixture_author(raw):
    return _author(raw.get("author"))


def _fixture_experiment(raw):
    _unknown_keys(raw, FIXTURE_EXPERIMENT_KEYS)
    clean = _description(raw)
    clean["author"] = _fixture_author(raw)
    clean["started_on"] = _date(raw.get("started_on"), "started_on")
    clean["review_due"] = (_date(raw["review_due"], "review_due") if raw.get("review_due") is not None
                           else clean["started_on"] + dt.timedelta(weeks=DEFAULT_REVIEW_WEEKS))
    if clean["review_due"] < clean["started_on"]:
        raise CasesError("field review_due is before started_on", code="date_before_start", field="review_due")
    status = raw.get("status", "running")
    if status not in STATUSES:
        raise CasesError(f"field status must be one of: {', '.join(STATUSES)}", code="field_value", field="status")
    notes = raw.get("notes") or []
    if not isinstance(notes, list):
        raise CasesError("field notes must be a list", code="field_type", field="notes")
    clean["status"] = status
    clean["notes"] = []
    for item in notes:
        _unknown_keys(item, ("noted_on", "note"))
        noted = _date(item.get("noted_on"), "notes.noted_on")
        if noted < clean["started_on"]:
            raise CasesError("a note is dated before the start of the experiment", code="date_before_start", field="notes")
        clean["notes"].append((noted, _text(item.get("note"), "notes.note", required=True)))
    return clean


def _fixture_case(raw):
    _unknown_keys(raw, FIXTURE_CASE_KEYS)
    clean = _description(raw)
    clean["author"] = _fixture_author(raw)
    clean["launched_on"] = _date(raw.get("launched_on"), "launched_on")
    clean["reviewed_on"] = _date(raw.get("reviewed_on"), "reviewed_on")
    if clean["reviewed_on"] < clean["launched_on"]:
        raise CasesError("field reviewed_on is before launched_on", code="date_before_start", field="reviewed_on")
    outcome = _choice(raw.get("outcome"), "outcome", OUTCOMES, required=True)
    reason = _text(raw.get("drop_reason"), "drop_reason")
    if outcome == "dropped" and not reason:
        raise CasesError("field drop_reason is required when outcome is dropped", code="field_missing", field="drop_reason")
    history = raw.get("history") or []
    if not isinstance(history, list):
        raise CasesError("field history must be a list", code="field_type", field="history")
    clean["history"] = []
    for item in history:
        _unknown_keys(item, ("noted_on", "note"))
        clean["history"].append({"noted_on": _date(item.get("noted_on"), "history.noted_on").isoformat(),
                                 "note": _text(item.get("note"), "history.note", required=True)})
    clean.update(outcome=outcome, drop_reason=reason, what_got_stuck=_text(raw.get("what_got_stuck"), "what_got_stuck"),
                 confidence=_choice(raw.get("confidence"), "confidence", CONFIDENCES))
    return clean


def load_fixture(conn, embed, path) -> dict:
    """Charge un jeu d'essai YAML inventé (experiments puis cases) sous SET ROLE pmzilla_cases, en une transaction. Rend les décomptes.
    Mêmes règles que les brouillons, sauf la garde des noms sensibles et les règles de date « futur / passé » (dates fixes)."""
    import yaml
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    _unknown_keys(data, ("experiments", "cases"))
    experiments = [_fixture_experiment(raw) for raw in data.get("experiments") or []]
    cases = [_fixture_case(raw) for raw in data.get("cases") or []]
    embedded_experiments = [_embed(embed, embedding_text(e["problem"], e["chosen_path"], e["tested"])) for e in experiments]
    embedded_cases = [_embed(embed, embedding_text(c["problem"], c["chosen_path"], c["tested"])) for c in cases]
    with _transaction(conn) as cursor:
        cursor.execute("SET LOCAL ROLE pmzilla_cases")
        for e, vector in zip(experiments, embedded_experiments):
            number = _insert_experiment(cursor, e, vector, status=e["status"])
            for noted, note in e["notes"]:
                cursor.execute("INSERT INTO cases.experiment_notes (experiment_id, noted_on, note) VALUES (%s, %s, %s)", (number, noted, note))
        for c, vector in zip(cases, embedded_cases):
            number = _insert_experiment(cursor, {**c, "started_on": c["launched_on"], "review_due": c["reviewed_on"]}, vector, status="closed")
            cursor.execute(
                "INSERT INTO cases.cases (experiment_id, author, posture, problem, context, hypotheses, chosen_path, references_used, tested, "
                "expected_signal, success_criterion, launched_on, reviewed_on, history, outcome, drop_reason, what_got_stuck, confidence, embedding) "
                "VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s::halfvec)",
                (number, c["author"], c["posture"], c["problem"], _json(c["context"]), _json(c["hypotheses"]), c["chosen_path"],
                 _json(c["references_used"]), c["tested"], c["expected_signal"], c["success_criterion"], c["launched_on"], c["reviewed_on"],
                 _json(c["history"]), c["outcome"], c["drop_reason"], c["what_got_stuck"], c["confidence"], _vector(vector)))
    return {"experiments": len(experiments), "cases": len(cases)}
