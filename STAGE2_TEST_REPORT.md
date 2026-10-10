# Current Stage2 test report — DroidCam extension

Application commit `c618576` has the same source bytes as the final independently tested working tree. Test snapshot recorded baseHEAD `aba5c5f` plus the source hash map before controlled integration commit. Subsequent documentation/package commits do not imply additional execution.

| Check | Actual result | Evidence |
|---|---|---|
| Final integrator Python suite |135 PASS,21.876 seconds |research/verification/DROIDCAM_INTEGRATION_TESTS.txt |
| Independent final Python suite |135 PASS,21.730 seconds |research/verification/DROIDCAM_python_tests.txt |
| Integrator host/USB helper suite |9 PASS,0.735 seconds on Linux |research/verification/DROIDCAM_HOST_TESTS.txt |
| Independent host helper suite |9 PASS,0.704 seconds on Linux |research/verification/DROIDCAM_host_tests.txt |
| Node parser/capture/independent state suites |3 suites PASS, explicit mocked recorder tests |DROIDCAM_ui_data_tests.txt,DROIDCAM_capture_state_tests.txt,DROIDCAM_independent_state_tests.txt under research/verification |
| Source freeze/integrity |51 app/test/script hashes unchanged during independent final run |research/verification/DROIDCAM_source_snapshot.json |
| Original protection |Original ZIP+57 inventoried authored files match |research/verification/DROIDCAM_original_integrity.txt |
| Python empty-body scan |No empty bodies in scanned ocurisk_lab |research/verification/DROIDCAM_empty_body_check.json |
| Python compile/JS syntax/whitespace |PASS in actual owner checks |research/DROIDCAM_INTEGRATION.md and DROIDCAM_UI.md |
| Actual browser interaction |BLOCKED before launch: Chromium install invalid/truncated ZIP; missing executable |research/droidcam-browser-install.log and droidcam-browser-execution.log |
| Actual Windows+CMF DroidCam |NOT physically verified by agents |User reports existing USB+WiFi connection works; Lab checklist pending |
| Optical/clinical calibration or winner |NOT established |No independently referenced/approved clinical cohort |

The135 suite includes previous tests,10 quality tests,4 new integration tests and9 new independent tests. Repeated suites are not additional unique tests. Nine helper tests are fixture runs, not actual Windows/USB device operation. No screenshots or browser/phone acceptance is claimed.

Runtime used pinned Python3.12.14, NumPy2.2.6, OpenCV4.12.0, Pillow12.3.0, SciPy1.17.0 and scikit-learn1.8.0; FFmpeg/ffprobe6.1.1. Synthetic/encoded fixtures test real computations, imports, metadata, saving, PTS, comparisons and integrity; they are not patient or optical-bench measurements.

## Failure evidence and corrected findings

Initial134-test suite exposed historical-export failure after an attachment was appended. Historical archives now explicitly retain old/current attachment snapshots and mismatch flags, while source/sidecar/artifact hashes and quality-summary equality remain enforced. One independent rerun was invalidated by code changing during execution; source-integrity guards correctly rejected it. Both logs remain retained. Final fresh135-test run used a hard freeze and passed.

Six findings were resolved: inaccurate requested-camera metadata, stale/racing capture context, identical-source comparison, partial/error recording eligibility, historical export rejection and contradictory archive summaries. Read research/verification/DROIDCAM_INDEPENDENT_REVIEW.md for independent dispositions and limited CONDITIONAL software verdict. Previous Stage2 report is preserved at research/verification/STAGE2_TEST_REPORT_PRE_DROIDCAM.md and in Git.

## Measurement limits

Resolution/count/valid saved PTS/code statistics are direct saved-data measurements. Sharpness/block-grid/motion are proxies; exposure/AWB causes are not identified. Browser settings/callbacks are not verified sensor timing. Original link codec/bitrate and exact camera frame losses remain unknown; absent saved bitrate remains unavailable. USB/WiFi differences are observed descriptive values with confound warnings, never a manufactured winner. Native APK/CNN gates remain separate and optional for primary DroidCam.
