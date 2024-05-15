# JSON TO STRICTDOC

Questo progetto permette di convertire un file JSON in un file STRICTDOC (.sdoc)

> [!NOTE]
> How to use script
> python3 strictdock-parser.py <file_input.json> <file_output.sdoc>
>
> Example with the test file
> 1. python3 strictdock-parser.py test.json test.sdoc
> 2. strictdoc export test.sdoc

Example:

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

Output generated:

```sdoc
[DOCUMENT]
TITLE: Test Documentation

[FREETEXT]
This requirements specification will illustrate the functionalities of the HTR System of the Isolette Project.
[/FREETEXT]

[SECTION]
TITLE: System Overview

[FREETEXT]
This documentation is used to test the script
[/FREETEXT]

[REQUIREMENT]
UID: TEST-01
TITLE: Test the script
STATEMENT: >>>
This is a Test
<<<
RATIONALE: >>>
This is a test
<<<

[/SECTION]

```