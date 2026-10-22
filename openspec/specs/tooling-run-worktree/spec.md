# tooling-run-worktree Specification

## Purpose
The system SHALL keep a separate run tree, a detached worktree at the tip of main, whose code the scheduled jobs and the library server run, so the development checkout can be on any branch.

## Requirements

### Requirement: Create the run tree detached at the tip of main
The system SHALL provide a run-tree script whose create subcommand adds, beside the development checkout, a Git worktree detached at the tip of local `main`, at a configurable location. It SHALL create no branch and SHALL NOT link or copy a content folder. An existing valid run tree SHALL be reported as already present and left unchanged. It SHALL NOT overwrite, move or delete an existing folder. Untested until implemented.

#### Scenario: Creation
- **WHEN** the create subcommand runs and no run tree exists
- **THEN** a worktree detached at the tip of `main` exists at the run-tree location, no branch was created, its content folders hold only their tracked placeholders, the output says "run_worktree: created" in English, and the exit code is 0

#### Scenario: Already present
- **WHEN** the create subcommand runs and the run tree exists, detached on an ancestor of `main`
- **THEN** the output says "already present", nothing changes and the exit code is 0

#### Scenario: Folder occupied
- **WHEN** a folder that is not the run tree exists at the run-tree location
- **THEN** the exit code is 4, the message says the folder exists and is not the run tree, and the folder is untouched

### Requirement: Report the run tree state without changing it
The system SHALL provide a status subcommand that reports whether the run tree is missing, clean at the tip of `main`, behind `main` by fast-forward, on a branch, off the history of `main`, or holding local changes, each with its exit code of design D3. It SHALL NOT fetch, update, switch, clean or write anything. Untested until implemented.

#### Scenario: Behind main
- **WHEN** `main` has a commit that the run tree's detached head does not have and the run tree is clean
- **THEN** the status says "behind main", the exit code is 8, and the run tree's head is unchanged

#### Scenario: Missing
- **WHEN** no run tree exists
- **THEN** the exit code is 4 and nothing is created

### Requirement: Update the run tree by fast-forward only
The system SHALL provide an update subcommand that moves the detached run tree to the tip of local `main` only when its commit is an ancestor of it and it holds no modified, staged or untracked non-ignored file; otherwise it SHALL refuse with the code of design D3 and change nothing. It SHALL NOT reset, stash, clean, force a checkout, switch to a branch, fetch, or remove and recreate the tree. Untested until implemented.

#### Scenario: Behind main
- **WHEN** the run tree is clean and detached on an ancestor of `main`
- **THEN** its head becomes the tip of `main`, the output says "updated" and the exit code is 0

#### Scenario: Local change
- **WHEN** a tracked file of the run tree is modified
- **THEN** the exit code is 5, the message says there are local changes in the run tree, and the file and the head are unchanged

#### Scenario: On a branch
- **WHEN** the run tree has a branch checked out
- **THEN** the exit code is 6 and nothing changes

#### Scenario: Forbidden commands
- **WHEN** the script text is scanned outside comments
- **THEN** it holds no reset, clean, stash, forced checkout, worktree removal or prune

### Requirement: Postpone the update around a scheduled run
The system SHALL postpone the update (run-worktree design D3), naming the job and the update command, while the watch lock or a run marker of the backup or off-site jobs is held, at any hour. It SHALL also postpone it, from a configurable morning start to a configurable end of the morning period, while the morning runs of the day are not finished as safe-branch-finish design D2 defines: the record of the day's watch run holds today's date and a final state, and the backups folder holds the plain dated folder of today; a missing backups folder makes the backup part not count. Only when that state cannot be read (safe-branch-finish design D3) SHALL it postpone from the morning start until a configurable fallback time, then go on with the information line of safe-branch-finish design D8. When the watch part holds the update, the message SHALL say why it waits and which marker is involved, named generically, and give the command to resume once the watch is unblocked (safe-branch-finish design D8). Held and stale follow the one rule of run-worktree design D12 and D14; a stale one SHALL be reported and ignored. The folders SHALL be found through the shared lab-paths resolution. It SHALL NOT postpone on a fixed time window when the state can be read, SHALL NOT wait, retry on its own, or create, take or remove a lock or marker, SHALL NOT write, rename or remove the record of the day's watch run, and SHALL NOT list the backups folder, read a file in it or print its path. Tested by the `run_worktree` suite.

#### Scenario: Watch running
- **WHEN** the update runs while the watch lock exists and holds the identifier of a live process, recently created
- **THEN** the exit code is 7, the message says a scheduled run of the watch is in progress and gives the update command, and the head is unchanged

#### Scenario: Off-site copy running
- **WHEN** the update runs while the off-site copy's marker exists and holds the identifier of a live process, recently created
- **THEN** the exit code is 7, the message names the off-site copy, and the head is unchanged

#### Scenario: Lock left by a dead process
- **WHEN** the watch lock exists, its process no longer exists, and the morning runs of the day are finished
- **THEN** the output says the watch's run marker is stale and ignored, the update proceeds, and the lock folder is still there afterwards

#### Scenario: Marker too old
- **WHEN** the backup's marker holds a live process but is older than its configurable maximum age, and the morning runs of the day are finished
- **THEN** the output says the backup's run marker is stale and ignored, and the update proceeds

#### Scenario: Marker in creation
- **WHEN** a marker folder exists without a process identifier and is younger than its maximum age
- **THEN** the exit code is 7 and the head is unchanged

#### Scenario: Inside the window
- **WHEN** the update runs at a time inside the former morning window, no lock or marker exists, the record of the day's watch run holds today's date and a finished state, and today's dated backup folder exists
- **THEN** the update proceeds and no window is named, since the windows no longer postpone it

#### Scenario: Backup of the day missing
- **WHEN** the update runs after the morning start, the watch record is finished for today, and the backups folder exists without today's plain dated folder, a labelled folder of today being present
- **THEN** the exit code is 7, the message is the "morning not finished" key phrase of safe-branch-finish design D8 naming the backup, and the head is unchanged

#### Scenario: Watch record of another day
- **WHEN** the update runs after the morning start and the watch record holds yesterday's date
- **THEN** the exit code is 7 and the message names the watch

#### Scenario: Watch reported or started
- **WHEN** the update runs after the morning start and today's watch record says reported or started, with no lock held
- **THEN** the exit code is 7 and the message names the watch

#### Scenario: Waiting on a watch that does not finish
- **WHEN** the update runs after the morning start, no lock is held, the backup of the day is present, and the watch record says reported for today
- **THEN** the exit code is 7, the error output holds the "morning not finished" key phrase naming the watch, then the "waiting reason" line of safe-branch-finish design D8 naming the record of the day's watch run generically with the state reported, then the "resume command" line with the update command, and it holds neither the record's file name nor a path of the lab data folder

#### Scenario: Before the morning start
- **WHEN** the update runs before the morning start, no lock or marker is held, and today's watch record does not exist
- **THEN** the update proceeds

#### Scenario: State unreadable before the fallback time
- **WHEN** the update runs after the morning start and before the fallback time, and the watch record is absent or unreadable
- **THEN** the exit code is 7 and the message is the "state unreadable, before the fallback" key phrase with the fallback time

#### Scenario: State unreadable after the fallback time
- **WHEN** the update runs after the fallback time, the watch record is unreadable, and the backup of the day is present
- **THEN** the output holds the "state unreadable, after the fallback" information line and the update proceeds

#### Scenario: No backups folder
- **WHEN** the backups folder does not exist and the watch record is finished for today
- **THEN** the backup part does not count and the update proceeds

#### Scenario: Nothing created or removed
- **WHEN** every case of the suite has run
- **THEN** the lock and marker folders, the watch record and the backups folder present after each case are exactly those present before it, unchanged, and the script text, outside comments, creates or removes none of them

#### Scenario: Same maximum age as the run script
- **WHEN** the default maximum age of the watch lock, the default end of the morning period and the list of final states in the run-tree script are compared with the lock's maximum age, the latest time and the states that end the day in the watch run script
- **THEN** they are equal

### Requirement: Prepare the dependencies of the new code
The system SHALL, after a creation and after every accepted update, moved or already at the tip, prepare from the run tree the locked dependencies of every script that a scheduled job or the library server launches, so that the next scheduled run needs no network. A failure SHALL give the code and key phrase of design D3 and leave the head where it is. It SHALL NOT change a lock file or a tracked file, nor reset the head. Untested until implemented.

#### Scenario: Update with preparation
- **WHEN** an update moves the head and the dependency tool succeeds for every scheduled script
- **THEN** the tool was called once per script from the run tree, in locked mode, and the exit code is 0

#### Scenario: Preparation fails
- **WHEN** the dependency tool fails for one script after the head moved
- **THEN** the exit code is 9, the message says the dependencies are not prepared and gives the update command, the head stays at the tip of `main`, and no tracked file changed

#### Scenario: Retry after a failed preparation
- **WHEN** the run tree is already at the tip of `main` after a failed preparation and the update runs again
- **THEN** the output says up to date, the preparation runs again, and the exit code is 0 when it succeeds

### Requirement: Run-tree script codes, key phrases and language
The system SHALL give the run-tree script the exit codes and key phrases of design D3, print in French by default and in English with the shared language option, and print every refusal on the error output, prefixed with the script name. It SHALL NOT give one exit code to two outcomes, and SHALL NOT print a content path or a file content. Untested until implemented.

#### Scenario: English refusal
- **WHEN** the update runs with the English language and the run tree holds local changes
- **THEN** the error output holds "run_worktree: local changes in the run tree" and the exit code is 5

#### Scenario: Usage
- **WHEN** the script is started without a subcommand or with an unknown one
- **THEN** the exit code is 2 and nothing changes

### Requirement: Scheduled jobs and the library server run the code of the run tree
The system SHALL make every scheduler template launch its script through a lab-folder link, and SHALL make the links, including the library server's, resolve into the run tree, so that switching the code tree changes the links only. A template SHALL NOT name the development checkout or the run tree. After an update, the system SHALL print that the running library server keeps its old code until the next session. Untested until implemented.

#### Scenario: Templates scanned
- **WHEN** every scheduler template of the repository is rendered, the watch, watch catch-up, backup, off-site copy, off-site restore-test and doctor templates included
- **THEN** each program path is a lab-folder link and none names a code-tree folder

#### Scenario: Catch-up job after a switch
- **WHEN** the links are switched to the run tree and the watch catch-up template is rendered
- **THEN** its program is the same `watch.sh` link as the watch template's, so it runs the run tree's code without being reloaded

#### Scenario: Server reminder
- **WHEN** an update moves the run tree's head
- **THEN** the output holds the library-server reminder of design D3

### Requirement: Content is read and written in the content root
The system SHALL make each scheduled entry point set the content root, by default the development checkout, and SHALL make the tools it runs read and write the content folders, the local settings and the outputs the dashboard reads in the content root, and tracked code and settings in the code root. A tool SHALL NOT derive a content path from its own location. Untested until implemented.

#### Scenario: Run from the run tree
- **WHEN** a scheduled watch run starts from the run tree with the development checkout as content root
- **THEN** new articles land in the content root's watch folder and the run tree's content folders still hold only their placeholders

#### Scenario: Tracked settings differ
- **WHEN** the tracked watch configuration differs between the run tree and the development checkout
- **THEN** the run tree's version is used

#### Scenario: Component check from the run tree
- **WHEN** a scheduled watch run from the run tree reaches the component check
- **THEN** the component tool launched is the run tree's, it reads the inventory and lock files of the run tree, and its state is written in the lab data folder, not in either tree

### Requirement: The run-tree script is testable without the real lab folder
The system SHALL include a shell suite, listed in the runner, that runs the run-tree script on temporary repositories with a temporary bare remote, the run-tree location, the lab data folder and the clock replaced through environment variables. The suite SHALL NOT read or change the real lab folder, the real run tree or the real data folder. Untested until implemented.

#### Scenario: Suite run
- **WHEN** the runner runs the run-tree suite
- **THEN** every case runs in a temporary folder, one case per exit code, and the suite reports its counts in the runner's shell format

### Requirement: The run-tree script reads the morning state through the shared module
The system SHALL make the run-tree script read the watch record and today's dated backup folder through the shared morning-state module (morning-guard design D1), its window, fallback, final states, codes and key phrases unchanged. It SHALL NOT keep a second reading of those sources, SHALL NOT adopt the finishing guard's stricter criterion, and SHALL NOT change any outcome of its suite. Untested until implemented (suite `run_worktree`).

#### Scenario: Existing cases
- **WHEN** the run-tree suite runs after the change, its cases unchanged
- **THEN** every case passes

#### Scenario: Watch failed, run tree updated
- **WHEN** the update runs after the morning start, today's watch record says `echoue`, today's backup folder exists and no lock or marker is held
- **THEN** the update proceeds as before, the off-site copy and the dump count playing no part
