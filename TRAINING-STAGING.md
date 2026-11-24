# Training review workspace

The server offers a separate course-only staging link for reviewing all 33 written lessons and worksheets without signing in. Lessons 1.1 and 1.2 include the existing sample videos; the other lessons remain written drafts.

The link is stored privately at `/var/lib/rycf-bootstrap/training-staging-link.json` on `runyourcarfleet-01`. It is not published in navigation, source control, or this document. Anyone with the link can view the draft course. `VYNE_TRAINING_PREVIEW_TOKEN` in the private runtime environment controls the link; removing or rotating it and restarting the app revokes the old link.

The preview serves an explicit allowlist of course assets before database access. It cannot read customer records, grant membership, or write server records. Production course and video access remain unchanged. Preview answers and progress use `rycf-course-staging-v1` browser storage, separate from customer course answers. Use Lessons & tools to download a backup; answers do not sync between devices. This is a review workspace, not an in-browser script editor.

The presentation is rendered from the deployed course source, so later course releases update the preview without duplicating the lesson curriculum. Staging is excluded from search indexing and browser/CDN caching, and sends no referrer. Software, account, and setup links are hidden to keep review navigation in the course.

Validation:

- 5 HTTP checks cover all 33 lessons, all 197 textareas (including review notes), missing/revoked preview links, blocked writes, asset allowlisting, video byte ranges, and no database access.
- 7 course interaction tests pass against the staging render, including all worksheets, resume, restore, and print behavior.
- 8 billing and 33 deployment checks pass.
- Live Chrome at 390 × 844 showed all 33 lessons with no horizontal overflow; both sample videos played. Local staging worksheet saving and resume were checked in Chrome. This is browser emulation, not physical iPhone QA.
- Anonymous origin checks confirmed preview access while the production course, private video, and customer API remained gated. Cloudflare blocked Python's public probe with 1010; public functionality was verified in Chrome instead.
- After deployment, the original signing blobs, three database integrity checks, settled rental and photos, and billing test mode were verified.

Deployment receipt and screenshots: `output/training-staging/`. Customer app HTML/JS/CSS, billing configuration and state were preserved. Only the server routing addition and new preview module were released. Earlier proposed sign-in navigation changes were deferred and saved in `output/training-access/auth-navigation-fix.patch` after the owner clarified that staging was the intended request.

## Lesson illustrations

All 33 staging lessons now have their own business concept illustration, with the exact lesson title rendered as HTML and a short teaching caption. The same pictures appear in the lesson list, module cards, and current lesson card. The two video lessons use matching illustrated posters; the existing video files and written curriculum are unchanged.

Original artwork was generated with the built-in image_gen tool, reviewed in three contact sheets, and optimized to 960 × 640 JPEGs. The 33 web images total approximately 4 MB, with lazy loading for pictures outside the current view. Assets are in `assets/lessons/`; the prompt set, accessible descriptions and captions are in `docs/lesson-art-direction-v1.json`. Original PNGs and review screenshots are retained under `output/lesson-art/`.

Artwork is attached only to the staging renderer. The production course, authentication, saved-answer keys, and video sources are preserved. Latest validation: 8 course interaction checks, 6 staging HTTP checks, and 34 deployment checks. All 33 deployed image files matched their local release bytes. Live Chrome at 390 × 844 showed the correct title and loaded illustration without horizontal overflow. The final phone screenshot was saved; subsequent screenshot capture encountered a browser focus timeout, so no physical-device or new browser-playback result is claimed.
