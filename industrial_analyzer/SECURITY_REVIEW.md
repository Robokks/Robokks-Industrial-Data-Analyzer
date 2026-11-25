# Preliminary source security review

Scope: engine.py, main.py, safe_export.py and the experimental Rust source. No penetration test or complete dependency audit performed.

| Finding | Disposition |
|---|---|
| Spreadsheet formula injection through channel names and text | Mitigated by escaping formula-leading text in headers and cells; tested CSV and XLSX import/export separately. |
| Partial file overwrite during table export | Mitigated using same-directory temporary file and atomic replacement. |
| Qt automatic rich-text interpretation in labels | Mitigated by explicitly using plain text in label helper. |
| Invalid FFT time base, bad parameters, mismatched comparison timestamps | Added validation and regression tests. |
| Unsupported file extensions | Rejected in import layer. |
| Repeated expensive per-channel statistics calculations | Reduced to one calculation per channel in statistics table. |
| Dynamic eval/exec, shell execution, unsafe pickle deserialization | No direct calls found in a limited AST scan of application modules; not a comprehensive static analysis. |
| Dependency CVEs and supply-chain risk | OPEN: pip-audit and Bandit could not be installed because DNS/network access is unavailable. Build script includes checks. Pin verified versions, produce an SBOM and review licensing before distribution. |
| Resource exhaustion / malicious files | OPEN: large or malformed files may exhaust memory or CPU; parser sandbox and decompression limits needed. |
| User authentication, authorization, tamper-resistant audit log | OPEN: not implemented. Application relies on OS access controls only. |
| GUI runtime errors and native code safety | OPEN: runtime libraries and Cargo unavailable; perform Windows testing and Rust audit before release. |
| Artifact trust | OPEN: build and sign installer/executable in controlled CI. |

Do not interpret passing unit tests as absence of vulnerabilities or defects. Release requires all open critical/high risks addressed or explicitly accepted by the owner after independent verification.
