import importlib.util,json,tempfile,unittest
from html.parser import HTMLParser
from pathlib import Path
SPEC=importlib.util.spec_from_file_location('release',Path(__file__).resolve().parents[1]/'package_release.py')
r=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(r)
class ReleasePackage(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name).resolve();self.root=self.base/'source';self.root.mkdir()
  for name in ['index.html','backend/server.py','backend/data.sqlite3','investor-demo/private/config.json','investor-demo/private/submissions.json','investor-demo/index.html','investor-demo/demo.js','investor-demo/.venv/bin/python','.env','output/customer.pdf','deployment/README.md','deployment/runtime.env','deployment/app.json','deployment/provider.json','deployment/docuseal.env','course-materials/originals/source.pdf']:
   p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture')
 def test_allowlist_omits_runtime_private_and_output(self):
  result=r.build(self.root,self.base/'release');names={x['path'] for x in result['files']}
  self.assertEqual(names,{'index.html','backend/server.py','deployment/README.md','course-materials/originals/source.pdf','investor-demo/index.html','investor-demo/demo.js'})
  self.assertFalse(result['livePilotReady']);r.verify(self.base/'release')
  with self.assertRaises(FileExistsError):r.build(self.root,self.base/'release')
 def test_open_road_and_functional_frontend_assets_are_preserved(self):
  for name in ['open-road.css','journey.css','journey.js','account-client.js','rentals.html','account.html','trip.html']:
   (self.root/name).write_text('current working UI: '+name)
  manifest=r.build(self.root,self.base/'release');names={x['path'] for x in manifest['files']}
  for name in ['open-road.css','journey.css','journey.js','account-client.js','rentals.html','account.html','trip.html']:
   self.assertIn(name,names)
   self.assertEqual((self.root/name).read_bytes(),(self.base/'release'/name).read_bytes())
 def test_repository_ui_local_styles_and_scripts_are_packaged(self):
  root=Path(__file__).resolve().parents[2]
  names={p.relative_to(root).as_posix() for p in r.source_files(root)}
  class Assets(HTMLParser):
   def __init__(self):super().__init__();self.paths=[]
   def handle_starttag(self,tag,attrs):
    attrs=dict(attrs)
    if tag=='script' and attrs.get('src'):self.paths.append(attrs['src'])
    if tag=='link' and attrs.get('rel')=='stylesheet':self.paths.append(attrs.get('href',''))
  self.assertIn('open-road.css',names)
  for html in [*root.glob('*.html'),root/'investor-demo/index.html']:
   parser=Assets();parser.feed(html.read_text())
   for asset in parser.paths:
    if not asset or asset.startswith(('https:','http:','//','data:')):continue
    name=asset.lstrip('/').split('?',1)[0]
    if name=='demo.js':name='investor-demo/demo.js'
    with self.subTest(page=html.name,asset=name):self.assertIn(name,names)
 def test_course_videos_and_posters_migrate_but_unrelated_uploads_do_not(self):
  media=['lesson-1-1.mp4','lesson-1-1-poster.jpg','lesson-1-2.mp4','lesson-1-2-poster.jpg']
  (self.root/'lesson-media').mkdir()
  for name in media+['private-renter-photo.jpg']:(self.root/'lesson-media'/name).write_bytes(b'fixture-'+name.encode())
  manifest=r.build(self.root,self.base/'release');names={x['path'] for x in manifest['files']}
  for name in media:
   self.assertIn('lesson-media/'+name,names)
   self.assertEqual((self.root/'lesson-media'/name).read_bytes(),(self.base/'release/lesson-media'/name).read_bytes())
  self.assertNotIn('lesson-media/private-renter-photo.jpg',names)
 def test_public_entry_artwork_is_explicitly_allowlisted(self):
  (self.root/'assets').mkdir()
  for name in ['entry-concept-v1.png','training-cover-v1.png','private-upload.png']:(self.root/'assets'/name).write_bytes(b'fixture-image')
  manifest=r.build(self.root,self.base/'release');names={x['path'] for x in manifest['files']}
  self.assertIn('assets/entry-concept-v1.png',names)
  self.assertIn('assets/training-cover-v1.png',names)
  self.assertNotIn('assets/private-upload.png',names)
 def test_lesson_artwork_is_packaged_without_unrelated_uploads(self):
  assets=self.root/'assets/lessons';assets.mkdir(parents=True)
  for name in ['lesson-0-1-v1.jpg','lesson-7-4-v1.jpg','private-upload.jpg']:(assets/name).write_bytes(b'fixture')
  result=r.build(self.root,self.base/'release');names={x['path'] for x in result['files']}
  self.assertIn('assets/lessons/lesson-0-1-v1.jpg',names);self.assertIn('assets/lessons/lesson-7-4-v1.jpg',names)
  self.assertNotIn('assets/lessons/private-upload.jpg',names)
 def test_real_course_and_media_routes_are_in_release(self):
  root=Path(__file__).resolve().parents[2]
  names={p.relative_to(root).as_posix() for p in r.source_files(root)}
  self.assertIn('course.html',names)
  import re
  for page in ['course.html','lesson-sample.html']:
   for asset in re.findall(r'(?:src|poster)=["\'](/lesson-[^"\'?]+)',(root/page).read_text()):
    self.assertIn('lesson-media/'+asset.lstrip('/'),names)
 def test_tamper_and_unlisted_files_fail(self):
  r.build(self.root,self.base/'release');p=self.base/'release/index.html';p.write_text('changed')
  with self.assertRaises(ValueError):r.verify(self.base/'release')
  p.write_text('fixture');(self.base/'release/unlisted.txt').write_text('extra')
  with self.assertRaises(ValueError):r.verify(self.base/'release')
 def test_symlink_and_manifest_escape_fail(self):
  (self.root/'linked.js').symlink_to(self.root/'index.html')
  with self.assertRaises(ValueError):r.build(self.root,self.base/'release')
  (self.root/'linked.js').unlink();r.build(self.root,self.base/'release')
  p=self.base/'release/release-manifest.json';manifest=json.loads(p.read_text());manifest['files'][0]['path']='../outside';p.write_text(json.dumps(manifest))
  with self.assertRaises(ValueError):r.verify(self.base/'release')
if __name__=='__main__':unittest.main()
