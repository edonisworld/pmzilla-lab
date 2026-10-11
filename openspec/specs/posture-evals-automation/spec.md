# posture-evals-automation Specification

## Purpose

Describes the on-demand automation script that replays the evaluation set on the committed state, regenerates the dashboard, optionally refreshes the README and installation guide, and notifies the user.

## Requirements

### Requirement: Default automatic run
The system SHALL, with no option, replay the evaluation set on the committed state, regenerate the dashboard, start no model session for documentation and push nothing, and release its lock at the end.

#### Scenario: No option
- WHEN the script is started without options
- THEN it exits with success, replays on the committed state, regenerates the dashboard, makes no documentation session, does not try to push, and the lock is released

Source: tests/evals_auto/test_evals_auto.sh

### Requirement: Optional documentation update
The system SHALL, with the documentation option, run the update-readme instruction in a non-interactive session carrying the run summary (without the instruction file's header), and then attempt a push.

#### Scenario: Documentation option
- WHEN started with the option
- THEN the evaluation set runs, a session starts with the summary in the prompt and the instruction body, and a push is attempted

Source: tests/evals_auto/test_evals_auto.sh

### Requirement: Refusal when documentation files are dirty
The system SHALL refuse the documentation update, giving the reason "uncommitted changes", when the README or the installation guide has uncommitted changes, SHALL still run the evaluation set, and SHALL start no session. Without the option, such changes SHALL NOT interfere.

#### Scenario: README modified
- WHEN the option is used with a modified README
- THEN the reason is shown, no session starts and the evaluation set still ran

#### Scenario: Installation guide modified
- WHEN the guide has uncommitted changes
- THEN the update is refused likewise

#### Scenario: No option
- WHEN there is no option, with modified files
- THEN the run proceeds without that message

Source: tests/evals_auto/test_evals_auto.sh

### Requirement: Option handling
The system SHALL refuse an unknown option with exit code 2 and no call, and SHALL print a help text describing the documentation option with exit code 0 and no call.

#### Scenario: Unknown option
- WHEN started with an unknown option
- THEN exit code is 2 and nothing is invoked

#### Scenario: Help
- WHEN started with the help flag
- THEN exit code is 0, the documentation option is described and nothing is invoked

Source: tests/evals_auto/test_evals_auto.sh

### Requirement: One run at a time with re-run request
The system SHALL allow only one automatic run at a time; a concurrent start SHALL record a re-run request and exit without replaying the evaluation set, regenerating the dashboard, notifying, or releasing the lock of the run in progress. The running one SHALL run again at its end when requested.

#### Scenario: Concurrent start
- WHEN a run is in progress
- THEN the new start records the re-run request, says that a re-run is requested, exits successfully, plays neither the evaluation set nor the dashboard, sends no notification, and the lock of the run in progress stays in place

Source: tools/evals_auto.sh; tests/evals_auto/test_evals_auto.sh (re-run requested during a run)

### Requirement: Prerequisite and notification
The system SHALL check that the embedding service is up before running and, if not, postpone the run with a notification and SHALL NOT play the evaluation set; it SHALL notify the summary at the end, or an error notification when no summary was produced; a failing dashboard SHALL never fail the run.

#### Scenario: Service down
- WHEN the embedding service does not answer
- THEN the run is postponed with its reason in the output, the evaluation set is not played, exactly one notification (the postponement) is sent, the exit code is non-zero, and the lock is released

#### Scenario: No summary
- WHEN the evaluation run produces no summary
- THEN the output says the run has no summary, exactly one "error" notification refers to the log, the dashboard is still regenerated, and the lock is released

Source: tools/evals_auto.sh; tests/evals_auto/test_evals_auto.sh

## Open questions

1. The automatic run is triggered from a commit hook only on request; the hook itself is outside this capability's files.
