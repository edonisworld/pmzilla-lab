# tooling-sanctum-backup Specification

## Purpose
The posture sanctums are not tracked by Git. A local backup script copies the whole sanctum folder into a dated folder of the lab's backups folder, never overwrites a backup, and rotates the plain dated backups while keeping a protected backup and the labelled ones. The off-site copy of these backups belongs to tooling-offsite-backup.

## Requirements

### Requirement: A dated copy of the whole sanctum
The system SHALL copy the sanctum folder into a backup folder named after the day, check that the copy holds as many files as the sanctum, and print the backup's path with its file count. It SHALL print only paths and file counts, never the content of a sanctum file.

#### Scenario: Copy
- **WHEN** the backup runs on a sanctum of three files
- **THEN** the dated backup holds the three files with their content, and the output names it with `(3 fichiers)`

#### Scenario: Content never shown
- **WHEN** the sanctum files hold a sentinel text
- **THEN** the output holds no sentinel

Source: tests/sauvegarde_sanctum/test_sauvegarde_sanctum.py (test_copie_datee_avec_le_nombre_de_fichiers, test_n_affiche_jamais_le_contenu); the file-count check of an incomplete copy is untested

### Requirement: A backup is never overwritten
The system SHALL refuse, with exit code 1 and `La sauvegarde du jour existe déjà`, to run when the backup folder of that day, or of that day and label, already exists, and SHALL then copy and delete nothing.

#### Scenario: Second backup the same day
- **WHEN** the backup runs twice the same day after the sanctum changed
- **THEN** the second run exits 1 and the first copy keeps its content

Source: tests/sauvegarde_sanctum/test_sauvegarde_sanctum.py (test_refuse_d_ecraser_la_sauvegarde_du_jour, test_deuxieme_sauvegarde_du_meme_jour_avec_une_etiquette)

### Requirement: The rotation keeps the newest plain backups and a protected one
The system SHALL keep a configurable number of the newest plain dated backups and delete the older ones, printing `Supprimée :` with the path and file count of each. It SHALL NOT delete the protected backup, a labelled backup, or any other folder of the backups folder, and SHALL NOT count a labelled backup in the retention.

#### Scenario: Retention exceeded
- **WHEN** one more plain backup than the retention is made
- **THEN** the oldest one is deleted and named once in the output

#### Scenario: Protected backup
- **WHEN** the protected backup is the oldest and the retention is exceeded
- **THEN** it is kept in addition to the newest backups

#### Scenario: Labelled and foreign folders
- **WHEN** the backups folder holds a labelled backup and a folder that is not a backup
- **THEN** neither is deleted, and the labelled one does not reduce the number of plain backups kept

Source: tests/sauvegarde_sanctum/test_sauvegarde_sanctum.py (test_rotation_garde_les_plus_recentes_et_affiche_ce_qu_elle_supprime, test_la_sortie_nomme_ce_qui_est_supprime, the protected-backup test, test_les_autres_dossiers_du_dossier_des_sauvegardes_ne_sont_pas_touches, test_une_sauvegarde_etiquetee_n_est_ni_comptee_ni_supprimee_par_la_rotation)

### Requirement: A second backup of the day carries a label
The system SHALL accept a date followed by a label of lowercase letters and digits to make another backup the same day, and SHALL refuse with exit code 2 an invalid date or label, creating nothing.

#### Scenario: Labelled backup
- **WHEN** a plain backup of the day exists and a labelled backup of the same day is asked
- **THEN** both folders exist after the run

#### Scenario: Invalid label
- **WHEN** the label is empty, holds a space or a path step
- **THEN** the script exits 2 and creates nothing

Source: tests/sauvegarde_sanctum/test_sauvegarde_sanctum.py (test_deuxieme_sauvegarde_du_meme_jour_avec_une_etiquette, test_etiquette_invalide, test_date_invalide)

### Requirement: A missing or empty sanctum stops the backup
The system SHALL exit with code 2 and `Sanctum introuvable ou vide` when the sanctum folder is absent or holds no file, and SHALL create no backup. A copy that fails or holds fewer files than the sanctum SHALL exit with code 2 without rotating.

#### Scenario: Sanctum absent
- **WHEN** the sanctum folder does not exist
- **THEN** the script exits 2 and the backups folder stays empty

Source: tests/sauvegarde_sanctum/test_sauvegarde_sanctum.py (test_source_absente_ou_vide); the failed or incomplete copy is untested
