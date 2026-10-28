const {chromium}=require('/home/zj/.npm/_npx/e41f203b7505f1fb/node_modules/playwright');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({executablePath:'/home/zj/.cache/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell'});
 const p=await browser.newPage({viewport:{width:1440,height:1050}});const errors=[];p.on('pageerror',e=>errors.push(e.message));
 await p.route('**/api/v1/**',r=>{const u=r.request().url();r.fulfill({json:u.includes('projects')||u.includes('announcements')?[]:u.includes('festival')?{hasFestival:false}:{items:[],total:0}})});
 await p.goto('http://127.0.0.1:5199/card-review.html#/');await p.locator('.entry-card').first().waitFor();
 const style=async selector=>p.locator(selector).first().evaluate(el=>{const s=getComputedStyle(el),b=getComputedStyle(el,'::before'),arrow=el.querySelector('.card-state-arrow');return {background:s.backgroundImage,color:s.backgroundColor,border:s.borderTopColor,borderLeft:s.borderLeftColor,borderWidth:s.borderTopWidth,borderStyle:s.borderTopStyle,arrow:arrow?getComputedStyle(arrow).color:null,bar:{left:b.left,top:b.top,bottom:b.bottom,width:b.width,radius:b.borderRadius,opacity:b.opacity,color:b.backgroundColor,transform:b.transform},overflow:s.overflow,transform:s.transform,transitionDuration:s.transitionDuration};});
 const groups=['.entry-card','.pillar-card','.ecosystem-card'];const defaults={},hover={},selected={};
 for(const selector of groups){
  defaults[selector]=await style(selector);await p.locator(selector).first().hover();
  await p.waitForFunction(sel=>getComputedStyle(document.querySelector(sel)).backgroundColor==='rgb(248, 250, 255)'&&getComputedStyle(document.querySelector(sel)).transform==='matrix(1, 0, 0, 1, 0, -1)',selector);
  hover[selector]=await style(selector);
  if(hover[selector].bar.opacity!=='0'||hover[selector].background!=='none'||hover[selector].transform!=='matrix(1, 0, 0, 1, 0, -1)')throw Error('Hover is selected '+JSON.stringify(hover[selector]));
  await p.locator(selector).first().click();await p.mouse.move(1430,10);
  await p.waitForFunction(sel=>getComputedStyle(document.querySelector(sel),'::before').opacity==='1',selector);
  selected[selector]=await style(selector);
  const a=selected[selector];if(a.background!=='linear-gradient(135deg, rgb(245, 247, 255) 0%, rgb(238, 241, 255) 100%)'||a.border!=='rgb(199, 210, 254)'||a.borderLeft!==a.border||a.borderWidth!=='1px'||a.borderStyle!=='solid'||a.arrow!=='rgb(79, 110, 247)'||a.bar.width!=='4px'||a.bar.left!=='0px'||a.bar.top!=='12px'||a.bar.bottom!=='12px'||a.bar.radius!=='2px'||a.bar.color!=='rgb(99, 102, 241)'||a.overflow!=='hidden')throw Error('Selected mismatch '+selector+' '+JSON.stringify(a));
  await p.locator(selector).first().screenshot({path:'evidence/card-selection-unification/'+selector.slice(1)+'-selected.png'});
 }
 // Native keyboard selection updates the pillar state and clears its previous selection.
 const pillar2=p.locator('.pillar-card').nth(1);await pillar2.focus();await p.keyboard.press('Space');
 if(await pillar2.getAttribute('aria-pressed')!=='true'||await p.locator('.pillar-card').first().getAttribute('aria-pressed')!=='false')throw Error('Keyboard selection failed');
 // Focus alone must never expose a selected marker.
 const pillar3=p.locator('.pillar-card').nth(2);await pillar3.focus();await p.mouse.move(1430,10);if(await pillar3.evaluate(el=>getComputedStyle(el,'::before').opacity)!=='0')throw Error('Focus implies selection');
 await p.waitForTimeout(250);
 await p.locator('.pillars-section').screenshot({path:'evidence/card-selection-unification/pillars-keyboard.png'});
 // Pressed state is distinct from hover, even before the click commits.
 await pillar3.hover();await p.mouse.down();await p.waitForFunction(()=>getComputedStyle(document.querySelectorAll('.pillar-card')[2],'::before').opacity==='1');await p.mouse.up();
 // Existing shared consumers: actual image selector + AgentCard, and model selector surface.
 await p.locator('.image-item').nth(1).click();await p.locator('.agent-card').click();await p.mouse.move(1430,10);await p.waitForTimeout(230);
 const shared={};for(const selector of ['.image-item.is-selected','.agent-card.is-highlighted','.model-item.is-selected']){const a=await style(selector);shared[selector]=a;if(a.background!==selected['.entry-card'].background||a.border!=='rgb(199, 210, 254)'||a.bar.width!=='4px')throw Error('Shared consumer mismatch '+selector+JSON.stringify(a));}
 await p.locator('#shared-regression').screenshot({path:'evidence/card-selection-unification/shared-consumers.png'});
 await p.emulateMedia({reducedMotion:'reduce'});await p.locator('.pillar-card').nth(3).hover();const reduced=await p.locator('.pillar-card').nth(3).evaluate(el=>({transform:getComputedStyle(el).transform,duration:getComputedStyle(el).transitionDuration}));if(reduced.transform!=='none')throw Error('Reduced motion lift');
 await p.setViewportSize({width:390,height:1000});await p.locator('.entry-card').first().scrollIntoViewIfNeeded();await p.screenshot({path:'evidence/card-selection-unification/mobile.png'});if(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Mobile overflow');
 await p.emulateMedia({reducedMotion:'no-preference'});await p.evaluate(()=>document.documentElement.dataset.theme='dark');await p.setViewportSize({width:1440,height:1000});await p.locator('.pillars-section').scrollIntoViewIfNeeded();await p.waitForFunction(()=>getComputedStyle(document.querySelector('.pillars-section')).opacity==='1');await p.locator('.pillars-section').screenshot({path:'evidence/card-selection-unification/dark.png'});
 const markerPixels={};
 for(const name of ['entry-card','pillar-card','ecosystem-card']){
  const data='data:image/png;base64,'+fs.readFileSync('evidence/card-selection-unification/'+name+'-selected.png').toString('base64');
  const pixels=await p.evaluate(async data=>{const image=new Image();image.src=data;await image.decode();const c=document.createElement('canvas');c.width=image.width;c.height=image.height;const ctx=c.getContext('2d');ctx.drawImage(image,0,0);return Array.from({length:8},(_,x)=>Array.from(ctx.getImageData(x,Math.floor(c.height/2),1,1).data).slice(0,3));},data);
  const columns=pixels.flatMap((rgb,x)=>JSON.stringify(rgb)==='[99,102,241]'?[x]:[]);
  if(columns.length!==4||columns.some((x,i)=>x!==columns[0]+i))throw Error('Marker clipped '+name+JSON.stringify(pixels));
  markerPixels[name]={columns,width:columns.length};
 }
 fs.writeFileSync('evidence/card-selection-unification/marker-pixels.json',JSON.stringify(markerPixels,null,2));
 if(errors.length)throw Error(errors.join('\n'));fs.writeFileSync('evidence/card-selection-unification/browser-result.json',JSON.stringify({defaults,hover,selected,shared,reduced,errors,keyboard:true,active:true,mobileOverflow:false},null,2));console.log('Card groups and shared consumers verified: selected palette, inside 4px marker, hover separation, keyboard, active, reduced motion and mobile.');await browser.close();
})();
