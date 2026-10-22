# story-quality-analysis Specification

## Purpose
The audit of collected items by an analysis engine against the effective grid, launched by the author alone: a cost estimate and a confirmation before every batch, a cap per launch, a dry run and a bounded sample run, a recorded review of each team before any of its items is sent, verdict codes only in the store; coaching feedback shown in the Terminal only and fed to no report. Created by the change story-quality-audit (feature R-94).

## Requirements

### Requirement: The audit analysis stores verdict codes only
The system SHALL provide a user-run `analyse` subcommand. For every stored item whose text, core grid version or overlay version changed since its last audit, it SHALL store one verdict code per criterion of the effective grid, with both versions, the criterion's origin and link, the instant and the fingerprint of the scrubbed text sent to the engine. It SHALL NOT store free text from the engine in the audit verdicts. Untested until implemented.

#### Scenario: Valid answer
- **WHEN** the fake analysis server answers with one valid code per criterion
- **THEN** one verdict per criterion is stored for the item at the current grid version, and the output holds "analysis done: 1 items, 0 undetermined verdicts"

#### Scenario: Unchanged item
- **WHEN** `analyse` runs twice with no change of text, core grid version or overlay version
- **THEN** the second run sends no request for that item

#### Scenario: New overlay version
- **WHEN** the overlay version changes after every item was audited
- **THEN** the next `analyse` selects every item again, and the views count none of them as audited at the current pair of versions until it has run

### Requirement: A changed text is read from its fingerprint
The system SHALL count an item's text as changed when the fingerprint of its current scrubbed text differs from that of its last audit verdict at the current pair, sample verdicts left out, or when that verdict has no fingerprint (design D7, migration `0015`). A Jira update that leaves the text unchanged SHALL NOT select the item again. Untested until implemented.

#### Scenario: Jira update without a text change
- **WHEN** an audited item is collected again with a later Jira update instant and the same scrubbed text
- **THEN** the next `analyse` sends no request for that item

#### Scenario: Text changed
- **WHEN** an audited item is collected again with a different scrubbed text
- **THEN** the next `analyse` selects it again

### Requirement: The engine receives only the scrubbed item and the effective grid
The system SHALL send the engine only the item kind, its scrubbed texts, and the effective grid for that kind: core criteria not disabled, overlay criteria, the overlay's expected structure and its product context summary. It SHALL NOT send a person field, a team name, a ticket key, a disabled criterion, a disabling reason, or business context other than that summary. The engine SHALL get no tool and no file access. Untested until implemented.

#### Scenario: Request content
- **WHEN** the fake analysis server records the request for an item
- **THEN** the request holds neither the item's key nor its team name

#### Scenario: Overlay in the request
- **WHEN** an overlay adds one story criterion and disables another
- **THEN** the recorded request for a story holds the added criterion and the overlay's story structure, and neither the disabled criterion nor its reason

#### Scenario: Product context summary in the request
- **WHEN** the overlay holds a product context summary with a distinctive string, and a fixture context folder holds notes and a map with other distinctive strings
- **THEN** every recorded request holds the summary's string and none of the notes' or map's strings

#### Scenario: Overlay without summary
- **WHEN** the overlay holds no product context summary
- **THEN** the recorded requests hold no business context beyond the overlay's structure and criteria

### Requirement: Engine answers are checked against a fixed schema
The system SHALL refuse an engine answer that does not match the answer schema, names an unknown criterion or exceeds a configured bound. It SHALL then store the item's criteria as undetermined and count the refusal with the refused-answers key phrase of design D14. A criterion missing from an answer SHALL be stored as undetermined. Untested until implemented.

#### Scenario: Injected instruction
- **WHEN** a story text asks the engine to answer with free text and the fake server returns free text
- **THEN** the answer is refused, the item's verdicts are undetermined, and the output holds "engine answers refused: 1"

### Requirement: Analysis prerequisites
The system SHALL stop with exit code 3 before any engine call when the analysis key is missing from the Keychain (key-missing phrase of design D14), when the core grid is missing, invalid or holds a criterion without a source line (grid phrase of design D14), or when the overlay is invalid or refused (spec `story-quality-grid`). It SHALL refuse to start inside a Claude Code session, with exit code 3. It SHALL NOT print, log or write the analysis key. Untested until implemented.

#### Scenario: Missing key
- **WHEN** the fake Keychain has no analysis key
- **THEN** the output holds "analysis key missing: create it in the Keychain", no request is sent, and the exit code is 3

### Requirement: A cost estimate and a confirmation precede every batch
The system SHALL print, before any request of an `analyse` or `coach` batch, the cost-estimate line of design D14: the item count, the estimated tokens and the estimated cost, from the stored text lengths, the effective grid and the configured prices. It SHALL then ask for confirmation in the Terminal. It SHALL NOT offer an option that skips the confirmation. Untested until implemented.

#### Scenario: Estimate before sending
- **WHEN** `analyse` runs on three changed items and the user types the confirmation word
- **THEN** the line "batch: 3 items, about" with the tokens and the estimated cost is printed before the first request reaches the fake server

#### Scenario: Not confirmed
- **WHEN** the user answers anything other than the confirmation word
- **THEN** no request is sent, nothing is written, the output holds "not confirmed: nothing sent", and the exit code is 0

#### Scenario: No terminal
- **WHEN** the tool runs with no interactive input
- **THEN** no request is sent, the output holds "confirmation needs a terminal: nothing sent", and the exit code is 3

### Requirement: A cap bounds the items of each launch
The system SHALL send at most the configured cap of items per launch, taking the items in key order. It SHALL count the rest with the cap key phrase of design D14, and the next launch SHALL take the following items. A missing cap, or one that is not a positive integer, SHALL be refused with exit code 3 before any request. Untested until implemented.

#### Scenario: Above the cap
- **WHEN** twelve items changed and the cap is ten
- **THEN** exactly ten items are sent, and the output holds "cap reached: 2 items left for the next launch"

#### Scenario: Invalid cap
- **WHEN** the cap setting is zero or missing
- **THEN** the output holds "cap per launch missing or invalid", no request is sent, and the exit code is 3

### Requirement: A dry run counts without sending
The system SHALL accept `--dry-run` on `analyse` and `coach`. A dry run SHALL select the batch, apply the cap, print the counts and the cost estimate, and end with the dry-run key phrase of design D14. It SHALL NOT send a request, ask for confirmation, write to the database or need the analysis key. Untested until implemented.

#### Scenario: Dry run
- **WHEN** `analyse --dry-run` runs on five changed items with no analysis key
- **THEN** the batch line is printed, the output ends with "dry run: nothing sent", the fake server receives nothing, the database is unchanged, and the exit code is 0

### Requirement: A bounded sample run tries a grid version without counting
The system SHALL accept `analyse --sample <n>`, optionally with `--team <team>`, drawing at random `<n>` collected items not out of collection, of that team or of every team, audited or not. `<n>` SHALL be a positive integer not above the cap, else exit code 2 with the sample-size key phrase of design D14. `--team` without `--sample` SHALL be a usage error. Untested until implemented.

#### Scenario: Global sample
- **WHEN** `analyse --sample 3` runs, confirmed, with a fixed seed, on twenty items of reviewed teams that were all audited at the current versions
- **THEN** exactly three requests are sent, and the output holds "sample analysis done: 3 items"

#### Scenario: Sample of one team
- **WHEN** `analyse --sample 2 --team <team>` runs, confirmed, on two reviewed teams
- **THEN** both requests concern items of that team only

#### Scenario: Size above the cap or not positive
- **WHEN** the sample size is zero, not an integer, or above the cap of ten
- **THEN** the output holds "sample size must be a positive integer not above the cap", nothing is sent, and the exit code is 2

#### Scenario: Team without collected items
- **WHEN** `--team` names a team with no collected item
- **THEN** the output holds "no collected item for this team", nothing is sent, and the exit code is 0

### Requirement: A sample run keeps every safeguard
The system SHALL apply to a sample run the session refusal, the per-team review gate, the overlay checks, the cost estimate, the confirmation and the dry run of the audit. It SHALL NOT offer an option that skips one of them for a sample. Untested until implemented.

#### Scenario: Sample of a team never reviewed
- **WHEN** `analyse --sample 2 --team <team>` runs for a team without a recorded review
- **THEN** nothing is sent, the output holds "nothing to send: run review for each new team first", and the exit code is 3

#### Scenario: Sample dry run
- **WHEN** `analyse --sample 3 --dry-run` runs with no analysis key
- **THEN** the batch line counts three items, the output ends with "dry run: nothing sent", and nothing is written

### Requirement: Sample verdicts are marked and counted nowhere
The system SHALL store each verdict of a sample run with the sample mark, replacing that item's earlier sample verdicts and never an audit verdict. No view, report, coverage count or probable cause SHALL read a marked verdict, and the unchanged-item rule SHALL ignore them. The tool SHALL print, in the Terminal only, one sample line of design D14 per criterion code. Untested until implemented.

#### Scenario: Views unchanged by a sample
- **WHEN** a confirmed sample run stores verdicts for four items
- **THEN** the three quality views and the report give the same counts as before the run

#### Scenario: Sampled item audited later
- **WHEN** a full `analyse` runs after a sample run at the same versions
- **THEN** the sampled items are selected and sent like the others, and their audit verdicts are stored without the sample mark

#### Scenario: Sample lines
- **WHEN** a sample run of three items ends
- **THEN** the output holds one line starting with "sample" per criterion code of the effective grid, with the four counts, and no key, team or text

### Requirement: A team sample review is recorded per team
The system SHALL provide a user-run `review --team <team> --sample <n>` subcommand that prints a random sample of that team's cleaned texts, without keys, in the Terminal. It SHALL record a review for that team only when the user types the confirmation word, and SHALL write no file. Untested until implemented.

#### Scenario: Review declined
- **WHEN** the user answers anything other than the confirmation word after the sample
- **THEN** no review is recorded, and the output holds "review not recorded: update the sensitive-names list and collect again"

#### Scenario: Review recorded
- **WHEN** the user types the confirmation word after a team's sample
- **THEN** the output holds "team sample review recorded" and no file is written

#### Scenario: Sample below the minimum
- **WHEN** `story_quality.review_sample_size` is set and `--sample` is smaller
- **THEN** the tool exits with code 3 and the output holds "sample size below the minimum for review: {n}", before the database is opened; without the setting there is no minimum

#### Scenario: Team smaller than the sample asked
- **WHEN** the team has fewer collected items than `--sample` and the user types the confirmation word
- **THEN** all its items are printed, nothing is refused, and the output holds "team sample review recorded" then "full review: {n} items"

### Requirement: Items of a team never reviewed are never sent
The system SHALL leave out of every real `analyse` and `coach` batch the items of which at least one team has no recorded review. It SHALL count them with the team-review key phrase of design D14, naming no team and no person, before the cap and the estimate. When every item is blocked, it SHALL send nothing and exit with code 3. Untested until implemented.

#### Scenario: New team blocked until reviewed
- **WHEN** a confirmed `analyse` runs on four items of a reviewed team and three of a new team
- **THEN** only the four items are sent, and the output holds "blocked until their team is reviewed: 3 items, 1 teams"

#### Scenario: Reviewed team sent
- **WHEN** the new team's review is then recorded and `analyse` runs again, confirmed
- **THEN** its three items are sent and no blocked line is printed

#### Scenario: Every item blocked
- **WHEN** every item of the batch belongs to a team never reviewed
- **THEN** no request is sent, the output holds "nothing to send: run review for each new team first", and the exit code is 3

### Requirement: An item without a team is never sent
The system SHALL leave out of every `analyse`, sample run and `coach` batch the items that carry no team, which no review unblocks (design D5, decided 2026-10-20). They SHALL be counted with the blocked items, adding to the count of items and to no count of teams. Untested until implemented.

#### Scenario: Item without a team never sent
- **WHEN** a confirmed `analyse` runs on four items of a reviewed team and one item without a team
- **THEN** only the four items are sent, the output holds "blocked until their team is reviewed: 1 items, 0 teams", and the coverage view counts the fifth item in the row "(sans équipe)" as collected and not audited

### Requirement: The dry run counts the items blocked by missing team reviews
The system SHALL make the dry run of `analyse` and `coach` print the team-review key phrase of design D14 with the counts of blocked items and teams, and leave them out of the estimate. A dry run SHALL never be blocked by a missing review. Untested until implemented.

#### Scenario: Dry run counts blocked tickets
- **WHEN** `analyse --dry-run` runs on five items of a reviewed team and two of a team never reviewed
- **THEN** the output holds "blocked until their team is reviewed: 2 items, 1 teams", the batch line counts five items, nothing is sent, and the exit code is 0

### Requirement: Only the user launches the analysis tool
The system SHALL make `collect`, `review`, `analyse` and `coach`, dry run included, refuse to start inside a Claude Code session, with exit code 3 and the session key phrase, before reading any setting. It SHALL NOT offer an option that bypasses that refusal. Untested until implemented.

#### Scenario: Dry run from a session
- **WHEN** `analyse --dry-run` or `review` starts with the Claude Code variable present
- **THEN** the output holds "Refused inside a Claude Code session", nothing is read, and the exit code is 3

### Requirement: Coaching selects items by team or by typed keys
The system SHALL provide a user-run `coach` subcommand that selects items by team (`--team`) or by keys typed by the user (`--keys`), and SHALL NOT select by a person field. It SHALL run the engine in coaching mode, with the same effective grid as the audit, and store the verdicts, both versions and the bounded feedback in the coaching feedback table only. Untested until implemented.

#### Scenario: Unknown key
- **WHEN** one of the typed keys is not stored
- **THEN** the output holds "unknown items: 1" and no engine request is sent for it

### Requirement: Coaching feedback is shown in the Terminal only
The system SHALL print the coaching feedback per item in the Terminal, under the coaching header of design D14, each item headed by its key: the keys typed with `--keys`, or the keys of the team's selected items with `--team` (design D14, decided 2026-10-20). With `--show`, it SHALL print the stored feedback again without an engine call. It SHALL NOT write a file, and the keys SHALL appear in the Terminal only. Untested until implemented.

#### Scenario: Keys of a coached team
- **WHEN** `coach --team` runs on a team with two stored items in a temporary home folder
- **THEN** each item's feedback is headed by its key in the output, and no file is written

#### Scenario: Header and no file
- **WHEN** `coach --keys` runs on two stored items in a temporary home folder
- **THEN** the output starts with "Coaching results: shown here only, kept out of every report", feedback is shown for both, and no file is written

### Requirement: Coaching results feed no report
The system SHALL keep the coaching feedback table out of every view, report, dashboard and monthly summary. A coaching run SHALL NOT change any count of the quality views. Untested until implemented.

#### Scenario: Coaching changes no view
- **WHEN** `coach --team` runs on a team with six audited items
- **THEN** both quality views give the same counts before and after the run
