'use strict';
// Run against an isolated service/database, never the user's research service.
// Chromium's generated camera frames are SYNTHETIC engineering fixtures.
const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const {chromium} = require('playwright');

const url = process.env.UI_URL || 'http://127.0.0.1:8766';
const target = new URL(url);
assert.ok(['127.0.0.1', 'localhost'].includes(target.hostname), 'Use a loopback test service');
assert.notEqual(target.port, '8765', 'Use an isolated test database/service, not the research service on 8765');
const report = {scope: 'Real Chromium; synthetic camera, isolated research records; no physical DroidCam verification', cases: []};

async function status(page, expected) {
  await page.waitForFunction(value => document.getElementById('connection')?.textContent === value, expected);
}

async function openCapture(page) {
  await page.goto(url, {waitUntil: 'networkidle'});
  await status(page, 'Local service connected');
  await page.locator('nav a[data-route="capture"]').click();
  await status(page, 'Local service connected');
  await page.getByRole('button', {name: 'Create experiment', exact: true}).waitFor();
}

(async () => {
  let browser;
  try {
    browser = await chromium.launch({
      executablePath: process.env.CHROME_PATH || '/usr/bin/chromium',
      headless: true,
      args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'],
    });
    report.browser = browser.version();
    const context = await browser.newContext({permissions: ['camera'], viewport: {width: 1400, height: 1000}});
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await openCapture(page);

    assert.equal(await page.locator('main h1').textContent(), 'Capture Studio');
    assert.equal(await page.getByText('Workspace unavailable', {exact: true}).count(), 0);
    assert.equal(await page.locator('#notes').evaluate(node => node.tagName), 'TEXTAREA');
    const fixture = {
      title: `SYNTHETIC Capture browser regression ${Date.now()}`,
      participant_id: 'synthetic-browser-participant',
      session_id: `synthetic-browser-${Date.now()}`,
      mode: 'MULTI_VIEW',
      data_origin: 'SYNTHETIC',
      notes: 'Synthetic real-browser regression.\nNo human participant or physical camera measurement.',
    };
    for (const name of ['title', 'participant_id', 'session_id', 'notes']) {
      await page.locator(`#${name}`).fill(fixture[name]);
      assert.equal(await page.locator(`#${name}`).inputValue(), fixture[name]);
    }
    await page.locator('#mode').selectOption('HEAD_TURN');
    await page.locator('#mode').selectOption(fixture.mode);
    await page.locator('#data_origin').selectOption('REAL_APPROVED');
    assert.equal(await page.locator('#approval_reference').evaluate(node => node.required), true);
    assert.equal(await page.locator('#title').evaluate(node => node.form.checkValidity()), false);
    await page.locator('#approval_reference').fill('synthetic-ui-validation-only');
    assert.equal(await page.locator('#title').evaluate(node => node.form.checkValidity()), true);
    await page.locator('#data_origin').selectOption(fixture.data_origin);
    await page.locator('#approval_reference').fill('');
    assert.equal(await page.locator('#approval_reference').evaluate(node => node.required), false);

    const createdResponse = page.waitForResponse(response => response.url() === `${url}/api/experiments` && response.request().method() === 'POST');
    await page.getByRole('button', {name: 'Create experiment', exact: true}).click();
    const response = await createdResponse;
    assert.equal(response.status(), 201);
    const created = await response.json();
    await page.waitForFunction(id => document.getElementById('upload-experiment')?.value === id, created.experiment_id);
    const persistedResponse = await page.request.get(`${url}/api/experiments/${created.experiment_id}`);
    assert.equal(persistedResponse.status(), 200);
    const persisted = await persistedResponse.json();
    for (const [name, value] of Object.entries(fixture)) assert.equal(persisted[name], value);
    assert.equal(persisted.approval_reference, null);
    report.experiment_id = created.experiment_id;
    report.cases.push('Capture Studio renders editable textarea, inputs, mode/origin and approval gating; experiment metadata persists');

    for (const name of ['Discover cameras', 'Request camera permission / preview', 'Start recording', 'Stop & autosave', 'Snapshot & autosave', 'Close camera']) {
      assert.equal(await page.getByRole('button', {name, exact: true}).isVisible(), true, name);
    }
    assert.equal(await page.getByRole('button', {name: 'Start recording', exact: true}).isDisabled(), true);
    await page.getByRole('button', {name: 'Discover cameras', exact: true}).click();
    await page.waitForFunction(() => document.getElementById('camera-device')?.options.length > 0);
    await page.getByRole('button', {name: 'Request camera permission / preview', exact: true}).click();
    await page.waitForFunction(() => document.getElementById('capture-status')?.textContent === 'PREVIEW');
    await page.locator('#live-auto').uncheck();
    await page.getByRole('button', {name: 'Start recording', exact: true}).click();
    await page.waitForFunction(() => document.getElementById('capture-status')?.textContent === 'RECORDING');
    assert.equal(await page.locator('#upload-experiment').isDisabled(), true);
    // Observe live generated frames before stopping; no mock MediaRecorder or DOM substitution.
    await page.waitForFunction(() => document.querySelector('video')?.currentTime > 0.5);
    await page.getByRole('button', {name: 'Stop & autosave', exact: true}).click();
    await page.waitForFunction(() => /^Saved /.test(document.getElementById('capture-status')?.textContent || ''));
    assert.equal(await page.getByRole('link', {name: 'Download retained source bytes', exact: true}).isVisible(), true);
    const recorded = await (await page.request.get(`${url}/api/experiments/${created.experiment_id}`)).json();
    assert.equal(recorded.media.length, 1);
    assert.equal(recorded.media[0].kind, 'VIDEO');
    const media = await (await page.request.get(`${url}/api/media/${recorded.media[0].media_id}`)).json();
    assert.ok(media.sidecars.some(item => item.filename === 'capture-quality.json'));
    assert.equal(media.jobs.length, 0, 'This narrow recording regression deliberately disables autoanalysis');
    report.media_id = media.media_id;
    await page.getByRole('button', {name: 'Close camera', exact: true}).click();
    await page.waitForFunction(() => document.getElementById('capture-status')?.textContent === 'Camera closed');
    assert.equal(await page.locator('video').evaluate(node => node.srcObject), null);
    assert.deepEqual(errors, []);
    report.cases.push('Real synthetic camera discovery, preview, MediaRecorder start/stop, source/sidecar save and camera close');
    await context.close();

    const autoContext = await browser.newContext({permissions: ['camera']});
    const autoPage = await autoContext.newPage();
    const autoErrors = [];
    autoPage.on('pageerror', error => autoErrors.push(error.message));
    await openCapture(autoPage);
    await autoPage.locator('#upload-experiment').selectOption(created.experiment_id);
    assert.equal(await autoPage.locator('#live-auto').isChecked(), true, 'Automatic analysis is enabled by default');
    await autoPage.getByRole('button', {name: 'Request camera permission / preview', exact: true}).click();
    await autoPage.waitForFunction(() => document.getElementById('capture-status')?.textContent === 'PREVIEW');
    await autoPage.getByRole('button', {name: 'Start recording', exact: true}).click();
    await autoPage.waitForFunction(() => document.getElementById('capture-status')?.textContent === 'RECORDING');
    await autoPage.waitForFunction(() => document.querySelector('video')?.currentTime > 0.5);
    await autoPage.getByRole('button', {name: 'Stop & autosave', exact: true}).click();
    await autoPage.waitForFunction(() => location.hash.startsWith('#optical?') && location.hash.includes('job='));
    const parameters = new URLSearchParams(new URL(autoPage.url()).hash.split('?')[1]);
    const jobId = parameters.get('job'), autoMediaId = parameters.get('media');
    assert.ok(jobId && autoMediaId);
    let completed;
    const deadline = Date.now() + 60000;
    do {
      completed = await (await autoPage.request.get(`${url}/api/jobs/${jobId}`)).json();
      if (['COMPLETED', 'FAILED', 'CANCELLED', 'INTERRUPTED'].includes(completed.state)) break;
      await new Promise(resolve => setTimeout(resolve, 300));
    } while (Date.now() < deadline);
    assert.equal(completed.state, 'COMPLETED', JSON.stringify(completed.error));
    assert.ok(completed.result.frames.length > 0);
    assert.ok(completed.result.acquisition_quality);
    await autoPage.waitForFunction(() => document.querySelector('canvas[aria-label="Actual source frame with source-coordinate manual circles"]')?.width > 0);
    await status(autoPage, 'Local service connected');
    assert.equal(await autoPage.locator('main h1').textContent(), 'Optical Workspace');
    assert.equal(await autoPage.getByRole('link', {name: 'Download immutable original', exact: true}).isVisible(), true);
    const autoMedia = await (await autoPage.request.get(`${url}/api/media/${autoMediaId}`)).json();
    const original = await autoPage.request.get(`${url}/api/media/${autoMediaId}/original`);
    assert.equal(original.status(), 200);
    const originalBytes = await original.body();
    assert.ok(originalBytes.length > 0);
    assert.equal(originalBytes.length, autoMedia.size_bytes);
    assert.equal(createHash('sha256').update(originalBytes).digest('hex'), autoMedia.sha256);
    assert.deepEqual(autoErrors, []);
    report.autoanalysis_job_id = jobId;
    report.autoanalysis_frame_count = completed.result.frames.length;
    report.autoanalysis_original_bytes = originalBytes.length;
    report.cases.push('Default automatic analysis completes; Optical Workspace renders actual decoded pixels/quality; original bytes match persisted SHA256');
    await autoContext.close();

    const failures = [
      ['HTTP 503', route => route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({error: 'Regression service unavailable'})}), /HTTP 503.*Regression service unavailable/],
      ['transport abort', route => route.abort('failed'), /Network request failed/],
      ['malformed JSON', route => route.fulfill({status: 200, contentType: 'application/json', body: '{invalid-json'}), /Invalid JSON response \(HTTP 200\)/],
    ];
    for (const [name, handler, expected] of failures) {
      const failurePage = await browser.newPage();
      await failurePage.route('**/api/experiments', handler);
      await failurePage.goto(`${url}/#capture`, {waitUntil: 'networkidle'});
      await status(failurePage, 'Service request failed');
      const visible = await failurePage.locator('main').innerText();
      assert.match(visible, /GET \/api\/experiments:/);
      assert.match(visible, expected);
      assert.match(await failurePage.locator('#notice').innerText(), expected);
      await failurePage.close();
      report.cases.push(`${name}: service status and visible failing request/detail`);
    }

    const submitPage = await browser.newPage();
    await openCapture(submitPage);
    for (const name of ['title', 'participant_id', 'session_id', 'notes']) await submitPage.locator(`#${name}`).fill(fixture[name]);
    await submitPage.locator('#data_origin').selectOption('SYNTHETIC');
    await submitPage.route('**/api/experiments', route => route.request().method() === 'POST'
      ? route.fulfill({status: 400, contentType: 'application/json', body: JSON.stringify({error: 'Regression rejected experiment'})})
      : route.continue());
    await submitPage.getByRole('button', {name: 'Create experiment', exact: true}).click();
    await status(submitPage, 'Service request failed');
    assert.match(await submitPage.locator('#notice').innerText(), /POST \/api\/experiments: HTTP 400.*Regression rejected experiment/);
    assert.equal(await submitPage.locator('main h1').textContent(), 'Capture Studio');
    assert.equal(await submitPage.locator('#notes').inputValue(), fixture.notes);
    await submitPage.close();
    report.cases.push('Rejected experiment submission reports request/status/detail and preserves editable Capture Studio');

    const renderPage = await browser.newPage();
    await renderPage.addInitScript(() => {
      const create = Document.prototype.createElement;
      Document.prototype.createElement = function(tag, options) {
        if (String(tag).toLowerCase() === 'textarea') throw new TypeError('Injected textarea rendering failure');
        return create.call(this, tag, options);
      };
    });
    await renderPage.goto(`${url}/#capture`, {waitUntil: 'networkidle'});
    await status(renderPage, 'Workspace rendering failed');
    assert.match(await renderPage.locator('main').innerText(), /Injected textarea rendering failure/);
    const health = await renderPage.request.get(`${url}/api/health`);
    assert.equal(health.status(), 200);
    assert.equal((await health.json()).status, 'running');
    await renderPage.close();
    report.cases.push('Injected rendering failure is distinguished from backend failure; health stays running');
    report.passed = true;
    console.log(JSON.stringify(report, null, 2));
  } finally {
    await browser?.close();
  }
})().catch(error => {console.error(error.stack || error); process.exitCode = 1;});
