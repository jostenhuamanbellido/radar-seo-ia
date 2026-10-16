"""Pilar 3 · AEO (Answer Engine Optimization): ¿tu contenido está escrito como respuesta directa?"""
from .checks_base import check, graded
from .extract import nodes_of

P = "aeo"
FAQ_HINTS = ("preguntas", "faq", "frecuentes", "dudas")


def run(ctx: dict) -> list:
    home, pages, nodes = ctx["home"], ctx["pages"], ctx["all_nodes"]
    out = []

    # 1. FAQPage schema ------------------------------------------------------
    faq_nodes = nodes_of(nodes, {"FAQPage"})
    q_nodes = nodes_of(nodes, {"Question"})
    if faq_nodes:
        out.append(check(P, "faq_schema", "Schema FAQPage", "ok", 12, 12, f"{len(q_nodes)} preguntas marcadas"))
    else:
        out.append(check(P, "faq_schema", "Schema FAQPage", "fail", 0, 12, "No hay FAQPage en las páginas analizadas.",
                         "Crea un bloque de preguntas frecuentes por servicio y márcalo con FAQPage (Rank Math: bloque FAQ)."))

    # 2. Encabezados en forma de pregunta --------------------------------------
    qh, seen = [], set()
    for h in (h for p in pages for h in p["question_headings"]):
        if h["text"].lower() not in seen:
            seen.add(h["text"].lower())
            qh.append(h)
    out.append(graded(P, "question_headings", "Encabezados escritos como preguntas reales", min(1.0, len(qh) / 5), 12,
                      f"{len(qh)} encabezados-pregunta: " + " | ".join(h["text"] for h in qh[:4]),
                      "Usa H2/H3 con las preguntas que la gente le hace a ChatGPT/Google: \"¿Cuánto cuesta...?\", \"¿Cuántas sesiones...?\"."))

    # 3. Respuesta directa tras la pregunta (40-80 palabras ideal) ------------
    answered = [h for h in qh if 20 <= h.get("answer_words", 0) <= 90]
    if qh:
        ratio = len(answered) / len(qh)
        out.append(graded(P, "direct_answers", "Respuesta directa (20-90 palabras) tras cada pregunta", ratio, 12,
                          f"{len(answered)} de {len(qh)} preguntas tienen una respuesta concisa justo debajo",
                          "Responde en el primer párrafo (40-60 palabras) y luego amplía. Es el formato que copian los fragmentos y las IAs."))
    else:
        out.append(check(P, "direct_answers", "Respuesta directa tras cada pregunta", "fail", 0, 12, "No hay preguntas que responder.",
                         "Primero crea secciones pregunta → respuesta corta → detalle."))

    # 4. Resumen al inicio ------------------------------------------------------
    fp = home["first_paragraph_words"]
    ok = 15 <= fp <= 70
    out.append(check(P, "summary_first", "Párrafo inicial que resume quién eres y qué ofreces", "ok" if ok else "warn",
                     8 if ok else 3 if fp else 0, 8, f"Primer párrafo: {fp} palabras. \"{home['first_paragraph'][:140]}\"",
                     "Abre con 1-2 frases tipo definición: \"[Marca] es una clínica de [especialidad] en [distrito], [ciudad], que ofrece...\"."))

    # 5. Listas ---------------------------------------------------------------
    lists = sum(p["lists"] for p in pages)
    out.append(graded(P, "lists", "Listas (viñetas o numeradas) en el contenido", min(1.0, lists / 3), 8,
                      f"{lists} listas en el contenido principal",
                      "Presenta beneficios, pasos, requisitos y precios en listas: son fáciles de extraer para las IAs."))

    # 6. Tablas ---------------------------------------------------------------
    tables = sum(p["tables"] for p in pages)
    out.append(check(P, "tables", "Tablas comparativas o de precios", "ok" if tables else "warn", 5 if tables else 1, 5,
                     f"{tables} tabla(s)", "Agrega una tabla (precios desde, duración, sesiones, comparativa de tratamientos)."))

    # 7. Pasos / HowTo -------------------------------------------------------
    ol = sum(p["ordered_lists"] for p in pages)
    howto = bool(nodes_of(nodes, {"HowTo"}))
    ok = ol > 0 or howto
    out.append(check(P, "steps", "Procesos explicados paso a paso", "ok" if ok else "warn", 5 if ok else 1, 5,
                     f"Listas numeradas: {ol} · HowTo: {'sí' if howto else 'no'}",
                     "Explica el proceso (\"¿Cómo es el tratamiento?\") con una lista numerada de pasos."))

    # 8. Meta description como respuesta --------------------------------------
    md = len(home["meta_description"])
    ok = 70 <= md <= 165
    out.append(check(P, "meta_answer", "Meta description de 70-165 caracteres", "ok" if ok else "warn", 6 if ok else 2 if md else 0, 6,
                     f"{md} caracteres", "Escribe la meta description como respuesta corta a la búsqueda principal."))

    # 9. Breadcrumbs --------------------------------------------------------
    bc = bool(nodes_of(nodes, {"BreadcrumbList"}))
    out.append(check(P, "breadcrumbs", "Schema BreadcrumbList", "ok" if bc else "warn", 5 if bc else 0, 5, "",
                     "Activa las migas de pan con schema (Rank Math/Yoast > Breadcrumbs)."))

    # 10. Página de preguntas frecuentes ---------------------------------------
    links = [u for u, t in home["internal_links"] if any(h in (u + " " + t).lower() for h in FAQ_HINTS)]
    out.append(check(P, "faq_page", "Página o sección de preguntas frecuentes enlazada", "ok" if links or faq_nodes else "warn",
                     5 if links or faq_nodes else 0, 5, links[0] if links else ("FAQ en la página" if faq_nodes else "No enlazada desde la home"),
                     "Crea /preguntas-frecuentes/ y enlázala desde el menú o footer."))

    # 11. Legibilidad ---------------------------------------------------------
    asw = home["avg_sentence_words"]
    ratio = 1.0 if 0 < asw <= 22 else 0.6 if asw <= 30 else 0.2
    out.append(graded(P, "readability", "Frases cortas y claras (≤ 22 palabras de promedio)", ratio, 6,
                      f"Promedio: {asw} palabras por frase", "Acorta las frases. Una idea por frase facilita que la IA la cite literal."))

    # 12. Imágenes con alt -----------------------------------------------------
    tot = sum(p["img_total"] for p in pages)
    alt = sum(p["img_with_alt"] for p in pages)
    if tot:
        out.append(graded(P, "img_alt", "Imágenes con texto alternativo", alt / tot, 5, f"{alt} de {tot} imágenes con alt",
                          "Describe cada imagen en el atributo alt (las IAs multimodales y Google Imágenes lo usan)."))
    return out
