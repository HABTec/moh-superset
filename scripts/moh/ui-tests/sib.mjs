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
  const sl=[...document.querySelectorAll(".chart-slice")].find(h=>h.getBoundingClientRect().width>0&&h.getBoundingClientRect().width<60);
  const row=sl.parentElement.parentElement;
  const d=e=>e.tagName.toLowerCase()+(e.id?'#'+e.id:'')+(typeof e.className==='string'&&e.className?'.'+e.className.trim().split(/\s+/).slice(0,3).join('.'):'');
  return [...row.children].map(c=>{const s=getComputedStyle(c);return `${Math.round(c.getBoundingClientRect().width)}px ${d(c)} flex=${s.flex} w=${s.width} minw=${s.minWidth} text="${(c.innerText||'').slice(0,40).replace(/\n/g,' ')}" kids=${[...c.children].slice(0,4).map(d).join(',')}`});
});
console.log(JSON.stringify(r,null,1)); await b.close();
