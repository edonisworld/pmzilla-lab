# tooling-branch-sync Specification

## Purpose
`tools/branch_sync.sh` lets a session bring `main` into the work branch of the current worktree before its finish, so that conflicts show while they can still be prepared, not under the finish lock. It merges only `main`, previews first, refuses before anything is started, never pushes, resets or fetches, and checks the result after the merge. Created by the change branch-sync (feature R-97).

## Requirements

### Requirement: The branch-sync tool merges main only into the work branch of the current worktree
The system SHALL provide `tools/branch_sync.sh`, launched by a session from a work branch's worktree, that merges into the current branch only the more advanced of local `main` and `origin/main` (`light_main_ref`), without fetch. It SHALL take no branch argument, and SHALL NOT push, move `main` or `origin/main`, force, bypass a hook, or resolve a conflict.

#### Scenario: Local main ahead, no conflict
- **WHEN** local `main` has commits the branch lacks and the preview finds no conflict
- **THEN** the tool merges `main` into the branch with `git merge --no-edit`, prints `branch_sync : main fusionnée dans <branche> : <sha court> <sujet>`, leaves the worktree clean, leaves local `main` and `origin/main` unchanged, and exits 0

#### Scenario: origin/main ahead
- **WHEN** `origin/main` contains local `main` and is ahead of it
- **THEN** the tool merges `origin/main` into the branch, names `origin/main` in its output, leaves local `main` unchanged, and exits 0

#### Scenario: main already contained
- **WHEN** the branch already contains the chosen `main`
- **THEN** the tool prints `branch_sync : déjà à jour : main est contenue dans <branche>`, changes nothing, and exits 0

#### Scenario: Diverged references
- **WHEN** local `main` and `origin/main` have diverged
- **THEN** the tool prints `branch_sync : main local et origin/main ont divergé : rien n'est fait`, changes nothing, and exits 7

#### Scenario: Main not found
- **WHEN** there is no local `main`
- **THEN** the tool prints `branch_sync : main introuvable : rien n'est fait`, changes nothing, and exits 7 (the radar too)

#### Scenario: Main moved after the preview
- **WHEN** the reference chosen no longer equals the commit chosen when the tool is about to merge
- **THEN** the tool prints `branch_sync : main a changé pendant l'exécution : rien n'est fait`, merges nothing, and exits 7

#### Scenario: Fast-forward
- **WHEN** the branch has no commit of its own beyond `main`
- **THEN** the branch moves to `main` without a merge commit, the worktree is clean, and the tool exits 0

#### Scenario: Merge commit message
- **WHEN** the merge needs a commit
- **THEN** it is made from the full reference, with rerere switched off, and with the message git writes for the short name, passed by the tool: `Merge branch 'main' into <branche>` from `refs/heads/main`, `Merge remote-tracking branch 'origin/main' into <branche>` from `refs/remotes/origin/main`

#### Scenario: Usage
- **WHEN** the tool is given an unknown option, a branch name, or two options
- **THEN** it prints `branch_sync : usage : bash tools/branch_sync.sh [--manuel | --check | --help]` and exits 2

#### Scenario: Variable that is not an executable file
- **WHEN** `BRANCH_SYNC_MANUAL` or `BRANCH_SYNC_RUNNER` is set to anything but an executable file (a command line, a missing or non-executable file)
- **THEN** the tool prints `branch_sync : <variable> doit désigner un fichier exécutable : rien n'est fait`, runs nothing (never through `eval`), and exits 2

### Requirement: The branch-sync tool refuses outside the worktree of a clean work branch
Before any merge, the tool SHALL refuse, in this order: outside Git (3); under another finish's live lock (4); in the workspace, the run folder, on a detached HEAD, `main` or `spike/*` (3); with modified tracked files (5); during a merge, rebase, cherry-pick or revert (6). A refusal SHALL change nothing, and the tool SHALL never touch the finish lock.

#### Scenario: Workspace
- **WHEN** the tool is run in the workspace
- **THEN** it prints `branch_sync : refusé : l'espace de travail n'est pas une branche de travail` and exits 3

#### Scenario: Run folder
- **WHEN** the tool is run in the run folder, detached or on a branch
- **THEN** it prints `branch_sync : refusé : le dossier d'exécution n'est pas une branche de travail` and exits 3

#### Scenario: main or spike branch
- **WHEN** the worktree holds `main` or a `spike/*` branch
- **THEN** it prints `branch_sync : refusé : <branche> n'est pas une branche de travail` and exits 3

#### Scenario: Detached HEAD
- **WHEN** the worktree is on a detached HEAD outside the run folder
- **THEN** it prints `branch_sync : refusé : HEAD détachée, aucune branche de travail` and exits 3

#### Scenario: Dirty worktree
- **WHEN** a tracked file of the worktree is modified
- **THEN** it prints `branch_sync : worktree pas propre : rien n'est fait` and exits 5

#### Scenario: Merge in progress
- **WHEN** the worktree has a merge in progress
- **THEN** it prints `branch_sync : une fusion est déjà en cours dans le worktree : rien n'est fait` and exits 6

#### Scenario: Cherry-pick, revert or rebase in progress
- **WHEN** `CHERRY_PICK_HEAD`, `REVERT_HEAD`, `rebase-merge` or `rebase-apply` exists
- **THEN** it prints `branch_sync : une opération Git (rebase, cherry-pick ou revert) est en cours dans le worktree : rien n'est fait` and exits 6

#### Scenario: Untracked file
- **WHEN** only untracked files are present and none is in the way of the merge
- **THEN** the worktree counts as clean, the merge is made and the untracked files are left in place

#### Scenario: Another finish holds the lock
- **WHEN** the finish lock of the common Git folder is held by a live process with another token, even when the tool is run in the workspace
- **THEN** it prints `branch_sync : fin de branche en cours (<branche>, depuis HH:MM) : rien n'est fait`, exits 4, and the lock is left as it was

#### Scenario: Stale lock
- **WHEN** the lock's process no longer exists
- **THEN** the tool goes on as without a lock and leaves the lock folder untouched

### Requirement: The branch-sync tool previews first and aborts at the first conflict
The tool SHALL preview through `finish_merge_preview` of `tools/finish_merge.sh` first. A predicted conflict or an impossible preview SHALL stop it with nothing started (8), listing the files and the resolution path (Edit, commit, run again). A failed merge SHALL be aborted with `git merge --abort` (9). An interruption (129, 130, 143) SHALL abort a merge the tool started.

#### Scenario: Predicted conflict
- **WHEN** the preview finds a conflict
- **THEN** the tool prints `branch_sync : fusion de main prévue : conflit sur <n> fichier(s)`, the paths and `branch_sync : conflit prévu : rien n'est commencé`, exits 8, and the branch, the index and the files are unchanged with no merge in progress

#### Scenario: Preview impossible
- **WHEN** git cannot compute the preview
- **THEN** the tool prints `branch_sync : aperçu de la fusion impossible : rien n'est commencé`, changes nothing, and exits 8

#### Scenario: Conflict the preview did not predict
- **WHEN** the preview finds no conflict but the real merge conflicts
- **THEN** the tool aborts the merge, prints `branch_sync : fusion en échec (conflit non prévu ou crochet refusé) : annulée, rien n'est changé`, exits 9, and the branch, the index and the files are as before

#### Scenario: Untracked file in the way
- **WHEN** an untracked file would be overwritten by the merge
- **THEN** git refuses, the tool exits 9 with the same phrase, the file keeps its content and nothing else changed

#### Scenario: Abort impossible
- **WHEN** the merge failed and `git merge --abort` leaves the merge in progress
- **THEN** the tool prints `branch_sync : annulation impossible : une fusion reste en cours dans le worktree`, forces nothing, and exits 11

#### Scenario: Interrupted before MERGE_HEAD
- **WHEN** the merge was started, `MERGE_HEAD` is absent, `HEAD` still equals the commit noted before the merge and tracked files are modified
- **THEN** the tool exits 11 with a phrase that gives that commit (`sommet avant la fusion : <AVANT>`) and says that nothing is reset, and it resets nothing

#### Scenario: Check after the merge fails
- **WHEN** the merge is committed but the check afterwards fails (main not contained, worktree not clean, merge in progress)
- **THEN** the tool prints `branch_sync : vérification : …` followed by `; fusion commitée, sommet avant : <AVANT court>` and exits 11

#### Scenario: Hook refuses the merge commit
- **WHEN** the preview finds no conflict but a `commit-msg` hook refuses the merge commit
- **THEN** the tool aborts the merge, prints `branch_sync : fusion en échec (conflit non prévu ou crochet refusé) : annulée, rien n'est changé`, exits 9, and no merge state is left

#### Scenario: Interruption during the merge
- **WHEN** the tool receives SIGTERM while its merge is in progress
- **THEN** it prints `branch_sync : interrompu (code 143)` and `branch_sync : fusion commencée par l'outil : annulée`, exits 143, and the branch is unchanged with no merge in progress

### Requirement: The branch-sync tool regenerates a manual-only conflict with --manuel
With `--manuel`, when the only predicted conflict is `docs/pmzilla/manuel.md`, the tool SHALL merge, regenerate the manual (`uv run tools/manual.py --write`), stage it, run `bash tests/run_all.sh --staged` and commit the merge with its hooks. Any failure, a red runner included, SHALL abort the merge (code 10). Any other conflict, or no option, SHALL stop the tool (8).

#### Scenario: Manual alone in conflict
- **WHEN** the tool runs with `--manuel` and only the manual conflicts
- **THEN** the manual is regenerated by the generation command, the runner is run in the worktree before the commit (the regenerated manual already staged), the merge is committed, the branch contains `main`, the worktree is clean, and the tool exits 0

#### Scenario: Generation fails
- **WHEN** the generation command fails
- **THEN** the tool aborts the merge without running the runner, prints `branch_sync : régénération du manuel, runner ou commit en échec : fusion annulée, rien n'est changé` and exits 10

#### Scenario: Runner red
- **WHEN** the generation succeeds and the runner fails
- **THEN** the tool aborts the merge, prints the same phrase, exits 10, and the branch, the index and the files are as before

#### Scenario: Option without conflict
- **WHEN** `--manuel` is given and the merge has no conflict
- **THEN** the merge is the ordinary one and neither the generation command nor the runner runs

#### Scenario: Another conflict besides the manual
- **WHEN** the tool runs with `--manuel` and another file conflicts too
- **THEN** it exits 8 with nothing started

#### Scenario: Manual alone without the option
- **WHEN** only the manual conflicts and `--manuel` is absent
- **THEN** the tool exits 8 and prints `seul le manuel généré est en conflit : relancer avec --manuel`

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
