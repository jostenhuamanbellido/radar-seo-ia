"""Descarga de páginas, robots.txt, sitemap y llms.txt."""
import time
from urllib.parse import urlparse, urlunparse

import requests

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0 Safari/537.36 RadarSEOIA/1.0"
)

# User-agents de los rastreadores de IA (para probar si un firewall/WAF los bloquea)
AI_BOT_UAS = {
    "GPTBot (OpenAI)": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; GPTBot/1.2; +https://openai.com/gptbot)",
    "ClaudeBot (Anthropic)": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)",
    "PerplexityBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
}

session = requests.Session()


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    p = urlparse(url)
    path = p.path or "/"
    return urlunparse((p.scheme, p.netloc.lower(), path, "", p.query, ""))


def root_domain(url: str) -> str:
    host = urlparse(url).netloc.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def origin(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def get(url: str, timeout: int = 25, ua: str = BROWSER_UA) -> dict:
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.6",
    }
    t0 = time.time()
    try:
        r = session.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        return {
            "ok": True,
            "status": r.status_code,
            "url": r.url,
            "content": r.content,
            "text": r.text,
            "headers": {k.lower(): v for k, v in r.headers.items()},
            "elapsed": round(time.time() - t0, 2),
            "redirects": [h.url for h in r.history],
        }
    except requests.RequestException as exc:
        return {
            "ok": False,
            "status": 0,
            "url": url,
            "content": b"",
            "text": "",
            "headers": {},
            "elapsed": round(time.time() - t0, 2),
            "error": str(exc)[:300],
            "redirects": [],
        }


def looks_like_html(resp: dict) -> bool:
    ctype = resp.get("headers", {}).get("content-type", "")
    return "html" in ctype or resp.get("text", "")[:500].lower().lstrip().startswith(("<!doctype", "<html"))
