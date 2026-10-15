# library-search-knowledge-import

## Purpose

Records that the library reaches the PostgreSQL `knowledge` schema through the indexer only: the former copy of a SQLite index into the database, with its verification and comparison commands, is retired, and no tool replaces it.

Source of truth: `tests/knowledge_import/test_knowledge_import.py`, `tools/knowledge_import.py`, `tools/knowledge_library.py`.

## Requirements

### Requirement: No tool copies or compares a SQLite library index
The system SHALL provide no command that copies, verifies, compares or counts a SQLite library index against the database: the former import and parity tool, its tests, its runner entry, its script-dependencies entry and its lock file SHALL be absent. The library reaches the database through the indexer only (library-search-indexing), its counts come from the indexer's status command and its full-text index is checked by the indexer's probe command.

#### Scenario: Former tool absent
- **WHEN** the tools folder and the script list of the runner are read
- **THEN** no import or parity tool of the library index is present, and no test suite names it
