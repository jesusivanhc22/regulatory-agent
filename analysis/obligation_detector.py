from config.keywords import OBLIGATION_KEYWORDS


def calculate_operational_obligation(text: str) -> int:
    """
    Calcula score de obligación operativa.

    Las frases compuestas (de OBLIGATION_KEYWORDS) cuentan +1 cada una.
    Adicionalmente, si "deberá" aparece 5+ veces en el texto, se suma +1
    como señal de carga regulatoria real (no solo mención casual).
    """

    score = 0
    lower_text = text.lower()

    # Frases compuestas específicas
    for word in OBLIGATION_KEYWORDS:
        if word.lower() in lower_text:
            score += 1

    # "deberá/deberán" por frecuencia — solo si aparece muchas veces
    # (indica un texto con obligaciones operativas reales, no mención casual)
    debera_count = lower_text.count("deberá") + lower_text.count("deberán")
    if debera_count >= 5:
        score += 1
    if debera_count >= 15:
        score += 1

    return score
