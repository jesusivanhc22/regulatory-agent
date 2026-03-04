"""
Scraper de documentos regulatorios de la Secretaría de Salud (gob.mx/salud).

Extrae publicaciones normativas relevantes para farmacias:
- NOMs (Normas Oficiales Mexicanas) del sector salud
- Lineamientos y acuerdos regulatorios
- Actualizaciones de marco jurídico
- Documentos de COFEPRIS publicados vía Secretaría de Salud

Fuente: https://www.gob.mx/salud
Nota: gob.mx tiene WAF — se usa curl_cffi con impersonación Chrome.
"""

import logging
import re
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlencode

try:
    from curl_cffi import requests as curl_requests
except ImportError:
    curl_requests = None  # No disponible en deploy
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.gob.mx"

# URLs de documentos de la Secretaría de Salud
# Archivo general de documentos
SALUD_ARCHIVE_URL = f"{BASE_URL}/salud/es/archivo/documentos"

# Categorías específicas de documentos regulatorios
SALUD_DOC_URLS = {
    "noms": f"{BASE_URL}/salud/en/documentos/normas-oficiales-mexicanas-9705",
    "dof_publications": f"{BASE_URL}/salud/documentos/publicaciones-en-el-diario-oficial-de-la-federacion",
}

# Session reutilizable
_session = None

# Meses en español para parseo de fechas
MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def _get_session():
    """Devuelve una sesión curl_cffi con impersonación de Chrome.

    gob.mx tiene WAF con challenge crypto que bloquea requests estándar.
    """
    global _session
    if _session is None:
        if curl_requests is None:
            logger.warning(
                "curl_cffi no disponible. Scraper de Secretaría de Salud deshabilitado."
            )
            return None
        _session = curl_requests.Session(impersonate="chrome")
    return _session


def _parse_spanish_date(text):
    """Parsea fecha en formato '03 de marzo de 2026'.

    Returns:
        str: fecha ISO (YYYY-MM-DD) o None
    """
    if not text:
        return None

    match = re.search(r'(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})', text.strip())
    if not match:
        return None

    day = int(match.group(1))
    month_name = match.group(2).lower()
    year = int(match.group(3))

    month = MONTHS.get(month_name)
    if not month:
        return None

    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


def _scrape_archive_page(page=1, year=None):
    """Scrapea una página del archivo de documentos de Secretaría de Salud.

    Estructura HTML de cada documento en gob.mx:
        <div>
            "03 de marzo de 2026"     <- fecha (stripped_strings[0])
            "Fecha de publicación"    <- label (stripped_strings[1])
            "Título del Documento"    <- título (stripped_strings[2])
            <a href="/salud/documentos/...">Continuar leyendo</a>
        </div>

    Args:
        page: número de página (1-based)
        year: año para filtrar (opcional)

    Returns:
        tuple: (list[dict], bool) — publicaciones, hay más páginas
    """
    session = _get_session()
    if session is None:
        return [], False

    publications = []

    # Construir URL con parámetros
    params = {
        "idiom": "es",
        "order": "DESC",
        "page": page,
    }
    if year:
        params["year"] = year

    url = f"{SALUD_ARCHIVE_URL}?{urlencode(params)}"

    try:
        response = session.get(url, verify=False, timeout=30)
        response.raise_for_status()
    except Exception as e:
        logger.error("Error accediendo Secretaría de Salud página %d: %s", page, e)
        return publications, False

    soup = BeautifulSoup(response.text, "html.parser")
    seen_urls = set()

    # Buscar links "Continuar leyendo" que apuntan a documentos
    for link in soup.find_all("a", href=True):
        href = link["href"]
        link_text = link.get_text(strip=True).lower()

        # Solo links "Continuar leyendo" que apuntan a documentos de salud
        if "continuar" not in link_text:
            continue
        if "/salud/documentos/" not in href and "/salud/acciones-y-programas/" not in href:
            continue

        # URL absoluta
        full_url = urljoin(BASE_URL, href)
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        # Extraer título y fecha del contenedor padre
        parent = link.find_parent("div")
        if not parent:
            continue

        texts = [t.strip() for t in parent.stripped_strings]
        # Estructura esperada: [fecha, "Fecha de publicación", título, "Continuar leyendo"]
        pub_date = None
        title = None

        if len(texts) >= 3:
            pub_date = _parse_spanish_date(texts[0])
            # El título es el texto que NO es fecha, NO es label, NO es "Continuar leyendo"
            for t in texts:
                t_lower = t.lower()
                if (t_lower not in ("continuar leyendo", "fecha de publicación", "leer más")
                        and not _parse_spanish_date(t)
                        and len(t) > 5):
                    title = t
                    break

        if not title:
            # Fallback: usar slug de la URL como título
            slug = href.split("/")[-1].replace("-", " ").title()
            title = slug

        publications.append({
            "title": f"[SE_SALUD] {title}",
            "url": full_url,
            "publication_date": pub_date,
        })

    # Detectar paginación
    has_more = False
    for a in soup.find_all("a", href=True):
        if re.search(r'page=\d+', a["href"]) and a.get_text(strip=True) in ("»", "›", "Siguiente"):
            has_more = True
            break
    if not has_more and len(publications) >= 8:
        has_more = True

    logger.info(
        "Secretaría de Salud página %d: %d documentos encontrados",
        page, len(publications),
    )
    return publications, has_more


def _scrape_noms_page():
    """Scrapea la página de NOMs de Salud.

    Returns:
        list[dict]: publicaciones de NOMs
    """
    session = _get_session()
    if session is None:
        return []

    publications = []
    url = SALUD_DOC_URLS["noms"]

    try:
        response = session.get(url, verify=False, timeout=30)
        response.raise_for_status()
    except Exception as e:
        logger.error("Error accediendo NOMs de Salud: %s", e)
        return publications

    soup = BeautifulSoup(response.text, "html.parser")
    seen_urls = set()

    # Buscar links a PDFs o páginas de NOMs
    for link in soup.find_all("a", href=True):
        href = link["href"]
        title = link.get_text(strip=True)

        if not title or len(title) < 5:
            continue

        # Links a NOMs (PDFs en DOF o en gob.mx)
        is_nom = (
            "nom-" in title.lower()
            or "nom-" in href.lower()
            or "norma oficial" in title.lower()
            or href.lower().endswith(".pdf")
        )
        if not is_nom:
            continue

        full_url = urljoin(BASE_URL, href)

        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        publications.append({
            "title": f"[SE_SALUD] {title}",
            "url": full_url,
            "publication_date": None,
        })

    logger.info("Secretaría de Salud NOMs: %d documentos encontrados", len(publications))
    return publications


def fetch_sesalud(days_back=180, max_pages=3):
    """Scrapea documentos regulatorios de la Secretaría de Salud.

    Combina:
    1. Archivo general de documentos recientes
    2. Página de NOMs

    Args:
        days_back: días hacia atrás (para filtrar por fecha). Default 180.
        max_pages: máximo de páginas del archivo. Default 3.

    Returns:
        List[Dict]: publicaciones con keys 'title', 'url', 'publication_date'.
    """
    if curl_requests is None:
        logger.warning(
            "curl_cffi no instalado. Saltando Secretaría de Salud."
        )
        return []

    logger.info("Iniciando scraping Secretaría de Salud...")

    all_pubs = []
    seen_urls = set()

    # 1. Archivo general (documentos recientes)
    current_year = datetime.now().year
    for year in [current_year, current_year - 1]:
        for page in range(1, max_pages + 1):
            pubs, has_more = _scrape_archive_page(page=page, year=year)
            for pub in pubs:
                if pub["url"] not in seen_urls:
                    seen_urls.add(pub["url"])
                    all_pubs.append(pub)
            if not has_more:
                break

    # 2. Página específica de NOMs
    nom_pubs = _scrape_noms_page()
    for pub in nom_pubs:
        if pub["url"] not in seen_urls:
            seen_urls.add(pub["url"])
            all_pubs.append(pub)

    # Filtrar por fecha si la publicación tiene fecha
    if days_back:
        cutoff = (datetime.now() - timedelta(days=days_back)).date().isoformat()
        filtered = []
        for pub in all_pubs:
            if pub["publication_date"] and pub["publication_date"] >= cutoff:
                filtered.append(pub)
            elif not pub["publication_date"]:
                # Sin fecha: incluir por si acaso
                filtered.append(pub)
        all_pubs = filtered

    logger.info(
        "Secretaría de Salud total: %d documentos",
        len(all_pubs),
    )
    return all_pubs
