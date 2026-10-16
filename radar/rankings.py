"""Rankings públicos: "¿qué [rubro] recomienda la IA en [ciudad]?" con datos REALES de cada IA.

Se generan por consola (python rankings_cli.py ...) con tus claves de API y se guardan en Supabase.
Nunca se muestran rankings inventados: si no hay datos, la página no existe.
"""
import json
import re
import unicodedata
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urlparse

from . import ai_visibility
from .checks_base import norm
from .countries import COUNTRIES

PROMPT = (
    "Vivo en {city}, {country}. ¿Cuáles son las 10 mejores opciones de {category} en {city}? "
    "Busca en internet y responde SOLO con un JSON válido, sin texto adicional, con este formato: "
    '[{{"nombre": "Nombre del negocio", "web": "https://..."}}] ordenado del más recomendado al menos. '
    'Si no conoces la web, usa "".'
)


def slugify(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def ranking_slug(category: str, city: str) -> str:
    return slugify(f"{category} {city}")


def _parse_list(text: str) -> list:
    m = re.search(r"\[.*\]", text or "", re.S)
    if not m:
        return []
    raw = m.group(0)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # quita marcas de cita tipo [1] que algunas IAs insertan
        try:
            data = json.loads(re.sub(r"\[\d+\]", "", raw))
        except json.JSONDecodeError:
            return []
    out = []
    for item in data if isinstance(data, list) else []:
        if isinstance(item, dict) and item.get("nombre"):
            out.append({"name": str(item["nombre"]).strip()[:120], "web": str(item.get("web") or "").strip()[:200]})
    return out[:10]


def _key(name: str) -> str:
    k = norm(name)
    k = re.sub(r"\b(clinica|centro|consultorio|dr|dra|s\.?a\.?c?|e\.?i\.?r\.?l|spa|la|el|de|del)\b", " ", k)
    return re.sub(r"[^a-z0-9]+", "", k)


def _host(u: str) -> str:
    h = urlparse(u if "://" in u else "https://" + u).netloc.lower()
    return h[4:] if h.startswith("www.") else h


def generate(country_code: str, city: str, category: str, progress=print) -> dict:
    country = COUNTRIES[country_code]
    providers = ai_visibility.active_providers(force=True)
    if not providers:
        raise RuntimeError("Configura al menos una API key de IA en .env para generar rankings.")
    prompt = PROMPT.format(city=city, country=country["name"], category=category)

    def one(p):
        try:
            resp = ai_visibility.ask(p, prompt, city, country["iso"])
            items = _parse_list(resp["text"])
            progress(f"  {p}: {len(items)} negocios")
            return p, items, ""
        except Exception as exc:  # noqa: BLE001
            progress(f"  {p}: error {exc}")
            return p, [], str(exc)[:200]

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(one, providers))

    merged: dict = {}
    by_host: dict = {}
    for prov, items, _ in results:
        for pos, it in enumerate(items, start=1):
            host = _host(it["web"]) if it["web"] else ""
            k = by_host.get(host) if host else None
            k = k or _key(it["name"])
            if not k:
                continue
            entry = merged.setdefault(k, {"name": it["name"], "web": it["web"], "mentions": {}, "score": 0})
            if not entry["web"] and it["web"]:
                entry["web"] = it["web"]
            if host:
                by_host[host] = k
            if prov not in entry["mentions"]:
                entry["mentions"][prov] = pos
                entry["score"] += 11 - pos
    items = sorted(merged.values(), key=lambda e: (-len(e["mentions"]), -e["score"]))
    ok_providers = [p for p, its, _ in results if its]
    return {
        "country": country_code, "city": city, "category": category,
        "slug": ranking_slug(category, city),
        "generated_at": datetime.now().strftime("%Y-%m-%d"),
        "providers": ok_providers,
        "errors": {p: e for p, _, e in results if e},
        "prompt": prompt,
        "items": items[:20],
    }
