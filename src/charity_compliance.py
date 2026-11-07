#!/usr/bin/env python3
"""charity-compliance — is this charity ready to file?

One suite, two checkers that used to be two separate tools,
merged (FLEET-AUDIT-2026-11-04, flagship B3) without
changing a single check:

    charity-compliance receipt-gate check|register|rules ...
        Validate a donations CSV against the CRA's encoded
        official-receipt requirements before the receipts
        go out (13 elements, split-receipting math, the
        80% and 10% advantage rules, serial discipline,
        date logic) — plus the year-end register whose
        eligible total starts the T3010 work.
    charity-compliance t3010-check check|deadline|rules ...
        Pre-flight a charity's T3010 return data before
        filing: completeness against the CRA's published
        requirements, exact cross-footing (including line
        4500 vs the receipt-register total), and the
        filing deadline (year-end + 6 months).
    charity-compliance filing-ready DIR
        Both, pointed at one charity folder — the donation
        records and the draft T3010 inputs, wherever the
        folder keeps them — as a single readiness receipt.

Every module keeps its source tool's checks, verdict words
and honesty limits — the engines are ported, not rewritten.
A READY verdict means the data satisfies the checks
*encoded in the two modules* (receipt rules checked
2026-11; T3010 checks checked 2026-11-04) — never that the
CRA will accept the receipts or the return. This suite is
a checking aid: it files nothing, issues nothing, and is
not tax advice. Read-only, local only: filing-ready reads
the folder and writes nothing.

(stdlib only, local only, no network.)
"""

import argparse
import csv
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import receipt_gate
import t3010_check

__version__ = "1.0.0"

TOOL = "charity-compliance"

MODULES = {
    "receipt-gate": receipt_gate,
    "t3010-check": t3010_check,
}

_MODULE_BLURBS = {
    "receipt-gate": "donation receipts vs the encoded CRA "
                    "receipt rules",
    "t3010-check": "the draft T3010 return vs the encoded "
                   "pre-flight checks",
}

DISCLAIMER = (
    "charity-compliance is a checking aid: it files "
    "nothing, issues no receipts, and is not tax advice. "
    "A READY verdict means the data satisfies the checks "
    "encoded in the two modules (receipt rules checked "
    "2026-11; T3010 checks checked 2026-11-04) — never "
    "that the CRA will accept the receipts or the return. "
    "Verify against the CRA's current guidance before "
    "relying on any verdict.")

HELP = """usage: charity-compliance <command> [args...]

Is this charity ready to file? Two checkers, one suite.
Every command accepts --json (one JSON object, exit
0 pass / 1 findings / 2 usage or input error).

commands:
  receipt-gate  check|register|rules ...
                                 donation receipts vs the CRA
                                 receipt rules (encoded)
  t3010-check   check|deadline|rules ...
                                 T3010 return pre-flight:
                                 completeness, cross-footing,
                                 deadline
  filing-ready  DIR              both modules over one charity
                                 folder, as a single readiness
                                 receipt

Run `charity-compliance <command> --help` for a module's
own options. Read-only and local: filing-ready reads the
folder, writes nothing, and sends donor data nowhere.
A READY verdict is a statement about the encoded checks,
never about CRA acceptance — see the disclaimer in every
report."""


class ToolError(Exception):
    """A user-facing failure: printed without a traceback,
    exit code 2 (same convention as the two modules)."""


class _JsonAwareParser(argparse.ArgumentParser):
    """ArgumentParser that reports usage errors as JSON in
    --json mode ({"error": ...} on stdout, same exit code 2).
    The flag lives on the class so subparsers share it."""

    json_mode = False

    def error(self, message):
        if self.json_mode:
            print(json.dumps({"error": message}))
            self.exit(2)
        super().error(message)


# ---------------------------------------------------------------------------
# Combined filing-ready run
# ---------------------------------------------------------------------------

def _iter_files(d, suffix):
    """Files under DIR with the given suffix, in sorted,
    deterministic order; .git is never entered. The
    suffix match is case-insensitive — a charity's
    DONATIONS.CSV is still its donations file."""
    out = []
    for p in sorted(d.rglob("*")):
        if ".git" in p.relative_to(d).parts:
            continue
        if p.is_file() and p.name.lower().endswith(suffix):
            out.append(p)
    return out


def _normalized_header(path):
    """The CSV header as a set of normalized names
    (non-alphanumerics stripped, lowercased) — the same
    normalization receipt-gate itself applies — or None
    when the file has no readable header row."""
    try:
        with path.open(newline="", encoding="utf-8-sig") as fh:
            for row in csv.reader(fh):
                if row:
                    return {"".join(ch for ch in cell.lower()
                                    if ch.isalnum())
                            for cell in row}
    except (OSError, UnicodeDecodeError, csv.Error):
        return None
    return None


def _discover_donations(d):
    """The donations CSV receipt-gate is pointed at during
    a combined run: the first CSV under DIR (sorted order)
    whose header carries the receipt columns — it must
    name both serial_number and donor_name, which the
    T3010 field,value CSVs and unrelated spreadsheets do
    not. Returns None when no CSV qualifies."""
    for p in _iter_files(d, ".csv"):
        header = _normalized_header(p)
        if header and {"serialnumber", "donorname"} <= header:
            return p
    return None


def _discover_return(d):
    """The T3010 input t3010-check is pointed at during a
    combined run. JSON first: the first .json under DIR
    (sorted order) that parses to an object carrying the
    return's charity or financials section. Else the CSV
    quick path: the first .csv whose header row is the
    T3010 field,value shape. Returns None when neither
    qualifies."""
    for p in _iter_files(d, ".json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and (
                "charity" in data or "financials" in data):
            return p
    for p in _iter_files(d, ".csv"):
        header = _normalized_header(p)
        if header == {"field", "value"}:
            return p
    return None


def _run_capture(module_main, args):
    """Run a module's own CLI in-process and capture what it
    prints. Returns (exit_code, stdout_text). The module's
    main() may raise SystemExit (argparse errors, --help);
    its code is honoured either way."""
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            code = module_main(args)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 2
    return code, buf.getvalue()


def _run_json_section(module_main, args):
    """Run a module in --json mode; its section is the exact
    object the module itself prints, plus its exit code."""
    code, text = _run_capture(module_main, args)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = {"error": "module produced no JSON output",
                   "raw": text.strip()[:500]}
    payload = dict(payload)
    payload["exit_code"] = code
    return payload


def _skipped_section(name, reason):
    section = {"tool": name, "status": "skipped",
               "reason": reason, "clean": None,
               "exit_code": None}
    module = MODULES[name]
    version = getattr(module, "__version__", None)
    if version is not None:
        section["version"] = version
    return section


def _section_clean(section):
    """A run section is clean exactly when the module's own
    verdict is PASS; an error payload is never clean; a
    skipped section is neither (None)."""
    if section.get("status") == "skipped":
        return None
    if "error" in section:
        return False
    return section.get("verdict") == "PASS"


def filing_ready(d, year=None, as_of=None, want_text=False):
    """Run both modules over the charity folder DIR.
    Returns (payload, sections_text) — the payload is the
    combined receipt (JSON mode); sections_text holds each
    run module's own captured text output (text mode only;
    the modules are read-only and deterministic, so the
    second run is identical)."""
    sections_json = {}
    sections_text = {}

    def _text(name, module_main, args):
        if not want_text:
            return (None, None)
        return _run_capture(module_main, args)

    inputs = {"receipt-gate": None, "t3010-check": None}

    # receipt-gate: the discovered donations CSV.
    donations = _discover_donations(d)
    if donations is not None:
        inputs["receipt-gate"] = str(donations)
        args = ["check", str(donations)]
        if year is not None:
            args += ["--year", str(year)]
        if as_of is not None:
            args += ["--as-of", as_of]
        sections_json["receipt-gate"] = _run_json_section(
            receipt_gate.main, args + ["--json"])
        sections_text["receipt-gate"] = _text(
            "receipt-gate", receipt_gate.main, args)
    else:
        sections_json["receipt-gate"] = _skipped_section(
            "receipt-gate",
            "no donations CSV found under the folder (looked "
            "for a .csv whose header names serial_number and "
            "donor_name)")
        sections_text["receipt-gate"] = (None, None)

    # t3010-check: the discovered return input (JSON model
    # preferred, field,value CSV as the quick path).
    ret = _discover_return(d)
    if ret is not None:
        inputs["t3010-check"] = str(ret)
        args = ["check", str(ret)]
        if as_of is not None:
            args += ["--as-of", as_of]
        sections_json["t3010-check"] = _run_json_section(
            t3010_check.main, args + ["--json"])
        sections_text["t3010-check"] = _text(
            "t3010-check", t3010_check.main, args)
    else:
        sections_json["t3010-check"] = _skipped_section(
            "t3010-check",
            "no T3010 input found under the folder (looked "
            "for a .json return model carrying charity or "
            "financials, or a field,value .csv)")
        sections_text["t3010-check"] = (None, None)

    run = [n for n, s in sections_json.items()
           if s.get("status") != "skipped"]
    skipped = [n for n, s in sections_json.items()
               if s.get("status") == "skipped"]
    clean_modules = [n for n in run
                     if _section_clean(sections_json[n]) is True]
    finding_modules = [n for n in run
                       if _section_clean(sections_json[n])
                       is False]
    ready = bool(run) and not finding_modules
    payload = {
        "tool": TOOL, "version": __version__,
        "command": "filing-ready", "dir": str(d),
        "inputs": inputs,
        "modules": sections_json,
        "summary": {
            "modules_run": len(run),
            "modules_skipped": len(skipped),
            "clean_modules": len(clean_modules),
            "finding_modules": len(finding_modules),
            "skipped": skipped,
        },
        "ready": ready,
        "verdict": "READY" if ready else "NOT READY",
        "disclaimer": DISCLAIMER,
    }
    return payload, sections_text


def cmd_filing_ready(a):
    d = Path(a.dir)
    if not d.exists():
        raise ToolError(f"no such folder: {a.dir}")
    if not d.is_dir():
        raise ToolError(f"not a folder: {a.dir}")
    payload, sections_text = filing_ready(
        d, year=a.year, as_of=a.as_of, want_text=not a.json)
    if a.json:
        print(json.dumps(payload, indent=2))
        return 0 if payload["ready"] else 1
    s = payload["summary"]
    print(f"{TOOL} v{__version__} — filing-ready · "
          f"folder {d.name}")
    print(f"{s['modules_run']} module(s) run · "
          f"{s['clean_modules']} passed · "
          f"{s['finding_modules']} with findings · "
          f"{s['modules_skipped']} skipped")
    for name in MODULES:
        section = payload["modules"][name]
        print()
        print(f"===== {name} — {_MODULE_BLURBS[name]} =====")
        if section.get("status") == "skipped":
            print(f"SKIPPED — {section['reason']}")
            continue
        _code, text = sections_text[name]
        print(text.rstrip())
    print()
    if payload["ready"]:
        passed = [n for n, sec in payload["modules"].items()
                  if _section_clean(sec) is True]
        line = ("VERDICT: READY — every module that ran "
                "passed (" + ", ".join(passed) + ")")
        if s["skipped"]:
            line += ("; skipped, NOT checked: "
                     + ", ".join(s["skipped"]))
        print(line + ". READY covers only the checks "
              "encoded in the two modules — it is never a "
              "statement that the CRA will accept the "
              "receipts or the return. Filing remains a "
              "human act.")
    elif s["modules_run"] == 0:
        print("VERDICT: NOT READY — neither module had "
              "inputs to check in this folder, so nothing "
              "was verified. A READY verdict requires at "
              "least one module to have run and passed.")
    else:
        names = [n for n, sec in payload["modules"].items()
                 if _section_clean(sec) is False]
        print("VERDICT: NOT READY — findings in "
              + ", ".join(names)
              + " — fix each module's section above before "
                "the receipts go out or the return is filed.")
    print()
    print(DISCLAIMER)
    return 0 if payload["ready"] else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _filing_ready_parser():
    ap = _JsonAwareParser(
        prog=f"{TOOL} filing-ready",
        description="Run both modules over one charity "
                    "folder and print a single readiness "
                    "receipt. Read-only: the folder is "
                    "never written to.")
    ap.add_argument("dir", help="the charity folder holding "
                                "the donation records and the "
                                "draft T3010 inputs")
    ap.add_argument("--year", type=int, default=None,
                    help="receipting year passed to "
                         "receipt-gate (flags donations "
                         "received in other years)")
    ap.add_argument("--as-of", default=None,
                    metavar="YYYY-MM-DD",
                    help="check date passed to both modules "
                         "(receipt-gate flags dates after "
                         "it; t3010-check computes the "
                         "deadline status against it — "
                         "without it, t3010-check uses "
                         "today, its own standalone "
                         "behaviour)")
    ap.add_argument("--json", action="store_true",
                    help="print one JSON object (with a "
                         "per-module section) instead of "
                         "text")
    return ap


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(HELP)
        return 0
    if argv[0] in ("-v", "--version"):
        print(f"{TOOL} v{__version__}")
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd in MODULES:
        return MODULES[cmd].main(rest)
    if cmd == "filing-ready":
        _JsonAwareParser.json_mode = "--json" in rest
        ap = _filing_ready_parser()
        a = ap.parse_args(rest)

        def fail(msg):
            if getattr(a, "json", False):
                print(json.dumps({"error": msg}))
            else:
                print(f"ERROR: {msg}")
            return 2

        try:
            return cmd_filing_ready(a)
        except ToolError as exc:
            return fail(str(exc))
    if "--json" in argv:
        print(json.dumps(
            {"error": f"unknown command: {cmd} "
                      f"(expected one of: "
                      f"{', '.join(MODULES)}, filing-ready)"}))
    else:
        print(f"ERROR: unknown command: {cmd}")
        print()
        print(HELP)
    return 2


if __name__ == "__main__":
    sys.exit(main())
