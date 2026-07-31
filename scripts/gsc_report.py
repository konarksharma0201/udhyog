#!/usr/bin/env python3
"""Daily GSC eyes: submit sitemap, inspect all URLs' index status, pull performance -> reports/gsc-status.md"""
import json, os, sys, datetime, urllib.request, urllib.parse

KEY = os.environ.get("GSC_KEY_JSON")
if not KEY:
    print("GSC_KEY_JSON secret not set — skipping (add it in repo Settings > Secrets)"); sys.exit(0)

from google.oauth2 import service_account
import google.auth.transport.requests

creds = service_account.Credentials.from_service_account_info(
    json.loads(KEY), scopes=["https://www.googleapis.com/auth/webmasters"])
creds.refresh(google.auth.transport.requests.Request())
TOK = creds.token
SITE = "https://udyoggrowth.com/"
ENC = urllib.parse.quote(SITE, safe="")

def call(url, method="GET", body=None):
    req = urllib.request.Request(url, method=method,
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bearer {TOK}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = r.read()
            return json.loads(d) if d else {}
    except urllib.error.HTTPError as e:
        return {"error": e.code, "detail": e.read().decode()[:200]}

# 1) (re)submit sitemap
sm = call(f"https://www.googleapis.com/webmasters/v3/sites/{ENC}/sitemaps/{urllib.parse.quote(SITE+'sitemap.xml',safe='')}", "PUT")

# 2) inspect every sitemap URL
import re
urls = re.findall(r"<loc>(.*?)</loc>", open("sitemap.xml").read())
rows = []
for u in urls:
    r = call("https://searchconsole.googleapis.com/v1/urlInspection/index:inspect", "POST",
             {"inspectionUrl": u, "siteUrl": SITE})
    st = r.get("inspectionResult", {}).get("indexStatusResult", {})
    rows.append((u.replace(SITE, "/"), st.get("coverageState", r.get("error", "?")),
                 (st.get("lastCrawlTime") or "-")[:10]))

# 3) performance last 28d: top queries + pages
today = datetime.date.today(); start = today - datetime.timedelta(days=28)
perf_q = call(f"https://www.googleapis.com/webmasters/v3/sites/{ENC}/searchAnalytics/query", "POST",
    {"startDate": str(start), "endDate": str(today), "dimensions": ["query"], "rowLimit": 25})
perf_p = call(f"https://www.googleapis.com/webmasters/v3/sites/{ENC}/searchAnalytics/query", "POST",
    {"startDate": str(start), "endDate": str(today), "dimensions": ["page"], "rowLimit": 25})

out = [f"# GSC Status — {today} (auto-generated)", "",
       f"Sitemap resubmit: {'OK' if 'error' not in sm else sm}", "",
       "## Index status (all URLs)", "| Page | Coverage | Last crawl |", "|---|---|---|"]
for p, c, t in rows: out.append(f"| {p} | {c} | {t} |")
out += ["", "## Top queries (28d)", "| Query | Clicks | Impr | Pos |", "|---|---|---|---|"]
for r in (perf_q.get("rows") or [])[:25]:
    out.append(f"| {r['keys'][0]} | {r['clicks']} | {r['impressions']} | {r['position']:.1f} |")
if not perf_q.get("rows"): out.append("| (no data yet) | | | |")
out += ["", "## Top pages (28d)", "| Page | Clicks | Impr |", "|---|---|---|"]
for r in (perf_p.get("rows") or [])[:25]:
    out.append(f"| {r['keys'][0].replace(SITE,'/')} | {r['clicks']} | {r['impressions']} |")
if not perf_p.get("rows"): out.append("| (no data yet) | | |")

open("reports/gsc-status.md", "w").write("\n".join(out) + "\n")
print("report written:", len(rows), "URLs inspected")
