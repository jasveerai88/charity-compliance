---
name: charity-compliance
description: Pre-filing compliance check for a Canadian registered charity — validate the year's donation receipts against the CRA's encoded official-receipt requirements AND pre-flight the draft T3010 return (completeness, exact cross-footing including line 4500 vs the receipt-register total, filing deadline), separately or as one filing-ready run over a charity folder. Use before receipts are issued from a spreadsheet, when preparing or reviewing a T3010 draft, or when asked "is this charity ready to file?" The rules are ENCODED (receipt rules checked 2026-11; T3010 checks checked 2026-11-04) — a PASS or READY means the data satisfies the encoded checks, never that the CRA will accept the receipts or the return. A checking aid: files nothing, issues nothing, not tax advice.
---

# charity-compliance — agent skill

## Purpose

A small Canadian charity's year-end has two mechanical
failure points, and they connect: the donation receipts
it issued from a spreadsheet (a missing prescribed
element, split-receipting math that doesn't recompute, a
serial used twice — defects the CRA can revoke
registration over), and the T3010 return it files from
those figures (a required worksheet missing, totals that
don't cross-foot, line 4500 disagreeing with the receipt
register, a deadline quietly missed). This suite is the
two checkers as one tool: receipt-gate validates the
donations CSV and prints the year-end register whose
eligible total is the return's starting figure;
t3010-check pre-flights the return data, tying line 4500
back to that register total. `filing-ready` runs both
over one charity folder and prints a single readiness
receipt. Pure Python standard library; local only; reads
the files, writes nothing, sends donor data nowhere.

**The honesty core of this suite:** the requirements are
encoded data, checked 2026-11 (receipts) and 2026-11-04
(T3010), drawn from the CRA's published guidance, the
T3010 (24) form, the T4033 guide and the CRA's own T3010
checklist. Guidance changes. A PASS / READY means the
data satisfies the rules *encoded in these modules* —
never present it as CRA acceptance or compliance, never
call the suite tax advice, and never say it issues
receipts or files returns. It checks; humans issue and
file.

## When to use / not use

Use when:
- A charity is about to issue official donation receipts
  from a spreadsheet: run `receipt-gate check` first and
  fix every error in the sheet, not after mailing.
- A T3010 draft exists as figures (spreadsheet, export,
  preparer's worksheet): run `t3010-check check` for the
  mechanical pass before human review.
- The question is the whole folder — "are we ready to
  file?": run `filing-ready` and report both sections.
- A receipting file needs its year-end register, or an
  agent needs the encoded requirements themselves:
  `receipt-gate register`, either module's `rules`.

Do NOT use when:
- The question is whether the CRA *will* accept a
  receipt or a return — that depends on current CRA
  guidance and facts about the gifts this suite cannot
  see. PASS is a mechanical pre-flight, nothing more.
- Issuing receipts or filing the return — the suite
  generates neither; it validates the data behind both.
- Tax advice — whether a transfer is a gift, what an
  advantage is worth, whether an appraisal was adequate
  are questions for the charity's advisors.
- The donations file mixes several charities or several
  receipt books — receipt-gate's consistency and serial
  checks assume one charity, one book; split it first.

## Commands

```bash
# One readiness receipt over a charity folder
charity-compliance filing-ready CHARITY_DIR [--year 2026] [--as-of 2026-12-31] [--json]

# The modules on their own
charity-compliance receipt-gate check DONATIONS.csv [--year YYYY] [--as-of YYYY-MM-DD] [--json]
charity-compliance receipt-gate register DONATIONS.csv [--year YYYY] [--json]
charity-compliance receipt-gate rules [--json]
charity-compliance t3010-check check RETURN.json|RETURN.csv [--as-of YYYY-MM-DD] [--json]
charity-compliance t3010-check deadline --year-end YYYY-MM-DD [--as-of YYYY-MM-DD] [--filed YYYY-MM-DD] [--json]
charity-compliance t3010-check rules [--json]
```

(From a source checkout, prefix with
`python3 src/charity_compliance.py`. Suite version
1.0.0; receipt-gate still reports its own source-tool
version, v0.1.0, inside its sections and JSON —
t3010-check carries no version field, by its source
design.)

Every command accepts `--json` and prints exactly one
JSON object. Input and usage errors — argparse included
— print `{"error": "..."}` and exit 2, never a
traceback. Exit codes: **0** pass, **1** findings,
**2** usage/input error.

## filing-ready: discovery and skip honesty

Pointed at a folder, filing-ready discovers its inputs
deterministically (recursive, sorted order, `.git` never
entered):

- **receipt-gate** gets the first `.csv` whose header
  names both `serial_number` and `donor_name` (the
  receipt columns). The T3010 `field,value` CSVs never
  qualify.
- **t3010-check** gets the first `.json` that parses to
  an object carrying `charity` or `financials` (the
  return model); failing that, the first `.csv` in the
  `field,value` quick-path shape.

A module with no qualifying input reports
`status: "skipped"` with the reason and `clean: null` —
**skipped is never passed**. The combined verdict is
READY only when at least one module ran and every module
that ran passed; an empty folder is NOT READY, not
quietly clean. `--year` passes to receipt-gate only;
`--as-of` passes to both — without it, t3010-check
computes its deadline status against today (its own
standalone behaviour), while receipt-gate never reads
the clock at all.

## What each module decides

| Module | Verdict | Clean means |
|---|---|---|
| receipt-gate `check` | PASS / FAIL with per-row findings (`rule`, `severity`, `measured` vs `limit`) | no errors against the 13 encoded receipt elements: statement, charity name/address, registration number (9 digits + RR + 4) and consistency, serial unique + gap-checked, place issued, both dates in order, donor name/address, gift amount, in-kind description + appraiser, advantage amount/description, eligible = amount − advantage recomputed to the cent, canada.ca/charities-giving. The 80% advantage rule is an ERROR (not a gift — no receipt may be issued); over 10% is a WARNING (intention questioned); in-kind over $1,000 without an appraiser is a WARNING (guidance). |
| t3010-check `check` | PASS / FAIL with grouped ERROR / WARNING / INFO findings | the draft satisfies the encoded completeness checks (required lines, worksheets T1235/T1236/T1441, schedules 1/2/3/4/5 as triggered, financial statements, signed certification), every modelled cross-foot is exact (totals vs components, line 4500 vs the supplied register eligible total, return vs statement totals), and the deadline (fiscal year-end + 6 months, ITA s. 149.1(14)) is met. Judgement-shaped triggers (Schedule 8, T2081, non-arm's-length compensation) are WARNING prompts, never determinations. |

## JSON contract

Module commands emit exactly the object their standalone
tool emits. `receipt-gate check` carries `verdict`,
`findings` (row, serial, field, rule, severity, measured,
limit, message), `summary` (errors / warnings / by_rule),
`rules_note` and `disclaimer`; `register` carries
`entries`, `excluded`, `totals`, `by_donor`.
`t3010-check check` carries `charity`, `deadline`
(due date, rule, status), `summary` (errors / warnings /
info), `verdict`, `findings` (section, field, rule,
severity, measured, limit, message), `rules_checked`,
`sources` and `disclaimer`.

`filing-ready --json` emits one object: `tool:
"charity-compliance"`, `command: "filing-ready"`, `dir`,
`inputs` (the discovered path per module, or null),
`modules` (per-module sections — each module's own
object plus its `exit_code`; skipped modules carry
`status: "skipped"`, a `reason`, `clean: null`),
`summary` (modules run / skipped / passed / with
findings), `ready`, `verdict` (READY / NOT READY), and
the suite `disclaimer`.

## Limits & honesty rules the agent must respect

- **Never present PASS or READY as CRA acceptance or
  compliance.** The encoded rules were checked 2026-11 /
  2026-11-04 against published sources; the CRA's
  current guidance governs. Always carry the rules
  stamps and the disclaimer when reporting results.
- **Never call the suite tax advice, a receipt issuer,
  or a filer.** It checks spreadsheets and return data;
  it issues nothing and files nothing.
- **Errors are not suggestions; warnings are not
  failures.** An error means the receipt would be
  invalid or must not be issued, or the return data is
  incomplete or self-contradictory; a warning means a
  human should look before issuing or filing. Report
  both counts, by rule, with the field names and both
  numbers wherever arithmetic disagrees.
- **Do not soften the 80% rule.** An advantage over 80%
  of the gift means the transfer is not a gift — no
  receipt may be issued. Thresholds are the encoded
  rules with their basis (80% not-a-gift, 10% intention,
  $1,000 appraisal guidance) — state them as such, not
  as the suite's opinion.
- **A skipped module is not evidence.** filing-ready
  with only one side checked says so in its verdict
  line; never relay a one-sided READY as a whole-folder
  verdict without naming what was skipped.
- **No clock games, no network.** receipt-gate never
  reads the machine clock (future checks need
  `--as-of`); t3010-check reads it only for the deadline
  status when `--as-of` is absent — pin `--as-of` when
  a reproducible receipt matters. Donor data never
  leaves the machine: do not pipe any input to an
  external service to "double-check".
