"""Attach the reviewed illustration set to staging without editing lesson content."""
IDS=('0.1','0.2','1.1','1.2','1.3','1.4','1.5','2.1','2.2','2.3','2.4','3.1','3.2','3.3','3.4','3.5','4.1','4.2','4.3','4.4','5.1','5.2','5.3','5.4','5.5','5.6','6.1','6.2','6.3','7.1','7.2','7.3','7.4')
ASSETS=tuple('assets/lessons/lesson-'+i.replace('.','-')+'-v1.jpg' for i in IDS)

def decorate(source,prefix):
 replacements={
  'visual.innerHTML=art(i);':"visual.append(window.RycfLessonArt.image(group.children[0].value,{decorative:true}));",
  'b.dataset.lessonLink=o.value;list.append(b)':"b.dataset.lessonLink=o.value;window.RycfLessonArt.thumbnail(b,o.value,o.textContent);list.append(b)",
  "heroTitle.textContent=Array.from(selector.options).find(o=>o.value===continueId).textContent;": "heroTitle.textContent=Array.from(selector.options).find(o=>o.value===continueId).textContent;window.RycfLessonArt.hero(hi,continueId);hc.querySelector('.hero-description').textContent=window.RycfLessonArt.info(continueId).caption;",
  "const oldVideoNote=$('p.note',script);if(video){const wrap=make('div','video-wrap');wrap.append(video);if(oldVideoNote)wrap.append(oldVideoNote);script.prepend(wrap)}else{const visual=make('div','lesson-visual');visual.innerHTML=art(index);script.prepend(visual)}": "const oldVideoNote=$('p.note',script);if(video){video.poster=window.RycfLessonArt.url(id);const wrap=make('div','video-wrap');wrap.append(video,make('p','video-visual-caption',window.RycfLessonArt.info(id).caption));if(oldVideoNote)wrap.append(oldVideoNote);script.prepend(wrap)}else{script.prepend(window.RycfLessonArt.figure(id))}",
 }
 for old,new in replacements.items():
  if source.count(old)!=1:raise ValueError('Course illustration integration needs review')
  source=source.replace(old,new,1)
 return source.replace('</head>','<link rel="stylesheet" href="'+prefix+'lesson-art.css?v=1"><script src="'+prefix+'lesson-art.js?v=1"></script></head>',1)
