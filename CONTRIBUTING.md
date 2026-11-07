# Contributing

Thanks for looking. charity-compliance is a merged
suite: two checkers with deliberately separate scopes,
one dispatcher. Contributions that keep each module's
scope sharp — and the merge honest — are welcome.

## Ground rules

- **Standard library only.** No third-party
  dependencies, no network calls, ever — in either
  module or in the dispatcher. The suite's promise is
  "clone and run" on a charity's own machine.
- **The engines are ported, not rewritten.** Each
  module's checks, verdict words, thresholds, and
  honesty limits are its source tool's contract. A
  behaviour change to a module belongs upstream in that
  module's own test suite first: its ported suite here
  must keep passing, and any intentional divergence
  must be named in CHANGELOG.md, never silent.
- **Encoded rules carry their check dates.** The
  receipt rules are stamped "checked 2026-11" and the
  T3010 checks "checked 2026-11-04". A rule change
  without a fresh check against the CRA's published
  sources — and a new stamp — is not a contribution,
  it's a rumour.
- **Deterministic, always.** No LLM, no randomness:
  the same inputs must produce a byte-identical report
  on every run. receipt-gate never reads the machine
  clock; anything date-sensitive takes an explicit
  `--as-of`.
- **Read-only, always.** No command may write to the
  files it checks. Tests prove fixture trees are
  byte-identical after a filing-ready run; keep them
  passing.
- **Skipped is not clean.** A module with nothing to
  check reports itself skipped with a reason. Never let
  the combined verdict count a skipped module as
  evidence of readiness.
- **No tracebacks, ever.** Bad input is a clean
  `{"error": ...}` with exit 2 — including argument
  errors in `--json` mode, at dispatcher and module
  level alike.
- **Fixtures stay fictional.** Test charities, donors
  and figures are invented; never commit a real
  charity's data.

## Running the tests

```bash
python3 -m unittest discover -s tests
```

All 123 tests must pass on a clean checkout with
nothing but Python 3.10+ — including in a copy with
every file's executable bit stripped (the suites invoke
engines through the Python interpreter and set any
fixture permissions themselves). The two module suites
live in `tests/test_receipt_gate.py` and
`tests/test_t3010_check.py`; dispatcher and
filing-ready tests in `tests/test_charity_compliance.py`.
