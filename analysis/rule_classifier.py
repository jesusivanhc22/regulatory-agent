import logging
import unicodedata

from config import CATEGORY_KEYWORDS, CATEGORY_WEIGHTS, PRIORITY_THRESHOLDS

logger = logging.getLogger(__name__)


def _normalize(text):
    """Normaliza texto: minúsculas y elimina acentos para matching robusto."""
    text = text.lower()
    # Descompone caracteres unicode y elimina marcas de acento
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def classify(title):
    """Clasifica una publicación por título con soporte multi-categoría.

    Analiza el título contra todas las categorías, cuenta keywords
    individuales encontrados y acumula score ponderado.

    Returns:
        tuple: (categories: str, priority: str, score: int)
            - categories: categorías separadas por '|' o 'GENERAL'
            - priority: 'ALTA', 'MEDIA' o 'BAJA'
            - score: suma ponderada de keywords encontrados
    """
    title_normalized = _normalize(title)

    score = 0
    matched_categories = []

    for category, keywords in CATEGORY_KEYWORDS.items():
        weight = CATEGORY_WEIGHTS.get(category, 1)
        hits = sum(1 for kw in keywords if _normalize(kw) in title_normalized)

        if hits > 0:
            matched_categories.append(category)
            score += hits * weight

    # Categoría resultante
    if matched_categories:
        category = " | ".join(matched_categories)
    else:
        category = "GENERAL"

    # Prioridad basada en score
    if score >= PRIORITY_THRESHOLDS["ALTA"]:
        priority = "ALTA"
    elif score >= PRIORITY_THRESHOLDS["MEDIA"]:
        priority = "MEDIA"
    else:
        priority = "BAJA"

    logger.debug(
        "Clasificado: '%s' -> %s (prioridad=%s, score=%d)",
        title[:60], category, priority, score,
    )

    return category, priority, score
