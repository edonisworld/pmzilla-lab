# jira-flow-export Specification

## Purpose

Describes the command-line tool that exports tickets from the Jira API into a CSV file in the same layout as a manual Jira export, so that the flow and dependency reports read it unchanged. The tool never asks Jira for titles, descriptions or individual data. Sources are the tests in `tests/export_jira_api/`.

## Requirements

### Requirement: Subcommands and retired subcommands
The system SHALL offer the subcommands `diagnose`, `fields` and `export`, and SHALL refuse the retired subcommands `compare` and `teams-table` (and the former French subcommand names) with exit code 2, without a traceback, without calling Jira, and with a message that points to the replacement path.

Source: tests/export_jira_api/test_export_jira_api.py (SousCommandesRetirees, AnciensNoms)

#### Scenario: Retired subcommand
- **WHEN** the user runs `compare` or `teams-table`
- **THEN** the exit code is 2, the message says the subcommand is retired and names the replacement (the export subcommand and the comparison tool, or the hand-written team table), and no request reaches Jira

#### Scenario: Help
- **WHEN** the user asks for help
- **THEN** only `diagnose`, `fields` and `export` are listed

#### Scenario: Former option and setting names
- **WHEN** a former option name (for example the French search or output option) or a former setting name is used
- **THEN** it is refused (exit code 2 for an option, non-zero for a setting) with a message naming the current name, no file is written and Jira is not called; former subcommand names are refused with exit code 2

### Requirement: Dates in a configurable time zone
The system SHALL convert every exported date to a configurable time zone, with a default zone applying daylight saving, and SHALL stop before any call to Jira when the configured zone is invalid.

Source: tests/export_jira_api/test_export_jira_api.py (FuseauExport)

#### Scenario: Default zone
- **WHEN** a summer UTC timestamp is exported without a zone setting
- **THEN** it is written with the summer offset of the default zone; a winter timestamp with the winter offset

#### Scenario: Invalid zone
- **WHEN** the zone setting is unknown
- **THEN** the exit code is 1, the message names the setting, no file is written and Jira is not called

### Requirement: Updated column
The system SHALL always request the updated date and record it in each snapshot as an instant, and SHALL record no instant when Jira returns none.

Source: tests/export_jira_api/test_export_jira_api.py (ColonneUpdated)

#### Scenario: Updated written
- **WHEN** a ticket has an updated date
- **THEN** its snapshot holds that instant, converted from the export time zone

### Requirement: Complete pagination
The system SHALL follow the page token of the search API until the last page, and SHALL stop (not loop) when the API returns the same token repeatedly.

Source: tests/export_jira_api/test_export_jira_api.py (test_pagination_complete, test_jeton_de_page_qui_se_repete_ne_boucle_pas)

#### Scenario: One ticket per page
- **WHEN** the API pages one ticket at a time
- **THEN** all tickets are exported and the next-page token of each request is the one returned by the previous response

#### Scenario: Repeated token
- **WHEN** the API keeps returning the same page token
- **THEN** the export ends successfully after the second request

### Requirement: No sensitive field requested or printed
The system SHALL NOT request titles, assignee, reporter, creator, description, comments, labels, fix versions or any other user field (the PO in charge included, design D3 of the GDPR alignment) from Jira, SHALL write no title, no label, no version and no person into the database, and SHALL NOT print the token, the site address, the cloud identifier, ticket keys, team labels, labels, version names or the query to the console. The console SHALL report the ticket and page counts.

Source: tests/export_jira_api/test_export_jira_api.py (test_aucun_titre_demande_a_jira_et_rien_de_sensible_en_sortie); tests/export_jira_api/test_garde_champs.py; tests/export_jira_api/test_export_jira_api.py (NouveauxComportements.test_champs_demandes_sans_etiquette_ni_version); tests/export_jira_api/test_couche_brute.py (test_aucun_texte_de_ticket_dans_les_instantanes)

#### Scenario: Console and file content
- **WHEN** an export succeeds
- **THEN** the requested field list contains none of the forbidden fields, no file is written, and neither the output nor the snapshots contain the secret title or the token

#### Scenario: Labels not configured
- **WHEN** declared labels are not configured
- **THEN** the requested field list contains neither the labels field nor any user field

#### Scenario: No user field with every setting
- **WHEN** an export runs with every supported optional setting present, declared labels included
- **THEN** the requested field list contains no comment, summary, description, creator, reporter, assignee, labels, fix versions or other user field

### Requirement: Access errors show only the status code
The system SHALL, when Jira rejects the request, print only the HTTP status code and exit with code 1.

Source: tests/export_jira_api/test_export_jira_api.py (Export, Champs: test_erreur_d_acces_ne_montre_que_le_code)

#### Scenario: Unauthorized
- **WHEN** the credentials are refused
- **THEN** the output is the status code alone and the exit code is 1

### Requirement: Named export queries
The system SHALL read the export queries from the settings either as one query or as a mapping of names to queries; the mapping SHALL take precedence. Without `--query`, the system SHALL run every named query in one run of the raw layer. With `--query <name>`, it SHALL run only that query, and that run SHALL NOT count as a complete set for the out-of-export mark. The run SHALL NOT record a query name. Invalid names, empty queries or a non-mapping value SHALL stop with exit code 1 before calling Jira.

Source: tests/export_jira_api/test_export_jira_api.py (RequetesNommees); tests/export_jira_api/test_couche_brute.py (PassageEtVisites: test_premier_export_de_deux_requetes_nommees, test_une_seule_requete_n_est_pas_toutes_les_requetes)

#### Scenario: All queries
- **WHEN** two named queries are configured and export runs without options
- **THEN** one run holds the sightings of both queries with identical time zone and team handling, and the console lines are prefixed with the query name

#### Scenario: Unknown query name
- **WHEN** the requested name is not configured
- **THEN** the exit code is 1, the available names are listed, and Jira is not called

#### Scenario: No query configured
- **WHEN** no query is configured
- **THEN** export stops with exit code 1 and names the missing setting, without calling Jira

#### Scenario: Diagnose uses the first query
- **WHEN** `diagnose` runs with several named queries
- **THEN** only the first query is sent

### Requirement: Team field as labels
The system SHALL read the team field when it is configured and record the teams of each ticket in its snapshot, in API order. When no team field is configured, it SHALL record no team and SHALL NOT request the field. The team header setting (`export_team_header`) SHALL be accepted and ignored, like the verification settings (requirement "Optional verification column"): no column, file or message uses it, and it SHALL NOT stop the export or `check-teams` (design D13).

Source: tests/export_jira_api/test_export_jira_api.py (Export, ChampEquipeIllisible); amendment task 14.1 (header setting accepted and ignored)

#### Scenario: No team field
- **WHEN** no team field is set
- **THEN** the team field is not requested and no snapshot holds a team

#### Scenario: Identifier alone is not a label
- **WHEN** a field value is a bare number, a UUID, or an object holding only a numeric value
- **THEN** it is not accepted as a label, whereas values with a value or name property, or plain strings, are

#### Scenario: Team header setting present
- **WHEN** the flow settings hold the team header setting and the export, then `check-teams`, run
- **THEN** both run as without it, and no output names the setting or its value

### Requirement: Optional verification column
The system SHALL accept the verification field and verification header settings and SHALL ignore them: the verification field SHALL NOT be requested from Jira, nothing of it SHALL be recorded, and no message SHALL name it (decision Q7 (b) of the database-only change: no reader uses it). An identifier that is not a field identifier SHALL NOT stop the export.

Source: tests/export_jira_api/test_export_jira_api.py (ChampVerification)

#### Scenario: Column present
- **WHEN** the setting is present and Jira would return values for the field
- **THEN** the field is not in the requested field list and no snapshot holds its value

#### Scenario: Invalid identifier
- **WHEN** the identifier contains spaces
- **THEN** the export runs with exit code 0 and the output does not name the setting

### Requirement: Optional story points column
The system SHALL, when a points field identifier or list of identifiers is configured, write a "story points" column after the updated column and before the team columns, taking the first non-empty numeric value in list order; non-numeric values and booleans SHALL be written empty. A duplicate identifier SHALL be requested once. The console SHALL report per field how many tickets are filled and how many tickets have another points field filled with a different value, plus the count of non-numeric values, never the values themselves. An invalid identifier SHALL stop before calling Jira.

Source: tests/export_jira_api/test_export_jira_api.py (ChampPoints, ListeDeChampsPoints)

#### Scenario: Several fields
- **WHEN** two fields hold different values on one ticket
- **THEN** the first field in the configured order wins, and the console counts the disagreement

#### Scenario: No setting
- **WHEN** nothing is configured
- **THEN** there is no points column and the field is not requested

#### Scenario: Setting as text or list
- **WHEN** the setting is a single identifier, a list, empty, or absent
- **THEN** it is read as a one-element list, a list, and two empty lists respectively

### Requirement: Field search
The system SHALL provide a `fields --search <text>` subcommand that lists, case-insensitively, only the identifier and name of the Jira fields whose name contains the text, together with the match count over the total count, and SHALL NOT read any ticket. The text SHALL be mandatory and non-blank, and the subcommand SHALL work without an export query.

Source: tests/export_jira_api/test_export_jira_api.py (Champs)

#### Scenario: Search
- **WHEN** the user searches for a text present in two field names
- **THEN** exactly those two identifier and name lines are printed, with no schema or other metadata, and no ticket request is made

#### Scenario: Blank text
- **WHEN** the text is blank
- **THEN** the exit code is 1 and Jira is not called

### Requirement: Diagnose subcommand
The system SHALL provide a `diagnose` subcommand that reads a single page of tickets requesting only the team field and reports, without any value, whether team labels are usable and the shape of the field. It SHALL exit 1 when labels are not usable and neither the referential nor the catalogue holds an identifier, or when the field is absent from responses; otherwise 0, with the identifier count of each source. It SHALL NOT read the former team table.

Source: tests/export_jira_api/test_export_jira_api.py (Diagnostic, ChampEquipeIllisible); tests/export_jira_api/test_referentiel_et_etiquettes.py (to be extended, task 4.7)

#### Scenario: Usable labels
- **WHEN** the team field returns labels
- **THEN** the report says labels are usable, one single request is made and no label appears in the output

#### Scenario: Field absent
- **WHEN** the configured field never appears in responses
- **THEN** the exit code is 1 and the message says it is absent from responses

#### Scenario: Referential as source
- **WHEN** the field returns asset objects and the referential and the catalogue hold identifiers
- **THEN** the exit code is 0 and the report gives the identifier count of each source, without any identifier or name

#### Scenario: Only the former table
- **WHEN** the field returns asset objects, neither source holds an identifier, and the former table exists
- **THEN** the exit code is 1 and the former-table key phrase is printed

### Requirement: Message language
The system SHALL print its messages in French by default and in English with `--language en`, SHALL reject other languages with exit code 2, SHALL NOT keep the language between runs, and SHALL refuse the former option name with exit code 2 naming the current one. English output SHALL contain no French words.

Source: tests/export_jira_api/test_language.py

#### Scenario: English run
- **WHEN** `--language en` is given
- **THEN** the output matches the recorded English reference and contains no French text

#### Scenario: Unknown language
- **WHEN** `--language de` is given
- **THEN** the exit code is 2

### Requirement: Strict option for unknown team identifiers
The system SHALL accept on the export subcommand an opt-in strict-teams option (decision Q10 (B) of the database-only change). With it, when at least one team identifier is in neither the organisation referential nor the catalogue of teams outside the organisation, the system SHALL print its usual lines as without the option, then print the key phrase of design D5 of the monthly-run change, exit with code 3, and record no run, sighting or snapshot in the raw layer. A catalogue team, obsolete or not, SHALL NOT make the export incomplete. The key phrase SHALL NOT name an identifier, a label, a key or a value. Without the option, the exit code and the output SHALL stay unchanged and the run SHALL be recorded.

Source: tests/export_jira_api/test_export_jira_api.py (TableEquipes: test_strict_teams_*); tests/export_jira_api/test_couche_brute.py (EquipesInconnuesEnMode_strict)

#### Scenario: Unknown identifier with the option
- **WHEN** the export runs with the strict-teams option and one identifier is in neither source
- **THEN** no file is written, the raw layer holds nothing from that run, the output ends with "unknown team identifiers: export incomplete" in English and holds no key, title, label or person, and the exit code is 3

#### Scenario: Complete referential with the option
- **WHEN** every identifier is in the referential or in the catalogue, some catalogue teams flagged obsolete, including teams written obsolete from Assets
- **THEN** the exit code is 0 and the key phrase is not printed

#### Scenario: Complete table with the option
- **WHEN** an identifier is in neither source but is in the former team table
- **THEN** the exit code is 3: the former table is not read

#### Scenario: Without the option
- **WHEN** the export runs without the option and one identifier is in neither source
- **THEN** the exit code is 0

### Requirement: Rows past the retention rule are not written
The system SHALL leave out of the raw layer the tickets resolved longer ago than the retention period of the jira-flow-retention capability: no sighting and no snapshot. It SHALL print the rows-past-the-rule key phrase with their count, and SHALL NOT print their keys.

Source: tests/export_jira_api/test_referentiel_et_etiquettes.py (Conservation); tests/export_jira_api/test_couche_brute.py (TicketsHorsConservation)

#### Scenario: Old resolved ticket
- **WHEN** the query returns a ticket resolved before the retention period
- **THEN** the raw layer holds nothing for it and the console prints "tickets past retention, not written: 1"

### Requirement: Team translation through the referential and the catalogue
The system SHALL translate asset team identifiers through the referential and the catalogue read together (team-mapping D1): the referential name first, otherwise the catalogue label, an identifier in both files being accepted. It SHALL NOT read the former team table, let one source hide the other, or call the Assets API. An identifier in neither source SHALL get the unknown-team marker, the same in both languages.

Source: tests/export_jira_api (task 4.1)

#### Scenario: Both sources used together
- **WHEN** one identifier of a ticket is in the referential only and another is in the catalogue only
- **THEN** the first is written with the referential name, the second with the catalogue label, in the API order, and no unknown marker is written

#### Scenario: Identifier in both files, the referential name wins
- **WHEN** an identifier listed under a referential team is also held by a catalogue entry with another label
- **THEN** its cell holds the referential name, it is not counted among the teams outside the organisation, no refusal is printed, and the exit code is 0

#### Scenario: Former table present
- **WHEN** the former team table exists next to the referential and the catalogue
- **THEN** its content is not read, the console prints "former team table no longer read: delete equipes-assets.yaml", and the translation is the same as without the file

### Requirement: Conflicting or missing team sources stop the export
The system SHALL stop the export with exit code 1, writing no file, with the phrase of team-mapping D11, when a catalogue entry named like a referential team holds an identifier no referential team lists, or when asset identifiers meet sources without any identifier. It SHALL name key paths and lines, or both structures. It SHALL NOT refuse an identifier present in both files, nor print an identifier, a name or a label.

Source: tests/export_jira_api (tasks 4.3, 4.4)

#### Scenario: Catalogue name of a referential team, identifier outside the referential
- **WHEN** a catalogue entry has the name of a referential team and holds an identifier that no referential team lists
- **THEN** the exit code is 1, no file is written, and the message names both key paths and lines without the name or the identifier

#### Scenario: Same team named alike in both files
- **WHEN** a catalogue entry has the name of a referential team and every identifier of the entry is listed by that referential team
- **THEN** the export continues, the identifiers are written with the referential name, and the exit code is 0

#### Scenario: No source
- **WHEN** the team field returns asset objects and neither source holds an identifier
- **THEN** the exit code is 1, the output file is not created, and the message gives the structure of both files and none of their values, even when the former table exists

### Requirement: Teams outside the organisation and obsolete teams counted apart
The system SHALL print at export the D11 lines (team-mapping): outside teams (catalogue identifiers no referential team lists), tickets on identifiers flagged obsolete in the catalogue (from Assets included, E2), and identifiers in neither source with their sorted list. No catalogue identifier SHALL be counted as unknown or change the exit code. These lines SHALL NOT print a label, a name, a ticket key or a person, nor mention a mark to confirm.

Source: tests/export_jira_api (task 4.5)

#### Scenario: Outside teams
- **WHEN** an export has three tickets on two catalogue teams and none in neither source
- **THEN** the console prints "teams outside the organisation: 2 identifiers, 3 tickets", no unknown-identifier line, and no label

#### Scenario: Obsolete team
- **WHEN** one ticket carries a team flagged obsolete in the catalogue
- **THEN** its cell holds the catalogue label, the console prints "tickets on obsolete teams: 1", and the team is not unknown

#### Scenario: Team obsolete from Assets on old tickets
- **WHEN** two tickets carry the identifier of a catalogue entry written with `obsolete: true` from an `inactive` Assets object, and every other identifier is in a source
- **THEN** its cells hold the catalogue label, the console prints "tickets on obsolete teams: 2", no unknown-identifier line, and the exit code is 0, also with the strict-teams option

#### Scenario: Obsolete in the catalogue, named by the referential
- **WHEN** one ticket carries an identifier listed under a referential team and flagged obsolete in its catalogue entry
- **THEN** its cell holds the referential name, the console prints "tickets on obsolete teams: 1", and the identifier is counted neither as outside nor as unknown

#### Scenario: Identifier in neither source
- **WHEN** one identifier is in neither the referential nor the catalogue
- **THEN** its cell holds the unknown marker, the console prints the count line and "identifiers to add:" followed by the identifier, and the export continues

### Requirement: Team sources check
The system SHALL provide `check-teams` (team-mapping D11): no Jira call, both sources read with the export's refusals, the former table only counted. Exit 0 when no table identifier is left uncovered, 4 when some are, 1 on a refusal; the cross-check gaps (E3) and the review signal never change it. It SHALL NOT print a label, a name or a person, nor write a file, and SHALL NOT edit the former table.

Source: tests/export_jira_api (task 5.1)

#### Scenario: Migration incomplete
- **WHEN** two identifiers of the former table are in neither the referential nor the catalogue
- **THEN** the output holds "former table identifiers not covered: 2" and the two identifiers, no label, and the exit code is 4

#### Scenario: Migration complete
- **WHEN** every identifier of the former table is in one source and the table is deleted
- **THEN** the output holds the sources-consistent line with counts only and the exit code is 0

#### Scenario: Former table cleaned, control before removal
- **WHEN** the author has placed, added as obsolete or removed every table identifier that was in neither source, the table still existing
- **THEN** the output holds the sources-consistent line and the former-table phrase, no not-covered line, and the exit code is 0

#### Scenario: Catalogue key to confirm refused
- **WHEN** a catalogue entry holds an `obsolete_to_confirm` key
- **THEN** the exit code is 1 and the message names the key path and line as an unknown key, without any value

### Requirement: Catalogue entries seen on export tickets signalled for review
The system SHALL make `check-teams` signal (team-mapping D1, D11) the non-obsolete catalogue entries holding an identifier outside the referential and named by the team of at least one stored ticket in scope (requirement "Team sources check reads the database, never an export file"), split by the review list (design D5 of the names-and-team-review change): an entry whose identifiers outside the referential are all in the review list is already reviewed and only counted; the others are new, counted with their tickets (the sum of the view counts of the new entries, design D13, worded "tickets counted per entry" in English and "tickets comptés par entrée" in French), and only their identifiers missing from the review list are listed. The computation SHALL live in a function that returns the counts and identifiers, the command only formatting them (design D13). It SHALL NOT read an export file, print a label or a team name, signal an entry the referential fully lists, list an identifier of the review list, or change the exit code.

Source: tests/export_jira_api (task 5.3; names-and-team-review task 4.1; rewritten on the teams read from the database by amendment task 14.1)

#### Scenario: Catalogue entry on tickets of the scope
- **WHEN** the database holds three tickets in scope whose team names one non-obsolete catalogue entry with two identifiers, the review list is empty, and the sources are otherwise consistent
- **THEN** the output holds "catalogue teams seen on export tickets, to review: 1 entries, 3 tickets", "catalogue teams seen on export tickets, already reviewed: 0 entries" and "identifiers to review:" followed by the two identifiers, no label, and the exit code is 0

#### Scenario: Entry already reviewed
- **WHEN** two seen entries are outside the referential and the identifiers of one of them are all in the review list
- **THEN** the output holds "to review: 1 entries", "already reviewed: 1 entries", and "identifiers to review:" lists only the identifiers of the other entry

#### Scenario: Every seen entry reviewed
- **WHEN** every seen entry has all its outside identifiers in the review list
- **THEN** the to-review count is 0, no "identifiers to review:" line is printed, and the exit code is unchanged

#### Scenario: Obsolete entry not signalled
- **WHEN** the only catalogue entry seen on tickets in scope is flagged obsolete
- **THEN** no review line is printed

#### Scenario: Entry of a referential team not signalled
- **WHEN** a non-obsolete catalogue entry has every identifier listed by a referential team, and the database holds tickets in scope of that referential team
- **THEN** no review line names its identifiers

#### Scenario: Ticket out of the export not counted
- **WHEN** the only ticket naming a catalogue entry carries an out-of-export instant
- **THEN** the entry is not signalled

#### Scenario: Signal with identifiers left to place
- **WHEN** a catalogue entry is seen on tickets in scope and one former-table identifier is in neither source
- **THEN** both the review lines and the not-covered lines are printed and the exit code is 4, as without the signal

#### Scenario: No export file
- **WHEN** no export CSV file exists and the database holds tickets in scope naming a catalogue entry outside the referential
- **THEN** the review lines are printed from the database, and no review-skipped phrase is printed

### Requirement: Catalogue migration from the complete Assets list
The system SHALL provide `migrate-teams --from-assets <file>` (team-mapping C1, E1, D1), no Jira call, writing once, owner-only, from a dated list of the flow folder, an entry (label, identifier, `type`) per object, then listing the identifiers named like a referential team that does not list them. It SHALL NOT skip objects, read the former table as source, write the referential or `nom_court`, or print values but identifiers and D9 labels.

Source: tests/export_jira_api (5.2, 5.6, 5.9)

#### Scenario: First migration
- **WHEN** a fictitious list holds three active objects, one of which has the name of a referential team that does not list its identifier, and no catalogue exists
- **THEN** the catalogue holds three entries with their `type`, the output holds "catalogue written: 3 entries, 1 identifiers named like a referential team, to place in the referential", "identifiers named like a referential team:" followed by that object's identifier, and the types-written line, the referential is unchanged, and the file is readable by its owner only

#### Scenario: Identifier already in the referential
- **WHEN** a fictitious object's identifier is already listed under a referential team of another name
- **THEN** a catalogue entry holds it with its label and `type`, it is counted among the entries written and not listed as named like a referential team, the referential is unchanged, and no label is printed

#### Scenario: List read
- **WHEN** `migrate-teams --from-assets` reads a fictitious list of four objects, one per status, and no catalogue exists
- **THEN** the catalogue holds four entries, the output holds "assets list read: 4 objects, 1 active, 1 draft (written as active), 1 inactive, 1 discarded", and the exit code is 0

#### Scenario: Option missing
- **WHEN** `migrate-teams` runs without `--from-assets`
- **THEN** the exit code is 2, no file is read and no catalogue is written

#### Scenario: Catalogue already present
- **WHEN** the catalogue exists
- **THEN** the exit code is 1, the output holds "catalogue already present: nothing written", the file is unchanged, and no label is printed

#### Scenario: Path outside the flow folder
- **WHEN** the option names a file outside the flow folder or with another name
- **THEN** the exit code is 1, the output holds "assets list absent or outside the flow folder: nothing written", and the file is not read

#### Scenario: Sentinel values never printed
- **WHEN** the fictitious list holds sentinel values in `libelle` and `nom_court`, all filtered out of the sensitive-names proposal
- **THEN** no sentinel value appears in the output, and the catalogue holds no `nom_court` sentinel

### Requirement: Distinctive labels proposed for the sensitive-names list
The system SHALL make `migrate-teams` print the distinctive labels it wrote, the count of the others (team-mapping D11) and, among them, the count of labels left out as common words (design D2 of the names-and-team-review change). A distinctive label reaches the minimum length of design D9 and holds a word neither of three letters or fewer nor a common word, ignoring case and accents. The common words SHALL be the closed list of the shared rule of the sensitive-names module: function and team vocabulary, common business words and common English and French dictionary words. It SHALL NOT write the proposal to a file, touch the sensitive-names list, print a label left out, embed a dictionary, or keep a second word set of its own.

Source: tests/export_jira_api (task 5.4); the suite that covers tools/sensitive_names.py (shared rule)

#### Scenario: Distinctive label proposed
- **WHEN** the migration writes an entry whose fictitious label is long enough and holds a word that is neither short nor common
- **THEN** the output holds "labels to add to the sensitive-names list: 1" followed by that label, and no file other than the catalogue is written

#### Scenario: Short label left out
- **WHEN** an entry's fictitious label is shorter than the minimum length
- **THEN** it is not printed and is counted in "labels left out by the filter:"

#### Scenario: Acronym left out
- **WHEN** an entry's fictitious label is made of words of three letters or fewer, even if the label as a whole reaches the minimum length
- **THEN** it is not printed and is counted as left out

#### Scenario: Common words left out
- **WHEN** an entry's fictitious label is made only of common words and acronyms, whatever its case or accents
- **THEN** it is not printed and is counted as left out

#### Scenario: Business words left out
- **WHEN** an entry's fictitious label is long enough and its words longer than three letters are all common business words of the shared rule
- **THEN** it is not printed, it is counted as left out, and the output holds "labels left out as common words: 1"

#### Scenario: Proposal never written
- **WHEN** the migration ends with distinctive labels proposed
- **THEN** the sensitive-names list is neither read nor modified, and no file holds the proposal

### Requirement: Strict reading of the Assets list
The system SHALL read the whole Assets list (five columns, any order) first and exit 1 (D11 phrases) on: a missing or extra column, an empty `id`, `type`, `statut` or `libelle` (counted, with the first line), a non-numeric `id`, a `type` not exactly one of four names (case kept, outer spaces cut), a bad status, a duplicate identifier, a label with two types. An empty `nom_court` is no refusal: the label stands in, and `migrate-teams` warns with the count of those lines per status (draft apart). A line with `libelle` and `nom_court` both empty is refused. The extra-column refusal keeps a nominative attribute out of the catalogue. It SHALL NOT convert an identifier, write on a refusal, or print a value.

Source: tests/export_jira_api (task 5.6)

#### Scenario: Empty short name falls back to the label
- **WHEN** the fictitious list holds one line per status with an empty `nom_court`, and `check-teams` reads the same list
- **THEN** the catalogue names those entries by their `libelle` (inactive and discarded obsolete, draft not), the output holds "short name empty, label used: 4 lines (1 active, 1 inactive, 1 draft written as active, 1 discarded)" with no label, the labels join the sensitive-names proposal, and `check-teams` accepts the list

#### Scenario: Empty cells counted
- **WHEN** two lines have an empty `id`, or one line has `libelle` and `nom_court` both empty
- **THEN** the exit code is 1, the output holds "assets list refused: id empty, 2 lines concerned (first: line N)" or the both-empty phrase with its count, and no catalogue is written

#### Scenario: Columns in another order
- **WHEN** the fictitious list holds the five columns in another order than the author's header
- **THEN** the list is read like the same list in the author's order

#### Scenario: Extra nominative column refused
- **WHEN** the fictitious list holds a sixth column naming a responsible person, with a sentinel name in its cells
- **THEN** the exit code is 1, the output holds "assets list refused: unknown column at position" followed by the position, neither the header nor the sentinel name appears in the output, and no catalogue is written

#### Scenario: Type surrounded by spaces
- **WHEN** one line holds `Verification Team` with leading and trailing spaces
- **THEN** the line is accepted and its entry is written with the type `Verification Team`

#### Scenario: Missing column
- **WHEN** the list has no `statut` column
- **THEN** the exit code is 1, the output holds "assets list refused: missing column statut", and no catalogue is written

#### Scenario: Non-numeric identifier
- **WHEN** one line holds an `id` with a character other than a digit
- **THEN** the exit code is 1, the output holds "assets list refused: non-numeric id at line" followed by the line number, not the value read, and no catalogue is written

#### Scenario: Type outside the four names
- **WHEN** one line holds a `type` that differs from the four names, if only by its case
- **THEN** the exit code is 1, the message names the line number and not the value read, and no catalogue is written

#### Scenario: Status outside the four values
- **WHEN** one line holds a status other than the four values
- **THEN** the exit code is 1, the message names the line number and not the value read, and no catalogue is written

#### Scenario: Identifier listed twice
- **WHEN** two lines hold the same identifier
- **THEN** the exit code is 1, the message names both line numbers and not the identifier, and no catalogue is written

### Requirement: Obsolete flag written from the Assets status
The system SHALL make `migrate-teams` write `obsolete: true` on each catalogue entry whose objects are all `inactive` or `discarded`, listed by identifier under their count line (team-mapping E2, D11). It SHALL treat `draft` as active, counted apart (C2 bis (a)). An entry mixing statuses SHALL be written without the flag and listed. It SHALL NOT write `obsolete_to_confirm` or a comment, nor print a label in these lines.

Source: tests/export_jira_api (task 5.7, fictitious data only)

#### Scenario: Inactive and discarded written obsolete
- **WHEN** the list holds one `inactive` and one `discarded` object, one of whose identifiers is listed by a referential team
- **THEN** both entries hold `obsolete: true`, the output holds "entries written obsolete (inactive or discarded in Assets): 2" and "identifiers written obsolete:" followed by the two identifiers, and no catalogue entry holds the `obsolete_to_confirm` key

#### Scenario: Draft treated as active
- **WHEN** the list holds one `draft` object
- **THEN** its entry is written without the `obsolete` key, it is not in the obsolete lines, and it is counted as draft in the reading line

#### Scenario: Entry mixing statuses
- **WHEN** two objects with the same label and type are one `active` and one `inactive`
- **THEN** their single entry holds both identifiers without the `obsolete` key, and the output holds "entries with active and inactive objects, written not obsolete: 1" and "identifiers of entries with mixed statuses:" followed by its two identifiers, no label, and the exit code is 0

### Requirement: Former table compared with the Assets list by counts only
With the former table present, the system SHALL make `migrate-teams` build the catalogue from the list alone and read the table only to print the comparison counts and table-only identifiers of team-mapping D11, with exit code 0. It SHALL NOT print a label, write a table-only identifier, modify the table, or refuse for an absent table.

Source: tests/export_jira_api (task 5.8)

#### Scenario: Divergent sources
- **WHEN** the table holds one identifier absent from the list and one identifier with another label than in the list, and the list holds two identifiers absent from the table
- **THEN** the output holds "former table and assets list compared: 1 identifiers only in the table, 2 only in the list, 1 with a different label" and "identifiers only in the former table:" followed by that identifier, no label of either source, the table-only identifier is not in the catalogue, and the exit code is 0

#### Scenario: Table absent
- **WHEN** `--from-assets` is given and the former table does not exist
- **THEN** the catalogue is written from the list, no comparison line is printed, and the exit code is 0

### Requirement: Referential cross-checked with the Assets list
The system SHALL make `check-teams` signal, as counts then identifiers (team-mapping E3, D11): referential identifiers absent from the latest Assets list, and teams with an identifier inactive or discarded there; teams whose catalogue types differ, or whose forced `type` differs from the deduced one. Without a list, the skipped phrase names the three list controls. It SHALL NOT change the exit code, write a file or print a label.

Source: tests/export_jira_api (tasks 5.10, 5.11)

#### Scenario: Referential identifier absent from Assets
- **WHEN** one referential identifier is not in the fictitious list, and the sources are otherwise consistent
- **THEN** the output holds "referential identifiers absent from Assets: 1" and "identifiers absent from Assets:" followed by that identifier, no label, and the exit code is 0

#### Scenario: Referential team inactive in Assets
- **WHEN** one referential team holds an identifier whose object is `inactive` in the list, and the sources are otherwise consistent
- **THEN** the output holds "referential teams with an identifier inactive or discarded in Assets: 1" and "identifiers inactive or discarded in Assets:" followed by that identifier, no label, and the exit code is 0

#### Scenario: Identifiers of different types
- **WHEN** one referential team holds two identifiers whose catalogue entries have different types, and one former-table identifier is in neither source
- **THEN** the output holds "referential teams with identifiers of different types: 1" and "identifiers with different types:" followed by the two identifiers, the referential is unchanged, and the exit code is 4, as without the control

#### Scenario: Forced type differs from the deduction
- **WHEN** one referential team forces a `type` other than the type the catalogue gives to all its identifiers
- **THEN** the output holds "referential teams whose forced type differs from the deduced type: 1" and the team's identifiers, the referential is unchanged, and the exit code is unchanged

#### Scenario: No Assets list
- **WHEN** the flow folder holds no Assets list
- **THEN** the output holds "no assets list found: checks skipped:" followed by the names of the three list controls (referential identifiers absent from Assets, referential teams inactive in Assets, team types changed in Assets), the type controls read from the catalogue, the forced-type signals included, are still printed, and the exit code is that of the other checks

### Requirement: Forced team types listed with the Assets type
The system SHALL make `check-teams` list each referential team holding a `type` key, located by the key path and line of that key, with the forced value and the Assets type alongside: the deduced type, `none` or `different types` (team-mapping point 2, D11), with or without an Assets list. It SHALL NOT print a label or a name, write the referential, or change the exit code.

Source: tests/export_jira_api (task 5.12)

#### Scenario: Forced type listed next to the Assets type
- **WHEN** a fictitious referential team, with a sentinel name, forces `Verification Team`, the catalogue gives `Development Team` to all its identifiers, and one former-table identifier is in neither source
- **THEN** the output holds "referential teams with a forced type: 1" and "forced type at" followed by the key path and line, "Verification Team" and "Assets type: Development Team", the sentinel name is absent, and the exit code is 4, as without the signal

#### Scenario: Forced team without deduced type
- **WHEN** a referential team forces a `type` and none of its identifiers is in the catalogue
- **THEN** its line ends with "Assets type: none", and the exit code is unchanged

#### Scenario: No forced type
- **WHEN** no referential team holds a `type` key
- **THEN** the output holds "referential teams with a forced type: 0" and no per-team line

### Requirement: Forced team type no longer needed signalled
The system SHALL make `check-teams` count the referential teams whose forced `type` equals their deduced type, then list the key paths and lines of these keys, to be removed (team-mapping point 2, D11), with or without an Assets list. It SHALL NOT count a team without a deduced type, remove the key or write the referential, print a label, or change the exit code.

Source: tests/export_jira_api (task 5.12)

#### Scenario: Forcing no longer needed
- **WHEN** a referential team forces `Development Team`, the catalogue gives `Development Team` to all its identifiers, and the sources are otherwise consistent
- **THEN** the output holds "forced types no longer needed, to remove: 1" and "forced types to remove:" followed by the key path and line, the referential is unchanged, and the exit code is 0

#### Scenario: Team without deduced type not counted
- **WHEN** the only forced team has two identifiers of different types in the catalogue
- **THEN** the output holds "forced types no longer needed, to remove: 0" and no list line

### Requirement: Team types changed in Assets since the catalogue was written signalled
The system SHALL make `check-teams` count the catalogue identifiers whose catalogue `type`, the type of the previous import, differs from their `type` in the latest Assets list, then list them sorted (team-mapping point 2, D11). It SHALL NOT compare an identifier absent from the list or whose entry has no `type`, keep a type history or another file, write the catalogue, print a label, or change the exit code.

Source: tests/export_jira_api (task 5.13)

#### Scenario: Type changed in Assets
- **WHEN** a catalogue entry holds `Other Team`, the latest fictitious list gives `Verification Team` to its identifier, and the sources are otherwise consistent
- **THEN** the output holds "team types changed in Assets since the catalogue was written: 1" and "identifiers with a changed type:" followed by that identifier, no label, the catalogue is unchanged, and the exit code is 0

#### Scenario: Catalogue written from the latest list
- **WHEN** the catalogue was written by `migrate-teams` from the latest list
- **THEN** the output holds "team types changed in Assets since the catalogue was written: 0" and no list line

#### Scenario: Identifier absent from the list not compared
- **WHEN** a catalogue entry added by hand, without `type`, holds an identifier absent from the latest list
- **THEN** that identifier is not counted among the changed types

#### Scenario: Signal with identifiers left to place
- **WHEN** one identifier's type changed in Assets and one former-table identifier is in neither source
- **THEN** both the changed-type lines and the not-covered lines are printed and the exit code is 4, as without the signal

### Requirement: Expected referential team without identifier signalled
The system SHALL make `check-teams` count the referential teams with no `jira_team_ids` and list their key paths and lines (team-mapping E3, D11), with or without an Assets list. It SHALL NOT print a team name, change the exit code for this gap, or write the referential.

Source: tests/export_jira_api (task 5.11)

#### Scenario: Team without identifier
- **WHEN** one fictitious referential team, with a sentinel name, holds no `jira_team_ids`, and the sources are otherwise consistent
- **THEN** the output holds "referential teams without identifier: 1" and "teams without identifier:" followed by its key path and line, the sentinel name is absent, and the exit code is 0

#### Scenario: Every team with an identifier
- **WHEN** every referential team holds at least one identifier
- **THEN** the output holds "referential teams without identifier: 0" and no list line

### Requirement: Latest Assets list chosen by the date in its name
The system SHALL make `check-teams` take, among the files of the flow folder named `equipes-assets-complet-<YYYY-MM-DD>.csv` with a valid date, the one with the latest date in its name, and print that file name alone with the list-used phrase of team-mapping D11. It SHALL NOT choose a list by modification date, nor print the folder or full path, which would carry the home folder (a personal identifier).

Source: tests/export_jira_api (task 5.10)

#### Scenario: Latest list chosen by the name, not the modification date
- **WHEN** the flow folder holds two dated Assets lists, and the one with the earlier date in its name was modified last
- **THEN** only the one with the latest date in its name is read

#### Scenario: File name printed
- **WHEN** `check-teams` reads a fictitious list dated in its name
- **THEN** the output holds "assets list used:" followed by the file name alone, and no folder or other part of its path

### Requirement: Team subcommands refused inside a Claude Code session
The system SHALL make `check-teams`, `migrate-teams` and `review-teams` refuse to start inside a Claude Code session, with exit code 3 and the session key phrase of design D11 of the team-mapping change, before reading any file. They SHALL NOT read the referential, the catalogue, the review list, the former table or any Assets list in that case, and `review-teams` SHALL NOT write the review list.

Source: tests/export_jira_api (tasks 5.1 and 5.2; names-and-team-review task 4.1)

#### Scenario: Inside a session
- **WHEN** `check-teams`, `migrate-teams` or `review-teams` starts with the Claude Code session marker set
- **THEN** it prints "Refused inside a Claude Code session", reads no file and exits with code 3

### Requirement: Export connects to the database as the import role before any Jira call
The system SHALL, before the first Jira call, connect to the database as the flow import role with that role's own password (design D13), and SHALL stop with exit code 1 and the phrases of design D11 when the password is missing or the database does not answer, calling Jira for nothing and writing no file. It SHALL NOT read the owner's password and SHALL NOT print a password. The `diagnose` and `fields` subcommands SHALL NOT connect to the database. Untested until implemented.

#### Scenario: Database unreachable
- **WHEN** the database does not answer
- **THEN** the output holds "database unreachable: export stopped before any Jira call", the exit code is 1, Jira is not called and no file is written

#### Scenario: Password missing
- **WHEN** no password is stored for the import role
- **THEN** the output holds "import role password missing: set it with db.py role-password", the exit code is 1, and Jira is not called

#### Scenario: Diagnose without database
- **WHEN** `diagnose` runs with no database available
- **THEN** it behaves as before and opens no database connection

### Requirement: Review list of outside entries kept apart from the catalogue
The system SHALL read the review list of design D4 (a file of the flow folder outside Git holding only reviewed identifiers) with the strict loader, refusing with exit 1, key path and line, never a value: an unknown key, a value that is not an identifier, a duplicate identifier. A missing review list SHALL be read as empty. `migrate-teams` SHALL NOT read, write or delete it. The system SHALL NOT accept a label in it.

#### Scenario: Survives a migration
- **WHEN** a fictitious review list holds two identifiers and `migrate-teams` writes a new catalogue
- **THEN** the review list is unchanged and `check-teams` still counts those entries as already reviewed

#### Scenario: Label key refused
- **WHEN** a fictitious review list holds a key for a label
- **THEN** `check-teams` stops with exit code 1, naming the key path and line, without any value

#### Scenario: Missing review list
- **WHEN** the review list does not exist
- **THEN** every seen outside entry is new, as before this change

### Requirement: Outside entries added to the review list by identifier
The system SHALL provide `review-teams --add <identifier> [<identifier> ...]`: several identifiers in one command, each checked, all added to the review list, owner-only, with the phrases and exit codes of design D6. One unknown identifier (held by no catalogue entry, or listed by a referential team) SHALL refuse the whole command with nothing written. It SHALL NOT offer a mark-all option, print a label, or accept a label as argument.

#### Scenario: Identifiers added
- **WHEN** `review-teams --add` names two fictitious outside catalogue identifiers, one already in the review list
- **THEN** the review list holds both, the output holds "identifiers added to the review list: 1" and "identifiers already in the review list: 1", no label, the file is readable by its owner only, and the exit code is 0

#### Scenario: Several valid identifiers in one command
- **WHEN** `review-teams --add` names three fictitious outside catalogue identifiers, none yet in the review list
- **THEN** the review list holds all three, the output holds "identifiers added to the review list: 3", and the exit code is 0

#### Scenario: One unknown identifier refuses the whole command
- **WHEN** `review-teams --add` names two valid outside catalogue identifiers and one identifier held by no catalogue entry
- **THEN** the exit code is 1, the output holds "not an outside catalogue identifier, nothing written:" followed by the unknown identifier only, and the review list is unchanged (neither valid identifier is written)

#### Scenario: Identifier of a referential team
- **WHEN** one named identifier is listed by a referential team
- **THEN** the exit code is 1, the output holds "not an outside catalogue identifier, nothing written:" followed by that identifier, and the review list is unchanged

#### Scenario: No mark-all option
- **WHEN** `review-teams` runs with `--add-seen`
- **THEN** the exit code is 2 and no file is read or written

#### Scenario: Option missing
- **WHEN** `review-teams` runs without `--add`
- **THEN** the exit code is 2 and no file is read or written

### Requirement: Line of empty cells in the Assets list refused
The system SHALL refuse, in `migrate-teams` and `check-teams`, an Assets list holding a line whose cells are all empty, with exit code 1 and the empty-line phrase of design D8 naming the line number (decided by the author, D12 of the fiche). It SHALL NOT skip that line silently, write a catalogue, or print a value.

#### Scenario: Line of separators only
- **WHEN** a fictitious list holds a line made only of separators on line 3
- **THEN** the exit code is 1, the output holds "assets list refused: empty line at line 3", and no catalogue is written

### Requirement: Catalogue refusals in the form of the export's refusals
The system SHALL print the refusals of the referential and the catalogue raised in the export tool's subcommands as its other refusals are printed (design D9): on standard error, with the `Error: ` prefix in English and the French counterpart of the export's catalogue, plain double quotes instead of guillemets in English output, exit code 1, the wording of the phrases unchanged. It SHALL NOT print a value, a name or an identifier in these refusals, nor print guillemets in English output.

#### Scenario: Unknown catalogue key in English
- **WHEN** `check-teams --language en` reads a fictitious catalogue entry holding a headcount key
- **THEN** standard error holds a line starting with "Error: " that names the key path and line in plain quotes, no guillemet and no value, the exit code is 1, and the English reference snapshot matches

### Requirement: Export writes the team type of each team
The system SHALL, in its raw-layer transaction, write the team type of each team it meets: the catalogue type, or the effective type of the referential team (forced, else deduced). It SHALL create a missing team, update only a differing type, and print "teams without a type: {n}" (design, "Complement: team type column"). It SHALL NOT guess a type from a label or another team, turn a null type into `Other Team`, or print a team label.
#### Scenario: Types from both sources
- **WHEN** an export meets a catalogue team with a type, a referential team with a deduced type and an unknown identifier
- **THEN** the first two teams carry their type, the unknown team has a null type, and the output holds "teams without a type: 1" and no label

#### Scenario: Type changed in the sources
- **WHEN** the catalogue type of a team changes between two exports
- **THEN** the second export updates that team's column and no other team row

### Requirement: Export writes the raw layer, never a file
The system SHALL write each export run into the raw layer, under the import role, in one transaction: the run, its sightings and the snapshots of the tickets read in full (design D1, D3). It SHALL connect to the database before the first Jira call and record nothing on any error. It SHALL NOT write a file holding ticket data, a title, a person, a declared label or a fix version, SHALL NOT read the owner's password, and SHALL NOT print a key, a team or a value.

#### Scenario: Successful run
- **WHEN** an export of two named queries succeeds against a fake Jira server and a disposable database
- **THEN** one run, its sightings and its snapshots exist, the exports folder holds no new file, and the output holds counts only

#### Scenario: Jira error mid-run
- **WHEN** Jira refuses a page after the first one
- **THEN** the exit code is 1, only the status code is printed, and no run, sighting or snapshot of that run remains

#### Scenario: Database unreachable
- **WHEN** the database does not answer
- **THEN** the exit code is 1, the database error is printed without password, and Jira is not called

### Requirement: Full export at each run
The system SHALL, at each run, read every ticket of each named query in full and record each as a sighting of the run (design D3 (c)). It SHALL accept `--full`, which forces that full read and changes nothing else. It SHALL NOT restrict a search to the tickets updated since an earlier run, nor read the instant of an earlier run.
#### Scenario: Second run
- **WHEN** a second run follows a successful one and one ticket was updated in between
- **THEN** every ticket of every query is read in full, every key is a sighting of the run, and the search sent to Jira holds no condition on the updated date

#### Scenario: Full option
- **WHEN** the export runs with `--full`, then without it, on the same fake Jira server
- **THEN** both runs read the same tickets in full, and their outputs are identical apart from counts that changed on the server

#### Scenario: After a failed run
- **WHEN** a run fails and the next one succeeds
- **THEN** the failed run left no run, sighting or snapshot, and the next run reads every ticket in full

### Requirement: Output option retired
The system SHALL refuse `--output` with exit code 2 and the key phrase of design D6, before any Jira call or database connection.
#### Scenario: Output option
- **WHEN** the export runs with `--output`
- **THEN** the output holds "--output is retired: the export writes into the database", the exit code is 2, and Jira is not called

### Requirement: Team sources check reads the database, never an export file
The system SHALL make `check-teams` read, under the flow read-only role, the ticket counts per team name through the teams-seen view only (design D13), matching catalogue entries by label. With the database unreachable or no ticket in scope, it SHALL print the review-skipped phrase of design D13, exit code unchanged. It SHALL NOT read an export file or a flow table, write, mask its counts, or print a key, title, team name, label, person or password.

#### Scenario: CSV file present, database read
- **WHEN** the exports folder holds a fictitious CSV file naming a catalogue entry in its team column, and the database holds no ticket of that entry
- **THEN** no review line names the entry's identifiers, and the CSV file is not opened

#### Scenario: Database unreachable
- **WHEN** `check-teams` runs and the database does not answer
- **THEN** the output holds "database unreachable: catalogue review skipped", no password is printed, and the exit code is that of the other checks

#### Scenario: No ticket in scope
- **WHEN** the database holds no ticket, or only tickets carrying an out-of-export instant
- **THEN** the output holds "no ticket in the database: catalogue review skipped" and the exit code is that of the other checks

#### Scenario: View only
- **WHEN** `check-teams` reads the teams seen on a disposable database
- **THEN** its reader queries the teams-seen view and no flow table, and a count below 5 is used as is
