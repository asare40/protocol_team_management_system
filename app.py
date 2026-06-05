from flask import Flask, request, jsonify, render_template, session, redirect, url_for
import sqlite3, os, json
from datetime import datetime, timedelta, date
from functools import wraps

app = Flask(__name__)
app.secret_key = 'wellspring_protocol_2026_ultra_secret'
DB = os.path.join(os.path.dirname(__file__), 'protocol.db')

# ── DATABASE ──────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'member',
            full_name TEXT,
            member_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY,
            member_code TEXT UNIQUE,
            name TEXT NOT NULL,
            role TEXT,
            office TEXT,
            phone TEXT,
            email TEXT,
            date_joined TEXT,
            emergency_contact TEXT,
            emergency_phone TEXT,
            spiritual_status TEXT DEFAULT 'Active',
            skills TEXT,
            notes TEXT,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY,
            member_id INTEGER,
            date TEXT,
            service TEXT,
            status TEXT,
            notes TEXT,
            recorded_by TEXT,
            recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(member_id) REFERENCES members(id)
        );
        CREATE TABLE IF NOT EXISTS attendance_excuses (
            id INTEGER PRIMARY KEY,
            member_id INTEGER,
            date TEXT,
            service TEXT,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            reviewed_by TEXT,
            reviewed_at TEXT,
            FOREIGN KEY(member_id) REFERENCES members(id)
        );
        CREATE TABLE IF NOT EXISTS duty_roster (
            id INTEGER PRIMARY KEY,
            week_number INTEGER,
            date TEXT,
            duty1 TEXT,
            duty2 TEXT,
            standby TEXT,
            remarks TEXT,
            confirmed INTEGER DEFAULT 0,
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS welfare_contributions (
            id INTEGER PRIMARY KEY,
            member_id INTEGER,
            date TEXT,
            amount REAL,
            receipt_no TEXT,
            notes TEXT,
            recorded_by TEXT,
            recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(member_id) REFERENCES members(id)
        );
        CREATE TABLE IF NOT EXISTS welfare_disbursements (
            id INTEGER PRIMARY KEY,
            member_id INTEGER,
            date TEXT,
            purpose TEXT,
            amount REAL,
            approved_by TEXT,
            notes TEXT,
            status TEXT DEFAULT 'approved',
            requested_by TEXT,
            recorded_by TEXT,
            recorded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(member_id) REFERENCES members(id)
        );
        CREATE TABLE IF NOT EXISTS disciplinary (
            id INTEGER PRIMARY KEY,
            member_id INTEGER,
            date TEXT,
            offence TEXT,
            section TEXT,
            action_taken TEXT,
            issued_by TEXT,
            remarks TEXT,
            acknowledged INTEGER DEFAULT 0,
            acknowledged_date TEXT,
            expiry_date TEXT,
            active INTEGER DEFAULT 1,
            FOREIGN KEY(member_id) REFERENCES members(id)
        );
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY,
            type TEXT,
            title TEXT,
            message TEXT,
            target_role TEXT DEFAULT 'all',
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            read_by TEXT DEFAULT '[]'
        );
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY,
            title TEXT,
            body TEXT,
            priority TEXT DEFAULT 'normal',
            created_by TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT
        );
    ''')

    # Seed users
    for uname, pwd, urole, uname_full in [
        ('asare',   'admin123',   'admin',     'Mr. Asare Enock'),
        ('richard', 'richard123', 'secretary', 'Richard'),
        ('apostle', 'apostle123', 'member',    'Apostle Nick'),
    ]:
        try:
            db.execute("INSERT INTO users (username,password,role,full_name) VALUES (?,?,?,?)",
                       (uname, pwd, urole, uname_full))
        except: pass

    # Seed members
    member_count = db.execute("SELECT COUNT(*) as c FROM members").fetchone()['c']
    if member_count == 0:
        members = [
            ('PT-001', 'Mr. Asare Enock',  'Head of Protocol',              'Head of Protocol',                    None, '2020-01-01'),
            ('PT-002', 'Lamptey',           'General Member',                'General Member',                       None, '2021-03-15'),
            ('PT-003', 'Foster',            'Operations & Security Officer', 'Operations & Security Officer',        None, '2021-03-15'),
            ('PT-004', 'Apostle Nick',      'Operations & Security Officer', 'Operations & Security Officer',        None, '2021-06-10'),
            ('PT-005', 'Mr. Straw',         'Soul Winning Assistant',        'Soul Winning Coordinator (Assistant)', None, '2022-01-01'),
            ('PT-006', 'Richard',           'Secretary & Financial Officer', 'Secretary & Financial Officer',        None, '2020-01-01'),
            ('PT-007', 'Artiki David',      'Welfare & Hospitality Officer', 'Welfare & Hospitality Officer',        None, '2022-05-20'),
            ('PT-008', 'Nyarko Emmanuel',   'General Member',                'General Member',                       None, '2023-01-01'),
            ('PT-009', 'Michael',           'Media Officer',                 'Media Officer',                        None, '2022-08-01'),
        ]
        for m in members:
            db.execute("INSERT INTO members (member_code,name,role,office,phone,date_joined) VALUES (?,?,?,?,?,?)", m)
    db.commit()
    db.close()

# ── AUTH ──────────────────────────────────────────────────────────────────────
USERS = {
    'asare':   {'password':'admin123',   'role':'admin',     'name':'Mr. Asare Enock'},
    'richard': {'password':'richard123', 'role':'secretary', 'name':'Richard'},
    'apostle': {'password':'apostle123', 'role':'member',    'name':'Apostle Nick'},
}

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        if session.get('role') not in ('admin', 'secretary'):
            return jsonify({'error': 'Unauthorized'}), 403
        return f(*args, **kwargs)
    return decorated

@app.route('/', methods=['GET','POST'])
def login():
    error = None
    if request.method == 'POST':
        u = request.form.get('username','').lower()
        p = request.form.get('password','')
        if u in USERS and USERS[u]['password'] == p:
            session['user'] = u
            session['role'] = USERS[u]['role']
            session['name'] = USERS[u]['name']
            return redirect(url_for('dashboard'))
        error = 'Invalid username or password.'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── DASHBOARD ─────────────────────────────────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    db = get_db()
    members_count = db.execute("SELECT COUNT(*) as c FROM members WHERE active=1").fetchone()['c']
    att_count     = db.execute("SELECT COUNT(*) as c FROM attendance").fetchone()['c']
    welfare_in    = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM welfare_contributions").fetchone()['s']
    welfare_out   = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM welfare_disbursements").fetchone()['s']
    disc_count    = db.execute("SELECT COUNT(*) as c FROM disciplinary WHERE active=1").fetchone()['c']
    welfare_bal   = round(welfare_in - welfare_out, 2)

    # Attendance alerts - missed 3+ consecutive services
    alerts = []
    members = db.execute("SELECT id, name FROM members WHERE active=1").fetchall()
    for m in members:
        last3 = db.execute("""SELECT status FROM attendance WHERE member_id=?
                               ORDER BY date DESC LIMIT 3""", (m['id'],)).fetchall()
        if len(last3) == 3 and all(r['status'] == 'A' for r in last3):
            alerts.append({'name': m['name'], 'type': 'attendance', 'msg': '3 consecutive absences'})

    # Members with no contribution this month
    this_month = datetime.now().strftime('%Y-%m')
    for m in members:
        contrib = db.execute("""SELECT id FROM welfare_contributions
                                WHERE member_id=? AND date LIKE ?""",
                             (m['id'], this_month + '%')).fetchone()
        if not contrib:
            alerts.append({'name': m['name'], 'type': 'welfare', 'msg': 'No contribution this month'})

    recent_att = db.execute("""SELECT a.date,a.service,m.name,a.status FROM attendance a
                                JOIN members m ON a.member_id=m.id
                                ORDER BY a.id DESC LIMIT 8""").fetchall()

    upcoming_duty = db.execute("""SELECT * FROM duty_roster WHERE date >= date('now')
                                   ORDER BY date ASC LIMIT 3""").fetchall()

    announcements = db.execute("""SELECT * FROM announcements
                                   WHERE expires_at IS NULL OR expires_at >= date('now')
                                   ORDER BY created_at DESC LIMIT 5""").fetchall()

    # Attendance this month
    att_this_month = db.execute("""SELECT
        SUM(CASE WHEN status='P' THEN 1 ELSE 0 END) as present,
        SUM(CASE WHEN status='A' THEN 1 ELSE 0 END) as absent,
        SUM(CASE WHEN status='L' THEN 1 ELSE 0 END) as late,
        SUM(CASE WHEN status='E' THEN 1 ELSE 0 END) as excused
        FROM attendance WHERE date LIKE ?""", (this_month + '%',)).fetchone()

    db.close()
    return render_template('dashboard.html',
        members_count=members_count, att_count=att_count,
        welfare_bal=welfare_bal, welfare_in=welfare_in, welfare_out=welfare_out,
        disc_count=disc_count, recent_att=recent_att,
        upcoming_duty=upcoming_duty, alerts=alerts,
        announcements=announcements, att_this_month=att_this_month)

# ── MEMBERS ───────────────────────────────────────────────────────────────────
@app.route('/members')
@login_required
def members_page():
    return render_template('members.html')

@app.route('/members/<int:mid>')
@login_required
def member_profile(mid):
    db = get_db()
    member = db.execute("SELECT * FROM members WHERE id=?", (mid,)).fetchone()
    if not member:
        db.close()
        return redirect(url_for('members_page'))

    att_summary = db.execute("""SELECT
        SUM(CASE WHEN status='P' THEN 1 ELSE 0 END) as present,
        SUM(CASE WHEN status='A' THEN 1 ELSE 0 END) as absent,
        SUM(CASE WHEN status='L' THEN 1 ELSE 0 END) as late,
        SUM(CASE WHEN status='E' THEN 1 ELSE 0 END) as excused,
        COUNT(*) as total FROM attendance WHERE member_id=?""", (mid,)).fetchone()

    welfare_total = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM welfare_contributions WHERE member_id=?", (mid,)).fetchone()['s']
    welfare_received = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM welfare_disbursements WHERE member_id=?", (mid,)).fetchone()['s']
    disc_count = db.execute("SELECT COUNT(*) as c FROM disciplinary WHERE member_id=? AND active=1", (mid,)).fetchone()['c']
    recent_att = db.execute("""SELECT * FROM attendance WHERE member_id=? ORDER BY date DESC LIMIT 10""", (mid,)).fetchall()
    disc_records = db.execute("SELECT * FROM disciplinary WHERE member_id=? ORDER BY date DESC", (mid,)).fetchall()
    contrib_records = db.execute("SELECT * FROM welfare_contributions WHERE member_id=? ORDER BY date DESC LIMIT 10", (mid,)).fetchall()
    duty_records = db.execute("""SELECT * FROM duty_roster WHERE duty1=? OR duty2=? OR standby=?
                                  ORDER BY date DESC LIMIT 10""", (member['name'], member['name'], member['name'])).fetchall()
    db.close()
    return render_template('profile.html',
        member=member, att_summary=att_summary,
        welfare_total=welfare_total, welfare_received=welfare_received,
        disc_count=disc_count, recent_att=recent_att,
        disc_records=disc_records, contrib_records=contrib_records,
        duty_records=duty_records)

@app.route('/api/members', methods=['GET'])
@login_required
def api_members():
    db = get_db()
    include_all = request.args.get('all', '0') == '1'
    q = "SELECT * FROM members" + ("" if include_all else " WHERE active=1") + " ORDER BY name"
    rows = db.execute(q).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/members', methods=['POST'])
@login_required
def api_members_add():
    d = request.json
    if not d.get('name'):
        return jsonify({'success': False, 'error': 'Name is required'}), 400
    db = get_db()
    # Generate member code
    last = db.execute("SELECT member_code FROM members ORDER BY id DESC LIMIT 1").fetchone()
    if last and last['member_code']:
        try:
            num = int(last['member_code'].split('-')[1]) + 1
        except:
            num = db.execute("SELECT COUNT(*) as c FROM members").fetchone()['c'] + 1
    else:
        num = 1
    code = f"PT-{num:03d}"
    db.execute("""INSERT INTO members (member_code,name,role,office,phone,email,date_joined,
                  emergency_contact,emergency_phone,spiritual_status,skills,notes,active)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)""",
               (code, d['name'], d.get('role','General Member'),
                d.get('office', d.get('role','General Member')),
                d.get('phone',''), d.get('email',''), d.get('date_joined', date.today().isoformat()),
                d.get('emergency_contact',''), d.get('emergency_phone',''),
                d.get('spiritual_status','Active'), d.get('skills',''), d.get('notes','')))
    db.commit()
    db.close()
    return jsonify({'success': True, 'code': code})

@app.route('/api/members/<int:mid>', methods=['PUT'])
@login_required
def api_members_edit(mid):
    d = request.json
    db = get_db()
    db.execute("""UPDATE members SET name=?,role=?,office=?,phone=?,email=?,date_joined=?,
                  emergency_contact=?,emergency_phone=?,spiritual_status=?,skills=?,notes=? WHERE id=?""",
               (d['name'], d.get('role',''), d.get('office',''), d.get('phone',''),
                d.get('email',''), d.get('date_joined',''), d.get('emergency_contact',''),
                d.get('emergency_phone',''), d.get('spiritual_status','Active'),
                d.get('skills',''), d.get('notes',''), mid))
    db.commit()
    db.close()
    return jsonify({'success': True})

@app.route('/api/members/<int:mid>', methods=['DELETE'])
@login_required
def api_members_delete(mid):
    db = get_db()
    db.execute("UPDATE members SET active=0 WHERE id=?", (mid,))
    db.commit(); db.close()
    return jsonify({'success': True})

@app.route('/api/members/<int:mid>/restore', methods=['POST'])
@login_required
def api_members_restore(mid):
    db = get_db()
    db.execute("UPDATE members SET active=1 WHERE id=?", (mid,))
    db.commit(); db.close()
    return jsonify({'success': True})

# ── ATTENDANCE ────────────────────────────────────────────────────────────────
@app.route('/attendance')
@login_required
def attendance():
    return render_template('attendance.html')

@app.route('/api/attendance', methods=['GET','POST'])
@login_required
def api_attendance():
    db = get_db()
    if request.method == 'POST':
        data = request.json
        for entry in data.get('entries', []):
            # Check if already recorded for this date/service/member
            existing = db.execute("""SELECT id FROM attendance WHERE member_id=? AND date=? AND service=?""",
                                  (entry['member_id'], data['date'], data['service'])).fetchone()
            if existing:
                db.execute("""UPDATE attendance SET status=?,notes=?,recorded_by=? WHERE id=?""",
                           (entry['status'], entry.get('notes',''), session.get('name',''), existing['id']))
            else:
                db.execute("""INSERT INTO attendance (member_id,date,service,status,notes,recorded_by)
                              VALUES (?,?,?,?,?,?)""",
                           (entry['member_id'], data['date'], data['service'],
                            entry['status'], entry.get('notes',''), session.get('name','')))
        db.commit(); db.close()
        return jsonify({'success': True})
    date    = request.args.get('date','')
    service = request.args.get('service','')
    q = "SELECT a.*,m.name,m.member_code FROM attendance a JOIN members m ON a.member_id=m.id WHERE 1=1"
    params = []
    if date:    q += " AND a.date=?";    params.append(date)
    if service: q += " AND a.service=?"; params.append(service)
    q += " ORDER BY a.date DESC, m.name"
    rows = db.execute(q, params).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/attendance/summary')
@login_required
def att_summary():
    db = get_db()
    rows = db.execute("""
        SELECT m.id, m.name, m.member_code,
            SUM(CASE WHEN a.status='P' THEN 1 ELSE 0 END) as present,
            SUM(CASE WHEN a.status='A' THEN 1 ELSE 0 END) as absent,
            SUM(CASE WHEN a.status='L' THEN 1 ELSE 0 END) as late,
            SUM(CASE WHEN a.status='E' THEN 1 ELSE 0 END) as excused,
            COUNT(*) as total
        FROM attendance a JOIN members m ON a.member_id=m.id
        WHERE m.active=1 GROUP BY m.id ORDER BY m.name
    """).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/attendance/alerts')
@login_required
def att_alerts():
    db = get_db()
    members = db.execute("SELECT id, name FROM members WHERE active=1").fetchall()
    alerts = []
    for m in members:
        last3 = db.execute("""SELECT status FROM attendance WHERE member_id=?
                               ORDER BY date DESC LIMIT 3""", (m['id'],)).fetchall()
        if len(last3) >= 3 and all(r['status'] == 'A' for r in last3):
            alerts.append({'member_id': m['id'], 'name': m['name'], 'consecutive_absences': len(last3)})
    db.close()
    return jsonify(alerts)

@app.route('/api/attendance/monthly')
@login_required
def att_monthly():
    db = get_db()
    month = request.args.get('month', datetime.now().strftime('%Y-%m'))
    rows = db.execute("""SELECT
        SUM(CASE WHEN status='P' THEN 1 ELSE 0 END) as present,
        SUM(CASE WHEN status='A' THEN 1 ELSE 0 END) as absent,
        SUM(CASE WHEN status='L' THEN 1 ELSE 0 END) as late,
        SUM(CASE WHEN status='E' THEN 1 ELSE 0 END) as excused,
        COUNT(*) as total, date
        FROM attendance WHERE date LIKE ? GROUP BY date ORDER BY date""",
                      (month + '%',)).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

# ── DUTY ROSTER ───────────────────────────────────────────────────────────────
@app.route('/duty')
@login_required
def duty():
    return render_template('duty.html')

@app.route('/api/duty', methods=['GET','POST','DELETE'])
@login_required
def api_duty():
    db = get_db()
    if request.method == 'POST':
        d = request.json
        if d.get('id'):
            db.execute("""UPDATE duty_roster SET week_number=?,date=?,duty1=?,duty2=?,standby=?,remarks=? WHERE id=?""",
                       (d['week_number'],d['date'],d['duty1'],d['duty2'],d['standby'],d.get('remarks',''),d['id']))
        else:
            db.execute("""INSERT INTO duty_roster (week_number,date,duty1,duty2,standby,remarks,created_by)
                          VALUES (?,?,?,?,?,?,?)""",
                       (d['week_number'],d['date'],d['duty1'],d['duty2'],d['standby'],
                        d.get('remarks',''), session.get('name','')))
        db.commit(); db.close()
        return jsonify({'success': True})
    if request.method == 'DELETE':
        rid = request.json.get('id')
        db.execute("DELETE FROM duty_roster WHERE id=?", (rid,))
        db.commit(); db.close()
        return jsonify({'success': True})
    rows = db.execute("SELECT * FROM duty_roster ORDER BY date DESC").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/duty/autoschedule', methods=['POST'])
@login_required
def auto_schedule():
    db = get_db()
    d = request.json
    members = db.execute("SELECT name FROM members WHERE active=1 ORDER BY name").fetchall()
    member_names = [m['name'] for m in members]
    if len(member_names) < 3:
        db.close()
        return jsonify({'success': False, 'error': 'Need at least 3 members'})
    # Get last duty assignments to ensure fair rotation
    last_duties = db.execute("""SELECT duty1,duty2,standby FROM duty_roster ORDER BY date DESC LIMIT 10""").fetchall()
    duty_count = {name: 0 for name in member_names}
    for row in last_duties:
        for name in [row['duty1'], row['duty2'], row['standby']]:
            if name in duty_count:
                duty_count[name] += 1
    # Sort by least recently assigned
    sorted_members = sorted(member_names, key=lambda x: duty_count.get(x, 0))
    start_date = datetime.strptime(d['start_date'], '%Y-%m-%d')
    weeks = d.get('weeks', 4)
    created = []
    for i in range(weeks):
        week_date = start_date + timedelta(weeks=i)
        week_num = week_date.isocalendar()[1]
        idx = (i * 3) % len(sorted_members)
        duty1  = sorted_members[idx % len(sorted_members)]
        duty2  = sorted_members[(idx+1) % len(sorted_members)]
        standby = sorted_members[(idx+2) % len(sorted_members)]
        db.execute("""INSERT INTO duty_roster (week_number,date,duty1,duty2,standby,remarks,created_by)
                      VALUES (?,?,?,?,?,?,?)""",
                   (week_num, week_date.strftime('%Y-%m-%d'), duty1, duty2, standby,
                    'Auto-scheduled', session.get('name','')))
        created.append({'week': week_num, 'date': week_date.strftime('%Y-%m-%d'), 'duty1': duty1, 'duty2': duty2, 'standby': standby})
    db.commit(); db.close()
    return jsonify({'success': True, 'created': created})

# ── WELFARE ───────────────────────────────────────────────────────────────────
@app.route('/welfare')
@login_required
def welfare():
    return render_template('welfare.html')

@app.route('/api/welfare/contributions', methods=['GET','POST'])
@login_required
def api_contributions():
    db = get_db()
    if request.method == 'POST':
        d = request.json
        db.execute("""INSERT INTO welfare_contributions (member_id,date,amount,receipt_no,notes,recorded_by)
                      VALUES (?,?,?,?,?,?)""",
                   (d['member_id'],d['date'],d['amount'],d.get('receipt_no',''),
                    d.get('notes',''), session.get('name','')))
        db.commit(); db.close()
        return jsonify({'success': True})
    rows = db.execute("""SELECT c.*,m.name,m.member_code FROM welfare_contributions c
                         JOIN members m ON c.member_id=m.id ORDER BY c.date DESC""").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/welfare/contributions/<int:cid>', methods=['DELETE'])
@login_required
def api_contrib_delete(cid):
    db = get_db()
    db.execute("DELETE FROM welfare_contributions WHERE id=?", (cid,))
    db.commit(); db.close()
    return jsonify({'success': True})

@app.route('/api/welfare/disbursements', methods=['GET','POST'])
@login_required
def api_disbursements():
    db = get_db()
    if request.method == 'POST':
        d = request.json
        db.execute("""INSERT INTO welfare_disbursements (member_id,date,purpose,amount,approved_by,notes,recorded_by)
                      VALUES (?,?,?,?,?,?,?)""",
                   (d['member_id'],d['date'],d['purpose'],d['amount'],
                    d.get('approved_by',''),d.get('notes',''), session.get('name','')))
        db.commit(); db.close()
        return jsonify({'success': True})
    rows = db.execute("""SELECT d.*,m.name FROM welfare_disbursements d
                         JOIN members m ON d.member_id=m.id ORDER BY d.date DESC""").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/welfare/balance')
@login_required
def welfare_balance():
    db = get_db()
    total_in  = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM welfare_contributions").fetchone()['s']
    total_out = db.execute("SELECT COALESCE(SUM(amount),0) as s FROM welfare_disbursements").fetchone()['s']
    # Monthly breakdown
    monthly = db.execute("""SELECT strftime('%Y-%m', date) as month,
        SUM(amount) as total FROM welfare_contributions
        GROUP BY month ORDER BY month DESC LIMIT 12""").fetchall()
    # Per member summary
    per_member = db.execute("""SELECT m.name,
        COALESCE(SUM(c.amount),0) as contributed,
        (SELECT COALESCE(SUM(amount),0) FROM welfare_disbursements WHERE member_id=m.id) as received
        FROM members m LEFT JOIN welfare_contributions c ON m.id=c.member_id
        WHERE m.active=1 GROUP BY m.id ORDER BY contributed DESC""").fetchall()
    db.close()
    return jsonify({
        'total_in': total_in, 'total_out': total_out,
        'balance': round(total_in - total_out, 2),
        'monthly': [dict(r) for r in monthly],
        'per_member': [dict(r) for r in per_member]
    })

# ── DISCIPLINARY ──────────────────────────────────────────────────────────────
@app.route('/disciplinary')
@login_required
def disciplinary():
    return render_template('disciplinary.html')

@app.route('/api/disciplinary', methods=['GET','POST'])
@login_required
def api_disciplinary():
    db = get_db()
    if request.method == 'POST':
        d = request.json
        # Auto-set expiry date (6 months for verbal/written warnings)
        expiry = None
        if d.get('action_taken') in ('Verbal Warning', 'Written Warning'):
            expiry = (datetime.now() + timedelta(days=180)).strftime('%Y-%m-%d')
        db.execute("""INSERT INTO disciplinary (member_id,date,offence,section,action_taken,issued_by,remarks,expiry_date)
                      VALUES (?,?,?,?,?,?,?,?)""",
                   (d['member_id'],d['date'],d['offence'],d.get('section',''),
                    d['action_taken'],d.get('issued_by','Mr. Asare Enock'),
                    d.get('remarks',''), expiry))
        db.commit(); db.close()
        return jsonify({'success': True})
    rows = db.execute("""SELECT di.*,m.name FROM disciplinary di
                         JOIN members m ON di.member_id=m.id ORDER BY di.date DESC""").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/disciplinary/<int:did>/acknowledge', methods=['POST'])
@login_required
def disc_acknowledge(did):
    db = get_db()
    db.execute("UPDATE disciplinary SET acknowledged=1, acknowledged_date=? WHERE id=?",
               (date.today().isoformat(), did))
    db.commit(); db.close()
    return jsonify({'success': True})

# ── NOTIFICATIONS ─────────────────────────────────────────────────────────────
@app.route('/api/notifications', methods=['GET','POST'])
@login_required
def api_notifications():
    db = get_db()
    if request.method == 'POST':
        d = request.json
        db.execute("""INSERT INTO notifications (type,title,message,target_role,created_by)
                      VALUES (?,?,?,?,?)""",
                   (d.get('type','info'), d['title'], d['message'],
                    d.get('target_role','all'), session.get('name','')))
        db.commit(); db.close()
        return jsonify({'success': True})
    role = session.get('role', 'member')
    rows = db.execute("""SELECT * FROM notifications WHERE target_role='all' OR target_role=?
                         ORDER BY created_at DESC LIMIT 20""", (role,)).fetchall()
    db.close()
    result = []
    user = session.get('user', '')
    for r in rows:
        rd = dict(r)
        try:
            read_by = json.loads(r['read_by'] or '[]')
        except:
            read_by = []
        rd['is_read'] = user in read_by
        result.append(rd)
    return jsonify(result)

@app.route('/api/notifications/<int:nid>/read', methods=['POST'])
@login_required
def mark_notification_read(nid):
    db = get_db()
    row = db.execute("SELECT read_by FROM notifications WHERE id=?", (nid,)).fetchone()
    if row:
        try:
            read_by = json.loads(row['read_by'] or '[]')
        except:
            read_by = []
        user = session.get('user','')
        if user not in read_by:
            read_by.append(user)
        db.execute("UPDATE notifications SET read_by=? WHERE id=?", (json.dumps(read_by), nid))
        db.commit()
    db.close()
    return jsonify({'success': True})

# ── ANNOUNCEMENTS ─────────────────────────────────────────────────────────────
@app.route('/api/announcements', methods=['GET','POST','DELETE'])
@login_required
def api_announcements():
    db = get_db()
    if request.method == 'POST':
        d = request.json
        db.execute("""INSERT INTO announcements (title,body,priority,created_by,expires_at)
                      VALUES (?,?,?,?,?)""",
                   (d['title'], d['body'], d.get('priority','normal'),
                    session.get('name',''), d.get('expires_at',None)))
        db.commit(); db.close()
        return jsonify({'success': True})
    if request.method == 'DELETE':
        aid = request.json.get('id')
        db.execute("DELETE FROM announcements WHERE id=?", (aid,))
        db.commit(); db.close()
        return jsonify({'success': True})
    rows = db.execute("""SELECT * FROM announcements
                         WHERE expires_at IS NULL OR expires_at >= date('now')
                         ORDER BY created_at DESC""").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

# ── REPORTS ───────────────────────────────────────────────────────────────────
@app.route('/reports')
@login_required
def reports():
    return render_template('reports.html')

@app.route('/api/reports/monthly')
@login_required
def monthly_report():
    db = get_db()
    month = request.args.get('month', datetime.now().strftime('%Y-%m'))
    # Attendance
    att = db.execute("""SELECT m.name,
        SUM(CASE WHEN a.status='P' THEN 1 ELSE 0 END) as present,
        SUM(CASE WHEN a.status='A' THEN 1 ELSE 0 END) as absent,
        SUM(CASE WHEN a.status='L' THEN 1 ELSE 0 END) as late,
        SUM(CASE WHEN a.status='E' THEN 1 ELSE 0 END) as excused,
        COUNT(*) as total
        FROM members m LEFT JOIN attendance a ON m.id=a.member_id AND a.date LIKE ?
        WHERE m.active=1 GROUP BY m.id ORDER BY m.name""", (month+'%',)).fetchall()
    # Welfare
    contrib = db.execute("""SELECT COALESCE(SUM(amount),0) as s FROM welfare_contributions WHERE date LIKE ?""",
                         (month+'%',)).fetchone()['s']
    disburse = db.execute("""SELECT COALESCE(SUM(amount),0) as s FROM welfare_disbursements WHERE date LIKE ?""",
                          (month+'%',)).fetchone()['s']
    # Disciplinary
    disc = db.execute("""SELECT m.name, d.action_taken, d.date FROM disciplinary d
                         JOIN members m ON d.member_id=m.id WHERE d.date LIKE ?""",
                      (month+'%',)).fetchall()
    # Duty
    duty = db.execute("SELECT * FROM duty_roster WHERE date LIKE ? ORDER BY date", (month+'%',)).fetchall()
    db.close()
    return jsonify({
        'month': month,
        'attendance': [dict(r) for r in att],
        'welfare': {'contributions': contrib, 'disbursements': disburse, 'net': round(contrib - disburse, 2)},
        'disciplinary': [dict(r) for r in disc],
        'duty': [dict(r) for r in duty]
    })

if __name__ == '__main__':
    init_db()
    print("\n" + "="*60)
    print("  PROTOCOL & MEDIA TEAM — MANAGEMENT SYSTEM v2.0")
    print("  Wellspring of Grace Arena Chapel")
    print("="*60)
    print("  http://localhost:5000")
    print("="*60)
    print("  asare / admin123   |  richard / richard123  |  apostle / apostle123")
    print("="*60 + "\n")
    app.run(debug=False, port=5000)
