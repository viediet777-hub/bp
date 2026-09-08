import os
import sqlite3
from pathlib import Path

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                join_date TEXT,
                wallet_balance REAL DEFAULT 0,
                total_deposited REAL DEFAULT 0,
                total_spent REAL DEFAULT 0,
                referral_code TEXT,
                referred_by INTEGER,
                is_admin INTEGER DEFAULT 0,
                is_banned INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                price REAL DEFAULT 0,
                category TEXT DEFAULT 'General',
                stock INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active',
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE,
                user_id INTEGER,
                product_id INTEGER,
                quantity INTEGER DEFAULT 1,
                total_price REAL DEFAULT 0,
                codes_delivered TEXT DEFAULT '[]',
                status TEXT DEFAULT 'pending',
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS stock_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                code TEXT,
                is_used INTEGER DEFAULT 0,
                order_id TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS deposits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                order_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        self.conn.commit()

    def execute(self, query, params=()):
        self.conn.execute(query, params)
        self.conn.commit()

    def fetchone(self, query, params=()):
        return self.conn.execute(query, params).fetchone()

    def fetchall(self, query, params=()):
        return self.conn.execute(query, params).fetchall()

db = Database(os.getenv("DATABASE_PATH", "bot/database/selling_bot.db"))
