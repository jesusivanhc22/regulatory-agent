import logging

from database.connection import (
    get_connection,
    transaction,
    execute,
    executemany,
    adapt_sql,
    fetchone_value,
    init_schema,
    is_postgres,
)

logger = logging.getLogger(__name__)


# ==============================
# INICIALIZACION
# ==============================

def init_db():
    """Crea las tablas si no existen."""
    init_schema()
    logger.info("Base de datos inicializada.")


# ==============================
# OPERACIONES BATCH
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

    with transaction() as conn:
        count_before = fetchone_value(conn, "SELECT COUNT(*) FROM publications")

        if is_postgres():
            executemany(conn,
                "INSERT INTO publications (title, url, source, publication_date, status) "
                "VALUES (%s, %s, %s, %s, 'DISCOVERED') ON CONFLICT DO NOTHING",
                data,
            )
        else:
            executemany(conn,
                "INSERT OR IGNORE INTO publications (title, url, source, publication_date, status) "
                "VALUES (?, ?, ?, ?, 'DISCOVERED')",
                data,
            )

        count_after = fetchone_value(conn, "SELECT COUNT(*) FROM publications")

    new_count = count_after - count_before
    logger.info("[%s] Publicaciones insertadas: %d nuevas de %d scrapeadas.", source, new_count, len(publications))
    return new_count


def get_discovered(limit=100):
    """Obtiene publicaciones pendientes de analisis (version con limit)."""
    conn = get_connection()
    cursor = execute(conn,
        "SELECT id, title, url FROM publications "
        "WHERE status = 'DISCOVERED' ORDER BY detected_at ASC LIMIT ?",
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def mark_as_analyzed(pub_id, category, priority, score):
    """Marca una publicacion como analizada con su clasificacion."""
    with transaction() as conn:
        execute(conn,
            "UPDATE publications SET status = 'ANALYZED', "
            "category = ?, priority = ?, score = ?, "
            "analyzed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (category, priority, score, pub_id),
        )


def mark_batch_as_analyzed(batch_results):
    """Marca multiples publicaciones como analizadas en una sola transaccion."""
    if not batch_results:
        return

    with transaction() as conn:
        executemany(conn,
            "UPDATE publications SET status = 'ANALYZED', "
            "category = ?, priority = ?, score = ?, "
            "analyzed_at = CURRENT_TIMESTAMP WHERE id = ?",
            [(cat, pri, sc, pid) for pid, cat, pri, sc in batch_results],
        )

    logger.info("Batch de %d publicaciones marcadas como analizadas.", len(batch_results))


# ==============================
# CONTENT PIPELINE
# ==============================

def get_discovered_publications():
    """Obtiene publicaciones descubiertas que aun no tienen contenido descargado."""
    conn = get_connection()
    cursor = execute(conn,
        "SELECT id, title, url FROM publications WHERE status = 'DISCOVERED'",
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def save_content(publication_id: int, raw_html: str, full_text: str,
                 content_type: str = "HTML", pdf_path: str = None, pdf_hash: str = None):
    """Guarda el contenido descargado y marca como CONTENT_FETCHED."""
    conn = get_connection()
    execute(conn,
        "UPDATE publications SET "
        "raw_html = ?, full_text = ?, content_type = ?, "
        "pdf_path = ?, pdf_hash = ?, status = 'CONTENT_FETCHED' "
        "WHERE id = ?",
        (raw_html, full_text, content_type, pdf_path, pdf_hash, publication_id),
    )
    conn.commit()
    conn.close()


# ==============================
# REPROCESSING
# ==============================

def reset_for_reprocessing():
    """Resetea publicaciones ANALYZED que no tienen contenido para reprocesarlas."""
    conn = get_connection()
    cursor = execute(conn, """
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
            ai_summary = NULL,
            ai_actions = NULL,
            ai_deadline = NULL,
            ai_priority = NULL,
            analyzed_at = NULL
        WHERE status = 'ANALYZED'
          AND (full_text IS NULL OR full_text = '')
    """)
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected


def reset_all_analyzed():
    """Resetea TODAS las publicaciones ANALYZED a CONTENT_FETCHED
    para re-analizarlas con reglas actualizadas."""
    conn = get_connection()
    cursor = execute(conn, """
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
            ai_summary = NULL,
            ai_actions = NULL,
            ai_deadline = NULL,
            ai_priority = NULL,
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
# ANALYSIS PIPELINE
# ==============================

def get_pending_publications():
    """Obtiene publicaciones que ya tienen contenido pero aun no han sido analizadas."""
    conn = get_connection()
    cursor = execute(conn,
        "SELECT * FROM publications WHERE status IN ('DISCOVERED', 'CONTENT_FETCHED')",
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def _ensure_columns(conn):
    """Asegura que columnas adicionales existen (solo SQLite, PG las tiene desde schema)."""
    if is_postgres():
        return
    import sqlite3
    for col_sql in [
        "ALTER TABLE publications ADD COLUMN source TEXT",
        "ALTER TABLE publications ADD COLUMN publication_date TEXT",
        "ALTER TABLE publications ADD COLUMN effective_date TEXT",
        "ALTER TABLE publications ADD COLUMN raw_html TEXT",
        "ALTER TABLE publications ADD COLUMN full_text TEXT",
        "ALTER TABLE publications ADD COLUMN content_type TEXT",
        "ALTER TABLE publications ADD COLUMN pdf_path TEXT",
        "ALTER TABLE publications ADD COLUMN pdf_hash TEXT",
        "ALTER TABLE publications ADD COLUMN primary_domain TEXT",
        "ALTER TABLE publications ADD COLUMN health_score INTEGER",
        "ALTER TABLE publications ADD COLUMN fiscal_score INTEGER",
        "ALTER TABLE publications ADD COLUMN retail_score INTEGER",
        "ALTER TABLE publications ADD COLUMN border_region_score INTEGER",
        "ALTER TABLE publications ADD COLUMN currency_score INTEGER",
        "ALTER TABLE publications ADD COLUMN operational_obligation_score INTEGER",
        "ALTER TABLE publications ADD COLUMN regulatory_compliance_score INTEGER DEFAULT 0",
        "ALTER TABLE publications ADD COLUMN invoicing_score INTEGER",
        "ALTER TABLE publications ADD COLUMN tax_reporting_score INTEGER",
        "ALTER TABLE publications ADD COLUMN inventory_score INTEGER",
        "ALTER TABLE publications ADD COLUMN accounting_score INTEGER",
        "ALTER TABLE publications ADD COLUMN pos_score INTEGER",
        "ALTER TABLE publications ADD COLUMN impacted_module TEXT",
        "ALTER TABLE publications ADD COLUMN severity TEXT",
        "ALTER TABLE publications ADD COLUMN impact_flag INTEGER",
        "ALTER TABLE publications ADD COLUMN impact_reason TEXT",
        "ALTER TABLE publications ADD COLUMN ai_summary TEXT",
        "ALTER TABLE publications ADD COLUMN ai_actions TEXT",
        "ALTER TABLE publications ADD COLUMN ai_deadline TEXT",
        "ALTER TABLE publications ADD COLUMN ai_priority TEXT",
    ]:
        try:
            conn.execute(col_sql)
            conn.commit()
        except sqlite3.OperationalError:
            pass


def save_analysis(publication_id: int, analysis_data: dict):
    """Guarda el resultado del analisis y marca como ANALYZED."""
    conn = get_connection()

    _ensure_columns(conn)

    execute(conn, """
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
            ai_summary = ?,
            ai_actions = ?,
            ai_deadline = ?,
            ai_priority = ?,
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
        analysis_data.get("ai_summary"),
        analysis_data.get("ai_actions"),
        analysis_data.get("ai_deadline"),
        analysis_data.get("ai_priority"),
        analysis_data["analyzed_at"],
        publication_id,
    ))

    conn.commit()
    conn.close()


def get_new_impact_publications(since_timestamp: str):
    """Obtiene publicaciones con impacto analizadas despues de un timestamp."""
    conn = get_connection()
    cursor = execute(conn,
        "SELECT * FROM publications "
        "WHERE impact_flag = 1 AND analyzed_at > ? "
        "ORDER BY severity DESC, analyzed_at DESC",
        (since_timestamp,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_impact_publications():
    """Obtiene publicaciones con impacto detectado."""
    conn = get_connection()
    cursor = execute(conn,
        "SELECT * FROM publications WHERE impact_flag = 1 ORDER BY analyzed_at DESC",
    )
    rows = cursor.fetchall()
    conn.close()
    return rows
