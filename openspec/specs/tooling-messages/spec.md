# tooling-messages Specification

## Purpose
Per-language message catalogs shared by scripts, with French as the reference language, fallback to French, and a consistency check between languages.

## Requirements

### Requirement: Language selection
The system SHALL return messages in the chosen language, formatting named fields, and SHALL reject a language absent from the catalogs.

#### Scenario: Chosen language
- WHEN the French or English language is selected and a key with a field is requested
- THEN the text in that language is returned with the field filled

#### Scenario: Unknown language
- WHEN a language that is not in the catalogs is selected
- THEN a value error is raised

Source: tests/messages/test_messages.py

### Requirement: Format-compatible escaping
The system SHALL render doubled braces as literal braces, like standard string formatting, even when no field is given.

#### Scenario: Literal braces
- WHEN a text contains doubled braces and no fields are passed
- THEN single braces appear in the result

Source: tests/messages/test_messages.py (test_accolades_doublees_rendues_comme_str_format)

### Requirement: Fallback to French
The system SHALL return the French text when a key is missing in the selected language, and SHALL raise a key error when the key exists in no language.

#### Scenario: Missing English key
- WHEN an English key is absent but present in French
- THEN the French text is returned

#### Scenario: Unknown key
- WHEN a key is in no catalog
- THEN a key error is raised

Source: tests/messages/test_messages.py

### Requirement: Catalog consistency check
The system SHALL report, per non-reference language, keys missing from it, keys absent from French, and keys whose fields differ from French; an empty list means consistent.

#### Scenario: Missing key
- WHEN the English catalog lacks a French key
- THEN the report lists that key as absent for English

#### Scenario: Field mismatch
- WHEN a key uses different fields in two languages
- THEN the report lists a mismatch

Source: tests/messages/test_messages.py (test_check_catalogs)

### Requirement: Shared language option
The system SHALL provide a command-line option choosing between French and English, defaulting to French and rejecting other values.

#### Scenario: Option values
- WHEN no option, an English option or an unsupported language is passed
- THEN the result is French, English, or a usage error respectively

Source: tests/messages/test_messages.py (test_option_language)
