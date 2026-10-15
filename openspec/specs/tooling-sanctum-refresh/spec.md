# tooling-sanctum-refresh Specification

## Purpose
The posture sanctums are not tracked by Git, so they do not follow the changes of the skill templates they were created from. A refresh script regenerates each sanctum from its skill in a temporary folder and copies into the existing sanctum only the parts that come from the templates, never the lived memory. The scan of generated sanctums for personal identifiers belongs to tooling-personal-identifiers.

## Requirements

### Requirement: The template parts are refreshed from a fresh sanctum
The system SHALL generate a fresh sanctum of a posture with its skill's initialisation script in a temporary folder, then copy into the existing sanctum the identity file, the capabilities file and the files of the references and scripts folders whose content differs, and report the files written. A second run with no template change SHALL write nothing.

#### Scenario: Changed reference
- **WHEN** a reference file of the skill gains a line
- **THEN** only that file is written into the sanctum, with the new line

#### Scenario: Second run
- **WHEN** the refresh runs twice without any template change
- **THEN** the second run writes and deletes nothing

Source: tests/sanctum_refresh/test_sanctum_refresh.py (test_modele_modifie_recopie_et_vecu_intact, test_deuxieme_passage_ne_change_rien)

### Requirement: The lived memory is never touched
The system SHALL NOT write, rewrite or delete the memory, bond, persona and index files of a sanctum nor its sessions folder, nor any file outside the template parts. The index file SHALL stay the user's choice even when the template's version differs.

#### Scenario: Lived files kept
- **WHEN** the memory, bond and persona files and a session file hold the user's content and a template changes
- **THEN** they are unchanged after the refresh

#### Scenario: User's index
- **WHEN** the index file holds the user's own content
- **THEN** the refresh neither writes nor lists it

Source: tests/sanctum_refresh/test_sanctum_refresh.py (test_modele_modifie_recopie_et_vecu_intact, test_index_n_est_jamais_reecrit)

### Requirement: Files removed from the skill are removed from the sanctum
The system SHALL delete from the references and scripts folders of the sanctum any file that the fresh sanctum no longer has, and report each deletion. It SHALL NOT delete a file elsewhere in the sanctum.

#### Scenario: Retired reference
- **WHEN** the sanctum holds a reference file that the skill no longer produces
- **THEN** it is deleted and reported as deleted

Source: tests/sanctum_refresh/test_sanctum_refresh.py (test_reference_retiree_du_skill_est_supprimee_du_sanctum)

### Requirement: An absent sanctum is created
The system SHALL create the whole sanctum from the fresh copy when the posture has none.

#### Scenario: First refresh
- **WHEN** a posture has no sanctum
- **THEN** the refresh creates it with its identity file

Source: tests/sanctum_refresh/test_sanctum_refresh.py (test_sanctum_absent_est_cree)

### Requirement: A template with an absolute path stops the refresh
The system SHALL stop without writing anything, naming the files concerned, when a template part of the fresh sanctum holds a user home path or the path of the temporary folder. Copied template parts SHALL replace those of an older sanctum that held such a path.

#### Scenario: Path in a template
- **WHEN** the identity template of a skill gains a user home path
- **THEN** the refresh stops, names the identity file, and the existing sanctum is unchanged

#### Scenario: Older sanctum with a path
- **WHEN** an existing sanctum's identity and capabilities files hold a user home path and the templates do not
- **THEN** both are rewritten and no longer hold the path

Source: tests/sanctum_refresh/test_sanctum_refresh.py (test_un_modele_avec_un_chemin_absolu_arrete_tout_sans_rien_ecrire, test_aucun_chemin_absolu_dans_le_sanctum_cree_ni_dans_un_ancien_sanctum_rafraichi)

### Requirement: A dry run says what would change
The system SHALL, with the dry-run option, report the files it would write or delete and change nothing. It SHALL refresh one posture given by option, or the four postures, printing one line per posture that says it is up to date or lists the changes.

#### Scenario: Dry run
- **WHEN** the identity file of a sanctum differs from the template and the dry-run option is given
- **THEN** the identity file is reported and keeps its content

Source: tests/sanctum_refresh/test_sanctum_refresh.py (test_dry_run_n_ecrit_rien); the posture option and the printed lines are untested
