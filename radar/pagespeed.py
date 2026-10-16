"""Google PageSpeed Insights (gratis; la API key es opcional pero evita límites)."""
import requests

from . import config

API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def run(url: str) -> dict:
    params = {"url": url, "strategy": "mobile", "category": "performance", "locale": "es"}
    if config.PAGESPEED_API_KEY:
        params["key"] = config.PAGESPEED_API_KEY
    try:
        r = requests.get(API, params=params, timeout=120)
        if r.status_code != 200:
            msg = r.json().get("error", {}).get("message", r.text[:200]) if r.headers.get("content-type", "").startswith("application/json") else r.text[:200]
            return {"ok": False, "error": f"PageSpeed no disponible (HTTP {r.status_code}): {msg}"}
        lh = r.json().get("lighthouseResult", {})
        audits = lh.get("audits", {})
        perf = lh.get("categories", {}).get("performance", {}).get("score")
        if perf is None:
            return {"ok": False, "error": "PageSpeed no devolvió puntaje."}
        def dv(k):
            return audits.get(k, {}).get("displayValue", "?")
        return {
            "ok": True,
            "performance": round(perf * 100),
            "lcp": dv("largest-contentful-paint"),
            "cls": dv("cumulative-layout-shift"),
            "tbt": dv("total-blocking-time"),
            "fcp": dv("first-contentful-paint"),
            "si": dv("speed-index"),
        }
    except requests.RequestException as exc:
        return {"ok": False, "error": f"PageSpeed no respondió: {str(exc)[:150]}"}
