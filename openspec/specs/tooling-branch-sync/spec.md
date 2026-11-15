# tooling-branch-sync Specification

## Purpose
`tools/branch_sync.sh` is a read-only radar: run with `--check`, it lists, for each worktree holding a work branch, how many commits of `main` its branch lacks and, when late, the preview of the merge of `main` (without conflict, or the conflicting files), so that conflicts show while they can still be prepared, not under the finish lock. It never integrates `main` itself: a work branch integrates `main` by `git rebase main` in its own worktree. Created by the change branch-sync (feature R-97); reduced to the radar by the author's decision of 2026-10-28 (weeding, entry D99), described by the change branch-sync-radar-purpose.

## Requirements

### Requirement: The branch-sync radar lists late worktrees without changing anything
`tools/branch_sync.sh --check` SHALL list, for each worktree holding a branch other than `main` and `spike/*`, outside the workspace and the run folder, how many commits of the chosen `main` its branch lacks and, when late, the preview (without conflict, or the conflicting files). It SHALL run anywhere in the repository and under another finish's lock (saying so on one line), and it SHALL NOT merge, fetch, or write a ref, an index or a file.

#### Scenario: Three work branches
- **WHEN** one work branch is up to date, one is late without conflict and one is late with a conflict
- **THEN** the radar prints `<branche> (<dossier>) : à jour`, `<branche> (<dossier>) : <n> commit(s) de retard ; fusion de main prévue : sans conflit`, `<branche> (<dossier>) : <n> commit(s) de retard ; fusion de main prévue : conflit sur <k> fichier(s)` with the paths, then `branch_sync : 3 worktree(s) de branche de travail, 2 en retard sur main, 1 avec conflit prévu`, and exits 0

#### Scenario: Read-only
- **WHEN** the radar has run
- **THEN** the refs, the HEAD, the index and the files of every worktree are unchanged and no merge is in progress

#### Scenario: Diverged references
- **WHEN** local `main` and `origin/main` have diverged
- **THEN** the radar exits 0 (it does not refuse), prints for each work branch `<branche> (<dossier>) : main local et origin/main ont divergé : retard non calculé`, and changes nothing

#### Scenario: Under the lock
- **WHEN** another finish holds the lock
- **THEN** the radar still runs, prints `branch_sync : fin de branche en cours (<branche>, depuis HH:MM) : aucune fusion possible avant sa fin`, and exits 0

### Requirement: The branch-sync tool is a radar only
The system SHALL give `tools/branch_sync.sh` a single working mode, the read-only radar `--check`, plus `--help`. Any other invocation SHALL be refused with exit code 2 and the messages of design D2, and SHALL NOT change the worktree. This rule replaces the former merge mode and its `--manuel` option (design D4); it falls with the rule that integrates `main` by `git rebase main`. Source: `tests/branch_sync/test_branch_sync.sh`.

#### Scenario: No option
- **WHEN** the tool is launched with no option in a work branch's worktree that is late on `main`
- **THEN** it exits 2, prints `branch_sync : usage : bash tools/branch_sync.sh --check` and a line containing `git rebase main`, and the worktree's refs, HEAD, index and files are unchanged

#### Scenario: Removed merge option
- **WHEN** the tool is launched with `--manuel`
- **THEN** it exits 2 with the usage phrase, merges nothing and the worktree is unchanged

#### Scenario: Other arguments
- **WHEN** the tool is launched with an unknown option, with a branch name, or with `--check` and another option
- **THEN** it exits 2 with the usage phrase and starts no radar and no merge

#### Scenario: Help
- **WHEN** the tool is launched with `--help`
- **THEN** it exits 0, describes `--check`, names `git rebase main` as the way to integrate `main`, lists its codes and changes nothing

### Requirement: The branch-sync tool never integrates main itself
The system SHALL leave the integration of `main` to `git rebase main` in the work branch's worktree; `tools/branch_sync.sh` names it and SHALL NOT run it nor change a ref, HEAD, index or file. The scan SHALL bear on `tools/branch_sync.sh` alone; its only admitted exception SHALL be the merge preview by `git merge-tree --write-tree` (objects only). Replacement and removal: design D4. Source: `tests/branch_sync/test_branch_sync.sh`.

#### Scenario: No forbidden command in the tool
- **WHEN** the source of `tools/branch_sync.sh` alone is scanned outside its comments, the usage line that advises `git rebase main` being the only allowed mention
- **THEN** no git command that pushes, resets, fetches, pulls, checks out, switches, rebases, stashes, updates a ref, deletes a branch, cleans, cherry-picks, reverts or merges is found, nor any `--force`, `--no-verify` or hooks-path override, including after global `-C` and `-c` options

#### Scenario: Merge preview is the only exception
- **WHEN** the radar shows, for a late worktree, the preview of the merge of `main`
- **THEN** the preview goes through `git merge-tree --write-tree` of `tools/finish_merge.sh`, which writes objects only, and no other merging command is admitted (author's validation with this correction, R-20261031-32); the worktree's refs, HEAD, index and files are unchanged
