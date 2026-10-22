# tooling-doctor Specification

## Purpose
The system SHALL provide one read-only, local diagnostic command that reports the health of the lab (database, Ollama, scheduled jobs, backups, disk, branches, run tree) with levels, exit codes and a state file.

## Requirements

### Requirement: One read-only diagnostic command
The system SHALL provide a diagnostic script that runs every check of design D5 and prints one line per check with its level, then the summary line of design D4. It SHALL NOT start, load, unload, pull, delete, prune or repair anything, and SHALL write nothing except its state file when the record option is given.

#### Scenario: Plain run
- **WHEN** the doctor runs without the record option
- **THEN** it prints one line per check and the summary, and no file is created or changed

#### Scenario: Service down
- **WHEN** Ollama does not answer
- **THEN** the doctor reports it as a problem and calls no command that starts it

### Requirement: Levels and exit codes
The system SHALL give each check one level among ok, warning, problem and skipped, a skipped check carrying its reason. It SHALL exit with code 0 when no check is in problem, 1 when at least one is, and 2 on a usage error or when it cannot run, with the key phrases of design D4. It SHALL NOT exit non-zero for warnings or skipped checks alone.

#### Scenario: Warnings only
- **WHEN** one check is in warning and the others are ok
- **THEN** the summary says "doctor: 1 warning(s)" in English and the exit code is 0

#### Scenario: One problem
- **WHEN** one check is in problem
- **THEN** the summary counts one problem and the exit code is 1

#### Scenario: Unknown option
- **WHEN** an unknown option is given
- **THEN** the exit code is 2 and no check runs

### Requirement: Output options and language
The system SHALL print in French by default or in English through the shared language option, SHALL print the result as JSON in the state-file format with the JSON option, and SHALL print only the checks not ok and the summary with the quiet option. Check identifiers SHALL NOT be translated.

#### Scenario: Quiet run
- **WHEN** the quiet option is given and one check is in warning
- **THEN** only that check's line and the summary are printed

#### Scenario: English
- **WHEN** the English language is chosen and every check passes
- **THEN** the summary is "doctor: all good"

### Requirement: Database check without a database session
The system SHALL report the database as a problem when its configured local host and port refuse a TCP connection, or when the watch run of the day recorded it unreachable or its tables missing. It SHALL NOT authenticate, open a database session or read a password, and SHALL NOT contact a host that is not local.

#### Scenario: Port closed
- **WHEN** nothing listens on the configured database port
- **THEN** the db check is a problem and no database client is invoked

#### Scenario: Tables missing in the watch run
- **WHEN** the port answers and the watch run of the day recorded missing tables
- **THEN** the db check is a problem

### Requirement: Ollama and models check
The system SHALL report Ollama as a problem when its configured local address does not answer the model listing, and SHALL report a problem naming the missing role (embedding or watch triage) when a model named by the repository constants is absent. When Ollama is down, the models check SHALL be skipped. It SHALL NOT pull or remove a model.

#### Scenario: Triage model missing
- **WHEN** the fake Ollama lists the embedding model only
- **THEN** the models check is a problem for the watch-triage model and no pull is requested

#### Scenario: Ollama down
- **WHEN** the fake Ollama does not answer
- **THEN** the ollama check is a problem and the models check is skipped

### Requirement: Scheduled jobs check
The system SHALL check, for each launchd job template of the repository whose rendered file is installed, that the job is loaded, and SHALL report an installed job that is not loaded as a problem naming it. A job not installed SHALL be skipped as not set up. It SHALL NOT load, unload or start any job.

#### Scenario: Installed but not loaded
- **WHEN** the backup job file is installed and the launchd status query fails for it
- **THEN** the launchd check is a problem naming that job, and no load command is called

#### Scenario: Job not installed
- **WHEN** a template has no installed file
- **THEN** that job is skipped as not set up and is not a problem

### Requirement: Watch run of the day
The system SHALL read the watch run of the day from the run record of the watch (design D2), never from the watch log, and SHALL compare the record's date with today's date in Europe/Paris. It SHALL report, with the reason keys of design D13:
- a problem when the lab data folder is not writable or the watch's alert marker holds today's date (the record cannot be written);
- ok when today's record says the run ended without failed step;
- a problem when today's record says failed;
- a problem when today's record says interrupted, or says started while the watch lock does not exist;
- skipped as running when today's record says started and the watch lock exists;
- a problem naming the missed day when, after the configurable latest start time, there is no record of today or today's record says postponed;
- skipped as postponed when today's record says postponed before the latest start time;
- a problem when no record of today exists after the configurable due time.

Before the due time, with no record of today, the check SHALL be skipped as not due yet. A missing, unreadable or other-day record SHALL count as no record of today. It SHALL NOT run the watch, SHALL NOT write the record or the alert marker, SHALL NOT take or remove the watch lock, and SHALL check the data folder's writability without writing to it.

#### Scenario: Failed run
- **WHEN** today's record says failed
- **THEN** the watch check is a problem

#### Scenario: Before the due time
- **WHEN** no record of today exists and the current time is before the due time
- **THEN** the watch check is skipped as not due yet

#### Scenario: Done, whatever the log says
- **WHEN** today's record says done and the watch log is absent or ends with a failed run
- **THEN** the watch check is ok and the log is not read for it

#### Scenario: Postponed during the day
- **WHEN** today's record says postponed and the current time is between the due time and the latest start time
- **THEN** the watch check is skipped with the postponed reason

#### Scenario: Day missed
- **WHEN** the current time is after the latest start time and today's record says postponed, or no record of today exists
- **THEN** the watch check is a problem with the missed-day reason

#### Scenario: Interrupted run
- **WHEN** today's record says started and the watch lock does not exist
- **THEN** the watch check is a problem with the interrupted reason

#### Scenario: Record cannot be written
- **WHEN** the lab data folder is read-only
- **THEN** the watch check is a problem with the record-not-writable reason, and no file is created in the data folder or the logs folder

#### Scenario: Record of yesterday in Paris
- **WHEN** the record holds the previous day's date and the current time is after the due time
- **THEN** the watch check is a problem for a missing run of today

### Requirement: Database backup of the day
The system SHALL report a problem when today's dated database backup folder is missing after the configurable due time, or holds fewer dumps than schemas, checked by file name and count only. It SHALL NOT open, copy or print the name of any file of the backups folder. Before the due time, it SHALL be skipped.

#### Scenario: Short backup
- **WHEN** today's backup folder holds two dumps instead of one per schema
- **THEN** the backup check is a problem and no file name of the folder appears in the output

#### Scenario: Sentinel never shown
- **WHEN** every fake dump holds a sentinel string
- **THEN** the sentinel appears in no output, JSON or state file

### Requirement: Off-site copy age
The system SHALL report the off-site copy, in order: skipped if not set up; a problem if no copy succeeded, or if the last 40 lines of the off-site log show a refused permission or an incomplete copy logged after the last success's day; a problem past a configurable age (default 15 days); a warning past another (default 1 day). It SHALL NOT print log text, access or mount the off-site disk, or run the off-site script.

#### Scenario: Old copy
- **WHEN** the last off-site success, read from the copy line of the off-site status file, is older than the warning age and younger than the problem age, and the log holds no failure
- **THEN** the offsite check is a warning

#### Scenario: Copy of the day before yesterday
- **WHEN** the last off-site success is two days old, the log holds no failure and the ages are the defaults
- **THEN** the offsite check is a warning

#### Scenario: Copy of yesterday
- **WHEN** the last off-site success is one day old, the log holds no failure and the ages are the defaults
- **THEN** the offsite check is ok

#### Scenario: Very old copy
- **WHEN** the last off-site success is more than 15 days old, the log holds no failure and the ages are the defaults
- **THEN** the offsite check is a problem

#### Scenario: Permission refused, no success since
- **WHEN** the last 40 lines of the off-site log hold "Operation not permitted" and the log was written on a later day than the last successful copy
- **THEN** the offsite check is a problem with the not-permitted reason, whatever the age of the last success, and no text of the log appears in the output or the state file

#### Scenario: Incomplete copy, no success since
- **WHEN** a line of the last 40 lines of the off-site log starts with "copie incomplète", none holds "Operation not permitted", and the log was written on a later day than the last successful copy
- **THEN** the offsite check is a problem with the incomplete reason

#### Scenario: Successful copy after the failure
- **WHEN** the last 40 lines of the off-site log hold "Operation not permitted" and the last successful copy is dated on or after the day the log was last written
- **THEN** the offsite check is not a problem for the log, and is ok when that copy is less than two days old

#### Scenario: Both failures in the log
- **WHEN** the last 40 lines of the off-site log hold both "Operation not permitted" and a line starting with "copie incomplète", written on a later day than the last successful copy
- **THEN** the offsite check is a problem with the not-permitted reason

#### Scenario: Log missing
- **WHEN** the off-site log is absent or unreadable
- **THEN** the offsite check follows the age rules only

#### Scenario: Failure out of the last 40 lines
- **WHEN** "Operation not permitted" appears in the off-site log only before its last 40 lines
- **THEN** the offsite check ignores it

#### Scenario: Not set up
- **WHEN** no off-site configuration exists
- **THEN** the offsite check is skipped as not set up

### Requirement: Free disk space
The system SHALL measure the free space of the volume that holds the home folder and report a warning under a first configurable threshold and a problem under a second, smaller one. It SHALL NOT delete or clean anything.

#### Scenario: Low space
- **WHEN** the measured free space is between the two thresholds
- **THEN** the disk check is a warning

### Requirement: Jira token expiry from a non-secret date
The system SHALL read the token expiry date only from `jira_token_expires` in the flow settings file, reporting a problem once it is past, a warning within its configurable warning period, and skipped with "expiry date unknown" when the key is absent. It SHALL NOT invoke the Keychain tool, nor read, print or handle the token.

#### Scenario: Date absent
- **WHEN** the flow settings file has no `jira_token_expires` key
- **THEN** the jira check is skipped with the unknown-date reason and the exit code is not changed by it

#### Scenario: Expired
- **WHEN** the expiry date is yesterday
- **THEN** the jira check is a problem and the Keychain tool is never invoked

### Requirement: Stale branches and worktrees
The system SHALL report a warning, never a problem, when the main checkout has worktrees whose branch is merged into main or whose last commit is older than a configurable number of days, local branches merged and not deleted, or prunable worktrees. It SHALL ignore the run tree. It SHALL print their counts and names in the terminal only, and SHALL NOT delete a branch, remove or prune a worktree.

#### Scenario: Merged branch left
- **WHEN** a local branch is merged into main and still exists
- **THEN** the branches check is a warning naming it in the terminal, and the state file holds its count only

#### Scenario: Nothing deleted
- **WHEN** the branches check finds a prunable worktree
- **THEN** the git calls log shows no branch deletion, worktree removal or prune

#### Scenario: Run tree ignored
- **WHEN** the only worktree besides the main checkout is the run tree, detached and with a commit older than the threshold
- **THEN** the branches check is ok and does not name it

### Requirement: Run worktree on main
The system SHALL report the run tree, at a configurable location, as ok when it is detached at the tip of main and clean, as a warning when it is behind main by fast-forward, and as a problem when it is missing, on a branch, off the history of main or holding local changes. It SHALL NOT switch, reset, update or fetch that worktree.

#### Scenario: Wrong branch
- **WHEN** the run worktree is on a feature branch
- **THEN** the run-worktree check is a problem and no git command that changes it is called

#### Scenario: Detached at the tip of main
- **WHEN** the run tree is clean and detached at the tip of main
- **THEN** the run-worktree check is ok

#### Scenario: Behind main
- **WHEN** the run tree is clean, detached on an ancestor of main, and main has a newer commit
- **THEN** the run-worktree check is a warning and the run tree is unchanged

#### Scenario: Local change
- **WHEN** a tracked file of the run tree is modified
- **THEN** the run-worktree check is a problem

### Requirement: State file on the record option
The system SHALL, with the record option only, replace atomically an owner-only state file in the lab data folder holding the format version, the check time, the counts by level, each check's identifier, level and reason key, and the last notification date. It SHALL NOT write in it a path, a branch name, a model name or a secret.

#### Scenario: Recorded run
- **WHEN** the doctor runs with the record option
- **THEN** the state file exists, is owner read/write only, and holds one entry per check present in the output

#### Scenario: Not writable
- **WHEN** the state file cannot be written
- **THEN** the exit code is 2 with the cannot-run key phrase

### Requirement: Notification only on problem, under the scheduler
The system SHALL send one macOS notification when the record option and the notifier setting are both set and at least one check is in problem, at most once per day, stating the problem count and check identifiers. It SHALL NOT notify on warnings, on a manual run, or with a path, a branch name, a model name or a secret.

#### Scenario: Two problems, twice a day
- **WHEN** the scheduled doctor runs twice the same day with two problems
- **THEN** exactly one notification is sent, naming the two check identifiers

#### Scenario: Manual run
- **WHEN** the doctor runs with problems but without the notifier setting
- **THEN** no notification is sent

### Requirement: Scheduled daily job
The system SHALL provide a launchd template that runs the doctor's wrapper daily, later than the backup and off-site copy jobs, with no run at load and no keep-alive. The wrapper SHALL record the result with notification enabled, then regenerate the dashboard, and SHALL NOT fail because of the dashboard.

#### Scenario: Well-formed template
- **WHEN** the template is parsed
- **THEN** it has its label, a daily schedule later than its predecessor jobs, and neither run-at-load nor keep-alive

#### Scenario: Dashboard failure
- **WHEN** the dashboard generation fails in the wrapper
- **THEN** the wrapper exits with the doctor's exit code

### Requirement: No secret, database client or backup content
The system SHALL NOT invoke the Keychain tool, a database client or a container exec command, and SHALL NOT open a file of the backups folder. A test SHALL scan the script source for these commands and fail naming any it finds.

#### Scenario: Whole suite
- **WHEN** every scenario of the suite has run
- **THEN** the calls log never shows the Keychain tool, a database client or a container command

### Requirement: Local checks only, no versions
The system SHALL contact only addresses of the local machine, and SHALL NOT compare versions, query a release source or suggest an upgrade; versions belong to the components watch.

#### Scenario: Source scan
- **WHEN** the script source is scanned
- **THEN** it holds no non-local network address and no version-comparison call

### Requirement: Testable without real services
The system SHALL be covered by a test suite that redirects every probe to fakes: data, logs, date, time and home through environment overrides, Ollama through a fake local server, the database port through a local socket, launchd, Git and notification tools through stubs. The suite SHALL NOT need the network, Docker, the Keychain or a real launchd session.

#### Scenario: Isolation
- **WHEN** the suite runs on a machine with real services
- **THEN** no real service is contacted and no file outside the temporary folder is written

### Requirement: Mothra's Node and npm dependencies check
The system SHALL report in warning, in a check `mothra-npm`, a Node other than `mothra/.node-version` or absent, a missing `mothra/node_modules`, and a `node_modules` whose recorded lock differs from `mothra/package-lock.json`, and skip the check with its reason when the lock is absent (mothra-npm-ready design D3). It SHALL NOT give the problem level nor use the network.

#### Scenario: Node of another version
- **WHEN** the lock exists, `node_modules` is ready and the fake Node answers a version other than `.node-version`
- **THEN** the check is in warning and names both versions

#### Scenario: Stale node_modules
- **WHEN** `mothra/node_modules/.package-lock.json` differs from the lock
- **THEN** the check is in warning with `node_modules périmé : verrou plus récent ou différent`

#### Scenario: No lock
- **WHEN** `mothra/package-lock.json` is absent
- **THEN** the check is skipped with `pas de verrou npm de Mothra`
