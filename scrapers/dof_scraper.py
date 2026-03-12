import logging
from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
import urllib3
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
    seen = set()

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

        if full_url in seen:
            continue

        seen.add(full_url)

        publications.append({
            "title": title,
            "url": full_url,
            "publication_date": datetime.now().date().isoformat(),
        })

    logger.info("Publicaciones detectadas en portada: %d", len(publications))

    return publications


def fetch_dof_by_date(date_obj):

    year = date_obj.year
    month = str(date_obj.month).zfill(2)
    day = str(date_obj.day).zfill(2)

    url = f"{BASE_URL}/index.php?year={year}&month={month}&day={day}"

    publications = []

    try:
        response = requests.get(url, verify=False, timeout=15)
    except Exception as e:
        print(f"Error accediendo DOF {date_obj.date()}:", e)
        return publications

    if response.status_code != 200:
        return publications

    soup = BeautifulSoup(response.text, "html.parser")
    seen = set()

    for link in soup.find_all("a"):

        title = link.get_text(strip=True)
        href = link.get("href")

        if not href or not title:
            continue

        if "nota_detalle.php" not in href:
            continue

        if not href.startswith("http"):
            full_url = f"{BASE_URL}/{href}"
        else:
            full_url = href

        if full_url in seen:
            continue

        seen.add(full_url)

        publications.append({
            "title": title,
            "url": full_url,
            "publication_date": date_obj.date().isoformat(),
        })

    return publications


def run_backfill_scraper(days: int = 120):
    """Scrapea el DOF histórico por N días y guarda en BD (compatible PG/SQLite)."""
    from database.db import save_discovered_batch

    logger.info("Ejecutando backfill DOF por %d dias...", days)

    today = datetime.today()
    total_new = 0

    for i in range(days):
        target_date = today - timedelta(days=i)

        publications = fetch_dof_by_date(target_date)

        if publications:
            new_count = save_discovered_batch(publications, source="DOF")
            total_new += new_count
            if new_count > 0:
                logger.info("[DOF Backfill] %s: %d nuevas de %d",
                            target_date.date(), new_count, len(publications))

    logger.info("Backfill DOF completado: %d nuevas publicaciones en total.", total_new)
    return total_new
