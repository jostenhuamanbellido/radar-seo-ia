"""Pilar 2 · GEO (Generative Engine Optimization): ¿pueden las IAs leer, entender y citar tu web?"""
from datetime import date

from .checks_base import check, graded
from .extract import as_list, extract_dates, nodes_of, ORG_TYPES

P = "geo"

# Rastreadores de IA que se evalúan en robots.txt
AI_CRAWLERS = [
    ("GPTBot", "OpenAI · entrenamiento"),
    ("OAI-SearchBot", "ChatGPT Search"),
    ("ChatGPT-User", "ChatGPT navegando por un usuario"),
    ("ClaudeBot", "Anthropic · entrenamiento"),
    ("Claude-SearchBot", "Claude búsqueda"),
    ("Claude-User", "Claude navegando por un usuario"),
    ("PerplexityBot", "Perplexity"),
    ("Perplexity-User", "Perplexity navegando por un usuario"),
    ("Google-Extended", "Gemini / IA de Google"),
    ("Googlebot", "Google Search + AI Overviews"),
    ("Bingbot", "Bing + Copilot + ChatGPT"),
    ("Applebot-Extended", "Apple Intelligence"),
    ("CCBot", "Common Crawl (datasets de IA)"),
    ("meta-externalagent", "Meta AI"),
]
# Los que más impactan en que te CITEN (búsqueda en tiempo real)
CRITICAL = {"OAI-SearchBot", "ChatGPT-User", "Claude-SearchBot", "Claude-User", "PerplexityBot", "Perplexity-User", "Googlebot", "Bingbot"}


def run(ctx: dict) -> list:
    home, pages, nodes = ctx["home"], ctx["pages"], ctx["all_nodes"]
    out = []

    # 1. robots.txt para bots de IA ------------------------------------------
    rb = ctx["robots"]
    allowed = rb["allowed"]
    blocked = [b for b, ok in allowed.items() if not ok]
    blocked_critical = [b for b in blocked if b in CRITICAL]
    ratio = 1 - (len(blocked_critical) * 0.15 + (len(blocked) - len(blocked_critical)) * 0.04)
    detail = "Todos los rastreadores de IA permitidos." if not blocked else f"Bloqueados: {', '.join(blocked)}"
    if not rb["found"]:
        detail = "No hay robots.txt (todo permitido por defecto). " + detail
    out.append(graded(P, "robots_ai", "robots.txt permite a los rastreadores de IA", ratio, 15, detail,
                      "Quita los Disallow para bots de búsqueda de IA (OAI-SearchBot, Claude-SearchBot, PerplexityBot, Bingbot). "
                      "Bloquear bots de entrenamiento (GPTBot, CCBot) es opcional; bloquear los de búsqueda te saca de las respuestas."))

    # 2. Firewall / WAF -------------------------------------------------------
    bt = ctx["bot_tests"]
    if bt:
        bad = [name for name, r in bt.items() if r["blocked"]]
        out.append(check(P, "waf_ai", "El servidor/firewall responde a los bots de IA", "ok" if not bad else "fail",
                         10 if not bad else 10 * (1 - len(bad) / len(bt)), 10,
                         "; ".join(f"{n}: HTTP {r['status']}" for n, r in bt.items()) + " (prueba indicativa con user-agent simulado)",
                         "Revisa Cloudflare (Security > Bots > 'Block AI bots' / 'AI Labyrinth') o Wordfence/hosting: "
                         "están devolviendo error a los bots de IA."))

    # 3. Contenido renderizado en HTML ---------------------------------------
    wc = home["word_count"]
    if wc >= 300:
        out.append(check(P, "ssr", "Contenido legible sin JavaScript", "ok", 10, 10, f"{wc} palabras en el HTML inicial."))
    elif wc >= 100:
        out.append(check(P, "ssr", "Contenido legible sin JavaScript", "warn", 5, 10, f"Solo {wc} palabras en el HTML inicial.",
                         "La mayoría de bots de IA no ejecutan JavaScript: el texto importante debe venir en el HTML."))
    else:
        out.append(check(P, "ssr", "Contenido legible sin JavaScript", "fail", 0, 10,
                         f"Solo {wc} palabras visibles sin ejecutar JS ({home['script_count']} scripts).",
                         "Tu contenido depende de JavaScript. Usa renderizado en servidor o HTML estático para los textos clave."))

    # 4. Meta robots ---------------------------------------------------------
    mr = home["meta_robots"]
    bad_dirs = [d for d in ("noindex", "nosnippet", "max-snippet:0", "noai", "noimageai") if d in mr.replace(" ", "")]
    out.append(check(P, "meta_robots", "Meta robots no bloquea fragmentos (nosnippet/noindex)",
                     "ok" if not bad_dirs else "fail", 8 if not bad_dirs else 0, 8,
                     f"meta robots: \"{mr or 'no definido'}\"",
                     f"Quita {', '.join(bad_dirs)}: impide que Google y las IAs usen tu contenido en sus respuestas."))

    # 5. Entidad clara (Organization + sameAs + logo) ------------------------
    orgs = nodes_of(nodes, ORG_TYPES)
    same = sorted({str(s) for n in orgs for s in as_list(n.get("sameAs"))})
    has_logo = any(n.get("logo") for n in orgs)
    has_desc = any(n.get("description") for n in orgs)
    ratio = (0.4 if orgs else 0) + (0.3 if len(same) >= 2 else 0.15 if same else 0) + (0.15 if has_logo else 0) + (0.15 if has_desc else 0)
    out.append(graded(P, "entity", "Entidad bien definida (Organization/LocalBusiness + sameAs + logo + descripción)", ratio, 10,
                      f"Nodos de organización: {len(orgs)} · sameAs: {len(same)} · logo: {'sí' if has_logo else 'no'} · description: {'sí' if has_desc else 'no'}",
                      "Las IAs conectan tu marca con fuentes externas vía sameAs. Completa logo, description y perfiles oficiales."))

    # 6. Autoría / E-E-A-T ---------------------------------------------------
    persons = nodes_of(nodes, {"Person", "Physician"})
    has_author = bool(home["meta_author"]) or any(n.get("author") for n in nodes) or bool(persons)
    reviewed = any(n.get("reviewedBy") or n.get("lastReviewed") for n in nodes)
    ratio = (0.7 if has_author else 0) + (0.3 if reviewed or len(persons) >= 1 else 0)
    out.append(graded(P, "authorship", "Autoría y credenciales (E-E-A-T)", ratio, 8,
                      f"Autor: {'sí' if has_author else 'no'} · Person/Physician: {len(persons)} · revisión médica: {'sí' if reviewed else 'no'}",
                      "Muestra quién escribe/revisa el contenido (nombre, especialidad, CMP) y márcalo con schema Person/Physician y reviewedBy."))

    # 7. Frescura -------------------------------------------------------------
    dates = sorted({d for p in pages for d in extract_dates(p)})
    if dates:
        last = dates[-1]
        try:
            days = (date.today() - date.fromisoformat(last)).days
        except ValueError:
            days = 9999
        st = "ok" if days <= 365 else "warn"
        out.append(check(P, "freshness", "Contenido con fecha de actualización reciente", st, 8 if st == "ok" else 3, 8,
                         f"Fecha más reciente: {last} (hace {days} días)",
                         "Actualiza el contenido clave y muestra/marca dateModified. Las IAs priorizan información reciente."))
    else:
        out.append(check(P, "freshness", "Contenido con fecha de actualización reciente", "fail", 0, 8, "No se encontraron fechas.",
                         "Muestra la fecha de actualización y agrega dateModified en el schema."))

    # 8. Citabilidad: datos y fuentes ------------------------------------------
    stats = sum(p["stats_count"] for p in pages)
    auth = sorted({a for p in pages for a in p["authority_links"]})
    ratio = min(1.0, stats / 8) * 0.6 + min(1.0, len(auth) / 2) * 0.4
    out.append(graded(P, "citability", "Citabilidad: datos concretos y fuentes externas", ratio, 8,
                      f"{stats} datos/cifras · {len(auth)} enlaces a fuentes de autoridad",
                      "Incluye cifras concretas (años de experiencia, nº de pacientes, precios desde, duración) y cita fuentes (MINSA, PubMed, OMS)."))

    # 9. Estructura de encabezados -------------------------------------------
    h2 = sum(1 for h in home["headings"] if h["tag"] == "h2")
    out.append(graded(P, "headings", "Estructura de encabezados (H2/H3) para fragmentar respuestas", min(1.0, h2 / 4), 6,
                      f"{h2} H2 en la home", "Divide el contenido en secciones con H2 descriptivos; las IAs extraen por secciones."))

    # 10. Sitemap ------------------------------------------------------------
    sm = ctx["sitemap"]
    out.append(check(P, "sitemap", "Sitemap XML accesible", "ok" if sm["found"] else "fail", 6 if sm["found"] else 0, 6,
                     sm.get("url") or "No encontrado en robots.txt, /sitemap.xml ni /sitemap_index.xml",
                     "Activa el sitemap en Rank Math/Yoast y decláralo en robots.txt (Sitemap: https://...)."))

    # 11. llms.txt ------------------------------------------------------------
    ll = ctx["llms"]
    out.append(check(P, "llms_txt", "Archivo /llms.txt", "ok" if ll["found"] else "warn", 4 if ll["found"] else 1, 4,
                     f"Encontrado ({ll['size']} bytes)" if ll["found"] else "No existe /llms.txt",
                     "Estándar emergente (aún no lo usa oficialmente ninguna IA grande, impacto bajo). Rank Math y Yoast ya pueden generarlo."))

    # 12. Profundidad del contenido -------------------------------------------
    mw = home["main_word_count"]
    out.append(graded(P, "depth", "Profundidad del contenido principal", min(1.0, mw / 600), 6,
                      f"{mw} palabras en el contenido principal de la home",
                      "Las respuestas de IA citan páginas que explican el tema con profundidad. Apunta a 600+ palabras útiles."))

    # 13. JSON-LD válido ------------------------------------------------------
    errs = sum(p["jsonld_errors"] for p in pages)
    blocks = sum(p["jsonld_blocks"] for p in pages)
    if blocks:
        out.append(check(P, "jsonld_valid", "JSON-LD sin errores de sintaxis", "ok" if not errs else "fail", 5 if not errs else 0, 5,
                         f"{blocks} bloques, {errs} con error", "Corrige los bloques JSON-LD inválidos (valida en validator.schema.org)."))
    else:
        out.append(check(P, "jsonld_valid", "Datos estructurados JSON-LD", "fail", 0, 5, "No hay JSON-LD.",
                         "Activa el schema en Rank Math/Yoast o agrega JSON-LD manual."))
    return out
