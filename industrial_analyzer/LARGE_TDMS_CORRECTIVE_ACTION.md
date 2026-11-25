# Large TDMS corrective action

Reported by user: "TDMS exceeds in-memory budget; use range browser" during normal Open Data.

Full in-memory import has fixed limits (8 million numeric values, 256 channels and 128 MiB source file size). These are application guardrails, not TDMS format limits or proof of insufficient physical RAM.

Changes:
- Typed TDMS budget exception retains the original file and remaining workspace budget. Normal Open Data opens the multi-channel range dialog automatically and continues import after confirmation. Manual Extended Tools range browser uses the same dialog.
- Select channels, common inclusive start and exclusive stop, fit interval to budget, inspect total selected values and stream exact whole-channel statistics for a highlighted channel. Oversized or invalid selections cannot be loaded. Cancellation does not install a partial workspace.
- Metadata-only catalog and preallocation checks; exact selected samples, waveform time and unique matching timestamp-channel time when available. No display decimation is used for engineering calculations. Explicit sample-index fallback for ambiguous clocks.
- Multiple selected ranges stored in one recording manifest, with validation and backward compatibility for the old single-range manifest.
- Imported range workspaces visibly marked as selected ranges; full-channel statistics are separate from loaded-range analysis.
- Tests cover sample/file limits, multi-channel selection, actual Open Data action, timing, range validation and manifest round trip.

Limitation: this is automatic bounded-range import, not an unrestricted out-of-core engine. Some algorithms still need in-memory arrays; exact peak RAM depends on parser, copies, clocks and analyses. Arbitrarily large full-recording FFT, correlation and export are not implemented by this patch. Real production TDMS formats and performance need testing with the user's actual recording. Windows CI and screenshot acceptance pending.
