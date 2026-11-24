// Apply the reviewed curriculum to the existing course without changing answer IDs or videos.
import {readFileSync,writeFileSync} from 'node:fs';
import {createRequire} from 'node:module';
const {JSDOM}=createRequire(new URL('../tests/training/package.json',import.meta.url))('jsdom');
const root=new URL('../',import.meta.url),file=new URL('course.html',root);
const data=JSON.parse(readFileSync(new URL('docs/training-curriculum-v2.json',root),'utf8'));
let html=readFileSync(file,'utf8');
const segmenter=new Intl.Segmenter('en',{granularity:'sentence'});
const capstone=data.capstone;
for(const row of data.lessons){
 const re=new RegExp('<section data-lesson="'+row.id.replace('.','\\.')+'"[\\s\\S]*?</section>');
 const old=html.match(re)?.[0];if(!old)throw Error('Missing section '+row.id);
 const d=new JSDOM(old).window.document,s=d.querySelector('section'),script=s.querySelector('[id^="script-"]'),worksheet=s.querySelector('[id^="worksheet-"]');
 const make=(tag,text,cls)=>{const n=d.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
 const originalKeys=[...s.querySelectorAll('textarea')].map(t=>t.dataset.key);
 s.dataset.contentVersion=String(data.version);s.querySelector('.outcome').textContent='Your output: '+row.output;
 s.querySelectorAll('.lesson-brief,.lesson-support,.question-help,.reuse-work,.practice-intro').forEach(n=>n.remove());
 const ps=[...script.children].filter(n=>n.tagName==='P'&&!n.classList.contains('note'));if(ps.length!==4)throw Error('Reader shape changed '+row.id);
 row.paragraphs.forEach((text,i)=>{
  const p=ps[i];p.replaceChildren(make('strong',['The idea','How to do it','Worked example','Your small task'][i],'reading-label'));
  let group='';const groups=[];
  for(const {segment} of segmenter.segment(text)){if(group&&(`${group} ${segment}`).split(/\s+/).length>43){groups.push(group.trim());group=''}group+=segment;}
  if(group)groups.push(group.trim());for(const chunk of groups)p.append(make('span',chunk,'reading-block'),d.createTextNode('\n'));
 });
 const brief=make('div',undefined,'lesson-brief');brief.append(make('p','Bring: '+row.bring),make('p',row.time,'note'));script.prepend(brief);
 const wordCount=row.paragraphs.join(' ').split(/\s+/).length;const tag=script.querySelector('.tag');if(tag)tag.textContent='Written lesson · '+wordCount+' words';
 const fields=[...worksheet.querySelectorAll('textarea')].filter(t=>!t.dataset.key.endsWith('-notes'));
 if(fields.length!==row.questions.length)throw Error('Question count changed '+row.id);
 fields.forEach((input,i)=>{
  const q=row.questions[i],label=worksheet.querySelector('label[for="'+input.id+'"]');label.textContent=(i+1)+'. '+q.label;
  input.placeholder='Write a short answer…';input.setAttribute('aria-describedby','help-'+input.dataset.key);
  const help=make('div',undefined,'question-help');help.id='help-'+input.dataset.key;help.dataset.for=input.dataset.key;
  help.append(make('p',q.hint,'question-hint'));const example=make('details',undefined,'question-example');example.append(make('summary','See a worked answer'),make('p',q.example));help.append(example);input.after(help);
 });
 const notes=worksheet.querySelector('[data-key$="-notes"]');worksheet.querySelector('label[for="'+notes.id+'"]').textContent='Optional: one question to follow up';notes.placeholder='Question → next action → responsible person → review date';
 const check=worksheet.querySelector('h3').nextElementSibling;check.textContent=row.done;
 const details=[...worksheet.querySelectorAll(':scope > details')];
 const oldExample=details.find(n=>n.querySelector('summary')?.textContent.includes('example'));oldExample?.remove();
 const location=details.find(n=>n.querySelector('summary')?.textContent.includes('Location'));if(location){location.replaceChildren(make('summary','Location checkpoint'),make('p',row.local||'No separate local-rule task in this lesson. Carry your operating-location questions into Lesson 3.1.'));}
 const support=make('div',undefined,'lesson-support');
 if(row.sources.length){const refs=make('details',undefined,'lesson-sources');refs.append(make('summary','Sources & further reading'));for(const source of row.sources){const p=make('p'),a=make('a',source.title);a.href=source.url;a.target='_blank';a.rel='noopener noreferrer';p.append(a,make('small',source.scope+' Checked '+source.checkedOn+'.'));refs.append(p)}support.append(refs);}
 function rehearsal(){const box=make('details',undefined,'capstone-checklist');box.append(make('summary','Final rehearsal: reservation to receipt'),make('p','Fictional practice only. Reuse your answers from 5.1–5.6; no real booking, signature, charge or message is created. Mark each check in your question 4 answer as checked, needs revision or unknown.'));
  const list=make('ol');for(const [id,title,body]of capstone){const li=make('li'),step=make('details');step.append(make('summary',title),make('p',body));if(id!=='7.4'){const b=make('button','Open lesson '+id,'quiet');b.type='button';b.dataset.reuseLesson=id;step.append(b)}li.append(step);list.append(li)}box.append(list);return box;}
 if(row.id==='7.4'){support.append(rehearsal());worksheet.querySelector('[data-for="7.4-3"]').append(rehearsal());}
 if(support.children.length)script.append(support);
 const reuse=make('details',undefined,'reuse-work');reuse.dataset.lessons=row.reuse.join(',');reuse.append(make('summary','Earlier answers — reuse your work'),make('div',undefined,'reuse-body'));if(row.reuse.length)worksheet.append(reuse);
 if(JSON.stringify(originalKeys)!==JSON.stringify([...s.querySelectorAll('textarea')].map(t=>t.dataset.key)))throw Error('Answer keys changed');
 html=html.replace(old,()=>s.outerHTML);
 d.defaultView.close();
}
writeFileSync(file,html);
console.log('Updated '+data.lessons.length+' lessons; existing answer keys preserved.');
