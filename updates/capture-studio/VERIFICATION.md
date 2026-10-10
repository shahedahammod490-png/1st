# GitHub publication verification — 2026-10-10

Before committing, extracted the latest main snapshot from the unchanged uploaded checkpoint into a fresh temporary directory, verified every extracted file against FILE_SHA256.json, and applied this updater.

- Updater:4 regression tests passed, independently repeated. Source backups preserve baseline bytes; second update changes nothing; local edits, wrong/original-project roots and external symlinks are rejected before writes; synthetic dataset sentinel unchanged.
- Fresh updated Stage2 Python suite:136 tests passed in30.615 seconds, exit0.
- Fresh updated real Chromium154.0.8037.57 Capture regression:8 cases passed, exit0. Editable forms and metadata persistence; camera discovery/preview, real MediaRecorder, source/sidecar save; automatic analysis completed with11 decoded frames and20221 original bytes matching saved SHA256; HTTP503, transport abort, invalid JSON and rejected POST400 reported with request detail; rendering error distinct from healthy backend.
- Fresh service/data lived only in temporary validation directories. No existing research dataset was opened or copied for publication tests.
- Four implementation and two application-regression test files match the previously verified patch hashes. Original repository files and archives remain unchanged. No scientific algorithm, CameraX or dependency declaration is changed.

These are synthetic software checks on Linux. Physical Windows/DroidCam and optical/clinical validity remain unverified.
