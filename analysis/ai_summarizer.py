"""
Modulo de analisis con IA usando Google Gemini 2.5 Flash.

Genera resumen ejecutivo, acciones concretas y fechas limite
para publicaciones regulatorias con impacto en ERP de farmacias.

Tier gratuito de Gemini:
- 15 requests/minuto
- 500 requests/dia
- 250,000 tokens/minuto
- Sin tarjeta de credito

Configuracion:
    GEMINI_API_KEY=tu-api-key  (obtener en https://aistudio.google.com/apikey)
"""

import json
import logging
import os
import re

logger = logging.getLogger(__name__)

# Lazy import: solo se carga si se usa
_genai = None
_model = None

GEMINI_MODEL = "gemini-2.5-flash"
MAX_TEXT_LENGTH = 8000  # Truncar texto para mantenerse en limites gratuitos


SYSTEM_PROMPT = """Eres un asistente de analisis regulatorio especializado en farmacias privadas de Mexico y su sistema ERP.

Tu trabajo es analizar publicaciones del Diario Oficial de la Federacion (DOF), COFEPRIS, SAT y Secretaria de Salud, y generar un resumen ejecutivo orientado a un operador de farmacia que necesita saber:
1. QUE dice la publicacion en terminos simples
2. QUE acciones concretas debe tomar en su ERP o en su operacion
3. Si hay una fecha limite o de entrada en vigor

REGLAS:
- Responde SIEMPRE en espanol
- Se conciso: el resumen debe ser de 2-3 oraciones maximo
- Las acciones deben ser concretas y accionables desde un ERP de farmacia (ej: "Actualizar catalogo de CFDI", "Revisar lotes de medicamento X")
- Si no hay fecha limite clara, indica null
- La prioridad debe ser: URGENTE (requiere accion inmediata, hay fecha limite cercana o sancion), PLANIFICAR (requiere accion pero hay tiempo), INFORMATIVO (solo para conocimiento)

RESPONDE UNICAMENTE con un JSON valido (sin markdown, sin backticks, sin texto adicional) con esta estructura exacta:
{
    "resumen": "Resumen ejecutivo de 2-3 oraciones...",
    "acciones": ["Accion 1 para ERP farmacia", "Accion 2", ...],
    "fecha_limite": "YYYY-MM-DD o null si no hay",
    "prioridad": "URGENTE|PLANIFICAR|INFORMATIVO"
}"""


def _init_gemini():
    """Inicializa el cliente de Gemini de forma lazy."""
    global _genai, _model

    if _model is not None:
        return True

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.info("GEMINI_API_KEY no configurado. Analisis IA deshabilitado.")
        return False

    try:
        import google.generativeai as genai
        _genai = genai
        _genai.configure(api_key=api_key)
        _model = _genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
        )
        logger.info("Gemini %s inicializado correctamente.", GEMINI_MODEL)
        return True
    except ImportError:
        logger.warning("google-generativeai no instalado. pip install google-generativeai")
        return False
    except Exception as e:
        logger.error("Error inicializando Gemini: %s", e)
        return False


def _truncate_text(text: str, max_length: int = MAX_TEXT_LENGTH) -> str:
    """Trunca texto al limite manteniendo oraciones completas."""
    if len(text) <= max_length:
        return text

    truncated = text[:max_length]
    # Intentar cortar en el ultimo punto o salto de linea
    last_period = truncated.rfind(".")
    last_newline = truncated.rfind("\n")
    cut_point = max(last_period, last_newline)

    if cut_point > max_length * 0.7:  # Solo si el corte no pierde demasiado
        truncated = truncated[:cut_point + 1]

    return truncated


def _build_user_prompt(title: str, full_text: str, source: str,
                       domain: str, module: str, severity: str,
                       effective_date: str = None) -> str:
    """Construye el prompt del usuario con el contexto de la publicacion."""
    text_truncated = _truncate_text(full_text) if full_text else "(Sin texto disponible)"

    prompt = f"""Analiza la siguiente publicacion regulatoria:

TITULO: {title}
FUENTE: {source}
DOMINIO DETECTADO: {domain}
MODULO ERP AFECTADO: {module}
SEVERIDAD: {severity}
FECHA ENTRADA EN VIGOR DETECTADA: {effective_date or "No detectada"}

TEXTO DE LA PUBLICACION:
{text_truncated}

Genera el JSON con resumen, acciones, fecha_limite y prioridad."""

    return prompt


def _parse_response(response_text: str) -> dict:
    """Parsea la respuesta JSON del modelo, con manejo de errores."""
    # Limpiar posibles backticks de markdown
    cleaned = response_text.strip()
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.warning("Gemini retorno JSON invalido: %s | Respuesta: %s", e, cleaned[:200])
        return None

    # Validar campos requeridos
    resumen = data.get("resumen", "").strip()
    acciones = data.get("acciones", [])
    fecha_limite = data.get("fecha_limite")
    prioridad = data.get("prioridad", "INFORMATIVO").upper()

    if not resumen:
        logger.warning("Gemini retorno resumen vacio.")
        return None

    # Normalizar prioridad
    if prioridad not in ("URGENTE", "PLANIFICAR", "INFORMATIVO"):
        prioridad = "INFORMATIVO"

    # Normalizar fecha_limite
    if fecha_limite and fecha_limite.lower() in ("null", "none", "n/a", "no aplica", ""):
        fecha_limite = None

    # Validar formato de fecha si existe
    if fecha_limite:
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', fecha_limite):
            logger.warning("Fecha limite con formato invalido: %s", fecha_limite)
            fecha_limite = None

    # Asegurar que acciones es una lista de strings
    if isinstance(acciones, str):
        acciones = [acciones]
    acciones = [str(a).strip() for a in acciones if a]

    return {
        "ai_summary": resumen,
        "ai_actions": json.dumps(acciones, ensure_ascii=False),
        "ai_deadline": fecha_limite,
        "ai_priority": prioridad,
    }


def generate_ai_summary(title: str, full_text: str, source: str = "DOF",
                         domain: str = "", module: str = "",
                         severity: str = "", effective_date: str = None) -> dict:
    """
    Genera resumen ejecutivo con IA para una publicacion regulatoria.

    Args:
        title: Titulo de la publicacion.
        full_text: Texto completo de la publicacion.
        source: Fuente (DOF, COFEPRIS, SAT, SE_SALUD, COFEPRIS_NORMAS).
        domain: Dominio primario detectado (HEALTH, FISCAL, etc.).
        module: Modulo ERP impactado (INVOICING, INVENTORY, etc.).
        severity: Severidad detectada (ALTA, MEDIA).
        effective_date: Fecha de entrada en vigor detectada.

    Returns:
        dict con keys: ai_summary, ai_actions, ai_deadline, ai_priority.
        None si falla la API o no hay key configurada.
    """
    if not _init_gemini():
        return None

    user_prompt = _build_user_prompt(
        title=title,
        full_text=full_text,
        source=source,
        domain=domain,
        module=module,
        severity=severity,
        effective_date=effective_date,
    )

    try:
        response = _model.generate_content(
            user_prompt,
            generation_config={
                "temperature": 0.3,  # Baja para respuestas consistentes
                "max_output_tokens": 1024,
            },
        )

        if not response.text:
            logger.warning("Gemini retorno respuesta vacia para: %s", title[:80])
            return None

        result = _parse_response(response.text)
        if result:
            logger.info("Resumen IA generado para: %s [%s]",
                        title[:60], result["ai_priority"])
        return result

    except Exception as e:
        logger.error("Error llamando a Gemini para '%s': %s", title[:60], e)
        return None
