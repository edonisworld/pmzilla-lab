# tooling-offsite-backup Specification

## Purpose
The off-site backup: `tools/offsite_backup.sh` copies the newest database and sanctum backups to an encrypted external APFS volume identified by its UUID, rotates the copies, defers when the disk is absent, and runs a monthly restore test of the off-site copy in a throwaway database; nothing goes to an online service (work-queue job R-46).
## Requirements
### Requirement: The off-site disk is identified by its volume identifier
The system SHALL provide a setup subcommand that, after the destination checks and a confirmation by the user, records the identifier of one external volume in a local, owner-only configuration file of the lab data folder, and creates the off-site folder with its fixed name at the volume's root, owner-only. Every other subcommand SHALL find the volume by that identifier only. The system SHALL NOT find the volume by its name or by a mount path, SHALL NOT print the volume's name outside setup, and SHALL NOT write the identifier in any tracked file. Without a configuration, every subcommand except help and status SHALL exit with code 2 and the key phrase of design D13. Untested until implemented.

#### Scenario: Setup confirmed
- **WHEN** setup is run on an encrypted external volume and the user answers yes
- **THEN** the identifier is recorded, the off-site folder exists at the volume's root, both are owner-only, and the exit code is 0

#### Scenario: Same name, other disk
- **WHEN** a different volume with the same name as the configured one is mounted and the configured one is not
- **THEN** nothing is written to the other volume and the run is deferred as for an absent disk

#### Scenario: Not configured
- **WHEN** the copy is run before any setup
- **THEN** the output says "disque hors du Mac non configuré : lancer setup", nothing is written, and the exit code is 2

### Requirement: Only an encrypted, physically attached, local volume is accepted
The system SHALL check the destination before any write, in setup, copy and restore test, and SHALL refuse with exit code 2, writing nothing, a volume that is not encrypted, the Mac's internal disk, a network volume, and a destination inside a cloud-synced folder or inside a Git work tree, each with its key phrase of design D13. The system SHALL NOT offer an option that bypasses these refusals. Untested until implemented.

#### Scenario: Unencrypted volume
- **WHEN** the configured volume is reported as not encrypted
- **THEN** the output says "volume non chiffré : refusé", nothing is written, and the exit code is 2

#### Scenario: Internal or network volume
- **WHEN** setup is given the internal disk or a network volume
- **THEN** it refuses with "disque interne : refusé" or "volume réseau : refusé", records nothing, and exits with code 2

### Requirement: Nothing is sent to an online service
The system SHALL write the off-site copies only under the off-site folder of the identified local volume, and its reports and status only under the lab data folder. The system SHALL NOT contain or run any network command (HTTP client, remote copy, remote shell, cloud synchronisation tool), SHALL NOT write into a cloud-synced folder, and SHALL NOT send a copy, a report or a checksum to any online service. Untested until implemented.

#### Scenario: Static check of the script
- **WHEN** the script's source is scanned
- **THEN** it contains no network client, no remote copy or shell command and no cloud tool invocation

#### Scenario: Synced destination
- **WHEN** the destination resolves inside a cloud-synced folder of the home folder
- **THEN** the output says "dossier synchronisé ou dépôt Git : refusé", nothing is written, and the exit code is 2

### Requirement: The newest plain backups are copied atomically with a manifest
The system SHALL copy, for the database series and for the sanctum series, the newest plain dated local backup when the disk does not already hold a complete copy of it. Each copy SHALL be written under a temporary name with a manifest that lists every file with its size and checksum, verified on the disk, then renamed to its final name; the copy folders SHALL be owner-only and the files owner read/write only, whatever the umask. The system SHALL NOT copy a labeled backup or any other folder of the backups folder, SHALL NOT leave a temporary folder counted as a copy, SHALL NOT modify or delete a local backup, and SHALL NOT start a copy when the free space is insufficient (exit code 1, nothing written). The protected sanctum backup SHALL be copied only on an explicit option. Untested until implemented.

#### Scenario: Nominal copy
- **WHEN** the newest database and sanctum backups are not on the disk
- **THEN** one copy of each is created under its final name with its manifest, "copie créée" is printed for each, and the exit code is 0

#### Scenario: Already present
- **WHEN** the disk already holds complete copies of the newest backups
- **THEN** each series says "déjà présente", nothing is written, and the exit code is 0

#### Scenario: Interrupted copy
- **WHEN** a temporary copy folder is left by an interrupted run
- **THEN** the next run removes it, does not count it as a copy, and copies again

#### Scenario: Labeled backup
- **WHEN** the newest local folder carries a label after its date
- **THEN** it is not copied, and the newest plain dated folder is copied instead

#### Scenario: Not enough space
- **WHEN** the volume's free space is below the source size with its margin
- **THEN** the output says "place insuffisante sur le disque", nothing is written, and the exit code is 1

### Requirement: The rotation keeps recent and monthly copies and deletes only its own copies
The system SHALL, after a verified copy only, keep in each series a configurable number of most recent copies plus the newest copy of each of a configurable number of recent months, and delete the older copies with one "copie supprimée" line each. The system SHALL NOT delete the newest complete copy, SHALL NOT delete a folder whose name is not a copy name, SHALL NOT rotate after a failed copy, and SHALL refuse an invalid retention value (zero, negative, non-numeric) with exit code 2, creating and deleting nothing. Untested until implemented.

#### Scenario: Retention exceeded
- **WHEN** a series holds more copies than the recent and monthly retention allow
- **THEN** the copies outside both are deleted, each with a "copie supprimée" line, and the others remain

#### Scenario: Foreign folder
- **WHEN** the series holds a folder that does not match a copy name
- **THEN** it is neither counted, deleted nor mentioned

#### Scenario: Invalid retention
- **WHEN** a retention value is 0, -1 or a word
- **THEN** the exit code is 2 and no copy is created or deleted

### Requirement: An absent or locked disk defers the run, with a single notification once copies get old
The system SHALL, when the configured volume is not mounted or is locked, write nothing, print its deferral key phrase and exit with code 3. Under the scheduler, the system SHALL send no notification while the last successful copy is younger than a configurable age, and SHALL send at most one notification per day, stating the age, once it is older or when no copy ever succeeded. The system SHALL NOT treat an absent disk as a failure (code 1) or a refusal (code 2), and SHALL NOT notify on a manual run. Untested until implemented.

#### Scenario: Disk unplugged, recent copy
- **WHEN** the scheduled copy runs without the disk and the last success is recent
- **THEN** the output says "disque absent ou verrouillé : copie reportée", the exit code is 3, and no notification is sent

#### Scenario: Disk unplugged, old copy
- **WHEN** the scheduled copy runs twice the same day without the disk and the last success is older than the configured age
- **THEN** exactly one notification is sent that day, stating the number of days

### Requirement: Failures and refusals notify under the scheduler only, without sensitive content
The system SHALL send one macOS notification on exit codes 1 and 2 when the notifier setting is enabled, stating the cause and the exit code. A manual run and a successful run SHALL send none. The notification, the output and the report SHALL NOT contain a password, the volume's name or identifier, a file name inside a copy, a database value or any sanctum content. Untested until implemented.

#### Scenario: Scheduled refusal
- **WHEN** the scheduled copy finds the volume unencrypted
- **THEN** one notification carries the cause and the exit code 2

#### Scenario: Sentinel never shown
- **WHEN** every fake backup file holds a sentinel string and any subcommand runs
- **THEN** the sentinel appears in no output, notification or report

### Requirement: The monthly restore test restores the off-site copy into a disposable database only
The system SHALL provide a restore test that runs only when no successful test exists for the current calendar month (unless forced), and that checks the manifest of the newest copy of each series (every file present, same size, same checksum, no extra file), restores the newest off-site database copy through the existing restore-test script (disposable container, migrations, counts compared with the real database read in counts only), and checks the file count of the newest sanctum copy against its manifest. The system SHALL NOT restore into the real database, SHALL NOT start, stop or write to the real database, SHALL NOT read a database value or a sanctum file's content, and SHALL NOT decrypt or unlock the disk itself. A disk absent or locked, or a real database not running, SHALL defer the test with exit code 3. A checksum difference, a restore-test failure or a sanctum count gap SHALL give exit code 1. Untested until implemented.

#### Scenario: Not due
- **WHEN** a successful test already exists for the current month
- **THEN** the output says "test du mois déjà fait", nothing is checked or started, and the exit code is 0

#### Scenario: Successful test
- **WHEN** the test is due, the disk is present, the real database answers and every check passes
- **THEN** the restore-test script is called on the off-site database copy, the output ends with "test de restauration hors du Mac : OK", and the exit code is 0

#### Scenario: Altered copy
- **WHEN** a file of the newest database copy differs from its manifest
- **THEN** the output names the copy with "somme de contrôle différente", no container is started, and the exit code is 1

#### Scenario: Real database down
- **WHEN** the test is due and the real database container is stopped
- **THEN** the output says "vraie base indisponible : test reporté", the real database is not started, and the exit code is 3

### Requirement: The restore test writes a counts-only report in the lab data folder
The system SHALL write one report per month, owner read/write only, in a reports subfolder of the lab data folder, keeping a configurable number of the newest reports, and SHALL update a status file with the date and result of the last copy and of the last test. The report SHALL hold only the run date, the copy names tested, the checksum result per series, the table names with their two counts and status, the sanctum file counts, the final result and the exit code. The system SHALL NOT write a report in the repository, in the flow folder or in the deliverables folder, and SHALL NOT write a value, a person's, team's or project's name, or a file name inside a copy into a report. A status subcommand SHALL print the status file and the age of the newest copy of each series without mounting or writing anything. Untested until implemented.

#### Scenario: Report content
- **WHEN** a restore test completes
- **THEN** its report holds only the listed fields, and the status file records the test's date and result

#### Scenario: Report retention
- **WHEN** more monthly reports exist than the configured number
- **THEN** the oldest are removed and the newest remain

### Requirement: Two launchd templates schedule the copy and the restore test, installed by the user
The system SHALL provide two launchd job templates that run the copy daily at a time later than the database backup job and at every volume mount, and the restore test daily at a time later than the copy job and at every volume mount, with output and errors to one log file each, notifications enabled, the home placeholder as the only user path, no run at load and no keep-alive. The templates SHALL NOT contain a secret, a Keychain command, a volume identifier or a real path. The session SHALL NOT install, load, start or unload them; the user does. Untested until implemented.

#### Scenario: Well-formed templates
- **WHEN** each template is parsed
- **THEN** it is valid, has its label, a daily schedule later than its predecessor job, a mount trigger, and neither run-at-load nor keep-alive

#### Scenario: No secret and no real path
- **WHEN** the raw templates are read
- **THEN** they contain no password mention, no Keychain command, no identifier and no user path other than the placeholder

