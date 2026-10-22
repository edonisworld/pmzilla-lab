-- Schéma touché : flow (vues flow.v_teams et flow.v_team_jira_ids).
-- Change team-names-readable (conception D2 et D3, décision e) : la décision de l'organisation du 2026-10-19 permet de lire les noms
-- d'équipe tels que stockés. Deux vues agrégées pour le rôle des vues, aucune table ouverte.
--
-- flow.v_teams : une ligne par ligne de flow.teams (l'équipe inconnue y comprise, telle que stockée). Colonnes : team (nom stocké),
-- team_type (type stocké, l'un des quatre noms de sous-type, nul tant que l'export n'en a pas écrit ; jamais déduit), tickets (nombre
-- masqué sous 5, par flow.mask_count, des tickets sans instant de sortie de l'export qui portent l'équipe dans flow.issue_teams ; une
-- équipe sans ticket a donc un nombre nul). Aucun regroupement par type.
--
-- flow.v_team_jira_ids : à partir du dernier instantané de chaque ticket (DISTINCT ON la clé, run_id décroissant) dont le ticket est dans
-- flow.issues sans instant de sortie de l'export, une ligne par paire (nom d'équipe, identifiant d'équipe Jira) de son JSON `teams` dont
-- l'identifiant n'est pas nul. Colonnes : team, jira_team_id (jamais masqué), tickets (tickets distincts qui portent la paire, masqué
-- sous 5). La vue lit la couche brute avec les droits de son propriétaire ; les tables brutes restent sans droit pour le rôle des vues.
--
-- Aucune colonne ne porte de clé de ticket, de titre, de description, de personne, d'étiquette, de projet, d'état, d'instant ni
-- d'identifiant d'équipe de la base. Aucun nom de colonne ne contient « key » ni « label ».
--
-- Droits : les droits par défaut du schéma donnent SELECT au rôle d'import et au rôle en lecture seule sur tout nouvel objet : ils sont
-- retirés ici, ainsi qu'à PUBLIC et au rôle des vues de la qualité, puis SELECT est donné au seul rôle des vues. Aucune donnée, aucun mot
-- de passe, aucun rôle créé ni modifié, aucune table changée.

SET LOCAL ROLE pmzilla_owner;

CREATE VIEW flow.v_teams AS
SELECT t.name AS team, t.team_type, flow.mask_count(count(i.key)) AS tickets
FROM flow.teams t
LEFT JOIN flow.issue_teams it ON it.team_id = t.id
LEFT JOIN flow.issues i ON i.key = it.issue_key AND i.out_of_export_at IS NULL
GROUP BY t.id, t.name, t.team_type;

CREATE VIEW flow.v_team_jira_ids AS
SELECT e.element ->> 'name' AS team, e.element ->> 'jira_team_id' AS jira_team_id,
       flow.mask_count(count(DISTINCT dernier.issue_key)) AS tickets
FROM (
    SELECT DISTINCT ON (s.issue_key) s.issue_key, s.teams
    FROM flow.raw_issue_snapshots s
    JOIN flow.issues i ON i.key = s.issue_key AND i.out_of_export_at IS NULL
    ORDER BY s.issue_key, s.run_id DESC
) dernier
CROSS JOIN LATERAL jsonb_array_elements(dernier.teams) AS e(element)
WHERE e.element ->> 'jira_team_id' IS NOT NULL
GROUP BY 1, 2;

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle

-- Droits : retirés d'abord (les droits par défaut du lot 1 s'appliquent à tout nouvel objet du propriétaire), puis accordés.
REVOKE ALL ON flow.v_teams FROM PUBLIC, pmzilla_flow, pmzilla_flow_ro, pmzilla_quality_views;
GRANT SELECT ON flow.v_teams TO pmzilla_flow_views;
REVOKE ALL ON flow.v_team_jira_ids FROM PUBLIC, pmzilla_flow, pmzilla_flow_ro, pmzilla_quality_views;
GRANT SELECT ON flow.v_team_jira_ids TO pmzilla_flow_views;
