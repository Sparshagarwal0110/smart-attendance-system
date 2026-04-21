from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
from flask_session import Session
import hashlib
import os
import numpy as np
import cv2
import face_recognition
from datetime import datetime
from utils.db_utils import *
from utils.face_utils import get_face_encoding_from_image_bytes, recognize_face, passive_liveness_multi
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'hospital-secret-key-change'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

init_db()

# Create default admin if not exists
if not get_user_by_username("admin"):
    add_user("admin", hash_password("admin123"), "admin")

def login_required(role=None):
    def decorator(f):
        def wrapper(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                return "Access denied", 403
            return f(*args, **kwargs)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator

# ------------------- Auth -------------------
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = get_user_by_username(username)
        if user and user['password_hash'] == hash_password(password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role_name']
            session['related_employee_id'] = user['related_employee_id']
            if user['role_name'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role_name'] == 'hod':
                return redirect(url_for('hod_dashboard'))
            else:
                return redirect(url_for('employee_dashboard'))
        else:
            return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ------------------- Admin -------------------
@app.route('/admin')
@login_required(role='admin')
def admin_dashboard():
    total = get_total_employees()
    present = get_today_attendance_count()
    percent = get_today_attendance_percentage()
    return render_template('admin_dashboard.html', username=session['username'],
                          total_employees=total, present_today=present, attendance_percent=percent)

@app.route('/admin/users')
@login_required(role='admin')
def admin_users():
    users = list_users()
    employees = get_all_employee_records()
    return render_template('admin_users.html', users=users, employees=employees)

@app.route('/admin/add_user', methods=['POST'])
@login_required(role='admin')
def admin_add_user():
    username = request.form['username']
    password = request.form['password']
    role = request.form['role']
    if role == 'employee':
        emp_id = request.form['employee_id']
        name = request.form['name']
        designation = request.form['designation']
        work_dept = request.form['work_department']
        join_year = request.form['joining_year']
        existing = get_employee_by_id(emp_id)
        if existing:
            # Cleanup old attendance and update employee record
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM attendance WHERE employee_id = ?", (emp_id,))
            cursor.execute("UPDATE employees SET name=?, designation=?, work_department=?, joining_year=?, face_encoding=NULL WHERE employee_id=?",
                           (name, designation, work_dept, int(join_year), emp_id))
            conn.commit()
            conn.close()
            if add_user(username, hash_password(password), role, emp_id):
                return redirect(url_for('admin_users'))
            else:
                return "Username exists", 400
        else:
            if add_employee(emp_id, name, designation, work_dept, int(join_year)):
                if add_user(username, hash_password(password), role, emp_id):
                    return redirect(url_for('admin_users'))
                else:
                    return "Username exists, employee record created but user not added", 400
            else:
                return "Employee ID already exists", 400
    else:
        if add_user(username, hash_password(password), role, None):
            return redirect(url_for('admin_users'))
        else:
            return "Username exists", 400

@app.route('/admin/remove_user/<username>')
@login_required(role='admin')
def admin_remove_user(username):
    if username == 'admin':
        return "Cannot remove default admin", 400
    user = get_user_by_username(username)
    emp_id = user.get('related_employee_id') if user else None
    remove_user(username)
    if emp_id:
        delete_employee_completely(emp_id)
    return redirect(url_for('admin_users'))

@app.route('/admin/employees')
@login_required(role='admin')
def admin_employees():
    employees = get_all_employee_records()
    return render_template('admin_employees.html', employees=employees)

@app.route('/admin/departments')
@login_required(role='admin')
def admin_departments():
    depts = get_all_departments()
    for d in depts:
        d['hods'] = get_hods_for_department(d['id'])
    users = list_users()
    hods = [u for u in users if u['role_name'] == 'hod']
    return render_template('admin_departments.html', departments=depts, hods=hods)

@app.route('/admin/add_department', methods=['POST'])
@login_required(role='admin')
def admin_add_department():
    code = request.form['dept_code']
    name = request.form['dept_name']
    shift = request.form['shift_timing']
    if add_department(code, name, shift):
        return redirect(url_for('admin_departments'))
    else:
        return "Department code already exists", 400

@app.route('/admin/assign_hod', methods=['POST'])
@login_required(role='admin')
def admin_assign_hod():
    hod_id = request.form['hod_id']
    dept_id = request.form['department_id']
    if assign_hod_to_department(int(hod_id), int(dept_id)):
        return redirect(url_for('admin_departments'))
    else:
        return "HOD already assigned to this department", 400

@app.route('/admin/attendance')
@login_required(role='admin')
def admin_attendance():
    start = request.args.get('start_date')
    end = request.args.get('end_date')
    dept_id = request.args.get('department_id', type=int)
    if start and end:
        records = get_attendance_by_date_range(start, end, dept_id)
    else:
        date = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))
        records = get_attendance_by_date_and_department(date, dept_id)
        start = end = date
    departments = get_all_departments()
    return render_template('view_attendance.html', records=records, role='admin',
                          departments=departments, selected_dept=dept_id,
                          start_date=start, end_date=end)

@app.route('/admin/attendance/export_pdf')
@login_required(role='admin')
def admin_export_pdf():
    start = request.args.get('start_date')
    end = request.args.get('end_date')
    dept_id = request.args.get('department_id', type=int)
    if not start or not end:
        return "Missing date range", 400
    records = get_attendance_by_date_range(start, end, dept_id)
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    elements = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1)
    title = Paragraph(f"Hospital Attendance Report ({start} to {end})", title_style)
    elements.append(title)
    elements.append(Spacer(1, 0.2*inch))
    data = [['Name', 'Employee ID', 'Department', 'Date', 'Time In', 'Status', 'Notes']]
    for r in records:
        data.append([r['name'], r['employee_id'], r['dept_code'], r['date'], r['time_in'], r['status'], r.get('shift_notes', '')])
    table = Table(data)
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.grey), ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
                               ('ALIGN',(0,0),(-1,-1),'CENTER'), ('GRID',(0,0),(-1,-1),1,colors.black)]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return Response(buffer, mimetype='application/pdf', headers={'Content-Disposition': f'attachment;filename=attendance_{start}_to_{end}.pdf'})

@app.route('/admin/stats')
@login_required(role='admin')
def admin_stats():
    depts = get_all_departments()
    return render_template('admin_stats.html', username=session['username'], departments=depts)

@app.route('/admin/stats/data')
@login_required(role='admin')
def admin_stats_data():
    dept_id = request.args.get('department_id', type=int)
    daily = get_attendance_stats_by_department(dept_id, 30)
    if dept_id:
        emp_pct = get_employee_attendance_percentage_by_department(dept_id)
    else:
        emp_pct = []
        # For all departments we can combine or leave empty
    return jsonify({'daily': daily, 'employee_percentages': emp_pct})

# ------------------- HOD (Head of Department) -------------------
@app.route('/hod')
@login_required(role='hod')
def hod_dashboard():
    hod_id = session['user_id']
    depts = get_hod_departments(hod_id)
    # Aggregate stats for all assigned departments
    total_present = 0
    for d in depts:
        total_present += get_today_attendance_count(d['id'])
    total_employees = get_total_employees()
    percent = round((total_present / total_employees) * 100, 1) if total_employees else 0
    return render_template('hod_dashboard.html', username=session['username'],
                          departments=depts, present_today=total_present, attendance_percent=percent)

@app.route('/hod/attendance/start')
@login_required(role='hod')
def hod_attendance_camera():
    hod_id = session['user_id']
    depts = get_hod_departments(hod_id)
    if not depts:
        return "No departments assigned to you. Contact admin.", 400
    return render_template('attendance_camera.html', departments=depts)

@app.route('/hod/attendance/recognize', methods=['POST'])
@login_required(role='hod')
def hod_recognize():
    dept_id = request.form.get('department_id')
    if not dept_id:
        return jsonify({'error': 'Department not selected'}), 400
    if 'image' not in request.files:
        return jsonify({'error': 'No image'}), 400
    img_bytes = request.files['image'].read()
    known_emps = get_all_employees()
    if not known_emps:
        return jsonify({'error': 'No registered employees'}), 400
    result = recognize_face(img_bytes, known_emps)
    if result:
        dept = get_department_by_id(int(dept_id))
        if not dept:
            return jsonify({'error': 'Invalid department'}), 400
        success = mark_attendance(result['employee_id'], int(dept_id), dept['dept_code'])
        return jsonify({
            'recognized': True,
            'name': result['name'],
            'employee_id': result['employee_id'],
            'already_marked': not success,
            'department': dept['dept_code']
        })
    else:
        return jsonify({'recognized': False, 'reason': 'Face not recognized'}), 200

@app.route('/hod/attendance/view')
@login_required(role='hod')
def hod_view_attendance():
    hod_id = session['user_id']
    my_depts = get_hod_departments(hod_id)
    dept_ids = [d['id'] for d in my_depts]
    start = request.args.get('start_date')
    end = request.args.get('end_date')
    dept_id = request.args.get('department_id', type=int)
    if dept_id and dept_id not in dept_ids:
        return "Access denied", 403
    if start and end:
        records = get_attendance_by_date_range(start, end, dept_id)
    else:
        date = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))
        records = get_attendance_by_date_and_department(date, dept_id)
        start = end = date
    return render_template('view_attendance.html', records=records, role='hod',
                          departments=my_depts, selected_dept=dept_id,
                          start_date=start, end_date=end)

@app.route('/hod/attendance/export_pdf')
@login_required(role='hod')
def hod_export_pdf():
    hod_id = session['user_id']
    my_depts = get_hod_departments(hod_id)
    dept_ids = [d['id'] for d in my_depts]
    start = request.args.get('start_date')
    end = request.args.get('end_date')
    dept_id = request.args.get('department_id', type=int)
    if dept_id and dept_id not in dept_ids:
        return "Access denied", 403
    if not start or not end:
        return "Missing date range", 400
    records = get_attendance_by_date_range(start, end, dept_id)
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    elements = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1)
    title = Paragraph(f"Department Attendance Report ({start} to {end})", title_style)
    elements.append(title)
    elements.append(Spacer(1, 0.2*inch))
    data = [['Name', 'Employee ID', 'Date', 'Time In', 'Status', 'Notes']]
    for r in records:
        data.append([r['name'], r['employee_id'], r['date'], r['time_in'], r['status'], r.get('shift_notes', '')])
    table = Table(data)
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.grey), ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
                               ('ALIGN',(0,0),(-1,-1),'CENTER'), ('GRID',(0,0),(-1,-1),1,colors.black)]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return Response(buffer, mimetype='application/pdf', headers={'Content-Disposition': f'attachment;filename=attendance_{start}_to_{end}.pdf'})

@app.route('/hod/register_face')
@login_required(role='hod')
def hod_register_face():
    employees = get_all_employee_records()
    return render_template('register_face.html', employees=employees)

@app.route('/hod/register_face/live')
@login_required(role='hod')
def hod_register_face_live():
    employees = get_all_employee_records()
    return render_template('register_face_live.html', employees=employees)

@app.route('/hod/register_face/capture', methods=['POST'])
@login_required(role='hod')
def hod_register_face_capture():
    employee_id = request.form.get('employee_id')
    if 'face_image' not in request.files:
        return jsonify({'success': False, 'error': 'No image uploaded'})
    file = request.files['face_image']
    image_bytes = file.read()
    encoding = get_face_encoding_from_image_bytes(image_bytes)
    if encoding is None:
        return jsonify({'success': False, 'error': 'No face detected in the image. Please try again with better lighting.'})
    update_face_encoding(employee_id, encoding)
    return jsonify({'success': True})

@app.route('/hod/register_face/submit', methods=['POST'])
@login_required(role='hod')
def hod_submit_face():
    emp_id = request.form['employee_id']
    if 'face_image' not in request.files:
        return "No image", 400
    img_bytes = request.files['face_image'].read()
    encoding = get_face_encoding_from_image_bytes(img_bytes)
    if encoding is None:
        return "No face detected", 400
    update_face_encoding(emp_id, encoding)
    return redirect(url_for('hod_register_face', success=emp_id))

@app.route('/hod/stats')
@login_required(role='hod')
def hod_stats():
    hod_id = session['user_id']
    depts = get_hod_departments(hod_id)
    return render_template('hod_stats.html', username=session['username'], departments=depts)

@app.route('/hod/stats/data')
@login_required(role='hod')
def hod_stats_data():
    dept_id = request.args.get('department_id', type=int)
    if not dept_id:
        return jsonify({'error': 'Department required'}), 400
    daily = get_attendance_stats_by_department(dept_id, 30)
    return jsonify({'daily': daily})

# ------------------- Employee -------------------
@app.route('/employee')
@login_required(role='employee')
def employee_dashboard():
    emp_id = session['related_employee_id']
    records = get_employee_attendance(emp_id)
    return render_template('employee_dashboard.html', username=session['username'], records=records)

@app.route('/employee/attendance_data')
@login_required(role='employee')
def employee_attendance_data():
    emp_id = session['related_employee_id']
    records = get_employee_attendance(emp_id)
    return jsonify(records)

@app.route('/employee/export_csv')
@login_required(role='employee')
def employee_export_csv():
    import csv
    from io import StringIO
    emp_id = session['related_employee_id']
    records = get_employee_attendance(emp_id)
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Date', 'Time In', 'Status', 'Department', 'Shift Notes'])
    for r in records:
        cw.writerow([r['date'], r['time_in'], r['status'], r['dept_code'], r.get('shift_notes', '')])
    output = si.getvalue()
    return Response(output, mimetype='text/csv', headers={"Content-Disposition": f"attachment;filename=attendance_{emp_id}.csv"})

if __name__ == '__main__':
    app.run(debug=True)