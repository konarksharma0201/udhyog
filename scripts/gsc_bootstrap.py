#!/usr/bin/env python3
"""Bot self-verifies https://udyoggrowth.com/ (Site Verification API, FILE). Always token-first. Logs to reports/bootstrap.log"""
import json, os, sys, urllib.request, urllib.parse

os.makedirs("reports", exist_ok=True)
LOG = open("reports/bootstrap.log", "a")
def log(*a): print(*a); LOG.write(" ".join(map(str,a))+"\n")

KEY = os.environ.get("GSC_KEY_JSON")
if not KEY: log("no key"); sys.exit(0)
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

t = call("https://www.googleapis.com/siteVerification/v1/token", "POST",
         {"site": {"type": "SITE", "identifier": SITE}, "verificationMethod": "FILE"})
if "token" not in t:
    log("TOKEN-ERROR:", json.dumps(t)[:400]); sys.exit(0)
fn = t["token"]
if not os.path.exists(fn):
    open(fn, "w").write("google-site-verification: " + fn)
    log("TOKEN-FILE-CREATED:", fn, "— verify on next run after deploy")
    sys.exit(0)
v = call("https://www.googleapis.com/siteVerification/v1/webResource?verificationMethod=FILE",
         "POST", {"site": {"type": "SITE", "identifier": SITE}})
log("VERIFY:", "OK" if "id" in v else json.dumps(v)[:400])
a = call("https://www.googleapis.com/webmasters/v3/sites/" + urllib.parse.quote(SITE, safe=""), "PUT")
log("SITES.ADD:", "OK" if "error" not in a else json.dumps(a)[:200])
