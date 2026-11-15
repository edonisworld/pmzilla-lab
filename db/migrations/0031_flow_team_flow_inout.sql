-- Schéma touché : flow (une vue agrégée des panneaux du tableau de bord du périmètre produit de Mothra). Aucune donnée, aucun mot de passe, aucun rôle créé
-- ni modifié, aucune table changée.
-- Change mothra-slices, groupe 36, tâche 36.1, exception F12 (conception D35), plan R-150 (R-20261031-01, bloc 1, Q1 A et Q2 A).
--
-- NUMÉRO : cette migration prend 0031 parce que 0030 est réservé à la relation T3 de masking-sums (D17, branche pas encore fusionnée). Si l'ordre de fusion
-- change, elle est renumérotée au rebase (son nom, lui, ne change pas : tests et contrats la retrouvent par le suffixe `_flow_team_flow_inout.sql`).
--
--   flow.v_team_flow_inout   par équipe, ou pour le produit (ligne `(produit)`), par trimestre civil clos de l'année retenue (les quatre derniers trimestres
--                            terminés : le trimestre en cours n'a jamais de ligne) et par groupe de types, `story` ou `defect` : le nombre d'éléments CRÉÉS
--                            dans le trimestre (created) et le nombre d'éléments TERMINÉS dans le trimestre (done). Colonnes : team, quarter_start, type_group,
--                            created, done. Aucun grain semaine ni mois : le trimestre seul, pour les équipes comme pour le produit (décisions Q7, M3 et du
--                            2026-10-28).
--
-- Définitions :
--   * Groupe `story` (R-20261031-01, Q2 A) : les types Story et Task, comme le débit des rapports de flux et de v_team_lead_time_throughput (la relation T13
--     de masking-sums D16 n'est exacte que si le groupe couvre les deux). Groupe `defect` : les types de ref_unplanned_types (genre défaut), jamais une
--     liste en dur. Tout autre type est hors de la vue.
--   * Terminé : status_category 'Done' (sans casse) et une date de résolution, comme les rapports de flux ; créé : la date de création. Les tickets sortis de
--     l'export sont écartés. Le trimestre d'un élément est celui (civil, UTC) de sa date de création pour `created`, de sa date de résolution pour `done`.
--   * Rattachement : par l'équipe du ticket (flow.issues.team_id) seulement, jamais par lien, parent ou épic. Un élément sans équipe est compté sous la ligne
--     `(sans équipe)`, à part (défauts compris : le champ d'équipe des défauts est rempli pour environ deux tiers d'entre eux, R-20261029-07 ; D33 point 1) ;
--     il compte dans la ligne du produit.
--   * Exclusions des rapports de flux : les types de portefeuille (Epic, Initiative) sont retirés ici, écrits en dur comme le type Epic de la migration 0018
--     (une vue ne lit pas flux.yaml). PROJETS EXCLUS : la base ne porte aucune liste des projets exclus des rapports de flux (le réglage excluded_projects
--     vit dans flux.yaml) ; la vue ne peut donc pas les retirer. Point arrêté de la tâche 36.1, décidé par l'auteur (R-20261031-27, Q56) : une table
--     ref_excluded_projects, en change séparé, en place avant toute publication de comptes réels. D'ici là, la vue compte les éléments d'un projet exclu et
--     aucune publication sur données réelles n'a lieu (D34 point 7).
--
-- Masquage, dans la vue : une cellule de moins de 5 est masquée (NULL) par flow.mask_count (un zéro est masqué aussi). Famille de la vue : les cellules
-- d'une même colonne (created ou done) d'un même trimestre et d'un même groupe de types, lignes d'équipe et ligne `(sans équipe)` ; elles font le total du
-- produit. Règle de la ligne du produit (masking-sums D3, décision Q8) : la cellule du produit n'est montrée que si TOUTES les cellules d'équipe de sa
-- colonne (la ligne `(sans équipe)` comprise) sont visibles ; elle n'a alors aucun inconnu, et aucune différence ne redonne une cellule masquée. Les deux
-- colonnes n'ont entre elles aucune relation exacte propre à la vue : pas de total publié à compléter (D2). Bornes (BORNES de tools/flow_views.py) :
-- created et done valent (0, sans complément) : une ligne existe dès qu'un des deux comptes est au moins 1, l'autre peut valoir 0.
--
-- Relations avec d'autres vues, NON implémentées ici (décision R-20261031-01 Q1 A : une branche de spécification les ajoute à masking-sums D16 avant le
-- groupe 7 ; aucune publication de comptes réels d'ici là, D34 point 7) : T13 (done du groupe `story` contre le débit de v_team_lead_time_throughput) ;
-- les résolus par semaine de v_team_weekly_resolved contre `done` ; le total contre histoires plus défauts ; créés moins finis contre la variation du
-- stock ouvert. Cette vue ne REPREND RIEN de ce que D17 ferme (T3) : elle n'expose aucune ligne hebdomadaire, ses cellules sont de grain trimestre avec un
-- plancher bas de 0 (jamais un « chaque ligne vaut au moins 1 »), et elle ne montre ni ne retire aucune ligne de v_team_weekly_resolved. T13 reste ouverte :
-- `done` du groupe `story` visible alors que le débit de la même équipe est masqué ou retenu par D17 redonnerait le débit, aux projets exclus près.
-- Décision de l'auteur R-20261031-27, Q57 : T13 passe en priorité au groupe 7 de masking-sums, et la précaution de Q33 (ne pas lire en local les vues
-- hebdomadaire et de part d'une équipe dont le débit trimestriel est masqué) vaut aussi pour cette vue.
--
-- Droits : les droits par défaut du schéma donnent SELECT au rôle d'import et au rôle en lecture seule sur tout nouvel objet : ils sont retirés ici, à PUBLIC
-- et au rôle des vues de la qualité, puis SELECT est donné au seul rôle des vues. La vue lit les tables avec les droits de son propriétaire.

SET LOCAL ROLE pmzilla_owner;

CREATE VIEW flow.v_team_flow_inout AS
WITH trimestres AS (
    SELECT (date_trunc('quarter', now() AT TIME ZONE 'UTC') - make_interval(months => 3 * k))::date AS quarter_start
    FROM generate_series(1, 4) AS k       -- les quatre derniers trimestres terminés : le trimestre en cours n'y est jamais
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
      AND lower(i.type) NOT IN ('epic', 'initiative')   -- types de portefeuille ; les projets exclus : voir l'en-tête
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

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle

-- Droits : retirés d'abord (les droits par défaut du lot 1 s'appliquent à tout nouvel objet du propriétaire), puis accordés.
REVOKE ALL ON flow.v_team_flow_inout FROM PUBLIC, pmzilla_flow, pmzilla_flow_ro, pmzilla_quality_views;
GRANT SELECT ON flow.v_team_flow_inout TO pmzilla_flow_views;
