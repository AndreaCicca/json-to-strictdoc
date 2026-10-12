#!/usr/bin/env python3
"""
Entrypoint for StrictDoc <-> JSON bidirectional parser and converter.
Exposes the full `strictdoc_parser` API (`json_to_sdoc`, `sdoc_to_json`, `parse_sdoc`,
`parse_sgra`, `SDocValidator`, etc.) and runs the CLI when executed directly.
"""

from __future__ import annotations

import sys

from strictdoc_parser import (
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
    SDocParser,
    SDocSyntaxError,
    SDocValidationError,
    SDocValidator,
    SDocWriter,
    ViewElement,
    ViewElementField,
    ViewElementTags,
    create_default_grammar,
    dict_to_grammar,
    dict_to_sdoc,
    json_to_sdoc,
    json_to_sdoc_document,
    json_to_sgra,
    parse_sdoc,
    parse_sgra,
    sdoc_document_to_json,
    sdoc_to_dict,
    sdoc_to_json,
    sgra_to_json,
    write_sdoc,
    write_sgra,
)
from strictdoc_parser.cli import main

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
    "dict_to_grammar",
    "dict_to_sdoc",
    "json_to_sdoc",
    "json_to_sdoc_document",
    "json_to_sgra",
    "main",
    "parse_sdoc",
    "parse_sgra",
    "sdoc_document_to_json",
    "sdoc_to_dict",
    "sdoc_to_json",
    "sgra_to_json",
    "write_sdoc",
    "write_sgra",
]

if __name__ == "__main__":
    sys.exit(main())
