import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

# En deploy (Railway/Render) usa la DB ligera; localmente usa la completa.
# Si regulatory.db no existe (deploy), cae a regulatory_deploy.db automáticamente.
_db_name = os.environ.get("DB_NAME", "regulatory.db")
_db_path = BASE_DIR / "data" / _db_name
if not _db_path.exists() and _db_name == "regulatory.db":
    _db_path = BASE_DIR / "data" / "regulatory_deploy.db"
DB_PATH = _db_path


# ==============================
# CONEXIÓN
# ==============================

@contextmanager
def _get_connection():
    """Context manager que provee una conexión SQLite con commit/rollback automático."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_connection():
    """Retorna una conexión SQLite con row_factory para acceso por nombre de columna."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


# ==============================
# INICIALIZACIÓN (origin/main)
# ==============================

def init_db():
    """Crea la tabla de publicaciones si no existe."""
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS publications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                url TEXT UNIQUE,
                status TEXT DEFAULT 'DISCOVERED',
                category TEXT,
                priority TEXT,
                score INTEGER DEFAULT 0,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                analyzed_at TIMESTAMP
            )
        """)
    logger.info("Base de datos inicializada.")


# ==============================
# OPERACIONES BATCH (origin/main)
# ==============================

def save_discovered_batch(publications, source="DOF"):
    """Inserta publicaciones en batch, ignorando duplicados por URL.

    Args:
        publications: lista de dicts con keys 'title' y 'url'.
        source: fuente de las publicaciones ('DOF', 'COFEPRIS', 'SAT').

    Returns:
        int: cantidad de publicaciones nuevas insertadas.
    """
    if not publications:
        return 0

    data = [(pub["title"], pub["url"], source, pub.get("publication_date"))
            for pub in publications]

    with _get_connection() as conn:
        cursor = conn.cursor()

        # Contar existentes antes del insert para saber cuántas son nuevas
        cursor.execute("SELECT COUNT(*) FROM publications")
        count_before = cursor.fetchone()[0]

        cursor.executemany("""
            INSERT OR IGNORE INTO publications (title, url, source, publication_date, status)
            VALUES (?, ?, ?, ?, 'DISCOVERED')
        """, data)

        cursor.execute("SELECT COUNT(*) FROM publications")
        count_after = cursor.fetchone()[0]

    new_count = count_after - count_before
    logger.info("[%s] Publicaciones insertadas: %d nuevas de %d scrapeadas.", source, new_count, len(publications))
    return new_count


def get_discovered(limit=100):
    """Obtiene publicaciones pendientes de análisis (versión con limit).

    Returns:
        list[tuple]: lista de (id, title, url).
    """
    with _get_connection() as conn:
        cursor = conn.execute("""
            SELECT id, title, url
            FROM publications
            WHERE status = 'DISCOVERED'
            ORDER BY detected_at ASC
            LIMIT ?
        """, (limit,))
        return cursor.fetchall()


def mark_as_analyzed(pub_id, category, priority, score):
    """Marca una publicación como analizada con su clasificación."""
    with _get_connection() as conn:
        conn.execute("""
            UPDATE publications
            SET status = 'ANALYZED',
                category = ?,
                priority = ?,
                score = ?,
                analyzed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (category, priority, score, pub_id))


def mark_batch_as_analyzed(batch_results):
    """Marca múltiples publicaciones como analizadas en una sola transacción.

    Args:
        batch_results: lista de tuples (pub_id, category, priority, score).
    """
    if not batch_results:
        return

    with _get_connection() as conn:
        conn.executemany("""
            UPDATE publications
            SET status = 'ANALYZED',
                category = ?,
                priority = ?,
                score = ?,
                analyzed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, [(cat, pri, sc, pid) for pid, cat, pri, sc in batch_results])

    logger.info("Batch de %d publicaciones marcadas como analizadas.", len(batch_results))


# ==============================
# CONTENT PIPELINE (stash)
# ==============================

def get_discovered_publications():
    """
    Obtiene publicaciones descubiertas que aún no tienen contenido descargado.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, url FROM publications
        WHERE status = 'DISCOVERED'
    """)

    rows = cursor.fetchall()
    conn.close()
    return rows


def save_content(publication_id: int, raw_html: str, full_text: str,
                 content_type: str = "HTML", pdf_path: str = None, pdf_hash: str = None):
    """
    Guarda el contenido descargado y marca como CONTENT_FETCHED.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE publications SET
            raw_html = ?,
            full_text = ?,
            content_type = ?,
            pdf_path = ?,
            pdf_hash = ?,
            status = 'CONTENT_FETCHED'
        WHERE id = ?
    """, (raw_html, full_text, content_type, pdf_path, pdf_hash, publication_id))

    conn.commit()
    conn.close()


# ==============================
# REPROCESSING (stash)
# ==============================

def reset_for_reprocessing():
    """
    Resetea publicaciones ANALYZED que no tienen contenido para reprocesarlas.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE publications
        SET status = 'DISCOVERED',
            primary_domain = NULL,
            health_score = NULL,
            fiscal_score = NULL,
            retail_score = NULL,
            border_region_score = NULL,
            currency_score = NULL,
            operational_obligation_score = NULL,
            invoicing_score = NULL,
            tax_reporting_score = NULL,
            inventory_score = NULL,
            accounting_score = NULL,
            pos_score = NULL,
            regulatory_compliance_score = NULL,
            impacted_module = NULL,
            severity = NULL,
            impact_flag = NULL,
            impact_reason = NULL,
            analyzed_at = NULL
        WHERE status = 'ANALYZED'
          AND (full_text IS NULL OR full_text = '')
    """)

    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected


def reset_all_analyzed():
    """
    Resetea TODAS las publicaciones ANALYZED a CONTENT_FETCHED
    para re-analizarlas con reglas actualizadas.
    Solo aplica a las que tienen full_text (contenido descargado).
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE publications
        SET status = 'CONTENT_FETCHED',
            primary_domain = NULL,
            health_score = NULL,
            fiscal_score = NULL,
            retail_score = NULL,
            border_region_score = NULL,
            currency_score = NULL,
            operational_obligation_score = NULL,
            invoicing_score = NULL,
            tax_reporting_score = NULL,
            inventory_score = NULL,
            accounting_score = NULL,
            pos_score = NULL,
            regulatory_compliance_score = NULL,
            impacted_module = NULL,
            severity = NULL,
            impact_flag = NULL,
            impact_reason = NULL,
            analyzed_at = NULL
        WHERE status = 'ANALYZED'
          AND full_text IS NOT NULL
          AND full_text != ''
    """)

    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected


# ==============================
# ANALYSIS PIPELINE (stash)
# ==============================

def get_pending_publications():
    """
    Obtiene publicaciones que ya tienen contenido
    pero aún no han sido analizadas.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM publications
        WHERE status IN ('DISCOVERED', 'CONTENT_FETCHED')
    """)

    rows = cursor.fetchall()
    conn.close()
    return rows


def save_analysis(publication_id: int, analysis_data: dict):
    """
    Guarda el resultado del análisis y marca como ANALYZED
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Migraciones: asegurar que columnas nuevas existen
    for col_sql in [
        "ALTER TABLE publications ADD COLUMN regulatory_compliance_score INTEGER DEFAULT 0",
        "ALTER TABLE publications ADD COLUMN effective_date TEXT",
    ]:
        try:
            cursor.execute(col_sql)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # La columna ya existe

    cursor.execute("""
        UPDATE publications SET
            primary_domain = ?,
            health_score = ?,
            fiscal_score = ?,
            retail_score = ?,
            border_region_score = ?,
            currency_score = ?,
            operational_obligation_score = ?,
            invoicing_score = ?,
            tax_reporting_score = ?,
            inventory_score = ?,
            accounting_score = ?,
            pos_score = ?,
            regulatory_compliance_score = ?,
            impacted_module = ?,
            severity = ?,
            impact_flag = ?,
            impact_reason = ?,
            effective_date = ?,
            analyzed_at = ?,
            status = 'ANALYZED'
        WHERE id = ?
    """, (
        analysis_data["primary_domain"],
        analysis_data["health_score"],
        analysis_data["fiscal_score"],
        analysis_data["retail_score"],
        analysis_data["border_region_score"],
        analysis_data["currency_score"],
        analysis_data["operational_obligation_score"],
        analysis_data["invoicing_score"],
        analysis_data["tax_reporting_score"],
        analysis_data["inventory_score"],
        analysis_data["accounting_score"],
        analysis_data["pos_score"],
        analysis_data.get("regulatory_compliance_score", 0),
        analysis_data["impacted_module"],
        analysis_data["severity"],
        analysis_data["impact_flag"],
        analysis_data["impact_reason"],
        analysis_data.get("effective_date"),
        analysis_data["analyzed_at"],
        publication_id
    ))

    conn.commit()
    conn.close()


def get_new_impact_publications(since_timestamp: str):
    """
    Obtiene publicaciones con impacto que fueron analizadas DESPUÉS
    de un timestamp dado. Sirve para detectar nuevas publicaciones
    en cada corrida del pipeline.

    Args:
        since_timestamp: ISO timestamp (e.g. '2026-03-02 10:00:00')

    Returns:
        list[Row]: publicaciones nuevas con impacto.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM publications
        WHERE impact_flag = 1 AND analyzed_at > ?
        ORDER BY severity DESC, analyzed_at DESC
    """, (since_timestamp,))

    rows = cursor.fetchall()
    conn.close()
    return rows


def get_impact_publications():
    """
    Obtiene publicaciones con impacto detectado
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM publications
        WHERE impact_flag = 1
        ORDER BY analyzed_at DESC
    """)

    rows = cursor.fetchall()
    conn.close()
    return rows
