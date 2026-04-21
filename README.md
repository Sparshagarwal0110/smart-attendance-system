# 🏥 Hospital Staff Attendance System using Face Recognition

A web-based attendance system for hospitals with face recognition, passive liveness detection, role-based access (Admin, HOD, Employee), department/shift management, and analytics.

## Features

- **Face Recognition** using `face_recognition` library
- **Passive Liveness Detection** – no forced actions, detects natural movement
- **Role-Based Dashboards** – Admin, HOD (Head of Department), Employee
- **Department & Shift Management** – Multiple departments with shift timings
- **Live Face Registration** – Capture employee faces directly from webcam
- **PDF Report Export** – Download attendance reports by date range
- **Date Range Filtering** – View attendance between any two dates
- **Dashboard Summary Cards** – Real-time statistics (total employees, today's present, attendance %)
- **Interactive Charts** – Attendance trends and employee-wise percentages

## Tech Stack
- Flask (Python)
- SQLite
- OpenCV
- face_recognition
- Chart.js

## Installation
1. Clone the repository
2. Create virtual environment: `python -m venv myenv`
3. Activate: `source myenv/bin/activate` (Linux/Mac) or `myenv\Scripts\activate` (Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Run: `python app.py`
6. Access: `http://localhost:5000`
7. Default admin: `admin` / `admin123`

## Author
Sparsh Agarwal – Final Year Project
