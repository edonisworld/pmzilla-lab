# tooling-install-links Specification

## Purpose
Make the repository's tools folder the single source of truth for scripts called by launchd, the MCP server and the evaluation runs, by exposing each script as a symbolic link in the lab folder.

## Requirements

### Requirement: Create links to tracked scripts
The system SHALL create, for each listed script, a symbolic link in the lab folder pointing to the script in the tools folder of the run tree, or in the tools folder of the development checkout when the rollback target is chosen, and SHALL leave an already correct link untouched. It SHALL NOT point a link at a work-branch worktree. Untested until implemented for the run tree and the rollback target.

#### Scenario: First run
- WHEN the installer runs and scripts exist only as copies or are absent
- THEN each script becomes a working relative link to the run tree's tools folder, and executable scripts stay executable through the link

#### Scenario: Rerun
- WHEN the installer runs again
- THEN no link is recreated and no new backup is made

#### Scenario: Rollback target
- **WHEN** the installer runs with the rollback target
- **THEN** each link points to the development checkout's tools folder

Source: tests/installation/test_install_links.sh

### Requirement: Back up replaced copies
The system SHALL move any existing regular file replaced by a link, and leftover backup files, into a timestamped backup folder, never delete them, and report whether each copy was identical or different from the tracked script.

#### Scenario: Different copy
- WHEN a copy differs from the tracked script
- THEN the output flags it as a different copy and the old content is kept in the backup folder

#### Scenario: Identical copy
- WHEN a copy is identical
- THEN the output says so

Source: tests/installation/test_install_links.sh

### Requirement: Verify mode
The system SHALL, in verify mode, report the state of every link without changing anything, exit non-zero naming each missing script when any link is missing, and exit 0 with an "all links in place" message otherwise.

#### Scenario: Missing link
- WHEN any single link of the list is missing, whichever it is
- THEN verify exits non-zero and names that script, and does not claim all links are in place

#### Scenario: All present
- WHEN every link exists
- THEN verify exits 0

#### Scenario: Verify creates nothing
- WHEN verify runs with links missing
- THEN no link is created

Source: tests/installation/test_install_links.sh

### Requirement: Shell independence
The system SHALL give the same verdict whether it is launched by zsh, bash or sh, re-executing itself under zsh, and SHALL stop with an error if zsh is unavailable.

#### Scenario: Launched by bash with one link missing
- WHEN the script runs under bash while one link is missing
- THEN the verdict is the same as under zsh, naming the missing script

Source: tests/installation/test_install_links.sh

### Requirement: Link list is complete and consistent
The system SHALL ensure every script in its list exists in the tools folder and gets a link, and SHALL stop with an error naming the absent scripts when one is missing from the tools folder.

#### Scenario: Script absent from tools
- WHEN a listed script is not in the tools folder
- THEN the installer exits non-zero without creating links

#### Scenario: List read from the installer
- WHEN the test reads the installer's own script list
- THEN every listed script exists in the tools folder and gets a working link

Source: tests/installation/test_install_links.sh

### Requirement: Former verify option refused
The system SHALL refuse the former name of the verify option with an error that names the current option, SHALL exit non-zero and SHALL create or change no link.

#### Scenario: Old option
- **WHEN** the former option name is passed
- **THEN** the exit code is non-zero, the message names the current option, and no link is created

### Requirement: Links follow the chosen code tree
The system SHALL replace a link that points into the other code tree and report it; in verify mode it SHALL report such a link as aimed at the wrong tree and exit non-zero, changing nothing. Without the rollback target, it SHALL refuse when the run tree is missing, naming the run-tree script's create command, and SHALL create or change no link. Untested until implemented.

#### Scenario: Switch-over
- **WHEN** the links point to the development checkout and the installer runs without the rollback target
- **THEN** every link points into the run tree and the output names each replaced link

#### Scenario: Verify after a switch
- **WHEN** one link still points to the development checkout and verify mode runs without the rollback target
- **THEN** verify exits non-zero, names that script as aimed at the wrong tree, and changes nothing

#### Scenario: Run tree missing
- **WHEN** no run tree exists and the rollback target is not chosen
- **THEN** the installer exits non-zero, names the create command, and no link is created or changed

### Requirement: Scheduled scripts are linked and find their folder through the link
The system SHALL include in the link list every script that a scheduler template launches, and SHALL make each such script resolve its own folder through the link, so that a script launched by its lab-folder link finds the files of its code tree. A linked script SHALL NOT take the lab folder as its own folder. Untested until implemented.

#### Scenario: Template scripts in the list
- **WHEN** the test reads the program of every scheduler template, the watch catch-up and doctor templates included, and the installer's list
- **THEN** each launched script is in the list, the doctor wrapper included

#### Scenario: Backup through its link
- **WHEN** the backup script is started through its lab-folder link in a fixture
- **THEN** it resolves its folder inside the code tree the link points to
