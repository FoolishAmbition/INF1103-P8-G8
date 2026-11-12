# GeoLocation — Project Plan & Progress Tracker

**Baseline:** `oop_andrew` commit `2a08f807248949501946d2dc00a29ad960971e2b`  
**Created:** 10 November 2026  
**Status:** Postal validation is complete and committed. Step 3 transit service is implemented and verified with offline tests, but is not committed or live-tested. OneMap's published terms have been reviewed, but API pricing and numeric usage limits remain unconfirmed. Step 4 assessment and later integration milestones are not started.

## Progress rules
- Work on one milestone at a time; ask for approval before coding.
- Mark a task done only after checking code and evidence.
- A suggested Git commit is **not** an actual commit.
- Record real test commands/results and commit hashes after verification.
- Coordinate edits to `main.py`, `src/models.py`, `src/io_manager.py` and other shared files.

## Step 0 — Scope and documentation
- [x] Confirm home postal saved in profile, destination postal only, public transport.
- [x] Inspect relevant `oop_andrew` source.
- [x] Draft PRD, codebase map, coding background and tracker.
- [x] Check current Git status and branch before implementation.
- [ ] Agree on shared-file integration with team.
- [x] Verify feature branch from `oop_andrew`: `feature/geolocation` is based on `oop_andrew`.

**Suggested commit:** `docs(geolocation): add PRD and development plan`  
**Actual commit:** None.

## Step 1 — API feasibility
- [x] Check Google demo key result: Geocoding was denied because billing was not enabled; Google Routes was not tested.
- [x] Resolve the user's home and destination postal codes through OneMap; both exact matches were reported in the local test.
- [x] Request and receive an actual OneMap public-transport itinerary for those locations.
- [x] Document response fields and units: itinerary duration in seconds, start/end timestamps in milliseconds, and leg distances in metres.
- [x] Select OneMap and accept clearly labelled departure-based estimates; the tested `arriveBy=true` parameter was ignored and did not alter the route.
- [x] Review the official API Terms of Service and Singapore Open Data Licence.
- [x] Confirm the Search API documentation requires a token and documents HTTP 429 for an exceeded API limit.
- [ ] Confirm whether OneMap charges for API calls and the numeric usage limits for Search and public-transport routing before describing access as free or setting usage expectations.

**Exit gate:** Provider behavior is understood and the arrival-time limitation is accepted. Official terms and licence are reviewed, but this remains partially open because the published pages do not confirm API-call pricing or a numeric quota for Search and transit routing.  
**Suggested commit:** `docs(geolocation): document API feasibility`  
**Actual commit:** None.

## Step 2 — Postal validation
- [x] Add isolated six-digit postal validation.
- [x] Preserve leading zeroes and reject invalid inputs.
- [x] Test valid and invalid input formats offline.
- [x] Test that a valid-format but unresolvable postal code is handled; covered by mocked OneMap lookup tests in Step 3.

**Exit gate:** Format validation and its offline tests pass. Address resolution and nonexistent-postal handling are now covered by Step 3 offline tests.  
**Suggested commit:** `feat(geolocation): validate Singapore postal codes`  
**Actual commit:** `983ec9cb6bfd34d887591abfc75f537ee617108a` — 10 November 2026 (`feat/geolocation: validate Singapore postal codes`).

## Step 3 — Transit API service
- [x] Implement postal lookup and a departure-based transit request; do not promise arrival by the event start time.
- [x] Parse distance and duration with correct units.
- [x] Handle timeout, quota, authentication and no-route responses.
- [x] Mock provider responses in automated tests.
- [x] Verify secrets and home postal codes are not logged.

**Exit gate:** Mock success and failure tests pass: `python -B -m unittest test_geolocation -v` — 25 passed (4 existing validation tests and 21 service tests, including subtests). `python -B test_logic_manager.py` — 58 passed, 0 failed. Verified 12 November 2026. No live API requests were made.  
**Suggested commit:** `feat(geolocation): implement public transit routing`  
**Actual commit:** None.

**Implementation:** `src/geolocation.py` now contains `GeoLocationService`, `TransitRoute`, and `GeoLocationError`. The service reads `ONEMAP_ACCESS_TOKEN` when no token is supplied and accepts an injectable HTTP opener for offline tests. It requires a timezone-aware departure, resolves exact postal matches, requests public transport, validates all leg distances, and converts units and itinerary timestamps. Missing data is an explicit failure, never a fabricated zero. Provider errors use safe messages and stable codes; tests verify silent operation and suppression of sensitive HTTP exception context. HTTP-200 provider errors are classified using known message patterns; unfamiliar errors remain `PROVIDER_ERROR`.

**Boundary:** `TransitRoute` contains provider data only. Recommended departure, arrival buffer, feasibility, and the final `TravelAssessment` remain Step 4. The proof-of-concept scripts, shared application files, dependencies, and existing uncommitted diagram/document organisation were not changed. The new service still needs a later authorised live check.

## Step 4 — Departure and feasibility
- [ ] Add travel assessment result.
- [ ] Compute leave time with configurable arrival buffer.
- [ ] Handle Singapore timezone and previous-day departures.
- [ ] Evaluate within-limit, long-journey and unavailable cases.
- [ ] Test thresholds and midnight boundaries.

**Exit gate:** Deterministic assessment tests pass.  
**Suggested commit:** `feat(geolocation): calculate departure and feasibility`  
**Actual commit:** None.

## Step 5 — Student profile integration (shared files)
- [ ] Add optional `home_postal_code` to `StudentProfile`.
- [ ] Update `to_dict`/`from_dict` and profile prompt/copy logic.
- [ ] Test backward compatibility and persistence.

**Exit gate:** Old profiles load; new postal saves and reloads.  
**Suggested commit:** `feat(profile): persist home postal code`  
**Actual commit:** None.

## Step 6 — Event integration (shared files)
- [ ] Collect event destination postal code and start date/time.
- [ ] Preserve existing Gemini and recommendation workflow.
- [ ] Display route assessment beside AI recommendation.
- [ ] Agree on event record persistence.
- [ ] Run existing and new regression tests.

**Exit gate:** End-to-end demo works with no unrelated regressions.  
**Suggested commit:** `feat(eventwise): display transit assessment`  
**Actual commit:** None.

## Step 7 — Review and handoff
- [ ] Run full offline suite; record exact counts.
- [ ] Verify live API demo with authorised key.
- [ ] Check no `.env` or secrets in Git.
- [ ] Explain new classes for UML/report.
- [ ] Open PR only after approval.

**Suggested commit:** `test(geolocation): cover errors and regressions`  
**Actual commit:** None.

## Evidence log
| Date | Step | Tests/evidence | Commit | Status |
|---|---|---|---|---|
| 2026-11-10 | Planning | Source review and documents drafted | None | Drafted |
| 2026-11-10 | API feasibility | OneMap lookup matched both user-entered postal codes and returned a transit itinerary. `arriveBy=true` was ignored; the user accepted clearly labelled departure-based estimates. Google Geocoding denied because billing was not enabled; Google Routes not tested. Official OneMap API Terms of Service and Singapore Open Data Licence reviewed: datasets are royalty-free with attribution, but the reviewed pages do not confirm API-call pricing. Search API docs require a token and document HTTP 429 for API limits, without stating a numeric quota. No credentials or personal postal codes recorded. | None | Partial; confirm OneMap API pricing and applicable numeric limits |
| 2026-11-10 | Postal validation | `python -m unittest test_geolocation -v` — 4 passed; `python test_logic_manager.py` — 58 passed, 0 failed. Re-run after commit with same results. | `983ec9cb6bfd34d887591abfc75f537ee617108a` (committed 2026-11-10 19:44:28 +08:00) | Complete for format validation; existence lookup deferred to Step 3 |
| 2026-11-12 | Routing | `python -B -m unittest test_geolocation -v` — 25 passed; `python -B test_logic_manager.py` — 58 passed, 0 failed. All HTTP mocked; exact lookup, unit/time conversion, invalid data, auth/quota, timeout/network, no-route, unsupported-mode and privacy checks pass. Tests required approved execution outside the sandbox because the Windows Python launcher was inaccessible inside it. | None | Step 3 complete offline; uncommitted; live verification pending |
| TBD | Assessment | Not run | None | Not started |
| TBD | Integration | Not run | None | Not started |

## Prompt to resume work
Read `AI_Coding_Background.md`, `CODEBASE_MAP_GeoLocation.md`, `PRD_GeoLocation.md`, and this tracker. Compare progress with actual source and Git history. Propose the **next single unfinished milestone**, exact files and tests, then wait for approval. Do not check boxes or claim commits without evidence.
