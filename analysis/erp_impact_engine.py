# ==============================
# KEYWORDS POR MÓDULO ERP
# (Específicos a contexto ERP farmacia — sin términos genéricos)
# ==============================

INVOICING_WORDS = [
    "CFDI",
    "factura electrónica",
    "cancelación de CFDI",
    "cancelación de factura",
    "Anexo 20",
    "factura global",
    "complemento de pago",
    "complemento carta porte",
    "comprobante de traslado",
    "comprobante fiscal",
]

TAX_REPORTING_WORDS = [
    "DIOT",
    "declaración informativa",
    "devolución de IVA",
    "contabilidad electrónica",
    "declaración anual",
]

INVENTORY_WORDS = [
    "lote",
    "caducidad",
    "trazabilidad",
    "control de inventario",
    "devolución de mercancía",
    "devolución de producto",
    "existencias",
    "traslado de mercancías",
    "carta porte",
]

ACCOUNTING_WORDS = [
    "póliza contable",
    "balanza de comprobación",
    "catálogo de cuentas",
    "asiento contable",
]

POS_WORDS = [
    "ticket",
    "venta al público",
    "punto de venta",
    "venta mostrador",
    "corte de caja",
    "venta y suministro de medicamentos",
]


# ==============================
# FUNCIÓN AUXILIAR
# ==============================

def calculate_module_score(text: str, keywords: list) -> int:
    score = 0
    lower_text = text.lower()

    for word in keywords:
        if word.lower() in lower_text:
            score += 1

    return score


# ==============================
# FUNCIÓN PRINCIPAL
# ==============================

def evaluate_erp_impact(text: str):

    scores = {
        "INVOICING": calculate_module_score(text, INVOICING_WORDS),
        "TAX_REPORTING": calculate_module_score(text, TAX_REPORTING_WORDS),
        "INVENTORY": calculate_module_score(text, INVENTORY_WORDS),
        "ACCOUNTING": calculate_module_score(text, ACCOUNTING_WORDS),
        "POS": calculate_module_score(text, POS_WORDS)
    }

    max_score = max(scores.values())

    if max_score == 0:
        impacted_module = "NONE"
    else:
        impacted_module = max(scores, key=scores.get)

    return impacted_module, scores
