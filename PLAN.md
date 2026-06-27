# resourcer — Windows System Resource Dashboard

> A native desktop app that shows live CPU / RAM / disk / network usage with real-time
> charts and a sortable process list with a kill action. First desktop project — chosen
> because it teaches the core OS-boundary skill (background-thread polling + real-time
> charts without freezing the UI) with the least incidental friction.

**Status:** Planning · **Started:** 2026-06-26 · **Owner:** Tejas
**Stack:** Python 3.12 · PySide6 · psutil · pyqtgraph · pytest · pyright

---

## 1. Goal & Non-Goals

### Goal
Ship a single-window Windows desktop app that:
- Polls system metrics once per second on a background thread (UI never blocks).
- Renders scrolling real-time charts for CPU (overall + per-core), memory, disk I/O, network I/O.
- Shows a sortable process table (PID, name, CPU%, memory) refreshed every ~2 s.
- Lets the user terminate a selected process, with a confirmation dialog and graceful
  handling of permission errors.
- Packages to a distributable Windows executable.

### Definition of Done (measurable — the "README must state a number" rule)
- Refreshes **20+ metrics at 1 Hz**; UI stays responsive (**> 50 fps**, no freeze during process scan).
- Process kill completes in **< 200 ms** and never crashes on `AccessDenied`.
- Cold start to first chart point **< 2 s**.
- Single packaged build runs on a clean Windows 11 machine with no Python installed.
- **80%+ line coverage** on pure logic modules (format, buffers, sampler, models).

### Non-Goals (YAGNI — explicitly out of scope for v1)
- No cross-platform support (Windows only; psutil is portable but we don't test/ship Linux/macOS).
- No historical persistence to disk (in-memory ring buffer only).
- No GPU / temperature / fan sensors (Windows exposure is unreliable; stretch goal).
- No remote/agent monitoring, no web UI, no auth, no settings persistence in v1.
- No installer (.msi) in v1 — a portable build is enough.

---

## 2. Tech Stack & Rationale

| Concern | Choice | Why |
|---------|--------|-----|
| Language | Python 3.12 | Already fluent (firstApply); fastest path to a working app. |
| GUI | **PySide6** (Qt 6, LGPL) | Native widgets, official Qt binding, strong threading model via signals/slots. LGPL = safe to distribute. |
| Metrics | **psutil** | Gold-standard cross-platform metrics lib; one call per metric. |
| Charts | **pyqtgraph** | Built for *streaming* real-time plots; far faster than matplotlib for live data. Integrates natively with Qt. |
| Numerics | **numpy** | pyqtgraph dependency; used for chart arrays. |
| Tests | **pytest** + pytest-cov | Project standard. |
| Type gate | **pyright** | Project standard; run before every "done". |
| Packaging | **PyInstaller** | Mature, produces a Windows exe. |

### Dependency policy (security rule)
- Pin exact versions in `requirements.txt` (e.g. `psutil==6.0.0`, not `^`).
- Commit lock state. Run `pip-audit` before first install and on any version bump.
- All four runtime deps are well-maintained, high-download, permissive-licensed — but still
  run the **dependency-auditor** pass once `requirements.txt` is finalized.

---

## 3. Architecture

Three layers with a strict, one-directional dependency rule:

```
  ┌──────────────────────────────────────────────┐
  │ UI layer  (ui/, main_window.py)               │  Qt widgets, charts, table.
  │   - knows nothing about psutil                │  Receives MetricsSample via signal.
  └───────────────▲──────────────────────────────┘
                  │  Qt signal (queued, thread-safe)
  ┌───────────────┴──────────────────────────────┐
  │ Worker layer  (metrics/worker.py)             │  QObject on a QThread.
  │   - owns a QTimer, drives sampling            │  Emits sample_ready(MetricsSample).
  └───────────────▲──────────────────────────────┘
                  │  plain function call
  ┌───────────────┴──────────────────────────────┐
  │ Sampler layer  (metrics/sampler.py)           │  PURE-ish: wraps psutil, computes
  │   - stateless except last-counter cache       │  rates (delta / interval), returns
  │   - returns MetricsSample / list[ProcessInfo] │  dataclasses. Easy to unit-test.
  └──────────────────────────────────────────────┘
```

**Key rule:** the UI never imports psutil, and the sampler never imports Qt. This keeps the
sampler unit-testable without a Qt event loop and keeps OS-boundary code isolated.

### 3.1 Threading model (the crux of the project)

psutil calls are mostly fast, **but iterating all processes can take 50–100 ms** — enough to
visibly jank a 60 fps UI if done on the main thread. So sampling runs on a worker thread.

Pattern (idiomatic Qt — worker object moved to a thread that runs its own event loop):

1. `MetricsWorker(QObject)` holds the sampler state and **two `QTimer`s** (fast: metrics @1 s,
   slow: process list @2 s).
2. Create the worker, then `worker.moveToThread(thread)`.
3. The timers are **created and started inside the worker thread** (in a slot wired to
   `thread.started`) — a QTimer must live in the thread whose event loop drives it.
4. On each `timeout`, the worker samples psutil and **emits a signal** carrying the data.
5. The main thread connects that signal to a UI slot. Cross-thread signal delivery is
   **auto-queued by Qt → thread-safe** with no manual locks.

**Shutdown discipline (avoids "QThread destroyed while running" crash):** on window close,
stop the timers, call `thread.quit()`, then `thread.wait()` before the app exits.

### 3.2 Data model

```python
@dataclass(frozen=True)
class MetricsSample:
    ts: float                    # time.monotonic()
    cpu_overall: float           # 0..100
    cpu_per_core: tuple[float, ...]
    mem_percent: float
    mem_used: int                # bytes
    mem_total: int               # bytes
    disk_read_rate: float        # bytes/sec
    disk_write_rate: float       # bytes/sec
    net_sent_rate: float         # bytes/sec
    net_recv_rate: float         # bytes/sec

@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    name: str
    cpu_percent: float
    mem_rss: int                 # bytes
```

**Ring buffer:** one `collections.deque(maxlen=HISTORY_POINTS)` per chart series.
`HISTORY_POINTS = HISTORY_WINDOW_SECONDS / (POLL_INTERVAL_MS/1000)` → 60 points for a 60 s
window at 1 Hz. Appending past `maxlen` drops the oldest automatically — O(1), no manual trim.

### 3.3 Rates from counters
`disk_io_counters()` and `net_io_counters()` return **cumulative** totals. Rate =
`(current - previous) / elapsed_seconds`. The sampler caches the previous counters + timestamp.
**Clamp negative deltas to 0** (handles counter reset/wrap and the very first sample).

---

## 4. Project Structure

Every file stays **< 300 lines** (project hard limit). Split by responsibility.

```
resourcer/
├── PLAN.md                       # this file
├── README.md                     # written last (Phase 8), with screenshots + numbers
├── main.py                       # `python main.py` launcher → calls app.run()
├── requirements.txt              # pinned runtime deps
├── requirements-dev.txt          # pytest, pytest-cov, pyright, pyinstaller, pip-audit
├── pyrightconfig.json
├── pytest.ini
├── .gitignore
├── src/resourcer/
│   ├── __init__.py
│   ├── app.py                    # QApplication setup, high-DPI, wiring, run()
│   ├── main_window.py            # MainWindow: layout of charts + table + toolbar
│   ├── metrics/
│   │   ├── __init__.py
│   │   ├── models.py             # MetricsSample, ProcessInfo dataclasses
│   │   ├── sampler.py            # psutil wrappers + rate computation (pure-ish)
│   │   ├── worker.py             # MetricsWorker(QObject) + QThread lifecycle
│   │   └── buffers.py            # SeriesStore: named deques + numpy export
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── charts.py             # pyqtgraph chart widgets (CPU/mem/disk/net)
│   │   ├── process_table.py      # QAbstractTableModel + view + kill action
│   │   └── widgets.py            # small reusables (stat card)
│   └── util/
│       ├── __init__.py
│       ├── constants.py          # intervals, window size, top-N, named constants
│       └── format.py             # human_bytes, human_rate, percent — pure fns
└── tests/
    ├── test_format.py            # mirrors util/format.py
    ├── test_buffers.py           # mirrors metrics/buffers.py
    ├── test_sampler.py           # mirrors metrics/sampler.py (psutil monkeypatched)
    └── test_models.py
```

---

## 5. Metrics Collected

| Metric | psutil source | Notes / gotcha |
|--------|---------------|----------------|
| CPU overall % | `cpu_percent(interval=None)` | **First call returns 0.0** → prime once at startup. |
| CPU per-core % | `cpu_percent(interval=None, percpu=True)` | 4–16 line series; same priming. |
| Memory | `virtual_memory()` | `.percent`, `.used`, `.total`. |
| Disk I/O rate | `disk_io_counters()` | Cumulative → delta/interval. May be `None` on some systems → guard. |
| Network I/O rate | `net_io_counters()` | Cumulative → delta/interval. |
| Process list | `process_iter(['pid','name','cpu_percent','memory_info'])` | Per-proc `cpu_percent` needs priming (first call 0); wrap each in try for `AccessDenied`/`NoSuchProcess`. |

**Windows-specific gotchas to handle:**
- Per-process CPU% can exceed 100% (sum across cores) — display raw, optionally divide by
  `cpu_count()` behind a toggle (stretch).
- Some system processes raise `AccessDenied` on `.name()` / `.cpu_percent()` → skip the row,
  never crash the scan.
- High-DPI: Qt 6 auto-scales; just verify on a scaled display.

---

## 6. UI Layout

```
┌─ resourcer ─────────────────────────────────────────────┐
│ [⟳ 1s ▼]  CPU 23%   RAM 41%   ↓ 1.2 MB/s   ↑ 0.3 MB/s    │  ← toolbar: stat cards
├──────────────────────────────┬──────────────────────────┤
│  CPU %  (overall + per-core) │   Memory %                │  ← pyqtgraph, 60 s window
├──────────────────────────────┼──────────────────────────┤
│  Disk  R/W bytes/s           │   Network  ↑/↓ bytes/s    │
├──────────────────────────────┴──────────────────────────┤
│  Processes            [search…]            [ Kill PID ]  │
│  PID │ Name          │ CPU% ▼ │ Memory                   │  ← QTableView, sortable
│  ...                                                     │
└─────────────────────────────────────────────────────────┘
```

- Charts: fixed 60 s scrolling window, y-axis auto-range (CPU/mem locked 0–100).
- Process table: `QAbstractTableModel` + `QSortFilterProxyModel` for sort + name filter.
  Refresh by diffing/rebuilding the model every 2 s (≤ ~300 rows → cheap).
- Theme: dark by default (pyqtgraph `setConfigOption('background', ...)`); keep simple.

---

## 7. Process Kill — Safety

This is the one outward/destructive action; treat carefully (security + patterns rules):
1. User selects a row → reads the **PID from the model**, not screen text.
2. **Confirmation dialog** showing PID + name. Default button = Cancel.
3. `psutil.Process(pid).terminate()`; if still alive after a short wait, `kill()`.
4. Wrap in `try` for `psutil.NoSuchProcess` (already gone — treat as success) and
   `psutil.AccessDenied` (show a friendly "needs admin" message — never a traceback).
5. Never expose raw exception text to the UI.

---

## 8. Performance Plan (performance rules)

- Sampling on a worker thread; UI only does cheap `setData` calls.
- Reuse numpy arrays for chart data; avoid allocating per tick.
- pyqtgraph: disable antialiasing if profiling shows jank; it's fast by default.
- Process table: bounded by the OS process count; rebuild every 2 s, not every 1 s.
- No per-tick object churn in the sampler beyond the single immutable `MetricsSample`.
- Poll interval is a named constant, not a magic number — tunable in one place.

---

## 9. Testing Strategy (testing rules)

- **No real psutil / no Qt event loop in unit tests.** Monkeypatch psutil functions at the
  sampler boundary; inject fake counter values.
- `test_format.py` — `human_bytes(1536) == "1.5 KB"`, GB rollover, rate suffix, zero/negative.
- `test_buffers.py` — deque `maxlen` window behavior, append, numpy export shape.
- `test_sampler.py` — rate = delta/interval; **negative delta clamps to 0**; first-sample
  behavior; `disk_io_counters()` returning `None` is handled.
- `test_models.py` — dataclass immutability / construction.
- Worker, charts, table, kill = OS/Qt boundary → **exempt from unit tests**, covered by
  manual/E2E checks (per testing rules; OS-boundary calls are E2E-level).
- Target **80%+** on the four pure modules. Run `pytest --cov` + `pyright` before each "done".

---

## 10. Milestones (TDD + branch-per-phase; never commit to main)

Each phase: branch `feature/<phase>`, write failing tests first where logic exists, implement,
run `pyright` + `pytest`, then `--no-ff` merge.

- [x] **Phase 0 — Skeleton.** Repo `git init`; venv; pinned deps; `pyrightconfig.json`,
      `pytest.ini`, `.gitignore`; empty package; a bare `MainWindow` that opens. Type gate +
      empty test suite green. Run `pip-audit`.
- [x] **Phase 1 — Pure logic (TDD).** `util/format.py`, `metrics/models.py`,
      `metrics/buffers.py` with full tests. No Qt, no psutil yet.
- [x] **Phase 2 — Sampler (TDD).** `metrics/sampler.py` with psutil monkeypatched in tests;
      rate math + Windows gotchas covered.
- [x] **Phase 3 — Worker thread.** `metrics/worker.py`; wire signal to a slot that just
      `print`s samples. **Verify UI stays responsive** while sampling. Clean shutdown.
- [x] **Phase 4 — First live chart.** One CPU-overall pyqtgraph chart fed by the signal +
      ring buffer. The "it's alive" moment.
- [x] **Phase 5 — All charts + stat cards.** Per-core CPU, memory, disk, network; toolbar cards.
- [x] **Phase 6 — Process table.** Model/view + sort + name filter, 2 s refresh.
- [x] **Phase 7 — Kill + polish.** Confirmation + error handling; dark theme; poll-interval
      selector; About dialog.
- [x] **Phase 8 — Package & document.** PyInstaller build; `README.md` with the measured
      numbers from the Definition of Done.

---

## 10b. v2 — Task Manager Expansion (post-v1)

v1 shipped a passive dashboard. v2 turns it into an *understandable, actionable* task
manager. Same architecture rules: files < 300 lines, pure logic TDD'd at the sampler
boundary, Qt/OS calls E2E-only. Branch-per-phase, `--no-ff` merge.

- [ ] **Phase 9 — Meaning + process power.** Chart **readouts** (current · peak + units)
      and **threshold zones** so each graph states what it means. Richer process columns
      (Status, Threads, User, Uptime). **Right-click actions**: End task, End process tree,
      Suspend/Resume, Copy PID, Open file location. Per-process CPU normalization toggle.
      New testable logic: `human_duration`, `process_actions` (tree collection, suspend).
- [ ] **Phase 10 — Understandable layout.** Tabbed shell (Overview / Performance /
      Processes / Disks & Network). **System summary** panel: uptime, process/thread counts,
      top CPU + memory consumer, memory breakdown (used / cached / available).
- [x] **Phase 11 — Drill-down + storage.** Process **detail dialog** (threads, handles,
      open files, connections, cmdline, exe path) on double-click / right-click. **Per-drive
      capacity** bars (`disk_usage` per partition) in a new Disks tab. _(Per-interface
      network breakdown deferred to Phase 12.)_
- [~] **Phase 12 — Insight + polish.** _Done:_ per-interface network breakdown (Disks &
      Network tab) and CSV snapshot export. _Remaining:_ metric tooltips/explanations, row
      heat-coloring for hot processes, threshold **alerts**, settings persistence.

---

## 11. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Process scan janks the UI | Sampling on worker thread; process poll at 2 s, not 1 s. |
| QThread shutdown crash | Stop timers → `quit()` → `wait()` on window close. |
| First CPU sample reads 0% | Prime `cpu_percent` once at startup; drop/ignore first point. |
| Counter rates go negative on reset | Clamp negative deltas to 0 in the sampler. |
| `AccessDenied` on system procs | try/except per process; skip row; never crash. |
| PyInstaller onefile is huge & slow-start | Use **`--onedir`** for v1; consider onefile later. |
| Qt timer created in wrong thread | Create/start timers inside the worker thread via `thread.started`. |

---

## 12. Stretch Goals (post-v1, only if time)

- Minimize-to-tray + background polling.
- Threshold alerts (e.g. CPU > 90% for 30 s → notification).
- Per-disk and per-NIC breakdown.
- CSV export of the current history window.
- GPU stats via `pynvml` (NVIDIA only) behind a feature flag.
- Settings persistence (poll interval, window size, theme).

---

## 13. First Action

Phase 0 scaffold: `git init` on a `feature/skeleton` branch, create the package layout above,
pin deps in `requirements.txt`, add config files, and open a bare window. Then Phase 1 starts
test-first.
