# tooling-edition Specification

## Purpose
TBD - created by archiving change build-edition. Update Purpose after archive.
## Requirements
### Requirement: The edition is built from a committed state into a new folder
The system SHALL provide an edition generator that takes a language and an output folder, plus an optional commit that defaults to the current head. The generator SHALL read the list of files and their content from the Git objects of that commit, never from the working tree. It SHALL refuse a working tree that has a modified, staged or untracked non-ignored file with exit code 3 and the key phrase "working tree not clean", and SHALL refuse an unknown commit with exit code 3. It SHALL refuse with exit code 4 an output folder that already exists, whose staging or not-publishable sibling exists, whose parent is missing, or that lies inside the private workspace. It SHALL accept only the English language and SHALL exit with code 2 on a usage error. The generator SHALL NOT copy any untracked file into the tree, SHALL NOT write a Git folder in the output, and SHALL NOT overwrite an existing folder. Exit codes and messages are those of design.md (D8, D10). Untested until implemented.

#### Scenario: Dirty working tree
- **WHEN** the private workspace has an untracked file that is not ignored
- **THEN** the generator exits with code 3, prints "working tree not clean" and creates no folder

#### Scenario: Untracked ignored file
- **WHEN** an ignored file exists in the workspace and the tree is otherwise clean
- **THEN** the build goes on and the ignored file is absent from the output

#### Scenario: Committed content only
- **WHEN** a file is committed and the build runs on that commit
- **THEN** the output holds the committed content of that file and no Git folder

#### Scenario: Existing output
- **WHEN** the output folder already exists
- **THEN** the generator exits with code 4 and the folder is unchanged

#### Scenario: Output inside the workspace
- **WHEN** the output folder is inside the private workspace
- **THEN** the generator exits with code 4 and writes nothing

#### Scenario: Unsupported language
- **WHEN** the language is not English or is missing
- **THEN** the generator exits with code 2

### Requirement: Every tracked file is classified by the manifest, fail closed
The system SHALL classify every tracked file of the commit with the rules of a tracked edition manifest, the first matching rule winning. The possible actions SHALL be: include; exclude, which requires a reason; or replace by a neutral template taken from the same commit. A tracked file matched by no rule SHALL stop the build before any copy, with exit code 6 and the key phrase "unclassified tracked paths:" followed by every unclassified path. A manifest that cannot be parsed, has an unknown action, an exclude rule without a reason, a template rule whose template is absent, or a rule that matches no tracked path SHALL stop the build with exit code 5 and the key phrase "manifest invalid:". The generator SHALL NOT guess a classification for an unmatched file. The manifest, its templates, the generator and its test suite SHALL be excluded from the edition. Untested until implemented.

#### Scenario: Unclassified file
- **WHEN** a tracked file matches no rule
- **THEN** the generator exits with code 6, lists that path and writes no tree

#### Scenario: Exclude without reason
- **WHEN** an exclude rule has no reason
- **THEN** the generator exits with code 5

#### Scenario: Stale rule
- **WHEN** a rule matches no tracked path
- **THEN** the generator exits with code 5 and names the rule

#### Scenario: Known out-of-edition files
- **WHEN** the manifest excludes the private roadmap documents, the plan of the English version, the library-gaps document, the round-table outputs, the batch-7 correspondence output, the documentation archives and the archived OpenSpec changes
- **THEN** none of them is in the output

#### Scenario: A tracked file without a rule
- **WHEN** the manifest has no rule for a tracked file, such as a file added after the manifest was written
- **THEN** the build stops with code 6 and names it

### Requirement: Whole files only, never rewritten
The system SHALL copy an included file byte for byte, keeping its executable bit. It SHALL write nothing for an excluded file. For a templated file, it SHALL write the bytes of the template at the path of the replaced file. The generator SHALL NOT edit, cut, concatenate or substitute text inside any file. Untested until implemented.

#### Scenario: Included file
- **WHEN** a tracked script is included
- **THEN** its bytes and executable bit in the output equal those of the commit

#### Scenario: Templated file
- **WHEN** the author's book catalogue is classified as a template
- **THEN** the output file at the catalogue path equals the neutral template, byte for byte

### Requirement: English CHANGELOG starting at the edition
The system SHALL give the edition a CHANGELOG written in English that starts at the edition, taken whole from a tracked source file through a template rule. The system SHALL NOT ship the French history of the private CHANGELOG, in whole or in part. Untested until implemented.

#### Scenario: CHANGELOG source missing
- **WHEN** the template source of the edition CHANGELOG does not exist in the commit
- **THEN** the generator exits with code 5

#### Scenario: French history absent
- **WHEN** a tree is built
- **THEN** its CHANGELOG equals the English template and differs from the private CHANGELOG

### Requirement: Publication check on the generated tree
The system SHALL run the publication check on the staging tree as the last step of the build. The check has two parts:
- the personal-identifier scanner in tree mode, with the identifiers of the private workspace (the local identifiers file included), no tolerated file, and sanctums instantiated from the tree's own skills;
- the sensitive-name matching rules of the pre-commit hook, applied to every non-binary file of the tree whatever its size.

On any occurrence, the system SHALL:
- exit with code 7;
- print one line per occurrence, giving the path relative to the tree and the line number with the key phrase "personal identifier in" or "sensitive name in", then the "not publishable:" summary;
- rename the tree to the not-publishable sibling name.

When the sensitive-names list is absent or empty, or the scanner fails, the system SHALL:
- exit with code 8 and the key phrase "publication check could not run:";
- delete the staging tree.

The system SHALL NOT print a matched value nor the text of a line, SHALL NOT tolerate any file, and SHALL NOT name the output folder without suffix unless every check passed. Untested until implemented.

#### Scenario: Clean tree
- **WHEN** no identifier and no sensitive name occurs in the tree or in the generated sanctums
- **THEN** the generator exits with code 0, the tree is at the output path and the last line says "publishable tree written to"

#### Scenario: Identifier in a file
- **WHEN** an included file contains an identifier of the session in capitals
- **THEN** the generator exits with code 7, prints the file and the line number, contains no identifier in its output, and the tree is kept under the not-publishable name

#### Scenario: Extra string from the local identifiers file
- **WHEN** the local identifiers file lists a string, such as an employer name, that appears in an included test file
- **THEN** the generator exits with code 7 and names that file and line

#### Scenario: Sensitive name in a large file
- **WHEN** a file larger than the hook's size limit contains a listed name
- **THEN** it is reported and the exit code is 7

#### Scenario: Sanctum template writes a personal path
- **WHEN** a posture skill of the tree generates a sanctum that contains the private root path
- **THEN** the occurrence is reported under the sanctum key and the exit code is 7

#### Scenario: Former names still present
- **WHEN** the build runs before the change that removes the former names is merged, so that included files still carry a former name holding an identifier
- **THEN** the generator exits with code 7 and lists those files and lines

#### Scenario: Sensitive-names list absent
- **WHEN** the sensitive-names list is absent or holds only comments
- **THEN** the generator exits with code 8 and no tree remains

### Requirement: Optional test run in the generated tree
The system SHALL, with the test-run option, run the full test runner on a copy of the publishable tree, placed in a temporary folder outside the output with a throwaway repository and one commit. It SHALL run the runner without the variable reserved to git commit and without any bypass variable, print the runner's total line, and delete the temporary folder. On a red run it SHALL exit with code 1 and the key phrase "tests red in the generated tree", and rename the tree to the not-publishable name. Without the option, the system SHALL print the commands that the user runs after creating their repository. The system SHALL NOT run a filtered or targeted run instead of the full one. Untested until implemented.

#### Scenario: Green run
- **WHEN** the test-run option is given and every suite passes in the copy
- **THEN** the exit code is 0 and the output holds the runner's total line

#### Scenario: Manifest inconsistent with the runner
- **WHEN** a shell suite listed in the runner is excluded by the manifest
- **THEN** the run is red, the exit code is 1 and the tree carries the not-publishable name

#### Scenario: Without the option
- **WHEN** the option is not given
- **THEN** no test runs and the output lists the commands to run

### Requirement: The generator publishes nothing and runs nothing paid or private
The system SHALL NOT, while building the edition:
- create a remote repository, push, publish, or initialise a repository in the output folder;
- run the posture evaluation set or the automatic evaluation script;
- run the real Jira tools, the database scripts, or the import and compare tools;
- connect to the database or make any network call.

The last line of a successful build SHALL say that no repository was created and nothing was pushed. Untested until implemented.

#### Scenario: Forbidden commands
- **WHEN** the generator's text is scanned outside comments
- **THEN** it contains no push, no remote creation, no evaluation-set launch, no Jira or database tool launch

#### Scenario: Success message
- **WHEN** a build succeeds
- **THEN** the output says that nothing was pushed and no repository was created

### Requirement: The edition ships the install script and its suite
The system SHALL classify the install script's bootstrap and orchestrator with explicit include rules, placed before the broad rule of the tools folder, so that their presence in the edition is a stated intent and does not depend on the broad rule. The install-script test suite SHALL be included through the tests rule. The bootstrap SHALL keep its executable bit in the tree. The install-script suite SHALL read no file that the manifest excludes or replaces, so that the test run in the generated tree stays green. Untested until implemented.

#### Scenario: Script in the tree
- **WHEN** a tree is built
- **THEN** it holds the bootstrap with its executable bit, the orchestrator and the install-script suite, byte for byte

#### Scenario: Explicit rule removed
- **WHEN** the explicit include rule of the orchestrator is removed from the manifest
- **THEN** the edition-manifest test fails and names the install script

