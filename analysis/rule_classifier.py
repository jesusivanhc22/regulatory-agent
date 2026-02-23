from datetime import datetime

from analysis.domain_classifier import classify_domain
from analysis.obligation_detector import calculate_operational_obligation
from analysis.erp_impact_engine import evaluate_erp_impact
from analysis.severity_evaluator import evaluate_severity

# Pre-filtro: si el texto no contiene al menos 1 de estos términos,
# la publicación no es relevante para un ERP de farmacias.
PHARMACY_RELEVANCE = [
    # Farmacia y medicamentos
    "farmacia", "medicamento", "cofepris",
    "farmacopea", "suplemento para establecimientos",
    "venta y suministro de medicamentos", "sustancia activa",
    "receta", "controlado", "dispositivo médico",
    "farmacovigilancia", "tecnovigilancia", "registro sanitario",
    # Antimicrobianos y controlados
    "antimicrobiano", "antibiótico", "psicotrópico",
    "estupefaciente", "sustancia controlada",
    # Regulación operativa farmacia
    "responsable sanitario", "aviso de funcionamiento",
    "licencia sanitaria", "sistema computarizado",
    "registro electrónico", "cadena de frío",
    "control de temperatura", "refrigeración",
    "residuos peligrosos", "rpbi",
    "buenas prácticas de dispensación", "buenas prácticas de farmacia",
    "alertamiento", "alerta sanitaria",
    "feum",
    # NOMs sanitarias clave
    "nom-059", "nom-072", "nom-176", "nom-001-ssa",
    "nom-024", "nom-004", "nom-220", "nom-240", "nom-241",
    # Fiscal y facturación
    "cfdi", "factura", "impuesto", "iva", "isr", "ieps",
    "miscelánea fiscal", "carta porte", "comprobante de traslado",
    "traslado de mercancías", "complemento de pago", "comprobante fiscal",
    "contabilidad electrónica", "diot",
    # Inventario y operación
    "inventario", "caducidad", "lote", "trazabilidad",
    "punto de venta", "profeco",
]


# Filtro negativo: si el título contiene estos términos Y NO contiene
# ningún término fuerte de farmacia privada, es probable que sea gobierno/hospital.
GOVERNMENT_EXCLUDE_TITLE = [
    # Militar y seguridad
    "secretaría de la defensa", "sedena", "fuerzas armadas",
    "armada de méxico", "marina", "secretaría de marina",
    # Seguridad social (hospitales públicos)
    "issste", "imss-bienestar",
    "hospital general", "hospital regional", "hospital rural",
    "instituto nacional de salud",
    # Judicial
    "tribunal", "juzgado", "poder judicial",
    "acción de inconstitucionalidad",
    # Educación
    "secretaría de educación",
    "programa nacional de inglés", "becas ",
    # Energía y transporte no farmacia
    "aviación civil", "aeropuerto",
    "comisión federal de electricidad",
    "pemex", "petróleos mexicanos", "petrolíferos",
    "combustible", "gasolina", "gas licuado",
    # Gobierno general
    "secretaría de gobernación",
    "secretaría de bienestar",
    "personas desaparecidas", "desaparición forzada",
    # Transferencias entre gobierno y estados
    "transferencia de recursos federales",
    "convenio específico en materia de transferencia",
    # Comercio/antidumping
    "investigación antidumping", "antisubvención",
    "importaciones de pierna", "importaciones de carne",
    # Moneda informativa
    "equivalencia de las monedas",
    # Laboratorios de gobierno
    "laboratorios de biológicos y reactivos",
    # Programas presupuestarios de gobierno
    "programa presupuestario",
    "programas nacionales estratégicos",
    # Instituciones de crédito bancarias
    "instituciones de crédito",
    # Turismo
    "nom-008-tur", "guías de turistas",
    # Varios gobierno
    "posicionamiento global de unidades vehiculares",
    "servicio de protección federal",
]

# Términos que ANULAN el filtro negativo — si aparecen EN EL TÍTULO,
# la publicación siempre es relevante aunque tenga términos de gobierno.
# NO incluir "cfdi", "factura", etc. porque cualquier programa de gobierno
# los menciona genéricamente.
PHARMACY_STRONG = [
    "farmacia", "medicamento", "cofepris", "farmacopea",
    "suplemento para establecimientos",
    "nom-059", "nom-072", "nom-176", "nom-001-ssa",
    "antimicrobiano", "receta médica", "receta electrónica",
    "responsable sanitario", "sistema computarizado",
    "trazabilidad", "farmacovigilancia", "tecnovigilancia",
    "cadena de frío", "feum",
    "venta y suministro de medicamentos",
]


def _is_relevant(title: str, full_text: str) -> bool:
    """
    Verifica si la publicación es relevante para un ERP de farmacias privadas.

    - Filtro negativo se aplica SOLO al título (define la naturaleza de la publicación)
    - PHARMACY_STRONG se busca en el título para anular el filtro negativo
    - PHARMACY_RELEVANCE se busca en título + texto completo
    """
    lower_title = title.lower()
    lower_text = (title + "\n" + (full_text or "")).lower()

    # Paso 1: si el TÍTULO tiene un término de gobierno...
    has_gov_title = any(kw in lower_title for kw in GOVERNMENT_EXCLUDE_TITLE)

    if has_gov_title:
        # ...verificar si el TÍTULO también tiene un término fuerte de farmacia
        has_strong_title = any(kw in lower_title for kw in PHARMACY_STRONG)
        if not has_strong_title:
            return False  # Gobierno sin farmacia = excluir

    # Paso 2: debe tener al menos 1 keyword de relevancia en título o texto
    has_relevance = any(kw in lower_text for kw in PHARMACY_RELEVANCE)
    return has_relevance


def _empty_result():
    """Retorna resultado vacío para publicaciones no relevantes."""
    return {
        "primary_domain": "NO_RELEVANTE",
        "health_score": 0, "fiscal_score": 0, "retail_score": 0,
        "border_region_score": 0, "currency_score": 0,
        "operational_obligation_score": 0,
        "invoicing_score": 0, "tax_reporting_score": 0,
        "inventory_score": 0, "accounting_score": 0, "pos_score": 0,
        "regulatory_compliance_score": 0,
        "impacted_module": "NONE",
        "severity": "BAJA",
        "impact_flag": 0,
        "impact_reason": "No relevante para ERP farmacias",
        "analyzed_at": datetime.utcnow().isoformat(),
    }


def analyze_publication(title: str, full_text: str):

    text = f"{title}\n{full_text or ''}"

    # 0. Pre-filtro de relevancia farmacia/ERP
    if not _is_relevant(title, full_text or ""):
        return _empty_result()

    # 1. Clasificación por dominio
    primary_domain, domain_scores = classify_domain(text)

    # 2. Obligación operativa
    obligation_score = calculate_operational_obligation(text)

    # 3. Impacto en módulo ERP
    impacted_module, module_scores = evaluate_erp_impact(text)

    # 4. Severidad
    severity = evaluate_severity(domain_scores, obligation_score, module_scores)

    impact_flag = 1 if severity in ["ALTA", "MEDIA"] else 0

    impact_reason = (
        f"Dominio: {primary_domain} | "
        f"Módulo: {impacted_module} | "
        f"Obligación: {obligation_score}"
    )

    return {
        "primary_domain": primary_domain,

        "health_score": domain_scores.get("HEALTH", 0),
        "fiscal_score": domain_scores.get("FISCAL", 0),
        "retail_score": domain_scores.get("RETAIL", 0),
        "border_region_score": domain_scores.get("BORDER", 0),
        "currency_score": domain_scores.get("CURRENCY", 0),

        "operational_obligation_score": obligation_score,

        "invoicing_score": module_scores.get("INVOICING", 0),
        "tax_reporting_score": module_scores.get("TAX_REPORTING", 0),
        "inventory_score": module_scores.get("INVENTORY", 0),
        "accounting_score": module_scores.get("ACCOUNTING", 0),
        "pos_score": module_scores.get("POS", 0),
        "regulatory_compliance_score": module_scores.get("REGULATORY_COMPLIANCE", 0),

        "impacted_module": impacted_module,
        "severity": severity,
        "impact_flag": impact_flag,
        "impact_reason": impact_reason,

        "analyzed_at": datetime.utcnow().isoformat()
    }
