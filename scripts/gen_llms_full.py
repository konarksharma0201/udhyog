#!/usr/bin/env python3
"""Regenerate llms-full.txt from the live HTML pages (sitemap order), so the
AI-crawler mirror never drifts from the actual page content again.
Run after any content edit: python3 scripts/gen_llms_full.py"""
import re, html

def visible_text(path):
    s = open(path, encoding="utf-8").read()
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()

urls = re.findall(r"<loc>(https://udyoggrowth\.com[^<]*)</loc>", open("sitemap.xml").read())
out = ["# Udyog Growth — full site content for AI assistants",
       "# Regenerated automatically from live pages. Index: https://udyoggrowth.com/llms.txt", ""]
for u in urls:
    slug = u.replace("https://udyoggrowth.com/", "").strip("/")
    path = (slug + "/index.html") if slug else "index.html"
    out.append(f"## {u}")
    out.append(visible_text(path))
    out.append("")
open("llms-full.txt", "w", encoding="utf-8").write("\n".join(out))
print(f"llms-full.txt regenerated: {len(urls)} pages")
