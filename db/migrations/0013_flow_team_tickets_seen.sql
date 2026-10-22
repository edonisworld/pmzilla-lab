-- Schéma touché : flow (vue flow.v_team_tickets_seen).
-- Change database-only (D13) : la revue du catalogue de `check-teams` (entrées vues sur les tickets de l'export) lit les équipes vues sur
-- les tickets par cette vue agrégée, jamais par les tables des tickets ni des équipes par ticket. Une ligne par équipe qui porte, dans
-- flow.issue_teams, au moins un ticket stocké sans instant de sortie de l'export, avec le nombre de ces tickets : un ticket à deux équipes
-- compte une fois sous chacune, un ticket sans équipe n'apparaît nulle part.
--
-- Colonnes : team_id (identifiant de la ligne d'équipe), team_name (nom d'équipe, apparié aux entrées du catalogue par leur étiquette),
-- tickets (nombre, non masqué : la sortie de `check-teams` montre à l'auteur des décomptes et des identifiants d'équipe, jamais un ticket).
-- Aucune colonne ne porte de clé de ticket, de titre, de personne, d'étiquette, de type, d'état ni d'instant ; aucun nom de colonne ne
-- contient « key » ni « label ».
--
-- Droits : SELECT au seul rôle en lecture seule du flux. Les droits par défaut du schéma donnent SELECT au rôle d'import et au rôle en
-- lecture seule sur tout nouvel objet : ils sont retirés ici au rôle d'import, et par prudence au rôle des vues, au rôle des vues de la
-- qualité et à PUBLIC. Le rôle des vues ne la lit donc pas : flow_views.py, la session, les rapports et les tableaux de bord ne peuvent pas
-- la lire. Aucune donnée, aucun mot de passe, aucun rôle créé ni modifié, aucune autre vue ni table changée.

SET LOCAL ROLE pmzilla_owner;

CREATE VIEW flow.v_team_tickets_seen AS
SELECT t.id AS team_id, t.name AS team_name, count(*) AS tickets
FROM flow.issue_teams it
JOIN flow.issues i ON i.key = it.issue_key AND i.out_of_export_at IS NULL
JOIN flow.teams t ON t.id = it.team_id
GROUP BY t.id, t.name;

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle

-- Droits : retirés d'abord (les droits par défaut du lot 1 s'appliquent à tout nouvel objet du propriétaire), puis accordés.
REVOKE ALL ON flow.v_team_tickets_seen FROM PUBLIC, pmzilla_flow, pmzilla_flow_ro, pmzilla_flow_views, pmzilla_quality_views;
GRANT SELECT ON flow.v_team_tickets_seen TO pmzilla_flow_ro;
