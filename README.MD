# JSON to StrictDoc

A lightweight, zero-dependency bidirectional converter and parser between **JSON** and **StrictDoc** (`.sdoc` / `.sgra`).

## Features

- **Bidirectional Conversion**: Convert `JSON <-> SDOC` and `JSON <-> SGRA`.
- **Full StrictDoc Support**: Document config (`OPTIONS`, `METADATA`, `VIEWS`), custom `[GRAMMAR]`, composite nodes (`[[SECTION]]`, `[[NODE]]`), standard nodes (`[TEXT]`, `[REQUIREMENT]`), `[DOCUMENT_FROM_FILE]`, relations (`Parent`, `Child`, `File`), and inline `[LINK]` / `[ANCHOR]`.
- **Legacy Compatibility**: Supports legacy `[SECTION]` and `[FREETEXT]` blocks via `--legacy` and `--legacy-json`.
- **Built-in Validation**: Validates syntax, field order, required fields, choice/tag types, and unique `UID`s.

## Installation

```bash
pip install json-to-strictdoc
```

## CLI Usage

```bash
# Convert JSON to SDOC (modern StrictDoc syntax)
json-to-strictdoc test.json test.sdoc

# Convert JSON to SDOC (legacy [SECTION] / [FREETEXT] syntax)
json-to-strictdoc --legacy test.json test_legacy.sdoc

# Convert SDOC to JSON
json-to-strictdoc test.sdoc output.json

# Convert SDOC to compact JSON (SECTIONS / REQUIREMENTS / FREETEXT)
json-to-strictdoc --legacy-json test.sdoc output_legacy.json

# Validate an .sdoc, .sgra, or .json file
json-to-strictdoc --validate test.sdoc
```

*(You can also run the script directly with `python3 strictdock-parser.py <input> <output>`).*

## Python API

```python
from strictdoc_parser import json_to_sdoc, sdoc_to_json, parse_sdoc, SDocValidator

# JSON -> SDOC
sdoc_text = json_to_sdoc(json_string)

# SDOC -> JSON
json_text = sdoc_to_json(sdoc_text)

# Parse into AST and validate
doc = parse_sdoc(sdoc_text)
SDocValidator.validate_document(doc)
```

## Example

Input (`test.json`):

```json
{
    "TITLE": "Test Documentation",
    "SECTIONS": [
        {
            "TITLE": "System Overview",
            "FREETEXT": "This documentation is used to test the script",
            "REQUIREMENTS": [
                {
                    "UID": "TEST-01",
                    "TITLE": "Test the script",
                    "STATEMENT": "This is a Test",
                    "RATIONALE": "This is a test"
                }
            ]
        }
    ]
}
```

Generated Output (`test.sdoc`):

```sdoc
[DOCUMENT]
TITLE: Test Documentation

[[SECTION]]
TITLE: System Overview

[TEXT]
STATEMENT: >>>
This documentation is used to test the script
<<<

[REQUIREMENT]
UID: TEST-01
TITLE: Test the script
STATEMENT: >>>
This is a Test
<<<
RATIONALE: >>>
This is a test
<<<

[[/SECTION]]
```