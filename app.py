import csv
from io import StringIO
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response
from werkzeug.security import generate_password_hash, check_password_hash
import random

app = Flask(__name__)
app.secret_key = "dpmg_campussync_secret_key"
app.permanent_session_lifetime = timedelta(minutes=30)

# --- ADVANCED MOCK DATABASE ---
users = {
    'admin@xime.edu': {'name': 'System Admin', 'password': generate_password_hash('admin123'), 'role': 'super_admin', 'status': 'approved'},
    'ganesh@college.edu': {'name': 'Shree Ganesh', 'password': generate_password_hash('password'), 'role': 'club_admin', 'status': 'approved'},
    'student@college.edu': {'name': 'Mock Student', 'password': generate_password_hash('password'), 'role': 'student', 'club': 'Finance Club', 'status': 'approved'}
}

clubs = [
    {'id': 1, 'name': 'X-Insights Analytics Club', 'category': 'Analytics', 'description': 'Data and analytics.', 'coordinator': 'None', 'threshold': 75},
    {'id': 2, 'name': 'Marketing Club', 'category': 'Marketing', 'description': 'Marketing enthusiasts.', 'coordinator': 'None', 'threshold': 75},
    {'id': 3, 'name': 'Matrix Club', 'category': 'Operations', 'description': 'Operations management.', 'coordinator': 'None', 'threshold': 75},
    {'id': 4, 'name': 'Finance Club', 'category': 'Finance', 'description': 'Finance and trading.', 'coordinator': 'ganesh@college.edu', 'threshold': 80},
    {'id': 5, 'name': 'X Tech Club', 'category': 'Technology', 'description': 'Tech and coding.', 'coordinator': 'None', 'threshold': 75}
]

# The mock event is pre-loaded with an expiration time 15 minutes from server start
events = [{'id': 1, 'club': 'Finance Club', 'name': 'Intro to Trading', 'date': '2026-10-01', 'start_time': '10:00', 'end_time': '12:00', 'venue': 'Auditorium', 'code': '123456', 'status': 'Active', 'expires_at': datetime.now() + timedelta(minutes=15)}]
members = [{'email': 'student@college.edu', 'name': 'Mock Student', 'club': 'Finance Club', 'attendance_pct': 100}]
attendance_records = []
correction_requests = []
audit_logs = []

def log_audit(action, user, details):
    audit_logs.append({'action': action, 'user': user, 'details': details})

def recalc_attendance():
    """Dynamically calculates the attendance percentage for every student."""
    for m in members:
        c_events = [e for e in events if e['club'] == m['club'] and e['status'] == 'Active']
        total = len(c_events)
        if total == 0:
            m['attendance_pct'] = 100
        else:
            event_names = [e['name'] for e in c_events]
            attended = sum(1 for r in attendance_records if r['email'] == m['email'] and r['event'] in event_names and r['status'] in ['Present', 'Excused'])
            m['attendance_pct'] = int((attended / total) * 100)

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    global members
    if request.method == 'POST':
        email = request.form['email']
        users[email] = {
            'name': request.form['name'],
            'password': generate_password_hash(request.form['password']),
            'role': request.form['role'],
            'club': request.form.get('club'),
            'status': 'pending' 
        }
        flash("Account created! Status: PENDING APPROVAL.", "success")
        return redirect(url_for('login'))
    return render_template('signup.html', clubs=clubs)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        session.permanent = True
        email = request.form['email']
        password = request.form['password']
        user = users.get(email)
        
        if not user or not check_password_hash(user['password'], password):
            flash("Invalid Email or Password.", "error")
        elif user['status'] == 'pending':
            flash("Your account is pending admin approval.", "error")
        else:
            session['user'] = email
            session['role'] = user['role']
            session['name'] = user['name']
            log_audit("LOGIN", email, "Successful login.")
            
            if user['role'] == 'super_admin': return redirect(url_for('super_admin'))
            elif user['role'] == 'club_admin': return redirect(url_for('club_admin'))
            else: return redirect(url_for('student_dashboard'))
    return render_template('login.html')

@app.route('/super_admin', methods=['GET', 'POST'])
def super_admin():
    global members, clubs, audit_logs
    if 'user' not in session or session.get('role') != 'super_admin': return redirect(url_for('login'))
        
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'approve_user':
            email = request.form.get('email')
            if email in users:
                users[email]['status'] = 'approved'
                if users[email]['role'] == 'student' and users[email].get('club'):
                    members.append({'email': email, 'name': users[email]['name'], 'club': users[email]['club'], 'attendance_pct': 100})
                log_audit("APPROVE_USER", session['user'], f"Approved {email}")
                flash(f"User {email} approved successfully.", "success")
                
        elif action == 'create_club':
            clubs.append({
                'id': len(clubs) + 1, 'name': request.form.get('club_name'), 'category': request.form.get('category'),
                'description': request.form.get('description'), 'coordinator': 'None', 'threshold': 75
            })
            log_audit("CREATE_CLUB", session['user'], f"Created {request.form.get('club_name')}")
            flash("New club created successfully.", "success")
            
        elif action == 'edit_club':
            club_id = int(request.form.get('club_id'))
            for c in clubs:
                if c['id'] == club_id:
                    c['name'] = request.form.get('club_name')
                    c['category'] = request.form.get('category')
                    log_audit("EDIT_CLUB", session['user'], f"Edited club details.")
                    flash("Club details updated.", "success")
                    
        elif action == 'assign_coordinator':
            club_id = int(request.form.get('club_id'))
            new_coord = request.form.get('coordinator_email')
            for c in clubs:
                if c['id'] == club_id:
                    c['coordinator'] = new_coord
                    log_audit("ASSIGN_COORD", session['user'], f"Assigned {new_coord} as coordinator.")
                    flash(f"Coordinator reassigned.", "success")

    pending = {k: v for k, v in users.items() if v['status'] == 'pending'}
    coords = {k: v for k, v in users.items() if v['role'] == 'club_admin' and v['status'] == 'approved'}
    return render_template('super_admin.html', name=session['name'], pending_users=pending, clubs=clubs, coords=coords, logs=audit_logs[-10:])

@app.route('/club_admin', methods=['GET', 'POST'])
def club_admin():
    global members, events, attendance_records, correction_requests
    if 'user' not in session or session.get('role') != 'club_admin': return redirect(url_for('login'))
        
    my_club = next((c for c in clubs if c['coordinator'] == session['user']), None)
    if not my_club:
        flash("Not assigned to a club.", "error")
        return redirect(url_for('login'))

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_student':
            student_email = request.form.get('student_email')
            if student_email in users and users[student_email]['role'] == 'student':
                members.append({'email': student_email, 'name': users[student_email]['name'], 'club': my_club['name'], 'attendance_pct': 100})
                flash("Student added to roster.", "success")
                
        elif action == 'remove_student':
            student_email = request.form.get('student_email')
            members = [m for m in members if m['email'] != student_email]
            flash("Student removed.", "success")
            
        elif action == 'create_event':
            new_code = str(random.randint(100000, 999999))
            expiration_time = datetime.now() + timedelta(minutes=15)
            
            events.append({
                'id': len(events)+1, 'club': my_club['name'], 'name': request.form.get('event_name'),
                'date': request.form.get('date'), 'start_time': request.form.get('start_time'),
                'end_time': request.form.get('end_time'), 'venue': request.form.get('venue'),
                'code': new_code, 'status': 'Active', 'expires_at': expiration_time
            })
            flash(f"Success! Event Scheduled. Code: {new_code} (Valid for 15 mins)", "success")
            
        elif action == 'cancel_event':
            event_id = int(request.form.get('event_id'))
            for e in events:
                if e['id'] == event_id: e['status'] = 'Cancelled'
            flash("Event cancelled.", "success")

        elif action == 'manual_override':
            email = request.form.get('student_email')
            event_name = request.form.get('event_name')
            status = request.form.get('status')
            reason = request.form.get('reason')
            
            existing = next((r for r in attendance_records if r['email'] == email and r['event'] == event_name), None)
            if existing:
                existing['status'] = status
                existing['reason'] = reason
            else:
                attendance_records.append({'email': email, 'event': event_name, 'status': status, 'reason': reason})
                
            log_audit("MANUAL_OVERRIDE", session['user'], f"Marked {email} as {status} for {event_name}")
            flash(f"Manual override applied for {event_name}.", "success")
            
        elif action == 'set_threshold':
            my_club['threshold'] = int(request.form.get('threshold'))
            flash(f"Threshold updated to {my_club['threshold']}%", "success")
            
        elif action == 'resolve_request':
            req_id = int(request.form.get('request_id'))
            for r in correction_requests:
                if r['id'] == req_id: r['status'] = 'Resolved'
            flash("Ticket marked as resolved.", "success")

    recalc_attendance()
    
    my_members = [m for m in members if m['club'] == my_club['name']]
    my_events = [e for e in events if e['club'] == my_club['name']]
    flagged = [m for m in my_members if m['attendance_pct'] < my_club.get('threshold', 75)]
    my_requests = [r for r in correction_requests if r['club'] == my_club['name'] and r['status'] == 'Pending']
    
    my_event_names = [e['name'] for e in my_events]
    club_records = [r for r in attendance_records if r['event'] in my_event_names]
    
    return render_template('club_admin.html', name=session['name'], club=my_club, members=my_members, events=my_events, flagged=flagged, requests=my_requests, attendance=club_records)

@app.route('/student_dashboard', methods=['GET', 'POST'])
def student_dashboard():
    global attendance_records, correction_requests
    if 'user' not in session or session.get('role') != 'student': return redirect(url_for('login'))
        
    student_email = session['user']
    student_user = users.get(student_email)
    student_club = student_user.get('club') if student_user else 'None'
    club_events = [e for e in events if e.get('club') == student_club and e.get('status') == 'Active']
        
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'mark_attendance':
            code = request.form.get('code')
            valid_event = next((e for e in club_events if e['code'] == code), None)
            
            if valid_event:
                # NEW TIMEOUT LOGIC: Checks if current time is past the expires_at timestamp
                if 'expires_at' in valid_event and datetime.now() > valid_event['expires_at']:
                    flash("❌ This Session Code has expired (15-minute limit exceeded).", "error")
                elif any(r['email'] == student_email and r['event'] == valid_event['name'] for r in attendance_records):
                    flash("You have already marked attendance for this session.", "error")
                else:
                    attendance_records.append({'email': student_email, 'event': valid_event['name'], 'status': 'Present', 'reason': 'System Code'})
                    flash(f"✓ Attendance Verified for {valid_event['name']}!", "success")
            else:
                flash("❌ Invalid or Cancelled Session Code", "error")
                
        elif action == 'submit_correction':
            correction_requests.append({
                'id': len(correction_requests)+1, 'email': student_email, 'club': student_club,
                'event': request.form.get('event_name'), 'reason': request.form.get('reason'), 'status': 'Pending'
            })
            flash("Correction request submitted to your Club Admin.", "success")

    recalc_attendance()
    my_member_record = next((m for m in members if m['email'] == student_email), None)
    current_pct = my_member_record['attendance_pct'] if my_member_record else 100
    attended_count = sum(1 for r in attendance_records if r['email'] == student_email and r['status'] in ['Present', 'Excused'])

    student_stats = {
        'total_clubs': 1,
        'workshops_attended': attended_count,
        'avg_attendance': current_pct,
        'memberships': [
            {'name': student_club, 'attended': attended_count, 'total': len(club_events), 'percentage': current_pct, 'role': 'Active Member'}
        ]
    }

    my_records = [r for r in attendance_records if r['email'] == student_email]
    return render_template('student_dashboard.html', name=session['name'], club=student_club, events=club_events, records=my_records, stats=student_stats)

@app.route('/report/export')
def export_report():
    if 'user' not in session: return redirect(url_for('login'))
    scope = request.args.get('scope')
    recalc_attendance()
    
    def generate():
        data = StringIO()
        writer = csv.writer(data)
        writer.writerow(['CAMPUS SYNC - OFFICIAL ATTENDANCE REPORT'])
        writer.writerow(['Scope:', scope])
        writer.writerow(['Student Name', 'College Email', 'Club', 'Attendance Percentage'])
        
        export_members = members if scope == 'System-Wide' else [m for m in members if m['club'] == scope]
        for m in export_members:
            writer.writerow([m['name'], m['email'], m['club'], f"{m['attendance_pct']}%"])
            yield data.getvalue()
            data.seek(0)
            data.truncate(0)

    response = Response(generate(), mimetype='text/csv')
    response.headers.set("Content-Disposition", f"attachment; filename=CampusSync_{scope}_Report.csv")
    return response

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)