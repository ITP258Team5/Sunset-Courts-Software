"""
Sunset Courts Management System (SCMS)
Flask application — Sprint 2 Build
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
from datetime import datetime, date, timedelta
from db import get_db, query_db, execute_db
import csv
import io
import os
import shutil
import glob

app = Flask(__name__)
app.secret_key = 'sunset-courts-kiosk-2026'

DUES_RATE = 150.00

# Maintenance blocks are handled via a protected MAINTENANCE account (account_id=1).
# An alternative approach using a separate maintenance_blocks table with dedicated CRUD
# routes was considered, but this method reuses existing booking infrastructure —
# conflict detection, calendar display, and cancellation all work automatically
# without additional code or templates.
MAINTENANCE_ACCOUNT_ID = 1


# ═══════════════════════════════════════════════════════════════════
#  FILTERS & GLOBALS
# ═══════════════════════════════════════════════════════════════════

@app.template_filter('usdate')
def us_date_filter(value):
    if not value:
        return ''
    try:
        d = datetime.strptime(str(value), '%Y-%m-%d')
        return d.strftime('%m/%d/%Y')
    except (ValueError, TypeError):
        return str(value)


@app.template_filter('ustime')
def us_time_filter(value):
    if not value:
        return ''
    try:
        t = datetime.strptime(str(value).strip(), '%H:%M')
        return t.strftime('%-I:%M %p')
    except (ValueError, TypeError):
        return str(value)


@app.context_processor
def inject_globals():
    now = datetime.now()
    return {
        'today_display': now.strftime('%a %m/%d/%Y  %-I:%M %p'),
        'DUES_RATE': DUES_RATE,
        'MAINTENANCE_ACCOUNT_ID': MAINTENANCE_ACCOUNT_ID,
        'current_year': now.year
    }


# ═══════════════════════════════════════════════════════════════════
#  TIME VERIFICATION (runs before every request)
# ═══════════════════════════════════════════════════════════════════

@app.before_request
def check_time_verified():
    allowed = ['verify_time', 'static', 'exit_kiosk', 'admin_reopen', 'launch_kiosk']
    if request.endpoint in allowed:
        return
    if not session.get('time_verified'):
        return redirect(url_for('verify_time'))


@app.route('/verify-time', methods=['GET', 'POST'])
def verify_time():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'confirm':
            session['time_verified'] = True
            _check_dues_reset()
            return redirect(url_for('dashboard'))
        elif action == 'set':
            new_date = request.form.get('new_date', '')
            new_time = request.form.get('new_time', '')
            if new_date and new_time:
                try:
                    import subprocess
                    dt_str = f"{new_date} {new_time}:00"
                    subprocess.run(['sudo', 'date', '-s', dt_str],
                                   capture_output=True, timeout=5)
                except Exception:
                    flash('Could not set system time. Continuing with current time.', 'warning')
                session['time_verified'] = True
                _check_dues_reset()
                return redirect(url_for('dashboard'))

    now = datetime.now()
    return render_template('verify_time.html',
                           current_date=now.strftime('%Y-%m-%d'),
                           current_time=now.strftime('%H:%M'),
                           current_display=now.strftime('%A, %B %d, %Y  %-I:%M %p'))


def _check_dues_reset():
    """Check if the year has rolled over since last launch. If so, create
    unpaid dues records for all accounts for the new year."""
    current_year = date.today().year

    last = query_db("SELECT value FROM system_config WHERE key = 'last_launch_year'", one=True)
    last_year = int(last['value']) if last else None

    if last_year is None:
        # First launch — just record the year
        execute_db("INSERT OR REPLACE INTO system_config (key, value) VALUES ('last_launch_year', ?)",
                   (str(current_year),))
        return

    if current_year > last_year:
        # Year rolled over — create unpaid dues for all non-maintenance accounts
        accounts = query_db('SELECT account_id FROM accounts WHERE account_id != ?',
                            (MAINTENANCE_ACCOUNT_ID,))
        count = 0
        for acct in accounts:
            existing = query_db('SELECT * FROM dues WHERE account_id = ? AND year = ?',
                                (acct['account_id'], current_year), one=True)
            if not existing:
                execute_db('''
                    INSERT INTO dues (account_id, year, is_paid, amount_paid, total_due)
                    VALUES (?, ?, 0, 0.0, ?)
                ''', (acct['account_id'], current_year, DUES_RATE))
                count += 1

        if count > 0:
            flash(f'New year detected. {count} account(s) have been reset to unpaid for {current_year}.', 'warning')

        execute_db("INSERT OR REPLACE INTO system_config (key, value) VALUES ('last_launch_year', ?)",
                   (str(current_year),))


# ═══════════════════════════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════════════════════════

@app.route('/')
def dashboard():
    today = date.today().isoformat()
    now_time = datetime.now().strftime('%H:%M')

    todays_bookings = query_db('''
        SELECT b.*, a.account_name, c.court_name
        FROM bookings b
        JOIN accounts a ON b.account_id = a.account_id
        JOIN courts c ON b.court_id = c.court_id
        WHERE b.booking_date = ? AND b.is_cancelled = 0
        ORDER BY b.start_time, c.court_name
    ''', (today,))

    courts = query_db('SELECT * FROM courts ORDER BY court_id')
    court_status = []
    for court in courts:
        current_booking = query_db('''
            SELECT b.*, a.account_name FROM bookings b
            JOIN accounts a ON b.account_id = a.account_id
            WHERE b.court_id = ? AND b.booking_date = ? AND b.is_cancelled = 0
            AND b.start_time <= ? AND b.end_time > ?
        ''', (court['court_id'], today, now_time, now_time), one=True)

        if current_booking:
            if current_booking['account_id'] == MAINTENANCE_ACCOUNT_ID:
                status = 'maint'
                detail = current_booking['notes'] or 'Maintenance'
            else:
                status = 'busy'
                detail = f"Until {us_time_filter(current_booking['end_time'])}"
        else:
            status = 'open'
            detail = 'Available now'

        court_status.append({'court': court, 'status': status, 'detail': detail})

    total_accounts = query_db(
        'SELECT COUNT(*) as cnt FROM accounts WHERE account_id != ?',
        (MAINTENANCE_ACCOUNT_ID,), one=True)['cnt']
    current_year = date.today().year
    dues_unpaid = query_db('''
        SELECT COUNT(*) as cnt FROM accounts a
        LEFT JOIN dues d ON a.account_id = d.account_id AND d.year = ?
        WHERE a.account_id != ? AND COALESCE(d.is_paid, 0) = 0
    ''', (current_year, MAINTENANCE_ACCOUNT_ID), one=True)['cnt']
    today_booking_count = len(todays_bookings)
    open_courts = sum(1 for cs in court_status if cs['status'] == 'open')

    return render_template('dashboard.html',
                           todays_bookings=todays_bookings,
                           court_status=court_status,
                           open_courts=open_courts,
                           today_booking_count=today_booking_count,
                           dues_unpaid=dues_unpaid,
                           total_accounts=total_accounts,
                           today=today)


# ═══════════════════════════════════════════════════════════════════
#  ACCOUNT DIRECTORY
# ═══════════════════════════════════════════════════════════════════

@app.route('/accounts')
def account_list():
    search = request.args.get('search', '').strip()
    if search:
        accounts = query_db('''
            SELECT a.*, d.is_paid as dues_paid, d.amount_paid, d.total_due
            FROM accounts a
            LEFT JOIN dues d ON a.account_id = d.account_id AND d.year = ?
            WHERE a.account_id != ? AND (
                a.account_name LIKE ? OR a.primary_contact LIKE ?
                OR a.phone LIKE ? OR a.join_date LIKE ?
            )
            ORDER BY a.account_name
        ''', (date.today().year, MAINTENANCE_ACCOUNT_ID,
              f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%'))
    else:
        accounts = query_db('''
            SELECT a.*, d.is_paid as dues_paid, d.amount_paid, d.total_due
            FROM accounts a
            LEFT JOIN dues d ON a.account_id = d.account_id AND d.year = ?
            WHERE a.account_id != ?
            ORDER BY a.account_name
        ''', (date.today().year, MAINTENANCE_ACCOUNT_ID))
    return render_template('accounts/list.html', accounts=accounts, search=search)


@app.route('/accounts/add', methods=['GET', 'POST'])
def account_add():
    if request.method == 'POST':
        account_name = request.form.get('account_name', '').strip()
        primary_contact = request.form.get('primary_contact', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        join_date = request.form.get('join_date', date.today().isoformat())
        notes = request.form.get('notes', '').strip()

        if not account_name:
            flash('Account name is required.', 'error')
            return render_template('accounts/form.html', mode='add', account=request.form)

        account_id = execute_db('''
            INSERT INTO accounts (account_name, primary_contact, phone, email, join_date, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (account_name, primary_contact, phone, email, join_date, notes or None))

        execute_db('INSERT OR IGNORE INTO dues (account_id, year, total_due) VALUES (?, ?, ?)',
                   (account_id, date.today().year, DUES_RATE))

        flash(f'{account_name} has been added.', 'success')
        return redirect(url_for('account_list'))

    return render_template('accounts/form.html', mode='add', account={})


@app.route('/accounts/<int:account_id>/edit', methods=['GET', 'POST'])
def account_edit(account_id):
    account = query_db('SELECT * FROM accounts WHERE account_id = ?', (account_id,), one=True)
    if not account:
        flash('Account not found.', 'error')
        return redirect(url_for('account_list'))

    if request.method == 'POST':
        account_name = request.form.get('account_name', '').strip()
        if not account_name:
            flash('Account name is required.', 'error')
            return render_template('accounts/form.html', mode='edit',
                                   account=request.form, account_id=account_id)

        execute_db('''
            UPDATE accounts SET account_name=?, primary_contact=?, phone=?, email=?, notes=?
            WHERE account_id=?
        ''', (account_name,
              request.form.get('primary_contact','').strip(),
              request.form.get('phone','').strip(),
              request.form.get('email','').strip(),
              request.form.get('notes','').strip() or None,
              account_id))

        flash(f'{account_name} updated.', 'success')
        return redirect(url_for('account_list'))

    return render_template('accounts/form.html', mode='edit', account=account, account_id=account_id)


@app.route('/accounts/<int:account_id>/view')
def account_view(account_id):
    account = query_db('SELECT * FROM accounts WHERE account_id = ?', (account_id,), one=True)
    if not account:
        flash('Account not found.', 'error')
        return redirect(url_for('account_list'))

    dues = query_db('SELECT * FROM dues WHERE account_id = ? ORDER BY year DESC', (account_id,))
    bookings = query_db('''
        SELECT b.*, c.court_name FROM bookings b
        JOIN courts c ON b.court_id = c.court_id
        WHERE b.account_id = ? ORDER BY b.booking_date DESC, b.start_time DESC LIMIT 20
    ''', (account_id,))

    return render_template('accounts/view.html', account=account, dues=dues, bookings=bookings)


@app.route('/accounts/<int:account_id>/delete', methods=['POST'])
def account_delete(account_id):
    account = query_db('SELECT * FROM accounts WHERE account_id = ?', (account_id,), one=True)
    if not account:
        flash('Account not found.', 'error')
        return redirect(url_for('account_list'))

    if account['is_protected']:
        flash('This is a protected system account and cannot be deleted.', 'error')
        return redirect(url_for('account_list'))

    name = account['account_name']
    execute_db('DELETE FROM accounts WHERE account_id = ?', (account_id,))
    flash(f'{name} has been deleted.', 'success')
    return redirect(url_for('account_list'))


# ═══════════════════════════════════════════════════════════════════
#  BAN / UNBAN
# ═══════════════════════════════════════════════════════════════════

@app.route('/accounts/<int:account_id>/ban', methods=['POST'])
def account_ban(account_id):
    account = query_db('SELECT * FROM accounts WHERE account_id = ?', (account_id,), one=True)
    if not account:
        flash('Account not found.', 'error')
        return redirect(url_for('account_list'))

    if account['is_protected']:
        flash('This is a protected system account and cannot be banned.', 'error')
        return redirect(url_for('account_list'))

    execute_db('UPDATE accounts SET is_banned = 1 WHERE account_id = ?', (account_id,))

    future = query_db('''
        SELECT b.*, c.court_name FROM bookings b
        JOIN courts c ON b.court_id = c.court_id
        WHERE b.account_id = ? AND b.booking_date >= ? AND b.is_cancelled = 0
        ORDER BY b.booking_date, b.start_time
    ''', (account_id, date.today().isoformat()))

    flash(f'{account["account_name"]} has been BANNED. {len(future)} future booking(s) to review.', 'warning')

    if future:
        return render_template('accounts/ban_review.html', account=account, bookings=future)
    return redirect(url_for('account_list'))


@app.route('/accounts/<int:account_id>/unban', methods=['POST'])
def account_unban(account_id):
    execute_db('UPDATE accounts SET is_banned = 0 WHERE account_id = ?', (account_id,))
    account = query_db('SELECT account_name FROM accounts WHERE account_id = ?', (account_id,), one=True)
    flash(f'{account["account_name"]} ban lifted.', 'success')
    return redirect(url_for('account_list'))


# ═══════════════════════════════════════════════════════════════════
#  BOOKINGS
# ═══════════════════════════════════════════════════════════════════

@app.route('/bookings')
def booking_calendar():
    view_date = request.args.get('date', date.today().isoformat())
    try:
        current_date = datetime.strptime(view_date, '%Y-%m-%d').date()
    except ValueError:
        current_date = date.today()

    prev_date = (current_date - timedelta(days=1)).isoformat()
    next_date = (current_date + timedelta(days=1)).isoformat()

    courts = query_db('SELECT * FROM courts ORDER BY court_id')
    bookings = query_db('''
        SELECT b.*, a.account_name, a.is_banned, a.account_id as acct_id, c.court_name
        FROM bookings b
        JOIN accounts a ON b.account_id = a.account_id
        JOIN courts c ON b.court_id = c.court_id
        WHERE b.booking_date = ? AND b.is_cancelled = 0
        ORDER BY c.court_id, b.start_time
    ''', (current_date.isoformat(),))

    court_bookings = {c['court_id']: [] for c in courts}
    for b in bookings:
        court_bookings[b['court_id']].append(b)

    return render_template('bookings/calendar.html',
                           courts=courts, court_bookings=court_bookings,
                           current_date=current_date,
                           prev_date=prev_date, next_date=next_date)


@app.route('/bookings/add', methods=['GET', 'POST'])
def booking_add():
    if request.method == 'POST':
        account_id = request.form.get('account_id', type=int)
        court_id = request.form.get('court_id', type=int)
        booking_date = request.form.get('booking_date', '')
        start_time = request.form.get('start_time', '')
        end_time = request.form.get('end_time', '')
        guest_count = request.form.get('guest_count', 0, type=int)
        notes = request.form.get('notes', '').strip()

        errors = []
        if not all([account_id, court_id, booking_date, start_time, end_time]):
            errors.append('All fields are required.')

        if account_id:
            acct = query_db('SELECT * FROM accounts WHERE account_id = ?', (account_id,), one=True)
            if not acct:
                errors.append('Account not found.')
            elif acct['is_banned']:
                errors.append(f'{acct["account_name"]} is BANNED and cannot book.')

        if booking_date:
            try:
                bd = datetime.strptime(booking_date, '%Y-%m-%d').date()
                if bd > date.today() + timedelta(days=365):
                    errors.append('Bookings cannot exceed 365 days in advance.')
                if bd < date.today():
                    errors.append('Cannot book in the past.')
            except ValueError:
                errors.append('Invalid date.')

        if start_time and end_time and start_time >= end_time:
            errors.append('End time must be after start time.')

        if not errors and court_id and booking_date and start_time and end_time:
            conflict = query_db('''
                SELECT b.*, a.account_name FROM bookings b
                JOIN accounts a ON b.account_id = a.account_id
                WHERE b.court_id = ? AND b.booking_date = ? AND b.is_cancelled = 0
                AND b.start_time < ? AND b.end_time > ?
            ''', (court_id, booking_date, end_time, start_time))
            if conflict:
                names = ', '.join([c['account_name'] for c in conflict])
                errors.append(f'Time conflict with: {names}')

        if guest_count > 2 and account_id != MAINTENANCE_ACCOUNT_ID:
            flash('Note: Guest limit is 2 per visit. Booking exceeds recommended limit.', 'warning')

        if errors:
            for e in errors:
                flash(e, 'error')
            accounts = query_db(
                'SELECT * FROM accounts WHERE is_banned = 0 ORDER BY account_name')
            courts = query_db('SELECT * FROM courts ORDER BY court_id')
            return render_template('bookings/form.html', mode='add',
                                   accounts=accounts, courts=courts, booking=request.form)

        execute_db('''
            INSERT INTO bookings (account_id, court_id, booking_date, start_time, end_time, guest_count, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (account_id, court_id, booking_date, start_time, end_time, guest_count, notes or None))

        flash('Booking created.', 'success')
        return redirect(url_for('booking_calendar', date=booking_date))

    accounts = query_db('SELECT * FROM accounts WHERE is_banned = 0 ORDER BY account_name')
    courts = query_db('SELECT * FROM courts ORDER BY court_id')
    prefill = {
        'booking_date': request.args.get('date', date.today().isoformat()),
        'court_id': request.args.get('court', ''),
        'start_time': request.args.get('time', ''),
    }
    return render_template('bookings/form.html', mode='add',
                           accounts=accounts, courts=courts, booking=prefill)


@app.route('/bookings/<int:booking_id>/cancel', methods=['POST'])
def booking_cancel(booking_id):
    booking = query_db('SELECT * FROM bookings WHERE booking_id = ?', (booking_id,), one=True)
    if not booking:
        flash('Booking not found.', 'error')
        return redirect(url_for('booking_calendar'))

    execute_db('UPDATE bookings SET is_cancelled = 1 WHERE booking_id = ?', (booking_id,))
    flash('Booking cancelled.', 'success')
    return redirect(url_for('booking_calendar', date=booking['booking_date']))


@app.route('/bookings/<int:booking_id>')
def booking_view(booking_id):
    booking = query_db('''
        SELECT b.*, a.account_name, a.is_banned, a.account_id as acct_id, c.court_name
        FROM bookings b
        JOIN accounts a ON b.account_id = a.account_id
        JOIN courts c ON b.court_id = c.court_id
        WHERE b.booking_id = ?
    ''', (booking_id,), one=True)
    if not booking:
        flash('Booking not found.', 'error')
        return redirect(url_for('booking_calendar'))
    return render_template('bookings/view.html', booking=booking)


# ═══════════════════════════════════════════════════════════════════
#  DUES
# ═══════════════════════════════════════════════════════════════════

@app.route('/dues')
def dues_list():
    current_year = request.args.get('year', date.today().year, type=int)
    dues = query_db('''
        SELECT a.account_id, a.account_name, a.is_banned,
               d.due_id, d.is_paid, d.amount_paid, d.total_due, d.date_paid, d.notes as dues_notes
        FROM accounts a
        LEFT JOIN dues d ON a.account_id = d.account_id AND d.year = ?
        WHERE a.account_id != ?
        ORDER BY a.account_name
    ''', (current_year, MAINTENANCE_ACCOUNT_ID))
    return render_template('dues/list.html', dues=dues, current_year=current_year)


@app.route('/dues/<int:account_id>/pay', methods=['POST'])
def dues_pay(account_id):
    year = request.form.get('year', date.today().year, type=int)
    amount = request.form.get('amount', 0.0, type=float)
    total = request.form.get('total', DUES_RATE, type=float)
    notes = request.form.get('notes', '').strip()

    is_paid = 1 if amount >= total else 0

    existing = query_db('SELECT * FROM dues WHERE account_id = ? AND year = ?', (account_id, year), one=True)
    if existing:
        execute_db('''
            UPDATE dues SET is_paid=?, amount_paid=?, total_due=?, date_paid=?, notes=?
            WHERE account_id=? AND year=?
        ''', (is_paid, amount, total, date.today().isoformat(), notes or None, account_id, year))
    else:
        execute_db('''
            INSERT INTO dues (account_id, year, is_paid, amount_paid, total_due, date_paid, notes)
            VALUES (?,?,?,?,?,?,?)
        ''', (account_id, year, is_paid, amount, total, date.today().isoformat(), notes or None))

    if is_paid:
        flash('Dues recorded as paid in full.', 'success')
    else:
        flash(f'Partial payment of ${amount:.2f} recorded.', 'success')
    return redirect(url_for('dues_list', year=year))


@app.route('/dues/<int:account_id>/unpay', methods=['POST'])
def dues_unpay(account_id):
    year = request.form.get('year', date.today().year, type=int)
    execute_db('UPDATE dues SET is_paid=0, amount_paid=0, date_paid=NULL WHERE account_id=? AND year=?',
               (account_id, year))
    flash('Dues marked unpaid.', 'success')
    return redirect(url_for('dues_list', year=year))


# ═══════════════════════════════════════════════════════════════════
#  REPORTS
# ═══════════════════════════════════════════════════════════════════

@app.route('/reports')
def reports_home():
    return render_template('reports/home.html')


@app.route('/reports/monthly')
def report_monthly():
    year = request.args.get('year', date.today().year, type=int)
    month = request.args.get('month', date.today().month, type=int)

    total = query_db('''
        SELECT COUNT(*) as cnt FROM bookings
        WHERE strftime('%Y', booking_date) = ? AND strftime('%m', booking_date) = ?
        AND is_cancelled = 0 AND account_id != ?
    ''', (str(year), f'{month:02d}', MAINTENANCE_ACCOUNT_ID), one=True)['cnt']

    by_member = query_db('''
        SELECT a.account_name, COUNT(*) as cnt FROM bookings b
        JOIN accounts a ON b.account_id = a.account_id
        WHERE strftime('%Y', b.booking_date) = ? AND strftime('%m', b.booking_date) = ?
        AND b.is_cancelled = 0 AND b.account_id != ?
        GROUP BY a.account_id ORDER BY cnt DESC
    ''', (str(year), f'{month:02d}', MAINTENANCE_ACCOUNT_ID))

    by_court = query_db('''
        SELECT c.court_name, COUNT(*) as cnt FROM bookings b
        JOIN courts c ON b.court_id = c.court_id
        WHERE strftime('%Y', b.booking_date) = ? AND strftime('%m', b.booking_date) = ?
        AND b.is_cancelled = 0 AND b.account_id != ?
        GROUP BY c.court_id ORDER BY c.court_name
    ''', (str(year), f'{month:02d}', MAINTENANCE_ACCOUNT_ID))

    return render_template('reports/monthly.html', total=total,
                           by_member=by_member, by_court=by_court, year=year, month=month)


@app.route('/reports/peak')
def report_peak():
    year = request.args.get('year', date.today().year, type=int)

    by_hour = query_db('''
        SELECT CAST(substr(start_time, 1, 2) AS INTEGER) as hour, COUNT(*) as cnt
        FROM bookings WHERE strftime('%Y', booking_date) = ? AND is_cancelled = 0
        AND account_id != ?
        GROUP BY hour ORDER BY hour
    ''', (str(year), MAINTENANCE_ACCOUNT_ID))

    by_day = query_db('''
        SELECT CAST(strftime('%w', booking_date) AS INTEGER) as dow, COUNT(*) as cnt
        FROM bookings WHERE strftime('%Y', booking_date) = ? AND is_cancelled = 0
        AND account_id != ?
        GROUP BY dow ORDER BY dow
    ''', (str(year), MAINTENANCE_ACCOUNT_ID))

    day_names = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']
    return render_template('reports/peak.html', by_hour=by_hour, by_day=by_day,
                           day_names=day_names, year=year)


@app.route('/reports/yearly')
def report_yearly():
    year = request.args.get('year', date.today().year, type=int)

    total = query_db('''
        SELECT COUNT(*) as cnt FROM bookings
        WHERE strftime('%Y', booking_date) = ? AND is_cancelled = 0 AND account_id != ?
    ''', (str(year), MAINTENANCE_ACCOUNT_ID), one=True)['cnt']

    by_member = query_db('''
        SELECT a.account_name, COUNT(*) as cnt FROM bookings b
        JOIN accounts a ON b.account_id = a.account_id
        WHERE strftime('%Y', b.booking_date) = ? AND b.is_cancelled = 0 AND b.account_id != ?
        GROUP BY a.account_id ORDER BY cnt DESC
    ''', (str(year), MAINTENANCE_ACCOUNT_ID))

    by_court = query_db('''
        SELECT c.court_name, COUNT(*) as cnt FROM bookings b
        JOIN courts c ON b.court_id = c.court_id
        WHERE strftime('%Y', b.booking_date) = ? AND b.is_cancelled = 0 AND b.account_id != ?
        GROUP BY c.court_id ORDER BY c.court_name
    ''', (str(year), MAINTENANCE_ACCOUNT_ID))

    # Maintenance bookings count as maintenance blocks
    maint = query_db('''
        SELECT c.court_name, COUNT(*) as cnt FROM bookings b
        JOIN courts c ON b.court_id = c.court_id
        WHERE strftime('%Y', b.booking_date) = ? AND b.is_cancelled = 0
        AND b.account_id = ?
        GROUP BY c.court_id ORDER BY c.court_name
    ''', (str(year), MAINTENANCE_ACCOUNT_ID))

    return render_template('reports/yearly.html', total_bookings=total,
                           by_member=by_member, by_court=by_court,
                           maintenance_by_court=maint, year=year)


@app.route('/reports/guests')
def report_guests():
    year = request.args.get('year', date.today().year, type=int)
    report = query_db('''
        SELECT a.account_name, SUM(b.guest_count) as total_guests,
               COUNT(CASE WHEN b.guest_count > 0 THEN 1 END) as visits_with_guests
        FROM bookings b JOIN accounts a ON b.account_id = a.account_id
        WHERE strftime('%Y', b.booking_date) = ? AND b.is_cancelled = 0
        AND b.guest_count > 0 AND b.account_id != ?
        GROUP BY a.account_id ORDER BY total_guests DESC
    ''', (str(year), MAINTENANCE_ACCOUNT_ID))
    return render_template('reports/guests.html', guest_report=report, year=year)


@app.route('/reports/dues')
def report_dues_status():
    year = request.args.get('year', date.today().year, type=int)
    report = query_db('''
        SELECT a.account_name, a.is_banned, COALESCE(d.is_paid, 0) as is_paid,
               d.amount_paid, d.total_due, d.date_paid
        FROM accounts a
        LEFT JOIN dues d ON a.account_id = d.account_id AND d.year = ?
        WHERE a.account_id != ?
        ORDER BY COALESCE(d.is_paid, 0), a.account_name
    ''', (year, MAINTENANCE_ACCOUNT_ID))
    paid = sum(1 for r in report if r['is_paid'])
    return render_template('reports/dues_status.html', dues_report=report, year=year,
                           paid_count=paid, unpaid_count=len(report) - paid)


# ═══════════════════════════════════════════════════════════════════
#  DATA EXPORT & BACKUP
# ═══════════════════════════════════════════════════════════════════

APP_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_DIR = os.path.join(APP_DIR, 'backups')


def _detect_usb():
    """Find mounted USB drives. Returns list of mount paths."""
    usb_paths = []
    media_base = '/media'
    if os.path.exists(media_base):
        for user_dir in os.listdir(media_base):
            user_path = os.path.join(media_base, user_dir)
            if os.path.isdir(user_path):
                for drive in os.listdir(user_path):
                    drive_path = os.path.join(user_path, drive)
                    if os.path.ismount(drive_path):
                        usb_paths.append(drive_path)
    return usb_paths


def _create_backup(destination=None):
    """Create a dated backup of the database. Returns the backup path."""
    db_path = os.path.join(APP_DIR, 'sunset_courts.db')
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M')
    filename = f'sunset_courts_backup_{timestamp}.db'

    if destination:
        backup_path = os.path.join(destination, filename)
    else:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        backup_path = os.path.join(BACKUP_DIR, filename)

    shutil.copy2(db_path, backup_path)
    return backup_path


def _cleanup_old_backups(keep=8):
    """Keep only the most recent backups in the local backup folder."""
    if not os.path.exists(BACKUP_DIR):
        return
    backups = sorted(glob.glob(os.path.join(BACKUP_DIR, 'sunset_courts_backup_*.db')))
    while len(backups) > keep:
        os.remove(backups.pop(0))


def _get_local_backups():
    """List existing local backups, newest first."""
    if not os.path.exists(BACKUP_DIR):
        return []
    backups = sorted(glob.glob(os.path.join(BACKUP_DIR, 'sunset_courts_backup_*.db')), reverse=True)
    result = []
    for b in backups:
        stat = os.stat(b)
        result.append({
            'filename': os.path.basename(b),
            'size_kb': round(stat.st_size / 1024),
            'date': datetime.fromtimestamp(stat.st_mtime).strftime('%m/%d/%Y %-I:%M %p')
        })
    return result


@app.route('/export')
def export_home():
    usb_drives = _detect_usb()
    local_backups = _get_local_backups()
    return render_template('export.html', usb_drives=usb_drives, local_backups=local_backups)


@app.route('/export/backup', methods=['POST'])
def export_backup():
    target = request.form.get('target', 'local')

    if target == 'usb':
        usb_drives = _detect_usb()
        if not usb_drives:
            flash('No USB drive detected. Please insert a USB drive and try again.', 'error')
            return redirect(url_for('export_home'))

        usb_path = usb_drives[0]
        try:
            # Create backup folder on USB
            usb_backup_dir = os.path.join(usb_path, 'SunsetCourts_Backups')
            os.makedirs(usb_backup_dir, exist_ok=True)

            # Copy database
            backup_path = _create_backup(usb_backup_dir)

            # Also generate CSVs to USB
            year = date.today().year
            _export_csv_to_dir(usb_backup_dir, year)

            drive_name = os.path.basename(usb_path)
            flash(f'Backup saved to USB drive ({drive_name}). Database and CSV files exported.', 'success')
        except PermissionError:
            flash('Cannot write to USB drive. The drive may be read-only.', 'error')
        except Exception as e:
            flash(f'Backup failed: {str(e)}', 'error')
    else:
        _create_backup()
        _cleanup_old_backups()
        flash('Backup saved locally.', 'success')

    return redirect(url_for('export_home'))


def _export_csv_to_dir(directory, year):
    """Write all CSV exports directly to a directory."""
    timestamp = datetime.now().strftime('%Y-%m-%d')

    # Accounts
    accounts = query_db('''
        SELECT account_name, primary_contact, phone, email, join_date, is_banned, notes
        FROM accounts WHERE account_id != ? ORDER BY account_name
    ''', (MAINTENANCE_ACCOUNT_ID,))
    with open(os.path.join(directory, f'accounts_{timestamp}.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Account Name', 'Primary Contact', 'Phone', 'Email', 'Join Date', 'Banned', 'Notes'])
        for a in accounts:
            w.writerow([a['account_name'], a['primary_contact'] or '', a['phone'] or '',
                        a['email'] or '', a['join_date'], 'Yes' if a['is_banned'] else 'No', a['notes'] or ''])

    # Bookings
    bookings = query_db('''
        SELECT a.account_name, c.court_name, b.booking_date, b.start_time, b.end_time,
               b.guest_count, b.notes, b.is_cancelled
        FROM bookings b JOIN accounts a ON b.account_id = a.account_id
        JOIN courts c ON b.court_id = c.court_id
        WHERE strftime('%Y', b.booking_date) = ? AND b.account_id != ?
        ORDER BY b.booking_date, b.start_time
    ''', (str(year), MAINTENANCE_ACCOUNT_ID))
    with open(os.path.join(directory, f'bookings_{year}.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Account', 'Court', 'Date', 'Start Time', 'End Time', 'Guests', 'Notes', 'Cancelled'])
        for b in bookings:
            w.writerow([b['account_name'], b['court_name'], b['booking_date'],
                        b['start_time'], b['end_time'], b['guest_count'], b['notes'] or '',
                        'Yes' if b['is_cancelled'] else 'No'])

    # Dues
    dues = query_db('''
        SELECT a.account_name, d.year, d.is_paid, d.amount_paid, d.total_due, d.date_paid, d.notes
        FROM accounts a LEFT JOIN dues d ON a.account_id = d.account_id AND d.year = ?
        WHERE a.account_id != ? ORDER BY a.account_name
    ''', (year, MAINTENANCE_ACCOUNT_ID))
    with open(os.path.join(directory, f'dues_{year}.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Account', 'Year', 'Paid', 'Amount Paid', 'Total Due', 'Date Paid', 'Notes'])
        for d in dues:
            w.writerow([d['account_name'], d['year'] or year, 'Yes' if d['is_paid'] else 'No',
                        f"{d['amount_paid'] or 0:.2f}", f"{d['total_due'] or DUES_RATE:.2f}",
                        d['date_paid'] or '', d['notes'] or ''])


# Individual CSV downloads (kept for direct download use)

@app.route('/export/accounts')
def export_accounts():
    accounts = query_db('''
        SELECT account_name, primary_contact, phone, email, join_date, is_banned, notes
        FROM accounts WHERE account_id != ?
        ORDER BY account_name
    ''', (MAINTENANCE_ACCOUNT_ID,))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Account Name', 'Primary Contact', 'Phone', 'Email', 'Join Date', 'Banned', 'Notes'])
    for a in accounts:
        writer.writerow([
            a['account_name'], a['primary_contact'] or '', a['phone'] or '',
            a['email'] or '', a['join_date'], 'Yes' if a['is_banned'] else 'No',
            a['notes'] or ''
        ])

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=accounts_{date.today().isoformat()}.csv'}
    )


@app.route('/export/bookings')
def export_bookings():
    year = request.args.get('year', date.today().year, type=int)
    bookings = query_db('''
        SELECT a.account_name, c.court_name, b.booking_date, b.start_time, b.end_time,
               b.guest_count, b.notes, b.is_cancelled
        FROM bookings b
        JOIN accounts a ON b.account_id = a.account_id
        JOIN courts c ON b.court_id = c.court_id
        WHERE strftime('%Y', b.booking_date) = ? AND b.account_id != ?
        ORDER BY b.booking_date, b.start_time
    ''', (str(year), MAINTENANCE_ACCOUNT_ID))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Account', 'Court', 'Date', 'Start Time', 'End Time', 'Guests', 'Notes', 'Cancelled'])
    for b in bookings:
        writer.writerow([
            b['account_name'], b['court_name'], b['booking_date'],
            b['start_time'], b['end_time'], b['guest_count'],
            b['notes'] or '', 'Yes' if b['is_cancelled'] else 'No'
        ])

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=bookings_{year}.csv'}
    )


@app.route('/export/dues')
def export_dues():
    year = request.args.get('year', date.today().year, type=int)
    dues = query_db('''
        SELECT a.account_name, d.year, d.is_paid, d.amount_paid, d.total_due, d.date_paid, d.notes
        FROM accounts a
        LEFT JOIN dues d ON a.account_id = d.account_id AND d.year = ?
        WHERE a.account_id != ?
        ORDER BY a.account_name
    ''', (year, MAINTENANCE_ACCOUNT_ID))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Account', 'Year', 'Paid', 'Amount Paid', 'Total Due', 'Date Paid', 'Notes'])
    for d in dues:
        writer.writerow([
            d['account_name'], d['year'] or year,
            'Yes' if d['is_paid'] else 'No',
            f"{d['amount_paid'] or 0:.2f}",
            f"{d['total_due'] or DUES_RATE:.2f}",
            d['date_paid'] or '', d['notes'] or ''
        ])

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=dues_{year}.csv'}
    )


@app.route('/export/maintenance')
def export_maintenance():
    year = request.args.get('year', date.today().year, type=int)
    maint = query_db('''
        SELECT c.court_name, b.booking_date, b.start_time, b.end_time, b.notes
        FROM bookings b
        JOIN courts c ON b.court_id = c.court_id
        WHERE b.account_id = ? AND b.is_cancelled = 0
        AND strftime('%Y', b.booking_date) = ?
        ORDER BY b.booking_date, b.start_time
    ''', (MAINTENANCE_ACCOUNT_ID, str(year)))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Court', 'Date', 'Start Time', 'End Time', 'Reason'])
    for m in maint:
        writer.writerow([
            m['court_name'], m['booking_date'], m['start_time'],
            m['end_time'], m['notes'] or ''
        ])

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=maintenance_{year}.csv'}
    )


# ═══════════════════════════════════════════════════════════════════
#  ADMIN
# ═══════════════════════════════════════════════════════════════════

@app.route('/admin/exit-kiosk', methods=['POST'])
def exit_kiosk():
    """Kill kiosk browser, open a small reopen window."""
    import subprocess
    # Kill kiosk chromium
    subprocess.Popen(['pkill', '-f', 'chromium'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # Wait a moment then open a small regular window to the reopen page
    subprocess.Popen(
        ['bash', '-c', 'sleep 1 && chromium --app=http://localhost:5000/admin/reopen '
         '--window-size=400,250 --window-position=50,50 '
         '--noerrdialogs --no-first-run 2>/dev/null'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return '', 204


@app.route('/admin/reopen')
def admin_reopen():
    """Small popup page with a button to relaunch kiosk mode."""
    return '''<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<title>Sunset Courts</title>
<style>
  body { font-family: Georgia, serif; background: #fdf6ee; margin: 0;
         display: flex; align-items: center; justify-content: center;
         height: 100vh; text-align: center; }
  .box { padding: 30px; }
  h2 { color: #6a3010; margin-bottom: 8px; font-size: 18px; }
  p { color: #9a7050; font-size: 13px; margin-bottom: 20px; }
  button { background: #c45c1e; color: white; border: none; padding: 14px 32px;
           border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer;
           font-family: inherit; }
  button:hover { background: #a04818; }
</style>
</head><body>
<div class="box">
  <h2>Kiosk Mode Exited</h2>
  <p>The desktop is now accessible.</p>
  <form method="POST" action="/admin/launch-kiosk">
    <button type="submit">Reopen Kiosk</button>
  </form>
</div>
</body></html>'''


@app.route('/admin/launch-kiosk', methods=['POST'])
def launch_kiosk():
    """Relaunch kiosk browser and close the popup."""
    import subprocess
    # Find the browser
    browser = 'chromium'
    subprocess.Popen(
        ['bash', '-c', f'sleep 0.5 && {browser} --kiosk --noerrdialogs '
         '--disable-infobars --no-first-run http://localhost:5000 2>/dev/null'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    # Return a self-closing page
    return '''<!DOCTYPE html>
<html><head>
<title>Reopening...</title>
<style>
  body { font-family: Georgia, serif; background: #fdf6ee; margin: 0;
         display: flex; align-items: center; justify-content: center;
         height: 100vh; text-align: center; }
  p { color: #6a3010; font-size: 16px; }
</style>
<script>setTimeout(function(){ window.close(); }, 2000);</script>
</head><body>
<p>Reopening kiosk...</p>
</body></html>'''


# ═══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
