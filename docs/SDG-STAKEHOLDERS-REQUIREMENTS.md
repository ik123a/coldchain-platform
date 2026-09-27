# SDG Alignment, Stakeholders & Requirements

**Course:** CBCA301 Capstone Project · **Rubric items:** Milestone-1 →
*Problem Definition & SDG Alignment (5)*, *Stakeholder & Requirements Analysis (5)*

---

## 1. Problem statement

Cold-chain logistics — moving temperature-sensitive pharmaceutical and
perishable goods — loses product value silently. A pallet that warms from
2 °C to 8 °C in transit produces no alarm at the moment it happens; the loss
surfaces days later as rejected stock, and by then the cause is unrecoverable.
Existing cold-chain monitoring is built around **reactive alerts at the
destination**: the shipment already arrived damaged.

**This project builds the missing half — a live operational digital twin that
detects, explains, and acts on spoilage risk *while the vehicle is moving*.**

## 2. Motivation and significance

| Evidence | Consequence if unaddressed |
|---|---|
| Cold-chain excursions are a leading cause of vaccine and food loss in low-resource supply chains | Wasted stock, retreatment cost, and in the medical case, unusable doses |
| Freight temperature excursions are usually detected *after* delivery | No chance to intervene; the load is already lost |
| Manual log review cannot cover a live fleet at 4-second telemetry cadence | Excursions are found hours late, or not at all |

The engineering problem is therefore specific: **detect the excursion early
enough to act on it, and prove the action was correct.**

## 3. SDG mapping

### Primary — **SDG 3: Good Health and Well-Being**

Target 3.d: *Strengthen early-warning systems for health risk.* The product is
an early-warning system for a health risk. A live twin that surfaces a
compressor failure and a rising cargo temperature **before** the load arrives
is directly a 3.d implementation, not a metaphor. The pharma cargo class in
the simulation models exactly this case.

### Secondary — **SDG 2: Zero Hunger**

Target 2.1: *End hunger by ensuring access to sufficient, safe, nutritious food
for all.* Perishable cargo spoilage is a food-loss mechanism. The chilled and
frozen cargo classes model temperature-sensitive food in transit, where the
same detection logic prevents loss.

**Why two SDGs is honest rather than decorative:** they are not the same
claim restated. SDG 3 covers the *health* end (pharmaceutical spoilage =
unusable medical product); SDG 2 covers the *food systems* end. The shared
technical mechanism is temperature-excursion detection, and the project
demonstrates it on both cargo types.

### What it is NOT

Not climate action (SDG 13): the heatwave scenario *models* ambient weather,
but the product's output is a routing/cooling decision, not an emissions claim.
No carbon accounting is performed. Claiming 13 would be inflation.

## 4. Stakeholders

| Stakeholder | Need | How the product serves it |
|---|---|---|
| **Dispatcher / fleet operator** (primary user) | Know *now* which load is at risk, and what to do | Live map, telemetry rail, vehicle table, risk-sorted |
| **Logistics manager** | Utilisation, SLA adherence, incident throughput | Analytics, reports, incident priority queue |
| **Quality / compliance officer** | Documented excursion handling and audit trail | Incident records with cause, peak temperature, tick, resolution state |
| **Driver** | Instruction, not dashboards | Route change and cargo-transfer recommendations, not raw telemetry |
| **Pharma / food consignor** | Proof the cold chain held | Per-shipment temperature history and excursion evidence |
| **Auditor / academic evaluator** | Reproducible, inspectable evidence | Deterministic simulation, no LLM in the operational path, scripted tests |

**Primary stakeholder statement:** the dispatcher. Every design decision below
follows from that — which is why the product rejects several of the reference
site's motion effects (see §7).

## 5. Requirements

### 5.1 Functional

| ID | Requirement | Status |
|---|---|---|
| FR-01 | Simulate a live fleet with per-vehicle position, speed, heading, cargo state | Implemented |
| FR-02 | Detect temperature excursion against each cargo class's **own** safe band | Implemented (frozen ≈ −22…−15 °C, chilled distinct) |
| FR-03 | Classify risk and surface it without reading a number | Implemented (telemetry rail, colour + text equivalent) |
| FR-04 | Raise an incident on detection, with cause, peak temperature and tick | Implemented |
| FR-05 | Drive recovery: reroute, service, or cargo transfer | Implemented |
| FR-06 | Verify recovery and resolve the incident | Implemented — requires a `RecoveryVerifier` result, not a timeout |
| FR-07 | Explain the decision (copilot) | Implemented — **deterministic agents, explicitly not an LLM** |
| FR-08 | Model world events (heatwave, rain, fog) | Implemented |
| FR-09 | Replay an incident | Implemented |
| FR-10 | Reconstruct vehicle state in a digital twin | Implemented |

### 5.2 Non-functional

| ID | Requirement | Evidence |
|---|---|---|
| NFR-01 | Deterministic and reproducible | Rule-based Python; identical seed → identical output (TC-02) |
| NFR-02 | Honest system status | `ai_mode` must read `DETERMINISTIC-AGENTS`; the UI must never claim an LLM |
| NFR-03 | Keyboard/touch accessible | WCAG 2.5.8: 0/411 controls under 24px |
| NFR-04 | Motion-sensitive safe | `prefers-reduced-motion` honoured; 14 infinite animations → 0 |
| NFR-05 | Semantically navigable | 14/14 routes expose exactly one `<h1>` |
| NFR-06 | No credential material in source | Gate B2; 6 hardcoded keys removed |
| NFR-07 | Not silently mis-report state | Orphaned simulations reported separately from running ones |
| NFR-08 | Acceptable render cost | `/live-map` 3,441 → 2,604 DOM mutations/s |

### 5.3 Explicit non-requirements

Stated because a rubric scores scope discipline:

- **No LLM in the operational path.** Gemini/OpenAI keys are used only for
  design-reference asset generation, never for simulation or decisions.
- **No fleet-scheduling optimisation** beyond per-incident rerouting.
- **No multi-tenant / billing** (single organisation).
- **No hardware integration** — hardware is simulated, which the framework
  explicitly permits for IoT-type projects.
- **No production deployment** — this is a demonstrable prototype.

## 6. Technology selection and justification

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js 15 App Router, React 19, Tailwind 4 | Server components + streaming for a dense dashboard; the rubric requires a working web MVP with real API integration |
| Mapping | MapLibre GL | Vector map with a GeoJSON source that supports live `setData` updates — required for a moving fleet |
| Backend | FastAPI, SQLAlchemy, SQLite | Async, typed, and cheap to run for a demo; no external service dependency |
| Simulation | Pure Python, rule-based agents | **Determinism is a rubric requirement** ("reproducible results"). An LLM would forfeit it |
| Validation | Standalone `assert` scripts + Playwright DOM probes | Exit codes a CI/judge can gate on; measures the rendered product, not the source |

The simulation-engine choice is the load-bearing decision. Using an LLM for
agent decisions would look more impressive and score *worse*: it would make
results non-reproducible, which the Performance & Results criterion explicitly
penalises.

## 7. Design decisions traced to evidence

The UI was developed against measured audits, not taste:

- **Type scale** — original audit found the entire app rendering 10–12.5px with
  **zero** semantic headings. A 9-step scale replaced 308 arbitrary
  `text-[Npx]` utilities across 26 files; all 14 routes now expose one `<h1>`.
- **Telemetry rail** — a colour-coded spine derived from live fleet KPIs with a
  text equivalent for screen readers, so the status can never contradict a number.
- **Cargo-aware alerting** — an earlier build applied a single 8 °C threshold to
  every cargo class, which false-flagged frozen cargo sitting correctly at
  −18 °C. Fixed to evaluate each vehicle against its own band.
- **Awwwards reference study** — used for reference discovery and two motion
  findings. Its 2-second full-page white-out and 4-second scroll hand-off were
  **rejected**: they blank the viewport mid-shift, which is unacceptable for an
  operator watching for a temperature breach. This is recorded in
  `refs/coldchain2/MOTION-INVENTORY.md` with reasons.

## 8. Scope, limitations and exclusions

| # | Limitation | Effect | Mitigation / future work |
|---|---|---|---|
| L1 | Simulation only — no real telematics hardware | Cannot validate against a physical fleet | Hardware-in-the-loop adapter behind the existing telemetry interface |
| L2 | SQLite, single-node | Not concurrent beyond one demo instance | PostgreSQL migration path; the data layer is already abstracted |
| L3 | No authentication (see §9) | Not deployable to an untrusted network | **Open decision — deliberately not chosen unilaterally** |
| L4 | Weather modelled, not forecast | No predictive risk | Historical weather ingestion + forecast model |
| L5 | Risk model is rule-based, not learned | No detection of novel failure modes | Train on incident history once labelled data exists |
| L6 | Single organisation, no billing | Not a commercial product | Out of scope for capstone |
| L7 | `/live-map` still interpolates through the data layer | 2,604 mutations/s remains | Move interpolation to a map transform layer |

## 9. Open decisions (not unilaterally made)

1. **Auth posture.** No authentication architecture was selected, because
   choosing one silently would be a product/security decision belonging to the
   team and guide. The JWT signing key now *refuses to start* outside
   development without an explicit secret, so the current state fails safe
   rather than shipping a forgeable default.
2. **Credential rotation.** Two Google/Gemini keys were found hardcoded in
   tracked source and in git history. They are removed from source, but
   **rotation at the provider requires the account owner** and has not been
   done by me.
3. **Report and deck authorship.** Academic content must be the students' own
   work; the engineering evidence in `docs/TESTING.md` is provided as raw
   material, not as text to submit.

## 10. Success criteria

| Criterion | Measure | Current |
|---|---|---|
| Fleet simulated live | Vehicles with live telemetry | 14 |
| Excursions detected | Incident raised on breach | Verified live (compressor failure → 4.05 °C → 10.25 °C → incident) |
| Incidents resolved | Chain reaches `RESOLVED` | Verified; requires `RecoveryVerifier`, not a timer |
| UI correctness | Routes clean | 14/14 HTTP 200, 0 console errors |
| Reproducibility | Same seed → same output | Asserted in TC-02 |
| Honesty | No false AI claim | `ai_mode = DETERMINISTIC-AGENTS` |
| Security | No credentials in source | Gate B2; 0 literals |
