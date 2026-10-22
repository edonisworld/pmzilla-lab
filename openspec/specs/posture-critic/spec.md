# posture-critic Specification

## Purpose
Critic is the fifth PMZilla posture, a sub-agent that contests a deliverable produced by one of the four other postures. This spec describes what the agent definition makes it do (what it checks, what it may read, what it produces, its language) and how the project instructions call it: when it applies, in the foreground, with only the request and the deliverable, and how its answer is restored in the single final message. The extraction of Critic's objections from saved deliverables (the mirror) and the evaluation checks are described elsewhere (posture-evals-checks).

Source of truth: `.claude/agents/pmzilla-critic.md`, `CLAUDE.md` (routing protocol, step 4), `.claude/commands/journal.md` (mode `review`), `tests/postures/cas.yaml` (case `delivery-diagnostic-critic`), `tests/critic_mirror/test_critic_mirror.py` (VocabulaireCommun).

## Requirements

### Requirement: Critic applies to a deliverable only
The system SHALL call Critic when the answer is a deliverable the user will rely on to decide: a diagnosis, plan, workshop design or synthesis the user asks to keep, or a diagnosis built from data the user supplied. It SHALL NOT call Critic on a framing answer (hypotheses, context questions, leads without data or without a request to keep) nor on a purely informative answer.

#### Scenario: Diagnosis kept from supplied data
- **WHEN** the user supplies flow figures, asks for a diagnosis and asks to keep it
- **THEN** the posture produces the diagnosis and calls Critic

#### Scenario: Framing answer
- **WHEN** the answer only asks context questions or lists hypotheses to check
- **THEN** Critic is not called

Source: tests/postures/cas.yaml (delivery-diagnostic-critic, rule `critic: true`); the excluded side (framing answer without Critic) has no shipped case

### Requirement: Critic is never alone
The system SHALL activate Critic only on a deliverable another posture has just produced, and SHALL NOT answer a request with Critic alone or end the final message with Critic's section only.

#### Scenario: Critic in a final message
- **WHEN** Critic has reviewed a deliverable
- **THEN** the final message also carries the posture's own answer before the Critic section

Source: CLAUDE.md (postures table, routing step 4); .claude/agents/pmzilla-critic.md; untested

### Requirement: Critic runs in the foreground with the request and the deliverable only
The system SHALL call Critic in the foreground and wait for its answer before ending the turn, passing it only the initial request and the deliverable. It SHALL NOT run Critic in the background, pass it the posture's reasoning, or send a message announcing that Critic's result will follow.

#### Scenario: Critic called
- **WHEN** a posture calls Critic on a deliverable
- **THEN** the turn ends only after Critic has answered, and Critic received no reasoning

Source: CLAUDE.md (routing step 4); .claude/agents/pmzilla-critic.md (description); tests/posture_evals/test_posture_evals.py (DernierEchange, non-blocking indicator of a single final message)

### Requirement: The final message restores Critic in a fixed order
The system SHALL deliver one final message in this order: the posture's answer with its analysis and key points; a short Critic section headed by the posture tag with `Critic` as the name, summarising the objections in a few lines; the posture's reading under the title "Ma lecture de cette critique" or "My reading of this critique". It SHALL NOT replace this by a pointer to a file.

#### Scenario: English deliverable
- **WHEN** a deliverable in English has been reviewed
- **THEN** the message holds the answer, a section tagged `[Posture: Critic]`, then "My reading of this critique" saying what is kept and set aside and why

Source: CLAUDE.md (routing step 4, fixed-formula table); tests/postures/cas.yaml (delivery-diagnostic-critic, judged criterion on Critic's challenge)

### Requirement: A saved deliverable keeps Critic's full answer
The system SHALL keep Critic's full answer in the file of a saved deliverable and give only its summary in the message. For the kept audit of a pasted story or epic, the file SHALL hold the verdicts, the learning points and a summary of each objection alone, and SHALL NOT quote or reword the pasted text.

#### Scenario: Saved diagnosis
- **WHEN** a reviewed diagnosis is saved
- **THEN** the file holds Critic's full answer and the message holds the summary

#### Scenario: Kept story audit
- **WHEN** the audit of a pasted story is kept
- **THEN** the file names each objection (for example an untestable acceptance criterion) without any part of the story's text

Source: CLAUDE.md (routing step 4, exception of the kept audit); untested

### Requirement: Critic contests and does not validate
The system SHALL make Critic challenge the deliverable without validating or enriching it, checking output versus outcome, framework dropping, assumed maturity, cause versus symptom, agile clichés, politics and power, leverage, unverifiable sources, and a mere restatement of the user's published positions. Critic SHALL NOT be diplomatic or spare the previous posture.

#### Scenario: Cliché recommendation
- **WHEN** a deliverable recommends a dedicated PO without questioning the root cause
- **THEN** Critic flags it as an agile anti-pattern

Source: .claude/agents/pmzilla-critic.md (Mission, What you systematically check); untested

### Requirement: Critic reads only the library
The system SHALL give Critic only the library search and passage reading tools, over the whole library without a domain filter, and Critic SHALL cite a passage it relies on as *Author, Title*, section. Critic SHALL NOT invent a citation and has no other tool.

#### Scenario: Counter-argument from a book
- **WHEN** Critic finds a passage that contradicts the deliverable
- **THEN** its critique cites the author, the title as in the library and the section

Source: .claude/agents/pmzilla-critic.md (front matter `tools`, The library as ammunition); untested

### Requirement: Critic produces two to four dry critiques
The system SHALL make Critic produce 2 to 4 critiques of one sentence each, with an optional one-sentence improvement at the end, with no emoji and no pleasantries. Critic SHALL NOT be obliged to fix the deliverable.

#### Scenario: No clear improvement
- **WHEN** Critic sees blind spots but no clear improvement
- **THEN** it lists the critiques and adds no improvement line

Source: .claude/agents/pmzilla-critic.md (What you produce); untested

### Requirement: Critic answers in the deliverable's language
The system SHALL make Critic answer in the language of the deliverable, French by default, with that language's section headings ("Ce que Critic conteste", "Objections de Critic", "Revue de Critic" or "What Critic challenges", "Critic's objections", "Critic's review") and source-separation formulas. Critic SHALL NOT mix the two languages.

#### Scenario: French deliverable
- **WHEN** Critic reviews a French deliverable
- **THEN** it writes in French with "J'en déduis", "Hypothèse" and "hors bibliothèque"

#### Scenario: Headings recognised in both languages
- **WHEN** the shared vocabulary is read
- **THEN** the French and English Critic headings are both recognised as the start of a Critic section

Source: .claude/agents/pmzilla-critic.md (Language); tests/critic_mirror/test_critic_mirror.py (VocabulaireCommun)

### Requirement: The journal period review is passed to Critic
The system SHALL pass a period review of the coaching journal to Critic, which checks that each conclusion rests on several sessions and that none targets a person, with the same foreground call and final-message order. It SHALL NOT save the review unless the user asks to keep it.

#### Scenario: Journal review
- **WHEN** the user asks for a review of the journal
- **THEN** Critic is called on the review and the message ends with "Ma lecture de cette critique" or its English form

Source: .claude/commands/journal.md (mode `review`); untested

## Open questions

- No test reads the agent definition (its tool list, its number of critiques, its language rule): is a structural check of `.claude/agents/pmzilla-critic.md` wanted?
- No shipped case checks the excluded side (`critic: false` on a framing answer).
