# watch-shadow-scoring

## Purpose

Optional second scoring of each article with English prompts ("shadow"), strictly without effect on any decision, and a comparison report.

Source of truth: `tests/watch_triage/test_shadow.py`, `tools/watch_triage.py`, `tools/watch_config.py`, `tools/watch_prompts_en.py`.

## Requirements

### Requirement: Validate the shadow setting strictly
The system SHALL treat an absent shadow block as disabled with English as language, accept only the keys `enabled` (boolean) and `language` (English), reject unknown keys, wrong types, other languages, non-mapping blocks and duplicated keys, report the offending line when loaded through the strict loader, and never echo the rejected value in the error.

Source: `tests/watch_triage/test_shadow.py` (Reglage)

#### Scenario: Unknown key
- **WHEN** the block holds an unknown key
- **THEN** a configuration error mentions the key and its line number

#### Scenario: Secret-looking value
- **WHEN** a wrong value is given
- **THEN** the error message does not contain it

#### Scenario: Tracked settings
- **WHEN** the tracked triage settings are loaded through the strict loader
- **THEN** their shadow block is valid, with a boolean enabled flag and English as language (the flag's value is the user's choice and is not checked)

### Requirement: Do nothing extra when the shadow is inactive
The system SHALL make no shadow model call and store no shadow row when the shadow is inactive or absent, or when scoring runs without the model. It SHALL NOT load the English prompts for the shadow in those cases. The English prompts SHALL be loaded only when the triage language itself is English.

Source: `tests/watch_triage/test_shadow.py` (Notation.test_inactive_aucune_ligne_et_aucun_appel_en_plus, test_reglage_absent_equivaut_a_inactif, test_sans_modele_pas_d_ombre)

#### Scenario: Inactive
- **WHEN** six articles are scored with the shadow disabled and the French triage language
- **THEN** six French model calls, zero English calls, zero shadow rows

### Requirement: Store one shadow row per scored article
When active, the system SHALL score each article a second time with the same model and the English prompts and themes, and store one row per article with language, model, a 12-hex fingerprint of the prompts, criteria, substance, flags and timestamp; rescoring SHALL replace the row.

Source: `tests/watch_triage/test_shadow.py` (Notation.test_active_une_ligne_par_article_avec_l_empreinte, test_renotation_remplace_la_ligne)

#### Scenario: Active
- **WHEN** six articles are scored with the shadow enabled
- **THEN** six shadow rows exist with the same fingerprint and the output matches "Notation en ombre (en) : 6 notés, 0 échec(s)"

#### Scenario: Rescoring
- **WHEN** an article already holding a shadow row is scored again
- **THEN** its row is replaced

### Requirement: Change the shadow fingerprint with the prompts
The fingerprint of the shadow prompts SHALL change when the prompts, criterion questions or themes change.

Source: `tests/watch_triage/test_shadow.py` (Notation.test_l_empreinte_change_avec_les_prompts)

#### Scenario: Prompts changed
- **WHEN** the English prompts, a criterion question or the themes change
- **THEN** the fingerprint differs from the previous one

### Requirement: Report shadow scoring counts
When active, the output SHALL report counts of scored and failed shadow notations and elapsed seconds.

Source: `tests/watch_triage/test_shadow.py` (Notation.test_active_une_ligne_par_article_avec_l_empreinte)

#### Scenario: Counts in the output
- **WHEN** six articles are scored with the shadow enabled and none fails
- **THEN** the output matches "Notation en ombre (en) : 6 notés, 0 échec(s)" and gives the elapsed seconds

### Requirement: Never let the shadow change a decision
The system SHALL keep scores, ranking, reading list, discarded articles and article locations identical whether the shadow is active or not, even when the shadow notation differs.

Source: `tests/watch_triage/test_shadow.py` (Notation.test_l_ombre_ne_change_aucune_decision, test_la_photo_ignore_l_heure_de_notation)

#### Scenario: Same corpus twice
- **WHEN** the same corpus is scored with the shadow off then on, with an English model that scores differently
- **THEN** scores, ranking, reading list, moved and remaining files and locations are equal

#### Scenario: Scoring time differs
- **WHEN** two identical scorings differ only by their scoring timestamp (to the second), which is not a decision and is excluded from the comparison
- **THEN** the compared decisions are equal

### Requirement: Keep the decision payload in the triage language
The decision model payload SHALL stay exactly the prompts of the triage language, which are the French prompts when the language is French or absent.

Source: `tests/watch_triage/test_shadow.py` (Notation.test_le_francais_garde_sa_charge_utile)

#### Scenario: French triage with the shadow active
- **WHEN** the triage language is French or absent and the shadow is active
- **THEN** the decision model receives exactly the French prompts

### Requirement: Isolate shadow failures
The system SHALL write the French score even when the shadow fails (unreadable answer, network error, timeout on one article, failing or missing prompt module), count failures in the output, and disable the shadow for the pass with a message when the prompt module cannot be loaded.

Source: `tests/watch_triage/test_shadow.py` (Notation.test_echec_de_l_ombre_la_note_francaise_est_ecrite, test_echec_partiel_compte, test_module_de_prompts_defaillant_ne_bloque_pas_la_notation)

#### Scenario: Partial failure
- **WHEN** the English call fails for one of six articles
- **THEN** the output reports "5 notés, 1 échec(s)" and all French scores are stored

### Requirement: Retry an unusable English answer once
An unusable English answer SHALL be retried once and a network error SHALL NOT be retried.

Source: `tests/watch_triage/test_partages_semaine.py` (RelanceEnAnglais)

#### Scenario: Unusable answer then network error
- **WHEN** the English answer is unusable, or the English call raises a network error
- **THEN** the unusable answer is retried once, and the network error is not retried

### Requirement: Enforce a prompt module contract
The system SHALL accept a prompt module only if it provides a system prompt with a themes placeholder, a user prompt containing title, source, text, criteria and the answer keys, the exact criteria keys of the French set, and non-empty themes; otherwise it SHALL raise a value error. The shipped English module SHALL satisfy the contract and its system prompt SHALL differ from the French one.

Source: `tests/watch_triage/test_shadow.py` (Contrat)

#### Scenario: Incomplete module
- **WHEN** any of the four required parts is missing or the criteria keys differ
- **THEN** validation raises an error

### Requirement: Compare languages in a read-only report
The `shadow-report` command SHALL, in the terminal only, report: articles scored in both languages; agreement on keep/discard at the current threshold; mean substance in each language with mean and absolute differences; per-criterion disagreement counts; and the list of decision disagreements with each side's substance, decision and missing criteria, limited by a count option (stating the limit).

Source: `tests/watch_triage/test_shadow.py` (Rapport)

#### Scenario: Report content
- **WHEN** four articles are scored in both languages with differing decisions on two
- **THEN** the report gives 2/4 agreement, the disagreement list shows both decisions, and an article scored in French only is absent

### Requirement: Compare the shadow with the user's calibration opinions
The `shadow-report` command SHALL report agreement with the user's calibration opinions stored in the database, and agreement on rescues (keep) and manual rejections (discard). It SHALL state "no common article" for calibration when no calibration opinion is stored, and SHALL NOT read the calibration sheet.

Source: `tests/watch_triage/test_shadow.py` (Rapport)

#### Scenario: No calibration opinion
- **WHEN** the report runs while no calibration opinion is stored, even if a sheet exists
- **THEN** the calibration part states "no common article"

### Requirement: Report articles without a shadow comparison
The `shadow-report` command SHALL ignore articles scored in one language only, and SHALL say "no article scored in both languages" and whether the shadow is inactive or active when there is no data.

Source: `tests/watch_triage/test_shadow.py` (Rapport)

#### Scenario: No data
- **WHEN** the report runs while no article is scored in both languages
- **THEN** it says "no article scored in both languages" and whether the shadow is inactive or active

### Requirement: Keep the shadow report read-only
The `shadow-report` command SHALL connect under the knowledge read-only role, SHALL write no file nor modify any table, and SHALL NOT create the settings file. Its discard-reason rule SHALL be the same function used by ranking.

Source: `tests/watch_triage/test_shadow.py` (Rapport)

#### Scenario: Read only
- **WHEN** the report runs
- **THEN** the set of files with their modification times, the shadow rows and the calibration entries are unchanged, and the connection used is the read-only one

#### Scenario: Same discard-reason rule as ranking
- **WHEN** the report gives the discard reason of an article
- **THEN** it comes from the same function used by ranking

### Requirement: Catch up the shadow on articles already scored in French
The `shadow-backfill` command SHALL score in the shadow language, with the shadow prompts, themes and model, the articles already scored in French (grid filled, complete article), in the library or set aside, that have no shadow row or a shadow row made with another prompt fingerprint. The watch run takes no lock, so the command SHALL NOT be run during the morning watch run (documented).

Source: `tests/watch_triage/test_shadow_backfill.py` (Ecritures, Reprise, Echecs, Ordre, Limite, Refus)

#### Scenario: Articles to catch up
- **WHEN** some articles scored in French have no shadow row, one has a row with another prompt fingerprint and one has a row with the current fingerprint
- **THEN** the first ones and the stale one are scored in the shadow language, and the current one is not

### Requirement: Write only the shadow table during the catch-up
The `shadow-backfill` command SHALL write only to the shadow table: the French scores, the forced and excluded tables, the calibration entries, the thresholds, the reading list and the set-aside articles SHALL stay unchanged.

Source: `tests/watch_triage/test_shadow_backfill.py` (Ecritures)

#### Scenario: Nothing else changes
- **WHEN** six articles scored in French, some set aside, are caught up
- **THEN** six shadow rows exist and the scores, forced and excluded tables, the calibration entries, the reading list and every article file are identical to before

### Requirement: Resume an interrupted catch-up
In the `shadow-backfill` command, an article already scored with the current fingerprint SHALL NOT be scored again (so an interrupted pass resumes).

Source: `tests/watch_triage/test_shadow_backfill.py` (Reprise)

#### Scenario: Resume
- **WHEN** the command runs twice, or after an interruption
- **THEN** the second run scores nothing for articles already scored with the current fingerprint, and rescores only the one whose fingerprint is stale

### Requirement: Catch up articles with a calibration opinion first
In the `shadow-backfill` command, articles with a calibration opinion (keep or discard) stored in the database SHALL come first, then the others in file order; the calibration sheet SHALL NOT be read.

Source: `tests/watch_triage/test_shadow_backfill.py` (Ordre)

#### Scenario: Opinions first
- **WHEN** the database holds calibration opinions on two articles
- **THEN** those two are scored before the others

### Requirement: Count catch-up failures and bound the pass
In the `shadow-backfill` command, a failure of the model SHALL be counted without stopping the pass, a missing file SHALL be skipped and counted, `--limit N` SHALL bound the pass, and the command SHALL print progress as `[n/N]` and a final summary (scored, failures, skipped, duration).

Source: `tests/watch_triage/test_shadow_backfill.py` (Echecs, Limite)

#### Scenario: Failure and missing file
- **WHEN** the model fails on one article and another article's file is missing
- **THEN** the pass continues, the failure and the skipped file are counted, and the final summary gives scored, failures, skipped and duration

#### Scenario: Limit
- **WHEN** `--limit N` is given
- **THEN** the pass is bounded by N and its progress is printed as `[n/N]`

### Requirement: Refuse the catch-up when a prerequisite is missing
The `shadow-backfill` command SHALL refuse with a clear message when the shadow is disabled, when the shadow prompts cannot be loaded, when the model service does not answer, or when the database does not answer (code and message of design.md D4, before any model call).

Source: `tests/watch_triage/test_shadow_backfill.py` (Refus)

#### Scenario: Shadow disabled
- **WHEN** the shadow is disabled in the settings
- **THEN** the command exits with a message and calls no model

#### Scenario: Database down
- **WHEN** the database does not answer
- **THEN** the command exits with the code of design.md D4 and calls no model

### Requirement: The shadow ends at the batch 5b decision
The system SHALL keep the shadow scoring available until the user has measured the batch 5b English prompts with the shadow catch-up and the shadow report. After that measurement, the tracked triage settings SHALL disable the shadow. The removal of the shadow SHALL NOT happen in batch 5b; it is decided in a later batch.

Source: project decision recorded with this change; the disabled flag is set by the last implementation task (tasks.md, 4.4); no automated test checks the flag's value

#### Scenario: Before the measurement
- **WHEN** the user has not yet measured the English prompts
- **THEN** the shadow stays enabled in the tracked settings and still has no effect on any decision

### Requirement: Keep the shadow data and code once disabled
Disabling the shadow SHALL keep the stored shadow rows, the shadow setting, the catch-up command, the report and their code: the report keeps reading the stored rows.

Source: project decision recorded with this change (tasks.md, 4.4); no automated test checks it

#### Scenario: After the measurement
- **WHEN** the measurement is done and the shadow is disabled
- **THEN** no new shadow row is written, the stored rows remain, and the shadow report still prints the comparison from them

### Requirement: Store shadow scores in the database, apart from every decision
The system SHALL store the shadow scores in their own table of the knowledge schema, one row per article address and language, and SHALL NOT read that table in scoring decisions, ranking, reading lists, moves, thresholds or calibration. It SHALL NOT keep shadow scores in a local file.

Source: tests/watch_triage/test_shadow.py

#### Scenario: Shadow rows in the database
- **WHEN** six articles are scored with the shadow enabled
- **THEN** six shadow rows exist in the database table, one per address and language, and no local file holds them

#### Scenario: Decisions ignore the table
- **WHEN** the shadow table is emptied and the reading list is written again
- **THEN** the reading list, the discard reasons and the article locations are identical
