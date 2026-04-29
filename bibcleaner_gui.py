"""
bibcleaner_gui – Tkinter graphical interface for bibcleaner.

Launch with::

    python bibcleaner_gui.py

or, after installation::

    bibcleaner-gui
"""

import sys
import threading
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk
except ModuleNotFoundError:  # pragma: no cover
    sys.exit(
        "Error: tkinter is not available in this Python installation.\n"
        "On Debian/Ubuntu, install it with:  sudo apt-get install python3-tk\n"
        "On Fedora/RHEL:                     sudo dnf install python3-tkinter\n"
        "On macOS (Homebrew Python):         brew install python-tk"
    )

import bibcleaner as bc


class BibCleanerApp:
    """Main application window."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title(f"BibCleaner {bc.__version__}")
        root.minsize(620, 480)
        root.resizable(True, True)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 5}

        # ── File selection ──────────────────────────────────────────────
        files = ttk.LabelFrame(self.root, text="Files", padding=10)
        files.pack(fill="x", **pad)
        files.columnconfigure(1, weight=1)

        ttk.Label(files, text="Input .bib:").grid(
            row=0, column=0, sticky="w"
        )
        self.input_var = tk.StringVar()
        ttk.Entry(files, textvariable=self.input_var).grid(
            row=0, column=1, sticky="ew", padx=(6, 4)
        )
        ttk.Button(files, text="Browse…", command=self._browse_input).grid(
            row=0, column=2
        )

        ttk.Label(files, text="Output .bib:").grid(
            row=1, column=0, sticky="w", pady=(6, 0)
        )
        self.output_var = tk.StringVar()
        ttk.Entry(files, textvariable=self.output_var).grid(
            row=1, column=1, sticky="ew", padx=(6, 4), pady=(6, 0)
        )
        ttk.Button(files, text="Browse…", command=self._browse_output).grid(
            row=1, column=2, pady=(6, 0)
        )

        # ── Options ─────────────────────────────────────────────────────
        opts = ttk.LabelFrame(self.root, text="Options", padding=10)
        opts.pack(fill="x", **pad)

        self.dedup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opts,
            text="Deduplicate entries  (removes entries sharing a DOI or title)",
            variable=self.dedup_var,
        ).pack(anchor="w")

        # ── Action row ───────────────────────────────────────────────────
        action = ttk.Frame(self.root)
        action.pack(fill="x", **pad)

        self.run_btn = ttk.Button(
            action, text="  Clean Bibliography  ", command=self._run
        )
        self.run_btn.pack(side="left")

        self.status_var = tk.StringVar()
        ttk.Label(action, textvariable=self.status_var, foreground="gray").pack(
            side="left", padx=10
        )

        # ── Report ───────────────────────────────────────────────────────
        report_frame = ttk.LabelFrame(self.root, text="Report", padding=10)
        report_frame.pack(fill="both", expand=True, **pad)

        self.report_box = scrolledtext.ScrolledText(
            report_frame,
            height=12,
            state="disabled",
            font=("Courier", 10),
            wrap="word",
            background="#f8f8f8",
        )
        self.report_box.pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def _browse_input(self) -> None:
        path = filedialog.askopenfilename(
            title="Select input BibTeX file",
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

    def _run(self) -> None:
        input_path = self.input_var.get().strip()
        if not input_path:
            messagebox.showerror("BibCleaner", "Please select an input .bib file.")
            return

        output_path = self.output_var.get().strip() or None
        dedup = self.dedup_var.get()

        self.run_btn.configure(state="disabled")
        self._set_status("Working…", "gray")
        self._set_report("")

        threading.Thread(
            target=self._worker,
            args=(input_path, output_path, dedup),
            daemon=True,
        ).start()

    # ------------------------------------------------------------------
    # Background worker + GUI callbacks
    # ------------------------------------------------------------------

    def _worker(self, input_path: str, output_path, dedup: bool) -> None:
        try:
            report = bc.clean_bibtex(input_path, output_path, dedup)
            self.root.after(0, self._on_success, report)
        except FileNotFoundError as exc:
            self.root.after(0, self._on_error, str(exc))
        except Exception as exc:
            self.root.after(0, self._on_error, f"Unexpected error:\n{exc}")

    def _on_success(self, report: dict) -> None:
        self.run_btn.configure(state="normal")
        removed = report.get("duplicates_removed", 0)
        self._set_status(
            f"Done — {report['initial_entries']} → {report['cleaned_entries']} entries"
            + (f", {removed} duplicate(s) removed" if report.get("deduplication_enabled") else ""),
            "green",
        )

        sep = "─" * 54
        lines = [
            sep,
            "  BibTeX Cleanup Report",
            sep,
            f"  Input file:          {report['input_file']}",
            f"  Output file:         {report['output_file']}",
            f"  Initial entries:     {report['initial_entries']}",
            f"  Cleaned entries:     {report['cleaned_entries']}",
        ]
        if report.get("deduplication_enabled"):
            lines.append(
                f"  Duplicates removed:  {report.get('duplicates_removed', 0)}"
            )
        lines.append(sep)
        self._set_report("\n".join(lines))

    def _on_error(self, message: str) -> None:
        self.run_btn.configure(state="normal")
        self._set_status("Error.", "red")
        messagebox.showerror("BibCleaner Error", message)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_status(self, text: str, colour: str = "gray") -> None:
        self.status_var.set(text)
        # Locate the status label and update its foreground
        for widget in self.root.winfo_children():
            for child in getattr(widget, "winfo_children", lambda: [])():
                if isinstance(child, ttk.Label) and child.cget("textvariable"):
                    try:
                        child.configure(foreground=colour)
                    except Exception:
                        pass

    def _set_report(self, text: str) -> None:
        self.report_box.configure(state="normal")
        self.report_box.delete("1.0", tk.END)
        if text:
            self.report_box.insert(tk.END, text)
        self.report_box.configure(state="disabled")


def main() -> None:
    """Launch the BibCleaner graphical interface."""
    root = tk.Tk()
    BibCleanerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
