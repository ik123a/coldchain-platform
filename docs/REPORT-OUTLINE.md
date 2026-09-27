# Mini-Report — Structural Outline & Evidence Map

**Course:** CBCA301 Capstone Project · **Format required:** 20–30 pages
**Deadline:** 23 November 2026 (Panel Evaluation)

> **This is not the report.** It is the skeleton plus an evidence map: for each
> section, what the rubric expects, which committed artefact supplies the facts,
> and what still has to be written in the group's own words.
>
> **The academic prose must be your group's work.** An agent writing a
> capstone report raises academic-integrity problems under the university rules
> ("responsible AI use", "plagiarism, academic integrity"). What follows is
> scaffolding so you spend your time arguing and writing rather than hunting
> for numbers.

---

## How to use this

1. Open the linked artefact for each section — the facts are already verified.
2. Write the argument and interpretation yourself; cite the artefact.
3. Anything marked **WRITE** has no committed source and needs your input.
4. Page budget assumes ~350 words/page with 2–3 figures per chapter.

---

## Front matter (3–4 pp)

| Item | Source | Status |
|---|---|---|
| Cover page | University template | **WRITE** — group names, IDs, guide |
| Certificate | As prescribed by the school | **WRITE** |
| Declaration | As prescribed by the school | **WRITE** |
| Abstract (250–300 words) | §Summary of contributions below | Draft from the table |
| Table of contents | auto-generate | LaTeX/Word |
| List of figures/tables | The 6 figures below | — |

---

## Chapter 1 — Introduction and Problem Statement (3–4 pp)

**Rubric link:** CO1 · *Problem Definition & SDG Alignment (5)*

**Evidence available**
- [`docs/SDG-STAKEHOLDERS-REQUIREMENTS.md`](SDG-STAKEHOLDERS-REQUIREMENTS.md) §1 problem statement, §2 motivation table, §3 SDG mapping
- Live demo: `/live-map`, `/incidents`

**The argument to make**
Cold-chain loss is currently detected at the *destination*, after the value is
already gone. This project builds the missing half: detection and recovery
*while the vehicle is moving*.

**SDG claim — state it precisely**

| SDG | Target | Relationship |
|---|---|---|
| **3 — Good Health and Well-Being** (primary) | 3.d — early-warning systems for health risk | Direct implementation: a live twin surfacing a compressor failure before delivery is an early-warning system for a health risk |
| **2 — Zero Hunger** (secondary) | 2.1 — end hunger, ensure safe nutritious food | Perishable spoilage is a food-loss mechanism; the chilled/frozen cargo classes model it |

**Do not claim SDG 13.** The heatwave scenario *models* ambient weather, but
the product's output is a routing decision, not an emissions claim. Claiming
it would be inflation and is easy for a panel to challenge.
→ Source: SDG doc §3, "What it is NOT".

**WRITE:** your own framing of why this matters to *you*, and the target-user
statement in your own words.

---

## Chapter 2 — Background / Literature / Existing Solutions (3–4 pp)

**Rubric link:** *Literature/Existing Solutions & Gap (5)* — **the weakest
area, because no literature review has been done.**

**Evidence available**
- Contrast with the Awwwards reference study in `docs/PERFORMANCE-RESULTS.md` §7 — usable as a *design* comparison
- `docs/ARCHITECTURE.md` §5 — the alternatives you rejected and why

**WRITE — this chapter needs real work:**
| Need | Why it matters |
|---|---|
| 3–5 academic papers on cold-chain monitoring | The rubric awards marks for "literature evidence" |
| 2–3 commercial systems (e.g. Sensitech, Tive, Roambee) | Shows you know the competitive space |
| An explicit **gap statement** | "Existing X does Y; none does Z" is the highest-value sentence in the chapter |

**This is the one chapter where the agent has contributed nothing, and the
rubric allots it 5 marks.** Budget your time accordingly.

---

## Chapter 3 — Requirements & Stakeholder Analysis (3 pp)

**Rubric link:** CO2 · *Stakeholder & Requirements Analysis (5)*

**Evidence available — essentially complete**
- Stakeholder table: 6 stakeholders with need/system-response pairs
- Requirements: 10 functional (FR-01…FR-10), 8 non-functional (NFR-01…NFR-08)
- Explicit non-requirements (scope discipline is scored)
- Technology selection table with justification per layer

→ Source: SDG doc §4, §5, §6.

**WRITE:** the primary-stakeholder argument. The source doc names the
dispatcher primary and explains every design decision follows from that.

---

## Chapter 4 — Proposed Methodology / System Design (4–5 pp)

**Rubric link:** *System/Technical Design (5)*

**Evidence available — complete**
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — layer diagram, 26-module
  inventory, 15-table data model, 6 agents, incident-lifecycle flow,
  **10 numbered technical decisions each with the rejected alternative**
- [`docs/use-case-diagram.html`](use-case-diagram.html) — UML, 5 actors,
  12 use cases, all 54 endpoints mapped
- [`docs/data-flow-diagram.html`](data-flow-diagram.html) — L0 context,
  L1 processes + stores, incident sequence

**Figures for this chapter:** use-case diagram, DFD L1, architecture layers,
data model.

**The decision table (§5 of ARCHITECTURE.md) is the strongest single artefact
you have.** Ten decisions, each with rationale and the alternative rejected —
that is exactly what "good technical decisions and coherence" means. Use it.

**The one to defend in the viva:** *why no LLM in the operational path.*
Answer: the rubric scores reproducible results; an LLM decision layer would
forfeit determinism. The system asserts `ai_mode = DETERMINISTIC-AGENTS` and
the UI is gated on that string so it cannot claim an AI it does not use.

---

## Chapter 5 — Implementation (4–5 pp)

**Rubric link:** *Prototype/MVP Implementation (10 — the largest single
criterion)*

**Evidence available**
- 26 modules, 11 API route groups, 54 endpoints, 14 frontend routes
- Figures: screenshots from `C:/Users/SKV/ui-compare/final/`
- Demo video: `C:/Users/SKV/coldchain-video/coldchain-ui-tour.mp4` (56s)

**WRITE:** what *you* built vs what each group member built. The guide
evaluates **individual contribution (5 marks)** and will ask. Keep this
section factual and specific.

**Screenshot suggestions** (all currently render with 0 console errors):
1. `/live-map` — the live fleet with telemetry rail
2. `/incidents` — an incident with root-cause diagram
3. `/simulation` — scenario control + failure injection
4. `/twin` — per-vehicle reconstruction (shows Zone A 22 °C / Zone C −18 °C)

---

## Chapter 6 — Testing, Results and Validation (4–5 pp)

**Rubric link:** *Testing & Validation (5)* + *Performance and Results (5)*

**Evidence available — the strongest chapter, all measured**
- [`docs/TESTING.md`](TESTING.md) — 7 test cases, how to run each,
  **4 cross-validation methods** with deliberately different failure modes
- [`docs/PERFORMANCE-RESULTS.md`](PERFORMANCE-RESULTS.md) — 7 measured
  results with interpretation, including the ones that did not go your way

**Results table to reproduce (all measured, all reproducible):**

| # | Result | Before → After |
|---|---|---|
| 1 | DOM mutations on `/live-map` | 3,441/s → 2,604/s (−24%) |
| 2 | Phantom alerts on a healthy fleet | 154–224 → **0** |
| 3 | Controls under 24 px (WCAG 2.5.8) | 91/407 (22.4%) → **0/411** |
| 4 | Infinite animations under reduced motion | 14 → **0** |
| 5 | Credential literals in tracked source | 6 → **0** |
| 6 | Routes clean (HTTP 200, 1 `<h1>`, 0 errors) | 14/14 |
| 7 | Backend suites | 5/5 PASS |

**Report the incomplete one too.** The performance fix is −24%, *not* a fix;
the residual needs a MapLibre custom layer. Say so. The rubric rewards
"well defined limitations and remaining work", and volunteering the gap is
stronger than being caught on it.

**Also disclose the known failing assertion:** `acceptance_sweep.py` has one
`service.completed` contract failure, classified as a §6C sweep-contract
issue, not a broken incident pipeline (the incident chain independently
reaches `RESOLVED`).

---

## Chapter 7 — SDG Impact, Discussion, Limitations, Future Scope (2–3 pp)

**Rubric link:** *SDG Impact & Societal/Industry Relevance (2)*

**Evidence available**
- SDG mapping with rationale: SDG doc §3
- **7 limitations** with effect + mitigation: SDG doc §8
- Architectural debt: ARCHITECTURE.md §8
- Future prospects across 4 horizons: LOG-DIARY.md

**Honest framing that will play well with a panel:** the strongest SDG
argument is *what you did not claim*. State SDG 13 explicitly as rejected and
why — it demonstrates you understood the difference between modelling weather
and reducing emissions.

**WRITE:** one paragraph on societal relevance in your own words (who benefits,
and what changes for a dispatcher, a quality officer, a consignor).

---

## Chapter 8 — Conclusion (1 pp)

**Rubric link:** CO3

**WRITE.** Three sentences: what was built, what was proven, what remains.
Do not introduce new claims here.

---

## References, Appendices

| Item | Status |
|---|---|
| Literature review (Ch. 2) | **WRITE — not done** |
| Technology docs (Next.js, FastAPI, MapLibre, SQLAlchemy) | Cite official docs |
| Appendices: test output, gate output, screenshots | Committed in `docs/` — cite by path |

---

## Summary of contributions (for the Abstract)

Use this as a scaffold and rewrite it in your own words:

> ColdChain Rescue is a live operational digital twin for cold-chain logistics
> that detects temperature excursions while a vehicle is in transit and drives a
> verified recovery, rather than reporting loss after delivery. The system
> comprises 26 backend/simulation modules, 54 API endpoints and 14 frontend
> routes over a 15-table data model, driven by six deterministic rule-based
> agents. Determinism was chosen deliberately: it makes every result exactly
> reproducible, and the product asserts `ai_mode = DETERMINISTIC-AGENTS` so it
> cannot misrepresent an AI capability it does not have. Contributions include
> a per-cargo-class excursion model, a verified incident lifecycle, an
> accessibility remediation from 91 undersized controls to zero, a 24%
> reduction in live-map render cost, and a six-goal acceptance gate whose
> anti-Goodhart boundary was proven by deliberately corrupting a test file.

---

## Effort estimate

| Section | Status | Your effort |
|---|---|---|
| Front matter | template needed | Low |
| Ch. 1 Introduction | evidence ready | Medium — write the argument |
| **Ch. 2 Literature** | **not started** | **High — the real gap** |
| Ch. 3 Requirements | evidence ready | Low |
| Ch. 4 System design | evidence ready + 4 figures | Low |
| Ch. 5 Implementation | evidence ready | Medium — individual contribution |
| Ch. 6 Testing & results | evidence ready | Low |
| Ch. 7 SDG + limitations | evidence ready | Medium |
| Ch. 8 Conclusion | — | Low |
| References | not started | Medium |

**Start with Chapter 2.** It is the only chapter with no committed source, it
carries 5 rubric marks, and it is the one a panel can most easily tell was not
genuinely done.

---

## Before submission — checklist

- [ ] `python .loop/judge.py` exits 0 (6/6 goals, 3/3 boundaries)
- [ ] `python tools/rubric_audit.py` shows only Report + Presentation missing
- [ ] **Gemini keys rotated** at the provider (in git history — see LOG-DIARY)
- [ ] Auth posture decided and documented
- [ ] Every figure in the report regenerates from a committed script
- [ ] Individual contribution section written per group member (guide scores it separately)
- [ ] Declaration and certificate signed
- [ ] Chapter 2 literature review genuinely done
