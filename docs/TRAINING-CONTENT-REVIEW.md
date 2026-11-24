# All-lesson content review — November 23, 2026

Reviewed all 33 written lessons, their 164 required questions and 33 optional notes against the original curriculum, current course UI and module assignments. This is an editorial and functional review, not a customer usability study, legal certification or a review of every third-party Whop video. Stripe configuration was outside scope.

## Changes shared across the course

- Every lesson has one concrete output, preparation guidance, a four-part reader, a worked example and a manageable stopping point.
- Every required question has a specific hint and a collapsed worked answer. Optional follow-up notes can be skipped explicitly.
- Research can be unfinished: learners record an unknown and a next action. Fictional practice data is explicitly labeled and never presented as a real quote, customer, transaction or approval.
- 28 lessons link to earlier answers in a read-only panel, with links back to edit the source lesson. No duplicate answers are created or silently copied.
- The rental module uses R-001 throughout. Later pickup practice explicitly records the supplied fictional clearance assumptions instead of silently turning missing evidence into approval.
- The final rehearsal is now available in lesson 7.4 and question 4, with seven expandable steps. It reuses 5.1–5.6 instead of adding a separate set of required forms.
- Reader text is broken into short visual blocks. Next-question navigation stays with the question instead of scrolling back to the page header.
- Existing lesson IDs, all 197 textarea keys, review marks, v1 backup format, videos and illustration files are preserved. Revised guidance does not erase prior work or mark unanswered worksheets complete.

## Lesson-by-lesson findings and repairs

| Lesson | Main issue found | Revision |
| --- | --- | --- |
| 0.1 | Goal and pace were abstract | One study goal, one unknown and a scheduled next session; backup instructions |
| 0.2 | A beginner was asked about an existing process | Separate beginner/existing-owner routes, location examples and a valid first task |
| 1.1 | Good concept but no guidance at the individual answers | A coherent customer → need → offer → research worked profile |
| 1.2 | Three sourced comparisons were required without a complete practice dataset | Three labeled fictional offer cards, matching conditions and missing-total reasoning |
| 1.3 | Responsibility mapping remained abstract | Concrete owner/operator responsibilities, downtime explanation and unresolved rows |
| 1.4 | Accounting jargon and potential mixing of per-trip/per-day costs | Plain prompts, cost-unit conversion, worked math, nonpositive contribution and capacity limits |
| 1.5 | Asked learners to reuse work without exposing it | Earlier-answer panel and a short plan based on saved notes |
| 2.1 | No comparable candidate example | Two candidates judged on the same needs, with missing cost/history information |
| 2.2 | Practice assumed a real inspection/records existed | Supplied claims-versus-evidence case, recall source and an explicit hold decision |
| 2.3 | Warned about total commitment without showing it | Two fictional payment timelines and a checked total-cash-outlay comparison |
| 2.4 | Preparation checklist lacked concrete statuses | Cleaning/service/key/condition groups and a warning-indicator hold case |
| 3.1 | Told learners to find authorities without research starting points | Relevant official office categories and submitted/pending/confirmed evidence distinctions |
| 3.2 | Insurance questions were broad | A plain-language briefing, priority questions, document references and follow-up example |
| 3.3 | Review process lacked a complete missing-item scenario | Named-driver/additional-driver example and privacy/access/retention prompts |
| 3.4 | Referenced a fictional packet that was not supplied | R-001 facts and a specific return-day mismatch; version-preservation steps |
| 3.5 | Broad policy coverage could imply writing every policy immediately | Draft one process now; keep other topics as a later-work list |
| 4.1 | Listing advice without a full short draft | Factual sample listing, explicit unavailable service and one booking next step |
| 4.2 | Subtotal could be mistaken for an all-inclusive total | Itemized arithmetic, selected-option distinction and explicit unknown tax/deposit lines |
| 4.3 | Marketing task lacked a bounded example | One research channel, time/spend limit and a modest evidence-based decision rule |
| 4.4 | Inquiry response was described rather than demonstrated | A concise customer reply and status/person/next-action follow-up |
| 5.1 | No common rental record for the module | R-001 with one time conflict and explicit fictional clarification |
| 5.2 | Agreement status exercise lacked a concrete packet | Wrong return day, document version and delivery-without-signature scenario |
| 5.3 | Payment vocabulary assumed prior knowledge | Plain status concepts, matched fictional reference and duplicate-payment prevention |
| 5.4 | Later handoff could silently bypass earlier unresolved checks | Initial hold plus explicit fictional assumptions; specific condition/readings/return facts |
| 5.5 | Extension remained pending without a complete sample outcome | Actual fictional decline, next-booking conflict and unchanged original return |
| 5.6 | No full pickup/return comparison or closeout example | 150-mile comparison, existing mark, base arithmetic and honest pending items |
| 6.1 | Exception could conflict with the normal rental example | Separate late-return branch, timeline and calm message |
| 6.2 | No ready-to-practice incident contact/message example | Contact roles, verified-instruction questions and safety-first acknowledgment |
| 6.3 | Complaint exercise needed concrete evidence gaps | Separate fuel-charge case, missing photo, responsible reviewer and no invented refund |
| 7.1 | Metric jargon and denominator edge case | Explicit denominators, 75%/50% math and undefined zero-available-days case |
| 7.2 | Service appointment could be mistaken for readiness | Service/calendar example with evidence required before return to service |
| 7.3 | Staff procedure lacked a complete handoff | One return-inspection procedure, decision limit, access and reassignment steps |
| 7.4 | Required a capstone that was absent from the site | Embedded seven-step rehearsal, saved-answer references and a justified hold example |

## Evidence and limits

Canonical content: `docs/training-curriculum-v2.json`. Apply it with `node scripts/build-training-content.mjs` after installing the existing `tests/training` dependencies. The builder edits lesson content while preserving the surrounding UI, exact answer IDs and video elements. It is separate from the old v1 package generator, which must not be used to regenerate the current website.

A separate v2 export with 33 scripts and 33 worksheets is at `/Users/rebuiltpros/Documents/ChatGPT/car rental/course-production-v2/`. The v1 package, mascot, voice 3 / Trevin and media prompts are preserved. No new narration or video was produced; existing videos are short introductions, not recordings of every revised sentence.

Official background references were checked on November 23, 2026 and are linked only where relevant in lesson Sources & further reading: [SBA planning](https://www.sba.gov/counseling/plan-your-business/), [SBA break-even](https://bec.www.sba.gov/), [SBA setup](https://www.sba.gov/counseling/launch-your-business/), [NHTSA recall search](https://www.nhtsa.gov/recalls), [NAIC insurance education](https://content.naic.org/consumer/small-business.htm), [FTC information protection](https://www.ftc.gov/business-guidance/resources/protecting-personal-information-guide-business), and [IRS records](https://www.irs.gov/businesses/small-businesses-self-employed/what-kind-of-records-should-i-keep). These support limited concepts, not every course statement or state-specific approval. Numerical exercises and teaching scenarios are original fictional examples.

Ten automated staging course checks cover all 33 worksheet reviews, exact resume, v1 restore, partial restore, oversized imports, save failures, long-answer printing, unique artwork, retained answers, contextual examples, optional-note skipping, escaped earlier-answer display and capstone availability. Six staging HTTP checks and 34 deployment checks passed. Browser checks covered the phone worksheet, actual reload preservation, expanded example, final rehearsal and desktop home; 320- and 390-pixel views checked had no horizontal overflow. This is browser emulation, not a physical iPhone or beginner-customer trial.

Remaining work: real learner trial; qualified state/local, insurance and provider-specific review; final videos and timed captions; account/device answer sync if promised; real support and account-recovery processes. None is certified by this editorial pass. Live Stripe remains deferred.
