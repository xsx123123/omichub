/** Real browser regression for the Vue/React draft echo and the Vue chat inputs.
 * PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs CHROMIUM_PATH=/path/to/chrome
 * node scripts/poc/chat-input-editing-browser.mjs
 * Uses real components with isolated stores; no live account, API or model.
 */
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, mkdir, rm } from 'node:fs/promises';
import { resolve, basename } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createServer } from '../../frontend/node_modules/vite/dist/node/index.js';

const frontend = resolve('frontend');
const fixture = await mkdtemp(resolve(frontend, '.input-editing-'));
const output = resolve('evidence/chat-input-editing');
await mkdir(output, { recursive: true });
await writeFile(resolve(fixture, 'index.html'), '<div id="app"></div><script type="module" src="./main.ts"></script>');
await writeFile(resolve(fixture, 'main.ts'), `
import { createApp } from 'vue';
import { createPinia } from 'pinia';
import { createRouter, createMemoryHistory } from 'vue-router';
import App from './App.vue';
const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { render: () => null } }] });
await router.push('/');
createApp(App).use(createPinia()).use(router).mount('#app');
`);
await writeFile(resolve(fixture, 'App.vue'), `
<script setup>
import { ref, nextTick, onMounted } from 'vue';
import { NMessageProvider, NDialogProvider } from 'naive-ui';
import KimiChatInput from '@/components/ai-chat/KimiChatInput.vue';
import Sidebar from '@/components/ai-assistant/GlobalAiAssistantSidebar.vue';
import Treasure from '@/components/research/TreasureOriginalDisplay.vue';
import { useAiAssistantSidebarStore } from '@/stores/aiAssistantSidebar';
import { useAgentHubStore } from '@/stores/agentHub';
const draft = ref(''), assistant = ref(''), studio = ref(''), messages = ref([]);
const theme = ref('light');
const sidebar = useAiAssistantSidebarStore();
sidebar.ensureModels = async () => {};
useAgentHubStore().fetchRuntimeProfiles = async () => {};
window.sends = [];
sidebar.sendOrQueue = async text => { window.sends.push(text); return 'queued'; };
sidebar.modelId = 'fixture-model';
window.setChat = () => { messages.value = [{ id: 'reply', role: 'assistant', content: 'fixture reply' }]; };
window.externalDraft = value => { draft.value = value; };
window.refreshPresentation = () => { theme.value = theme.value === 'light' ? 'dark' : 'light'; };
onMounted(async () => { await nextTick(); sidebar.open = true; });
</script>
<template>
  <NMessageProvider><NDialogProvider>
    <div id="treasure" style="height:700px"><Treasure mode="app" v-model:draft="draft" :disabled="false" :streaming="false" :project-id="null" :presentation="{ messages, context: { projectId: null, projectName: '', locale: 'zh', theme } }" /></div>
    <div id="assistant"><KimiChatInput v-model="assistant" /></div>
    <div id="studio"><KimiChatInput v-model="studio" /></div>
    <Sidebar />
  </NDialogProvider></NMessageProvider>
</template>
`);
let server, browser;
const report = { checks: [], errors: [] };
try {
  server = await createServer({ configFile: resolve(frontend, 'vite.config.ts'), root: frontend,
    plugins: [{ name: 'built-island-fixture', configureServer(vite) {
      // Serve the already-built Island as production does, including Vite's ?import query.
      vite.middlewares.use(async (req, res, next) => {
        if (req.url?.split('?')[0] !== '/treasure-island/treasure-island.js') return next();
        res.setHeader('Content-Type', 'text/javascript');
        res.end(await readFile(resolve(frontend, 'public/treasure-island/treasure-island.js')));
      });
    } }],
    optimizeDeps: { entries: [resolve(fixture, 'index.html')] },
    server: { host: '127.0.0.1', port: 0, open: false }, logLevel: 'error' });
  await server.listen();
  const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : 'playwright');
  browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.on('console', message => { if (message.type() === 'error') console.error(message.text()); });
  page.on('requestfailed', request => console.error(request.url(), request.failure()));
  page.on('pageerror', error => report.errors.push(error.message));
  await page.route('**/api/v1/**', route => route.fulfill({ json: { data: [], items: [], profiles: [] } }));
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/${basename(fixture)}/index.html`);
  await page.waitForFunction(() => document.querySelector('#treasure .original-display-host')?.shadowRoot?.querySelector('textarea'), { timeout: 30000 }).catch(async error => {
    console.error(await page.content());
    throw error;
  });
  async function select(input, start, end = start) {
    await input.focus();
    await input.evaluate((el, [a, b]) => el.setSelectionRange(a, b), [start, end]);
  }
  async function check(input, name) {
    await input.fill('ABCDEFGH');
    await select(input, 2);
    await input.pressSequentially('123', { delay: 40 });
    assert.equal(await input.inputValue(), 'AB123CDEFGH', name + ': middle insertion');
    assert.equal(await input.evaluate(el => el.selectionStart), 5, name + ': caret');
    await select(input, 2, 5);
    await input.pressSequentially('xy', { delay: 40 });
    assert.equal(await input.inputValue(), 'ABxyCDEFGH', name + ': selected replacement');
    await select(input, 3);
    await input.press('Backspace');
    await input.press('Delete');
    assert.equal(await input.inputValue(), 'ABCDEFGH', name + ': middle deletion');
    await input.fill('寻找相关数据');
    await select(input, 2);
    await page.keyboard.insertText('小鼠');
    await page.keyboard.insertText('肝脏');
    assert.equal(await input.inputValue(), '寻找小鼠肝脏相关数据', name + ': Chinese insertion');
    await select(input, 2);
    await input.press('Shift+Enter');
    await input.pressSequentially('RNA');
    assert.equal(await input.inputValue(), '寻找\nRNA小鼠肝脏相关数据', name + ': multiline editing');
    report.checks.push(name + ': insertion, replacement, caret, deletion, Chinese text, multiline');
  }
  await check(page.locator('#treasure textarea'), 'Treasure welcome');
  await page.evaluate(() => window.setChat());
  const treasure = page.locator('#treasure textarea');
  await check(treasure, 'Treasure conversation');
  await select(treasure, 1, 3);
  await page.evaluate(() => window.refreshPresentation());
  assert.deepEqual(await treasure.evaluate(el => [el.selectionStart, el.selectionEnd]), [1, 3]);
  await page.evaluate(() => window.externalDraft('external prefill'));
  await page.waitForFunction(() => document.querySelector('#treasure .original-display-host').shadowRoot.querySelector('textarea').value === 'external prefill');
  // CDP sends actual browser composition updates (system IME itself is not automated).
  await treasure.fill('ABCD');
  await select(treasure, 2);
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Input.imeSetComposition', { text: 'zhong', selectionStart: 5, selectionEnd: 5 });
  await cdp.send('Input.imeSetComposition', { text: '中文', selectionStart: 2, selectionEnd: 2 });
  await cdp.send('Input.insertText', { text: '中文' });
  await page.keyboard.insertText('插入');
  assert.equal(await treasure.inputValue(), 'AB中文插入CD');
  report.checks.push('Treasure: unrelated render preserves selection; external prefill; CDP composition in middle');
  await check(page.locator('#assistant textarea'), 'AI assistant shared KimiChatInput');
  await check(page.locator('#studio textarea'), 'AI studio shared KimiChatInput');
  const sidebar = page.locator('.ai-sidebar textarea');
  await check(sidebar, 'AI sidebar');
  await sidebar.dispatchEvent('compositionstart');
  await sidebar.dispatchEvent('keydown', { key: 'Enter', isComposing: true });
  await sidebar.dispatchEvent('compositionend');
  await sidebar.dispatchEvent('keydown', { key: 'Enter' });
  assert.equal(await page.evaluate(() => window.sends.length), 0, 'IME confirmation must not send');
  await page.waitForTimeout(220);
  await sidebar.press('Enter');
  assert.equal(await page.evaluate(() => window.sends.length), 1, 'ordinary Enter still sends');
  report.checks.push('AI sidebar: IME Enter guarded; normal Enter sends');
  assert.deepEqual(report.errors, []);
  console.log(JSON.stringify(report, null, 2));
} finally {
  await writeFile(resolve(output, 'browser-result.json'), JSON.stringify(report, null, 2));
  await browser?.close();
  await server?.close();
  await rm(fixture, { recursive: true, force: true });
}
