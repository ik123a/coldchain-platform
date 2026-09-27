# ColdChain Rescue

**CBCA301 Capstone Project — Bennett University, BCA Semester V**

A live operational **digital twin for cold-chain logistics**: it detects
temperature excursions *while a vehicle is moving*, explains the cause, and
drives a verified recovery — rather than reporting the loss after delivery.

---

## Quick start

Two terminals. Backend first.

```powershell
# 1. Backend  (port 8000)
cd backend
$env:APP_ENV="development"     # permits an auto-generated dev JWT secret
$env:CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000,http://localhost:3100,http://127.0.0.1:3100,http://localhost:8000"
./.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```powershell
# 2. Frontend (port 3000)
cd frontend
npm run dev
```

Then open <http://localhost:3000/live-map>.

> **Never run `npm run build` while `next dev` is serving** — it corrupts the
> shared `.next` directory. Use `npx tsc --noEmit` for type checks.
>
> If the dev server wedges (port open, page blank, `/_next/static/*` 404s):
> kill the process **first**, then delete `.next`, then restart.

## Verify everything

```powershell
python .loop/judge.py     # 6 goals + 3 boundaries; exit 0 = releasable
```

---

## What it does

| Capability | Route |
|---|---|
| Live fleet map with moving vehicles and trails | `/live-map` |
| Operations dashboard | `/dashboard` |
| Incident lifecycle: detection → recovery → verified resolution, with replay | `/incidents` |
| KPI and incident analytics | `/analytics` |
| Scenario control: heatwave / rain / fog, failure injection | `/simulation` |
| Per-vehicle digital twin reconstruction | `/twin` |
| Deterministic decision explanations | `/copilot` |
| Reports, shipments, settings | `/reports` `/shipments` `/settings` |

## Architecture in one paragraph

Next.js 15 + React 19 + Tailwind 4 frontend; FastAPI + SQLAlchemy + SQLite
backend; a **15-module deterministic Python simulation** driving six
rule-based operational agents. **There is no LLM in the operational path** —
Google/Gemini keys are used only to generate design-reference images. The UI
reports `ai_mode = DETERMINISTIC-AGENTS` and the header is gated on that exact
string, so the product cannot claim an AI it does not use. This is deliberate:
the rubric scores *reproducible results*, which an LLM decision layer would
forfeit. Full detail in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

### Diagrams

| Diagram | File |
|---|---|
| Use-case (UML) — 5 actors, 12 use cases, 54 endpoints mapped | [`docs/use-case-diagram.html`](docs/use-case-diagram.html) |
| Data flow — Level 0 context, Level 1 processes/stores, incident sequence | [`docs/data-flow-diagram.html`](docs/data-flow-diagram.html) |

Both are self-contained HTML with inline SVG — open them directly in any
browser, no server or dependencies required.

## Documentation

| Document | Rubric item it serves |
|---|---|
| [`docs/LOG-DIARY.md`](docs/LOG-DIARY.md) | Milestone-2 — Documentation & Project Management (progress evidence, action plan, future prospects) |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Milestone-2 — System/Technical Design |
| [`docs/TESTING.md`](docs/TESTING.md) | Milestone-2 — Testing & Validation |
| [`docs/PERFORMANCE-RESULTS.md`](docs/PERFORMANCE-RESULTS.md) | Milestone-2 — Performance & Results |
| [`docs/SDG-STAKEHOLDERS-REQUIREMENTS.md`](docs/SDG-STAKEHOLDERS-REQUIREMENTS.md) | Milestone-1 — SDG alignment, stakeholders, requirements |
| [`HANDOFF.md`](HANDOFF.md) | Project state and continuation notes |

## Quality gates

`.loop/judge.py` is a deterministic acceptance gate. It exists to stop an
automated agent (or a tired human) from declaring success without evidence.

| ID | Check |
|---|---|
| G1 | `tsc --noEmit` exits 0 |
| G2 | 5/5 backend suites independently exit 0 |
| G3 | Backend serves; `ai_mode` is exactly `DETERMINISTIC-AGENTS` |
| G4 | 14 routes: HTTP 200, exactly one `<h1>`, 0 console errors |
| G5 | Computed-style probes match a human-written baseline; layout guards clean |
| G6 | No control renders under the 24px WCAG 2.5.8 hit area |
| B1 | 8 protected files byte-identical to baseline — **tests cannot be edited to make the gate pass** |
| B2 | No credential material in any tracked file |
| B3 | No `.env` tracked by git |

B1 is the anti-Goodhart control, and it was verified by deliberately corrupting
a test file: the judge reported `PROTECTED FILE MODIFIED`, `RELEASABLE: False`,
exit 1.

## Known limitations

Recorded rather than hidden — see `docs/ARCHITECTURE.md` §8 and
`docs/SDG-STAKEHOLDERS-REQUIREMENTS.md` §8.

- Simulation only — no real telematics hardware
- SQLite, single-node
- **No authentication.** Not chosen unilaterally: it is a product/security
  decision for the team and guide. The JWT layer now *refuses to start*
  outside development without an explicit secret, so the current state fails
  safe rather than shipping a forgeable default.
- `/live-map` still interpolates through the data layer (2,604 mutations/s)
- Two Gemini keys were found hardcoded in tracked source and in git history.
  They are **removed from source**; **rotation at the provider is still
  outstanding** and requires the account owner.
