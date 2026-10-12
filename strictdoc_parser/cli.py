"""
Command-line interface for StrictDoc <-> JSON parser and converter.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from . import (
    SDocSyntaxError,
    SDocValidationError,
    SDocValidator,
    json_to_sdoc,
    json_to_sgra,
    parse_sdoc,
    parse_sgra,
    sdoc_to_json,
    sgra_to_json,
    write_sdoc,
    write_sgra,
)


def _detect_format(path: str, content: Optional[str] = None) -> str:
    lower = path.lower()
    if lower.endswith(".json"):
        return "json"
    if lower.endswith(".sgra"):
        return "sgra"
    if lower.endswith(".sdoc"):
        return "sdoc"
    if content is not None:
        stripped = content.lstrip()
        if stripped.startswith("{"):
            return "json"
        if stripped.startswith("[GRAMMAR]"):
            return "sgra"
        if stripped.startswith("[DOCUMENT]"):
            return "sdoc"
    return "sdoc"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Feature-complete bidirectional parser and converter for StrictDoc (.sdoc / .sgra) and JSON."
        )
    )
    parser.add_argument(
        "input_file",
        help="Path to the input file (.json, .sdoc, .sgra, or '-' for stdin)",
    )
    parser.add_argument(
        "output_file",
        nargs="?",
        default=None,
        help=(
            "Path to the output file (.sdoc, .json, .sgra, or '-' for stdout). "
            "Optional when using --validate."
        ),
    )
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Emit legacy SDoc syntax ([SECTION]...[/SECTION] and [FREETEXT]...[/FREETEXT]) when generating .sdoc",
    )
    parser.add_argument(
        "--legacy-json",
        action="store_true",
        help="Emit shorthand/legacy JSON schema (SECTIONS, FREETEXT, REQUIREMENTS) when generating .json",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip semantic validation of the document against the active grammar",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate the input file against the StrictDoc specification (output_file is optional)",
    )
    parser.add_argument(
        "--strict-modern",
        action="store_true",
        help="Disallow legacy [SECTION] and [FREETEXT] blocks when parsing/validating .sdoc files",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=4,
        help="Indentation level for JSON output (default: 4)",
    )
    parser.add_argument(
        "--from",
        dest="from_format",
        choices=("json", "sdoc", "sgra"),
        default=None,
        help="Explicitly specify input format (auto-detected by file extension/content by default)",
    )
    parser.add_argument(
        "--to",
        dest="to_format",
        choices=("json", "sdoc", "sgra"),
        default=None,
        help="Explicitly specify output format (auto-detected by file extension by default)",
    )

    args = parser.parse_args(argv)

    if not args.validate and args.output_file is None:
        parser.error("output_file is required unless --validate is specified")

    try:
        if args.input_file == "-":
            input_data = sys.stdin.read()
        else:
            if not os.path.isfile(args.input_file):
                print(
                    f"Error: Input file not found: {args.input_file}",
                    file=sys.stderr,
                )
                return 1
            with open(args.input_file, "r", encoding="utf-8") as f:
                input_data = f.read()

        in_fmt = args.from_format or _detect_format(args.input_file, input_data)
        validate = not args.no_validate
        allow_legacy = not args.strict_modern

        # Validation-only mode when no output file is requested
        if args.validate and args.output_file is None:
            if in_fmt == "sdoc":
                doc = parse_sdoc(input_data, allow_legacy_sections=allow_legacy)
                SDocValidator.validate_document(
                    doc, strict_field_order=True, allow_legacy=allow_legacy
                )
            elif in_fmt == "sgra":
                gram = parse_sgra(input_data)
                SDocValidator.validate_grammar(gram)
            elif in_fmt == "json":
                json_to_sdoc(input_data, legacy=args.legacy, validate=True)
            print(f"OK: {args.input_file} is valid ({in_fmt.upper()}).")
            return 0

        assert args.output_file is not None
        out_fmt = args.to_format
        if out_fmt is None:
            if args.output_file == "-":
                out_fmt = "sdoc" if in_fmt == "json" else "json"
            else:
                out_fmt = _detect_format(args.output_file)

        if in_fmt == "json" and out_fmt == "sdoc":
            output_data = json_to_sdoc(
                input_data, legacy=args.legacy, validate=validate
            )
        elif in_fmt == "json" and out_fmt == "sgra":
            output_data = json_to_sgra(input_data, validate=validate)
        elif in_fmt == "sdoc" and out_fmt == "json":
            output_data = sdoc_to_json(
                input_data,
                indent=args.indent,
                legacy_json=args.legacy_json,
                validate=validate,
                allow_legacy_sections=allow_legacy,
            )
        elif in_fmt == "sgra" and out_fmt == "json":
            output_data = sgra_to_json(
                input_data, indent=args.indent, validate=validate
            )
        elif in_fmt == "sdoc" and out_fmt == "sdoc":
            # Useful for formatting / migrating legacy .sdoc to modern .sdoc!
            doc = parse_sdoc(input_data, allow_legacy_sections=allow_legacy)
            if validate:
                SDocValidator.validate_document(
                    doc, strict_field_order=False, allow_legacy=allow_legacy
                )
            output_data = write_sdoc(doc, legacy=args.legacy)
        elif in_fmt == "sgra" and out_fmt == "sgra":
            gram = parse_sgra(input_data)
            if validate:
                SDocValidator.validate_grammar(gram)
            output_data = write_sgra(gram)
        else:
            print(
                f"Error: Unsupported conversion from '{in_fmt}' to '{out_fmt}'",
                file=sys.stderr,
            )
            return 1

        if args.output_file == "-":
            sys.stdout.write(output_data)
        else:
            with open(args.output_file, "w", encoding="utf-8") as f:
                f.write(output_data)

        return 0

    except (SDocSyntaxError, SDocValidationError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

