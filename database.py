"""
database.py - SQLite Database with TTL Tombstone Support
Brand: VIEDDETX SINGH
Project: FOD Pilot – Meesho First-Order Engine
"""
import sqlite3
import time
from pathlib import Path
from config import DB_PATH

TOMBSTONE_TTL = 300  # 5 minutes TTL for deletion tombstone


def get_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
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
            product_id INTEGER DEFAULT 0,
            supplier_id INTEGER DEFAULT 0,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            price INTEGER DEFAULT 0,
            mrp INTEGER DEFAULT 0,
            rating REAL DEFAULT 4.2,
            stock INTEGER DEFAULT 100,
            image_url TEXT DEFAULT '',
            images TEXT DEFAULT '',
            sizes TEXT DEFAULT '',
            category TEXT DEFAULT '',
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS cart (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cart_id INTEGER DEFAULT 0,
            user_id INTEGER,
            product_id INTEGER,
            supplier_id INTEGER DEFAULT 0,
            variation_id INTEGER DEFAULT 0,
            variation_name TEXT DEFAULT '',
            name TEXT DEFAULT '',
            price INTEGER DEFAULT 0,
            mrp INTEGER DEFAULT 0,
            image TEXT DEFAULT '',
            source TEXT DEFAULT 'meesho',
            qty INTEGER DEFAULT 1,
            identifier TEXT DEFAULT '',
            sellerUPI TEXT DEFAULT '',
            created_at REAL DEFAULT 0,
            updated_at REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS cart_tombstones (
            user_id INTEGER,
            product_id INTEGER,
            variation_id INTEGER DEFAULT 0,
            deleted_at REAL DEFAULT 0,
            PRIMARY KEY (user_id, product_id, variation_id)
        );

        CREATE TABLE IF NOT EXISTS recently_removed (
            user_id INTEGER,
            product_id INTEGER,
            created_at REAL DEFAULT 0,
            PRIMARY KEY (user_id, product_id)
        );

        CREATE TABLE IF NOT EXISTS addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            meesho_account_id INTEGER DEFAULT 0,
            meesho_address_id INTEGER DEFAULT 0,
            name TEXT DEFAULT '',
            mobile TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            pin TEXT DEFAULT '',
            city TEXT DEFAULT '',
            state TEXT DEFAULT '',
            line1 TEXT DEFAULT '',
            line2 TEXT DEFAULT '',
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
            address_id INTEGER DEFAULT 0,
            payment_mode TEXT DEFAULT 'COD',
            payment_method TEXT DEFAULT 'COD',
            status TEXT DEFAULT 'pending',
            items TEXT DEFAULT '',
            breakdown TEXT DEFAULT '',
            total INTEGER DEFAULT 0,
            fee INTEGER DEFAULT 0,
            address TEXT DEFAULT '',
            meesho_order_num TEXT DEFAULT '',
            meesho_amount INTEGER DEFAULT 0,
            created_at REAL DEFAULT 0,
            paid_at REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS otps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            phone TEXT DEFAULT '',
            code TEXT DEFAULT '',
            session_json TEXT DEFAULT '',
            expires_at REAL DEFAULT 0,
            attempts INTEGER DEFAULT 0,
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

        CREATE TABLE IF NOT EXISTS wallet_tx (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER DEFAULT 0,
            type TEXT DEFAULT 'credit',
            status TEXT DEFAULT 'pending',
            txn_id TEXT DEFAULT '',
            created_at REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT DEFAULT ''
        );
    """)
    conn.commit()

    # Apply idempotent column additions for migrations
    migration_columns = [
        ("cart", "sellerUPI", "TEXT DEFAULT ''"),
        ("cart", "supplier_id", "INTEGER DEFAULT 0"),
        ("cart", "variation_id", "INTEGER DEFAULT 0"),
        ("cart", "variation_name", "TEXT DEFAULT ''"),
        ("cart", "mrp", "INTEGER DEFAULT 0"),
        ("cart", "identifier", "TEXT DEFAULT ''"),
        ("cart", "updated_at", "REAL DEFAULT 0"),
        ("orders", "meesho_order_num", "TEXT DEFAULT ''"),
        ("orders", "payment_method", "TEXT DEFAULT 'COD'"),
        ("orders", "payment_mode", "TEXT DEFAULT 'COD'"),
        ("orders", "meesho_amount", "INTEGER DEFAULT 0"),
        ("orders", "paid_at", "REAL DEFAULT 0"),
        ("orders", "breakdown", "TEXT DEFAULT ''"),
        ("orders", "order_num", "TEXT DEFAULT ''"),
        ("users", "cart_session", "TEXT DEFAULT ''"),
        ("addresses", "meesho_address_id", "INTEGER DEFAULT 0"),
        ("addresses", "phone", "TEXT DEFAULT ''"),
        ("addresses", "line1", "TEXT DEFAULT ''"),
        ("addresses", "line2", "TEXT DEFAULT ''"),
        ("meesho_accounts", "instance_id", "TEXT DEFAULT ''"),
        ("meesho_accounts", "app_session_id", "TEXT DEFAULT ''"),
        ("meesho_accounts", "shield_session_id", "TEXT DEFAULT ''"),
        ("meesho_accounts", "gaid", "TEXT DEFAULT ''"),
        ("meesho_accounts", "anon_xo", "TEXT DEFAULT ''"),
        ("meesho_accounts", "identity_json", "TEXT DEFAULT ''"),
        ("meesho_accounts", "is_active", "INTEGER DEFAULT 1"),
        ("wallet_tx", "note", "TEXT DEFAULT ''"),
    ]
    for tbl, col, decl in migration_columns:
        try:
            conn.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {decl}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()


# ─── TOMBSTONE MECHANISM (Fix 1: Prevents Re-import After Removal) ───

def tombstone_add(user_id, product_id, variation_id=0):
    """
    Adds item to tombstone table when removed (qty=0).
    TTL: 300 seconds prevents sync/pull from re-importing stale remote cart items.
    """
    try:
        conn = get_db()
        now = time.time()
        pid = int(product_id)
        vid = int(variation_id or 0)
        conn.execute(
            """INSERT OR REPLACE INTO cart_tombstones (user_id, product_id, variation_id, deleted_at)
               VALUES (?, ?, ?, ?)""",
            (user_id, pid, vid, now),
        )
        conn.execute(
            """INSERT OR REPLACE INTO recently_removed (user_id, product_id, created_at)
               VALUES (?, ?, ?)""",
            (user_id, pid, now),
        )
        # Purge expired entries older than 300 seconds
        cutoff = now - TOMBSTONE_TTL
        conn.execute("DELETE FROM cart_tombstones WHERE deleted_at < ?", (cutoff,))
        conn.execute("DELETE FROM recently_removed WHERE created_at < ?", (cutoff,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[TOMBSTONE] add error: {e}", flush=True)


def tombstone_recent(user_id):
    """
    Returns set of recently removed product_ids within 300s TTL.
    """
    try:
        conn = get_db()
        cutoff = time.time() - TOMBSTONE_TTL
        rows = conn.execute(
            "SELECT product_id FROM cart_tombstones WHERE user_id=? AND deleted_at > ?",
            (user_id, cutoff),
        ).fetchall()
        rows2 = conn.execute(
            "SELECT product_id FROM recently_removed WHERE user_id=? AND created_at > ?",
            (user_id, cutoff),
        ).fetchall()
        conn.close()
        t_set = {int(r["product_id"]) for r in rows}
        t_set.update(int(r["product_id"]) for r in rows2)
        return t_set
    except Exception as e:
        print(f"[TOMBSTONE] query error: {e}", flush=True)
        return set()


# ─── USER OPERATIONS ───

def get_user(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_user(user_id, name=""):
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, name, created_at) VALUES (?, ?, ?)",
        (user_id, name, time.time()),
    )
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
    rows = conn.execute(
        "SELECT user_id, name, phone, wallet, mode, created_at FROM users ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_order_count(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM orders WHERE user_id=?", (user_id,)
    ).fetchone()
    conn.close()
    return dict(row)["cnt"] if row else 0


def add_wallet(user_id, amount, note="", ref_id=""):
    """
    Credits user wallet balance and logs a completed credit transaction.
    """
    conn = get_db()
    amt = int(amount)
    conn.execute("UPDATE users SET wallet=wallet+? WHERE user_id=?", (amt, user_id))
    conn.execute(
        "INSERT INTO wallet_tx (user_id, amount, type, status, txn_id, note, created_at) VALUES (?,?,?,?,?,?,?)",
        (user_id, amt, "credit", "completed", str(ref_id or ""), str(note or "Wallet recharge"), time.time()),
    )
    conn.commit()
    conn.close()


def deduct_wallet(user_id, amount, note="", ref_id=""):
    """
    Atomically deducts wallet balance if sufficient funds exist.
    Records debit transaction in wallet_tx.
    Returns:
        bool: True on successful deduction, False if insufficient balance.
    """
    conn = get_db()
    amt = int(amount)
    cur = conn.execute(
        "UPDATE users SET wallet=wallet-? WHERE user_id=? AND wallet>=?",
        (amt, user_id, amt),
    )
    success = cur.rowcount > 0
    if success:
        conn.execute(
            "INSERT INTO wallet_tx (user_id, amount, type, status, txn_id, note, created_at) VALUES (?,?,?,?,?,?,?)",
            (user_id, -amt, "debit", "completed", str(ref_id or ""), str(note or "Order service fee"), time.time()),
        )
        conn.commit()
    conn.close()
    return success


def get_wallet_balance(user_id):
    """Returns current wallet balance for user."""
    conn = get_db()
    row = conn.execute("SELECT wallet FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    if row and row["wallet"] is not None:
        return int(row["wallet"])
    return 0



def get_global_mode():
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key='global_mode'").fetchone()
    conn.close()
    if row and row["value"]:
        return str(row["value"]).strip().lower()
    return "free"


def set_global_mode(mode):
    clean_mode = "paid" if str(mode).strip().lower() == "paid" else "free"
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES ('global_mode', ?, ?)",
        (clean_mode, time.time()),
    )
    conn.commit()
    conn.close()
    return clean_mode


def get_order_fee():
    """
    Returns platform service fee based on active global_mode in settings table.
    In 'free' mode, fee is 0.
    In 'paid' mode, reads 'order_fee' from settings (defaults to 5).
    """
    mode = get_global_mode()
    if mode == "free":
        return 0
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key='order_fee'").fetchone()
    conn.close()
    if row and row["value"] is not None:
        try:
            return int(row["value"])
        except (ValueError, TypeError):
            pass
    return 5


def set_order_fee(fee):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES ('order_fee', ?, ?)",
        (str(int(fee)), time.time()),
    )
    conn.commit()
    conn.close()


def toggle_user_mode(user_id=None):
    current = get_global_mode()
    new_mode = "free" if current == "paid" else "paid"
    set_global_mode(new_mode)
    return new_mode


def get_user_mode(user_id=None):
    return get_global_mode()


# ─── CART OPERATIONS ───

def get_cart(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM cart WHERE user_id=? ORDER BY created_at ASC", (user_id,)
    ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        if not d.get("name"):
            p = get_product(d.get("product_id"))
            if p:
                d["name"] = p.get("name", "")
                d["price"] = p.get("price", 0)
                d["image"] = p.get("image_url", "")
        # Populate line item aliases
        d["line1"] = d.get("variation_name") or ""
        result.append(d)
    conn.close()
    return result


def add_to_cart(
    user_id,
    product_id,
    qty=1,
    name="",
    price=0,
    image="",
    source="meesho",
    supplier_id=0,
    variation_id=0,
    variation_name="",
    mrp=0,
    sellerUPI="",
    identifier="",
):
    conn = get_db()
    now = time.time()
    existing = conn.execute(
        "SELECT id, qty FROM cart WHERE user_id=? AND product_id=?",
        (user_id, product_id),
    ).fetchone()
    if existing:
        conn.execute(
            """UPDATE cart SET qty=qty+?, price=?, mrp=?, variation_id=?, variation_name=?, updated_at=?
               WHERE id=?""",
            (qty, price, mrp or price, variation_id, variation_name, now, existing["id"]),
        )
    else:
        conn.execute(
            """INSERT INTO cart (user_id, product_id, name, price, image, source, qty,
               supplier_id, variation_id, variation_name, mrp, sellerUPI, identifier, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                user_id,
                product_id,
                name,
                price,
                image,
                source,
                qty,
                supplier_id,
                variation_id,
                variation_name,
                mrp or price,
                sellerUPI,
                identifier,
                now,
                now,
            ),
        )
    conn.commit()
    conn.close()


def update_cart_qty(cart_id, qty):
    conn = get_db()
    if qty <= 0:
        conn.execute("DELETE FROM cart WHERE id=?", (cart_id,))
    else:
        conn.execute("UPDATE cart SET qty=?, updated_at=? WHERE id=?", (qty, time.time(), cart_id))
    conn.commit()
    conn.close()


def clear_cart(user_id):
    conn = get_db()
    conn.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def get_cart_session(user_id):
    conn = get_db()
    row = conn.execute("SELECT cart_session FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row)["cart_session"] if row and row["cart_session"] else None


def set_cart_session(user_id, cart_session):
    conn = get_db()
    conn.execute("UPDATE users SET cart_session=? WHERE user_id=?", (cart_session or "", user_id))
    conn.commit()
    conn.close()


# ─── ORDER OPERATIONS ───

def create_order(
    user_id,
    items,
    total,
    fee=0,
    address="",
    meesho_order_num="",
    payment_method="COD",
    meesho_amount=0,
    breakdown="",
    address_id=0,
):
    conn = get_db()
    now = time.time()
    order_num = meesho_order_num or str(int(now * 1000))[-8:]
    conn.execute(
        """INSERT INTO orders (order_num, user_id, address_id, payment_mode, payment_method,
           status, items, breakdown, total, fee, address, meesho_order_num, meesho_amount, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            order_num,
            user_id,
            address_id,
            payment_method,
            payment_method,
            "pending",
            items,
            breakdown,
            total,
            fee,
            address,
            meesho_order_num,
            meesho_amount,
            now,
        ),
    )
    conn.commit()
    oid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return oid


def get_orders(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def sync_meesho_orders_to_db(user_id, meesho_orders):
    """
    Stores or updates real Meesho orders into the database orders table,
    preventing duplicate inserts based on meesho_order_num or order_num.
    """
    if not meesho_orders:
        return 0
    conn = get_db()
    inserted_or_updated = 0
    now = time.time()
    for o in meesho_orders:
        m_num = str(o.get("sub_order_id") or o.get("order_id") or o.get("id") or "").strip()
        if not m_num:
            continue

        existing = conn.execute(
            "SELECT id FROM orders WHERE user_id=? AND (meesho_order_num=? OR order_num=?)",
            (user_id, m_num, m_num),
        ).fetchone()

        status = str(o.get("sub_order_status") or o.get("status") or o.get("order_status") or "placed").lower()
        total = int(o.get("total_price") or o.get("amount") or o.get("total") or o.get("price") or 0)

        items_name = o.get("product_title") or o.get("product_name") or o.get("item_title") or ""
        if not items_name and o.get("sub_orders"):
            items_name = ", ".join([so.get("product_title") or so.get("product_name") or "Item" for so in o["sub_orders"]])
        if not items_name:
            items_name = f"Meesho Order #{m_num}"

        # Extract image if present
        img = o.get("product_image") or o.get("image") or o.get("image_url") or o.get("cover_image") or ""
        if not img and isinstance(o.get("product_images"), list) and o["product_images"]:
            first_im = o["product_images"][0]
            img = first_im.get("url") if isinstance(first_im, dict) else str(first_im)
        if not img and o.get("sub_orders") and isinstance(o["sub_orders"], list):
            for so in o["sub_orders"]:
                so_img = so.get("product_image") or so.get("image") or so.get("image_url") or ""
                if not so_img and isinstance(so.get("product_images"), list) and so["product_images"]:
                    f_im = so["product_images"][0]
                    so_img = f_im.get("url") if isinstance(f_im, dict) else str(f_im)
                if so_img:
                    img = so_img
                    break

        import json
        items_payload = json.dumps([{
            "name": items_name,
            "image": img,
            "price": total,
            "qty": 1
        }])

        created_raw = o.get("sub_order_created") or o.get("created_at") or o.get("order_date")
        created_ts = now
        if created_raw:
            try:
                if isinstance(created_raw, (int, float)):
                    created_ts = created_raw / 1000.0 if created_raw > 1e11 else float(created_raw)
            except Exception:
                pass

        if existing:
            conn.execute(
                "UPDATE orders SET status=?, items=?, total=?, meesho_amount=? WHERE id=?",
                (status, items_payload, total, total, existing["id"]),
            )
            inserted_or_updated += 1
        else:
            conn.execute(
                """INSERT INTO orders (order_num, user_id, address_id, payment_mode, payment_method,
                   status, items, breakdown, total, fee, address, meesho_order_num, meesho_amount, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    m_num,
                    user_id,
                    0,
                    o.get("payment_mode") or "COD",
                    o.get("payment_mode") or "COD",
                    status,
                    items_payload,
                    "",
                    total,
                    0,
                    o.get("delivery_address") or "",
                    m_num,
                    total,
                    created_ts,
                ),
            )
            inserted_or_updated += 1

    conn.commit()
    conn.close()
    return inserted_or_updated


def get_order(oid):
    conn = get_db()
    row = conn.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_order_status(oid, status, paid_at=None):
    conn = get_db()
    if paid_at:
        conn.execute("UPDATE orders SET status=?, paid_at=? WHERE id=?", (status, paid_at, oid))
    else:
        conn.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
    conn.commit()
    conn.close()


def get_all_orders():
    conn = get_db()
    rows = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── ADDRESS OPERATIONS ───

def get_addresses(user_id, meesho_account_id=None):
    conn = get_db()
    if meesho_account_id:
        rows = conn.execute(
            """SELECT * FROM addresses WHERE user_id=? AND meesho_account_id=?
               ORDER BY is_default DESC, created_at DESC""",
            (user_id, meesho_account_id),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM addresses WHERE user_id=?
               ORDER BY is_default DESC, created_at DESC""",
            (user_id,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_address(addr_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM addresses WHERE id=?", (addr_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_address(
    user_id,
    meesho_account_id=0,
    name="",
    mobile="",
    pin="",
    city="",
    state="",
    address_line_1="",
    address_line_2="",
    landmark="",
    address_type="Home",
    latitude="",
    longitude="",
    is_default=0,
    meesho_address_id=0,
):
    conn = get_db()
    if is_default:
        conn.execute("UPDATE addresses SET is_default=0 WHERE user_id=?", (user_id,))
    conn.execute(
        """INSERT INTO addresses (user_id, meesho_account_id, meesho_address_id, name, mobile, phone,
           pin, city, state, line1, line2, address_line_1, address_line_2, landmark, address_type,
           latitude, longitude, is_default, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            user_id,
            meesho_account_id,
            meesho_address_id,
            name,
            mobile,
            mobile,
            pin,
            city,
            state,
            address_line_1,
            address_line_2,
            address_line_1,
            address_line_2,
            landmark,
            address_type,
            latitude,
            longitude,
            is_default,
            time.time(),
        ),
    )
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
        "SELECT * FROM addresses WHERE user_id=? AND is_default=1 LIMIT 1", (user_id,)
    ).fetchone()
    if not row:
        row = conn.execute(
            "SELECT * FROM addresses WHERE user_id=? ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    conn.close()
    return dict(row) if row else None


# ─── MEESHO ACCOUNTS ───

def save_meesho_account(
    user_id,
    phone,
    meesho_user_id,
    xo,
    xo_exp=0,
    instance_id="",
    is_first_order=1,
    app_session_id="",
    shield_session_id="",
    gaid="",
    anon_xo="",
    identity_json="",
):
    conn = get_db()
    meesho_user_id = str(meesho_user_id)
    existing = None
    if meesho_user_id:
        existing = conn.execute(
            "SELECT * FROM meesho_accounts WHERE user_id=? AND meesho_user_id=?",
            (user_id, meesho_user_id),
        ).fetchone()
    if existing:
        old = dict(existing)
        conn.execute(
            """UPDATE meesho_accounts SET phone=?, xo=?, xo_exp=?, instance_id=?,
               is_first_order=?, app_session_id=?, shield_session_id=?, gaid=?, anon_xo=?,
               identity_json=?, is_active=1, created_at=?
               WHERE id=?""",
            (
                phone or old.get("phone", ""),
                xo or old.get("xo", ""),
                xo_exp or old.get("xo_exp", 0),
                instance_id or old.get("instance_id", ""),
                int(is_first_order),
                app_session_id or old.get("app_session_id", ""),
                shield_session_id or old.get("shield_session_id", ""),
                gaid or old.get("gaid", ""),
                anon_xo or old.get("anon_xo", ""),
                identity_json or old.get("identity_json", ""),
                time.time(),
                old["id"],
            ),
        )
    else:
        conn.execute(
            """INSERT INTO meesho_accounts (user_id, phone, meesho_user_id, xo, xo_exp, instance_id,
               is_first_order, app_session_id, shield_session_id, gaid, anon_xo, identity_json, is_active, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                user_id,
                phone,
                meesho_user_id,
                xo,
                xo_exp,
                instance_id,
                int(is_first_order),
                app_session_id,
                shield_session_id,
                gaid,
                anon_xo,
                identity_json,
                1,
                time.time(),
            ),
        )
    conn.commit()
    conn.close()


def get_meesho_accounts(user_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM meesho_accounts WHERE user_id=? ORDER BY created_at DESC", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_active_meesho_account(user_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM meesho_accounts WHERE user_id=? AND is_active=1 ORDER BY created_at DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    if not row:
        row = conn.execute(
            "SELECT * FROM meesho_accounts WHERE user_id=? ORDER BY created_at DESC LIMIT 1",
            (user_id,),
        ).fetchone()
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
    conn.execute(
        "INSERT OR REPLACE INTO user_offers (user_id, offer_json, created_at) VALUES (?,?,?)",
        (user_id, offer_json, time.time()),
    )
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
    row = conn.execute("SELECT * FROM products WHERE id=? OR product_id=?", (pid, pid)).fetchone()
    conn.close()
    return dict(row) if row else None


def add_product(name, price, stock=100, desc="", category="", image=""):
    conn = get_db()
    conn.execute(
        "INSERT INTO products (name, price, stock, description, category, image_url) VALUES (?,?,?,?,?,?)",
        (name, price, stock, desc, category, image),
    )
    conn.commit()
    pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return pid


def update_stock(pid, qty):
    conn = get_db()
    conn.execute("UPDATE products SET stock=stock-? WHERE id=? AND stock>=?", (qty, pid, qty))
    conn.commit()
    conn.close()


# ─── WALLET TRANSACTIONS ───

def create_wallet_tx(user_id, amount, txn_id="", note="Wallet recharge"):
    conn = get_db()
    conn.execute(
        "INSERT INTO wallet_tx (user_id, amount, type, status, txn_id, note, created_at) VALUES (?,?,?,?,?,?,?)",
        (user_id, int(amount), "credit", "pending", txn_id, note, time.time()),
    )
    conn.commit()
    txid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return txid


def verify_wallet_tx(txid):
    """
    Marks a wallet transaction as completed by database ID and credits the user's wallet.
    Idempotent: will not double-credit if already completed.
    """
    conn = get_db()
    row = conn.execute("SELECT * FROM wallet_tx WHERE id=?", (txid,)).fetchone()
    if row and row["status"] != "completed":
        conn.execute("UPDATE wallet_tx SET status='completed' WHERE id=?", (txid,))
        conn.execute(
            "UPDATE users SET wallet=wallet+? WHERE user_id=?", (row["amount"], row["user_id"])
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM wallet_tx WHERE id=?", (txid,)).fetchone()
        conn.close()
        return dict(updated)
    conn.close()
    return dict(row) if row else None


def verify_wallet_tx_by_order_id(txn_id, verified_amount=None):
    """
    Idempotent verification by gateway order/transaction ID (from VC Gateway).
    Marks transaction as completed and credits user wallet balance.
    """
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM wallet_tx WHERE txn_id=? ORDER BY id DESC LIMIT 1", (txn_id,)
    ).fetchone()
    if not row:
        conn.close()
        return None

    if row["status"] == "completed":
        conn.close()
        return dict(row)

    amt = int(float(verified_amount)) if verified_amount else int(row["amount"])
    conn.execute("UPDATE wallet_tx SET status='completed', amount=? WHERE id=?", (amt, row["id"]))
    conn.execute("UPDATE users SET wallet=wallet+? WHERE user_id=?", (amt, row["user_id"]))
    conn.commit()
    updated = conn.execute("SELECT * FROM wallet_tx WHERE id=?", (row["id"],)).fetchone()
    conn.close()
    return dict(updated)


def get_wallet_tx(user_id, limit=20):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM wallet_tx WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (user_id, limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]



init_db()
