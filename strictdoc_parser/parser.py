"""
Complete parser for StrictDoc (.sdoc) and Grammar (.sgra) files.
Supports 100% of the official StrictDoc grammar specification plus legacy constructs:
- [DOCUMENT], MID, TITLE, UID, VERSION, DATE, CLASSIFICATION, PREFIX / REQ_PREFIX, ROOT
- OPTIONS (ENABLE_MID, RELATION_FIELD, MARKUP, AUTO_LEVELS, LAYOUT,
  VIEW_STYLE / REQUIREMENT_STYLE, NODE_IN_TOC / REQUIREMENT_IN_TOC, DEFAULT_VIEW)
- METADATA (custom key-value pairs)
- VIEWS (ID, NAME, TAGS -> OBJECT_TYPE -> VISIBLE_FIELDS -> NAME/PLACEMENT, HIDDEN_TAGS)
- [GRAMMAR] (IMPORT_FROM_FILE or ELEMENTS -> TAG, PROPERTIES, FIELDS, RELATIONS)
- [[COMPOSITE_NODE]] ... [[/COMPOSITE_NODE]] (including modern [[SECTION]] ... [[/SECTION]])
- [NODE] (including [TEXT], [REQUIREMENT], and any custom grammar node)
- [DOCUMENT_FROM_FILE]
- Legacy [SECTION] ... [/SECTION], [FREETEXT] ... [/FREETEXT],
  [COMPOSITE_REQUIREMENT] ... [/COMPOSITE_REQUIREMENT], and REFS:
- Inline [LINK: UID] and ^[ANCHOR: UID, Title] inside text fields
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from .grammar import (
    RE_FIELD_NAME,
    RE_FILE_FORMAT,
    RE_METADATA_KEY,
    RE_NODE_NAME,
    RE_UID,
    RESERVED_SINGLELINE_FIELDS,
    VALID_AUTO_LEVELS_CHOICES,
    VALID_BOOLEAN_CHOICES,
    VALID_LAYOUT_CHOICES,
    VALID_MARKUP_CHOICES,
    VALID_RELATION_TYPES,
    VALID_VIEW_STYLE_CHOICES,
    create_default_grammar,
    create_default_text_element,
    parse_choice_options,
    parse_text_parts,
)
from .models import (
    ChildReqReference,
    DocumentConfig,
    DocumentFromFile,
    DocumentGrammar,
    DocumentOptions,
    FileReference,
    GrammarElement,
    GrammarElementField,
    GrammarElementRelation,
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


class SDocSyntaxError(ValueError):
    """Raised when an SDoc or SGra file violates the StrictDoc syntax grammar."""

    def __init__(
        self,
        message: str,
        line: Optional[int] = None,
        column: Optional[int] = None,
        line_text: Optional[str] = None,
    ) -> None:
        self.raw_message = message
        self.line = line
        self.column = column
        self.line_text = line_text
        loc = f" (line {line}" + (f", col {column})" if column else ")") if line else ""
        ctx = f": {line_text!r}" if line_text is not None else ""
        super().__init__(f"SDoc syntax error{loc}: {message}{ctx}")


_RE_COMPOSITE_OPEN = re.compile(r"^\[\[(?P<tag>[A-Z]+(?:_[A-Z]+)*)\]\]$")
_RE_COMPOSITE_CLOSE = re.compile(r"^\[\[/(?P<tag>[A-Z]+(?:_[A-Z]+)*)\]\]$")
_RE_NODE_OPEN = re.compile(r"^\[(?P<tag>[A-Z]+(?:_[A-Z]+)*)\]$")
_RE_NODE_CLOSE = re.compile(r"^\[/(?P<tag>[A-Z]+(?:_[A-Z]+)*)\]$")
_RE_SINGLE_CHOICE_TYPE = re.compile(r"^SingleChoice\((?P<opts>.+)\)$")
_RE_MULTIPLE_CHOICE_TYPE = re.compile(r"^MultipleChoice\((?P<opts>.+)\)$")


class _LineReader:
    """Helper cursor over 1-indexed source lines."""

    def __init__(self, text: str) -> None:
        # Normalize CRLF / CR to LF
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        self.lines: List[str] = normalized.split("\n")
        # If text ends with a trailing newline, split("\n") produces a final ""
        if normalized.endswith("\n") and self.lines and self.lines[-1] == "":
            self.lines.pop()
        self.idx: int = 0
        self.total: int = len(self.lines)

    def eof(self) -> bool:
        return self.idx >= self.total

    def peek(self) -> Optional[str]:
        if self.idx >= self.total:
            return None
        return self.lines[self.idx]

    def peek_line_num(self) -> int:
        return self.idx + 1

    def next_line(self) -> Tuple[int, str]:
        if self.idx >= self.total:
            raise SDocSyntaxError("Unexpected end of file", line=self.total)
        line_num = self.idx + 1
        line = self.lines[self.idx]
        self.idx += 1
        return line_num, line

    def skip_blank_lines(self) -> int:
        count = 0
        while not self.eof() and self.lines[self.idx] == "":
            self.idx += 1
            count += 1
        return count

    def error(self, msg: str, line_num: Optional[int] = None) -> SDocSyntaxError:
        ln = line_num if line_num is not None else self.peek_line_num()
        txt = self.lines[ln - 1] if 1 <= ln <= len(self.lines) else None
        return SDocSyntaxError(msg, line=ln, line_text=txt)


def _require_non_empty_single_line(
    value: str, field_name: str, reader: _LineReader, line_num: int
) -> str:
    """Enforces StrictDoc Rule #3: SingleLineString must start with a non-space character and not be `>>>`."""
    if not value or value[0].isspace():
        raise reader.error(
            f"Field '{field_name}' must be a non-empty single-line string starting with a non-whitespace character",
            line_num,
        )
    if value == ">>>":
        raise reader.error(
            f"Field '{field_name}' cannot use multiline '>>>' syntax",
            line_num,
        )
    return value


def _parse_boolean(
    value: str, field_name: str, reader: _LineReader, line_num: int
) -> bool:
    if value not in VALID_BOOLEAN_CHOICES:
        raise reader.error(
            f"Field '{field_name}' must be 'True' or 'False', got '{value}'",
            line_num,
        )
    return value == "True"


class SDocParser:
    """Parser for `.sdoc` documents and `.sgra` grammar files."""

    def __init__(self, *, allow_legacy_sections: bool = True) -> None:
        self.allow_legacy_sections = allow_legacy_sections

    def parse_sdoc(self, text: str) -> SDocDocument:
        reader = _LineReader(text)
        reader.skip_blank_lines()
        if reader.eof():
            raise SDocSyntaxError("Empty SDoc document", line=1)

        line_num, first_line = reader.next_line()
        if first_line != "[DOCUMENT]":
            raise reader.error(
                "Expected '[DOCUMENT]' at the start of the file", line_num
            )

        mid, title, config, views = self._parse_document_header(reader)

        # Check for optional [GRAMMAR]
        saved_idx = reader.idx
        reader.skip_blank_lines()
        grammar: Optional[DocumentGrammar] = None
        if not reader.eof() and reader.peek() == "[GRAMMAR]":
            grammar = self._parse_grammar_block(
                reader, enable_mid=config.enable_mid
            )
        else:
            reader.idx = saved_idx

        if grammar is None:
            grammar = create_default_grammar(enable_mid=config.enable_mid)

        # Parse document body (section_contents)
        section_contents = self._parse_section_contents(
            reader, closing_tag=None, is_legacy_close=False
        )

        reader.skip_blank_lines()
        if not reader.eof():
            raise reader.error(
                f"Unexpected content at top level: {reader.peek()!r}"
            )

        return SDocDocument(
            title=title,
            mid=mid,
            config=config,
            views=views,
            grammar=grammar,
            section_contents=section_contents,
        )

    def parse_sgra(self, text: str, *, enable_mid: bool = False) -> DocumentGrammar:
        reader = _LineReader(text)
        reader.skip_blank_lines()
        if reader.eof():
            raise SDocSyntaxError("Empty SGra grammar file", line=1)

        grammar = self._parse_grammar_block(reader, enable_mid=enable_mid)
        reader.skip_blank_lines()
        if not reader.eof():
            raise reader.error(
                f"Unexpected trailing content in grammar file: {reader.peek()!r}"
            )
        return grammar

    def _parse_document_header(
        self, reader: _LineReader
    ) -> Tuple[Optional[str], str, DocumentConfig, List[ViewElement]]:
        mid: Optional[str] = None
        title: Optional[str] = None
        config = DocumentConfig()
        views: List[ViewElement] = []

        # Parse MID and TITLE (and config fields)
        while not reader.eof():
            line = reader.peek()
            assert line is not None
            if line == "" or line.startswith("["):
                break

            line_num, line = reader.next_line()
            if line.startswith("MID: "):
                if mid is not None:
                    raise reader.error("Duplicate 'MID' in [DOCUMENT]", line_num)
                mid = _require_non_empty_single_line(
                    line[len("MID: ") :], "MID", reader, line_num
                )
            elif line.startswith("TITLE: "):
                if title is not None:
                    raise reader.error("Duplicate 'TITLE' in [DOCUMENT]", line_num)
                title = _require_non_empty_single_line(
                    line[len("TITLE: ") :], "TITLE", reader, line_num
                )
            elif line.startswith("UID: "):
                uid_val = line[len("UID: ") :]
                if not RE_UID.match(uid_val):
                    raise reader.error(
                        f"Invalid UID format in [DOCUMENT]: '{uid_val}'", line_num
                    )
                config.uid = uid_val
            elif line.startswith("VERSION: "):
                config.version = _require_non_empty_single_line(
                    line[len("VERSION: ") :], "VERSION", reader, line_num
                )
            elif line.startswith("DATE: "):
                config.date = _require_non_empty_single_line(
                    line[len("DATE: ") :], "DATE", reader, line_num
                )
            elif line.startswith("CLASSIFICATION: "):
                config.classification = _require_non_empty_single_line(
                    line[len("CLASSIFICATION: ") :],
                    "CLASSIFICATION",
                    reader,
                    line_num,
                )
            elif line.startswith("PREFIX: ") or line.startswith("REQ_PREFIX: "):
                tag, val = line.split(": ", 1)
                config.prefix_tag = tag
                config.prefix = _require_non_empty_single_line(
                    val, tag, reader, line_num
                )
            elif line.startswith("ROOT: "):
                config.root = _parse_boolean(
                    line[len("ROOT: ") :], "ROOT", reader, line_num
                )
            elif line == "OPTIONS:":
                config.options = self._parse_document_options(reader)
            elif line == "METADATA:":
                config.metadata = self._parse_document_metadata(reader)
            elif line == "VIEWS:":
                views = self._parse_document_views(reader)
            else:
                raise reader.error(
                    f"Unrecognized [DOCUMENT] header line: {line!r}", line_num
                )

        if title is None:
            raise reader.error("[DOCUMENT] is missing required 'TITLE' field", 1)

        return mid, title, config, views

    def _parse_document_options(self, reader: _LineReader) -> DocumentOptions:
        opts = DocumentOptions()
        while not reader.eof():
            line = reader.peek()
            assert line is not None
            if not line.startswith("  "):
                break
            line_num, line = reader.next_line()
            stripped = line[2:]
            if ": " not in stripped:
                raise reader.error(
                    f"Malformed option in OPTIONS block: {line!r}", line_num
                )
            key, val = stripped.split(": ", 1)
            if key == "ENABLE_MID":
                opts.enable_mid = _parse_boolean(val, key, reader, line_num)
            elif key == "RELATION_FIELD":
                opts.relation_field = _require_non_empty_single_line(
                    val, key, reader, line_num
                )
            elif key == "MARKUP":
                if val not in VALID_MARKUP_CHOICES:
                    raise reader.error(
                        f"Invalid MARKUP option '{val}'. Expected one of {VALID_MARKUP_CHOICES}",
                        line_num,
                    )
                opts.markup = val
            elif key == "AUTO_LEVELS":
                if val not in VALID_AUTO_LEVELS_CHOICES:
                    raise reader.error(
                        f"Invalid AUTO_LEVELS option '{val}'. Expected one of {VALID_AUTO_LEVELS_CHOICES}",
                        line_num,
                    )
                opts.auto_levels = val
            elif key == "LAYOUT":
                if val not in VALID_LAYOUT_CHOICES:
                    raise reader.error(
                        f"Invalid LAYOUT option '{val}'. Expected one of {VALID_LAYOUT_CHOICES}",
                        line_num,
                    )
                opts.layout = val
            elif key in ("VIEW_STYLE", "REQUIREMENT_STYLE"):
                if val not in VALID_VIEW_STYLE_CHOICES:
                    raise reader.error(
                        f"Invalid {key} option '{val}'. Expected one of {VALID_VIEW_STYLE_CHOICES}",
                        line_num,
                    )
                opts.view_style_tag = key
                opts.view_style = val
            elif key in ("NODE_IN_TOC", "REQUIREMENT_IN_TOC"):
                if val not in VALID_BOOLEAN_CHOICES:
                    raise reader.error(
                        f"Invalid {key} option '{val}'. Expected 'True' or 'False'",
                        line_num,
                    )
                opts.node_in_toc_tag = key
                opts.node_in_toc = val
            elif key == "DEFAULT_VIEW":
                opts.default_view = _require_non_empty_single_line(
                    val, key, reader, line_num
                )
            else:
                raise reader.error(f"Unknown option in OPTIONS: '{key}'", line_num)
        return opts

    def _parse_document_metadata(
        self, reader: _LineReader
    ) -> dict[str, str]:
        metadata: dict[str, str] = {}
        while not reader.eof():
            line = reader.peek()
            assert line is not None
            if not line.startswith("  "):
                break
            line_num, line = reader.next_line()
            stripped = line[2:]
            if ": " not in stripped:
                raise reader.error(
                    f"Malformed entry in METADATA block: {line!r}", line_num
                )
            key, val = stripped.split(": ", 1)
            if not RE_METADATA_KEY.match(key):
                raise reader.error(
                    f"Invalid metadata key '{key}' (must match [a-zA-Z_][a-zA-Z0-9_-]*)",
                    line_num,
                )
            metadata[key] = _require_non_empty_single_line(
                val, key, reader, line_num
            )
        return metadata

    def _parse_document_views(self, reader: _LineReader) -> List[ViewElement]:
        views: List[ViewElement] = []
        while not reader.eof():
            line = reader.peek()
            assert line is not None
            if not line.startswith("- ID: "):
                break
            line_num, line = reader.next_line()
            view_id = line[len("- ID: ") :]
            if not RE_UID.match(view_id):
                raise reader.error(f"Invalid view ID '{view_id}'", line_num)

            name: Optional[str] = None
            if not reader.eof() and reader.peek().startswith("  NAME: "):
                _, nline = reader.next_line()
                name = _require_non_empty_single_line(
                    nline[len("  NAME: ") :], "NAME", reader, reader.idx
                )

            if reader.eof() or reader.peek() != "  TAGS:":
                raise reader.error(
                    f"View '{view_id}' is missing required '  TAGS:' section"
                )
            reader.next_line()  # consume "  TAGS:"

            tags: List[ViewElementTags] = []
            while not reader.eof() and reader.peek().startswith(
                "  - OBJECT_TYPE: "
            ):
                t_line_num, t_line = reader.next_line()
                obj_type = _require_non_empty_single_line(
                    t_line[len("  - OBJECT_TYPE: ") :],
                    "OBJECT_TYPE",
                    reader,
                    t_line_num,
                )
                if reader.eof() or reader.peek() != "    VISIBLE_FIELDS:":
                    raise reader.error(
                        f"View tag '{obj_type}' is missing '    VISIBLE_FIELDS:'"
                    )
                reader.next_line()  # consume "    VISIBLE_FIELDS:"

                vis_fields: List[ViewElementField] = []
                while not reader.eof() and reader.peek().startswith(
                    "    - NAME: "
                ):
                    f_line_num, f_line = reader.next_line()
                    f_name = _require_non_empty_single_line(
                        f_line[len("    - NAME: ") :],
                        "NAME",
                        reader,
                        f_line_num,
                    )
                    placement: Optional[str] = None
                    if not reader.eof() and reader.peek().startswith(
                        "      PLACEMENT: "
                    ):
                        p_line_num, p_line = reader.next_line()
                        placement = _require_non_empty_single_line(
                            p_line[len("      PLACEMENT: ") :],
                            "PLACEMENT",
                            reader,
                            p_line_num,
                        )
                    vis_fields.append(
                        ViewElementField(name=f_name, placement=placement)
                    )
                if not vis_fields:
                    raise reader.error(
                        f"View tag '{obj_type}' must define at least one field in VISIBLE_FIELDS",
                        t_line_num,
                    )
                tags.append(
                    ViewElementTags(
                        object_type=obj_type, visible_fields=vis_fields
                    )
                )

            if not tags:
                raise reader.error(
                    f"View '{view_id}' must define at least one entry in TAGS",
                    line_num,
                )

            hidden_tags: List[str] = []
            if not reader.eof() and reader.peek() == "  HIDDEN_TAGS:":
                reader.next_line()
                while not reader.eof() and reader.peek().startswith("  - "):
                    h_line_num, h_line = reader.next_line()
                    ht = _require_non_empty_single_line(
                        h_line[len("  - ") :],
                        "HIDDEN_TAG",
                        reader,
                        h_line_num,
                    )
                    hidden_tags.append(ht)

            views.append(
                ViewElement(
                    view_id=view_id,
                    name=name,
                    tags=tags,
                    hidden_tags=hidden_tags,
                )
            )

        if not views:
            raise reader.error("VIEWS block must contain at least one '- ID: ...' view")
        return views

    def _parse_grammar_block(
        self, reader: _LineReader, *, enable_mid: bool = False
    ) -> DocumentGrammar:
        line_num, line = reader.next_line()
        if line != "[GRAMMAR]":
            raise reader.error("Expected '[GRAMMAR]'", line_num)

        if not reader.eof() and reader.peek().startswith("IMPORT_FROM_FILE: "):
            imp_num, imp_line = reader.next_line()
            import_file = imp_line[len("IMPORT_FROM_FILE: ") :].strip()
            if not import_file:
                raise reader.error(
                    "[GRAMMAR] IMPORT_FROM_FILE cannot be empty", imp_num
                )
            return DocumentGrammar(
                elements=[],
                import_from_file=import_file,
                is_default=False,
            )

        elements: List[GrammarElement] = []
        if not reader.eof() and reader.peek() == "ELEMENTS:":
            reader.next_line()  # consume "ELEMENTS:"
            while not reader.eof() and reader.peek().startswith("- TAG: "):
                elements.append(self._parse_grammar_element(reader))
            if not elements:
                raise reader.error(
                    "[GRAMMAR] ELEMENTS block must contain at least one '- TAG:' element",
                    line_num,
                )

        grammar = DocumentGrammar(
            elements=elements,
            import_from_file=None,
            is_default=False,
        )
        # StrictDoc automatically ensures TEXT element is available in grammar if ELEMENTS were specified
        if elements and not grammar.has_text_element():
            grammar.elements.insert(
                0, create_default_text_element(enable_mid=enable_mid)
            )
        return grammar

    def _parse_grammar_element(self, reader: _LineReader) -> GrammarElement:
        line_num, line = reader.next_line()
        tag = line[len("- TAG: ") :]
        if not RE_NODE_NAME.match(tag) or tag in ("DOCUMENT", "GRAMMAR"):
            raise reader.error(
                f"Invalid grammar element TAG '{tag}'", line_num
            )

        prop_is_composite: Optional[bool] = None
        prop_prefix: Optional[str] = None
        prop_view_style: Optional[str] = None

        if not reader.eof() and reader.peek() == "  PROPERTIES:":
            reader.next_line()
            while not reader.eof() and reader.peek().startswith("    "):
                p_num, p_line = reader.next_line()
                stripped = p_line[4:]
                if stripped.startswith("IS_COMPOSITE: "):
                    val = stripped[len("IS_COMPOSITE: ") :]
                    prop_is_composite = _parse_boolean(
                        val, "IS_COMPOSITE", reader, p_num
                    )
                elif stripped.startswith("PREFIX:"):
                    prop_prefix = stripped[len("PREFIX:") :].lstrip(" ")
                elif stripped.startswith("VIEW_STYLE: "):
                    val = stripped[len("VIEW_STYLE: ") :]
                    if val not in VALID_VIEW_STYLE_CHOICES:
                        raise reader.error(
                            f"Invalid grammar VIEW_STYLE '{val}'. Expected one of {VALID_VIEW_STYLE_CHOICES}",
                            p_num,
                        )
                    prop_view_style = val
                else:
                    raise reader.error(
                        f"Unknown property in grammar element '{tag}': {stripped!r}",
                        p_num,
                    )

        if reader.eof() or reader.peek() != "  FIELDS:":
            raise reader.error(
                f"Grammar element '{tag}' is missing required '  FIELDS:' block",
                line_num,
            )
        reader.next_line()  # consume "  FIELDS:"

        fields: List[GrammarElementField] = []
        while not reader.eof() and reader.peek().startswith("  - TITLE: "):
            fields.append(self._parse_grammar_field(reader, tag))

        if not fields:
            raise reader.error(
                f"Grammar element '{tag}' must define at least one field in FIELDS",
                line_num,
            )

        relations: List[GrammarElementRelation] = []
        if not reader.eof() and reader.peek() == "  RELATIONS:":
            reader.next_line()
            while not reader.eof() and reader.peek().startswith("  - TYPE: "):
                relations.append(self._parse_grammar_relation(reader, tag))
            if not relations:
                raise reader.error(
                    f"Grammar element '{tag}' RELATIONS block cannot be empty",
                    line_num,
                )

        return GrammarElement(
            tag=tag,
            property_is_composite=prop_is_composite,
            property_prefix=prop_prefix,
            property_view_style=prop_view_style,
            fields=fields,
            relations=relations,
        )

    def _parse_grammar_field(
        self, reader: _LineReader, element_tag: str
    ) -> GrammarElementField:
        f_num, f_line = reader.next_line()
        title = f_line[len("  - TITLE: ") :]
        if title == "RELATIONS" or not RE_FIELD_NAME.match(title):
            raise reader.error(
                f"Invalid field TITLE '{title}' in grammar element '{element_tag}'",
                f_num,
            )

        human_title: Optional[str] = None
        if not reader.eof() and reader.peek().startswith("    HUMAN_TITLE: "):
            h_num, h_line = reader.next_line()
            human_title = _require_non_empty_single_line(
                h_line[len("    HUMAN_TITLE: ") :],
                "HUMAN_TITLE",
                reader,
                h_num,
            )

        if reader.eof() or not reader.peek().startswith("    TYPE: "):
            raise reader.error(
                f"Grammar field '{title}' is missing '    TYPE: ...'", f_num
            )
        t_num, t_line = reader.next_line()
        raw_type = t_line[len("    TYPE: ") :]

        gef_type: str
        options: List[str] = []
        if raw_type == "String":
            gef_type = "String"
        elif raw_type == "Tag":
            gef_type = "Tag"
        elif m_sc := _RE_SINGLE_CHOICE_TYPE.match(raw_type):
            gef_type = "SingleChoice"
            options = parse_choice_options(m_sc.group("opts"))
            if not options:
                raise reader.error(
                    f"SingleChoice field '{title}' must specify options", t_num
                )
        elif m_mc := _RE_MULTIPLE_CHOICE_TYPE.match(raw_type):
            gef_type = "MultipleChoice"
            options = parse_choice_options(m_mc.group("opts"))
            if not options:
                raise reader.error(
                    f"MultipleChoice field '{title}' must specify options", t_num
                )
        else:
            raise reader.error(
                f"Invalid grammar field TYPE '{raw_type}' for field '{title}'",
                t_num,
            )

        if reader.eof() or not reader.peek().startswith("    REQUIRED: "):
            raise reader.error(
                f"Grammar field '{title}' is missing '    REQUIRED: True|False'",
                t_num,
            )
        r_num, r_line = reader.next_line()
        req_bool = _parse_boolean(
            r_line[len("    REQUIRED: ") :], "REQUIRED", reader, r_num
        )

        return GrammarElementField(
            title=title,
            gef_type=gef_type,
            required=req_bool,
            human_title=human_title,
            options=options,
        )

    def _parse_grammar_relation(
        self, reader: _LineReader, element_tag: str
    ) -> GrammarElementRelation:
        r_num, r_line = reader.next_line()
        rel_type = r_line[len("  - TYPE: ") :]
        if rel_type not in VALID_RELATION_TYPES:
            raise reader.error(
                f"Invalid grammar relation TYPE '{rel_type}' in '{element_tag}'. Expected Parent, Child, or File",
                r_num,
            )
        role: Optional[str] = None
        rev_role: Optional[str] = None
        while not reader.eof() and reader.peek().startswith("    "):
            sub_num, sub_line = reader.next_line()
            stripped = sub_line[4:]
            if stripped.startswith("ROLE: "):
                role = _require_non_empty_single_line(
                    stripped[len("ROLE: ") :], "ROLE", reader, sub_num
                )
            elif stripped.startswith("REVERSE_ROLE: "):
                if rel_type == "File":
                    raise reader.error(
                        "File grammar relation cannot have REVERSE_ROLE",
                        sub_num,
                    )
                rev_role = _require_non_empty_single_line(
                    stripped[len("REVERSE_ROLE: ") :],
                    "REVERSE_ROLE",
                    reader,
                    sub_num,
                )
            else:
                raise reader.error(
                    f"Unexpected line in grammar relation: {sub_line!r}",
                    sub_num,
                )
        return GrammarElementRelation(
            relation_type=rel_type,
            relation_role=role,
            reverse_relation_role=rev_role,
        )

    def _parse_section_contents(
        self,
        reader: _LineReader,
        *,
        closing_tag: Optional[str],
        is_legacy_close: bool,
    ) -> List[SDocElement]:
        contents: List[SDocElement] = []

        while not reader.eof():
            reader.skip_blank_lines()
            if reader.eof():
                break

            peeked = reader.peek()
            assert peeked is not None

            # Check for composite closing tag [[/TAG]]
            if m_comp_close := _RE_COMPOSITE_CLOSE.match(peeked):
                close_tag = m_comp_close.group("tag")
                if not is_legacy_close and closing_tag == close_tag:
                    reader.next_line()  # consume [[/TAG]]
                    return contents
                raise reader.error(
                    f"Unexpected closing composite tag '[[/{close_tag}]]'"
                    + (
                        f" (expected '[[/{closing_tag}]]')"
                        if closing_tag and not is_legacy_close
                        else ""
                    )
                )

            # Check for legacy closing tag [/SECTION] or [/COMPOSITE_REQUIREMENT]
            if m_node_close := _RE_NODE_CLOSE.match(peeked):
                close_tag = m_node_close.group("tag")
                if is_legacy_close and closing_tag == close_tag:
                    reader.next_line()  # consume [/TAG]
                    return contents
                raise reader.error(
                    f"Unexpected closing tag '[/{close_tag}]'"
                    + (
                        f" (expected '[/{closing_tag}]')"
                        if closing_tag and is_legacy_close
                        else ""
                    )
                )

            # 1. Composite node: [[NODE_TYPE]]
            if m_comp_open := _RE_COMPOSITE_OPEN.match(peeked):
                tag = m_comp_open.group("tag")
                if tag in ("DOCUMENT", "GRAMMAR"):
                    raise reader.error(
                        f"Reserved keyword '{tag}' cannot be used as composite node type"
                    )
                contents.append(self._parse_composite_node(reader, tag))
                continue

            # 2. [DOCUMENT_FROM_FILE]
            if peeked == "[DOCUMENT_FROM_FILE]":
                contents.append(self._parse_document_from_file(reader))
                continue

            # 3. Legacy [FREETEXT] ... [/FREETEXT]
            if peeked == "[FREETEXT]":
                contents.append(self._parse_legacy_freetext(reader))
                continue

            # 4. Legacy [SECTION] ... [/SECTION]
            if peeked == "[SECTION]":
                if not self.allow_legacy_sections:
                    raise reader.error(
                        "[SECTION] elements are deprecated in modern StrictDoc (use [[SECTION]] ... [[/SECTION]] or enable allow_legacy_sections)"
                    )
                contents.append(self._parse_legacy_section(reader))
                continue

            # 5. Legacy [COMPOSITE_REQUIREMENT] ... [/COMPOSITE_REQUIREMENT]
            if peeked == "[COMPOSITE_REQUIREMENT]":
                contents.append(
                    self._parse_legacy_composite_requirement(reader)
                )
                continue

            # 6. Standard node: [NODE_TYPE]
            if m_node_open := _RE_NODE_OPEN.match(peeked):
                tag = m_node_open.group("tag")
                if tag in ("DOCUMENT", "GRAMMAR", "SECTION", "DOCUMENT_FROM_FILE"):
                    raise reader.error(
                        f"Reserved keyword '{tag}' cannot be used as standard node type"
                    )
                contents.append(self._parse_standard_node(reader, tag))
                continue

            raise reader.error(
                f"Expected section or node declaration (e.g. [[SECTION]], [REQUIREMENT], [TEXT]), got {peeked!r}"
            )

        if closing_tag is not None:
            expected_str = (
                f"[/{closing_tag}]"
                if is_legacy_close
                else f"[[/{closing_tag}]]"
            )
            raise reader.error(
                f"Unclosed block: expected '{expected_str}' before end of file",
                line_num=reader.total,
            )

        return contents

    def _parse_document_from_file(
        self, reader: _LineReader
    ) -> DocumentFromFile:
        start_line, _ = reader.next_line()  # consume [DOCUMENT_FROM_FILE]
        if reader.eof():
            raise reader.error(
                "[DOCUMENT_FROM_FILE] is missing required 'FILE: ...' line",
                start_line,
            )
        f_num, f_line = reader.next_line()
        if not f_line.startswith("FILE: "):
            raise reader.error(
                f"Expected 'FILE: <path>' inside [DOCUMENT_FROM_FILE], got {f_line!r}",
                f_num,
            )
        file_path = f_line[len("FILE: ") :].strip()
        if not file_path:
            raise reader.error(
                "[DOCUMENT_FROM_FILE] FILE path cannot be empty", f_num
            )
        return DocumentFromFile(file=file_path, line_start=start_line)

    def _parse_legacy_freetext(self, reader: _LineReader) -> SDocNode:
        start_line, _ = reader.next_line()  # consume [FREETEXT]
        lines: List[str] = []
        while not reader.eof():
            line_num, line = reader.next_line()
            if line == "[/FREETEXT]":
                text_val = "\n".join(lines)
                return SDocNode(
                    node_type="TEXT",
                    fields=[
                        SDocNodeField(
                            field_name="STATEMENT",
                            value=text_val,
                            multiline=True,
                            parts=parse_text_parts(text_val),
                        )
                    ],
                    is_composite=False,
                    legacy_freetext=True,
                    line_start=start_line,
                )
            lines.append(line)
        raise reader.error(
            "Unclosed [FREETEXT] block: missing '[/FREETEXT]'", start_line
        )

    def _parse_legacy_section(self, reader: _LineReader) -> SDocNode:
        start_line, _ = reader.next_line()  # consume [SECTION]
        fields, relations = self._parse_node_fields_and_relations(
            reader, node_type="SECTION", allow_req_prefix=True
        )
        if not any(f.field_name == "TITLE" for f in fields):
            raise reader.error(
                "[SECTION] is missing required 'TITLE' field", start_line
            )
        children = self._parse_section_contents(
            reader, closing_tag="SECTION", is_legacy_close=True
        )
        return SDocNode(
            node_type="SECTION",
            fields=fields,
            relations=relations,
            section_contents=children,
            is_composite=True,
            legacy_section=True,
            line_start=start_line,
        )

    def _parse_legacy_composite_requirement(
        self, reader: _LineReader
    ) -> SDocNode:
        start_line, _ = reader.next_line()  # consume [COMPOSITE_REQUIREMENT]
        fields, relations = self._parse_node_fields_and_relations(
            reader, node_type="COMPOSITE_REQUIREMENT", allow_req_prefix=True
        )
        children = self._parse_section_contents(
            reader, closing_tag="COMPOSITE_REQUIREMENT", is_legacy_close=True
        )
        return SDocNode(
            node_type="COMPOSITE_REQUIREMENT",
            fields=fields,
            relations=relations,
            section_contents=children,
            is_composite=True,
            legacy_section=True,
            line_start=start_line,
        )

    def _parse_composite_node(
        self, reader: _LineReader, node_type: str
    ) -> SDocNode:
        start_line, _ = reader.next_line()  # consume [[NODE_TYPE]]
        fields, relations = self._parse_node_fields_and_relations(
            reader, node_type=node_type, allow_req_prefix=(node_type == "SECTION")
        )
        if not fields:
            raise reader.error(
                f"Composite node '[[{node_type}]]' must have at least one field",
                start_line,
            )
        children = self._parse_section_contents(
            reader, closing_tag=node_type, is_legacy_close=False
        )
        return SDocNode(
            node_type=node_type,
            fields=fields,
            relations=relations,
            section_contents=children,
            is_composite=True,
            line_start=start_line,
        )

    def _parse_standard_node(
        self, reader: _LineReader, node_type: str
    ) -> SDocNode:
        start_line, _ = reader.next_line()  # consume [NODE_TYPE]
        fields, relations = self._parse_node_fields_and_relations(
            reader, node_type=node_type, allow_req_prefix=False
        )
        if not fields:
            raise reader.error(
                f"Node '[{node_type}]' must have at least one field",
                start_line,
            )
        return SDocNode(
            node_type=node_type,
            fields=fields,
            relations=relations,
            section_contents=[],
            is_composite=False,
            line_start=start_line,
        )

    def _parse_node_fields_and_relations(
        self,
        reader: _LineReader,
        *,
        node_type: str,
        allow_req_prefix: bool = False,
    ) -> Tuple[List[SDocNodeField], List[Reference]]:
        fields: List[SDocNodeField] = []
        relations: List[Reference] = []

        while not reader.eof():
            peeked = reader.peek()
            assert peeked is not None

            if peeked == "" or peeked.startswith("["):
                break

            if peeked in ("RELATIONS:", "REFS:"):
                reader.next_line()  # consume RELATIONS: or REFS:
                relations.extend(self._parse_node_relations(reader))
                break

            line_num, line = reader.next_line()
            if ": " not in line and not line.endswith(":"):
                raise reader.error(
                    f"Expected field 'NAME: value' or 'RELATIONS:' in [{node_type}], got {line!r}",
                    line_num,
                )

            if ": " in line:
                field_name, rest = line.split(": ", 1)
            else:
                field_name = line[:-1]
                rest = ""

            if allow_req_prefix and field_name == "REQ_PREFIX":
                field_name = "PREFIX"

            if field_name == "RELATIONS":
                raise reader.error(
                    "'RELATIONS' is a reserved keyword and cannot be used as a field name",
                    line_num,
                )
            if not RE_FIELD_NAME.match(field_name):
                raise reader.error(
                    f"Invalid field name '{field_name}' in [{node_type}]",
                    line_num,
                )

            if rest == ">>>":
                if field_name in RESERVED_SINGLELINE_FIELDS:
                    raise reader.error(
                        f"The node field '{field_name}' is a reserved single-line field and cannot be multiline",
                        line_num,
                    )
                multiline_val = self._parse_multiline_string(
                    reader, field_name, line_num
                )
                fields.append(
                    SDocNodeField(
                        field_name=field_name,
                        value=multiline_val,
                        multiline=True,
                        parts=parse_text_parts(multiline_val),
                    )
                )
            else:
                val = _require_non_empty_single_line(
                    rest, field_name, reader, line_num
                )
                if field_name == "UID" and not RE_UID.match(val):
                    raise reader.error(
                        f"Invalid UID value '{val}' in [{node_type}]",
                        line_num,
                    )
                fields.append(
                    SDocNodeField(
                        field_name=field_name,
                        value=val,
                        multiline=False,
                        parts=parse_text_parts(val),
                    )
                )

        # Also check if legacy REFS: was placed before fields (as in early commit of strictdock-parser.py)
        while not reader.eof():
            peeked = reader.peek()
            assert peeked is not None
            if peeked == "" or peeked.startswith("["):
                break
            if peeked in ("RELATIONS:", "REFS:"):
                reader.next_line()
                relations.extend(self._parse_node_relations(reader))
            else:
                # Additional fields after legacy REFS:
                more_fields, more_rels = self._parse_node_fields_and_relations(
                    reader,
                    node_type=node_type,
                    allow_req_prefix=allow_req_prefix,
                )
                fields.extend(more_fields)
                relations.extend(more_rels)
                break

        return fields, relations

    def _parse_multiline_string(
        self, reader: _LineReader, field_name: str, start_line: int
    ) -> str:
        lines: List[str] = []
        while not reader.eof():
            line_num, line = reader.next_line()
            if line == "<<<":
                content = "\n".join(lines)
                if not content or not content.strip():
                    raise reader.error(
                        f"Multiline field '{field_name}' cannot be empty (StrictDoc Rule #3)",
                        start_line,
                    )
                return content
            lines.append(line)
        raise reader.error(
            f"Unclosed multiline string for field '{field_name}': missing '<<<'",
            start_line,
        )

    def _parse_node_relations(self, reader: _LineReader) -> List[Reference]:
        relations: List[Reference] = []
        while not reader.eof() and reader.peek().startswith("- TYPE: "):
            r_num, r_line = reader.next_line()
            ref_type = r_line[len("- TYPE: ") :].strip()
            if ref_type not in VALID_RELATION_TYPES:
                raise reader.error(
                    f"Invalid relation TYPE '{ref_type}'. Expected one of {VALID_RELATION_TYPES}",
                    r_num,
                )

            if ref_type in ("Parent", "Child"):
                if reader.eof() or not reader.peek().startswith("  VALUE: "):
                    raise reader.error(
                        f"{ref_type} relation is missing required '  VALUE: <UID>'",
                        r_num,
                    )
                v_num, v_line = reader.next_line()
                ref_uid = v_line[len("  VALUE: ") :].strip()
                if not ref_uid:
                    raise reader.error(
                        f"{ref_type} relation VALUE cannot be empty", v_num
                    )
                role: Optional[str] = None
                if not reader.eof() and reader.peek().startswith("  ROLE: "):
                    role_num, role_line = reader.next_line()
                    role = _require_non_empty_single_line(
                        role_line[len("  ROLE: ") :], "ROLE", reader, role_num
                    )
                if ref_type == "Parent":
                    relations.append(
                        ParentReqReference(ref_uid=ref_uid, role=role)
                    )
                else:
                    relations.append(
                        ChildReqReference(ref_uid=ref_uid, role=role)
                    )
            elif ref_type == "File":
                role = None
                file_format: Optional[str] = None
                deprecated_val: Optional[str] = None
                path: Optional[str] = None
                element: Optional[str] = None
                entry_id: Optional[str] = None
                line_range: Optional[Tuple[int, int]] = None
                func: Optional[str] = None
                clazz: Optional[str] = None
                hash_val: Optional[str] = None

                while not reader.eof() and reader.peek().startswith("  "):
                    sub_num, sub_line = reader.next_line()
                    stripped = sub_line[2:]
                    if ": " not in stripped:
                        raise reader.error(
                            f"Malformed File relation entry: {sub_line!r}",
                            sub_num,
                        )
                    k, v = stripped.split(": ", 1)
                    if k == "ROLE":
                        role = _require_non_empty_single_line(
                            v, k, reader, sub_num
                        )
                    elif k == "FORMAT":
                        if not RE_FILE_FORMAT.match(v):
                            raise reader.error(
                                f"Invalid File FORMAT '{v}'", sub_num
                            )
                        file_format = v
                    elif k == "VALUE":
                        deprecated_val = v
                    elif k == "PATH":
                        path = v
                    elif k == "ELEMENT":
                        element = v
                    elif k == "ID":
                        entry_id = v
                    elif k == "LINE_RANGE":
                        parts = [p.strip() for p in v.split(",")]
                        if len(parts) != 2 or not all(
                            p.isdigit() for p in parts
                        ):
                            raise reader.error(
                                f"Invalid LINE_RANGE '{v}': expected '<start>, <end>'",
                                sub_num,
                            )
                        line_range = (int(parts[0]), int(parts[1]))
                    elif k == "FUNCTION":
                        func = v
                    elif k == "CLASS":
                        clazz = v
                    elif k == "HASH":
                        hash_val = v
                    else:
                        raise reader.error(
                            f"Unknown File relation property '{k}'", sub_num
                        )

                if path is None and deprecated_val is None:
                    raise reader.error(
                        "File relation must specify 'PATH' (or legacy 'VALUE')",
                        r_num,
                    )
                relations.append(
                    FileReference(
                        path=path,
                        role=role,
                        file_format=file_format,
                        deprecated_value=deprecated_val,
                        element=element,
                        id=entry_id,
                        line_range=line_range,
                        function=func,
                        clazz=clazz,
                        hash=hash_val,
                    )
                )

        if not relations:
            raise reader.error("RELATIONS block must contain at least one '- TYPE: ...' entry")
        return relations


def parse_sdoc(text: str, *, allow_legacy_sections: bool = True) -> SDocDocument:
    """Convenience function to parse an `.sdoc` string into an `SDocDocument`."""
    return SDocParser(allow_legacy_sections=allow_legacy_sections).parse_sdoc(
        text
    )


def parse_sgra(text: str, *, enable_mid: bool = False) -> DocumentGrammar:
    """Convenience function to parse an `.sgra` string into a `DocumentGrammar`."""
    return SDocParser().parse_sgra(text, enable_mid=enable_mid)

