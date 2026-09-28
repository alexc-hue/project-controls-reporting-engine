# Changelog

All notable changes to this project are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and version numbers
follow [Semantic Versioning](https://semver.org/).

## [1.2.0] - 2026-09-28

Performance at larger sizes. Output is unchanged: the console report and report.md are byte-identical to the previous release on the sample data and on generated inputs, and the integrated chart renders pixel-identical, so no committed image changed.

### Added

- `benchmarks/size_test.py`, a hand-run size test: generates bigger inputs, runs the tool end to end
  and prints run time and peak memory. Not part of CI or the test suite.
- Measured size-test numbers in the README's Limitations section.

### Changed

- The vendored CPM engine re-copied from schedule-health-analyzer for its single-pass network
  ordering (same order, same results).
- The vendored risk engine re-copied from risk-trend-tracker for its per-risk rewrite (same
  results).
- The integrated chart's schedule panel is drawn in one call instead of one per activity
  (pixel-identical). 10,000 rows per register went from about 40 to about 28 seconds.

## [1.1.0] - 2026-09-28

Checks and tests only. The tool's output is unchanged.

### Added

- A test that runs `reporting_engine.py` end to end on the sample data and checks the README's Result block against what it actually prints, so the README can't drift from the code.
- A check that the committed `assets/report.md` is exactly what the script regenerates.
- `engines/VENDORED.json`, recording the source repo, file and commit each vendored engine came from, plus `scripts/vendored.py` to check the copies.
- A test that fails if a vendored engine is edited here without being re-vendored from its source.
- A CI job, on every push and weekly, that checks the vendored engines against their sources on GitHub.
- A test that pins the chart colors and styling shared across all six toolkit repos.
- ruff linting, run locally from `ruff.toml` and as its own CI job.
- CI now tests on Python 3.11 and 3.12, matching the "Python 3.11+" badge.
- `.gitattributes` keeps line endings consistent (LF) on every OS.

### Changed

- Import ordering and two placeholder-free f-strings in `reporting_engine.py`, from the new lint rules. No behaviour change.

## [1.0.0] - 2026-09-13

First tagged release, marking the state of the repo before this changelog started. Runs the EVM, schedule health, change control and risk trend engines against one shared programme and composes a single integrated status report. Includes the fixes from code review, a pytest suite and CI.

[1.2.0]: https://github.com/alexc-hue/project-controls-reporting-engine/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/alexc-hue/project-controls-reporting-engine/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/alexc-hue/project-controls-reporting-engine/releases/tag/v1.0.0
