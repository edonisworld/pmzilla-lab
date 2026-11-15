-- Schéma touché : flow (cinq vues agrégées de la tranche 1 de Mothra, une fonction de masquage).
-- Change mothra-slices, groupe 15, tâche 15.1, conception D25, D33 et D34, décisions de l'auteur R-20261029-07, R-20261029-08, R-20261029-09 et
-- R-20261029-10. Aucune donnée, aucun mot de passe, aucun rôle créé ni modifié, aucune table changée. Les définitions (statuts, types, liens) se
-- lisent dans les tables du référentiel des définitions de flux (migration 0025) : aucun nom réel ni aucune liste de noms n'est écrit ici.
--
--   flow.v_team_lead_time_throughput   par équipe et par trimestre civil de résolution (UTC), sur les quatre derniers trimestres terminés (le
--                                      trimestre en cours n'a jamais de ligne), plus une ligne « année groupée » par équipe (les quatre trimestres
--                                      ensemble). Colonnes : team, period ('quarter' ou 'pooled_year'), quarter_start (nul pour l'année groupée),
--                                      throughput, items_lt, lead_median_days, lead_p85_days, items_ct, cycle_median_days, cycle_p85_days,
--                                      items_old, items_without_commitment.
--   flow.v_task_without_team_share     par trimestre, pour le produit : tâches terminées, sans équipe, part (tasks_done, tasks_without_team,
--                                      share_percent).
--   flow.v_team_ready_queue            par équipe et par trimestre clos : les stories et tâches de l'équipe dont le statut, à la fin du trimestre, est
--                                      un statut de la file prête (ready).
--   flow.v_team_blocked_share          par équipe et par trimestre : parmi les stories et tâches terminées de l'équipe (blocked_n), celles qui portent
--                                      un lien entrant d'un type bloquant depuis une autre équipe (blocked) et la part (share_percent).
--   flow.v_unplanned_share             par trimestre, pour le produit seulement (R-20261029-08), sans colonne d'équipe : éléments terminés d'un type non
--                                      planifié (unplanned), base (unplanned_n : stories et tâches terminées plus ces éléments) et part.
--   flow.fuite_serie(bigint[], boolean[])  règle de masquage complémentaire de l'année groupée (voir plus bas).
--   flow.mask_count_zero(bigint)           masque sous 5 sauf le zéro, pour un reste dont le zéro se déduit de la partie et du tout visibles.
--
-- Définitions :
--   * Terminé : status_category 'Done' (sans casse, comme v_team_status) et une date de résolution ; les tickets sortis de l'export sont écartés.
--   * Débit : les stories et les tâches rattachées à l'équipe par flow.issues.team_id, et elles seules : aucun rattachement par lien, parent ou
--     épic ; un ticket sans équipe ne compte dans le débit d'aucune équipe. Les défauts sont rattachés par la même colonne (R-20261029-07) ; un défaut
--     n'est pas du débit.
--   * Lead time : de la création à la résolution, en jours, sur ces tickets ; un ticket dont la résolution précède la création est écarté du lead time.
--   * Engagement (R-20261029-09, Q1) : la première entrée dans un statut dont ref_flow_statuses.is_committed est vrai (comparaison sans casse ni
--     espaces). Cycle time : de cet engagement à la résolution. Un ticket terminé sans engagement (ou dont l'engagement suit la résolution) est
--     compté à part : items_without_commitment = débit moins items_ct (R-20261029-10, X29 de masking-sums D16). items_old : parmi les items du cycle
--     time, ceux créés plus d'un an avant leur engagement. Tant que le référentiel est vide, il n'y a aucun cycle time et tout est sans engagement.
--   * File prête (Q2) : les statuts de ref_flow_statuses.is_ready_queue, lus à la fin du trimestre clos : le dernier passage avant le début du trimestre
--     suivant. Un ticket sans passage connu n'y est pas.
--   * Part bloquée (Q3) : un ticket terminé du trimestre est bloqué quand un lien d'un type de ref_blocking_link_types l'atteint depuis un ticket
--     d'une autre équipe (équipe connue et différente). Le sens du type : « blocks », un lien sortant d'un autre ticket vers lui (ou entrant sur lui,
--     enregistré de son côté) ; « waits_for », le lien dit qu'il dépend de l'autre. Un lien sans sens (direction nulle) n'est pas lu. Dénominateur :
--     les stories et tâches terminées de l'équipe.
--   * Non planifié (Q4, R-20261029-08) : les types de ref_unplanned_types, au niveau du produit seulement (défauts sans équipe inclus), jamais par équipe.
--
-- Masquage, dans les vues : une cellule de moins de 5 est masquée (NULL), effectif et statistiques de la même ligne. Règle des paires (relation T6 de
-- masking-sums D16) : quand un effectif est une partie d'un tout visible, il n'est montré que si la différence, qui se lirait par soustraction, est nulle
-- ou d'au moins 5 ; un effectif de reste n'est montré que si la partie l'est. Part (bloqués, sans équipe, non planifié) : le nombre et la part sont
-- masqués dès que le nombre ou son complément est sous 5. Année groupée, masquage complémentaire avec les trimestres (T1, somme des quatre trimestres) :
-- chaque effectif de l'année est masqué dès que les trimestres masqués de la série (au moins un) sont exactement un, ou que leur somme est sous 5
-- (flow.fuite_serie), calculées sur les cellules trimestrielles AFFICHÉES, règle des paires comprise (une cellule masquée par la paire compte comme
-- masquée, avec sa vraie valeur) ; les effectifs liés au débit (items_lt, items_ct, items_old, items_without_commitment) le sont aussi quand le débit de
-- l'année l'est (leur somme le redonnerait), et items_ct exige l'absence de fuite des séries items_ct et items_without_commitment (c = débit - sans engagement).
-- items_old ne s'affiche que si items_ct s'affiche ; items_without_commitment aussi, sauf quand il n'y a aucun cycle time (items_ct vaudrait 0) et que le débit
-- est visible : sans aucun statut engagé déclaré, chaque ticket terminé est sans engagement, la colonne vaut le débit et le zéro de items_ct s'en déduit ; items_ct est contrôlé aussi contre items_lt (paire (m, c), T6). Les statistiques restent montrées dès
-- que leur effectif atteint 5.
--
-- Colonnes ajoutées, à déclarer dans masking-sums D16 avant toute publication (aucune relation décidée ici) : items_without_commitment ; en outre
-- unplanned_n et la part de v_unplanned_share (D16 les nomme unp et unp_n) et blocked_n (blk_n) existent sous ces noms réels.
-- Le masquage de ces vues est celui de cette migration seulement : les relations T1 à T13 que masking-sums D15 et son groupe 7 propageront ne sont pas
-- encore appliquées ; aucune fiche n'est publiée sur ces vues avant.
--
-- Droits : les droits par défaut du schéma donnent SELECT au rôle d'import et au rôle en lecture seule sur tout nouvel objet : ils sont retirés ici, à
-- PUBLIC et au rôle des vues de la qualité, puis SELECT (EXECUTE pour la fonction) est donné au seul rôle des vues. Les vues lisent les tables avec les
-- droits de leur propriétaire, celles du référentiel comprises.

SET LOCAL ROLE pmzilla_owner;

-- Vrai quand l'année groupée redonnerait, par différence, une cellule trimestrielle masquée. `vrais` : les vraies valeurs de la série, `masques` : pour
-- chacune, si la cellule AFFICHÉE est nulle (masque de seuil ou de la règle des paires : une cellule masquée par la paire alors qu'elle vaut 5 ou plus
-- compte comme masquée). Fuite quand il y a au moins une cellule masquée et qu'elles sont exactement une, ou que la somme de leurs vraies valeurs est
-- sous 5. Même règle que la vue de la part des fix versions, appliquée aux cellules affichées.
CREATE FUNCTION flow.fuite_serie(vrais bigint[], masques boolean[]) RETURNS boolean
    LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT count(*) FILTER (WHERE t.masque) >= 1
           AND (count(*) FILTER (WHERE t.masque) = 1 OR coalesce(sum(t.x) FILTER (WHERE t.masque), 0) < 5)
    FROM unnest(vrais, masques) AS t(x, masque)
$$;

-- Masquage d'un compte dont le zéro est déductible : sous 5, masqué, sauf zéro (que la règle des paires laisse lire par différence : le montrer ne
-- révèle rien et le masquer serait incohérent avec l'effectif visible dont il se déduit).
CREATE FUNCTION flow.mask_count_zero(n bigint) RETURNS bigint
    LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$ SELECT CASE WHEN n = 0 OR n >= 5 THEN n END $$;

CREATE VIEW flow.v_team_lead_time_throughput AS
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
affiche_1 AS (       -- cellules trimestrielles affichées, dans l'ordre de dépendance : le débit et le lead time d'abord
    SELECT p.*, (p.n >= 5) AS d_n, (p.m >= 5 AND (p.n - p.m = 0 OR p.n - p.m >= 5)) AS d_m
    FROM par_trimestre p
),
affiche_2 AS (       -- le cycle time : règle des paires avec le débit (g) et avec le lead time (m, c : items_ct est une partie de items_lt, T6)
    SELECT a.*, (a.c >= 5 AND (a.g = 0 OR a.g >= 5) AND (NOT a.d_m OR abs(a.m - a.c) = 0 OR abs(a.m - a.c) >= 5)) AS d_c
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
           flow.fuite_serie(array_agg(o), array_agg(NOT d_o)) AS f_o
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
       flow.mask_count(p.n) AS throughput,
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
           (a.n >= 5 AND NOT f.f_n) AS d_n,
           (a.m >= 5 AND NOT f.f_n AND NOT f.f_m AND (a.n - a.m = 0 OR a.n - a.m >= 5)) AS d_m,
           (a.c >= 5 AND NOT f.f_n AND NOT f.f_c AND NOT f.f_g AND (a.g = 0 OR a.g >= 5)
            AND NOT (a.m >= 5 AND NOT f.f_n AND NOT f.f_m AND (a.n - a.m = 0 OR a.n - a.m >= 5)
                     AND abs(a.m - a.c) BETWEEN 1 AND 4)) AS d_c,
           ((a.c >= 5 AND NOT f.f_n AND NOT f.f_c AND NOT f.f_g AND (a.g = 0 OR a.g >= 5)
             AND NOT (a.m >= 5 AND NOT f.f_n AND NOT f.f_m AND (a.n - a.m = 0 OR a.n - a.m >= 5)
                      AND abs(a.m - a.c) BETWEEN 1 AND 4)
             AND (a.g >= 5 OR (a.g = 0 AND a.n >= 5 AND NOT f.f_n)))
            OR (a.c = 0 AND a.g >= 5 AND a.n >= 5 AND NOT f.f_n AND NOT f.f_g)) AS d_g,
           (a.c >= 5 AND NOT f.f_n AND NOT f.f_c AND NOT f.f_g AND (a.g = 0 OR a.g >= 5)
            AND NOT (a.m >= 5 AND NOT f.f_n AND NOT f.f_m AND (a.n - a.m = 0 OR a.n - a.m >= 5)
                     AND abs(a.m - a.c) BETWEEN 1 AND 4)
            AND NOT f.f_o AND a.o >= 5 AND (a.c - a.o = 0 OR a.c - a.o >= 5)) AS d_o
    FROM annee a
    JOIN fuites f ON f.team = a.team
) y;

CREATE VIEW flow.v_task_without_team_share AS
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
       CASE WHEN p.sans >= 5 AND p.avec >= 5 THEN p.sans END AS tasks_without_team,
       CASE WHEN p.sans >= 5 AND p.avec >= 5 THEN round(100.0 * p.sans / p.n, 1) END AS share_percent
FROM par_trimestre p;

CREATE VIEW flow.v_team_ready_queue AS
WITH trimestres AS (
    SELECT (date_trunc('quarter', now() AT TIME ZONE 'UTC') - make_interval(months => 3 * k))::date AS quarter_start
    FROM generate_series(1, 4) AS k
),
file_prete AS (       -- statut à la fin du trimestre : le dernier passage avant le début du trimestre suivant
    SELECT t.name AS team, q.quarter_start
    FROM trimestres q
    JOIN flow.issues i ON i.created_at < (q.quarter_start + interval '3 months') AT TIME ZONE 'UTC'
                      AND (i.resolved_at IS NULL OR i.resolved_at >= (q.quarter_start + interval '3 months') AT TIME ZONE 'UTC')
    JOIN flow.teams t ON t.id = i.team_id
    CROSS JOIN LATERAL (
        SELECT x.to_status
        FROM flow.transitions x
        WHERE x.issue_key = i.key AND x.transitioned_at < (q.quarter_start + interval '3 months') AT TIME ZONE 'UTC'
        ORDER BY x.transitioned_at DESC
        LIMIT 1
    ) dernier
    JOIN flow.ref_flow_statuses s ON lower(btrim(s.status)) = lower(btrim(dernier.to_status)) AND s.is_ready_queue
    WHERE i.out_of_export_at IS NULL AND lower(i.type) IN ('story', 'task')
)
SELECT team, quarter_start, flow.mask_count(count(*)) AS ready
FROM file_prete
GROUP BY team, quarter_start;

CREATE VIEW flow.v_team_blocked_share AS
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
       CASE WHEN p.b >= 5 AND p.r >= 5 THEN p.b END AS blocked,
       CASE WHEN p.b >= 5 AND p.r >= 5 THEN round(100.0 * p.b / p.n, 1) END AS share_percent
FROM par_trimestre p;

CREATE VIEW flow.v_unplanned_share AS
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
       CASE WHEN p.u >= 5 AND p.r >= 5 THEN p.u END AS unplanned,
       CASE WHEN p.u >= 5 AND p.r >= 5 THEN round(100.0 * p.u / p.n, 1) END AS share_percent
FROM par_trimestre p;

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle

-- Droits : retirés d'abord (les droits par défaut du lot 1 s'appliquent à tout nouvel objet du propriétaire), puis accordés.
REVOKE ALL ON flow.v_team_lead_time_throughput, flow.v_task_without_team_share, flow.v_team_ready_queue, flow.v_team_blocked_share, flow.v_unplanned_share
    FROM PUBLIC, pmzilla_flow, pmzilla_flow_ro, pmzilla_quality_views;
REVOKE ALL ON FUNCTION flow.fuite_serie(bigint[], boolean[]), flow.mask_count_zero(bigint) FROM PUBLIC;
GRANT SELECT ON flow.v_team_lead_time_throughput, flow.v_task_without_team_share, flow.v_team_ready_queue, flow.v_team_blocked_share, flow.v_unplanned_share
    TO pmzilla_flow_views;
GRANT EXECUTE ON FUNCTION flow.fuite_serie(bigint[], boolean[]), flow.mask_count_zero(bigint) TO pmzilla_flow_views;
