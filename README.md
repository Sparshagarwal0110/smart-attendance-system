# Smart Attendance System using Face Recognition

A web-based attendance system with face recognition, liveness detection, role-based access (Admin, Teacher, Student), multi-subject support, and analytics.

## Features
- Face recognition using `face_recognition` library
- Passive liveness detection (no forced actions)
- Role-based dashboards (Admin, Teacher, Student)
- Multi-subject attendance tracking
- PDF report export
- Date range filtering
- Dashboard summary cards

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
