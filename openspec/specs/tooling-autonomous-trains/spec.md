# tooling-autonomous-trains Specification

## Purpose
Describes the autonomous-train job: a pass (`train_auto.py pass`), launched by launchd or from the Terminal, that runs its controls in order, reads the ready list kept by `train_ready.py`, and runs the trial of the train finish on the retained branches, then, only after the author's activation, the real train (change autonomous-trains-merge); and the journal, state, observation summary, emergency stop, launchd template and exit codes of both tools.

## Requirements

### Requirement: The pass is refused in a Claude Code session
The system SHALL refuse `pass` and `reprendre` when the session marker is present, with exit 3 and `train_auto : session Claude Code, lancement refusé`, before reading the list or taking any lock. It SHALL record the caller as `launchd` when launchd's service label is in the environment and `terminal` otherwise.

#### Scenario: Session marker present
- **WHEN** `pass` runs with the session marker set
- **THEN** it exits 3 with the key phrase, and no trial runs

#### Scenario: Launched by launchd
- **WHEN** `pass` runs without the session marker and with launchd's service label set
- **THEN** the journal record names the caller `launchd`

### Requirement: Controls run in order and the first failure stops the pass
The system SHALL evaluate the controls of design D2 in their order. On the first failure it SHALL record the decision and the reason code of design D11, and launch nothing. It SHALL read the exit codes of the tools it calls, never their phrases. It SHALL NOT fetch: it compares local `main` with `git ls-remote --exit-code origin main`, run without any prompt.

#### Scenario: Outside the window
- **WHEN** `pass` runs before the observation time or after its tolerance or after the latest start time
- **THEN** it prints `train_auto : attente : hors fenêtre`, journals `attente` with `hors-fenetre`, and runs no trial

#### Scenario: Morning state not verified
- **WHEN** `morning_state.sh check` exits non-zero inside the window
- **THEN** the pass journals `attente` with `matin` and runs no trial

#### Scenario: Remote unreachable
- **WHEN** `git ls-remote` fails or exceeds its time limit
- **THEN** the pass journals `attente` with `distant`, no prompt is shown, and no trial runs

#### Scenario: Local main differs from the remote
- **WHEN** the remote `main` differs from local `main`
- **THEN** the pass journals `attente` with `main-different` and does not fetch

### Requirement: The pass waits for the finish lock and the session runner within the tolerance
The system SHALL retry the lock control every five minutes while the finish lock is held by a live process, until the end of the tolerance, then journal `attente` with `verrou-fin`. It SHALL NOT take over a lock held by a live process. From T2 of change tooling-proof-in-container it SHALL NOT wait for the session runner's lock, removed with that lock (design D3, R-20261104-7), nor journal `runner-session`.

#### Scenario: Author's finish running
- **WHEN** the finish lock is held during the whole tolerance
- **THEN** the pass journals `attente` with `verrou-fin` and runs no trial

#### Scenario: Lock released in time
- **WHEN** the finish lock is released before the end of the tolerance
- **THEN** the pass goes on to the next controls

#### Scenario: Former session runner's lock present
- **WHEN** a file at the former place of the session runner's lock names a live process and the finish lock is free
- **THEN** the pass does not wait, goes on to the next controls, and no record holds `runner-session`

### Requirement: The ready list is written only through train_ready
The system SHALL keep the ready list in one owner-only file of the lab's data folder, outside Git, in the format of design D3 of autonomous-trains-observe. `train_ready.py add <branch> --revue faite|non-requise` SHALL compute the tip and its proof itself and SHALL refuse for every reason of design D3. A session SHALL prove a branch by the container proof, no longer by the branch fingerprint (change tooling-proof-in-container, D3). The pass SHALL NOT write the list.

#### Scenario: Proof computed by add
- **WHEN** `add` runs
- **THEN** it computes the tip and its proof itself, through the one proof function of the tip (complete fingerprint, container proof with the Mac fingerprint, or branch fingerprint); it accepts no tip or fingerprint on its command line, and does not accept the per-commit targeted fingerprint as a proof

#### Scenario: Refusal of add
- **WHEN** `add` meets one or more reasons of design D3
- **THEN** it exits 3, prints one `train_ready : refusée : <branche> : <raison>` line per reason, and writes nothing

#### Scenario: Branch added with the branch fingerprint
- **WHEN** a clean worktree whose branch fingerprint equals the tip's tree is added with `--revue faite`
- **THEN** one line holds the branch, the tip, the tree, `faite` and the time, and the output is `train_ready : inscrite : <branche> (sommet <sha12>, revue faite)` followed by `train_ready : preuve : suites de la branche (<n>)`

#### Scenario: Branch added
- **WHEN** a clean worktree whose complete-runner fingerprint equals the tip's tree is added with `--revue faite`
- **THEN** one line holds the branch, the tip, the fingerprint tree, `faite` and the time, and the output is `train_ready : inscrite : <branche> (sommet <sha12>, revue faite)` followed by `train_ready : preuve : runner complet`

#### Scenario: Branch proven by a session
- **WHEN** a session has run `bash tools/ci_local.sh run <branche>` green on its three phases, then `bash tests/run_all.sh --mac` green on the same tree, and adds the branch with `--revue faite`
- **THEN** `add` lists it and prints `train_ready : preuve : conteneur et passe Mac`

#### Scenario: Stale fingerprint
- **WHEN** neither fingerprint's tree equals the tip's tree
- **THEN** `add` exits 3 with the reason, and the list is unchanged

#### Scenario: Per-commit targeted fingerprint only
- **WHEN** the worktree holds only the targeted fingerprint of its last commit's index
- **THEN** `add` exits 3 with `sans-empreinte`

#### Scenario: Review not required for code
- **WHEN** `add` is given `--revue non-requise` for a branch that changes a file outside the specification and documentation paths
- **THEN** it exits 3 with the `revue` reason

#### Scenario: Protected branch
- **WHEN** the branch touches a protected file and `add` is given `--revue non-requise`
- **THEN** `add` exits 3 with the `outillage-protege` label, which names the author's finish

#### Scenario: The pass leaves the list untouched
- **WHEN** a pass has run
- **THEN** the list file's content is byte for byte unchanged

### Requirement: The exclusion reasons of the job refuse the listing only without a review
The exclusion reasons of the job (`outillage-protege`, `postures`, `base`, `front`) SHALL be reasons of refusal of `add` only with `--revue non-requise`, with the labels of design D16 of change autonomous-trains-merge; with `--revue faite` they SHALL NOT prevent the listing. In both modes, the pass SHALL exclude at every pass a line whose branch is an author's train (design D2, through the one function `train_de_l_auteur`): `outillage-protege` with `outillage de fin, runner, preuve, .claude/ ou CLAUDE.md : train de l'auteur`, or `postures` with `arbre lu par les postures : train de l'auteur`. The pass SHALL NOT exclude a line for database code, a Mothra interface path or `sensible` files only when its review is `faite` at its tip. `controle-impossible` SHALL refuse with both flags. A listed line that the pass excludes SHALL still count toward the ceiling of five until its branch ends.

#### Scenario: Database branch reviewed
- **WHEN** a branch that touches database code is listed with `--revue faite` at its tip
- **THEN** the pass retains it, and the train's gate decides

#### Scenario: The pass still excludes the listed line
- **WHEN** the pass meets the line of a branch that touches a `juge` file, the runner or the proof, listed with `--revue faite`
- **THEN** it excludes it with `outillage-protege` and the label `outillage de fin, runner, preuve, .claude/ ou CLAUDE.md : train de l'auteur`, takes no trial from it, and the line keeps one place of the ceiling

#### Scenario: Branch excluded from the job, review done
- **WHEN** a branch that touches protected `juge` tooling or the files the postures read is added with `--revue faite`, and nothing else refuses it
- **THEN** `add` exits 0 and writes its line with `faite`, and the single-branch train reads that line as a recorded review

#### Scenario: Branch excluded from the job, review not required
- **WHEN** a branch that touches database code or a Mothra interface path is added with `--revue non-requise`
- **THEN** `add` exits 3 with `code de la base ou migration : revue Opus requise` or `chemin d'interface de Mothra : revue Opus requise`, and the list is unchanged

#### Scenario: Branch not controllable
- **WHEN** the branch is not controllable (finish_checks code 3), whatever the review flag
- **THEN** `add` exits 3 with `controle-impossible`

#### Scenario: Calculation impossible
- **WHEN** finish_checks returns code 4 or the front list cannot be read, whatever the review flag
- **THEN** `add` exits 5 (calculation impossible) and writes nothing

### Requirement: The ready list stays consistent under parallel sessions
The system SHALL write the list only under an exclusive lock on a lock file beside it, through a temporary file replaced atomically. It SHALL keep one line per branch, replacing an existing line in place, and keep the order of addition. It SHALL treat a malformed line as making the whole list unreadable, naming the line number and never its content.

#### Scenario: Two additions at once
- **WHEN** two `add` commands for different branches run at the same time
- **THEN** the list holds both lines and stays well formed

#### Scenario: Branch added again
- **WHEN** a branch already listed is added again after a new commit
- **THEN** its line holds the new tip at the same position, and no second line exists

#### Scenario: Malformed line
- **WHEN** a line of the list has a wrong number of fields
- **THEN** `list` exits 4 with `train_ready : liste illisible : ligne <n>`, and the pass journals `attente` with `liste-illisible`

### Requirement: Lines are dropped and pruned by the tool
The system SHALL provide `drop <branch>`, which removes the line and exits 0 with `train_ready : absente de la liste : <branche>` when there is none. It SHALL provide `prune`, run first by `add`, which removes the lines whose tip is in `origin/main` or whose branch no longer exists. It SHALL NOT remove any other line.

#### Scenario: Merged branch pruned
- **WHEN** a listed branch's tip is in `origin/main` and `prune` runs
- **THEN** its line is removed and the output counts it

### Requirement: The pass checks every line again before the trial
The system SHALL check every line again before the trial: branch present and not in `origin/main`, reference equal to the noted tip, a proof of the tip's tree by the same function as `add`, path exclusions, review flag. It SHALL exclude a line that no longer holds, naming the branch and the reason of design D11, and SHALL keep the other lines. It SHALL NOT treat the proof as replacing the finish's checks or the train's complete runner.

#### Scenario: Commit after the addition
- **WHEN** a listed branch received a commit after its line was written
- **THEN** the pass prints `train_auto : écartée : <branche> : sommet changé depuis l'inscription` for it and keeps the other valid branches

#### Scenario: Branch fingerprint removed
- **WHEN** the branch fingerprint of a listed line was erased by a new branch run that failed
- **THEN** the line is excluded with `sans-empreinte`

Design references: proof function of change targeted-suites-admission, design D4; exclusion reasons of design D11 of autonomous-trains-observe.

### Requirement: Exclusions come from the finish checks' contract
The system SHALL compute the path exclusions in one function, called by both tools, from `finish_checks.py branch <b> --json`, and from the finish's interface-path list until the train's e2e proof replaces it; the pass's exclusions for an author's train SHALL go through the one function `train_de_l_auteur` (change autonomous-trains-merge, design D2, D16). The `base` and `front` reasons SHALL refuse `add --revue non-requise` only, and SHALL NOT exclude from the pass a line whose review is `faite` at its tip (R-20261101-61, P3). The function SHALL NOT copy a path list of the finish. If the JSON contract lacks a needed record, the implementation SHALL stop rather than use another source.

#### Scenario: Database change excluded
- **WHEN** a branch that changes a database path that makes control 14 applicable is added with `--revue non-requise`
- **THEN** `add` refuses it with `base` and the label `code de la base ou migration : revue Opus requise`; listed with `--revue faite` at its tip, the same branch is not excluded by the pass with `base`

#### Scenario: Checks impossible
- **WHEN** `finish_checks.py` exits 4 for a branch
- **THEN** that branch is excluded with `controle-impossible`

### Requirement: A busy worktree excludes its branch, and the workspace is frozen by the finish lock
The system SHALL check only the worktrees of the listed branches for a running process, with the pilot tool's busy map, and exclude a busy worktree's branch with `session-active`. It SHALL NOT wait because a session is open in the workspace or in a worktree outside the train: the trial's finish lock freezes, through the targeted freeze of change autonomous-trains-merge (design D18), `main`, the run tree, the ready list and the train's worktrees, and nothing else.

#### Scenario: Session in a listed worktree
- **WHEN** a process has its current folder in one listed branch's worktree
- **THEN** that branch is excluded with `session-active`, and the others are tried

#### Scenario: Session in the workspace
- **WHEN** a session is open in the workspace only
- **THEN** the pass is not delayed by it, and the trial's lock refuses the session's commits and suites only as design D18 states

### Requirement: The cap keeps the first valid lines
The system SHALL retain at most the cap of valid lines, in list order, and exclude the rest with `plafond`.

#### Scenario: More valid lines than the cap
- **WHEN** the list holds more valid lines than the cap
- **THEN** the first lines up to the cap are retained and the others are excluded with `plafond`

### Requirement: The trial result is read by its exit code with one relaunch
The system SHALL read the trial's exit code. On 62 or 64 it SHALL relaunch the trial once without the branches the finish named in its refusal lines, read by one parser function. It SHALL NOT relaunch when no branch can be read, nor more than once per pass. On 65 or 79 it SHALL arm the emergency stop.

#### Scenario: One branch refused at admission
- **WHEN** the first trial exits 62 and names one branch
- **THEN** the pass relaunches the trial once without it, and the record holds both codes and the removed branch

#### Scenario: Names in the train
- **WHEN** the trial exits 65
- **THEN** the pass creates the stop file, prints `train_auto : arrêt armé après le code 65`, and does not relaunch

#### Scenario: Parser pinned to the real finish
- **WHEN** the real `finish_train.sh` refuses a branch in a fixture repository
- **THEN** the parser returns that branch

### Requirement: Each pass is journaled without names and purged after one year
The system SHALL append one JSON record per pass, `arret` and `reprendre` to the journal of design D7, and remove records older than one year at each pass. Branch names SHALL pass the sensitive-names guard before any write: a match is written `branche masquée` and excluded with `nom`; a guard that cannot run gives `attente` with `garde-noms`. The journal SHALL NOT hold a person name or a ticket key, nor go to Git or GitHub.

#### Scenario: Sensitive name in a branch name
- **WHEN** a listed branch name matches a sensitive name
- **THEN** the journal and the state hold `branche masquée`, never the name, and the branch is excluded with `nom`

#### Scenario: Purge
- **WHEN** the journal holds a record older than one year
- **THEN** the next pass removes it

### Requirement: The state, the status and the observation summary are service functions
The system SHALL write the last pass record to the state file, the pass being its only writer. It SHALL expose `last_state()` through `status [--json]` and `observation_summary(days)` through `observation [--days N] [--json]`, with the content of design D7. Both are allowed in a session and SHALL write nothing. The printed forms SHALL only format these records.

#### Scenario: Branch later merged by the author
- **WHEN** a branch retained by an `observé` pass with trial 0 has its tip in `origin/main` afterwards
- **THEN** the summary counts it as merged after observation, with the delay from the pass

#### Scenario: JSON and text agree
- **WHEN** `observation --json` and `observation` run on the same journal
- **THEN** every figure of the text appears in the JSON

### Requirement: The emergency stop is set by anyone and lifted by the author only
The system SHALL treat the presence of the stop file as a stop (`arrêté`). `arret [--raison <code>]` SHALL create it and journal an `arret` record, also in a session. `reprendre` SHALL remove it and journal a `reprendre` record, and SHALL be refused in a session (exit 3). When the file is absent while the last stop record is newer than the last `reprendre` record, the pass SHALL recreate it, print `train_auto : arrêt disparu sans « reprendre » : recréé` and decide `arrêté`.

#### Scenario: Stop set from a session
- **WHEN** `arret` runs in a session
- **THEN** the stop file exists, the output is `train_auto : arrêt posé`, and the next pass decides `arrêté`

#### Scenario: Stop removed by hand
- **WHEN** the stop file is deleted without `reprendre`
- **THEN** the next pass recreates it and decides `arrêté` with `arret-disparu`

### Requirement: Only one pass runs at a time
The system SHALL hold the job's own lock for the whole pass. A second pass SHALL exit 5 with `train_auto : un autre passage est en cours`, writing nothing.

#### Scenario: Concurrent pass
- **WHEN** a pass starts while another holds the job's lock
- **THEN** it exits 5 and the journal gains no record from it

### Requirement: The launchd template is printed by the tool and installed by the author
The system SHALL print the launchd template with `train_auto.py plist`, from the tool's own constants:
- fourteen `StartCalendarInterval` entries, hourly from 08:00 to 21:00 Paris time;
- no `RunAtLoad`, `KeepAlive` or `StartInterval`;
- the run tree's tool launched by the generation's interpreter with `-I` (design D1);
- the job's log file.

It SHALL NOT install or load the template nor launch the job with the system `python3`, and no other copy of the schedule SHALL exist.

#### Scenario: Template content
- **WHEN** `plist` runs
- **THEN** the output is a valid property list with the entries above and no `RunAtLoad`, `KeepAlive` or `StartInterval` key

#### Scenario: Hourly entries
- **WHEN** `plist` runs
- **THEN** it holds fourteen calendar entries, from hour 8 to hour 21, each at minute 0

#### Scenario: Interpreter of the generation
- **WHEN** `plist` runs under an interpreter of 3.10 or newer whose folder holds an identical `python3`
- **THEN** `ProgramArguments` is that interpreter (`sys.executable`, exact comparison), then `-I`, the run tree's `tools/train_auto.py` and `pass`, and the folder of that interpreter opens the job's `PATH`

#### Scenario: Generation under a fake 3.9 refused
- **WHEN** `plist` is run by a fake interpreter that reports 3.9
- **THEN** it exits 8 with `train_auto : modèle refusé : python3 3.10 ou plus requis pour le générer (version 3.9)` and prints no template

#### Scenario: Interpreter of the installed template differs
- **WHEN** the first element of the installed `ProgramArguments` does not have the real path of the `python3` of the template's first PATH folder
- **THEN** `installed_plist_check()` returns `different` with `ProgramArguments` among the differences, and the doctor check `train-auto-plist` is a problem with the regeneration command

### Requirement: Exit codes have one sense each
The system SHALL use, for `train_auto.py`: 0 done, 2 usage, 3 refused in a session (`pass`, `reprendre`, `activer`), 4 folders or files not writable, 5 another pass running, 6 unexpected error (type only), 7 activation refused, condition not met (change autonomous-trains-merge, design D19). For `train_ready.py`: 0 done, 2 usage, 3 branch refused, 4 list unreadable or not writable, 5 calculation impossible. Both are declared in each tool's header. A pass SHALL exit 0 whatever its journaled decision, a real train included, and SHALL NOT print a stack trace.

#### Scenario: Waiting pass exits 0
- **WHEN** a pass decides `attente`
- **THEN** it exits 0 and the decision is in the journal

#### Scenario: Unexpected error
- **WHEN** an unexpected exception occurs
- **THEN** the tool exits 6 with the exception type only

#### Scenario: Activation refused
- **WHEN** `activer` runs outside a session and the condition is not met
- **THEN** it exits 7

#### Scenario: Red real train
- **WHEN** a pass runs a real train that exits 70
- **THEN** the pass exits 0 and the train's code is in the journal

### Requirement: One function computes the proof of a tip
The system SHALL compute the proof of a tip through the one function `preuve(arbre, worktree=None)` of `tools/preuve_arbre.py`, called by `train_ready` for `add`, `list` and the pass, returning `complete` (complete fingerprint, written by a complete Mac runner or, until the follow-up after 26/11, by the train after its gate), `conteneur` (the CI proof line of the tree with exactly `portable,base,e2e` and the Mac fingerprint of the same tree), `ciblee` (branch fingerprint) or none, in that order, and SHALL expose it in `list --json`, with the suites of a branch proof (change ci-local-runner, design D8, Q216, Q218 (a), R-20261101-116). Its command line SHALL print the word and exit 0 for a proof, 1 for none and 2 when the proof cannot be computed. It SHALL NOT read the per-commit targeted fingerprint, accept a container proof without the Mac fingerprint or with other phases, compute `complete` or `ciblee` without a worktree, nor keep a second copy of the rule in `train_auto` or elsewhere.

#### Scenario: Proof line with two phases
- **WHEN** the CI proof file holds the tree with `portable,base` and the Mac record holds it
- **THEN** the proof is not `conteneur`

#### Scenario: Last line of the tree decides
- **WHEN** the CI proof file holds a `portable,base,e2e` line for the tree followed by a later line for the same tree with `base,portable,e2e`, and the Mac record holds the tree
- **THEN** the proof is not `conteneur`

#### Scenario: Command line without proof
- **WHEN** `python3 -I tools/preuve_arbre.py <arbre>` runs on a tree held by no file
- **THEN** it exits 1

#### Scenario: Container proof
- **WHEN** the CI proof file holds the tip's tree with its three phases and the Mac record holds the same tree
- **THEN** `add` lists the branch and prints `train_ready : preuve : conteneur et passe Mac`

#### Scenario: Container proof without the Mac pass
- **WHEN** the CI proof file holds the tree and the Mac record does not
- **THEN** `add` refuses with the reason of a missing proof

#### Scenario: JSON
- **WHEN** `list --json` runs on a line proven by its branch fingerprint
- **THEN** the line holds `"preuve": "ciblee"` and its suites

#### Scenario: Complete proof preferred
- **WHEN** the complete fingerprint and the branch fingerprint equal the tip's tree
- **THEN** the proof is `complete`

### Requirement: The doctor state is read from the doctor's level in a clean environment
The system SHALL compute the pass's doctor state by running the run tree's doctor with the tool's own interpreter, isolated, in an environment without the checked-repository test variable and without any `GIT_*` variable, and SHALL parse its JSON from standard output only: `vert` when the hook check's `level` is ok, `rouge` otherwise, `absent` without that check or a readable JSON. It SHALL NOT read standard error as part of the JSON (R-20261110-43).

#### Scenario: Conforming hook
- **WHEN** the run tree's hooks folder holds the conforming `reference-transaction` link
- **THEN** the doctor state is `vert`

#### Scenario: Hook missing
- **WHEN** the run tree has no `reference-transaction` hook
- **THEN** the doctor state is `rouge`

#### Scenario: Run tree as a linked worktree
- **WHEN** the run tree is a linked worktree whose common repository holds, respectively lacks, the conforming link
- **THEN** the doctor state is `vert`, respectively `rouge`

#### Scenario: Inherited variable towards a conforming repository
- **WHEN** the pass's environment holds the checked-repository test variable, `GIT_DIR`, `GIT_COMMON_DIR` or `GIT_WORK_TREE` naming a conforming repository, and the run tree has no hook
- **THEN** the doctor state is `rouge`

#### Scenario: Warning on standard error
- **WHEN** the doctor writes a warning on standard error and its JSON on standard output gives the hook check ok
- **THEN** the doctor state is `vert`

#### Scenario: Interpreter without the YAML module
- **WHEN** the tool's interpreter cannot import the YAML module
- **THEN** the doctor state is still `vert` with a conforming hook and `rouge` without it

Source: `tests/train_auto/test_doctor_etat_reel.py` (DoctorEtatReel); `tools/train_auto.py` (`doctor_state`). The level is read under `level`, and under `status` only when `level` is absent (the fake doctor of the merge tests). What the state decides stays in the requirement on the doctor check of the hook (change autonomous-trains-merge, design D17).

### Requirement: The merge mode needs the author's activation
The system SHALL launch a real train only when the activation file of design D6 exists and `activation_valid()` holds it valid; otherwise the pass SHALL run the trial only, as in observation, and journal `mode` `observation`. `train_auto.py activer` SHALL exit 3 in a session, and SHALL exit 7 with `train_auto : activation refusée : condition non remplie` and one `train_auto : activation : manque <libellé>` line per missing element when the condition is not met, writing nothing in either case. The system SHALL NOT read the activation from an environment variable, recreate a vanished activation file, or let `reprendre` activate.

#### Scenario: Activation before the series
- **WHEN** the author runs `activer` and the train record holds four counted trains in a row
- **THEN** it exits 7, prints the missing `serie` element, and no activation file exists

#### Scenario: Activation in a session
- **WHEN** `activer` runs with the session marker set
- **THEN** it exits 3 and writes nothing

#### Scenario: Vanished activation file
- **WHEN** the activation file is deleted by hand
- **THEN** the next pass runs the trial only, journals `observation`, and does not recreate the file

#### Scenario: Forged activation
- **WHEN** the activation file names a tip that is not a counted record of the train record
- **THEN** the pass runs the trial only and the status shows `activation invalide`

### Requirement: The series of five green trains is computed from the train record only
The system SHALL compute the activation condition in `activation_status()` from the train record of design D4 at each call, as design D5 states: five counted records in a row (`mode` `manuel`, code 0, sense `fusionne`, `runner` `conteneur`), at least one with two branches or more and at least one with `base` or `front` true, the series being reset by a `manuel` record on `runner` `conteneur` with code 69, 70, 71 or 82. `activation [--json]` SHALL be allowed in a session and SHALL write nothing. The system SHALL NOT keep a counter file, read a log text or a phrase, nor count a record in `auto` mode, with `runner` `remplace` or with the sense `essai`.

#### Scenario: Series met
- **WHEN** the five newest counted records are in a row, one with two branches and one with `base` true
- **THEN** `activation --json` holds `"met": true` and `"series": 5`

#### Scenario: Red gate resets the series
- **WHEN** a `manuel` record on the container with code 70 is newer than three counted records
- **THEN** the series is 0

#### Scenario: Substituted gate
- **WHEN** a code 0 record has `runner` `remplace`
- **THEN** it is not counted and does not reset the series

#### Scenario: Refusal before the gate
- **WHEN** a `manuel` record with code 62 lies between counted records
- **THEN** it neither counts nor resets the series

### Requirement: Deactivation is allowed to anyone and only strengthens
The system SHALL provide `train_auto.py desactiver`, allowed in a session, which removes the activation file, journals a `desactiver` record and prints `train_auto : fusion automatique désactivée`, or `train_auto : fusion automatique déjà désactivée` when no file exists. It SHALL NOT remove the stop file, change the ready list or lift a stop.

#### Scenario: Deactivated from a session
- **WHEN** `desactiver` runs in a session while the merge mode is active
- **THEN** the activation file is absent, the stop file is unchanged, and the next pass observes only

### Requirement: The active pass launches the real train after a green trial and never relaunches it
When the activation is valid and the final trial exits 0 before the latest start of design D9, the system SHALL run `finish_train.sh --auto` from the run tree on the branches of that trial, three at most, with standard input closed, without any `FINISH_TRAIN_*` variable or the finish lock token, in its own process group ended after three hours, and SHALL journal the decision `train` with the train's code, sense, duration and tips. The pass SHALL NOT relaunch the real train in the same pass, add a branch after the trial, answer a question, fast-forward, push or write a reference itself, nor start a trial in merge mode after the latest start.

#### Scenario: Green trial in merge mode
- **WHEN** the mode is active and the trial of two branches exits 0
- **THEN** the pass runs the train with `--auto` and these two branches, and the journal holds the decision `train` with the train's code

#### Scenario: Four valid lines
- **WHEN** the mode is active and the list holds four valid lines
- **THEN** the trial and the real train take the first three, and the fourth is excluded with `plafond`

#### Scenario: After the latest start
- **WHEN** the mode is active and the pass runs after `latest_start()`
- **THEN** it journals `attente` with `depart-limite` and runs neither a trial nor a train

#### Scenario: Latest start reached during the trial
- **WHEN** the mode is active and the clock passes `latest_start()` between the trial and the real train
- **THEN** it journals `attente` with `depart-limite` and runs no train

#### Scenario: Deactivated during the trial
- **WHEN** the activation file is removed while the trial runs
- **THEN** the pass journals `observe` with `essai` and runs no train

#### Scenario: Unreadable state in merge mode
- **WHEN** the mode is active and `etat.json` is present but unreadable
- **THEN** it journals `attente` with `etat-illisible`, runs neither a trial nor a train, and does not rewrite the file

#### Scenario: Unreadable state in observation mode
- **WHEN** the mode is observation and `etat.json` is present but unreadable
- **THEN** the pass keeps observing and journals its record, but does not rewrite the file: an unreadable state is never rewritten, whatever the mode

#### Scenario: Unreadable state is shown
- **WHEN** `etat.json` is present but unreadable
- **THEN** `status`, `status --json` (`illisible: true`) and the `/pilot` train line say `état du train automatique illisible : le réparer ou le retirer`, and no notification is sent

#### Scenario: A train that ignores TERM
- **WHEN** the real train ignores TERM
- **THEN** it gets KILL after the grace period, the stop is armed, and no train leaves before `reprendre`

#### Scenario: Fewer than ten measured trains
- **WHEN** the train record holds fewer than ten merged container trains
- **THEN** the latest start is 20:30 Paris time

### Requirement: Every exit code of the real train has one handling, checked against the register
The system SHALL handle each code of the real train by the table of design D10, armed stop included, and SHALL keep a test that fails when a `finish_train` code of `tools/finish_codes.yaml` with origin `utilise` or `reserve` has no line in the table, or when a line names a code absent from the register. The pass SHALL NOT treat an unknown code, or a code 0 without a record of sense `fusionne`, as a success.

#### Scenario: Names in the train
- **WHEN** the real train exits 65
- **THEN** the stop file exists and the report line ends with `arrêt armé : examiner, puis reprendre`

#### Scenario: Lock held by the author
- **WHEN** the real train exits 67
- **THEN** no stop is armed and the report says that the next pass tries again

#### Scenario: Code missing from the table
- **WHEN** the register declares a `finish_train` code that the table lacks
- **THEN** the table test fails and names the code

### Requirement: A refused real train is not retried on the same tips
After a real train that exits 62, 64, 69, 70, 71, 82, 83 or 84, the system SHALL exclude at every later pass each line whose tip belongs to that train, with `echec-au-sommet` and `train refusé sur ce sommet : nouveau commit ou retrait attendu`, until the line's tip changes or the line is dropped (design D11). The pass SHALL NOT remove a list line, and `reprendre` SHALL NOT clear the exclusion. The author SHALL be notified of each excluded branch and its reason (R-20261106-6 Q3), once per excluded tip, at the first pass that excludes it; the later passes write it to the journal only.

#### Scenario: Red train, next pass
- **WHEN** a real train of two branches exits 70 and neither branch receives a commit
- **THEN** the next pass excludes both lines with `echec-au-sommet`, runs no trial with them, and notifies the author of each branch with the reason `train refusé sur ce sommet (code 70)`

#### Scenario: Exclusion repeated
- **WHEN** a later pass excludes the same line at the same tip again
- **THEN** no new notification is sent and the exclusion is written to the journal

#### Scenario: Branch corrected
- **WHEN** one of these branches receives a commit and is listed again at its new tip
- **THEN** that line is no longer excluded for `echec-au-sommet`

### Requirement: Each real train and each failed trial in merge mode is reported and notified
After each real train, and after a trial that ends non-zero after its relaunch while the activation is valid, the system SHALL append one line to the merge report `fusions-auto.md` of the lab's private step folder, creating its header when absent, and send one notification, both formatted from `merge_report()` (design D12, D14, D15). Branch names SHALL pass the sensitive-names guard first. The system SHALL NOT rewrite or remove a line of that file, write in the gesture file `gestes.md` or any other file of that private folder, write a person name or a ticket key, put a branch name in the notification, send anything to Git or GitHub, or notify a pass in observation.

#### Scenario: Merged train
- **WHEN** a real train of two branches exits 0 with the sense `fusionne`
- **THEN** the file gains one line with both tips, their reviews, main before and after, the duration and `rien`, and one notification `fusionné : 2 branche(s), …` is sent

#### Scenario: Sensitive branch name
- **WHEN** a branch name matches a sensitive name
- **THEN** the line holds `branche masquée` and never the name

#### Scenario: Observation
- **WHEN** the activation is absent and a trial exits 64
- **THEN** no line is written and no notification is sent

### Requirement: The doctor check of the reference-transaction hook blocks the merge mode
The system SHALL record the state of the doctor check of the `reference-transaction` hook as `vert`, `rouge` or `absent` in each pass record. In merge mode, `rouge` or `absent` SHALL stop the pass with `attente` and `crochets-doctor`; in observation it SHALL NOT stop the pass (design D17). A failed `install_hooks.sh --verify` SHALL stop the pass with `crochets` in both modes. The pass SHALL NOT launch a real train while the doctor check is not `vert`.

#### Scenario: Check absent in merge mode
- **WHEN** the mode is active and the doctor check does not exist
- **THEN** the pass journals `attente` with `crochets-doctor` and runs no trial

#### Scenario: Check absent in observation
- **WHEN** the activation is absent and the doctor check does not exist
- **THEN** the pass record holds `doctor` `absent` and the pass goes on

### Requirement: The launchd template carries the job's PATH
The system SHALL write in the template printed by `train_auto.py plist` an `EnvironmentVariables` entry holding `PATH` only, computed at each call by one function: the folder of the generating interpreter, then the account's fnm default folder, then the system folders of the tool's constant, without duplicates (design D1). It SHALL NOT write an account path in a tracked file, nor read the fnm folder from an environment variable.

#### Scenario: Order of the folders
- **WHEN** `plist` runs under an interpreter of 3.10 or newer whose folder holds an identical `python3`
- **THEN** the template's `PATH` starts with that folder, then the fnm default `bin` folder under the account's home folder, then the system folders, each once

#### Scenario: Rest of the template unchanged
- **WHEN** the template is printed
- **THEN** `ProgramArguments`, `WorkingDirectory`, the calendar entries and the log paths are those of the requirement on the launchd template, and no `RunAtLoad`, `KeepAlive` or `StartInterval` key exists

#### Scenario: Account path computed
- **WHEN** the tests give another home folder
- **THEN** the fnm folder of `PATH` is under that home folder, and the tool's source holds no account path

### Requirement: The template is refused for an interpreter older than 3.10
The system SHALL make `plist` exit 8, printing nothing on standard output and the phrase of design D2 on standard error, when the generating interpreter is older than 3.10 or when its folder holds no `python3` that is the same file. Code 8 SHALL be declared in the tool's header with the sense `modèle launchd refusé : interpréteur de la génération`. The system SHALL NOT print a partial template.

#### Scenario: Old interpreter
- **WHEN** `plist` runs under an interpreter that reports 3.9
- **THEN** it exits 8 with `train_auto : modèle refusé : python3 3.10 ou plus requis pour le générer (version 3.9)` and standard output is empty

#### Scenario: Folder without an identical python3
- **WHEN** the interpreter's folder holds no `python3`, or one that resolves to another file
- **THEN** it exits 8 with `train_auto : modèle refusé : le dossier de l'interpréteur n'a pas de python3 identique`

### Requirement: An unreadable scan or a missing interpreter does not stop the job
The system SHALL keep arming the emergency stop on a trial code 65 or 79 only. A trial that exits 68 (content scan impossible) or 76 (calculation impossible, `python3` 3.10 or newer missing included) SHALL be journaled with its code and SHALL NOT create the stop file (design D3, D5).

#### Scenario: Trial exits 68
- **WHEN** the final trial exits 68
- **THEN** the pass journals the code, no stop file is created, and `train_auto : arrêt armé après le code 68` is not printed

#### Scenario: Trial exits 76
- **WHEN** the final trial exits 76
- **THEN** no stop file is created and the next pass is not stopped by it

#### Scenario: Trial exits 65
- **WHEN** the final trial exits 65
- **THEN** the stop is armed as before

### Requirement: One service function reads the emergency stop for other tools
The system SHALL provide `stop_info()` in `train_auto.py`, read-only and never raising, returning the format, a state among `absent`, `arrete`, `illisible` and `inconnu`, the date of the last `arret` record (`AAAA-MM-JJ HH:MM`, Paris time) and its reason (design D7). Another tool SHALL read the stop through it only. It SHALL NOT write the stop file or the journal.

#### Scenario: Stop armed by a trial
- **WHEN** the stop file exists and the last `arret` record holds the Paris time `2026-11-07 21:04` and the reason `65`
- **THEN** `stop_info()` returns `arrete`, that date and `65`

#### Scenario: Stop without a record
- **WHEN** the stop file exists and the journal holds no `arret` record or cannot be read
- **THEN** `stop_info()` returns `illisible` with a null date and reason

#### Scenario: No stop
- **WHEN** the stop file does not exist
- **THEN** `stop_info()` returns `absent`

#### Scenario: Data folder unresolved
- **WHEN** the data folder cannot be resolved
- **THEN** `stop_info()` returns `inconnu` and raises nothing

### Requirement: The activation is refused while the emergency stop is active
The system SHALL add the missing code `arret-actif`, labelled `arrêt d'urgence actif (reprendre d'abord)`, to `activation_status()` while `stop_info()` is not `absent`, so that `activer` exits 7 with one `manque` line for it and writes nothing (design D9). It SHALL NOT change the validity of an existing activation file because of the stop.

#### Scenario: Activation during a stop
- **WHEN** the series is met and the stop file exists, and the author runs `activer`
- **THEN** it exits 7, prints `train_auto : activation : manque arrêt d'urgence actif (reprendre d'abord)`, and no activation file exists

#### Scenario: Status during a stop
- **WHEN** `activation --json` runs while the stop file exists
- **THEN** `missing` holds `arret-actif` and `met` is false

### Requirement: The activation needs a launchd trial at 0 since the template was last loaded
The system SHALL add the missing code `essai-launchd` to `activation_status()` unless the installed template is at state `ok` of `installed_plist_check()` and a pass record has the caller `launchd`, a final trial code 0, the template's `env_job` fingerprint and a time later than the template's modification time (design D10). Each pass SHALL record `env_job` for a launchd caller only. It SHALL NOT count a Terminal pass or a trial under a different template.

#### Scenario: Only manual trains
- **WHEN** the series of the author's trains is met, the stop is absent and no launchd pass has a trial at 0
- **THEN** `activer` exits 7 with `manque un essai à 0 lancé par launchd depuis le dernier chargement du modèle`

#### Scenario: Trial under the former template
- **WHEN** the only launchd trial at 0 has an `env_job` that differs from the installed template's, or is older than its modification time
- **THEN** `essai-launchd` is still missing

#### Scenario: Installed template absent
- **WHEN** the installed template is absent or unreadable
- **THEN** `essai-launchd` is missing

#### Scenario: Installed template present but not conforming
- **WHEN** a launchd trial at 0 later than the template's modification time has the template's fingerprint, but `installed_plist_check()` returns `different`, `python-absent` or `python-ancien`
- **THEN** `essai-launchd` is still missing

#### Scenario: Template regenerated after the interpreter change
- **WHEN** the template installed before the change of `ProgramArguments` is still loaded
- **THEN** its state is `different` and `essai-launchd` is missing until the author regenerates and reloads it and a launchd trial at 0 runs under it

#### Scenario: Launchd trial after the reload
- **WHEN** a launchd pass later than the installed template's modification time has a final trial code 0 and the template's fingerprint, and the other conditions hold
- **THEN** `activation --json` holds `"met": true`

#### Scenario: Fingerprint, never a path
- **WHEN** a pass runs under launchd
- **THEN** its journal record holds `env_job` as 16 hexadecimal digits and no `PATH` value; a Terminal pass holds a null `env_job`

### Requirement: A pass under an interpreter older than 3.10 waits without arming the stop
The system SHALL check, at the start of a pass and after the stop and session checks, the version of the interpreter that runs it: under 3.10 the pass SHALL journal the decision `attente` with the reason `python-ancien` (`python3 3.10 ou plus requis`) and exit 0 (design D1). It SHALL NOT arm the stop, run a trial or a train for this reason, and `train_auto.py` SHALL stay importable under 3.9.

#### Scenario: Pass under 3.9
- **WHEN** a pass runs under an interpreter that reports 3.9
- **THEN** it journals `attente` with `python-ancien`, prints `train_auto : attente : python3 3.10 ou plus requis`, creates no stop file, runs no trial and exits 0

#### Scenario: Import under 3.9
- **WHEN** `train_auto.py` and its import closure are parsed with the 3.9 grammar
- **THEN** every file parses, and on a Mac whose system `python3` is older than 3.10 that interpreter imports the tool with `-I`
