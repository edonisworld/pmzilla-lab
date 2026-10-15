# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=1.2,<2", "numpy", "httpx", "pyyaml", "psycopg[binary]"]
# ///
"""
PMZilla Lab : garde de la recherche de la bibliothèque, par instantané des résultats PostgreSQL.

    uv run tools/library_parity.py record [--replace] [options]     # enregistre l'instantané (action de l'utilisateur)
    uv run tools/library_parity.py [options]                        # compare à l'instantané (défaut)
    options : [--queries tests/parity/queries.yaml] [--limit 8] [--scan ann|exact] [--ef-search 400] [--fulltext tsvector|bm25]
              [--rank-norm 0|1|2] [--component vector|text|hybrid] [--collections a,b] [--details] [--explain ID] [--threshold 0.85] [--min-overlap 0.5]

`record` joue le jeu figé (français et anglais) et écrit UN fichier, `library_parity_snapshot.json`, dans le dossier de données
(PMZILLA_LAB_DATA, défaut ~/.pmzilla-lab), lisible par le seul propriétaire : par requête les `limit` premiers résultats (fichier, position),
les réglages, la date de fraîcheur, l'empreinte du jeu de requêtes et les livres indexés (fichier, empreinte du contenu). Ni texte ni titre.
Il n'affiche que des nombres et le chemin, et refuse de remplacer un instantané existant sans --replace (« snapshot exists », code 2).

La comparaison rejoue le jeu avec les réglages et la date de l'instantané et mesure le recouvrement : résultats communs / limit. Elle sort avec
le code 2, avant toute requête, sans instantané (« no snapshot: run library_parity.py record first »), si le jeu de requêtes a changé
(« query set changed since the snapshot ») ou si une option donnée diffère des réglages de l'instantané (« settings differ from the snapshot »).
Elle dit combien de livres ont été ajoutés, retirés ou modifiés depuis l'instantané (nombres seuls), pour lire un recouvrement plus bas après
de nouveaux articles de veille. À réenregistrer à la main, après un ajout de livres, un REINDEX vérifié ou un changement du code de recherche.

Verdict (seuils proposés) : recouvrement moyen >= --threshold (0,85), aucune requête sous --min-overlap (0,5), et au moins 7 résultats communs
sur 8 pour les requêtes `rare: true`. --component mesure une seule composante : `vector`, `text` ou `hybrid` (défaut). Le rapport est un résumé
(identifiant, recouvrement, verdict de la requête, latence de la recherche seule, sans l'embedding) ; `--details` ajoute, pour les requêtes sous
0,75, les fichier:position propres à l'instantané ou au présent.

--explain ID ne compare rien : il joue la requête ID avec EXPLAIN (ANALYZE, BUFFERS) et affiche le plan, débarrassé de tout littéral.

Code de sortie : 0 si le verdict est « parité », 1 sinon, 2 si la mesure n'a pas pu se faire (dont base injoignable).
Le rapport s'affiche dans le Terminal et n'est écrit nulle part ; seul `record` écrit l'instantané.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

RACINE = Path(__file__).resolve().parents[1]
QUERIES_FILE = RACINE / "tests" / "parity" / "queries.yaml"
MIGRATIONS = RACINE / "db" / "migrations"
DEFAULT_LIMIT = 8
DEFAULT_EF_SEARCH = 400      # = hybrid_search.EF_SEARCH (pgvector : 40, sous les 50 candidats de la voie vecteur)
DEFAULT_THRESHOLD = 0.85
DEFAULT_MIN_OVERLAP = 0.5
RARE_COMMON = 7        # résultats communs exigés (sur 8) pour une requête à mot rare
SNAPSHOT_NAME = "library_parity_snapshot.json"
KNOWN_KEYS = {"id", "lang", "query", "collections", "types", "rare"}


class ParityError(Exception):
    """Mesure impossible ou jeu de requêtes invalide ; le message ne contient ni texte de livre ni secret."""


# ---------------------------------------------------------------------------
# Jeu de requêtes
# ---------------------------------------------------------------------------

def load_queries(path: Path) -> list[dict]:
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except OSError as error:
        raise ParityError(f"jeu de requêtes illisible : {path} ({error.strerror})") from None
    queries = (data or {}).get("queries") if isinstance(data, dict) else None
    if not isinstance(queries, list) or not queries:
        raise ParityError(f"{path} : liste « queries » absente ou vide")
    seen: set[str] = set()
    for number, item in enumerate(queries, 1):
        if not isinstance(item, dict) or not item.get("id") or not str(item.get("query", "")).strip():
            raise ParityError(f"{path} : requête {number} sans identifiant ou sans texte")
        if set(item) - KNOWN_KEYS:
            raise ParityError(f"{path} : requête {item['id']} : clé inconnue {sorted(set(item) - KNOWN_KEYS)}")
        if item["id"] in seen:
            raise ParityError(f"{path} : identifiant en double : {item['id']}")
        seen.add(item["id"])
        if item.get("lang") not in ("fr", "en"):
            raise ParityError(f"{path} : requête {item['id']} : lang doit être fr ou en")
    return queries


# ---------------------------------------------------------------------------
# Mesure
# ---------------------------------------------------------------------------

def keys_of(results: list[dict]) -> list[tuple[str, int]]:
    return [(r["file"], r["position"]) for r in results]


def overlap(first: list, second: list, limit: int) -> int:
    """Nombre de résultats communs entre les `limit` premiers de chaque liste."""
    return len(set(first[:limit]) & set(second[:limit]))


def p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int(round(0.95 * len(ordered))) - 1))] if ordered else 0.0


def run_compare(queries: list[dict], snapshot: dict, lib, *, limit: int = DEFAULT_LIMIT, collections: list[str] | None = None,
                warm=None, clock=time.perf_counter, component: str = "hybrid") -> dict:
    """Joue les requêtes sur la voie PostgreSQL et compare à l'instantané. `warm(query)` calcule l'embedding avant la mesure de latence."""
    rows, latency = [], []
    for item in queries:
        query = item["query"]
        wanted = collections or item.get("collections") or None
        if warm:
            warm(query)
        extra = {} if component == "hybrid" else {"component": component}      # les doublures des tests n'ont pas ce paramètre
        started = clock()
        found = lib.search(query, wanted, limit, None, item.get("types"), **extra)
        seconds = clock() - started
        latency.append(seconds)
        now = keys_of(found)[:limit]
        before = [(f, p) for f, p in snapshot["queries"].get(item["id"], [])][:limit]
        rows.append({"id": item["id"], "lang": item["lang"], "rare": bool(item.get("rare")), "common": overlap(before, now, limit),
                     "snapshot": before, "now": now, "seconds": seconds})
    return {"rows": rows, "limit": limit, "latency": latency, "component": component}


def record_results(queries: list[dict], lib, *, limit: int, collections: list[str] | None, warm=None, component: str = "hybrid") -> dict:
    """Les `limit` premiers (fichier, position) de chaque requête, dans l'ordre, par identifiant."""
    out = {}
    for item in queries:
        if warm:
            warm(item["query"])
        extra = {} if component == "hybrid" else {"component": component}
        found = lib.search(item["query"], collections or item.get("collections") or None, limit, None, item.get("types"), **extra)
        out[item["id"]] = [list(k) for k in keys_of(found)[:limit]]
    return out


def queries_fingerprint(queries: list[dict]) -> str:
    return hashlib.sha256(json.dumps(queries, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")).hexdigest()


def snapshot_path() -> Path:
    return Path(os.environ.get("PMZILLA_LAB_DATA") or "~/.pmzilla-lab").expanduser() / SNAPSHOT_NAME


def write_snapshot(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def read_books(lib) -> list[list[str]]:
    """(fichier, empreinte du contenu) des livres indexés ; ni titre ni texte."""
    return [[f, h] for f, h in lib._query("SELECT file_name, sha256 FROM knowledge.books ORDER BY file_name")]


def book_changes(before: list, now: list) -> dict:
    old, new = {f: h for f, h in before}, {f: h for f, h in now}
    return {"added": len(set(new) - set(old)), "removed": len(set(old) - set(new)),
            "changed": sum(1 for f in set(old) & set(new) if old[f] != new[f])}


def verdict(report: dict, threshold: float = DEFAULT_THRESHOLD, min_overlap: float = DEFAULT_MIN_OVERLAP) -> dict:
    limit = report["limit"]
    rows = report["rows"]
    ratios = [r["common"] / limit for r in rows]
    mean = statistics.fmean(ratios) if ratios else 0.0
    below = [r["id"] for r, x in zip(rows, ratios) if x < min_overlap]
    rare_needed = min(RARE_COMMON, limit)
    rare_bad = [r["id"] for r in rows if r["rare"] and r["common"] < rare_needed]
    worst = min(rows, key=lambda r: r["common"]) if rows else None
    return {"mean": mean, "min": min(ratios) if ratios else 0.0, "worst": worst["id"] if worst else None,
            "below": below, "rare_bad": rare_bad, "threshold": threshold, "min_overlap": min_overlap,
            "ok": bool(rows) and mean >= threshold and not below and not rare_bad}


def redact_plan(text: str) -> str:
    """Plan EXPLAIN sans aucune valeur : les littéraux entre apostrophes (mots de la question, noms de collection, dates) et les vecteurs
    entre crochets sont remplacés ; restent les nœuds, les noms d'index et de tables, les nombres de lignes et les temps."""
    text = re.sub(r"'(?:[^']|'')*'", "'…'", text)
    text = re.sub(r"\[[-0-9.eE+, ]{12,}\]", "[…]", text)
    return text


def explain_query(conn, sql: str, params: dict, setup: tuple[str, ...] = ()) -> str:
    """EXPLAIN (ANALYZE, BUFFERS) d'une requête de lecture, plan expurgé. La transaction est annulée ensuite."""
    try:
        with conn.cursor() as cursor:
            for ordre in setup:
                cursor.execute(ordre)
            cursor.execute("EXPLAIN (ANALYZE, BUFFERS) " + sql, params)
            lignes = [row[0] for row in cursor.fetchall()]
    finally:
        conn.rollback()
    return redact_plan("\n".join(lignes))


def row_verdict(row: dict, limit: int, min_overlap: float) -> str:
    """Verdict d'une requête : « ok », ou « écart » sous le recouvrement minimal ou, pour une requête rare, sous 7 résultats communs."""
    if row["common"] / limit < min_overlap or (row["rare"] and row["common"] < min(RARE_COMMON, limit)):
        return "écart"
    return "ok"


def render(report: dict, result: dict, details: bool = False, changes: dict | None = None) -> str:
    limit = report["limit"]
    composante = {"hybrid": "hybride", "vector": "vecteur seul", "text": "plein texte seul"}.get(report.get("component", "hybrid"), "hybride")
    lines = [f"Comparaison avec l'instantané · {composante} · {len(report['rows'])} requêtes · {limit} premiers résultats", "",
             f"{'requête':<28} lang  recouvrement  verdict   latence"]
    for r in report["rows"]:
        ms = f"{1000 * r['seconds']:>5.0f} ms" if "seconds" in r else "     -  "
        lines.append(f"{r['id']:<28} {r['lang']:<4}  {r['common']}/{limit}{' (rare)' if r['rare'] else '       '}"
                     f"   {row_verdict(r, limit, result['min_overlap']):<7}  {ms}")
        if details and r["common"] / limit < 0.75:
            only_a = [f"{f}:{p}" for f, p in r["snapshot"] if (f, p) not in set(map(tuple, r["now"]))]
            only_b = [f"{f}:{p}" for f, p in r["now"] if (f, p) not in set(map(tuple, r["snapshot"]))]
            lines.append(f"    seulement dans l'instantané : {', '.join(only_a) or '-'}")
            lines.append(f"    seulement maintenant : {', '.join(only_b) or '-'}")
    lines.append("")
    if changes:
        lines.append(f"Bibliothèque depuis l'instantané : {changes['added']} livres ajoutés · {changes['removed']} retirés · {changes['changed']} modifiés")
    lines += [f"Recouvrement moyen : {result['mean']:.3f} (seuil {result['threshold']:.2f}) · minimum : {result['min']:.3f}"
                  f" · pire requête : {result['worst']}",
              f"Requêtes sous {result['min_overlap']:.2f} : {len(result['below'])}"
              + (f" ({', '.join(result['below'])})" if result["below"] else ""),
              f"Requêtes rares sous {min(RARE_COMMON, limit)}/{limit} : {len(result['rare_bad'])}"
              + (f" ({', '.join(result['rare_bad'])})" if result["rare_bad"] else "")]
    values = report["latency"]
    lines.append(f"Latence : moyenne {1000 * statistics.fmean(values):.0f} ms · p95 {1000 * p95(values):.0f} ms" if values else "Latence : -")
    lines.append("Verdict : " + ("PARITÉ au seuil retenu" if result["ok"] else "PARITÉ NON ATTEINTE au seuil retenu"))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Ligne de commande
# ---------------------------------------------------------------------------

class SharedEmbed:
    """Un embedding par texte, mis en cache avant la mesure de latence."""

    def __init__(self, embed):
        self.embed, self.cache = embed, {}

    def __call__(self, texts):
        import numpy as np
        for text in texts:
            if text not in self.cache:
                self.cache[text] = self.embed([text])[0]
        return np.vstack([self.cache[text] for text in texts])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Garde de la recherche de la bibliothèque : instantané des résultats PostgreSQL et comparaison")
    parser.add_argument("command", nargs="?", choices=("record", "compare"), default="compare",
                        help="record : enregistre l'instantané ; compare (défaut) : compare à l'instantané")
    parser.add_argument("--replace", action="store_true", help="record : remplace un instantané existant")
    parser.add_argument("--queries", type=Path, default=QUERIES_FILE)
    # None = non donné : en comparaison, seule une option donnée est confrontée aux réglages de l'instantané.
    parser.add_argument("--limit", type=int, default=None, help=f"défaut {DEFAULT_LIMIT}")
    parser.add_argument("--fulltext", choices=("tsvector", "bm25"), default=None,
                        help="classement plein texte : bm25 (pg_search, défaut) ou tsvector (ts_rank_cd)")
    parser.add_argument("--scan", choices=("exact", "ann"), default=None,
                        help="balayage vectoriel : ann (index HNSW, défaut) ou exact")
    parser.add_argument("--ef-search", type=int, default=None, metavar="N",
                        help="hnsw.ef_search du balayage ann (SET LOCAL dans la transaction ; 1 à 1000, défaut 400 ; pgvector : 40)")
    parser.add_argument("--component", choices=("hybrid", "vector", "text"), default=None,
                        help="composante mesurée : vector (similarité seule), text (plein texte seul) ou hybrid (les deux fusionnées, défaut)")
    parser.add_argument("--explain", metavar="ID", help="afficher le plan EXPLAIN ANALYZE de la requête ID (sans comparer)")
    parser.add_argument("--details", action="store_true", help="afficher les fichier:position propres à l'instantané ou au présent (sinon : résumé)")
    parser.add_argument("--rank-norm", type=int, choices=(0, 1, 2), default=None,
                        help="drapeau de normalisation de ts_rank_cd (--fulltext tsvector) : 0 aucune, 1 divise par 1 + log(longueur), 2 divise par la longueur (défaut : celui du module, 1)")
    parser.add_argument("--collections", help="restreint toutes les requêtes à ces collections (séparées par des virgules)")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--min-overlap", type=float, default=DEFAULT_MIN_OVERLAP)
    return parser


def default_embed():
    import knowledge_library
    return getattr(knowledge_library, "embed", None) or knowledge_library.library.embed


def settings_from(args) -> dict:
    wanted = sorted({c for c in (args.collections or "").split(",") if c}) or None
    return {"limit": DEFAULT_LIMIT if args.limit is None else args.limit, "scan": args.scan or "ann", "ef_search": DEFAULT_EF_SEARCH if args.ef_search is None else args.ef_search,
            "fulltext": args.fulltext or "bm25", "rank_norm": args.rank_norm, "component": args.component or "hybrid", "collections": wanted}


def settings_differ(args, saved: dict) -> bool:
    given = {"limit": args.limit, "scan": args.scan, "ef_search": args.ef_search, "fulltext": args.fulltext, "rank_norm": args.rank_norm,
             "component": args.component, "collections": sorted({c for c in (args.collections or "").split(",") if c}) or None}
    return any(value is not None and value != saved.get(key) for key, value in given.items())


def main(argv: list[str] | None = None, *, factory=None, embed=None, books_reader=None, today=None, clock=time.perf_counter) -> int:
    """`factory`, `embed`, `books_reader` et `today` s'injectent pour les tests ; par défaut : PostgresLibrary et la base réelle."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit doit être au moins 1")
    if args.ef_search is not None and not 1 <= args.ef_search <= 1000:
        parser.error("--ef-search doit être compris entre 1 et 1000")
    if (args.fulltext or "bm25") == "bm25" and not list(MIGRATIONS.glob("0005_*.sql")):
        print("Plein texte BM25 non disponible : migration 0005 absente")
        return 2
    recording = args.command == "record"
    path = snapshot_path()
    try:
        queries = load_queries(args.queries)
        fingerprint = queries_fingerprint(queries)
        snapshot = None
        if recording:
            if path.exists() and not args.replace:
                print(f"Mesure impossible : snapshot exists ({path}) ; --replace pour le remplacer")
                return 2
            settings = settings_from(args)
        elif not args.explain:
            if not path.exists():
                print("Mesure impossible : no snapshot: run library_parity.py record first")
                return 2
            try:
                snapshot = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raise ParityError("instantané illisible : run library_parity.py record --replace") from None
            if snapshot.get("queries_fingerprint") != fingerprint:
                print("Mesure impossible : query set changed since the snapshot")
                return 2
            if settings_differ(args, snapshot["settings"]):
                print("Mesure impossible : settings differ from the snapshot")
                return 2
            settings = snapshot["settings"]
            today = dt.date.fromisoformat(snapshot["freshness_date"])
        else:
            settings = settings_from(args)
        shared = SharedEmbed(embed or default_embed())
        if factory is None:
            import knowledge_library
            factory = knowledge_library.PostgresLibrary
        try:
            lib = factory(embed=shared, scan=settings["scan"], fulltext=settings["fulltext"], rank_norm=settings["rank_norm"],
                          ef_search=settings["ef_search"], today=today or dt.date.today())
        except (Exception, SystemExit) as error:
            raise ParityError(f"base de la bibliothèque injoignable ({type(error).__name__})") from None
        wanted_collections = settings["collections"]
        if args.explain:
            found = [q for q in queries if q["id"] == args.explain]
            if not found:
                raise ParityError(f"requête inconnue : {args.explain} (identifiants dans {Path(args.queries).name})")
            import hybrid_search
            item = found[0]
            kinds = None if set(item.get("types") or ["texte"]) == {"texte", "figure"} else [{"texte": "text", "figure": "figure"}[k] for k in (item.get("types") or ["texte"])]
            sql, params = hybrid_search.build_query(
                lib.spec, query=item["query"], vector=shared([item["query"]])[0], limit=settings["limit"],
                collections=wanted_collections or item.get("collections") or None, kinds=kinds, scan=settings["scan"],
                fulltext=settings["fulltext"], rank_norm=settings["rank_norm"], component=settings["component"])
            setup = (f"SET LOCAL hnsw.ef_search = {settings['ef_search']}", "SET LOCAL hnsw.iterative_scan = relaxed_order") if settings["scan"] == "ann" else ()
            print(f"Plan de la requête {args.explain} · composante {settings['component']} · plein texte {settings['fulltext']} · balayage {settings['scan']}\n")
            print(explain_query(lib.connection(), sql, params, setup))
            return 0
        reader = books_reader or read_books
        if recording:
            results = record_results(queries, lib, limit=settings["limit"], collections=wanted_collections,
                                     warm=lambda q: shared([q]), component=settings["component"])
            books = reader(lib)
            write_snapshot(path, {"version": 1, "settings": settings, "freshness_date": (today or dt.date.today()).isoformat(),
                                  "queries_fingerprint": fingerprint, "queries": results, "books": books})
            print(f"Instantané enregistré : {len(results)} requêtes · {len(books)} livres · {path}")
            return 0
        report = run_compare(queries, snapshot, lib, limit=settings["limit"], collections=wanted_collections,
                             warm=lambda q: shared([q]), component=settings["component"], clock=clock)
        changes = book_changes(snapshot.get("books", []), reader(lib))
    except ParityError as error:
        print(f"Mesure impossible : {error}")
        return 2
    except NotImplementedError as error:
        print(f"Mesure impossible : {error}")
        return 2
    result = verdict(report, args.threshold, args.min_overlap)
    print(render(report, result, details=args.details, changes=changes))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
