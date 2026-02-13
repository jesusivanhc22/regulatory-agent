from database.db import (
    init_db,
    url_exists,
    save_discovered,
    get_discovered,
    mark_as_analyzed
)

from scrapers.dof_scraper import fetch_dof
from reporting.report_generator import generate
from analysis.rule_classifier import classify

BATCH_SIZE = 10


def main():

    print("PIPELINE STARTED - PASO B")

    init_db()

    scraped = fetch_dof()

    print(f"Publicaciones detectadas en portada: {len(scraped)}")

    for pub in scraped:
        if not url_exists(pub["url"]):
            save_discovered(pub["title"], pub["url"])

    discovered = get_discovered(limit=100)

    print(f"Publicaciones pendientes: {len(discovered)}")

    if not discovered:
        print("No hay pendientes.")
        return

    for i in range(0, len(discovered), BATCH_SIZE):

        batch = discovered[i:i + BATCH_SIZE]
        results = []

        for pub_id, title, url in batch:

            category, priority, score = classify(title)

            analysis = f"""
Categoría: {category}
Prioridad: {priority}
Score: {score}
URL: {url}
"""

            results.append({
                "title": title,
                "analysis": analysis
            })

            mark_as_analyzed(pub_id, category, priority, score)

        batch_number = (i // BATCH_SIZE) + 1
        filename = generate(results, batch_number=batch_number)

        print(f"Reporte generado: {filename}")


if __name__ == "__main__":
    main()
