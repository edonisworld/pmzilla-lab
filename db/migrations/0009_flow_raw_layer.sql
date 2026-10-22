-- Schéma touché : flow (trois tables de la couche brute datée) ; droits des rôles pmzilla_flow, pmzilla_flow_ro et pmzilla_flow_views.
-- Change jira-data-architecture (R-70, design D2, D3, D13) : la couche brute datée de l'export Jira. Aucune donnée, aucun mot de
-- passe, aucun rôle créé ni modifié dans cette migration (le mot de passe du rôle d'import se pose avec db.py role-password).
--
--   flow.raw_runs               un passage par export réussi (kind export), par amorçage (seed) ; history est réservé à R-69.
--                               Instant, nombre de requêtes nommées lues, toutes lues ou non. Ni nom de fichier, ni nom de requête.
--   flow.raw_run_sightings      les clés de tickets lues par un passage, après l'écart de conservation. Une ligne par clé et par passage.
--   flow.raw_issue_snapshots    les attributs autorisés d'un ticket quand ils changent : projet, type, état, catégorie, dates,
--                               résolution, story points, clé du parent, équipes dans l'ordre des colonnes (nom traduit et
--                               identifiant d'équipe Jira, JSON), liens (JSON, nul = liens non suivis), empreinte du contenu,
--                               instantané d'amorçage ou non. Ni titre, ni description, ni personne, ni étiquette, ni version.
--
-- Pas de clé étrangère vers flow.issues : la purge de conservation supprime ticket et couche brute dans la même transaction.
-- Droits : le rôle d'import (pmzilla_flow) lit, insère et supprime (la suppression est celle de la purge, jamais une mise à jour :
-- la couche brute est en ajout seulement, donc aucun droit UPDATE). Le rôle en lecture seule (pmzilla_flow_ro) et le rôle des vues
-- (pmzilla_flow_views) n'ont aucun droit sur ces tables ; les quatre vues ne les lisent pas.

SET LOCAL ROLE pmzilla_owner;

CREATE TABLE flow.raw_runs (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind             text NOT NULL CHECK (kind IN ('export', 'seed', 'history')),
    run_at           timestamptz NOT NULL DEFAULT now(),
    queries_searched integer NOT NULL DEFAULT 0 CHECK (queries_searched >= 0),
    all_queries      boolean NOT NULL DEFAULT false      -- vrai si chaque requête nommée des réglages a été lue (faux pour --query)
);

CREATE TABLE flow.raw_run_sightings (
    run_id    bigint NOT NULL REFERENCES flow.raw_runs (id),
    issue_key text NOT NULL,
    PRIMARY KEY (run_id, issue_key)
);
CREATE INDEX raw_run_sightings_key ON flow.raw_run_sightings (issue_key, run_id);

CREATE TABLE flow.raw_issue_snapshots (
    issue_key                  text NOT NULL,
    run_id                     bigint NOT NULL REFERENCES flow.raw_runs (id),
    updated_at                 timestamptz NOT NULL,
    project                    text NOT NULL,
    type                       text NOT NULL,
    status                     text NOT NULL,
    status_category            text,
    created_at                 timestamptz NOT NULL,
    resolved_at                timestamptz,
    resolution                 text,
    status_category_changed_at timestamptz,
    story_points               numeric,
    parent_key                 text,
    teams                      jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(teams) = 'array'),    -- [{"name": ..., "jira_team_id": ... ou null}], ordre des colonnes
    links                      jsonb CHECK (links IS NULL OR jsonb_typeof(links) = 'array'),                -- [{"target", "type", "direction"}] ; nul : liens non suivis
    content_hash               text NOT NULL,
    seeded                     boolean NOT NULL DEFAULT false,
    PRIMARY KEY (issue_key, run_id)
);

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle

-- Les droits par défaut du lot 1 donnent toutes les opérations au rôle d'import et la lecture au rôle en lecture seule sur toute
-- nouvelle table du schéma : on les retire pour ces trois tables, puis on donne seulement ce qui est voulu.
REVOKE ALL ON flow.raw_runs, flow.raw_run_sightings, flow.raw_issue_snapshots FROM pmzilla_flow, pmzilla_flow_ro, pmzilla_flow_views;
REVOKE ALL ON SEQUENCE flow.raw_runs_id_seq FROM pmzilla_flow_ro, pmzilla_flow_views;
GRANT SELECT, INSERT, DELETE ON flow.raw_runs, flow.raw_run_sightings, flow.raw_issue_snapshots TO pmzilla_flow;
