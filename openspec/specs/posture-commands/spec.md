# posture-commands Specification

## Purpose

Describes the slash commands that put a posture to work on a given input: `/monthly-flow` (flow follow-up of a series), `/dependencies` (reading of the dependency map), `/adapt-message` (one diagnosis rewritten for several audiences), `/roundtable` (library authors confronted on a question), `/watch-digest` (weekly digest of the watch) and `/critic-mirror` (recurring Critic objections), with the mirror tool that extracts the objections. The work-queue and developer commands (`/next`, `/start`, `/batch`, `/implement`, `/close`, `/add-books`, `/audit`) belong to workflow-commands and workflow-roadmap; the computation of the flow and dependency reports belongs to the jira-flow capabilities.

## Requirements

### Requirement: Posture commands answer in the user's language
The system SHALL provide the posture commands `/monthly-flow`, `/dependencies`, `/adapt-message`, `/roundtable`, `/watch-digest` and `/critic-mirror` as command files written in English that answer in the language of the user's request, French by default, and write each fixed formula in its form for that language in the shared vocabulary. A command SHALL NOT mix both languages' formulas in one answer, and SHALL write roles, never a person's name.

#### Scenario: French request
- **WHEN** a posture command is run with a request in French
- **THEN** the answer is in French, with the French posture tag and the French out-of-library, inference, hypothesis and reading-of-the-critique formulas

#### Scenario: English request
- **WHEN** the same command is run with a request in English
- **THEN** the answer uses the English forms and no French formula

Source: .claude/commands/*.md; French answer and tag of `/monthly-flow` and `/watch-digest`: judged criteria of tests/postures/cas-commandes.yaml (evaluation run on request); otherwise untested

### Requirement: Posture commands restitute Critic in one final message
The system SHALL make `/monthly-flow`, `/dependencies`, `/adapt-message`, `/roundtable` and `/watch-digest` pass their deliverable to the Critic sub-agent in the foreground, with only the request and the deliverable, and end with a single message: the answer, a short section headed by the Critic tag, then the reading of the critique. They SHALL NOT call Critic in the background, end the turn before its answer, or announce a result to come.

#### Scenario: Deliverable produced
- **WHEN** one of these commands has produced its reading, versions, roundtable or digest
- **THEN** Critic is called once in the foreground and the final message holds the answer, the Critic section and the reading of the critique, in that order

Source: `critic` rule of both cases and judged order of the watch-digest final message: tests/postures/cas-commandes.yaml (evaluation run on request); otherwise untested

### Requirement: Posture commands save only where they are told
The system SHALL make `/monthly-flow`, `/dependencies`, `/adapt-message` and `/roundtable` save nothing unless the user asks to keep the result, then write it as a dated Markdown file in the command's output folder, the flow, dependency and message folders being ignored by Git. `/adapt-message` and `/roundtable` SHALL add a numeric suffix rather than overwrite a file. None of them SHALL write a file without that request.

#### Scenario: No request to keep
- **WHEN** the user does not ask to keep the reading
- **THEN** no file is written

#### Scenario: Same name on the same day
- **WHEN** a kept roundtable has the name of an existing file
- **THEN** it is written with a `-2` suffix and the existing file is unchanged

Source: .claude/commands/monthly-flow.md, dependencies.md, adapt-message.md, roundtable.md; untested

### Requirement: /monthly-flow reads the reports of one series
The system SHALL make `/monthly-flow [series]` use the given series name, or else the default series of the flow configuration, and ask for it and stop when neither exists. It SHALL read only the flow and evolution reports of that series. When the series has several flow reports but no evolution report as recent as the latest one, it SHALL stop and give the compute or compare command to run. It SHALL NOT read the Jira exports nor run that command.

#### Scenario: No name and no default
- **WHEN** no series name is given and the flow configuration has no default series
- **THEN** the command asks for the name and stops

#### Scenario: Evolution report missing
- **WHEN** two flow reports exist and no evolution report compares them
- **THEN** the command prints the computation command for the user and interprets nothing

#### Scenario: First series
- **WHEN** a single flow report exists for the series
- **THEN** the command says so and describes the state without a trend

Source: no export path in the answer: `without_text` rule of tests/postures/cas-commandes.yaml (cmd-monthly-flow, evaluation run on request); otherwise untested

### Requirement: /monthly-flow reading by Delivery or Scaling
The system SHALL make `/monthly-flow` have a series of ten teams or fewer read by Delivery, and a larger one by Scaling for the overview and by Delivery for the three teams that changed most clearly. The reading SHALL start with what comparability forbids concluding and give per signal two explanations, one a measurement cause, a check and a question for the team. It SHALL NOT rank or compare teams, nor comment a team on a first series.

#### Scenario: Team series
- **WHEN** the latest flow report lists four teams
- **THEN** the Delivery posture gives three to five changes with their hypotheses, the questions for the teams and what stays stable

#### Scenario: Product-wide series
- **WHEN** the latest flow report lists more than ten teams
- **THEN** Scaling gives the overview without any organisational proposal, Delivery comments three teams and says other readings are possible

Source: Delivery tag and judged criteria of tests/postures/cas-commandes.yaml (cmd-monthly-flow, evaluation run on request); product-wide reading untested

### Requirement: /dependencies opens with a verdict on the map
The system SHALL make `/dependencies [scope or path]` read the named dependency report, else the latest, and open after the posture tag with a verdict on what the map allows to conclude, from its warnings (unknown-state or untyped links, truncated exports, small samples). Without a report it SHALL stop and give the diagnose and compute commands. It SHALL NOT read the Jira exports, nor decide anything structural on a map mostly of unknown state.

#### Scenario: No report
- **WHEN** the reports folder holds no dependency report
- **THEN** the command prints the two commands for the user and reads nothing else

#### Scenario: Map mostly of unknown state
- **WHEN** most links of the report are of unknown state
- **THEN** the verdict says nothing structural can be decided and what to redo first

Source: .claude/commands/dependencies.md; untested

### Requirement: /dependencies reading by the Scaling posture
The system SHALL make `/dependencies` have the Scaling posture read loaded pairs, loops and site splits as hypotheses, interaction modes under the inference formula, old blockages as tickets to clean, the lead time gap as a correlation, two explanations per signal, open questions in roles, and actions from lightest to most structuring with a library limit. It SHALL NOT present that gap as the cost of dependencies, nor write a person's name or a ticket key.

#### Scenario: Interaction mode
- **WHEN** the reading names the interaction mode of a loaded pair
- **THEN** the mode is introduced by the inference formula, the report giving no actual mode

#### Scenario: Keys pasted by the user
- **WHEN** the user pastes ticket keys shown in the Terminal
- **THEN** no key is copied into the answer or a file

Source: .claude/commands/dependencies.md; untested

### Requirement: /adapt-message keeps one common ground across versions
The system SHALL make `/adapt-message <source> [audiences]` read a file or pasted text, extract a common ground (findings with their strength, limits, what is asked), ask at most one grouped question on each audience's expected action and channel, and write one version per audience, by default leadership, POs and team. No version SHALL add or change a finding or figure, promote a hypothesis, designate a culprit or rank teams.

#### Scenario: Audiences named
- **WHEN** the user names two audiences after the source
- **THEN** only those two versions are written

#### Scenario: Intent not given
- **WHEN** the source does not say what each audience must do and the user does not answer the grouped question
- **THEN** the default intents are used and the answer says so at the top

Source: .claude/commands/adapt-message.md; untested

### Requirement: /adapt-message has Critic check fidelity only
The system SHALL make `/adapt-message` ask Critic to judge only the fidelity of the versions to the common ground and to each other, correct each gap raised, and, when something was corrected, send Critic only the common ground and the corrected passages for a second pass. It SHALL NOT have Critic judge the diagnosis itself, run a third pass, or hide a remaining gap: it lists it under the points not corrected with its reason.

#### Scenario: Nothing corrected
- **WHEN** Critic raises no gap
- **THEN** no second pass is run

#### Scenario: Gap left after the second pass
- **WHEN** the second pass still finds a gap
- **THEN** the gap is listed among the points not corrected and no third pass is run

Source: .claude/commands/adapt-message.md; untested

### Requirement: /roundtable lets only the books speak
The system SHALL make `/roundtable <question> [| authors]` seat the named authors, or three to five library authors of different positions found by several book searches, and give each a thesis, an argument, conditions and a short original-language quotation with author, title and section. An author SHALL say only what their read passages say, in the third person. It SHALL NOT invent a dialogue, seat an author the library does not cover on the question, or seat two watch articles.

#### Scenario: Author without passage
- **WHEN** an invited author has no passage on the question in the library
- **THEN** that author does not take part

#### Scenario: Watch article
- **WHEN** a watch article is relevant
- **THEN** at most one sits at the end of the table, presented as not carrying the weight of a book

Source: .claude/commands/roundtable.md; untested

### Requirement: /roundtable confronts without fabricating
The system SHALL make `/roundtable` confront the two or three sharpest disagreements, saying for each whether it is a real disagreement or a difference of context and what would settle it, then give the points of agreement and what the library does not say, under the out-of-library formula, and ways to use it in a workshop or an article. A reply that is a transposition SHALL open with the inference or hypothesis formula. It SHALL NOT fabricate a disagreement the library does not hold.

#### Scenario: No real disagreement
- **WHEN** the library authors agree on the question
- **THEN** the roundtable says so and presents their nuances instead

Source: .claude/commands/roundtable.md; untested

### Requirement: /watch-digest reads the watch through the library
The system SHALL make `/watch-digest [days]`, seven by default, run the pre-sort's week inventory, read the inventory it writes, and group the articles into three to five themes, each tied to a posture and tagged. It SHALL read articles through the library only, the watch collection from the period start, and read a user's own article in full before citing it. It SHALL NOT read watch article files directly, nor keep an unread weak signal.

#### Scenario: Theme reading
- **WHEN** a theme is written
- **THEN** the library is searched in the watch collection from the start of the period, and the central passages are read

#### Scenario: User's own article
- **WHEN** the digest says a user's article agrees with or contradicts an author
- **THEN** the article was read in full through the library and is cited with title, date and link

Source: search of the watch collection: `tool` rule of tests/postures/cas-commandes.yaml (cmd-watch-digest, evaluation run on request); own collection named in the command: tests/pmzilla_lab_library/test_coherence_noms.py (test_watch_digest_nomme_la_collection_personnelle); otherwise untested

### Requirement: /watch-digest separates echo from convergence
The system SHALL make `/watch-digest` give per theme what the authors say and what it rests on, their divergences, what the library says, the user's positions when relevant, and questions; put a dated short reference in every sourced paragraph and open every other with the inference or hypothesis formula; and end with Sources listing articles only. It SHALL NOT call authors convergent without proof of independence, nor copy beyond a short quotation.

#### Scenario: Same publication
- **WHEN** two authors of the same publication reach the same finding
- **THEN** the digest calls it an echo or the same finding under the same conditions, not a convergence

#### Scenario: Subject outside the library
- **WHEN** the library does not cover a theme
- **THEN** the digest writes the out-of-library formula instead of inventing a source

Source: judged criteria and the date and source-structure rules of tests/postures/cas-commandes.yaml (cmd-watch-digest, evaluation run on request); otherwise untested

### Requirement: /watch-digest saves the digest with Critic's answer
The system SHALL make `/watch-digest` save the digest by default as a dated file of its output folder, with a numeric suffix rather than overwriting, keep Critic's full answer and the reading of the critique in it, and end with one message: path and three lines, Critic section, reading, then Sources last. It SHALL NOT commit the file, write a placeholder while Critic answers, or correct the digest except for a factual error or a badly cited source.

#### Scenario: Final message
- **WHEN** the digest is saved
- **THEN** the message gives the file path and three lines, then the Critic section, the reading of the critique, and Sources as its last section

Source: judged criterion on the final message order: tests/postures/cas-commandes.yaml (cmd-watch-digest, evaluation run on request); saving untested

### Requirement: /critic-mirror classifies the tool's corpus with the tool's grid
The system SHALL make `/critic-mirror [period]` get the corpus from the mirror tool in the request's language, stop with the raw list below five objections, and put each objection in exactly one category of the grid the tool prints, checking the classified total against the corpus count. It SHALL NOT read the deliverables, copy the grid into the command, rename or merge categories, or add a category: it only proposes one.

#### Scenario: Grid not copied
- **WHEN** the command file is read
- **THEN** it names the categories option of the tool and contains none of the category names of either language

#### Scenario: Too few objections
- **WHEN** the corpus holds four objections
- **THEN** the command says it is too early to speak of recurrence, gives the raw list and stops

Source: tests/critic_mirror/test_language.py (test_la_commande_ne_recopie_pas_la_grille); the rest untested

### Requirement: /critic-mirror proposes and saves the mirror
The system SHALL make `/critic-mirror` write a table of non-empty categories, the blind spots (the most recurrent categories touching at least two deliverables, with two examples each), the evolution against the previous mirror, one countermeasure per blind spot and the limits, then save it by default as the month's file of the mirror folder, adding a numeric suffix rather than overwriting. It SHALL NOT apply a countermeasure nor commit.

#### Scenario: Category touching one deliverable
- **WHEN** the most frequent category comes from a single deliverable
- **THEN** it is not presented as a blind spot

#### Scenario: Countermeasure
- **WHEN** a blind spot is found
- **THEN** a change acting before Critic is proposed and nothing is modified

Source: .claude/commands/critic-mirror.md; untested

### Requirement: Mirror period
The system SHALL make the mirror tool cover by default the current month up to today, or the whole previous month before the eighth day of the month. An explicit start and end SHALL be inclusive, and a start alone SHALL run to today. A former French option name SHALL be refused with exit code 2 and a message naming the current option. The tool SHALL NOT read a deliverable dated outside the period.

#### Scenario: Start of the month
- **WHEN** the tool runs on the fourth day of a month without options
- **THEN** the corpus covers the whole previous month

#### Scenario: Start only
- **WHEN** only a start date is given
- **THEN** the period runs from that date to today

#### Scenario: Former option
- **WHEN** a former French option name is used
- **THEN** the tool exits with code 2 and names the current option

Source: tests/critic_mirror/test_critic_mirror.py (Periode, Corpus)

### Requirement: Mirror corpus scope
The system SHALL make the mirror tool read every Markdown deliverable of the deliverables folder dated in the period, its date taken from a valid date in its file name or else from its modification time. It SHALL ignore the mirror folder, list apart the deliverables without a Critic section, and give zero counts when the folder is missing. It SHALL NOT classify objections nor read evaluation reports.

#### Scenario: Previous mirror
- **WHEN** a previous mirror holds a Critic section
- **THEN** none of its text enters the corpus

#### Scenario: Impossible date in the name
- **WHEN** a file name holds an impossible date
- **THEN** the file's modification date is used

#### Scenario: No folder
- **WHEN** the deliverables folder does not exist
- **THEN** the summary gives zero deliverables, zero objections and zero deliverables without a Critic section

Source: tests/critic_mirror/test_critic_mirror.py (Corpus)

### Requirement: Critic sections are recognised in both languages
The system SHALL recognise a Critic section opened by a Markdown heading naming Critic, or by a short plain line starting with a Critic section formula of the shared vocabulary in either language, ending at the next heading of the same or higher level, or, for a plain line, at any heading or end formula. Formulas SHALL come from the evaluation set's vocabulary file. A heading carrying a posture tag SHALL NOT open a section, and an empty section SHALL NOT count.

#### Scenario: Plain-line section
- **WHEN** a message holds a plain "What Critic challenges" line followed by a list and a "Corrections made" line
- **THEN** one section is found, ending before the corrections

#### Scenario: Heading with the Critic tag only
- **WHEN** the section heading is the Critic posture tag
- **THEN** no section is opened

#### Scenario: Formula added to the vocabulary
- **WHEN** a start formula is added to the vocabulary
- **THEN** patterns built from it recognise the new formula

Source: tests/critic_mirror/test_critic_mirror.py (Sections, VocabulaireCommun)

### Requirement: Objections are split and numbered without rewording
The system SHALL count one objection per top-level list item of a section, sub-items joined to their item, and the whole section as one objection when it has no list, removing quotation marks and a short posture tag line, and stopping at an improvement suggestion. Objections SHALL be numbered continuously across the corpus and copied in the deliverable's language. The tool SHALL NOT reword or translate an objection.

#### Scenario: Numbered list with a sub-item
- **WHEN** a section lists three numbered points, the first with a sub-item, followed by an improvement line
- **THEN** three objections are counted, the first including its sub-item, the improvement excluded

#### Scenario: Continuous numbering
- **WHEN** the corpus holds six objections in three deliverables
- **THEN** they are numbered O1 to O6

Source: tests/critic_mirror/test_critic_mirror.py (Sections, Corpus); tests/critic_mirror/test_language.py

### Requirement: Each deliverable is labelled with its kind and postures
The system SHALL label each deliverable with its relative path, date, kind (watch digest, adapted messages or posture deliverable, from its folder) and postures, read from the posture metadata line of the header, before the first second-level heading, and from posture tags, without duplicates. Critic and unknown names SHALL NOT count as postures; with none found the posture SHALL be shown as not stated.

#### Scenario: Metadata line forms
- **WHEN** the header holds "Posture:" or "Posture :" with bullets, bold, italics or several postures joined by a comma, "and", "et" or "+"
- **THEN** the leading known postures are read; a posture named later in the sentence is not

#### Scenario: Neither metadata nor tag
- **WHEN** a deliverable has a Critic section but no posture line and no tag
- **THEN** its posture is shown as not stated

Source: tests/critic_mirror/test_critic_mirror.py (PostureEnMetadonnee, Corpus)

### Requirement: Mirror output language and grid
The system SHALL print the corpus title with the period, a summary line counting deliverables with a Critic section, objections and deliverables without one, then each deliverable's objections, in French by default or English on request, the objection count staying readable in both. With the categories option it SHALL print only the eleven-category grid in the requested language. It SHALL NOT read deliverables for the grid.

#### Scenario: Default language
- **WHEN** no language is given
- **THEN** the output equals the French output and starts with "# Objections de Critic du"

#### Scenario: English output
- **WHEN** English is requested
- **THEN** the output equals the stored English snapshot, holds no French word outside copied objections and file names, and starts with "# Critic objections from"

#### Scenario: Grid
- **WHEN** the categories option is used
- **THEN** a table of eleven categories is printed, from "hypothèse prise pour un fait" to "autre" in French or "hypothesis taken as fact" to "other" in English, and no corpus line

Source: tests/critic_mirror/test_language.py

## Open questions

1. The six posture command files are not read by the workflow command test (header pre-approvals, forbidden actions, user's language): only `/critic-mirror` (grid not copied) and `/watch-digest` (own collection named) are pinned by a test. Whether they should join that test is not decided.
2. The roundtable output folder is not among the folders that the project instructions list as ignored by Git, unlike the flow, dependency and message folders; whether a kept roundtable is meant to be tracked is not stated.
3. A Critic section whose heading is only the Critic posture tag is not read by the mirror tool; a test pins this as current behaviour to know, not as a decision.
