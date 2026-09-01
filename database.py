import sqlite3
import time
from pathlib import Path
from config import DB_PATH


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            address TEXT DEFAULT '',
            upi_id TEXT DEFAULT '',
            wallet INTEGER DEFAULT 0,
            created_at REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            price INTEGER DEFAULT 0,
            stock INTEGER DEFAULT 0,
            image_url TEXT DEFAULT '',
            category TEXT DEFAULT '',
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            qty INTEGER DEFAULT 1,
            created_at REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            items TEXT DEFAULT '',
            total INTEGER DEFAULT 0,
            fee INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            address TEXT DEFAULT '',
            created_at REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS wallet_tx (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER DEFAULT 0,
            type TEXT DEFAULT 'credit',
            status TEXT DEFAULT 'pending',
            txn_id TEXT DEFAULT '',
            created_at REAL DEFAULT 0
        );
    """)
    conn.commit()
    conn.close()


# ─── USER ───

def get_user(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_user(user_id, name=""):
    conn = get_db()
    conn.execute("INSERT OR IGNORE INTO users (user_id, name, created_at) VALUES (?, ?, ?)",
                 (user_id, name, time.time()))
    conn.commit()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_user(user_id, **kwargs):
    conn = get_db()
    for k, v in kwargs.items():
        conn.execute(f"UPDATE users SET {k}=? WHERE user_id=?", (v, user_id))
    conn.commit()
    conn.close()


def delete_user(user_id):
    conn = get_db()
    conn.execute("DELETE FROM users WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM orders WHERE user_id=?", (user_id,))
    conn.execute("DELETE FROM wallet_tx WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def add_wallet(user_id, amount):
    conn = get_db()
    conn.execute("UPDATE users SET wallet=wallet+? WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()


def deduct_wallet(user_id, amount):
    conn = get_db()
    conn.execute("UPDATE users SET wallet=wallet-? WHERE user_id=? AND wallet>=?",
                 (amount, user_id, amount))
    conn.commit()
    conn.close()


# ─── PRODUCTS ───

def get_products(category=None, search=None):
    conn = get_db()
    q = "SELECT * FROM products WHERE active=1"
    params = []
    if category:
        q += " AND category=?"
        params.append(category)
    if search:
        q += " AND (name LIKE ? OR description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_product(pid):
    conn = get_db()
    row = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_product(name, price, stock, desc="", category="", image=""):
    conn = get_db()
    conn.execute(
        "INSERT INTO products (name, price, stock, description, category, image_url) VALUES (?,?,?,?,?,?)",
        (name, price, stock, desc, category, image))
    conn.commit()
    pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return pid


def update_stock(pid, qty):
    conn = get_db()
    conn.execute("UPDATE products SET stock=stock-? WHERE id=? AND stock>=?", (qty, pid, qty))
    conn.commit()
    conn.close()


# ─── CART ───

def get_cart(user_id):
    conn = get_db()
    rows = conn.execute(
        """SELECT c.*, p.name, p.price, p.image_url
           FROM cart c JOIN products p ON c.product_id=p.id
           WHERE c.user_id=?""", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_to_cart(user_id, product_id, qty=1):
    conn = get_db()
    existing = conn.execute(
        "SELECT id, qty FROM cart WHERE user_id=? AND product_id=?",
        (user_id, product_id)).fetchone()
    if existing:
        conn.execute("UPDATE cart SET qty=qty+? WHERE id=?", (qty, existing["id"]))
    else:
        conn.execute("INSERT INTO cart (user_id, product_id, qty, created_at) VALUES (?,?,?,?)",
                     (user_id, product_id, qty, time.time()))
    conn.commit()
    conn.close()


def update_cart_qty(cart_id, qty):
    conn = get_db()
    if qty <= 0:
        conn.execute("DELETE FROM cart WHERE id=?", (cart_id,))
    else:
        conn.execute("UPDATE cart SET qty=? WHERE id=?", (qty, cart_id))
    conn.commit()
    conn.close()


def clear_cart(user_id):
    conn = get_db()
    conn.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


# ─── ORDERS ───

def create_order(user_id, items, total, fee, address=""):
    conn = get_db()
    conn.execute(
        "INSERT INTO orders (user_id, items, total, fee, status, address, created_at) VALUES (?,?,?,?,?,?,?)",
        (user_id, items, total, fee, "pending", address, time.time()))
    conn.commit()
    oid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return oid


def get_orders(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_order(oid):
    conn = get_db()
    row = conn.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_order_status(oid, status):
    conn = get_db()
    conn.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
    conn.commit()
    conn.close()


def get_all_orders():
    conn = get_db()
    rows = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── WALLET TX ───

def create_wallet_tx(user_id, amount, txn_id=""):
    conn = get_db()
    conn.execute(
        "INSERT INTO wallet_tx (user_id, amount, type, status, txn_id, created_at) VALUES (?,?,?,?,?,?)",
        (user_id, amount, "credit", "pending", txn_id, time.time()))
    conn.commit()
    txid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return txid


def verify_wallet_tx(txid):
    conn = get_db()
    row = conn.execute("SELECT * FROM wallet_tx WHERE id=?", (txid,)).fetchone()
    if row:
        conn.execute("UPDATE wallet_tx SET status='completed' WHERE id=?", (txid,))
        conn.execute("UPDATE users SET wallet=wallet+? WHERE user_id=?", (row["amount"], row["user_id"]))
        conn.commit()
        conn.close()
        return dict(row)
    conn.close()
    return None


def get_pending_tx():
    conn = get_db()
    rows = conn.execute("SELECT * FROM wallet_tx WHERE status='pending'").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_wallet_tx(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM wallet_tx WHERE user_id=? ORDER BY created_at DESC LIMIT 20",
        (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


init_db()
