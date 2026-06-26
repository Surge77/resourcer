# resourcer

A native Windows desktop dashboard for live system resources — real-time CPU,
memory, disk and network charts plus a sortable process manager with a kill
action. Sampling runs on a background thread so the UI never freezes.

**Stack:** Python 3.11 · PySide6 (Qt 6) · psutil · pyqtgraph · numpy

---

## Features

- **Live charts** (60-second scrolling window, 1 Hz):
  - CPU — overall load over per-core lines
  - Memory percent
  - Disk read / write rate (bytes/s, byte-formatted axis)
  - Network down / up rate (bytes/s)
- **Toolbar stat cards** — CPU %, RAM %, net down, net up at a glance.
- **Process table** — PID / name / CPU% / memory, sortable (numeric, not
  lexical) with a name filter; refreshes every 2 s and keeps your selection.
- **Kill a process** — confirmation dialog (defaults to Cancel), graceful
  terminate with a force-kill fallback, and friendly handling of
  permission-denied / already-exited cases. No traceback ever reaches the UI.
- **Adjustable poll interval** (1 s / 2 s / 5 s) and a dark theme.

## Measured numbers

Measured on a 12-thread Windows 11 machine:

| Metric | Target | Measured |
|--------|--------|----------|
| Metrics sampled per tick @ 1 Hz | 20+ | **20** (1 overall + 12 per-core + 3 memory + 2 disk + 2 net) |
| Cold start to first chart point | < 2 s | **~1.6 s** |
| UI responsiveness | no freeze | sampling off the UI thread; the only hitch is a brief (~90 ms) GIL pause while psutil scans all processes, which is why the process scan runs at 2 s, not 1 s |
| Process kill | safe, fast | terminate is immediate; force-kill fallback after a 0.5 s grace window; `AccessDenied`/`NoSuchProcess` never crash |
| Pure-logic test coverage | 80%+ | **100%** (123 statements, 40 tests) |

## Architecture

Three layers with a strict one-directional dependency rule — the UI never
imports psutil, and the sampler never imports Qt:

```
UI (main_window, ui/)        Qt widgets, charts, table — receive samples via signal
   ▲ Qt signal (auto-queued, thread-safe)
Worker (metrics/worker)      QObject on a QThread; two QTimers drive sampling
   ▲ plain call
Sampler (metrics/sampler)    psutil wrapper; turns cumulative counters into rates
```

This keeps the OS-boundary code isolated and the pure logic unit-testable
without a Qt event loop. See [PLAN.md](PLAN.md) for the full design.

## Run from source

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Develop

```bash
pip install -r requirements-dev.txt
pytest                      # run tests
pytest --cov=src            # with coverage
pyright                     # type gate
pip-audit -r requirements.txt
```

## Build a portable executable

```bash
pyinstaller --noconfirm --onedir --windowed --name resourcer \
  --paths src --collect-submodules pyqtgraph main.py
```

The build lands in `dist/resourcer/`. It is a portable `--onedir` bundle
(~160 MB, mostly Qt + numpy) that runs without Python installed. The binary is
unsigned, so Windows SmartScreen / Application Control may warn on first launch.

## License

MIT
