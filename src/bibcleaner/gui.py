"""Tkinter graphical interface for bibcleaner.

Launch with ``bibcleaner --gui`` or ``bibcleaner-gui``.
"""

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from pathlib import Path
from typing import Optional

from .cleaner import clean_bibtex


class BibCleanerGUI:
    """Main application window for the bibcleaner GUI."""

    _FONT_MONO = ("Courier", 10)
    _PAD = 10

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("bibcleaner")
        self.root.geometry("780x580")
        self.root.minsize(620, 460)
        self._build_menu()
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open .bib file…", command=self._browse_input,
                              accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.root.quit,
                              accelerator="Ctrl+Q")
        menubar.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)
        self.root.bind("<Control-o>", lambda _e: self._browse_input())
        self.root.bind("<Control-q>", lambda _e: self.root.quit())

    def _build_ui(self) -> None:
        p = self._PAD
        main = ttk.Frame(self.root, padding=p)
        main.pack(fill=tk.BOTH, expand=True)

        # ── Input file row ──────────────────────────────────────────────
        ttk.Label(main, text="Input file:").grid(
            row=0, column=0, sticky="w", pady=(0, 4))
        self._input_var = tk.StringVar()
        self._input_entry = ttk.Entry(main, textvariable=self._input_var, width=58)
        self._input_entry.grid(row=0, column=1, sticky="ew", padx=(6, 4))
        ttk.Button(main, text="Browse…", command=self._browse_input).grid(
            row=0, column=2)

        # ── Output file row ─────────────────────────────────────────────
        ttk.Label(main, text="Output file:").grid(
            row=1, column=0, sticky="w", pady=(0, 4))
        self._output_var = tk.StringVar()
        ttk.Entry(main, textvariable=self._output_var, width=58).grid(
            row=1, column=1, sticky="ew", padx=(6, 4))
        ttk.Button(main, text="Browse…", command=self._browse_output).grid(
            row=1, column=2)

        main.columnconfigure(1, weight=1)

        # ── Options ──────────────────────────────────────────────────────
        opts = ttk.LabelFrame(main, text="Options", padding=(p, 4))
        opts.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(p, 4))

        self._dedup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opts, text="Remove duplicate entries", variable=self._dedup_var
        ).grid(row=0, column=0, sticky="w")

        self._report_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opts, text="Show cleanup report", variable=self._report_var
        ).grid(row=0, column=1, sticky="w", padx=(p * 2, 0))

        # ── Action row ───────────────────────────────────────────────────
        action = ttk.Frame(main)
        action.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(4, p))

        self._run_btn = ttk.Button(
            action, text="Clean BibTeX", command=self._run, width=16
        )
        self._run_btn.pack(side=tk.LEFT)

        self._progress = ttk.Progressbar(action, mode="indeterminate", length=180)
        self._progress.pack(side=tk.LEFT, padx=(p, 0))

        ttk.Button(action, text="Clear", command=self._clear_report).pack(
            side=tk.RIGHT
        )

        # ── Report / output area ─────────────────────────────────────────
        ttk.Label(main, text="Report:").grid(
            row=4, column=0, sticky="nw", pady=(0, 2))
        self._report_text = scrolledtext.ScrolledText(
            main, height=14, state="disabled", font=self._FONT_MONO,
            wrap=tk.WORD
        )
        self._report_text.grid(
            row=5, column=0, columnspan=3, sticky="nsew"
        )
        main.rowconfigure(5, weight=1)

        # ── Status bar ───────────────────────────────────────────────────
        self._status_var = tk.StringVar(value="Ready.")
        ttk.Label(
            self.root, textvariable=self._status_var,
            relief="sunken", anchor="w", padding=(4, 2)
        ).pack(side=tk.BOTTOM, fill=tk.X)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _browse_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Open BibTeX file",
            filetypes=[("BibTeX files", "*.bib"), ("All files", "*.*")],
        )
        if path:
            self._input_var.set(path)
            p = Path(path)
            if not self._output_var.get():
                self._output_var.set(str(p.parent / f"{p.stem}.clean.bib"))

    def _browse_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save cleaned BibTeX as",
            defaultextension=".bib",
            filetypes=[("BibTeX files", "*.bib"), ("All files", "*.*")],
        )
        if path:
            self._output_var.set(path)

    def _run(self) -> None:
        input_path = self._input_var.get().strip()
        if not input_path:
            messagebox.showwarning(
                "No input file", "Please select an input .bib file first."
            )
            return

        output_path: Optional[str] = self._output_var.get().strip() or None
        dedup = self._dedup_var.get()

        self._run_btn.config(state="disabled")
        self._progress.start(10)
        self._set_status("Processing…")

        def _worker() -> None:
            try:
                report = clean_bibtex(input_path, output_path, dedup=dedup)
                self.root.after(0, self._on_success, report)
            except Exception as exc:
                self.root.after(0, self._on_error, str(exc))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_success(self, report: dict) -> None:
        self._progress.stop()
        self._run_btn.config(state="normal")

        if self._report_var.get():
            sep = "=" * 54
            lines = [
                sep,
                "  BibTeX Cleanup Report",
                sep,
                f"  Input file:         {report.get('input_file', 'N/A')}",
                f"  Output file:        {report.get('output_file', 'N/A')}",
                f"  Initial entries:    {report.get('initial_entries', 0)}",
                f"  Cleaned entries:    {report.get('cleaned_entries', 0)}",
            ]
            if report.get("deduplication_enabled"):
                lines.append(
                    f"  Duplicates removed: {report.get('duplicates_removed', 0)}"
                )
            lines.append(sep)
            self._set_report("\n".join(lines))

        out = report.get("output_file", "output")
        n = report.get("cleaned_entries", 0)
        self._set_status(f"Done. {n} entries written to {out}.")

    def _on_error(self, message: str) -> None:
        self._progress.stop()
        self._run_btn.config(state="normal")
        self._set_report(f"Error:\n  {message}")
        self._set_status("Failed.")
        messagebox.showerror("bibcleaner error", message)

    def _clear_report(self) -> None:
        self._set_report("")
        self._set_status("Ready.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_report(self, text: str) -> None:
        self._report_text.config(state="normal")
        self._report_text.delete("1.0", tk.END)
        if text:
            self._report_text.insert(tk.END, text)
        self._report_text.config(state="disabled")

    def _set_status(self, msg: str) -> None:
        self._status_var.set(msg)

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About bibcleaner",
            "bibcleaner\n\n"
            "A tool for cleaning and deduplicating BibTeX files.\n\n"
            "Features:\n"
            "  • Duplicate detection by DOI and normalised title\n"
            "  • Author name normalisation (Last, First)\n"
            "  • Title brace and year extraction\n"
            "  • Page range normalisation (1-10 → 1--10)\n\n"
            "https://github.com/vdeshmukh203/bibcleaner",
        )


def launch_gui() -> None:
    """Launch the bibcleaner graphical interface (blocking call)."""
    root = tk.Tk()
    BibCleanerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
