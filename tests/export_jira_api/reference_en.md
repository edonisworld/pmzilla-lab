# export_jira_api.py, test run

## export (exit 0)

```
Tickets: 4; pages: 1.
teams without a type: 2
raw layer: 4 tickets seen, 4 snapshots added
```

## export without a team field (exit 0)

```
Tickets: 4; pages: 1.
No team read: export_team_field is not set.
teams without a type: 0
raw layer: 4 tickets seen, 3 snapshots added
```

## export with the retired verification setting (exit 0)

```
Tickets: 4; pages: 1.
teams without a type: 2
raw layer: 4 tickets seen, 3 snapshots added
```

## export, named queries (exit 0)

```
[a] Tickets: 4; pages: 1.
[b] Tickets: 4; pages: 1.
teams without a type: 2
raw layer: 4 tickets seen, 0 snapshots added
```

## export, one named query (exit 0)

```
[a] Tickets: 4; pages: 1.
teams without a type: 2
raw layer: 4 tickets seen, 0 snapshots added
```

## export, full option (exit 0)

```
[a] Tickets: 4; pages: 1.
[b] Tickets: 4; pages: 1.
teams without a type: 2
raw layer: 4 tickets seen, 0 snapshots added
```

## export, unknown query (exit 1)

```
Error: query "c" unknown. Available: a, b.
```

## export, --output retired (exit 2)

```
Error: --output is retired: the export writes into the database
```

## export, --query without jql_exports (exit 1)

```
Error: --query needs a jql_exports setting in flux.yaml (name -> JQL query); only jql_export exists.
```

## settings, missing query (exit 1)

```
Error: setting jql_export (or jql_exports) is missing in <ws>/Flux-Lab/flux.yaml.
```

## settings, invalid query name (exit 1)

```
Error: a jql_exports name contains only letters, digits, hyphens and underscores.
```

## settings, empty query (exit 1)

```
Error: the query "a" of jql_exports is empty.
```

## settings, query list (exit 1)

```
Error: jql_exports must map a name to a JQL query.
```

## settings, invalid team field (exit 1)

```
Error: export_team_field must be a field identifier (customfield_NNNNN).
```

## settings, invalid points field (exit 1)

```
Error: export_points_field must be a field identifier (customfield_NNNNN).
```

## settings, unknown time zone (exit 1)

```
Error: export_timezone "Nulle/Part" is not a known time zone (example: Europe/Paris).
```

## export, classic token (exit 1)

```
Error: classic token refused: use a scoped token
```

## fields, classic token (exit 1)

```
Error: classic token refused: use a scoped token
```

## export, cloud id missing (exit 1)

```
Error: cloudId not found: jira_cloud_id is missing or invalid in the settings.
```

## export, access denied (exit 1)

```
HTTP 401
```

## fields, access denied (exit 1)

```
HTTP 401
```

## diagnose (exit 0)

```
Page queried: 4 ticket(s).
Shape of the team field values: empty list 1; list of object {value} 3.
Usable labels: yes (text, or object with a label). The export can be written.
```

## diagnose without a team field (exit 1)

```
Error: setting export_team_field is missing: nothing to diagnose for the team.
```

## diagnose, field absent (exit 1)

```
Page queried: 4 ticket(s).
Error: the team field is absent from the responses: check its identifier and the token permissions.
```

## diagnose, various shapes (exit 1)

```
Page queried: 4 ticket(s).
Shape of the team field values: empty 1; empty list 1; float 1; text 1.
Usable labels: no.
no team source: fill jira_team_ids in the referential and the catalogue. The team field does not return the team label (shape received: empty, empty list, float, text). Nothing is guessed, nothing is written.
Organisation referential Flux-Lab/organisation.yaml (keys only):
source_date: <date>
sites: [<site>, ...]
departments:
  - name: <name>
    site: <declared site>
    headcount: <integer>
    mission_teams:                 # or teams: [<team>, ...]
      - name: <name>
        discovery_workflow_pilot: <true|false>   # optional
        teams: [<team>, ...]
teams:
  - name: <name>
    headcount: <integer>
    site: <declared site>          # optional
    jira_team_ids: [<identifier>, ...]   # optional
    type: <Team sub-type>          # optional, forces the type deduced from the catalogue
cross_cutting_teams: [<team>, ...]  # optional
Team catalogue Flux-Lab/equipes-jira.yaml (keys only):
teams:
  - name: <label>
    jira_team_ids: [<identifier>, ...]
    type: <Team sub-type>            # optional
    obsolete: <true|false>           # optional
`diagnose` shows the shape of the field. The export then lists the identifiers to add.
```

## diagnose, more shapes (exit 1)

```
Page queried: 4 ticket(s).
Shape of the team field values: list of object {value} / text 1; object {aa, zz} 1; text 1; text (identifier only) 1.
Usable labels: no.
no team source: fill jira_team_ids in the referential and the catalogue. The team field does not return the team label (shape received: list of object {value} / text, object {aa, zz}, text, text (identifier only)). Nothing is guessed, nothing is written.
Organisation referential Flux-Lab/organisation.yaml (keys only):
source_date: <date>
sites: [<site>, ...]
departments:
  - name: <name>
    site: <declared site>
    headcount: <integer>
    mission_teams:                 # or teams: [<team>, ...]
      - name: <name>
        discovery_workflow_pilot: <true|false>   # optional
        teams: [<team>, ...]
teams:
  - name: <name>
    headcount: <integer>
    site: <declared site>          # optional
    jira_team_ids: [<identifier>, ...]   # optional
    type: <Team sub-type>          # optional, forces the type deduced from the catalogue
cross_cutting_teams: [<team>, ...]  # optional
Team catalogue Flux-Lab/equipes-jira.yaml (keys only):
teams:
  - name: <label>
    jira_team_ids: [<identifier>, ...]
    type: <Team sub-type>            # optional
    obsolete: <true|false>           # optional
`diagnose` shows the shape of the field. The export then lists the identifiers to add.
```

## diagnose, Assets objects (exit 1)

```
Page queried: 4 ticket(s).
Shape of the team field values: list of object {id, objectId, workspaceId} 4.
Usable labels: no.
no team source: fill jira_team_ids in the referential and the catalogue. The team field does not return the team label (shape received: list of object {id, objectId, workspaceId}). Nothing is guessed, nothing is written.
Organisation referential Flux-Lab/organisation.yaml (keys only):
source_date: <date>
sites: [<site>, ...]
departments:
  - name: <name>
    site: <declared site>
    headcount: <integer>
    mission_teams:                 # or teams: [<team>, ...]
      - name: <name>
        discovery_workflow_pilot: <true|false>   # optional
        teams: [<team>, ...]
teams:
  - name: <name>
    headcount: <integer>
    site: <declared site>          # optional
    jira_team_ids: [<identifier>, ...]   # optional
    type: <Team sub-type>          # optional, forces the type deduced from the catalogue
cross_cutting_teams: [<team>, ...]  # optional
Team catalogue Flux-Lab/equipes-jira.yaml (keys only):
teams:
  - name: <label>
    jira_team_ids: [<identifier>, ...]
    type: <Team sub-type>            # optional
    obsolete: <true|false>           # optional
`diagnose` shows the shape of the field. The export then lists the identifiers to add.
```

## export, Assets objects without a source (exit 1)

```
Error: no team source: fill jira_team_ids in the referential and the catalogue. The team field does not return the team label (shape received: list of object {id, objectId, workspaceId}: 4). Nothing is guessed, nothing is written.
Organisation referential Flux-Lab/organisation.yaml (keys only):
source_date: <date>
sites: [<site>, ...]
departments:
  - name: <name>
    site: <declared site>
    headcount: <integer>
    mission_teams:                 # or teams: [<team>, ...]
      - name: <name>
        discovery_workflow_pilot: <true|false>   # optional
        teams: [<team>, ...]
teams:
  - name: <name>
    headcount: <integer>
    site: <declared site>          # optional
    jira_team_ids: [<identifier>, ...]   # optional
    type: <Team sub-type>          # optional, forces the type deduced from the catalogue
cross_cutting_teams: [<team>, ...]  # optional
Team catalogue Flux-Lab/equipes-jira.yaml (keys only):
teams:
  - name: <label>
    jira_team_ids: [<identifier>, ...]
    type: <Team sub-type>            # optional
    obsolete: <true|false>           # optional
`diagnose` shows the shape of the field. The export then lists the identifiers to add.
```

## diagnose, with a catalogue (exit 0)

```
Page queried: 4 ticket(s).
Shape of the team field values: list of object {objectId} 4.
Usable labels: through the team sources. The export can be written; complete jira_team_ids or the catalogue if identifiers to add show up.
team sources: referential 0 identifiers, catalogue 1 identifiers
```

## export, unknown teams (exit 0)

```
Tickets: 4; pages: 1.
teams outside the organisation: 1 identifiers, 4 tickets
team identifiers in neither the referential nor the catalogue: 1, on 4 tickets
identifiers to add: 999
teams without a type: 2
raw layer: 4 tickets seen, 4 snapshots added
```

## export, obsolete team (exit 0)

```
Tickets: 4; pages: 1.
teams outside the organisation: 1 identifiers, 4 tickets
tickets on obsolete teams: 4
team identifiers in neither the referential nor the catalogue: 1, on 4 tickets
identifiers to add: 999
teams without a type: 2
raw layer: 4 tickets seen, 0 snapshots added
```

## fields (exit 0)

```
2 field(s) out of 5 whose name contains the searched text.
  customfield_10002  [G] team label
  customfield_10001  [G] Team/s
```

## fields, no match (exit 0)

```
0 field(s) out of 5 whose name contains the searched text.
```

## fields, empty text (exit 1)

```
Error: --search: give a text to look for in the field names.
```

## fields, unexpected response (exit 1)

```
Error: unexpected response from Jira for the field list.
```

## export, with the catalogue (exit 0)

```
Tickets: 6; pages: 1.
teams outside the organisation: 3 identifiers, 4 tickets
team identifiers in neither the referential nor the catalogue: 3, on 2 tickets
identifiers to add: 4; 5; 6
teams without a type: 4
raw layer: 6 tickets seen, 6 snapshots added
```

## diagnose, with the referential and the catalogue (exit 0)

```
Page queried: 6 ticket(s).
Shape of the team field values: list of object {id, objectId, workspaceId} 6.
Usable labels: through the team sources. The export can be written; complete jira_team_ids or the catalogue if identifiers to add show up.
team sources: referential 2 identifiers, catalogue 3 identifiers
```

## export, referential, catalogue and former table present (exit 0)

```
Tickets: 6; pages: 1.
former team table no longer read: delete equipes-assets.yaml
teams outside the organisation: 1 identifiers, 1 tickets
team identifiers in neither the referential nor the catalogue: 3, on 2 tickets
identifiers to add: 4; 5; 6
referential teams without ticket: 1
teams without a type: 4
raw layer: 6 tickets seen, 0 snapshots added
```

## export, referential and catalogue share an identifier (exit 0)

```
Tickets: 6; pages: 1.
team identifiers in neither the referential nor the catalogue: 4, on 3 tickets
identifiers to add: 3; 4; 5; 6
referential teams without ticket: 1
teams without a type: 3
raw layer: 6 tickets seen, 1 snapshots added
```

## export, strict teams (exit 3)

```
Tickets: 6; pages: 1.
team identifiers in neither the referential nor the catalogue: 4, on 3 tickets
identifiers to add: 3; 4; 5; 6
referential teams without ticket: 1
unknown team identifiers: export incomplete
```

## export, catalogue team named like a referential team (exit 1)

```
Error: catalogue team named like a referential team: catalogue "teams[0].name" (L2) / referential "teams[0].name" (L9)
```

## diagnose, with the former table only (exit 1)

```
Page queried: 6 ticket(s).
Shape of the team field values: list of object {id, objectId, workspaceId} 6.
Usable labels: no.
no team source: fill jira_team_ids in the referential and the catalogue. The team field does not return the team label (shape received: list of object {id, objectId, workspaceId}). Nothing is guessed, nothing is written.
Organisation referential Flux-Lab/organisation.yaml (keys only):
source_date: <date>
sites: [<site>, ...]
departments:
  - name: <name>
    site: <declared site>
    headcount: <integer>
    mission_teams:                 # or teams: [<team>, ...]
      - name: <name>
        discovery_workflow_pilot: <true|false>   # optional
        teams: [<team>, ...]
teams:
  - name: <name>
    headcount: <integer>
    site: <declared site>          # optional
    jira_team_ids: [<identifier>, ...]   # optional
    type: <Team sub-type>          # optional, forces the type deduced from the catalogue
cross_cutting_teams: [<team>, ...]  # optional
Team catalogue Flux-Lab/equipes-jira.yaml (keys only):
teams:
  - name: <label>
    jira_team_ids: [<identifier>, ...]
    type: <Team sub-type>            # optional
    obsolete: <true|false>           # optional
`diagnose` shows the shape of the field. The export then lists the identifiers to add.
former team table no longer read: delete equipes-assets.yaml
```

## export, former table only (exit 1)

```
Error: no team source: fill jira_team_ids in the referential and the catalogue. The team field does not return the team label (shape received: list of object {id, objectId, workspaceId}: 6). Nothing is guessed, nothing is written.
Organisation referential Flux-Lab/organisation.yaml (keys only):
source_date: <date>
sites: [<site>, ...]
departments:
  - name: <name>
    site: <declared site>
    headcount: <integer>
    mission_teams:                 # or teams: [<team>, ...]
      - name: <name>
        discovery_workflow_pilot: <true|false>   # optional
        teams: [<team>, ...]
teams:
  - name: <name>
    headcount: <integer>
    site: <declared site>          # optional
    jira_team_ids: [<identifier>, ...]   # optional
    type: <Team sub-type>          # optional, forces the type deduced from the catalogue
cross_cutting_teams: [<team>, ...]  # optional
Team catalogue Flux-Lab/equipes-jira.yaml (keys only):
teams:
  - name: <label>
    jira_team_ids: [<identifier>, ...]
    type: <Team sub-type>            # optional
    obsolete: <true|false>           # optional
`diagnose` shows the shape of the field. The export then lists the identifiers to add.
```

## export, declared labels (not requested any more) (exit 0)

```
Tickets: 4; pages: 1.
No team read: export_team_field is not set.
teams without a type: 0
raw layer: 4 tickets seen, 2 snapshots added
```

## export, rows past the retention rule (exit 0)

```
Tickets: 3; pages: 1.
tickets past retention, not written: 1
No team read: export_team_field is not set.
teams without a type: 0
raw layer: 3 tickets seen, 0 snapshots added
```

## teams-table, retired (exit 2)

```
Error: the teams-table subcommand is retired. Teams are entered by hand in the referential (Flux-Lab/organisation.yaml) and the catalogue (Flux-Lab/equipes-jira.yaml); `export_jira_api.py export` lists the identifiers to add.
```

## compare, retired (exit 2)

```
Error: the compare subcommand is retired (the manual CSV export is no longer a route). Use `export_jira_api.py export`; the database-versus-CSV comparison is in flow_compare.py.
```
