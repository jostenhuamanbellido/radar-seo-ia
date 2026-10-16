"""Genera rankings públicos con datos reales de las IAs y los guarda en Supabase.

Ejemplos:
  python rankings_cli.py --pais pe --ciudad Lima --rubro "clínicas dermatológicas"
  python rankings_cli.py --pais pe --ciudad Lima --todos         (todos los rubros de radar/countries.py)
"""
import argparse
import sys
from datetime import datetime, timezone

from radar import db
from radar.countries import CATEGORIES, COUNTRIES
from radar.rankings import generate


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--pais", required=True, choices=list(COUNTRIES))
    ap.add_argument("--ciudad", required=True)
    ap.add_argument("--rubro", action="append")
    ap.add_argument("--todos", action="store_true")
    args = ap.parse_args()
    if not db.enabled():
        sys.exit("Configura SUPABASE_URL y SUPABASE_SERVICE_KEY en .env")
    rubros = CATEGORIES if args.todos else (args.rubro or [])
    for r in rubros:
        print(f"▶ {r} en {args.ciudad}")
        data = generate(args.pais, args.ciudad, r)
        if not data["items"]:
            print("  sin resultados, no se publica")
            continue
        db.insert("rankings", {"country": args.pais, "city": args.ciudad, "category": r, "slug": data["slug"],
                               "data": data, "updated_at": datetime.now(timezone.utc).isoformat()},
                  upsert=True, on_conflict="country,slug")
        print(f"  publicado: /rankings/{args.pais}/{data['slug']}/  ({len(data['items'])} negocios)")


if __name__ == "__main__":
    main()
