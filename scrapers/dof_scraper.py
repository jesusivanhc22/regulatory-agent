import logging
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

BASE_URL = "https://www.dof.gob.mx"

# Configuración de reintentos y sesión reutilizable
_session = None


def _get_session():
    """Devuelve una sesión HTTP reutilizable con reintentos automáticos."""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        })
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        _session.mount("https://", adapter)
        _session.mount("http://", adapter)
    return _session


def fetch_dof():
    """Scrapea la portada del DOF y devuelve publicaciones encontradas."""
    publications = []

    logger.info("Accediendo a portada DOF...")

    try:
        session = _get_session()
        response = session.get(BASE_URL, verify=False, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error("Error accediendo al DOF: %s", e)
        return publications

    soup = BeautifulSoup(response.text, "html.parser")

    seen_urls = set()

    for link in soup.find_all("a", href=True):
        title = link.get_text(strip=True)
        href = link["href"]

        if not title or "nota_detalle.php" not in href:
            continue

        full_url = urljoin(BASE_URL, href)

        # Evitar duplicados dentro del mismo scrape
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        publications.append({
            "title": title,
            "url": full_url,
        })

    logger.info("Publicaciones detectadas en portada: %d", len(publications))

    return publications
