-- Schéma touché : flow (redéfinition de trois vues agrégées de la tranche 1 de Mothra, mêmes colonnes dans le même ordre, aucune donnée, aucune table).
-- Change mothra-slices, tâche 15.2, décision de l'auteur R-20261030-08 : dans v_task_without_team_share, v_team_blocked_share et v_unplanned_share,
-- les comptes tasks_without_team, blocked et unplanned (écrits en CASE WHEN dans la migration 0026) passent par flow.mask_count, comme les autres
-- comptes des vues : la première barrière de masquage reste la fonction de masquage de la base, et le contrat des vues peut les déclarer
-- colonnes de compte (contrats/vues.json).
--
-- Jamais plus permissif que 0026 : flow.mask_count(n) rend NULL sous 5 et n sinon ; elle ne couvre pas le reste (tout moins partie). La condition de
-- reste de 0026 est donc gardée, à l'intérieur de l'appel :
--     tasks_without_team   avant : CASE WHEN p.sans >= 5 AND p.avec >= 5 THEN p.sans END
--                          après : flow.mask_count(CASE WHEN p.avec >= 5 THEN p.sans END)
--     blocked              avant : CASE WHEN p.b >= 5 AND p.r >= 5 THEN p.b END
--                          après : flow.mask_count(CASE WHEN p.r >= 5 THEN p.b END)
--     unplanned            avant : CASE WHEN p.u >= 5 AND p.r >= 5 THEN p.u END
--                          après : flow.mask_count(CASE WHEN p.r >= 5 THEN p.u END)
-- Les deux écritures sont égales : la partie est masquée sous 5 par flow.mask_count (NULL donne NULL), le reste par le CASE. share_percent est
-- inchangée, mot pour mot (la part n'est montrée que si la partie et le reste atteignent 5).
--
-- Droits : CREATE OR REPLACE VIEW conserve les droits de la migration 0026 (SELECT au seul rôle des vues) ; aucun GRANT ni REVOKE ici.

SET LOCAL ROLE pmzilla_owner;

CREATE OR REPLACE VIEW flow.v_task_without_team_share AS
WITH trimestres AS (
    SELECT (date_trunc('quarter', now() AT TIME ZONE 'UTC') - make_interval(months => 3 * k))::date AS quarter_start
    FROM generate_series(1, 4) AS k
),
taches AS (
    SELECT (date_trunc('quarter', i.resolved_at AT TIME ZONE 'UTC'))::date AS quarter_start, (i.team_id IS NULL) AS sans_equipe
    FROM flow.issues i
    WHERE i.out_of_export_at IS NULL
      AND lower(i.status_category) = 'done'
      AND i.resolved_at IS NOT NULL
      AND lower(i.type) = 'task'
),
par_trimestre AS (
    SELECT q.quarter_start, count(*) AS n, count(*) FILTER (WHERE x.sans_equipe) AS sans, count(*) FILTER (WHERE NOT x.sans_equipe) AS avec
    FROM taches x JOIN trimestres q ON q.quarter_start = x.quarter_start
    GROUP BY q.quarter_start
)
SELECT p.quarter_start,
       flow.mask_count(p.n) AS tasks_done,
       flow.mask_count(CASE WHEN p.avec >= 5 THEN p.sans END) AS tasks_without_team,
       CASE WHEN p.sans >= 5 AND p.avec >= 5 THEN round(100.0 * p.sans / p.n, 1) END AS share_percent
FROM par_trimestre p;

CREATE OR REPLACE VIEW flow.v_team_blocked_share AS
WITH trimestres AS (
    SELECT (date_trunc('quarter', now() AT TIME ZONE 'UTC') - make_interval(months => 3 * k))::date AS quarter_start
    FROM generate_series(1, 4) AS k
),
termines AS (
    SELECT i.key, i.team_id, t.name AS team, q.quarter_start
    FROM flow.issues i
    JOIN flow.teams t ON t.id = i.team_id
    JOIN trimestres q ON q.quarter_start = (date_trunc('quarter', i.resolved_at AT TIME ZONE 'UTC'))::date
    WHERE i.out_of_export_at IS NULL
      AND lower(i.status_category) = 'done'
      AND i.resolved_at IS NOT NULL
      AND lower(i.type) IN ('story', 'task')
),
marques AS (
    SELECT d.team, d.quarter_start,
           EXISTS (
               SELECT 1
               FROM flow.links l
               JOIN flow.ref_blocking_link_types b ON lower(btrim(b.type)) = lower(btrim(l.link_type))
               JOIN flow.issues autre ON autre.out_of_export_at IS NULL AND autre.team_id IS NOT NULL AND autre.team_id <> d.team_id
                                     AND autre.key = CASE WHEN l.source_key = d.key THEN l.target_key ELSE l.source_key END
               WHERE (l.source_key = d.key OR l.target_key = d.key)
                 AND ((b.direction = 'blocks'    AND ((l.source_key = autre.key AND l.direction = 'outward')
                                                      OR (l.source_key = d.key AND l.direction = 'inward')))
                   OR (b.direction = 'waits_for' AND ((l.source_key = d.key AND l.direction = 'outward')
                                                      OR (l.source_key = autre.key AND l.direction = 'inward'))))
           ) AS bloque
    FROM termines d
),
par_trimestre AS (
    SELECT team, quarter_start, count(*) AS n, count(*) FILTER (WHERE bloque) AS b, count(*) FILTER (WHERE NOT bloque) AS r
    FROM marques
    GROUP BY team, quarter_start
)
SELECT p.team, p.quarter_start,
       flow.mask_count(p.n) AS blocked_n,
       flow.mask_count(CASE WHEN p.r >= 5 THEN p.b END) AS blocked,
       CASE WHEN p.b >= 5 AND p.r >= 5 THEN round(100.0 * p.b / p.n, 1) END AS share_percent
FROM par_trimestre p;

CREATE OR REPLACE VIEW flow.v_unplanned_share AS
WITH trimestres AS (
    SELECT (date_trunc('quarter', now() AT TIME ZONE 'UTC') - make_interval(months => 3 * k))::date AS quarter_start
    FROM generate_series(1, 4) AS k
),
termines AS (
    SELECT q.quarter_start,
           EXISTS (SELECT 1 FROM flow.ref_unplanned_types u WHERE lower(btrim(u.type)) = lower(btrim(i.type))) AS non_planifie
    FROM flow.issues i
    JOIN trimestres q ON q.quarter_start = (date_trunc('quarter', i.resolved_at AT TIME ZONE 'UTC'))::date
    WHERE i.out_of_export_at IS NULL
      AND lower(i.status_category) = 'done'
      AND i.resolved_at IS NOT NULL
      AND (lower(i.type) IN ('story', 'task')
           OR EXISTS (SELECT 1 FROM flow.ref_unplanned_types u WHERE lower(btrim(u.type)) = lower(btrim(i.type))))
),
par_trimestre AS (
    SELECT quarter_start, count(*) AS n, count(*) FILTER (WHERE non_planifie) AS u, count(*) FILTER (WHERE NOT non_planifie) AS r
    FROM termines
    GROUP BY quarter_start
)
SELECT p.quarter_start,
       flow.mask_count(p.n) AS unplanned_n,
       flow.mask_count(CASE WHEN p.r >= 5 THEN p.u END) AS unplanned,
       CASE WHEN p.u >= 5 AND p.r >= 5 THEN round(100.0 * p.u / p.n, 1) END AS share_percent
FROM par_trimestre p;

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle
