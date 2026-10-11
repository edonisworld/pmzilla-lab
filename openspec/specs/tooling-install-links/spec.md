# tooling-install-links Specification

## Purpose
Make the repository's tools folder the single source of truth for scripts called by launchd, the MCP server and the evaluation runs, by exposing each script as a symbolic link in the lab folder.
## Requirements
### Requirement: Create links to tracked scripts
The system SHALL create, for each listed script, a symbolic link in the lab folder pointing to the script in the tools folder, and SHALL leave an already correct link untouched.

#### Scenario: First run
- WHEN the installer runs and scripts exist only as copies or are absent
- THEN each script becomes a working relative link to the tools folder, and executable scripts stay executable through the link

#### Scenario: Rerun
- WHEN the installer runs again
- THEN no link is recreated and no new backup is made

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

