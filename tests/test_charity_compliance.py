#!/usr/bin/env python3
"""Tests for the charity-compliance dispatcher and the
combined filing-ready run. Stdlib unittest only, temp
dirs only.

Run from the pack root:
    python3 -m unittest discover -s tests -v

The two module engines carry their own ported suites
(test_receipt_gate.py, test_t3010_check.py — the source
tools' suites, unchanged except each suite's EXAMPLES
path). This file tests only what is new: routing, the
JSON/error contract at the suite level, filing-ready's
discovery, skip honesty and verdict math, read-only
behaviour, and determinism.

The fixtures are built by examples/make_fixture.py.
Every expectation is stated from the fixture's
construction (see that file's docstring), not copied
from the tool's output: the faulty folder plants exactly
one fault per side (a gift in kind with its mandatory
description removed -> receipt-gate required_missing,
1 error 0 warnings; a T3010 total revenue of 74,800
against components of 74,700 -> t3010-check
total_mismatch, 1 error 0 warnings 1 info), and the
clean folder ties by construction — the donations
register's eligible total (48,500.00 - 250.00 =
48,250.00, added by hand) is the return's line 4500 and
receipts.eligible_total.
"""

import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parent.parent
SRC = PACK_ROOT / "src"
EXAMPLES = PACK_ROOT / "examples"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(EXAMPLES))

import charity_compliance as cc  # noqa: E402
import make_fixture  # noqa: E402
import receipt_gate  # noqa: E402
import t3010_check  # noqa: E402

AS_OF = "2026-04-01"


def run_cli(argv):
    """Run the dispatcher in-process; return
    (exit_code, stdout_text)."""
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            code = cc.main(argv)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 2
    return code, buf.getvalue()


def run_module_json(module_main, args):
    """Run a module's own CLI in --json mode in-process;
    return (exit_code, parsed_object)."""
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            code = module_main(args)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 2
    return code, json.loads(buf.getvalue())


def tree_hashes(root):
    out = {}
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            out[str(p.relative_to(root))] = hashlib.sha256(
                p.read_bytes()).hexdigest()
    return out


class FixtureCase(unittest.TestCase):
    """Base: fresh faulty + clean fixture folders."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.faulty = make_fixture.build_faulty(
            base / "faulty")
        self.clean = make_fixture.build_clean(base / "clean")

    def tearDown(self):
        self._tmp.cleanup()


class DelegationTests(FixtureCase):

    def test_receipt_gate_routes(self):
        code, out = run_cli(
            ["receipt-gate", "check",
             str(self.clean / "donations.csv")])
        self.assertEqual(code, 0)
        self.assertIn("receipt-gate v", out)

    def test_receipt_gate_register_ties_to_return(self):
        # The hand-off the two source tools document: the
        # register's eligible total is the return's
        # receipts.eligible_total / line 4500 figure.
        code, payload = run_module_json(
            receipt_gate.main,
            ["register", str(self.clean / "donations.csv"),
             "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(payload["totals"]["eligible"],
                         "48250.00")
        ret = json.loads(
            (self.clean / "return.json").read_text())
        self.assertEqual(ret["receipts"]["eligible_total"],
                         "48250.00")
        self.assertEqual(
            ret["financials"]["lines"]["4500"], 48250)

    def test_t3010_check_routes(self):
        code, out = run_cli(
            ["t3010-check", "deadline",
             "--year-end", "2025-12-31"])
        self.assertEqual(code, 0)
        self.assertIn("2025-12-31 + 6 months = due "
                      "2026-06-30", out)

    def test_module_help_delegates(self):
        code, out = run_cli(["receipt-gate", "--help"])
        self.assertEqual(code, 0)
        self.assertIn("check", out)

    def test_version_and_bare_help(self):
        code, out = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("charity-compliance v1.0.0", out)
        code, out = run_cli([])
        self.assertEqual(code, 0)
        self.assertIn("filing-ready", out)

    def test_unknown_command_json_error(self):
        code, out = run_cli(["bogus", "--json"])
        self.assertEqual(code, 2)
        self.assertIn("error", json.loads(out))


class FilingReadyFaultyTests(FixtureCase):

    def test_text_run_catches_both_plants(self):
        code, out = run_cli(
            ["filing-ready", str(self.faulty),
             "--as-of", AS_OF])
        self.assertEqual(code, 1)
        self.assertIn("required_missing", out)
        self.assertIn("total_mismatch", out)
        self.assertIn("VERDICT: NOT READY", out)

    def test_json_sections_are_module_verbatim(self):
        code, out = run_cli(
            ["filing-ready", str(self.faulty),
             "--as-of", AS_OF, "--json"])
        self.assertEqual(code, 1)
        payload = json.loads(out)
        self.assertEqual(payload["tool"],
                         "charity-compliance")
        self.assertEqual(payload["command"], "filing-ready")
        self.assertFalse(payload["ready"])
        self.assertEqual(payload["verdict"], "NOT READY")
        self.assertEqual(
            payload["summary"],
            {"modules_run": 2, "modules_skipped": 0,
             "clean_modules": 0, "finding_modules": 2,
             "skipped": []})
        # Each section is the module's own object plus
        # exit_code — same keys, same verdict, same counts
        # as running the module standalone.
        for name, module_main, args in (
                ("receipt-gate", receipt_gate.main,
                 ["check", str(self.faulty / "donations.csv"),
                  "--json"]),
                ("t3010-check", t3010_check.main,
                 ["check", str(self.faulty / "return.json"),
                  "--as-of", AS_OF, "--json"])):
            mcode, mobj = run_module_json(module_main, args)
            section = payload["modules"][name]
            self.assertEqual(section["exit_code"], mcode)
            self.assertEqual(mcode, 1)
            self.assertEqual(
                set(section) - {"exit_code"}, set(mobj))
            self.assertEqual(section["verdict"],
                             mobj["verdict"])
            self.assertEqual(section["summary"],
                             mobj["summary"])

    def test_read_only(self):
        before = tree_hashes(self.faulty)
        run_cli(["filing-ready", str(self.faulty),
                 "--as-of", AS_OF])
        run_cli(["filing-ready", str(self.faulty),
                 "--as-of", AS_OF, "--json"])
        self.assertEqual(tree_hashes(self.faulty), before)

    def test_json_deterministic(self):
        _, out1 = run_cli(
            ["filing-ready", str(self.faulty),
             "--as-of", AS_OF, "--json"])
        _, out2 = run_cli(
            ["filing-ready", str(self.faulty),
             "--as-of", AS_OF, "--json"])
        self.assertEqual(out1, out2)


class FilingReadyCleanTests(FixtureCase):

    def test_clean_folder_is_ready(self):
        code, out = run_cli(
            ["filing-ready", str(self.clean),
             "--as-of", AS_OF, "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertTrue(payload["ready"])
        self.assertEqual(payload["verdict"], "READY")
        self.assertEqual(
            payload["modules"]["receipt-gate"]["verdict"],
            "PASS")
        self.assertEqual(
            payload["modules"]["t3010-check"]["verdict"],
            "PASS")
        self.assertEqual(payload["summary"]["clean_modules"],
                         2)

    def test_clean_text_verdict_carries_limits(self):
        code, out = run_cli(
            ["filing-ready", str(self.clean),
             "--as-of", AS_OF])
        self.assertEqual(code, 0)
        self.assertIn("VERDICT: READY", out)
        self.assertIn("never a statement that the CRA "
                      "will accept", out)
        self.assertIn("not tax advice", out)


class SkipAndDiscoveryTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _folder(self, name):
        d = self.base / name
        d.mkdir()
        return d

    def test_donations_only_skips_t3010(self):
        src = make_fixture.build_clean(self.base / "src1")
        d = self._folder("donations-only")
        (d / "donations.csv").write_bytes(
            (src / "donations.csv").read_bytes())
        code, out = run_cli(
            ["filing-ready", str(d), "--as-of", AS_OF,
             "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        section = payload["modules"]["t3010-check"]
        self.assertEqual(section["status"], "skipped")
        self.assertIsNone(section["clean"])
        self.assertIsNone(section["exit_code"])
        self.assertIn("no T3010 input", section["reason"])
        self.assertEqual(payload["summary"]["skipped"],
                         ["t3010-check"])
        self.assertTrue(payload["ready"])

    def test_return_only_skips_receipt_gate(self):
        src = make_fixture.build_clean(self.base / "src2")
        d = self._folder("return-only")
        (d / "return.json").write_bytes(
            (src / "return.json").read_bytes())
        code, out = run_cli(
            ["filing-ready", str(d), "--as-of", AS_OF,
             "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(
            payload["modules"]["receipt-gate"]["status"],
            "skipped")
        self.assertTrue(payload["ready"])

    def test_empty_folder_is_not_ready(self):
        d = self._folder("empty")
        code, out = run_cli(
            ["filing-ready", str(d), "--json"])
        self.assertEqual(code, 1)
        payload = json.loads(out)
        self.assertFalse(payload["ready"])
        self.assertEqual(payload["summary"]["modules_run"],
                         0)
        self.assertEqual(payload["summary"]["modules_skipped"],
                         2)

    def test_inputs_found_in_subfolders(self):
        src = make_fixture.build_clean(self.base / "src3")
        d = self._folder("nested")
        (d / "receipts").mkdir()
        (d / "filing").mkdir()
        (d / "receipts" / "donations.csv").write_bytes(
            (src / "donations.csv").read_bytes())
        (d / "filing" / "return.json").write_bytes(
            (src / "return.json").read_bytes())
        code, out = run_cli(
            ["filing-ready", str(d), "--as-of", AS_OF,
             "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["summary"]["modules_run"], 2)
        self.assertTrue(payload["ready"])

    def test_t3010_csv_not_mistaken_for_donations(self):
        # The T3010 field,value CSV must feed t3010-check
        # (its quick path), never receipt-gate.
        d = self._folder("csv-return")
        (d / "return.csv").write_bytes(
            (EXAMPLES / "t3010-check" / "clean-return.csv")
            .read_bytes())
        code, out = run_cli(
            ["filing-ready", str(d), "--as-of", AS_OF,
             "--json"])
        payload = json.loads(out)
        self.assertEqual(
            payload["modules"]["receipt-gate"]["status"],
            "skipped")
        self.assertEqual(
            payload["modules"]["t3010-check"]["verdict"],
            "PASS")
        self.assertEqual(code, 0)

    def test_unrelated_json_is_not_a_return(self):
        d = self._folder("stray-json")
        (d / "notes.json").write_text('{"foo": 1}')
        code, out = run_cli(
            ["filing-ready", str(d), "--json"])
        payload = json.loads(out)
        self.assertEqual(
            payload["modules"]["t3010-check"]["status"],
            "skipped")
        self.assertEqual(code, 1)

    def test_missing_folder_is_input_error(self):
        code, out = run_cli(
            ["filing-ready", str(self.base / "nope"),
             "--json"])
        self.assertEqual(code, 2)
        self.assertIn("error", json.loads(out))

    def test_file_not_folder_is_input_error(self):
        f = self.base / "a-file"
        f.write_text("x")
        code, out = run_cli(["filing-ready", str(f)])
        self.assertEqual(code, 2)
        self.assertIn("ERROR", out)

    def test_filing_ready_argparse_error_is_json(self):
        code, out = run_cli(["filing-ready", "--json"])
        self.assertEqual(code, 2)
        self.assertIn("error", json.loads(out))

    def test_uppercase_extensions_are_discovered(self):
        # A charity's DONATIONS.CSV / RETURN.JSON are its
        # inputs whatever case the export used.
        src = make_fixture.build_clean(self.base / "src4")
        d = self._folder("upper")
        (d / "DONATIONS.CSV").write_bytes(
            (src / "donations.csv").read_bytes())
        (d / "RETURN.JSON").write_bytes(
            (src / "return.json").read_bytes())
        code, out = run_cli(
            ["filing-ready", str(d), "--as-of", AS_OF,
             "--json"])
        payload = json.loads(out)
        self.assertEqual(payload["summary"]["modules_run"], 2)
        self.assertEqual(code, 0)
        self.assertTrue(payload["ready"])

    def test_malformed_donations_is_error_section(self):
        # Header names the two discovery columns but the
        # rest are missing: receipt-gate's own {"error"}
        # object becomes the section (exit_code 2) — the
        # combined run reports it, never crashes, and an
        # errored module is not clean.
        d = self._folder("broken")
        (d / "donations.csv").write_text(
            "serial_number,donor_name\nonly,two\n")
        code, out = run_cli(
            ["filing-ready", str(d), "--json"])
        payload = json.loads(out)
        section = payload["modules"]["receipt-gate"]
        self.assertIn("error", section)
        self.assertEqual(section["exit_code"], 2)
        self.assertEqual(payload["verdict"], "NOT READY")
        self.assertEqual(code, 1)

    def test_year_passthrough_warns_but_passes(self):
        # --year reaches receipt-gate: the clean fixture's
        # four 2025 donations under --year 2024 draw four
        # donation_year_mismatch warnings, no errors, and
        # the module still PASSes.
        src = make_fixture.build_clean(self.base / "src5")
        code, out = run_cli(
            ["filing-ready", str(src), "--year", "2024",
             "--as-of", AS_OF, "--json"])
        payload = json.loads(out)
        section = payload["modules"]["receipt-gate"]
        self.assertEqual(section["verdict"], "PASS")
        self.assertEqual(section["summary"]["warnings"], 4)
        self.assertEqual(
            section["summary"]["by_rule"]
            ["donation_year_mismatch"], 4)
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
