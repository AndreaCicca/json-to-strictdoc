"""
Data models (AST) for the StrictDoc (.sdoc and .sgra) specification.
Covers 100% of StrictDoc's grammar:
- SDocDocument, DocumentConfig, DocumentOptions, DocumentView, ViewElement
- DocumentGrammar, GrammarElement, GrammarElementField, GrammarElementRelation
- SDocNode (including TEXT, REQUIREMENT, custom nodes, and composite [[NODE]] / [[SECTION]])
- DocumentFromFile
- References (ParentReqReference, ChildReqReference, FileReference)
- Text parts (InlineLink, Anchor)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union


@dataclass
class InlineLink:
    """Represents an inline link `[LINK: UID]` inside a text field."""

    value: str

    def to_sdoc(self) -> str:
        return f"[LINK: {self.value}]"

    def to_dict(self) -> Dict[str, Any]:
        return {"TYPE": "InlineLink", "VALUE": self.value}


@dataclass
class Anchor:
    """Represents an anchor `[ANCHOR: UID]` or `[ANCHOR: UID, Title]` inside a text field."""

    value: str
    title: Optional[str] = None

    def to_sdoc(self) -> str:
        if self.title is not None:
            return f"[ANCHOR: {self.value}, {self.title}]"
        return f"[ANCHOR: {self.value}]"

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {"TYPE": "Anchor", "VALUE": self.value}
        if self.title is not None:
            res["TITLE"] = self.title
        return res


TextPart = Union[str, InlineLink, Anchor]


@dataclass
class DocumentOptions:
    """Represents the `OPTIONS:` block inside `[DOCUMENT]`."""

    enable_mid: Optional[bool] = None
    relation_field: Optional[str] = None
    markup: Optional[str] = None  # RST | Text | HTML | Markdown
    auto_levels: Optional[str] = None  # On | Off
    layout: Optional[str] = None  # Default | Website
    view_style: Optional[str] = None  # Plain | Inline | Simple | Narrative | Table | Zebra
    node_in_toc: Optional[str] = None  # True | False
    default_view: Optional[str] = None
    # Preserve legacy option tag names if parsed from legacy files
    view_style_tag: str = "VIEW_STYLE"
    node_in_toc_tag: str = "NODE_IN_TOC"

    def is_empty(self) -> bool:
        return all(
            v is None
            for v in (
                self.enable_mid,
                self.relation_field,
                self.markup,
                self.auto_levels,
                self.layout,
                self.view_style,
                self.node_in_toc,
                self.default_view,
            )
        )

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        if self.enable_mid is not None:
            result["ENABLE_MID"] = self.enable_mid
        if self.relation_field is not None:
            result["RELATION_FIELD"] = self.relation_field
        if self.markup is not None:
            result["MARKUP"] = self.markup
        if self.auto_levels is not None:
            result["AUTO_LEVELS"] = self.auto_levels
        if self.layout is not None:
            result["LAYOUT"] = self.layout
        if self.view_style is not None:
            result[self.view_style_tag] = self.view_style
        if self.node_in_toc is not None:
            result[self.node_in_toc_tag] = self.node_in_toc
        if self.default_view is not None:
            result["DEFAULT_VIEW"] = self.default_view
        return result


@dataclass
class DocumentConfig:
    """Represents the configuration fields of a `[DOCUMENT]` block."""

    uid: Optional[str] = None
    version: Optional[str] = None
    date: Optional[str] = None
    classification: Optional[str] = None
    prefix: Optional[str] = None
    prefix_tag: str = "PREFIX"  # Can be PREFIX or REQ_PREFIX
    root: Optional[bool] = None
    options: Optional[DocumentOptions] = None
    metadata: Dict[str, str] = field(default_factory=dict)

    @property
    def enable_mid(self) -> bool:
        return bool(self.options and self.options.enable_mid)


@dataclass
class ViewElementField:
    """Represents a field entry inside `VISIBLE_FIELDS:` of a view tag."""

    name: str
    placement: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"NAME": self.name}
        if self.placement is not None:
            d["PLACEMENT"] = self.placement
        return d


@dataclass
class ViewElementTags:
    """Represents an object type entry inside `TAGS:` of a view."""

    object_type: str
    visible_fields: List[ViewElementField] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "OBJECT_TYPE": self.object_type,
            "VISIBLE_FIELDS": [f.to_dict() for f in self.visible_fields],
        }


@dataclass
class ViewElement:
    """Represents a single view inside `VIEWS:`."""

    view_id: str
    name: Optional[str] = None
    tags: List[ViewElementTags] = field(default_factory=list)
    hidden_tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"ID": self.view_id}
        if self.name is not None:
            d["NAME"] = self.name
        d["TAGS"] = [t.to_dict() for t in self.tags]
        if self.hidden_tags:
            d["HIDDEN_TAGS"] = list(self.hidden_tags)
        return d


@dataclass
class GrammarElementField:
    """Represents a field definition inside `[GRAMMAR]` -> `ELEMENTS` -> `FIELDS`."""

    title: str
    gef_type: str = "String"  # String | SingleChoice | MultipleChoice | Tag
    required: bool = False
    human_title: Optional[str] = None
    options: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"TITLE": self.title}
        if self.human_title is not None:
            d["HUMAN_TITLE"] = self.human_title
        d["TYPE"] = self.gef_type
        if self.options:
            d["OPTIONS"] = list(self.options)
        d["REQUIRED"] = self.required
        return d


@dataclass
class GrammarElementRelation:
    """Represents a relation definition inside `[GRAMMAR]` -> `ELEMENTS` -> `RELATIONS`."""

    relation_type: str  # Parent | Child | File
    relation_role: Optional[str] = None
    reverse_relation_role: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"TYPE": self.relation_type}
        if self.relation_role is not None:
            d["ROLE"] = self.relation_role
        if self.reverse_relation_role is not None:
            d["REVERSE_ROLE"] = self.reverse_relation_role
        return d


@dataclass
class GrammarElement:
    """Represents a `- TAG: ...` element definition inside `[GRAMMAR]`."""

    tag: str
    property_is_composite: Optional[bool] = None
    property_prefix: Optional[str] = None
    property_view_style: Optional[str] = None
    fields: List[GrammarElementField] = field(default_factory=list)
    relations: List[GrammarElementRelation] = field(default_factory=list)

    @property
    def fields_map(self) -> Dict[str, GrammarElementField]:
        return {f.title: f for f in self.fields}

    def get_field_titles(self) -> List[str]:
        return [f.title for f in self.fields]

    def has_relation_type_role(
        self, relation_type: str, relation_role: Optional[str]
    ) -> bool:
        for rel in self.relations:
            if rel.relation_type == relation_type and rel.relation_role == relation_role:
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"TAG": self.tag}
        props: Dict[str, Any] = {}
        if self.property_is_composite is not None:
            props["IS_COMPOSITE"] = self.property_is_composite
        if self.property_prefix is not None:
            props["PREFIX"] = self.property_prefix
        if self.property_view_style is not None:
            props["VIEW_STYLE"] = self.property_view_style
        if props:
            d["PROPERTIES"] = props
        d["FIELDS"] = [f.to_dict() for f in self.fields]
        if self.relations:
            d["RELATIONS"] = [r.to_dict() for r in self.relations]
        return d


@dataclass
class DocumentGrammar:
    """Represents a `[GRAMMAR]` block (inline in `.sdoc` or standalone `.sgra`)."""

    elements: List[GrammarElement] = field(default_factory=list)
    import_from_file: Optional[str] = None
    is_default: bool = True

    @property
    def elements_by_type(self) -> Dict[str, GrammarElement]:
        return {el.tag: el for el in self.elements}

    @property
    def registered_elements(self) -> set[str]:
        return {el.tag for el in self.elements}

    def has_text_element(self) -> bool:
        return any(el.tag == "TEXT" for el in self.elements)

    def to_dict(self) -> Dict[str, Any]:
        if self.import_from_file is not None:
            return {"IMPORT_FROM_FILE": self.import_from_file}
        return {"ELEMENTS": [el.to_dict() for el in self.elements]}


@dataclass
class Reference:
    """Base class for node relations in `RELATIONS:`."""

    ref_type: str  # Parent | Child | File
    role: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        raise NotImplementedError


@dataclass
class ParentReqReference(Reference):
    """Represents a `Parent` requirement relation."""

    ref_uid: str = ""

    def __init__(self, ref_uid: str, role: Optional[str] = None) -> None:
        super().__init__(ref_type="Parent", role=role)
        self.ref_uid = ref_uid

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"TYPE": "Parent", "VALUE": self.ref_uid}
        if self.role is not None:
            d["ROLE"] = self.role
        return d


@dataclass
class ChildReqReference(Reference):
    """Represents a `Child` requirement relation."""

    ref_uid: str = ""

    def __init__(self, ref_uid: str, role: Optional[str] = None) -> None:
        super().__init__(ref_type="Child", role=role)
        self.ref_uid = ref_uid

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"TYPE": "Child", "VALUE": self.ref_uid}
        if self.role is not None:
            d["ROLE"] = self.role
        return d


@dataclass
class FileReference(Reference):
    """Represents a `File` relation with all supported file entry properties."""

    file_format: Optional[str] = None
    path: Optional[str] = None
    deprecated_value: Optional[str] = None
    element: Optional[str] = None
    id: Optional[str] = None
    line_range: Optional[Tuple[int, int]] = None
    function: Optional[str] = None
    clazz: Optional[str] = None
    hash: Optional[str] = None

    def __init__(
        self,
        path: Optional[str] = None,
        *,
        role: Optional[str] = None,
        file_format: Optional[str] = None,
        deprecated_value: Optional[str] = None,
        element: Optional[str] = None,
        id: Optional[str] = None,
        line_range: Optional[Tuple[int, int]] = None,
        function: Optional[str] = None,
        clazz: Optional[str] = None,
        hash: Optional[str] = None,
    ) -> None:
        super().__init__(ref_type="File", role=role)
        self.file_format = file_format
        self.deprecated_value = deprecated_value
        self.path = path if path is not None else deprecated_value
        self.element = element
        self.id = id
        self.line_range = line_range
        self.function = function
        self.clazz = clazz
        self.hash = hash

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"TYPE": "File"}
        if self.role is not None:
            d["ROLE"] = self.role
        if self.file_format is not None:
            d["FORMAT"] = self.file_format
        if self.deprecated_value is not None and self.path == self.deprecated_value:
            d["VALUE"] = self.deprecated_value
        elif self.path is not None:
            d["PATH"] = self.path
        if self.element is not None:
            d["ELEMENT"] = self.element
        if self.id is not None:
            d["ID"] = self.id
        if self.line_range is not None:
            d["LINE_RANGE"] = f"{self.line_range[0]}, {self.line_range[1]}"
        if self.function is not None:
            d["FUNCTION"] = self.function
        if self.clazz is not None:
            d["CLASS"] = self.clazz
        if self.hash is not None:
            d["HASH"] = self.hash
        return d


@dataclass
class SDocNodeField:
    """Represents a single field on an `SDocNode`."""

    field_name: str
    value: str
    multiline: bool = False
    parts: List[TextPart] = field(default_factory=list)


@dataclass
class DocumentFromFile:
    """Represents a `[DOCUMENT_FROM_FILE]` inclusion block."""

    file: str
    line_start: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "NODE_TYPE": "DOCUMENT_FROM_FILE",
            "FILE": self.file,
        }


@dataclass
class SDocNode:
    """
    Represents any node in a StrictDoc document:
    - Standard nodes: `[TEXT]`, `[REQUIREMENT]`, `[CUSTOM_NODE]`
    - Composite nodes: `[[SECTION]]`, `[[COMPOSITE_NODE]]`
    - Legacy constructs: `[SECTION]...[/SECTION]`, `[FREETEXT]...[/FREETEXT]`
    """

    node_type: str
    fields: List[SDocNodeField] = field(default_factory=list)
    relations: List[Reference] = field(default_factory=list)
    section_contents: List[SDocElement] = field(default_factory=list)
    is_composite: bool = False
    legacy_section: bool = False
    legacy_freetext: bool = False
    line_start: Optional[int] = None

    def get_field(self, name: str) -> Optional[SDocNodeField]:
        for f in self.fields:
            if f.field_name == name:
                return f
        return None

    def get_field_value(self, name: str) -> Optional[str]:
        f = self.get_field(name)
        return f.value if f is not None else None

    def get_fields(self, name: str) -> List[SDocNodeField]:
        return [f for f in self.fields if f.field_name == name]

    def set_field(
        self, name: str, value: str, multiline: Optional[bool] = None
    ) -> None:
        for f in self.fields:
            if f.field_name == name:
                f.value = value
                if multiline is not None:
                    f.multiline = multiline
                return
        self.fields.append(
            SDocNodeField(
                field_name=name,
                value=value,
                multiline=bool(multiline) if multiline is not None else ("\n" in value),
            )
        )


SDocElement = Union[SDocNode, DocumentFromFile]


@dataclass
class SDocDocument:
    """Represents a complete `[DOCUMENT]` in StrictDoc."""

    title: str
    mid: Optional[str] = None
    config: DocumentConfig = field(default_factory=DocumentConfig)
    views: List[ViewElement] = field(default_factory=list)
    grammar: Optional[DocumentGrammar] = None
    section_contents: List[SDocElement] = field(default_factory=list)

