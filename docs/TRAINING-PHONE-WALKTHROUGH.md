# New-owner phone walkthrough — November 25, 2026

Tested in the user's Thaerbearllc Chrome profile. Phone viewport simulation is not a physical iPhone test or a study with an independent novice.

## Findings and repairs

- The initial mobile hero and global roadmap pushed the lesson action below the first screen. Kept the illustrations, made mobile art compact, and placed the roadmap after the next lesson card. Fresh learners see Start here; existing drafts show Resume lesson.
- Browser Back left the course because all lesson changes replaced history. Course navigation now records home, lesson and stage transitions. Back/Forward restore the reading part or worksheet question without changing answers. Returning from earlier-lesson references works too.
- The full lessons for 1.1 and 1.2 were hidden behind a disclosure while a takeaways shortcut let the learner miss them. Written lessons now appear directly; videos remain available as optional introductions with transcripts. Fixed the video-note selector so preparation time stays with preparation and the intro note stays with its video.
- Reading Next now moves focus and scroll position to the new part. Preparation details remain available without occupying the opening screen.
- Long review answers produced a long wall of text. Review now shows expandable previews and an explicit statement that answers are not graded. Added Pause for now to worksheet/completion screens, preserving existing resume storage.
- The home screen now identifies all 33 worksheets as reviewed instead of presenting endless continuation. Renamed the backup control to Download answers to match the lesson instructions.

## Browser evidence

- Inspected all 33 lesson Read and Practice screens at 390 × 844: four reading parts each, original artwork/video, one visible worksheet input, no horizontal overflow. Required questions had contextual help; the optional note intentionally has none.
- Worked through the roadmap with fictional beginner answers; completed a fictional pickup worksheet through review and completion. Used a stated unknown and next action instead of inventing operating approval.
- Paused on question 2 of lesson 1.1, reloaded and resumed on that question with the draft intact.
- Opened earlier lesson 1.1 from lesson 1.5 and used browser Back to return to 1.5 Practice.
- Downloaded a v1 answer backup through the UI and restored it. The page confirmed restoration and retained the 0.1 and 5.4 answers. Chrome's download-event listener timed out although the download succeeded; verified the actual JSON artifact and UI restore result.
- Checked home layout at widths 320, 390, 768 and 1280: no horizontal overflow or overlap between artwork and copy. Retained the concurrent layout-repair chat's deployed CSS fixes.
- Public staging at 390 × 844 shows 33 lessons, 197 fields and 2 videos. The primary action ends at y=612, above navigation at y=777. Live Back returned to course home. Viewport overrides were reset afterward.
- Screenshot: `output/training-new-owner/live-phone.jpg`.

## Regression and release evidence

15 course behavior tests, 6 staging HTTP checks and 34 deployment tests passed (55 distinct tests). Three targeted checks were repeated after the backup-label edit. Coverage includes all 33 worksheet completion paths, edits invalidating only their own review, exact resume, failed storage reporting, partial/full restore, long answers, escaping, illustration mapping, and the final rehearsal.

Preserved all 197 textarea IDs/data keys, v1 backup format and production/staging storage keys. No curriculum answers, videos, artwork files, customer databases, billing configuration or rental application code were replaced.

Release `59ede465d48c6578` was based on the verified current release `2adae8e39a1c550b` and changes only `course.html`, `training.css` and `backend/lesson_art.py`. Runtime and billing config bytes were checked before/after activation. Consistent database backup was taken; rollback is a source switch, not a database restore.

After activation: all 182 manifest files match; all 23 original signing blobs remain; all three databases pass integrity checks; owner fixture login works; the settled rental and both photos persist; both video byte-range requests return matching 206 responses; Cloudflare has 4 active connections. Stripe remains in test mode with live rental payments disabled. Existing sample videos are preserved; their availability does not mean all 33 final videos exist.

Detailed receipts live in `output/training-new-owner/`. No physical-device Safari or independent learner validation is claimed.
