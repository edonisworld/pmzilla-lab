# tooling-user-manual Specification

## Purpose
The system SHALL generate, by reading the sources and never running them, a deterministic user manual of every command, and keep it current through a blocking test.

## Requirements

### Requirement: A generated manual of every command
The system SHALL provide a generator that produces the French user manual of the repository's commands, one section per feature area in the order of design D2: every Python script with an entry point and every shell script of the tools folder, the test runner script, and every slash command. It SHALL NOT describe library modules without an entry point, hook scripts or launchd templates; a closing « Hors du manuel » section names the last two.

#### Scenario: Library module skipped
- **WHEN** the fake repository holds a Python module with no entry point next to a script with one
- **THEN** only the script appears in the manual

#### Scenario: Hooks named, not described
- **WHEN** the fake repository holds a hook script and a launchd template
- **THEN** neither has an entry, and the closing « Hors du manuel » section names them

#### Scenario: Slash command placed in its area
- **WHEN** the feature table maps a slash command to an area
- **THEN** the command appears in that area's section, in the order of design D2

### Requirement: Scheduled launches noted
The system SHALL add the note « lancée aussi par une tâche planifiée » to the entry of a script that a launchd template of the tools folder names, reading the template as text only. It SHALL NOT load, start or change a scheduled job.

#### Scenario: Wrapper named by a template
- **WHEN** a launchd template of the fake repository names a shell script
- **THEN** that script's entry carries the note « lancée aussi par une tâche planifiée »

### Requirement: Sources read, never run
The system SHALL build the manual only by reading files: the syntax tree of the Python scripts, the leading comments of the shell scripts, the front-matter of the slash commands and the deny list of the settings file. It SHALL NOT import, execute or launch a script it describes, nor start any process.

#### Scenario: Booby-trapped fixture
- **WHEN** every fixture script would write a sentinel file if imported or executed
- **THEN** after generation no sentinel file exists

### Requirement: Content of each entry
The system SHALL give each command its role, who launches it, its subcommands, its parameters with their choices and defaults, its exit codes and one example, with the French headings and labels of design D11, copying help texts as written. It SHALL NOT show an argument whose help is suppressed, nor translate a help text.

#### Scenario: Parameters table
- **WHEN** a subcommand has an option with choices and a default
- **THEN** its row shows the choices under `Valeurs` and the default under `Défaut`

#### Scenario: Hidden test option
- **WHEN** an argument's help is suppressed
- **THEN** neither its name nor its help appears in the manual

### Requirement: Argparse extraction from the syntax tree
The system SHALL read parsers, nested subparsers, argument groups and each argument's names, destination, required flag, action, number of values, choices, default and help as design D5 says, rendering any non-literal value as « valeur calculée ». A script with an entry point and no parser SHALL be listed with its role and usage lines. It SHALL NOT resolve a variable or call.

#### Scenario: Computed choices
- **WHEN** an argument's choices come from a module constant
- **THEN** its `Valeurs` cell is « valeur calculée »

#### Scenario: Mutually exclusive options
- **WHEN** two options belong to a mutually exclusive group
- **THEN** they are shown together under the label « un seul parmi »

#### Scenario: Script without argparse
- **WHEN** a script has an entry point, a docstring with usage lines and no parser
- **THEN** its entry gives its role, its usage lines and « paramètres : voir l'usage »

### Requirement: Shell headers and slash-command front-matter
The system SHALL read a shell script's role, usage lines and exit codes from its leading comment block, and a slash command's description, argument hint and model from its front-matter, as design D5 says. It SHALL NOT read the rest of a shell script or the body of a slash command.

#### Scenario: Shell header
- **WHEN** a shell script's header has a role, two usage lines and a codes line
- **THEN** its entry shows that role, those usage lines and those codes

#### Scenario: Slash command
- **WHEN** a slash command's front-matter has a description, an argument hint and a model
- **THEN** its entry shows them, with « Claude Code seulement »

### Requirement: Who launches, from the deny rules
The system SHALL mark a script or subcommand « Terminal seulement » when one of its synthetic launch forms matches a deny rule, with the matching of the permission-guards test, « Terminal ou Claude Code » otherwise, and « Terminal seulement avec » an option when only a form with that option matches (design D7). It SHALL NOT write or change the settings file.

#### Scenario: Denied subcommand
- **WHEN** a deny rule matches the launch of one subcommand and not another
- **THEN** the first is « Terminal seulement » and the second « Terminal ou Claude Code »

#### Scenario: Option-only rule
- **WHEN** a deny rule matches a subcommand only with an option value
- **THEN** the subcommand carries the note « Terminal seulement avec » that option

#### Scenario: Same verdict as the guard test
- **WHEN** a shared list of launch forms is matched by the generator and by the permission-guards test
- **THEN** both give the same verdict for every form

### Requirement: Exit codes from one convention
The system SHALL read exit codes from a « Codes : » line or a « Codes de sortie » section of the docstring or header, and SHALL write « codes de sortie non documentés » when none is found, without failing. It SHALL NOT infer exit codes from the code. The commands without codes are listed in the test-gaps file.

#### Scenario: Codes documented
- **WHEN** a docstring holds a « Codes : » line
- **THEN** the entry lists those codes as written

#### Scenario: Codes absent
- **WHEN** a script documents no exit code
- **THEN** its entry says « codes de sortie non documentés » and the generation exits 0

### Requirement: One example without placeholder
The system SHALL give each command one example: the first usage line that launches it, otherwise one generated when every required argument has choices or a default (design D3). A test SHALL fail naming each command left without an example, and each example holding a placeholder. It SHALL NOT invent a value for a required argument.

#### Scenario: Example from the docstring
- **WHEN** a docstring holds a usage line that launches the script with no placeholder
- **THEN** that line is the example

#### Scenario: Placeholder refused
- **WHEN** the only usage line of a script holds an angle-bracket placeholder and a required argument has no default
- **THEN** the command has no example and the test names it

### Requirement: One feature table, complete and current
The system SHALL place each command in its feature area through one table in the generator. A test SHALL fail naming every command found in the sources and absent from the table, and every table entry naming no existing command. It SHALL NOT read a feature area from the scripts.

#### Scenario: Unclassified command
- **WHEN** a new script with an entry point is absent from the table
- **THEN** the table test fails and names it

#### Scenario: Stale entry
- **WHEN** a table entry names a script that no longer exists
- **THEN** the table test fails and names the entry

### Requirement: Command line, messages and exit codes
The system SHALL print the manual by default, write the manual file with the write option, and with the check option exit 1 with the stale or missing message of design D10, giving the regeneration command. It SHALL exit 0 on success and 2 on a usage error or an unreadable source, and SHALL NOT write any file without the write option.

#### Scenario: Check on a stale manual
- **WHEN** the manual file differs from the output and the check option is given
- **THEN** the exit code is 1, the message gives `uv run tools/manual.py --write`, and no file changes

#### Scenario: Unknown option
- **WHEN** an unknown option is given
- **THEN** the exit code is 2 and nothing is written

### Requirement: Deterministic output
The system SHALL produce identical bytes from identical sources, in the stable order of design D12. It SHALL NOT write a date, a time, an absolute path, a user name or a host name in the manual.

#### Scenario: Two runs, two roots
- **WHEN** the same fake repository is generated twice, from two different folder paths
- **THEN** the two outputs are byte-identical and hold no absolute path

### Requirement: The committed manual stays current
The system SHALL be covered by a blocking test that fails when the committed manual differs from the generator's output on the repository, giving the regeneration command. A manual in merge conflict SHALL be regenerated; it SHALL NOT be edited by hand.

#### Scenario: Command added without regeneration
- **WHEN** a script gains an option and the manual is not regenerated
- **THEN** the freshness test fails and its message gives `uv run tools/manual.py --write`

### Requirement: Freshness suite selected from the staged files
The system SHALL make the staged-file selector select the manual suite when a Python or shell script of the tools folder, a slash command or the manual file is staged; the manual is the one documentation path that selects a suite. This selection SHALL NOT stand for a suite of the path: a code path no test names still requires the complete run.

#### Scenario: Manual edited alone
- **WHEN** only the manual file is staged
- **THEN** the selector selects the manual suite and the always-selected guard suites

#### Scenario: Unmapped script
- **WHEN** a tools script that no test names is staged
- **THEN** the selector still requires the complete run

### Requirement: English stub in the edition
The system SHALL classify the manual as a template in the edition manifest, replaced by a short English stub that says the manual is generated in French, that an English version is planned, and points to the generator's help. The real-repository tests SHALL be excluded from the edition; the generator and the fixture tests SHALL NOT be.

#### Scenario: Edition tree
- **WHEN** an edition tree is built
- **THEN** its manual equals the stub, byte for byte, and the generator and fixture tests are present

### Requirement: README link
The system SHALL link the manual from the README's contents list with the label « User manual (French, generated) » and name the generator where the README lists the tools. The link SHALL NOT point to a file absent from the private repository or the edition.

#### Scenario: Link present
- **WHEN** the README is read by the suite
- **THEN** it holds a link to the manual path with that label

### Requirement: The generator is safe for the session
The system SHALL ship the generator with a PEP 723 header and a lock file, list it in its own manual, and let the session run it: no deny rule SHALL match any of its launch forms. It SHALL NOT open a database session, read the Keychain or contact the network. Untested until implemented (suite `manual`).

#### Scenario: Own entry
- **WHEN** the manual of the real repository is generated
- **THEN** the generator's entry says « Terminal ou Claude Code »

### Requirement: Tests on a fake repository
The system SHALL be covered by a suite that builds a temporary fake repository of fixture scripts, slash commands and settings, and checks the manual produced from it (design D13). The suite SHALL NOT run any fixture or repository script other than the generator, need the network, or write outside its temporary folder.

#### Scenario: Isolation
- **WHEN** the suite runs
- **THEN** no fixture script runs and no file outside the temporary folder is written
