/** Real Chromium verification of the built platform presentation.
 * Uses explicit fixture props/callbacks; does not authenticate or call a live LLM.
 * PLAYWRIGHT_MODULE=/absolute/path/to/playwright/index.mjs
 * CHROMIUM_PATH=/absolute/path/to/chrome node scripts/poc/treasure-ui-browser.mjs
 */
import { createServer } from 'node:http';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { resolve, extname, sep } from 'node:path';
import { pathToFileURL } from 'node:url';
import assert from 'node:assert/strict';

const output = resolve('evidence/treasure-ui-refresh');
await mkdir(output, { recursive: true });
const root = resolve('frontend/public');
const html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,"><style>body{margin:0}#host{height:100dvh}</style></head><body><div id="host"></div><script type="module">
import {mount} from '/treasure-island/treasure-island.js';
const params=new URLSearchParams(location.search);
window.events=[];
const record=(event,value)=>events.push({event,value});
const time=new Date().toISOString();
window.props={mode:'app',context:{projectId:null,projectName:'',locale:params.get('lang')||'zh',theme:params.get('theme')||'light'},
messages:[],sessions:[{id:'history',title:'干扰素应答 · RNA-seq / Interferon response datasets',updated_at:time}],
projects:[],modelOptions:['Platform default','Alternative model'],selectedModel:'Platform default',draft:'',streaming:false,disabled:false,
onDraftChange:value=>update({draft:value}),onSubmit:value=>record('submit',value),onCancel:()=>record('cancel'),
onPickExample:value=>{record('example',value);update({draft:value})},onSelectModel:value=>update({selectedModel:value}),
onLocaleChange:locale=>update({context:{...props.context,locale}}),onThemeChange:()=>update({context:{...props.context,theme:props.context.theme==='dark'?'light':'dark'}}),
onNewSession:()=>{record('new');update({messages:[],activeSessionId:null,draft:''})},
onSelectSession:id=>{record('history',id);window.showChat()},onRenameSession:(id,title)=>record('rename',{id,title}),onArchiveSession:id=>record('archive',id),
onOpenDataset:id=>record('dataset',id)};
window.update=change=>{props={...props,...change};handle.update(props)};
window.showChat=()=>update({activeSessionId:'history',messages:[{id:'u',role:'user',content:'寻找干扰素应答相关的高通量测序数据 / Find interferon response datasets'},
{id:'a',role:'assistant',content:'## 干扰素应答相关的研究资料 / Research evidence\\n\\n这是一段用于检查回复区宽度与排版的测试内容。真实检索仍由平台原有 API 完成。\\n\\n| 编号 / Accession | 物种 / Organism | 方法 / Assay |\\n| --- | --- | --- |\\n| GSE12345 | Homo sapiens | RNA-seq |\\n| PRJNA123456 | Mus musculus | RNA-seq |\\n\\n长文本布局：'+ 'long_identifier_'.repeat(18)+'\\n\\n- 保留文献、证据与来源信息。\\n- 支持多行正文与科研编号。'}]});
window.handle=mount(document.querySelector('#host'),props);
</script></body></html>`;
const server = createServer(async (req, res) => {
  const path = new URL(req.url, 'http://local').pathname;
  if (path === '/') { res.setHeader('Content-Type', 'text/html'); res.end(html); return; }
  const file = resolve(root, path.slice(1));
  if (!file.startsWith(root + sep)) { res.writeHead(403).end(); return; }
  try {
    const types = { '.js': 'text/javascript', '.css': 'text/css', '.woff2': 'font/woff2', '.webp': 'image/webp', '.png': 'image/png' };
    res.setHeader('Content-Type', types[extname(file)] || 'application/octet-stream');
    res.end(await readFile(file));
  } catch { res.writeHead(404).end(); }
});
await new Promise(done => server.listen(0, '127.0.0.1', done));
const url = `http://127.0.0.1:${server.address().port}`;
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ? pathToFileURL(process.env.PLAYWRIGHT_MODULE).href : 'playwright');
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH, args: ['--no-sandbox'] });
const report = { checks: [], screenshots: [], errors: [] };
try {
  const page = await browser.newPage();
  page.on('pageerror', e => report.errors.push(e.message));
  page.on('console', msg => { if (msg.type() === 'error') report.errors.push(msg.text()); });
  for (const [width, height] of [[1440,900],[1280,800],[1024,768],[390,844]]) {
    await page.setViewportSize({width,height});
    for (const lang of ['zh','en']) for (const theme of ['light','dark']) {
      await page.goto(`${url}/?lang=${lang}&theme=${theme}`);
      await page.locator('.task-card').first().waitFor();
      await page.locator('.welcome-heading').scrollIntoViewIfNeeded();
      await page.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.querySelector('#host').shadowRoot.querySelectorAll('img')].map(img=>img.decode())); });
      const layout = await page.locator('.task-grid').evaluate(el => {
        const app = el.getRootNode().querySelector('[data-treasure-app]');
        const scroll = el.closest('main').querySelector('.overflow-y-auto');
        return {columns:getComputedStyle(el).gridTemplateColumns.split(' ').length,overflow:app.scrollWidth>app.clientWidth,innerOverflow:scroll.scrollWidth>scroll.clientWidth};
      });
      assert.equal(layout.overflow,false,`${width}/${lang}/${theme} app overflow`);
      assert.equal(layout.innerOverflow,false,`${width}/${lang}/${theme} workspace overflow`);
      assert.equal(layout.columns,width<640?1:2);
      assert.equal(await page.locator('.task-card').count(),4);
      assert.equal(await page.locator('.pet-welcome-bubble').count(),0);
      const name=`welcome-${width}-${lang}-${theme}.png`;
      await page.screenshot({path:resolve(output,name)}); report.screenshots.push(name);
      await page.evaluate(()=>showChat());
      const reply = page.locator('[data-treasure-messages]');
      assert.equal(await reply.evaluate(el=>el.scrollWidth>el.clientWidth),false,'Long reply overflow');
      const replyWidth = await reply.evaluate(el=>el.getBoundingClientRect().width);
      if(width===1440) assert.ok(replyWidth>=950,`Reply remains narrow: ${replyWidth}`);
      if(lang==='zh') {
        const chatName=`chat-${width}-${theme}.png`;
        await page.screenshot({path:resolve(output,chatName)});report.screenshots.push(chatName);
      }
    }
    report.checks.push(`${width}×${height}: zh/en, light/dark, welcome/chat, columns, overflow, images`);
  }
  await page.setViewportSize({width:1440,height:900});
  await page.goto(url);
  await page.locator('textarea').waitFor();
  await page.locator('.task-example').first().click();
  await page.waitForFunction(()=>document.querySelector('#host').shadowRoot.querySelector('textarea').value.length>0);
  assert.ok((await page.locator('textarea').inputValue()).length>0);
  await page.locator('textarea').fill('研究问题 GSE12345');await page.locator('textarea').press('Enter');
  assert.ok(await page.evaluate(()=>events.some(e=>e.event==='submit'&&e.value==='研究问题 GSE12345')));
  await page.locator('.composer-model').selectOption('Alternative model');
  assert.equal(await page.evaluate(()=>props.selectedModel),'Alternative model');
  assert.equal(await page.getByRole('button',{name:'展开会话列表',exact:true}).count(),1);
  await page.getByRole('button',{name:'展开会话列表',exact:true}).click();
  await page.getByRole('button',{name:'收起会话列表',exact:true}).click();
  await page.getByRole('button',{name:'展开会话列表',exact:true}).click();
  await page.getByRole('button',{name:'干扰素应答 · RNA-seq / Interferon response datasets',exact:true}).click();
  await page.locator('[data-treasure-messages]').waitFor();
  await page.getByRole('button',{name:'新建对话',exact:true}).click();
  await page.locator('.task-grid').waitFor();
  const search=page.locator('.session-sidebar input').first();
  await search.fill('no matching history');
  assert.equal(await page.getByRole('button',{name:'干扰素应答 · RNA-seq / Interferon response datasets',exact:true}).count(),0);
  await search.fill('');
  await page.getByRole('button',{name:'切换到英文',exact:true}).click();
  assert.equal(await page.evaluate(()=>props.context.locale),'en');
  await page.evaluate(()=>update({context:{...props.context,locale:'zh'}}));
  await page.getByRole('button',{name:'切换主题',exact:true}).click();
  assert.equal(await page.evaluate(()=>props.context.theme),'dark');
  await page.evaluate(()=>update({streaming:true}));
  await page.locator('.composer button').filter({has:page.locator('svg')}).last().click();
  assert.ok(await page.evaluate(()=>events.some(e=>e.event==='cancel')));
  await page.evaluate(()=>update({streaming:false,disabled:true}));
  assert.equal(await page.locator('textarea').isDisabled(),true);
  assert.equal(await page.locator('.task-example:disabled').count(),8);
  await page.evaluate(()=>update({disabled:false,accessError:'权限暂不可用，请刷新后重试',streamError:'连接中断，草稿已保留'}));
  await page.getByRole('alert').waitFor();
  await page.evaluate(()=>update({accessError:null,streamError:null}));
  await page.getByRole('button',{name:'桌宠设置',exact:true}).click();
  await page.getByRole('button',{name:'找回阿寻',exact:true}).click();
  await page.getByRole('group',{name:'寻宝鼠阿寻',exact:true}).waitFor();
  await page.getByRole('group',{name:'寻宝鼠阿寻',exact:true}).click({button:'right'});
  await page.getByRole('group',{name:'寻宝鼠阿寻',exact:true}).waitFor({state:'detached'});
  await page.locator('.welcome-content > div button').first().click({clickCount:3});
  await page.getByRole('dialog').waitFor();await page.keyboard.press('Escape');
  await page.getByRole('dialog').waitFor({state:'detached'});
  await page.setViewportSize({width:390,height:844});
  await page.getByRole('button',{name:'打开会话列表',exact:true}).click();
  await page.locator('.session-sidebar:visible').waitFor();
  await page.getByRole('button',{name:'新建对话',exact:true}).click();
  assert.equal(await page.locator('.session-sidebar:visible').count(),0);
  await page.emulateMedia({reducedMotion:'reduce'});
  assert.equal(await page.locator('.pet-idle').first().evaluate(el=>getComputedStyle(el).animationName),'none');
  report.checks.push('Example → draft; input/Enter → owner; model; collapse/expand; history/new/search; locale/theme; stop/disabled/error; pet recall/quiet; scoped Easter egg/Escape; mobile drawer; reduced motion');
  assert.deepEqual(report.errors,[]);
} finally {
  await browser.close();await new Promise(done=>server.close(done));
  await writeFile(resolve(output,'browser-result.json'),JSON.stringify(report,null,2)+'\n');
}
console.log(JSON.stringify(report,null,2));
