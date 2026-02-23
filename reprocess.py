"""
Script para reprocesar publicaciones.

Modo 1 (default): Resetea publicaciones ANALYZED sin contenido → descarga → analiza.
Modo 2 (--reanalyze): Resetea TODAS las ANALYZED con contenido → re-analiza con reglas nuevas.
"""

import sys
from database.db import reset_for_reprocessing, reset_all_analyzed
from main import run_content_pipeline, run_analysis_pipeline


def reprocess():
    """Reprocesa publicaciones sin contenido: descarga + analiza."""

    print("🔄 Reprocesando publicaciones sin contenido...")

    affected = reset_for_reprocessing()
    print(f"📋 {affected} publicaciones reseteadas a DISCOVERED.")

    if affected == 0:
        print("✅ Todas las publicaciones ya tienen contenido. Nada que reprocesar.")
        return

    run_content_pipeline()
    run_analysis_pipeline()

    print("✅ Reprocesamiento completo.")


def reanalyze():
    """Re-analiza publicaciones que ya tienen contenido con reglas actualizadas."""

    print("🔄 Re-analizando con reglas actualizadas...")

    affected = reset_all_analyzed()
    print(f"📋 {affected} publicaciones reseteadas a CONTENT_FETCHED.")

    if affected == 0:
        print("✅ No hay publicaciones analizadas con contenido. Nada que re-analizar.")
        return

    run_analysis_pipeline()

    print("✅ Re-análisis completo.")


if __name__ == "__main__":
    if "--reanalyze" in sys.argv:
        reanalyze()
    else:
        reprocess()
