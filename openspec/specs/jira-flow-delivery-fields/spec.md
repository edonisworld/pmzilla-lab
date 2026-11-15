# jira-flow-delivery-fields Specification

## Purpose
TBD - created by archiving change jira-delivery-fields. Update Purpose after archive.

## Requirements

### Requirement: Closed list of delivery fields in their stored form
The system SHALL request the closed list of delivery fields of design D1 and reduce each value to its stored form before storage: a sprint as identifier, state and dates; an asset version field as object identifiers; an option field as option identifiers only. It SHALL NOT request or store a sprint name, goal or board, an option value, a customer name, a person, free text, time spent, an estimate in hours or an attachment.

#### Scenario: Distinctive sprint and customer
- **WHEN** the fake server returns a ticket whose sprint carries a distinctive name and goal and whose customer commitment names a distinctive customer
- **THEN** the database holds the sprint identifier, state and dates and `customer_commitment` true, and neither distinctive string

#### Scenario: Requested field list
- **WHEN** an export runs with every setting present
- **THEN** the requested delivery fields are exactly those of design D1, and no person, free text, time spent or attachment field is requested

### Requirement: Commitments and strategic objective by presence only
The system SHALL store the customer commitment, the source commitment and the strategic objective as yes when filled and no when empty, whatever the option (R-20261102-50, design D1). It SHALL NOT read the label of an option to decide yes or no: the former case "option No is no" is withdrawn.

#### Scenario: Commitment read by presence only
- **WHEN** the customer commitment holds one option, whatever its label, and the source commitment and the strategic objective are empty
- **THEN** `customer_commitment` is true, `source_commitment` and `strategic_objective` are false, and no option label decides a false value

### Requirement: Asset version fields kept as object identifiers
The system SHALL store, for the target, resolution and the two epic version asset fields, the list of asset object identifiers alone, under their kind. It SHALL NOT store the asset `id`, the workspace identifier or any label of the object, and SHALL NOT call the Assets API.

#### Scenario: Asset value with other attributes
- **WHEN** a target version value holds an object identifier, an `id`, a workspace identifier and a distinctive label
- **THEN** the database holds only the object identifier under the kind `target`, and the server log holds no Assets request

### Requirement: Option fields kept as option identifiers only
The system SHALL store every option field of design D1, the detected by and affected installed base fields of a defect included, as its option identifiers only (R-20261102-51). An option without identifier SHALL NOT be kept. It SHALL NOT store, print or expose an option value, and no table of design D3 SHALL hold a column for one.

#### Scenario: Option value never stored
- **WHEN** the fake server returns a ticket whose workflow option field and release target each hold an option with an identifier and a distinctive label
- **THEN** the database holds the two option identifiers, and the distinctive labels are in no table, snapshot or output

#### Scenario: No value column
- **WHEN** the columns of the delivery option table, of the delivery row table and of the defect fields table are listed after migration `0034`
- **THEN** none of them holds an option value: the single-value option columns are option identifier columns, and the delivery option table has no value column

### Requirement: Sensitive-names filter on version short names
The system SHALL pass a version short name, the only text value still stored, through the shared sensitive-names rule before storage: a short name holding a listed name is replaced by the module's marker and counted on the short-name filter line of design D12. The list SHALL be loaded before the first Jira call; if unavailable, the export SHALL stop with exit code 1 before any call. It SHALL NOT print a short name, the list's path or its content.

#### Scenario: Short name holding a sensitive name
- **WHEN** a version ticket's short name holds a name of a fictitious sensitive-names list
- **THEN** the version reference holds the marker in place of the short name, the output holds "version short names replaced by the sensitive-name marker: 1", and the name appears in no output

#### Scenario: Sensitive-names list unavailable
- **WHEN** the export runs and the sensitive-names list cannot be loaded
- **THEN** the exit code is 1, the output holds "sensitive-names list unavailable: version short names cannot be filtered, export stopped.", the server's raw log is empty, and no output holds the list's path or a name

### Requirement: Version tickets read in the reference project only
The system SHALL read the version tickets with the single search of design D4, on the project of the version reference setting, kept outside Git. With the setting absent it SHALL skip the version attributes, print the line of design D12 and keep exit code 0. A malformed setting, or a key also declared in scope, SHALL stop with exit code 6 and the setting phrase, before any Jira call.

#### Scenario: Setting absent
- **WHEN** the export runs without the version reference setting
- **THEN** no version search is sent, the output holds "version reference project not configured: version attributes skipped", and the exit code is 0

#### Scenario: Malformed setting
- **WHEN** the setting holds two project keys
- **THEN** the exit code is 6, the output holds "Jira request refused: setting unreadable (version_reference_project)" and no value, and the server's raw log is empty

#### Scenario: Other search on the reference project
- **WHEN** the client is asked for a search naming the fictitious reference project in another form than design D4
- **THEN** it is refused with the scope phrase before any call, and through a command the exit code is 6

### Requirement: Other types and other requests refused on the reference project
The system SHALL set aside and count, in the answer of the version search, every ticket whose type is not Version, and SHALL NOT store it. It SHALL NOT send a changelog or bulk changelog request for a ticket of the reference project, nor store the key or summary of a version ticket.

#### Scenario: Ticket of another type
- **WHEN** the version search answer holds two Version tickets and one ticket of another type
- **THEN** only the two are stored, the output holds "tickets of another type set aside from the version reference project: 1", and no key is printed

#### Scenario: Changelog of a version ticket
- **WHEN** the client is asked for the changelog of a ticket of the fictitious reference project
- **THEN** it is refused with the scope phrase and the server's raw log is empty

### Requirement: Version attributes joined by asset object
The system SHALL join a version ticket to the stories by the object identifier of its asset field, storing short name (after the filter), status, status category, Started and Released per object. A version ticket with zero objects and one with several objects SHALL each be counted on its own line, and not stored; an object carried by two tickets SHALL get null attributes and be counted. Lines of design D12. It SHALL NOT store a version ticket that holds several objects under any of them.

#### Scenario: One object per ticket
- **WHEN** a version ticket holds one object identifier also held by the target version of a story
- **THEN** the version reference of that object holds the ticket's attributes and the output holds "version tickets read: 1"

#### Scenario: Two tickets on one object
- **WHEN** two version tickets hold the same object identifier
- **THEN** that object's attributes are null and the output holds "assets with conflicting version tickets: 1"

#### Scenario: Ticket without asset
- **WHEN** a version ticket holds no object identifier
- **THEN** nothing is stored for it and the output holds "version tickets without asset: 1"

#### Scenario: Ticket with several assets
- **WHEN** a version ticket holds two object identifiers
- **THEN** nothing is stored for either object from it and the output holds "version tickets with several assets: 1"

#### Scenario: Version without ticket at import
- **WHEN** a story's resolution version holds an object identifier that no version ticket holds
- **THEN** the import prints "versions without version ticket: 1"

### Requirement: Version tickets kept out of the ticket table
The system SHALL NOT write a version ticket into the ticket table, its teams or its links, so that the existing views are unchanged. A version SHALL be exposed only by its opaque number, assigned by the database, never by its short name or a ticket key. Released SHALL be described as the availability date, never an installation date.

#### Scenario: Existing views unchanged
- **WHEN** an export reads three version tickets and the import runs
- **THEN** the ticket table holds no version ticket and every existing view returns the same rows as without them

### Requirement: Delivery fields derived at import
The system SHALL derive, at import, from the latest snapshot of each ticket, its delivery row, current sprints, current asset versions and option identifiers, and from the latest version snapshots the version references, under the import role in the import's transaction. A ticket deletion SHALL remove its delivery rows by cascade.

#### Scenario: Sprint removed in Jira
- **WHEN** a later export finds one of a ticket's two sprints removed and the import runs
- **THEN** the ticket's current sprints hold only the remaining one

### Requirement: Slip rule
The system SHALL count slips of a sprint or version field with the pure function of design D7: over the ordered non-empty values, a slip is a step to a value holding an identifier absent from the previous non-empty value. A first fill and an emptying SHALL NOT be slips. Readers SHALL call the function, never recount in their formatting.

#### Scenario: First fill
- **WHEN** a field goes from empty to {S1}
- **THEN** the slip count is 0

#### Scenario: Identifier added
- **WHEN** a field goes from {S1} to {S1, S2}
- **THEN** the slip count is 1

#### Scenario: Emptied then refilled
- **WHEN** a field goes from {V1} to empty, then to {V2}
- **THEN** the slip count is 1

#### Scenario: Identifier removed only
- **WHEN** a field goes from {S1, S2} to {S1}
- **THEN** the slip count is 0

### Requirement: Flow of an epic read on its own statuses
The system SHALL measure the flow of an epic on its own transitions, through the pure function of design D11, and SHALL NOT measure it only from the transitions of its stories.

#### Scenario: Epic without story
- **WHEN** an epic has no story and three transitions of its own
- **THEN** its flow measures are computed on those three transitions

### Requirement: No delivery value printed
The system SHALL print, for the delivery fields and the version tickets, counts only. It SHALL NOT print a sprint identifier or name, an object identifier, an option identifier or label, a short name, a date, a version ticket key or the reference project key, in any output or error message.

#### Scenario: Distinctive values absent
- **WHEN** the fake server returns distinctive strings in every sprint, option, short name, version ticket key and asset label, and the export succeeds or fails
- **THEN** none of them appears in the output or the error output

### Requirement: Defect fields collected by the export only
The system SHALL request in the export's ticket search the defect fields of design D1 and store them for tickets of a configured defect type only: detection and affected versions as object identifiers, detection phase as option identifier plus closed code, detected by and installed base as option identifier only (R-20261102-51). It SHALL NOT historise them, store them for another type, or store, print or expose an option value or a person.

#### Scenario: Defect fields stored
- **WHEN** the fake server returns a defect with a detection version, an affected version, a detection phase option labelled Production and a detected-by option holding a distinctive string
- **THEN** the database holds the two object identifiers under the kinds `detected` and `affected`, the detection phase option identifier with the code `production`, and the detected-by option identifier alone, and the distinctive string appears in no table, snapshot or output

#### Scenario: Defect fields on another type
- **WHEN** a story carries a detection phase option and a detection version
- **THEN** no defect field and no `detected` version is stored for it

#### Scenario: Defect fields not historised
- **WHEN** `collect` runs
- **THEN** the bulk changelog field list holds none of the detection version, affected versions, detection phase, detected by or installed base fields

### Requirement: Detection phase stored as a closed code
The system SHALL store a defect's detection phase as its option identifier and a closed code (R-20261102-35): `production` when the trimmed label is exactly "Production", `piloting` when exactly "Piloting", `other` otherwise. The label SHALL be compared, never stored. The database SHALL refuse any other code through the constraint `issue_defect_fields_phase_code` of migration `0034`. It SHALL NOT store a free phase value. The closed code SHALL be kept even when the option has no identifier.

#### Scenario: Phase option without identifier
- **WHEN** a defect carries a detection phase option labelled Production and holding no identifier
- **THEN** its stored code is `production`, its detection phase identifier is null (the column `detection_phase_id` is nullable, migration `0032` line 79; decision R-20261105-35, B1 (a)), and no label is stored

#### Scenario: Recognised and other labels
- **WHEN** three defects carry a detection phase option labelled Production, one labelled Piloting and one with a distinctive label
- **THEN** their stored codes are `production`, `piloting` and `other`, and the distinctive label is in no table or output

#### Scenario: Free value refused by the database
- **WHEN** the import role inserts a defect row whose detection phase holds a value outside `production`, `piloting` and `other`
- **THEN** the database refuses it on the constraint `issue_defect_fields_phase_code`

### Requirement: Change failure counts by detection version
The system SHALL count, with the pure function of design D13, per detection version object, the defects whose detection phase code is `production` and, in a separate count, those whose code is `piloting`; it SHALL NOT add the two. A defect without detection version SHALL be counted as unattached, never attached to a version nor dropped. A defect with several versions SHALL count in each; a total over versions SHALL count it once. Readers SHALL call the function, never recount.

#### Scenario: Piloting never added
- **WHEN** a version object holds two Production defects and three Piloting defects
- **THEN** the function returns production 2 and piloting 3 for it, and no count of its result equals their sum

#### Scenario: Defect without detection version
- **WHEN** a Production defect has no detection version
- **THEN** it is counted in the unattached Production count and attached to no version

#### Scenario: Several detection versions, per version
- **WHEN** a Production defect names the detection versions V1 and V2
- **THEN** the production count of V1 and that of V2 each hold it once

#### Scenario: Several detection versions, total
- **WHEN** the same defect is in a total over V1 and V2 (a year or the product)
- **THEN** the total's production count holds it once, not twice

#### Scenario: Other phase
- **WHEN** a defect's detection phase is empty or its code is `other`
- **THEN** it is counted as other phase and in neither the Production nor the Piloting count

#### Scenario: Context fields not read
- **WHEN** two defects differ only by detected by and affected installed base
- **THEN** the function returns the same counts for each
