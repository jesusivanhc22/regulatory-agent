import logging
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import urllib3

try:
    from curl_cffi import requests as curl_requests
except ImportError:
    curl_requests = None

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

# Dominios que requieren curl_cffi (WAF con challenge crypto)
WAF_DOMAINS = ["gob.mx", "cofemersimir.gob.mx"]


def _needs_curl(url):
    """Determina si la URL requiere curl_cffi para bypass de WAF."""
    return any(domain in url for domain in WAF_DOMAINS)


def _fetch_with_curl(url, timeout=30):
    """Fetch usando curl_cffi con impersonación Chrome (para gob.mx)."""
    if curl_requests is None:
        logger.warning("curl_cffi no disponible, usando requests estándar para %s", url[:80])
        return _fetch_standard(url, timeout)

    try:
        session = curl_requests.Session(impersonate="chrome")
        response = session.get(url, verify=False, timeout=timeout)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.error("Error curl_cffi %s: %s", url[:80], e)
        return None


def _fetch_standard(url, timeout=15):
    """Fetch usando requests estándar."""
    try:
        response = requests.get(url, verify=False, timeout=timeout)
        if response.status_code != 200:
            return None
        return response.text
    except Exception as e:
        logger.error("Error descargando %s: %s", url[:80], e)
        return None


def fetch_content(url):
    """Descarga el contenido de una URL y busca links a PDF.

    Soporta:
    - DOF (requests estándar)
    - COFEPRIS / Secretaría de Salud / gob.mx (curl_cffi con WAF bypass)
    - CONAMER / COFEMERSIMIR (requests estándar)
    - PDFs directos (retorna sin descargar HTML)

    Returns:
        tuple: (raw_html, pdf_url)
    """
    # Si la URL apunta directamente a un PDF (COFEPRIS, SAT),
    # no hay página HTML intermedia.
    if url.lower().endswith('.pdf'):
        return None, url

    # Determinar método de fetch según el dominio
    if _needs_curl(url):
        html = _fetch_with_curl(url)
    else:
        html = _fetch_standard(url)

    if not html:
        return None, None

    soup = BeautifulSoup(html, "html.parser")

    pdf_url = None

    for link in soup.find_all("a"):
        href = link.get("href")
        if href and ".pdf" in href.lower():
            if href.startswith("http"):
                pdf_url = href
            else:
                # Construir URL absoluta basada en el dominio de la URL original
                pdf_url = urljoin(url, href)
            break

    return html, pdf_url
