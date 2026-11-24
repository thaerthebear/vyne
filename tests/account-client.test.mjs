import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import fs from 'node:fs';
const source=fs.readFileSync(new URL('../account-client.js',import.meta.url),'utf8');
function setup(state){
 const events={},calls=[],redirects=[];let submits=0;
 const elements={key:{value:'',closest:()=>({requestSubmit(){submits++}})},'account-entry':{hidden:false},message:{textContent:''}};
 const context={URL,Headers,Request,AbortController,AbortSignal,DOMException,location:{href:'https://fleet.example/rentals.html',origin:'https://fleet.example',pathname:'/rentals.html',replace:u=>redirects.push(u),assign:u=>redirects.push(u)},document:{addEventListener:(e,fn)=>events[e]=fn,createElement:()=>({append(){}}),querySelector:()=>({prepend(){}}),getElementById:id=>elements[id]}};
 context.window={fetch:async(input,options)=>{calls.push({input,options});return input==='/api/auth/session'?{ok:!!state,status:state?200:401,json:async()=>state}:{ok:true,status:200}}};
 vm.runInNewContext(source,context);
 return {context,events,calls,redirects,elements,get submits(){return submits}};
}
const state={actor:{name:'Test owner',role:'owner'},csrfToken:'synthetic-csrf'};
test('anonymous page offers account sign-in without submitting legacy bridge',async()=>{const x=setup(null);await x.events.DOMContentLoaded();assert.equal(x.submits,0);assert.equal(x.elements['account-entry'].hidden,false);assert.match(x.elements.message.textContent,/email and password/);});
test('account session auto-opens workspace using noncredential marker',async()=>{const x=setup(state);await x.events.DOMContentLoaded();assert.equal(x.submits,1);assert.equal(x.elements.key.value,'@account-session');assert.equal(x.elements['account-entry'].hidden,true);});
test('marker request uses cookie and CSRF without a bearer credential',async()=>{const x=setup(state);await x.context.window.VyneAccount.ready;await x.context.window.fetch('/api/admin/profile',{method:'POST',headers:{Authorization:'Bearer @account-session'},body:'{}'});const request=x.calls.at(-1);assert.equal(request.options.credentials,'same-origin');assert.equal(request.options.headers.get('Authorization'),null);assert.equal(request.options.headers.get('X-Vyne-CSRF'),'synthetic-csrf');});
test('missing session cannot send workspace request with marker',async()=>{const x=setup(null);await assert.rejects(x.context.window.fetch('/api/admin/profile',{headers:{Authorization:'Bearer @account-session'}}),{name:'AbortError'});assert.equal(x.calls.length,1);});
test('external request never receives account CSRF',async()=>{const x=setup(state);await x.context.window.fetch('https://elsewhere.example/api/data',{headers:{}});assert.deepEqual(x.calls.at(-1).options.headers,{});});

for(const [next,expected] of [['/operations.html','/operations.html'],['/course.html','/course.html'],['https://elsewhere.example','/admin.html']])test('account login safely returns to '+next+' without hearing its own sign-in broadcast',async()=>{
 const code=fs.readFileSync(new URL('../account.js',import.meta.url),'utf8'),elements=new Map(),redirects=[],channels=[],events={};let loggedIn=false;
 const node=()=>({value:'',hidden:false,textContent:'',className:'',reset(){},replaceChildren(){},append(){},add(){},focus(){}});
 const get=id=>{if(!elements.has(id))elements.set(id,node());return elements.get(id)};
 class Channel {constructor(){channels.push(this)}postMessage(data){for(const other of channels)if(other!==this)other.onmessage?.({data})}close(){}}
 const context={URL,URLSearchParams,AbortController,DOMException,BroadcastChannel:Channel,location:{hash:'',search:'?next='+encodeURIComponent(next),pathname:'/account.html',origin:'https://fleet.example',assign:p=>redirects.push(p),replace:p=>redirects.push(p)},history:{replaceState(){}},document:{body:{classList:{toggle(){}}},getElementById:get,querySelector:()=>null,querySelectorAll:()=>[],createElement:node},navigator:{},window:{addEventListener:(name,handler)=>{events[name]=handler}},fetch:async path=>{if(path==='/api/auth/login')loggedIn=true;const ok=loggedIn;return{ok,status:ok?200:401,json:async()=>path==='/api/admin/accounts'?{members:[],invitations:[]}:state}}};
 vm.runInNewContext(code,context);await new Promise(r=>setImmediate(r));get('email').value='owner@example.test';get('password').value='synthetic password';context.location.hash='#login';events.hashchange();await new Promise(r=>setImmediate(r));assert.equal(get('acceptCard').hidden,true);assert.equal(get('password').value,'synthetic password');get('signInForm').onsubmit({preventDefault(){}});await new Promise(r=>setImmediate(r));assert.deepEqual(redirects,[expected]);assert.equal(channels.length,1);assert.equal(get('password').value,'');
});
