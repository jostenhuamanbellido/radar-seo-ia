"""Radar SEO IA · interfaz web local.

Ejecuta:  python app.py   y abre http://localhost:5050
"""
import threading
import uuid
import webbrowser

from flask import Flask, Response, abort, jsonify, redirect, render_template, request

from radar import ai_visibility, config, report, storage
from radar.audit import run_audit

app = Flask(__name__, template_folder=str(config.TEMPLATES_DIR))
JOBS: dict = {}


@app.context_processor
def _globals():
    return {"cloud": config.CLOUD, "github_url": config.GITHUB_URL}


def _params(form) -> dict:
    return {
        "url": (form.get("url") or "").strip(),
        "brand": form.get("brand", ""),
        "service": form.get("service", ""),
        "city": form.get("city", ""),
        "custom_queries": [q for q in (form.get("queries") or "").splitlines() if q.strip()],
        "run_ai": form.get("ai") == "1",
        "run_psi": form.get("psi") == "1",
    }


def _worker(job_id: str, params: dict):
    job = JOBS[job_id]
    try:
        result = run_audit(progress=lambda m: job["log"].append(m), **params)
        audit_id = storage.save(result)
        result["id"] = audit_id
        prev = storage.previous(result["domain"], audit_id)
        path = report.save(result, prev)
        job["log"].append(f"Informe guardado en {path.name}")
        job.update(status="done", audit_id=audit_id)
    except Exception as exc:  # noqa: BLE001 - se muestra al usuario
        job.update(status="error", error=str(exc))


@app.get("/")
def index():
    recent = [] if config.CLOUD else storage.recent()
    return render_template("index.html", recent=recent, providers=ai_visibility.active_providers(), standalone=False)


@app.post("/auditar")
def auditar():
    params = _params(request.form)
    url = params["url"]
    if not url:
        return redirect("/")
    if config.CLOUD:
        # Serverless: no hay hilos persistentes; la página de progreso llama a /api/run y espera el informe
        return render_template("progress.html", job=None, url=url, form=dict(request.form), standalone=False)
    job_id = uuid.uuid4().hex[:10]
    JOBS[job_id] = {"status": "running", "log": [], "audit_id": None, "error": ""}
    threading.Thread(target=_worker, args=(job_id, params), daemon=True).start()
    return render_template("progress.html", job=job_id, url=url, standalone=False)


@app.post("/api/run")
def run_sync():
    """Auditoría síncrona (usada en Vercel). Devuelve el informe HTML completo."""
    params = _params(request.form)
    if not params["url"]:
        return Response("Escribe una URL.", status=400, mimetype="text/plain")
    try:
        result = run_audit(**params)
    except Exception as exc:  # noqa: BLE001
        return Response(str(exc), status=400, mimetype="text/plain")
    return report.render(result)


@app.get("/api/job/<job_id>")
def job_status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"status": "error", "error": "Trabajo no encontrado (¿se reinició el servidor?)"}), 404
    return jsonify(job)


@app.get("/reporte/<int:audit_id>")
def ver_reporte(audit_id):
    r = storage.get(audit_id) or abort(404)
    return report.render(r, storage.previous(r["domain"], audit_id))


@app.get("/reporte/<int:audit_id>/descargar")
def descargar(audit_id):
    r = storage.get(audit_id) or abort(404)
    html = report.render(r, storage.previous(r["domain"], audit_id), standalone=True)
    name = f"radar-{r['domain']}-{r['created_at'][:10]}.html"
    return Response(html, mimetype="text/html", headers={"Content-Disposition": f"attachment; filename={name}"})


@app.get("/reporte/<int:audit_id>/json")
def ver_json(audit_id):
    r = storage.get(audit_id) or abort(404)
    return jsonify(r)


@app.get("/historial/<domain>")
def historial(domain):
    rows = storage.history(domain)
    if not rows:
        abort(404)
    return render_template("history.html", domain=domain, rows=rows, standalone=False)


if __name__ == "__main__":
    url = f"http://localhost:{config.PUERTO}"
    print(f"\n  Radar SEO IA corriendo en {url}  (Ctrl+C para detener)\n")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=config.PUERTO, debug=False)
