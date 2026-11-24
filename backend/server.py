"""Local review server. No payment, insurance, email, or production signing provider."""
from zoneinfo import ZoneInfo
from contextlib import contextmanager
import os, json, sqlite3, secrets, hashlib, html, re, threading, subprocess
import billing
import quote_offers, document_artifacts, booking_candidates, rental_extensions, candidate_signing, candidate_signing_service, rental_payments, payment_routes, health, academy, transactions, journey, staff, maintenance, document_versions, document_review_routes, standalone_documents, accounts, account_transport, records, candidate_routes, signing_operations, signing_service, cancellation_requests, cancellation_service
from availability import assert_available
from money import cents
from pathlib import Path
from datetime import datetime, timezone, timedelta
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1]
TENANT=threading.local()
DB=Path(os.environ.get('VYNE_DB', ROOT/'backend/data.sqlite3'))
LOCK=threading.RLock()
def now(): return datetime.now(timezone.utc).isoformat()
def digest(v): return hashlib.sha256(v.encode()).hexdigest()
def canonical(v): return json.dumps(v,sort_keys=True,separators=(',',':'))
@contextmanager
def connect():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
 try:
  with c: yield c
 finally: c.close()
def init():
 DB.parent.mkdir(parents=True,exist_ok=True)
 with connect() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS vehicles(id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS customers(id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS profiles(id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS bookings(id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS templates(id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agreements(id TEXT PRIMARY KEY, booking TEXT NOT NULL, token TEXT, expires TEXT, state TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY, at TEXT, agreement TEXT, event TEXT, evidence TEXT, previous TEXT, hash TEXT);''')
  records.init(c)
  accounts.init(c)
  billing.init(c)
  staff.init(c)
  maintenance.init(c)
  document_versions.init(c)
  candidate_routes.init(c)
  standalone_documents.init(c)
  academy.init(c)
  transactions.init(c)
  journey.init(c)
  signing_operations.init(c)
  cancellation_requests.init(c)
  candidate_signing.init(c)
  rental_payments.init(c)
  booking_candidates.init(c)
  rental_extensions.init(c)
  quote_offers.init(c)
 try: os.chmod(DB,0o600)
 except OSError: pass
def audit(c,aid,event,evidence):
 prev=c.execute('SELECT hash FROM audit ORDER BY seq DESC LIMIT 1').fetchone(); prev=prev[0] if prev else ''
 at=now(); raw=canonical([at,aid,event,evidence,prev]); c.execute('INSERT INTO audit(at,agreement,event,evidence,previous,hash) VALUES(?,?,?,?,?,?)',(at,aid,event,canonical(evidence),prev,digest(raw)))
def fail(message): raise ValueError(message)
def text(v,n=500):
 if not isinstance(v,str) or not v.strip() or len(v)>n: fail('Missing or invalid text')
 return v.strip()
FLEET={'Mercedes-Benz S-Class':299,'Cadillac Escalade':349,'Porsche 911 Carrera':499,'BMW 7 Series':279,'Lamborghini Urus':899,'Bentley Continental GT':749}
def create_booking(c,b):
 vr=c.execute('SELECT data FROM vehicles WHERE id=?',(b.get('vehicleId'),)).fetchone(); cr=c.execute('SELECT data FROM customers WHERE id=?',(b.get('customerId'),)).fetchone()
 if not vr or not cr: fail('Saved vehicle and customer required')
 vehicleRecord=json.loads(vr[0]); customerRecord=json.loads(cr[0])
 records.assert_usable(vehicleRecord);records.assert_usable(customerRecord)
 if vehicleRecord['tenantId']!=TENANT.id or customerRecord['tenantId']!=TENANT.id: fail('Vehicle or customer unavailable')
 vehicle=vehicleRecord['make']+' '+vehicleRecord['model']; rate=vehicleRecord['dailyRate']; rateCents=cents(rate)
 name=customerRecord['name'];email=customerRecord['email'];phone=customerRecord['phone']
 start=datetime.strptime(b.get('pickup',''),'%Y-%m-%d').date(); end=datetime.strptime(b.get('return',''),'%Y-%m-%d').date(); days=(end-start).days
 if start<datetime.now(ZoneInfo('America/Chicago')).date() or not 1<=days<=90: fail('Invalid rental dates')
 contract_facts={}
 supplied_times={k:b.get(k) for k in ('startAt','endAt') if b.get(k) not in (None,'')}
 if supplied_times:
  if set(supplied_times)!={'startAt','endAt'}: fail('Supply both exact pickup and return times')
  parsed={}
  for key,expected in [('startAt',start),('endAt',end)]:
   value=supplied_times[key]
   if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})',value): fail('Exact times require ISO date/time with explicit UTC offset')
   stamp=datetime.fromisoformat(value)
   if stamp.utcoffset() is None or stamp.astimezone(ZoneInfo('America/Chicago')).date()!=expected: fail('Exact time must match the rental date in America/Chicago')
   parsed[key]=stamp;contract_facts[key]=stamp.isoformat()
  if parsed['endAt']<=parsed['startAt']: fail('Exact return time must follow pickup')
 for key in ('pickupAddress','returnAddress'):
  if b.get(key) not in (None,''): contract_facts[key]=text(b[key],2000)
 assert_available(c,TENANT.id,vehicleRecord['id'],str(start),str(end))
 bid='VYN-'+secrets.token_hex(6).upper(); data=dict(tenantId=TENANT.id,vehicleRecord=vehicleRecord,customerRecord=customerRecord,rentalDetails=b.get('rentalDetails',{}),partner=b.get('partner',{}),agreement=b.get('agreement',{}),id=bid,name=name,email=email,phone=phone,vehicle=vehicle,pickup=str(start),returnDate=str(end),days=days,rate=rate,rateCents=rateCents,totalCents=rateCents*days,total=(rateCents*days)/100,status='requested',demo=b.get('demo') is True,payment='not_collected',insurance='not_issued')
 data.update(contract_facts)
 c.execute('INSERT INTO bookings VALUES(?,?)',(bid,canonical(data))); audit(c,bid,'booking_requested',{'bookingHash':digest(canonical(data))}); return data
def register_template(c,b):
 # Owner review is explicit; never auto-import inferred contract language.
 if b.get('ownerReviewed') is not True: fail('Owner review required')
 content=text(b.get('content'),200000); fields=b.get('fields',[])
 if not isinstance(fields,list) or not fields or len(fields)>100: fail('Required signature/initial fields needed')
 for f in fields:
  if not isinstance(f,dict) or f.get('kind') not in ['signature','initials']: fail('Invalid signing field')
  text(f.get('id'),80); text(f.get('label'),500)
 if len({f['id'] for f in fields})!=len(fields): fail('Duplicate fields')
 tokens=set(re.findall(r'{{(.*?)}}',content))
 if not tokens or any(not re.fullmatch(r'(business|customer|vehicle|rental|partner|agreement)\.[A-Za-z]+',k) for k in tokens): fail('Use canonical business/customer/vehicle/rental placeholders')
 autofillFields=b.get('autofillFields')
 if not isinstance(autofillFields,list): fail('Autofill field definitions required')
 sourceHash=text(b.get('sourceHash'),64)
 if not re.fullmatch('[a-f0-9]{64}',sourceHash): fail('Original source SHA-256 required')
 data=dict(tenantId=TENANT.id,name=text(b.get('name')),source=text(b.get('source'),2000),sourceHash=sourceHash,content=content,fields=fields,autofillFields=autofillFields,reviewedAt=now(),mode='local_review')
 tid=digest(canonical(data)); c.execute('INSERT INTO templates VALUES(?,?)',(tid,canonical(data))); audit(c,tid,'template_registered',{'hash':tid,'source':data['source']}); return dict(id=tid,**data)
def draft(c,b):
 row=c.execute('SELECT data FROM bookings WHERE id=?',(b.get('bookingId'),)).fetchone(); tr=c.execute('SELECT data FROM templates WHERE id=?',(b.get('templateId'),)).fetchone()
 if not row or not tr: fail('Booking or reviewed template missing')
 if json.loads(row[0])['tenantId']!=TENANT.id or json.loads(tr[0])['tenantId']!=TENANT.id: fail('Booking or reviewed template missing')
 booking=json.loads(row[0]); template=json.loads(tr[0])
 profile=c.execute('SELECT data FROM profiles WHERE id=?',(TENANT.id,)).fetchone()
 if not profile: fail('Save the business profile first')
 business=json.loads(profile[0]); tenant={'tenantId':TENANT.id}
 context=dict(tenantId=TENANT.id,partner=dict(booking.get('partner',{}),**tenant),agreement=dict(booking.get('agreement',{}),**tenant),business=business,customer=booking['customerRecord'],vehicle=booking['vehicleRecord'],rental=dict(booking['rentalDetails'],**tenant,dailyRate=cents(booking['rate'])),settings=dict(locale='en-US',currency='USD',timeZone='America/Chicago'))
 context['rental'].update({k:booking[k] for k in ('startAt','endAt','pickupAddress','returnAddress') if k in booking})
 engineTemplate=dict(id=b['templateId'],version=template['reviewedAt'],body=template['content'],source=dict(fileName=template['source'],sha256=template['sourceHash']),fields=template['autofillFields'],approved=template.get('approved',True),blockers=template.get('blockers',[]))
 snapshot=autofill(dict(action='courseDraft',id=template['courseId'],context=context)) if template.get('courseId') else autofill(dict(template=engineTemplate,context=context,allowDraft=True))
 content=snapshot['text']
 aid=secrets.token_hex(16); data=dict(tenantId=TENANT.id,id=aid,bookingId=booking['id'],templateId=b['templateId'],template=template,content=content,contentHash=digest(content),snapshot=snapshot,createdAt=now(),mode='local_review')
 c.execute('INSERT INTO agreements VALUES(?,?,NULL,NULL,?,?)',(aid,booking['id'],'draft',canonical(data))); audit(c,aid,'draft_created',{'contentHash':data['contentHash'],'templateId':b['templateId']}); return data
def autofill(payload):
 result=subprocess.run(['node',str(ROOT/'backend/autofill.mjs')],input=canonical(payload),text=True,capture_output=True,timeout=15)
 if result.returncode: fail(result.stderr.strip()[:2000] or 'Autofill validation failed')
 return json.loads(result.stdout)
def seed_sources(c):
 sourceFile=ROOT/'template-autofill/course-preview-templates.json'
 if not sourceFile.exists(): return
 for source in autofill({'action':'sources'}):
  tid=digest(TENANT.id+source['id']+source['source']['sha256']+source['sourceTextHash']+source['authoritativeMappingHash']+digest(source['body'])+source['version'])
  if c.execute('SELECT id FROM templates WHERE id=?',(tid,)).fetchone(): continue
  data=dict(courseId=source['id'],tenantId=TENANT.id,name=source['id']+' — REVIEW REQUIRED',source=source['source']['fileName'],sourceHash=source['source']['sha256'],content=source['body'],fields=[],autofillFields=source['fields'],reviewedAt=source['version'],approved=False,blockers=source['blockers'],sourceTextHash=source['sourceTextHash'],mappingHash=source['authoritativeMappingHash'],mode='local_review')
  c.execute('INSERT INTO templates VALUES(?,?)',(tid,canonical(data)))
  audit(c,tid,'source_template_registered',{'sourceHash':data['sourceHash'],'mappingHash':data['mappingHash']})
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args): pass # URLs must not leak bearer tokens.
 def respond(self,status,data,ctype='application/json'):
  if 200<=status<300 and getattr(self,'db',None) is not None: self.db.commit()
  raw=(canonical(data) if ctype=='application/json' else data).encode(); self.send_response(status)
  for k,v in {'Content-Type':ctype,'Content-Length':str(len(raw)),'Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff','Content-Security-Policy':"frame-ancestors 'none'"}.items(): self.send_header(k,v)
  for key,value in getattr(self,'response_headers',{}).items(): self.send_header(key,value)
  self.end_headers(); self.wfile.write(raw)
 def do_GET(self): self.handle_request()
 def do_POST(self): self.handle_request()
 def handle_request(self):
  self.response_headers={};self.signing_work=None;self.db=None
  path=urlparse(self.path).path
  if path in ('/health/live','/health/ready'):
   if self.command!='GET':return self.respond(405,{'error':'GET required'})
   status,payload=health.live() if path=='/health/live' else health.ready(DB,LOCK,os.environ.get('VYNE_READ_ONLY_RECOVERY')=='1')
   return self.respond(status,payload)
  try:
   if path.startswith('/api/billing/') or path=='/api/auth/signup':
    return self.respond(*billing.handle_http(self,path,DB))
   with LOCK,connect() as c:
    if self.command=='POST': c.execute('BEGIN IMMEDIATE')
    self.db=c; self.route(c)
   self.db=None
   if self.signing_work:
    service,tenant,operation,authorize=self.signing_work
    status,payload=service.execute(DB,tenant,operation,authorize)
    self.respond(status,payload)
  except billing.Forbidden as e:self.respond(403,{'error':str(e),'membershipUrl':'/membership.html'})
  except billing.Conflict as e:self.respond(409,{'error':str(e)})
  except billing.Unavailable as e:self.respond(503,{'error':str(e)})
  except (ValueError,KeyError,TypeError) as e: self.respond(400,{'error':str(e)})
  except Exception: self.respond(500,{'error':'Internal error; no completion confirmed'})
 def route(self,c):
  path=urlparse(self.path).path; b={}
  if self.command=='POST':
   if os.environ.get('VYNE_READ_ONLY_RECOVERY')=='1':return self.respond(503,{'error':'Restored workspace is read-only until recovery reconciliation is approved'})
   if self.headers.get('Origin') and self.headers['Origin'] not in {os.environ.get('VYNE_ORIGIN','http://127.0.0.1:8765'),*os.environ.get('VYNE_ALLOWED_ORIGINS','').split(',')}: return self.respond(403,{'error':'Origin rejected'})
   size=int(self.headers.get('Content-Length','0'))
   if not 0<size<=2200000: fail('Invalid request size')
   b=json.loads(self.rfile.read(size))
   if not isinstance(b,dict): fail('JSON object required')
   def reject_cards(value):
    if isinstance(value,dict):
     for key,item in value.items():
      if re.sub('[^a-z]','',key.lower()) in ['cvv','cvc','pan','cardnumber','creditcardnumber','cardsecuritycode']: fail('Card data requires hosted processor collection')
      reject_cards(item)
    elif isinstance(value,list):
     for item in value: reject_cards(item)
   reject_cards(b)
  authorization=self.headers.get('Authorization','').strip()
  bearer=authorization.removeprefix('Bearer ').strip() if authorization.startswith('Bearer ') else ''
  browser_token=account_transport.cookie_token(self.headers) if not authorization else ''
  session_token=bearer or browser_token
  if browser_token and self.command=='POST' and (path.startswith('/api/admin/') or path in ('/api/auth/logout','/api/auth/password')):
   if not account_transport.valid_csrf(self.headers,browser_token): return self.respond(403,{'error':'Browser session verification required; sign in again'})
  if path=='/api/auth/session' and self.command=='GET':
   account=accounts.authenticate(c,session_token)
   if not account: return self.respond(401,{'error':'Sign in required'})
   return self.respond(200,{'actor':account,'csrfToken':account_transport.csrf(session_token)})
  if path.startswith('/api/auth/'):
   result=accounts.handle_public(c,self.command,path,b,session_token)
   if result is None: return self.respond(404,{'error':'Account route unavailable'})
   status,payload=result
   if 200<=status<300:
    if payload.get('accessToken') and self.headers.get('X-Vyne-Session')=='browser':
     payload=dict(payload);token=payload.pop('accessToken')
     self.response_headers['Set-Cookie']=account_transport.session_cookie(token,os.environ.get('VYNE_ORIGIN','http://127.0.0.1:8765'))
    elif path in ('/api/auth/logout','/api/auth/password'):
     self.response_headers['Set-Cookie']=account_transport.session_cookie('',os.environ.get('VYNE_ORIGIN','http://127.0.0.1:8765'),clear=True)
   c.commit() # Failed authentication throttles persist even if the client disconnects.
   return self.respond(status,payload)
  if path.startswith('/api/admin/'):
   legacy_enabled=os.environ.get('VYNE_ALLOW_LEGACY_KEYS','1')=='1'
   owners=json.loads(os.environ.get('VYNE_OWNERS','{}')) if legacy_enabled else {}
   fallback=os.environ.get('VYNE_ADMIN_TOKEN','') if legacy_enabled else ''
   if fallback: owners[fallback]='local-owner'
   TENANT.id=next((tenant for key,tenant in owners.items() if key and secrets.compare_digest(self.headers.get('Authorization',''),'Bearer '+key)),None)
   actor=accounts.authenticate(c,session_token) or (staff.authenticate(c,bearer) if legacy_enabled else None)
   if actor is None and TENANT.id:
    actor={'id':'legacy-owner:'+TENANT.id,'tenantId':TENANT.id,'role':'owner','name':'Legacy business key'}
   if actor is None: return self.respond(401,{'error':'Admin authentication required'})
   TENANT.id=actor['tenantId']
   route=path.removeprefix('/api/admin/')
   if not staff.allowed(actor,self.command,route,b): return self.respond(403,{'error':'Staff role does not permit this action'})
   billing.enforce(c,actor,self.command,route,b)
   if self.command=='POST': staff.record(c,actor,route,b)
   candidate_prepare=self.command=='POST' and route.startswith('candidate-signing/requests/') and route.endswith('/prepare') and len(route.split('/'))==4
   candidate_revoke=self.command=='POST' and route.startswith('contract-candidates/versions/') and route.endswith('/revoke') and len(route.split('/'))==4
   if candidate_revoke or candidate_prepare or (self.command=='POST' and b.get('action') in ('send','cancel') and (route=='journey/action' or (route=='trips/action' and b['action']=='cancel' and transactions.owner_trip(c,TENANT.id,b.get('tripId')).get('journeyVersion')))):
    if candidate_prepare and b:raise ValueError('Candidate prepare does not accept replacement fields')
    service=candidate_signing_service.ReviewRevocation if candidate_revoke else (candidate_signing_service if candidate_prepare else (signing_service if b['action']=='send' else cancellation_service))
    scheduled=service.schedule(c,actor,route.split('/')[2],b) if candidate_revoke else service.schedule(c,actor,route.split('/')[2] if candidate_prepare else b.get('tripId'))
    if 'ready' in scheduled:return self.respond(200,scheduled['ready'])
    def authorized(db):
     current=accounts.authenticate(db,session_token)
     if current is None and os.environ.get('VYNE_ALLOW_LEGACY_KEYS','1')=='1':
      current=staff.authenticate(db,bearer)
      if current is None and actor['id'].startswith('legacy-owner:'):
       configured=json.loads(os.environ.get('VYNE_OWNERS','{}'))
       fallback=os.environ.get('VYNE_ADMIN_TOKEN','')
       if fallback:configured[fallback]='local-owner'
       if configured.get(bearer)==actor['tenantId']:current=actor
     return bool(current and current['id']==actor['id'] and current['tenantId']==actor['tenantId'] and current['role']=='owner')
    self.signing_work=(service,actor['tenantId'],scheduled.get('operationId') or scheduled['id'],authorized)
    return # Commit intent, close connection and release LOCK before provider work.
   result=quote_offers.handle(c,actor,self.command,route,b)
   if result is not None:return self.respond(*result)
   result=rental_extensions.handle(c,actor,self.command,route,b)
   if result is not None:return self.respond(*result)
   result=booking_candidates.handle(c,actor,self.command,route,b)
   if result is not None:return self.respond(*result)
   result=candidate_signing_service.handle(c,actor,self.command,route,b)
   if result is not None:return self.respond(*result)
   result=payment_routes.handle(c,actor,self.command,route,b)
   if result is not None:return self.respond(*result)
   result=records.handle(c,actor,self.command,route,b)
   if result is not None: return self.respond(*result)
   result=accounts.handle_admin(c,actor,self.command,route,b)
   if result is not None: return self.respond(*result)
   result=standalone_documents.handle(c,TENANT.id,actor['id'],self.command,route,b)
   if result is not None: return self.respond(*result)
   result=candidate_routes.handle(c,TENANT.id,actor['id'],self.command,route,b)
   if result is not None: return self.respond(*result)
   result=document_review_routes.handle(c,TENANT.id,actor['id'],self.command,route,b)
   if result is not None: return self.respond(*result)
   result=maintenance.handle(c,actor,self.command,route,b)
   if result is not None: return self.respond(*result)
   result=staff.handle(c,actor,self.command,route,b)
   if result is not None: return self.respond(*result)
   result=journey.handle_admin(c,TENANT.id,self.command,route,b,create_booking)
   if result is not None: return self.respond(*result)
   for handler in [academy.handle,transactions.handle_admin]:
    result=handler(c,TENANT.id,self.command,route,b)
    if result is not None: return self.respond(*result)
   if self.command=='GET' and route=='schema': return self.respond(200,autofill({'action':'catalog'}))
   if route in ['vehicles','customers'] and self.command=='POST':
    required=['make','model','vin','plateNumber'] if route=='vehicles' else ['name','email','phone']
    record={k:text(b.get(k),2000) for k in required}
    extras=b.get('details',{})
    if not isinstance(extras,dict) or any(k in extras for k in ['tenantId','id','dailyRate']+required): fail('Invalid details')
    if route=='customers':
     supplied={k:v for k,v in extras.items() if k in records.CUSTOMER_DETAILS}
     if supplied: extras=dict(extras,**records.changes('customers',supplied))
    record.update(extras)
    if route=='vehicles':
     rate=b.get('dailyRate')
     if not isinstance(rate,(int,float)) or isinstance(rate,bool) or not 0<=rate<=100000: fail('Invalid rate')
     record['dailyRateCents']=cents(rate)
     record['dailyRate']=rate
    record.update(id=secrets.token_hex(12),tenantId=TENANT.id)
    c.execute('INSERT INTO '+route+' VALUES(?,?)',(record['id'],canonical(record)));audit(c,record['id'],'record_created',{'hash':digest(canonical(record))});return self.respond(201,record)
   if route=='profile':
    if self.command=='POST':
     profile={k:text(b.get(k),2000) for k in ['legalName','email','phone','address']}; profile.update({k:v for k,v in b.items() if k not in ['tenantId','updatedAt','legalName','email','phone','address','details','rentalDetails','partner','agreement']}); profile['tenantId']=TENANT.id; profile['updatedAt']=now()
     c.execute('INSERT OR REPLACE INTO profiles VALUES(?,?)',(TENANT.id,canonical(profile))); audit(c,TENANT.id,'profile_updated',{'hash':digest(canonical(profile))}); return self.respond(200,profile)
    r=c.execute('SELECT data FROM profiles WHERE id=?',(TENANT.id,)).fetchone(); return self.respond(200,json.loads(r[0]) if r else {})
   if self.command=='POST' and route=='bookings': return self.respond(201,create_booking(c,b))
   if self.command=='GET' and route=='overview':
    seed_sources(c)
    result={}
    for table in ['bookings','templates','agreements','vehicles','customers']:
     result[table]=[]
     for r in c.execute('SELECT * FROM '+table):
      item=json.loads(r['data'])
      if item['tenantId']==TENANT.id:
       if table=='templates': item['id']=r['id']
       if table=='agreements': item.update(state=r['state'],expires=r['expires'])
       result[table].append(item)
    ids={TENANT.id}|{x['id'] for group in result.values() for x in group}
    result['audit']=[dict(r) for r in c.execute('SELECT * FROM audit') if r['agreement'] in ids]
    return self.respond(200,result)
   if self.command=='POST' and route=='templates': return self.respond(201,register_template(c,b))
   if self.command=='POST' and route=='document':
    row=c.execute('SELECT * FROM agreements WHERE id=?',(b.get('agreementId'),)).fetchone()
    if not row or row['state']!='completed' or json.loads(row['data'])['tenantId']!=TENANT.id: fail('Completed record unavailable')
    data=json.loads(row['data']); original=dict(data);stored=original.pop('recordHash',None)
    if digest(canonical(original))!=stored: fail('Completed record integrity failure')
    return self.respond(200,data)
   if self.command=='POST' and route=='refresh':
    old=c.execute('SELECT * FROM agreements WHERE id=?',(b.get('agreementId'),)).fetchone()
    if not old or old['state']!='draft' or json.loads(old['data'])['tenantId']!=TENANT.id: fail('Only your unsigned drafts can be refreshed')
    if json.loads(old['data']).get('provider'): fail('Manage this provider document in the connected rental workspace')
    previous=json.loads(old['data']); new=draft(c,dict(bookingId=previous['bookingId'],templateId=previous['templateId']))
    c.execute("UPDATE agreements SET state='revoked',token=NULL WHERE id=?",(old['id'],)); audit(c,new['id'],'draft_refreshed',{'previousAgreement':old['id'],'previousContentHash':previous['contentHash']}); return self.respond(201,new)
   if self.command=='POST' and route=='agreements': return self.respond(201,draft(c,b))
   if self.command=='POST' and route in ['links','revoke']:
    row=c.execute('SELECT * FROM agreements WHERE id=?',(b.get('agreementId'),)).fetchone()
    if not row or json.loads(row['data'])['tenantId']!=TENANT.id or row['state'] in ['completed','revoked']: fail('Agreement unavailable')
    if json.loads(row['data']).get('provider'): fail('Manage this provider document in the connected rental workspace')
    if route=='revoke':
     c.execute("UPDATE agreements SET token=NULL,state='revoked' WHERE id=?",(row['id'],)); audit(c,row['id'],'revoked',{}); return self.respond(200,{'state':'revoked'})
    autofill({'action':'ready','snapshot':json.loads(row['data'])['snapshot']})
    token=secrets.token_urlsafe(32); expires=(datetime.now(timezone.utc)+timedelta(hours=24)).isoformat()
    c.execute("UPDATE agreements SET token=?,expires=?,state='awaiting_signature' WHERE id=?",(digest(token),expires,row['id'])); audit(c,row['id'],'link_issued',{'expires':expires}); return self.respond(201,{'url':'/sign.html#'+token,'expires':expires,'delivery':'manual_local_review_only'})
  if path in ('/api/journey/extensions','/api/journey/extensions/consent'):
   trip=journey.renter_trip(c,bearer);tenant=trip['tenantId']
   if self.command=='GET' and path=='/api/journey/extensions':return self.respond(200,rental_extensions.get_public(c,tenant,trip['id']))
   if self.command!='POST' or path!='/api/journey/extensions/consent':return self.respond(405,{'error':'Method not supported'})
   if set(b)!={'proposalId','proposalHash','quoteHash','attestation'}:raise ValueError('Exact offer, quote and explicit consent text required')
   attestation=text(b['attestation'],10000)
   offer=rental_extensions.get(c,tenant,b['proposalId'])
   if offer['tripId']!=trip['id']:raise ValueError('Extension offer unavailable for this trip')
   payload={'kind':'extension_consent','tripId':trip['id'],'proposalId':b['proposalId'],'proposalHash':b['proposalHash'],'quoteHash':b['quoteHash'],'attestation':attestation}
   raw=canonical(payload).encode()
   prior=next((e for e in offer['events'] if e['kind']=='renter_consented'),None)
   if prior:
    artifact=document_artifacts.get(c,tenant,prior['evidenceId'])
    if artifact['body']!=raw:raise ValueError('Existing consent differs; owner review is required')
   else:artifact=document_artifacts.store(c,tenant,'renter-trip:'+trip['id'],raw,'text/plain','extension-consent.txt')
   rental_extensions.record_consent(c,tenant,trip['id'],offer['originalSnapshot']['email'],offer['id'],b['proposalHash'],b['quoteHash'],artifact['id'])
   return self.respond(200,rental_extensions.get_public(c,tenant,trip['id']))
  if path in ('/api/journey/quote-offers','/api/journey/quote-offers/accept'):
   trip=journey.renter_trip(c,bearer)
   if path.endswith('/accept') and self.command=='POST':quote_offers.accept(c,trip,b)
   elif path.endswith('/accept') or self.command!='GET':return self.respond(405,{'error':'Method not allowed'})
   return self.respond(200,quote_offers.public(c,trip))
  result=journey.handle_public(c,self.command,path,b,self.headers.get('Authorization','').removeprefix('Bearer '),create_booking,TENANT)
  if result is not None: return self.respond(*result)
  if path=='/api/trip' or path.startswith('/api/trip/'):
   result=transactions.handle_trip(c,self.command,path,b,self.headers.get('Authorization','').removeprefix('Bearer '))
   if result is not None: return self.respond(*result)
  if path=='/api/bookings' and self.command=='POST': return self.respond(503,{'error':'Public booking is disabled. An authenticated business owner must create the request.'})
  if path in ['/api/sign','/api/sign/complete','/api/sign/document']:
   token=self.headers.get('Authorization','').removeprefix('Bearer ')
   row=c.execute('SELECT * FROM agreements WHERE token=?',(digest(token),)).fetchone()
   if not row or not row['expires'] or row['expires']<now() or row['state']=='revoked': return self.respond(404,{'error':'Link unavailable or expired'})
   data=json.loads(row['data'])
   if digest(data['content'])!=data['contentHash']: fail('Document integrity failure')
   if row['state']=='completed':
    original=dict(data); stored=original.pop('recordHash',None)
    if digest(canonical(original))!=stored: fail('Completed record integrity failure')
   autofill({'action':'verify','snapshot':data['snapshot']})
   if path=='/api/sign/complete' and self.command=='POST':
    if row['state']!='awaiting_signature': return self.respond(409,{'error':'Already completed'})
    if b.get('contentHash')!=data['contentHash'] or b.get('consent') is not True: fail('Document hash and explicit consent required')
    answers=b.get('answers',{}); required=data['template']['fields']
    if set(answers)!={f['id'] for f in required}: fail('All required fields must be completed')
    for f in required: text(answers[f['id']],200)
    data['completion']=dict(answers=answers,consent=True,consentText='I consent to use an electronic record and intend the entered signature and initials to sign this document.',completedAt=now(),userAgent=self.headers.get('User-Agent','')[:500],remoteAddress=self.client_address[0])
    data['snapshot']=autofill({'action':'seal','snapshot':data['snapshot']})
    data['recordHash']=digest(canonical(data)); c.execute("UPDATE agreements SET state='completed',data=? WHERE id=?",(canonical(data),row['id'])); audit(c,row['id'],'completed',{'recordHash':data['recordHash'],'contentHash':data['contentHash']}); return self.respond(200,{'state':'completed','recordHash':data['recordHash']})
   if self.command!='GET': return self.respond(405,{'error':'Method not allowed'})
   if path=='/api/sign/document':
    if row['state']!='completed': fail('Document not completed')
    body='<html><meta charset="utf-8"><title>VYNE completed review record</title><h1>VYNE — local review record</h1><pre style="white-space:pre-wrap">'+html.escape(data['content'])+'</pre><h2>Signing evidence</h2><pre style="white-space:pre-wrap">'+html.escape(json.dumps({k:data[k] for k in ['completion','contentHash','recordHash','templateId']},indent=2))+'</pre></html>'
    return self.respond(200,body,'text/html; charset=utf-8')
   return self.respond(200,dict(id=data['id'],content=data['content'],contentHash=data['contentHash'],fields=data['template']['fields'],state=row['state'],mode='local_review'))
  if path.startswith('/api/'): return self.respond(404,{'error':'Not found'})
  if os.environ.get('VYNE_BILLING_CONFIG') and path in ('/course.html','/lesson-1-2.mp4','/lesson-1-2-poster.jpg'):
   actor=accounts.authenticate(c,session_token)
   if not actor or not billing.access(c,actor)['training']:
    if path=='/course.html':
     self.response_headers['Location']='/membership.html?training=1'
     return self.respond(303,'','text/plain')
    return self.respond(403,{'error':'Training access required'})
  if path in ('/assets/entry-concept-v1.png','/assets/training-cover-v1.png') and self.command=='GET':
   image=(ROOT/path.lstrip('/')).read_bytes()
   self.send_response(200)
   for key,value in {'Content-Type':'image/png','Content-Length':str(len(image)),'Cache-Control':'public, max-age=86400','X-Content-Type-Options':'nosniff'}.items(): self.send_header(key,value)
   self.end_headers();self.wfile.write(image);return
  if path in ('/lesson-1-1.mp4','/lesson-1-1-poster.jpg','/lesson-1-2.mp4','/lesson-1-2-poster.jpg'):
   if self.command!='GET': return self.respond(405,{'error':'Method not allowed'})
   media=ROOT/'lesson-media'/path.lstrip('/')
   if not media.is_file(): return self.respond(404,{'error':'Media not available'})
   total=media.stat().st_size; start=0; end=total-1; status=200
   requested=self.headers.get('Range')
   if requested:
    match=re.fullmatch(r'bytes=(\d*)-(\d*)',requested)
    if not match or not any(match.groups()):
     self.send_response(416); self.send_header('Content-Range',f'bytes */{total}'); self.send_header('Content-Length','0'); self.end_headers(); return
    a,b=match.groups()
    if a: start=int(a); end=min(int(b),total-1) if b else total-1
    else: start=max(0,total-int(b))
    if start>end or start>=total:
     self.send_response(416); self.send_header('Content-Range',f'bytes */{total}'); self.send_header('Content-Length','0'); self.end_headers(); return
    status=206
   self.send_response(status)
   self.send_header('Content-Type','video/mp4' if path.endswith('.mp4') else 'image/jpeg')
   self.send_header('Content-Length',str(end-start+1)); self.send_header('Accept-Ranges','bytes')
   self.send_header('Cache-Control','private, no-store' if path.startswith('/lesson-1-2') else 'public, max-age=3600'); self.send_header('X-Content-Type-Options','nosniff')
   if status==206: self.send_header('Content-Range',f'bytes {start}-{end}/{total}')
   self.end_headers()
   with media.open('rb') as stream:
    stream.seek(start); remaining=end-start+1
    while remaining:
     block=stream.read(min(65536,remaining))
     if not block: break
     self.wfile.write(block); remaining-=len(block)
   return
  files={'/':'index.html','/index.html':'index.html','/vyne-booking.html':'vyne-booking.html','/vyne-fleet.html':'vyne-fleet.html','/vyne-admin.html':'admin.html','/admin.html':'admin.html','/sign.html':'sign.html','/workflow.css':'workflow.css','/workflow.js':'workflow.js'}
  files.update({'/entry.css':'entry.css','/entry.js':'entry.js','/training.css':'training.css'})
  files.update({'/'+name:name for name in ['membership.html','membership.css','membership.js']})
  files.update({'/'+name:name for name in ['course.html','lesson-sample.html','open-road.css','payments.html','payments.js','candidates.html','candidates.js','records.html','records.js','account.html','account.js','account-client.js','standalone.html','standalone.js','maintenance.html','maintenance.js','documents.html','documents.js','staff.html','staff.js','rentals.html','rental.html','reserve.html','journey.css','journey.js','academy.html','academy.js','academy.css','trip.html','trip.js','trip.css','operations.html','operations.js','operations.css']})
  if self.command!='GET' or path not in files: return self.respond(404,{'error':'Not found'})
  file=ROOT/files[path]; ct='text/css' if file.suffix=='.css' else 'text/javascript' if file.suffix=='.js' else 'text/html; charset=utf-8'
  content=file.read_text()
  if path=='/course.html' and os.environ.get('VYNE_BILLING_CONFIG') and not billing.access(c,actor)['grandfathered']:
   # New paying students never inherit another student's browser answers.
   # Existing workspaces retain the original key and all saved worksheets.
   content=content.replace("storeKey='rycf-course-draft-v1'","storeKey='rycf-course-draft-v1-"+digest(actor['userId'])[:24]+"'",1)
  self.respond(200,content,ct)
if __name__=='__main__':
 init(); port=int(os.environ.get('VYNE_PORT','8765')); print(f'VYNE local review: http://127.0.0.1:{port}',flush=True); ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
