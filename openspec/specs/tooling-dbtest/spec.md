# tooling-dbtest Specification

## Purpose
The throwaway-database script `tools/dbtest.sh` runs the suites that need a database against a disposable PostgreSQL container, never the real instance, and leaves a record of a green run for the exact tree it tested, which the branch finish requires when a branch changes database code.

## Requirements

### Requirement: The throwaway run passes only its own database variables
The system SHALL launch each suite of the throwaway-database script without any `PMZILLA_LAB_DB_*` variable of its caller, with only the port and the random password of its container and the mark `DBTEST_PORT` equal to that port (test-speed-2 design D1, D3). It SHALL NOT pass the caller's address, password or per-role passwords, nor accept the standard port or the configured real port.

#### Scenario: Caller's variables
- **WHEN** the caller exports the address, a password and a per-role password and runs the script with fake Docker and a fake suite launcher
- **THEN** each suite sees the container's port, a password of the container, `DBTEST_PORT` equal to the port, and none of the caller's values

#### Scenario: Real port refused
- **WHEN** the port option is the standard port or equals the configured real port
- **THEN** the script exits 2 and starts nothing, as before

Source: untested until implemented (tests/db_scripts/test_dbtest.sh, task 1.3)

### Requirement: The default list covers every suite that uses a database
The system SHALL run by default every suite whose tests use a database, the book usage, dashboard, flow retention and posture evaluation suites included (test-speed-2 design D8), and SHALL include a static test, run without a database, that fails naming the suite or file when such a suite is missing from the default list, a database test file is outside the finishing script's database list, or a listed name or path matches nothing (D9).

#### Scenario: Default run
- **WHEN** the script runs without suite names, with fake Docker and a fake suite launcher
- **THEN** the fourteen suites run in the declared order and the summary names them all

#### Scenario: Suite missing from the list
- **WHEN** a suite holds a test file that uses the database guard and is not in the default list
- **THEN** the static test fails and names that suite

#### Scenario: Database file outside the finishing list
- **WHEN** a database test file is not covered by the finishing script's database paths
- **THEN** the static test fails and names that file

Source: untested until implemented (tests/db, tests/db_scripts/test_dbtest.sh, tasks 2.2 and 2.3)

### Requirement: A green run on a clean tree is recorded for that tree
The system SHALL, after a green run of the default list on a checkout clean at start and end with an unchanged `HEAD`, append the tree of `HEAD` to the record of test-speed-2 design D5 in the common Git folder, owner-only, and print the record line of D29, having removed that tree's line at the start. Otherwise it SHALL write nothing and print the reason of D29. It SHALL NOT write a path, a date or a password, nor change its exit codes.

#### Scenario: Green default run
- **WHEN** the default list passes on a clean checkout
- **THEN** the record holds the tree of `HEAD`, the output holds `Empreinte dbtest enregistrée`, and the exit code is 0

#### Scenario: Named suites or dirty tree
- **WHEN** the run names suites, or the checkout holds an untracked non-ignored file
- **THEN** no line is added, the output gives the reason `suites choisies` or `arbre non propre`, and the exit code is unchanged

#### Scenario: Red run after a green one
- **WHEN** a green run recorded the tree and a later run on the same tree has a red suite
- **THEN** the record no longer holds that tree and the exit code is 1

Source: untested until implemented (tests/db_scripts/test_dbtest.sh, task 2.4)

### Requirement: Tests of the script never write a real record
The system SHALL let tests name another record file, and SHALL write no record when the suite launcher is replaced and no record file is named (test-speed-2 design D5). It SHALL NOT write into the Git folder of the repository that holds the script during the script's own tests.

#### Scenario: Fake launcher without a record file
- **WHEN** the suite launcher is replaced, no record file is named, and the run is green on a clean checkout
- **THEN** no record file exists in that repository's Git folder

Source: untested until implemented (tests/db_scripts/test_dbtest.sh, task 2.4)

### Requirement: The throwaway-database script compares ports as numbers
The system SHALL accept a port option only in the plain decimal form of test-db-guards design D1, compare it as a number with the standard and configured real ports, and refuse with exit 2 (line of D5) a configured real port set in another form. It SHALL NOT start a container or run a suite after these refusals, nor accept a form naming the standard or configured port as a number.

#### Scenario: Leading zero
- **WHEN** the port option is the standard port written with a leading zero
- **THEN** the script exits 2 with `Port invalide` and fake Docker records no call

#### Scenario: Sign, spaces or out of range
- **WHEN** the port option carries a sign, leading or trailing spaces, is zero or is above 65535
- **THEN** the script exits 2 with `Port invalide` and starts nothing

#### Scenario: Same number as the configured real port
- **WHEN** the configured real port is a valid port and the port option is the same number
- **THEN** the script exits 2 with the refusal line of the real port and starts nothing

#### Scenario: Configured real port unreadable
- **WHEN** the configured real port is set to a value that is not a valid port
- **THEN** the script exits 2 with `le port configuré de la vraie base est illisible` and starts nothing

#### Scenario: Valid other port
- **WHEN** the port option is a valid port different from both, with fake Docker and a fake suite launcher
- **THEN** the run goes on as before

Source: untested until implemented (tests/db_scripts/test_dbtest.sh, task 2.2)

### Requirement: The throwaway-database script refuses while another finish holds the lock
The system SHALL make the throwaway-database script, before starting any container, read the finish lock with the rule of the test runner and exit 3 with `dbtest : fin de branche en cours (<branche>), lancement refusé` when a live lock's token differs from `FINISH_LOCK_TOKEN` or that variable is unset (finish-under-lock design D5). It SHALL NOT start a container, touch a record, wait, or create, remove or change the lock.

#### Scenario: Another finish running
- **WHEN** a lock of a live process with another token exists and the script runs with fake Docker
- **THEN** it exits 3 with its phrase, fake Docker records no call, and the record file is unchanged

#### Scenario: Launched by the worktree finish
- **WHEN** the caller's token equals the lock's token
- **THEN** the run goes on as without a lock

### Requirement: The throwaway-database script ignores a stale lock
The system SHALL treat a stale finish lock (multi-session-piloting design D6) as absent, print `dbtest : verrou de fin périmé, ignoré` and go on. It SHALL NOT remove or replace the stale lock.

#### Scenario: Stale lock
- **WHEN** the lock names a process that no longer exists
- **THEN** the output holds `dbtest : verrou de fin périmé, ignoré`, the run goes on, and the lock folder is still there
