#!/usr/bin/env python3
"""Self-verify the bot as owner of https://udyoggrowth.com/ via Site Verification API (FILE method).
Run 1: fetch token, write file (site deploys it). Run 2+: verify + add site. Idempotent."""
import json, os, sys, glob, urllib.request, urllib.parse

KEY = os.environ.get("GSC_KEY_JSON")
if not KEY: print("no key"); sys.exit(0)
from google.oauth2 import service_account
import google.auth.transport.requests
creds = service_account.Credentials.from_service_account_info(json.loads(KEY),
    scopes=["https://www.googleapis.com/auth/webmasters",
            "https://www.googleapis.com/auth/siteverification"])
creds.refresh(google.auth.transport.requests.Request())
TOK = creds.token
SITE = "https://udyoggrowth.com/"

def call(url, method="GET", body=None):
    req = urllib.request.Request(url, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": "Bearer " + TOK, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = r.read(); return json.loads(d) if d else {}
    except urllib.error.HTTPError as e:
        return {"error": e.code, "detail": e.read().decode()[:400]}

existing = glob.glob("google*.html")
bot_files = [f for f in existing if open(f).read().strip().startswith("google-site-verification:")
             and f in open(f).read()]
if not bot_files:
    t = call("https://www.googleapis.com/siteVerification/v1/token", "POST",
             {"site": {"type": "SITE", "identifier": SITE}, "verificationMethod": "FILE"})
    if "token" in t:
        fn = t["token"]
        open(fn, "w").write("google-site-verification: " + fn)
        print("TOKEN-FILE-CREATED:", fn, "(will verify on next run after deploy)")
    else:
        print("TOKEN-ERROR:", t)
else:
    v = call("https://www.googleapis.com/siteVerification/v1/webResource?verificationMethod=FILE",
             "POST", {"site": {"type": "SITE", "identifier": SITE}})
    print("VERIFY:", "OK" if "id" in v else v)
    a = call("https://www.googleapis.com/webmasters/v3/sites/" +
             urllib.parse.quote(SITE, safe=""), "PUT")
    print("SITES.ADD:", "OK" if "error" not in a else a)
