from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.database import AttendanceDB
import sqlite3
from datetime import datetime, timedelta
import json
import os

app = FastAPI()

# Updated CORS for both local development and your Vercel production URL
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://db-attendance-and-task-tracking.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = AttendanceDB()

# Path fix for Vercel environment
STAFF_REGISTRY_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'staff_registry.json')

def load_staff_registry():
    """Load staff registry from JSON file"""
    try:
        if not os.path.exists(STAFF_REGISTRY_PATH):
            return []
        with open(STAFF_REGISTRY_PATH, 'r') as f:
            data = json.load(f)
            return data.get('staff', [])
    except Exception as e:
        print(f"⚠️ Error loading registry: {e}")
        return []

@app.get("/")
def root():
    return {"message": "WiBiz Attendance API", "status": "running on Vercel"}

@app.get("/api/attendance/today")
def get_today_attendance():
    conn = sqlite3.connect(db.db_file)
    cursor = conn.cursor()
    pst_now = db.get_current_pst_time()
    today = pst_now.strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT name, time_in, time_out, break_start, break_end, 
               break_duration, hours_worked, status
        FROM attendance
        WHERE date = ?
        ORDER BY time_in
    ''', (today,))
    results = cursor.fetchall()
    conn.close()
    data = [{"name": r[0], "time_in": r[1], "time_out": r[2], "break_start": r[3], 
             "break_end": r[4], "break_duration": r[5], "hours_worked": r[6], "status": r[7]} for r in results]
    return {"data": data}

@app.get("/api/attendance/count")
def get_attendance_count():
    conn = sqlite3.connect(db.db_file)
    cursor = conn.cursor()
    pst_now = db.get_current_pst_time()
    today = pst_now.strftime('%Y-%m-%d')
    cursor.execute('SELECT DISTINCT user_id FROM attendance WHERE date = ?', (today,))
    present_ids = {row[0] for row in cursor.fetchall()}
    conn.close()
    all_staff = load_staff_registry()
    active_staff = [s for s in all_staff if s.get('active')]
    present = [s for s in active_staff if s['user_id'] in present_ids]
    absent = [s for s in active_staff if s['user_id'] not in present_ids]
    return {
        "date": today,
        "total_staff": len(active_staff),
        "present_count": len(present),
        "absent_count": len(absent),
        "present": present,
        "absent": absent
    }

@app.get("/api/attendance/summary/daily")
def get_daily_summary():
    conn = sqlite3.connect(db.db_file)
    cursor = conn.cursor()
    pst_now = db.get_current_pst_time()
    thirty_days_ago = (pst_now - timedelta(days=30)).strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT date, COUNT(DISTINCT user_id), SUM(hours_worked),
               COUNT(CASE WHEN status = 'complete' THEN 1 END),
               COUNT(CASE WHEN status = 'clocked_in' THEN 1 END)
        FROM attendance WHERE date >= ? GROUP BY date ORDER BY date DESC
    ''', (thirty_days_ago,))
    results = cursor.fetchall()
    conn.close()
    data = [{"date": r[0], "staff_count": r[1], "total_hours": round(r[2] or 0, 1), 
             "completed": r[3], "still_working": r[4]} for r in results]
    return {"data": data}

@app.get("/api/attendance/summary/weekly")
def get_weekly_summary():
    conn = sqlite3.connect(db.db_file)
    cursor = conn.cursor()
    pst_now = db.get_current_pst_time()
    twelve_weeks_ago = (pst_now - timedelta(weeks=12)).strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT strftime('%Y-W%W', date) as week, MIN(date), MAX(date),
               COUNT(DISTINCT user_id), COUNT(DISTINCT date || user_id),
               SUM(hours_worked), AVG(hours_worked)
        FROM attendance WHERE date >= ? AND status = 'complete'
        GROUP BY week ORDER BY week DESC
    ''', (twelve_weeks_ago,))
    results = cursor.fetchall()
    conn.close()
    data = [{"week": r[0], "week_start": r[1], "week_end": r[2], "unique_staff": r[3],
             "days_worked": r[4], "total_hours": round(r[5] or 0, 1), "avg_hours_per_day": round(r[6] or 0, 1)} for r in results]
    return {"data": data}

@app.get("/api/attendance/summary/monthly")
def get_monthly_summary():
    conn = sqlite3.connect(db.db_file)
    cursor = conn.cursor()
    pst_now = db.get_current_pst_time()
    twelve_months_ago = (pst_now - timedelta(days=365)).strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT strftime('%Y-%m', date) as month, COUNT(DISTINCT user_id),
               COUNT(DISTINCT date || user_id), SUM(hours_worked),
               AVG(hours_worked), SUM(break_duration)
        FROM attendance WHERE date >= ? AND status = 'complete'
        GROUP BY month ORDER BY month DESC
    ''', (twelve_months_ago,))
    results = cursor.fetchall()
    conn.close()
    data = []
    for r in results:
        month_name = datetime.strptime(r[0], '%Y-%m').strftime('%B %Y')
        data.append({"month": r[0], "month_name": month_name, "unique_staff": r[1],
                     "days_worked": r[2], "total_hours": round(r[3] or 0, 1),
                     "avg_hours_per_day": round(r[4] or 0, 1), "total_break_hours": round(r[5] or 0, 1)})
    return {"data": data}

@app.get("/api/attendance/week")
def get_week_attendance():
    conn = sqlite3.connect(db.db_file)
    cursor = conn.cursor()
    pst_now = db.get_current_pst_time()
    monday = (pst_now.date() - timedelta(days=pst_now.date().weekday())).strftime('%Y-%m-%d')
    cursor.execute('''
        SELECT name, SUM(hours_worked), COUNT(*)
        FROM attendance WHERE date >= ? AND status = 'complete'
        GROUP BY name ORDER BY SUM(hours_worked) DESC
    ''', (monday,))
    results = cursor.fetchall()
    conn.close()
    data = [{"name": r[0], "total_hours": round(r[1] or 0, 1), "days_worked": r[2]} for r in results]
    return {"data": data}

@app.get("/api/tasks/today")
def get_today_tasks():
    conn = sqlite3.connect(db.db_file)
    cursor = conn.cursor()
    pst_now = db.get_current_pst_time()
    today = pst_now.strftime('%Y-%m-%d')
    cursor.execute('SELECT name, task_description, deliverable_url, created_at FROM tasks WHERE date = ? ORDER BY created_at DESC', (today,))
    results = cursor.fetchall()
    conn.close()
    data = [{"name": r[0], "task": r[1], "url": r[2], "created_at": r[3]} for r in results]
    return {"data": data}

@app.get("/api/stats")
def get_stats():
    conn = sqlite3.connect(db.db_file)
    cursor = conn.cursor()
    pst_now = db.get_current_pst_time()
    today_str = pst_now.strftime('%Y-%m-%d')
    monday_str = (pst_now.date() - timedelta(days=pst_now.date().weekday())).strftime('%Y-%m-%d')
    
    cursor.execute('SELECT COUNT(*) FROM attendance')
    total_att = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM tasks')
    total_tasks = cursor.fetchone()[0]
    cursor.execute('SELECT SUM(hours_worked) FROM attendance WHERE status = "complete"')
    total_hrs = cursor.fetchone()[0] or 0
    cursor.execute('SELECT SUM(hours_worked) FROM attendance WHERE date >= ? AND status = "complete"', (monday_str,))
    wk_hrs = cursor.fetchone()[0] or 0
    cursor.execute('SELECT COUNT(DISTINCT user_id) FROM attendance WHERE date = ? AND status = "clocked_in"', (today_str,))
    working = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(DISTINCT user_id) FROM attendance WHERE date = ? AND status = "on_break"', (today_str,))
    breaks = cursor.fetchone()[0]
    conn.close()
    return {
        "total_attendance": total_att, "total_tasks": total_tasks, "total_hours": round(total_hrs, 1),
        "week_hours": round(wk_hrs, 1), "currently_working": working, "on_break": breaks
    }