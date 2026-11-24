import os,sys,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import server as s
import training_preview
TOKEN='synthetic-preview-link-for-isolated-tests-2026'
class TrainingPreviewTests(unittest.TestCase):
 def setUp(self):
  self.env=patch.dict(os.environ,{'VYNE_TRAINING_PREVIEW_TOKEN':TOKEN});self.env.start()
  self.http=s.ThreadingHTTPServer(('127.0.0.1',0),s.Handler);threading.Thread(target=self.http.serve_forever,daemon=True).start()
  self.base='http://127.0.0.1:'+str(self.http.server_port)
  self.prefix='/training-preview/'+TOKEN+'/'
 def tearDown(self):
  self.http.shutdown();self.http.server_close();self.env.stop()
 def req(self,path,headers=None,data=None):
  try:return urllib.request.urlopen(urllib.request.Request(self.base+path,headers=headers or {},data=data))
  except urllib.error.HTTPError as e:return e
 def test_all_lessons_and_answers_without_session_or_database(self):
  with patch.object(s,'connect',side_effect=AssertionError('Preview must not access customer data')):
   with self.req(self.prefix+'course.html?lesson=1.2') as r:
    self.assertEqual(r.status,200);body=r.read().decode()
    self.assertEqual(body.count('<section data-lesson='),33)
    self.assertEqual(body.count('<textarea '),197)
    self.assertIn("storeKey='rycf-course-staging-v1'",body)
    self.assertNotIn("storeKey='rycf-course-draft-v1'",body)
    self.assertIn(self.prefix+'lesson-1-2.mp4?v=2',body)
    self.assertIn('TRAINING STAGING',body)
    self.assertIn('noindex',r.headers['X-Robots-Tag'])
    self.assertEqual(r.headers['Referrer-Policy'],'no-referrer')
    self.assertIn('no-store',r.headers['Cache-Control'])
    self.assertIsNone(r.headers.get('Set-Cookie'))
 def test_unknown_or_disabled_link_is_not_publicly_accessible(self):
  for path in ['/training-preview/wrong/course.html',self.prefix+'api/admin/profile',self.prefix+'../../backend/server.py',self.prefix+'account.html']:
   with self.req(path) as r:self.assertEqual(r.status,404)
  with patch.dict(os.environ,{'VYNE_TRAINING_PREVIEW_TOKEN':''}):
   with self.req(self.prefix) as r:self.assertEqual(r.status,404)
 def test_preview_cannot_write_any_server_records(self):
  with patch.object(s,'connect',side_effect=AssertionError('No DB writes')):
   with self.req(self.prefix+'course.html',data=b'{}') as r:self.assertEqual(r.status,405)
 def test_both_videos_seek_without_login_and_do_not_cache(self):
  for name in ['lesson-1-1.mp4','lesson-1-2.mp4']:
   for requested,expected in [('bytes=0-1023',(s.ROOT/'lesson-media'/name).read_bytes()[:1024]),('bytes=-64',(s.ROOT/'lesson-media'/name).read_bytes()[-64:])]:
    with self.req(self.prefix+name,{'Range':requested}) as r:
     self.assertEqual(r.status,206);self.assertEqual(r.read(),expected);self.assertIn('no-store',r.headers['Cache-Control'])
   for requested in ['bytes=5-2','bytes=-0','bytes=0-1,3-4','bytes=999999999999999999999999999999999-']:
    with self.req(self.prefix+name,{'Range':requested}) as r:self.assertEqual(r.status,416)
 def test_only_allowlisted_assets_available(self):
  for name in ['training.css','assets/training-cover-v1.png','lesson-1-1-poster.jpg','lesson-1-2-poster.jpg']:
   with self.req(self.prefix+name) as r:
    self.assertEqual(r.status,200);self.assertEqual(r.read(),(s.ROOT/training_preview.FILES[name][0]).read_bytes())
if __name__=='__main__':unittest.main()
