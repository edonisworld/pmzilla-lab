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
Already cached and finished (not queried again): 0; to query: 1.
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

## collect, bulk mode (exit 0)

```
Tickets read: 5; discarded (portfolio types, excluded projects): 0.
Already cached and finished (not queried again): 0; to query: 5.
tickets past retention, skipped: 0
Mode: bulk. Tickets processed: 5; status transitions: 10; errors: 0.
```

## collect, everything cached (exit 0)

```
Tickets read: 5; discarded (portfolio types, excluded projects): 0.
Already cached and finished (not queried again): 4; to query: 1.
tickets past retention, skipped: 0
Mode: bulk. Tickets processed: 1; status transitions: 2; errors: 0.
```

## collect, --refresh (exit 0)

```
Tickets read: 5; discarded (portfolio types, excluded projects): 0.
Cache ignored (--refresh): to query: 5.
tickets past retention, skipped: 0
Mode: bulk. Tickets processed: 5; status transitions: 10; errors: 0.
```

## collect, --team (exit 0)

```
Tickets read: 5; discarded (portfolio types, excluded projects): 0; outside the requested team: 2.
Already cached and finished (not queried again): 2; to query: 1.
tickets past retention, skipped: 0
Mode: bulk. Tickets processed: 1; status transitions: 2; errors: 0.
```

## collect, unknown team (exit 1)

```
Error: --team: no ticket in the export matches.
```

## collect, tickets past retention (exit 0)

```
Tickets read: 2; discarded (portfolio types, excluded projects): 0.
Already cached and finished (not queried again): 0; to query: 1.
tickets past retention, skipped: 1
Mode: bulk. Tickets processed: 1; status transitions: 2; errors: 0.
```

## collect, ticket by ticket with one error (exit 0)

```
Tickets read: 5; discarded (portfolio types, excluded projects): 0.
Cache ignored (--refresh): to query: 5.
tickets past retention, skipped: 0
Mode: ticket by ticket. Tickets processed: 4; status transitions: 8; errors: 1 (HTTP 404: 1).
```

## collect, access denied (exit 1)

```
Tickets read: 5; discarded (portfolio types, excluded projects): 0.
Cache ignored (--refresh): to query: 5.
tickets past retention, skipped: 0
Mode: ticket by ticket. Tickets processed: 0; status transitions: 0; errors: 0.
Stopped: HTTP 401 (access denied: check the token and its permissions). The cache keeps what was collected.
```

## collect, no key column (exit 1)

```
Error: key column not found in the export (see the column names in flux.yaml). Only the CSV files of export_jira_api.py are read (uv run tools/export_jira_api.py export).
```

## collect, --team without a team column (exit 1)

```
Error: --team: no team column in the export.
```

## check (exit 0)

```
Export tickets kept: 6; missing from the cache: 1.
Last state in the history equal to the export state: consistent 3; inconsistent 1; not comparable (no transition) 1.
Transitions per ticket: 0: 1; 1: 2; 2-4: 2; 5-9: 0; 10 or more: 0.
Delivered tickets (resolution date): 4; delivered with no transition at all: 1.
Unreadable transition dates: 1 (the flux_jira.py computation cannot place these transitions).

Delivered tickets (4): reading of the history.
  Starting state of the first known transition: Open 2; Implementation 1.
  Transitions per delivered ticket: 0: 1; 1: 1; 2-4: 2; 5-9: 0; 10 or more: 0.
  Segments crossed (delivered tickets that went through the segment): definition 1; ready 1; implementation 2; review_verification 1; (no segment) 1.
  States crossed (delivered tickets): Done 3; Implementation 2; Open 2; Definition 1; Ready for Implementation 1; Verification 1.
```

## check, --team (exit 0)

```
Export tickets kept: 6; missing from the cache: 1.
Last state in the history equal to the export state: consistent 3; inconsistent 1; not comparable (no transition) 1.
Transitions per ticket: 0: 1; 1: 2; 2-4: 2; 5-9: 0; 10 or more: 0.
Delivered tickets (resolution date): 4; delivered with no transition at all: 1.
Unreadable transition dates: 1 (the flux_jira.py computation cannot place these transitions).

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
abc-2: 2 status transition(s) in the cache.
  start             Implementation
  2026-03-01 10:00:00+0200  Implementation  ->  Verification
  2026-03-02 10:00:00+0200  Verification  ->  Done
  export status: Done
```

## check, unknown --key (exit 1)

```
Error: ticket not in the cache.
```

## check, no export (exit 1)

```
Error: check: give at least one export (or --key).
```

## check, no status column (exit 1)

```
Error: no status column (Status) in the export.
```

## check, unreadable cache (exit 1)

```
Error: the history cache is unreadable: move it aside before running again.
```
