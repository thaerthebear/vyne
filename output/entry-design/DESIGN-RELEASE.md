# Approved homepage and sign-in design

Implements the approved navy/blue sales-and-login concept as real responsive HTML: the main headline, original visual artwork, software/training cards, and functional email/password sign-in. Both `/` and `/account.html` share the entrance. Existing account management, invitations, business choice and role handling remain available after login.

The platform-overview dialog links to the existing written course and software entry. No registration, payment, insurance, subscription or course-sync capability was invented. Course answers still use browser storage. No live customer mail is sent by this change.

UI artwork is the approved concept; CSS displays its original product illustrations. Header, copy, navigation, login fields and actions are live HTML controls.

Validation before release: 13 client tests, 13 account HTTP/model tests and 8 package tests passed. Local Chrome phone viewport checks covered layout, overview dialog, sign-in anchor and successful fictional-account login to the dashboard. Safe redirect checks preserve workspace destinations, allow training and reject an external destination. Source comparison retains 130 previous release files unchanged, including all lessons, worksheets, video media and rental/provider modules. The only server changes are explicit public CSS/JS/image routes; database initialization and rental mutation code are unchanged.

This is a scoped source commit in the existing repository. Unrelated local work, databases, credentials, original third-party course documents, recovery archives and deployment state are not included. The complete private deployment package retains the existing application's dependencies and content.
