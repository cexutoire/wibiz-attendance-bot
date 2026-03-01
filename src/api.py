from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.database import AttendanceDB, USE_POSTGRES

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://db-attendance-and-task-tracking.vercel.app",
        "https://db-attendance-dashboard.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = AttendanceDB()

STAFF_REGISTRY_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'staff_registry.json')

def load_staff_registry():
    try:
        with open(STAFF_REGISTRY_PATH, 'r') as f:
            data = json.load(f)
            return data['staff']
    except FileNotFoundError:
        print("⚠️  Staff registry not found")
        return []

def get_conn():
    """Get a database connection regardless of backend."""
    if USE_POSTGRES:
        import psycopg2
        return psycopg2.connect(db.db_url)
    else:
        import sqlite3
        return sqlite3.connect(db.db_file)

def fix_sql(sql):
    """Convert SQLite syntax to PostgreSQL if needed."""
    if USE_POSTGRES:
        sql = sql.replace('?', '%s')
        sql = sql.replace('"complete"', "'complete'")
        sql = sql.replace('"clocked_in"', "'clocked_in'")
        sql = sql.replace('"on_break"', "'on_break'")
        # PostgreSQL date concat
        sql = sql.replace("date || user_id", "date::text || user_id")
        # PostgreSQL week format (no strftime)
        sql = sql.replace("strftime('%Y-W%W', date)", "to_char(date, 'IYYY-IW')")
        sql = sql.replace("strftime('%Y-%m', date)", "to_char(date, 'YYYY-MM')")
    return sql

@app.get("/")
def root():
    return {"message": "WiBiz Attendance API", "status": "running"}

@app.get("/api/attendance/today")
def get_today_attendance():
    conn = get_conn()
    cursor = conn.cursor()
    pst_now = db.get_current_pst_time()
    today = pst_now.strftime('%Y-%m-%d')
    cursor.execute(fix_sql('''
        SELECT name, time_in, time_out, break_start, break_end,
               break_duration, hours_worked, status
        FROM attendance
        WHERE date = ?
        ORDER BY time_in
    '''), (today,))
    results = cursor.fetchall()
    conn.close()
    data = []
    for name, time_in, time_out, break_start, break_end, break_duration, hours, status in results:
        data.append({
            "name": name,
            "time_in": str(time_in) if time_in else None,
            "time_out": str(time_out) if time_out else None,
            "break_start": str(break_start) if break_start else None,
            "break_end": str(break_end) if break_end else None,
            "break_duration": break_duration,
            "hours_worked": hours,
            "status": status
        })
    return {"data": data}

@app.get("/api/attendance/count")
def get_attendance_count():
    conn = get_conn()
    cursor = conn.cursor()
    pst_now = db.get_current_pst_time()
    today = pst_now.strftime('%Y-%m-%d')
    cursor.execute(fix_sql('''
        SELECT DISTINCT user_id, name FROM attendance WHERE date = ?
    '''), (today,))
    present_staff = cursor.fetchall()
    conn.close()
    all_staff = load_staff_registry()
    active_staff = [s for s in all_staff if s['active']]
    present_ids = {staff[0] for staff in present_staff}
    present = []
    absent = []
    for staff in active_staff:
        if staff['user_id'] in present_ids:
            present.append({"name": staff['name'], "role": staff['role']})
        else:
            absent.append({"name": staff['name'], "role": staff['role']})
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
    conn = get_conn()
    cursor = conn.cursor()
    pst_now = db.get_current_pst_time()
    thirty_days_ago = (pst_now - timedelta(days=30)).strftime('%Y-%m-%d')
    cursor.execute(fix_sql('''
        SELECT date, COUNT(DISTINCT user_id), SUM(hours_worked),
               COUNT(CASE WHEN status = 'complete' THEN 1 END),
               COUNT(CASE WHEN status = 'clocked_in' THEN 1 END)
        FROM attendance WHERE date >= ? GROUP BY date ORDER BY date DESC
    '''), (thirty_days_ago,))
    results = cursor.fetchall()
    conn.close()
    data = []
    for date, staff_count, total_hours, completed, still_working in results:
        data.append({
            "date": str(date),
            "staff_count": staff_count,
            "total_hours": round(total_hours, 1) if total_hours else 0,
            "completed": completed,
            "still_working": still_working
        })
    return {"data": data}

@app.get("/api/attendance/summary/weekly")
def get_weekly_summary():
    conn = get_conn()
    cursor = conn.cursor()
    pst_now = db.get_current_pst_time()
    twelve_weeks_ago = (pst_now - timedelta(weeks=12)).strftime('%Y-%m-%d')
    cursor.execute(fix_sql('''
        SELECT strftime('%Y-W%W', date), MIN(date), MAX(date),
               COUNT(DISTINCT user_id), COUNT(DISTINCT date || user_id),
               SUM(hours_worked), AVG(hours_worked)
        FROM attendance WHERE date >= ? AND status = 'complete'
        GROUP BY strftime('%Y-W%W', date) ORDER BY 1 DESC
    '''), (twelve_weeks_ago,))
    results = cursor.fetchall()
    conn.close()
    data = []
    for week, week_start, week_end, unique_staff, days_worked, total_hours, avg_hours in results:
        data.append({
            "week": week, "week_start": str(week_start), "week_end": str(week_end),
            "unique_staff": unique_staff, "days_worked": days_worked,
            "total_hours": round(total_hours, 1) if total_hours else 0,
            "avg_hours_per_day": round(avg_hours, 1) if avg_hours else 0
        })
    return {"data": data}

@app.get("/api/attendance/summary/monthly")
def get_monthly_summary():
    conn = get_conn()
    cursor = conn.cursor()
    pst_now = db.get_current_pst_time()
    twelve_months_ago = (pst_now - timedelta(days=365)).strftime('%Y-%m-%d')
    cursor.execute(fix_sql('''
        SELECT strftime('%Y-%m', date), COUNT(DISTINCT user_id),
               COUNT(DISTINCT date || user_id), SUM(hours_worked),
               AVG(hours_worked), SUM(break_duration)
        FROM attendance WHERE date >= ? AND status = 'complete'
        GROUP BY strftime('%Y-%m', date) ORDER BY 1 DESC
    '''), (twelve_months_ago,))
    results = cursor.fetchall()
    conn.close()
    data = []
    for month, unique_staff, days_worked, total_hours, avg_hours, break_hours in results:
        date_obj = datetime.strptime(str(month), '%Y-%m')
        data.append({
            "month": month,
            "month_name": date_obj.strftime('%B %Y'),
            "unique_staff": unique_staff,
            "days_worked": days_worked,
            "total_hours": round(total_hours, 1) if total_hours else 0,
            "avg_hours_per_day": round(avg_hours, 1) if avg_hours else 0,
            "total_break_hours": round(break_hours, 1) if break_hours else 0
        })
    return {"data": data}

@app.get("/api/attendance/week")
def get_week_attendance():
    conn = get_conn()
    cursor = conn.cursor()
    pst_now = db.get_current_pst_time()
    today = pst_now.date()
    monday = today - timedelta(days=today.weekday())
    cursor.execute(fix_sql('''
        SELECT name, SUM(hours_worked), COUNT(*)
        FROM attendance WHERE date >= ? AND status = 'complete'
        GROUP BY name ORDER BY 2 DESC
    '''), (monday.strftime('%Y-%m-%d'),))
    results = cursor.fetchall()
    conn.close()
    data = []
    for name, total_hours, days in results:
        data.append({
            "name": name,
            "total_hours": round(total_hours, 1) if total_hours else 0,
            "days_worked": days
        })
    return {"data": data}

@app.get("/api/tasks/today")
def get_today_tasks():
    conn = get_conn()
    cursor = conn.cursor()
    pst_now = db.get_current_pst_time()
    today = pst_now.strftime('%Y-%m-%d')
    cursor.execute(fix_sql('''
        SELECT name, task_description, deliverable_url, created_at
        FROM tasks WHERE date = ? ORDER BY created_at DESC
    '''), (today,))
    results = cursor.fetchall()
    conn.close()
    data = []
    for name, task, url, created_at in results:
        data.append({"name": name, "task": task, "url": url, "created_at": str(created_at)})
    return {"data": data}

@app.get("/api/stats")
def get_stats():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM attendance')
    total_attendance = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM tasks')
    total_tasks = cursor.fetchone()[0]
    cursor.execute(fix_sql('''
        SELECT SUM(hours_worked) FROM attendance WHERE status = 'complete'
    '''))
    total_hours = cursor.fetchone()[0] or 0
    pst_now = db.get_current_pst_time()
    today = pst_now.date()
    monday = today - timedelta(days=today.weekday())
    cursor.execute(fix_sql('''
        SELECT SUM(hours_worked) FROM attendance
        WHERE date >= ? AND status = 'complete'
    '''), (monday.strftime('%Y-%m-%d'),))
    week_hours = cursor.fetchone()[0] or 0
    cursor.execute(fix_sql('''
        SELECT COUNT(DISTINCT user_id) FROM attendance
        WHERE date = ? AND status = 'clocked_in'
    '''), (today.strftime('%Y-%m-%d'),))
    currently_working = cursor.fetchone()[0]
    cursor.execute(fix_sql('''
        SELECT COUNT(DISTINCT user_id) FROM attendance
        WHERE date = ? AND status = 'on_break'
    '''), (today.strftime('%Y-%m-%d'),))
    on_break = cursor.fetchone()[0]
    conn.close()
    return {
        "total_attendance": total_attendance,
        "total_tasks": total_tasks,
        "total_hours": round(total_hours, 1),
        "week_hours": round(week_hours, 1),
        "currently_working": currently_working,
        "on_break": on_break
    }

# ✅ NO uvicorn.run() here — Vercel handles this automatically