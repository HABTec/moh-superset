import {chromium} from '@playwright/test';
import fs from 'fs';
const [,, url, state, cssFile] = process.argv;
const b = await chromium.launch({channel:'chrome'});
const c = await b.newContext({storageState: state, viewport:{width:375,height:667}, hasTouch:true});
const p = await c.newPage();
await p.goto(url,{waitUntil:'domcontentloaded',timeout:60000});
await p.waitForFunction(()=>document.body.getElementsByTagName('*').length>800,{timeout:60000}).catch(()=>{});
await p.waitForTimeout(12000);
if (cssFile) await p.addStyleTag({content: fs.readFileSync(cssFile,'utf8')}).then(()=>p.waitForTimeout(1500));
const r = await p.evaluate(()=>{
  const d=e=>e.tagName.toLowerCase()+(e.id?'#'+e.id:'')+(typeof e.className==='string'&&e.className?'.'+e.className.trim().split(/\s+/).slice(0,2).join('.'):'');
  const out=[];
  const holder=[...document.querySelectorAll(".chart-slice")].find(h=>h.getBoundingClientRect().width>0&&h.getBoundingClientRect().width<60);
  let a=holder; let n=0;
  while(a&&a!==document.body&&n<9){const s=getComputedStyle(a);out.push(`${Math.round(a.getBoundingClientRect().width)}px ${d(a)} disp=${s.display} fd=${s.flexDirection} fl=${s.flex} mw=${s.minWidth} pad=${s.paddingLeft}/${s.paddingRight} mar=${s.marginLeft}/${s.marginRight}`);a=a.parentElement;n++}
  return {bodyClass:document.body.className.slice(0,120),vw:innerWidth,chain:out};
});
console.log(JSON.stringify(r,null,1)); await b.close();
