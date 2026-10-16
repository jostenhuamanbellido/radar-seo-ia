"""Cítame · aplicación web (Flask).

Local:   python app.py   →  http://localhost:5050
Vercel:  api/index.py importa `app`.

Modos:
- Con Supabase (SUPABASE_URL + claves): cuentas, panel, informes compartibles, rankings, seguimiento semanal.
- Sin Supabase (uso local): auditorías con historial en SQLite (data/radar.db).
"""
import threading
import webbrowser
from datetime import timedelta

from flask import Flask, Response, abort, jsonify, render_template

from radar import config, db, report, storage
from radar.countries import COUNTRIES
from web import account, api, public
from web.common import current_user, seo

app = Flask(__name__, template_folder=str(config.TEMPLATES_DIR), static_folder=str(config.BASE_DIR / "static"))
app.secret_key = config.FLASK_SECRET
app.permanent_session_lifetime = timedelta(days=30)
app.config.update(SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_SECURE=config.CLOUD, SESSION_COOKIE_HTTPONLY=True)

app.register_blueprint(public.bp)
app.register_blueprint(account.bp)
app.register_blueprint(api.bp)


@app.context_processor
def _globals():
    return {"cloud": config.CLOUD, "github_url": config.GITHUB_URL, "brand": config.BRAND,
            "site_url": config.SITE_URL, "db_enabled": db.enabled(), "local_mode": not db.enabled() and not config.CLOUD}


@app.errorhandler(404)
def not_found(_):
    meta = seo(f"No encontrado | {config.BRAND}", "", "/404", noindex=True)
    return render_template("404.html", meta=meta, user=current_user(), countries=COUNTRIES), 404


# --- Modo local sin Supabase: historial en SQLite ----------------------------
@app.get("/local/")
def local_history():
    if db.enabled() or config.CLOUD:
        abort(404)
    meta = seo(f"Historial local | {config.BRAND}", "", "/local/", noindex=True)
    return render_template("local.html", meta=meta, recent=storage.recent(), user=None, countries=COUNTRIES)


@app.get("/reporte/<int:audit_id>")
def ver_reporte(audit_id):
    if config.CLOUD:
        abort(404)
    r = storage.get(audit_id) or abort(404)
    return report.render(r, storage.previous(r["domain"], audit_id))


@app.get("/reporte/<int:audit_id>/json")
def ver_json(audit_id):
    if config.CLOUD:
        abort(404)
    r = storage.get(audit_id) or abort(404)
    return jsonify(r)


@app.get("/historial/<domain>")
def historial(domain):
    if config.CLOUD:
        abort(404)
    rows = storage.history(domain) or abort(404)
    meta = seo(f"Evolución {domain} | {config.BRAND}", "", f"/historial/{domain}", noindex=True)
    hist = [{"href": f"/reporte/{r['id']}", **r} for r in rows]
    return render_template("history.html", meta=meta, domain=domain, rows=hist, user=None, countries=COUNTRIES)


@app.get("/health")
def health():
    return Response("ok", mimetype="text/plain")


if __name__ == "__main__":
    url = f"http://localhost:{config.PUERTO}"
    print(f"\n  {config.BRAND} corriendo en {url}  (Ctrl+C para detener)\n")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=config.PUERTO, debug=False)
