"""Validate private host layout; launch read-only unless rehearsal writes explicit."""
import argparse,json,os,shutil,sys
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1]

def checked_layout(state):
 state=Path(state).resolve()
 for folder in [state,state/'config',state/'app',state/'provider']:
  if not folder.is_dir() or folder.stat().st_mode&0o077:raise ValueError('Private state directories require mode0700')
 paths=[state/'app/database.sqlite3',state/'config/provider.json',state/'config/app.json',state/'config/docuseal.env',state/'app/demo-submissions.json']
 for path in paths:
  if path.is_symlink() or not path.is_file() or path.stat().st_mode&0o077:raise ValueError('Required private state file missing or not mode0600')
 provider=json.loads(paths[1].read_text());app=json.loads(paths[2].read_text())
 if provider.get('api_origin')!='http://127.0.0.1:3090' or provider.get('app_config')!=str(paths[2]):raise ValueError('Provider paths must match the reviewed host layout')
 if not provider.get('api_key') or provider['api_key']=='REPLACE_PRIVATELY':raise ValueError('Private provider configuration is incomplete')
 if not isinstance(provider.get('template_id'),int) or provider['template_id']<=0:raise ValueError('Migrated demo signing template required')
 submissions=json.loads(paths[4].read_text())
 if not isinstance(submissions,list) or any(not isinstance(row,dict) or not all(k in row for k in ('id','slug')) for row in submissions):raise ValueError('Migrated demo submission index required')
 for asset in ['index.html','demo.js']:
  if not (ROOT/'investor-demo'/asset).is_file():raise ValueError('Investor demo assets are missing')
 for asset in ['lesson-1-1.mp4','lesson-1-1-poster.jpg','lesson-1-2.mp4','lesson-1-2-poster.jpg']:
  if not (ROOT/'lesson-media'/asset).is_file():raise ValueError('Required course video/poster is missing')
 for field in ['portal_url','docuseal_url']:
  parsed=urlparse(app.get(field,''))
  if parsed.scheme!='https' or not parsed.hostname or parsed.hostname.endswith('.example') or parsed.path not in ('','/') or parsed.username or parsed.password or parsed.query or parsed.fragment:raise ValueError('Verified HTTPS origins required')
 if os.environ.get('VYNE_ORIGIN')!=app['portal_url']:raise ValueError('Application origin must exactly match portal URL')
 docker=Path(os.environ.get('VYNE_DOCKER_BIN','/usr/bin/docker'))
 if not docker.is_absolute() or not docker.is_file() or not os.access(docker,os.X_OK):raise ValueError('Absolute executable Docker path required')
 font=Path(os.environ.get('VYNE_REVIEW_PDF_FONT','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
 if not font.is_file():raise ValueError('Configured review font is unavailable')
 for executable in ['node','pdfinfo','pdftotext','pdftoppm']:
  if not shutil.which(executable):raise ValueError('Required Node/Poppler executable is unavailable')
 if not (ROOT/'investor-demo/.venv/bin/python').is_file():raise ValueError('Release PDF virtualenv is missing')
 if os.environ.get('VYNE_BILLING_CONFIG'):
  if Path(os.environ['VYNE_BILLING_CONFIG'])!=state/'config/billing.json':raise ValueError('Billing configuration must use the private state directory')
  sys.path.insert(0,str(ROOT/'backend'));import billing
  try:billing.config()
  except billing.Unavailable:raise ValueError('Private billing configuration failed validation') from None
 return state

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--state',required=True);parser.add_argument('--check',action='store_true');parser.add_argument('--enable-rehearsal-writes',action='store_true');args=parser.parse_args()
 try:state=checked_layout(args.state)
 except (ValueError,OSError,KeyError):raise SystemExit('Deployment preflight failed: check private layout, dependencies, origins and configuration; no service started.')
 if args.check:
  print('Private layout preflight passed; provider health, Linux runtime, TLS, accounts and pilot readiness are not certified.');return
 os.environ.update(VYNE_DB=str(state/'app/database.sqlite3'),VYNE_DOCUSEAL_CONFIG=str(state/'config/provider.json'),VYNE_DOCUSEAL_CONTAINER='vyne-docuseal-pilot',VYNE_ALLOW_LEGACY_KEYS='0',VYNE_DEMO_TRANSACTIONS='1',VYNE_READ_ONLY_RECOVERY='0' if args.enable_rehearsal_writes else '1')
 os.environ.pop('VYNE_ADMIN_TOKEN',None);os.environ.pop('VYNE_OWNERS',None)
 sys.path.insert(0,str(ROOT/'backend'));import server
 from investor_demo import handler_class
 config=json.loads((state/'config/app.json').read_text());provider=json.loads((state/'config/provider.json').read_text())
 handler=handler_class(server.Handler,config=config,provider=provider,state=state/'app',assets=ROOT/'investor-demo',read_only=not args.enable_rehearsal_writes)
 server.init()
 print('VYNE hosted rehearsal on loopback8765; live rental readiness is false.',flush=True)
 server.ThreadingHTTPServer(('127.0.0.1',8765),handler).serve_forever()
if __name__=='__main__':main()
