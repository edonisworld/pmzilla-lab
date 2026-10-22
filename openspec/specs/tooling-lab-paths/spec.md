# tooling-lab-paths Specification

## Purpose
Resolve the lab folders (content root, code root, lab folder, run tree, context and worktrees folders) once, in shared Python and shell modules, from the variable or else from Git, so that no tool writes a literal lab path and a failed resolution stops the tool with a clear message.

## Requirements

### Requirement: One shared resolution of the lab folders
The system SHALL resolve the code root, the content root, the lab folder, the run tree and the local files ignored by Git through one shared module per language, Python and shell, both following the rule of design D1 and giving the same answers. A tool of the tools folder SHALL NOT compute one of these folders itself. Untested until implemented.

#### Scenario: Same answers in both languages
- **WHEN** the Python and the shell module run on the same fixture, under bash and under zsh
- **THEN** they give the same code root, content root, lab folder and run tree

### Requirement: The content root comes from the variable, else from Git
The system SHALL take the content root from its variable when it is set, else from the parent of the Git common folder of the code root, in the order of design D1. It SHALL NOT fall back on a folder under the home folder, on the code root or on the current folder. Untested until implemented.

#### Scenario: From a linked worktree
- **WHEN** a tool runs from a linked worktree and the variable is not set
- **THEN** its content root is the main checkout of that repository

#### Scenario: Variable set
- **WHEN** the variable names an existing folder
- **THEN** that folder is the content root and Git is not asked

### Requirement: A failed resolution stops the tool with a clear message
When the variable names a missing folder, or Git gives no usable common folder, the system SHALL stop the tool before any step with exit code 78 and the key phrase of design D2, naming the variable. It SHALL NOT print a path, guess a folder or run a step. The tools of design D7 keep their own outcome instead. Untested until implemented.

#### Scenario: Copy outside Git
- **WHEN** a tool runs from a copy outside any Git repository and the variable is not set
- **THEN** it prints "dossier de contenu introuvable", runs no step and exits with code 78

#### Scenario: Variable on a missing folder
- **WHEN** the variable names a folder that does not exist
- **THEN** the tool prints "PMZILLA_LAB_WORKSPACE désigne un dossier absent", prints no path and exits with code 78

### Requirement: The code root, lab folder and run tree are derived
The system SHALL take the code root from the resolved location of the running file, links followed; the lab folder as the parent of the content root; the run tree from its variable, else the run folder of the lab folder. It SHALL NOT take the lab folder or the content root as the code root. Untested until implemented.

#### Scenario: Through a lab-folder link
- **WHEN** a script is launched through its lab-folder link into the run tree
- **THEN** its code root is the run tree and its content root is the development checkout

### Requirement: Local ignored files are read in place
The system SHALL find each local file ignored by Git of the registry of design D5 at the path of its variable when set, else at its place in the content root, and read it there. It SHALL NOT copy, link or move such a file into a worktree, nor write its path into a tracked file. A missing file SHALL keep the behaviour of the tool that reads it. Untested until implemented.

#### Scenario: Sensitive-names list from a worktree
- **WHEN** a tool runs from a linked worktree that holds no sensitive-names list
- **THEN** it reads the list of the content root, and the worktree holds no copy and no link of it

#### Scenario: Replacement rules from a worktree
- **WHEN** the BMAD replacement rules are asked from a linked worktree
- **THEN** the path given is the one in the content root

### Requirement: A guard test forbids literal lab paths in the tools folder
The system SHALL include a guard test that fails, naming each file and line, when a tracked file of the tools folder holds a literal path to the lab folder or to a user's home folder (design D3). Once the migration ends, it SHALL accept no exception, comments included (design D4); until then, only the transitional list, where an entry with no literal left is an error. Untested until implemented.

#### Scenario: Literal path added
- **WHEN** a tool of the tools folder gains a line with a literal path to the lab folder
- **THEN** the guard fails and names that file and line

#### Scenario: Stale transitional entry
- **WHEN** a file of the transitional list no longer holds a literal path
- **THEN** the guard fails and names the entry

### Requirement: The context folder is resolved by the shared modules
The system SHALL resolve the context folder in both lab-paths modules by the rule of design D16 (change organisation-context): `PMZILLA_LAB_CONTEXT` when set, else `contexte` of the lab folder, with the same answer in Python, bash and zsh and a seventh printed line `context_folder=<path>`. The modules SHALL NOT create, list or touch anything inside it, and no tool SHALL compute it or write the former name `Contexte-Lab`. Untested until implemented.

#### Scenario: Default under the lab folder
- **WHEN** the Python and the shell module run on the same fixture without the variable
- **THEN** both give the folder `contexte` of the fixture's lab folder, and both print it on the line `context_folder=`

#### Scenario: Variable set
- **WHEN** the variable names a folder with a leading tilde
- **THEN** both modules give that folder, tilde expanded, and Git is not asked for it

#### Scenario: Nothing inside the folder touched
- **WHEN** the modules resolve a fixture context folder whose originals folder is watched for file access
- **THEN** no path inside the context folder is listed, opened, stat-ed or tested

#### Scenario: Former default written in a tool
- **WHEN** a tracked file of the tools folder writes `Contexte-Lab` as a path
- **THEN** the guard test fails and names that file and line

### Requirement: The worktrees folder is resolved by the shared modules
The system SHALL resolve the worktrees folder in both shared lab-paths modules from its variable when set, else as the worktrees folder of the lab folder, and print it as the last listed line (design D1). The shell module SHALL also give it for a given content root without Git. The modules SHALL NOT create, list or open anything inside it, and no tool SHALL compute it itself. Untested until implemented.

#### Scenario: Default under the lab folder
- **WHEN** the Python and the shell module run on the same fixture lab, under bash and under zsh, with the variable unset
- **THEN** both give as worktrees folder the worktrees folder of the fixture's lab folder, and the printed listing ends with the line `worktrees_folder=` and that path

#### Scenario: Variable set
- **WHEN** the variable names a folder, written with a leading tilde
- **THEN** both modules give that folder with the tilde expanded, whether or not it exists

#### Scenario: Missing folder is not an error
- **WHEN** the worktrees folder does not exist
- **THEN** the modules exit 0, print its path, and the folder is still absent afterwards

#### Scenario: Given content root
- **WHEN** the shell function is given a content root that is not the module's own repository
- **THEN** it prints the worktrees folder of that content root's lab folder and runs no Git command
