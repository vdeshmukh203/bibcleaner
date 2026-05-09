"""
bibcleaner GUI — zero-dependency web front-end for the bibcleaner library.

Starts a local HTTP server, opens the default browser, and provides a
single-page interface for uploading, cleaning, and downloading BibTeX files.

Usage::

    python bibcleaner_gui.py          # default port 8765
    python bibcleaner_gui.py --port 9000
    bibcleaner-gui                    # after installation

The server listens only on 127.0.0.1 and shuts down when the browser tab
sends a ``/shutdown`` request or the process is interrupted.
"""

import argparse
import json
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import StringIO
from pathlib import Path
from typing import Any, Dict

import bibcleaner as bc

# ---------------------------------------------------------------------------
# Embedded single-page application
# ---------------------------------------------------------------------------

_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>bibcleaner</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f0f2f5;
      color: #222;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 32px 16px;
    }

    header {
      text-align: center;
      margin-bottom: 28px;
    }
    header h1 { font-size: 2rem; color: #1565c0; letter-spacing: -0.5px; }
    header p  { color: #555; font-size: 0.95rem; margin-top: 4px; }

    .card {
      background: #fff;
      border-radius: 10px;
      box-shadow: 0 2px 12px rgba(0,0,0,.10);
      padding: 24px 28px;
      width: 100%;
      max-width: 760px;
      margin-bottom: 20px;
    }
    .card h2 { font-size: 1rem; font-weight: 600; margin-bottom: 14px; color: #333; }

    /* Drop zone */
    #drop-zone {
      border: 2.5px dashed #90caf9;
      border-radius: 8px;
      padding: 36px 20px;
      text-align: center;
      cursor: pointer;
      transition: background .15s, border-color .15s;
    }
    #drop-zone.hover { background: #e3f2fd; border-color: #1565c0; }
    #drop-zone svg { width: 40px; height: 40px; color: #90caf9; margin-bottom: 8px; }
    #drop-zone p { color: #666; font-size: 0.9rem; }
    #drop-zone strong { color: #1565c0; }
    #file-name {
      margin-top: 10px; font-size: 0.85rem; color: #1565c0;
      font-weight: 600; word-break: break-all;
    }
    input[type=file] { display: none; }

    /* Options */
    .option-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
    .option-row label { cursor: pointer; font-size: 0.93rem; }
    input[type=checkbox] { width: 16px; height: 16px; cursor: pointer; accent-color: #1565c0; }

    /* Button */
    #run-btn {
      display: block;
      width: 100%;
      padding: 12px;
      background: #1565c0;
      color: #fff;
      font-size: 1rem;
      font-weight: 700;
      border: none;
      border-radius: 6px;
      cursor: pointer;
      transition: background .15s;
    }
    #run-btn:hover:not(:disabled) { background: #0d47a1; }
    #run-btn:disabled { background: #90caf9; cursor: not-allowed; }

    /* Report */
    #report { display: none; }
    .stat-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }
    .stat {
      background: #f5f7fa;
      border-radius: 6px;
      padding: 12px 16px;
      text-align: center;
    }
    .stat .val { font-size: 1.8rem; font-weight: 700; color: #1565c0; }
    .stat .lbl { font-size: 0.8rem; color: #666; margin-top: 2px; }
    .stat.warn .val { color: #e65100; }

    /* Warnings list */
    #warnings { list-style: none; margin-bottom: 14px; }
    #warnings li {
      background: #fff8e1;
      border-left: 4px solid #ffa000;
      border-radius: 0 4px 4px 0;
      padding: 6px 12px;
      margin-bottom: 6px;
      font-size: 0.87rem;
      font-family: monospace;
    }

    /* Download button */
    #dl-btn {
      display: inline-block;
      padding: 10px 24px;
      background: #2e7d32;
      color: #fff;
      font-weight: 600;
      border-radius: 6px;
      cursor: pointer;
      border: none;
      font-size: 0.95rem;
      transition: background .15s;
      text-decoration: none;
    }
    #dl-btn:hover { background: #1b5e20; }

    /* Preview */
    #preview-wrap { margin-top: 16px; }
    #preview-wrap summary { cursor: pointer; font-size: 0.9rem; color: #555; margin-bottom: 8px; }
    pre#preview {
      background: #1e1e1e;
      color: #d4d4d4;
      padding: 14px;
      border-radius: 6px;
      font-size: 0.82rem;
      overflow: auto;
      max-height: 300px;
      white-space: pre-wrap;
      word-break: break-word;
    }

    /* Error */
    #error-box {
      display: none;
      background: #ffebee;
      border-left: 4px solid #c62828;
      border-radius: 0 6px 6px 0;
      padding: 12px 16px;
      font-size: 0.9rem;
      color: #b71c1c;
    }

    footer {
      font-size: 0.8rem;
      color: #aaa;
      margin-top: auto;
      padding-top: 16px;
      text-align: center;
    }
    footer a { color: #90caf9; text-decoration: none; }
    footer a:hover { text-decoration: underline; }
  </style>
</head>
<body>

<header>
  <h1>bibcleaner</h1>
  <p>Parse, normalize, and deduplicate your BibTeX bibliography files</p>
</header>

<!-- Upload card -->
<div class="card">
  <h2>1. Select a .bib file</h2>
  <div id="drop-zone" onclick="document.getElementById('file-input').click()">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
      <path stroke-linecap="round" stroke-linejoin="round"
        d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414A1 1 0 0119 9.414V19a2 2 0 01-2 2z"/>
    </svg>
    <p><strong>Click to browse</strong> or drag &amp; drop a <code>.bib</code> file here</p>
  </div>
  <input type="file" id="file-input" accept=".bib,text/plain"/>
  <div id="file-name"></div>
</div>

<!-- Options card -->
<div class="card">
  <h2>2. Options</h2>
  <div class="option-row">
    <input type="checkbox" id="opt-dedup" checked/>
    <label for="opt-dedup">Deduplicate entries (by DOI and normalized title)</label>
  </div>
  <button id="run-btn" disabled>Run bibcleaner</button>
  <div id="error-box"></div>
</div>

<!-- Results card -->
<div class="card" id="report">
  <h2>3. Results</h2>
  <div class="stat-grid" id="stat-grid"></div>
  <ul id="warnings"></ul>
  <button id="dl-btn">Download cleaned .bib</button>
  <details id="preview-wrap">
    <summary>Preview cleaned output</summary>
    <pre id="preview"></pre>
  </details>
</div>

<footer>
  bibcleaner v<span id="ver"></span> &nbsp;|&nbsp;
  <a href="https://github.com/vdeshmukh203/bibcleaner" target="_blank">GitHub</a>
  &nbsp;|&nbsp;
  <a href="#" onclick="fetch('/shutdown');return false;">Quit server</a>
</footer>

<script>
  let _fileContent = null;
  let _fileName = '';
  let _cleanedContent = '';

  // Fetch version
  fetch('/api/version').then(r => r.json()).then(d => {
    document.getElementById('ver').textContent = d.version;
  });

  // Drop zone
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');

  ['dragenter','dragover'].forEach(ev =>
    dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.add('hover'); })
  );
  ['dragleave','drop'].forEach(ev =>
    dropZone.addEventListener(ev, e => { e.preventDefault(); dropZone.classList.remove('hover'); })
  );
  dropZone.addEventListener('drop', e => loadFile(e.dataTransfer.files[0]));
  fileInput.addEventListener('change', () => loadFile(fileInput.files[0]));

  function loadFile(file) {
    if (!file) return;
    _fileName = file.name;
    document.getElementById('file-name').textContent = '✓ ' + file.name;
    document.getElementById('run-btn').disabled = false;
    document.getElementById('report').style.display = 'none';
    document.getElementById('error-box').style.display = 'none';
    const reader = new FileReader();
    reader.onload = e => { _fileContent = e.target.result; };
    reader.readAsText(file);
  }

  // Run
  document.getElementById('run-btn').addEventListener('click', async () => {
    if (!_fileContent) return;
    const btn = document.getElementById('run-btn');
    btn.disabled = true;
    btn.textContent = 'Processing…';
    document.getElementById('error-box').style.display = 'none';
    document.getElementById('report').style.display = 'none';

    try {
      const resp = await fetch('/api/clean', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          content: _fileContent,
          filename: _fileName,
          dedup: document.getElementById('opt-dedup').checked,
        }),
      });
      const data = await resp.json();
      if (data.error) throw new Error(data.error);
      showReport(data);
    } catch (err) {
      showError(err.message || String(err));
    } finally {
      btn.disabled = false;
      btn.textContent = 'Run bibcleaner';
    }
  });

  function showReport(data) {
    const r = data.report;
    _cleanedContent = data.output;

    // Stats
    const grid = document.getElementById('stat-grid');
    grid.innerHTML = '';
    const stats = [
      ['Initial entries', r.initial_entries, false],
      ['Cleaned entries', r.cleaned_entries, false],
      ['Duplicates removed', r.duplicates_removed ?? 0, (r.duplicates_removed ?? 0) > 0],
    ];
    stats.forEach(([lbl, val, warn]) => {
      const d = document.createElement('div');
      d.className = 'stat' + (warn ? ' warn' : '');
      d.innerHTML = `<div class="val">${val}</div><div class="lbl">${lbl}</div>`;
      grid.appendChild(d);
    });

    // Warnings
    const ul = document.getElementById('warnings');
    ul.innerHTML = '';
    (data.warnings || []).forEach(w => {
      const li = document.createElement('li');
      li.textContent = w;
      ul.appendChild(li);
    });

    // Preview (first 4000 chars)
    document.getElementById('preview').textContent =
      _cleanedContent.length > 4000
        ? _cleanedContent.slice(0, 4000) + '\n… (truncated)'
        : _cleanedContent;

    document.getElementById('report').style.display = '';
  }

  function showError(msg) {
    const box = document.getElementById('error-box');
    box.textContent = 'Error: ' + msg;
    box.style.display = '';
  }

  // Download
  document.getElementById('dl-btn').addEventListener('click', () => {
    const blob = new Blob([_cleanedContent], {type: 'text/plain'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const stem = _fileName.replace(/\.bib$/i, '');
    a.download = stem + '.clean.bib';
    a.click();
    URL.revokeObjectURL(url);
  });
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# HTTP request handler
# ---------------------------------------------------------------------------

class _Handler(BaseHTTPRequestHandler):

    server: "BibCleanerServer"

    def log_message(self, fmt: str, *args: Any) -> None:
        pass  # suppress default request logging

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._respond(200, "text/html; charset=utf-8", _HTML.encode())
        elif self.path == "/api/version":
            body = json.dumps({"version": bc.__version__}).encode()
            self._respond(200, "application/json", body)
        elif self.path == "/shutdown":
            self._respond(200, "text/plain", b"Shutting down...")
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        else:
            self._respond(404, "text/plain", b"Not found")

    def do_POST(self) -> None:
        if self.path == "/api/clean":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                self._respond(400, "application/json", json.dumps({"error": "Bad JSON"}).encode())
                return

            result = _process(payload)
            self._respond(200, "application/json", json.dumps(result).encode())
        else:
            self._respond(404, "text/plain", b"Not found")

    def _respond(self, code: int, content_type: str, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------

def _process(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run bibcleaner on in-memory content and return a JSON-serialisable result."""
    content: str = payload.get("content", "")
    dedup: bool = bool(payload.get("dedup", True))

    try:
        entries = bc.parse_bibtex(content)
        initial_count = len(entries)

        cleaned = [bc.clean_entry(e) for e in entries]

        duplicates_removed = 0
        if dedup:
            cleaned, dedup_report = bc.deduplicate(cleaned)
            duplicates_removed = dedup_report.get("duplicates_removed", 0)

        output = "\n".join(f"{bc.format_entry(e)}\n" for e in cleaned)

        # Collect missing-field warnings
        warnings = []
        for e in cleaned:
            missing = e.missing_required_fields()
            if missing:
                warnings.append(f"[{e.key}] missing: {', '.join(missing)}")

        report: Dict[str, Any] = {
            "initial_entries": initial_count,
            "cleaned_entries": len(cleaned),
            "duplicates_removed": duplicates_removed,
            "deduplication_enabled": dedup,
        }
        return {"report": report, "output": output, "warnings": warnings}

    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

class BibCleanerServer(HTTPServer):
    pass


def _find_free_port(preferred: int) -> int:
    import socket
    for port in range(preferred, preferred + 20):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return preferred


def run_server(port: int = 8765, open_browser: bool = True) -> None:
    """Start the local web server and optionally open a browser tab."""
    port = _find_free_port(port)
    url = f"http://127.0.0.1:{port}"

    server = BibCleanerServer(("127.0.0.1", port), _Handler)
    print(f"bibcleaner GUI running at {url}", flush=True)
    print("Press Ctrl-C to quit.", flush=True)

    if open_browser:
        threading.Timer(0.4, webbrowser.open, args=[url]).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.", flush=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Launch the bibcleaner web GUI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--port", type=int, default=8765,
        help="Port to listen on (default: 8765; auto-increments if occupied)",
    )
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Do not open a browser tab automatically",
    )
    args = parser.parse_args()
    run_server(port=args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
