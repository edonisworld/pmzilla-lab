-- Schéma touché : flow (vue flow.v_team_delivery_fields_coverage). Aucune donnée, aucun mot de passe, aucun rôle créé ni modifié, aucune table changée.
-- Change jira-delivery-fields (R-20261102-14 à -36), design D9.
--
-- Couverture des champs de livraison : par équipe, par trimestre civil de résolution (UTC) sur les quatre derniers trimestres terminés (le
-- trimestre en cours n'y est jamais) et par genre d'item (story pour les items qui ne sont pas des épics, epic pour les épics, sur leur propre
-- ligne), le nombre d'items terminés (les tickets sortis de l'export sont écartés) et, pour chaque champ de livraison, le nombre d'items où ce
-- champ est rempli (un indicateur oui/non compte quand il est vrai). L'équipe est la première équipe du ticket, « (sans équipe) » à défaut.
-- Aucune ligne du produit. Aucune version, aucun sprint, aucune valeur d'option, aucune clé, aucun titre, aucune personne : la vue ne compte que
-- des champs remplis.
--
-- Colonnes : team, quarter_start (premier jour du trimestre), item_kind, items, puis with_sprint, with_target_version, with_resolution_version,
-- with_epic_version_a, with_epic_version_b, with_category_nature, with_workflow_option, with_release_target, with_verification_required,
-- with_product_safety, with_isp, with_code_review_status, with_portfolio_rank, with_customer_commitment, with_source_commitment,
-- with_strategic_objective.
--
-- Masquage, dans la vue : un nombre d'items sous 5 est nul (flow.mask_count). Un compte de champs remplis est nul quand le nombre de remplis
-- OU le nombre de non remplis est sous 5 (leur somme est le nombre d'items, visible : un petit nombre se retrouverait par différence). Le
-- type « Epic » est écrit en dur : une vue ne lit pas flux.yaml.
--
-- Droits : les droits par défaut du schéma donnent SELECT au rôle d'import et au rôle en lecture seule sur tout nouvel objet : ils sont retirés ici,
-- à PUBLIC et au rôle des vues de la qualité, puis SELECT est donné au seul rôle des vues. La vue lit les tables des champs de livraison avec
-- les droits de son propriétaire ; aucun rôle des vues ne lit ces tables.

SET LOCAL ROLE pmzilla_owner;

CREATE VIEW flow.v_team_delivery_fields_coverage AS
WITH trimestres AS (
    SELECT (date_trunc('quarter', now() AT TIME ZONE 'UTC') - make_interval(months => 3 * k))::date AS quarter_start
    FROM generate_series(1, 4) AS k       -- les quatre derniers trimestres terminés : le trimestre en cours n'y est jamais
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
           (d.release_target IS NOT NULL) AS f_release_target,
           (d.verification_required IS NOT NULL) AS f_verification,
           (d.product_safety IS NOT NULL) AS f_safety,
           (d.isp IS NOT NULL) AS f_isp,
           (d.code_review_status IS NOT NULL) AS f_review,
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

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle

-- Droits : retirés d'abord (les droits par défaut du lot 1 s'appliquent à tout nouvel objet du propriétaire), puis accordés.
REVOKE ALL ON flow.v_team_delivery_fields_coverage FROM PUBLIC, pmzilla_flow, pmzilla_flow_ro, pmzilla_quality_views;
GRANT SELECT ON flow.v_team_delivery_fields_coverage TO pmzilla_flow_views;
