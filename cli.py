"""Radar SEO IA · uso por consola (ideal para auditar varias webs de una vez).

Ejemplos:
  python cli.py https://capilarcenter.pe
  python cli.py https://skinmedical.pe --ciudad "Miraflores, Lima" --servicio "dermatología"
  python cli.py --archivo webs.txt          (una URL por línea)
  python cli.py https://misitio.pe --sin-ia --sin-pagespeed
"""
import argparse
import sys

from radar import report, storage
from radar.audit import run_audit
from radar.checks_base import PILLARS


def audit_one(url, args):
    print(f"\n▶ {url}")
    result = run_audit(
        url, brand=args.marca or "", service=args.servicio or "", city=args.ciudad or "",
        custom_queries=args.pregunta or [], run_ai=not args.sin_ia, run_psi=not args.sin_pagespeed,
        progress=lambda m: print(f"   · {m}"),
    )
    audit_id = storage.save(result)
    result["id"] = audit_id
    prev = storage.previous(result["domain"], audit_id)
    path = report.save(result, prev)
    s = result["scores"]
    print(f"\n   TOTAL {s['total']}/100 ({result['grades']['total']})")
    for k, name in PILLARS.items():
        v = s.get(k)
        extra = ""
        if prev and prev.get(k) is not None and v is not None:
            d = v - prev[k]
            extra = f"  ({'+' if d >= 0 else ''}{d} vs. {prev['created_at']})"
        print(f"   {name:<32} {v if v is not None else '—':>4}{extra}")
    print("\n   Prioridades:")
    for c in result["priorities"][:5]:
        print(f"   - [{c['pillar']}] {c['name']}: {c['fix']}")
    print(f"\n   Informe: {path}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Auditoría de SEO local, GEO y AEO + visibilidad en IAs")
    ap.add_argument("url", nargs="?", help="URL de la web")
    ap.add_argument("--archivo", help="archivo .txt con una URL por línea")
    ap.add_argument("--marca")
    ap.add_argument("--servicio")
    ap.add_argument("--ciudad")
    ap.add_argument("--pregunta", action="append", help="pregunta extra para las IAs (se puede repetir)")
    ap.add_argument("--sin-ia", action="store_true", help="no consultar IAs")
    ap.add_argument("--sin-pagespeed", action="store_true", help="no medir velocidad")
    args = ap.parse_args()

    urls = []
    if args.archivo:
        with open(args.archivo, encoding="utf-8") as f:
            urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    if args.url:
        urls.insert(0, args.url)
    if not urls:
        ap.print_help()
        return
    for u in urls:
        try:
            audit_one(u, args)
        except Exception as exc:  # noqa: BLE001
            print(f"   ✕ Error: {exc}")


if __name__ == "__main__":
    main()
