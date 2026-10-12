"""
Comprehensive test suite for the feature-complete StrictDoc parser, validator,
writer, JSON converter, and CLI.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest

from strictdoc_parser import (
    Anchor,
    InlineLink,
    SDocSyntaxError,
    SDocValidationError,
    SDocValidator,
    json_to_sdoc,
    json_to_sgra,
    parse_sdoc,
    parse_sgra,
    parse_text_parts,
    sdoc_to_dict,
    sdoc_to_json,
    sgra_to_json,
    write_sdoc,
)
from strictdoc_parser.cli import main as cli_main


class TestStrictDocParser(unittest.TestCase):
    def test_full_modern_sdoc_roundtrip(self) -> None:
        sdoc_input = """[DOCUMENT]
MID: doc-mid-001
TITLE: Full Specification Document
UID: DOC-001
VERSION: 2.1.0
DATE: 2026-10-12
CLASSIFICATION: Public
PREFIX: REQ-
ROOT: True
OPTIONS:
  ENABLE_MID: True
  RELATION_FIELD: UID
  MARKUP: Markdown
  AUTO_LEVELS: On
  LAYOUT: Website
  VIEW_STYLE: Narrative
  NODE_IN_TOC: True
  DEFAULT_VIEW: MAIN_VIEW
METADATA:
  author: Engineering Team
  project_code: ISO-123
VIEWS:
- ID: MAIN_VIEW
  NAME: Main Engineering View
  TAGS:
  - OBJECT_TYPE: REQUIREMENT
    VISIBLE_FIELDS:
    - NAME: UID
      PLACEMENT: Inline
    - NAME: TITLE
    - NAME: STATEMENT
  HIDDEN_TAGS:
  - TEXT

[GRAMMAR]
ELEMENTS:
- TAG: SECTION
  PROPERTIES:
    IS_COMPOSITE: True
    PREFIX: SEC-
    VIEW_STYLE: Narrative
  FIELDS:
  - TITLE: MID
    TYPE: String
    REQUIRED: False
  - TITLE: UID
    TYPE: String
    REQUIRED: False
  - TITLE: LEVEL
    TYPE: String
    REQUIRED: False
  - TITLE: PREFIX
    TYPE: String
    REQUIRED: False
  - TITLE: TITLE
    TYPE: String
    REQUIRED: True
- TAG: TEXT
  FIELDS:
  - TITLE: MID
    TYPE: String
    REQUIRED: False
  - TITLE: UID
    TYPE: String
    REQUIRED: False
  - TITLE: STATEMENT
    TYPE: String
    REQUIRED: True
- TAG: REQUIREMENT
  PROPERTIES:
    IS_COMPOSITE: False
    PREFIX: REQ-
    VIEW_STYLE: Zebra
  FIELDS:
  - TITLE: MID
    TYPE: String
    REQUIRED: False
  - TITLE: UID
    HUMAN_TITLE: Unique Identifier
    TYPE: String
    REQUIRED: True
  - TITLE: LEVEL
    TYPE: String
    REQUIRED: False
  - TITLE: STATUS
    TYPE: SingleChoice(Draft, Active, "Deprecated (Legacy)")
    REQUIRED: False
  - TITLE: COMP_TAGS
    TYPE: MultipleChoice(Safety, Security, Performance)
    REQUIRED: False
  - TITLE: TAGS
    TYPE: Tag
    REQUIRED: False
  - TITLE: TITLE
    TYPE: String
    REQUIRED: True
  - TITLE: STATEMENT
    TYPE: String
    REQUIRED: True
  - TITLE: RATIONALE
    TYPE: String
    REQUIRED: False
  - TITLE: COMMENT
    TYPE: String
    REQUIRED: False
  RELATIONS:
  - TYPE: Parent
  - TYPE: Parent
    ROLE: Refines
    REVERSE_ROLE: RefinedBy
  - TYPE: Child
    ROLE: Verifies
  - TYPE: File
  - TYPE: File
    ROLE: Implementation
- TAG: COMPOSITE_REQ
  PROPERTIES:
    IS_COMPOSITE: True
  FIELDS:
  - TITLE: MID
    TYPE: String
    REQUIRED: False
  - TITLE: UID
    TYPE: String
    REQUIRED: True
  - TITLE: TITLE
    TYPE: String
    REQUIRED: True
  - TITLE: STATEMENT
    TYPE: String
    REQUIRED: True

[[SECTION]]
MID: sec-mid-1
UID: SEC-01
LEVEL: 1.0
PREFIX: SYS-
TITLE: System Architecture

[TEXT]
MID: txt-mid-1
UID: TXT-01
STATEMENT: >>>
Introductory text referencing [LINK: REQ-001].
[ANCHOR: ANC-01, Architecture Overview]
<<<

[REQUIREMENT]
MID: req-mid-1
UID: REQ-001
LEVEL: 1.1
STATUS: "Deprecated (Legacy)"
COMP_TAGS: Safety, Security
TAGS: Core, ISO26262
TITLE: Primary Safety Requirement
STATEMENT: >>>
The system shall maintain safe operation.
<<<
RATIONALE: >>>
Required for safety certification.
<<<
COMMENT: >>>
First review comment.
<<<
COMMENT: >>>
Second review comment.
<<<
RELATIONS:
- TYPE: Parent
  VALUE: SYS-HIGH-01
- TYPE: Parent
  VALUE: SYS-HIGH-02
  ROLE: Refines
- TYPE: Child
  VALUE: SUB-REQ-01
  ROLE: Verifies
- TYPE: File
  ROLE: Implementation
  FORMAT: Python
  PATH: src/controller.py
  ELEMENT: function
  ID: control_loop
  LINE_RANGE: 10, 45
  HASH: a1b2c3d4

[[COMPOSITE_REQ]]
MID: comp-mid-1
UID: COMP-001
TITLE: Subsystem Composite Requirement
STATEMENT: >>>
High-level composite block.
<<<

[REQUIREMENT]
MID: req-mid-2
UID: REQ-002
STATUS: TBD
TITLE: Nested Child Requirement
STATEMENT: >>>
Nested requirement statement.
<<<

[[/COMPOSITE_REQ]]

[DOCUMENT_FROM_FILE]
FILE: fragment.sdoc

[[/SECTION]]
"""
        doc = parse_sdoc(sdoc_input)
        SDocValidator.validate_document(doc)
        written = write_sdoc(doc)
        self.assertEqual(written, sdoc_input)

        # Round-trip through JSON -> SDoc
        json_str = sdoc_to_json(sdoc_input)
        reconstructed_sdoc = json_to_sdoc(json_str)
        self.assertEqual(reconstructed_sdoc, sdoc_input)

    def test_inline_links_and_anchors_parsing(self) -> None:
        text = (
            "See [LINK: REQ-01] and [LINK: SEC-02] for details.\n"
            "[ANCHOR: ANC-1]\n"
            '[ANCHOR: ANC-2, "Quoted, Title"]\n'
            "[ANCHOR: ANC-3, Unquoted Title]\n"
            "Trailing text."
        )
        parts = parse_text_parts(text)
        links = [p for p in parts if isinstance(p, InlineLink)]
        anchors = [p for p in parts if isinstance(p, Anchor)]
        self.assertEqual([l.value for l in links], ["REQ-01", "SEC-02"])
        self.assertEqual(len(anchors), 3)
        self.assertEqual((anchors[0].value, anchors[0].title), ("ANC-1", None))
        self.assertEqual(
            (anchors[1].value, anchors[1].title), ("ANC-2", "Quoted, Title")
        )
        self.assertEqual(
            (anchors[2].value, anchors[2].title), ("ANC-3", "Unquoted Title")
        )

    def test_legacy_test_json_and_test_sdoc_compatibility(self) -> None:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(repo_root, "test.json"), "r", encoding="utf-8") as f:
            test_json_content = f.read()
        with open(os.path.join(repo_root, "test.sdoc"), "r", encoding="utf-8") as f:
            test_sdoc_content = f.read()

        # 1. Convert test.json to modern SDoc
        modern_sdoc = json_to_sdoc(test_json_content, legacy=False)
        self.assertIn("[[SECTION]]", modern_sdoc)
        self.assertIn("[[/SECTION]]", modern_sdoc)
        self.assertIn("[TEXT]\nSTATEMENT: >>>", modern_sdoc)
        self.assertIn("[REQUIREMENT]\nUID: TEST-01", modern_sdoc)

        # 2. Convert test.json to legacy SDoc
        legacy_sdoc = json_to_sdoc(test_json_content, legacy=True)
        self.assertIn("[SECTION]", legacy_sdoc)
        self.assertIn("[/SECTION]", legacy_sdoc)
        self.assertIn("[FREETEXT]", legacy_sdoc)
        self.assertIn("[/FREETEXT]", legacy_sdoc)

        # 3. Parse existing test.sdoc and convert back to legacy JSON
        parsed_legacy = parse_sdoc(test_sdoc_content)
        SDocValidator.validate_document(parsed_legacy)
        legacy_dict = sdoc_to_dict(parsed_legacy, legacy_json=True)
        self.assertEqual(legacy_dict["TITLE"], "Test Documentation")
        self.assertEqual(len(legacy_dict["SECTIONS"]), 1)
        self.assertEqual(
            legacy_dict["SECTIONS"][0]["REQUIREMENTS"][0]["UID"], "TEST-01"
        )

    def test_sgra_standalone_roundtrip(self) -> None:
        sgra_text = """[GRAMMAR]
ELEMENTS:
- TAG: REQUIREMENT
  PROPERTIES:
    IS_COMPOSITE: False
    PREFIX: REQ-
    VIEW_STYLE: Table
  FIELDS:
  - TITLE: UID
    TYPE: String
    REQUIRED: True
  - TITLE: TITLE
    TYPE: String
    REQUIRED: True
  - TITLE: STATEMENT
    TYPE: String
    REQUIRED: True
  RELATIONS:
  - TYPE: Parent
    ROLE: Refines
    REVERSE_ROLE: RefinedBy
"""
        json_str = sgra_to_json(sgra_text)
        reconstructed = json_to_sgra(json_str)
        # Note: when ELEMENTS are parsed, default TEXT element is prepended if absent
        self.assertIn("- TAG: REQUIREMENT", reconstructed)
        self.assertIn("REVERSE_ROLE: RefinedBy", reconstructed)

    def test_unordered_json_fields_are_automatically_ordered_by_grammar(self) -> None:
        unordered_json = {
            "TITLE": "Field Order Test",
            "SECTIONS": [
                {
                    "TITLE": "Sec 1",
                    "UID": "SEC-1",
                    "REQUIREMENTS": [
                        {
                            "RATIONALE": "Why it matters",
                            "STATEMENT": "What it does",
                            "TITLE": "Req Title",
                            "UID": "REQ-1",
                            "STATUS": "Active",
                        }
                    ],
                }
            ],
        }
        sdoc_out = json_to_sdoc(unordered_json)
        uid_pos = sdoc_out.index("UID: REQ-1")
        status_pos = sdoc_out.index("STATUS: Active")
        title_pos = sdoc_out.index("TITLE: Req Title")
        stmt_pos = sdoc_out.index("STATEMENT: >>>")
        rat_pos = sdoc_out.index("RATIONALE: >>>")
        self.assertTrue(uid_pos < status_pos < title_pos < stmt_pos < rat_pos)

    def test_validation_errors(self) -> None:
        # 1. Wrong field order in raw SDoc
        bad_order_sdoc = """[DOCUMENT]
TITLE: Doc

[REQUIREMENT]
TITLE: Title before UID
UID: REQ-1
"""
        doc = parse_sdoc(bad_order_sdoc)
        with self.assertRaises(SDocValidationError):
            SDocValidator.validate_document(doc, strict_field_order=True)

        # 2. Reserved single-line field as multiline
        bad_multiline_sdoc = """[DOCUMENT]
TITLE: Doc

[REQUIREMENT]
UID: >>>
REQ-1
<<<
"""
        with self.assertRaises(SDocSyntaxError):
            parse_sdoc(bad_multiline_sdoc)

        # 3. Duplicate UID
        dup_uid_sdoc = """[DOCUMENT]
TITLE: Doc

[REQUIREMENT]
UID: REQ-1
TITLE: First

[REQUIREMENT]
UID: REQ-1
TITLE: Second
"""
        doc_dup = parse_sdoc(dup_uid_sdoc)
        with self.assertRaises(SDocValidationError):
            SDocValidator.validate_document(doc_dup)

        # 4. Invalid SingleChoice value
        bad_choice_sdoc = """[DOCUMENT]
TITLE: Doc

[GRAMMAR]
ELEMENTS:
- TAG: REQUIREMENT
  FIELDS:
  - TITLE: STATUS
    TYPE: SingleChoice(Draft, Active)
    REQUIRED: True

[REQUIREMENT]
STATUS: InvalidStatus
"""
        doc_choice = parse_sdoc(bad_choice_sdoc)
        with self.assertRaises(SDocValidationError):
            SDocValidator.validate_document(doc_choice)

        # 5. Unsafe IMPORT_FROM_FILE
        bad_import_sdoc = """[DOCUMENT]
TITLE: Doc

[GRAMMAR]
IMPORT_FROM_FILE: ../secret.sgra
"""
        doc_imp = parse_sdoc(bad_import_sdoc)
        with self.assertRaises(SDocValidationError):
            SDocValidator.validate_document(doc_imp)

    def test_cli_end_to_end(self) -> None:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        test_json_path = os.path.join(repo_root, "test.json")

        with tempfile.TemporaryDirectory() as tmpdir:
            out_sdoc = os.path.join(tmpdir, "out.sdoc")
            out_json = os.path.join(tmpdir, "out.json")

            # JSON -> SDOC
            rc1 = cli_main([test_json_path, out_sdoc])
            self.assertEqual(rc1, 0)
            self.assertTrue(os.path.isfile(out_sdoc))

            # Validate SDOC
            rc2 = cli_main(["--validate", out_sdoc])
            self.assertEqual(rc2, 0)

            # SDOC -> JSON
            rc3 = cli_main([out_sdoc, out_json])
            self.assertEqual(rc3, 0)
            with open(out_json, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.assertEqual(loaded["TITLE"], "Test Documentation")


if __name__ == "__main__":
    unittest.main()

