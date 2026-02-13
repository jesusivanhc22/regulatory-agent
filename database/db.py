import sqlite3

DB_PATH = "data/regulatory.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
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

    conn.commit()
    conn.close()


def url_exists(url):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM publications WHERE url = ?", (url,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def save_discovered(title, url):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO publications (title, url, status)
        VALUES (?, ?, 'DISCOVERED')
    """, (title, url))

    conn.commit()
    conn.close()


def get_discovered(limit=100):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, url
        FROM publications
        WHERE status = 'DISCOVERED'
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    conn.close()
    return rows


def mark_as_analyzed(pub_id, category, priority, score):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE publications
        SET status = 'ANALYZED',
            category = ?,
            priority = ?,
            score = ?,
            analyzed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (category, priority, score, pub_id))

    conn.commit()
    conn.close()
