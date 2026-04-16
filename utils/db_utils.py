import sqlite3
import pickle
import os
from datetime import datetime

DB_PATH = "database/attendance.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs("database", exist_ok=True)
    conn = get_db_connection()
    with open("database/schema.sql", "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()

# ---------------------- Student & Face Encoding ----------------------
def add_student(student_id, name, department, enrollment_year, face_encoding=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    encoding_blob = pickle.dumps(face_encoding) if face_encoding is not None else None
    try:
        cursor.execute("""
            INSERT INTO students (student_id, name, department, enrollment_year, face_encoding)
            VALUES (?, ?, ?, ?, ?)
        """, (student_id, name, department, enrollment_year, encoding_blob))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def update_face_encoding(student_id, face_encoding):
    conn = get_db_connection()
    cursor = conn.cursor()
    encoding_blob = pickle.dumps(face_encoding)
    cursor.execute("UPDATE students SET face_encoding = ? WHERE student_id = ?", (encoding_blob, student_id))
    conn.commit()
    conn.close()

def get_all_students():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT student_id, name, face_encoding FROM students WHERE face_encoding IS NOT NULL")
    rows = cursor.fetchall()
    students = []
    for row in rows:
        students.append({
            "student_id": row["student_id"],
            "name": row["name"],
            "face_encoding": pickle.loads(row["face_encoding"])
        })
    conn.close()
    return students

def get_student_by_id(student_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_student_records():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT student_id, name, department, enrollment_year, 
               CASE WHEN face_encoding IS NOT NULL THEN 1 ELSE 0 END as has_face
        FROM students
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ---------------------- Attendance ----------------------
def mark_attendance(student_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    now_time = datetime.now().strftime("%H:%M:%S")
    try:
        cursor.execute("""
            INSERT INTO attendance (student_id, date, time_in)
            VALUES (?, ?, ?)
        """, (student_id, today, now_time))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_attendance_by_date(date=None):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.name, s.student_id, a.time_in, a.status
        FROM attendance a
        JOIN students s ON a.student_id = s.student_id
        WHERE a.date = ?
        ORDER BY a.time_in
    """, (date,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_student_attendance(student_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date, time_in, status
        FROM attendance
        WHERE student_id = ?
        ORDER BY date DESC
    """, (student_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ---------------------- User Management ----------------------
def add_user(username, password_hash, role_name, related_student_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO users (username, password_hash, role_id, related_student_id)
            VALUES (?, ?, (SELECT id FROM roles WHERE role_name=?), ?)
        """, (username, password_hash, role_name, related_student_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def remove_user(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0

def list_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.username, r.role_name, u.related_student_id, u.created_at
        FROM users u
        JOIN roles r ON u.role_id = r.id
        ORDER BY u.created_at
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_user_by_username(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.username, u.password_hash, r.role_name, u.related_student_id
        FROM users u
        JOIN roles r ON u.role_id = r.id
        WHERE u.username = ?
    """, (username,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# ---------------------- Statistics ----------------------
def get_attendance_stats(days=30):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date, COUNT(*) as count
        FROM attendance
        WHERE date >= date('now', ?)
        GROUP BY date
        ORDER BY date
    """, (f'-{days} days',))
    rows = cursor.fetchall()
    conn.close()
    return [{'date': row['date'], 'count': row['count']} for row in rows]

def get_student_attendance_percentage():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT date) as total_days FROM attendance")
    total_days = cursor.fetchone()['total_days']
    if total_days == 0:
        return []
    # Only include students that exist in students table (should be fine)
    cursor.execute("""
        SELECT s.student_id, s.name, COUNT(a.id) as present_days
        FROM students s
        LEFT JOIN attendance a ON s.student_id = a.student_id
        GROUP BY s.student_id, s.name
    """)
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        percentage = round((row['present_days'] / total_days) * 100, 1)
        result.append({
            'student_id': row['student_id'],
            'name': row['name'],
            'percentage': percentage,
            'present_days': row['present_days'],
            'total_days': total_days
        })
    return result

def delete_student_and_attendance(student_id):
    """Force delete student and all related attendance records."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Delete attendance first (to avoid foreign key issues)
    cursor.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
    # Then delete the student record
    cursor.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
    conn.commit()
    conn.close()
    print(f"Deleted student {student_id} and all associated attendance records.")

# ---------------------- Subject Management ----------------------
def add_subject(subject_code, subject_name, department, semester):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO subjects (subject_code, subject_name, department, semester)
            VALUES (?, ?, ?, ?)
        """, (subject_code, subject_name, department, semester))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_all_subjects():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subjects ORDER BY subject_code")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_subject_by_code(subject_code):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subjects WHERE subject_code = ?", (subject_code,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def assign_teacher_to_subject(teacher_id, subject_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?)", (teacher_id, subject_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def remove_teacher_subject(teacher_id, subject_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM teacher_subjects WHERE teacher_id = ? AND subject_id = ?", (teacher_id, subject_id))
    conn.commit()
    conn.close()

def get_teacher_subjects(teacher_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id, s.subject_code, s.subject_name, s.department, s.semester
        FROM subjects s
        JOIN teacher_subjects ts ON s.id = ts.subject_id
        WHERE ts.teacher_id = ?
    """, (teacher_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_subject_students(subject_id):
    """Get all students (for a subject) – in a real system, you'd have student_subject enrollment.
       For simplicity, we assume all students are enrolled in all subjects.
       You can extend later."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT student_id, name FROM students")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ---------------------- Updated Attendance Functions ----------------------
def mark_attendance_with_subject(student_id, subject_id, subject_code):
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    now_time = datetime.now().strftime("%H:%M:%S")
    try:
        cursor.execute("""
            INSERT INTO attendance (student_id, subject_id, subject_code, date, time_in)
            VALUES (?, ?, ?, ?, ?)
        """, (student_id, subject_id, subject_code, today, now_time))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_attendance_by_date_and_subject(date=None, subject_id=None):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT s.name, s.student_id, a.time_in, a.status, a.subject_code
        FROM attendance a
        JOIN students s ON a.student_id = s.student_id
        WHERE a.date = ?
    """
    params = [date]
    if subject_id:
        query += " AND a.subject_id = ?"
        params.append(subject_id)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_student_attendance_by_subject(student_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.date, a.time_in, a.status, a.subject_code, s.subject_name
        FROM attendance a
        JOIN subjects s ON a.subject_id = s.id
        WHERE a.student_id = ?
        ORDER BY a.date DESC
    """, (student_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_attendance_stats_by_subject(subject_id=None, days=30):
    """Get daily attendance count for a specific subject or all subjects."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if subject_id:
        cursor.execute("""
            SELECT date, COUNT(*) as count
            FROM attendance
            WHERE subject_id = ? AND date >= date('now', ?)
            GROUP BY date
            ORDER BY date
        """, (subject_id, f'-{days} days'))
    else:
        cursor.execute("""
            SELECT date, COUNT(*) as count
            FROM attendance
            WHERE date >= date('now', ?)
            GROUP BY date
            ORDER BY date
        """, (f'-{days} days',))
    rows = cursor.fetchall()
    conn.close()
    return [{'date': row['date'], 'count': row['count']} for row in rows]

def get_subject_by_id(subject_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subjects WHERE id = ?", (subject_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_teachers_for_subject(subject_id):
    """Return list of teacher usernames assigned to a subject."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.username
        FROM users u
        JOIN teacher_subjects ts ON u.id = ts.teacher_id
        WHERE ts.subject_id = ?
    """, (subject_id,))
    rows = cursor.fetchall()
    conn.close()
    return [row['username'] for row in rows]

def get_attendance_stats_by_subject(subject_id=None, days=30):
    """Get daily attendance count for a specific subject or all subjects."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if subject_id:
        cursor.execute("""
            SELECT date, COUNT(*) as count
            FROM attendance
            WHERE subject_id = ? AND date >= date('now', ?)
            GROUP BY date
            ORDER BY date
        """, (subject_id, f'-{days} days'))
    else:
        cursor.execute("""
            SELECT date, COUNT(*) as count
            FROM attendance
            WHERE date >= date('now', ?)
            GROUP BY date
            ORDER BY date
        """, (f'-{days} days',))
    rows = cursor.fetchall()
    conn.close()
    return [{'date': row['date'], 'count': row['count']} for row in rows]

def get_student_attendance_percentage_by_subject(subject_id):
    """Calculate attendance percentage for each student for a specific subject."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Get total working days for this subject
    cursor.execute("""
        SELECT COUNT(DISTINCT date) as total_days
        FROM attendance
        WHERE subject_id = ?
    """, (subject_id,))
    total_days = cursor.fetchone()['total_days']
    if total_days == 0:
        return []
    cursor.execute("""
        SELECT s.student_id, s.name, COUNT(a.id) as present_days
        FROM students s
        LEFT JOIN attendance a ON s.student_id = a.student_id AND a.subject_id = ?
        GROUP BY s.student_id, s.name
    """, (subject_id,))
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        percentage = round((row['present_days'] / total_days) * 100, 1)
        result.append({
            'student_id': row['student_id'],
            'name': row['name'],
            'percentage': percentage,
            'present_days': row['present_days'],
            'total_days': total_days
        })
    return result

def get_attendance_by_date_range(start_date, end_date, subject_id=None):
    """Get attendance records between two dates, optionally filtered by subject."""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT s.name, s.student_id, a.date, a.time_in, a.status, a.subject_code
        FROM attendance a
        JOIN students s ON a.student_id = s.student_id
        WHERE a.date BETWEEN ? AND ?
    """
    params = [start_date, end_date]
    if subject_id:
        query += " AND a.subject_id = ?"
        params.append(subject_id)
    query += " ORDER BY a.date DESC, a.time_in"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_today_attendance_count(subject_id=None):
    """Get number of students marked present today, optionally by subject."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    cursor = conn.cursor()
    if subject_id:
        cursor.execute("SELECT COUNT(DISTINCT student_id) as count FROM attendance WHERE date = ? AND subject_id = ?", (today, subject_id))
    else:
        cursor.execute("SELECT COUNT(DISTINCT student_id) as count FROM attendance WHERE date = ?", (today,))
    count = cursor.fetchone()['count']
    conn.close()
    return count

def get_total_students():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM students")
    count = cursor.fetchone()['count']
    conn.close()
    return count

def get_today_attendance_percentage(subject_id=None):
    total = get_total_students()
    if total == 0:
        return 0
    present = get_today_attendance_count(subject_id)
    return round((present / total) * 100, 1)