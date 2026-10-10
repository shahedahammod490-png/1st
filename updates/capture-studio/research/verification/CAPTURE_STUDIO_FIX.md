# Capture Studio fix — 2026-10-10 Asia/Dhaka

Applied to the existing extracted Stage 2 main snapshot in /workspace/ocurisk-lab. The uploaded original/checkpoint archives and Android/CameraX, scientific algorithms, models, quality analyzer and store sources remain unchanged.

## Root causes and evidence

1. web/ui.js field() created a textarea and executed n.type=type. HTMLTextAreaElement.type has only a getter; ES modules throw TypeError. Assign type only when tagName is INPUT. This also restores Models and review/reference textareas.
2. web/app.js route() used a catch-all which labelled any exception Service request failed. Independent original-code replay in real Chromium reproduced the exact error after clicking Capture: only /api/overview HTTP200 occurred; zero failed requests. The textarea exception occurred before the experiment-list request. Actual health, overview, experiments and jobs returned200. No backend outage explains this reproduction. Distinguish ApiError from rendering errors; genuine failures show method, endpoint, HTTP status/backend detail, network failure or invalid JSON. Form actions and binary media/sidecar uploads share this reporting.
3. Unexpected backend exceptions previously returned a generic500 without diagnostic traceback. server.py now logs method/path and traceback, retaining the existing sanitized HTTP response. No request body is logged. A real HTTP regression injects an exception and verifies logging,500 response sanitization and subsequent healthy request.

## Changed implementation and tests

- ocurisk_lab/web/ui.js: input-only type assignment, ApiError and service diagnostics, form/button error reporting.
- ocurisk_lab/web/app.js: classify workspace rendering versus API failures and retain console diagnostic.
- ocurisk_lab/web/live-capture.js: media and sidecar requests use the shared API helper; original-retained/analysis-not-queued warning preserved on sidecar failure.
- ocurisk_lab/server.py: unexpected exception diagnostics.
- tests/browser/capture-regression.cjs: eight real Chromium regression cases; use isolated service/database8766.
- tests/test_service_logging.py: actual HTTP logging/sanitization/recovery regression.

## Final validation

- Python:136 tests PASS,23.746s, /workspace/setup/capture-final-python.log.
- Host helpers:9 tests PASS,0.791s, /workspace/setup/capture-fixed-host.log.
- Node:ui-data,live-capture,droidcam-independent PASS.
- Existing stage2-ui.cjs PASS:five workspaces, light/dark desktop/narrow, experiment/export, no page errors.
- New capture-regression.cjs PASS8 cases in Chromium154.0.8037.57: notes/controls/gating/persisted metadata; generated camera preview/MediaRecorder/autosave/sidecar; default autoanalysis COMPLETED,11 decoded frames,20221 original bytes SHA256 matched; HTTP503, transport abort, malformed JSON, rejected POST400; rendering error distinct from backend with healthy health endpoint.
- Services restarted after the last Python implementation change. An intermediate browser autoanalysis run correctly failed the stale-implementation guard; post-restart final runs passed. No assertion was disabled.
- Requested actual cloud127.0.0.1:8765 verification PASS: experiment196b8ae363a24951a4e58d07064f2f20 is explicitly SYNTHETIC; two recordings retained, autoanalysis job820ab253708b471fa9f82e22b7b422fc COMPLETED,11 frames,20221 source bytes matched. Existing real records preserved. Service uses /workspace/ocurisk-data and remains running.
- Independent actual8765 review: all five workspaces connected, seven API reads200, health200, no requestfailed/pageerrors/badHTTP; synthetic preview640x480 played and closed. /workspace/setup/capture-independent-review.json.

## Windows continuation

This cloud localhost is distinct from localhost on the user's Windows PC. To apply there, stop ONLY the separate Research Lab server, back up the listed four implementation files, copy the matching paths from the fix package into that existing Stage2 Lab directory, then restart with the existing launcher or `.\.venv\Scripts\python.exe -m ocurisk_lab.server --host 127.0.0.1 --port 8765 --data-dir data` using the original Lab data directory. Refresh Capture Studio. Never copy files into the original EYE/OcuRisk project. No dependency changes required.

Select the actual DroidCam virtual webcam and perform a nonhuman recording with the user's already working Windows USB/WiFi connection. Cloud tests use Chromium-generated frames and do not establish physical DroidCam operation, optical or clinical performance. Native CameraX remains optional and unchanged.
