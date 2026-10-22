# tooling-install-script Specification

## Purpose
The system SHALL provide a scripted, step-by-step installation of the lab on a new machine, each state change confirmed, idempotent, with a dry run and no secret handled.

## Requirements

### Requirement: Fresh mode and an ordered list of steps
The system SHALL provide an install script with one mode, the fresh mode, for the published edition with no personal data. The mode option SHALL be required. It SHALL run the steps of the mode in a fixed order, and SHALL list them on request. The fresh mode SHALL NOT create or copy any personal data. Any mode value other than fresh SHALL be refused with exit code 2 and the key phrase of design D17 that points to the "Install script" section of the installation guide, and no step SHALL run. The system SHALL NOT accept a bundle option, a dumps option or a pack subcommand; each SHALL give exit code 2 as an unknown option or argument. A missing mode, an unknown option or an unknown step SHALL also give exit code 2. Exit codes and messages are those of design.md (D13, D17).

#### Scenario: Step list
- **WHEN** the steps are listed for the fresh mode
- **THEN** they appear in order, and the exit code is 0

#### Scenario: Other mode refused
- **WHEN** the script is started with the migrate mode
- **THEN** it prints "is not available in this version" with the pointer to the "Install script" section of the guide, runs no step, and exits with code 2

#### Scenario: Migrate options refused
- **WHEN** a bundle option, a dumps option or the pack subcommand is given
- **THEN** the script exits with code 2 and runs no step

### Requirement: Every state change is confirmed, default no
The system SHALL ask an explicit yes-or-no confirmation before each action that changes the machine, showing the command it will run. Only an explicit yes SHALL accept; an empty answer or any other answer SHALL decline. The system SHALL NOT offer an option that answers yes for all steps, and SHALL refuse a real run whose standard input is not a terminal with exit code 2. A declined action SHALL be reported as declined, and the steps that depend on it SHALL be deferred, not run.

#### Scenario: Empty answer
- **WHEN** the user presses enter at a confirmation
- **THEN** the action is not run and the step is reported as declined

#### Scenario: No terminal
- **WHEN** a real run is started with standard input from a pipe
- **THEN** the script exits with code 2 before any action

#### Scenario: No global yes
- **WHEN** an option that would accept every step is passed
- **THEN** the script exits with code 2 as for an unknown option

### Requirement: Dry run changes nothing
The system SHALL, with the dry-run option, run only the read-only probes of each step and print every action it would run, with the key phrase "dry run: would run". It SHALL ask no confirmation, and SHALL end with the report, the manual checklist and "dry run: nothing was changed". It SHALL NOT run any state-changing command and SHALL NOT write, link, move or delete any file.

#### Scenario: Dry run on a fresh machine
- **WHEN** the dry run runs with nothing installed
- **THEN** every action is printed as "dry run: would run", the home and repository folders are unchanged, and every command called is in the probe allow-list

#### Scenario: Bootstrap dry run outside a clone
- **WHEN** the bootstrap's dry run runs where no clone exists
- **THEN** it prints the clone it would make, creates no folder, and stops with "dry run: the remaining steps need the clone"

### Requirement: Steps are idempotent and skip what is already done
The system SHALL probe, before each step, whether the step is already done. When it is, the system SHALL skip the step with the key phrase "already done, skipped" and ask nothing. A second run on a fully installed machine SHALL make no state-changing call and exit with code 0.

#### Scenario: Second run
- **WHEN** the script runs again after a complete installation
- **THEN** every step says "already done, skipped", no state-changing command is called, and the exit code is 0

#### Scenario: Hooks already in place
- **WHEN** the hooks verification of the existing installer succeeds
- **THEN** the hooks step is skipped and the installer is not run without its verify option

### Requirement: One step or a starting step
The system SHALL run a single named step, or every step from a named step to the end. When a step's dependency is not done, it SHALL defer that step and name the missing dependency. Giving both a single step and a starting step, or naming a step that the mode does not have, SHALL give exit code 2.

#### Scenario: Single step
- **WHEN** only the MCP step is asked and the lab-folder links are in place
- **THEN** only that step runs

#### Scenario: Missing dependency
- **WHEN** only the MCP step is asked and the lab-folder links are missing
- **THEN** the step is deferred, the message names the links step, and the exit code is 4

#### Scenario: Step outside the mode
- **WHEN** a restore step is named with the fresh mode
- **THEN** the script exits with code 2 and runs no step

### Requirement: No secret is handled
The system SHALL NOT read, write, print or prompt for a password or a token, and SHALL NOT invoke the Keychain command-line tool with any verb. It SHALL NOT run the role-password command of the database script. When the database start script reports that its Keychain entry is missing, the system SHALL stop that step, print "manual action needed:" with the exact creation command (with no password value in it), and defer the steps that need the database. It SHALL list the role-password commands in the manual checklist instead of running them.

#### Scenario: Database entry missing
- **WHEN** the start script reports its missing-password key phrase
- **THEN** the step prints "manual action needed:" and the creation command, the database-dependent steps are deferred, the Keychain tool is never invoked by the install script, and the exit code is 4

#### Scenario: No Keychain call in any run
- **WHEN** the whole suite has run, through every scenario
- **THEN** the calls log never shows the Keychain tool invoked by the install script

### Requirement: Existing scripts are called, not rewritten
The system SHALL run the existing installers of hook links and lab-folder links, the database start script and the migration command, each by its path in the clone. It SHALL run each installer's verify mode after the installer. It SHALL NOT duplicate their logic. It SHALL NOT run the backup script, the restore-test script, the sanctum backup script, the Jira tools, the evaluation set, or the conversion and indexing tools. It SHALL resolve the Python launcher from the search path, never from a fixed path.

#### Scenario: Links step
- **WHEN** the links step runs after confirmation
- **THEN** the lab-folder links installer is called, then its verify mode, and the step is done when the verify exits 0

#### Scenario: Forbidden tools
- **WHEN** the script text is scanned outside comments
- **THEN** it contains no call to the backup script, the role-password command, the Jira tools or the evaluation set, and no fixed path to the Python launcher

### Requirement: Bootstrap before the Python launcher exists
The system SHALL provide a shell bootstrap that refuses any platform other than macOS on Apple Silicon (exit 3). When Homebrew is absent, it SHALL stop with "Homebrew not found" and the address of the Homebrew installation page, without installing Homebrew (exit 3). It SHALL offer, with confirmation, to install Git and the Python launcher through Homebrew. When run outside a clone, it SHALL clone the repository given by the repository option to the expected clone path. Then it SHALL hand over to the orchestrator with every argument. It SHALL refuse a clone at another path, or an existing folder at the clone path that is not a clone, with exit code 3, and SHALL NOT move or delete either.

#### Scenario: Homebrew absent
- **WHEN** the bootstrap runs on a machine without Homebrew
- **THEN** it prints "Homebrew not found" with the installation page, installs nothing, and exits with code 3

#### Scenario: Clone elsewhere
- **WHEN** the bootstrap runs from a clone that is not at the expected path
- **THEN** it exits with code 3, prints "clone must be at" with the expected path, and moves nothing

#### Scenario: Outside a clone without repository option
- **WHEN** the bootstrap runs where no clone exists and no repository option is given
- **THEN** it exits with code 2 and clones nothing

### Requirement: Missing container runtime or Ollama is offered, never forced
The system SHALL use the container runtime that answers. When none answers, it SHALL offer to install and start a container runtime through Homebrew, one confirmation per command, and SHALL NOT start a desktop container application. When the user declines:
- the database step SHALL be deferred;
- the library server step SHALL be deferred, waiting for the database step;
- the backup job SHALL NOT be installed.

The system SHALL NOT register the library server with any file backend. When Ollama is absent, the system SHALL offer to install it with the Homebrew cask `ollama-app` (when Ollama.app is already installed without its command line, it SHALL NOT install it again but SHALL ask the user to open the application once, and Ollama counts as declined for that run), and SHALL offer each required model with its own confirmation showing its approximate size. When Ollama or a model is declined, the watch job SHALL NOT be installed and indexing SHALL be listed as deferred.

#### Scenario: Runtime declined
- **WHEN** no container runtime answers and the user declines its installation
- **THEN** the database step is deferred, the library server step is deferred waiting for the database step, the backup job is not installed, the report lists each, and no registration command is run

#### Scenario: Model declined
- **WHEN** the user declines a model pull
- **THEN** the watch job is not installed and the report lists indexing as deferred

### Requirement: Launchd jobs are rendered, installed and loaded once
The system SHALL render each launchd template by replacing the home placeholder with the user's home folder, write it under the user's launch agents folder, clear its extended attributes, and load it in the user's session. A job that is installed identical and loaded SHALL be skipped as already done. A job whose installed file differs SHALL be replaced only after confirmation, unloading it first. A load error that is followed by a successful status query of the job SHALL count as done.

#### Scenario: Job already loaded
- **WHEN** the installed file equals the rendered template and the job status query succeeds
- **THEN** the job is skipped and no load command is called

#### Scenario: Harmless load error
- **WHEN** the load command fails but the status query then succeeds
- **THEN** the job is reported as done

### Requirement: The library server is registered for the user
The system SHALL register the library server for the user in Claude Code, launched through the lab-folder link with the Python launcher found on the search path, in serve mode with no backend argument. The step SHALL depend on the lab-folder links step and on the database step: when the database step is declined, deferred, failed or waiting for a manual action, the step SHALL be deferred with the reason "waiting for step database" of design D8 and SHALL run no registration command. It SHALL skip the step when the server is already registered with that link and without a backend argument. It SHALL replace a different registration, including one that carries a backend argument, only after confirmation, and SHALL NOT replace it without one.

#### Scenario: Already registered
- **WHEN** the server query succeeds, names the lab-folder link and shows no backend argument
- **THEN** the step is skipped

#### Scenario: Database not ready
- **WHEN** the database step was deferred in the same run
- **THEN** the library server step is deferred waiting for step database, no registration command is called, and the exit code is 4

#### Scenario: Former file-backend registration
- **WHEN** the server is registered with the lab-folder link and a backend argument, and the user confirms the replacement
- **THEN** the former registration is removed and the server is registered in serve mode with no backend argument

#### Scenario: Different registration declined
- **WHEN** the server is registered differently and the user declines the replacement
- **THEN** the registration is unchanged and the step is reported as declined

### Requirement: Final check, report and manual checklist
The system SHALL end every run with:
- a read-only check step, which runs the read-only subset of the installation guide's checks;
- a report with one line per step (done, already done, declined, deferred with its reason, manual action, failed, not run);
- the list "remaining manual steps:".

It SHALL exit with code 0 when every step is done or already done, 4 when any step is declined, deferred or waiting for a manual action, and 1 at the first failed step, naming it and the command that failed. It SHALL NOT run the full test runner or the evaluation set; it prints them as next commands.

#### Scenario: Incomplete run
- **WHEN** one step was declined
- **THEN** the output ends with "installation incomplete", the report names the step, the manual checklist follows, and the exit code is 4

#### Scenario: Failed step
- **WHEN** a called script exits non-zero
- **THEN** the run stops there, prints the step and the command that failed, and exits with code 1

### Requirement: Tests have no real effect
The system SHALL be covered by a test suite that runs the bootstrap and the orchestrator with:
- a fake home and a fake repository root;
- stubs first on the search path, for the package manager, the model runtime, the container tools, the launchd tool, Claude Code, the Keychain tool, Git, the download tool, the platform query and the Python launcher;
- stub versions of the called repository scripts.

The suite SHALL assert that:
- the Keychain tool is never invoked;
- every command is called by name, so only the stubs run;
- every written path is under the temporary folder;
- a dry run leaves the fake folders unchanged.

The suite SHALL NOT need the network, Docker, the Keychain or a real launchd session.

#### Scenario: Isolation
- **WHEN** the suite runs on a machine with real services
- **THEN** no real service is called and no file outside the temporary folder is written

#### Scenario: Absolute command path
- **WHEN** the script text holds an absolute path to a command or a user folder
- **THEN** a test of the suite fails and names it

### Requirement: The doctor job is installed with the other jobs
The system SHALL install and load the doctor's launchd job in the launchd step, with the same rendering, confirmation and already-done rules as the other jobs. It SHALL install it even when the watch or backup job is not installed, since it needs neither Ollama nor the container runtime. It SHALL NOT run the doctor or its wrapper during the installation.

#### Scenario: Runtime declined
- **WHEN** the container runtime and Ollama are declined
- **THEN** the doctor job is still installed and loaded, and the backup and watch jobs are not

#### Scenario: Second run
- **WHEN** the doctor job is installed identical and loaded
- **THEN** it is skipped as already done and no load command is called

### Requirement: The watch catch-up job is installed with the watch job
The system SHALL render, install and load the watch catch-up template right after the watch job, under the same prerequisites, and SHALL defer both watch jobs when Ollama or a model is missing, while the backup and doctor jobs keep their own rules. Loading SHALL be the only start: the step SHALL NOT kickstart it. The run started at load SHALL go through the scheduled-mode guard, so a watch already run today is not run again.

#### Scenario: Fresh install
- **WHEN** the launchd step runs with every prerequisite ready
- **THEN** the watch, catch-up, backup and doctor jobs are rendered, written and loaded, and no kickstart command is called

#### Scenario: Ollama missing
- **WHEN** Ollama or a model is not ready
- **THEN** neither watch job is installed, the backup and doctor jobs are, and the report lists the catch-up job as not installed

#### Scenario: Already in place
- **WHEN** the installed catch-up file equals the rendered template and the job is loaded
- **THEN** the job is skipped as already done and no load command is called

### Requirement: The run tree is created before the links and the jobs
The system SHALL run, in the fresh mode, a run-tree step after the clone and the hooks and before the lab-folder links, the library server and the launchd jobs. After confirmation it SHALL call the run-tree script's create subcommand, then its status. A run tree clean at the tip of `main` SHALL be skipped as already done. It SHALL NOT update, reset or remove an existing run tree.

#### Scenario: Fresh machine
- **WHEN** the run-tree step runs after confirmation and no run tree exists
- **THEN** the create subcommand is called, then the status, and the step is done when the status exits 0

#### Scenario: Run tree behind main
- **WHEN** the status reports the run tree behind `main`
- **THEN** the step is reported as a manual action with the update command, and no update is called

#### Scenario: Order
- **WHEN** the steps of the fresh mode are listed
- **THEN** the run-tree step comes after the hooks and before the links, the library server and the launchd jobs
