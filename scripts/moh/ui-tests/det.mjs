import {chromium} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
const [,, url, state, w] = process.argv;
const b = await chromium.launch({channel:'chrome'});
const c = await b.newContext({storageState: state, viewport:{width:+w,height:667}, hasTouch:true});
const p = await c.newPage();
await p.goto(url,{waitUntil:'domcontentloaded',timeout:60000});
await p.waitForFunction(()=>document.body.getElementsByTagName('*').length>700,{timeout:60000}).catch(()=>{});
await p.waitForTimeout(14000);
await p.evaluate(async()=>{for(let y=0;y<document.body.scrollHeight;y+=600){scrollTo(0,y);await new Promise(r=>setTimeout(r,120))}scrollTo(0,0)});
await p.waitForTimeout(2500);
const small = await p.evaluate(()=>[...document.querySelectorAll('a[href],button,input:not([type=hidden]),select,textarea,[role=button],[role=tab],[tabindex="0"]')].filter(e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&(r.width<24||r.height<24)}).map(e=>{const r=e.getBoundingClientRect();return `${e.tagName.toLowerCase()} ${Math.round(r.width)}x${Math.round(r.height)} aria="${e.getAttribute('aria-label')||''}" txt="${(e.textContent||'').trim().slice(0,20)}" in=${e.closest('[data-test]')?.getAttribute('data-test')||e.closest('[class*=ai]')?.className?.toString().slice(0,20)||''}`}));
console.log('SMALL',small.length); console.log(small.join('\n'));
const ax = await new AxeBuilder({page:p}).withRules(['color-contrast']).analyze();
for (const v of ax.violations) for (const n of v.nodes.slice(0,6)) { const d=n.any[0]?.data||{}; console.log('CONTRAST',d.fgColor,d.bgColor,d.contrastRatio,d.fontSize,'|',(n.html||'').slice(0,110).replace(/\n/g,' ')); }
await b.close();
