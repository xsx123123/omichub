/** Verify the supplied CygnusX wordmark in the real desktop/mobile layout.
 * PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs CHROMIUM_PATH=/path/to/chrome
 * node scripts/poc/platform-logo-browser.mjs
 */
import assert from 'node:assert/strict';
import { mkdtemp, readFile, writeFile, mkdir, rm } from 'node:fs/promises';
import { resolve, basename } from 'node:path';
import { pathToFileURL } from 'node:url';
import { createServer } from '../../frontend/node_modules/vite/dist/node/index.js';

const frontend = resolve('frontend');
const fixture = await mkdtemp(resolve(frontend, '.platform-logo-'));
const output = resolve('evidence/platform-logo');
await mkdir(output, { recursive: true });
assert.deepEqual(await readFile('frontend/public/cygnusx-wordmark.png'), await readFile('docs/logo/天鹅星环科技标志.png'));
await writeFile(resolve(fixture, 'index.html'), '<div id="app"></div><script type="module" src="./main.ts"></script>');
await writeFile(resolve(fixture, 'main.ts'), `
import { createApp } from 'vue';
import { createPinia } from 'pinia';
import { createRouter, createMemoryHistory } from 'vue-router';
import App from './App.vue';
import '@/styles/tokens.css';
import '@/styles/global.css';
import '@/styles/chat-theme.css';
const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { render: () => null } }] });
await router.push('/');
createApp(App).use(createPinia()).use(router).mount('#app');
`);
await writeFile(resolve(fixture, 'App.vue'), `
<script setup>
import { ref } from 'vue';
import { NConfigProvider, NMessageProvider, NDialogProvider, NNotificationProvider, darkTheme } from 'naive-ui';
import DefaultLayout from '@/layouts/DefaultLayout.vue';
const dark = ref(false);
window.setTheme = value => { dark.value = value; document.documentElement.dataset.theme = value ? 'dark' : 'light'; };
</script>
<template><NConfigProvider :theme="dark ? darkTheme : null"><NMessageProvider><NDialogProvider><NNotificationProvider><DefaultLayout /></NNotificationProvider></NDialogProvider></NMessageProvider></NConfigProvider></template>
`);
let server, browser;
const report = { checks: [], errors: [] };
try {
  server = await createServer({ configFile: resolve(frontend, 'vite.config.ts'), root: frontend,
    optimizeDeps: { entries: [resolve(fixture, 'index.html')] },
    server: { host: '127.0.0.1', port: 0, open: false }, logLevel: 'error' });
  await server.listen();
  const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : 'playwright');
  browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.on('pageerror', error => report.errors.push(error.message));
  await page.route('**/api/v1/**', route => route.fulfill({ json: { data: [], items: [], modules: [], profiles: [] } }));
  await page.goto(`http://127.0.0.1:${server.httpServer.address().port}/${basename(fixture)}/index.html`);
  const logo = page.locator('.top-nav .platform-brand-logo');
  await logo.waitFor();
  await logo.evaluate(img => img.decode());
  await page.evaluate(() => window.setTheme(false));
  await page.waitForTimeout(300);
  assert.equal(await logo.getAttribute('alt'), 'CygnusX');
  assert.equal(await page.locator('.logo-block .logo-text').count(), 0);
  const dimensions = await logo.evaluate(img => ({ width: img.naturalWidth, height: img.naturalHeight, renderedHeight: img.height }));
  assert.equal(dimensions.width / dimensions.height, 3);
  assert.ok(dimensions.renderedHeight <= 56);
  await page.screenshot({ path: resolve(output, 'desktop-light.png') });
  report.checks.push('Desktop uses the exact supplied image, correct aspect ratio and accessible name, without duplicated wordmark');
  await page.evaluate(() => window.setTheme(true));
  await page.waitForTimeout(300);
  await page.screenshot({ path: resolve(output, 'desktop-dark.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator('.hamburger-btn').click();
  const drawerLogo = page.locator('.mobile-logo .platform-brand-logo');
  await drawerLogo.waitFor();
  await drawerLogo.evaluate(img => img.decode());
  await page.waitForTimeout(300);
  await page.screenshot({ path: resolve(output, 'mobile-drawer.png') });
  report.checks.push('Dark theme and 390px mobile drawer render the same complete logo');
  assert.deepEqual(report.errors, []);
  console.log(JSON.stringify(report, null, 2));
} finally {
  await writeFile(resolve(output, 'browser-results.json'), JSON.stringify(report, null, 2));
  await browser?.close();
  await server?.close();
  await rm(fixture, { recursive: true, force: true });
}
