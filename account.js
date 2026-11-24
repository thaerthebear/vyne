'use strict';
(()=>{
  const $=id=>document.getElementById(id);
  let session=null,invitation='',epoch=0,busy=false,controller=new AbortController();
  const updates=typeof BroadcastChannel==='function'?new BroadcastChannel('vyne-account'):null;
  const destinations=new Set(['/rentals.html','/operations.html','/records.html','/academy.html','/course.html','/admin.html','/documents.html','/payments.html','/candidates.html','/standalone.html','/maintenance.html','/staff.html','/demo']);
  const next=new URLSearchParams(location.search).get('next');
  destinations.add('/membership.html');
  async function continueToWorkspace(){
    if(destinations.has(next)){location.replace(next);return}
    try{const r=await request('/api/billing/status');location.replace(r.access.software?'/admin.html':r.access.training?'/course.html':'/membership.html')}
    catch{location.replace('/admin.html')}
  }
  const pageAnchors=new Set(['main','login','software']);
  const raw=location.hash.slice(1);
  if(raw&&!pageAnchors.has(raw)){invitation=raw.startsWith('invite=')?new URLSearchParams(raw).get('invite')||'':raw;history.replaceState(null,'',location.pathname+location.search)}
  if(invitation.length>200)invitation='';
  function element(tag,text){const n=document.createElement(tag);n.textContent=text;return n}
  function message(text,error=false){$('message').textContent=text;$('message').className=error?'error':''}
  function controls(){document.querySelectorAll('button').forEach(b=>{b.disabled=busy&&b.id!=='signOut'})}
  function announceSignIn(){updates?.postMessage('signed-in')}
  function announceSignOut(){updates?.postMessage('signed-out')}
  function clearIssued(){$('issuedLink').value='';$('issuedSummary').textContent='';$('issuedCard').hidden=true}
  function clearPrivate(){for(const id of ['password','enrollPassword','currentPassword','newPassword'])$(id).value='';clearIssued();$('members').replaceChildren();$('invitations').replaceChildren();$('identity').textContent='';$('businessIdentity').textContent='';$('business').replaceChildren();$('businessChoice').hidden=true}
  function layout(){
    $('sessionCard').hidden=!session;$('acceptCard').hidden=!invitation;$('signInCard').hidden=!!session||!!invitation;
    $('ownerArea').hidden=session?.actor.role!=='owner';
    document.body.classList.toggle('account-signed-in',!!session);
    document.body.classList.toggle('invitation-open',!!invitation);
    const heading=document.querySelector('main>h1');if(heading)heading.textContent=session?'Your account.':invitation?'Join your rental workspace.':'Welcome back.';
    const intro=document.querySelector('.account-intro');if(intro?.firstChild)intro.firstChild.textContent=session?'Manage your access and return to your rental workspace.':invitation?'Use your invitation to join the business.':'Sign in to see your fleet, rentals, and next steps.';
    if(session){$('identity').textContent=session.actor.name+' · '+session.actor.email+' · '+session.actor.role;$('businessIdentity').textContent='Business: '+session.actor.tenantId}
  }
  function reset(){epoch++;controller.abort();controller=new AbortController();session=null;busy=false;clearPrivate();$('inviteForm').reset();layout();controls()}
  async function request(path,body,opts={}){
    const current=epoch,signal=controller.signal,headers={'Content-Type':'application/json'};
    if(opts.browser)headers['X-Vyne-Session']='browser';
    if(body!==undefined&&session?.csrfToken)headers['X-Vyne-CSRF']=session.csrfToken;
    const response=await fetch(path,{method:body===undefined?'GET':'POST',headers,body:body===undefined?undefined:JSON.stringify(body),credentials:'same-origin',cache:'no-store',signal});
    let data;try{data=await response.json()}catch{throw Error('The account service did not return a usable response.')}
    if(current!==epoch||signal.aborted)throw new DOMException('Page cleared','AbortError');
    if(!response.ok){const error=Error(data.error||'The account request could not be completed.');error.status=response.status;error.data=data;throw error}
    return data;
  }
  async function work(task){if(busy)return;const current=epoch;busy=true;controls();message('');try{await task()}catch(e){if(current===epoch&&e.name!=='AbortError')message(e.message,true)}finally{if(current===epoch){busy=false;controls()}}}
  async function loadSession(withRoster=true){session=await request('/api/auth/session');layout();if(withRoster&&session.actor.role==='owner')await roster()}
  function action(text,fn){const b=element('button',text);b.type='button';b.onclick=()=>work(fn);return b}
  async function roster(){
    const data=await request('/api/admin/accounts');$('members').replaceChildren();$('invitations').replaceChildren();
    if(!data.members.length)$('members').append(element('p','No individual members enrolled yet.'));
    for(const m of data.members){const box=element('article','');box.className='card';box.append(element('strong',m.name),element('p',m.email+' · '+m.role+(m.revokedAt?' · revoked':'')));if(!m.revokedAt&&m.id!==session?.actor.id)box.append(action('Revoke access',async()=>{if(!confirm('Revoke '+m.name+'’s access to this business and end their sessions?'))return;await request('/api/admin/accounts/revoke',{id:m.id});await roster();message('Business access revoked.')}));$('members').append(box)}
    if(!data.invitations.length)$('invitations').append(element('p','No invitations issued.'));
    for(const i of data.invitations){const box=element('article','');box.className='card';const state=i.revokedAt?'Revoked':i.usedAt?'Accepted':Date.parse(i.expiresAt)<=Date.now()?'Expired':'Pending';box.append(element('strong',i.email),element('p',i.role+' · '+state+' · expires '+new Date(i.expiresAt).toLocaleString()));if(state==='Pending')box.append(action('Revoke invitation',async()=>{await request('/api/admin/accounts/revoke-invite',{id:i.id});await roster();clearIssued();message('Invitation revoked.')}));$('invitations').append(box)}
  }
  $('signInForm').onsubmit=e=>{e.preventDefault();work(async()=>{
    const body={email:$('email').value.trim(),password:$('password').value};if(!$('businessChoice').hidden)body.businessId=$('business').value;
    try{await request('/api/auth/login',body,{browser:true});$('password').value='';await loadSession(false);announceSignIn();message('Signed in. Opening your workspace.');continueToWorkspace()}
    catch(error){if(error.status===409&&Array.isArray(error.data?.businesses)){const select=$('business');select.replaceChildren();for(const b of error.data.businesses)select.add(new Option(b.businessId+' · '+b.role,b.businessId));$('businessChoice').hidden=false;message('Choose your business, then select Sign in again.');return}$('password').value='';throw error}
  })};
  $('email').oninput=()=>{$('businessChoice').hidden=true;$('business').replaceChildren()};
  $('acceptForm').onsubmit=e=>{e.preventDefault();work(async()=>{try{await request('/api/auth/accept',{invitationToken:invitation,email:$('inviteEmail').value.trim(),name:$('name').value.trim(),password:$('enrollPassword').value},{browser:true});invitation='';$('acceptForm').reset();await loadSession();announceSignIn();message('Invitation accepted. Your account now has access to this business.')}finally{$('enrollPassword').value=''}})};
  $('discardInvite').onclick=()=>{invitation='';$('acceptForm').reset();layout();message('Invitation removed from this page. Reopen the original link if needed.')};
  $('inviteForm').onsubmit=e=>{e.preventDefault();work(async()=>{const r=await request('/api/admin/accounts/invite',{email:$('memberEmail').value.trim(),role:$('role').value});await roster();const url=new URL('/account.html',location.origin);url.hash='invite='+encodeURIComponent(r.invitationToken);$('issuedLink').value=url.href;$('issuedSummary').textContent=r.email+' · '+r.role+' · expires '+new Date(r.expiresAt).toLocaleString();$('issuedCard').hidden=false;message('Private invitation created. No email was sent.')})};
  $('copyInvite').onclick=()=>work(async()=>{if(!$('issuedLink').value)throw Error('No invitation link to copy.');await navigator.clipboard.writeText($('issuedLink').value);message('Invitation copied. Share it only with the invited person.')});
  $('clearInvite').onclick=clearIssued;$('refresh').onclick=()=>work(roster);
  $('signOut').onclick=()=>{epoch++;controller.abort();controller=new AbortController();busy=false;clearPrivate();$('ownerArea').hidden=true;work(async()=>{await request('/api/auth/logout',{});announceSignOut();reset();message('Signed out.');});};
  $('passwordForm').onsubmit=e=>{e.preventDefault();work(async()=>{try{await request('/api/auth/password',{currentPassword:$('currentPassword').value,newPassword:$('newPassword').value});announceSignOut();reset();message('Password changed. Sign in again; all previous sessions have ended.')}finally{$('currentPassword').value='';$('newPassword').value=''}})};
  window.addEventListener('hashchange',()=>{const value=location.hash.slice(1);if(!value||pageAnchors.has(value))return;reset();invitation=value.startsWith('invite=')?new URLSearchParams(value).get('invite')||'':value;if(invitation.length>200)invitation='';history.replaceState(null,'',location.pathname+location.search);layout();work(async()=>{try{await loadSession()}catch(e){if(e.status!==401)throw e}})});
  window.addEventListener('pagehide',()=>{invitation='';reset();$('acceptForm').reset();$('signInForm').reset()});
  if(updates){updates.onmessage=event=>{if(['signed-in','signed-out'].includes(event.data)){invitation='';reset();location.replace(event.data==='signed-in'?location.pathname+location.search:'/account.html')}}}
  layout();work(async()=>{try{await loadSession(false);if(!invitation&&next!==null){continueToWorkspace();return}if(session.actor.role==='owner')await roster();if(invitation)message('An invitation is open. Accept it with the invited account’s credentials.')}catch(error){if(error.status===401){session=null;layout();return}throw error}});
})();
