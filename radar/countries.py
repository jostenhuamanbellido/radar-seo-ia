"""Países soportados: cada uno tiene su landing (/pe/, /mx/…) con hreflang propio."""

COUNTRIES = {
    "pe": {
        "name": "Perú", "iso": "PE", "hreflang": "es-PE", "in": "en Perú",
        "capital": "Lima",
        "cities": ["Lima", "Arequipa", "Trujillo", "Cusco", "Chiclayo", "Piura"],
        "example_business": "una clínica dermatológica en Miraflores",
        "example_query": "¿Cuál es la mejor clínica dermatológica en Miraflores?",
        "directories": "Google Business Profile, Doctoralia, Facebook e Instagram",
    },
    "mx": {
        "name": "México", "iso": "MX", "hreflang": "es-MX", "in": "en México",
        "capital": "Ciudad de México",
        "cities": ["Ciudad de México", "Guadalajara", "Monterrey", "Puebla", "Querétaro", "Mérida"],
        "example_business": "un consultorio dental en Polanco",
        "example_query": "¿Qué dentista me recomiendas en Polanco, CDMX?",
        "directories": "Google Business Profile, Doctoralia, Sección Amarilla y Facebook",
    },
    "co": {
        "name": "Colombia", "iso": "CO", "hreflang": "es-CO", "in": "en Colombia",
        "capital": "Bogotá",
        "cities": ["Bogotá", "Medellín", "Cali", "Barranquilla", "Cartagena", "Bucaramanga"],
        "example_business": "una clínica estética en El Poblado",
        "example_query": "¿Cuál es la mejor clínica estética en El Poblado, Medellín?",
        "directories": "Google Business Profile, Doctoralia, Páginas Amarillas y Facebook",
    },
    "cl": {
        "name": "Chile", "iso": "CL", "hreflang": "es-CL", "in": "en Chile",
        "capital": "Santiago",
        "cities": ["Santiago", "Viña del Mar", "Valparaíso", "Concepción", "Antofagasta", "La Serena"],
        "example_business": "un centro médico en Providencia",
        "example_query": "¿Qué centro médico recomiendas en Providencia, Santiago?",
        "directories": "Google Business Profile, Doctoralia, Facebook e Instagram",
    },
    "ar": {
        "name": "Argentina", "iso": "AR", "hreflang": "es-AR", "in": "en Argentina",
        "capital": "Buenos Aires",
        "cities": ["Buenos Aires", "Córdoba", "Rosario", "Mendoza", "La Plata", "Mar del Plata"],
        "example_business": "un estudio de abogados en Palermo",
        "example_query": "¿Qué estudio de abogados me recomiendas en Palermo, Buenos Aires?",
        "directories": "Google Business Profile, Doctoralia, Facebook e Instagram",
    },
}

DEFAULT_COUNTRY = "pe"

# Rubros con landing/ranking (los que más se buscan en IAs para negocios locales)
CATEGORIES = [
    "clínicas dermatológicas", "dentistas", "clínicas estéticas", "trasplante capilar", "abogados",
    "restaurantes", "inmobiliarias", "veterinarias", "gimnasios", "psicólogos",
]


def get(code: str | None) -> dict:
    code = (code or "").lower()
    c = COUNTRIES.get(code) or COUNTRIES[DEFAULT_COUNTRY]
    return {"code": code if code in COUNTRIES else DEFAULT_COUNTRY, **c}
