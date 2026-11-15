-- Schéma touché : mothra (création : quatre tables, aucune donnée) ; rôle du cluster pmzilla_mothra.
-- Tâche 16.1 du change mothra-slices (design D17, D21, D26, D31 ; ADR 0006 : stockage propre de Mothra) : les fiches d'argument, leurs
-- versions publiées figées, l'historique daté des seuils et les utilisateurs de l'application vivent dans ce schéma, et nulle part ailleurs.
-- Aucune donnée dans cette migration : aucun utilisateur réel n'est écrit avant la confirmation de la personne en charge du RGPD (D26).
--
-- Rôle (NOLOGIN ici : aucun mot de passe dans une migration, jamais ; il se connecte après `uv run tools/db.py role-password pmzilla_mothra`) :
--   pmzilla_mothra  seul rôle du schéma (exception écrite à la règle « un rôle d'écriture et un rôle de lecture seule par schéma », ADR 0006) :
--     published_versions et threshold_history   SELECT et INSERT seulement : ni UPDATE ni DELETE, ces lignes sont figées ;
--     sheets                                    SELECT, INSERT et UPDATE ;
--     users                                     SELECT, INSERT, UPDATE et DELETE (purge des utilisateurs inactifs par un outil que l'auteur lance, D26) ;
--     aucun droit sur flow, quality, cases ni knowledge, aucun DDL (le propriétaire reste pmzilla_owner).
-- Aucun autre rôle ne reçoit de droit sur mothra : ni les vues de flow, ni les vues de quality, ni le rôle d'import de flow.
--
-- Colonnes : ni secret, ni nom de personne, ni adresse e-mail, ni clé de ticket, ni titre, ni description. Un utilisateur est un identifiant
-- pseudonyme et un rôle applicatif (author ou reviewer). L'effet et la cause d'une fiche sont les seuls textes libres, chacun avec sa langue
-- (fr ou en) ; ils sont vérifiés à l'écriture (D20). L'historique des seuils n'a pas de champ de participants (D21).
-- Les tables figées ne portent aucune clé étrangère vers users : la purge des utilisateurs (DELETE sur users) ne doit ni échouer ni toucher
-- une ligne figée. L'auteur y est un identifiant pseudonyme copié, jamais un renvoi.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pmzilla_mothra') THEN
        CREATE ROLE pmzilla_mothra NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO pmzilla_mothra', current_database());
END
$$;

CREATE SCHEMA IF NOT EXISTS mothra AUTHORIZATION pmzilla_owner;
REVOKE ALL ON SCHEMA mothra FROM PUBLIC;
GRANT USAGE ON SCHEMA mothra TO pmzilla_mothra;

SET LOCAL ROLE pmzilla_owner;

-- Utilisateurs : identifiant pseudonyme, rôle applicatif, dates d'activité (rétention : D26).
CREATE TABLE mothra.users (
    id              text PRIMARY KEY CHECK (id ~ '^[a-z0-9][a-z0-9_-]{0,63}$'),
    role            text NOT NULL CHECK (role IN ('author', 'reviewer')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    last_active_at  timestamptz NOT NULL DEFAULT now()
);

-- Fiches d'argument (brouillon, relue, publiée) : effet et cause avec leur langue.
CREATE TABLE mothra.sheets (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    kind            text NOT NULL CHECK (kind ~ '^[a-z0-9_-]{1,64}$'),
    state           text NOT NULL DEFAULT 'draft' CHECK (state IN ('draft', 'reviewed', 'published')),
    effect_text     text CHECK (effect_text IS NULL OR char_length(effect_text) <= 500),
    effect_lang     text CHECK (effect_lang IS NULL OR effect_lang IN ('fr', 'en')),
    cause_text      text CHECK (cause_text IS NULL OR char_length(cause_text) <= 500),
    cause_lang      text CHECK (cause_lang IS NULL OR cause_lang IN ('fr', 'en')),
    created_by      text NOT NULL,
    reviewed_by     text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CHECK ((effect_text IS NULL) = (effect_lang IS NULL)),
    CHECK ((cause_text IS NULL) = (cause_lang IS NULL))
);

-- Versions publiées : figées (insertion seulement), agrégats uniquement, empreinte de la version.
CREATE TABLE mothra.published_versions (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sheet_id        bigint NOT NULL REFERENCES mothra.sheets (id),
    version         integer NOT NULL CHECK (version >= 1),
    content         jsonb NOT NULL,
    fingerprint     text NOT NULL CHECK (fingerprint ~ '^[0-9a-f]{64}$'),
    published_by    text NOT NULL,
    published_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (sheet_id, version)
);

-- Historique des seuils : valeur, date et auteur seulement (insertion seulement).
CREATE TABLE mothra.threshold_history (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    threshold_code  text NOT NULL CHECK (threshold_code ~ '^[a-z0-9_.-]{1,64}$'),
    value           numeric NOT NULL,
    set_on          date NOT NULL,
    set_by          text NOT NULL
);

CREATE INDEX threshold_history_code_date ON mothra.threshold_history (threshold_code, set_on);

RESET ROLE;

GRANT SELECT, INSERT ON mothra.published_versions, mothra.threshold_history TO pmzilla_mothra;
GRANT SELECT, INSERT, UPDATE ON mothra.sheets TO pmzilla_mothra;
GRANT SELECT, INSERT, UPDATE, DELETE ON mothra.users TO pmzilla_mothra;
