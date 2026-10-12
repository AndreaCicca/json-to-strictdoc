"""
Serializer (Writer) for StrictDoc (.sdoc) documents and (.sgra) grammar files.
Faithfully implements `strictdoc/backend/sdoc/writer.py` (`SDWriter`), supporting both:
- Modern StrictDoc syntax (`[[SECTION]]`, `[TEXT]`, `[[COMPOSITE_NODE]]`)
- Legacy StrictDoc syntax (`[SECTION]`, `[FREETEXT]`) via `legacy=True`
"""

from __future__ import annotations

from typing import List, Optional

from .grammar import (
    create_default_grammar,
    format_choice_options,
    is_field_multiline,
)
from .models import (
    ChildReqReference,
    DocumentFromFile,
    DocumentGrammar,
    FileReference,
    GrammarElement,
    GrammarElementField,
    ParentReqReference,
    Reference,
    SDocDocument,
    SDocElement,
    SDocNode,
    SDocNodeField,
)


def _ensure_newline(text: str) -> str:
    return text if text.endswith("\n") else text + "\n"


class SDocWriter:
    """Writes `SDocDocument` and `DocumentGrammar` objects to `.sdoc` / `.sgra` text."""

    def __init__(self, *, legacy: bool = False) -> None:
        self.legacy = legacy

    def write_sdoc(self, document: SDocDocument) -> str:
        output = "[DOCUMENT]\n"

        if document.mid is not None:
            output += f"MID: {document.mid}\n"

        output += f"TITLE: {document.title}\n"

        cfg = document.config
        if cfg.uid is not None:
            output += f"UID: {cfg.uid}\n"
        if cfg.version is not None:
            output += f"VERSION: {cfg.version}\n"
        if cfg.date is not None:
            output += f"DATE: {cfg.date}\n"
        if cfg.classification is not None:
            output += f"CLASSIFICATION: {cfg.classification}\n"
        if cfg.prefix is not None:
            output += f"{cfg.prefix_tag}: {cfg.prefix}\n"
        if cfg.root is not None:
            output += f"ROOT: {'True' if cfg.root else 'False'}\n"

        opts = cfg.options
        if opts is not None and not opts.is_empty():
            output += "OPTIONS:\n"
            if opts.enable_mid is not None:
                output += (
                    f"  ENABLE_MID: {'True' if opts.enable_mid else 'False'}\n"
                )
            if opts.relation_field is not None:
                output += f"  RELATION_FIELD: {opts.relation_field}\n"
            if opts.markup is not None:
                output += f"  MARKUP: {opts.markup}\n"
            if opts.auto_levels is not None:
                output += f"  AUTO_LEVELS: {opts.auto_levels}\n"
            if opts.layout is not None:
                output += f"  LAYOUT: {opts.layout}\n"
            if opts.view_style is not None:
                output += f"  {opts.view_style_tag}: {opts.view_style}\n"
            if opts.node_in_toc is not None:
                output += f"  {opts.node_in_toc_tag}: {opts.node_in_toc}\n"
            if opts.default_view is not None:
                output += f"  DEFAULT_VIEW: {opts.default_view}\n"

        if cfg.metadata:
            output += "METADATA:\n"
            for k, v in cfg.metadata.items():
                output += f"  {k}: {v}\n"

        if document.views:
            output += "VIEWS:\n"
            for view in document.views:
                output += f"- ID: {view.view_id}\n"
                if view.name is not None:
                    output += f"  NAME: {view.name}\n"
                output += "  TAGS:\n"
                for tag in view.tags:
                    output += f"  - OBJECT_TYPE: {tag.object_type}\n"
                    output += "    VISIBLE_FIELDS:\n"
                    for vf in tag.visible_fields:
                        output += f"    - NAME: {vf.name}\n"
                        if vf.placement is not None:
                            output += f"      PLACEMENT: {vf.placement}\n"
                if view.hidden_tags:
                    output += "  HIDDEN_TAGS:\n"
                    for ht in view.hidden_tags:
                        output += f"  - {ht}\n"

        grammar = document.grammar or create_default_grammar(
            enable_mid=cfg.enable_mid
        )
        if not grammar.is_default:
            output += "\n"
            output += self.write_sgra(grammar)

        output += "\n"

        for element in document.section_contents:
            output += self._write_element(element, grammar)

        output = output.rstrip() + "\n"
        return output

    def write_sgra(self, grammar: DocumentGrammar) -> str:
        output = "[GRAMMAR]\n"
        if grammar.import_from_file is not None:
            output += f"IMPORT_FROM_FILE: {grammar.import_from_file}\n"
            return output

        output += "ELEMENTS:\n"
        for element in grammar.elements:
            output += f"- TAG: {element.tag}\n"
            if (
                element.property_is_composite is not None
                or element.property_prefix is not None
                or element.property_view_style is not None
            ):
                output += "  PROPERTIES:\n"
                if element.property_is_composite is not None:
                    output += f"    IS_COMPOSITE: {'True' if element.property_is_composite else 'False'}\n"
                if element.property_prefix is not None:
                    output += f"    PREFIX: {element.property_prefix}\n"
                if element.property_view_style is not None:
                    output += f"    VIEW_STYLE: {element.property_view_style}\n"

            output += "  FIELDS:\n"
            for gf in element.fields:
                output += self._write_grammar_field(gf)

            if element.relations:
                output += "  RELATIONS:\n"
                for rel in element.relations:
                    output += f"  - TYPE: {rel.relation_type}\n"
                    if rel.relation_role is not None:
                        output += f"    ROLE: {rel.relation_role}\n"
                    if rel.reverse_relation_role is not None:
                        output += (
                            f"    REVERSE_ROLE: {rel.reverse_relation_role}\n"
                        )
        return output

    @staticmethod
    def _write_grammar_field(gf: GrammarElementField) -> str:
        out = f"  - TITLE: {gf.title}\n"
        if gf.human_title is not None:
            out += f"    HUMAN_TITLE: {gf.human_title}\n"
        out += "    TYPE: "
        if gf.gef_type == "String":
            out += "String"
        elif gf.gef_type == "Tag":
            out += "Tag"
        elif gf.gef_type in ("SingleChoice", "MultipleChoice"):
            out += f"{gf.gef_type}({format_choice_options(gf.options)})"
        else:
            out += gf.gef_type
        out += "\n"
        out += f"    REQUIRED: {'True' if gf.required else 'False'}\n"
        return out

    def _write_element(
        self, element: SDocElement, grammar: DocumentGrammar
    ) -> str:
        if isinstance(element, DocumentFromFile):
            return f"[DOCUMENT_FROM_FILE]\nFILE: {element.file}\n\n"

        assert isinstance(element, SDocNode)
        node = element

        # Legacy [FREETEXT] rendering when self.legacy is True
        if self.legacy and node.node_type == "TEXT":
            uid_val = node.get_field_value("UID")
            mid_val = node.get_field_value("MID")
            stmt_val = node.get_field_value("STATEMENT") or ""
            if node.legacy_freetext or (uid_val is None and mid_val is None):
                return f"[FREETEXT]\n{_ensure_newline(stmt_val)}[/FREETEXT]\n\n"

        # Legacy [SECTION] ... [/SECTION] rendering when self.legacy is True
        if self.legacy and node.node_type == "SECTION" and node.is_composite:
            output = "[SECTION]\n"
            output += self._write_node_fields(node, grammar)
            output += "\n"
            for child in node.section_contents:
                output += self._write_element(child, grammar)
            output += "[/SECTION]\n\n"
            return output

        # Modern composite node [[NODE]] ... [[/NODE]] or standard node [NODE]
        output = ""
        if node.is_composite:
            output += f"[[{node.node_type}]]\n"
        else:
            output += f"[{node.node_type}]\n"

        output += self._write_node_fields(node, grammar)
        output += "\n"

        if node.is_composite:
            for child in node.section_contents:
                output += self._write_element(child, grammar)
            output += f"[[/{node.node_type}]]\n\n"

        return output

    def _write_node_fields(
        self, node: SDocNode, grammar: DocumentGrammar
    ) -> str:
        output = ""
        grammar_element: Optional[GrammarElement] = grammar.elements_by_type.get(
            node.node_type
        )

        ordered_fields: List[SDocNodeField] = []
        if grammar_element is not None:
            handled_names = set()
            for gf in grammar_element.fields:
                matching = node.get_fields(gf.title)
                ordered_fields.extend(matching)
                handled_names.add(gf.title)
            for f in node.fields:
                if f.field_name not in handled_names:
                    ordered_fields.append(f)
        else:
            ordered_fields = list(node.fields)

        for f in ordered_fields:
            if not f.value:
                continue
            multiline = is_field_multiline(
                grammar_element=grammar_element,
                field_name=f.field_name,
                value=f.value,
                explicit_multiline=f.multiline if f.multiline else None,
            )
            if multiline:
                output += f"{f.field_name}: >>>\n"
                output += _ensure_newline(f.value)
                output += "<<<\n"
            else:
                output += f"{f.field_name}: {f.value}\n"

        output += self._write_relations(node.relations)
        return output

    @staticmethod
    def _write_relations(relations: List[Reference]) -> str:
        if not relations:
            return ""
        output = "RELATIONS:\n"
        for ref in relations:
            output += f"- TYPE: {ref.ref_type}\n"
            if isinstance(ref, (ParentReqReference, ChildReqReference)):
                output += f"  VALUE: {ref.ref_uid}\n"
                if ref.role is not None:
                    output += f"  ROLE: {ref.role}\n"
            elif isinstance(ref, FileReference):
                if ref.role is not None:
                    output += f"  ROLE: {ref.role}\n"
                if ref.file_format is not None:
                    output += f"  FORMAT: {ref.file_format}\n"
                if (
                    ref.deprecated_value is not None
                    and ref.path == ref.deprecated_value
                ):
                    output += f"  VALUE: {ref.deprecated_value}\n"
                elif ref.path is not None:
                    output += f"  PATH: {ref.path}\n"
                if ref.element is not None:
                    output += f"  ELEMENT: {ref.element}\n"
                if ref.id is not None:
                    output += f"  ID: {ref.id}\n"
                if ref.line_range is not None:
                    output += f"  LINE_RANGE: {ref.line_range[0]}, {ref.line_range[1]}\n"
                if ref.function is not None:
                    output += f"  FUNCTION: {ref.function}\n"
                if ref.clazz is not None:
                    output += f"  CLASS: {ref.clazz}\n"
                if ref.hash is not None:
                    output += f"  HASH: {ref.hash}\n"
        return output


def write_sdoc(document: SDocDocument, *, legacy: bool = False) -> str:
    """Convenience function to serialize an `SDocDocument` to `.sdoc` text."""
    return SDocWriter(legacy=legacy).write_sdoc(document)


def write_sgra(grammar: DocumentGrammar) -> str:
    """Convenience function to serialize a `DocumentGrammar` to `.sgra` text."""
    return SDocWriter().write_sgra(grammar)

