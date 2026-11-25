# Corrective action: Windows EXE user bug report

Affected release: packaged source f8bb7a2, workflow run 45577532570. User reports theme hangs, inconsistent light mode, Open Data and Extended Tools not working.

## Corrective changes
- Theme: reuse Fusion style engine, skip redundant theme applications, stop reentrant layout timers, refresh visible graphs only and synchronize cached graphs when revisited. Reflow avoids traversing inactive stacked workbenches and repeated same-width layout passes. This reduces work; the exact hang on the reporting PC has not yet been reproduced.
- Light palette: explicit view selection/foreground, trees, progress bars, scrollbars, disabled controls, chart lines, scatter symbols, histogram fills, cursor labels and correlation table contrast. Some fixed/custom user trace colors remain by design; screenshots still require human acceptance.
- Open Data: demo is intentionally synthetic-only; the button is now active and clearly labeled Sign in. Opens account creation/sign-in, continues directly to file selection after authorization, and returns to demo on cancel. Existing role restrictions retained. Native Qt file dialog avoids Windows shell extension problems; source data remains untouched.
- Extended Tools: replace nested popup menu with a scrollable categorized native dialog. Demo-compatible tools are available directly; restricted actions explain that sign-in is required. Disabled actions for insufficient authenticated roles are labeled Restricted.
- Background workers start only after modal event loop begins; local rotating error log and visible error dialogs for runtime exceptions.
- Packaging: include the extended UI and self-test module explicitly. The compiled EXE must execute a real button/dialog/import/theme smoke test with synthetic fixtures and temporary accounts before the existing startup check. No production accounts or measurements are accessed by the smoke test.

## Regression evidence
Source action tests use the application entry point, actual login and launcher dialogs, real generated CSV/TXT/XLSX/TDMS files, repeated cached-page theme changes, histogram/scatter/cursor color checks, and a timed theme-switch guard. File-picker responses/import settings are supplied automatically, not manual OS interaction. The existing 82 tests, screen width and scaling gates remain; tests which previously expected the demo Open Data button to be disabled now expect a working sign-in action. New tests must pass in Windows CI. Real PC reproduction, larger loaded data performance, and visual acceptance remain pending.
