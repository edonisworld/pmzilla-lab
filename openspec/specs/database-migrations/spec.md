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

### Requirement: Status reports applied and pending migrations
The status command SHALL list applied and pending migrations, then the role and extension lines of the related status requirements and a summary line (key phrases of design D6). It SHALL exit 0 when no line is a problem, 1 when it cannot run, 3 otherwise, and SHALL print no password and change nothing.

Source: tests/db/test_db.py (test_cli_status_et_migrate_sans_mot_de_passe_dans_la_sortie) for the migration lines; role, extension, summary and exit-code parts untested until implemented.

#### Scenario: Status before and after migrate
- **WHEN** status runs before migrate with two files
- **THEN** the first is listed as pending
- **AND** after migrate, status lists it as applied

#### Scenario: Problem found
- **WHEN** one role line is a problem and the other checks are fine
- **THEN** the summary counts one problem and the exit code is 3

#### Scenario: Nothing wrong
- **WHEN** every role is ok or not set up, the extension matches and one migration is pending
- **THEN** the summary says there is no problem and the exit code is 0

#### Scenario: Tampered migration
- **WHEN** an applied migration file was modified
- **THEN** the exit code is 1 with the existing error and no role or extension check runs

#### Scenario: Status cannot run
- **WHEN** the connection fails, or a migration is malformed, tampered or missing, or the expected extension version is unreadable
- **THEN** the exit code is 1

#### Scenario: Pending migrations and roles not set up are not problems
- **WHEN** a migration is pending or a role is not set up, and no other line is a problem
- **THEN** the exit code is 0

#### Scenario: Status changes nothing
- **WHEN** status runs
- **THEN** no password is printed
- **AND** no role is altered, no extension is updated, no migration is applied and the keychain is not written

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

### Requirement: Later migrations add structure only, under the owner role
The system SHALL keep the watch-and-triage and flow data-protection migrations free of data statements, passwords and role creation, SHALL number the second right after the first, SHALL create its objects under the owner role, and SHALL leave their tables empty. Writing rows, setting a password or creating a role in them is excluded.

Source: tests/db/test_watch_schema.py (SansBase, AvecBase); tests/db/test_flow_gdpr.py (SansBase, ColonneEtTables)

#### Scenario: Static reading of the two migrations
- **WHEN** the watch-and-triage and the flow data-protection migrations are read
- **THEN** the first declares the knowledge schema, the second declares the flow schema and follows the first, and neither contains an insert, a password or a role creation (the second contains no update, delete or copy statement either)

#### Scenario: Owner role before the first change
- **WHEN** the flow data-protection migration is read
- **THEN** it switches to the owner role before altering the issues table

#### Scenario: Empty tables after migration
- **WHEN** all migrations are applied to a disposable database
- **THEN** the watch and triage tables and the flow tables hold no row

### Requirement: Generate, store and test a limited role password from the command line
The system SHALL offer a command that generates a limited role's password (D1), refuses an unlisted role at parsing, alters the role in a transaction (D3), stores the password in the role's keychain entry (D4), reads it back and compares it before committing, then opens a test session as the role (D2), with the exit codes and lines of D6. It SHALL NOT ask for, accept, print, log or write the password. Untested until implemented.

#### Scenario: Generated, stored and tested
- **WHEN** the command runs for a permitted role, the keychain double accepts the write and the test session as the role succeeds
- **THEN** the exit code is 0, the success line names the role and its keychain service, no prompt was shown, the commit came after the keychain write, and the password appears in no output, no argument of the keychain double and no statement sent to the connection

#### Scenario: Keychain refuses
- **WHEN** the keychain double fails the write
- **THEN** the exit code is 1, the error says nothing was set, the transaction is rolled back and no commit was made

#### Scenario: Entry read back and compared before the commit
- **WHEN** the keychain write is accepted but the entry read back by the normal search differs from the generated password, or cannot be read
- **THEN** the exit code is 1, the error says the keychain did not return the password written and that nothing was set, the transaction is rolled back, no commit is made and no test session is opened, and neither the generated password nor the value read appears in any output or error

#### Scenario: Test session fails
- **WHEN** the role change is committed but the test session as the role is refused
- **THEN** the exit code is 1 and the error names the role with a message that does not hold the password

#### Scenario: Role outside the list
- **WHEN** the command names the superuser role
- **THEN** the argument parser refuses it and no connection is opened

#### Scenario: Password generated, never typed
- **WHEN** the command runs twice for the same role
- **THEN** the two stored passwords differ, each is longer than the setter's minimum and uses only letters, digits, dash and underscore

#### Scenario: Throwaway database
- **WHEN** the command runs against a throwaway database for the views role
- **THEN** the role can log in with the password read from the keychain double, and the server statements hold no clear password

### Requirement: Status checks the roles of the permitted list
The system SHALL, in the status command, compute through a service function returning one structured result per role (design D5) the state of each role of the permitted password list: ok, not set up, or a problem with one of the reasons of design D5. The command SHALL only format these results. It SHALL NOT print, return or log a password, SHALL NOT open a session as a role whose password is missing, and SHALL NOT change a role. Untested until implemented.

#### Scenario: Password refused
- **WHEN** the views role may log in and the keychain double returns a password the server refuses
- **THEN** its line is a problem with the refused reason and the hint to rerun the password command for that role, and the output does not hold the returned password

#### Scenario: Role ok
- **WHEN** a permitted role may log in, a password is found and the test session as the role is accepted
- **THEN** its line is ok

#### Scenario: Role never set up
- **WHEN** a permitted role may not log in and no password is found for it
- **THEN** its line says not set up and it does not count as a problem

#### Scenario: Login without stored password
- **WHEN** a permitted role may log in and neither its keychain entry nor its variable gives a password
- **THEN** its line is a problem naming the keychain service and the variable searched, and no session as that role is attempted

#### Scenario: Stored password, login forbidden
- **WHEN** a password is found for a permitted role that may not log in
- **THEN** its line is a problem saying login is forbidden

#### Scenario: Missing role
- **WHEN** a permitted role does not exist in the database
- **THEN** its line is a problem saying it is absent

#### Scenario: Throwaway database
- **WHEN** status runs on a throwaway database where one role got its password from the password command and another holds a different password in the keychain double
- **THEN** the first is ok, the second is refused, and roles never set up are not set up

### Requirement: Status flags roles that never get a password but may log in
The system SHALL, in the status command, report as a problem each application role created by the migrations and outside the permitted password list that may log in, and SHALL print nothing for such a role that may not log in. It SHALL NOT open a session as such a role or change it. Untested until implemented.

#### Scenario: Read-write role with login
- **WHEN** the read-write role of a schema may log in
- **THEN** a problem line says it may log in although it never gets a password

#### Scenario: Roles without login
- **WHEN** no role outside the list may log in
- **THEN** no line is printed for them

### Requirement: Status checks the pg_search version
The system SHALL, in the status command, compare through a service function the installed version of the BM25 search extension with the version expected from the pinned database image (design D5), and SHALL report ok, missing or different with the lines of design D6. An unreadable expected version SHALL stop the command with exit 1. It SHALL NOT update or create the extension, nor query a release source or the network. Untested until implemented.

#### Scenario: Different version
- **WHEN** the fake catalogue gives an extension version other than the one of the fake image tag
- **THEN** the extension line is a problem naming the installed and the expected versions, and the exit code is 3

#### Scenario: Same version
- **WHEN** the installed version equals the expected one
- **THEN** the extension line is ok with that version

#### Scenario: Missing extension
- **WHEN** the extension is not installed
- **THEN** the extension line is a problem saying it is missing

#### Scenario: Unreadable tag
- **WHEN** the compose file has no readable tag for the database image
- **THEN** the exit code is 1 with the unreadable-version error
