#!/usr/bin/env python3
import subprocess, re
def gitdate(p):
    try: return subprocess.check_output(["git","log","-1","--format=%cs","--",p]).decode().strip() or "2026-07-31"
    except: return "2026-07-31"
s=open("sitemap.xml").read()
def rep(m):
    loc=m.group(1); path=loc.replace("https://udyoggrowth.com/","")
    f=(path.rstrip("/")+"/index.html") if path else "index.html"
    return f"<url><loc>{loc}</loc><lastmod>{gitdate(f)}</lastmod>"
s=re.sub(r"<url><loc>(.*?)</loc><lastmod>[^<]*</lastmod>", rep, s)
open("sitemap.xml","w").write(s)
print("sitemap lastmod refreshed from git")
