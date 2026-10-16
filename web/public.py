"""Páginas públicas (marketing + SEO): home, países, guía, precios, rankings, sitemap."""
from flask import Blueprint, Response, abort, make_response, redirect, render_template, request

from radar import config, countries, db, plans, report
from radar.countries import CATEGORIES, COUNTRIES

from .common import ORG_JSONLD, cached, country_alternates, current_user, seo

bp = Blueprint("public", __name__)

GUIDE_PATH = "/guia/como-aparecer-en-chatgpt/"


def faq(country: dict | None) -> list:
    where = country["in"] if country else "en Latinoamérica"
    return [
        ("¿Cómo sé si ChatGPT recomienda mi negocio?",
         f"Pega la URL de tu web en {config.BRAND}. Hacemos las preguntas que haría un cliente {where} "
         "(\"¿cuál es el mejor [servicio] en [ciudad]?\") a ChatGPT, Gemini, Claude y Perplexity con búsqueda web "
         "activada, y te mostramos si te mencionan, si citan tu web y quién aparece en tu lugar."),
        ("¿Qué es GEO y en qué se diferencia del SEO?",
         "GEO (Generative Engine Optimization) es optimizar tu web para que los motores de IA la lean, la entiendan y "
         "la citen en sus respuestas. El SEO clásico busca posiciones en Google; el GEO busca ser la fuente que la IA "
         "nombra. Comparten bases (contenido útil, datos estructurados, autoridad), pero el GEO añade acceso de los "
         "bots de IA, respuestas directas y menciones en otras fuentes."),
        ("¿Qué es AEO?",
         "AEO (Answer Engine Optimization) es escribir tu contenido como respuesta directa a preguntas reales: "
         "encabezados en forma de pregunta, una respuesta corta de 40-60 palabras debajo y luego el detalle. Es el "
         "formato que copian los fragmentos destacados de Google y los asistentes de IA."),
        ("¿La auditoría es gratis?",
         "Sí. La auditoría técnica de SEO local, GEO y AEO es gratis y sin registro. Con una cuenta gratuita también "
         "medimos tu visibilidad real en las IAs; los planes de pago añaden seguimiento semanal y más preguntas."),
        ("¿Por qué no aparezco en ChatGPT si estoy primero en Google?",
         "Porque las IAs combinan varias fuentes: tu web, tu ficha de Google, directorios, reseñas y medios. Las causas "
         "más comunes son bots de IA bloqueados en robots.txt o Cloudflare, contenido que solo carga con JavaScript, "
         "falta de schema LocalBusiness y pocas menciones de tu marca fuera de tu web."),
        ("¿Cada cuánto cambian las respuestas de las IAs?",
         "Cambian con frecuencia: según el modelo, la ubicación y el día. Por eso conviene medir cada semana y mirar la "
         "tendencia, no una sola respuesta."),
    ]


def _home(code: str | None):
    country = countries.get(code) if code else None
    path = f"/{code}/" if code else "/"
    if country:
        title = f"Cómo aparecer en ChatGPT {country['in']}: auditoría GEO gratis | {config.BRAND}"
        desc = (f"Descubre si ChatGPT, Gemini y Perplexity recomiendan tu negocio {country['in']}. Auditoría gratis de "
                f"SEO local, GEO y AEO con acciones concretas para aparecer.")
    else:
        title = f"¿Tu negocio aparece en ChatGPT? Auditoría GEO gratis | {config.BRAND}"
        desc = ("Mide si ChatGPT, Gemini, Claude y Perplexity recomiendan tu negocio local. Auditoría gratis de SEO "
                "local, GEO y AEO con lo que debes corregir para aparecer.")
    questions = faq(country)
    jsonld = [
        ORG_JSONLD,
        {"@context": "https://schema.org", "@type": "WebSite", "name": config.BRAND, "url": config.SITE_URL + "/",
         "inLanguage": country["hreflang"] if country else "es"},
        {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": config.BRAND,
         "applicationCategory": "BusinessApplication", "operatingSystem": "Web",
         "description": desc, "url": config.SITE_URL + path,
         "offers": [{"@type": "Offer", "name": p["name"], "price": str(p["price"]), "priceCurrency": "USD"}
                    for p in plans.PLANS.values()]},
        {"@context": "https://schema.org", "@type": "FAQPage",
         "mainEntity": [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
                        for q, a in questions]},
    ]
    meta = seo(title, desc, path, alternates=country_alternates(lambda c: f"/{c}/" if c else "/"), jsonld=jsonld)
    recent = []
    if db.enabled():
        try:
            recent = db.rankings(code)[:6]
        except db.DBError:
            recent = []
    html = render_template("home.html", meta=meta, country=country, faq=questions, plans=plans.PLANS,
                           countries=COUNTRIES, categories=CATEGORIES, rankings=recent, user=current_user(),
                           lang=country["hreflang"] if country else "es")
    return cached(make_response(html), 600)


@bp.get("/")
def home():
    return _home(None)


@bp.get("/<code>/")
def home_country(code):
    if code not in COUNTRIES:
        abort(404)
    return _home(code)


@bp.get("/<code>")
def home_country_noslash(code):
    if code not in COUNTRIES:
        abort(404)
    return redirect(f"/{code}/", 301)


@bp.get(GUIDE_PATH)
def guide():
    title = f"Cómo aparecer en ChatGPT con tu negocio (guía 2026) | {config.BRAND}"
    desc = ("Guía práctica para que ChatGPT, Gemini y Perplexity recomienden tu negocio local: acceso de bots, "
            "schema, contenido pregunta-respuesta, reseñas y menciones. Con checklist.")
    jsonld = [ORG_JSONLD, {
        "@context": "https://schema.org", "@type": "Article", "headline": "Cómo aparecer en ChatGPT con tu negocio",
        "description": desc, "inLanguage": "es", "datePublished": "2026-10-16", "dateModified": "2026-10-16",
        "author": {"@type": "Person", "name": "Josten Huamán", "jobTitle": "Ingeniero de software y SEO"},
        "publisher": {"@id": config.SITE_URL + "/#org"}, "mainEntityOfPage": config.SITE_URL + GUIDE_PATH,
    }, {
        "@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": config.BRAND, "item": config.SITE_URL + "/"},
            {"@type": "ListItem", "position": 2, "name": "Cómo aparecer en ChatGPT", "item": config.SITE_URL + GUIDE_PATH},
        ]}]
    meta = seo(title, desc, GUIDE_PATH, jsonld=jsonld, og_type="article")
    return cached(make_response(render_template("guia.html", meta=meta, user=current_user(), countries=COUNTRIES)), 3600)


@bp.route("/precios/", methods=["GET", "POST"])
def pricing():
    sent = False
    error = ""
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        if "@" not in email or len(email) > 200:
            error = "Escribe un correo válido."
        elif db.enabled():
            try:
                db.save_lead(email, request.form.get("plan", ""), request.form.get("country", ""), request.form.get("note", ""))
                sent = True
            except db.DBError:
                error = "No pudimos guardar tu solicitud. Escríbenos a " + config.CONTACT_EMAIL
        else:
            error = "Escríbenos a " + config.CONTACT_EMAIL
    title = f"Precios: auditoría GEO y seguimiento en ChatGPT | {config.BRAND}"
    desc = "Gratis para auditar tu web. Desde US$15/mes para seguir cada semana tu visibilidad en ChatGPT, Gemini y Perplexity. Plan para agencias."
    meta = seo(title, desc, "/precios/", jsonld=[ORG_JSONLD])
    resp = make_response(render_template("precios.html", meta=meta, plans=plans.PLANS, sent=sent, error=error,
                                         user=current_user(), countries=COUNTRIES,
                                         chosen=request.values.get("plan", "negocio")))
    return resp if request.method == "POST" else cached(resp, 3600)


@bp.get("/privacidad/")
def privacy():
    meta = seo(f"Privacidad | {config.BRAND}", "Cómo tratamos tus datos.", "/privacidad/")
    return render_template("privacidad.html", meta=meta, user=current_user(), countries=COUNTRIES)


# --- Rankings ---------------------------------------------------------------
@bp.get("/rankings/")
def rankings_index():
    rows = db.rankings() if db.enabled() else []
    meta = seo(f"Qué negocios recomienda la IA en cada ciudad | {config.BRAND}",
               "Rankings con datos reales de ChatGPT, Gemini, Claude y Perplexity: qué clínicas, dentistas, abogados y más recomiendan en tu ciudad.",
               "/rankings/", jsonld=[ORG_JSONLD])
    return cached(make_response(render_template("rankings_index.html", meta=meta, rows=rows, countries=COUNTRIES,
                                                user=current_user())), 1800)


@bp.get("/rankings/<code>/<slug>/")
def ranking_page(code, slug):
    if code not in COUNTRIES or not db.enabled():
        abort(404)
    row = db.ranking(code, slug)
    if not row:
        abort(404)
    d = row["data"]
    country = countries.get(code)
    path = f"/rankings/{code}/{slug}/"
    title = f"Mejores {d['category']} en {d['city']} según ChatGPT y otras IAs | {config.BRAND}"
    desc = (f"Qué {d['category']} recomiendan ChatGPT, Gemini, Claude y Perplexity en {d['city']}, {country['name']}. "
            f"Datos reales actualizados el {d['generated_at']}.")
    jsonld = [ORG_JSONLD, {
        "@context": "https://schema.org", "@type": "ItemList", "name": f"{d['category'].capitalize()} en {d['city']} recomendados por IA",
        "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": it["name"], **({"url": it["web"]} if it["web"] else {})}
                            for i, it in enumerate(d["items"][:10])],
    }, {
        "@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Rankings", "item": config.SITE_URL + "/rankings/"},
            {"@type": "ListItem", "position": 2, "name": f"{d['category']} en {d['city']}", "item": config.SITE_URL + path},
        ]}]
    meta = seo(title, desc, path, jsonld=jsonld)
    return cached(make_response(render_template("ranking.html", meta=meta, d=d, country=country, countries=COUNTRIES,
                                                user=current_user(), lang=country["hreflang"])), 3600)


# --- Informe público --------------------------------------------------------
@bp.get("/r/<public_id>")
def public_report(public_id):
    if not db.enabled():
        abort(404)
    row = db.audit_by_public_id(public_id)
    if not row:
        abort(404)
    r = row["data"]
    r["public_id"] = public_id
    prev = db.previous_audit(row["site_id"], row["created_at"]) if row.get("site_id") else None
    brand = None
    if row.get("user_id"):
        p = db.profile(row["user_id"])
        if plans.get(p.get("plan"))["white_label"] and p.get("agency_name"):
            brand = p["agency_name"]
    u = current_user()
    owner = bool(u and row.get("user_id") == u["id"])
    return report.render(r, prev, brand=brand, owner=owner, site_id=row.get("site_id"), user=u)


# --- Archivos técnicos (dogfooding de GEO) ----------------------------------
@bp.get("/robots.txt")
def robots():
    body = (
        "User-agent: *\nAllow: /\nDisallow: /panel/\nDisallow: /r/\nDisallow: /api/\n\n"
        "# Bots de IA bienvenidos\n"
        + "".join(f"User-agent: {b}\nAllow: /\n\n" for b in
                  ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "PerplexityBot",
                   "Google-Extended", "Applebot-Extended"])
        + f"Sitemap: {config.SITE_URL}/sitemap.xml\n"
    )
    return cached(Response(body, mimetype="text/plain"), 86400)


@bp.get("/sitemap.xml")
def sitemap():
    urls = ["/", *[f"/{c}/" for c in COUNTRIES], GUIDE_PATH, "/precios/", "/rankings/"]
    if db.enabled():
        try:
            urls += [f"/rankings/{r['country']}/{r['slug']}/" for r in db.rankings()]
        except db.DBError:
            pass
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    body += "".join(f"  <url><loc>{config.SITE_URL}{u}</loc></url>\n" for u in urls)
    body += "</urlset>\n"
    return cached(Response(body, mimetype="application/xml"), 3600)


@bp.get("/llms.txt")
def llms():
    body = f"""# {config.BRAND}

> {config.BRAND} mide si ChatGPT, Gemini, Claude y Perplexity recomiendan a un negocio local y le dice qué corregir para aparecer. Audita SEO local, GEO (Generative Engine Optimization) y AEO (Answer Engine Optimization). Enfocado en Latinoamérica: Perú, México, Colombia, Chile y Argentina.

## Páginas principales
- [Auditoría GEO gratis]({config.SITE_URL}/): pega una URL y obtén puntaje de SEO local, GEO, AEO y visibilidad en IAs.
- [Cómo aparecer en ChatGPT]({config.SITE_URL}{GUIDE_PATH}): guía práctica para negocios locales.
- [Rankings por ciudad]({config.SITE_URL}/rankings/): qué negocios recomiendan las IAs en cada ciudad, con datos reales.
- [Precios]({config.SITE_URL}/precios/): plan gratis, plan Negocio (US$15/mes) y plan Agencia (US$89/mes).

## Países
""" + "".join(f"- [{c['name']}]({config.SITE_URL}/{k}/)\n" for k, c in COUNTRIES.items())
    return cached(Response(body, mimetype="text/plain; charset=utf-8"), 86400)


@bp.get("/favicon.ico")
def favicon():
    return redirect("/static/favicon.svg", 301)
