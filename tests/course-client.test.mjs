import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
const {JSDOM, VirtualConsole}=createRequire(new URL('./training/package.json',import.meta.url))('jsdom');
const html=readFileSync(process.env.RYCF_COURSE_HTML||new URL('../course.html',import.meta.url),'utf8');
const key=process.env.RYCF_COURSE_KEY||'rycf-course-draft-v1';
function fixture(seed={},lesson='0.1',failSaving=false){
 const errors=[];const virtualConsole=new VirtualConsole();virtualConsole.on('jsdomError',e=>errors.push(e));
 const dom=new JSDOM(html,{url:'https://runyourcarfleet.com/course.html?lesson='+lesson,runScripts:'dangerously',virtualConsole,beforeParse(w){
  if(process.env.RYCF_COURSE_ART==='1')w.eval(readFileSync(new URL('../lesson-art.js',import.meta.url),'utf8'));
  for(const [k,v] of Object.entries(seed))w.localStorage.setItem(k,typeof v==='string'?v:JSON.stringify(v));
  w.scrollTo=()=>{};w.HTMLElement.prototype.scrollIntoView=()=>{};w.HTMLMediaElement.prototype.pause=()=>{};w.confirm=()=>true;
  if(failSaving)w.Storage.prototype.setItem=()=>{throw Error('Quota exceeded')};
 }});
 assert.deepEqual(errors.map(e=>e.message),[]);
 const d=dom.window.document;
 return {dom,w:dom.window,d,section:id=>d.querySelector(`[data-lesson="${id}"]`),
  button(root,text){const b=[...root.querySelectorAll('button')].find(n=>n.textContent===text);assert.ok(b,'Button: '+text);b.click();return b},
  select(id){const s=d.querySelector('#lesson');s.value=id;s.dispatchEvent(new dom.window.Event('change'))},
  input(node,value){node.value=value;node.dispatchEvent(new dom.window.Event('input',{bubbles:true}))},
  storage(){return Object.fromEntries(Object.keys(dom.window.localStorage).map(k=>[k,dom.window.localStorage.getItem(k)]))},
  async restore(data){const input=d.querySelector('#restore-file');const raw=JSON.stringify(data);Object.defineProperty(input,'files',{configurable:true,value:[{size:raw.length,text:async()=>raw}]});await input.onchange({target:input})}
 };
}
function answerLesson(f,id){const s=f.section(id);for(const t of s.querySelectorAll('textarea'))f.input(t,'Fictional practice answer for '+t.dataset.key);s.querySelector('.complete').click();assert.equal(s.dataset.stage,'finish');}

test('all 33 worksheets can be reviewed; edits remove only the affected review mark',()=>{
 const f=fixture();const ids=[...f.d.querySelector('#lesson').options].map(o=>o.value);assert.equal(ids.length,33);
 for(const id of ids){f.select(id);answerLesson(f,id)}
 assert.equal(Object.values(JSON.parse(f.w.localStorage.getItem(key+'-completed'))).filter(Boolean).length,33);
 f.input(f.section('1.2').querySelector('textarea'),'Changed market research');
 const completed=JSON.parse(f.w.localStorage.getItem(key+'-completed'));assert.equal(completed['1.2'],false);assert.equal(completed['1.1'],true);f.w.close();
});

test('reload resumes the exact worksheet question and remembers reading position per lesson',()=>{
 const f=fixture();let s=f.section('0.1');f.button(s,'Next part →');f.button(s,'Next part →');f.button(s,'Practice');
 f.input(s.querySelector('textarea'),'My practical goal');f.button(s,'Save & continue →');
 const seed=f.storage();f.w.close();const r=fixture(seed);s=r.section('0.1');assert.equal(s.dataset.stage,'practice');assert.match(s.querySelector('.question-count').textContent,/Question 2 of/);assert.equal(s.querySelector('textarea').value,'My practical goal');
 r.button(s,'Read');assert.equal(s.querySelector('.reading-meta').textContent,'Written lesson3 / 4');
 r.select('0.2');assert.equal(r.section('0.2').dataset.stage,'learn');r.select('0.1');assert.equal(r.section('0.1').dataset.stage,'learn');r.w.close();
});

test('partial restore preserves unrelated work and does not trust a reviewed flag with missing answers',async()=>{
 const f=fixture();answerLesson(f,'0.1');f.select('0.2');answerLesson(f,'0.2');const field=f.section('0.1').querySelector('textarea');
 await f.restore({version:1,answers:{[field.dataset.key]:'Restored answer'},completed:{'0.1':true}});
 const reviews=JSON.parse(f.w.localStorage.getItem(key+'-completed'));assert.equal(reviews['0.1'],false);assert.equal(reviews['0.2'],true);assert.equal(field.value,'Restored answer');assert.match(f.section('0.2').querySelector('textarea').value,/Fictional/);f.w.close();
});

test('oversized answer import leaves current answers unchanged instead of silently truncating',async()=>{
 const f=fixture();const field=f.section('0.1').querySelector('textarea');f.input(field,'Keep this answer');
 await f.restore({version:1,answers:{[field.dataset.key]:'x'.repeat(20001)}});assert.equal(field.value,'Keep this answer');assert.match(f.d.querySelector('#save').textContent,/not changed/);f.w.close();
});

test('failed browser saving is visible outside the collapsed tools and never reported as saved',()=>{
 const f=fixture({},'0.1',true);const s=f.section('0.1');f.button(s,'Practice');f.input(s.querySelector('textarea'),'Unsaved answer');
 assert.equal(f.d.querySelector('.course-save-warning').hidden,false);assert.match(s.querySelector('.save-indicator').textContent,/could not be saved/);assert.equal(f.w.localStorage.getItem(key),null);f.w.close();
});

test('home continues to an unfinished lesson; print includes complete long answers',()=>{
 const f=fixture();answerLesson(f,'0.1');f.button(f.section('0.1'),'Back to course');assert.match(f.d.querySelector('.hero-copy h2').textContent,/0.2/);
 const long='A complete answer. '.repeat(180);f.input(f.section('0.1').querySelector('textarea'),long);f.w.dispatchEvent(new f.w.Event('beforeprint'));assert.equal(f.section('0.1').querySelector('.print-answer').textContent,long);f.w.close();
});

test('full backup restores saved question, state and review without overwriting unrelated answers',async()=>{
 const f=fixture();const s=f.section('0.1');const answers=Object.fromEntries([...s.querySelectorAll('textarea')].map(t=>[t.dataset.key,'Restored '+t.dataset.key]));answers.__state='Tennessee';
 await f.restore({version:1,answers,completed:{'0.1':true},lastLesson:'0.1',resume:{'0.1':{stage:'practice',question:2,part:1}}});
 assert.equal(s.dataset.stage,'practice');assert.match(s.querySelector('.question-count').textContent,/Question 3 of/);assert.equal(s.querySelector('.location-select').value,'Tennessee');assert.equal(JSON.parse(f.w.localStorage.getItem(key+'-completed'))['0.1'],true);f.button(s,'Read');assert.equal(s.querySelector('.reading-meta').textContent,'Written lesson2 / 4');f.w.close();
});

if(process.env.RYCF_COURSE_ART==='1')test('every lesson has distinct title-matched art and working navigation',()=>{
 const f=fixture(),ids=[...f.d.querySelector('#lesson').options].map(o=>o.value),urls=new Set();
 assert.equal(f.d.querySelectorAll('[data-lesson-link] img').length,33);
 for(const id of ids){
  f.select(id);const section=f.section(id),art=section.querySelector('.lesson-illustration img'),video=section.querySelector('video');
  const url=art?.src||video?.poster;assert(url?.endsWith('lesson-'+id.replace('.','-')+'-v1.jpg'));urls.add(url);
  if(art)assert(art.alt.length>20);
  assert.equal(f.d.querySelector('.hero-art img').dataset.artLesson,id);
  assert.match(f.d.querySelector('.hero-copy h2').textContent,new RegExp('^'+id.replace('.','\\.')+' · '));
 }
 assert.equal(urls.size,33);assert.equal(f.d.querySelectorAll('video source').length,2);f.w.close();
});

test('reviewed guidance keeps existing answers, shows contextual help and makes optional notes skippable',()=>{
 const f=fixture({[key]:{'0.1-0':'Existing goal from before the content review'}},'0.1');let s=f.section('0.1');
 assert.equal(f.d.querySelectorAll('[data-content-version="2"]').length,33);
 assert.equal(f.d.querySelectorAll('.question-help').length,164);
 for(const help of f.d.querySelectorAll('.question-help')){assert.ok(help.querySelector('.question-hint')?.textContent.length>15);assert.ok(help.querySelector('.question-example p')?.textContent.length>20)}
 f.button(s,'Practice');const input=s.querySelector('textarea');assert.equal(input.value,'Existing goal from before the content review');
 const visible=()=>[...s.querySelectorAll('.question-card')].filter(n=>!n.hidden);assert.equal(visible().length,1);
 f.button(s,'Save & continue →');assert.equal(visible().length,1);assert.match(visible()[0].querySelector('.question-example p').textContent,/One car/);
 const required=[...s.querySelectorAll('textarea')].filter(t=>!t.dataset.key.endsWith('-notes'));for(const t of required)if(!t.value)f.input(t,'My short draft');
 for(let i=1;i<required.length;i++)f.button(s,'Save & continue →');
 assert.match(s.querySelector('.question-count').textContent,/Optional/);f.button(s,'Skip optional note →');assert.equal(s.dataset.stage,'review');
 assert.equal(s.querySelectorAll('.review-answer').length,5);assert.equal(s.querySelector('[data-key="0.1-notes"]').value,'');
 s.querySelector('.complete').click();assert.equal(s.dataset.stage,'finish');f.w.close();
});

test('earlier answers are read-only and escaped; final rehearsal is available exactly where requested',()=>{
 const f=fixture({[key]:{'1.1-0':'<img src=x onerror=alert(1)> My original customer'}},'1.5');let s=f.section('1.5');f.button(s,'Practice');
 const reuse=s.querySelector('.reuse-work');reuse.open=true;reuse.dispatchEvent(new f.w.Event('toggle'));
 assert.match(reuse.querySelector('.reused-answer p').textContent,/<img/);assert.equal(reuse.querySelectorAll('img,textarea').length,0);
 f.button(reuse,'Open lesson 1.1');assert.equal(f.d.querySelector('#lesson').value,'1.1');assert.equal(f.section('1.1').querySelector('textarea').value,'<img src=x onerror=alert(1)> My original customer');
 f.select('7.4');s=f.section('7.4');assert.ok(s.querySelector('.learn-panel .capstone-checklist'));f.button(s,'Practice');
 for(let i=0;i<3;i++){f.input(s.querySelectorAll('textarea')[i],'My evidence');f.button(s,'Save & continue →')}
 const card=[...s.querySelectorAll('.question-card')].find(n=>!n.hidden);assert.ok(card.querySelector('.capstone-checklist'));
 const text=card.querySelector('.capstone-checklist').textContent;for(const required of ['R-001','Day 4','Practice-P001','42,800','42,950','150 miles'])assert.ok(text.includes(required));
 assert.equal(f.d.querySelectorAll('textarea').length,197);f.w.close();
});
