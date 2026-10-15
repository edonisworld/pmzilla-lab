"""
PMZilla Lab : recherche hybride en SQL (lot 4 de la base, docs/pmzilla/application.md 5.1 et 9), réutilisable telle quelle par les
outils de recherche du module de cas (search_cases, search_experiments, lot 2) : seule la spécification change.

La recherche de la bibliothèque est une fusion de deux listes, écrite en une requête :

  - candidats sémantiques : les 50 passages les plus proches de la question (cosinus), rangés par score arrondi à 3 décimales,
    puis par bonus de fraîcheur décroissant, puis par identifiant (à égalité de pertinence, le billet récent d'abord) ;
  - candidats plein texte : les 50 meilleurs passages qui contiennent au moins un des mots de la question (OU, comme FTS5), classés par BM25
    (index pg_search de la migration 0005, tokenizer `pdb.simple` avec ascii_folding : minuscules, sans accents, sans racinisation, comme
    `unicode61 remove_diacritics 2` de FTS5). `fulltext="tsvector"` garde l'ancien classement `ts_rank_cd` (configuration `simple`, normalisé par la
    longueur : drapeau 1, voir NORMALISATION_RANG), qui ignore l'IDF : seulement pour comparer ;
  - fusion de rangs réciproque : somme de 1 / (60 + rang + 1) sur les deux listes (rangs à partir de 0), plus le bonus de fraîcheur
    (0,001 par défaut, demi-vie 180 jours, seulement pour un document daté de la collection « watch », jamais la collection personnelle (OWN_COLLECTION) ;
    la moitié du bonus, « neutre », sinon).

Le balayage vectoriel passe par défaut par l'index HNSW (`scan="ann"`, `hnsw.ef_search` = EF_SEARCH, réglable) ; `scan="exact"` (le cast
en `vector` met l'index HNSW hors jeu : même résultat que numpy) reste une option, plus lent. La CTE `scope` n'est jamais matérialisée (voir build_query).

Aucune valeur n'est interpolée dans le SQL : la question, les mots, les collections, la date et le vecteur passent en paramètres
psycopg ; seuls des entiers et des réels convertis par int() et float() (constantes de réglage) sont écrits dans le texte.
`fuse` et `freshness_bonus` sont les mêmes calculs en Python pur : les tests les comparent aux valeurs figées et à la requête SQL sur la bibliothèque inventée.

Ce module n'ouvre aucune connexion de lui-même : `hybrid_search` reçoit une connexion psycopg.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

from watch_paths import OWN_COLLECTION  # jamais de bonus de fraîcheur pour les articles de la collection personnelle

RRF_K = 60                 # constante de la fusion de rangs
CANDIDATES = 50            # candidats pris dans chaque liste avant la fusion
EF_SEARCH = 400            # hnsw.ef_search du balayage ann (défaut pgvector : 40, sous les CANDIDATES ; 100 laissait atelier-fr à 2/8) ; pgvector accepte 1 à 1000
FRESHNESS_BONUS = 0.001
FRESHNESS_HALF_LIFE = 180  # jours
FRESHNESS_COLLECTIONS = ("watch",)
SCANS = ("exact", "ann")
DEFAULT_SCAN = "ann"       # décidé après la parité du lot 4 (hybride 0,946, vecteur seul 0,994 avec ef_search 400) ; « exact » reste une option
FULLTEXTS = ("tsvector", "bm25")
COMPONENTS = ("hybrid", "vector", "text")      # voies fusionnées ; « vector » et « text » : une seule, pour mesurer chacune séparément

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class HybridSpec:
    """Ce qu'il faut savoir d'une table pour la chercher. Les fragments SQL sont du texte du dépôt, jamais des valeurs saisies."""
    from_sql: str                          # FROM … JOIN … (le premier alias porte les passages)
    id_expr: str                           # identifiant du passage
    vector_expr: str                       # colonne halfvec(1024), vecteurs L2-normalisés
    tsvector_expr: str | None = None       # colonne tsvector (configuration simple, sans accents) ; None = pas de plein texte hérité (BM25 seul)
    date_expr: str | None = None           # AAAA-MM-JJ (texte) ou NULL ; None = aucun bonus de fraîcheur
    collections_expr: str | None = None    # text[] des collections canoniques du document, pour le bonus
    collection_filter: str | None = None   # condition avec %(collections)s (text[]) ; None = pas de filtre par collection
    kind_expr: str | None = None           # colonne du type de passage, pour le filtre `types`
    unaccent_function: str = "knowledge.immutable_unaccent"
    # Plein texte BM25 (pg_search, migration 0005) : la table qui porte l'index (sans jointure, pour que le classement par score soit poussé dans l'index),
    # la colonne indexée, la clé de l'index et, facultatif, la colonne du type de passage.
    bm25_table_sql: str | None = None
    bm25_text_expr: str | None = None
    bm25_id_expr: str | None = None
    bm25_kind_expr: str | None = None
    # Restriction du plein texte par livre AVANT la limite (change filter-before-keyword-limit) : la colonne du livre sur la table de l'index et la table
    # des livres (alias que `collection_filter` et `date_expr` utilisent). None = les filtres de collection et de date s'appliquent après la limite.
    bm25_book_expr: str | None = None
    book_from_sql: str | None = None


# La bibliothèque : passages -> livres -> collections (les noms stockés peuvent encore être « veille » : repliés sur « watch »).
_COLLECTION_NAMES = ("SELECT CASE co.name WHEN 'veille' THEN 'watch' ELSE co.name END "
                     "FROM knowledge.book_collections bc JOIN knowledge.collections co ON co.id = bc.collection_id "
                     "WHERE bc.book_id = b.id")
LIBRARY_SPEC = HybridSpec(
    from_sql="knowledge.chunks c JOIN knowledge.books b ON b.id = c.book_id",
    id_expr="c.id",
    vector_expr="c.embedding",
    tsvector_expr="c.search_vector",
    date_expr="b.published_on",
    collections_expr=f"ARRAY({_COLLECTION_NAMES})",
    collection_filter=("EXISTS (SELECT 1 FROM knowledge.book_collections bc JOIN knowledge.collections co ON co.id = bc.collection_id "
                       "WHERE bc.book_id = b.id AND co.name = ANY(%(collections)s::text[]))"),
    kind_expr="c.kind",
    bm25_table_sql="knowledge.chunks c",
    bm25_text_expr="c.fts_text",
    bm25_id_expr="c.id",
    bm25_kind_expr="c.kind",
    bm25_book_expr="c.book_id",
    book_from_sql="knowledge.books b",
)


# ---------------------------------------------------------------------------
# Les mêmes calculs en Python pur (référence des tests)
# ---------------------------------------------------------------------------

# Drapeau de normalisation de ts_rank_cd (0 : aucune ; 1 : divise par 1 + log(longueur) ; 2 : divise par la longueur). BM25 (FTS5) pénalise
# les passages longs mais sature : sur des passages de taille voisine (environ 1 500 caractères) la correction est douce. Le drapeau 1 en est le
# plus proche ; le drapeau 2 est linéaire (trop fort) et ramène les scores vers 0,004, où l'arrondi à 3 décimales du classement créerait des égalités.
# Départage. Dans chaque liste : score arrondi à 3 décimales, fraîcheur décroissante, puis identifiant croissant. Après la fusion : à score égal,
# rang vectoriel croissant, les passages sans rang vectoriel en dernier, puis rang plein texte croissant, puis id.
NORMALISATION_RANG = 1


def words(query: str) -> list[str]:
    """Mots de la question : `re.findall(r"\\w+", query)`."""
    return re.findall(r"\w+", query, flags=re.UNICODE)


def freshness_bonus(published: str | None, collections, today: dt.date, bonus: float = FRESHNESS_BONUS,
                    half_life: int = FRESHNESS_HALF_LIFE) -> float:
    """Bonus de fraîcheur d'un document : décroissance par demi-vie pour un document daté
    de « watch » (hors la collection personnelle, OWN_COLLECTION), la moitié du bonus sinon ou si la date est illisible."""
    neutral = bonus * 0.5
    names = set(collections or ())
    if not published or not (names & set(FRESHNESS_COLLECTIONS)) or OWN_COLLECTION in names:
        return neutral
    try:
        age = max(0, (today - dt.date.fromisoformat(published[:10])).days)
    except ValueError:
        return neutral
    return bonus * 0.5 ** (age / half_life)


def fuse(ranked_lists, freshness, rrf_k: int = RRF_K, limit: int | None = None) -> list[tuple[object, float]]:
    """Fusion de rangs réciproque : `ranked_lists` = listes d'identifiants (meilleur d'abord), `freshness` = fonction id -> bonus.
    Rend [(id, score)] du meilleur au moins bon ; à score égal, l'ordre d'arrivée dans les listes."""
    fused: dict = {}
    for ranking in ranked_lists:
        for rank, item in enumerate(ranking):
            fused[item] = fused.get(item, 0.0) + 1.0 / (rrf_k + rank + 1)
    for item in fused:
        fused[item] += freshness(item)
    ordered = sorted(fused, key=fused.get, reverse=True)
    return [(item, fused[item]) for item in ordered[:limit]]


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

def vector_literal(vector) -> str:
    """Texte `[x1,x2,…]` accepté par les casts ::vector et ::halfvec (paramètre, jamais interpolé)."""
    return "[" + ",".join(f"{float(x):.8g}" for x in vector) + "]"


def _freshness_sql(spec: HybridSpec, bonus: float, half_life: int) -> str:
    neutral = repr(float(bonus) * 0.5)
    if not spec.date_expr or not spec.collections_expr:
        return neutral
    watch = ", ".join("'" + name + "'" for name in FRESHNESS_COLLECTIONS)      # constantes du module, pas des saisies
    sql = ("CASE WHEN @DATE@ IS NULL OR @DATE@ !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' "
           "OR NOT (@COLL@ && ARRAY[@WATCH@]::text[]) OR '@OWN@' = ANY(@COLL@) THEN @NEUTRAL@ "
           "ELSE @BONUS@ * power(0.5::float8, GREATEST(0, (%(today)s::date - (@DATE@)::date))::float8 / @HALF@) END")
    for token, value in (("@DATE@", spec.date_expr), ("@COLL@", spec.collections_expr), ("@WATCH@", watch),
                         ("@OWN@", OWN_COLLECTION), ("@NEUTRAL@", neutral), ("@BONUS@", repr(float(bonus))),
                         ("@HALF@", repr(float(half_life)))):
        sql = sql.replace(token, value)
    return sql


def build_query(spec: HybridSpec, *, query: str, vector, limit: int = 8, collections=None, since: str | None = None,
                kinds=None, today: dt.date | None = None, scan: str = DEFAULT_SCAN, fulltext: str = "bm25",
                bonus: float = FRESHNESS_BONUS, half_life: int = FRESHNESS_HALF_LIFE,
                rrf_k: int = RRF_K, candidates: int = CANDIDATES, diagnostic: bool = False,
                rank_norm: int | None = None, component: str = "hybrid") -> tuple[str, dict]:
    """(SQL, paramètres) de la recherche hybride. Lève ValueError pour un balayage, un plein texte ou une composante inconnus.
    `fulltext` : "bm25" (défaut, index pg_search de la migration 0005) ou "tsvector" (ts_rank_cd, pour comparer).
    `diagnostic=True` ajoute à la sortie les valeurs intermédiaires (rang et score de chaque voie, RRF, bonus) sans changer le classement ;
    la requête de production (diagnostic=False) classe exactement de la même façon."""
    if scan not in SCANS:
        raise ValueError(f"scan inconnu : {scan!r} (attendu : {', '.join(SCANS)})")
    if fulltext not in FULLTEXTS:
        raise ValueError(f"plein texte inconnu : {fulltext!r} (attendu : {', '.join(FULLTEXTS)})")
    if component not in COMPONENTS:
        raise ValueError(f"composante inconnue : {component!r} (attendu : {', '.join(COMPONENTS)})")
    if fulltext == "tsvector" and spec.tsvector_expr is None:
        raise ValueError("cette spécification n'a pas de colonne tsvector (tsvector_expr) : le plein texte « tsvector » est refusé")
    if fulltext == "bm25" and not (spec.bm25_table_sql and spec.bm25_text_expr and spec.bm25_id_expr):
        raise ValueError("cette spécification n'a pas d'index BM25 (bm25_table_sql, bm25_text_expr, bm25_id_expr)")
    norm = NORMALISATION_RANG if rank_norm is None else int(rank_norm)
    if norm not in (0, 1, 2):
        raise ValueError(f"normalisation inconnue : {rank_norm!r} (attendu : 0, 1 ou 2)")
    mots = words(query)
    params: dict = {"words": list(mots), "qvec": vector_literal(vector), "today": (today or dt.date.today()).isoformat()}
    conditions = []
    book_conditions = []      # les filtres qui portent sur le livre (collection, date), aussi appliqués avant la limite du plein texte
    if collections and spec.collection_filter:
        book_conditions.append(spec.collection_filter)
        params["collections"] = list(collections)
    if since and spec.date_expr:
        book_conditions.append(f"({spec.date_expr} IS NULL OR {spec.date_expr} >= %(since)s)")      # un livre (sans date) est gardé
        params["since"] = since
    conditions.extend(book_conditions)
    if kinds and spec.kind_expr:
        conditions.append(f"{spec.kind_expr} = ANY(%(kinds)s::text[])")
        params["kinds"] = list(kinds)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    n = int(candidates)
    if scan == "exact":
        # PRODUIT SCALAIRE (vecteurs @ requête, sans renormaliser). `<#>` rend l'opposé du produit scalaire.
        # Le cosinus (`<=>`) renormalise : il diffère du produit scalaire pour des vecteurs non unitaires et rend NaN pour un vecteur nul,
        # or PostgreSQL range NaN avant tous les nombres en tri décroissant : un tel passage sortirait premier de toutes les requêtes.
        # Cast en vector (float32) : calcul exact, sans l'index HNSW.
        score = "-(vec::vector <#> %(qvec)s::vector)"
        sem_source = f"SELECT id, fresh, {score} AS score FROM scope"
    else:
        score = "-(vec <#> %(qvec)s::halfvec)"
        sem_source = f"SELECT id, fresh, {score} AS score FROM scope ORDER BY vec <=> %(qvec)s::halfvec LIMIT {n}"
    # `scope` n'est JAMAIS matérialisée : référencée plusieurs fois, une CTE matérialisée recopierait tous les passages (vecteur de 1 024
    # dimensions, plein texte, bonus de fraîcheur) à chaque requête, même pour une seule voie ; inlinée, chaque voie ne lit que ce qu'elle utilise
    # (et l'index HNSW reste utilisable).
    use_sem = component in ("hybrid", "vector")
    use_kw = component in ("hybrid", "text")
    fused_source = " UNION ALL ".join(f"SELECT id, rank FROM {nom}" for nom, utilise in (("sem", use_sem), ("kw", use_kw)) if utilise)
    sem_extra = sem_extra_in = kw_extra = kw_extra_in = ""
    if diagnostic:      # colonnes en plus, jamais utilisées pour classer
        sem_extra, sem_extra_in = ", score AS sem_score", ", score"
        kw_extra = ", raw AS kw_raw"
    if fulltext == "tsvector":
        if diagnostic:
            kw_extra_in = f", ts_rank_cd(s.tsv, q.tsq, {norm}) AS raw"
        text_ctes = f"""q AS (
    SELECT to_tsquery('simple', string_agg(quote_literal({spec.unaccent_function}(lower(w))), ' | ')) AS tsq
    FROM unnest(%(words)s::text[]) AS w
),
kw AS (
    SELECT id, rank{kw_extra} FROM (
        SELECT s.id, row_number() OVER (ORDER BY round(ts_rank_cd(s.tsv, q.tsq, {norm})::numeric, 3) DESC, s.fresh DESC, s.id) - 1 AS rank{kw_extra_in}
        FROM scope s CROSS JOIN q
        WHERE s.tsv @@ q.tsq
    ) r WHERE rank < {n}
)"""
    else:
        # BM25 (pg_search) : le même OU de mots que FTS5 (`|||` = au moins un des mots, tokenisés comme l'index), les 4 x 50 meilleurs d'abord,
        # puis les 50 premiers. Le type de passage, la collection et la date s'appliquent AVANT la limite de 200 (change filter-before-keyword-limit) :
        # le type par une condition sur la table de l'index, la collection et la date par la liste des livres retenus (sous-requête sur les livres, sans
        # jointure dans `hits` : l'index ne porte que l'identifiant et le texte, et le classement par score reste poussé dans l'index). Sans filtre
        # de collection ni de date, la requête est celle d'avant.
        params["bm25_query"] = " ".join(mots)
        kind_condition = f" AND {spec.bm25_kind_expr} = ANY(%(kinds)s::text[])" if kinds and spec.bm25_kind_expr else ""
        book_condition = ""
        if book_conditions and spec.bm25_book_expr and spec.book_from_sql:
            book_condition = (f" AND {spec.bm25_book_expr} IN (SELECT b.id FROM {spec.book_from_sql} WHERE "
                              + " AND ".join(book_conditions) + ")")
        search_condition = f"{spec.bm25_text_expr} ||| %(bm25_query)s{kind_condition}{book_condition}" if mots else "FALSE"
        if diagnostic:
            kw_extra_in = ", h.raw AS raw"
        text_ctes = f"""hits AS (
    SELECT {spec.bm25_id_expr} AS id, pdb.score({spec.bm25_id_expr}) AS raw
    FROM {spec.bm25_table_sql}
    WHERE {search_condition}
    ORDER BY pdb.score({spec.bm25_id_expr}) DESC
    LIMIT {4 * n}
),
kw AS (
    SELECT id, rank{kw_extra} FROM (
        SELECT s.id, row_number() OVER (ORDER BY round(h.raw::numeric, 3) DESC, s.fresh DESC, s.id) - 1 AS rank{kw_extra_in}
        FROM hits h JOIN scope s ON s.id = h.id
    ) r WHERE rank < {n}
)"""
    joins, order_extra, final_extra = "", "", ""
    if use_sem:
        joins += "\nLEFT JOIN sem ON sem.id = f.id"
        order_extra += ", sem.rank ASC NULLS LAST"
    if use_kw:
        joins += "\nLEFT JOIN kw ON kw.id = f.id"
        order_extra += ", kw.rank ASC NULLS LAST"
    if diagnostic:
        final_extra = (", f.rrf, s.fresh, " + ("sem.rank AS sem_rank, sem.sem_score" if use_sem else "NULL::bigint AS sem_rank, NULL::float8 AS sem_score")
                       + ", " + ("kw.rank AS kw_rank, kw.kw_raw" if use_kw else "NULL::bigint AS kw_rank, NULL::float8 AS kw_raw"))
    sql = f"""
WITH scope AS NOT MATERIALIZED (
    SELECT {spec.id_expr} AS id, {spec.vector_expr} AS vec, {spec.tsvector_expr or "NULL::tsvector"} AS tsv,
           ({_freshness_sql(spec, bonus, half_life)}) AS fresh
    FROM {spec.from_sql}
    {where}
),
sem AS (
    SELECT id, rank{sem_extra} FROM (
        SELECT id, row_number() OVER (ORDER BY round(score::numeric, 3) DESC, fresh DESC, id) - 1 AS rank{sem_extra_in}
        FROM ({sem_source}) t
    ) r WHERE rank < {n}
),
{text_ctes},
fused AS (
    SELECT id, sum(1.0::float8 / ({int(rrf_k)} + rank + 1)) AS rrf
    FROM ({fused_source}) u
    GROUP BY id
)
SELECT f.id, f.rrf + s.fresh AS score{final_extra}
FROM fused f JOIN scope s ON s.id = f.id{joins}
ORDER BY score DESC{order_extra}, f.id
LIMIT {int(limit)}
"""
    return sql, params


def hybrid_search(conn, spec: HybridSpec, *, query: str, vector, limit: int = 8, collections=None, since: str | None = None,
                  kinds=None, today: dt.date | None = None, scan: str = DEFAULT_SCAN, ef_search: int = EF_SEARCH,
                  fulltext: str = "bm25", rank_norm: int | None = None,
                  component: str = "hybrid") -> list[tuple[int, float]]:
    """[(id, score)] du meilleur au moins bon. La connexion n'est utilisée qu'en lecture ; la transaction est fermée (rollback)."""
    sql, params = build_query(spec, query=query, vector=vector, limit=limit, collections=collections, since=since, kinds=kinds,
                              today=today, scan=scan, fulltext=fulltext, rank_norm=rank_norm,
                              component=component)
    if scan == "ann" and not 1 <= int(ef_search) <= 1000:
        raise ValueError(f"ef_search hors de 1 à 1000 : {ef_search!r}")
    try:
        with conn.cursor() as cursor:
            if scan == "ann":
                cursor.execute(f"SET LOCAL hnsw.ef_search = {int(ef_search)}")
                cursor.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")      # pgvector 0.8 : filtres sans perdre de résultats
            cursor.execute(sql, params)
            return [(row[0], float(row[1])) for row in cursor.fetchall()]
    finally:
        conn.rollback()


def diagnose(conn, spec: HybridSpec, *, query: str, vector, limit: int = 14, collections=None, since: str | None = None,
             kinds=None, today: dt.date | None = None, scan: str = DEFAULT_SCAN, rank_norm: int | None = None,
             fulltext: str = "bm25") -> list[dict]:
    """Valeurs intermédiaires de la recherche, dans l'ordre final : id, score, rrf (avant bonus), fresh, sem_rank, sem_score, kw_rank,
    kw_raw (score brut de BM25, ou de ts_rank_cd normalisé en mode tsvector). Pour comprendre un classement ; ne sert à aucune décision."""
    sql, params = build_query(spec, query=query, vector=vector, limit=limit, collections=collections, since=since, kinds=kinds,
                              today=today, scan=scan, diagnostic=True, rank_norm=rank_norm, fulltext=fulltext)
    colonnes = ("id", "score", "rrf", "fresh", "sem_rank", "sem_score", "kw_rank", "kw_raw")
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return [dict(zip(colonnes, row)) for row in cursor.fetchall()]
    finally:
        conn.rollback()
