# GeoLocation — Project Plan & Progress Tracker

**Baseline:** `oop_andrew` commit `2a08f807248949501946d2dc00a29ad960971e2b`  
**Created:** 10 November 2026  
**Status:** Steps 2–4 are committed. Step 5 profile integration is implemented and verified offline, with changes ready for review. The user's manual live test successfully retrieved a route and produced a travel assessment. Automatic routing at the recommended departure and the full application travel display remain Step 6 work. OneMap API pricing and numeric usage limits remain unconfirmed.

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
**Actual commit:** `f12bf9494da7df68e92a924b55f8dfcb469fd319` (`feat(geolocation): implement public transit routing`). Verified from local Git history.

**Implementation:** `src/geolocation.py` now contains `GeoLocationService`, `TransitRoute`, and `GeoLocationError`. The service reads `ONEMAP_ACCESS_TOKEN` when no token is supplied and accepts an injectable HTTP opener for offline tests. It requires a timezone-aware departure, resolves exact postal matches, requests public transport, validates all leg distances, and converts units and itinerary timestamps. Missing data is an explicit failure, never a fabricated zero. Provider errors use safe messages and stable codes; tests verify silent operation and suppression of sensitive HTTP exception context. HTTP-200 provider errors are classified using known message patterns; unfamiliar errors remain `PROVIDER_ERROR`.

The Step 3 service returns `TransitRoute`. Step 4 adds `TravelAssessment` and departure calculations. A user-supplied screenshot now records a successful manual live service test. A route recheck at the calculated departure remains part of application integration.

## Step 4 — Departure and feasibility
- [x] Add travel assessment result.
- [x] Compute leave time with configurable arrival buffer.
- [x] Handle Singapore timezone and previous-day departures.
- [x] Evaluate within-limit, long-journey and unavailable cases.
- [x] Test thresholds and midnight boundaries.

**Exit gate:** `python -B -m unittest test_travel_assessment test_geolocation -v` passed all 44 tests, including 19 assessment tests and 25 GeoLocation tests. `python -B test_logic_manager.py` passed all 58 tests with 0 failures. Verified 12 November 2026 using the installed Python 3.14 executable.
**Suggested commit:** `feat(geolocation): calculate departure and feasibility`  
**Actual commit:** `ecd57beff7fe74c6e3604965dd7e223fbdcca6bb` (`refactor(geolocation): simplify code for readability`) includes Step 4 and the approved readability revision. Verified from local Git history.

`src/travel_assessment.py` contains `TravelAssessment` and `TravelEvaluator`. The user approved defaults of 15 minutes for the arrival buffer and 60 minutes for the preferred journey limit. `evaluate(event_start, route)` calculates the recommended departure and compares duration with the configured limit. Passing `None` for the route produces `UNAVAILABLE`, with journey values set to `None`. Invalid caller inputs raise `ValidationError`.

The tests cover the PRD's 09:00 event and 32-minute journey giving 08:13 departure, midnight/year/leap-day boundaries, timezone conversion, fractional minutes, threshold equality, configurable settings, unavailable routes and invalid inputs. The estimated arrival retains the supplied itinerary's time. A fresh route request at the recommended departure and a check against the target arrival buffer belong to the later application integration. Journey feasibility here describes the duration relative to the preferred limit. Live arrival verification remains pending.

## Step 5 — Student profile integration (shared files)
- [x] Add optional `home_postal_code` to `StudentProfile`.
- [x] Update `to_dict`/`from_dict` and profile prompt/copy logic.
- [x] Test backward compatibility and persistence.

**Exit gate:** Older profiles load and postal strings survive JSON save/reload. `python -B -m unittest test_profile_geolocation test_travel_assessment test_geolocation -v` passed 68 tests, including 24 new profile/editor/application tests. `python -B test_logic_manager.py` passed 58 tests with 0 failures. Used the installed Python 3.14 executable directly, verified 12 November 2026.
**Suggested commit:** `feat(profile): persist home postal code`  
**Actual commit:** None.

`StudentProfile` accepts an optional third constructor argument, `home_postal_code`. An empty string represents an unset postal, and loading `None` normalises to an empty string. Nonempty values use the existing six-digit validator. The profile editor supports adding, changing and clearing the postal, and cancellation preserves the original profile. Existing field-of-study and interest requirements still apply. The existing application saves the updated profile through its normal exit flow.

The user specifically approved a small additional `main.py` edit after inspection showed the whole saved profile was passed to Gemini. Event analysis now passes field of study and interests explicitly. The profile tests check the exact AIManager call as well as profile editing and saving through EventWiseApp. JSON tests use temporary directories and fake postal codes. Team coordination remains open.

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
| 2026-11-12 | Routing | `python -B -m unittest test_geolocation -v` — 25 passed; `python -B test_logic_manager.py` — 58 passed, 0 failed. All HTTP mocked; exact lookup, unit/time conversion, invalid data, auth/quota, timeout/network, no-route, unsupported-mode and privacy checks pass. Tests required approved execution outside the sandbox because the Windows Python launcher was inaccessible inside it. | `f12bf9494da7df68e92a924b55f8dfcb469fd319` | Step 3 complete offline and committed. Live verification pending. |
| 2026-11-12 | Assessment | `python -B -m unittest test_travel_assessment test_geolocation -v` — 44 passed (19 assessment and 25 GeoLocation). `python -B test_logic_manager.py` — 58 passed, 0 failed. Used `C:/Users/user/AppData/Local/Python/pythoncore-3.14-64/python.exe` directly with bytecode writing disabled. | None | Step 4 complete offline. Changes ready for review. |
| 2026-11-12 | Approved readability revision | Replaced dataclass constructors with explicit `__init__` methods. Expanded conditional expressions, generator expressions, validation checks and test setup. Added names showing seconds, milliseconds and metres, plus focused method explanations. Reran `python -B -m unittest test_travel_assessment test_geolocation -v` — 44 passed. `python -B test_logic_manager.py` — 58 passed, 0 failed. Used the installed Python 3.14 executable directly. | None | Readability revision verified offline. Changes ready for review. |
| 2026-11-12 | Step 4 commit verification | Local Git history confirms that the readability commit contains `src/travel_assessment.py` and its tests. | `ecd57beff7fe74c6e3604965dd7e223fbdcca6bb` | Step 4 and readability revision committed. |
| 2026-11-12 | User manual live test | User-supplied terminal screenshot shows a OneMap route of 32.48693 km and 88.7167 minutes, recommended departure 13:16:17 for a 15:00 event, and `LONG_JOURNEY`. Returned arrival 13:30:08 belongs to the entered 12:00 departure. Credentials and postal codes were hidden. | Existing service | Successful manual route/assessment test. Recheck at recommended departure remains pending. |
| 2026-11-12 | Profile integration | `python -B -m unittest test_profile_geolocation test_travel_assessment test_geolocation -v` — 68 passed (24 profile and 44 existing travel tests). `python -B test_logic_manager.py` — 58 passed, 0 failed. Covers old profiles, leading zeroes, validation, JSON round trip, copying, save/clear/cancel editing, app profile save and the exact AI profile input. | None | Step 5 verified offline. Changes ready for review. |
| TBD | Integration | Not run | None | Not started |

## Prompt to resume work
Read `AI_Coding_Background.md`, `CODEBASE_MAP_GeoLocation.md`, `PRD_GeoLocation.md`, and this tracker. Compare progress with actual source and Git history. Propose the **next single unfinished milestone**, exact files and tests, then wait for approval. Do not check boxes or claim commits without evidence.
