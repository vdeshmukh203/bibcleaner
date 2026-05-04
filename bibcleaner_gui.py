"""
Graphical user interface for bibcleaner.

Requires tkinter, which ships with the standard Python installer on Windows
and macOS.  On Debian/Ubuntu Linux install it with::

    sudo apt-get install python3-tk

Run the GUI directly::

    python bibcleaner_gui.py

or via the installed entry point::

    bibcleaner-gui
"""

import sys
import threading
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk

    _TKINTER_AVAILABLE = True
except ModuleNotFoundError:
    _TKINTER_AVAILABLE = False

import bibcleaner as bc


def _build_app_class():
    """Return the _App class only when tkinter is importable."""

    class _App(tk.Tk):
        """Main application window."""

        def __init__(self):
            super().__init__()
            self.title("BibCleaner — BibTeX Normalizer & Deduplicator")
            self.resizable(True, True)
            self.minsize(680, 480)
            self._build()
            self.columnconfigure(0, weight=1)
            self.rowconfigure(0, weight=1)

        # ------------------------------------------------------------------
        # Layout
        # ------------------------------------------------------------------

        def _build(self):
            root = ttk.Frame(self, padding=12)
            root.grid(sticky="nsew")
            root.columnconfigure(1, weight=1)

            # ---- Input file row ----
            ttk.Label(root, text="Input .bib file:").grid(
                row=0, column=0, sticky="w", pady=(0, 4)
            )
            self._input_var = tk.StringVar()
            ttk.Entry(root, textvariable=self._input_var).grid(
                row=0, column=1, sticky="ew", padx=6, pady=(0, 4)
            )
            ttk.Button(root, text="Browse…", command=self._browse_input).grid(
                row=0, column=2, pady=(0, 4)
            )

            # ---- Output file row ----
            ttk.Label(root, text="Output .bib file:").grid(
                row=1, column=0, sticky="w", pady=(0, 4)
            )
            self._output_var = tk.StringVar()
            ttk.Entry(root, textvariable=self._output_var).grid(
                row=1, column=1, sticky="ew", padx=6, pady=(0, 4)
            )
            ttk.Button(root, text="Browse…", command=self._browse_output).grid(
                row=1, column=2, pady=(0, 4)
            )

            # ---- Options ----
            opt_frame = ttk.LabelFrame(root, text="Options", padding=(10, 6))
            opt_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=8)
            self._dedup_var = tk.BooleanVar(value=True)
            ttk.Checkbutton(
                opt_frame,
                text="Remove duplicate entries (by DOI and title)",
                variable=self._dedup_var,
            ).grid(row=0, column=0, sticky="w")

            # ---- Action buttons ----
            btn_frame = ttk.Frame(root)
            btn_frame.grid(row=3, column=0, columnspan=3, pady=(0, 8))
            self._clean_btn = ttk.Button(
                btn_frame, text="Clean", command=self._run_clean, width=14
            )
            self._clean_btn.grid(row=0, column=0, padx=6)
            ttk.Button(btn_frame, text="Clear", command=self._clear, width=10).grid(
                row=0, column=1, padx=6
            )

            # ---- Progress bar ----
            self._progress = ttk.Progressbar(root, mode="indeterminate")
            self._progress.grid(
                row=4, column=0, columnspan=3, sticky="ew", pady=(0, 6)
            )

            # ---- Report area ----
            ttk.Label(root, text="Report:").grid(row=5, column=0, sticky="w")
            self._report = scrolledtext.ScrolledText(
                root,
                height=14,
                state="disabled",
                wrap="word",
                font=("Courier", 10),
            )
            self._report.grid(
                row=6, column=0, columnspan=3, sticky="nsew", pady=(2, 0)
            )
            root.rowconfigure(6, weight=1)

        # ------------------------------------------------------------------
        # Event handlers
        # ------------------------------------------------------------------

        def _browse_input(self):
            path = filedialog.askopenfilename(
                title="Select input BibTeX file",
                filetypes=[("BibTeX files", "*.bib"), ("All files", "*.*")],
            )
            if path:
                self._input_var.set(path)
                if not self._output_var.get():
                    p = Path(path)
                    self._output_var.set(str(p.parent / f"{p.stem}.clean.bib"))

        def _browse_output(self):
            path = filedialog.asksaveasfilename(
                title="Save cleaned BibTeX file",
                defaultextension=".bib",
                filetypes=[("BibTeX files", "*.bib"), ("All files", "*.*")],
            )
            if path:
                self._output_var.set(path)

        def _clear(self):
            self._input_var.set("")
            self._output_var.set("")
            self._dedup_var.set(True)
            self._set_report("")

        def _run_clean(self):
            input_path = self._input_var.get().strip()
            if not input_path:
                messagebox.showwarning(
                    "No input", "Please select an input .bib file."
                )
                return

            output_path = self._output_var.get().strip() or None
            dedup = self._dedup_var.get()

            self._clean_btn.configure(state="disabled")
            self._progress.start(12)
            self._set_report("Running…\n")

            threading.Thread(
                target=self._worker,
                args=(input_path, output_path, dedup),
                daemon=True,
            ).start()

        def _worker(self, input_path: str, output_path, dedup: bool):
            try:
                report = bc.clean_bibtex(input_path, output_path, dedup=dedup)
                self.after(0, self._on_success, report)
            except FileNotFoundError as exc:
                self.after(0, self._on_error, str(exc))
            except Exception as exc:  # noqa: BLE001
                self.after(0, self._on_error, f"Unexpected error: {exc}")

        def _on_success(self, report: dict):
            self._progress.stop()
            self._clean_btn.configure(state="normal")

            lines = [
                "=" * 54,
                "BibTeX Cleanup Report",
                "=" * 54,
                f"Input file:         {report.get('input_file', 'N/A')}",
                f"Output file:        {report.get('output_file', 'N/A')}",
                f"Initial entries:    {report.get('initial_entries', 0)}",
                f"Cleaned entries:    {report.get('cleaned_entries', 0)}",
            ]
            if report.get("deduplication_enabled"):
                lines.append(
                    f"Duplicates removed: {report.get('duplicates_removed', 0)}"
                )
            lines.append("=" * 54)
            lines.append("\nDone.")
            self._set_report("\n".join(lines))

        def _on_error(self, message: str):
            self._progress.stop()
            self._clean_btn.configure(state="normal")
            self._set_report(f"Error: {message}")
            messagebox.showerror("Error", message)

        def _set_report(self, text: str):
            self._report.configure(state="normal")
            self._report.delete("1.0", tk.END)
            self._report.insert(tk.END, text)
            self._report.configure(state="disabled")

    return _App


def main():
    """Entry point for the bibcleaner GUI."""
    if not _TKINTER_AVAILABLE:
        print(
            "Error: tkinter is not installed.\n"
            "Install it via your system package manager, e.g.:\n"
            "  Debian/Ubuntu: sudo apt-get install python3-tk\n"
            "  Fedora/RHEL:   sudo dnf install python3-tkinter\n"
            "  macOS/Windows: tkinter is bundled with the standard Python installer.\n"
            "\nAlternatively, use the CLI:  bibcleaner --help",
            file=sys.stderr,
        )
        sys.exit(1)

    App = _build_app_class()
    try:
        App().mainloop()
    except tk.TclError as exc:
        print(
            f"Error: cannot open display — {exc}\n"
            "bibcleaner-gui requires a graphical environment.\n"
            "Use the CLI instead:  bibcleaner --help",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
