import sqlite3

db = sqlite3.connect('sha-cache.db')
cursor = db.cursor()

def setup_sqlite():
    # set up migrations
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sha_cache (
        sha256 TEXT NOT NULL,
        oshash TEXT NOT NULL
    );""")
    cursor.execute("CREATE INDEX IF NOT EXISTS oshash_index ON sha_cache (oshash);")
    db.commit()

def add_sha256(sha256, oshash):
    cursor.execute("INSERT INTO sha_cache VALUES (?, ?)", (sha256, oshash))
    db.commit()

def lookup_sha(oshash):
    cursor.execute("SELECT sha256 FROM sha_cache WHERE oshash = ?", [oshash])
    return cursor.fetchone()

def get_rows():
    cursor.execute("SELECT sha256, oshash FROM sha_cache")
    return cursor.fetchall()