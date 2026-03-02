"""
Extractor de fecha de entrada en vigor desde textos regulatorios mexicanos.

Busca patrones como:
- "entrará en vigor el 1 de marzo de 2026"
- "vigente a partir del 15 de enero de 2026"
- "surtirá efectos a partir del 1 de abril de 2026"
"""

import re
from datetime import datetime

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

# Patrones comunes en documentos regulatorios mexicanos
_EFFECTIVE_DATE_PATTERNS = [
    re.compile(
        r'entr(?:ará|a|ó)\s+en\s+vigor\s+(?:el\s+)?(\d{1,2})\s+de\s+(\w+)\s+(?:de\s+)?(\d{4})',
        re.IGNORECASE,
    ),
    re.compile(
        r'vigente?\s+a\s+partir\s+del?\s+(\d{1,2})\s+de\s+(\w+)\s+(?:de\s+)?(\d{4})',
        re.IGNORECASE,
    ),
    re.compile(
        r'vigencia\s+a\s+partir\s+del?\s+(\d{1,2})\s+de\s+(\w+)\s+(?:de\s+)?(\d{4})',
        re.IGNORECASE,
    ),
    re.compile(
        r'surt(?:irá|e|ió)\s+efectos?\s+(?:a\s+partir\s+del?\s+)?(\d{1,2})\s+de\s+(\w+)\s+(?:de\s+)?(\d{4})',
        re.IGNORECASE,
    ),
    re.compile(
        r'aplicable\s+a\s+partir\s+del?\s+(\d{1,2})\s+de\s+(\w+)\s+(?:de\s+)?(\d{4})',
        re.IGNORECASE,
    ),
    # "al día siguiente de su publicación" → no captura fecha específica, skip
    # Patrón con "del día" o "el día"
    re.compile(
        r'(?:el|del)\s+d[ií]a\s+(\d{1,2})\s+de\s+(\w+)\s+(?:de\s+)?(\d{4})\s*[,.]?\s*(?:entr|surt|vigent)',
        re.IGNORECASE,
    ),
]

# Patrón especial: "al día siguiente de su publicación en el DOF"
_NEXT_DAY_RE = re.compile(
    r'(?:al\s+)?d[ií]a\s+siguiente\s+(?:de\s+)?(?:al\s+de\s+)?su\s+publicaci[oó]n',
    re.IGNORECASE,
)

# Patrón relativo: "a los XX días naturales/hábiles posteriores a la publicación"
_RELATIVE_DAYS_RE = re.compile(
    r'(?:entr(?:ará|a)\s+en\s+vigor|surt(?:irá|e)\s+efectos?|vigente?)\s+'
    r'(?:a\s+los\s+)?(\d{1,3})\s+d[ií]as\s+(?:naturales\s+)?'
    r'(?:posteriores|siguientes|después)\s+'
    r'(?:a\s+(?:la\s+)?|de\s+(?:la\s+)?|al\s+de\s+(?:la\s+)?)?'
    r'(?:su\s+)?publicaci[oó]n',
    re.IGNORECASE,
)


def extract_effective_date(text, publication_date=None):
    """Extrae la fecha de entrada en vigor del texto de una publicación regulatoria.

    Args:
        text: Texto completo de la publicación.
        publication_date: Fecha de publicación (ISO string YYYY-MM-DD) para resolver
                         "al día siguiente de su publicación".

    Returns:
        str: ISO date string (YYYY-MM-DD) o None si no se detecta.
    """
    if not text:
        return None

    # Buscar patrones con fecha explícita
    for pattern in _EFFECTIVE_DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            day = int(match.group(1))
            month_name = match.group(2).lower()
            year = int(match.group(3))

            month = MESES.get(month_name)
            if month:
                try:
                    return datetime(year, month, day).date().isoformat()
                except ValueError:
                    continue

    # Patrón "al día siguiente de su publicación"
    if _NEXT_DAY_RE.search(text) and publication_date:
        try:
            from datetime import timedelta
            pub_dt = datetime.strptime(publication_date, '%Y-%m-%d')
            return (pub_dt + timedelta(days=1)).date().isoformat()
        except ValueError:
            pass

    # Patrón relativo: "a los 60 días naturales posteriores a la publicación"
    if publication_date:
        match = _RELATIVE_DAYS_RE.search(text)
        if match:
            try:
                from datetime import timedelta
                days = int(match.group(1))
                pub_dt = datetime.strptime(publication_date, '%Y-%m-%d')
                return (pub_dt + timedelta(days=days)).date().isoformat()
            except ValueError:
                pass

    return None
