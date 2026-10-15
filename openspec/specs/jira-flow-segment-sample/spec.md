# jira-flow-segment-sample

## Purpose

Terminal-only sampling of the tickets behind a time-per-segment figure of a flow report: population, longest tickets, near-median draw, oldest tickets still in the segment, per-state breakdown, batch-closure exclusion, project starts against a random reference, and the output language.

The tool works on the flow-metrics data (ticket exports and status-history cache); its flow calculations are those of the flow report tool.

Source of truth: `tests/segment_sample/test_segment_sample.py`, `tests/segment_sample/test_language.py`, `tests/segment_sample/reference_en.md` (structure only), `tools/segment_sample.py`, `tools/segment_sample_messages.py`.

## Requirements

### Requirement: Use the same population and calculation as the flow report
The system SHALL sample tickets that left the chosen segment during the analysed complete weeks, with time summed over all their finished visits to the segment, SHALL use the same exports, history cache, settings, excluded projects and types and calculation functions as the flow report, so that the displayed P50 equals the report's, and SHALL show the states that make up the segment, the number of tickets without history and the number set aside.

Source: `tests/segment_sample/test_segment_sample.py` (TestEchantillon.test_etats_du_segment_et_population, test_meme_population_que_flux_jira)

#### Scenario: Same figures as the report
- **WHEN** the sample and the flow report are computed on the same export and date
- **THEN** the population size, P50, P85, mean and the count of tickets still in the segment are those of the report

#### Scenario: Segment states
- **WHEN** the sample runs
- **THEN** the states composing the segment are listed, states of other steps are not, and counts of tickets without history and of set-aside tickets (excluded project or type) appear

### Requirement: Show the longest tickets, a near-median draw and the oldest tickets still inside
The system SHALL show, for each sampled ticket, its key, project, cumulative days, number of visits, entry and exit dates of its longest visit, days of that visit, origin state and destination state, SHALL use markers for a created ticket (no origin) and a ticket resolved from the segment, SHALL list the longest tickets, then a random draw among tickets within a window around the median that does not overlap the longest, and, apart, the oldest tickets still in the segment with the age of their current visit and cumulative time including previous visits.

Source: `tests/segment_sample/test_segment_sample.py` (TestEchantillon.test_cas_construits, test_resolu_depuis_le_segment, test_plus_longs_puis_proches_sans_recouvrement, test_plus_anciens_dans_le_segment, test_aller_retour_encore_dans_le_segment)

#### Scenario: Built cases
- **WHEN** tickets with a return, a creation directly in the segment and a resolution from the segment exist
- **THEN** each row shows its days, visits, dates and origin and destination, using the creation or resolved marker where applicable, and out-of-population tickets do not appear

#### Scenario: Longest then near-median
- **WHEN** the sample is shown
- **THEN** the longest are in decreasing order, the near-median rows lie inside the printed window and none is also among the longest

#### Scenario: Still inside after a return
- **WHEN** a ticket left and came back to the segment
- **THEN** its current visit age and its cumulative time over two visits are shown

### Requirement: Make the draw reproducible
The system SHALL give the same draw for the same data, calculation date and seed, and SHALL give different draws for different seeds.

Source: `tests/segment_sample/test_segment_sample.py` (TestEchantillon.test_tirage_reproductible_a_graine_fixe, TestDebuts.test_sortie_identique_d_un_lancement_a_l_autre)

#### Scenario: Same seed
- **WHEN** the tool runs twice with the same seed
- **THEN** the near-median rows are identical

#### Scenario: Other seeds
- **WHEN** several seeds are tried
- **THEN** more than one distinct draw results

### Requirement: Print to the terminal only, with no title and no file written
The system SHALL write nothing to disk, SHALL read no ticket title or person (keys and states only), and SHALL not put the keys in any tracked file; the starts-per-project section SHALL contain no ticket key.

Source: `tests/segment_sample/test_segment_sample.py` (TestEchantillon.test_sortie_sans_titre_ni_ecriture, TestParEtat.test_aucune_ecriture_ni_titre, TestDebuts.test_aucune_cle_dans_la_section_et_sortie_inchangee_sans_option)

#### Scenario: No side effects
- **WHEN** the tool runs on an export whose titles are marked
- **THEN** no title appears and the set of files in the workspace is unchanged

### Requirement: Refuse an unknown segment and a missing history cache
The system SHALL stop with a non-zero code when the segment is not a computed segment, saying so, and when the export has no history cache, saying the cache was not found. A segment SHALL be accepted by its internal name and by its English name with identical output.

Source: `tests/segment_sample/test_segment_sample.py` (TestEchantillon.test_segment_inconnu_et_export_sans_historique, test_segment_sous_son_nom_anglais)

#### Scenario: Unknown segment
- **WHEN** an unknown segment name is passed
- **THEN** the run fails with a message that it is not a computed segment

#### Scenario: Missing cache
- **WHEN** the history cache is removed
- **THEN** the run fails with a "cache not found" message

#### Scenario: English segment name
- **WHEN** the segment is given by its English name
- **THEN** the output equals the one for the internal name

### Requirement: Break the segment time down by state on request
The system SHALL, with the per-state option, add the time spent in each state of the segment over the whole population (state total, share of segment time, P50 and P85 among tickets that passed through the state, and their number), in the order of the settings, with states summing to the segment total; the per-state detail of each sampled ticket (group: longest, near-median draw, still inside), including the ongoing visit; and, for the longest tickets, the number of other tickets whose segment visit ends the same day, with the maximum exits in a day as a baseline. Without the option none of these sections SHALL appear.

Source: `tests/segment_sample/test_segment_sample.py` (TestParEtat)

#### Scenario: Time by state
- **WHEN** the option is used
- **THEN** all states of the segment are listed with totals that add up to the segment total, and an unused state shows zero and dashes

#### Scenario: Ticket still inside after two visits
- **WHEN** a ticket has one finished and one ongoing visit in different states
- **THEN** its row shows days per state with the ongoing visit counted to the reference date

#### Scenario: Grouped exits
- **WHEN** other tickets leave the segment on the same day as a longest ticket's longest visit
- **THEN** their number is shown for that ticket and the maximum per day is stated

#### Scenario: Without the option
- **WHEN** the option is omitted
- **THEN** no per-state or grouped-exit section is shown

### Requirement: Exclude batch closures on request
The system SHALL, with the batch-closure option, remove from the population, before any calculation, the delivered tickets whose resolution falls in the same minute as at least a threshold of other tickets of the same project among the configured closure reasons, SHALL apply the same rule as the flow report (shared function), SHALL state at the top how many tickets and segment passes are removed, and SHALL never count as a batch a ticket whose resolution has no time of day, reporting how many such tickets there are. Without the option the output SHALL NOT change.

Source: `tests/segment_sample/test_segment_sample.py` (TestFermeturesEnLot)

#### Scenario: A batch in one minute
- **WHEN** six tickets of one project are resolved in the same minute and the batch threshold is five (the threshold itself is configurable)
- **THEN** they leave the population while tickets resolved over several minutes, or four in the same minute, stay

#### Scenario: Header and downstream figures
- **WHEN** the option is used with the per-state and starts sections
- **THEN** the header counts the removed tickets and passes and every figure is computed without them

#### Scenario: No time of day
- **WHEN** resolutions have no hour
- **THEN** no ticket is in a batch and the count of such tickets is reported

#### Scenario: Option off
- **WHEN** the option is omitted
- **THEN** the output is unchanged and stable

#### Scenario: Same rule as the report
- **WHEN** the shared rule is applied to a set with five tickets in one minute and four in the next
- **THEN** five tickets form a batch for the matching reason and none for a non-matching reason

### Requirement: Compare per-project verification starts to a random reference
The system SHALL, with the starts option, list per project with at least a minimum number of passes (settable) the passes from the waiting state to the ongoing verification state (direct passes only, each visit counting once), the number of distinct days, the share of passes on the busiest fifth of days, the median wait before each pass, and two comparisons against random draws of the project's passes over the working days of the period with French public holidays removed: the concentration at equal active days (expected share, upper percentile, indicator "more concentrated") and the number of active days (expected distinct days, lower percentile, ratio, indicator "fewer active days than chance"). The reference SHALL be reproducible for a given seed, SHALL not depend on the other projects, SHALL keep the observed share equal to the percentile as not above it, and SHALL give percentiles at least the mean. Both comparisons SHALL read the same random draws. When the period has no working day, the system SHALL NOT compute a reference and SHALL show dashes in the reference columns. Projects below the minimum SHALL be counted, and when none reaches it a message SHALL say so. Without the option the section SHALL NOT appear.

Source: `tests/segment_sample/test_segment_sample.py` (TestDebuts, TestPartAttendue, TestIndicateurDeReference)

#### Scenario: No working day
- **WHEN** the period holds only a weekend
- **THEN** the project row shows its passes and observed share, and dashes in every reference column

#### Scenario: Concentrated and spread projects
- **WHEN** one project has all its passes on few days and another one pass per day
- **THEN** the former shows a high observed share flagged "more concentrated" and "fewer active days", the latter neither

#### Scenario: Direct passes only
- **WHEN** a ticket passes through an intermediate state before the ongoing state, or goes through the waiting state twice
- **THEN** the indirect pass is not counted and each of the two visits counts once

#### Scenario: Threshold
- **WHEN** the minimum is raised above every project, or lowered to include a small project
- **THEN** a "no project reaches the threshold" message appears, respectively the small project is listed, and projects below are counted

#### Scenario: Holidays and weekends
- **WHEN** the working days of the period are computed
- **THEN** weekends and French public holidays are excluded from the period and from the draws, and passes on those days are outside the model

#### Scenario: Stable output
- **WHEN** the tool runs twice with the same seed
- **THEN** the section is identical, including the reference columns, and another seed changes the draws

### Requirement: Print in French by default and in English on request
The system SHALL print the report in French by default and in English with the language option, SHALL give the same data (keys, figures, states) in both, SHALL contain no French text in the English output, SHALL match a versioned English snapshot, SHALL refuse an unknown language, and SHALL keep message catalogues coherent between languages.

Source: `tests/segment_sample/test_language.py`

#### Scenario: Default language
- **WHEN** no language is given
- **THEN** the title and markers are French

#### Scenario: English
- **WHEN** the language option is set to English
- **THEN** the title and markers are English and no French word remains in any line

#### Scenario: Same data
- **WHEN** the two languages are compared
- **THEN** the ticket keys and numbers are the same

#### Scenario: Unknown language
- **WHEN** a language other than French or English is given
- **THEN** the exit code is 2

### Requirement: Former option names refused
The system SHALL refuse a former French option name with a non-zero exit code, a message naming the current option and nothing on stdout.

Source: `tests/segment_sample/test_segment_sample.py` (test_anciennes_options_refusees_avec_le_nom_actuel), `tests/segment_sample/test_language.py` (test_ancienne_option_langue_refusee)

#### Scenario: Former option names
- **WHEN** the former option name for date, longest, seed or language is used
- **THEN** the run fails (exit code 2 for the language option), stderr says the option no longer exists and names the current one, and stdout is empty

## Open questions

1. The tool accepts a project-scope option, exercised only by the English snapshot (a scope without a match); its expected behaviour is not described by an assertion and is not specified here.
