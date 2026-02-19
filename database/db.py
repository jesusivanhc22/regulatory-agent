import logging
import os
import sqlite3
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB_PATH = os.path.join("data", "regulatory.db")


@contextmanager
def _get_connection():
    """Context manager que provee una conexión SQLite con commit/rollback automático."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


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


def save_discovered_batch(publications):
    """Inserta publicaciones en batch, ignorando duplicados por URL.

    Args:
        publications: lista de dicts con keys 'title' y 'url'.

    Returns:
        int: cantidad de publicaciones nuevas insertadas.
    """
    if not publications:
        return 0

    data = [(pub["title"], pub["url"]) for pub in publications]

    with _get_connection() as conn:
        cursor = conn.cursor()

        # Contar existentes antes del insert para saber cuántas son nuevas
        cursor.execute("SELECT COUNT(*) FROM publications")
        count_before = cursor.fetchone()[0]

        cursor.executemany("""
            INSERT OR IGNORE INTO publications (title, url, status)
            VALUES (?, ?, 'DISCOVERED')
        """, data)

        cursor.execute("SELECT COUNT(*) FROM publications")
        count_after = cursor.fetchone()[0]

    new_count = count_after - count_before
    logger.info("Publicaciones insertadas: %d nuevas de %d scrapeadas.", new_count, len(publications))
    return new_count


def get_discovered(limit=100):
    """Obtiene publicaciones pendientes de análisis.

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
