import sqlite3

conn = sqlite3.connect("data.db")
conn.cursor().execute("""CREATE TABLE IF NOT EXISTS results
        (run text, executable text, benchmark text, time real)
        """)
