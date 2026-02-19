import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ── Configuración del pipeline ──────────────────────────────────────
BATCH_SIZE = 10

# ── Directorio de reportes ──────────────────────────────────────────
REPORTS_DIR = "reports"

# ── Keywords por categoría (fuente única de verdad) ─────────────────
CATEGORY_KEYWORDS = {
    "FISCAL": [
        "impuesto", "iva", "isr", "sat", "fiscal", "contribucion",
        "contribución", "ieps", "cfdi", "carta porte", "tributario",
        "declaracion", "declaración", "recaudacion", "recaudación",
    ],
    "SANITARIO": [
        "salud", "medicamento", "cofepris", "farmacia",
        "establecimiento farmacia", "consultorio medico", "consultorio médico",
        "control sanitario", "receta", "controlado", "nom-",
        "dispositivo medico", "dispositivo médico", "vacuna", "epidemiologia",
    ],
    "ECONÓMICO": [
        "economia", "economía", "inflacion", "inflación", "precio",
        "mercado", "consumidor", "ticket", "comprobante", "precio maximo",
        "precio máximo", "comercio", "aranceles", "exportacion", "importacion",
    ],
}

# Pesos por categoría (para cálculo de score)
CATEGORY_WEIGHTS = {
    "FISCAL": 3,
    "SANITARIO": 3,
    "ECONÓMICO": 2,
}

# Umbrales de prioridad
PRIORITY_THRESHOLDS = {
    "ALTA": 3,
    "MEDIA": 2,
}
