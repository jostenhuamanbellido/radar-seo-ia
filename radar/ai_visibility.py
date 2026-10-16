"""Pilar 4 · Visibilidad real: pregunta a varias IAs (con búsqueda web) y mide si te mencionan o te citan."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus, urlparse

import requests

from . import config
from .checks_base import norm

TIMEOUT = 120


# --- Consultas ---------------------------------------------------------------
def build_queries(brand: str, service: str, city: str, custom: list | None = None) -> list:
    service = service or "servicios"
    city = city or config.CIUDAD_DEFECTO
    qs = [
        f"¿Cuáles son las mejores opciones de {service} en {city}? Dame nombres concretos y sus páginas web.",
        f"Recomiéndame un lugar confiable para {service} en {city}. ¿Por qué lo recomiendas?",
    ]
    if brand:
        qs += [
            f"¿Qué sabes de {brand} en {city}? ¿Es recomendable?",
            f"¿Cuál es la dirección, el teléfono y el horario de {brand}?",
        ]
    for q in custom or []:
        q = q.strip()
        if q and q not in qs:
            qs.append(q)
    return qs[:8]


def manual_links(queries: list) -> list:
    """Enlaces para revisar a mano cuando no hay API keys."""
    out = []
    for q in queries:
        e = quote_plus(q)
        out.append({
            "query": q,
            "links": {
                "ChatGPT": f"https://chatgpt.com/?q={e}&hints=search",
                "Perplexity": f"https://www.perplexity.ai/search?q={e}",
                "Claude": f"https://claude.ai/new?q={e}",
                "Google AI Mode": f"https://www.google.com/search?q={e}&udm=50",
                "Copilot": f"https://www.bing.com/search?q={e}&showconv=1",
            },
        })
    return out


# --- Proveedores -------------------------------------------------------------
def _ask_openai(q: str, city: str) -> dict:
    r = requests.post(
        "https://api.openai.com/v1/responses",
        headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
        json={
            "model": config.OPENAI_MODEL,
            "input": q,
            "tools": [{"type": "web_search", "user_location": {"type": "approximate", "country": config.PAIS, "city": city}}],
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    text, cites = "", []
    for item in data.get("output", []):
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    text += c.get("text", "")
                    for a in c.get("annotations", []):
                        if a.get("type") == "url_citation":
                            cites.append({"url": a.get("url", ""), "title": a.get("title", "")})
    return {"text": text, "citations": cites}


def _ask_anthropic(q: str, city: str) -> dict:
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": config.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={
            "model": config.ANTHROPIC_MODEL,
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": q}],
            "tools": [{
                "type": "web_search_20250305", "name": "web_search", "max_uses": 3,
                "user_location": {"type": "approximate", "country": config.PAIS, "city": city},
            }],
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    text, cites, sources = "", [], []
    for block in data.get("content", []):
        if block.get("type") == "text":
            text += block.get("text", "")
            for c in block.get("citations") or []:
                if c.get("url"):
                    cites.append({"url": c["url"], "title": c.get("title", "")})
        elif block.get("type") == "web_search_tool_result" and isinstance(block.get("content"), list):
            for s in block["content"]:
                if s.get("url"):
                    sources.append({"url": s["url"], "title": s.get("title", "")})
    return {"text": text, "citations": cites, "sources": sources}


def _ask_gemini(q: str, city: str) -> dict:
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent",
        headers={"x-goog-api-key": config.GEMINI_API_KEY, "content-type": "application/json"},
        json={"contents": [{"parts": [{"text": q}]}], "tools": [{"google_search": {}}]},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    cand = (data.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
    cites = []
    for ch in cand.get("groundingMetadata", {}).get("groundingChunks", []):
        web = ch.get("web") or {}
        # Gemini devuelve una URL de redirección; el 'title' suele ser el dominio real
        cites.append({"url": web.get("uri", ""), "title": web.get("title", "")})
    return {"text": text, "citations": cites}


def _ask_perplexity(q: str, city: str) -> dict:
    r = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers={"Authorization": f"Bearer {config.PERPLEXITY_API_KEY}"},
        json={
            "model": config.PERPLEXITY_MODEL,
            "messages": [{"role": "user", "content": q}],
            "web_search_options": {"user_location": {"country": config.PAIS}},
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    text = data["choices"][0]["message"]["content"]
    cites = [{"url": u, "title": ""} for u in data.get("citations") or []]
    if not cites:
        cites = [{"url": s.get("url", ""), "title": s.get("title", "")} for s in data.get("search_results") or []]
    return {"text": text, "citations": cites}


PROVIDERS = {
    "ChatGPT": (lambda: config.OPENAI_API_KEY, _ask_openai, lambda: config.OPENAI_MODEL),
    "Claude": (lambda: config.ANTHROPIC_API_KEY, _ask_anthropic, lambda: config.ANTHROPIC_MODEL),
    "Gemini": (lambda: config.GEMINI_API_KEY, _ask_gemini, lambda: config.GEMINI_MODEL),
    "Perplexity": (lambda: config.PERPLEXITY_API_KEY, _ask_perplexity, lambda: config.PERPLEXITY_MODEL),
}


def active_providers() -> list:
    if config.CLOUD and not config.PUBLIC_AI:
        return []
    return [name for name, (key, _, _) in PROVIDERS.items() if key()]


# --- Análisis de cada respuesta ---------------------------------------------
def _host(u: str) -> str:
    h = urlparse(u).netloc.lower().split(":")[0]
    return h[4:] if h.startswith("www.") else h


def _is_ours(cite: dict, domain: str) -> bool:
    h = _host(cite.get("url", ""))
    t = (cite.get("title") or "").lower()
    return h == domain or h.endswith("." + domain) or domain in t


def _analyze(resp: dict, brand: str, domain: str) -> dict:
    text_n = norm(resp.get("text", ""))
    stem = domain.split(".")[0]
    terms = [norm(brand)] if brand and len(brand) >= 3 else []
    terms += [domain, stem] if len(stem) >= 4 else [domain]
    mentioned = any(t and t in text_n for t in terms)
    position = None
    if mentioned:
        idx = min(text_n.find(t) for t in terms if t and t in text_n)
        position = round(100 * idx / max(1, len(text_n)))  # % del texto donde aparece por primera vez
    all_cites = resp.get("citations", []) + resp.get("sources", [])
    cited = any(_is_ours(c, domain) for c in resp.get("citations", []))
    in_sources = any(_is_ours(c, domain) for c in all_cites)
    others = []
    for c in all_cites:
        h = _host(c.get("url", ""))
        if "vertexaisearch" in h or not h:
            h = (c.get("title") or "").lower().strip()
        if h and not _is_ours(c, domain):
            others.append(h)
    return {"mentioned": mentioned, "cited": cited, "in_sources": in_sources, "position": position, "competitors": others}


def run(queries: list, brand: str, city: str, domain: str, progress=lambda m: None) -> dict:
    providers = active_providers()
    if not providers:
        return {"ran": False, "providers": [], "results": [], "score": None,
                "message": ("Demo pública: la consulta automática a IAs está desactivada. Instala la versión local con tus claves "
                            "de API para medirla, o usa los enlaces de abajo para revisar cada IA a mano.") if config.CLOUD else
                "No hay claves de API configuradas en .env. Usa los enlaces manuales para revisar cada IA."}

    jobs = [(p, q) for p in providers for q in queries]
    progress(f"Consultando {len(providers)} IA(s) con {len(queries)} preguntas ({len(jobs)} consultas)…")

    def one(job):
        prov, q = job
        _, fn, model = PROVIDERS[prov]
        try:
            resp = fn(q, city or config.CIUDAD_DEFECTO)
            res = _analyze(resp, brand, domain)
            return {"provider": prov, "model": model(), "query": q, "ok": True, "text": resp["text"][:4000],
                    "citations": resp.get("citations", [])[:15], **res}
        except requests.HTTPError as exc:
            body = exc.response.text[:300] if exc.response is not None else ""
            return {"provider": prov, "model": model(), "query": q, "ok": False, "error": f"HTTP {exc.response.status_code if exc.response is not None else ''}: {body}"}
        except Exception as exc:  # noqa: BLE001 - se reporta el error en el informe
            return {"provider": prov, "model": model(), "query": q, "ok": False, "error": str(exc)[:300]}

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(one, jobs))

    summary = {}
    comp = Counter()
    for prov in providers:
        rs = [r for r in results if r["provider"] == prov and r["ok"]]
        if not rs:
            summary[prov] = {"score": None, "mentions": 0, "citations": 0, "answered": 0,
                             "error": next((r["error"] for r in results if r["provider"] == prov), "")}
            continue
        m = sum(r["mentioned"] for r in rs)
        c = sum(r["cited"] or r["in_sources"] for r in rs)
        # mención vale 60%, cita/fuente vale 40%
        score = round(100 * (0.6 * m + 0.4 * c) / len(rs))
        summary[prov] = {"score": score, "mentions": m, "citations": c, "answered": len(rs), "error": ""}
        for r in rs:
            comp.update(set(r["competitors"]))

    valid = [s["score"] for s in summary.values() if s["score"] is not None]
    return {
        "ran": True,
        "providers": providers,
        "summary": summary,
        "results": results,
        "score": round(sum(valid) / len(valid)) if valid else None,
        "competitors": comp.most_common(15),
        "message": "",
    }
