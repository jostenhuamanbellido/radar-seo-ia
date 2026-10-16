"""Estructura común de un chequeo y cálculo de puntajes."""
import unicodedata

PILLARS = {
    "local": "SEO Local",
    "geo": "GEO · Motores generativos",
    "aeo": "AEO · Motores de respuesta",
    "ai": "Visibilidad real en IAs",
}

# Peso de cada pilar en el puntaje total (se re-normaliza si un pilar no se pudo medir)
WEIGHTS = {"local": 0.30, "geo": 0.25, "aeo": 0.20, "ai": 0.25}


def check(pillar, cid, name, status, points, max_points, detail="", fix=""):
    """status: ok | warn | fail | info. 'info' no suma ni resta."""
    return {
        "pillar": pillar,
        "id": cid,
        "name": name,
        "status": status,
        "points": round(points, 1),
        "max": max_points if status != "info" else 0,
        "detail": detail,
        "fix": fix if status in ("warn", "fail") else "",
    }


def graded(pillar, cid, name, ratio, max_points, detail, fix, warn_from=0.4, ok_from=0.85):
    """Chequeo con puntaje proporcional (ratio 0..1)."""
    ratio = max(0.0, min(1.0, ratio))
    status = "ok" if ratio >= ok_from else ("warn" if ratio >= warn_from else "fail")
    return check(pillar, cid, name, status, ratio * max_points, max_points, detail, fix)


def pillar_score(checks: list, pillar: str):
    items = [c for c in checks if c["pillar"] == pillar and c["status"] != "info"]
    total = sum(c["max"] for c in items)
    if not total:
        return None
    return round(100 * sum(c["points"] for c in items) / total)


def total_score(scores: dict):
    num = den = 0.0
    for p, w in WEIGHTS.items():
        if scores.get(p) is not None:
            num += scores[p] * w
            den += w
    return round(num / den) if den else 0


def grade(score) -> str:
    if score is None:
        return "—"
    if score >= 85:
        return "Excelente"
    if score >= 70:
        return "Bien"
    if score >= 50:
        return "Regular"
    return "Débil"


def norm(text: str) -> str:
    """minúsculas y sin tildes, para comparar textos."""
    t = unicodedata.normalize("NFKD", (text or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))
