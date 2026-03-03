import logging
import sys
from datetime import datetime, timezone

from analysis.rule_classifier import analyze_publication
from database.db import (
    get_discovered_publications,
    get_pending_publications,
    save_content,
    save_analysis,
    save_discovered_batch,
    get_impact_publications,
    get_new_impact_publications,
)
from scrapers.dof_scraper import fetch_dof
from scrapers.cofepris_scraper import fetch_cofepris
from scrapers.sat_scraper import fetch_sat
from scrapers.content_fetcher import fetch_content
from scrapers.pdf_downloader import download_pdf
from scrapers.text_extractor import extract_from_html, extract_from_pdf
from reporting.executive_report_generator import generate_executive_summary
from notifications.webhook import send_webhook

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

            full_text = ""
            content_type = "NONE"
            pdf_path = None
            pdf_hash = None

            # 2. Si hay HTML, extraer texto
            if raw_html:
                full_text = extract_from_html(raw_html)
                content_type = "HTML"

            # 3. Si hay PDF, descargar y extraer texto
            if pdf_url:
                pdf_path, pdf_hash = download_pdf(pdf_url)

                if pdf_path:
                    pdf_text = extract_from_pdf(pdf_path)
                    if pdf_text:
                        if full_text:
                            full_text = full_text + "\n\n" + pdf_text
                            content_type = "HTML+PDF"
                        else:
                            full_text = pdf_text
                            content_type = "PDF"

            if not full_text:
                logger.warning("Sin contenido para: %s", title[:50])
                errors += 1
                continue

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

        # Obtener fuente (COFEPRIS, SAT, DOF)
        try:
            source = pub["source"] or "DOF"
        except (IndexError, KeyError):
            source = "DOF"

        # Obtener fecha de publicacion si existe
        try:
            pub_date = pub["publication_date"]
        except (IndexError, KeyError):
            pub_date = None

        analysis = analyze_publication(
            title=pub["title"],
            full_text=pub["full_text"] or "",
            source=source,
            publication_date=pub_date
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


def run_scraper():
    """Ejecuta scraping de todas las fuentes y guarda en BD."""
    logger.info("=" * 60)
    logger.info("SCRAPING MULTI-FUENTE INICIADO")
    logger.info("=" * 60)

    # DOF
    dof_pubs = fetch_dof()
    new_dof = save_discovered_batch(dof_pubs, source="DOF")
    logger.info("[DOF] %d nuevas de %d scrapeadas", new_dof, len(dof_pubs))

    # COFEPRIS
    cofepris_pubs = fetch_cofepris()
    new_cofepris = save_discovered_batch(cofepris_pubs, source="COFEPRIS")
    logger.info("[COFEPRIS] %d nuevas de %d scrapeadas", new_cofepris, len(cofepris_pubs))

    # SAT
    sat_pubs = fetch_sat()
    new_sat = save_discovered_batch(sat_pubs, source="SAT")
    logger.info("[SAT] %d nuevas de %d scrapeadas", new_sat, len(sat_pubs))

    total_new = new_dof + new_cofepris + new_sat
    logger.info("SCRAPING COMPLETADO: %d nuevas publicaciones en total", total_new)
    return total_new


def run_full_pipeline():
    """Ejecuta el pipeline completo: scrape -> contenido -> analisis -> notificar.

    Solo dispara webhook si hay publicaciones NUEVAS con impacto
    (analizadas en esta corrida del pipeline).
    """
    # Marcar timestamp antes de iniciar para detectar nuevas al final
    pipeline_start = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # 1. Scraping
    total_new_discovered = run_scraper()

    # 2. Descarga de contenido
    run_content_pipeline()

    # 3. Análisis
    run_analysis_pipeline()

    # 4. Notificar solo si hay nuevas publicaciones con impacto
    new_impact = get_new_impact_publications(pipeline_start)

    if new_impact:
        new_impact_dicts = [dict(row) for row in new_impact]
        pipeline_stats = {
            "new_discovered": total_new_discovered,
            "pipeline_start": pipeline_start,
        }
        send_webhook(new_impact_dicts, pipeline_stats)
        logger.info(
            "NUEVAS publicaciones con impacto: %d (webhook disparado)",
            len(new_impact),
        )
    else:
        logger.info("Sin nuevas publicaciones con impacto. Sin notificaciones.")


if __name__ == "__main__":
    run_full_pipeline()
