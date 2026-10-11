-- Schéma touché : flow (flow.issues).
-- Lot 6, correctif : un ticket « avec historique » n'est pas un ticket « avec au moins une transition ». Le cache de history_jira.py
-- a une entrée par ticket collecté, avec ou sans transition (un ticket qui n'a jamais changé d'état n'a aucune transition) ;
-- flux_jira.py compte la couverture de l'historique et repère les dormants d'après ces entrées. La base doit donc se souvenir des
-- tickets dont le cache a une entrée, sinon la lecture de la base les compterait tous (ou aucun des tickets sans transition).
-- Renseigné par tools/flow_import.py (option d'historique), jamais à la main. Aucune donnée dans cette migration.

SET LOCAL ROLE pmzilla_owner;

ALTER TABLE flow.issues ADD COLUMN has_history boolean NOT NULL DEFAULT false;

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle
