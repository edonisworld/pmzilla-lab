# coaching-journal Specification

## Purpose
The coaching journal keeps, after each session with a team or a role (workshop, retrospective, coaching, CoP), what was tried, what was observed, the promised follow-ups and, formerly, an experiment to review. A command adds an entry, lists open follow-ups, updates a follow-up or concludes a journal experiment, and prints the material of a period review. The journal lives in a local folder outside Git and names roles and scopes, never people. The experiment subcommands of the same tool (cases module) are described by cases-lifecycle.

Source of truth: `tests/journal_lab/test_journal_lab.py`, `tools/journal_lab.py`, `.claude/commands/journal.md`, `CLAUDE.md` (Coaching journal).

## Requirements

### Requirement: An entry is validated before it is written
The system SHALL add an entry from a YAML file only when it is a mapping with known keys only, a known session type, a known posture (none by default), a scope, what was tried and the finding, each text within the length limit, a date not in the future (today by default), and follow-ups each with what, a role and a due date. A refused entry SHALL NOT write anything and SHALL keep the file.

#### Scenario: Unknown key
- **WHEN** the entry carries a key outside the format
- **THEN** the command stops with "Entrée refusée, rien n'est écrit", names the key, keeps the file and creates no journal

#### Scenario: Type read as a number
- **WHEN** the type is written `1:1`
- **THEN** the entry is refused because YAML reads it as a number

Source: tests/journal_lab/test_journal_lab.py (Ajout.test_refus_ne_ecrit_rien_et_garde_le_fichier, test_suites_et_experience_sans_champ_obligatoire, test_fichier_introuvable)

### Requirement: An added entry gets identifiers and the file is deleted
The system SHALL give an entry the identifier `J-<date>-<n>`, numbered per day, its follow-ups `.s<n>` with the status open, and a journal experiment `.x` with the status running; it SHALL write the journal atomically, print the identifiers and delete the source file. It SHALL NOT leave a temporary file beside the journal.

#### Scenario: Two entries the same day
- **WHEN** two entries dated the same day are added
- **THEN** their identifiers end in -1 and -2

#### Scenario: Valid entry
- **WHEN** a valid entry is added
- **THEN** the session, follow-ups and experiment identifiers are printed and the source file no longer exists

Source: tests/journal_lab/test_journal_lab.py (Ajout.test_entree_valide, test_identifiants_du_meme_jour_incrementes, test_champs_facultatifs_et_defauts)

### Requirement: Follow-ups are listed by urgency
The system SHALL list open follow-ups by due date, flag those past due as late, filter on a scope by a case-insensitive substring echoed in the heading, and list journal experiments whose review date is today or earlier. With the all option it SHALL add done and abandoned follow-ups after the open ones. It SHALL NOT list a concluded experiment as due.

#### Scenario: Late follow-up
- **WHEN** an open follow-up is past its due date
- **THEN** its line starts with the late flag and comes first

#### Scenario: Review not yet due
- **WHEN** a journal experiment's review date is after today
- **THEN** it is not listed as due

Source: tests/journal_lab/test_journal_lab.py (Suites, MiseAJour.test_conclure_une_experience_exige_un_resultat)

### Requirement: A follow-up or a journal experiment is updated by identifier
The system SHALL set a follow-up to open, done or abandoned, keeping an earlier note unless a new one is given, and SHALL conclude a journal experiment only with the concluded status and a non-blank result note. It SHALL refuse a follow-up status on an experiment, the concluded status on a follow-up, and an unknown identifier.

#### Scenario: Conclude without result
- **WHEN** a journal experiment is concluded without a note or with a blank note
- **THEN** the command refuses and says the note is required

#### Scenario: Unknown identifier
- **WHEN** an identifier that does not exist is updated
- **THEN** the command refuses and names it

Source: tests/journal_lab/test_journal_lab.py (MiseAJour)

### Requirement: The review gives the material of a period
The system SHALL print, for a period (30 days by default, or from a given date) and an optional scope, the session count, follow-up counts (promised, done, abandoned, open, late), journal experiments and concluded ones, then each session with its follow-ups, notes and results. An empty or missing journal SHALL give zero sessions, not an error.

#### Scenario: Default period
- **WHEN** the review is asked without a date
- **THEN** it covers the 30 days up to today and leaves out older sessions

#### Scenario: Missing journal
- **WHEN** the journal folder does not exist
- **THEN** the review prints zero sessions and follow-ups prints none

Source: tests/journal_lab/test_journal_lab.py (Bilan)

### Requirement: Former French names are refused
The system SHALL refuse the former French option names with an error naming the current one, and the former French subcommand names as unknown, with exit code 2. It SHALL NOT accept them as aliases.

#### Scenario: Former option
- **WHEN** follow-ups are asked with the former scope option
- **THEN** the command exits with code 2 and names the current option

Source: tests/journal_lab/test_journal_lab.py (AnciensNoms)

### Requirement: Messages follow the language option, data stays in French
The system SHALL print messages in French by default and in English with the language option, and SHALL keep the entry keys and status values in French in the journal whatever the language, translating only their display.

#### Scenario: English display
- **WHEN** follow-ups are listed with the English option
- **THEN** the messages and displayed statuses are in English and the journal file keeps French values

Source: tools/journal_lab.py (status_label, module docstring); untested in tests/journal_lab/test_journal_lab.py

### Requirement: The journal names roles, never people
The system SHALL keep the journal outside Git and write in it only roles and scopes. The journal command SHALL replace a name in the account by its role before writing and say so, and SHALL NOT write a judgment about a person nor edit the journal by hand.

#### Scenario: Name in the account
- **WHEN** the user's account of a session contains a person's name
- **THEN** the entry written holds the role instead and the reply says the name was replaced

Source: .claude/commands/journal.md (Absolute rule); CLAUDE.md (Coaching journal); untested (the tool itself does not check names on add)

### Requirement: Sessions are prepared from the open follow-ups
The system SHALL, before preparing a session with a team or a role, list the open follow-ups and due experiments of its scope, and SHALL propose logging the session at the end of the preparation. It SHALL NOT log a session without the user's account.

#### Scenario: Retrospective preparation
- **WHEN** the user asks to prepare a retrospective for a team
- **THEN** the follow-ups of that scope are recalled first and logging is proposed at the end

Source: CLAUDE.md (Coaching journal); untested

## Open questions

- The `add` path does not check text against the sensitive-names list, unlike the experiment drafts: is that guard wanted for journal entries?
- The language option of `add`, `follow-ups`, `update` and `review` has no test in the journal suite.
