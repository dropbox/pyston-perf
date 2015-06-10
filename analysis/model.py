import os.path
import sqlite3

conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db"))
conn.cursor().execute("""CREATE TABLE IF NOT EXISTS runs
        (id INTEGER PRIMARY KEY,
         revision TEXT,
         benchmark TEXT,
         date TIMESTAMP)
        """)
conn.cursor().execute("""CREATE TABLE IF NOT EXISTS metadata
        (run_id INTEGER,
        type TEXT,
        value TEXT,
        PRIMARY KEY (run_id, type),
        FOREIGN KEY (run_id) REFERENCES runs(id)
        )""")

def add_run(revision, benchmark):
    assert len(revision) == 40
    cursor = conn.cursor()
    cursor.execute("""INSERT INTO runs(revision, benchmark, date)
            VALUES (?, ?, CURRENT_TIMESTAMP)""", (revision, benchmark))
    id = cursor.lastrowid
    conn.commit()
    return id

def add_metadata(run_id, md_name, md_value):
    conn.cursor().execute("""INSERT INTO metadata(run_id, type, value)
            VALUES (?, ?, ?)""", (run_id, md_name, md_value))
    conn.commit()

def set_metadata(run_id, md_name, md_value):
    conn.cursor().execute("""INSERT OR REPLACE INTO metadata(run_id, type, value)
            VALUES (?, ?, ?)""", (run_id, md_name, md_value))
    conn.commit()

def get_metadata(run_id, md_name):
    cursor = conn.cursor()
    cursor.execute("""SELECT value FROM metadata WHERE run_id=? AND type=?""",
            (run_id, md_name))
    r = cursor.fetchall()
    assert len(r) in (0, 1)
    if not r:
        return None
    return r[0][0]

def get_runs(revision, benchmark):
    assert len(revision) == 40
    cursor = conn.cursor()
    cursor.execute("""SELECT id FROM runs WHERE revision=? AND benchmark=?""",
            (revision, benchmark))
    return [r[0] for r in cursor.fetchall()]

def delete_run(run_id):
    conn.cursor().execute("""DELETE FROM metadata WHERE run_id=?""", (run_id,))
    conn.cursor().execute("""DELETE FROM runs WHERE id=?""", (run_id,))
    conn.commit()
