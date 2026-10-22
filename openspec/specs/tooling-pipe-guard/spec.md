# tooling-pipe-guard Specification

## Purpose
The pipe guard (`tools/pipe_guard.py`), fed by a Claude Code hook on Bash calls, flags a command that pipes into an interpreter, a search or a tail, and tells the model in French, before the command runs (PreToolUse form, the one posed since 2026-10-19) or after it (PostToolUse form). It never allows or denies a call: it teaches, and blocking stays a later decision (change deny-rules-review, Q5).

## Requirements

### Requirement: The pipe guard flags pipes into an interpreter, a search or a tail
The system SHALL provide a pipe-guard tool that reads a hook input on its standard input and, for a Bash call, flags every `|` or `|&` pipe whose receiving program (base name, after variable assignments) is `python3` with or without a minor version, `python`, `grep`, `egrep`, `fgrep` or `tail` (design D6 of change deny-rules-review). It SHALL NOT treat `||` as a pipe, flag a program that receives no pipe, or look inside quoted strings.

#### Scenario: Pipe into grep
- **WHEN** the Bash command is `ls tests | grep pilot`
- **THEN** the tool flags `grep`

#### Scenario: Interpreter with version and absolute path
- **WHEN** the command pipes into `python3.12 -c` or into `/usr/bin/grep`
- **THEN** the tool flags `python3.12` or `grep` respectively

#### Scenario: No pipe
- **WHEN** the command is `git grep x`, `a || grep x`, `grep x file`, `tail -f log` or `echo "a | grep"`
- **THEN** the tool flags nothing

### Requirement: The pipe guard exempts a tail fed by the test runner
The system SHALL NOT flag a `tail` fed directly by a test-runner call, that is a pipeline segment holding a word whose base name is `run_all.sh` or the word `unittest`, redirections such as `2>&1` ignored (design D6, decision Q3 option B). It SHALL NOT extend this exemption to `python3`, `python`, `grep`, `egrep` or `fgrep`, nor to a `tail` fed by any other program, including a `grep` that follows the runner.

#### Scenario: Tail after the test runner
- **WHEN** the command is `bash tests/run_all.sh select_suites 2>&1 | tail -4` or `uv run python -W ignore -m unittest discover -s tests/x -q -f 2>&1 | tail -4`
- **THEN** the tool flags nothing

#### Scenario: Exemption limited to tail after the runner
- **WHEN** the command is `bash tests/run_all.sh x | grep -v ok | tail -5`, `bash tests/run_all.sh x | grep ok`, `python -m unittest | python3 -c y` or `git log | tail -4`
- **THEN** the tool flags `grep, tail`, `grep`, `python3` and `tail` respectively

### Requirement: The pipe guard never blocks a call
The system SHALL make the pipe guard signal a flag without blocking, with the exit codes and outputs of design D7: `--event post` exits 2 with the message of D8 on the error output; `--event pre` exits 0 with the message as `additionalContext`; nothing flagged or unreadable input exits 0 silently; a usage error exits 1. It SHALL NOT print a permission decision, so it can neither allow nor deny a call.

#### Scenario: Flag after the run
- **WHEN** the tool runs with `--event post` on a command that pipes into `tail`
- **THEN** it exits 2 and the error output is `garde des tubes : sortie passée à « tail » ; utiliser l'outil Read ou Grep, ou lire la sortie telle quelle (préambule des agents). Signalement seulement : la commande n'a pas été bloquée.`

#### Scenario: Flag before the run
- **WHEN** the tool runs with `--event pre` on a command that pipes into `grep` and then `python3`
- **THEN** it exits 0 and prints a JSON object whose `hookSpecificOutput.additionalContext` names `grep, python3`, with no `permissionDecision`

#### Scenario: Unreadable input
- **WHEN** the standard input is not JSON or the command has unbalanced quotes
- **THEN** the tool exits 0 with no output

#### Scenario: Usage error
- **WHEN** the tool runs without `--event`
- **THEN** it exits 1 with the usage line

### Requirement: The pipe guard reads and writes nothing else
The system SHALL keep the pipe guard to the standard library, reading only its standard input. It SHALL NOT read or write a file, call the network or another command, or print the command or any part of it other than the receiving programs' names.

#### Scenario: Command text kept out
- **WHEN** the tool flags a command that holds a path and a pattern
- **THEN** its output holds neither the path nor the pattern

#### Scenario: Tool text scanned
- **WHEN** the tool's source is scanned
- **THEN** it holds no `permissionDecision`, no subprocess call and no file opened for writing
