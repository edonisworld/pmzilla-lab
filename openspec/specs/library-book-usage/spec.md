# library-book-usage Specification

## Purpose
Aggregated usage of the library books by the postures: `tools/book_usage.py`, run by the user alone, collects counts per turn from the Claude Code session transcripts (passages returned, read, cited, "outside the library" formulas) into a local ledger, and writes an untracked French report with the books never used; no text and no name is ever kept (work-queue job R-52). The ledger is the durable trace of this usage: Claude Code deletes old session transcripts after its cleanup period (setting `cleanupPeriodDays`, absent from the user and project settings on 2026-10-17, so the documented default of 30 days applies), after which those turns can no longer be collected.
## Requirements
### Requirement: Collect aggregated usage from the session transcripts of the workspace
The system SHALL provide a collect subcommand that reads the Claude Code session transcripts of the configured workspace project folders and, for each completed turn not yet counted, appends to a local ledger in the data folder one aggregated record per turn and bucket (design.md D2 and D3). A turn SHALL be collected only when it has a final answer and its transcript was not modified within a configurable delay. The subcommand SHALL print the collect summary key phrase of design.md D1 and exit with the codes of design.md D1. It SHALL NOT count a turn twice when a transcript is read again, SHALL NOT rewrite existing records, and SHALL NOT read the transcripts of any other project folder, including the disposable copies of the posture evaluation set and the raw evaluation traces.

Source: tests/book_usage/test_collect.py (Collect)

#### Scenario: New turns
- **WHEN** a transcript holds two completed turns not in the ledger
- **THEN** two records are appended and the summary says "tours ajoutés : 2"

#### Scenario: Read again
- **WHEN** collect runs twice on the same transcripts
- **THEN** the second run appends nothing and reports the turns as "déjà comptés"

#### Scenario: Running session
- **WHEN** the last turn of a transcript has no final answer, or the transcript was modified within the delay
- **THEN** that turn is not collected and is collected by a later run once complete

#### Scenario: Evaluation copies
- **WHEN** transcripts exist under a project folder that is not configured
- **THEN** none of them is read

#### Scenario: Unreadable transcript
- **WHEN** one transcript file or line cannot be parsed
- **THEN** it is skipped and counted in "illisibles", the other transcripts are collected, and the exit code is 0

#### Scenario: Folder missing
- **WHEN** no configured project folder exists
- **THEN** the subcommand prints "Dossier des transcriptions introuvable", writes nothing and exits 2

### Requirement: Attribute each turn to a posture bucket
The system SHALL attribute the library usage and the final answer of a turn to one bucket read from the posture tags of the main-thread final answer, in either language format and with exact posture names: the single posture named, "plusieurs postures" when several postures are named, "sans posture" when none is. The library calls of the Critic sub-agent, and its final answer taken from the result of its Agent call returned to the main thread (or, when that result is absent, from the last non-empty text of the sub-agent), SHALL be counted in the bucket "Critic", separately from the calling posture, and a Critic tag in the main-thread answer SHALL NOT make the turn multi-posture. The system SHALL NOT guess a posture from the content of the question, and SHALL NOT count a misspelt, accented, translated or recased tag as a posture.

Source: tests/book_usage/test_attribution.py (Attribution)

#### Scenario: One posture
- **WHEN** the final answer starts with the Delivery tag in the English format
- **THEN** the turn's usage is counted for Delivery

#### Scenario: Switch
- **WHEN** the final answer holds a Delivery tag and a switch to Scaling
- **THEN** the turn is counted in "plusieurs postures"

#### Scenario: Critic sub-agent
- **WHEN** the posture calls Critic, which searches the library, and the final answer carries the posture tag and the Critic section tag
- **THEN** Critic's searches are counted for Critic, the posture's own calls for the posture, and the turn is not multi-posture

#### Scenario: No tag
- **WHEN** the final answer carries no posture tag, or only a misspelt one
- **THEN** the turn is counted in "sans posture"

### Requirement: Count passages returned, passages read and citations per book
The system SHALL count, per book file identifier and per bucket, the passages returned by searches, the read calls whose anchor passage belongs to the book, one citation per turn when the final answer names the book (catalogue title, or its part before a colon, compared without case or accents) and the book was returned or read during that turn, and the turns in which the book was returned, read or cited (design.md D4). It SHALL NOT count as cited a book named in an answer without having been returned or read in that turn, and SHALL NOT count a citation twice in one turn.

Source: tests/book_usage/test_counts.py (Counts)

#### Scenario: Read and cited
- **WHEN** a turn returns three passages of a book, reads one of them, and names the book in the final answer
- **THEN** the book has 3 passages returned, 1 passage read, 1 citation and 1 turn for that bucket

#### Scenario: Named without use
- **WHEN** the final answer names a book that no search returned and no read touched in the turn
- **THEN** no citation is counted for that book

#### Scenario: Accents and subtitle
- **WHEN** the answer names a book by the part of its catalogue title before the colon, with other case or accents
- **THEN** the citation is counted

### Requirement: Count books only, never watch or personal articles
The system SHALL count and list only the documents of the library outside the watch collection and the personal collection, matched by exact collection name, SHALL drop hits on articles at collection time, and SHALL NOT write any article identifier or title in the ledger or the report.

Source: tests/book_usage/test_counts.py (Counts), tests/book_usage/test_reader.py (Lecteur)

#### Scenario: Mixed hits
- **WHEN** a search returns passages of a book, of a watch article and of a personal article
- **THEN** only the book is counted and the ledger holds no identifier of the two articles

### Requirement: Record only aggregated counts in the ledger
The system SHALL write in each ledger record only a one-way key derived from the session and turn, the day of the turn, the bucket, the per-book counts keyed by book file identifier, the number of "outside the library" formulas and a record version (design.md D3). The system SHALL NOT write in the ledger any query, passage identifier, section, book or article text, user or assistant text, title, session identifier in clear, time of day, or person, team or project name. The ledger SHALL be readable by its owner only.

Source: tests/book_usage/test_ledger.py (Registre)

#### Scenario: Sentinels absent
- **WHEN** synthetic transcripts carry sentinel strings in the user message, the search query, the passage text, the section, the assistant answer and a fake person name
- **THEN** none of the sentinels appears in the ledger, and the ledger file has owner-only permissions

#### Scenario: Session identifier
- **WHEN** a turn is recorded
- **THEN** the session identifier of the transcript does not appear in the ledger

### Requirement: Write a French usage report over a period
The system SHALL provide a report subcommand that reads the ledger and the list of books of the library and writes one French Markdown report in the report folder of design.md D6, with the title, period line, availability line and sections of design.md D6 in that order, and prints "Rapport écrit : <chemin>". The period SHALL default to the whole ledger and SHALL be bounded inclusively by optional start and end dates. With no turn in the period it SHALL still write the report with the key phrase "Aucun tour de posture dans la période". It SHALL exit with the codes and key phrases of design.md D1. It SHALL NOT write the report anywhere else, and SHALL NOT replace a report of another day.

Source: tests/book_usage/test_report.py (Rapport)

#### Scenario: Usual report
- **WHEN** the ledger holds turns of several postures in the period
- **THEN** the report has the sections "Par livre", "Par posture", "Livres jamais cités", "Livres jamais lus ni cités", "Livres du domaine jamais cités, par posture" and "Lacunes par posture" in that order

#### Scenario: Period bounds
- **WHEN** start and end dates are given
- **THEN** only records whose day is within both bounds are counted, and the period line shows those dates

#### Scenario: Bad dates
- **WHEN** a date is not a calendar date, or the start is after the end
- **THEN** the subcommand prints "Date invalide : <valeur>" or "Période vide : début après fin", writes nothing and exits 1

#### Scenario: Empty period
- **WHEN** no record falls within the period
- **THEN** the report is written with "Aucun tour de posture dans la période" and lists every book as never cited

### Requirement: List the books never used, per posture domain too
The system SHALL list the books of the library with zero citations in the period, the books with zero reads and zero citations, and, for Discovery, Delivery, Scaling and Facilitation, the books of the posture's library domains that this posture never cited. The posture-to-domains mapping SHALL agree with the postures table of the session instructions, and a test SHALL fail when they differ. The system SHALL NOT list a book outside the library, and SHALL NOT infer a domain from a book's title.

Source: tests/book_usage/test_report.py (Rapport), tests/book_usage/test_consistency.py (Correspondance)

#### Scenario: Never cited
- **WHEN** a library book was read in the period but never cited
- **THEN** it appears under "Livres jamais cités" with its read count and not under "Livres jamais lus ni cités"

#### Scenario: Domain of a posture
- **WHEN** a book of the facilitation collection was cited by Delivery only
- **THEN** it appears among Facilitation's never-cited domain books

#### Scenario: Mapping drift
- **WHEN** the postures table of the session instructions gives a posture other domains than the tool's mapping
- **THEN** the consistency test fails naming the posture

### Requirement: Count the "outside the library" formulas per posture
The system SHALL count, per bucket, the turns whose final answer holds the "outside the library" formula of either language and the number of such formulas, and SHALL report them under "Lacunes par posture". It SHALL NOT copy the sentence or the subject that follows the formula.

Source: tests/book_usage/test_counts.py (Counts), tests/book_usage/test_report.py (Rapport)

#### Scenario: Both languages
- **WHEN** a French answer holds the French formula twice and an English answer holds the English formula once, both for Scaling
- **THEN** Scaling has 2 turns and 3 formulas, and no text after the formulas appears in the report

### Requirement: Read the book list from the library database, read-only
The system SHALL read the books, their catalogue titles and their collections from the library database under the read-only role with a short connection timeout, and SHALL print "Bibliothèque injoignable (<type d'erreur>)" with the error type only, write no report and exit 2 when the database does not answer. It SHALL NOT open the library content folders, the image folder, the watch folders, the agents' memory or any book file.

Source: tests/book_usage/test_reader.py (Lecteur, BaseFactice, DossiersDeContenu), tests/book_usage/test_report.py (Rapport) ; database class tests/book_usage/test_book_usage_db.py (ListeDesLivresSurBaseJetable), run with the database test script

#### Scenario: Database down
- **WHEN** the library database does not answer
- **THEN** the report subcommand prints the key phrase with the error type, writes no report and exits 2

#### Scenario: No content folder opened
- **WHEN** collect and report run with watchers on file access under the library, image and watch folders
- **THEN** no file under those folders is opened

### Requirement: Keep every output free of text and names
The system SHALL write in the report and on the console only catalogue titles, book file identifiers, collection names, bucket names, dates, counts and the key phrases of design.md D1. It SHALL NOT write any book or article text, query, section, passage identifier, user or assistant text, session identifier, error message, or person, team or project name, and SHALL NOT open a network connection or write to the database.

Source: tests/book_usage/test_outputs.py (Sorties), tests/book_usage/test_reader.py (DossiersDeContenu)

#### Scenario: Sentinels in the report
- **WHEN** the report is written from transcripts carrying sentinel strings in every text field
- **THEN** neither the report nor the console output holds any sentinel

#### Scenario: No network
- **WHEN** collect and report run under a guard that fails any non-loopback connection
- **THEN** both succeed without triggering the guard

