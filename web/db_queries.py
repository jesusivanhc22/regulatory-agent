"""
Funciones de consulta SQL especificas para el dashboard web.
Reutiliza connection.py para soporte dual SQLite/PostgreSQL.
"""

import os
import sys

# Asegurar que el directorio raiz del proyecto este en el path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_connection, execute, fetchone_value, is_postgres


def get_summary_stats():
    """Obtiene todas las estadisticas del resumen en un solo roundtrip."""
    conn = get_connection()
    stats = {}

    stats["total"] = fetchone_value(conn, "SELECT COUNT(*) FROM publications")

    cursor = execute(conn, "SELECT status, COUNT(*) as cnt FROM publications GROUP BY status")
    stats["by_status"] = {dict(row)["status"]: dict(row)["cnt"] for row in cursor.fetchall()}

    cursor = execute(conn, """
        SELECT severity, COUNT(*) as cnt FROM publications
        WHERE severity IS NOT NULL
        GROUP BY severity
    """)
    stats["by_severity"] = {dict(row)["severity"]: dict(row)["cnt"] for row in cursor.fetchall()}

    cursor = execute(conn, """
        SELECT primary_domain, COUNT(*) as cnt FROM publications
        WHERE primary_domain IS NOT NULL AND primary_domain != 'NO_RELEVANTE'
        GROUP BY primary_domain
    """)
    stats["by_domain"] = {dict(row)["primary_domain"]: dict(row)["cnt"] for row in cursor.fetchall()}

    cursor = execute(conn, """
        SELECT impacted_module, COUNT(*) as cnt FROM publications
        WHERE impacted_module IS NOT NULL AND impacted_module != 'NONE'
        GROUP BY impacted_module
    """)
    stats["by_module"] = {dict(row)["impacted_module"]: dict(row)["cnt"] for row in cursor.fetchall()}

    stats["impact_count"] = fetchone_value(conn,
        "SELECT COUNT(*) FROM publications WHERE impact_flag = 1")

    stats["last_analyzed"] = fetchone_value(conn,
        "SELECT MAX(analyzed_at) FROM publications")

    cursor = execute(conn, """
        SELECT COALESCE(source, 'DOF') as src, COUNT(*) as cnt
        FROM publications GROUP BY src
    """)
    stats["by_source"] = {dict(row)["src"]: dict(row)["cnt"] for row in cursor.fetchall()}

    # Impacto por fuente (para grafica de cobertura)
    cursor = execute(conn, """
        SELECT COALESCE(source, 'DOF') as src, COUNT(*) as cnt
        FROM publications WHERE impact_flag = 1 GROUP BY src
    """)
    stats["impact_by_source"] = {dict(row)["src"]: dict(row)["cnt"] for row in cursor.fetchall()}

    conn.close()
    return stats


def get_filtered_publications(severity=None, domain=None, module=None,
                               source=None, impact_only=True, page=1,
                               per_page=25, sort_by="analyzed_at",
                               sort_dir="DESC"):
    """Obtiene publicaciones filtradas, paginadas y ordenadas."""
    conn = get_connection()

    ph = "%s" if is_postgres() else "?"

    conditions = []
    params = []

    if impact_only:
        conditions.append("impact_flag = 1")

    if severity:
        conditions.append(f"severity = {ph}")
        params.append(severity)

    if domain:
        conditions.append(f"primary_domain = {ph}")
        params.append(domain)

    if module:
        conditions.append(f"impacted_module = {ph}")
        params.append(module)

    if source:
        conditions.append(f"COALESCE(source, 'DOF') = {ph}")
        params.append(source)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    # Whitelist de columnas para evitar SQL injection
    allowed_sorts = {
        "analyzed_at", "publication_date", "effective_date",
        "severity", "primary_domain", "impacted_module", "title"
    }
    if sort_by not in allowed_sorts:
        sort_by = "analyzed_at"
    sort_dir = "DESC" if sort_dir.upper() == "DESC" else "ASC"

    # Contar total
    count_sql = f"SELECT COUNT(*) FROM publications {where}"
    total = fetchone_value(conn, count_sql, tuple(params) if params else None)

    # Resultados paginados
    offset = (page - 1) * per_page
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT id, title, url, publication_date, effective_date,
               primary_domain, impacted_module, severity, impact_flag,
               impact_reason, analyzed_at, COALESCE(source, 'DOF') as source,
               ai_summary, ai_actions, ai_deadline, ai_priority
        FROM publications
        {where}
        ORDER BY {sort_by} {sort_dir}
        LIMIT {ph} OFFSET {ph}
    """, params + [per_page, offset])

    publications = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return publications, total


def get_publication_by_id(pub_id):
    """Obtiene una publicacion con todos sus campos."""
    conn = get_connection()
    cursor = execute(conn,
        "SELECT *, COALESCE(source, 'DOF') as source FROM publications WHERE id = ?",
        (pub_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def get_pipeline_counts():
    """Obtiene contadores por status para la pagina de pipeline."""
    conn = get_connection()

    cursor = execute(conn, "SELECT status, COUNT(*) as cnt FROM publications GROUP BY status")
    counts = {dict(row)["status"]: dict(row)["cnt"] for row in cursor.fetchall()}

    counts["TOTAL"] = fetchone_value(conn, "SELECT COUNT(*) FROM publications")
    counts["WITH_IMPACT"] = fetchone_value(conn,
        "SELECT COUNT(*) FROM publications WHERE impact_flag = 1")

    conn.close()
    return counts
