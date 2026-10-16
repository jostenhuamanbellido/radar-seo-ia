"""Cliente mínimo de Supabase (REST + Auth) usando requests.

El servidor usa la service_role key: las tablas tienen RLS activado SIN políticas públicas,
así que solo el backend puede leer/escribir, y siempre filtra por user_id.
"""
import hashlib
from datetime import date, datetime, timedelta, timezone

import requests

from . import config

TIMEOUT = 20


def enabled() -> bool:
    return bool(config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY)


def _h(key: str | None = None, extra: dict | None = None) -> dict:
    """Soporta claves legacy (JWT eyJ...) y las nuevas sb_publishable_/sb_secret_ (solo van en 'apikey')."""
    k = key or config.SUPABASE_SERVICE_KEY
    h = {"apikey": k, "Content-Type": "application/json"}
    if k.startswith("eyJ"):
        h["Authorization"] = f"Bearer {k}"
    h.update(extra or {})
    return h


def _rest(table: str) -> str:
    return f"{config.SUPABASE_URL}/rest/v1/{table}"


class DBError(Exception):
    pass


def _check(r):
    if r.status_code >= 400:
        raise DBError(f"Supabase {r.status_code}: {r.text[:300]}")
    return r


# --- CRUD genérico -----------------------------------------------------------
def select(table: str, params: dict) -> list:
    return _check(requests.get(_rest(table), headers=_h(), params=params, timeout=TIMEOUT)).json()


def one(table: str, params: dict):
    rows = select(table, {**params, "limit": 1})
    return rows[0] if rows else None


def insert(table: str, row: dict, upsert: bool = False, on_conflict: str | None = None) -> dict:
    prefer = "return=representation" + (",resolution=merge-duplicates" if upsert else "")
    params = {"on_conflict": on_conflict} if on_conflict else None
    r = _check(requests.post(_rest(table), headers=_h(extra={"Prefer": prefer}), params=params, json=row,
                             timeout=TIMEOUT))
    data = r.json()
    return data[0] if isinstance(data, list) and data else data


def update(table: str, match: dict, values: dict) -> list:
    r = _check(requests.patch(_rest(table), headers=_h(extra={"Prefer": "return=representation"}), params=match,
                              json=values, timeout=TIMEOUT))
    return r.json()


def delete(table: str, match: dict):
    _check(requests.delete(_rest(table), headers=_h(), params=match, timeout=TIMEOUT))


def count(table: str, params: dict) -> int:
    r = _check(requests.get(_rest(table), headers=_h(extra={"Prefer": "count=exact", "Range": "0-0"}),
                            params={**params, "select": "id"}, timeout=TIMEOUT))
    rng = r.headers.get("content-range", "*/0")
    try:
        return int(rng.split("/")[-1])
    except ValueError:
        return 0


# --- Auth --------------------------------------------------------------------
def _auth(path: str) -> str:
    return f"{config.SUPABASE_URL}/auth/v1/{path}"


def auth_signup(email: str, password: str, redirect_to: str) -> dict:
    r = requests.post(_auth("signup"), headers=_h(config.SUPABASE_ANON_KEY), params={"redirect_to": redirect_to},
                      json={"email": email, "password": password}, timeout=TIMEOUT)
    return {"status": r.status_code, **(r.json() if r.content else {})}


def auth_login(email: str, password: str) -> dict:
    r = requests.post(_auth("token"), headers=_h(config.SUPABASE_ANON_KEY), params={"grant_type": "password"},
                      json={"email": email, "password": password}, timeout=TIMEOUT)
    return {"status": r.status_code, **(r.json() if r.content else {})}


def auth_user(access_token: str) -> dict | None:
    r = requests.get(_auth("user"), headers={"apikey": config.SUPABASE_ANON_KEY, "Authorization": f"Bearer {access_token}"},
                     timeout=TIMEOUT)
    return r.json() if r.status_code == 200 else None


def auth_recover(email: str, redirect_to: str):
    requests.post(_auth("recover"), headers=_h(config.SUPABASE_ANON_KEY), params={"redirect_to": redirect_to},
                  json={"email": email}, timeout=TIMEOUT)


def auth_set_password(access_token: str, password: str) -> bool:
    r = requests.put(_auth("user"), headers={"apikey": config.SUPABASE_ANON_KEY, "Authorization": f"Bearer {access_token}",
                                             "Content-Type": "application/json"},
                     json={"password": password}, timeout=TIMEOUT)
    return r.status_code == 200


# --- Dominio -----------------------------------------------------------------
def profile(user_id: str) -> dict:
    p = one("profiles", {"user_id": f"eq.{user_id}"})
    return p or {"user_id": user_id, "plan": "free", "agency_name": None}


def ensure_profile(user_id: str, email: str):
    if not one("profiles", {"user_id": f"eq.{user_id}"}):
        insert("profiles", {"user_id": user_id, "email": email}, upsert=True)


def month_key() -> str:
    return date.today().strftime("%Y-%m")


def audits_this_month(user_id: str) -> int:
    start = date.today().replace(day=1).isoformat()
    return count("audits", {"user_id": f"eq.{user_id}", "created_at": f"gte.{start}"})


def save_audit(result: dict, user_id: str | None = None, site_id: str | None = None) -> dict:
    s = result["scores"]
    row = insert("audits", {
        "user_id": user_id, "site_id": site_id, "url": result["final_url"], "domain": result["domain"],
        "total": s["total"], "local": s.get("local"), "geo": s.get("geo"), "aeo": s.get("aeo"), "ai": s.get("ai"),
        "data": result,
    })
    if site_id:
        update("sites", {"id": f"eq.{site_id}"}, {"last_audit_at": datetime.now(timezone.utc).isoformat(),
                                                  "last_score": s["total"]})
    return row


def audit_by_public_id(public_id: str):
    return one("audits", {"public_id": f"eq.{public_id}", "select": "*"})


def previous_audit(site_id: str, before_iso: str):
    return one("audits", {"site_id": f"eq.{site_id}", "created_at": f"lt.{before_iso}", "order": "created_at.desc",
                          "select": "total,local,geo,aeo,ai,created_at"})


def site_history(site_id: str) -> list:
    return select("audits", {"site_id": f"eq.{site_id}", "order": "created_at.asc",
                             "select": "public_id,created_at,total,local,geo,aeo,ai"})


def sites_due(limit: int = 40) -> list:
    """Webs con plan de pago que no se auditan hace 7 días."""
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return select("sites", {
        "select": "*,profiles!inner(plan)",
        "profiles.plan": "in.(negocio,agencia)",
        "or": f"(last_audit_at.is.null,last_audit_at.lt.{week_ago})",
        "order": "last_audit_at.asc.nullsfirst",
        "limit": limit,
    })


def rate_limit(key: str, limit: int) -> bool:
    """True si todavía está dentro del límite diario para esa clave (p. ej. IP anónima)."""
    hashed = hashlib.sha256((key + (config.FLASK_SECRET or "")).encode()).hexdigest()[:32]
    today = date.today().isoformat()
    row = one("rate_limits", {"key": f"eq.{hashed}", "day": f"eq.{today}"})
    n = (row or {}).get("count", 0)
    if n >= limit:
        return False
    insert("rate_limits", {"key": hashed, "day": today, "count": n + 1}, upsert=True)
    return True


# --- Rankings ----------------------------------------------------------------
def rankings(country: str | None = None) -> list:
    params = {"select": "country,city,category,slug,updated_at", "order": "updated_at.desc", "limit": 200}
    if country:
        params["country"] = f"eq.{country}"
    return select("rankings", params)


def ranking(country: str, slug: str):
    return one("rankings", {"country": f"eq.{country}", "slug": f"eq.{slug}", "select": "*"})


def save_lead(email: str, plan: str, country: str, note: str = ""):
    insert("leads", {"email": email, "plan": plan, "country": country, "note": note[:500]})
