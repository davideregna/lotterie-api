import sqlite3
from contextlib import contextmanager
from app.config import DB_PATH


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def get_db_ctx():
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_db_ctx() as conn:
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS millionday (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                ora TEXT NOT NULL,
                n1 INTEGER NOT NULL, n2 INTEGER NOT NULL, n3 INTEGER NOT NULL,
                n4 INTEGER NOT NULL, n5 INTEGER NOT NULL,
                e1 INTEGER DEFAULT 0, e2 INTEGER DEFAULT 0, e3 INTEGER DEFAULT 0,
                e4 INTEGER DEFAULT 0, e5 INTEGER DEFAULT 0,
                UNIQUE(data, ora)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS superenalotto (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                concorso INTEGER,
                data TEXT NOT NULL,
                n1 INTEGER NOT NULL, n2 INTEGER NOT NULL, n3 INTEGER NOT NULL,
                n4 INTEGER NOT NULL, n5 INTEGER NOT NULL, n6 INTEGER NOT NULL,
                jolly INTEGER DEFAULT 0,
                superstar INTEGER DEFAULT 0,
                UNIQUE(data)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS lotto (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                ruota TEXT NOT NULL,
                n1 INTEGER NOT NULL, n2 INTEGER NOT NULL, n3 INTEGER NOT NULL,
                n4 INTEGER NOT NULL, n5 INTEGER NOT NULL,
                UNIQUE(data, ruota)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS diecelotto (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                n1 INTEGER, n2 INTEGER, n3 INTEGER, n4 INTEGER, n5 INTEGER,
                n6 INTEGER, n7 INTEGER, n8 INTEGER, n9 INTEGER, n10 INTEGER,
                n11 INTEGER, n12 INTEGER, n13 INTEGER, n14 INTEGER, n15 INTEGER,
                n16 INTEGER, n17 INTEGER, n18 INTEGER, n19 INTEGER, n20 INTEGER,
                numero_oro INTEGER DEFAULT 0,
                doppio_oro INTEGER DEFAULT 0,
                UNIQUE(data)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS vincicasa (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                concorso INTEGER DEFAULT 0,
                data TEXT NOT NULL,
                n1 INTEGER NOT NULL, n2 INTEGER NOT NULL, n3 INTEGER NOT NULL,
                n4 INTEGER NOT NULL, n5 INTEGER NOT NULL,
                UNIQUE(data)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS eurojackpot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                concorso INTEGER DEFAULT 0,
                data TEXT NOT NULL,
                n1 INTEGER NOT NULL, n2 INTEGER NOT NULL, n3 INTEGER NOT NULL,
                n4 INTEGER NOT NULL, n5 INTEGER NOT NULL,
                e1 INTEGER NOT NULL, e2 INTEGER NOT NULL,
                UNIQUE(data)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS sivincetutto (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                concorso INTEGER DEFAULT 0,
                data TEXT NOT NULL,
                n1 INTEGER NOT NULL, n2 INTEGER NOT NULL, n3 INTEGER NOT NULL,
                n4 INTEGER NOT NULL, n5 INTEGER NOT NULL, n6 INTEGER NOT NULL,
                UNIQUE(data)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS winforlife (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                concorso INTEGER DEFAULT 0,
                data TEXT NOT NULL,
                ora TEXT NOT NULL DEFAULT '',
                n1 INTEGER NOT NULL, n2 INTEGER NOT NULL, n3 INTEGER NOT NULL,
                n4 INTEGER NOT NULL, n5 INTEGER NOT NULL, n6 INTEGER NOT NULL,
                n7 INTEGER NOT NULL, n8 INTEGER NOT NULL, n9 INTEGER NOT NULL,
                n10 INTEGER NOT NULL,
                numerone INTEGER DEFAULT 0,
                UNIQUE(data, tipo, ora)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS simbolotto (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                concorso INTEGER DEFAULT 0,
                data TEXT NOT NULL,
                ruota TEXT NOT NULL DEFAULT '',
                n1 INTEGER NOT NULL, n2 INTEGER NOT NULL, n3 INTEGER NOT NULL,
                n4 INTEGER NOT NULL, n5 INTEGER NOT NULL,
                UNIQUE(data)
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS statistiche (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lotteria TEXT NOT NULL,
                numero INTEGER NOT NULL,
                frequenza INTEGER DEFAULT 0,
                ritardo_attuale INTEGER DEFAULT 0,
                ritardo_max INTEGER DEFAULT 0,
                ultima_data TEXT,
                aggiornato_il TEXT,
                UNIQUE(lotteria, numero)
            )
        """)

        # ── Dati live (JSON completo per /ultima) ──

        c.execute("""
            CREATE TABLE IF NOT EXISTS live_data (
                gioco TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                raw_json TEXT NOT NULL,
                aggiornato_il TEXT NOT NULL
            )
        """)

        c.execute("CREATE INDEX IF NOT EXISTS idx_md_data ON millionday(data DESC, ora DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_se_data ON superenalotto(data DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_lo_data ON lotto(data DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_dl_data ON diecelotto(data DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_vc_data ON vincicasa(data DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ej_data ON eurojackpot(data DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_svt_data ON sivincetutto(data DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_wfl_data ON winforlife(data DESC, tipo)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_simb_data ON simbolotto(data DESC)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_stats ON statistiche(lotteria, numero)")

        conn.commit()
    print("Database inizializzato.")


if __name__ == "__main__":
    init_db()