-- Schéma touché : flow (tables, vues agrégées, fonction de masquage) ; rôle du cluster pmzilla_flow_views.
-- Lot 6 : Jira en base, sur le Mac (docs/pmzilla/application.md, 5.3). Aucun titre, aucune description, aucun auteur,
-- aucune donnée individuelle : le test de la migration vérifie qu'aucune colonne n'a ce nom.
--
-- Les tables portent des clés de tickets : Claude Code ne les lit jamais (règles deny, application.md 4). Il ne lit que
-- les vues v_*, par tools/flow_views.py, avec le rôle pmzilla_flow_views (NOLOGIN ici ; le mot de passe est posé hors fichier
-- par `uv run tools/db.py role-password pmzilla_flow_views`). Une vue s'exécute avec les droits de son propriétaire : le rôle
-- n'a de droit que sur les vues, aucun sur les tables. Une cellule de moins de 5 tickets est masquée (NULL) dans la vue
-- même ; flow_views.py peut masquer davantage (flux.yaml), jamais moins.

SET LOCAL ROLE pmzilla_owner;

CREATE TABLE flow.teams (
    id   integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL UNIQUE                -- valeur du champ équipe de Jira ; les noms ne vivent que dans la base
);

CREATE TABLE flow.issues (
    key                         text PRIMARY KEY,
    project                     text NOT NULL,
    type                        text NOT NULL,
    status                      text NOT NULL,
    status_category             text,
    created_at                  timestamptz NOT NULL,
    resolved_at                 timestamptz,            -- à la minute : règle des fermetures groupées
    resolution                  text,
    status_category_changed_at  timestamptz,            -- « debut » de flux_jira.py (dormants, âges)
    story_points                numeric,
    updated_at                  timestamptz NOT NULL,   -- champ Updated de l'export API : base de l'import incrémental
    team_id                     integer REFERENCES flow.teams (id),   -- première équipe du ticket (attribution)
    parent_key                  text
);
CREATE INDEX issues_project_resolved ON flow.issues (project, resolved_at);
CREATE INDEX issues_team ON flow.issues (team_id);
CREATE INDEX issues_parent ON flow.issues (parent_key);
CREATE INDEX issues_updated ON flow.issues (updated_at);

-- Toutes les équipes d'un ticket (comptage), dans l'ordre des colonnes de l'export ; team_id de issues = position 1.
CREATE TABLE flow.issue_teams (
    issue_key text NOT NULL REFERENCES flow.issues (key) ON DELETE CASCADE,
    team_id   integer NOT NULL REFERENCES flow.teams (id),
    position  smallint NOT NULL,
    PRIMARY KEY (issue_key, team_id)
);
CREATE INDEX issue_teams_team ON flow.issue_teams (team_id);

CREATE TABLE flow.transitions (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    issue_key       text NOT NULL REFERENCES flow.issues (key) ON DELETE CASCADE,
    transitioned_at timestamptz NOT NULL,
    from_status     text,
    to_status       text NOT NULL
);
CREATE INDEX transitions_issue_time ON flow.transitions (issue_key, transitioned_at);
CREATE INDEX transitions_to_status ON flow.transitions (to_status);
CREATE UNIQUE INDEX transitions_unique ON flow.transitions (issue_key, transitioned_at, COALESCE(from_status, ''), to_status);

-- link_type : '' pour un lien sans type (colonne de lien simple de l'export) ; direction : inward, outward ou NULL.
CREATE TABLE flow.links (
    id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_key text NOT NULL REFERENCES flow.issues (key) ON DELETE CASCADE,
    target_key text NOT NULL,
    link_type  text NOT NULL,
    direction  text CHECK (direction IN ('inward', 'outward'))
);
CREATE INDEX links_source ON flow.links (source_key);
CREATE INDEX links_target ON flow.links (target_key);
CREATE UNIQUE INDEX links_unique ON flow.links (source_key, target_key, link_type, COALESCE(direction, ''));

-- Masquage : une cellule de moins de 5 tickets n'est pas rendue.
CREATE FUNCTION flow.mask_count(n bigint) RETURNS bigint
    LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$ SELECT CASE WHEN n < 5 THEN NULL ELSE n END $$;
REVOKE ALL ON FUNCTION flow.mask_count(bigint) FROM PUBLIC;

-- Vues agrégées par équipe : aucune clé de ticket, aucune colonne individuelle.
CREATE VIEW flow.v_team_status AS
SELECT coalesce(t.name, '(sans équipe)') AS team, i.type, i.status_category, i.status,
       flow.mask_count(count(*)) AS tickets
FROM flow.issues i LEFT JOIN flow.teams t ON t.id = i.team_id
GROUP BY 1, 2, 3, 4;

CREATE VIEW flow.v_team_weekly_resolved AS
SELECT coalesce(t.name, '(sans équipe)') AS team, i.type,
       (date_trunc('week', i.resolved_at AT TIME ZONE 'UTC'))::date AS week_start,
       flow.mask_count(count(*)) AS tickets
FROM flow.issues i LEFT JOIN flow.teams t ON t.id = i.team_id
WHERE i.resolved_at IS NOT NULL
GROUP BY 1, 2, 3;

CREATE VIEW flow.v_team_open_age AS
SELECT team, status_category, age_bucket, flow.mask_count(count(*)) AS tickets
FROM (
    SELECT coalesce(t.name, '(sans équipe)') AS team, i.status_category,
           CASE WHEN now() - i.created_at < interval '8 days'  THEN '0-7 j'
                WHEN now() - i.created_at < interval '31 days' THEN '8-30 j'
                WHEN now() - i.created_at < interval '91 days' THEN '31-90 j'
                ELSE '91 j et plus' END AS age_bucket
    FROM flow.issues i LEFT JOIN flow.teams t ON t.id = i.team_id
    WHERE i.resolved_at IS NULL
) ouverts
GROUP BY 1, 2, 3;

CREATE VIEW flow.v_team_dependencies AS
SELECT coalesce(ts.name, '(sans équipe)') AS source_team, coalesce(tt.name, '(sans équipe)') AS target_team,
       l.link_type, flow.mask_count(count(*)) AS links
FROM flow.links l
JOIN flow.issues s ON s.key = l.source_key
LEFT JOIN flow.teams ts ON ts.id = s.team_id
LEFT JOIN flow.issues d ON d.key = l.target_key
LEFT JOIN flow.teams tt ON tt.id = d.team_id
GROUP BY 1, 2, 3;

-- Le rôle des vues : aucun droit sur les tables, SELECT sur les vues seulement (les droits par défaut du lot 1 ne le visent pas).
RESET ROLE;
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pmzilla_flow_views') THEN
        CREATE ROLE pmzilla_flow_views NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO pmzilla_flow_views', current_database());
END
$$;
GRANT USAGE ON SCHEMA flow TO pmzilla_flow_views;
GRANT EXECUTE ON FUNCTION flow.mask_count(bigint) TO pmzilla_flow_views;     -- une fonction d'une vue est vérifiée pour l'appelant
GRANT SELECT ON flow.v_team_status, flow.v_team_weekly_resolved, flow.v_team_open_age, flow.v_team_dependencies
    TO pmzilla_flow_views;
