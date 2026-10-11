# database-migrations Specification

## Purpose

Ordered, tracked, tamper-evident schema migrations for the local PostgreSQL database, and the secret-free connection layer used by the migration runner (`tools/db.py`, `db/migrations/`).
## Requirements
### Requirement: Migration files are strictly named and contiguous
The system SHALL accept only migration files named with a four-digit number, an underscore and a lowercase description (letters, digits, underscores), SHALL ignore non-SQL files, and SHALL refuse a folder whose numbers are duplicated, do not start at 1, or contain a gap.

Source: tests/db/test_db.py (TestSansBase: test_noms_mal_formes_refuses, test_numero_en_double_refuse, test_trou_refuse, test_suite_qui_ne_commence_pas_a_un_refusee, test_fichiers_non_sql_ignores, test_suite_continue_triee)

#### Scenario: Malformed name
- WHEN a migration file has a name with a wrong digit count, an uppercase letter, a dash or a space
- THEN listing the migrations fails with a "malformed" error

#### Scenario: Duplicate or gap
- WHEN two files share a number, or the sequence skips a number, or starts above 1
- THEN listing fails with a duplicate or gap error

#### Scenario: Sorted contiguous sequence
- WHEN files 1, 2 and 3 are present in any filesystem order alongside a README
- THEN the system returns migrations 1, 2, 3 in order and ignores the README

### Requirement: Each repository migration declares the schema it touches
The system SHALL ship repository migrations whose first line is a comment beginning with the "schema touched" marker, SHALL start the sequence with the schemas, roles and extensions migration, and SHALL keep data (INSERT statements) and password settings out of migrations.

Source: tests/db/test_db.py (test_migrations_du_depot_bien_nommees); tests/db/test_flow_schema.py (SansBase.test_migration_0002_presente_et_sans_donnee); tests/db/test_knowledge_schema.py (SansBase); tests/db/test_cases_schema.py (SansBase.test_migration_0006_presente_sans_donnee_ni_mot_de_passe, SansBase.test_travailleurs_paralleles_coupes_avant_le_premier_index_bm25); tests/db/test_lacunes_base.py (SansBase.test_migration_0003_ajoute_la_colonne_sans_donnee)

#### Scenario: First line of a repository migration
- **WHEN** the repository migrations are read
- **THEN** the first migration is the schemas, roles and extensions one and every file's first line starts with the "schema touched" comment

#### Scenario: No data and no password in a migration
- **WHEN** the flow, knowledge, BM25 and cases migrations are read
- **THEN** none contains an INSERT INTO statement or a password literal

#### Scenario: Cases migration builds its BM25 indexes without parallel workers
- **WHEN** the cases migration is read
- **THEN** the setting disabling parallel maintenance workers appears before its first BM25 index

### Requirement: Migrations never create login roles or alter roles
The system SHALL ensure that every role created by a migration is created without login capability, and that no migration sets a password, alters a role or drops a role (roles are shared by the whole database instance).

Source: tests/db/test_db.py (test_aucune_migration_ne_cree_de_role_avec_connexion_ni_mot_de_passe)

#### Scenario: Static check of all migrations
- WHEN comments are stripped from every repository migration
- THEN each role creation is NOLOGIN and no LOGIN, PASSWORD, ALTER ROLE or DROP ROLE appears

### Requirement: Each migration is fingerprinted by the SHA-256 of its content
The system SHALL compute a SHA-256 fingerprint of each migration file's bytes, and the fingerprint SHALL change when the content changes.

Source: tests/db/test_db.py (test_empreinte_sha256_du_fichier)

#### Scenario: Content change
- WHEN a migration file's content is rewritten
- THEN its fingerprint differs from the previous one and equals the SHA-256 of the new bytes

### Requirement: Pending migrations are applied in order, one transaction each, and tracked
The system SHALL apply pending migrations in numeric order, each in its own transaction, SHALL record each applied migration (its number, name, fingerprint and application time) in a tracking table of the default schema, and SHALL report each applied migration. A first run on an empty database SHALL create the schemas, the extensions for vector and BM25 search, and the roles.

Source: tests/db/test_db.py (TestAvecBase.test_migration_0001_du_depot, test_cli_status_et_migrate_sans_mot_de_passe_dans_la_sortie)

#### Scenario: First migration on a blank database
- WHEN only the first repository migration is applied to a blank database
- THEN the vector and BM25 extensions exist, the knowledge, cases and flow schemas exist, an owner role plus a read-write and a read-only role per schema exist, the knowledge and cases schemas hold no table, and the tracking table lists the first migration

#### Scenario: Command-line migrate
- WHEN the migrate command runs with two pending migrations
- THEN the output lists "Applied" for them and the exit code is 0

### Requirement: A failed migration is rolled back and halts the run
The system SHALL roll back a migration that fails (including its tracking row), SHALL report which migration failed, SHALL NOT apply later migrations, and SHALL resume from the failed one on the next run once the file is fixed.

Source: tests/db/test_db.py (test_migration_invalide_annulee)

#### Scenario: Failure in the middle
- WHEN migration 2 creates a table and then fails, and migration 3 is pending
- THEN the error names migration 2 as failed and rolled back, only migration 1 is tracked, neither migration 2's partial table nor migration 3's table exists
- AND after fixing migration 2, the next run applies migrations 2 and 3

### Requirement: Already applied migrations are immutable and must remain present
The system SHALL, before applying anything, compare the files to the tracking table and SHALL stop without applying any migration if an applied migration's fingerprint has changed or if an applied migration's file is missing or renamed.

Source: tests/db/test_db.py (test_empreinte_modifiee_arrete_tout, test_fichier_applique_disparu_arrete_tout)

#### Scenario: Modified applied file
- WHEN an applied migration's file is edited and a new migration is pending
- THEN the run fails with a "modified since application" error, the new migration is not applied and the tracking table is unchanged

#### Scenario: Missing applied file
- WHEN an applied migration's file is replaced by a file with another name at the same number
- THEN the run fails with a "missing or renamed" error

### Requirement: Re-running is a no-op
The system SHALL do nothing when no migration is pending, SHALL say there is nothing to apply, and SHALL leave the tracking rows (including application times) untouched.

Source: tests/db/test_db.py (test_deuxieme_passage_sans_effet); tests/db/test_knowledge_schema.py (test_migration_rejouee_sans_effet)

#### Scenario: Second pass
- WHEN migrations are run a second time on an up-to-date database
- THEN the pending list is empty, the output says there is nothing to apply and the tracking rows are identical

### Requirement: Dry run writes nothing
The system SHALL, in dry-run mode, list pending migrations without creating the tracking table or any object.

Source: tests/db/test_db.py (test_dry_run_n_ecrit_rien)

#### Scenario: Dry run on a blank database
- WHEN a dry run is made with one pending migration
- THEN the output lists it as pending, and neither the tracking table nor the migration's table exists

### Requirement: An advisory lock prevents concurrent runners
The system SHALL take a database-level advisory lock for the duration of a run, SHALL refuse to run (with an "other runner" error) if the lock is held elsewhere, and SHALL release the lock after each run.

Source: tests/db/test_db.py (test_verrou_empeche_deux_executeurs, test_verrou_libere_apres_passage)

#### Scenario: Lock held by another session
- WHEN another session holds the lock and a run is attempted
- THEN the run fails with an "other runner" error
- AND once the lock is released, the run succeeds

#### Scenario: Lock released after a run
- WHEN a run completes
- THEN a further run can be started immediately

### Requirement: Set a limited role password from the command line
The system SHALL offer a command that sets the password of a limited role through a masked prompt asked twice (the prompt naming the role), SHALL refuse a role outside the permitted list at argument parsing, SHALL stop with exit code 1 without connecting when the two entries differ, SHALL stop with exit code 1 and close its connection when the password is too short, and on success SHALL set the password, close the connection and print the instruction for storing the password in the role's keychain entry without storing it. The password SHALL never appear in the output, and no keychain instruction SHALL be printed after a refusal.

Source: tests/db/test_lacunes_base.py (CommandeRolePassword)

#### Scenario: Prompted password
- WHEN the command runs for a permitted role and the same valid password is entered twice
- THEN the password is asked twice without echo, the exit code is 0, a confirmation and the keychain instruction for that role are printed, and the password is not printed

#### Scenario: Different entries
- **WHEN** the two entries differ
- **THEN** the exit code is 1, the error says the entries differ, no connection is opened and no password is set

#### Scenario: Too short
- **WHEN** a too short password is entered twice
- **THEN** the exit code is 1, the error says it is too short, nothing is executed on the connection and the connection is closed

#### Scenario: Role outside the list
- **WHEN** the command names the superuser role
- **THEN** the argument parser refuses it

### Requirement: Status reports applied and pending migrations
The system SHALL provide a status command listing each applied migration and each pending migration, and SHALL print no password in its output.

Source: tests/db/test_db.py (test_cli_status_et_migrate_sans_mot_de_passe_dans_la_sortie)

#### Scenario: Status before and after migrate
- WHEN status runs before migrate with two files
- THEN the first is listed as pending
- AND after migrate, status lists it as applied

### Requirement: Connection addresses never carry a password
The system SHALL refuse a connection address that contains a password (in the authority part or as a query parameter), SHALL explain where the password is read from, and SHALL NOT echo the rejected password. An address without a password SHALL be accepted. The default address SHALL follow the configured port variable.

Source: tests/db/test_db.py (test_url_avec_mot_de_passe_refusee_sans_l_afficher, test_connect_refuse_url_avec_mot_de_passe, test_url_sans_mot_de_passe_acceptee, test_url_par_defaut_suit_le_port)

#### Scenario: Password in the address
- WHEN an address embeds a password, either inline or as a parameter
- THEN a "password" error is raised that does not contain the password value

#### Scenario: Default address and port variable
- WHEN no address is configured and a port variable is set
- THEN the default local address uses that port

### Requirement: The password is read from the macOS keychain first, then from an environment variable
The system SHALL read the database password at connection time from the macOS keychain (via the `security` command, output captured), SHALL fall back to an environment variable when the keychain gives nothing, SHALL return nothing when neither exists or the command is unavailable, and SHALL allow the keychain command to be overridden for tests.

Source: tests/db/test_db.py (test_voie_trousseau_via_faux_security, test_trousseau_prioritaire_sur_la_variable, test_repli_sur_la_variable_si_trousseau_vide, test_ni_trousseau_ni_variable, test_connexion_par_la_voie_trousseau)

#### Scenario: Keychain wins
- WHEN both the keychain and the variable provide a value
- THEN the keychain value is used

#### Scenario: Fallback
- WHEN the keychain has no entry and the variable is set
- THEN the variable value is used

#### Scenario: Nothing available
- WHEN neither source exists, or the keychain command does not exist
- THEN no password is returned

### Requirement: A connection without any password says where it looked
The system SHALL, when a connection fails and no password was found, add to the database error a hint naming the keychain service and the environment variable that were searched (those of the limited role when a role is requested), and SHALL add no such hint when a password was supplied.

Source: tests/db/test_lacunes_base.py (SansBase.test_indice_sans_mot_de_passe_nomme_le_trousseau_et_la_variable, SansBase.test_pas_d_indice_quand_un_mot_de_passe_est_fourni)

#### Scenario: No password anywhere
- **WHEN** a connection is attempted with an empty keychain and no variable, as the superuser and then as a limited role
- **THEN** each error names the keychain service and the variable searched, specific to the role in the second case

#### Scenario: Password supplied
- **WHEN** a connection with a supplied password fails
- **THEN** the error carries no "no password found" hint

### Requirement: Connection errors never leak the password
The system SHALL rewrite connection failures as a database error that does not contain the password and does not chain the original exception, both from the library and from the command line (exit code 1, message on the error stream).

Source: tests/db/test_db.py (test_erreur_de_connexion_sans_le_mot_de_passe, test_mot_de_passe_absent_des_erreurs_de_connexion, test_cli_erreur_de_connexion_sans_mot_de_passe)

#### Scenario: Wrong password or unreachable server
- WHEN a connection fails with a given password
- THEN the raised error does not contain that password and has no chained cause

#### Scenario: Command line failure
- WHEN the migrate command fails to connect
- THEN the exit code is 1, stderr starts with an error message and neither stream contains the password

