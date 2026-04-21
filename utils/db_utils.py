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

# ---------------------- Employee Management ----------------------
def add_employee(employee_id, name, designation, work_department, joining_year, face_encoding=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    encoding_blob = pickle.dumps(face_encoding) if face_encoding is not None else None
    try:
        cursor.execute("""
            INSERT INTO employees (employee_id, name, designation, work_department, joining_year, face_encoding)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (employee_id, name, designation, work_department, joining_year, encoding_blob))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def update_face_encoding(employee_id, face_encoding):
    conn = get_db_connection()
    cursor = conn.cursor()
    encoding_blob = pickle.dumps(face_encoding)
    cursor.execute("UPDATE employees SET face_encoding = ? WHERE employee_id = ?", (encoding_blob, employee_id))
    conn.commit()
    conn.close()

def get_all_employees():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT employee_id, name, face_encoding FROM employees WHERE face_encoding IS NOT NULL")
    rows = cursor.fetchall()
    employees = []
    for row in rows:
        employees.append({
            "employee_id": row["employee_id"],
            "name": row["name"],
            "face_encoding": pickle.loads(row["face_encoding"])
        })
    conn.close()
    return employees

def get_employee_by_id(employee_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM employees WHERE employee_id = ?", (employee_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_employee_records():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT employee_id, name, designation, work_department, joining_year, 
               CASE WHEN face_encoding IS NOT NULL THEN 1 ELSE 0 END as has_face
        FROM employees
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_employee_completely(employee_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM attendance WHERE employee_id = ?", (employee_id,))
    cursor.execute("DELETE FROM employees WHERE employee_id = ?", (employee_id,))
    conn.commit()
    conn.close()

# ---------------------- Department Management ----------------------
def add_department(dept_code, dept_name, shift_timing):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO departments (dept_code, dept_name, shift_timing)
            VALUES (?, ?, ?)
        """, (dept_code, dept_name, shift_timing))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_all_departments():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM departments ORDER BY dept_code")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_department_by_id(dept_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM departments WHERE id = ?", (dept_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_department_by_code(dept_code):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM departments WHERE dept_code = ?", (dept_code,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def assign_hod_to_department(hod_id, department_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO hod_departments (hod_id, department_id) VALUES (?, ?)", (hod_id, department_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def remove_hod_department(hod_id, department_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM hod_departments WHERE hod_id = ? AND department_id = ?", (hod_id, department_id))
    conn.commit()
    conn.close()

def get_hod_departments(hod_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.id, d.dept_code, d.dept_name, d.shift_timing
        FROM departments d
        JOIN hod_departments hd ON d.id = hd.department_id
        WHERE hd.hod_id = ?
    """, (hod_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_hods_for_department(department_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.username
        FROM users u
        JOIN hod_departments hd ON u.id = hd.hod_id
        WHERE hd.department_id = ?
    """, (department_id,))
    rows = cursor.fetchall()
    conn.close()
    return [row['username'] for row in rows]

# ---------------------- Attendance ----------------------
def mark_attendance(employee_id, department_id, dept_code, shift_notes=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    now_time = datetime.now().strftime("%H:%M:%S")
    try:
        cursor.execute("""
            INSERT INTO attendance (employee_id, department_id, dept_code, date, time_in, shift_notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (employee_id, department_id, dept_code, today, now_time, shift_notes))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_attendance_by_date_and_department(date=None, department_id=None):
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT e.name, e.employee_id, a.time_in, a.status, a.dept_code, a.shift_notes
        FROM attendance a
        JOIN employees e ON a.employee_id = e.employee_id
        WHERE a.date = ?
    """
    params = [date]
    if department_id:
        query += " AND a.department_id = ?"
        params.append(department_id)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_attendance_by_date_range(start_date, end_date, department_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT e.name, e.employee_id, a.date, a.time_in, a.status, a.dept_code, a.shift_notes
        FROM attendance a
        JOIN employees e ON a.employee_id = e.employee_id
        WHERE a.date BETWEEN ? AND ?
    """
    params = [start_date, end_date]
    if department_id:
        query += " AND a.department_id = ?"
        params.append(department_id)
    query += " ORDER BY a.date DESC, a.time_in"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_employee_attendance(employee_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date, time_in, status, dept_code, shift_notes
        FROM attendance
        WHERE employee_id = ?
        ORDER BY date DESC
    """, (employee_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ---------------------- User Management ----------------------
def add_user(username, password_hash, role_name, related_employee_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO users (username, password_hash, role_id, related_employee_id)
            VALUES (?, ?, (SELECT id FROM roles WHERE role_name=?), ?)
        """, (username, password_hash, role_name, related_employee_id))
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
        SELECT u.id, u.username, r.role_name, u.related_employee_id, u.created_at
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
        SELECT u.id, u.username, u.password_hash, r.role_name, u.related_employee_id
        FROM users u
        JOIN roles r ON u.role_id = r.id
        WHERE u.username = ?
    """, (username,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# ---------------------- Statistics & Dashboard ----------------------
def get_today_attendance_count(department_id=None):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    cursor = conn.cursor()
    if department_id:
        cursor.execute("SELECT COUNT(DISTINCT employee_id) as count FROM attendance WHERE date = ? AND department_id = ?", (today, department_id))
    else:
        cursor.execute("SELECT COUNT(DISTINCT employee_id) as count FROM attendance WHERE date = ?", (today,))
    count = cursor.fetchone()['count']
    conn.close()
    return count

def get_total_employees():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM employees")
    count = cursor.fetchone()['count']
    conn.close()
    return count

def get_today_attendance_percentage(department_id=None):
    total = get_total_employees()
    if total == 0:
        return 0
    present = get_today_attendance_count(department_id)
    return round((present / total) * 100, 1)

def get_attendance_stats_by_department(department_id=None, days=30):
    conn = get_db_connection()
    cursor = conn.cursor()
    if department_id:
        cursor.execute("""
            SELECT date, COUNT(*) as count
            FROM attendance
            WHERE department_id = ? AND date >= date('now', ?)
            GROUP BY date
            ORDER BY date
        """, (department_id, f'-{days} days'))
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

def get_employee_attendance_percentage_by_department(department_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(DISTINCT date) as total_days FROM attendance WHERE department_id = ?", (department_id,))
    total_days = cursor.fetchone()['total_days']
    if total_days == 0:
        return []
    cursor.execute("""
        SELECT e.employee_id, e.name, COUNT(a.id) as present_days
        FROM employees e
        LEFT JOIN attendance a ON e.employee_id = a.employee_id AND a.department_id = ?
        GROUP BY e.employee_id, e.name
    """, (department_id,))
    rows = cursor.fetchall()
    conn.close()
    result = []
    for row in rows:
        percentage = round((row['present_days'] / total_days) * 100, 1)
        result.append({
            'employee_id': row['employee_id'],
            'name': row['name'],
            'percentage': percentage,
            'present_days': row['present_days'],
            'total_days': total_days
        })
    return result