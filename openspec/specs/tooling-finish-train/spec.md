# tooling-finish-train Specification

## Purpose
Describes `tools/finish_train.sh`, the only finishing script, run by the author in the Terminal from the run tree: it finishes one to six local branches given on its command line as one train, admitting each branch on its worktree and its finish checks, building the train from `origin/main` with its own merge commits, scanning every commit, running the gate on the train tree (the CI run in the container, then the Mac pass), asking one question, then fast-forwarding and pushing `main`, recording it as validated, cleaning up, and logging each run with fixed exit codes and banners.

## Requirements

### Requirement: Interface branches admitted to the train
The system SHALL admit to the train a branch that changes a path of the interface list when no other admission rule refuses it, and SHALL require control 16 in the branch's check output without refusing on its verdict (change finish-e2e-proof-shared, design D5, D6). The system SHALL NOT exclude a branch for changing the front of Mothra, and SHALL NOT read the interface list itself: it reads control 16 through the finish checks module only. Untested until implemented.

#### Scenario: Front branch admitted
- **WHEN** a listed branch changes a path of the interface list and touches no protected tooling
- **THEN** it is admitted, and no reason naming the front of Mothra or a unit finish is printed for it

#### Scenario: Control 16 missing from the check output
- **WHEN** the finish checks module returns a branch output without control 16
- **THEN** that branch is refused with `contrôles impossibles : contrôle 16 absent de la sortie de finish_checks`

### Requirement: Red suites are replayed on the train tip before exiting
When the portable phase of the CI run or the Mac pass exits red with named suites, the system SHALL replay them once on the train tip, container suites by `run --rejeu portable <suites>` through `FINISH_TRAIN_CI` or ci_local, Mac suites by `run_all.sh <suites>`, names as arguments, and exit 71 when the replay is green; a red Mac replay gives 70 with today's lines, a container replay as its own requirement says (design D9). The replay SHALL NOT write a report, verdict, proof or fingerprint, run dbtest, run in the quick trial, or move a reference.

#### Scenario: Unstable suite
- **WHEN** a portable suite is red in the train's CI run and green in its replay
- **THEN** the train exits 71 with `runner non concluant : suites rouges non reproduites (<suites>) ; rien n'est fusionné`, and `main` is unchanged

#### Scenario: Replay command
- **WHEN** the replay runs
- **THEN** it runs `ci_local.sh run --rejeu portable` followed by the red container suite names, or `run_all.sh` followed by the red Mac suite names, in the integration worktree detached on the train tip, and no verdict, proof or fingerprint file changes

#### Scenario: Suite red again
- **WHEN** the Mac replay fails again, or exits with any code other than 0
- **THEN** the train exits 70 with today's lines, unchanged, `train rouge : suites en échec : <suites> ; rien n'est fusionné` and `retirer de la liste la branche qui casse ces suites, puis relancer la ligne`, and `main` is unchanged

#### Scenario: Quick trial
- **WHEN** the author runs the train with `--essai`
- **THEN** no runner and no replay run

### Requirement: A red train prints which branches selected the red suites
When the integrated runner exits red with named suites, the system SHALL print, before the replay, the branches whose selection by the selector's range mode holds a red suite (design D5). The hint SHALL NOT designate a branch, remove a branch from the list, change the exit code, or stop the train when the selector fails for a branch. Untested until implemented (the finish_train suites).

#### Scenario: One branch selected a red suite
- **WHEN** a train of three branches is red on a suite that only the second branch's selection holds
- **THEN** the train prints `train rouge : suites rouges sélectionnées par : <deuxième branche>` before its exit line

#### Scenario: No branch selected the red suite
- **WHEN** no branch's selection holds a red suite
- **THEN** the train prints `train rouge : suites rouges sélectionnées par aucune branche`

#### Scenario: Selector fails for one branch
- **WHEN** the selector's range mode fails for one branch of a red train
- **THEN** the train prints `indice impossible pour <branche>`, prints the hint for the other branches, and its exit code is the one the replay decides

#### Scenario: Selector requires the complete run for one branch
- **WHEN** the selector's range mode exits 3 (complete run required) for a branch of a red train
- **THEN** that branch counts as having selected every suite, because the complete runner proved it: the hint names it, and the line of the selection defect is absent (design D5)

#### Scenario: Every branch named
- **WHEN** a red train's hint names every branch and the replay is red
- **THEN** the train exits 70 with today's lines, relaunches nothing, and the ready list is unchanged

### Requirement: A red train outside every selection reports a selection defect
When the replay is red, the hint names no branch and no selector failed, the system SHALL keep the line of 70 and its code and print after it, before the end banner, a line reporting a selection defect (targeted-suites-admission D5, R-20261031-41, R-20261031-50). The system SHALL NOT print that line after a green replay, when the hint names a branch or when a selector failed, and SHALL NOT relaunch the train or change the list. Untested until implemented (the finish_train suites).

#### Scenario: Red suite outside every selection
- **WHEN** the replay is red, no branch's selection holds a red suite and the selector succeeded for every branch
- **THEN** the train exits 70 with today's line, followed by `finish_train : défaut de sélection : suites rouges hors de toute sélection de select_suites (<suites>) ; corriger le sélecteur avant le train suivant`, then the end banner

#### Scenario: Hint names a branch
- **WHEN** the replay is red and the hint names one branch
- **THEN** no selection-defect line is printed

#### Scenario: Selector failed for a branch
- **WHEN** the replay is red, the hint names no branch and the selector failed for one branch (`indice impossible pour <branche>`)
- **THEN** the train exits 70 with today's line and no selection-defect line is printed

### Requirement: The integrated complete runner stays the only gate to main
The system SHALL run, in every train that is not a quick trial and before the question, one CI run on the train tree from the integration worktree, then the Mac pass there (change ci-local-runner, design D9), whatever the proofs of the listed branches; a stop during the Mac pass or its stability reading SHALL end with `===== arrêt à passe Mac : rien n'est fusionné =====`, and every other stop at this gate with `===== arrêt à porte du conteneur : rien n'est fusionné =====` (Q232 (a), R-20261101-118). It SHALL NOT skip or narrow that gate because a branch holds a proof, nor name the container's step for a stop of the Mac pass.

#### Scenario: Green gate
- **WHEN** the CI run is green on its three phases and the Mac pass is green
- **THEN** the train prints `porte du conteneur verte sur l'arbre du train`, then `runner complet vert sur l'arbre du train`, and goes to the question

#### Scenario: Stop at the Mac pass
- **WHEN** the CI run is green and the Mac pass stops the train, or its stability reading does
- **THEN** the train ends with `===== arrêt à passe Mac : rien n'est fusionné =====`

#### Scenario: Stop at the container
- **WHEN** the CI run stops the train
- **THEN** the train ends with `===== arrêt à porte du conteneur : rien n'est fusionné =====`

#### Scenario: Every branch proven by its suites
- **WHEN** every branch of a train was listed with a branch fingerprint
- **THEN** the train still runs the CI run and the Mac pass in the integration worktree before the question

### Requirement: Branch list taken from the command line only
The system SHALL provide `tools/finish_train.sh`, which finishes 1 to 6 local branches given on its command line, merged in list order (design D1, M1). The system SHALL NOT read the list from a file written by a session, and SHALL exit 60 on a duplicate name, an unknown option, an empty list or more than six names. Untested until implemented.

#### Scenario: Duplicate branch
- **WHEN** the author gives the same branch twice
- **THEN** the script exits 60 with the usage phrase and changes nothing

#### Scenario: Seven branches
- **WHEN** the author gives seven branch names
- **THEN** the script exits 60 and changes nothing

### Requirement: Launch only from the run tree, in the author's terminal
The system SHALL refuse to run, with code 61 and the phrases of design D18, unless it is launched from a clean run tree detached at local `main`, at `origin/main`, or at the train's base in state S2, outside a Claude Code session, with the workspace on a clean `main` (design D1). The system SHALL NOT be launched by a Claude Code session, nor from a run tree detached elsewhere. Untested until implemented.

#### Scenario: Launched from a worktree copy
- **WHEN** the script is launched from a copy outside the run tree
- **THEN** it exits 61 with `lancement refusé : à lancer depuis le dossier d'exécution` and changes nothing

#### Scenario: Run tree modified
- **WHEN** the run tree has a local change, or its HEAD is not detached
- **THEN** the script exits 61 with `lancement refusé : dossier d'exécution modifié ou pas détaché`

#### Scenario: Run tree left behind by an earlier run
- **WHEN** a run resumed at the push finds the run tree at `origin/main`, or a run resumed at the cleanup finds it at the train's base
- **THEN** the launch is accepted and the resumption goes on

#### Scenario: Run tree detached elsewhere
- **WHEN** the run tree is detached at a commit that is neither local `main`, `origin/main` nor, in state S2, the train's base
- **THEN** the script exits 61 at the step `état des références` with `ni la base du train déjà poussé`, and the second banner line gives the real state (E2, E3 or E4)

#### Scenario: Claude Code session
- **WHEN** `CLAUDECODE` is set in the environment
- **THEN** the script exits 61 before taking the finish lock

#### Scenario: Workspace not ready
- **WHEN** the workspace is not on `main`, or holds a non-ignored change
- **THEN** the script exits 61 and changes nothing

#### Scenario: Current folder in a listed worktree
- **WHEN** the current folder is inside the worktree of a listed branch
- **THEN** the script exits 61 with `lancement refusé : le dossier courant est dans le worktree de <branche>`

#### Scenario: Git identity missing
- **WHEN** the author's Git identity is not configured
- **THEN** the script exits 61 with `lancement refusé : identité Git de l'auteur absente`

### Requirement: Script body read before it runs
The system SHALL keep the whole body of the script in functions called from its last line, and SHALL source its modules before the first step (design D2). After the run-tree update, the system SHALL NOT launch or source anything from the run tree. Untested until implemented.

#### Scenario: Run tree updated during the run
- **WHEN** the run-tree update replaces the file of the running script with another content
- **THEN** the closing lines printed are those of the version that started

### Requirement: Finish lock and morning guard
The system SHALL hold the finish lock from right after the launch checks until exit, and SHALL check the morning guard right after the lock and again just before main moves (design D3), refusing with code 66 and the two lines of morning-guard-light design D4 only when the guard exits 1 (watch or backup running). No variable SHALL bypass either refusal, and a warning SHALL NOT refuse. Untested until implemented.

#### Scenario: Another finish running
- **WHEN** another finish holds the finish lock
- **THEN** the script exits 67 at once, without waiting, with `une autre fin de branche est en cours`, and changes nothing

#### Scenario: Lock released on every exit
- **WHEN** the script exits after a refusal, a success or an interruption
- **THEN** its lock is removed, and a lock carrying another token is never removed

#### Scenario: Window opens during the runner
- **WHEN** the morning guard allows the start and exits 1 just before main moves, because the backup started meanwhile
- **THEN** the script exits 66 with `finish_train : veille ou sauvegarde du jour en cours` and `finish_train : relancer la même ligne quand la veille et la sauvegarde sont finies`, main is unchanged and nothing is pushed

#### Scenario: Watch running at the start
- **WHEN** the morning guard exits 1 right after the lock is taken
- **THEN** the script exits 66 with the same two lines, before any build, and changes nothing

#### Scenario: Warnings only
- **WHEN** the morning guard exits 0 and prints warning lines
- **THEN** the train goes on as without a warning

### Requirement: Base is origin/main after a fetch
The system SHALL fetch `origin/main` once at the start, take its sha as the base, require local `main` to equal it for a fresh run, and start every range from it (design D4, B1). Before the admission, it SHALL exit 63 when local `main` differs and carries no merge of the list, judged on the graph only. The system SHALL NOT move, reset or rebase local `main` to reconcile it, and SHALL NOT use local `main` as a base. Untested until implemented.

#### Scenario: Local main ahead
- **WHEN** local `main` holds a commit that `origin/main` does not have, and no noted tip of a listed branch is an ancestor of local `main`
- **THEN** the script exits 63 with `base non établie : main local` and both shas, and main is unchanged

#### Scenario: Merge decided on the graph, not on the message
- **WHEN** local `main` is ahead by a commit made by hand with the message `Merge branch '<b>'` for a listed branch whose noted tip is not an ancestor of it
- **THEN** that commit is not counted as a merge of the list and the script exits 63; a noted tip that is an ancestor of local `main` without that message is counted, and the script exits 79

#### Scenario: Base checked before the admission, two launches in a row
- **WHEN** one listed branch is already in `origin/main`, local `main` is ahead of `origin/main` by a foreign commit, and the author launches the line, settles the base by hand (local `main` equal to `origin/main`), then launches the same line again
- **THEN** the first launch exits 63 with `base non établie : main local` and no admission line, the second exits 62 with `déjà contenue dans origin/main` and the relaunch line without that branch, and neither exits 79

#### Scenario: Fetch fails
- **WHEN** the fetch of `origin/main` fails
- **THEN** the script exits 63 and merges nothing

#### Scenario: Custom merge driver
- **WHEN** the repository configuration sets a merge driver
- **THEN** the script exits 63 before any `merge-tree`

### Requirement: Every listed branch checked, every refusal reported
The system SHALL check every listed branch before building the train and report each refused branch with its reason, then exit 62 with the relaunch line without the refused branches (design D6). The system SHALL NOT stop at the first refused branch. Untested until implemented.

#### Scenario: Two refused branches
- **WHEN** the list holds three branches, one touching `.claude/` (or a `CLAUDE.md`) and one with its change left unarchived, and the third admitted
- **THEN** the script exits 62, prints `branche(s) refusée(s) au train : 2 sur 3 ; rien n'est fusionné`, lists the first with `outillage de fin touché (<n> fichier(s)) : train d'une seule branche` followed by its paths and the second with `contrôle 5 refusé : <phrase>`, and prints `ligne sans les branches refusées :` followed by the line with the third branch only

#### Scenario: Missing or merged branch
- **WHEN** a listed branch does not exist locally, or its tip is already in `origin/main`
- **THEN** that branch is refused with `introuvable en local` or `déjà contenue dans origin/main`

### Requirement: Branch admission on its worktree
The system SHALL refuse a branch whose worktree is dirty, holds ignored files that would be lost, or holds another process's current folder, and SHALL refuse it when the process check cannot run (design D6, M10). The system SHALL NOT print a file name from the ignored-files check. Untested until implemented.

#### Scenario: Ignored files in a branch worktree
- **WHEN** a listed branch's worktree holds an ignored file outside the exceptions
- **THEN** the branch is refused with the count and the first-level folders only, and no file name is printed

#### Scenario: Process in a branch worktree
- **WHEN** another process has its current folder in a listed branch's worktree
- **THEN** the branch is refused and the process is named by its number and short command only

#### Scenario: Process check impossible
- **WHEN** `lsof` is absent or its listing does not show the script itself
- **THEN** the branch is refused with `vérification des processus impossible`

### Requirement: Branch admission on its finish checks
The system SHALL admit a branch only when `finish_checks.py` exits 0 or 1, returns controls 19, 5, 6, 14 and 16, and passes or exempts controls 19 and 5 (design D6, M8; finish-single-b3-b6 D19). The system SHALL NOT refuse a branch for its own control 6, 14 or 16: the train tree decides them. Tests: `tests/finish_train/test_admission.py`, `tests/finish_train/test_une_branche.py`.

#### Scenario: Control 6 applicable
- **WHEN** a branch changes an evaluated file
- **THEN** it is not refused at admission for its control 6, and the train tree's control 6 decides after control 14, exiting 83 with `jeu d'essai validant absent pour l'arbre du train ; rien n'est fusionné` when no validating record matches the train tree

#### Scenario: Control 6 missing from the check output
- **WHEN** the finish checks module returns a branch output without control 6
- **THEN** that branch is refused with `contrôles impossibles : contrôle 6 absent de la sortie de finish_checks`

#### Scenario: Not checkable or not computable
- **WHEN** `finish_checks.py` exits 3 or 4 for a branch
- **THEN** that branch is refused with `non contrôlable` or `contrôles impossibles` and the module's phrase

#### Scenario: Database change in a branch
- **WHEN** a branch changes a database path and its tip's tree has no dbtest line
- **THEN** the branch is admitted, and the train tree decides control 14

### Requirement: Protected tooling refused for the train
The system SHALL decide the admission of a branch that touches protected tooling (class `juge`, `.claude/`, a `CLAUDE.md` at any depth) from the number of listed branches and the other admitted judge branches (R-20261102-43, R-20261102-55 (4)). The system SHALL NOT admit `.claude/`, a `CLAUDE.md`, the runner or the proof beside another branch, two judge branches on one `juge` file, a fourth judge branch, or a `sensible` file without review, and SHALL NOT skip the question.

#### Scenario: Rules replaced, removal and tests
- **WHEN** the origin of this requirement is checked
- **THEN** rule R-20261102-43 replaces "a judge branch passes alone", removal: permanent while the train carries judge branches; rule R-20261102-55 (4) replaces nothing, removal: permanent while the train judges its tree with the runner and the proof carried by its own branches; tests: `tests/finish_train/test_plusieurs_juges.py`, `tests/finish_train/test_admission_classes.py`, `tests/finish_train/test_une_branche.py`

#### Scenario: Protected tooling in a one-branch list
- **WHEN** the list holds one branch and it touches protected tooling of class `juge`, a path under `.claude/` or a file named `CLAUDE.md` at any depth
- **THEN** the branch is admitted, and `outillage de fin dans ce train d'une branche : <n> fichier(s)` and the paths are printed before the question

#### Scenario: .claude/ or CLAUDE.md in a list of two branches or more
- **WHEN** in a list of two branches or more, a branch touches `.claude/` or a `CLAUDE.md`
- **THEN** it is refused (62) with `outillage de fin touché (<n> fichier(s)) : train d'une seule branche` followed by the paths

#### Scenario: Runner or proof in a list of two branches or more
- **WHEN** in a list of two branches or more, a branch's `juge` files include the runner or the proof (`tests/run_all.sh`, `ci/passage.sh`, `tools/preuve_arbre.py` or `tools/finish_train.sh`)
- **THEN** it is refused (62) with `modifie le runner ou la preuve : train d'une seule branche (R-20261102-43)` followed by those paths, it does not count among the judge branches, and alone it is admitted

#### Scenario: Up to 3 judge branches beside other branches
- **WHEN** in a list of two branches or more, a judge branch is not refused by another rule
- **THEN** it is admitted beside other branches, up to 3 judge branches per train, and `outillage de fin dans ce train de plusieurs branches (branche juge de rang <i> : <branche>) : <n> fichier(s)` and its paths are printed before the question, the rank being the branch's place in the line

#### Scenario: Judge file already touched by an earlier judge branch
- **WHEN** a judge branch touches a `juge` file already touched by an earlier admitted judge branch of the line
- **THEN** it is refused (62) with `fichier juge <chemin> touché aussi par la branche de rang <i> (rang <j> ici) : deux branches juges ne passent pas ensemble`, the path quoted when its name requires it

#### Scenario: Fourth and later judge branches
- **WHEN** the line holds a fourth admitted judge branch, or a later one
- **THEN** each of them is refused (62) with `quatrième branche juge (rang <j>) : au plus 3 branches juges par train`, and a branch already refused for another reason does not count among the 3

#### Scenario: Sensible files keep the review rule
- **WHEN** a branch also touches `sensible` files
- **THEN** it is admitted with `outil sensible admis après revue Opus du sommet <sha12> : <branche>` when the review is recorded for its exact tip, and refused with `outil sensible touché (<n> fichier(s)) sans revue Opus enregistrée pour le sommet <sha12> : revue ou fin unitaire` otherwise

#### Scenario: Merge conflict refused at the build, never at admission
- **WHEN** two branches of the line conflict on any file
- **THEN** the conflict is refused when the train is built, in the order of the line, with 64 (requirement "Train built by the script with its own commits"), and pairs of branches are not checked for a merge conflict at admission

#### Scenario: Branches judged with the run tree's scripts
- **WHEN** the train judges a listed branch
- **THEN** it uses the run tree's scripts, never the branch's own finish scripts

#### Scenario: Two judge branches on different files
- **WHEN** the author lists two branches, one changing a finish script and the other a file of the Git hooks folder, both `juge`
- **THEN** both are admitted, and `outillage de fin dans ce train de plusieurs branches (branche juge de rang 1 : <b1>) : 1 fichier(s)` and `… (branche juge de rang 2 : <b2>) : 1 fichier(s)` are printed with their paths before the question, and `train d'une seule branche` is not printed

#### Scenario: Hook touched
- **WHEN** a branch modifies a `juge` file, such as a file of the Git hooks folder, and is listed with a branch that touches no protected tooling
- **THEN** both branches are admitted, and the judge branch is printed with `outillage de fin dans ce train de plusieurs branches (branche juge de rang <i> : <branche>) : <n> fichier(s)` and its paths

#### Scenario: Same judge file
- **WHEN** two listed branches both change the same `juge` file
- **THEN** the train exits 62 with `branche(s) refusée(s) au train : 1 sur 2 ; rien n'est fusionné`, the second branch is refused with `fichier juge <chemin> touché aussi par la branche de rang 1 (rang 2 ici) : deux branches juges ne passent pas ensemble`, the relaunch line holds the first branch only, and nothing changes; a recorded review changes nothing

#### Scenario: Fourth judge branch
- **WHEN** four listed branches each change a different `juge` file
- **THEN** the train exits 62, the fourth is refused with `quatrième branche juge (rang 4) : au plus 3 branches juges par train`, and the relaunch line holds the first three

#### Scenario: Branch refused for another reason not counted
- **WHEN** four judge branches on different files are listed and the first one's worktree is not clean
- **THEN** the first is refused with `worktree pas propre`, the three others are admitted, and `quatrième branche juge` is not printed

#### Scenario: .claude/ beside a judge branch
- **WHEN** a branch that changes a file under `.claude/` is listed with an admitted judge branch
- **THEN** it is refused with `outillage de fin touché (1 fichier(s)) : train d'une seule branche` and its path, the train exits 62, and the relaunch line holds the judge branch

#### Scenario: CLAUDE.md in a subfolder
- **WHEN** a branch changes a file named `CLAUDE.md` in a subfolder and is listed with another branch
- **THEN** it is refused with `outillage de fin touché (1 fichier(s)) : train d'une seule branche` and the train exits 62

#### Scenario: Runner or proof beside other branches
- **WHEN** a branch that changes `tests/run_all.sh` or `tools/finish_train.sh` is listed with other branches
- **THEN** it is refused with `modifie le runner ou la preuve : train d'une seule branche (R-20261102-43)` and the path, the train exits 62, and the relaunch line holds the other branches, a judge branch among them

#### Scenario: Runner branch alone
- **WHEN** the author lists only a branch that changes `tests/run_all.sh`
- **THEN** it is admitted, and `outillage de fin dans ce train d'une branche : 1 fichier(s)` and the path are printed before the question

#### Scenario: Conflict on an ordinary file between two judge branches
- **WHEN** two judge branches on different `juge` files both change the same ordinary file in conflicting ways
- **THEN** both pass the admission, the build exits 64 with `conflit à la construction du train : <b2> avec <b1> sur 1 fichier(s) ; rien n'est fusionné`, the file path and `ligne sans cette branche :` followed by the line with the first branch, no runner runs and nothing changes

#### Scenario: Judge and sensible files beside another branch
- **WHEN** a branch changes a `juge` file and a `sensible` file and is listed with an ordinary branch
- **THEN** with an Opus review recorded for its exact tip it is admitted with both lines, `outillage de fin dans ce train de plusieurs branches (branche juge de rang 1 : <branche>) : 1 fichier(s)` and `outil sensible admis après revue Opus du sommet <sha12> : <branche>`; without that review it is refused (62) with `outil sensible touché (<n> fichier(s)) sans revue Opus enregistrée pour le sommet <sha12> : revue ou fin unitaire`, and neither `outil sensible admis` nor `train d'une seule branche` is printed

### Requirement: Train built by the script with its own commits
The system SHALL build the train itself from the base with `git merge-tree --write-tree` and `git commit-tree`, one merge per admitted branch in list order, under the author's Git identity and with the message `Merge branch '<branch>'` (design D7, M9). The system SHALL NOT resolve a conflict, write a `refs/heads/*` or `lot/*` reference while building, or use a session's commit object other than the branch tips. Untested until implemented.

#### Scenario: Shape of the train
- **WHEN** a train of three branches is built
- **THEN** its first-parent chain is three commits `Merge branch '<b1>'`, `Merge branch '<b2>'`, `Merge branch '<b3>'`, each with the previous tip and the branch tip as parents, under the author's identity

#### Scenario: Conflict
- **WHEN** the second listed branch conflicts with the first on one file
- **THEN** the script exits 64 with `conflit à la construction du train`, the branches involved, the file path and the relaunch line without the second branch, and no reference changes

#### Scenario: Conflict on a file with a special name
- **WHEN** the conflicting file's name holds a space, a quote and a newline
- **THEN** the script reads `merge-tree` in its `-z` form, counts one file and prints its path on one quoted line (design D7)

#### Scenario: Git error is not a conflict
- **WHEN** `git merge-tree` exits with a code above 1
- **THEN** the script exits 64 with `construction du train impossible` and names no branch as conflicting

### Requirement: Content scan of every commit of the train
The system SHALL run `range_scan.py` on `origin/main..<train tip>` with every listed branch name, twice (text, then `--json`), and show only its `range_scan : ` lines (design D8, M2; change train-auto-launchd-env, D5, D6). It SHALL exit 65 only when both reads exit 1 and the format-1 JSON holds code 1 and a finding, and 68 on any other outcome than 0 to both. It SHALL NOT scan only the net diff, continue after 65 or 68, or log a trace.

#### Scenario: Secret added then removed on a branch
- **WHEN** a branch adds a secret in one commit and removes it in a later one
- **THEN** the script exits 65 with the scan's finding line and merges nothing

#### Scenario: Names list absent
- **WHEN** the scan exits 2 or 3
- **THEN** the script exits 68 and merges nothing

#### Scenario: Files not examined
- **WHEN** the scan lists files not examined
- **THEN** their count appears in the summary before the question

#### Scenario: Scan crashes at import
- **WHEN** the scan prints a Python trace and exits 1 to both reads, with no JSON report
- **THEN** the script exits 68 with `contrôle de contenu impossible (range_scan, sortie incohérente : code 1 sans trouvaille) ; rien n'est fusionné`, not 65, and merges nothing

#### Scenario: Code 1 without a finding
- **WHEN** both reads exit 1 and the JSON report of format 1 holds no finding of kind `secret`, `name`, `identifier` or `encoding`
- **THEN** the script exits 68 with the same phrase

#### Scenario: Discordant reads
- **WHEN** the text read exits 1 and the JSON read exits 0, or the reverse
- **THEN** the script exits 68 with `contrôle de contenu impossible (range_scan, sortie incohérente : codes <c1> et <c2>) ; rien n'est fusionné`

#### Scenario: No trace in the log
- **WHEN** the scan's output holds lines that do not start with `range_scan : `
- **THEN** the terminal and the log show its `range_scan : ` lines and one line `finish_train : sortie inattendue de range_scan`, and none of the other lines

### Requirement: dbtest run by the script on the train tree
When `finish_checks.py tree` finds a database path changed between `origin/main` and the train tree, the system SHALL run dbtest itself in the integration worktree, then require control 14 to pass on the train tree (design D9). The system SHALL NOT skip dbtest because a dbtest line for that tree already exists. Untested until implemented.

#### Scenario: Line already present
- **WHEN** a dbtest line for the train tree already exists before the run, and a database path changed
- **THEN** the script still runs dbtest

#### Scenario: dbtest red or without line
- **WHEN** dbtest exits non-zero, or exits 0 without writing a line for the train tree
- **THEN** the script exits 69 and merges nothing

#### Scenario: No database change
- **WHEN** no database path changes in the train
- **THEN** the script prints `dbtest sans objet (code de la base inchangé)` and does not run dbtest

### Requirement: Single full runner run by the script, no verdict reused
The system SHALL run the train's gate once on the train tip, in an integration worktree detached at that tip: the CI run, then the Mac pass `bash tests/run_all.sh --mac`, each with closed standard input and none of the reserved variables (design D10, B2; ci-local-runner D9). The system SHALL NOT reuse a verdict, proof, fingerprint or line written before the current run, and SHALL NOT filter or target the gate, except the single replay of the red suites. Untested until implemented.

#### Scenario: Forged verdict file
- **WHEN** a file in the common Git folder declares the train tree green before the run, or the Mac record or the CI proof file already holds a line of the train tree
- **THEN** the CI run and the Mac pass still run, and a line written before the marker is not accepted

#### Scenario: Reserved variables
- **WHEN** `FINISH_TRAIN_*`, `CI_LOCAL_*` or `PMZILLA_LAB_DB_*` variables are set in the author's shell
- **THEN** none of them reaches the CI run or the Mac pass

#### Scenario: Replay is the only targeted Mac run
- **WHEN** the Mac pass exits 1 with named suites
- **THEN** the only other Mac run is `${FINISH_TRAIN_RUNNER:-bash tests/run_all.sh}` followed by those suite names, once, without `--mac`, and no fingerprint file changes

### Requirement: Reading the runner's outcome
The system SHALL count the Mac pass green only on exit 0 with a stable worktree and the train tree's Mac record and CI proof lines written after the marker. After an exit 1 with named suites, it SHALL print the hint and replay them once: 70 if the replay is not green, 71 if it is; any other outcome SHALL exit 71 naming no suite (design D10; targeted-suites-admission D5). It SHALL NOT merge anything after a Mac pass that is not green. Test: `tests/finish_train_base/test_rejeu.py`.

#### Scenario: Branch breaks the train
- **WHEN** the Mac pass on the train tree exits 1 with two suites named on its `TOTAL` line, and the replay of those two suites fails again
- **THEN** the script prints the hint, then exits 70 with `train rouge : suites en échec :` and those two suites, and main is unchanged

#### Scenario: Red suites not reproduced
- **WHEN** the Mac pass exits 1 with named suites, and the replay of those suites exits 0
- **THEN** the script exits 71 with `runner non concluant : suites rouges non reproduites (<suites>) ; rien n'est fusionné`, and main is unchanged

#### Scenario: Runner frozen or refused
- **WHEN** the Mac pass exits 4, 6 or 7, or exits 1 without suites named on a `TOTAL` line
- **THEN** the script exits 71 with `runner non concluant (code <n>)`, names no suite and runs no replay

#### Scenario: Worktree changed during the runner
- **WHEN** a tracked file of the integration worktree changes during the Mac pass and the pass exits 0
- **THEN** the script exits 71 with `worktree d'intégration modifié pendant le runner`

#### Scenario: Fingerprint not rewritten
- **WHEN** the Mac pass exits 0 but the Mac record holds no line of the train tree written after the marker
- **THEN** the script exits 71 with `empreinte du runner absente, différente de l'arbre du train ou non réécrite`

### Requirement: Tracked folders judged on their entries after the runner
The system SHALL snapshot the `inode nom` entries of every tracked folder before the runner and, after an exit 0, judge each folder whose ctime changed on that snapshot, forgiving only ignored additions still present (design D25, author's decision of 2026-10-28). The system SHALL NOT refuse a green runner only for ignored files it left, and SHALL NOT forgive a removal, an inode change, a non-ignored addition, an unchanged list or a tool failure. Untested until implemented.

#### Scenario: Ignored cache left by a green runner
- **WHEN** the runner exits 0 in a fresh integration worktree and leaves a new ignored `__pycache__` folder in a tracked folder, and nothing else changes
- **THEN** the runner counts as green and the script goes on to the summary

#### Scenario: Non-ignored file added
- **WHEN** the runner exits 0 and leaves in a tracked folder a new file that Git does not ignore, beside an ignored addition
- **THEN** the script exits 71 with `runner non concluant (code 0) : worktree d'intégration modifié pendant le runner ; rien n'est fusionné`

#### Scenario: Entry removed or replaced
- **WHEN** the runner exits 0 after removing an ignored entry present before it, or replacing an entry by another with the same name and a different inode
- **THEN** the script exits 71

#### Scenario: Folder renamed then put back
- **WHEN** the runner renames a tracked folder and puts it back under its name, and exits 0
- **THEN** the root's list is identical with a newer ctime, and the script exits 71

#### Scenario: File created then deleted
- **WHEN** the runner creates a file in a tracked folder that receives nothing else, deletes it, and exits 0
- **THEN** the folder's list is identical with a newer ctime, and the script exits 71, also when the file was ignored

#### Scenario: Tool failure
- **WHEN** the snapshot, `ls`, `find` or `git check-ignore` fails, or an entry name holds a newline
- **THEN** the script exits 71 with `worktree d'intégration modifié pendant le runner`

#### Scenario: Known limit
- **WHEN** the runner creates then deletes a file that Git does not ignore in a tracked folder that also keeps a new ignored addition, and exits 0
- **THEN** the transient file is not seen and the runner counts as green, as the script's comment and design D25 document

### Requirement: Mothra's npm packages installed offline in the integration worktree
When the train tree holds `mothra/package-lock.json`, the system SHALL run the offline `npm ci` of design D10 in the integration worktree's `mothra/` before dbtest and the runner, and refuse with 76, 80 or 81 and the lines of design D18 (author's decisions A, Q and B of 2026-10-27). The system SHALL NOT use code 71 for these refusals, run npm without `--offline`, run an install script, or merge anything after a refusal. Untested until implemented.

#### Scenario: Lock in the train tree
- **WHEN** the train tree holds `mothra/package-lock.json` as a regular file and the Node version matches
- **THEN** the script runs the offline `npm ci` in the integration worktree's `mothra/` before dbtest and the runner, at the banner step `paquets npm`

#### Scenario: No lock
- **WHEN** the train tree does not hold `mothra/package-lock.json`
- **THEN** the script runs no npm and this is not a refusal

#### Scenario: Node version differs
- **WHEN** `mothra/.node-version` says `22.1` and `node --version` gives 22.11.0
- **THEN** the script exits 80 with `version de Node trouvée`, the line `fnm use --install-if-missing` followed by the relaunch line, and the banner `===== arrêt à paquets npm : rien n'est fusionné =====`

#### Scenario: Packages absent from the npm cache
- **WHEN** the offline install fails and npm's output contains `ENOTCACHED`
- **THEN** the script exits 81 with `paquets de Mothra absents du cache npm`, then names the train's branches that change the lock relative to `origin/main` and advises on one line `npm ci --ignore-scripts` in each branch's worktree followed by the relaunch line, runs no runner and removes the integration worktree

#### Scenario: Refusal before advice
- **WHEN** the script refuses with 80 or 81
- **THEN** the refusal message is printed before the advice line, never after it

#### Scenario: Names and paths quoted in a line to paste
- **WHEN** a branch name or a worktree path of the cache advice holds a space or a quote
- **THEN** the advice line quotes it with `printf %q`, as it quotes the workspace path and the Node version of the `fnm use` line, and the pasted line runs it as given

#### Scenario: Node version file unreadable by git show
- **WHEN** `mothra/.node-version` is a regular file of the train tree and `git show` fails to read its content
- **THEN** the script exits 76 with `calcul impossible (lecture de mothra/.node-version en échec) ; rien n'est fusionné` and runs no npm

#### Scenario: Other offline failure
- **WHEN** the offline install fails without `ENOTCACHED` in npm's output
- **THEN** the script exits 81 with `npm ci hors ligne en échec`, gives no cache advice, and the log keeps the `npm error` lines without the complete-log line and with the home folder written `~`

#### Scenario: npm missing
- **WHEN** the train tree holds the lock and `npm` is not found
- **THEN** the script exits 76 with `calcul impossible (outil introuvable : npm) ; rien n'est fusionné`

#### Scenario: Node version file not a regular file
- **WHEN** the train tree holds the lock and `mothra/.node-version` with a mode other than 100644 or 100755
- **THEN** the script exits 76 with `calcul impossible (mothra/.node-version de l'arbre du train n'est pas un fichier ordinaire : mode <mode>) ; rien n'est fusionné` and runs no npm

### Requirement: Workspace fingerprint written with the tree its runner validated
Just before main moves, and only after a green runner in the current run, the system SHALL write the train tree into the workspace's full fingerprint (design D11, M3). The system SHALL NOT write that fingerprint in a trial, after an answer other than `o`, or in a resumed run. Untested until implemented.

#### Scenario: No second runner at push
- **WHEN** the train is green and the author answers `o`
- **THEN** the pre-push hook finds the full fingerprint for the pushed tree and launches no runner

#### Scenario: Resumed push
- **WHEN** the script resumes at the push
- **THEN** it writes no fingerprint, and the pre-push hook either finds the earlier one or runs the full runner itself

### Requirement: One summary and one question
The system SHALL print the per-branch summary, the diff stat from `origin/main`, and the verdicts of the train's gate. Without `--auto`, it SHALL then ask the single question `Terminer le train (<n> branche(s)) ? (o/n)` (design D12). With `--auto`, it SHALL evaluate the automatic policy in its place (change autonomous-trains-merge, design D8). The system SHALL NOT merge anything on an answer other than `o`, nor, with `--auto`, without a policy that allows, and SHALL NOT print the question with `--auto`. Untested until implemented.

#### Scenario: Answer n
- **WHEN** the author answers `n`, an empty line, or input ends
- **THEN** the script exits 0 with the banner sense `essai` (design D24), main and the branches are unchanged, no fingerprint is written, and the integration worktree is removed under the cleanup rules

#### Scenario: Automatic mode asks nothing
- **WHEN** the train runs with `--auto`
- **THEN** the question is not printed and standard input is not read

### Requirement: Quick trial without runner
With `--essai`, the system SHALL run every check except dbtest and the runner, print the summary and exit 0 with the trial phrase (design D12). A trial SHALL NOT create a worktree, write a reference or a fingerprint, or ask the question. Untested until implemented.

#### Scenario: Quick trial
- **WHEN** the author runs the line with `--essai` on admissible branches
- **THEN** the script exits 0 with `essai rapide : contrôles passés, sans dbtest ni runner`, and no reference or worktree is added

### Requirement: References read again before main moves
After `o`, the system SHALL read every branch tip, local `main` and `origin/main` again (after one more fetch) and require them unchanged, then check the morning guard (design D13). The system SHALL NOT move main when any of them moved. Untested until implemented.

#### Scenario: Branch moved after the question
- **WHEN** a listed branch gains a commit between admission and the fast-forward
- **THEN** the script exits 73 naming that branch, and main is unchanged

#### Scenario: origin/main moved
- **WHEN** `origin/main` advanced since the start
- **THEN** the script exits 73 with `main ou origin/main a bougé depuis le début de la fin`

### Requirement: Fast-forward of main onto the script's train and one push
The system SHALL fast-forward main onto its own train tip in the workspace with `--ff-only`, require main's tree to equal the tested tree, then push main once (design D13). The system SHALL NOT reset main, push with the owner's bypass variable or `--no-verify`, or push when the tree differs. Untested until implemented.

#### Scenario: Tree differs after the fast-forward
- **WHEN** main's tree after the fast-forward differs from the tested tree
- **THEN** the script exits 73, pushes nothing and prints the old main, without resetting

#### Scenario: Push refused
- **WHEN** the push of main is refused
- **THEN** the script exits 74 with `push refusé : le train est fusionné dans main local seulement`

### Requirement: Main recorded as validated
After a push in a full run whose own gate was green, the system SHALL append `<tree><TAB>complet<TAB><UTC date><TAB><signature>` to the main-validation record of the common Git folder, keeping at most 50 lines, owner-only (change tooling-specs-apres-b9, design D4). It SHALL NOT write it when a test command is set, in a resumed run, in a quick trial or after an answer other than `o`, put a branch or a commit in it, or let a train or pre-push decision depend on it.

#### Scenario: Main recorded
- **WHEN** the push succeeds after a green gate in the same full run
- **THEN** the record gains, as its last line written through a temporary file renamed in place and readable by its owner only, the train tree with the genre `complet`, the UTC date of the day and the signature of requirement "Environment signature of the main-validation record", or `inconnue` when it cannot be computed, and the train prints `arbre de main enregistré comme validé (complet)`

#### Scenario: Rules replaced and removal
- **WHEN** the origin of this requirement is checked
- **THEN** it replaces the writing by the removed branch-finishing script and the requirements of the removed capability `tooling-finish-branch` (change finish-single-b7-b9, design D8; author's decision R-20261105-32 Q1); removal: it falls with an author's decision to remove the record, the same change removing the writing and signature helpers of `tools/finish_env.sh`, the train's call, the tests of the format and requirement "Environment signature of the main-validation record"

#### Scenario: Record full
- **WHEN** the record holds 50 lines before the write
- **THEN** it holds 50 lines after it, the oldest line gone and the new one last

#### Scenario: Record not writable
- **WHEN** the record cannot be written after the push, for example because its path is a folder
- **THEN** the train prints `arbre de main non enregistré (écriture impossible)`, lists it under `train fusionné et poussé, fin incomplète :` and exits 75, and `main` stays pushed

#### Scenario: Run resumed at the push
- **WHEN** a run resumed at the push pushes `main`
- **THEN** no line is added to the record

Source: tests/finish_train_fin/test_question_arrivee.py, class `EnregistrementDeMain` (`test_main_enregistre_comme_valide_complet_avec_le_runner_et_le_ci_local_du_depot`: the line of the train tree with the genre `complet` and the phrase `arbre de main enregistré comme validé (complet)`; `test_la_ligne_de_main_valide_a_quatre_colonnes_date_utc_et_signature_sans_branche_ni_commit`: four columns, UTC date, 64 hexadecimal characters or `inconnue`, neither branch nor commit; `test_main_non_enregistre_quand_le_runner_est_remplace`: the test-command case, whose source stays requirement "Test variables never bypass a refusal"); tests/finish_train_base/test_dbtest_runner.py (`test_un_verdict_vert_force_avant_le_lancement_n_evite_pas_le_runner`: a record line of the train tree written before the run does not spare the gate). Untested: the cap of 50 lines, the failed write (`écriture impossible`, exit 75) and the owner-only write; listed in `openspec/test-gaps.md` (task 2.1 of change tooling-specs-apres-b9). The run resumed at the push: no test located by that inventory, which searched the record's name and not the test helper `lignes_validees`.

### Requirement: Worktrees removed only after checking again
Before removing each worktree, branch or integration, the system SHALL check again that it is clean, holds no ignored file that would be lost and holds no other process's current folder, and only then remove it without force (design D14, M10). A worktree that fails SHALL stay and be listed. The system SHALL NOT force a removal, prune worktrees or delete a worktree's file. Untested until implemented.

#### Scenario: Ignored file written after admission
- **WHEN** an ignored file appears in a branch worktree between admission and cleanup
- **THEN** that worktree and its branch stay, are listed with `worktree gardé`, and the script exits 75 after the push

#### Scenario: Process in a worktree at cleanup
- **WHEN** a process has its current folder in a branch worktree at cleanup
- **THEN** the worktree stays and the line names the process by its number and short command only

#### Scenario: Process check impossible at cleanup
- **WHEN** `lsof` is absent or its listing does not show the script itself at cleanup
- **THEN** the worktree stays, listed with `worktree gardé : <dossier> : processus dans le worktree (vérification impossible)`

### Requirement: Branches deleted safely after the push
After the push, the system SHALL delete with `git branch -d` each listed local branch whose worktree is gone, and a remote branch of the same name when one exists (design D14). A branch that cannot be deleted SHALL stay, be listed and lead to exit 75. The system SHALL NOT force a branch deletion or delete a branch before the push. Untested until implemented.

#### Scenario: Branch kept with its worktree
- **WHEN** a branch's worktree was kept
- **THEN** the branch is kept and listed with `branche gardée`

### Requirement: Run tree updated once, last
After the final check (workspace on a clean `main`, no merge in progress, local `main` equal to `origin/main`), the system SHALL run `run_worktree.sh update` once, as its last action (design D15). The system SHALL NOT run the update before the push or more than once per run. Untested until implemented.

#### Scenario: Run tree absent
- **WHEN** the run-tree update exits 4 because the run tree is absent
- **THEN** the script prints `dossier d'exécution absent, rien à mettre à jour`

#### Scenario: Run tree update postponed
- **WHEN** the run-tree update exits 7 after a successful push
- **THEN** the script exits 75 with `dossier d'exécution non mis à jour` and `Pour le mettre à jour : bash tools/run_worktree.sh update`

#### Scenario: Full success
- **WHEN** every step succeeds
- **THEN** the script exits 0 with `terminé : main <sha12> -> <sha12>, <n> branche(s)`

### Requirement: Resumption decided from the references only
The system SHALL decide where to resume from the references only, after the fetch: a full run, a run resumed at the push, or a cleanup only (design D5, B3). A local `main` carrying all or part of the list's merges without being the pure train SHALL exit 79 with nothing touched. The system SHALL NOT take a resumption step from a file, and SHALL NOT reuse a runner verdict in a resumed run. Untested until implemented.

#### Scenario: Fresh run
- **WHEN** local `main` equals `origin/main` and no listed branch is merged
- **THEN** the script runs every step

#### Scenario: Push failed, then relaunch
- **WHEN** `origin/main` is a strict ancestor of local `main` and `origin/main..main` is exactly the pure train of the listed branches
- **THEN** the script prints `reprise : main porte déjà le train`, redoes the admission, the scan on `origin/main..main` and the morning guard, runs no build, dbtest, runner or question, and pushes

#### Scenario: Train already pushed
- **WHEN** main and `origin/main` already carry the pure train and a branch worktree is left
- **THEN** the script prints `reprise : le train est déjà poussé ; reprise au nettoyage` and only cleans up and updates the run tree

#### Scenario: Branch already in origin/main
- **WHEN** local `main` equals `origin/main`, one listed branch is already contained in it and another is not
- **THEN** the script exits 62, refuses that branch with `déjà contenue dans origin/main` and prints the relaunch line without it

#### Scenario: Partly merged list on local main
- **WHEN** local `main` is ahead of `origin/main` and carries the merge of one listed branch but not of another
- **THEN** the script exits 79 with `reprise refusée` and nothing is touched

### Requirement: Purity of a train found on main
The system SHALL treat main as carrying the train only when each of its new first-parent commits has two parents (the expected first parent and the branch's tip), a tree equal to `merge-tree` of its parents, the exact message, only the standard headers and the author's identity (design D5). The system SHALL NOT resume from a chain that fails one of these. Untested until implemented.

#### Scenario: Foreign commit on main
- **WHEN** local `main` is ahead of `origin/main` by the train of the listed branches plus a foreign commit
- **THEN** the script exits 79 with `reprise refusée` and changes nothing

#### Scenario: Altered train commit
- **WHEN** a train commit on main has a third parent, a changed message, an extra header, another identity or a tree that is not `merge-tree` of its parents
- **THEN** the script exits 79

#### Scenario: Branch moved after the local merge
- **WHEN** main carries the train locally and a listed branch no longer points to the second parent of its merge
- **THEN** the script exits 79

#### Scenario: Branch already deleted after the push
- **WHEN** the train is pushed and a listed branch was already deleted by an earlier cleanup
- **THEN** the state is still accepted as already pushed

### Requirement: Log of each run
The system SHALL copy every printed line into one log file per run, named with a timestamp and no branch name, starting with the train line and holding the resumption line in a resumed run (design D16). The system SHALL NOT write into the log anything the terminal does not show. Untested until implemented.

#### Scenario: Resumption logged
- **WHEN** a run resumes at the push
- **THEN** its log holds the resumption line, naming the state and the steps redone and skipped, and the push outcome

#### Scenario: Log not writable
- **WHEN** the log file cannot be written
- **THEN** one line says so and the run continues

### Requirement: Exit codes and messages
The system SHALL use the exit codes of design D17 (0, 60 to 71, 73 to 76, 78 to 84, 129, 130, 141, 143; 72 and 77 reserved and never returned; range 60 to 81 since the author's decision Q of 2026-10-27, 82 added by change finish-e2e-proof-shared, design D11, 83 by change finish-single-b3-b6, design D19, and 84 by change autonomous-trains-merge, design D19) and the French key phrases of design D18 and of change autonomous-trains-merge design D19, each line starting with `finish_train : `. The system SHALL NOT print a stack trace or an exception text, nor give 84 any sense other than a refusal of the automatic policy. Untested until implemented.

#### Scenario: Unexpected error
- **WHEN** a Git command fails unexpectedly before main moves
- **THEN** the script exits 76 with `calcul impossible` and merges nothing

#### Scenario: Lab folders unresolved
- **WHEN** the lab folders cannot be resolved
- **THEN** the script exits 78 with the message of the lab-paths module

#### Scenario: No validating record for the train tree
- **WHEN** control 6 of the train tree refuses
- **THEN** the script exits 83, a code inside the declared range

#### Scenario: Policy refusal
- **WHEN** the automatic policy refuses
- **THEN** the script exits 84 and the closing banner reads `===== fin du train : code 84 (refusé), <AAAA-MM-JJ HH:MM:SS> Paris =====`

### Requirement: Interruption states what is left
On interruption (129, 130, 143), the system SHALL remove the integration worktree under the cleanup rules, release its lock and print the state left (design D17). The system SHALL NOT undo a fast-forward or a push on interruption. Untested until implemented.

#### Scenario: Interrupted after the fast-forward
- **WHEN** the author interrupts the script after main moved and before the push
- **THEN** the script exits 130 with `interrompu (code 130) : main avancé sur le train, push non fait : relancer la même ligne`

#### Scenario: Interrupted before the build
- **WHEN** the author interrupts the script before the train is built
- **THEN** the script exits 130 with `rien n'est fusionné`

### Requirement: Interruption written straight into the log
On INT, TERM, HUP or PIPE, the exit trap of `tools/finish_train.sh` SHALL append the interruption line, its code (130, 143, 129, 141) and the closing banner directly to the log file, then still try to print them on screen (design D23). The system SHALL NOT write these lines through a `tee` or any other process of the script's process group. Untested until implemented.

#### Scenario: Interrupted during the runner
- **WHEN** the author presses Ctrl-C while the runner runs, and the signal reaches the whole process group
- **THEN** the script exits 130, and its log ends with `interrompu (code 130) : rien n'est fusionné`, then `===== fin du train : code 130 (interrompu), <AAAA-MM-JJ HH:MM:SS> Paris =====`, then `===== arrêt à runner : rien n'est fusionné =====`

#### Scenario: No tee alive
- **WHEN** the process copying the output into the log is already gone when the trap runs
- **THEN** the interruption line and the closing banner are still in the log file

#### Scenario: Terminated
- **WHEN** the script receives TERM, or HUP, during a long command
- **THEN** it exits 143, or 129, and the log holds the interruption line with that code and the closing banner

### Requirement: SIGPIPE caught, never ignored for the whole script
The system SHALL catch SIGPIPE with a trap that ends the script with code 141, the interruption line and the banner sense `interrompu` (design D17, D23), and SHALL declare 141 in the exit-code register `tools/finish_codes.yaml`. The system SHALL NOT ignore SIGPIPE for its whole run, so that the processes it launches keep the default behaviour of SIGPIPE. Untested until implemented.

#### Scenario: Output pipe closed
- **WHEN** the reader of the script's output is closed during the runner
- **THEN** the script exits 141, and its log ends with `interrompu (code 141)`, then `===== fin du train : code 141 (interrompu), <AAAA-MM-JJ HH:MM:SS> Paris =====` and the second banner line

#### Scenario: Child keeps the default
- **WHEN** a process launched by the script writes into a pipe whose reader is gone
- **THEN** that process is ended by SIGPIPE, as with the default action

### Requirement: Closing banner on every exit
On every exit, the system SHALL append to the log, directly and never through the `tee`, `===== fin du train : code <n> (<sens>), <AAAA-MM-JJ HH:MM:SS> Paris =====`, with a sense of design D24 (`fusionné`, `refusé`, `interrompu`, `essai`) and the Europe/Paris time, then, when the code is not 0, `===== arrêt à <étape> : <état> =====` (D24). The system SHALL NOT write a second line for code 0, nor take the time from the process's zone. Untested until implemented.

#### Scenario: Merged
- **WHEN** a train finishes with code 0, with the process's time zone set to another zone than Paris
- **THEN** the log ends with `===== fin du train : code 0 (fusionné), <AAAA-MM-JJ HH:MM:SS> Paris =====` at the Paris time, and no second line follows

#### Scenario: Refused
- **WHEN** the Mac pass is red on the train tree and the replay of its red suites is red again
- **THEN** the script exits 70, and the log ends with `===== fin du train : code 70 (refusé), <AAAA-MM-JJ HH:MM:SS> Paris =====`, then `===== arrêt à passe Mac : rien n'est fusionné =====`

#### Scenario: Interrupted after the push
- **WHEN** the author interrupts the script during the cleanup, after the push
- **THEN** the script exits 130, and the log ends with `===== fin du train : code 130 (interrompu), <AAAA-MM-JJ HH:MM:SS> Paris =====`, then `===== arrêt à nettoyage : train poussé ; relancer la même commande pour reprendre au nettoyage =====`

#### Scenario: Trial
- **WHEN** the author runs the line with `--essai`, or answers `n` at the question
- **THEN** the script exits 0, and the log ends with `===== fin du train : code 0 (essai), <AAAA-MM-JJ HH:MM:SS> Paris =====` with no second line

### Requirement: Second banner line states the real state of the references
The second banner line SHALL name the state of the references at exit with the exact phrase of design D24 (E1 to E6): nothing done, `rien n'est fusionné`, train on local `main` not pushed, train pushed, local `main` moved off the tested train, or references in no known state. The system SHALL NOT write `rien n'est fusionné` when local `main` has moved or carries the train. Untested until implemented.

#### Scenario: Resumption at the push
- **WHEN** the push is refused after main moved onto the train, or a run resumed at the push is refused
- **THEN** the script exits with its code, and the last line of the log is `===== arrêt à <étape> : main local porte le train, rien n'est poussé ; relancer la même commande pour reprendre au push =====`

#### Scenario: Main unchanged
- **WHEN** a full run is refused before the fast-forward
- **THEN** the last line of the log is `===== arrêt à <étape> : rien n'est fusionné =====`, and local `main` is the one read at the start

#### Scenario: Local main moved before the reread
- **WHEN** local `main` is moved by another hand between the question and the reread of the references
- **THEN** the script exits 73, and the last line of the log is `===== arrêt à relecture des références : main local a bougé hors du train testé, rien n'est poussé ; examiner main avant de relancer =====`

#### Scenario: Launch refused at the state detection
- **WHEN** a run in state S1 is refused with code 61 because the run tree is detached elsewhere
- **THEN** the last line of the log is `===== arrêt à état des références : main local porte le train, rien n'est poussé ; relancer la même commande pour reprendre au push =====`

### Requirement: Test variables never bypass a refusal
The system SHALL accept `FINISH_TRAIN_RUNNER`, `FINISH_TRAIN_DBTEST`, `FINISH_TRAIN_MORNING_CHECK` and `FINISH_TRAIN_LOG_DIR` only as replacements of one command or folder, and print `commande de test posée : <VARIABLE>` for each command variable set (design D19). The system SHALL NOT let any of them bypass a refusal, and SHALL NOT record main when the runner is replaced. Untested until implemented.

#### Scenario: Runner replaced
- **WHEN** `FINISH_TRAIN_RUNNER` is set and the train finishes
- **THEN** the script prints `arbre de main non enregistré (runner remplacé)` and writes no main-validated line

#### Scenario: Morning guard replaced
- **WHEN** `FINISH_TRAIN_MORNING_CHECK` is set to a command that allows
- **THEN** the lock, the base, the admission, the scan, the purity check, the question and the push guard still apply

### Requirement: The script is protected tooling
The system SHALL add `tools/finish_train.sh` as a root of the protected-tooling closure, and cover the script and its suite with `juge` patterns of the protected list (design D20). The npm lock `mothra/package-lock.json` SHALL be exempted (E2, option (a) of 2026-10-27), and `tools/npm_lock_check.py` SHALL stay `juge`. The change SHALL NOT add or remove a deny rule, nor refuse a branch that changes only the lock. Test: `tests/finish_checks/test_closure.py`.

#### Scenario: Closure root
- **WHEN** the closure test runs on the tree of this change
- **THEN** `tools/finish_train.sh` is a root and every file it sources or launches is covered by the list, except the exempted npm lock

#### Scenario: Branch that changes only the lock
- **WHEN** a listed branch changes only `mothra/package-lock.json`
- **THEN** it is admitted to the train as an ordinary branch, and a branch that changes `tools/npm_lock_check.py` is counted as `juge` finish tooling: admitted alone, or beside other branches as one of at most 3 judge branches (R-20261102-43)

#### Scenario: Script changed beside other branches
- **WHEN** a branch that changes `tools/finish_train.sh` is listed with another branch
- **THEN** it is refused with `modifie le runner ou la preuve : train d'une seule branche (R-20261102-43)` and the train exits 62; listed alone, it is admitted

### Requirement: Mothra's root package files stay protected
The system SHALL keep `mothra/package.json` and `mothra/.node-version` in the `juge` protected tooling, and SHALL NOT protect the `package.json` of a subfolder of `mothra/` (author's decision (ii) of 2026-10-27, design D10). A branch that touches them SHALL be admitted only as finish tooling: alone, or beside other branches as one of at most 3 judge branches (finish-single-b3-b6 D18; R-20261102-43). The system SHALL NOT admit it as an ordinary branch. Untested until implemented.

#### Scenario: Root package.json and lock
- **WHEN** a branch listed with an ordinary branch changes `mothra/package.json` and `mothra/package-lock.json`
- **THEN** both are admitted, and `outillage de fin dans ce train de plusieurs branches (branche juge de rang <i> : <branche>) : <n> fichier(s)` and `mothra/package.json` are printed before the question

#### Scenario: Root package.json in a one-branch train
- **WHEN** the author lists only a branch that changes `mothra/package.json` and `mothra/package-lock.json`
- **THEN** the branch is admitted, and `outillage de fin dans ce train d'une branche : <n> fichier(s)` and `mothra/package.json` are printed before the question

#### Scenario: Front package.json and lock
- **WHEN** a listed branch changes only the `package.json` of a subfolder of `mothra/` and `mothra/package-lock.json`
- **THEN** it is admitted to the train

### Requirement: Shared stability rule in the train
The train SHALL judge the stability of the integration worktree after the runner through the stability module, keeping its phrases and code 71 (change finish-single-b3-b6, design D4, D6). The system SHALL NOT keep its own copy of the folder verdict, and SHALL NOT forgive an addition that Git does not ignore. Untested until implemented.

#### Scenario: Ignored additions only
- **WHEN** the runner is green and only created ignored files in the integration worktree
- **THEN** the train continues to the question

### Requirement: Cleaned process names in the train
The train SHALL list the processes in a worktree, at admission, after the runner and at cleanup, through the shared stability module, and SHALL name each by its number and its cleaned short command name (design D4, D6). The system SHALL NOT keep its own process listing, and SHALL NOT print the arguments or the full path of a process. Untested until implemented.

#### Scenario: Process with a forbidden character
- **WHEN** a process whose command name holds a character outside letters, digits and `._+ -` has its current folder in the integration worktree after the runner
- **THEN** the train exits 71 and names the process with the cleaned name

### Requirement: Shared ignored-files admission
The train SHALL count the ignored files that would be lost with a branch's worktree, at admission and before removing it, through the admission module (design D8). The system SHALL NOT keep a copy of that rule, SHALL NOT exempt a symbolic link or a tracked folder, and SHALL NOT print a file name. Untested until implemented.

#### Scenario: Ignored file outside the exemptions
- **WHEN** a listed branch's worktree holds an ignored file outside the exemptions
- **THEN** the branch is refused with `<n> fichier(s) ignoré(s) seraient perdus (dossiers : <liste>)` and the train exits 62

### Requirement: Sensitive tools admitted after a recorded review
The train SHALL admit a branch that touches only `sensible` protected files when the review record holds that branch with its exact tip, and print the admission with the paths before the question; otherwise it SHALL refuse the branch (design D11, D12, D23). The system SHALL NOT accept a line for another tip, SHALL NOT treat a missing record as a review, and SHALL NOT write the record. Untested until implemented.

#### Scenario: Sensitive tool reviewed
- **WHEN** a listed branch changes only a `sensible` file and the review record holds its exact tip
- **THEN** the branch is admitted and `outil sensible admis après revue Opus du sommet <sha12> : <branche>` is printed with the paths before the question

#### Scenario: Review for an older tip
- **WHEN** the review record holds the branch with a tip other than its current tip
- **THEN** the branch is refused with `outil sensible touché (<n> fichier(s)) sans revue Opus enregistrée pour le sommet <sha12> : revue ou fin unitaire` and the train exits 62

### Requirement: Protected classes read from the module only
The train SHALL read the protected classes of each branch from the finish checks module's output only, and SHALL refuse a branch whose output lacks them with `contrôles impossibles : classes de l'outillage protégé absentes de la sortie de finish_checks` (design D11). The system SHALL NOT read the protected-tooling list itself. Untested until implemented.

#### Scenario: Class fields missing
- **WHEN** the module's output for a branch lacks the class fields
- **THEN** the branch is refused with that phrase and the train exits 62

### Requirement: Control 6 decided on the train tree
The train SHALL NOT refuse a branch at admission for its control 6 verdict, and SHALL read control 6 of the train tree after control 14 and before the npm install; a refusal SHALL exit 83 with `jeu d'essai validant absent pour l'arbre du train ; rien n'est fusionné`, the module's details and the banner `===== arrêt à contrôle 6 : rien n'est fusionné =====` (design D19). The system SHALL NOT merge anything, nor run dbtest, the end-to-end pass or the runner, after 83. Untested until implemented.

#### Scenario: Instruction change with its record
- **WHEN** the train tree changes an evaluated file and a validating record carries the fingerprint computed on that tree
- **THEN** the train prints `jeu d'essai validant trouvé pour l'arbre du train : <détail>` and continues

#### Scenario: No record for the train tree
- **WHEN** the train tree changes an evaluated file and no record matches it
- **THEN** the train exits 83 and main is unchanged

### Requirement: Local main strictly behind is fast-forwarded
After the fetch and before detecting the reference state, the train SHALL fast-forward a local `main` that is a strict ancestor of `origin/main`, in the clean workspace on `main`; a failed fast-forward SHALL exit 63 (design D20, D23). The system SHALL NOT move a local `main` that is ahead or diverged, and SHALL NOT force or reset anything. Untested until implemented.

#### Scenario: Main behind
- **WHEN** local `main` is two commits behind `origin/main` and the workspace is clean
- **THEN** local `main` and the workspace files are moved to `origin/main`, `main local en retard avancé sur origin/main : <ancien12> -> <nouveau12>` is printed and the train continues

#### Scenario: Fast-forward fails
- **WHEN** the fast-forward of a local `main` strictly behind fails
- **THEN** the train exits 63 with `base non établie : avance rapide de main local en échec ; rien n'est fusionné`

#### Scenario: Main diverged
- **WHEN** local `main` holds a commit that `origin/main` does not have and no fusion of the list
- **THEN** the train exits 63 as before

### Requirement: Relay note removed after a merged train
After a code 0 with the sense `fusionné`, the train SHALL remove the relay note of each merged branch and print `note de relais retirée : <branche>` when one existed; a failed removal SHALL be a cause of code 75 with `note de relais non retirée : <branche>` (design D21). The system SHALL NOT remove a relay note after any other code, after a quick trial or after an answer other than `o`. Untested until implemented.

#### Scenario: Merged train
- **WHEN** a train of two branches ends merged and one of them has a relay note
- **THEN** that note is removed and the line names the branch

#### Scenario: Refused train
- **WHEN** a train ends with a code other than 0
- **THEN** every relay note of the listed branches is kept

### Requirement: The train's database proof comes from the CI run
The system SHALL take the database proof of the train tree from the base phase of its CI run, exiting 69 with `phase base du conteneur rouge sur l'arbre du train ; rien n'est fusionné` when that phase is red (change ci-local-runner, design D9). It SHALL NOT launch `tools/dbtest.sh`.

#### Scenario: Red base phase
- **WHEN** the CI run of the train tree reports its base phase red
- **THEN** the train exits 69 with that phrase and merges nothing

### Requirement: The train's end-to-end proof comes from the CI run
The system SHALL take the end-to-end proof of every train tree from the end-to-end phase of its CI run, and a red phase SHALL exit 82 with `phase de bout en bout du conteneur rouge sur l'arbre du train ; rien n'est fusionné` (change ci-local-runner, design D9). The system SHALL NOT launch `tools/dbtest.sh --e2e`, reuse a proof of another tree, pass a `DBTEST_` variable, or run the pass in the quick trial.

#### Scenario: Red end-to-end phase
- **WHEN** the CI run of the train tree reports its end-to-end phase red
- **THEN** the train exits 82 with that phrase and merges nothing

#### Scenario: Quick trial
- **WHEN** the author runs the train with `--essai`
- **THEN** no CI run and no end-to-end pass run

### Requirement: A green container needs its three green phase lines
The system SHALL hold the CI run green only when it exits 0 with the lines `ci_passage : phase portable : verte`, `ci_passage : phase base : verte` and `ci_passage : phase e2e : verte` and no red phase line, then print `porte du conteneur verte sur l'arbre du train` (design D9, Q226 (a), R-20261101-116). Otherwise, on exit 0, it SHALL exit 71 with `runner non concluant : conteneur non concluant ; rien n'est fusionné`. It SHALL NOT read a green from the exit code alone.

#### Scenario: Exit 0 without the end-to-end line
- **WHEN** the CI run exits 0 and its output holds the portable and base green lines but no `ci_passage : phase e2e : verte`
- **THEN** the train exits 71 with `runner non concluant : conteneur non concluant ; rien n'est fusionné` and merges nothing

### Requirement: An inconclusive container exit stops the train
The system SHALL exit 71 with `runner non concluant : conteneur indisponible (code <c>) ; rien n'est fusionné` on any CI exit code other than 0 and 1, and on code 1 without a recognised red phase line (design D9, Q215, Q170). It SHALL NOT fall back to another runner.

#### Scenario: Container unavailable
- **WHEN** the CI run of the train exits 3
- **THEN** the train exits 71 with that phrase and merges nothing

### Requirement: The train's gate carries no former substitution nor database variable
The system SHALL run the CI run through `FINISH_TRAIN_CI` (default `bash tools/ci_local.sh run`) and the Mac pass through `FINISH_TRAIN_RUNNER` (design D9, R-20261101-114). It SHALL NOT read `FINISH_TRAIN_DBTEST` or `FINISH_TRAIN_E2E`, nor pass a `PMZILLA_LAB_DB_*`, `DBTEST_*` or `CI_LOCAL_*` variable of the caller to either.

#### Scenario: Former substitutions set
- **WHEN** the train runs with `FINISH_TRAIN_DBTEST` and `FINISH_TRAIN_E2E` set to fake commands that record their calls
- **THEN** neither fake records a call

#### Scenario: Database variables of the caller
- **WHEN** the caller exports `PMZILLA_LAB_DB_PORT` and `DBTEST_PORT` with witness values and the train runs with recording fakes
- **THEN** neither the CI run nor the Mac pass sees those values

#### Scenario: Caller's CI variable
- **WHEN** the caller exports a `CI_LOCAL_*` variable with a witness value and the train runs with recording fakes
- **THEN** neither the CI run, nor its replay, nor the Mac pass sees that value

### Requirement: A substitution variable never makes a proof
The system SHALL write no `pmzilla-run-all-ok` fingerprint of the workspace and SHALL NOT record main as validated `complet` when `FINISH_TRAIN_CI` or `FINISH_TRAIN_RUNNER` is set (design D8, Q233 (a), R-20261101-118). It SHALL NOT let a substituted command stand for a proof of the tree.

#### Scenario: Substitution set at arrival
- **WHEN** a train merges with `FINISH_TRAIN_CI` set, or with `FINISH_TRAIN_RUNNER` set, each case run on its own
- **THEN** the workspace holds no `pmzilla-run-all-ok` fingerprint written by the train, main is not recorded as validated `complet`, and the train prints `arbre de main non enregistré (runner remplacé)`

### Requirement: A portable red without named suites is never replayed
The system SHALL exit 71 with `runner non concluant : phase portable du conteneur rouge sans suite nommée (<suites, ou aucune>) ; rien n'est fusionné` when the red portable line names no suite or starts with `code ` or `aucune ` (design D9). It SHALL NOT run a replay then.

#### Scenario: Red portable line without a suite
- **WHEN** the red portable line ends with `aucune ligne TOTAL du lanceur (code 2)`
- **THEN** the train exits 71 with that phrase and no replay runs

### Requirement: A suspicious suite name is refused before any replay
The system SHALL exit 71 with `runner non concluant : nom de suite refusé pour le rejeu ; rien n'est fusionné` when a red suite name of the portable phase or of the Mac pass does not match `[A-Za-z0-9_]+`, read under `LC_ALL=C` (design D9, Q230, Q236 (a), R-20261101-120). It SHALL NOT run either replay then, nor let through a dot or a hyphen.

#### Scenario: Suspicious suite name
- **WHEN** the red portable phase names a suite holding a `;`
- **THEN** the train exits 71 with that phrase and no replay runs

#### Scenario: Name with a dot or a hyphen
- **WHEN** the red portable phase names a suite holding a `.` or a `-`
- **THEN** the train exits 71 with `runner non concluant : nom de suite refusé pour le rejeu ; rien n'est fusionné` and no replay runs

#### Scenario: Mac pass names a suspicious suite
- **WHEN** the Mac pass is red and its `TOTAL` line names a suite holding a `-`
- **THEN** the train exits 71 with `runner non concluant : nom de suite refusé pour le rejeu ; rien n'est fusionné` and the Mac replay does not run

### Requirement: Only a conclusive red replay of the container gives 70
The system SHALL exit 70 after the container replay only when it exits 1 with a line `ci_local : rejeu rouge …`, and otherwise, on codes 2 to 7 or 1 without that line, SHALL exit 71 with `runner non concluant : rejeu du conteneur non concluant (code <c>) ; rien n'est fusionné` (design D9). It SHALL NOT read a red suite from the exit code alone.

#### Scenario: Replay red with its line
- **WHEN** the container replay exits 1 with a line `ci_local : rejeu rouge`
- **THEN** the train exits 70 with `train rouge : suites en échec : <suites> ; rien n'est fusionné`

#### Scenario: Replay exits 1 without its line
- **WHEN** the container replay exits 1 and prints no `ci_local : rejeu rouge` line
- **THEN** the train exits 71 with `runner non concluant : rejeu du conteneur non concluant (code 1) ; rien n'est fusionné`

#### Scenario: Replay refused in usage
- **WHEN** the container replay exits 2
- **THEN** the train exits 71 with `runner non concluant : rejeu du conteneur non concluant (code 2) ; rien n'est fusionné`, never 70

### Requirement: Controls 14 and 16 ask for the container's phases
The system SHALL keep the refusal 68 of controls 14 and 16 unchanged and SHALL word them `passage du conteneur requis (phase base)` (14) and `phase e2e du conteneur requise` (16) (change ci-local-runner, design D9, Q225 (a), R-20261101-116). It SHALL NOT launch dbtest for either control, nor change their code.

#### Scenario: Control 16 refuses
- **WHEN** control 16 refuses a branch
- **THEN** the train exits 68 and its line holds `phase e2e du conteneur requise`

### Requirement: The train's stability is read around the Mac pass
The system SHALL keep the marker, the worktree reading and the process list around the Mac pass, and SHALL hold the gate stable only when the train tree's line in the Mac record and its `portable,base,e2e` line in the CI proof file were both written after the marker, otherwise exiting 71 with `runner non concluant (code 0) : <raison> ; rien n'est fusionné` (design D9, Q219). It SHALL NOT accept a line written before the marker.

#### Scenario: Line written before the marker
- **WHEN** the Mac record line or the CI proof line of the train tree was written before the marker
- **THEN** the train exits 71 and merges nothing

### Requirement: Each part of the stability has its own reason
The system SHALL give, for the Mac part of the stability, main's reason `empreinte du runner absente, différente de l'arbre du train ou non réécrite`, and for the container part the reason `preuve du conteneur absente, différente de l'arbre du train, sans exactement portable,base,e2e ou non réécrite` (design D9, Q231 (a), R-20261101-118). It SHALL NOT give the Mac reason for a fault of the container proof.

#### Scenario: Proof line older than the marker
- **WHEN** the CI proof line of the train tree was written before the marker and the Mac record line after it
- **THEN** the train exits 71 with `runner non concluant (code 0) : preuve du conteneur absente, différente de l'arbre du train, sans exactement portable,base,e2e ou non réécrite ; rien n'est fusionné` and merges nothing

#### Scenario: Mac record not rewritten
- **WHEN** the Mac record holds no line of the train tree written after the marker
- **THEN** the train exits 71 with `runner non concluant (code 0) : empreinte du runner absente, différente de l'arbre du train ou non réécrite ; rien n'est fusionné` and merges nothing

### Requirement: The train is the only finishing script
The system SHALL finish every branch through `tools/finish_train.sh`, launched from the run tree; a `juge` branch SHALL finish alone or beside at most two `juge` branches on other files, alone if it changes the runner or the proof (D8; R-20261102-43, -55). The system SHALL NOT provide another finishing script (neither `tools/finish_branch.sh` nor `tools/finish_worktree.sh`), merge `main` into a work branch, or switch the workspace onto the branch. Untested until implemented.

#### Scenario: One ordinary branch
- **WHEN** the author finishes a single ordinary branch
- **THEN** the route is `bash tools/finish_train.sh <branche>` from the run tree, and the exit code is one of the train's

#### Scenario: The former scripts are gone
- **WHEN** the run tree is updated after the merge of B9
- **THEN** it holds neither `tools/finish_branch.sh` nor `tools/finish_worktree.sh`, and no tracked file other than the deny rules launches them

### Requirement: The train runs the complete runner on every train tree, without a light path or a CI mode
The system SHALL run the complete runner once on the train tree for every train, whatever paths the train changes (change finish-single-b7-b9, design D6, D8; framing questions Q4 and Q5). The system SHALL NOT replace the runner by the suites that read `openspec/`, SHALL NOT skip it because the tree of `main` was recorded as validated, SHALL NOT skip any step because a verdict of the local CI container already exists for a tree (the train launches the container gate itself on the train tree, then the Mac pass, and reads only the code and phase lines of that run and the proof lines of the train tree that the run writes), and SHALL NOT source `tools/light_finish.sh` or run `tools/light_validate.py`. Untested until implemented.

#### Scenario: A train that changes only OpenSpec files
- **WHEN** every branch of the train changes only files under `openspec/`
- **THEN** the train runs the complete runner on its tree, as for any other train

#### Scenario: A container verdict exists for the train tree
- **WHEN** the CI verdict file holds a green line for the train tree
- **THEN** the train skips no step because of it: it launches the container gate and the Mac pass on its tree and judges them by that run's own code, phase lines and proof lines

### Requirement: The exit-code register declares the train only
The system SHALL keep in `tools/finish_codes.yaml` the codes of `finish_train` only: 0, 60 to 83, and the signals 129, 130, 141 and 143, each with one sense (change finish-single-b7-b9, design D8). The system SHALL NOT keep an entry, a translation, a transmitted code or a share for `finish_branch` or `finish_worktree`, and SHALL NOT add a code to replace a removed one. Untested until implemented.

#### Scenario: Register after B9
- **WHEN** the register's test reads `tools/finish_codes.yaml` after the merge of B9
- **THEN** its `scripts` section names `finish_train` only, and it holds no section `traductions`, `transmis`, `controle_rendus` or `continue_au_controle`

#### Scenario: Former code cited
- **WHEN** a step file or a document cites code 42 of the former worktree finish
- **THEN** the register gives it no sense, and the train's code 67 is the one that says another finish holds the lock

### Requirement: Environment signature of the main-validation record
The system SHALL compute the record's signature with `tools/finish_env.sh --main-signature` (design D4): 64 lowercase hexadecimal characters digesting the versions of python3, uv, git and bash and the three lab folders, exit 0; or `absent:<component>`, exit 1. It SHALL NOT print a path or a version, write a file, or digest the code or hooks folder. Replaces the removed light module's signature; falls with "Main recorded as validated".

#### Scenario: Signature computed
- **WHEN** python3, uv, git and bash answer their version and the lab folders resolve
- **THEN** the option prints one line of 64 lowercase hexadecimal characters, no path and no version, and exits 0

#### Scenario: Tool missing
- **WHEN** uv is not found
- **THEN** the option prints `absent:uv` and exits 1, and a record line written by the train at that moment holds `inconnue`

#### Scenario: Lab folders unresolved
- **WHEN** the lab-paths module fails
- **THEN** the option prints `absent:dossiers-du-lab` and exits 1

Source: untested: no test asserts the option's output or its failures; `tests/hooks/test_pre_push.sh` calls it only to build its fixtures, and the line test of `tests/finish_train_fin/test_question_arrivee.py` accepts 64 hexadecimal characters or `inconnue` without telling which; the assertions left with the suites of the light module (B9); listed in `openspec/test-gaps.md` (task 2.1 of change tooling-specs-apres-b9). Among the tools, only `env_signature` of `tools/finish_env.sh` calls the option.

### Requirement: The automatic mode replaces the question by the policy
With `--auto`, the system SHALL, at the question point and after the gate and the summary, print `finish_train : mode automatique : la politique remplace la question` and run `finish_checks.py policy --json` on the train tip, the branches and their tips. It SHALL go on to the arrival exactly as after `o` only when the policy exits 0 with `"allowed": true`. On any other outcome it SHALL print one `finish_train : politique automatique refuse : …` line per reason, `contrôles de fin impossibles` for an exit 4 or an unreadable output, and exit 84 with the banner step `politique automatique`, merging nothing (change autonomous-trains-merge, design D7, D8). It SHALL NOT read standard input in `--auto`, skip or narrow the gate, the content scan, control 6 or the morning guard read again, nor admit an author's train (design D2), even alone.

#### Scenario: Policy allows
- **WHEN** a green train of two branches listed `faite` at their tips runs with `--auto` and a valid activation file
- **THEN** the train prints `finish_train : politique automatique : départ autorisé (2 branche(s))`, fast-forwards main and pushes

#### Scenario: Missing review
- **WHEN** a code branch's line at its tip is `non-requise` or absent
- **THEN** the train exits 84 with `revue Opus absente pour ce sommet` and main is unchanged

#### Scenario: Runner branch alone
- **WHEN** a one-branch train that changes `tests/run_all.sh` runs with `--auto`
- **THEN** it exits 84 with the author's-train label and merges nothing

#### Scenario: Policy cannot compute
- **WHEN** the policy command exits 4
- **THEN** the train exits 84 with `contrôles de fin impossibles` and merges nothing

### Requirement: The automatic mode is refused with the trial, from a terminal and on a resumption
The system SHALL exit 60 with `usage : --auto et --essai ne vont pas ensemble` when both options are given, 61 with `lancement refusé : --auto depuis un terminal ; le train de l'auteur garde la question` when `--auto` runs with standard input on a terminal, and 84 with `politique automatique refuse : état de reprise (<S1|S2>) ; train de l'auteur` when the state of the references is S1 or S2 (design D8). It SHALL NOT treat any environment variable as a reason to accept `--auto`, and SHALL NOT push in a resumption under `--auto`.

#### Scenario: From the author's Terminal
- **WHEN** the author runs `--auto` with standard input on a terminal
- **THEN** the train exits 61 with that phrase and changes nothing

#### Scenario: Resumption state
- **WHEN** local main already carries the train (S1) and `--auto` is given
- **THEN** the train exits 84 and pushes nothing

### Requirement: Every real run of the train is recorded without names
The system SHALL, through `tools/train_record.py` only, in its exit trap once the code and the sense are computed and before releasing the finish lock, remove the records older than one year and append one JSON line to the train record of design D4 for every run that took the finish lock and is not a quick trial. The line SHALL hold the fields of D4, with `runner` `remplace` whenever `FINISH_TRAIN_CI` or `FINISH_TRAIN_RUNNER` is set. It SHALL NOT hold a branch name, a person name or a ticket key, and no other tool SHALL write it. A failed write SHALL print `finish_train : journal des trains non écrit (écriture impossible)`, SHALL NOT change a refusal code, and SHALL add a cause of 75 only after a merge.

#### Scenario: Merged by the author
- **WHEN** the author's train of one branch exits 0 merged
- **THEN** the record gains one line with `mode` `manuel`, code 0, sense `fusionne` and the tip, and no branch name

#### Scenario: Quick trial
- **WHEN** the train runs with `--essai`
- **THEN** the record is unchanged

#### Scenario: Substituted gate
- **WHEN** a train runs with `FINISH_TRAIN_CI` set
- **THEN** its record line holds `runner` `remplace`

#### Scenario: Record and banner agree
- **WHEN** a fixture train ends with code 70
- **THEN** the record line holds code 70 and sense `refuse`, as the closing banner says

### Requirement: The train refuses a python3 older than 3.10
Before its first `python3` call and after the usage check, the system SHALL check that `python3` exists in PATH and is 3.10 or newer, and otherwise exit 76 with `calcul impossible (python3 3.10 ou plus introuvable) ; rien n'est fusionné` and the banner step `version de python3` (change train-auto-launchd-env, design D3). It SHALL NOT call another `python3` command, build or merge anything after that refusal.

#### Scenario: Python 3.9 first in PATH
- **WHEN** the first `python3` of PATH reports 3.9
- **THEN** the train exits 76 with that phrase, the banner reads `===== arrêt à version de python3 : rien n'est fusionné =====`, and no other `python3` command ran

#### Scenario: No python3
- **WHEN** PATH holds no `python3`
- **THEN** the train exits 76 with the same phrase

#### Scenario: launchd's default PATH
- **WHEN** the train runs with launchd's default PATH on a machine whose system `python3` is older than 3.10
- **THEN** it exits 76; on a machine whose system `python3` is 3.10 or newer, the test is skipped and prints its reason
