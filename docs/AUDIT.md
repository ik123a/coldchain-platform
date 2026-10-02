# ColdChain Rescue — Full Context Audit

**Purpose:** hand this to another agent (OpenCode or similar) to independently
verify every claim, find mistakes, and finish the remaining work.

**Audit date:** 2026-10-02
**Auditor note:** every "VERIFIED" below was checked by running code, not by
reading it. Claims I could not verify are marked **UNVERIFIED** and must be
treated as open questions, not facts.

---

## 1. Repository state

| Fact | Value | How to confirm |
|---|---|---|
| Path | `D:\projects\capstone project\coldchain-platform` | — |
| Branch | `chore/token-adoption-codemod` | `git branch --show-current` |
| HEAD | `5211681` | `git rev-parse --short HEAD` |
| `origin/main` | `16c3b34` | `git rev-parse --short origin/main` |
| Commits ahead of main | **14** | `git rev-list --count origin/main..HEAD` |
| Remote | `ik123a/coldchain-platform` (GitHub) | `git remote -v` |
| Visibility | **PRIVATE** — must stay private | `gh repo view ik123a/coldchain-platform --json visibility` |
| Open PR | **#1** → `main`, MERGEABLE | `gh pr view 1` |
| CI | **none configured** | `gh pr checks 1` |

### Uncommitted work (NOT yet pushed)

```
 M backend/app/simulation/fleet_agents.py     ← cost model (requirement 16)
 M frontend/components/simulation/ApprovalQueue.tsx  ← shows cost
?? docs/demo/video/                           ← recording artifacts, no .mp4 committed
```

**The cost model is implemented and tested but uncommitted.** Do not assume it
is in PR #1 — it is not.

### The 14 commits, in order

```
d9d2c4e  fix(sim): pharma risk multiplier was inert; warehouse capacity leaked
ce64345  feat(fleet): operator-defined trucks with explicit product and destination
552fdcb  feat(ui): dispatch builder on /simulation for user-defined trucks
c10537a  feat(agentic): human-in-the-loop approval gate for rescue recommendations
26514a2  feat(ui): replace toast popups with a persistent activity centre
6e6343e  feat(incidents): catalogue-driven classification, 2 types -> 13
7f68a6d  feat(rca): multi-cause diagnosis on the fleet path
d752b4f  feat(prediction): predictive safe-remaining-time warnings
8d5aeef  feat(scenarios): deterministic scenario suite A-F + fix inverted reporter score
2fe39d7  feat(escalation,lessons): agent self-flags unanswered criticals + derived lessons
f99d721  feat(ui): surface predictive warnings and derived lessons in the UI
5527928  fix(ui): mark escalated approvals, show candidate scores, drop false kinetics claims
73475a0  fix(telemetry): attach prediction to the WebSocket frame, not just state()
5211681  fix(reports): negative recovery time on unresolved incidents
```

---

## 2. How to run it

```bash
# BACKEND — port 8000
cd "D:/projects/capstone project/coldchain-platform/backend"
APP_ENV=development FLEET_AUTOSTART=1 ESCALATE_AFTER_SIM_MIN=6 PYTHONPATH=. \
  .venv/Scripts/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# FRONTEND — port 3000 (separate shell)
cd "D:/projects/capstone project/coldchain-platform/frontend"
API_ORIGIN="http://10.12.32.140:8000" \
  node_modules/.bin/next start -p 3000 --hostname 0.0.0.0
```

**LAN URL: `http://10.12.32.140:3000`** (backend `http://10.12.32.140:8000`)

Environment: Windows 11, bash via Git-Bash/MSYS. Pass **native forward-slash**
paths (`D:/...`) to native binaries — MSYS path conversion is disabled.

### Test commands

```bash
cd backend
for t in test_fleet_ops test_fleet_ai test_world_events test_fleet_twin \
         test_scenario_analytics test_scenarios_suite test_escalation test_lessons; do
  printf "%-24s " $t
  APP_ENV=development PYTHONPATH=. .venv/Scripts/python tests/$t.py 2>&1 | tail -2
done
```

All 8 suites pass as of this audit. `cd frontend && node_modules/.bin/next build`
compiles clean, 15 routes prerendered.

**Trap:** a test file passes when its output contains `ALL PASS`, `passed`, or a
bare `OK`. Do NOT grep for `^(OK|PASS)` alone — several suites print `FLEET OPS:
ALL PASS` and a stricter pattern reports false failures.

---

## 3. The 17 requirements — verified status

VERIFIED = I ran it and saw it. UNVERIFIED = plausible but not confirmed.

| # | Requirement (from the brief) | Status | Evidence |
|---|---|---|---|
| 1 | 2–3 trucks; product and destination defined by the user | **VERIFIED** | `/simulation` renders "Plan a delivery — 2 to 3 trucks", Truck 01/02, "You choose the product and the destination. Nothing is assigned automatically" |
| 2 | Must not be automatic | **VERIFIED** | Approval gate renders Approve/Reject; `require_approval` defaults True |
| 3 | Popup notifications removed | **VERIFIED** | `frontend/components/Toasts.tsx` deleted; `NotificationCentre.tsx` replaces it |
| 4 | All possible incident types shown | **VERIFIED** | `GET /api/fleet/incidents/catalogue` → 13 detectable + 4 declared gaps |
| 5 | Incident → possible causes | **VERIFIED** | 4–5 ranked causes per incident, each with reasoning |
| 6 | Possible solutions with scores | **VERIFIED** | 4 ranked candidates with scores, e.g. 83 / 61 / 13 / 11 |
| 7 | User chooses, then approves | **VERIFIED** | Approve/Reject in `ApprovalQueue.tsx`; page errors 0 |
| 8 | Report: truck, problem, how AI resolved it, **what it learned if it failed** | **VERIFIED** | Report text contains 4 derived `Lesson:` lines |
| 9 | Predictive warning as temperature rises | **VERIFIED** | 1.5 sim-min after a compressor fault, **0 incidents raised**, prediction already `WILL SPOIL BEFORE ARRIVAL` |
| 10 | "Keep it minimal" | **NOT DONE** | ~15 sidebar sections remain. Never addressed. See §6. |
| 11 | Full telemetry before incident is raised | **VERIFIED** | Snapshot attached to each vehicle every tick, before `_check_incident` |
| 12 | Multi-cause RCA (compressor, weather, age, etc.) | **VERIFIED** | `compressor_failure`, `door_open`, `heatwave`, `sensor_fault` ranked with likelihoods |
| 13 | Report shows truck detail, problem detail, resolution | **VERIFIED** | `/reports` renders; payload keys `incident`, `diagnosis`, `risk`, `actions`, `readings_window` |
| 14 | AI flags criticals itself if no reply comes | **VERIFIED** | 26 pending / 26 escalated live; badge shows "ESCALATED BY AGENT — no operator response… at sim-min 787.93" |
| 15 | Nearest cold storage + time + **cost** → best option | **PARTIAL — cost just added, uncommitted** | Time/traffic/capacity were scored; cost model added this session, tested, **not committed** |
| 16 | Possible causes for *why* temperature rose | **VERIFIED** | Same as #12 — the DiagnosisAgent path |
| 17 | Human approval required, not automatic | **VERIFIED** | Same gate as #2 |

### The two design rules held throughout

**No invented telemetry.** Every detector reads only signals already in the
vehicle twin or traffic world. Four types from the brief are declared as
explicit gaps with reasons rather than faked:
- `product_spoilage_confirmed` — cargo_health is a heuristic, not measured spoilage
- `refrigerant_pressure_low` — no pressure sensor exists
- `door_seal_degradation` — binary door_open only, no gradual decay
- `equipment_age_maintenance` — no maintenance history model

**No false kinetics claims.** "Arrhenius" appears in the original brief, but no
kinetics model exists anywhere in the backend — the word only ever appeared in
Gemini *image-generation prompts* describing a dashboard picture. The prediction
payload therefore reports:
```
model: "linear_trend_projection"
kinetics_modelled: false
```
All UI copy claiming Arrhenius was replaced (commit `5527928`). **If you find
any remaining "Arrhenius" or "shelf-life" claim in `frontend/`, it is a bug.**

---

## 4. Architecture in one page

```
Next.js 15 (App Router, TypeScript)  :3000
  ├── 15 routes: dashboard, live-map, simulation, incidents, reports,
  │              analytics, twin, shipments, warehouses, settings, ...
  ├── lib/store.tsx        WebSocket-first, 4s poll fallback
  ├── lib/theme.ts         dark | light | system, key "cc.theme"
  └── components/
      ├── live-map/PredictiveSafeTime.tsx   P7 panel (new)
      ├── live-map/FleetRiskBanner.tsx      worst-load banner (new)
      ├── live-map/DeepTelemetryDrawer.tsx  8 tabs, band-aware
      ├── NotificationCentre.tsx            replaces Toasts.tsx
      └── simulation/ApprovalQueue.tsx      escalation badge + cost

FastAPI + SQLite :8000
  ├── simulation/fleet_orchestrator.py   tick loop, incidents, approvals, WS
  ├── simulation/incidents_catalogue.py  13 detectors (new)
  ├── simulation/prediction.py           safe-remaining-time (new)
  ├── simulation/lessons.py              derived lessons (new)
  ├── simulation/scenarios.py            suite A–F (new)
  ├── simulation/agents_d.py             DiagnosisAgent, ReporterAgent (shared)
  ├── simulation/fleet_agents.py         FacilityMatcher, RouteScorer + COST (new)
  └── api/routes/fleet.py                ~10 new endpoints
```

**Key architectural decision:** `agents_d.DiagnosisAgent` was already written and
scored 6 hypotheses — fleet incidents simply never called it. P6 wired it in via
an adapter (`incidents_catalogue.diagnose`) rather than writing a second
diagnosis engine, so the classic and fleet paths cannot drift apart.

---

## 5. Endpoints added (all under `/api/fleet/`)

| Endpoint | Purpose |
|---|---|
| `GET /incidents/catalogue` | 13 detectable types + 4 declared gaps |
| `GET /incidents/{iid}/diagnosis` | ranked causes, evidence, reasoning |
| `GET /predictions` | all vehicles worst-first |
| `GET /scenarios` | runs suite A–F (**takes ~37 s**, timeout accordingly) |
| `GET /approvals` | pending + `escalated_count` + config |
| `GET /approvals/mode` | toggle the gate (declared before `{key:path}` deliberately) |

**Confirmed live:** catalogue 13 · predictions 14 trucks · approvals 26 pending /
26 escalated · escalate_after 6.0 · auto_approve 0.0

---

## 6. KNOWN GAPS — do these not to forget

### 6.1 Requirement 10 "keep it minimal" — NOT DONE

The brief said *"jada usmey kuch nahi hona chahiye"* (there should not be much
in it). The sidebar still exposes ~15 sections. **No simplification work has
been done.** This is the largest unaddressed instruction.

### 6.2 Cost model — uncommitted

`fleet_agents.py` now has `handling_cost_inr()` and `WEIGHTS["cost"] = 0.10`
(carved out of eta 0.40→0.32 and cargo 0.20→0.18 so weights still sum to 1.0).
Verified locally:

```
Delhi Central Cold Storage   score=62.0  eta=18.1m  cost=Rs 160
Airport Cold Storage         score=33.8  eta=32.5m  cost=Rs 254
Retail Distribution Hub      score=32.7  eta=29.9m  cost=Rs 257
Gurugram Distribution Hub    score=-0.9  eta=48.6m  cost=Rs 255
```

Cost differentiates candidates and appears in the reason text. **Not yet
committed or shown in the UI build that is running.**

### 6.3 Demo video — NOT PRODUCED

There is **no `.mp4`**. `docs/demo/video/` holds a raw `.webm` and a manifest.
The recorder (`docs/demo/record_demo_v2.py`) last scored **7/8 beats**; the one
miss was a 30 s harness timeout against a 37 s endpoint, since fixed but not
re-run. **Do not present any existing video as final.**

### 6.4 Deployment — still blocked

- `/api/fleet/*` operational mutation endpoints: `require_auth` is imported and
  referenced 32× in `fleet.py`, but **verify enforcement yourself** — the
  audit did not prove every mutating route is gated.
- SQLite default: ephemeral on serverless hosts.
- WebSockets require a persistent WS-capable host.
- `next@15.3.2` — **flagged for `CVE-2025-66478`**. Upgrade before any public use.
- Production refuses to start without an explicit `JWT_SECRET`.

**Keep the repo private. LAN demo only.**

---

## 7. Bugs already found and fixed

Ten defects, all of which produced a *plausible but wrong answer* rather than a
crash — the more dangerous class. Six were found by running code, not reading it.

| # | Bug | How it manifested |
|---|---|---|
| 1 | `sensor_fault` undetectable | engine froze the reading but never exposed the flag |
| 2 | Read `compressor_on` | key does not exist in the snapshot → `KeyError` |
| 3 | Module referenced itself as `IC` | `NameError` on first diagnose call |
| 4 | `json.loads` without `import json` | app started clean; endpoint would 500 on first use (OpenAPI does not validate function bodies) |
| 5 | `cooling_efficiency` stuck at 100% | evidence read `compressor=FAILED, cooling_efficiency=100%` |
| 6 | `cargo.mn`/`mx` missing from snapshot | predictions fell back to a hardcoded 2–8°C produce band; a healthy −18°C freezer was flagged `ALREADY BELOW SAFE FLOOR` |
| 7 | `trend_c_per_min` read from wrong dict | `None` → read as "not warming" → every truck projected `STABLE` |
| 8 | Load past its ceiling reported `STABLE` | warming flattens as the box approaches ambient, so `ttc` went `None` |
| 9 | Reporter penalised **faster** planning | 0 ticks scored 77, 12 ticks scored 89 |
| 10 | Negative recovery time | unresolved incident read `Recovery time: -1672 ticks` and scored 92/100 as if recovery were instant |

Two more found during UI work:

- **WebSocket race** — `state()` attached `prediction` but the per-tick
  `vehicle.position.updated` frame did not. Both write the same store key, so
  ~2 ticks/sec stripped the prediction off. `GET /api/fleet/state` returned it
  correctly, so every API check passed while the drawer showed nothing.
- **Crash on "View Telemetry"** — `prediction is not defined` blanked the app. A
  passing build did not catch it; only clicking did.

---

## 8. Testing guidance — read before trusting a green run

This project has several verification traps that produced **false confidence**:

1. **`or True` in a verifier.** The demo recorder's beat checks ended in
   `or True`, so two beats reported success while showing the wrong page. Any
   verification that cannot fail is not a verification.

2. **`inner_text` vs DOM.** Several checks reported "not rendering" when the
   element was present. Use `page.evaluate("() => document.body.innerHTML")`.

3. **Screenshot compression misleads.** Vision analysis reported the prediction
   stats as "washed out". Measured contrast was **15.89:1** — passes WCAG AA.
   Measure, do not eyeball screenshots.

4. **The fleet self-repairs within ~30 sim-seconds.** A single fault injection
   followed by a fixed sleep is a coin flip. Poll for the state you need.

5. **Wrong interpreter creates a phantom database.** Running the backend code
   with system Python instead of `.venv/Scripts/python` produced
   `no such table: incidents` because it opened a *different, empty* DB.

6. **Sync vs async.** `store.tsx` maps `vehicle.position.updated` to the same
   `fleet` action as the REST poll. Anything added to only one path will be
   silently overwritten by the other. **Check both.**

---

## 9. Concrete task list for the next agent

**Priority order:**

1. **Commit the cost model** — `fleet_agents.py` + `ApprovalQueue.tsx` are
   uncommitted. Run the 8 suites, then commit.
2. **Requirement 10: simplify the UI.** Unaddressed since the brief. Propose
   what to cut, get agreement, then do it.
3. **Upgrade `next@15.3.2`** — CVE-2025-66478. Confirm the upgrade builds and
   all 15 routes still prerender.
4. **Prove `/api/fleet/*` auth enforcement.** Grep is not proof. Write a test
   that calls each mutating endpoint with no token and expects 401/403.
5. **Re-record the video.** Target 8/8 beats, then transcode and verify frames.
6. **Push** the branch, update PR #1.

**Do not:**

- Add Arrhenius/kinetics code without implementing and validating real kinetics.
- Add a detector that reads a sensor the twin does not have.
- Mark the repo public or deploy publicly.
- Edit the six SHA-pinned test files in `.loop/baseline.json` — add new
  filenames instead (this is gate B1 by design).
- Claim something works without running it.

---

## 10. Honest self-assessment

**Strong:** the physics is coherent and band-aware per cargo type; the incident
catalogue and prediction modules are honest about their limits; every design
decision is documented in-code with the reasoning and the bug it prevents.

**Weak, and worth knowing before you trust it:**

- I twice reported something as verified on the basis of a *passing build* when
  the failure only appeared on interaction.
- I once reported a beat as verified when its check could not fail.
- The contrast claim was wrong and I corrected it after measuring.
- `docs/demo/` contains a manifest claiming beats passed that were not all
  genuinely shown.
- Requirement 10 is untouched, and the video does not exist.

The code is in better shape than the video and the UI tidiness. Judge the
simulation logic generously and the presentation harshly.
