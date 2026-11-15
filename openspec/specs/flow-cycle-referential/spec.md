# flow-cycle-referential Specification

## Purpose
Define the cycle referential held in the flow schema: the tables that record the cycles, their labels, columns and statuses as read by the flow settings readers, which the referential copies without replacing them. This capability sets how a referential is validated before any write, how a refusal avoids naming any value, and how a load replaces the whole referential in one transaction under the import role only. It also gives Mothra's synthetic dataset its own invented referential, loaded only into the throwaway database.

## Requirements

### Requirement: A referential is validated before any write
The system SHALL check a referential structure against every constraint of the referential tables, the flow definitions included, and its labels against the declared label set given by the loader, before writing it, and SHALL refuse it with `référentiel des cycles invalide : <codes>`, the thirteen codes of the cycle referential followed by the six codes of design D4, in that order. A refused referential SHALL NOT be written, even in part.

#### Scenario: Two findings
- **WHEN** a referential holds a cycle key written as a version number and two Ready labels
- **THEN** the writing function raises `référentiel des cycles invalide : cycle_key_form, single_label_role`, the message holds neither the key nor a label, and no statement is sent to the connection

#### Scenario: Valid referential
- **WHEN** a referential satisfies every rule of the cycle referential and of design D4
- **THEN** validation returns no finding

#### Scenario: Definition findings after cycle findings
- **WHEN** a referential holds a cycle ending before it starts, two statuses of one segment with different commitment flags and a link type with an unknown direction
- **THEN** the writing function raises `référentiel des cycles invalide : cycle_dates, commitment_flag, blocking_link_type` and no statement is sent to the connection

Source: change flow-definitions-referential, design D2 and D4 (flow definitions constraints); tests/flow_referential (cycle codes); definition codes untested until implemented (task 2.1)

### Requirement: A refusal of the referential names no value
The system SHALL name only the codes of the cycle referential and of design D4 in a refusal of the referential. The message SHALL NOT hold a cycle key, a label, a status, a segment, an issue type, a link type, a column name or a date.

Source: tests/flow_referential (cycle codes); definition codes untested until implemented (task 2.1)

#### Scenario: Refusal without values
- **WHEN** a referential with an undeclared label and a malformed cycle key is refused
- **THEN** the message holds the codes only, and neither the label nor the key

#### Scenario: Definition refusal without values
- **WHEN** a referential holding a sentinel status twice and a sentinel unplanned type with an unknown kind is refused
- **THEN** the message holds `flow_status_duplicate, unplanned_type` and neither sentinel

### Requirement: A referential load replaces the whole referential in one transaction
The system SHALL write a valid referential under the import role only, deleting the old rows of the eight referential tables and inserting the new ones in one transaction, the flow definitions after the cycle tables and the state row last. It SHALL NOT update a row in place, keep an old row, or leave a mix of two loads after a failure; under another role it SHALL refuse with `référentiel des cycles : rôle d'écriture inattendu` before any write.

#### Scenario: Replacement
- **WHEN** a referential of four cycles is loaded, then a referential of two cycles
- **THEN** the cycles table holds the two cycles only, and the state row holds the second load instant

#### Scenario: Definitions replaced
- **WHEN** a referential with three flow statuses is loaded, then the same referential with one flow status
- **THEN** the flow statuses table holds the one status only

#### Scenario: Failure during the load
- **WHEN** an insert fails in the middle of a load
- **THEN** the transaction is rolled back and the previous referential, definitions included, is intact

#### Scenario: Wrong role
- **WHEN** the writing function runs while the current role is not the import role
- **THEN** it raises `référentiel des cycles : rôle d'écriture inattendu` and sends no write statement

Source: change flow-definitions-referential, design D4 (order of the load); tests/flow_referential; tests/db/test_flow_referential.py; definition tables untested until implemented (tasks 2.1, 2.2)

### Requirement: The synthetic dataset holds its own cycle referential
The system SHALL give Mothra's synthetic dataset a referential built from the load day only (design D6): four contiguous cycles around that day, invented labels, columns and statuses, and a mapping not validated by default or validated on request. It SHALL NOT read a file of the flow content folder, copy a value of the flow settings or derive anything from real data.

Source: untested (tests/mothra_donnees, task 2.3)

#### Scenario: Cycles around the load day
- **WHEN** the synthetic referential is built for a given day
- **THEN** exactly one cycle contains that day, one ended before it, two start after it, and every cycle starts on a Monday and ends on a Friday eight weeks later

#### Scenario: Deterministic
- **WHEN** the synthetic referential is built twice for the same day
- **THEN** both structures are equal

#### Scenario: Two variants
- **WHEN** the referential is built without argument, then with the validated variant
- **THEN** the first has no validation date and the second has a date before the load day, all else being equal

#### Scenario: Valid and invented
- **WHEN** the synthetic referential is validated and its labels, columns and statuses are read
- **THEN** validation against the synthetic dataset's own declared label set returns no finding, every label, column and status starts with the prefix of the synthetic dataset, two up-merge labels, one cycle label per cycle and one confirmation label per meaning are present, and one status maps to no column

### Requirement: The synthetic referential loads only into the throwaway database
The system SHALL load the synthetic referential through the writing function, under the import role of the throwaway database, as a step of the existing synthetic loader, after its refusal without `DBTEST_PORT` (exit 2, `jeu synthétique : base jetable absente`). It SHALL NOT connect to the real database or load a referential there.

Source: untested until implemented (tests/mothra_donnees, task 4.2)

#### Scenario: Without throwaway database
- **WHEN** the synthetic loader runs without `DBTEST_PORT`
- **THEN** it exits 2 with `jeu synthétique : base jetable absente`, opens no connection and writes no referential

#### Scenario: Loaded with the dataset
- **WHEN** the synthetic loader runs on the throwaway database
- **THEN** the referential tables hold the four synthetic cycles and the state row, and the flow views role still cannot read them

### Requirement: The two flags of a status are derived by one function
The system SHALL compute the two flags of a flow status only through the flag function of design D3, from its segment and a commitment point given by the caller. It SHALL NOT assume a default commitment point, and SHALL refuse a commitment point outside the computed segments (`commitment_flag`) or an unknown segment (`flow_status_segment`) without the value.

Source: untested (task 2.1)

#### Scenario: Default commitment point of the flow reports
- **WHEN** the flag function is called for a status of each segment with the Ready segment as commitment point
- **THEN** only the Ready status is committed and carries the Ready-queue flag; the statuses of every other segment, the later computed segments included, carry neither flag (delegated decision R-20261029-10, as in the flow reports)

#### Scenario: Later commitment point
- **WHEN** the flag function is called for a Ready status and an implementation status with the implementation segment as commitment point
- **THEN** the Ready status is not committed and carries the Ready-queue flag, and the implementation status is committed without the Ready-queue flag

#### Scenario: Committed statuses in two segments refused
- **WHEN** a referential holds committed statuses in the Ready and implementation segments
- **THEN** validation returns `commitment_flag`

#### Scenario: Commitment point outside the computed segments
- **WHEN** the flag function is called with the done segment as commitment point
- **THEN** it raises `référentiel des cycles invalide : commitment_flag`

### Requirement: Empty flow definitions are a valid referential
The system SHALL accept a referential without flow statuses, unplanned types or blocking link types, and SHALL write it with the three definition tables empty, so that a reader sees that the definitions are absent. It SHALL NOT fill an empty definition table from a default, the flow settings or a code constant.

Source: untested until implemented (tests/flow_referential, task 2.1)

#### Scenario: Cycle referential alone
- **WHEN** a valid referential with cycles and labels but no definition is written
- **THEN** validation returns no finding, the three definition tables are emptied, and no definition row is inserted

### Requirement: The synthetic dataset holds its own flow definitions
The system SHALL give the synthetic referential of Mothra deterministic flow definitions (design D8), the same in both variants, with flags from the flag function and the Ready segment as commitment point. It SHALL NOT read a file of the flow content folder, copy a value of the flow settings or of a code default, or derive anything from real data.

Source: untested (task 2.3)

#### Scenario: Definitions present and valid
- **WHEN** the synthetic referential is built for a given day, in either variant
- **THEN** its definitions are equal in both variants, validation returns no finding, every segment has a status, one unplanned type of kind `defect` and one link type per direction are present, their names come from the synthetic dataset module, and each status's flags equal those of the flag function with the Ready segment

#### Scenario: Deterministic and invented
- **WHEN** the synthetic definitions are built twice for the same day while any opening of a path under the flow content folder fails the test
- **THEN** both structures are equal and no such path is opened

#### Scenario: Loaded with the dataset
- **WHEN** the synthetic loader runs on the throwaway database
- **THEN** the three definition tables hold the synthetic definitions, and the flow views role still cannot read them

### Requirement: Real flow definitions are built from the tools' own readers
The system SHALL build the real flow definitions from one strict read of the flow settings, through the readers the flow tools already use (change flow-definitions-loader, design D2). It SHALL NOT copy a list of statuses, types or link types, read the flow settings a second time, call a report's own settings loader, or read Jira.

Source: untested until implemented (tests/flow_definitions, task 2.1)

#### Scenario: Settings without the definition keys
- **WHEN** the definitions are built from settings that give no segment, commitment point or link type key and no defect type
- **THEN** the statuses and segments equal those of the flow report's code defaults, the commitment point is the shared default, the link types are the dependency report's defaults with their directions, and there is no unplanned type

#### Scenario: Link type in both lists
- **WHEN** the settings give one link type in both the blocking and the waiting lists
- **THEN** the definitions hold it once, with direction `blocks`, as the dependency report classifies it

### Requirement: Flags of real statuses come from the flag function
The system SHALL give each real status its flags only through the referential's flag function, with the commitment point of the shared reader translated to the referential's segment names (design D2). It SHALL NOT compute a flag in the loader, and SHALL refuse a segment the name tables do not know without naming it.

Source: untested until implemented (tests/flow_definitions, task 2.1)

#### Scenario: Flags equal the flag function
- **WHEN** the definitions are built from the code defaults
- **THEN** every status's flags equal those of the flag function with the shared default commitment point

#### Scenario: Unknown segment refused
- **WHEN** the settings declare a computed segment whose name the segment name tables do not know
- **THEN** building the definitions raises `référentiel des cycles invalide : flow_status_segment` and the message holds no segment or status name

### Requirement: Real definitions are written through the referential's writing function
The system SHALL write the real definitions only through the referential's writing function, under the import role, replacing the definitions whole, dated by the state row's load instant (design D3). It SHALL NOT use a second writer, read a table other than the four cycle tables of the guard, keep a definition absent from the new load, or keep a history of the definitions.

Source: untested until implemented (tests/flow_definitions, task 2.2; tests/db/test_flow_definitions_loader.py, task 2.4)

#### Scenario: Reload replaces
- **WHEN** definitions with three statuses are loaded, then definitions with one status
- **THEN** the flow statuses table holds the one status and the state row holds the second load instant

#### Scenario: Refused load keeps the previous definitions
- **WHEN** a load is refused by validation after a successful load
- **THEN** the command exits 1 with the `référentiel des cycles invalide : <codes>` message and the previous definitions are intact

### Requirement: A definitions load writes the cycle part empty
Until the real loader of the cycle referential exists, the system SHALL write the cycle part of the referential empty with the definitions and print `référentiel des cycles : non chargé, ses tables restent vides` (design D4). It SHALL NOT write a cycle, label, column or Discovery Workflow status from a definitions load, nor load it silently.

Source: untested until implemented (tests/flow_definitions, task 2.2)

#### Scenario: Cycle tables stay empty
- **WHEN** the author loads the real definitions
- **THEN** the cycle tables are empty after the load and the output holds the fixed line on the cycle referential

### Requirement: A definitions load never empties a loaded cycle referential
The system SHALL check, in the load's transaction and before any write, that the four cycle tables hold no row, and SHALL refuse otherwise with exit 1 and `définitions de flux : référentiel des cycles déjà chargé (cycle_referential_present), rien n'est écrit` (design D4). It SHALL NOT then write, empty a cycle table, or read another table.

Source: untested until implemented (tests/flow_definitions, task 2.2; tests/db/test_flow_definitions_loader.py, task 2.4)

#### Scenario: Cycle present
- **WHEN** the throwaway database holds one cycle and the definitions are loaded
- **THEN** the load is refused with the guard's phrase, no definition is written, and the cycle is still present after the refusal

### Requirement: The real definitions load is run by the author alone
The system SHALL offer `uv run tools/flow_definitions.py load [--dry-run]` with the exit codes and phrases of design D5, and SHALL refuse it inside a Claude Code session with exit 3 and `définitions de flux : à lancer par l'utilisateur seul, dans le Terminal` before reading anything. It SHALL NOT create a missing flow settings file or print a status, type, link type, segment, password or settings value.

Source: untested until implemented (tests/flow_definitions, task 2.2)

#### Scenario: Session refused
- **WHEN** the command runs inside a Claude Code session
- **THEN** it exits 3 with the session phrase, reads no file and opens no connection

#### Scenario: Settings absent
- **WHEN** the flow settings file does not exist
- **THEN** the command exits 1 with `définitions de flux : réglages de flux absents` and no file is created

#### Scenario: Database unreachable
- **WHEN** the database cannot be reached or the import role's password is missing
- **THEN** the command exits 1 with `définitions de flux : base injoignable (<type de l'erreur>)` and the message holds no password

### Requirement: The dry run of the definitions load writes nothing
The system SHALL build and validate the definitions in a dry run and print `définitions de flux, essai à blanc : <n> statuts, <n> types non planifiés, <n> types de liens bloquants ; rien n'est écrit` (design D5). It SHALL NOT open a database connection in a dry run.

Source: untested until implemented (tests/flow_definitions, task 2.2)

#### Scenario: Dry run
- **WHEN** the author runs the command with `--dry-run` on valid settings
- **THEN** it exits 0 with the dry-run line and opens no connection

### Requirement: A referential without any cycle column does not need a start column
The system SHALL accept, in the referential's validation, a cycle part that is entirely empty (no cycle, label, column, status or validation date), and SHALL keep refusing with `start_column` any cycle part that holds something but does not have exactly one start column (change flow-definitions-loader, design D4, delegated decision R-20261029-23). It SHALL NOT weaken any other rule of the cycle part.

Source: untested until implemented (tests/flow_definitions, task 2.2)

#### Scenario: Empty cycle part accepted
- **WHEN** a referential with no cycle, label, column or status is validated
- **THEN** validation reports no finding

#### Scenario: Columns without a single start column still refused
- **WHEN** a referential has columns but none, or two, flagged as the start column
- **THEN** validation reports `start_column`

#### Scenario: Cycles without a column refused
- **WHEN** a referential has a cycle, a label, a status or a validation date but no column
- **THEN** validation reports `start_column`
