"""
Graphical user interface for bibcleaner.

Provides a simple Tk-based GUI so users who prefer not to use the
command line can still clean and deduplicate their ``.bib`` files.

Launch with::

    bibcleaner-gui

or::

    python -m bibcleaner gui
"""

from __future__ import annotations

import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Optional

from .cleaner import clean_bibtex, _print_report
from io import StringIO


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_output(input_path: str) -> str:
    p = Path(input_path)
    return str(p.parent / f"{p.stem}.clean.bib")


# ---------------------------------------------------------------------------
# Main application class
# ---------------------------------------------------------------------------

class BibCleanerApp:
    """Main application window for the BibCleaner GUI."""

    _PAD = 8

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("BibCleaner")
        self.root.resizable(True, True)
        self.root.minsize(600, 480)

        self._input_var = tk.StringVar()
        self._output_var = tk.StringVar()
        self._dedup_var = tk.BooleanVar(value=True)
        self._status_var = tk.StringVar(value="Ready.")

        self._build_ui()
        self._input_var.trace_add("write", self._on_input_change)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        p = self._PAD
        root = self.root

        # ── File selection ────────────────────────────────────────────
        file_frame = ttk.LabelFrame(root, text="Files", padding=p)
        file_frame.pack(fill="x", padx=p, pady=(p, 0))
        file_frame.columnconfigure(1, weight=1)

        ttk.Label(file_frame, text="Input .bib:").grid(
            row=0, column=0, sticky="w", pady=2
        )
        ttk.Entry(file_frame, textvariable=self._input_var).grid(
            row=0, column=1, sticky="ew", padx=(4, 4)
        )
        ttk.Button(file_frame, text="Browse…", command=self._browse_input).grid(
            row=0, column=2
        )

        ttk.Label(file_frame, text="Output .bib:").grid(
            row=1, column=0, sticky="w", pady=2
        )
        ttk.Entry(file_frame, textvariable=self._output_var).grid(
            row=1, column=1, sticky="ew", padx=(4, 4)
        )
        ttk.Button(file_frame, text="Browse…", command=self._browse_output).grid(
            row=1, column=2
        )

        # ── Options ───────────────────────────────────────────────────
        opt_frame = ttk.LabelFrame(root, text="Options", padding=p)
        opt_frame.pack(fill="x", padx=p, pady=(4, 0))

        ttk.Checkbutton(
            opt_frame,
            text="Remove duplicate entries (by DOI and title)",
            variable=self._dedup_var,
        ).pack(anchor="w")

        # ── Action button ─────────────────────────────────────────────
        btn_frame = ttk.Frame(root, padding=(p, 4))
        btn_frame.pack(fill="x", padx=p)

        self._run_btn = ttk.Button(
            btn_frame,
            text="Clean BibTeX File",
            command=self._run,
            style="Accent.TButton",
        )
        self._run_btn.pack(side="left")

        ttk.Button(btn_frame, text="Clear Log", command=self._clear_log).pack(
            side="left", padx=(4, 0)
        )

        # ── Log area ──────────────────────────────────────────────────
        log_frame = ttk.LabelFrame(root, text="Log", padding=p)
        log_frame.pack(fill="both", expand=True, padx=p, pady=(0, 4))
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self._log = scrolledtext.ScrolledText(
            log_frame,
            state="disabled",
            wrap="word",
            height=14,
            font=("Courier", 10) if sys.platform != "darwin" else ("Monaco", 11),
        )
        self._log.grid(row=0, column=0, sticky="nsew")

        # ── Status bar ────────────────────────────────────────────────
        status_bar = ttk.Label(
            root,
            textvariable=self._status_var,
            relief="sunken",
            anchor="w",
            padding=(4, 2),
        )
        status_bar.pack(fill="x", side="bottom")

    # ------------------------------------------------------------------
    # File-browser callbacks
    # ------------------------------------------------------------------

    def _browse_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Select input .bib file",
            filetypes=[("BibTeX files", "*.bib"), ("All files", "*.*")],
        )
        if path:
            self._input_var.set(path)

    def _browse_output(self) -> None:
        initial = self._output_var.get() or self._input_var.get()
        path = filedialog.asksaveasfilename(
            title="Save cleaned .bib file as",
            initialfile=Path(initial).name if initial else "output.clean.bib",
            defaultextension=".bib",
            filetypes=[("BibTeX files", "*.bib"), ("All files", "*.*")],
        )
        if path:
            self._output_var.set(path)

    def _on_input_change(self, *_) -> None:
        """Auto-fill output path when input changes."""
        inp = self._input_var.get().strip()
        if inp and not self._output_var.get().strip():
            self._output_var.set(_default_output(inp))

    # ------------------------------------------------------------------
    # Log helpers
    # ------------------------------------------------------------------

    def _log_write(self, text: str) -> None:
        self._log.configure(state="normal")
        self._log.insert("end", text)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _clear_log(self) -> None:
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    # ------------------------------------------------------------------
    # Run action
    # ------------------------------------------------------------------

    def _run(self) -> None:
        input_path = self._input_var.get().strip()
        output_path = self._output_var.get().strip() or None
        dedup = self._dedup_var.get()

        if not input_path:
            messagebox.showwarning(
                "No input file", "Please select an input .bib file first."
            )
            return

        if not Path(input_path).exists():
            messagebox.showerror(
                "File not found", f"Input file not found:\n{input_path}"
            )
            return

        self._run_btn.configure(state="disabled")
        self._status_var.set("Running…")
        self._log_write(f"Input:  {input_path}\n")
        if output_path:
            self._log_write(f"Output: {output_path}\n")

        thread = threading.Thread(
            target=self._worker,
            args=(input_path, output_path, dedup),
            daemon=True,
        )
        thread.start()

    def _worker(
        self,
        input_path: str,
        output_path: Optional[str],
        dedup: bool,
    ) -> None:
        try:
            report = clean_bibtex(input_path, output_path, dedup=dedup)
        except Exception as exc:  # noqa: BLE001
            self.root.after(0, self._on_error, str(exc))
            return
        self.root.after(0, self._on_success, report)

    def _on_success(self, report: dict) -> None:
        buf = StringIO()
        _print_report(report, file=buf)
        self._log_write(buf.getvalue().strip() + "\n\n")
        self._status_var.set(
            f"Done — {report['cleaned_entries']} entries written to "
            f"{report['output_file']}"
        )
        self._run_btn.configure(state="normal")

    def _on_error(self, message: str) -> None:
        self._log_write(f"ERROR: {message}\n")
        self._status_var.set("Error — see log for details.")
        self._run_btn.configure(state="normal")
        messagebox.showerror("Error", message)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Launch the BibCleaner GUI."""
    root = tk.Tk()

    # Apply a modern theme if available
    style = ttk.Style(root)
    for theme in ("clam", "alt", "default"):
        if theme in style.theme_names():
            style.theme_use(theme)
            break

    app = BibCleanerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
