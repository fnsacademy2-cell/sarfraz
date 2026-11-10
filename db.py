import sqlite3
import os
from config import Config

def get_db_connection():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')

    # Customers table (stores customer information, monthly salary day, credit limits)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            alternate_phone TEXT,
            address TEXT,
            salary_day INTEGER DEFAULT 1,
            credit_limit REAL DEFAULT 0.0,
            opening_balance REAL DEFAULT 0.0,
            status TEXT DEFAULT 'active',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Products / Grocery Items Catalog
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'General Grocery',
            unit TEXT DEFAULT 'kg',
            selling_price REAL DEFAULT 0.0,
            cost_price REAL DEFAULT 0.0,
            stock_quantity REAL DEFAULT 0.0,
            barcode TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Bills / Invoices table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_number TEXT UNIQUE NOT NULL,
            customer_id INTEGER NOT NULL,
            bill_date TEXT NOT NULL,
            subtotal REAL DEFAULT 0.0,
            discount REAL DEFAULT 0.0,
            net_amount REAL DEFAULT 0.0,
            paid_amount REAL DEFAULT 0.0,
            due_amount REAL DEFAULT 0.0,
            payment_status TEXT DEFAULT 'due',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE
        )
    ''')

    # Bill items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bill_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bill_id INTEGER NOT NULL,
            product_id INTEGER,
            item_name TEXT NOT NULL,
            unit TEXT DEFAULT 'pcs',
            quantity REAL NOT NULL,
            unit_price REAL NOT NULL,
            total_price REAL NOT NULL,
            FOREIGN KEY (bill_id) REFERENCES bills (id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE SET NULL
        )
    ''')

    # Payments table (tracks payments made against bills or general customer ledger)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_number TEXT UNIQUE NOT NULL,
            customer_id INTEGER NOT NULL,
            bill_id INTEGER,
            payment_date TEXT NOT NULL,
            amount REAL NOT NULL,
            payment_method TEXT DEFAULT 'Cash',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE,
            FOREIGN KEY (bill_id) REFERENCES bills (id) ON DELETE SET NULL
        )
    ''')

    # Default settings if not already present
    default_settings = [
        ('shop_name', 'SARFRAZ General and Grossary Store Newjatoi'),
        ('shop_tagline', 'Fresh Groceries & Monthly Salary Khata Service'),
        ('shop_phone', '+92 300 1234567'),
        ('shop_address', 'Main Commercial Bazaar, Newjatoi, Sindh'),
        ('currency_symbol', 'Rs.'),
        ('footer_note', 'SARFRAZ General and Grossary Store Newjatoi. Please clear your dues on your monthly salary date.')
    ]
    for key, val in default_settings:
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully!")

