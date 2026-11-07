# Security Policy

## Reporting a vulnerability

Please report security issues privately through
GitHub's private vulnerability reporting on this
repository (Security → Report a vulnerability) rather
than a public issue.

## Scope notes

charity-compliance is a static, local-only checker:

- It reads files; it never executes, imports, compiles,
  or installs code from a checked folder, and the
  combined `filing-ready` run writes nothing.
- It makes no network calls and collects no telemetry.
  Donation records name real donors in real use — the
  tool is designed so that data never leaves the
  machine, and reports cite only the figures and fields
  a finding is about.
- A PASS or READY verdict from any command means "none
  of the problems this suite's encoded checks look for
  were found". It is not a guarantee that the CRA will
  accept the receipts or the return — each report prints
  its own limits and disclaimer.
