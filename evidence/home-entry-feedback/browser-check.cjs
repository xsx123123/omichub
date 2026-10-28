const {chromium}=require('/home/zj/.npm/_npx/e41f203b7505f1fb/node_modules/playwright');
const fs=require('fs');
(async()=>{
 const b=await chromium.launch({executablePath:'/home/zj/.cache/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell'});
 const p=await b.newPage({viewport:{width:1440,height:1000}}); const errors=[];p.on('pageerror',e=>{errors.push(e.message);console.log('PAGEERROR',e.message)});p.on('console',m=>{if(m.type()==='error')console.log('CONSOLE',m.text())});
 let created=0, oldReads=0;const old={session_id:'old-session',project_id:null,title:'已有研究',updated_at:'2026-10-25T12:00:00Z'};
 await p.route('**/api/v1/**',r=>{const path=new URL(r.request().url()).pathname;let json={items:[],total:0};
 if(path.endsWith('/research-agent/capabilities'))json={read_sessions:true,read_discovery:true,prepare_import:false};
 else if(path.endsWith('/research-agent/sessions')){if(r.request().method()==='POST'){created++;json={...old,session_id:'new-'+created,title:'新对话'};}else json=[old];}
 else if(path.includes('/research-agent/sessions/')&&path.endsWith('/messages')){oldReads++;json=[{message_id:'old-message',role:'user',content:'之前的研究问题',metadata_json:{},status:'complete'}];}
 else if(path.includes('agent-tools')&&path.endsWith('capabilities'))json={tools:[]};
 else if(path.endsWith('/projects')||path.includes('announcements'))json=[];
 else if(path.endsWith('/flows'))json={items:[{id:'rna-seq',name:'RNA-seq 分析流程',description:'标准 RNA-seq 分析',category:'rna-seq',version:'2.3.0',enabled:true,icon:'rna'}],total:1};
 else if(path.includes('festival'))json={hasFestival:false};
 r.fulfill({json});});
 await p.route('**/treasure-island/treasure-island.js*',r=>r.fulfill({path:'frontend/public/treasure-island/treasure-island.js',contentType:'application/javascript'}));
 await p.goto('http://127.0.0.1:5199/home-review.html#/');await p.locator('.hero-btn-primary').waitFor();
 for(const selector of ['.mechanism-card','.evidence-note','.pillar-card','.ecosystem-card']){
 const card=p.locator(selector).first();await card.hover();await p.waitForFunction(sel=>getComputedStyle(document.querySelector(sel),'::before').opacity==='1',selector);console.log('hover',selector,'visible');}
 await p.locator('.pillars-section').screenshot({path:'evidence/home-entry-feedback/pillars-hover.png'});
 const link=p.locator('.ecosystem-card').first();await link.focus();if(!await link.evaluate(el=>el.matches(':focus-visible')))throw Error('Missing keyboard focus');
 await p.locator('.ecosystem-section').screenshot({path:'evidence/home-entry-feedback/ecosystem-focus.png'});
 await p.emulateMedia({reducedMotion:'reduce'});await link.hover();if(await link.evaluate(el=>getComputedStyle(el).transform)!=='none')throw Error('Reduced motion lift');await p.emulateMedia({reducedMotion:'no-preference'});
 for(const [selector,planning] of [['.hero-btn-primary',false],['.hero-btn-secondary',true]]){
 const before=created;await p.locator(selector).click();await p.locator('textarea').waitFor({timeout:12000}).catch(async e=>{await p.screenshot({path:'/tmp/cta-debug.png'});console.log('PAGE',p.url(),await p.locator('body').innerText());throw e;});await p.waitForFunction(()=>{const h=document.querySelector('.original-display-host');const t=h?.shadowRoot?.querySelector('textarea');return t&&!t.disabled&&t.getRootNode().activeElement===t;});
 const draft=await p.locator('textarea').inputValue();if((planning&&!draft.includes('规划一项研究方案'))||(!planning&&draft!==''))throw Error('Incorrect draft '+draft);
 if(created!==before+1||oldReads!==0)throw Error('Incorrect session behavior '+JSON.stringify({created,oldReads}));
 if(p.url().includes('start='))throw Error('Launch not consumed');
 if(await p.locator('[data-treasure-messages]').count())throw Error('Restored old messages');
 await p.screenshot({path:`evidence/home-entry-feedback/${planning?'plan':'new'}-conversation.png`});
 await p.goBack();await p.locator('.hero-title').waitFor();if(!p.url().endsWith('#/'))throw Error('Back did not return home');console.log('launch',planning?'plan':'new','new session, focused, draft, back verified');}
 await p.getByRole('link',{name:'分析中心',exact:true}).click();await p.getByText('RNA-seq 分析流程',{exact:true}).first().waitFor();console.log('analysis center reachable with flow list');
 await p.goBack();await p.locator('.hero-title').waitFor();await p.setViewportSize({width:390,height:1000});await p.locator('.pillars-section').scrollIntoViewIfNeeded();const overflow=await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth);if(overflow)throw Error('Mobile overflow');
 await p.screenshot({path:'evidence/home-entry-feedback/mobile.png'});
 await p.goto('http://127.0.0.1:5199/home-review.html#/about');await p.locator('.vision-signoff').scrollIntoViewIfNeeded();const en=p.locator('.vision-signoff [lang=en]');if(await en.innerText()!=='From Stardust, to Discovery.')throw Error('Missing English signoff');await p.locator('.vision-section').screenshot({path:'evidence/home-entry-feedback/about-mobile.png'});await p.setViewportSize({width:1440,height:1000});await p.locator('.vision-section').screenshot({path:'evidence/home-entry-feedback/about-desktop.png'});console.log('about bilingual signoff verified');
 if(errors.length)throw Error('Page errors: '+errors.join('\n'));
 fs.writeFileSync('evidence/home-entry-feedback/browser-result.json',JSON.stringify({created,oldReads,errors,hover:true,keyboardFocus:true,reducedMotion:true,newConversation:true,planDraft:true,back:true,flowList:true,mobileOverflow:false},null,2));await b.close();
})();
