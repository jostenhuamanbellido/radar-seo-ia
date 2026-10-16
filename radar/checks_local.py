"""Pilar 1 · SEO Local: señales que Google Maps / Local Pack y las IAs usan para ubicar un negocio."""
from .checks_base import check, graded, norm
from .extract import address_of, as_list, digits, first_local_node, nodes_of, ORG_TYPES

P = "local"


def run(ctx: dict) -> list:
    home, nodes = ctx["home"], ctx["all_nodes"]
    city = ctx.get("city") or ""
    out = []
    local = first_local_node(nodes)

    # 1. Schema LocalBusiness ------------------------------------------------
    if local:
        types = ", ".join(as_list(local.get("@type")))
        out.append(check(P, "schema_local", "Schema de negocio local (LocalBusiness o subtipo)", "ok", 15, 15,
                         f"Encontrado: {types}"))
    elif nodes_of(nodes, ORG_TYPES):
        out.append(check(P, "schema_local", "Schema de negocio local (LocalBusiness o subtipo)", "warn", 6, 15,
                         "Solo hay schema Organization genérico.",
                         "Cambia o agrega un tipo específico (MedicalClinic, Dentist, BeautySalon, etc.) con dirección, teléfono y horario."))
    else:
        out.append(check(P, "schema_local", "Schema de negocio local (LocalBusiness o subtipo)", "fail", 0, 15,
                         "No se encontró schema de negocio en las páginas analizadas.",
                         "Agrega JSON-LD LocalBusiness (o subtipo) en la home y en la página de contacto. En WordPress: Rank Math > Local SEO."))

    # 2. Dirección completa ----------------------------------------------------
    addr = address_of(local) if local else {}
    fields = ["streetAddress", "addressLocality", "addressRegion", "addressCountry", "postalCode"]
    have = [f for f in fields if addr.get(f)]
    out.append(graded(P, "schema_address", "Dirección estructurada completa (NAP)", len(have) / len(fields), 10,
                      f"Campos presentes: {', '.join(have) or 'ninguno'}",
                      "Completa PostalAddress: streetAddress, addressLocality (distrito), addressRegion, addressCountry=PE y postalCode."))

    # 3. Teléfono ------------------------------------------------------------
    schema_tel = (local or {}).get("telephone") or next((n.get("telephone") for n in nodes if n.get("telephone")), "")
    tel_links = sorted({t for p in ctx["pages"] for t in p["tel_links"]})
    if schema_tel and tel_links:
        out.append(check(P, "phone", "Teléfono en schema y enlace tel: clicable", "ok", 8, 8, f"Schema: {schema_tel} · tel: {', '.join(tel_links[:3])}"))
    elif schema_tel or tel_links:
        out.append(check(P, "phone", "Teléfono en schema y enlace tel: clicable", "warn", 4, 8,
                         f"Schema: {schema_tel or 'no'} · enlaces tel: {', '.join(tel_links[:3]) or 'no'}",
                         "Ten el teléfono en ambos: dentro del schema (telephone) y como enlace <a href=\"tel:+51...\">."))
    else:
        out.append(check(P, "phone", "Teléfono en schema y enlace tel: clicable", "fail", 0, 8, "No se detectó teléfono estructurado.",
                         "Agrega telephone en el schema y un botón de llamada con href=\"tel:\"."))

    # 4. Consistencia NAP (teléfono) -----------------------------------------
    if schema_tel:
        sd = digits(schema_tel)
        found = sd and (sd in {digits(t) for t in tel_links} or sd in ctx["home"]["text_phones"]
                        or any(sd in p["text_phones"] for p in ctx["pages"]))
        out.append(check(P, "nap_consistency", "Consistencia NAP: el teléfono del schema aparece en la web",
                         "ok" if found else "warn", 5 if found else 1, 5,
                         "El mismo número aparece visible." if found else f"El número {schema_tel} del schema no aparece visible en el texto.",
                         "Usa exactamente el mismo teléfono en schema, web, Google Business Profile y directorios."))

    # 5. Geo coordenadas ----------------------------------------------------
    geo = (local or {}).get("geo") or {}
    has_geo = isinstance(geo, dict) and geo.get("latitude") and geo.get("longitude")
    out.append(check(P, "geo_coords", "Coordenadas GPS en el schema (geo)", "ok" if has_geo else "fail", 5 if has_geo else 0, 5,
                     f"lat {geo.get('latitude')}, lng {geo.get('longitude')}" if has_geo else "Sin GeoCoordinates.",
                     "Agrega \"geo\": {\"@type\":\"GeoCoordinates\",\"latitude\":...,\"longitude\":...} con los datos de tu ficha de Google."))

    # 6. Horario ------------------------------------------------------------
    hours = (local or {}).get("openingHoursSpecification") or (local or {}).get("openingHours")
    out.append(check(P, "hours", "Horario de atención estructurado", "ok" if hours else "fail", 5 if hours else 0, 5,
                     "Horario declarado." if hours else "Sin openingHoursSpecification.",
                     "Declara el horario en el schema; las IAs responden mucho \"¿a qué hora atiende...?\"."))

    # 7. Mapa ---------------------------------------------------------------
    maps = sorted({m for p in ctx["pages"] for m in p["maps_links"]})
    out.append(check(P, "maps", "Mapa o enlace a Google Maps", "ok" if maps else "warn", 5 if maps else 1, 5,
                     f"{len(maps)} enlace(s)/iframe de Maps" if maps else "No se encontró mapa embebido ni enlace a Maps.",
                     "Inserta el mapa de tu ficha de Google Business Profile en contacto y footer."))

    # 8. Ciudad en title / H1 -----------------------------------------------
    if city:
        nc = norm(city)
        in_title = nc in norm(home["title"])
        in_h1 = any(nc in norm(h) for h in home["h1"])
        in_text = nc in norm(home["full_text"])
        pts = (5 if in_title else 0) + (3 if in_h1 else 0) + (2 if in_text else 0)
        out.append(graded(P, "city_onpage", f"Ubicación \"{city}\" en title, H1 y contenido", pts / 10, 10,
                          f"Title: {'sí' if in_title else 'no'} · H1: {'sí' if in_h1 else 'no'} · Texto: {'sí' if in_text else 'no'}",
                          f"Incluye \"{city}\" (o el distrito) en el title y el H1 de la home y páginas de servicio."))
    else:
        out.append(check(P, "city_onpage", "Ubicación en title, H1 y contenido", "info", 0, 0,
                         "No se pudo determinar la ciudad. Escríbela en el formulario para medir esto."))

    # 9. Meta description ---------------------------------------------------
    md = home["meta_description"]
    if not md:
        out.append(check(P, "meta_desc", "Meta description con ubicación", "fail", 0, 5, "Sin meta description.",
                         "Escribe una meta description de 120-155 caracteres con servicio + distrito/ciudad."))
    else:
        has_city = bool(city) and norm(city) in norm(md)
        out.append(check(P, "meta_desc", "Meta description con ubicación", "ok" if has_city else "warn", 5 if has_city else 3, 5,
                         f"{len(md)} caracteres · {'menciona' if has_city else 'no menciona'} la ciudad",
                         "Menciona la ciudad o el distrito en la meta description."))

    # 10. sameAs / perfiles -------------------------------------------------
    same_as = sorted({str(s) for n in nodes for s in as_list(n.get("sameAs"))})
    social = sorted({s for p in ctx["pages"] for s in p["social_links"]})
    gbp = [s for s in same_as if any(k in str(s) for k in ("google.com/maps", "g.page", "maps.app.goo.gl", "g.co/kgs"))]
    ratio = min(1.0, (len(same_as) >= 2) * 0.5 + bool(gbp) * 0.3 + (len(social) >= 2) * 0.2)
    out.append(graded(P, "same_as", "Perfiles vinculados (sameAs + redes + Google Business)", ratio, 6,
                      f"sameAs: {len(same_as)} · Google Business en sameAs: {'sí' if gbp else 'no'} · redes enlazadas: {len(social)}",
                      "Agrega en el schema \"sameAs\" con tu ficha de Google Maps, Facebook, Instagram, TikTok, Doctoralia, etc."))

    # 11. Reseñas -----------------------------------------------------------
    has_rating = any(n.get("aggregateRating") or n.get("review") for n in nodes)
    out.append(check(P, "reviews", "Reseñas / valoraciones visibles", "ok" if has_rating else "warn", 4 if has_rating else 1, 4,
                     "Hay aggregateRating/review en el schema." if has_rating else "No hay reseñas estructuradas.",
                     "Muestra testimonios reales en la web (con nombre y fecha). Google no da estrellas a reseñas propias, pero las IAs sí leen esos testimonios."))

    # 12. WhatsApp ----------------------------------------------------------
    wa = sorted({w for p in ctx["pages"] for w in p["whatsapp_links"]})
    out.append(check(P, "whatsapp", "Contacto por WhatsApp", "ok" if wa else "warn", 3 if wa else 0, 3,
                     f"{len(wa)} enlace(s)" if wa else "Sin enlace wa.me.",
                     "Agrega un botón https://wa.me/51XXXXXXXXX con mensaje predefinido."))

    # 13. Idioma ------------------------------------------------------------
    lang = home["lang"].lower()
    ok_lang = lang.startswith("es")
    out.append(check(P, "lang", "Idioma declarado (lang=\"es\")", "ok" if ok_lang else "warn", 3 if ok_lang else 0, 3,
                     f"lang=\"{home['lang'] or 'vacío'}\"", "Declara <html lang=\"es-PE\"> (WordPress: Ajustes > Generales > Idioma)."))

    # 14. HTTPS + viewport ---------------------------------------------------
    https = ctx["final_url"].startswith("https://")
    out.append(check(P, "https", "HTTPS activo", "ok" if https else "fail", 4 if https else 0, 4,
                     ctx["final_url"], "Instala un certificado SSL y redirige todo a https."))
    out.append(check(P, "viewport", "Diseño móvil (meta viewport)", "ok" if home["viewport"] else "fail",
                     4 if home["viewport"] else 0, 4, "", "Agrega <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">."))

    # 15. Title y H1 --------------------------------------------------------
    tl = len(home["title"])
    ok_t = 30 <= tl <= 65
    out.append(check(P, "title", "Title de 30-65 caracteres", "ok" if ok_t else "warn", 4 if ok_t else 2 if tl else 0, 4,
                     f"{tl} caracteres: \"{home['title'][:90]}\"", "Ajusta el title: servicio principal + distrito/ciudad + marca."))
    n_h1 = len(home["h1"])
    out.append(check(P, "h1", "Un único H1", "ok" if n_h1 == 1 else "warn", 4 if n_h1 == 1 else 1, 4,
                     f"{n_h1} H1: {' | '.join(home['h1'][:3])}", "Deja un solo H1 descriptivo por página."))

    # 16. Velocidad móvil (PageSpeed) ----------------------------------------
    psi = ctx.get("psi") or {}
    if psi.get("ok"):
        perf = psi["performance"]
        out.append(graded(P, "pagespeed", "Rendimiento móvil (PageSpeed Insights)", perf / 100, 10,
                          f"Performance {perf}/100 · LCP {psi.get('lcp', '?')} · CLS {psi.get('cls', '?')} · TBT {psi.get('tbt', '?')}",
                          "Optimiza imágenes (WebP), caché, y reduce JS/CSS de plugins. Revisa el detalle en pagespeed.web.dev.",
                          warn_from=0.5, ok_from=0.8))
    else:
        out.append(check(P, "pagespeed", "Rendimiento móvil (PageSpeed Insights)", "info", 0, 0,
                         psi.get("error", "No se ejecutó PageSpeed.")))
    return out
