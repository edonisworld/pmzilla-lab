# posture-evals-judge Specification

## Purpose

Describes how criteria that require reading are judged by a model: the prompt, the answer it reads, the strict parsing of verdicts and the failure modes.

## Requirements

### Requirement: Judge prompt per language
The system SHALL send the judge a prompt in the language of the run (French or English) that contains the question, the tools called, the sections returned by the library, chapter mentions, the assistant's answer and the numbered criteria, and asks for a JSON object of verdicts under the language-specific key. The English prompt SHALL NOT contain the French key. The French prompt SHALL remain unchanged.

#### Scenario: French judge
- WHEN a French case is judged
- THEN the prompt starts in French and, with no tools or answer, shows the "none" placeholders

#### Scenario: English judge
- WHEN an English case is judged
- THEN the English prompt is used, its verdict key is read and verdicts are returned in the usual structure

Source: tests/posture_evals/test_posture_evals.py (Langue)

### Requirement: Judge runs in a neutral folder
The system SHALL run the judge as a non-interactive call from a neutral folder that carries no project instructions, with structured output, and with the judge model passed on. The judge model SHALL default to Sonnet, justified by the calibration of 2026-10-09 (rejudging the same traces with Sonnet instead of the default judge changed 0 verdicts out of 55 checks), and SHALL be replaceable by an explicit choice; the tested sessions SHALL keep the usual model of Claude Code by default.

#### Scenario: Command
- WHEN the judge is invoked
- THEN the command carries the prompt including the criteria, an output format, and the neutral folder exists

#### Scenario: Judge model
- WHEN a judge model is chosen
- THEN it is the last option of the command

#### Scenario: Default judge model
- WHEN no judge model is given
- THEN the judge command names Sonnet as its model, and the tested sessions are started without a model option

Source: tests/posture_evals/test_posture_evals.py (Juge)

### Requirement: Strict verdict parsing
The system SHALL take each verdict's pass value only from a true boolean, SHALL pair verdicts with criteria by position using the criterion text of the case, SHALL treat missing verdicts as failures with the justification "no usable judgement", and SHALL fail all criteria when the output is not usable JSON, lacks the verdict list, or the call times out.

#### Scenario: Non-boolean values
- WHEN a verdict says "true" as a string, a number, or omits the value
- THEN the criterion fails

#### Scenario: Fewer verdicts than criteria
- WHEN fewer verdicts than criteria are returned
- THEN the missing ones fail with the "no usable judgement" justification

#### Scenario: Unreadable output or timeout
- WHEN the output is plain text, broken JSON, an empty result, another key, or the judge times out
- THEN all criteria fail

Source: tests/posture_evals/test_posture_evals.py (Juge)

### Requirement: No criteria, no call
The system SHALL NOT invoke the judge for a case with no judged criteria.

#### Scenario: Case without criteria
- WHEN a case has none
- THEN an empty verdict list is returned and no command runs

Source: tests/posture_evals/test_posture_evals.py (Juge)

### Requirement: Non-blocking judged criteria
The system SHALL accept judged criteria written as text (blocking) or as a record with text and a non-blocking mark (indicator), SHALL send only the criterion text to the judge, and SHALL flag verdicts of non-blocking criteria as indicators.

#### Scenario: Mixed criteria
- WHEN a case has a text criterion and a non-blocking record
- THEN the judge prompt lists both numbered, without the mark, and only the second verdict is an indicator

Source: tests/posture_evals/test_posture_evals.py (CritereJugeNonBloquant)

### Requirement: The judge reads every message of the last exchange
The system SHALL give the judge the single answer unchanged when there is one message, and otherwise all messages of the last exchange in order, each preceded by a separator giving its rank and the total, with a note stating the count and that criteria apply to all together, in the run language.

#### Scenario: Two messages
- WHEN the last exchange has two messages
- THEN the judge sees a note of two successive messages and both texts in order, including the Critic message

#### Scenario: One message
- WHEN there is one
- THEN the judge input is the answer unchanged

Source: tests/posture_evals/test_posture_evals.py (DernierEchange)

### Requirement: Shipped judged criteria
The system SHALL keep in the shipped cases a sources-paragraph criterion as a non-blocking indicator and the "weight of a book" criterion blocking, with the three source-structure checks blocking. The blocking total of the shipped cases is a snapshot, not a requirement.

#### Scenario: Classification
- WHEN the shipped judged criteria and source-structure checks are read
- THEN the sources-paragraph criterion is an indicator and the other named ones are blocking

Source: tests/posture_evals/test_posture_evals.py (CritereJugeNonBloquant)
