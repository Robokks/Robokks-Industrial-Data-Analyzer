# Industrial Analyzer Desktop — engineering preview

Native PySide6 widgets and PyQtGraph, based on the supplied V12.2 visual reference. No HTML frontend, browser or server. This is a source release candidate for evaluation, **not a production-approved or bug-free release**.

## Windows setup
Install 64-bit Python 3.12. Run `run.bat` to install requirements and start the app. For a gated Windows executable build, run `build_windows.bat` from Command Prompt. It installs test/build tooling, runs tests, Bandit and pip-audit, then builds a PyInstaller directory distribution. The entire dist/IndustrialAnalyzer directory is required. The first installation and vulnerability check need internet access. Runtime is offline. For an offline installation, prepare an appropriate wheelhouse on a connected Windows machine. Dependency versions are minimum constraints, not a reproducible audited lockfile; freeze and review the validated environment before release.

## Scope
Nine pages, 21 callable analysis modes, dark theme, demo dataset, data import dialogs, trend selection, two plots, statistics, threshold excursions, correlation matrix, engineering and diagnostic tabs, text reports and CSV/XLSX export. TXT/CSV accept a delimiter and optional time column or sample rate. Excel sheet selection is supported. TDMS reader preserves group/channel names, waveform-relative time and unit_string if provided. Sample index is used when time metadata is unavailable. Export uses long format for independent time bases. Excel macros are not executed by the application. Analysis is exploratory, not a certified fault or safety decision.

## Optional Rust
`rust_engine` contains an experimental PyO3 bucket-extrema module. With Rust and maturin installed, activate the virtual environment, change to rust_engine, run `maturin develop --release`, then return to root and run tests. The native routine is not connected to the GUI or analysis engine yet; the Python application is independent. No Rust performance claims are made.

## Known limitations / release blockers
- GUI is a native approximation, not pixel-identical. Original per-trace color/range controls, detailed report builder, account management, role authorization and audit history are not implemented. Some diagnostic charts and controls are simplified.
- Import and calculation run synchronously and use memory-resident arrays. Large files can exhaust RAM or freeze the UI. No 10 GB performance guarantee. Table previews are limited to 10,000 rows; exports can be larger.
- TDMS timestamp handling is relative, not absolute cross-channel alignment. Comparisons require matching time arrays; validate shared clock origins independently. Multiple-file workspaces, script execution and PDF reports are not implemented.
- TDMS, legacy XLS, native GUI, Rust compilation and Windows packaging have not been validated in this environment. Optional tests skip if packages are missing; skipped tests must be resolved before release. Real hardware data and numerical reference validation are still necessary.
- Do not expose the app to untrusted measurement files or rely on it for safety-critical decisions until parser isolation, resource controls and independent security review are complete.

## Tests
`python -m pytest -q`. See test_results.txt for this environment's actual results. See SECURITY_REVIEW.md for the audit scope. Windows build script is provided but not executed here.
