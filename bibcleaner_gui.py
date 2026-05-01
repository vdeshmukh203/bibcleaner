"""
bibcleaner_gui – Tkinter graphical interface for the bibcleaner library.

Launch via:
    python bibcleaner_gui.py
    bibcleaner --gui
    bibcleaner-gui
"""

import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from pathlib import Path

import bibcleaner as bc

__all__ = ["BibCleanerApp", "launch"]

_PADX = 10
_PADY = 6


class BibCleanerApp(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title("BibCleaner")
        self.resizable(True, True)
        self.minsize(560, 480)
        self._build_ui()
        self._center()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        # ── File selection ───────────────────────────────────────────
        file_frame = ttk.LabelFrame(self, text="Input / Output", padding=8)
        file_frame.grid(row=0, column=0, padx=_PADX, pady=_PADY, sticky="ew")
        file_frame.columnconfigure(1, weight=1)

        ttk.Label(file_frame, text="Input .bib:").grid(row=0, column=0, sticky="w")
        self._input_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self._input_var).grid(
            row=0, column=1, padx=6, sticky="ew"
        )
        ttk.Button(file_frame, text="Browse…", command=self._browse_input).grid(
            row=0, column=2
        )

        ttk.Label(file_frame, text="Output .bib:").grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )
        self._output_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self._output_var).grid(
            row=1, column=1, padx=6, sticky="ew", pady=(4, 0)
        )
        ttk.Button(file_frame, text="Browse…", command=self._browse_output).grid(
            row=1, column=2, pady=(4, 0)
        )

        # ── Options ──────────────────────────────────────────────────
        opt_frame = ttk.LabelFrame(self, text="Options", padding=8)
        opt_frame.grid(row=1, column=0, padx=_PADX, pady=_PADY, sticky="ew")

        self._dedup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opt_frame,
            text="Remove duplicate entries (by DOI, arXiv ID, and title)",
            variable=self._dedup_var,
        ).grid(row=0, column=0, sticky="w")

        self._report_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opt_frame,
            text="Show detailed report after cleaning",
            variable=self._report_var,
        ).grid(row=1, column=0, sticky="w")

        # ── Action button + progress ──────────────────────────────────
        action_frame = ttk.Frame(self)
        action_frame.grid(row=2, column=0, padx=_PADX, pady=(4, 0), sticky="ew")
        action_frame.columnconfigure(0, weight=1)

        self._clean_btn = ttk.Button(
            action_frame, text="Clean", command=self._run_clean
        )
        self._clean_btn.grid(row=0, column=0, sticky="e")

        self._progress = ttk.Progressbar(
            action_frame, mode="indeterminate", length=120
        )
        self._progress.grid(row=0, column=1, padx=(8, 0))

        # ── Output log ───────────────────────────────────────────────
        log_frame = ttk.LabelFrame(self, text="Output", padding=8)
        log_frame.grid(
            row=3, column=0, padx=_PADX, pady=_PADY, sticky="nsew"
        )
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self._log = scrolledtext.ScrolledText(
            log_frame, state="disabled", wrap="word",
            font=("Courier", 10), height=14,
        )
        self._log.grid(row=0, column=0, sticky="nsew")

        # Tag for coloured output
        self._log.tag_config("ok", foreground="#005f00")
        self._log.tag_config("err", foreground="#9f0000")
        self._log.tag_config("info", foreground="#00005f")

        # ── Status bar ────────────────────────────────────────────────
        self._status_var = tk.StringVar(value="Ready.")
        ttk.Label(
            self, textvariable=self._status_var,
            relief="sunken", anchor="w",
        ).grid(row=4, column=0, sticky="ew", padx=_PADX, pady=(0, 6))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _center(self) -> None:
        self.update_idletasks()
        w, h = 640, 520
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _browse_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Select BibTeX file",
            filetypes=[("BibTeX files", "*.bib"), ("All files", "*.*")],
        )
        if path:
            self._input_var.set(path)
            # Auto-populate output path
            if not self._output_var.get():
                stem = Path(path).stem
                parent = Path(path).parent
                self._output_var.set(str(parent / f"{stem}.clean.bib"))

    def _browse_output(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Save cleaned BibTeX as",
            defaultextension=".bib",
            filetypes=[("BibTeX files", "*.bib"), ("All files", "*.*")],
        )
        if path:
            self._output_var.set(path)

    def _log_write(self, text: str, tag: str = "") -> None:
        self._log.config(state="normal")
        self._log.insert("end", text, tag)
        self._log.see("end")
        self._log.config(state="disabled")

    def _set_status(self, msg: str) -> None:
        self._status_var.set(msg)

    # ------------------------------------------------------------------
    # Clean action
    # ------------------------------------------------------------------

    def _run_clean(self) -> None:
        input_path = self._input_var.get().strip()
        output_path = self._output_var.get().strip() or None

        if not input_path:
            messagebox.showwarning("No input", "Please select an input .bib file.")
            return

        # Disable button while working
        self._clean_btn.config(state="disabled")
        self._progress.start(10)
        self._set_status("Cleaning…")
        self._log_write("\n")

        def worker() -> None:
            try:
                report = bc.clean_bibtex(
                    input_path=input_path,
                    output_path=output_path or None,
                    dedup=self._dedup_var.get(),
                )
                self.after(0, lambda: self._on_success(report))
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda e=exc: self._on_error(e))

        threading.Thread(target=worker, daemon=True).start()

    def _on_success(self, report: dict) -> None:
        self._progress.stop()
        self._clean_btn.config(state="normal")
        self._set_status("Done.")

        self._log_write("✔  Cleaning completed successfully.\n", "ok")

        if self._report_var.get():
            initial = report.get("initial_entries", 0)
            cleaned = report.get("cleaned_entries", 0)
            dups = report.get("duplicates_removed", 0)
            out = report.get("output_file", "")
            lines = [
                "─" * 50,
                f"  Input file    : {report.get('input_file', '')}",
                f"  Output file   : {out}",
                f"  Initial entries   : {initial}",
                f"  Cleaned entries   : {cleaned}",
            ]
            if report.get("deduplication_enabled"):
                lines.append(f"  Duplicates removed: {dups}")
            lines.append("─" * 50)
            self._log_write("\n".join(lines) + "\n", "info")

    def _on_error(self, exc: Exception) -> None:
        self._progress.stop()
        self._clean_btn.config(state="normal")
        self._set_status("Error.")
        self._log_write(f"✖  {exc}\n", "err")
        messagebox.showerror("Error", str(exc))


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def launch() -> None:
    """Create and run the BibCleaner GUI (blocks until window is closed)."""
    app = BibCleanerApp()
    app.mainloop()


def main() -> None:
    """Script entry point."""
    launch()


if __name__ == "__main__":
    main()
