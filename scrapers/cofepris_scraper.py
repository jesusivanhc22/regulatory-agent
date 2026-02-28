"""
Scraper de alertas sanitarias de COFEPRIS.
Extrae alertas de medicamentos, dispositivos medicos, suplementos, etc.
desde las paginas de documentos en gob.mx/cofepris.

Nota: gob.mx tiene un WAF (Web Application Firewall) con challenge crypto
que bloquea requests estandar. Se usa curl_cffi con impersonacion de Chrome
para emular el TLS fingerprint de un navegador real.
"""

import logging
import re
from datetime import datetime, timedelta

from curl_cffi import requests as curl_requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.gob.mx"

COFEPRIS_URLS = {
    "medicamentos": f"{BASE_URL}/cofepris/documentos/alertas-sanitarias-de-medicamentos?state=published",
    "dispositivos_medicos": f"{BASE_URL}/cofepris/documentos/alertas-sanitarias-de-dispositivos-medicos?state=published",
    "suplementos": f"{BASE_URL}/cofepris/documentos/alertas-sanitarias-de-suplementos-alimenticios?state=published",
    "otros": f"{BASE_URL}/cofepris/documentos/alertas-sanitarias-de-otros-productos-y-servicios?state=published",
    "publicidad_enganosa": f"{BASE_URL}/cofepris/documentos/alertas-sanitarias-de-publicidad-enganosa?state=published",
    "aviso_riesgo": f"{BASE_URL}/cofepris/documentos/aviso-de-riesgo-344496",
    "comunicado_riesgo": f"{BASE_URL}/cofepris/documentos/comunicado-de-riesgo-343865",
}

# Regex para extraer fecha del nombre de archivo: ..._{DDMMYYYY}.pdf
_DATE_RE = re.compile(r'(\d{8})\.pdf$', re.IGNORECASE)

# Session reutilizable
_session = None


def _get_session():
    """Devuelve una sesion curl_cffi con impersonacion de Chrome.

    gob.mx tiene un WAF con challenge crypto que detecta el TLS fingerprint
    de requests/urllib3. curl_cffi emula el fingerprint de Chrome real.
    """
    global _session
    if _session is None:
        _session = curl_requests.Session(impersonate="chrome")
    return _session


def _title_from_filename(filename):
    """Extrae un titulo legible del nombre de archivo PDF.

    Ejemplo: '288_Alerta_Sanitaria_Cafiaspirina_19022026.pdf'
           -> 'Alerta Sanitaria Cafiaspirina'
    """
    name = filename.rsplit('.', 1)[0]  # Quitar .pdf
    # Quitar numero de secuencia al inicio
    name = re.sub(r'^\d+_', '', name)
    # Quitar fecha al final (8 digitos)
    name = re.sub(r'_\d{8}$', '', name)
    # Reemplazar guiones bajos por espacios
    return name.replace('_', ' ').strip()


def _parse_date_from_filename(filename):
    """Extrae fecha del nombre de archivo PDF.

    Formato esperado: ..._{DDMMYYYY}.pdf
    Returns: datetime o None si no se puede parsear.
    """
    match = _DATE_RE.search(filename)
    if not match:
        return None
    date_str = match.group(1)
    try:
        return datetime.strptime(date_str, '%d%m%Y')
    except ValueError:
        return None


def _scrape_category(url, category):
    """Scrapea una pagina de documentos COFEPRIS.

    Busca <a> tags con '/cms/uploads/attachment/file/' en el href.
    """
    publications = []
    session = _get_session()

    try:
        response = session.get(url, verify=False, timeout=30)
        response.raise_for_status()
    except Exception as e:
        logger.error("Error accediendo COFEPRIS %s: %s", category, e)
        return publications

    soup = BeautifulSoup(response.text, "html.parser")

    for link in soup.find_all("a", href=True):
        href = link["href"]

        # Solo links a PDFs en el CMS de gob.mx
        if "/cms/uploads/attachment/file/" not in href:
            continue
        if not href.lower().endswith('.pdf'):
            continue

        # URL absoluta
        if href.startswith("http"):
            full_url = href
        else:
            full_url = BASE_URL + href

        # Extraer titulo del filename
        filename = href.split("/")[-1]
        title = _title_from_filename(filename)

        if not title:
            title = link.get_text(strip=True) or filename

        pub_date = _parse_date_from_filename(filename)
        publications.append({
            "title": f"[COFEPRIS] {title}",
            "url": full_url,
            "publication_date": pub_date.date().isoformat() if pub_date else None,
        })

    logger.info("COFEPRIS %s: %d documentos encontrados", category, len(publications))
    return publications


def fetch_cofepris():
    """Scrapea todas las categorias de alertas COFEPRIS.

    Returns:
        List[Dict]: publicaciones con keys 'title' y 'url'.
    """
    logger.info("Iniciando scraping COFEPRIS...")

    all_pubs = []
    seen_urls = set()

    for category, url in COFEPRIS_URLS.items():
        pubs = _scrape_category(url, category)
        for pub in pubs:
            if pub["url"] not in seen_urls:
                seen_urls.add(pub["url"])
                all_pubs.append(pub)

    logger.info("COFEPRIS total: %d documentos unicos", len(all_pubs))
    return all_pubs


def fetch_cofepris_by_date(days_back=180):
    """Scrapea COFEPRIS y filtra por fecha (ultimos N dias).

    La fecha se extrae del nombre del archivo PDF.
    """
    cutoff = datetime.now() - timedelta(days=days_back)
    all_pubs = fetch_cofepris()

    filtered = []
    for pub in all_pubs:
        filename = pub["url"].split("/")[-1]
        pub_date = _parse_date_from_filename(filename)
        if pub_date and pub_date >= cutoff:
            filtered.append(pub)
        elif not pub_date:
            # Si no podemos parsear la fecha, incluir por si acaso
            filtered.append(pub)

    logger.info("COFEPRIS filtrado (%d dias): %d de %d", days_back, len(filtered), len(all_pubs))
    return filtered
