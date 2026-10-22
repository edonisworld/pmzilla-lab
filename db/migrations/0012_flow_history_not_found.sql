-- Schéma touché : flow (flow.issues, flow.raw_runs).
-- Change database-only (D15), bug du 404 permanent de la collecte de l'historique : un ticket supprimé ou sans accès répond 404 à chaque
-- collecte, donc aucun passage « history » n'était enregistré et la fenêtre des tickets modifiés ne bougeait jamais. La collecte compte
-- désormais à part les tickets introuvables (404) et les erreurs passagères (429, 5xx, délai, réseau) :
--
--   flow.issues.history_not_found   nombre de collections consécutives où Jira a répondu 404 pour le ticket ; remis à zéro dès qu'une
--                                   réponse normale arrive ; inchangé par une erreur passagère.
--   flow.issues.history_gone_at     instant de la collection où le ticket a atteint la limite (réglage history_not_found_limit) et a été
--                                   marqué disparu ; nul tant que le ticket est interrogé ; effacé par une réponse normale. Un ticket
--                                   disparu n'est plus interrogé, sauf avec --refresh.
--   flow.raw_runs.errors            nombre d'erreurs passagères d'un passage « history » ; nul pour les passages d'export et d'amorçage.
--                                   La dernière collecte réussie est le dernier passage « history » dont ce nombre est zéro.
--   flow.raw_runs.not_found         nombre de réponses 404 d'un passage « history » ; nul pour les passages d'export et d'amorçage.
--
-- Aucune donnée, aucune mise à jour de lignes existantes (valeurs par défaut), aucun mot de passe, aucun rôle créé ni modifié, aucun droit
-- changé : le rôle d'import écrit déjà flow.issues (mise à jour) et insère dans flow.raw_runs (couche brute en ajout seulement : aucune
-- mise à jour de cette table), le rôle en lecture seule lit déjà flow.issues, le rôle des vues n'a aucun droit sur ces tables et aucune
-- vue ne lit ces colonnes. Aucun nom de colonne ne contient « label », « key » ou « version ».

SET LOCAL ROLE pmzilla_owner;

ALTER TABLE flow.issues
    ADD COLUMN history_not_found integer NOT NULL DEFAULT 0 CONSTRAINT issues_history_not_found_positive CHECK (history_not_found >= 0),
    ADD COLUMN history_gone_at timestamptz;

ALTER TABLE flow.raw_runs
    ADD COLUMN errors integer CONSTRAINT raw_runs_errors_positive CHECK (errors >= 0),
    ADD COLUMN not_found integer CONSTRAINT raw_runs_not_found_positive CHECK (not_found >= 0);

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle
