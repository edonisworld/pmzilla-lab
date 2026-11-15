-- Schéma touché : flow (colonne current_versions de flow.raw_issue_snapshots, table flow.issue_current_versions).
-- Change flow-version-share (validation de l'organisation du 2026-10-23 : lecture par l'API de la fix version courante et de l'affects
-- version des tickets). Aucune donnée, aucun mot de passe, aucun rôle créé ni modifié.
--
--   flow.raw_issue_snapshots.current_versions   jsonb nul : {"fix": [noms], "affects": [noms]}, les versions courantes du ticket lues
--                                               par l'export. Nul pour un instantané écrit avant ce change (versions non suivies : la
--                                               dérivation ne compare rien et laisse les lignes vivantes telles quelles). La table
--                                               reste en ajout seulement (aucun droit UPDATE).
--   flow.issue_current_versions                 les versions courantes d'un ticket, dérivées du dernier instantané par flow_import.py :
--                                               une ligne par (ticket, genre fix ou affects, nom). Supprimée avec son ticket
--                                               (ON DELETE CASCADE), donc par la purge de conservation. Les noms de version ne sont lus
--                                               par aucune vue : seule flow.v_team_fix_version_share (migration suivante) les compte.
--
-- Droits : les droits par défaut du schéma s'appliquent à la table (rôle d'import : écriture) ; ils sont retirés à PUBLIC, au rôle en
-- lecture seule et aux deux rôles des vues, qui ne lisent donc pas les noms. Aucune autre table ni vue changée.

SET LOCAL ROLE pmzilla_owner;

ALTER TABLE flow.raw_issue_snapshots
    ADD COLUMN current_versions jsonb CHECK (current_versions IS NULL OR jsonb_typeof(current_versions) = 'object');

CREATE TABLE flow.issue_current_versions (
    issue_key text NOT NULL REFERENCES flow.issues (key) ON DELETE CASCADE,
    kind      text NOT NULL CHECK (kind IN ('fix', 'affects')),
    name      text NOT NULL,
    PRIMARY KEY (issue_key, kind, name)
);

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle

REVOKE ALL ON flow.issue_current_versions FROM PUBLIC, pmzilla_flow_ro, pmzilla_flow_views, pmzilla_quality_views;
