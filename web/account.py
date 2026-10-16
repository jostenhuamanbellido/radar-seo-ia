"""Cuentas (Supabase Auth) y panel de usuario."""
from flask import Blueprint, abort, jsonify, redirect, render_template, request, session, url_for

from radar import config, db, plans
from radar.countries import COUNTRIES
from radar.fetcher import normalize_url, root_domain

from .common import current_user, login_required, seo

bp = Blueprint("account", __name__)


def _login_session(user: dict):
    session.permanent = True
    session["uid"] = user["id"]
    session["email"] = user.get("email", "")
    db.ensure_profile(user["id"], user.get("email", ""))


def _safe_next(nxt: str | None) -> str:
    return nxt if nxt and nxt.startswith("/") and not nxt.startswith("//") else "/panel/"


@bp.route("/entrar/", methods=["GET", "POST"])
def entrar():
    if current_user():
        return redirect("/panel/")
    mode = request.values.get("modo", "entrar")
    error, info = "", ""
    nxt = _safe_next(request.values.get("next"))
    if request.method == "POST":
        if not db.enabled():
            error = "Las cuentas aún no están activas."
        else:
            email = (request.form.get("email") or "").strip().lower()
            pw = request.form.get("password") or ""
            if mode == "registro":
                if len(pw) < 8:
                    error = "La clave debe tener al menos 8 caracteres."
                else:
                    r = db.auth_signup(email, pw, config.SITE_URL + "/auth/callback/")
                    if r["status"] >= 400:
                        error = r.get("msg") or r.get("error_description") or "No se pudo crear la cuenta."
                    elif r.get("access_token") and r.get("user"):
                        _login_session(r["user"])
                        return redirect(nxt)
                    else:
                        info = "Te enviamos un correo para confirmar tu cuenta. Ábrelo y vuelve aquí."
                        mode = "entrar"
            else:
                r = db.auth_login(email, pw)
                if r["status"] == 200 and r.get("user"):
                    _login_session(r["user"])
                    return redirect(nxt)
                msg = (r.get("error_description") or r.get("msg") or "").lower()
                error = ("Confirma tu correo antes de entrar." if "confirm" in msg
                         else "Correo o clave incorrectos.")
    meta = seo(f"Entrar | {config.BRAND}", "Accede a tu panel.", "/entrar/", noindex=True)
    return render_template("entrar.html", meta=meta, mode=mode, error=error, info=info, next=nxt,
                           user=None, countries=COUNTRIES)


@bp.get("/auth/callback/")
def auth_callback():
    """Supabase redirige aquí con el token en el #hash (confirmación de correo / recuperación)."""
    meta = seo(f"Confirmando | {config.BRAND}", "", "/auth/callback/", noindex=True)
    return render_template("auth_callback.html", meta=meta, user=None, countries=COUNTRIES)


@bp.post("/auth/session/")
def auth_session():
    token = (request.json or {}).get("access_token", "")
    kind = (request.json or {}).get("type", "")
    user = db.auth_user(token) if token and db.enabled() else None
    if not user:
        return jsonify({"ok": False}), 400
    _login_session(user)
    if kind == "recovery":
        session["recovery_token"] = token
        return jsonify({"ok": True, "next": "/restablecer/"})
    return jsonify({"ok": True, "next": "/panel/"})


@bp.route("/recuperar/", methods=["GET", "POST"])
def recuperar():
    sent = False
    if request.method == "POST" and db.enabled():
        db.auth_recover((request.form.get("email") or "").strip().lower(), config.SITE_URL + "/auth/callback/")
        sent = True
    meta = seo(f"Recuperar clave | {config.BRAND}", "", "/recuperar/", noindex=True)
    return render_template("recuperar.html", meta=meta, sent=sent, user=None, countries=COUNTRIES)


@bp.route("/restablecer/", methods=["GET", "POST"])
def restablecer():
    token = session.get("recovery_token")
    if not token:
        return redirect("/recuperar/")
    error = ""
    if request.method == "POST":
        pw = request.form.get("password") or ""
        if len(pw) < 8:
            error = "Mínimo 8 caracteres."
        elif db.auth_set_password(token, pw):
            session.pop("recovery_token", None)
            return redirect("/panel/")
        else:
            error = "El enlace expiró. Pide uno nuevo."
    meta = seo(f"Nueva clave | {config.BRAND}", "", "/restablecer/", noindex=True)
    return render_template("restablecer.html", meta=meta, error=error, user=current_user(), countries=COUNTRIES)


@bp.get("/salir/")
def salir():
    session.clear()
    return redirect("/")


# --- Panel ------------------------------------------------------------------
def _context(user):
    prof = db.profile(user["id"])
    plan = plans.get(prof.get("plan"))
    sites = db.select("sites", {"user_id": f"eq.{user['id']}", "order": "created_at.asc", "select": "*"})
    used = db.audits_this_month(user["id"])
    return prof, plan, sites, used


@bp.get("/panel/")
@login_required
def panel():
    user = current_user()
    prof, plan, sites, used = _context(user)
    meta = seo(f"Panel | {config.BRAND}", "", "/panel/", noindex=True)
    return render_template("panel.html", meta=meta, user=user, profile=prof, plan=plan, sites=sites, used=used,
                           countries=COUNTRIES, error=request.args.get("error", ""))


@bp.post("/panel/sitios/")
@login_required
def add_site():
    user = current_user()
    prof, plan, sites, _ = _context(user)
    if len(sites) >= plan["sites"]:
        return redirect(url_for("account.panel", error=f"Tu plan {plan['name']} permite {plan['sites']} web(s)."))
    url = normalize_url(request.form.get("url", ""))
    if not url or "." not in url:
        return redirect(url_for("account.panel", error="URL no válida."))
    country = request.form.get("country", "pe")
    queries = [q.strip() for q in (request.form.get("queries") or "").splitlines() if q.strip()][:plan["ai_queries"]]
    site = db.insert("sites", {
        "user_id": user["id"], "url": url, "domain": root_domain(url),
        "brand": request.form.get("brand", "").strip()[:120], "service": request.form.get("service", "").strip()[:120],
        "city": request.form.get("city", "").strip()[:120], "country": country if country in COUNTRIES else "pe",
        "queries": queries,
    })
    return redirect(url_for("account.site", site_id=site["id"], medir=1))


def _own_site(site_id):
    user = current_user()
    site = db.one("sites", {"id": f"eq.{site_id}", "user_id": f"eq.{user['id']}", "select": "*"})
    if not site:
        abort(404)
    return user, site


@bp.get("/panel/sitio/<site_id>/")
@login_required
def site(site_id):
    user, s = _own_site(site_id)
    prof = db.profile(user["id"])
    plan = plans.get(prof.get("plan"))
    history = db.site_history(site_id)
    meta = seo(f"{s['domain']} | {config.BRAND}", "", f"/panel/sitio/{site_id}/", noindex=True)
    return render_template("sitio.html", meta=meta, user=user, site=s, plan=plan, history=history,
                           countries=COUNTRIES, autorun=request.args.get("medir") == "1" and not history)


@bp.post("/panel/sitio/<site_id>/editar/")
@login_required
def edit_site(site_id):
    user, s = _own_site(site_id)
    plan = plans.get(db.profile(user["id"]).get("plan"))
    queries = [q.strip() for q in (request.form.get("queries") or "").splitlines() if q.strip()][:plan["ai_queries"]]
    country = request.form.get("country", s["country"])
    db.update("sites", {"id": f"eq.{site_id}"}, {
        "brand": request.form.get("brand", "").strip()[:120], "service": request.form.get("service", "").strip()[:120],
        "city": request.form.get("city", "").strip()[:120], "queries": queries,
        "country": country if country in COUNTRIES else s["country"],
    })
    return redirect(url_for("account.site", site_id=site_id))


@bp.post("/panel/sitio/<site_id>/eliminar/")
@login_required
def delete_site(site_id):
    _own_site(site_id)
    db.delete("sites", {"id": f"eq.{site_id}"})
    return redirect("/panel/")


@bp.post("/panel/agencia/")
@login_required
def agency():
    user = current_user()
    db.update("profiles", {"user_id": f"eq.{user['id']}"}, {"agency_name": request.form.get("agency_name", "").strip()[:80]})
    return redirect("/panel/")
