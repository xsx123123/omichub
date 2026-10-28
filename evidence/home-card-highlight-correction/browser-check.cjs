const {chromium}=require('/home/zj/.npm/_npx/e41f203b7505f1fb/node_modules/playwright');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({executablePath:'/home/zj/.cache/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell'});
 const context=await browser.newContext({viewport:{width:1440,height:1000}});await context.addInitScript(()=>{localStorage.setItem('access_token','ui-fixture-only');localStorage.setItem('cygnusx:sidebar-expanded','false');localStorage.setItem('cygnusx-theme','light');localStorage.setItem('cygnusx:ai-sidebar-hint-seen','1');});
 const p=await context.newPage();p.on('popup',popup=>void popup.close());const errors=[];p.on('pageerror',e=>{errors.push(e.message);console.log('PAGEERROR',e.message)});
 await context.route('https://github.com/**',r=>r.abort());
 await context.route('**/api/v1/**',r=>{const u=new URL(r.request().url()),path=u.pathname;let json={items:[],total:0};
 if(path.endsWith('/auth/setup-required'))json={setup_required:false};
 else if(path.endsWith('/auth/me'))json={id:'ui-only',username:'UI 验证',nickname:'UI 验证',role:'user',is_active:true,disabled_modules:[]};
 else if(path.endsWith('/modules/registry'))json={modules:[]};
 else if(path.includes('/notifications')||path.includes('announcements'))json=[];
 else if(path.endsWith('/site-content'))json=JSON.parse(fs.readFileSync('/tmp/github-links-content.json','utf8'));
 else if(path.endsWith('/site-settings'))json={registration_enabled:true,collaboration_enabled:false};
 else if(path.includes('/festival'))json={hasFestival:false};
 else if(path.endsWith('/projects'))json=['数据可视化研究','variant','rna-seq'].map((name,i)=>({id:'p'+i,name,slug:'p'+i,description:'项目工作区',created_at:'2026-09-25T08:00:00Z',updated_at:'2026-09-25T12:00:00Z'}));
 else if(path.endsWith('/tasks'))json={items:[{id:'task-'+u.searchParams.get('status'),name:'RNA-seq 数据分析',status:u.searchParams.get('status'),flow_id:'rna_seq',created_at:'2026-10-25T10:00:00Z'}],total:1};
 else if(path.endsWith('/reports'))json={items:[{id:'report-1',title:'转录组分析报告',flow_name:'RNA-seq',status:'completed',created_at:'2026-10-25T10:00:00Z'}],total:1};
 else if(path.includes('balance')||path.includes('account'))json={balance:1000,available_balance:1000,frozen_balance:0};
 r.fulfill({json});});
 await p.goto(process.env.CARD_REVIEW_URL||'http://127.0.0.1:5199/');await p.locator('.workbench-card').first().waitFor({timeout:30000});await p.locator('.workbench-items').first().waitFor();
 const selectors=['.workbench-card','.entry-card','.mechanism-card','.evidence-note','.pillar-card','.ecosystem-card'];const hover={},selected={};
 async function state(sel){return p.locator(sel).first().evaluate(el=>{const s=getComputedStyle(el),bar=getComputedStyle(el,'::before'),after=getComputedStyle(el,'::after');return {background:s.backgroundImage,color:s.backgroundColor,border:s.borderColor,shadow:s.boxShadow,marker:{left:bar.left,width:bar.width,top:bar.top,bottom:bar.bottom,opacity:bar.opacity,color:bar.backgroundColor},transform:s.transform,after:after.content,arrows:Array.from(el.querySelectorAll('.card-state-arrow')).map(a=>getComputedStyle(a).color)};});}
 for(const sel of selectors){console.log('hover',sel);await p.locator(sel).first().hover();await p.waitForFunction(sel=>getComputedStyle(document.querySelector(sel)).backgroundColor==='rgb(248, 250, 255)'&&getComputedStyle(document.querySelector(sel)).transform==='matrix(1, 0, 0, 1, 0, -1)',sel);hover[sel]=await state(sel);if(hover[sel].marker.opacity!=='0')throw Error('Hover marker '+sel);}
 await p.locator('.workbench-card').first().hover();await p.waitForTimeout(250);await p.screenshot({path:'evidence/home-card-highlight-correction/workbench-hover-full-page.png'});
 // Actual clicks for information cards; navigation cards are checked in their real pressed state.
 for(const sel of selectors){const card=p.locator(sel).first();
  if(sel==='.entry-card'||sel==='.ecosystem-card'){await card.hover();await p.mouse.down();}
  else if(sel==='.workbench-card')await card.click({position:{x:14,y:14}});
  else await card.click();
  await p.waitForFunction(sel=>getComputedStyle(document.querySelector(sel),'::before').opacity==='1',sel);selected[sel]=await state(sel);
  if(sel==='.entry-card'||sel==='.ecosystem-card'){const r=await card.boundingBox();await p.mouse.move(r.x+r.width+10,r.y+10);await p.mouse.up();}
 }
 const reference=selected['.entry-card'];for(const sel of selectors){const a=selected[sel];if(a.background!==reference.background||a.border!==reference.border||a.shadow!==reference.shadow||a.marker.left!=='6px'||a.marker.width!=='4px'||a.arrows.some(c=>c!=='rgb(79, 110, 247)'))throw Error('Selected mismatch '+sel+JSON.stringify(a));}
 if(hover['.workbench-card'].after!=='none')throw Error('Legacy heavy shadow remains');
 const homeOverflow=await p.locator('.home-page').evaluate(el=>getComputedStyle(el).overflowX);if(homeOverflow!=='visible')throw Error('Home clips shadows');
 await p.locator('.mechanism-card').first().click();await p.locator('.mechanism-section').scrollIntoViewIfNeeded();await p.waitForTimeout(250);await p.screenshot({path:'evidence/home-card-highlight-correction/mechanism-selected-full-page.png'});
 // Keep surrounding page margin in every capture: do not crop the evidence at the card edge.
 await p.locator('.workbench-card').first().scrollIntoViewIfNeeded();await p.waitForTimeout(250);await p.screenshot({path:'evidence/home-card-highlight-correction/workbench-selected-full-page.png'});
 const marker=await p.locator('.workbench-card').first().screenshot();
 const pixels=await p.evaluate(async data=>{const im=new Image();im.src=data;await im.decode();const c=document.createElement('canvas');c.width=im.width;c.height=im.height;const ctx=c.getContext('2d');ctx.drawImage(im,0,0);return Array.from({length:14},(_,x)=>Array.from(ctx.getImageData(x,Math.floor(c.height/2),1,1).data).slice(0,3));},'data:image/png;base64,'+marker.toString('base64'));
 const columns=pixels.flatMap((rgb,x)=>JSON.stringify(rgb)==='[99,102,241]'?[x]:[]);if(columns.length!==4||columns[0]<6)throw Error('Marker not fully inset '+JSON.stringify(pixels));
 await p.emulateMedia({reducedMotion:'reduce'});await p.locator('.pillar-card').nth(3).hover();if(await p.locator('.pillar-card').nth(3).evaluate(el=>getComputedStyle(el).transform)!=='none')throw Error('Reduced motion');
 for(const width of [1280,820,390]){await p.setViewportSize({width,height:1000});await p.locator('.mechanism-section').scrollIntoViewIfNeeded();if(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Page overflow '+width);await p.screenshot({path:'evidence/home-card-highlight-correction/home-'+width+'.png'});}
 if(errors.length)throw Error(errors.join('\n'));
 fs.writeFileSync('evidence/home-card-highlight-correction/browser-result.json',JSON.stringify({realApp:true,realLayout:true,hover,selected,homeOverflow,markerColumns:columns,mobileOverflow:false,reducedMotion:true,errors},null,2));console.log('Actual App + DefaultLayout verified: 6 card groups share hover/selected styles; inset marker fully visible; shadows unclipped; 1280/820/390px fit.');await browser.close();
})();
