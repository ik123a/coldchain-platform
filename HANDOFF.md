# ColdChain Rescue — Handoff Brief for Continuing Agent

**Date:** 2026-09-27
**Repo:** `D:\Projects\capstone project\coldchain-platform`
**Related:** `D:\Projects\capstone project\coldchain-rescue` (Milestone-1, separate, all tests pass)
**Original requirements:** `D:\Projects\capstone project\university-docs` (docx, not yet extracted)
**Note:** this repo already has `.hermes/plans/` (three plans dated 2026-09-13, all predating the
work described here). Read them for intent, but they are stale on the items in §6.

---

## 1. What this project is

ColdChain Rescue — a cold-chain logistics **digital twin / operations command center**.
CBCA301 Capstone (Bennett University). Stack: Next.js 15 App Router + React 19 + Tailwind 4
frontend, FastAPI + SQLAlchemy + SQLite backend, WebSocket telemetry.

**The simulation engine works and must not be rebuilt or replaced.**

### Critical architecture truth
The "AI" is **deterministic rule-based Python**, not an LLM.
- `backend/app/simulation/agents_d.py` — 6 operational agents, docstring says *"Pure-python — works with zero API keys"*
- `backend/app/simulation/fleet_agents.py` — *"No LLM needed"*
- Real LLM calls exist **only** in `backend/app/services/gemini/` and only generate **design reference images/videos** (a build-time asset tool).
- BUT the UI header displays **"AI ENGINE: LLM"** because `core/config.py` sets `AI_MODE = "LLM"` merely because a Gemini key string exists.
- The multi-agent *architecture* is legitimate (6 named agents + coordinator), but **no LLM participates in operations**. This is a material misrepresentation given the project claims T3 Agentic AI. Decide: relabel, or integrate.

---

## 2. Environment / how to run

| Item | Value |
|---|---|
| Backend | `http://127.0.0.1:8000` |
| Frontend | `http://localhost:3100` (dev) |
| Backend start | `backend\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000` from `backend/` |
| Frontend start | `npx next dev -p 3100` from `frontend/` |
| Python | venv 3.13.9 (use `.venv` python for all backend work) |
| DB | `backend/coldchain.db` (SQLite, 15 tables) |
| Logs | `.run\backend.err.log`, `.run\backend.out.log`, `.run\frontend.err.log` |

### ENV VAR — this bit me
The backend reads **`CORS_ORIGINS`**, *not* `ALLOWED_ORIGINS`:
```python
# backend/app/core/config.py:18
CORS_ORIGINS = [o.strip() for o in os.getenv(
    "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000").split(",")]
```
Default does **not** include :3100. Always start the backend with:
```powershell
$env:CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000,http://localhost:3100,http://127.0.0.1:3100,http://localhost:8000"
```
Symptom of getting it wrong: every fetch fails with `blocked by CORS policy` and the page renders empty shells.

### NEVER run `npm run build` while `next dev` is serving
Production build writes `BUILD_ID` / `export-marker.json` into the same `.next` the dev server
uses → **HTML loads but React hydration is dead** (markers never appear, no console error).
Recovery: kill dev, `Remove-Item -Recurse -Force frontend\.next`, restart dev.
For type checks use `npx tsc --noEmit`, which is safe.
Also: the dev server bloats to **~824 MB RSS** after a long editing session. Restart it if the
machine feels slow. A fresh dev server is ~115 MB.

### Subagent delegation is BROKEN in this environment
`visual-engineering` and `unspecified-high` categories are pinned to model
`opencode/gpt-5-nano`, which does not exist. Three attempts all failed with
`ProviderModelNotFoundError`. Do the work inline.

---

## 3. Data contracts you must know

### Vehicle snapshot — `GET /api/fleet/state` → `vehicles[]`
```jsonc
{
  "vehicle_id": "TRUCK-1824-00", "type": "EV_REEFER",   // or "SERVICE_TRUCK"
  "lat": 28.53, "lng": 77.19,
  "heading": 68.0,          // COMPASS degrees, 0=N, 90=E
  "direction": "North-East",
  "speed_kmh": 34.0, "status": "IN_TRANSIT",
  "alerts": 0,              // present in backend, was missing from the TS type (now added)
  "trip": { "route_id": "R-7", "origin_id": "WH-007", "destination_id": "WH-004",
            "distance_total_km": 12.0, "distance_remaining_km": 2.0,
            "eta_min": 6.0, "route_progress_percent": 83.2 },
  "refrigeration": { "temperature": 5.2, "humidity": 61.0, "compressor_status": "ON" },
  "cargo": { "cargo_type": "fresh_produce", "load_percent": 34.0, "load_units": 340,
             "risk_level": "LOW", "risk_score": 12.0, "time_to_critical_min": null },
  "driver": { "name": "...", "driving_score": 94 },
  "vehicle": { "engine_status": "RUNNING", "fuel_percent": 70.0, "battery_percent": 80.0 },
  "outside_temperature": 32.9
}
```

### Route geometry (`v.geom`) is NOT in the snapshot
`vehicle.position.updated` (the high-frequency WS event) carries snapshots only. Geometry is
reachable from exactly two places:
- `GET /api/fleet/vehicle/{vid}` → `{ snapshot, recent_events, geometry: [[lng,lat], ...] }` (capped 120 pts)
- WS event `vehicle.route.changed` → `geometry` (capped 80 pts)

The page fetches per-vehicle and re-fetches when `trip.route_id` changes
(rebuild / divert / respawn). Do **not** "optimise" this into the bulk state payload — the key
isn't there.

### WebSocket event vocabulary (`ws://127.0.0.1:8000/ws`)
Frequent: `vehicle.position.updated`, `cargo.transferred`, `traffic.changed`, `weather.changed`,
`vehicle.idling`, `vehicle.stopped`, `hello`.
Incident chain: `fleet.incident.created` → `ai.analysis.started` → `ai.route.decision` →
`vehicle.route.changed`.
Also: `geofence.entered` / `geofence.exited`, `service.dispatched`, `vehicle.failure.injected`.

### Real API contracts
| Endpoint | Body |
|---|---|
| `POST /api/fleet/speed` | **`{"speed": 5}`** — the field is `speed`, NOT `multiplier`. `multiplier` → HTTP 422 |
| `POST /api/fleet/pause` / `resume` | `{}` |
| `POST /api/fleet/weather` | `{"weather": "HEATWAVE"}` (NORMAL/HEATWAVE/RAIN/FOG) |
| `POST /api/fleet/rebuild` | `{"fleet_size": 12, "seed": 7}` |
| `POST /api/fleet/vehicle/{id}/inject` | `{"failure": "compressor_failure"}` |
| `POST /api/fleet/inject-random` | `{}` |
| `POST /api/fleet/service/dispatch` | `{"vehicle_id": "...", "task": "repair"}` |
| `POST /api/fleet/transfer` | `{"from_vehicle_id": "...", "to_vehicle_id": "..."}` |
| `POST /api/fleet/demo` | `{}` — the "Run Autonomous Demo" button |

`/api/fleet/state` is the fleet list (**not** `/api/fleet/vehicles`, which 404s).
`/api/fleet/state.counts` gives: `vehicles, in_transit, at_risk, critical, arrived, completed, active_incidents`.

---

## 4. Work completed and verified (do not regress)

Everything below was **observed in the running app**, not inferred from code.

### Backend fixes
| Fix | Detail |
|---|---|
| Geofence event collision | `runner.py` `Broadcast.emit` built `{"type": etype, ..., **payload}` — the spread came *after* `type`, so payloads containing `type` overwrote the event name. `geofence.entered` shipped as `WAREHOUSE`/`DELIVERY`/`EMERGENCY`. Fixed by moving `**payload` first AND renaming the payload key to `fence_type` in both calls. Verified: `acceptance_sweep.py` now reports `PASS - event observed: geofence.entered`, and the UI feed shows `entered WH-005`. |
| Event retention | `fleet_vehicle_events` had grown to **190,067 rows** with zero prune/vacuum anywhere. Added `EVENT_RETENTION_HOURS = 6`, `_prune_events()` (deletes only `VehicleEvent` rows older than cutoff; `incidents`, `ai_analyses`, `recommended_actions`, `alerts`, `fleet_route_decisions` untouched), called every 2400 ticks from `_run()`. Verified 190,067 → 31,441 rows; backend RSS 99 MB after 5 h. |
| CORS | Set correct `CORS_ORIGINS` on start (see §2). |

### Frontend — Phase 1 (map visualisation)
| Feature | Verification evidence |
|---|---|
| **Route lines** | 38–39 polylines, real backend geometry (up to 120 pts), split by `trip.route_progress_percent` into travelled (`#34d399`) + upcoming dashed (`#38bdf8`) |
| **Travelled trails** | `#7dd3fc`, built from real positions, rolling cap 40 |
| **Truck icons + heading** | **12 rotated markers, 12 distinct angles** (68, 85, 93, 117, 142, 150, 196, 209, 238, 273, 309, 315 degrees). Was **0** before |
| **Zoom scaling** | glyph 17–23 px at zoom 9.3 → **35 px** zoomed in |
| **Incident markers** | pulsing severity pin at real `snapshot.lat/lng`; appears ~18 s after failure |
| **AI reroute** | purple `#a78bfa` new rescue route + grey `#64748b` stale old route (15 s window), 38→39 polylines |

**Route colour vocabulary** (keep consistent): `#34d399` travelled · `#38bdf8` upcoming (dashed) ·
`#fbbf24` warning · `#f87171` critical · `#a78bfa` reroute · `#64748b` stale old route ·
`#7dd3fc` trail.

### Frontend — Phase 2
| Feature | Evidence |
|---|---|
| Vehicle detail panel | `onScreen: true`; shows SPEED/HEADING (34 km/h, NE 33 deg), ETA (6 min, 2.0 km), TEMP (5.2 C "Safe 2-8C"), CARGO, RISK + SPEED/TEMP/RISK sparklines, Track + inject buttons |
| Camera follow | Truck locked at (453, 337) over 12 s — **`x_range: 0, y_range: 0`** |
| KPI bar | all 8 tiles present: ACTIVE, TRANSIT, AT RISK, INCID, EXCURSION, REROUTE, XFER, DELIV |
| Sim controls | `1x 2x 5x 10x` verified end-to-end (backend `speed` went 2→5→1), weather select, Incident, Reset |

### Bugs found and fixed during verification
| Bug | Cause | Fix |
|---|---|---|
| Detail panel invisible (199 px below viewport) | `FloatingVehicleInspector` had **both `absolute` and `relative`** in its own `className`; Tailwind emitted both, `relative` won | removed the stray `relative` |
| Camera follow lagged 213 px | rAF called `map.easeTo({duration: 320})` **every frame** — each ease ~5% complete before retarget | `duration: 80` |
| Reroute colours never appeared | `fleetEvents.find(e => e.type === "vehicle.route.changed")` returns the **oldest** match; the ring is newest-first | use the last element via a `useMemo` |
| 3 TS errors | `route_id` and `alerts` missing from `VSnap` though the backend returns both | added to the type |

---

## 5. Map architecture — why it is built this way

**MapLibre's GeoJSON worker does not load in this Next build.** Every `addSource`/`addLayer`
for `route` / `trail` / `veh` / `inc` is created and silently renders **nothing**. This is why
the map was "dots on a map" for so long. `map-markers.tsx` originally documented the same issue
for symbol layers (which also need a `glyphs` endpoint the basemap-only style lacks).

**Do not try to fix the worker.** The working approach is a projected DOM/SVG overlay:
- MapLibre owns: basemap, camera, zoom/pan, coordinate system
- `map.project([lng,lat])` converts geo → screen space
- `frontend/components/ui/map-markers.tsx` — point markers (buttons positioned by `left/top`)
- `frontend/components/ui/map-overlay.tsx` — **new**; routes/trails/incidents as SVG `<polyline>`
  and `<g>`, children created once per identity change and **mutated per animation frame**

### Heading rotation gotcha
Backend `heading` is a **compass bearing**: `degrees(atan2(dlng, dlat))`, so 0=N, 90=E
(`fleet.py:295`). CSS `rotate()` is clockwise-from-up. Therefore the truck glyph **must be drawn
pointing north** so `rotate(heading)` is correct with no offset. This is noted in a comment in
`map-markers.tsx` — do not remove it, it prevents a silent 90-degree error.

### Ordering / stacking
`MapOverlay` is `z-[5]`, `MapMarkers` is `z-10`, both `absolute inset-0` inside the map card.
Any new absolute panel must live **inside a positioned ancestor** — see the `relative`/`absolute`
bug in §4.

---

## 6. OUTSTANDING WORK

### A. Awwwards MCP visual redesign — NOT STARTED
This has **never been done**. All work so far was functional. If the goal is award-level visual
quality, start here:
- `awwwards_search_sites` / `awwwards_get_site_details` / `awwwards_get_site_elements` are available
- `awwwards_capture_live_site`, `awwwards_analyze_page_structure`, `awwwards_record_site_motion` for capture
- If awwwards-mcp itself misbehaves, read `C:\Users\SKV\.config\opencode\skills\awwwards-doctor\SKILL.md`
- Design language to preserve: dark command-centre, `bg-[#0E121A]/95`, `border-[#1E2638]`, CSS vars
  `--accent / --canvas / --text / --text3 / --cyan`, classes `base-card, badge, badge-green,
  badge-red, btn, btn-amber, chip`, `font-mono` for numbers, `text-[10px]`–`text-[12px]` labels.
  No gradients, no oversized cards, no emoji, no cartoon graphics.
- Useful skills: `design-taste-frontend`, `high-end-visual-design`, `awwwards-motion-study`,
  `awwwards-inspiration`. There is a `design-system/` folder with tokens and a
  `design-references/CRITIQUE_REPORT.md` already in the repo.

### B. Crash investigation — no crash reproduced; needs your reproduction
I found **zero** tracebacks / `MemoryError` / exceptions in `.run\backend.err.log` across a ~5 h run.
Both servers stayed up. Measured healthy:
- backend RSS **99 MB** after 5 h; retention prune firing cleanly every ~10 min (~900 rows)
- store arrays all capped: `fleetEvents slice(0,90)`, `events slice(0,90)`, `history slice(-400)`, `toasts slice(-5)`
- backend in-memory capped: `_incident_tel` <= 2400 per incident, `event_ring` <= 90
- **Browser-side JS heap soak was never completed** — this is the main untested surface.

Suspects worth checking, in order:
1. **`simulations_running: 9`** — the Milestone-1 subsystem keeps 9 `SimulationRunner` loops alive.
   Each holds `_tel` frames and emits `sensor_update` over the shared WS. This is the strongest
   candidate for both backend memory growth and frontend event pressure. Consider capping or
   lazily starting M1 runners.
2. **Browser heap growth** — measure `performance.memory.usedJSHeapSize` over 10+ min with 14
   vehicles. `MapOverlay` has its own rAF + 4 registries; confirm `sync()` is evicting children.
3. `next dev` bloat — restart it (824 MB → 115 MB observed). This looks like "slowness", not a crash.
4. MapLibre WebGL: `"GPU stall due to ReadPixels"` warnings appear (screenshot-induced, likely benign).

**Ask the user what they actually see** — browser tab crash, freeze, backend death, or slow? The
logs say the backend is healthy, so the symptom may be frontend-side or a specific interaction.

### C. `service.completed` acceptance-sweep failure — sweep contract, NOT a backend bug
`acceptance_sweep.py` now fails only on `service.completed`. That event fires at
`fleet_orchestrator.py:523` only when a service truck closes to **0.8 km** of a broken truck.
Delhi-NCR legs are tens of km and the window is 60 s, so it is unreachable. Per the user's explicit
instruction: **do not distort simulation physics to make it pass.** Either assert
`service.dispatched` instead, or lengthen the window. Low priority.

### D. Agent-name inconsistency
`runner.py:174` persists `agent_name="risk"`; the class and UI use `risk_analyst`. Also only 4 of 6
agents persist analyses (`monitoring` / `response_planner` do not).

### E. Committed secrets — rotate before any submission
Three real Gemini API keys are hardcoded in `backend/app/core/config.py` (used as `os.getenv`
fallback defaults) and present in `backend/.env`. Rotate all three, empty the fallbacks, add
`.env.example`.

### F. Auth posture — undecided
Auth is implemented (`auth.py`, pbkdf2 + JWT) but **not enforced on any of ~45 business routes**;
the frontend never sends a token; the `users` table is empty. Either enforce or document as
deliberately demo-scope. This is a decision, not a bug to fix silently.

### G. Route geometry looks straight — upstream, not frontend
`routing.py:53` tries **OSRM first** for real road-following geometry. OSRM is unreachable in
this sandbox, so it falls back to `_fallback`, and for node-pairs missing from `geo_data.POLYLINES`
that fallback is literally **3 points: origin → jittered midpoint → destination**
(`routing.py:98-103`). Self-heals with network access. Do not fake roads.

### H. Minor
- Legend still shows a dot for "vehicle" instead of the truck glyph; the incident entry only
  appears when an incident is active
- Two API access patterns coexist: `lib/api.ts` uses absolute `http://127.0.0.1:8000` (needs CORS);
  reports + design-references use relative `/api/...` through the `next.config.mjs` rewrite
- No README for `coldchain-platform`; root `docs/` and `tests/` are empty; no CI; no Docker
- `next.config.mjs` sets `typescript.ignoreBuildErrors: true` and `eslint.ignoreDuringBuilds: true`
  — **`npm run build` does not typecheck or lint.** Use `npx tsc --noEmit`.

---

## 7. Verification commands (run these, don't assume)

```powershell
# backend suites — MUST all exit 0
$py = "D:\Projects\capstone project\coldchain-platform\backend\.venv\Scripts\python.exe"
Push-Location "D:\Projects\capstone project\coldchain-platform\backend"
foreach ($t in @("tests\test_fleet_twin.py","tests\test_fleet_ai.py","tests\test_fleet_ops.py",
                 "tests\test_world_events.py","tests\test_scenario_analytics.py")) {
  & $py $t; "  $t EXIT=$LASTEXITCODE" }
& $py -m tests.sim_regression; "  sim_regression EXIT=$LASTEXITCODE"
& $py tests\acceptance_sweep.py   # geofence should PASS; service.completed expected to FAIL (see 6C)
Pop-Location

# typecheck — MUST exit 0
Push-Location "D:\Projects\capstone project\coldchain-platform\frontend"
npx tsc --noEmit; "  TSC EXIT=$LASTEXITCODE"
Pop-Location
```

### Headless browser verification pattern that works here
`everything-claude-code_playwright_*` is **unavailable** (Playwright MCP Bridge extension not
installed). Use system Python 3.10 which has Playwright + cached Chromium:
```powershell
$py = @'
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width":1600,"height":1000})
    errs=[]; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("console", lambda m: errs.append(m.text) if m.type=="error" else None)
    pg.goto("http://localhost:3100/live-map", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_selector("div.pointer-events-none button", timeout=40000)
    ...
'@
$py | python -
```
Key selectors that actually work:
- markers: `div.pointer-events-none.absolute.inset-0 button`
- heading rotation: a descendant `span` whose computed `transform` is a `matrix` with
  `abs(m[1])>0.01` or `abs(m[2])>0.01`, then `atan2(m[1], m[0])` -> degrees
- routes: `Array.from(document.querySelectorAll('svg')).filter(s=>s.querySelector('polyline')).pop()`
  then filter `polyline` where `points` length > 10
- incident pins: count `g` inside that same overlay `<svg>`

Wait ~18–20 s after load before sampling: the page fetches per-vehicle geometry, so routes are
absent for the first several seconds. Fewer than ~20 polylines usually means the geometry fetch broke.

---

## 8. Files changed in this work

| File | Change |
|---|---|
| `backend/app/simulation/runner.py` | `**payload` moved before reserved keys in `Broadcast.emit` (1 line) |
| `backend/app/simulation/fleet_orchestrator.py` | 2 geofence payloads `type`→`fence_type`; `from datetime import timedelta`; `from sqlalchemy import delete`; `EVENT_RETENTION_HOURS = 6`; `_prune_events()`; prune call every 2400 ticks |
| `frontend/components/ui/map-overlay.tsx` | **NEW** — SVG route/trail/incident overlay via `map.project()` |
| `frontend/components/ui/map-markers.tsx` | `TruckGlyph`; `MapPoint` gains optional `heading`/`kind`; rotation; pulse ring; zoom scaling |
| `frontend/components/live-map/FloatingVehicleInspector.tsx` | removed stray `relative` that overrode `absolute` |
| `frontend/app/live-map/page.tsx` | overlay wiring; route-geometry state/fetch; reroute-stale logic; `routeGeom`/`staleGeom`; `kpis` memo; speed/weather/inject/reset controls; `relative` on map column; `duration: 80` follow; `VSnap` gained `route_id` + `alerts`; `RotateCcw` import |
| `frontend/app/globals.css` | `@keyframes pulse-ring` |

Pre-existing uncommitted changes from earlier sessions are also present across
`app/{analytics,dashboard,incidents,layout,shipments-live,simulation,twin}` and
`components/{CommandPalette,Layout,RiskGauge,Toasts}` + `components/live-map/*`. **Do not discard.**

---

## 9. Recommended order for the next agent

1. **Ask the user what the crash actually is** (browser tab / freeze / backend death / slow).
   Do not "fix" what you cannot reproduce.
2. Instrument and run a **10-minute browser heap soak**; investigate `simulations_running: 9`.
3. If the goal is visual quality, do the **awwwards MCP redesign** (see 6A) — it is entirely untouched.
4. Resolve the **AI-mode honesty** question and the **auth posture** decision (see 1 and 6F).
5. Rotate the committed Gemini keys (see 6E) before any submission.
6. Write the missing platform README; decide whether to enable `ignoreBuildErrors: false`.
