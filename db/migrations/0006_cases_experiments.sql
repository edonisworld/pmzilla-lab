-- Schéma touché : cases (experiments, experiment_notes, cases ; index BM25 et HNSW ; déclencheur du critère de réussite).
-- Lot 2 : module des cas (docs/pmzilla/application.md, 5.2). Trois tables : les expériences en cours, leurs notes, les cas clos.
-- Aucune donnée, aucun rôle, aucun mot de secret ici : les droits viennent des privilèges par défaut posés par 0001 pour le propriétaire
-- (pmzilla_cases : lecture et écriture ; pmzilla_cases_ro : lecture), les droits d'usage de pdb et paradedb viennent de 0005.
--
-- Plein texte : la colonne générée fts_text (problème, chemin retenu, ce qui est testé) porte un index BM25 de même forme que
-- knowledge.chunks_bm25 (pdb.simple avec ascii_folding : minuscules, sans accents, sans racinisation). Le contexte est stocké, jamais cherché.
-- Les index HNSW utilisent halfvec_cosine_ops, comme knowledge.chunks.
--
-- Le critère de réussite s'écrit au lancement et ne se réécrit jamais : un déclencheur le refuse sur experiments et sur cases.

SET LOCAL ROLE pmzilla_owner;

-- Filet de sécurité de la 0005 : pas de travailleur parallèle pour la construction des index BM25 (segment de mémoire partagée).
SET LOCAL max_parallel_maintenance_workers = 0;

CREATE TABLE cases.experiments (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    author            text NOT NULL CHECK (btrim(author) <> ''),
    started_on        date NOT NULL,
    posture           text CHECK (posture IN ('discovery', 'delivery', 'scaling', 'facilitation', 'none')),
    status            text NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'closed', 'dropped')),
    problem           text NOT NULL CHECK (btrim(problem) <> ''),
    context           jsonb NOT NULL CHECK (jsonb_typeof(context) = 'object'),
    hypotheses        jsonb CHECK (hypotheses IS NULL OR jsonb_typeof(hypotheses) = 'array'),
    chosen_path       text,
    references_used   jsonb CHECK (references_used IS NULL OR jsonb_typeof(references_used) = 'array'),
    tested            text NOT NULL CHECK (btrim(tested) <> ''),
    expected_signal   text NOT NULL CHECK (btrim(expected_signal) <> ''),
    success_criterion text NOT NULL CHECK (btrim(success_criterion) <> ''),
    review_due        date NOT NULL,
    postponements     integer NOT NULL DEFAULT 0 CHECK (postponements >= 0),
    embedding         halfvec(1024),
    fts_text          text GENERATED ALWAYS AS (problem || ' ' || coalesce(chosen_path, '') || ' ' || tested) STORED,
    CHECK (review_due >= started_on)
);

CREATE TABLE cases.experiment_notes (
    id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    experiment_id  bigint NOT NULL REFERENCES cases.experiments (id),
    noted_on       date NOT NULL,
    note           text NOT NULL CHECK (btrim(note) <> '')
);

CREATE TABLE cases.cases (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    experiment_id     bigint NOT NULL UNIQUE REFERENCES cases.experiments (id),
    author            text NOT NULL CHECK (btrim(author) <> ''),
    posture           text CHECK (posture IN ('discovery', 'delivery', 'scaling', 'facilitation', 'none')),
    problem           text NOT NULL CHECK (btrim(problem) <> ''),
    context           jsonb NOT NULL CHECK (jsonb_typeof(context) = 'object'),
    hypotheses        jsonb CHECK (hypotheses IS NULL OR jsonb_typeof(hypotheses) = 'array'),
    chosen_path       text,
    references_used   jsonb CHECK (references_used IS NULL OR jsonb_typeof(references_used) = 'array'),
    tested            text NOT NULL CHECK (btrim(tested) <> ''),
    expected_signal   text NOT NULL CHECK (btrim(expected_signal) <> ''),
    success_criterion text NOT NULL CHECK (btrim(success_criterion) <> ''),
    launched_on       date NOT NULL,
    reviewed_on       date NOT NULL,
    history           jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(history) = 'array'),
    outcome           text NOT NULL CHECK (outcome IN ('worked', 'partly', 'failed', 'dropped')),
    drop_reason       text,
    what_got_stuck    text,
    confidence        text CHECK (confidence IS NULL OR confidence IN ('low', 'medium', 'high')),
    embedding         halfvec(1024) NOT NULL,
    fts_text          text GENERATED ALWAYS AS (problem || ' ' || coalesce(chosen_path, '') || ' ' || tested) STORED,
    CHECK (reviewed_on >= launched_on),
    CHECK (outcome <> 'dropped' OR (drop_reason IS NOT NULL AND btrim(drop_reason) <> ''))
);

CREATE FUNCTION cases.forbid_success_criterion_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF NEW.success_criterion IS DISTINCT FROM OLD.success_criterion THEN
        RAISE EXCEPTION 'success_criterion is written at launch and never rewritten' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$;

CREATE TRIGGER experiments_success_criterion_frozen
    BEFORE UPDATE OF success_criterion ON cases.experiments
    FOR EACH ROW EXECUTE FUNCTION cases.forbid_success_criterion_update();

CREATE TRIGGER cases_success_criterion_frozen
    BEFORE UPDATE OF success_criterion ON cases.cases
    FOR EACH ROW EXECUTE FUNCTION cases.forbid_success_criterion_update();

CREATE INDEX experiments_author_status_due ON cases.experiments (author, status, review_due);
CREATE INDEX experiment_notes_experiment_noted ON cases.experiment_notes (experiment_id, noted_on);
CREATE INDEX cases_outcome ON cases.cases (outcome);

CREATE INDEX experiments_embedding_hnsw ON cases.experiments USING hnsw (embedding halfvec_cosine_ops);
CREATE INDEX cases_embedding_hnsw ON cases.cases USING hnsw (embedding halfvec_cosine_ops);

CREATE INDEX experiments_bm25 ON cases.experiments
    USING bm25 (id, (fts_text::pdb.simple('ascii_folding=true')))
    WITH (key_field = 'id');

CREATE INDEX cases_bm25 ON cases.cases
    USING bm25 (id, (fts_text::pdb.simple('ascii_folding=true')))
    WITH (key_field = 'id');

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle
