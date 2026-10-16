"""Configuración central: lee el archivo .env de la raíz del proyecto."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"

load_dotenv(BASE_DIR / ".env")

# En Vercel (serverless) el disco es de solo lectura salvo /tmp y no hay historial persistente
CLOUD = bool(os.getenv("VERCEL"))
DATA_DIR = Path("/tmp/radar/data") if CLOUD else BASE_DIR / "data"
REPORTS_DIR = Path("/tmp/radar/reportes") if CLOUD else BASE_DIR / "reportes"
DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def env(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


def env_int(key: str, default: int) -> int:
    try:
        return int(env(key, str(default)))
    except ValueError:
        return default


# --- Proveedores de IA (todos opcionales) ---------------------------------
OPENAI_API_KEY = env("OPENAI_API_KEY")
OPENAI_MODEL = env("OPENAI_MODEL", "gpt-5-mini")

ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = env("ANTHROPIC_MODEL", "claude-sonnet-5-5")

GEMINI_API_KEY = env("GEMINI_API_KEY")
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-flash-latest")

PERPLEXITY_API_KEY = env("PERPLEXITY_API_KEY")
PERPLEXITY_MODEL = env("PERPLEXITY_MODEL", "sonar")

# --- Otros ------------------------------------------------------------------
PAGESPEED_API_KEY = env("PAGESPEED_API_KEY")
PAIS = env("PAIS", "PE")
CIUDAD_DEFECTO = env("CIUDAD_DEFECTO", "Lima")
MAX_PAGINAS = env_int("MAX_PAGINAS", 6)
PUERTO = env_int("PUERTO", 5050)

# En la demo pública las claves de IA del servidor NO se usan salvo que pongas PUBLIC_AI=1
# (evita que cualquier visitante gaste tus créditos de API)
PUBLIC_AI = env("PUBLIC_AI") == "1"
GITHUB_URL = env("GITHUB_URL", "https://github.com/jostenhuamanbellido/radar-seo-ia")

# --- Marca y SaaS -----------------------------------------------------------
BRAND = env("BRAND", "Cítame")
SITE_URL = env("SITE_URL", "https://radar-seo-ia.vercel.app").rstrip("/")
CONTACT_EMAIL = env("CONTACT_EMAIL", "jostinmarc10@gmail.com")
FLASK_SECRET = env("FLASK_SECRET", "cambia-esta-clave-en-produccion")

# Supabase (cuentas, historial en la nube, rankings). Sin esto funciona en modo local con SQLite.
SUPABASE_URL = env("SUPABASE_URL").rstrip("/")
SUPABASE_ANON_KEY = env("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = env("SUPABASE_SERVICE_KEY")

# Vercel Cron envía "Authorization: Bearer <CRON_SECRET>"
CRON_SECRET = env("CRON_SECRET")
ANON_DAILY_LIMIT = env_int("ANON_DAILY_LIMIT", 5)
