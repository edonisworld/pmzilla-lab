# tooling-local-ci Specification

## Purpose
Run the portable test suites on one commit's tree in a throwaway, pinned container, isolated from the network and the caller's secrets and under the finish lock, and record a readable verdict per tested tree that one command reproduces on the Mac.

## Requirements

### Requirement: The CI script runs the portable suites in a throwaway container
The system SHALL provide `tools/ci_local.sh` whose `run [<branche>]` runs `bash tests/run_all.sh --portable` in a throwaway container from the CI image, on the tree of one commit, exiting 0 when green and 1 when red (local-ci-container design D1, D2). It SHALL NOT test uncommitted changes nor run a targeted run, except in the `--index` and `--travail` modes of design D4 of change tooling-proof-in-container.

#### Scenario: Green run
- **WHEN** the fake Docker command makes the runner exit 0
- **THEN** the script exits 0 and its last line starts with `ci_local : verdict vert (arbre`

#### Scenario: Red run
- **WHEN** the fake Docker command makes the runner exit 1
- **THEN** the script exits 1 and its last line starts with `ci_local : verdict rouge (arbre`

### Requirement: The CI script refuses before starting any container
The system SHALL exit 2 on usage, 3 when Docker or Colima does not answer, 4 outside the repository, for an unknown branch or an unclean tree, 5 for a missing or stale image or npm lock, 6 on a failed build, each with its phrase of design D2 of change local-ci-container, the phrase of code 5 for the CI image being `ci_local : image absente ou périmée pour cet arbre (lancer : cd <worktree> && bash tools/ci_local.sh up)` (change ci-local-runner, design D11, R-20261101-116). `<worktree>` SHALL be the worktree that holds the tested branch, read in `git worktree list` (the current checkout when `run` names no branch); when that branch has no worktree, the phrase SHALL give the command that creates one first, in the form of design D11 (Q229 (a), R-20261101-118). It SHALL NOT start a container after these codes, leave a tagged image after 6, build an image itself on a code 5, nor name a worktree that does not hold the tested branch.

#### Scenario: Unclean tree
- **WHEN** `run` gets no branch and the checkout holds an untracked non-ignored file
- **THEN** the script exits 4 with `ci_local : arbre non propre ; rien n'est lancé` and the fake Docker records no run

#### Scenario: Image out of date
- **WHEN** `ci/Dockerfile` changed since the image was built
- **THEN** `run` exits 5 with `ci_local : image absente ou périmée pour cet arbre (lancer : cd <worktree> && bash tools/ci_local.sh up)`, `<worktree>` filled, and the fake Docker records no build

#### Scenario: Stale image for a branch held by another worktree
- **WHEN** `run <branche>` is launched from a checkout that does not hold that branch, the branch has its own worktree, and its image is missing
- **THEN** `run` exits 5 and `<worktree>` in the phrase is the branch's worktree, not the current checkout

#### Scenario: Stale image on a detached HEAD
- **WHEN** `run` is launched without a branch from a checkout on a detached `HEAD`, as the train's integration worktree, and the image is missing
- **THEN** `run` exits 5, the phrase gives `cd <worktree principal> && bash tools/ci_local.sh up` with the first worktree of `git worktree list` (Q237 (a), R-20261101-120), followed by the line `si une branche du train change la clé (ci/Dockerfile, verrou npm, bloc # /// script, engines.npm), construire l'image depuis le worktree de cette branche`, and no branch is named

#### Scenario: Stale image for a branch without a worktree
- **WHEN** `run <branche>` is launched for a branch that no worktree holds and its image is missing
- **THEN** `run` exits 5 and the phrase gives the `git worktree add` command for that branch before `cd` and `bash tools/ci_local.sh up`

### Requirement: The CI script honours the finish lock
The system SHALL, when a live finish lock holds another token or no token is set, refuse `build` and `up` with code 7 and `ci_local : fin de branche en cours (<branche>), lancement refusé`, and refuse `run` with the same code and phrase only when the targeted freeze of change autonomous-trains-merge (design D18, through `freeze_scope()`) covers it: the current worktree is in the lock's list, or the lock holds no readable list. Any other `run` SHALL wait in the queue behind the train's pass instead of exiting 7 (design D18 point 4). The script SHALL say and ignore a stale lock, and run normally with the matching `FINISH_LOCK_TOKEN` (design D2). It SHALL NOT create, remove or change the lock, nor keep a freeze rule of its own for `run` beside `freeze_scope()`.

#### Scenario: Lock of another finish
- **WHEN** a live lock holds a token different from the caller's and lists the current worktree
- **THEN** `run` exits 7 and the fake Docker records nothing

#### Scenario: Run from a worktree outside the train
- **WHEN** a live lock holds a token different from the caller's and lists other worktrees than the current one
- **THEN** `run` does not exit 7, waits in the queue behind the train's pass, and starts once a place is free

#### Scenario: Build or up during a train
- **WHEN** a live lock holds a token different from the caller's, whatever worktree it lists
- **THEN** `build` and `up` exit 7 and the fake Docker records nothing

#### Scenario: Finish's own token
- **WHEN** the caller carries the lock's token
- **THEN** the run starts as without a lock

### Requirement: The CI image is pinned and keyed
The system SHALL build the image from the official Node 26 slim image and uv, both pinned by digest, Python from `.python-version` and the pinned OpenSpec CLI, with the runner's dependencies resolved at build, and tag it with a key hashing its definition, pins, dependency set and declared npm locks (design D4). It SHALL NOT carry a secret or an unpinned base.

#### Scenario: Key follows the dependency set
- **WHEN** the runner's dependency set changes in the tested tree
- **THEN** the computed key differs from the image's and `run` exits 5

### Requirement: The CI run copies one commit's tree and nothing else
The system SHALL stream into the container an archive of the tree of the named branch's tip, of a clean `HEAD`, or, in the modes of design D4 of change tooling-proof-in-container, of the index or the working tree, recommitted in a throwaway repository inside the container (design D5). It SHALL NOT bind-mount the workspace, a worktree, the home folder or a lab folder, nor bring in an ignored file, nor an untracked file outside `--travail`.

#### Scenario: Ignored file absent
- **WHEN** the checkout holds an ignored local file and `run` gets its branch
- **THEN** the archive sent to the container does not hold that file

#### Scenario: Named branch
- **WHEN** `run` gets a branch whose tip differs from `HEAD`
- **THEN** the tested tree is the tree of that tip

#### Scenario: Untracked file in index mode
- **WHEN** `run --index a` runs while the checkout holds an untracked non-ignored file
- **THEN** the archive does not hold that file

### Requirement: The CI run is isolated from the network and the caller's secrets
The system SHALL run both containers of a run without network exit (design D1), as a non-root user for the suites container, with random names, an environment built by the script with `UV_OFFLINE=1`, and SHALL remove both at the end, on failure and on interruption (design D1). It SHALL NOT pass any caller variable, database variable, `DBTEST_PORT`, token or lock token, nor mount the Docker socket; the only database variables inside are those the run sets for its own base (design D2).

#### Scenario: Recorded arguments
- **WHEN** the caller exports a database variable, `DBTEST_PORT`, a fake token and a lock token, and `run` starts with the fake Docker command
- **THEN** the recorded arguments hold no mount and none of those values, and neither container has a network with an exit

#### Scenario: Interruption
- **WHEN** the run is interrupted
- **THEN** the fake Docker command records the removal of both containers

### Requirement: The CI run gives a readable verdict and a report
The system SHALL end every run that started a container with the verdict line of design D7, naming the tree, the image key and the counts or failed suites, and SHALL write a report in the lab data folder with the tree, key, date, runner lines and code. It SHALL NOT write a path, a branch name or a person in the report, nor change the code when the report fails.

#### Scenario: Report written
- **WHEN** a run is green
- **THEN** the fake data folder holds a report with the tree, the key and the `TOTAL` line, and no path or branch name

#### Scenario: Report impossible
- **WHEN** the data folder cannot be written
- **THEN** one line says so and the exit code is the runner's

### Requirement: The CI run records its verdict for the tested tree
The system SHALL keep, in the `verdicts` file of the lab data folder's `ci` folder, outside any `.git` folder, one line per tree (tree id, `vert` or `rouge`, image key) in its three-field format; `run` SHALL remove the tested tree's line before the containers start and write it once the run gave a verdict, with the phrases of design D7b of change local-ci-container, and SHALL write no line for a replay. It SHALL NOT write a branch, path, date or person, change another tree's line, leave a line after an interruption or codes 2 to 7, or change its exit code when the write fails.

#### Scenario: Green verdict recorded
- **WHEN** a run on a branch tip is green with a fake verdict file holding a line for another tree
- **THEN** the file holds a `vert` line for the tested tree with the image key, and the other line unchanged

#### Scenario: Red run replaces a green line
- **WHEN** the file holds a `vert` line for the tested tree and the new run is red
- **THEN** the file holds a `rouge` line for that tree and no `vert` line for it

#### Scenario: Interrupted run
- **WHEN** a run is interrupted after the containers started
- **THEN** the file holds no line for the tested tree

#### Scenario: Unwritable verdict file
- **WHEN** the verdict file cannot be written and the run is green
- **THEN** `ci_local : verdict non enregistré (écriture impossible)` is printed and the script exits 0

### Requirement: Tests of the CI script never touch the real verdict file
The system SHALL read and write the verdict file named by `CI_LOCAL_VERDICTS` when it is set, and SHALL write it through a renamed temporary file readable by its owner only (design D7b). It SHALL NOT read or write any verdict file when `CI_LOCAL_DOCKER` is set without `CI_LOCAL_VERDICTS`.

#### Scenario: Fake Docker without a verdict file
- **WHEN** `run` is green with `CI_LOCAL_DOCKER` set and `CI_LOCAL_VERDICTS` unset
- **THEN** no verdict file is created or changed and the script exits 0

### Requirement: One command reproduces the local CI on the Mac
The system SHALL provide `bash tools/ci_local.sh up [<branche>]`, default `main`, which starts Colima only when it does not answer, builds the image only when no image has the key of the branch's tip, then runs `run` on it and exits with its code (design D9). It SHALL NOT delete a Colima instance, a volume or an image other than the CI images it replaces.

#### Scenario: Everything ready
- **WHEN** Colima answers and an image has the key of the tip of `main`
- **THEN** `up` records no Colima start and no build, and runs the container once

#### Scenario: Stale image
- **WHEN** the key of the tip of `main` has no image
- **THEN** `up` builds it before the run

### Requirement: The CI image prepares the dependencies of every declared npm lock
The system SHALL install at build, with `npm ci`, the dependencies of every npm lock the runner declares, and SHALL exit 5 with the npm phrase of design D2 when a tested lock differs from the baked one (design D10). It SHALL NOT install or fetch an npm package during a run, nor run `npx`.

#### Scenario: Lock changed
- **WHEN** a declared lock of the tested tree differs from the one in the image
- **THEN** `run` exits 5 with the npm phrase and starts no container

#### Scenario: No declared lock
- **WHEN** the runner declares no npm lock
- **THEN** the build adds no npm layer and `run` checks no lock

### Requirement: The CI script is testable without Docker
The system SHALL include the shell suite `tests/ci_local`, listed in the runner, that exercises the script with fake Docker and Colima commands, temporary repositories and a fake data folder (design D14). It SHALL NOT build a real image, start a real container, or write into the real data folder or Git folder.

#### Scenario: Suite run
- **WHEN** the runner runs the CI suite
- **THEN** every case runs in a temporary folder and the suite reports its counts in the runner's shell format

### Requirement: A CI run tests the database suites on its own throwaway database
The system SHALL start, for each CI run, a throwaway ParadeDB container from the image pinned in the `docker-compose.yml` of the tree the run proves (the commit, index tree or work tree whose archive is sent to the suites container), read through Git, with its data in memory, a random password and PostgreSQL on port 55432, and SHALL run the database phase against it (design D1, D2; change ci-local-base-image-from-tree, design D1, R-20261106-68). It SHALL exit 4 with `ci_local : image de la base introuvable (docker-compose.yml) ; rien n'est lancé`, before any container, when that tree holds no `docker-compose.yml` or no readable `image:` line. It SHALL NOT read the image from the `docker-compose.yml` of the repository that holds the running script, fall back to it, reuse a database between runs, publish a port, write the password to the output, an argument or a kept file, nor pass a `PMZILLA_LAB_DB_*` variable of the caller.

#### Scenario: Base started without a published port
- **WHEN** a run starts with the fake Docker command
- **THEN** the recorded arguments of the base container hold `--network none`, a tmpfs, `--shm-size 1g` and no `-p`, and no recorded argument holds the password

#### Scenario: Base removed with the run
- **WHEN** the run ends green, red or by an interruption
- **THEN** the fake Docker command records the removal of the suites container and then of the base container

#### Scenario: Branch that changes the database image tag
- **WHEN** the tool's repository compose names one ParadeDB tag, the proved tree's compose names another, and both images are known to the fake Docker
- **THEN** the base container is created from the proved tree's tag and never from the tool repository's

#### Scenario: Named branch from another checkout
- **WHEN** `run <branche>` is launched from a checkout whose compose differs from the branch tip's
- **THEN** the base container is created from the tag of the branch tip's compose

#### Scenario: Compose absent from the proved tree
- **WHEN** the proved tree holds no `docker-compose.yml`
- **THEN** `run` exits 4 with `ci_local : image de la base introuvable (docker-compose.yml) ; rien n'est lancé` and the fake Docker records no `create` and no `run`

#### Scenario: Tree image absent while the tool's image is present
- **WHEN** the proved tree's image is unknown to the fake Docker and the tool repository's image is known
- **THEN** `run` exits 5 with `ci_local : image de la base absente (à tirer par l'auteur)` and records no container

### Requirement: The containers of a run cannot reach any network
The system SHALL start the suites container of a run in the network namespace of its base container (`--network container:<base>`), the base having no network (design D1). It SHALL NOT create a Docker network, attach either container to a network with an exit, mount the Docker socket, or let either container reach the real database.

#### Scenario: Shared loopback only
- **WHEN** the recorded arguments of a run are read
- **THEN** the suites container has `--network container:` followed by the base's name, and no `docker network create` is recorded

### Requirement: A run has three phases and one verdict
The system SHALL run in the container, through `ci/passage.sh`, the portable phase, then the database phase on the default list of `tools/dbtest.sh` minus the Mac-bound suites, then the end-to-end phase, each after the previous one ends green, with the key phrases of design D2, and SHALL give a green verdict only when every phase of the run is green. It SHALL NOT start a phase after a red one, nor keep a second copy of the default list.

#### Scenario: Red base phase
- **WHEN** the base answers no connection within 120 s
- **THEN** the run prints `ci_passage : base du conteneur injoignable au bout de 120 s`, marks the end-to-end phase `sautée` and its verdict is red

#### Scenario: Mac-bound database suite
- **WHEN** a suite of the default list is in `tests/suites_mac.txt`
- **THEN** the database phase does not run it and names it in its line of suites not run

### Requirement: The end-to-end phase runs the shared steps
The system SHALL run the end-to-end phase with the step functions of `tools/e2e_steps.sh`, the copy `tools/dbtest.sh` also sources, and SHALL give the suites container `--shm-size 1g` (design D2, R-20261101-113). It SHALL NOT keep a second copy of the steps, pass a `PMZILLA_LAB_DB_*` variable to the pass, or download a browser.

#### Scenario: Shared memory of the suites container
- **WHEN** the recorded arguments of a run are read
- **THEN** the suites container has `--shm-size 1g`

#### Scenario: Steps absent from the inner text
- **WHEN** a test runs `ci/passage.sh` alone, without the step functions
- **THEN** the output holds `ci_passage : phase e2e : non lancée (étapes de bout en bout absentes du script intérieur)` and no `phase e2e : verte` line

### Requirement: The role passwords of the end-to-end phase never pass through the shell
The system SHALL set the passwords of the view and storage roles in the container through psycopg, the SQL and the secret on standard input (design D2, Q209 (a)). It SHALL NOT put a password in an argument, let the shell expand it, or add a psql client to the image.

#### Scenario: Recorded arguments of the SQL step
- **WHEN** the end-to-end phase sets the role passwords with a witness password
- **THEN** no recorded argument holds the witness value

### Requirement: A red end-to-end phase names its cause
The system SHALL print, for a failed step, one line `ci_passage : phase e2e : rouge · <durée> s : <cause>` with a cause of design D2, and exit 1 (Q211). It SHALL NOT mark the phase `sautée` when the browser is missing (Q210 (a)).

#### Scenario: Build fails
- **WHEN** the fake build of the bundle exits non-zero in the end-to-end phase
- **THEN** the output holds `ci_passage : phase e2e : rouge · <durée> s : construction du bundle` and passage exits 1

#### Scenario: Browser missing from the image
- **WHEN** the end-to-end phase runs in an image without the Playwright browser
- **THEN** the output holds `ci_passage : navigateur absent de l'image (rebaser sur main ou reconstruire l'image)` and a red e2e line with the cause `navigateur absent`, and no proof is written

### Requirement: The inner text comes from the tool's repository
The system SHALL build the inner text launched in the container from `tools/e2e_steps.sh` followed by `ci/passage.sh`, both read from the repository that holds the running `tools/ci_local.sh`, and SHALL exit 4 with `ci_local : script intérieur introuvable (<fichier>) ; rien n'est lancé` before any container when either is missing (design D2, R-20261101-113). It SHALL NOT read either file from the tested tree.

#### Scenario: Steps file missing
- **WHEN** the tool's repository holds no `tools/e2e_steps.sh`
- **THEN** `run` exits 4 with `ci_local : script intérieur introuvable (tools/e2e_steps.sh) ; rien n'est lancé` and the fake Docker records no run

#### Scenario: Tested tree carries another copy
- **WHEN** the tested tree holds a `tools/e2e_steps.sh` that differs from the tool's
- **THEN** the inner text holds the tool's copy

### Requirement: A replay runs only the named portable suites
The system SHALL provide `bash tools/ci_local.sh run --rejeu portable <suite> [<suite> ...]`, which waits in the queue like a run, runs `bash tests/run_all.sh` with the named suites as arguments, starts no base, and exits 2 with `ci_local : usage : bash tools/ci_local.sh run [<branche>] | build | up` on a missing or other phase word, no suite or a refused name (design D9). It SHALL NOT run the base or end-to-end phase, interpolate a name, or write a report, verdict or proof.

#### Scenario: Replay of two suites
- **WHEN** `run --rejeu portable a b` runs with the fake Docker command and fake data files
- **THEN** one container runs the runner with `a` and `b` as arguments, no base container is recorded, and the report, verdict and proof files are unchanged

#### Scenario: Wrong phase word
- **WHEN** `run --rejeu base a` runs
- **THEN** the script exits 2 with the usage phrase and the fake Docker records nothing

### Requirement: A replayed suite name matches the train's set
The system SHALL accept in `run --rejeu portable` only names matching `[A-Za-z0-9_]+`, the set of the train's check (design D9, Q230, R-20261101-118), and SHALL exit 2 with the usage phrase otherwise. It SHALL NOT accept a dot, a hyphen or any other character.

#### Scenario: Name with a hyphen
- **WHEN** `run --rejeu portable a-b` runs
- **THEN** the script exits 2 with the usage phrase and the fake Docker records nothing

### Requirement: The inner script refuses outside the container
The system SHALL make `ci/passage.sh` exit 2 with `ci_passage : réservé au conteneur de la CI locale, rien n'est lancé` when the system is macOS (design D2). It SHALL NOT be lifted by any environment variable.

#### Scenario: Launched on the Mac
- **WHEN** `bash ci/passage.sh` is run with a fake `uname` that prints `Darwin`
- **THEN** it exits 2 with that phrase and runs no suite

### Requirement: Runs beyond the number of places wait in a queue
The system SHALL let at most N runs hold a place at once, N given by the service function of design D3, and SHALL make any other run wait in a queue, printing its position, until a place is free. It SHALL NOT refuse a run for lack of place, exit 8, or wait for a place held by a dead process. A run carrying the token of the live finish lock SHALL get the first ticket, never a held place.

#### Scenario: Third run with two places
- **WHEN** two runs hold the two places and a third starts
- **THEN** the third prints `ci_local : en file (position 1, 2 passage(s) en cours sur 2 places)` and starts once a place is freed

#### Scenario: Dead holder
- **WHEN** a place holds the pid of a dead process
- **THEN** the next run takes it without waiting

#### Scenario: Interrupted wait
- **WHEN** a waiting run is interrupted
- **THEN** its ticket is removed and no container is started

### Requirement: The number of places is computed by one service function
The system SHALL compute N in one function from the CPU count and memory reported by the Docker engine and the run's limits (design D3), and SHALL expose it with `bash tools/ci_local.sh places --json`, the text form only formatting that output. It SHALL NOT start a container, write a file or compute N elsewhere.

#### Scenario: Places listed
- **WHEN** `places --json` runs with a fake engine of 8 CPUs and 16 GiB
- **THEN** the JSON gives N 2, the inputs, the places held and the queue length

### Requirement: Places are typed and pinned to disjoint processors
The function of N SHALL allocate the places from a budget, a proof place or a targeted place without base, each with the processors and memory of design D5 of change tooling-proof-in-container and a `--cpuset-cpus` set disjoint from the other held places, read from the Docker engine; `places --json` SHALL give each place's type, processors and memory. It SHALL NOT give the train's token a held place. Typed places replace the uniform places of ci-local-runner D3.
Source: tests/ci_local/test_ci_local.sh (block "6.6 : places typées")

#### Scenario: Two proofs on eight processors
- **WHEN** `places --json` runs with a fake engine of 8 processors and two proof places are held
- **THEN** the two places have disjoint processor sets and no targeted place is free

#### Scenario: One proof and two targeted runs
- **WHEN** one proof place is held on a fake engine of 8 processors and two targeted runs start
- **THEN** both get a targeted place, with processor sets disjoint from the proof's and from each other

### Requirement: The report records phases, memory and wait
The system SHALL add to each run's report the verdict and duration of each phase, the peak memory of the suites container or `non lue`, the places line and the wait in queue (design D5). It SHALL NOT write a path, a branch name or a person.

#### Scenario: Memory not readable
- **WHEN** the container has no readable `memory.peak`
- **THEN** the report holds `mémoire au plus : non lue` and the exit code is unchanged

### Requirement: A fully green run records a proof of its tree
The system SHALL write the line `<arbre>\t<clé>\t<phases>` of design D6, one per tree, to the `ci/preuves` file of the lab data folder, only when `<phases>` is exactly `portable,base,e2e`, under the verdicts' write rules, with the proof phrase of D6 (R-20261101-113). It SHALL NOT write a proof for a run without a green end-to-end phase, a red, interrupted or replayed run, nor keep two lines for one tree.

#### Scenario: Green on two phases only
- **WHEN** a run is green on the portable and database phases and has no end-to-end phase
- **THEN** no proof line is written for its tree

#### Scenario: Green on three phases
- **WHEN** a run is green on its three phases with `CI_LOCAL_PREUVES` set on a fake file holding a line for another tree
- **THEN** the file holds one line for the tested tree whose third field is `portable,base,e2e`, and the other line unchanged

### Requirement: Tests of the CI script never touch the real proof file
The system SHALL read and write the proof file named by `CI_LOCAL_PREUVES` when it is set (design D6, Q213, R-20261101-116). It SHALL NOT read or write any proof file when `CI_LOCAL_DOCKER` is set without `CI_LOCAL_PREUVES`.

#### Scenario: Fake Docker without a proof file
- **WHEN** a run is green on its three phases with `CI_LOCAL_DOCKER` set and `CI_LOCAL_PREUVES` unset
- **THEN** no proof file is created or changed

### Requirement: A missing database image stops the run before any container
The system SHALL exit 5 with `ci_local : image de la base absente (à tirer par l'auteur)` when the pinned ParadeDB image is not present, before any container (design D11). It SHALL NOT pull an image.

#### Scenario: ParadeDB absent
- **WHEN** the fake Docker command does not know the ParadeDB image
- **THEN** `run` exits 5 with that phrase and records no `run`

### Requirement: Up removes the CI images of closed trees after a new build
The system SHALL, in `bash tools/ci_local.sh up` and only after it built a new image, remove every `pmzilla-ci` image whose key is the key of no open tree: a local branch (`main` included), the `HEAD` of a worktree (detached ones included) or the key just built (design D1, D2; R-20261106-55). It SHALL NOT clean up when the image of the key already exists, clean up in `build`, nor change the exit code of `up`. Removal condition: design D8.

#### Scenario: Image of a closed branch
- **WHEN** `up` builds a new image and the fake Docker also holds an image whose key matches no local branch and no worktree
- **THEN** that image is removed and `up` goes on to the run

#### Scenario: Images of open trees kept
- **WHEN** `up` builds a new image and the fake Docker holds the images of `main`, of another local branch and of a detached worktree
- **THEN** none of them is removed

#### Scenario: Image up to date
- **WHEN** `up` finds the image of the key already present
- **THEN** no image is removed

### Requirement: The image clean-up lists each image by its key
The system SHALL print one line per removed image and one line per image that Docker refuses to remove, each naming the image's short key, then a summary line, with the phrases of design D7. It SHALL NOT print a branch name.

#### Scenario: Removed image listed
- **WHEN** the clean-up removes a stale image
- **THEN** `ci_local : image supprimée (clé <clé courte>)` is printed, then `ci_local : nettoyage des images : <n> supprimée(s), <m> gardée(s)`

#### Scenario: Image in use
- **WHEN** the fake Docker refuses to remove a stale image because a container uses it
- **THEN** the image is kept and `ci_local : image gardée (clé <clé courte>) : suppression refusée par Docker` is printed

### Requirement: The image clean-up touches only CI images
The system SHALL list and remove only tags of the `pmzilla-ci` repository, one by one and without forcing (design D2). It SHALL NOT list or remove an image of another repository (the ParadeDB image included), a volume or a container, nor issue a prune command.

#### Scenario: Nothing outside the CI repository
- **WHEN** the clean-up runs
- **THEN** the fake Docker journal holds no removal of an image of another repository, no `--force`, and no prune, volume or container command

### Requirement: The image clean-up abstains during a proof or under the finish lock
The system SHALL keep every image and print `ci_local : images non nettoyées (<raison>)` with the reasons of design D3 when the finish lock is held and not stale, whatever the caller's token, or when a place is held or a ticket of the queue belongs to a live process. It SHALL hold the places lock from that check to the last removal. It SHALL NOT detect a proof otherwise than the run's places and queue do.

#### Scenario: Proof running
- **WHEN** `up` builds a new image while a place of the data folder is held by a live process
- **THEN** no image is removed and `ci_local : images non nettoyées (preuve en cours)` is printed

#### Scenario: Finish lock held with the caller's token
- **WHEN** `up` runs with the token of a live finish lock and builds a new image
- **THEN** no image is removed and `ci_local : images non nettoyées (verrou de fin tenu)` is printed

### Requirement: The image clean-up keeps every image on a doubt
The system SHALL keep every image and print `ci_local : images non nettoyées (<raison>)` when the data folder is not found, the places lock cannot be taken, the key of an open tree cannot be computed or the image listing fails (design D1 to D3, D7), and SHALL keep any image whose tag is not a well-formed key. It SHALL NOT remove an image it cannot match with certainty.

#### Scenario: Key in doubt
- **WHEN** the commit of a local branch cannot be read
- **THEN** every image is kept and `ci_local : images non nettoyées (clé d'une branche non calculée)` is printed

#### Scenario: Malformed tag
- **WHEN** the fake Docker lists a `pmzilla-ci` image with a `<none>` tag
- **THEN** that image is kept

### Requirement: Run refuses when the Colima machine lacks free space
The system SHALL measure the free space of the Docker data root of the Colima machine in every form of `run` and in `up`, after the Docker check and before the image check, and SHALL exit 8 with the phrase of design D7 on standard error when it is below the fixed minimum of design D4 (R-20261106-55). It SHALL NOT start a container, take a place or a ticket, or write a verdict, proof or report after code 8, nor let a variable change the minimum.

#### Scenario: Below the minimum
- **WHEN** the fake Colima reports a free space below the minimum and `run` is launched
- **THEN** the script exits 8 with `ci_local : place libre insuffisante dans la machine Colima (<x> Gio libres, minimum <m> Gio) ; rien n'est lancé (nettoyage : docker image ls pmzilla-ci, puis docker image rm pmzilla-ci:<clé> pour chaque clé sans branche ouverte)` on standard error, and the fake Docker journal holds no `create` and no `run`

#### Scenario: Targeted forms refused too
- **WHEN** the free space is below the minimum and `run --index <suite>` or `run --rejeu portable <suite>` is launched
- **THEN** the script exits 8 and no container starts

#### Scenario: At the minimum
- **WHEN** the fake Colima reports exactly the minimum
- **THEN** the run starts

#### Scenario: Docker check first
- **WHEN** Docker does not answer
- **THEN** the script exits 3 and the fake Colima journal holds no `ssh`

### Requirement: The free-space measure goes through Colima without network
The system SHALL measure the free space with `colima ssh` and `df`, and SHALL print `ci_local : place libre de la machine Colima non mesurée ; passage sans ce contrôle` and go on when the measure fails (design D4, D5). It SHALL NOT start a container, pull an image or use the network to measure.

#### Scenario: Measure failed
- **WHEN** the fake Colima `ssh` fails
- **THEN** `ci_local : place libre de la machine Colima non mesurée ; passage sans ce contrôle` is printed and the run starts

### Requirement: The CI script tests the index or the working tree of a session run
The system SHALL give `run` the modes `--index` (tree of `git write-tree`) and `--travail` (working tree through a temporary index, untracked non-ignored files included), followed by suite names matching `[A-Za-z0-9_]+`, and SHALL exit 2 when a branch is also named or a name does not match (design D4, D8). The tool computes the tree itself. It SHALL NOT write a reference or the real index, nor accept a tree from its caller.
Source: untested until implemented (T2, suite ci_local)

#### Scenario: Index mode
- **WHEN** `run --index a` runs with the fake Docker command while the index differs from `HEAD`
- **THEN** the archive sent to the container holds the tree of the index, and the container runs the runner with `a` as argument

#### Scenario: Working-tree mode
- **WHEN** `run --travail a` runs while the checkout holds an untracked non-ignored file and an ignored file
- **THEN** the archive holds the untracked file and not the ignored one, and the branch references and the real index are unchanged

#### Scenario: Mode with a branch
- **WHEN** `run --index <branche> a` runs, then `run --travail <branche> a`
- **THEN** each exits 2 (usage) and the fake Docker records nothing

#### Scenario: Suite name outside the pattern
- **WHEN** `run --travail 'a;b'` runs
- **THEN** the script exits 2 and the fake Docker records nothing

### Requirement: A green index run records its proof line
The system SHALL make a green `run --index` append to the index-proof file (design D1; `CI_LOCAL_PREUVES_INDEX` in tests) one line with the tree, the image key and the suites, under the write rules of the verdicts. A red or interrupted `--index` run SHALL write no line; `--travail` no proof, verdict or report. It SHALL NOT write a branch, a path, a date, a verdict or a person in that file.
Source: untested until implemented (T2, suite ci_local)

#### Scenario: Green index run
- **WHEN** `run --index a b` is green with a fake index-proof file
- **THEN** the file holds one line with the tested tree, the image key, `a` and `b`, and no verdict field

#### Scenario: Red index run
- **WHEN** `run --index a` is red with a fake index-proof file
- **THEN** the script exits 1, its output gives the red verdict, and the index-proof file is unchanged

#### Scenario: Working-tree run
- **WHEN** `run --travail a` is green
- **THEN** the index-proof file, the verdicts file, the proof file and the reports are unchanged
