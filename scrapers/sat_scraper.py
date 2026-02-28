"""
Scraper de normatividad del SAT (Servicio de Administracion Tributaria).
Extrae documentos de RMF, RGCE y RFA desde el minisite de normatividad.
El sitio principal sat.gob.mx usa SvelteKit (no scrapeable con requests),
pero el minisite de normatividad es HTML estatico.
"""

import logging
import re
from datetime import datetime

import requests
import urllib3
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SAT_BASE = "https://www.sat.gob.mx/minisitio/NormatividadRMFyRGCE"

# Paginas por anno (HTML estatico, sin paginacion)
SAT_URLS = {
    2026: f"{SAT_BASE}/normatividad_rmf_rgce2026.html",
    2025: f"{SAT_BASE}/normatividad_rmf_rgce2025.html",
}

# Mapeo de meses en espanol
MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

# Regex para fecha en texto: "28 de diciembre de 2025"
_SPANISH_DATE_RE = re.compile(
    r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})'
)

# Session reutilizable
_session = None


def _get_session():
    """Devuelve una sesion HTTP reutilizable con reintentos automaticos."""
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


def _parse_spanish_date(text):
    """Parsea fecha en espanol: '28 de diciembre de 2025' -> datetime."""
    match = _SPANISH_DATE_RE.search(text)
    if not match:
        return None
    day = int(match.group(1))
    month_name = match.group(2).lower()
    year = int(match.group(3))

    month = MESES.get(month_name)
    if not month:
        return None

    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def _scrape_year(year, url):
    """Scrapea una pagina de normatividad SAT para un anno dado.

    Busca <a> tags con href terminando en .pdf.
    URLs son relativas al SAT_BASE.
    """
    publications = []
    session = _get_session()

    try:
        response = session.get(url, verify=False, timeout=20)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error("Error accediendo SAT normatividad %d: %s", year, e)
        return publications

    soup = BeautifulSoup(response.text, "html.parser")

    for link in soup.find_all("a", href=True):
        href = link["href"]

        if not href.lower().endswith('.pdf'):
            continue

        # Construir URL absoluta
        if href.startswith("http"):
            full_url = href
        else:
            # URLs relativas al directorio del minisite
            full_url = f"{SAT_BASE}/{href}"

        # Extraer titulo: texto bold dentro del link, o el texto del link
        bold = link.find("b") or link.find("strong")
        if bold:
            title = bold.get_text(strip=True)
        else:
            title = link.get_text(strip=True)

        if not title:
            # Usar filename como fallback
            title = href.split("/")[-1].replace('.pdf', '').replace('_', ' ')

        # Extraer fecha de publicacion del texto del <li> padre
        parent_li = link.find_parent("li")
        pub_date = None
        if parent_li:
            pub_date = _parse_spanish_date(parent_li.get_text())

        publications.append({
            "title": f"[SAT] {title}",
            "url": full_url,
            "publication_date": pub_date.date().isoformat() if pub_date else None,
        })

    logger.info("SAT %d: %d documentos encontrados", year, len(publications))
    return publications


def fetch_sat(years=None):
    """Scrapea paginas de normatividad SAT.

    Args:
        years: lista de annos a scrapear. Default: anno actual + anterior.

    Returns:
        List[Dict]: publicaciones con keys 'title' y 'url'.
    """
    if years is None:
        current_year = datetime.now().year
        years = [current_year, current_year - 1]

    logger.info("Iniciando scraping SAT normatividad (annos: %s)...", years)

    all_pubs = []
    seen_urls = set()

    for year in years:
        url = SAT_URLS.get(year)
        if not url:
            # Intentar construir URL para annos no predefinidos
            url = f"{SAT_BASE}/normatividad_rmf_rgce{year}.html"

        pubs = _scrape_year(year, url)
        for pub in pubs:
            if pub["url"] not in seen_urls:
                seen_urls.add(pub["url"])
                all_pubs.append(pub)

    logger.info("SAT total: %d documentos unicos", len(all_pubs))
    return all_pubs
