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
  const d=e=>e.tagName.toLowerCase()+(e.id?'#'+e.id:'')+(typeof e.className==='string'&&e.className?'.'+e.className.trim().split(/\s+/).slice(0,3).join('.'):'');
  const chain=(e)=>{const o=[];let a=e.parentElement;while(a&&a!==document.body&&o.length<7){const s=getComputedStyle(a);o.push(d(a)+` ox=${s.overflowX} w=${Math.round(a.getBoundingClientRect().width)}`);a=a.parentElement}return o};
  const tables=[...document.querySelectorAll('table')].filter(t=>t.getBoundingClientRect().width>0).map(t=>{let a=t.parentElement,hit=null;while(a&&a!==document.body){const s=getComputedStyle(a);if(/auto|scroll/.test(s.overflowX))return null;if(/hidden|clip/.test(s.overflowX)){hit=a;break}a=a.parentElement}
    return hit&&t.getBoundingClientRect().right>hit.getBoundingClientRect().right+4?{t:d(t),tw:Math.round(t.getBoundingClientRect().width),clipper:d(hit),cw:Math.round(hit.getBoundingClientRect().width),chain:chain(t)}:null}).filter(Boolean);
  const heads=[...document.querySelectorAll('.chart-slice')].map(s=>{const a=s.getBoundingClientRect();const over=[...s.querySelectorAll('*')].filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.right>a.right+4&&r.left<a.right});return over.length?{slice:d(s),sw:Math.round(a.width),over:over.slice(0,3).map(d)}:null}).filter(Boolean);
  const charts=[...document.querySelectorAll('canvas,[data-test="chart-container"] svg')].filter(c=>c.getBoundingClientRect().width>0).map(c=>{const h=c.closest('[data-test="dashboard-component-chart-holder"],.dashboard-chart,.chart-container');return h&&c.getBoundingClientRect().right>h.getBoundingClientRect().right+4?{c:d(c),cw:Math.round(c.getBoundingClientRect().width),holder:d(h),hw:Math.round(h.getBoundingClientRect().width)}:null}).filter(Boolean);
  return {tables:tables.slice(0,2),heads:heads.slice(0,2),headCount:heads.length,charts:charts.slice(0,3),chartCount:charts.length,tableCount:tables.length};
});
console.log(JSON.stringify(r,null,1)); await b.close();
