"""
Modulo de configuracion de alertas.

Permite configurar:
- Destinatarios (usuarios que reciben alertas)
- Horario de envio (dia de la semana + hora)

Usa tabla alert_config (key-value) para persistencia.
"""

import json
import logging

from database.connection import get_connection, adapt_sql, is_postgres

logger = logging.getLogger(__name__)


def ensure_alert_config_table():
    """Crea la tabla alert_config si no existe."""
    conn = get_connection()
    cursor = conn.cursor()
    if is_postgres():
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
    conn.commit()
    conn.close()


def get_alert_config():
    """Obtiene la configuracion de alertas como dict.

    Returns:
        dict con keys: recipients (list), schedule_day (str), schedule_hour (str)
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM alert_config")
    rows = cursor.fetchall()
    conn.close()

    config = {}
    for row in rows:
        row = dict(row)
        config[row["key"]] = row["value"]

    # Parsear recipients como JSON list
    recipients_raw = config.get("recipients", "[]")
    try:
        recipients = json.loads(recipients_raw)
    except (json.JSONDecodeError, TypeError):
        recipients = []

    return {
        "recipients": recipients,
        "schedule_day": config.get("schedule_day", "monday"),
        "schedule_hour": config.get("schedule_hour", "9"),
    }


def save_alert_config(recipients, schedule_day, schedule_hour):
    """Guarda la configuracion de alertas.

    Args:
        recipients: lista de emails de destinatarios
        schedule_day: dia de la semana (monday, tuesday, etc.)
        schedule_hour: hora del dia (0-23)
    """
    conn = get_connection()
    cursor = conn.cursor()

    items = [
        ("recipients", json.dumps(recipients)),
        ("schedule_day", schedule_day),
        ("schedule_hour", str(schedule_hour)),
    ]

    for key, value in items:
        if is_postgres():
            cursor.execute(
                "INSERT INTO alert_config (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (key, value),
            )
        else:
            cursor.execute(
                "INSERT OR REPLACE INTO alert_config (key, value) VALUES (?, ?)",
                (key, value),
            )

    conn.commit()
    conn.close()
    logger.info("Configuracion de alertas guardada: %d destinatarios, %s %s:00",
                len(recipients), schedule_day, schedule_hour)
