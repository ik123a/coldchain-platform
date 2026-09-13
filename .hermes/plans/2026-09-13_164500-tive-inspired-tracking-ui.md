# Plan: Tive-Inspired Live Map & Shipment-Tracking UI for ColdChain Rescue

## Goal

Rebuild `/live-map` (and add a `/shipments-live` list view) so the UI reads like Tive's professional cold-chain tracking platform — windowed map+list layout, status-tabbed vehicle/shipment rows with inline sensor readings, alert-count badges, split completed/upcoming path rendering on the map, per-vehicle event timelines — while keeping every value backend-driven.

## Current context / assumptions

- Repo: `D:\projects\capstone project\coldchain-platform\` — git-tracked, last commit `64c21cf`.
- Backend (port 8000, running): FastAPI + fleet orchestrator — 12 vehicle twins, WS `vehicle.position.updated` (~4 Hz, full snapshots incl. `trip`, `refrigeration`, `cargo`, `driver`, `connectivity`), event stream (`fleet.incident.created`, `ai.route.decision`, `vehicle.route.changed`, `cargo.transferred`, `vehicle.event`), REST `/api/fleet/state|vehicle/{id}|route-compare/{vid}|...`. All verified working.
- Frontend (port 3000, running): Next.js 15 App Router, Tailwind v4, maplibre-gl 6.9, framer-motion 13.2, recharts. `/live-map` currently has: rotating truck icons, risk halos, trails (last 10 s), route polyline, incident pulse, vehicle panel, AI decision card, event feed, filters, search, layers menu, demo button. Store in `frontend/lib/store.tsx` already dispatches `fleet` (snapshots) and `fleet_event` (events).
- Build green (`next build` exit 0, last verified). `frontend/build_log.txt` is committed by accident — remove it and gitignore.
- **Tive patterns distilled from their support docs** (the actual design targets):
  1. Windowed View (map + table side-by-side) ↔ Fullscreen View toggle
  2. List rows carry: shipment/vehicle ID, origin→destination, last known location, **latest sensor readings inline (red when alert-triggering)**, **alert-count badge color-coded by severity**, last-connection time
  3. Status tabs: In-Transit / At Risk (alerts) / Completed
  4. Shipment map: origin & destination markers, current-location marker, **alert markers at excursion locations (clustered when close)**, geofence rings at leg endpoints, **completed path = solid line, upcoming path = dashed line**
  5. Shipment timeline: chronological event list tied to the map
  6. Filters: origin/destination node, alert type, status; alert-context ("where did the excursion happen")
- Taste discipline (per skill, adapted to UI): one coherent visual grammar — dark ops canvas, status colors ONLY for state (green/amber/red/cyan), no decorative gradients; density and rhythm over novelty; every accent means something.

## Architecture / proposed approach

Pure frontend work over existing WS/REST contracts — no backend changes except two tiny additive endpoints (list-friendly alert counts; per-vehicle event history is already served by `/api/fleet/vehicle/{vid}` `recent_events`). The live-map page is restructured into a Tive-style **windowed layout**: left = status-tabbed fleet table (sortable, inline sensor chips, alert badges), right = map with **split-path rendering** (solid completed / dashed upcoming computed from `trip.route_progress_percent` against the geometry) plus clustered alert markers. A **fullscreen mode** hides the table; a **timeline drawer** opens under the map for the selected vehicle. Keep the existing rAF interpolation and layer stack; add maplibre `Marker`-free clustering via a simple zoom-dependent grid (12–50 vehicles, no supercluster dep — YAGNI).

---

## Step-by-step tasks

### Task 0: Clean build artifacts from git
- `frontend/.gitignore`: append `build_log.txt`.
- `git rm --cached frontend/build_log.txt`.
- **Verify:** `git status --short` shows no build_log.txt staged after next commit.

### Task 1: Backend — fleet state gains per-vehicle alert summary (additive, 1 field)
**File:** `backend/app/simulation/fleet_orchestrator.py`

In `FleetOrchestrator.__init__` add `self.alert_counts: dict[str, int] = {}`. In `_evt()` increment `self.alert_counts[v.id]` when `severity != "info"`. In `state()` add to each vehicle snapshot merge:
```python
snaps = []
for vid, v in self.vehicles.items():
    s = v.snapshot()
    s["alerts"] = self.alert_counts.get(vid, 0)
    snaps.append(s)
```
Also add to `state()`: `"counts": {... existing ..., "in_transit": sum(1 for s in snaps if s["status"] == "IN_TRANSIT"), "completed": sum(1 for s in snaps if s["status"] == "ARRIVED")}` — in_transit already derivable; just add `completed`.

**Verify:** restart backend, `curl -s http://127.0.0.1:8000/api/fleet/state | python -c "import json,sys; d=json.load(sys.stdin); print(d['vehicles'][0]['alerts'], d['counts'])"` → prints `0 {...,'completed': N}`.

**Commit:** `feat(fleet-ui): per-vehicle alert counts in state payload`.

### Task 2: Store — keep a rolling alert-location list for map markers
**File:** `frontend/lib/store.tsx`

In the `fleet_event` reducer case, when `ev.type === "fleet.incident.created"`, append to a new state field `alertPins`:
```ts
alertPins: [...(st.alertPins || []).slice(-60), {
  id: ev.event_id || Math.random(), vehicle_id: ev.vehicle_id,
  lng: ev.snapshot?.lng ?? 0, lat: ev.snapshot?.lat ?? 0,
  cause: ev.root_cause, severity: ev.severity, ts: ev.ts,
}],
```
Add `alertPins?: any[]` to `State` and `alertPins: []` to `initial`. Also cap `fleetEvents` at 90 (already) and keep `fleetVehicles` as-is.

**Verify:** `npm run build` → exit 0 (type-level check only; runtime verified in Task 6).

### Task 3: Tive-style fleet table component
**File (new):** `frontend/components/live-map/FleetTable.tsx`

A dense table (Tive windowed-view pattern), columns per row:
`● status | ID | route (ORIG→DEST) | temp | speed | cargo | alerts badge | ETA | last ping`.

- Rows sorted: alerts desc → risk desc → ETA asc.
- Sensor chip goes **red** when `refrigeration.compressor_status !== "ONLINE"` or `temperature` out of band (`cargo.risk_level` HIGH/CRITICAL) — exactly Tive's "reading highlighted in red when it triggered an alert".
- Alert badge: `🔴 n` pill colored by max severity seen in that vehicle's events (`fleetEvents` filter).
- Status tab bar above the table: `ALL | IN TRANSIT | AT RISK | ARRIVED` — reuse existing filter chips but moved into the table header.
- Click row → `onSelect(vehicle_id)` (parent centers map + opens panel); hover row → subtle highlight.
- `last ping`: seconds since last `vehicle.position.updated` (compute from store update; show `--s`).

Component signature:
```tsx
export function FleetTable({ vehicles, events, filter, setFilter, onSelect, selected }: {
  vehicles: any[]; events: any[]; filter: string; setFilter: (f: string) => void;
  onSelect: (vid: string) => void; selected: string | null;
})
```
No new deps. Pure presentational; styling via existing `.tbl`, `.badge-*` classes.

**Verify:** `npm run build` → exit 0.

### Task 4: Split-path rendering (completed solid / upcoming dashed)
**File:** `frontend/app/live-map/page.tsx`

Compute from `routeData.geometry` (already fetched for selected vehicle) + `snap.trip.route_progress_percent`:
```ts
function splitRoute(geometry: [number, number][], progressPct: number) {
  const total = geometry.length - 1;
  const cut = Math.max(1, Math.min(total, Math.round(total * progressPct / 100)));
  return {
    done: geometry.slice(0, cut + 1),
    todo: geometry.slice(cut),
  };
}
```
Render two features into the existing `route` GeoJSON source:
- done → `{ color: "#34d399", dash: [1, 0] }` (solid green — completed path, Tive solid)
- todo → `{ color: "#38bdf8", dash: [2, 1.5] }` (dashed cyan — upcoming path)
Replace the current single-line draw. Update the `route` layer paint to honor per-feature `line-color` (already uses `["get","color"]` and `["get","dash"]`).

**Verify:** build → open page → select truck → map shows solid-green behind the truck, dashed-cyan ahead. (Manual + Task 6 WS check that geometry arrives.)

### Task 5: Alert pin markers with zoom clustering
**File:** `frontend/app/live-map/page.tsx` (+ helper in same file)

- New GeoJSON source `pins` fed from `st.alertPins` (Task 2). Two layers: `pins-core` (circle r=5 red/amber by severity) and `pins-ring` (r=11, opacity 0.25).
- Clustering without a dep: on each `moveend`, if `map.getZoom() < 9.5`, aggregate pins into a 0.05°-grid (round lat/lng), render count labels via a symbol layer (`+n`); at `>= 9.5` render individually. ~20 lines: group by `Math.round(lat/0.05) + ":" + Math.round(lng/0.05)`.
- Click pin/cluster → parent selects that vehicle (or first member) + `flyTo`.

**Verify:** run demo (inject failure), watch pins appear at excursion location; zoom out → cluster labels. Task 6 asserts presence via DOM layer count.

### Task 6: Windowed/fullscreen layout + timeline drawer + integration
**File:** `frontend/app/live-map/page.tsx` — restructure:

- New layout: `grid-cols-12` → table `col-span-4` (was 2-col incidents+filters), map `col-span-8` (was 7), right rail becomes an overlay drawer rather than a column (vehicle panel + AI card float over the map top-right, `absolute`, width 320).
- **Fullscreen toggle** button (Maximize2 icon) in top bar: sets `fullscreen` state → hides FleetTable column, map takes `col-span-12`, drawer stays. Persist in localStorage.
- **Timeline drawer** under map (Tive shipment timeline): horizontal scroll of the selected vehicle's `recent_events` (already in `/api/fleet/vehicle/{vid}`) + live `fleetEvents` filtered to that vehicle; each entry `HH:MM:SS — icon — text`; alert entries red-dot. Height 96px, collapsible.
- Filters/`layers` move into a small popover on the map (keep existing chips component, relocate into `MapControls` bar: pause, demo, fullscreen, layers).
- Legend updated: `━ completed  ┅ upcoming  ⚠ alert  🚚 vehicle  🟦 warehouse`.
- Top bar counters stay (vehicles / at risk / critical / sim clock / weather).

**Verify (WS + DOM, headless):**
```bash
curl -s http://127.0.0.1:8000/api/fleet/vehicle/TRUCK-101 | head -c 200
# expect recent_events array
npm run build   # exit 0
```
Then browser check: `/live-map` renders table with 12 rows, status tabs filter rows, toggling fullscreen hides table column, selecting a truck draws split path, timeline shows entries.

### Task 7: `/shipments-live` list page (Tive shipment list, deferred-value)
**File (new):** `frontend/app/shipments-live/page.tsx`

Full-width table (Tive windowed list): all 12 vehicles as "shipments" — columns `ID | cargo | origin→destination | status | load | temp | risk | alerts | ETA | progress bar`. Tabs `IN TRANSIT | ARRIVED | AT RISK`. Row click → `/live-map?focus=TRUCK-x` (live-map reads `?focus=` via useSearchParams inside Suspense → selects + flies). Reuses `FleetTable` with `variant="wide"` prop. Add nav entry to `components/Layout.tsx` (`label: "Fleet List"`).

**Verify:** build → visit page → rows equal live vehicle count; click navigates to live-map focused.

### Task 8: Cleanup + final commit
- Remove dead code from old layout (old left column, old event feed location — feed moves into timeline drawer header toggle `Events | Timeline`).
- `git add -A && git commit -m "feat(fleet-ui): Tive-style windowed tracking UI — fleet table w/ inline sensor alerts, split completed/upcoming paths, clustered alert pins, fullscreen mode, timeline drawer, /shipments-live list"`.

## Tests / validation

- **TDD where applicable** (pure-UI tasks are build+DOM-verified):
  - Task 1 (backend): before restarting, `curl /api/fleet/state` → KeyError-free; after: `alerts` field present on first vehicle (assert via the exact python one-liner above; expected `0`).
  - Task 4: unit-ish check — paste `splitRoute([[0,0],[1,0],[2,0],[3,0]], 50)` in a scratch `node -e` → `done` length 3, `todo` length 3, sharing point `[1,0]`... wait: total=3, cut=round(3*0.5)=2 → done=slice(0,3) len 3, todo=slice(2) len 2. Verify with: `node -e "…same fn…; console.log(splitRoute([[0,0],[1,0],[2,0],[3,0]],50).done.length)"` → `3`.
  - Tasks 3,5,6,7: `npm run build` exit 0 after each; then single browser pass asserting: 12 rows, tabs filter, split path colors (visual), pins after demo, fullscreen toggle, timeline entries.
  - Full regression: `pytest backend/tests -q` (twin + AI suites) stays green — no backend physics touched.
- Every task ends with a commit (see per-task messages).

## Risks, tradeoffs, and open questions

- **MapLibre symbol clustering**: doing it manually (grid) keeps deps zero; if 50+ vehicles later, swap to `supercluster` — one-line change in the source pipeline. Acceptable for 12–25.
- **Split-path accuracy**: progress % maps linearly onto polyline points; with OSRM's simplified geometry (every 2nd point) the cut point can be off by one segment. Fine for demo; refine later with cumulative-distance cut (note in code comment).
- **Tive trademark/branding**: we borrow layout *patterns*, not assets/copy — all visuals are our own SVG/CSS. No scraping of their app (pages are auth-walled anyway).
- **Live servers**: backend restart in Task 1 drops the in-memory fleet state (DB persists) — acceptable; the fleet respawns automatically on boot. The frontend `next start` needs restart after build — use the existing background-process pattern; watch for EADDRINUSE and kill stale PIDs via `netstat -ano | grep :3000`.
- **Open**: should the right-rail drawer stay visible in fullscreen? Plan: yes, but collapsible — matches Tive windowed↔fullscreen behavior where detail follows selection.
- **Deferred (YAGNI, explicitly)**: column reorder/drag (Tive has it; skip), collaborator/share features, alert-preset configuration UI, satellite toggle, geofence editor. The event-feed and timeline share data; no replay UI (recorded in plan for coldchain-platform v2).

## Execution order

Tasks 0→8 sequential; after each: `npm run build` (frontend tasks) or the stated curl/python check (backend task), then `git commit`. Final acceptance = browser pass on Task 6 list + all previous fleet regression tests still green.
