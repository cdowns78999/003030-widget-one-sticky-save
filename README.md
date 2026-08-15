# 003030 — widget-one-sticky-save

Local Windows widget (`poll.py` + `widget.html`) with three independent concerns:
- **HANG** — always-on-top pin, PowerShell `SetWindowPos`.
- **CLAUDE** — usage gauges, polls `/live`.
- **STICKY** — real editable note, autosaves to `note.json` via `/note`, mirror-dot
  pings on keystroke and backs up again after 2 minutes idle.

## Run
```
pythonw poll.py
chrome --app=http://127.0.0.1:8743/widget.html --window-size=380,380
```
Or use `startup_widget.vbs` (silent launch, wired into Windows Startup).

`note.json` is gitignored (personal note content) — see `note.json.example` for the shape.
