"""Platform subscriptions, separate from rental-owner collections.

Stripe owns card collection. Browser redirects never grant access. Provider work
uses a separate lock/connection so slow checkout calls do not lock rental work.
The pinned API version is intentional; update it with provider contract tests.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import hashlib, hmac, json, os, re, secrets, sqlite3, threading, time
import accounts

API_VERSION = '2024-06-20'
PLANS = {
 'monthly': dict(name='Software monthly', amount=4900, interval='month', software=True, training=False, vehicles=5, seats=2),
 'yearly': dict(name='Software + training yearly', amount=49000, interval='year', software=True, training=True, vehicles=5, seats=2),
 'training': dict(name='Training only', amount=9900, interval=None, software=False, training=True, vehicles=0, seats=1),
}
SYNC_LOCK = threading.RLock()

class Unavailable(Exception): pass
class Forbidden(Exception): pass
class Conflict(Exception): pass

def stamp(): return int(time.time())
def identifier(value):
 if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_]{1,200}',value):raise ValueError('Invalid provider reference')
 return value
def oid(value): return value.get('id') if isinstance(value,dict) else value
def config():
 path=os.environ.get('VYNE_BILLING_CONFIG')
 if not path:return None
 p=Path(path)
 try:
  if p.is_symlink() or p.stat().st_mode&0o077:raise Unavailable('Billing configuration must be private')
  cfg=json.loads(p.read_text())
 except (OSError,ValueError):raise Unavailable('Billing configuration is unavailable') from None
 mode=cfg.get('mode')
 if mode not in ('test','live'):raise Unavailable('Billing is not configured')
 if not cfg.get('secretKey','').startswith(('sk_'+mode+'_','rk_'+mode+'_')):raise Unavailable('Billing key mode does not match')
 if not cfg.get('webhookSecret','').startswith('whsec_'):raise Unavailable('Billing event verification is not configured')
 if not cfg.get('accountId','').startswith('acct_'):raise Unavailable('Billing merchant must be selected')
 for plan in PLANS:
  if not cfg.get('prices',{}).get(plan,'').startswith('price_'):raise Unavailable('All three Stripe prices are required')
 if len(set(cfg['prices'].values()))!=3:raise Unavailable('Stripe prices must be distinct')
 origin=os.environ.get('VYNE_ORIGIN','http://127.0.0.1:8765');u=urlparse(origin)
 if u.scheme!='https' and not (u.scheme=='http' and u.hostname in ('127.0.0.1','localhost')):raise Unavailable('Secure checkout return origin required')
 cfg['origin']=origin.rstrip('/')
 # Live is explicit, never inferred by substituting a key into a test deployment.
 if mode=='live' and cfg.get('liveSalesApproved') is not True:raise Unavailable('Live sales are not enabled')
 return cfg

def public_config():
 try:cfg=config()
 except (Unavailable,OSError,ValueError):cfg=None
 return {'ready':bool(cfg),'mode':cfg['mode'] if cfg else 'unconfigured',
         'merchant':'Only One Worker','plans':[dict(id=k,currency='usd',**v) for k,v in PLANS.items()],
         'trainingAccessMonths':12,'liveRentalPayments':False}

def stripe(cfg,method,path,params=None,key=None):
 if not path.startswith('/v1/') or '..' in path:raise ValueError('Invalid Stripe resource')
 payload=urlencode(params or {},doseq=True)
 url='https://api.stripe.com'+path
 if method=='GET' and payload:url+='?'+payload
 headers={'Authorization':'Bearer '+cfg['secretKey'],'Stripe-Version':API_VERSION,
          'Content-Type':'application/x-www-form-urlencoded'}
 if key:headers['Idempotency-Key']=key
 request=Request(url,data=payload.encode() if method=='POST' else None,headers=headers,method=method)
 try:
  with urlopen(request,timeout=15) as response:return json.loads(response.read(2_000_000))
 except (HTTPError,URLError,TimeoutError,ValueError):
  raise Unavailable('Stripe could not confirm this request. Retry safely; access has not been changed.') from None

def init(c):
 c.executescript('''
 CREATE TABLE IF NOT EXISTS billing_migrations(name TEXT PRIMARY KEY);
 CREATE TABLE IF NOT EXISTS billing_merchants(mode TEXT PRIMARY KEY,account_id TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS billing_accounts(
 tenant_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, grandfathered INTEGER NOT NULL DEFAULT 0,
 created_at INTEGER NOT NULL);
 CREATE TABLE IF NOT EXISTS billing_customers(
 tenant_id TEXT NOT NULL, mode TEXT NOT NULL, customer_id TEXT UNIQUE NOT NULL,
 PRIMARY KEY(tenant_id,mode));
 CREATE TABLE IF NOT EXISTS billing_orders(
 id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL,plan TEXT NOT NULL,mode TEXT NOT NULL,
 created_at INTEGER NOT NULL,session_id TEXT UNIQUE,checkout_url TEXT,customer_id TEXT,
 subscription_id TEXT UNIQUE,payment_intent TEXT,state TEXT NOT NULL DEFAULT 'creating',
 paid_until INTEGER NOT NULL DEFAULT 0,blocked INTEGER NOT NULL DEFAULT 0,
 cancel_at_period_end INTEGER NOT NULL DEFAULT 0,invoice_id TEXT,verified_at INTEGER);
 CREATE TABLE IF NOT EXISTS billing_events(
 mode TEXT NOT NULL,id TEXT NOT NULL,payload_hash TEXT NOT NULL,type TEXT NOT NULL,
 processed_at INTEGER NOT NULL,PRIMARY KEY(mode,id));
 CREATE TABLE IF NOT EXISTS billing_course_progress(
 user_id TEXT PRIMARY KEY,revision INTEGER NOT NULL,data TEXT NOT NULL,updated_at INTEGER NOT NULL);
 ''')
 # Snapshot existing workspaces once; subsequent signup never becomes grandfathered.
 if not c.execute("SELECT 1 FROM billing_migrations WHERE name='preserve-existing-v1'").fetchone():
  for row in c.execute("SELECT tenant_id,MIN(user_id) owner_id FROM account_memberships WHERE role='owner' AND revoked_at IS NULL GROUP BY tenant_id").fetchall():
   c.execute('INSERT OR IGNORE INTO billing_accounts VALUES(?,?,1,?)',(row['tenant_id'],row['owner_id'],stamp()))
  c.execute("INSERT INTO billing_migrations VALUES('preserve-existing-v1')")

@contextmanager
def db(path):
 c=sqlite3.connect(path,timeout=30);c.row_factory=sqlite3.Row
 try:
  c.execute('BEGIN IMMEDIATE')
  with c:yield c
 finally:c.close()

def access(c,actor,cfg=None):
 if not actor:return dict(software=False,training=False,grandfathered=False,vehicles=0,seats=0)
 row=c.execute('SELECT * FROM billing_accounts WHERE tenant_id=?',(actor['tenantId'],)).fetchone()
 if row and row['grandfathered']:return dict(software=True,training=True,grandfathered=True,vehicles=None,seats=None)
 result=dict(software=False,training=False,grandfathered=False,vehicles=0,seats=0)
 # Before provider configuration, old invitation-only workspaces retain their access.
 if not row and not os.environ.get('VYNE_BILLING_CONFIG'):
  return dict(software=True,training=True,grandfathered=True,vehicles=None,seats=None)
 cfg=cfg if cfg is not None else config()
 if not cfg:return result
 for order in c.execute('SELECT * FROM billing_orders WHERE tenant_id=? AND mode=? AND paid_until>? AND blocked=0',(actor['tenantId'],cfg['mode'],stamp())):
  plan=PLANS[order['plan']]
  for k in ('software','training'):result[k]=result[k] or plan[k]
  for k in ('vehicles','seats'):result[k]=max(result[k],plan[k])
 return result

def require_owner(actor):
 if not actor:raise Forbidden('Sign in to continue')
 if actor.get('role')!='owner':raise Forbidden('Only the workspace owner can manage its plan')

def register(c,body,peer):
 accounts.fields(body,('name','email','password'))
 name=accounts.text(body['name']);email=accounts.email(body['email']);password=accounts.password(body['password'])
 if accounts.limited(c,'signup:'+accounts.digest(email)) or not accounts.throttle(c,'signup-ip:'+accounts.digest(peer),10,3600):
  return 429,{'error':'Too many signup attempts. Please try again later.'}
 existing=c.execute('SELECT id FROM account_users WHERE email=?',(email,)).fetchone()
 if existing:return 409,{'error':'This email cannot create another account. Sign in with your existing account.'}
 uid=secrets.token_hex(16);mid=secrets.token_hex(16);tenant='fleet-'+secrets.token_hex(12);salt=secrets.token_bytes(16)
 c.execute('INSERT INTO account_users VALUES(?,?,?,?,?,?)',(uid,email,name,salt.hex(),accounts.derive(password,salt),accounts.now().isoformat()))
 c.execute('INSERT INTO account_memberships VALUES(?,?,?,?,NULL)',(mid,uid,tenant,'owner'))
 c.execute('INSERT INTO billing_accounts VALUES(?,?,0,?)',(tenant,uid,stamp()))
 accounts.event(c,tenant,mid,'signup',uid)
 return 201,accounts.new_session(c,mid)

def status(c,actor,cfg):
 if not actor:raise Forbidden('Sign in to view your membership')
 orders=[]
 if cfg:
  for row in c.execute('SELECT id,plan,state,paid_until,cancel_at_period_end,blocked FROM billing_orders WHERE tenant_id=? AND mode=? ORDER BY created_at DESC',(actor['tenantId'],cfg['mode'])):
   orders.append(dict(row))
 return dict(actor=actor,access=access(c,actor,cfg),orders=orders,**public_config())

def check_plan_price(price,plan,cfg):
 expected=PLANS[plan];recurring=price.get('recurring') or {}
 if not (price.get('id')==cfg['prices'][plan] and price.get('currency')=='usd'
         and price.get('unit_amount')==expected['amount'] and price.get('livemode')==(cfg['mode']=='live')
         and recurring.get('interval')==expected['interval'] and (not expected['interval'] or recurring.get('interval_count')==1)):
  raise Unavailable('Stripe price does not match the selected plan. No purchase can start.')

def checkout(path,actor,plan,cfg):
 require_owner(actor)
 if plan not in PLANS:raise ValueError('Choose an available plan')
 with SYNC_LOCK:
  with db(path) as c:
   bind_merchant(c,cfg)
   ent=access(c,actor,cfg)
   if ent['grandfathered'] or (plan=='training' and ent['training']):raise Conflict('This workspace already includes that access. No additional purchase is needed.')
   # Same category cannot create a second paid subscription or duplicate course.
   category=('training',) if plan=='training' else ('monthly','yearly')
   orders=c.execute('SELECT * FROM billing_orders WHERE tenant_id=? AND mode=? ORDER BY created_at DESC',(actor['tenantId'],cfg['mode'])).fetchall()
   relevant=[r for r in orders if r['plan'] in category]
  for order in relevant:
   if order['session_id']:reconcile(path,order['id'],cfg)
  with db(path) as c:
   relevant=[r for r in c.execute('SELECT * FROM billing_orders WHERE tenant_id=? AND mode=? ORDER BY created_at DESC',(actor['tenantId'],cfg['mode'])) if r['plan'] in category]
   if any(r['paid_until']>stamp() or (r['subscription_id'] and r['state'] not in ('canceled','incomplete_expired')) for r in relevant):
    raise Conflict('You already have this membership. Manage it from your account rather than buying it again.')
   order=next((r for r in relevant if r['state'] in ('creating','open','pending')),None)
   if order and order['plan']!=plan:raise Conflict('Finish or cancel your open checkout before choosing a different plan.')
   if order and order['checkout_url']:return {'url':order['checkout_url'],'orderId':order['id'],'mode':cfg['mode']}
   if order and stamp()-order['created_at']>=23*3600:raise Conflict('This unfinished checkout needs support review before retrying.')
   if not order:
    if not accounts.throttle(c,'checkout:'+actor['tenantId'],10,3600):raise Conflict('Too many checkout attempts. Please try later.')
    order_id=secrets.token_hex(16)
    c.execute('INSERT INTO billing_orders(id,tenant_id,plan,mode,created_at) VALUES(?,?,?,?,?)',(order_id,actor['tenantId'],plan,cfg['mode'],stamp()))
    order=c.execute('SELECT * FROM billing_orders WHERE id=?',(order_id,)).fetchone()
   customer=c.execute('SELECT customer_id FROM billing_customers WHERE tenant_id=? AND mode=?',(actor['tenantId'],cfg['mode'])).fetchone()
  # Verify selected merchant and prices before creating any chargeable session.
  merchant=stripe(cfg,'GET','/v1/account')
  if merchant.get('id')!=cfg['accountId']:raise Unavailable('Stripe merchant does not match this deployment')
  check_plan_price(stripe(cfg,'GET','/v1/prices/'+identifier(cfg['prices'][plan])),plan,cfg)
  if not customer:
   new=stripe(cfg,'POST','/v1/customers',{'email':actor['email'],'name':actor['name'],'metadata[rycf_tenant]':actor['tenantId']},'rycf-customer-'+cfg['mode']+'-'+actor['tenantId'])
   customer_id=identifier(new['id'])
   with db(path) as c:c.execute('INSERT INTO billing_customers VALUES(?,?,?)',(actor['tenantId'],cfg['mode'],customer_id))
  else:customer_id=customer['customer_id']
  with db(path) as c:c.execute('UPDATE billing_orders SET customer_id=? WHERE id=?',(customer_id,order['id']))
  mode='subscription' if PLANS[plan]['interval'] else 'payment'
  params={'mode':mode,'customer':customer_id,'line_items[0][price]':cfg['prices'][plan],
   'line_items[0][quantity]':1,'payment_method_types[0]':'card','client_reference_id':order['id'],
   'metadata[rycf_order]':order['id'],'metadata[rycf_tenant]':actor['tenantId'],
   'success_url':cfg['origin']+'/membership.html?order='+order['id'],
   'cancel_url':cfg['origin']+'/membership.html?canceled=1&order='+order['id'],
   'billing_address_collection':'required'}
  if mode=='subscription':params.update({'subscription_data[metadata][rycf_order]':order['id'],'subscription_data[metadata][rycf_tenant]':actor['tenantId']})
  else:params['payment_intent_data[metadata][rycf_order]']=order['id']
  session=stripe(cfg,'POST','/v1/checkout/sessions',params,'rycf-checkout-'+order['id'])
  if session.get('livemode')!=(cfg['mode']=='live') or urlparse(session.get('url','')).netloc!='checkout.stripe.com':raise Unavailable('Stripe returned an unexpected checkout')
  with db(path) as c:c.execute("UPDATE billing_orders SET session_id=?,checkout_url=?,customer_id=?,state='open' WHERE id=?",(identifier(session['id']),session['url'],customer_id,order['id']))
  return {'url':session['url'],'orderId':order['id'],'mode':cfg['mode']}

def charge_state(cfg,payment_intent,customer,amount):
 if not payment_intent:return None
 pi=stripe(cfg,'GET','/v1/payment_intents/'+identifier(oid(payment_intent)),{'expand[]':'latest_charge'})
 charge=pi.get('latest_charge')
 if not isinstance(charge,dict) or pi.get('status')!='succeeded':return None
 if pi.get('livemode')!=(cfg['mode']=='live'):raise ValueError('Payment mode mismatch')
 if oid(pi.get('customer'))!=customer or pi.get('currency')!='usd' or pi.get('amount_received',0)<amount:raise ValueError('Payment ownership or amount mismatch')
 disputed=bool(charge.get('disputed'))
 if disputed:
  disputes=stripe(cfg,'GET','/v1/disputes',{'charge':charge['id'],'limit':10})
  disputed=not disputes.get('data') or any(d.get('status')!='won' for d in disputes['data'])
 return dict(id=pi['id'],blocked=bool(charge.get('refunded') or disputed),created=charge.get('created',0))

def bind_merchant(c,cfg):
 row=c.execute('SELECT account_id FROM billing_merchants WHERE mode=?',(cfg['mode'],)).fetchone()
 if row and row[0]!=cfg['accountId']:raise Unavailable('This database is bound to a different Stripe merchant')
 c.execute('INSERT OR IGNORE INTO billing_merchants VALUES(?,?)',(cfg['mode'],cfg['accountId']))

def reconcile(path,order_id,cfg):
 with SYNC_LOCK:
  with db(path) as c:
   bind_merchant(c,cfg)
   row=c.execute('SELECT * FROM billing_orders WHERE id=? AND mode=?',(order_id,cfg['mode'])).fetchone()
  if not row or not row['session_id']:return
  session=stripe(cfg,'GET','/v1/checkout/sessions/'+identifier(row['session_id']),{'expand[]':'line_items'})
  items=session.get('line_items',{}).get('data',[])
  if session.get('livemode')!=(cfg['mode']=='live') or session.get('client_reference_id')!=row['id'] or oid(session.get('customer'))!=row['customer_id'] or session.get('metadata',{}).get('rycf_order')!=row['id']:
   raise ValueError('Checkout does not belong to this purchase')
  if len(items)!=1 or items[0].get('quantity')!=1:raise ValueError('Unexpected checkout items')
  check_plan_price(items[0]['price'],row['plan'],cfg)
  plan=PLANS[row['plan']];state=session.get('status','pending');end=row['paid_until'];blocked=row['blocked'];cancel=0;subid=None;invoice_id=None;pi=None
  if plan['interval']:
   if session.get('mode')!='subscription':raise ValueError('Checkout type mismatch')
   subid=oid(session.get('subscription'))
   if subid:
    sub=stripe(cfg,'GET','/v1/subscriptions/'+identifier(subid),{'expand[]':'latest_invoice'})
    si=sub.get('items',{}).get('data',[])
    if len(si)!=1 or si[0].get('quantity')!=1 or oid(sub.get('customer'))!=row['customer_id'] or sub.get('metadata',{}).get('rycf_order')!=row['id']:raise ValueError('Subscription does not belong to this purchase')
    check_plan_price(si[0]['price'],row['plan'],cfg)
    state=sub['status'];cancel=int(bool(sub.get('cancel_at_period_end')));invoice=sub.get('latest_invoice')
    if isinstance(invoice,str):invoice=stripe(cfg,'GET','/v1/invoices/'+identifier(invoice))
    if isinstance(invoice,dict) and invoice.get('status')=='paid' and invoice.get('amount_paid',0)>=plan['amount'] and invoice.get('currency')=='usd':
     if oid(invoice.get('customer'))!=row['customer_id'] or oid(invoice.get('subscription'))!=subid:raise ValueError('Invoice ownership mismatch')
     paid=charge_state(cfg,invoice.get('payment_intent'),row['customer_id'],plan['amount']);invoice_id=invoice['id']
     if paid:
      pi=paid['id'];blocked=int(paid['blocked'])
      lines=invoice.get('lines',{}).get('data',[])
      matching=[line for line in lines if oid(line.get('price'))==cfg['prices'][row['plan']] and not line.get('proration') and line.get('amount',0)>=plan['amount']]
      if len(matching)!=1:raise ValueError('Verified paid invoice period required')
      period=matching[0].get('period',{}).get('end')
      if not isinstance(period,int):raise ValueError('Verified subscription period required')
      end=max(end,period)
  else:
   if session.get('mode')!='payment':raise ValueError('Checkout type mismatch')
   if session.get('payment_status')=='paid' and session.get('amount_subtotal')==plan['amount'] and session.get('currency')=='usd':
    paid=charge_state(cfg,session.get('payment_intent'),row['customer_id'],plan['amount'])
    if paid:
     pi=paid['id'];blocked=int(paid['blocked']);state='paid'
     start=datetime.fromtimestamp(paid['created'],timezone.utc)
     try:finish=start.replace(year=start.year+1)
     except ValueError:finish=start.replace(year=start.year+1,day=28)
     end=int(finish.timestamp())
  with db(path) as c:
   c.execute('''UPDATE billing_orders SET state=?,paid_until=?,blocked=?,cancel_at_period_end=?,
    subscription_id=COALESCE(?,subscription_id),payment_intent=COALESCE(?,payment_intent),invoice_id=COALESCE(?,invoice_id),verified_at=? WHERE id=?''',
    (state,end,blocked,cancel,subid,pi,invoice_id,stamp(),row['id']))

def verify_event(raw,signature,cfg):
 if not isinstance(signature,str):raise ValueError('Stripe signature required')
 pieces={}
 for piece in signature.split(','):
  k,_,v=piece.partition('=');pieces.setdefault(k,[]).append(v)
 try:t=int(pieces['t'][0])
 except (KeyError,ValueError):raise ValueError('Stripe signature required') from None
 if abs(stamp()-t)>300:raise ValueError('Stripe signature expired')
 expected=hmac.new(cfg['webhookSecret'].encode(),str(t).encode()+b'.'+raw,hashlib.sha256).hexdigest()
 if not any(hmac.compare_digest(expected,x) for x in pieces.get('v1',[])):raise ValueError('Stripe signature invalid')
 event=json.loads(raw)
 if event.get('livemode')!=(cfg['mode']=='live') or event.get('account'):raise ValueError('Stripe event account or mode mismatch')
 identifier(event.get('id'));return event

def webhook(path,raw,signature,cfg):
 event=verify_event(raw,signature,cfg);event_hash=hashlib.sha256(raw).hexdigest();obj=event.get('data',{}).get('object',{})
 if event.get('type','').startswith('charge.dispute.') and not obj.get('payment_intent') and obj.get('charge'):
  charge=stripe(cfg,'GET','/v1/charges/'+identifier(oid(obj['charge'])))
  obj={**obj,'payment_intent':charge.get('payment_intent')}
 with SYNC_LOCK:
  with db(path) as c:
   old=c.execute('SELECT payload_hash FROM billing_events WHERE mode=? AND id=?',(cfg['mode'],event['id'])).fetchone()
   if old:
    if old[0]!=event_hash:raise ValueError('Conflicting event replay')
    return {'received':True,'duplicate':True}
   references=[obj.get('id'),oid(obj.get('subscription')),oid(obj.get('payment_intent')),obj.get('metadata',{}).get('rycf_order')]
   rows=c.execute('SELECT * FROM billing_orders WHERE mode=?',(cfg['mode'],)).fetchall()
   targets=[r for r in rows if any(x and x in references for x in [r['id'],r['session_id'],r['subscription_id'],r['payment_intent'],r['invoice_id']])]
  for row in targets:
   if not row['session_id'] and obj.get('object')=='checkout.session':
    session=stripe(cfg,'GET','/v1/checkout/sessions/'+identifier(obj['id']))
    if session.get('client_reference_id')!=row['id'] or oid(session.get('customer'))!=row['customer_id'] or session.get('metadata',{}).get('rycf_order')!=row['id'] or session.get('livemode')!=(cfg['mode']=='live'):raise ValueError('Checkout recovery ownership mismatch')
    with db(path) as c:c.execute('UPDATE billing_orders SET session_id=? WHERE id=? AND session_id IS NULL',(session['id'],row['id']))
   reconcile(path,row['id'],cfg)
  with db(path) as c:c.execute('INSERT INTO billing_events VALUES(?,?,?,?,?)',(cfg['mode'],event['id'],event_hash,event.get('type',''),stamp()))
 return {'received':True}

def enforce(c,actor,method,route,body):
 """Paid workspace gate plus plan limits; old workspaces are explicitly retained."""
 ent=access(c,actor)
 if ent['grandfathered']:return
 if route=='accounts' or route.startswith('accounts/revoke'):return
 if not ent['software']:raise Forbidden('An active software plan is required. Open Membership to continue.')
 if method=='POST' and (route=='vehicles' or (route.startswith('records/vehicles/') and route.endswith('/archive') and body.get('archived') is False)):
  count=sum(1 for r in c.execute('SELECT data FROM vehicles') if (v:=json.loads(r[0])).get('tenantId')==actor['tenantId'] and not v.get('archived'))
  if count>=ent['vehicles']:raise Forbidden('This plan includes five active vehicles.')
 if method=='POST' and route=='accounts/invite':
  existing=c.execute('''SELECT 1 FROM account_memberships m JOIN account_users u ON u.id=m.user_id WHERE m.tenant_id=? AND m.revoked_at IS NULL AND u.email=?''',(actor['tenantId'],str(body.get('email','')).lower())).fetchone()
  if not existing:
   seats=c.execute('SELECT COUNT(*) FROM account_memberships WHERE tenant_id=? AND revoked_at IS NULL',(actor['tenantId'],)).fetchone()[0]
   pending=c.execute('SELECT COUNT(DISTINCT email) FROM account_invitations WHERE tenant_id=? AND used_at IS NULL AND revoked_at IS NULL AND expires_at>? AND email!=?',(actor['tenantId'],accounts.now().isoformat(),str(body.get('email','')).lower())).fetchone()[0]
   if seats+pending>=ent['seats']:raise Forbidden('This plan includes two staff accounts, including the owner.')
 if method=='POST' and route=='staff':raise Forbidden('Invite individual accounts from Account to manage plan seats.')

def accept_invitation(c,invitation):
 if not c.execute("SELECT 1 FROM sqlite_master WHERE name='billing_accounts'").fetchone():return
 ent=access(c,{'tenantId':invitation['tenant_id']})
 if ent['grandfathered']:return
 if not ent['software']:raise Forbidden('The workspace needs an active software plan before adding staff.')
 count=c.execute('SELECT COUNT(*) FROM account_memberships WHERE tenant_id=? AND revoked_at IS NULL',(invitation['tenant_id'],)).fetchone()[0]
 if count>=ent['seats']:raise Forbidden('This plan includes two staff accounts, including the owner.')

def owned_order(c,actor,order_id,cfg):
 require_owner(actor)
 row=c.execute('SELECT * FROM billing_orders WHERE id=? AND tenant_id=? AND mode=?',(identifier(order_id),actor['tenantId'],cfg['mode'])).fetchone()
 if not row:raise Forbidden('Purchase unavailable for this account')
 return row

def manage(path,actor,action,body,cfg):
 accounts.fields(body,('orderId',))
 with SYNC_LOCK:
  with db(path) as c:row=owned_order(c,actor,body['orderId'],cfg)
  if action=='refresh':
   reconcile(path,row['id'],cfg)
  elif action=='expire':
   if row['session_id']:
    session=stripe(cfg,'GET','/v1/checkout/sessions/'+identifier(row['session_id']))
    if session.get('status')=='open':stripe(cfg,'POST','/v1/checkout/sessions/'+identifier(row['session_id'])+'/expire',{},'rycf-expire-'+row['id'])
    reconcile(path,row['id'],cfg)
   else:raise Conflict('Checkout creation is still being confirmed. Retry or contact support.')
  elif action=='cancel':
   if not row['subscription_id']:raise Conflict('No recurring subscription is attached to this purchase.')
   stripe(cfg,'POST','/v1/subscriptions/'+identifier(row['subscription_id']),{'cancel_at_period_end':'true'},'rycf-cancel-'+row['id'])
   reconcile(path,row['id'],cfg)
  else:raise ValueError('Unknown membership action')
  with db(path) as c:return status(c,actor,cfg)

def handle_http(handler,path,database):
 """Own transactions; never hold the application's rental lock during Stripe IO."""
 import account_transport
 cfg=config();body={};raw=b'';method=handler.command
 if method=='POST':
  if os.environ.get('VYNE_READ_ONLY_RECOVERY')=='1':raise Unavailable('Workspace is read-only during recovery')
  if handler.headers.get('Origin') and handler.headers['Origin']!=os.environ.get('VYNE_ORIGIN','http://127.0.0.1:8765'):raise Forbidden('Origin rejected')
  size=int(handler.headers.get('Content-Length','0'))
  if not 0<size<=128000:raise ValueError('Invalid request size')
  raw=handler.rfile.read(size)
  if path!='/api/billing/webhook':
   body=json.loads(raw)
   if not isinstance(body,dict):raise ValueError('JSON object required')
 if path=='/api/billing/plans' and method=='GET':return 200,public_config()
 if path=='/api/billing/webhook' and method=='POST':
  if not cfg:raise Unavailable('Billing is not connected yet')
  return 200,webhook(database,raw,handler.headers.get('Stripe-Signature'),cfg)
 authorization=handler.headers.get('Authorization','').strip()
 cookie=account_transport.cookie_token(handler.headers) if not authorization else ''
 token=authorization.removeprefix('Bearer ').strip() if authorization.startswith('Bearer ') else cookie
 if path=='/api/auth/signup' and method=='POST':
  if not cfg:raise Unavailable('Signup will open when checkout is connected')
  with db(database) as c:
   result,payload=register(c,body,handler.client_address[0])
   if result==201 and handler.headers.get('X-Vyne-Session')=='browser':
    token=payload.pop('accessToken');handler.response_headers['Set-Cookie']=account_transport.session_cookie(token,cfg['origin'])
  return result,payload
 with db(database) as c:actor=accounts.authenticate(c,token)
 if not actor:return 401,{'error':'Sign in to view your membership'}
 if method=='POST' and cookie and not account_transport.valid_csrf(handler.headers,cookie):raise Forbidden('Browser session verification required; sign in again')
 if path=='/api/billing/status' and method=='GET':
  with db(database) as c:return 200,status(c,actor,cfg)
 if not cfg:raise Unavailable('Billing is not connected yet')
 if method=='POST' and path=='/api/billing/checkout':
  accounts.fields(body,('plan',));return 200,checkout(database,actor,body['plan'],cfg)
 if method=='POST' and path=='/api/billing/portal':
  accounts.fields(body,());require_owner(actor)
  if not cfg.get('portalConfiguration'):raise Unavailable('Billing management is not connected yet')
  with db(database) as c:
   bind_merchant(c,cfg)
   customer=c.execute('SELECT customer_id FROM billing_customers WHERE tenant_id=? AND mode=?',(actor['tenantId'],cfg['mode'])).fetchone()
  if not customer:raise Conflict('Start a checkout before opening billing management')
  result=stripe(cfg,'POST','/v1/billing_portal/sessions',{'customer':customer['customer_id'],'configuration':identifier(cfg['portalConfiguration']),'return_url':cfg['origin']+'/membership.html'})
  if urlparse(result.get('url','')).netloc!='billing.stripe.com':raise Unavailable('Unexpected billing portal destination')
  return 200,{'url':result['url']}
 if method=='POST' and path.removeprefix('/api/billing/') in ('refresh','expire','cancel'):
  return 200,manage(database,actor,path.rsplit('/',1)[1],body,cfg)
 return 404,{'error':'Membership route unavailable'}
