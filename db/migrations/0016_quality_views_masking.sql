-- Schéma touché : quality (les trois vues agrégées recréées, fonction quality.mask_verdicts) ; aucune table, aucun rôle créé ni modifié.
-- Change story-quality-audit, décision de l'auteur du 2026-10-20 (R-94, Q1 (a) et Q2 (b)), design D5, D15, D18, O13 et T7 : un compte
-- de moins de 5 n'est jamais retrouvable, ni par différence dans une ligne, ni par différence entre la ligne du produit et les lignes
-- d'équipe. Aucune donnée, aucun mot de passe. Les vues sont supprimées puis recréées (des colonnes s'ajoutent et la logique change) :
-- elles retrouvent leurs droits à la fin, SELECT au seul rôle des vues comme en 0010.
--
-- quality_by_team et quality_by_product, masquage complémentaire : les quatre comptes d'une ligne (met, not_met, not_applicable,
-- undetermined) ont pour somme `audited`, qui est public (couverture, autre ligne de critère). Une cellule de moins de 5 est masquée ;
-- tant que la somme des cellules masquées d'une ligne (que `audited` moins les cellules visibles redonne) reste sous 5, la plus petite
-- cellule visible est masquée aussi (égalité : l'ordre des colonnes). Un seul compte masqué entraîne donc toujours un second, et
-- plusieurs zéros masqués ne se retrouvent pas par leur somme nulle. `audited` n'est jamais masqué par ce complément. Il reste un
-- intervalle (la somme connue d'au moins deux cellules masquées, au moins 5), comme O13 l'accepte.
--
-- quality_by_product, masquage secondaire (D18) : par genre, critère, origine et maillon, pour chaque colonne (audited et les quatre
-- comptes) où la cellule du produit est visible, la vue calcule les cellules d'équipe que quality_by_team masque. Si une telle colonne a
-- exactement une cellule d'équipe masquée, ou des cellules masquées dont la somme est sous 5, la cellule du produit moins la somme des
-- cellules d'équipe visibles la redonnerait : toute la ligne du produit est masquée (ses cinq comptes nuls). Un élément de plusieurs équipes rend cette différence inexacte : la règle la
-- traite comme exacte, par prudence.
--
-- quality_coverage_by_team : aucune différence entre deux colonnes visibles d'une même ligne ne redonne un nombre sous 5. `audited` n'est
-- jamais masqué par le complément (il est public par quality_by_team) ; collectés moins audités sous 5 masque `collected` ; audités moins
-- sans critère d'acceptation (en valeur absolue) ou collectés visibles moins sans critère d'acceptation sous 5 masque
-- `empty_acceptance_criteria`. Un élément sans équipe n'est jamais envoyé au moteur (Q2 (b)) : la ligne « (sans équipe) » le compte comme
-- collecté et non audité.
--
-- Versions de grille (D5, D15) : les trois vues portent en dernières colonnes core_grid_version et overlay_version de la paire courante,
-- jamais l'identifiant de la surcouche. Couverture sans aucun verdict d'audit : versions nulles.

SET LOCAL ROLE pmzilla_owner;

DROP VIEW quality.quality_by_team;
DROP VIEW quality.quality_coverage_by_team;
DROP VIEW quality.quality_by_product;

-- Masquage complémentaire des quatre comptes d'une ligne, dans l'ordre reçu. Une cellule est masquée (nulle) si elle est sous 5, ou si
-- une cellule de la ligne est sous 5 et que la somme des cellules plus petites qu'elle (dans l'ordre valeur, puis position) est sous 5.
CREATE FUNCTION quality.mask_verdicts(n bigint[]) RETURNS bigint[]
    LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    WITH cellules AS (
        SELECT u.v, u.i,
               coalesce(sum(u.v) OVER (ORDER BY u.v, u.i ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS avant,
               bool_or(u.v < 5) OVER () AS une_sous_le_seuil
        FROM unnest(n) WITH ORDINALITY AS u(v, i)
    )
    SELECT array_agg(CASE WHEN v < 5 OR (une_sous_le_seuil AND avant < 5) THEN NULL ELSE v END ORDER BY i) FROM cellules
$$;
REVOKE ALL ON FUNCTION quality.mask_verdicts(bigint[]) FROM PUBLIC;

-- Résultats par équipe, type d'élément et critère, à la paire courante, verdicts d'audit seulement, éléments encore dans la collecte.
-- Un élément de deux équipes compte une fois pour chacune. Aucune clé, aucun texte, aucune personne.
CREATE VIEW quality.quality_by_team AS
WITH courant AS (
    SELECT core_grid_id, core_grid_version, overlay_id, overlay_version
    FROM quality.assessments
    WHERE NOT sample
    ORDER BY analysed_at DESC, id DESC
    LIMIT 1
),
brut AS (
    SELECT coalesce(t.team, '(sans équipe)') AS team, i.kind AS item_kind, a.criterion_code, a.origin, a.link,
           count(*) AS audited,
           ARRAY[count(*) FILTER (WHERE a.verdict = 'met'), count(*) FILTER (WHERE a.verdict = 'not_met'),
                 count(*) FILTER (WHERE a.verdict = 'not_applicable'), count(*) FILTER (WHERE a.verdict = 'undetermined')] AS comptes
    FROM quality.assessments a
    JOIN courant c ON c.core_grid_id = a.core_grid_id AND c.core_grid_version = a.core_grid_version
                  AND c.overlay_id = a.overlay_id AND c.overlay_version = a.overlay_version
    JOIN quality.items i ON i.key = a.item_key AND i.out_of_collection_at IS NULL
    LEFT JOIN quality.item_teams t ON t.item_key = i.key
    WHERE NOT a.sample
    GROUP BY 1, 2, 3, 4, 5
)
SELECT b.team, b.item_kind, b.criterion_code, b.origin, b.link,
       quality.mask_count(b.audited) AS audited,
       m.v[1] AS met, m.v[2] AS not_met, m.v[3] AS not_applicable, m.v[4] AS undetermined,
       c.core_grid_version, c.overlay_version
FROM brut b
CROSS JOIN courant c
CROSS JOIN LATERAL (SELECT quality.mask_verdicts(b.comptes) AS v) m;

-- Couverture par équipe et type d'élément : éléments collectés, audités à la paire courante, sans critère d'acceptation, et le drapeau
-- d'équipe à un seul PO (jamais masqué : c'est un attribut de l'équipe, qui ne change aucun compte).
CREATE VIEW quality.quality_coverage_by_team AS
WITH courant AS (
    SELECT core_grid_id, core_grid_version, overlay_id, overlay_version
    FROM quality.assessments
    WHERE NOT sample
    ORDER BY analysed_at DESC, id DESC
    LIMIT 1
),
audites AS (
    SELECT DISTINCT a.item_key
    FROM quality.assessments a
    JOIN courant c ON c.core_grid_id = a.core_grid_id AND c.core_grid_version = a.core_grid_version
                  AND c.overlay_id = a.overlay_id AND c.overlay_version = a.overlay_version
    WHERE NOT a.sample
),
brut AS (
    SELECT coalesce(t.team, '(sans équipe)') AS team, i.kind AS item_kind,
           count(*) AS collected,
           count(*) FILTER (WHERE au.item_key IS NOT NULL) AS audited,
           count(*) FILTER (WHERE btrim(coalesce(ct.acceptance_criteria, '')) = '') AS vides,
           coalesce(bool_or(ta.single_po), false) AS single_po
    FROM quality.items i
    LEFT JOIN quality.item_teams t ON t.item_key = i.key
    LEFT JOIN quality.team_attributes ta ON ta.team = t.team
    LEFT JOIN quality.contents ct ON ct.item_key = i.key
    LEFT JOIN audites au ON au.item_key = i.key
    WHERE i.out_of_collection_at IS NULL
    GROUP BY 1, 2
),
complement AS (
    SELECT b.*, (b.collected >= 5 AND b.audited >= 5 AND b.collected - b.audited < 5) AS collectes_masques
    FROM brut b
)
SELECT k.team, k.item_kind,
       CASE WHEN k.collectes_masques THEN NULL ELSE quality.mask_count(k.collected) END AS collected,
       quality.mask_count(k.audited) AS audited,
       CASE WHEN k.vides >= 5 AND ((k.audited >= 5 AND abs(k.audited - k.vides) < 5)
                                   OR (k.collected >= 5 AND NOT k.collectes_masques AND k.collected - k.vides < 5)) THEN NULL
            ELSE quality.mask_count(k.vides) END AS empty_acceptance_criteria,
       k.single_po,
       c.core_grid_version, c.overlay_version
FROM complement k
LEFT JOIN courant c ON true;

-- Résultats du produit entier, toutes équipes réunies : chaque élément compte UNE fois, même avec plusieurs équipes. Aucune colonne d'équipe :
-- les lignes ne peuvent pas se regrouper par équipe. Un agrégat du produit, jamais une comparaison entre équipes (D8, O8).
CREATE VIEW quality.quality_by_product AS
WITH courant AS (
    SELECT core_grid_id, core_grid_version, overlay_id, overlay_version
    FROM quality.assessments
    WHERE NOT sample
    ORDER BY analysed_at DESC, id DESC
    LIMIT 1
),
retenus AS (
    SELECT a.item_key, i.kind AS item_kind, a.criterion_code, a.origin, a.link, a.verdict
    FROM quality.assessments a
    JOIN courant c ON c.core_grid_id = a.core_grid_id AND c.core_grid_version = a.core_grid_version
                  AND c.overlay_id = a.overlay_id AND c.overlay_version = a.overlay_version
    JOIN quality.items i ON i.key = a.item_key AND i.out_of_collection_at IS NULL
    WHERE NOT a.sample
),
equipes AS (       -- les comptes de quality_by_team, avant et après leur masquage
    SELECT r.item_kind, r.criterion_code, r.origin, r.link,
           ARRAY[count(*), count(*) FILTER (WHERE r.verdict = 'met'), count(*) FILTER (WHERE r.verdict = 'not_met'),
                 count(*) FILTER (WHERE r.verdict = 'not_applicable'), count(*) FILTER (WHERE r.verdict = 'undetermined')] AS bruts
    FROM retenus r
    LEFT JOIN quality.item_teams t ON t.item_key = r.item_key
    GROUP BY coalesce(t.team, '(sans équipe)'), r.item_kind, r.criterion_code, r.origin, r.link
),
cellules_masquees AS (
    SELECT e.item_kind, e.criterion_code, e.origin, e.link, k AS colonne, e.bruts[k] AS brut
    FROM equipes e
    CROSS JOIN LATERAL (SELECT quality.mask_count(e.bruts[1]) AS audited, quality.mask_verdicts(e.bruts[2:5]) AS v) m
    CROSS JOIN LATERAL generate_series(1, 5) AS k
    WHERE (k = 1 AND m.audited IS NULL) OR (k > 1 AND m.v[k - 1] IS NULL)
),
produit AS (       -- la ligne du produit avec son propre masquage (cellule sous 5, complément)
    SELECT g.item_kind, g.criterion_code, g.origin, g.link,
           quality.mask_count(g.audited) AS audited, quality.mask_verdicts(g.comptes) AS v
    FROM (SELECT item_kind, criterion_code, origin, link,
                 count(*) AS audited,
                 ARRAY[count(*) FILTER (WHERE verdict = 'met'), count(*) FILTER (WHERE verdict = 'not_met'),
                       count(*) FILTER (WHERE verdict = 'not_applicable'), count(*) FILTER (WHERE verdict = 'undetermined')] AS comptes
          FROM retenus
          GROUP BY 1, 2, 3, 4) g
),
secondaire AS (    -- lignes du produit dont une cellule visible, moins les cellules d'équipe visibles, redonnerait une cellule masquée (D18)
    SELECT DISTINCT p.item_kind, p.criterion_code, p.origin, p.link
    FROM (SELECT item_kind, criterion_code, origin, link, colonne, count(*) AS nombre, sum(brut) AS somme
          FROM cellules_masquees GROUP BY 1, 2, 3, 4, 5) parcolonne
    JOIN produit p ON p.item_kind = parcolonne.item_kind AND p.criterion_code = parcolonne.criterion_code
                  AND p.origin = parcolonne.origin AND p.link = parcolonne.link
    WHERE (parcolonne.nombre = 1 OR parcolonne.somme < 5)
      AND CASE WHEN parcolonne.colonne = 1 THEN p.audited IS NOT NULL ELSE p.v[parcolonne.colonne - 1] IS NOT NULL END
)
SELECT p.item_kind, p.criterion_code, p.origin, p.link,
       CASE WHEN s.item_kind IS NULL THEN p.audited END AS audited,
       CASE WHEN s.item_kind IS NULL THEN p.v[1] END AS met,
       CASE WHEN s.item_kind IS NULL THEN p.v[2] END AS not_met,
       CASE WHEN s.item_kind IS NULL THEN p.v[3] END AS not_applicable,
       CASE WHEN s.item_kind IS NULL THEN p.v[4] END AS undetermined,
       c.core_grid_version, c.overlay_version
FROM produit p
CROSS JOIN courant c
LEFT JOIN secondaire s ON s.item_kind = p.item_kind AND s.criterion_code = p.criterion_code
                      AND s.origin = p.origin AND s.link = p.link;

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle

-- Droits : comme en 0010. Les droits par défaut du schéma donnent SELECT sur les nouvelles vues au rôle de lecture-écriture et au rôle en
-- lecture seule (qui lisent déjà les tables) ; le rôle des vues reçoit SELECT sur les trois vues, rien d'autre. Une fonction d'une vue est
-- vérifiée pour l'appelant : les trois rôles qui lisent les vues peuvent masquer.
REVOKE ALL ON quality.quality_by_team, quality.quality_coverage_by_team, quality.quality_by_product FROM PUBLIC;
GRANT SELECT ON quality.quality_by_team, quality.quality_coverage_by_team, quality.quality_by_product TO pmzilla_quality, pmzilla_quality_ro;
GRANT EXECUTE ON FUNCTION quality.mask_verdicts(bigint[]) TO pmzilla_quality, pmzilla_quality_ro, pmzilla_quality_views;
GRANT SELECT ON quality.quality_by_team, quality.quality_coverage_by_team, quality.quality_by_product TO pmzilla_quality_views;
