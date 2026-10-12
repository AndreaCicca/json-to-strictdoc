"""
StrictDoc Feature-Complete Parser & Bidirectional JSON <-> SDOC/SGRA Converter.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Union

from .grammar import (
    create_default_grammar,
    create_default_requirement_element,
    create_default_section_element,
    create_default_text_element,
    is_field_multiline,
    parse_choice_options,
    parse_text_parts,
)
from .json_converter import (
    dict_to_grammar,
    dict_to_sdoc,
    json_to_sdoc_document,
    sdoc_document_to_json,
    sdoc_to_dict,
)
from .models import (
    Anchor,
    ChildReqReference,
    DocumentConfig,
    DocumentFromFile,
    DocumentGrammar,
    DocumentOptions,
    FileReference,
    GrammarElement,
    GrammarElementField,
    GrammarElementRelation,
    InlineLink,
    ParentReqReference,
    Reference,
    SDocDocument,
    SDocElement,
    SDocNode,
    SDocNodeField,
    ViewElement,
    ViewElementField,
    ViewElementTags,
)
from .parser import SDocParser, SDocSyntaxError, parse_sdoc, parse_sgra
from .validator import SDocValidationError, SDocValidator
from .writer import SDocWriter, write_sdoc, write_sgra


def json_to_sdoc(
    json_data: Union[str, Dict[str, Any]],
    *,
    legacy: bool = False,
    validate: bool = True,
) -> str:
    """
    Converts a JSON string or dictionary into a formatted `.sdoc` string.
    By default emits modern StrictDoc syntax (`[[SECTION]]`, `[TEXT]`, `[[COMPOSITE_NODE]]`).
    Pass `legacy=True` to emit `[SECTION] ... [/SECTION]` and `[FREETEXT] ... [/FREETEXT]`.
    """
    doc = json_to_sdoc_document(json_data)
    if validate:
        # When converting from JSON, fields on dicts may be in arbitrary key order;
        # SDocWriter automatically orders fields according to the grammar!
        SDocValidator.validate_document(
            doc, strict_field_order=False, allow_legacy=True
        )
    sdoc_text = write_sdoc(doc, legacy=legacy)
    if validate:
        # Also verify the generated output satisfies strict field order
        parsed_back = parse_sdoc(sdoc_text, allow_legacy_sections=True)
        SDocValidator.validate_document(
            parsed_back, strict_field_order=True, allow_legacy=True
        )
    return sdoc_text


def sdoc_to_json(
    sdoc_text: str,
    *,
    indent: int = 4,
    legacy_json: bool = False,
    validate: bool = True,
    allow_legacy_sections: bool = True,
) -> str:
    """
    Parses a `.sdoc` string, optionally validates it against StrictDoc semantic rules,
    and serializes it to a formatted JSON string.
    """
    doc = parse_sdoc(sdoc_text, allow_legacy_sections=allow_legacy_sections)
    if validate:
        SDocValidator.validate_document(
            doc,
            strict_field_order=True,
            allow_legacy=allow_legacy_sections,
        )
    return sdoc_document_to_json(doc, indent=indent, legacy_json=legacy_json)


def sgra_to_json(
    sgra_text: str,
    *,
    indent: int = 4,
    validate: bool = True,
) -> str:
    """Parses a `.sgra` grammar string and converts it to a JSON string."""
    grammar = parse_sgra(sgra_text)
    if validate:
        SDocValidator.validate_grammar(grammar)
    return json.dumps(grammar.to_dict(), indent=indent, ensure_ascii=False) + "\n"


def json_to_sgra(
    json_data: Union[str, Dict[str, Any]],
    *,
    validate: bool = True,
) -> str:
    """Converts a JSON grammar string or dict into a `.sgra` string."""
    parsed = json.loads(json_data) if isinstance(json_data, str) else json_data
    if "GRAMMAR" in parsed and isinstance(parsed["GRAMMAR"], dict):
        parsed = parsed["GRAMMAR"]
    grammar = dict_to_grammar(parsed)
    if validate:
        SDocValidator.validate_grammar(grammar)
    return write_sgra(grammar)


__all__ = [
    "Anchor",
    "ChildReqReference",
    "DocumentConfig",
    "DocumentFromFile",
    "DocumentGrammar",
    "DocumentOptions",
    "FileReference",
    "GrammarElement",
    "GrammarElementField",
    "GrammarElementRelation",
    "InlineLink",
    "ParentReqReference",
    "Reference",
    "SDocDocument",
    "SDocElement",
    "SDocNode",
    "SDocNodeField",
    "SDocParser",
    "SDocSyntaxError",
    "SDocValidationError",
    "SDocValidator",
    "SDocWriter",
    "ViewElement",
    "ViewElementField",
    "ViewElementTags",
    "create_default_grammar",
    "create_default_requirement_element",
    "create_default_section_element",
    "create_default_text_element",
    "dict_to_grammar",
    "dict_to_sdoc",
    "is_field_multiline",
    "json_to_sdoc",
    "json_to_sdoc_document",
    "json_to_sgra",
    "parse_choice_options",
    "parse_sdoc",
    "parse_sgra",
    "parse_text_parts",
    "sdoc_document_to_json",
    "sdoc_to_dict",
    "sdoc_to_json",
    "sgra_to_json",
    "write_sdoc",
    "write_sgra",
]

