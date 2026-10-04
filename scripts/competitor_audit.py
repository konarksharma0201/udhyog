#!/usr/bin/env python3
"""Competitor audit + keyword universe for udyoggrowth.com.

Runs after serp_tracker.py in the daily workflow.
1. Reads reports/serp/latest.json → top-10 URLs per query (competitors only).
2. Fetches each URL (robots.txt respected, 1 fetch/domain/sec), extracts: title, H1, H2/H3 outline,
   FAQ questions (details/summary, FAQPage JSON-LD, question-like headings), schema types, word count,
   ₹ figures, phone/WhatsApp CTA, visible dates, city/locality mentions. Cached per URL per day.
3. Compares, per keyword group, competitor heading/FAQ topics against OUR page for that group:
   topics present on >=2 competitor pages but absent from ours => gap.
4. Collects autosuggest expansions (DuckDuckGo suggestions via ddgs) for every base query → keyword universe,
   diffed day over day.
Outputs: reports/competitors/<date>/pages.json, reports/competitor-gaps.md, reports/keyword-universe.json
"""
import json, os, re, time, datetime, socket, urllib.parse, urllib.request, urllib.robotparser, html as H
socket.setdefaulttimeout(15)
from collections import defaultdict, Counter

try:
    from bs4 import BeautifulSoup
except ImportError:
    raise SystemExit("pip install beautifulsoup4 lxml")

OWN = "udyoggrowth.com"
UA = "Mozilla/5.0 (compatible; UdyogGrowthAudit/1.0; +https://udyoggrowth.com)"
TODAY = datetime.date.today().isoformat()
BUDGET_MIN = int(os.environ.get("AUDIT_BUDGET_MIN", "30"))
MAX_FETCH = int(os.environ.get("AUDIT_MAX_FETCH", "220"))
T0 = time.time()
OUT = f"reports/competitors/{TODAY}"
SKIP_DOM = ("justdial.", "indiamart.", "sulekha.", "tradeindia.", "facebook.", "linkedin.", "youtube.", "instagram.", ".gov.in", ".nic.in", "wikipedia.")
BOILER = {"recent posts","recent comments","archives","categories","quick links","get touch","call now","contact us","frequently asked questions","faqs","faq","need help","quick enquiry","leave reply","share","related posts","follow us","our services","why choose","about us","testimonials","get quote","free consultation","request callback","book consultation","table contents","latest posts","popular posts","tags","meta","subscribe","newsletter","talk expert","enquire now","apply now","get started","our clients","client reviews"}
STOP = set("the a an and or of for in to with your you we our is are on at by from how what which who why when do does can i my it this that be as not all any into about more best top near me services service consultant consultants registration online india delhi noida gurugram gurgaon faridabad ghaziabad patna bihar ncr".split())

def norm_topic(t: str) -> str:
    t = H.unescape(t).lower()
    t = re.sub(r"[^a-z0-9₹%\s/-]", " ", t)
    words = [w for w in t.split() if w not in STOP and len(w) > 2]
    return " ".join(words[:8])

_robots = {}
def allowed(url: str) -> bool:
    p = urllib.parse.urlsplit(url); base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(base + "/robots.txt", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=8) as r:
                rp.parse(r.read(200_000).decode("utf-8", "ignore").splitlines())
            _robots[base] = rp
        except Exception:
            _robots[base] = None
    rp = _robots[base]
    return True if rp is None else rp.can_fetch(UA, url)

_last = defaultdict(float)
def fetch(url: str, timeout=20):
    host = urllib.parse.urlsplit(url).netloc
    wait = 1.0 - (time.time() - _last[host])
    if wait > 0: time.sleep(wait)
    _last[host] = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-IN,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        if "text/html" not in r.headers.get("Content-Type", ""): return None
        return r.read(2_000_000).decode(r.headers.get_content_charset() or "utf-8", "ignore")

def extract(url: str, html_: str) -> dict:
    s = BeautifulSoup(html_, "lxml")
    ld = [sc for sc in s.find_all("script", type="application/ld+json")]
    for t in s(["script", "style", "noscript", "nav", "header", "footer", "aside", "form", "iframe", "svg"]):
        if t in ld: continue
        t.decompose()
    for t in s.select('[class*="sidebar"],[class*="widget"],[class*="footer"],[class*="header"],[class*="menu"],[class*="breadcrumb"],[id*="sidebar"],[id*="footer"],[id*="header"],[id*="comments"]'):
        t.decompose()
    text = s.get_text(" ", strip=True)
    schema_types, faq_ld = set(), []
    for sc in s.find_all("script", type="application/ld+json"):
        try:
            d = json.loads(sc.string or "")
        except Exception:
            continue
        stack = [d]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                t = x.get("@type")
                if t: schema_types.update(t if isinstance(t, list) else [t])
                if x.get("@type") == "Question" and x.get("name"): faq_ld.append(x["name"])
                stack.extend(x.values())
            elif isinstance(x, list): stack.extend(x)
    heads = [(h.name, h.get_text(" ", strip=True)) for h in s.find_all(["h1", "h2", "h3"])]
    faq_vis = [x.get_text(" ", strip=True) for x in s.find_all("summary")]
    faq_q = [t for _, t in heads if t.strip().endswith("?")]
    faqs = list(dict.fromkeys(faq_ld + faq_vis + faq_q))
    rupees = re.findall(r"₹\s?[\d,]+(?:\.\d+)?(?:\s?(?:lakh|crore|cr|lac|l))?", text)[:20]
    dates = re.findall(r"(?:updated|reviewed|published)[^.]{0,25}?(20\d\d)", text, re.I)[:3]
    phones = len(re.findall(r"(?:\+91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}", text))
    local = re.findall(r"\b(sector\s?\d+|udyog vihar|cyber city|manesar|okhla|naraina|bawana|connaught place|karol bagh|nehru place|sahibabad|ecotech|boring road|fraser road|patliputra|fatuha|bihta|nit\b)", text, re.I)
    return dict(url=url, title=(s.title.get_text(strip=True) if s.title else ""), words=len(text.split()),
                h1=[t for n, t in heads if n == "h1"], outline=[(n, t) for n, t in heads if n != "h1"][:60],
                faqs=faqs[:40], faq_count=len(faqs), schema=sorted(schema_types), faqpage=("FAQPage" in schema_types),
                rupees=rupees, dates=dates, phone_mentions=phones, whatsapp=("wa.me" in html_ or "whatsapp" in html_.lower()),
                localities=sorted(set(l.lower() for l in local))[:25], fee_table=bool(s.find("table")) and ("₹" in text))

def own_topics(own_url: str):
    path = own_url.strip("/") + "/index.html"
    if not os.path.exists(path): return set(), set()
    s = BeautifulSoup(open(path, encoding="utf-8").read(), "lxml")
    heads = {norm_topic(h.get_text(" ", strip=True)) for h in s.find_all(["h2", "h3"])}
    faqs = {norm_topic(x.get_text(" ", strip=True)) for x in s.find_all("summary")}
    body = s.get_text(" ", strip=True).lower()
    return heads | faqs, body

def overlap(topic: str, body: str) -> bool:
    words = [w for w in topic.split() if len(w) > 3]
    if not words: return True
    hits = sum(1 for w in words if w in body)
    return hits / len(words) >= 0.6

def main():
    os.makedirs(OUT, exist_ok=True)
    serp = json.load(open("reports/serp/latest.json"))
    # ---- keyword universe via autosuggest (runs first; cheap) ----
    uni_path = "reports/keyword-universe.json"
    uni = json.load(open(uni_path)) if os.path.exists(uni_path) else {"keywords": {}, "history": []}
    new_kw = []
    def bing_suggest(q):
        u = "https://api.bing.com/osjson.aspx?market=en-IN&query=" + urllib.parse.quote(q)
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))[1]
    bases = sorted({q["query"] for q in serp["queries"] if not q.get("city")} | {q["query"] for q in serp["queries"] if q.get("city") == "delhi"})
    ts = time.time()
    for b in bases[:80]:
        if time.time() - ts > 8 * 60: break
        sugg = []
        try:
            sugg = bing_suggest(b)
        except Exception:
            try:
                from ddgs import DDGS
                sugg = [x.get("phrase", "") for x in DDGS().suggestions(b, region="in-en")]
            except Exception:
                sugg = []
        for k in sugg:
            k = (k or "").strip().lower()
            if k and k != b.lower() and k not in uni["keywords"]:
                uni["keywords"][k] = {"first_seen": TODAY, "from": b}; new_kw.append(k)
        time.sleep(1.0)
    uni["history"].append({"date": TODAY, "new": len(new_kw), "total": len(uni["keywords"])})
    json.dump(uni, open(uni_path, "w"), indent=1, ensure_ascii=False)
    # ---- 1. collect URLs per group ----
    OWN_MAP = {"gst-notice":"/gst-notice-reply/","gst-consultant":"/gst-notice-reply/","gst-registration":"/gst-registration-rule-14a/","fssai":"/fssai-license-consultant/","fssai-license":"/fssai-license-consultant/","company-registration":"/company-registration-delhi/","shop-act":"/labour-code-compliance-epf-esic/","epf-esic":"/labour-code-compliance-epf-esic/","trademark":"/trademark-registration-delhi/","income-tax":"/income-tax-notice-reply/","itr":"/income-tax-notice-reply/","pollution-noc":"/pollution-noc-environmental-clearance/","gem":"/gem-registration-tender-bidding/","msme":"/msme-schemes/","udyam":"/msme-schemes/","pmfme":"/pmfme-subsidy-consultant/","iec":"/import-export-iec-dgft-consultant/","ngo":"/ngo-trust-12a-80g-fcra-registration/","clu":"/land-conversion-clu-consultant/","liquor":"/liquor-excise-license-delhi/","solar":"/solar-subsidy-pm-surya-ghar/","biada":"/biada-land-allotment-bihar-industrial-policy/","school":"/school-affiliation-consultant/","tender":"/bihar-government-tenders/"}
    by_group = defaultdict(lambda: dict(urls=Counter(), own=None, queries=[]))
    for q in serp["queries"]:
        g = q["keyword_group"] if q["keyword_group"] != "page" else q["query_id"]
        by_group[g]["queries"].append(q["query"])
        if q.get("own_url"): by_group[g]["own"] = q["own_url"]
        elif not by_group[g]["own"]:
            for k, v in OWN_MAP.items():
                if k in g: by_group[g]["own"] = v; break
        for r in q["results"][:10]:
            if OWN in r["domain"] or any(d in r["domain"] for d in SKIP_DOM): continue
            by_group[g]["urls"][r["url"]] += 1
    # ---- 2. fetch + extract (cap per group) ----
    cache_path = f"{OUT}/pages.json"
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    fetched = 0
    for g, info in sorted(by_group.items(), key=lambda kv: (kv[0].startswith("page__"), kv[0])):
        for url, _ in info["urls"].most_common(6):
            if url in cache: continue
            if fetched >= MAX_FETCH or (time.time() - T0) / 60 > BUDGET_MIN: break
            if not allowed(url): cache[url] = {"url": url, "blocked": "robots"}; continue
            try:
                h = fetch(url)
                cache[url] = extract(url, h) if h else {"url": url, "blocked": "non-html"}
            except Exception as e:
                cache[url] = {"url": url, "blocked": type(e).__name__}
            fetched += 1
            if fetched % 25 == 0:
                json.dump(cache, open(cache_path, "w"), indent=1, ensure_ascii=False)
    json.dump(cache, open(cache_path, "w"), indent=1, ensure_ascii=False)
    # ---- 3. gap analysis ----
    L = [f"# Competitor content gaps — {TODAY}", "", f"Groups: {len(by_group)} · competitor pages audited: {sum(1 for v in cache.values() if 'blocked' not in v)} · blocked/unreachable: {sum(1 for v in cache.values() if 'blocked' in v)}", ""]
    summary_rows = []
    for g, info in sorted(by_group.items()):
        pages = [cache[u] for u, _ in info["urls"].most_common(10) if u in cache and "blocked" not in cache[u]]
        if not pages: continue
        own_t, own_body = own_topics(info["own"]) if info["own"] else (set(), "")
        topic_sources = defaultdict(set)
        for p in pages:
            for _, t in p["outline"]:
                nt = norm_topic(t)
                if len(nt) >= 8: topic_sources[nt].add(p["url"])
            for fq in p["faqs"]:
                nt = norm_topic(fq)
                if len(nt) >= 8: topic_sources["Q: " + nt].add(p["url"])
        def boiler(t):
            core = t.replace("Q: ", "")
            return core in BOILER or any(core.startswith(b) or core.endswith(b) for b in BOILER) or len(core.split()) < 2
        gaps = [(t, len(srcs)) for t, srcs in topic_sources.items() if len(srcs) >= 2 and not boiler(t) and not overlap(t.replace("Q: ", ""), own_body)]
        gaps.sort(key=lambda x: -x[1])
        stats = dict(n=len(pages), avg_words=int(sum(p["words"] for p in pages) / len(pages)), faqpage=sum(p["faqpage"] for p in pages),
                     fee_table=sum(p["fee_table"] for p in pages), dated=sum(1 for p in pages if p["dates"]), whatsapp=sum(p["whatsapp"] for p in pages),
                     avg_faq=round(sum(p["faq_count"] for p in pages) / len(pages), 1))
        summary_rows.append((g, info["own"] or "-", stats, len(gaps)))
        L += [f"## {g}", f"Our page: `{info['own'] or '-'}` · competitors audited: {stats['n']} · avg words {stats['avg_words']} · with FAQPage {stats['faqpage']}/{stats['n']} · fee table {stats['fee_table']}/{stats['n']} · dated {stats['dated']}/{stats['n']} · WhatsApp {stats['whatsapp']}/{stats['n']} · avg FAQs {stats['avg_faq']}", ""]
        L += ["**Competitor pages (by frequency in top-10):**"] + [f"- {p['url']} — {p['words']}w, {p['faq_count']} FAQs{', FAQPage' if p['faqpage'] else ''}{', fee table' if p['fee_table'] else ''}, schema: {', '.join(p['schema'][:5]) or '-'}" for p in pages] + [""]
        if gaps:
            L += ["**Topics on 2+ competitor pages that our page does not cover (add or answer):**"] + [f"- ({n}) {t}" for t, n in gaps[:25]] + [""]
        else:
            L += ["**No multi-competitor topic gaps detected against our page.**", ""]
    L += ["## Keyword universe (autosuggest)", f"Total suggested keywords tracked: {len(uni['keywords'])} · new today: {len(new_kw)}", ""] + [f"- {k}" for k in new_kw[:60]] + [""]
    # ---- summary table at top ----
    tbl = ["| Group | Our page | Comp. pages | Avg words | FAQPage | Fee table | Dated | Gaps |", "|---|---|---|---|---|---|---|---|"]
    for g, own, st, ng in sorted(summary_rows, key=lambda x: -x[3]):
        tbl.append(f"| {g} | {own} | {st['n']} | {st['avg_words']} | {st['faqpage']} | {st['fee_table']} | {st['dated']} | {ng} |")
    L = L[:4] + ["## Summary (sorted by gaps)"] + tbl + [""] + L[4:]
    open("reports/competitor-gaps.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("groups", len(by_group), "fetched", fetched, "cached", len(cache), "new keywords", len(new_kw))

if __name__ == "__main__":
    main()
