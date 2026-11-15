-- Schéma touché : flow (vue flow.v_team_fix_version_share).
-- Change flow-version-share : par équipe et par trimestre civil de résolution (UTC, comme la vue hebdomadaire), sur les quatre derniers
-- trimestres terminés (sans le trimestre en cours : du début du trimestre qui précède de quatre le trimestre en cours jusqu'au début du
-- trimestre en cours exclu), le nombre d'items terminés, le nombre de ceux qui portent une fix version courante (présence seulement) et
-- la part en pourcent. Les items de type Epic, les tickets sortis de l'export et les tickets non résolus n'y sont pas ; l'équipe est la
-- première équipe du ticket (comme les autres vues), « (sans équipe) » à défaut. Une ligne « (produit) » par trimestre compte chaque
-- item une fois. Une version d'affects seule ne compte pas. Aucun nom de version, aucune clé, aucun titre, aucune personne.
--
-- Colonnes : team, quarter_start (premier jour du trimestre), items, with_fix_version, share_percent (un chiffre après la virgule),
-- with_fix_version_min.
--
-- Borne basse (décision de l'auteur du 2026-10-23, D10) : quand les items d'une équipe sont visibles (au moins 5) et que le nombre sans
-- fix version est sous 5, la colonne with_fix_version_min publie items - 4, un nombre qui ne dépend que des items visibles : le nombre
-- exact et la part restent masqués, et la borne ne donne aucune valeur exacte (ni par elle-même, ni par différence avec la ligne produit,
-- dont le masquage complémentaire est inchangé). Nulle sinon, et toujours nulle pour la ligne « (produit) ».
--
-- Masquage, dans la vue : une cellule d'équipe de moins de 5 items est masquée (les trois valeurs). Masquage complémentaire : le nombre
-- avec fix version et la part sont masqués dès que le nombre avec ou le nombre sans fix version est sous 5 (leur somme est le nombre
-- d'items, visible : un petit nombre se retrouverait par différence). Ligne du produit : toute la ligne d'un trimestre est masquée si
-- ses propres cellules sont sous le seuil, ou si les cellules d'équipe masquées de ce trimestre sont exactement une, ou si leur somme
-- (items, avec, ou sans fix version) est sous 5 : la différence avec les cellules visibles les redonnerait. Un item de plusieurs
-- équipes compte une fois, pour sa première équipe seulement : la règle est exacte.
--
-- Le type « Epic » est écrit en dur : une vue ne lit pas flux.yaml (les autres types de niveau portefeuille, s'il y en a, sont comptés).
--
-- Droits : les droits par défaut du schéma donnent SELECT au rôle d'import et au rôle en lecture seule sur tout nouvel objet : ils sont
-- retirés ici, à PUBLIC et au rôle des vues de la qualité, puis SELECT est donné au seul rôle des vues. La vue lit flow.issue_current_versions
-- avec les droits de son propriétaire. Aucune donnée, aucun mot de passe, aucun rôle créé ni modifié, aucune table changée.

SET LOCAL ROLE pmzilla_owner;

CREATE VIEW flow.v_team_fix_version_share AS
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
    SELECT p.*, (p.n >= 5) AS items_ok, (p.n >= 5 AND p.f >= 5 AND p.g >= 5) AS detail_ok, (p.n >= 5 AND p.g < 5) AS borne_ok
    FROM par_equipe p
),
produit AS (
    SELECT quarter_start, count(*) AS n,
           count(*) FILTER (WHERE has_fix) AS f,
           count(*) FILTER (WHERE NOT has_fix) AS g
    FROM dans_la_fenetre
    GROUP BY quarter_start
),
fuites AS (       -- trimestres dont la ligne du produit redonnerait, par différence, une cellule d'équipe masquée
    SELECT quarter_start,
           (count(*) FILTER (WHERE NOT items_ok) >= 1
            AND (count(*) FILTER (WHERE NOT items_ok) = 1 OR coalesce(sum(n) FILTER (WHERE NOT items_ok), 0) < 5)) AS fuite_items,
           (count(*) FILTER (WHERE NOT detail_ok) >= 1
            AND (count(*) FILTER (WHERE NOT detail_ok) = 1
                 OR coalesce(sum(f) FILTER (WHERE NOT detail_ok), 0) < 5
                 OR coalesce(sum(g) FILTER (WHERE NOT detail_ok), 0) < 5)) AS fuite_detail
    FROM equipes
    GROUP BY quarter_start
)
SELECT e.team, e.quarter_start,
       CASE WHEN e.items_ok THEN e.n END AS items,
       CASE WHEN e.detail_ok THEN e.f END AS with_fix_version,
       CASE WHEN e.detail_ok THEN round(100.0 * e.f / e.n, 1) END AS share_percent,
       CASE WHEN e.borne_ok THEN e.n - 4 END AS with_fix_version_min
FROM equipes e
UNION ALL
SELECT '(produit)'::text AS team, p.quarter_start,
       CASE WHEN p.n >= 5 AND NOT u.fuite_items AND NOT u.fuite_detail THEN p.n END AS items,
       CASE WHEN p.n >= 5 AND p.f >= 5 AND p.g >= 5 AND NOT u.fuite_items AND NOT u.fuite_detail THEN p.f END AS with_fix_version,
       CASE WHEN p.n >= 5 AND p.f >= 5 AND p.g >= 5 AND NOT u.fuite_items AND NOT u.fuite_detail
            THEN round(100.0 * p.f / p.n, 1) END AS share_percent,
       NULL::bigint AS with_fix_version_min       -- jamais de borne pour le produit : un produit à moins de 5 sans version masque déjà ses équipes
FROM produit p
JOIN fuites u ON u.quarter_start = p.quarter_start;

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle

-- Droits : retirés d'abord (les droits par défaut du lot 1 s'appliquent à tout nouvel objet du propriétaire), puis accordés.
REVOKE ALL ON flow.v_team_fix_version_share FROM PUBLIC, pmzilla_flow, pmzilla_flow_ro, pmzilla_quality_views;
GRANT SELECT ON flow.v_team_fix_version_share TO pmzilla_flow_views;
