"""Orquestador: dada una URL rastrea la web, ejecuta los 4 pilares y arma el resultado."""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib import robotparser

from . import ai_visibility, checks_aeo, checks_geo, checks_local, config, pagespeed
from .checks_base import PILLARS, WEIGHTS, grade, norm, pillar_score, total_score
from .extract import address_of, first_local_node, nodes_of, ORG_TYPES, parse_page
from .fetcher import AI_BOT_UAS, get, looks_like_html, normalize_url, origin, root_domain

PRIORITY_KEYWORDS = ("contact", "nosotros", "quienes", "about", "preguntas", "faq", "servicio", "tratamiento",
                     "especialidad", "precio", "blog", "doctor", "equipo", "sede", "ubicacion")

KNOWN_PLACES = [
    "Miraflores", "San Isidro", "Santiago de Surco", "Surco", "La Molina", "San Borja", "Jesús María", "Lince",
    "Magdalena", "San Miguel", "Pueblo Libre", "Barranco", "Chorrillos", "Los Olivos", "San Martín de Porres",
    "Independencia", "Comas", "Ate", "La Victoria", "Breña", "Rímac", "San Juan de Lurigancho", "San Juan de Miraflores",
    "Villa El Salvador", "Lima", "Callao", "Arequipa", "Trujillo", "Chiclayo", "Piura", "Cusco", "Huancayo", "Ica",
    "Tacna", "Puno", "Cajamarca", "Iquitos", "Pucallpa", "Chimbote", "Huánuco", "Ayacucho", "Tarapoto",
]

TYPE_TO_SERVICE = {
    "Dentist": "odontología", "MedicalClinic": "clínica médica", "Physician": "médico especialista",
    "Hospital": "clínica", "BeautySalon": "salón de belleza", "DaySpa": "spa", "HairSalon": "peluquería",
    "Restaurant": "restaurante", "Attorney": "abogados", "LegalService": "abogados", "Optician": "óptica",
    "Pharmacy": "farmacia", "ExerciseGym": "gimnasio", "VeterinaryCare": "veterinaria", "Hotel": "hotel",
    "RealEstateAgent": "inmobiliaria", "AutoRepair": "taller mecánico", "TravelAgency": "agencia de viajes",
}


# --- Utilidades de rastreo ----------------------------------------------------
def _pick_internal(home: dict, final_url: str, limit: int) -> list:
    def score(item):
        u, t = item
        s = (u + " " + t).lower()
        return -sum(k in s for k in PRIORITY_KEYWORDS)
    base = final_url.rstrip("/")
    cands = [(u, t) for u, t in home["internal_links"] if u.rstrip("/") != base and "?" not in u]
    cands.sort(key=score)
    picked, seen = [], set()
    for u, _ in cands:
        key = u.rstrip("/")
        if key not in seen:
            seen.add(key)
            picked.append(u)
        if len(picked) >= limit:
            break
    return picked


def _robots(base: str, url: str) -> dict:
    r = get(base + "/robots.txt", timeout=15)
    found = r["status"] == 200 and not looks_like_html(r)
    rp = robotparser.RobotFileParser()
    rp.parse(r["text"].splitlines() if found else [])
    allowed = {bot: rp.can_fetch(bot, url) for bot, _ in checks_geo.AI_CRAWLERS}
    sitemaps = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", r["text"]) if found else []
    return {"found": found, "allowed": allowed, "sitemaps": sitemaps, "content": r["text"][:3000] if found else ""}


def _sitemap(base: str, robots: dict) -> dict:
    for u in robots["sitemaps"][:2] + [base + "/sitemap_index.xml", base + "/sitemap.xml", base + "/wp-sitemap.xml"]:
        r = get(u, timeout=15)
        if r["status"] == 200 and ("<urlset" in r["text"][:3000] or "<sitemapindex" in r["text"][:3000]):
            return {"found": True, "url": r["url"]}
    return {"found": False, "url": ""}


def _llms(base: str) -> dict:
    r = get(base + "/llms.txt", timeout=15)
    ok = r["status"] == 200 and not looks_like_html(r) and len(r["text"].strip()) > 20
    return {"found": ok, "size": len(r["content"]) if ok else 0, "preview": r["text"][:600] if ok else ""}


def _bot_tests(url: str, normal_status: int) -> dict:
    out = {}
    for name, ua in AI_BOT_UAS.items():
        r = get(url, timeout=20, ua=ua)
        txt = r["text"][:4000].lower()
        challenge = "just a moment" in txt or "cf-chl" in txt or "attention required" in txt
        blocked = (r["status"] in (0, 401, 403, 406, 429, 503) and normal_status == 200) or (challenge and normal_status == 200)
        out[name] = {"status": r["status"], "blocked": blocked}
    return out


# --- Inferencia de marca / ciudad / servicio --------------------------------
def _infer_brand(home, nodes) -> str:
    local = first_local_node(nodes)
    if local and isinstance(local.get("name"), str):
        return local["name"].strip()
    if home["og_site_name"]:
        return home["og_site_name"]
    for n in nodes_of(nodes, ORG_TYPES):
        if isinstance(n.get("name"), str):
            return n["name"].strip()
    parts = [p.strip() for p in re.split(r"\s[|–—\-:·]\s", home["title"]) if p.strip()]
    return parts[-1] if len(parts) > 1 else (parts[0] if parts else "")


def _infer_city(home, nodes) -> tuple[str, str]:
    """Devuelve (ciudad_para_onpage, ciudad_para_consultas)."""
    addr = address_of(first_local_node(nodes) or {})
    loc, reg = addr.get("addressLocality", ""), addr.get("addressRegion", "")
    if isinstance(loc, str) and loc.strip():
        loc = loc.strip()
        full = f"{loc}, {reg}" if isinstance(reg, str) and reg.strip() and norm(reg) not in norm(loc) else loc
        return loc, full
    def hits(place, text):
        return len(re.findall(rf"\b{re.escape(norm(place))}\b", text))
    hay = norm(home["title"] + " " + " ".join(home["h1"]))
    lima_districts = KNOWN_PLACES[:KNOWN_PLACES.index("Lima")]
    for place in KNOWN_PLACES:
        if hits(place, hay):
            return place, (f"{place}, Lima" if place in lima_districts else place)
    text = norm(home["full_text"])
    counts = {p: hits(p, text) for p in KNOWN_PLACES}
    best = max(counts, key=counts.get)
    if counts[best] >= 2:
        return best, best
    return "", config.CIUDAD_DEFECTO


def _infer_service(home, nodes, brand, city) -> str:
    parts = [p.strip() for p in re.split(r"\s[|–—\-:·]\s", home["title"]) if p.strip()]
    parts = [p for p in parts if not brand or norm(brand) not in norm(p)]
    if parts:
        s = parts[0]
        if city:
            s = re.sub(rf"\s+(en|de)\s+{re.escape(city)}.*$", "", s, flags=re.I)
        s = re.sub(r"\s+en\s+(Lima|Perú|Peru)\b.*$", "", s, flags=re.I).strip()
        if 2 <= len(s) <= 70:
            return s
    local = first_local_node(nodes)
    if local:
        for t in (local.get("@type") if isinstance(local.get("@type"), list) else [local.get("@type")]):
            if t in TYPE_TO_SERVICE:
                return TYPE_TO_SERVICE[t]
    if home["h1"] and len(home["h1"][0].split()) <= 8:
        return home["h1"][0]
    return ""


def _block_private(url: str):
    """En la demo pública no se permite auditar IPs internas (protección SSRF)."""
    import ipaddress
    import socket
    from urllib.parse import urlparse
    host = urlparse(url).hostname or ""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise ValueError(f"No existe el dominio {host}.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("Esa dirección no está permitida en la demo pública.")


# --- Auditoría principal ------------------------------------------------------
def run_audit(url: str, brand: str = "", service: str = "", city: str = "", custom_queries=None,
              run_ai: bool = True, run_psi: bool = True, max_pages: int | None = None, progress=lambda m: None) -> dict:
    url = normalize_url(url)
    if not url:
        raise ValueError("Escribe una URL.")
    max_pages = max_pages or config.MAX_PAGINAS
    if config.CLOUD:
        _block_private(url)

    progress("Descargando la página principal…")
    resp = get(url)
    if not resp["ok"] or resp["status"] >= 400 or not looks_like_html(resp):
        raise ValueError(f"No se pudo leer {url} (HTTP {resp['status']}). {resp.get('error', '')}")
    final_url = resp["url"]
    domain = root_domain(final_url)
    base = origin(final_url)

    with ThreadPoolExecutor(max_workers=6) as pool:
        psi_future = pool.submit(pagespeed.run, final_url) if run_psi else None
        bots_future = pool.submit(_bot_tests, final_url, resp["status"])

        home = parse_page(resp["content"], final_url, domain)
        home["status"], home["elapsed"] = resp["status"], resp["elapsed"]

        progress("Rastreando páginas internas clave…")
        internal = _pick_internal(home, final_url, max(0, max_pages - 1))
        def fetch_parse(u):
            r = get(u)
            if r["ok"] and r["status"] == 200 and looks_like_html(r):
                p = parse_page(r["content"], r["url"], domain)
                p["status"], p["elapsed"] = r["status"], r["elapsed"]
                return p
            return None
        pages = [home] + [p for p in pool.map(fetch_parse, internal) if p]

        progress("Revisando robots.txt, sitemap y llms.txt…")
        robots = _robots(base, final_url)
        sitemap = _sitemap(base, robots)
        llms = _llms(base)
        bot_tests = bots_future.result()
        if run_psi:
            progress("Midiendo velocidad móvil con PageSpeed Insights…")
        psi = psi_future.result() if psi_future else {"ok": False, "error": "PageSpeed desactivado en esta auditoría."}

    # nodos de schema sin duplicar (el mismo schema suele repetirse en todas las páginas)
    all_nodes, seen_nodes = [], set()
    for n in (n for p in pages for n in p["schema_nodes"]):
        key = json.dumps(n, sort_keys=True, ensure_ascii=False, default=str)
        if key not in seen_nodes:
            seen_nodes.add(key)
            all_nodes.append(n)
    auto_brand = _infer_brand(home, all_nodes)
    city_onpage, city_query = _infer_city(home, all_nodes)
    brand = (brand or auto_brand).strip()
    if city:
        city_onpage = city_query = city.strip()
    service = (service or _infer_service(home, all_nodes, brand, city_onpage)).strip()

    ctx = {
        "home": home, "pages": pages, "all_nodes": all_nodes, "robots": robots, "sitemap": sitemap, "llms": llms,
        "bot_tests": bot_tests, "psi": psi, "brand": brand, "city": city_onpage, "service": service,
        "domain": domain, "final_url": final_url,
    }

    progress("Evaluando SEO local, GEO y AEO…")
    checks = checks_local.run(ctx) + checks_geo.run(ctx) + checks_aeo.run(ctx)

    queries = ai_visibility.build_queries(brand, service, city_query, custom_queries)
    if run_ai:
        ai = ai_visibility.run(queries, brand, city_query, domain, progress)
    else:
        ai = {"ran": False, "providers": [], "results": [], "score": None, "message": "Consulta a IAs desactivada en esta auditoría."}

    scores = {p: pillar_score(checks, p) for p in ("local", "geo", "aeo")}
    scores["ai"] = ai.get("score")
    scores["total"] = total_score(scores)

    weight = {p: w for p, w in WEIGHTS.items()}
    issues = [c for c in checks if c["status"] in ("warn", "fail")]
    issues.sort(key=lambda c: (c["max"] - c["points"]) * weight[c["pillar"]], reverse=True)

    progress("Generando informe…")
    return {
        "version": 1,
        "input_url": url,
        "final_url": final_url,
        "domain": domain,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "meta": {"brand": brand, "service": service, "city": city_onpage, "city_query": city_query,
                 "auto_brand": auto_brand},
        "scores": scores,
        "grades": {k: grade(v) for k, v in scores.items()},
        "pillars": PILLARS,
        "checks": checks,
        "priorities": issues[:12],
        "pages": [{"url": p["url"], "title": p["title"], "words": p["word_count"], "schema": p["schema_types"],
                   "questions": len(p["question_headings"]), "status": p.get("status"), "elapsed": p.get("elapsed")}
                  for p in pages],
        "schema_types": sorted({t for p in pages for t in p["schema_types"]}),
        "robots": {"found": robots["found"], "allowed": robots["allowed"], "labels": dict(checks_geo.AI_CRAWLERS)},
        "bot_tests": bot_tests,
        "llms": llms,
        "sitemap": sitemap,
        "psi": psi,
        "ai": ai,
        "queries": queries,
        "manual": ai_visibility.manual_links(queries),
    }
