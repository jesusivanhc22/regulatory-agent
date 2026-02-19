import logging
import sys

from analysis.rule_classifier import classify
from config import BATCH_SIZE
from database.db import (
    get_discovered,
    init_db,
    mark_batch_as_analyzed,
    save_discovered_batch,
)
from reporting.report_generator import generate
from scrapers.dof_scraper import fetch_dof

# ── Configuración de logging ────────────────────────────────────────
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


def main():
    logger.info("=" * 60)
    logger.info("PIPELINE INICIADO - PASO B MEJORADO")
    logger.info("=" * 60)

    # 1. Inicializar BD
    init_db()

    # 2. Scraping
    scraped = fetch_dof()

    if not scraped:
        logger.warning("No se obtuvieron publicaciones del DOF.")
        return

    # 3. Guardar en batch (INSERT OR IGNORE maneja duplicados)
    new_count = save_discovered_batch(scraped)
    logger.info("Resumen scraping: %d scrapeadas, %d nuevas.", len(scraped), new_count)

    # 4. Obtener pendientes
    discovered = get_discovered(limit=100)
    logger.info("Publicaciones pendientes de análisis: %d", len(discovered))

    if not discovered:
        logger.info("No hay publicaciones pendientes. Pipeline terminado.")
        return

    # 5. Procesar en batches
    total_processed = 0
    total_errors = 0

    for i in range(0, len(discovered), BATCH_SIZE):
        batch = discovered[i:i + BATCH_SIZE]
        batch_number = (i // BATCH_SIZE) + 1

        logger.info("Procesando batch %d (%d publicaciones)...", batch_number, len(batch))

        results = []
        db_updates = []

        for pub_id, title, url in batch:
            try:
                category, priority, score = classify(title)

                results.append({
                    "title": title,
                    "category": category,
                    "priority": priority,
                    "score": score,
                    "url": url,
                })

                db_updates.append((pub_id, category, priority, score))
                total_processed += 1

            except Exception:
                logger.exception("Error clasificando pub_id=%d: '%s'", pub_id, title[:80])
                total_errors += 1
                continue

        # Marcar batch completo en una sola transacción
        if db_updates:
            try:
                mark_batch_as_analyzed(db_updates)
            except Exception:
                logger.exception("Error guardando batch %d en BD.", batch_number)
                continue

        # Generar reporte solo si hay resultados
        if results:
            try:
                filename = generate(results, batch_number=batch_number)
                logger.info("Reporte batch %d: %s", batch_number, filename)
            except Exception:
                logger.exception("Error generando reporte batch %d.", batch_number)

    # 6. Resumen final
    logger.info("=" * 60)
    logger.info(
        "PIPELINE COMPLETADO: %d procesadas, %d errores.",
        total_processed, total_errors,
    )
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
