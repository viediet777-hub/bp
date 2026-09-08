import json
import uuid
from datetime import datetime
from typing import Optional, List
from bot.database.database import db

class User:
    def __init__(self, user_id, username=None, first_name=None, last_name=None,
                 wallet_balance=0.0, total_deposited=0.0, total_spent=0.0,
                 is_admin=False, is_banned=False):
        self.user_id = user_id
        self.username = username
        self.first_name = first_name
        self.last_name = last_name
        self.wallet_balance = wallet_balance
        self.total_deposited = total_deposited
        self.total_spent = total_spent
        self.is_admin = is_admin
        self.is_banned = is_banned

    @classmethod
    def get(cls, user_id):
        row = db.fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if row:
            return cls(user_id=row['user_id'], username=row['username'],
                       first_name=row['first_name'], last_name=row['last_name'],
                       wallet_balance=row['wallet_balance'],
                       total_deposited=row['total_deposited'],
                       total_spent=row['total_spent'],
                       is_admin=bool(row['is_admin']),
                       is_banned=bool(row['is_banned']))
        return None

    @classmethod
    def get_or_create(cls, user_id, username=None, first_name=None, last_name=None):
        user = cls.get(user_id)
        if not user:
            db.execute(
                "INSERT INTO users (user_id, username, first_name, last_name, join_date) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, first_name, last_name, datetime.now().strftime("%Y-%m-%d"))
            )
            user = cls.get(user_id)
        return user

    def add_balance(self, amount):
        db.execute("UPDATE users SET wallet_balance = wallet_balance + ?, total_deposited = total_deposited + ? WHERE user_id = ?",
                   (amount, amount, self.user_id))
        self.wallet_balance += amount
        self.total_deposited += amount

    def deduct_balance(self, amount):
        db.execute("UPDATE users SET wallet_balance = wallet_balance - ?, total_spent = total_spent + ? WHERE user_id = ?",
                   (amount, amount, self.user_id))
        self.wallet_balance -= amount
        self.total_spent += amount

    @classmethod
    def get_all(cls):
        rows = db.fetchall("SELECT user_id FROM users ORDER BY join_date DESC")
        return [r['user_id'] for r in rows]

    @classmethod
    def count(cls):
        row = db.fetchone("SELECT COUNT(*) as c FROM users")
        return row['c'] if row else 0


class Product:
    def __init__(self, id=None, name="", description="", price=0.0,
                 category="General", stock=0, status="active", created_at=None):
        self.id = id
        self.name = name
        self.description = description
        self.price = price
        self.category = category
        self.stock = stock
        self.status = status
        self.created_at = created_at

    @classmethod
    def get(cls, product_id):
        row = db.fetchone("SELECT * FROM products WHERE id = ?", (product_id,))
        if row:
            return cls(id=row['id'], name=row['name'], description=row['description'],
                       price=row['price'], category=row['category'], stock=row['stock'],
                       status=row['status'], created_at=row['created_at'])
        return None

    @classmethod
    def get_all(cls, status=None):
        if status:
            rows = db.fetchall("SELECT * FROM products WHERE status = ? ORDER BY created_at DESC", (status,))
        else:
            rows = db.fetchall("SELECT * FROM products ORDER BY created_at DESC")
        return [cls(id=r['id'], name=r['name'], description=r['description'],
                    price=r['price'], category=r['category'], stock=r['stock'],
                    status=r['status'], created_at=r['created_at']) for r in rows]

    def save(self):
        if self.id:
            db.execute("UPDATE products SET name=?, description=?, price=?, category=?, stock=?, status=? WHERE id=?",
                       (self.name, self.description, self.price, self.category, self.stock, self.status, self.id))
        else:
            db.execute("INSERT INTO products (name, description, price, category, stock, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (self.name, self.description, self.price, self.category, self.stock, self.status,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            self.id = db.fetchone("SELECT last_insert_rowid() as id")['id']
        return self

    def reduce_stock(self, qty):
        db.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (qty, self.id))
        self.stock -= qty

    def is_available(self, qty=1):
        return self.stock >= qty

    def codes_count(self):
        row = db.fetchone("SELECT COUNT(*) as c FROM stock_codes WHERE product_id = ? AND is_used = 0", (self.id,))
        return row['c'] if row else 0


class Order:
    def __init__(self, id=None, order_id=None, user_id=None, product_id=None,
                 quantity=1, total_price=0.0, codes_delivered="[]",
                 status="pending", created_at=None):
        self.id = id
        self.order_id = order_id
        self.user_id = user_id
        self.product_id = product_id
        self.quantity = quantity
        self.total_price = total_price
        self.codes_delivered = codes_delivered
        self.status = status
        self.created_at = created_at

    @classmethod
    def create(cls, user_id, product_id, quantity, total_price, order_id=None):
        if not order_id:
            order_id = f"ORD-{int(datetime.now().timestamp()*1000)}"
        db.execute(
            "INSERT INTO orders (order_id, user_id, product_id, quantity, total_price, status, created_at) VALUES (?, ?, ?, ?, ?, 'completed', ?)",
            (order_id, user_id, product_id, quantity, total_price, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        return cls.get_by_order_id(order_id)

    @classmethod
    def get_by_order_id(cls, order_id):
        row = db.fetchone("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        if row:
            return cls(id=row['id'], order_id=row['order_id'], user_id=row['user_id'],
                       product_id=row['product_id'], quantity=row['quantity'],
                       total_price=row['total_price'], codes_delivered=row['codes_delivered'],
                       status=row['status'], created_at=row['created_at'])
        return None

    @classmethod
    def get_user_orders(cls, user_id, limit=10):
        rows = db.fetchall("SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
        return [cls(id=r['id'], order_id=r['order_id'], user_id=r['user_id'],
                    product_id=r['product_id'], quantity=r['quantity'],
                    total_price=r['total_price'], codes_delivered=r['codes_delivered'],
                    status=r['status'], created_at=r['created_at']) for r in rows]

    def save_codes(self, codes):
        self.codes_delivered = json.dumps(codes)
        db.execute("UPDATE orders SET codes_delivered = ? WHERE order_id = ?", (self.codes_delivered, self.order_id))


class StockCode:
    @classmethod
    def add_bulk(cls, product_id, codes):
        for code in codes:
            db.execute("INSERT INTO stock_codes (product_id, code, created_at) VALUES (?, ?, ?)",
                       (product_id, code.strip(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    @classmethod
    def count_unused(cls, product_id):
        row = db.fetchone("SELECT COUNT(*) as c FROM stock_codes WHERE product_id = ? AND is_used = 0", (product_id,))
        return row['c'] if row else 0

    @classmethod
    def assign(cls, product_id, order_id, qty):
        codes = db.fetchall(
            "SELECT id, code FROM stock_codes WHERE product_id = ? AND is_used = 0 ORDER BY id ASC LIMIT ?",
            (product_id, qty)
        )
        if len(codes) < qty:
            return []
        assigned = []
        for c in codes:
            db.execute("UPDATE stock_codes SET is_used = 1, order_id = ? WHERE id = ?", (order_id, c['id']))
            assigned.append(c['code'])
        return assigned

    @classmethod
    def get_all_unused(cls, product_id):
        rows = db.fetchall("SELECT code FROM stock_codes WHERE product_id = ? AND is_used = 0", (product_id,))
        return [r['code'] for r in rows]

    @classmethod
    def withdraw(cls, product_id, qty):
        rows = db.fetchall(
            "SELECT id FROM stock_codes WHERE product_id = ? AND is_used = 0 ORDER BY id DESC LIMIT ?",
            (product_id, qty)
        )
        for r in rows:
            db.execute("DELETE FROM stock_codes WHERE id = ?", (r['id'],))
        return len(rows)

    @classmethod
    def export_all(cls, product_id):
        rows = db.fetchall("SELECT code FROM stock_codes WHERE product_id = ? AND is_used = 0", (product_id,))
        return [r['code'] for r in rows]
