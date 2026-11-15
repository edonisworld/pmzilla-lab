-- Schéma touché : flow (trois tables des définitions de flux, dans le référentiel des cycles).
-- Change flow-definitions-referential, conception D2, D5 et D6, décision de l'auteur R-20261029-09. Aucune donnée, aucun mot de passe, aucun rôle
-- créé ni modifié : les tables sont vides après la migration (les définitions réelles viennent du chargeur de la partie 2 du référentiel).
--
--   flow.ref_flow_statuses       le statut Jira rangé dans un segment (cinq segments calculés, todo, done), avec le drapeau d'engagement et celui de la
--                                file Ready ; un statut dans un seul segment (comparé sans casse ni espaces autour) ; todo et done sans drapeau
--   flow.ref_unplanned_types     le type de ticket non planifié et son genre (liste fermée : defect)
--   flow.ref_blocking_link_types le type de lien et son sens : blocks (le sens sortant se lit « bloque ») ou waits_for (« dépend de »)
--
-- Règles laissées au chargeur (flow_referential.valider), qu'une contrainte de contrôle ne peut pas voir : mêmes drapeaux pour tous les statuts d'un segment,
-- drapeau d'engagement et drapeau de la file Ready sur un seul segment. Non stocké : le point d'engagement lui-même, tout historique, tout compte, tout ticket.
--
-- Droits (D6) : ceux du référentiel des cycles. Le rôle d'import lit, insère et supprime (aucun UPDATE) ; le rôle en lecture seule lit ; le rôle des vues de
-- flow, celui de la qualité et PUBLIC n'ont aucun droit. Les droits par défaut du schéma flow (migration 0001) ne donnent à un nouvel objet que tous les droits
-- d'écriture au rôle d'import et la lecture au rôle en lecture seule, jamais rien au rôle des vues : ils sont retirés d'abord, puis les droits de D6 sont accordés.

SET LOCAL ROLE pmzilla_owner;

CREATE TABLE flow.ref_flow_statuses (
    status          text    PRIMARY KEY CHECK (btrim(status) <> ''),
    segment         text    NOT NULL CHECK (segment IN ('definition', 'ready', 'implementation', 'review_verification', 'acceptance', 'todo', 'done')),
    is_committed    boolean NOT NULL,
    is_ready_queue  boolean NOT NULL,
    CHECK (segment NOT IN ('todo', 'done') OR (NOT is_committed AND NOT is_ready_queue))
);
CREATE UNIQUE INDEX ref_flow_statuses_status_folded ON flow.ref_flow_statuses (lower(btrim(status)));

CREATE TABLE flow.ref_unplanned_types (
    type text PRIMARY KEY CHECK (btrim(type) <> ''),
    kind text NOT NULL CHECK (kind IN ('defect'))
);
CREATE UNIQUE INDEX ref_unplanned_types_type_folded ON flow.ref_unplanned_types (lower(btrim(type)));

CREATE TABLE flow.ref_blocking_link_types (
    type      text PRIMARY KEY CHECK (btrim(type) <> ''),
    direction text NOT NULL CHECK (direction IN ('blocks', 'waits_for'))
);
CREATE UNIQUE INDEX ref_blocking_link_types_type_folded ON flow.ref_blocking_link_types (lower(btrim(type)));

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle

-- Droits : retirés d'abord (les droits par défaut du schéma s'appliquent à toute nouvelle table), puis accordés.
REVOKE ALL ON flow.ref_flow_statuses, flow.ref_unplanned_types, flow.ref_blocking_link_types
    FROM PUBLIC, pmzilla_flow, pmzilla_flow_ro, pmzilla_flow_views, pmzilla_quality_views;
GRANT SELECT, INSERT, DELETE ON flow.ref_flow_statuses, flow.ref_unplanned_types, flow.ref_blocking_link_types
    TO pmzilla_flow;
GRANT SELECT ON flow.ref_flow_statuses, flow.ref_unplanned_types, flow.ref_blocking_link_types
    TO pmzilla_flow_ro;
