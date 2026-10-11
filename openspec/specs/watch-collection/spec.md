# watch-collection

## Purpose

Collection of articles from followed sources into a local article folder, with a persistent state, a collection report, source discovery, a reading list and import of the user's own articles.

Source of truth: `tests/watch_lab/test_watch_lab.py`, `tools/watch_lab.py`.
## Requirements
### Requirement: Collect new articles from active sources
The system SHALL read the feed of every active source that has a feed, and write each new recent article as one Markdown file with front matter (title with source name, link, source key, author, publication date, completeness flag) and a body whose repeated leading title is removed. Articles older than the requested period, entries without a link, and entries rejected by the source's include/exclude keyword filter (matched against title and categories, exclude winning over include) SHALL be skipped.

Source: `tests/watch_lab/test_watch_lab.py` (Collecte, Fonctions.test_keep_filtre_titre_et_categories, test_article_markdown)

#### Scenario: Two new articles in a feed
- **WHEN** a feed holds two recent articles with full text and collection runs
- **THEN** two files are written, the output reports "2 nouveaux" for the source, and the page of each article is not fetched

#### Scenario: Keyword filter
- **WHEN** a source has an include and an exclude keyword and the feed has articles matching only include, matching both, matching neither, and matching include only through a category
- **THEN** only the articles that match include and not exclude (title or category) are written

#### Scenario: Old article and missing link
- **WHEN** the feed contains an article older than the period and an entry without a link
- **THEN** neither is written

### Requirement: Complete short feed entries from the article page
The system SHALL fetch the article page when the feed content is only an excerpt, and use the main body text of the page; links cited in the body (not menu or footer) SHALL be recorded. When the page cannot be fetched, the article SHALL be written as an excerpt, flagged incomplete, with a visible "excerpt only" notice, and counted as such in the output.

Source: `tests/watch_lab/test_watch_lab.py` (test_extrait_complete_par_la_page, test_extrait_seulement_quand_la_page_est_inaccessible)

#### Scenario: Excerpt completed
- **WHEN** a feed entry is short and its page is reachable
- **THEN** the file is flagged complete and only body links (not menu links) are stored

#### Scenario: Page unreachable
- **WHEN** a feed entry is short and its page returns an error
- **THEN** the file is flagged incomplete with an "Extrait seulement" notice and the output says "dont 1 extraits seulement"

### Requirement: Deduplicate articles
The system SHALL NOT write an article already collected: links are compared after cleaning (lowercase scheme and host, no leading www, no tracking parameters, no fragment, no trailing punctuation), and an article that comes back under another address with the same title and publication date SHALL NOT be duplicated. A title identical to an existing article but with another publication date SHALL be a different article. Two distinct articles with the same title on the same day SHALL both be kept under distinct file names.

Source: `tests/watch_lab/test_watch_lab.py` (test_deduplication, test_meme_titre_meme_jour_ne_s_ecrase_pas, test_meme_article_revenu_sous_une_autre_url_n_est_pas_duplique, test_clean_url)

#### Scenario: Re-run with a tracked link
- **WHEN** a second collection sees the same article with a tracking parameter plus one new article
- **THEN** only the new article is written, and a third run writes nothing

#### Scenario: Same title, same day
- **WHEN** two different articles share title and day
- **THEN** two files exist and the second has a numeric suffix

### Requirement: Isolate source failures and report them
The system SHALL continue with the remaining sources when one source fails (HTTP error, network error, unreadable feed, HTML page or redirect to a home page served instead of a feed). Each failure SHALL be shown in the output with its cause, recorded per source in the state with the last success date left unchanged, and counted in a report file that also gives the number of new articles. A valid empty feed SHALL be a success; a partially readable feed SHALL yield its readable entries. A source that recovers SHALL have its error cleared at the next run.

Source: `tests/watch_lab/test_watch_lab.py` (test_source_en_erreur_ne_bloque_pas_les_autres, test_flux_mal_forme, test_page_html_a_la_place_du_flux_est_une_erreur, test_redirection_vers_l_accueil_est_une_erreur, test_flux_vide_valide_reste_un_succes)

#### Scenario: One source down
- **WHEN** one source answers an HTTP error and another is healthy
- **THEN** the healthy source's article is written, the output shows "ERREUR" for the failing source, and the report says "1 sources en erreur"

#### Scenario: HTML served instead of a feed
- **WHEN** a feed address answers an HTML page
- **THEN** the source is reported as an error stating the response is not an RSS or Atom feed, and its last-success date stays empty

### Requirement: Refuse to collect without an active source
The system SHALL stop with an error when no source is active or when active sources have no feed.

Source: `tests/watch_lab/test_watch_lab.py` (test_aucune_source_active)

#### Scenario: Only inactive or feedless sources
- **WHEN** collection runs with sources that are all inactive or have no feed
- **THEN** the command exits with an error

### Requirement: Store a source's own collection separately
The system SHALL write articles of a source assigned to another collection (the user's own articles) into that collection's folder, not into the default one, and SHALL exclude them from the reading list.

Source: `tests/watch_lab/test_watch_lab.py` (test of the personal-collection separation, test_digest_exclut_vos_articles_et_respecte_la_periode)

#### Scenario: Personal collection
- **WHEN** a source is assigned to the personal collection and collected
- **THEN** its article is in the personal folder and the default folder stays empty

### Requirement: Derive candidate sources from shared links
The system SHALL read links from a text list (and from social-network and chat exports), ignore video and social-network links (counting the ignored ones), resolve shortened links, group links by source, and add each new source as inactive with its share count and discovered feed (or "no feed" when none). An existing source SHALL keep its settings (name, active flag, feed, filters) and only have its share count updated, without any feed search. The command SHALL fail when no link input is given. Feed discovery SHALL look for an advertised feed on an article page or the home page, then usual paths, and return nothing when none is found. Source keys SHALL be derived from the address (personal-author path on a blogging platform, host otherwise, subdomain-specific feeds for platform sub-sites).

Source: `tests/watch_lab/test_watch_lab.py` (Sources, Fonctions.test_source_of, test_liens_bluesky_linkedin_et_claude)

#### Scenario: New sources inactive
- **WHEN** a link list is read and sources are derived
- **THEN** every new source is inactive, "5 liens lus" and the ignored social-link count are printed, and a source without feed is marked as such

#### Scenario: Known source untouched
- **WHEN** a link list cites an already configured source
- **THEN** its name, active flag, feed and filters are unchanged and its share count increases

### Requirement: Preserve a free-text note on sources
The system SHALL keep the optional free-text `note` of each source (for example the reason for a deactivation) through every full rewrite of the sources file, including source derivation and suggestions, and SHALL document the field in the file header.

Source: `tests/watch_lab/test_watch_lab.py` (ChampNote)

#### Scenario: Round trip
- **WHEN** sources with a note are loaded and saved again
- **THEN** the reloaded sources equal the original ones

#### Scenario: Tracked sources file
- **WHEN** the tracked sources file is loaded and rewritten
- **THEN** the rewritten file is identical to the tracked one, notes included

### Requirement: Recover links of previously collected articles
The system SHALL provide a `links` command that records, once, the links cited by already collected articles whose links were not kept, report the number of unreachable pages, and leave unreachable articles to be retried at the next run. The former French-named command SHALL no longer be accepted.

Source: `tests/watch_lab/test_watch_lab.py` (test_liens_reprend_ce_qui_etait_inaccessible, SousCommandes)

#### Scenario: One page unreachable
- **WHEN** links are recovered and one of two pages is unreachable
- **THEN** the output reports "1 pages inaccessibles" and a second run retries only that article

### Requirement: Write the plain reading list
The system SHALL write a reading list of articles collected within the requested period, grouped by source, excluding the user's own collection and flagging excerpt-only articles.

Source: `tests/watch_lab/test_watch_lab.py` (test_digest_exclut_vos_articles_et_respecte_la_periode); `tools/watch_lab.py` (cmd_digest)

#### Scenario: Period boundary
- **WHEN** the only article was collected long before the period
- **THEN** the list header reports 0 articles

### Requirement: Import the user's own articles from a Medium export
The system SHALL import published posts from a Medium export archive into the chosen collection, the personal collection (its generic name defined in the code) when none is chosen, ignoring drafts and posts shorter than a minimum length (replies), without network access, and be idempotent (already present posts counted, none duplicated). The summary SHALL give imported, ignored drafts, too-short and already-present counts.

Source: `tests/watch_lab/test_watch_lab.py` (test_import_medium, CoucheLocale.test_import_medium_sans_collection_va_dans_la_collection_personnelle)

#### Scenario: Mixed archive
- **WHEN** an archive holds one post, one draft and one reply and is imported twice
- **THEN** the first run reports 1 imported, 1 draft, 1 too short; the second reports 1 already present and no new file

#### Scenario: Default collection
- **WHEN** an archive is imported without choosing a collection
- **THEN** the imported post is written in the folder of the personal collection

### Requirement: Read the user's own sources from a local, untracked file
The system SHALL read, in addition to the tracked sources file, an optional local sources file placed next to it, ignored by Git, with the same structure. A local entry whose key exists in the tracked file SHALL replace that entry at its place; any other local entry SHALL come after the tracked ones. Every command that reads sources SHALL see the merged list. No command SHALL write the local file, and a rewrite of the tracked file SHALL NOT write any value of a local entry: an entry defined only locally is not written, and a tracked entry whose key is also defined locally is written as it is in the tracked file. When the local file is absent or empty, the system SHALL use the tracked sources only, print nothing about it and keep its exit codes. When the local file cannot be read, is not valid YAML, has no list of sources, has an entry without key or two entries with the same key, the system SHALL stop with exit code 1 and a message naming the local file and, when known, the line or the entry rank, never a value of the file.

Source: `tests/watch_lab/test_watch_lab.py` (CoucheLocale)

#### Scenario: No local file
- **WHEN** no local sources file exists
- **THEN** the sources are those of the tracked file, nothing is printed about the local file, and collection behaves as before

#### Scenario: Personal source only in the local file
- **WHEN** the local file holds a source assigned to the personal collection and collection runs
- **THEN** that source's new articles are written in the personal collection folder

#### Scenario: Same key in both files
- **WHEN** a key is defined in both files
- **THEN** the local entry is used, and a rewrite of the tracked file keeps the tracked entry unchanged

#### Scenario: Rewrite of the tracked file
- **WHEN** source derivation or suggestions rewrite the tracked sources file
- **THEN** no entry defined only in the local file appears in it

#### Scenario: Invalid local file
- **WHEN** the local file has a syntax error, is not valid UTF-8, has no list of sources, has an entry without key, has a key written twice in one entry, or has two entries with the same key
- **THEN** the command stops with exit code 1 and a message naming the local file and, when known, the line or the entry ranks, without any value of the file; except for the duplicated-key case, the message adds that the file must be corrected or removed (the tracked sources are then read alone)

#### Scenario: Header
- **WHEN** the tracked sources file is written
- **THEN** its header mentions the local sources file

## Open questions

1. The ordering of articles within the reading list for sources with equal publication dates is not specified by tests.
2. The retention of the state database (old articles, links) is not described in tests or docs read.
