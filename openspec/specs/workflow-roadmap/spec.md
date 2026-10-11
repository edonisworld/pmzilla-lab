# workflow-roadmap Specification

## Purpose
A work queue kept in one tracked document, a reader that checks it, proposes the ready jobs that fit a time budget and marks a job done, and the `/next` command that presents those proposals without editing anything.
## Requirements
### Requirement: The work queue has a fixed, checkable format
The system SHALL keep the work queue in a tracked document of the documentation folder, made of free prose and exactly one fenced YAML block whose `jobs` key holds an ordered list; the order SHALL be the priority. Each job SHALL have an identifier (unique, a fixed prefix followed by digits), a title, a list of dependencies (identifiers of the queue), start conditions (text, possibly empty), a state among `ready`, `blocked`, `in-progress` and `done`, an estimate (a duration in minutes, hours or hours and minutes, or `tbd`), a method among `openspec` and `direct-prompt`, and a model among `opus`, `sonnet`, `haiku` and `tbd`; it MAY have a not-before date, a due date (both as year-month-day dates) and the name of an OpenSpec change, and SHALL have no other field. Fenced blocks of another language SHALL be ignored when counting YAML blocks. The queue SHALL NOT be a calendar (dates never reorder it) and SHALL NOT contain a person's, team's or project's name.

#### Scenario: Valid queue
- **WHEN** the document holds one YAML block whose jobs have every required field with allowed values
- **THEN** the queue is valid

#### Scenario: Two YAML blocks
- **WHEN** the document holds two fenced YAML blocks, or none
- **THEN** the queue is invalid

#### Scenario: Unknown field
- **WHEN** a job has a field outside the required and optional ones
- **THEN** the queue is invalid and the job and the field are named

#### Scenario: Forbidden values
- **WHEN** a job has a state, a method or a model outside the allowed values, a zero or malformed estimate, an identifier without the prefix, or an impossible date
- **THEN** the queue is invalid and the job and the field are named

Source: tests/roadmap/test_roadmap.py (TestFormat, including test_modeles_admis and test_le_message_du_modele_nomme_les_valeurs_admises)

### Requirement: The queue reader checks consistency
The system SHALL provide a queue reader whose check command exits 0 on a valid queue, exits 1 and prints one line per problem naming the job identifier and the field on an invalid queue, and exits 2 on a usage error or a missing file. Beyond field presence and allowed values, it SHALL check that identifiers are unique, that dependencies exist, that there is no dependency cycle, that a `ready` job has all its dependencies `done`, and that a `done` job has no dependency that is not `done`. The check SHALL also read the archive document when it exists, resolving dependencies against the queue and the archive together, so that an archived identifier counts as `done`, identifiers are unique across the two files, and a job of the archive that is not `done` is a problem; an unreadable archive SHALL make the queue invalid. It SHALL NOT modify the document.

#### Scenario: Unknown dependency
- **WHEN** a job depends on an identifier absent from the queue and from the archive
- **THEN** the check exits 1 and names the job and the dependency field

#### Scenario: Cycle
- **WHEN** two jobs depend on each other
- **THEN** the check exits 1 and names both jobs

#### Scenario: Ready with a pending dependency
- **WHEN** a `ready` job depends on a job that is not `done`
- **THEN** the check exits 1 and names the job and its state field

#### Scenario: Done with a pending dependency
- **WHEN** a `done` job depends on a job that is not `done`
- **THEN** the check exits 1 and names the job and its state field

#### Scenario: Missing file
- **WHEN** the queue document does not exist
- **THEN** the reader exits 2 with a message on the error output

#### Scenario: Dependency in the archive
- **WHEN** a job depends on an identifier that only the archive holds
- **THEN** the dependency is resolved and counts as `done`

#### Scenario: Identifier in both files
- **WHEN** the same identifier is in the queue and in the archive
- **THEN** the check exits 1 and names the identifier as duplicated

Source: tests/roadmap/test_roadmap.py (TestCoherence, TestCodesDeSortie, TestDeuxFichiers)

### Requirement: The queue reader proposes jobs for a time budget
The system SHALL provide a next command that takes a duration budget, walks the queue in order, and proposes each job that is `ready`, whose dependencies are `done` (an archived dependency counts as `done`) and whose not-before date is reached, when its estimate fits the remaining budget; a proposable job that does not fit SHALL be listed as too long for the remaining time and the walk SHALL continue; proposable jobs estimated `tbd` SHALL be listed apart and never counted in the budget. For each proposed job it SHALL print the identifier, the title, the estimate, the method, the model, the conditions to confirm and the due date when present, then the total. It SHALL exit 1 on an invalid queue and 2 on a malformed budget. Today's date SHALL be replaceable by an option or an environment variable, for tests. It SHALL NOT modify the document, reorder the queue, or propose a job that is `blocked`, `in-progress`, `done`, waiting for a dependency or before its not-before date.

#### Scenario: Budget filled in order
- **WHEN** the budget is two hours and the first three proposable jobs are estimated one hour, ninety minutes and thirty minutes
- **THEN** the first and the third are proposed, the second is listed as too long, and the total is ninety minutes

#### Scenario: Unestimated job
- **WHEN** a proposable job is estimated `tbd`
- **THEN** it is listed apart and not counted

#### Scenario: Not-before date in the future
- **WHEN** a `ready` job has a not-before date after today
- **THEN** it is not proposed

#### Scenario: Malformed budget
- **WHEN** the budget is not a duration
- **THEN** the command exits 2 and proposes nothing

#### Scenario: Archived dependency
- **WHEN** a `ready` job depends only on an archived job
- **THEN** it is proposed

Source: tests/roadmap/test_roadmap.py (TestNext, TestDeuxFichiers)

### Requirement: The queue reader marks a job done
The system SHALL provide a done command that sets the state of the given job to `done`, keeps every other line of the document unchanged, and lists the jobs whose dependencies are now all `done` (archived jobs counting as `done`) so that the user can set them `ready`. It SHALL exit 1 on an unknown identifier or an invalid queue, and SHALL NOT change the state of any other job. Given the identifier of an archived job, it SHALL say that the job is already archived, exit 0 and write nothing.

#### Scenario: Job completed
- **WHEN** the done command is given the identifier of the only dependency of a `blocked` job
- **THEN** that job is `done`, the blocked job is listed as unblocked but stays `blocked`, and no other line changed

#### Scenario: Unknown identifier
- **WHEN** the done command is given an identifier absent from the queue and from the archive
- **THEN** it exits 1, names the identifier and leaves the document unchanged

#### Scenario: Archived identifier
- **WHEN** the done command is given the identifier of an archived job
- **THEN** it says the job is already archived, exits 0 and leaves both files unchanged

Source: tests/roadmap/test_roadmap.py (TestDone, TestDeuxFichiers)

### Requirement: /next proposes ready jobs for the time given
The system SHALL provide a `/next <duration>` slash command that runs the queue reader's next command with the duration, presents the result in the user's language (enumerated values translated), and asks the user which job to start. It SHALL NOT edit the queue, start a job, reorder the queue, invent an estimate or a model, or run anything other than the queue reader.

#### Scenario: Two hours
- **WHEN** the user types `/next 2h`
- **THEN** the command lists, in queue order, the proposed jobs with their durations and the total, the jobs too long and the unestimated ones apart, and ends by asking which job to start

#### Scenario: Pre-approval
- **WHEN** the header of the command file is read
- **THEN** it pre-approves only the reader's next command

Source: tests/workflow_commands/test_workflow_commands.py (test_next_ne_pre_approuve_que_la_sous_commande_next_du_lecteur); the presentation is untested

### Requirement: The real queue stays valid
The system SHALL include a test that runs the queue reader's check on the tracked queue document and fails when it is invalid, naming the job and the field; the test SHALL be skipped, naming the expected document, when the document is absent; the test SHALL NOT print the free text of the jobs.

#### Scenario: Missing document
- **WHEN** the tracked queue document does not exist
- **THEN** the test is skipped and names the expected document

#### Scenario: Invalid real queue
- **WHEN** a job of the tracked queue has a state outside the allowed values
- **THEN** the test fails and names the job and the state field

Source: tests/roadmap/test_roadmap.py (TestDocumentReel)

### Requirement: Finished jobs are archived
The system SHALL provide an archive command that moves to an archive document, kept next to the queue document and of the same format (prose descriptions and one fenced YAML block whose `jobs` key holds the list), every `done` job that no job outside `done` depends on: its YAML entry and its description paragraph, moved word for word, placed at the head of the archive in front of the jobs already there. It SHALL create the archive, with a one-sentence header, when it does not exist, SHALL be idempotent (a second run moves nothing and writes nothing), and SHALL keep in the queue a `done` job on which a job outside `done` depends. With a dry-run option it SHALL list the jobs that would move and write nothing. It SHALL exit 1 when the queue is invalid before the move, or would be invalid after it, in which case it writes nothing. The archive SHALL hold only `done` jobs.

#### Scenario: Job moved
- **WHEN** a `done` job has no dependent outside `done`
- **THEN** its entry and its description paragraph are in the archive, unchanged, and no other line of the queue changed

#### Scenario: Job kept
- **WHEN** a `done` job has a dependent that is not `done`
- **THEN** it stays in the queue

#### Scenario: Second run
- **WHEN** the archive command runs twice in a row
- **THEN** the second run reports nothing to archive and neither file changes

#### Scenario: Dry run
- **WHEN** the archive command runs with the dry-run option
- **THEN** it lists the jobs that would move and neither file is written nor created

Source: tests/roadmap/test_roadmap.py (TestArchive)

## Open questions

None.

