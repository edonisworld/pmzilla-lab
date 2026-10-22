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
The system SHALL provide a `collect` subcommand that reads the tickets to query from the database and, for each ticket, keeps only the list of status transitions as (date, starting status, arrival status), the add and remove events of fix versions and, when declared labels are configured, of declared labels, as (date, added or removed, value), and the current fix versions and declared labels. Changes to other fields and to undeclared labels SHALL be discarded and the author SHALL never be stored. Tickets resolved longer ago than the retention period SHALL be skipped and counted with the key phrase of design D19 of the GDPR alignment. The console SHALL report the mode, the tickets processed, the transition count and the error count, without ticket keys, team names, token, titles, labels, version names, site address or author.

Source: tests/history_jira/test_history_jira.py (Collecte); tests/history_jira/test_collecte_etendue.py (in-memory store of tests/history_jira/aide_historique.py)

#### Scenario: Grouped mode
- **WHEN** the grouped history API is available, no label is declared and no fix version changed
- **THEN** each queried ticket gets its three-element transitions, the assignee change is dropped, and the console says the mode is grouped

#### Scenario: Declared label events
- **WHEN** the changelog adds a declared label, adds an undeclared one and changes the fix version
- **THEN** the stored periods hold the declared label and the fix versions with their instants, and nothing about the undeclared label

#### Scenario: Nothing sensitive written
- **WHEN** a collection ends
- **THEN** neither the console nor the database contains the token, the author, the author's address, a title, the assignee field name, the account address or an undeclared label

#### Scenario: Export without key column
- **WHEN** `collect` is given an export file, with or without a key column
- **THEN** the exit code is 2, the output holds "export files are no longer read: the database is the only source", and Jira is not called

#### Scenario: Ticket past the rule
- **WHEN** a stored ticket was resolved before the retention period
- **THEN** its history is not requested and the console prints "tickets past retention, skipped: 1"

#### Scenario: Update date kept
- **WHEN** a stored ticket is queried
- **THEN** the collection writes no update date of its own: the updated instant used to select it next time is the one the export recorded and the import derived

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
The system SHALL query only the stored tickets without history, those not resolved, those updated since the last successful collection minus one day, and those whose not-found counter is above 0, leaving out the tickets marked gone (requirement "Ticket not found in Jira marked gone after consecutive collections"). The last successful collection SHALL be the latest history run whose error count is 0, whatever its not-found count (design D15). The system SHALL report how many are skipped and how many will be queried, and, when the stored tickets hold updated instants, how many resolved tickets are queried again because they were updated; SHALL make no Jira call when none qualifies; and SHALL query every stored ticket with `--refresh`, gone tickets included, reporting it. A ticket without an updated instant SHALL NOT be queried again for that reason. A history run with transient errors SHALL NOT move the instant used to select the updated tickets.

Source: tests/history_jira/test_history_jira.py (Collecte: test_rafraichir_interroge_tout); tests/history_jira/test_reinterrogation_maj.py; amendment task 14.4 (run with errors not taken as the last successful collection)

#### Scenario: Second collection
- **WHEN** one stored ticket is new, another is open, and the rest are resolved, already collected and not updated since
- **THEN** one search batch queries only those two tickets

#### Scenario: Nothing to query
- **WHEN** every stored ticket is resolved, collected and not updated since the last collection
- **THEN** no Jira call is made

#### Scenario: Finished ticket unchanged
- **WHEN** a resolved, collected ticket has an updated instant earlier than the last successful collection minus one day
- **THEN** no call is made for it and the report counts it as already collected

#### Scenario: Finished ticket updated
- **WHEN** a resolved, collected ticket has an updated instant later than the last successful collection minus one day, and Jira holds a new transition
- **THEN** it is queried again, the new transition is stored, and the report counts it among the resolved tickets queried again

#### Scenario: Older entry
- **WHEN** a resolved, collected ticket has no updated instant
- **THEN** it is not queried again for that reason

#### Scenario: Run with transient errors
- **WHEN** a collection ends with one persistent 429, and a resolved ticket was updated between the last run without error and that collection
- **THEN** the next collection still selects the updated tickets from the instant of the last run without error, and queries that resolved ticket again

### Requirement: Team filter and scope exclusions
The system SHALL, with `--team`, keep a ticket as soon as any of its team columns (including values separated by semicolons) matches case-insensitively, and report only the count of tickets outside the team, never the name. An unknown team SHALL stop with exit 1 and no Jira call, without echoing the name. Portfolio-level issue types and excluded projects from the settings SHALL NOT be queried, and their count SHALL be reported, with one exception (design D12 of the epic flow report change): the tickets of the configured epic types SHALL be queried even when they are portfolio-level types, and their count SHALL be printed on its own line with the key phrase "epics queried: {n}" (French "épics interrogés : {n}"). Tickets of an excluded project SHALL NOT be queried, epics included, and the other portfolio-level types SHALL stay unqueried. The epic line SHALL NOT name a key, a team or a type value.

Source: tests/history_jira/test_history_jira.py (test_equipe_filtre_et_ne_montre_pas_le_nom, test_equipe_retient_un_ticket_des_qu_une_de_ses_equipes_correspond, test_equipe_inconnue, test_portefeuille_et_projets_exclus_ne_sont_pas_interroges); epic exception untested until implemented.

#### Scenario: Multi-team ticket
- **WHEN** the requested team appears in a second team column
- **THEN** the ticket is kept

#### Scenario: Epics among the portfolio types
- **WHEN** the settings list epics and initiatives as portfolio types, epics as the epic type, and the export holds three epics and two initiatives of included projects
- **THEN** the three epics are queried, the two initiatives are not, and the console prints "epics queried: 3" with no key

#### Scenario: Epic of an excluded project
- **WHEN** an epic belongs to an excluded project
- **THEN** it is not queried and is counted with the other excluded tickets

### Requirement: Rate limiting and errors
The system SHALL honor the retry delay supplied by Jira on HTTP 429 and retry; without such a delay it SHALL wait with doubling delays and give up after several attempts with the final status code. Persistent throttling and the other transient errors SHALL count errors per status code in the report, exit 0, and record a history run holding that error count (design D15). An access error (401, 403) SHALL stop the run with exit 1 and a message giving only the code, and SHALL write nothing to the database, no run and no counter included. A ticket not found SHALL NOT count among the errors: it gets no transition written, adds one to its not-found counter, and is counted in the not-found count of the run (requirement "Ticket not found in Jira marked gone after consecutive collections").

Source: tests/history_jira/test_history_jira.py (test_429_*, test_attente_croissante_sans_retry_after, test_erreur_d_acces_arrete_et_n_ecrit_rien; the former test_ticket_introuvable_compte_une_erreur_et_n_ecrit_pas_de_passage rewritten by amendment task 14.4)

#### Scenario: Transient throttling
- **WHEN** the first two calls answer 429 with a one-second delay
- **THEN** the system waits one second twice, then succeeds

#### Scenario: Persistent throttling
- **WHEN** every call answers 429
- **THEN** the report shows the errors with their code, exit code is 0, a history run is recorded with that error count, and no file is written

#### Scenario: Ticket not found
- **WHEN** Jira answers not found for one of two tickets and the other is answered normally
- **THEN** the report shows no error with code 404 but "tickets not found in Jira: 1", the second ticket's history is stored, and the history run holds an error count of 0 and a not-found count of 1

### Requirement: Date normalisation and chronological order
The system SHALL read transition dates from Jira as instants with offset; a millisecond or second epoch value (number or digit text) SHALL be converted to a UTC instant; an unreadable value SHALL NOT be stored as a transition; empty becomes none. Transitions SHALL be sorted by instant, not by text, regardless of the API order or offsets.

Source: tests/history_jira/test_history_jira.py (NormaliserDate, Tri, DatesDeLaCollecte)

#### Scenario: Mixed offsets
- **WHEN** a history has an entry at 09:00 with a positive two-hour offset and another at 08:00 UTC
- **THEN** the first one is ordered before the second

#### Scenario: Old numeric cache
- **WHEN** Jira returns a transition date as epoch milliseconds
- **THEN** it is stored as the matching UTC instant, and the key inspection prints a readable date

### Requirement: Dormant tickets from history
The system SHALL compute dormant tickets from the history as tickets not finished, created at least a threshold number of days ago, with no status change for at least that many days (last transition date, or creation date if none). A ticket without history (not yet collected) SHALL NOT be dormant and SHALL be counted separately.

Source: tests/history_jira/test_history_jira.py (test_dormants_selon_l_historique_sans_format_de_csv)

#### Scenario: Unknown history
- **WHEN** one old ticket has a long-ago transition, one recent ticket has none, and one old ticket has no history
- **THEN** only the first is dormant and one ticket is counted as without history

### Requirement: Cache check
The system SHALL provide a `check` subcommand that reads the database under the read-only role, makes no network call, and reports aggregated counts only: tickets without history, consistency between the last arrival status and the stored status (consistent, inconsistent, not comparable when there are no transitions), distribution of transitions per ticket in fixed buckets, delivered tickets without any transition, starting state of the first known transition, and number of delivered tickets passing through each segment (including "no segment"). The report SHALL contain no key, no team, no title. Segments SHALL come from the settings when set, otherwise from defaults, and the default table SHALL also place known workflow start and end states outside the computed segments. The flow report SHALL use the same segment table as the check. An export file SHALL be refused with exit code 2 and the phrase of design D6; no stored history SHALL stop with exit code 1 and the phrase of design D6.

Source: tests/history_jira/test_history_jira.py (Controle: test_controle_sans_aucun_historique_stocke, test_fichier_d_export_refuse_avec_la_phrase_de_la_conception, test_flux_jira_et_controle_partagent_la_table_des_segments)

#### Scenario: Aggregated counts
- **WHEN** the check runs on five delivered tickets plus one open ticket without history
- **THEN** it prints the count without history, the consistent/inconsistent/not-comparable counts and the transition distribution buckets, with no keys and no team name

#### Scenario: Unreadable dates
- **WHEN** the check reads the stored transitions
- **THEN** their instants are read as stored, no unreadable-date count is printed, and the flow report reads the same instants

#### Scenario: Segments from settings
- **WHEN** the settings define a custom segment
- **THEN** the check reports delivered tickets per that segment

#### Scenario: No history
- **WHEN** no transition is stored
- **THEN** the output holds "no history in the database: run the history collection first" and the exit code is 1

### Requirement: Inspect one ticket
The system SHALL provide `check --key <key>` that prints, from the database under the read-only role, the ordered list of status transitions of one ticket with readable dates and its stored status, without author, case-insensitively on the key; an unknown key SHALL exit 1 saying it is absent from the database. The command is run by the user alone.

Source: tests/history_jira/test_history_jira.py (test_cle_affiche_la_suite_des_etats_sans_auteur, through the fake reader of tests/history_jira/aide_historique.py)

#### Scenario: Known ticket
- **WHEN** the key of a stored ticket is given in lower case
- **THEN** the number of transitions and each "from -> to" line are printed, with no author and no ISO "T" separator

### Requirement: Check input validation
The system SHALL refuse the removed dormant-file option of `check` with exit 1 and a message pointing to the history-based dormant option of the flow report.

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
The system SHALL accept on the collect subcommand an opt-in strict option. With it, when the error count of the run is above zero, the system SHALL print its usual report, write to the database exactly what it would write without the option, then print the key phrase of design D5 and exit with code 3. Not-found answers SHALL NOT count among these errors (design D15): they alone SHALL NOT give exit code 3. The key phrase SHALL NOT name a key, a team or a value. An access error SHALL keep its current exit code 1. Without the option, the exit code and the output SHALL stay unchanged.

Source: tests/history_jira/test_history_jira.py (test_strict_*); amendment task 14.4 (not-found answers with the option)

#### Scenario: Persistent throttling with the option
- **WHEN** every call answers 429 and the collection runs with the strict option
- **THEN** the report shows the errors with their code, a history run is recorded with that error count, the output ends with "collection errors: history incomplete" in English, and the exit code is 3

#### Scenario: Not-found answers only, with the option
- **WHEN** the only failing ticket gets a not-found answer and the collection runs with the strict option
- **THEN** the key phrase is not printed and the exit code is 0

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

### Requirement: History written in one transaction, no cache file
The system SHALL connect as the import role before any Jira call (design D2) and write in one transaction: new transitions (never duplicated), has-history flags, periods (design D5), not-found counters and gone instants, and one history run with its error and not-found counts, errors or not (design D15). It SHALL roll back on an access or database error, refuse an export file (exit 2), and print the summary of design D6. It SHALL NOT use a cache file or skip the run because of errors.

#### Scenario: Collection written
- **WHEN** a collection runs against a fake Jira server on a disposable database holding three tickets
- **THEN** their transitions, flags and periods are stored, a history run with an error count of 0 and a not-found count of 0 is recorded, and no file appears in the history folder

#### Scenario: Collection with errors
- **WHEN** a collection of three tickets gets one persistent 429 and one not-found answer
- **THEN** the third ticket's history is stored, and a history run is recorded with an error count of 1 and a not-found count of 1

#### Scenario: Export file given
- **WHEN** `collect` is given an export file
- **THEN** the output holds "export files are no longer read: the database is the only source", the exit code is 2, and Jira is not called

#### Scenario: Empty database
- **WHEN** the database holds no ticket
- **THEN** the output holds "no ticket in the database: run the export and the import first" and the exit code is 1

### Requirement: Ticket not found in Jira marked gone after consecutive collections
The system SHALL tell a not-found answer (HTTP 404) from a transient error and count per ticket the consecutive not-found collections (design D15): plus one on a 404, reset with the gone instant cleared on a normal answer, unchanged on a transient error. At `history_not_found_limit` (default 3), the ticket SHALL be marked gone and not queried, except with `--refresh` or after the import cleared the mark. It SHALL NOT mark a ticket gone before the limit, delete it, or print its key.

#### Scenario: Not found below the limit
- **WHEN** the limit is 3 and a stored ticket gets a not-found answer at two consecutive collections
- **THEN** its counter is 2, it has no gone instant, it is queried again at the next collection, and each output holds "tickets not found in Jira: 1"

#### Scenario: Limit reached
- **WHEN** the limit is 3 and the same ticket gets a not-found answer at a third consecutive collection
- **THEN** it gets the collection instant as gone instant, the output holds "tickets not found in Jira, now marked gone: 1", and the next collection makes no call for it and prints "tickets marked gone, not queried: 1"

#### Scenario: Transient error between two not-found answers
- **WHEN** a ticket gets a not-found answer, then a persistent 429 at the next collection, then a not-found answer
- **THEN** its counter is 2 after the third collection: the transient error neither added to it nor reset it

#### Scenario: Ticket found again
- **WHEN** a ticket with a counter of 2 is answered normally
- **THEN** its counter is 0 and its transitions are stored

#### Scenario: Refresh queries gone tickets
- **WHEN** `--refresh` is given and a gone ticket is answered normally
- **THEN** its gone instant is cleared, its counter is 0, and the output holds "tickets marked gone found again: 1"

#### Scenario: Gone ticket cleared by the import
- **WHEN** a gone ticket lost its mark because the export sighted it again and the import ran
- **THEN** the next collection queries it, and a not-found answer sets its counter to 1

#### Scenario: Limit from the settings
- **WHEN** the settings set the limit to 1 and a ticket gets one not-found answer
- **THEN** it is marked gone at that collection

## Open questions

None.
