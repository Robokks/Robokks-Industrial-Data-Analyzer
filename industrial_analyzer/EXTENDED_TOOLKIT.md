# Extended industrial toolkit

The original nine V12.2 pages remain. Use **Extended tools** in the sidebar for additional workspaces. The Open button now supports multiple files. The new code is a development candidate pending Windows CI and acceptance testing.

## Data and performance
- Multiple recordings, file-prefixed names, cross-file clock guard, append, JSON manifest restore with confirmation, trace selection/color restore.
- TDMS metadata tree and selected sample-range reads; streamed count, min/max, mean, population SD and RMS across a complete channel. Full import is capped by source size and working-set budget (8 million values, 256 loaded channels). Catalog browsing is distinct from working-set size.
- Background import, range statistics, new engineering operations and streamed export. Cancellation is cooperative; individual parser/FFT calls may not be interruptible. Original analysis pages still contain synchronous calculations.
- Excel archive expanded-size checks and formula-safe atomic exports. These are not comprehensive hostile-file isolation.
- Range reads use waveform timing or sample index; independent timestamp-channel mapping in the existing full TDMS reader is retained. npTDMS may read an entire compressed/interleaved segment internally, so range reads are not a guarantee of bounded peak memory for every file.
- JSON manifests save source paths, import options/ranges, selection and colors. They do not embed data or persist derived/live channels, all analysis settings or annotations.

## Engineering workstation
Mechanical kW, positive-flow efficiency, equivalent shaft loss torque, torque-speed XY, single-phase and three-phase (phase-neutral V and A) real/apparent power and power factor, harmonic least-squares THD, low/high-pass Butterworth, integral, derivative, detrending, envelope spectrum, constant/variable speed order tracking, theoretical bearing frequencies, spectrogram, waterfall, baseline tolerance, derived arithmetic, factor/offset unit conversion and explicit interpolation resampling. Users must select channels in the indicated units; calculations do not infer or certify calibration, sign convention, synchronization, electrical phase wiring or anti-aliasing. The resampler refuses downsampling rather than silently alias.

## Graph, reports and capture
- Dual independent Y axes for compatible clocks, session-local movable annotations/bookmarks, CSV bookmark export and PNG capture.
- Full-resolution A/B range statistics and export, PDF text report, and batch per-file statistical CSV/XLSX summary.
- Local read-only TCP/UDP capture, opt-in loopback only. LabVIEW sends UTF-8 JSON with seconds and channel dictionary; TCP uses one newline-terminated frame, UDP one frame per datagram. Example: {"t":0.1,"values":{"Speed":1500,"Torque":20}}. Capture is duration/row/channel bounded, requires strictly increasing time and stable channel names. No remote server binding, control commands, sender authentication or continuous live plotting. UDP can drop packets. Export captured data before replacing it.

## Remaining work
Transparent out-of-core execution of all existing analysis modes, validated 10 GB/100M sample performance, automatic absolute clock alignment, multi-channel range import, unrestricted large files, full background migration, merge/split, efficient binned efficiency maps, validated sensor-specific calibration, arbitrary analysis templates, scheduled reports, continuous live display and streaming to disk, remote authenticated integration, full workspace state including derived formulas/bookmarks, installer signing, complete visual and numerical acceptance, dependency locking and independent security audit. Do not claim all original and proposed features are production-complete.

Tests cover known reference calculations, expression rejection, TDMS slices/statistics, file/clock isolation, manifest parsing, capture frame validation and GUI/worker smoke. The Windows workflow retains Bandit, pip-audit, Cargo Audit and EXE startup checks.
