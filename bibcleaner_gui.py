"""
Graphical interface for bibcleaner.

Provides a Tkinter-based GUI for cleaning and deduplicating BibTeX files,
exposing the same options as the CLI in a point-and-click interface.

Usage:
    python bibcleaner_gui.py
    bibcleaner-gui  (after pip install)
"""

import io
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from pathlib import Path

import bibcleaner as bc


class BibCleanerApp:
    """Main application window for bibcleaner GUI."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"bibcleaner {bc.__version__}")
        self.root.minsize(640, 460)
        self._build_menu()
        self._build_ui()
        self.root.bind("<Control-o>", lambda _e: self._browse_input())
        self.root.bind("<Control-q>", lambda _e: self.root.quit())

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(
            label="Open .bib file…", command=self._browse_input, accelerator="Ctrl+O"
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Exit", command=self.root.quit, accelerator="Ctrl+Q"
        )
        menubar.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding=12)
        main.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(4, weight=1)

        # Input file row
        ttk.Label(main, text="Input .bib file:").grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )
        self.input_var = tk.StringVar()
        ttk.Entry(main, textvariable=self.input_var).grid(
            row=0, column=1, sticky="ew", padx=(6, 6)
        )
        ttk.Button(main, text="Browse…", command=self._browse_input).grid(
            row=0, column=2
        )

        # Output file row
        ttk.Label(main, text="Output .bib file:").grid(
            row=1, column=0, sticky="w", pady=(0, 6)
        )
        self.output_var = tk.StringVar()
        ttk.Entry(main, textvariable=self.output_var).grid(
            row=1, column=1, sticky="ew", padx=(6, 6)
        )
        ttk.Button(main, text="Browse…", command=self._browse_output).grid(
            row=1, column=2
        )

        # Options frame
        opts = ttk.LabelFrame(main, text="Options", padding=8)
        opts.grid(row=2, column=0, columnspan=3, sticky="ew", pady=8)

        self.dedup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opts, text="Deduplicate entries (by DOI and title)", variable=self.dedup_var
        ).pack(side="left", padx=4)

        # Action buttons
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=(0, 8))

        self.run_btn = ttk.Button(
            btn_frame, text="Clean", command=self._run, width=14
        )
        self.run_btn.pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Clear log", command=self._clear_log, width=14).pack(
            side="left", padx=6
        )

        # Report / log area
        ttk.Label(main, text="Report:").grid(row=4, column=0, sticky="nw")
        self.log = scrolledtext.ScrolledText(
            main,
            height=14,
            state="disabled",
            wrap="word",
            font=("Courier", 10),
        )
        self.log.grid(row=4, column=1, columnspan=2, sticky="nsew")

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(
            main, textvariable=self.status_var, relief="sunken", anchor="w"
        ).grid(row=5, column=0, columnspan=3, sticky="ew", pady=(6, 0))

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _browse_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Select BibTeX file",
            filetypes=[("BibTeX files", "*.bib"), ("All files", "*.*")],
        )
        if path:
            self.input_var.set(path)
            if not self.output_var.get():
                p = Path(path)
                self.output_var.set(str(p.parent / f"{p.stem}.clean.bib"))

    def _browse_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save cleaned BibTeX file",
            defaultextension=".bib",
            filetypes=[("BibTeX files", "*.bib"), ("All files", "*.*")],
        )
        if path:
            self.output_var.set(path)

    def _clear_log(self) -> None:
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")
        self.status_var.set("Ready")

    def _run(self) -> None:
        input_path = self.input_var.get().strip()
        if not input_path:
            messagebox.showwarning(
                "No input file", "Please select an input .bib file first."
            )
            return

        output_path = self.output_var.get().strip() or None
        dedup = self.dedup_var.get()

        self.run_btn.config(state="disabled")
        self.status_var.set("Processing…")
        self._log_append(f"Processing: {input_path}\n")

        def _worker() -> None:
            try:
                report = bc.clean_bibtex(input_path, output_path, dedup=dedup)
                self.root.after(0, self._on_done, report)
            except Exception as exc:  # noqa: BLE001
                self.root.after(0, self._on_error, str(exc))

        threading.Thread(target=_worker, daemon=True).start()

    # ------------------------------------------------------------------
    # Callbacks from worker thread (always called on main thread via after())
    # ------------------------------------------------------------------

    def _on_done(self, report: dict) -> None:
        buf = io.StringIO()
        bc._print_report(report, file=buf)
        self._log_append(buf.getvalue() + "\n")
        n = report.get("cleaned_entries", 0)
        out = report.get("output_file", "")
        self.status_var.set(f"Done — {n} entries written to {out}")
        self.run_btn.config(state="normal")

    def _on_error(self, msg: str) -> None:
        self._log_append(f"Error: {msg}\n")
        self.status_var.set("Error — see log")
        messagebox.showerror("bibcleaner error", msg)
        self.run_btn.config(state="normal")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _log_append(self, text: str) -> None:
        self.log.config(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.config(state="disabled")

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About bibcleaner",
            (
                f"bibcleaner v{bc.__version__}\n\n"
                "Parse, normalise, and deduplicate BibTeX files.\n\n"
                "Author: Vaibhav Deshmukh\n"
                "License: MIT\n"
                "https://github.com/vdeshmukh203/bibcleaner"
            ),
        )


def main() -> None:
    """Launch the bibcleaner GUI."""
    root = tk.Tk()
    BibCleanerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
