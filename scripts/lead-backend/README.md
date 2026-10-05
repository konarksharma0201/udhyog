# Lead capture backend (Google Apps Script)

Runs under udyoggrowth@gmail.com: mail is sent from and to that account; leads go to a Google Sheet ("Udyog Growth — Leads").

1. Sign in as udyoggrowth@gmail.com -> script.google.com -> New project -> paste `Code.gs`.
2. Run `setup` (authorise when asked) -> creates the sheet with dropdowns, colours, dashboard.
3. Run `testLead` -> a test row appears and an email with the .xlsx attached arrives. Delete the test row.
4. Deploy -> New deployment -> Web app -> Execute as: Me -> Who has access: Anyone -> copy the `/exec` URL.
5. Put the URL in `assets/lead-popup.js` (`CFG.endpoint`) — currently set. Empty endpoint = popup disabled, links work as before.
6. Optional: run `installTriggers` for a 9 AM IST daily digest.
`SITE_KEY` in Code.gs must equal `CFG.key` in lead-popup.js.
