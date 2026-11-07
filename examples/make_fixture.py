#!/usr/bin/env python3
"""Build the charity-compliance example fixtures.

Two folders for one fictional charity — the Exampleton
Community Food Bank, registration 123456789RR0001, fiscal
year 2025 — in the shapes charity-compliance filing-ready
discovers: a donations CSV (receipt-gate's input) and a
T3010 return model (t3010-check's input, copied from the
ported examples/t3010-check/clean-return.json).

The two sides TIE BY CONSTRUCTION: the donations register
totals are amount 48,500.00 / advantage 250.00 / eligible
48,250.00 (added by hand from the rows below), and the
return's line 4500 and receipts.eligible_total are both
48,250 — so a human can run receipt-gate's register on the
donations and feed its eligible total into the return,
exactly the hand-off the two source tools document.

build_clean(root) — everything checks out:
  donations.csv   4 rows, serials 101-104, every
                  prescribed element present
  return.json     the clean return (0 errors, 0 warnings,
                  1 info — the deadline note)

build_faulty(root) — ONE planted fault per side:
  donations.csv   row 104 is a gift in kind with its
                  gift_description REMOVED — a receipt
                  missing a mandatory element
                  (receipt-gate: required_missing, 1
                  error, 0 warnings)
  return.json     line 4700 (total revenue) reads 74,800
                  while its components still add to 74,700
                  (4500 48,250 + 4510 5,000 + 4530 3,200 +
                  4570 12,000 + 4630 4,500 + 4640 1,500 +
                  4650 250 = 74,700); the financial
                  statements carry the same wrong 74,800,
                  so the return disagrees only with
                  itself (t3010-check: total_mismatch, 1
                  error, 0 warnings, 1 info)

Usage:
    python3 examples/make_fixture.py TARGET [--clean]
"""

import csv
import io
import json
import sys
from pathlib import Path

EXAMPLES = Path(__file__).resolve().parent

HEADER = [
    "serial_number", "charity_name", "charity_address",
    "registration_number", "place_issued",
    "official_statement", "cra_website", "donor_name",
    "donor_address", "donation_date", "receipt_date",
    "gift_type", "amount", "advantage_amount",
    "advantage_description", "eligible_amount",
    "gift_description", "appraiser_name", "appraiser_address",
]

_CHARITY = "Exampleton Community Food Bank"
_ADDRESS = "123 Example Street, Kelowna, BC V1Y 0A0"
_REG = "123456789RR0001"
_PLACE = "Kelowna, BC"
_STATEMENT = "Official receipt for income tax purposes"
_SITE = "canada.ca/charities-giving"


def _row(serial, donor, donor_addr, ddate, rdate, gtype,
         amount, adv, adv_desc, eligible, gift_desc="",
         appraiser="", appraiser_addr=""):
    return [serial, _CHARITY, _ADDRESS, _REG, _PLACE,
            _STATEMENT, _SITE, donor, donor_addr, ddate,
            rdate, gtype, amount, adv, adv_desc, eligible,
            gift_desc, appraiser, appraiser_addr]


def _donations_rows(faulty):
    rows = [
        _row("101", "Nadia Rahman",
             "45 Maple Crescent, Kelowna, BC V1Y 3B2",
             "2025-02-10", "2025-02-15", "cash",
             "20000.00", "", "", "20000.00"),
        _row("102", "Omar Haddad",
             "12 Vineyard Row, Kelowna, BC V1Y 4C9",
             "2025-05-01", "2025-05-06", "cash",
             "10000.00", "250.00", "Charity gala dinner",
             "9750.00"),
        _row("103", "Sofia Almeida",
             "18 Orchard View, Kelowna, BC V1Y 3K8",
             "2025-09-12", "2025-09-15", "cash",
             "15000.00", "", "", "15000.00"),
        _row("104", "Peter Novak",
             "92 Vinewood Terrace, Kelowna, BC V1Y 4L2",
             "2025-11-03", "2025-11-08", "in_kind",
             "3500.00", "", "", "3500.00",
             gift_desc="" if faulty else
             "Commercial food warmer, used, working order",
             appraiser="Linda Cho",
             appraiser_addr="88 Appraisal Lane, Vernon, "
                            "BC V1T 1A1"),
    ]
    return rows


def _donations_csv(faulty):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(HEADER)
    w.writerows(_donations_rows(faulty))
    return buf.getvalue()


def _return_data(faulty):
    data = json.loads(
        (EXAMPLES / "t3010-check" / "clean-return.json")
        .read_text(encoding="utf-8"))
    if faulty:
        # The one plant: the stated total revenue no
        # longer reconciles with its own components
        # (74,700). The financial statements carry the
        # same wrong figure, so nothing else fires.
        data["financials"]["lines"]["4700"] = 74800
        data["financial_statements"]["total_revenue"] = 74800
    return data


def _build(root, faulty):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "donations.csv").write_text(
        _donations_csv(faulty), encoding="utf-8")
    (root / "return.json").write_text(
        json.dumps(_return_data(faulty), indent=2) + "\n",
        encoding="utf-8")
    return root


def build_faulty(root):
    """The faulty charity folder: one planted fault per
    side (see module docstring)."""
    return _build(root, faulty=True)


def build_clean(root):
    """The clean charity folder: both modules pass."""
    return _build(root, faulty=False)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    clean = "--clean" in argv
    args = [a for a in argv if a != "--clean"]
    if len(args) != 1:
        print("usage: make_fixture.py TARGET [--clean]")
        return 2
    root = build_clean(args[0]) if clean \
        else build_faulty(args[0])
    print(f"fixture written to {root} "
          f"({'clean' if clean else 'faulty'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
