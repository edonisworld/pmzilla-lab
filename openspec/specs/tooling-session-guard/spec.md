# tooling-session-guard Specification

## Purpose
Level 1 of the correction of the security audit of Kraken (#629): a PreToolUse guard, `tools/garde_session.py`, declared as a hook next to the pipe guard and the npm guard, decides every Bash call of a session before it runs and refuses the evident bypasses of the deny rules and of the hooks (git global options, other launch forms of `security`, open `gh` subcommands, aliases, guard-setting variables, the frozen envelopes outside their admitted form), with a corpus of known refusals replayed by its suite. It does not close what a script or a program can do once launched: that is level 2, the Bash sandbox (change bash-sandbox-n2, deferred to Hydra). Created by the archive of change session-guard-n1.

## Requirements

### Requirement: The session guard decides every Bash call before it runs
The system SHALL provide a PreToolUse guard on Bash, `tools/garde_session.py`, that decides each simple command with a pure decision function returning a verdict or nothing. It SHALL exit 0 to let a command through and 2 to refuse it, with the single line of design D10 on the error output: `garde de session : refusé : <classe> : <forme>. Voie permise : <voie>.`. It SHALL NOT print the command, nor write on standard output.

#### Scenario: Refused command
- **WHEN** the guard receives a Bash call that one of its rules refuses
- **THEN** it exits 2, writes one line starting with `garde de session : refusé :` that names the class and the permitted path, and does not print the command

#### Scenario: Allowed command
- **WHEN** the guard receives a Bash call that no rule refuses, such as `git status`
- **THEN** it exits 0 and writes nothing

#### Scenario: Chained and nested commands
- **WHEN** a refused form is chained after `&&`, `;` or a pipe, or sits inside a shell `-c` string or a substitution
- **THEN** the guard refuses the whole call

Source: untested until implemented (tests/garde_session, tasks 7.1 and 7.2)

### Requirement: An unreadable input or an internal error refuses
The system SHALL make the session guard refuse, with exit 2, an input it cannot read and any exception raised while it decides, with the key phrase `entrée illisible` or `erreur interne de la garde`. When the analyser cannot split a command, the guard SHALL refuse it if its raw text holds a word one of its rules watches, and SHALL NOT refuse it otherwise (design D1). It SHALL NOT let a command through because of its own failure.

#### Scenario: Unreadable input
- **WHEN** the guard receives an input that is not the PreToolUse JSON
- **THEN** it exits 2 with `entrée illisible`

#### Scenario: Internal error
- **WHEN** a test double makes the decision function raise an exception
- **THEN** the guard exits 2 with `erreur interne de la garde`

#### Scenario: Unparsable text with a watched word
- **WHEN** the analyser cannot split a command whose text holds `git`
- **THEN** the guard refuses it

Source: untested until implemented (tests/garde_session, task 7.2)

### Requirement: Git push forms and unknown subcommands are refused after normalisation
The system SHALL make the session guard drop the global options of git (design D4) before it reads the subcommand. It SHALL refuse `push`, `send-pack` and `http-push` with class A1, whatever global options precede them. It SHALL refuse any subcommand outside the closed read and write lists of design D4, an alias included, with class A2. It SHALL NOT refuse a listed subcommand for its global options alone.

#### Scenario: Global option before push
- **WHEN** a command runs git with `-C`, `-c` or `--git-dir` options and then `push`
- **THEN** the guard refuses it with class A1 and `git push, send-pack ou http-push`

#### Scenario: Alias
- **WHEN** a command runs a git subcommand that is not in the lists of design D4
- **THEN** the guard refuses it with class A2 and `sous-commande git inconnue ou alias`

#### Scenario: Read subcommand with a global option
- **WHEN** a command runs `git -C <worktree> log`
- **THEN** the guard lets it through

Source: untested until implemented (tests/garde_session, task 7.1); first cases from the confirmed reproduction of A-17

### Requirement: git merge and git pull are refused everywhere
The system SHALL make the session guard refuse, with class A1 and `git merge ou git pull`, every `git merge` and `git pull`, in a worktree as in the workspace, whatever their options (design D14). It SHALL NOT refuse `git rebase main` in a worktree, the permitted path.

#### Scenario: Merge in a worktree
- **WHEN** a command run in a worktree runs `git merge main`
- **THEN** the guard refuses it with class A1 and `git merge ou git pull`

#### Scenario: Pull
- **WHEN** a command runs `git pull`
- **THEN** the guard refuses it with class A1

#### Scenario: Rebase on main
- **WHEN** a command runs `git -C <worktree> rebase main`
- **THEN** the guard lets it through

Source: untested until implemented (tests/garde_session, task 7.5); decision R-20261108-01, question 15 (a)

### Requirement: --force and push texts are refused in git commands
The system SHALL make the session guard refuse, with class A6 and `option --force, ou ce texte, dans une commande git`, a git command other than push that holds `--force`, as an option or inside a text; push stays under class A1. It SHALL refuse, with class A1 and `texte push dans une commande git -C`, a git command with `-C` or `--git-dir` whose later words name `push`. It SHALL NOT refuse a commit whose message is read from a file (design D14).

#### Scenario: Forced checkout written in full
- **WHEN** a command runs `git checkout --force <branch>`
- **THEN** the guard refuses it with `option --force, ou ce texte, dans une commande git`

#### Scenario: Push named in a message
- **WHEN** a command runs `git -C <worktree> commit -m` with a message that names push
- **THEN** the guard refuses it with `texte push dans une commande git -C`

#### Scenario: Message from a file
- **WHEN** a command runs `git -C <worktree> commit -F <file>`
- **THEN** the guard lets it through

Source: untested until implemented (tests/garde_session, task 7.5); decision R-20261108-01, question 15 (a)

### Requirement: main is never renamed nor overwritten by git branch
The system SHALL make the session guard refuse, with class A6 and `git branch -M ou -C visant main`, a `git branch` forced write (`-M`, `-C`, or a move or copy with a force option, clusters and abbreviations included) with a name that starts with `main` or `refs/heads/main`, in any order and any case, or an unreadable name, and the same form inside a text of a git command. It SHALL NOT refuse creating or listing branches (design D14).

#### Scenario: Branch renamed onto main
- **WHEN** a command runs `git branch -M <branch> main`
- **THEN** the guard refuses it with `git branch -M ou -C visant main`

#### Scenario: Branch listing
- **WHEN** a command runs `git branch --list`
- **THEN** the guard lets it through

Source: untested until implemented (tests/garde_session, task 7.5); decision R-20261108-01, question 15 (a)

### Requirement: The hooks-path and configuration-variable texts are refused
The system SHALL make the session guard refuse, with class A6 and `texte core.hooksPath ou GIT_CONFIG_ dans une commande`, any command whose words name the hooks-path key, in any case, or the `GIT_CONFIG_` prefix, unless a form already refused under its own key (`-c` key, `git config` writing, git variable) takes it. It SHALL NOT refuse `git config` in reading forms; a search goes through the Grep or Read tool (design D14).

#### Scenario: Text in a search command
- **WHEN** a command passes the hooks-path key as a search pattern to a terminal program
- **THEN** the guard refuses it with `texte core.hooksPath ou GIT_CONFIG_ dans une commande`

#### Scenario: Configuration read
- **WHEN** a command runs `git config --get-all core.hooksPath`
- **THEN** the guard lets it through

#### Scenario: Form refused under its own key
- **WHEN** a command passes the hooks-path key with `-c` to git
- **THEN** the guard refuses it with `réglage git hors liste blanche`, not with the text phrase

Source: untested until implemented (tests/garde_session, task 7.5); decision R-20261108-01, question 15 (a)

### Requirement: Git options that launch a command are refused
The system SHALL make the session guard refuse, with class A6 and `option git qui lance une commande`, `rebase --exec` and `-x`, `grep -O` and `--open-files-in-pager`, `--upload-pack`, `--receive-pack`, `--exec` of the subcommands that accept it, and `--exec-path=` with a folder, abbreviations included. It SHALL NOT refuse the same subcommands without these options (design D14).

#### Scenario: Rebase with a command
- **WHEN** a command runs `git rebase --exec <command> main`
- **THEN** the guard refuses it with `option git qui lance une commande`

#### Scenario: Plain rebase
- **WHEN** a command run in a worktree runs `git rebase main`
- **THEN** the guard lets it through

Source: untested until implemented (tests/garde_session, task 7.5); correction 4 of the Opus review of the guard, accepted with corrections 1 to 11 in R-20261108-04 (not question 15, not fragments 26 or 39)

### Requirement: GIT_EDITOR=true is admitted only before git rebase --continue
The system SHALL make the session guard admit `GIT_EDITOR=true` only for the `git rebase --continue` that follows it: as a prefix, through `env`, inside a shell `-c` string, or exported in the same call just before that command. It SHALL refuse, with `variable qui déplace la configuration de git`, any other value of `GIT_EDITOR`, and `GIT_EDITOR=true` before another command or with no command after it (design D14).

#### Scenario: Rebase continued without an editor
- **WHEN** a command runs `GIT_EDITOR=true git rebase --continue`
- **THEN** the guard lets it through

#### Scenario: Other admitted forms
- **WHEN** a command sets `GIT_EDITOR=true` through `env`, inside a `bash -c` string just before `git rebase --continue`, or by an `export` followed in the same call by `git rebase --continue`
- **THEN** the guard lets it through

#### Scenario: Editor variable before a commit
- **WHEN** a command assigns `GIT_EDITOR=true` before `git commit`, or exports it alone
- **THEN** the guard refuses it with `variable qui déplace la configuration de git`

#### Scenario: Other editor value
- **WHEN** a command assigns another value to `GIT_EDITOR` before `git rebase --continue`
- **THEN** the guard refuses it with class A6

Source: untested until implemented (tests/garde_session, task 7.5); decisions R-20261107-27 point 12 and R-20261108-01 question 16

### Requirement: Options that skip the hooks are refused
The system SHALL make the session guard refuse, with class A6 and `option qui saute les crochets`, `--no-verify` and each of its abbreviations from `--no-v` on, on every git subcommand, and `-n` of `commit`, alone or in a cluster of short options. It SHALL NOT refuse a commit whose short options hold no `n`.

#### Scenario: Cluster
- **WHEN** a command runs `git commit -anm <message>`
- **THEN** the guard refuses it with class A6

#### Scenario: Abbreviation
- **WHEN** a command runs a git subcommand with `--no-veri`
- **THEN** the guard refuses it with class A6

#### Scenario: Ordinary commit
- **WHEN** a command runs `git commit -am <message>`
- **THEN** the guard lets it through

Source: untested until implemented (tests/garde_session, task 7.1)

### Requirement: Git configuration overrides are refused at the call
The system SHALL make the session guard refuse, with class A6, the following:
- a `-c` key outside the allow-list `core.quotepath`, `color.*` and `advice.*`, after lowercasing the key;
- `--config-env`;
- every writing form of `git config`;
- an assignment of `GIT_*`, `HOME` or `XDG_CONFIG_HOME` before any program, through `env`, `export`, `declare` or `typeset`, outside the `GIT_EDITOR` admission.

It SHALL NOT refuse `git config` in reading forms, nor an allow-listed `-c` key.

#### Scenario: Case of the hooks key
- **WHEN** a command runs git with `-c` and the hooks-path key written in mixed case
- **THEN** the guard refuses it with `réglage git hors liste blanche`

#### Scenario: Include path
- **WHEN** a command runs git with `-c include.path=<file>`
- **THEN** the guard refuses it with class A6

#### Scenario: Home moved
- **WHEN** a command assigns `HOME` before git, or exports it earlier in the same call
- **THEN** the guard refuses it with `variable qui déplace la configuration de git`

#### Scenario: Configuration read
- **WHEN** a command runs `git config --get <key>` or `git -c color.ui=never log`
- **THEN** the guard lets it through

Source: untested until implemented (tests/garde_session, task 7.1); first case from the confirmed reproduction of A-23

### Requirement: The effective hooks path is checked before a git write
The system SHALL make the session guard read the effective `core.hooksPath` through git itself, in every scope, before a subcommand of the write list of design D4, and refuse on any value with `core.hooksPath défini`. It SHALL NOT run this check for a subcommand of the read list.

#### Scenario: Persistent hooks path
- **WHEN** the global or local configuration of a throwaway repository sets the hooks path, and a command commits in it
- **THEN** the guard refuses the commit with `core.hooksPath défini`

#### Scenario: Read subcommand
- **WHEN** the hooks path is set and a command runs `git status`
- **THEN** the guard lets it through

Source: untested until implemented (tests/garde_session, task 7.3)

### Requirement: The hook links are checked before a git write
The system SHALL make the session guard check, before a subcommand of the write list, that each of the six hook links of the common git folder aims at its tracked source. When one is missing or aims elsewhere, it SHALL refuse every write subcommand with `liens des crochets non conformes`. It SHALL NOT refuse a read subcommand for a broken link.

#### Scenario: Link removed
- **WHEN** one hook link of a throwaway repository is removed and a command commits in it
- **THEN** the guard refuses the commit with `liens des crochets non conformes`

#### Scenario: Read with a broken link
- **WHEN** one hook link is removed and a command runs `git log`
- **THEN** the guard lets it through

Source: untested until implemented (tests/garde_session, task 7.3)

### Requirement: Git never writes the work tree of the workspace or of the run tree
The system SHALL make the session guard refuse, with class A3, `checkout` with `--` or a path, `restore`, `apply`, `stash pop`, `stash apply` and `reset --hard` whose target work tree, read through the working directory, `-C`, `--git-dir` or `--work-tree`, is the workspace, the run tree or unknown. It SHALL NOT refuse them with class A3 in a worktree, where `reset --hard` falls under the `git reset` requirement (design D4, D13).

#### Scenario: Restore in the workspace
- **WHEN** a command runs `git -C <workspace> restore <path>`
- **THEN** the guard refuses it with `git qui écrit l'arbre de l'espace de travail ou de run`

#### Scenario: Abbreviated hard reset in the workspace
- **WHEN** a command run in the workspace resets with `--h` or `--har`
- **THEN** the guard refuses it with class A3

#### Scenario: Restore in a worktree
- **WHEN** the same restore command targets a worktree
- **THEN** the guard lets it through

Source: untested until implemented (tests/garde_session, task 7.1; abbreviations, task 7.4)

### Requirement: git clean runs only as a dry run
The system SHALL make the session guard refuse `git clean`, with class A6, unless a dry run is in effect, its options read one by one up to `--` or `--end-of-options`, the last of `-n`, `--dry-run` and `--no-dry-run` deciding. An unreadable option, or a bare expansion as the value of `-e` or `--exclude`, SHALL refuse it. The guard SHALL NOT refuse a dry run whose exclusion values are readable or quoted (design D13).

#### Scenario: Clean that deletes
- **WHEN** a command run in a worktree runs `git clean -fdx`
- **THEN** the guard refuses it with class A6 and `git qui efface des fichiers ou des modifications (clean, checkout -f, switch --discard-changes)`

#### Scenario: Dry run cancelled
- **WHEN** a `git clean` command holds `-n` and then `--no-dry-run`, or holds `-n` only after `--end-of-options`
- **THEN** the guard refuses it with class A6

#### Scenario: Bare expansion as an exclusion
- **WHEN** a `git clean -n` command gives `-e` an unquoted variable expansion
- **THEN** the guard refuses it with class A6

#### Scenario: Dry run with a quoted exclusion
- **WHEN** a `git clean -n` command gives `-e` a variable expansion between double quotes
- **THEN** the guard lets it through

Source: untested until implemented (tests/garde_session, task 7.4); decisions R-20261108-04 point 3 (a) and R-20261108-06 point 1 (a)

### Requirement: Forced checkout and switch are refused
The system SHALL make the session guard refuse, with class A6 and the erasing key phrase of design D10, `git checkout -f`, `git switch -f` and `git switch --discard-changes`, abbreviations included, in a worktree as in the workspace. It SHALL NOT refuse a branch change without a forcing option.

#### Scenario: Forced checkout
- **WHEN** a command runs `git checkout -f` or `git switch --discard-changes <branch>`
- **THEN** the guard refuses it with class A6

#### Scenario: Ordinary branch change
- **WHEN** a command runs `git switch <branch>` or `git checkout -b <branch>`
- **THEN** the guard lets it through

Source: untested until implemented (tests/garde_session, task 7.4); decision R-20261108-04 point 3 (a)

### Requirement: git reset never moves HEAD and never runs hard in a worktree
The system SHALL make the session guard refuse, with class A6, a `git reset` that moves HEAD: `--soft`, `--mixed`, `--keep` or `--merge`, abbreviations included, or a revision other than `HEAD`, or an unreadable word, before `--`. In a worktree, it SHALL refuse `--hard` in every form, from `--h` on. It SHALL NOT refuse `git reset` with no argument, with `HEAD` alone, or with `HEAD` or `--` followed by paths (design D13).

#### Scenario: Soft reset
- **WHEN** a command runs `git reset --soft HEAD~1`
- **THEN** the guard refuses it with class A6 and `git reset --soft, --mixed, --keep ou --merge, ou avec un commit (--hard compris)`

#### Scenario: Keep or merge
- **WHEN** a command runs `git reset --keep` or `git reset --merge`
- **THEN** the guard refuses it with class A6

#### Scenario: Reset to a commit without an option
- **WHEN** a command runs `git reset <commit>`
- **THEN** the guard refuses it with class A6

#### Scenario: Hard reset in a worktree
- **WHEN** a command run in a worktree runs `git reset --hard`, `git reset --hard HEAD` or `git reset --h HEAD~1`
- **THEN** the guard refuses it with class A6

#### Scenario: Unstaging a file
- **WHEN** a command runs `git reset HEAD -- <path>` or `git reset -- <path>`
- **THEN** the guard lets it through

Source: untested until implemented (tests/garde_session, task 7.4); decisions R-20261108-04 point 3 (a), R-20261108-05 points 2 (a) and 3 (a), R-20261108-06 point 2 (a)

### Requirement: The reflog is read only
The system SHALL make the session guard refuse, with class A6 and `git reflog expire, delete, drop ou write`, those four `git reflog` subcommands and an unreadable first word. It SHALL NOT refuse `git reflog` alone or with an option or a revision, nor `git reflog show`, `list` or `exists` (design D13).

#### Scenario: Reflog expired
- **WHEN** a command runs `git reflog expire --all` or `git reflog drop`
- **THEN** the guard refuses it with class A6

#### Scenario: Reflog read
- **WHEN** a command runs `git reflog show`
- **THEN** the guard lets it through

Source: untested until implemented (tests/garde_session, task 7.4); decision R-20261108-04 point 3 (a)

### Requirement: git fetch never writes main
The system SHALL make the session guard refuse, with class A6 and `git fetch qui écrit la branche main`, a `git fetch` whose refspec destination is or may be the branch main, with or without `+`, `-u` or `--update-head-ok`. It SHALL NOT refuse a fetch without a refspec toward main (design D13).

#### Scenario: Fetch into main
- **WHEN** a command runs `git fetch -u . +<branch>:main`
- **THEN** the guard refuses it with `git fetch qui écrit la branche main`

#### Scenario: Ordinary fetch
- **WHEN** a command runs `git fetch origin` or fetches into a remote-tracking reference
- **THEN** the guard lets it through

Source: untested until implemented (tests/garde_session, task 7.4)

### Requirement: git --output never writes a protected path nor an unreadable target
The system SHALL make the session guard refuse, with class C and `écriture du shell vers un chemin protégé`, a `--output` option of any git subcommand, abbreviations included, whose value resolves under a path of the fragment 41 list, or whose value it cannot read (R-20261108-04 point 3 (a); R-20261108-06 point 4 (a)). It SHALL NOT refuse a readable `--output` value outside the protected paths, nor options that only start with the same letters, such as the output indicators of `git diff`.

#### Scenario: Output into a hook
- **WHEN** a command run in the workspace writes `git log --output=` toward a file of the hooks folder
- **THEN** the guard refuses it with class C

#### Scenario: Unreadable output value
- **WHEN** a git command gives `--output` a variable or a substitution as its value
- **THEN** the guard refuses it with class C

#### Scenario: Ordinary output file
- **WHEN** a command writes `git diff --output=` toward a file outside the protected paths
- **THEN** the guard lets it through

Source: untested until implemented (tests/garde_session, task 7.4)

### Requirement: Security is refused in every launch form
The system SHALL make the session guard refuse, with class A4 and the form `security`, every launch of `security`, whatever the launcher, the path or the prefix of assignments. It SHALL NOT refuse a command that only names it as a search pattern.

#### Scenario: Another form of security
- **WHEN** a command launches `security` by its absolute path, through `env` or inside a shell `-c` string
- **THEN** the guard refuses it with class A4

Source: untested until implemented (tests/garde_session, task 7.1); first case from the confirmed reproduction of A-18

### Requirement: gh follows a closed list
The system SHALL make the session guard refuse `gh`, with class B and `gh hors liste fermée`, outside `gh issue view`, `gh issue list` and `gh --version`, its options read wherever they sit. It SHALL refuse an assignment of `GH_TOKEN`, `GH_HOST` or `GH_CONFIG_DIR` with `variable de gh`. It SHALL NOT refuse listing or viewing issues.

#### Scenario: gh pull request or alias
- **WHEN** a command runs `gh pr list`, `gh alias set` or `gh workflow run`
- **THEN** the guard refuses it with `gh hors liste fermée`

#### Scenario: Option between issue and its subcommand
- **WHEN** a command places an option between `gh issue` and a writing subcommand
- **THEN** the guard refuses it with class B

#### Scenario: Issue reading
- **WHEN** a command runs `gh issue view <number>` or `gh issue list --state open`
- **THEN** the guard lets it through

Source: untested until implemented (tests/garde_session, task 7.1); first case from the confirmed reproduction of A-19

### Requirement: The GitHub write tool runs only from the workspace copy
The system SHALL make the session guard refuse, with class C3 and `gh_issue.py hors de la copie de l'espace de travail`, a launch of `tools/gh_issue.py` whose script path does not resolve to the workspace copy. It SHALL NOT refuse the workspace copy, whatever the working directory of the call.

#### Scenario: Write tool from a worktree
- **WHEN** a command launches the worktree's copy of `tools/gh_issue.py`
- **THEN** the guard refuses it with class C3

#### Scenario: Workspace copy from a worktree
- **WHEN** a command run in a worktree launches the workspace copy by its absolute path
- **THEN** the guard lets it through

Source: untested until implemented (tests/garde_session, task 7.1); first case from the confirmed reproduction of A-39

### Requirement: Shell writes toward the protected paths are refused
The system SHALL make the session guard refuse, with class C, the redirections `>` and `>>`, `tee`, `cp`, `mv`, `rm`, `ln`, `sed -i`, `touch`, `chmod` and `dd of=` whose target resolves under a path of the fragment 41 list (design D7), read from the same source as that fragment. It SHALL NOT refuse the same programs on a path of a worktree that the list does not cover.

#### Scenario: Redirection into a hook of the workspace
- **WHEN** a command redirects text into a file of the workspace's hooks folder
- **THEN** the guard refuses it with `écriture du shell vers un chemin protégé`

#### Scenario: Settings file of a worktree
- **WHEN** a command copies a file over a worktree's `.claude/settings.json`
- **THEN** the guard refuses it with class C

#### Scenario: Ordinary worktree file
- **WHEN** a command removes a file of a worktree's own folder for tests
- **THEN** the guard lets it through

Source: untested until implemented (tests/garde_session, task 7.1)

### Requirement: The tuning variables of the guards and hooks are refused
The system SHALL make the session guard refuse, with class E and `variable de réglage des gardes`, an assignment, an `export` or an `unset` of a variable of the closed list of design D6. The list holds the variables that tune or disarm the hooks, the guards and the finish lock, those that relocate the lab folders, and five Python variables (design D13). The guard SHALL NOT refuse a command that only names such a variable, nor a Python variable outside the list.

#### Scenario: Variable before a commit
- **WHEN** a command assigns a variable of the list before `git commit`
- **THEN** the guard refuses it with class E

#### Scenario: Python variable that moves loaded code
- **WHEN** a command assigns, exports, sets through `env`, removes through `env -u` or unsets `PYTHONPATH`, `PYTHONHOME`, `PYTHONUSERBASE`, `PYTHONPLATLIBDIR` or `PYTHONWARNINGS`
- **THEN** the guard refuses it with class E and `variable de réglage des gardes`

#### Scenario: Python variable outside the list
- **WHEN** a command sets `PYTHONDONTWRITEBYTECODE` before `python3`, or prints the value of `PYTHONPATH`
- **THEN** the guard lets it through

#### Scenario: Variable named in a search
- **WHEN** a command only names a variable of the list as a search pattern
- **THEN** the guard lets it through

Source: untested until implemented (tests/garde_session, task 7.1; list from task 3.1; Python variables, task 7.4, decisions R-20261108-04 point 2 (a), R-20261108-05 point 1 (a), R-20261108-06 point 3 (a))

### Requirement: Docker never reaches the real database nor destroys its storage
The system SHALL make the session guard refuse, with class G, a container run or created with any mount (named volume, real volume, host path, docker socket), a command aimed at the lab's compose project, read from the workspace's compose file at each call, and the destruction of a volume or of the Colima machine (design D6). It SHALL NOT refuse `docker ps`, `docker logs` or a container without any mount.

#### Scenario: Real volume
- **WHEN** a command runs a container that mounts the volume of the real database
- **THEN** the guard refuses it with class G

#### Scenario: Any named volume
- **WHEN** a command runs a container that mounts a named volume other than the real one
- **THEN** the guard refuses it with class G

#### Scenario: Volume destruction
- **WHEN** a command removes a docker volume or deletes the Colima machine
- **THEN** the guard refuses it with class G

#### Scenario: Container status
- **WHEN** a command runs `docker ps`
- **THEN** the guard lets it through

Source: untested until implemented (tests/garde_session, task 7.1); first case from the confirmed reproduction of A-29; every mount refused: decision R-20261108-01, question 17

### Requirement: The scripts of fragment 07 and the quarantined skill are refused in every launch form
The system SHALL make the session guard refuse, with class A5, the launch of a script of the fragment 07 list. The refusal SHALL apply to every launcher and path form of design D6. It SHALL refuse, with class H, any command that names the quarantined skill or one of its scripts. It SHALL NOT refuse reading those scripts with the Read tool, nor running their test suites through the test runner.

#### Scenario: Launch through source
- **WHEN** a command sources a script of the fragment 07 list or runs it through `env`
- **THEN** the guard refuses it with `script réservé à l'auteur`

#### Scenario: Quarantined skill
- **WHEN** a command names the quarantined skill's folder or one of its scripts
- **THEN** the guard refuses it with `skill en quarantaine`

Source: untested until implemented (tests/garde_session, task 7.1)

### Requirement: The guards run from the workspace copy under an isolated interpreter
The system SHALL launch the pipe guard, the npm guard and the session guard by the absolute path of the workspace copy, written from `$HOME`, with `python3 -I`. Each guard SHALL load its sibling modules from its own resolved folder. It SHALL NOT use the working directory or the project-folder variable to find its code. The npm guard SHALL expose a decision callback in `lancer`. Without a callback, it SHALL behave as before, every existing npm guard test unchanged.

#### Scenario: Launch from another directory
- **WHEN** each guard is launched by its absolute path with `python3 -I` from a working directory that holds a planted module of the same name as one of its siblings
- **THEN** the guard loads its sibling from its own folder and decides as usual

#### Scenario: npm guard without a callback
- **WHEN** the npm guard suite runs after the callback is added
- **THEN** every existing test passes unchanged

Source: untested until implemented (tests/garde_session and tests/npm_guard, task 8.2)

### Requirement: The PreToolUse entry admits two states around the pose
The system SHALL hold one PreToolUse entry with matcher `Bash` that, after the author's P2 step file, runs in order the pipe guard, the npm guard and the session guard, launched as the previous requirement states, the session guard with `onFailure: block` and a timeout. The strict hook tests SHALL admit the current state and this one until the P2 train merges, then this one only. The session SHALL NOT edit the settings files.

#### Scenario: Before the pose
- **WHEN** the hooks section holds the two current guards launched through the project-folder variable
- **THEN** the strict hook tests pass

#### Scenario: After the pose
- **WHEN** the hooks section holds the three guards launched by the workspace path with `python3 -I`
- **THEN** the strict hook tests pass

#### Scenario: Mixed form
- **WHEN** the session guard is posed but one guard is still launched through the project-folder variable
- **THEN** the strict hook tests fail and name that guard

Source: untested until implemented (tests/settings_deny, task 8.3)

### Requirement: The duplicate fragments are checked against the guard
The system SHALL keep deny fragments 12, 26 and 39 and the `security` lines of fragment 02 posed, the session guard being their source. A matrix test SHALL fail, naming the form, when a form they deny is let through by the guard, or when the guard's fragment 07 list differs from fragment 07. They SHALL be removed only at the level-1 weeding. That weeding SHALL NOT remove the other lines of fragment 02 (design D6, D8).

#### Scenario: Gap between a fragment and the guard
- **WHEN** a form denied by fragment 12 is let through by the guard
- **THEN** the matrix test fails and names the form

#### Scenario: Fragment 07 list out of step
- **WHEN** fragment 07 refuses a script that the guard's list does not hold
- **THEN** the matrix test fails and names the script

#### Scenario: Weeding of fragment 02
- **WHEN** the level-1 weeding removes the duplicate fragments
- **THEN** fragment 02 loses its `security` lines only, and its lines on the Jira scripts reserved to the author and on the green-check bypass variable stay deny rules

#### Scenario: Matrix rows of fragment 02
- **WHEN** the matrix reads fragment 02
- **THEN** it compares only its `security` forms with the guard

Source: untested until implemented (tests/garde_session, task 9.3); weeding of fragment 02: decision R-20261108-04 point 1 (a), carried out at task 16.1 after the sandbox pose and two weeks of green probe

### Requirement: The known-refusals corpus is replayed
The system SHALL hold a corpus of known refusals, `tests/garde_session/corpus-refus.json`, each case carrying class, finding, tool, input, expected refusal and pose (design D9). Its first cases SHALL be only the confirmed reproductions of lot L1, and no case SHALL be written without a confirmed reproduction. The suite `garde_session` SHALL replay every case whose pose is reached and fail, naming the case, on a case let through.

#### Scenario: Case let through
- **WHEN** a case expected refused from a reached pose is let through by the guard or the assembled rules
- **THEN** the replay fails and names the case id and its class

#### Scenario: Case of a later pose
- **WHEN** a case is expected from P2 and the settings do not yet hold the P2 entry
- **THEN** the replay skips it, stating the pose it waits for

Source: untested until implemented (tests/garde_session, task 9.2)

### Requirement: The known-refusals corpus stays out of the public tree
The system SHALL exclude the corpus file and its replay module from the public tree by exact rules of the edition manifest, never by a prefix. A manifest test SHALL fail if either is included.

#### Scenario: Public tree
- **WHEN** the manifest classifies the corpus file or its replay module
- **THEN** both are excluded by an exact rule

#### Scenario: Rule turned into a prefix
- **WHEN** the exclusion of the corpus is written as a folder prefix
- **THEN** the manifest test fails and names the path

Source: untested until implemented (tests/build_edition, task 9.2)

### Requirement: bmad-eval-runner stays in quarantine until the BMAD 7 decision
The system SHALL keep the bmad-eval-runner skill under `.claude/quarantaine/`, with its `SKILL.md` renamed so that Claude Code does not load it. Static tests SHALL fail when a `SKILL.md` of that skill is under `.claude/skills/`, when the quarantine folder lacks the renamed file, or when a file under `.claude/skills/` or `.claude/agents/` carries the Claude Code option that skips permissions. The quarantine SHALL be lifted only at the go or no-go of BMAD 7 and after an Opus review.

#### Scenario: Skill reinstalled
- **WHEN** a BMAD reinstall puts the skill back under `.claude/skills/`
- **THEN** the static test fails and names the skill

#### Scenario: Permission-skipping option
- **WHEN** a skill file holds the option that skips permissions
- **THEN** the static test fails and names the file

Source: untested until implemented (tests/garde_session, task 9.4)
