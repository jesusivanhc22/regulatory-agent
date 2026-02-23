from config.keywords import (
    HEALTH_KEYWORDS,
    FISCAL_KEYWORDS,
    RETAIL_KEYWORDS,
    BORDER_KEYWORDS,
    CURRENCY_KEYWORDS
)


def calculate_score(text: str, keywords: list) -> int:
    score = 0
    lower_text = text.lower()

    for word in keywords:
        if word.lower() in lower_text:
            score += 1

    return score


def classify_domain(text: str):

    scores = {
        "HEALTH": calculate_score(text, HEALTH_KEYWORDS),
        "FISCAL": calculate_score(text, FISCAL_KEYWORDS),
        "RETAIL": calculate_score(text, RETAIL_KEYWORDS),
        "BORDER": calculate_score(text, BORDER_KEYWORDS),
        "CURRENCY": calculate_score(text, CURRENCY_KEYWORDS)
    }

    primary_domain = max(scores, key=scores.get)

    return primary_domain, scores
