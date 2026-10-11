# workflow-commands Specification

## Purpose
Slash commands that drive the work on the repository: `/implement` and `/close` for an OpenSpec change, `/add-books` for the library configuration, `/audit` for a read-only audit. Each states what it does, what it hands over to the user and what it never does; a test checks that their headers pre-approve no forbidden launch. `/next` is specified with the work queue (workflow-roadmap).
## Requirements
### Requirement: /implement works on the change's branch
The system SHALL provide an `/implement <change>` slash command that reads the proposal, design, tasks and delta specs of the named OpenSpec change and implements its tasks in order. It SHALL refuse, with a message naming the change, when the change does not exist or is archived. When the session is on `main`, it SHALL create and switch to a branch whose last name segment is the change name before writing anything. It SHALL NOT write or commit on `main`.

#### Scenario: Unknown change
- **WHEN** `/implement` is given a name that is not an unarchived change
- **THEN** it says so, names the change and writes nothing

#### Scenario: Started on main
- **WHEN** `/implement` starts while the current branch is `main`
- **THEN** it creates a branch ending with the change name, switches to it, and only then writes files

Source: .claude/commands/implement.md; behaviour of the session, untested

### Requirement: /implement applies the permanent rules
The system SHALL make `/implement` answer in the user's language (French by default), run the personal-identifier scanner on every file it writes before each commit, run only the suites touched while working (quiet, stopping at the first failure), run the runner's targeted option before each commit, add the CHANGELOG line and the documentation updates in the same commit as the change they accompany, use parallel agents only for work on distinct files and end with a single final message. It SHALL NOT push, merge, run the branch-finishing script, bypass a hook, set the owner bypass variable, or write a person's, team's or project's name in any file.

#### Scenario: Commit
- **WHEN** a unit of work is ready to commit
- **THEN** the scanner reports no identifier in the written files, the targeted run is green, the CHANGELOG line is in the same commit, and nothing is pushed

#### Scenario: Parallel work
- **WHEN** two tasks touch distinct files
- **THEN** they may be given to agents launched in one message, and the user receives one final message

#### Scenario: Test needing the network
- **WHEN** a commit stumbles on a test that needs the network
- **THEN** `/implement` does not work around it, stops and gives the user the exact command to run in the Terminal

Source: .claude/commands/implement.md; the forbidden actions named in the body: tests/workflow_commands/test_workflow_commands.py; the session behaviour is untested

### Requirement: /implement stops at manual steps
The system SHALL make `/implement` stop and hand over to the user, with the command and its purpose, at every step reserved to the user: commands that contact the real Jira, the flow import and comparison, the knowledge import's import, verify and status, the database scripts, any calculation with the database as source, book conversion, sorting and indexing, edits of the settings file that the change assigns to the user, and the posture evaluation set (whose cost it SHALL announce first). It SHALL NOT run any of these, SHALL NOT read the forbidden content folders, the sensitive flow-folder files, the backups or the journal, and SHALL NOT edit the session instructions file unless the change's tasks require it and the evaluation cost was announced and accepted.

#### Scenario: Task needing a database import
- **WHEN** a task requires an import into the database
- **THEN** `/implement` prints the command and its purpose, does not run it, and waits for the user

#### Scenario: Task needing the evaluation set
- **WHEN** a task requires the evaluation set
- **THEN** `/implement` announces its cost and runs nothing until the user agrees

Source: .claude/commands/implement.md; untested beyond the header and body checks of tests/workflow_commands/test_workflow_commands.py

### Requirement: Tasks are ticked only when a test covers them
The system SHALL make `/implement` and `/close` tick a task only when the suite the task names passes in the current state. A task that names no suite SHALL stay unticked, with a short reason given by the user (a user step, a manual check). Neither command SHALL tick a task on its own judgement.

#### Scenario: Covering suite passes
- **WHEN** the suite named by a task passes
- **THEN** the task may be ticked

#### Scenario: No test
- **WHEN** a task names no suite
- **THEN** it stays unticked and carries the reason given by the user

Source: .claude/commands/implement.md, .claude/commands/close.md; untested

### Requirement: /close closes a change and hands the merge to the user
The system SHALL provide a `/close <change>` slash command that, in order, checks and ticks the tasks under the rule above, updates the status line at the top of the application document, closes the matching entry of the evolutions document when there is one, adds the CHANGELOG line under today's date, archives the change with the OpenSpec archive command when every unticked task carries a reason and the user confirms, marks the change's job `done` in the work queue with the queue reader and lists the jobs the change unblocks, runs the reader's archive command and shows what left the queue, commits after a targeted green run, and finally prints the branch-finishing command for the user to type in the Terminal. It SHALL NOT run the finishing script, push or merge, SHALL NOT archive when an unticked task has no reason, SHALL NOT invent a queue job when the change has none (it says so instead), and SHALL NOT create an evolutions entry when none matches the change.

#### Scenario: All tasks covered
- **WHEN** every task's suite passes and the user confirms
- **THEN** the change is archived, the queue job is `done`, a commit holds the archive, the documents and the CHANGELOG line, and the output ends with the finishing command, not run

#### Scenario: Unticked task without reason
- **WHEN** a task is unticked and has no reason
- **THEN** `/close` does not archive and names the task

#### Scenario: No queue job
- **WHEN** no queue job names the change
- **THEN** `/close` says so and edits no job

Source: .claude/commands/close.md; the session behaviour is untested

### Requirement: /add-books prepares the configuration of new books
The system SHALL provide an `/add-books <files>` slash command that, from a list of book file names given by the user, proposes for each book its domains (for the user to validate), its classification line, and its catalogue entry (title, authors, year when known, and the to-verify flag when a value is deduced from the file name), and writes them once validated. When a title exists in both EPUB and PDF, it SHALL keep the EPUB and add the PDF to the exclusions with its reason. It SHALL apply the items of the section "À traiter au prochain ajout de livres" of the library gaps document, and SHALL remove an item from that section only after the user confirms that the commands it needs have run. It SHALL add the CHANGELOG line and, when a book fills a topic of the gaps document, update that document. It SHALL NOT read book contents or the library, image and content folders, SHALL NOT copy text from a book, SHALL NOT decide domains without the user's validation, and SHALL NOT commit.

#### Scenario: Same title in two formats
- **WHEN** the list holds an EPUB and a PDF of the same title
- **THEN** the classification line is that of the EPUB's Markdown and the PDF is added to the exclusions with the reason

#### Scenario: Author deduced from the file name
- **WHEN** the author can only be deduced from the file name
- **THEN** the catalogue entry carries the to-verify flag

#### Scenario: Pending section-4 item
- **WHEN** the gaps document lists an item to handle at the next book addition
- **THEN** `/add-books` applies its configuration part, gives the commands it needs, and keeps the item until the user confirms they ran

Source: .claude/commands/add-books.md; no commit pre-approved and the body saying not to commit: tests/workflow_commands/test_workflow_commands.py (Commandes.test_add_books_ne_pre_approuve_aucun_commit, test_add_books_dit_de_ne_pas_commiter); the rest of the session behaviour is untested

### Requirement: /add-books gives the commands without running them
The system SHALL make `/add-books` state that the daily watch run imports into the database after indexing, so that a change to the book catalogue makes the book replaced in the database at the next daily run, and SHALL print, in order, the commands for the user to run: the conversion dry run, the conversion, the sort by domain, the indexing, the import dry run, the import and the verification. It SHALL NOT run the conversion, the sort, the indexing or the import.

#### Scenario: Commands printed
- **WHEN** the configuration of the new books is written
- **THEN** the output lists the commands in that order, says the catalogue change reaches the database at the next daily run, and none of the commands was run

Source: .claude/commands/add-books.md; the body naming the conversion, sort and indexing scripts: tests/workflow_commands/test_workflow_commands.py

### Requirement: Workflow command files state and respect their limits
The system SHALL keep the workflow command files under the commands folder, written in English and serving the user in the user's language, and SHALL include a test that checks, for `/implement`, `/close`, `/add-books`, `/next` and `/start`, that the file exists, that its header has a description, that its header pre-approves none of the forbidden launches (real Jira subcommands, flow import and compare, knowledge import's import, verify and status, database scripts and clients, database-sourced calculations, book conversion, sorting and indexing, the branch-finishing script, the owner bypass variable, push, merge, hook bypass, the evaluation set), that its header pre-approves no launcher without a restriction (a bare shell, Python or uv launcher, or the shell tool without a pattern), that its body names the forbidden actions, and that its body says it serves the user in the user's language. The test SHALL also check that `/next` pre-approves only the queue reader's next command and that `/implement` and `/close` do not pre-approve the queue reader's done command. The command files SHALL NOT contain a person's, team's or project's name.

#### Scenario: Forbidden pre-approval
- **WHEN** a workflow command header pre-approves the knowledge import
- **THEN** the test fails and names the command and the pattern

#### Scenario: Too broad a launcher
- **WHEN** a workflow command header pre-approves a bare launcher or the shell tool without a pattern
- **THEN** the test fails and names the command

#### Scenario: Compliant files
- **WHEN** the five command files respect the rules
- **THEN** the test passes

Source: tests/workflow_commands/test_workflow_commands.py; the absence of names is left to the pre-commit hook

### Requirement: /start launches one job of the work queue
The system SHALL provide a `/start <id>` command that first checks the queue with the reader's check command and reads the job's entry and its prose description, and SHALL refuse to start, saying why, a job that is unknown, not `ready`, has a dependency that is not `done`, or has a not-before date later than today; it SHALL ask the user to confirm non-empty start conditions, and to switch model when the job's model differs from the session's, before writing anything. It SHALL never write on `main`: from `main` it creates the job's branch first (a `chore/<id>-<slug>` branch for a direct-prompt job, the branch of `/implement` for an OpenSpec job), and it SHALL stop on a dirty working tree. A direct-prompt job SHALL be done from its description; an OpenSpec job with a change SHALL follow the `/implement` instructions; an OpenSpec job without a change SHALL have the change written by the spec-writer agent, validated, and reviewed by the user before any implementation. When the work is committed and green, the command SHALL mark the job `done` on the branch with the reader's done command, run the check, name the jobs this unblocks and commit, then print `bash tools/finish_branch.sh` for the user. It SHALL NOT push, merge, run the finishing script, reorder the queue, change a job's estimate, model or dependencies, pre-approve the done command, or fix a model in its header.

#### Scenario: Job not startable
- **WHEN** the user starts a job that is blocked, done, waiting for a dependency or before its start date
- **THEN** the command says why and writes nothing

#### Scenario: Job started from main
- **WHEN** the user starts a ready direct-prompt job while on `main`
- **THEN** the job's branch is created before any write, and the job is marked `done` on that branch before the finishing command is printed

Source: tests/workflow_commands/test_workflow_commands.py (test_start_verifie_le_travail_avant_de_le_lancer, test_start_ne_fixe_pas_le_modele, header checks); the session behaviour itself is untested

### Requirement: /audit checks the repository without changing it
The system SHALL provide an `/audit` slash command with a default end-of-session mode and a full mode chosen by its argument. Both modes SHALL be read-only: they SHALL write only the dated audit report and the file holding the commit reached at the end of the pass, both in the local, Git-ignored audit folder, SHALL make no other edit, move, deletion or commit, and SHALL run no database command, Jira tool, evaluation set or test suite. The default mode SHALL check, in order, the state for the night (branch, status, unpushed commits, unmerged branches, stash, and first any file read by the daily watch that differs from `main`), the unarchived OpenSpec changes, the documentation and CHANGELOG of the files changed since the last audit, the books without a complete catalogue entry, the identifier scanner on the changed files, and leftover backup or temporary files by name. Book names SHALL be compared after Unicode NFC normalization, as the indexer does. The full mode SHALL add one read-only agent per domain (documentation, code, tests, configuration) and merge their findings into one report. Every finding SHALL be numbered with an action, a proof and a risk; a point already covered by an OpenSpec change in progress SHALL be reported as covered, not as a finding. The command SHALL NOT handle any finding before the user chooses the numbers, SHALL NOT read the forbidden content folders, and SHALL NOT write a team, project or person name.

#### Scenario: Book name in another Unicode form
- **WHEN** a mapped book name and its catalogue key differ only by their Unicode form
- **THEN** the book is not reported as lacking a catalogue entry

#### Scenario: End of the pass
- **WHEN** the audit ends
- **THEN** the message gives counts by risk, the main findings and the report path, and asks which numbers to handle, having handled none

Source: .claude/commands/audit.md; NFC comparison: tests/workflow_commands/test_workflow_commands.py (test_audit_compare_les_noms_de_livres_apres_normalisation_unicode); header (forbidden launches, wide launchers, writes limited to the audit folder, no commit, test suite or evaluation) and read-only body: tests/workflow_commands/test_workflow_commands.py (Commandes, test_audit_*); the session behaviour is untested

