# tooling-range-scan Specification

## Purpose
Describes the read-only range scan: it scans every commit of `origin/main..<tip>`, merge commits included, and the branch names it is given, for secrets, sensitive names and personal identifiers, with declared secret examples read from `origin/main` only; it prints nothing sensitive, fails closed when a list is unavailable, and exposes its report through a service function and a `--json` output.

## Requirements

### Requirement: Range based on origin/main, commit by commit
The system SHALL provide a read-only range scan that reads every commit of `origin/main..<tip>`, oldest first, with rename detection off, and scans each commit on its own (design D1, D2). The base SHALL always be the `origin/main` remote-tracking reference. The system SHALL NOT accept an option that changes the base, SHALL NOT use local `main`, and SHALL NOT scan only the net diff between base and tip. Untested until implemented.

#### Scenario: Secret added then removed
- **WHEN** a commit of the range adds a line with a secret and a later commit of the range removes it
- **THEN** the scan reports the secret with the file, the line and the short hash of the commit that added it, and exits 1

#### Scenario: Local main moved
- **WHEN** local `main` holds a commit that `origin/main` does not have, and the tip contains it
- **THEN** that commit is part of the scanned range

### Requirement: The range scan writes nothing
The system SHALL keep the range scan read-only: it SHALL NOT fetch, write a reference, write a file or create a Git object (design D1). Untested until implemented.

#### Scenario: Read only
- **WHEN** the scan runs on any range
- **THEN** no reference, file or object of the repository is created or changed

### Requirement: Merge commits scanned for content that no parent has
The system SHALL scan a merge commit of the range in dense combined form, and SHALL treat as added only the lines that exist in none of its parents (design D2). The system SHALL NOT skip merge commits, and SHALL NOT report a line that comes unchanged from one parent. Untested until implemented.

#### Scenario: Injected line in a merge
- **WHEN** a merge commit of the range holds a line with a sensitive name that neither parent holds
- **THEN** the scan reports a sensitive name in that file at that line, for the merge commit

#### Scenario: Line brought from a parent
- **WHEN** a merge commit only brings lines that already exist in one of its parents
- **THEN** the scan reports nothing for the merge commit

### Requirement: Added lines, paths, messages and branch names
For each commit, the system SHALL scan the lines the commit adds, the path of each file it adds, copies or modifies, and its full message, for secrets, sensitive names and personal identifiers. It SHALL also scan each branch name given on the command line, and the tip's name when the tip is a local branch (design D3). The system SHALL NOT report a removed line, and SHALL NOT scan commit author or committer headers. Untested until implemented.

#### Scenario: Rules reused from the hooks
- **WHEN** the scan looks for secrets, names and identifiers
- **THEN** secrets follow the pre-commit secret rules, names follow the two lists and the matching rules of the pre-commit hook, and identifiers are those of the personal-identifiers tool

#### Scenario: Name in a commit message
- **WHEN** a commit message of the range holds a sensitive name
- **THEN** the scan reports a sensitive name in the message of that commit, and exits 1

#### Scenario: Identifier in an added line
- **WHEN** a commit adds a line that holds a personal identifier
- **THEN** the scan reports a personal identifier in that file at that line, for that commit

#### Scenario: Name in a branch name
- **WHEN** a branch name given to the scan holds a sensitive name
- **THEN** the scan reports a sensitive name in the branch name, identified by its rank on the command line

#### Scenario: Removed line
- **WHEN** a commit only removes a line that holds a sensitive name
- **THEN** the scan reports nothing for that line

### Requirement: Declared secret examples read from origin/main only
The system SHALL read the list of declared secret examples from its version in `origin/main`, and SHALL accept a secret found in an added line only when that version declares its path and fingerprint (design D4). Accepted examples SHALL be reported. The system SHALL NOT read the list from the working tree, the index or any commit of the range. A malformed list in `origin/main` SHALL refuse the scan with exit 2. Untested until implemented.

#### Scenario: Secret in a message
- **WHEN** a commit message, a path or a branch name holds a secret whose value is declared in the list of `origin/main`
- **THEN** the secret is reported as a finding: a declared example is never accepted outside an added line

#### Scenario: Example declared on the branch only
- **WHEN** a commit of the range adds a secret, and another commit of the range declares it in the examples list
- **THEN** the secret is reported as a finding and the scan exits 1

#### Scenario: Example declared on origin/main
- **WHEN** a commit adds a secret whose path and fingerprint are declared in the list of `origin/main`
- **THEN** the scan reports an accepted declared example and does not count it as a finding

#### Scenario: Malformed list
- **WHEN** the examples list of `origin/main` has a malformed line
- **THEN** the scan exits 2 with the malformed-list phrase of design D6, and scans nothing

### Requirement: Files not examined are counted and listed
The system SHALL leave out of the scan, and count as "binary", a file that Git reports as binary or whose new content holds a NUL byte. It SHALL scan for secrets a file larger than the pre-commit size limit for names, but SHALL NOT scan it for names or identifiers, and SHALL count it as "size" (design D5). Each file left out SHALL be listed with its path and commit, and the summary SHALL give both counts. The system SHALL NOT skip a file silently. Untested until implemented.

#### Scenario: Binary file
- **WHEN** a commit adds a binary file
- **THEN** the scan lists it as not examined (binary) and the summary counts one binary file

#### Scenario: Large file with a secret
- **WHEN** a commit adds a text file over the size limit that holds a secret and a sensitive name
- **THEN** the secret is reported, the name is not, and the file is listed as not examined for names

### Requirement: Nothing sensitive is printed
The system SHALL report a finding by kind, file, line, commit and, for a secret, family (design D6). The system SHALL NOT print a sensitive name, a secret value, a personal identifier, a branch name, a line of text or a commit message, in text output, JSON output or an error message. A file path that itself holds a finding SHALL be replaced by its rank in the commit, and SHALL appear in JSON as a structured masked cell with its reason. Untested until implemented.

#### Scenario: Name in a path
- **WHEN** a commit adds a file whose path holds a sensitive name
- **THEN** the output says a sensitive name is in the path of file number k of that commit, and the path does not appear in the output

#### Scenario: Sentinel never printed
- **WHEN** fictitious names, identifiers and secrets are planted in lines, messages, paths and branch names
- **THEN** none of them appears in the standard output or the error output, in text or JSON mode

### Requirement: Exit codes and fail-closed lists
The system SHALL exit 0 when nothing is found, 1 on a finding, 2 when a list is unavailable (names list absent or unreadable, examples list of `origin/main` malformed, identifiers unreadable) and 3 on a usage error, a missing `origin/main`, an unknown tip, a Git failure or an unexpected error, with the key phrases of design D6. The system SHALL NOT exit 0 when a list is unavailable, and SHALL NOT print a stack trace. Untested until implemented.

#### Scenario: Unexpected error
- **WHEN** an unexpected exception occurs during the scan
- **THEN** the scan exits 3 and prints the exception type only, never its text nor a stack trace

#### Scenario: Empty names list
- **WHEN** the sensitive-names list exists but holds no name and the team extract adds none
- **THEN** the scan prints the empty-list warning and still scans secrets and identifiers

#### Scenario: Names list absent
- **WHEN** the sensitive-names list cannot be found
- **THEN** the scan exits 2 with the absent-list phrase, and scans nothing

#### Scenario: Empty range
- **WHEN** the tip is an ancestor of `origin/main`
- **THEN** the scan exits 0 and its summary says zero commits were read

#### Scenario: Missing base
- **WHEN** the repository has no `origin/main` reference
- **THEN** the scan exits 3 with the phrase `origin/main introuvable`

### Requirement: Logic in a service function, JSON contract
The system SHALL compute the scan in a service function that returns a report record. The text output and the `--json` output (versioned by a `format` field, design D6) SHALL only format that record. The system SHALL NOT keep a scanning or counting rule in the formatting code alone. Untested until implemented.

#### Scenario: Same result in both outputs
- **WHEN** the same range is scanned with and without `--json`
- **THEN** both outputs give the same findings, counts and exit code

#### Scenario: Function call
- **WHEN** the service function is called on a throwaway repository with a planted finding
- **THEN** it returns a report that holds that finding, with no printed output

### Requirement: The scan imports under Python 3.9
The system SHALL keep `tools/range_scan.py` importable by Python 3.9: `from __future__ import annotations` as its first import, and no 3.10 form evaluated at run time (change train-auto-launchd-env, design D4). It SHALL NOT let an annotation crash its import with a trace instead of its own exit codes.

#### Scenario: Future import first
- **WHEN** the source of `tools/range_scan.py` is read
- **THEN** its first import statement is `from __future__ import annotations`

#### Scenario: 3.9 grammar
- **WHEN** the source is parsed with the Python 3.9 grammar
- **THEN** it parses without error
