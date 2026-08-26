#!/usr/bin/env python3
"""Attempt Google's Indexing API (urlNotifications:publish) for priority URLs
that are stuck 'Discovered - not indexed' or 'URL unknown to Google'.

Uses the SAME GSC_KEY_JSON service-account credential already verified as a
site owner (see gsc_bootstrap.py), just requesting the additional
'indexing' OAuth scope. This is a legitimate, safe API call: worst case,
the Indexing API is not enabled on the linked Google Cloud project and
every call returns a clean 403 (logged, no side effects). If it IS enabled,
this can nudge Google to (re)crawl a URL faster than waiting on organic
discovery -- Google officially scopes this API to JobPosting/BroadcastEvent
content, so treat any success here as a bonus signal, not a guarantee.
"""
import json, os, sys, urllib.request, urllib.error

os.makedirs("reports", exist_ok=True)
OUT = "reports/indexing-api-status.md"

KEY = os.environ.get("GSC_KEY_JSON")
if not KEY:
    open(OUT, "w").write("# Indexing API attempt\n\nNo GSC_KEY_JSON in environment -- skipped.\n")
    sys.exit(0)

from google.oauth2 import service_account
import google.auth.transport.requests

PRIORITY_URLS = [
    "https://udyoggrowth.com/pmfme-subsidy-consultant/",
    "https://udyoggrowth.com/fssai-license-consultant/",
    "https://udyoggrowth.com/school-affiliation-consultant/",
    "https://udyoggrowth.com/import-export-iec-dgft-consultant/",
    "https://udyoggrowth.com/gem-registration-tender-bidding/",
    "https://udyoggrowth.com/bihar-gst-consultant/",
    "https://udyoggrowth.com/gst-consultant-faridabad/",
    "https://udyoggrowth.com/gst-consultant-patna/",
    "https://udyoggrowth.com/delhi-school-admissions/",
    "https://udyoggrowth.com/asmt-10-reply/",
]

try:
    creds = service_account.Credentials.from_service_account_info(
        json.loads(KEY), scopes=["https://www.googleapis.com/auth/indexing"])
    creds.refresh(google.auth.transport.requests.Request())
    tok = creds.token
except Exception as e:
    open(OUT, "w").write(f"# Indexing API attempt\n\nCredential/scope error: {e}\n")
    sys.exit(0)

results = []
for url in PRIORITY_URLS:
    req = urllib.request.Request(
        "https://indexing.googleapis.com/v3/urlNotifications:publish",
        method="POST",
        data=json.dumps({"url": url, "type": "URL_UPDATED"}).encode(),
        headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = json.loads(r.read())
            results.append((url, "OK", body.get("urlNotificationMetadata", {}).get("latestUpdate", {}).get("notifyTime", "")))
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:200]
        results.append((url, f"HTTP {e.code}", detail))
    except Exception as e:
        results.append((url, "ERROR", str(e)[:200]))

lines = ["# Indexing API attempt (Google urlNotifications:publish)", ""]
lines.append("| URL | Result | Detail |")
lines.append("|---|---|---|")
for url, status, detail in results:
    lines.append(f"| {url} | {status} | {detail} |")
lines.append("")
ok_count = sum(1 for _, s, _ in results if s == "OK")
lines.append(f"**{ok_count}/{len(results)} accepted.** A 403 here means the Indexing API "
              "is not enabled on the linked Google Cloud project (expected unless it was "
              "explicitly turned on) -- that requires the project owner's Google Cloud "
              "Console access, not something this credential/API call can self-enable.")
open(OUT, "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
