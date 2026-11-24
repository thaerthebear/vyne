"""Link-scoped course staging. No account, billing or customer-data access."""
import os
import re
import secrets
import lesson_art

FILES = {
 'lesson-art.js': ('lesson-art.js', 'text/javascript'),
 'lesson-art.css': ('lesson-art.css', 'text/css'),
 **{name: (name, 'image/jpeg') for name in lesson_art.ASSETS},
 'course.html': ('course.html', 'text/html; charset=utf-8'),
 'training.css': ('training.css', 'text/css'),
 'assets/training-cover-v1.png': ('assets/training-cover-v1.png', 'image/png'),
 **{name: ('lesson-media/'+name, 'video/mp4' if name.endswith('.mp4') else 'image/jpeg')
    for name in ('lesson-1-1.mp4', 'lesson-1-2.mp4', 'lesson-1-1-poster.jpg', 'lesson-1-2-poster.jpg')},
}

def course_html(source, prefix):
 source = source.replace("storeKey='rycf-course-draft-v1'", "storeKey='rycf-course-staging-v1'", 1)
 source = source.replace('<title>Your course', '<title>Training staging')
 for name in FILES:
  source = source.replace('/'+name, prefix+name)
 source = source.replace('href="/"', 'href="'+prefix+'course.html"')
 source = source.replace('</head>', '''<meta name="robots" content="noindex,nofollow,noarchive">
<style>
.staging-notice{max-width:1080px;margin:16px auto 0;padding:14px 18px;background:#eaf2ff;border:1px solid #c8d9ff;border-radius:12px;color:#153567;font:14px/1.5 system-ui}
.staging-notice strong{display:block}.staging-notice p{margin:4px 0 0}
body a[href^="/account.html"],body a[href="/academy.html"],.software-bridge{display:none!important}
@media(max-width:700px){.staging-notice{margin:12px 16px 0}}
@media print{.staging-notice{display:none}}
</style></head>''')
 source = source.replace('<main>', '''<aside class="staging-notice" aria-label="Training staging">
<strong>TRAINING STAGING · 33 lessons open</strong>
<p>Review copy · 2 sample videos · Answers save in this browser.</p>
</aside><main>''', 1)
 return lesson_art.decorate(source,prefix)

def handle(handler, root, path):
 token = os.environ.get('VYNE_TRAINING_PREVIEW_TOKEN', '')
 parts = path.split('/', 3)
 if (not re.fullmatch(r'[A-Za-z0-9_-]{32,100}', token)
     or len(parts) != 4 or not secrets.compare_digest(parts[2], token)):
  return handler.respond(404, {'error': 'Preview not found'})
 if handler.command != 'GET':
  return handler.respond(405, {'error': 'Preview is read-only; worksheet answers save in your browser'})
 name = parts[3] or 'course.html'
 if name not in FILES:
  return handler.respond(404, {'error': 'Preview not found'})
 relative, content_type = FILES[name]
 file = root / relative
 if not file.is_file():
  return handler.respond(404, {'error': 'Preview asset not available'})
 headers = {'X-Robots-Tag': 'noindex, nofollow, noarchive', 'Referrer-Policy': 'no-referrer',
            'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
            'Content-Security-Policy': "frame-ancestors 'none'"}
 if name == 'course.html':
  handler.response_headers.update(headers)
  return handler.respond(200, course_html(file.read_text(), '/training-preview/'+token+'/'), content_type)
 total = file.stat().st_size
 start, end, status = 0, total-1, 200
 requested = handler.headers.get('Range')
 if requested:
  match = re.fullmatch(r'bytes=(\d{0,16})-(\d{0,16})', requested)
  valid = match and any(match.groups())
  if valid:
   a, b = match.groups()
   if a: start, end = int(a), min(int(b), total-1) if b else total-1
   else: start = max(0, total-int(b))
   valid = start <= end and start < total
  if not valid:
   handler.response_headers.update({**headers, 'Content-Range': f'bytes */{total}'})
   return handler.respond(416, '', 'text/plain')
  status = 206
 handler.send_response(status)
 for key, value in {**headers, 'Content-Type': content_type, 'Content-Length': str(end-start+1), 'Accept-Ranges': 'bytes'}.items():
  handler.send_header(key, value)
 if status == 206: handler.send_header('Content-Range', f'bytes {start}-{end}/{total}')
 handler.end_headers()
 with file.open('rb') as stream:
  stream.seek(start)
  remaining = end-start+1
  while remaining:
   block = stream.read(min(65536, remaining))
   if not block: break
   handler.wfile.write(block)
   remaining -= len(block)
