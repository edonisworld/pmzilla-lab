# watch-migration

## Purpose

Naming of the watch folders with backward compatibility (`watch_paths`), and the one-time migration from the former French names to the English names (`migrate_watch`).

Source of truth: `tests/watch_lab/test_watch_paths.py`, `tests/migrate_watch/test_migrate_watch.py`, `tools/watch_paths.py`, `tools/migrate_watch.py`.

## Requirements

### Requirement: Resolve watch folder names with one warning
The system SHALL resolve the settings folder, the content folder and the excluded folder to their current names. When only a former-named folder exists the system SHALL NOT use it: it SHALL stop with an error that names the current folder and the migration tool. A plain file with the current name SHALL NOT be treated as a former folder.

#### Scenario: No folder
- **WHEN** the workspace is empty
- **THEN** current names are returned with no warning

#### Scenario: Former folder only
- **WHEN** only a former-named folder exists
- **THEN** resolution fails with an error naming the current folder and the migration tool, and the former path is never returned

### Requirement: Resolve the collection sub-folder name
The system SHALL name the collection sub-folder with the current name, SHALL refuse a leftover former sub-folder of a current content folder with an error naming the migration tool, and SHALL use the current reading-list file name only.

#### Scenario: Interrupted migration
- **WHEN** the current content folder holds only a former-named sub-folder
- **THEN** resolution fails with an error naming the migration tool

### Requirement: Expose paths to shell scripts with standard-library only
The path module SHALL print the resolved path or name for `lab`, `excluded` and `collection` arguments (warnings on standard error), exit with code 2 on unknown arguments, and import only the standard library.

Source: `tests/watch_lab/test_watch_paths.py` (LigneDeCommande)

#### Scenario: Unknown argument
- **WHEN** an unknown argument is given
- **THEN** the exit code is 2

### Requirement: Support a dry run that changes nothing
The migration tool SHALL, with a dry-run option, write, create and move nothing (no backup folder either) while printing counts for folder moves, file renames, settings keys and permission rules. It SHALL NOT open any database.

Source: `tests/migrate_watch/test_migrate_watch.py` (DryRun)

#### Scenario: Dry run
- **WHEN** the tool runs with dry-run on a former-named workspace
- **THEN** the file tree and contents are unchanged and the counts are printed, with no database-row count

### Requirement: Back up and verify before migrating
The system SHALL copy the folders to migrate to a dated backup folder first, verify the copy (file count and each file size), and refuse to migrate with exit 1 and no change when the backup fails, is incomplete or has a different size, or when the day's backup folder already exists. The backup date SHALL be overridable. The backup SHALL NOT include any database file.

Source: `tests/migrate_watch/test_migrate_watch.py` (Migration, Garde.test_refus_*, test_sauvegarde_du_jour_deja_presente)

#### Scenario: Backup fails
- **WHEN** the copy raises an error
- **THEN** the exit code is 1, "Sauvegarde échouée" is shown, and nothing is migrated

#### Scenario: No database in the backup
- **WHEN** the migration runs while a former triage state file exists in the data folder
- **THEN** the backup folder holds only the migrated folders and the file is neither copied nor changed

### Requirement: Migrate folders without deleting data
The system SHALL move the content folder, excluded folder and settings folder to their new names, with their collection sub-folders and the reading-list file renamed, preserving every file byte for byte and leaving no former folder behind. A freshly cloned repository holding only placeholder files SHALL follow its placeholders. A partially migrated state (content folder already renamed by hand) SHALL be completed.

Source: `tests/migrate_watch/test_migrate_watch.py` (Migration.test_migration_complete, Garde.test_etat_partiel_reprend_ou_il_en_etait, test_depot_cloné_avec_seulement_des_gitkeep)

#### Scenario: Full migration
- **WHEN** the tool runs on a former-named workspace
- **THEN** every file is found under the new names with identical content and the former folders no longer exist

### Requirement: Report counts only
The system SHALL print a report made of numbers (folders moved with file count, keys rewritten, rules added) and SHALL NOT print article names, contents or source names. The closing reminder SHALL NOT name a collection-rename command of the library index.

Source: `tests/migrate_watch/test_migrate_watch.py` (Migration.test_migration_complete)

#### Scenario: Report
- **WHEN** the migration finishes
- **THEN** the report contains the counts and none of the article names or source names

#### Scenario: Closing reminder
- **WHEN** the migration finishes
- **THEN** the closing reminder names no collection-rename command of the library index

### Requirement: Be idempotent and stop on conflicts
The system SHALL, on a second run, print "Rien à faire", change nothing and create no new backup. It SHALL stop with exit 1 and change nothing when a target folder or sub-folder already holds data, or when the settings hold both the former and new name of one setting.

Source: `tests/migrate_watch/test_migrate_watch.py` (Garde)

#### Scenario: Second run
- **WHEN** the tool is run again after a successful migration
- **THEN** "Rien à faire" is printed and the tree is unchanged

#### Scenario: Occupied target
- **WHEN** the new content folder already holds files
- **THEN** exit is 1 with "Dossier cible occupé" and nothing, including backup, is created

### Requirement: Leave the installed scheduler job to the user
The migration tool SHALL NOT touch the installed scheduler job (neither its file nor its registration); the installation guide describes how the user replaces a job installed under the former label by hand.

Source: `tools/migrate_watch.py` (module documentation); `tests/migrate_watch/test_migrate_watch.py` (TachePlanifiee); `docs/pmzilla/installation.md` (section "Install the watch")

#### Scenario: Job installed under the former label
- **WHEN** the migration runs on a machine whose scheduler job still uses the former label
- **THEN** the job is left as it is and the user replaces it following the installation guide

### Requirement: Rewrite settings and permissions
The system SHALL rename the keys of the triage settings while keeping every comment, line count and the theme list, preserve mode, threshold and source activation (sources file identical byte for byte unless it uses the former collection name, in which case those lines are rewritten and counted), and add the new content-folder permission deny rules while keeping all existing ones (no duplicates). It SHALL NOT open or rewrite any database.

Source: `tests/migrate_watch/test_migrate_watch.py` (Migration.test_garde_mode_filtre_le_seuil_et_quatre_sources_desactivees, test_regles_deny_ajoutees_les_anciennes_gardees, test_collection_veille_de_sources_yaml_reecrite)

#### Scenario: Permissions
- **WHEN** the tool runs
- **THEN** all prior deny rules remain and exactly three new ones are present, each once

#### Scenario: No database touched
- **WHEN** the tool runs while a former triage state file exists
- **THEN** that file is byte-identical afterwards

## Open questions

None.
