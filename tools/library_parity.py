# /// script
# requires-python = ">=3.11"
# dependencies = ["mcp>=1.2,<2", "numpy", "httpx", "pyyaml", "psycopg[binary]"]
# ///
"""
PMZilla Lab : parité des deux voies de la bibliothèque, SQLite et PostgreSQL (lot 4 de la base).

    uv run tools/library_parity.py [--queries tests/parity/queries.yaml] [--limit 8] [--scan ann|exact] [--ef-search 400]
                                   [--fulltext tsvector|bm25] [--rank-norm 0|1|2] [--component vector|text|hybrid] [--details] [--explain ID] [--collections watch,own-articles] [--threshold 0.85] [--min-overlap 0.5]

Joue chaque requête du jeu figé (français et anglais) sur les deux voies et compare les `limit` premiers résultats par paires
(fichier, position) : recouvrement = résultats communs / limit. L'embedding de la requête est calculé UNE fois (bge-m3 par Ollama) et
partagé : les deux voies reçoivent le même vecteur, la mesure ne porte que sur la recherche. Les latences ne comptent que la recherche.

Verdict (seuils proposés, à recaler sur la première mesure avec l'accord de l'utilisateur) : recouvrement moyen >= --threshold
(0,85), aucune requête sous --min-overlap (0,5), et au moins 7 résultats communs sur 8 pour les requêtes `rare: true`.
--component mesure une seule voie des deux côtés : `vector` (classement par similarité seul), `text` (plein texte seul) ou `hybrid` (défaut, les deux
fusionnées) ; la composante qui échoue désigne la cause d'un écart. Par défaut le rapport est un résumé (identifiant de la requête, recouvrement,
verdict de la requête, latence de chaque voie) ; `--details` ajoute, pour les requêtes sous 0,75, les fichier:position propres à chaque voie.

--explain ID ne lance aucune parité : il joue la requête d'identifiant ID sur la voie PostgreSQL seule avec EXPLAIN (ANALYZE, BUFFERS) et affiche
le plan (nœuds, index utilisés, lignes, temps), débarrassé de tout littéral (mots de la question, collections, dates, vecteur) : aucune valeur de données.
Les options --component, --fulltext, --rank-norm, --scan et --collections s'appliquent. À lancer pour comprendre une latence.

Code de sortie : 0 si le verdict est « parité », 1 sinon, 2 si la mesure n'a pas pu se faire.

Le rapport s'affiche dans le Terminal et n'est écrit nulle part : il ne contient que des identifiants de requêtes, des
fichier:position et des nombres, jamais un titre de passage ni un texte. À lancer juste après `knowledge_import.py import`, pour
comparer des corpus identiques (l'index SQLite change chaque matin avec la veille).
"""
from __future__ import annotations

import argparse
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


def run_parity(queries: list[dict], sqlite_lib, postgres_lib, *, limit: int = DEFAULT_LIMIT, collections: list[str] | None = None,
               warm=None, clock=time.perf_counter, component: str = "hybrid") -> dict:
    """Joue les requêtes sur les deux voies. `warm(query)` calcule et met en cache l'embedding avant la mesure de latence."""
    rows = []
    lat = {"sqlite": [], "postgres": []}
    for item in queries:
        query = item["query"]
        wanted = collections or item.get("collections") or None
        if warm:
            warm(query)
        found, seconds = {}, {}
        extra = {} if component == "hybrid" else {"component": component}      # les faux backends des tests n'ont pas ce paramètre
        for name, lib in (("sqlite", sqlite_lib), ("postgres", postgres_lib)):
            started = clock()
            found[name] = lib.search(query, wanted, limit, None, item.get("types"), **extra)
            seconds[name] = clock() - started
            lat[name].append(seconds[name])
        a, b = keys_of(found["sqlite"]), keys_of(found["postgres"])
        rows.append({"id": item["id"], "lang": item["lang"], "rare": bool(item.get("rare")), "common": overlap(a, b, limit),
                     "sqlite": a[:limit], "postgres": b[:limit], "count_sqlite": len(a), "count_postgres": len(b),
                     "seconds": seconds, "restricted": bool(wanted)})
    return {"rows": rows, "limit": limit, "latency": lat, "component": component}


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


def group_lines(report: dict) -> list[str]:
    """Les requêtes restreintes par collection (jeu de requêtes ou option globale) à part des autres : sur la voie PostgreSQL la collection filtre
    avant la limite du plein texte, sur la voie SQLite après (change filter-before-keyword-limit) ; l'écart qui en découle n'est pas une régression
    des requêtes libres. Aucun groupe restreint : aucune ligne. Les deux groupes restent dans le verdict global."""
    limit = report["limit"]
    restreintes = [r for r in report["rows"] if r.get("restricted")]
    if not restreintes:
        return []
    libres = [r for r in report["rows"] if not r.get("restricted")]
    def ligne(nom, groupe):
        ratios = [r["common"] / limit for r in groupe]
        return f"{nom} : {len(groupe)} · recouvrement moyen {statistics.fmean(ratios):.3f} · minimum {min(ratios):.3f}"
    lines = [ligne("Requêtes restreintes par collection (écart possible par construction)", restreintes),
             "  " + ", ".join(r["id"] for r in restreintes)]
    if libres:
        lines.append(ligne("Requêtes sans restriction", libres))
    return lines


def render(report: dict, result: dict, details: bool = False) -> str:
    limit = report["limit"]
    composante = {"hybrid": "hybride", "vector": "vecteur seul", "text": "plein texte seul"}.get(report.get("component", "hybrid"), "hybride")
    lines = [f"Parité SQLite / PostgreSQL · {composante} · {len(report['rows'])} requêtes · {limit} premiers résultats", "",
             f"{'requête':<28} lang  recouvrement  verdict   SQLite   PostgreSQL"]
    for r in report["rows"]:
        sec = r.get("seconds", {})
        ms = lambda nom: f"{1000 * sec[nom]:>5.0f} ms" if nom in sec else "     -  "
        lines.append(f"{r['id']:<28} {r['lang']:<4}  {r['common']}/{limit}{' (rare)' if r['rare'] else '       '}"
                     f"   {row_verdict(r, limit, result['min_overlap']):<7}  {ms('sqlite')}  {ms('postgres')}")
        if details and r["common"] / limit < 0.75:
            only_a = [f"{f}:{p}" for f, p in r["sqlite"] if (f, p) not in set(r["postgres"])]
            only_b = [f"{f}:{p}" for f, p in r["postgres"] if (f, p) not in set(r["sqlite"])]
            lines.append(f"    seulement SQLite : {', '.join(only_a) or '-'}")
            lines.append(f"    seulement PostgreSQL : {', '.join(only_b) or '-'}")
    lines += [""] + group_lines(report)
    lines += [f"Recouvrement moyen : {result['mean']:.3f} (seuil {result['threshold']:.2f}) · minimum : {result['min']:.3f}"
                  f" · pire requête : {result['worst']}",
              f"Requêtes sous {result['min_overlap']:.2f} : {len(result['below'])}"
              + (f" ({', '.join(result['below'])})" if result["below"] else ""),
              f"Requêtes rares sous {min(RARE_COMMON, limit)}/{limit} : {len(result['rare_bad'])}"
              + (f" ({', '.join(result['rare_bad'])})" if result["rare_bad"] else "")]
    for name in ("sqlite", "postgres"):
        values = report["latency"][name]
        lines.append(f"Latence {name:<8} : moyenne {1000 * statistics.fmean(values):.0f} ms · p95 {1000 * p95(values):.0f} ms" if values
                     else f"Latence {name} : -")
    lines.append("Verdict : " + ("PARITÉ au seuil retenu" if result["ok"] else "PARITÉ NON ATTEINTE au seuil retenu"))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Ligne de commande
# ---------------------------------------------------------------------------

class SharedEmbed:
    """Un embedding par texte, partagé par les deux voies (et mis en cache avant la mesure de latence)."""

    def __init__(self, embed):
        self.embed, self.cache = embed, {}

    def __call__(self, texts):
        import numpy as np
        for text in texts:
            if text not in self.cache:
                self.cache[text] = self.embed([text])[0]
        return np.vstack([self.cache[text] for text in texts])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parité des deux voies de la bibliothèque (SQLite, PostgreSQL)")
    parser.add_argument("--queries", type=Path, default=QUERIES_FILE)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--fulltext", choices=("tsvector", "bm25"), default="bm25",
                        help="classement plein texte de la voie PostgreSQL : bm25 (pg_search, défaut) ou tsvector (ts_rank_cd, pour comparer)")
    parser.add_argument("--scan", choices=("exact", "ann"), default="ann",
                        help="balayage vectoriel de la voie PostgreSQL : ann (index HNSW, défaut) ou exact")
    parser.add_argument("--ef-search", type=int, default=DEFAULT_EF_SEARCH, metavar="N",
                        help="hnsw.ef_search du balayage ann (SET LOCAL dans la transaction ; 1 à 1000, défaut 400 ; pgvector : 40)")
    parser.add_argument("--component", choices=("hybrid", "vector", "text"), default="hybrid",
                        help="voie mesurée : vector (similarité seule), text (plein texte seul) ou hybrid (les deux fusionnées, défaut)")
    parser.add_argument("--explain", metavar="ID", help="afficher le plan EXPLAIN ANALYZE de la requête ID sur la voie PostgreSQL (sans lancer la parité)")
    parser.add_argument("--details", action="store_true", help="afficher les fichier:position propres à chaque voie (sinon : résumé)")
    parser.add_argument("--rank-norm", type=int, choices=(0, 1, 2), default=None,
                        help="drapeau de normalisation de ts_rank_cd (voie --fulltext tsvector) : 0 aucune, 1 divise par 1 + log(longueur), 2 divise par la longueur (défaut : celui du module, 1)")
    parser.add_argument("--collections", help="restreint toutes les requêtes à ces collections (séparées par des virgules)")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--min-overlap", type=float, default=DEFAULT_MIN_OVERLAP)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit doit être au moins 1")
    if not 1 <= args.ef_search <= 1000:
        parser.error("--ef-search doit être compris entre 1 et 1000")
    if args.fulltext == "bm25" and not list(MIGRATIONS.glob("0005_*.sql")):
        print("Plein texte BM25 non disponible : migration 0005 absente")
        return 2
    try:
        queries = load_queries(args.queries)
        import pmzilla_lab_library as library
        import knowledge_library
        shared = SharedEmbed(library.embed)
        library.embed = shared      # la voie SQLite appelle library.embed : même vecteur pour les deux voies
        sqlite_lib = library.Library()
        postgres_lib = knowledge_library.PostgresLibrary(embed=shared, scan=args.scan, fulltext=args.fulltext, rank_norm=args.rank_norm,
                                                      ef_search=args.ef_search)
        collections = [c for c in (args.collections or "").split(",") if c] or None
        if args.explain:
            wanted = [q for q in queries if q["id"] == args.explain]
            if not wanted:
                raise ParityError(f"requête inconnue : {args.explain} (identifiants dans {Path(args.queries).name})")
            import hybrid_search
            item = wanted[0]
            kinds = None if set(item.get("types") or ["texte"]) == {"texte", "figure"} else [{"texte": "text", "figure": "figure"}[k] for k in (item.get("types") or ["texte"])]
            sql, params = hybrid_search.build_query(
                postgres_lib.spec, query=item["query"], vector=shared([item["query"]])[0], limit=args.limit,
                collections=collections or item.get("collections") or None, kinds=kinds, scan=args.scan, fulltext=args.fulltext,
                rank_norm=args.rank_norm, component=args.component)
            setup = (f"SET LOCAL hnsw.ef_search = {args.ef_search}", "SET LOCAL hnsw.iterative_scan = relaxed_order") if args.scan == "ann" else ()
            print(f"Plan de la requête {args.explain} · composante {args.component} · plein texte {args.fulltext} · balayage {args.scan}\n")
            print(explain_query(postgres_lib.connection(), sql, params, setup))
            return 0
        report = run_parity(queries, sqlite_lib, postgres_lib, limit=args.limit, collections=collections,
                            warm=lambda q: shared([q]), component=args.component)
    except ParityError as error:
        print(f"Mesure impossible : {error}")
        return 2
    except NotImplementedError as error:
        print(f"Mesure impossible : {error}")
        return 2
    result = verdict(report, args.threshold, args.min_overlap)
    print(render(report, result, details=args.details))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
