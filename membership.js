'use strict';
(()=>{
 const $=id=>document.getElementById(id);let session=null,config=null,state=null,busy=false,chosen='yearly';
 const names={monthly:'Software monthly · $49/month',yearly:'Software + training · $490/year',training:'Training only · $99 once for 12 months'};
 function message(text,error=false){$('message').textContent=text;$('message').className=error?'error':''}
 async function api(path,body){const r=await fetch(path,{credentials:'same-origin',cache:'no-store',method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-Vyne-Session':'browser',...(session?{'X-Vyne-CSRF':session.csrfToken}:{})},...(body?{body:JSON.stringify(body)}:{})});const data=await r.json();if(!r.ok)throw Object.assign(Error(data.error||'Request could not be confirmed'),{status:r.status});return data}
 function controls(){document.querySelectorAll('button').forEach(b=>b.disabled=busy||!config?.ready||(!!b.dataset.plan&&(state?.access.grandfathered||(b.dataset.plan==='training'&&state?.access.training))))}
 async function work(fn){if(busy)return;busy=true;controls();message('');try{await fn()}catch(e){message(e.message,true)}finally{busy=false;controls()}}
 function node(tag,text){const el=document.createElement(tag);el.textContent=text;return el}
 function action(label,fn){const b=node('button',label);b.type='button';b.className='secondary';b.onclick=()=>work(fn);return b}
 function render(){
  $('environment').textContent=!config.ready?'Plans are prepared. Checkout is not connected yet.':config.mode==='test'?'TEST CHECKOUT · No real money moves. Use Stripe test cards only.':'Secure checkout through Stripe · Merchant: Only One Worker';
  $('current').hidden=!state;
  if(!state)return;
  $('signup').hidden=true;$('manageBilling').hidden=!state.orders.length;$('identity').textContent=state.actor.name;$('dashboardLink').hidden=!state.access.software;$('courseLink').hidden=!state.access.training;
  $('accessSummary').textContent=state.access.grandfathered?'Your existing workspace and training access are preserved.':state.access.software&&state.access.training?'Software and training are available.':state.access.software?'Your software is available. Add training whenever you are ready.':state.access.training?'Your training is available. Software is a separate subscription.':'Choose a plan below to activate your access.';
  $('orders').replaceChildren();
  for(const order of state.orders){const card=node('article','');card.append(node('strong',names[order.plan]));const end=order.paid_until?new Date(order.paid_until*1000).toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'}):null;card.append(node('p',order.blocked?'Access is paused following a refund or payment dispute.':end?'Paid access through '+end+(order.cancel_at_period_end?' · Renewal canceled.':order.plan==='training'?' · Does not renew.':''):['open','creating','pending'].includes(order.state)?'Checkout is not complete. No paid access has been granted.':'Status: '+order.state));
   card.append(action('Check payment status',async()=>{state=await api('/api/billing/refresh',{orderId:order.id});render();message('Checked with Stripe. Your access is shown above.')}));
   if(['open','creating','pending'].includes(order.state))card.append(action('Close unfinished checkout',async()=>{state=await api('/api/billing/expire',{orderId:order.id});render();message('Checkout closed. You can choose a plan again.')}));
   if(order.plan!=='training'&&end&&!order.cancel_at_period_end&&!['canceled','incomplete_expired'].includes(order.state))card.append(action('Cancel next renewal',async()=>{if(!confirm('Stop the next renewal? Your existing paid access continues through '+end+'. This does not issue a refund.'))return;state=await api('/api/billing/cancel',{orderId:order.id});render();message('Next renewal canceled.')}));
   $('orders').append(card);
  }
 }
 async function load(){try{session=await api('/api/auth/session');state=await api('/api/billing/status')}catch(e){if(e.status!==401)throw e;session=null;state=null}render()}
 async function checkout(plan){const result=await api('/api/billing/checkout',{plan});const url=new URL(result.url);if(url.protocol!=='https:'||url.hostname!=='checkout.stripe.com')throw Error('Unexpected checkout destination');location.assign(url.href)}
 document.querySelectorAll('[data-plan]').forEach(b=>b.onclick=()=>work(async()=>{chosen=b.dataset.plan;if(session){await checkout(chosen);return}$('selection').textContent=names[chosen];$('signup').hidden=false;$('signup').scrollIntoView({behavior:'smooth',block:'start'});$('signupName').focus({preventScroll:true})}));
 $('manageBilling').onclick=()=>work(async()=>{const result=await api('/api/billing/portal',{});const url=new URL(result.url);if(url.protocol!=='https:'||url.hostname!=='billing.stripe.com')throw Error('Unexpected billing destination');location.assign(url.href)});
 $('signupForm').onsubmit=e=>{e.preventDefault();work(async()=>{try{await api('/api/auth/signup',{name:$('signupName').value,email:$('signupEmail').value,password:$('signupPassword').value});$('signupForm').reset();await load();await checkout(chosen)}finally{$('signupPassword').value=''}})};
 work(async()=>{config=await api('/api/billing/plans');await load();const params=new URLSearchParams(location.search),order=params.get('order');if(order&&session){state=await api('/api/billing/refresh',{orderId:order});render();message(params.has('canceled')?'Checkout was left unfinished. Resume with the same plan or close it above.':'Your payment was checked with Stripe. Your current access is shown above.');history.replaceState(null,'','/membership.html')}if(params.has('training')&&!state?.access.training)message('Choose Training only or Software yearly to unlock the course.')});
})();
