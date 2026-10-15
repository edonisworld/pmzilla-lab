-- Schéma touché : knowledge (veille : articles, passages de collecte, liens cités ; pré-tri : références, notes, sauvetages, exclusions, partages, sélections du jour, notes fantômes, calibration).
-- Lot 5 : l'état de la veille et du pré-tri (aujourd'hui veille.sqlite et tri.sqlite) dans PostgreSQL, docs/pmzilla/application.md, 5.1.
-- Aucune donnée ici : la recopie se fait par tools/watch_copy.py. Aucun rôle, aucun mot de secret : les droits des deux rôles knowledge
-- sont aussi donnés explicitement en fin de fichier (lecture et écriture pour pmzilla_knowledge, lecture seule pour pmzilla_knowledge_ro).
--
-- Valeurs : horodatages en timestamptz, booléens en boolean, textes JSON en jsonb, vecteurs float16 en halfvec(1024) (valeurs exactes).
-- triage_calibration remplace la feuille de calibration comme lieu des avis : une ligne par article, donc un nouvel export ne duplique rien
-- et un avis survit à l'export.

SET LOCAL ROLE pmzilla_owner;

CREATE TABLE knowledge.watch_articles (
    url              text PRIMARY KEY,
    source           text NOT NULL,
    title            text NOT NULL,
    file             text NOT NULL,
    published        date,
    complete         boolean NOT NULL,
    collected        timestamptz NOT NULL,
    links_extracted  boolean NOT NULL DEFAULT false
);

CREATE TABLE knowledge.watch_source_runs (
    source    text PRIMARY KEY,
    last_try  timestamptz NOT NULL,
    last_ok   timestamptz,
    error     text
);

CREATE TABLE knowledge.watch_article_links (
    article_url  text NOT NULL REFERENCES knowledge.watch_articles (url) ON DELETE CASCADE,
    target_url   text NOT NULL,
    PRIMARY KEY (article_url, target_url)
);
CREATE INDEX watch_article_links_target ON knowledge.watch_article_links (target_url);

CREATE TABLE knowledge.triage_references (
    url        text PRIMARY KEY,
    title      text,
    origin     text,
    embedding  halfvec(1024) NOT NULL
);

CREATE TABLE knowledge.triage_scores (
    file             text PRIMARY KEY,
    url              text,
    title            text,
    source           text,
    published        date,
    collected        timestamptz,
    complete         boolean,
    embedding        halfvec(1024) NOT NULL,
    criteria         jsonb,
    substance        integer,
    summary          text,
    why              text,
    model            text,
    scored_at        timestamptz,
    location         text DEFAULT 'watch',
    justifications   jsonb,
    is_compilation   boolean,
    in_themes        boolean,
    is_promo         boolean
);

CREATE TABLE knowledge.triage_forced (
    file   text PRIMARY KEY,
    since  date
);

CREATE TABLE knowledge.triage_excluded (
    file   text PRIMARY KEY,
    since  date
);

CREATE TABLE knowledge.triage_shared (
    file       text PRIMARY KEY,
    url        text,
    post_date  date,
    found      date
);

CREATE TABLE knowledge.triage_daily_picks (
    day   date NOT NULL,
    file  text NOT NULL,
    PRIMARY KEY (day, file)
);

CREATE TABLE knowledge.triage_shadow_scores (
    url            text NOT NULL,
    language       text NOT NULL,
    model          text,
    prompts_hash   text,
    criteria       jsonb,
    substance      integer,
    is_compilation boolean,
    in_themes      boolean,
    is_promo       boolean,
    scored_at      timestamptz,
    PRIMARY KEY (url, language)
);

CREATE TABLE knowledge.triage_calibration (
    file            text PRIMARY KEY,
    exported_at     timestamptz NOT NULL,
    verdict         text NOT NULL CHECK (verdict IN ('keep', 'discard')),
    relevance       integer,
    substance       integer,
    in_themes       boolean,
    is_compilation  boolean,
    is_promo        boolean,
    missing         text,
    opinion         text CHECK (opinion IS NULL OR opinion IN ('keep', 'discard')),
    opinion_at      timestamptz
);

GRANT SELECT, INSERT, UPDATE, DELETE ON
    knowledge.watch_articles, knowledge.watch_source_runs, knowledge.watch_article_links,
    knowledge.triage_references, knowledge.triage_scores, knowledge.triage_forced, knowledge.triage_excluded,
    knowledge.triage_shared, knowledge.triage_daily_picks, knowledge.triage_shadow_scores, knowledge.triage_calibration
    TO pmzilla_knowledge;
GRANT SELECT ON
    knowledge.watch_articles, knowledge.watch_source_runs, knowledge.watch_article_links,
    knowledge.triage_references, knowledge.triage_scores, knowledge.triage_forced, knowledge.triage_excluded,
    knowledge.triage_shared, knowledge.triage_daily_picks, knowledge.triage_shadow_scores, knowledge.triage_calibration
    TO pmzilla_knowledge_ro;

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle
