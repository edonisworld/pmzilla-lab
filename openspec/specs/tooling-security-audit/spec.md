# tooling-security-audit Specification

## Purpose
TBD - created by archiving change security-audit-kraken. Update Purpose after archive.

## Requirements

### Requirement: A third-party skill is read only from a pinned and reviewed copy
The system SHALL let the audit agents read the audit skill only from a quarantine copy fetched by the author at one full upstream commit, after an Opus review whose verdict is `installable` or `installable sous réserve` (design D1, D2). It SHALL NOT install the skill, run anything from the copy, or read a copy that is refused, unreviewed, edited, or fetched by a session or an agent.

#### Scenario: Refused verdict
- **WHEN** the review finds that the copy ships a hook, a settings file, an MCP declaration or an `allowed-tools` grant beyond read and search tools
- **THEN** the verdict is `refusé`, the audit agents do not read the copy, and nothing is written under `.claude/`

#### Scenario: Instructions that need other tools
- **WHEN** the copy tells Claude to run a command or fetch an address, and ships nothing that runs by itself
- **THEN** the verdict is `installable sous réserve` and the review lists each such instruction, to be reported as not run

### Requirement: Quarantine copies carry a SHA-256 fingerprint
The system SHALL record, for each quarantine copy (the skill and the pinned `axe-core` release), one `shasum -a 256` line per regular file, and SHALL compare them again before the audit (design D1). It SHALL NOT start the audit on a gap. A later publication SHALL refetch the same commit; a new upstream commit SHALL require a new review.

#### Scenario: Copy changed since its record
- **WHEN** one line recomputed before the audit differs from the record
- **THEN** no audit lot starts and the gap goes to the author

#### Scenario: New upstream commit
- **WHEN** a later publication audit uses another upstream commit of the skill
- **THEN** the copy is not read before a new review of design D2

### Requirement: The bug hunt follows the method validated by the author
The system SHALL hunt bugs with the method drawn from the third-party plugin by a read-only review (design D3), with the corrections of the author. The plugin SHALL NOT be installed, run or followed. The hunt SHALL NOT write outside the repository, except the exploratory report folder and the results file, nor write an authentication file or a browser profile.

#### Scenario: Plugin instruction to install a browser server
- **WHEN** the method file reports an instruction of the plugin to add a server or install a package
- **THEN** the hunt does not carry it out and no configuration of the agent changes

### Requirement: The audit and the bug hunt are read-only
The system SHALL run each audit lot and the bug hunt (design D4, D7) as an Opus agent with Read, Grep and Glob only, one pass, at the frozen commit. A lot SHALL stop at 150 % of its announced estimate with its partial coverage. The agents SHALL NOT run a command, fetch an address, write a file, read a closed path of the root session instructions, or connect to a database.

#### Scenario: Skill asks for a scanner
- **WHEN** the skill tells the agent to run a dependency scanner
- **THEN** the agent does not run it and the results file lists it under `## Non exécuté` with its reason

#### Scenario: Closed path in scope
- **WHEN** a lot's file list reaches a closed path
- **THEN** the agent does not read it and the coverage table counts it as not read, without naming its content

#### Scenario: Estimate exceeded
- **WHEN** a lot reaches 150 % of its estimate
- **THEN** it stops and returns its findings and its partial coverage

### Requirement: The audit covers the whole repository and the public tree
The system SHALL split the tracked files of the frozen commit so that each belongs to exactly one of the lots L1 to L3 of design D4, and SHALL audit the public tree built by the generator at the same commit (design D5). The results file SHALL give the count of files per lot and the generator's exit code. A tree the generator declares not publishable SHALL be a critical finding.

#### Scenario: File in no lot
- **WHEN** the coverage count of the lots differs from the count of tracked files
- **THEN** the consolidation does not return the results text and names the gap

#### Scenario: Internal path in the public tree
- **WHEN** a file of the built tree holds an absolute path of the author's machine
- **THEN** the finding is at least high, located by its path in the tree, without copying the path's private part

### Requirement: The exploratory pass runs on the synthetic instance only and writes nothing
The system SHALL run the exploratory pass of design D6 only against `http://127.0.0.1:3001`, after checking that the dataset is `synthetic`. It SHALL abort and record every request other than GET or HEAD and every request to another host. It SHALL NOT read the real database, save a response body, download a browser or another Playwright version, or leave a change in the worktree.

#### Scenario: Other address
- **WHEN** the base address is not `http://127.0.0.1:3001`
- **THEN** the pass stops with `exploration : instance refusée (http://127.0.0.1:3001 seulement)` before any screen

#### Scenario: Not the synthetic dataset
- **WHEN** the dataset code of the dashboard answer is not `synthetic`
- **THEN** the pass stops with `exploration : jeu de données non synthétique, passe arrêtée` before any screen

#### Scenario: Write request
- **WHEN** a screen issues a POST or PATCH request
- **THEN** the request is aborted and the report holds an entry of kind `ecriture_bloquee`

### Requirement: The exploratory pass records errors and accessibility violations
The system SHALL visit each screen, served conviction, filter value one at a time and catalogue language, and record console errors, uncaught exceptions, responses 400 to 599 (method and route path) and axe violations, in one JSON report outside the repository. axe SHALL come from its quarantine file. The pass SHALL exit 0 when the visit completes. It SHALL NOT add a dependency to the repository or a lock.

#### Scenario: Server error on a filter
- **WHEN** a filter value makes the server answer 500
- **THEN** the report holds an `http` entry with the screen, the filter, the language, the method and the route path, and the visit goes on

#### Scenario: Entry of the pass
- **WHEN** the pass records an entry
- **THEN** it is a lead with status `soupçonné` until a reproduction confirms it

### Requirement: The bug hunt covers the whole of Mothra
The system SHALL hunt in the whole of Mothra (server, contract, front, views read by Mothra, Python reader of the masking) for the bug kinds of design D7, in the priority order of the Kraken diff and its impact radius. It SHALL NOT limit the scope to the diff. Each gap between SQL, Python and TypeScript SHALL cite both sides by file and line.

#### Scenario: Floor computed differently
- **WHEN** the masking floor or a rounding differs between the SQL view and the TypeScript reader
- **THEN** the finding names both locations and is at least high

#### Scenario: Module outside the diff
- **WHEN** a Mothra module was not touched by Kraken
- **THEN** it is still in scope, read after the modules of the diff and its impact radius

### Requirement: A finding is confirmed only by three red runs of its reproduction
The system SHALL write reproductions in the single throwaway branch `chasse/kraken` and run each three times with `bash tests/run_all.sh <suite>` in the container (design D8). Status: `confirmé` when red at three runs, `soupçonné (intermittent, k/3)` at one or two, `soupçonné` otherwise. It SHALL NOT run a reproduction by a direct form, change source code, or merge or register that branch in a train.

#### Scenario: Intermittent reproduction
- **WHEN** a reproduction is red at two of the three runs
- **THEN** the status is `soupçonné (intermittent, k/3)` with k = 2, and the reproduction is never used as is as the test of a correction

#### Scenario: Deterministic rewrite
- **WHEN** an intermittent reproduction is rewritten with test doubles and a frozen clock and is red at the three runs
- **THEN** the status becomes `confirmé`

#### Scenario: Branch after the triage
- **WHEN** the author's triage is done and the corrections have taken the reproductions they need
- **THEN** the branch `chasse/kraken` and its worktree are deleted

### Requirement: Findings go into one classified results file
The system SHALL write all findings of the audit and of the bug hunt into one file in the decisions folder outside the repository, with the headings, fields, statuses and severity scale of design D9. Each finding SHALL carry a status, a location and a proposed correction. There SHALL NOT be a second results file, and the file SHALL NOT enter the repository or stay only in a message.

#### Scenario: Finding without correction
- **WHEN** a consolidated finding has no `Correction proposée`
- **THEN** the consolidation does not return the results text and names the finding

#### Scenario: Finding without status
- **WHEN** a consolidated finding has no `Statut` among the three of design D8
- **THEN** the consolidation does not return the results text and names the finding

### Requirement: Findings never copy a sensitive value
The system SHALL describe a secret, a name, a ticket key or title, or a closed path's content by its kind and location only, in the results file, the review files, the reproductions and the issue drafts. It SHALL NOT copy the value.

#### Scenario: Token in a tracked file
- **WHEN** an agent finds a token in a tracked file
- **THEN** the finding reads its kind and path:line, holds no character of the token, and is critical

### Requirement: Every finding is fixed in Kraken, whatever its severity
The system SHALL fix in Kraken, before the publication, every finding whatever its severity (R-20261107-23), except the findings that go to Hydra under the two requirements on Hydra, with a test written first, its confirmed reproduction when there is one, and an Opus review (design D10). A changed existing test SHALL be authorised by its name and checked by that review to tighten (R-20261107-26). It SHALL NOT send a finding to Hydra for its severity alone or loosen an existing test.

#### Scenario: Fix without a red test
- **WHEN** a correction's commit holds no test that fails without the fix
- **THEN** the Opus review of task 13.1 refuses it

#### Scenario: Confirmed reproduction taken over
- **WHEN** a finding sorted to Kraken has a `confirmé` reproduction
- **THEN** its correction branch takes that reproduction as its first, red test

#### Scenario: Low finding without a Hydra dependency
- **WHEN** a low finding needs no function planned for Hydra
- **THEN** it is fixed in Kraken, and no Hydra issue is created for it

### Requirement: A finding that needs a Hydra function goes to Hydra with its reason
The system SHALL send to Hydra a finding that needs a function planned for Hydra, such as the local accounts or the sandbox of level 2, named with its reason in its `Tri :` line (R-20261107-23), as one issue or comment created through `tools/gh_issue.py` only, after the author's re-read. It SHALL NOT create an issue before that re-read, or write a value or a name in an issue.

#### Scenario: Finding that needs the local accounts
- **WHEN** a finding can only be fixed with the local accounts
- **THEN** its `Tri :` line reads Hydra with that reason, and it is not fixed in Kraken

#### Scenario: Drafts not yet re-read
- **WHEN** the author has not re-read the batch of drafts
- **THEN** no Hydra issue is created

### Requirement: A critical finding goes to Hydra only by the author's decision
The system SHALL send a critical finding to Hydra only by an explicit decision of the author, cited in its `Tri :` line and in the closing comment of the audit issue (R-20261114-02). It SHALL NOT defer a critical finding without that decision, or close the audit issue without naming the exception.

#### Scenario: Critical finding that needs the sandbox of level 2
- **WHEN** a critical finding can only be closed by the sandbox of level 2 planned for Hydra
- **THEN** it goes to Hydra only after the author's decision, its `Tri :` line reads critical, deferred with that function and its issue, and the audit issue closes with that exception named

#### Scenario: Critical finding without the author's decision
- **WHEN** a critical finding needs a Hydra function and the author has not decided its deferral
- **THEN** it stays sorted to Kraken and task 14.2 stays open

### Requirement: Each finding carries its hosting mark
The system SHALL give each consolidated finding the line `Hébergement : oui` or `Hébergement : non`, which says whether the finding counts for a network exposure of Mothra (R-20261107-24). At the closure of Kraken, the session SHALL copy the list of the findings marked `oui`, fixed or not, into the hosting issue of the V3 horizon, through `tools/gh_issue.py` only. It SHALL NOT leave a finding without its mark, or copy a value or a name into that issue.

#### Scenario: Finding without its mark
- **WHEN** a consolidated finding has no `Hébergement :` line
- **THEN** the consolidation does not return the results text and names the finding

#### Scenario: Closure of Kraken
- **WHEN** the session closes Kraken
- **THEN** the hosting issue receives the identifiers and titles of the findings marked `oui`, and nothing else from the results file

### Requirement: No correction lowers an existing protection
The system SHALL accept, as a correction, only a change that adds or tightens a protection among those of design D12. A finding whose only fix would remove or loosen one SHALL go back to the author as a separate decision, never delegated. Checked by the review of task 13.1.

#### Scenario: Fix that would remove a deny rule
- **WHEN** the only proposed fix of a finding removes a deny rule
- **THEN** the correction is not made in this change and the finding goes to the author as a separate decision

### Requirement: The public publication of Kraken waits for the audit
The system SHALL start the public publication of Kraken only after the results file exists and every finding sorted to Kraken is merged (task 14.2). This is ordering in the plan; the publication tool is not changed (design D11). The rule falls when that publication is done.

#### Scenario: High finding still open
- **WHEN** a finding sorted to Kraken is not merged
- **THEN** task 14.2 stays open and the publication does not start
