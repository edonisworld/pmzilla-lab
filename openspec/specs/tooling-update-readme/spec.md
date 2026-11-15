# tooling-update-readme Specification

## Purpose

Describes the `/update-readme` command: an instruction that aligns the README with the repository as it is today, checks the installation guide, and commits the two documentation files. Reverse-engineered from the command file; no test asserts its behaviour beyond the wording checks listed in the sources.

## Requirements

### Requirement: Language of the exchange and of the files
The system SHALL serve the user in the language of the request (French by default), with the fixed formulas of the reply written in that language, and SHALL write the README and the installation guide in the language of those files, with business terms untranslated. Untested until implemented.

#### Scenario: French request
- WHEN the user asks in French for the update
- THEN the reply is in French and the text added to the README stays in the language of the README

Source: .claude/commands/update-readme.md (Language paragraph); tests/pmzilla_lab_library/test_coherence_noms.py (wording of the command file)

### Requirement: Scope of the two files
The system SHALL align the README with the repository and SHALL check the installation guide only when a command, script, option, path, file name, setting, hook, scheduled task, book procedure or book count changed. It SHALL keep the README's installation and evolution-ideas sections to a short paragraph and a link. Untested until implemented.

#### Scenario: Installation steps copied into the README
- WHEN a step or an idea has been copied into the README
- THEN the system removes it from the README and reports it

Source: .claude/commands/update-readme.md (two files, two regimes; step 2)

### Requirement: Finding what changed
The system SHALL start from the last commit that modified the README or the installation guide, list the changes since that commit including uncommitted ones, and read the modified files that matter for the documentation. It SHALL obtain the commands and options of each script from its help and SHALL NOT invent any. Untested until implemented.

#### Scenario: Script without help
- WHEN a script has no help output
- THEN the system reads its header instead of guessing options

Source: .claude/commands/update-readme.md (step 1)

### Requirement: Gaps listed before writing
The system SHALL list the gaps between the documentation and the repository before writing: commands, rules summarized from `CLAUDE.md`, presentation of every slash command, layout trees, troubleshooting lines and the two links to installation and evolution ideas. For the installation guide it SHALL check cited paths, commands, options and the checking section, and SHALL run no installation command. Untested until implemented.

#### Scenario: Cited command no longer exists
- WHEN the README cites a command absent from the script's help
- THEN the gap is listed and corrected before the commit

Source: .claude/commands/update-readme.md (step 2)

### Requirement: Writing rules
The system SHALL change only what is out of line and keep the structure, tone and direct address. It SHALL use no em dash, name no colleague, include no information internal to a company, and mention neither backup nor the note-taking application. Untested until implemented.

#### Scenario: Out-of-line paragraph
- WHEN one paragraph of a section no longer matches the repository
- THEN only that paragraph is rewritten and the rest of the section is left as it was

Source: .claude/commands/update-readme.md (step 3)

### Requirement: Check before commit and reporting
The system SHALL reread the diff of both files, check that cited commands exist and that internal links and anchors of both files resolve, then display the gaps handled and those left with the reason. When neither file has a gap it SHALL change nothing, commit nothing and say so. Untested until implemented.

#### Scenario: No gap
- WHEN neither the README nor the installation guide is out of line
- THEN no file changes, no commit is made and the reply says there was nothing to do

Source: .claude/commands/update-readme.md (step 4)

### Requirement: Commit of the two documentation files only
The system SHALL commit only the README and the installation guide, without touching what is staged elsewhere, with a message that starts with `README :` and a short summary, SHALL NOT push (the branch finish pushes), and SHALL tell the user about the other uncommitted changes it saw. Untested until implemented.

#### Scenario: Other changes staged
- WHEN other files have uncommitted changes
- THEN the commit names only the two documentation files, nothing is pushed and the reply lists the other changes

Source: .claude/commands/update-readme.md (step 4, last item)
