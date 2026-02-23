import logging
import sys

from analysis.rule_classifier import analyze_publication
from database.db import (
    get_discovered_publications,
    get_pending_publications,
    save_content,
    save_analysis,
    get_impact_publications
)
from scrapers.content_fetcher import fetch_content
from scrapers.pdf_downloader import download_pdf
from scrapers.text_extractor import extract_from_html, extract_from_pdf
from reporting.executive_report_generator import generate_executive_summary

# -- Configuración de logging ------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def run_content_pipeline():
    """
    Descarga el contenido (HTML + PDF) de publicaciones descubiertas
    y extrae el texto completo para analisis posterior.
    """

    logger.info("=" * 60)
    logger.info("CONTENT PIPELINE INICIADO")
    logger.info("=" * 60)

    publications = get_discovered_publications()

    if not publications:
        logger.info("No hay publicaciones pendientes de descarga.")
        return

    logger.info("Publicaciones por descargar: %d", len(publications))

    success = 0
    errors = 0

    for pub in publications:
        pub_id = pub["id"]
        title = pub["title"]
        url = pub["url"]

        logger.info("  Descargando: %s...", title[:70])

        try:
            # 1. Fetch HTML y detectar PDF
            raw_html, pdf_url = fetch_content(url)

            if not raw_html:
                logger.warning("Sin contenido HTML para: %s", title[:50])
                errors += 1
                continue

            # 2. Extraer texto del HTML
            full_text = extract_from_html(raw_html)
            content_type = "HTML"
            pdf_path = None
            pdf_hash = None

            # 3. Si hay PDF, descargar y extraer texto adicional
            if pdf_url:
                pdf_path, pdf_hash = download_pdf(pdf_url)

                if pdf_path:
                    pdf_text = extract_from_pdf(pdf_path)
                    if pdf_text:
                        full_text = full_text + "\n\n" + pdf_text
                        content_type = "HTML+PDF"

            # 4. Guardar en BD
            save_content(
                publication_id=pub_id,
                raw_html=raw_html,
                full_text=full_text,
                content_type=content_type,
                pdf_path=pdf_path,
                pdf_hash=pdf_hash,
            )

            success += 1

        except Exception:
            logger.exception("Error procesando %s", title[:50])
            errors += 1
            continue

    logger.info("=" * 60)
    logger.info("CONTENT PIPELINE COMPLETADO: %d exitosas, %d errores.", success, errors)
    logger.info("=" * 60)


def run_analysis_pipeline():

    logger.info("=" * 60)
    logger.info("ANALYSIS PIPELINE INICIADO")
    logger.info("=" * 60)

    publications = get_pending_publications()

    if not publications:
        logger.info("No hay publicaciones pendientes.")
        return

    logger.info("Publicaciones pendientes: %d", len(publications))

    for pub in publications:
        logger.info("Analizando: %s", pub['title'])

        analysis = analyze_publication(
            title=pub["title"],
            full_text=pub["full_text"] or ""
        )

        save_analysis(pub["id"], analysis)

    logger.info("Analisis completado.")

    # Generar reporte ejecutivo
    impact_pubs = get_impact_publications()

    report = generate_executive_summary(impact_pubs)

    with open("impact_report.md", "w", encoding="utf-8") as f:
        f.write(report)

    logger.info("Reporte generado: impact_report.md (%d con impacto)", len(impact_pubs))

    logger.info("=" * 60)
    logger.info("ANALYSIS PIPELINE COMPLETADO")
    logger.info("=" * 60)


if __name__ == "__main__":
    run_analysis_pipeline()
