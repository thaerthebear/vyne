"""Invite-only individual accounts; caller owns transactions and HTTPS/origin policy.

No email is sent. Sessions and invitations are opaque secrets stored only as hashes.
Admin actor must be supplied by authenticated server state, never request JSON.
"""
import hashlib
import json
import re
import secrets
from datetime import datetime, timedelta, timezone

ROLES = ('owner', 'operator', 'viewer')
SESSION_HOURS = 12
INVITE_MINUTES = 60
SCRYPT_N, SCRYPT_R, SCRYPT_P = 32768, 8, 3
DUMMY_SALT = bytes.fromhex('09a19e5ad71f445b8df243ccabb85912')


def now():
    return datetime.now(timezone.utc)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def init(c):
    c.executescript('''
CREATE TABLE IF NOT EXISTS account_users(
 id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
 password_salt TEXT NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS account_memberships(
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL, tenant_id TEXT NOT NULL,
 role TEXT NOT NULL, revoked_at TEXT, UNIQUE(user_id,tenant_id));
CREATE TABLE IF NOT EXISTS account_invitations(
 id TEXT PRIMARY KEY, token_hash TEXT UNIQUE NOT NULL, tenant_id TEXT NOT NULL,
 email TEXT NOT NULL, role TEXT NOT NULL, expires_at TEXT NOT NULL,
 issued_by TEXT NOT NULL, created_at TEXT NOT NULL, used_at TEXT, revoked_at TEXT);
CREATE TABLE IF NOT EXISTS account_sessions(
 token_hash TEXT PRIMARY KEY, membership_id TEXT NOT NULL, expires_at TEXT NOT NULL,
 created_at TEXT NOT NULL, revoked_at TEXT);
CREATE TABLE IF NOT EXISTS account_attempts(
 bucket TEXT PRIMARY KEY, attempts INTEGER NOT NULL, window_start TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS account_events(
 seq INTEGER PRIMARY KEY, tenant_id TEXT NOT NULL, actor_id TEXT NOT NULL,
 event TEXT NOT NULL, subject_id TEXT NOT NULL, at TEXT NOT NULL);
''')


def fields(body, required, optional=()):
    if not isinstance(body, dict) or set(body)-set(required)-set(optional) or not set(required)<=set(body):
        raise ValueError('Invalid account request fields')


def text(value, limit=200):
    if not isinstance(value,str) or not value.strip() or len(value)>limit:
        raise ValueError('Missing or invalid account detail')
    return value.strip()


def email(value):
    value=text(value,254).lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value):
        raise ValueError('Valid email required')
    return value


def password(value):
    if not isinstance(value,str) or not 12<=len(value)<=256:
        raise ValueError('Password must contain 12 to 256 characters')
    return value


def derive(value,salt):
    return hashlib.scrypt(value.encode(),salt=salt,n=SCRYPT_N,r=SCRYPT_R,p=SCRYPT_P,
                          maxmem=64*1024*1024,dklen=32).hex()


def check_password(row,value):
    # Unknown users pay the same fixed KDF cost; no cleartext credential logging.
    salt=bytes.fromhex(row['password_salt']) if row else DUMMY_SALT
    result=derive(value,salt)
    return row is not None and secrets.compare_digest(result,row['password_hash'])


def event(c,tenant,actor,kind,subject):
    c.execute('INSERT INTO account_events(tenant_id,actor_id,event,subject_id,at) VALUES(?,?,?,?,?)',
              (tenant,actor,kind,subject,now().isoformat()))


def throttle(c,key,limit=5,seconds=900):
    """Count each credential attempt before verification. Caller MUST commit failures."""
    at=now();cutoff=(at-timedelta(seconds=seconds)).isoformat()
    row=c.execute('SELECT attempts,window_start FROM account_attempts WHERE bucket=?',(key,)).fetchone()
    if row and row['window_start']>cutoff:
        if row['attempts']>=limit:return False
        c.execute('UPDATE account_attempts SET attempts=attempts+1 WHERE bucket=?',(key,))
    else:
        c.execute('INSERT OR REPLACE INTO account_attempts VALUES(?,?,?)',(key,1,at.isoformat()))
    # Bound historical rows without relying on a background process.
    c.execute('DELETE FROM account_attempts WHERE window_start<?',((at-timedelta(days=1)).isoformat(),))
    return True


def limited(c,key):
    # Global burst cap supplements per-identity protection. Upstream per-IP limits
    # remain necessary before exposure; this does not trust proxy headers.
    return not (throttle(c,'global-auth',100,60) and throttle(c,key))


def actor_for(row):
    return {'id':row['membership_id'],'userId':row['user_id'],'tenantId':row['tenant_id'],
            'role':row['role'],'name':row['name'],'email':row['email'],'authKind':'individual_account'}


def authenticate(c,token):
    if not isinstance(token,str) or not token or len(token)>200:return None
    row=c.execute('''SELECT m.id membership_id,m.user_id,m.tenant_id,m.role,u.name,u.email
      FROM account_sessions s JOIN account_memberships m ON m.id=s.membership_id
      JOIN account_users u ON u.id=m.user_id
      WHERE s.token_hash=? AND s.revoked_at IS NULL AND s.expires_at>?
      AND m.revoked_at IS NULL''',(digest(token),now().isoformat())).fetchone()
    return actor_for(row) if row else None


def new_session(c,membership_id):
    token=secrets.token_urlsafe(32);at=now();expires=(at+timedelta(hours=SESSION_HOURS)).isoformat()
    c.execute('INSERT INTO account_sessions VALUES(?,?,?,?,NULL)',(digest(token),membership_id,expires,at.isoformat()))
    return {'accessToken':token,'expiresAt':expires,'actor':authenticate(c,token)}


def failure(status=401):
    return status,{'error':'Unable to authenticate. Check your credentials or try again later.'}


def handle_public(c,method,path,body,token=''):
    if not path.startswith('/api/auth/'):return None
    if method!='POST':return 405,{'error':'Method not allowed'}
    if path=='/api/auth/login':
        fields(body,('email','password'),('businessId',))
        address=email(body['email']);secret=password(body['password']);key='login:'+digest(address)
        if limited(c,key):return failure(429)
        row=c.execute('SELECT * FROM account_users WHERE email=?',(address,)).fetchone()
        if not check_password(row,secret):return failure()
        memberships=c.execute('SELECT id,tenant_id,role FROM account_memberships WHERE user_id=? AND revoked_at IS NULL',(row['id'],)).fetchall()
        if not memberships:return failure()
        business=body.get('businessId')
        if business is not None:business=text(business)
        if business is None and len(memberships)>1:
            return 409,{'error':'Choose your business to finish signing in.',
                        'businesses':[{'businessId':m['tenant_id'],'role':m['role']} for m in memberships]}
        chosen=next((m for m in memberships if business is None or m['tenant_id']==business),None)
        if chosen is None:return failure()
        c.execute('DELETE FROM account_attempts WHERE bucket=?',(key,))
        result=new_session(c,chosen['id']);event(c,chosen['tenant_id'],chosen['id'],'login',chosen['id'])
        return 200,result
    if path=='/api/auth/accept':
        fields(body,('invitationToken','email','name','password'))
        invite_token=text(body['invitationToken'],200);address=email(body['email'])
        name=text(body['name']);secret=password(body['password']);key='accept:'+digest(address)
        if limited(c,key):return failure(429)
        invitation=c.execute('SELECT * FROM account_invitations WHERE token_hash=? AND used_at IS NULL AND revoked_at IS NULL AND expires_at>?',
                             (digest(invite_token),now().isoformat())).fetchone()
        if invitation is None or invitation['email']!=address:return failure()
        import billing
        billing.accept_invitation(c,invitation)
        user=c.execute('SELECT * FROM account_users WHERE email=?',(address,)).fetchone()
        if user is not None and not check_password(user,secret):return failure()
        if user is None:
            uid=secrets.token_hex(16);salt=secrets.token_bytes(16)
            c.execute('INSERT INTO account_users VALUES(?,?,?,?,?,?)',
                      (uid,address,name,salt.hex(),derive(secret,salt),now().isoformat()))
        else:uid=user['id']
        membership=c.execute('SELECT * FROM account_memberships WHERE user_id=? AND tenant_id=?',(uid,invitation['tenant_id'])).fetchone()
        if membership and membership['revoked_at'] is None:
            # An invitation never silently changes an existing member's role.
            return 409,{'error':'This account already has access. Sign in with its existing password.'}
        if membership:
            mid=membership['id']
            c.execute('UPDATE account_memberships SET role=?,revoked_at=NULL WHERE id=?',(invitation['role'],mid))
        else:
            mid=secrets.token_hex(16)
            c.execute('INSERT INTO account_memberships VALUES(?,?,?,?,NULL)',(mid,uid,invitation['tenant_id'],invitation['role']))
        c.execute('UPDATE account_invitations SET used_at=? WHERE id=?',(now().isoformat(),invitation['id']))
        c.execute('DELETE FROM account_attempts WHERE bucket=?',(key,))
        event(c,invitation['tenant_id'],mid,'invitation_accepted',invitation['id'])
        return 201,new_session(c,mid)
    if path=='/api/auth/logout':
        fields(body,())
        actor=authenticate(c,token)
        c.execute('UPDATE account_sessions SET revoked_at=? WHERE token_hash=?',(now().isoformat(),digest(token)))
        if actor:event(c,actor['tenantId'],actor['id'],'logout',actor['id'])
        return 200,{'signedOut':True}
    if path=='/api/auth/password':
        fields(body,('currentPassword','newPassword'))
        actor=authenticate(c,token)
        if not actor:return failure()
        current=password(body['currentPassword']);replacement=password(body['newPassword'])
        key='password:'+actor['userId']
        if limited(c,key):return failure(429)
        user=c.execute('SELECT * FROM account_users WHERE id=?',(actor['userId'],)).fetchone()
        if not check_password(user,current):return failure()
        salt=secrets.token_bytes(16)
        c.execute('UPDATE account_users SET password_salt=?,password_hash=? WHERE id=?',
                  (salt.hex(),derive(replacement,salt),actor['userId']))
        c.execute('UPDATE account_sessions SET revoked_at=? WHERE membership_id IN (SELECT id FROM account_memberships WHERE user_id=?)',
                  (now().isoformat(),actor['userId']))
        c.execute('DELETE FROM account_attempts WHERE bucket=?',(key,))
        event(c,actor['tenantId'],actor['id'],'password_changed',actor['id'])
        return 200,{'passwordChanged':True,'signedOut':True}
    return 404,{'error':'Account route unavailable'}


def handle_admin(c,actor,method,route,body):
    route=route.removeprefix('/api/admin/')
    if route!='accounts' and not route.startswith('accounts/'):return None
    if not actor or actor.get('role')!='owner':return 403,{'error':'Owner role required'}
    tenant=text(actor.get('tenantId'));aid=text(actor.get('id'))
    if route=='accounts' and method=='GET':
        members=[dict(r) for r in c.execute('''SELECT m.id,u.name,u.email,m.role,m.revoked_at revokedAt
          FROM account_memberships m JOIN account_users u ON u.id=m.user_id WHERE m.tenant_id=?''',(tenant,))]
        invitations=[dict(r) for r in c.execute('''SELECT id,email,role,expires_at expiresAt,used_at usedAt,revoked_at revokedAt
          FROM account_invitations WHERE tenant_id=? ORDER BY created_at DESC''',(tenant,))]
        return 200,{'members':members,'invitations':invitations}
    if route=='accounts/invite' and method=='POST':
        fields(body,('email','role'))
        address=email(body['email']);role=body['role']
        if role not in ROLES:raise ValueError('Unsupported account role')
        at=now();token=secrets.token_urlsafe(32);iid=secrets.token_hex(16)
        expires=(at+timedelta(minutes=INVITE_MINUTES)).isoformat()
        c.execute('UPDATE account_invitations SET revoked_at=? WHERE tenant_id=? AND email=? AND used_at IS NULL AND revoked_at IS NULL',
                  (at.isoformat(),tenant,address))
        c.execute('INSERT INTO account_invitations VALUES(?,?,?,?,?,?,?,?,NULL,NULL)',
                  (iid,digest(token),tenant,address,role,expires,aid,at.isoformat()))
        event(c,tenant,aid,'invitation_issued',iid)
        return 201,{'id':iid,'invitationToken':token,'expiresAt':expires,'email':address,'role':role,
                    'delivery':'manual_private_handoff','url':'/account.html#invite='+token}
    if route=='accounts/revoke-invite' and method=='POST':
        fields(body,('id',));iid=text(body['id'])
        found=c.execute('SELECT id FROM account_invitations WHERE id=? AND tenant_id=?',(iid,tenant)).fetchone()
        if not found:return 404,{'error':'Invitation unavailable'}
        c.execute('UPDATE account_invitations SET revoked_at=COALESCE(revoked_at,?) WHERE id=?',(now().isoformat(),iid))
        event(c,tenant,aid,'invitation_revoked',iid)
        return 200,{'revoked':True}
    if route=='accounts/revoke' and method=='POST':
        fields(body,('id',));mid=text(body['id'])
        member=c.execute('SELECT * FROM account_memberships WHERE id=? AND tenant_id=?',(mid,tenant)).fetchone()
        if not member:return 404,{'error':'Account membership unavailable'}
        if mid==aid:return 409,{'error':'Cannot revoke your own current membership'}
        if member['role']=='owner' and member['revoked_at'] is None:
            count=c.execute("SELECT count(*) FROM account_memberships WHERE tenant_id=? AND role='owner' AND revoked_at IS NULL",(tenant,)).fetchone()[0]
            if count<=1:return 409,{'error':'Cannot remove the last enrolled owner'}
        c.execute('UPDATE account_memberships SET revoked_at=COALESCE(revoked_at,?) WHERE id=?',(now().isoformat(),mid))
        c.execute('UPDATE account_sessions SET revoked_at=COALESCE(revoked_at,?) WHERE membership_id=?',(now().isoformat(),mid))
        event(c,tenant,aid,'membership_revoked',mid)
        return 200,{'revoked':True}
    return 404,{'error':'Account route unavailable'}
