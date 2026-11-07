# Changelog

## v1.0.0 — 2026-11-07

- **charity-compliance created** as the merged flagship
  ordered by FLEET-AUDIT-2026-11-04 (flagship B3): two
  shipped Canadian-charity checkers — receipt-gate and
  t3010-check — become modules of one "is this charity
  ready to file?" suite. They were always two halves of
  one job: receipt-gate's year-end register eligible
  total is the figure t3010-check ties the return's
  line 4500 back to — and nobody was installing both.
- **Engines ported byte-identical** from the source
  packs — receipt_gate.py and t3010_check.py, each at
  its source v0.1.0 state (t3010-check carries no
  version field, by its source design). No check,
  verdict, threshold, or honesty limit was changed;
  each module keeps its own CLI shape behind the suite
  command (`charity-compliance receipt-gate
  check|register|rules ...`, `charity-compliance
  t3010-check check|deadline|rules ...`), and
  receipt-gate still reports its own v0.1.0 inside its
  sections.
- **New: `filing-ready` subcommand** — runs both modules
  over one charity folder and prints a single readiness
  receipt. Input discovery is deterministic and
  documented: receipt-gate gets the first `.csv` whose
  header names both `serial_number` and `donor_name`;
  t3010-check gets the first `.json` return model
  (an object carrying `charity` or `financials`), or
  failing that the first `field,value` `.csv` — the
  JSON model is preferred, the CSV is the quick path.
  `--json` emits one object whose per-module sections
  are the exact objects the modules print standalone,
  plus their exit codes. A module with no qualifying
  input reports SKIPPED with a reason — never as
  passed — and **READY requires at least one module to
  have actually run and passed**, so an empty folder is
  NOT READY. Read-only: the folder is never written to.
- **One stage-1 fix, in the dispatcher only:** file
  discovery matched extensions case-sensitively, so a
  donations file named `DONATIONS.CSV` was silently
  skipped and its module reported SKIPPED instead of
  checking the charity's real records. Discovery is now
  case-insensitive. The engines are untouched — the fix
  is in how filing-ready finds their inputs, not in
  what they check.
- **Tests: 123.** The two source suites carried over
  (60 + 39 = 99 tests; the only edit is each suite's
  EXAMPLES path — examples now live per-module under
  `examples/<module>/`) plus 24 new dispatcher /
  filing-ready tests. The full suite also passes in a
  scratch copy with every file's executable bit
  stripped: the suites invoke engines through the
  Python interpreter and establish their own fixture
  permissions, and never depend on checkout modes,
  $HOME, or machine paths.
- **Examples:** the two tools' example files ported
  under `examples/<module>/`, plus
  `examples/make_fixture.py` — one fictional charity
  (Exampleton Community Food Bank, fiscal 2025) whose
  donations register eligible total (48,250.00) ties by
  construction to the return's line 4500 and
  `receipts.eligible_total`. The faulty folder plants
  exactly one fault per side: an in-kind receipt with
  its mandatory gift description removed
  (receipt-gate: `required_missing`, 1 error) and a
  T3010 total revenue that does not reconcile with its
  components (t3010-check: `total_mismatch` on line
  4700, 1 error).
- **Honesty, kept from both sources:** this is a
  filing-preparation aid, not tax advice. The receipt
  rules were checked 2026-11 against the CRA's
  published guidance for registered charities; the
  T3010 checks were checked 2026-11-04 against the
  T3010 (24) form, the T4033 guide and the CRA's own
  T3010 checklist — and every report carries those
  stamps. A PASS or READY means the data satisfies the
  checks encoded in the modules — never that the CRA
  will accept the receipts or the return. The suite
  handles no SINs and files nothing.
- **Name:** `charity-compliance` was free on PyPI
  (JSON API 404, checked 2026-11-07) and no repo of
  that name exists in the jasveerai88 GitHub account;
  the only GitHub name hit is an unrelated
  `charity-compliance-tracker`. First choice, taken.
