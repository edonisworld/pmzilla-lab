# posture-outside-library Specification

## Purpose
Each posture's rules cite works, some of which are not in the user's library. A script computes, for each posture, the list of cited works that are absent from the user's book catalogue (the "outside the library" list) and the relations between works that must not be confused, from a tracked references file. The posture wake script prints this list; that printing is described by posture-evals-skills.

## Requirements

### Requirement: The list is computed from the user's catalogue
The system SHALL list, for a posture, the works its references file cites that no catalogue entry matches. An entry SHALL match a work when its title equals the work's title or one of its aliases, or contains it as whole words (or the reverse for a long enough catalogue title), ignoring case, accents and punctuation, and when they share an author or either has none.

#### Scenario: Book in the catalogue
- **WHEN** the catalogue holds a book whose longer title contains the cited title as whole words, by the same author
- **THEN** the work is not in the list

#### Scenario: Same title, other author
- **WHEN** the catalogue holds a book with the cited title by another author
- **THEN** the work stays in the list

#### Scenario: Accents and case
- **WHEN** the catalogue title differs from the cited title only by capitals and accents
- **THEN** the work is not in the list

#### Scenario: Empty catalogue
- **WHEN** the catalogue is empty
- **THEN** every cited work is in the list

Source: tests/outside_library/test_outside_library.py (TestCalcul)

### Requirement: Documents are matched like books
The system SHALL treat an official document or toolbox marked as a document like a book: it SHALL stay in the list until a catalogue entry carries its title, and SHALL leave it as soon as it is indexed.

#### Scenario: Document not indexed
- **WHEN** the catalogue holds no entry with the document's title
- **THEN** the document is in the list

#### Scenario: Document indexed
- **WHEN** the catalogue holds the document under a title that contains it
- **THEN** the document is not in the list

Source: tests/outside_library/test_outside_library.py (TestCalcul.test_document_hors_bibliotheque_tant_qu_il_n_est_pas_indexe, TestCalcul.test_document_indexe_n_est_plus_hors_bibliotheque)

### Requirement: An unreadable catalogue classifies nothing
The system SHALL read the catalogue given by option, else the one named by an environment variable, else the default catalogue of the tools folder. When the catalogue is absent or unreadable, it SHALL classify nothing and say that the list is not computed, pointing to the out-of-library formula of the response language without quoting it. It SHALL NOT guess the list.

#### Scenario: Catalogue absent
- **WHEN** the catalogue file does not exist
- **THEN** no list is returned and the message says the list is not computed

#### Scenario: Catalogue from the environment
- **WHEN** the environment variable names a catalogue and no option is given
- **THEN** that catalogue is used

Source: tests/outside_library/test_outside_library.py (TestCalcul.test_catalogue_illisible_ne_classe_rien, TestCalcul.test_catalogue_par_variable_d_environnement); the option is untested

### Requirement: Relations between works are printed with the list
The system SHALL print, under a posture's list, one line per relation of its works (a work that comments another, two works not to be confused, a work to rely on by default), with the related work and the note when present. A posture without relations SHALL print none, and an unknown posture SHALL give a message naming the known postures instead of a list.

#### Scenario: Relations of a posture
- **WHEN** a posture cites a work that comments another and a work not to be confused with a third
- **THEN** two relation lines are printed, the second with its note

#### Scenario: Unknown posture
- **WHEN** the list of an unknown posture is asked
- **THEN** the output says the posture is unknown

Source: tests/outside_library/test_outside_library.py (TestCalcul.test_relations_imprimees_pour_la_posture, TestCalcul.test_posture_inconnue)

### Requirement: The references file has a fixed shape
The system SHALL keep a tracked references file with exactly the four postures, where every work has a title and either at least one author or the document mark, and every relation has a known type and a related work. Against an empty catalogue, every posture's list SHALL be non-empty.

#### Scenario: Shape of the tracked file
- **WHEN** the tracked references file is read
- **THEN** it names the four postures, each work has a title and an author or the document mark, and each relation type is known

Source: tests/outside_library/test_outside_library.py (TestReferencesDuDepot)

### Requirement: The command prints one posture or all
The system SHALL print the list and relations of the posture given, or of the four postures under one heading each when all are asked. It SHALL refuse the former French name of the catalogue option and point to the current one.

#### Scenario: All postures
- **WHEN** the command is asked for all postures
- **THEN** it prints a heading and a list for each of the four

Source: untested (tools/outside_library.py, main)
