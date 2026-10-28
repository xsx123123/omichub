const http=require('http'),fs=require('fs'),path=require('path');
const {chromium}=require('/home/zj/.npm/_npx/e41f203b7505f1fb/node_modules/playwright');
(async()=>{
 const counters={capabilities:0,sessions:0,messages:0,streams:0,titles:0,prematureAbort:false};
 const root=path.resolve('frontend/dist');let finished=false;
 const session={session_id:'ui-focus-session',title:'界面稳定性验证',project_id:null,updated_at:'2026-10-26T02:00:00Z'};
 const json=(res,value)=>{res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify(value));};
 const server=http.createServer((req,res)=>{const u=new URL(req.url,'http://localhost'),p=u.pathname;
 if(p.startsWith('/api/v1/')){
  if(p.endsWith('/welcome/claim')){res.writeHead(204);res.end();return;}
  if(p.endsWith('/auth/setup-required'))return json(res,{setup_required:false});
  if(p.endsWith('/auth/me'))return json(res,{id:'ui-fixture',username:'界面验证',nickname:'界面验证',role:'user',is_active:true,disabled_modules:[]});
  if(p.endsWith('/modules/registry'))return json(res,{modules:[]});
  if(p.includes('/notifications')||p.includes('announcements'))return json(res,[]);
  if(p.endsWith('/site-content'))return json(res,JSON.parse(fs.readFileSync('/tmp/github-links-content.json','utf8')));
  if(p.endsWith('/site-settings'))return json(res,{registration_enabled:true});
  if(p.endsWith('/research-agent/capabilities')){counters.capabilities++;return setTimeout(()=>json(res,{read_sessions:true,read_discovery:true,prepare_import:false}),100);}
  if(p.endsWith('/research-agent/sessions')){counters.sessions++;return json(res,[session]);}
  if(p.includes('/research-agent/sessions/')&&p.endsWith('/messages')){counters.messages++;return json(res,finished?[{message_id:'old-read',role:'assistant',content:'这是从历史重新读取的回复',metadata_json:{},status:'complete'}]:[]);}
  if(p.includes('/research-agent/sessions/')&&p.endsWith('/messages:stream')){
   counters.streams++;res.writeHead(200,{'Content-Type':'text/event-stream','Cache-Control':'no-cache'});res.flushHeaders();
   res.on('close',()=>{if(!res.writableEnded)counters.prematureAbort=true;});
   res.write('data: {"event":"delta","delta":"这是用于界面验证的前半段回复。"}\n\n');
   setTimeout(()=>{if(!res.destroyed)res.write('data: {"event":"delta","delta":"后半段回复保持完整，未重新打开欢迎页。"}\n\n');},700);
   setTimeout(()=>{if(!res.destroyed){finished=true;res.end('data: {"event":"end"}\n\n');}},1100);return;
  }
  if(p.endsWith('/generate-title')){counters.titles++;return setTimeout(()=>json(res,{title:'稳定保留的研究对话'}),500);}
  if(p.includes('/agent-tools/')&&p.endsWith('/capabilities'))return json(res,{tools:[]});
  if(p.endsWith('/projects'))return json(res,[]);
  if(p.includes('balance')||p.includes('account'))return json(res,{balance:1000,available_balance:1000});
  return json(res,{items:[],total:0});
 }
 let file=path.resolve(root,'.'+decodeURIComponent(p));if(!file.startsWith(root)||!fs.existsSync(file)||fs.statSync(file).isDirectory())file=path.join(root,'index.html');
 const types={'.html':'text/html','.js':'application/javascript','.css':'text/css','.woff2':'font/woff2','.woff':'font/woff','.webp':'image/webp','.png':'image/png','.svg':'image/svg+xml'};res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream'});fs.createReadStream(file).pipe(res);
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({executablePath:'/home/zj/.cache/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell'});
 try{
 const context=await browser.newContext({viewport:{width:1440,height:1000}});await context.addInitScript(()=>{localStorage.setItem('access_token','ui-fixture-only');localStorage.setItem('cygnusx-theme','light');localStorage.setItem('cygnusx:ai-sidebar-hint-seen','1');});
 const p=await context.newPage(),errors=[];p.on('pageerror',e=>{errors.push(e.message);console.log('PAGEERROR',e.message)});
 await p.goto(`http://127.0.0.1:${server.address().port}/treasure-mouse`);await p.locator('textarea:not(:disabled)').waitFor();
 const expand=p.getByRole('button',{name:'展开会话列表',exact:true});await expand.waitFor();if(await p.locator('.session-sidebar:visible').count())throw Error('History not collapsed by default');
 await p.screenshot({path:'evidence/treasure-focus-stability/default-collapsed.png'});await expand.click();await p.locator('.session-sidebar:visible').waitFor();
 const baseline={sessions:counters.sessions,messages:counters.messages};
 await p.evaluate(()=>{const root=document.querySelector('.original-display-host').shadowRoot;window.replyTrace={started:false,emptyFrames:0,paths:[]};new MutationObserver(()=>{const has=!!root.querySelector('[data-treasure-messages]');if(has)window.replyTrace.started=true;if(window.replyTrace.started&&!has)window.replyTrace.emptyFrames++;window.replyTrace.paths.push(location.pathname);}).observe(root,{subtree:true,childList:true});});
 await p.locator('textarea').fill('请进行界面稳定性验证');await p.getByRole('button',{name:'下铲挖宝',exact:true}).click();await p.getByText('这是用于界面验证的前半段回复。',{exact:false}).first().waitFor();
 await p.evaluate(()=>window.dispatchEvent(new Event('focus')));await p.getByRole('button',{name:'停止生成',exact:true}).waitFor();
 await p.getByText('后半段回复保持完整，未重新打开欢迎页。',{exact:false}).first().waitFor();await p.getByRole('button',{name:'停止生成',exact:true}).waitFor({state:'hidden'});
 await p.evaluate(()=>{window.dispatchEvent(new Event('focus'));window.dispatchEvent(new Event('focus'));});
 await p.getByText('稳定保留的研究对话',{exact:true}).first().waitFor();await p.waitForTimeout(350);
 if(!await p.getByRole('button',{name:'收起会话列表',exact:true}).isVisible())throw Error('Manual expansion was reset by response updates');
 const trace=await p.evaluate(()=>window.replyTrace);if(trace.emptyFrames||trace.paths.some(p=>p!=='/treasure-mouse'))throw Error('Reply/home flicker '+JSON.stringify(trace));
 if(counters.sessions!==baseline.sessions||counters.messages!==baseline.messages||counters.streams!==1||counters.titles!==1||counters.prematureAbort)throw Error('Unexpected session reload or stream abort '+JSON.stringify(counters));
 await p.getByRole('button',{name:'收起会话列表',exact:true}).click();await p.screenshot({path:'evidence/treasure-focus-stability/completed-reply-collapsed.png'});
 await p.setViewportSize({width:390,height:1000});await p.getByRole('button',{name:'打开会话列表',exact:true}).click();await p.locator('.session-sidebar:visible').waitFor();await p.getByRole('button',{name:'关闭文献卡片',exact:true}).click();await p.locator('.session-sidebar:visible').waitFor({state:'hidden'});if(await p.locator('.session-sidebar:visible').count())throw Error('Mobile drawer did not close');await p.screenshot({path:'evidence/treasure-focus-stability/mobile-reply.png'});
 if(errors.length)throw Error(errors.join('\n'));
 fs.writeFileSync('evidence/treasure-focus-stability/browser-result.json',JSON.stringify({productionApp:true,defaultCollapsed:true,manualExpandPreserved:true,mobileDrawer:true,counters,baseline,trace,errors},null,2));console.log('Production App + real SSE verified: focus during/after reply causes zero empty frames, zero session reloads, no abort; default sidebar collapsed; manual expansion and mobile drawer work.');
 }finally{await browser.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
})();
