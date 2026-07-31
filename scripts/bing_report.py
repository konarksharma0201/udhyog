#!/usr/bin/env python3
"""Bing Webmaster automation: add site, submit sitemap, submit all URLs (legit Bing feature),
pull rank/traffic + crawl stats -> reports/bing-status.md (always writes, errors visible)."""
import json, os, re, sys, urllib.request, urllib.parse

os.makedirs("reports", exist_ok=True)
OUT = "reports/bing-status.md"
KEY = os.environ.get("BING_API_KEY")
SITE = "https://udyoggrowth.com"

if not KEY:
    open(OUT, "w").write("# Bing\n\nBING_API_KEY secret not set.\n")
    sys.exit(0)

BASE = "https://ssl.bing.com/webmaster/api.svc/json/"

def call(method, params=None, http_method="GET"):
    q = {"apikey": KEY}
    body = None
    if http_method == "GET":
        if params: q.update(params)
        url = BASE + method + "?" + urllib.parse.urlencode(q)
        req = urllib.request.Request(url, method="GET")
    else:
        url = BASE + method + "?" + urllib.parse.urlencode({"apikey": KEY})
        body = json.dumps(params or {}).encode()
        req = urllib.request.Request(url, data=body, method="POST",
                                      headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = r.read()
            return json.loads(d) if d else {}
    except urllib.error.HTTPError as e:
        return {"__error": e.code, "__detail": e.read().decode()[:400]}
    except Exception as e:
        return {"__error": "exception", "__detail": str(e)[:400]}

log = []
def L(*a): s = " ".join(map(str, a)); print(s); log.append(s)

# 1) list sites; add if missing
sites = call("GetUserSites")
site_list = sites.get("d") or []
L("GetUserSites:", "OK" if isinstance(sites.get("d"), list) else json.dumps(sites)[:300])
have = any((s.get("Url") or "").rstrip("/") == SITE.rstrip("/") for s in site_list) if isinstance(site_list, list) else False
if not have:
    add = call("AddSite", {"siteUrl": SITE}, "POST")
    L("AddSite:", "OK" if "__error" not in add else json.dumps(add)[:300])
else:
    L("AddSite: already present")

# 2) submit sitemap
sm = call("SubmitFeed" if False else "SubmitSitemap", {"siteUrl": SITE, "feedUrl": SITE + "/sitemap.xml"}, "POST")
L("SubmitSitemap:", "OK" if "__error" not in sm else json.dumps(sm)[:300])

# 3) submit all URLs (Bing officially supports direct URL submission — unlike Google)
urls = re.findall(r"<loc>(.*?)</loc>", open("sitemap.xml").read())
batch = call("SubmitUrlBatch", {"siteUrl": SITE, "urlList": urls}, "POST")
L("SubmitUrlBatch (%d urls):" % len(urls), "OK" if "__error" not in batch else json.dumps(batch)[:300])

# 4) rank & traffic stats (site-level clicks/impressions over time)
traffic = call("GetRankAndTrafficStats", {"siteUrl": SITE})
L("GetRankAndTrafficStats:", "OK" if "__error" not in traffic else json.dumps(traffic)[:300])

# 5) crawl stats
crawl = call("GetCrawlStats", {"siteUrl": SITE})
L("GetCrawlStats:", "OK" if "__error" not in crawl else json.dumps(crawl)[:300])

out = ["# Bing Webmaster Status (auto)", "", "```", *log, "```", ""]

td = traffic.get("d")
if isinstance(td, list) and td:
    out += ["## Rank & Traffic (recent days)", "| Date | Clicks | Impressions | Avg position |", "|---|---|---|---|"]
    for row in td[-14:]:
        out.append("| %s | %s | %s | %s |" % (
            row.get("Date", "-"), row.get("Clicks", 0), row.get("Impressions", 0),
            row.get("AvgClickPosition") or row.get("AvgImpressionPosition", "-")))
else:
    out += ["## Rank & Traffic", "(no data yet)"]

open(OUT, "w").write("\n".join(out) + "\n")
print("bing report written")
