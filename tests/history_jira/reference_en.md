# history_jira.py, parcours de test

## test, connection (exit 0)

```
connection OK
access search: OK
access history: OK
access fields: OK
```

## test, access denied (exit 1)

```
HTTP 401
```

## missing settings (exit 1)

```
Error: missing settings in <ws>/Flux-Lab/flux.yaml: jira_site
```

## remote http (exit 1)

```
Error: jira_site must start with https:// (http is only accepted for the local machine).
```

## token type (exit 1)

```
Error: jira_token_type must be "scoped".
```

## test, classic token (exit 1)

```
Error: classic token refused: use a scoped token
```

## collect, classic token (exit 1)

```
Tickets read: 1; discarded (portfolio types, excluded projects): 0.
Already collected and finished (not queried again): 0; to query: 1.
Finished tickets queried again (updated since the last collection): 0.
tickets past retention, skipped: 0
Error: classic token refused: use a scoped token
```

## test, cloud id missing (exit 1)

```
Error: cloudId not found: jira_cloud_id is missing or invalid in the settings.
```

## test, cloud id with path characters (exit 1)

```
Error: cloudId not found: jira_cloud_id is missing or invalid in the settings.
```

## test, cloud id differs from the site's (exit 1)

```
Error: cloudId differs from the site's
```

## test, missing scope on history (exit 1)

```
connection OK
access search: OK
access history: 403
access fields: OK
```

## test, missing scopes on search and fields (exit 1)

```
connection OK
access search: 403
access history: OK
access fields: 403
```

## test, token expires soon (exit 0)

```
connection OK
access search: OK
access history: OK
access fields: OK
API token expires in 10 days
```

## test, token expiry passed (exit 0)

```
connection OK
access search: OK
access history: OK
access fields: OK
API token expiry date passed
```

## test, token expiry passed and a refused call (exit 1)

```
connection OK
access search: OK
access history: OK
access fields: 403
API token expiry date passed
```

## test, no token expiry date (exit 0)

```
connection OK
access search: OK
access history: OK
access fields: OK
token expiry date not set
```

## collect, empty database (exit 1)

```
Error: no ticket in the database: run the export and the import first
```

## collect, bulk mode (exit 0)

```
Tickets read: 5; discarded (portfolio types, excluded projects): 0.
Already collected and finished (not queried again): 0; to query: 5.
Finished tickets queried again (updated since the last collection): 0.
tickets past retention, skipped: 0
Mode: bulk. Tickets processed: 5; status transitions: 10; errors: 0.
history written: 10 transitions added, 0 periods written
```

## collect, everything already collected (exit 0)

```
Tickets read: 5; discarded (portfolio types, excluded projects): 0.
Already collected and finished (not queried again): 4; to query: 1.
Finished tickets queried again (updated since the last collection): 0.
tickets past retention, skipped: 0
Mode: bulk. Tickets processed: 1; status transitions: 2; errors: 0.
history written: 0 transitions added, 0 periods written
```

## collect, --refresh (exit 0)

```
Tickets read: 5; discarded (portfolio types, excluded projects): 0.
Everything is queried again (--refresh): to query: 5.
tickets past retention, skipped: 0
Mode: bulk. Tickets processed: 5; status transitions: 10; errors: 0.
history written: 0 transitions added, 0 periods written
```

## collect, --team (exit 0)

```
Tickets read: 5; discarded (portfolio types, excluded projects): 0; outside the requested team: 2.
Already collected and finished (not queried again): 2; to query: 1.
Finished tickets queried again (updated since the last collection): 0.
tickets past retention, skipped: 0
Mode: bulk. Tickets processed: 1; status transitions: 2; errors: 0.
history written: 0 transitions added, 0 periods written
```

## collect, unknown team (exit 1)

```
Error: --team: no ticket in the database matches.
```

## collect, tickets past retention (exit 0)

```
Tickets read: 5; discarded (portfolio types, excluded projects): 0.
Everything is queried again (--refresh): to query: 4.
tickets past retention, skipped: 1
Mode: bulk. Tickets processed: 4; status transitions: 8; errors: 0.
history written: 0 transitions added, 0 periods written
```

## collect, ticket by ticket with one error (exit 0)

```
Tickets read: 5; discarded (portfolio types, excluded projects): 0.
Everything is queried again (--refresh): to query: 5.
tickets past retention, skipped: 0
Mode: ticket by ticket. Tickets processed: 4; status transitions: 8; errors: 0.
tickets not found in Jira: 1
history written: 0 transitions added, 0 periods written
```

## collect, access denied (exit 1)

```
Tickets read: 5; discarded (portfolio types, excluded projects): 0.
Everything is queried again (--refresh): to query: 5.
tickets past retention, skipped: 0
Mode: ticket by ticket. Tickets processed: 0; status transitions: 0; errors: 0.
Stopped: HTTP 401 (access denied: check the token and its permissions). Nothing is written to the database.
```

## collect, export file refused (exit 2)

```
Error: export files are no longer read: the database is the only source
```

## collect, --team without a team in the database (exit 1)

```
Error: --team: no team in the database.
```

## check (exit 0)

```
Database tickets kept: 6; without history: 1.
Last state in the history equal to the stored state: consistent 3; inconsistent 1; not comparable (no transition) 1.
Transitions per ticket: 0: 1; 1: 2; 2-4: 2; 5-9: 0; 10 or more: 0.
Delivered tickets (resolution date): 4; delivered with no transition at all: 1.

Delivered tickets (4): reading of the history.
  Starting state of the first known transition: Open 2; Implementation 1.
  Transitions per delivered ticket: 0: 1; 1: 1; 2-4: 2; 5-9: 0; 10 or more: 0.
  Segments crossed (delivered tickets that went through the segment): definition 1; ready 1; implementation 2; review_verification 1; (no segment) 1.
  States crossed (delivered tickets): Done 3; Implementation 2; Open 2; Definition 1; Ready for Implementation 1; Verification 1.
```

## check, --team (exit 0)

```
Database tickets kept: 6; without history: 1.
Last state in the history equal to the stored state: consistent 3; inconsistent 1; not comparable (no transition) 1.
Transitions per ticket: 0: 1; 1: 2; 2-4: 2; 5-9: 0; 10 or more: 0.
Delivered tickets (resolution date): 4; delivered with no transition at all: 1.

Delivered tickets (4): reading of the history.
  Starting state of the first known transition: Open 2; Implementation 1.
  Transitions per delivered ticket: 0: 1; 1: 1; 2-4: 2; 5-9: 0; 10 or more: 0.
  Segments crossed (delivered tickets that went through the segment): definition 1; ready 1; implementation 2; review_verification 1; (no segment) 1.
  States crossed (delivered tickets): Done 3; Implementation 2; Open 2; Definition 1; Ready for Implementation 1; Verification 1.
```

## check, --dormants removed (exit 1)

```
Error: --dormants (dormant tickets CSV export) no longer exists: dormant items are inferred from the status history. Use flux_jira.py compute --dormant-from-history.
```

## check, --key (exit 0)

```
abc-2: 2 status transition(s) in the database.
  start             Implementation
  2026-03-01 09:00:00+0100  Implementation  ->  Verification
  2026-03-02 09:00:00+0100  Verification  ->  Done
  stored status: Done
```

## check, unknown --key (exit 1)

```
Error: ticket not in the database.
```

## check, export file refused (exit 2)

```
Error: export files are no longer read: the database is the only source
```

## check, inside a Claude Code session (exit 3)

```
Refused inside a Claude Code session
```

## check, no history in the database (exit 1)

```
Error: no history in the database: run the history collection first
```
