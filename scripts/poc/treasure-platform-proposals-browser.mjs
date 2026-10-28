/** Real Vue workbench + built React Island, isolated HTTP fixtures only.
 * PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs CHROMIUM_PATH=/path/to/chrome
 * node scripts/poc/treasure-platform-proposals-browser.mjs
 * Does not authenticate against a live service, run an LLM, or create Tasks.
 */
import assert from 'node:assert/strict';
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { extname, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createServer } from '../../frontend/node_modules/vite/dist/node/index.js';

const frontend = resolve('frontend');
const fixture = await mkdtemp(resolve(frontend, '.treasure-proposals-'));
const output = resolve('evidence/treasure-platform-tools-20261027');
await mkdir(output, { recursive: true });
await writeFile(resolve(fixture, 'index.html'), '<html lang="zh"><div id="app"></div><script type="module" src="./main.ts"></script></html>');
await writeFile(resolve(fixture, 'main.ts'), `
import { createApp } from 'vue';
import Workbench from '@/views/TreasureResearchWorkbench.vue';
import '@/styles/tokens.css';
document.body.style.margin = '0';
document.querySelector('#app').style.height = '100vh';
createApp(Workbench).mount('#app');
`);
const report = { status: 'NOT_RUN', scope: 'ISOLATED_HTTP_NOT_RUNTIME_ACCEPTANCE', checks: [], errors: [] };
const proposals = [proposal('download-proposal', 'downloads.submit'), proposal('analysis-proposal', 'analysis.submit')];
const decisions = [];
let generated = false;
let revoked = false;
let server, browser;
try {
  server = await createServer({ configFile: resolve(frontend, 'vite.config.ts'), root: frontend,
    optimizeDeps: { entries: [resolve(fixture, 'index.html')] },
    server: { host: '127.0.0.1', port: 0, open: false }, logLevel: 'error' });
  await server.listen();
  const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : 'playwright');
  browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.on('pageerror', error => report.errors.push(error.message));
  const origin = server.resolvedUrls.local[0].replace(/\/$/, '');
  await page.route('**/*', async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin !== origin) return route.abort();
    // Serve the already-built Island as immutable static assets. Vite's source
    // import transform intentionally rejects modules in public/ during dev.
    if (url.pathname.startsWith('/treasure-island/')) {
      const contentTypes = { '.js': 'text/javascript', '.css': 'text/css', '.woff2': 'font/woff2', '.webp': 'image/webp', '.png': 'image/png' };
      return route.fulfill({ body: await readFile(resolve(frontend, 'public', url.pathname.slice(1))),
        contentType: contentTypes[extname(url.pathname)] || 'application/octet-stream' });
    }
    if (!url.pathname.startsWith('/api/v1/')) return route.continue();
    const path = url.pathname.slice('/api/v1'.length);
    const json = body => route.fulfill({ json: body });
    if (path === '/research-agent/capabilities') return json({ read_sessions: true, read_discovery: true, prepare_import: false, prepare_analysis: false });
    if (path === '/projects') return json([{ id: 'p1', name: '隔离验证项目' }]);
    if (path === '/research-agent/sessions') return json(url.searchParams.get('project_id') === 'p1'
      ? [{ session_id: 's1', project_id: 'p1', title: '平台任务预案', title_locked: true }] : []);
    if (path === '/research-agent/sessions/s1/messages') return json([]);
    if (path === '/research-agent/sessions/s1/messages:stream') {
      generated = true;
      return route.fulfill({ contentType: 'text/event-stream', body: [
        { event: 'platform_tool', result: { result: { proposal_id: 'download-proposal' } } },
        { delta: '已生成下载与分析预案，请分别审阅。执行尚未开放。' },
        { event: 'end' },
      ].map(event => `data: ${JSON.stringify(event)}\n\n`).join('') });
    }
    if (path === '/agent-tools/sessions/s1/capabilities') return json({ tools: [
      'tasks.list_related', 'analysis.prepare', ...(!revoked ? ['downloads.prepare'] : []),
    ].map(capability_id => ({ capability_id })), write_enabled: false, gate: 'WRITE_GATE_BLOCKED' });
    if (path === '/agent-tools/sessions/s1/related') return json(generated ? proposals.map(item => ({
      capability_id: item.operation === 'downloads.submit' ? 'downloads.prepare' : 'analysis.prepare', proposal: item,
    })) : []);
    const decision = /^\/agent-tools\/sessions\/s1\/proposals\/(.+)\/(approve|reject)$/.exec(path);
    if (decision && request.method() === 'POST') {
      decisions.push({ id: decision[1], approve: decision[2] === 'approve' });
      const item = proposals.find(item => item.proposal_id === decision[1]);
      assert.ok(item);
      item.state = decision[2] === 'approve' ? 'APPROVED' : 'REJECTED';
      return json({ state: item.state, write_enabled: false });
    }
    report.errors.push(`Unexpected API request: ${request.method()} ${path}`);
    return route.fulfill({ status: 500, json: { code: 'UNEXPECTED_FIXTURE_CALL' } });
  });
  const enterProject = async () => {
    await page.getByRole('combobox', { name: '项目上下文' }).selectOption('p1');
    await page.getByText('平台任务预案', { exact: true }).waitFor();
  };
  await page.goto(`${origin}/${fixture.split('/').at(-1)}/index.html`);
  await enterProject();
  await page.locator('textarea').fill('请准备平台下载与分析预案');
  await page.locator('textarea').press('Enter');
  const dialog = page.getByRole('dialog');
  await dialog.waitFor();
  await dialog.getByText('SRR123', { exact: true }).waitFor();
  await dialog.getByText('rna_seq', { exact: true }).waitFor();
  assert.deepEqual(decisions, []);
  assert.ok(!(await dialog.innerText()).includes('/private'));
  assert.ok(!(await dialog.innerText()).includes('confirmation-secret'));
  report.checks.push('SSE proposal event opens persisted shared proposals without Dataset permissions; no automatic approval');
  await dialog.locator('section').filter({ hasText: 'SRR123' }).getByRole('button', { name: '人工批准预案', exact: true }).click();
  await dialog.getByText(/APPROVED/).waitFor();
  await dialog.locator('section').filter({ hasText: 'rna_seq' }).getByRole('button', { name: '拒绝预案', exact: true }).click();
  await dialog.getByText(/REJECTED/).waitFor();
  assert.deepEqual(decisions, [{ id: 'download-proposal', approve: true }, { id: 'analysis-proposal', approve: false }]);
  report.checks.push('Human download approval and analysis rejection each call the session Gateway once; no Dataset or Task endpoint');
  await page.keyboard.press('Escape');
  await page.reload();
  await enterProject();
  await page.getByRole('button', { name: '刷新下载能力与权限', exact: true }).click();
  await dialog.getByText(/APPROVED/).waitFor();
  await dialog.getByText(/REJECTED/).waitFor();
  assert.equal(decisions.length, 2);
  report.checks.push('Reload restores durable approval/rejection without replaying decisions');
  const expired = proposal('expired-proposal', 'downloads.submit');
  expired.expires_at = '2000-01-01T00:00:00Z';
  proposals.push(expired);
  await dialog.getByRole('button', { name: '恢复预案与任务', exact: true }).click();
  const expiredSection = dialog.locator('section').filter({ hasText: 'expired-proposal-hash' });
  await expiredSection.waitFor();
  await expiredSection.getByText(/EXPIRED/).waitFor();
  assert.equal(await expiredSection.getByRole('button', { name: '人工批准预案', exact: true }).isDisabled(), true);
  report.checks.push('Expired shared proposal cannot be approved');
  await page.screenshot({ path: resolve(output, 'shared-proposals-desktop.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: resolve(output, 'shared-proposals-mobile.png') });
  revoked = true;
  await dialog.getByRole('button', { name: '恢复预案与任务', exact: true }).click();
  await page.waitForFunction(() => !document.querySelector('.original-display-host').shadowRoot.textContent.includes('download-proposal-hash'));
  assert.equal(await dialog.getByText('SRR123', { exact: true }).count(), 0);
  assert.equal(decisions.length, 2);
  report.checks.push('Revoking downloads.prepare removes download proposals and approval bindings');
  assert.deepEqual(report.errors, []);
  report.status = 'PASS_ISOLATED_BROWSER';
} catch (error) {
  report.status = 'FAIL'; report.errors.push(String(error)); process.exitCode = 1;
} finally {
  await browser?.close();
  await server?.close();
  await rm(fixture, { recursive: true, force: true });
  await writeFile(resolve(output, 'shared-proposals-browser.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report, null, 2));
}

function proposal(id, operation) {
  return { proposal_id: id, conversation_id: 's1', project_id: 'p1', operation,
    state: 'PENDING', parameters_hash: `${id}-hash`, expires_at: '2099-01-01T00:00:00Z',
    confirmation_id: 'confirmation-secret', normalized_parameters: { target_directory: '/private' },
    preview: operation === 'downloads.submit' ? { accession: 'SRR123', target_directory: '/private' }
      : { flow_id: 'rna_seq', sample_count: 4 }, write_enabled: false, gate: 'WRITE_GATE_BLOCKED' };
}
