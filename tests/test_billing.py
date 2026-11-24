"""Isolated provider-contract tests. These mocks do not certify Stripe checkout."""
import copy,hashlib,hmac,json,os,sys,tempfile,threading,time,unittest,urllib.request,urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import server as s, billing, accounts

class Provider:
 def __init__(self,cfg):self.cfg=cfg;self.objects={};self.sessions=0
 def price(self,plan):
  p=billing.PLANS[plan];return dict(id=self.cfg['prices'][plan],currency='usd',unit_amount=p['amount'],livemode=False,recurring={'interval':p['interval'],'interval_count':1} if p['interval'] else None)
 def __call__(self,cfg,method,path,params=None,key=None):
  params=params or {};name=path.split('/')[-1]
  if method=='GET':
   if path=='/v1/account':return {'id':cfg['accountId']}
   if '/prices/' in path:return self.price(next(k for k,v in cfg['prices'].items() if v==name))
   if path=='/v1/disputes':return {'data':[{'status':'won'}]}
   return copy.deepcopy(self.objects[name])
  if path=='/v1/customers':return {'id':'cus_'+params['metadata[rycf_tenant]'].replace('-','_')}
  if path=='/v1/checkout/sessions':
   self.sessions+=1;sid='cs_test_'+str(self.sessions);plan=next(k for k,v in cfg['prices'].items() if v==params['line_items[0][price]'])
   self.objects[sid]=dict(id=sid,object='checkout.session',url='https://checkout.stripe.com/c/pay/'+sid,customer=params['customer'],mode=params['mode'],livemode=False,client_reference_id=params['client_reference_id'],metadata={'rycf_order':params['metadata[rycf_order]']},status='open',payment_status='unpaid',line_items={'data':[{'quantity':1,'price':self.price(plan)}]},currency='usd',amount_subtotal=billing.PLANS[plan]['amount'])
   return copy.deepcopy(self.objects[sid])
  if name=='expire':self.objects[path.split('/')[-2]]['status']='expired';return {}
  if '/subscriptions/' in path:self.objects[name]['cancel_at_period_end']=True;return copy.deepcopy(self.objects[name])
  raise AssertionError((method,path))
 def pay(self,sid,plan):
  session=self.objects[sid];pi='pi_'+sid;sub='sub_'+sid;amount=billing.PLANS[plan]['amount']
  self.objects[pi]=dict(id=pi,livemode=False,status='succeeded',customer=session['customer'],currency='usd',amount_received=amount,latest_charge={'id':'ch_'+sid,'created':billing.stamp(),'refunded':False,'disputed':False})
  session.update(status='complete',payment_status='paid',payment_intent=pi)
  if plan!='training':
   session['subscription']=sub;invoice='in_'+sid
   self.objects[sub]=dict(id=sub,status='active',customer=session['customer'],metadata=session['metadata'],items={'data':[{'price':self.price(plan),'quantity':1}]},latest_invoice=dict(id=invoice,status='paid',amount_paid=amount,currency='usd',customer=session['customer'],subscription=sub,payment_intent=pi,lines={'data':[{'price':self.price(plan),'amount':amount,'period':{'end':billing.stamp()+86400}}]}))

class BillingTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=s.DB;s.DB=Path(self.tmp.name)/'test.sqlite3'
  self.cfg=dict(mode='test',accountId='acct_test',secretKey='sk_test_fake',webhookSecret='whsec_fake',prices={k:'price_'+k for k in billing.PLANS},origin='http://127.0.0.1:8765')
  p=Path(self.tmp.name)/'billing.json';p.write_text(json.dumps(self.cfg));p.chmod(0o600)
  self.env=patch.dict(os.environ,{'VYNE_BILLING_CONFIG':str(p),'VYNE_ORIGIN':self.cfg['origin'],'VYNE_ALLOW_LEGACY_KEYS':'0'});self.env.start();s.init()
  self.provider=Provider(self.cfg);self.provider_patch=patch.object(billing,'stripe',self.provider);self.provider_patch.start()
  self.http=s.ThreadingHTTPServer(('127.0.0.1',0),s.Handler);threading.Thread(target=self.http.serve_forever,daemon=True).start();self.base='http://127.0.0.1:'+str(self.http.server_port)
 def tearDown(self):
  self.http.shutdown();self.http.server_close();self.provider_patch.stop();self.env.stop();s.DB=self.old;self.tmp.cleanup()
 def req(self,path,body=None,auth=None,expected=200,extra=None):
  headers={'Content-Type':'application/json',**(auth or {}),**(extra or {})};raw=json.dumps(body).encode() if body is not None else None
  try:r=urllib.request.urlopen(urllib.request.Request(self.base+path,data=raw,headers=headers))
  except urllib.error.HTTPError as e:r=e
  with r:
   data=json.load(r);self.assertEqual(r.status,expected,data);return data,r.headers
 def signup(self,email='fictional@example.test'):
  data,h=self.req('/api/auth/signup',dict(name='Fictional Test',email=email,password='fictional-password-2026'),expected=201,extra={'X-Vyne-Session':'browser'})
  self.assertNotIn('accessToken',data);cookie=h['Set-Cookie'].split(';')[0]
  session,_=self.req('/api/auth/session',auth={'Cookie':cookie})
  return {'Cookie':cookie,'X-Vyne-CSRF':session['csrfToken']},session['actor']
 def purchase(self,auth,plan):
  result,_=self.req('/api/billing/checkout',{'plan':plan},auth);sid='cs_test_'+str(self.provider.sessions);self.provider.pay(sid,plan)
  self.req('/api/billing/refresh',{'orderId':result['orderId']},auth)
  return result['orderId'],sid
 def signed(self,event):
  raw=json.dumps(event).encode();ts=str(billing.stamp());sig=hmac.new(self.cfg['webhookSecret'].encode(),ts.encode()+b'.'+raw,hashlib.sha256).hexdigest();return raw,'t='+ts+',v1='+sig
 def test_three_plans_grant_only_paid_entitlements_and_reject_cross_tenant(self):
  for plan in billing.PLANS:
   auth,actor=self.signup(plan+'@example.test')
   self.req('/api/admin/profile',auth=auth,expected=403)
   self.req('/lesson-1-2.mp4',auth=auth,expected=403)
   self.assertFalse(self.req('/api/billing/status',auth=auth)[0]['access']['software'])
   order,sid=self.purchase(auth,plan)
   access=self.req('/api/billing/status',auth=auth)[0]['access'];self.assertEqual(access['software'],plan!='training');self.assertEqual(access['training'],plan!='monthly')
   self.req('/api/billing/checkout',{'plan':plan},auth,expected=409)
   outsider,_=self.signup('outsider-'+plan+'@example.test')
   self.req('/api/billing/refresh',{'orderId':order},outsider,expected=403)
 def test_session_csrf_tampering_and_duplicate_checkout(self):
  auth,actor=self.signup()
  self.req('/api/billing/checkout',{'plan':'yearly'},{'Cookie':auth['Cookie']},expected=403)
  self.req('/api/billing/checkout',{'plan':'yearly'},auth,expected=403,extra={'Origin':'https://evil.example'})
  self.req('/api/billing/checkout',{'plan':'yearly','amount':1},auth,expected=400)
  def start(_):return self.req('/api/billing/checkout',{'plan':'monthly'},auth)[0]
  with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(start,range(3)))
  self.assertEqual(len({r['orderId'] for r in results}),1);self.assertEqual(self.provider.sessions,1)
  self.req('/api/billing/checkout',{'plan':'yearly'},auth,expected=409)
  self.req('/api/billing/refresh',{'orderId':results[0]['orderId']},auth)
  self.assertFalse(self.req('/api/billing/status',auth=auth)[0]['access']['software'])
  self.req('/api/billing/expire',{'orderId':results[0]['orderId']},auth)
  self.req('/api/billing/checkout',{'plan':'yearly'},auth)
 def test_cancel_failed_renewal_refund_and_webhook_replay(self):
  auth,actor=self.signup();order,sid=self.purchase(auth,'yearly')
  out,_=self.req('/api/billing/cancel',{'orderId':order},auth);self.assertTrue(out['access']['training']);self.assertTrue(out['orders'][0]['cancel_at_period_end'])
  invoice=self.provider.objects['sub_'+sid]['latest_invoice'];end=invoice['lines']['data'][0]['period']['end'];invoice['status']='open'
  self.req('/api/billing/refresh',{'orderId':order},auth)
  self.assertEqual(self.req('/api/billing/status',auth=auth)[0]['orders'][0]['paid_until'],end)
  invoice['status']='paid';self.provider.objects['pi_'+sid]['latest_charge']['refunded']=True
  event=dict(id='evt_refund',type='charge.refunded',livemode=False,data={'object':{'id':'ch_'+sid,'payment_intent':'pi_'+sid}})
  raw,sig=self.signed(event);billing.webhook(s.DB,raw,sig,self.cfg);self.assertTrue(billing.webhook(s.DB,raw,sig,self.cfg)['duplicate'])
  self.assertFalse(self.req('/api/billing/status',auth=auth)[0]['access']['training'])
  with self.assertRaises(ValueError):billing.webhook(s.DB,raw+b' ',sig,self.cfg)
  bad=dict(event,livemode=True);raw,sig=self.signed(bad)
  with self.assertRaises(ValueError):billing.webhook(s.DB,raw,sig,self.cfg)
  old=dict(event,id='evt_old_checkout',type='checkout.session.completed');raw,sig=self.signed(old);billing.webhook(s.DB,raw,sig,self.cfg)
  self.assertFalse(self.req('/api/billing/status',auth=auth)[0]['access']['software'])
 def test_training_expiry_and_paid_invoice_binding(self):
  auth,actor=self.signup();order,sid=self.purchase(auth,'training')
  with billing.db(s.DB) as c:c.execute('UPDATE billing_orders SET paid_until=? WHERE id=?',(billing.stamp()-1,order))
  self.assertFalse(self.req('/api/billing/status',auth=auth)[0]['access']['training'])
  other,_=self.signup('other@example.test');order,sid=self.purchase(other,'monthly')
  self.provider.objects['sub_'+sid]['latest_invoice']['lines']['data'][0]['price']['id']='price_wrong'
  self.req('/api/billing/refresh',{'orderId':order},other,expected=400)
 def test_course_answers_are_scoped_to_new_student_and_unpaid_cannot_read_course(self):
  auth,actor=self.signup();self.purchase(auth,'training')
  req=urllib.request.Request(self.base+'/course.html',headers=auth)
  with urllib.request.urlopen(req) as r:html=r.read().decode();self.assertIn("storeKey='rycf-course-draft-v1-"+s.digest(actor['userId'])[:24],html)
  with urllib.request.urlopen(self.base+'/course.html') as r:self.assertTrue(r.url.endswith('/membership.html?training=1'))
 def test_mismatched_price_cannot_create_checkout_and_stale_intent_cannot_retry(self):
  auth,actor=self.signup()
  original=self.provider.price
  with patch.object(self.provider,'price',lambda p:{**original(p),'unit_amount':1}):self.req('/api/billing/checkout',{'plan':'monthly'},auth,expected=503)
  self.assertEqual(self.provider.sessions,0)
  with billing.db(s.DB) as c:c.execute('UPDATE billing_orders SET created_at=?',(billing.stamp()-86400,))
  self.req('/api/billing/checkout',{'plan':'monthly'},auth,expected=409)
 def test_limits_recheck_at_invitation_acceptance_and_vehicle_restore(self):
  auth,actor=self.signup();self.purchase(auth,'monthly')
  invite,_=self.req('/api/admin/accounts/invite',{'email':'staff@example.test','role':'operator'},auth,expected=201)
  self.req('/api/admin/accounts/invite',{'email':'third@example.test','role':'operator'},auth,expected=403)
  with billing.db(s.DB) as c:
   c.execute('UPDATE billing_orders SET paid_until=0')
  self.req('/api/auth/accept',{'invitationToken':invite['invitationToken'],'email':invite['email'],'name':'Test Staff','password':'fictional-password-2026'},expected=403)
  with billing.db(s.DB) as c:
   c.execute('UPDATE billing_orders SET paid_until=?',(billing.stamp()+86400,))
   for i in range(5):c.execute('INSERT INTO vehicles VALUES(?,?)',(str(i),json.dumps({'id':str(i),'tenantId':actor['tenantId']})))
   with self.assertRaises(billing.Forbidden):billing.enforce(c,actor,'POST','vehicles',{})
   with self.assertRaises(billing.Forbidden):billing.enforce(c,actor,'POST','records/vehicles/old/archive',{'archived':False})
 def test_existing_workspace_migration_is_once_and_retains_access(self):
  auth,actor=self.signup()
  with billing.db(s.DB) as c:
   c.execute('DELETE FROM billing_migrations');c.execute('DELETE FROM billing_accounts');billing.init(c)
   self.assertTrue(billing.access(c,actor,self.cfg)['grandfathered'])
  new_auth,new_actor=self.signup('new@example.test')
  with billing.db(s.DB) as c:billing.init(c);self.assertFalse(billing.access(c,new_actor,self.cfg)['grandfathered'])

if __name__=='__main__':unittest.main()
