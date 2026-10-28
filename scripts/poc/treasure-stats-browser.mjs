/** Real Vue workbench / React Island / axios boundary, with explicit HTTP fixtures.
 * Run from repository root after building the Island. Set PLAYWRIGHT_MODULE and
 * CHROMIUM_PATH if Playwright/Chromium are not on the standard module path.
 */
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, mkdir, rm } from 'node:fs/promises';
import { resolve, basename } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createServer } from '../../frontend/node_modules/vite/dist/node/index.js';

const frontend = resolve('frontend');
const fixture = await mkdtemp(resolve(frontend, '.stats-check-'));
const output = resolve('evidence/treasure-platform-stats');
await mkdir(output, { recursive: true });
await writeFile(resolve(fixture, 'index.html'), '<html lang="zh-CN"><div id="app" style="height:100vh"></div><script type="module" src="./main.ts"></script></html>');
await writeFile(resolve(fixture, 'main.ts'), `import { createApp } from 'vue'; import Workbench from '@/views/TreasureResearchWorkbench.vue'; createApp(Workbench).mount('#app');`);
let server, browser;
const report = { checks: [], errors: [] };
try {
  server = await createServer({ configFile: resolve(frontend, 'vite.config.ts'), root: frontend,
    optimizeDeps: { entries: [resolve(fixture, 'index.html')] },
    server: { host: '127.0.0.1', port: 0, open: false }, logLevel: 'error',
    plugins: [{ name: 'built-stats-island', configureServer(vite) {
      vite.middlewares.use(async (req, res, next) => {
        if (req.url?.split('?')[0] !== '/treasure-island/treasure-island.js') return next();
        res.setHeader('Content-Type', 'text/javascript');
        res.end(await readFile(resolve(frontend, 'public/treasure-island/treasure-island.js')));
      });
    } }],
  });
  await server.listen();
  const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : 'playwright');
  browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.on('pageerror', error => report.errors.push(error.message));
  const state = { nickname: '浏览器用户', boardError: false, nickError: false, statsError: false };
  const requests = [];
  const row = (key, name, treasures, weekTreasures) => ({ key, name, treasures, weekTreasures,
    chats: 3, digs: 4, weekChats: 1, weekDigs: 2, isGuest: false, updated_at: new Date().toISOString() });
  await page.route('**/api/v1/**', async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname;
    requests.push({ path, method: request.method(), period: url.searchParams.get('period') });
    const json = value => route.fulfill({ json: value });
    if (path.endsWith('/capabilities')) return json({ enabled: true, native_ui_enabled: true, read_discovery: true, read_sessions: true, prepare_import: false });
    if (path.endsWith('/projects') || path.endsWith('/projects/') || path.endsWith('/sessions')) return json([]);
    if (path.endsWith('/leaderboard')) {
      if (state.boardError) return route.fulfill({ status: 503, json: { code: 'UNAVAILABLE' } });
      return json({ users: [row('u:me', state.nickname, 5, 1), row('u:other', '其他研究者', 3, 3)],
        guests: [], ownKey: 'u:me', nickname: state.nickname, totalTreasures: 8, weekTreasures: 4 });
    }
    if (path.endsWith('/nickname')) {
      assert.equal(request.method(), 'PATCH');
      assert.deepEqual(Object.keys(request.postDataJSON()), ['nickname']);
      if (state.nickError) return route.fulfill({ status: 503, json: {} });
      state.nickname = request.postDataJSON().nickname;
      return json({ ok: true, nickname: state.nickname });
    }
    if (path.endsWith('/stats')) {
      if (state.statsError) return route.fulfill({ status: 503, json: {} });
      return json({ chats: 3, actors: 2, llmCalls: 4, totalTokens: 125, promptTokens: 100, completionTokens: 25,
        toolCalls: 6, toolErrors: 1, tools: [{ name: 'search_geo', label: 'GEO 检索', count: 6, errors: 1, empties: 0 }],
        usageRecordedChats: 2, since: '2026-10-01T00:00:00Z', updatedAt: new Date().toISOString() });
    }
    throw new Error('Unexpected fixture API: ' + path);
  });
  const url = `http://127.0.0.1:${server.httpServer.address().port}/${basename(fixture)}/index.html`;
  await page.goto(url);
  await page.getByRole('button', { name: '打开寻宝排行榜' }).click();
  const board = page.getByRole('dialog', { name: '寻宝排行榜', exact: true });
  await board.getByText('浏览器用户', { exact: true }).waitFor();
  assert.equal(await board.getByText('临时矿工', { exact: true }).count(), 0);
  assert.equal(await board.getByText('我', { exact: true }).count(), 1);
  assert.ok((await board.textContent()).includes('8 件宝藏'));
  await board.getByRole('button', { name: '本周', exact: true }).click();
  await page.waitForFunction(() => [...document.querySelector('.original-display-host').shadowRoot.querySelectorAll('ol li')][0]?.textContent.includes('其他研究者'));
  assert.ok((await board.textContent()).includes('4 件宝藏'));
  report.checks.push('Vue axios callbacks; all/week ranking; real own-key highlight; platform-only tab and totals');
  await board.getByRole('button', { name: /给自己取个上榜昵称/ }).click();
  const nick = board.locator('input');
  assert.equal(await nick.inputValue(), '浏览器用户');
  await nick.fill('我的新寻宝名');
  state.nickError = true;
  await board.getByRole('button', { name: '保存', exact: true }).click();
  await board.getByText('保存失败', { exact: true }).waitFor();
  state.nickError = false;
  await board.getByRole('button', { name: '保存', exact: true }).click();
  await board.getByText('我的新寻宝名', { exact: true }).waitFor();
  state.boardError = true;
  await board.getByRole('button', { name: '刷新榜单' }).click();
  await board.getByRole('button', { name: '重试', exact: true }).waitFor();
  state.boardError = false;
  await board.getByRole('button', { name: '重试', exact: true }).click();
  await board.getByText('我的新寻宝名', { exact: true }).waitFor();
  await page.screenshot({ path: resolve(output, 'leaderboard.png') });
  await board.getByRole('button', { name: '关闭排行榜' }).click();
  report.checks.push('Nickname save failure/retry; owner-only request body; leaderboard failure/retry');
  state.statsError = true;
  await page.getByRole('button', { name: '打开使用统计' }).click();
  const stats = page.getByRole('dialog', { name: '使用统计', exact: true });
  await stats.getByText(/暂不可用/).waitFor();
  state.statsError = false;
  await stats.getByRole('button', { name: '刷新统计' }).click();
  await stats.getByText(/覆盖 2 \/ 3 轮/).waitFor();
  assert.ok((await stats.textContent()).includes('125'));
  assert.ok((await stats.textContent()).includes('CygnusX 科研寻宝鼠'));
  await page.screenshot({ path: resolve(output, 'usage.png') });
  report.checks.push('Usage failure/retry; persisted token totals and explicit historical coverage');
  await page.reload();
  await page.getByRole('button', { name: '打开寻宝排行榜' }).click();
  await page.getByText('我的新寻宝名', { exact: true }).waitFor();
  assert.ok(requests.some(request => request.period === 'week'));
  assert.deepEqual(report.errors, []);
  report.checks.push('Reload preserves server nickname; no uncaught promise errors');
  console.log(JSON.stringify(report, null, 2));
} finally {
  await writeFile(resolve(output, 'browser-result.json'), JSON.stringify(report, null, 2));
  await browser?.close();
  await server?.close();
  await rm(fixture, { recursive: true, force: true });
}
