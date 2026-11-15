# mothra-tooling Specification

## Purpose
Frame the sessions that work on Mothra, the lab's web application: short session instructions in Mothra's folder that point to the recorded decisions, kept out of the public edition and of the posture evaluation set.

## Requirements

### Requirement: Mothra's folder carries short session instructions that point to the decisions
The system SHALL hold a short English `mothra/CLAUDE.md`, written by the author, with the content of design D6 of mothra-session-guards (references, stack, `node -e` rule, invariants 1 to 14 one line each), checked by a static suite with the phrases of design D7. It SHALL NOT copy a version number or the ADR's text, nor name a person, team, project or domain; the session SHALL NOT write it. Untested until implemented (suite `mothra_consignes`).

#### Scenario: Missing reference
- **WHEN** the file does not name `docs/pmzilla/mothra-tranches.md`
- **THEN** the suite fails with `renvoi absent des consignes de Mothra : docs/pmzilla/mothra-tranches.md`

#### Scenario: Stack not named
- **WHEN** the file does not name `Fastify`
- **THEN** the suite fails with `pile absente des consignes de Mothra : Fastify`

#### Scenario: Missing invariant line
- **WHEN** the file holds no line `9.` naming `ADR 0002`
- **THEN** the suite fails with `invariant absent des consignes de Mothra : 9`

#### Scenario: Copied version
- **WHEN** the file holds a dotted version number of three numeric segments
- **THEN** the suite fails with `version recopiée dans les consignes de Mothra : <texte> (la lire dans mothra/.node-version)`

#### Scenario: Too long
- **WHEN** the file holds more than 80 lines
- **THEN** the suite fails with `consignes de Mothra trop longues : <n> lignes (au plus 80)`

#### Scenario: Missing file
- **WHEN** the file does not exist
- **THEN** the suite fails with `consignes de Mothra absentes : mothra/CLAUDE.md`

### Requirement: Mothra's session instructions stay out of the public edition and of the evaluation set
The system SHALL exclude `mothra/CLAUDE.md` from the public edition by a specific manifest rule placed before any folder rule for `mothra/`, and the static suite SHALL fail with `consignes de Mothra évaluées par le jeu d'essai : <entrée> (décision Q11 à revoir)` when an entry of the posture evaluation list matches it. It SHALL NOT add the file to the evaluation list. Untested until implemented (suites `build_edition`, `mothra_consignes`).

#### Scenario: Edition build
- **WHEN** the edition is built with the file tracked
- **THEN** the file is excluded by its specific rule and the build does not stop with code 6

#### Scenario: Evaluation list entry
- **WHEN** a fake evaluation list holds an entry that matches `mothra/CLAUDE.md`
- **THEN** the suite fails and names the entry

#### Scenario: Root entry only
- **WHEN** the real evaluation list holds only the root `CLAUDE.md` entry
- **THEN** the suite passes and a change of `mothra/CLAUDE.md` triggers no posture evaluation check

### Requirement: A PreToolUse hook refuses the npm, npx and node commands that a session never runs
The system SHALL ship `tools/npm_guard.py`, a PreToolUse hook on Bash that resolves each command as npm does (aliases, unique abbreviations, camelCase of npm 11) and refuses with exit code 2 any npm command outside the list a session runs, npx, node in evaluation or reading its program from standard input, and the other package managers. The only exception SHALL be the `npm ci` of the scenario "Admitted npm ci". It SHALL NOT run, write or print the command.

#### Scenario: Admitted npm ci
- **WHEN** the command is `npm ci` in the forms and under the conditions of requirement "The hook admits npm ci only in a worktree's mothra folder under the author's conditions" (design D2 to D6 of npm-ci-session)
- **THEN** the hook admits it as that requirement states, and it is the only exception to the refusal

#### Scenario: Alias and abbreviation
- **WHEN** the command is `npm isntall x`, `npm upd` or `npm cleanInstall`
- **THEN** the hook exits 2 and its message names the resolved command and the word as written

#### Scenario: Permitted command
- **WHEN** the command is `npm test`, `npm run build`, `npm audit` or `node server.js`
- **THEN** the hook exits 0 with no output

#### Scenario: npm ci outside the exception
- **WHEN** the command is `npm ci --offline`, `npm install` or `npm update`
- **THEN** the hook exits 2, whatever folder it runs from

Suite `npm_guard`.

### Requirement: The hook follows paths, launchers and compound commands
The system SHALL apply the same refusal behind absolute paths (Homebrew, the version manager's default and per-shell paths, any case), launchers (`env`, `command`, `time`, `sudo`, `timeout`, `xargs`, `find -exec`, `sh -c`, `eval`, `fnm exec`, `uv run`), `;`, `&&`, `||`, `|`, sub-shells, substitutions and variables. A command name it cannot resolve SHALL be refused. Suite `npm_guard`.

#### Scenario: Launcher and list
- **WHEN** the command is `cd mothra && bash -c 'fnm exec npm i'`
- **THEN** the hook exits 2

#### Scenario: Unresolved name
- **WHEN** the command is `$(which npm) install`
- **THEN** the hook exits 2 and names an unresolved command

### Requirement: A shell file argument is accepted only in a strict form
The system SHALL refuse a shell file argument with a bare expansion (benign variables included), a wildcard, a `..` after expansion, a path to `/dev` or `/proc`, or a last component that may be `stdin`, a number or `-`; an unknown long option or an option holding an expansion; fish, csh and tcsh. It SHALL read options in order and treat word splitting as unknown once `IFS` is named. Suite `npm_guard`.

#### Scenario: Quoted expansion and bare expansion
- **WHEN** the command is `bash "$D/x.sh"` or `bash $1-x.sh`
- **THEN** the hook exits 0 for the first and 2 for the second

### Requirement: The shell analysis is a net, not a replacement for the deny rules
The system SHALL treat the hook as complementing the `settings.json` deny rules, never replacing them, because no shell analyser is complete (`eval`, aliases, functions, encodings). The single exception SHALL be the two forms of `npm ci` admitted by design D2 of npm-ci-session, whose deny rules the author removed: for them the hook is the only barrier and the source. Removing any other deny rule SHALL remain an explicit decision of the author, rule by rule.

#### Scenario: Deny rules kept
- **WHEN** the hook passes a command that a deny rule refuses
- **THEN** the deny rule still blocks it

#### Scenario: Gap between the guard and the deny block
- **WHEN** an `npm ci` command of the deny test's matrix is denied by the declared block but passed by the hook
- **THEN** the suite fails and names the command

Decision R-20261031-53 of the author removed the deny rules of the two admitted `npm ci` forms. Suite `npm_guard`.

### Requirement: The hook refuses in case of doubt
The system SHALL exit 0 with no output only for an input that is not the hook JSON, for a tool other than Bash, for an empty command, for a permitted command, and for `npm ci` admitted with every condition holding. It SHALL exit 2 for a command it cannot read (unclosed quote or parenthesis, nesting beyond its bound), for an unknown or ambiguous npm subcommand, for any exception of its analysis, and for any exception or timeout of the `npm ci` check. Suite `npm_guard`.

#### Scenario: Unclosed quote
- **WHEN** the command is `echo 'abc`
- **THEN** the hook exits 2 and says the command is unreadable

#### Scenario: Deep nesting
- **WHEN** a line `n''pm install` is followed by 1000 nested `$(`
- **THEN** the hook exits 2 without a traceback

#### Scenario: Check that fails
- **WHEN** the `npm ci` check raises an exception or exceeds its time bound
- **THEN** the hook exits 2 with the phrase `vérification impossible` and no traceback

### Requirement: The hook does not replace the registration by the author
The system SHALL NOT edit `.claude/settings.json`: the author registers the hook (`hooks.PreToolUse`, matcher `Bash`, `onFailure` block, timeout 10) in a step file; the 273 deny rules stay, the hook is one more net. `docs/pmzilla/installation.md` gives the entry. Untested until registered.

#### Scenario: Before registration
- **WHEN** the hook is not in `.claude/settings.json`
- **THEN** the suites stay green and the ban holds in words and by the deny rules

### Requirement: The hook admits npm ci only in a worktree's mothra folder under the author's conditions
The system SHALL admit, with exit 0 and no output, `npm ci` run from the `mothra` folder of a linked worktree under the lab's worktrees folder, or `cd <folder> && npm ci` with `<folder>` one literal word resolving to it, when the conditions of R-20261030-11 (a) hold (next requirement). It SHALL NOT admit an option, an alias, a launcher, anything before or after, an expanded folder, the workspace or the run tree. Untested until implemented (suite `npm_guard`).

#### Scenario: Admitted in a clean worktree
- **WHEN** a throwaway repository has a linked worktree under a test worktrees folder, its package files identical to `origin/main`, a clean tree and no finish lock, and the command is `npm ci` from its `mothra` folder or `cd <its mothra folder> && npm ci`
- **THEN** the hook exits 0 with no output

#### Scenario: Form other than npm ci
- **WHEN** the same worktree receives `npm ci --offline`, `npm clean-install`, `npm --prefix mothra ci`, `env npm ci`, `cd x; npm ci`, `npm ci && npm test` or `cd "$D" && npm ci`
- **THEN** the hook exits 2 with the phrase `forme non admise (aucune option, aucun alias, rien avant ni après)`

#### Scenario: Workspace
- **WHEN** the command is `npm ci` from the `mothra` folder of the main worktree, or of a linked worktree outside the worktrees folder
- **THEN** the hook exits 2 with the phrase `pas dans le dossier mothra d'un worktree (espace de travail, dossier d'exécution ou autre dossier)`

#### Scenario: cd with .. refused
- **WHEN** the command is `cd ../<worktree>/mothra && npm ci`, `cd ./mothra && npm ci` or `cd -P mothra && npm ci`, or a relative `cd` while `CDPATH` is set in the hook's environment, even if the folder resolves to a clean worktree's `mothra` folder
- **THEN** the hook exits 2 with the phrase `forme non admise (aucune option, aucun alias, rien avant ni après)`

#### Scenario: Repository outside the lab refused
- **WHEN** the command is `npm ci` from the `mothra` folder of a linked worktree of a repository whose common Git folder is not under the lab's content root taken from the guard's code root, even when that repository has a worktrees folder beside it laid out like the lab's
- **THEN** the hook exits 2 with the `pas dans le dossier mothra d'un worktree` phrase

### Requirement: The npm ci conditions are those of R-20261030-11 (a)
The system SHALL refuse `npm ci` unless every `package.json`, `package-lock.json` and `.npmrc` under `mothra/`, outside `node_modules`, is identical on disk and in `origin/main` (a `.npmrc` absent from `origin/main` counting as a difference), the worktree has no uncommitted modification, and no finish lock exists in the common Git folder. It SHALL NOT fetch `origin/main` and SHALL NOT add any other condition. Untested until implemented (suite `npm_guard`).

#### Scenario: Finish in progress
- **WHEN** the finish lock folder exists in the common Git folder, live or stale
- **THEN** the hook exits 2 with the phrase `fin en cours (verrou de fin présent)`

#### Scenario: Modified lock
- **WHEN** a `package-lock.json` under `mothra/` differs from `origin/main`, committed on the branch
- **THEN** the hook exits 2 with the phrase `package-lock.json différent de origin/main : <chemin>`

#### Scenario: Script added in a package.json
- **WHEN** a `package.json` under `mothra/` gains a script, committed on the branch
- **THEN** the hook exits 2 with the phrase `package.json différent de origin/main : <chemin>`

#### Scenario: .npmrc added
- **WHEN** a `.npmrc` exists under `mothra/`, outside `node_modules`, and is absent from `origin/main`, untracked or ignored
- **THEN** the hook exits 2 with the phrase `.npmrc absent de origin/main ou différent : <chemin>`

#### Scenario: Package file name in capitals
- **WHEN** a `Package.json` or a `.NPMRC` under `mothra/`, outside `node_modules`, differs from `origin/main` or is absent from it
- **THEN** the names are matched after NFC normalisation and casefolding, and the hook exits 2 with the `package.json` or `.npmrc` phrase naming that path

#### Scenario: Uncommitted modification
- **WHEN** any file of the worktree is modified or untracked, ignored files excepted
- **THEN** the hook exits 2 with the phrase `modification non commitée dans le worktree`

#### Scenario: origin/main missing
- **WHEN** the repository has no `origin/main`
- **THEN** the hook exits 2 with the phrase `état Git illisible ou origin/main introuvable`

### Requirement: The npm ci refusal line is fixed and decided before formatting
The system SHALL print, for a refused `npm ci`, the single line of design D7 of npm-ci-session: prefix `garde npm : npm ci refusé : `, the failed conditions' phrases joined by `; ` in D7's order, then the closing sentence of D7. A function SHALL return the failed conditions as a list; the message SHALL only print them. It SHALL NOT print the command, the worktree's absolute path or a file's content. Untested until implemented (suite `npm_guard`).

#### Scenario: Two failed conditions
- **WHEN** a worktree has an uncommitted change to a `package-lock.json` under `mothra/`
- **THEN** the line holds `modification non commitée dans le worktree` then `package-lock.json différent de origin/main : <chemin>`, in this order, and the path is relative to the worktree's top level

#### Scenario: Form refused first
- **WHEN** the command is `npm ci --offline` in a worktree that also has an uncommitted change
- **THEN** the line holds only the `forme non admise` phrase

### Requirement: The npm ci check only reads Git and the worktree
The system SHALL check the conditions in `tools/npm_ci_conditions.py`, standard library only, through Git reads with fixed arguments (design D6) and a walk of `mothra/` that skips `node_modules`, imported by the guard only for a command reduced to `npm ci`. It SHALL NOT fetch, pull, write a file, run npm or node, open a network connection, or read outside the worktree and its common Git folder. Untested until implemented (suite `npm_guard`).

#### Scenario: Source read by the suite
- **WHEN** the suite reads the module's source
- **THEN** it finds no network import, no file opened for writing, no Git subcommand other than the reads of design D6, and no call that runs npm or node

### Requirement: The npm ci exception states what it replaces and when it falls
The system SHALL write, in the module's docstring, the guard's comment and the guide, that the exception replaces the two deny rules of design D8 of npm-ci-session and the author's `npm ci` gestures on new worktrees, and falls with the change that gives a worktree its `node_modules` without a session `npm ci` (design D11). It SHALL NOT be widened to another npm form without a decision of the author. Untested until implemented (review of task 4.1).

#### Scenario: Removal written
- **WHEN** the review reads the module, the guard and the guide
- **THEN** each states what the exception replaces and its removal condition
