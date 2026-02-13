FISCAL_KEYWORDS = [
    "impuesto", "iva", "isr", "sat", "fiscal", "contribución", "ieps", "cfdi", "carta porte"
]

SANITARY_KEYWORDS = [
    "salud", "medicamento", "cofepris", "farmacia", "establecimiento farmacia", "consultorio médico"
    "control sanitario", "receta",
]

ECONOMIC_KEYWORDS = [
    "economía", "inflación", "precio", "mercado", "consumidor", "ticket", "comprobante", "precio máximo"
]


def classify(title):

    title_lower = title.lower()

    score = 0
    category = "GENERAL"

    # Categoría
    if any(word in title_lower for word in FISCAL_KEYWORDS):
        category = "FISCAL"
        score += 3

    elif any(word in title_lower for word in SANITARY_KEYWORDS):
        category = "SANITARIO"
        score += 3

    elif any(word in title_lower for word in ECONOMIC_KEYWORDS):
        category = "ECONÓMICO"
        score += 2

    # Prioridad
    if score >= 3:
        priority = "ALTA"
    elif score == 2:
        priority = "MEDIA"
    else:
        priority = "BAJA"

    return category, priority, score