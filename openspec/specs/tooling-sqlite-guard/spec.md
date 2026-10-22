# tooling-sqlite-guard Specification

## Purpose
The system SHALL guarantee that no tool reads or writes a SQLite file and that no test builds a SQLite fixture, now that PostgreSQL is the only store.

## Requirements

### Requirement: No tool reads or writes a SQLite file
The system SHALL be covered by a test, run without a database, that fails when a file of the tools folder (Python and shell scripts) imports the SQLite module, names a file with the SQLite extension, or calls the SQLite command-line tool, outside an explicit allow-list kept in the test. The allow-list SHALL start empty, and the failure message SHALL name the file and the line. The test SHALL NOT read any file outside the repository.

#### Scenario: SQLite import added
- **WHEN** a tool file imports the SQLite module
- **THEN** the test fails and names the file and the line

#### Scenario: SQLite path in a script
- **WHEN** a shell script of the tools folder names a file with the SQLite extension
- **THEN** the test fails and names it

#### Scenario: Clean tree
- **WHEN** no tool file uses SQLite
- **THEN** the test passes

### Requirement: Tests build no SQLite fixture
The system SHALL be covered by a test that fails when a test file imports the SQLite module or calls the builder of the SQLite demo library, outside an explicit allow-list kept in the test and starting empty, so that a guarantee checked only against a SQLite fixture cannot survive the removal of the SQLite route. The guard's own files SHALL be excluded. A test that only creates a placeholder file carrying a SQLite file name, to check that it is ignored, SHALL NOT make the guard fail.

#### Scenario: Placeholder file
- **WHEN** a test writes a few bytes to a file named like a former SQLite file to check that a tool ignores it
- **THEN** the guard passes

#### Scenario: Fixture builder left
- **WHEN** a test file still calls the builder of the SQLite demo library
- **THEN** the test fails and names the file
