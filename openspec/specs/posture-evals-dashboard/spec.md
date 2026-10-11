# posture-evals-dashboard Specification

## Purpose

Describes the local dashboard: a single self-contained HTML page summarising follow-ups, the watch, the library, evaluation quality, flow changes and Critic's mirror, in French or English.
## Requirements
### Requirement: Self-contained page without content leaks
The system SHALL generate a single HTML page with seven sections (to-do, experiments awaiting a result, watch, library, quality, flow, Critic), with inline styles and charts, a dark-mode style, no script, no network address and no em dash, and SHALL NEVER include text or titles of articles or book passages. It SHALL exit successfully.

Source: tests/dashboard/test_dashboard.py

#### Scenario: All sources present
- **WHEN** every source is available
- **THEN** the page has the seven sections and none of the sentinel article or book texts, no script, no http address

#### Scenario: Chart readability
- **WHEN** charts are drawn
- **THEN** they use a full-width view box and legible text size, with a day/month date under each bar and a score under each point of the curve

### Requirement: Missing or unreadable sources
The system SHALL show "no data yet" in each section whose source is missing, SHALL show "unreadable source" for an unreadable source, SHALL never print a traceback into the page, and SHALL still write the page and exit with success.

#### Scenario: No source
- WHEN no source exists
- THEN the page says there is no data yet at least seven times and contains no traceback

#### Scenario: Corrupt sources
- WHEN the library database and the journal file are unreadable
- THEN the page is written with the common guarantees and shows "unreadable source"

Source: tests/dashboard/test_dashboard.py

### Requirement: Follow-ups from the journal
The system SHALL list from the coaching journal the overdue follow-ups, those due within seven days relative to today, and experiments whose review is due, each with counts in the heading.

#### Scenario: Dates
- WHEN today is after one follow-up's due date and three days before another
- THEN one is overdue and one upcoming, and one experiment review is due

Source: tests/dashboard/test_dashboard.py (donnees_completes, test_avec_toutes_les_sources)

### Requirement: Watch section
The system SHALL show, from the watch log, the new articles per day, sources in error, consecutive days of failure, pre-sort duration per run, pre-sort mode, shared links and the share of shared links that were proposed. It SHALL read the current log name and fall back on the former one, and the current sorting configuration folder before the former one. With a single pre-sorting run it SHALL write a sentence instead of a curve and use the singular.

#### Scenario: Errors
- WHEN a source errors on three consecutive days
- THEN the page shows it with "3 consecutive days"

#### Scenario: Single run
- WHEN only one run pre-sorted articles
- THEN a single sentence appears and "1 latest run" is in the singular

#### Scenario: Log and config names
- WHEN only the new log name exists
- THEN it is read; when a config exists in both folders the new one has priority and sets the mode badge

#### Scenario: Shared proposals
- WHEN one of two shared links had been proposed
- THEN the page shows "1 of 2"

Source: tests/dashboard/test_dashboard.py

### Requirement: Library section
The system SHALL list books without a known author, SHALL list books to re-download one per line without domain codes or explanatory sentences with a total, and SHALL count watch articles lacking an author or site separately from those displayed with a "not stated" author. The book and passage counts of the section SHALL exclude documents of the watch collection (current and former names) and of the personal collection, matched by exact collection name.

Source: tests/dashboard/test_dashboard.py

#### Scenario: Books
- **WHEN** one book lacks an author and another has one
- **THEN** only the former is listed

#### Scenario: To re-download
- **WHEN** the mapping comments name books
- **THEN** each appears as a line "Title (Author)", split correctly across "and"-joined and semicolon-separated entries, with the total

#### Scenario: Watch and personal collections excluded
- **WHEN** the library holds a book, a watch article and an article of the personal collection
- **THEN** only the book is counted

#### Scenario: Exact collection names
- **WHEN** a book belongs to a collection whose name merely contains the name of an excluded collection
- **THEN** the book is counted

### Requirement: Quality section from evaluation reports
The system SHALL draw the pass-rate curve and a cost table from the evaluation reports, using only complete runs, report the number of partial runs excluded, show the commit of the latest run, its cost, the month's total cost including partial runs, and display the number of latest complete runs. A run is complete when its total of verifications equals the total of the most recent report; every other run is partial. The history table SHALL show the models of each run when its report names them and SHALL flag a non-validating run; a non-validating run SHALL stay out of the curve and the case matrix, and its cost SHALL count in the month's total.

#### Scenario: Partial run
- WHEN a report has fewer verifications than complete runs
- THEN it is excluded from the curve and the table, its commit is not shown, and "1 partial run excluded" appears, but its cost counts in the month's total

#### Scenario: Partial criterion
- WHEN two older reports have fewer verifications than the most recent one and two reports have the same total as it, one of them with failures
- THEN the two older ones are counted as partial runs excluded, their commits are not shown, and the two others count as the latest complete runs; when every report has the same total, no run is partial, failures included

#### Scenario: More verifications than the latest report
- WHEN an older report has more verifications than the most recent one
- THEN it is counted as partial and excluded like a report with fewer

#### Scenario: Non-validating run
- WHEN a report names a session model other than the usual one and is marked not validating
- THEN the history table shows its models and a "not validating" flag, the curve and the case matrix omit it, and its cost counts in the month's total

#### Scenario: Report without models
- WHEN a report predates the models line
- THEN its models cell is a placeholder

Source: tests/dashboard/test_dashboard.py; tests/dashboard/test_language.py; tests/dashboard/test_gaps_dashboard.py (PassagePartiel, LecteurReelExperiences)

### Requirement: Flow and Critic sections
The system SHALL show the "what moved" lines of the latest flow evolution report, and for Critic the blind-spots of the latest mirror and the current month's objection count with its date range. When no mirror exists it SHALL announce the first one for early November; it SHALL remind of the flow follow-up as "to do" when the latest flow report is older than a month and "up to date" otherwise.

#### Scenario: Reminders
- WHEN no mirror exists and the latest flow report is old
- THEN the first mirror is announced and the flow follow-up is "to do" with the date; a recent report turns it "up to date"

Source: tests/dashboard/test_dashboard.py (test_rappels)

### Requirement: Page language
The system SHALL render the page in French by default or in English on request, translating headings, labels, sentences, dates, currency formatting and the document language, while keeping section identifiers, the formats read from other files and the invented data unchanged. Language catalogues SHALL be consistent with each other. Pluralisation SHALL follow the language. A former option name SHALL be accepted with a warning.

#### Scenario: English page
- WHEN the English language is chosen
- THEN the document language is English, the French tokens do not appear in visible text, ISO dates and dollar amounts are used, the title is the English one, and the output equals the stored reference snapshot

#### Scenario: Default is French
- WHEN no language is given
- THEN output equals the French option and states French as document language

Source: tests/dashboard/test_language.py; tests/dashboard/test_dashboard.py (test_anciennes_options)

### Requirement: Experiments awaiting a result
The system SHALL list, in the section of experiments awaiting a result, the configured author's running experiments ordered by review date, each with its number, problem, start date, review date, postponement count and a review-due flag, with the counts of running and due experiments in the heading. A review is due when its review date is today or earlier, the same rule as the journal and the MCP tool. It SHALL read them under the cases read-only role with a short connection timeout, SHALL show "no data yet" when no author is configured (without any read) or no experiment is running, SHALL show "unreadable source" with the error type only, never the error message, when the cases database does not answer, SHALL escape the problem text, and SHALL still write the page. The section SHALL come between the to-do section and the watch section.

#### Scenario: One due experiment
- **WHEN** the author has two running experiments, one whose review date is past
- **THEN** both are listed in review-date order, the past one flagged review due, and the heading counts two running and one due

#### Scenario: Review due today
- **WHEN** a running experiment has today as its review date
- **THEN** it is listed, flagged review due and counted as due in the heading, like in the journal and the MCP tool

#### Scenario: Database down
- **WHEN** the cases database does not answer
- **THEN** the section shows "unreadable source" with the error type and without the error message, and the other sections are unchanged

Source: tests/dashboard/test_dashboard.py (Experimentations)

## Open questions

None.
