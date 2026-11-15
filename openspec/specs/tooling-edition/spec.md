# tooling-edition Specification

## Purpose
An edition generator that builds a shareable English tree from the Git objects of one commit into a new folder, classifying every tracked file by the edition manifest, copying whole files only (the one exception: marked blocks that the manifest declares with `strip_blocks` on an included file are removed, never rewritten), checking the tree for personal identifiers, sensitive names, book text and product version numbers before naming it publishable, and optionally running the full test runner in a throwaway copy. It writes no Git folder and publishes nothing.

## Requirements

### Requirement: The edition is built from a committed state into a new folder
The system SHALL provide an edition generator that takes a language and an output folder, plus an optional commit that defaults to the current head. The generator SHALL read the list of files and their content from the Git objects of that commit, never from the working tree. Exit codes and messages are those of design.md (D8, D10).

#### Scenario: Committed content only
- **WHEN** a file is committed and the build runs on that commit
- **THEN** the output holds the committed content of that file and no Git folder

Source: tests/build_edition/test_generateur_source.py (usage, source, output and order of the checks)

### Requirement: The generator refuses an unclean working tree or an unknown commit
The generator SHALL refuse a working tree that has a modified, staged or untracked non-ignored file with exit code 3 and the key phrase "working tree not clean", and SHALL refuse an unknown commit with exit code 3.

#### Scenario: Dirty working tree
- **WHEN** the private workspace has an untracked file that is not ignored
- **THEN** the generator exits with code 3, prints "working tree not clean" and creates no folder

Source: tests/build_edition/test_generateur_source.py (usage, source, output and order of the checks)

### Requirement: The generator refuses an unusable output folder
The generator SHALL refuse with exit code 4 an output folder that already exists, whose staging or not-publishable sibling exists, whose parent is missing, or that lies inside the private workspace.

#### Scenario: Existing output
- **WHEN** the output folder already exists
- **THEN** the generator exits with code 4 and the folder is unchanged

#### Scenario: Output inside the workspace
- **WHEN** the output folder is inside the private workspace
- **THEN** the generator exits with code 4 and writes nothing

Source: tests/build_edition/test_generateur_source.py (usage, source, output and order of the checks)

### Requirement: The generator accepts only English
The generator SHALL accept only the English language and SHALL exit with code 2 on a usage error.

#### Scenario: Unsupported language
- **WHEN** the language is not English or is missing
- **THEN** the generator exits with code 2

Source: tests/build_edition/test_generateur_source.py (usage, source, output and order of the checks)

### Requirement: The generator copies no untracked file and overwrites no folder
The generator SHALL NOT copy any untracked file into the tree, SHALL NOT write a Git folder in the output, and SHALL NOT overwrite an existing folder.

#### Scenario: Untracked ignored file
- **WHEN** an ignored file exists in the workspace and the tree is otherwise clean
- **THEN** the build goes on and the ignored file is absent from the output

Source: tests/build_edition/test_generateur_source.py (usage, source, output and order of the checks)

### Requirement: Every tracked file is classified by the manifest, fail closed
The system SHALL classify every tracked file of the commit with the rules of a tracked edition manifest, the first matching rule winning. The possible actions SHALL be: include; exclude, which requires a reason; or replace by a neutral template taken from the same commit. The generator SHALL NOT guess a classification for an unmatched file.

#### Scenario: First matching rule
- **WHEN** two rules of the manifest match the same tracked file
- **THEN** the action of the first one applies

Source: tests/build_edition/test_generateur_classement.py (first match); tests/build_edition/test_manifeste.py (the real manifest: every tracked file classified)

### Requirement: An unclassified tracked file stops the build
A tracked file matched by no rule SHALL stop the build before any copy, with exit code 6 and the key phrase "unclassified tracked paths:" followed by every unclassified path.

#### Scenario: Unclassified file
- **WHEN** a tracked file matches no rule
- **THEN** the generator exits with code 6, lists that path and writes no tree

#### Scenario: A tracked file without a rule
- **WHEN** the manifest has no rule for a tracked file, such as a file added after the manifest was written
- **THEN** the build stops with code 6 and names it

Source: tests/build_edition/test_generateur_classement.py (unclassified paths)

### Requirement: An invalid manifest stops the build
A manifest that cannot be parsed, has an unknown action, an exclude rule without a reason, a template rule whose template is absent, or a rule that matches no tracked path SHALL stop the build with exit code 5 and the key phrase "manifest invalid:".

#### Scenario: Exclude without reason
- **WHEN** an exclude rule has no reason
- **THEN** the generator exits with code 5

#### Scenario: Stale rule
- **WHEN** a rule matches no tracked path, such as a rule left for the removed work-queue document
- **THEN** the generator exits with code 5 and names the rule

Source: tests/build_edition/test_generateur_classement.py (manifest invalid); tests/build_edition/test_manifeste.py (no stale rule)

### Requirement: The manifest excludes the edition tooling and holds no work-queue rule
The manifest, its templates, the generator and its test suite SHALL be excluded from the edition. The manifest SHALL hold no rule for the former work-queue document, its archive or its template, which are no longer tracked.

#### Scenario: Generator files excluded
- **WHEN** a tree is built
- **THEN** neither the manifest, its templates, the generator nor its test suite is in the output

#### Scenario: Known out-of-edition files
- **WHEN** the manifest excludes the plan of the English version, the library-gaps document, the round-table outputs, the batch-7 correspondence output, the documentation archives and the archived OpenSpec changes
- **THEN** none of them is in the output

Source: tests/build_edition/test_manifeste.py (generator files excluded, no work-queue rule, private documents and archived changes excluded); the batch-7 correspondence output and the documentation archives are not asserted by name

### Requirement: Whole files only, never rewritten
The system SHALL copy an included file byte for byte, keeping its executable bit. It SHALL write nothing for an excluded file. For a templated file, it SHALL write the bytes of the template at the path of the replaced file. The generator SHALL NOT edit, cut, concatenate or substitute text inside any file, with one exception: removing the marked blocks declared by the manifest field `strip_blocks` (design D1).

#### Scenario: Included file
- **WHEN** a tracked script is included
- **THEN** its bytes and executable bit in the output equal those of the commit

#### Scenario: Templated file
- **WHEN** the author's book catalogue is classified as a template
- **THEN** the output file at the catalogue path equals the neutral template, byte for byte

#### Scenario: Declared marked block removed
- **WHEN** an included file whose rule declares `strip_blocks` holds a block framed by the markers of that name
- **THEN** the output file equals the committed file without the block and its markers, and with no other change

Source: tests/build_edition/test_generateur_classement.py (TestWholeFiles); the catalogue's template rule: tests/build_edition/test_manifeste.py (test_fichiers_remplaces_par_un_gabarit); the exception: tests/build_edition/test_blocs_identite.py

### Requirement: English CHANGELOG starting at the edition
The system SHALL give the edition a CHANGELOG written in English that starts at the edition, taken whole from a tracked source file through a template rule, and whose text says that later versions are described in the releases of the public repository (design D6). The system SHALL NOT ship the French history of the private CHANGELOG, in whole or in part.

#### Scenario: CHANGELOG source missing
- **WHEN** the template source of the edition CHANGELOG does not exist in the commit
- **THEN** the generator exits with code 5

#### Scenario: French history absent
- **WHEN** a tree is built
- **THEN** its CHANGELOG equals the English template and differs from the private CHANGELOG

#### Scenario: Pointer to the releases
- **WHEN** the edition CHANGELOG template is read
- **THEN** it says that later versions are described in the releases of the public repository

Source: tests/build_edition/test_gabarits.py (Changelog); tests/build_edition/test_generateur_classement.py (test_changelog_template_missing_gives_code_5, test_template_replaces_whole_file)

### Requirement: Publication check on the generated tree
The system SHALL run the publication check on the staging tree as the last step of the build. The check has six parts, each stated in a requirement of its own: the personal-identifier part, the sensitive-name part, the book-text check, the library-file-name check, the product-version check and the listing check. The system SHALL NOT tolerate any file, and SHALL NOT name the output folder without suffix unless every check passed.

#### Scenario: Clean tree
- **WHEN** no identifier, sensitive name, book text, product version or listed local file occurs in the tree or in the generated sanctums
- **THEN** the generator exits with code 0, the tree is at the output path and the last line says "publishable tree written to"

Source: tests/build_edition/test_generateur_publication.py; tests/build_edition/test_generateur_livres_versions.py; tests/build_edition/test_generateur_listes.py

### Requirement: Any occurrence makes the tree not publishable
On any occurrence found by the publication check, the system SHALL:
- exit with code 7;
- print one line per occurrence, giving the path relative to the tree and the line number with the key phrase "personal identifier in", "sensitive name in", "book text in", "library file name in", "product version in" or "local file in" (for the listing check, the path and line of the listing), then the "not publishable:" summary;
- rename the tree to the not-publishable sibling name.

#### Scenario: Occurrence found
- **WHEN** any part of the publication check finds an occurrence
- **THEN** the generator exits with code 7, prints the path and line with the part's key phrase and the "not publishable:" summary, and the tree is kept under the not-publishable name

Source: tests/build_edition/test_generateur_publication.py; tests/build_edition/test_generateur_livres_versions.py; tests/build_edition/test_generateur_listes.py

### Requirement: A publication check that cannot run deletes the staging tree
When the sensitive-names list is absent or empty, the converted library text is absent or empty, the product-version list is absent, empty or holds a pattern that does not compile, a listing of the table present in the tree cannot be read or has no path column, or the scanner fails, the system SHALL:
- exit with code 8 and the key phrase "publication check could not run:" followed by the cause;
- delete the staging tree.

#### Scenario: Sensitive-names list absent
- **WHEN** the sensitive-names list is absent or holds only comments
- **THEN** the generator exits with code 8 and no tree remains

#### Scenario: Library text unavailable
- **WHEN** the converted library text folders are absent or hold no text
- **THEN** the generator exits with code 8, prints "publication check could not run: library text unavailable" and no tree remains

Source: tests/build_edition/test_generateur_publication.py (code 8 of the list and of the scanner), test_generateur_livres_versions.py, test_generateur_listes.py

### Requirement: The publication check prints nothing it matched
The system SHALL NOT print a matched value, the text of a line, a shared word sequence, a book or article name, a pattern, a listed path or a fingerprint.

#### Scenario: Output of a finding
- **WHEN** any part of the publication check reports an occurrence
- **THEN** the output holds no matched value, line text, shared word sequence, book or article name, pattern, listed path or fingerprint

Source: tests/build_edition/test_generateur_publication.py; tests/build_edition/test_generateur_livres_versions.py; tests/build_edition/test_generateur_listes.py

### Requirement: Personal-identifier part of the publication check
The personal-identifier part SHALL run the personal-identifier scanner in tree mode, with the identifiers of the private workspace (the local identifiers file included), no tolerated file, and sanctums instantiated from the tree's own skills.

Source: tests/build_edition/test_generateur_publication.py (identifier part)

#### Scenario: Identifier in a file
- **WHEN** an included file contains an identifier of the session in capitals
- **THEN** the generator exits with code 7, prints the file and the line number, contains no identifier in its output, and the tree is kept under the not-publishable name

#### Scenario: Extra string from the local identifiers file
- **WHEN** the local identifiers file lists a string, such as an employer name, that appears in an included test file
- **THEN** the generator exits with code 7 and names that file and line

#### Scenario: Sanctum template writes a personal path
- **WHEN** a posture skill of the tree generates a sanctum that contains the private root path
- **THEN** the occurrence is reported under the sanctum key and the exit code is 7

#### Scenario: Former names still present
- **WHEN** the build runs before the change that removes the former names is merged, so that included files still carry a former name holding an identifier
- **THEN** the generator exits with code 7 and lists those files and lines

### Requirement: Sensitive-name part of the publication check
The sensitive-name part SHALL apply the sensitive-name matching rules of the pre-commit hook to every non-binary file of the tree whatever its size.

Source: tests/build_edition/test_generateur_publication.py (sensitive-name part)

#### Scenario: Sensitive name in a large file
- **WHEN** a file larger than the hook's size limit contains a listed name
- **THEN** it is reported and the exit code is 7

### Requirement: Book-text part of the publication check
In the book-text check, a line of a non-binary file of the tree SHALL be a finding when a sequence of consecutive words starting on it, of the configured minimum length, also occurs in the converted text of a library book or of a third party's watch article, words compared lowercased and without punctuation.

Source: tests/build_edition/test_generateur_livres_versions.py (book-text part)

#### Scenario: Passage of a book in a document
- **WHEN** an included document holds a sequence of words of the minimum length taken from a fixture book text, with different case and punctuation
- **THEN** the generator exits with code 7, prints "book text in" with the path and line, and the output holds neither the words nor the book name

#### Scenario: Short common phrase
- **WHEN** an included file shares with a fixture book only a sequence shorter than the minimum length
- **THEN** no book-text finding is reported

### Requirement: What the book-text part leaves out
In the book-text check, a sequence holding no letter (only numbers and punctuation) SHALL never count, and the own-articles folder and the files the watch produces (names starting with "_") SHALL NOT be compared. The system SHALL NOT copy or write the converted library text.

Source: tests/build_edition/test_generateur_livres_versions.py (book-text part)

#### Scenario: Sequence without a letter
- **WHEN** an included file shares with a fixture book only a sequence of the minimum length made of numbers and punctuation
- **THEN** no book-text finding is reported

#### Scenario: Own articles and watch files
- **WHEN** a sequence of an included file occurs only in the own-articles folder or in a file the watch produces
- **THEN** no book-text finding is reported

### Requirement: Library-file-name part of the publication check
In the library-file-name check, a line of a non-binary file of the tree SHALL be a finding when it holds a file name of the private mapping table (keys of MAPPING, SOURCES and EXCLUSIONS, values of SOURCES; the table is read as text, never run), case and accents ignored.

Source: tests/build_edition/test_generateur_livres_versions.py (library-file-name part)

#### Scenario: Library file name in a file
- **WHEN** an included file holds a file name taken from the private mapping table
- **THEN** the generator exits with code 7, prints "library file name in" with the path and line, and the output holds no such name

#### Scenario: Mapping table unusable
- **WHEN** the mapping table named for the check is missing, is not readable as Python source, or holds no file name
- **THEN** the generator exits with code 8, prints "publication check could not run: mapping table unavailable" and no tree remains

### Requirement: Product-version part of the publication check
In the product-version check, a line of a non-binary file of the tree SHALL be a finding when it matches a pattern of the local, untracked product-version list.

Source: tests/build_edition/test_generateur_livres_versions.py (product-version part)

#### Scenario: Product version in a file
- **WHEN** an included file holds a string matched by a pattern of the product-version list
- **THEN** the generator exits with code 7, prints "product version in" with the path and line, and the output holds neither the string nor the pattern

#### Scenario: Product-version list unusable
- **WHEN** the product-version list is absent, holds only comments, or holds a pattern that does not compile
- **THEN** the generator exits with code 8, the cause says absent, empty or invalid, an invalid pattern is named by its line number only, and no tree remains

### Requirement: Listing part of the publication check
In the listing check, for each file listing of the generator's fixed table present in the tree, an entry SHALL be a finding when its path, joined to the listing's base folder, is not a regular file or a symbolic link of the tree, or is absolute, or leaves the base folder; a listing of the table absent from the tree SHALL give no finding (design D3, D5, decided 2026-10-15).

Source: tests/build_edition/test_generateur_listes.py (change edition-local-files, tasks 4.2 and 6.1)

#### Scenario: Listing names an ignored file
- **WHEN** a listing of the table in a fixture tree has an entry for a file that Git ignores and that is therefore absent from the tree
- **THEN** the generator exits with code 7, prints "local file in" with the listing's path and the entry's line, prints neither the listed path nor the fingerprint, and the tree is kept under the not-publishable name

#### Scenario: Listing names an excluded file
- **WHEN** a listing of the table has an entry for a tracked file that the manifest excludes
- **THEN** the generator exits with code 7 and prints "local file in" with the listing's path and the entry's line

#### Scenario: Entry leaving the base folder
- **WHEN** an entry of a listing holds an absolute path or a path that leaves the listing's base folder
- **THEN** it is reported as "local file in" and the exit code is 7

#### Scenario: Coherent listing
- **WHEN** every entry of a listing of the table names a file of the tree
- **THEN** no listing finding is reported

#### Scenario: Listing excluded from the edition
- **WHEN** the manifest excludes a listing of the table
- **THEN** the listing check reports nothing and prints nothing about it

### Requirement: Limits of the listing part
A local file name cited in free text is not seen by the listing check (accepted residual risk, design "Risks"). A listing of the table that is a symbolic link or not a regular file SHALL be unreadable. For an unreadable listing, the cause printed after "publication check could not run:" SHALL be "file listing unreadable" and the listing's path in the tree (design D6).

Source: tests/build_edition/test_generateur_listes.py (change edition-local-files, tasks 4.2 and 6.1)

#### Scenario: Listing unreadable
- **WHEN** a listing of the table in the tree is not valid UTF-8 CSV (a byte order mark is accepted), has no path column, has a row whose column count differs from the header, or is a symbolic link or not a regular file
- **THEN** the generator exits with code 8, prints "publication check could not run: file listing unreadable" with the listing's path, and no tree remains

#### Scenario: Malformed CSV or symbolic link listing
- **WHEN** a listing of the table has a row longer or shorter than its header, an orphan quote, or is a symbolic link or a folder
- **THEN** the generator exits with code 8 with the same unreadable message, and no tree remains

### Requirement: The listing part reads only the staging tree
The system SHALL NOT read a file outside the staging tree for the listing check.

Source: tests/build_edition/test_generateur_listes.py (change edition-local-files, tasks 4.2 and 6.1)

#### Scenario: Entry for a file of the workspace
- **WHEN** a listing entry names a file that exists in the private workspace but not in the staging tree
- **THEN** the entry is a finding and no file outside the staging tree is read

### Requirement: The BMAD skills listing is left out of the listing table
The table of the listing check SHALL deliberately leave out the BMAD skills listing (`_bmad/_config/skill-manifest.csv`), with its written reason and accepted risk (design D5, decided 2026-10-16).

Source: tests/build_edition/test_generateur_listes.py (change edition-local-files, tasks 4.2 and 6.1)

#### Scenario: Frozen exclusion of the skills listing
- **WHEN** the table of listings is read by its test
- **THEN** `_bmad/_config/skill-manifest.csv` is not in it and a written reason and risk accompany the exclusion

### Requirement: Optional test run in the generated tree
The system SHALL, with the test-run option, run the full test runner on a copy of the publishable tree, placed in a temporary folder outside the output with a throwaway repository and one commit. It SHALL run the runner without the variable reserved to git commit and without any bypass variable, print the runner's total line, and delete the temporary folder. The system SHALL NOT run a filtered or targeted run instead of the full one.

#### Scenario: Green run
- **WHEN** the test-run option is given and every suite passes in the copy
- **THEN** the exit code is 0 and the output holds the runner's total line

Source: tests/build_edition/test_generateur_validation.py (fake runner through the environment)

### Requirement: A red test run makes the tree not publishable
On a red run of the test-run option, the system SHALL exit with code 1 and the key phrase "tests red in the generated tree", and rename the tree to the not-publishable name.

#### Scenario: Manifest inconsistent with the runner
- **WHEN** a shell suite listed in the runner is excluded by the manifest
- **THEN** the run is red, the exit code is 1 and the tree carries the not-publishable name

Source: tests/build_edition/test_generateur_validation.py (fake runner through the environment); the case of a suite excluded by the manifest is covered only through a red fake runner

### Requirement: Without the test-run option the commands are printed
Without the test-run option, the system SHALL print the commands that the user runs after creating their repository.

#### Scenario: Without the option
- **WHEN** the option is not given
- **THEN** no test runs and the output lists the commands to run

Source: tests/build_edition/test_generateur_validation.py (fake runner through the environment)

### Requirement: The generator publishes nothing and runs nothing paid or private
The system SHALL NOT, while building the edition:
- create a remote repository, push, publish, or initialise a repository in the output folder;
- run the posture evaluation set or the automatic evaluation script;
- run the real Jira tools, the database scripts, or the import and compare tools;
- connect to the database or make any network call.

The last line of a successful build SHALL say that no repository was created and nothing was pushed.

#### Scenario: Forbidden commands
- **WHEN** the generator's text is scanned outside comments
- **THEN** it contains no push, no remote creation, no evaluation-set launch, no Jira or database tool launch

#### Scenario: Success message
- **WHEN** a build succeeds
- **THEN** the output says that nothing was pushed and no repository was created

Source: tests/build_edition/test_generateur_interdits.py; success line: tests/build_edition/test_generateur_classement.py (test_success_leaves_only_the_output)

### Requirement: The edition ships the install script and its suite
The system SHALL classify the install script's bootstrap and orchestrator with explicit include rules, placed before the broad rule of the tools folder, so that their presence in the edition is a stated intent and does not depend on the broad rule. The bootstrap SHALL keep its executable bit in the tree.

#### Scenario: Script in the tree
- **WHEN** a tree is built
- **THEN** it holds the bootstrap with its executable bit, the orchestrator and the install-script suite, byte for byte

#### Scenario: Explicit rule removed
- **WHEN** the explicit include rule of the orchestrator is removed from the manifest
- **THEN** the edition-manifest test fails and names the install script

Source: tests/build_edition/test_manifeste.py (test_script_d_installation_a_ses_regles_explicites, test_le_test_nomme_le_script_d_installation_quand_les_regles_manquent); the bytes and executable bit through the generic copy tests of tests/build_edition/test_generateur_classement.py

### Requirement: The install-script suite is included and reads only edition files
The install-script test suite SHALL be included through the tests rule. The install-script suite SHALL read no file that the manifest excludes or replaces, so that the test run in the generated tree stays green.

#### Scenario: Suite in the generated tree
- **WHEN** the full test runner runs in the generated tree
- **THEN** the install-script suite is present and passes without reading an excluded or replaced file

Source: tests/build_edition/test_manifeste.py; that the install-script suite reads no excluded file is checked only by the test run in the generated tree

### Requirement: The edition ships the GitHub queue tools without a queue template
The system SHALL include in the edition the queue reader, the GitHub write tool, their test suites and the `/next`, `/start` and `/close` commands, and SHALL NOT ship a template of a work-queue document. The edition's installation guide SHALL state that the queue needs `gh` with the Project scope, a Project whose Status field holds the four options, and the local sensitive-names list, without which the write tool refuses every write.

#### Scenario: Tools in the tree
- **WHEN** a tree is built
- **THEN** it holds the reader, the write tool, their suites and the three commands, byte for byte, and no work-queue template

#### Scenario: Rule removed
- **WHEN** the include rule of the write tool is removed from the manifest
- **THEN** the edition-manifest test fails and names the write tool

Source: tests/build_edition/test_manifeste.py (test_l_edition_livre_la_file_github_sans_gabarit_de_file); the statement of the installation guide is untested

### Requirement: Release notes are not built by the generator
The system SHALL keep the edition generator free of release notes: it SHALL NOT call `gh`, read issues or milestones, or write a notes file; the notes come from the queue reader (design D5). The manifest SHALL hold no rule for the removed evolutions document.

#### Scenario: No gh in the generator
- **WHEN** the generator's text is scanned outside comments
- **THEN** it holds no launch of `gh` and no read of issues or milestones

#### Scenario: Stale evolutions rule
- **WHEN** the evolutions document is removed and its manifest rule is left
- **THEN** the generator exits with code 5 and names the rule

Source: tests/build_edition/test_generateur_interdits.py (test_scan_catches_a_gh_launch and the forbidden-commands scan); stale rules: tests/build_edition/test_generateur_classement.py (test_stale_rule_is_named) and tests/build_edition/test_manifeste.py (test_aucune_regle_perimee)

### Requirement: The edition ships no listing entry of a local file
The system SHALL exclude the BMAD files listing from the edition with its reason (design D1, decided 2026-10-15), so that the edition holds no entry naming a file ignored by Git, absent from the commit, or replaced by a template (D2). The system SHALL NOT ship the private listing whole, SHALL NOT edit lines inside it, and SHALL NOT open or fingerprint an ignored local file.

#### Scenario: Personal BMAD answers file
- **WHEN** the private listing has an entry for the personal BMAD answers file, which Git ignores
- **THEN** no file of the built tree holds that entry

#### Scenario: Compiled files
- **WHEN** the private listing has entries for compiled files under ignored cache folders
- **THEN** no file of the built tree holds those entries

#### Scenario: Manifest test
- **WHEN** the edition-manifest test reads the real manifest
- **THEN** it fails if the BMAD files listing is not excluded with a reason before the broad include rule of its folder

Source: tests/build_edition/test_manifeste.py (manifest rule); tests/build_edition/test_generateur_listes.py (the ignored file is created on disk with an identifiable fictitious content, and appears neither in the built tree nor in any output)

### Requirement: Converted-text folders of the book-text check
The system SHALL take the converted-text folders from the content folder (library and watch) unless a configured folder list replaces them. Only the watch folder MAY be absent: the system SHALL then print "publication check: watch texts folder absent, article comparison not done" once and go on. The system SHALL NOT skip an absent library folder, a list without a library folder, or library folders without text: it SHALL exit with code 8 "library text unavailable".

#### Scenario: Watch folder absent
- **WHEN** the watch texts folder is absent and the library folder holds text
- **THEN** the output holds "watch texts folder absent, article comparison not done" once, without a path, and the check goes on

#### Scenario: Library folder absent, watch present
- **WHEN** the library texts folder is absent and the watch folder holds text
- **THEN** the generator exits with code 8, prints "publication check could not run: library text unavailable" and no tree remains

#### Scenario: No library folder in the list
- **WHEN** the configured folder list holds only a watch folder
- **THEN** the generator exits with code 8 with the same cause

#### Scenario: Library folders without text
- **WHEN** the library folders hold no compared text and the watch folder holds text
- **THEN** the generator exits with code 8 with the same cause

#### Scenario: Default folders
- **WHEN** no folder list is configured
- **THEN** the folders are the library and watch folders of the content folder, also from a worktree

### Requirement: Mapping table of the built commit
The system SHALL read the default private mapping table from the Git objects of the built commit, never from the working copy; a configured table path SHALL keep priority. When the table is absent from that commit, is not a regular file there, cannot be parsed as Python source or holds no name, the system SHALL exit with code 8 "mapping table unavailable" (design D3) and SHALL NOT skip the library-file-name part.

#### Scenario: Older commit with another table
- **WHEN** the build runs with a commit option on a revision whose table differs from the current one
- **THEN** the names of that revision's table are findings and names found only in the current table are not

#### Scenario: Table absent at its default place
- **WHEN** no table path is configured and the built commit holds no table
- **THEN** the generator exits with code 8, prints "publication check could not run: mapping table unavailable" and no tree remains

#### Scenario: Configured table keeps priority
- **WHEN** a table path is configured
- **THEN** the names of that file are used, not those of the commit

### Requirement: The edition ships the context mechanism without any context data
The system SHALL include in the edition the context tool, the private-collections module, the `/context` command, their suites and an invented note template (design D12). The manifest test SHALL fail, naming the path, when a tracked path lies under a context subfolder or the former folder `Contexte-Lab`. The system SHALL NOT ship real context, and the test SHALL NOT refuse a file merely because its name holds `contexte`.

#### Scenario: Mechanism in the tree
- **WHEN** a tree is built
- **THEN** it holds the context tool, the module, the command, their suites and the template, byte for byte

#### Scenario: Context folder tracked
- **WHEN** a tracked path holds `contexte/notes/` or `Contexte-Lab/`
- **THEN** the edition-manifest test fails and names the path

#### Scenario: Neutral template kept
- **WHEN** the tree holds the neutral context template `tests/postures/contexte-neutre.md`
- **THEN** the manifest test does not fail on it

### Requirement: The publication check compares the tree with the context notes
The system SHALL, when the context notes folder exists, compare every non-binary file of the tree with the text of every note by the book-text rule, report "context text in" with the path and line, and exit with code 7. When the folder is absent it SHALL print "context notes: none compared" and go on. It SHALL NOT print a note's text, title or file name, nor read the originals.

#### Scenario: Note sentence in a document
- **WHEN** an included document holds a word sequence of the minimum length taken from a fixture note
- **THEN** the generator exits with code 7, prints "context text in" with the path and line, and the output holds neither the words nor the note name

#### Scenario: No context folder
- **WHEN** the context folder does not exist
- **THEN** the output holds "context notes: none compared" and the build goes on to its other checks

### Requirement: The edition ships the overlay mechanism without the real overlay
The system SHALL include in the edition the story quality tool's overlay reading, the overlay schema and the invented example overlay (design D17). The manifest test SHALL fail, naming the path, when a tracked path holds the real overlay's file name. The system SHALL NOT ship the real overlay or any fixture holding organisation content. Untested until implemented.

#### Scenario: Mechanism in the tree
- **WHEN** a tree is built
- **THEN** it holds the overlay schema and the example overlay, byte for byte

#### Scenario: Real overlay name tracked
- **WHEN** a tracked path holds the real overlay's file name
- **THEN** the edition-manifest test fails and names the path

### Requirement: The publication check compares the tree with the organisation overlay
The system SHALL, when the overlay file exists, compare every non-binary file of the tree with the overlay's text by the book-text rule, report "overlay text in" with the path and line, and exit with code 7. When the file is absent it SHALL print "organisation overlay: none compared" and go on. It SHALL NOT print the overlay's text or identifier. Untested until implemented.

#### Scenario: Overlay sentence in a document
- **WHEN** an included document holds a word sequence of the minimum length taken from a fixture overlay
- **THEN** the generator exits with code 7, prints "overlay text in" with the path and line, and the output does not hold the words

#### Scenario: No overlay
- **WHEN** the overlay file does not exist
- **THEN** the output holds "organisation overlay: none compared" and the build goes on to its other checks

### Requirement: Marked blocks declared in the manifest are removed
The system SHALL accept an optional `strip_blocks` field holding a block name on an include rule only, to keep what awaits a validation (the visual identity, pending the legal check of the names) apart from what is publishable. It SHALL remove from that file every block framed by the markers of that name, markers included, and one blank line left doubled (design D2). It SHALL NOT rewrite, reorder or substitute any text.

#### Scenario: Two blocks removed
- **WHEN** an included file declared with a block name holds two blocks of that name, each followed by a blank line
- **THEN** the output file holds neither block nor marker, and no doubled or leading blank line

#### Scenario: Other block name kept
- **WHEN** the file holds a block framed by markers of another name
- **THEN** that block and its markers are written unchanged

#### Scenario: File without a marker
- **WHEN** the file holds no marker of the declared name
- **THEN** the output file equals the committed file, byte for byte

Source: tests/build_edition/test_blocs_identite.py (TestRetrait, test_l_edition_ne_contient_ni_balise_ni_bloc_ni_chemin_de_marque)

### Requirement: A malformed marker stops the build
For the declared block name, a marker not alone on its line, a closing marker without an opening one, an opening marker inside a block or an opening marker never closed SHALL stop the build with exit code 5 and the messages of design D3, naming the file and, except for a block never closed, the line. The system SHALL NOT leave the output folder or its staging folder.

#### Scenario: Opening marker never closed
- **WHEN** the declared file holds an opening marker with no closing marker
- **THEN** the generator exits with code 5, names the file with "never closed", and neither the output nor its staging folder exists

#### Scenario: Closing marker alone
- **WHEN** the declared file holds a closing marker with no opening marker before it
- **THEN** the build stops with "closing marker without an opening one"

#### Scenario: Nested or inline marker
- **WHEN** an opening marker appears inside a block, or a marker stands inside a line of text
- **THEN** the build stops with exit code 5

Source: tests/build_edition/test_blocs_identite.py (test_balise_ouvrante_sans_fermante, test_balise_fermante_seule, test_balise_ouvrante_imbriquee, test_balise_au_milieu_d_une_ligne, test_balise_non_fermee_arrete_la_construction)

### Requirement: An invalid strip_blocks field makes the manifest invalid
The system SHALL treat a `strip_blocks` field on a rule whose action is not include, or whose value is not a lower-case block name (design D1), as an invalid manifest, with exit code 5 and the key phrase "manifest invalid:". It SHALL NOT strip blocks from an excluded or templated file.

#### Scenario: Field on an exclude rule
- **WHEN** an exclude rule with a reason also declares `strip_blocks`
- **THEN** the generator exits with code 5

#### Scenario: Invalid block name
- **WHEN** an include rule declares `strip_blocks` with a name holding capitals or a space
- **THEN** the generator exits with code 5

Source: tests/build_edition/test_blocs_identite.py (test_champ_inconnu_ou_mal_place_refuse)

### Requirement: The real manifest strips the README identity block
The edition manifest SHALL declare the identity block on the README include rule and SHALL exclude the brand assets folder with its reason, so that the edition holds no identity marker, no brand asset path and no picture element of the identity.

#### Scenario: README of the edition
- **WHEN** the real README is passed through the removal of the identity block
- **THEN** it holds no identity marker, no brand asset path and no picture element

#### Scenario: Brand folder excluded
- **WHEN** the edition-manifest test reads the real manifest
- **THEN** the README rule declares the identity block and the brand assets folder is excluded

Source: tests/build_edition/test_blocs_identite.py (test_manifeste_reel)
