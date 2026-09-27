# Project Log Diary

**Course:** CBCA301 Capstone Project · **Rubric item:** Milestone-2 →
*Documentation & Project Management (5 marks)* — *"Good Progress evidence, well
defined limitations and remaining work. Well maintained Log Diary with up to
date action plan; future prospects, funding or startup planning."*

**How to read this.** Entries are in reverse chronological order. Each records
what was done, **how it was verified**, and what remains. Entries marked
*Corrected* record a claim that was later found to be wrong — they are kept
because a diary that hides its own mistakes is not evidence of rigour.

**Machine-generated evidence for every entry:** `git log --oneline` (34 commits
on `main`), and the acceptance gate `python .loop/judge.py` (6 goals + 3
boundaries, exit 0 = releasable).

---

## Progress summary

| Milestone | Deadline | Status | Evidence |
|---|---|---|---|
| Milestone-0 Problem & group | 04 Sep 2026 | Submitted | `docs/SDG-STAKEHOLDERS-REQUIREMENTS.md` |
| Milestone-1 Proposal, requirements, feasibility | 18 Oct 2026 | **Submitted** | 4 documents, rubric-mapped |
| Milestone-2 Design, MVP, validation | 09 Nov 2026 | **Ready for submission** | Prototype running, 14/14 routes clean, 5/5 suites pass |
| Final report + presentation | 23 Nov 2026 | **Not started — requires the group** | Raw material provided in `docs/` |

---

## 2026-09-28 — Documentation & diagrams for Milestone-2

**Done**
- Extracted the actual requirements from `university-docs/` (Framework +
  Rubrics `.docx`) — this had never been read, and it changed what "done" means
- Wrote the four rubric-scored documents: `ARCHITECTURE.md`, `TESTING.md`,
  `PERFORMANCE-RESULTS.md`, `SDG-STAKEHOLDERS-REQUIREMENTS.md`
- Built two diagrams as self-contained HTML+SVG: UML use case (5 actors,
  12 use cases, all 54 endpoints mapped) and DFD (L0 context, L1 processes +
  stores, incident sequence)
- Added `README.md` with quick start, capability map, gates, limitations

**Verified**
- Judge: 6/6 goals, 3/3 boundaries, exit 0
- `tsc --noEmit` exit 0; 5/5 backend suites pass
- All 14 routes: HTTP 200, exactly one `<h1>`, 0 console errors
- Diagram layout checked geometrically: 23 boxes, **0 overlaps**, 0 text
  escaping canvas; DFD tab switching verified in a real browser

**Corrected**
- Documentation first draft claimed **28 modules / 12 API routes / 10 tables**.
  Actual: **26 / 11 / 15**. A fact-check pass failed 3 of 8 claims and the
  document was corrected *before* commit. A false claim in an academic document
  costs marks and credibility.
- A layout-verification probe reported "all clear" after finding only **4 of 23**
  boxes — a `:scope >` CSS selector miss. The verdict was meaningless until the
  probe was fixed.

**Remaining**
- Mini-report prose (20–30 pages) and the 10–15 min slide deck — **group work,
  not agent work.** Engineering evidence is in `docs/` as raw material.

---

## 2026-09-28 — Security: live keys removed from source

**Done**
- Found **six live Google/Gemini keys hardcoded in tracked Python**: two in
  `app/core/config.py` as `os.getenv()` fallbacks, two each in
  `services/gemini/{critique,image_generation,video_generation}.py`
- Because they sat in the *fallback* position, deleting `.env` would **not**
  have removed the exposure — the service would have kept using the embedded key
- JWT signing key defaulted to the public string `***REDACTED-JWT-PLACEHOLDER***`,
  making every token forgeable. Now: explicit value used as-is;
  `APP_ENV=development` gets a random per-process secret; anything else
  **refuses to start**
- Removed the same class of bug from `.loop/judge.py` itself: `check_styles` hit
  an `ImportError` and **silently passed**. A gate that skips itself is worse
  than no gate; it now fails loudly

**Verified**
- Zero key-shaped literals in any tracked file (Google/Gemini, `sk-`, `ghp_`,
  `AKIA`, `xox` all clean)
- JWT: non-dev + unset → REFUSED · `APP_ENV=development` → random 47-char
  secret · real secret → used
- Keys still load from `.env`; backend serves `OPERATIONAL` / `CONNECTED`
- 5/5 backend suites pass

**Corrected**
- An earlier entry in this diary claimed the Gemini keys were *"already
  rotated."* **That was wrong.** The `.env` primary had changed, but the BACKUP
  key was the unchanged history-exposed value, **and** both were additionally
  embedded in source. The claim came from a handoff note, not from a check.

**Remaining — ACTION REQUIRED BY THE GROUP**
- **Rotate both Gemini keys at the provider.** They were in tracked source and
  in git history. Removal from source is done; rotation is not, and only the
  account owner can perform it.
- Optional: `git filter-repo` to purge the values from history (rewrites SHAs).
  The remote is **private**, which limits exposure.

---

## 2026-09-28 — Performance: 3,441 → 2,604 DOM mutations/sec

**Done**
- `/live-map` was mutating the DOM **3,441×/sec** — 80× `/incidents`, 10×
  `/dashboard`
- Root cause: the rAF loop called `setData()` on **both** GeoJSON sources every
  frame (~1,700 dataset rebuilds/sec to move 14 dots), ran unconditionally
  including the ~99% of frames where nothing interpolated, and re-sent a trail
  source that only changes every ~4 s
- Fix: loop parks when interpolation completes, a `startRef` wakes it on data
  arrival, only the vehicle source is touched during interpolation, trail is
  pushed once per arrival

**Verified** — 3,441 → 2,604/s (−24%). Post-change render intact: 12 markers,
25 clickable map elements, 1 canvas, 60 KPI tiles, 12 table rows, rail
`nominal` at `rgb(16,185,129)`, 0 console errors.

**Investigated and rejected**
- `backdrop-filter` was the first suspect (13 blurred surfaces). Measured:
  83 ms with blur vs 100 ms without — **worse** without. Blur was not the
  bottleneck and was left alone.
- The "12 fps" figure is itself a headless-rAF-throttling artifact, which is
  why MutationObserver count is the signal used instead.

**Remaining**
- The residual 2,604/s is inherent to interpolating through the data layer.
  Eliminating it needs a MapLibre custom layer — a larger change, recorded as
  architectural debt rather than taken unprompted.

---

## 2026-09-28 — Accessibility: WCAG 2.5.8 and reduced motion

**Done**
- **91 of 407 real controls (22.4%) rendered under 24 px** — a WCAG 2.2
  Target Size violation. Fixed at the token layer; re-measured **0 of 411**
- `prefers-reduced-motion` was **absent entirely** from the codebase while 156
  infinite animations ran. Added a global kill switch

**Verified**
- 0/411 undersized across 12 routes; live-map 12→0, incidents 34→2, copilot 10→2
- Reduced motion emulated at the OS level: 14 infinite animations on
  `/live-map` → **0**, durations → 1e-05s, elements stay rendered so state
  still reads
- Both now gated (G6, plus a design-review checklist item for the media query,
  which a desktop computed-style probe cannot detect)

**Note on measurement error**
- My first audit reported "147 undersized targets", then 1,799, then 219, before
  filtering to real `button`/`a[href]`/`input` controls. Most were text spans
  inheriting `cursor:pointer` inside clickable rows. The real figure was 91.

---

## 2026-09-28 — Loop engineering: acceptance gate

**Done**
- Built `.loop/judge.py`: 6 machine-decidable goals + 3 boundaries
- B1 pins 8 protected files to a human-written baseline, so a test **cannot be
  edited to make the gate pass** — the anti-Goodhart control
- G5/G6 added later after a real gap was found

**Verified — the boundary actually bites**
- Appending a line to `test_fleet_twin.py` → `PROTECTED FILE MODIFIED`,
  `RELEASABLE: False`, exit 1
- Injecting a 99 px CSS outline → `element outline 99px (limit 20.0)`,
  `RELEASABLE: False`, exit 1
- The judge's own first run found two bugs in itself, both fixed

**Corrected**
- The route list contained two routes that **do not exist** (`/world-events`,
  `/fleet`) — invented by me. The real ones are `/design-references` and
  `/design-reference-board`, which had never been audited until that fix.

**Left deliberately unimplemented**
- Cron scheduling (stage 3 of the method). The loop is a worker, not the
  acceptance officer; judgment stays with the group.

---

## Earlier entries (2026-09-27)

| Area | Change | Verification |
|---|---|---|
| Fleet alerts | `alerts_delta()` differenced a **sum** of cumulative counters → healthy fleet reported 154–224 alerts. Fixed to per-counter baselines | 14 healthy vehicles → 0; live failure still raises exactly 1 incident |
| Telemetry rail | Cargo-specific bands; a single 8 °C threshold had been false-flagging frozen cargo sitting correctly at −18 °C | All 14 vehicles `nominal` |
| AI honesty | `AI_MODE` reported `LLM` merely because a design-generation key existed. Now `DETERMINISTIC-AGENTS`, and the header is gated on that exact string | Verified in the live header |
| Simulation status | 9 seed rows reported `RUNNING` with no runner behind them. `RUNNERS` registry is now authoritative; orphans reported separately | 0 running, 2 orphaned |
| WebSocket | Cleanup cleared the timer before closing, so `onclose` scheduled an orphan reconnect | 6 mount/unmount cycles → exactly 6 accepts, 0 orphans |
| UI | 308 arbitrary `text-[Npx]` → 9-step scale; semantic `<h1>` on all 14 routes | 561 scale uses, 0 arbitrary sizes |

---

## Action plan

### Immediate (group, this week)

| # | Action | Why | Owner |
|---|---|---|---|
| 1 | **Rotate both Gemini keys** | In tracked source + git history | Account owner |
| 2 | Decide **auth posture** | Not deployable to an untrusted network; JWT now fails safe rather than shipping a forgeable default | Group + guide |
| 3 | Write the **mini-report** (20–30 pp) | Final panel requirement; `docs/` has the evidence | Group |
| 4 | Build the **slide deck** (10–15 min) | Final panel requirement | Group |

### Next sprint (if time permits)

| # | Action | Expected effect |
|---|---|---|
| 5 | Move map interpolation to a MapLibre custom layer | Removes the residual 2,604 mutations/s |
| 6 | Run gitleaks/trufflehog over full history | Shape-based scan; catches keys this work could not |
| 7 | Add a `tests/README.md` or fold `docs/TESTING.md` into it | Rubric-visible test documentation |
| 8 | Hardware-in-the-loop adapter behind the telemetry interface | Addresses limitation L1 |

### Explicitly out of scope

Fleet-scheduling optimisation, multi-tenancy/billing, real hardware, production
deployment. Stated because the rubric scores scope discipline.

---

## Limitations and remaining work

Seven limitations are enumerated with their effect and mitigation in
`docs/SDG-STAKEHOLDERS-REQUIREMENTS.md` §8; architectural debt with its impact
and plan is in `docs/ARCHITECTURE.md` §8. The headline items:

- Simulation only — no real telematics hardware
- SQLite, single-node
- **No authentication** — an open decision, deliberately not chosen unilaterally
- `/live-map` still interpolates through the data layer
- **Gemini keys still valid at the provider** despite removal from source

---

## Future prospects

| Horizon | Direction | Rationale |
|---|---|---|
| Near | Hardware-in-the-loop adapter | The telemetry interface is already abstracted; this is the main barrier to field use |
| Near | PostgreSQL | Data layer is already abstracted behind SQLAlchemy |
| Medium | Predictive risk from incident history | Current risk is rule-based; labelled incident data now exists |
| Medium | Multi-modal (rail/air) cold chain | The excursion-detection logic is cargo-agnostic |
| Long | Carbon accounting per route | Would legitimately support an SDG 13 claim, which this project does **not** make |

**Funding / startup planning.** A defensible commercial framing is a
cold-chain compliance SaaS for mid-size 3PLs, sold on *evidence*: excursion
handling is currently documented after the fact, and insurers/consignors pay
for the audit trail. The defensible moat is the incident history dataset, not
the dashboard. No funding research has been done — that is a group task and is
recorded here as **remaining work** rather than presented as complete.
