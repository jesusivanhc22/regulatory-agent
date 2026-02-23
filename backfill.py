from main import run_content_pipeline, run_analysis_pipeline
from scrapers.dof_scraper import run_backfill_scraper


def run_backfill():

    print("📅 Ejecutando backfill histórico...")

    # 1. Scrape de URLs históricas
    run_backfill_scraper(days=120)

    # 2. Descargar contenido HTML + PDF de cada publicación
    run_content_pipeline()

    # 3. Analizar publicaciones con contenido real
    run_analysis_pipeline()

    print("📦 Backfill completo.")


if __name__ == "__main__":
    run_backfill()
