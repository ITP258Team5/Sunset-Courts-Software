"""
Sunset Courts — Demo Data Generator
Run AFTER init_db.py to populate the database with realistic test data.
Usage: python3 seed_demo.py
"""

import sqlite3
import os
import random
from datetime import date, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sunset_courts.db')

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON")
cursor = conn.cursor()

# ── Accounts ────────────────────────────────────────────────────
accounts = [
    ('The Johnson Family', 'Robert Johnson', '540-555-0101', 'rjohnson@email.com', '2023-03-15'),
    ('The Martinez Family', 'Sofia Martinez', '540-555-0202', 'smartinez@email.com', '2022-01-10'),
    ('Derek Williams', 'Derek Williams', '540-555-0303', 'dwilliams@email.com', '2024-06-01'),
    ('The Chen Family', 'Linda Chen', '540-555-0404', 'lchen@email.com', '2023-09-20'),
    ('The Patel Family', 'Raj Patel', '540-555-0505', 'rpatel@email.com', '2022-04-05'),
    ('Sarah Thompson', 'Sarah Thompson', '540-555-0606', 'sthompson@email.com', '2024-01-12'),
    ('The Garcia Family', 'Maria Garcia', '540-555-0707', 'mgarcia@email.com', '2023-07-22'),
    ('James Wilson', 'James Wilson', '540-555-0808', 'jwilson@email.com', '2024-03-30'),
    ('The Kim Family', 'David Kim', '540-555-0909', 'dkim@email.com', '2022-11-15'),
    ('The Brown Family', 'Angela Brown', '540-555-1010', 'abrown@email.com', '2023-05-18'),
    ('Mike Taylor', 'Mike Taylor', '540-555-1111', 'mtaylor@email.com', '2024-08-05'),
    ('The Robinson Family', 'Chris Robinson', '540-555-1212', 'crobinson@email.com', '2022-02-28'),
    ('Emily Davis', 'Emily Davis', '540-555-1313', 'edavis@email.com', '2024-04-14'),
    ('The Nguyen Family', 'Tran Nguyen', '540-555-1414', 'tnguyen@email.com', '2023-10-01'),
    ('The Cooper Family', 'Janet Cooper', '540-555-1515', 'jcooper@email.com', '2022-06-20'),
    ('Alex Morgan', 'Alex Morgan', '540-555-1616', 'amorgan@email.com', '2025-01-08'),
    ('The Reed Family', 'Tom Reed', '540-555-1717', 'treed@email.com', '2024-11-12'),
    ('Lisa Park', 'Lisa Park', '540-555-1818', 'lpark@email.com', '2025-02-20'),
    ('The Adams Family', 'Steve Adams', '540-555-1919', 'sadams@email.com', '2023-08-30'),
    ('The Wright Family', 'Karen Wright', '540-555-2020', 'kwright@email.com', '2024-05-25'),
]

for name, contact, phone, email, join in accounts:
    cursor.execute('''
        INSERT INTO accounts (account_name, primary_contact, phone, email, join_date, notes)
        VALUES (?, ?, ?, ?, ?, NULL)
    ''', (name, contact, phone, email, join))

# Ban one account
cursor.execute("UPDATE accounts SET is_banned = 1, notes = 'Repeated no-shows' WHERE account_id = 6")

print(f"  {len(accounts)} accounts created (1 banned)")

# ── Dues ────────────────────────────────────────────────────────
current_year = date.today().year
account_ids = list(range(2, 2 + len(accounts)))  # 2 through 21 (1 is MAINTENANCE)

for aid in account_ids:
    # Current year
    paid = random.random() < 0.75  # 75% paid
    amount = 150.0 if paid else random.choice([0.0, 0.0, 75.0])  # some partial
    is_paid = 1 if amount >= 150 else 0
    date_paid = None
    if amount > 0:
        month = random.randint(1, min(date.today().month, 12))
        day = random.randint(1, 28)
        date_paid = f"{current_year}-{month:02d}-{day:02d}"

    cursor.execute('''
        INSERT OR IGNORE INTO dues (account_id, year, is_paid, amount_paid, total_due, date_paid)
        VALUES (?, ?, ?, ?, 150.0, ?)
    ''', (aid, current_year, is_paid, amount, date_paid))

    # Previous year — everyone paid
    prev_date = f"{current_year - 1}-{random.randint(1,3):02d}-{random.randint(1,28):02d}"
    cursor.execute('''
        INSERT OR IGNORE INTO dues (account_id, year, is_paid, amount_paid, total_due, date_paid)
        VALUES (?, ?, 1, 150.0, 150.0, ?)
    ''', (aid, current_year - 1, prev_date))

print(f"  Dues created for {current_year - 1} and {current_year}")

# ── Bookings ────────────────────────────────────────────────────
today = date.today()
booking_count = 0
active_accounts = [aid for aid in account_ids if aid != 6]  # exclude banned

# Generate bookings for the past 90 days and next 14 days
for day_offset in range(-90, 15):
    booking_date = today + timedelta(days=day_offset)

    # Skip some days randomly (weekdays less busy)
    if booking_date.weekday() < 5:  # Mon-Fri
        num_bookings = random.randint(2, 6)
    else:  # Sat-Sun
        num_bookings = random.randint(5, 10)

    used_slots = set()
    for _ in range(num_bookings):
        aid = random.choice(active_accounts)
        court = random.randint(1, 6)
        hour = random.choice([6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20])
        duration = random.choice([1, 1, 1, 1.5, 2])

        slot_key = (court, hour)
        if slot_key in used_slots:
            continue
        used_slots.add(slot_key)

        start = f"{hour:02d}:00"
        end_hour = int(hour + duration)
        end_min = 30 if duration % 1 else 0
        end = f"{end_hour:02d}:{end_min:02d}"

        guests = random.choices([0, 0, 0, 1, 1, 2, 3], weights=[40, 20, 10, 10, 10, 8, 2])[0]
        notes = random.choice([
            None, None, None, None,
            'Tennis', 'Pickleball', 'Tennis doubles', 'Pickleball league',
            'Practice session', 'Coaching session', 'Tournament prep',
        ])

        is_cancelled = 1 if random.random() < 0.05 else 0  # 5% cancelled

        cursor.execute('''
            INSERT INTO bookings (account_id, court_id, booking_date, start_time, end_time,
                                  guest_count, notes, is_cancelled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (aid, court, booking_date.isoformat(), start, end, guests, notes, is_cancelled))
        booking_count += 1

print(f"  {booking_count} bookings created (past 90 days + next 14 days)")

# ── Maintenance Blocks (via MAINTENANCE account) ────────────────
maint_bookings = [
    (3, today - timedelta(days=45), '08:00', '17:00', 'Court resurfacing'),
    (3, today - timedelta(days=44), '08:00', '17:00', 'Court resurfacing'),
    (6, today - timedelta(days=20), '06:00', '18:00', 'Net replacement'),
    (1, today - timedelta(days=10), '12:00', '16:00', 'Line repainting'),
    (5, today + timedelta(days=3), '08:00', '12:00', 'Scheduled inspection'),
    (2, today + timedelta(days=7), '07:00', '15:00', 'Surface repair'),
]

for court, bdate, start, end, reason in maint_bookings:
    cursor.execute('''
        INSERT INTO bookings (account_id, court_id, booking_date, start_time, end_time,
                              guest_count, notes, is_cancelled)
        VALUES (1, ?, ?, ?, ?, 0, ?, 0)
    ''', (court, bdate.isoformat(), start, end, reason))

print(f"  {len(maint_bookings)} maintenance blocks created")

conn.commit()
conn.close()

print()
print("Demo data ready. Start the app to see reports populated.")
