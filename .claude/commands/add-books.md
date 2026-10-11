---
description: Prepares the configuration of new books (classification, exclusions, catalogue) from file names, and prints the commands for you to run
argument-hint: "<book file names>"
model: sonnet
allowed-tools: Read(tools/mapping_lab.py), Read(tools/book_catalog.yaml), Read(docs/pmzilla/bibliotheque-lacunes.md), Read(docs/pmzilla/installation.md), Edit(tools/mapping_lab.py), Edit(tools/book_catalog.yaml), Edit(docs/pmzilla/bibliotheque-lacunes.md), Grep, Glob
---

Add these books to the library configuration: $ARGUMENTS

Language: this command is written in English, but serve the user in THEIR language (French by default when their request is in French).

You work from the FILE NAMES the user gives. You never open the books.

## Steps

1. **Pairs.** Look for a title that exists in both EPUB and PDF. The EPUB takes priority: the classification line (`MAPPING` of `tools/mapping_lab.py`) is that of the EPUB's Markdown, and the PDF is added to `EXCLUSIONS` with its reason.
2. **Domains.** For each book, PROPOSE its domains among `P` (produit), `D` (flow), `O` (organisation), `F` (facilitation), `T` (tech), with a one-line reason from the title. Wait for the user's validation before writing anything: you never decide the domains alone.
3. **Write, once validated.** The `MAPPING` line (`R + "<Folder>/<Name>.md": "<codes>"`, a book that must not be indexed gets `""` and a comment), the `EXCLUSIONS` line of a PDF duplicate, and the catalogue entry in `tools/book_catalog.yaml` (key = the `.md` file name; `titre`, `auteurs`, `annee` when known). When a value (author, title, year) can only be deduced from the file name, set `a_verifier: true`. Copy no text from a book.
4. **Pending items.** Read the section "À traiter au prochain ajout de livres" of `docs/pmzilla/bibliotheque-lacunes.md`. Apply the configuration part of each item (for example an `EXCLUSIONS` line) and give the commands it needs. Remove an item from that section ONLY after the user confirms that those commands ran.
5. **Print the commands, in this order, for the user's Terminal (run none)**, with the file names filled in (section 12 of `docs/pmzilla/installation.md` is the reference):
   1. conversion, dry run: `uv run tools/convert_books.py ~/Downloads/"Livres - Ressources" "Bibliotheque-MD/Livres - Ressources" --dry-run` (it must show "sans Markdown : 0" and "erreurs : 0" apart from the new books);
   2. conversion of each new book: `uv run tools/convert_books.py … --convert-book "<Folder>/<Name>.epub" --to "<Folder>/<Name>.md"`; read `_rapport_livre.txt`;
   3. sort by domain: `uv run tools/sort_by_domain.py Bibliotheque-MD Bibliotheque-Lab`;
   4. indexing, written directly into the database: `uv run ~/PMZilla-Lab/pmzilla_lab_library.py index Bibliotheque-Lab Watch-Lab`;
   5. BM25 probe: `uv run ~/PMZilla-Lab/pmzilla_lab_library.py probe` (expected: `BM25 index readable`).
6. **Say** that the daily watch run indexes directly into the database: a change to the book catalogue therefore reaches the database at the next daily run, even if the user does not run step 5.4 now.
7. **Documentation.** If a book fills a topic of the gaps document, say so and update that file; add the CHANGELOG line. Do not commit.

## Never

- Run the conversion (`convert_books.py`), the sort (`sort_by_domain.py`), the indexer (`pmzilla_lab_library.py` `index`, `rename-collection`, `probe`, `status`) or `knowledge_import.py` (import, verify, status).
- Read book contents or the content folders (`Bibliotheque-MD`, `Bibliotheque-Lab`, `Bibliotheque-Images`, `Watch-Lab`, `Watch-Excluded`); only the file names given by the user.
- Decide the domains without proposing them to the user.
- Launch anything reserved to the user: the real Jira tools (`history_jira.py`, `export_jira_api.py`), `flow_import.py`, `flow_compare.py`, the database scripts (`db.py`, `db_backup.sh`, `db_up.sh`), any calculation with the database as source (`--source db`), any database client (`psql`, `docker exec`), the branch-finishing script (`finish_branch.sh`), the owner bypass variable (`PMZILLA_SKIP_GREEN_CHECK`), the posture evaluation set.
- Write a person's, team's or project's name in any file.
