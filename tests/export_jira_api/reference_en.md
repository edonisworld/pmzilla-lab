# export_jira_api.py, test run

## export (exit 0)

```
Tickets: 4; pages: 1; columns: 17 (team: 2, links: 5 for 2 type(s)).
File written: api.csv (permissions 600).
```

## export without a team field (exit 0)

```
Tickets: 4; pages: 1; columns: 15 (team: 0, links: 5 for 2 type(s)).
No team column: export_team_field is not set.
File written: b.csv (permissions 600).
```

## export with the verification column (exit 0)

```
Tickets: 4; pages: 1; columns: 18 (team: 2, links: 5 for 2 type(s)).
Column "Verification Required": 2 ticket(s) filled out of 4 (no value displayed).
File written: c.csv (permissions 600).
```

## export, named queries (exit 0)

```
[a] Tickets: 4; pages: 1; columns: 17 (team: 2, links: 5 for 2 type(s)).
[a] File written: api-a-<today>.csv (permissions 600).
[b] Tickets: 4; pages: 1; columns: 17 (team: 2, links: 5 for 2 type(s)).
[b] File written: api-b-<today>.csv (permissions 600).
```

## export, one named query (exit 0)

```
[a] Tickets: 4; pages: 1; columns: 17 (team: 2, links: 5 for 2 type(s)).
[a] File written: d.csv (permissions 600).
```

## export, unknown query (exit 1)

```
Error: query "c" unknown. Available: a, b.
```

## export, --output with several queries (exit 1)

```
Error: --output only works with a single query: add --query NAME.
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

## settings, invalid verification field (exit 1)

```
Error: export_verification_field must be a field identifier (customfield_NNNNN).
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
The team field does not return the team label (shape received: empty, empty list, float, text). Nothing is guessed, nothing is written. Fill the organisation referential Flux-Lab/organisation.yaml: under `teams`, each team has the keys `name`, `headcount` and `jira_team_ids` (the list of its Jira team identifiers, entered by hand); the root keys are `source_date`, `sites`, `departments`, `teams` and `cross_cutting_teams`. Then run again; `diagnose` shows the shape of the field. The export then lists the identifiers to complete.
```

## diagnose, more shapes (exit 1)

```
Page queried: 4 ticket(s).
Shape of the team field values: list of object {value} / text 1; object {aa, zz} 1; text 1; text (identifier only) 1.
Usable labels: no.
The team field does not return the team label (shape received: list of object {value} / text, object {aa, zz}, text, text (identifier only)). Nothing is guessed, nothing is written. Fill the organisation referential Flux-Lab/organisation.yaml: under `teams`, each team has the keys `name`, `headcount` and `jira_team_ids` (the list of its Jira team identifiers, entered by hand); the root keys are `source_date`, `sites`, `departments`, `teams` and `cross_cutting_teams`. Then run again; `diagnose` shows the shape of the field. The export then lists the identifiers to complete.
```

## diagnose, Assets objects (exit 1)

```
Page queried: 4 ticket(s).
Shape of the team field values: list of object {id, objectId, workspaceId} 4.
Usable labels: no.
The team field does not return the team label (shape received: list of object {id, objectId, workspaceId}). Nothing is guessed, nothing is written. Fill the organisation referential Flux-Lab/organisation.yaml: under `teams`, each team has the keys `name`, `headcount` and `jira_team_ids` (the list of its Jira team identifiers, entered by hand); the root keys are `source_date`, `sites`, `departments`, `teams` and `cross_cutting_teams`. Then run again; `diagnose` shows the shape of the field. The export then lists the identifiers to complete.
```

## export, Assets objects without a table (exit 1)

```
Error: The team field does not return the team label (shape received: list of object {id, objectId, workspaceId}: 4). Nothing is guessed, nothing is written. Fill the organisation referential Flux-Lab/organisation.yaml: under `teams`, each team has the keys `name`, `headcount` and `jira_team_ids` (the list of its Jira team identifiers, entered by hand); the root keys are `source_date`, `sites`, `departments`, `teams` and `cross_cutting_teams`. Then run again; `diagnose` shows the shape of the field. The export then lists the identifiers to complete.
```

## diagnose, with a table (exit 0)

```
Page queried: 4 ticket(s).
Shape of the team field values: list of object {objectId} 4.
Usable labels: through the table equipes-assets.yaml (1 identifier(s)). The export can be written; complete the table if unknown teams show up.
team table deprecated: fill jira_team_ids in the organisation referential
```

## export, unknown teams (exit 0)

```
Tickets: 4; pages: 1; columns: 17 (team: 2, links: 5 for 2 type(s)).
team table deprecated: fill jira_team_ids in the organisation referential
Unknown teams: 1 distinct identifier(s) missing from the table, 4 ticket(s) affected, written "(équipe inconnue)".
Complete equipes-assets.yaml (equipes: identifier -> label) with these identifiers: 999.
File written: u.csv (permissions 600).
```

## export, unreadable table (exit 1)

```
Error: equipes-assets.yaml is unreadable: fix or recreate it by hand (equipes: {identifier: label}).
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

## export, with the table (exit 0)

```
Tickets: 6; pages: 1; columns: 12 (team: 2, links: 0 for 0 type(s)).
team table deprecated: fill jira_team_ids in the organisation referential
Unknown teams: 3 distinct identifier(s) missing from the table, 2 ticket(s) affected, written "(équipe inconnue)".
Complete equipes-assets.yaml (equipes: identifier -> label) with these identifiers: 4; 5; 6.
File written: w.csv (permissions 600).
```

## diagnose, with the referential (exit 0)

```
Page queried: 6 ticket(s).
Shape of the team field values: list of object {id, objectId, workspaceId} 6.
Usable labels: through the organisation referential (2 identifier(s)). The export can be written; complete jira_team_ids if unknown teams show up.
team table deprecated: fill jira_team_ids in the organisation referential
```

## export, referential and former table both present (exit 0)

```
Tickets: 6; pages: 1; columns: 12 (team: 2, links: 0 for 0 type(s)).
team table deprecated: fill jira_team_ids in the organisation referential
Unknown teams: 4 distinct identifier(s) missing from the referential, 3 ticket(s) affected, written "(équipe inconnue)".
Complete jira_team_ids of the organisation referential with these identifiers: 3; 4; 5; 6.
File written: x.csv (permissions 600).
referential teams without ticket: 1
```

## export, with the referential (exit 0)

```
Tickets: 6; pages: 1; columns: 12 (team: 2, links: 0 for 0 type(s)).
Unknown teams: 4 distinct identifier(s) missing from the referential, 3 ticket(s) affected, written "(équipe inconnue)".
Complete jira_team_ids of the organisation referential with these identifiers: 3; 4; 5; 6.
File written: r.csv (permissions 600).
referential teams without ticket: 1
```

## export, strict teams (exit 3)

```
Tickets: 6; pages: 1; columns: 12 (team: 2, links: 0 for 0 type(s)).
Unknown teams: 4 distinct identifier(s) missing from the referential, 3 ticket(s) affected, written "(équipe inconnue)".
Complete jira_team_ids of the organisation referential with these identifiers: 3; 4; 5; 6.
File written: s.csv (permissions 600).
referential teams without ticket: 1
unknown team identifiers: export incomplete
```

## diagnose, with the former table (exit 0)

```
Page queried: 6 ticket(s).
Shape of the team field values: list of object {id, objectId, workspaceId} 6.
Usable labels: through the table equipes-assets.yaml (3 identifier(s)). The export can be written; complete the table if unknown teams show up.
team table deprecated: fill jira_team_ids in the organisation referential
```

## export, former table fallback (exit 0)

```
Tickets: 6; pages: 1; columns: 12 (team: 2, links: 0 for 0 type(s)).
team table deprecated: fill jira_team_ids in the organisation referential
Unknown teams: 3 distinct identifier(s) missing from the table, 2 ticket(s) affected, written "(équipe inconnue)".
Complete equipes-assets.yaml (equipes: identifier -> label) with these identifiers: 4; 5; 6.
File written: f.csv (permissions 600).
```

## export, declared labels and fix versions (exit 0)

```
Tickets: 4; pages: 1; columns: 19 (team: 0, links: 5 for 2 type(s)).
No team column: export_team_field is not set.
undeclared labels with a declared prefix: 1
  tickets carrying them: 2 (no label displayed).
up-merge items with two labels: 1
File written: l.csv (permissions 600).
```

## export, rows past the retention rule (exit 0)

```
Tickets: 3; pages: 1; columns: 12 (team: 0, links: 2 for 2 type(s)).
tickets past retention, not written: 1
No team column: export_team_field is not set.
File written: k.csv (permissions 600).
```

## teams-table, retired (exit 2)

```
Error: the teams-table subcommand is retired. Flux-Lab/equipes-assets.yaml is completed by hand (equipes: identifier -> label); `export_jira_api.py export` lists the unknown identifiers.
```

## compare, retired (exit 2)

```
Error: the compare subcommand is retired (the manual CSV export is no longer a route). Use `export_jira_api.py export`; the database-versus-CSV comparison is in flow_compare.py.
```
