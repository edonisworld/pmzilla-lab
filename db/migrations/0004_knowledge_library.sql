-- Schéma touché : knowledge (bibliothèque : books, collections, book_collections, chunks) ; public (extension unaccent).
-- Lot 4 : la bibliothèque (aujourd'hui library.sqlite) dans PostgreSQL, docs/pmzilla/application.md, 5.1. Aucune donnée ici : la recopie
-- se fait par tools/knowledge_import.py, sans reconversion des livres ni recalcul des vecteurs (bge-m3, 1024 dimensions, L2-normalisés).
--
-- Plein texte : configuration `simple` (pas de racinisation, comme FTS5 `unicode61`) sur le texte débarrassé de ses accents
-- (`remove_diacritics 2` de FTS5). `unaccent` n'est pas IMMUABLE : l'enveloppe knowledge.immutable_unaccent l'est, ce qui permet la
-- colonne générée. Un index BM25 (pg_search) peut s'y ajouter par une migration ultérieure, sans changer les tables.
--
-- `meta` est la copie exacte du JSON des métadonnées de SQLite (url, author, published, source des articles ; author des livres) : la
-- recherche rend ces champs tels quels. `author` et `published_on` en sont tirés (colonnes générées) pour les filtres.

CREATE EXTENSION IF NOT EXISTS unaccent;      -- superutilisateur, avant de prendre le rôle propriétaire

SET LOCAL ROLE pmzilla_owner;

CREATE FUNCTION knowledge.immutable_unaccent(texte text) RETURNS text
    LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
    AS $$ SELECT public.unaccent('public.unaccent'::regdictionary, texte) $$;

CREATE TABLE knowledge.books (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    file_name   text NOT NULL UNIQUE,
    title       text NOT NULL,
    author      text GENERATED ALWAYS AS (meta ->> 'author') STORED,
    published_on text GENERATED ALWAYS AS (left(meta ->> 'published', 10)) STORED,   -- AAAA-MM-JJ, NULL pour un livre
    meta        jsonb NOT NULL DEFAULT '{}',
    sha256      text NOT NULL,
    model       text NOT NULL,
    indexed_at  timestamptz NOT NULL
);
CREATE INDEX books_sha256 ON knowledge.books (sha256);

CREATE TABLE knowledge.collections (
    id    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name  text NOT NULL UNIQUE
);

CREATE TABLE knowledge.book_collections (
    book_id        bigint NOT NULL REFERENCES knowledge.books (id) ON DELETE CASCADE,
    collection_id  bigint NOT NULL REFERENCES knowledge.collections (id),
    PRIMARY KEY (book_id, collection_id)
);
CREATE INDEX book_collections_collection ON knowledge.book_collections (collection_id);

CREATE TABLE knowledge.chunks (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    book_id        bigint NOT NULL REFERENCES knowledge.books (id) ON DELETE CASCADE,
    position       integer NOT NULL,
    section        text NOT NULL,
    text           text NOT NULL,
    embedding      halfvec(1024) NOT NULL,
    kind           text NOT NULL DEFAULT 'text' CHECK (kind IN ('text', 'figure')),
    ref            jsonb NOT NULL DEFAULT '{}',
    search_vector  tsvector GENERATED ALWAYS AS (
        to_tsvector('simple', knowledge.immutable_unaccent(section || ' ' || text))
    ) STORED
);
CREATE INDEX chunks_book_position ON knowledge.chunks (book_id, position);
CREATE INDEX chunks_kind ON knowledge.chunks (kind);
CREATE INDEX chunks_search_vector ON knowledge.chunks USING gin (search_vector);
CREATE INDEX chunks_embedding_hnsw ON knowledge.chunks USING hnsw (embedding halfvec_cosine_ops);

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle
