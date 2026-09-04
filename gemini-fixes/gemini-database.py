import os
import sqlite3
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "bot.db"

TOMBSTONE_TTL = 300  # 5 minutes lifespan to prevent Meesho sync ghost imports


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
            mode TEXT DEFAULT 'free',
            referral_link TEXT DEFAULT '',
            cart_session TEXT DEFAULT '',
            created_at REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER UNIQUE,
            supplier_id INTEGER DEFAULT 0,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            price INTEGER DEFAULT 0,
            mrp INTEGER DEFAULT 0,
            stock INTEGER DEFAULT 0,
            image_url TEXT DEFAULT '',
            category TEXT DEFAULT '',
            rating REAL DEFAULT 0.0,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            name TEXT DEFAULT '',
            price INTEGER DEFAULT 0,
            image TEXT DEFAULT '',
            source TEXT DEFAULT 'meesho',
            qty INTEGER DEFAULT 1,
            supplier_id INTEGER DEFAULT 0,
            variation_id INTEGER DEFAULT 0,
            variation_name TEXT DEFAULT '',
            mrp INTEGER DEFAULT 0,
            sellerUPI TEXT DEFAULT '',
            identifier TEXT DEFAULT '',
            created_at REAL DEFAULT 0,
            UNIQUE(user_id, product_id, variation_id) ON CONFLICT REPLACE
        );

        CREATE TABLE IF NOT EXISTS recently_removed (
            user_id INTEGER,
            product_id INTEGER,
            variation_id INTEGER DEFAULT 0,
            created_at REAL DEFAULT 0,
            PRIMARY KEY (user_id, product_id, variation_id)
        );

        CREATE TABLE IF NOT EXISTS addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            meesho_account_id INTEGER DEFAULT 0,
            meesho_address_id INTEGER DEFAULT 0,
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

        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_num TEXT DEFAULT '',
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
            anon_xo TEXT DEFAULT '',
            identity_json TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS user_offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            offer_json TEXT DEFAULT '',
            created_at REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS otps (
            phone TEXT PRIMARY KEY,
            session_json TEXT DEFAULT '',
            created_at REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
        );
    """)
    conn.commit()
    conn.close()


# ─── USERS ───
def get_user(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_user(user_id, name=""):
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, name, created_at) VALUES (?, ?, ?)",
        (user_id, name, time.time())
    )
    conn.commit()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_cart_session(user_id):
    conn = get_db()
    row = conn.execute("SELECT cart_session FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row)["cart_session"] if row and row["cart_session"] else ""


def set_cart_session(user_id, cart_session):
    conn = get_db()
    conn.execute("UPDATE users SET cart_session=? WHERE user_id=?", (cart_session or "", user_id))
    conn.commit()
    conn.close()


# ─── TOMBSTONES ───
def tombstone_add(user_id, product_id, variation_id=0):
    """Marks a product as deleted so background pulls don't resurrect it."""
    try:
        conn = get_db()
        conn.execute(
            "INSERT OR REPLACE INTO recently_removed (user_id, product_id, variation_id, created_at) VALUES (?,?,?,?)",
            (user_id, int(product_id), int(variation_id or 0), time.time())
        )
        conn.execute("DELETE FROM recently_removed WHERE created_at < ?", (time.time() - TOMBSTONE_TTL,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[TOMBSTONE] Add failed: {e}", flush=True)


def tombstone_recent(user_id):
    """Returns set of active tombstoned product IDs."""
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT product_id FROM recently_removed WHERE user_id=? AND created_at > ?",
            (user_id, time.time() - TOMBSTONE_TTL)
        ).fetchall()
        conn.close()
        return {int(r["product_id"]) for r in rows}
    except Exception:
        return set()


# ─── CART ───
def get_cart(user_id):
    conn = get_db()
    rows = conn.execute("SELECT * FROM cart WHERE user_id=?", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_to_cart(user_id, product_id, qty=1, name="", price=0, image="",
                source="meesho", supplier_id=0, variation_id=0, variation_name="", mrp=0, identifier=""):
    conn = get_db()
    existing = conn.execute(
        "SELECT id, qty FROM cart WHERE user_id=? AND product_id=? AND variation_id=?",
        (user_id, int(product_id), int(variation_id or 0))
    ).fetchone()

    if existing:
        conn.execute("UPDATE cart SET qty=qty+?, price=?, mrp=? WHERE id=?",
                     (int(qty), int(price), int(mrp), existing["id"]))
    else:
        conn.execute(
            """INSERT INTO cart (user_id, product_id, name, price, image, source, qty,
               supplier_id, variation_id, variation_name, mrp, identifier, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (user_id, int(product_id), name, int(price), image, source, int(qty),
             int(supplier_id or 0), int(variation_id or 0), variation_name, int(mrp), identifier or "", time.time())
        )
    conn.commit()
    conn.close()


def update_cart_qty(cart_id, qty):
    conn = get_db()
    if int(qty) <= 0:
        conn.execute("DELETE FROM cart WHERE id=?", (cart_id,))
    else:
        conn.execute("UPDATE cart SET qty=? WHERE id=?", (int(qty), cart_id))
    conn.commit()
    conn.close()


def clear_cart(user_id):
    conn = get_db()
    conn.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


# ─── ORDERS ───
def create_order(user_id, items, total, fee=0, address="", meesho_order_num="",
                 payment_method="COD", meesho_amount=0):
    conn = get_db()
    conn.execute(
        """INSERT INTO orders (user_id, items, total, fee, status, address,
           meesho_order_num, payment_method, meesho_amount, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (user_id, items, int(total), int(fee), "pending", address,
         str(meesho_order_num), payment_method, int(meesho_amount), time.time())
    )
    conn.commit()
    oid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return oid


def get_orders(user_id):
    conn = get_db()
    rows = conn.execute("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC", (user_id,)).fetchall()
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


# ─── ADDRESSES ───
def get_addresses(user_id):
    conn = get_db()
    rows = conn.execute("SELECT * FROM addresses WHERE user_id=? ORDER BY is_default DESC, created_at DESC", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_address(addr_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM addresses WHERE id=?", (addr_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_default_address(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM addresses WHERE user_id=? AND is_default=1 LIMIT 1", (user_id,)).fetchone()
    if not row:
        row = conn.execute("SELECT * FROM addresses WHERE user_id=? ORDER BY created_at DESC LIMIT 1", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def set_default_address(user_id, addr_id):
    conn = get_db()
    conn.execute("UPDATE addresses SET is_default=0 WHERE user_id=?", (user_id,))
    conn.execute("UPDATE addresses SET is_default=1 WHERE id=? AND user_id=?", (addr_id, user_id))
    conn.commit()
    conn.close()


def create_address(user_id, meesho_account_id=0, name="", mobile="", pin="", city="",
                   state="", address_line_1="", address_line_2="", landmark="",
                   address_type="Home", latitude="", longitude="", is_default=0, meesho_address_id=0):
    conn = get_db()
    if is_default:
        conn.execute("UPDATE addresses SET is_default=0 WHERE user_id=?", (user_id,))
    conn.execute(
        """INSERT INTO addresses (user_id, meesho_account_id, name, mobile, pin, city, state,
           address_line_1, address_line_2, landmark, address_type, latitude, longitude,
           is_default, meesho_address_id, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (user_id, meesho_account_id, name, mobile, pin, city, state,
         address_line_1, address_line_2, landmark, address_type, latitude, longitude,
         is_default, meesho_address_id, time.time())
    )
    conn.commit()
    aid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return aid


# ─── MEESHO ACCOUNTS ───
def save_meesho_account(user_id, phone, meesho_user_id, xo, xo_exp=0, instance_id="", is_first_order=1,
                        app_session_id="", shield_session_id="", gaid="", anon_xo="", identity_json=""):
    conn = get_db()
    conn.execute("UPDATE meesho_accounts SET is_active=0 WHERE user_id=?", (user_id,))
    existing = conn.execute(
        "SELECT * FROM meesho_accounts WHERE user_id=? AND (meesho_user_id=? OR phone=?)",
        (user_id, str(meesho_user_id), str(phone))
    ).fetchone()

    if existing:
        conn.execute(
            """UPDATE meesho_accounts SET phone=?, meesho_user_id=?, xo=?, xo_exp=?, instance_id=?,
               is_first_order=?, app_session_id=?, shield_session_id=?, gaid=?, anon_xo=?,
               identity_json=?, is_active=1, created_at=? WHERE id=?""",
            (str(phone), str(meesho_user_id), str(xo), float(xo_exp or 0), str(instance_id),
             int(is_first_order), str(app_session_id), str(shield_session_id), str(gaid),
             str(anon_xo), str(identity_json), time.time(), existing["id"])
        )
    else:
        conn.execute(
            """INSERT INTO meesho_accounts (user_id, phone, meesho_user_id, xo, xo_exp, instance_id,
               is_first_order, app_session_id, shield_session_id, gaid, anon_xo, identity_json, is_active, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1,?)""",
            (user_id, str(phone), str(meesho_user_id), str(xo), float(xo_exp or 0), str(instance_id),
             int(is_first_order), str(app_session_id), str(shield_session_id), str(gaid),
             str(anon_xo), str(identity_json), time.time())
        )
    conn.commit()
    conn.close()


def get_meesho_accounts(user_id):
    conn = get_db()
    rows = conn.execute("SELECT * FROM meesho_accounts WHERE user_id=? ORDER BY is_active DESC, created_at DESC", (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_active_meesho_account(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM meesho_accounts WHERE user_id=? AND is_active=1 LIMIT 1", (user_id,)).fetchone()
    if not row:
        row = conn.execute("SELECT * FROM meesho_accounts WHERE user_id=? ORDER BY created_at DESC LIMIT 1", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


init_db()