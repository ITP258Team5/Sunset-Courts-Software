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
#  TEMPLATE FILTERS & GLOBALS
# ═══════════════════════════════════════════════════════════════════

@app.template_filter('usdate')
def us_date_filter(value):
    """Convert YYYY-MM-DD to MM/DD/YYYY."""
    if not value:
        return ''
    try:
        d = datetime.strptime(str(value), '%Y-%m-%d')
        return d.strftime('%m/%d/%Y')
    except (ValueError, TypeError):
        return str(value)


@app.template_filter('ustime')
def us_time_filter(value):
    """Convert HH:MM (24hr) to h:MM AM/PM."""
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
        'today_display': now.strftime('%a %m/%d/%Y  %-I:%M %p')
    }


# ═══════════════════════════════════════════════════════════════════
#  DASHBOARD
# ═══════════════════════════════════════════════════════════════════

@app.route('/')
def dashboard():
    today = date.today().isoformat()
    now_time = datetime.now().strftime('%H:%M')

    todays_bookings = query_db('''
        SELECT b.*, f.family_name, c.court_name
        FROM bookings b
        JOIN families f ON b.family_id = f.family_id
        JOIN courts c ON b.court_id = c.court_id
        WHERE b.booking_date = ? AND b.is_cancelled = 0
        ORDER BY b.start_time, c.court_name
    ''', (today,))

    courts = query_db('SELECT * FROM courts ORDER BY court_id')
    court_status = []
    for court in courts:
        current_booking = query_db('''
            SELECT b.*, f.family_name FROM bookings b
            JOIN families f ON b.family_id = f.family_id
            WHERE b.court_id = ? AND b.booking_date = ? AND b.is_cancelled = 0
            AND b.start_time <= ? AND b.end_time > ?
        ''', (court['court_id'], today, now_time, now_time), one=True)

        maint = query_db('''
            SELECT * FROM maintenance_blocks
            WHERE court_id = ? AND block_date = ?
            AND start_time <= ? AND end_time > ?
        ''', (court['court_id'], today, now_time, now_time), one=True)

        if maint:
            status = 'maint'
            detail = maint['reason'] or 'Maintenance'
        elif current_booking:
            status = 'busy'
            detail = f"Until {us_time_filter(current_booking['end_time'])}"
        else:
            status = 'open'
            detail = 'Available now'

        court_status.append({
            'court': court,
            'status': status,
            'detail': detail
        })

    total_accounts = query_db('SELECT COUNT(*) as cnt FROM families', one=True)['cnt']
    current_year = date.today().year
    dues_unpaid = query_db('''
        SELECT COUNT(*) as cnt FROM families f
        LEFT JOIN dues d ON f.family_id = d.family_id AND d.year = ?
        WHERE COALESCE(d.is_paid, 0) = 0
    ''', (current_year,), one=True)['cnt']
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
            flash('Account name is required.', 'error')
            return render_template('members/form.html', mode='add', family=request.form)

        family_id = execute_db('''
            INSERT INTO families (family_name, primary_contact, phone, email, join_date, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (family_name, primary_contact, phone, email, join_date, notes or None))

        execute_db('INSERT OR IGNORE INTO dues (family_id, year) VALUES (?, ?)',
                   (family_id, date.today().year))

        flash(f'{family_name} has been added.', 'success')
        return redirect(url_for('member_list'))

    return render_template('members/form.html', mode='add', family={})


@app.route('/members/<int:family_id>/edit', methods=['GET', 'POST'])
def member_edit(family_id):
    family = query_db('SELECT * FROM families WHERE family_id = ?', (family_id,), one=True)
    if not family:
        flash('Account not found.', 'error')
        return redirect(url_for('member_list'))

    if request.method == 'POST':
        family_name = request.form.get('family_name', '').strip()
        if not family_name:
            flash('Account name is required.', 'error')
            return render_template('members/form.html', mode='edit',
                                   family=request.form, family_id=family_id)

        execute_db('''
            UPDATE families SET family_name=?, primary_contact=?, phone=?, email=?, notes=?
            WHERE family_id=?
        ''', (family_name,
              request.form.get('primary_contact','').strip(),
              request.form.get('phone','').strip(),
              request.form.get('email','').strip(),
              request.form.get('notes','').strip() or None,
              family_id))

        flash(f'{family_name} updated.', 'success')
        return redirect(url_for('member_list'))

    return render_template('members/form.html', mode='edit', family=family, family_id=family_id)


@app.route('/members/<int:family_id>/view')
def member_view(family_id):
    family = query_db('SELECT * FROM families WHERE family_id = ?', (family_id,), one=True)
    if not family:
        flash('Account not found.', 'error')
        return redirect(url_for('member_list'))

    dues = query_db('SELECT * FROM dues WHERE family_id = ? ORDER BY year DESC', (family_id,))
    bookings = query_db('''
        SELECT b.*, c.court_name FROM bookings b
        JOIN courts c ON b.court_id = c.court_id
        WHERE b.family_id = ? ORDER BY b.booking_date DESC, b.start_time DESC LIMIT 20
    ''', (family_id,))

    return render_template('members/view.html', family=family, dues=dues, bookings=bookings)


# ═══════════════════════════════════════════════════════════════════
#  BAN / UNBAN
# ═══════════════════════════════════════════════════════════════════

@app.route('/members/<int:family_id>/ban', methods=['POST'])
def member_ban(family_id):
    family = query_db('SELECT * FROM families WHERE family_id = ?', (family_id,), one=True)
    if not family:
        flash('Account not found.', 'error')
        return redirect(url_for('member_list'))

    execute_db('UPDATE families SET is_banned = 1 WHERE family_id = ?', (family_id,))

    future = query_db('''
        SELECT b.*, c.court_name FROM bookings b
        JOIN courts c ON b.court_id = c.court_id
        WHERE b.family_id = ? AND b.booking_date >= ? AND b.is_cancelled = 0
        ORDER BY b.booking_date, b.start_time
    ''', (family_id, date.today().isoformat()))

    flash(f'{family["family_name"]} has been BANNED. {len(future)} future booking(s) to review.', 'warning')

    if future:
        return render_template('members/ban_review.html', family=family, bookings=future)
    return redirect(url_for('member_list'))


@app.route('/members/<int:family_id>/unban', methods=['POST'])
def member_unban(family_id):
    execute_db('UPDATE families SET is_banned = 0 WHERE family_id = ?', (family_id,))
    family = query_db('SELECT family_name FROM families WHERE family_id = ?', (family_id,), one=True)
    flash(f'{family["family_name"]} ban lifted.', 'success')
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
        family_id = request.form.get('family_id', type=int)
        court_id = request.form.get('court_id', type=int)
        booking_date = request.form.get('booking_date', '')
        start_time = request.form.get('start_time', '')
        end_time = request.form.get('end_time', '')
        guest_count = request.form.get('guest_count', 0, type=int)
        notes = request.form.get('notes', '').strip()

        errors = []
        if not all([family_id, court_id, booking_date, start_time, end_time]):
            errors.append('All fields are required.')

        if family_id:
            fam = query_db('SELECT * FROM families WHERE family_id = ?', (family_id,), one=True)
            if not fam:
                errors.append('Account not found.')
            elif fam['is_banned']:
                errors.append(f'{fam["family_name"]} is BANNED and cannot book.')

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
                SELECT b.*, f.family_name FROM bookings b
                JOIN families f ON b.family_id = f.family_id
                WHERE b.court_id = ? AND b.booking_date = ? AND b.is_cancelled = 0
                AND b.start_time < ? AND b.end_time > ?
            ''', (court_id, booking_date, end_time, start_time))
            if conflict:
                names = ', '.join([c['family_name'] for c in conflict])
                errors.append(f'Time conflict with: {names}')

        if guest_count > 2:
            flash('Note: Guest limit is 2 per visit. Booking exceeds recommended limit.', 'warning')

        if errors:
            for e in errors:
                flash(e, 'error')
            families = query_db('SELECT * FROM families WHERE is_banned = 0 ORDER BY family_name')
            courts = query_db('SELECT * FROM courts ORDER BY court_id')
            return render_template('bookings/form.html', mode='add',
                                   families=families, courts=courts, booking=request.form)

        execute_db('''
            INSERT INTO bookings (family_id, court_id, booking_date, start_time, end_time, guest_count, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (family_id, court_id, booking_date, start_time, end_time, guest_count, notes or None))

        flash('Booking created.', 'success')
        return redirect(url_for('booking_calendar', date=booking_date))

    families = query_db('SELECT * FROM families WHERE is_banned = 0 ORDER BY family_name')
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
#  DUES
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

    existing = query_db('SELECT * FROM dues WHERE family_id = ? AND year = ?', (family_id, year), one=True)
    if existing:
        execute_db('UPDATE dues SET is_paid=1, amount_paid=?, date_paid=?, notes=? WHERE family_id=? AND year=?',
                   (amount, date.today().isoformat(), notes or None, family_id, year))
    else:
        execute_db('INSERT INTO dues (family_id, year, is_paid, amount_paid, date_paid, notes) VALUES (?,?,1,?,?,?)',
                   (family_id, year, amount, date.today().isoformat(), notes or None))

    flash('Dues recorded as paid.', 'success')
    return redirect(url_for('dues_list', year=year))


@app.route('/dues/<int:family_id>/unpay', methods=['POST'])
def dues_unpay(family_id):
    year = request.form.get('year', date.today().year, type=int)
    execute_db('UPDATE dues SET is_paid=0, amount_paid=0, date_paid=NULL WHERE family_id=? AND year=?',
               (family_id, year))
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
        WHERE strftime('%Y', booking_date) = ? AND strftime('%m', booking_date) = ? AND is_cancelled = 0
    ''', (str(year), f'{month:02d}'), one=True)['cnt']

    by_member = query_db('''
        SELECT f.family_name, COUNT(*) as cnt FROM bookings b
        JOIN families f ON b.family_id = f.family_id
        WHERE strftime('%Y', b.booking_date) = ? AND strftime('%m', b.booking_date) = ? AND b.is_cancelled = 0
        GROUP BY f.family_id ORDER BY cnt DESC
    ''', (str(year), f'{month:02d}'))

    by_court = query_db('''
        SELECT c.court_name, COUNT(*) as cnt FROM bookings b
        JOIN courts c ON b.court_id = c.court_id
        WHERE strftime('%Y', b.booking_date) = ? AND strftime('%m', b.booking_date) = ? AND b.is_cancelled = 0
        GROUP BY c.court_id ORDER BY c.court_name
    ''', (str(year), f'{month:02d}'))

    return render_template('reports/monthly.html', total=total,
                           by_member=by_member, by_court=by_court, year=year, month=month)


@app.route('/reports/peak')
def report_peak():
    year = request.args.get('year', date.today().year, type=int)

    by_hour = query_db('''
        SELECT CAST(substr(start_time, 1, 2) AS INTEGER) as hour, COUNT(*) as cnt
        FROM bookings WHERE strftime('%Y', booking_date) = ? AND is_cancelled = 0
        GROUP BY hour ORDER BY hour
    ''', (str(year),))

    by_day = query_db('''
        SELECT CAST(strftime('%w', booking_date) AS INTEGER) as dow, COUNT(*) as cnt
        FROM bookings WHERE strftime('%Y', booking_date) = ? AND is_cancelled = 0
        GROUP BY dow ORDER BY dow
    ''', (str(year),))

    day_names = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday']
    return render_template('reports/peak.html', by_hour=by_hour, by_day=by_day,
                           day_names=day_names, year=year)


@app.route('/reports/yearly')
def report_yearly():
    year = request.args.get('year', date.today().year, type=int)

    total = query_db('SELECT COUNT(*) as cnt FROM bookings WHERE strftime(\'%Y\', booking_date) = ? AND is_cancelled = 0',
                     (str(year),), one=True)['cnt']

    by_member = query_db('''
        SELECT f.family_name, COUNT(*) as cnt FROM bookings b
        JOIN families f ON b.family_id = f.family_id
        WHERE strftime('%Y', b.booking_date) = ? AND b.is_cancelled = 0
        GROUP BY f.family_id ORDER BY cnt DESC
    ''', (str(year),))

    by_court = query_db('''
        SELECT c.court_name, COUNT(*) as cnt FROM bookings b
        JOIN courts c ON b.court_id = c.court_id
        WHERE strftime('%Y', b.booking_date) = ? AND b.is_cancelled = 0
        GROUP BY c.court_id ORDER BY c.court_name
    ''', (str(year),))

    maint = query_db('''
        SELECT c.court_name, COUNT(*) as cnt FROM maintenance_blocks mb
        JOIN courts c ON mb.court_id = c.court_id
        WHERE strftime('%Y', mb.block_date) = ?
        GROUP BY c.court_id ORDER BY c.court_name
    ''', (str(year),))

    return render_template('reports/yearly.html', total_bookings=total,
                           by_member=by_member, by_court=by_court,
                           maintenance_by_court=maint, year=year)


@app.route('/reports/guests')
def report_guests():
    year = request.args.get('year', date.today().year, type=int)
    report = query_db('''
        SELECT f.family_name, SUM(b.guest_count) as total_guests,
               COUNT(CASE WHEN b.guest_count > 0 THEN 1 END) as visits_with_guests
        FROM bookings b JOIN families f ON b.family_id = f.family_id
        WHERE strftime('%Y', b.booking_date) = ? AND b.is_cancelled = 0 AND b.guest_count > 0
        GROUP BY f.family_id ORDER BY total_guests DESC
    ''', (str(year),))
    return render_template('reports/guests.html', guest_report=report, year=year)


@app.route('/reports/dues')
def report_dues_status():
    year = request.args.get('year', date.today().year, type=int)
    report = query_db('''
        SELECT f.family_name, f.is_banned, COALESCE(d.is_paid, 0) as is_paid,
               d.amount_paid, d.date_paid
        FROM families f
        LEFT JOIN dues d ON f.family_id = d.family_id AND d.year = ?
        ORDER BY COALESCE(d.is_paid, 0), f.family_name
    ''', (year,))
    paid = sum(1 for r in report if r['is_paid'])
    return render_template('reports/dues_status.html', dues_report=report, year=year,
                           paid_count=paid, unpaid_count=len(report) - paid)


# ═══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
