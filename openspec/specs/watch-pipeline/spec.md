# watch-pipeline

## Purpose

The daily watch run (`watch.sh`): ordered steps, failure handling, notifications, index freshness, the daily check of the uv dependency cache, optional PostgreSQL copy, and the scheduler template.

Source of truth: `tests/watch_sh/test_watch_sh.py`, `tools/watch.sh`, `tools/com.pmzilla.watch.plist`.
## Requirements
### Requirement: Run the steps in a fixed order
The system SHALL run, when the local model service responds: collection, scoring, apply, shares, ranked reading list, library indexing of both content folders directly into the database, the BM25 probe, then the dashboard (with the parity step between the probe and the dashboard when enabled). On full success it SHALL print a timestamp header, end with "Veille terminée sans erreur", exit 0 and send no notification. Scripts SHALL be called through their linked path. It SHALL NOT run the former import or verification of the PostgreSQL copy.

Source: `tests/watch_sh/test_watch_sh.py` (test_chemin_nominal_enchaine_toutes_les_etapes_dans_l_ordre, test_journal_horodate_et_les_deux_dossiers_indexes), to be updated with the probe.

#### Scenario: Nominal path
- **WHEN** every step succeeds and the parity marker is absent
- **THEN** the steps are called in the order above, the import script is never called, exit code is 0, and no notification is raised

### Requirement: Degrade gracefully without the model service
The system SHALL, when the model service does not respond, collect, write the plain reading list, skip scoring and indexing, say they are postponed, generate the dashboard, and exit 0 without recording an index timestamp.

Source: `tests/watch_sh/test_watch_sh.py` (test_ollama_absent_liste_simple_sans_pre_tri_ni_index)

#### Scenario: Service absent
- **WHEN** the model service is unreachable
- **THEN** only collect, plain digest and dashboard run, the output says pre-sorting and indexing are postponed, and exit code is 0

### Requirement: Warn when the index becomes stale
The system SHALL, when the model service is absent and the last successful indexation is older than a configurable number of days (default applied for missing or invalid values), print a staleness message and raise one desktop notification, without changing the exit code. The age SHALL come from the timestamp file only. A missing or unreadable timestamp SHALL be treated as unknown and notified. A recent index SHALL give no notification, including at the exact threshold boundary. A successful indexation SHALL refresh the timestamp; a failed or skipped one, including one stopped because the database does not answer, SHALL leave it. The system SHALL NOT read the date of any index file.

Source: `tests/watch_sh/test_watch_sh.py` (test_ollama_absent_*, test_seuil_*, test_repere_illisible_traite_comme_inconnu, test_indexation_reussie_ecrit_le_repere_et_echouee_le_laisse); test_avant_le_premier_repere_on_se_fie_a_l_index_lui_meme is replaced by a test that a SQLite file in the data folder is ignored.

#### Scenario: Too old
- **WHEN** the service is absent and the last indexation is older than the limit
- **THEN** a message states the age in days and the limit, one notification is raised, and exit code is 0

#### Scenario: Invalid limit value
- **WHEN** the limit setting is not a number
- **THEN** the default limit is used

#### Scenario: No timestamp, old SQLite file present
- **WHEN** the service is absent, the timestamp file is missing and an index file exists in the data folder
- **THEN** the indexation is treated as unknown and one notification is raised

### Requirement: Continue after a failing step and report every failure once
The system SHALL log a failing collection, scoring chain, reading list or indexation, continue with later steps, exit 1, end with "Veille terminée avec N étape(s) en échec" naming failed steps in order, and raise one single notification naming them. An indexation stopped because the database does not answer (indexer exit code 2) SHALL be logged with the "base PostgreSQL injoignable" phrase and named with the step label "indexation (base injoignable)" of design.md D9; any other indexing failure keeps the label "indexation". A failure of the pre-sort chain (scoring, apply, shares, digest) SHALL stop that chain at the first failing command, fall back to the plain reading list, and still index. A failing notification SHALL be logged and SHALL NOT change the exit code. A failing indexation SHALL NOT prevent the reading list or the dashboard.

Source: `tests/watch_sh/test_watch_sh.py` (test_collecte_en_erreur_est_journalisee_et_la_suite_continue, test_echec_du_pre_tri_bascule_sur_la_liste_non_triee_et_arrete_la_chaine, test_echec_de_l_indexation_est_dit_et_notifie, test_plusieurs_echecs_nommes_dans_l_ordre, test_liste_a_lire_en_erreur, test_notification_impossible_ne_change_pas_le_code_de_sortie)

#### Scenario: Scoring fails
- **WHEN** the apply command fails
- **THEN** shares and digest are not run, the plain list is written, indexing runs, exit is 1 and the summary names the pre-sort step

#### Scenario: Several failures
- **WHEN** collection, scoring and indexing fail
- **THEN** one notification and one summary line list them in that order

#### Scenario: Database does not answer
- **WHEN** the indexer exits with code 2
- **THEN** the log says the database is unreachable, the summary and the single notification name "indexation (base injoignable)", the dashboard runs, the timestamp is unchanged and exit is 1

### Requirement: Never fail the run on the dashboard
The system SHALL log a failing dashboard generation and keep exit code 0 with no notification.

Source: `tests/watch_sh/test_watch_sh.py` (test_echec_du_dashboard_ne_fait_pas_echouer_la_veille)

#### Scenario: Dashboard error
- **WHEN** the dashboard fails
- **THEN** "Tableau de bord non généré" is logged and exit is 0

### Requirement: Resolve the watch folder through the shared path logic
The system SHALL index the current-named watch folder, and SHALL stop the step with an error naming the migration tool when only a former-named folder exists.

#### Scenario: Former folder only
- **WHEN** only the former folder exists
- **THEN** it is not indexed and the error names the migration tool

### Requirement: Stay inside the user's home in tests and templates
The scheduler file SHALL be a template carrying a label, a script path and one log path used for both outputs, all relative to a home placeholder, with no real absolute path and no former watch name, and SHALL render into a valid property list when the placeholder is replaced. The folder of the script path the template launches SHALL be the tools folder from which the run script derives its own folders (tools and workspace), so that the launched script finds its tools.

Source: `tests/watch_sh/test_watch_sh.py` (Plist, including test_le_chemin_du_plist_est_le_dossier_des_outils_de_watch_sh; test_aucune_commande_reelle_et_rien_hors_du_faux_home)

#### Scenario: Rendering
- **WHEN** the placeholder is substituted
- **THEN** the result parses as a property list whose program argument is the substituted script path

#### Scenario: Script path and tools folder agree
- **WHEN** the rendered program argument is compared with the tools folder declared by the run script
- **THEN** the program's folder equals that tools folder, the workspace is declared inside it, and the program is the run script

### Requirement: Check the uv dependency cache once a day without blocking the run
The system SHALL, at the start of each run and before collection, read the uv version and the Python version uv selects in the workspace, and compare them with the versions recorded in the data folder. When both are recorded and unchanged it SHALL do nothing and print nothing about the cache. When either changed or is not recorded, it SHALL build a throwaway script made only of the dependency header of the Discovery posture's wake script followed by a single `import yaml` line (no wake code is run), copy it into two distinct temporary folders, run it from the first with network access and then, only if that succeeded, from the second in offline mode, both times by relative path and with the Python version read in the workspace, and remove both folders. On success it SHALL record both versions and print that the cache was filled and verified offline. On failure (network run, offline run, missing wake script, or a wake script without a dependency header, in which case nothing is run) it SHALL record nothing, so the check is retried at the next run, print a message pointing to the manual procedure of the installation guide ("After an update of uv"), and raise one desktop notification. When the uv or Python version cannot be read, it SHALL print that the cache check is impossible, raise no notification and run nothing. The cache check SHALL NOT change the steps run nor the exit code, including when the notification itself fails. The repository root SHALL pin a Python version.

Source: `tests/watch_sh/test_watch_sh.py` (CacheUv, including test_le_controle_du_cache_precede_la_collecte)

#### Scenario: Versions unchanged
- **WHEN** the recorded uv and Python versions equal the current ones
- **THEN** no throwaway script is run and the output does not mention the cache

#### Scenario: uv updated
- **WHEN** the uv version differs from the recorded one
- **THEN** the throwaway script runs with network then offline, the output says "Cache de uv rempli et vérifié hors ligne", the new version is recorded, no notification is raised and exit code is 0; a second run does not check again

#### Scenario: Offline run fails
- **WHEN** the offline run of the throwaway script fails
- **THEN** one notification and one output line mention "After an update of uv", the recorded version is unchanged, collection and dashboard still run, and exit code is 0

#### Scenario: Network run fails
- **WHEN** the run with network access fails
- **THEN** the offline run is not attempted, one notification is raised and exit code is 0

#### Scenario: Version unreadable
- **WHEN** uv cannot report the Python version
- **THEN** the output says "Contrôle du cache de uv impossible", no notification is raised, no throwaway script is run and exit code is 0

#### Scenario: Throwaway script content
- **WHEN** the check runs against the real wake script
- **THEN** each throwaway copy holds exactly the wake script's dependency header and, apart from blank lines, only `import yaml`

### Requirement: Probe the BM25 index after a good indexation, without blocking
The system SHALL run the indexer's BM25 probe after a successful indexation. A probe exiting with code 3 SHALL be logged as an unreadable BM25 index naming the "Damaged BM25 index" section of the installation guide and SHALL raise one notification pointing to it; any other non-zero code SHALL be logged with its code and raise one notification. A failing probe SHALL NOT count as a failed step, SHALL leave the exit code unchanged and SHALL let later steps continue. The system SHALL NOT repair anything (rebuilding the index is done by the user alone) and SHALL NOT run the probe when indexing fails or is skipped.

#### Scenario: Unreadable BM25 index
- **WHEN** the probe exits with code 3
- **THEN** the log names the unreadable index and the guide section, one notification is raised, the dashboard still runs and exit is 0

#### Scenario: Other probe failure
- **WHEN** the probe exits with another non-zero code
- **THEN** the log gives the code, one notification is raised, and exit is 0

#### Scenario: Probe passes
- **WHEN** the probe exits with 0
- **THEN** no notification is raised

#### Scenario: Indexing failed
- **WHEN** the indexation fails
- **THEN** the probe is not run

### Requirement: Compare with the former path during the parity window, without blocking
The system SHALL, only when the parity marker exists in the data folder, after a successful indexation and probe, run the frozen former indexer on the same two folders and then the parity comparison with the start date read from the marker. A missing frozen copy, a failing former indexer or an "écart" verdict SHALL be logged with the key phrases of design.md D9 and SHALL raise one notification. The parity step SHALL NOT count as a failed step, SHALL NOT change the exit code, SHALL NOT run when the marker is absent, when the indexation failed or when the model service is absent, and SHALL NOT write into the database.

#### Scenario: Marker absent
- **WHEN** the parity marker does not exist
- **THEN** neither the former indexer nor the comparison is run

#### Scenario: Verdict different
- **WHEN** the marker exists and the comparison exits with code 1
- **THEN** the log says the parity is different, one notification is raised, the dashboard runs and exit is 0

#### Scenario: Frozen copy missing
- **WHEN** the marker exists and the frozen former path is absent
- **THEN** the log says the comparison is impossible, one notification is raised, no comparison runs and exit is 0

