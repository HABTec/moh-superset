import { verdict } from './gate-summary.mjs';
const mk=(tests)=>({suites:[{specs:tests.map((t,i)=>({title:'t'+i,tests:[t]}))}]});
const ok={status:'expected',results:[]}, fl={status:'flaky',results:[]};
const reg={status:'unexpected',results:[{error:{message:'Error: UI regressions on home@375:\n  RESP-OVERFLOW-X: 1 > budget 0'}}]};
const nv={status:'unexpected',results:[{error:{message:'TimeoutError: page.goto: Timeout 60000ms exceeded.'}}]};
const cases=[['all pass',[ok,ok,fl],0],['one regression',[ok,reg],1],['one infra failure',[ok,nv],3],['regression beats not-verified',[nv,reg],1],['no tests',[],3],['skipped',[ok,{status:'skipped',results:[]}],3]];
let bad=0; for(const [n,t,want] of cases){const g=verdict(mk(t)).code; const pass=g===want; if(!pass)bad++; console.log((pass?'ok  ':'FAIL'),n,'->',g,'(want',want+')');}
process.exit(bad?1:0);
