import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "regulatory.db"
SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"

print("Creando DB en:", DB_PATH)
print("Leyendo schema desde:", SCHEMA_PATH)

with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
    sql_script = f.read()

print("Longitud del schema:", len(sql_script))
print("Primeros 200 caracteres:")
print(sql_script[:200])

conn = sqlite3.connect(DB_PATH)
conn.executescript(sql_script)
conn.commit()
conn.close()

print("Base de datos inicializada correctamente.")