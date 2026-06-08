"""
Cronometer nutrition fetch — direct API path (no browser).

Cronometer has no public API, but its own web app talks to the backend over a
small, stable set of HTTP calls. We make the *same* calls the website makes:

    1. GET  /login/                  -> scrape the `anticsrf` token
    2. POST /login                   -> establish the session (`sesnonce` cookie)
    3. GWT-RPC authenticate(tz)      -> the numeric user id
    4. GWT-RPC generateAuthorizationToken(...) -> a short-lived export token
    5. GET  /export?nonce=<token>&generate=dailySummary&start=..&end=..  -> CSV

Because this is plain HTTP that mirrors the app, there is no browser to
fingerprint and nothing for bot-detection to flag — it is far more reliable than
driving the GWT diary UI with Playwright (the old approach, kept as a fallback in
`cronometer_client.py`).

The only brittle part is GWT's serialization ids, which change when Cronometer
ships a new build. They are pinned in CONFIG below AND **self-healed at runtime**:
if the token call fails with an `IncompatibleRemoteServiceException`, we re-read
the live `AuthScope` id out of Cronometer's compiled JS and retry once.

Output matches `cronometer_client.fetch_daily_nutrition`: a list of daily rows
    [{"date": "YYYY-MM-DD", "calories": float|None, "protein": ..., ...}, ...]
parsed by the already-unit-tested `parse_daily_nutrition_csv`.
"""
import re
import http.cookiejar
import datetime as _dt
import urllib.parse
import urllib.request
import urllib.error
import logging

from cronometer_client import parse_daily_nutrition_csv

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# CONFIG — pinned GWT constants. If Cronometer ships a new build and the sync
# starts failing on the token step, these are what to refresh; the AuthScope id
# is also recovered automatically (see _discover_authscope).
# --------------------------------------------------------------------------
BASE = "https://cronometer.com"
LOGIN_PAGE = BASE + "/login/"
LOGIN_POST = BASE + "/login"
GWT_URL = BASE + "/cronometer/app"
MODULE_BASE = BASE + "/cronometer/"
EXPORT_URL = BASE + "/export"

GWT_POLICY = "2D6A926E3729946302DC68073CB0D550"   # RPC serialization policy hash
GWT_PERMUTATION = "7B121DC5483BF272B1BC1916DA9FA963"
SERVICE = "com.cronometer.shared.rpc.CronometerService"
INTEGER_TYPE = "java.lang.Integer/3438268394"
STRING_TYPE = "java.lang.String/2004016611"
# AuthScope enum — package + serialization id; auto-refreshed if it drifts.
AUTHSCOPE_TYPE = "com.cronometer.shared.user.AuthScope/2065601159"
AUTHSCOPE_ORDINAL = 2          # the scope value the export token needs
TOKEN_TTL_SECONDS = 3600

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
TIMEOUT = 45


class CronometerError(RuntimeError):
    """Readable failure the dashboard can show the coach directly."""


# --------------------------------------------------------------------------
# Low-level HTTP (cookie-jar session, no third-party deps)
# --------------------------------------------------------------------------
def _new_opener():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    return opener, cj


def _request(opener, url, data=None, headers=None):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    if isinstance(data, str):
        data = data.encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=h)
    return opener.open(req, timeout=TIMEOUT)


def _gwt(opener, body):
    """One GWT-RPC POST. Returns the response text (starts with //OK or //EX)."""
    resp = _request(opener, GWT_URL, data=body, headers={
        "Content-Type": "text/x-gwt-rpc; charset=UTF-8",
        "x-gwt-module-base": MODULE_BASE,
        "x-gwt-permutation": GWT_PERMUTATION,
    })
    return resp.read().decode("utf-8", "replace")


# --------------------------------------------------------------------------
# Steps
# --------------------------------------------------------------------------
def _login(opener, cj, email, password):
    """Form login. Returns the `sesnonce` value or raises CronometerError."""
    try:
        html = _request(opener, LOGIN_PAGE).read().decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        raise CronometerError(f"Could not reach Cronometer: {exc}") from exc

    m = (re.search(r'name="anticsrf"[^>]*value="([^"]+)"', html)
         or re.search(r'value="([^"]+)"[^>]*name="anticsrf"', html))
    if not m:
        raise CronometerError("Cronometer's login page changed (no anticsrf "
                              "token). The sync needs updating.")
    payload = urllib.parse.urlencode({
        "anticsrf": m.group(1), "username": email, "password": password,
    })
    body = _request(opener, LOGIN_POST, data=payload).read().decode("utf-8", "replace")

    if '"error"' in body:
        err = re.search(r'"error"\s*:\s*"([^"]*)"', body)
        msg = err.group(1) if err else "login failed"
        if "TOTP" in msg or "2FA" in msg.upper():
            raise CronometerError(
                "This Cronometer account has 2-factor authentication enabled, "
                "which the automated sync can't pass. Turn off 2FA for this "
                "account (Account → Settings → Security) to use sync.")
        raise CronometerError(f"Cronometer login failed: {msg} "
                              "(check the saved email/password).")

    nonce = next((c.value for c in cj if c.name == "sesnonce"), None)
    if not nonce:
        raise CronometerError("Cronometer login did not establish a session "
                              "(no sesnonce). Check the saved email/password.")
    return nonce


def _authenticate(opener):
    """GWT authenticate -> numeric user id (uses the session cookie)."""
    body = (f"7|0|5|{MODULE_BASE}|{GWT_POLICY}|{SERVICE}|authenticate|"
            f"{INTEGER_TYPE}|1|2|3|4|1|5|5|-300|")
    resp = _gwt(opener, body)
    ids = re.findall(r"OK\[(\d+),", resp)
    if not ids:
        raise CronometerError(f"Cronometer authenticate failed: {resp[:160]}")
    return ids[0]


def _generate_token(opener, nonce, userid):
    """GWT generateAuthorizationToken -> short-lived export token (with retry
    that re-discovers the AuthScope id if Cronometer drifted it)."""
    global AUTHSCOPE_TYPE

    def _call():
        body = (f"7|0|8|{MODULE_BASE}|{GWT_POLICY}|{SERVICE}|"
                f"generateAuthorizationToken|{STRING_TYPE}|I|{AUTHSCOPE_TYPE}|"
                f"{nonce}|1|2|3|4|4|5|6|6|7|8|{userid}|{TOKEN_TTL_SECONDS}|"
                f"7|{AUTHSCOPE_ORDINAL}|")
        return _gwt(opener, body)

    resp = _call()
    if not resp.startswith("//OK"):
        # Self-heal: AuthScope serialization id likely drifted on a new build.
        new_type = _discover_authscope(opener)
        if new_type and new_type != AUTHSCOPE_TYPE:
            logger.warning("Cronometer AuthScope drifted; using %s", new_type)
            AUTHSCOPE_TYPE = new_type
            resp = _call()
    if not resp.startswith("//OK"):
        raise CronometerError(f"Cronometer token request failed: {resp[:160]}")
    m = re.search(r'"([^"]+)"', resp)
    if not m:
        raise CronometerError("Cronometer returned an empty export token.")
    return m.group(1)


def _discover_authscope(opener):
    """Read the current `com.cronometer.shared.user.AuthScope/<id>` from the
    live compiled GWT JS, so the token call self-heals across Cronometer builds."""
    try:
        nocache = _request(
            opener, MODULE_BASE + "cronometer.nocache.js"
        ).read().decode("utf-8", "replace")
        for strong in set(re.findall(r"[0-9A-F]{30,32}", nocache)):
            try:
                js = _request(
                    opener, f"{MODULE_BASE}{strong}.cache.js"
                ).read().decode("utf-8", "replace")
            except urllib.error.URLError:
                continue
            m = re.search(r"(com\.cronometer\.[\w.]*AuthScope/\d+)", js)
            if m:
                return m.group(1)
    except urllib.error.URLError as exc:
        logger.warning("AuthScope discovery failed: %s", exc)
    return None


def _export_csv(opener, token, start, end):
    url = (f"{EXPORT_URL}?nonce={urllib.parse.quote(token)}&generate=dailySummary"
           f"&start={start.isoformat()}&end={end.isoformat()}")
    try:
        return _request(opener, url).read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise CronometerError(
            f"Cronometer export was rejected (HTTP {exc.code}). The export "
            "token may have expired — try the sync again.") from exc


# --------------------------------------------------------------------------
# Public entry point — same shape as cronometer_client.fetch_daily_nutrition
# --------------------------------------------------------------------------
def fetch_daily_nutrition(email, password, days=14, **_ignored):
    """
    Log in to Cronometer and return parsed daily-nutrition rows for the last
    `days` days. Raises CronometerError with a coach-readable message on failure.
    Extra kwargs (e.g. `headless`) are accepted and ignored for drop-in
    compatibility with the old Playwright client.
    """
    if not email or not password:
        raise CronometerError("Missing Cronometer email or password.")

    end = _dt.date.today()
    start = end - _dt.timedelta(days=days)

    opener, cj = _new_opener()
    nonce = _login(opener, cj, email, password)
    userid = _authenticate(opener)
    # authenticate can rotate the session nonce
    nonce = next((c.value for c in cj if c.name == "sesnonce"), nonce)
    token = _generate_token(opener, nonce, userid)
    csv_text = _export_csv(opener, token, start, end)

    rows = parse_daily_nutrition_csv(csv_text)
    if not rows:
        raise CronometerError("Logged in, but the Cronometer export had no "
                              "rows for that date range.")
    return rows


if __name__ == "__main__":  # manual self-test against the saved account
    import sys
    import secrets_store
    name = sys.argv[1] if len(sys.argv) > 1 else "Ceasar Attar"
    creds = secrets_store.get_credentials(name)
    if not creds:
        print("No saved credentials for", name); raise SystemExit(1)
    out = fetch_daily_nutrition(creds["email"], creds["password"], days=30)
    print(f"OK — {len(out)} day(s) parsed.")
    for r in out[-5:]:
        print(f"  {r['date']}  calories={r['calories']}  protein={r['protein']}")
