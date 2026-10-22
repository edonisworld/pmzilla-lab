# tooling-local-ci Specification

## Purpose
Run the portable test suites on one commit's tree in a throwaway, pinned container, isolated from the network and the caller's secrets and under the finish lock, and record a readable verdict per tested tree that one command reproduces on the Mac.

## Requirements

### Requirement: The CI script runs the portable suites in a throwaway container
The system SHALL provide `tools/ci_local.sh` whose `run [<branche>]` runs `bash tests/run_all.sh --portable` in a throwaway container from the CI image, on the tree of one commit, exiting 0 when green and 1 when red (local-ci-container design D1, D2). It SHALL NOT test uncommitted changes nor run a targeted run.

#### Scenario: Green run
- **WHEN** the fake Docker command makes the runner exit 0
- **THEN** the script exits 0 and its last line starts with `ci_local : verdict vert (arbre`

#### Scenario: Red run
- **WHEN** the fake Docker command makes the runner exit 1
- **THEN** the script exits 1 and its last line starts with `ci_local : verdict rouge (arbre`

### Requirement: The CI script refuses before starting any container
The system SHALL exit 2 on usage, 3 when Docker or Colima does not answer, 4 outside the repository, for an unknown branch or an unclean tree, 5 for a missing or stale image or npm lock, 6 on a failed build, each with its phrase of design D2. It SHALL NOT start a container after these codes nor leave a tagged image after 6.

#### Scenario: Unclean tree
- **WHEN** `run` gets no branch and the checkout holds an untracked non-ignored file
- **THEN** the script exits 4 with `ci_local : arbre non propre ; rien n'est lancé` and the fake Docker records no run

#### Scenario: Image out of date
- **WHEN** `ci/Dockerfile` changed since the image was built
- **THEN** `run` exits 5 with `ci_local : image absente ou périmée (lancer bash tools/ci_local.sh up)`

### Requirement: The CI script honours the finish lock
The system SHALL refuse `run`, `build` and `up` with code 7 and `ci_local : fin de branche en cours (<branche>), lancement refusé` when a live finish lock holds another token or no token is set, say and ignore a stale lock, and run normally with the matching `FINISH_LOCK_TOKEN` (design D2). It SHALL NOT create, remove or change the lock.

#### Scenario: Lock of another finish
- **WHEN** a live lock holds a token different from the caller's
- **THEN** the script exits 7 and the fake Docker records nothing

#### Scenario: Finish's own token
- **WHEN** the caller carries the lock's token
- **THEN** the run starts as without a lock

### Requirement: The CI image is pinned and keyed
The system SHALL build the image from the official Node 26 slim image and uv, both pinned by digest, Python from `.python-version` and the pinned OpenSpec CLI, with the runner's dependencies resolved at build, and tag it with a key hashing its definition, pins, dependency set and declared npm locks (design D4). It SHALL NOT carry a secret or an unpinned base.

#### Scenario: Key follows the dependency set
- **WHEN** the runner's dependency set changes in the tested tree
- **THEN** the computed key differs from the image's and `run` exits 5

### Requirement: The CI run copies one commit's tree and nothing else
The system SHALL stream into the container an archive of the tree of the named branch's tip, or of a clean `HEAD`, recommitted in a throwaway repository inside the container (design D5). It SHALL NOT bind-mount the workspace, a worktree, the home folder or a lab folder, nor bring in an ignored or untracked file.

#### Scenario: Ignored file absent
- **WHEN** the checkout holds an ignored local file and `run` gets its branch
- **THEN** the archive sent to the container does not hold that file

#### Scenario: Named branch
- **WHEN** `run` gets a branch whose tip differs from `HEAD`
- **THEN** the tested tree is the tree of that tip

### Requirement: The CI run is isolated from the network and the caller's secrets
The system SHALL run the container with `--network none`, a non-root user, a random name, an environment built by the script with `UV_OFFLINE=1`, and SHALL remove it at the end, on failure and on interruption (design D6). It SHALL NOT pass any caller variable, database variable, `DBTEST_PORT`, token or lock token, nor mount the Docker socket.

#### Scenario: Recorded arguments
- **WHEN** the caller exports a database variable, `DBTEST_PORT`, a fake token and a lock token, and `run` starts with the fake Docker command
- **THEN** the recorded arguments disable the network, hold no mount and none of those values

#### Scenario: Interruption
- **WHEN** the run is interrupted
- **THEN** the fake Docker command records the removal of the container

### Requirement: The CI run gives a readable verdict and a report
The system SHALL end every run that started a container with the verdict line of design D7, naming the tree, the image key and the counts or failed suites, and SHALL write a report in the lab data folder with the tree, key, date, runner lines and code. It SHALL NOT write a path, a branch name or a person in the report, nor change the code when the report fails.

#### Scenario: Report written
- **WHEN** a run is green
- **THEN** the fake data folder holds a report with the tree, the key and the `TOTAL` line, and no path or branch name

#### Scenario: Report impossible
- **WHEN** the data folder cannot be written
- **THEN** one line says so and the exit code is the runner's

### Requirement: The CI run records its verdict for the tested tree
The system SHALL keep, in the `verdicts` file of the lab data folder's `ci` folder, outside any `.git` folder, one line per tree (tree id, `vert` or `rouge`, image key); `run` SHALL remove the tested tree's line before the container starts and write it once the container gave a verdict, with the phrases of design D7b. It SHALL NOT write a branch, path, date or person, change another tree's line, leave a line after an interruption or codes 2 to 7, or change its exit code when the write fails.

#### Scenario: Green verdict recorded
- **WHEN** a run on a branch tip is green with a fake verdict file holding a line for another tree
- **THEN** the file holds a `vert` line for the tested tree with the image key, and the other line unchanged

#### Scenario: Red run replaces a green line
- **WHEN** the file holds a `vert` line for the tested tree and the new run is red
- **THEN** the file holds a `rouge` line for that tree and no `vert` line for it

#### Scenario: Interrupted run
- **WHEN** a run is interrupted after the container started
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

### Requirement: Database suites skip in the container
The system SHALL never pass `DBTEST_PORT` nor a database variable to the container, so that database suites skip as without a throwaway database (design D11). It SHALL NOT start a database container from the CI script.

#### Scenario: No throwaway database
- **WHEN** the recorded environment of a run is read
- **THEN** it holds no `DBTEST_PORT` and no `PMZILLA_LAB_DB_` variable

### Requirement: The CI script is testable without Docker
The system SHALL include the shell suite `tests/ci_local`, listed in the runner, that exercises the script with fake Docker and Colima commands, temporary repositories and a fake data folder (design D14). It SHALL NOT build a real image, start a real container, or write into the real data folder or Git folder.

#### Scenario: Suite run
- **WHEN** the runner runs the CI suite
- **THEN** every case runs in a temporary folder and the suite reports its counts in the runner's shell format
