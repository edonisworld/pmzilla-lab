# jira-flow-history Specification

## Purpose

Describes the tool that collects the status history of tickets from the Jira API into a local cache (only date, starting status and arrival status of each transition), and checks that cache against an export. It also covers the shared history-reading rules (date normalisation, chronological sorting, segments, dormant tickets) used by the flow report. Sources are the tests in `tests/history_jira/`.

## Requirements

### Requirement: Connection test
The system SHALL provide a `test` subcommand that checks the connection to Jira and prints only "connexion OK" on success, or only the HTTP status code on failure (exit 1), never the site, account, token, cloud identifier or any name returned by Jira. It SHALL go through the cloud gateway with the cloud identifier of the settings, then probe each resource the tools read (design D19) and print the expiry lines of design D15. Missing settings SHALL produce an error naming the missing setting, without printing any value of the settings. A non-secure remote site address SHALL be refused before any call. The token SHALL be read from the operating-system keychain; a missing token SHALL give a message without traceback. The system SHALL NOT print, log or write the token, and SHALL NOT retry a refused token.

Source: tests/history_jira/test_history_jira.py (Connexion); tests/history_jira/test_jeton_scopes.py

#### Scenario: Connection succeeds
- **WHEN** `test` runs with valid settings
- **THEN** the output holds the success text and one OK line per probed resource, and the exit code is 0

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
The system SHALL send every authenticated request through the cloud gateway address built from the cloud identifier read in the settings (`jira_cloud_id`), with Basic authentication by account email and token, and SHALL NOT read the cloud identifier from the site in `export`, `collect` or `check`. In `test` only, it SHALL also read the site's cloud identifier without authentication and, when it differs from the settings, stop with exit code 1 and the mismatch key phrase of design D19 before any authenticated call. A refused token SHALL print only the HTTP status code (exit 1), never the cloud identifier, the site, the account or the token, and SHALL NOT be retried. A missing, empty or unsafe cloud identifier in the settings (one that contains path characters) SHALL stop the run with exit 1 and a "cloudId introuvable" message, without traceback and before any authenticated call.

Source: tests/history_jira/test_jeton_scopes.py (SequenceScopes)

#### Scenario: Full sequence
- **WHEN** `test` runs with valid settings
- **THEN** the first call reads the cloud identifier on the site without authentication, the following calls are authenticated through the gateway address built from the settings, and the output holds the success text

#### Scenario: Collection without tenant call
- **WHEN** `collect` runs
- **THEN** no call reads the site's tenant information, and every call goes to the gateway

#### Scenario: Mismatch
- **WHEN** the site's cloud identifier differs from the settings
- **THEN** the output holds "cloudId differs from the site's", neither identifier is printed, no authenticated call is made, and the exit code is 1

#### Scenario: Token refused
- **WHEN** the gateway refuses the token
- **THEN** the output is the status code alone, with no cloud identifier, site, account, token or traceback, and no further call is made

#### Scenario: Unusable cloud identifier
- **WHEN** the settings hold no cloud identifier, an empty one, or one containing a path
- **THEN** the exit code is 1, the message says the cloud identifier was not found, and no authenticated call is made

### Requirement: Former names
The system SHALL refuse former option names with exit code 2, and former setting names and former setting values with a non-zero exit code, each with a message naming the current name and without any call to Jira; it SHALL refuse former subcommand names with exit code 2 without any call to Jira, and SHALL cite the new setting name in missing-setting messages.

Source: tests/history_jira/test_history_jira.py (AnciensNoms)

#### Scenario: Former options
- **WHEN** a former name of the team, refresh or key option is used
- **THEN** the exit code is 2, the message says the option no longer exists and names the current one, and Jira is not called

#### Scenario: New names
- **WHEN** only new names are used
- **THEN** no warning is printed

### Requirement: History collection keeps only date and states
The system SHALL provide a `collect` subcommand that reads one or more export CSV files, merges the tickets by key, and for each ticket stores in the cache only a finished flag, the resolution date, the last date the ticket was seen in an export, the list of status transitions as (date, starting status, arrival status), the add and remove events of fix versions and, when declared labels are configured, of declared labels, as (date, added or removed, value). Changes to other fields and to undeclared labels SHALL be discarded and the author SHALL never be stored. Tickets resolved longer ago than the retention period SHALL be skipped and counted with the key phrase of design D19. The console SHALL report the mode, the tickets processed, the transition count and the error count, without ticket keys, team names, token, titles, labels, version names, site address or author.

Source: tests/history_jira/test_history_jira.py (Collecte); tests/history_jira/test_collecte_etendue.py

#### Scenario: Grouped mode
- **WHEN** the grouped history API is available, no label is declared and no fix version changed
- **THEN** each cache entry holds the finished flag, the two dates and its three-element transitions, the assignee change is dropped, and the console says the mode is grouped

#### Scenario: Declared label events
- **WHEN** the changelog adds a declared label, adds an undeclared one and changes the fix version
- **THEN** the entry holds the declared-label add and the fix-version remove and add with their instants, and nothing about the undeclared label

#### Scenario: Nothing sensitive written
- **WHEN** a collection ends
- **THEN** neither the console nor any file written contains the token, the author, the author's address, a title, the assignee field name, the account address or an undeclared label

#### Scenario: Export without key column
- **WHEN** the export has no key column
- **THEN** the exit code is 1 and the message mentions the key column

#### Scenario: Ticket past the rule
- **WHEN** an export row was resolved before the retention period
- **THEN** its history is not requested and the console prints "tickets past retention, skipped: 1"

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
The system SHALL print messages in French by default and English with `--language en`, refuse other languages with exit 2, not keep the language between runs, refuse the former option name with exit 2 naming the current one, and produce English output matching the recorded reference without French words.

Source: tests/history_jira/test_language.py

#### Scenario: English output
- **WHEN** `--language en` is given
- **THEN** the output equals the English reference and contains no French

### Requirement: Strict option for collection errors
The system SHALL accept on the collect subcommand an opt-in strict option. With it, when the error count of the run is above zero, the system SHALL print its usual report, leave the cache exactly as it would without the option, then print the key phrase of design D5 and exit with code 3. The key phrase SHALL NOT name a key, a team or a value. An access error SHALL keep its current exit code 1. Without the option, the exit code and the output SHALL stay unchanged.

Source: tests/history_jira

#### Scenario: Persistent throttling with the option
- **WHEN** every call answers 429 and the collection runs with the strict option
- **THEN** the report shows the errors with their code, no cache file exists, the output ends with "collection errors: history incomplete" in English, and the exit code is 3

#### Scenario: No error with the option
- **WHEN** the collection succeeds without any error
- **THEN** the exit code is 0 and the key phrase is not printed

#### Scenario: Without the option
- **WHEN** every call answers 429 and the option is not given
- **THEN** the exit code is 0, as before this change

### Requirement: Scoped token only
The system SHALL use the scoped-token mode when the token-type setting is absent, and SHALL refuse the classic value with exit code 1 and the classic-token key phrase of design D19, before reading the keychain and before any call, in every subcommand that calls Jira (and in the export, which uses the same client). The system SHALL NOT call the site address with an authenticated request.

Source: tests/history_jira/test_jeton_scopes.py; tests/export_jira_api/test_export_jira_api.py

#### Scenario: Classic setting
- **WHEN** the token type is set to classic and `test` runs
- **THEN** the output holds "classic token refused: use a scoped token", the keychain is not read, no call is made, and the exit code is 1

#### Scenario: Setting absent
- **WHEN** the token type is not set
- **THEN** the gateway address is used

### Requirement: Resource probe
The system SHALL, in `test`, make one read request per resource the tools use (ticket search, history, field list), each limited to one result, and print one line per resource with OK or the HTTP status code, following design D19. The exit code SHALL be 1 when any resource fails. The probe SHALL NOT print a value returned by Jira, a key or a field name.

Source: tests/history_jira/test_jeton_scopes.py (SondeEtExpiration)

#### Scenario: Missing scope
- **WHEN** the history request answers 403 and the others succeed
- **THEN** the output holds "access history: 403" and the OK lines of the other resources, and the exit code is 1

### Requirement: Token expiry warning
The system SHALL read the non-secret expiry date of the token from the settings (`jira_token_expires`) and, in `test`, print the expiry-soon key phrase with the number of days when the date is within a configurable number of days, the expiry-passed key phrase when the date has passed, and the not-set key phrase when the setting is absent. The expiry lines SHALL NOT change the exit code of a successful test, except that a passed date with a refused call keeps exit code 1. The system SHALL NOT read the expiry from the token or from Jira. An unreadable date SHALL stop with exit code 1 naming the setting, not the value.

Source: tests/history_jira/test_jeton_scopes.py (SondeEtExpiration)

#### Scenario: Expiry soon
- **WHEN** the date is ten days ahead and the warning period is longer
- **THEN** the output holds "API token expires in 10 days" and the exit code is 0

#### Scenario: Not set
- **WHEN** the setting is absent
- **THEN** the output holds "token expiry date not set"

## Open questions

None.
