"""
Funciones de consulta SQL especificas para el dashboard web.
Reutiliza get_connection() de database/db.py.
"""

import os
import sys

# Asegurar que el directorio raiz del proyecto este en el path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import get_connection


def get_summary_stats():
    """Obtiene todas las estadisticas del resumen en un solo roundtrip."""
    conn = get_connection()
    cursor = conn.cursor()

    stats = {}

    # Total publicaciones
    cursor.execute("SELECT COUNT(*) FROM publications")
    stats["total"] = cursor.fetchone()[0]

    # Por status
    cursor.execute("SELECT status, COUNT(*) as cnt FROM publications GROUP BY status")
    stats["by_status"] = {row["status"]: row["cnt"] for row in cursor.fetchall()}

    # Por severidad (solo analizadas)
    cursor.execute("""
        SELECT severity, COUNT(*) as cnt FROM publications
        WHERE severity IS NOT NULL
        GROUP BY severity
    """)
    stats["by_severity"] = {row["severity"]: row["cnt"] for row in cursor.fetchall()}

    # Por dominio primario (excluyendo NO_RELEVANTE)
    cursor.execute("""
        SELECT primary_domain, COUNT(*) as cnt FROM publications
        WHERE primary_domain IS NOT NULL AND primary_domain != 'NO_RELEVANTE'
        GROUP BY primary_domain
    """)
    stats["by_domain"] = {row["primary_domain"]: row["cnt"] for row in cursor.fetchall()}

    # Por modulo impactado (excluyendo NONE)
    cursor.execute("""
        SELECT impacted_module, COUNT(*) as cnt FROM publications
        WHERE impacted_module IS NOT NULL AND impacted_module != 'NONE'
        GROUP BY impacted_module
    """)
    stats["by_module"] = {row["impacted_module"]: row["cnt"] for row in cursor.fetchall()}

    # Con impacto
    cursor.execute("SELECT COUNT(*) FROM publications WHERE impact_flag = 1")
    stats["impact_count"] = cursor.fetchone()[0]

    # Ultima fecha de analisis
    cursor.execute("SELECT MAX(analyzed_at) FROM publications")
    stats["last_analyzed"] = cursor.fetchone()[0]

    # Por fuente
    cursor.execute("""
        SELECT COALESCE(source, 'DOF') as src, COUNT(*) as cnt
        FROM publications GROUP BY src
    """)
    stats["by_source"] = {row["src"]: row["cnt"] for row in cursor.fetchall()}

    conn.close()
    return stats


def get_filtered_publications(severity=None, domain=None, module=None,
                               source=None, impact_only=True, page=1,
                               per_page=25, sort_by="analyzed_at",
                               sort_dir="DESC"):
    """Obtiene publicaciones filtradas, paginadas y ordenadas."""
    conn = get_connection()
    cursor = conn.cursor()

    conditions = []
    params = []

    if impact_only:
        conditions.append("impact_flag = 1")

    if severity:
        conditions.append("severity = ?")
        params.append(severity)

    if domain:
        conditions.append("primary_domain = ?")
        params.append(domain)

    if module:
        conditions.append("impacted_module = ?")
        params.append(module)

    if source:
        conditions.append("COALESCE(source, 'DOF') = ?")
        params.append(source)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    # Whitelist de columnas para evitar SQL injection
    allowed_sorts = {
        "analyzed_at", "publication_date", "severity",
        "primary_domain", "impacted_module", "title"
    }
    if sort_by not in allowed_sorts:
        sort_by = "analyzed_at"
    sort_dir = "DESC" if sort_dir.upper() == "DESC" else "ASC"

    # Contar total
    cursor.execute(f"SELECT COUNT(*) FROM publications {where}", params)
    total = cursor.fetchone()[0]

    # Resultados paginados
    offset = (page - 1) * per_page
    cursor.execute(f"""
        SELECT id, title, url, publication_date, primary_domain,
               impacted_module, severity, impact_flag, impact_reason,
               analyzed_at, COALESCE(source, 'DOF') as source
        FROM publications
        {where}
        ORDER BY {sort_by} {sort_dir}
        LIMIT ? OFFSET ?
    """, params + [per_page, offset])

    publications = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return publications, total


def get_publication_by_id(pub_id):
    """Obtiene una publicacion con todos sus campos."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT *, COALESCE(source, 'DOF') as source FROM publications WHERE id = ?", (pub_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def get_pipeline_counts():
    """Obtiene contadores por status para la pagina de pipeline."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT status, COUNT(*) as cnt FROM publications GROUP BY status")
    counts = {row["status"]: row["cnt"] for row in cursor.fetchall()}

    cursor.execute("SELECT COUNT(*) FROM publications")
    counts["TOTAL"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM publications WHERE impact_flag = 1")
    counts["WITH_IMPACT"] = cursor.fetchone()[0]

    conn.close()
    return counts
