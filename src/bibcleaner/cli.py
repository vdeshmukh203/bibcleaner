"""Command-line interface for bibcleaner."""

import sys
import argparse
from typing import Any, Dict, List, Optional

from .cleaner import clean_bibtex


def _print_report(report: Dict[str, Any], file=None) -> None:
    """Print a formatted cleanup report."""
    if file is None:
        file = sys.stderr
    sep = "=" * 60
    print(f"\n{sep}", file=file)
    print("BibTeX Cleanup Report", file=file)
    print(sep, file=file)
    print(f"Input file:          {report.get('input_file', 'N/A')}", file=file)
    print(f"Output file:         {report.get('output_file', 'N/A')}", file=file)
    print(f"Initial entries:     {report.get('initial_entries', 0)}", file=file)
    print(f"Cleaned entries:     {report.get('cleaned_entries', 0)}", file=file)
    if report.get("deduplication_enabled"):
        print(f"Duplicates removed:  {report.get('duplicates_removed', 0)}", file=file)
    print(sep, file=file)


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for the ``bibcleaner`` command.

    Returns exit code 0 on success, 1 on error.
    """
    parser = argparse.ArgumentParser(
        prog="bibcleaner",
        description="Clean and deduplicate BibTeX files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  bibcleaner refs.bib
  bibcleaner refs.bib -o refs_clean.bib
  bibcleaner messy.bib --no-dedup
  bibcleaner citations.bib --report
  bibcleaner --gui
        """,
    )
    parser.add_argument("input", nargs="?", help="Path to input .bib file")
    parser.add_argument(
        "-o", "--output",
        default=None,
        metavar="FILE",
        help="Output .bib file (default: <input>.clean.bib)",
    )
    parser.add_argument(
        "--no-dedup",
        action="store_true",
        help="Disable duplicate removal",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Print a cleanup summary to stderr",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the graphical interface",
    )

    args = parser.parse_args(argv)

    if args.gui:
        try:
            from .gui import launch_gui
        except ImportError as exc:
            print(f"Error: GUI dependencies not available: {exc}", file=sys.stderr)
            return 1
        launch_gui()
        return 0

    if not args.input:
        parser.print_help()
        return 1

    try:
        report = clean_bibtex(
            input_path=args.input,
            output_path=args.output,
            dedup=not args.no_dedup,
        )
        if args.report:
            _print_report(report)
        return 0
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
