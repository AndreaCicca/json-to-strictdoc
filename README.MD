# JSON <-> STRICTDOC Feature-Complete Parser & Converter

Parser e convertitore bidirezionale feature-complete tra **JSON** e **StrictDoc** (`.sdoc` / `.sgra`), conforme al 100% alla specifica grammaticale e semantica ufficiale di [StrictDoc](https://github.com/strictdoc-project/strictdoc).

## Funzionalità Supportate

- **Conversione Bidirezionale**:
  - `JSON -> SDOC` (`.json` $\to$ `.sdoc`)
  - `SDOC -> JSON` (`.sdoc` $\to$ `.json`)
  - `SGRA <-> JSON` (`.sgra` $\leftrightarrow$ `.json` per grammatiche standalone)
  - Migrazione/Formattazione `SDOC -> SDOC` (da sintassi legacy `[SECTION]`/`[FREETEXT]` a sintassi moderna `[[SECTION]]`/`[TEXT]`)
- **Copertura Completa della Specifica StrictDoc**:
  - **Header & Configurazione `[DOCUMENT]`**: `MID`, `TITLE`, `UID`, `VERSION`, `DATE`, `CLASSIFICATION`, `PREFIX` / `REQ_PREFIX`, `ROOT`
  - **Blocco `OPTIONS`**: `ENABLE_MID`, `RELATION_FIELD`, `MARKUP` (`RST`, `Text`, `HTML`, `Markdown`), `AUTO_LEVELS` (`On`, `Off`), `LAYOUT` (`Default`, `Website`), `VIEW_STYLE` (`Plain`, `Inline`, `Simple`, `Narrative`, `Table`, `Zebra`), `NODE_IN_TOC`, `DEFAULT_VIEW`
  - **Blocco `METADATA`**: coppie chiave-valore personalizzate
  - **Blocco `VIEWS`**: definizione completa di viste (`ID`, `NAME`, `TAGS` $\to$ `OBJECT_TYPE` $\to$ `VISIBLE_FIELDS` con `NAME` e `PLACEMENT`, `HIDDEN_TAGS`)
  - **Blocco `[GRAMMAR]`**: sia `IMPORT_FROM_FILE` sia `ELEMENTS` completi di `PROPERTIES` (`IS_COMPOSITE`, `PREFIX`, `VIEW_STYLE`), `FIELDS` (`String`, `Tag`, `SingleChoice(...)`, `MultipleChoice(...)`, `HUMAN_TITLE`, `REQUIRED`) e `RELATIONS` (`Parent`, `Child`, `File` con `ROLE` e `REVERSE_ROLE`)
  - **Nodi del Documento**:
    - Nodi compositi moderni `[[SECTION]] ... [[/SECTION]]` e `[[CUSTOM_NODE]] ... [[/CUSTOM_NODE]]`
    - Nodi standard `[TEXT]`, `[REQUIREMENT]` e qualsiasi nodo custom definito nella grammatica
    - Campi single-line e multi-line (`>>> ... <<<`) con ordinamento automatico dei campi secondo la grammatica attiva e supporto per campi `COMMENT` multipli
    - Inclusione frammenti `[DOCUMENT_FROM_FILE]`
    - Elementi inline nel testo: `[LINK: UID]` e `[ANCHOR: UID, Title]`
  - **Relazioni (`RELATIONS:`)**: `Parent`, `Child` e `File` (`ROLE`, `FORMAT`, `PATH`, `VALUE`, `ELEMENT`, `ID`, `LINE_RANGE`, `FUNCTION`, `CLASS`, `HASH`)
  - **Retrocompatibilità Legacy**: supporto in lettura e scrittura (`--legacy` / `--legacy-json`) per `[SECTION] ... [/SECTION]`, `[FREETEXT] ... [/FREETEXT]`, `[COMPOSITE_REQUIREMENT]` e `REFS:`
  - **Validatore Semantico (`SDocValidator`)**: verifica tipi di nodo, proprietà composite, campi obbligatori, ordine dei campi, opzioni `SingleChoice`/`MultipleChoice`/`Tag`, relazioni ammesse dalla grammatica e unicità degli `UID`.

---

## Utilizzo da CLI

```bash
# Convertire JSON in SDOC (sintassi moderna StrictDoc)
python3 strictdock-parser.py test.json test.sdoc

# Convertire JSON in SDOC (sintassi legacy [SECTION] / [FREETEXT])
python3 strictdock-parser.py --legacy test.json test_legacy.sdoc

# Convertire SDOC in JSON (AST completo lossless)
python3 strictdock-parser.py test.sdoc output.json

# Convertire SDOC in JSON (schema compatto legacy con SECTIONS / REQUIREMENTS / FREETEXT)
python3 strictdock-parser.py --legacy-json test.sdoc output_legacy.json

# Validare un file .sdoc, .sgra o .json
python3 strictdock-parser.py --validate test.sdoc

# Migrare un file .sdoc legacy alla sintassi StrictDoc moderna
python3 strictdock-parser.py legacy_doc.sdoc modern_doc.sdoc
```

---

## Utilizzo come Libreria Python

```python
from strictdoc_parser import (
    json_to_sdoc,
    sdoc_to_json,
    parse_sdoc,
    write_sdoc,
    SDocValidator,
)

# Da JSON a SDOC
sdoc_text = json_to_sdoc(json_string, legacy=False, validate=True)

# Da SDOC a JSON
json_text = sdoc_to_json(sdoc_text, legacy_json=False, validate=True)

# Parsing in AST e validazione semantica
doc = parse_sdoc(sdoc_text)
SDocValidator.validate_document(doc)
```

---

## Esempio (`test.json` $\to$ `test.sdoc`)

Input ([test.json](file:///Users/andrea/git-stuff/github/json-to-strictdoc/test.json)):

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

Output Moderno ([test.sdoc](file:///Users/andrea/git-stuff/github/json-to-strictdoc/test.sdoc)):

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

## Eseguire i Test

```bash
python3 -m unittest discover -s tests -v
```