import json
import os
import subprocess
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

PIN_PS = r'''
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win {
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr ib, int x, int y, int cx, int cy, uint u);
}
"@
$p = Get-Process chrome -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -eq "Claude Tokens" } | Select-Object -First 1
if (-not $p) { Write-Output "not-found"; exit 1 }
$topmost = [IntPtr]({TOPMOST})
[Win]::SetWindowPos($p.MainWindowHandle, $topmost, 0, 0, 0, 0, 0x0001 -bor 0x0002)
Write-Output "ok"
'''


def set_pin(pinned):
    hwnd = "-1" if pinned else "-2"
    script = PIN_PS.replace("{TOPMOST}", hwnd)
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True, text=True, timeout=10,
    )
    if "ok" not in result.stdout:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "pin failed")

CREDS_FILE = os.path.join(os.path.expanduser("~"), ".claude", ".credentials.json")


def fetch_live_usage():
    """Hit Anthropic's OAuth usage endpoint with the local Claude Code token.
    Returns the real session/weekly percentages in well under a second."""
    with open(CREDS_FILE, "r", encoding="utf-8") as f:
        tok = json.load(f)["claudeAiOauth"]["accessToken"]
    req = urllib.request.Request(
        "https://api.anthropic.com/api/oauth/usage",
        headers={"Authorization": "Bearer " + tok, "anthropic-beta": "oauth-2025-04-20"},
    )
    raw = json.loads(urllib.request.urlopen(req, timeout=10).read().decode("utf-8"))
    out = {"fetched_at": datetime.now().strftime("%H:%M:%S"), "limits": []}
    for lim in raw.get("limits", []):
        scope = lim.get("scope") or {}
        model = (scope.get("model") or {}).get("display_name")
        if lim["kind"] == "session":
            label = "SESSION"
        elif lim["kind"] == "weekly_all":
            label = "WEEKLY"
        elif model:
            label = model.upper()
        else:
            label = lim["kind"].upper()
        out["limits"].append({
            "label": label,
            "percent": lim.get("percent", 0),
            "severity": lim.get("severity", "normal"),
            "resets_at": lim.get("resets_at"),
        })
    return out

ROOT = os.path.dirname(os.path.abspath(__file__))
USAGE_FILE = os.path.join(ROOT, "usage.json")
WIDGET_FILE = os.path.join(ROOT, "widget.html")
SYNC_STATE_FILE = os.path.join(ROOT, "sync_state.json")
NOTE_FILE = os.path.join(ROOT, "note.json")
PORT = 8743


def load_note():
    try:
        with open(NOTE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        text = data.get("text")
        if not isinstance(text, str):
            return {"text": ""}
        return {"text": text}
    except Exception:
        return {"text": ""}


def write_note(text):
    with open(NOTE_FILE, "w", encoding="utf-8") as f:
        json.dump({"text": text}, f, ensure_ascii=False)


def load_usage():
    try:
        with open(USAGE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e)}


def load_sync_state():
    try:
        with open(SYNC_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"stage": 0, "done": True, "error": None, "requested": False}


def write_sync_state(state):
    with open(SYNC_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # keep console silent — this runs headless via pythonw

    def do_POST(self):
        path = self.path.split("?")[0]

        if path == "/sync-start":
            # Marks a sync request as pending — the live Claude Code session
            # (which alone can drive Chrome + Drive) watches this flag and
            # advances stage/done/error as the pipeline actually progresses.
            write_sync_state({"stage": 0, "done": False, "error": None, "requested": True})
            body = json.dumps({"ok": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/sync-write":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                incoming = json.loads(raw)
            except Exception:
                incoming = {}
            with open(USAGE_FILE, "w", encoding="utf-8") as f:
                json.dump(incoming, f)
            write_sync_state({"stage": 8, "done": True, "error": None, "requested": False})
            body = json.dumps({"ok": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/note":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b""
            ok = False
            try:
                incoming = json.loads(raw)
                text = incoming.get("text") if isinstance(incoming, dict) else None
                if isinstance(text, str) and len(text.encode("utf-8")) <= 100 * 1024:
                    write_note(text)
                    ok = True
            except Exception:
                ok = False
            body = json.dumps({"ok": ok}).encode("utf-8")
            self.send_response(200 if ok else 400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path in ("/pin", "/unpin"):
            try:
                set_pin(path == "/pin")
                body = json.dumps({"ok": True}).encode("utf-8")
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/sync-status":
            data = load_sync_state()
            body = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/note":
            data = load_note()
            body = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/live":
            try:
                data = fetch_live_usage()
            except Exception as e:
                data = {"error": str(e)}
            body = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/refresh":
            data = load_usage()
            body = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path in ("/", "/widget.html"):
            try:
                with open(WIDGET_FILE, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                self.send_response(404)
                self.end_headers()
            return

        if path.endswith(".ico"):
            ico_path = os.path.join(ROOT, os.path.basename(path))
            if os.path.isfile(ico_path):
                with open(ico_path, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "image/x-icon")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

        self.send_response(404)
        self.end_headers()


def already_running():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", PORT))
        return True
    except OSError:
        return False
    finally:
        s.close()


def main():
    if already_running():
        return
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
