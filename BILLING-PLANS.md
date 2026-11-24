# Run Your Car Fleet memberships

Deployment: 2026-11-23. The website and signup/checkout integration are deployed on the Dell home-server VM. Stripe is connected to **Only One Worker in TEST MODE**. No real money has moved. Live sales remain disabled until a dedicated restricted live key is approved and configured.

| Plan | Price | Access |
| --- | --- | --- |
| Software monthly | $49 each month | 5 active vehicles, 2 staff including owner; training separate |
| Software + training yearly | $490 each year | Same software limits; all 33 written lessons and worksheets during paid annual term |
| Training only | $99 once | 12 months of course access; no software subscription; no renewal |

Existing workspaces were grandfathered by a one-time migration. Saved course content, records, original signing assets, and the current business owner's access are preserved. The course still has two sample videos, not 33 finished videos; state-specific guides remain unfinished. Renter payments and coverage/identity checks remain demonstrations. SaaS subscriptions do not turn those demonstrations into real renter collections or legal approval.

## Purchase and access

1. `/membership.html` shows exact price, interval, limits, merchant and test/live mode.
2. A customer registers with name, email and a 12–256 character password, or signs in. A new tenant begins unpaid.
3. The server chooses the configured immutable Stripe price; the browser cannot supply an amount, Stripe customer or subscription ID.
4. Stripe hosts payment collection. No card data goes through this app.
5. Signed webhooks and an authenticated server reconciliation fetch the current Checkout Session, price, subscription, paid invoice and payment intent. A success URL alone grants no access.
6. Software APIs and the full course/media enforce paid access on the server. Lesson 1.1 remains a free sample.
7. Membership offers receipts/payment-method management through a dedicated Stripe portal, and cancellation of the next renewal. Cancellation preserves the paid term. A full refund or unresolved dispute blocks the affected purchase; a failed renewal does not extend its paid period.

One unfinished checkout is reused per product category. Switching plans requires closing that checkout. An ambiguous creation older than 23 hours requires support review rather than risking a new charge after Stripe's idempotency-key window. Duplicate purchases and cross-tenant refreshes are rejected. Signed event replays are idempotent; out-of-order events re-read current Stripe state.

Five-vehicle enforcement includes unarchiving. Two-seat enforcement includes outstanding invitations and re-checks invitation acceptance. Existing workspaces have preserved limits. New paid students use individual local-browser worksheet keys; existing workspaces retain their original storage key and answers. Answers do not synchronize between devices. Download/print remains available. Password recovery, email verification and MFA are not implemented; signup discloses the recovery limitation.

## Evidence

- 263 backend regression tests passed, including the initial six billing tests. The final billing suite has eight passing tests after additional course-isolation and price/idempotency coverage.
- 21 client tests and 33 deployment tests passed; account-client tests were rerun after final changes.
- Annual: Chrome signup, actual Stripe sandbox checkout at $490, return to the app, and software + course unlock.
- Monthly: actual Stripe sandbox declined card, successful retry at $49, signed webhooks grant software only, duplicate blocked, next renewal canceled while paid access remains.
- Training: actual Stripe sandbox checkout at $99 with a 3D Secure challenge, signed webhook grants training only; actual sandbox refund removes training access through the webhook.
- Provider portal session creation, tenant separation, malformed signatures, replay/out-of-order events, expired training and failed renewal behavior checked.
- Published layout inspected at 390×844 with no horizontal overflow. This is browser phone emulation, not physical iPhone testing.
- On the home server: all 145 release files match their manifest, all 23 original signing blobs match, three databases pass integrity checks, existing login and settled rental/photos survive, both video byte ranges match, and four Cloudflare connections remain ready.
- Two pre-existing legacy unbound agreements remain a signing-reconciliation limitation; this release does not certify live rental readiness.

Sanitized evidence: `output/billing-plans/hosted-verification.json`, `server-verification.json`, `release.json`, `billing-tests.log`, `backend-tests.log`, `client-tests.log`, `deployment-tests.log`. Private credentials/test fixtures are ignored under `output/billing-plans/private/` and are never part of the source release.

## Hosted release and rollback

Current test release: `/srv/vyne/releases/5469e62440d56cf0`; previous `/srv/vyne/releases/8acdc29f23cf5cb4`. A consistent pre-migration application snapshot and prior runtime environment are in `/var/lib/rycf-bootstrap/billing-pre-deploy/`. No existing state was restored or replaced. Source rollback uses the previous symlink plus saved runtime environment; do not restore the database over new purchases. New billing tables are additive.

Private host configuration: `/srv/vyne/state/config/billing.json`, mode0600, owned by `vyne`; `VYNE_BILLING_CONFIG` points there. `mode`, key prefix, webhook secret, merchant binding, all three distinct price IDs and HTTPS return origin are validated. Stripe API version is pinned to `2024-06-20`. Test and live customers, orders and entitlements are isolated by mode. Changing merchants cannot silently reuse customer IDs.

## Live activation awaiting credential approval

Prepared Stripe key name: **Run Your Car Fleet live billing**, in Only One Worker. Requested resources:

- Write: Customers, Products, Prices, Subscriptions, Checkout Sessions, Customer Portal, Webhook Endpoints/Event Destinations.
- Read: Accounts, Charges and Refunds, Payment Intents, Payment Disputes, Invoices.
- No payout, bank-account, transfer, refund-write, or payment-intent-write permissions.

The browser requires action-time confirmation before creating new security-sensitive access. The key has **not** been created. Live product/price provisioning and a live webhook must use separate IDs/secrets; never substitute a live key into the test configuration. Live configuration requires explicit `liveSalesApproved: true`. Verify the merchant has charges enabled and the prepared checkout amounts before activating. No real card should be charged for validation.

Before advertising the SaaS as production-ready, complete account recovery, published business/refund/privacy terms and tax decisions, offsite backup/restore exercises, and the separate real-rental provider/legal readiness work. These are unresolved launch limitations, not passed checks.

Stripe references: [Checkout fulfillment](https://docs.stripe.com/checkout/fulfillment), [webhooks](https://docs.stripe.com/webhooks), [test cards](https://docs.stripe.com/testing), [customer portal](https://docs.stripe.com/api/customer_portal/sessions/create).
