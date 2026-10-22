# posture-evals-replay Specification

## Purpose

Describes how a case is replayed in isolation with a non-interactive Claude Code session: temporary copy, frozen neutral memory and context, protection of the real memory, allowed tools, trace reading, rejudging and tool inspection of past runs.

## Requirements

### Requirement: Each case runs in a disposable copy of the workspace
The system SHALL run each case in a temporary copy of the workspace made from the current state (including uncommitted changes of tracked files and new untracked files) or, on request, from the last commit only, and SHALL remove the copy at the end unless asked to keep it. The copy SHALL also receive the local configuration files that agents need and that Git does not track.

#### Scenario: Copy removed
- WHEN a case finishes, successfully or not
- THEN its copy is removed, unless the user asked to keep copies

#### Scenario: Case that crashes
- WHEN preparing or running a case raises an error
- THEN the error is printed, the case is recorded as failed with an explicit "session failed" note, its copy is removed, and the run continues with the other cases up to the final summary

Source: tests/posture_evals/test_posture_evals.py (CasQuiPlante)

### Requirement: Frozen neutral memory and neutral context by default
The system SHALL, by default, create the agents' memory areas inside the copy, replace each posture's lived memory by the neutral version for the run language (removing lived files without a neutral version and the session history), keep the structure of the tested state, and deposit a neutral local context instead of any personal one. The neutral material of the English language SHALL be kept apart from the French, SHALL contain no French text, and SHALL cover the same postures and files as the French one.

#### Scenario: Lived memory replaced
- WHEN memory is frozen
- THEN each posture's memory file equals the neutral version, files without a neutral version and the session history are removed, structural files remain

#### Scenario: Missing neutral material
- WHEN the neutral memory or the neutral context for the run language cannot be found
- THEN the run stops with a clear error naming the missing material (an older tested state may fall back to the neutral context of the workspace)

#### Scenario: English run
- WHEN the language is English
- THEN the English neutral memory and context are used and the memory declares the English language

#### Scenario: French by default
- WHEN no language is given
- THEN French neutral memory and context are used

Source: tests/posture_evals/test_posture_evals.py (MemoireFigee, MemoireEtContexteParLangue, SanctumsEtContexte, CasQuiPlante); tests/posture_evals/test_gaps_a_voies.py (RejugementSansVerrou)

### Requirement: Real memory is copied, never used in place, and never changed
The system SHALL, when real memory is requested, copy the real memory areas and local context into the copy, rewrite absolute paths inside the copied files to point to the copy, and leave the real files unchanged. The system SHALL detect any change of the real memory during a case and SHALL record it as a failed check that is never replayed. Only one run SHALL be allowed at a time; a rejudge takes no lock.

#### Scenario: Copy is independent
- WHEN real memory is used
- THEN the copied files are distinct files and writing to them leaves the real memory fingerprint unchanged

#### Scenario: Case writes to the real memory
- WHEN a session modifies the real memory
- THEN a warning is printed and the case reports a failed "real memory intact" check

#### Scenario: Second concurrent run
- WHEN a run starts while another run holds the lock
- THEN it stops with a message that another run is in progress; the lock is released at the end of the first run

Source: tests/posture_evals/test_posture_evals.py (SanctumReelProtege)

### Requirement: Session command and permissions
The system SHALL run each case as a non-interactive session with a strict library tool configuration, an explicit allow-list of tools, edit-accepting permission mode, a system instruction giving the copy's working folder (in the language of the run, French text unchanged) and an optional choice of the session model, passed to the session command. The session SHALL run with the current environment, with the copy named as its workspace, so that start-of-session hooks never read the real workspace. Free-form shell access SHALL be absent unless the user asks for it. A session that exceeds its time limit SHALL keep what was already written and record the timeout in the trace.

#### Scenario: Default session
- WHEN a case is played
- THEN the command has the strict configuration, the allow-list and the system instruction, does not include free-form shell access, and names no model

#### Scenario: Session model
- WHEN a session model is given
- THEN every session and every replay of the run uses it

#### Scenario: Timeout
- WHEN the session exceeds its time limit
- THEN partial output is kept and the trace notes the timeout

#### Scenario: Library configuration
- WHEN the library configuration is produced
- THEN it declares the library server launched in serve mode

#### Scenario: Workspace of the session
- WHEN a session is started, with or without a disposable cases database
- THEN its environment keeps the current variables and names the copy as the workspace

Source: tests/posture_evals/test_posture_evals.py (Seance, ChoixDuModele); tests/posture_evals/test_cases_fixture.py (EnvironnementDesSeances)

### Requirement: Reading a trace
The system SHALL read a session trace to extract the tools called with their results, the sections returned by the library, chapter or part mentions found in passages, the cost, the number of turns, the error state, refused tools (deduplicated, truncated), the final answer, and the text of the main thread only (sub-agent text excluded). An empty trace or a trace without a final result SHALL be an error; in the latter case the main-thread text is used as the answer.

#### Scenario: Normal session
- WHEN a trace with tool calls, a sub-agent, and a final result is read
- THEN calls, sections, mentions, cost, turns and answer are extracted and sub-agent text is excluded from the main thread text

#### Scenario: Saved trace with noise
- WHEN a saved trace includes non-JSON lines and a trailing error-stream section
- THEN the noise is ignored and the saved list of written files is read alongside; an absent case yields nothing

#### Scenario: Refused tools
- WHEN the trace lists permission denials
- THEN each is rendered with the tool name and a truncated command

Source: tests/posture_evals/test_posture_evals.py (Trace)

### Requirement: Messages of the last exchange
The system SHALL compute the ordered list of messages of the last exchange: main-thread texts after the last tool call plus the text of each final result, without duplicates, a result being placed at the position of the message it repeats. Lead-in sentences before tools and sub-agent text SHALL be excluded. The blocking checks SHALL keep reading the last answer.

#### Scenario: Critic in the background
- WHEN the posture writes its analysis and then relays Critic in a second message, with two result events
- THEN two messages are listed in order and the result count is two

#### Scenario: Single message
- WHEN there is one final message
- THEN the list holds only that message

Source: tests/posture_evals/test_posture_evals.py (DernierEchange)

### Requirement: Rejudging past runs without new sessions
The system SHALL, on request, recompute the automatic checks and the judge on the saved traces of a past run, SHALL start no new session, SHALL skip with a message the cases that have no trace in that run, SHALL compute the score and regressions against the preceding validating run, SHALL write a new report and run folder, and SHALL take the memory mode, the tested state, the session model and the validating status from the rejudged run. A rejudge SHALL accept a judge model, used for that rejudge only and recorded in its record, and SHALL refuse a session model with an explicit message. A missing run SHALL stop the run with an error.

#### Scenario: Rejudge
- WHEN a past run is rejudged
- THEN only the judge is invoked, the summary line shows the score and regression count, and the report carries the original memory mode and tested state

#### Scenario: Rejudge with another judge
- WHEN a past run is rejudged with a judge model
- THEN the judge command names that model, no session is started, and the new record carries the judge model, the original session model and the original validating status

#### Scenario: Session model at rejudge
- WHEN a session model is given together with a rejudge
- THEN the system stops with a message saying the option does not apply

#### Scenario: Regression at rejudge
- WHEN the judge returns nothing usable for a criterion that previously passed
- THEN it is counted as a regression and named in the report

#### Scenario: Missing run
- WHEN the run to rejudge does not exist
- THEN the system stops with an error

Source: tests/posture_evals/test_posture_evals.py (Principal, Rejeux, ChoixDuModele)

### Requirement: Tool inspection of a past run
The system SHALL list, for each case of a past run, the tools called (library searches with query and collections, sub-agents with their type) without launching anything, and SHALL stop with an error for an unknown run.

#### Scenario: Listing
- WHEN a past run is inspected
- THEN each case appears under its identifier with its searches and sub-agent calls, and no session is launched

Source: tests/posture_evals/test_posture_evals.py (Trace, Principal)

### Requirement: Comparison of two runs
The system SHALL, on request, compare two past runs and list the verdicts that differ: for each, the case, the check, whether it is blocking or not, and the verdict of each run (passed, failed, or absent from that run). It SHALL print the models of both runs, the number of differing verdicts, and neither answer text nor judge justification. It SHALL launch no session and no judge, and SHALL stop with an error when a run is missing.

#### Scenario: Differing verdicts
- WHEN two runs of the same traces judged by two judges are compared
- THEN only the checks whose verdict differs or that exist in one run only are listed, each with its blocking status and both verdicts

#### Scenario: No text leaks
- WHEN the runs carry justifications
- THEN none appears in the output and no model is called

#### Scenario: Missing run
- WHEN one of the runs does not exist
- THEN the system stops with an error

Source: tests/posture_evals/test_posture_evals.py (ChoixDuModele)

### Requirement: Detection of out-of-report workspace changes
The system SHALL warn at the end of a run when the workspace status changed during the run outside the report folder.

#### Scenario: Unexpected change
- WHEN the workspace status after the run differs from before, ignoring report files
- THEN a warning asks the user to check the Git status

#### Scenario: Unchanged workspace
- WHEN the workspace status is the same before and after the run, even with uncommitted changes
- THEN no warning is printed

#### Scenario: Only a report was added
- WHEN the only change during the run is a new file in the report folder
- THEN no warning is printed

Source: tools/posture_evals.py; tests/posture_evals/test_gaps_posture_evals.py (ChangementDuWorkspace)

### Requirement: Former back-end option refused
The system SHALL refuse the former library back-end option, whatever its value, before anything runs (no copy, no database, no session), with exit code 2 and the key phrase of design D7 ("--backend n'existe plus : la bibliothèque est lue dans PostgreSQL seulement"). The library server configuration of every run and of every case SHALL name no back-end. The system SHALL NOT read the former back-end environment variable.

#### Scenario: Option given
- **WHEN** a run is started with the back-end option set to the file-based route or to the database
- **THEN** it stops with exit code 2 and the key phrase, and no copy, database or session is created

#### Scenario: Configuration
- **WHEN** the library server configuration of a run is produced, with the former variable set in the environment
- **THEN** it declares the server launched in serve mode with no back-end argument

### Requirement: Copies can be built from the tip of a named branch
The system SHALL, with the branch option, build every case's disposable copy, replays included, from the tip commit of that local branch, wherever it is checked out, and print `état testé : sommet de <branche> (<sommet court>)` before the first case and in the report header (posture-evals-on-branch-tip design D1). It SHALL NOT copy the workspace's working state, uncommitted changes or untracked files when the option is given.

#### Scenario: Branch checked out in a worktree
- **WHEN** the branch option names a branch checked out in another worktree whose tip differs from the workspace's working state
- **THEN** each copy holds the tip's files and none of the workspace's uncommitted changes, and the record's tested state is the tip commit

#### Scenario: Merged tip after a finish refusal
- **WHEN** the worktree finish merged `main` into the branch and refused with 33, and the branch option names that branch
- **THEN** each copy holds the merged tip's files

### Requirement: The branch option refuses before any copy
The system SHALL exit 2 with `branche inconnue : <branche>` for an unknown local branch, and 2 with `--branch ne se combine pas avec <option>` when it is combined with the last-commit option. It SHALL NOT create a copy, a database or a session after either refusal.

#### Scenario: Unknown branch
- **WHEN** the branch option names no local branch
- **THEN** the script exits 2 with its phrase and no copy is created

### Requirement: Uncommitted evaluated files of the branch's worktree refuse the run
The system SHALL exit 2 with `le worktree de <branche> a des modifications non commitées des fichiers évalués : commite-les ou retire-les, puis relance` when the named branch's worktree holds uncommitted changes of evaluated paths, before any copy (posture-evals-on-branch-tip design D1). It SHALL compare paths only and SHALL NOT read a file of that worktree.

#### Scenario: Dirty worktree
- **WHEN** the branch's worktree holds a modified posture skill
- **THEN** the script exits 2 with that phrase and no copy is created

#### Scenario: Where the run reads and writes
- **WHEN** a run with the branch option completes with a fake session command
- **THEN** the copies hold the tip's cases and posture memory, and the run record and report are written where a run without the option writes them

## Open questions

1. The back-end option only changes the library server configuration (tested); whether both back-ends give the same hits during a session is not covered by any test run on a real database.
