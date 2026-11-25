# Release acceptance and functional requirements

Acceptance is distinct from unit tests. The push workflow runs Windows tests, native Qt screenshot capture, 125% and 150% Qt scale checks, Python and Rust dependency audits. It does not publish a new EXE automatically. Review screenshots and test evidence first. For packaging, manually run the same workflow with package=true and reviewed_sha equal to the reviewed full commit SHA. The job reruns all tests and audits, then packages and startup-tests the EXE. The SHA guard does not independently authenticate that a human performed the review; approval must be recorded by the reviewer.

| ID | Requirement | Evidence |
|---|---|---|
| FR-01 | Import TDMS/TXT/CSV/Excel with units and time bases | test_engine.py, test_optional.py, test_performance.py |
| FR-02 | TDMS metadata/range and streaming statistics | test_extended.py |
| FR-03 | Multiple recordings and safe clock alignment | test_extended.py, test_acceptance.py |
| FR-04 | Native login/setup, permissions, throttling | test_v12_ui.py, test_acceptance.py |
| FR-05 | All nine original pages and 15 workbenches render | test_v12_ui.py + screenshot artifact |
| FR-06 | Search, filtered selection, cursor measurement and raw scale | test_acceptance.py |
| FR-07 | Mechanical/electrical/vibration and signal processing | test_extended.py, test_acceptance.py (21 workbenches) |
| FR-08 | Report generation, PDF, CSV/XLSX safety | test_acceptance.py, test_performance.py |
| FR-09 | Workspace validation and restoration metadata | test_extended.py |
| FR-10 | TCP/UDP measurement capture with real loopback socket I/O | test_acceptance.py, test_extended.py |
| FR-11 | Explicit channel alignment, split/merge without source mutation | test_acceptance.py |
| FR-12 | Power-weighted speed/torque efficiency bins | test_acceptance.py |
| NFR-01 | Build, packaging and startup | Approved packaging job |
| NFR-02 | Static and dependency security checks | Bandit, pip-audit, Cargo Audit |
| NFR-03 | 1440/1920 native screenshots, 125/150% Qt scale checks | UI screenshot artifact; visual review still manual |
| NFR-04 | 10 GB / 100M samples and 1000 channels | NOT verified; bounded loaded working set remains 8 million values / 256 channels |
| NFR-05 | Full HTML pixel and formula parity | NOT verified; source-to-screen and numerical manual review required |
| NFR-06 | Signed installer, OS access policy, independent security evaluation | NOT complete |

New recording operations create derived channels and do not overwrite original measurements. Alignment is explicit, same-unit, strictly increasing, overlap-only; potential downsampling is rejected. Efficiency map bins are ratios of summed output and input power, not means of per-sample efficiency; low-count bins remain missing. This is not a certified test-rig result.

Remaining: all original analyses on background/out-of-core engines, production-scale benchmarks, multi-channel lazy read, full workspace serialization, reusable/scheduled analysis templates, continuous plotting and disk logging, signed installer, full real-data and DPI acceptance. Offscreen rendering is not the same as human visual or real Windows monitor acceptance. Review all screenshots, test with real LabVIEW TDMS fixtures, and record deviations before production deployment.
