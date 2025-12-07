import sqlite3

DB_PATH = "database/shop.db"


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            description TEXT,
            price       REAL NOT NULL,
            image_path  TEXT
        )
        """)
        conn.commit()


def add_product(name: str, description: str, price: float, image_path: str | None):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO products (name, description, price, image_path) VALUES (?, ?, ?, ?)",
            (name, description, price, image_path),
        )
        conn.commit()
        return cur.lastrowid


def get_all_products():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT id, name, description, price, image_path FROM products ORDER BY id")
        return cur.fetchall()


def delete_product(product_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        conn.commit()
