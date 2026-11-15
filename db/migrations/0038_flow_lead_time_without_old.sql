-- Schéma touché : flow (une vue agrégée redéfinie : ses colonnes existantes inchangées et dans le même ordre, quatre colonnes ajoutées en fin de liste ; aucune donnée,
-- aucune table, aucun rôle, aucun mot de passe).
-- Change masking-sums, tâche 22.1 ; conception D16 (« Grouped year without the old items ») ; décisions de l'auteur R-20261104-46, R-20261105-30 (réponses Q1 (b) amendée,
-- Q2 (a) et Q3 (a)) et R-20261106-52 (Q2 (a) : le test statique compare cette vue à 0037, sa dernière définition, une fois retirées les lignes des nouvelles colonnes).
--
-- Les médianes et les P85 de flow.v_team_lead_time_throughput comptent les éléments anciens (0030 : un élément créé plus d'un an avant son point d'engagement, compté
-- dans items_old), contre l'hypothèse 1 de Mothra (« comptés à part, hors du ratio »). Quatre colonnes les calculent sans eux, sur chaque ligne (les quatre trimestres et
-- l'année groupée) : lead_median_days_excl_old, lead_p85_days_excl_old, cycle_median_days_excl_old, cycle_p85_days_excl_old. Même percentile et même arrondi que leurs
-- équivalents ; population : les éléments dont `ancien` n'est pas vrai (un ancien a un lead time et un cycle time : il atteint son point d'engagement avant sa résolution,
-- si bien que l'échantillon du lead time sans les anciens est m - o, celui du cycle time c - o).
--
-- Visibilité (D16, au plancher de 5 ; R-20261106-59, Q1 (a)) : une statistique de lead time est montrée si items_lt de la ligne l'est (d_m), si items_old de la même
-- ligne l'est (d_o) et que m - o >= 5 ; une statistique de cycle time si items_ct de la ligne l'est (d_c), si items_old de la même ligne l'est (d_o) et que c - o >= 5.
-- Sur l'année groupée, d_m, d_c et d_o sont ceux de l'année (règles de série comprises). Principe : la visibilité d'une cellule ne dépend que de cellules publiées ;
-- une statistique montrée avec items_old masqué donnerait une inégalité sur un items_old masqué (quatre trimestres masqués fixés à c - 1 quand la statistique de l'année
-- est absente ; effectif de 6 : items_old = 1), une valeur unique contraire au critère D1. Plus strict que les statistiques existantes (m >= 5 ou c >= 5 seul). Aucune
-- colonne de compte n'est ajoutée : le compte des éléments sans les anciens (X38) reste écarté, il épinglerait items_old masqué. Les colonnes sont lues par le seul
-- rapport de l'hypothèse 1 de Mothra.
--
-- Remplace : rien (colonnes nouvelles). La vue repart du texte de 0037, mot pour mot : un test (tests/flow_views/test_migration_sans_anciens.py) retire les lignes des
-- nouvelles colonnes et compare le reste à 0037. Ne modifie ni 0030, ni 0035, ni 0037.
-- Retrait : permanent tant que le rapport de l'hypothèse 1 lit ces colonnes.
--
-- Droits : CREATE OR REPLACE VIEW conserve les droits de la vue (SELECT au seul rôle des vues). Aucun GRANT ni REVOKE.

SET LOCAL ROLE pmzilla_owner;

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
           percentile_cont(0.5) WITHIN GROUP (ORDER BY lead_days) FILTER (WHERE ancien IS NOT TRUE) AS lt_med_sans_anc,
           percentile_cont(0.85) WITHIN GROUP (ORDER BY lead_days) FILTER (WHERE ancien IS NOT TRUE) AS lt_p85_sans_anc,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY cycle_days) FILTER (WHERE ancien IS NOT TRUE) AS ct_med_sans_anc,
           percentile_cont(0.85) WITHIN GROUP (ORDER BY cycle_days) FILTER (WHERE ancien IS NOT TRUE) AS ct_p85_sans_anc,
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
           (a.d_c AND (a.o = 0 OR (a.o >= 5 AND (a.c - a.o = 0 OR a.c - a.o >= 5)))) AS d_o      -- R-20261106-39 : le zéro d'items_old est montré quand items_ct l'est
    FROM affiche_2 a
),
fuites AS (       -- équipes dont l'année groupée redonnerait, par différence, un trimestre masqué, série par série, sur les cellules affichées
    SELECT team,
           flow.fuite_serie(array_agg(n), array_agg(NOT d_n)) AS f_n, flow.fuite_serie(array_agg(m), array_agg(NOT d_m)) AS f_m,
           flow.fuite_serie(array_agg(c), array_agg(NOT d_c)) AS f_c, flow.fuite_serie(array_agg(g), array_agg(NOT d_g)) AS f_g,
           flow.fuite_serie(array_agg(o), array_agg(NOT d_o)) AS f_o,
           bool_or(NOT d_n AND n >= 5) AS f_t3,         -- revue de T3, B1 : un trimestre retiré par D17 masque toute l'année (fuite_serie n'est pas monotone)
           bool_or(NOT d_o) AS q_o                      -- R-20261106-39 : un items_old trimestriel masqué masque l'année, comme le lecteur Python et la copie TypeScript
    FROM affiche
    GROUP BY team
),
annee AS (
    SELECT team, count(*) AS n, count(lead_days) AS m, count(cycle_days) AS c, count(*) - count(cycle_days) AS g,
           count(*) FILTER (WHERE ancien) AS o,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY lead_days) FILTER (WHERE ancien IS NOT TRUE) AS lt_med_sans_anc,
           percentile_cont(0.85) WITHIN GROUP (ORDER BY lead_days) FILTER (WHERE ancien IS NOT TRUE) AS lt_p85_sans_anc,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY cycle_days) FILTER (WHERE ancien IS NOT TRUE) AS ct_med_sans_anc,
           percentile_cont(0.85) WITHIN GROUP (ORDER BY cycle_days) FILTER (WHERE ancien IS NOT TRUE) AS ct_p85_sans_anc,
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
       flow.mask_count_zero(CASE WHEN p.d_o THEN p.o END) AS items_old,
       flow.mask_count_zero(CASE WHEN p.d_g THEN p.g END) AS items_without_commitment,
       CASE WHEN p.d_m AND p.d_o AND p.m - p.o >= 5 THEN round(p.lt_med_sans_anc::numeric, 1) END AS lead_median_days_excl_old,
       CASE WHEN p.d_m AND p.d_o AND p.m - p.o >= 5 THEN round(p.lt_p85_sans_anc::numeric, 1) END AS lead_p85_days_excl_old,
       CASE WHEN p.d_c AND p.d_o AND p.c - p.o >= 5 THEN round(p.ct_med_sans_anc::numeric, 1) END AS cycle_median_days_excl_old,
       CASE WHEN p.d_c AND p.d_o AND p.c - p.o >= 5 THEN round(p.ct_p85_sans_anc::numeric, 1) END AS cycle_p85_days_excl_old
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
       CASE WHEN y.d_g THEN y.g END,
       CASE WHEN y.d_m AND y.d_o AND y.m - y.o >= 5 THEN round(y.lt_med_sans_anc::numeric, 1) END,
       CASE WHEN y.d_m AND y.d_o AND y.m - y.o >= 5 THEN round(y.lt_p85_sans_anc::numeric, 1) END,
       CASE WHEN y.d_c AND y.d_o AND y.c - y.o >= 5 THEN round(y.ct_med_sans_anc::numeric, 1) END,
       CASE WHEN y.d_c AND y.d_o AND y.c - y.o >= 5 THEN round(y.ct_p85_sans_anc::numeric, 1) END
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
            AND NOT f.f_o AND NOT f.q_o AND (a.o = 0 OR (a.o >= 5 AND (a.c - a.o = 0 OR a.c - a.o >= 5)))) AS d_o
    FROM annee a
    JOIN fuites f ON f.team = a.team
) y;

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle
