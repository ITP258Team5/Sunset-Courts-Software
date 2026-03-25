"""
Sunset Courts Management System — Database Initialization
Creates the SQLite schema and seeds with sample data.
"""

import sqlite3
import os
from datetime import date, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sunset_courts.db')


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def create_tables(conn):
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS families (
            family_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            family_name     TEXT    NOT NULL,
            primary_contact TEXT,
            phone           TEXT,
            email           TEXT,
            join_date       DATE    NOT NULL DEFAULT (date('now')),
            is_banned       INTEGER NOT NULL DEFAULT 0,
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
            family_id   INTEGER NOT NULL,
            year        INTEGER NOT NULL,
            is_paid     INTEGER NOT NULL DEFAULT 0,
            amount_paid REAL    DEFAULT 0.0,
            date_paid   DATE,
            notes       TEXT,
            FOREIGN KEY (family_id) REFERENCES families(family_id) ON DELETE CASCADE,
            UNIQUE(family_id, year)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            booking_id      INTEGER  PRIMARY KEY AUTOINCREMENT,
            family_id       INTEGER  NOT NULL,
            court_id        INTEGER  NOT NULL,
            booking_date    DATE     NOT NULL,
            start_time      TEXT     NOT NULL,
            end_time        TEXT     NOT NULL,
            guest_count     INTEGER  NOT NULL DEFAULT 0,
            notes           TEXT,
            is_cancelled    INTEGER  NOT NULL DEFAULT 0,
            created_at      DATETIME NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (family_id) REFERENCES families(family_id) ON DELETE CASCADE,
            FOREIGN KEY (court_id)  REFERENCES courts(court_id)  ON DELETE CASCADE
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

    conn.commit()
    print("All tables created.")


def seed_data(conn):
    cursor = conn.cursor()

    courts = [('Court 1','Available'),('Court 2','Available'),('Court 3','Available'),
              ('Court 4','Available'),('Court 5','Available'),('Court 6','Available')]
    cursor.executemany('INSERT OR IGNORE INTO courts (court_name, status) VALUES (?, ?)', courts)

    families = [
        ('The Johnson Family','Robert Johnson','540-555-0101','rjohnson@email.com','2024-03-15',0,None),
        ('The Martinez Family','Sofia Martinez','540-555-0202','smartinez@email.com','2023-01-10',0,None),
        ('The Williams Family','Derek Williams','540-555-0303','dwilliams@email.com','2025-06-01',0,None),
        ('The Chen Family','Linda Chen','540-555-0404','lchen@email.com','2024-09-20',0,None),
        ('The Patel Family','Raj Patel','540-555-0505','rpatel@email.com','2022-04-05',1,'Banned for repeated no-shows'),
    ]
    cursor.executemany('''INSERT OR IGNORE INTO families
        (family_name, primary_contact, phone, email, join_date, is_banned, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)''', families)

    yr = date.today().year
    dues = [
        (1,yr,1,150.00,f'{yr}-01-15',None),(2,yr,1,150.00,f'{yr}-02-01',None),
        (3,yr,0,0.0,None,'New member'),(4,yr,1,150.00,f'{yr}-01-20',None),
        (5,yr,0,0.0,None,'Banned'),
    ]
    cursor.executemany('''INSERT OR IGNORE INTO dues
        (family_id, year, is_paid, amount_paid, date_paid, notes) VALUES (?,?,?,?,?,?)''', dues)

    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    day_after = (date.today() + timedelta(days=2)).isoformat()
    bookings = [
        (1, 1, today,     '09:00', '10:00', 1, 'Morning tennis'),
        (1, 3, today,     '14:00', '15:30', 0, None),
        (2, 2, tomorrow,  '10:00', '11:00', 2, 'Pickleball with guests'),
        (4, 5, tomorrow,  '16:00', '17:00', 0, None),
        (3, 1, day_after, '08:00', '09:30', 0, 'Early session'),
    ]
    cursor.executemany('''INSERT OR IGNORE INTO bookings
        (family_id, court_id, booking_date, start_time, end_time, guest_count, notes)
        VALUES (?,?,?,?,?,?,?)''', bookings)

    conn.commit()
    print("Seed data inserted.")


if __name__ == '__main__':
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = get_connection()
    create_tables(conn)
    seed_data(conn)
    for t in ['families','courts','dues','bookings','maintenance_blocks']:
        c = conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        print(f"  {t}: {c} rows")
    conn.close()
    print(f"Database ready: {DB_PATH}")
