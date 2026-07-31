#!/usr/bin/env python3
"""GSC eyes: sitemap submit + index status of all URLs + performance -> reports/gsc-status.md (errors included)."""
import json, os, sys, re, datetime, traceback, urllib.request, urllib.parse

OUT = "reports/gsc-status.md"
os.makedirs("reports", exist_ok=True)
KEY = os.environ.get("GSC_KEY_JSON")
if not KEY:
    open(OUT, "w").write("# GSC\n\nGSC_KEY_JSON secret not set.\n")
    sys.exit(0)

def main():
    from google.oauth2 import service_account
    import google.auth.transport.requests
    creds = service_account.Credentials.from_service_account_info(
        json.loads(KEY), scopes=["https://www.googleapis.com/auth/webmasters"])
    creds.refresh(google.auth.transport.requests.Request())
    tok = creds.token
    # auto-detect property: prefer domain property, else URL-prefix
    def _list_sites(t):
        req = urllib.request.Request("https://www.googleapis.com/webmasters/v3/sites",
            headers={"Authorization": "Bearer " + t})
        with urllib.request.urlopen(req, timeout=30) as r:
            return [e["siteUrl"] for e in json.loads(r.read()).get("siteEntry", [])]
    avail = _list_sites(tok)
    def pick(a):
        for want in ("sc-domain:udyoggrowth.com", "https://udyoggrowth.com/"):
            if want in a: return want
        return next((x for x in a if "udyoggrowth" in x), "https://udyoggrowth.com/")
    site = pick(avail)
    enc = urllib.parse.quote(site, safe="")
    prefix = "https://udyoggrowth.com/"

    def call(url, method="GET", body=None):
        req = urllib.request.Request(url, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = r.read()
                return json.loads(d) if d else {}
        except urllib.error.HTTPError as e:
            return {"error": e.code, "detail": e.read().decode()[:300]}

    sm = call("https://www.googleapis.com/webmasters/v3/sites/%s/sitemaps/%s" %
              (enc, urllib.parse.quote(prefix + "sitemap.xml", safe="")), "PUT")

    urls = re.findall(r"<loc>(.*?)</loc>", open("sitemap.xml").read())
    rows = []
    for u in urls:
        r = call("https://searchconsole.googleapis.com/v1/urlInspection/index:inspect", "POST",
                 {"inspectionUrl": u, "siteUrl": site})
        if "error" in r:
            rows.append((u.replace(prefix, "/"), "ERR %s: %s" % (r["error"], r["detail"][:80]), "-"))
        else:
            st = r.get("inspectionResult", {}).get("indexStatusResult", {})
            rows.append((u.replace(prefix, "/"), st.get("coverageState", "?"),
                         (st.get("lastCrawlTime") or "-")[:10]))

    today = datetime.date.today()
    start = today - datetime.timedelta(days=28)
    def perf(dim):
        return call("https://www.googleapis.com/webmasters/v3/sites/%s/searchAnalytics/query" % enc,
                    "POST", {"startDate": str(start), "endDate": str(today),
                             "dimensions": [dim], "rowLimit": 25})
    pq, pp = perf("query"), perf("page")

    out = ["# GSC Status — %s (auto) — property: %s" % (today, site), "",
           "Sitemap resubmit: %s" % ("OK" if "error" not in sm else sm), "",
           "## Index status", "| Page | Coverage | Last crawl |", "|---|---|---|"]
    out += ["| %s | %s | %s |" % r for r in rows]
    out += ["", "## Top queries (28d)", "| Query | Clicks | Impr | Pos |", "|---|---|---|---|"]
    qr = pq.get("rows") or []
    out += ["| %s | %s | %s | %.1f |" % (r["keys"][0], r["clicks"], r["impressions"], r["position"]) for r in qr] or ["| (no data yet — %s) | | | |" % pq.get("error", "")]
    out += ["", "## Top pages (28d)", "| Page | Clicks | Impr |", "|---|---|---|"]
    pr = pp.get("rows") or []
    out += ["| %s | %s | %s |" % (r["keys"][0].replace(prefix, "/"), r["clicks"], r["impressions"]) for r in pr] or ["| (no data yet) | | |"]
    open(OUT, "w").write("\n".join(out) + "\n")
    print("report written:", len(rows), "URLs")

try:
    main()
except Exception:
    open(OUT, "w").write("# GSC run ERROR\n\n```\n" + traceback.format_exc() + "\n```\n")
    print("wrote error report")
