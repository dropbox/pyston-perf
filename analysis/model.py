import os.path
import sqlite3

conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db"))
conn.cursor().execute("""CREATE TABLE IF NOT EXISTS runs
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
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

def get_runs(revision, benchmark=None):
    assert len(revision) == 40, repr(revision)
    cursor = conn.cursor()
    if benchmark:
        cursor.execute("""SELECT id, benchmark FROM runs WHERE revision=? AND benchmark=?""",
                (revision, benchmark))
    else:
        cursor.execute("""SELECT id, benchmark FROM runs WHERE revision=?""",
                (revision,))
    return [Run(*r) for r in cursor.fetchall()]

def delete_run(run_id):
    conn.cursor().execute("""DELETE FROM metadata WHERE run_id=?""", (run_id,))
    conn.cursor().execute("""DELETE FROM runs WHERE id=?""", (run_id,))
    conn.commit()

class Metadata(object):
    __CONVERSIONS = {
        "exitcode": int,
        "elapsed": float,
    }

    def __init__(self, run_id):
        self.__run_id = run_id

    def __getattr__(self, attr):
        v = get_metadata(self.__run_id, attr)
        if v is None:
            raise AttributeError(attr)
        # TODO: cache it?
        if attr in self.__CONVERSIONS:
            return self.__CONVERSIONS[attr](v)
        return v

class Run(object):
    def __init__(self, id, benchmark):
        self.id = id
        self.benchmark = benchmark
        self.md = Metadata(id)

    def format(self):
        if self.md.exitcode:
            return "\033[31m% 3d\033[0m" % self.id
        else:
            return "% 3d (%.1fs)" % (self.id, self.md.elapsed)
