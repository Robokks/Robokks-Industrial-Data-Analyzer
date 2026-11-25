# Performance and signal-navigation update

## Included
- TDMS timestamp arrays and explicitly named numeric seconds channels can provide time coordinates when waveform metadata is absent. Only a unique valid monotonic equal-length clock in the same group is accepted; ambiguous clocks fall back to sample index. This is a heuristic, not proof of physical synchronization. Metadata and clock information appear in the Data Explorer properties dialog. Relative waveform time remains supported; absolute clock alignment is not certified.
- CSV and XLSX exports stream rows without a full pandas DataFrame copy. Excel write-only output rejects oversize worksheets; incomplete exports do not replace the existing file. Formula injection protection remains in place.
- Overview preview uses peak-preserving NumPy extrema selection (finite traces); missing data keeps the full array to preserve gaps. Full interactive trend plots use PyQtGraph peak downsampling. Calculations and exports use original samples.
- Cursor lookup uses binary search for ordered time arrays, with a linear fallback for unordered arrays. Out-of-range cursor values return no measurement. A/B cursors on panel A show sample-aligned time difference and raw engineering-value differences.
- Normalized and raw-value modes are selectable. A raw plot still has a common Y axis, so mixed engineering units are explicitly labeled rather than presented as independent scales.
- Position-slider redraw is debounced. Optional Rust extrema backend is covered by a parity test; NumPy is the default until real-data benchmarks show a benefit.

## Verification
Tests cover extrema retention, missing samples, Rust parity, cursor values, streamed exports, atomic failure recovery, Excel formula escaping, TDMS timestamps and clock ambiguity. Existing tests and security gates remain enabled.

## Still pending
True lazy/chunked TDMS analysis and memory budgets, cancellation and background workers for import/analysis/export, multi-file workspace, group tree and per-channel axes, cursor range statistics/export, derived channels, absolute timestamp alignment, PDF reports, numerical parity and DPI acceptance, dependency locking, signed installer and independent security assessment. No large-file throughput or 10 GB capacity guarantee is made.
