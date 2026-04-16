from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_session import Session
import hashlib
import os
import numpy as np
import cv2
import face_recognition
from datetime import datetime
from utils.db_utils import (
    init_db, get_user_by_username, add_user, remove_user, list_users,
    get_all_students, get_all_student_records, add_student, update_face_encoding,
    get_attendance_by_date, get_student_attendance, mark_attendance, get_student_by_id,
    get_attendance_stats, get_student_attendance_percentage,
    get_db_connection, delete_student_and_attendance,
    get_attendance_stats_by_subject,
    get_today_attendance_count,
    get_total_students,
    get_today_attendance_percentage,
    get_attendance_by_date_range,
    get_student_attendance_percentage_by_subject,
    add_subject, get_all_subjects, get_subject_by_code, get_subject_by_id,
    assign_teacher_to_subject, remove_teacher_subject, get_teacher_subjects,
    get_subject_students, mark_attendance_with_subject,
    get_attendance_by_date_and_subject, get_student_attendance_by_subject,
    get_attendance_stats_by_subject,
    get_teachers_for_subject   # <-- ADD THIS LINE
)
from utils.face_utils import get_face_encoding_from_image_bytes, recognize_face, passive_liveness_multi

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Initialize database on startup
init_db()

# Create default admin user if not exists
if not get_user_by_username("admin"):
    add_user("admin", hash_password("admin123"), "admin")

# ------------------- Authentication decorator -------------------
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

# ------------------- Routes -------------------
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
            session['related_student_id'] = user['related_student_id']
            if user['role_name'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role_name'] == 'teacher':
                return redirect(url_for('teacher_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
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
    total_students = get_total_students()
    present_today = get_today_attendance_count()
    attendance_percentage = get_today_attendance_percentage()
    return render_template('admin_dashboard.html', 
                          username=session['username'],
                          total_students=total_students,
                          present_today=present_today,
                          attendance_percentage=attendance_percentage)

@app.route('/admin/users')
@login_required(role='admin')
def admin_users():
    users = list_users()
    # We still need all students for display, but not for dropdown linking anymore
    all_students = get_all_student_records()
    return render_template('admin_users.html', users=users, students=all_students)

@app.route('/admin/add_user', methods=['POST'])
@login_required(role='admin')
def admin_add_user():
    username = request.form['username']
    password = request.form['password']
    role = request.form['role']
    
    if role == 'student':
        student_id = request.form.get('student_id')
        name = request.form.get('name')
        department = request.form.get('department')
        enrollment_year = request.form.get('enrollment_year')
        
        # Validate student fields
        if not all([student_id, name, department, enrollment_year]):
            return "All student fields are required for student role", 400
        
        # Check if student record already exists
        existing_student = get_student_by_id(student_id)
        if existing_student:
            # Clean up old attendance and face data
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
            cursor.execute("UPDATE students SET face_encoding = NULL, name = ?, department = ?, enrollment_year = ? WHERE student_id = ?", 
                           (name, department, int(enrollment_year), student_id))
            conn.commit()
            conn.close()
            
            if add_user(username, hash_password(password), role, student_id):
                return redirect(url_for('admin_users'))
            else:
                return "Username already exists", 400
        else:
            # Create new student record
            success = add_student(student_id, name, department, int(enrollment_year), face_encoding=None)
            if not success:
                return f"Student ID '{student_id}' could not be created.", 400
            if add_user(username, hash_password(password), role, student_id):
                return redirect(url_for('admin_users'))
            else:
                return "Username already exists. Student record created but user not added.", 400
    else:
        # For admin or teacher: just create user account (no student record)
        if add_user(username, hash_password(password), role, None):
            return redirect(url_for('admin_users'))
        else:
            return "Username already exists", 400

@app.route('/admin/remove_user/<username>')
@login_required(role='admin')
def admin_remove_user(username):
    if username == 'admin':
        return "Cannot remove default admin", 400
    
    user = get_user_by_username(username)
    if not user:
        return "User not found", 404
    
    student_id = user.get('related_student_id')
    
    # Remove the user account
    remove_user(username)
    
    # If this was a student user, delete all student data
    if student_id:
        delete_student_and_attendance(student_id)
        print(f"Removed user {username} and cleaned up student {student_id}")
    
    # Also delete orphaned attendance records? Not needed.
    return redirect(url_for('admin_users'))

@app.route('/admin/attendance')
@login_required(role='admin')
def admin_attendance():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    subject_id = request.args.get('subject_id', type=int)
    
    if start_date and end_date:
        records = get_attendance_by_date_range(start_date, end_date, subject_id)
    else:
        # Default to today if no range
        date = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))
        records = get_attendance_by_date_and_subject(date, subject_id)
        start_date = end_date = date
    
    subjects = get_all_subjects()
    return render_template('view_attendance.html', records=records, role='admin',
                          selected_subject=subject_id, subjects=subjects,
                          start_date=start_date, end_date=end_date)

# REMOVED /admin/students and /admin/add_student_record routes

@app.route('/admin/stats')
@login_required(role='admin')
def admin_stats():
    subjects = get_all_subjects()
    return render_template('admin_stats.html', username=session['username'], subjects=subjects)

@app.route('/admin/stats/data')
@login_required(role='admin')
def admin_stats_data():
    subject_id = request.args.get('subject_id', type=int)
    daily = get_attendance_stats_by_subject(subject_id, days=30)
    if subject_id:
        student_pct = get_student_attendance_percentage_by_subject(subject_id)
    else:
        student_pct = get_student_attendance_percentage()  # existing function for all subjects
    return jsonify({
        'daily': daily,
        'student_percentages': student_pct
    })

# ------------------- Subject Management (Admin only) -------------------
@app.route('/admin/subjects')
@login_required(role='admin')
def admin_subjects():
    subjects = get_all_subjects()
    # Augment each subject with list of teacher usernames
    for subj in subjects:
        subj['teachers'] = get_teachers_for_subject(subj['id'])
    teachers = list_users()
    teacher_list = [t for t in teachers if t['role_name'] == 'teacher']
    return render_template('admin_subjects.html', subjects=subjects, teachers=teacher_list)

@app.route('/admin/add_subject', methods=['POST'])
@login_required(role='admin')
def admin_add_subject():
    subject_code = request.form['subject_code']
    subject_name = request.form['subject_name']
    department = request.form['department']
    semester = request.form['semester']
    if add_subject(subject_code, subject_name, department, int(semester)):
        return redirect(url_for('admin_subjects'))
    else:
        return "Subject code already exists", 400

@app.route('/admin/assign_teacher', methods=['POST'])
@login_required(role='admin')
def admin_assign_teacher():
    teacher_id = request.form.get('teacher_id')
    subject_id = request.form.get('subject_id')
    
    if not teacher_id or not subject_id:
        return "Please select both a teacher and a subject", 400
    
    try:
        teacher_id = int(teacher_id)
        subject_id = int(subject_id)
    except ValueError:
        return "Invalid teacher or subject selection", 400
    
    if assign_teacher_to_subject(teacher_id, subject_id):
        return redirect(url_for('admin_subjects'))
    else:
        return "Teacher already assigned to this subject", 400

@app.route('/admin/remove_teacher_subject/<int:teacher_id>/<int:subject_id>')
@login_required(role='admin')
def admin_remove_teacher_subject(teacher_id, subject_id):
    remove_teacher_subject(teacher_id, subject_id)
    return redirect(url_for('admin_subjects'))

# ------------------- Teacher -------------------
@app.route('/teacher')
@login_required(role='teacher')
def teacher_dashboard():
    teacher_id = session['user_id']
    subjects = get_teacher_subjects(teacher_id)
    # For simplicity, show overall today's attendance (across all subjects taught)
    # Or you could sum per subject
    present_today = get_today_attendance_count()  # modify to filter by teacher's subjects if needed
    total_students = get_total_students()
    attendance_percentage = get_today_attendance_percentage()
    return render_template('teacher_dashboard.html',
                          username=session['username'],
                          present_today=present_today,
                          attendance_percentage=attendance_percentage)

@app.route('/teacher/attendance/start')
@login_required(role='teacher')
def attendance_camera():
    teacher_id = session['user_id']
    subjects = get_teacher_subjects(teacher_id)
    if not subjects:
        return "No subjects assigned to you. Contact admin.", 400
    return render_template('attendance_camera.html', subjects=subjects)

@app.route('/teacher/attendance/recognize_liveness', methods=['POST'])
@login_required(role='teacher')
def recognize_with_liveness():
    """Passive liveness using multiple frames (movement + texture)."""
    subject_id = request.form.get('subject_id')
    if not subject_id:
        return jsonify({'error': 'Subject not selected'}), 400
    
    # Expect 5 frames from frontend
    frame_bytes = []
    for i in range(5):
        key = f'frame{i}'
        if key not in request.files:
            return jsonify({'error': f'Missing {key}'}), 400
        frame_bytes.append(request.files[key].read())
    
    # Check liveness
    is_live, score, reason = passive_liveness_multi(frame_bytes)
    
    if not is_live:
        return jsonify({'recognized': False, 'reason': reason}), 200
    
    # Recognize face using the middle frame
    known_students = get_all_students()
    if not known_students:
        return jsonify({'error': 'No registered students'}), 400
    
    result = recognize_face(frame_bytes[2], known_students)
    if result:
        subject = get_subject_by_id(int(subject_id))
        if not subject:
            return jsonify({'error': 'Invalid subject'}), 400
        success = mark_attendance_with_subject(result['student_id'], int(subject_id), subject['subject_code'])
        return jsonify({
            'recognized': True,
            'name': result['name'],
            'student_id': result['student_id'],
            'already_marked': not success,
            'subject': subject['subject_code'],
            'liveness_score': score,
            'liveness': True
        })
    else:
        return jsonify({'recognized': False, 'reason': 'Face not recognized'}), 200

@app.route('/teacher/attendance/view')
@login_required(role='teacher')
def teacher_view_attendance():
    teacher_id = session['user_id']
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    subject_id = request.args.get('subject_id', type=int)
    
    # Verify teacher has access to subject
    if subject_id:
        teacher_subjects = get_teacher_subjects(teacher_id)
        if not any(s['id'] == subject_id for s in teacher_subjects):
            return "Access denied", 403
    
    if start_date and end_date:
        records = get_attendance_by_date_range(start_date, end_date, subject_id)
    else:
        date = request.args.get('date', datetime.now().strftime("%Y-%m-%d"))
        records = get_attendance_by_date_and_subject(date, subject_id)
        start_date = end_date = date
    
    subjects = get_teacher_subjects(teacher_id)
    return render_template('view_attendance.html', records=records, role='teacher',
                          selected_subject=subject_id, subjects=subjects,
                          start_date=start_date, end_date=end_date)

@app.route('/teacher/register_face')
@login_required(role='teacher')
def teacher_register_face():
    all_students = get_all_student_records()
    return render_template('register_face.html', students=all_students)

@app.route('/teacher/register_face/submit', methods=['POST'])
@login_required(role='teacher')
def submit_face_registration():
    student_id = request.form['student_id']
    if 'face_image' not in request.files:
        return "No image uploaded", 400
    file = request.files['face_image']
    image_bytes = file.read()
    encoding = get_face_encoding_from_image_bytes(image_bytes)
    if encoding is None:
        return "No face detected in image. Please try again.", 400
    update_face_encoding(student_id, encoding)
    return redirect(url_for('teacher_register_face', success=student_id))

@app.route('/teacher/stats')
@login_required(role='teacher')
def teacher_stats():
    teacher_id = session['user_id']
    subjects = get_teacher_subjects(teacher_id)
    return render_template('teacher_stats.html', username=session['username'], subjects=subjects)

@app.route('/teacher/stats/data')
@login_required(role='teacher')
def teacher_stats_data():
    subject_id = request.args.get('subject_id', type=int)
    if not subject_id:
        return jsonify({'error': 'Subject ID required'}), 400
    daily = get_attendance_stats_by_subject(subject_id, days=30)
    return jsonify({'daily': daily})

# ------------------- Student -------------------
@app.route('/student')
@login_required(role='student')
def student_dashboard():
    student_id = session['related_student_id']
    records = get_student_attendance(student_id)
    return render_template('student_dashboard.html', username=session['username'], records=records)

@app.route('/student/attendance_data')
@login_required(role='student')
def student_attendance_data():
    student_id = session['related_student_id']
    records = get_student_attendance(student_id)
    return jsonify(records)

@app.route('/student/export_csv')
@login_required(role='student')
def student_export_csv():
    import csv
    from io import StringIO
    from flask import Response
    student_id = session['related_student_id']
    records = get_student_attendance(student_id)
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Date', 'Time In', 'Status'])
    for rec in records:
        cw.writerow([rec['date'], rec['time_in'], rec['status']])
    output = si.getvalue()
    return Response(output, mimetype='text/csv', headers={"Content-Disposition": f"attachment;filename=attendance_{student_id}.csv"})

from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO
from flask import Response

@app.route('/admin/attendance/export_pdf')
@login_required(role='admin')
def admin_export_pdf():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    subject_id = request.args.get('subject_id', type=int)
    
    if not start_date or not end_date:
        return "Start date and end date required", 400
    
    records = get_attendance_by_date_range(start_date, end_date, subject_id)
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    elements = []
    
    # Title
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1)
    title = Paragraph(f"Attendance Report ({start_date} to {end_date})", title_style)
    elements.append(title)
    elements.append(Spacer(1, 0.2*inch))
    
    # Table data
    data = [['Name', 'Student ID', 'Subject', 'Date', 'Time In', 'Status']]
    for rec in records:
        data.append([
            rec['name'], rec['student_id'], rec['subject_code'],
            rec['date'], rec['time_in'], rec['status']
        ])
    
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    
    return Response(buffer, mimetype='application/pdf', headers={'Content-Disposition': f'attachment;filename=attendance_{start_date}_to_{end_date}.pdf'})

# Similarly for teacher:
@app.route('/teacher/attendance/export_pdf')
@login_required(role='teacher')
def teacher_export_pdf():
    teacher_id = session['user_id']
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    subject_id = request.args.get('subject_id', type=int)
    
    if not start_date or not end_date:
        return "Start date and end date required", 400
    
    # Verify teacher has access to this subject
    if subject_id:
        teacher_subjects = get_teacher_subjects(teacher_id)
        if not any(s['id'] == subject_id for s in teacher_subjects):
            return "Access denied", 403
    
    records = get_attendance_by_date_range(start_date, end_date, subject_id)
    
    # Same PDF generation as above (copy code)
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
    elements = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, alignment=1)
    title = Paragraph(f"Attendance Report ({start_date} to {end_date})", title_style)
    elements.append(title)
    elements.append(Spacer(1, 0.2*inch))
    
    data = [['Name', 'Student ID', 'Subject', 'Date', 'Time In', 'Status']]
    for rec in records:
        data.append([rec['name'], rec['student_id'], rec['subject_code'], rec['date'], rec['time_in'], rec['status']])
    
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 10),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    
    return Response(buffer, mimetype='application/pdf', headers={'Content-Disposition': f'attachment;filename=attendance_{start_date}_to_{end_date}.pdf'})

# ------------------- Run -------------------
if __name__ == '__main__':
    app.run(debug=True)