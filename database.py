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
            mode TEXT DEFAULT 'paid',
            referral_link TEXT DEFAULT '',
            cart_session TEXT DEFAULT '',
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
            name TEXT DEFAULT '',
            price INTEGER DEFAULT 0,
            image TEXT DEFAULT '',
            source TEXT DEFAULT 'local',
            qty INTEGER DEFAULT 1,
            supplier_id INTEGER DEFAULT 0,
            variation_id INTEGER DEFAULT 0,
            variation_name TEXT DEFAULT '',
            mrp INTEGER DEFAULT 0,
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
            meesho_order_num TEXT DEFAULT '',
            payment_method TEXT DEFAULT 'COD',
            meesho_amount INTEGER DEFAULT 0,
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

        CREATE TABLE IF NOT EXISTS meesho_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            phone TEXT DEFAULT '',
            meesho_user_id TEXT DEFAULT '',
            xo TEXT DEFAULT '',
            xo_exp REAL DEFAULT 0,
            instance_id TEXT DEFAULT '',
            is_first_order INTEGER DEFAULT 1,
            app_session_id TEXT DEFAULT '',
            shield_session_id TEXT DEFAULT '',
            gaid TEXT DEFAULT '',
            created_at REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS user_offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            offer_json TEXT DEFAULT '',
            created_at REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            meesho_account_id INTEGER DEFAULT 0,
            name TEXT DEFAULT '',
            mobile TEXT DEFAULT '',
            pin TEXT DEFAULT '',
            city TEXT DEFAULT '',
            state TEXT DEFAULT '',
            address_line_1 TEXT DEFAULT '',
            address_line_2 TEXT DEFAULT '',
            landmark TEXT DEFAULT '',
            address_type TEXT DEFAULT 'Home',
            latitude TEXT DEFAULT '',
            longitude TEXT DEFAULT '',
            is_default INTEGER DEFAULT 0,
            created_at REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
        );
    """)
    conn.commit()
    # Migrations for existing databases
    try:
        conn.execute("ALTER TABLE users ADD COLUMN mode TEXT DEFAULT 'paid'")
    except Exception:
        pass
    try:
        conn.execute("ALTER TABLE meesho_accounts ADD COLUMN instance_id TEXT DEFAULT ''")
    except Exception:
        pass
    for col, tbl, default in [
        ("supplier_id", "cart", "0"), ("variation_id", "cart", "0"),
        ("variation_name", "cart", "''"), ("mrp", "cart", "0"),
        ("meesho_order_num", "orders", "''"), ("payment_method", "orders", "'COD'"),
        ("meesho_amount", "orders", "0"),
        ("cart_session", "users", "''"),
        ("meesho_address_id", "addresses", "0"),
        ("app_session_id", "meesho_accounts", "''"),
        ("shield_session_id", "meesho_accounts", "''"),
        ("gaid", "meesho_accounts", "''"),
    ]:
        try:
            conn.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {default}")
        except Exception:
            pass
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


def get_all_users():
    conn = get_db()
    rows = conn.execute("SELECT user_id, name, phone, wallet, mode, created_at FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def toggle_user_mode(user_id):
    current = get_global_mode()
    new_mode = "free" if current == "paid" else "paid"
    set_global_mode(new_mode)
    return new_mode


def get_user_mode(user_id):
    return get_global_mode()


def get_global_mode():
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key='global_mode'").fetchone()
    conn.close()
    return dict(row)["value"] if row else "paid"


def set_global_mode(mode):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('global_mode', ?)", (mode,))
    conn.commit()
    conn.close()


def get_order_count(user_id):
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) as cnt FROM orders WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row)["cnt"] if row else 0


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
        "SELECT * FROM cart WHERE user_id=?", (user_id,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        if not d.get("name"):
            p = get_product(d.get("product_id"))
            if p:
                d["name"] = p.get("name", "")
                d["price"] = p.get("price", 0)
                d["image"] = p.get("image_url", "")
        result.append(d)
    conn.close()
    return result


def add_to_cart(user_id, product_id, qty=1, name="", price=0, image="",
                source="local", supplier_id=0, variation_id=0, variation_name="", mrp=0):
    conn = get_db()
    existing = conn.execute(
        "SELECT id, qty FROM cart WHERE user_id=? AND product_id=?",
        (user_id, product_id)).fetchone()
    if existing:
        conn.execute("UPDATE cart SET qty=qty+? WHERE id=?", (qty, existing["id"]))
    else:
        conn.execute(
            """INSERT INTO cart (user_id, product_id, name, price, image, source, qty,
               supplier_id, variation_id, variation_name, mrp, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (user_id, product_id, name, price, image, source, qty,
             supplier_id, variation_id, variation_name, mrp, time.time()))
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

def create_order(user_id, items, total, fee, address="", meesho_order_num="",
                 payment_method="COD", meesho_amount=0):
    conn = get_db()
    conn.execute(
        """INSERT INTO orders (user_id, items, total, fee, status, address,
           meesho_order_num, payment_method, meesho_amount, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (user_id, items, total, fee, "pending", address,
         meesho_order_num, payment_method, meesho_amount, time.time()))
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


# ─── MEESHO ACCOUNTS ───

def save_meesho_account(user_id, phone, meesho_user_id, xo, xo_exp=0, instance_id="", is_first_order=1,
                        app_session_id="", shield_session_id="", gaid=""):
    conn = get_db()
    conn.execute(
        """INSERT INTO meesho_accounts (user_id, phone, meesho_user_id, xo, xo_exp, instance_id,
           is_first_order, app_session_id, shield_session_id, gaid, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (user_id, phone, str(meesho_user_id), xo, xo_exp, instance_id, int(is_first_order),
         app_session_id, shield_session_id, gaid, time.time()))
    conn.commit()
    conn.close()


def get_meesho_accounts(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM meesho_accounts WHERE user_id=? ORDER BY created_at DESC", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_active_meesho_account(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM meesho_accounts WHERE user_id=? ORDER BY created_at DESC LIMIT 1",
        (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_meesho_account(user_id, acc_id):
    conn = get_db()
    conn.execute("DELETE FROM meesho_accounts WHERE user_id=? AND id=?", (user_id, acc_id))
    conn.commit()
    conn.close()


def update_meesho_xo(acc_id, xo, xo_exp=0):
    conn = get_db()
    conn.execute("UPDATE meesho_accounts SET xo=?, xo_exp=? WHERE id=?", (xo, xo_exp, acc_id))
    conn.commit()
    conn.close()


# ─── USER OFFERS ───

def save_user_offer(user_id, offer_json):
    conn = get_db()
    conn.execute("INSERT OR REPLACE INTO user_offers (user_id, offer_json, created_at) VALUES (?,?,?)",
                 (user_id, offer_json, time.time()))
    conn.commit()
    conn.close()


def get_user_offer(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM user_offers WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    if row:
        import json as _json
        try:
            return _json.loads(row["offer_json"])
        except Exception:
            return None
    return None


# ─── ADDRESSES ───

def get_addresses(user_id, meesho_account_id=None):
    conn = get_db()
    if meesho_account_id:
        rows = conn.execute(
            "SELECT * FROM addresses WHERE user_id=? AND meesho_account_id=? ORDER BY is_default DESC, created_at DESC",
            (user_id, meesho_account_id)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM addresses WHERE user_id=? ORDER BY is_default DESC, created_at DESC",
            (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_address(addr_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM addresses WHERE id=?", (addr_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_address(user_id, meesho_account_id=0, name="", mobile="", pin="", city="",
                   state="", address_line_1="", address_line_2="", landmark="",
                   address_type="Home", latitude="", longitude="", is_default=0):
    conn = get_db()
    if is_default:
        conn.execute("UPDATE addresses SET is_default=0 WHERE user_id=?", (user_id,))
    conn.execute(
        """INSERT INTO addresses (user_id, meesho_account_id, name, mobile, pin, city, state,
           address_line_1, address_line_2, landmark, address_type, latitude, longitude,
           is_default, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (user_id, meesho_account_id, name, mobile, pin, city, state,
         address_line_1, address_line_2, landmark, address_type, latitude, longitude,
         is_default, time.time()))
    conn.commit()
    aid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return aid


def update_address(addr_id, **kwargs):
    conn = get_db()
    for k, v in kwargs.items():
        conn.execute(f"UPDATE addresses SET {k}=? WHERE id=?", (v, addr_id))
    conn.commit()
    conn.close()


def delete_address(addr_id):
    conn = get_db()
    conn.execute("DELETE FROM addresses WHERE id=?", (addr_id,))
    conn.commit()
    conn.close()


def set_default_address(user_id, addr_id):
    conn = get_db()
    conn.execute("UPDATE addresses SET is_default=0 WHERE user_id=?", (user_id,))
    conn.execute("UPDATE addresses SET is_default=1 WHERE id=?", (addr_id,))
    conn.commit()
    conn.close()


def get_default_address(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM addresses WHERE user_id=? AND is_default=1 LIMIT 1",
        (user_id,)).fetchone()
    if not row:
        row = conn.execute(
            "SELECT * FROM addresses WHERE user_id=? ORDER BY created_at DESC LIMIT 1",
            (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_cart_session(user_id):
    conn = get_db()
    row = conn.execute("SELECT cart_session FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row)["cart_session"] if row and row["cart_session"] else None


def set_cart_session(user_id, cart_session):
    conn = get_db()
    conn.execute("UPDATE users SET cart_session=? WHERE user_id=?", (cart_session, user_id))
    conn.commit()
    conn.close()


init_db()
