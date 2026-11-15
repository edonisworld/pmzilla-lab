-- Schéma touché : flow (cinq tables du référentiel des cycles).
-- Change cycle-referential-schema (partie 1), conception D1 à D4, décision de l'auteur R-20261028-91 (questions 1 à 5). Aucune donnée, aucun mot
-- de passe, aucun rôle créé ni modifié. Les vues qui lisent ces tables viennent avec la page de préparation d'un cycle de Mothra.
--
--   flow.ref_cycles       les cycles neutres : clé (forme AAAA-Cn, n de 1 à 6, ou AAAA-EOY), date de début, date de fin (jamais avant le début)
--   flow.ref_labels       les étiquettes déclarées et leur rôle (liste fermée) ; la clé de cycle seulement pour le rôle « cycle » ; le sens seulement
--                         et toujours pour le rôle « confirmation » ; au plus une étiquette de domaine pilote et une Ready. Seconde et dernière table
--                         où un texte d'étiquette peut être écrit (décision R-20261028-91) : sans colonne de ticket ni clé étrangère vers les tickets,
--                         et le texte n'y entre que par flow_referential.ecrire, qui refuse toute étiquette non déclarée
--   flow.ref_dw_columns   les colonnes du Discovery Workflow : position unique et positive, au plus une colonne de départ et une Ready, une colonne
--                         Ready jamais active (« exactement une colonne de départ » est la règle du chargeur ; la base garantit « au plus une »)
--   flow.ref_dw_statuses  le statut Jira rangé dans une colonne (un statut dans une seule colonne)
--   flow.ref_state        une ligne au plus : date de validation de la correspondance (nulle tant qu'elle n'est pas validée) et instant du chargement
--
-- Non stocké : l'état d'un cycle (calculé par les vues), tout compte, tout historique du référentiel (un chargement le remplace en entier), le nom
-- d'une version. Règles laissées aux lecteurs des réglages de flux et au chargeur : préfixes des étiquettes, contiguïté des cycles, avertissement des
-- huit semaines, nombre exact d'étiquettes de fusion et de domaine, drapeau de version de base.
--
-- Droits (D4) : le rôle d'import lit, insère et supprime (un chargement supprime puis insère dans une transaction ; aucun UPDATE, une ligne n'est jamais
-- changée sur place) ; le rôle en lecture seule lit ; le rôle des vues de flow, le rôle des vues de la qualité et PUBLIC n'ont aucun droit (les vues de
-- Mothra liront ces tables avec les droits de leur propriétaire) ; les rôles des autres schémas n'ont pas même l'usage du schéma flow.
-- Les droits par défaut du schéma flow (migration 0001) ne donnent à un nouvel objet que tous les droits d'écriture au rôle d'import et la lecture au rôle
-- en lecture seule : ils sont retirés d'abord, puis les droits de D4 sont accordés.

SET LOCAL ROLE pmzilla_owner;

CREATE TABLE flow.ref_cycles (
    cycle_key  text PRIMARY KEY CHECK (cycle_key ~ '^[0-9]{4}-(C[1-6]|EOY)$'),
    start_date date NOT NULL,
    end_date   date NOT NULL,
    CHECK (end_date >= start_date)
);

CREATE TABLE flow.ref_labels (
    label     text PRIMARY KEY,
    role      text NOT NULL CHECK (role IN ('up_merge', 'cycle', 'epic_review', 'pilot_domain', 'ready', 'confirmation')),
    cycle_key text REFERENCES flow.ref_cycles (cycle_key),
    meaning   text,
    CHECK (cycle_key IS NULL OR role = 'cycle'),
    CHECK ((role = 'confirmation' AND meaning IS NOT NULL AND meaning IN ('taken_in', 'not_taken_in'))
           OR (role <> 'confirmation' AND meaning IS NULL))
);
CREATE UNIQUE INDEX ref_labels_one_pilot_domain ON flow.ref_labels (role) WHERE role = 'pilot_domain';
CREATE UNIQUE INDEX ref_labels_one_ready ON flow.ref_labels (role) WHERE role = 'ready';

CREATE TABLE flow.ref_dw_columns (
    name             text PRIMARY KEY,
    position         integer NOT NULL UNIQUE CHECK (position > 0),
    is_start         boolean NOT NULL,
    is_review_passed boolean NOT NULL,
    is_ready         boolean NOT NULL,
    is_active        boolean NOT NULL,
    CHECK (NOT (is_ready AND is_active))
);
CREATE UNIQUE INDEX ref_dw_columns_one_start ON flow.ref_dw_columns (is_start) WHERE is_start;
CREATE UNIQUE INDEX ref_dw_columns_one_ready ON flow.ref_dw_columns (is_ready) WHERE is_ready;

CREATE TABLE flow.ref_dw_statuses (
    status      text PRIMARY KEY,
    column_name text NOT NULL REFERENCES flow.ref_dw_columns (name)
);

CREATE TABLE flow.ref_state (
    id                  smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    mapping_validated_on date,
    loaded_at           timestamptz NOT NULL DEFAULT now()
);

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle

-- Droits : retirés d'abord (les droits par défaut du schéma s'appliquent à toute nouvelle table), puis accordés.
REVOKE ALL ON flow.ref_cycles, flow.ref_labels, flow.ref_dw_columns, flow.ref_dw_statuses, flow.ref_state
    FROM PUBLIC, pmzilla_flow, pmzilla_flow_ro, pmzilla_flow_views, pmzilla_quality_views;
GRANT SELECT, INSERT, DELETE ON flow.ref_cycles, flow.ref_labels, flow.ref_dw_columns, flow.ref_dw_statuses, flow.ref_state
    TO pmzilla_flow;
GRANT SELECT ON flow.ref_cycles, flow.ref_labels, flow.ref_dw_columns, flow.ref_dw_statuses, flow.ref_state
    TO pmzilla_flow_ro;
