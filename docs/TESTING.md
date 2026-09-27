# ColdChain Rescue — Test Documentation

**Course:** CBCA301 Capstone Project · **Rubric item:** Milestone-2 → *Testing & Validation (5 marks)*

The rubric descriptor for the top band is *"Test case conducted with proper
documentation, cross validation method and verifiable evidence."* This document
exists to satisfy that descriptor, and every claim below is reproducible.

---

## 1. How to run everything

```powershell
# Backend test suites (5 standalone scripts, each exits 0 on success)
cd backend
foreach ($t in @("test_fleet_twin","test_fleet_ai","test_fleet_ops",
                 "test_world_events","test_scenario_analytics")) {
  ./.venv/Scripts/python.exe "tests/$t.py"
  if ($LASTEXITCODE -ne 0) { Write-Host "FAIL: $t" -ForegroundColor Red }
}

# Full acceptance gate: 6 goals + 3 boundaries, exit 0 = releasable
cd ..
python .loop/judge.py
```

**These are standalone `assert`-based scripts, not pytest modules.** `pytest`
reports "no tests ran" on them, which is a tooling mismatch, not a missing
suite. Run them directly as above.

---

## 2. Test cases

| ID | Suite | What it validates | Method |
|----|-------|-------------------|--------|
| TC-01 | `test_fleet_twin.py` | Digital-twin state derivation: each vehicle's twin reflects its sensor state (cargo temp, position, door, compressor) | Assert on derived state vs. injected sensor values |
| TC-02 | `test_fleet_ai.py` | Deterministic agent decisions: given identical inputs, the agent produces the identical decision (no LLM nondeterminism) | Repeat-run comparison + expected-decision assertions |
| TC-03 | `test_fleet_ops.py` | Fleet operations: service/repair actions, truck-to-truck cargo transfer, incident priority queue | Assert on resulting fleet + queue state |
| TC-04 | `test_world_events.py` | World-event injection: heatwave / rain / fog scenarios alter the environment as specified | Assert on environment state after injection |
| TC-05 | `test_scenario_analytics.py` | Scenario analytics: KPIs and incident analytics are computed consistently from run data | Assert on derived metrics |
| TC-06 | `acceptance_sweep.py` | End-to-end incident lifecycle: detection → incident creation → recovery → resolution | Full run; asserts the chain reaches `RESOLVED` |
| TC-07 | `.loop/judge.py` | Six acceptance goals + three anti-Goodhart boundaries | Exit code 0 required |

**Current status:** TC-01…TC-05 **PASS (5/5)**, verified after the most recent
backend change. TC-06 has one **known failing assertion** — see §4.

---

## 3. Cross-validation methods

The rubric asks for a *cross validation method*, not just tests. Four
independent methods are used, deliberately not sharing a failure mode:

### 3.1 Unit → integration cross-check
`test_fleet_ops.py` asserts a single operation's effect; `acceptance_sweep.py`
asserts the same operation's effect across a full simulated run. A regression
that breaks one but not the other is caught by the disagreement.

### 3.2 Determinism as a correctness oracle
Because the operational simulation is **rule-based Python with no LLM in the
loop**, the same seed and inputs must produce byte-identical output. TC-02
asserts this. This is a stronger guarantee than a statistical AI test: it is
exactly reproducible, which is what the *Performance & Results* criterion
("reproducible results") asks for.

### 3.3 Live-system reconciliation against the running app
Assertions are cross-checked against the deployed instance, not only in-process:

```powershell
curl http://127.0.0.1:8000/api/status
```
Verified on the running system: `system=OPERATIONAL`,
`ai_mode=DETERMINISTIC-AGENTS`, `database=CONNECTED`. The `ai_mode` check is a
**negative assertion** — the system must never report an LLM mode, and the
frontend header must never claim one. A test that only asserted "an AI mode
exists" would have passed while the UI lied.

### 3.4 Browser-level DOM and accessibility measurement
`bin/count_controls.py`, `bin/design_audit.py` and `.loop/judge.py` (G4/G5/G6)
measure the **rendered** DOM, not the source. This caught two defects that
source review could not: 91 of 407 controls under the 24px WCAG target, and a
`/live-map` doing 3,441 DOM mutations/second.

---

## 4. Known failure — recorded, not hidden

`acceptance_sweep.py` collects 283 events; the incident and geofence paths pass.
One assertion fails:

```
service.completed  →  contract mismatch (Milestone-2 sweep contract)
```

**Classification:** a §6C sweep-contract discrepancy, **not** evidence of a
broken incident pipeline. The incident chain independently reaches `RESOLVED`
when tested directly. It is left failing and visible rather than suppressed,
because a green suite that hides a real assertion is worse than a red one that
is honestly labelled.

---

## 5. Accessibility validation

| Requirement | Method | Result |
|---|---|---|
| WCAG 2.2 Target Size (Minimum) 2.5.8 | Playwright bounding-box probe over `button, a[href], input, select, textarea` on 12 routes | **0 of 411 controls** under 24px (was 91 / 22.4%) |
| `prefers-reduced-motion` | Emulate OS setting, read computed `animation-duration` | 14 infinite animations → **0**; duration → 1e-05s; elements stay rendered so state still reads |
| Semantic structure | DOM query per route | **14/14** routes: exactly one `<h1>`, 0 console errors |
| Colour-independence | Rail carries `data-state` + accessible text, not colour alone | Critical/warning states have text equivalents |

The judge gates G4/G5/G6 on all of the above, so a regression fails the build
rather than waiting to be noticed.

---

## 6. Acceptance gate (`.loop/judge.py`)

| ID | Goal | Result |
|----|------|--------|
| G1 | `tsc --noEmit` exits 0 | PASS |
| G2 | 5/5 backend suites independently exit 0 | PASS |
| G3 | Backend serves; `ai_mode` is exactly `DETERMINISTIC-AGENTS` | PASS |
| G4 | 14 routes: HTTP 200, one `<h1>`, 0 console errors | PASS |
| G5 | Computed-style probes match baseline; layout guards clean | PASS |
| G6 | No control under the 24px hit area | PASS |
| B1 | 7 protected files byte-identical to baseline (tests cannot be edited to pass) | PASS |
| B2 | No credential material in tracked files | PASS |
| B3 | No `.env` tracked | PASS |

**Boundary B1 is the anti-Goodhart control.** It was verified by deliberately
appending a line to `test_fleet_twin.py`: the judge returned
`PROTECTED FILE MODIFIED`, `RELEASABLE: False`, exit 1. A test suite that a
build agent can edit to make itself pass is not evidence.

---

## 7. Evidence index

| Artefact | Location |
|---|---|
| Test suites | `backend/tests/*.py` |
| Acceptance gate | `.loop/judge.py`, `.loop/loop.py` |
| Protected-file baseline | `.loop/baseline.json` |
| Visual baseline | `.loop/style-baseline.json` |
| Route/DOM audit | `bin/audit_all.py`, `bin/design_audit.py` |
| Accessibility probe | `bin/count_controls.py`, `bin/verify_reduced_motion.py` |
| Performance measurement | `bin/diagnose_fps.py` |
| Rubric self-audit | `bin/rubric_audit.py` |
| UI walkthrough video | `C:/Users/SKV/coldchain-video/coldchain-ui-tour.mp4` |
| Comparison screenshots | `C:/Users/SKV/ui-compare/` |

Every number in this document is produced by a script in that table. None is
asserted from memory.
