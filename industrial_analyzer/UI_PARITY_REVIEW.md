# V12.2 native screen parity review

Reference: Industrial_Analyzer_V12_2_Demo_Entry_Fixed.html supplied by the project owner. The original HTML is not used by the running application. The reference was inspected as HTML source and rendered for visual inspection. The Qt implementation is a native reconstruction, not a claim of pixel-identical rendering.

## Implementation and verification

| Reference screen | Native reconstruction |
|---|---|
| Login | Split hero / credential form, first administrator setup, sign in, synthetic demo |
| Overview | 236 px navigation, hero artwork, four KPI tiles, graph, investigation shortcuts, dataset card |
| Data Explorer | Searchable channel table, checkbox selection, select filtered / clear |
| Signal Trends | Channel browser dialog, 12 displayed traces, six per panel, normalized percentage, synchronized plots, position/window, cursors, trace colors/ranges/removal |
| Statistics | Searchable all-channel table, row detail, histogram, CDF, configurable range, rolling, outliers, segments |
| Thresholds | Inclusive limits, separate violation records and grouped event timeline, CSV export |
| Comparison | Two-channel view, selectable 4/6/8-channel correlation matrix, colored correlation cells |
| Engineering Lab | Five specialized panes, dedicated plots and tables, box plot, capability, dwell, lag, SPC |
| Advanced Diagnostics | Ten separate panes, dedicated plot titles, parameters, diagnostic detail and exports |
| Reports | Builder, export contents and generated report preview |
| Access & Users | Local SQLite accounts, scrypt, role matrix, account creation / disabling, audit and password change |

The Windows workflow captures native login, all nine pages and all fifteen workbenches for visual acceptance review. It tests account operations, demo separation, and workbench execution, then retains the existing security gates and EXE smoke test.

## Intentional differences and remaining checks

- The reference's unrestricted administrator demo is unsafe as a real access boundary. Native demo mode uses synthetic data only; create a local account to import files. Password minimum is 12 characters, rather than the HTML's 8. Local storage and audit history are still not tamper-proof against someone with OS-level access.
- Qt controls, fonts, plot rendering, layout reflow and native dialogs differ from browser CSS. Screenshot comparison and manual review at multiple Windows DPI settings are required before calling the UI 1:1.
- Additional native support: TDMS, TXT, Excel, per-channel time bases, no forced alignment of unrelated datasets.
- Some original diagnostic formulas and output details still differ; the original population standard deviation versus existing sample standard deviation is one example. Data quality flatline/gap classification, step response measures, exact peak/envelope and change-detection calculations, report formatting and all table headers require further source-to-formula verification.
- The HTML's normalized trend chart is implemented; raw values remain in the cursor and export. Confirm mixed time-base visualization and alignment for real TDMS data.
- The native account controls are not an independent security boundary; OS access control, external authentication if required, hardened file parsing, large-file handling and signed release are outstanding.
- GUI tests and screenshots prove that widgets can be rendered and calculations can run on the synthetic dataset, not that every pixel or user interaction has passed acceptance.
