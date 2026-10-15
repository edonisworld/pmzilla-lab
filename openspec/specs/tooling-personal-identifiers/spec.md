# tooling-personal-identifiers Specification

## Purpose
A publication-gate scanner that reports where the author's personal identifiers appear in Git-tracked files and in generated posture sanctums, without ever revealing the identifier.
## Requirements
### Requirement: Search tracked files for identifiers
The system SHALL search every Git-tracked text file case-insensitively for the identifiers and report, per file, the lines that contain one.

#### Scenario: Personal path
- WHEN a tracked file contains a home path with the identifier
- THEN the file is reported with that line number

#### Scenario: Case
- WHEN the identifier appears in capitals
- THEN it is still found

Source: tests/identifiants_personnels/test_identifiants_personnels.py (test_trouve_l_identifiant_et_le_chemin_personnel)

### Requirement: Identifier sources
The system SHALL take identifiers from the session account, the home folder name, the repository root path, an optional local, Git-ignored identifiers file and the cases author identifier read from the local, Git-ignored cases configuration file of the personal layer, and SHALL store none in tracked files. The cases author identifier SHALL be read from that file only, never from the environment setting of the cases module. When that file is absent, has no author key or gives an empty value, the system SHALL use the other identifiers only, print nothing about it and keep its exit code; when the file exists but cannot be read as text, the system SHALL exit with code 2 and a message naming the file, never its content.

Source: tests/identifiants_personnels/test_identifiants_personnels.py (test_identifiants_viennent_du_compte_et_du_fichier_local, test_le_chemin_de_la_racine_est_un_identifiant, AuteurDesCas)

#### Scenario: Sources
- **WHEN** identifiers are computed
- **THEN** both the local file entries and the account name are included, and the root path is also an identifier

#### Scenario: Cases author in a tracked file
- **WHEN** the local cases configuration file gives an author identifier and a tracked file contains it in capitals
- **THEN** the tracked file is reported with its line number, the output contains neither the identifier nor the line text, and the exit code is 1

#### Scenario: Quoted or commented value
- **WHEN** the author key's value is quoted or followed by a comment
- **THEN** the identifier searched is the value without quotes, comment or surrounding spaces

#### Scenario: Indented or other key
- **WHEN** the author key is indented, or the value is under another key
- **THEN** no cases author identifier is read

#### Scenario: Author absent or empty
- **WHEN** the cases configuration file is absent, has no author key, or gives an empty value
- **THEN** the identifiers are the same as without that file, nothing is printed about it, and the exit code is unchanged

#### Scenario: Environment setting not read
- **WHEN** the cases author environment setting holds an invented handle and no cases configuration file exists
- **THEN** that handle is not among the identifiers

#### Scenario: Unreadable configuration file
- **WHEN** the cases configuration file exists but is not valid text
- **THEN** the scanner exits with code 2, names the file, and prints none of its content

#### Scenario: Given file
- **WHEN** a given text file contains the cases author identifier
- **THEN** it is reported and the exit code is 1

### Requirement: Ignored files
The system SHALL ignore untracked files, binary or image files, files that cannot be decoded as text, a default set of personal non-published documents, and the round-table output folder, while still scanning the rest of the output folder; extra exclusions may be given.

#### Scenario: Default exclusions
- WHEN excluded documents or untracked files contain the identifier
- THEN they are not reported

#### Scenario: Other documents
- WHEN another document in the same documentation folder contains it
- THEN it is reported

#### Scenario: Extra exclusion
- WHEN a path is passed as an extra exclusion
- THEN it is not reported

Source: tests/identifiants_personnels/test_identifiants_personnels.py (test_ignore_les_fichiers_hors_edition_non_suivis_et_binaires, test_le_dossier_des_tables_rondes_est_exclu_mais_pas_le_reste_de_bmad_output, test_le_plan_est_exclu_par_defaut_mais_pas_les_autres_docs, test_exclusion_supplementaire)

### Requirement: Output reveals no identifier or line text
The system SHALL print only counts and, with the lines option, line numbers, never the identifier nor the line text, plus a total, and SHALL exit 1 when any occurrence exists and 0 otherwise, and SHALL exit 2 on an error.

#### Scenario: Occurrences found
- WHEN occurrences exist
- THEN the output lists each file with counts and the total, contains no identifier or surrounding text, and the exit code is 1

#### Scenario: None
- WHEN no occurrence exists
- THEN the total is zero lines in zero files and the exit code is 0

Source: tests/identifiants_personnels/test_identifiants_personnels.py (test_sortie_sans_identifiant_ni_texte_de_ligne, test_code_zero_sans_occurrence)

### Requirement: Generated sanctums are scanned
The system SHALL instantiate each posture skill's sanctum in a temporary folder through its init script and scan the result as if it were tracked, reporting findings under a sanctum-prefixed key; a skill without an init script SHALL be ignored, and a failing init script SHALL stop the scan.

#### Scenario: Template writes a personal path
- WHEN the generated sanctum file contains a personal path
- THEN it is reported under the sanctum key with its line number

#### Scenario: Clean sanctum
- WHEN generated files contain nothing
- THEN nothing is reported

#### Scenario: Init failure
- WHEN the init script exits non-zero
- THEN the scan aborts with an error

#### Scenario: Real skills
- WHEN the real skills' sanctums are generated
- THEN no generic user-path pattern or root path is found

Source: tests/identifiants_personnels/test_identifiants_personnels.py (Sanctums)

### Requirement: Scan a given text file
The system SHALL accept a path to a text file and search it, case-insensitively, for the same identifiers as the tracked files, whether or not the file is tracked, and SHALL apply the same output rules: only counts and, with the lines option, line numbers, never the identifier nor the line text, with exit code 1 when any occurrence exists and 0 otherwise. With a given file, the system SHALL search that file only, not the tracked files.

#### Scenario: Identifier in the file
- WHEN the given file contains an identifier
- THEN the output reports the file with a count, contains no identifier nor line text, and the exit code is 1

#### Scenario: Clean file
- WHEN the given file contains no identifier
- THEN the exit code is 0

#### Scenario: Missing file
- WHEN the given path does not exist
- THEN the scanner exits with code 2 and a message naming the path

#### Scenario: Tracked files not searched
- WHEN a tracked file contains an identifier and a clean file is given
- THEN the exit code is 0

Source: tests/identifiants_personnels/test_identifiants_personnels.py (FichierDonne)

### Requirement: Repository guard against personal identifiers
The system SHALL include, in the scanner's test suite, a test that runs the scanner on the real repository: the tracked files, the default exclusions and the identifiers of the current session. The test SHALL fail on any occurrence of an identifier in a tracked file. No file SHALL be tolerated, including the files that carried a former name before batch 8 and the social handle line of the tracked watch triage settings, since the handle lives in the untracked local settings layer. The failure message SHALL name only files and line numbers, never an identifier nor a line text. Where no identifier of the session appears in the repository, the test SHALL pass.

Source: tests/identifiants_personnels/test_identifiants_personnels.py (DepotReel)

#### Scenario: Clean repository
- **WHEN** no tracked file outside the default exclusions contains an identifier
- **THEN** the test passes

#### Scenario: Former-name file
- **WHEN** a tracked file that carried a former name before batch 8 contains an identifier
- **THEN** the test fails, its message names the file and the line number, and contains neither the identifier nor the line text

#### Scenario: Handle back in the tracked settings
- **WHEN** the tracked triage settings hold an identifier on the social handle line
- **THEN** the test fails, its message names the file and the line number, and contains neither the identifier nor the line text

#### Scenario: Another machine
- **WHEN** the suite runs under an account whose identifiers appear in no tracked file
- **THEN** the test passes

### Requirement: Other guards read the scanner's identifiers
The system SHALL make every test that keeps a personal identifier out of a file or an output read the identifiers from the scanner's identifier function, compare them without regard to case, report a failure without printing the identifier, and SHALL NOT hard-code a personal identifier in any test.

Source: tests/parity/test_parity.py (test_formulations_courtes_sans_extrait_ni_nom), tests/watch_triage/test_watch_triage.py (test_aucun_identifiant_personnel_dans_les_options_ni_dans_l_aide), tests/pmzilla_lab_library/test_coherence_noms.py (test_aucun_identifiant_personnel_dans_les_fichiers_lus_par_le_modele)

#### Scenario: Identifier in the frozen parity queries
- **WHEN** the frozen query file contains one of the session's identifiers, in any case
- **THEN** the parity guard fails with a message that does not contain the identifier

#### Scenario: No identifier
- **WHEN** none of the session's identifiers appears in the checked text
- **THEN** the guard passes

### Requirement: Personal BMAD settings stay local
The system SHALL keep the BMAD user name of the tracked BMAD configuration files at the generic BMAD default, SHALL keep BMAD's personal install-answer layer out of Git, and SHALL let the BMAD configuration resolver take the real user name from that local layer when it exists and the generic default otherwise.

Source: tests/identifiants_personnels/test_identifiants_personnels.py (ConfigurationBmad, DepotReel); the resolver's fallback is not tested

#### Scenario: Tracked configuration
- **WHEN** the tracked BMAD module configuration files are read
- **THEN** their user name is the generic default, and the personal install-answer files (the user layer and the custom user files) are not tracked and are listed in the ignore rules

#### Scenario: Reinstall writes the real name back
- **WHEN** a BMAD reinstall writes a user name other than the generic default into a tracked module configuration file
- **THEN** the configuration test fails and names that file

### Requirement: Scan a generated tree
The system SHALL offer a tree mode, given a folder through a tree option, that searches every regular text file under that folder, case-insensitively, whether or not the folder is a Git repository, with the identifiers of the root option (the private workspace), with the sanctums instantiated from the posture skills found in the given folder, and with the output and exit-code rules of the tracked-file search, paths relative to the given folder.

#### Scenario: Identifier in a tree without Git
- **WHEN** a folder that is not a Git repository holds a file containing an identifier of the private workspace
- **THEN** the file and line are reported, the output holds no identifier nor line text, and the exit code is 1

#### Scenario: Cases author of the root
- **WHEN** the root's cases configuration gives an author identifier and a file of the tree contains it in capitals
- **THEN** that file is reported

#### Scenario: Sanctums of the tree
- **WHEN** a posture skill of the tree generates a sanctum file containing the private root path
- **THEN** it is reported under the sanctum-prefixed key

#### Scenario: Clean tree
- **WHEN** no file of the tree and no generated sanctum contains an identifier
- **THEN** the total is zero and the exit code is 0

Source: tests/identifiants_personnels/test_identifiants_personnels.py (Arbre)

### Requirement: The tree mode applies no exclusion and takes nothing from the tree
The system SHALL NOT apply the default exclusions in tree mode. It SHALL refuse an extra exclusion with exit code 2 and scan nothing, and SHALL exit with code 2 when the folder does not exist. It SHALL NOT read the local identifiers file or the cases configuration of the given folder. It SHALL skip symbolic links and files that cannot be read as text.

#### Scenario: Default exclusions not applied
- **WHEN** the tree holds a file at a path that is excluded by default, and that file contains an identifier
- **THEN** it is reported

#### Scenario: Extra exclusion refused
- **WHEN** the tree mode is combined with an extra exclusion
- **THEN** the scanner exits with code 2 and scans nothing

#### Scenario: Missing folder
- **WHEN** the given folder does not exist
- **THEN** the scanner exits with code 2 and names the folder

#### Scenario: Binary file skipped
- **WHEN** the tree holds a file that is not valid text and that contains an identifier
- **THEN** it is not reported

#### Scenario: Files of the given folder not read as identifiers
- **WHEN** the given folder holds its own local identifiers file and cases configuration, and a file that contains their values
- **THEN** nothing is reported

Source: tests/identifiants_personnels/test_identifiants_personnels.py (Arbre); skipping symbolic links is untested

