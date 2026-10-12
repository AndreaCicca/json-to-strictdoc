"""
Semantic validator for StrictDoc documents and grammars.
Faithfully implements all rules from `strictdoc/backend/sdoc/validations/sdoc_validator.py`
and `strictdoc/backend/sdoc/processor.py`.
"""

from __future__ import annotations

import re
from typing import Iterator, List, Optional, Set

from .grammar import (
    RE_COMMA_SEPARATED,
    RE_FIELD_NAME,
    RE_METADATA_KEY,
    RE_NODE_NAME,
    RE_UID,
    RESERVED_SINGLELINE_FIELDS,
    VALID_AUTO_LEVELS_CHOICES,
    VALID_BOOLEAN_CHOICES,
    VALID_LAYOUT_CHOICES,
    VALID_MARKUP_CHOICES,
    VALID_VIEW_STYLE_CHOICES,
    create_default_grammar,
)
from .models import (
    DocumentFromFile,
    DocumentGrammar,
    GrammarElement,
    GrammarElementField,
    SDocDocument,
    SDocElement,
    SDocNode,
    SDocNodeField,
)


class SDocValidationError(ValueError):
    """Raised when an SDoc document or grammar violates StrictDoc semantic rules."""

    def __init__(self, message: str, line: Optional[int] = None) -> None:
        self.raw_message = message
        self.line = line
        loc = f" (line {line})" if line is not None else ""
        super().__init__(f"SDoc validation error{loc}: {message}")


class SDocValidator:
    """Validates `SDocDocument` and `DocumentGrammar` instances against StrictDoc's specification."""

    @staticmethod
    def validate_document(
        document: SDocDocument,
        *,
        strict_field_order: bool = True,
        auto_uid_mode: bool = False,
        allow_legacy: bool = True,
    ) -> None:
        if not document.title or not document.title.strip():
            raise SDocValidationError("[DOCUMENT] TITLE cannot be empty")

        if document.config.uid is not None and not RE_UID.match(
            document.config.uid
        ):
            raise SDocValidationError(
                f"Invalid [DOCUMENT] UID: '{document.config.uid}'"
            )

        opts = document.config.options
        if opts is not None:
            if opts.markup is not None and opts.markup not in VALID_MARKUP_CHOICES:
                raise SDocValidationError(
                    f"Invalid MARKUP option '{opts.markup}'. Must be one of {VALID_MARKUP_CHOICES}"
                )
            if (
                opts.auto_levels is not None
                and opts.auto_levels not in VALID_AUTO_LEVELS_CHOICES
            ):
                raise SDocValidationError(
                    f"Invalid AUTO_LEVELS option '{opts.auto_levels}'. Must be one of {VALID_AUTO_LEVELS_CHOICES}"
                )
            if opts.layout is not None and opts.layout not in VALID_LAYOUT_CHOICES:
                raise SDocValidationError(
                    f"Invalid LAYOUT option '{opts.layout}'. Must be one of {VALID_LAYOUT_CHOICES}"
                )
            if (
                opts.view_style is not None
                and opts.view_style not in VALID_VIEW_STYLE_CHOICES
            ):
                raise SDocValidationError(
                    f"Invalid {opts.view_style_tag} option '{opts.view_style}'. Must be one of {VALID_VIEW_STYLE_CHOICES}"
                )
            if (
                opts.node_in_toc is not None
                and opts.node_in_toc not in VALID_BOOLEAN_CHOICES
            ):
                raise SDocValidationError(
                    f"Invalid {opts.node_in_toc_tag} option '{opts.node_in_toc}'. Must be 'True' or 'False'"
                )
            if opts.default_view is not None:
                view_ids = {v.view_id for v in document.views}
                if opts.default_view not in view_ids:
                    raise SDocValidationError(
                        f"DEFAULT_VIEW '{opts.default_view}' does not exist in VIEWS"
                    )

        for k, v in document.config.metadata.items():
            if not RE_METADATA_KEY.match(k):
                raise SDocValidationError(f"Invalid METADATA key '{k}'")
            if not v or not v.strip():
                raise SDocValidationError(
                    f"METADATA value for key '{k}' cannot be empty"
                )

        grammar = document.grammar or create_default_grammar(
            enable_mid=document.config.enable_mid
        )
        SDocValidator.validate_grammar(
            grammar, enable_mid=document.config.enable_mid
        )

        # Validate VIEWS against grammar elements (if grammar elements are resolved)
        if grammar.import_from_file is None:
            for view in document.views:
                for tag in view.tags:
                    if tag.object_type not in grammar.registered_elements:
                        raise SDocValidationError(
                            f"View '{view.view_id}' references unknown grammar element '{tag.object_type}'"
                        )
                    g_el = grammar.elements_by_type[tag.object_type]
                    for vf in tag.visible_fields:
                        if vf.name not in g_el.fields_map:
                            raise SDocValidationError(
                                f"View '{view.view_id}' references unknown field '{vf.name}' in element '{tag.object_type}'"
                            )

        seen_uids: Set[str] = set()
        if document.config.uid:
            seen_uids.add(document.config.uid)

        for item in document.section_contents:
            SDocValidator._validate_element(
                item,
                grammar=grammar,
                strict_field_order=strict_field_order,
                auto_uid_mode=auto_uid_mode,
                allow_legacy=allow_legacy,
                seen_uids=seen_uids,
            )

    @staticmethod
    def validate_grammar(
        grammar: DocumentGrammar, *, enable_mid: bool = False
    ) -> None:
        if grammar.import_from_file is not None:
            if re.search(r"\.\.|[/\\]", grammar.import_from_file):
                raise SDocValidationError(
                    f"[GRAMMAR]: IMPORT_FROM_FILE must not contain '..', '/', or '\\' characters: {grammar.import_from_file}"
                )
            return

        for element in grammar.elements:
            SDocValidator.validate_grammar_element(
                element, enable_mid=enable_mid
            )

    @staticmethod
    def validate_grammar_element(
        element: GrammarElement, *, enable_mid: bool = False
    ) -> None:
        if not RE_NODE_NAME.match(element.tag) or element.tag in (
            "DOCUMENT",
            "GRAMMAR",
        ):
            raise SDocValidationError(
                f"Invalid grammar element TAG '{element.tag}'"
            )

        if enable_mid and "MID" not in element.fields_map:
            raise SDocValidationError(
                f"Grammar element '{element.tag}' is missing 'MID' field required when ENABLE_MID is True"
            )

        if element.tag == "TEXT" and element.property_is_composite is True:
            raise SDocValidationError(
                "Grammar element 'TEXT' must not have IS_COMPOSITE: True"
            )

        if element.tag == "SECTION" and element.property_is_composite is not True:
            raise SDocValidationError(
                "Grammar element 'SECTION' must have IS_COMPOSITE: True"
            )

        for field in element.fields:
            if field.title == "RELATIONS" or not RE_FIELD_NAME.match(field.title):
                raise SDocValidationError(
                    f"Invalid field title '{field.title}' in grammar element '{element.tag}'"
                )

        for rel in element.relations:
            if (
                rel.reverse_relation_role is not None
                and rel.relation_role is None
            ):
                raise SDocValidationError(
                    f"Grammar element '{element.tag}' relation '{rel.relation_type}' has REVERSE_ROLE='{rel.reverse_relation_role}' without ROLE"
                )

    @staticmethod
    def _validate_element(
        element: SDocElement,
        *,
        grammar: DocumentGrammar,
        strict_field_order: bool,
        auto_uid_mode: bool,
        allow_legacy: bool,
        seen_uids: Set[str],
    ) -> None:
        if isinstance(element, DocumentFromFile):
            if not element.file.endswith(".sdoc"):
                raise SDocValidationError(
                    f"[DOCUMENT_FROM_FILE]: A document file name must have '.sdoc' extension: {element.file}",
                    line=element.line_start,
                )
            return

        assert isinstance(element, SDocNode)
        node = element

        if not allow_legacy and (node.legacy_section or node.legacy_freetext):
            raise SDocValidationError(
                f"Legacy element '{node.node_type}' is not allowed when allow_legacy=False",
                line=node.line_start,
            )

        # Check UID uniqueness and format
        uid_val = node.get_field_value("UID")
        if uid_val is not None:
            if not RE_UID.match(uid_val):
                raise SDocValidationError(
                    f"Invalid UID '{uid_val}' on node [{node.node_type}]",
                    line=node.line_start,
                )
            if uid_val in seen_uids:
                raise SDocValidationError(
                    f"Duplicate UID '{uid_val}' found in document",
                    line=node.line_start,
                )
            seen_uids.add(uid_val)

        # If grammar is imported from external file and not loaded, skip grammar element checks
        if grammar.import_from_file is not None and not grammar.elements:
            for child in node.section_contents:
                SDocValidator._validate_element(
                    child,
                    grammar=grammar,
                    strict_field_order=strict_field_order,
                    auto_uid_mode=auto_uid_mode,
                    allow_legacy=allow_legacy,
                    seen_uids=seen_uids,
                )
            return

        # Allow legacy COMPOSITE_REQUIREMENT if allow_legacy is True and not explicitly in grammar
        if (
            node.node_type == "COMPOSITE_REQUIREMENT"
            and allow_legacy
            and "COMPOSITE_REQUIREMENT" not in grammar.registered_elements
        ):
            grammar_element = GrammarElement(
                tag="COMPOSITE_REQUIREMENT",
                property_is_composite=True,
                fields=list(grammar.elements_by_type["REQUIREMENT"].fields)
                if "REQUIREMENT" in grammar.elements_by_type
                else [],
                relations=list(grammar.elements_by_type["REQUIREMENT"].relations)
                if "REQUIREMENT" in grammar.elements_by_type
                else [],
            )
        else:
            if node.node_type not in grammar.registered_elements:
                raise SDocValidationError(
                    f"Unknown node type '[{node.node_type}]'. Registered types: {sorted(grammar.registered_elements)}",
                    line=node.line_start,
                )
            grammar_element = grammar.elements_by_type[node.node_type]

        # Composite vs non-composite validation
        if node.is_composite and not grammar_element.property_is_composite:
            raise SDocValidationError(
                f"Node '[[{node.node_type}]]' is written as composite, but grammar element '{node.node_type}' is not composite",
                line=node.line_start,
            )
        if not node.is_composite and grammar_element.property_is_composite:
            raise SDocValidationError(
                f"Node '[{node.node_type}]' is written as non-composite, but grammar element '{node.node_type}' has IS_COMPOSITE: True",
                line=node.line_start,
            )

        registered_fields = set(grammar_element.get_field_titles())
        for f in node.fields:
            if f.field_name not in registered_fields:
                raise SDocValidationError(
                    f"Unregistered field '{f.field_name}' in node [{node.node_type}]. Allowed fields: {grammar_element.get_field_titles()}",
                    line=node.line_start,
                )
            if f.multiline and f.field_name in RESERVED_SINGLELINE_FIELDS:
                raise SDocValidationError(
                    f"Field '{f.field_name}' in node [{node.node_type}] is a reserved single-line field and cannot be multiline",
                    line=node.line_start,
                )

        if strict_field_order:
            SDocValidator._validate_node_fields_ordered(
                node=node,
                grammar_element=grammar_element,
                auto_uid_mode=auto_uid_mode,
            )
        else:
            # Validate required fields and field values regardless of order
            present_names = {f.field_name for f in node.fields}
            for gf in grammar_element.fields:
                if gf.required and gf.title not in present_names:
                    if gf.title in ("MID", "UID") and auto_uid_mode:
                        continue
                    raise SDocValidationError(
                        f"Node [{node.node_type}] is missing required field '{gf.title}'",
                        line=node.line_start,
                    )
            for f in node.fields:
                gf = grammar_element.fields_map[f.field_name]
                SDocValidator._validate_field_value(node, f, gf)

        # Validate relations against grammar element
        for ref in node.relations:
            if not grammar_element.has_relation_type_role(
                ref.ref_type, ref.role
            ):
                role_info = f" with ROLE '{ref.role}'" if ref.role else ""
                raise SDocValidationError(
                    f"Node [{node.node_type}] has unregistered relation TYPE '{ref.ref_type}'{role_info}",
                    line=node.line_start,
                )

        for child in node.section_contents:
            SDocValidator._validate_element(
                child,
                grammar=grammar,
                strict_field_order=strict_field_order,
                auto_uid_mode=auto_uid_mode,
                allow_legacy=allow_legacy,
                seen_uids=seen_uids,
            )

    @staticmethod
    def _validate_node_fields_ordered(
        *,
        node: SDocNode,
        grammar_element: GrammarElement,
        auto_uid_mode: bool,
    ) -> None:
        grammar_iter: Iterator[GrammarElementField] = iter(
            grammar_element.fields
        )
        node_iter: Iterator[SDocNodeField] = iter(node.fields)

        req_field: Optional[SDocNodeField] = next(node_iter, None)
        gram_field: Optional[GrammarElementField] = next(grammar_iter, None)

        while True:
            if gram_field is None:
                if req_field is None:
                    break
                raise SDocValidationError(
                    f"Wrong field order or duplicate field '{req_field.field_name}' in node [{node.node_type}]. Expected order: {grammar_element.get_field_titles()}",
                    line=node.line_start,
                )

            if req_field is None:
                if gram_field.required:
                    if gram_field.title in ("MID", "UID") and auto_uid_mode:
                        gram_field = next(grammar_iter, None)
                        continue
                    raise SDocValidationError(
                        f"Node [{node.node_type}] is missing required field '{gram_field.title}'",
                        line=node.line_start,
                    )
                gram_field = next(grammar_iter, None)
                continue

            if gram_field.title != req_field.field_name:
                if gram_field.required:
                    present_names = {f.field_name for f in node.fields}
                    if gram_field.title not in present_names:
                        if gram_field.title in ("MID", "UID") and auto_uid_mode:
                            gram_field = next(grammar_iter, None)
                            continue
                        raise SDocValidationError(
                            f"Node [{node.node_type}] is missing required field '{gram_field.title}'",
                            line=node.line_start,
                        )
                    raise SDocValidationError(
                        f"Wrong field order for '{req_field.field_name}' in node [{node.node_type}]. Expected '{gram_field.title}' first (grammar order: {grammar_element.get_field_titles()})",
                        line=node.line_start,
                    )
                gram_field = next(grammar_iter, None)
                continue

            SDocValidator._validate_field_value(node, req_field, gram_field)

            # COMMENT can appear multiple times consecutively
            if req_field.field_name == "COMMENT":
                req_field = next(node_iter, None)
                if req_field is not None and req_field.field_name == "COMMENT":
                    continue
                gram_field = next(grammar_iter, None)
                continue

            gram_field = next(grammar_iter, None)
            req_field = next(node_iter, None)

    @staticmethod
    def _validate_field_value(
        node: SDocNode,
        req_field: SDocNodeField,
        gram_field: GrammarElementField,
    ) -> None:
        val = req_field.value
        if gram_field.gef_type == "SingleChoice":
            if req_field.multiline:
                raise SDocValidationError(
                    f"SingleChoice field '{req_field.field_name}' in [{node.node_type}] cannot be multiline",
                    line=node.line_start,
                )
            if (
                val not in gram_field.options
                and val.strip('"') not in gram_field.options
                and val not in ("TBD", "TBC")
            ):
                raise SDocValidationError(
                    f"Invalid choice '{val}' for SingleChoice field '{req_field.field_name}' in [{node.node_type}]. Allowed: {gram_field.options}",
                    line=node.line_start,
                )
        elif gram_field.gef_type == "MultipleChoice":
            if req_field.multiline:
                raise SDocValidationError(
                    f"MultipleChoice field '{req_field.field_name}' in [{node.node_type}] cannot be multiline",
                    line=node.line_start,
                )
            if not RE_COMMA_SEPARATED.match(val):
                raise SDocValidationError(
                    f"MultipleChoice field '{req_field.field_name}' in [{node.node_type}] must be comma-space separated (e.g. 'A, B'), got '{val}'",
                    line=node.line_start,
                )
            for item in val.split(", "):
                if (
                    item not in gram_field.options
                    and item.strip('"') not in gram_field.options
                    and item not in ("TBD", "TBC")
                ):
                    raise SDocValidationError(
                        f"Invalid choice '{item}' in MultipleChoice field '{req_field.field_name}' in [{node.node_type}]. Allowed: {gram_field.options}",
                        line=node.line_start,
                    )
        elif gram_field.gef_type == "Tag":
            if req_field.multiline:
                raise SDocValidationError(
                    f"Tag field '{req_field.field_name}' in [{node.node_type}] cannot be multiline",
                    line=node.line_start,
                )
            if not RE_COMMA_SEPARATED.match(val):
                raise SDocValidationError(
                    f"Tag field '{req_field.field_name}' in [{node.node_type}] must be comma-space separated (e.g. 'Tag1, Tag2'), got '{val}'",
                    line=node.line_start,
                )
