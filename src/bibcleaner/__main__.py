"""
Entry point for ``python -m bibcleaner``.

Usage::

    python -m bibcleaner input.bib
    python -m bibcleaner input.bib -o output.bib --report
    python -m bibcleaner gui          # launch the GUI
"""

import sys
import argparse
from pathlib import Path

from .cleaner import clean_bibtex, _print_report


def _cli_main() -> int:
    parser = argparse.ArgumentParser(
        prog="bibcleaner",
        description="Clean and deduplicate BibTeX bibliography files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  bibcleaner refs.bib
  bibcleaner refs.bib -o refs.clean.bib
  bibcleaner messy.bib --no-dedup
  bibcleaner citations.bib --report
  bibcleaner gui                       # launch the GUI
""",
    )
    subparsers = parser.add_subparsers(dest="command")

    # ---- 'gui' sub-command ----
    subparsers.add_parser("gui", help="Launch the graphical user interface.")

    # ---- default / 'clean' positional ----
    # We support both `bibcleaner file.bib` and `bibcleaner clean file.bib`
    clean_p = subparsers.add_parser("clean", help="Clean a .bib file (default).")
    _add_clean_args(clean_p)

    # Make the positional also work without a sub-command
    _add_clean_args(parser)

    args = parser.parse_args()

    if args.command == "gui":
        from .gui import main as gui_main
        gui_main()
        return 0

    # Resolve input from either top-level or 'clean' sub-command
    input_path = getattr(args, "input", None)
    if not input_path:
        parser.print_help()
        return 0

    try:
        report = clean_bibtex(
            input_path=input_path,
            output_path=args.output,
            dedup=not args.no_dedup,
        )
        if args.report:
            _print_report(report)
        return 0
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _add_clean_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("input", nargs="?", help="Path to input .bib file.")
    p.add_argument(
        "-o", "--output",
        default=None,
        help="Output path (default: <input>.clean.bib).",
    )
    p.add_argument(
        "--no-dedup",
        action="store_true",
        help="Disable duplicate removal.",
    )
    p.add_argument(
        "--report",
        action="store_true",
        help="Print a summary report to stderr.",
    )


if __name__ == "__main__":
    sys.exit(_cli_main())
