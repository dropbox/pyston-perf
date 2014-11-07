import sqlite3

conn = sqlite3.connect("data.db")
conn.cursor().execute("""CREATE TABLE IF NOT EXISTS results
        (report text, benchmark text, time real)
        """)

def save_result(report, benchmark, value):
    conn.cursor().execute("""INSERT INTO results (report, benchmark, time)
            VALUES (?, ?, ?)""", (report, benchmark, value))
    conn.commit()

def get_result(report, benchmark):
    val = conn.cursor().execute("""SELECT time FROM results WHERE
            report=? AND benchmark=?""", (report, benchmark)).fetchone()
    if val is not None:
        return val[0]
    return val
