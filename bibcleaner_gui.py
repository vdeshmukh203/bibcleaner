"""Graphical user interface for bibcleaner.

Provides a simple tkinter-based window for selecting, cleaning, and
deduplicating BibTeX files without using the command line.

Usage::

    python bibcleaner_gui.py
    bibcleaner-gui          # when installed via pip
"""

import sys
import pathlib

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk
except ImportError:
    print(
        "Error: tkinter is not available.\n"
        "Install it via your OS package manager:\n"
        "  Ubuntu/Debian : sudo apt-get install python3-tk\n"
        "  Fedora/RHEL   : sudo dnf install python3-tkinter\n"
        "  macOS (brew)  : brew install python-tk",
        file=sys.stderr,
    )
    sys.exit(1)

# Allow running directly from the repository root as well as after pip install.
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import bibcleaner as bc


class _BibCleanerApp(tk.Tk):
    """Main application window."""

    _PAD = {"padx": 8, "pady": 4}

    def __init__(self):
        super().__init__()
        self.title(f"bibcleaner {bc.__version__}")
        self.minsize(580, 460)
        self.resizable(True, True)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        self._build_file_frame()
        self._build_options_frame()
        self._build_action_row()
        self._build_report_frame()
        self._build_status_bar()

    def _build_file_frame(self) -> None:
        frame = ttk.LabelFrame(self, text="Files")
        frame.grid(row=0, column=0, sticky="ew", **self._PAD, pady=(10, 4))
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Input .bib file:").grid(
            row=0, column=0, sticky="w", **self._PAD
        )
        self.input_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.input_var).grid(
            row=0, column=1, sticky="ew", **self._PAD
        )
        ttk.Button(frame, text="Browse…", command=self._browse_input).grid(
            row=0, column=2, **self._PAD
        )

        ttk.Label(frame, text="Output .bib file:").grid(
            row=1, column=0, sticky="w", **self._PAD
        )
        self.output_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.output_var).grid(
            row=1, column=1, sticky="ew", **self._PAD
        )
        ttk.Button(frame, text="Browse…", command=self._browse_output).grid(
            row=1, column=2, **self._PAD
        )
        ttk.Label(frame, text="(leave blank for <input>.clean.bib)", foreground="grey").grid(
            row=2, column=1, sticky="w", padx=8, pady=(0, 4)
        )

    def _build_options_frame(self) -> None:
        frame = ttk.LabelFrame(self, text="Options")
        frame.grid(row=1, column=0, sticky="ew", **self._PAD)

        self.dedup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            frame,
            text="Enable deduplication  (matches by DOI, arXiv ID, and title)",
            variable=self.dedup_var,
        ).grid(row=0, column=0, sticky="w", **self._PAD)

    def _build_action_row(self) -> None:
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=2, column=0, pady=6)
        ttk.Button(btn_frame, text="  Clean BibTeX  ", command=self._run).pack()

    def _build_report_frame(self) -> None:
        frame = ttk.LabelFrame(self, text="Report")
        frame.grid(row=3, column=0, sticky="nsew", **self._PAD, pady=(0, 4))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.report_text = scrolledtext.ScrolledText(
            frame,
            height=12,
            state="disabled",
            font=("Courier", 10),
            wrap="word",
        )
        self.report_text.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

    def _build_status_bar(self) -> None:
        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(
            self,
            textvariable=self.status_var,
            anchor="w",
            relief="sunken",
        ).grid(row=4, column=0, sticky="ew", padx=8, pady=(0, 6))

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _browse_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Select input .bib file",
            filetypes=[("BibTeX files", "*.bib"), ("All files", "*.*")],
        )
        if path:
            self.input_var.set(path)
            if not self.output_var.get():
                p = pathlib.Path(path)
                self.output_var.set(str(p.parent / f"{p.stem}.clean.bib"))

    def _browse_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save cleaned .bib file as…",
            defaultextension=".bib",
            filetypes=[("BibTeX files", "*.bib"), ("All files", "*.*")],
        )
        if path:
            self.output_var.set(path)

    def _run(self) -> None:
        input_path = self.input_var.get().strip()
        if not input_path:
            messagebox.showerror("Missing input", "Please select an input .bib file.")
            return

        output_path = self.output_var.get().strip() or None
        self._set_status("Processing…")
        self.update()

        try:
            report = bc.clean_bibtex(
                input_path=input_path,
                output_path=output_path,
                dedup=self.dedup_var.get(),
            )
        except FileNotFoundError as exc:
            messagebox.showerror("File not found", str(exc))
            self._set_status("Error — file not found.")
            return
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Error", str(exc))
            self._set_status(f"Error — {exc}")
            return

        self._show_report(report)
        self._set_status(f"Done — output written to {report['output_file']}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, msg: str) -> None:
        self.status_var.set(msg)

    def _show_report(self, report: dict) -> None:
        sep = "─" * 50
        dups = report.get("duplicates_removed", 0)
        lines = [
            sep,
            "  BibTeX Cleanup Report",
            sep,
            f"  Input file      : {report.get('input_file', 'N/A')}",
            f"  Output file     : {report.get('output_file', 'N/A')}",
            f"  Initial entries : {report.get('initial_entries', 0)}",
            f"  Cleaned entries : {report.get('cleaned_entries', 0)}",
        ]
        if report.get("deduplication_enabled"):
            lines.append(f"  Duplicates removed : {dups}")
        lines.append(sep)
        text = "\n".join(lines) + "\n"

        self.report_text.config(state="normal")
        self.report_text.delete("1.0", "end")
        self.report_text.insert("end", text)
        self.report_text.config(state="disabled")


def main() -> None:
    """Launch the bibcleaner GUI."""
    app = _BibCleanerApp()
    app.mainloop()


def _gui_cli() -> None:
    """Console-script entry point for bibcleaner-gui."""
    main()


if __name__ == "__main__":
    main()
