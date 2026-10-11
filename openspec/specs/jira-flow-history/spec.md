# jira-flow-history Specification

## Purpose

Describes the tool that collects the status history of tickets from the Jira API into a local cache (only date, starting status and arrival status of each transition), and checks that cache against an export. It also covers the shared history-reading rules (date normalisation, chronological sorting, segments, dormant tickets) used by the flow report. Sources are the tests in `tests/history_jira/`.

## Requirements

### Requirement: Connection test
The system SHALL provide a `test` subcommand that checks the connection to Jira and prints only "connexion OK" on success, or only the HTTP status code on failure (exit 1), never the site, account, token or any name returned by Jira. With the scoped-token mode it SHALL go through the cloud identifier of the site without printing it. Missing settings SHALL produce an error naming the missing setting, without printing any value of the settings. A non-secure remote site address SHALL be refused before any call. The token SHALL be read from the operating-system keychain; a missing token SHALL give a message without traceback.

Source: tests/history_jira/test_history_jira.py (Connexion)

#### Scenario: Connection succeeds
- **WHEN** `test` runs with valid settings
- **THEN** the output is exactly the success text and the exit code is 0

#### Scenario: Credentials refused
- **WHEN** Jira answers 401
- **THEN** the output is the status code only, with no site, account or token, exit code 1

#### Scenario: Plain-HTTP site
- **WHEN** the site address is not HTTPS
- **THEN** the exit code is 1, the message mentions HTTPS and no call is made

#### Scenario: Token lookup
- **WHEN** the token is read
- **THEN** the system asks the keychain for the generic password of the dedicated service, and prints a no-traceback message if it is not found

### Requirement: Scoped-token authentication sequence
The system SHALL, in the scoped-token mode, first read the cloud identifier from the site without authentication, then send the authenticated request through the cloud gateway address built from that identifier; `test` SHALL make exactly these two calls. A refused token SHALL print only the HTTP status code (exit 1), never the cloud identifier, the site, the account or the token, and SHALL NOT be retried. A missing, empty or unsafe cloud identifier (one that contains path characters) SHALL stop the run with exit 1 and a "cloudId introuvable" message, without traceback and before any authenticated call.

Source: tests/history_jira/test_jeton_scopes.py

#### Scenario: Full sequence
- **WHEN** `test` runs in the scoped-token mode with valid settings
- **THEN** the output is exactly the success text, the first call reads the cloud identifier on the site without authentication, and the second is one authenticated search through the gateway address

#### Scenario: Token refused
- **WHEN** the gateway refuses the token
- **THEN** the output is the status code alone, with no cloud identifier, site, account, token or traceback, and no further call is made

#### Scenario: Unusable cloud identifier
- **WHEN** the site returns no cloud identifier, an empty one, or one containing a path
- **THEN** the exit code is 1, the message says the cloud identifier was not found, and no authenticated call is made

### Requirement: Former names
The system SHALL accept former option names and former setting names (and former setting values) with a warning naming the new name, SHALL refuse former subcommand names with exit code 2 without any call to Jira, and SHALL cite the new setting name in missing-setting messages.

Source: tests/history_jira/test_history_jira.py (AnciensNoms)

#### Scenario: Former options
- **WHEN** a former name of the team, refresh or key option is used
- **THEN** it works and a warning gives the new option name

#### Scenario: New names
- **WHEN** only new names are used
- **THEN** no warning is printed

### Requirement: History collection keeps only date and states
The system SHALL provide a `collect` subcommand that reads one or more export CSV files, merges the tickets by key, and for each ticket stores in the cache only a finished flag and the list of status transitions as (date, starting status, arrival status). Changes to other fields SHALL be discarded and the author SHALL never be stored. The console SHALL report the mode, the tickets processed, the transition count and the error count, without ticket keys, team names, token, titles, site address or author.

Source: tests/history_jira/test_history_jira.py (Collecte)

#### Scenario: Grouped mode
- **WHEN** the grouped history API is available
- **THEN** each cache entry holds exactly the finished flag and its three-element transitions, the assignee change is dropped, and the console says the mode is grouped

#### Scenario: Nothing sensitive written
- **WHEN** a collection ends
- **THEN** neither the console nor any file written contains the token, the author, the author's address, a title, the assignee field name or the account address

#### Scenario: Export without key column
- **WHEN** the export has no key column
- **THEN** the exit code is 1 and the message mentions the key column

### Requirement: Pagination and fallback
The system SHALL follow pagination of the key search, of the grouped history (including a ticket split between two pages) and of the per-ticket history. It SHALL fall back to a per-ticket mode when the grouped API is unavailable, and in that mode SHALL read until the last page, or until an empty page when the API gives no last-page indicator.

Source: tests/history_jira/test_history_jira.py (test_pagination_groupee, test_repli_ticket_par_ticket_avec_pagination, test_pagination_groupee_ticket_coupe_entre_deux_pages_et_recherche_paginee, test_ticket_par_ticket_sans_islast_va_jusqu_a_la_page_vide)

#### Scenario: Fallback
- **WHEN** the grouped API answers 404
- **THEN** the console says the mode is ticket by ticket and every ticket has all its transitions

#### Scenario: Ticket split across pages
- **WHEN** the grouped response is cut in the middle of a ticket's history
- **THEN** the ticket's transitions are completed from the next page

### Requirement: Incremental cache
The system SHALL re-query only tickets absent from the cache or not marked finished, SHALL report how many were already cached and finished and how many will be queried, SHALL make no Jira call when everything is cached and finished, SHALL re-query once a ticket that has become finished, and SHALL ignore the cache with `--refresh` (reporting it).

Source: tests/history_jira/test_history_jira.py (test_incremental_ne_reinterroge_que_les_non_termines_ou_absents, test_tout_en_cache_et_termine_aucun_appel, test_ticket_devenu_termine_est_reinterroge_une_fois, test_rafraichir_ignore_le_cache)

#### Scenario: Second collection
- **WHEN** a ticket is new and another is unfinished and the rest are finished and cached
- **THEN** one search batch queries only those two tickets

### Requirement: Team filter and scope exclusions
The system SHALL, with `--team`, keep a ticket as soon as any of its team columns (including values separated by semicolons) matches case-insensitively, and report only the count of tickets outside the team, never the name. An unknown team SHALL stop with exit 1 and no Jira call, without echoing the name. Portfolio-level issue types and excluded projects from the settings SHALL NOT be queried, and their count SHALL be reported.

Source: tests/history_jira/test_history_jira.py (test_equipe_filtre_et_ne_montre_pas_le_nom, test_equipe_retient_un_ticket_des_qu_une_de_ses_equipes_correspond, test_equipe_inconnue, test_portefeuille_et_projets_exclus_ne_sont_pas_interroges)

#### Scenario: Multi-team ticket
- **WHEN** the requested team appears in a second team column
- **THEN** the ticket is kept

### Requirement: Rate limiting and errors
The system SHALL honor the retry delay supplied by Jira on HTTP 429 and retry; without such a delay it SHALL wait with doubling delays and give up after several attempts with the final status code. Persistent throttling SHALL count errors per status code in the report, exit 0, and write no cache. An access error (401) SHALL stop the run with exit 1 and a message giving only the code. A ticket not found SHALL count as one error and be left out of the cache so it is retried.

Source: tests/history_jira/test_history_jira.py (test_429_*, test_attente_croissante_sans_retry_after, test_erreur_d_acces_arrete_et_garde_le_cache, test_ticket_introuvable_compte_une_erreur)

#### Scenario: Transient throttling
- **WHEN** the first two calls answer 429 with a one-second delay
- **THEN** the system waits one second twice, then succeeds

#### Scenario: Persistent throttling
- **WHEN** every call answers 429
- **THEN** the report shows the errors with their code, exit code is 0 and no cache file exists

### Requirement: Cache stored privately
The system SHALL store the cache outside version control, in a folder readable only by its owner, with the file readable and writable only by its owner.

Source: tests/history_jira/test_history_jira.py (test_cache_hors_git_permissions_restreintes)

#### Scenario: Permissions
- **WHEN** a collection writes the cache
- **THEN** the folder is owner-only and the file is owner read/write only

### Requirement: Date normalisation and chronological order
The system SHALL store and read transition dates as ISO 8601 text with offset; a millisecond or second epoch value (number or digit text) SHALL be converted to a UTC date; an unreadable value SHALL be kept as text; empty becomes none. Transitions SHALL be sorted by instant, not by text, regardless of the API order or offsets; an unreadable date SHALL NOT crash and SHALL sort after readable ones. An older cache with numeric dates SHALL give the same results as a cache with ISO dates.

Source: tests/history_jira/test_history_jira.py (NormaliserDate, Tri, FormatsDeDateReduits, FluxSurCacheReel)

#### Scenario: Mixed offsets
- **WHEN** a history has an entry at 09:00 with a positive two-hour offset and another at 08:00 UTC
- **THEN** the first one is ordered before the second

#### Scenario: Old numeric cache
- **WHEN** the cache holds millisecond numbers
- **THEN** the flow report computed from it gives the same lead-time and segment results, and the key inspection prints readable UTC dates

### Requirement: Single CSV date format
The system SHALL read CSV dates only in the format of the API export (day, abbreviated month, year, hour, minute) and refuse other formats (ISO, numeric day-month-year, two-digit year, AM/PM) as unreadable.

Source: tests/history_jira/test_history_jira.py (FormatsDeDateReduits)

#### Scenario: Other format
- **WHEN** a date such as an ISO date is parsed
- **THEN** it is rejected as none

### Requirement: Dormant tickets from history
The system SHALL compute dormant tickets from the history as tickets not finished, created at least a threshold number of days ago, with no status change for at least that many days (last transition date, or creation date if none). A ticket absent from the cache SHALL NOT be dormant and SHALL be counted separately.

Source: tests/history_jira/test_history_jira.py (test_dormants_selon_l_historique_sans_format_de_csv)

#### Scenario: Unknown history
- **WHEN** one old ticket has a long-ago transition, one recent ticket has none, and one old ticket is absent from the cache
- **THEN** only the first is dormant and one ticket is counted as without history

### Requirement: Cache check
The system SHALL provide a `check` subcommand that reads an export and the cache, makes no network call, and reports aggregated counts only: tickets absent from the cache, consistency between the last arrival status and the export status (consistent, inconsistent, not comparable when there are no transitions), distribution of transitions per ticket in fixed buckets, delivered tickets without any transition, unreadable transition dates with their count, starting state of the first known transition, and number of delivered tickets passing through each segment (including "no segment"). The report SHALL contain no key, no team, no title. Segments SHALL come from the settings when set, otherwise from defaults, and the default table SHALL also place known workflow start and end states outside the computed segments. The flow report SHALL use the same segment table as the check.

Source: tests/history_jira/test_history_jira.py (Controle, FluxSurCacheReel)

#### Scenario: Aggregated counts
- **WHEN** the check runs on five delivered tickets plus one uncached open ticket
- **THEN** it prints the uncached count, the consistent/inconsistent/not-comparable counts and the transition distribution buckets, with no keys and no team name

#### Scenario: Unreadable dates
- **WHEN** transition dates in the cache cannot be read
- **THEN** the check reports their number, and the flow report counts them and warns instead of silently using zero

#### Scenario: Segments from settings
- **WHEN** the settings define a custom segment
- **THEN** the check reports delivered tickets per that segment

### Requirement: Inspect one ticket
The system SHALL provide `check --key <key>` that prints the ordered list of status transitions of one ticket with readable dates and the status in the export, without author, case-insensitively on the key; an unknown key SHALL exit 1 saying it is absent from the cache. `check` without export and without key SHALL exit 1.

Source: tests/history_jira/test_history_jira.py (test_cle_affiche_la_suite_des_etats_sans_auteur, test_controle_sans_export_ni_cle)

#### Scenario: Known ticket
- **WHEN** the key of a cached ticket is given in lower case
- **THEN** the number of transitions and each "from -> to" line are printed, with no author and no ISO "T" separator

### Requirement: Check input validation
The system SHALL refuse the removed dormant-file option of `check` with exit 1 and a message pointing to the history-based dormant option of the flow report, SHALL refuse an export with non-English headers pointing to the API export, and SHALL stop with exit 1 when the export has no state column.

Source: tests/history_jira/test_history_jira.py (Controle)

#### Scenario: Removed option
- **WHEN** the removed option is given, in either language
- **THEN** exit 1, no traceback, and the message names the replacement

### Requirement: Message language
The system SHALL print messages in French by default and English with `--language en`, refuse other languages with exit 2, not keep the language between runs, accept the former option name with a warning, and produce English output matching the recorded reference without French words.

Source: tests/history_jira/test_language.py

#### Scenario: English output
- **WHEN** `--language en` is given
- **THEN** the output equals the English reference and contains no French

## Open questions

None.
