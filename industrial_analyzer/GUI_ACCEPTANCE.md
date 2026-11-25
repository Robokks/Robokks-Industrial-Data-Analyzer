# Native responsive GUI acceptance

The earlier Windows screenshot artifact revealed tofu (square glyphs) and horizontal page clipping. Those screenshots are rejected. This revision introduces:
- Explicit font discovery and validation, Windows Qt platform for Windows CI instead of the earlier offscreen backend, and Fusion native widget style.
- Separate top command/status rows, smaller navigation buttons, consistent minimum control height, focus and hover styling, text tooltips, adaptive card/toolbar reflow, responsive KPI and tool tab grids.
- User-selectable dark and light gradient/glass-style palettes, persisted with QSettings. Native Qt cards simulate a glass look; there is no system blur/acrylic compositor dependency. Charts, axes and default trace colors follow theme.
- Native dialogs and chart sizing; no browser, HTML UI or WebView.
- Screenshots for nine pages in both modes at 1280×800, 1440×900 and 1920×1080, plus login. Additional CI runs at Qt scales 125% and 150%. Checks fail if fonts lack basic Latin glyphs, page horizontal overflow exceeds two logical pixels, visible buttons are undersized or visible chart canvases are too small.

The tests are intentionally strict and may reveal more defects. Qt scale factors are simulated; actual Windows display scaling and real monitor acceptance remain required. Screenshots must be inspected before packaging. Release validation is not a proof of exact HTML pixel parity or production readiness. This update does not address remaining large-file, numerical and industrial-data acceptance requirements.

## Corrective action after run 45575063644
81 tests passed; the responsive test rejected a 55-pixel horizontal overflow on Engineering Lab at 1280×800 dark. Actual Windows overview screenshot showed readable text. Corrective changes: active-pane-only stacked-widget sizing, adaptive input and metric grids, layout invalidation and per-tab reflow. Expanded regression tests visit each engineering and diagnostic tab at the same viewport widths. No overflow allowance or packaging gate has been relaxed. Verification pending on the new commit.
