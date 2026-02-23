from datetime import datetime

from analysis.domain_classifier import classify_domain
from analysis.obligation_detector import calculate_operational_obligation
from analysis.erp_impact_engine import evaluate_erp_impact
from analysis.severity_evaluator import evaluate_severity

# Pre-filtro: si el texto no contiene al menos 1 de estos términos,
# la publicación no es relevante para un ERP de farmacias.
PHARMACY_RELEVANCE = [
    # Farmacia y medicamentos
    "farmacia", "medicamento", "cofepris", "salud", "sanitario",
    "farmacopea", "suplemento para establecimientos",
    "venta y suministro de medicamentos", "sustancia activa",
    "receta", "controlado", "dispositivo médico",
    "farmacovigilancia", "registro sanitario", "control sanitario",
    # NOMs sanitarias clave
    "nom-059", "nom-072", "nom-176", "nom-001-ssa",
    "nom-024", "nom-004", "nom-220", "nom-240", "nom-241",
    # Fiscal y facturación
    "cfdi", "factura", "impuesto", "iva", "isr", "ieps",
    "miscelánea fiscal", "carta porte", "comprobante de traslado",
    "traslado de mercancías", "complemento de pago", "comprobante fiscal",
    "contabilidad electrónica",
    # Inventario y operación
    "inventario", "caducidad", "lote", "trazabilidad",
    "punto de venta", "precio", "profeco",
]


def _is_relevant(text: str) -> bool:
    """Verifica si el texto tiene al menos 1 keyword de relevancia farmacia/ERP."""
    lower_text = text.lower()
    return any(kw in lower_text for kw in PHARMACY_RELEVANCE)


def _empty_result():
    """Retorna resultado vacío para publicaciones no relevantes."""
    return {
        "primary_domain": "NO_RELEVANTE",
        "health_score": 0, "fiscal_score": 0, "retail_score": 0,
        "border_region_score": 0, "currency_score": 0,
        "operational_obligation_score": 0,
        "invoicing_score": 0, "tax_reporting_score": 0,
        "inventory_score": 0, "accounting_score": 0, "pos_score": 0,
        "impacted_module": "NONE",
        "severity": "BAJA",
        "impact_flag": 0,
        "impact_reason": "No relevante para ERP farmacias",
        "analyzed_at": datetime.utcnow().isoformat(),
    }


def analyze_publication(title: str, full_text: str):

    text = f"{title}\n{full_text}"

    # 0. Pre-filtro de relevancia farmacia/ERP
    if not _is_relevant(text):
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

        "impacted_module": impacted_module,
        "severity": severity,
        "impact_flag": impact_flag,
        "impact_reason": impact_reason,

        "analyzed_at": datetime.utcnow().isoformat()
    }
