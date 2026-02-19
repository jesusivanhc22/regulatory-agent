import logging
import os
from collections import Counter
from datetime import datetime

from config import REPORTS_DIR

logger = logging.getLogger(__name__)


def generate(results, batch_number=1):
    """Genera un reporte Markdown con resumen ejecutivo.

    Args:
        results: lista de dicts con keys 'title', 'category', 'priority', 'score', 'url'.
        batch_number: número de batch para el nombre del archivo.

    Returns:
        str: ruta del archivo generado.
    """
    os.makedirs(REPORTS_DIR, exist_ok=True)

    month = datetime.now().strftime("%Y_%m")
    timestamp = datetime.now().strftime("%H%M%S")
    filename = os.path.join(REPORTS_DIR, f"report_{month}_batch{batch_number}_{timestamp}.md")

    # ── Resumen ejecutivo ───────────────────────────────────────────
    cat_counter = Counter(r["category"] for r in results)
    pri_counter = Counter(r["priority"] for r in results)

    with open(filename, "w", encoding="utf-8") as f:
        f.write("# Reporte Regulatorio Mensual\n\n")
        f.write(f"**Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"**Batch:** {batch_number} | **Total publicaciones:** {len(results)}\n\n")

        # Resumen por categoría
        f.write("## Resumen Ejecutivo\n\n")
        f.write("### Por Categoría\n")
        f.write("| Categoría | Cantidad |\n")
        f.write("|-----------|----------|\n")
        for cat, count in cat_counter.most_common():
            f.write(f"| {cat} | {count} |\n")

        f.write("\n### Por Prioridad\n")
        f.write("| Prioridad | Cantidad |\n")
        f.write("|-----------|----------|\n")
        for pri, count in pri_counter.most_common():
            f.write(f"| {pri} | {count} |\n")

        f.write("\n---\n\n")

        # Detalle de publicaciones (ordenadas por score descendente)
        f.write("## Detalle de Publicaciones\n\n")
        for r in sorted(results, key=lambda x: x["score"], reverse=True):
            f.write(f"### {r['title']}\n\n")
            f.write(f"- **Categoría:** {r['category']}\n")
            f.write(f"- **Prioridad:** {r['priority']}\n")
            f.write(f"- **Score:** {r['score']}\n")
            f.write(f"- **URL:** [{r['url']}]({r['url']})\n\n")

    logger.info("Reporte generado: %s", filename)
    return filename
