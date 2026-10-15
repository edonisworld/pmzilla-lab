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
When active, the system SHALL score each article a second time with the same model and the English prompts and themes, and store one row per article with language, model, a 12-hex fingerprint of the prompts, criteria, substance, flags and timestamp; rescoring SHALL replace the row. The fingerprint SHALL change when the prompts, criterion questions or themes change. The output SHALL report counts of scored and failed shadow notations and elapsed seconds.

Source: `tests/watch_triage/test_shadow.py` (Notation.test_active_une_ligne_par_article_avec_l_empreinte, test_l_empreinte_change_avec_les_prompts, test_renotation_remplace_la_ligne)

#### Scenario: Active
- **WHEN** six articles are scored with the shadow enabled
- **THEN** six shadow rows exist with the same fingerprint and the output matches "Notation en ombre (en) : 6 notés, 0 échec(s)"

### Requirement: Never let the shadow change a decision
The system SHALL keep scores, ranking, reading list, discarded articles and article locations identical whether the shadow is active or not, even when the shadow notation differs. The scoring timestamp (to the second) is not a decision and is excluded from the comparison. The decision model payload SHALL stay exactly the prompts of the triage language, which are the French prompts when the language is French or absent.

Source: `tests/watch_triage/test_shadow.py` (Notation.test_l_ombre_ne_change_aucune_decision, test_la_photo_ignore_l_heure_de_notation, test_le_francais_garde_sa_charge_utile)

#### Scenario: Same corpus twice
- **WHEN** the same corpus is scored with the shadow off then on, with an English model that scores differently
- **THEN** scores, ranking, reading list, moved and remaining files and locations are equal

#### Scenario: Scoring time differs
- **WHEN** two identical scorings differ only by their scoring timestamp
- **THEN** the compared decisions are equal

### Requirement: Isolate shadow failures
The system SHALL write the French score even when the shadow fails (unreadable answer, network error, timeout on one article, failing or missing prompt module), count failures in the output, and disable the shadow for the pass with a message when the prompt module cannot be loaded. An unusable English answer SHALL be retried once and a network error SHALL NOT be retried.

Source: `tests/watch_triage/test_shadow.py` (Notation.test_echec_de_l_ombre_la_note_francaise_est_ecrite, test_echec_partiel_compte, test_module_de_prompts_defaillant_ne_bloque_pas_la_notation); `tests/watch_triage/test_partages_semaine.py` (RelanceEnAnglais)

#### Scenario: Partial failure
- **WHEN** the English call fails for one of six articles
- **THEN** the output reports "5 notés, 1 échec(s)" and all French scores are stored

### Requirement: Enforce a prompt module contract
The system SHALL accept a prompt module only if it provides a system prompt with a themes placeholder, a user prompt containing title, source, text, criteria and the answer keys, the exact criteria keys of the French set, and non-empty themes; otherwise it SHALL raise a value error. The shipped English module SHALL satisfy the contract and its system prompt SHALL differ from the French one.

Source: `tests/watch_triage/test_shadow.py` (Contrat)

#### Scenario: Incomplete module
- **WHEN** any of the four required parts is missing or the criteria keys differ
- **THEN** validation raises an error

### Requirement: Compare languages in a read-only report
The `shadow-report` command SHALL, in the terminal only, report: articles scored in both languages; agreement on keep/discard at the current threshold; mean substance in each language with mean and absolute differences; per-criterion disagreement counts; agreement with the user's calibration opinions stored in the database; agreement on rescues (keep) and manual rejections (discard); and the list of decision disagreements with each side's substance, decision and missing criteria, limited by a count option (stating the limit). It SHALL ignore articles scored in one language only, SHALL say "no article scored in both languages" and whether the shadow is inactive or active when there is no data, and SHALL state "no common article" for calibration when no calibration opinion is stored. It SHALL connect under the knowledge read-only role, SHALL write no file nor modify any table, SHALL NOT read the calibration sheet, and SHALL NOT create the settings file. The discard-reason rule SHALL be the same function used by ranking.

Source: `tests/watch_triage/test_shadow.py` (Rapport)

#### Scenario: Report content
- **WHEN** four articles are scored in both languages with differing decisions on two
- **THEN** the report gives 2/4 agreement, the disagreement list shows both decisions, and an article scored in French only is absent

#### Scenario: Read only
- **WHEN** the report runs
- **THEN** the set of files with their modification times, the shadow rows and the calibration entries are unchanged, and the connection used is the read-only one

#### Scenario: No calibration opinion
- **WHEN** the report runs while no calibration opinion is stored, even if a sheet exists
- **THEN** the calibration part states "no common article"

### Requirement: Catch up the shadow on articles already scored in French
The `shadow-backfill` command SHALL score in the shadow language, with the shadow prompts, themes and model, the articles already scored in French (grid filled, complete article), in the library or set aside, that have no shadow row or a shadow row made with another prompt fingerprint, and SHALL write only to the shadow table: the French scores, the forced and excluded tables, the calibration entries, the thresholds, the reading list and the set-aside articles SHALL stay unchanged. It SHALL refuse with a clear message when the shadow is disabled, when the shadow prompts cannot be loaded, when the model service does not answer, or when the database does not answer (code and message of design.md D4, before any model call). Articles with a calibration opinion (keep or discard) stored in the database SHALL come first, then the others in file order; the calibration sheet SHALL NOT be read. An article already scored with the current fingerprint SHALL NOT be scored again (so an interrupted pass resumes). A failure of the model SHALL be counted without stopping the pass, a missing file SHALL be skipped and counted, `--limit N` SHALL bound the pass, and the command SHALL print progress as `[n/N]` and a final summary (scored, failures, skipped, duration). The watch run takes no lock, so the command SHALL NOT be run during the morning watch run (documented).

Source: `tests/watch_triage/test_shadow_backfill.py` (Ecritures, Reprise, Echecs, Ordre, Limite, Refus)

#### Scenario: Nothing else changes
- **WHEN** six articles scored in French, some set aside, are caught up
- **THEN** six shadow rows exist and the scores, forced and excluded tables, the calibration entries, the reading list and every article file are identical to before

#### Scenario: Resume
- **WHEN** the command runs twice, or after an interruption
- **THEN** the second run scores nothing for articles already scored with the current fingerprint, and rescores only the one whose fingerprint is stale

#### Scenario: Opinions first
- **WHEN** the database holds calibration opinions on two articles
- **THEN** those two are scored before the others

#### Scenario: Shadow disabled
- **WHEN** the shadow is disabled in the settings
- **THEN** the command exits with a message and calls no model

#### Scenario: Database down
- **WHEN** the database does not answer
- **THEN** the command exits with the code of design.md D4 and calls no model

### Requirement: The shadow ends at the batch 5b decision
The system SHALL keep the shadow scoring available until the user has measured the batch 5b English prompts with the shadow catch-up and the shadow report. After that measurement, the tracked triage settings SHALL disable the shadow. Disabling SHALL keep the stored shadow rows, the shadow setting, the catch-up command, the report and their code: the report keeps reading the stored rows. The removal of the shadow SHALL NOT happen in batch 5b; it is decided in a later batch.

Source: project decision recorded with this change; the disabled flag is set by the last implementation task (tasks.md, 4.4); no automated test checks the flag's value

#### Scenario: Before the measurement
- **WHEN** the user has not yet measured the English prompts
- **THEN** the shadow stays enabled in the tracked settings and still has no effect on any decision

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
