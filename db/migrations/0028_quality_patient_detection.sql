-- Schéma touché : quality (création : deux tables, aucune vue, aucune donnée) ; aucun rôle créé ni modifié.
-- Change patient-data-detection, tâche 3.1 (design D6) : le passage du détecteur de données de patient (`story_quality.py patient-scan`) et la
-- levée de la suspension de l'analyse (`story_quality.py patient-lift`) s'enregistrent dans ces deux tables.
--
--   quality.patient_scan_runs   un passage : instant, version du détecteur, empreinte de la liste facultative d'étiquettes (NULL : liste
--                               absente), éléments lus par genre, et un drapeau trouvé / non trouvé par catégorie P1 à P9. Aucun compte par
--                               catégorie, aucun texte, aucune clé de ticket, aucune équipe, aucune étiquette de la liste.
--   quality.patient_scan_lifts  une levée : instant, version du détecteur, empreinte de la liste, passage sur lequel elle s'appuie, catégories
--                               acceptées une à une par l'auteur (acceptation écrite, inscrite à son registre).
--
-- Droits : aucune vue ne lit ces tables ; seuls les rôles existants du schéma les touchent (pmzilla_quality : lecture et écriture ;
-- pmzilla_quality_ro : lecture). Le rôle des vues (pmzilla_quality_views) n'a aucun droit sur elles.
-- Elles ne figurent pas dans le dump partiel de quality : après une restauration, aucune levée n'existe et l'analyse reste suspendue,
-- ce qui est le sens sûr. Ces tables ne contiennent ni texte ni clé, et flow_retention.py ne les purge pas aujourd'hui ; les ajouter à la purge d'un an est une décision de l'auteur, à venir.

SET LOCAL ROLE pmzilla_owner;

CREATE TABLE quality.patient_scan_runs (
    id                     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_at                 timestamptz NOT NULL DEFAULT now(),
    detector_version       integer NOT NULL CHECK (detector_version >= 1),
    id_markers_fingerprint text,                             -- NULL : liste facultative absente
    items_read             jsonb NOT NULL,                   -- {"story": n, "epic": n, ...} : des effectifs de genre
    found                  jsonb NOT NULL                    -- {"P1": true, ..., "P9": false} : un drapeau par catégorie
);
CREATE INDEX patient_scan_runs_recent ON quality.patient_scan_runs (run_at DESC, id DESC);

CREATE TABLE quality.patient_scan_lifts (
    id                     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lifted_at              timestamptz NOT NULL DEFAULT now(),
    detector_version       integer NOT NULL CHECK (detector_version >= 1),
    id_markers_fingerprint text,                             -- NULL : liste facultative absente
    run_id                 bigint NOT NULL REFERENCES quality.patient_scan_runs (id),
    accepted_categories    text[] NOT NULL DEFAULT '{}'
);
CREATE INDEX patient_scan_lifts_recent ON quality.patient_scan_lifts (lifted_at DESC, id DESC);

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle

-- Droits : ceux des rôles existants du schéma seulement (les droits par défaut de 0010 les donnent déjà ; écrits ici pour qu'ils se lisent).
REVOKE ALL ON quality.patient_scan_runs, quality.patient_scan_lifts FROM PUBLIC, pmzilla_quality_views;
GRANT SELECT, INSERT, UPDATE, DELETE ON quality.patient_scan_runs, quality.patient_scan_lifts TO pmzilla_quality;
GRANT SELECT ON quality.patient_scan_runs, quality.patient_scan_lifts TO pmzilla_quality_ro;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA quality TO pmzilla_quality;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA quality TO pmzilla_quality_ro;
