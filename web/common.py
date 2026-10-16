"""Utilidades compartidas por las rutas: sesión, SEO y caché."""
import json
from functools import wraps

from flask import redirect, request, session, url_for

from radar import config, db
from radar.countries import COUNTRIES


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    return {"id": uid, "email": session.get("email", "")}


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not current_user():
            return redirect(url_for("account.entrar", next=request.path))
        if not db.enabled():
            return "Las cuentas necesitan Supabase configurado (SUPABASE_URL y claves).", 503
        return fn(*a, **kw)
    return wrapper


def abs_url(path: str) -> str:
    return config.SITE_URL + path


def seo(title: str, description: str, path: str, *, alternates: dict | None = None, jsonld: list | None = None,
        noindex: bool = False, og_type: str = "website") -> dict:
    """alternates: {hreflang: path}."""
    return {
        "title": title,
        "description": description,
        "canonical": abs_url(path),
        "alternates": {k: abs_url(v) for k, v in (alternates or {}).items()},
        "jsonld": [json.dumps(j, ensure_ascii=False) for j in (jsonld or [])],
        "noindex": noindex,
        "og_type": og_type,
    }


def country_alternates(path_for) -> dict:
    """Alternates hreflang para páginas que existen en cada país. path_for(code|None) -> path."""
    alts = {"x-default": path_for(None), "es": path_for(None)}
    for code, c in COUNTRIES.items():
        alts[c["hreflang"]] = path_for(code)
    return alts


def cached(resp, seconds: int = 3600):
    """Cachea en el CDN de Vercel las páginas públicas."""
    resp.headers["Cache-Control"] = f"public, s-maxage={seconds}, stale-while-revalidate=86400"
    return resp


def client_ip() -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return (fwd.split(",")[0].strip() if fwd else request.remote_addr) or "0.0.0.0"


ORG_JSONLD = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": config.SITE_URL + "/#org",
    "name": config.BRAND,
    "url": config.SITE_URL + "/",
    "logo": config.SITE_URL + "/static/logo.png",
    "description": "Herramienta para medir y mejorar la visibilidad de negocios locales en ChatGPT, Gemini, Claude y Perplexity.",
    "founder": {"@type": "Person", "name": "Josten Huamán", "jobTitle": "Ingeniero de software y SEO"},
    "sameAs": [config.GITHUB_URL],
}
