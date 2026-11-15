# jira-flow-history Specification

## Purpose

Describes the tool that collects the status history of tickets from the Jira API into a local cache (only date, starting status and arrival status of each transition), and checks that cache against an export. It also covers the shared history-reading rules (date normalisation, chronological sorting, segments, dormant tickets) used by the flow report. Sources are the tests in `tests/history_jira/`.

## Requirements

### Requirement: Connection test
The system SHALL provide a `test` subcommand that checks the connection to Jira and prints only "connexion OK" on success, or only the HTTP status code on failure (exit 1), never the site, account, token, cloud identifier or any name returned by Jira.

Source: tests/history_jira/test_history_jira.py (Connexion); tests/history_jira/test_jeton_scopes.py

#### Scenario: Credentials refused
- **WHEN** Jira answers 401
- **THEN** the output is the status code only, with no site, account or token, exit code 1

### Requirement: Connection test steps
In `test`, the system SHALL go through the cloud gateway with the cloud identifier of the settings, then probe each resource the tools read (design D19) and print the expiry lines of design D15.

Source: tests/history_jira/test_history_jira.py (Connexion); tests/history_jira/test_jeton_scopes.py

#### Scenario: Connection succeeds
- **WHEN** `test` runs with valid settings
- **THEN** the output holds the success text and one OK line per probed resource, and the exit code is 0

### Requirement: Connection settings checked before any call
Missing settings SHALL produce an error naming the missing setting, without printing any value of the settings. A non-secure remote site address SHALL be refused before any call.

Source: tests/history_jira/test_history_jira.py (Connexion); tests/history_jira/test_jeton_scopes.py

#### Scenario: Plain-HTTP site
- **WHEN** the site address is not HTTPS
- **THEN** the exit code is 1, the message mentions HTTPS and no call is made

### Requirement: Token read from the keychain
The token SHALL be read from the operating-system keychain; a missing token SHALL give a message without traceback. The system SHALL NOT print, log or write the token, and SHALL NOT retry a refused token.

Source: tests/history_jira/test_history_jira.py (Connexion); tests/history_jira/test_jeton_scopes.py

#### Scenario: Token lookup
- **WHEN** the token is read
- **THEN** the system asks the keychain for the generic password of the dedicated service, and prints a no-traceback message if it is not found

### Requirement: Scoped-token authentication sequence
The system SHALL send every authenticated request through the cloud gateway address built from the cloud identifier read in the settings (`jira_cloud_id`), with Basic authentication by account email and token, and SHALL NOT read the cloud identifier from the site in `export`, `collect` or `check`.

Source: tests/history_jira/test_jeton_scopes.py (SequenceScopes)

#### Scenario: Collection without tenant call
- **WHEN** `collect` runs
- **THEN** no call reads the site's tenant information, and every call goes to the gateway

### Requirement: Cloud identifier compared with the site in test
In `test` only, the system SHALL also read the site's cloud identifier without authentication and, when it differs from the settings, stop with exit code 1 and the mismatch key phrase of design D19 before any authenticated call.

Source: tests/history_jira/test_jeton_scopes.py (SequenceScopes)

#### Scenario: Full sequence
- **WHEN** `test` runs with valid settings
- **THEN** the first call reads the cloud identifier on the site without authentication, the following calls are authenticated through the gateway address built from the settings, and the output holds the success text

#### Scenario: Mismatch
- **WHEN** the site's cloud identifier differs from the settings
- **THEN** the output holds "cloudId differs from the site's", neither identifier is printed, no authenticated call is made, and the exit code is 1

### Requirement: Refused scoped token
A refused token SHALL print only the HTTP status code (exit 1), never the cloud identifier, the site, the account or the token, and SHALL NOT be retried.

Source: tests/history_jira/test_jeton_scopes.py (SequenceScopes)

#### Scenario: Token refused
- **WHEN** the gateway refuses the token
- **THEN** the output is the status code alone, with no cloud identifier, site, account, token or traceback, and no further call is made

### Requirement: Unusable cloud identifier
A missing, empty or unsafe cloud identifier in the settings (one that contains path characters) SHALL stop the run with exit 1 and a "cloudId introuvable" message, without traceback and before any authenticated call.

Source: tests/history_jira/test_jeton_scopes.py (SequenceScopes)

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
The system SHALL provide a `collect` subcommand that reads the tickets to query from the database and keeps per ticket only the status transitions as (date, starting status, arrival status), the add and remove events, as (date, added or removed, value or identifier), of fix versions, declared labels when configured, and delivery fields (jira-delivery-fields D2), and the current fix versions and declared labels.

Source: tests/history_jira (Collecte, test_collecte_etendue.py)

#### Scenario: Grouped mode
- **WHEN** the grouped history API is available, no label is declared and no fix version changed
- **THEN** each queried ticket gets its three-element transitions, the assignee change is dropped, and the console says the mode is grouped

#### Scenario: Export without key column
- **WHEN** `collect` is given an export file, with or without a key column
- **THEN** the exit code is 2, the output holds "export files are no longer read: the database is the only source", and Jira is not called

#### Scenario: Update date kept
- **WHEN** a stored ticket is queried
- **THEN** the collection writes no update date of its own: the updated instant used to select it next time is the one the export recorded and the import derived

#### Scenario: Sprint names discarded
- **WHEN** the changelog moves a ticket from one sprint to another, its `fromString` and `toString` carrying distinctive sprint names
- **THEN** the stored events hold the two sprint identifiers with their instant, and neither name is in the database or the output

### Requirement: Collection discards other fields and authors
In the history collection, changes to other fields and to undeclared labels SHALL be discarded and the author SHALL never be stored.

Source: tests/history_jira/test_history_jira.py (Collecte); tests/history_jira/test_collecte_etendue.py (in-memory store of tests/history_jira/aide_historique.py)

#### Scenario: Declared label events
- **WHEN** the changelog adds a declared label, adds an undeclared one and changes the fix version
- **THEN** the stored periods hold the declared label and the fix versions with their instants, and nothing about the undeclared label

### Requirement: Collection skips tickets past retention
In the history collection, tickets resolved longer ago than the retention period SHALL be skipped and counted with the key phrase of design D19 of the GDPR alignment.

Source: tests/history_jira/test_history_jira.py (Collecte)

#### Scenario: Ticket past the rule
- **WHEN** a stored ticket was resolved before the retention period
- **THEN** its history is not requested and the console prints "tickets past retention, skipped: 1"

### Requirement: Collection console without content
The console of the history collection SHALL report the mode, the tickets processed, the transition count and the error count, without ticket keys, team names, token, titles, labels, version names, site address or author.

Source: tests/history_jira/test_history_jira.py (Collecte); tests/history_jira/test_collecte_etendue.py

#### Scenario: Nothing sensitive written
- **WHEN** a collection ends
- **THEN** neither the console nor the database contains the token, the author, the author's address, a title, the assignee field name, the account address or an undeclared label

### Requirement: Pagination and fallback
The system SHALL follow pagination of the key search, of the grouped history (including a ticket split between two pages) and of the per-ticket history.

Source: tests/history_jira/test_history_jira.py (test_pagination_groupee, test_pagination_groupee_ticket_coupe_entre_deux_pages_et_recherche_paginee)

#### Scenario: Ticket split across pages
- **WHEN** the grouped response is cut in the middle of a ticket's history
- **THEN** the ticket's transitions are completed from the next page

### Requirement: Per-ticket fallback
The system SHALL fall back to a per-ticket mode when the grouped API is unavailable, and in that mode SHALL read until the last page, or until an empty page when the API gives no last-page indicator.

Source: tests/history_jira/test_history_jira.py (test_repli_ticket_par_ticket_avec_pagination, test_ticket_par_ticket_sans_islast_va_jusqu_a_la_page_vide)

#### Scenario: Fallback
- **WHEN** the grouped API answers 404
- **THEN** the console says the mode is ticket by ticket and every ticket has all its transitions

### Requirement: Incremental cache
The system SHALL query only the stored tickets without history, those not resolved, those updated since the last successful collection minus one day, and those whose not-found counter is above 0, leaving out the tickets marked gone (requirement "Ticket not found in Jira marked gone after consecutive collections"). A ticket without an updated instant SHALL NOT be queried again for that reason.

Source: tests/history_jira, test_history_jira.py (Collecte) and test_reinterrogation_maj.py

#### Scenario: Second collection
- **WHEN** one stored ticket is new, another is open, and the rest are resolved, already collected and not updated since
- **THEN** one search batch queries only those two tickets

#### Scenario: Finished ticket unchanged
- **WHEN** a resolved, collected ticket has an updated instant earlier than the last successful collection minus one day
- **THEN** no call is made for it and the report counts it as already collected

#### Scenario: Finished ticket updated
- **WHEN** a resolved, collected ticket has an updated instant later than the last successful collection minus one day, and Jira holds a new transition
- **THEN** it is queried again, the new transition is stored, and the report counts it among the resolved tickets queried again

#### Scenario: Older entry
- **WHEN** a resolved, collected ticket has no updated instant
- **THEN** it is not queried again for that reason

### Requirement: Last successful collection
The last successful collection SHALL be the latest history run whose error count is 0, whatever its not-found count (design D15). A history run with transient errors SHALL NOT move the instant used to select the updated tickets.

Source: tests/history_jira/test_reinterrogation_maj.py; amendment task 14.4 (run with errors not taken as the last successful collection)

#### Scenario: Run with transient errors
- **WHEN** a collection ends with one persistent 429, and a resolved ticket was updated between the last run without error and that collection
- **THEN** the next collection still selects the updated tickets from the instant of the last run without error, and queries that resolved ticket again

### Requirement: Incremental selection report and refresh
The system SHALL report how many stored tickets are skipped and how many will be queried, and, when the stored tickets hold updated instants, how many resolved tickets are queried again because they were updated; SHALL make no Jira call when none qualifies; and SHALL query every stored ticket with `--refresh`, gone tickets included, reporting it.

Source: tests/history_jira/test_history_jira.py (Collecte: test_rafraichir_interroge_tout); tests/history_jira/test_reinterrogation_maj.py

#### Scenario: Nothing to query
- **WHEN** every stored ticket is resolved, collected and not updated since the last collection
- **THEN** no Jira call is made

### Requirement: Team filter and scope exclusions
The system SHALL, with `--team`, keep a ticket as soon as any of its team columns (including values separated by semicolons) matches case-insensitively, and report only the count of tickets outside the team, never the name. An unknown team SHALL stop with exit 1 and no Jira call, without echoing the name.

Source: tests/history_jira/test_history_jira.py (test_equipe_filtre_et_ne_montre_pas_le_nom, test_equipe_retient_un_ticket_des_qu_une_de_ses_equipes_correspond, test_equipe_inconnue)

#### Scenario: Multi-team ticket
- **WHEN** the requested team appears in a second team column
- **THEN** the ticket is kept

### Requirement: Epics queried among the portfolio types
The tickets of the configured epic types SHALL be queried even when they are portfolio-level types (design D12 of the epic flow report change), and their count SHALL be printed on its own line with the key phrase "epics queried: {n}" (French "épics interrogés : {n}"). The epic line SHALL NOT name a key, a team or a type value.

Source: epic exception untested until implemented.

#### Scenario: Epics among the portfolio types
- **WHEN** the settings list epics and initiatives as portfolio types, epics as the epic type, and the export holds three epics and two initiatives of included projects
- **THEN** the three epics are queried, the two initiatives are not, and the console prints "epics queried: 3" with no key

### Requirement: Portfolio types and excluded projects not queried
Portfolio-level issue types and excluded projects from the settings SHALL NOT be queried, and their count SHALL be reported, with the one exception of requirement "Epics queried among the portfolio types". Tickets of an excluded project SHALL NOT be queried, epics included, and the other portfolio-level types SHALL stay unqueried.

Source: tests/history_jira/test_history_jira.py (test_portefeuille_et_projets_exclus_ne_sont_pas_interroges)

#### Scenario: Epic of an excluded project
- **WHEN** an epic belongs to an excluded project
- **THEN** it is not queried and is counted with the other excluded tickets

### Requirement: Rate limiting and errors
The system SHALL honor the retry delay supplied by Jira on HTTP 429 and retry; without such a delay it SHALL wait with doubling delays and give up after several attempts with the final status code.

Source: tests/history_jira/test_history_jira.py (test_429_*, test_attente_croissante_sans_retry_after)

#### Scenario: Transient throttling
- **WHEN** the first two calls answer 429 with a one-second delay
- **THEN** the system waits one second twice, then succeeds

### Requirement: Transient errors counted in a recorded run
Persistent throttling and the other transient errors SHALL count errors per status code in the report, exit 0, and record a history run holding that error count (design D15).

Source: tests/history_jira/test_history_jira.py (test_429_*)

#### Scenario: Persistent throttling
- **WHEN** every call answers 429
- **THEN** the report shows the errors with their code, exit code is 0, a history run is recorded with that error count, and no file is written

### Requirement: Access error stops the collection without writing
An access error (401, 403) SHALL stop the run with exit 1 and a message giving only the code, and SHALL write nothing to the database, no run and no counter included.

Source: tests/history_jira/test_history_jira.py (test_erreur_d_acces_arrete_et_n_ecrit_rien)

#### Scenario: Access refused during the collection
- **WHEN** Jira answers 403 during a collection
- **THEN** the exit code is 1, the message gives only the code, and nothing is written to the database, no run and no counter included

### Requirement: Ticket not found is not an error
A ticket not found SHALL NOT count among the errors: it gets no transition written, adds one to its not-found counter, and is counted in the not-found count of the run (requirement "Ticket not found in Jira marked gone after consecutive collections").

Source: tests/history_jira/test_history_jira.py (the former test_ticket_introuvable_compte_une_erreur_et_n_ecrit_pas_de_passage rewritten by amendment task 14.4)

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
The system SHALL provide a `check` subcommand that reads the database under the read-only role, makes no network call, and reports aggregated counts only, those of the scenario "Counts reported". The report SHALL contain no key, no team, no title.

Source: tests/history_jira/test_history_jira.py (Controle)

#### Scenario: Counts reported
- **WHEN** `check` runs on stored history
- **THEN** it reports: tickets without history, consistency between the last arrival status and the stored status (consistent, inconsistent, not comparable when there are no transitions), distribution of transitions per ticket in fixed buckets, delivered tickets without any transition, starting state of the first known transition, and number of delivered tickets passing through each segment (including "no segment")

#### Scenario: Aggregated counts
- **WHEN** the check runs on five delivered tickets plus one open ticket without history
- **THEN** it prints the count without history, the consistent/inconsistent/not-comparable counts and the transition distribution buckets, with no keys and no team name

#### Scenario: Unreadable dates
- **WHEN** the check reads the stored transitions
- **THEN** their instants are read as stored, no unreadable-date count is printed, and the flow report reads the same instants

### Requirement: Segment table shared by the check and the flow report
Segments SHALL come from the settings when set, otherwise from defaults, and the default table SHALL also place known workflow start and end states outside the computed segments. The flow report SHALL use the same segment table as the check.

Source: tests/history_jira/test_history_jira.py (Controle: test_flux_jira_et_controle_partagent_la_table_des_segments)

#### Scenario: Segments from settings
- **WHEN** the settings define a custom segment
- **THEN** the check reports delivered tickets per that segment

### Requirement: Check refusals
In `check`, an export file SHALL be refused with exit code 2 and the phrase of design D6; no stored history SHALL stop with exit code 1 and the phrase of design D6.

Source: tests/history_jira/test_history_jira.py (Controle: test_controle_sans_aucun_historique_stocke, test_fichier_d_export_refuse_avec_la_phrase_de_la_conception)

#### Scenario: No history
- **WHEN** no transition is stored
- **THEN** the output holds "no history in the database: run the history collection first" and the exit code is 1

### Requirement: Transitions to the same status counted apart
The system SHALL print in `check`, on its own line and as a number only, the transitions whose starting and arrival statuses have the same name (case and spaces ignored). They SHALL stay stored, and SHALL change neither the segments traversed nor the time per segment.

Source: tests/history_jira/test_history_jira.py (Controle: test_transitions_meme_statut_comptees_a_part_sans_nom_ni_cle, ..._ne_changent_ni_segments_ni_temps_par_segment)

#### Scenario: Open to Open
- **WHEN** a ticket history holds a transition from Open to Open
- **THEN** the check counts it on the same-status line, and the segments and time per segment equal those of the history without it

### Requirement: Transitions to the same status left out of the transitions per ticket
The system SHALL leave transitions whose starting and arrival statuses have the same name (case and spaces ignored, an empty status never counted) out of the distribution of transitions per ticket in `check`, for all tickets and for delivered tickets. The same-status line SHALL stay.

Source: tests/history_jira/test_history_jira.py (test_transitions_meme_statut_comptees_a_part_sans_nom_ni_cle)

#### Scenario: Only same-status transitions
- **WHEN** a ticket holds only a transition from Open to Open
- **THEN** it falls in the bucket 0, and the same-status line counts that transition

### Requirement: Inspect one ticket
The system SHALL provide `check --key <key>` that prints, from the database under the read-only role, the ordered list of status transitions of one ticket with readable dates and its stored status, without author, case-insensitively on the key; an unknown key SHALL exit 1 saying it is absent from the database. The command is run by the user alone.

Source: tests/history_jira/test_history_jira.py (test_cle_affiche_la_suite_des_etats_sans_auteur, fake reader of aide_historique.py)

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
The system SHALL accept on the collect subcommand an opt-in strict option. With it, when the error count of the run is above zero, the system SHALL print its usual report, write to the database exactly what it would write without the option, then print the key phrase of design D5 and exit with code 3. The key phrase SHALL NOT name a key, a team or a value.

Source: tests/history_jira/test_history_jira.py (test_strict_*)

#### Scenario: Persistent throttling with the option
- **WHEN** every call answers 429 and the collection runs with the strict option
- **THEN** the report shows the errors with their code, a history run is recorded with that error count, the output ends with "collection errors: history incomplete" in English, and the exit code is 3

#### Scenario: No error with the option
- **WHEN** the collection succeeds without any error
- **THEN** the exit code is 0 and the key phrase is not printed

### Requirement: Strict option leaves other exits unchanged
Not-found answers SHALL NOT count among the errors of the strict option (design D15): they alone SHALL NOT give exit code 3. An access error SHALL keep its current exit code 1. Without the option, the exit code and the output SHALL stay unchanged.

Source: tests/history_jira/test_history_jira.py (test_strict_*); amendment task 14.4 (not-found answers with the option)

#### Scenario: Not-found answers only, with the option
- **WHEN** the only failing ticket gets a not-found answer and the collection runs with the strict option
- **THEN** the key phrase is not printed and the exit code is 0

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
The system SHALL read the non-secret expiry date of the token from the settings (`jira_token_expires`) and, in `test`, print the expiry-soon key phrase with the number of days when the date is within a configurable number of days, the expiry-passed key phrase when the date has passed, and the not-set key phrase when the setting is absent. The system SHALL NOT read the expiry from the token or from Jira.

Source: tests/history_jira/test_jeton_scopes.py (SondeEtExpiration)

#### Scenario: Not set
- **WHEN** the setting is absent
- **THEN** the output holds "token expiry date not set"

### Requirement: Token expiry and exit code
The expiry lines SHALL NOT change the exit code of a successful test, except that a passed date with a refused call keeps exit code 1. An unreadable date SHALL stop with exit code 1 naming the setting, not the value.

Source: tests/history_jira/test_jeton_scopes.py (SondeEtExpiration)

#### Scenario: Expiry soon
- **WHEN** the date is ten days ahead and the warning period is longer
- **THEN** the output holds "API token expires in 10 days" and the exit code is 0

#### Scenario: Unreadable expiry date
- **WHEN** the expiry setting holds an unreadable date
- **THEN** the exit code is 1 and the message names the setting, not the value

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

### Requirement: Jira client allowlist checked before any call
The system SHALL check every request of the Jira client against the allowlist of design D1 before building the URL, before any retry and before any network call: GET only on the inventoried read paths, POST only on the ticket search path and the bulk changelog path. It SHALL refuse every other (method, path) pair without any call, and SHALL always refuse PUT, PATCH and DELETE.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Write method refused without a call
- **WHEN** the client is asked for PUT, PATCH, DELETE, HEAD or OPTIONS on a ticket path, against the live fake server
- **THEN** the refusal error is raised with the write phrase, the server's raw log is empty and no wait or retry occurs

#### Scenario: POST outside the two read paths
- **WHEN** the client is asked for POST on the ticket creation path, the field list path or a per-ticket changelog path
- **THEN** the request is refused with the write phrase and no byte reaches the server

### Requirement: Allowlist path and method matching
The system SHALL match the path argument alone, never the full URL, as a full match, and SHALL refuse a path holding a query, a fragment, an encoded character, a backslash, a double slash or a parent segment. It SHALL upper-case the method before the check and SHALL send that value. It SHALL NOT accept a method or a path by partial match.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Trap paths
- **WHEN** the client is asked for GET on a path with a parent segment, a query string, an encoded slash, a lower-case key, a double leading slash, a trailing slash or an empty path
- **THEN** each is refused without a call, with the read-outside-the-list phrase

#### Scenario: Lower-case method
- **WHEN** the client is asked for "get" on the field list path
- **THEN** the request passes and the server receives GET

### Requirement: Authentication column of the allowlist
The system SHALL allow the tenant-information path only on a client without authentication, and every API path only on an authenticated client. It SHALL NOT send the token to the site address.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Authentication mismatch
- **WHEN** a client without authentication asks for the field list, or an authenticated client asks for the tenant information
- **THEN** both are refused without a call, with the read-outside-the-list phrase

### Requirement: Allowlist exposed as data
The system SHALL expose the allowlist through a service function that returns its entries as data (method, path pattern, authentication required). The list SHALL hold only GET and POST entries, its POST entries SHALL be exactly the two read paths without variable part, and no pattern SHALL hold an open wildcard or an alternation. The system SHALL NOT add a command-line option for it.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Guard of the list
- **WHEN** the test reads the list
- **THEN** it holds the seven entries of design D1, every pattern compiles, and none matches a trap path

### Requirement: Refused request is a simple error with a fixed phrase
A refused request SHALL raise a simple error, never an HTTP error, and SHALL never be counted as a transient error. Its message SHALL be the fixed phrase of design D3 for its kind (write, or read outside the list) in the run language, naming only the method (or `?` when the method is not text). It SHALL NOT print the path, a key, the token or an argument value.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Write phrase in both languages
- **WHEN** a DELETE is refused
- **THEN** the message is "requête Jira refusée : écriture interdite (DELETE)" in French and "Jira request refused: write forbidden (DELETE)" in English, and holds neither the path nor the token

#### Scenario: Read-outside-the-list phrase in both languages
- **WHEN** a GET on a path outside the allowlist is refused, or an authenticated client asks for the tenant information
- **THEN** the message is "requête Jira refusée : hors de la liste des lectures permises (GET)" in French and "Jira request refused: outside the list of allowed reads (GET)" in English, and holds neither the path nor the token

### Requirement: Request options limited to parameters and body
The system SHALL accept as extra arguments of a client request only query parameters and a JSON body. Any other option SHALL be refused before any call with the option phrase of design D3, which names no value.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Form data on an allowed POST
- **WHEN** a POST on the ticket search path carries form data, files, a replaced authentication or extra headers
- **THEN** each is refused with "Jira request refused: option not allowed" and no byte reaches the server

### Requirement: Request paths stay in the callers
The request paths SHALL stay written in the calling functions; the allowlist SHALL only check them. The system SHALL NOT let a caller reach Jira other than through the client's request method.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Caller path checked
- **WHEN** a caller function is replaced by one that asks the client for a write path
- **THEN** the client refuses it, whatever the caller

### Requirement: Refusal exits with code 5
In `test` and `collect`, a refused request SHALL stop the run with exit code 5 (design D4) and print the fixed phrase in full, not only an error type name. The probe of `test` SHALL NOT swallow it. Exit code 5 SHALL be declared with the other exit codes of the tool and SHALL NOT be used for another cause.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Refusal during the connection test
- **WHEN** a probe step is replaced by a write request and `test` runs
- **THEN** the exit code is 5 and the output holds the fixed phrase

### Requirement: Refused collection writes nothing
In `collect`, a refused request SHALL write nothing to the database, no transition, counter or history run included. It SHALL NOT appear in the error count, and the strict option SHALL NOT turn it into exit code 3.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Refusal during the collection
- **WHEN** the reading of current values is replaced by a write request and `collect` runs, with or without the strict option
- **THEN** the exit code is 5, the output holds the fixed phrase, the fake store recorded nothing, no "errors" count replaces it, and the server received no write request

### Requirement: Gateway named by the client only
The system SHALL keep a static test over `tools/`, subfolders included, that fails when a file other than the client and its messages module names the Jira gateway or the tenant-information path in a string literal outside docstrings, or in shell text outside comments. API paths SHALL stay allowed in callers.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Gateway named elsewhere
- **WHEN** another file of `tools/` holds the gateway host in a string literal
- **THEN** the test fails and names the file

### Requirement: Declared table of HTTP importers
The static test SHALL read a declared table of the `tools/` files that import an HTTP library or call a download command (file, library, destination, reason). The table SHALL be the source: exactly one line, the client, SHALL go to Jira. The test SHALL fail on an importer missing from the table and on a table line whose file no longer imports any.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: New importer
- **WHEN** a file of `tools/` imports an HTTP library and is absent from the table
- **THEN** the test fails and names the file

#### Scenario: Dead table line
- **WHEN** a table line names a file that no longer imports an HTTP library, or no longer exists
- **THEN** the test fails and names the line

### Requirement: No bypass of the client
The static test SHALL fail when a file importing the client accesses its `requests` or `session` attribute.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Bypass of the client
- **WHEN** a file importing the client calls its HTTP library or its session directly
- **THEN** the test fails and names the file

### Requirement: Real probe of every Jira-calling subcommand
The system SHALL keep tests that run every subcommand calling Jira end to end against a local fake server that logs every request before any check. Every logged request SHALL be an allowlisted pair, no authenticated request SHALL leave the gateway, and at least one request SHALL be received. Remaining fakes SHALL be declared at the top of each test file.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: History subcommands
- **WHEN** `test`, `collect` in grouped mode, in per-ticket fallback, with pagination, with a throttled answer then success, and with declared labels run against the fake server
- **THEN** every logged request, retries included, is an allowlisted pair, and at least one request was received

### Requirement: Allowlist coverage by the probes
The union of the pairs seen by the probes of the history, export and story quality suites SHALL equal the allowlist. An entry seen by no probe SHALL fail the test and be named.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Dead entry
- **WHEN** an allowlist entry is seen by no probe of any suite
- **THEN** the coverage test fails and names the entry

### Requirement: Closed list of declared projects
The system SHALL give the Jira client the closed list of the declared projects of the product scope, read from the existing setting `scope_projects` of the flow configuration (design D8). The system SHALL NOT fall back on another setting, on a default list or on the projects seen in the database.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: List read from the setting
- **WHEN** the test configuration declares the fictitious projects PRJA and PRJB in `scope_projects`, and the fake store holds tickets of the fictitious project OTHER
- **THEN** the client's declared list is exactly PRJA and PRJB

### Requirement: No Jira call without a readable declared list
The system SHALL refuse to build the Jira client, and so to make any call to Jira, when `scope_projects` is absent, empty or unreadable, with exit code 6 and the missing-setting phrase of design D10, as for `forbidden_projects` (author's decision R-20261028-96). The guard SHALL NOT fall back on any list.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: No declared list
- **WHEN** the test configuration has no `scope_projects` setting and the client is built for a ticket search
- **THEN** the build is refused with "Jira request refused: setting missing, empty or unreadable (scope_projects)" in English, and the server's raw log is empty

#### Scenario: Empty declared list, even for the field list
- **WHEN** `scope_projects` is an empty list and a command asks only for the field list or the tenant information
- **THEN** the build is refused the same way and no request is sent

### Requirement: Ticket search restricted to the declared projects
The system SHALL refuse, before any call, every ticket search, GET or POST, whose JQL is not in the accepted form of design D8 (a leading project or key clause naming only declared projects, then optionally one parenthesised group joined by AND, then optionally an ORDER BY clause). It SHALL NOT accept any query that could widen the result beyond the declared projects. Excepted: the fixed version search of jira-delivery-fields D4.

Source: tests/history_jira/test_lecture_seule.py (to be written).

#### Scenario: Restricted query passes
- **WHEN** the declared list is the fictitious keys PRJA and PRJB, and the client is asked for a search with `project in (PRJA, PRJB) AND (status = Done) ORDER BY created`
- **THEN** the request reaches the server

#### Scenario: Unrestricted or widened queries refused
- **WHEN** the client is asked for a search with `status = Done`, with `project = PRJA OR project = OTHER`, with `project in (PRJA, OTHER)`, with `project = PRJA AND status = Done OR key = OTHER-1`, or with no `jql` value
- **THEN** each is refused with the scope phrase of design D10 and the server's raw log is empty

#### Scenario: Other forms refused
- **WHEN** the client is asked for a search with `NOT project = OTHER`, with `project in ()`, with `project = PRJA AND (status = Done) AND key = OTHER-1`, or with `project = PRJA AND (status = Done) OR (key = OTHER-1)`
- **THEN** each is refused with the scope phrase and the server's raw log is empty

#### Scenario: Key clause on declared projects
- **WHEN** the client is asked for a search with `key in (PRJA-1, PRJB-2)`, then with `key in (PRJA-1, OTHER-2)`
- **THEN** the first reaches the server and the second is refused with the scope phrase

#### Scenario: Version search in its fixed form only
- **WHEN** the version reference is the fictitious key VREF, and the client is asked for `project = VREF AND issuetype = "Version"`, then for `project = VREF`, then for `project = VREF AND issuetype = "Version" OR project = OTHER`
- **THEN** the first reaches the server, the two others are refused with the scope phrase and send nothing

#### Scenario: No version search without the setting
- **WHEN** the version reference setting is absent and the client is asked for `project = VREF AND issuetype = "Version"`
- **THEN** it is refused with the scope phrase and the server's raw log is empty

### Requirement: Ticket-addressed changelog requests restricted to the declared projects
The system SHALL refuse, before any call, a per-ticket changelog request whose ticket key does not belong to a declared project, and a bulk changelog request whose body names a ticket outside the declared projects or a ticket by a numeric identifier. It SHALL NOT send any part of such a request.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Changelog of an undeclared ticket
- **WHEN** the client is asked for the changelog of the fictitious ticket OTHER-1, or for a bulk changelog naming PRJA-1 and OTHER-1
- **THEN** both are refused with the scope phrase and the server's raw log is empty

### Requirement: Answer filtered to the declared projects
The system SHALL filter the answer of every ticket search inside the client, before it reaches the caller: a ticket whose key is missing, malformed or of an undeclared project SHALL be removed, and the client SHALL count the removed tickets. In the answer of the version search alone, a ticket of the reference project of type Version SHALL be kept; one of another type SHALL be removed and counted apart.

Source: tests/history_jira/test_lecture_seule.py (to be written).

#### Scenario: Planted ticket of another project
- **WHEN** the fake server answers a restricted search with two tickets of PRJA and one ticket of the fictitious project OTHER
- **THEN** the caller receives only the two PRJA tickets and the client's count is 1

#### Scenario: Ticket without a valid key
- **WHEN** the answer holds a ticket without a key and a ticket whose key is malformed
- **THEN** both are removed and counted

#### Scenario: Reference project ticket in an ordinary search
- **WHEN** the fake server answers a restricted search on PRJA with one PRJA ticket and one Version ticket of the fictitious reference project VREF
- **THEN** the caller receives only the PRJA ticket and the client's count is 1

### Requirement: Removed tickets leave no trace
The count of removed tickets SHALL be a number only. The system SHALL NOT print, log or store the key, the project or any field of a removed ticket.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Removed key in no output
- **WHEN** a ticket of OTHER is removed during `collect`
- **THEN** neither its key nor its project appears in the standard output, the error output or the fake store

### Requirement: Count line printed only above zero
A command that read tickets SHALL print the count line of design D9 when the count is above zero, and SHALL NOT print it when the count is zero.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Count line shown
- **WHEN** one ticket is removed during `collect`
- **THEN** the output holds "tickets outside the declared projects set aside: 1" in English and "tickets hors des projets déclarés écartés : 1" in French

#### Scenario: No ticket removed
- **WHEN** every ticket of the answer belongs to a declared project
- **THEN** the count is 0 and the command prints no count line

### Requirement: Linked tickets reduced to identifier and type
The system SHALL reduce, in every kept ticket of a search answer, each linked ticket to its identifier and its type (design D9), keeping the link's own type. It SHALL NOT return to the caller any other field of a linked ticket, its summary and status included, whatever the project of the linked ticket. A link to a forbidden project is removed instead.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Link to a ticket of another project
- **WHEN** the fake server answers with a PRJA ticket linked to the fictitious ticket OTHER-7, the linked ticket carrying a summary, a status and a priority
- **THEN** the caller receives the link with its type and, for OTHER-7, only its key and its type name; no summary, status or priority reaches the caller

### Requirement: Parent and sub-tasks reduced to identifier and type
The system SHALL reduce, in every kept ticket of a search answer, the parent and each sub-task to their identifier and their type, as for linked tickets (design D9; delegated decision R-20261028-94). It SHALL NOT return to the caller any other field of the parent or of a sub-task, their summary and status included, whatever their project. A parent or sub-task of a forbidden project is removed instead.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Parent and sub-task carrying other fields
- **WHEN** the fake server answers with a PRJA ticket whose parent OTHER-3 and sub-task PRJA-9 each carry a summary, a status and a priority
- **THEN** the caller receives, for OTHER-3 and PRJA-9, only their key and their type name

### Requirement: Scope refusal is a simple error
A scope refusal SHALL raise a simple error distinct from the allowlist refusal, never an HTTP error, and SHALL never be counted as a transient error.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Not a transient error
- **WHEN** a search is refused for scope during `collect`
- **THEN** no wait or retry occurs and the refusal is not in the "errors" count

### Requirement: Scope refusal phrases
The message of a scope refusal SHALL be one of the fixed phrases of design D10 in the run language. It SHALL NOT name a project, a key, a setting value or the query.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Scope phrase in both languages
- **WHEN** a search with `status = Done` is refused
- **THEN** the message is "requête Jira refusée : hors des projets déclarés du périmètre" in French and "Jira request refused: outside the declared scope projects" in English, and holds neither the query nor a key

#### Scenario: Missing declared list phrase in both languages
- **WHEN** the client is refused because `scope_projects` is absent, empty or unreadable
- **THEN** the message is "requête Jira refusée : réglage absent, vide ou illisible (scope_projects)" in French and "Jira request refused: setting missing, empty or unreadable (scope_projects)" in English, and holds no value of the setting

#### Scenario: Missing forbidden list phrase in both languages
- **WHEN** the client is refused because `forbidden_projects` is absent, empty or unreadable
- **THEN** the message is "requête Jira refusée : réglage absent, vide ou illisible (forbidden_projects)" in French and "Jira request refused: setting missing, empty or unreadable (forbidden_projects)" in English, and holds no value of the setting

#### Scenario: Forbidden project refused with the scope phrase
- **WHEN** a search naming the fictitious forbidden project SUPX is refused
- **THEN** the message is the scope phrase and holds neither SUPX nor the query

### Requirement: Scope refusal exits with code 6
In `test` and `collect`, a scope refusal SHALL stop the run with exit code 6 and print the fixed phrase in full. Exit code 6 SHALL be declared with the other exit codes of the tool and SHALL NOT be used for another cause.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Refusal during the connection test
- **WHEN** a probe step of `test` is replaced by a search with `status = Done`
- **THEN** the exit code is 6 and the output holds the scope phrase

#### Scenario: Missing forbidden list through a command
- **WHEN** `test` and `collect` run with a test configuration without `forbidden_projects`
- **THEN** each exits with code 6, prints the missing-setting phrase and the server's raw log is empty

### Requirement: Allowlist refusal wins over scope refusal
When a request is both outside the allowlist and outside the declared projects, the system SHALL give the allowlist refusal and its code 5, and SHALL NOT give the scope refusal.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Allowlist refusal wins
- **WHEN** a PUT is asked on the changelog path of OTHER-1
- **THEN** the write phrase is given and, through a command, the exit code is 5

### Requirement: Scope-refused collection writes nothing
In `collect`, a scope refusal SHALL write nothing to the database, no transition, counter or history run included. It SHALL NOT appear in the error count, and the strict option SHALL NOT turn it into exit code 3.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Scope refusal during the collection
- **WHEN** the collection is run with a declared list that does not hold the project of the tickets stored in the fake store, with or without the strict option
- **THEN** the exit code is 6, the output holds the scope phrase, the fake store recorded nothing and the server received no ticket request

### Requirement: Forbidden projects read from the configuration
The system SHALL read the list of forbidden projects from the setting `forbidden_projects` of the flow configuration, kept outside Git (design D11). The repository and its tests SHALL hold only fictitious forbidden keys; the system SHALL NOT hold a real forbidden key in code, tests or any tracked file.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Fictitious forbidden key in a test configuration
- **WHEN** a test configuration declares the fictitious project SUPX in `forbidden_projects`
- **THEN** the client's forbidden list is exactly SUPX

### Requirement: No Jira call without a readable forbidden list
The system SHALL refuse to build the Jira client, and so to make any call to Jira, when `forbidden_projects` is absent, empty or unreadable, with exit code 6 and the missing-setting phrase of design D10. The guard SHALL NOT switch itself off silently, and SHALL NOT fall back on a default list.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Setting absent
- **WHEN** the test configuration has no `forbidden_projects` and the client is built, even for the tenant information
- **THEN** the build is refused with the missing-setting phrase and the server's raw log is empty

#### Scenario: Empty list
- **WHEN** the test configuration has `forbidden_projects` as an empty list
- **THEN** the build is refused the same way and no request is sent

#### Scenario: Unreadable setting
- **WHEN** `forbidden_projects` is a text, a number or a list holding an empty or non-text entry
- **THEN** the build is refused the same way, and the message holds no value of the setting

### Requirement: Requests naming a forbidden project refused
The system SHALL refuse, before any call and with the scope phrase, every search whose JQL names a forbidden project or a key of it anywhere in the query, and every changelog request naming a ticket of a forbidden project. The refusal SHALL hold even when the project also appears in `scope_projects`.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Forbidden project inside the restricted group
- **WHEN** the declared list is PRJA, the forbidden list is SUPX, and the query is `project = PRJA AND (issue in linkedIssues(SUPX-1))`
- **THEN** the request is refused with the scope phrase and the server's raw log is empty

#### Scenario: Forbidden project also declared
- **WHEN** SUPX is both in `scope_projects` and in `forbidden_projects`, and the client is asked for `project = SUPX` or for the changelog of SUPX-1
- **THEN** both are refused with the scope phrase and no request is sent

### Requirement: Forbidden project removed from answers
The system SHALL remove from every search answer, before it reaches the caller, every ticket of a forbidden project, and every link, parent or sub-task that points to one, and SHALL count them in the count of tickets set aside. No key, field or reference of a forbidden project SHALL reach the caller.

Source: tests/history_jira/test_lecture_seule.py (to be written). Untested until implemented.

#### Scenario: Ticket and link of the forbidden project planted
- **WHEN** the fake server answers a restricted search with a PRJA ticket linked to SUPX-4 and whose parent is SUPX-2, plus a ticket SUPX-5
- **THEN** the caller receives the PRJA ticket without that link and without that parent, no SUPX key reaches the caller, and the count is 3

#### Scenario: Reference to a forbidden ticket in any string of any answer
- **WHEN** the fake server answers any readable 2xx request, whatever its nature (search, changelog, bulk changelog, field list), with a string holding a key of a forbidden project followed by digits (for example SUPX-12, in any case, anywhere in the string, at any depth), including a changelog item or a label or version name
- **THEN** the caller receives that string with each such reference replaced by the exact marker `[ticket-refusé]`, the effective replacements are added to the count of references replaced (a number, never a key), and no forbidden key reaches the caller; a digit sequence is replaced whatever follows it, and a key preceded by a letter, a digit or an underscore (another project) is left as it is

### Requirement: Delivery field events read from identifiers only
The system SHALL add the sprint and version asset fields of design D2 to the bulk changelog field list and read their events from the identifier columns only. Target and resolution versions SHALL be read as the bracketed `uuid:objectId` list of design D2, with no fallback. Periods SHALL be derived like the fix version periods. It SHALL NOT read `fromString` or `toString`, nor try another form.

#### Scenario: Sprint and target version in the field list
- **WHEN** `collect` sends the bulk changelog request
- **THEN** its `fieldIds` hold the sprint, target version and resolution version fields

#### Scenario: Bracketed list of asset identifiers
- **WHEN** the changelog of the target version goes from `[U:101]` to `[U:101, U:102]`, U being a fictitious 36-character hexadecimal identifier with hyphens, and its display strings carry distinctive labels
- **THEN** one event is stored, added, object identifier 102, and no label is in the database or the output

#### Scenario: Version history of a defect
- **WHEN** a defect ticket is collected and the changelog of its resolution version goes from `[U:101]` to `[U:102]`
- **THEN** one removed event for 101 and one added event for 102 are stored for the defect, and no event of its detection version, affected versions, detection phase, detected by or installed base is stored

#### Scenario: Element out of the pattern
- **WHEN** an element of a resolution version changelog does not match the pattern of design D2
- **THEN** it is not stored, the display strings are not read, and the output holds "unreadable changelog elements (target, resolution and epic versions): 1"

#### Scenario: Events counted
- **WHEN** a collection keeps two sprint events and one target version event
- **THEN** the output holds "delivery field events kept: 3" and no identifier

#### Scenario: Refresh after the migration
- **WHEN** a ticket was collected before the migration and `collect --refresh` runs
- **THEN** its delivery field events are stored, and a ticket past retention stays skipped

### Requirement: Epic version fields historised
The system SHALL historise the two epic version fields, read by the bracketed `uuid:objectId` rule of design D2 (R-20261102-61 (1) (a); form established for the first one by finding 1.1 v2), an element out of the pattern counted and set aside, the rest of the change kept (R-20261102-36). It SHALL NOT read their display strings, and SHALL NOT print a line naming an epic version kind.

#### Scenario: Epic version history collected
- **WHEN** an epic is collected and the changelog of its first epic version field goes from `[U:201]` to `[U:202]`, its display strings carrying distinctive labels
- **THEN** one removed event for 201 and one added event for 202 are stored under the kind `epic_a`, no label is in the database or the output, and the output holds no "history not collected" line

#### Scenario: Epic version element out of the pattern
- **WHEN** an element of the second epic version field's changelog does not match the pattern of design D2
- **THEN** it is not stored, the other elements of the change are kept under the kind `epic_b`, and the output holds "unreadable changelog elements (target, resolution and epic versions): 1"

#### Scenario: Both epic fields in the field list
- **WHEN** `collect` sends the bulk changelog request
- **THEN** its `fieldIds` hold the two epic version fields, and still none of the defect-only fields

## Open questions

None.
