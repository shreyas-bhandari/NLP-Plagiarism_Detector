import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'db', 'veritext.db')


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id TEXT UNIQUE NOT NULL,
            filename_a TEXT,
            filename_b TEXT,
            similarity_score REAL,
            label TEXT,
            created_at TEXT,
            result_json TEXT
        )
    ''')
    conn.commit()
    conn.close()


def insert_analysis(analysis_id, filename_a, filename_b, similarity_score, label, result_json):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        'INSERT INTO analyses (analysis_id, filename_a, filename_b, similarity_score, label, created_at, result_json) '
        'VALUES (?, ?, ?, ?, ?, ?, ?)',
        (analysis_id, filename_a, filename_b, similarity_score, label,
         datetime.utcnow().isoformat(), result_json),
    )
    conn.commit()
    rowid = c.lastrowid
    conn.close()
    return rowid


def get_analysis(analysis_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT * FROM analyses WHERE analysis_id = ?', (analysis_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def list_analyses(limit=20):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        'SELECT analysis_id, filename_a, filename_b, similarity_score, label, created_at '
        'FROM analyses ORDER BY id DESC LIMIT ?',
        (limit,),
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows
