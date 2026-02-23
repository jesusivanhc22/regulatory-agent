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
# CUMPLIMIENTO REGULATORIO SANITARIO
# (Lo que obliga a cambios en el software ERP)
# ==============================

REGULATORY_COMPLIANCE_WORDS = [
    # Validación de sistema
    "sistema computarizado",
    "sistema computarizado validado",
    "validación de sistemas",
    "registro electrónico",
    "registros electrónicos",
    "firma electrónica avanzada",
    "bitácora electrónica",
    # Trazabilidad y control de inventario sanitario
    "trazabilidad",
    "registro de entradas y salidas",
    "control de existencias",
    "control de inventario sanitario",
    "registro de movimientos",
    "cadena de suministro",
    "cadena de distribución",
    # Antimicrobianos y controlados
    "antimicrobiano",
    "antimicrobianos",
    "antibiótico",
    "psicotrópico",
    "estupefaciente",
    "sustancia controlada",
    "receta retenida",
    "receta con código de barras",
    "libro de control",
    # Responsable sanitario
    "responsable sanitario",
    "aviso de responsable sanitario",
    "aviso de funcionamiento",
    "licencia sanitaria",
    # Farmacovigilancia y tecnovigilancia
    "farmacovigilancia",
    "tecnovigilancia",
    "reporte de sospecha",
    "reacción adversa",
    "evento adverso",
    "notificación de sospecha",
    "alertamiento sanitario",
    "alerta sanitaria",
    # Temperatura y almacenamiento
    "control de temperatura",
    "cadena de frío",
    "refrigeración",
    "condiciones de almacenamiento",
    "temperatura de conservación",
    "termómetro calibrado",
    "registro de temperatura",
    # Residuos
    "residuos peligrosos",
    "residuos peligrosos biológico-infecciosos",
    "RPBI",
    "manejo de residuos",
    # Buenas prácticas
    "buenas prácticas de dispensación",
    "buenas prácticas de almacenamiento",
    "buenas prácticas de distribución",
    "buenas prácticas de farmacia",
    # Suplemento FEUM
    "suplemento para establecimientos",
    "farmacopea de los estados unidos mexicanos",
    "FEUM",
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
        "POS": calculate_module_score(text, POS_WORDS),
        "REGULATORY_COMPLIANCE": calculate_module_score(text, REGULATORY_COMPLIANCE_WORDS),
    }

    max_score = max(scores.values())

    if max_score == 0:
        impacted_module = "NONE"
    else:
        impacted_module = max(scores, key=scores.get)

    return impacted_module, scores
