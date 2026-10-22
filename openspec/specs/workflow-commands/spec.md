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
The system SHALL make `/implement` answer in the user's language, scan written files for personal identifiers and run the targeted runner before each commit, run only touched suites, keep documentation in the commit of its change, use parallel agents only on distinct files and end with one final message. It SHALL NOT add a CHANGELOG entry, push, merge, run the finishing script, bypass a hook, set the owner bypass variable or write a person's, team's or project's name.

#### Scenario: Commit
- **WHEN** a unit of work is ready to commit
- **THEN** the scanner reports no identifier in the written files, the targeted run is green, the documentation is in the same commit, `CHANGELOG.md` is unchanged, and nothing is pushed; the former demand of a CHANGELOG line in the same commit disappears

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
The system SHALL provide a `/close <change>` command that, in order, ticks tasks under the tick rule, updates the application document's status line, syncs the sub-issues of the feature naming this change through the write tool, archives the change, closes that feature, commits after a targeted green run and prints the finishing command. It SHALL NOT add a CHANGELOG entry, touch an evolutions document, run the finishing script, push or merge.

#### Scenario: All tasks covered
- **WHEN** every task's suite passes, no user-step sub-issue is open and the user confirms
- **THEN** the change is archived, the feature is closed with Status `Done`, a commit holds the archive and the status line with `CHANGELOG.md` unchanged, and the output ends with the finishing command, not run; the former CHANGELOG line in that commit disappears

#### Scenario: User steps remain
- **WHEN** the change is archived and a user-step sub-issue of its feature is open
- **THEN** the feature stays open with Status `In progress` and the command names the open sub-issue

#### Scenario: Unticked task without reason
- **WHEN** a task is unticked and has no reason
- **THEN** `/close` does not archive and names the task

#### Scenario: No feature
- **WHEN** no feature names the change
- **THEN** `/close` says so and writes nothing to GitHub

### Requirement: /add-books prepares the configuration of new books
The system SHALL provide an `/add-books <files>` command that, from book file names, proposes each book's domains, classification line and catalogue entry (to-verify flag on values deduced from the file name), and writes them once validated, keeping the EPUB over a PDF of the same title and excluding the PDF with its reason. It SHALL NOT read book contents or content folders, copy book text, decide domains alone, add a CHANGELOG entry or commit.

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
The system SHALL keep the workflow command files under the commands folder, written in English and serving the user in the user's language, and SHALL include a test that checks, for `/implement`, `/close`, `/add-books`, `/next` and `/start`, that the file exists, that its header has a description, that its header pre-approves none of the forbidden launches (real Jira subcommands, flow import and compare, knowledge import's import, verify and status, database scripts and clients, database-sourced calculations, book conversion, sorting and indexing, the branch-finishing script, the owner bypass variable, push, merge, hook bypass, the evaluation set, the roadmap import tool), that its header pre-approves no launcher without a restriction (a bare shell, Python or uv launcher, or the shell tool without a pattern), that its body names the forbidden actions, and that its body says it serves the user in the user's language. The test SHALL also check that `/next` pre-approves only the queue reader's next command, and that no command header pre-approves the GitHub write tool or any `gh` command. The command files SHALL NOT contain a person's, team's or project's name.

#### Scenario: Forbidden pre-approval
- **WHEN** a workflow command header pre-approves the knowledge import
- **THEN** the test fails and names the command and the pattern

#### Scenario: Write tool pre-approved
- **WHEN** the header of `/start` or `/close` pre-approves the GitHub write tool or a `gh` command
- **THEN** the test fails and names the command

#### Scenario: Too broad a launcher
- **WHEN** a workflow command header pre-approves a bare launcher or the shell tool without a pattern
- **THEN** the test fails and names the command

#### Scenario: Compliant files
- **WHEN** the five command files respect the rules
- **THEN** the test passes

### Requirement: /start launches one job of the work queue
The system SHALL provide a `/start <id>` command that runs the queue reader's check and show commands first, and SHALL refuse, saying why and writing nothing, a feature that is unknown, has an open blocker, is before its not-before date, or whose Status is not `Ready` outside the resume case. It SHALL ask the user to confirm non-empty conditions, and to switch model when the feature's differs, before any write.

#### Scenario: Job not startable
- **WHEN** the user starts a feature that is `Todo`, closed, blocked by an open feature or before its not-before date
- **THEN** the command says why and writes nothing, on GitHub or in the repository

#### Scenario: Job started from main
- **WHEN** the user starts a `Ready` direct-prompt feature while on `main`
- **THEN** the job's branch is created before any write, the Status becomes `In progress`, and the feature is closed through the write tool before the finishing command is printed

#### Scenario: In progress outside its batch branch
- **WHEN** the user starts an `In progress` feature while the session is on `main` or on a branch that is not the one a batch names for it
- **THEN** the command says why and writes nothing

### Requirement: /audit checks the repository without changing it
The system SHALL provide a read-only `/audit` command with a default end-of-session mode and a full mode adding one read-only agent per domain. The default mode SHALL check the state for the night, the unarchived changes, the documentation of the files changed since the last audit and that the frozen CHANGELOG did not change, catalogue gaps with book names compared after Unicode NFC normalization, the identifier scanner and leftover files.

#### Scenario: Book name in another Unicode form
- **WHEN** a mapped book name and its catalogue key differ only by their Unicode form
- **THEN** the book is not reported as lacking a catalogue entry

#### Scenario: End of the pass
- **WHEN** the audit ends
- **THEN** the message gives counts by risk, the main findings and the report path, and asks which numbers to handle, having handled none

#### Scenario: Changed command without a CHANGELOG line
- **WHEN** a command file changed since the last audit and the CHANGELOG has no line for it
- **THEN** no finding is raised for the missing line; the former check of a CHANGELOG line per changed file disappears

#### Scenario: CHANGELOG changed
- **WHEN** `CHANGELOG.md` changed since the last audit
- **THEN** the report lists it as a finding with its proof and risk

Source: .claude/commands/audit.md; NFC comparison: tests/workflow_commands/test_workflow_commands.py (test_audit_compare_les_noms_de_livres_apres_normalisation_unicode); header (forbidden launches, wide launchers, writes limited to the audit folder, no commit, test suite or evaluation) and read-only body: tests/workflow_commands/test_workflow_commands.py (Commandes, test_audit_*); the session behaviour is untested

### Requirement: /start reports the move into the current release
The system SHALL make `/start` report to the user the line the write tool prints, when it sets the Status `In progress`, about the move into the current release or the absence of one. `/start` SHALL NOT move a feature or a sub-issue to a milestone by any other command, and SHALL NOT edit the current-release setting.

#### Scenario: Release configured
- **WHEN** the write tool prints that the feature and its sub-issues moved to the current release
- **THEN** `/start` tells the user the milestone they moved to

#### Scenario: Command file
- **WHEN** the `/start` command file is read
- **THEN** it says to report the release line of the write tool and forbids editing the release setting and moving a milestone otherwise

### Requirement: /close closes agent sub-issues left with a reason
The system SHALL make `/close`, when an agent sub-issue stays open and every unticked task of its group carries a reason, propose close-step with that reason and run it only after the user's confirmation. It SHALL NOT close a sub-issue whose group holds an unticked task without a reason, nor close one without the user's yes.

#### Scenario: Group with reasoned tasks
- **WHEN** a group keeps one unticked task that carries a reason and its agent sub-issue is open
- **THEN** `/close` proposes close-step with that reason and waits for the user's yes

#### Scenario: Task without a reason
- **WHEN** a group keeps an unticked task without a reason
- **THEN** `/close` proposes no close-step for its sub-issue and names the task

### Requirement: /start and /close handle an unknown GitHub state
The system SHALL make `/start` and `/close`, when the write tool exits with code 8, stop, show the check command the tool printed, and send no further GitHub write until the user has checked. They SHALL NOT report that write as not sent, nor run it again before the check.

#### Scenario: Write without an answer
- **WHEN** `close-feature` exits with code 8 during `/close`
- **THEN** `/close` stops, shows the check command, and runs no other write-tool command

#### Scenario: Command files
- **WHEN** the `/start` and `/close` command files are read
- **THEN** each names exit code 8 of the write tool and says to stop and check before any further write

### Requirement: Commit instructions carry no variable prefix
The system SHALL make every workflow command file, and the session instructions file when it gives a commit instruction, tell to commit with `git commit` alone, the variables a commit needs coming from the session's environment. It SHALL include a test that fails when one of those files puts a variable assignment before `git commit`. The commands SHALL NOT set the after-commit mode variable of the post-commit hook.

#### Scenario: Prefixed commit
- **WHEN** a command file says to commit with `PMZILLA_NO_EVALS=1 git commit`
- **THEN** the test fails and names the file

#### Scenario: Bare commit
- **WHEN** every command file and the session instructions file say `git commit` with no assignment before it
- **THEN** the test passes

#### Scenario: Commit in a worktree
- **WHEN** a session opened in a worktree prepared by the worktree script commits
- **THEN** the commit is a bare `git commit` and the name guard of the pre-commit hook finds the workspace's list through the session's environment

### Requirement: The CHANGELOG is frozen
The system SHALL keep `CHANGELOG.md` as a frozen history ending on 2026-10-13, whose introduction says the history continues in the GitHub releases (design D1). It SHALL include a test that fails, naming the heading, when a dated heading later than that date appears or the introduction loses that sentence. No command, agent, skill or session instruction SHALL tell to add, rewrite or remove an entry.

#### Scenario: New dated entry
- **WHEN** a `## 2026-10-14` heading is added to the CHANGELOG
- **THEN** the freeze test fails, names that heading and prints no entry text

#### Scenario: Frozen file
- **WHEN** the CHANGELOG holds the frozen introduction and no heading after 2026-10-13
- **THEN** the freeze test passes

#### Scenario: Existing entries kept
- **WHEN** the freeze is applied
- **THEN** every entry dated up to 2026-10-13 is unchanged, byte for byte

### Requirement: Every mention of the CHANGELOG says it is frozen
The system SHALL include a test that reads the command, agent and skill files and the session instructions, and fails, naming file and line, when a line names the CHANGELOG without the word `frozen` (design D2). The test SHALL also fail when a changelog update command or skill exists. The system SHALL NOT provide a command, skill or hook that writes changelog entries.

#### Scenario: Leftover instruction
- **WHEN** a command file still asks for "its CHANGELOG line" in the commit
- **THEN** the test fails and prints the file and the line number

#### Scenario: Former command restored
- **WHEN** the changelog update command file exists again
- **THEN** the test fails and names it

#### Scenario: Compliant files
- **WHEN** every line naming the CHANGELOG says it is frozen and no changelog command or skill exists
- **THEN** the test passes

### Requirement: /close archives and closes the feature only when complete
The system SHALL make `/close` sync the sub-issues before the archive, archive only when every unticked task carries a reason and the user confirms, and close the feature only when none of its sub-issues is open, listing the features it unblocks; otherwise the feature stays `In progress` and its open user steps are named. It SHALL NOT invent a feature when none names the change, nor write to GitHub other than through the write tool.

#### Scenario: Sync before the archive
- **WHEN** `/close` runs on a change named by a feature
- **THEN** the sub-issues are synced through the write tool before the archive command runs

#### Scenario: Unblocked features
- **WHEN** closing the feature leaves another open feature with every blocker closed
- **THEN** `/close` names that feature for the user to set `Ready` and does not change its Status

### Requirement: /add-books handles the gaps document
The system SHALL make `/add-books` apply the configuration part of each item that the library gaps document lists for the next book addition, give the commands the item needs, remove the item only after the user confirms they ran, and update that document when a book fills one of its topics. It SHALL NOT remove an item without that confirmation.

#### Scenario: Book fills a gap
- **WHEN** a new book covers a topic listed in the gaps document
- **THEN** `/add-books` says so and updates that document, and adds no CHANGELOG entry

#### Scenario: Item not confirmed
- **WHEN** the user has not confirmed that an item's commands ran
- **THEN** the item stays in the gaps document

Source: .claude/commands/add-books.md; untested

### Requirement: /audit writes only its report and handles nothing
The system SHALL make `/audit` write only the dated report and the reached-commit file in the ignored audit folder, number every finding with an action, a proof and a risk, report a point covered by an open change as covered, and wait for the user to choose numbers. It SHALL NOT edit, move, delete or commit, run a database command, Jira tool, evaluation set or test suite, read the forbidden content folders, or write a team, project or person name.

#### Scenario: Point covered by a change
- **WHEN** a finding is already a task of an open change
- **THEN** the report says "covered by" that change and task instead of listing a finding

#### Scenario: Full mode
- **WHEN** `/audit complet` runs
- **THEN** one read-only agent per domain reports, the findings are merged into one report, and none is handled

Source: .claude/commands/audit.md; header and read-only body: tests/workflow_commands/test_workflow_commands.py (Commandes, test_audit_*); the session behaviour is untested

### Requirement: /start creates the job's branch before writing
The system SHALL make `/start` stop on a dirty working tree and never write on `main`: from `main` it creates the job's branch first, a `chore/<id>-<slug>` branch for a direct-prompt job or the branch of `/implement` for an OpenSpec job. It SHALL then set the Status `In progress` through the GitHub write tool. Untested until implemented.

#### Scenario: Dirty working tree
- **WHEN** the user starts a `Ready` feature while the working tree holds a modified file
- **THEN** the command stops, lists the file, creates no branch and sends no GitHub write

### Requirement: /start runs the job by its method
The system SHALL make `/start` do a direct-prompt job from its description, follow the `/implement` instructions for an OpenSpec job with a change and sync the feature's sub-issues after each commit that completes a group, and have the change of an OpenSpec job without one written by the spec-writer agent, validated and reviewed by the user before any implementation. Untested until implemented.

#### Scenario: OpenSpec job without a change
- **WHEN** the user starts a `Ready` OpenSpec feature whose block names no change
- **THEN** the spec-writer agent writes the change, it is validated, and the command stops for the user's review before any implementation

### Requirement: /start closes the feature and hands over
The system SHALL make `/start`, when the work is committed and green, close the feature through the write tool, name the features this unblocks and print `bash tools/finish_branch.sh` for the user. It SHALL NOT push, merge, run a finishing script, change a rank, an estimate, a model or a dependency, write to GitHub other than through the write tool, pre-approve the write tool, or fix a model in its header.

#### Scenario: Work committed and green
- **WHEN** the job's work is committed and the targeted run is green
- **THEN** the feature is closed through the write tool, the unblocked features are named, and the finishing command is printed, not run

### Requirement: /start resumes a feature started by a batch
The system SHALL make `/start` accept an `In progress` feature when the session is on the branch a batch names for it (design D4, D5). It SHALL then check blockers, the not-before date, conditions and model as for a `Ready` feature, and SHALL NOT create a branch nor set the Status again. On resume it SHALL print the worktree-finishing command of design D12 instead of the branch-finishing one, and SHALL NOT run either.

#### Scenario: Session opened from a batch
- **WHEN** the user runs `/start` on an `In progress` direct-prompt feature in the worktree a batch created, on the branch it named
- **THEN** the command does the job on that branch, sends no Status write, closes the feature as usual, and prints `bash tools/finish_worktree.sh` with that branch, to run from the workspace

#### Scenario: Command file
- **WHEN** the `/start` command file is read
- **THEN** it names the resume rule, the three batch branch forms of design D5, `tools/finish_worktree.sh`, and says not to set the Status again

### Requirement: /batch proposes a batch and waits for the user's yes
The system SHALL provide a `/batch <milestone>` command that runs the queue reader's check and batch commands, then presents the retained features, those set aside with their reason, the unknown-file flags, the shared files and the conditions to confirm (design D6). It SHALL ask for one yes, in which the user may remove features, and SHALL NOT create a worktree or write to GitHub before it. Untested until implemented.

#### Scenario: User removes a feature
- **WHEN** the reader retains three features and the user answers yes without the second one
- **THEN** only the first and the third get a worktree and a Status write

#### Scenario: Conditions not confirmed
- **WHEN** a retained feature has non-empty conditions and the user's yes does not confirm them
- **THEN** that feature gets no worktree and no Status write

### Requirement: /batch refuses what it cannot start
The system SHALL make `/batch` ask for a milestone and run nothing when none is given, and stop, writing nothing, when the session is not on `main`, the reader exits non-zero, the current release is absent, or no feature is retained (design D4, D8, D10). It SHALL NOT fetch or pull, nor start from the reader's snapshot. Untested until implemented.

#### Scenario: No current release
- **WHEN** the reader prints that there is no current release
- **THEN** `/batch` says the setting is empty, creates no worktree and sends no GitHub write

#### Scenario: Not on main
- **WHEN** `/batch` runs in a session on a work branch
- **THEN** it says it runs on `main` only and runs neither the reader nor the worktree script

#### Scenario: GitHub unreachable
- **WHEN** the reader's batch command exits 5
- **THEN** `/batch` reports it and proposes nothing

### Requirement: /batch prepares one worktree per kept feature
The system SHALL make `/batch`, after the yes, take the kept features in rank order and, for each, run the worktree script with the branch the reader named, then set its Status `In progress` through the write tool and report the tool's line about the current release (design D4, D7). It SHALL NOT create two worktrees for one feature.

#### Scenario: Feature of an older milestone
- **WHEN** a kept feature sits in a milestone other than the current release
- **THEN** after its worktree is created, the Status write moves it and its sub-issues into the current release and `/batch` reports the `moved` line

### Requirement: /batch hands over one launch per feature
The system SHALL make `/batch` end with one block per started feature: its folder, branch, launch model, the launch command and prompt of design D5, and the worktree-finishing command of design D12, for the user to run from the workspace once that session has ended. It SHALL NOT launch a session, `claude` or a finishing script, nor open a Terminal.

#### Scenario: Framing and execution in one batch
- **WHEN** a batch starts an OpenSpec feature without change and an OpenSpec feature with a change
- **THEN** the first block gives the framing model and prompt, the second the execution model and the `/start` prompt, each block gives `bash tools/finish_worktree.sh` with its branch as the user's command, and no session nor script is started

### Requirement: /batch handles a refused worktree or write
The system SHALL make `/batch` set a feature aside with no GitHub write when the worktree script refuses because its folder exists or its branch is open elsewhere, and go on. Any other refusal of the worktree script, and any other non-zero exit of the write tool, SHALL stop the batch with the list of worktrees created and features started (design D7). Untested until implemented.

#### Scenario: Folder already there
- **WHEN** the worktree script exits 4 for the second kept feature
- **THEN** that feature gets no Status write and the third one is prepared

#### Scenario: Closed current release
- **WHEN** the write tool exits 7 because the current release is not an open milestone
- **THEN** `/batch` stops, reports the tool's line, and names the worktree already created for that feature

### Requirement: /batch stops on an unknown GitHub state
The system SHALL make `/batch`, when the write tool exits with code 8, stop the whole batch, show the check command the tool printed, and send no further GitHub write until the user has checked. It SHALL NOT report that write as not sent, nor run it again before the check.

#### Scenario: Write without an answer
- **WHEN** the Status write of the first kept feature exits 8
- **THEN** `/batch` shows the check command, prepares no other feature and runs no other write-tool command

### Requirement: /batch never merges, pushes or reshapes the queue
The system SHALL NOT let `/batch` merge, push, run the branch- or worktree-finishing script, remove a worktree or branch, write to GitHub other than through the write tool or with a `gh` command, set a Status other than `In progress`, change a rank, estimate, model, dependency, condition or milestone otherwise, or edit the current-release setting (design D9).

#### Scenario: Command file
- **WHEN** the `/batch` command file is read
- **THEN** its body names each forbidden action of design D9, both finishing scripts among them, exit code 8 with the stop before any further write, and the launches reserved to the user

### Requirement: /batch is a checked command file
The system SHALL include `/batch` in the command files checked by the workflow command test, with the same header and body rules, and SHALL check that its header pre-approves only the reader's check and batch commands, the worktree script and Git's status and rev-parse (design D11), never the write tool nor a `gh` command.

#### Scenario: Write tool pre-approved
- **WHEN** the `/batch` header pre-approves the GitHub write tool or a `gh` command
- **THEN** the test fails and names the command

#### Scenario: Compliant file
- **WHEN** the `/batch` header holds exactly the pre-approvals of design D11 and its body names the forbidden actions and serves the user in the user's language
- **THEN** the test passes

### Requirement: /close and /start check whether the branch changes the edition
The system SHALL make `/close` and `/start`, before they close the feature, list the paths changed on the branch since its merge base with `main` and check them against the include and template rules of the edition manifest (design D19 of `edition-publish-tooling`). When no changed path enters the edition, they SHALL say so and pass no label option.

#### Scenario: Private change only
- **WHEN** every changed path is excluded by the manifest
- **THEN** `/close` says that no path of the edition changed and closes the feature without the option

#### Scenario: End of a /start job
- **WHEN** a job started with `/start` ends and its branch changes a path that the manifest includes
- **THEN** `/start` names the path and proposes the label before `close-feature`, as `/close` does

### Requirement: /close and /start propose the public-edition label
When at least one changed path enters the edition, the system SHALL make `/close` and `/start` name those paths, propose the label `edition:public`, and pass the write tool's public-edition option only after the user's yes. They SHALL NOT add the label through any other command.

#### Scenario: Edition changed
- **WHEN** the branch changes a path that the manifest includes
- **THEN** `/close` names the path, proposes the label and closes the feature with the option only after the user's yes

### Requirement: /doctor runs the diagnostic and explains it
The system SHALL provide a `/doctor` slash command that runs the doctor script without the record option, then explains each check not ok with the next step and the commands for the user to run, in the user's language. It SHALL NOT run a repair, start or load a service, delete a branch or worktree, or run the doctor's scheduled wrapper.

#### Scenario: Problem found
- **WHEN** the doctor reports Ollama down
- **THEN** `/doctor` explains the problem and gives the start command for the user, without running it

#### Scenario: All good
- **WHEN** the doctor exits with code 0 and no warning
- **THEN** `/doctor` says so in one line and runs nothing else

### Requirement: /doctor is a checked command file
The system SHALL include `/doctor` in the command files checked by the workflow command test, with the same header and body rules, and SHALL check that its header pre-approves only the doctor script launch, without the record option, and never the scheduled wrapper.

#### Scenario: Wrapper pre-approved
- **WHEN** the `/doctor` header pre-approves the doctor's scheduled wrapper or the record option
- **THEN** the test fails and names the command

#### Scenario: Compliant file
- **WHEN** the `/doctor` file pre-approves only the doctor script launch and its body names the forbidden actions
- **THEN** the test passes

### Requirement: /audit checks the run tree for the night
The system SHALL make `/audit` report, in its state for the night, the run tree's state read through the run-tree script's status subcommand, as a finding when the run tree is missing, behind `main`, on a branch, off the history of `main` or holding local changes. It SHALL NOT report the development checkout's branch as a risk for the night, and SHALL NOT create or update the run tree.

#### Scenario: Run tree behind main
- **WHEN** the status reports the run tree behind `main`
- **THEN** the audit numbers a finding whose action is the update command for the user, and runs no update

#### Scenario: Development checkout on a work branch
- **WHEN** the development checkout is on a work branch and the run tree is clean at the tip of `main`
- **THEN** the state for the night reports no risk for the scheduled runs

#### Scenario: Command header
- **WHEN** the `/audit` command file is read by the workflow command test
- **THEN** its header pre-approves the status subcommand only, and neither create nor update

### Requirement: /next passes a product filter only for a known product
The system SHALL make `/next` add the reader's product option only when the user names `mothra` or `pmzilla` after the duration, and run the reader over the whole queue otherwise. For any other product it SHALL say the product is unknown, ask again and run nothing. It SHALL NOT drop a blocked feature from the reader's answer nor add one back, and its header SHALL pre-approve only the reader's next command.

#### Scenario: Product named
- **WHEN** the user types `/next 90min pmzilla`
- **THEN** the command runs the reader's next command with the duration and `--product pmzilla`

#### Scenario: No product named
- **WHEN** the user types `/next 2h`
- **THEN** the command runs the reader's next command with the duration only

#### Scenario: Unknown product
- **WHEN** the user types `/next 2h autre`
- **THEN** the command says the product is unknown, asks again and runs nothing

#### Scenario: Reader refuses the product
- **WHEN** the reader exits 2 on a product
- **THEN** the command says so and asks again

Source: .claude/commands/next.md; the header check: tests/workflow_commands/test_workflow_commands.py (test_next_ne_pre_approuve_que_la_sous_commande_next_du_lecteur); the argument handling is untested

### Requirement: /start creates the job's worktree and hands over to a session there
The system SHALL make `/start`, started from the workspace on `main` once the checks of its first step pass, create the job's branch through the worktree script, set the feature `In progress` through the write tool, print the commands that open a session in the new folder and resume with `/start <id>`, labelled as the user's, and stop (finish-under-lock design D7). It SHALL NOT use `git checkout -b`, write or commit in the workspace, or work in the worktree from the workspace session.

#### Scenario: Started from the workspace
- **WHEN** the header and body of the command file are read
- **THEN** the header pre-approves `bash tools/worktree.sh` and not `git checkout -b`, and the body says to stop after the worktree creation and to resume with `/start <id>` in a session opened in the new folder

#### Scenario: Worktree script refuses
- **WHEN** the body is read for the case of a refusal of the worktree script
- **THEN** it says to report the refusal line and stop without changing the Status

### Requirement: /start always hands over the worktree finish
The system SHALL make every final hand-over of `/start` print the worktree-finishing command for the branch, to run from the workspace once the session has ended. It SHALL NOT run a finishing script nor print the direct finishing command as the one to use.

#### Scenario: Hand-over
- **WHEN** the body's hand-over section is read
- **THEN** it prints `bash tools/finish_worktree.sh <branch>` for every job

### Requirement: /implement refuses to start in the workspace on main
The system SHALL make `/implement`, started from the workspace on `main`, refuse with the same hand-over as `/start` (create the worktree with `bash tools/worktree.sh <branch>` and resume in a session opened there), write nothing and change no Status (finish-under-lock design D18).

#### Scenario: Started from the workspace
- **WHEN** the body of the `/implement` command file is read
- **THEN** it says to refuse in the workspace on `main`, names `bash tools/worktree.sh <branch>`, and says to stop without writing
