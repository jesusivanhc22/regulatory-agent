"""
Script de migracion one-time: SQLite -> PostgreSQL.

Uso:
    DATABASE_URL=postgres://... python migrate_to_pg.py

Lee datos de data/regulatory_deploy.db (SQLite) y los inserta en PostgreSQL.
Crea el schema y el usuario admin inicial.
"""

import os
import sys
import sqlite3
from pathlib import Path

# Verificar DATABASE_URL
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_URL:
    print("ERROR: DATABASE_URL no configurado.")
    print("Uso: DATABASE_URL=postgres://user:pass@host:5432/dbname python migrate_to_pg.py")
    sys.exit(1)

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("ERROR: psycopg2 no instalado. pip install psycopg2-binary")
    sys.exit(1)

from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
SQLITE_DB = BASE_DIR / "data" / "regulatory_deploy.db"

if not SQLITE_DB.exists():
    SQLITE_DB = BASE_DIR / "data" / "regulatory.db"
    if not SQLITE_DB.exists():
        print(f"ERROR: No se encontro base de datos SQLite en data/")
        sys.exit(1)

print(f"Fuente SQLite: {SQLITE_DB}")
print(f"Destino PG: {DATABASE_URL[:50]}...")


def migrate():
    # Conectar a SQLite
    src = sqlite3.connect(SQLITE_DB)
    src.row_factory = sqlite3.Row

    # Conectar a PostgreSQL
    dst = psycopg2.connect(DATABASE_URL)
    dst_cursor = dst.cursor()

    # 1. Crear schema
    print("\n[1/4] Creando schema PostgreSQL...")
    schema_path = BASE_DIR / "database" / "schema_pg.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")
    dst_cursor.execute(schema_sql)
    dst.commit()
    print("  Schema creado.")

    # 2. Migrar publicaciones
    print("\n[2/4] Migrando publicaciones...")
    src_cursor = src.execute("SELECT * FROM publications")
    cols = [d[0] for d in src_cursor.description]

    # Filtrar columna 'id' para que PG use SERIAL
    cols_no_id = [c for c in cols if c != "id"]
    placeholders = ", ".join(["%s"] * len(cols_no_id))
    col_names = ", ".join(cols_no_id)

    insert_sql = (
        f"INSERT INTO publications ({col_names}) VALUES ({placeholders}) "
        f"ON CONFLICT (url) DO NOTHING"
    )

    count = 0
    for row in src_cursor:
        values = []
        for col in cols_no_id:
            v = row[col]
            # Truncar raw_html para ahorrar espacio
            if col == "raw_html":
                v = None
            elif col == "full_text" and v and len(v) > 50000:
                v = v[:50000] + "... [truncado]"
            values.append(v)

        try:
            dst_cursor.execute(insert_sql, values)
            count += 1
        except Exception as e:
            print(f"  Error en row: {e}")
            dst.rollback()
            dst_cursor = dst.cursor()
            continue

    dst.commit()
    print(f"  {count} publicaciones migradas.")

    # 3. Crear admin inicial
    print("\n[3/4] Creando usuario admin...")
    admin_email = os.environ.get("ADMIN_EMAIL", "").strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "").strip()

    if admin_email and admin_password:
        password_hash = generate_password_hash(admin_password)
        try:
            dst_cursor.execute(
                "INSERT INTO users (email, password_hash, role, name) "
                "VALUES (%s, %s, %s, %s) ON CONFLICT (email) DO NOTHING",
                (admin_email.lower(), password_hash, "admin", "Administrador"),
            )
            dst.commit()
            print(f"  Admin creado: {admin_email}")
        except Exception as e:
            print(f"  Error creando admin: {e}")
            dst.rollback()
    else:
        print("  ADMIN_EMAIL/ADMIN_PASSWORD no configurados. Sin admin inicial.")

    # 4. Verificar
    print("\n[4/4] Verificando...")
    dst_cursor.execute("SELECT COUNT(*) FROM publications")
    pub_count = dst_cursor.fetchone()[0]
    dst_cursor.execute("SELECT COUNT(*) FROM publications WHERE impact_flag = 1")
    impact_count = dst_cursor.fetchone()[0]
    dst_cursor.execute("SELECT COUNT(*) FROM users")
    user_count = dst_cursor.fetchone()[0]

    print(f"  Publicaciones: {pub_count}")
    print(f"  Con impacto: {impact_count}")
    print(f"  Usuarios: {user_count}")

    src.close()
    dst.close()

    print("\nMigracion completada exitosamente.")


if __name__ == "__main__":
    migrate()
