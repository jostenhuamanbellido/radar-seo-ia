"""Extrae de un HTML todas las señales que usan los chequeos (schema, NAP, preguntas, etc.)."""
import copy
import json
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

QUESTION_STARTS = (
    "¿", "qué ", "que ", "cómo ", "cuánto", "cuanto", "cuál", "cual ", "cuáles", "por qué",
    "dónde", "donde ", "cuándo", "quién", "es posible", "se puede", "puedo ", "es bueno",
    "what ", "how ", "why ", "when ", "where ", "which ", "who ", "can ", "is ", "are ", "does ", "do ",
)

SOCIAL_HOSTS = (
    "facebook.com", "instagram.com", "tiktok.com", "youtube.com", "youtu.be", "twitter.com", "x.com",
    "linkedin.com", "wa.me", "whatsapp.com", "pinterest.com", "threads.net",
)
MAPS_PATTERNS = ("google.com/maps", "maps.google", "goo.gl/maps", "maps.app.goo.gl", "g.page", "g.co/kgs")
AUTHORITY_PATTERNS = (
    ".gob.pe", ".gov", ".edu", "who.int", "paho.org", "nih.gov", "pubmed", "ncbi.nlm", "scielo",
    "minsa", "essalud", "wikipedia.org", "cochrane", "mayoclinic", "nature.com", "sciencedirect",
)
SKIP_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".pdf", ".zip", ".mp4", ".mp3", ".doc", ".docx", ".xls", ".xlsx")

STAT_RE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s?(?:%|por ciento|años|pacientes|clientes|casos|tratamientos|procedimientos|"
    r"sesiones|mil|millones|semanas|meses|minutos|horas|especialistas)\b",
    re.I,
)
PHONE_RE = re.compile(r"(?:\+?51[\s.-]?)?(?:9\d{2}[\s.-]?\d{3}[\s.-]?\d{3}|\(?0?1\)?[\s.-]?\d{3}[\s.-]?\d{4})")
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _types(node: dict) -> list:
    t = node.get("@type", [])
    if isinstance(t, str):
        t = [t]
    return [str(x) for x in t if x]


def _walk_jsonld(obj, out: list):
    if isinstance(obj, list):
        for o in obj:
            _walk_jsonld(o, out)
    elif isinstance(obj, dict):
        if "@type" in obj:
            out.append(obj)
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                _walk_jsonld(v, out)


def digits(s: str) -> str:
    d = re.sub(r"\D", "", s or "")
    return d[-9:] if len(d) >= 9 else d


def is_question(text: str) -> bool:
    t = (text or "").strip().lower()
    return bool(t) and (t.endswith("?") or t.startswith(QUESTION_STARTS))


def words(text: str) -> int:
    return len(re.findall(r"\w+", text or ""))


def _first_text_after(heading) -> str:
    """Primer párrafo de texto que sigue a un encabezado (antes del siguiente encabezado)."""
    n = 0
    for el in heading.find_all_next():
        n += 1
        if n > 80:
            break
        if el.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            return ""
        if el.name == "p":
            txt = el.get_text(" ", strip=True)
            if words(txt) >= 3:
                return txt
    return ""


def parse_page(html_bytes: bytes, url: str, domain: str) -> dict:
    soup = BeautifulSoup(html_bytes, "lxml")
    data: dict = {"url": url}

    # --- Meta básicos -------------------------------------------------------
    data["title"] = soup.title.get_text(strip=True) if soup.title else ""
    def meta(name=None, prop=None):
        tag = soup.find("meta", attrs={"name": name}) if name else soup.find("meta", attrs={"property": prop})
        return (tag.get("content") or "").strip() if tag else ""
    data["meta_description"] = meta(name="description")
    data["meta_robots"] = meta(name="robots").lower()
    data["og_site_name"] = meta(prop="og:site_name")
    data["og_title"] = meta(prop="og:title")
    data["og_image"] = meta(prop="og:image")
    data["meta_author"] = meta(name="author")
    data["modified_time"] = meta(prop="article:modified_time") or meta(prop="og:updated_time")
    data["published_time"] = meta(prop="article:published_time")
    data["viewport"] = bool(soup.find("meta", attrs={"name": "viewport"}))
    html_tag = soup.find("html")
    data["lang"] = (html_tag.get("lang") or "").strip() if html_tag else ""
    canon = soup.find("link", rel=lambda v: v and "canonical" in v)
    data["canonical"] = canon.get("href", "") if canon else ""
    data["hreflang"] = [l.get("hreflang") for l in soup.find_all("link", hreflang=True)]

    # --- JSON-LD ------------------------------------------------------------
    nodes, jsonld_errors, jsonld_blocks = [], 0, 0
    for s in soup.find_all("script", type=lambda v: v and "ld+json" in v.lower()):
        jsonld_blocks += 1
        raw = s.string or s.get_text() or ""
        try:
            _walk_jsonld(json.loads(raw), nodes)
        except (json.JSONDecodeError, ValueError):
            jsonld_errors += 1
    data["schema_nodes"] = nodes
    data["schema_types"] = sorted({t for n in nodes for t in _types(n)})
    data["jsonld_blocks"] = jsonld_blocks
    data["jsonld_errors"] = jsonld_errors
    data["microdata_types"] = sorted({
        (t.get("itemtype") or "").rstrip("/").split("/")[-1] for t in soup.find_all(attrs={"itemtype": True})
    })

    # --- Enlaces ------------------------------------------------------------
    internal, external, tel, mailto, whatsapp, maps, social, authority = [], [], [], [], [], [], [], []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        low = href.lower()
        if low.startswith("tel:"):
            tel.append(href[4:])
            continue
        if low.startswith("mailto:"):
            mailto.append(href[7:])
            continue
        if "wa.me" in low or "whatsapp.com" in low:
            whatsapp.append(href)
        if any(p in low for p in MAPS_PATTERNS):
            maps.append(href)
        absu = urljoin(url, href)
        p = urlparse(absu)
        if p.scheme not in ("http", "https"):
            continue
        host = p.netloc.lower().split(":")[0]
        host = host[4:] if host.startswith("www.") else host
        if host == domain or host.endswith("." + domain):
            clean = absu.split("#")[0]
            if not clean.lower().endswith(SKIP_EXT) and "wp-admin" not in clean and "wp-login" not in clean:
                internal.append((clean, a.get_text(" ", strip=True)[:80]))
        else:
            if any(s in host for s in SOCIAL_HOSTS):
                social.append(absu)
            elif not any(p_ in low for p_ in MAPS_PATTERNS):
                external.append(absu)
                if any(ap in host or ap in low for ap in AUTHORITY_PATTERNS):
                    authority.append(absu)
    for f in soup.find_all("iframe", src=True):
        if any(p in f["src"].lower() for p in MAPS_PATTERNS):
            maps.append(f["src"])
    seen = set()
    data["internal_links"] = [(u, t) for u, t in internal if not (u in seen or seen.add(u))]
    data["external_links"] = sorted(set(external))
    data["authority_links"] = sorted(set(authority))
    data["social_links"] = sorted(set(social))
    data["tel_links"] = sorted(set(tel))
    data["mailto_links"] = sorted(set(mailto))
    data["whatsapp_links"] = sorted(set(whatsapp))
    data["maps_links"] = sorted(set(maps))

    # --- Imágenes -----------------------------------------------------------
    imgs = soup.find_all("img")
    data["img_total"] = len(imgs)
    data["img_with_alt"] = sum(1 for i in imgs if (i.get("alt") or "").strip())

    # --- Encabezados (antes de limpiar) ------------------------------------
    headings = []
    for h in soup.find_all(["h1", "h2", "h3", "h4"]):
        txt = h.get_text(" ", strip=True)
        if not txt:
            continue
        item = {"tag": h.name, "text": txt[:160], "question": is_question(txt)}
        if item["question"] and h.name != "h1":
            ans = _first_text_after(h)
            item["answer_words"] = words(ans)
        headings.append(item)
    data["headings"] = headings
    data["h1"] = [h["text"] for h in headings if h["tag"] == "h1"]
    data["question_headings"] = [h for h in headings if h["question"] and h["tag"] != "h1"]

    # --- Fechas -------------------------------------------------------------
    times = [t.get("datetime", "") for t in soup.find_all("time") if t.get("datetime")]
    data["time_tags"] = times

    # --- Texto visible ------------------------------------------------------
    full = copy.copy(soup)
    for t in full(["script", "style", "noscript", "template", "svg", "iframe"]):
        t.decompose()
    body_text = full.get_text(" ", strip=True)
    data["word_count"] = words(body_text)
    data["full_text"] = body_text[:60000]
    data["script_count"] = len(soup.find_all("script"))

    main = full.find("main") or full.find("article") or full.find("body") or full
    main = copy.copy(main)
    for t in main(["header", "nav", "footer", "aside", "form"]):
        t.decompose()
    main_text = main.get_text(" ", strip=True)
    data["main_word_count"] = words(main_text)
    data["lists"] = sum(1 for l in main.find_all(["ul", "ol"]) if len(l.find_all("li")) >= 2)
    data["ordered_lists"] = sum(1 for l in main.find_all("ol") if len(l.find_all("li")) >= 2)
    data["tables"] = len(main.find_all("table"))
    data["stats_count"] = len(STAT_RE.findall(main_text))
    paras = [p.get_text(" ", strip=True) for p in main.find_all("p")]
    paras = [p for p in paras if words(p) >= 8]
    data["first_paragraph_words"] = words(paras[0]) if paras else 0
    data["first_paragraph"] = paras[0][:400] if paras else ""
    sentences = [s for s in re.split(r"[.!?¿¡]+\s", main_text) if words(s) >= 3]
    data["avg_sentence_words"] = round(sum(words(s) for s in sentences) / len(sentences), 1) if sentences else 0
    data["text_phones"] = sorted({digits(m) for m in PHONE_RE.findall(body_text) if len(digits(m)) >= 7})
    return data


# --- Utilidades sobre nodos de schema ----------------------------------------
LOCAL_TYPES = {
    "LocalBusiness", "MedicalClinic", "MedicalBusiness", "Dentist", "Physician", "Hospital", "MedicalOrganization",
    "HealthAndBeautyBusiness", "BeautySalon", "DaySpa", "HairSalon", "NailSalon", "Optician", "Pharmacy",
    "Store", "Restaurant", "FoodEstablishment", "CafeOrCoffeeShop", "ProfessionalService", "LegalService",
    "Attorney", "AccountingService", "RealEstateAgent", "AutomotiveBusiness", "AutoRepair", "HomeAndConstructionBusiness",
    "Hotel", "LodgingBusiness", "SportsActivityLocation", "ExerciseGym", "EducationalOrganization", "School",
    "TravelAgency", "VeterinaryCare", "ChildCare", "EmploymentAgency", "FinancialService", "InsuranceAgency",
    "EntertainmentBusiness", "ShoppingCenter", "Plumber", "Electrician", "GeneralContractor", "MovingCompany",
    "DiagnosticLab", "Clinic",
}
ORG_TYPES = LOCAL_TYPES | {"Organization", "Corporation", "NGO", "MedicalOrganization"}


def nodes_of(nodes: list, wanted: set) -> list:
    return [n for n in nodes if set(_types(n)) & wanted]


def first_local_node(nodes: list):
    loc = nodes_of(nodes, LOCAL_TYPES)
    if loc:
        return max(loc, key=lambda n: len(n))
    return None


def as_list(v):
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def address_of(node: dict) -> dict:
    addr = node.get("address") if node else None
    if isinstance(addr, list):
        addr = addr[0] if addr else None
    if isinstance(addr, str):
        return {"streetAddress": addr}
    return addr if isinstance(addr, dict) else {}


def extract_dates(page: dict) -> list:
    out = []
    for v in [page.get("modified_time"), page.get("published_time"), *page.get("time_tags", [])]:
        m = DATE_RE.search(v or "")
        if m:
            out.append(m.group(1))
    for n in page.get("schema_nodes", []):
        for k in ("dateModified", "datePublished", "lastReviewed"):
            m = DATE_RE.search(str(n.get(k, "")))
            if m:
                out.append(m.group(1))
    return sorted(set(out))
