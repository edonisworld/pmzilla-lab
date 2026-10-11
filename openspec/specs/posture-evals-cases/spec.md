# posture-evals-cases Specification

## Purpose

Describes the reference cases of the posture evaluation set: how they are read, normalized, translated into a language variant, filtered by prerequisites, and protected against unintended changes of what the judge receives. Also covers the shared vocabulary of fixed formulas.
## Requirements
### Requirement: Case files are read and unknown rules are refused
The system SHALL read the reference cases from a case file (the default file or an alternative file given on the command line), SHALL refuse to run when that file is missing, and SHALL refuse any automatic check rule it does not know how to apply.

#### Scenario: Missing case file
- WHEN the run is started with a case file that does not exist
- THEN the system stops with a "cases not found" message and plays nothing

#### Scenario: Unknown check rule
- WHEN a case contains a verification rule the system does not know
- THEN applying that rule stops the run with an error naming the rule

#### Scenario: Shipped cases are applicable
- WHEN the shipped case file is loaded
- THEN case identifiers are unique, each question is non-empty, each expected posture is one of the five postures or "none", and every verification rule can be applied

Source: tests/posture_evals/test_posture_evals.py (Verifications, Principal)

### Requirement: Case selection by identifier
The system SHALL let the user restrict a run to a comma-separated list of case identifiers and SHALL refuse identifiers that do not exist in the selected case file.

#### Scenario: Unknown identifier
- WHEN the user selects a case identifier absent from the selected case file
- THEN the system stops with a message "unknown cases" listing the missing identifiers

#### Scenario: Alternative file does not alter the standard count
- WHEN cases are replayed from an alternative case file
- THEN identifiers of the standard file are unknown for that run, the run is a separate run with its own summary, report and record holding only the alternative cases, its checks are not added to those of the standard file, and the standard case file is not modified

Source: tests/posture_evals/test_posture_evals.py (Principal, CasDeCommandes); tests/posture_evals/test_gaps_posture_evals.py (FichierDeCasDeCommandes)

### Requirement: Language variants of cases
The system SHALL support a French default and an English language; in English it SHALL replay only cases that carry an English variant, replacing the question, the judged criteria, the text pattern of text rules and, when the variant names one, the cases fixture, while keeping every other field; cases without a variant SHALL be listed and not replayed.

Source: tests/posture_evals/test_posture_evals.py (Langue, Principal); tests/posture_evals/test_cases_fixture.py (FixtureDansUnCas)

#### Scenario: French is unchanged
- **WHEN** the language is French
- **THEN** the case is used as is, even if it has an English block

#### Scenario: English variant
- **WHEN** the language is English and a case has an English block
- **THEN** the merged case takes the English question, criteria and text pattern, keeps the other fields, and does not modify the original case

#### Scenario: English fixture
- **WHEN** the language is English and the English block of a case names its own cases fixture
- **THEN** the merged case uses the English fixture; an English block without a fixture keeps the fixture of the case

#### Scenario: No variant
- **WHEN** the language is English and no case has a variant
- **THEN** the system lists the cases without variant, states that there is nothing to replay, plays no session and writes no report

#### Scenario: Shipped cases are fully translated
- **WHEN** the shipped cases are read in English
- **THEN** every case has a variant with a different question, the same number and kind of criteria, rules of the same shape, and no French fixed formula

### Requirement: Prerequisites make a case non-evaluable
The system SHALL check the optional prerequisites of a case against the library index of the installation and SHALL mark the case as non-evaluable, without playing it, when a prerequisite is unmet. Supported prerequisites SHALL be: a book present, a collection with a minimum number of books, and a topic that must be absent. An unreadable index or an unknown rule SHALL count as unmet.

#### Scenario: Satisfied prerequisites
- WHEN the index has the book, enough books in the collection, and no passage on the absent topic
- THEN no reason is returned

#### Scenario: Unmet prerequisite
- WHEN a book is missing, a collection is too small, or the topic expected to be absent is present
- THEN the corresponding reason is reported and the case is shown as non-evaluable with the reasons

#### Scenario: Index not found
- WHEN the index file cannot be opened
- THEN the reason says the index is not found

#### Scenario: Rejudge ignores prerequisites
- WHEN a past run is rejudged
- THEN prerequisites are not checked

Source: tests/posture_evals/test_posture_evals.py (Prerequis)

### Requirement: Command cases with invented files and throwaway library
The system SHALL support cases that place invented files into the temporary copy and that use a throwaway library index built from a given folder, without overwriting the installation's library configuration. Files SHALL NOT be placed outside the copy.

#### Scenario: Files placed in the copy only
- WHEN a case declares source and destination files
- THEN the files are copied into the temporary copy; a destination escaping the copy is refused

#### Scenario: Throwaway index
- WHEN a case declares a library folder
- THEN that folder is indexed into a per-case location and a separate library configuration is produced; without it the installation configuration is used unchanged

#### Scenario: Command cases are separate from the standard set
- WHEN the command-case file is read
- THEN its cases have identifiers distinct from the standard cases and every referenced input file exists

Source: tests/posture_evals/test_posture_evals.py (CasDeCommandes)

### Requirement: Judge inputs are guarded against unintended change
The system SHALL provide a permanent check comparing what the judge receives (the French judge prompt and, per case, question, posture, verifications, prerequisites, judged criteria after normalization) with a reference Git state, defaulting to the last pushed state. Added cases and language blocks SHALL NOT count as differences; renamed keys SHALL NOT count as differences; a changed criterion, question, text pattern or removed case SHALL. The check SHALL be skippable only by an explicit environment switch, whose skip reason names the switch and requires the commit message to say so.

#### Scenario: Unchanged inputs
- WHEN inputs equal those of the reference
- THEN the check passes

#### Scenario: Modified criterion
- WHEN a judged criterion differs from the reference
- THEN the difference is reported as that case and field being modified

#### Scenario: No reference available
- WHEN the reference cannot be found
- THEN the check is skipped

Source: tests/posture_evals/test_entrees_juge.py

### Requirement: Fixed-formula table equals the shared vocabulary
The system SHALL keep a shared vocabulary file for both languages, with identical keys in both languages, a posture-tag format containing the posture placeholder and distinguishing the languages, and a valid tag pattern. The vocabulary SHALL also hold, once and for both languages, the list of the five posture names. The fixed-formula table of the project instructions SHALL reproduce the formula values exactly, with no regular expression syntax in it, and SHALL include the case-citation formula. The postures table of the project instructions SHALL name exactly the postures of that list.

Source: tests/posture_evals/test_claude_md_vocabulaire.py, tests/posture_evals/test_posture_evals.py (Langue)

#### Scenario: Both languages complete
- **WHEN** the vocabulary is loaded
- **THEN** both French and English are present with the same set of keys, and the posture names list holds five names

#### Scenario: Table matches vocabulary
- **WHEN** the table of fixed formulas is compared with the vocabulary
- **THEN** each of the seven formulas, the case-citation formula included, equals the vocabulary value in each language

#### Scenario: Posture names match
- **WHEN** the postures table of the project instructions is compared with the vocabulary's posture names
- **THEN** the names are the same, with the same spelling and case

### Requirement: Evaluation sessions read only a disposable cases database
The system SHALL, for a run that plays sessions, create one disposable database in the instance, apply every migration to it, empty its cases tables and reset their numbering before each case, load the case's invented fixture when it has one, and drop the database at the end of the run whatever happens. It SHALL pass the disposable database and an invented author to the session environment and to the library server configuration of every case, so that no session reads the real cases. When the disposable database cannot be created, it SHALL pass a cases database name that does not exist and an empty author. The temporary copy of the workspace SHALL never contain the local author file, so the author of every session comes from the environment only. A fixture path SHALL exist and stay inside the fixtures folder of the evaluation set, and SHALL be checked before any database is created or any session played. A rejudge SHALL create no database, and a run on the file-based library back-end SHALL create none either (it runs as if the database could not be created). Every replay of a case SHALL empty and reload the database again. When the database cannot be created, the system SHALL print the message of a database connection error (which names where the password is looked for, never a value) and, for any other error, its type only.

#### Scenario: Case with a fixture
- **WHEN** a case names a fixture with one case and one running experiment
- **THEN** before the session the disposable database holds exactly them, numbered from 1, and the session environment and server configuration name the disposable database and the invented author

#### Scenario: Database cannot be created
- **WHEN** the disposable database cannot be created
- **THEN** a case with a fixture is reported as not evaluable here with the reason that the cases database is unavailable, and the other cases run with a cases database name that does not exist, never the real one, and with an empty author

#### Scenario: Local author file
- **WHEN** the workspace holds a local author file and a case is prepared
- **THEN** the temporary copy does not contain that file

#### Scenario: Fixture outside the folder
- **WHEN** a fixture path, in a case or in its English block, points outside the fixtures folder or to a missing file
- **THEN** the case file is refused with an error naming the case, before any database is created

#### Scenario: Cleanup
- **WHEN** a run ends normally, with an error, or because another run holds the lock
- **THEN** the disposable database no longer exists

#### Scenario: Replay
- **WHEN** a failing case is replayed
- **THEN** the database is emptied and the fixture loaded again before the replay

#### Scenario: Error message without secret
- **WHEN** creating the database fails with an error other than a database connection error
- **THEN** only the error type is printed, never its message

Source: tests/posture_evals/test_cases_fixture.py (FixtureDansUnCas, EnvironnementDesSeances, MessageDeBaseIndisponible, BaseJetable, PassageAvecBaseJetable, CopieSansFichierAuteur)

### Requirement: Shipped cases cover the cases module
The system SHALL ship three cases with invented fixtures, each with exactly one blocking criterion and non-blocking indicators, checking that a close case that worked is presented as a lead cited with its number, author, date and outcome and as a testimony; that a close case that failed is presented as a path already tried, to avoid or adapt; and that the user's running experiment is mentioned for information only with a proposal to add a note to it.

#### Scenario: Blocking count
- **WHEN** the shipped standard cases are counted
- **THEN** there are thirteen cases carrying thirty-seven blocking checks

#### Scenario: No review due in the shipped fixtures
- **WHEN** the shipped fixtures are read
- **THEN** every running experiment has a review date after 2027-12-31

#### Scenario: Cases tool checks recognised
- **WHEN** a case verifies that the case-search, experiment-search or due-reviews tool was called
- **THEN** the rule is accepted and applied to the session trace; a call to another tool does not satisfy it

Source: tests/posture_evals/test_posture_evals.py (CritereJugeNonBloquant); tests/posture_evals/test_cases_fixture.py (PassageAvecBaseJetable, OutilsDesCas); tests/posture_evals/test_cas_livres.py (FixturesLivrees, review dates after 2027-12-31).

### Requirement: Former French option and key names are refused
The system SHALL refuse a former French option name with an error naming the current option, and SHALL refuse a case file that uses a former key, including inside a language variant, with an error naming the case and the current key. Current names SHALL produce no message.

#### Scenario: Old option
- **WHEN** the former name of an option is used
- **THEN** the run stops with an error naming the current option

#### Scenario: Old case key
- **WHEN** a case uses a former key
- **THEN** loading stops with an error naming the case and the current key

#### Scenario: Both keys present
- **WHEN** a case has both a former and a current key
- **THEN** loading stops with the same error

## Open questions

None.
