# workflow-roadmap Specification

## Purpose
A work queue that lives in the issues of the GitHub repository, a reader that loads it through a cached snapshot, checks it, proposes the ready jobs that fit a time budget, prints a feature, the counts and a board page, drafts the release notes of a milestone and proposes a batch, and the `/next` command that presents those proposals without editing anything. The reader never writes to GitHub: the write tool does.

## Requirements

### Requirement: The work queue has a fixed, checkable format
The system SHALL keep the work queue in the issues of the private repository, never in a tracked document. Each job SHALL be one feature issue titled `R-<n> · <title>` (a fixed prefix followed by digits, unique among open and closed features), with the labels `type:feature` and exactly one `theme:<theme>` label, a milestone, an identity marker that names the identifier of the title, and a fenced `roadmap` block of design D5 (theme, estimate, method, model, conditions, rank on an open feature, and optionally change, not-before, due, started-on and done-on dates) whose theme equals the theme label. The queue SHALL NOT contain a person's, team's or project's name.

#### Scenario: Valid feature
- **WHEN** a feature has its title, marker, labels, milestone, Status and a block whose keys hold allowed values
- **THEN** it is a valid job

#### Scenario: Unknown block key
- **WHEN** the block of a feature holds a key outside design D5
- **THEN** the queue is invalid and the identifier and the key are named

#### Scenario: Forbidden values
- **WHEN** a block has a method or a model outside the allowed values, a zero or malformed estimate, an impossible date, or a theme different from the theme label
- **THEN** the queue is invalid and the identifier and the field are named

#### Scenario: Two theme labels
- **WHEN** a feature carries two `theme:` labels
- **THEN** the queue is invalid and the identifier and the labels field are named

#### Scenario: Marker of another identifier
- **WHEN** a feature's title has no identifier, or its marker names another identifier than its title
- **THEN** the queue is invalid and the title or marker field is named

Source: tests/roadmap/test_roadmap_github.py (TestCheck); tests/roadmap_model/test_roadmap_model.py (TestMarkers, TestTitles, TestBlock); the name rule rests on the write tool's guard (spec workflow-github-issues)

### Requirement: /next proposes ready jobs for the time given
The system SHALL provide a `/next <duration>` slash command that runs the queue reader's next command with the duration, presents the result in the user's language (enumerated values translated), and asks the user which job to start. It SHALL NOT edit the queue, start a job, reorder the queue, invent an estimate or a model, or run anything other than the queue reader.

#### Scenario: Two hours
- **WHEN** the user types `/next 2h`
- **THEN** the command lists, in queue order, the proposed jobs with their durations and the total, the jobs too long and the unestimated ones apart, and ends by asking which job to start

#### Scenario: Pre-approval
- **WHEN** the header of the command file is read
- **THEN** it pre-approves only the reader's next command

Source: tests/workflow_commands/test_workflow_commands.py (test_next_ne_pre_approuve_que_la_sous_commande_next_du_lecteur); the presentation is untested

### Requirement: The reader works from a cache when GitHub is unreachable
The system SHALL write, after each successful full read, a snapshot of the queue into the lab data folder, outside the repository, replacing the previous one. The snapshot SHALL be dated with the real day of the read, never with the date given by the today option or its environment variable. When GitHub is unreachable or `gh` is not authenticated, the check, next, status, board and show commands SHALL read the snapshot and print first `GitHub unreachable; read from the cache of <date>`; with no snapshot they SHALL exit 5 with `GitHub unreachable and no cache`. The reader SHALL NOT write the snapshot inside the repository, SHALL NOT rewrite it from an offline run, and SHALL NOT write to GitHub from it.

#### Scenario: Offline with a cache
- **WHEN** GitHub is unreachable and a snapshot exists
- **THEN** next proposes from the snapshot and the first line names the date of the cache

#### Scenario: Offline without a cache
- **WHEN** GitHub is unreachable and no snapshot exists
- **THEN** the reader exits 5

#### Scenario: Snapshot dated with the real day
- **WHEN** a successful read runs with a today option or variable set to another date
- **THEN** the snapshot carries the real day of the read

#### Scenario: Offline run keeps the snapshot
- **WHEN** a command runs offline with a snapshot
- **THEN** the snapshot file is unchanged

Source: tests/roadmap/test_roadmap_github.py (TestHorsLigne; TestCorrectionsRevue: test_date_du_cache_est_la_date_reelle_pas_today)

### Requirement: The session start recalls the queue in one line
The system SHALL provide a reminder command for the session-start hook that reads only the snapshot, never the network, and prints one line `roadmap: <n> ready, <n> in progress (cache of <date>)`, or nothing when no snapshot exists or the snapshot cannot be read. It SHALL always exit 0, SHALL NOT launch `gh`, and SHALL NOT print a title or a body.

#### Scenario: Session start offline
- **WHEN** the session starts without network and a snapshot exists
- **THEN** the hook prints the counts line with the date of the snapshot and the session starts normally

#### Scenario: No snapshot
- **WHEN** no snapshot exists
- **THEN** the reminder prints nothing and exits 0

#### Scenario: Unreadable snapshot
- **WHEN** the snapshot file holds text that is not a snapshot
- **THEN** the reminder prints nothing and exits 0

Source: tests/roadmap/test_roadmap_github.py (TestRappel)

### Requirement: No queue document remains
The system SHALL hold no work-queue document nor archive document in the repository, and no reader command SHALL read a queue from a file.

#### Scenario: Former document
- **WHEN** the repository is searched for the former queue document and its archive
- **THEN** neither is tracked, and the reader has no file option

#### Scenario: Former file commands
- **WHEN** the reader is given the file option, or the former done or archive subcommands
- **THEN** it exits 2 and calls no `gh` command

Source: tests/roadmap/test_roadmap_github.py (TestModeFichierRetire); the absence of the former documents from the repository is untested (design, open question 6)

### Requirement: The reader reads the repository of origin
The system SHALL make the queue reader resolve the repository from the remote `origin` by the same rule as the write tool and pass its owner and name explicitly to every GitHub read. It SHALL NOT rely on the default repository chosen by `gh`. When `origin` is missing or is not a GitHub repository, it SHALL exit with code 2 and read neither GitHub nor the cache.

#### Scenario: Default repository of gh differs
- **WHEN** the default repository of `gh` differs from the repository of `origin`
- **THEN** every read of the reader names the repository of `origin`

#### Scenario: Same repository for both tools
- **WHEN** the same `origin` URL is given to the reader and to the write tool, in any of the URL forms the write tool accepts
- **THEN** both resolve the same owner and name

#### Scenario: Origin missing
- **WHEN** the repository has no `origin` remote
- **THEN** the reader exits with code 2 with `usage: the origin remote is missing or is not a GitHub repository` and reads nothing

### Requirement: Reader calls are bounded in time
The system SHALL run every `gh` call of the reader with its standard input closed, prompts disabled and a configurable time limit. A call over the limit SHALL count as GitHub unreachable, so the reader falls back to its cache as it does offline. It SHALL NOT wait without a bound.

#### Scenario: Read that never answers
- **WHEN** `gh` gives no answer within the time limit and a snapshot exists
- **THEN** the reader prints first `GitHub unreachable; read from the cache of <date>` and answers from the snapshot

#### Scenario: No answer and no snapshot
- **WHEN** `gh` gives no answer within the time limit and no snapshot exists
- **THEN** the reader exits with code 5

### Requirement: The current release is a checked setting
The system SHALL keep the current release as a tracked queue setting that names one milestone or none. The check command SHALL exit 1 with one line naming the setting when it names a milestone that does not exist, is closed, or is `Tarasque`. The setting SHALL NOT hold anything but a milestone name, and the reader SHALL NOT write it.

#### Scenario: Open milestone
- **WHEN** the setting names an open milestone
- **THEN** the check raises no problem for it

#### Scenario: Closed or unknown milestone
- **WHEN** the setting names a closed milestone, `Tarasque`, or a title no milestone has
- **THEN** the check exits 1 and prints a line that starts with `current_release`

#### Scenario: No release
- **WHEN** the setting is empty
- **THEN** the check raises no problem for it

### Requirement: The reader drafts the release notes of a milestone
The system SHALL provide a reader command that prints Markdown release notes of a milestone from its features closed as completed, one line per feature grouped by theme, and names on the error stream what it leaves out (design D5 of `github-roadmap`). Themes SHALL come in alphabetical order, and features within a theme by closing date, then identifier number, an unknown date last. Features closed as not planned, sub-issues and ideas SHALL be left out; issues without a type label SHALL be named on the error stream by number only, with `not listed: issues without a type label:`. With the public option, it SHALL keep only the closed features carrying the label `edition:public` and name on the error stream the closed features it leaves out for lack of that label (design D20 of `edition-publish-tooling`); the notes keep the titles as they are, in French, and the command translates nothing. It SHALL pass the notes through the write tool's guard and print nothing on a finding (exit 3) or when the guard cannot run (exit 4). It SHALL NOT write to GitHub or a file, create a release or tag, or list sub-issues, ideas or open features.

#### Scenario: Closed features listed
- **WHEN** a milestone holds two closed features of different themes
- **THEN** the notes hold one heading per theme and one line per feature, titles without their identifier prefix, and the exit code is 0

#### Scenario: Order within a theme
- **WHEN** a theme holds features closed on different days and two closed on the same day
- **THEN** they are listed by closing date, those of the same day by identifier number, and one without a known date last

#### Scenario: Open feature and sub-issues left out
- **WHEN** the milestone also holds an open feature and closed sub-issues
- **THEN** none of them is in the notes and the error stream says `not listed: 1 open feature(s)`

#### Scenario: Feature closed as not planned
- **WHEN** a feature of the milestone was closed as not planned
- **THEN** it is not in the notes, from a live read or from the snapshot

#### Scenario: Issue without a type label
- **WHEN** the milestone holds an issue labelled neither feature, task nor idea
- **THEN** it is not in the notes and the error stream names its number, never its title

#### Scenario: Sensitive name in a title
- **WHEN** a closed feature's title holds a name of the sensitive-names list
- **THEN** the command exits 3 with `refused: sensitive name in notes`, prints no notes and does not print the name

#### Scenario: Unknown milestone
- **WHEN** the milestone does not exist
- **THEN** the command exits 2 with `usage: unknown milestone`

#### Scenario: Offline with a cache
- **WHEN** GitHub is unreachable and a snapshot exists
- **THEN** the notes come from the snapshot and the error stream starts with the cache banner

#### Scenario: Public notes
- **WHEN** the milestone holds three closed features, one of them labelled `edition:public`, and the public option is given
- **THEN** the notes hold that feature only, its title unchanged, and the error stream says `not listed: 2 closed feature(s) without edition:public`

#### Scenario: Private notes unchanged
- **WHEN** the same milestone is read without the public option
- **THEN** the notes hold the three features

Source: tests/roadmap/test_roadmap_notes.py (TestNotesSelection, TestNotesGarde, TestNotesHorsLigne, TestNotesPubliques)

### Requirement: Ideas stay outside the queue
The system SHALL make the queue reader ignore issues labelled `type:idea`: the check SHALL NOT report them, next SHALL NOT propose them, and status and board SHALL NOT count them. An issue that carries an idea marker without the `type:idea` label is not an idea: the check SHALL report it by its number. An idea SHALL become a job only when the user creates a feature for it through the write tool.

#### Scenario: Idea without milestone
- **WHEN** the repository holds an open `type:idea` issue without milestone, block or marker of a job
- **THEN** the check exits 0 and names no problem for it

#### Scenario: Next ignores ideas
- **WHEN** the next command walks the queue
- **THEN** no idea is proposed, listed too long or listed unestimated

#### Scenario: Status and board unchanged
- **WHEN** open and closed ideas are added to a queue
- **THEN** the status output and the board page are the same as without them

#### Scenario: Idea marker without the idea label
- **WHEN** an issue carries an idea marker and another label than `type:idea`
- **THEN** the check exits 1 and names its number

Source: tests/roadmap/test_roadmap_notes.py (TestIdees)

### Requirement: No evolutions document remains
The system SHALL hold no evolutions document in the repository: an unnumbered idea SHALL live as a `type:idea` issue without milestone. No command, agent or tracked document SHALL point to an evolutions document. Untested until implemented.

#### Scenario: Former document
- **WHEN** the repository is searched for the former evolutions document
- **THEN** it is not tracked, and the README's evolution-ideas section names the `type:idea` label instead

#### Scenario: Closing a change
- **WHEN** `/close` runs
- **THEN** it updates no evolutions entry and creates none

### Requirement: The reader proposes a batch on a milestone
The system SHALL provide a reader batch command that takes a milestone and walks its open features by rank. It SHALL retain each feature whose Status is `Ready`, whose blockers are all closed and whose not-before date is reached, unless its known files overlap those of a better-ranked retained feature or of a feature `In progress` (design D3). It SHALL NOT retain a feature of another milestone.

#### Scenario: Two independent features
- **WHEN** a milestone holds two `Ready` features without open blockers whose changes cite no common path
- **THEN** both are retained, in rank order

#### Scenario: Common file with a better-ranked feature
- **WHEN** two `Ready` features of the milestone have changes that both cite the same existing file
- **THEN** the better-ranked one is retained and the other is set aside with `fichiers communs avec` and the identifier of the first

#### Scenario: Common file with a job in progress
- **WHEN** a `Ready` feature's change cites a folder that holds a file cited by the change of an `In progress` feature of another milestone
- **THEN** it is set aside with `fichiers communs avec`, the identifier of the job in progress and `(en cours)`

#### Scenario: Feature not proposable
- **WHEN** a feature of the milestone is `Todo`, has an open blocker or a not-before date after today
- **THEN** it is neither retained nor listed as set aside

Source: tests/roadmap/test_roadmap_github.py (TestBatch)

### Requirement: Known files come from the feature's change
The system SHALL take the known files of a feature from the tasks and design of the unarchived change its block names: each code span that is, whole, a repository path existing as a file or folder, outside the OpenSpec folder (design D3). A folder SHALL overlap every path under it. A span that starts with `/` or `~`, or holds a `.` or `..` segment, SHALL NOT be a known file, and a change name holding `/`, `.`, `..` or `archive` SHALL NOT name a change. The reader SHALL NOT decide from any other file, nor guess files from a title or a description.

#### Scenario: Command line in a code span
- **WHEN** a tasks file quotes a command line holding a space and a script path
- **THEN** that span gives no known file

#### Scenario: Path that does not exist
- **WHEN** a tasks file quotes a path that does not exist in the repository
- **THEN** that path is not a known file

#### Scenario: OpenSpec paths
- **WHEN** two changes both cite a baseline spec file
- **THEN** that path does not make them overlap

#### Scenario: Path leaving the repository
- **WHEN** a tasks file quotes an existing file as an absolute path, from the home folder, or through a `..` or `.` segment
- **THEN** that span gives no known file

Source: tests/roadmap/test_roadmap.py (TestFichiersConnus, TestRecoupement)

### Requirement: Unknown files are flagged and a missing change sets aside
The system SHALL retain a feature whose block names no change with the unknown-files flag of design D2, and SHALL NOT set another feature aside because of it. It SHALL set aside, with the reason of design D2, a feature whose change field names no unarchived change.

#### Scenario: Direct-prompt job
- **WHEN** a `Ready` direct-prompt feature of the milestone has no change
- **THEN** it is retained with `fichiers inconnus` and every other feature is judged as if it were absent

#### Scenario: Archived or absent change
- **WHEN** a `Ready` feature names a change that has no folder outside the archive
- **THEN** it is set aside with `change <name> introuvable`

Source: tests/roadmap/test_roadmap_github.py (TestBatch: test_fichiers_inconnus_ne_ecartent_personne, test_change_introuvable, test_change_archive_introuvable)

### Requirement: Shared files are reported without setting aside
The system SHALL leave the fixed list of shared files of design D3 out of the overlap, and SHALL print apart each of them that two retained features cite, with their identifiers. It SHALL NOT set a feature aside for those files alone.

#### Scenario: Both changes edit the installation guide
- **WHEN** the only path two retained features have in common is the installation guide
- **THEN** both stay retained and the guide is listed under `fichiers partagés` with both identifiers

Source: tests/roadmap/test_roadmap_github.py (TestBatch: test_fichiers_partages_listes_sans_ecarter); tests/roadmap/test_roadmap.py (TestRecoupement: test_fichiers_partages_hors_recoupement)

### Requirement: The batch names each feature's branch and launch
The system SHALL give each retained feature a branch, a launch model and a session kind by the table of design D5, from its method, change field and model only: framing for an OpenSpec feature without change, execution otherwise. It SHALL NOT invent a model: an undecided model gives the execution model.

#### Scenario: OpenSpec feature to frame
- **WHEN** a retained OpenSpec feature has no change
- **THEN** its line names the framing branch of design D5, the framing model and `cadrage`

#### Scenario: Direct-prompt job with an undecided model
- **WHEN** a retained direct-prompt feature has the model `tbd`
- **THEN** its line names the execution model and a branch made of its identifier and the slug of design D5

Source: tests/roadmap/test_roadmap.py (TestLancement); tests/roadmap/test_roadmap_github.py (TestBatch: test_openspec_sans_change_cadrage)

### Requirement: The batch output is stable
The system SHALL print the batch with the lines and key phrases of design D2: the milestone, the current release or its absence, one line per retained feature (identifier, title, method, model, branch, launch model, session kind, file count or unknown flag, conditions, due date), then each feature set aside with its reason. It SHALL NOT print a feature description.

#### Scenario: No current release
- **WHEN** the current-release setting is empty
- **THEN** the output holds `release courante : aucune`

#### Scenario: Nothing to retain
- **WHEN** the milestone holds no proposable feature
- **THEN** the output holds `retenues : aucune` and the exit code is 0

Source: tests/roadmap/test_roadmap_github.py (TestBatch)

### Requirement: The batch needs a live read
The system SHALL make the batch command exit 5 with `GitHub unreachable; a batch needs a live read` when GitHub cannot be read, snapshot or not, exit 1 with one line per problem on an invalid queue, and exit 2 on a missing, unknown or closed milestone (design D2). It SHALL NOT propose a batch from the snapshot.

#### Scenario: Offline with a snapshot
- **WHEN** GitHub is unreachable and a snapshot exists
- **THEN** the batch command exits 5 and prints no retained feature

#### Scenario: Closed milestone
- **WHEN** the milestone given is closed
- **THEN** the command exits 2 with `usage: closed milestone`

Source: tests/roadmap/test_roadmap_github.py (TestBatch: test_hors_ligne_avec_et_sans_instantane, test_jalon_manquant_inconnu_ferme, test_file_invalide)

### Requirement: The batch command writes nothing
The system SHALL keep the batch command read-only. It SHALL NOT write to GitHub, create a branch or a worktree, or write in the repository; its only write SHALL be the reader's usual snapshot outside the repository.

#### Scenario: Calls to gh
- **WHEN** the batch command runs against a fake `gh` that records its calls
- **THEN** every recorded call is a read

Source: tests/roadmap/test_roadmap_github.py (TestBatch: test_lecture_seule); the absence of a branch, worktree or repository write is read in tools/roadmap.py and untested

### Requirement: Queue order and progress follow the rank and the Status
The system SHALL keep each feature's progress in the Status field of a Project among `Todo`, `Ready`, `In progress` and `Done`, and its dependencies as "blocked by" relations. The priority SHALL be the rank of the block, smaller first; dates SHALL NOT reorder the queue. A finished job SHALL be a closed feature with Status `Done`, and an open feature SHALL NOT have Status `Done`. The milestone `Tarasque` SHALL hold only closed features.

#### Scenario: Rank before number
- **WHEN** a feature with a higher number has a smaller rank than another
- **THEN** the reader walks it first

#### Scenario: Status and state disagree
- **WHEN** a closed feature has Status `Ready`, an open one has Status `Done`, or a feature has no Status in the Project
- **THEN** the check exits 1 and names each identifier and its Status field

Source: tests/roadmap/test_roadmap_github.py (TestNext: test_le_rang_prime_sur_le_numero; TestCheck: test_status_et_ouverture_incoherents, test_feature_ouverte_dans_tarasque)

### Requirement: The check command reads the queue and reports each problem
The system SHALL provide a reader check command that reads every page of the queue from GitHub and exits 0 with `file valide` on a valid queue, 1 with one line per problem naming the identifier (or sub-issue key, or issue number) and the field, 2 on a usage error, and 5 when GitHub is unreachable without a cache. A GitHub refusal SHALL exit 1 with `GitHub refused`, never read as unreachable. It SHALL NOT write to GitHub.

#### Scenario: Unknown dependency
- **WHEN** a feature is blocked by an issue that is not a feature
- **THEN** the check exits 1 and names the identifier and the dependency field

#### Scenario: Read-only
- **WHEN** the check runs against a fake `gh` that records its calls
- **THEN** every call is a GraphQL read without a mutation

#### Scenario: GitHub refusal
- **WHEN** GitHub answers the read with a GraphQL error
- **THEN** the check exits 1 with `GitHub refused` and does not read the cache

Source: tests/roadmap/test_roadmap_github.py (TestCheck: test_file_valide, test_dependance_inconnue, test_ne_fait_aucune_ecriture, test_pagination, test_erreur_graphql_n_est_pas_hors_ligne)

### Requirement: The check covers identifiers, ranks, dependencies, Status, milestones and sub-issues
The system SHALL make the check report: a duplicate identifier; a rank held by two open features; a blocker that is not a known feature; a feature blocking itself; a cycle; a `Ready` or `In progress` feature with an open blocker; a closed feature with an open blocker; an open issue in a closed milestone; an open feature in `Tarasque`; a sub-issue whose parent is not a feature, that lacks `type:task`, or that has not exactly one model label or the user-step label.

#### Scenario: Cycle
- **WHEN** two features block each other
- **THEN** the check exits 1 and names both on the cycle line

#### Scenario: Ready with an open blocker
- **WHEN** a `Ready` feature is blocked by an open feature
- **THEN** the check exits 1 and names the identifier and its Status field

#### Scenario: Closed with an open blocker
- **WHEN** a closed feature is blocked by an open feature
- **THEN** the check exits 1 and names the identifier and its state field

#### Scenario: Open feature in Tarasque
- **WHEN** an open feature has the milestone `Tarasque`
- **THEN** the check exits 1 and names the identifier and the milestone field

#### Scenario: Sub-issue labels
- **WHEN** a sub-issue has both a model label and the user-step label, or neither
- **THEN** the check exits 1 and names the sub-issue key

#### Scenario: Duplicate rank
- **WHEN** two open features hold the same rank
- **THEN** the check exits 1 and names both with the rank field

Source: tests/roadmap/test_roadmap_github.py (TestCheck)

### Requirement: The next command proposes ready jobs within a budget
The system SHALL provide a next command that takes a duration budget and walks the open features by rank, optionally in one milestone. It SHALL propose each `Ready` feature whose blockers are closed and whose not-before date is reached when its estimate fits the remaining budget, list one that does not fit as too long and go on, and list `tbd` ones apart, uncounted. It SHALL NOT write to GitHub, change a rank, or propose any other feature.

#### Scenario: Budget filled in rank order
- **WHEN** the budget is two hours and the first three proposable features by rank are estimated one hour, ninety minutes and thirty minutes
- **THEN** the first and the third are proposed, the second is listed as too long, and the total is ninety minutes

#### Scenario: Unestimated feature
- **WHEN** a proposable feature is estimated `tbd`
- **THEN** it is listed apart and not counted

#### Scenario: Not-before date in the future
- **WHEN** a `Ready` feature has a not-before date after today
- **THEN** it is not proposed

#### Scenario: One milestone
- **WHEN** the next command is given a milestone
- **THEN** only features of that milestone are proposed

#### Scenario: Not ready or blocked
- **WHEN** the open features are `Todo`, `In progress`, or `Todo` with an open blocker
- **THEN** none is proposed and the total is zero

Source: tests/roadmap/test_roadmap_github.py (TestNext); tests/roadmap/test_roadmap.py (TestSelection)

### Requirement: The next command prints each proposal and its total
The system SHALL make the next command print, for each proposed feature, the identifier, the title, the estimate, the method, the model, the conditions to confirm and the due date when present, then the list of features too long, the unestimated ones and the total. It SHALL exit 1 on an invalid queue and 2 on a malformed budget, proposing nothing. Today's date SHALL be replaceable by an option or an environment variable, for tests.

#### Scenario: Full line
- **WHEN** a proposed feature has conditions and a due date
- **THEN** its line holds the title, the estimate, the method, the model, the conditions and the due date

#### Scenario: Malformed budget
- **WHEN** the budget is not a duration
- **THEN** the command exits 2 and proposes nothing

#### Scenario: Invalid queue
- **WHEN** a feature's block holds a forbidden method
- **THEN** the command exits 1

#### Scenario: Date from the environment
- **WHEN** the date variable is set after a feature's not-before date
- **THEN** that feature is proposed

Source: tests/roadmap/test_roadmap_github.py (TestNext: test_affichage_complet, test_budget_mal_forme, test_file_invalide, test_date_du_jour_par_environnement)

### Requirement: The show command prints one feature
The system SHALL provide a reader show command that prints, for one identifier, its title, state, Status, milestone, estimate, method, model, rank, conditions, the dates and change of its block, each blocker with its state, each sub-issue with its key, title and state, and the description. The Status SHALL come from the queue's Project only. An unknown identifier SHALL exit 1 and be named. The command SHALL NOT write to GitHub.

#### Scenario: Feature in progress
- **WHEN** show is run on a feature in progress with a closed blocker and two sub-issues
- **THEN** the output holds its title, Status, milestone, conditions, start date, the blocker marked closed, each sub-issue with its state and the description

#### Scenario: Unknown identifier
- **WHEN** show is run on an identifier no feature has
- **THEN** the command exits 1 and names that identifier

#### Scenario: Status of another Project
- **WHEN** the feature has the Status `Done` in another Project and `Ready` in the queue's Project
- **THEN** show prints the Status `Ready`

Source: tests/roadmap/test_roadmap_github.py (TestShowStatusBoard: test_show, test_show_identifiant_inconnu; TestCorrectionsRevue: test_status_d_un_autre_project_ignore)

### Requirement: The status command prints counts and open jobs
The system SHALL provide a reader status command that prints the number of features ready, in progress, blocked and done, then a line per job in progress with its start date, per blocked job with the features it waits for, and per ready job with its estimate. It SHALL exit 1 on an invalid queue and SHALL NOT write to GitHub.

#### Scenario: Counts and lines
- **WHEN** the queue holds one done, one in progress, one blocked and one ready feature
- **THEN** the output holds `ready 1`, `in-progress 1`, `blocked 1`, `done 1`, the start date of the job in progress and the blocker of the blocked job

#### Scenario: Invalid queue
- **WHEN** a feature's block holds a forbidden method
- **THEN** the status command exits 1

Source: tests/roadmap/test_roadmap_github.py (TestShowStatusBoard: test_status, test_status_file_invalide)

### Requirement: The board command writes a page in the data folder
The system SHALL provide a reader board command that writes an HTML page of the queue into the lab data folder, outside the repository, and prints the page's file name without any absolute path. It SHALL exit 1 on an invalid queue and SHALL NOT write to GitHub or in the repository.

#### Scenario: Page written
- **WHEN** the board command runs on a valid queue
- **THEN** the page exists in the data folder and holds the identifiers and the closing dates

#### Scenario: No absolute path printed
- **WHEN** the board command runs
- **THEN** its output names the page file and holds neither the data folder path nor the home folder path

Source: tests/roadmap/test_roadmap_github.py (TestShowStatusBoard: test_board_ecrit_dans_le_dossier_de_donnees; TestCorrectionsRevue: test_board_n_imprime_pas_de_chemin_absolu); the option that opens the page is untested

### Requirement: GitHub error messages holding an identifier are withheld
The system SHALL make the reader check every GitHub refusal message against the personal identifiers before printing it. When the message holds one, or the identifiers cannot be read, the reader SHALL exit 1 with `GitHub refused: HTTP <code> (message withheld)`; otherwise it SHALL print `GitHub refused:` followed by the message. It SHALL NOT print a withheld message in part.

#### Scenario: Identifier in a GraphQL error
- **WHEN** GitHub answers with a GraphQL error whose message holds an identifier of the session
- **THEN** the reader exits 1, prints `GitHub refused: HTTP 403 (message withheld)` and its output holds no identifier

#### Scenario: Errors in the response body
- **WHEN** the response body lists errors whose message holds an identifier
- **THEN** the reader exits 1 and prints `(message withheld)`

#### Scenario: Clean message
- **WHEN** the GraphQL error holds no identifier
- **THEN** the reader prints it after `GitHub refused:`

Source: tests/roadmap/test_roadmap_github.py (TestCorrectionsRevue: test_erreur_graphql_avec_identifiant_personnel_retenue, test_erreur_graphql_sans_identifiant_gardee, test_erreurs_dans_la_reponse_json_avec_identifiant_retenues)

### Requirement: A missing or unauthenticated gh falls back to the snapshot
The system SHALL treat a `gh` that cannot be launched, or that is not authenticated, as GitHub unreachable: the check, next, status, board, show and release-notes commands SHALL read an existing snapshot with the cache line, or exit 5 with `GitHub unreachable and no cache` when none exists. The reader SHALL NOT ask the user to log in and SHALL NOT launch `gh auth`.

#### Scenario: gh missing without a snapshot
- **WHEN** the `gh` executable cannot be found and no snapshot exists
- **THEN** the check exits 5

#### Scenario: Not logged in without a snapshot
- **WHEN** `gh` reports that it is not logged in and no snapshot exists
- **THEN** the check exits 5

#### Scenario: gh missing with a snapshot
- **WHEN** the `gh` executable cannot be found and a snapshot exists
- **THEN** the command answers from the snapshot after the cache line

Source: tests/roadmap/test_roadmap_github.py (TestHorsLigne: test_gh_absent, test_non_authentifie_est_traite_comme_injoignable, without a snapshot only); the fallback to an existing snapshot is read in tools/roadmap.py and untested

## Open questions

None.
