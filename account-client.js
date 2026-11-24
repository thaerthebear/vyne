'use strict';
// Account session transport; the marker is an internal bridge, never a credential.
(()=>{
  const nativeFetch=window.fetch.bind(window), marker='@account-session';
  let current=null, ready;
  const signInPath='/account.html?next='+encodeURIComponent(location.pathname);
  function expired(){current=null;sessionAbort.abort();location.replace(signInPath)}
  const sessionAbort=new AbortController();
  const channel=typeof BroadcastChannel==='function'?new BroadcastChannel('vyne-account'):null;
  channel?.addEventListener('message',event=>{if(event.data==='signed-out'){sessionAbort.abort();location.replace('/account.html')}else if(event.data==='signed-in'){sessionAbort.abort();location.reload()}});
  async function session(){const r=await nativeFetch('/api/auth/session',{credentials:'same-origin',cache:'no-store'});current=r.ok?await r.json():null;return current}
  ready=session().catch(()=>null);
  window.VyneAccount={ready,marker,session};
  window.fetch=async(input,options={})=>{
    const url=new URL(typeof input==='string'?input:input.url,location.href);
    if(url.origin!==location.origin||!url.pathname.startsWith('/api/'))return nativeFetch(input,options);
    const headers=new Headers(options.headers||(input instanceof Request?input.headers:undefined));
    if(headers.get('Authorization')==='Bearer '+marker){
      headers.delete('Authorization');await ready;
      if(!current||sessionAbort.signal.aborted)throw new DOMException('Account session closed','AbortError');
      if(current?.csrfToken)headers.set('X-Vyne-CSRF',current.csrfToken);
      const signal=options.signal?AbortSignal.any([options.signal,sessionAbort.signal]):sessionAbort.signal;
      const response=await nativeFetch(input,{...options,headers,signal,credentials:'same-origin'});
      if(response.status===401)expired();
      return response;
    }
    return nativeFetch(input,options);
  };
  document.addEventListener('DOMContentLoaded',async()=>{
    const state=await ready;
    const entry=document.createElement('p');entry.className='notice';
    const link=document.createElement('a');link.href=state?'/account.html':signInPath;
    link.textContent=state?'Account: '+state.actor.name+' · '+state.actor.role:'Sign in with your individual account';entry.append(link);
    document.querySelector('main')?.prepend(entry);
    const entryCard=document.getElementById('account-entry');
    if(entryCard)entryCard.hidden=!!state;
    if(!state){const message=document.getElementById('message');if(message)message.textContent='Sign in with your email and password to continue.';return;}
    const input=document.getElementById('key')||document.getElementById('access-key');
    if(!input)return;
    input.value=marker;
    const form=input.closest('form');
    if(form)form.requestSubmit();else document.getElementById('connect')?.click();
  });
  document.addEventListener('click',event=>{
    if(!current||!event.target.closest('#lock,#logout'))return;
    const state=current;current=null;sessionAbort.abort();
    // Existing page handler clears local data immediately. Invalidate server session too.
    nativeFetch('/api/auth/logout',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-Vyne-CSRF':state.csrfToken},body:'{}'})
      .then(r=>{if(!r.ok)throw Error();channel?.postMessage('signed-out');location.assign('/account.html')})
      .catch(()=>{const m=document.getElementById('message');if(m)m.textContent='Page locked. Server sign-out could not be confirmed; retry from Account.'});
  },true);
})();
