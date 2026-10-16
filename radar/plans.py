"""Planes y límites. El cobro se activa a mano (lista de espera) hasta conectar pagos."""

PLANS = {
    "free": {
        "name": "Gratis", "price": 0, "sites": 1, "audits_month": 4, "ai_queries": 2, "weekly": False, "white_label": False,
        "features": ["1 web", "4 auditorías al mes", "2 preguntas a cada IA", "Informe compartible"],
    },
    "negocio": {
        "name": "Negocio", "price": 15, "sites": 1, "audits_month": 30, "ai_queries": 10, "weekly": True, "white_label": False,
        "features": ["1 web", "Seguimiento semanal automático", "10 preguntas a cada IA (tus preguntas)",
                     "Historial y evolución", "Competidores que aparecen en tu lugar"],
    },
    "agencia": {
        "name": "Agencia", "price": 89, "sites": 15, "audits_month": 300, "ai_queries": 10, "weekly": True, "white_label": True,
        "features": ["Hasta 15 webs de clientes", "Seguimiento semanal de todas", "Informe con la marca de tu agencia",
                     "10 preguntas a cada IA por web", "Historial por cliente"],
    },
}


def get(plan: str | None) -> dict:
    return {"code": plan if plan in PLANS else "free", **PLANS.get(plan or "free", PLANS["free"])}
