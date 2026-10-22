-- Schéma touché : quality (création : huit tables, trois vues agrégées, fonction de masquage) ; rôles du cluster pmzilla_quality, pmzilla_quality_ro, pmzilla_quality_views.
-- R-78 (change story-quality-audit, design D2, D8 et « Data model ») : le contenu des stories et des epics Jira (titre, description, critères
-- d'acceptation, après retrait des données de personne) et les verdicts de l'audit vivent dans ce schéma, et nulle part ailleurs.
-- Aucune donnée dans cette migration. Ce schéma n'est jamais sauvegardé (tools/db_backup.sh ne vise que knowledge, cases et flow) :
-- le texte se recollecte depuis Jira, les verdicts se recalculent, et aucune copie ne survit à la règle d'un an (tools/flow_retention.py).
--
-- Rôles (tous NOLOGIN ici : aucun mot de passe dans une migration, jamais) :
--   pmzilla_quality        lecture et écriture des tables (la collecte et l'analyse, lancées par l'utilisateur seul)
--   pmzilla_quality_ro     lecture seule des tables
--   pmzilla_quality_views  lecture des trois vues agrégées et de rien d'autre : pas de table, pas d'écriture, pas d'autre schéma ;
--                          son mot de passe est posé hors fichier (uv run tools/db.py role-password pmzilla_quality_views)
-- Aucun rôle d'un autre schéma ne lit quality, et aucun rôle de quality ne lit un autre schéma (aucun droit d'usage accordé).
--
-- Colonnes : du texte libre seulement dans contents (titre, description, critères d'acceptation) et coaching_feedback (retour borné).
-- Aucune colonne de personne : ni assignee, reporter, creator, author, comment, owner, person, user, account, e-mail ou nom. Seule
-- exception de nom, voulue : `single_po` des attributs d'équipe, un booléen d'équipe (D8), jamais le nom ni le compte d'un PO.
--
-- Version « courante » : la paire (socle, surcouche) du verdict d'audit (hors échantillon) le plus récent. Les verdicts d'une paire
-- antérieure cessent de compter dans les vues (O4) ; la couverture dit combien d'éléments sont audités à la paire courante.
-- Les verdicts d'échantillon (sample) et les retours de coaching ne sont lus par aucune vue.
-- Masquage : toute cellule de moins de 5 est nulle dans la vue même, comme les vues de flow.

-- Rôles du cluster : créés une fois, sans connexion.
DO $$
DECLARE
    nom text;
BEGIN
    FOREACH nom IN ARRAY ARRAY['pmzilla_quality', 'pmzilla_quality_ro', 'pmzilla_quality_views'] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = nom) THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION', nom);
        END IF;
    END LOOP;
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO pmzilla_quality, pmzilla_quality_ro, pmzilla_quality_views', current_database());
END
$$;

CREATE SCHEMA IF NOT EXISTS quality AUTHORIZATION pmzilla_owner;
REVOKE ALL ON SCHEMA quality FROM PUBLIC;
GRANT USAGE ON SCHEMA quality TO pmzilla_quality, pmzilla_quality_ro, pmzilla_quality_views;

-- Droits par défaut des objets à venir (le rôle des vues n'en reçoit aucun : ses droits sont explicites, sur les trois vues).
DO $$
DECLARE
    createur text;
BEGIN
    FOREACH createur IN ARRAY ARRAY['pmzilla_owner', current_user::text] LOOP
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA quality GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO pmzilla_quality', createur);
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA quality GRANT SELECT ON TABLES TO pmzilla_quality_ro', createur);
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA quality GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO pmzilla_quality', createur);
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA quality GRANT SELECT ON SEQUENCES TO pmzilla_quality_ro', createur);
    END LOOP;
END
$$;

SET LOCAL ROLE pmzilla_owner;

-- Un élément Jira : story ou epic. Ni texte, ni personne : le texte est dans contents.
CREATE TABLE quality.items (
    key                  text PRIMARY KEY,
    kind                 text NOT NULL CHECK (kind IN ('story', 'epic')),
    parent_key           text,
    status_category      text,
    created_at           timestamptz NOT NULL,
    updated_at           timestamptz NOT NULL,
    resolved_at          timestamptz,
    text_collected_at    timestamptz NOT NULL DEFAULT now(),      -- instant de la dernière collecte du texte : horloge de la règle d'un an (D9)
    out_of_collection_at timestamptz                              -- nul : l'élément est encore dans la collecte
);
CREATE INDEX items_out_of_collection ON quality.items (out_of_collection_at) WHERE out_of_collection_at IS NOT NULL;
CREATE INDEX items_text_collected ON quality.items (text_collected_at);

-- Les équipes d'un élément, dans l'ordre des colonnes de Jira, comme en flow.
CREATE TABLE quality.item_teams (
    item_key text NOT NULL REFERENCES quality.items (key) ON DELETE CASCADE,
    team     text NOT NULL,
    position smallint NOT NULL,
    PRIMARY KEY (item_key, team)
);
CREATE INDEX item_teams_team ON quality.item_teams (team);

-- Attributs d'équipe copiés du référentiel par la collecte. Aucune personne : ni nom, ni compte, ni titulaire de rôle.
CREATE TABLE quality.team_attributes (
    team      text PRIMARY KEY,
    single_po boolean NOT NULL DEFAULT false              -- déclaré par l'utilisateur : les stories de l'équipe sont écrites par un seul PO (D8)
);

-- Une relecture d'échantillon enregistrée par équipe (porte de relecture de D5). Ni texte, ni clé, ni personne.
CREATE TABLE quality.team_reviews (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    team        text NOT NULL,
    reviewed_at timestamptz NOT NULL DEFAULT now(),
    sample_size integer NOT NULL CHECK (sample_size > 0)
);
CREATE INDEX team_reviews_team ON quality.team_reviews (team);

-- Le texte nettoyé d'un élément (un seul par élément ; chaque collecte le remplace). Seuls les rôles de lecture-écriture et de lecture seule le lisent.
CREATE TABLE quality.contents (
    item_key            text PRIMARY KEY REFERENCES quality.items (key) ON DELETE CASCADE,
    title               text NOT NULL DEFAULT '',
    description         text NOT NULL DEFAULT '',
    acceptance_criteria text NOT NULL DEFAULT '',
    content_hash        text NOT NULL,
    replacements        integer NOT NULL DEFAULT 0 CHECK (replacements >= 0)
);

-- Les verdicts. Aucun texte libre : des codes, énumérés et contraints par la base.
-- Surcouche vide ('') quand il n'y a pas de surcouche : l'identifiant et la version sont vides ensemble, ou donnés ensemble.
CREATE TABLE quality.assessments (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_key          text NOT NULL REFERENCES quality.items (key) ON DELETE CASCADE,
    core_grid_id      text NOT NULL,
    core_grid_version text NOT NULL,
    overlay_id        text NOT NULL DEFAULT '',
    overlay_version   text NOT NULL DEFAULT '',
    criterion_code    text NOT NULL,
    origin            text NOT NULL CHECK (origin IN ('core', 'organisation_rule')),
    link              text NOT NULL CHECK (link IN ('ticket_template', 'discovery_workflow_step', 'definition_of_ready', 'refinement')),
    verdict           text NOT NULL CHECK (verdict IN ('met', 'not_met', 'not_applicable', 'undetermined')),
    sample            boolean NOT NULL,                    -- vrai : verdict d'une analyse d'échantillon, compté par aucune vue (D7) ; jamais de valeur par défaut
    analysed_at       timestamptz NOT NULL DEFAULT now(),
    CHECK ((overlay_id = '') = (overlay_version = ''))
);
CREATE UNIQUE INDEX assessments_unique ON quality.assessments
    (item_key, core_grid_id, core_grid_version, overlay_id, overlay_version, criterion_code, sample);
CREATE INDEX assessments_recent ON quality.assessments (analysed_at DESC, id DESC) WHERE NOT sample;

-- Une ligne par identifiant et version de surcouche : l'empreinte de son contenu, posée au premier envoi réel qui l'utilise (O3).
-- Aucun texte de la surcouche.
CREATE TABLE quality.overlay_versions (
    overlay_id    text NOT NULL,
    version       text NOT NULL,
    content_hash  text NOT NULL,
    first_used_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (overlay_id, version)
);

-- Les retours de coaching : texte borné. Aucune vue, aucun rapport, aucun tableau ne le lit.
CREATE TABLE quality.coaching_feedback (
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_key          text NOT NULL REFERENCES quality.items (key) ON DELETE CASCADE,
    core_grid_id      text NOT NULL,
    core_grid_version text NOT NULL,
    overlay_id        text NOT NULL DEFAULT '',
    overlay_version   text NOT NULL DEFAULT '',
    criterion_code    text NOT NULL,
    verdict           text NOT NULL CHECK (verdict IN ('met', 'not_met', 'not_applicable', 'undetermined')),
    feedback          text NOT NULL CHECK (char_length(feedback) <= 2000),
    analysed_at       timestamptz NOT NULL DEFAULT now(),
    CHECK ((overlay_id = '') = (overlay_version = ''))
);
CREATE INDEX coaching_feedback_item ON quality.coaching_feedback (item_key);

-- Masquage : une cellule de moins de 5 n'est pas rendue (comme flow.mask_count).
CREATE FUNCTION quality.mask_count(n bigint) RETURNS bigint
    LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$ SELECT CASE WHEN n < 5 THEN NULL ELSE n END $$;
REVOKE ALL ON FUNCTION quality.mask_count(bigint) FROM PUBLIC;

-- Résultats par équipe, type d'élément et critère, à la paire courante, verdicts d'audit seulement, éléments encore dans la collecte.
-- Un élément de deux équipes compte une fois pour chacune. Aucune clé, aucun texte, aucune personne.
CREATE VIEW quality.quality_by_team AS
WITH courant AS (
    SELECT core_grid_id, core_grid_version, overlay_id, overlay_version
    FROM quality.assessments
    WHERE NOT sample
    ORDER BY analysed_at DESC, id DESC
    LIMIT 1
)
SELECT coalesce(t.team, '(sans équipe)') AS team, i.kind AS item_kind, a.criterion_code, a.origin, a.link,
       quality.mask_count(count(*)) AS audited,
       quality.mask_count(count(*) FILTER (WHERE a.verdict = 'met')) AS met,
       quality.mask_count(count(*) FILTER (WHERE a.verdict = 'not_met')) AS not_met,
       quality.mask_count(count(*) FILTER (WHERE a.verdict = 'not_applicable')) AS not_applicable,
       quality.mask_count(count(*) FILTER (WHERE a.verdict = 'undetermined')) AS undetermined
FROM quality.assessments a
JOIN courant c ON c.core_grid_id = a.core_grid_id AND c.core_grid_version = a.core_grid_version
              AND c.overlay_id = a.overlay_id AND c.overlay_version = a.overlay_version
JOIN quality.items i ON i.key = a.item_key AND i.out_of_collection_at IS NULL
LEFT JOIN quality.item_teams t ON t.item_key = i.key
WHERE NOT a.sample
GROUP BY 1, 2, 3, 4, 5;

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
)
SELECT coalesce(t.team, '(sans équipe)') AS team, i.kind AS item_kind,
       quality.mask_count(count(*)) AS collected,
       quality.mask_count(count(*) FILTER (WHERE au.item_key IS NOT NULL)) AS audited,
       quality.mask_count(count(*) FILTER (WHERE btrim(coalesce(c.acceptance_criteria, '')) = '')) AS empty_acceptance_criteria,
       coalesce(bool_or(ta.single_po), false) AS single_po
FROM quality.items i
LEFT JOIN quality.item_teams t ON t.item_key = i.key
LEFT JOIN quality.team_attributes ta ON ta.team = t.team
LEFT JOIN quality.contents c ON c.item_key = i.key
LEFT JOIN audites au ON au.item_key = i.key
WHERE i.out_of_collection_at IS NULL
GROUP BY 1, 2;

-- Résultats du produit entier, toutes équipes réunies : chaque élément compte UNE fois, même avec plusieurs équipes. Aucune colonne d'équipe :
-- les lignes ne peuvent pas se regrouper par équipe. Un agrégat du produit, jamais une comparaison entre équipes (D8, O8).
CREATE VIEW quality.quality_by_product AS
WITH courant AS (
    SELECT core_grid_id, core_grid_version, overlay_id, overlay_version
    FROM quality.assessments
    WHERE NOT sample
    ORDER BY analysed_at DESC, id DESC
    LIMIT 1
)
SELECT i.kind AS item_kind, a.criterion_code, a.origin, a.link,
       quality.mask_count(count(*)) AS audited,
       quality.mask_count(count(*) FILTER (WHERE a.verdict = 'met')) AS met,
       quality.mask_count(count(*) FILTER (WHERE a.verdict = 'not_met')) AS not_met,
       quality.mask_count(count(*) FILTER (WHERE a.verdict = 'not_applicable')) AS not_applicable,
       quality.mask_count(count(*) FILTER (WHERE a.verdict = 'undetermined')) AS undetermined
FROM quality.assessments a
JOIN courant c ON c.core_grid_id = a.core_grid_id AND c.core_grid_version = a.core_grid_version
              AND c.overlay_id = a.overlay_id AND c.overlay_version = a.overlay_version
JOIN quality.items i ON i.key = a.item_key AND i.out_of_collection_at IS NULL
WHERE NOT a.sample
GROUP BY 1, 2, 3, 4;

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle

-- Droits explicites (les droits par défaut ci-dessus les donnent déjà : on les écrit pour qu'ils se lisent ici).
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA quality TO pmzilla_quality;
GRANT SELECT ON ALL TABLES IN SCHEMA quality TO pmzilla_quality_ro;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA quality TO pmzilla_quality;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA quality TO pmzilla_quality_ro;
-- Une fonction d'une vue est vérifiée pour l'appelant : les trois rôles qui lisent les vues peuvent masquer.
GRANT EXECUTE ON FUNCTION quality.mask_count(bigint) TO pmzilla_quality, pmzilla_quality_ro, pmzilla_quality_views;
-- Le rôle des vues : SELECT sur les trois vues, rien d'autre. Aucun droit sur les tables ni sur les séquences.
GRANT SELECT ON quality.quality_by_team, quality.quality_coverage_by_team, quality.quality_by_product TO pmzilla_quality_views;
