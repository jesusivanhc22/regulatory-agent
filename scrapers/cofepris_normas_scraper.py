"""
Scraper de NOMs y lineamientos de COFEPRIS (transparencia.cofepris.gob.mx).

A diferencia del cofepris_scraper.py que extrae ALERTAS SANITARIAS,
este scraper extrae el MARCO NORMATIVO: NOMs, lineamientos, acuerdos
y reglamentos que definen las reglas de operación para farmacias.

Fuente: https://transparencia.cofepris.gob.mx/index.php/es/marco-juridico/
Categorías:
  - NOMs de medicamentos
  - NOMs de dispositivos médicos
  - NOMs de insumos para la salud
  - Lineamientos
  - Reglamentos

Nota: transparencia.cofepris.gob.mx NO tiene WAF agresivo (no gob.mx),
se puede usar requests estándar.
"""

import logging
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

BASE_URL = "https://transparencia.cofepris.gob.mx"

# Páginas del marco jurídico relevantes para farmacias
NORMAS_URLS = {
    "noms_medicamentos": f"{BASE_URL}/index.php/es/allcategories-es-es/63-transparencia/marco-juridico/normas-oficiales-mexicanas/medicamentos",
    "noms_dispositivos": f"{BASE_URL}/index.php/es/marco-juridico/normas-oficiales-mexicanas/dispositivos-medicos",
    "lineamientos": f"{BASE_URL}/index.php/es/marco-juridico/lineamientos",
    "reglamentos": f"{BASE_URL}/index.php/es/marco-juridico/reglamentos",
}

# Session reutilizable
_session = None


def _get_session():
    """Sesión HTTP reutilizable."""
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


def _scrape_normas_page(url, category):
    """Scrapea una página del marco jurídico de COFEPRIS.

    La estructura es una tabla HTML con columnas:
    - Nombre/Clave de NOM
    - Título
    - Fecha de publicación en DOF
    - Fecha de entrada en vigor
    - Estado actual
    - Enlaces (PDF)

    Returns:
        list[dict]: publicaciones encontradas
    """
    session = _get_session()
    publications = []

    try:
        response = session.get(url, verify=False, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error("Error accediendo COFEPRIS normas (%s): %s", category, e)
        return publications

    soup = BeautifulSoup(response.text, "html.parser")
    seen_urls = set()

    # Buscar links a PDFs (DOF o gob.mx)
    for link in soup.find_all("a", href=True):
        href = link["href"]
        title = link.get_text(strip=True)

        # Filtrar: solo links a PDFs o a páginas del DOF
        is_relevant = (
            href.lower().endswith(".pdf")
            or "dof.gob.mx" in href
            or "nota_detalle" in href
            or "normasOficiales" in href
        )
        if not is_relevant:
            continue

        if not title or len(title) < 3:
            continue

        # Construir URL absoluta
        if href.startswith("http"):
            full_url = href
        else:
            full_url = urljoin(BASE_URL, href)

        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        # Intentar extraer contexto del row padre (tabla)
        pub_date = None
        parent_row = link.find_parent("tr")
        if parent_row:
            cells = parent_row.find_all("td")
            # Buscar fecha en las celdas
            for cell in cells:
                cell_text = cell.get_text(strip=True)
                if "dof" in cell_text.lower() or "/" in cell_text:
                    # Intentar parsear fecha tipo "DOF-09-10-2020" o "09/10/2020"
                    import re
                    date_match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', cell_text)
                    if date_match:
                        day, month, year = date_match.groups()
                        try:
                            from datetime import datetime
                            pub_date = datetime(int(year), int(month), int(day)).date().isoformat()
                        except ValueError:
                            pass
                    break

        # Mejorar título para NOMs
        if title.lower().startswith("descargar") or len(title) < 10:
            # Buscar título en la misma fila de tabla
            if parent_row:
                cells = parent_row.find_all("td")
                for cell in cells:
                    cell_text = cell.get_text(strip=True)
                    if "nom-" in cell_text.lower() or len(cell_text) > 20:
                        title = cell_text[:200]
                        break

        publications.append({
            "title": f"[COFEPRIS_NORMAS] {title}",
            "url": full_url,
            "publication_date": pub_date,
        })

    logger.info(
        "COFEPRIS normas (%s): %d documentos encontrados",
        category, len(publications),
    )
    return publications


def fetch_cofepris_normas():
    """Scrapea todas las categorías del marco normativo de COFEPRIS.

    Returns:
        List[Dict]: publicaciones con keys 'title', 'url', 'publication_date'.
    """
    logger.info("Iniciando scraping marco normativo COFEPRIS...")

    all_pubs = []
    seen_urls = set()

    for category, url in NORMAS_URLS.items():
        pubs = _scrape_normas_page(url, category)
        for pub in pubs:
            if pub["url"] not in seen_urls:
                seen_urls.add(pub["url"])
                all_pubs.append(pub)

    logger.info("COFEPRIS normas total: %d documentos únicos", len(all_pubs))
    return all_pubs
