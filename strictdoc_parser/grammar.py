"""
StrictDoc Grammar Specification, Constants, Default Grammars, and Text Part Parsers.
Faithfully implements the rules from:
- strictdoc/backend/sdoc/grammar/grammar.py
- strictdoc/backend/sdoc/grammar/grammar_grammar.py
- strictdoc/backend/sdoc/grammar/type_system.py
- strictdoc/backend/sdoc/models/document_grammar.py
- strictdoc/backend/sdoc/models/grammar_element.py
"""

from __future__ import annotations

import re
from typing import List, Optional

from .models import (
    Anchor,
    DocumentGrammar,
    GrammarElement,
    GrammarElementField,
    GrammarElementRelation,
    InlineLink,
    TextPart,
)

# Official StrictDoc regular expressions
REGEX_UID_PATTERN = r"([\w]+[\w()\-\/.: ]*)"
REGEX_FIELD_NAME_PATTERN = r"[A-Z]+[A-Za-z0-9_\-]*"
REGEX_NODE_NAME_PATTERN = r"[A-Z]+(_[A-Z]+)*"
REGEX_METADATA_KEY_PATTERN = r"[a-zA-Z_][a-zA-Z0-9_-]*"
REGEX_FILE_FORMAT_PATTERN = r"Sourcecode|Python|[A-Z]+[A-Z_]*"

RE_UID = re.compile(rf"^{REGEX_UID_PATTERN}$")
RE_FIELD_NAME = re.compile(rf"^{REGEX_FIELD_NAME_PATTERN}$")
RE_NODE_NAME = re.compile(rf"^{REGEX_NODE_NAME_PATTERN}$")
RE_METADATA_KEY = re.compile(rf"^{REGEX_METADATA_KEY_PATTERN}$")
RE_FILE_FORMAT = re.compile(rf"^{REGEX_FILE_FORMAT_PATTERN}$")

# Inline Link and Anchor patterns inside TextPart
RE_INLINE_LINK = re.compile(rf"\[LINK: (?P<uid>{REGEX_UID_PATTERN})\]")
RE_ANCHOR = re.compile(
    rf"(?m)^\[ANCHOR: (?P<uid>{REGEX_UID_PATTERN})(?:, (?P<title>\"[^\"\r\n]+\"|[^,\]\r\n]+))?\](?=\Z|\r?\n)"
)
RE_TEXT_TOKEN = re.compile(
    rf"(?m)(?P<anchor>^\[ANCHOR: {REGEX_UID_PATTERN}(?:, (?:\"[^\"\r\n]+\"|[^,\]\r\n]+))?\](?=\Z|\r?\n))|(?P<link>\[LINK: {REGEX_UID_PATTERN}\])"
)

# Choice option parser: /(["])[^,]+\1|[^,()"]+/
RE_CHOICE_OPTION = re.compile(r'("(?:[^,]+)"|[^,()"]+)')

# Comma-separated multi-choice / tag validation
RE_COMMA_SEPARATED = re.compile(r"^[^\s,][^,]*(?:, [^\s,][^,]*)*$")

# Reserved keywords and enumerations
RESERVED_DOCUMENT_KEYWORDS = frozenset({"DOCUMENT", "GRAMMAR"})
RESERVED_NON_COMPOSITE_KEYWORDS = frozenset(
    {"DOCUMENT", "GRAMMAR", "SECTION", "DOCUMENT_FROM_FILE"}
)

VALID_MARKUP_CHOICES = ("RST", "Text", "HTML", "Markdown")
VALID_VIEW_STYLE_CHOICES = (
    "Plain",
    "Inline",
    "Simple",
    "Narrative",
    "Table",
    "Zebra",
)
VALID_AUTO_LEVELS_CHOICES = ("On", "Off")
VALID_LAYOUT_CHOICES = ("Default", "Website")
VALID_BOOLEAN_CHOICES = ("True", "False")
VALID_REQUIREMENT_STATUS = ("Draft", "Active", "Deleted")
VALID_RELATION_TYPES = ("Parent", "Child", "File")
VALID_FIELD_TYPES = ("String", "SingleChoice", "MultipleChoice", "Tag")

RESERVED_SINGLELINE_FIELDS = frozenset(
    {
        "MID",
        "UID",
        "PREFIX",
        "REQ_PREFIX",
        "LEVEL",
        "STATUS",
        "TAGS",
        "TITLE",
    }
)

RESERVED_NON_META_FIELDS = frozenset(
    {
        "TITLE",
        "STATEMENT",
        "DESCRIPTION",
        "CONTENT",
        "COMMENT",
        "RATIONALE",
    }
)

CONTENT_FIELD_ALIASES = ("STATEMENT", "DESCRIPTION", "CONTENT")


def create_default_section_element(enable_mid: bool = False) -> GrammarElement:
    """Creates the built-in default `SECTION` grammar element."""
    fields: List[GrammarElementField] = []
    if enable_mid:
        fields.append(
            GrammarElementField(title="MID", gef_type="String", required=False)
        )
    fields.extend(
        [
            GrammarElementField(title="UID", gef_type="String", required=False),
            GrammarElementField(title="LEVEL", gef_type="String", required=False),
            GrammarElementField(title="PREFIX", gef_type="String", required=False),
            GrammarElementField(title="TITLE", gef_type="String", required=True),
        ]
    )
    return GrammarElement(
        tag="SECTION",
        property_is_composite=True,
        fields=fields,
        relations=[],
    )


def create_default_text_element(enable_mid: bool = False) -> GrammarElement:
    """Creates the built-in default `TEXT` grammar element."""
    fields: List[GrammarElementField] = []
    if enable_mid:
        fields.append(
            GrammarElementField(title="MID", gef_type="String", required=False)
        )
    fields.extend(
        [
            GrammarElementField(title="UID", gef_type="String", required=False),
            GrammarElementField(title="STATEMENT", gef_type="String", required=True),
        ]
    )
    return GrammarElement(
        tag="TEXT",
        property_is_composite=None,
        fields=fields,
        relations=[],
    )


def create_default_requirement_element(
    enable_mid: bool = False, include_child_relation: bool = True
) -> GrammarElement:
    """Creates the built-in default `REQUIREMENT` grammar element."""
    fields: List[GrammarElementField] = []
    if enable_mid:
        fields.append(
            GrammarElementField(title="MID", gef_type="String", required=False)
        )
    fields.extend(
        [
            GrammarElementField(title="UID", gef_type="String", required=False),
            GrammarElementField(title="LEVEL", gef_type="String", required=False),
            GrammarElementField(title="STATUS", gef_type="String", required=False),
            GrammarElementField(title="TAGS", gef_type="String", required=False),
            GrammarElementField(title="TITLE", gef_type="String", required=False),
            GrammarElementField(title="STATEMENT", gef_type="String", required=False),
            GrammarElementField(title="RATIONALE", gef_type="String", required=False),
            GrammarElementField(title="COMMENT", gef_type="String", required=False),
        ]
    )
    relations: List[GrammarElementRelation] = [
        GrammarElementRelation(relation_type="Parent"),
    ]
    if include_child_relation:
        relations.append(GrammarElementRelation(relation_type="Child"))
    relations.append(GrammarElementRelation(relation_type="File"))

    return GrammarElement(
        tag="REQUIREMENT",
        property_is_composite=None,
        fields=fields,
        relations=relations,
    )


def create_default_grammar(
    enable_mid: bool = False, include_child_relation: bool = True
) -> DocumentGrammar:
    """Creates the default DocumentGrammar (`SECTION`, `TEXT`, `REQUIREMENT`)."""
    return DocumentGrammar(
        elements=[
            create_default_section_element(enable_mid=enable_mid),
            create_default_text_element(enable_mid=enable_mid),
            create_default_requirement_element(
                enable_mid=enable_mid,
                include_child_relation=include_child_relation,
            ),
        ],
        import_from_file=None,
        is_default=True,
    )


def is_field_multiline(
    grammar_element: Optional[GrammarElement],
    field_name: str,
    value: str,
    explicit_multiline: Optional[bool] = None,
) -> bool:
    """
    Determines whether a field should be formatted as multiline (`>>> ... <<<`)
    according to StrictDoc's `GrammarElement.is_field_idx_multiline` rules:
    1. Reserved single-line fields (`MID`, `UID`, `PREFIX`, `LEVEL`, `STATUS`, `TAGS`, `TITLE`)
       can never be multiline.
    2. If `value` contains a newline, it must be multiline.
    3. If `explicit_multiline` is explicitly set (e.g. from parsed SDoc), respect it
       unless forbidden by grammar (choice/tag or reserved single-line).
    4. Using the grammar element's field list:
       - Non-String fields (`SingleChoice`, `MultipleChoice`, `Tag`) are never multiline.
       - Any field at or after `STATEMENT`/`DESCRIPTION`/`CONTENT`, or after `TITLE`
         (such as `RATIONALE`, `COMMENT`, etc.) is multiline by default.
    """
    if field_name in RESERVED_SINGLELINE_FIELDS:
        return False

    if grammar_element is not None and field_name in grammar_element.fields_map:
        gf = grammar_element.fields_map[field_name]
        if gf.gef_type != "String":
            return False

    if "\n" in value:
        return True

    if explicit_multiline is not None:
        return explicit_multiline

    if grammar_element is not None:
        titles = grammar_element.get_field_titles()
        if field_name in titles:
            field_idx = titles.index(field_name)
            multiline_idx = -1
            for alias in CONTENT_FIELD_ALIASES:
                if alias in titles:
                    multiline_idx = titles.index(alias)
                    break
            if multiline_idx == -1:
                if "TITLE" in titles:
                    multiline_idx = titles.index("TITLE") + 1
                else:
                    multiline_idx = -1
            return multiline_idx <= field_idx

    # Fallback when custom field is not in grammar_element
    if field_name in RESERVED_NON_META_FIELDS and field_name != "TITLE":
        return True
    return False


def parse_text_parts(text: str) -> List[TextPart]:
    """
    Parses a single-line or multi-line string into `TextPart` items:
    - `str` (NormalString)
    - `InlineLink` (`[LINK: UID]`)
    - `Anchor` (`^[ANCHOR: UID]` or `^[ANCHOR: UID, Title]`)
    """
    if not text:
        return []

    parts: List[TextPart] = []
    last_end = 0

    for match in RE_TEXT_TOKEN.finditer(text):
        start, end = match.span()
        if start > last_end:
            parts.append(text[last_end:start])

        anchor_str = match.group("anchor")
        link_str = match.group("link")

        if anchor_str is not None:
            m_anchor = RE_ANCHOR.match(anchor_str)
            if m_anchor:
                uid = m_anchor.group("uid")
                title = m_anchor.group("title")
                if title is not None and len(title) >= 2 and title.startswith('"') and title.endswith('"'):
                    title = title[1:-1]
                parts.append(Anchor(value=uid, title=title))
            else:
                parts.append(anchor_str)
        elif link_str is not None:
            m_link = RE_INLINE_LINK.match(link_str)
            if m_link:
                parts.append(InlineLink(value=m_link.group("uid")))
            else:
                parts.append(link_str)

        last_end = end

    if last_end < len(text):
        parts.append(text[last_end:])

    return parts


def parse_choice_options(options_str: str) -> List[str]:
    """
    Parses the options inside `SingleChoice(...)` or `MultipleChoice(...)`.
    Supports quoted options with parentheses as defined in `type_system.py`.
    """
    raw_parts = [p.strip() for p in options_str.split(", ")]
    options: List[str] = []
    for part in raw_parts:
        if not part:
            continue
        if len(part) >= 2 and part.startswith('"') and part.endswith('"'):
            options.append(part[1:-1])
        else:
            options.append(part)
    return options


def format_choice_options(options: List[str]) -> str:
    """
    Formats options for `SingleChoice(...)` or `MultipleChoice(...)`, quoting
    options that contain `(` or `)` as in `GrammarElementFieldSingleChoice.get_unprocessed_options`.
    """
    formatted: List[str] = []
    for opt in options:
        if any(ch in opt for ch in ("(", ")")):
            formatted.append(f'"{opt}"')
        else:
            formatted.append(opt)
    return ", ".join(formatted)

