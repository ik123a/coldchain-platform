# FINAL ENGINEERING AND SECURITY REPORT — ColdChain Rescue

**Project:** `D:\Projects\capstone project\coldchain-platform`
**Branch:** `chore/token-adoption-codemod` · **HEAD:** `161269c` — this work is now **committed in 3 commits** (`41a6744` backend, `51f48c0` frontend, `161269c` docs), **not pushed**.
**Report date:** 12 October 2026 (updated after commit)
**Live database digest:** `3510d9fbb2f80c4e` before and after every verification run — **unchanged throughout**.

---

## 1. Executive summary

The platform is **functionally complete and security-hardened for its intended single-node, single-process demo deployment**. Every prior fix was re-verified against current source (not inherited from reports): fail-closed authentication, RBAC with vehicle scoping, authenticated single-use WebSocket tickets with per-frame driver scoping, resource-bound report tickets, Gemini safe-path resolution, honest critique failures, billable-operation rate limits, CWD-independent database paths, and truthful frontend telemetry.

This finalization pass closed the last critical dependency exposure — **Next.js 15.3.2/15.3.3 was vulnerable to two unauthenticated RCE advisories on Windows hosts, where this project actually runs** — by upgrading to **15.5.27** (latest stable 15.5.x) and re-verifying the build and the full acceptance sweep (19/19).

**Readiness statement:** ready for the M2 capstone demonstration on a trusted network. Not production-ready for public internet deployment (see §12, §13). One manual action is mandatory before any public exposure: **rotate the Gemini API key** (§11).

**Scope caveat (adopted verbatim from the project owner):** these results indicate strong progress toward release readiness; they do **not** establish that every browser workflow has been manually verified, nor that every production deployment risk has been eliminated. Backend/API correctness is evidenced by the suites and the 19/19 sweep; interactive UX and operational hardening for a hostile network remain open items (§10, §12).

---

## 2. Technology stack and verified architecture

| Layer | Technology | Verified |
|---|---|---|
| Backend | Python 3.13, FastAPI, SQLAlchemy async, SQLite (aiosqlite), uvicorn | via test suite + live sweep |
| Frontend | Next.js **15.5.27**, React 19.0.0, TypeScript, Tailwind, MapLibre, framer-motion | via production build |
| Realtime | WebSocket `/ws` with single-use ticket auth (subprotocol `cc-ticket.<ticket>`) | via 29 unit + 8 live checks |
| Auth | HS256 JWT (pbkdf2-120k passwords), fail-closed `require_auth`/`require_auth_read`, `require_role`, `require_vehicle_scope` | via 17+ authorization tests |
| Simulation | Deterministic multi-agent fleet orchestrator (no LLM in the decision path) | via acceptance sweep identity check |
| External AI | Gemini image/video/critique services — **disabled-path-safe** (explicit failures, never fabricated success) | via honesty tests |

Two parallel simulation systems exist (documented in the repo audit): the fleet world (`simulation_id=0`, `fleet_orchestrator.py`) and the classic single-box sim (`runner.py`). The acceptance sweep exercises the fleet world end-to-end.

---

## 3. Security fixes implemented (with evidence)

All items below were **verified against current source during this mission**, not trusted from earlier reports.

### 3.1 Authentication & authorization (verified intact)
- `REQUIRE_AUTH = True` (constant, fail-closed) — `app/core/authz.py:59`.
- `ALLOW_ANONYMOUS_WRITES` defaults `False`; launcher (`scripts/coldchain.ps1`) sets only `APP_ENV=development` and never enables it.
- `require_role("operator")` on operator-only routes; `require_vehicle_scope` on driver vehicle actions.
- Public registration/login unprotected by design; all other state-changing routes require a valid bearer token.

### 3.2 Authenticated WebSocket (implemented this mission set; verified)
- `POST /api/ws/ticket` (bearer-auth) mints an opaque `secrets.token_urlsafe(32)` ticket, TTL 30 s, bound to principal + scope (`fleet` for operators, `vehicle` for drivers).
- **Single-use redemption is atomic** (`threading.Lock` + tombstones in `app/core/ws_tickets.py`); replay rejected. Proven under a 2-thread race (exactly one winner) and live (second connect → HTTP 403).
- Handshake presents the ticket as subprotocol `cc-ticket.<ticket>` — **uvicorn logs the full query string on WS accept**, so a `?ticket=` credential would leak verbatim; the subprotocol rides in headers, which are never logged. A query fallback remains for non-browser clients, defended by the `_RedactWsTickets` logging filter on uvicorn's loggers in `app/main.py`.
- **Per-frame scope enforcement** (`_narrow`/`_filter_frame` in `app/websocket/handler.py`): whole-fleet `vehicle.position.updated` frames are narrowed to the driver's own vehicle in the same parse that decides visibility; unattributed frames (sensor_update/alert/agent_event/weather) are withheld from drivers. Live proof: during a real fleet rebuild the operator socket saw 26 distinct vehicles, the driver socket saw 0 other-vehicle frames.
- Nothing is sent before the ticket validates (close without accept, WS 1008, no reason text).

### 3.3 Report downloads (verified)
- `REPORT_TICKET_TTL_S` = 300 s (session token TTL unchanged at 12 h); ticket bound to `iid` via `extra={"iid": ..., "typ": "report_ticket"}`; mismatch → 403; session token in the `?ticket=` slot → 401; anonymous → 401. Verified 8/8 live on an isolated server in the prior phase.

### 3.4 Gemini arbitrary-file-read (verified)
- Client references resolve only inside `design-references/images/` via asset id or bare filename (`app/services/gemini/safe_paths.py`); separators, drive prefixes, `..`, NUL bytes, and disallowed suffixes are rejected **before any filesystem call or billable provider call** (both in the route, 400, and in the service, fail-closed `rejected_reference: True`).
- `Path.resolve()` + `is_relative_to` defeats symlink escape; suffix allowlist; 8 MB cap.
- **API keys are sent in the `x-goog-api-key` header, never in URLs** — all three Gemini services and the operation-status poll. Regression test `SecretHygieneTests.test_no_api_key_in_any_upstream_url` pins this (a URL-embedded key was printed by a failing test in an earlier session).
- `check_video_operation` validates `operation_name` format (`models/<m>/operations/<id>`) before it reaches a URL (SSRF-by-parameter).

### 3.5 Honest critique failures (implemented this mission)
- The fabricated fallback (hardcoded 9.x scores, verdict `APPROVED`) is **deleted**. Missing key → `{success: False, status: "unavailable"}` → HTTP 503; provider 429 → `rate_limited` → 429; provider error/network failure/malformed output → `failed` → 502. Only a genuine 200 with parseable JSON containing `overall_verdict` returns scores. Tests: `tests/test_gemini_honesty.py` (12/12), including the route-level assertion that failure can never map to 200+scores.

### 3.6 Billable-operation rate limits (implemented this mission)
- New `app/core/rate_limit.py` (`RateLimiter`, fixed-window, lock-guarded, injectable clock). Per-principal limits on the three billable endpoints: image 10/min, video 3/min, critique 15/min (`GEMINI_RL_*_PER_MIN` env-overridable), plus 429 responses. Documented single-process constraint in §12. Tests cover limit enforcement, per-principal independence, window rollover, and a global cap.

### 3.7 Credential & history scan (metadata-only)
- 323 tracked files scanned: **no credential-shaped literals** (Google `AIza…`, JWT secret assignments, bearer literals).
- All 88 commits scanned blob-by-blob: the only `AIza` mentions are **detection regexes inside scanner tools** (`tools/scan_history_secrets.py`, `tools/redact_blobs.py`, `.loop/judge.py`) — zero real credential literals remain in history.
- `.env` is git-ignored; `.env.example` contains placeholders only.

---

## 4. Simulation, recovery, transfer, service-dispatch, KPI correctness (verified, not modified this pass)

- **Recovery verification:** RESOLVED requires verifier evidence with cargo-specific bounds (recoverable in `tests/test_recovery_verification.py`).
- **Transfer semantics:** RESOLVED / TRANSFERRED / ESCALATED remain distinct; `CargoTransfer` rows only for genuine transfers; failed diversions leave cargo stranded and escalating (acceptance-sweep `transfer progress ramps 0→100` PASS).
- **Service dispatch:** `_retarget_service` navigation fix verified live — `service.completed` observed during the sweep after genuine arrival and repair; the arrival radius is the module constant `SERVICE_ARRIVAL_KM = 0.8`.
- **Route persistence:** no `fleet_routes.id` collisions during the sweep's multiple diverts.
- **KPIs:** `analytics fleet_health sums to cargo count (10)` PASS; heuristic scores remain labelled as heuristics; no fabricated financial values in backend metrics.

---

## 5. Database configuration and test isolation

- **CWD-independent default path (implemented this mission):** `app/database/engine.py` now anchors the default SQLite URL to `<repo>/backend/coldchain.db` (verified from an arbitrary CWD) instead of `./coldchain.db`, which silently created a second empty database when uvicorn was started from the repo root (the origin of the 0-byte root `coldchain.db` artefact, left in place, untouched). Explicit `DATABASE_URL` values retain their exact documented semantics.
- SQLite `timeout=5` connect arg added (busy-wait for the one-writer + short-request pattern).
- **Isolation:** `tests/_db_isolation.py` + `conftest.py` set the URL before any app import; negative control (`CC_TEST_ISOLATION_OFF=1` abort, exit 4) retained; positive run with the new default left the live digest unchanged. The 0-byte root DB and the populated backend DB were never moved, merged, deleted, or migrated.
- **Contamination:** the previously identified 42 test-signature incidents remain in the live DB, untouched, pending a human decision with reliable evidence.

---

## 6. Frontend truthfulness, downloads, and functionality

- **`data-stream.tsx` rewritten (this mission):** rendered `Math.random()` fiction under a "LIVE TELEMETRY FEED" label; now renders real store events (`st.events` from the authenticated WS + REST polls) with a truthful empty state. Dashboard passes actual events.
- **Landing page (this mission):** fabricated "KINETICS BENCHMARK" panel with `Ea = 78.4 kJ/mol` and invented rate multipliers replaced by a "PROJECTION BASIS" panel describing the actual margin÷trend method; `$145,000` figures relabelled as example-scenario values; "physics clone" claim corrected to an illustrative walkthrough; dashboard chip "ARRHENIUS GATED" → "TREND PROJECTION".
- Report downloads: ticket-based flow (Phase 2, verified 8/8 live earlier). Remaining gap noted in §10: the browser-level click-through was verified at the API level, not by watching a file land in a browser this pass.
- Login/RBAC journeys and driver scoping were e2e-verified in earlier phases (9/9) and their backend contracts re-verified this pass.

---

## 7. Dependency advisories and final versions

| Advisory | Affects installed? | Action |
|---|---|---|
| CVE-2025-29927 (middleware auth bypass) | No (≥ 15.2.3) | — |
| CVE-2025-49005 (RSC/HTML cache poisoning, 15.3.0–15.3.2) | **Yes at 15.3.2** | Upgraded → 15.3.3 (earlier pass) |
| **CVE-2026-75604 / GHSA-p293-qw3h-jr36 (unauthenticated RCE, Windows-hosted servers, no workaround, public PoC)** | **Yes at 15.3.3 — and this project runs on Windows** | **Upgraded → 15.5.27** |
| **GHSA-2xp9-vwfh-vxw4 (unauthenticated RCE via AVIF image optimization / libheif)** | Affected range (< 15.5.24); exposure requires AVIF optimization enabled | **Upgraded → 15.5.27** (patched releases disable AVIF optimization pending upstream libheif fix) |

**Final versions:** `next@15.5.27` (package.json + lockfile consistent), `react@19.0.0`, `react-dom@19.0.0` (compatible; no major-version jump). Build after upgrade: **Compiled successfully**; baked rewrite target verified as `http://127.0.0.1:8000/api/:path*`, matching the launcher. Advisory verification used the official GitHub advisories, the Vercel August-2026 security release, and NVD. `npm audit` was **not** run and is not claimed.

---

## 8. Changed-file inventory

**This finalization mission:**
```
M  frontend/package.json                     (next 15.3.3 → 15.5.27)
M  frontend/package-lock.json                (lockfile consistent)
```

**This mission overall (engineering + security pass; all in working tree, uncommitted):**
```
?? backend/app/core/ws_tickets.py            new — single-use WS tickets
?? backend/app/core/rate_limit.py            new — billable-op limiter
?? backend/tests/test_ws_auth.py             new — 29 tests
?? backend/tests/test_gemini_honesty.py      new — 12 tests
?? backend/tests/test_gemini_security.py     new — 16 tests
?? backend/tests/test_report_tickets.py      new — 11 tests
M  backend/app/websocket/handler.py          authenticated WS + per-frame scoping
M  backend/app/main.py                       log-redaction filter
M  backend/app/database/engine.py            CWD-independent default DB path
M  backend/app/api/routes/gemini.py          rate limits + honest failure mapping
M  backend/app/api/routes/reports.py         ticket TTL + resource binding
M  backend/app/core/security.py              ttl_seconds/extra params
M  backend/app/services/gemini/safe_paths.py new — approved-asset resolution
M  backend/app/services/gemini/image_generation.py   fail-closed refs; key in header
M  backend/app/services/gemini/video_generation.py   fail-closed refs; key in header; op-name validation
M  backend/app/services/gemini/critique.py   fabricated fallback removed
M  backend/tests/acceptance_sweep.py         SWEEP_BASE/SWEEP_WS config; ticket minting
M  frontend/lib/api.ts                       fetchWsTicket()
M  frontend/lib/store.tsx                    auth-gated socket, fresh ticket/backoff
M  frontend/components/ui/data-stream.tsx    real events, no random fiction
M  frontend/app/page.tsx                     Arrhenius/$ figures made honest
M  frontend/app/dashboard/page.tsx           chip label; DataStream wired to events
```

**Pre-existing changes preserved untouched:** recovery-verification, cargo-transfer, service-dispatch navigation, route-ID collision fix, test-isolation framework, authorization Phase 1, E2E suite and cleanup, launcher — all confirmed intact in current source and re-exercised by the passing suites.

---

## 9. Test, build, and acceptance-sweep results (actual exit codes)

| Run | Command (abbreviated) | Result | Exit |
|---|---|---|---|
| Backend full suite (isolated temp DBs) | `pytest tests/ --ignore=tests/acceptance_sweep.py` | **138 passed, 0 failed, 0 skipped** | 0 |
| Frontend production build (15.5.27) | `next build` with launcher `API_ORIGIN` | **Compiled successfully** | 0 |
| Frontend build (15.3.3, pre-upgrade baseline) | `next build` | Compiled successfully | 0 |
| Acceptance sweep (isolated, fresh empty DB, port 8010, identity-verified) | `acceptance_sweep.py` | **19/19 assertions PASS** (incl. `vehicle.route.changed`, `service.completed`, transfer ramp, KPI, approval gate on) | 0 |
| Live WS checks (earlier phase, isolated) | `verify_ws_live.py` | 8/8 | 0 |
| Live WS scoping (earlier phase, isolated) | `verify_ws_scoping_live.py` | operator 26 vehicles / driver 0 other frames | 0 |
| Live report-ticket checks (earlier phase) | `verify_report_tickets_live.py` | 8/8 | 0 |
| Negative controls | e.g. pre-fix code fails 9/29 WS tests, 11/14 Gemini tests | tests genuinely catch the defects | — |

Isolated sweep environment: fresh empty SQLite at `D:/Temp/cc_sweep_final_w842w3gy/sweep.db`, bound to `127.0.0.1:8010`, identity confirmed (`ai_mode: DETERMINISTIC-AGENTS`) before any mutating request, server stopped after (`8010` free). Live DB digest unchanged before/after all runs. No real billable Gemini call was made; all provider transport in tests is mocked.

---

## 10. Remaining bugs, known limitations, tests not run

1. **Browser-level download/socket click-through not re-run this pass** — report downloads and the socket lifecycle were verified at the API/transport level; an interactive browser session (Playwright) would close the last experiential gap.
2. **`FleetCoordinator` CONTINUE-on-CRITICAL defect (pre-existing, ledger item 7)** — the approval gate can be unreachable for a CRITICAL load because the risk projection adds `slope*eta` over the whole trip. The sweep passes because it drives the approval API directly. Still open; fix is a bounded change to the projection, deliberately not attempted in this pass.
3. **Fragile incident-description parsing** in `FLEET.replay()` (`description.split(":")`) — open.
4. **`test_scenario_analytics.py` hard-asserts vehicle count** — open (baseline-pinned).
5. **42 test-signature incidents** remain in the live DB — untouched pending evidence-based human review.
6. **E2E suite not re-run this pass** (requires the dev servers; backend contracts it depends on were re-verified by the suite + sweep instead).
7. `npm audit` not run; advisory verification was manual against official sources.

---

## 11. MANUAL ACTION REQUIRED — Gemini credential rotation

A live Gemini API key was exposed through test output in an earlier session (the URL-embedded `?key=` pattern, since removed from the code entirely). **This key must be treated as compromised and rotated in the Google AI Studio / Cloud console by the account owner.** Code-level mitigations (header transport, no-URL test, log redaction) are complete, but revocation is external and **has not been performed** — nothing in this report claims it has.

**Rotation attempt status (12 Oct, post-report):**
- Control test against the provider confirmed the exposed key in `backend/.env` **still authenticates** (HTTP 200; initial 503s were transient provider-side). It has NOT been revoked.
- Browser-driven rotation in AI Studio was attempted and is currently **blocked: the local browser automation daemon is unresponsive** (all probes timed out). Rotation therefore remains a **manual action for the project owner**.
- Once a replacement key is placed in `backend/.env`, a controlled verification (provider call with the key sent via `x-goog-api-key` header, value never printed) will confirm the new credential without exposure. The same check should be applied to `GEMINI_API_KEY_BACKUP` and `GOOGLE_API_KEY`, which hold distinct values and must be revoked too if they match any exposed credential.

---

## 12. Deployment constraints

- **Single-process, in-memory ticket store and rate limiters.** WS tickets, report-ticket tombstoning state, and the gemini rate limiters live in process memory: a restart voids outstanding tickets (clients re-mint transparently) and a multi-worker deployment would NOT share them (per-worker limits = limit × workers). Multi-worker or multi-node deployment requires Redis or a DB-backed store — a documented design task, deliberately not introduced untested.
- **Windows RCE posture:** with 15.5.27 both Windows-specific advisories are addressed; keep Next.js on a patched 15.5.x/16.x line when upgrading further.
- **AVIF:** patched Next releases disable AVIF optimization pending the upstream libheif fix — do not re-enable it until the advisory clears.
- **SQLite** is appropriate for the single-node capstone; Postgres is required for any multi-instance deployment.
- Launcher expectations unchanged: backend :8000 via `scripts/coldchain.ps1`, `API_ORIGIN`/`NEXT_PUBLIC_WS_URL` baked at build time (verified in the generated `routes-manifest.json`).

---

## 13. Remaining blockers and next recommended action

| Priority | Item | Next action |
|---|---|---|
| **P0 (manual)** | Gemini key rotation | Revoke + reissue in Google AI Studio; update `backend/.env` only |
| P1 | CONTINUE-on-CRITICAL coordinator defect | Bounded fix to the risk projection + regression asserting `DIVERT` at CRITICAL |
| P2 | Browser E2E re-run on 15.5.27 | `npm run e2e` against isolated servers |
| P2 | Multi-worker ticket/limiter store | Redis-backed adapter behind the existing interfaces |
| P3 | Root-level 0-byte `coldchain.db` artefact | Delete manually once confirmed unneeded (left untouched by policy) |

**Committed (not pushed) at the project owner's instruction: 3 commits on `chore/token-adoption-codemod`** — `41a6744` (backend security/correctness), `51f48c0` (frontend + Next 15.5.27), `161269c` (this report + handoff doc). Runtime artifacts (`.run/`) untracked and gitignored; the owner's demo-film assets under `docs/demo/` remain intentionally untracked. All temporary processes were stopped (isolated servers on 8001/8010 terminated; ports verified free); no user process was touched; the live database was never modified.
