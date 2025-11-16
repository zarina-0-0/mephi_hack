# В createbd.py
def create_tables(cur):
    # Таблица НКО
    cur.execute('''
        CREATE TABLE IF NOT EXISTS nko_info (
            nko_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Таблица постов
    cur.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            post_id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_type TEXT NOT NULL, -- 'example', 'generated', 'edited', 'ai_refined'
            nko_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            goal TEXT,
            audience TEXT,
            tone TEXT,
            details TEXT,
            cta TEXT,
            nuances TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (nko_id) REFERENCES nko_info (nko_id)
        )
    ''')