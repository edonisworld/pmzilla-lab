-- Schéma touché : flow (flow.teams).
-- Change database-only (R-69), complément « colonne du type d'équipe » (team-mapping Q5 (b)) : le type d'une équipe, écrit par l'export
-- dans sa transaction de la couche brute à partir du catalogue ou du référentiel, jamais deviné. Une colonne facultative, contrainte aux
-- quatre noms de sous-type d'équipe ; nulle tant que l'export n'a pas écrit de type (une équipe d'une base existante garde donc un type
-- nul après la migration). Aucune donnée, aucun mot de passe, aucun rôle créé ni modifié, aucun droit changé : le rôle d'import écrit
-- flow.teams déjà (droits par défaut du lot 1), le rôle en lecture seule lit toutes ses colonnes, le rôle des vues n'a aucun droit sur
-- cette table et ne lirait le type qu'au travers d'une vue (aucune vue ni rapport par type n'est ajouté ici).
-- Le nom de la colonne ne contient ni « label » ni « key » : les règles de database-roles-views sur ces mots tiennent.

SET LOCAL ROLE pmzilla_owner;

ALTER TABLE flow.teams
    ADD COLUMN team_type text
    CONSTRAINT teams_team_type_known CHECK (team_type IN ('Development Team', 'Verification Team', 'Product Management Team', 'Other Team'));

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle
