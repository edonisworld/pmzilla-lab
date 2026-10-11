# watch-triage

## Purpose

Pre-sorting of collected articles by a local model: scoring, ranking, mode observation versus mode filter, calibration, thresholds, shares, weekly inventory, source suggestions and the triage settings file.

Source of truth: `tests/watch_triage/test_watch_triage.py`, `tests/watch_triage/test_robustesse.py`, `tools/watch_triage.py`, `tools/watch_config.py`.
## Requirements
### Requirement: Create and edit the triage settings preserving comments
The system SHALL create the triage settings file on first use with observation mode by default, an explicit French `language` line, no social handle key and a comment pointing to the local settings file. It SHALL update one setting in place without losing comments, appending the key when absent. Updating a setting SHALL write only the tracked settings file, never the local one.

Source: `tests/watch_triage/test_watch_triage.py` (Classement.test_reglages_crees_au_premier_lancement_et_commentaires_conserves, Reglages.test_set_config_en_nouveaux_noms_et_ajout_si_absent)

#### Scenario: First launch
- **WHEN** settings are read and no file exists
- **THEN** a file is created with mode observation, French language and no handle key, and later edits keep its comments

#### Scenario: Local file untouched
- **WHEN** a setting is updated and a local settings file exists
- **THEN** the local file is unchanged

### Requirement: Accept former setting and option names with a warning
The system SHALL load settings written with former French key names (mapped to the English names) with one warning per key, load English names silently, and refuse a file that holds both names of the same setting. Writing a setting to a file in former names SHALL update the existing former-named line and keep its comment. A text migration function SHALL rename the keys, keep comments and be idempotent. Former option names SHALL be accepted with a "renamed" warning, and the former French sub-commands SHALL be refused. Public help and option names SHALL NOT contain the user's name.

Source: `tests/watch_triage/test_watch_triage.py` (Reglages)

#### Scenario: Former keys
- **WHEN** settings use former key names
- **THEN** values load under the new names and a warning names each former key

#### Scenario: Both names present
- **WHEN** a setting appears under both its former and new name
- **THEN** loading stops with an error saying it is the same setting

#### Scenario: Former sub-command
- **WHEN** a former French sub-command is invoked
- **THEN** the command exits with an error

### Requirement: Rank articles by relevance and give discard reasons
The system SHALL compute for every scored article a relevance, as a rank on a 0-100 scale by proximity to reference articles, and a list of discard reasons:
- outside the user's themes, with the model's justification;
- promotional content;
- reading compilation;
- excerpt only (no score);
- each unmet substance criterion, when the number of satisfied criteria is below the substance threshold;
- relevance below the optional relevance threshold, for articles collected within the settings period only.

Relevance SHALL order the reading list. It SHALL decide filtering only through the relevance threshold and SHALL NOT discard any article collected before the period. A manual exclusion SHALL override a good score, and a manual rescue SHALL override a poor one. The command SHALL stop with an error when there are no references or no scored articles.

Source: `tests/watch_triage/test_watch_triage.py` (Classement)

#### Scenario: Reasons
- **WHEN** articles are scored with different flags
- **THEN** the closest to the reference gets relevance 100, the farthest 0, and each discarded article lists its specific reasons

#### Scenario: Threshold decides
- **WHEN** the substance threshold is raised above an article's satisfied criteria
- **THEN** the unmet criteria become its discard reasons

#### Scenario: Manual override
- **WHEN** a good article is manually excluded and a weak one rescued
- **THEN** the first shows the reason "écarté à la main" and the second has no reason

#### Scenario: No relevance threshold
- **WHEN** no relevance threshold is set
- **THEN** relevance gives no discard reason to any article

### Requirement: Build references and score new articles
The system SHALL build the reference set from the user's assistant conversation exports and from the user's own articles, read in the folder of the personal collection (its generic name defined in the code). Rebuilding the references SHALL replace every previous reference that is not a share, whatever label it was stored under, and SHALL keep share references. The system SHALL score articles not yet scored with a local model, storing relevance vector, criteria with justifications, flags, summary and why-it-matters; a rescore option SHALL redo existing scores and a no-model option SHALL skip the model call.

Source: `tools/watch_triage.py` (cmd_references, cmd_score); `tests/watch_triage/test_shadow.py` (test_sans_modele_pas_d_ombre); `tests/watch_triage/test_watch_triage.py` (CollectionPersonnelle); `tests/watch_triage/test_robustesse.py` (FusionDesReferences)

#### Scenario: No model
- **WHEN** scoring runs with the no-model option
- **THEN** no model call is made

#### Scenario: Own articles
- **WHEN** references are built with the user's own articles
- **THEN** the articles of the personal collection folder are added and the output gives their number with the collection name

#### Scenario: Rebuild
- **WHEN** references are rebuilt while the store holds share references and references under another label
- **THEN** the share references remain and every other previous reference is replaced

#### Scenario: Second run with fewer references
- **WHEN** references are built a second time from an export that yields fewer conversations
- **THEN** the references of the first run that are not in the second are gone, and running twice with the same references does not duplicate them

### Requirement: Never store a score from an unusable model answer
The system SHALL refuse, for one article, a model answer that is empty, not JSON, truncated, missing a criterion or a flag, or whose criterion or flag is not an object with a true/false value, and SHALL then retry that article once. A timeout SHALL NOT be retried inside the model call itself (one request per attempt) but counts as a failed attempt, so the article is tried at most twice in the pass. When both attempts fail, the article SHALL get no score at all (never a partial or default score), the output SHALL mark it "NON NOTÉ" with the reason and say it is "repris au prochain passage", and the pass SHALL continue with the next article. A model that refuses the thinking option SHALL be asked again once without it. A model unknown to the local service SHALL stop the command with the command to download it. A JSON answer that is valid but not an object, and a response body without a message, SHALL be refused like any other unusable answer (retried once, then "NON NOTÉ"), and SHALL NOT stop the pass.

Source: `tests/watch_triage/test_robustesse.py` (Notation, including the answers that are not an object and the bodies without a message)

#### Scenario: Unusable answer for one article
- **WHEN** the model answers unusably for one of two articles on both attempts
- **THEN** only the other article is scored and the output says "NON NOTÉ" and "repris au prochain passage"

#### Scenario: Timeout then success
- **WHEN** the first attempt for an article times out and the second answers validly
- **THEN** the article is called twice and scored

#### Scenario: Two timeouts
- **WHEN** both attempts for an article time out
- **THEN** the article is not scored, the output says "pas de réponse du modèle", and the next article is scored

#### Scenario: Unknown model
- **WHEN** the local service answers that the model does not exist
- **THEN** the command stops with a message containing the download command for that model

### Requirement: Keep observation mode non-destructive and filter mode moving discarded articles
In observation mode, `apply` SHALL announce the mode and move nothing. In filter mode, `apply` SHALL move every article that has discard reasons from the library folder to the excluded folder (never delete), record the new location, report the number moved, and move nothing on a second run. Articles scored but no longer in the library SHALL be ignored.

Source: `tests/watch_triage/test_watch_triage.py` (Filtre)

#### Scenario: Observation
- **WHEN** apply runs in observation mode
- **THEN** all files stay and the excluded folder is not created

#### Scenario: Filter
- **WHEN** apply runs in filter mode with a weak and a promotional article
- **THEN** "2 article(s) sorti(s)", both files are in the excluded folder, and a second run reports 0

### Requirement: Exclude and restore articles by hand
The system SHALL let the user exclude an article by file name or path (applied at the next apply) and restore an excluded article to the library, which SHALL protect it from later filtering and cancel a prior manual exclusion. An unknown file SHALL be an error.

Source: `tests/watch_triage/test_watch_triage.py` (Filtre.test_ecarter_a_la_main, test_repecher_ramene_et_protege, test_repecher_annule_un_ecart_manuel)

#### Scenario: Restore protects
- **WHEN** a filtered article with score 0 is restored and apply runs again
- **THEN** the file stays in the library and 0 articles are moved

### Requirement: Write the ranked reading list
The system SHALL write a reading list for the settings period: the top N unread articles (excluding articles the user has already shared), the others by relevance, reading compilations, and the discarded articles with their reasons (headed "would be discarded" in observation mode and "discarded" in filter mode), plus a share statistic when applicable. Picks SHALL be recorded by day. Top picks SHALL be ordered by relevance whatever their publication dates (equal dates decide nothing), and articles of equal relevance and date SHALL keep the same order from one run to the next.

Source: `tools/watch_triage.py` (cmd_digest, share_stats); `tests/watch_triage/test_shadow.py` (photo); `tests/watch_triage/test_robustesse.py` (OrdreADatesEgales)

#### Scenario: Equal publication dates
- **WHEN** three articles published the same day are inserted in an order unrelated to their relevance
- **THEN** the top picks list them from the most to the least relevant

#### Scenario: Equal relevance and date
- **WHEN** the reading list is written several times for articles of equal relevance and date
- **THEN** their order is identical each time

#### Scenario: Shared article
- **WHEN** an article was shared by the user
- **THEN** it is not in the top picks and is marked as shared elsewhere in the list

### Requirement: Read the user's shares and refine references
The system SHALL read the user's recent public social posts when a social handle is configured in the merged settings (local layer first), mark the collected articles the user shared (matching cleaned links and platform identifiers), and add them to the references. With no handle, it SHALL skip the step with a message naming the local settings file. When the social service is unavailable, it SHALL continue the run with a message. It SHALL NOT print the handle.

Source: `tools/watch_triage.py` (cmd_shares); `tests/watch_triage/test_partages_semaine.py` (Partages)

#### Scenario: No handle
- **WHEN** shares runs without a configured handle
- **THEN** a message says the step is skipped, names the local settings file, and nothing is changed

### Requirement: Produce the weekly inventory
The system SHALL write an inventory of retained articles of a period (title, source, link, summary, why-it-matters, relevance, substance, shared flag), by publication date by default or collection date on request, limited to a maximum count, without article text.

Source: `tools/watch_triage.py` (cmd_week); `tests/watch_triage/test_partages_semaine.py` (Semaine); `tests/watch_triage/test_watch_triage.py` (test_main_accepte_ancien_et_nouveau_nom_d_option_et_de_sous_commande)

#### Scenario: Per-run option
- **WHEN** the week command is called with the days and per-collection options
- **THEN** both are parsed and applied to the period computation

### Requirement: Export calibration sheet and propose thresholds from user opinions
The system SHALL export scored articles to a semicolon-separated sheet with the filter's verdict, relevance, missing criteria, flags and an empty opinion column (keep/discard).

The `thresholds` command SHALL:
- refuse to run without the sheet or with too few opinions, stating the count;
- compare opinions with every possible substance threshold, print the table and propose the substance threshold that loses the fewest wanted articles, then keeps the fewest weak ones, then is the least strict;
- read relevance from the sheet without re-exporting it, and print a matrix of wanted articles lost and weak articles kept for every pair of substance threshold and relevance threshold in steps of ten (zero meaning no relevance filtering);
- propose the pair with the highest agreement, then the fewest wanted lost, then the lowest relevance threshold, then the lowest substance threshold, listing the wanted articles that pair loses with the command to restore each;
- report disagreements caused by fixed rules (compilation, promotional) and by wrongly kept articles, with the command to fix each;
- write nothing unless asked to save.

When saving, it SHALL write the substance and relevance thresholds of the combined proposal, keep comments, and keep the mode unchanged.

Source: `tests/watch_triage/test_watch_triage.py` (Calibration)

#### Scenario: Too few opinions
- **WHEN** only two opinions are filled
- **THEN** the command exits with an error mentioning "2 avis"

#### Scenario: Proposal without saving
- **WHEN** thresholds runs with opinions and without save
- **THEN** the substance-only proposal, the combined proposal "Proposition (substance et pertinence)", the matrix and the disagreements are printed, and the settings file is unchanged

#### Scenario: Combined proposal rule
- **WHEN** wanted articles are all highly relevant and weak ones mostly poorly relevant
- **THEN** the combined proposal has a relevance threshold above zero and a higher agreement than the substance-only proposal

#### Scenario: Save
- **WHEN** thresholds runs with save
- **THEN** both thresholds of the combined proposal are stored, comments are kept and the mode remains observation

#### Scenario: Sheet not rewritten
- **WHEN** thresholds runs, with or without save
- **THEN** the calibration sheet is byte-identical afterwards

### Requirement: Suggest new sources from citations
The system SHALL propose, as inactive sources with feed discovery, hosts cited by at least a minimum number of distinct citing sources among retained articles (or by retained compilations even from a single source), up to a maximum, most cited first. It SHALL NOT count citations from discarded articles, repeated citations from the same source, home pages, images, shop or social links, hosts already followed, or hosts cited once. An already suggested source SHALL be updated (counts) while keeping its feed, active flag and suggestion date, with no new feed search. The reset option SHALL remove suggestions never activated and keep active and manually added sources. With no scored article, the command SHALL end without error, say so and point to scoring, still honour reset, and make no network call.

Source: `tests/watch_triage/test_watch_triage.py` (Suggestions)

#### Scenario: Cited by two sources
- **WHEN** a host is cited by articles from two retained sources
- **THEN** it is added inactive with its feed, citation count 2 and example links

#### Scenario: Empty base with reset
- **WHEN** reset runs with no scored article
- **THEN** "Aucun article noté" is printed and never-activated suggestions are removed

### Requirement: Guard the tracked configuration
The tracked settings SHALL load without error and be in filter mode. They SHALL hold a substance threshold that is a number within the range the loader accepts, a `language` that is French or English, a relevance threshold that is absent or an integer from 0 to 100, and a social handle that is absent or empty. The local settings file SHALL NOT be tracked and SHALL be matched by the ignore rules. In the tracked sources file, every source SHALL have a unique key and a boolean active flag, and a note present on a deactivated source SHALL be non-empty (a deactivated source without a note is accepted). The guard SHALL NOT depend on any calibration date, any exact threshold value, any source name or any handle value, and SHALL NOT print a handle.

Source: `tests/watch_triage/test_watch_triage.py` (FichiersSuivis)

#### Scenario: Repository files
- **WHEN** the tracked settings and sources files are loaded
- **THEN** the settings are valid and in filter mode, with a valid language, a relevance threshold absent or in range and no handle value, and every source is well formed

#### Scenario: Handle in the tracked file
- **WHEN** the tracked settings hold a non-empty handle
- **THEN** the guard fails and its message does not contain the handle

#### Scenario: Deactivated source with an empty note
- **WHEN** a deactivated source carries a note that is empty or blank
- **THEN** the guard fails and names the position of the entry in the file

#### Scenario: Deactivated source without a note
- **WHEN** a deactivated source carries no note
- **THEN** the guard still passes

#### Scenario: Duplicated key
- **WHEN** two sources share a key
- **THEN** the guard fails

#### Scenario: Legitimate recalibration
- **WHEN** a source is reactivated, or a new source is deactivated with a note, or a threshold changes within the accepted range
- **THEN** the guard still passes

### Requirement: Keep personal identifiers out of help and option names
The system SHALL keep every personal identifier computed by the scanner out of the public help of the pre-sort commands and out of their current option names; the test SHALL read the identifiers from the scanner and SHALL report a failure without printing the identifier.

Source: tests/watch_triage/test_watch_triage.py (test_aucun_identifiant_personnel_dans_les_options_ni_dans_l_aide)

#### Scenario: References help
- **WHEN** the help of the references command and the current option names are compared with the scanner's identifiers, without regard to case
- **THEN** none is found

### Requirement: Select the scoring prompts by the triage language
The system SHALL read a top-level `language` setting of the triage settings, accepting only French and English, treating an absent key as French, and SHALL score every article for decision with the prompt set of that language: the French prompts and criteria of the triage tool for French, the English prompt module checked by the prompt module contract for English. A value other than the two languages SHALL be refused with the key's line number and without echoing the value, and SHALL stop the command with exit code 1. With English, an English module that cannot be loaded or fails the contract SHALL stop scoring with exit code 1 and a message naming the module (design.md, section 1). It SHALL NOT fall back to the French prompts, and SHALL NOT store any score from that pass. Themes SHALL always come from the `themes` setting. With French, the decision payload SHALL stay byte-identical to the payload before this change.

Source: to be covered by `tests/watch_triage/test_watch_triage.py` (tasks 1.1, 1.2)

#### Scenario: Absent key
- **WHEN** the settings have no `language` key and an article is scored
- **THEN** the model receives the French prompts, identical to before this change

#### Scenario: English
- **WHEN** `language` is English and an article is scored
- **THEN** the model receives the English system and user prompts and English criteria questions, with the themes of the settings

#### Scenario: Unknown language
- **WHEN** `language` holds another value
- **THEN** the command exits with code 1, the message names the key and its line, and the value is not in the message

#### Scenario: Broken English module
- **WHEN** `language` is English and the English module misses a required part
- **THEN** scoring stops with exit code 1 and the module name, no model call is made and no score is stored

### Requirement: Ship an English prompt set for the published edition
The system SHALL ship English prompts that satisfy the prompt module contract and that, compared with the French text, reinforce promotional detection and tighten the compilation rule. Promotional detection SHALL explicitly cover book excerpts and book announcements, webinars and events, and paid courses. The compilation rule SHALL leave an article false when the author's own argument runs through the text, even when the text is organised as a list. The French prompts and criteria SHALL stay byte-identical, which a frozen-fingerprint test guards. Every deliberate deviation of the English text SHALL be recorded in the phrase-by-phrase correspondence document. The English prompts SHALL NOT become official without the user's measurement against the acceptance figures of design.md, section 2.

Source: to be covered by `tests/watch_triage/test_shadow.py` (Contrat) and a French-fingerprint test (task 2.1)

#### Scenario: French unchanged
- **WHEN** the fingerprint of the French prompts, criteria and default themes is computed
- **THEN** it equals the frozen value

#### Scenario: English contract
- **WHEN** the shipped English module is checked
- **THEN** it satisfies the contract, its fingerprint differs from the one before this change, and its promotional item names book excerpts, book announcements, webinars and paid courses

### Requirement: Discard articles below an optional relevance threshold
The system SHALL accept an optional `relevance_threshold` setting, an integer from 0 to 100, absent or 0 meaning no relevance filtering. Any other value SHALL be refused with the key's line number, without echoing the value, and with exit code 1. When the threshold is above 0, an article collected within the settings period whose relevance is below the threshold SHALL get the discard reason "pertinence {p}/100 sous le seuil {R}". An article collected before the period SHALL NOT get a relevance reason. A manual rescue SHALL remove that reason like any other, and a manual exclusion SHALL still show "écarté à la main". The reading list SHALL state the relevance part of the rule when the threshold is above 0. The language comparison of the shadow report SHALL NOT apply relevance.

Source: to be covered by `tests/watch_triage/test_watch_triage.py` (task 1.1)

#### Scenario: Recent article below the threshold
- **WHEN** the threshold is set and an article collected within the period has a lower relevance
- **THEN** its reasons include "pertinence {p}/100 sous le seuil {R}" and `apply` in filter mode moves it out

#### Scenario: Older article
- **WHEN** an article collected before the period has a relevance below the threshold
- **THEN** it has no relevance reason and stays in the library

#### Scenario: Rescue
- **WHEN** an article discarded by relevance is restored
- **THEN** it has no reason and stays in the library at the next `apply`

#### Scenario: Absent setting
- **WHEN** the setting is absent
- **THEN** reasons, reading list and moves are identical to before this change

#### Scenario: Out of range
- **WHEN** the setting is negative, above 100 or not an integer
- **THEN** loading exits with code 1, naming the key and its line, without the value

### Requirement: Keep the social handle in an untracked local settings layer
The system SHALL read an optional local triage settings file next to the tracked one, ignored by Git and never written by any command, and SHALL merge it over the tracked settings. The only accepted key SHALL be the social handle. An unknown key, a duplicated key or a non-mapping file SHALL be refused with the line number and exit code 1, without echoing any value. A missing local file SHALL mean no local value. A non-empty handle in the tracked file SHALL still be read when the local layer does not set one, with a warning, naming no value, that asks to move it. When both set the handle, the local one SHALL win and the same warning SHALL be printed. The settings file created at first launch SHALL hold no handle key.

Source: to be covered by `tests/watch_triage/test_watch_triage.py` and `tests/watch_triage/test_partages_semaine.py` (task 1.1)

#### Scenario: Local handle
- **WHEN** the local file sets the handle and the tracked file has none
- **THEN** the shares step uses the local handle

#### Scenario: No local file
- **WHEN** neither file sets a handle
- **THEN** the shares step is skipped with a message naming the local file

#### Scenario: Unknown local key
- **WHEN** the local file holds another key
- **THEN** loading exits with code 1, naming the key and its line

#### Scenario: Handle still tracked
- **WHEN** the tracked file holds a non-empty handle
- **THEN** it is used, a warning asks to move it to the local file, and the warning does not contain it

#### Scenario: Writing a setting
- **WHEN** a command updates a setting while a local file exists
- **THEN** only the tracked file changes, and the local file is byte-identical

## Open questions

None.
