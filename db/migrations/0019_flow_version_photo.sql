-- Schéma touché : flow (cinq tables d'agrégats de la photo de qualité par version).
-- Change version-quality-photo (R-140, branche 1), décisions D9, D10, D11, D13, D15 : le magasin des photos. Aucune donnée, aucun mot de
-- passe, aucun rôle créé ni modifié. Les vues qui lisent ces tables viennent dans la migration suivante.
--
--   flow.version_photo_versions  le registre des versions : un numéro opaque donné dans l'ordre de première rencontre, le nom (jamais lu
--                                par un rôle de vue), la date de sortie et le drapeau « sortie » laissés nuls (D3 : rien ne les remplit
--                                dans ce change, rien ne les estime).
--   flow.version_photo_runs      un passage de l'outil : instant, source « reconstructed » ou « live ».
--   flow.version_photo_weeks     une semaine photographiée (le lundi, semaine ISO en UTC) : son passage et sa couverture « partial » ou
--                                « complete ». La clé primaire est le lundi : une semaine n'a qu'une photo, vivante ou reconstruite (D13).
--   flow.version_photo_rows      les comptes de D6 par semaine, équipe et version (ligne de version : numéro de version non nul, cinq
--                                comptes) ou par semaine et équipe (ligne libre : numéro nul, quatre comptes). Jamais la somme des
--                                défauts trouvés et des défauts corrigés.
--   flow.version_photo_n         le registre de N : une ligne par adoption, en ajout seulement (D11).
--
-- Aucune clé de ticket, aucun titre, aucune personne, aucune clé étrangère vers les tickets : la purge d'un an n'y touche jamais (D9, D16).
-- Droits : le rôle d'import écrit ; personne d'autre ne lit directement, ni PUBLIC, ni le rôle en lecture seule, ni les rôles des vues
-- (qui lisent les deux vues de la migration suivante, exécutées avec les droits de leur propriétaire). Le rôle d'import peut insérer et lire
-- le registre de N, jamais le modifier ni le supprimer : N ne change jamais sans trace.

SET LOCAL ROLE pmzilla_owner;

CREATE TABLE flow.version_photo_versions (
    version_no   integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name         text NOT NULL UNIQUE,
    release_date date,
    released     boolean
);

CREATE TABLE flow.version_photo_runs (
    id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    taken_at timestamptz NOT NULL,
    source   text NOT NULL CHECK (source IN ('reconstructed', 'live'))
);

-- Aucun index d'unicité sur les passages (décision du 2026-10-23) : chaque relance de `reconstruct --replace` écrit un nouveau passage ; l'ancien
-- garde ses semaines non recalculables et son instant, et disparaît quand il n'a plus de semaine. L'unicité d'une photo par semaine est celle de
-- la clé primaire de flow.version_photo_weeks (D13).

CREATE TABLE flow.version_photo_weeks (
    week_start date PRIMARY KEY CHECK (extract(isodow FROM week_start) = 1),
    run_id     bigint NOT NULL REFERENCES flow.version_photo_runs (id) ON DELETE CASCADE,
    coverage   text NOT NULL CHECK (coverage IN ('partial', 'complete'))
);
CREATE INDEX version_photo_weeks_run ON flow.version_photo_weeks (run_id);

CREATE TABLE flow.version_photo_rows (
    week_start             date NOT NULL REFERENCES flow.version_photo_weeks (week_start) ON DELETE CASCADE,
    team                   text NOT NULL,
    version_no             integer REFERENCES flow.version_photo_versions (version_no),
    found                  bigint CHECK (found >= 0),
    found_open             bigint CHECK (found_open >= 0),
    corrected_at_week      bigint CHECK (corrected_at_week >= 0),
    corrected_now          bigint CHECK (corrected_now >= 0),
    reopened               bigint CHECK (reopened >= 0),
    defects_created        bigint CHECK (defects_created >= 0),
    defects_without_affects bigint CHECK (defects_without_affects >= 0),
    resolved_week          bigint CHECK (resolved_week >= 0),
    resolved_week_defects  bigint CHECK (resolved_week_defects >= 0),
    CHECK (
        (version_no IS NOT NULL
         AND found IS NOT NULL AND found_open IS NOT NULL AND corrected_at_week IS NOT NULL AND corrected_now IS NOT NULL
         AND reopened IS NOT NULL
         AND defects_created IS NULL AND defects_without_affects IS NULL AND resolved_week IS NULL AND resolved_week_defects IS NULL)
        OR
        (version_no IS NULL
         AND found IS NULL AND found_open IS NULL AND corrected_at_week IS NULL AND corrected_now IS NULL AND reopened IS NULL
         AND defects_created IS NOT NULL AND defects_without_affects IS NOT NULL AND resolved_week IS NOT NULL
         AND resolved_week_defects IS NOT NULL)
    )
);
CREATE UNIQUE INDEX version_photo_rows_unique ON flow.version_photo_rows (week_start, team, coalesce(version_no, 0));

CREATE TABLE flow.version_photo_n (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    weeks       integer NOT NULL CHECK (weeks > 0),
    adopted_on  date NOT NULL,
    session_tag text NOT NULL DEFAULT 'thresholds',
    taken_at    timestamptz NOT NULL DEFAULT now(),
    reason      text
);

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle

-- Droits : retirés d'abord (les droits par défaut du schéma s'appliquent à toute nouvelle table), puis accordés au rôle d'import seul.
REVOKE ALL ON flow.version_photo_versions, flow.version_photo_runs, flow.version_photo_weeks, flow.version_photo_rows,
              flow.version_photo_n
    FROM PUBLIC, pmzilla_flow, pmzilla_flow_ro, pmzilla_flow_views, pmzilla_quality_views;
GRANT SELECT, INSERT, UPDATE, DELETE ON flow.version_photo_versions, flow.version_photo_runs, flow.version_photo_weeks,
                                        flow.version_photo_rows TO pmzilla_flow;
GRANT SELECT, INSERT ON flow.version_photo_n TO pmzilla_flow;
-- Les séquences d'identité des trois tables à numéro automatique : le rôle d'import les garde (il insère), les deux rôles de lecture les perdent
-- (comme la migration de la couche brute).
REVOKE ALL ON SEQUENCE flow.version_photo_versions_version_no_seq, flow.version_photo_runs_id_seq, flow.version_photo_n_id_seq
    FROM pmzilla_flow_ro, pmzilla_flow_views;
-- Garde d'adopt-n (décision du 2026-10-23) : l'outil, sous le rôle d'import, lit les noms des migrations appliquées pour vérifier que celle de R-144
-- (masquage des croisements équipes x versions, nom de fichier contenant « masquage_somme ») est en place. Lecture seule, noms de fichiers seulement.
GRANT SELECT ON public.schema_migrations TO pmzilla_flow;
