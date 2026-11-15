# watch-migration

## Purpose

Naming of the watch folders with backward compatibility (`watch_paths`), and the one-time migration from the former French names to the English names (`migrate_watch`).

Source of truth: `tests/watch_lab/test_watch_paths.py`, `tools/watch_paths.py`.

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

## Open questions

None.
