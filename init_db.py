"""
Sunset Courts Management System — Database Initialization
"""

import sqlite3
import os
from datetime import date

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sunset_courts.db')


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def create_tables(conn):
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            account_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            account_name    TEXT    NOT NULL,
            primary_contact TEXT,
            phone           TEXT,
            email           TEXT,
            join_date       DATE    NOT NULL DEFAULT (date('now')),
            is_banned       INTEGER NOT NULL DEFAULT 0,
            is_protected    INTEGER NOT NULL DEFAULT 0,
            notes           TEXT,
            created_at      DATETIME NOT NULL DEFAULT (datetime('now'))
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS courts (
            court_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            court_name  TEXT    NOT NULL UNIQUE,
            status      TEXT    NOT NULL DEFAULT 'Available'
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dues (
            due_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id  INTEGER NOT NULL,
            year        INTEGER NOT NULL,
            is_paid     INTEGER NOT NULL DEFAULT 0,
            amount_paid REAL    DEFAULT 0.0,
            total_due   REAL    DEFAULT 150.0,
            date_paid   DATE,
            notes       TEXT,
            FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
            UNIQUE(account_id, year)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            booking_id      INTEGER  PRIMARY KEY AUTOINCREMENT,
            account_id      INTEGER  NOT NULL,
            court_id        INTEGER  NOT NULL,
            booking_date    DATE     NOT NULL,
            start_time      TEXT     NOT NULL,
            end_time        TEXT     NOT NULL,
            guest_count     INTEGER  NOT NULL DEFAULT 0,
            notes           TEXT,
            is_cancelled    INTEGER  NOT NULL DEFAULT 0,
            created_at      DATETIME NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE,
            FOREIGN KEY (court_id)   REFERENCES courts(court_id)     ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS maintenance_blocks (
            block_id    INTEGER  PRIMARY KEY AUTOINCREMENT,
            court_id    INTEGER  NOT NULL,
            block_date  DATE     NOT NULL,
            start_time  TEXT     NOT NULL,
            end_time    TEXT     NOT NULL,
            reason      TEXT,
            created_at  DATETIME NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (court_id) REFERENCES courts(court_id) ON DELETE CASCADE
        )
    ''')

    # Time verification tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_config (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    conn.commit()
    print("All tables created.")


def seed_data(conn):
    cursor = conn.cursor()

    # MAINTENANCE account — protected, always account_id = 1
    cursor.execute('''
        INSERT OR IGNORE INTO accounts
            (account_id, account_name, primary_contact, is_protected, notes)
        VALUES (1, 'MAINTENANCE', 'System', 1, 'Protected system account for court maintenance blocks. Do not delete.')
    ''')

    # Courts 1-6
    courts = [('Court 1','Available'),('Court 2','Available'),('Court 3','Available'),
              ('Court 4','Available'),('Court 5','Available'),('Court 6','Available')]
    cursor.executemany('INSERT OR IGNORE INTO courts (court_name, status) VALUES (?, ?)', courts)

    conn.commit()
    print("MAINTENANCE account and Courts 1-6 created.")


if __name__ == '__main__':
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = get_connection()
    create_tables(conn)
    seed_data(conn)
    for t in ['accounts','courts','dues','bookings','maintenance_blocks','system_config']:
        c = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        print(f"  {t}: {c} rows")
    conn.close()
    print(f"Database ready: {DB_PATH}")
