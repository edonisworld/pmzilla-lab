# posture-evals-report Specification

## Purpose

Describes scoring, regressions, automatic retries, run records and the report produced by a run of the posture evaluation set.

## Requirements

### Requirement: Score and regression computation
The system SHALL count blocking verifications only (the total also includes the expected blocking verifications of non-evaluable cases, see "Non-evaluable cases make the run non-validating"), SHALL define a regression as a blocking verification that fails now and passed in the most recent previous run of the same language (excluding the current run), and SHALL print a summary line with passed over total, the regression count, and the report location. The previous run SHALL be the latest other run; runs without a language field SHALL count as French.

#### Scenario: Previous results
- WHEN several previous runs exist
- THEN the most recent one other than the current is used; none gives an empty comparison

#### Scenario: Language-specific comparison
- WHEN comparing English results
- THEN only runs of the same language are used

#### Scenario: Indicator failing
- WHEN an indicator fails and passed before
- THEN it is neither counted nor a regression

Source: tests/posture_evals/test_posture_evals.py (Rapport, Langue, IndicateursNonBloquants)

### Requirement: Report content
The system SHALL write a Markdown report per run containing the memory mode (and the language when not French), the score with number of cases and tested state (truncated), the indicator score, a regression section only when regressions exist, a summary table with passed count (plus indicators), posture, cost (or a placeholder when unknown) and turns, and per case the question and each check with a pass or fail mark and a "regression" or "corrected" note, plus the justification. Indicators SHALL be labelled non-blocking.

#### Scenario: With a regression and a correction
- WHEN a verification newly fails and another newly passes
- THEN the report has a regression section naming the case and criterion, and marks each accordingly

#### Scenario: No regression
- WHEN there is none
- THEN no regression section appears and memory defaults to "real"

#### Scenario: Failed session and refusals
- WHEN a session failed or tools were refused
- THEN the case section says so and lists refused tools once each

#### Scenario: Non-evaluable case
- WHEN prerequisites were unmet or the cases database was unavailable
- THEN the case section lists the reasons instead of checks

Source: tests/posture_evals/test_posture_evals.py (Rapport, IndicateursNonBloquants); tests/posture_evals/test_cases_fixture.py (PassageAvecBaseJetable)

### Requirement: Run record
The system SHALL write, for each run, a record with date, tested state, memory mode, language, per-case results, whether the run was complete (no case selection and no alternative file), whether it was a rejudge, the session and judge models, whether the run is validating, the non-evaluable cases, and the cost of replays, next to the raw traces; the report and traces SHALL be kept outside tracked sources.

#### Scenario: English run
- WHEN a run is played in English
- THEN its record carries the language and its report says so

#### Scenario: Complete run
- WHEN a run has no case selection and no alternative case file
- THEN its record marks it complete; a case selection, an alternative case file, or both, mark it not complete

Source: tests/posture_evals/test_posture_evals.py (Principal, Langue); tests/posture_evals/test_gaps_posture_evals.py (PassageComplet, FichierDeCasDeCommandes)

### Requirement: Automatic retries of failing cases
The system SHALL replay a case whose blocking verification failed a configurable number of times (zero disables). A case that passes all replays SHALL be "unstable" and count as passed, with the first failure kept; a case failing a replay SHALL be a "confirmed failure" and the series SHALL stop at the first failing replay. When more than a configurable number of cases fail, no case SHALL be replayed and a note SHALL say so. Failing indicators, technical incidents and real-memory violations SHALL NOT trigger replays. A rejudge SHALL never replay.

#### Scenario: No failure
- WHEN every case passes
- THEN no replay occurs and the summary has no replay mention

#### Scenario: Fail then pass twice
- WHEN a case fails and then passes both replays
- THEN it is unstable, counted as passed, the summary shows one unstable case and the replay cost, and the report says "unstable (1 failure out of 3)" and has no regression section

#### Scenario: Confirmed failure
- WHEN the first replay fails
- THEN the second is not played and the case is marked confirmed failure; a pass followed by a fail also confirms

#### Scenario: Regression confirmed
- WHEN a criterion passed in a previous run and the case fails its replays
- THEN a regression is reported

#### Scenario: Massive failure
- WHEN failing cases exceed the cap
- THEN no replay is played and the report states the cap

#### Scenario: Retries disabled
- WHEN retries are zero
- THEN a failing case is not replayed and is not unstable

Source: tests/posture_evals/test_posture_evals.py (Rejeux)

### Requirement: Repeated instability
The system SHALL flag a case as "repeatedly unstable" when it is unstable in a complete run and was unstable in the previous complete run; partial runs (selected cases) SHALL NOT count.

#### Scenario: Two complete runs
- WHEN a case is unstable in consecutive complete runs
- THEN the second report marks it "repeated"

#### Scenario: Partial runs
- WHEN both runs are partial
- THEN the flag is not set

Source: tests/posture_evals/test_posture_evals.py (Rejeux)

### Requirement: Cost reporting
The system SHALL report each case's cost and turns and SHALL report the replay cost separately in the summary and the report.

#### Scenario: Replay cost
- WHEN replays were played
- THEN the summary line and the report show their total cost

Source: tests/posture_evals/test_posture_evals.py (Rejeux)

### Requirement: Models and non-validating runs
The system SHALL record in the run record, and print in the report header, the model of the tested sessions and the model of the judge, the session model as the usual model when none was given and the judge model as Sonnet when none was given (the default judge, see the judge specification). A run whose session model is not the usual one SHALL be marked "not validating" in its record and in its report. A non-validating run SHALL NOT serve as the previous run for the regression comparison, SHALL NOT serve as the previous complete run for the repeated-instability check, and SHALL NOT count for the acceptance rule. A judge model alone SHALL NOT make a run non-validating.

#### Scenario: Usual models
- WHEN no model is given
- THEN the header names the usual model for both and the run is validating

#### Scenario: Other session model
- WHEN a session model is given
- THEN the header names both models, the report carries a "not validating" notice, and the record marks the run as not validating

#### Scenario: Baseline
- WHEN a non-validating run is the most recent run
- THEN the next run compares with the latest validating run instead

#### Scenario: Judge model alone
- WHEN only a judge model is given
- THEN the run stays validating and the header shows that judge

Source: tests/posture_evals/test_posture_evals.py (ChoixDuModele)

### Requirement: Non-evaluable cases make the run non-validating
The system SHALL compute the total of a run over every expected blocking verification, those of non-evaluable cases included (counted as not passed): the posture check when a posture is expected, the blocking rules and the blocking judged criteria. When at least one case is non-evaluable, the summary line SHALL give the number of non-evaluable cases and say the run is not validating, the record SHALL mark the run not validating and list those cases, a line SHALL name them with the exit code, and the run SHALL end with exit code 3 after writing its record and report; the report SHALL carry a "not validating" notice naming them. Such a run SHALL NOT serve as a reference (same rule as any non-validating run). A run without non-evaluable case SHALL stay validating and exit with code 0. A rejudge checks no prerequisite, so it has no non-evaluable case.

#### Scenario: Cases database unavailable
- WHEN a case with a fixture cannot be evaluated because the disposable cases database is unavailable, and another case passes
- THEN the summary line is "1/2" with one non-evaluable case and the non-validating mention, the record is not validating and lists the case, and the exit code is 3

#### Scenario: All cases evaluable
- WHEN no case is non-evaluable
- THEN the summary line has no non-evaluable mention, the record is validating and the exit code is 0

#### Scenario: Shipped cases
- WHEN the expected blocking verifications of the shipped cases are counted
- THEN the count equals the blocking total of the shipped cases

Source: tests/posture_evals/test_cases_fixture.py (PassageAvecBaseJetable)

### Requirement: The run record carries the fingerprint of the evaluated files
The system SHALL write in every run record, next to the tested state, the fingerprint of the evaluated paths of the tested tree: `v1:` followed by the SHA-256 of the sorted lines mode, content identifier and path of each matching file (posture-evals-on-branch-tip design D2). A rejudge SHALL copy the rejudged run's fingerprint. It SHALL NOT write a path, a name or a file content in clear in that field.

#### Scenario: Same evaluated files
- **WHEN** two runs test trees whose evaluated files are identical and whose other files differ
- **THEN** both records hold the same fingerprint

#### Scenario: One evaluated file changed
- **WHEN** a posture skill differs between the two tested trees
- **THEN** the fingerprints differ

#### Scenario: Rejudge
- **WHEN** a past run is rejudged
- **THEN** the new record holds the rejudged run's fingerprint

### Requirement: The evaluated paths come from one tracked list
The system SHALL read the evaluated paths from one tracked data file shared with the finishing script, each entry a Git path specification from the repository root, and SHALL exit 2 with `liste des fichiers évalués absente ou vide`, before any copy, when that file is missing or empty (design D3, D7). It SHALL NOT fall back to built-in paths.

#### Scenario: Missing list
- **WHEN** the list file is absent
- **THEN** the script exits 2 with its phrase and no copy is created

#### Scenario: Families kept
- **WHEN** the list file is read by its test
- **THEN** it covers the session instructions file, the posture skills, the Critic agent file, the posture vocabulary and the frozen posture memory

#### Scenario: Sub-folder instructions file outside the fingerprint
- **WHEN** two tested trees differ only by a `CLAUDE.md` file under a sub-folder
- **THEN** both records hold the same fingerprint

## Open questions

1. A run of the command-case file is a separate run with its own summary, report and record, marked not complete (tested); nothing in its report names the case file it came from. Whether the report should carry a dedicated line for it is not decided.
