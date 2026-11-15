-- Schéma touché : flow (une fonction pure flow.closed_quarter_starts ; dix vues agrégées redéfinies, mêmes colonnes dans le même ordre ; commentaires de vue) ; aucune donnée,
-- aucune table, aucun rôle, aucun mot de passe.
-- Changement de trois trimestres clos (décisions de l'auteur R-20261114-45, R-20261114-49 et R-20261114-51), conception D1, D2 et D3.
--
-- Chaque vue qui lisait une fenêtre de quatre trimestres terminés (generate_series(1, 4)) lit désormais les TROIS trimestres clos qui précèdent le trimestre UTC de now(),
-- par une seule fonction, flow.closed_quarter_starts(now()) : le trimestre en cours n'y est jamais, et les trois trimestres tiennent toujours dans l'année de conservation
-- (sauf la limite déclarée plus bas). La ligne « pooled_year » de v_team_lead_time_throughput (identifiant inchangé) somme les trois trimestres montrés ; ses statistiques
-- sont calculées sur les éléments de ces trois trimestres. Aucune règle de masquage, aucun plancher, aucune propagation, aucune retenue de T3 ne change : seule la série
-- passe de quatre termes à trois.
--
-- Chaque vue repart de sa DERNIÈRE définition, mot pour mot, la fenêtre seule changée :
--   v_team_fix_version_share (0022), v_team_fix_version_lag (0022), v_t3_withheld (0030), v_team_lead_time_throughput (0038, colonnes *_excl_old comprises),
--   v_task_without_team_share, v_team_blocked_share, v_unplanned_share (0029), v_team_ready_queue (0026), v_team_flow_inout (0031),
--   v_team_delivery_fields_coverage (0033).
-- v_team_weekly_resolved (0030) n'a pas de fenêtre propre : inchangée. Les migrations appliquées ne sont pas touchées.
-- Migrations POSTÉRIEURES à la dernière définition textuelle d'une vue (relevé de toutes les ALTER TABLE ... RENAME/DROP COLUMN) : seule 0034 en touche une, par
-- renommage dans flow.issue_delivery_fields (release_target, verification_required, product_safety, isp, code_review_status deviennent *_id) : PostgreSQL a suivi
-- ces renommages dans v_team_delivery_fields_coverage sans la réécrire ; le texte recréé ici les porte donc sous leur nom actuel. Les colonnes supprimées de
-- flow.issue_delivery_options (value) et flow.issue_defect_fields ne sont lues par aucune des dix vues. Les autres ALTER TABLE ajoutent des colonnes (aucun effet).
--
-- Droits : CREATE OR REPLACE VIEW conserve les droits des vues ; aucun GRANT ni REVOKE de vue ici. La fonction n'a aucun droit pour PUBLIC ; EXECUTE va aux deux rôles
-- qui lisent ces vues (pmzilla_flow_views et pmzilla_mothra_views), car le droit EXECUTE d'une fonction appelée dans une vue est vérifié pour le lecteur de la vue
-- (comme flow.mask_count, 0002 et 0039). Elle ne lit aucune table.
--
-- Limite déclarée (R-20261114-51, option (a), conception D3) : la durée de recherche d'export est un réglage relatif, en semaines (sa valeur n'est pas recopiée ici),
-- et la conservation est plafonnée à 365 jours ; un trimestre plus ancien peut en dépasser le début de quelques heures. Le plus ancien des trois trimestres peut donc perdre au plus un jour et quelques heures les derniers jours d'un
-- trimestre (environ 1 %). Rien n'est masqué pour autant, aucun trimestre n'est retenu. Elle est écrite dans le commentaire de chaque vue trimestrielle ci-dessous.
--
-- Remplace : les fenêtres de quatre trimestres de chaque vue (generate_series(1, 4)) et le drapeau du premier trimestre tronqué de Mothra. Retrait : permanent tant que les
-- vues portent des trimestres et que la conservation est d'un an ; la limite tombe quand la recherche d'export et la conservation couvrent chacune 366 jours.

SET LOCAL ROLE pmzilla_owner;

-- Les trois débuts de trimestre clos avant le trimestre UTC de l'ancre, du plus récent au plus ancien (ordre de tools/flow_views.py, trois_trimestres_clos, et de
-- mothra/contract/src/trimestres.ts, fenetreTroisTrimestres : un test compare les trois sur chaque jour de 2027 à 2030).
CREATE FUNCTION flow.closed_quarter_starts(anchor timestamptz) RETURNS date[]
    LANGUAGE sql IMMUTABLE PARALLEL SAFE SET search_path = pg_catalog, pg_temp AS $$
    SELECT array_agg((date_trunc('quarter', anchor AT TIME ZONE 'UTC') - make_interval(months => 3 * k))::date ORDER BY k)
    FROM generate_series(1, 3) AS k
$$;

CREATE OR REPLACE VIEW flow.v_team_fix_version_share AS
WITH trimestres AS (
    SELECT q::date AS quarter_start
    FROM unnest(flow.closed_quarter_starts(now())) AS q       -- les trois derniers trimestres terminés : le trimestre en cours n'y est jamais
),
retenus AS (
    SELECT coalesce(t.name, '(sans équipe)') AS team,
           (date_trunc('quarter', i.resolved_at AT TIME ZONE 'UTC'))::date AS quarter_start,
           EXISTS (SELECT 1 FROM flow.issue_current_versions v WHERE v.issue_key = i.key AND v.kind = 'fix') AS has_fix
    FROM flow.issues i
    LEFT JOIN flow.teams t ON t.id = i.team_id
    WHERE i.resolved_at IS NOT NULL
      AND i.out_of_export_at IS NULL
      AND lower(i.type) <> 'epic'
),
dans_la_fenetre AS (
    SELECT r.* FROM retenus r JOIN trimestres q ON q.quarter_start = r.quarter_start
),
par_equipe AS (
    SELECT team, quarter_start, count(*) AS n,
           count(*) FILTER (WHERE has_fix) AS f,
           count(*) FILTER (WHERE NOT has_fix) AS g
    FROM dans_la_fenetre
    GROUP BY team, quarter_start
),
equipes AS (
    -- Items visibles : au moins 5, et pas le cas X10 (5 items sans aucun avec fix version : borne absente, donc « avec = 0 » se lirait).
    SELECT p.*, (p.n >= 5 AND NOT (p.n = 5 AND p.f = 0)) AS items_ok
    FROM par_equipe p
),
equipes_vis AS (
    SELECT e.*, (e.items_ok AND e.f >= 5 AND e.g >= 5) AS detail_ok, (e.items_ok AND e.g < 5) AS borne_ok
    FROM equipes e
),
produit AS (
    SELECT quarter_start, count(*) AS n,
           count(*) FILTER (WHERE has_fix) AS f,
           count(*) FILTER (WHERE NOT has_fix) AS g
    FROM dans_la_fenetre
    GROUP BY quarter_start
),
colonnes AS (       -- D3 : une cellule du produit exige toutes les cellules d'équipe de sa colonne (une ligne sans équipe en est une)
    SELECT quarter_start, bool_and(items_ok) AS tout_items, bool_and(detail_ok) AS tout_detail
    FROM equipes_vis
    GROUP BY quarter_start
)
SELECT e.team, e.quarter_start,
       CASE WHEN e.items_ok THEN e.n END AS items,
       CASE WHEN e.detail_ok THEN e.f END AS with_fix_version,
       CASE WHEN e.detail_ok THEN round(100.0 * e.f / e.n, 1) END AS share_percent,
       CASE WHEN e.borne_ok THEN e.n - 4 END AS with_fix_version_min
FROM equipes_vis e
UNION ALL
SELECT '(produit)'::text AS team, p.quarter_start,
       CASE WHEN p.n >= 5 AND u.tout_items THEN p.n END AS items,
       CASE WHEN p.n >= 5 AND p.f >= 5 AND p.g >= 5 AND u.tout_items AND u.tout_detail THEN p.f END AS with_fix_version,
       CASE WHEN p.n >= 5 AND p.f >= 5 AND p.g >= 5 AND u.tout_items AND u.tout_detail THEN round(100.0 * p.f / p.n, 1) END AS share_percent,
       NULL::bigint AS with_fix_version_min       -- jamais de borne pour le produit
FROM produit p
JOIN colonnes u ON u.quarter_start = p.quarter_start;

CREATE OR REPLACE VIEW flow.v_team_fix_version_lag AS
WITH trimestres AS (
    SELECT q::date AS quarter_start
    FROM unnest(flow.closed_quarter_starts(now())) AS q       -- les trois derniers trimestres terminés : le trimestre en cours n'y est jamais
),
items AS (
    SELECT coalesce(t.name, '(sans équipe)') AS team,
           (date_trunc('quarter', i.resolved_at AT TIME ZONE 'UTC'))::date AS quarter_start,
           CASE WHEN p.premiere IS NULL THEN 5                                       -- sans historique
                WHEN p.premiere <= i.resolved_at THEN 1                              -- avant ou à la résolution
                WHEN p.premiere <= i.resolved_at + interval '7 days' THEN 2
                WHEN p.premiere <= i.resolved_at + interval '30 days' THEN 3
                ELSE 4 END AS seau
    FROM flow.issues i
    LEFT JOIN flow.teams t ON t.id = i.team_id
    LEFT JOIN LATERAL (SELECT min(pv.added_at) AS premiere FROM flow.issue_version_periods pv WHERE pv.issue_key = i.key) p ON true
    WHERE i.resolved_at IS NOT NULL
      AND i.out_of_export_at IS NULL
      AND lower(i.type) <> 'epic'
      AND EXISTS (SELECT 1 FROM flow.issue_current_versions v WHERE v.issue_key = i.key AND v.kind = 'fix')
),
dans_la_fenetre AS (
    SELECT r.* FROM items r JOIN trimestres q ON q.quarter_start = r.quarter_start
),
par_equipe AS (
    SELECT team, quarter_start, count(*) AS n,
           count(*) FILTER (WHERE seau = 1) AS b1, count(*) FILTER (WHERE seau = 2) AS b2, count(*) FILTER (WHERE seau = 3) AS b3,
           count(*) FILTER (WHERE seau = 4) AS b4, count(*) FILTER (WHERE seau = 5) AS b5
    FROM dans_la_fenetre
    GROUP BY team, quarter_start
),
part_equipe AS (
    -- Décision 1(a) du 2026-10-23 : une ligne d'équipe et de trimestre n'est montrée que si le détail de la part est visible pour la même équipe
    -- et le même trimestre, lu dans la vue de la part recréée ci-dessus (D5-c au plancher) : with_fix_version est nul quand le détail est masqué.
    SELECT team, quarter_start FROM flow.v_team_fix_version_share WHERE team <> '(produit)' AND with_fix_version IS NOT NULL
),
part_produit AS (
    SELECT quarter_start FROM flow.v_team_fix_version_share WHERE team = '(produit)' AND with_fix_version IS NOT NULL
),
equipe_vis AS (
    SELECT e.team, e.quarter_start, e.n, e.b1, e.b2, e.b3, e.b4, e.b5,
           d.vn, d.v1, d.v2, d.v3, d.v4, d.v5
    FROM par_equipe e
    LEFT JOIN part_equipe s ON s.team = e.team AND s.quarter_start = e.quarter_start
    CROSS JOIN LATERAL flow.retard_d2(
        e.b1, e.b2, e.b3, e.b4, e.b5, (s.team IS NOT NULL AND e.n >= 5),
        e.b1 >= 5, e.b2 >= 5, e.b3 >= 5, e.b4 >= 5, e.b5 >= 5) d       -- D2 : la règle de complément repassée jusqu'à ce que plus rien ne change
),
produit AS (
    SELECT quarter_start, sum(n)::bigint AS n, sum(b1)::bigint AS b1, sum(b2)::bigint AS b2, sum(b3)::bigint AS b3,
           sum(b4)::bigint AS b4, sum(b5)::bigint AS b5,
           bool_and(vn) AS tn, bool_and(v1) AS t1, bool_and(v2) AS t2, bool_and(v3) AS t3, bool_and(v4) AS t4, bool_and(v5) AS t5   -- toutes les équipes visibles
    FROM equipe_vis
    GROUP BY quarter_start
),
produit_vis AS (
    -- Décision 1(b) du 2026-10-23 (D3) : une cellule du produit n'est montrée que si la ligne du produit est visible dans la vue de la part et que
    -- TOUTES les cellules d'équipe de la même colonne le sont. Les cellules ainsi masquées comptent parmi les cellules masquées de la ligne (D2).
    SELECT p.quarter_start, p.n, p.b1, p.b2, p.b3, p.b4, p.b5,
           d.vn, d.v1, d.v2, d.v3, d.v4, d.v5
    FROM produit p
    CROSS JOIN LATERAL (SELECT EXISTS (SELECT 1 FROM part_produit pp WHERE pp.quarter_start = p.quarter_start) AS ok) g
    CROSS JOIN LATERAL flow.retard_d2(p.b1, p.b2, p.b3, p.b4, p.b5, (g.ok AND p.tn), p.t1, p.t2, p.t3, p.t4, p.t5) d
)
SELECT e.team, e.quarter_start,
       CASE WHEN e.vn THEN e.n END AS items,
       CASE WHEN e.v1 THEN e.b1 END AS before_or_at_resolution,
       CASE WHEN e.v2 THEN e.b2 END AS within_7_days,
       CASE WHEN e.v3 THEN e.b3 END AS within_30_days,
       CASE WHEN e.v4 THEN e.b4 END AS later,
       CASE WHEN e.v5 THEN e.b5 END AS no_history
FROM equipe_vis e
UNION ALL
SELECT '(produit)'::text AS team, p.quarter_start,
       CASE WHEN p.vn THEN p.n END, CASE WHEN p.v1 THEN p.b1 END, CASE WHEN p.v2 THEN p.b2 END, CASE WHEN p.v3 THEN p.b3 END,
       CASE WHEN p.v4 THEN p.b4 END, CASE WHEN p.v5 THEN p.b5 END
FROM produit_vis p;

CREATE OR REPLACE VIEW flow.v_t3_withheld AS
WITH trimestres AS (
    SELECT q::date AS quarter_start
    FROM unnest(flow.closed_quarter_starts(now())) AS q       -- les trois derniers trimestres terminés, comme v_team_lead_time_throughput
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

CREATE OR REPLACE VIEW flow.v_team_lead_time_throughput AS
WITH trimestres AS (
    SELECT q::date AS quarter_start
    FROM unnest(flow.closed_quarter_starts(now())) AS q       -- les trois derniers trimestres terminés : le trimestre en cours n'y est jamais
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
    -- année groupée (les trois trimestres montrés) : mêmes règles que les trimestres, plus l'absence de fuite par différence avec les trimestres masqués ; items_ct et les restes
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

CREATE OR REPLACE VIEW flow.v_task_without_team_share AS
WITH trimestres AS (
    SELECT q::date AS quarter_start
    FROM unnest(flow.closed_quarter_starts(now())) AS q
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
    SELECT q::date AS quarter_start
    FROM unnest(flow.closed_quarter_starts(now())) AS q
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
    SELECT q::date AS quarter_start
    FROM unnest(flow.closed_quarter_starts(now())) AS q
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

CREATE OR REPLACE VIEW flow.v_team_ready_queue AS
WITH trimestres AS (
    SELECT q::date AS quarter_start
    FROM unnest(flow.closed_quarter_starts(now())) AS q
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

CREATE OR REPLACE VIEW flow.v_team_flow_inout AS
WITH trimestres AS (
    SELECT q::date AS quarter_start
    FROM unnest(flow.closed_quarter_starts(now())) AS q       -- les trois derniers trimestres terminés : le trimestre en cours n'y est jamais
),
population AS (
    SELECT coalesce(t.name, '(sans équipe)') AS team,
           CASE WHEN lower(i.type) IN ('story', 'task') THEN 'story'
                WHEN EXISTS (SELECT 1 FROM flow.ref_unplanned_types u
                              WHERE u.kind = 'defect' AND lower(btrim(u.type)) = lower(btrim(i.type))) THEN 'defect'
           END AS type_group,
           i.created_at, i.resolved_at,
           (lower(i.status_category) = 'done' AND i.resolved_at IS NOT NULL) AS termine
    FROM flow.issues i
    LEFT JOIN flow.teams t ON t.id = i.team_id          -- rattachement par l'équipe du ticket seulement : jamais par lien, parent ou épic
    WHERE i.out_of_export_at IS NULL
      AND lower(i.type) NOT IN ('epic', 'initiative')   -- types de portefeuille ; les projets exclus : voir l'en-tête de 0031
),
evenements AS (
    SELECT p.team, p.type_group, (date_trunc('quarter', p.created_at AT TIME ZONE 'UTC'))::date AS quarter_start, 1 AS cree, 0 AS fini
    FROM population p
    WHERE p.type_group IS NOT NULL
    UNION ALL
    SELECT p.team, p.type_group, (date_trunc('quarter', p.resolved_at AT TIME ZONE 'UTC'))::date, 0, 1
    FROM population p
    WHERE p.type_group IS NOT NULL AND p.termine
),
par_equipe AS (
    SELECT e.team, e.quarter_start, e.type_group, sum(e.cree)::bigint AS c, sum(e.fini)::bigint AS d
    FROM evenements e
    JOIN trimestres q ON q.quarter_start = e.quarter_start
    GROUP BY e.team, e.quarter_start, e.type_group
),
produit AS (
    SELECT quarter_start, type_group, sum(c)::bigint AS c, sum(d)::bigint AS d, bool_and(c >= 5) AS c_ok, bool_and(d >= 5) AS d_ok
    FROM par_equipe
    GROUP BY quarter_start, type_group
)
SELECT e.team, e.quarter_start, e.type_group,
       flow.mask_count(e.c) AS created,
       flow.mask_count(e.d) AS done
FROM par_equipe e
UNION ALL
SELECT '(produit)'::text, p.quarter_start, p.type_group,
       flow.mask_count(CASE WHEN p.c_ok THEN p.c END),       -- la ligne du produit seulement si chaque cellule d'équipe de sa colonne est visible (D3)
       flow.mask_count(CASE WHEN p.d_ok THEN p.d END)
FROM produit p;

CREATE OR REPLACE VIEW flow.v_team_delivery_fields_coverage AS
WITH trimestres AS (
    SELECT q::date AS quarter_start
    FROM unnest(flow.closed_quarter_starts(now())) AS q       -- les trois derniers trimestres terminés : le trimestre en cours n'y est jamais
),
retenus AS (
    SELECT coalesce(t.name, '(sans équipe)') AS team,
           (date_trunc('quarter', i.resolved_at AT TIME ZONE 'UTC'))::date AS quarter_start,
           CASE WHEN lower(i.type) = 'epic' THEN 'epic' ELSE 'story' END AS item_kind,
           EXISTS (SELECT 1 FROM flow.issue_current_sprints s WHERE s.issue_key = i.key) AS f_sprint,
           EXISTS (SELECT 1 FROM flow.issue_current_asset_versions v WHERE v.issue_key = i.key AND v.kind = 'target') AS f_target,
           EXISTS (SELECT 1 FROM flow.issue_current_asset_versions v WHERE v.issue_key = i.key AND v.kind = 'resolution') AS f_resolution,
           EXISTS (SELECT 1 FROM flow.issue_current_asset_versions v WHERE v.issue_key = i.key AND v.kind = 'epic_a') AS f_epic_a,
           EXISTS (SELECT 1 FROM flow.issue_current_asset_versions v WHERE v.issue_key = i.key AND v.kind = 'epic_b') AS f_epic_b,
           EXISTS (SELECT 1 FROM flow.issue_delivery_options o WHERE o.issue_key = i.key AND o.field = 'category_nature') AS f_nature,
           EXISTS (SELECT 1 FROM flow.issue_delivery_options o WHERE o.issue_key = i.key AND o.field = 'workflow_option') AS f_workflow,
           (d.release_target_id IS NOT NULL) AS f_release_target,                  -- colonnes renommées *_id par 0034, que la vue de 0033 suivait sans être réécrite
           (d.verification_required_id IS NOT NULL) AS f_verification,
           (d.product_safety_id IS NOT NULL) AS f_safety,
           (d.isp_id IS NOT NULL) AS f_isp,
           (d.code_review_status_id IS NOT NULL) AS f_review,
           (d.portfolio_rank IS NOT NULL) AS f_rank,
           coalesce(d.customer_commitment, false) AS f_customer,
           coalesce(d.source_commitment, false) AS f_source,
           coalesce(d.strategic_objective, false) AS f_strategic
    FROM flow.issues i
    LEFT JOIN flow.teams t ON t.id = i.team_id
    LEFT JOIN flow.issue_delivery_fields d ON d.issue_key = i.key
    WHERE i.resolved_at IS NOT NULL
      AND i.out_of_export_at IS NULL
),
par_equipe AS (
    SELECT r.team, r.quarter_start, r.item_kind, count(*) AS n,
           count(*) FILTER (WHERE r.f_sprint) AS c_sprint,
           count(*) FILTER (WHERE r.f_target) AS c_target,
           count(*) FILTER (WHERE r.f_resolution) AS c_resolution,
           count(*) FILTER (WHERE r.f_epic_a) AS c_epic_a,
           count(*) FILTER (WHERE r.f_epic_b) AS c_epic_b,
           count(*) FILTER (WHERE r.f_nature) AS c_nature,
           count(*) FILTER (WHERE r.f_workflow) AS c_workflow,
           count(*) FILTER (WHERE r.f_release_target) AS c_release_target,
           count(*) FILTER (WHERE r.f_verification) AS c_verification,
           count(*) FILTER (WHERE r.f_safety) AS c_safety,
           count(*) FILTER (WHERE r.f_isp) AS c_isp,
           count(*) FILTER (WHERE r.f_review) AS c_review,
           count(*) FILTER (WHERE r.f_rank) AS c_rank,
           count(*) FILTER (WHERE r.f_customer) AS c_customer,
           count(*) FILTER (WHERE r.f_source) AS c_source,
           count(*) FILTER (WHERE r.f_strategic) AS c_strategic
    FROM retenus r
    JOIN trimestres q ON q.quarter_start = r.quarter_start
    GROUP BY r.team, r.quarter_start, r.item_kind
)
SELECT p.team, p.quarter_start, p.item_kind,
       flow.mask_count(p.n) AS items,
       CASE WHEN p.c_sprint >= 5 AND p.n - p.c_sprint >= 5 THEN p.c_sprint END AS with_sprint,
       CASE WHEN p.c_target >= 5 AND p.n - p.c_target >= 5 THEN p.c_target END AS with_target_version,
       CASE WHEN p.c_resolution >= 5 AND p.n - p.c_resolution >= 5 THEN p.c_resolution END AS with_resolution_version,
       CASE WHEN p.c_epic_a >= 5 AND p.n - p.c_epic_a >= 5 THEN p.c_epic_a END AS with_epic_version_a,
       CASE WHEN p.c_epic_b >= 5 AND p.n - p.c_epic_b >= 5 THEN p.c_epic_b END AS with_epic_version_b,
       CASE WHEN p.c_nature >= 5 AND p.n - p.c_nature >= 5 THEN p.c_nature END AS with_category_nature,
       CASE WHEN p.c_workflow >= 5 AND p.n - p.c_workflow >= 5 THEN p.c_workflow END AS with_workflow_option,
       CASE WHEN p.c_release_target >= 5 AND p.n - p.c_release_target >= 5 THEN p.c_release_target END AS with_release_target,
       CASE WHEN p.c_verification >= 5 AND p.n - p.c_verification >= 5 THEN p.c_verification END AS with_verification_required,
       CASE WHEN p.c_safety >= 5 AND p.n - p.c_safety >= 5 THEN p.c_safety END AS with_product_safety,
       CASE WHEN p.c_isp >= 5 AND p.n - p.c_isp >= 5 THEN p.c_isp END AS with_isp,
       CASE WHEN p.c_review >= 5 AND p.n - p.c_review >= 5 THEN p.c_review END AS with_code_review_status,
       CASE WHEN p.c_rank >= 5 AND p.n - p.c_rank >= 5 THEN p.c_rank END AS with_portfolio_rank,
       CASE WHEN p.c_customer >= 5 AND p.n - p.c_customer >= 5 THEN p.c_customer END AS with_customer_commitment,
       CASE WHEN p.c_source >= 5 AND p.n - p.c_source >= 5 THEN p.c_source END AS with_source_commitment,
       CASE WHEN p.c_strategic >= 5 AND p.n - p.c_strategic >= 5 THEN p.c_strategic END AS with_strategic_objective
FROM par_equipe p;

-- La limite déclarée de la conception D3, en français et en anglais, dans le commentaire de chaque vue trimestrielle (R-20261114-51).
COMMENT ON VIEW flow.v_team_fix_version_share IS 'Trois derniers trimestres clos. le plus ancien des trois trimestres peut perdre au plus un jour et quelques heures les derniers jours d''un trimestre (environ 1 %) / the oldest of the three quarters may lose at most one day and a few hours on the last days of a quarter (about 1 %)';
COMMENT ON VIEW flow.v_team_fix_version_lag IS 'Trois derniers trimestres clos. le plus ancien des trois trimestres peut perdre au plus un jour et quelques heures les derniers jours d''un trimestre (environ 1 %) / the oldest of the three quarters may lose at most one day and a few hours on the last days of a quarter (about 1 %)';
COMMENT ON VIEW flow.v_team_lead_time_throughput IS 'Trois derniers trimestres clos, et la ligne pooled_year, somme des trois. le plus ancien des trois trimestres peut perdre au plus un jour et quelques heures les derniers jours d''un trimestre (environ 1 %) / the oldest of the three quarters may lose at most one day and a few hours on the last days of a quarter (about 1 %)';
COMMENT ON VIEW flow.v_task_without_team_share IS 'Trois derniers trimestres clos. le plus ancien des trois trimestres peut perdre au plus un jour et quelques heures les derniers jours d''un trimestre (environ 1 %) / the oldest of the three quarters may lose at most one day and a few hours on the last days of a quarter (about 1 %)';
COMMENT ON VIEW flow.v_team_ready_queue IS 'Trois derniers trimestres clos. le plus ancien des trois trimestres peut perdre au plus un jour et quelques heures les derniers jours d''un trimestre (environ 1 %) / the oldest of the three quarters may lose at most one day and a few hours on the last days of a quarter (about 1 %)';
COMMENT ON VIEW flow.v_team_blocked_share IS 'Trois derniers trimestres clos. le plus ancien des trois trimestres peut perdre au plus un jour et quelques heures les derniers jours d''un trimestre (environ 1 %) / the oldest of the three quarters may lose at most one day and a few hours on the last days of a quarter (about 1 %)';
COMMENT ON VIEW flow.v_unplanned_share IS 'Trois derniers trimestres clos. le plus ancien des trois trimestres peut perdre au plus un jour et quelques heures les derniers jours d''un trimestre (environ 1 %) / the oldest of the three quarters may lose at most one day and a few hours on the last days of a quarter (about 1 %)';
COMMENT ON VIEW flow.v_team_flow_inout IS 'Trois derniers trimestres clos. le plus ancien des trois trimestres peut perdre au plus un jour et quelques heures les derniers jours d''un trimestre (environ 1 %) / the oldest of the three quarters may lose at most one day and a few hours on the last days of a quarter (about 1 %)';
COMMENT ON VIEW flow.v_team_delivery_fields_coverage IS 'Trois derniers trimestres clos. le plus ancien des trois trimestres peut perdre au plus un jour et quelques heures les derniers jours d''un trimestre (environ 1 %) / the oldest of the three quarters may lose at most one day and a few hours on the last days of a quarter (about 1 %)';

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle

-- Droits de la fonction : aucun pour PUBLIC, EXECUTE aux deux rôles qui lisent les vues.
REVOKE ALL ON FUNCTION flow.closed_quarter_starts(timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION flow.closed_quarter_starts(timestamptz) TO pmzilla_flow_views, pmzilla_mothra_views;
