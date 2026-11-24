"""Create a private allowlisted source release, excluding runtime/customer secrets."""
import argparse,hashlib,json,os,shutil
from pathlib import Path

# Only reviewed deployment source/templates belong in a release. In particular,
# a locally filled runtime.env, app.json or provider.json must never be copied.
SOURCE_PATTERNS = [
 '*.html', '*.js', '*.css', 'backend/*.py', 'backend/*.mjs', 'backend/*.rb',
 'template-autofill/*.mjs', 'template-autofill/*.json', 'template-autofill/*.d.ts',
 'course-materials/originals/*.pdf', 'course-materials/extracted/*.txt',
 'course-materials/field-mapping.json', 'course-materials/source-manifest.json',
 'deployment/*.py', 'deployment/*.md', 'deployment/*.example',
 'deployment/compose.yml', 'deployment/requirements.txt', 'deployment/Dockerfile.smoke',
 'deployment/tests/*.py', 'deployment/evidence/*.json',
 'investor-demo/index.html', 'investor-demo/demo.js',
 'assets/entry-concept-v1.png',
 # Public course media only; never include arbitrary uploads or private state.
 'lesson-media/lesson-1-1.mp4', 'lesson-media/lesson-1-1-poster.jpg',
 'lesson-media/lesson-1-2.mp4', 'lesson-media/lesson-1-2-poster.jpg',
]

def source_files(root):
 root=Path(root).resolve();files=[]
 for pattern in SOURCE_PATTERNS:
  for path in root.glob(pattern):
   if path.is_symlink():raise ValueError('Release source symlinks are not permitted')
   if path.is_file():files.append(path)
 return sorted(set(files))

def build(root,destination):
 root=Path(root).resolve();destination=Path(destination).absolute()
 if destination.exists():raise FileExistsError('Release destination already exists')
 if not destination.parent.is_dir():raise ValueError('Release destination parent required')
 if destination.is_relative_to(root):raise ValueError('Release destination must be outside source tree')
 files=source_files(root);destination.mkdir(mode=0o700)
 try:
  inventory=[]
  for source in files:
   relative=source.relative_to(root);body=source.read_bytes();target=destination/relative
   target.parent.mkdir(mode=0o700,parents=True,exist_ok=True);target.write_bytes(body);target.chmod(0o600)
   inventory.append({'path':relative.as_posix(),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()})
  manifest={'format':'vyne-source-release-v1','scope':'hosted_rehearsal_candidate','livePilotReady':False,'runtimeAndPrivateStateIncluded':False,'files':inventory}
  output=destination/'release-manifest.json';output.write_text(json.dumps(manifest,indent=2)+'\n');output.chmod(0o600)
  verify(destination);return manifest
 except Exception:shutil.rmtree(destination);raise

def verify(destination):
 root=Path(destination);manifest=json.loads((root/'release-manifest.json').read_text());seen=set()
 if manifest.get('format')!='vyne-source-release-v1':raise ValueError('Unsupported release')
 for item in manifest['files']:
  name=item['path'];relative=Path(name)
  if relative.is_absolute() or '..' in relative.parts or name in seen:raise ValueError('Unsafe release inventory')
  seen.add(name);path=root/relative
  if any(p.is_symlink() for p in [path,*path.parents]):raise ValueError('Release symlink detected')
  body=path.read_bytes()
  if len(body)!=item['bytes'] or hashlib.sha256(body).hexdigest()!=item['sha256']:raise ValueError('Release source integrity failure')
 actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
 if actual!=seen|{'release-manifest.json'}:raise ValueError('Unmanifested release files')
 return manifest

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['build','verify']);p.add_argument('destination');p.add_argument('--source',default=str(Path(__file__).resolve().parents[1]));a=p.parse_args()
 result=build(a.source,a.destination) if a.action=='build' else verify(a.destination)
 print(json.dumps({'scope':result['scope'],'files':len(result['files']),'verified':True,'livePilotReady':False}))
if __name__=='__main__':main()
