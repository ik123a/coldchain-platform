# GitHub Inspiration & Evolution Notes — ColdChain Rescue

Swept 10 Oct 2026 with `gh search repos` across: cold chain monitoring, cold-chain
digital twin, cold-chain logistics IoT, reefer container, vaccine cold chain,
predictive maintenance IoT, fleet digital twin.

**Read this with the novelty constraint in mind.** These are *implementation
references*, not competitive claims. Verified 2026 literature already occupies the
obvious novelty gaps (see the capstone skill's "NOVELTY IS CONSTRAINED" section),
and no repo below is academically evaluated. What they are good for is stealing a
*shape* — a data pipeline, a simulator's sensor vocabulary, an analytics layout —
not for asserting we are first at anything.

---

## Notable comparable projects

| Repo | ★ | Stack | What it actually is |
|---|---|---|---|
| `ibm-cloud-architecture/refarch-reefer-ml` | 11 | Jupyter / Kafka / OpenShift | Prescriptive maintenance on reefer event streams: reefer **simulator** → scoring microservice (logistic regression) → event listener that **triggers a business process** when the score says "needs maintenance". Runs Kafka/Zookeeper/Postgres locally via Docker. |
| `An32006shi/Cold-Chain-Logistics-Analytics` | 0 | Python / SQL / Streamlit / Power BI | "Predictive cold-chain logistics, IoT thermal-drift telemetry & spoilage-risk analytics". Thermal drift + spoilage scoring, warehouse-shaped reporting. |
| `sarox56/Fleet-Digital-Twin` | 0 | TypeScript / Eclipse Ditto / K8s | Digital-twin IoT platform for fleet management: Ditto twin registry, real-time streaming, analytics, edge-cloud orchestration. |
| `Anusha0501/ThermaGuard-AI` | 0 | Python | "Predictive cold-chain monitoring system" — closest name-match to our predictive layer. |
| `SoumilBhandari/SecuriVax` | 3 | Python | Vaccine cold-chain integrity made "visible, measurable, actionable" — framing reference for the ops UI. |
| `Onfroy666999/coldwatch-iot-dashboard` | 2 | TypeScript | IoT cold-chain monitoring & control dashboard (KNUST 2026 student project). |
| `ishaanpgujaran/ChainChill` | 2 | JavaScript | Blockchain-based cold-chain monitoring & compliance DApp — the *audit/immutability* angle we deliberately left out. |

Honest read: the field on GitHub is thin and mostly student/portfolio work. **No
repo carries a fleet of 14 live digital twins with a deterministic decision loop
and a human-approval gate** — that remains our differentiator. But two of them
solve pieces we do poorly, below.

---

## What to steal (concrete)

### 1. Event-driven "scoring agent → business process" shape — from `refarch-reefer-ml`
IBM's pipeline is: stream in → **scoring agent** emits a verdict → a *listener
triggers a downstream business process*. Ours currently: incident → decision →
directive, wired tightly inside the orchestrator. The decoupling is worth copying
as a refactor: publish a `MaintenanceVerdict` signal and let a subscriber decide
the action. It makes the scoring layer independently testable, which is exactly
what the M2 "MAPE validation" milestone needs.

### 2. A reefer simulator with a richer sensor vocabulary — from `refarch-reefer-ml`
Their simulator emits the signals a real reefer telematics unit does. Ours emits
temperature / humidity / compressor / door / power. Adopt their vocabulary for
**evaporator coil temp, suction/discharge pressure, defrost cycle, and power
draw** — real reefers report these, and a compressor-failure signature is
*visible in the pressure trace before the box temperature moves*. That is a
genuine predictive win: detect the failure from the thermal system's own signals,
not from the cargo warming up after it is already too late.

### 3. Thermal-drift analytics layer — from `Cold-Chain-Logistics-Analytics`
They pair thermal-drift telemetry with spoilage-risk scoring and an SQL-backed
reporting surface. We have the drift (`trend_c_per_min`) and the risk verdict but
report them per-truck. Add a **fleet-level drift leaderboard** and a
spoilage-risk roll-up to `/analytics` — cheap, and it turns the per-truck
prediction into an operator-prioritisation tool.

### 4. "Visible, measurable, actionable" framing — from `SecuriVax` / `ThermaGuard-AI`
Useful as UI copy discipline for the predictive layer: every prediction surface
should show *what was measured*, *the projection*, and *the one action it implies*.
Our `/api/fleet/predictions` already returns `verdict` + `remedy` — surface both
in the truck drawer so the honesty contract ("linear trend projection, kinetics
not modelled") travels with the number.

---

## What to leave behind

- **Blockchain / DApp compliance (ChainChill).** Immutable audit is a real
  requirement in regulated pharma, but it is orthogonal to the rescue-optimisation
  claim, adds a heavy dependency, and would dilute the SDG 12.3 focus.
- **Power BI / Streamlit reporting stacks.** Our Next.js `/analytics` already
  covers this; bolting on a second BI tool is scope creep for a capstone.
- **Kafka/Zookeeper/OpenShift.** `refarch-reefer-ml` needs a cluster to run. Our
  asyncio single-process loop is a *feature* for a viva demo (starts in 8s, no
  infra). Keep it.
- **Claiming novelty from any of these repos.** They are small, unevaluated, and
  mostly student work. Cite them as *implementations that exist*, never as
  evidence of a gap we fill.

---

## Evolution roadmap (maps onto the M2 roadmap)

| Priority | Change | Source of inspiration | Milestone fit |
|---|---|---|---|
| P1 | Surface `verdict` + `remedy` + the "linear trend, not kinetics" caveat in the truck drawer | SecuriVax framing | M2 demo — makes the prediction honest **and** visible |
| P2 | Fleet-level thermal-drift leaderboard + spoilage roll-up on `/analytics` | Cold-Chain-Logistics-Analytics | M2 MVP — operator prioritisation |
| P3 | Add evaporator/pressure/defrost signals to the twin + a compressor-failure signature that fires *before* cargo warms | refarch-reefer-ml | M2 "physical AI" claim — genuinely predictive |
| P4 | Decouple the decision into a scoring signal + subscriber (business-process trigger) | refarch-reefer-ml | Refactor; improves testability |
| P5 | (Stretch) Immutable incident audit trail | ChainChill | Only if a regulator-audit requirement is added |

**Recommended order for M2:** P1 → P2 are hours of work and directly strengthen the
"The-prediction-is-honest-and-visible" story. P3 is the one with real research
weight (it moves us from "watching the box warm" to "detecting the fault in the
refrigeration system") but needs the kinetics/hardware lane to be credible.
P4–P5 are desirable, not deadline-critical.
