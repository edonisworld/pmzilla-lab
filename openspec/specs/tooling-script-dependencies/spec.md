# tooling-script-dependencies Specification

## Purpose
The scripts of the tools folder are launched with a bare uv run, so every third-party dependency they need, directly or through local modules, must be declared in their inline script metadata. A controlled set of scripts is checked in depth; every other entry script is either controlled or explicitly exempted, and exempted entry scripts must still declare what they import.

## Requirements

### Requirement: Declared dependencies cover all imports
The system SHALL fail a check when a controlled script lacks inline dependency metadata, or imports, directly, through local tools modules, or lazily inside functions, a third-party package that is not declared.

#### Scenario: Missing declaration
- WHEN a script or a local module it imports needs an undeclared package
- THEN the check fails naming the script

#### Scenario: Unknown module
- WHEN a script imports a module unknown to the package mapping
- THEN the check fails, asking for the mapping to be extended

#### Scenario: Late import
- WHEN a package is imported lazily by a module imported by a script
- THEN the static scan still sees it

#### Scenario: Extra in brackets
- WHEN a declared dependency carries an extra in brackets, followed by other dependencies on the same line
- THEN the check reads every dependency of the line, the package name without its extra

Source: tests/script_dependencies/test_script_dependencies.py (Declaration, test_une_extra_entre_crochets_ne_coupe_pas_la_liste)

### Requirement: Every entry script is controlled or exempted
The system SHALL fail a check when a script of the tools folder that has a main entry point is neither in the controlled set nor in the explicit exemption list, naming the unclassified scripts, and SHALL fail when a script named in either list no longer exists. The exemption list SHALL act as a ratchet: a new entry script SHALL NOT pass unless it is classified.

#### Scenario: New entry script
- WHEN an entry script is added to the tools folder without being classified
- THEN the check fails and names it

#### Scenario: Removed script still listed
- WHEN a controlled or exempted script no longer exists
- THEN the check fails and names it

Source: tests/script_dependencies/test_script_dependencies.py (Decouverte)

### Requirement: Exempted entry scripts declare their dependencies too
The system SHALL fail a check when an exempted entry script needs, directly or through local modules, a third-party package that its inline metadata does not declare, naming the incomplete scripts. An exempted script that needs no third-party package SHALL need no declaration.

#### Scenario: Exempted script with an undeclared import
- WHEN an exempted entry script imports a third-party package it does not declare
- THEN the check fails and names the script

Source: tests/script_dependencies/test_script_dependencies.py (test_les_scripts_d_entree_exemptes_declarent_aussi_leurs_dependances)

### Requirement: No pinned versions in the headers
The system SHALL declare dependencies by package name without pinned versions in the script headers, except a documented version bound on the MCP SDK, and SHALL keep no project manifest nor root lock file. Versions are pinned only by the per-script lock files of the next requirement.

#### Scenario: Declaration
- WHEN a script header is read
- THEN its dependencies are package names, without a pinned version apart from the documented bound

Source: docs/pmzilla/installation.md (section 16, "Script dependencies"); tests/script_dependencies/test_script_dependencies.py (SansVersionEpinglee)

### Requirement: One lock file per entry script with dependencies
The system SHALL keep, next to each entry script of tools/ that declares dependencies, the lock file written by `uv lock --script`, tracked in the repository and read by `uv run` for daily use and in the edition (decision of 2026-10-11, job R-36, build-edition D1; it replaces the unpinned daily use of R-10). The versions SHALL move only through a deliberate refresh (`uv lock --script --upgrade`, then the full test runner). The check SHALL fail when an entry script with dependencies has no lock file, when a lock file no longer lists the packages of its script's header, or when a lock file has no entry script with dependencies.

#### Scenario: Missing lock
- WHEN an entry script declares dependencies and has no lock file
- THEN the check fails and names the script

#### Scenario: Stale lock
- WHEN a package is added to or removed from a header without locking again
- THEN the check fails and names the script

Source: docs/pmzilla/installation.md (section 16, "Script dependencies"); tests/script_dependencies/test_script_dependencies.py (VersionsFigees)

### Requirement: Database driver declared where the database is read
The system SHALL require the database driver to be declared by every script that reads or administers the database.

#### Scenario: Flow scripts
- WHEN the flow, dependency, import, compare, views and database scripts are inspected
- THEN each declares the database driver

Source: tests/script_dependencies/test_script_dependencies.py (test_psycopg_declare_pour_la_lecture_de_la_base)

### Requirement: Minimum Python version declared
The system SHALL require each controlled script to declare a minimum Python version of 3.10 or higher near the top.

#### Scenario: Header
- WHEN the top of the script is read
- THEN a minimum Python version declaration of 3.1x appears

Source: tests/script_dependencies/test_script_dependencies.py (test_requires_python)

### Requirement: Help works in a clean environment
The system SHALL show help for each controlled script in an isolated uv environment with no extra dependency options, and the check SHALL be skipped with a reason when uv is absent or cannot resolve packages for lack of network.

#### Scenario: Clean help
- WHEN each script is run isolated with the help flag
- THEN it exits 0, prints usage and no missing-module error

#### Scenario: Offline
- WHEN uv cannot resolve packages because of the network
- THEN the test is skipped with the reason

Source: tests/script_dependencies/test_script_dependencies.py (AideSansWith)
