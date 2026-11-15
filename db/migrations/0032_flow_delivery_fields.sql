-- Schéma touché : flow (colonne delivery de flow.raw_issue_snapshots ; tables des champs de livraison, des périodes de sprint et de version
-- d'actif, des références de version et des instantanés de version). Aucune donnée, aucun mot de passe, aucun rôle créé ni modifié.
-- Change jira-delivery-fields (R-20261102-14 à -36), design D3.
--
--   flow.raw_issue_snapshots.delivery   jsonb nul : la partie « delivery » de l'instantané (sprints en identifiant, état et dates ; identifiants
--                                       d'objet d'actifs par genre ; options avec leur valeur filtrée ; indicateurs ; champs des défauts). Nulle
--                                       quand le ticket n'a aucun champ de livraison (son empreinte est alors celle d'avant). La table reste en
--                                       ajout seulement (aucun droit UPDATE).
--   flow.issue_delivery_fields          une ligne par ticket : champs à valeur unique, rang de portefeuille et trois indicateurs oui/non.
--   flow.sprints                        un sprint : identifiant Jira, état, dates. Jamais son nom, son but ni son tableau (Q295).
--   flow.issue_current_sprints          sprints courants d'un ticket.
--   flow.issue_current_asset_versions   versions courantes d'un ticket par genre (cible, livrée, deux champs d'épic, et pour les seuls défauts
--                                       détectée et touchée) : l'identifiant d'objet seul.
--   flow.issue_delivery_options         options des champs à valeurs multiples : identifiant d'option et valeur après le filtre des noms sensibles.
--   flow.issue_defect_fields            une ligne par défaut : phase de détection, détecté par, base installée (identifiant, valeur filtrée).
--   flow.issue_sprint_periods           périodes de sprint d'un ticket, dérivées de l'historique à la collecte.
--   flow.issue_asset_version_periods    périodes des versions d'actifs d'un ticket (genre, objet).
--   flow.release_versions               une version : identifiant d'objet (clé), numéro opaque attribué par la base à la première vue, nom court,
--                                       état, catégorie, Started, Released (date de mise à disposition), dernière vue. Les tickets de version
--                                       n'entrent jamais dans flow.issues ; leur clé et leur résumé ne sont jamais stockés.
--   flow.raw_version_snapshots          instantanés des versions de la couche brute, en ajout seulement, écrits quand le contenu change.
--
-- Les tables d'un ticket partent avec lui (ON DELETE CASCADE), donc par la purge de conservation. Droits : les droits par défaut du schéma
-- s'appliquent aux tables courantes (rôle d'import : écriture) ; ils sont retirés à PUBLIC, au rôle en lecture seule et aux deux rôles des vues,
-- qui ne lisent donc aucune de ces tables : la vue de la migration suivante est leur seul accès. La table brute des versions est en ajout seulement
-- pour le rôle d'import (aucun droit UPDATE), comme les autres tables de la couche brute.

SET LOCAL ROLE pmzilla_owner;

ALTER TABLE flow.raw_issue_snapshots
    ADD COLUMN delivery jsonb CHECK (delivery IS NULL OR jsonb_typeof(delivery) = 'object');

CREATE TABLE flow.issue_delivery_fields (
    issue_key             text PRIMARY KEY REFERENCES flow.issues (key) ON DELETE CASCADE,
    release_target        text,
    verification_required text,
    product_safety        text,
    isp                   text,
    code_review_status    text,
    portfolio_rank        numeric,
    customer_commitment   boolean NOT NULL DEFAULT false,
    source_commitment     boolean NOT NULL DEFAULT false,
    strategic_objective   boolean NOT NULL DEFAULT false
);

CREATE TABLE flow.sprints (
    sprint_id     text PRIMARY KEY,
    state         text,
    start_date    timestamptz,
    end_date      timestamptz,
    complete_date timestamptz
);

CREATE TABLE flow.issue_current_sprints (
    issue_key text NOT NULL REFERENCES flow.issues (key) ON DELETE CASCADE,
    sprint_id text NOT NULL REFERENCES flow.sprints (sprint_id),
    PRIMARY KEY (issue_key, sprint_id)
);

CREATE TABLE flow.issue_current_asset_versions (
    issue_key text NOT NULL REFERENCES flow.issues (key) ON DELETE CASCADE,
    kind      text NOT NULL CHECK (kind IN ('target', 'resolution', 'epic_a', 'epic_b', 'detected', 'affected')),
    object_id text NOT NULL,
    PRIMARY KEY (issue_key, kind, object_id)
);
CREATE INDEX issue_current_asset_versions_object ON flow.issue_current_asset_versions (object_id);

CREATE TABLE flow.issue_delivery_options (
    issue_key text NOT NULL REFERENCES flow.issues (key) ON DELETE CASCADE,
    field     text NOT NULL CHECK (field IN ('category_nature', 'workflow_option')),
    position  integer NOT NULL CHECK (position >= 1),
    option_id text,
    value     text NOT NULL,
    PRIMARY KEY (issue_key, field, position)
);

CREATE TABLE flow.issue_defect_fields (
    issue_key            text PRIMARY KEY REFERENCES flow.issues (key) ON DELETE CASCADE,
    detection_phase_id   text,
    detection_phase      text,
    detected_by_id       text,
    detected_by          text,
    installed_base_id    text,
    installed_base       text
);

CREATE TABLE flow.issue_sprint_periods (
    issue_key  text NOT NULL REFERENCES flow.issues (key) ON DELETE CASCADE,
    sprint_id  text NOT NULL,
    added_at   timestamptz NOT NULL,
    removed_at timestamptz,
    PRIMARY KEY (issue_key, sprint_id, added_at)
);

CREATE TABLE flow.issue_asset_version_periods (
    issue_key  text NOT NULL REFERENCES flow.issues (key) ON DELETE CASCADE,
    kind       text NOT NULL CHECK (kind IN ('target', 'resolution', 'epic_a', 'epic_b')),
    object_id  text NOT NULL,
    added_at   timestamptz NOT NULL,
    removed_at timestamptz,
    PRIMARY KEY (issue_key, kind, object_id, added_at)
);
CREATE INDEX issue_asset_version_periods_object ON flow.issue_asset_version_periods (object_id);

CREATE TABLE flow.release_versions (
    object_id       text PRIMARY KEY,
    number          bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
    short_name      text,
    status          text,
    status_category text,
    started         date,
    released        date,
    last_seen       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE flow.raw_version_snapshots (
    run_id       bigint NOT NULL REFERENCES flow.raw_runs (id),
    object_id    text NOT NULL,
    content      jsonb NOT NULL CHECK (jsonb_typeof(content) = 'object'),
    content_hash text NOT NULL,
    PRIMARY KEY (object_id, run_id)
);

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle

REVOKE ALL ON flow.issue_delivery_fields, flow.sprints, flow.issue_current_sprints, flow.issue_current_asset_versions,
              flow.issue_delivery_options, flow.issue_defect_fields, flow.issue_sprint_periods, flow.issue_asset_version_periods,
              flow.release_versions
    FROM PUBLIC, pmzilla_flow_ro, pmzilla_flow_views, pmzilla_quality_views;
REVOKE ALL ON SEQUENCE flow.release_versions_number_seq FROM PUBLIC, pmzilla_flow_ro, pmzilla_flow_views, pmzilla_quality_views;

REVOKE ALL ON flow.raw_version_snapshots FROM PUBLIC, pmzilla_flow, pmzilla_flow_ro, pmzilla_flow_views, pmzilla_quality_views;
GRANT SELECT, INSERT, DELETE ON flow.raw_version_snapshots TO pmzilla_flow;
