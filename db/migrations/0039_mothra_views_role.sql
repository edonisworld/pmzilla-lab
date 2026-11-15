-- Schéma touché : flow (droits seulement : aucune table, aucune vue et aucune fonction créée ni modifiée) ; rôle du cluster pmzilla_mothra_views.
-- Audit de sécurité #629, constat A-80 ; décision de l'auteur R-20261107-26, décision 3 (a) : le rôle propre à Mothra se fait dans Kraken.
-- Jusqu'ici le serveur de Mothra lisait les vues sous pmzilla_flow_views, le rôle que partage tools/flow_views.py : ce rôle lit plus de vues que
-- Mothra n'en sert (v_teams, v_team_jira_ids, v_team_open_age, les vues de version et de livraison, etc.).
--
-- Rôle (NOLOGIN ici : aucun mot de passe dans une migration, jamais ; il se connecte après `uv run tools/db.py role-password pmzilla_mothra_views`) :
--   pmzilla_mothra_views   rôle de lecture des vues pour le serveur de Mothra, et pour lui seul :
--     SELECT sur les sept vues de contrats/vues.json (celles que Mothra sert) et sur une vue interne nommée, flow.v_team_weekly_resolved (constante
--     VUE_HEBDO de mothra/server/src/service.ts : le serveur la lit pour masquer la relation T3 de v_team_lead_time_throughput, sans jamais la servir),
--     et sur aucune autre ; aucun droit sur une table, sur quality, sur mothra, sur cases ni sur knowledge. v_team_weekly_resolved n'appelle que
--     flow.mask_count (migrations 0002 à 0030), déjà accordée ci-dessous ;
--     EXECUTE sur les trois fonctions de masquage que ces vues appellent : le droit EXECUTE d'une fonction appelée dans une vue est vérifié pour
--     l'utilisateur qui lit la vue, non pour son propriétaire (le contraire des tables), comme dit en 0022 et 0035. Ces fonctions ne lisent aucune table ;
--     aucun DDL, aucune écriture.
--   pmzilla_flow_views garde tous ses droits, pour tools/flow_views.py : rien n'est retiré ici.
--
-- Remplace : la connexion de Mothra sous pmzilla_flow_views (rôle partagé, A-80). Le serveur de Mothra, ses tests et les étapes de bout en bout se
-- connectent désormais sous pmzilla_mothra_views, avec son propre secret (PMZILLA_LAB_DB_PASSWORD_PMZILLA_MOTHRA_VIEWS).
-- Condition de retrait : permanent, tant que Mothra et tools/flow_views.py servent des listes de vues différentes. La liste des vues ci-dessous est
-- celle de contrats/vues.json (clé « views », genre « flow ») plus la vue interne v_team_weekly_resolved : la source des sept premières est ce
-- contrat, celle de la vue interne est VUE_HEBDO de mothra/server/src/service.ts ; la migration en est la copie, et un écart est détecté par
-- tests/db/test_chasse_grep_droits_vues.py (droits du rôle comparés au contrat plus la vue interne, sur la base jetable) et par
-- tests/db/test_matrice_droits.py (matrice des droits). Une vue ajoutée au contrat sans migration de droits fait échouer le premier ; une vue
-- accordée en trop, les deux.
-- Retour arrière : il n'y a pas de migration de retour. Annuler le commit de cette migration laisse le rôle créé et NOLOGIN tant que
-- `uv run tools/db.py role-password pmzilla_mothra_views` n'a pas été passé : il ne peut alors se connecter à rien.
-- Mot de passe : le même circuit que les autres rôles (tools/db.py, Trousseau macOS, service pmzilla-lab-db-pmzilla_mothra_views).

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pmzilla_mothra_views') THEN
        CREATE ROLE pmzilla_mothra_views NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO pmzilla_mothra_views', current_database());
END
$$;

GRANT USAGE ON SCHEMA flow TO pmzilla_mothra_views;

-- Les droits par défaut du schéma ne visent pas ce rôle ; PUBLIC n'a déjà aucun droit sur ces objets (migrations 0002, 0026, 0031) : le retrait est redit
-- pour que le fichier se lise seul.
REVOKE ALL ON flow.v_team_status, flow.v_team_lead_time_throughput, flow.v_task_without_team_share, flow.v_team_ready_queue,
              flow.v_team_blocked_share, flow.v_unplanned_share, flow.v_team_flow_inout, flow.v_team_weekly_resolved
    FROM PUBLIC;
REVOKE ALL ON FUNCTION flow.mask_count(bigint), flow.mask_count_zero(bigint), flow.fuite_serie(bigint[], boolean[]) FROM PUBLIC;

GRANT SELECT ON flow.v_team_status, flow.v_team_lead_time_throughput, flow.v_task_without_team_share, flow.v_team_ready_queue,
                flow.v_team_blocked_share, flow.v_unplanned_share, flow.v_team_flow_inout, flow.v_team_weekly_resolved
    TO pmzilla_mothra_views;
GRANT EXECUTE ON FUNCTION flow.mask_count(bigint), flow.mask_count_zero(bigint), flow.fuite_serie(bigint[], boolean[]) TO pmzilla_mothra_views;
