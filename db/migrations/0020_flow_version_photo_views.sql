-- Schéma touché : flow (vues flow.v_version_quality_photo et flow.v_team_fix_version_lag).
-- Change version-quality-photo (R-140, branche 1), décisions D8, D10, D11, D14, D15. Aucune table, aucune donnée, aucun mot de passe, aucun rôle.
--
-- flow.v_version_quality_photo : lit les tables de la migration précédente avec les droits de son propriétaire. Cinq sortes de lignes.
--   * Ligne de couverture : une par passage et semaine (source, couverture, lundi, instant), toujours, N adopté ou non. Aucune équipe, aucune
--     version, aucun compte, aucune part.
--   * Après l'adoption de N seulement (D11) : pour chaque version dont la date de sortie est connue, la semaine retenue est celle dont le lundi
--     tombe N semaines avant le lundi de la semaine de sortie. Ligne d'équipe et de version (cinq comptes), ligne « (produit) » de la version,
--     ligne libre d'équipe (quatre comptes et deux parts), ligne libre « (produit) », pour les semaines retenues seulement.
--   Avant N, ou quand toutes les dates de sortie sont nulles (D3 : rien ne les remplit dans ce change), la jointure des semaines retenues est
--   vide par construction : aucun compte, aucune part, aucune ligne de produit (le test de garde le vérifie sur chaque colonne).
--
-- Numéro de version opaque (D10) : la vue donne version_no, jamais le nom du registre. La raison d'une adoption n'est jamais lue.
-- n_modified_after_reading : vrai dès que le registre de N a plus d'une adoption ; n_previous_weeks et n_previous_adopted_on : l'adoption
-- juste avant la courante (nuls avec une seule adoption), sur chaque ligne, couverture comprise.
--
-- Masquage des semaines retenues (D11) : un compte sous 5 est masqué ; la partie de chaque paire (found_open, found), (reopened, corrected_now),
-- (corrected_at_week, corrected_now), (defects_without_affects, defects_created), (resolved_week_defects, resolved_week) l'est aussi quand la partie
-- ou le tout moins la partie est sous 5 ; une part l'est avec sa partie ou son tout. Une ligne « (produit) » est masquée, colonne par colonne, quand
-- ses cellules d'équipe masquées sont exactement une ou ont une somme sous 5 : la différence les redonnerait (cellules à zéro : voir plus bas).
--
-- flow.v_team_fix_version_lag : par équipe et trimestre civil de résolution (UTC), sur les quatre derniers trimestres terminés, les items résolus
-- avec une fix version courante (type Epic et tickets sortis de l'export écartés, comme v_team_fix_version_share), par délai entre la résolution et
-- la première pose d'une fix version dans les périodes : avant ou à la résolution, sous 7 jours, sous 30 jours, plus tard, et sans historique
-- (fix version présente, aucune période). Lisible avant N. Le type « Epic » est écrit en dur : une vue ne lit pas flux.yaml (le délai des seuls
-- défauts est une hypothèse à vérifier à la première lecture).
-- Masquage : une cellule sous 5 ; puis, quand les cellules masquées d'une ligne ont une somme sous 5, la plus petite cellule visible est masquée
-- aussi (les cinq cellules font les items visibles : la différence redonnerait la petite). Deux règles en plus (décisions de l'auteur du
-- 2026-10-23, elles révisent le renvoi de la fuite à deux dimensions à R-144) :
--   (a) une ligne d'équipe et de trimestre n'est montrée (toutes ses cellules de comptage) que si le détail de la part est visible pour la même
--       équipe et le même trimestre dans flow.v_team_fix_version_share (détail visible si et seulement si ni avec ni sans fix version sous 5, et
--       la ligne du produit selon sa règle) ; sinon toute la ligne est masquée. Même principe pour la ligne du produit du trimestre. Sans cela, le
--       nombre d'items de cette vue (le nombre avec fix version) redonnait un nombre que la part masque (18 sur 20 items : sans fix version 2).
--   (b) une cellule du produit n'est montrée que si TOUTES les cellules d'équipe de la même colonne sont visibles (option B du cadrage de R-144).
--
-- Cellule à zéro (décision de l'auteur du 2026-10-23, comme v_team_fix_version_share) : un zéro masqué compte comme une cellule masquée dans « exactement
-- une cellule masquée » et dans le masquage complémentaire : un zéro ne se retrouve pas par différence. Conséquence assumée : une ligne qui porte un
-- zéro masqué perd aussi sa plus petite cellule visible quand la somme des cellules masquées est sous 5.
--
-- Ligne du produit de la vue du retard (revue du 2026-10-23, règle (b) ci-dessus : remplace « exactement une ou somme sous 5 ») : une cellule du produit
-- est masquée dès qu'une cellule d'équipe de la même colonne l'est, ou que la ligne du produit n'est pas visible dans la vue de la part ; ces cellules
-- comptent parmi les cellules masquées de la ligne, de sorte qu'une seule cellule masquée, ou des cellules masquées de somme sous 5, entraînent le
-- masquage de la plus petite cellule visible. La vue de la part est lue avec les droits du propriétaire, comme les tables.
--
-- defects_without_affects (décision de l'auteur du 2026-10-23, remplace la règle « une seule version ») : la relation « défauts créés = sans affects
-- + défauts distincts avec au moins une affects version » est traitée comme une ligne à compléter (un défaut peut porter plusieurs affects versions :
-- la somme des trouvés par version la dépasse alors, le masquage reste prudent). Les termes sont les versions qui ont au moins un défaut trouvé ; un
-- terme est caché quand sa version n'est pas retenue cette semaine ou que sa cellule est masquée. Sans affects masqué et aucun terme caché : les
-- défauts créés sont masqués aussi. Sans affects visible et termes cachés exactement un ou de somme sous 5 : sans affects est masqué. Même règle sur
-- la ligne du produit (termes par version du produit).
--
-- Droits : les droits par défaut du schéma donnent SELECT au rôle d'import et au rôle en lecture seule sur tout nouvel objet : ils sont retirés
-- ici, à PUBLIC et au rôle des vues de la qualité, puis SELECT est donné au seul rôle des vues de flow.

SET LOCAL ROLE pmzilla_owner;

CREATE VIEW flow.v_version_quality_photo AS
WITH adoptions AS (
    SELECT weeks, adopted_on, row_number() OVER (ORDER BY id DESC) AS rang FROM flow.version_photo_n
),
courante AS (
    SELECT weeks AS n_weeks, adopted_on AS n_adopted_on FROM adoptions WHERE rang = 1
),
etat_n AS (
    SELECT (SELECT count(*) FROM adoptions) > 0 AS adopte,
           (SELECT count(*) FROM adoptions) > 1 AS modifie,
           (SELECT weeks FROM adoptions WHERE rang = 2) AS n_previous_weeks,
           (SELECT adopted_on FROM adoptions WHERE rang = 2) AS n_previous_adopted_on
),
couverture AS (
    SELECT r.id AS run_id, r.source, w.coverage, w.week_start, r.taken_at
    FROM flow.version_photo_weeks w JOIN flow.version_photo_runs r ON r.id = w.run_id
),
retenues AS (       -- vide tant que N n'est pas adopté (jointure avec « courante ») et pour une version sans date de sortie
    SELECT v.version_no, v.release_date, v.released,
           (v.release_date - (extract(isodow FROM v.release_date)::int - 1) - 7 * c.n_weeks) AS week_start,
           c.n_weeks, c.n_adopted_on
    FROM flow.version_photo_versions v CROSS JOIN courante c
    WHERE v.release_date IS NOT NULL
),
equipe_version AS (
    SELECT x.run_id, x.source, x.coverage, x.week_start, x.taken_at, e.team, e.version_no,
           rt.release_date, rt.released, rt.n_weeks, rt.n_adopted_on,
           e.found, e.found_open, e.corrected_at_week, e.corrected_now, e.reopened
    FROM flow.version_photo_rows e
    JOIN retenues rt ON rt.version_no = e.version_no AND rt.week_start = e.week_start
    JOIN couverture x ON x.week_start = e.week_start
),
equipe_version_vis AS (
    SELECT ev.*,
           (ev.found >= 5) AS v_found,
           (ev.found_open >= 5 AND ev.found - ev.found_open >= 5) AS v_found_open,
           (ev.corrected_at_week >= 5 AND ev.corrected_now - ev.corrected_at_week >= 5) AS v_corrected_at_week,
           (ev.corrected_now >= 5) AS v_corrected_now,
           (ev.reopened >= 5 AND ev.corrected_now - ev.reopened >= 5) AS v_reopened
    FROM equipe_version ev
),
produit_version AS (
    SELECT week_start, version_no,
           min(run_id) AS run_id, min(source) AS source, min(coverage) AS coverage, min(taken_at) AS taken_at,
           min(release_date) AS release_date, bool_or(released) AS released, min(n_weeks) AS n_weeks, min(n_adopted_on) AS n_adopted_on,
           sum(found)::bigint AS found, sum(found_open)::bigint AS found_open, sum(corrected_at_week)::bigint AS corrected_at_week,
           sum(corrected_now)::bigint AS corrected_now, sum(reopened)::bigint AS reopened,
           (count(*) FILTER (WHERE NOT v_found) >= 1
            AND (count(*) FILTER (WHERE NOT v_found) = 1
                 OR coalesce(sum(found) FILTER (WHERE NOT v_found), 0) < 5)) AS f_found,
           (count(*) FILTER (WHERE NOT v_found_open) >= 1
            AND (count(*) FILTER (WHERE NOT v_found_open) = 1
                 OR coalesce(sum(found_open) FILTER (WHERE NOT v_found_open), 0) < 5)) AS f_found_open,
           (count(*) FILTER (WHERE NOT v_corrected_at_week) >= 1
            AND (count(*) FILTER (WHERE NOT v_corrected_at_week) = 1
                 OR coalesce(sum(corrected_at_week) FILTER (WHERE NOT v_corrected_at_week), 0) < 5)) AS f_corrected_at_week,
           (count(*) FILTER (WHERE NOT v_corrected_now) >= 1
            AND (count(*) FILTER (WHERE NOT v_corrected_now) = 1
                 OR coalesce(sum(corrected_now) FILTER (WHERE NOT v_corrected_now), 0) < 5)) AS f_corrected_now,
           (count(*) FILTER (WHERE NOT v_reopened) >= 1
            AND (count(*) FILTER (WHERE NOT v_reopened) = 1
                 OR coalesce(sum(reopened) FILTER (WHERE NOT v_reopened), 0) < 5)) AS f_reopened
    FROM equipe_version_vis
    GROUP BY week_start, version_no
),
libre_base AS (
    -- Défauts sans affects (décision du 2026-10-23, remplace la règle « une seule version ») : un défaut peut porter plusieurs affects versions
    -- (clé de flow.issue_current_versions : ticket, genre, nom), la somme des défauts trouvés par version dépasse alors les défauts distincts
    -- qui ont au moins une affects version. La relation réelle est : défauts créés = sans affects + défauts distincts avec au moins une affects,
    -- et la vue publie les trouvés par version. Elle est traitée comme une ligne à compléter : les termes sont les versions qui ont au moins un
    -- défaut trouvé dans l'équipe et la semaine ; un terme est « caché » quand sa version n'est pas retenue cette semaine ou que sa cellule est
    -- masquée (sous 5).
    SELECT x.run_id, x.source, x.coverage, x.week_start, x.taken_at, e.team, c.n_weeks, c.n_adopted_on,
           e.defects_created, e.defects_without_affects, e.resolved_week, e.resolved_week_defects,
           nv.n_caches, nv.somme_cachee,
           (e.defects_created >= 5) AS b_dc,
           (e.defects_without_affects >= 5 AND e.defects_created - e.defects_without_affects >= 5) AS b_dwa,
           (e.resolved_week >= 5) AS v_rw,
           (e.resolved_week_defects >= 5 AND e.resolved_week - e.resolved_week_defects >= 5) AS v_rwd
    FROM flow.version_photo_rows e
    JOIN (SELECT DISTINCT week_start FROM retenues) s ON s.week_start = e.week_start
    JOIN couverture x ON x.week_start = e.week_start
    CROSS JOIN courante c
    CROSS JOIN LATERAL (
        SELECT count(*) FILTER (WHERE NOT (ev.found >= 5
                                           AND EXISTS (SELECT 1 FROM retenues rt WHERE rt.version_no = ev.version_no AND rt.week_start = ev.week_start)))
                   AS n_caches,
               coalesce(sum(ev.found) FILTER (WHERE NOT (ev.found >= 5
                                                         AND EXISTS (SELECT 1 FROM retenues rt
                                                                     WHERE rt.version_no = ev.version_no AND rt.week_start = ev.week_start))), 0)::bigint
                   AS somme_cachee
        FROM flow.version_photo_rows ev
        WHERE ev.week_start = e.week_start AND ev.team = e.team AND ev.version_no IS NOT NULL AND ev.found > 0
    ) nv
    WHERE e.version_no IS NULL
),
libre AS (
    -- Masquage complémentaire de la ligne « créés = sans affects + trouvés » : cellules masquées = sans affects s'il l'est + termes cachés. Si elles
    -- sont exactement une ou de somme sous 5, la plus petite cellule visible de la ligne l'est aussi : sans affects s'il est visible (plus petit que
    -- les défauts créés), sinon les défauts créés.
    SELECT b.run_id, b.source, b.coverage, b.week_start, b.taken_at, b.team, b.n_weeks, b.n_adopted_on,
           b.defects_created, b.defects_without_affects, b.resolved_week, b.resolved_week_defects,
           (b.b_dc AND NOT (m.besoin AND NOT b.b_dwa)) AS v_dc,
           (b.b_dwa AND NOT m.besoin) AS v_dwa,
           b.v_rw, b.v_rwd
    FROM libre_base b
    CROSS JOIN LATERAL (
        SELECT (((NOT b.b_dwa)::int + b.n_caches) >= 1
                AND (((NOT b.b_dwa)::int + b.n_caches) = 1
                     OR (CASE WHEN b.b_dwa THEN 0 ELSE b.defects_without_affects END) + b.somme_cachee < 5)) AS besoin
    ) m
),
termes_produit AS (
    -- Mêmes termes au niveau du produit : par version qui a au moins un défaut trouvé dans la semaine, caché quand la version n'est pas retenue
    -- ou que sa cellule du produit est masquée.
    SELECT t.week_start,
           count(*) FILTER (WHERE NOT (pv.version_no IS NOT NULL AND pv.found >= 5 AND NOT pv.f_found)) AS n_caches,
           coalesce(sum(t.found) FILTER (WHERE NOT (pv.version_no IS NOT NULL AND pv.found >= 5 AND NOT pv.f_found)), 0)::bigint AS somme_cachee
    FROM (SELECT week_start, version_no, sum(found)::bigint AS found
          FROM flow.version_photo_rows
          WHERE version_no IS NOT NULL AND week_start IN (SELECT week_start FROM retenues)
          GROUP BY week_start, version_no
          HAVING sum(found) > 0) t
    LEFT JOIN produit_version pv ON pv.week_start = t.week_start AND pv.version_no = t.version_no
    GROUP BY t.week_start
),
produit_libre_brut AS (
    SELECT week_start,
           min(run_id) AS run_id, min(source) AS source, min(coverage) AS coverage, min(taken_at) AS taken_at,
           min(n_weeks) AS n_weeks, min(n_adopted_on) AS n_adopted_on,
           sum(defects_created)::bigint AS defects_created, sum(defects_without_affects)::bigint AS defects_without_affects,
           sum(resolved_week)::bigint AS resolved_week, sum(resolved_week_defects)::bigint AS resolved_week_defects,
           (count(*) FILTER (WHERE NOT v_dc) >= 1
            AND (count(*) FILTER (WHERE NOT v_dc) = 1
                 OR coalesce(sum(defects_created) FILTER (WHERE NOT v_dc), 0) < 5)) AS f_dc,
           (count(*) FILTER (WHERE NOT v_dwa) >= 1
            AND (count(*) FILTER (WHERE NOT v_dwa) = 1
                 OR coalesce(sum(defects_without_affects) FILTER (WHERE NOT v_dwa), 0) < 5)) AS f_dwa,
           (count(*) FILTER (WHERE NOT v_rw) >= 1
            AND (count(*) FILTER (WHERE NOT v_rw) = 1
                 OR coalesce(sum(resolved_week) FILTER (WHERE NOT v_rw), 0) < 5)) AS f_rw,
           (count(*) FILTER (WHERE NOT v_rwd) >= 1
            AND (count(*) FILTER (WHERE NOT v_rwd) = 1
                 OR coalesce(sum(resolved_week_defects) FILTER (WHERE NOT v_rwd), 0) < 5)) AS f_rwd
    FROM libre
    GROUP BY week_start
),
produit_libre AS (
    -- Même règle sur la ligne du produit : ses cellules masquées (sans affects s'il l'est, par sa règle de paire ou par celle des équipes) et ses
    -- termes cachés ; une ligne qui s'en trouve exactement une, ou de somme sous 5, masque sa plus petite cellule visible aussi.
    SELECT g.*,
           (m.p_dwa AND NOT m.besoin) AS v_dwa_p,
           (g.defects_created >= 5 AND NOT g.f_dc AND NOT (m.besoin AND NOT m.p_dwa)) AS v_dc_p
    FROM produit_libre_brut g
    LEFT JOIN termes_produit tp ON tp.week_start = g.week_start
    CROSS JOIN LATERAL (
        SELECT (g.defects_without_affects >= 5 AND g.defects_created - g.defects_without_affects >= 5 AND NOT g.f_dwa) AS p_dwa,
               coalesce(tp.n_caches, 0) AS nc, coalesce(tp.somme_cachee, 0) AS sc
    ) b
    CROSS JOIN LATERAL (
        SELECT b.p_dwa,
               (((NOT b.p_dwa)::int + b.nc) >= 1
                AND (((NOT b.p_dwa)::int + b.nc) = 1
                     OR (CASE WHEN b.p_dwa THEN 0 ELSE g.defects_without_affects END) + b.sc < 5)) AS besoin
    ) m
)
-- 1. lignes de couverture
SELECT x.run_id, x.source, x.coverage, x.week_start, x.taken_at,
       n.adopte AS n_adopted, n.modifie AS n_modified_after_reading, n.n_previous_weeks, n.n_previous_adopted_on,
       NULL::integer AS n_weeks, NULL::date AS n_adopted_on, NULL::text AS team, NULL::integer AS version_no,
       NULL::date AS release_date, NULL::boolean AS released,
       NULL::bigint AS found, NULL::bigint AS found_open, NULL::bigint AS corrected_at_week, NULL::bigint AS corrected_now,
       NULL::bigint AS reopened, NULL::bigint AS defects_created, NULL::bigint AS defects_without_affects,
       NULL::bigint AS resolved_week, NULL::bigint AS resolved_week_defects,
       NULL::numeric AS correction_share_percent, NULL::numeric AS without_affects_share_percent
FROM couverture x CROSS JOIN etat_n n
UNION ALL
-- 2. équipe et version
SELECT v.run_id, v.source, v.coverage, v.week_start, v.taken_at,
       n.adopte, n.modifie, n.n_previous_weeks, n.n_previous_adopted_on,
       v.n_weeks, v.n_adopted_on, v.team, v.version_no, v.release_date, v.released,
       CASE WHEN v.v_found THEN v.found END, CASE WHEN v.v_found_open THEN v.found_open END,
       CASE WHEN v.v_corrected_at_week THEN v.corrected_at_week END, CASE WHEN v.v_corrected_now THEN v.corrected_now END,
       CASE WHEN v.v_reopened THEN v.reopened END, NULL::bigint, NULL::bigint, NULL::bigint, NULL::bigint,
       NULL::numeric, NULL::numeric
FROM equipe_version_vis v CROSS JOIN etat_n n
UNION ALL
-- 3. produit et version
SELECT p.run_id, p.source, p.coverage, p.week_start, p.taken_at,
       n.adopte, n.modifie, n.n_previous_weeks, n.n_previous_adopted_on,
       p.n_weeks, p.n_adopted_on, '(produit)'::text, p.version_no, p.release_date, p.released,
       CASE WHEN p.found >= 5 AND NOT p.f_found THEN p.found END,
       CASE WHEN p.found_open >= 5 AND p.found - p.found_open >= 5 AND NOT p.f_found_open THEN p.found_open END,
       CASE WHEN p.corrected_at_week >= 5 AND p.corrected_now - p.corrected_at_week >= 5 AND NOT p.f_corrected_at_week THEN p.corrected_at_week END,
       CASE WHEN p.corrected_now >= 5 AND NOT p.f_corrected_now THEN p.corrected_now END,
       CASE WHEN p.reopened >= 5 AND p.corrected_now - p.reopened >= 5 AND NOT p.f_reopened THEN p.reopened END,
       NULL::bigint, NULL::bigint, NULL::bigint, NULL::bigint, NULL::numeric, NULL::numeric
FROM produit_version p CROSS JOIN etat_n n
UNION ALL
-- 4. équipe, sans version
SELECT l.run_id, l.source, l.coverage, l.week_start, l.taken_at,
       n.adopte, n.modifie, n.n_previous_weeks, n.n_previous_adopted_on,
       l.n_weeks, l.n_adopted_on, l.team, NULL::integer, NULL::date, NULL::boolean,
       NULL::bigint, NULL::bigint, NULL::bigint, NULL::bigint, NULL::bigint,
       CASE WHEN l.v_dc THEN l.defects_created END, CASE WHEN l.v_dwa THEN l.defects_without_affects END,
       CASE WHEN l.v_rw THEN l.resolved_week END, CASE WHEN l.v_rwd THEN l.resolved_week_defects END,
       CASE WHEN l.v_rwd AND l.v_rw THEN round(100.0 * l.resolved_week_defects / l.resolved_week, 1) END,
       CASE WHEN l.v_dwa AND l.v_dc THEN round(100.0 * l.defects_without_affects / l.defects_created, 1) END
FROM libre l CROSS JOIN etat_n n
UNION ALL
-- 5. produit, sans version
SELECT q.run_id, q.source, q.coverage, q.week_start, q.taken_at,
       n.adopte, n.modifie, n.n_previous_weeks, n.n_previous_adopted_on,
       q.n_weeks, q.n_adopted_on, '(produit)'::text, NULL::integer, NULL::date, NULL::boolean,
       NULL::bigint, NULL::bigint, NULL::bigint, NULL::bigint, NULL::bigint,
       CASE WHEN q.v_dc_p THEN q.defects_created END,
       CASE WHEN q.v_dwa_p THEN q.defects_without_affects END,
       CASE WHEN q.resolved_week >= 5 AND NOT q.f_rw THEN q.resolved_week END,
       CASE WHEN q.resolved_week_defects >= 5 AND q.resolved_week - q.resolved_week_defects >= 5 AND NOT q.f_rwd THEN q.resolved_week_defects END,
       CASE WHEN q.resolved_week_defects >= 5 AND q.resolved_week >= 5 AND q.resolved_week - q.resolved_week_defects >= 5
                 AND NOT q.f_rwd AND NOT q.f_rw
            THEN round(100.0 * q.resolved_week_defects / q.resolved_week, 1) END,
       CASE WHEN q.v_dwa_p AND q.v_dc_p THEN round(100.0 * q.defects_without_affects / q.defects_created, 1) END
FROM produit_libre q CROSS JOIN etat_n n;

CREATE VIEW flow.v_team_fix_version_lag AS
WITH trimestres AS (
    SELECT (date_trunc('quarter', now() AT TIME ZONE 'UTC') - make_interval(months => 3 * k))::date AS quarter_start
    FROM generate_series(1, 4) AS k       -- les quatre derniers trimestres terminés : le trimestre en cours n'y est jamais
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
    -- et le même trimestre. La vue de la part (migration 0018) donne with_fix_version nul quand le détail est masqué : détail visible si et
    -- seulement si ni avec ni sans fix version n'est sous 5. Le nombre d'items de cette vue-ci est le nombre avec fix version de la part.
    SELECT team, quarter_start FROM flow.v_team_fix_version_share WHERE team <> '(produit)' AND with_fix_version IS NOT NULL
),
part_produit AS (
    -- Même principe pour la ligne du produit du trimestre (sa règle propre dans 0018 : cellules du produit et fuites d'équipe).
    SELECT quarter_start FROM flow.v_team_fix_version_share WHERE team = '(produit)' AND with_fix_version IS NOT NULL
),
equipe_vis AS (
    SELECT e.team, e.quarter_start, e.n, e.b1, e.b2, e.b3, e.b4, e.b5,
           (s.team IS NOT NULL AND e.n >= 5) AS vn,
           (s.team IS NOT NULL AND e.n >= 5 AND e.b1 >= 5 AND NOT (m.compl AND m.petit = 1)) AS v1,
           (s.team IS NOT NULL AND e.n >= 5 AND e.b2 >= 5 AND NOT (m.compl AND m.petit = 2)) AS v2,
           (s.team IS NOT NULL AND e.n >= 5 AND e.b3 >= 5 AND NOT (m.compl AND m.petit = 3)) AS v3,
           (s.team IS NOT NULL AND e.n >= 5 AND e.b4 >= 5 AND NOT (m.compl AND m.petit = 4)) AS v4,
           (s.team IS NOT NULL AND e.n >= 5 AND e.b5 >= 5 AND NOT (m.compl AND m.petit = 5)) AS v5
    FROM par_equipe e
    LEFT JOIN part_equipe s ON s.team = e.team AND s.quarter_start = e.quarter_start
    CROSS JOIN LATERAL (
        SELECT (((e.b1 < 5)::int + (e.b2 < 5)::int + (e.b3 < 5)::int + (e.b4 < 5)::int + (e.b5 < 5)::int) >= 1       -- un zéro masqué compte
                AND ((CASE WHEN e.b1 < 5 THEN e.b1 ELSE 0 END) + (CASE WHEN e.b2 < 5 THEN e.b2 ELSE 0 END)
                     + (CASE WHEN e.b3 < 5 THEN e.b3 ELSE 0 END) + (CASE WHEN e.b4 < 5 THEN e.b4 ELSE 0 END)
                     + (CASE WHEN e.b5 < 5 THEN e.b5 ELSE 0 END)) < 5) AS compl,
               (SELECT b.idx FROM (VALUES (1, e.b1), (2, e.b2), (3, e.b3), (4, e.b4), (5, e.b5)) AS b(idx, val)
                WHERE b.val >= 5 ORDER BY b.val, b.idx LIMIT 1) AS petit
    ) m
),
produit AS (
    SELECT quarter_start, sum(n)::bigint AS n, sum(b1)::bigint AS b1, sum(b2)::bigint AS b2, sum(b3)::bigint AS b3,
           sum(b4)::bigint AS b4, sum(b5)::bigint AS b5,
           bool_and(vn) AS tn, bool_and(v1) AS t1, bool_and(v2) AS t2, bool_and(v3) AS t3, bool_and(v4) AS t4, bool_and(v5) AS t5   -- toutes les équipes visibles
    FROM equipe_vis
    GROUP BY quarter_start
),
produit_vis AS (
    -- Décision 1(b) du 2026-10-23 (option B de R-144, remplace « exactement une ou somme sous 5 ») : une cellule du produit n'est montrée que si la
    -- ligne du produit est visible dans la vue de la part et que TOUTES les cellules d'équipe de la même colonne le sont (une ligne d'équipe masquée
    -- entière en compte aucune) : une somme de cellules masquées ne se retrouve plus par différence avec le produit. Les cellules ainsi masquées
    -- comptent, comme les autres, parmi les cellules masquées de la ligne : exactement une, ou une somme sous 5, masque aussi la plus petite
    -- cellule visible (les cinq tranches font les items).
    SELECT p.quarter_start, p.n, p.b1, p.b2, p.b3, p.b4, p.b5,
           (g.ok AND p.tn) AS vn,
           (q.a1 AND NOT (m.nb >= 1 AND (m.nb = 1 OR m.sm < 5) AND m.petit = 1)) AS v1,
           (q.a2 AND NOT (m.nb >= 1 AND (m.nb = 1 OR m.sm < 5) AND m.petit = 2)) AS v2,
           (q.a3 AND NOT (m.nb >= 1 AND (m.nb = 1 OR m.sm < 5) AND m.petit = 3)) AS v3,
           (q.a4 AND NOT (m.nb >= 1 AND (m.nb = 1 OR m.sm < 5) AND m.petit = 4)) AS v4,
           (q.a5 AND NOT (m.nb >= 1 AND (m.nb = 1 OR m.sm < 5) AND m.petit = 5)) AS v5
    FROM produit p
    CROSS JOIN LATERAL (SELECT EXISTS (SELECT 1 FROM part_produit pp WHERE pp.quarter_start = p.quarter_start) AS ok) g
    CROSS JOIN LATERAL (
        SELECT (g.ok AND p.t1) AS a1, (g.ok AND p.t2) AS a2, (g.ok AND p.t3) AS a3, (g.ok AND p.t4) AS a4, (g.ok AND p.t5) AS a5
    ) q
    CROSS JOIN LATERAL (
        SELECT ((NOT q.a1)::int + (NOT q.a2)::int + (NOT q.a3)::int + (NOT q.a4)::int + (NOT q.a5)::int) AS nb,
               ((CASE WHEN q.a1 THEN 0 ELSE p.b1 END) + (CASE WHEN q.a2 THEN 0 ELSE p.b2 END) + (CASE WHEN q.a3 THEN 0 ELSE p.b3 END)
                + (CASE WHEN q.a4 THEN 0 ELSE p.b4 END) + (CASE WHEN q.a5 THEN 0 ELSE p.b5 END)) AS sm,
               (SELECT b.idx FROM (VALUES (1, p.b1, q.a1), (2, p.b2, q.a2), (3, p.b3, q.a3), (4, p.b4, q.a4), (5, p.b5, q.a5)) AS b(idx, val, ok)
                WHERE b.ok ORDER BY b.val, b.idx LIMIT 1) AS petit
    ) m
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

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle

-- Droits : retirés d'abord (les droits par défaut du schéma s'appliquent à tout nouvel objet du propriétaire), puis accordés.
REVOKE ALL ON flow.v_version_quality_photo, flow.v_team_fix_version_lag FROM PUBLIC, pmzilla_flow, pmzilla_flow_ro, pmzilla_quality_views;
GRANT SELECT ON flow.v_version_quality_photo, flow.v_team_fix_version_lag TO pmzilla_flow_views;
