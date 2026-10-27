/** Browser acceptance of the real artifact gallery, using local scientific files.
 * ARTIFACT_TSV=/path/to/GSE280781_sample_manifest.tsv
 * PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs node scripts/poc/artifact-table-browser.mjs
 * No account or live API required; download responses are served from local files.
 */
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, mkdir, rm } from 'node:fs/promises';
import { resolve, basename } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createServer } from '../../frontend/node_modules/vite/dist/node/index.js';
import XLSX from '../../frontend/node_modules/xlsx/xlsx.js';
import Papa from '../../frontend/node_modules/papaparse/papaparse.js';

const frontend = resolve('frontend');
const fixture = await mkdtemp(resolve(frontend, '.artifact-table-'));
const output = resolve('evidence/artifact-table-preview');
await mkdir(output, { recursive: true });
const tsvPath = process.env.ARTIFACT_TSV;
assert.ok(tsvPath, 'Set ARTIFACT_TSV to the real GSE280781 sample manifest');
const tsv = await readFile(tsvPath);
const records = Papa.parse(tsv.toString('utf8'), { delimiter: '\t', skipEmptyLines: 'greedy' }).data;
assert.ok(records[0].length >= 16, 'Wide real manifest');
const derivedRecords = [records[0], ...Array.from({ length: 125 }, (_, i) => [...records[1 + i % (records.length - 1)]])];
const platformColumn = records[0].indexOf('platform');
derivedRecords[1][platformColumn] += ' / long platform description'.repeat(5);
const workbook = XLSX.utils.book_new();
XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet(records), '真实样本');
XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet([['gene', 'score'], ['TP53', 1.5]]), '基因汇总');
const samples = new Map([
  ['GSE280781_sample_manifest.tsv', tsv],
  ['manifest-125.tsv', Buffer.from(Papa.unparse(derivedRecords, { delimiter: '\t' }))],
  ['enrichment.csv', await readFile('tool_configs/enrichments/examples/tomato_enrichment_result.csv')],
  ['ScTypeDB_full.xlsx', await readFile('pipelines/scrna/Celldex/ScTypeDB_full.xlsx')],
  ['multiple.xlsx', XLSX.write(workbook, { type: 'buffer', bookType: 'xlsx' })],
  ['legacy.XLS', XLSX.write(workbook, { type: 'buffer', bookType: 'xls' })],
  ['empty.csv', Buffer.from('')],
  ['broken.xlsx', Buffer.from('broken workbook: 原始内容')],
  ['notes.txt', Buffer.from('original plain text\nsecond line')],
  ['notes.md', Buffer.from('# Original markdown\nunchanged code preview')],
  ['large.csv', Buffer.from('gene,score\nTP53,1\n' + ' '.repeat(5 * 1024 * 1024))],
]);
samples.set('large-unknown.csv', samples.get('large.csv'));
const items = [...samples].map(([path, data]) => ({ path, size: path === 'large-unknown.csv' ? undefined : data.length, url: `/api/v1/table-fixture/${path}` }));
await writeFile(resolve(fixture, 'index.html'), '<div id="app"></div><script type="module" src="./main.ts"></script>');
await writeFile(resolve(fixture, 'main.ts'), `
import { createApp } from 'vue';
import App from './App.vue';
import '@/styles/tokens.css';
import '@/styles/global.css';
import '@/styles/chat-theme.css';
createApp(App).mount('#app');
`);
await writeFile(resolve(fixture, 'App.vue'), `
<script setup>
import { ref } from 'vue';
import { NConfigProvider, NMessageProvider, darkTheme } from 'naive-ui';
import StudioArtifactsPanel from '@/components/studio/StudioArtifactsPanel.vue';
const studio = ref(false);
window.setStudio = () => { studio.value = true; };
import MessageArtifactGallery from '@/components/ai-chat/MessageArtifactGallery.vue';
const dark = ref(false);
const artifacts = ${JSON.stringify(items)};
window.setTheme = value => { dark.value = value; document.documentElement.dataset.theme = value ? 'dark' : 'light'; };
</script>
<template><NConfigProvider :theme="dark ? darkTheme : null"><NMessageProvider><main style="max-width:1000px;margin:40px auto;padding:16px"><StudioArtifactsPanel v-if="studio" session-id="fixture" /><MessageArtifactGallery v-else :artifacts="artifacts" /></main></NMessageProvider></NConfigProvider></template>
`);
const report = { checks: [], errors: [], sampleRows: records.length - 1 };
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
  const requests = [];
  await page.route('**/api/v1/table-fixture/**', route => {
    const name = decodeURIComponent(new URL(route.request().url()).pathname.split('/').pop());
    requests.push(name);
    return route.fulfill({ body: samples.get(name), contentType: 'application/octet-stream' });
  });
  await page.route('**/api/v1/studio/sessions/fixture/**', route => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith('/download')) return route.fulfill({ body: samples.get(url.searchParams.get('path')) });
    return route.fulfill({ json: { artifacts: items.map(item => ({ ...item, mtime: Date.now() / 1000 })) } });
  });
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/${basename(fixture)}/index.html`);
  await page.getByRole('button', { name: '打开产物窗口' }).click();
  async function preview(name) {
    await page.locator('.message-artifacts__files li').filter({ hasText: name }).getByRole('button', { name: '预览', exact: true }).click();
    await page.waitForTimeout(200);
  }
  const table = page.locator('.artifact-table-preview');
  await preview('GSE280781_sample_manifest.tsv');
  await table.locator('tbody tr').first().waitFor();
  assert.equal(await table.locator('th').count(), records[0].length);
  assert.equal(await table.locator('tbody tr').count(), Math.min(100, records.length - 1));
  assert.match(await table.innerText(), new RegExp(`共 ${records.length - 1} 行`));
  await page.waitForTimeout(600);
  const geometry = await table.evaluate(element => {
    const headers = [...element.querySelectorAll('th')];
    const cells = [...element.querySelectorAll('tbody tr:first-child td')];
    const aligned = headers.every((th, i) => Math.abs(th.getBoundingClientRect().width - cells[i].getBoundingClientRect().width) < 2);
    const scroller = [...element.querySelectorAll('*')].find(el => el.scrollHeight > el.clientHeight + 100 && ['auto', 'scroll'].includes(getComputedStyle(el).overflowY));
    const horizontal = [...element.querySelectorAll('*')].find(el => el.scrollWidth > el.clientWidth + 100 && ['auto', 'scroll'].includes(getComputedStyle(el).overflowX));
    const before = headers[0].getBoundingClientRect().top;
    if (scroller) scroller.scrollTop = 300;
    if (horizontal) horizontal.scrollLeft = 400;
    return { aligned, vertical: !!scroller, horizontal: !!horizontal, before };
  });
  assert.ok(geometry.aligned, 'Header/body column widths align');
  assert.ok(geometry.horizontal, 'Wide TSV can scroll horizontally');
  if (records.length > 15) assert.ok(geometry.vertical, 'TSV can scroll vertically');
  await page.waitForTimeout(100);
  const headerAfter = await table.locator('th').first().evaluate(el => el.getBoundingClientRect().top);
  report.geometry = { ...geometry, headerAfter };
  assert.ok(Math.abs(headerAfter - geometry.before) < 2, 'Header stays fixed');
  await table.evaluate(element => [...element.querySelectorAll('*')].forEach(el => { el.scrollLeft = 0; el.scrollTop = 0; }));
  await page.waitForTimeout(100);
  await page.screenshot({ path: resolve(output, 'manifest-light.png') });
  report.checks.push(`Real ${records[0].length}-column manifest: aligned columns, horizontal/vertical scroll, fixed header, correct row count`);
  await page.keyboard.press('Escape');
  for (const name of ['manifest-125.tsv', 'enrichment.csv', 'ScTypeDB_full.xlsx', 'multiple.xlsx', 'legacy.XLS']) {
    await preview(name);
    await table.locator('tbody tr').first().waitFor();
    if (name === 'manifest-125.tsv') {
      assert.equal(await table.locator('tbody tr').count(), 100);
      assert.match(await table.innerText(), /共 125 行，预览前 100 行，下载查看完整数据/);
  const longest = platformColumn;
  await table.locator('tbody tr').first().locator('td').nth(longest).locator('.n-ellipsis').hover();
  await page.waitForTimeout(600);
  assert.ok((await page.locator('.n-popover').allTextContents()).some(text => text.includes(derivedRecords[1][longest])), 'Long cell tooltip shows full content');
  report.checks.push('Long platform field tooltip shows full text');
  await page.screenshot({ path: resolve(output, 'manifest-tooltip.png') });

    }
    if (name === 'multiple.xlsx' || name === 'legacy.XLS') {
      await table.locator('.n-tabs-tab').filter({ hasText: '基因汇总' }).click();
      await page.waitForTimeout(100);
      assert.match(await table.innerText(), /TP53/);
    }
    report.checks.push(`${name}: scientific sample rendered${name.includes('multiple') || name.includes('legacy') ? ', sheet switching verified' : ''}`);
    await page.keyboard.press('Escape');
  }
  for (const [name, expected] of [['empty.csv', '该产物为空表格'], ['broken.xlsx', 'broken workbook: 原始内容'], ['notes.txt', 'original plain text'], ['notes.md', '# Original markdown']]) {
    await preview(name);
    assert.match(await page.locator('.n-modal').last().innerText(), new RegExp(expected));
    report.checks.push(`${name}: expected placeholder/fallback/original preview`);
    await page.keyboard.press('Escape');
  }
  await preview('large.csv');
  assert.ok(!requests.includes('large.csv'), 'Large file not fetched before confirmation');
  await table.getByRole('button', { name: '确认加载' }).click();
  await table.locator('tbody tr').first().waitFor();
  assert.ok(requests.includes('large.csv'));
  report.checks.push('5 MB protection: confirmation before download/parse');
  await page.keyboard.press('Escape');
  await preview('large-unknown.csv');
  await table.getByRole('button', { name: '确认加载' }).waitFor();
  assert.equal(await table.locator('table').count(), 0);
  await table.getByRole('button', { name: '确认加载' }).click();
  await table.locator('tbody tr').first().waitFor();
  assert.equal(requests.filter(name => name === 'large-unknown.csv').length, 2);
  report.checks.push('Missing manifest size: stream stopped at response headers and reloaded only after confirmation');
  await page.keyboard.press('Escape');
  const downloadEvent = page.waitForEvent('download');
  await page.locator('.message-artifacts__files li').filter({ hasText: 'GSE280781_sample_manifest.tsv' }).getByRole('button', { name: '下载', exact: true }).click();
  const download = await downloadEvent;
  assert.equal(download.suggestedFilename(), 'GSE280781_sample_manifest.tsv');
  await download.saveAs(resolve(output, 'downloaded-manifest.tsv'));
  assert.deepEqual(await readFile(resolve(output, 'downloaded-manifest.tsv')), tsv);
  report.checks.push('Download retains original filename and identical bytes');
  await page.evaluate(() => window.setTheme(true));
  await preview('GSE280781_sample_manifest.tsv');
  await table.locator('tbody tr').first().waitFor();
  const colors = await table.locator('tbody td').first().evaluate(el => ({ text: getComputedStyle(el).color, background: getComputedStyle(el).backgroundColor }));
  assert.notEqual(colors.text, 'rgb(0, 0, 0)', 'Dark table text remains readable');
  report.darkColors = colors;
  await page.screenshot({ path: resolve(output, 'manifest-dark.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: resolve(output, 'manifest-mobile.png') });
  assert.ok(await table.locator('table').count());
  report.checks.push('Light/dark desktop and mobile screenshots captured');
  await page.keyboard.press('Escape');
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.evaluate(() => window.setStudio());
  const studioItem = page.locator('.artifact-item').filter({ hasText: 'multiple.xlsx' });
  await studioItem.hover();
  await studioItem.locator('.artifact-actions button').first().click();
  await table.locator('tbody tr').first().waitFor();
  await table.locator('.n-tabs-tab').filter({ hasText: '基因汇总' }).click();
  await page.waitForTimeout(100);
  assert.match(await table.innerText(), /TP53/);
  report.checks.push('Studio panel loads the same table renderer and switches Excel sheets');
  await page.screenshot({ path: resolve(output, 'studio-excel.png') });
  assert.deepEqual(report.errors, []);
  console.log(JSON.stringify(report, null, 2));
} finally {
  await writeFile(resolve(output, 'browser-results.json'), JSON.stringify(report, null, 2));
  await browser?.close();
  await server?.close();
  await rm(fixture, { recursive: true, force: true });
}
