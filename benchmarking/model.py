import os.path
import sqlite3

conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db"))
conn.cursor().execute("""CREATE TABLE IF NOT EXISTS results
        (report text, benchmark text, time real)
        """)

def clear_report(report):
    print "Deleting report '%s'" % (report,)
    conn.cursor().execute("""DELETE FROM results WHERE report=?""", (report,))
    conn.commit()

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

def list_reports():
    rows = conn.cursor().execute("""SELECT distinct(report) FROM results""").fetchall()
    return [r[0] for r in rows]
