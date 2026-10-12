"""
Bidirectional converter between StrictDoc AST (`SDocDocument` / `DocumentGrammar`) and JSON.
Supports both:
1. Canonical/Full AST JSON representation (lossless round-trip for 100% of StrictDoc features)
2. Shorthand/Legacy JSON representation (backward compatible with `test.json`:
   `SECTIONS`, `FREETEXT`, `REQUIREMENTS`, `REFS`, `SUBSECTIONS`, etc.)
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple, Union

from .grammar import (
    RESERVED_SINGLELINE_FIELDS,
    create_default_grammar,
    create_default_text_element,
    is_field_multiline,
    parse_choice_options,
    parse_text_parts,
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

# Reserved structural keys in a JSON node object (not treated as custom node fields)
_STRUCTURAL_NODE_KEYS = frozenset(
    {
        "NODE_TYPE",
        "TYPE",
        "IS_COMPOSITE",
        "LEGACY_SECTION",
        "LEGACY_FREETEXT",
        "FIELDS",
        "MULTILINE_FIELDS",
        "RELATIONS",
        "REFS",
        "NODES",
        "SECTION_CONTENTS",
        "CONTENT",
        "CHILDREN",
        "SECTIONS",
        "SUBSECTIONS",
        "REQUIREMENTS",
        "FREETEXT",
        "TEXT",
        "FILE",
        "INLINE_PARTS",
    }
)


def dict_to_grammar(
    data: Dict[str, Any], *, enable_mid: bool = False
) -> DocumentGrammar:
    """Converts a JSON dictionary representing `[GRAMMAR]` into a `DocumentGrammar`."""
    if "IMPORT_FROM_FILE" in data and data["IMPORT_FROM_FILE"]:
        return DocumentGrammar(
            elements=[],
            import_from_file=str(data["IMPORT_FROM_FILE"]),
            is_default=False,
        )

    raw_elements = data.get("ELEMENTS", [])
    elements: List[GrammarElement] = []
    for raw_el in raw_elements:
        tag = str(raw_el["TAG"])
        props = raw_el.get("PROPERTIES", {})
        prop_comp: Optional[bool] = None
        if "IS_COMPOSITE" in props and props["IS_COMPOSITE"] is not None:
            val = props["IS_COMPOSITE"]
            prop_comp = val if isinstance(val, bool) else (str(val) == "True")
        elif "IS_COMPOSITE" in raw_el and raw_el["IS_COMPOSITE"] is not None:
            val = raw_el["IS_COMPOSITE"]
            prop_comp = val if isinstance(val, bool) else (str(val) == "True")

        prop_prefix: Optional[str] = props.get("PREFIX", raw_el.get("PREFIX"))
        prop_view_style: Optional[str] = props.get(
            "VIEW_STYLE", raw_el.get("VIEW_STYLE")
        )

        fields: List[GrammarElementField] = []
        for raw_f in raw_el.get("FIELDS", []):
            f_title = str(raw_f["TITLE"])
            f_human = raw_f.get("HUMAN_TITLE")
            raw_type = str(raw_f.get("TYPE", "String"))
            options: List[str] = [str(o) for o in raw_f.get("OPTIONS", [])]
            if raw_type.startswith("SingleChoice(") and raw_type.endswith(")"):
                options = parse_choice_options(
                    raw_type[len("SingleChoice(") : -1]
                )
                f_type = "SingleChoice"
            elif raw_type.startswith("MultipleChoice(") and raw_type.endswith(
                ")"
            ):
                options = parse_choice_options(
                    raw_type[len("MultipleChoice(") : -1]
                )
                f_type = "MultipleChoice"
            else:
                f_type = raw_type

            req_val = raw_f.get("REQUIRED", False)
            req_bool = (
                req_val
                if isinstance(req_val, bool)
                else (str(req_val) == "True")
            )
            fields.append(
                GrammarElementField(
                    title=f_title,
                    gef_type=f_type,
                    required=req_bool,
                    human_title=str(f_human) if f_human is not None else None,
                    options=options,
                )
            )

        relations: List[GrammarElementRelation] = []
        for raw_r in raw_el.get("RELATIONS", []):
            relations.append(
                GrammarElementRelation(
                    relation_type=str(raw_r["TYPE"]),
                    relation_role=raw_r.get("ROLE"),
                    reverse_relation_role=raw_r.get("REVERSE_ROLE"),
                )
            )

        elements.append(
            GrammarElement(
                tag=tag,
                property_is_composite=prop_comp,
                property_prefix=prop_prefix,
                property_view_style=prop_view_style,
                fields=fields,
                relations=relations,
            )
        )

    grammar = DocumentGrammar(
        elements=elements,
        import_from_file=None,
        is_default=False,
    )
    if elements and not grammar.has_text_element():
        grammar.elements.insert(
            0, create_default_text_element(enable_mid=enable_mid)
        )
    return grammar


def _parse_json_relation(raw_rel: Dict[str, Any]) -> Reference:
    rel_type = str(raw_rel.get("TYPE", "Parent"))
    role = raw_rel.get("ROLE")
    role_str = str(role) if role is not None else None

    if rel_type == "Parent":
        return ParentReqReference(
            ref_uid=str(raw_rel.get("VALUE", raw_rel.get("UID", ""))),
            role=role_str,
        )
    if rel_type == "Child":
        return ChildReqReference(
            ref_uid=str(raw_rel.get("VALUE", raw_rel.get("UID", ""))),
            role=role_str,
        )
    if rel_type == "File":
        raw_lr = raw_rel.get("LINE_RANGE")
        line_range: Optional[Tuple[int, int]] = None
        if isinstance(raw_lr, (list, tuple)) and len(raw_lr) == 2:
            line_range = (int(raw_lr[0]), int(raw_lr[1]))
        elif isinstance(raw_lr, str) and "," in raw_lr:
            parts = [p.strip() for p in raw_lr.split(",")]
            if len(parts) == 2 and all(p.isdigit() for p in parts):
                line_range = (int(parts[0]), int(parts[1]))

        return FileReference(
            path=raw_rel.get("PATH"),
            role=role_str,
            file_format=raw_rel.get("FORMAT"),
            deprecated_value=raw_rel.get("VALUE"),
            element=raw_rel.get("ELEMENT"),
            id=raw_rel.get("ID"),
            line_range=line_range,
            function=raw_rel.get("FUNCTION"),
            clazz=raw_rel.get("CLASS"),
            hash=raw_rel.get("HASH"),
        )
    raise ValueError(f"Unsupported relation TYPE in JSON: '{rel_type}'")


def _dict_to_element(
    raw: Dict[str, Any],
    grammar: DocumentGrammar,
    *,
    default_node_type: str = "REQUIREMENT",
) -> SDocElement:
    node_type = str(
        raw.get("NODE_TYPE") or raw.get("TYPE") or default_node_type
    )

    if node_type == "DOCUMENT_FROM_FILE" or (
        "FILE" in raw and "TITLE" not in raw and "STATEMENT" not in raw
    ):
        return DocumentFromFile(file=str(raw["FILE"]))

    if node_type == "FREETEXT":
        stmt = str(
            raw.get("STATEMENT")
            or raw.get("FREETEXT")
            or raw.get("TEXT")
            or raw.get("CONTENT")
            or ""
        )
        return SDocNode(
            node_type="TEXT",
            fields=[
                SDocNodeField(
                    field_name="STATEMENT",
                    value=stmt,
                    multiline=True,
                    parts=parse_text_parts(stmt),
                )
            ],
            is_composite=False,
            legacy_freetext=True,
        )

    grammar_el = grammar.elements_by_type.get(node_type)

    # Determine child elements (if any)
    children: List[SDocElement] = []

    # 1. Shorthand FREETEXT or TEXT on a section/composite node
    for ft_key in ("FREETEXT", "TEXT"):
        if ft_key in raw and raw[ft_key] is not None:
            ft_val = raw[ft_key]
            if isinstance(ft_val, str):
                children.append(
                    SDocNode(
                        node_type="TEXT",
                        fields=[
                            SDocNodeField(
                                field_name="STATEMENT",
                                value=ft_val,
                                multiline=True,
                                parts=parse_text_parts(ft_val),
                            )
                        ],
                        is_composite=False,
                        legacy_freetext=(ft_key == "FREETEXT"),
                    )
                )
            elif isinstance(ft_val, list):
                for item in ft_val:
                    if isinstance(item, str):
                        children.append(
                            SDocNode(
                                node_type="TEXT",
                                fields=[
                                    SDocNodeField(
                                        field_name="STATEMENT",
                                        value=item,
                                        multiline=True,
                                        parts=parse_text_parts(item),
                                    )
                                ],
                                is_composite=False,
                                legacy_freetext=(ft_key == "FREETEXT"),
                            )
                        )
                    elif isinstance(item, dict):
                        children.append(
                            _dict_to_element(
                                item, grammar, default_node_type="TEXT"
                            )
                        )

    # 2. Explicit polymorphic children list (NODES / SECTION_CONTENTS / CONTENT / CHILDREN)
    for list_key in ("NODES", "SECTION_CONTENTS", "CONTENT", "CHILDREN"):
        if list_key in raw and isinstance(raw[list_key], list):
            for child_raw in raw[list_key]:
                children.append(
                    _dict_to_element(
                        child_raw, grammar, default_node_type="REQUIREMENT"
                    )
                )

    # 3. Shorthand REQUIREMENTS list
    if "REQUIREMENTS" in raw and isinstance(raw["REQUIREMENTS"], list):
        for req_raw in raw["REQUIREMENTS"]:
            children.append(
                _dict_to_element(
                    req_raw, grammar, default_node_type="REQUIREMENT"
                )
            )

    # 4. Shorthand SECTIONS or SUBSECTIONS list
    for sec_key in ("SECTIONS", "SUBSECTIONS"):
        if sec_key in raw and isinstance(raw[sec_key], list):
            for sec_raw in raw[sec_key]:
                children.append(
                    _dict_to_element(
                        sec_raw, grammar, default_node_type="SECTION"
                    )
                )

    is_composite = bool(
        raw.get("IS_COMPOSITE")
        if "IS_COMPOSITE" in raw
        else (
            (grammar_el and grammar_el.property_is_composite)
            or node_type in ("SECTION", "COMPOSITE_REQUIREMENT")
            or len(children) > 0
        )
    )

    multiline_set = set(raw.get("MULTILINE_FIELDS", []))

    # Extract node fields
    fields: List[SDocNodeField] = []

    if "FIELDS" in raw:
        raw_fields = raw["FIELDS"]
        if isinstance(raw_fields, list):
            for rf in raw_fields:
                fname = str(rf["NAME"] if "NAME" in rf else rf["FIELD_NAME"])
                fval = str(rf["VALUE"])
                fmulti = rf.get("MULTILINE")
                is_multi = is_field_multiline(
                    grammar_el,
                    fname,
                    fval,
                    explicit_multiline=(
                        bool(fmulti)
                        if fmulti is not None
                        else (True if fname in multiline_set else None)
                    ),
                )
                fields.append(
                    SDocNodeField(
                        field_name=fname,
                        value=fval,
                        multiline=is_multi,
                        parts=parse_text_parts(fval),
                    )
                )
        elif isinstance(raw_fields, dict):
            for k, v in raw_fields.items():
                if v is None:
                    continue
                _append_json_field(
                    fields, k, v, grammar_el, multiline_set=multiline_set
                )

    # Also extract direct field keys on the node dict
    for k, v in raw.items():
        if k in _STRUCTURAL_NODE_KEYS or v is None:
            continue
        fname = "PREFIX" if (node_type == "SECTION" and k == "REQ_PREFIX") else k
        _append_json_field(
            fields, fname, v, grammar_el, multiline_set=multiline_set
        )

    # Extract relations (RELATIONS or REFS)
    relations: List[Reference] = []
    for rel_key in ("RELATIONS", "REFS"):
        if rel_key in raw and isinstance(raw[rel_key], list):
            for r in raw[rel_key]:
                relations.append(_parse_json_relation(r))

    return SDocNode(
        node_type=node_type,
        fields=fields,
        relations=relations,
        section_contents=children,
        is_composite=is_composite,
        legacy_section=bool(raw.get("LEGACY_SECTION", False)),
        legacy_freetext=bool(raw.get("LEGACY_FREETEXT", False)),
    )


def _append_json_field(
    fields: List[SDocNodeField],
    field_name: str,
    raw_value: Any,
    grammar_el: Optional[GrammarElement],
    *,
    multiline_set: set[str],
) -> None:
    # Support multiple COMMENT fields passed as a list of strings
    if isinstance(raw_value, list):
        if field_name == "COMMENT":
            for item in raw_value:
                sval = str(item)
                fields.append(
                    SDocNodeField(
                        field_name="COMMENT",
                        value=sval,
                        multiline=is_field_multiline(
                            grammar_el, "COMMENT", sval, explicit_multiline=True
                        ),
                        parts=parse_text_parts(sval),
                    )
                )
            return
        # For MultipleChoice or Tag fields passed as a JSON list, join with ", "
        sval = ", ".join(str(x) for x in raw_value)
    else:
        sval = str(raw_value)

    if not sval:
        return

    explicit_multi = True if field_name in multiline_set else None
    is_multi = is_field_multiline(
        grammar_el, field_name, sval, explicit_multiline=explicit_multi
    )
    if field_name in RESERVED_SINGLELINE_FIELDS:
        is_multi = False

    fields.append(
        SDocNodeField(
            field_name=field_name,
            value=sval,
            multiline=is_multi,
            parts=parse_text_parts(sval),
        )
    )


def dict_to_sdoc(data: Dict[str, Any]) -> SDocDocument:
    """
    Converts a Python dictionary (loaded from JSON) into an `SDocDocument` AST.
    Supports both canonical AST JSON and shorthand/legacy JSON (`test.json`).
    """
    title = str(data.get("TITLE", "Untitled Document"))
    mid = str(data["MID"]) if data.get("MID") is not None else None

    config = DocumentConfig()
    if data.get("UID") is not None:
        config.uid = str(data["UID"])
    if data.get("VERSION") is not None:
        config.version = str(data["VERSION"])
    if data.get("DATE") is not None:
        config.date = str(data["DATE"])
    if data.get("CLASSIFICATION") is not None:
        config.classification = str(data["CLASSIFICATION"])
    if data.get("PREFIX") is not None:
        config.prefix = str(data["PREFIX"])
        config.prefix_tag = "PREFIX"
    elif data.get("REQ_PREFIX") is not None:
        config.prefix = str(data["REQ_PREFIX"])
        config.prefix_tag = "REQ_PREFIX"
    if data.get("ROOT") is not None:
        r_val = data["ROOT"]
        config.root = r_val if isinstance(r_val, bool) else (str(r_val) == "True")

    if "OPTIONS" in data and isinstance(data["OPTIONS"], dict):
        raw_opts = data["OPTIONS"]
        opts = DocumentOptions()
        if "ENABLE_MID" in raw_opts and raw_opts["ENABLE_MID"] is not None:
            em = raw_opts["ENABLE_MID"]
            opts.enable_mid = em if isinstance(em, bool) else (str(em) == "True")
        if raw_opts.get("RELATION_FIELD") is not None:
            opts.relation_field = str(raw_opts["RELATION_FIELD"])
        if raw_opts.get("MARKUP") is not None:
            opts.markup = str(raw_opts["MARKUP"])
        if raw_opts.get("AUTO_LEVELS") is not None:
            al = raw_opts["AUTO_LEVELS"]
            if isinstance(al, bool):
                opts.auto_levels = "On" if al else "Off"
            else:
                opts.auto_levels = str(al)
        if raw_opts.get("LAYOUT") is not None:
            opts.layout = str(raw_opts["LAYOUT"])
        if raw_opts.get("VIEW_STYLE") is not None:
            opts.view_style_tag = "VIEW_STYLE"
            opts.view_style = str(raw_opts["VIEW_STYLE"])
        elif raw_opts.get("REQUIREMENT_STYLE") is not None:
            opts.view_style_tag = "REQUIREMENT_STYLE"
            opts.view_style = str(raw_opts["REQUIREMENT_STYLE"])
        if raw_opts.get("NODE_IN_TOC") is not None:
            opts.node_in_toc_tag = "NODE_IN_TOC"
            nit = raw_opts["NODE_IN_TOC"]
            opts.node_in_toc = (
                ("True" if nit else "False")
                if isinstance(nit, bool)
                else str(nit)
            )
        elif raw_opts.get("REQUIREMENT_IN_TOC") is not None:
            opts.node_in_toc_tag = "REQUIREMENT_IN_TOC"
            rit = raw_opts["REQUIREMENT_IN_TOC"]
            opts.node_in_toc = (
                ("True" if rit else "False")
                if isinstance(rit, bool)
                else str(rit)
            )
        if raw_opts.get("DEFAULT_VIEW") is not None:
            opts.default_view = str(raw_opts["DEFAULT_VIEW"])
        config.options = opts

    if "METADATA" in data and isinstance(data["METADATA"], dict):
        config.metadata = {str(k): str(v) for k, v in data["METADATA"].items()}

    views: List[ViewElement] = []
    if "VIEWS" in data and isinstance(data["VIEWS"], list):
        for raw_v in data["VIEWS"]:
            v_tags: List[ViewElementTags] = []
            for raw_t in raw_v.get("TAGS", []):
                vis_fields = [
                    ViewElementField(
                        name=str(vf["NAME"]),
                        placement=(
                            str(vf["PLACEMENT"])
                            if vf.get("PLACEMENT") is not None
                            else None
                        ),
                    )
                    for vf in raw_t.get("VISIBLE_FIELDS", [])
                ]
                v_tags.append(
                    ViewElementTags(
                        object_type=str(raw_t["OBJECT_TYPE"]),
                        visible_fields=vis_fields,
                    )
                )
            views.append(
                ViewElement(
                    view_id=str(raw_v["ID"]),
                    name=(
                        str(raw_v["NAME"])
                        if raw_v.get("NAME") is not None
                        else None
                    ),
                    tags=v_tags,
                    hidden_tags=[
                        str(ht) for ht in raw_v.get("HIDDEN_TAGS", [])
                    ],
                )
            )

    if "GRAMMAR" in data and isinstance(data["GRAMMAR"], dict):
        grammar = dict_to_grammar(
            data["GRAMMAR"], enable_mid=config.enable_mid
        )
    else:
        grammar = create_default_grammar(enable_mid=config.enable_mid)

    section_contents: List[SDocElement] = []

    # Top-level FREETEXT or TEXT
    for ft_key in ("FREETEXT", "TEXT"):
        if ft_key in data and data[ft_key] is not None:
            ft_val = data[ft_key]
            if isinstance(ft_val, str):
                section_contents.append(
                    SDocNode(
                        node_type="TEXT",
                        fields=[
                            SDocNodeField(
                                field_name="STATEMENT",
                                value=ft_val,
                                multiline=True,
                                parts=parse_text_parts(ft_val),
                            )
                        ],
                        is_composite=False,
                        legacy_freetext=(ft_key == "FREETEXT"),
                    )
                )
            elif isinstance(ft_val, list):
                for item in ft_val:
                    if isinstance(item, str):
                        section_contents.append(
                            SDocNode(
                                node_type="TEXT",
                                fields=[
                                    SDocNodeField(
                                        field_name="STATEMENT",
                                        value=item,
                                        multiline=True,
                                        parts=parse_text_parts(item),
                                    )
                                ],
                                is_composite=False,
                                legacy_freetext=(ft_key == "FREETEXT"),
                            )
                        )
                    elif isinstance(item, dict):
                        section_contents.append(
                            _dict_to_element(
                                item, grammar, default_node_type="TEXT"
                            )
                        )

    # Top-level NODES / SECTION_CONTENTS / CONTENT
    for list_key in ("NODES", "SECTION_CONTENTS", "CONTENT"):
        if list_key in data and isinstance(data[list_key], list):
            for item in data[list_key]:
                section_contents.append(
                    _dict_to_element(
                        item, grammar, default_node_type="REQUIREMENT"
                    )
                )

    # Top-level REQUIREMENTS
    if "REQUIREMENTS" in data and isinstance(data["REQUIREMENTS"], list):
        for req in data["REQUIREMENTS"]:
            section_contents.append(
                _dict_to_element(req, grammar, default_node_type="REQUIREMENT")
            )

    # Top-level SECTIONS
    if "SECTIONS" in data and isinstance(data["SECTIONS"], list):
        for sec in data["SECTIONS"]:
            section_contents.append(
                _dict_to_element(sec, grammar, default_node_type="SECTION")
            )

    return SDocDocument(
        title=title,
        mid=mid,
        config=config,
        views=views,
        grammar=grammar,
        section_contents=section_contents,
    )


def _element_to_dict(
    element: SDocElement, *, legacy_json: bool = False
) -> Dict[str, Any]:
    if isinstance(element, DocumentFromFile):
        return element.to_dict()

    assert isinstance(element, SDocNode)
    node = element

    if legacy_json and node.node_type == "SECTION":
        sec_dict: Dict[str, Any] = {}
        for f in node.fields:
            sec_dict[f.field_name] = f.value
        freetexts: List[str] = []
        requirements: List[Dict[str, Any]] = []
        subsections: List[Dict[str, Any]] = []
        other_nodes: List[Dict[str, Any]] = []
        for child in node.section_contents:
            if isinstance(child, SDocNode) and child.node_type == "TEXT":
                stmt = child.get_field_value("STATEMENT")
                if stmt is not None and child.get_field_value("UID") is None:
                    freetexts.append(stmt)
                else:
                    other_nodes.append(_element_to_dict(child, legacy_json=True))
            elif (
                isinstance(child, SDocNode) and child.node_type == "REQUIREMENT"
            ):
                requirements.append(_element_to_dict(child, legacy_json=True))
            elif isinstance(child, SDocNode) and child.node_type == "SECTION":
                subsections.append(_element_to_dict(child, legacy_json=True))
            else:
                other_nodes.append(_element_to_dict(child, legacy_json=True))
        if len(freetexts) == 1:
            sec_dict["FREETEXT"] = freetexts[0]
        elif len(freetexts) > 1:
            sec_dict["FREETEXT"] = freetexts
        if requirements:
            sec_dict["REQUIREMENTS"] = requirements
        if subsections:
            sec_dict["SECTIONS"] = subsections
        if other_nodes:
            sec_dict["NODES"] = other_nodes
        return sec_dict

    if legacy_json and node.node_type == "REQUIREMENT" and not node.is_composite:
        req_dict: Dict[str, Any] = {}
        comments: List[str] = []
        for f in node.fields:
            if f.field_name == "COMMENT":
                comments.append(f.value)
            else:
                req_dict[f.field_name] = f.value
        if len(comments) == 1:
            req_dict["COMMENT"] = comments[0]
        elif len(comments) > 1:
            req_dict["COMMENT"] = comments
        if node.relations:
            req_dict["RELATIONS"] = [r.to_dict() for r in node.relations]
        return req_dict

    # Canonical AST representation
    d: Dict[str, Any] = {"NODE_TYPE": node.node_type}
    if node.is_composite:
        d["IS_COMPOSITE"] = True

    comments_list: List[str] = []
    inline_parts_map: Dict[str, List[Dict[str, Any]]] = {}

    for f in node.fields:
        if f.field_name == "COMMENT":
            comments_list.append(f.value)
        else:
            d[f.field_name] = f.value
        # Record structured inline links / anchors if present
        special_parts = [
            p.to_dict()
            for p in f.parts
            if isinstance(p, (InlineLink, Anchor))
        ]
        if special_parts:
            inline_parts_map.setdefault(f.field_name, []).extend(special_parts)

    if len(comments_list) == 1:
        d["COMMENT"] = comments_list[0]
    elif len(comments_list) > 1:
        d["COMMENT"] = comments_list

    if inline_parts_map:
        d["INLINE_PARTS"] = inline_parts_map

    if node.relations:
        d["RELATIONS"] = [r.to_dict() for r in node.relations]

    if node.section_contents:
        d["NODES"] = [
            _element_to_dict(c, legacy_json=legacy_json)
            for c in node.section_contents
        ]

    return d


def sdoc_to_dict(
    document: SDocDocument, *, legacy_json: bool = False
) -> Dict[str, Any]:
    """Converts an `SDocDocument` AST into a JSON-serializable Python dictionary."""
    result: Dict[str, Any] = {}
    if document.mid is not None:
        result["MID"] = document.mid
    result["TITLE"] = document.title

    cfg = document.config
    if cfg.uid is not None:
        result["UID"] = cfg.uid
    if cfg.version is not None:
        result["VERSION"] = cfg.version
    if cfg.date is not None:
        result["DATE"] = cfg.date
    if cfg.classification is not None:
        result["CLASSIFICATION"] = cfg.classification
    if cfg.prefix is not None:
        result[cfg.prefix_tag] = cfg.prefix
    if cfg.root is not None:
        result["ROOT"] = cfg.root

    if cfg.options is not None and not cfg.options.is_empty():
        result["OPTIONS"] = cfg.options.to_dict()

    if cfg.metadata:
        result["METADATA"] = dict(cfg.metadata)

    if document.views:
        result["VIEWS"] = [v.to_dict() for v in document.views]

    if document.grammar is not None and not document.grammar.is_default:
        result["GRAMMAR"] = document.grammar.to_dict()

    if legacy_json:
        top_freetexts: List[str] = []
        top_sections: List[Dict[str, Any]] = []
        top_requirements: List[Dict[str, Any]] = []
        top_other: List[Dict[str, Any]] = []

        for el in document.section_contents:
            if isinstance(el, SDocNode) and el.node_type == "TEXT":
                stmt = el.get_field_value("STATEMENT")
                if stmt is not None and el.get_field_value("UID") is None:
                    top_freetexts.append(stmt)
                else:
                    top_other.append(_element_to_dict(el, legacy_json=True))
            elif isinstance(el, SDocNode) and el.node_type == "SECTION":
                top_sections.append(_element_to_dict(el, legacy_json=True))
            elif isinstance(el, SDocNode) and el.node_type == "REQUIREMENT":
                top_requirements.append(_element_to_dict(el, legacy_json=True))
            else:
                top_other.append(_element_to_dict(el, legacy_json=True))

        if len(top_freetexts) == 1:
            result["FREETEXT"] = top_freetexts[0]
        elif len(top_freetexts) > 1:
            result["FREETEXT"] = top_freetexts
        if top_requirements:
            result["REQUIREMENTS"] = top_requirements
        if top_sections:
            result["SECTIONS"] = top_sections
        if top_other:
            result["NODES"] = top_other
    else:
        result["NODES"] = [
            _element_to_dict(el, legacy_json=False)
            for el in document.section_contents
        ]

    return result


def json_to_sdoc_document(json_data: Union[str, Dict[str, Any]]) -> SDocDocument:
    """Parses a JSON string or dict into an `SDocDocument` AST."""
    if isinstance(json_data, str):
        parsed = json.loads(json_data)
    else:
        parsed = json_data
    if not isinstance(parsed, dict):
        raise ValueError("Top-level JSON value must be an object/dictionary")
    return dict_to_sdoc(parsed)


def sdoc_document_to_json(
    document: SDocDocument, *, indent: int = 4, legacy_json: bool = False
) -> str:
    """Serializes an `SDocDocument` AST into a formatted JSON string."""
    d = sdoc_to_dict(document, legacy_json=legacy_json)
    return json.dumps(d, indent=indent, ensure_ascii=False) + "\n"

