"""
Database helper module for the Sunset Courts Management System.
Provides connection management and common query utilities.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sunset_courts.db')


def get_db():
    """Get a database connection with foreign keys and Row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def query_db(query, args=(), one=False):
    """Execute a SELECT query and return results."""
    conn = get_db()
    try:
        cursor = conn.execute(query, args)
        results = cursor.fetchall()
        return results[0] if one and results else (None if one else results)
    finally:
        conn.close()


def execute_db(query, args=()):
    """Execute an INSERT/UPDATE/DELETE and return lastrowid."""
    conn = get_db()
    try:
        cursor = conn.execute(query, args)
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()
