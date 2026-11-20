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
  const c=[...document.querySelectorAll("canvas")].find(c=>{const h=c.closest(".chart-container");return h&&c.getBoundingClientRect().right>h.getBoundingClientRect().right+4});
  if(!c) return "none";
  const o=[];let a=c;for(let n=0;a&&n<6;n++,a=a.parentElement){const r=a.getBoundingClientRect(),s=getComputedStyle(a);o.push(`${a.tagName.toLowerCase()}.${(a.className||"").toString().slice(0,24)} L=${Math.round(r.left)} R=${Math.round(r.right)} w=${Math.round(r.width)} pad=${s.paddingLeft}/${s.paddingRight} ox=${s.overflowX} style="${(a.getAttribute("style")||"").slice(0,60)}"`)}
  return o;
});
console.log(JSON.stringify(r,null,1)); await b.close();
