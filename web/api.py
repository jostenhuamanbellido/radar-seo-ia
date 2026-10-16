"""Ejecución de auditorías (anónimas y de usuarios) y tareas programadas."""
import requests
from flask import Blueprint, jsonify, render_template, request

from radar import config, db, plans, report, storage
from radar.audit import run_audit
from radar.countries import COUNTRIES

from .common import client_ip, current_user, seo

bp = Blueprint("api", __name__)


def form_params(form) -> dict:
    country = (form.get("country") or "").lower()
    return {
        "url": (form.get("url") or "").strip(),
        "brand": form.get("brand", ""),
        "service": form.get("service", ""),
        "city": form.get("city", ""),
        "custom_queries": [q for q in (form.get("queries") or "").splitlines() if q.strip()],
        "run_ai": form.get("ai", "1") == "1",
        "run_psi": form.get("psi", "1") == "1",
        "country": country if country in COUNTRIES else "",
    }


@bp.post("/auditar")
def auditar_cloud():
    """Página de progreso; el navegador llama luego a /api/run (una petición larga)."""
    params = form_params(request.form)
    meta = seo(f"Auditando… | {config.BRAND}", "", "/auditar", noindex=True)
    return render_template("progress.html", meta=meta, job=None, url=params["url"], form=dict(request.form),
                           endpoint="/api/run", user=current_user(), countries=COUNTRIES)


@bp.post("/api/run")
def run_anon():
    params = form_params(request.form)
    if not params["url"]:
        return jsonify({"error": "Escribe una URL."}), 400
    user = current_user()
    if db.enabled() and not user and not db.rate_limit("ip:" + client_ip(), config.ANON_DAILY_LIMIT):
        return jsonify({"error": f"Llegaste al límite de {config.ANON_DAILY_LIMIT} auditorías gratis por día. "
                                 "Crea una cuenta gratis para seguir."}), 429
    # Usuarios con cuenta: las IAs se consultan con el límite de preguntas de su plan
    force_ai, max_q = False, None
    if user and db.enabled():
        plan = plans.get(db.profile(user["id"]).get("plan"))
        if db.audits_this_month(user["id"]) >= plan["audits_month"]:
            return jsonify({"error": f"Usaste las {plan['audits_month']} auditorías de este mes de tu plan {plan['name']}."}), 429
        force_ai, max_q = True, plan["ai_queries"]
    try:
        result = run_audit(**params, force_ai=force_ai, max_queries=max_q)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 400
    if db.enabled():
        row = db.save_audit(result, user_id=user["id"] if user else None)
        return jsonify({"redirect": f"/r/{row['public_id']}"})
    if not config.CLOUD:  # modo local: historial en SQLite + copia HTML en /reportes
        audit_id = storage.save(result)
        result["id"] = audit_id
        report.save(result, storage.previous(result["domain"], audit_id))
        return jsonify({"redirect": f"/reporte/{audit_id}"})
    return jsonify({"html": report.render(result)})


def _audit_site(site: dict, plan: dict) -> dict:
    result = run_audit(site["url"], brand=site.get("brand") or "", service=site.get("service") or "",
                       city=site.get("city") or "", custom_queries=site.get("queries") or [],
                       country=site.get("country") or "", force_ai=True, max_queries=plan["ai_queries"])
    return db.save_audit(result, user_id=site["user_id"], site_id=site["id"])


@bp.post("/api/panel/run/<site_id>")
def run_site(site_id):
    user = current_user()
    if not user or not db.enabled():
        return jsonify({"error": "Inicia sesión."}), 401
    site = db.one("sites", {"id": f"eq.{site_id}", "user_id": f"eq.{user['id']}", "select": "*"})
    if not site:
        return jsonify({"error": "Web no encontrada."}), 404
    plan = plans.get(db.profile(user["id"]).get("plan"))
    if db.audits_this_month(user["id"]) >= plan["audits_month"]:
        return jsonify({"error": f"Usaste las {plan['audits_month']} auditorías del mes de tu plan {plan['name']}."}), 429
    try:
        row = _audit_site(site, plan)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 400
    return jsonify({"redirect": f"/r/{row['public_id']}"})


# --- Cron (Vercel) ----------------------------------------------------------
def _cron_ok() -> bool:
    return bool(config.CRON_SECRET) and request.headers.get("authorization") == f"Bearer {config.CRON_SECRET}"


@bp.get("/api/cron/semanal")
def cron_weekly():
    """Vercel Cron llama aquí una vez al día; lanza una función por cada web pendiente."""
    if not _cron_ok():
        return jsonify({"error": "no autorizado"}), 401
    due = db.sites_due(limit=40)
    for s in due:
        try:  # disparar y no esperar: cada web corre en su propia función
            requests.post(f"{config.SITE_URL}/api/cron/sitio/{s['id']}",
                          headers={"authorization": f"Bearer {config.CRON_SECRET}"}, timeout=1.5)
        except requests.RequestException:
            pass
    return jsonify({"lanzadas": len(due)})


@bp.post("/api/cron/sitio/<site_id>")
def cron_site(site_id):
    if not _cron_ok():
        return jsonify({"error": "no autorizado"}), 401
    site = db.one("sites", {"id": f"eq.{site_id}", "select": "*,profiles!inner(plan)"})
    if not site:
        return jsonify({"error": "no existe"}), 404
    plan = plans.get(site["profiles"]["plan"])
    if not plan["weekly"]:
        return jsonify({"omitida": True})
    row = _audit_site(site, plan)
    return jsonify({"ok": True, "public_id": row["public_id"]})
