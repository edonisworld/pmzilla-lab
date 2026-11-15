-- Schéma touché : flow (deux colonnes de flow.issue_current_versions).
-- Change version-release-date (R-140, branche 2), décisions D4 et D5. Aucune donnée, aucun mot de passe, aucun rôle créé ni modifié.
--
--   flow.issue_current_versions.release_date   date nulle : la date de sortie de la version (attribut releaseDate de Jira), dérivée du dernier
--                                              instantané par flow_import.py. Nulle quand Jira n'en porte pas, et pour un instantané écrit avant
--                                              ce change (clé « release » absente de sa colonne current_versions).
--   flow.issue_current_versions.released       boolean nul : le drapeau « sortie » (attribut released de Jira), mêmes règles.
--
-- Aucune autre colonne de version n'est ajoutée (identifiant, description, archivage, dates de début : jamais lus). Droits inchangés : la table
-- reste écrite par le rôle d'import et lue par aucun autre rôle (migration 0017) ; les colonnes ajoutées suivent les droits de la table. La
-- suppression en cascade avec le ticket (purge de conservation) vaut pour les deux colonnes. Le registre des versions de la photo
-- (flow.version_photo_versions, migration 0019) a déjà ses colonnes release_date et released : l'outil de photo les remplit.

SET LOCAL ROLE pmzilla_owner;

ALTER TABLE flow.issue_current_versions
    ADD COLUMN release_date date,
    ADD COLUMN released     boolean;

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle
