# cases-lifecycle Specification

## Purpose
Life of an experiment in the cases module: start from a draft, dated notes, postponements, drop, closing into a case, due reviews (journal follow-ups, session hook, dashboard), the local author, the sensitive-names guard, exit codes and messages of the journal's experiment commands, and the loading of invented fixtures.

Source of truth: `tests/cases_store/test_cases_store.py`, `tests/journal_lab/test_experiment.py`, `tests/dashboard/test_dashboard.py` (Experimentations), `tools/cases_store.py`, `tools/journal_lab.py`.
## Requirements
### Requirement: Experiments are started from a validated draft
The system SHALL provide a journal command that starts an experiment from a draft file, validating it (a mapping, known keys only, required problem, context, what is tested, expected signal and success criterion, a context made of known keys with text values, hypotheses and references as lists of text, a posture from the allowed set, dates not in the future, review date not in the past, bounded text length), computing its embedding with the library embedding function from the problem, the chosen path and what is tested, writing it under the cases read-write role, printing its number and review date, and deleting the draft. Without a review date, the review SHALL be set after a configurable default period counted from the start date. If the embedding cannot be computed, the command SHALL refuse and write nothing.

Source: `tests/cases_store/test_cases_store.py` (ValidationDuLancement, PannesDEmbedding, Lancement); `tests/journal_lab/test_experiment.py` (Ecritures)

#### Scenario: Valid draft
- **WHEN** a valid start draft without review date is given
- **THEN** the experiment is stored as running with the default review date, its number is printed and the draft is deleted

#### Scenario: Unknown key
- **WHEN** the draft contains an unknown key
- **THEN** the command exits with code 1, names the key, writes nothing and keeps the draft

#### Scenario: Embedding unavailable
- **WHEN** the embedding service does not answer
- **THEN** the command refuses, says the embedding service must run, and writes nothing

### Requirement: Written texts are checked against the sensitive-names list
The system SHALL refuse every experiment, note or closing draft in which a text value contains a name of the local sensitive-names list, applying the same matching rules as the pre-commit hook (whole words, case-sensitive for short names and acronyms), and SHALL name the field concerned but never the name found. When the list is missing, unreadable or holds no name, the system SHALL refuse every start, note and close command before any database connection, with a clear message that names the list's path and says that writes are refused until it exists, and SHALL write nothing. The messages for a missing list and for a list without any name SHALL differ, in both languages. Reading commands (show, due) SHALL NOT read the list.

Source: `tests/cases_store/test_cases_store.py` (ValidationDuLancement.test_nom_sensible_refuse_sans_etre_nomme, test_nom_colle_a_d_autres_lettres_accepte, ListeDesNomsAbsenteOuVide); `tests/journal_lab/test_experiment.py` (ListeDesNoms)

#### Scenario: Listed name in the problem
- **WHEN** the problem of a start draft contains a listed name
- **THEN** the command refuses, names the problem field, and its output does not contain the name

#### Scenario: Name glued to other letters
- **WHEN** a listed name appears only inside a longer word
- **THEN** the draft is accepted

#### Scenario: Missing list
- **WHEN** the sensitive-names list does not exist and a valid start draft is given
- **THEN** the command exits with code 2, names the list's path, opens no database connection, writes nothing and keeps the draft

#### Scenario: List without any name
- **WHEN** the sensitive-names list exists but holds only comments and blank lines, or is empty, and a valid start, note or close draft is given
- **THEN** the command exits with code 2, says the list holds no name and names its path, opens no database connection, writes nothing and keeps the draft

#### Scenario: Postpone and drop without a list
- **WHEN** the sensitive-names list is missing or holds no name and an experiment is postponed or dropped
- **THEN** the command does not read the list and is not refused because of it

### Requirement: Notes, postponements and drops apply to the author's running experiments only
The system SHALL add a dated note, postpone the review, or drop an experiment without lesson only for a running experiment of the configured author; an unknown number, another author's experiment or an experiment that is no longer running SHALL be refused with nothing written. A note SHALL be dated today by default, never in the future and never before the experiment's start. A postponement SHALL take a duration written as a positive whole number of days or weeks (for example `10d` or `2w`; any other form is refused), set the review date that far from today and count the postponement; once the configurable maximum of postponements is reached, a further postponement SHALL be refused with a message asking to close or drop. A drop without lesson SHALL mark the experiment dropped and create no case.

Source: `tests/cases_store/test_cases_store.py` (ReglesDesEcrituresSansBase, NotesReportsAbandons); `tests/journal_lab/test_experiment.py` (Ecritures.test_postpone_et_drop, test_troisieme_report_refuse_demande_close_ou_drop)

#### Scenario: Third postponement
- **WHEN** an experiment already postponed the maximum number of times is postponed again
- **THEN** the command refuses and asks to choose between closing and dropping

#### Scenario: Another author's experiment
- **WHEN** the configured author adds a note to an experiment of another author
- **THEN** the command refuses and writes nothing

#### Scenario: Drop without lesson
- **WHEN** a running experiment is dropped
- **THEN** its status is dropped and no case exists for it

### Requirement: Closing an experiment creates its case in one transaction
The system SHALL close a running experiment of the configured author from a closing draft (outcome required, drop reason required for a dropped outcome and refused for any other outcome, optional what got stuck, confidence and review date, the review date not in the future and not before the experiment's start) by creating, in one transaction, a case that copies the experiment's description, launch date and embedding, records its notes as history in date order (then in the order they were written), and by marking the experiment closed. It SHALL print the case number. A second closing of the same experiment SHALL be refused and leave a single case.

Source: `tests/cases_store/test_cases_store.py` (ValidationNoteEtCloture, Cloture); `tests/journal_lab/test_experiment.py` (Ecritures.test_note_et_close, test_close_refuse_garde_le_brouillon)

#### Scenario: Worked
- **WHEN** an experiment with two notes is closed with the outcome "worked"
- **THEN** a case exists with the same success criterion, the two notes in date order and the experiment's embedding, and the experiment is closed

#### Scenario: Instructive drop
- **WHEN** an experiment is closed with the outcome "dropped" and a drop reason
- **THEN** a case is created with that reason

#### Scenario: Failure leaves nothing
- **WHEN** the case insert fails
- **THEN** no case exists and the experiment is still running

### Requirement: The author comes from local configuration
The system SHALL take the author of experiments, a local identifier, from an environment setting when it is not blank, otherwise from a local, untracked configuration file of the personal layer of the workspace, and SHALL store it only in the database, never in a tracked file. An unreadable file, or a file without a non-blank author, SHALL count as no author. Without an author, write commands and the due-review command SHALL refuse with a message naming the file, before any database connection, and the follow-ups, the session hook and the dashboard SHALL omit the cases part (the dashboard's experiments section then says there is no data yet and reads nothing).

Source: `tests/cases_store/test_cases_store.py` (Auteur); `tests/journal_lab/test_experiment.py` (Ecritures.test_sans_auteur_code_2_et_nomme_le_fichier, SessionHook.test_sans_auteur_rien_et_aucune_connexion, SuivisEtDeprecation.test_follow_ups_sans_auteur_inchange); `tests/dashboard/test_dashboard.py` (Experimentations.test_sans_auteur)

#### Scenario: No author
- **WHEN** neither the setting nor the file gives an author and an experiment is started
- **THEN** the command exits with code 2 and names the configuration file

#### Scenario: Blank setting
- **WHEN** the environment setting is empty and the local file gives an author
- **THEN** the author of the file is used

### Requirement: Due reviews surface without being asked
The system SHALL list the configured author's due reviews in the journal follow-ups (after the journal's own experiments, without changing the exit code when the database does not answer) and through a session-start hook that runs only the due-review listing, always exits successfully, prints nothing when nothing is due, when no author is configured or (apart from one short line) when the database does not answer, and otherwise prints one line per due review and the ways to settle it. A review SHALL be due when its review date is today or earlier (the same day included); this single rule SHALL be shared by the server's due-review tool, the journal and the dashboard. A due review that has reached the maximum of postponements SHALL be flagged "decision required". The hook SHALL use a short connection timeout, SHALL exit successfully even when the database layer or the author lookup asks to exit, and SHALL never print a trace or a secret. The dashboard SHALL list the author's running experiments by review date with their start date, review date and postponement count, flag the due ones, and show an unreadable source by the error type only.

Source: `tests/cases_store/test_cases_store.py` (RegleDeLaRevueDue, Echeances); `tests/journal_lab/test_experiment.py` (SessionHook, SessionHookProcessusReel, SessionHookSeanceEvaluation, SuivisEtDeprecation); `tests/dashboard/test_dashboard.py` (Experimentations)

#### Scenario: Hook with a due review
- **WHEN** a session starts and one review is due
- **THEN** the hook prints a header, one line with its number, due date and problem, and the line naming close, postpone and drop

#### Scenario: Review due today
- **WHEN** an experiment's review date is today
- **THEN** it is listed as due by the journal, the server and the dashboard, and the dashboard does not call it late

#### Scenario: Decision required
- **WHEN** a due review has reached the maximum of postponements
- **THEN** its line carries "décision requise" in French or "decision required" in English

#### Scenario: Hook with the database down
- **WHEN** a session starts and the cases database does not answer
- **THEN** the hook prints one short line and exits with code 0

#### Scenario: Follow-ups without author
- **WHEN** follow-ups are listed and no author is configured
- **THEN** the output is identical to the output before the cases module

#### Scenario: Hook without author
- **WHEN** a session starts and no author is configured
- **THEN** the hook prints nothing, opens no database connection and exits with code 0

### Requirement: Lifecycle commands have English names only
The system SHALL name the experiment subcommands and the corresponding journal modes start, note, show, postpone, drop, close and due, SHALL offer no French alias, and SHALL leave the existing period review command unchanged.

Source: `tests/journal_lab/test_experiment.py` (Ecritures.test_sous_commandes_francaises_refusees)

#### Scenario: French name
- **WHEN** the subcommand "bilan" or "reporter" is called on an experiment number
- **THEN** it is refused as an unknown subcommand and nothing is written

### Requirement: The journal's YAML experiment block is deprecated but still read
The system SHALL keep accepting, storing and listing the experiment block of a journal entry exactly as before, and SHALL print on the error stream a deprecation line pointing to the start command when an entry with that block is added and, once per listing, when the follow-ups list such an experiment, without changing the standard output or the exit code.

Source: `tests/journal_lab/test_experiment.py` (SuivisEtDeprecation)

#### Scenario: Entry with an experiment block
- **WHEN** an entry with an experiment block is added
- **THEN** it is stored as before, the standard output is unchanged, and the error stream carries the deprecation line

#### Scenario: Follow-ups with a YAML experiment
- **WHEN** the follow-ups list one or more YAML experiments
- **THEN** the standard output is unchanged and the deprecation line appears once on the error stream

### Requirement: An experiment can be shown with its notes
The system SHALL show any experiment, whatever its author, with its description, status, review date, postponement count and dated notes, read under the cases read-only role, and SHALL name an unknown number in its error.

Source: `tests/cases_store/test_cases_store.py` (NotesReportsAbandons.test_note_puis_affichage, test_show_numero_inconnu, test_show_est_lisible_quel_que_soit_l_auteur); `tests/journal_lab/test_experiment.py` (Lectures)

#### Scenario: Unknown number
- **WHEN** an experiment number that does not exist is shown
- **THEN** the command exits with code 1 and names the number

### Requirement: Experiment commands report by exit code, in French or English, without secrets
The journal's experiment commands SHALL exit with 0 on success; with 1 when a draft or a rule refuses the request (unknown key, missing or invalid field, sensitive name, not the author's running experiment, postponement limit, unknown number, refusal by the database); and with 2 when the database does not answer, no author is configured, the sensitive-names list is missing or empty, or the embedding service is unavailable. A refused draft SHALL be kept and a draft SHALL be deleted only after success. Messages SHALL be in French by default and in English with the language option, with the same message keys in both languages. A message SHALL never contain the database password, the text of a connection error (only its type) or the row the database refused (only the error type and its state code). A draft file that does not exist or is not valid YAML SHALL be refused with code 1 (read in the code).

Source: `tests/journal_lab/test_experiment.py` (Ecritures, Catalogues, BrouillonIllisible); `tests/cases_store/test_cases_store.py` (ReglesDesEcrituresSansBase.test_erreur_de_la_base_sans_la_ligne_refusee); `tools/journal_lab.py` (read_draft)

#### Scenario: Database unreachable
- **WHEN** the connection to the cases database fails with a message containing a secret
- **THEN** the command exits with code 2, the draft is kept and the output does not contain the secret

#### Scenario: Refused by the database
- **WHEN** the database refuses a write and its error quotes the refused row
- **THEN** the refusal names the error type and state code and does not quote the row

#### Scenario: English messages
- **WHEN** an experiment is dropped with the English language option
- **THEN** the message differs from the French one and says the experiment was dropped

### Requirement: Invented fixtures are loaded with the draft rules except the names guard
The system SHALL load an invented fixture file (experiments, with their dated notes and status, then closed cases with their history) in one transaction under the cases read-write role, applying the same field rules as the drafts except the sensitive-names guard and the future and past date rules (fixtures carry fixed dates); a note or history entry dated before the start, a review date before the start, an unknown key or a missing required field SHALL refuse the whole file before any write. Each fixture case SHALL be stored with a closed experiment of its own. Loading SHALL return the counts of experiments and cases.

Source: `tests/cases_store/test_cases_store.py` (Recherche.test_le_fixture_est_charge_sous_le_role_des_cas, test_un_jeu_d_essai_refuse_n_ecrit_rien, ChargementDuJeuDEssaiSansBase)

#### Scenario: Refused fixture
- **WHEN** a fixture entry lacks a required field or carries an unknown key
- **THEN** the load is refused and nothing is written

#### Scenario: Names list absent
- **WHEN** a fixture holds a name of the sensitive-names list and the list is absent
- **THEN** the fixture is loaded

### Requirement: The due-review reminder runs first at session start
The system SHALL declare exactly two session-start commands, the due-review listing in session-hook mode first and the work-queue reminder second, and SHALL declare no other hook. Running the queue reminder before the due reviews, or adding any other hook, is excluded. The queue reminder itself is specified in workflow-roadmap.

Source: tests/journal_lab/test_session_hook.py (HookDeSession)

#### Scenario: Session start
- **WHEN** the project settings are read
- **THEN** the session-start hooks are the due-review listing then the queue reminder, in that order

#### Scenario: No other hook
- **WHEN** the declared hook events are listed
- **THEN** only the session-start event is present

## Open questions

None.

