# posture-evals-checks Specification

## Purpose

Describes the deterministic automatic checks applied to a session trace: posture tag, tool use, Critic, text patterns, memory content, structure of the sources section, language formulas and single final message. Checks may be blocking or non-blocking indicators.
## Requirements
### Requirement: Posture tag check
The system SHALL check that the expected posture is announced by a posture tag in the main-thread text, in the tag format of the run language, tolerating spaces inside the tag. The posture name SHALL match exactly, case-sensitively, one of the posture names of the shared vocabulary. A tag in the run language's format whose name is not exactly one of those names (accented, translated or recased) SHALL fail the check, even when a correctly written tag appears elsewhere, and the justification SHALL quote the misspelt tag and the expected format. The expected value "none" SHALL require no tag in any language. A tag in the format of the other language, or tags in both formats, SHALL fail the check, and the justification SHALL name the expected format. No expected posture SHALL produce no check.

#### Scenario: Right posture
- WHEN the expected posture is announced in the language format of the run, with its exact name
- THEN the check passes

#### Scenario: Wrong or absent tag
- WHEN another posture is announced, or no tag appears
- THEN the check fails and the justification lists the tag found or "absent"

#### Scenario: Misspelt tag
- WHEN a tag carries an accented, translated or recased posture name, alone or next to a correctly written tag
- THEN the check fails and the justification quotes the misspelt tag

#### Scenario: Tag in the other language
- WHEN a French run contains an English-format tag (or the reverse)
- THEN the check fails with a justification naming the other-language format and the expected one

#### Scenario: Expected none
- WHEN the expected posture is "none" and no tag appears
- THEN the check passes; any tag in either format fails it

#### Scenario: Default language
- WHEN no language is specified
- THEN French is used

Source: tests/posture_evals/test_posture_evals.py (Verifications, Langue)

### Requirement: Tool use checks
The system SHALL check that a named tool was called (matching library tools by their short name) and, optionally, that at least one of the wanted collections was used in a call, reporting the call count and collections used.

#### Scenario: Tool called
- WHEN the trace contains a call to the tool
- THEN the check passes and states the number of calls

#### Scenario: Collection filter
- WHEN wanted collections are given and none appear in the calls
- THEN the check fails

Source: tests/posture_evals/test_posture_evals.py (Verifications); tests/posture_evals/test_cases_fixture.py (OutilsDesCas)

### Requirement: Critic check
The system SHALL check whether the Critic sub-agent was or was not called, recognising only an agent or task call that targets it; other sub-agents and skill calls SHALL NOT count.

#### Scenario: Critic expected
- WHEN Critic is expected and was called
- THEN the check passes

#### Scenario: Critic not expected
- WHEN Critic is expected absent and a trace has no calls
- THEN the check passes

Source: tests/posture_evals/test_posture_evals.py (Trace, Verifications)

### Requirement: Text and written-file checks
The system SHALL check that a case-insensitive pattern is present in (or absent from) the whole main-thread text, and SHALL check that no file written during the session contains a given pattern, naming the offending files and the number of files written. No written file SHALL pass.

#### Scenario: Text pattern
- WHEN the pattern is present (or absent) as required
- THEN the check passes; otherwise it fails

#### Scenario: Names in memory
- WHEN a written file contains the forbidden pattern
- THEN the check fails and names that file

Source: tests/posture_evals/test_posture_evals.py (Verifications)

### Requirement: Non-blocking indicators
The system SHALL let any check or judged criterion be marked non-blocking; such a result SHALL be flagged as an indicator, reported separately, and SHALL NOT count in the total, the score, the regressions or the retry decision.

#### Scenario: Marked indicator
- WHEN a rule carries the non-blocking mark
- THEN its result carries the indicator flag and the blocking list excludes it while the indicator list includes it

Source: tests/posture_evals/test_posture_evals.py (IndicateursNonBloquants, CritereJugeNonBloquant)

### Requirement: Sources section structure checks
The system SHALL provide three deterministic checks for answers citing watch articles: the sources section is the last element and contains only entry lines; every ISO date in the text appears on a sources line; every sources line is cited in the text by surname or site stem.

#### Scenario: Conforming answer
- WHEN the sources section is last, dates are matched, and each line is cited
- THEN all three checks pass

#### Scenario: Text after the list
- WHEN a book line, a question, a bullet without date or link, or a sub-heading follows the entries
- THEN the first check fails and quotes the offending text

#### Scenario: Heading variants and bullets
- WHEN the heading is bold, followed by a colon, or at any heading level, or entries have no bullet
- THEN the section is still recognised; a line with a link but no date still counts as an entry; indented continuation lines are not trailing text

#### Scenario: Dates
- WHEN a date appears in the body but on no sources line
- THEN the date check fails and names the date; dates inside heading lines do not count, a date in a paragraph that merely looks like a title does

#### Scenario: Citation by name or site
- WHEN a sources line is never cited, or a short word is only a fragment of a longer word
- THEN the citation check fails; a site is recognised by its stem even when written in words

#### Scenario: No sources section
- WHEN no sources section exists
- THEN all three checks fail with a message that no section exists or is usable

Source: tests/posture_evals/test_posture_evals.py (VerificationsDeSources)

### Requirement: Other-language formulas indicator
The system SHALL, for every case, report as a non-blocking indicator whether the final answer contains a fixed formula of the other language (not shared with the run language), matching case-insensitively and treating typographic apostrophes as plain ones.

#### Scenario: Clean answer
- WHEN a French answer has only French formulas
- THEN the indicator passes

#### Scenario: Foreign formula
- WHEN the answer contains formulas of the other language
- THEN the indicator fails and lists them; it counts in neither total nor regressions

Source: tests/posture_evals/test_posture_evals.py (FormulesDeLAutreLangue)

### Requirement: Single final message indicator
The system SHALL, for every case, report as a non-blocking indicator whether the session ends with a single final message and a single result event, failing with the number of messages and result events otherwise. The indicator SHALL stay non-blocking and SHALL be reviewed after 10 complete runs, the review deciding whether it stays an indicator; until that review no decision makes it blocking.

#### Scenario: Critic relayed in a second message
- WHEN the last exchange has two messages
- THEN the indicator fails and states the number of messages

#### Scenario: One message
- WHEN there is only one
- THEN the indicator passes

#### Scenario: Offline measurement
- WHEN the measuring tool reads all kept traces without any model call
- THEN it counts per case the sessions with one message and with several, ignoring replay traces, and names the runs with several messages; it can restrict to one case, lists the affected runs on request, and prints the share of multi-message sessions, and with no trace it prints that none was found

Source: tests/posture_evals/test_posture_evals.py (DernierEchange), tests/posture_evals/test_final_messages_check.py (SortieDeLEntreePrincipale)

### Requirement: Posture tag placement indicator
The system SHALL, for every case with an expected posture other than "none", report as a non-blocking indicator whether the first non-blank line of the final answer starts with the expected posture tag in the run language's format. On failure, the justification SHALL quote that first line, cut to 80 characters. The indicator SHALL count in neither the total nor the regressions. It SHALL become blocking only with the user's agreement, after the evaluation runs of this change.

Source: to be covered by `tests/posture_evals/test_posture_evals.py` (task 3.2)

#### Scenario: Tag first
- WHEN the final answer starts with the expected tag
- THEN the indicator passes

#### Scenario: Tag at the end
- WHEN the final answer holds the expected tag only after other text
- THEN the indicator fails, quotes the first line, and the blocking posture check is not affected by placement

#### Scenario: No expected posture
- WHEN the expected posture is "none" or absent
- THEN no placement indicator is produced

