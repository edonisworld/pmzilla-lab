-- Schéma touché : flow (flow.issues, deux tables de périodes, quatre vues agrégées) ; droits du rôle pmzilla_flow_views conservés.
-- R-58 (alignement RGPD de l'export Jira, design D20) : trois ajouts, aucune donnée dans cette migration.
--   1. flow.issues.out_of_export_at : instant où le ticket est sorti de l'export (il ne remplit plus la règle d'un an ou n'est plus
--      dans le périmètre). Nul pour un ticket dans l'export. Renseigné par tools/flow_import.py, jamais à la main. Les vues et les
--      lecteurs de tools/flow_store.py écartent les tickets marqués : un rapport de la base égale celui des fichiers CSV du jour.
--   2. flow.issue_label_periods : périodes des étiquettes DÉCLARÉES seulement (jamais une étiquette non déclarée), un ajout et un
--      retrait par ligne ; removed_at nul = étiquette encore posée.
--   3. flow.issue_version_periods : périodes de fixVersion, même forme.
-- Ni colonne de personne, ni PO, ni titre, ni description : le schéma flow ne porte aucune donnée personnelle (D3, D20).
-- Les deux tables partent avec leur ticket (ON DELETE CASCADE). Droits, motif existant : le rôle d'import (pmzilla_flow) écrit,
-- le rôle de lecture seule (pmzilla_flow_ro) lit, le rôle des vues (pmzilla_flow_views) ne lit que les vues.

SET LOCAL ROLE pmzilla_owner;

ALTER TABLE flow.issues ADD COLUMN out_of_export_at timestamptz;
CREATE INDEX issues_out_of_export ON flow.issues (out_of_export_at) WHERE out_of_export_at IS NOT NULL;

CREATE TABLE flow.issue_label_periods (
    issue_key  text NOT NULL REFERENCES flow.issues (key) ON DELETE CASCADE,
    label      text NOT NULL,                  -- étiquette déclarée (réglage labels) ; les autres ne sont que comptées, jamais écrites
    added_at   timestamptz NOT NULL,
    removed_at timestamptz,                    -- nul : étiquette encore posée
    PRIMARY KEY (issue_key, label, added_at),
    CHECK (removed_at IS NULL OR removed_at >= added_at)
);

CREATE TABLE flow.issue_version_periods (
    issue_key  text NOT NULL REFERENCES flow.issues (key) ON DELETE CASCADE,
    version    text NOT NULL,                  -- fixVersion ; aucun rapport n'imprime ce nom (clé de cycle seulement)
    added_at   timestamptz NOT NULL,
    removed_at timestamptz,                    -- nul : version encore posée
    PRIMARY KEY (issue_key, version, added_at),
    CHECK (removed_at IS NULL OR removed_at >= added_at)
);

-- Vues agrégées : mêmes colonnes et mêmes droits qu'en 0002 (CREATE OR REPLACE conserve les droits), les tickets marqués en moins.
-- Un lien vers un ticket marqué se lit comme un lien vers un ticket hors export : la jointure de la cible ignore les marqués.
CREATE OR REPLACE VIEW flow.v_team_status AS
SELECT coalesce(t.name, '(sans équipe)') AS team, i.type, i.status_category, i.status,
       flow.mask_count(count(*)) AS tickets
FROM flow.issues i LEFT JOIN flow.teams t ON t.id = i.team_id
WHERE i.out_of_export_at IS NULL
GROUP BY 1, 2, 3, 4;

CREATE OR REPLACE VIEW flow.v_team_weekly_resolved AS
SELECT coalesce(t.name, '(sans équipe)') AS team, i.type,
       (date_trunc('week', i.resolved_at AT TIME ZONE 'UTC'))::date AS week_start,
       flow.mask_count(count(*)) AS tickets
FROM flow.issues i LEFT JOIN flow.teams t ON t.id = i.team_id
WHERE i.resolved_at IS NOT NULL AND i.out_of_export_at IS NULL
GROUP BY 1, 2, 3;

CREATE OR REPLACE VIEW flow.v_team_open_age AS
SELECT team, status_category, age_bucket, flow.mask_count(count(*)) AS tickets
FROM (
    SELECT coalesce(t.name, '(sans équipe)') AS team, i.status_category,
           CASE WHEN now() - i.created_at < interval '8 days'  THEN '0-7 j'
                WHEN now() - i.created_at < interval '31 days' THEN '8-30 j'
                WHEN now() - i.created_at < interval '91 days' THEN '31-90 j'
                ELSE '91 j et plus' END AS age_bucket
    FROM flow.issues i LEFT JOIN flow.teams t ON t.id = i.team_id
    WHERE i.resolved_at IS NULL AND i.out_of_export_at IS NULL
) ouverts
GROUP BY 1, 2, 3;

CREATE OR REPLACE VIEW flow.v_team_dependencies AS
SELECT coalesce(ts.name, '(sans équipe)') AS source_team, coalesce(tt.name, '(sans équipe)') AS target_team,
       l.link_type, flow.mask_count(count(*)) AS links
FROM flow.links l
JOIN flow.issues s ON s.key = l.source_key AND s.out_of_export_at IS NULL
LEFT JOIN flow.teams ts ON ts.id = s.team_id
LEFT JOIN flow.issues d ON d.key = l.target_key AND d.out_of_export_at IS NULL
LEFT JOIN flow.teams tt ON tt.id = d.team_id
GROUP BY 1, 2, 3;

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle

-- Droits explicites (les droits par défaut du lot 1 les donnent déjà : on les écrit pour qu'ils se lisent ici). Le rôle des vues
-- n'a rien sur ces tables, ni sur la nouvelle colonne : il ne lit que les vues v_*.
GRANT SELECT, INSERT, UPDATE, DELETE ON flow.issue_label_periods, flow.issue_version_periods TO pmzilla_flow;
GRANT SELECT ON flow.issue_label_periods, flow.issue_version_periods TO pmzilla_flow_ro;
