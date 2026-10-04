#!/usr/bin/env python3
"""Daily SERP tracker for udyoggrowth.com.

Breadth engine : ddgs (Bing backend, region in-en) for every query in seo/serp-queries.json
Panel engine   : SerpApi (real Google India + People-also-ask) for up to PANEL_SIZE queries/day,
                 only when SERPAPI_KEY is set. Free plan = 250/month => 8/day fits.
Outputs        : reports/serp/<date>.json, reports/serp/latest.json, reports/serp/diff-<date>.json,
                 reports/serp-status.md (human summary, committed by the workflow).
"""
import json, os, random, re, sys, time, datetime, urllib.parse, urllib.request, signal

OWN_HOST = "udyoggrowth.com"
QFILE = "seo/serp-queries.json"
OUT = "reports/serp"
PANEL_SIZE = int(os.environ.get("SERP_PANEL_SIZE", "8"))
SLEEP = (5, 9)         # jittered seconds between queries
BATCH = 25             # queries per batch
BATCH_SLEEP = (30, 45)
BUDGET_MIN = int(os.environ.get("SERP_BUDGET_MIN", "95"))   # stop issuing queries after this many minutes
QUERY_TIMEOUT = 25     # hard per-call timeout (seconds)

class _TO(Exception): pass
def _alarm(signum, frame): raise _TO()
def with_timeout(fn, *a, **k):
    signal.signal(signal.SIGALRM, _alarm); signal.alarm(QUERY_TIMEOUT)
    try: return fn(*a, **k)
    finally: signal.alarm(0)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"

TRACK = re.compile(r"(utm_[a-z]+|fbclid|gclid|ref|srsltid)=[^&]*&?", re.I)
def norm(u: str) -> str:
    try:
        p = urllib.parse.urlsplit(u.strip())
        host = p.netloc.lower().replace("www.", "")
        path = p.path.rstrip("/") or "/"
        q = TRACK.sub("", p.query).strip("&")
        return host + path + (("?" + q) if q else "")
    except Exception:
        return u

def domain_type(host: str) -> str:
    h = host.lower()
    if any(x in h for x in [".gov.in", ".nic.in", "mca.gov", "gst.gov"]): return "government"
    if any(x in h for x in ["justdial", "indiamart", "sulekha", "tradeindia", "yelp"]): return "listing"
    if any(x in h for x in ["indiafilings", "vakilsearch", "cleartax", "legalwiz", "corpseed", "razorpay", "setindiabiz", "registerkaro", "corpbiz", "enterslice"]): return "national_platform"
    if any(x in h for x in ["times", "hindustan", "ndtv", "business-standard", "economictimes", "pib.gov"]): return "news"
    return "local_or_other"

def run_ddgs(query: str, region="in-en", backend="bing"):
    from ddgs import DDGS
    last = None
    for attempt, (wait, be) in enumerate(((0, backend), (15, "duckduckgo"))):
        if wait: time.sleep(wait)
        try:
            res = with_timeout(lambda: DDGS(timeout=15).text(query, region=region, backend=be, max_results=10))
            if res:
                return [dict(position=i, url=r.get("href",""), title=r.get("title",""), snippet=r.get("body","")) for i, r in enumerate(res, 1)], ("ok" if be == backend else "ok-fallback")
            last = "empty"
        except _TO:
            last = "timeout"
        except Exception as e:
            last = type(e).__name__
    return [], f"failed:{last}"

def run_serpapi(query: str, location: str):
    key = os.environ.get("SERPAPI_KEY")
    if not key: return [], [], "skipped"
    params = {"engine":"google","q":query,"gl":"in","hl":"en","google_domain":"google.co.in","num":"10","api_key":key}
    if location: params["location"] = location
    url = "https://serpapi.com/search.json?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
            d = json.load(r)
        org = [dict(position=o.get("position", i), url=o.get("link",""), title=o.get("title",""), snippet=o.get("snippet","")) for i, o in enumerate(d.get("organic_results", []), 1)]
        paa = [x.get("question","") for x in d.get("related_questions", [])]
        return org, paa, "ok" if org else "empty"
    except Exception as e:
        return [], [], f"failed:{type(e).__name__}"

def enrich(results):
    for r in results:
        r["url_normalized"] = norm(r["url"])
        r["domain"] = r["url_normalized"].split("/")[0]
        r["domain_type"] = domain_type(r["domain"])
    return results

def own_pos(results):
    for r in results:
        if OWN_HOST in r["domain"]:
            return r["position"], r["url"]
    return None, None

CITY_LOC = {"delhi":"Delhi, India","noida":"Noida, Uttar Pradesh, India","gurugram":"Gurugram, Haryana, India",
            "faridabad":"Faridabad, Haryana, India","ghaziabad":"Ghaziabad, Uttar Pradesh, India","patna":"Patna, Bihar, India","":""}

def main():
    os.makedirs(OUT, exist_ok=True)
    today = datetime.date.today().isoformat()
    cfg = json.load(open(QFILE))
    queries = cfg["queries"][:]
    random.shuffle(queries)
    run = {"run_id": f"{today}_bing", "run_date_ist": today, "engine": "bing", "tool": "ddgs", "locale": {"region": "in-en"}, "queries": []}
    panel_ids = [q["query_id"] for q in cfg["queries"] if q.get("own_url")][:]
    random.Random(today).shuffle(panel_ids)           # rotate panel daily, deterministic per day
    panel_ids = set(panel_ids[:PANEL_SIZE]) if os.environ.get("SERPAPI_KEY") else set()

    t0 = time.time()
    def save_partial():
        json.dump(run, open(f"{OUT}/{today}.json","w"), indent=1)
    for i, q in enumerate(queries, 1):
        if (time.time() - t0) / 60 > BUDGET_MIN:
            run["queries"].append({**q, "status": "skipped:budget", "fetched_at": None, "own_best_position": None, "own_url_found": None, "results": []}); continue
        res, status = run_ddgs(q["query"])
        res = enrich(res)
        pos, url = own_pos(res)
        entry = {**q, "status": status, "fetched_at": datetime.datetime.utcnow().isoformat()+"Z", "own_best_position": pos, "own_url_found": url, "results": res}
        if q["query_id"] in panel_ids:
            g, paa, gs = run_serpapi(q["query"], CITY_LOC.get(q.get("city",""), ""))
            g = enrich(g); gp, gu = own_pos(g)
            entry["google"] = {"status": gs, "own_best_position": gp, "own_url_found": gu, "results": g, "paa": paa}
        run["queries"].append(entry)
        print(f"[{i}/{len(queries)}] {q['query']} -> {status} own={pos}", flush=True)
        if i % 10 == 0: save_partial()
        time.sleep(random.uniform(*SLEEP))
        if i % BATCH == 0 and i < len(queries): time.sleep(random.uniform(*BATCH_SLEEP))

    json.dump(run, open(f"{OUT}/{today}.json","w"), indent=1)
    # diff vs previous
    prev_path = f"{OUT}/latest.json"; prev = json.load(open(prev_path)) if os.path.exists(prev_path) else None
    json.dump(run, open(prev_path,"w"), indent=1)
    diff = {"date": today, "changes": []}
    if prev:
        pm = {q["query_id"]: q for q in prev["queries"]}
        for q in run["queries"]:
            p = pm.get(q["query_id"])
            if not p: continue
            a, b = p.get("own_best_position"), q.get("own_best_position")
            if a != b: diff["changes"].append({"query_id": q["query_id"], "query": q["query"], "from": a, "to": b})
            old = {r["url_normalized"] for r in p["results"][:10]}; new = {r["url_normalized"] for r in q["results"][:10]}
            ent, drop = sorted(new - old), sorted(old - new)
            if ent or drop: diff["changes"].append({"query_id": q["query_id"], "new_entrants": ent, "dropouts": drop})
    json.dump(diff, open(f"{OUT}/diff-{today}.json","w"), indent=1)

    # Markdown summary
    ok = sum(1 for q in run["queries"] if q["status"].startswith("ok"))
    ranked = [(q["query"], q["own_best_position"]) for q in run["queries"] if q["own_best_position"]]
    from collections import Counter
    comp = Counter(r["domain"] for q in run["queries"] for r in q["results"][:5] if OWN_HOST not in r["domain"])
    skipped = sum(1 for q in run["queries"] if q["status"].startswith("skipped"))
    L = [f"# SERP status — {today}", "", f"Engine: Bing (via ddgs, region in-en; DDG fallback) · queries: {len(run['queries'])} · ok: {ok} · skipped (budget): {skipped} · own-domain in top10: {len(ranked)} · runtime {int((time.time()-t0)/60)} min", ""]
    if ranked:
        L += ["## Where udyoggrowth.com appears (Bing top-10)", "| Query | Position |", "|---|---|"] + [f"| {q} | {p} |" for q, p in sorted(ranked, key=lambda x: x[1])] + [""]
    L += ["## Most frequent competing domains (top-5 slots)", "| Domain | Appearances |", "|---|---|"] + [f"| {d} | {n} |" for d, n in comp.most_common(20)] + [""]
    gq = [q for q in run["queries"] if "google" in q]
    if gq:
        L += [f"## Google India panel (SerpApi, {len(gq)} queries today)", "| Query | Own pos | PAA |", "|---|---|---|"]
        for q in gq:
            L.append(f"| {q['query']} | {q['google'].get('own_best_position') or '-'} | {' / '.join(q['google'].get('paa', [])[:4])} |")
        L.append("")
    if diff["changes"]:
        L += ["## Changes vs previous run", ""] + [f"- `{c['query_id']}`: " + (f"own {c['from']} → {c['to']}" if "to" in c else f"+{len(c.get('new_entrants',[]))} new / -{len(c.get('dropouts',[]))} dropped") for c in diff["changes"][:40]]
    open("reports/serp-status.md","w").write("\n".join(L)+"\n")
    print("done:", ok, "ok of", len(run["queries"]))

if __name__ == "__main__":
    main()
