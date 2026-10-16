"""Genera el informe HTML (el mismo que se ve en la app) y lo guarda en /reportes."""
import json
import re

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import CLOUD, GITHUB_URL, REPORTS_DIR, TEMPLATES_DIR

env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape(["html"]))


def render(result: dict, prev: dict | None = None, standalone: bool = False) -> str:
    return env.get_template("report.html").render(r=result, prev=prev, standalone=standalone, cloud=CLOUD,
                                                  github_url=GITHUB_URL)


def save(result: dict, prev: dict | None = None):
    stamp = re.sub(r"[^0-9]", "", result["created_at"])
    base = f"{result['domain']}_{stamp}"
    html_path = REPORTS_DIR / f"{base}.html"
    html_path.write_text(render(result, prev, standalone=True), encoding="utf-8")
    (REPORTS_DIR / f"{base}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return html_path
