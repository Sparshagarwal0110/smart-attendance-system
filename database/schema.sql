-- Roles table
CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role_name TEXT UNIQUE NOT NULL
);

INSERT OR IGNORE INTO roles (role_name) VALUES ('admin'), ('hod'), ('employee');

-- Employees table
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    designation TEXT,               -- Doctor, Nurse, Technician, etc.
    work_department TEXT,           -- Cardiology, Emergency, etc.
    joining_year INTEGER,
    face_encoding BLOB,
    registered_on TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Users table (authentication)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role_id INTEGER NOT NULL,
    related_employee_id TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES roles(id),
    FOREIGN KEY (related_employee_id) REFERENCES employees(employee_id)
);

-- Departments / Wards (replaces subjects)
CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dept_code TEXT UNIQUE NOT NULL,
    dept_name TEXT NOT NULL,
    shift_timing TEXT,              -- e.g., "Morning: 9-17", "Evening: 17-1", "Night: 1-9"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- HOD-Department assignment (replaces teacher_subjects)
CREATE TABLE IF NOT EXISTS hod_departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hod_id INTEGER NOT NULL,
    department_id INTEGER NOT NULL,
    FOREIGN KEY (hod_id) REFERENCES users(id),
    FOREIGN KEY (department_id) REFERENCES departments(id),
    UNIQUE(hod_id, department_id)
);

-- Attendance table (includes shift_notes)
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    department_id INTEGER NOT NULL,
    dept_code TEXT NOT NULL,
    date DATE NOT NULL,
    time_in TIME NOT NULL,
    status TEXT DEFAULT 'present',
    shift_notes TEXT,               -- e.g., "Late by 10 min", "Overtime"
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
    FOREIGN KEY (department_id) REFERENCES departments(id),
    UNIQUE(employee_id, department_id, date)
);

CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date);
CREATE INDEX IF NOT EXISTS idx_attendance_employee ON attendance(employee_id);
CREATE INDEX IF NOT EXISTS idx_attendance_department ON attendance(department_id);