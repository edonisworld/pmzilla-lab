-- Schéma touché : flow (vues flow.v_team_fix_version_share, flow.v_version_quality_photo, flow.v_teams, flow.v_team_jira_ids, flow.v_team_fix_version_lag ; fonctions flow.masking_version, flow.photo_serie et flow.retard_d2).
-- Change masking-sums (R-144), conception D2, D3, D5, D9 et D12. Aucune donnée, aucun mot de passe, aucun rôle créé, modifié ou supprimé, aucune table changée.
-- Les colonnes des vues sont celles qu'elles avaient : CREATE OR REPLACE VIEW suffit, aucune vue n'est supprimée (D12 : suppression et création seulement
-- quand des colonnes changent). La vue du retard (v_team_fix_version_lag) est recréée aussi (décision O de l'auteur du 2026-10-27, spec database-migrations) :
-- elle lit la vue de la part recréée ici et sa règle de complément devient celle de D2 (au moins deux cellules masquées, somme d'au moins 5, somme
-- différente de la somme des bornes hautes ; la borne haute d'une cellule masquée est le plus grand de 4 et de la plus petite cellule visible de la
-- ligne ; sans cellule visible, ce sont les items qui sont masqués). Les droits sont donnés de nouveau.
-- Ce fichier garde « masquage_somme » dans son nom pour la traçabilité seulement : la garde de adopt-n lit flow.masking_version() (D9).
--
-- Bornes d'une cellule masquée (table BORNES de tools/flow_views.py, qu'un test compare à ces lignes) : lo = valeur la plus basse possible (1 pour une
-- ligne de GROUP BY, 0 pour une tranche, un compte filtré ou une paire) ; complement = oui quand un masquage complémentaire peut s'appliquer au groupe,
-- la borne haute étant alors le plus grand de 4 et de la plus petite cellule visible (greatest(4, ...)), sinon 4.
-- BORNES v_team_fix_version_share.items lo=1 complement=non
-- BORNES v_team_fix_version_share.with_fix_version lo=0 complement=non
-- BORNES v_version_quality_photo.found lo=0 complement=non
-- BORNES v_version_quality_photo.found_open lo=0 complement=non
-- BORNES v_version_quality_photo.corrected_at_week lo=0 complement=non
-- BORNES v_version_quality_photo.corrected_now lo=0 complement=non
-- BORNES v_version_quality_photo.reopened lo=0 complement=non
-- BORNES v_version_quality_photo.defects_created lo=0 complement=non
-- BORNES v_version_quality_photo.defects_without_affects lo=0 complement=non
-- BORNES v_version_quality_photo.resolved_week lo=0 complement=non
-- BORNES v_version_quality_photo.resolved_week_defects lo=0 complement=non
-- BORNES v_teams.tickets lo=1 complement=non
-- BORNES v_team_jira_ids.tickets lo=1 complement=oui
-- BORNES v_team_fix_version_lag.items lo=1 complement=non
-- BORNES v_team_fix_version_lag.before_or_at_resolution lo=0 complement=oui
-- BORNES v_team_fix_version_lag.within_7_days lo=0 complement=oui
-- BORNES v_team_fix_version_lag.within_30_days lo=0 complement=oui
-- BORNES v_team_fix_version_lag.later lo=0 complement=oui
-- BORNES v_team_fix_version_lag.no_history lo=0 complement=oui
-- Limite de passes de la boucle de la ligne sans version de la photo, calculée par série (W : nombre de semaines de la série ; passes_max de
-- tools/flow_views.py, `limite := 2 * n + 1` de flow.photo_serie ; un test compare la formule des deux côtés). Justification : au plus 2 x W passes qui
-- changent (2 cellules par semaine, la visibilité ne passant que de vrai à faux) puis une stable ; limite atteinte : erreur, rien de publié :
-- PASSES-MAX 2 x W + 1
--
-- Principe de décision (revue R-144) : un masquage se décide sur ce que les valeurs publiées permettent de déduire, en SQL comme en Python ; la
-- ligne à compléter de la photo utilise donc la somme dérivée des cellules publiées (défauts créés moins sans affects moins trouvés visibles), non la
-- somme vraie des termes cachés. Deux écarts voulus où le SQL masque plus que le Python (jamais moins) : (1) la règle de la ligne à compléter est
-- appliquée avec le nombre de termes masqués publiés (versions retenues) puis avec celui de tous les termes cachés, versions non retenues comprises,
-- que le SQL voit et pas le Python ; un masquage décidé par l'une ou l'autre suffit ; (2) une ligne sans version dont la semaine n'a aucune ligne de version
-- (une semaine qui n'a que des trouvés nuls est traitée pareil en SQL et en Python) passe par la règle D5-e dans le SQL (puis par le point fixe : sans affects masqué, les créés le sont aussi, conservateur), alors que le Python, sans
-- terme publié, ne masque rien.
--
-- Dépendance : flow.v_team_jira_ids lit flow.v_teams (le compte publié du nom décide du masquage de son plus petit identifiant) ; v_teams est donc
-- recréée avant elle, et une suppression ultérieure de v_teams exige CASCADE ou la recréation des deux vues (D12).
-- Critère (D1) : aucune cellule masquée n'a une seule valeur possible, aucune somme déductible de cellules masquées n'est sous le seuil (5 ici ;
-- le lecteur relève le seuil, jamais en dessous). L'attaquant connaît ces règles, lit toutes les vues du rôle des vues et en déduit des bornes.
--
-- v_team_fix_version_share (D2, D3, X10) : la relation « items = avec + sans » d'une ligne d'équipe. Quand le détail est masqué et qu'aucune borne
-- n'est publiée, le compte sans fix version vaut au moins 5, donc 5 items sans aucun avec fix version donnent « avec = 0 » : les items de la ligne
-- sont masqués (décision de l'auteur du 2026-10-26, question 2). Une cellule du produit n'est montrée que si toutes les cellules d'équipe de la même
-- colonne (items, ou détail) le sont : la ligne « (produit) » ne redonne plus une cellule d'équipe par différence (X3, X4, X5).
--
-- v_version_quality_photo (D3, D5-d, D5-e) : une cellule du produit (par version et sur la ligne sans version) n'est montrée que si toutes les cellules
-- d'équipe de sa colonne le sont (X11). Les comptes cumulés de la ligne sans version (défauts créés, sans affects) sont lus semaine retenue après
-- semaine retenue, par équipe et pour le produit : une cellule dont l'écart avec la dernière cellule visible d'une semaine antérieure est de 1 à 4 en
-- valeur absolue est masquée (X8) ; la cellule masquée compte ensuite parmi les cellules cachées de la ligne. Défauts créés = sans affects + défauts
-- distincts avec affects : l'excès de la somme des trouvés par version sur ces défauts (défauts à plusieurs affects versions) est un terme caché ;
-- quand tous les termes de la ligne sont publiés et que cet excès est sous 5, zéro compris, la plus petite cellule visible de la ligne (sans affects)
-- est masquée aussi (X12, la limite connue de R-140 est levée).
--
-- v_teams et v_team_jira_ids (D5-a, D5-b, X1, X2), une famille : le compte de l'équipe est masqué quand le compte moins la somme des comptes de statut
-- visibles de l'équipe est au plus le nombre de cellules de statut masquées (au moins une) ; quand tous ses comptes d'identifiant et son compte sont
-- visibles et que la somme des identifiants moins le compte est, en valeur absolue, de 1 à 4 (la règle reste après le nettoyage de Jira) ; et quand la
-- relation « compte = somme des identifiants » laisserait des identifiants masqués déductibles (un seul, somme sous 5, somme des bornes basses ou
-- hautes) : alors le plus petit identifiant visible est masqué à son tour, et le compte avec lui s'il n'en reste aucun.
--
-- flow.masking_version() (D9) : version du masquage, croissante (toute évolution ultérieure du masquage la relève, jamais ne l'abaisse), exécutable par le
-- seul rôle d'import ; adopt-n la lit au lieu d'un nom de migration.

SET LOCAL ROLE pmzilla_owner;

CREATE OR REPLACE VIEW flow.v_team_fix_version_share AS
WITH trimestres AS (
    SELECT (date_trunc('quarter', now() AT TIME ZONE 'UTC') - make_interval(months => 3 * k))::date AS quarter_start
    FROM generate_series(1, 4) AS k       -- les quatre derniers trimestres terminés : le trimestre en cours n'y est jamais
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

-- Règles de la ligne sans version de la photo pour une série (une équipe, ou le produit après D3), repassées jusqu'à un point fixe (décisions de l'auteur
-- du 2026-10-27) : à chaque passe, D5-d (une cellule dont l'écart avec la dernière cellule encore publiée d'une semaine antérieure est de 1 à 4 est
-- masquée), puis D2 sur chaque semaine (une cellule masquée par D5-e, par D5-d ou par une passe précédente change la relation « créés = sans affects +
-- trouvés », et une cellule restée seule cachée se lirait par différence : créés 20, trouvé 12 visible, sans affects 8). Les tableaux sont dans l'ordre
-- des semaines retenues ; ok_dc et ok_dwa : les cellules publiées au départ (vue, paires, D3 pour le produit) ; np, nc, sv : termes cachés publiés,
-- tous les termes cachés, somme des trouvés visibles. Fonction pure : aucune table lue. Chaque passe qui change quelque chose masque au moins une des
-- 2 x W cellules de la série (W semaines retenues), la visibilité ne passant que de vrai à faux : au plus 2 x W passes qui changent, une dernière stable.
-- La limite PASSES-MAX vaut 2 x W + 1 (W : longueur des tableaux) ; elle n'est jamais atteinte en théorie, et si elle l'était la fonction lèverait une erreur.
-- EXECUTE est accordé au seul rôle des vues, en fin de fichier (voir là pourquoi il est nécessaire).
CREATE FUNCTION flow.photo_serie(crees bigint[], sans bigint[], ok_dc boolean[], ok_dwa boolean[], np bigint[], nc bigint[], sv bigint[])
    RETURNS TABLE (rang integer, v_dc boolean, v_dwa boolean)
    LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    passe integer := 0;
    n integer := coalesce(array_length(crees, 1), 0);
    limite integer := 2 * n + 1;
    dc boolean[] := ok_dc;
    dwa boolean[] := ok_dwa;
    avant_dc boolean[];
    avant_dwa boolean[];
    i integer;
    m bigint;
    dernier_c bigint;
    dernier_a bigint;
    besoin boolean;
    nouveau_dc boolean;
    nouveau_dwa boolean;
BEGIN
    LOOP
        IF passe >= limite THEN
            RAISE EXCEPTION 'v_version_quality_photo : le masquage de la ligne sans version ne se stabilise pas en % passes', limite;
        END IF;
        passe := passe + 1;
        avant_dc := dc;
        avant_dwa := dwa;
        dernier_c := NULL;
        dernier_a := NULL;
        FOR i IN 1..n LOOP                                   -- D5-d sur les seules cellules encore publiées
            IF dc[i] THEN
                IF dernier_c IS NOT NULL AND abs(crees[i] - dernier_c) BETWEEN 1 AND 4 THEN
                    dc[i] := false;
                ELSE
                    dernier_c := crees[i];
                END IF;
            END IF;
            IF dwa[i] THEN
                IF dernier_a IS NOT NULL AND abs(sans[i] - dernier_a) BETWEEN 1 AND 4 THEN
                    dwa[i] := false;
                ELSE
                    dernier_a := sans[i];
                END IF;
            END IF;
        END LOOP;
        FOR i IN 1..n LOOP                                   -- D2 sur chaque semaine
            besoin := false;
            IF dc[i] THEN
                FOREACH m IN ARRAY ARRAY[np[i], nc[i]] LOOP
                    besoin := besoin OR coalesce(CASE WHEN dwa[i]
                        THEN ((m >= 1 AND (m < 2 OR crees[i] - sans[i] - sv[i] < 5 OR crees[i] - sans[i] - sv[i] = 4 * m))
                              OR (m = 0 AND sv[i] - (crees[i] - sans[i]) < 5))
                        ELSE (1 + m < 2 OR crees[i] - sv[i] < 5 OR crees[i] - sv[i] = 4 * (1 + m))
                        END, false);
                END LOOP;
            END IF;
            nouveau_dc := dc[i] AND NOT (besoin AND NOT dwa[i]);
            nouveau_dwa := dwa[i] AND NOT besoin;
            dc[i] := nouveau_dc;
            dwa[i] := nouveau_dwa;
        END LOOP;
        IF dc IS NOT DISTINCT FROM avant_dc AND dwa IS NOT DISTINCT FROM avant_dwa THEN       -- n = 0 : tableaux nuls, stables
            EXIT;
        END IF;
    END LOOP;
    FOR i IN 1..n LOOP
        rang := i;
        v_dc := dc[i];
        v_dwa := dwa[i];
        RETURN NEXT;
    END LOOP;
END
$$;

-- Règle de complément D2 des cinq tranches du retard (revue 3, M1), repassée jusqu'à ce que plus rien ne change, comme _regle_ligne de
-- tools/flow_views.py : `ok` dit que les items de la ligne sont publiés ; a1 à a5 disent quelles tranches le sont avant la règle. Cellules cachées : k
-- (un zéro masqué compte) ; sans cellule visible, ou si k >= 2 et la somme S des cachées est d'au moins 5 et différente de k fois la borne haute (le plus
-- grand de 4 et de la plus petite cellule visible), la ligne est sûre ; sinon la plus petite cellule visible (à égalité, la première) est masquée et la
-- vérification repart ; sans cellule visible les items sont masqués à leur tour. Chaque tour masque une cellule : au plus cinq tours, aucune limite à
-- déclarer. Fonction pure : aucune table lue.
CREATE FUNCTION flow.retard_d2(b1 bigint, b2 bigint, b3 bigint, b4 bigint, b5 bigint, ok boolean,
                               a1 boolean, a2 boolean, a3 boolean, a4 boolean, a5 boolean)
    RETURNS TABLE (vn boolean, v1 boolean, v2 boolean, v3 boolean, v4 boolean, v5 boolean)
    LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    val bigint[] := ARRAY[b1, b2, b3, b4, b5];
    vis boolean[] := ARRAY[a1 AND ok, a2 AND ok, a3 AND ok, a4 AND ok, a5 AND ok];
    i integer;
    k integer;
    petit integer;
    somme bigint;
    haut bigint;
BEGIN
    vn := ok;
    IF ok THEN
        LOOP
            k := 0;
            somme := b1 + b2 + b3 + b4 + b5;
            petit := NULL;
            FOR i IN 1..5 LOOP
                IF vis[i] THEN
                    somme := somme - val[i];
                    IF petit IS NULL OR val[i] < val[petit] THEN
                        petit := i;
                    END IF;
                ELSE
                    k := k + 1;
                END IF;
            END LOOP;
            EXIT WHEN k = 0;
            haut := greatest(4, coalesce(val[petit], 4));
            EXIT WHEN k >= 2 AND somme >= 5 AND somme <> k * haut;
            IF petit IS NULL THEN
                vn := false;
                EXIT;
            END IF;
            vis[petit] := false;
        END LOOP;
    END IF;
    v1 := vis[1];
    v2 := vis[2];
    v3 := vis[3];
    v4 := vis[4];
    v5 := vis[5];
    RETURN NEXT;
END
$$;

CREATE OR REPLACE VIEW flow.v_version_quality_photo AS
WITH RECURSIVE adoptions AS (
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
    -- D3 : une cellule du produit n'est montrée que si toutes les cellules d'équipe de la même colonne le sont ; f_* : une cellule d'équipe est masquée.
    SELECT week_start, version_no,
           min(run_id) AS run_id, min(source) AS source, min(coverage) AS coverage, min(taken_at) AS taken_at,
           min(release_date) AS release_date, bool_or(released) AS released, min(n_weeks) AS n_weeks, min(n_adopted_on) AS n_adopted_on,
           sum(found)::bigint AS found, sum(found_open)::bigint AS found_open, sum(corrected_at_week)::bigint AS corrected_at_week,
           sum(corrected_now)::bigint AS corrected_now, sum(reopened)::bigint AS reopened,
           (count(*) FILTER (WHERE NOT v_found) >= 1) AS f_found,
           (count(*) FILTER (WHERE NOT v_found_open) >= 1) AS f_found_open,
           (count(*) FILTER (WHERE NOT v_corrected_at_week) >= 1) AS f_corrected_at_week,
           (count(*) FILTER (WHERE NOT v_corrected_now) >= 1) AS f_corrected_now,
           (count(*) FILTER (WHERE NOT v_reopened) >= 1) AS f_reopened
    FROM equipe_version_vis
    GROUP BY week_start, version_no
),
libre_base AS (
    -- Défauts sans affects : la relation réelle est « défauts créés = sans affects + défauts distincts avec au moins une affects version », la somme
    -- des trouvés par version la dépasse quand un défaut porte plusieurs affects versions (l'excès). Les termes sont les versions qui ont une ligne
    -- dans l'équipe et la semaine (un trouvé nul compris) ; un terme est « caché » quand sa version n'est pas retenue cette semaine ou que sa cellule est masquée
    -- (sous 5). somme_visible : la somme des termes visibles, pour mesurer l'excès quand toute la ligne est publiée.
    SELECT x.run_id, x.source, x.coverage, x.week_start, x.taken_at, e.team, c.n_weeks, c.n_adopted_on,
           e.defects_created, e.defects_without_affects, e.resolved_week, e.resolved_week_defects,
           nv.n_caches, nv.n_publies, nv.somme_cachee, nv.somme_visible,
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
               count(*) FILTER (WHERE ev.found < 5
                                AND EXISTS (SELECT 1 FROM retenues rt WHERE rt.version_no = ev.version_no AND rt.week_start = ev.week_start))
                   AS n_publies,       -- les termes cachés que les lignes publiées montrent : une version retenue dont la cellule est masquée
               coalesce(sum(ev.found) FILTER (WHERE NOT (ev.found >= 5
                                                         AND EXISTS (SELECT 1 FROM retenues rt
                                                                     WHERE rt.version_no = ev.version_no AND rt.week_start = ev.week_start))), 0)::bigint
                   AS somme_cachee,
               coalesce(sum(ev.found) FILTER (WHERE ev.found >= 5
                                              AND EXISTS (SELECT 1 FROM retenues rt WHERE rt.version_no = ev.version_no AND rt.week_start = ev.week_start)), 0)::bigint
                   AS somme_visible
        FROM flow.version_photo_rows ev
        WHERE ev.week_start = e.week_start AND ev.team = e.team AND ev.version_no IS NOT NULL    -- un trouvé nul est un terme caché, comme en Python
    ) nv
    WHERE e.version_no IS NULL
),
libre_rang AS (
    SELECT b.*, row_number() OVER (PARTITION BY b.team ORDER BY b.week_start, b.run_id) AS rang FROM libre_base b
),
libre_serie AS (
    -- Une série par équipe, semaines retenues dans l'ordre : D5-d sur les seules cellules publiées puis D2, repassés jusqu'à ce que plus rien ne change
    -- (flow.photo_serie). Cellules de départ : celles que la vue et leurs paires publient (b_dc, b_dwa).
    SELECT g.team, s.rang, s.v_dc, s.v_dwa
    FROM (SELECT r.team,
                 array_agg(r.defects_created ORDER BY r.rang) AS crees, array_agg(r.defects_without_affects ORDER BY r.rang) AS sans,
                 array_agg(coalesce(r.b_dc, false) ORDER BY r.rang) AS ok_dc, array_agg(coalesce(r.b_dwa, false) ORDER BY r.rang) AS ok_dwa,
                 array_agg(r.n_publies ORDER BY r.rang) AS np, array_agg(r.n_caches ORDER BY r.rang) AS nc,
                 array_agg(r.somme_visible ORDER BY r.rang) AS sv
          FROM libre_rang r GROUP BY r.team) g
    CROSS JOIN LATERAL flow.photo_serie(g.crees, g.sans, g.ok_dc, g.ok_dwa, g.np, g.nc, g.sv) s
),
libre AS (
    -- Ligne à compléter « créés = sans affects + trouvés », décidée sur les valeurs publiées (les défauts créés doivent l'être). Sans affects publié et
    -- n termes cachés : S = créés - sans affects - trouvés visibles ; au moins deux termes, S d'au moins 5, S différent de 4 fois n (somme des bornes
    -- hautes, B1 de la revue ; la somme des bornes basses est 0) ; sinon sans affects est masqué. Sans affects masqué : les termes cachés sont lui et les
    -- n autres, S = créés - trouvés visibles, même règle avec 4 fois (1 + n) ; sinon les défauts créés sont masqués. D5-e : aucun terme caché et un
    -- excès des trouvés sous 5, zéro compris, masquent sans affects. La règle s'applique deux fois, avec n = n_publies (les termes masqués que le
    -- Python voit : versions retenues) et avec n = n_caches (le SQL compte aussi les versions non retenues, qu'il voit) ; un masquage décidé par l'une
    -- des deux suffit : le SQL masque au moins autant que le Python (écart voulu, plus strict), jamais moins (revue 2, B1). Tout cela dans la fonction.
    SELECT b.run_id, b.source, b.coverage, b.week_start, b.taken_at, b.team, b.n_weeks, b.n_adopted_on,
           b.defects_created, b.defects_without_affects, b.resolved_week, b.resolved_week_defects,
           s.v_dc, s.v_dwa,
           b.v_rw, b.v_rwd
    FROM libre_rang b
    JOIN libre_serie s ON s.team = b.team AND s.rang = b.rang
),
termes_produit AS (
    -- Mêmes termes au niveau du produit : par version qui a une ligne dans la semaine (un trouvé nul compris), caché quand la version n'est pas
    -- retenue ou que sa cellule du produit est masquée.
    SELECT t.week_start,
           count(*) FILTER (WHERE NOT (pv.version_no IS NOT NULL AND pv.found >= 5 AND NOT pv.f_found)) AS n_caches,
           count(*) FILTER (WHERE pv.version_no IS NOT NULL AND NOT (pv.found >= 5 AND NOT pv.f_found)) AS n_publies,
           coalesce(sum(t.found) FILTER (WHERE NOT (pv.version_no IS NOT NULL AND pv.found >= 5 AND NOT pv.f_found)), 0)::bigint AS somme_cachee,
           coalesce(sum(t.found) FILTER (WHERE (pv.version_no IS NOT NULL AND pv.found >= 5 AND NOT pv.f_found)), 0)::bigint AS somme_visible
    FROM (SELECT week_start, version_no, sum(found)::bigint AS found
          FROM flow.version_photo_rows
          WHERE version_no IS NOT NULL AND week_start IN (SELECT week_start FROM retenues)
          GROUP BY week_start, version_no) t                   -- une version de trouvé nul reste un terme caché du produit
    LEFT JOIN produit_version pv ON pv.week_start = t.week_start AND pv.version_no = t.version_no
    GROUP BY t.week_start
),
produit_libre_brut AS (
    -- D3 : f_* : une cellule d'équipe de la colonne est masquée, la cellule du produit l'est alors.
    SELECT week_start,
           min(run_id) AS run_id, min(source) AS source, min(coverage) AS coverage, min(taken_at) AS taken_at,
           min(n_weeks) AS n_weeks, min(n_adopted_on) AS n_adopted_on,
           sum(defects_created)::bigint AS defects_created, sum(defects_without_affects)::bigint AS defects_without_affects,
           sum(resolved_week)::bigint AS resolved_week, sum(resolved_week_defects)::bigint AS resolved_week_defects,
           (count(*) FILTER (WHERE NOT v_dc) >= 1) AS f_dc,
           (count(*) FILTER (WHERE NOT v_dwa) >= 1) AS f_dwa,
           (count(*) FILTER (WHERE NOT v_rw) >= 1) AS f_rw,
           (count(*) FILTER (WHERE NOT v_rwd) >= 1) AS f_rwd
    FROM libre
    GROUP BY week_start
),
produit_base AS (
    SELECT g.*, (g.defects_created >= 5 AND NOT g.f_dc) AS b_dc,
           (g.defects_without_affects >= 5 AND g.defects_created - g.defects_without_affects >= 5 AND NOT g.f_dwa) AS b_dwa
    FROM produit_libre_brut g
),
produit_serie AS (
    -- D3 d'abord (b_dc, b_dwa du produit_base : une cellule d'équipe masquée masque celle du produit), puis la série du produit dans l'ordre des
    -- semaines retenues : D5-d sur les seules cellules publiées et D2 (mêmes sommes dérivées des cellules publiées, 4 fois n et 4 fois (1 + n)),
    -- repassés jusqu'à ce que plus rien ne change ; la ligne entièrement publiée dont l'excès est sous 5 masque sans affects (D5-e).
    SELECT s.rang, s.v_dc, s.v_dwa
    FROM (SELECT array_agg(g.defects_created ORDER BY g.week_start) AS crees, array_agg(g.defects_without_affects ORDER BY g.week_start) AS sans,
                 array_agg(coalesce(g.b_dc, false) ORDER BY g.week_start) AS ok_dc, array_agg(coalesce(g.b_dwa, false) ORDER BY g.week_start) AS ok_dwa,
                 array_agg(coalesce(tp.n_publies, 0) ORDER BY g.week_start) AS np, array_agg(coalesce(tp.n_caches, 0) ORDER BY g.week_start) AS nc,
                 array_agg(coalesce(tp.somme_visible, 0) ORDER BY g.week_start) AS sv
          FROM produit_base g LEFT JOIN termes_produit tp ON tp.week_start = g.week_start) a
    CROSS JOIN LATERAL flow.photo_serie(a.crees, a.sans, a.ok_dc, a.ok_dwa, a.np, a.nc, a.sv) s
    WHERE a.crees IS NOT NULL
),
produit_libre AS (
    SELECT g.*, s.v_dwa AS v_dwa_p, s.v_dc AS v_dc_p
    FROM (SELECT p.*, row_number() OVER (ORDER BY p.week_start) AS rang FROM produit_base p) g
    JOIN produit_serie s ON s.rang = g.rang
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

CREATE OR REPLACE VIEW flow.v_teams AS
WITH comptes AS (
    SELECT t.id, t.name, t.team_type, count(i.key) AS n
    FROM flow.teams t
    LEFT JOIN flow.issue_teams it ON it.team_id = t.id
    LEFT JOIN flow.issues i ON i.key = it.issue_key AND i.out_of_export_at IS NULL
    GROUP BY t.id, t.name, t.team_type
),
statuts AS (       -- D5-a : les cellules de flow.v_team_status de chaque équipe (première équipe du ticket)
    SELECT g.team_id, count(*) FILTER (WHERE g.c < 5) AS k, coalesce(sum(g.c) FILTER (WHERE g.c >= 5), 0) AS visibles
    FROM (SELECT i.team_id, i.type, i.status_category, i.status, count(*) AS c
          FROM flow.issues i
          WHERE i.out_of_export_at IS NULL AND i.team_id IS NOT NULL
          GROUP BY 1, 2, 3, 4) g
    GROUP BY g.team_id
),
ids_bruts AS (
    SELECT e.element ->> 'name' AS team, e.element ->> 'jira_team_id' AS jira_team_id, count(DISTINCT dernier.issue_key) AS n
    FROM (
        SELECT DISTINCT ON (s.issue_key) s.issue_key, s.teams
        FROM flow.raw_issue_snapshots s
        JOIN flow.issues i ON i.key = s.issue_key AND i.out_of_export_at IS NULL
        ORDER BY s.issue_key, s.run_id DESC
    ) dernier
    CROSS JOIN LATERAL jsonb_array_elements(dernier.teams) AS e(element)
    WHERE e.element ->> 'jira_team_id' IS NOT NULL
    GROUP BY 1, 2
),
rangs AS (         -- les identifiants visibles d'un nom, du plus petit au plus grand (à égalité, par identifiant)
    SELECT b.team, b.jira_team_id, b.n,
           row_number() OVER (PARTITION BY b.team ORDER BY b.n, b.jira_team_id) AS r
    FROM ids_bruts b
    WHERE b.n >= 5
),
famille AS (       -- D5-b : les identifiants du même nom, avec le compte brut du nom ; k0 identifiants masqués, v visibles
    SELECT c.name AS team, c.n AS total,
           count(*) FILTER (WHERE b.n < 5) AS k0,
           count(*) FILTER (WHERE b.n >= 5) AS v,
           coalesce(sum(b.n) FILTER (WHERE b.n >= 5), 0) AS visibles
    FROM comptes c
    JOIN ids_bruts b ON b.team = c.name
    GROUP BY c.name, c.n
),
paliers AS (       -- palier p : les p plus petits identifiants visibles sont masqués en complément ; k termes masqués, somme S = compte - visibles restants
    SELECT f.team, p AS palier, f.k0 + p AS k,
           f.total - coalesce((SELECT sum(r.n) FROM rangs r WHERE r.team = f.team AND r.r > p), 0) AS s,
           greatest(4, coalesce((SELECT r.n FROM rangs r WHERE r.team = f.team AND r.r = p + 1), 4)) AS haut,
           (p = f.v) AS dernier
    FROM famille f
    CROSS JOIN LATERAL generate_series(0, f.v) AS p
    WHERE f.k0 >= 1
),
arret AS (         -- D2 : la vérification s'arrête quand la relation est impossible, ou possible sans épingler (au moins deux, S d'au moins 5, S hors des bornes)
    SELECT t.team, t.palier, t.dernier,
           (NOT (t.s >= t.k AND t.s <= t.k * t.haut)
            OR (t.k >= 2 AND t.s >= 5 AND t.s <> t.k AND t.s <> t.k * t.haut)) AS rompt
    FROM paliers t
),
fin AS (           -- premier palier d'arrêt ; au dernier palier sans arrêt, aucun identifiant ne reste visible et le nom est masqué
    SELECT DISTINCT ON (a.team) a.team, a.palier AS masques, (a.dernier AND NOT a.rompt) AS nom_masque
    FROM arret a
    WHERE a.rompt OR a.dernier
    ORDER BY a.team, a.palier
)
SELECT c.name AS team, c.team_type,
       CASE WHEN c.n < 5 THEN NULL
            WHEN s.k >= 1 AND c.n - s.visibles <= s.k THEN NULL                                    -- D5-a : une cellule de statut serait épinglée
            WHEN f.k0 = 0 AND abs(f.visibles - c.n) BETWEEN 1 AND 4 THEN NULL                        -- D5-b : écart de 1 à 4 avec les identifiants
            WHEN f.k0 >= 1 AND fi.nom_masque THEN NULL                                               -- compte = somme des identifiants : plus aucun visible
            ELSE c.n END AS tickets
FROM comptes c
LEFT JOIN statuts s ON s.team_id = c.id
LEFT JOIN famille f ON f.team = c.name
LEFT JOIN fin fi ON fi.team = c.name;

CREATE OR REPLACE VIEW flow.v_team_jira_ids AS
WITH ids_bruts AS (
    SELECT e.element ->> 'name' AS team, e.element ->> 'jira_team_id' AS jira_team_id, count(DISTINCT dernier.issue_key) AS n
    FROM (
        SELECT DISTINCT ON (s.issue_key) s.issue_key, s.teams
        FROM flow.raw_issue_snapshots s
        JOIN flow.issues i ON i.key = s.issue_key AND i.out_of_export_at IS NULL
        ORDER BY s.issue_key, s.run_id DESC
    ) dernier
    CROSS JOIN LATERAL jsonb_array_elements(dernier.teams) AS e(element)
    WHERE e.element ->> 'jira_team_id' IS NOT NULL
    GROUP BY 1, 2
),
rangs AS (         -- les identifiants visibles d'un nom, du plus petit au plus grand (à égalité, par identifiant)
    SELECT b.team, b.jira_team_id, b.n,
           row_number() OVER (PARTITION BY b.team ORDER BY b.n, b.jira_team_id) AS r
    FROM ids_bruts b
    WHERE b.n >= 5
),
famille AS (
    SELECT b.team,
           count(*) FILTER (WHERE b.n < 5) AS k0,
           count(*) FILTER (WHERE b.n >= 5) AS v
    FROM ids_bruts b
    GROUP BY b.team
),
noms_visibles AS ( -- les noms dont la vue des noms publie le compte (celle-ci applique D5-a, D5-b et le compte sous 5) ; les autres sont masqués
    SELECT vt.team, vt.tickets AS total FROM flow.v_teams vt WHERE vt.tickets IS NOT NULL
),
paliers AS (       -- comme flow.v_teams, pour un nom dont le compte est publié et qui a des identifiants masqués
    SELECT f.team, p AS palier, f.k0 + p AS k,
           nv.total - coalesce((SELECT sum(r.n) FROM rangs r WHERE r.team = f.team AND r.r > p), 0) AS s,
           greatest(4, coalesce((SELECT r.n FROM rangs r WHERE r.team = f.team AND r.r = p + 1), 4)) AS haut,
           (p = f.v) AS dernier
    FROM famille f
    JOIN noms_visibles nv ON nv.team = f.team
    CROSS JOIN LATERAL generate_series(0, f.v) AS p
    WHERE f.k0 >= 1
),
arret AS (
    SELECT t.team, t.palier, t.dernier,
           (NOT (t.s >= t.k AND t.s <= t.k * t.haut)
            OR (t.k >= 2 AND t.s >= 5 AND t.s <> t.k AND t.s <> t.k * t.haut)) AS rompt
    FROM paliers t
),
fin AS (
    SELECT DISTINCT ON (a.team) a.team, a.palier AS masques
    FROM arret a
    WHERE a.rompt OR a.dernier
    ORDER BY a.team, a.palier
),
lignes AS (
    SELECT b.team, b.jira_team_id, b.n, r.r,
           (nv.team IS NULL) AS masque_avant,         -- m1, 5.11 option A élargie : le compte du nom est masqué, TOUS ses identifiants visibles le sont aussi
           coalesce(fi.masques, 0) AS masques
    FROM ids_bruts b
    LEFT JOIN rangs r ON r.team = b.team AND r.jira_team_id = b.jira_team_id
    LEFT JOIN noms_visibles nv ON nv.team = b.team
    LEFT JOIN fin fi ON fi.team = b.team
)
SELECT x.team, x.jira_team_id,
       CASE WHEN x.n < 5 THEN NULL
            WHEN x.masque_avant THEN NULL
            WHEN x.r <= x.masques THEN NULL
            ELSE x.n END AS tickets
FROM lignes x;

CREATE OR REPLACE VIEW flow.v_team_fix_version_lag AS
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

CREATE FUNCTION flow.masking_version() RETURNS integer
    LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$ SELECT 1 $$;

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle

-- Droits : retirés d'abord (les droits par défaut du schéma s'appliquent à tout nouvel objet du propriétaire), puis accordés, comme 0014, 0018 et 0020.
REVOKE ALL ON flow.v_team_fix_version_share FROM PUBLIC, pmzilla_flow, pmzilla_flow_ro, pmzilla_quality_views;
GRANT SELECT ON flow.v_team_fix_version_share TO pmzilla_flow_views;
REVOKE ALL ON flow.v_version_quality_photo FROM PUBLIC, pmzilla_flow, pmzilla_flow_ro, pmzilla_quality_views;
GRANT SELECT ON flow.v_version_quality_photo TO pmzilla_flow_views;
REVOKE ALL ON flow.v_teams FROM PUBLIC, pmzilla_flow, pmzilla_flow_ro, pmzilla_quality_views;
GRANT SELECT ON flow.v_teams TO pmzilla_flow_views;
REVOKE ALL ON flow.v_team_jira_ids FROM PUBLIC, pmzilla_flow, pmzilla_flow_ro, pmzilla_quality_views;
GRANT SELECT ON flow.v_team_jira_ids TO pmzilla_flow_views;
REVOKE ALL ON flow.v_team_fix_version_lag FROM PUBLIC, pmzilla_flow, pmzilla_flow_ro, pmzilla_quality_views;
GRANT SELECT ON flow.v_team_fix_version_lag TO pmzilla_flow_views;

-- Fonction de la règle complémentaire de la photo : EXECUTE au seul rôle des vues. En PostgreSQL, le droit EXECUTE d'une fonction appelée dans une
-- vue est vérifié pour l'utilisateur qui lit la vue, non pour son propriétaire (le contraire des tables) : sans lui, pmzilla_flow_views ne pourrait
-- plus lire v_version_quality_photo. La fonction ne lit aucune table : l'accorder n'ouvre aucune donnée.
REVOKE ALL ON FUNCTION flow.photo_serie(bigint[], bigint[], boolean[], boolean[], bigint[], bigint[], bigint[])
    FROM PUBLIC, pmzilla_flow, pmzilla_flow_views, pmzilla_flow_ro, pmzilla_quality_views;
GRANT EXECUTE ON FUNCTION flow.photo_serie(bigint[], bigint[], boolean[], boolean[], bigint[], bigint[], bigint[]) TO pmzilla_flow_views;
-- Même règle de droits pour la règle de complément du retard (flow.retard_d2) : pure, EXECUTE au seul rôle des vues.
REVOKE ALL ON FUNCTION flow.retard_d2(bigint, bigint, bigint, bigint, bigint, boolean, boolean, boolean, boolean, boolean, boolean)
    FROM PUBLIC, pmzilla_flow, pmzilla_flow_views, pmzilla_flow_ro, pmzilla_quality_views;
GRANT EXECUTE ON FUNCTION flow.retard_d2(bigint, bigint, bigint, bigint, bigint, boolean, boolean, boolean, boolean, boolean, boolean) TO pmzilla_flow_views;

-- Marqueur (D9) : exécutable par le seul rôle d'import ; ni PUBLIC, ni le rôle des vues, ni la lecture seule, ni les vues de la qualité.
REVOKE ALL ON FUNCTION flow.masking_version() FROM PUBLIC, pmzilla_flow_views, pmzilla_flow_ro, pmzilla_quality_views;
GRANT EXECUTE ON FUNCTION flow.masking_version() TO pmzilla_flow;
