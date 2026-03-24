"""
Sunset Courts Management System (SCMS)
Flask application — Sprint 2 Build
Offline kiosk running on Raspberry Pi
"""

from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime, date, timedelta
from db import get_db, query_db, execute_db

app = Flask(__name__)
app.secret_key = 'sunset-courts-kiosk-2026'


# ═══════════════════════════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════════════════════════

@app.route('/')
def dashboard():
    today = date.today().isoformat()
    # Today's bookings
    todays_bookings = query_db('''
        SELECT b.*, f.family_name, c.court_name
        FROM bookings b
        JOIN families f ON b.family_id = f.family_id
        JOIN courts c ON b.court_id = c.court_id
        WHERE b.booking_date = ? AND b.is_cancelled = 0
        ORDER BY b.start_time, c.court_name
    ''', (today,))

    # Quick stats
    total_families = query_db('SELECT COUNT(*) as cnt FROM families', one=True)['cnt']
    active_families = query_db(
        'SELECT COUNT(*) as cnt FROM families WHERE is_banned = 0', one=True
    )['cnt']
    current_year = date.today().year
    dues_paid = query_db(
        'SELECT COUNT(*) as cnt FROM dues WHERE year = ? AND is_paid = 1',
        (current_year,), one=True
    )['cnt']
    upcoming_bookings = query_db(
        'SELECT COUNT(*) as cnt FROM bookings WHERE booking_date >= ? AND is_cancelled = 0',
        (today,), one=True
    )['cnt']

    return render_template('dashboard.html',
                           todays_bookings=todays_bookings,
                           total_families=total_families,
                           active_families=active_families,
                           dues_paid=dues_paid,
                           upcoming_bookings=upcoming_bookings,
                           today=today)


# ═══════════════════════════════════════════════════════════════════
#  FAMILY DIRECTORY (CRUD)
# ═══════════════════════════════════════════════════════════════════

@app.route('/members')
def member_list():
    search = request.args.get('search', '').strip()
    if search:
        families = query_db('''
            SELECT f.*, d.is_paid as dues_paid
            FROM families f
            LEFT JOIN dues d ON f.family_id = d.family_id AND d.year = ?
            WHERE f.family_name LIKE ? OR f.primary_contact LIKE ?
            ORDER BY f.family_name
        ''', (date.today().year, f'%{search}%', f'%{search}%'))
    else:
        families = query_db('''
            SELECT f.*, d.is_paid as dues_paid
            FROM families f
            LEFT JOIN dues d ON f.family_id = d.family_id AND d.year = ?
            ORDER BY f.family_name
        ''', (date.today().year,))
    return render_template('members/list.html', families=families, search=search)


@app.route('/members/add', methods=['GET', 'POST'])
def member_add():
    if request.method == 'POST':
        family_name = request.form.get('family_name', '').strip()
        primary_contact = request.form.get('primary_contact', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        join_date = request.form.get('join_date', date.today().isoformat())
        notes = request.form.get('notes', '').strip()

        if not family_name:
            flash('Family name is required.', 'error')
            return render_template('members/form.html', mode='add', family=request.form)

        family_id = execute_db('''
            INSERT INTO families (family_name, primary_contact, phone, email, join_date, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (family_name, primary_contact, phone, email, join_date, notes or None))

        # Create dues record for current year
        execute_db('''
            INSERT OR IGNORE INTO dues (family_id, year, is_paid, amount_paid)
            VALUES (?, ?, 0, 0.0)
        ''', (family_id, date.today().year))

        flash(f'{family_name} has been added successfully.', 'success')
        return redirect(url_for('member_list'))

    return render_template('members/form.html', mode='add', family={})


@app.route('/members/<int:family_id>/edit', methods=['GET', 'POST'])
def member_edit(family_id):
    family = query_db('SELECT * FROM families WHERE family_id = ?', (family_id,), one=True)
    if not family:
        flash('Family account not found.', 'error')
        return redirect(url_for('member_list'))

    if request.method == 'POST':
        family_name = request.form.get('family_name', '').strip()
        primary_contact = request.form.get('primary_contact', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        notes = request.form.get('notes', '').strip()

        if not family_name:
            flash('Family name is required.', 'error')
            return render_template('members/form.html', mode='edit', family=request.form,
                                   family_id=family_id)

        execute_db('''
            UPDATE families
            SET family_name = ?, primary_contact = ?, phone = ?, email = ?, notes = ?
            WHERE family_id = ?
        ''', (family_name, primary_contact, phone, email, notes or None, family_id))

        flash(f'{family_name} has been updated.', 'success')
        return redirect(url_for('member_list'))

    return render_template('members/form.html', mode='edit', family=family, family_id=family_id)


@app.route('/members/<int:family_id>/view')
def member_view(family_id):
    family = query_db('SELECT * FROM families WHERE family_id = ?', (family_id,), one=True)
    if not family:
        flash('Family account not found.', 'error')
        return redirect(url_for('member_list'))

    # Dues history
    dues = query_db('''
        SELECT * FROM dues WHERE family_id = ? ORDER BY year DESC
    ''', (family_id,))

    # Recent & upcoming bookings
    bookings = query_db('''
        SELECT b.*, c.court_name
        FROM bookings b
        JOIN courts c ON b.court_id = c.court_id
        WHERE b.family_id = ?
        ORDER BY b.booking_date DESC, b.start_time DESC
        LIMIT 20
    ''', (family_id,))

    return render_template('members/view.html', family=family, dues=dues, bookings=bookings)


# ═══════════════════════════════════════════════════════════════════
#  BAN / UNBAN
# ═══════════════════════════════════════════════════════════════════

@app.route('/members/<int:family_id>/ban', methods=['POST'])
def member_ban(family_id):
    family = query_db('SELECT * FROM families WHERE family_id = ?', (family_id,), one=True)
    if not family:
        flash('Family account not found.', 'error')
        return redirect(url_for('member_list'))

    execute_db('UPDATE families SET is_banned = 1 WHERE family_id = ?', (family_id,))

    # Get future bookings to display warning
    future_bookings = query_db('''
        SELECT b.*, c.court_name
        FROM bookings b
        JOIN courts c ON b.court_id = c.court_id
        WHERE b.family_id = ? AND b.booking_date >= ? AND b.is_cancelled = 0
        ORDER BY b.booking_date, b.start_time
    ''', (family_id, date.today().isoformat()))

    flash(f'{family["family_name"]} has been BANNED. '
          f'{len(future_bookings)} future booking(s) should be reviewed.', 'warning')

    if future_bookings:
        return render_template('members/ban_review.html',
                               family=family, bookings=future_bookings)

    return redirect(url_for('member_list'))


@app.route('/members/<int:family_id>/unban', methods=['POST'])
def member_unban(family_id):
    execute_db('UPDATE families SET is_banned = 0 WHERE family_id = ?', (family_id,))
    family = query_db('SELECT family_name FROM families WHERE family_id = ?',
                      (family_id,), one=True)
    flash(f'{family["family_name"]} ban has been lifted.', 'success')
    return redirect(url_for('member_list'))


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
        SELECT b.*, f.family_name, f.is_banned, c.court_name
        FROM bookings b
        JOIN families f ON b.family_id = f.family_id
        JOIN courts c ON b.court_id = c.court_id
        WHERE b.booking_date = ? AND b.is_cancelled = 0
        ORDER BY c.court_id, b.start_time
    ''', (current_date.isoformat(),))

    # Group bookings by court
    court_bookings = {}
    for court in courts:
        court_bookings[court['court_id']] = []
    for b in bookings:
        court_bookings[b['court_id']].append(b)

    # Generate time slots (24-hour, every 30 min)
    time_slots = []
    for hour in range(24):
        for minute in [0, 30]:
            time_slots.append(f'{hour:02d}:{minute:02d}')

    return render_template('bookings/calendar.html',
                           courts=courts,
                           court_bookings=court_bookings,
                           current_date=current_date,
                           prev_date=prev_date,
                           next_date=next_date,
                           time_slots=time_slots)


@app.route('/bookings/add', methods=['GET', 'POST'])
def booking_add():
    if request.method == 'POST':
        family_id = request.form.get('family_id', type=int)
        court_id = request.form.get('court_id', type=int)
        booking_date = request.form.get('booking_date', '')
        start_time = request.form.get('start_time', '')
        end_time = request.form.get('end_time', '')
        guest_count = request.form.get('guest_count', 0, type=int)
        notes = request.form.get('notes', '').strip()

        errors = []

        # Validation
        if not all([family_id, court_id, booking_date, start_time, end_time]):
            errors.append('All fields are required.')

        # Check family exists and not banned
        if family_id:
            family = query_db('SELECT * FROM families WHERE family_id = ?',
                              (family_id,), one=True)
            if not family:
                errors.append('Family account not found.')
            elif family['is_banned']:
                errors.append(f'{family["family_name"]} is BANNED and cannot make bookings.')

        # 365-day advance limit
        if booking_date:
            try:
                bd = datetime.strptime(booking_date, '%Y-%m-%d').date()
                max_date = date.today() + timedelta(days=365)
                if bd > max_date:
                    errors.append('Bookings cannot be more than 365 days in advance.')
                if bd < date.today():
                    errors.append('Cannot book in the past.')
            except ValueError:
                errors.append('Invalid date format.')

        # Check time validity
        if start_time and end_time and start_time >= end_time:
            errors.append('End time must be after start time.')

        # Double-booking detection
        if not errors and court_id and booking_date and start_time and end_time:
            conflict = query_db('''
                SELECT b.*, f.family_name
                FROM bookings b
                JOIN families f ON b.family_id = f.family_id
                WHERE b.court_id = ? AND b.booking_date = ? AND b.is_cancelled = 0
                AND b.start_time < ? AND b.end_time > ?
            ''', (court_id, booking_date, end_time, start_time))
            if conflict:
                names = ', '.join([c['family_name'] for c in conflict])
                errors.append(f'Time conflict with existing booking(s): {names}')

        # Guest count soft warning
        if guest_count > 2:
            flash('Note: Guest limit is 2 per visit. This booking exceeds the recommended limit.', 'warning')

        if errors:
            for e in errors:
                flash(e, 'error')
            families = query_db(
                'SELECT * FROM families WHERE is_banned = 0 ORDER BY family_name')
            courts = query_db('SELECT * FROM courts ORDER BY court_id')
            return render_template('bookings/form.html', mode='add',
                                   families=families, courts=courts, booking=request.form)

        execute_db('''
            INSERT INTO bookings (family_id, court_id, booking_date, start_time, end_time,
                                  guest_count, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (family_id, court_id, booking_date, start_time, end_time,
              guest_count, notes or None))

        flash('Booking created successfully.', 'success')
        return redirect(url_for('booking_calendar', date=booking_date))

    # GET — prefill date/time/court from query params
    families = query_db(
        'SELECT * FROM families WHERE is_banned = 0 ORDER BY family_name')
    courts = query_db('SELECT * FROM courts ORDER BY court_id')
    prefill = {
        'booking_date': request.args.get('date', date.today().isoformat()),
        'court_id': request.args.get('court', ''),
        'start_time': request.args.get('time', ''),
    }
    return render_template('bookings/form.html', mode='add',
                           families=families, courts=courts, booking=prefill)


@app.route('/bookings/<int:booking_id>/cancel', methods=['POST'])
def booking_cancel(booking_id):
    booking = query_db('SELECT * FROM bookings WHERE booking_id = ?',
                       (booking_id,), one=True)
    if not booking:
        flash('Booking not found.', 'error')
        return redirect(url_for('booking_calendar'))

    execute_db('UPDATE bookings SET is_cancelled = 1 WHERE booking_id = ?', (booking_id,))
    flash('Booking cancelled.', 'success')
    return redirect(url_for('booking_calendar', date=booking['booking_date']))


@app.route('/bookings/<int:booking_id>')
def booking_view(booking_id):
    booking = query_db('''
        SELECT b.*, f.family_name, f.is_banned, c.court_name
        FROM bookings b
        JOIN families f ON b.family_id = f.family_id
        JOIN courts c ON b.court_id = c.court_id
        WHERE b.booking_id = ?
    ''', (booking_id,), one=True)
    if not booking:
        flash('Booking not found.', 'error')
        return redirect(url_for('booking_calendar'))
    return render_template('bookings/view.html', booking=booking)


# ═══════════════════════════════════════════════════════════════════
#  DUES MANAGEMENT
# ═══════════════════════════════════════════════════════════════════

@app.route('/dues')
def dues_list():
    current_year = request.args.get('year', date.today().year, type=int)
    dues = query_db('''
        SELECT f.family_id, f.family_name, f.is_banned,
               d.due_id, d.is_paid, d.amount_paid, d.date_paid, d.notes as dues_notes
        FROM families f
        LEFT JOIN dues d ON f.family_id = d.family_id AND d.year = ?
        ORDER BY f.family_name
    ''', (current_year,))
    return render_template('dues/list.html', dues=dues, current_year=current_year)


@app.route('/dues/<int:family_id>/pay', methods=['POST'])
def dues_pay(family_id):
    year = request.form.get('year', date.today().year, type=int)
    amount = request.form.get('amount', 0.0, type=float)
    notes = request.form.get('notes', '').strip()

    # Try update existing, else insert
    existing = query_db('SELECT * FROM dues WHERE family_id = ? AND year = ?',
                        (family_id, year), one=True)
    if existing:
        execute_db('''
            UPDATE dues SET is_paid = 1, amount_paid = ?, date_paid = ?, notes = ?
            WHERE family_id = ? AND year = ?
        ''', (amount, date.today().isoformat(), notes or None, family_id, year))
    else:
        execute_db('''
            INSERT INTO dues (family_id, year, is_paid, amount_paid, date_paid, notes)
            VALUES (?, ?, 1, ?, ?, ?)
        ''', (family_id, year, amount, date.today().isoformat(), notes or None))

    flash('Dues recorded as paid.', 'success')
    return redirect(url_for('dues_list', year=year))


@app.route('/dues/<int:family_id>/unpay', methods=['POST'])
def dues_unpay(family_id):
    year = request.form.get('year', date.today().year, type=int)
    execute_db('''
        UPDATE dues SET is_paid = 0, amount_paid = 0, date_paid = NULL
        WHERE family_id = ? AND year = ?
    ''', (family_id, year))
    flash('Dues marked as unpaid.', 'success')
    return redirect(url_for('dues_list', year=year))


# ═══════════════════════════════════════════════════════════════════
#  REPORTS
# ═══════════════════════════════════════════════════════════════════

@app.route('/reports')
def reports_home():
    return render_template('reports/home.html')


@app.route('/reports/monthly')
def report_monthly():
    # Default to current month
    year = request.args.get('year', date.today().year, type=int)
    month = request.args.get('month', date.today().month, type=int)

    # Total bookings this month
    total = query_db('''
        SELECT COUNT(*) as cnt FROM bookings
        WHERE strftime('%Y', booking_date) = ? AND strftime('%m', booking_date) = ?
        AND is_cancelled = 0
    ''', (str(year), f'{month:02d}'), one=True)['cnt']

    # By member
    by_member = query_db('''
        SELECT f.family_name, COUNT(*) as cnt
        FROM bookings b
        JOIN families f ON b.family_id = f.family_id
        WHERE strftime('%Y', b.booking_date) = ? AND strftime('%m', b.booking_date) = ?
        AND b.is_cancelled = 0
        GROUP BY f.family_id
        ORDER BY cnt DESC
    ''', (str(year), f'{month:02d}'))

    # By court
    by_court = query_db('''
        SELECT c.court_name, COUNT(*) as cnt
        FROM bookings b
        JOIN courts c ON b.court_id = c.court_id
        WHERE strftime('%Y', b.booking_date) = ? AND strftime('%m', b.booking_date) = ?
        AND b.is_cancelled = 0
        GROUP BY c.court_id
        ORDER BY c.court_name
    ''', (str(year), f'{month:02d}'))

    return render_template('reports/monthly.html',
                           total=total, by_member=by_member, by_court=by_court,
                           year=year, month=month)


@app.route('/reports/peak')
def report_peak():
    year = request.args.get('year', date.today().year, type=int)

    # By hour of day
    by_hour = query_db('''
        SELECT CAST(substr(start_time, 1, 2) AS INTEGER) as hour, COUNT(*) as cnt
        FROM bookings
        WHERE strftime('%Y', booking_date) = ? AND is_cancelled = 0
        GROUP BY hour
        ORDER BY hour
    ''', (str(year),))

    # By day of week (0=Sunday in SQLite strftime %w)
    by_day = query_db('''
        SELECT CAST(strftime('%w', booking_date) AS INTEGER) as dow, COUNT(*) as cnt
        FROM bookings
        WHERE strftime('%Y', booking_date) = ? AND is_cancelled = 0
        GROUP BY dow
        ORDER BY dow
    ''', (str(year),))

    day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

    return render_template('reports/peak.html',
                           by_hour=by_hour, by_day=by_day,
                           day_names=day_names, year=year)


@app.route('/reports/yearly')
def report_yearly():
    year = request.args.get('year', date.today().year, type=int)

    total_bookings = query_db('''
        SELECT COUNT(*) as cnt FROM bookings
        WHERE strftime('%Y', booking_date) = ? AND is_cancelled = 0
    ''', (str(year),), one=True)['cnt']

    by_member = query_db('''
        SELECT f.family_name, COUNT(*) as cnt
        FROM bookings b JOIN families f ON b.family_id = f.family_id
        WHERE strftime('%Y', b.booking_date) = ? AND b.is_cancelled = 0
        GROUP BY f.family_id ORDER BY cnt DESC
    ''', (str(year),))

    by_court = query_db('''
        SELECT c.court_name, COUNT(*) as cnt
        FROM bookings b JOIN courts c ON b.court_id = c.court_id
        WHERE strftime('%Y', b.booking_date) = ? AND b.is_cancelled = 0
        GROUP BY c.court_id ORDER BY c.court_name
    ''', (str(year),))

    maintenance_by_court = query_db('''
        SELECT c.court_name, COUNT(*) as cnt
        FROM maintenance_blocks mb JOIN courts c ON mb.court_id = c.court_id
        WHERE strftime('%Y', mb.block_date) = ?
        GROUP BY c.court_id ORDER BY c.court_name
    ''', (str(year),))

    return render_template('reports/yearly.html',
                           total_bookings=total_bookings,
                           by_member=by_member, by_court=by_court,
                           maintenance_by_court=maintenance_by_court,
                           year=year)


@app.route('/reports/guests')
def report_guests():
    year = request.args.get('year', date.today().year, type=int)

    guest_report = query_db('''
        SELECT f.family_name, SUM(b.guest_count) as total_guests,
               COUNT(CASE WHEN b.guest_count > 0 THEN 1 END) as visits_with_guests
        FROM bookings b
        JOIN families f ON b.family_id = f.family_id
        WHERE strftime('%Y', b.booking_date) = ? AND b.is_cancelled = 0
        AND b.guest_count > 0
        GROUP BY f.family_id
        ORDER BY total_guests DESC
    ''', (str(year),))

    return render_template('reports/guests.html', guest_report=guest_report, year=year)


@app.route('/reports/dues')
def report_dues_status():
    year = request.args.get('year', date.today().year, type=int)

    dues_report = query_db('''
        SELECT f.family_name, f.is_banned,
               COALESCE(d.is_paid, 0) as is_paid,
               d.amount_paid, d.date_paid
        FROM families f
        LEFT JOIN dues d ON f.family_id = d.family_id AND d.year = ?
        ORDER BY COALESCE(d.is_paid, 0), f.family_name
    ''', (year,))

    paid_count = sum(1 for d in dues_report if d['is_paid'])
    unpaid_count = len(dues_report) - paid_count

    return render_template('reports/dues_status.html',
                           dues_report=dues_report, year=year,
                           paid_count=paid_count, unpaid_count=unpaid_count)


# ═══════════════════════════════════════════════════════════════════
#  RUN
# ═══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
