#!/usr/bin/env python3
"""Free keyword intelligence for udyoggrowth.com (a no-cost, partial stand-in for paid tools).

Stage A  Autosuggest expansion  : Google + Bing (DuckDuckGo as fallback) suggest endpoints, India locale,
                                  seeds from seo/seeds.json, suffix + question-prefix modifiers, round-robin so
                                  a time budget still gives breadth. Real search suggestions = demand proxy.
Stage B  SERP check             : top suggestions per service are looked up with the existing ddgs/Bing engine to
                                  see who ranks (by DOMAIN TYPE) and our position.
Stage C  Reports                : intel/*.csv  (full detail incl. competitor domains -> workflow ARTIFACT only, never committed)
                                  seo/keyword-intel.json + seo/keyword-intel.md  (sanitised: no competitor names; committed)
Limits  : no search volume or traffic figures exist in free sources; 'score' is a relative suggestion-strength measure.
"""
import os, sys, re, json, csv, time, random, datetime, urllib.parse, urllib.request, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OWN = "udyoggrowth.com"
SUGGEST_BUDGET_MIN = float(os.environ.get("SUGGEST_BUDGET_MIN", "35"))
SERP_BUDGET_MIN = float(os.environ.get("SERP_BUDGET_MIN", "45"))
SERP_MAX = int(os.environ.get("SERP_MAX", "200"))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
STATUS_PRIORITY = {"GAP": 0, "Partial": 1, "Built": 2, "Dedicated": 3}

G_SUFFIX = ["", " fees", " documents", " due date", " penalty", " online", " delhi", " patna", " how to"]
G_PREFIX = ["how to ", "what is ", "can i ", "when is "]
B_SUFFIX = ["", " fees", " documents", " online", " delhi"]
STOP = set("a an the of for in to and or is are how what can i when india online service services registration filing return returns".split())
JUNK = re.compile(r"\b(movie|song|lyrics|download|pdf free|torrent|hindi film|cast|wikipedia)\b", re.I)
QWORDS = ("how", "what", "can", "when", "why", "who", "is", "are", "do", "does", "which", "should")
CITIES = ("delhi", "noida", "gurugram", "gurgaon", "faridabad", "ghaziabad", "patna", "bihar", "haryana", "uttar pradesh", "up")

def toks(s):
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 1}

def http_json(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-IN,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))

def fetch_suggest(engine, q):
    """returns list of suggestion strings (ordered) or raises."""
    qq = urllib.parse.quote(q)
    if engine == "google":
        d = http_json(f"https://suggestqueries.google.com/complete/search?client=firefox&hl=en&gl=in&q={qq}")
    elif engine == "bing":
        d = http_json(f"https://api.bing.com/osjson.aspx?query={qq}&mkt=en-IN")
    else:
        d = http_json(f"https://duckduckgo.com/ac/?q={qq}&kl=in-en&type=list")
    return [s for s in (d[1] if isinstance(d, list) and len(d) > 1 else []) if isinstance(s, str)]

def intent(q):
    ql = q.lower()
    if ql.split()[0] in QWORDS: return "informational"
    if any(c in ql for c in CITIES) or "near me" in ql: return "local"
    if any(w in ql for w in ("consultant", "service", "apply", "online", "registration", "filing", "agent", "near me")): return "transactional"
    return "mixed"

def stage_a(seeds, fetch=fetch_suggest, budget_min=SUGGEST_BUDGET_MIN, sleep=(0.3, 0.7)):
    # build round-robin task list: (round, priority, seed index, engine, query)
    rounds = []
    for ri, suf in enumerate(G_SUFFIX): rounds.append(("google", lambda s, suf=suf: s + suf))
    for pre in G_PREFIX: rounds.append(("google", lambda s, pre=pre: pre + s))
    for suf in B_SUFFIX: rounds.append(("bing", lambda s, suf=suf: s + suf))
    order = sorted(range(len(seeds)), key=lambda i: (STATUS_PRIORITY.get(seeds[i]["status"], 9), i))
    t0 = time.time(); stats = collections.Counter(); consec_fail = collections.Counter(); dead = set()
    hits = collections.defaultdict(lambda: collections.defaultdict(lambda: {"score": 0, "engines": set(), "seeds": set()}))
    done_rounds = 0
    for engine, mk in rounds:
        if engine in dead: continue
        for i in order:
            if (time.time() - t0) / 60 > budget_min: stats["stopped_budget"] += 1; return hits, stats, done_rounds
            sd = seeds[i]; q = mk(sd["seed"]).strip()
            try:
                sug = fetch(engine, q); consec_fail[engine] = 0; stats[f"{engine}_ok"] += 1
            except Exception as e:
                code = getattr(e, "code", None); stats[f"{engine}_fail"] += 1; consec_fail[engine] += 1
                if code in (429, 403): time.sleep(20)
                if consec_fail[engine] >= 25:
                    # try DDG as fallback for the rest of this engine's rounds
                    stats[f"{engine}_dead"] += 1; dead.add(engine); break
                try:
                    sug = fetch("ddg", q); stats["ddg_fallback_ok"] += 1; engine_used = "ddg"
                except Exception:
                    continue
            else:
                engine_used = engine
            sdtok = toks(sd["seed"])
            for rank, s in enumerate(sug, 1):
                s2 = re.sub(r"\s+", " ", s.lower()).strip()
                if len(s2) > 90 or len(s2.split()) < 2 or JUNK.search(s2): continue
                if sdtok and not (sdtok & toks(s2)): continue
                h = hits[sd["id"]][s2]; h["score"] += max(1, 6 - rank); h["engines"].add(engine_used); h["seeds"].add(q)
            time.sleep(random.uniform(*sleep))
        done_rounds += 1
    return hits, stats, done_rounds

def stage_b(seeds_by_id, services, hits, serp_fn, max_q=SERP_MAX, budget_min=SERP_BUDGET_MIN, sleep=(5, 9)):
    pick = []
    for sid in sorted(services, key=lambda s: (STATUS_PRIORITY.get(services[s]["status"], 9), s)):
        top = sorted(hits.get(sid, {}).items(), key=lambda kv: -kv[1]["score"])[:2]
        head = seeds_by_id[sid][0]["seed"].lower()
        qs = [head] + [k for k, _ in top if k != head]
        for q in qs[:2]: pick.append((sid, q))
    pick = pick[:max_q]
    t0 = time.time(); out = []
    for n, (sid, q) in enumerate(pick, 1):
        if (time.time() - t0) / 60 > budget_min: break
        res, status = serp_fn(q)
        out.append({"id": sid, "q": q, "status": status, "results": res})
        print(f"[serp {n}/{len(pick)}] {q} -> {status}", flush=True)
        time.sleep(random.uniform(*sleep))
        if n % 25 == 0: time.sleep(random.uniform(30, 45))
    return out

def main():
    os.makedirs("intel", exist_ok=True)
    today = datetime.date.today().isoformat()
    cfg = json.load(open("seo/seeds.json")); seeds = cfg["seeds"]
    seeds_by_id = collections.defaultdict(list); services = {}
    for s in seeds:
        seeds_by_id[s["id"]].append(s)
        services.setdefault(s["id"], {"service": s["service"], "category": s["category"], "status": s["status"], "our_url": s["our_url"]})
    hits, stats, rounds_done = stage_a(seeds)
    print("stage A", dict(stats), "rounds", rounds_done, flush=True)

    from serp_tracker import run_ddgs, enrich, own_pos
    def serp_fn(q):
        res, status = run_ddgs(q); return enrich(res), status
    serp = stage_b(seeds_by_id, services, hits, serp_fn)

    # ---- full detail (artifact only)
    with open("intel/keywords.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["service_id", "service", "status", "suggestion", "score", "engines", "intent"])
        for sid, d in hits.items():
            for q, h in sorted(d.items(), key=lambda kv: -kv[1]["score"]):
                w.writerow([sid, services[sid]["service"], services[sid]["status"], q, h["score"], "+".join(sorted(h["engines"])), intent(q)])
    dom = collections.defaultdict(lambda: {"queries": set(), "pos": [], "urls": collections.Counter(), "type": ""})
    with open("intel/serp-top10.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["service_id", "query", "position", "domain", "domain_type", "url", "title"])
        for r in serp:
            for x in r["results"][:10]:
                w.writerow([r["id"], r["q"], x["position"], x["domain"], x["domain_type"], x["url"], x["title"]])
                d = dom[x["domain"]]; d["queries"].add(r["q"]); d["pos"].append(x["position"]); d["urls"][x["url"]] += 1; d["type"] = x["domain_type"]
    with open("intel/competitor-domains.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["domain", "type", "queries_in_top10", "avg_position", "top_url"])
        for dname, d in sorted(dom.items(), key=lambda kv: -len(kv[1]["queries"])):
            w.writerow([dname, d["type"], len(d["queries"]), round(sum(d["pos"]) / len(d["pos"]), 1), d["urls"].most_common(1)[0][0]])

    # ---- sanitised output (committed): no competitor domains / names
    by_sid_serp = collections.defaultdict(list)
    for r in serp:
        types = collections.Counter(x["domain_type"] for x in r["results"][:10] if OWN not in x["domain"])
        op, ou = own_pos(r["results"])
        commercial = types.get("national_platform", 0) + types.get("local_or_other", 0) + types.get("listing", 0)
        gn = types.get("government", 0) + types.get("news", 0)
        diff = "authority-heavy" if gn >= 5 else ("crowded-commercial" if commercial >= 7 else "open")
        by_sid_serp[r["id"]].append({"q": r["q"], "status": r["status"], "own_position": op, "types_in_top10": dict(types), "difficulty": diff})
    out = {"generated": today, "stage_a": dict(stats), "rounds_completed": rounds_done, "services": []}
    for sid, sv in sorted(services.items()):
        d = hits.get(sid, {})
        ranked = sorted(d.items(), key=lambda kv: -kv[1]["score"])
        sug = [{"q": q, "score": h["score"], "engines": sorted(h["engines"]), "intent": intent(q)} for q, h in ranked[:25]]
        qs = [{"q": q, "score": h["score"]} for q, h in ranked if q.split()[0] in QWORDS][:10]
        out["services"].append({"id": sid, **sv, "n_suggestions": len(d), "suggestions": sug, "questions": qs, "serp": by_sid_serp.get(sid, [])})
    json.dump(out, open("seo/keyword-intel.json", "w"), ensure_ascii=False, indent=1)

    L = [f"# Keyword intelligence — {today}", "", f"Autosuggest rounds completed: {rounds_done} · requests: {dict(stats)}", "",
         f"Services with suggestions: {sum(1 for s in out['services'] if s['n_suggestions'])} / {len(out['services'])} · total unique suggestions: {sum(s['n_suggestions'] for s in out['services'])} · SERP lookups: {len(serp)}", "",
         "## Where we do not rank yet (SERP-checked queries)", "", "| Service | Query | Top-10 mix | Difficulty |", "|---|---|---|---|"]
    rows = []
    for s in out["services"]:
        for r in s["serp"]:
            if r["status"].startswith("ok") and r["own_position"] is None: rows.append((s["status"], s["service"], r["q"], r["types_in_top10"], r["difficulty"]))
    rows.sort(key=lambda r: (STATUS_PRIORITY.get(r[0], 9), r[1]))
    for st, sv, q, t, d in rows[:80]: L.append(f"| {sv} ({st}) | {q} | {', '.join(f'{k} {v}' for k, v in t.items())} | {d} |")
    L += ["", "## Strongest suggestions for GAP services (build these pages next)", ""]
    for s in out["services"]:
        if s["status"] == "GAP" and s["suggestions"]:
            L.append(f"- **{s['service']}** — " + "; ".join(x["q"] for x in s["suggestions"][:6]))
    open("seo/keyword-intel.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("done", len(serp), "serp lookups")

if __name__ == "__main__":
    main()
