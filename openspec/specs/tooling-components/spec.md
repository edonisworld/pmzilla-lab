# tooling-components Specification

## Purpose
The system SHALL inventory every component of the lab (packages, Python, database image, Ollama models, tools) in a checkable format and check weekly, without installing anything, for newer published versions.

## Requirements

### Requirement: The component inventory has a fixed, checkable format
The system SHALL keep a tracked inventory document in the documentation folder listing every component once, each with exactly a unique name, a kind among the kinds of design.md D2, the place where its version is fixed (or "not pinned" with the channel it follows), the type of upstream source of new versions, and the heading of the installation guide section that describes its update, plus optional flags among those of design.md D2. The inventory SHALL NOT copy the version used (it is read where it is fixed, fiche C15), SHALL NOT hold an address, a credential, or a person's, team's or project's name, and SHALL NOT accept any other field. Untested until implemented.

Source: to be covered by tests/composants (task 2.1)

#### Scenario: Unknown field
- **WHEN** an entry has a field outside those of design.md D2
- **THEN** the inventory command exits 1 and names the component and the field

#### Scenario: Missing procedure
- **WHEN** an entry has no procedure, or names a heading absent from the installation guide
- **THEN** the inventory command exits 1 with the key phrase "Champ manquant" or "Procédure introuvable dans le guide d'installation" and the component's name

#### Scenario: Copied version
- **WHEN** an entry carries a version field
- **THEN** the inventory command exits 1 and names the field as unknown

### Requirement: The inventory command resolves versions without network
The system SHALL provide an inventory subcommand that reads the inventory and prints, for each component, its kind, the version used read where it is fixed (lock files, root Python version file, compose file, BMAD manifest, vendored version file, model settings), or "non épinglé" for an unpinned tool, and where it is fixed. For a Python package locked at different versions by different scripts it SHALL list each version with the scripts concerned. It SHALL exit with the codes of design.md D1. It SHALL NOT open any network connection, run any upstream query, or write any file.

Source: to be covered by tests/composants (task 2.2)

#### Scenario: Locks disagree
- **WHEN** two lock files fix different versions of the same package
- **THEN** the line of that package lists both versions with their scripts

#### Scenario: Inventory missing
- **WHEN** the inventory document does not exist
- **THEN** the command exits 2 with a message on the error output

#### Scenario: No network
- **WHEN** the command runs with every non-loopback connection made to fail
- **THEN** it succeeds and no connection is attempted

### Requirement: The inventory test rebuilds the component list from the repository sources
The system SHALL include, in the suites of the test runner, a test that rebuilds the list of used components from the sources of design.md D2 (script headers and lock files, root Python version file, compose file, model settings, install prerequisites, BMAD manifest, OpenSpec configuration, vendored version files, the test runner's extra dependencies) and compares it with the inventory. It SHALL fail when a used component is missing, naming it and its source with the key phrase "Composant à ajouter à l'inventaire", and when the inventory keeps a component no longer used, with the key phrase "Composant à retirer de l'inventaire". Dependencies of a private tool SHALL count only when the tool is present and SHALL NOT be reported as unused when it is absent. The test SHALL read configuration files for their structure only and SHALL NOT print configuration values other than component names and versions. It SHALL NOT touch the network.

Source: to be covered by tests/composants (tasks 2.3 and 2.4)

#### Scenario: New dependency in a header
- **WHEN** a script header declares a package that the inventory does not list
- **THEN** the test fails and names the package and the script

#### Scenario: Component no longer used
- **WHEN** the inventory lists a package that no header, lock file or runner option declares
- **THEN** the test fails and names the package to remove

#### Scenario: Private tool absent
- **WHEN** a private tool is absent and the inventory lists a package that only that tool declares
- **THEN** the test does not report it

#### Scenario: Real repository
- **WHEN** the test runs on the repository
- **THEN** it passes, and fails as soon as a commit adds a component without its inventory entry

### Requirement: The image tag and its digest move together
The system SHALL fail the inventory test when an image line of the compose file has no tag or the `latest` tag, or when the digest recorded beside it is missing or is recorded for another tag, with the key phrase "Empreinte de l'image à mettre à jour avec l'étiquette". It SHALL NOT pull the image or query a registry for this check.

Source: to be covered by tests/composants (task 2.3)

#### Scenario: Tag changed alone
- **WHEN** the tag of the image line is changed and the digest comment still names the former tag
- **THEN** the test fails with the key phrase

### Requirement: The check compares with the latest published versions and installs nothing
The system SHALL provide a check subcommand that, for each component, reads the version used (or the local version of an unpinned tool through its version option), queries the upstream source type of design.md D5, and reports updates, major versions, pre-releases and republished tags as separate natures following design.md D8, with the key phrases of design.md D1. It SHALL NOT install, upgrade, download or start anything: no `brew install`, `brew upgrade` or `brew update`, no `ollama pull`, no `npm install`, no `docker pull`, no `uv sync`, no tool or self upgrade of uv, no start of the model service, of the container engine or of a container, and no write to any file of the repository. A missing tool SHALL be recorded as absent, not as an error. Untested until implemented.

Source: to be covered by tests/composants (tasks 3.1 to 3.6)

#### Scenario: Update available
- **WHEN** the fake registry publishes a newer version with the same major
- **THEN** the output has a line with the component, the used and available versions and the nature "mise à jour"

#### Scenario: Major and pre-release kept apart
- **WHEN** the fake registry publishes a newer major and a newer pre-release
- **THEN** they are reported with the natures "version majeure" and "préversion", and neither as "mise à jour"

#### Scenario: No install command
- **WHEN** a full check runs with fake commands recording their calls
- **THEN** none of the forbidden commands of design.md D5 was called and every repository file is unchanged

### Requirement: Version natures follow each ecosystem
The system SHALL classify versions by the rules of design.md D8: PEP 440 for Python packages (yanked versions ignored, post-releases as releases), the second segment for the Python runtime, semver with an optional leading "v" for npm packages, BMAD modules, vendored libraries and release lists, the `<version>-pg<N>` form for the database image (a higher `<N>` is a major version, other tag forms are ignored or pre-releases), the stable version for Homebrew packages, and the digest for model tags. It SHALL NOT report a pre-release as an update nor merge a major version with an update.

Source: to be covered by tests/composants (task 3.1)

#### Scenario: Leading v
- **WHEN** a BMAD module is used at a version written with a leading "v" and the registry publishes the same version without it
- **THEN** the module is up to date

#### Scenario: Database line
- **WHEN** the registry publishes a newer version of the same PostgreSQL line and a tag for a higher PostgreSQL line
- **THEN** the first is an update and the second a major version

#### Scenario: Zero major
- **WHEN** a package used at a `0.x` version has a newer `0.y` version
- **THEN** it is reported as a major version

### Requirement: Python dependencies are checked by a dry run on temporary copies
The system SHALL, for each lock file, copy the script and its lock into a fresh temporary folder and run there the uv locking with upgrade, in dry-run mode when the installed uv supports it, read the packages that would change, report direct dependencies by name and transitive ones as a count per script with the key phrase "Dépendances Python", and remove the temporary folder. It SHALL NOT pass a repository lock file to a writing command, SHALL NOT run `uv sync`, and a failing dry run SHALL mark the packages concerned incomplete without stopping the check.

Source: to be covered by tests/composants (task 3.4)

#### Scenario: Locks unchanged
- **WHEN** the check runs with a fake uv that rewrites the lock it is given
- **THEN** every repository lock file is byte-identical after the run

#### Scenario: Dry run fails
- **WHEN** the fake uv fails for one script
- **THEN** that script's packages are marked incomplete and the other scripts are checked

### Requirement: The check never cleans the uv cache
The system SHALL NOT run `uv cache clean` or `uv cache prune`, in the check or in any of its steps, whatever the outcome of the dry run.

Source: to be covered by tests/composants (task 3.4)

#### Scenario: Script text and calls
- **WHEN** the script text is read and a full check runs with a recording fake uv
- **THEN** the text holds no cache-cleaning command and no recorded call is a cache-cleaning one

### Requirement: Model tags are compared by digest
The system SHALL compare the local digest of each configured model, read from the local API of the model service, with the registry digest of the same tag, report a difference as a republished tag, and flag the embedding model "requires reindex". When the model service does not answer, the models SHALL be marked incomplete. It SHALL NOT download a model or start the service.

Source: to be covered by tests/composants (task 3.5)

#### Scenario: Embedding model republished
- **WHEN** the fake registry gives another digest for the embedding model's tag
- **THEN** the novelty has the nature "étiquette republiée" and the flag requires reindex

#### Scenario: Service down
- **WHEN** the local API does not answer
- **THEN** the models are incomplete, no command starts the service, and the other components are checked

### Requirement: Network access is bounded and a failure only makes the check incomplete
The system SHALL give every upstream request a bounded timeout, configurable by option or environment variable with a default for missing or invalid values, make no retry within a run, send no authentication header, and read no token, keychain entry or credential file. A source that times out, refuses, answers with an unexpected status or an unreadable body SHALL mark its component incomplete with the error type only, and the check SHALL go on. A run where any component is incomplete SHALL print the key phrase "Veille des composants incomplète" with the number of unreachable sources and SHALL NOT exit with code 2 for that reason. Upstream base addresses SHALL be constants of the script, overridable by environment variables for tests.

Source: to be covered by tests/composants (task 3.3)

#### Scenario: Timeout
- **WHEN** the fake server answers one source after the timeout
- **THEN** that component is incomplete, the others are checked, and the exit code follows the notification rule

#### Scenario: Invalid timeout setting
- **WHEN** the timeout setting is not a number
- **THEN** the default timeout is used

### Requirement: The check runs once a week, with catch-up, when asked
The system SHALL, with the due option, run the check only when no check was attempted today and either today is the configurable weekly day or the last complete check is older than seven days or absent (fiche C1), so that one complete check happens each week, on the weekly day or at the first following watch run; otherwise it SHALL print "Veille des composants : pas due", query nothing and exit 0. Once a complete check is recorded, the due option SHALL NOT query the network again before the next weekly day. Without the due option (manual run by the user) the check SHALL always run. Today's date SHALL be replaceable by an environment variable for tests.

Source: to be covered by tests/composants (task 3.7)

#### Scenario: Weekly day
- **WHEN** today is the weekly day and no check was attempted today
- **THEN** the check runs

#### Scenario: Catch-up at the first following run
- **WHEN** today is not the weekly day, no check was attempted today and the last complete check is older than seven days or absent
- **THEN** the check runs

#### Scenario: Not due after a complete check
- **WHEN** today is not the weekly day and the last complete check is at most seven days old
- **THEN** no source is queried, "Veille des composants : pas due" is printed and the exit code is 0

#### Scenario: Not due
- **WHEN** today is the weekly day and a check was already attempted today
- **THEN** no source is queried and the exit code is 0

### Requirement: The check records its result in a state file
The system SHALL write the result to a state file of the data folder, with owner-only permissions, atomically, holding the content of design.md D6 (dates of the last attempt and last complete check, completeness, per-component versions, natures, flags, incompleteness with the error type, suggested job title, and the pairs already notified). It SHALL NOT write any address, credential, error message text, or person's, team's or project's name to it. An unreadable or unwritable state SHALL give the key phrase "Veille des composants impossible" and exit 2.

Source: to be covered by tests/composants (task 3.6)

#### Scenario: Incomplete run
- **WHEN** one source fails
- **THEN** the state keeps the previous date of the last complete check and records the attempt

#### Scenario: Permissions
- **WHEN** the state file is written
- **THEN** only its owner can read it

### Requirement: The check says when there is something to notify
The system SHALL exit 1 when the run reports at least one component and version pair not yet notified, and then record those pairs as notified; it SHALL exit 1 as well, with the key phrase "Aucune vérification complète des composants depuis", when the last complete check is older than a configurable number of weeks, at most once a week on the weekly day; otherwise it SHALL exit 0. A network failure alone SHALL NOT give exit code 1. A pair already notified SHALL NOT make the check exit 1 again.

Source: to be covered by tests/composants (task 3.7)

#### Scenario: Same novelty next week
- **WHEN** a check reports a version already notified by the previous check
- **THEN** it is still listed but the exit code is 0

#### Scenario: Network down for weeks
- **WHEN** every check has been incomplete for longer than the staleness limit and today is the weekly day
- **THEN** the exit code is 1 with the staleness key phrase; the next day it is 0

### Requirement: Each novelty comes with a ready-to-paste job title, and nothing writes the work queue
The system SHALL print for each novelty a suggested job title "Mettre à jour <name> <used> → <available>" with the procedure heading and the flags, and record it in the state. It SHALL NOT write the work queue, its archive, the inventory, or any document of the documentation folder.

Source: to be covered by tests/composants (task 3.6)

#### Scenario: Suggested job
- **WHEN** a BMAD module has a newer version
- **THEN** the output has "Job proposé : Mettre à jour" with the module, both versions, and the procedure heading, and the work queue document is unchanged

### Requirement: The automated tests never touch the network
The system SHALL run every test of the component tooling, including the inventory test of the test runner, without network access: upstream sources through an injected fetcher or a loopback server, local commands through recording fakes on the path, and a guard that makes any connection to a non-loopback address fail the test.

Source: to be covered by tests/composants (task 2.1)

#### Scenario: Guard
- **WHEN** a test triggers a request to a non-loopback address
- **THEN** the test fails and names the attempted connection kind without its address

### Requirement: The CI image's pinned items are inventoried by name and checked against the definition
The system SHALL hold in `docs/pmzilla/composants.yaml` one entry per pinned item of the CI image (base image, uv image, OpenSpec CLI) with `pinned_in: CI Dockerfile`, and SHALL NOT copy any digest or version into the inventory: values live in `ci/Dockerfile` only (design D4, decision C15). The inventory test SHALL check the definition against the entries and name any value still to be filled by the author.

#### Scenario: Item pinned in the definition without an entry
- **WHEN** `ci/Dockerfile` pins an item that has no `pinned_in: CI Dockerfile` entry in the inventory
- **THEN** `tests/composants` fails and names the item

#### Scenario: Entry without a pinned item
- **WHEN** an inventory entry says `pinned_in: CI Dockerfile` and `ci/Dockerfile` does not use that item
- **THEN** `tests/composants` fails and names the entry

#### Scenario: Unpinned or malformed base
- **WHEN** `ci/Dockerfile` names an image by a tag without digest, or with a malformed digest
- **THEN** `tests/composants` fails

#### Scenario: CLI version and Python
- **WHEN** the OpenSpec CLI is pinned without an exact version, or the Python differs from `.python-version`
- **THEN** `tests/composants` fails

#### Scenario: No value in the inventory
- **WHEN** an inventory entry of the CI image carries a digest
- **THEN** `tests/composants` fails: the value belongs in `ci/Dockerfile` only

### Requirement: Mothra's Node is pinned in one version file and inventoried apart from BMAD's
The system SHALL accept the inventory kind `node-runtime`, read the version of Mothra's Node from `mothra/.node-version`, and keep one entry for it distinct from BMAD's unpinned `node`; the inventory test SHALL require the entry exactly when the file exists and refuse an invalid version with the phrase of design D2. It SHALL NOT copy the version, nor write one before the author's LTS check (design D1 of mothra-node-lts). Untested until implemented (suite `composants`).

#### Scenario: File without entry
- **WHEN** a fake repository holds a valid `mothra/.node-version` and no `node-runtime` entry
- **THEN** the inventory test fails with "Composant à ajouter à l'inventaire" naming the version file

#### Scenario: Alias instead of a version
- **WHEN** the version file holds `lts/*` or a version with a `v` prefix
- **THEN** the inventory command exits 1 with `version de Node de Mothra invalide : <texte> (attendu MAJEUR.MINEUR.CORRECTIF)`

#### Scenario: BMAD's Node unchanged
- **WHEN** the inventory is printed with both entries
- **THEN** BMAD's `node` is still reported as not pinned and Mothra's Node with the version read from its file

### Requirement: The check of Mothra's Node reports only LTS lines as major versions
The system SHALL, in the weekly check, report a newer patch or minor of the pinned line as an update, a newer line marked LTS in the official release list as a major version, and SHALL NOT report a newer line that the list does not mark LTS. A release list without the LTS marker SHALL make the component incomplete. It SHALL NOT install or download Node. Untested until implemented (suite `composants`).

#### Scenario: Current line published
- **WHEN** the fake release list holds a newer line not marked LTS
- **THEN** nothing is reported for it

#### Scenario: Next LTS line
- **WHEN** the fake release list marks a newer line LTS
- **THEN** it is reported with the nature "version majeure" and a suggested job naming the procedure "Update the Node of Mothra"

### Requirement: The CI image runs exactly Mothra's Node
The system SHALL fail the inventory test, when both the local CI's image definition and `mothra/.node-version` exist and the image's Node version differs from the file's, with `Node de l'image de CI différent du Node de Mothra : <version de l'image> contre <version du fichier>`, and SHALL skip the check with `contrôle Node de l'image sauté : <fichier> absent` while either is missing. It SHALL NOT pull the image or query a registry. Untested until implemented (suite `composants`).

#### Scenario: Patch moved on one side
- **WHEN** the version file is moved to a newer patch and the image line is not
- **THEN** the inventory test fails with the phrase naming both versions

#### Scenario: No image definition yet
- **WHEN** the repository has no image definition of the local CI
- **THEN** the check is skipped with its reason and the test passes
