"""
Capa de abstraccion para conexion a base de datos.

Detecta DATABASE_URL para usar PostgreSQL, o cae a SQLite como fallback.
Provee helpers para manejar diferencias de dialecto SQL.
"""

import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# SQLite paths (fallback para desarrollo local)
BASE_DIR = Path(__file__).resolve().parent.parent
_db_name = os.environ.get("DB_NAME", "regulatory.db")
_db_path = BASE_DIR / "data" / _db_name
if not _db_path.exists() and _db_name == "regulatory.db":
    _db_path = BASE_DIR / "data" / "regulatory_deploy.db"
SQLITE_PATH = _db_path


def is_postgres():
    """Retorna True si estamos usando PostgreSQL."""
    return bool(DATABASE_URL)


def placeholder():
    """Retorna el placeholder de parametros segun el backend."""
    return "%s" if is_postgres() else "?"


def adapt_sql(sql):
    """Adapta SQL de sintaxis SQLite a PostgreSQL si es necesario.

    Reemplaza ? por %s para parametros posicionales.
    """
    if is_postgres():
        return sql.replace("?", "%s")
    return sql


def get_connection():
    """Retorna una conexion a la base de datos con row factory habilitado.

    PostgreSQL: usa psycopg2 con RealDictCursor
    SQLite: usa sqlite3 con Row factory
    """
    if is_postgres():
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        return conn
    else:
        os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
        conn = sqlite3.connect(SQLITE_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn


@contextmanager
def transaction():
    """Context manager con commit/rollback automatico.

    Uso:
        with transaction() as conn:
            conn.execute(adapt_sql("INSERT INTO ..."), params)
    """
    conn = get_connection()
    try:
        if is_postgres():
            conn.autocommit = False
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute(conn, sql, params=None):
    """Ejecuta SQL adaptando placeholders automaticamente.

    Args:
        conn: conexion activa
        sql: SQL con placeholders ? (se adaptan a %s para PG)
        params: tuple o list de parametros

    Returns:
        cursor con resultados
    """
    cursor = conn.cursor()
    adapted = adapt_sql(sql)
    if params:
        cursor.execute(adapted, params)
    else:
        cursor.execute(adapted)
    return cursor


def executemany(conn, sql, params_list):
    """Ejecuta SQL en batch adaptando placeholders.

    Args:
        conn: conexion activa
        sql: SQL con placeholders ?
        params_list: lista de tuples de parametros

    Returns:
        cursor
    """
    cursor = conn.cursor()
    adapted = adapt_sql(sql)
    if is_postgres():
        # psycopg2 executemany
        cursor.executemany(adapted, params_list)
    else:
        cursor.executemany(adapted, params_list)
    return cursor


def insert_ignore(conn, sql_sqlite, sql_postgres=None):
    """Ejecuta INSERT ignorando duplicados.

    Args:
        conn: conexion activa
        sql_sqlite: SQL con INSERT OR IGNORE ... VALUES (?, ...)
        sql_postgres: SQL alternativo con ON CONFLICT DO NOTHING.
                      Si no se provee, se genera automaticamente.
    """
    if is_postgres():
        if sql_postgres:
            return conn.cursor().execute(sql_postgres)
        # Auto-convertir INSERT OR IGNORE a INSERT ... ON CONFLICT DO NOTHING
        adapted = sql_sqlite.replace("INSERT OR IGNORE", "INSERT")
        adapted = adapt_sql(adapted)
        # Agregar ON CONFLICT DO NOTHING antes del ultimo )
        # Buscar el cierre del VALUES(...)
        if "ON CONFLICT" not in adapted.upper():
            adapted = adapted.rstrip().rstrip(";")
            adapted += " ON CONFLICT DO NOTHING"
        return conn.cursor().execute(adapted)
    else:
        return conn.cursor().execute(sql_sqlite)


def fetchone_value(conn, sql, params=None):
    """Ejecuta query y retorna el primer valor escalar."""
    cursor = execute(conn, sql, params)
    row = cursor.fetchone()
    if row is None:
        return None
    if is_postgres():
        # RealDictCursor retorna dict
        return list(row.values())[0] if isinstance(row, dict) else row[0]
    else:
        return row[0]


def fetchall_dicts(conn, sql, params=None):
    """Ejecuta query y retorna lista de dicts."""
    cursor = execute(conn, sql, params)
    rows = cursor.fetchall()
    if is_postgres():
        # RealDictCursor ya retorna dicts
        return [dict(row) for row in rows]
    else:
        return [dict(row) for row in rows]


def init_schema():
    """Inicializa el schema de la base de datos.

    Para PostgreSQL: ejecuta schema_pg.sql
    Para SQLite: crea tabla basica con migraciones
    """
    if is_postgres():
        schema_path = Path(__file__).parent / "schema_pg.sql"
        schema_sql = schema_path.read_text(encoding="utf-8")
        with transaction() as conn:
            conn.cursor().execute(schema_sql)
        logger.info("Schema PostgreSQL inicializado.")
    else:
        with transaction() as conn:
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
        logger.info("Schema SQLite inicializado.")
