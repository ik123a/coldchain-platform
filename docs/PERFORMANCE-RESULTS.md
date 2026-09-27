# Performance & Validation Results

**Course:** CBCA301 Capstone Project · **Rubric item:** Milestone-2 →
*Performance and Results (5 marks)*

Descriptor for the top band: *"Flawless performance, reproducible results,
verifiable references, quantitative and qualitative results **and
interpretation**."* Every number below is produced by a committed script, and
each section states what the number means — not just what it is.

---

## 1. Method

Measurements use a `MutationObserver` on the rendered DOM rather than
synthetic frame timing. **Reason:** headless Chromium throttles
`requestAnimationFrame`, which produced a misleading 12 fps reading that did
not respond to any change under test. DOM mutation rate is a direct measure of
reactive work and responds correctly to real changes.

```powershell
python C:/Users/SKV/bin/diagnose_fps.py   # mutation rate, headed Chromium
python C:/Users/SKV/bin/count_controls.py # accessibility, 12 routes
python .loop/judge.py                     # 6 goals + 3 boundaries
```

Test machine: Windows 11, headless and headed Chromium via Playwright,
1600×1000 viewport.

## 2. Render cost — the dominant defect found

| Route | DOM mutations/sec (before) | Nodes | Animating |
|---|---|---|---|
| **`/live-map`** | **3,441** | 733 | 16 |
| `/dashboard` | 321 | 610 | 28 |
| `/incidents` | 43 | 596 | 10 |

`/live-map` was mutating **80× more than `/incidents`** and 10× `/dashboard`.

**Root cause.** The rAF interpolation loop called `setData()` on *both* the
vehicle and trail GeoJSON sources every frame. `setData()` rebuilds and
re-tessellates an entire `FeatureCollection`, so at 60 fps × 14 vehicles × 2
sources that is roughly **1,700 dataset rebuilds per second** to move 14 dots
a few pixels. The loop also ran unconditionally, including the ~99% of frames
where nothing was interpolating, and the trail source only ever changes when
data arrives (≈ every 4 s) so re-sending it per frame was pure waste.

**Fix.** The loop now exits when the interpolation reaches 1 and parks itself;
a `startRef` wakes it on each data arrival. Only the vehicle source is touched
during interpolation, and the trail source is pushed once per arrival.

**Result.**

| Route | Before | After | Change |
|---|---|---|---|
| `/live-map` | 3,441/s | **2,604/s** | **−24%** |

**Interpretation — and an honest limit.** This is a real improvement but it is
*not* a fix. The remaining 2,604/s is inherent to interpolating through the
data layer: any `setData` re-tessellates the whole collection. Eliminating it
requires moving interpolation to a MapLibre custom layer or symbol-level
update, where position is a GPU attribute rather than a data rebuild. That is a
larger change and was **not** taken unprompted. It is recorded as architectural
debt in `docs/ARCHITECTURE.md` §8.

## 3. Render cost — investigated and cleared

`backdrop-filter` was the first suspect (13 blurred surfaces). **It was
measured and cleared**, not assumed:

| Condition | Frame time (median) |
|---|---|
| As shipped (blur on) | 83.4 ms |
| All blur disabled | 100.0 ms |

Disabling blur made it *worse*, so the 13 blurred surfaces were left alone. The
12 fps implied by these figures is itself a headless-rAF artifact, which is why
§1 abandons frame timing for mutation counting.

**Interpretation:** a plausible-sounding hypothesis, cheaply tested and
rejected. Worth recording precisely because it was wrong.

## 4. Accuracy — the alert-counter defect

A healthy fleet was reporting **154–224 alerts per tick**. That looked like a
detection-sensitivity problem; it was an arithmetic bug.

`alerts_delta()` differenced the **sum** of cumulative lifetime counters.
Whenever any single counter incremented, the delta jumped by the entire
historical total. Fixing it to difference each counter against its own
baseline brought all 14 healthy vehicles to **zero** alerts.

**Cross-validation:** 5/5 backend suites pass after the fix, and a live
compressor failure still produces exactly one incident. So the fix removed the
phantom alerts **without** suppressing real detection.

This is the clearest example in the project of why the deterministic-simulation
decision pays: the bug produced a number, and that number was checkable.

## 5. Accuracy — cargo-aware risk

Frozen cargo held at **−18 °C** was flagged as breaching an **8 °C** limit. The
temperature was correct; the threshold was wrong — a single chilled-goods
threshold had been applied to every cargo class.

Fixed to evaluate each vehicle against its own band's safe range (frozen
≈ −22…−15 °C). All 14 healthy vehicles now read `nominal`.

**Interpretation:** a false positive in a safety product is worse than a
missing alert, because it trains the operator to ignore the rail. This is why
the telemetry rail derives its state from live KPIs with a text equivalent,
rather than from a hardcoded threshold.

## 6. Accuracy — incident resolution

Resolution requires a `RecoveryVerifier` result with `v["verified"]` truthy.
**It is not timeout-based.** A recovery that does not verify leaves the
incident open. Verified directly: the per-simulation path reaches `RESOLVED`,
and of 10 per-simulation incidents, 5 reached `RESOLVED`.

**Correction of an earlier false diagnosis.** An analysis initially reported 32
open incidents as a monotonic leak. Checking `simulation_id` first showed 27
belong to the fleet-orchestrator ID space with an independent lifecycle, and
only 10 are per-simulation. Treating them as one counter would have produced a
wrong fix.

## 7. Frontend correctness

| Route | HTTP | `<h1>` | Console errors |
|---|---|---|---|
| All 14 routes | 200 | exactly 1 | 0 |

Gated by judge check G4, so a regression fails the build rather than waiting to
be noticed.

## 8. Accessibility results

| Metric | Before | After | Standard |
|---|---|---|---|
| Controls under 24 px | 91 / 407 (22.4%) | **0 / 411** | WCAG 2.2 §2.5.8 |
| Infinite animations under reduced motion | 14 | **0** | `prefers-reduced-motion` |

Both are gated (G6, plus a design-review checklist item for the media query,
which a desktop computed-style probe cannot detect).

## 9. Security results

| Check | Result |
|---|---|
| Credential-shaped literals in tracked source | **0** (was 6 hardcoded Gemini keys) |
| `.env` tracked by git | No (purged at `cba6df9`) |
| JWT default signing key | Refuses to start outside development |
| Gate B1 — protected files unchanged | 8/8 |

**Outstanding, requires the account owner:** the two Gemini keys remain valid
at the provider. They were in tracked source and in git history. Removal from
source is done; **rotation is not**, and only the owner can perform it.

## 10. Reproducibility

Because the simulation is rule-based, results are exactly reproducible: the
same seed and inputs produce identical output (asserted in TC-02). This is the
direct advantage of decision D1 in `docs/ARCHITECTURE.md` §5, and it is what
makes every number in this document checkable rather than anecdotal.

## 11. Summary

| Criterion | Result |
|---|---|
| Reproducible | Yes — deterministic, asserted |
| Verifiable | Every number has a committed script |
| Quantitative | 7 measured results, before/after |
| Interpreted | Each states what it means, including what is *not* fixed |
| Honest | Two hypotheses tested and rejected; one false diagnosis corrected |
