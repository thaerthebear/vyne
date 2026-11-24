# Training review — November 23, 2026

The current course contains 33 original written lesson drafts, 164 required worksheet questions, example answers and completion checks. There are two sample videos. This review does not certify the educational, legal or commercial completeness of the course, or full coverage of the referenced Whop videos.

## Fixed and deployed

- Returning to a lesson restores its reading part, worksheet question and lesson stage on the same browser.
- The home page recommends an unfinished lesson after the current worksheet is reviewed.
- Restoring a partial answer backup preserves unrelated answers and reviewed lessons. A partial backup cannot falsely mark a mixed worksheet reviewed.
- Oversized imported answers are rejected before changing existing work, instead of silently truncating them.
- Browser-save failures appear outside the collapsed tools panel and beside the worksheet.
- Printing uses the complete answer text rather than fixed-height textareas that can clip long answers.
- Full backups include resume positions. Existing v1 backups and original answer keys remain supported.

Only `course.html` and `training.css` changed in the hosted release. All 33 lesson bodies, prompts, examples, existing media, rental code and billing configuration are unchanged. Current billing remains test mode; live Stripe activation was deferred by the user.

## Verification

- Seven automated DOM regression checks pass, including all 33 worksheet completions, review invalidation after edits, exact reload position, partial/full restore, oversized import rejection, failed local storage and long printed answers.
- Run with `npm ci --prefix tests/training` then `npm test --prefix tests/training`.
- 33 deployment checks pass.
- Chrome at 390×844: course home has no horizontal overflow; the worksheet resumed at question 2 after an actual reload and retained question 1. Screenshots are in `output/training-audit/`. This is emulation, not physical iPhone testing.
- Host verification: all 145 release files match; all 23 original signing blobs match; three databases pass integrity checks; existing owner login, settled rental and both photos persist; both videos return matching byte ranges; four Cloudflare connections are ready.
- Public verification: sample lesson returns 200; full course redirects anonymous visitors to membership; protected lesson 1.2 media remains 403 anonymously. The authenticated course matches the release.

Current release: `/srv/vyne/releases/ebfb7eefa9fd1795`. Previous: `/srv/vyne/releases/5469e62440d56cf0`. A consistent pre-change application snapshot is in `/var/lib/rycf-bootstrap/training-fixes-pre-deploy/`. No database was restored or replaced. Roll back source through the previous release, without overwriting later customer records.

## Remaining training work

These gaps are still open; the fixes above do not complete them.

| Area | Current evidence | Needed to finish |
| --- | --- | --- |
| Lesson quality | All 33 have scripts, tasks, examples and checks; source package labels them editorial drafts | Review each lesson for accuracy and actionable depth; test with a beginner and an existing owner |
| Video | Two sample videos, 31 lessons currently taught in writing | Produce approved final videos using the saved mascot and Trevin voice; verify actual on-screen wording |
| Accessibility | Written lesson and transcript views exist; neither video has a separate caption track | Add and verify timed captions for both samples and every final video |
| Saved work | Answers, review marks and resume positions stay in this browser; JSON backup/restore supported | Account-backed sync with explicit migration, conflict handling and tenant isolation; no current cross-device promise |
| State/local checks | State selector saves a choice and explicitly says guides are unreviewed | Operating city/county and multiple locations; sourced, dated applicability checks; separate learner and editorial status |
| Assignments | Module assignments/capstone exist in the production package | Connect assignments to saved worksheet outputs without duplicate entry, and demonstrate a complete fictional rental |
| Help | Worksheet examples and optional questions are available | Define a real support route and response policy, carrying the lesson ID into requests |
| Account access | Full course requires eligible sign-in; public sample is free | Finish account recovery and verification before broad customer sales |
| Commercial readiness | Sandbox purchase/access checks exist; live Stripe is deferred | Resume approved Stripe setup after identity verification and complete the previously documented launch requirements |

The source inventory is `output/training-audit/curriculum-inventory.json`. The editorial master remains `/Users/rebuiltpros/Documents/ChatGPT/car rental/course-production-v1/`; its saved mascot, voice and prompts were not changed. No new videos, state-specific legal assertions or real charges were created in this pass.
