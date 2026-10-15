# jira-flow-config Specification

## Purpose

Describes how the flow tools read the settings file (`flux.yaml`): strict YAML loading that refuses duplicated keys, English setting names with former French names refused (naming the current name), migration of an existing file, and refusal of retired settings. The structure only is described here, never the values. Sources are the tests in `tests/flux_config/`.

## Requirements

### Requirement: Duplicate keys refused
The system SHALL load configuration YAML files (the flow settings file and the other YAML configuration files of the project, including the watch sources file) so that a key written twice at the same level is refused rather than silently keeping the last one. The error SHALL name the file, the full dotted path of the key, and both line numbers, ask to remove one of the lines, and never show a value. A key quoted in one place and unquoted in another SHALL count as the same key; the same key name in different blocks or in different list items SHALL be allowed; a repeated value SHALL NOT be a key; a merge override SHALL NOT be a duplicate.

Source: tests/flux_config/test_yaml_strict.py (CleEcriteDeuxFois); tests/flux_config/test_lecteurs.py

#### Scenario: Top-level duplicate
- **WHEN** a setting appears on lines 1 and 3
- **THEN** the error reads that the key is written twice (L1 and L3), asks to delete one line, and shows no value

#### Scenario: Nested duplicate
- **WHEN** a key repeats inside a block or inside a series item
- **THEN** the message uses the dotted path (for example block.key) and both lines

#### Scenario: Merge override
- **WHEN** a mapping overrides a key it inherits by merge
- **THEN** no error is raised and the override wins

### Requirement: Same result as the standard loader
The system SHALL return the same data as the standard safe YAML loader for valid files (empty or comment-only files yield none), SHALL leave syntax errors as YAML errors, SHALL expose the line number of each key, SHALL dump like an ordinary dictionary, and SHALL raise a configuration error that exits the program and is not caught by generic exception handlers.

Source: tests/flux_config/test_yaml_strict.py (MemeResultatQueSafeLoad)

#### Scenario: Syntax error
- **WHEN** the file has an unclosed list
- **THEN** a YAML error is raised, not a configuration error

### Requirement: Every reader of the settings refuses duplicates
The system SHALL apply the same refusals in the flow report, dependency report, history collector and dashboard readers: a key written twice SHALL stop the program with both line numbers, and a former setting name, alone or beside its new name, SHALL stop it with the line of the former name and the current name.

Source: tests/flux_config/test_lecteurs.py

#### Scenario: Four readers
- **WHEN** a duplicate key is present
- **THEN** each of the four readers refuses it with "written twice (L1 and L3)"

#### Scenario: Former and new name together
- **WHEN** a setting is written on line 1 under its former name and on line 2 under its new name
- **THEN** each of the four readers refuses the file, naming line 1, the former name and the current name

#### Scenario: Valid file
- **WHEN** the file is correct
- **THEN** each reader reads it

### Requirement: Settings migration
The system SHALL rewrite a settings text to English names while preserving comments, end-of-line comments, values, unchanged keys and keys of other blocks that happen to carry a former name; the result SHALL be read without any message (the former file being refused) and be idempotent (second run no change).

Source: tests/flux_config/test_flux_config.py (Migration, MigrationDeConflits)

#### Scenario: Keys of another block untouched
- **WHEN** a map of project names uses a key named like a former column role
- **THEN** only the block name is renamed

#### Scenario: Same key in two series
- **WHEN** two dashboard series use the same former key
- **THEN** both are renamed and each change is listed with its line

### Requirement: Migration change list
The system SHALL list the changes of a settings migration as "line: old -> new" with full dotted paths, plus value migrations, and SHALL put no value of the file in that list.

Source: tests/flux_config/test_flux_config.py (Migration, MigrationDeConflits)

#### Scenario: Changes without values
- **WHEN** a file with former names under nested blocks is migrated
- **THEN** each change reads "line: old -> new" with the dotted path, value migrations are listed, and no value of the file appears

### Requirement: Migration conflicts
The system SHALL, for a file written with an unmigratable ambiguity, raise a migration conflict listing the conflicts (both names of one setting, or a key written twice) and the other changes, and SHALL write nothing, in dry run or not.

Source: tests/flux_config/test_flux_config.py (MigrationDeConflits)

#### Scenario: Conflict
- **WHEN** both portfolio-types names are present
- **THEN** a conflict names the lines and the keys, other changes are listed, and the file and its backup are untouched

### Requirement: Settings file migration
The system SHALL, when migrating the settings file, keep the former file beside it with a suffix, support dry run without writing anything, and do nothing on a second run.

Source: tests/flux_config/test_flux_config.py (MigrationDeFichier)

#### Scenario: Dry run, then real run, then second run
- **WHEN** a file with former names is migrated in dry run, then for real, then again
- **THEN** the dry run writes nothing, the real run keeps the former file beside it with a suffix, and the second run changes nothing

### Requirement: Retired settings refused
The system SHALL refuse a settings file holding the retired date-format setting (under either name) or a French column alias (matched without case or surrounding spaces), naming the setting or alias, never the value; other column names SHALL be kept. The flow and dependency tools SHALL stop on such a file and SHALL NOT ignore it with a warning.

Source: tests/flux_config/test_flux_config.py (AnciensReglagesRefuses)

#### Scenario: Retired date format
- **WHEN** a date-format setting is present
- **THEN** the file is refused with a message that the setting no longer exists because the API export has a fixed date format, and the value is not echoed

#### Scenario: French aliases
- **WHEN** the columns list holds a French alias beside an English name
- **THEN** the file is refused naming the alias, while a list of non-French names is read without any message

### Requirement: Former setting names and options refused
The system SHALL refuse a settings file that uses a former setting name, column role, segment name or value, and a command line that uses a former option name, with an error that names the current name and exits with a non-zero code, in every reader of the settings. A value or a longer option name that merely starts with a former name SHALL NOT be refused, and nothing after a double dash SHALL be examined.

Source: tests/flux_config/test_flux_config.py (RefusDesAnciennesOptions, DoubleNomRefuse)

#### Scenario: Former setting
- **WHEN** a settings file holds a former top-level name
- **THEN** the program stops with an error naming the current name

#### Scenario: Former option with equals sign
- **WHEN** a former option is given as `--option=value`
- **THEN** the program stops with an error naming the current option

#### Scenario: After a double dash
- **WHEN** a former option name appears after a double dash
- **THEN** it is not examined

### Requirement: Settings added by the GDPR alignment
The system SHALL accept in the flow settings, read with the strict loader and validated before any call to Jira, any database connection and any file write: the cloud identifier (`jira_cloud_id`), the token expiry date (`jira_token_expires`) and its warning period, and the `declared_labels` block.

Source: tests/flux_config/test_nouveaux_blocs.py (TestIdentifiantEtJeton, TestEtiquettesDeclarees)

#### Scenario: Identifier and token expiry
- **WHEN** the cloud identifier, the token expiry date and its warning period are set
- **THEN** they are read as given; without a warning period a default applies

### Requirement: Cycle and workflow settings added by the GDPR alignment
The system SHALL accept in the flow settings, read with the strict loader and validated before any call to Jira, any database connection and any file write: the `cycles` block (with its optional per-cycle base-version flag of design D12), the `patches` block, and the `discovery_workflow` block (columns, start column, review-passed columns of design D6, validation date).

Source: tests/flux_config/test_nouveaux_blocs.py (TestCycles, TestPatches, TestDiscoveryWorkflow)

#### Scenario: Valid blocks
- **WHEN** consecutive cycles, patches and a Discovery Workflow block with a validation date are set
- **THEN** they are read without warning and the mapping is marked validated

### Requirement: Retention settings added by the GDPR alignment
The system SHALL accept in the flow settings, read with the strict loader and validated before any call to Jira, any database connection and any file write, the `retention` block: retention period, maximum file age of CSV and points files, labelled-backup lifetime, pre-purge label, off-site flow age.

Source: tests/flux_config/test_nouveaux_blocs.py (TestRetention)

#### Scenario: Defaults and given values
- **WHEN** the block is absent, or holds every key
- **THEN** defaults apply, respectively the given values are read

### Requirement: Invalid new settings refused
The system SHALL stop the reading tool on an invalid value of the settings added by the GDPR alignment, with exit code 1 (exit code 3 in the retention tool), naming the key path and line and never the value.

Source: tests/flux_config/test_nouveaux_blocs.py; tests/flow_retention/test_regles.py

#### Scenario: Invalid off-site flow age
- **WHEN** the off-site flow age of the retention block is not a number
- **THEN** the reading tool stops with exit code 1, names the key path and its line, does not echo the value, and Jira is not called

#### Scenario: Unknown key in a new block
- **WHEN** the retention block holds an unknown key
- **THEN** the reading tool stops with exit code 1 and names the key path and line

### Requirement: New setting values never written
The system SHALL NOT write any value of the settings added by the GDPR alignment into an output, a report or a summary.

Source: tests/flux_jira/test_cycles_commande.py (SortiesSansValeurDistinctive); tests/flux_config/test_nouveaux_blocs.py

#### Scenario: Cycles report
- **WHEN** the cycles report is written with cycles, patches and declared labels configured
- **THEN** no fix version or label of the settings appears in the console or the report

### Requirement: PO field setting refused
The system SHALL refuse the setting `export_po_field`, whatever its value, in every reader of the flow settings, with exit code 1 and the unsupported-setting key phrase of design D19, before any call to Jira, any database connection and any file write, because the PO in charge is not stored in this change (design D3). The refusal SHALL name the key and its line and SHALL NOT echo the value. The system SHALL NOT ignore the setting silently and SHALL NOT request any user field because of it.

Source: tests/flux_config/test_nouveaux_blocs.py (TestPoField); tests/export_jira_api/test_garde_champs.py (no PO column). The export-level scenario is not run end to end.

#### Scenario: Setting present
- **WHEN** the flow settings hold `export_po_field` and the export starts
- **THEN** the output holds "setting not supported: export_po_field" with its line, no value is printed, Jira is not called, no file is written, and the exit code is 1

#### Scenario: Setting absent
- **WHEN** the flow settings do not hold `export_po_field`
- **THEN** the readers run without that refusal

### Requirement: New readers refuse duplicates
The system SHALL apply the duplicate-key and former-name refusals of this capability in the readers added by this change: the retention tool, the epic statuses tool, the import (for the declared labels and the export queries), the cycles report and the organisation referential reader.

Source: tests/flux_config/test_nouveaux_blocs.py; tests/flow_organisation/test_flow_organisation.py; the three other readers untested.

#### Scenario: Duplicate in the cycles block
- **WHEN** a cycle key is written twice
- **THEN** each new reader refuses it with "written twice" and both line numbers, without the value

## Open questions

1. The settings reader is shared with the watch tool (a sources file) per a test; its behavior is outside this domain and is only mentioned for the strict loader.
