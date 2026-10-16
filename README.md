# Radar SEO·IA

**Auditoría de SEO local, GEO y AEO con medición real de visibilidad en ChatGPT, Claude, Gemini y Perplexity.**

🔗 **Demo en vivo:** [radar-seo-ia.vercel.app](https://radar-seo-ia.vercel.app) · versión pública con la auditoría técnica completa.

Pegas una URL y el sistema:

1. **Rastrea la web** (home + hasta 5 páginas clave: contacto, servicios, FAQ, blog…), robots.txt, sitemap y llms.txt.
2. **Evalúa 4 pilares** con puntaje 0-100 y te dice qué corregir primero:
   | Pilar | Qué mide |
   |---|---|
   | **SEO Local** | Schema LocalBusiness/MedicalClinic, NAP completo y consistente, geo, horario, mapa, ciudad en title/H1, sameAs + Google Business, reseñas, WhatsApp, HTTPS, móvil, velocidad (PageSpeed). |
   | **GEO** (Generative Engine Optimization) | Si los bots de IA pueden entrar (robots.txt para 14 rastreadores y prueba de firewall/Cloudflare), contenido legible sin JS, entidad clara, autoría E-E-A-T, frescura, datos citables, sitemap, llms.txt, JSON-LD válido. |
   | **AEO** (Answer Engine Optimization) | FAQPage, encabezados en forma de pregunta, respuesta directa de 20-90 palabras, resumen inicial, listas, tablas, pasos, breadcrumbs, legibilidad. |
   | **Visibilidad real en IAs** | Hace preguntas reales ("mejor *servicio* en *ciudad*", "¿qué sabes de *marca*?") a cada IA **con búsqueda web activada** y mide si te **menciona**, si te **cita como fuente** y **qué competidores aparecen en tu lugar**. |
3. **Guarda el historial** (SQLite) para ver la **evolución** de cada web después de cada mejora.
4. **Exporta el informe** en HTML (listo para enviar a un cliente) y JSON.

---

## Instalación (Windows)

Requisito: **Python 3.10+** ([python.org](https://www.python.org/downloads/), marca *"Add python.exe to PATH"*).

1. Doble clic en **`iniciar.bat`**. La primera vez crea el entorno e instala dependencias.
2. Se abre `http://localhost:5050`. Pega la URL y pulsa **Auditar**.

### Activar la medición en IAs (opcional)

Abre el archivo **`.env`** (se crea solo) y pega las claves que tengas. Con una sola ya funciona:

| IA | Clave | Dónde obtenerla |
|---|---|---|
| ChatGPT | `OPENAI_API_KEY` | platform.openai.com/api-keys |
| Claude | `ANTHROPIC_API_KEY` | console.anthropic.com |
| Gemini | `GEMINI_API_KEY` | aistudio.google.com/apikey (tiene capa gratuita) |
| Perplexity | `PERPLEXITY_API_KEY` | perplexity.ai/settings/api |

Los modelos se cambian en el mismo `.env` (`OPENAI_MODEL`, `GEMINI_MODEL`…). Cada auditoría hace ~4 preguntas por IA: el costo es de céntimos.

Sin claves, el informe trae **enlaces directos** para abrir cada pregunta en ChatGPT, Perplexity, Claude, Google AI Mode y Copilot y revisarlo a mano.

### Uso por consola (varias webs)

```bat
auditar.bat https://misitio.pe
auditar.bat https://misitio.pe --ciudad "Miraflores, Lima" --servicio "dermatología"
auditar.bat --archivo webs.txt
auditar.bat https://misitio.pe --sin-ia --sin-pagespeed --pregunta "¿Cuánto cuesta un injerto capilar en Lima?"
```

Los informes quedan en `reportes/` y el historial en `data/radar.db`.

### Despliegue en Vercel

El mismo código corre como función serverless (`api/index.py` + `vercel.json`). En la nube (variable `VERCEL` presente):

- La auditoría se ejecuta en una sola petición (hasta 300 s) en vez de hilo en segundo plano.
- No hay historial (el disco de Vercel es efímero); el informe se descarga desde el navegador.
- Las claves de IA del servidor **no se usan** salvo que definas `PUBLIC_AI=1`, para que ningún visitante gaste tus créditos.
- Se bloquean IPs privadas/internas (protección SSRF).

Para desplegar tu copia: importa el repo en [vercel.com/new](https://vercel.com/new) (framework: *Other*), sin configuración extra.

---

## Estructura

```
radar-seo-ia/
├─ app.py               Interfaz web (Flask) con auditoría en segundo plano
├─ api/index.py         Entrada serverless para Vercel
├─ cli.py               Uso por consola / lotes
├─ radar/
│  ├─ fetcher.py        Descargas, user-agents de bots de IA
│  ├─ extract.py        Parser: JSON-LD, NAP, enlaces, preguntas, texto, fechas
│  ├─ checks_local.py   Pilar SEO Local
│  ├─ checks_geo.py     Pilar GEO
│  ├─ checks_aeo.py     Pilar AEO
│  ├─ ai_visibility.py  Consultas a OpenAI, Anthropic, Gemini y Perplexity con búsqueda web
│  ├─ pagespeed.py      Google PageSpeed Insights (móvil)
│  ├─ audit.py          Orquestador + detección automática de marca, servicio y ciudad
│  ├─ storage.py        Historial SQLite
│  └─ report.py         Informe HTML/JSON
└─ templates/           Vistas (informe, historial con gráfico, progreso)
```

### Decisiones técnicas

- **Sin navegador headless a propósito**: la mayoría de bots de IA (GPTBot, ClaudeBot, PerplexityBot) no ejecutan JavaScript, así que el sistema lee la web *como la leen ellos*. Si el contenido solo aparece con JS, se marca como problema.
- **Puntaje ponderado**: Local 30 % · GEO 25 % · AEO 20 % · IAs 25 %. Si un pilar no se puede medir (p. ej. sin claves), el total se re-normaliza.
- **Mención ≠ cita**: una IA puede nombrarte sin enlazarte. Se miden por separado (mención 60 %, cita 40 %).
- **Prueba de firewall indicativa**: se simula el user-agent de cada bot; Cloudflare verifica bots reales por IP, así que un "bloqueado" es una alerta para revisar, no una prueba definitiva.
- **Las respuestas de IA varían** entre ejecuciones y según ubicación: compara tendencias en el historial, no una sola medición.

## Hoja de ruta

- [ ] Programar auditorías semanales automáticas y alerta por correo si baja el puntaje
- [ ] Comparar tu web contra 2-3 competidores en el mismo informe
- [ ] Integrar Google Business Profile API (reseñas, categorías, fotos)
- [ ] Exportar a PDF con la marca del cliente

---

Hecho por **Josten Huamán** · Ingeniero de software y SEO.
