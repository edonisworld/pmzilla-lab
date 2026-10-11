# Installing PMZilla Lab

This file starts from a brand-new Mac and ends with a first session, a watch that runs every morning and an evaluation set that passes. Allow half a day, most of it waiting (converting and indexing the books, downloading the models). Each step ends with a check: do not move on to the next one until it passes. The last section gathers short checks to replay whenever you have a doubt.

All commands are typed in the **Terminal**, except those that start with `/`, which are typed in **Claude Code**. Claude Code's `!` prefix cannot write outside the workspace: anything that touches `~/PMZilla-Lab`, `~/.pmzilla-lab`, `~/Library` or `~/.Trash` is done in a regular Terminal.

The rest of the repository is described in the [README](../../README.md); the history of changes is in the [CHANGELOG](../../CHANGELOG.md).

## Contents

0. [Install script](#install-script) (a shortcut for sections 2, 3, 5.4, 8, 9 and 14)
1. [What you need before you start](#1-what-you-need-before-you-start)
2. [Install the tools](#2-install-the-tools)
3. [Get the repository and the scripts](#3-get-the-repository-and-the-scripts)
4. [Install BMAD](#4-install-bmad)
5. [Prepare the library](#5-prepare-the-library)
6. [Adapt PMZilla Lab to you](#6-adapt-pmzilla-lab-to-you)
7. [Bring the postures to life](#7-bring-the-postures-to-life)
8. [Install the watch](#8-install-the-watch)
9. [Install the evaluation set](#9-install-the-evaluation-set)
10. [Flow, dependencies, journal and dashboard](#10-flow-dependencies-journal-and-dashboard)
11. [First session](#11-first-session)
12. [Add a book](#12-add-a-book)
13. [Check the installation](#13-check-the-installation)
14. [Database (PostgreSQL in a container)](#14-database-postgresql-in-a-container)
15. [Repository audit (`/audit`)](#15-repository-audit-audit)
16. [Working on the repository](#16-working-on-the-repository)

---

## Install script

`tools/install_lab.sh` and `tools/install_lab.py` run, one step at a time, the installation steps that can be scripted. This section is the only place that describes the script; the sections below keep the explanations, the warnings and the checks, and point here for the commands the script runs. The script handles the **fresh mode**: a published edition with no personal data. Moving your own data from another machine (books, sanctums, database dumps) is not in this version.

**Start.** Clone the repository to the exact path `~/PMZilla-Lab/workspace` (section 3), then, from a regular Terminal:

```bash
cd ~/PMZilla-Lab/workspace
zsh tools/install_lab.sh --mode fresh --dry-run      # look first: runs only read-only checks, changes nothing
zsh tools/install_lab.sh --mode fresh                # then the real run
```

While the repository is private, this clone-then-run entry is the documented one. For the public edition only, the bootstrap can also be fetched and run in one go, which clones the repository itself (it needs `--repo`, the clone address; there is no default):

```bash
zsh -c "$(curl -fsSL <raw address of tools/install_lab.sh>)" -- --mode fresh --repo <clone address>
```

Do not pipe `curl` into `zsh`: the confirmations read your answers from the terminal.

**What it does.** The bootstrap (`install_lab.sh`) needs only macOS on Apple Silicon and Homebrew. It offers to install Git and `uv` through Homebrew, then hands over to the Python script (`install_lab.py`), which runs the steps in this order (`--list` prints them):

| Step | What it does | Calls |
|---|---|---|
| `prereqs` | `git`, `uv` and `node` (installed through Homebrew only if they do not answer on the `PATH`), Claude Code, a container runtime (Colima, only if none answers), Ollama and its two models (each pull confirmed, with its size) | `brew`, `ollama`, `colima` |
| `repo` | makes the scripts and hooks of `tools/` executable and clears their quarantine attribute | `xattr`, `chmod` |
| `hooks` | links the Git hooks | `tools/install_hooks.sh` |
| `links` | links the scripts in `~/PMZilla-Lab/` | `tools/install_links.sh` |
| `database` | starts the database and applies the migrations | `tools/db_up.sh`, `tools/db.py migrate` |
| `launchd` | renders and loads the two daily jobs (watch at 7:10, database backup at 7:45) | `launchctl` |
| `mcp` | registers the library server for Claude Code (with the file backend if the database is not ready) | `claude mcp` |
| `check` | read-only checks of section 13; prints, without running them, the full test runner, the wake-up check of the postures and the chart library checksum | |

**Rules it follows.**

- **Every change is confirmed.** Each action shows its command and asks `y/N`; only `y` or `yes` accepts, anything else (including Enter) declines. There is no "yes to all" option, and a real run needs a terminal.
- **`--dry-run`** runs only the read-only checks and prints each action as `dry run: would run …`. It asks nothing and writes nothing.
- **Safe to run again.** Each step first checks whether it is already done and then says `already done, skipped`. `--step <name>` runs one step, `--start-at <name>` runs that step and the next ones. A step whose prerequisite is missing is deferred, and says which.
- **No secret.** The script never reads, writes or asks for a password or a token, and never calls the Keychain tool. When the database password entry is missing, it stops that step and prints the command to run yourself (`security add-generic-password -s pmzilla-lab-db -a "$USER" -w`; the password is typed at the prompt).
- **It calls the existing scripts** (`install_hooks.sh`, `install_links.sh`, `db_up.sh`, `db.py migrate`) instead of repeating their logic. It never runs the backup, the restore test, the Jira tools, the conversion and indexing tools or the evaluation set.
- **If a runtime is missing.** No Docker or Colima that answers: the script offers to install Colima through Homebrew, one command at a time; if you decline, the database step is deferred, the library server is registered with the file backend and the backup job is not installed. No Ollama or a model declined: the watch job is not installed and indexing is deferred. The report at the end lists each of these. The script never starts the Docker Desktop application.

**Exit codes.** `0` everything is done or was already done; `1` a step failed (the run stops and names the step and the command); `2` usage error (unknown option, mode other than `fresh`, no terminal for a real run); `3` environment refused (not macOS on Apple Silicon, Homebrew absent, clone at another path); `4` incomplete (a step was declined, deferred or is waiting for a manual action).

**What stays manual.** The script prints this list at the end of every run:

- installing Homebrew (https://brew.sh);
- signing in to Claude Code in the browser, and GitHub authentication for a private clone;
- every Keychain entry: the database password and, once the migrations have run, one entry per application role (`uv run tools/db.py role-password <role>`, which then prints the command to run);
- the BMAD installer (section 4, only for updates);
- the first session of each posture (section 7);
- editing the local context and the triage themes and language (section 6);
- book conversion, sorting and indexing (section 5);
- choosing the watch sources and running the first collection (section 8);
- the posture evaluation baseline (section 9, about $3);
- the list of sensitive names (`Flux-Lab/noms-sensibles.txt`, outside Git);
- the Jira steps (section 10).

**Pinned versions.** Each script of `tools/` that declares dependencies ships with its lock file (`tools/<script>.py.lock`), so a fresh install runs the versions the tests were run with (section 16, "Script dependencies").

---

## 1. What you need before you start

- **An Apple Silicon Mac** (M1 or newer). Plan for **at least 32 GB of memory**: gemma4:26b, the pre-triage model, takes 18 GB on disk and uses a good share of memory while it runs. PMZilla Lab is developed on 48 GB.
- **Several tens of GB of free space**: the two local models (about 20 GB), the converted books and the index.
- **A Claude Pro, Max, Team or Enterprise subscription**: Claude Code is not included in the free plan.
- **Access to the PMZilla Lab GitHub repository** (private repository).
- **Your books as PDF or EPUB**, without DRM, in `~/Downloads/Livres - Ressources` (subfolders are accepted). EPUB is preferred when both exist; if it does not convert, the PDF of the same book replaces it and the conversion report says so. Other formats (MOBI, AZW3) are not read: see Calibre below.
- **Calibre** (optional): only to convert a MOBI or AZW3 into EPUB before step 5. No script in the repository uses it. Install the app from https://calibre-ebook.com; its command-line tool is not in the `PATH`: `/Applications/calibre.app/Contents/MacOS/ebook-convert livre.mobi livre.epub`.
- Optional, for the watch: an export of your Claude data (Settings, Privacy, Export data) if you have a SignalPM-type project where you paste article links; your Medium export if you publish.

## 2. Install the tools

```bash
# Homebrew, if missing: see https://brew.sh
brew install git uv node
curl -fsSL https://claude.ai/install.sh | bash      # Claude Code (official installer)
```

The install script (section above, step `prereqs`) runs these commands and the two model downloads below, each after a confirmation. `uv` runs the Python scripts and installs their dependencies by itself on first launch; `node` is needed for the BMAD installer (`npx`). The `python3` shipped with macOS is enough for `sort_by_domain.py`, which has no dependencies.

Next, install the Ollama app from https://ollama.com/download and open it once: it keeps running in the background.

Open a new Terminal window, then download the two local models:

```bash
ollama pull bge-m3          # search vectors (1.2 GB)
ollama pull gemma4:26b      # watch pre-triage, the bigger of the two (18 GB)
```

Run `claude` once and sign in with your Claude account in the browser, then quit with `/exit`.

**Check**: `claude --version`, `uv --version`, `node --version` and `ollama list` all respond, and `ollama list` shows `bge-m3` and `gemma4:26b`.

## 3. Get the repository and the scripts

```bash
mkdir -p ~/PMZilla-Lab
git clone https://github.com/<owner>/pmzilla-lab.git ~/PMZilla-Lab/workspace
cd ~/PMZilla-Lab/workspace
xattr -c tools/*.sh tools/hooks/*
chmod +x tools/*.sh tools/hooks/post-commit tools/hooks/pre-commit tools/hooks/commit-msg tools/hooks/pre-push
zsh tools/install_links.sh
```

(`<owner>` is the GitHub account or organization that hosts the repository.)

The `xattr`, `chmod` and `install_links.sh` lines above are the `repo` and `links` steps of the install script (run `zsh tools/install_lab.sh --mode fresh --step repo`, then `--step links`, or the whole script).

The folder must be named exactly `~/PMZilla-Lab/workspace`: the library server (book catalog), `flux_jira.py` and `watch.sh` look for the workspace there, and the Git hook only reacts in that folder.

**A single source for the scripts: `tools/`.** All scripts live in `tools/` (tracked by Git) and are run from there (`uv run tools/flux_jira.py …`). Some are also called by their path `~/PMZilla-Lab/<script>`: launchd runs `watch.sh`, the MCP server runs `pmzilla_lab_library.py`, the posture evaluation runs `posture_evals.py`. `install_links.sh` turns these paths into symbolic links to `tools/` (`convert_books.py`, `posture_evals.py`, `flux_jira.py`, `history_common.py`, `mapping_lab.py` (the `MAPPING` table, imported by `convert_books.py` and `sort_by_domain.py`), `pmzilla_lab_library.py`, `watch_triage.py`, `watch_lab.py`, `sort_by_domain.py` and `watch.sh`). So there is never a copy to redo after editing a script: the file in `tools/` is the only one. On a Mac that already has copies, the script first moves them to `~/PMZilla-Lab/copies-avant-liens-AAAA-MM-JJ-HHMMSS/` (it says whether one differs from `tools/`), then creates the links; run again, it does not touch a link that is already correct. `zsh tools/install_links.sh --verify` reports the state of each link without changing anything. The script checks itself with `zsh tests/installation/test_install_links.sh` (fake home folder, nothing real is touched).

**Check**: `zsh tools/install_links.sh --verify` answers "Tous les liens sont en place" (all links are in place), and `ls -l ~/PMZilla-Lab` shows an arrow `->` to `workspace/tools/…` for each of the ten scripts. The folders `Bibliotheque-MD`, `Bibliotheque-Lab`, `Watch-Lab`, `Watch-Excluded`, `Flux-Lab` and `Journal-Lab` exist in the workspace, each with its `.gitkeep` (`ls -a Flux-Lab` is enough to see it). Do not list the contents of the book and article folders with Claude Code: its `deny` rules forbid it.

## 4. Install BMAD

The repository already contains BMAD v6.12 and the agents. What is missing is BMAD's local configuration (`_bmad/custom/config.user.toml`: your name, your language), excluded from the repository by `_bmad/custom/.gitignore`. The installer creates it:

```bash
cd ~/PMZilla-Lab/workspace
npx bmad-method install
```

In its lists, tick with the **space bar** before confirming with Enter; keep the modules already present (`core`, `bmm` for the method, `bmb` for the Builder).

**Check**: `ls _bmad/custom/config.user.toml` responds, and `git status --short` shows no deleted agent file.

**Updating BMAD** (`npx bmad-method install` again, on a newer version). The installer only protects what is under `_bmad/`: files that are not in its manifest are restored, and a file it installed that you edited is replaced, with your copy saved next to it as `.bak`. It does **not** protect `.claude/skills/`: it rewrites those `SKILL.md` files without warning, so a text replacement made by hand in one of them disappears. Today this concerns one example file name in `.claude/skills/bmad-spec/SKILL.md` that the names hook (`pre-commit`) refuses in tracked files. The replacement is therefore replayed by a script, from rules kept in `.pmzilla/remplacements-bmad.tsv` (local, ignored by Git, because the text to replace is a name the hook forbids in tracked files; one rule per line: path, text to replace, replacement, separated by tabs). After the installer:

```bash
python3 tools/bmad_remplacements.py            # replays the replacements and lists the files it changed
python3 tools/bmad_remplacements.py --check    # writes nothing; exit code 1 if a replacement is still pending
git status --short                             # postures (.claude/skills/pmzilla-*) and _bmad/memory/ must not appear
bash tests/run_all.sh
```

Then commit with the BMAD version in the message: the `pre-commit` hook must pass. If it refuses a `SKILL.md` that the update brought back, add the rule for that line to `.pmzilla/remplacements-bmad.tsv` and run the script again. The script prints paths and counts, never the replaced texts.

**After a BMAD install or update, check the user name.** The installer writes your name into `_bmad/core/config.yaml`, `_bmad/bmm/config.yaml` and `_bmad/bmb/config.yaml`. Those three files are tracked: set `user_name: BMad` back in each before committing (`python3 tools/identifiants_personnels.py` and the `ConfigurationBmad` test catch it). Your real name stays in `_bmad/custom/config.user.toml`, outside Git like every personal override `_bmad/custom/*.user.toml` (`_bmad/custom/.gitignore`).

## 5. Prepare the library

1. **Convert the books to Markdown** (from 10 minutes to over an hour depending on the number of PDFs):
   ```bash
   cd ~/PMZilla-Lab/workspace
   uv run tools/convert_books.py ~/Downloads/"Livres - Ressources" "Bibliotheque-MD/Livres - Ressources"
   ```
   Since option A (2026-10-06), the normal conversion does not create Markdown: it finds the **existing** Markdown of each book (explicit `SOURCES` match, then file name, then `MAPPING`) and rewrites it in place, the old one remaining as `.md.avant-figures` (only once); it prefers the EPUB when the PDF has the same name and does not resume where it stopped (each run rewrites all the books that have a Markdown). A book with no existing Markdown is listed, not converted: from scratch, or for a new book, use `--convert-book "<book>" --to "<Folder>/<Name>.md"` (after adding the key to `MAPPING`). Before any run on the real library, run `--dry-run` (same arguments, nothing is written). The report `Bibliotheque-MD/Livres - Ressources/_rapport_conversion.txt` flags scanned PDFs (no text) and protected EPUBs: they will not be usable.

2. **Sort the books by domain.** Each book must have its line in `MAPPING`, in `tools/mapping_lab.py` (table shared by `sort_by_domain.py` and `convert_books.py`), with its domains (`P` product, `D` flow, `O` organisation, `F` facilitation, `T` tech; several letters allowed); a line set to `""` discards the book. A book missing from `MAPPING` is not sorted, hence not indexed. Then:
   ```bash
   python3 tools/sort_by_domain.py Bibliotheque-MD Bibliotheque-Lab
   touch Bibliotheque-Lab/.gitkeep
   ```
   The script reports the `MAPPING` books it cannot find ("Introuvables") and the books present but not classified ("Présents mais non classés"): complete `MAPPING` and run again until both lists are empty. The `MAPPING` keys are the relative paths of the `.md` files in `Bibliotheque-MD`, as the script prints them. Those in the repository follow the folder tree of the original library (`Agile & Scrum/`, `Books/`), which is no longer that of `~/Downloads/Livres - Ressources` (folders numbered `01` to `11`): books reconverted from that folder come out "not classified", and the keys are corrected from the printed list. The full procedure for a new book is section 12.

3. **Index** (Ollama running; 20 to 60 minutes for about a hundred books, interruptible with Ctrl+C, resumes where it stopped):
   ```bash
   uv run ~/PMZilla-Lab/pmzilla_lab_library.py index Bibliotheque-Lab Watch-Lab
   ```
   Always pass both folders, even if `Watch-Lab` is still empty: a file missing from both is removed from the index. The index is written to `~/.pmzilla-lab/library.sqlite`. Titles and authors come from `tools/book_catalog.yaml` (see section 12).

4. **Connect the library to Claude Code**, for all projects:
   ```bash
   claude mcp add --scope user --transport stdio pmzilla-library \
     -- /opt/homebrew/bin/uv run ~/PMZilla-Lab/pmzilla_lab_library.py serve
   ```
   The install script's `mcp` step does this with `uv` found on your `PATH` (so it also works when Homebrew is not under `/opt/homebrew`).

**Check**: `claude mcp get pmzilla-library` shows `Status: ✔ Connected`. In a session (`claude` from the workspace), `/mcp` shows the server with 7 tools (`search_library`, `read_passage`, `list_collections`, `list_books`, `search_cases`, `search_experiments`, `list_due_reviews`), and the request "List the library's collections" returns at least the five domains (`produit`, `flow`, `organisation`, `facilitation`, `tech`) with their number of books; `veille` and your personal collection (`<your-collection>`) are added once the watch is indexed.

The `deny` rules in `.claude/settings.json` are already in the repository: they forbid Claude Code from directly reading `Bibliotheque-MD`, `Bibliotheque-Lab`, `Watch-Lab/watch`, the personal-collection folder under `Watch-Lab`, `Watch-Excluded` and `Flux-Lab/exports`. It goes through the library, which only returns passages. Nothing to configure, but `.claude/settings.json` must stay as it is.

## 6. Adapt PMZilla Lab to you

The repository is tuned for its author. If you install it for yourself, adapt the following before the first session:

- **Your context**: `CLAUDE.md` no longer contains any personal context; it imports `.pmzilla/contexte.md`, a local file that Git ignores. Create it: `mkdir -p .pmzilla && cp tests/postures/contexte-neutre.md .pmzilla/contexte.md`, then replace its contents with your role, your organization (described by roles, never by colleagues' names) and, if you have one, your personal collection of articles. A missing file produces no Claude Code error: each posture's `wake.py` displays it at the top of its output ("FICHIER LOCAL ABSENT", local file missing), a sign of a typo or a file that was not created. Do not touch the citation, routing and privacy rules of `CLAUDE.md`.
- **`wake.py` dependency**: each `wake.py` declares `pyyaml` in its script header and receives it from `uv run` (step 2: `uv` is installed); run with `python3` without `pyyaml`, it still runs, prints "liste non calculée : le module … manque" (list not computed: module … missing) in place of the "hors bibliothèque" (out of library) list and says to go through `uv run`.
- **The agents' memory**: `_bmad/memory/` is local and ignored by Git: it is not in the repository and is created at the first session of each posture (step 7). After a change to a template, a reference or a script of a skill, `python3 tools/sanctum_refresh.py` updates `CREED.md`, `CAPABILITIES.md`, `references/` and `scripts/` of the sanctum without touching the lived content (`MEMORY.md`, `BOND.md`, `PERSONA.md`, `INDEX.md`, `sessions/`); `--dry-run` says what would change. The templates contain no absolute path: `wake.py` prints `Project root:` and `Sanctum:`, computed from its own location, and the refresh stops if a template ever contains one. Git no longer keeps it: back it up with `bash tools/sauvegarde_sanctum.sh`, which copies `_bmad/memory/` into `~/.pmzilla-lab/sauvegardes/bmad-memory-AAAA-MM-JJ` (one folder per day, never overwriting: the script stops if that day's folder exists; for a second backup the same day, `SANCTUM_DATE=AAAA-MM-JJ-label bash tools/sauvegarde_sanctum.sh`, a label in lowercase letters and digits, never deleted by the rotation), keeps the 6 most recent backups and prints the ones it deletes; it only prints paths and file counts. Run it after each important session, or at least every week; the 2026-10-07 backup (state before the move out of Git) is never deleted. **Do not touch `tests/postures/memoire/`**: it is the neutral, frozen memory that the evaluation set substitutes for the postures' lived memory (step 9).
- **`watch/tri.yaml`**: `themes` (your topics) and `language` (`fr` or `en`, the prompts that score the articles; absent: `fr`). **`watch/tri.local.yaml`** (to create, ignored by Git, never written by a script): one line `bluesky: <your handle>`, or nothing.
- **`watch/sources.yaml`**: your sources (step 8).
- **What concerns the author is optional**: the author's personal collection of published articles (compared with the books as positions), its rule in `CLAUDE.md`, the author's Medium source in `watch/sources.yaml` and the author's Bluesky account in `tri.yaml`. You can do without them, or adapt them to your use: import your own articles into a collection under your name (step 8), point the `CLAUDE.md` rule at it and enter your Bluesky account.
- **`tools/book_catalog.yaml` and `MAPPING`** describe the author's books. For another library, replace them with yours as you go through section 12; a book with no catalog entry comes out of the search with "auteur non indiqué" (author not given). The "hors bibliothèque" list that each posture prints when it wakes up is computed from this catalog: `tools/references_postures.yaml` lists the works that the rules cite, and `uv run tools/outside_library.py toutes` shows the result for your library.

## 7. Bring the postures to life

Each posture keeps its memory in `_bmad/memory/<agent>/`. It creates it at its very first session, through a guided ritual (`first-breath.md`) where it asks you a few questions. Do it one posture at a time, in Claude Code, from the workspace:

```text
/pmzilla-discovery-bmad
```

Let the ritual run to the end (allow `init-sanctum.py` when it asks), answer with roles and never with names, then `/clear` and move on to `/pmzilla-delivery-bmad`, `/pmzilla-scaling-bmad` and `/pmzilla-facilitation-bmad`. Critic has no memory, on purpose: nothing to do for it.

**Check**, in the Terminal: each posture must display `MODE: WAKING`, not `FIRST_BREATH`.

```bash
cd ~/PMZilla-Lab/workspace
for a in discovery delivery scaling facilitation; do echo "== $a"; uv run .claude/skills/pmzilla-$a-bmad/scripts/wake.py ~/PMZilla-Lab/workspace | head -2; done
```

The memories stay local (`_bmad/memory/` is ignored by Git): there is nothing to commit.

**Changing a posture's reference.** Each `references/*.md` sheet exists in the skill (`.claude/skills/pmzilla-<posture>-bmad/references/`), which the posture loads, and in its local sanctum (`_bmad/memory/pmzilla-<posture>-bmad/references/`), which the sanctum no longer keeps up to date by itself. You fix the skill, then `python3 tools/sanctum_refresh.py` copies the references, templates and scripts into the sanctum. `bash tests/run_all.sh references_postures` checks that a new sanctum reproduces the skill's references.

## 8. Install the watch

1. **Choose the sources.** Four ways, which can be combined:
   - from your Claude conversations (links pasted in a project like SignalPM): `uv run ~/PMZilla-Lab/watch_lab.py sources --claude-export conversations-000.zip projects-000.zip`;
   - from your Bluesky posts: `--bluesky <handle>`;
   - from your LinkedIn shares: `--linkedin Shares.csv` (the file from the LinkedIn export);
   - from a list of links, one per line: `--urls liens.txt`.

   The sources found go into `watch/sources.yaml` with `active: false`. Open the file and set to `active: true` the ones you want to follow.

2. **First collection** (fetches the recent articles of each feed):
   ```bash
   uv run ~/PMZilla-Lab/watch_lab.py collect
   ```
   The report `Watch-Lab/_rapport_collecte.txt` lists the sources in error. By default, articles older than 30 days are ignored; `--since-days N` changes that limit.

3. **Your articles** (optional, if you publish on Medium): `uv run ~/PMZilla-Lab/watch_lab.py import-medium medium-export.zip --source medium.com/@<your-user> --collection <your-collection> --author "<your name>"`. Without `--collection`, the articles go into the author's own collection; choose your own collection name and carry it over into the `CLAUDE.md` rule (step 6). Articles shorter than `--min-chars` characters are ignored (replies).

4. **The pre-triage reference** (optional): it learns what interests you from the articles already run through a project like SignalPM, and from the articles in your personal collection if there are any (`--without-own` excludes them). It requires a Claude export:
   ```bash
   uv run ~/PMZilla-Lab/watch_triage.py references --claude-export conversations-000.zip projects-000.zip
   ```
   Without an export, skip this step: the watch still collects and indexes, but the reading list is not sorted.

5. **First pre-triage, reading list and indexing** (about 12 seconds per article):
   ```bash
   uv run ~/PMZilla-Lab/watch_triage.py score
   uv run ~/PMZilla-Lab/watch_triage.py digest
   uv run ~/PMZilla-Lab/pmzilla_lab_library.py index Bibliotheque-Lab Watch-Lab
   ```
   Without the step 4 reference, `watch_triage.py digest` stops ("Pas de référence", no reference): replace it with `uv run ~/PMZilla-Lab/watch_lab.py digest` (`--days N` for the period), which writes the reading list without sorting it. The `mode: observation` setting in `watch/tri.yaml` is the starting one: nothing leaves the library until you have calibrated the filter (README, section "Watch").

6. **Automatic run every morning at 7:10.** `tools/com.pmzilla.watch.plist` is a template: it contains no real path, only `__HOME__`, which the `sed` line replaces with your home folder when it renders the file. It runs `~/PMZilla-Lab/watch.sh` (collection, pre-triage, reading list, indexing, dashboard) and writes its log to `~/Library/Logs/pmzilla-watch.log`.
   ```bash
   sed "s|__HOME__|$HOME|g" ~/PMZilla-Lab/workspace/tools/com.pmzilla.watch.plist > ~/Library/LaunchAgents/com.pmzilla.watch.plist
   xattr -c ~/Library/LaunchAgents/com.pmzilla.watch.plist ~/PMZilla-Lab/watch.sh
   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.pmzilla.watch.plist
   launchctl kickstart gui/$(id -u)/com.pmzilla.watch
   ```
   **If the task was installed before the rename** (label `com.pmzilla.veille`), unload the old label before loading the new one, and remove the old file once the new job runs (the old log `pmzilla-veille.log` stays readable by the dashboard until the new one exists):
   ```bash
   launchctl bootout gui/$(id -u)/com.pmzilla.veille
   rm ~/Library/LaunchAgents/com.pmzilla.veille.plist
   zsh ~/PMZilla-Lab/workspace/tools/install_links.sh      # links watch.sh, watch_lab.py, watch_triage.py; removes the dangling old links
   ```
   then run the four lines above (render, `xattr`, `bootstrap`, `kickstart`).

   The install script's `launchd` step renders, installs and loads this job (and the backup job of section 14) after a confirmation, and skips it when the installed file is identical and the job is loaded; it does not run `kickstart`.

   **Note (recent macOS).** The job can load by itself as soon as the plist is copied into `LaunchAgents`; `Bootstrap failed: 5` is then harmless. Check with `launchctl print gui/$(id -u)/com.pmzilla.watch`.

**Folders renamed (already installed watch).** Before the rename of lot 5a, the watch lived in `veille/` (repository), `Veille-Lab/` (with its `veille/` sub-folder and `_a-lire.md`) and `Veille-Ecartes/`; they are now `watch/`, `Watch-Lab/` (`watch/` sub-folder, `_to-read.md`) and `Watch-Excluded/`. The scripts refuse the old name and say which tool migrates it. To move everything once (nothing is deleted; the folders are moved):
```bash
cd ~/PMZilla-Lab/workspace
uv run tools/migrate_watch.py --dry-run      # 1. counts only: nothing is created, moved or written
uv run tools/migrate_watch.py                # 2. verified backup in ~/.pmzilla-lab/sauvegardes/watch-YYYY-MM-DD/, then the move
uv run tools/migrate_watch.py                # 3. rerun: it answers "Rien à faire" (nothing to do)
```
The script refuses to migrate if the backup is incomplete, stops if a target folder already holds data, rewrites the `tri.yaml` keys (`modele`, `a_lire`, `jours`, `seuil_substance` become `model`, `to_read`, `days`, `substance_threshold`, comments kept), adds the `Watch-...` rules to the `deny` rules (the old ones stay) and updates the `location` column of `~/.pmzilla-lab/tri.sqlite` (`veille` becomes `watch`, `ecartes` becomes `excluded`; `veille.sqlite` holds only bare file names, nothing to change). It does not touch the launchd job: replace it as shown above. Then rename the collection in the index (nothing is re-embedded) and commit the moved files:
```bash
uv run ~/PMZilla-Lab/pmzilla_lab_library.py rename-collection veille watch --dry-run
uv run ~/PMZilla-Lab/pmzilla_lab_library.py rename-collection veille watch
git add Watch-Lab/.gitkeep Watch-Excluded/.gitkeep watch/sources.yaml watch/tri.yaml
git add -u Veille-Lab Veille-Ecartes veille
```
From then on, `uv run ~/PMZilla-Lab/pmzilla_lab_library.py index Bibliotheque-Lab Watch-Lab` (the daily run does it).

**Check**: `launchctl list | grep com.pmzilla.watch` shows one line (the second number, `0`, is the exit code of the last run). `tail -20 ~/Library/Logs/pmzilla-watch.log` shows collection, pre-triage and indexing without errors (last line: `=== Veille terminée sans erreur ===`, watch finished with no error; otherwise `=== Veille terminée avec N étape(s) en échec : … ===`, watch finished with N failed step(s), exit code 1 and a macOS notification), and `ls -l Watch-Lab/_to-read.md` shows a modification at the launch time.

**Stale index (Ollama absent).** A run without Ollama is not a failure: pre-triage and indexing are postponed. But `watch.sh` records the date of each successful indexing in `~/.pmzilla-lab/derniere-indexation` and, if Ollama is absent and that date is more than 3 days old, sends a macOS notification (and writes it to the log), without changing the exit code. With no reference point (first time), it relies on the date of `~/.pmzilla-lab/library.sqlite`; with nothing known, it notifies. To change the threshold, add to the `.plist` (before `</dict>`): `<key>EnvironmentVariables</key><dict><key>PMZILLA_INDEXATION_MAX_JOURS</key><string>5</string></dict>`, then reload the task (`launchctl unload` then `load`). A value that is not an integer resets it to 3.

**Pre-triage settings of lot 5b (already installed watch).**

- **Your Bluesky handle moves to `watch/tri.local.yaml`**, ignored by Git and never written by a script: create the file with the single line `bluesky: <your handle>`, then empty the `bluesky` line of `watch/tri.yaml`. A handle still in `tri.yaml` is refused with a message that does not show it (`à déplacer dans tri.local.yaml`). Another key in `tri.local.yaml` is refused with its line number. The `shares` step without a handle says "pas d'identifiant Bluesky dans tri.local.yaml".
- **`language`** (`fr` or `en`, absent: `fr`) chooses the prompts that score every article: the French ones of `watch_triage.py` or the English module `tools/watch_prompts_en.py`. The themes always come from `themes`. With `en`, an English module that does not load stops `score` (`Prompts de la langue en inutilisables …`, exit code 1): the French prompts are never used instead.
- **`relevance_threshold`** (optional, integer from 0 to 100; absent or 0: none) sets aside the articles whose relevance is below it, with the reason `pertinence {p}/100 sous le seuil {R}`, **only for the articles collected within the period** `days`: relevance is a rank among all the scored articles and moves as the corpus grows, so an older article that was kept is never set aside later. `restore` still wins.
- **`thresholds`** now also prints a matrix (one row per relevance threshold, by steps of 10, one column per substance threshold, each cell "good articles lost/weak articles kept") and two proposals: the substance threshold alone (fewest good articles lost, then fewest weak ones kept, then the least strict) and the pair that agrees best with your opinions (then fewest good articles lost, then the lowest relevance, then the lowest substance), with the `restore` command of each good article the pair loses. `--save` writes both thresholds of the pair; without it, nothing is written. It reads relevance from the `pertinence` column of `_calibration.csv` and never rewrites the sheet: **do not rerun `calibration` before `thresholds`**, it rewrites the sheet with an empty opinion column.

**Shadow scoring in English (optional).** Lot 5b ended on 10 October with the shadow **disabled** in `watch/tri.yaml` (`enabled: false`); the grades already stored in `shadow_scores` are kept, and `shadow-report` still reads them. The author's filter keeps `language: fr`; the English prompts are those of the published edition (`language: en`). Switch the shadow on again only to measure a change of the English prompts: `shadow-backfill` then rescores every article whose prompts fingerprint changed, and `shadow-report` compares. To compare the French and the English pre-triage prompts on the same articles, switch on the shadow in `watch/tri.yaml`: change the line `enabled: false` of the `shadow:` block to
```yaml
shadow:
  enabled: true    # false (the default) switches it off
  language: en
```
From the next run, each article scored by the pre-triage is scored a second time with the English prompts and themes (`tools/watch_prompts_en.py`; phrase-by-phrase correspondence with the French ones in `docs/pmzilla/watch-prompts-en-correspondance.md`), by the same local model, and the result goes into the separate table `shadow_scores` of `~/.pmzilla-lab/tri.sqlite` (url, language, model, prompts fingerprint, grades, date). **These grades decide nothing**: the `filtre` mode, the thresholds, `_to-read.md` and the excluded articles are exactly the same with the shadow on or off (a test proves it). The log of the run ends with `Notation en ombre (en) : N notés, M échec(s), +X s` (the added time); if the English scoring fails for an article, the run goes on and the failures are counted. Only articles scored after you switch it on get an English grade. A misspelt key, a non-boolean `enabled` or a language other than `en` is refused with a message. To switch it off, set `enabled: false`: the grades already stored stay and are not used.

The shadow only scores articles collected after it is switched on, which is too few to decide lot 5b. **Once, before lot 5b**, catch up the articles already scored in French (about 190 articles with the local model: expect around an hour; run it in your Terminal, never during the morning watch run, which takes no lock):
```bash
uv run ~/PMZilla-Lab/watch_triage.py shadow-backfill            # --limit N scores N articles at most
```
It scores in English, with the same prompts, themes and model, the articles already scored in French (in the library or set aside) that have no shadow note or a note made with other prompts, and writes only to the shadow table: no French score, no threshold, not `_to-read.md`, no set-aside article changes. Articles with an opinion `g` or `e` in `_calibration.csv` come first, so an interruption already leaves the most useful ones. It shows `[n/N]` for each article and ends with a summary (scored, failures, skipped, duration). Interrupted or partly failed, rerun it: an article already scored with the current prompts is not scored again. It refuses, with a message, if the shadow is not enabled, if the prompts do not load or if Ollama does not answer.

To read the comparison (Terminal only, nothing is written to a tracked file):
```bash
uv run ~/PMZilla-Lab/watch_triage.py shadow-report            # --limit N lists N disagreements (20 by default, 0 for all)
```
It gives the number of articles scored in both languages, the agreement on keep or discard at the current threshold, the mean gap of the substance grade and the disagreement rate per criterion, the agreement of each language with your calibration opinions (`_calibration.csv`), your rescues (`restore`) and rejections (`exclude`), and the list of disagreements (title, source, French and English grades). Measurement of 10 October (lot 5b, iteration 2b of the English prompts): 123/192 agreement with the calibration opinions in both languages, 186/192 agreement between languages; then `thresholds --save` set substance 4 and relevance 50.

### Personal sources (`watch/sources.local.yaml`)

Your own published articles are collected from a source that belongs to you, not to the repository. Create `watch/sources.local.yaml` next to `watch/sources.yaml` (it is outside Git and no script rewrites it): a top-level `sources:` list with the same fields as the tracked file, and `collection: own-articles` on your own source. `watch_lab.py` reads the tracked list, then the local one: a local entry with the same `key` replaces the tracked one, a new key is added after them. An error in the local file stops the command with a message in French and exit code 1; fix the file or remove it (the tracked sources are then read alone). On a new machine without this file your own articles are simply not collected.

### One-time migration to the `own-articles` collection

The personal collection has one generic name, `own-articles` (`watch_paths.OWN_COLLECTION`), the same for every user. If your workspace still holds it under another name (`<FORMER>` below, which you type yourself), migrate once, with Claude Code closed and before the next daily run:

```bash
cd ~/PMZilla-Lab/workspace/Watch-Lab && mkdir -p own-articles && mv <FORMER>/*.md own-articles/
ls -A <FORMER>                                  # nothing, or .DS_Store only; move anything else by hand
rm -f <FORMER>/.DS_Store && rmdir <FORMER>
ls -d ~/PMZilla-Lab/workspace/Bibliotheque-Lab/<FORMER>   # "No such file or directory" expected; otherwise repeat the moves there
uv run ~/PMZilla-Lab/workspace/tools/knowledge_import.py status          # note C, the number of collections
uv run ~/PMZilla-Lab/pmzilla_lab_library.py rename-collection <FORMER> own-articles --dry-run
uv run ~/PMZilla-Lab/pmzilla_lab_library.py rename-collection <FORMER> own-articles   # then "Vectors recomputed: 0."
uv run ~/PMZilla-Lab/workspace/tools/knowledge_import.py import --dry-run
uv run ~/PMZilla-Lab/workspace/tools/knowledge_import.py import
uv run ~/PMZilla-Lab/workspace/tools/knowledge_import.py verify          # same C; if exit code 1: import --deep, then verify again
```

Then name `own-articles` in the "Collection personnelle" section of `.pmzilla/contexte.md`, and in `.claude/settings.json` replace the ten `deny` rules on `Watch-Lab/<FORMER>` (one `Read`, nine `Bash`) by the ten on `Watch-Lab/own-articles` (`Read(./Watch-Lab/own-articles/**)` and `cat`, `head`, `tail`, `less`, `more`, `grep`, `awk`, `sed`, `cp`). Check the JSON with `python3 -m json.tool .claude/settings.json > /dev/null`. Replay the evaluation set (section 9) afterwards: the search tool description and two files read by the model changed.

## 9. Install the evaluation set

```bash
cd ~/PMZilla-Lab/workspace
bash tools/install_hooks.sh      # links pre-commit, post-commit, commit-msg and pre-push (relative links, safe to run again) and checks them; the install script's `hooks` step runs it
uv run ~/PMZilla-Lab/posture_evals.py
```

The first run (ten cases, about $3 and 15 minutes, Ollama running) serves as a point of comparison. After that, the evaluation set and the README update are run **on demand**: the `post-commit` hook no longer triggers them by itself (decision of 2026-10-07: a full set costs about $3 on each relevant commit, and a `claude -p` session launched by the hook committed the README while another session was working on the repository). The script needs `claude` (installed in `~/.local/bin`), Ollama and `osascript` for the notification.

**Model choice.** `--model <model>` sets the model of the tested sessions and `--judge-model <model>` the model of the judge (both passed to `claude --model`; without `--model` the sessions use the usual model of Claude Code, without `--judge-model` the judge is Sonnet; the `spec-writer` agent is set to Opus in `.claude/agents/spec-writer.md`, and `pmzilla-critic` sets no model, so it inherits the model of the session that calls it). The report header says `modèles : sessions … · juge …`, the run record keeps both (`modele_sessions`, `modele_juge`) and the dashboard shows them in the history table. A run whose sessions use another model than the usual one is **non-validating** (`validant: false` in the record, a notice in the report, a flag in the dashboard): it is never the baseline of the regressions or of "instable répété", it is left out of the dashboard curve and it does not count for the acceptance rule. A judge model alone does not make a run non-validating. `--rejudge <run> --judge-model <model>` judges the saved traces again with another judge (no session; the session model and the status of the rejudged run are kept; `--model` is refused there). `--compare <run A> <run B>` lists the verdicts that differ between two runs (case, check, blocking or not, verdict of each), with no answer text and no justification, and calls no model. Judge default: Sonnet, since the calibration of 2026-10-09 (`--compare` of a run and its rejudge with the Sonnet judge: 0 different verdicts out of 55 checks, same traces). To calibrate another judge: rejudge the last complete run with `--judge-model <model>`, then compare it with the original run.

**Unstable cases and replays.** A case with a failing blocking check is replayed up to 2 times (`--retries N`, 0 to disable): if it passes every replay it is reported "instable (1 échec sur 3)" and counted as passed (the report says "instable répété" when the same case was already unstable in the previous complete pass); if a replay fails again it is a confirmed failure (a regression if the check passed in the previous pass) and the series stops at that replay. Beyond 3 failing cases (`--max-retried-cases`) nothing is replayed, and an indicator, a technical incident or a touched real sanctum never triggers a replay. The `BILAN` line and the report show the cost of the replays: with the defaults, a failing case adds at most two replays (about $0.15 to $0.70 each), and at most about $4 with three cases replayed; with no failing case the cost does not change. The hook (`PMZILLA_AFTER_COMMIT=evals`) keeps these defaults. The judge reads every message of the last exchange (marked `=== message i/n ===`), and the non-blocking indicator "Un seul message final" flags a final answer split in several messages; `uv run tools/final_messages_check.py [--list]` counts these sessions on the kept traces, with no model call.

- **Evaluation set, on demand**: `tools/evals_auto.sh` replays the ten cases on the committed state (the report stays in `_bmad-output/essais/`, outside Git), regenerates the dashboard and notifies the result. For a single case or the working state, `uv run ~/PMZilla-Lab/posture_evals.py [--cases ...]`.
- **README and installation, on demand**: `/update-readme` in a Claude Code session, or `tools/evals_auto.sh --readme` (evaluation set, then the same update without intervention, then push). The latter refuses to run if `README.md` or `docs/pmzilla/installation.md` have uncommitted changes: the session would commit them along with the rest.
- **After a commit, if you ask for it**: `PMZILLA_AFTER_COMMIT=evals git commit ...` runs the evaluation set alone in the background, `PMZILLA_AFTER_COMMIT=all git commit ...` runs the evaluation set and then the README, only if the commit touches `CLAUDE.md`, a posture, an agent, a command, `tests/postures/cas.yaml`, `tests/postures/vocabulaire.yaml`, the frozen memory or `tools/pmzilla_lab_library.py`. Log: `~/Library/Logs/pmzilla-essai.log`.
- **Commit without evaluation**: without `PMZILLA_AFTER_COMMIT`, the hook does nothing; `PMZILLA_NO_EVALS=1 git commit ...` overrides it even if the variable is set.
- **A commit requires a green run of the index, complete on `main`**: `bash tests/run_all.sh` (no filter, run after `git add`) records the fingerprint of the index (`git write-tree`) in `.git/pmzilla-run-all-ok` when everything passes. On a work branch, `bash tests/run_all.sh --staged` is enough: `tools/select_suites.py` reads the staged paths and picks the suites (a suite whose tests name the file, the suites inside the changed folder, the shell tests listed in the runner, and always the identifier scanner); documentation-only changes need nothing more. When a staged file is named by no suite, or when `CLAUDE.md`, `.claude/settings.json`, the runner, the hooks or the selector change, the selector requires the complete run and the option behaves exactly as a complete run. A green targeted run records the index fingerprint in `.git/pmzilla-run-targeted-ok` (erased at the start of each targeted run) and leaves the complete-run fingerprint alone. The `pre-commit` hook refuses a commit whose index matches neither fingerprint on a work branch ("lance d'abord bash tests/run_all.sh --staged"), and on `main` or a detached head it accepts only the complete one ("lance d'abord bash tests/run_all.sh"). The chain is therefore `git add … && bash tests/run_all.sh --staged && git commit …` on a branch, `git add … && bash tests/run_all.sh && git commit …` on `main`. Limit, accepted: a suite that exercises a file only through an import chain is not selected; this never reaches `main`, because of the next point. `PMZILLA_NO_EVALS` is reserved to `git commit`: the runner refuses to start when it is defined (exit code 2). Bypass, reserved to the owner (denied to the assistant in `.claude/settings.json`): `PMZILLA_SKIP_GREEN_CHECK=1 git commit …`. Tests: `sh tests/hooks/test_pre_commit_green.sh`, `python3 -m unittest discover -s tests/select_suites`.
- **`main` requires a complete green run of the pushed tree**: the `pre-push` hook, for a push that updates `main`, accepts when the complete-run fingerprint equals the tree of the pushed commit; otherwise, if the working tree is clean and `HEAD` is the pushed commit, it runs `bash tests/run_all.sh` itself and accepts only on success; in any other state it refuses ("main exige une exécution complète réussie de l'arbre poussé"). Other references are not checked. It never accepts a targeted fingerprint. Same owner bypass. Test: `sh tests/hooks/test_pre_push.sh`.
- **Frozen memory and context**: each run creates the sanctums in its copy (`init-sanctum.py`), puts in them the neutral memory from `tests/postures/memoire/` and the neutral context `tests/postures/contexte-neutre.md` (placed as `.pmzilla/contexte.md`), both tracked by Git, nothing to install: two runs can be compared, and your context is never used for the evaluation. `--real-memory` tests with your real sanctum and your real context. With `--language en`, the memory comes from `tests/postures/memoire/en/` and the context from `tests/postures/contexte-neutre.en.md`.
- **Cases that depend on your library**: a case whose `prerequis` field in `tests/postures/cas.yaml` is not satisfied by your index (a missing book, a collection that is too small, a topic supposed to be absent that is in it) is reported "non évaluable ici" (cannot be evaluated here) instead of failing.
- **If Ollama does not respond**, the evaluation is postponed with a notification: run `~/PMZilla-Lab/workspace/tools/evals_auto.sh` again.

**Check**: `ls -l .git/hooks/post-commit` shows a link to `../../tools/hooks/post-commit`, the report `_bmad-output/essais/essai-….md` shows no "Outils refusés" (tools refused) line, and all the postures announce their tag. The detail of the options and reports is in the README, section "Maintenance".

**Safety net on names**: the `pre-commit` hook reads `Flux-Lab/noms-sensibles.txt` (one team, project or domain name per line, outside Git) and refuses the commit if a staged file contains one. It prints the file and the line number, never the name. Case is ignored, except for names of 3 characters or fewer and capitalized acronyms, which are compared case-sensitively; all staged files are examined, whatever their extension, except binaries (null byte) and files larger than 1 MB, which are flagged without blocking. Without the list (or if it is empty), it warns "garde-fou des noms inactif" (name safety net inactive) without blocking. Manual test, without calling Claude: `sh tests/hooks/test_pre_commit.sh`. Check with `ls -l .git/hooks/pre-commit`, which shows a link to `../../tools/hooks/pre-commit`.

**Installing the hooks**: `bash tools/install_hooks.sh` creates the four relative links `.git/hooks/<hook> -> ../../tools/hooks/<hook>` (`pre-commit`, `post-commit`, `commit-msg`, `pre-push`), makes the sources executable and checks the result ("Tous les hooks sont en place" / all hooks are in place). Run again, it touches nothing that is already correct; a hook that is not the expected link is moved to `<hook>.avant-install`, never deleted. `bash tools/install_hooks.sh --verify` reports the state without changing anything. Test: `sh tests/installation/test_install_hooks.sh` (temporary repository).

**Safety net on personal identifiers in commit messages**: the `commit-msg` hook runs `tools/identifiants_personnels.py --fichier` on the message (comment lines starting with `#` ignored) and refuses the commit if it contains the author's user name or a personal path. It reports that the message contains an identifier, never the identifier nor the message text; if the scanner fails, the commit is refused with "the message could not be checked". Manual test: `sh tests/hooks/test_commit_msg.sh`. Installed by `bash tools/install_hooks.sh`.
## 10. Flow, dependencies, journal and dashboard

These tools need nothing beyond the previous steps: `uv` fetches their dependencies on first run.

- **Flow metrics**: the `Flux-Lab/` folder already exists (its content is excluded from Git, and exports cannot be read by Claude Code). `Flux-Lab/flux.yaml` is created on the first run of `uv run tools/flux_jira.py statuses Flux-Lab/exports/<fichier>.csv`, and you then complete it with the states of your workflow. The Jira export and calculation procedure is described further down, in "Flow metrics: procedure, options and reading". For an export that mixes several projects and several workflows, four settings are added, with no change for an export that does not have them:
  - **`Status Category` column**: if the export contains it, it decides what is "in progress" (In Progress) and "to do" (To Do); the `in_progress_states` and `todo_states` lists in `flux.yaml` are then used only for tickets without a category.
  - **`portfolio_types` and `excluded_projects`** in `flux.yaml` (the same as for the dependency map), for example `portfolio_types: [Epic, Initiative]` and `excluded_projects: [BUG]` with generic keys: tickets of these types and projects are left out of throughput, lead time, WIP and forecasts. The project is read from the `Key` column (`Issue key`), which must therefore be in the export for `excluded_projects`. The report states how many tickets were set aside, by type and by project.
  - **Several exports** passed together: `uv run tools/flux_jira.py compute Flux-Lab/exports/<exportA>.csv Flux-Lab/exports/<exportB>.csv --name produit`. They are merged by key if the `Key` column is present (the last file wins for a duplicated ticket); without `Key`, they are simply concatenated and duplicates are possible. Each export stays under Jira's limit of 10,000 tickets (see the dependency map below). If the report sets aside no Epic although the export contains some, `statuses` lists the types in the export and prints the "Écartés au calcul" (set aside at calculation) line: it says what `portfolio_types` recognized.
  - **"Comment lire ce rapport"** (How to read this report): each report ends, before "Limites" (Limits), with a fixed section that defines in short sentences the percentiles, lead time, age, active, waiting and dormant WIP, arrivals and departures, Little's law and the Monte Carlo forecast, with examples computed from the report's own figures. `/monthly-flow` points to it instead of redefining these terms.
  - **`--scope ABC,DEF`** (optional): keeps only the tickets of these projects (keys separated by commas, case-insensitive, or `tous` (all)), read from the key column, like `dependencies_jira.py --scope`. Without the option nothing changes: all tickets in the export are read, and `scope_projects` in `flux.yaml` is not consulted (it is used only for dependencies). The filter runs before the exclusions (`portfolio_types`, `excluded_projects`), the dormant tickets and the history. The report starts with "Périmètre : … (N tickets retenus sur M lus)" (Scope: … (N tickets kept out of M read)) and the JSON carries the `perimetre` key; only with the option. A requested project with no ticket is counted in the Terminal; if no ticket of the requested projects is found, the calculation stops. `compare` adds a comparability note when two reports of the same series do not have the same scope (headcounts, however, may vary).
  - **`--history [cache.json]`** (optional): adds the "Temps par segment" (time per segment) section from the state history collected by `history_jira.py` (see "State history"). The default cache is `Flux-Lab/historique/transitions.json`; the export must have a key column. The report gives, overall and per team, without ranking: the tickets that left each segment during the period (count, P50, P85, mean of cumulated time), the tickets still in a segment (count, age P50 and P85), the delivery lead time from the commitment point to resolution next to the one from creation, flow efficiency (the share of time in an active state, waiting states being those of `waiting_states`) and coverage, with a warning below 90%. Durations are differences of dates, in calendar days, initial state included, and the current state runs until the calculation date for an open ticket. A ticket's time is cumulated over all its visits to the segment. Without the option, the report is identical, and the added notions enter "Comment lire ce rapport" only with it.
  - **`segments`** and **`commitment_point`** in `flux.yaml` (optional): `segments` maps states to segments (state names are compared case-insensitively). Default values: `definition` (Definition, Definition - Ongoing, Definition - On Hold, Ready for Review (Definition), Analysis, Analysis - ongoing, Analysis - on hold, Ready for Enhancement Check), `ready` (Ready for Implementation), `implementation` (Implementation, Implementation - Ongoing, Implementation - On Hold, Analysis (Impl), Code Review (Impl), R&D Test (Impl)), `review_verification` (Ready for Review (Implementation), Review - Ongoing (Impl.), Review - On Hold (Impl.), Ready for Verification, Verification, Verification - Ongoing, Verification - On Hold) and `acceptance` (Ready for Acceptance, Documentation (Impl)). If you write `segments` in `flux.yaml`, it replaces the whole list. `commitment_point` (default `ready`) is the segment whose entry is the commitment point. `team_separator` (default `;`) separates the teams of a cell that contains several; team columns with the same name are added together. The per-team report assigns each ticket to the value of its first column, whole cell, and counts multi-team tickets separately. `uncounted_segments` (default `a_faire`: Open, Draft; `termine`: Closed, Resolved, Accepted & Released, Rejected) files the start and end states without computing any time for them, so that the list of states filed in no segment shows only the real omissions; like `segments`, writing it replaces the default list. States filed in no segment are listed in the report.
  - **Arrivals and departures**: the report counts, week by week, the tickets created (arrivals) next to throughput (departures), with the total of both and their difference, overall and per team, without ranking. Arrivals take the same types and the same exclusions as throughput; tickets created and then rejected count in arrivals, and never in departures. They depend on the export query.
  - **Batch closures**: with a key column and the time of day in the resolution date, the report counts, per project, the delivered tickets whose resolution falls in the same minute as that of at least 4 others of the same project (threshold of 5 tickets, adjustable), with their share of the project's throughput. Only the reasons listed in `batch_closure_resolutions` are tracked (`Done` by default; empty list: all reasons counted as delivered). This is a count only: these tickets stay in throughput, lead time and forecasts. Without a time of day in the date (date format without time), no group is possible and the report says so. `--batch-closure-resolutions "Done,Accepted & Released"` (or `tous` for all delivered reasons) replaces `batch_closure_resolutions` for one calculation, without touching `flux.yaml`. The section is titled "Fermetures groupées" in the report.
  - **Truncated first week**: when an export query in `flux.yaml` (`jql_export`, `jql_exports`) filters on `resolved >= -26w`, the window starts 26 weeks before the calculation date and the first week of the period is incomplete (items resolved before the window are missing). The "Arrivées et sorties" (Arrivals and departures) section says so: that week is to be excluded from comparisons. The calculation date serves as the export date.
  - **`waiting_states`** (optional) in `flux.yaml`: a list of states or patterns, for example `waiting_states: ["Ready for", "On Hold"]`. A state matches if it equals an entry, or starts or ends with it, case-insensitively ("Ready for" finds `Ready for Review`, "On Hold" finds `Implementation - On Hold`). Items in these states stay in the total WIP but are counted separately, as waiting queues: the report gives the active WIP, the waiting WIP and the waiting share, per team too, and a "Nature" column in the age per state. Without this setting, nothing changes. The setting describes a measure, it does not reclassify states: the `in_progress_states` and `todo_states` lists and the Jira status category keep deciding what is "in progress" and "to do".
  - **`--dormants`** (removed): the separate export of dormant tickets no longer exists; the option is refused with a message that points to `--dormant-from-history`.
  - **`--dormant-from-history`** (optional): infers the dormant tickets from the state history cache: unfinished, created at least 365 days ago, no state change for at least 365 days, based on the date of the last transition (or of creation if there is none). The cache is that of `--history` if given, otherwise `Flux-Lab/historique/transitions.json`. A ticket with no history in the cache is not counted as dormant (the Terminal and the report note give the number). The report then separates the active WIP, the waiting WIP (according to `waiting_states`) and the dormant WIP (a dormant ticket leaves the other two), with the share of each, overall and per team, and the dormant "to do" from the living "to do"; the age per state gains the "Dormants" and "Part dormante" (dormant share) columns. Little's law and the Monte Carlo forecast then apply to the non-dormant WIP (active and waiting); the result on the total WIP is given in a note, for comparison. A note in the report recalls the threshold (365 days) and the source (the state history).
  - **More than 10 teams** in the report: a note under the per-team table recalls that teams are not to be compared with one another (workflows, ticket sizes and types of work differ).
  - **Monthly follow-up**: each month, run `compute` again with the same `--name` on a new export (for example `--name produit`), then `/monthly-flow produit` in Claude Code. Without a name, the command reads the `default_series` series of `flux.yaml` (for example `default_series: produit`) and asks for the name if the key is absent. "Keep this diagnostic" writes into `_bmad-output/pmzilla/flux/`, a folder ignored by Git. For a series of more than 10 teams, the Scaling posture reads the overview and Delivery comments on only 3 teams, with no ranking or comparison between teams. The first series has no evolution file: the command says so and reads only the flow report.
  The tests, on synthetic exports: `uv run --with pyyaml --with numpy python -m unittest discover -s tests/flux_jira -v`.
- **Coaching journal**: the `Journal-Lab/` folder already exists; `Journal-Lab/journal.yaml` is created at the first session noted with `/journal add`. Harmless check: `uv run tools/journal_lab.py follow-ups` prints "aucune" (none) as long as the journal is empty.
- **Dashboard**: `uv run tools/dashboard.py --open` writes `~/PMZilla-Lab/tableau-de-bord.html` and opens it. It is then regenerated by `watch.sh` and by `evals_auto.sh`, without ever making them fail.

### `flux.yaml` settings

A single file, `Flux-Lab/flux.yaml` (outside Git), configures all the Jira scripts. `flux_jira.py` creates it on first run; the other scripts use their default values if it is missing. Each setting below is read by the code; an absent setting takes the default value.

| Setting | Read by | Default | Role |
|---|---|---|---|
| `jira_site`, `jira_email`, `jira_token_type` | `history_jira.py`, `export_jira_api.py` | required for the API | address `https://<site>.atlassian.net`, email of the token's account, token type (`scoped` or `classic`) |
| `jql_export` | `export_jira_api.py` | none | JQL query of the export (a single one) |
| `jql_exports` | `export_jira_api.py` | none | named queries (`nom: requête JQL`); `export` writes one file per query; takes precedence over `jql_export` |
| `export_team_field` | `export_jira_api.py` | none (no team column) | identifier of the team field (`customfield_NNNNN`) |
| `export_team_header` | `export_jira_api.py` | `Team` | header of the team columns written |
| `export_verification_field` | `export_jira_api.py` | none (no column) | identifier of the "Verification Required" field (`customfield_NNNNN`, to be found with `export_jira_api.py fields --search "Verification Required"`): one more column in the export, with no other use for now; the number of tickets filled in is displayed, never a value |
| `export_verification_header` | `export_jira_api.py` | `Verification Required` | header of this column |
| `export_timezone` | `export_jira_api.py` | `Europe/Paris` | time zone of the CSV dates |
| `export_points_field` | `export_jira_api.py` | none | identifier of the story points field (`customfield_NNNNN`), or a list tried in order (first non-empty value); without it, no "Story Points" column (see 14.1) |
| `flow_views_min_cell` | `flow_views.py` | `5` | masking threshold of the aggregated views of the `flow` schema; it can only raise it (see 14.1) |
| `date_format` | (removed) | | the export date format is fixed (`%d/%b/%Y %H:%M`); an old `date_format` or `format_date` key, and the French column names, are refused with the current name |
| `columns` | all | usual English and French names | possible names of each column (`key`, `type`, `status`, `category`, `created`, `resolved`, `resolution`, `category_changed`, `team`, `parent`); added names come before the default names |
| `in_progress_states`, `todo_states` | `flux_jira.py`, `dependencies_jira.py` | `In Progress`, `In Review`, `Testing`; `Open`, `To Do`, `Backlog` | classification of states; the `Status Category` column, if the export has it, decides first |
| `excluded_resolutions` | `flux_jira.py`, `dependencies_jira.py` | `Rejected`, `Won't Do`, `Duplicate`, `Cannot Reproduce`, `Obsolete` | closure reasons that are not deliveries |
| `portfolio_types` | `flux_jira.py`, `dependencies_jira.py`, `history_jira.py` | empty | portfolio-level types (`types_exclus` is the old name, refused) |
| `excluded_projects` | `flux_jira.py`, `dependencies_jira.py`, `history_jira.py` | empty | projects set aside (defects, support) |
| `scope_projects` | `dependencies_jira.py` only | empty (all) | projects studied; `flux_jira.py` does not read it (`--scope` option) |
| `waiting_states` | `flux_jira.py` | empty | states (or prefixes and suffixes) counted as waiting queues |
| `segments`, `uncounted_segments`, `commitment_point` | `flux_jira.py --history`, `history_jira.py check` | five segments (definition, ready, implementation, review and verification, acceptance); `todo` and `done` outside the calculation; `ready` | segments of the time per state (details above) |
| `batch_closure_threshold`, `batch_closure_resolutions` | `flux_jira.py` | `5`; `Done` | threshold (integer of at least 2) and resolution reasons of the "Fermetures groupées" section |
| `boards` | `flow_board.py` | none | series shown by the visual dashboard, with their dependency scopes and baselines (see "Visual flow dashboard") |
| `team_separator` | `flux_jira.py`, `history_jira.py` | `;` | separator of teams in a cell that contains several |
| `blocking_link_types`, `waiting_link_types` | `dependencies_jira.py` | `Blocks`, `Bloque`, `Blocage`, `Prerequisite`, `Prérequis`; `Depends`, `Dependance`, `Dépendance`, `Dependency` | link types counted as a dependency |
| `project_names` | `dependencies_jira.py` | empty | readable name per project key (`--by project`) |
| `default_series` | `/monthly-flow` command (read by Claude Code, not by a script) | none | series used when `/monthly-flow` is run without a name |

**Settings renamed.** The keys of `flux.yaml` have English names (the table above). The old French names are refused, with a message that gives the current name and the line. A key written twice in the same block, or one setting written under its old and its new name (for example `types_exclus` next to `portfolio_types`), is refused with the path of the key and the numbers of the two lines, never a value: keep one of the two lines. To rewrite your file once: `uv run tools/flux_jira.py config migrate --dry-run` lists the keys that would change (names only, never a value), then `uv run tools/flux_jira.py config migrate` rewrites `Flux-Lab/flux.yaml` keeping its comments and keeps the old file as `flux.yaml.avant-migration`. Each change is listed with its line number and the full path of the key as written in your file (for example `L13 : colonnes.debut -> category_changed`). If two keys of the same block would end up with the same name (for example `types_exclus`, the pre-rename name of `types_portefeuille`, written next to it, or a key written twice), the command writes nothing and lists the lines in conflict: keep one of them, then run it again. Run it yourself in the Terminal, not through Claude Code. The command-line options were renamed the same way (`--nom` is `--name`, `--perimetre` is `--scope`, and so on); the old options are refused, with a message that gives the current one.

### Flow metrics: procedure, options and reading

**What it is for.** To compute locally, from a Jira export, the throughput per week, the lead time, the WIP, the age of in-progress items (per state and per team), arrivals and departures, Monte Carlo forecasts and, with the state history, the time per segment; then to have them interpreted by the Delivery posture (action **DF**). Only aggregates are produced: no ticket, no title, no person. The script reads only the type, state, dates, closure reason, team and key of each ticket (the key is used to merge and link, in memory), and writes no key, title or description.

**Procedure.**

1. **Get the export.** `export_jira_api.py export` (see "Jira API export" and "Monthly procedure through the API"): the only route, a CSV in the Jira "visible fields" format written without titles, descriptions or people. An export stays under Jira's limit of 10,000 tickets; beyond that, use named queries in `jql_exports` (one file per query), passed together to the script.
2. **Put the file in `Flux-Lab/exports/`.** The folder is excluded from Git and unreadable by Claude Code (`deny` rule in `.claude/settings.json`).
3. **Check the export.** `uv run tools/flux_jira.py statuses Flux-Lab/exports/<fichier>.csv` prints the recognized columns, the period covered, then the states and types with their ticket counts.
4. **Classify the states in `Flux-Lab/flux.yaml`**: `in_progress_states` (from the commitment point on; a "ready to plan" state stays in `todo_states`), `todo_states` (everything before commitment) and `excluded_resolutions`. Resolved tickets are recognized by their resolution date. This classification is a reading convention, not the Jira category: a state that is "In Progress" in Jira can be filed under "to do" and then leaves the WIP. `statuses` flags unclassified states.
5. **Calculate.** `uv run tools/flux_jira.py compute Flux-Lab/exports/<fichier>.csv --name equipe-a` writes `Flux-Lab/rapports/flux-<nom>-AAAA-MM-JJ.md` (and `.json`; `AAAA-MM-JJ` is the date, YYYY-MM-DD). Also run a 10-week calculation (`--weeks 10 --name equipe-a-recent`): it gives a more cautious forecast than the default window.
6. **Have the report interpreted.** In Claude Code, `/pmzilla-delivery-bmad` then "DF à partir de `Flux-Lab/rapports/<rapport>.md`" (DF from the report), giving the scope, the decision at stake and the meaning of the states. The posture keeps its notes in memory, asks its context questions and passes the diagnostic to Critic. "Keep this diagnostic" saves it in `_bmad-output/pmzilla/`.
7. **Start again with a new export** to follow the evolution: at the end of `compute`, the script compares the new report with the previous one of the same `--name` and writes `Flux-Lab/rapports/evolution-<nom>-AAAA-MM-JJ.md` (and `.json`). Then `/monthly-flow <nom>` in Claude Code.

**Options of `compute`** (`uv run tools/flux_jira.py compute --help`). `--history`, `--dormant-from-history` and `--scope` are described above, in the bullets of "Flow metrics".

| Option | Effect |
|---|---|
| `--name NOM` | short name of the team or scope, used in the report name and for the comparison |
| `--weeks N` | complete weeks analyzed (26 by default) |
| `--target N` | number of items to finish for the "in how many weeks" forecast (by default, the WIP) |
| `--target-date AAAA-MM-JJ` | date for the "how many items by then" forecast |
| `--types Story,Bug` | ticket types kept, separated by commas |
| `--teams-only` | excludes tickets with no team (a separate flow, absent from the WIP) |
| `--language fr\|en` | language of the report and of the messages (French by default; the old `--langue` is refused). The other scripts of the flow (`compare`, `statuses`, `dependencies_jira.py`, `history_jira.py`, `export_jira_api.py`, `segment_sample.py`, `journal_lab.py`, `critic_mirror.py`, `dashboard.py`) have the same option |
| `--no-comparison` | does not compare with the previous report of the same name |
| `--points` | also writes `Flux-Lab/tableaux/points-<nom>-AAAA-MM-JJ.json`: one point per in-progress ticket (team, state, segment, age, nature), without key, for the dashboard's Aging WIP; outside Git, outside the reports (which stay aggregates) |

**Follow-up over time.** `uv run tools/flux_jira.py compare --name equipe-a` redoes the comparison on demand, without a new export; `--before AAAA-MM-JJ` and `--after AAAA-MM-JJ` choose the two reports (by default, the two most recent). The evolution file contains "Comparabilité" (Comparability: what prevents drawing conclusions: different period, types or scope, a report in an old format with a skipped section), "Ce qui a bougé" (What moved: throughput, lead time P85, WIP, Little's law, aging, batch closures, teams that change, each beyond a threshold set in the script), then the throughput detail. A gap under the threshold does not prove stability, and each signal is a question to put to the teams, not a conclusion. The reading by Claude Code (`/monthly-flow`, team series or product series) is described in `.claude/commands/monthly-flow.md`.

**The `Flux-Lab` folder** (in the workspace, content excluded from Git except an empty `.gitkeep`):

| Path | Content | Readable by Claude Code |
|---|---|---|
| `Flux-Lab/exports/` | CSV exports from Jira through the API (`api-…csv`) | no |
| `Flux-Lab/historique/` | state history cache | no |
| `Flux-Lab/equipes-assets.yaml` | table of object identifier to team label | no |
| `Flux-Lab/tableaux/` | Aging WIP points (`points-…json`), HTML dashboards, `anonymes.yaml` (mapping of anonymous names) | no |
| `Flux-Lab/noms-sensibles.txt` | names that the `pre-commit` hook refuses in a commit | no |
| `Flux-Lab/rapports/` | aggregate reports (`flux-…`, `evolution-…`, `dependances-…`, in `.md` and `.json`), with no ticket | yes |
| `Flux-Lab/flux.yaml` | settings | yes |

**What the flow report contains**: at the top, the scope (only with `--scope`); throughput per week and closure reasons; arrivals and departures, overall and per team; lead time, overall and per type; WIP per state (active, waiting, dormant when configured); the age of in-progress items per state and per threshold (30, 90, 180, 365 and 730 days), the queues before commitment; Little's law; the breakdown per team, with each team's weekly series and the note on multi-team tickets; with `--history`, the "Temps par segment" (segment exits, age in the segment, delivery lead time, flow efficiency, coverage); the Monte Carlo forecasts (10,000 simulations); a "Comment lire ce rapport" section that defines the terms; the limits.

**Limits** (repeated in each report):

- lead time starts at ticket creation, backlog included: it is not a cycle time;
- age starts at entry into the Jira "In Progress" category, which can include analysis and definition: it is not a development time;
- without `--history`, no time per state: the report does not say how long an item has waited in its current state;
- throughput counts closed tickets, not delivered value;
- forecasts assume that future throughput resembles that of the period and that items are of comparable size, and they depend on the window chosen;
- over a few weeks, a per-team throughput is a very small sample: do not present per-team figures as a ranking.

### Segment sample (`segment_sample.py`)

To look, in the state history, at what hides behind a time per segment (for example a P50 for "Revue et vérification" (Review and verification) in the "Temps par segment" section of the flow report). The script reuses the exports, the history cache, `flux.yaml` and the calculation functions of `flux_jira.py`: same tickets, same segment states, same period.

1. **Run**: `uv run tools/segment_sample.py Flux-Lab/exports/<exportA>.csv Flux-Lab/exports/<exportB>.csv --today AAAA-MM-JJ` (the exports of the calculation to reproduce, and the report date: the period depends on it). It reads the collected history (`history_jira.py collect`, see below) and writes nothing to disk.
2. **Check the header**: the number of tickets that left the segment and its P50 must match the flow report. If not, the scope differs (exports, date, `--scope`, `--types`): do not read the sample.
3. **Read**: the states that make up the segment; the longest ones (time cumulated over all visits); a random draw, with a fixed seed (`--seed`, 42 by default), among the tickets between P40 and P60; separately, the oldest ones still in the segment. Per ticket: key, project, days, visits, entry and exit of the longest visit, origin and destination state.
4. **Options**: `--by-state` adds the time per state (total, share of the segment, P50, P85), the sample detail and the batch exits of the longest ones; `--starts` adds the transitions from "Ready for Verification" to "Verification - Ongoing" per project (transitions, distinct days, share on the busiest 20% of days, concentration at equal active days against 1000 random draws over the working days, French public holidays removed (expected share, 95th percentile, "yes"/"no"), distinct active days observed against the draws (expected, 5th percentile, ratio, "yes"/"no" for fewer active days than chance), P50 of the wait), without any key, for projects with at least `--min-passes` transitions (20 by default); `--exclude-batch-closures` removes from the population the tickets that left the segment in a batch closure, with the rule of the "Fermetures groupées" section of `flux_jira.py` (same function: a delivered ticket resolved in the same minute as at least `batch_closure_threshold` - 1 others of the same project, 5 by default, among the resolutions of `batch_closure_resolutions`, "Done" by default; it needs the time in the resolution date): the output states at the top how many tickets and how many "Ready for Verification" to "Verification - Ongoing" transitions were discarded, and every section (population, time per state, transitions per project, active days against chance) is computed without them; without the option the output does not change; `--segment`, `--longest`, `--near-median`, `--oldest`, `--weeks`, `--scope`, `--types`, `--history` complete the set.

The output contains only keys, projects and states: no title and no person. Keys do not enter any file tracked by Git. The tests (`tests/segment_sample/`) run on a fake export and a fake cache.

### Dependency map

`tools/dependencies_jira.py` draws the dependencies between teams from Jira exports, on the same principle as `flux_jira.py`: ticket keys are used only to link tickets together, in memory, and are never written; the report (`Flux-Lab/rapports/dependances-<nom>-AAAA-MM-JJ.md`, and `.json`) contains only aggregates, readable by Claude Code. The script is run from `tools/`, without a copy in `~/PMZilla-Lab/`. The exports stay in `Flux-Lab/exports/`, unreadable by Claude Code. Project and team names appear only in `Flux-Lab` (outside Git); the examples below are generic.

1. **Export from Jira through the API, in two files.** Jira caps an export at 10,000 tickets: a file whose ticket count is a round number (a multiple of 1000, flagged by the script) was probably truncated, and the missing tickets would distort the map. Define two named queries in `jql_exports` of `flux.yaml` and run `uv run tools/export_jira_api.py export`, which writes one file per query, merged by key by the script:
   - **Query A**, the portfolio project (the one with the Epics) limited to open tickets, plus two cross-cutting projects: `(project = PORT AND resolution IS EMPTY) OR project in (TRANS1, TRANS2)`, where `PORT`, `TRANS1` and `TRANS2` are generic keys to replace with yours;
   - **Query B**, all the other projects of the product: `project in (ABC, DEF, GHI) AND (resolved >= -26w OR resolution IS EMPTY)`.
   If one of the two exceeds 10,000, move projects to the other or restrict it (open tickets only, or a shorter resolution window). In both cases, also take the projects that yours are linked to, otherwise the team on the other side of a link stays unknown. The export writes the key, the status category, the type, the status, the dates, the resolution, `Parent key` (to know whether an old Epic still has active children), the team and the typed link columns (`Inward issue link (Blocks)` and `Outward issue link (Blocks)`).
2. **Set the scope in `Flux-Lab/flux.yaml`**, the file of `flux_jira.py` (created at its first run; without it, the script takes its default values):
   - `scope_projects`: the projects studied, for example `[ABC, DEF]` (empty: all those in the exports). The other projects serve only to locate the team on the other side of a link: their internal dependencies and their lead time are not counted;
   - `excluded_projects`: the projects whose links are not dependencies between teams (defects, support, tests), counted separately, outside the matrix;
   - `portfolio_types`: the portfolio-level ticket types, for example `[Epic, Initiative]`. A link between one of these tickets and a ticket of another level is backlog decomposition: it leaves the map, counted separately. A link between two tickets of this level stays a dependency;
   - `blocking_link_types` and `waiting_link_types`: the link types counted as a dependency. For `blocking_link_types`, the outward direction reads "blocks" (by default `Blocks`, `Bloque`, `Prerequisite` and their variants); for `waiting_link_types`, it reads "depends on" (by default `Depends`, `Dependency` and their variants). The link label on a Jira ticket gives the direction: check it before trusting "who waits for whom";
   - `project_names`: a readable name per project key, for example `ABC: Domain A`, used when the report is aggregated by project.
3. **Diagnose the exports.** `uv run tools/dependencies_jira.py diagnose Flux-Lab/exports/<exportA>.csv Flux-Lab/exports/<exportB>.csv` prints the recognized columns, the link types and their count (ignored or counted), the share of links that leave the exports (above 30%, widen the query), the excluded projects, the decomposition links and the tickets with no team. Option: `--scope ABC,DEF` (or `tous`) replaces `scope_projects` of `flux.yaml` for this command. The round ticket count is tested file by file.
4. **Calculate.** `uv run tools/dependencies_jira.py compute Flux-Lab/exports/<exportA>.csv Flux-Lab/exports/<exportB>.csv --name perimetre` writes the report: team-by-team matrix (open dependencies, including between Epics, of unknown state, all), Mermaid graph, loops, current blockings (with the share of Epics and the "Même date d'entrée" (same entry date) column) and those older than a year, waits toward an item outside the export, lead time for the same type. A dependency toward a ticket absent from the exports is "à état inconnu" (of unknown state): it is never counted as open. A dependency between two Epics (types listed in `portfolio_types`, for example `[Epic, Initiative]`) measures portfolio sequencing, not a wait for work: its age is that of the Epic's life, and at product scale the map first describes this sequencing. The "Même date d'entrée" column flags, for a row of at least 3 items, those that entered in-progress on the same day, and the "Âges à vérifier" (ages to check) warning lists them: this is the probable sign of a batch status change (planning, migration), which overestimates the wait. Items with neither an entry date nor a creation date are ignored in this count. Options: `--by projet` aggregates by Jira project instead of team (a readable view at product scale; the file then carries `-projets` in its name), `--scope` as for `diagnose`, `--weeks 26` for the lead time period, `--keys` to display the keys of the blockings in the Terminal only, writing nothing.
5. **Check the old Epics.** The "Epics anciens : vivants ou abandonnés ?" (Old Epics: alive or abandoned?) section of the report classifies the Epics open for more than a year and caught in an open link: alive (a delivery child changed state or was delivered in the last 90 days), with inactive children, or with no delivery child. An RN Task (a portfolio-level child, for example) or a closure by rejection or cancellation does not count as a delivery, because it is often a batch cleanup. The classification sees only the tickets in the exports: for the Epics that are not alive, run `compute` again with `--keys`: the script prints in the Terminal (nothing is written) a Jira query `parent in (EPIC-1, EPIC-2, ...) ORDER BY updated DESC`. Paste it in Jira's advanced search: it lists all the children of these Epics, finished ones included, with their last update. You then know which are empty, entirely rejected, dormant or active. The count to share keeps neither titles nor keys.
6. **Have the report read.** In Claude Code, `/dependencies perimetre`: the Scaling posture opens with a verdict on what the map allows concluding, then reads the loaded pairs, the loops and the interaction modes (see the README, section "Dependency map (`dependencies_jira.py`)").

**Check**: `diagnose` prints "Mode : orienté" (Mode: directed) if the links are typed, "non orienté" (undirected) otherwise, and a "Tickets sans équipe" (tickets with no team) line. The report exists in `Flux-Lab/rapports/`.

### State history (collection)

`tools/history_jira.py` collects the history of the status field alone for each ticket (transition date, origin state, destination state), the first step of measuring time per state. The organization validated this measure over the whole product scope, provided it is aggregated by team and carries no individual data: the script discards the author and every other field as soon as it reads the response. The time-per-state calculation is then done with `flux_jira.py compute --history` ("Temps par segment" section of the report), and dormant tickets are inferred from the same cache with `--dormant-from-history` (see "Flow metrics").

1. **Create a token** in Atlassian (account management, API tokens). A "limited scope" token (scopes) is enough: it needs at least `read:jira-work`. An HTTP 403 on the first try signals a missing permission.
2. **Store it in the macOS Keychain**, under the service `pmzilla-jira`, **in this order** (the clipboard trap: if you copy the token before pasting the command, the clipboard holds the command instead of the token):
   1. **First paste the command in the Terminal, without pressing Enter**:
      ```bash
      security add-generic-password -U -a "$USER" -s pmzilla-jira -w "$(pbpaste | tr -d '\r\n ')"
      ```
      (`pbpaste` reads the clipboard; `tr` removes the line breaks and spaces that copying may add.)
   2. **Only then, copy the token** with Atlassian's "Copy" button: the clipboard now holds the token.
   3. **Then press Enter.**

   Never use `security`'s interactive prompt (`-w` without a value): it truncates the token to 128 characters. Do not pass the token as a plain argument either (it would stay in the shell history). **Check without displaying it**: the following command shows only the length and shape of the token, never the token (length of about 192 characters, starts with `ATATT`, ends with `=` followed by 8 characters):
   ```bash
   t=$(security find-generic-password -s pmzilla-jira -w); echo "longueur : ${#t}"; [[ $t == ATATT* ]] && echo "début ATATT : oui"; [[ $t =~ '=.{8}$' ]] && echo "fin = + 8 caractères : oui"; unset t
   ```
   (The command prints "longueur : …" (length), "début ATATT : oui" (starts with ATATT: yes) and "fin = + 8 caractères : oui" (ends with = + 8 characters: yes).) If one of the three checks is missing, start again (`-U` replaces the existing entry). The token is read only from the Keychain: it is never displayed, logged, written to a file or repeated in an error message. Once the command has run, copy some harmless text so as not to leave the token in the clipboard.
3. **Set `Flux-Lab/flux.yaml`**:
   - `jira_site`: `https://<site>.atlassian.net`;
   - `jira_email`: the email of the token's account;
   - `jira_token_type`: `scoped` (limited-scope token: calls go through `https://api.atlassian.com/ex/jira/<cloudId>`, the cloudId being read at `<site>/_edge/tenant_info`) or `classic`.
4. **Check the connection**: `uv run tools/history_jira.py test` prints only "connexion OK" (connection OK) or the HTTP code.
5. **Collect**: `uv run tools/history_jira.py collect Flux-Lab/exports/<export>.csv [<autres lots>.csv] [--team "<nom>"]`. The keys are read from the export, in memory. `--team` limits the collection to one team (name given only here, never displayed): do this first, to validate on one team before the whole scope. The `portfolio_types` types and the `excluded_projects` projects of `flux.yaml` are discarded, as in the flow reports. The script uses the bulk history retrieval API if the instance offers it, otherwise the ticket-by-ticket history; it waits with increasing delays, respects `Retry-After` on HTTP 429, and stops on HTTP 401 or 403.
6. **Read the output**: the number of tickets read, discarded, already in the cache, to query, processed, the number of status transitions and the errors per HTTP code. Never a key or a name.

**Check the cache**: `uv run tools/history_jira.py check Flux-Lab/exports/<export>.csv [--team "<nom>"]` does not contact Jira; it compares the last state in the history of each ticket in the cache with the Status column of the export (the export must have it) and prints only counts: consistent tickets, inconsistent, not comparable (no transition), transitions per ticket (0, 1, 2-4, 5-9, 10 and more), delivered tickets with no transition at all. For delivered tickets, the command also gives the origin state of the first known transition (a history truncated at the start shows as an origin state that is not the workflow's initial state), the transitions per ticket, the segments and the states traversed. `--key <clé>` prints the sequence of states of a single ticket with their dates, without author, to compare it with Jira's History tab (Terminal only). If the history looks incomplete, `collect … --refresh` queries all the retained tickets again, ignoring the cache.

The cache is `Flux-Lab/historique/transitions.json` (outside Git; `.claude/settings.json` forbids Claude Code from reading it; permissions 700 and 600). It is incremental: a new run queries again only the unfinished tickets or those absent from the cache. A ticket in error does not enter it and will be retried. The tests use a fake HTTP server, invented data and a fake token: `uv run --with pyyaml --with requests python -m unittest discover -s tests/history_jira -v`. The real calls (`test`, `collect`) are run by you in the Terminal, never by Claude Code: `.claude/settings.json` also forbids it from reading the Keychain (`security find-generic-password`, `security … pmzilla-jira`) and from running these two commands.

### Jira API export

`tools/export_jira_api.py` writes a CSV in the Jira "visible fields" export format from a JQL query. It is the only source of the CSV read by `flux_jira.py`, `dependencies_jira.py`, `history_jira.py`, `segment_sample.py` and the import into the database (the manual export from the Jira interface is no longer supported). It is a script separate from `history_jira.py` because it reads other fields (current state, dates, parent, links, team) than the state history alone; it reuses its access to Jira (Keychain token, retries). It asks Jira for no title, no description and no person.

1. **Set `Flux-Lab/flux.yaml`** (in addition to the collection settings): `jql_export` (the query) or `jql_exports` (named queries, `nom: requête JQL`, for example `produit-A` and `produit-B` for two batches under the 10,000-ticket limit; takes precedence over `jql_export`), `export_team_field` (the identifier of the "[G] Team/s" field, of the form `customfield_NNNNN`; without it, no team column) and, if needed, `export_team_header` (header of the team columns written, `Team` by default) and `export_timezone` (time zone of the CSV dates, `Europe/Paris` by default).
2. **Find the field identifier** if needed: `uv run tools/export_jira_api.py fields --search team` prints the identifier and name of the fields whose name contains the text (case-insensitive), never a value.
3. **Check the team field, once**: `uv run tools/export_jira_api.py diagnose` queries one page and says the shape of the team field's values (text, list, object and the names of its keys), never a value. If the API does not return a label (Assets object identifier, UUID), the script stops without writing anything and asks for the identifier -> label table `Flux-Lab/equipes-assets.yaml` (see step 4).
4. **Export**: `uv run tools/export_jira_api.py export [--query NOM] [--output <fichier.csv>]`. With `jql_export`, one file `Flux-Lab/exports/api-AAAA-MM-JJ.csv`; with `jql_exports`, without `--query`, all the queries, one file each (`Flux-Lab/exports/api-NOM-AAAA-MM-JJ.csv`), and `--query NOM` a single one (an unknown name stops the command and lists the available names; `--output` applies only to a single query). Permissions 600, same format, same team table and same time zone for each file. The output gives only numbers: tickets, pages, columns. Dates are written as `09/Nov/2017 08:49` ( converted to the time of the `export_timezone` setting).
   **If the API returns only an Assets object identifier** (the diagnostic says so): write by hand `Flux-Lab/equipes-assets.yaml`, with the key `equipes` mapping each identifier to the team label (`equipes: {"1": "Team A"}`, permissions 600; the file stays outside Git). `export` translates the identifiers through this table; an absent identifier becomes "(équipe inconnue)" (unknown team), and the Terminal then lists the unknown identifiers (identifiers only, never a label or a ticket key) with the message to complete `equipes-assets.yaml`: add them by hand, with the label shown in Jira. The old `teams-table` command (table built from a manual export) and `compare` (manual export against API) are removed and refused with a message; their `deny` rules in `.claude/settings.json` are kept.

The monthly procedure that chains these commands is described right after.

Tests, on a fake server and invented data: `uv run --with pyyaml --with requests python -m unittest discover -s tests/export_jira_api -v`. The real calls (`fields`, `diagnose`, `export`) are run by you in the Terminal, never by Claude Code: `.claude/settings.json` forbids it.

### Visual flow dashboard

`tools/flow_board.py` produces **a single HTML file**, for the Agile Leads who find Markdown reports hard to read: interactive charts, product view first and then a team selector, a "How to read" on each chart. The file is self-contained and works offline: the charting library (Apache ECharts), the CSS, the JavaScript and the data are embedded in it, with no network call or CDN. It is written in `Flux-Lab/tableaux/` (outside Git, unreadable by Claude Code) from the JSON files in `Flux-Lab/rapports/`. It is **in English by default** (read by English-speaking Agile Leads); the Markdown reports follow the `--language fr|en` option of their script (`flux_jira.py`, `dependencies_jira.py`; French by default, same file names in both languages), and PMZilla's readings stay in French until the commands are translated.

1. **Install the library, once**: `zsh tools/vendor/telecharger_echarts.sh` (version 5.6.0 by default; `zsh tools/vendor/telecharger_echarts.sh 5.6.0 <dossier>` for another folder). The script downloads the npm package, compares its SHA-512 integrity with the registry's, then writes into `tools/vendor/`: `echarts.min.js` (about 1 MB), `LICENSE-echarts` and `NOTICE-echarts` (Apache-2.0), `echarts.sha256` and `echarts.version`. Commit these files: the generator checks the fingerprint at each generation and refuses a modified file. This is the only network call; after that, none.
2. **Set the series** (optional) in `Flux-Lab/flux.yaml`:
   ```yaml
   boards:
     series:
       - name: <série>                  # the --name of flux_jira.py compute
         dependencies: <nom>            # the --name of dependencies_jira.py compute (per team), optional
         project_dependencies: <nom>    # same with --by project, optional
         baseline: "AAAA-MM-JJ"         # date of a pilot's reference report, optional
   ```
   Without this setting, all the series found in `Flux-Lab/rapports/` are displayed (series ending in `…-recent` are ignored). Series names stay in `Flux-Lab/`.
3. **Produce the Aging WIP points**: add `--points` to the flow `compute` (writes `Flux-Lab/tableaux/points-<série>-AAAA-MM-JJ.json`, one point per in-progress ticket, without key; the reports stay aggregates). The CFD, the time per segment, the delivery lead time and the efficiency require `--history`; the active, waiting and dormant breakdown requires `--dormant-from-history` (or `waiting_states` in `flux.yaml`). A view whose data is missing says so instead of being empty.
4. **Generate**: `uv run tools/flow_board.py` writes `Flux-Lab/tableaux/tableau-flux-AAAA-MM-JJ.html`. Options: `--language en|fr` (`en` by default; the French file carries `-fr`), `--anonymous` (shareable version, see below), `--output <fichier>`, `--open`. Without the library, the command stops and gives the download command.

**The eight views** (each with its "How to read", taken from the shared glossary `tools/flow_glossary.py`, in English and in French): arrivals and departures per week; cumulative flow diagram per segment; time per segment (P50 and P85); Aging WIP (one point per ticket, by state or by segment, with the P85 lead time); WIP breakdown and its evolution from one report to the next; delivery lead time and flow efficiency (with coverage); dependency map as an interactive graph, with its table and the loops; evolution since the pilot's baseline (table of gaps and curves, with the warning when the options of the two reports differ: scope, history, source of dormant tickets). Teams are always in alphabetical order, never ranked.

**Reading and printing.** Okabe-Ito palette colors, readable in light and dark themes (following the system); color never carries information alone: shapes (active ● , waiting ▲, dormant ◇), patterns, labels and values are added to it. The page address keeps the view (`#s=1&t=<équipe>&a=segment&th=dark`: series, team, Aging WIP mode, theme). "Print" prints in A4 landscape: charts at page size, "How to read" unfolded, light theme.

**Anonymous version.** `uv run tools/flow_board.py --anonymous` replaces team, project and series names with "Team A", "Project B", "Series 1" (in French "Équipe", "Projet", "Série") **before** writing anything to the file: no real name is in the page, nor in its data. The mapping is in `Flux-Lab/tableaux/anonymes.yaml` (permissions 600): letters drawn at random the first time, then stable from one month to the next; a new name receives the next free letter. Do not delete this file if an anonymous version has already been shared. Jira state names stay as they are: reread them before sharing.

**Tests** (invented data, temporary folder): `uv run --with pyyaml --with numpy --with requests python -m unittest discover -s tests/flow_board -v`. They run the page's JavaScript under Node in a fake DOM; once the library is installed, they also render each chart with the real ECharts (light, dark, French, English). `Flux-Lab/tableaux/` is forbidden to Claude Code (reading and common commands).

### Monthly procedure through the API

A **series** is a follow-up over time: a `--name` (and possibly a `--scope`), with its own reports `flux-<nom>-…`, `evolution-<nom>-…` and `dependances-<nom>-…`. You can follow several, for example a product-scale series (all teams) and a series for a pilot domain (a `--scope` of a few projects). Series, team and domain names stay in `Flux-Lab/` and in the ignored folders of `_bmad-output/`; this document gives only generic examples (`<série>`).

**Once** (see above): token in the Keychain, `jira_*` and `export_*` settings of `flux.yaml`, `jql_exports` (one query per batch under the 10,000-ticket limit, for example `produit-A` and `produit-B`), `export_jira_api.py diagnose`, the team table `Flux-Lab/equipes-assets.yaml` if the team field returns identifiers (written by hand; afterwards, completed when the export lists unknown identifiers).

**Each month**, all these commands are run by you in the Terminal from `~/PMZilla-Lab/workspace` (`<date>`: today's date, `AAAA-MM-JJ`):

1. **Export**: `uv run tools/export_jira_api.py export` writes `Flux-Lab/exports/api-produit-A-AAAA-MM-JJ.csv` and `api-produit-B-AAAA-MM-JJ.csv` (format `api-<query name>-AAAA-MM-JJ.csv`, one file per query of `jql_exports`, here named `produit-A` and `produit-B`). **If the output lists unknown team identifiers**, complete `Flux-Lab/equipes-assets.yaml` by hand, then run the export again.
2. **Collect the state history**: `uv run tools/history_jira.py collect Flux-Lab/exports/api-produit-A-AAAA-MM-JJ.csv Flux-Lab/exports/api-produit-B-AAAA-MM-JJ.csv` (several files in a single command: they are merged by key and feed a single cache, `Flux-Lab/historique/transitions.json`; incremental, finished tickets already in the cache are not queried again; `--team` for a single team).
3. **Calculate the flow, once per series**: `uv run tools/flux_jira.py compute Flux-Lab/exports/api-produit-A-AAAA-MM-JJ.csv Flux-Lab/exports/api-produit-B-AAAA-MM-JJ.csv --name <série> --scope <clés> --history --dormant-from-history --points` (`--points` writes the Aging WIP points of the dashboard). Without `--scope`, all the projects of the exports. The script compares with the previous report of the same series.
4. **Calculate the dependencies, once per series**: `uv run tools/dependencies_jira.py compute Flux-Lab/exports/api-produit-A-AAAA-MM-JJ.csv Flux-Lab/exports/api-produit-B-AAAA-MM-JJ.csv --name <série> --scope <clés>` (`--scope tous` for every project of the exports; `--by project` for the product view).
5. **Sample the segment, to check the report**: `uv run tools/segment_sample.py Flux-Lab/exports/api-produit-A-AAAA-MM-JJ.csv Flux-Lab/exports/api-produit-B-AAAA-MM-JJ.csv --today AAAA-MM-JJ --by-state --starts` (keys, projects and states only; see "Segment sample").
6. **Have Claude Code read it**: `/monthly-flow <série>` (flow, comparison and questions for the teams), then `/dependencies <série>` (dependency map). "Keep this diagnostic" writes the reading into `_bmad-output/pmzilla/flux/` or `dependances/` (folders ignored by Git).
7. **Generate the visual dashboard**: `uv run tools/flow_board.py --open` (full version, for you) and `uv run tools/flow_board.py --anonymous --open` (shareable version), see "Visual flow dashboard".
8. **Check from time to time**: `uv run tools/history_jira.py check Flux-Lab/exports/api-produit-A-AAAA-MM-JJ.csv Flux-Lab/exports/api-produit-B-AAAA-MM-JJ.csv` (cache consistent with the state of the tickets, history not truncated), on **both batches**: with a single batch, the tickets of the other are not checked.

## 11. First session

```bash
cd ~/PMZilla-Lab/workspace
claude
```

Ask a real question, for example "Our teams rarely meet their sprint commitments, and the usual answer is to estimate better." The answer must start with `[Posture : Delivery]`, ask context questions, cite at least one book (*Author, Title*, section) and flag as "hors bibliothèque" (out of library) whatever does not come from the library. The README, section "7. Starting a session", describes the ways of working (routing, calling a posture directly, round table, deliverables).

## 12. Add a book

The `/add-books` command (section 16) prepares the configuration steps below from the file names and prints the commands in order; the conversion, the sort, the indexing and the import stay yours.

Do this in a **regular Terminal**: Claude Code's `!` cannot write outside the workspace, and moving `Bibliotheque-Lab` (point 6) goes to `~/.Trash`. The `deny` rules also forbid Claude Code from reading `Bibliotheque-MD` and `Bibliotheque-Lab`: have it audit the original files, or the book once indexed, through `search_library`.

1. **Audit the batch before converting.** A file name often lies: several books in the library carried the content of another, and nineteen files had to be renamed according to their real content. For each file in the batch, open the title or copyright page (title, authors, edition, year) and compare it with `tools/book_catalog.yaml` and `MAPPING`: is it a book already present, another edition, a concise version or a summary, a translation, the same book in another format? Decide for each one: keep, discard or replace. In the last batch, 14 files out of 17 were already present or duplicates.

2. **Prefer EPUB to PDF.** EPUB keeps the chapters and headings; PDF produces a poorer extraction. **Rule: when a title exists as both EPUB and PDF, the EPUB takes priority**, whatever the file names; the PDF goes into `EXCLUSIONS` in `tools/mapping_lab.py` with the reason, and the `MAPPING` line stays that of the EPUB's Markdown. If both exist under the same name, `convert_books.py` ignores the PDF. If they have different names, it converts both: discard the one you do not want (point 4). A MOBI or AZW3 is ignored without a message: convert it to EPUB first with Calibre (see section 1).

3. **Drop and convert.**
   ```bash
   # drop the book in ~/Downloads/Livres - Ressources (or one of its subfolders), then add its key to MAPPING (step 4)
   cd ~/PMZilla-Lab/workspace
   uv run tools/convert_books.py ~/Downloads/"Livres - Ressources" "Bibliotheque-MD/Livres - Ressources" --convert-book "Folder/Book name.epub" --to "Books/Book name.md"
   ```
   The normal conversion (no option) does not convert a book that has no Markdown yet: it lists it. Read the `_rapport_livre.txt` report: a scanned PDF or a protected EPUB cannot be used. Step 4 (MAPPING) comes before the command, because `--to` must be a key of `MAPPING`.

   **Figures.** A converted book keeps its figures as text blocks (`<!-- figure id=… source=… page=… image="…" -->`, then "Légende : …" (Caption) and "Texte alternatif : …" (Alt text)) when they have a caption (EPUB: of any form; PDF: "Figure X.Y" only) or, for an EPUB, useful alt text (not empty, not a file name, not a generic word such as "image" or "logo", and not fewer than 4 words without a caption). The images of those figures only go into `Bibliotheque-Images/<book>/` (outside Git, unreadable by Claude Code; PDF: the page area rendered as PNG). Books already converted do not change until you ask:
   ```bash
   cd ~/PMZilla-Lab/workspace
   # 1. measure first, without converting anything (analysis only, nothing is written to the library or the index)
   uv run tools/convert_books.py --figure-statistics ~/Downloads/"Livres - Ressources" Bibliotheque-MD
   # 2. redo the chosen books (name, relative path, or @list.txt: one book per line); the existing Markdown is found by its file name anywhere in the output folder (even if the source folders were renamed) and rewritten in place, the old one stays as ".md.avant-figures"; when no Markdown carries the book's name (EPUB titled by ISBN, hand-renamed Markdown), the `MAPPING` table finds it (key with the book name without case or accents, or the Markdown's `source:` header); no match, several matches, a key pointing to a missing file or two books pointing to the same Markdown: stop before any conversion, all errors listed; the report states the route followed (name or MAPPING)
   uv run tools/convert_books.py ~/Downloads/"Livres - Ressources" "Bibliotheque-MD/Livres - Ressources" --redo-figures "Book name" "Another book"
   ```
   The first command writes `Bibliotheque-MD/_statistiques_figures.txt` and `~/PMZilla-Lab/figures-a-refaire.txt` (one source book per line that has at least one retained figure, relative path, number of figures as a comment at the end of the line; the list is passed as is to `--redo-figures "@…"`) (Claude Code may not read it): one table per book (columns visuals, captions, alt text, "Alt inut." (useless alt text), blocks that would be created), then, last and without any book title, the aggregate by format and the total: that is the part you can copy. The second writes `_rapport_figures.txt` (the full conversion report is not touched) and reminds you to rerun `sort_by_domain.py` and then the indexing.

   **Index the figures (a few books first).** Figure blocks only count for search once the book has been reconverted and then reindexed. Procedure for a pilot of five books (no other book changes; the Markdown of each book must exist under the same file name, e.g. `cfd.md` for `cfd.epub`, otherwise `--redo-figures` stops and says so):
   ```bash
   cd ~/PMZilla-Lab/workspace
   # 1. the list (outside the repository): one book per line, file name without extension or path relative to the books folder; # = comment
   cat > ~/PMZilla-Lab/pilote-figures.txt <<'EOF'
   # figures pilot
   Name of the first book
   Agile & Scrum/Name of the second book
   Third book
   Fourth book
   Fifth book
   EOF
   # 2. reconvert only these books (the old Markdown stays as ".md.avant-figures", the book's old images are replaced)
   uv run tools/convert_books.py ~/Downloads/"Livres - Ressources" "Bibliotheque-MD/Livres - Ressources" --redo-figures "@$HOME/PMZilla-Lab/pilote-figures.txt"
   # 3. read the report (Bibliotheque-MD/Livres - Ressources/_rapport_figures.txt: blocks and images per book), then copy into the domains
   python3 tools/sort_by_domain.py Bibliotheque-MD Bibliotheque-Lab
   # 4. precaution: copy the index, then reindex (only the five changed books are recomputed; the index migration is automatic and lossless)
   [ -e ~/.pmzilla-lab/library.sqlite.avant-figures ] || cp ~/.pmzilla-lab/library.sqlite ~/.pmzilla-lab/library.sqlite.avant-figures   # restore point from before the pilot: never overwritten
   uv run ~/PMZilla-Lab/pmzilla_lab_library.py index Bibliotheque-Lab Watch-Lab
   ```
   For each of the five books, the indexing output says "dont N figures, M légendes du texte de page retirées" (of which N figures, M captions removed from the page text); the other books are "unchanged". To test the search without going through Claude (Ollama running): `uv run --with numpy --with httpx --with pyyaml python -c "import sys; sys.path.insert(0, 'tools'); import pmzilla_lab_library as l; [print(h['book'], '|', h['ref'].get('label'), '| p.', h['ref'].get('page'), '|', h['ref'].get('image'), '|', h['text'][:70].replace(chr(10), ' / ')) for h in l.Library().search('cumulative flow diagram', None, 8, types=['figure'])]"`: each line gives the book, the label, the page and the image path, which you open with `open <path>` from the workspace. Then, after restarting the Claude Code session (the server reloads the new code), ask for example: "Search for figures on the cumulative flow diagram (`types ["figure"]`) and cite them". To roll back: put `library.sqlite.avant-figures` back, put the `.md.avant-figures` files back in place, and reindex.

   **Generalize to the books that have retained figures.** Each command on a single line, from `~/PMZilla-Lab/workspace`, in order:
   ```bash
   # 1. statistics: writes _statistiques_figures.txt and ~/PMZilla-Lab/figures-a-refaire.txt
   uv run tools/convert_books.py --figure-statistics ~/Downloads/"Livres - Ressources" Bibliotheque-MD
   # 2. dry run: source -> Markdown and route (name or MAPPING), all matching errors; nothing is converted or written
   uv run tools/convert_books.py ~/Downloads/"Livres - Ressources" "Bibliotheque-MD/Livres - Ressources" --redo-figures "@$HOME/PMZilla-Lab/figures-a-refaire.txt" --dry-run
   # 3. index backup, without overwriting an existing file (never library.sqlite.avant-figures)
   [ -e ~/.pmzilla-lab/library.sqlite.avant-generalisation ] || cp ~/.pmzilla-lab/library.sqlite ~/.pmzilla-lab/library.sqlite.avant-generalisation
   # 4. reconversion (the old Markdown stays as ".md.avant-figures")
   uv run tools/convert_books.py ~/Downloads/"Livres - Ressources" "Bibliotheque-MD/Livres - Ressources" --redo-figures "@$HOME/PMZilla-Lab/figures-a-refaire.txt"
   # 5. filing by domain
   uv run tools/sort_by_domain.py Bibliotheque-MD Bibliotheque-Lab
   # 6. reindexing of these books
   uv run ~/PMZilla-Lab/pmzilla_lab_library.py index Bibliotheque-Lab Watch-Lab --recompute "@$HOME/PMZilla-Lab/figures-a-refaire.txt"
   ```
   Only move on to the reconversion if the dry run reports no errors.

   **Books that neither the name nor `MAPPING` links to their Markdown.** `SOURCES` (`tools/mapping_lab.py`) gives an explicit source -> Markdown match; it takes precedence over the file name and `MAPPING`, and the "correspondance explicite" (explicit match) route is shown in the dry run and the report. A missing Markdown stops everything before conversion.

   **A book never converted** (no Markdown): first add its line to `MAPPING` (in an old folder, for example `Books/`, with its domains), then `--convert-book "<book>" --to "Books/<Name>.md"` converts this one book and writes its Markdown at that path without overwriting anything; then `sort_by_domain.py`, the catalog entry (from the copyright page) and the indexing.

   **Recomputing books whose Markdown has not changed** (for example after a change in the passage format, such as `ref.legende` and `ref.texte_alternatif`): the indexer skips a book whose content is unchanged; `--recompute` forces the recomputation of the designated books (name with or without extension, path, or `@list.txt`), the others stay "unchanged". An unknown or ambiguous book stops everything before the index is touched; the option makes no backup. A useful backup beforehand: `[ -e ~/.pmzilla-lab/library.sqlite.avant-ref ] || cp ~/.pmzilla-lab/library.sqlite ~/.pmzilla-lab/library.sqlite.avant-ref` (never `avant-figures`, which remains the restore point from before the pilot). Command line: `uv run ~/PMZilla-Lab/pmzilla_lab_library.py index Bibliotheque-Lab Watch-Lab --recompute "@$HOME/PMZilla-Lab/pilote-figures.txt"`.

4. **File it in `MAPPING`** (`tools/mapping_lab.py`): one line per `.md` file, with its domains (`P`, `D`, `O`, `F`, `T`). **Translations and dual formats are not indexed**: a line set to `""`, with a comment saying why ("French duplicate of …", "EPUB kept, PDF ignored"). A book indexed twice brings the same passages up twice and muddles the citations. Books discarded for another reason (off topic, concise version) also get `""` and a comment. The script checks all the codes before copying (an unknown code stops it, nothing is copied) and flags two books with the same file name without overwriting either: the second is not copied, so one of the two must be renamed.

5. **Fill in the catalog** (`tools/book_catalog.yaml`): one entry per indexed book, key = the `.md` file name, with `titre`, `auteurs` and `annee`. Fill it in **from the book's copyright page**, never from the file name or from memory: the author the postures cite is the one in this entry (citation rule in `CLAUDE.md`). `a_verifier: true` marks uncertain information.

6. **File and index.**
   ```bash
   mv Bibliotheque-Lab ~/.Trash/Bibliotheque-Lab-ancien   # filing adds files but never removes any
   python3 tools/sort_by_domain.py Bibliotheque-MD Bibliotheque-Lab
   touch Bibliotheque-Lab/.gitkeep
   uv run ~/PMZilla-Lab/pmzilla_lab_library.py index Bibliotheque-Lab Watch-Lab
   ```
   Emptying `Bibliotheque-Lab` before filing prevents a discarded book (a duplicate replaced by its EPUB version, for example) from staying indexed. The two lists of `sort_by_domain.py` ("Introuvables" (Not found), "Présents mais non classés" (Present but unclassified)) must be empty. Indexing is incremental: only new or modified books are reprocessed; always pass both folders.

7. **Check.**
   ```bash
   sqlite3 ~/.pmzilla-lab/library.sqlite "select count(*) from books where collections not like '%veille%' and collections not like '%watch%' and collections not like '%own-articles%'"
   ```
   The number must go up by the number of books added (110 today). Then search for a passage of the book with `search_library` in a session: the author returned must be the one in the catalog. (`own-articles` is the personal collection of published articles.)

8. **Keep it up to date.** If the book fills a topic listed in `docs/pmzilla/bibliotheque-lacunes.md`, update that file. Add the CHANGELOG line, then `/update-readme` aligns the README counts (number of books, domains). The postures only cite a book if it is in the library.

**A new book, in short (in this order).** The normal conversion never converts a book that has no Markdown (it lists it): a new book goes through `--convert-book`, which requires the Markdown path to already be a key of `MAPPING`.

1. **Drop the book** in `~/Downloads/Livres - Ressources` (or one of its subfolders), after the audit of step 1.
2. **Add it to `MAPPING` with its domain** (`tools/mapping_lab.py`): a line `R + "Books/<Book name>.md": "<domains>"` (`P` product, `D` flow, `O` organization, `F` facilitation, `T` tech; several letters possible). Also add its entry in `tools/book_catalog.yaml` (title, authors, year from the copyright page; `a_verifier: true` if some information is missing).
3. **Convert this one book** (nothing else is touched; a Markdown that already exists is never overwritten):
   ```bash
   uv run tools/convert_books.py ~/Downloads/"Livres - Ressources" "Bibliotheque-MD/Livres - Ressources" --convert-book "Folder/Book name.epub" --to "Books/Book name.md"
   ```
   Read `_rapport_livre.txt`: a scanned PDF or a protected EPUB cannot be used.
4. **File by domain** (copies, adds files, removes none):
   ```bash
   uv run tools/sort_by_domain.py Bibliotheque-MD Bibliotheque-Lab
   ```
   The "Introuvables" and "Présents mais non classés" lists must stay empty.
5. **Index** (only the new book is computed, the others stay "unchanged"):
   ```bash
   uv run ~/PMZilla-Lab/pmzilla_lab_library.py index Bibliotheque-Lab Watch-Lab
   ```

If the source and the Markdown have unrelated names (EPUB titled by ISBN, renamed Markdown), add a match to `SOURCES`; if a source is another edition of a book already indexed, add it to `EXCLUSIONS` with the reason (two files of `mapping_lab.py`). Before any run of the normal conversion, `--dry-run` (same arguments) must display "sans Markdown : 0" (without Markdown: 0) and "erreurs : 0" (errors: 0).

## 13. Check the installation

Sixteen short commands, to run from `~/PMZilla-Lab/workspace`. Each gives the expected result when everything is in place. The `check` step of the install script runs the read-only ones (`ollama list`, `claude mcp get`, the links and hooks verifications, `launchctl print` of the installed jobs, `docker compose ps`, `git status --short`) and prints the others without running them. The step fixes nothing: it only reports which one fails.

| Command | Expected result |
|---|---|
| `ollama list` | `bge-m3:latest` and `gemma4:26b` appear in the list |
| `claude mcp get pmzilla-library` | `Status: ✔ Connected`, with `Command: /opt/homebrew/bin/uv` and a path to `~/PMZilla-Lab/pmzilla_lab_library.py` |
| `sqlite3 ~/.pmzilla-lab/library.sqlite "select count(*) from books where collections not like '%veille%' and collections not like '%watch%' and collections not like '%own-articles%'"` | the number of books in your library (110 for the author's) |
| `for a in discovery delivery scaling facilitation; do uv run .claude/skills/pmzilla-$a-bmad/scripts/wake.py ~/PMZilla-Lab/workspace \| head -1; done` | four `MODE: WAKING` lines (`MODE: FIRST_BREATH`: the posture has never had its first session) |
| `(cd tools/vendor && shasum -a 256 -c echarts.sha256)` | `echarts.min.js: OK`: the dashboard library is installed and intact (otherwise: `zsh tools/vendor/telecharger_echarts.sh`) |
| `zsh tools/install_links.sh --verify` | "Tous les liens sont en place" (All links are in place): the scripts in `~/PMZilla-Lab/` are links to `tools/` |
| `launchctl list \| grep com.pmzilla.watch` | one line `-  0  com.pmzilla.watch`: the job is loaded, and its last run ended without error (nothing is displayed if it is not installed) |
| `bash tools/install_hooks.sh --verify` | "Tous les hooks sont en place" (all hooks are in place) |
| `ls -l .git/hooks/post-commit` | a link to `../../tools/hooks/post-commit` |
| `ls -l .git/hooks/pre-commit` | a link to `../../tools/hooks/pre-commit` |
| `ls -l .git/hooks/commit-msg` | a link to `../../tools/hooks/commit-msg` |
| `uv run tools/dashboard.py` | a line `Tableau de bord : …/PMZilla-Lab/tableau-de-bord.html` (Dashboard: …), no error |
| `bash tests/run_all.sh` | `TOTAL : N tests dans M suites · tous réussis` (TOTAL: N tests in M suites, all passed) and exit code 0: all the test suites pass on your machine (no network or paid calls; `bash tests/run_all.sh watch_lab` runs just one, `-v` shows everything) |
| `uv run tools/knowledge_import.py verify` | (only once the database is installed, step 14.3) compares counts (books, passages, figures, collections) and the content fingerprint of every book between the SQLite index and the `knowledge` copy: exit code 0 when they match, 1 and the names of the books that differ otherwise (`status` prints the counts of both sides) |
| `docker compose ps` | (only once the database is installed, step 14) the `db` service is `Up … (healthy)`, on `127.0.0.1:5432->5432/tcp` |
| `git status --short` | nothing about `Bibliotheque-MD`, `Bibliotheque-Lab`, `Bibliotheque-Images`, `Watch-Lab`, `Watch-Excluded`, `Flux-Lab` or `Journal-Lab`: their content is properly excluded from Git |

If something fails, the README, section "9. Maintenance", has a troubleshooting table.

---

## 14. Database (PostgreSQL in a container)

The database is a PostgreSQL 18 server with the pgvector and pg_search extensions, in a Docker container run by Colima. It has three schemas (`knowledge`, `cases`, `flow`) and listens on `127.0.0.1` only. The specs in `openspec/` are authoritative for behaviour; `application.md` explains why. Nothing in the rest of PMZilla Lab depends on it yet: you can skip this step until a later batch needs it.

> **Warning: `colima delete` erases the virtual machine AND the data of the database.** `colima stop` keeps them, and so do `bash tools/db_up.sh down` and `docker compose down`. Never run `docker compose down -v` or `colima delete` without a fresh backup (step 6 below).

1. **Install and start Colima** (free, MIT licence; Docker Desktop also works with the same `docker-compose.yml`):
   ```bash
   brew install colima docker docker-compose
   brew services start colima          # Colima restarts at login
   colima start --cpu 4 --memory 6     # leaves room for Ollama
   ```
   If Docker cannot find the Compose plugin, add `"cliPluginsExtraDirs": ["/opt/homebrew/lib/docker/cli-plugins"]` to `~/.docker/config.json`.
2. **Create the password entry in the macOS Keychain, once**, in a regular Terminal. The password is typed at the prompt, never as an argument (it would end up in the shell history):
   ```bash
   security add-generic-password -s pmzilla-lab-db -a "$USER" -w
   ```
   Choose a long random password. It is never written in a file of the repository. Fallback outside the Keychain: the `PMZILLA_LAB_DB_PASSWORD` environment variable (used only if the Keychain has no entry; never put it in a file tracked by Git).
3. **Start the database** (the install script's `database` step runs this and the migrations; if the Keychain entry of step 2 is missing, it stops there and prints the command of step 2):
   ```bash
   bash tools/db_up.sh
   ```
   The script reads the password in the Keychain, hands it to `docker compose up -d --wait` through the environment of that single command, and waits until the container is healthy. It never prints it. If the entry is missing, it says how to create it and stops. `bash tools/db_up.sh down` stops the database and keeps the data. The image is pinned (`paradedb/paradedb:0.26.0-pg18`, digest in a comment of `docker-compose.yml`); the data live in the named volume `pmzilla-lab_pgdata`, not in the repository. The container gets a 1 GB `/dev/shm` (`shm_size: 1gb` in `docker-compose.yml`; Docker's default is 64 MB, too small for the parallel build of the BM25 index of the migration `0005`, which asked for 366 MB). After a change of this value, `bash tools/db_up.sh` recreates the container (a few seconds without the database, so not around 7:10 and 7:45) and keeps the data volume; check with `docker compose exec -T db df -h /dev/shm`. To use another host port (for example if 5432 is taken), set `PMZILLA_LAB_DB_PORT` before the command: `PMZILLA_LAB_DB_PORT=5433 bash tools/db_up.sh`.
4. **Check**:
   ```bash
   docker compose ps       # service db: Up ... (healthy), 127.0.0.1:5432->5432/tcp
   docker compose exec -T db psql -U postgres -d pmzilla -c "select extname, extversion from pg_extension where extname in ('vector','pg_search')"
   ```
   Expected: `pg_search` 0.26.0 and `vector` 0.8.6.
5. **Connect from a script**: through `tools/db.py` only; never write the password in a command or a file.
6. **Back up** (one `pg_dump` per schema, run inside the container, no password needed):
   ```bash
   bash tools/db_backup.sh
   ```
   It writes `~/.pmzilla-lab/sauvegardes/db-AAAA-MM-JJ/` (one `.dump` file per schema, outside the repository), never overwrites a day's folder (a second run the same day says so and exits with code 0; for a second backup the same day, `DB_BACKUP_DATE=AAAA-MM-JJ-label`, lowercase letters and digits, never deleted by the rotation), keeps the 14 most recent folders (`DB_BACKUP_GARDER=N`, an integer of at least 1) and prints the ones it deletes. Folders are created `700` and dumps `600`. A schema that does not exist yet is reported and makes the script exit with code 1 after backing up the others; Docker not answering, a stopped container or a silent PostgreSQL give a clear message and code 2. Restore one schema with `docker compose exec -T db pg_restore -U postgres -d pmzilla --clean --if-exists < db-AAAA-MM-JJ/<schema>.dump`, after reading `pg_restore --help`.

7. **Daily automatic backup at 7:45.** `tools/com.pmzilla.db-backup.plist` is a template like the watch one: it contains no real path, only `__HOME__`. It runs `tools/db_backup.sh` every day at 7:45 (after the 7:10 watch collection); if the Mac was asleep, launchd runs it on wake. Log: `~/Library/Logs/pmzilla-db-backup.log`. Colima must be running (step 1: `brew services start colima` starts it at login) and the container up (`bash tools/db_up.sh`).

   **Password and Keychain.** The task never reads the Keychain and the plist holds no secret: `db_backup.sh` runs `pg_dump` inside the container through its local socket, and `docker compose ps` and `exec` do not need the password (a test checks it). Only `db_up.sh` reads the Keychain entry `pmzilla-lab-db`, and launchd does not run it. So there is nothing to authorise for the `gui` domain; if you add the password to the backup one day, check it from that domain first.

   ```bash
   sed "s|__HOME__|$HOME|g" ~/PMZilla-Lab/workspace/tools/com.pmzilla.db-backup.plist > ~/Library/LaunchAgents/com.pmzilla.db-backup.plist
   xattr -c ~/Library/LaunchAgents/com.pmzilla.db-backup.plist ~/PMZilla-Lab/workspace/tools/db_backup.sh
   launchctl print gui/$(id -u)/com.pmzilla.db-backup >/dev/null 2>&1 || launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.pmzilla.db-backup.plist
   ```
   The third line loads the task only if macOS has not already loaded it by itself when the file was copied (`Bootstrap failed: 5` is then harmless, as for the watch).

   **Check.** `launchctl print gui/$(id -u)/com.pmzilla.db-backup | grep -E "state|last exit code|hour|minute"` shows the schedule (`hour = 7`, `minute = 45`) and, after a run, `last exit code = 0`. To test now without waiting for 7:45: `launchctl kickstart gui/$(id -u)/com.pmzilla.db-backup`, then `tail -20 ~/Library/Logs/pmzilla-db-backup.log` (a line `Sauvegarde créée` per schema, or `La sauvegarde du jour existe déjà` on a second pass, then `Sauvegardes présentes : N`), and `ls -l ~/.pmzilla-lab/sauvegardes/` (folders `drwx------`; dumps `-rw-------`).

   **Failure.** Colima stopped, container stopped or PostgreSQL silent: the log says which, the exit code is 2 and a macOS notification names the cause (title "PMZilla db-backup"). A missing schema or an empty backup gives code 1 and a notification. Start Colima (`colima start --cpu 4 --memory 6`) or the database (`bash tools/db_up.sh`) then rerun the kickstart line. A run by hand never sends a notification (the plist sets `DB_BACKUP_NOTIFIER=1`).

   **Retention.** 14 daily folders are kept (a fortnight; at the previous default of 6, six days only). To change it, add `<key>DB_BACKUP_GARDER</key><string>30</string>` in the `EnvironmentVariables` dictionary of the installed plist, then reload: `launchctl bootout gui/$(id -u)/com.pmzilla.db-backup` and the `sed` + `bootstrap` lines above. A value that is not an integer of at least 1 is refused (code 2) and nothing is deleted.

   **Uninstall.**
   ```bash
   launchctl bootout gui/$(id -u)/com.pmzilla.db-backup
   rm ~/Library/LaunchAgents/com.pmzilla.db-backup.plist
   ```
   The backups and the log stay where they are. Claude Code is not allowed to run `launchctl` on this task nor the script: the commands above are yours to run in a Terminal.

### 14.1 Jira in the database (lot 6)

The `flow` schema holds the tickets, status transitions, links and teams read from the Jira API (never a title, a description or an author). The source is `export_jira_api.py` and the history cache of `history_jira.py`; no other CSV is imported. Claude Code never reads the tables (`.claude/settings.json` forbids `psql`, `docker exec`, the import, the comparison and every calculation on the database): it reads only the aggregated views, through `tools/flow_views.py`, and the reports. **You run everything below yourself.**

In this order:

1. **Back up, then migrate** (migration 0002 creates the tables, the four views and the role `pmzilla_flow_views`; it contains no data):
   ```bash
   bash tools/db_backup.sh
   uv run tools/db.py migrate
   ```
   The backup refuses to overwrite the one of the day: if today's folder already exists the script stops with a message; run it once per day, or move that folder first.
2. **Find the story points field, once.** `uv run tools/export_jira_api.py fields --search "Story point"` lists the identifiers; put the right one in `Flux-Lab/flux.yaml` as `export_points_field: customfield_NNNNN`, or a list (`export_points_field: [customfield_NNNNN, customfield_MMMMM]`) when several projects use different fields: the "Story Points" column takes the first non-empty value, in the order of the list, and `export` shows for each identifier how many tickets have it filled and how many have another points field filled with a different value (never a value). Without the setting the export has no "Story Points" column. The export always writes the `Updated` column (just after `Parent key`).
3. **Export again** with the API (`uv run tools/export_jira_api.py export`): an export made before this lot has no `Updated` column and the import refuses it (the message names the file and the column, no value).
4. **Import, dry run first** (counts only, nothing written):
   ```bash
   uv run tools/flow_import.py Flux-Lab/exports/<export>.csv [<other>.csv ...] --history --dry-run
   uv run tools/flow_import.py Flux-Lab/exports/<export>.csv [<other>.csv ...] --history
   uv run tools/flow_import.py Flux-Lab/exports/<export>.csv [<other>.csv ...] --history   # second run: 0 updated, 0 added
   ```
   With `--history`, every ticket that has an entry in the cache (with or without a transition) is marked "with history" in the base (`has_history`, migration 0003: run `uv run tools/db.py migrate` once after updating, then repeat the import with `--history`; the output ends with the number of tickets newly marked). Without that mark, a report computed from the base would count the coverage and the dormant tickets differently from the cache.
   One transaction; a row is written only if a field differs and it is not older than the one in the base; a ticket absent from a new export is kept; the output is counts only.
5. **Compute from both sources and compare**:
   ```bash
   uv run tools/flux_jira.py compute <export>.csv... --name csv-test
   uv run tools/flux_jira.py compute --source db --name db-test
   uv run tools/flow_compare.py data <export>.csv... --history
   uv run tools/flow_compare.py reports Flux-Lab/rapports/<report csv-test>.md Flux-Lab/rapports/<report db-test>.md
   uv run tools/dependencies_jira.py compute <export>.csv... && uv run tools/dependencies_jira.py compute --source db
   ```
   The criterion for the end of the lot: `flow_compare.py` prints "Aucun écart" (exit code 0) and the two reports have 0 differing lines. The CSV route stays the default; `--source db` is opt-in. The comparison prints counts only (no ticket key, no value, no team name).
6. **Let Claude Code read the aggregated views**: set the password of the limited role and put it in the Keychain (hidden prompts; the password is never written in a file or a command line):
   ```bash
   security add-generic-password -U -s pmzilla-lab-db-pmzilla_flow_views -a "$USER" -w "$(openssl rand -hex 24)"
   security find-generic-password -s pmzilla-lab-db-pmzilla_flow_views -a "$USER" -w | pbcopy && uv run tools/db.py role-password pmzilla_flow_views
   pbcopy < /dev/null
   uv run tools/flow_views.py list
   ```
   `role-password` asks for the password twice (hidden prompt): paste the generated one (Cmd+V) at both prompts, then empty the clipboard (third line) so the password does not stay in it. Generating it in the Keychain first avoids typing a weak password and the clipboard trap of copying a password you then overwrite or paste elsewhere.
   `flow_views.py show <view>` masks every cell under 5 tickets ("<5"); `flow_views_min_cell` in `flux.yaml` (or `--min-cell`) raises the threshold, never lowers it. The role `pmzilla_flow_views` can read only the four views, and its password is not the superuser's.

Tests (synthetic data, a throwaway database): `uv run --with "psycopg[binary]" --with pyyaml --with numpy python -m unittest discover -s tests/db`, then `tests/flow_import`, `tests/flow_store`, `tests/flow_views`, `tests/flow_compare` and `tests/script_dependencies` (each script runs with `uv run --isolated tools/<script>.py --help` and no `--with`: every dependency, indirect ones included, is declared in its `# /// script` block); they need `PMZILLA_LAB_DB_PASSWORD` and a database reachable at the default address (`tests/flow_store` and `tests/flow_compare`: a throwaway instance on another port, see 14.5), and are skipped otherwise. **Limit**: a `deny` rule stops Claude Code's commands, not a Python one-liner that would open the database; the limited role and the `CLAUDE.md` rule are the structural protection (see `application.md`, risks).

### 14.2 Restore the database, and test the restore every quarter

A backup that has never been restored is a hope, not a backup. Two procedures: the real restore after a loss (a), and the restore test, done once a quarter (b). Both rely on how `db_backup.sh` works: one `pg_dump` per schema (`knowledge`, `cases`, `flow`), so a backup holds **neither the roles, nor the extensions, nor `public.schema_migrations`**. A new database therefore gets its migrations first, then the schemas are restored into it.

**(a) Restore for real after a loss** (volume erased, `colima delete`, damaged disk). You run everything yourself, in a regular Terminal.

1. **Stop the database**, and copy the backup folder you are going to use somewhere safe (it is the only copy of the data):
   ```bash
   bash tools/db_up.sh down
   cp -R ~/.pmzilla-lab/sauvegardes/db-AAAA-MM-JJ ~/db-AAAA-MM-JJ-copy
   ```
2. **Only if the volume still exists but is damaged**, remove it (this erases what is left of the data; after `colima delete` the volume is already gone and this step is skipped):
   ```bash
   docker volume rm pmzilla-lab_pgdata
   ```
3. **Recreate the container** (the Keychain entry of step 2 above must exist; it sets the superuser password of the new volume):
   ```bash
   bash tools/db_up.sh
   ```
4. **Apply the migrations**: they create the roles, the extensions, the three schemas and `public.schema_migrations`.
   ```bash
   uv run tools/db.py migrate
   ```
5. **Restore the three schemas** from the latest backup (read `pg_restore --help` first if in doubt):
   ```bash
   for s in knowledge cases flow; do
     docker compose exec -T db pg_restore -U postgres -d pmzilla --clean --if-exists < ~/.pmzilla-lab/sauvegardes/db-AAAA-MM-JJ/$s.dump
   done
   ```
6. **Set the password of the views role again** (roles live in the volume and are lost with it): the command of step 3 of the 14.1 procedure, `uv run tools/db.py role-password pmzilla_flow_views`, generating the password in the Keychain first as described there.
7. **Check**: `uv run tools/db.py status` (every migration applied, none pending), the extension query of step 4 above, then `bash tools/db_restore_test.sh`: the restored database and the new real one are rebuilt from the same backup, so every table must read `OK`. Then re-import what was collected after the backup date (14.1).

**(b) Restore test, once a quarter** (it never touches the real database and does not back it up):

```bash
bash tools/db_restore_test.sh                      # latest backup in ~/.pmzilla-lab/sauvegardes/
bash tools/db_restore_test.sh --backup <folder>    # another backup folder (db-AAAA-MM-JJ)
```

What it does: starts a throwaway container (same pinned image as `docker-compose.yml`, unique name `pmzilla-lab-restore-test-…`, a port chosen by Docker on `127.0.0.1`, never 5432, its own random password: the real password is neither read nor used), applies the migrations, restores the three `.dump` files with `pg_restore --single-transaction --exit-on-error`, then compares the row count of every table of `knowledge`, `cases`, `flow` and `public.schema_migrations` with the real database (counts only, read through `docker compose exec`, no value) and compares a fingerprint of the migrations (`db/migrations/*.sql` files, throwaway database, real database). The throwaway container is removed at the end, even on an error or Ctrl+C. It prints only table names and counts.

Only folders named exactly `db-AAAA-MM-JJ` count as backups, for the test (latest date) as for the rotation of `db_backup.sh`; a folder with a label (`db-AAAA-MM-JJ-matin`) is ignored by both and is restored only with `--backup <folder>`. A backup older than a migration may not restore onto the migrated database: `pg_restore` fails on one schema, and the message (without detail) suggests trying a more recent backup or `--backup`.

**First test, 2026-10-08** (counts only): restoration OK, the five `flow` tables with identical counts, identical migration fingerprint, throwaway container removed.

**Making a second backup the same day.** `db_backup.sh` never overwrites the folder of the day. To redo it, rename that folder first (for example `mv ~/.pmzilla-lab/sauvegardes/db-AAAA-MM-JJ ~/.pmzilla-lab/sauvegardes/db-AAAA-MM-JJ-matin`), then run `bash tools/db_backup.sh`. The renamed folder is kept as it is (neither tested by default nor rotated); delete it by hand when it is no longer useful.

How to read the output:

| Line | Meaning |
|---|---|
| `OK` after a table | Same number of rows in the restored copy and in the real database |
| `écart -20 (attendu possible …)` | The real database changed since the backup (import, collection): normal if the backup is a few days old. Not a failure |
| `MANQUE dans la base restaurée` | A table of the real database is missing from the restore: **failure** (exit 1) |
| `ATTENTION : … restaurée(s) à 0 ligne` | A table is empty in the copy but filled in the real database: check the backup date (was it taken before the import?) |
| `ÉCHEC <schema> : pg_restore a échoué` | The dump cannot be restored: **failure**. Re-run with `--detail` to see the PostgreSQL errors (they may quote values: do not paste them anywhere) |
| `l'empreinte des migrations diffère` | The files, the restored database and the real one do not list the same migrations (a pending migration, a modified file): **failure**; the numbers and names that disagree are listed |
| `Conteneur jetable supprimé` | The cleanup ran. If it says `ATTENTION … existe encore`, run the `docker rm -f -v` command it prints |

Exit code 0: the restore works (row gaps possible); 1: restore failed, table missing or migration fingerprint different; 2: a prerequisite is missing (no backup, Docker stopped, real database stopped) and nothing was restored. Note the date and the result in your journal; if the backup is too old for a gap to be explained, run `bash tools/db_backup.sh` and repeat the test.

What the test does not cover: the contents of the rows (counts only), the roles and their passwords (rebuilt by the migrations, the password of the views role is set by hand), a restore into the real container, and the integrity of the Docker volume itself.

**Troubleshooting (section 14)**

| Symptom | Likely cause |
|---|---|
| `Colima ne tourne pas` or `Docker ne répond pas` | Colima is stopped: `colima start --cpu 4 --memory 6` |
| `Mot de passe de la base introuvable` | No Keychain entry: step 2 |
| The migration `0005` fails with `could not resize shared memory segment … No space left on device` | The container's `/dev/shm` is too small (64 MB by default). `shm_size: 1gb` is in `docker-compose.yml`: run `bash tools/db_up.sh` to recreate the container (the volume is kept), check `docker compose exec -T db df -h /dev/shm` (1.0G), then `uv run tools/db.py migrate` again. The failed migration was rolled back and is not recorded as applied |
| The first start fails with PostgreSQL saying the superuser password is not specified | The volume was created without a password (a direct `docker compose up`): use `bash tools/db_up.sh`; if the volume is empty and holds nothing yet, remove it with `docker volume rm pmzilla-lab_pgdata` and start again. `docker compose ps`, `port` and `exec`, and `tools/db_backup.sh`, do not need the password |
| `port is already allocated` or `address already in use` | Port 5432 is taken: `PMZILLA_LAB_DB_PORT=5433 bash tools/db_up.sh` |
| The container is `unhealthy` or restarts | `docker compose logs db`; after a change of password, the old one stays in the volume (it is read only at the first creation of the volume) |
| `La base ne répond pas` from `db_backup.sh` | The database is stopped: `bash tools/db_up.sh` |

### 14.3 The library in the database (lot 4)

The library (books, figures, watch and own articles) can be copied from the SQLite index `~/.pmzilla-lab/library.sqlite` into the schema `knowledge`, without converting the books again and without recomputing a vector (bge-m3). **PostgreSQL is the default since the switch of the lot 4 (SQLite stays available for one month as a fallback)**: the four MCP tools are the same on both routes, `serve --backend sqlite|postgres` (or `PMZILLA_LAB_BACKEND`) chooses. Nothing below changes what the postures read.

1. **Back up, then migrate** (migration `0004_knowledge_library.sql`: tables, full-text column, indexes, no data):
   ```bash
   DB_BACKUP_DATE=$(date +%Y-%m-%d)-avant-lot4 bash tools/db_backup.sh && uv run tools/db.py migrate --dry-run && uv run tools/db.py migrate
   ```
2. **Read-only role.** Set the password of `pmzilla_knowledge_ro` (typed at the prompt, never as an argument), then put the same password in the Keychain under the service `pmzilla-lab-db-pmzilla_knowledge_ro` (the command prints the exact `security` line; same procedure as `pmzilla_flow_views`):
   ```bash
   uv run tools/db.py role-password pmzilla_knowledge_ro
   ```
3. **Import, then verify** (counts and file names only, no text of a book; incremental by `sha256` of each book, so it can be rerun at any time):
   ```bash
   uv run tools/knowledge_import.py import --dry-run && uv run tools/knowledge_import.py import && uv run tools/knowledge_import.py verify
   ```
   `verify` compares the counts (books, passages, figures, collections) and the content fingerprint of every book on both sides; exit code 1 names the books that differ. `import --deep` also rereads every vector of the database (slower). `verify --vectors N` also rereads N random vectors from PostgreSQL, compares them with SQLite and prints only the maximum gap, the minimum cosine, the extreme norms and the number of null vectors (use a large N, for example 5000, to look for null vectors).
4. **Keep the copy up to date.** The daily watch run still writes the SQLite index (the watch moves to PostgreSQL at lot 5). Once the first import has succeeded, switch the synchronisation on: `watch.sh` then runs `knowledge_import.py import` after each successful indexing.
   ```bash
   touch ~/.pmzilla-lab/knowledge-sync
   ```
   It never blocks the watch: if the database does not answer, the log says `Synchronisation PostgreSQL en erreur` and a macOS notification is sent (start the database with `bash tools/db_up.sh`); the watch exit code does not change. After a good import, `watch.sh` also runs `verify`, which probes the BM25 index (section 14.6). Remove the file to switch it off.
5. **Parity** (right after an import, so that both routes hold the same passages; the report goes to the Terminal only and holds identifiers and counts, never a text):
   ```bash
   uv run tools/library_parity.py
   ```
   It runs the frozen set of 42 queries (French and English, `tests/parity/queries.yaml`) on both routes and prints a summary: per query the overlap of the first 8 results (pairs file and position), a verdict and the latency of each route, then the mean, the minimum, the queries under 0.5 and the mean and p95 latency of each route. `--details` adds the file:position of the results that only one route returns. `--component vector|text|hybrid` measures one way alone (similarity only, full text only, or both merged, the default): run the three when the overlap is low, the component that fails is the cause. Proposed threshold: mean at least 0.85, no query under 0.5, at least 7 of 8 for the queries marked `rare`. Options: `--scan ann|exact` (HNSW index, the default, or the exact scan) and `--ef-search N` (`hnsw.ef_search` of the ann scan, 1 to 1000, 400 by default; pgvector's own default, 40, is below the 50 candidates of the vector way and left some queries under 3 of 8), `--rank-norm 0|1|2` (length normalisation of `ts_rank_cd`: none, divided by 1 + log of the length, divided by the length; only with `--fulltext tsvector`), `--collections watch,own-articles`, `--limit`, `--threshold`. `--fulltext tsvector|bm25` chooses the full-text ranking of the PostgreSQL route (`bm25` by default, `tsvector` to compare). `--explain ID` runs no parity: it prints the `EXPLAIN (ANALYZE, BUFFERS)` plan of the query `ID` on the PostgreSQL route, with no literal (no word of the query, no collection, no date, no vector), to understand a latency.
6. **Try the SQLite fallback route** (PostgreSQL is already the default): `PMZILLA_LAB_BACKEND=sqlite` in the environment of the MCP server (`claude mcp add` with `serve --backend sqlite`), or for the evaluation set `--backend sqlite` (`posture_evals.py`).

The search is the same hybrid as before, written in SQL (`tools/hybrid_search.py`): 50 semantic candidates and 50 full-text candidates, reciprocal rank fusion (constant 60), freshness bonus for the watch collection. The similarity is the dot product, like the SQLite route. The full text is BM25 (pg_search, migration `0005`), with the same OR of words as FTS5 and the same number of candidates: the 200 best passages first (filtered only by the kind of passage), then the collection and date filters, then the first 50. As on the SQLite route, a collection filter therefore applies after the limit of 200. The index uses the `pdb.simple` tokenizer with `ascii_folding`, which is equivalent to FTS5 `unicode61 remove_diacritics 2` for French and English: split on non-alphanumeric characters (the apostrophe and the underscore split), lowercase, accents removed, no stemming, no stop words (the equivalence is written at the top of the migration). The old ranking, `ts_rank_cd` on a `tsvector`, ignores the rarity of words, so a query made of common words was ranked by its stop words (measured overlap with SQLite: 0.09): `--fulltext tsvector` keeps it only to compare. Rollback is immediate: SQLite and its index are untouched; `serve --backend sqlite` (or removing `PMZILLA_LAB_BACKEND`).

### 14.4 The cases module (lot 2)

The cases module keeps your experiments and, once reviewed, your cases (what you tried, the result, what got stuck) in the schema `cases`, and finds the closest ones when you submit a problem. The MCP server stays read-only: it offers three tools (`search_cases`, `search_experiments`, `list_due_reviews`), so the server now has seven tools. Everything is written through `tools/journal_lab.py experiment …` (modes of `/journal`: `start`, `note`, `show`, `postpone`, `drop`, `close`, `due`), under the role `pmzilla_cases`. Run the steps in this order, in a Terminal:

1. **Tests with the database** (each must end with `OK` and no `skipped=`):
   ```bash
   for suite in db hybrid_search cases_store library_backend; do PMZILLA_LAB_DB_PASSWORD="$(security find-generic-password -s pmzilla-lab-db -w)" uv run --with numpy --with httpx --with pyyaml --with "psycopg[binary]" python -m unittest discover -s tests/$suite 2>&1 | tail -3; done
   ```
2. **Back up (label made of letters only), then migrate** (migration `0006_cases_experiments.sql`: three tables, BM25 and HNSW indexes, no data):
   ```bash
   DB_BACKUP_DATE=$(date +%Y-%m-%d)-avantlotdeux bash tools/db_backup.sh
   uv run tools/db.py migrate --dry-run
   uv run tools/db.py migrate
   ```
3. **Two roles that log in**, each with its own password generated straight into the Keychain (the clipboard is emptied after each paste):
   ```bash
   security add-generic-password -U -s pmzilla-lab-db-pmzilla_cases_ro -a "$USER" -w "$(openssl rand -hex 24)"
   security find-generic-password -s pmzilla-lab-db-pmzilla_cases_ro -a "$USER" -w | pbcopy && uv run tools/db.py role-password pmzilla_cases_ro
   pbcopy < /dev/null
   security add-generic-password -U -s pmzilla-lab-db-pmzilla_cases -a "$USER" -w "$(openssl rand -hex 24)"
   security find-generic-password -s pmzilla-lab-db-pmzilla_cases -a "$USER" -w | pbcopy && uv run tools/db.py role-password pmzilla_cases
   pbcopy < /dev/null
   ```
4. **Your author identifier** (local, never in a tracked file). Note the total of the personal-identifiers scan, write the identifier, check that the file is ignored by Git, then check that the total did not change:
   ```bash
   python3 tools/identifiants_personnels.py | tail -1
   printf 'author: %s\n' "<your-identifier>" > .pmzilla/cases.yaml
   git check-ignore .pmzilla/cases.yaml
   python3 tools/identifiants_personnels.py | tail -1
   ```
   If the second total is higher, rerun with `--lignes` and remove the occurrences before going on.
5. **Checks:** `uv run tools/db.py status` (0006 applied, nothing pending); `uv run tools/journal_lab.py experiment due` (no review due, exit code 0); `uv run tools/dashboard.py --open` (the seventh section says "no data yet"); `claude mcp get pmzilla-library` (connected), then `/mcp` in a new Claude Code session shows seven tools; `test -f Flux-Lab/noms-sensibles.txt && echo present` prints `present` (without a list of sensitive names, or with an empty one, every experiment write is refused).
6. **Session hook.** `.claude/settings.json` declares a `SessionStart` hook that lists the reviews that are due, without running anything: `uv run tools/journal_lab.py experiment due --session-hook`. A new session shows no error from the hook and, until a review is due, no line. Evaluation sessions run the hook on the disposable database; no shipped case has a review due, and without a disposable database (empty author, no `.pmzilla/cases.yaml` in the copy) the hook prints nothing and exits 0, so it never changes a graded answer.
7. **Evaluation set**, French then English (each run is paid; 37 of 37 expected): `uv run ~/PMZilla-Lab/posture_evals.py` and `uv run ~/PMZilla-Lab/posture_evals.py --language en`. The cases run against a disposable cases database filled with invented data, never your real cases. The three cases that use a cases fixture (`cas-proche-reussi`, `cas-proche-echoue`, `experimentation-en-cours`) need that disposable database: the PostgreSQL instance must be running (`bash tools/db_up.sh`) and the superuser password must be reachable as for `tools/db.py`, in the Keychain (service `pmzilla-lab-db`) or, as a fallback, in the variable `PMZILLA_LAB_DB_PASSWORD`; the script declares its own dependencies (`psycopg[binary]`, `httpx`, `numpy`, `mcp`), so a plain `uv run` is enough and no variable is needed when the Keychain holds the password. If the database cannot be created, the first line of the run says why (the message names the Keychain service and the variable, never a value), those cases are reported as "non évaluable ici : cases database unavailable", the summary reads `BILAN 34/37 · 3 non évaluable(s) · passage non validant` and the exit code is 3: such a run validates nothing, whatever its score. To replay only those three cases, in French then in English:
   ```bash
   uv run ~/PMZilla-Lab/posture_evals.py --cases cas-proche-reussi,cas-proche-echoue,experimentation-en-cours
   uv run ~/PMZilla-Lab/posture_evals.py --language en --cases cas-proche-reussi,cas-proche-echoue,experimentation-en-cours
   ```
   A partial run is never a reference; the acceptance of 37 of 37 is read on the two complete runs.

The similarity threshold of the search (`MIN_SIMILARITY` in `tools/cases_store.py`) is provisional: it was calibrated on the invented set of the evaluation cases (`uv run tools/cases_calibration.py`) and is recalibrated after your first ten real cases. The `experience` block of the journal is deprecated: it is still read, with a warning, and a later change removes it.

### 14.5 Suites with a throwaway database

The suites `tests/flow_store` and `tests/flow_compare` refuse the database of `bash tools/db_up.sh` (port 5432, the real one): they need a throwaway PostgreSQL instance on ANOTHER port, in which they create their databases (`pmzilla_test_<hex>`, dropped after each test). `tests/db`, `tests/flow_import`, `tests/flow_views` and `tests/hybrid_search` accept either instance; run them against the throwaway one too, so that nothing touches the real data. Without such an instance the tests that need it are skipped, with the message « base jetable absente ».

`tools/dbtest.sh` does it all. You type it in your Terminal, Claude Code is not allowed to run it (`deny` rules, like `db_up.sh`):

```bash
cd ~/PMZilla-Lab/workspace
bash tools/dbtest.sh                          # db, flow_import, flow_store, flow_compare, flow_views, hybrid_search
bash tools/dbtest.sh flow_store flow_compare  # only these suites (folders of tests/)
bash tools/dbtest.sh --port 55433             # another host port (default 55432; never 5432 nor the real database's port)
```

- It starts the container `pmzilla-lab-test-db` (the image pinned in `docker-compose.yml`, published on `127.0.0.1` only) with a random password. The password lives in the script only: it is never displayed, never written, never exported in your shell, and the Keychain password of the real database is not read.
- It refuses to start if the port is 5432 (or the real database's port), if a suite does not exist, or if a container named `pmzilla-lab-test-db` already exists (it is then neither touched nor removed).
- It runs each suite with `bash tests/run_all.sh <suite>` and no pipe, then prints « Suites vertes » and « Suites en échec ». The exit code is 1 if a suite fails or the container does not start, 2 for a refusal.
- It removes the container and its volume (`docker rm -f -v`) at the end, also after a failure or Ctrl+C. If it says « ATTENTION … existe encore », run the `docker rm -f -v pmzilla-lab-test-db` command it prints.
- The suites apply the migrations themselves in each test database. A suite whose tests need the database must no longer show them as skipped (`skipped=…` in its line); the two diagnostics of `hybrid_search` (`PMZILLA_DIAG=1` shows them) stay skipped, as expected.

### 14.6 Damaged BM25 index

**Symptom.** A text search on the PostgreSQL route fails with `psycopg.errors.InternalError_: bitmap intersection stream (consumer 0, segment …) claimed twice` (pg_search, ParadeDB 0.26.0), typically on queries filtered by passage type (`types: ["figure"]`); the vector component and unfiltered text queries may still work. The error always names the same segment: the index `knowledge.chunks_bm25` is damaged (a disposable database, with a fresh index, does not show it). Setting `enable_bitmapscan = off` does not help.

**Detection.** The daily watch run checks it: after a successful library import, `watch.sh` runs `uv run tools/knowledge_import.py verify`, which also reads the BM25 index twice (without and with the passage-type filter) under the read-only role. On failure the log says `Index BM25 illisible` and a macOS notification points here. `verify` then exits with code 3 (1: difference between the copies; 2: database unreachable). The watch itself is never blocked and its exit code does not change. Nothing is repaired automatically.

**Rebuild** (you alone, as superuser, in your Terminal; Claude Code does not run it):

```bash
# psql as the superuser of the cluster, connected to the library database; adapt the connection to your setup
SET max_parallel_maintenance_workers = 0;
REINDEX INDEX knowledge.chunks_bm25;
```

The operation rebuilds the index only: no passage, vector or book is touched or lost, and the SQLite index is not involved. It reads the table and rewrites the index, so allow a few minutes on the whole library, and run it while no search is running.

**Check.** `uv run tools/knowledge_import.py verify` must end with `index BM25 lisible` (exit code 0), then `uv run tools/library_parity.py` must pass again (section 14.3, step 5). Until then the SQLite route stays the fallback: `PMZILLA_LAB_BACKEND=sqlite` (section 14.3, step 6).

## 15. Repository audit (`/audit`)

The `/audit` command (`.claude/commands/audit.md`) checks the repository without changing anything: it makes no edit and no commit, runs no command on the database, no test suite and no evaluation set. It writes only `.pmzilla/audit/YYYY-MM-DD.md` (the report) and `.pmzilla/audit/dernier-commit` (the hash of `HEAD` at the end of the pass), both outside Git.

- `/audit` (default, Sonnet, about 5 minutes, for the end of a session): state for the night (branch, status, unpushed commits, unmerged branches, stash; first, any file read by the 7:10 watch that differs from `main` when the branch is not `main`), OpenSpec changes not archived, documentation and CHANGELOG for the files changed since `dernier-commit`, books added without a complete entry in `tools/book_catalog.yaml`, the identifier scanner on the changed files, backup or temporary files left (by name only).
- `/audit complet` (Opus, parallel agents by domain: documentation, code, tests, configuration): the full audit, with four tables (to correct, to complete, to delete, to keep despite appearances) and a cleanup plan in thematic commits.

Each finding is numbered with an action, a proof and a risk; what an OpenSpec change in progress already covers is reported as covered, not as a finding. The message ends by asking which numbers to handle: nothing is handled before the answer. Create `.pmzilla/audit/` once (`mkdir -p .pmzilla/audit`) if it does not exist.

## 16. Working on the repository

### Finishing a branch (`tools/finish_branch.sh`)

The script merges the current work branch into `main`, pushes `main` and deletes the branch. Run it in your own Terminal, from the repository, on the branch to finish: `bash tools/finish_branch.sh`. Claude Code cannot launch it (deny rules cover every launcher and path form); reading it and running its test suite (`bash tests/finish_branch/test_finish_branch.sh`) stay allowed. It is already covered by the `chmod +x tools/*.sh` line of section 3.

It checks, in this order, and stops at the first refusal before touching any branch: usage, a branch to finish (not `main`, not a detached head), a clean working tree, every linked OpenSpec change archived (a branch that changes only `openspec/` is treated as a specification branch), a recorded validating evaluation run when `CLAUDE.md`, the posture skills, the Critic agent, the posture vocabulary or the frozen posture memory changed, `main` up to date with the remote, the branch containing `main`, then a complete green run of `bash tests/run_all.sh`. It never forces, rebases, resolves a conflict, bypasses a hook or runs the evaluation set.

| Code | Meaning |
|---|---|
| 0 | merged, pushed, branch deleted |
| 1 | complete run red, nothing merged |
| 2 | usage |
| 3 | no branch to finish |
| 4 | working tree not clean |
| 5 | OpenSpec change not archived |
| 6 | validating evaluation run missing (or its tested state no longer exists: run the set again on the committed state) |
| 7 | `main` not up to date |
| 8 | the branch does not contain `main` |
| 9 | merge impossible, aborted, back on the branch |
| 10 | push refused: the merge exists on local `main` only; the message gives the retry and undo commands |
| 11 | branch not deleted after a successful merge and push |

For tests, `FINISH_BRANCH_RUNNER` replaces the runner and `FINISH_BRANCH_RECORDS` the folder of evaluation records.

### Generating the English edition (`tools/build_edition.py`)

`uv run tools/build_edition.py --language en --output <dir> [--commit <rev>] [--run-tests]` writes a tree of the committed state (default `HEAD`) for a public repository. It reads the Git objects of the commit, never the working tree, and refuses a dirty tree. `edition/manifest.yaml` classifies every tracked file (`include`, `exclude` with a reason, or `template` from `edition/templates/`); a tracked file without a rule stops the build. The tree holds no personal layer and no history. The generator never publishes: it creates no repository (no `git init` in the output), never pushes and makes no network call. `<dir>` must not exist and must lie outside the workspace.

The tree is built in `<dir>.incomplete`, then checked: the identifier scanner in tree mode (`tools/identifiants_personnels.py --arbre`) and the sensitive-name rules of the pre-commit hook, on every file. It becomes `<dir>` only when the checks pass; on a finding it is renamed `<dir>.not-publishable` (the report gives paths and line numbers, never the values). `--run-tests` copies the tree into a throwaway repository in a temporary folder and runs `bash tests/run_all.sh` there. Exit codes: 0 publishable tree; 1 tests red; 2 usage; 3 source refused; 4 output refused; 5 manifest invalid; 6 unclassified tracked paths; 7 identifier or sensitive name found; 8 publication check could not run (sensitive-names list absent or empty). Tests: `tests/build_edition`.

**Before each generation (edition job R-33), refresh the pinned versions on purpose.** The lock files of `tools/` (section "Script dependencies" below) are shipped with the edition by the manifest (the locks of the private scripts stay out). In your Terminal, on a work branch:

```bash
cd ~/PMZilla-Lab/workspace
for f in tools/*.py; do [ -e "$f.lock" ] && uv lock --script --upgrade "$f"; done
bash tests/run_all.sh
```

Commit the locks that changed only when the run is green, then generate the edition from that commit.

### Model and method

- **Model rule (decided on 2026-10-10).** Frame and specify on Opus, then type `/model sonnet` in the same session to execute while the context is useful. The `/implement`, `/close`, `/add-books` and `/next` headers set Sonnet; `/audit complet` stays on Opus.
- **OpenSpec rule, by kind of work.** OpenSpec for behaviour, postures, `CLAUDE.md` and publication (proposal, design, tasks, delta specs under `openspec/changes/`); a direct prompt for maintenance (a test gap, a cleanup, a fix with no behaviour change). The queue below records the method of each job.

### The commands

| Command | What it does | What it never does |
|---|---|---|
| `/implement <change>` | Reads the change, creates a branch ending with its name when started on `main`, implements `tasks.md` in order (tests first), commits after a green `bash tests/run_all.sh --staged`, ticks a task only when its suite passes, ends with one message. | Push, merge, run the finishing script, bypass a hook, launch the real Jira tools, the imports, the database scripts or the evaluation set (cost announced first). |
| `/close <change>` | Ticks the covered tasks, updates the status documents the repository keeps (if any), adds the CHANGELOG line, archives the change (every unticked task has a reason, you confirm), marks the queue job `done`, commits, prints `bash tools/finish_branch.sh`. | Run the finishing script, push, merge, invent a queue job. |
| `/add-books <files>` | From file names: proposes the domains (you validate), writes the `MAPPING` line, the `EXCLUSIONS` line of a PDF duplicate (EPUB first) and the catalogue entry (`a_verifier` when deduced from the file name), applies the pending items of section 4 of `bibliotheque-lacunes.md`, prints the commands in order (conversion dry run, conversion, sort, indexing, import dry run, import, verification). The daily watch run imports into the database after indexing: a catalogue change reaches the database at the next daily run. | Run any of those commands, open a book, decide the domains. |
| `/next <duration>` | Proposes the jobs of `docs/pmzilla/feuille-de-route.md` that are `ready`, whose dependencies are `done` and whose `not_before` date is reached, that fit the time given; the jobs without an estimate are listed apart. | Edit the queue, start a job, invent an estimate. |
| `/start <id>` | Checks the job (queue valid, `ready`, dependencies `done`, `not_before` reached; asks you to confirm its conditions and to switch to its model), creates its branch from `main`, does it from its description (direct prompt) or through `/implement` (OpenSpec; a missing change is written by `spec-writer` and reviewed by you first), marks it `done` on the branch, commits, prints `bash tools/finish_branch.sh`. | Push, merge, run the finishing script, reorder the queue, change a job's estimate, model or dependencies, start a job that is not ready. |

The queue is one YAML block; `uv run --with pyyaml python tools/roadmap.py check` validates it, `next --budget 2h` is what `/next` runs, `done <id>` is what `/close` and `/start` run. The model field accepts `opus`, `sonnet`, `haiku` or `tbd`. The merge, the first time (change `workflow-tooling` itself), follows the procedure given in the final message of its implementation; afterwards `/close` ends with `bash tools/finish_branch.sh`, typed in your Terminal.

### Script dependencies (decisions of 2026-10-10 and 2026-10-11)

Each script of `tools/` declares its third-party packages in its `# /// script` block, imports reached through other modules of `tools/` included, even late ones inside a function; `uv run` builds and caches one environment per script. The tests add theirs with `uv run --with …`. The headers pin no version, except the `mcp>=1.2,<2` bound, and there is no `pyproject.toml`. `tests/script_dependencies` checks the declarations of every entry script.

**Pinned versions (decision of 2026-10-11, R-36; it replaces the unpinned daily use of R-10).** Each entry script that declares dependencies has its lock file next to it, `tools/<script>.py.lock`, written by `uv lock --script tools/<script>.py` and tracked; `uv run` reads it, for daily use as for a fresh clone of the edition, which receives the same files. The tests still add their packages with `uv run --with …`; the real check of `tests/script_dependencies` (`uv run --isolated tools/<script>.py --help`, skipped without network nor cache) runs the locked versions, and the suite fails when an entry script with dependencies has no lock, when a lock no longer lists the packages of its header, or when a lock has no script. A new entry script with dependencies: run `uv lock --script tools/<script>.py` and commit the lock with it. The versions only move when you refresh them on purpose ("Generating the English edition", above).

Other guards: the versions resolved stay in the uv cache, and two guards cover what changes them: `.python-version` at the root fixes the Python version, and the watch checks the uv cache every morning when uv or its Python changed (next paragraph).


### After an update of uv

The watch does this check by itself. Every morning `tools/watch.sh` compares the uv version and the Python version uv picks with those recorded in `~/.pmzilla-lab/` (`uv-version`, `uv-python-version`). When one changed (or nothing is recorded yet), it runs a throwaway script (the `# /// script` header of the wake-up script, then `import yaml`; no wake-up code is executed) from a temporary folder with the network, checks offline from a second one, writes the result in the watch log (`~/Library/Logs/pmzilla-watch.log`) and records the new versions only on success. It sends a macOS notification only on failure, and never stops the watch. The project Python is fixed by `.python-version` at the root (3.14 on 2026-10-10). The manual procedure below is for a notified failure, or to force the check (delete the two files above).

The offline wake-up test of `postures_skills` fails as long as the uv cache does not hold the `pyyaml` package for the Python version uv picks (seen on 2026-10-10 with uv 0.13.0 and Python 3.14: `Failed to download pyyaml…`, the network being cut in the sandbox). Commands with `--with` do not fill that cache. Fix it in your Terminal, with Claude Code and the watch stopped (otherwise the cache is locked): copy a wake-up script to a temporary folder, run it there once with the network, then check offline from a second temporary folder.

```bash
cd ~/PMZilla-Lab/workspace
dossier=$(mktemp -d) && cp .claude/skills/pmzilla-discovery-bmad/scripts/wake.py "$dossier"/
(cd "$dossier" && uv run wake.py)                  # with the network; the script path error it prints is of no importance
verif=$(mktemp -d) && cp .claude/skills/pmzilla-discovery-bmad/scripts/wake.py "$verif"/
(cd "$verif" && UV_OFFLINE=1 uv run wake.py)       # offline check from another folder: no download must be attempted
bash tests/run_all.sh postures_skills
```
