-- Schéma touché : knowledge, cases, flow (création), public (extensions) ; rôles du cluster.
-- Lot 1 : socle de la base. Aucune table métier ici. Exécuté par l'exécuteur de tools/db.py avec le
-- superutilisateur `postgres`, dans une transaction (CREATE EXTENSION, CREATE ROLE et GRANT sont transactionnels).
--
-- Rôles (tous NOLOGIN pour ce lot : aucun mot de passe dans une migration, jamais ; la connexion par rôle,
-- LOGIN et mot de passe posé hors fichier, viendra avec le premier consommateur) :
--   pmzilla_owner                     propriétaire des schémas et des objets ; seul à pouvoir changer la structure
--   pmzilla_<schéma>                  lecture et écriture dans son schéma, pas de DDL
--   pmzilla_<schéma>_ro               lecture seule dans son schéma
-- Les futures migrations commencent par SET LOCAL ROLE pmzilla_owner pour que leurs objets appartiennent au propriétaire.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_search;

DO $$
DECLARE
    nom text;
BEGIN
    FOREACH nom IN ARRAY ARRAY[
        'pmzilla_owner',
        'pmzilla_knowledge', 'pmzilla_knowledge_ro',
        'pmzilla_cases', 'pmzilla_cases_ro',
        'pmzilla_flow', 'pmzilla_flow_ro'
    ] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = nom) THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION', nom);
        END IF;
    END LOOP;
END
$$;

-- Personne d'autre que le propriétaire ne crée dans public ; les rôles d'accès n'ont pas de droit sur la base elle-même.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
DO $$
BEGIN
    EXECUTE format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database());
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO pmzilla_owner, pmzilla_knowledge, pmzilla_knowledge_ro, '
                   'pmzilla_cases, pmzilla_cases_ro, pmzilla_flow, pmzilla_flow_ro', current_database());
END
$$;

DO $$
DECLARE
    schema_nom text;
    createur text;
BEGIN
    FOREACH schema_nom IN ARRAY ARRAY['knowledge', 'cases', 'flow'] LOOP
        EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I AUTHORIZATION pmzilla_owner', schema_nom);
        EXECUTE format('REVOKE ALL ON SCHEMA %I FROM PUBLIC', schema_nom);
        EXECUTE format('GRANT USAGE ON SCHEMA %I TO %I, %I', schema_nom, 'pmzilla_' || schema_nom, 'pmzilla_' || schema_nom || '_ro');

        -- Tables et séquences existantes (aucune à ce lot) puis futures, pour le propriétaire et pour le rôle qui exécute les migrations.
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO %I', schema_nom, 'pmzilla_' || schema_nom);
        EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO %I', schema_nom, 'pmzilla_' || schema_nom || '_ro');
        EXECUTE format('GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA %I TO %I', schema_nom, 'pmzilla_' || schema_nom);
        EXECUTE format('GRANT SELECT ON ALL SEQUENCES IN SCHEMA %I TO %I', schema_nom, 'pmzilla_' || schema_nom || '_ro');

        FOREACH createur IN ARRAY ARRAY['pmzilla_owner', current_user::text] LOOP
            EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I',
                           createur, schema_nom, 'pmzilla_' || schema_nom);
            EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT SELECT ON TABLES TO %I',
                           createur, schema_nom, 'pmzilla_' || schema_nom || '_ro');
            EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO %I',
                           createur, schema_nom, 'pmzilla_' || schema_nom);
            EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA %I GRANT SELECT ON SEQUENCES TO %I',
                           createur, schema_nom, 'pmzilla_' || schema_nom || '_ro');
        END LOOP;
    END LOOP;
END
$$;
