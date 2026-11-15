-- Schéma touché : flow (une vue interne flow.v_t3_withheld, deux vues agrégées redéfinies avec les mêmes colonnes dans le même ordre ; aucune donnée, aucune table).
-- Change masking-sums, conception D17, relation T3 de D16 (décision de l'auteur R-20261031-07, question tranchée 19). Le débit trimestriel de
-- v_team_lead_time_throughput est la somme des cellules hebdomadaires Story et Task de v_team_weekly_resolved sur les semaines du trimestre (T3). Les
-- vues de 0008 et de 0026 masquaient chacune de leur côté : un débit masqué (au plus 4) sur des lignes hebdomadaires masquées (au moins 1 chacune)
-- laissait lire les lignes, et un débit visible sur des lignes masquées laissait lire leur somme.
--
--   flow.v_t3_withheld (team, quarter_start)   les équipes et les trimestres (les quatre derniers terminés) dont les lignes hebdomadaires Story et Task sont
--                                              retirées. Vue interne : propriétaire seul, aucun rôle n'a de droit dessus ; les deux vues ci-dessous la lisent
--                                              avec les droits de leur propriétaire. Aucune fonction appelée avec les droits de l'appelant.
--   flow.v_team_weekly_resolved                 mêmes colonnes ; les lignes Story et Task d'une équipe et d'une semaine qui touche un trimestre retiré sont absentes.
--   flow.v_team_lead_time_throughput            mêmes colonnes ; le débit d'un trimestre retiré est masqué, et ses effectifs liés avec lui (règle des paires et
--                                              règle de série de 0026, qui tournent avec cette cellule masquée).
--
-- Règle (a), débit masqué : sous 5 ou par la règle (b) ci-dessous, aucune ligne Story ni Task de l'équipe n'est publiée pour une semaine qui touche le
-- trimestre (une semaine à cheval sur une limite comprise). Les autres types gardent leurs règles.
-- Règle (b), débit visible : n le débit, k les lignes hebdomadaires masquées (sous 5) de l'équipe sur les semaines du trimestre, S = n moins les cellules
-- visibles (au moins 5) de ces lignes. Les lignes ne sont publiées que si les quatre conditions tiennent ; sinon le débit est masqué, puis la règle (a).
-- lo = 1 et hi = 4 (BORNES de tools/flow_views.py, v_team_weekly_resolved.tickets : sans drapeau de complément, hi = seuil - 1).
-- T3-READINGS: the two weeks straddling a quarter limit are each counted in the quarter or not (four readings); a reading whose S is outside [k * lo, k * hi] is dropped as inconsistent; the rows are published only when every reading left passes.
-- T3-CONDITIONS: publish only when k >= 2 and S >= T and S != k * lo and S != k * hi, with S = n - the visible weekly cells, k the masked rows, lo and hi from BORNES.
-- Au plancher T = 5, lo = 1, hi = 4 : k >= 2, S >= 5, S <> k, S <> 4 * k ; une lecture sans ligne masquée (k = 0) n'a rien à cacher ; une lecture
-- dont S sort de [k, 4 * k] est écartée. Les semaines sont des lundis UTC (date_trunc('week')), comme dans 0008 ; la semaine d'une ligne touche le
-- trimestre qui commence en d si lundi + 7 > d et lundi < d + 3 mois ; elle est « dans » le trimestre si lundi >= d et lundi + 7 <= d + 3 mois.
-- Même règle dans tools/flow_views.py (lignes_publiees, masquer_vue) et mothra/contract/src/masquage.ts (masquerVue) ; un test compare les deux lignes T3.
--
-- Jamais plus permissif que 0008 et 0026 : seuls des retraits et des masquages s'ajoutent. Tombe avec la propagation de D15 quand le groupe 7 de
-- masking-sums déclare T3 dans son unité (tâche 7.6). Droits : la vue interne est retirée à tous les rôles ; CREATE OR REPLACE VIEW conserve les droits
-- des deux autres vues (SELECT au seul rôle des vues).

SET LOCAL ROLE pmzilla_owner;

CREATE VIEW flow.v_t3_withheld AS
WITH trimestres AS (
    SELECT (date_trunc('quarter', now() AT TIME ZONE 'UTC') - make_interval(months => 3 * k))::date AS quarter_start
    FROM generate_series(1, 4) AS k       -- les quatre derniers trimestres terminés, comme v_team_lead_time_throughput
),
debit AS (          -- le débit vrai : mêmes tickets que v_team_lead_time_throughput (équipe du ticket, Story et Task terminées)
    SELECT t.name AS team, (date_trunc('quarter', i.resolved_at AT TIME ZONE 'UTC'))::date AS quarter_start, count(*) AS n
    FROM flow.issues i
    JOIN flow.teams t ON t.id = i.team_id
    WHERE i.out_of_export_at IS NULL
      AND lower(i.status_category) = 'done'
      AND i.resolved_at IS NOT NULL
      AND lower(i.type) IN ('story', 'task')
    GROUP BY 1, 2
),
semaines AS (       -- les lignes de v_team_weekly_resolved pour Story et Task, avec leur vrai compte
    SELECT t.name AS team, i.type, (date_trunc('week', i.resolved_at AT TIME ZONE 'UTC'))::date AS week_start, count(*) AS c
    FROM flow.issues i
    JOIN flow.teams t ON t.id = i.team_id
    WHERE i.resolved_at IS NOT NULL
      AND i.out_of_export_at IS NULL
      AND lower(i.type) IN ('story', 'task')
    GROUP BY 1, 2, 3
),
lectures AS (       -- une ligne par équipe, trimestre et lecture des deux semaines à cheval (début compté dans le trimestre ou non, fin de même)
    SELECT d.team, d.quarter_start, d.n,
           count(s.c) FILTER (WHERE s.c < 5) AS k,
           coalesce(sum(s.c) FILTER (WHERE s.c >= 5), 0) AS v
    FROM debit d
    JOIN trimestres q ON q.quarter_start = d.quarter_start
    CROSS JOIN (VALUES (false), (true)) AS a(avec_debut)
    CROSS JOIN (VALUES (false), (true)) AS b(avec_fin)
    LEFT JOIN semaines s
           ON s.team = d.team
          AND s.week_start + 7 > d.quarter_start
          AND s.week_start < (d.quarter_start + interval '3 months')::date
          AND ((s.week_start >= d.quarter_start AND s.week_start + 7 <= (d.quarter_start + interval '3 months')::date)      -- semaine dans le trimestre
               OR (s.week_start < d.quarter_start AND a.avec_debut)                                                            -- à cheval sur le début
               OR (s.week_start + 7 > (d.quarter_start + interval '3 months')::date AND b.avec_fin))                          -- à cheval sur la fin
    GROUP BY d.team, d.quarter_start, d.n, a.avec_debut, b.avec_fin
)
SELECT team, quarter_start
FROM lectures
GROUP BY team, quarter_start
HAVING max(n) < 5                                                                       -- règle (a) : débit sous le plancher
    OR bool_or(k >= 1 AND n - v BETWEEN k AND 4 * k                                     -- règle (b) : lecture cohérente avec des lignes masquées
               AND NOT (k >= 2 AND n - v >= 5 AND n - v <> k AND n - v <> 4 * k));      -- et une des quatre conditions échoue

CREATE OR REPLACE VIEW flow.v_team_weekly_resolved AS
SELECT coalesce(t.name, '(sans équipe)') AS team, i.type,
       (date_trunc('week', i.resolved_at AT TIME ZONE 'UTC'))::date AS week_start,
       flow.mask_count(count(*)) AS tickets
FROM flow.issues i LEFT JOIN flow.teams t ON t.id = i.team_id
WHERE i.resolved_at IS NOT NULL AND i.out_of_export_at IS NULL
  AND NOT (lower(i.type) IN ('story', 'task')            -- règle (a) : les lignes Story et Task d'un trimestre retiré sont absentes
           AND EXISTS (SELECT 1 FROM flow.v_t3_withheld w
                       WHERE w.team = t.name
                         AND (date_trunc('week', i.resolved_at AT TIME ZONE 'UTC'))::date + 7 > w.quarter_start
                         AND (date_trunc('week', i.resolved_at AT TIME ZONE 'UTC'))::date < (w.quarter_start + interval '3 months')::date))
GROUP BY 1, 2, 3;

CREATE OR REPLACE VIEW flow.v_team_lead_time_throughput AS
WITH trimestres AS (
    SELECT (date_trunc('quarter', now() AT TIME ZONE 'UTC') - make_interval(months => 3 * k))::date AS quarter_start
    FROM generate_series(1, 4) AS k       -- les quatre derniers trimestres terminés : le trimestre en cours n'y est jamais
),
termines AS (
    SELECT i.key, t.name AS team,
           (date_trunc('quarter', i.resolved_at AT TIME ZONE 'UTC'))::date AS quarter_start,
           i.created_at, i.resolved_at,
           (SELECT min(x.transitioned_at)
              FROM flow.transitions x
              JOIN flow.ref_flow_statuses s ON lower(btrim(s.status)) = lower(btrim(x.to_status)) AND s.is_committed
             WHERE x.issue_key = i.key) AS engage_le
    FROM flow.issues i
    JOIN flow.teams t ON t.id = i.team_id          -- rattachement par l'équipe du ticket seulement : jamais par lien, parent ou épic
    WHERE i.out_of_export_at IS NULL
      AND lower(i.status_category) = 'done'
      AND i.resolved_at IS NOT NULL
      AND lower(i.type) IN ('story', 'task')
),
mesures AS (
    SELECT d.team, d.quarter_start,
           CASE WHEN d.resolved_at >= d.created_at THEN extract(epoch FROM (d.resolved_at - d.created_at)) / 86400.0 END AS lead_days,
           CASE WHEN d.engage_le IS NOT NULL AND d.resolved_at >= d.engage_le
                THEN extract(epoch FROM (d.resolved_at - d.engage_le)) / 86400.0 END AS cycle_days,
           (d.engage_le IS NOT NULL AND d.resolved_at >= d.engage_le AND d.created_at < d.engage_le - interval '1 year') AS ancien
    FROM termines d JOIN trimestres q ON q.quarter_start = d.quarter_start
),
par_trimestre AS (
    SELECT team, quarter_start, count(*) AS n, count(lead_days) AS m, count(cycle_days) AS c,
           count(*) - count(cycle_days) AS g, count(*) FILTER (WHERE ancien) AS o,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY lead_days) AS lt_med, percentile_cont(0.85) WITHIN GROUP (ORDER BY lead_days) AS lt_p85,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY cycle_days) AS ct_med, percentile_cont(0.85) WITHIN GROUP (ORDER BY cycle_days) AS ct_p85
    FROM mesures
    GROUP BY team, quarter_start
),
affiche_1 AS (       -- cellules trimestrielles affichées, dans l'ordre de dépendance : le débit (relation T3 comprise) et le lead time d'abord
    SELECT p.*, (p.n >= 5 AND w.team IS NULL) AS d_n,
           (p.n >= 5 AND w.team IS NULL AND p.m >= 5 AND (p.n - p.m = 0 OR p.n - p.m >= 5)) AS d_m
    FROM par_trimestre p
    LEFT JOIN flow.v_t3_withheld w ON w.team = p.team AND w.quarter_start = p.quarter_start      -- débit masqué par la règle (a) ou (b) de D17
),
affiche_2 AS (       -- le cycle time : règle des paires avec le débit (g) et avec le lead time (m, c : items_ct est une partie de items_lt, T6)
    SELECT a.*, (a.d_n AND a.c >= 5 AND (a.g = 0 OR a.g >= 5) AND (NOT a.d_m OR abs(a.m - a.c) = 0 OR abs(a.m - a.c) >= 5)) AS d_c
    FROM affiche_1 a
),
affiche AS (         -- les anciens et les sans-engagement ne s'affichent que si items_ct l'est (un reste ne se montre que si la partie l'est)
    SELECT a.*,
           ((a.d_c AND (a.g >= 5 OR (a.g = 0 AND a.d_n)))
            OR (a.c = 0 AND a.g >= 5 AND a.d_n)) AS d_g,       -- sans aucun cycle time (c = 0), le débit visible donne g = n : le zéro de c se déduit, il n'a rien de petit
           (a.d_c AND a.o >= 5 AND (a.c - a.o = 0 OR a.c - a.o >= 5)) AS d_o
    FROM affiche_2 a
),
fuites AS (       -- équipes dont l'année groupée redonnerait, par différence, un trimestre masqué, série par série, sur les cellules affichées
    SELECT team,
           flow.fuite_serie(array_agg(n), array_agg(NOT d_n)) AS f_n, flow.fuite_serie(array_agg(m), array_agg(NOT d_m)) AS f_m,
           flow.fuite_serie(array_agg(c), array_agg(NOT d_c)) AS f_c, flow.fuite_serie(array_agg(g), array_agg(NOT d_g)) AS f_g,
           flow.fuite_serie(array_agg(o), array_agg(NOT d_o)) AS f_o,
           bool_or(NOT d_n AND n >= 5) AS f_t3         -- revue de T3, B1 : un trimestre retiré par D17 masque toute l'année (fuite_serie n'est pas monotone)
    FROM affiche
    GROUP BY team
),
annee AS (
    SELECT team, count(*) AS n, count(lead_days) AS m, count(cycle_days) AS c, count(*) - count(cycle_days) AS g,
           count(*) FILTER (WHERE ancien) AS o,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY lead_days) AS lt_med, percentile_cont(0.85) WITHIN GROUP (ORDER BY lead_days) AS lt_p85,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY cycle_days) AS ct_med, percentile_cont(0.85) WITHIN GROUP (ORDER BY cycle_days) AS ct_p85
    FROM mesures
    GROUP BY team
)
SELECT p.team, 'quarter'::text AS period, p.quarter_start,
       flow.mask_count(CASE WHEN p.d_n THEN p.n END) AS throughput,
       flow.mask_count(CASE WHEN p.d_m THEN p.m END) AS items_lt,
       CASE WHEN p.m >= 5 THEN round(p.lt_med::numeric, 1) END AS lead_median_days,
       CASE WHEN p.m >= 5 THEN round(p.lt_p85::numeric, 1) END AS lead_p85_days,
       flow.mask_count(CASE WHEN p.d_c THEN p.c END) AS items_ct,
       CASE WHEN p.c >= 5 THEN round(p.ct_med::numeric, 1) END AS cycle_median_days,
       CASE WHEN p.c >= 5 THEN round(p.ct_p85::numeric, 1) END AS cycle_p85_days,
       flow.mask_count(CASE WHEN p.d_o THEN p.o END) AS items_old,
       flow.mask_count_zero(CASE WHEN p.d_g THEN p.g END) AS items_without_commitment
FROM affiche p
UNION ALL
SELECT y.team, 'pooled_year'::text, NULL::date,
       CASE WHEN y.d_n THEN y.n END,
       CASE WHEN y.d_m THEN y.m END,
       CASE WHEN y.m >= 5 THEN round(y.lt_med::numeric, 1) END,
       CASE WHEN y.m >= 5 THEN round(y.lt_p85::numeric, 1) END,
       CASE WHEN y.d_c THEN y.c END,
       CASE WHEN y.c >= 5 THEN round(y.ct_med::numeric, 1) END,
       CASE WHEN y.c >= 5 THEN round(y.ct_p85::numeric, 1) END,
       CASE WHEN y.d_o THEN y.o END,
       CASE WHEN y.d_g THEN y.g END
FROM (
    -- année groupée : mêmes règles que les trimestres, plus l'absence de fuite par différence avec les trimestres masqués ; items_ct et les restes
    -- (g, o) exigent aussi l'absence de fuite des séries dont ils se déduisent (c = débit - g)
    SELECT a.*,
           (a.n >= 5 AND NOT f.f_n AND NOT f.f_t3) AS d_n,
           (a.m >= 5 AND NOT f.f_t3 AND NOT f.f_n AND NOT f.f_m AND (a.n - a.m = 0 OR a.n - a.m >= 5)) AS d_m,
           (a.c >= 5 AND NOT f.f_t3 AND NOT f.f_n AND NOT f.f_c AND NOT f.f_g AND (a.g = 0 OR a.g >= 5)
            AND NOT (a.m >= 5 AND NOT f.f_n AND NOT f.f_m AND (a.n - a.m = 0 OR a.n - a.m >= 5)
                     AND abs(a.m - a.c) BETWEEN 1 AND 4)) AS d_c,
           (NOT f.f_t3 AND ((a.c >= 5 AND NOT f.f_n AND NOT f.f_c AND NOT f.f_g AND (a.g = 0 OR a.g >= 5)
             AND NOT (a.m >= 5 AND NOT f.f_n AND NOT f.f_m AND (a.n - a.m = 0 OR a.n - a.m >= 5)
                      AND abs(a.m - a.c) BETWEEN 1 AND 4)
             AND (a.g >= 5 OR (a.g = 0 AND a.n >= 5 AND NOT f.f_n)))
            OR (a.c = 0 AND a.g >= 5 AND a.n >= 5 AND NOT f.f_n AND NOT f.f_g))) AS d_g,
           (a.c >= 5 AND NOT f.f_t3 AND NOT f.f_n AND NOT f.f_c AND NOT f.f_g AND (a.g = 0 OR a.g >= 5)
            AND NOT (a.m >= 5 AND NOT f.f_n AND NOT f.f_m AND (a.n - a.m = 0 OR a.n - a.m >= 5)
                     AND abs(a.m - a.c) BETWEEN 1 AND 4)
            AND NOT f.f_o AND a.o >= 5 AND (a.c - a.o = 0 OR a.c - a.o >= 5)) AS d_o
    FROM annee a
    JOIN fuites f ON f.team = a.team
) y;

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle

-- Droits : les droits par défaut du lot 1 s'appliquent à tout nouvel objet du propriétaire ; ils sont retirés à tous les rôles pour la vue interne, qui
-- n'est lue que par les deux vues ci-dessus (avec les droits de leur propriétaire). Aucun GRANT.
REVOKE ALL ON flow.v_t3_withheld FROM PUBLIC, pmzilla_flow, pmzilla_flow_ro, pmzilla_flow_views, pmzilla_quality_views;
