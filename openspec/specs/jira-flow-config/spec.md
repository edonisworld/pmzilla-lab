# jira-flow-config Specification

## Purpose

Describes how the flow tools read the settings file (`flux.yaml`): strict YAML loading that refuses duplicated keys, English setting names with former French names still accepted with a warning, migration of an existing file, and handling of retired settings. The structure only is described here, never the values. Sources are the tests in `tests/flux_config/`.
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
The system SHALL apply the same refusals in the flow report, dependency report, history collector and dashboard readers: a key written twice, or the same setting written under its former and its new name, SHALL stop the program with both line numbers.

Source: tests/flux_config/test_lecteurs.py

#### Scenario: Four readers
- **WHEN** a duplicate key is present
- **THEN** each of the four readers refuses it with "written twice (L1 and L3)"

#### Scenario: Valid file
- **WHEN** the file is correct
- **THEN** each reader reads it

### Requirement: Settings migration
The system SHALL rewrite a settings text to English names while preserving comments, end-of-line comments, values, unchanged keys and keys of other blocks that happen to carry a former name; the result SHALL read the same as the former file without warnings and be idempotent (second run no change). The list of changes SHALL give "line: old -> new" with full dotted paths, plus value migrations, and no value of the file. A file written with an unmigratable ambiguity SHALL raise a migration conflict listing the conflicts (both names of one setting, or a key written twice) and the other changes, and SHALL write nothing, in dry run or not. File migration SHALL keep the former file beside it with a suffix, support dry run without writing anything, and do nothing on a second run.

Source: tests/flux_config/test_flux_config.py (Migration, MigrationDeFichier, MigrationDeConflits)

#### Scenario: Keys of another block untouched
- **WHEN** a map of project names uses a key named like a former column role
- **THEN** only the block name is renamed

#### Scenario: Same key in two series
- **WHEN** two dashboard series use the same former key
- **THEN** both are renamed and each change is listed with its line

#### Scenario: Conflict
- **WHEN** both portfolio-types names are present
- **THEN** a conflict names the lines and the keys, other changes are listed, and the file and its backup are untouched

### Requirement: Retired settings ignored with a warning
The system SHALL accept, with a warning that names the setting but not its value, a retired date-format setting (under both its names) and French column aliases in the columns setting, SHALL ignore their values (French aliases are matched without case or surrounding spaces and other aliases are kept), and SHALL load such a file in the flow and dependency tools without error. The two date-format names together SHALL no longer be a conflict.

Source: tests/flux_config/test_flux_config.py (AnciensReglagesIgnores)

#### Scenario: Retired date format
- **WHEN** a date-format setting is present
- **THEN** it is dropped, a warning says the API export has a fixed date format, and the value is not echoed

#### Scenario: French aliases
- **WHEN** the columns list holds French and English names
- **THEN** the French ones are dropped and the others kept, with one warning

### Requirement: Former setting names and options refused
The system SHALL refuse a settings file that uses a former setting name, column role, segment name or value, and a command line that uses a former option name, with an error that names the current name and exits with a non-zero code, in every reader of the settings. A value or a longer option name that merely starts with a former name SHALL NOT be refused, and nothing after a double dash SHALL be examined.

#### Scenario: Former setting
- **WHEN** a settings file holds a former top-level name
- **THEN** the program stops with an error naming the current name

#### Scenario: Former option with equals sign
- **WHEN** a former option is given as `--option=value`
- **THEN** the program stops with an error naming the current option

#### Scenario: After a double dash
- **WHEN** a former option name appears after a double dash
- **THEN** it is not examined

## Open questions

1. The settings reader is shared with the watch tool (a sources file) per a test; its behavior is outside this domain and is only mentioned for the strict loader.
