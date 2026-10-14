# Agent B notes — Round 3 follow-up engine

## G1 (evaluator + fixtures)
- `followup/policy.py::evaluate(ctx, policy, now)`: pure. It imports only `followup/windows.py` (calendar math) and
  the contract. The tier order and its two documented exceptions are in the module docstring:
  - a customer callback replaces grace, the configured spacing and the per-case daily cap;
  - a manual call skips grace and turns every deferral into a BLOCK.
- `followup/windows.py`: Asia/Jerusalem windows, holidays and DST, with the envelope applied on top. `clock.py`
  re-exports it.
- `backend/policy/scenarios/*.json`: 39 fixtures, one per decision scenario in 03 §5 (S01–S18, S20–S28, S33–S37)
  plus variants (`S06-gate`, `S10-no-redial`, `S11-shabbat`, `S11-holiday`, `S11-dst`, `S12-unverified`,
  `S24-allowed`). The 24 fixtures under S01–S18 are `mandatory`. Expectations were written by hand from 03 §5.
  `now` is Tuesday 2026-10-13 11:00 Israel time unless stated.
- **Additive contract changes** (`followup/contract.py`; nothing renamed or removed):
  - `FollowupContext.live_sessions: int = 0`: live sessions. ACTIVE with ≥2 means "active on another device" (S17
    SUPPRESS vs S03 WAIT).
  - `FollowupContext.manual: bool = False`: a banker's call-now request (S24).
  - Rule `OP-CALL-IN-PROGRESS` (OPERATIONAL): an earlier attempt is still queued, dialling or connected, so there is
    no second contact (S10).
  - `contract.merge_overrides(config, overrides)`: the deep merge for `policy_overrides`. Dicts merge; lists and
    scalars replace. **Agent C: the simulator should use this** so fixture results match `test_followup_policy.py`.
- Simulator recipe (what the test does):
  `schema.parse("loan_policy", merge_overrides(config, s.policy_overrides))`, where a `ValidationError` means
  `policy=None`, then `evaluate(s.context, policy, s.now)`, then `contract.matches(s.expect, d)`.

## Open questions
- `APP_ENV` (read by `clock.environment()`, default `demo`) is not in `config.py`. At G5, decide whether it moves
  into `Settings`.
