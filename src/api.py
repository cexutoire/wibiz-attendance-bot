from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.database import AttendanceDB
import sqlite3
from datetime import datetime, timedelta

app = FastAPI()

# Allow React frontend to access the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = AttendanceDB()

@app.get("/")
def root():
    return {"message": "WiBiz Attendance API", "status": "running"}

@app.get("/api/attendance/today")
def get_today_attendance():
    """Get today's attendance records with break info"""
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
    
    data = []
    for name, time_in, time_out, break_start, break_end, break_duration, hours, status in results:
        data.append({
            "name": name,
            "time_in": time_in,
            "time_out": time_out,
            "break_start": break_start,
            "break_end": break_end,
            "break_duration": break_duration,
            "hours_worked": hours,
            "status": status
        })
    
    return {"data": data}

@app.get("/api/attendance/week")
def get_week_attendance():
    """Get this week's attendance summary"""
    conn = sqlite3.connect(db.db_file)
    cursor = conn.cursor()
    
    pst_now = db.get_current_pst_time()
    today = pst_now.date()
    days_since_monday = today.weekday()
    monday = today - timedelta(days=days_since_monday)
    
    cursor.execute('''
        SELECT name, SUM(hours_worked) as total_hours, COUNT(*) as days_worked
        FROM attendance
        WHERE date >= ? AND status = 'complete'
        GROUP BY name
        ORDER BY total_hours DESC
    ''', (monday.strftime('%Y-%m-%d'),))
    
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
    """Get today's tasks"""
    conn = sqlite3.connect(db.db_file)
    cursor = conn.cursor()
    
    pst_now = db.get_current_pst_time()
    today = pst_now.strftime('%Y-%m-%d')
    
    cursor.execute('''
        SELECT name, task_description, deliverable_url, created_at
        FROM tasks
        WHERE date = ?
        ORDER BY created_at DESC
    ''', (today,))
    
    results = cursor.fetchall()
    conn.close()
    
    data = []
    for name, task, url, created_at in results:
        data.append({
            "name": name,
            "task": task,
            "url": url,
            "created_at": created_at
        })
    
    return {"data": data}

@app.get("/api/stats")
def get_stats():
    """Get overall statistics"""
    conn = sqlite3.connect(db.db_file)
    cursor = conn.cursor()
    
    # Total records
    cursor.execute('SELECT COUNT(*) FROM attendance')
    total_attendance = cursor.fetchone()[0]
    
    # Total tasks
    cursor.execute('SELECT COUNT(*) FROM tasks')
    total_tasks = cursor.fetchone()[0]
    
    # Total hours
    cursor.execute('SELECT SUM(hours_worked) FROM attendance WHERE status = "complete"')
    total_hours = cursor.fetchone()[0] or 0
    
    # This week's hours
    pst_now = db.get_current_pst_time()
    today = pst_now.date()
    days_since_monday = today.weekday()
    monday = today - timedelta(days=days_since_monday)
    
    cursor.execute('''
        SELECT SUM(hours_worked)
        FROM attendance
        WHERE date >= ? AND status = "complete"
    ''', (monday.strftime('%Y-%m-%d'),))
    week_hours = cursor.fetchone()[0] or 0
    
    # People currently working
    cursor.execute('''
        SELECT COUNT(DISTINCT user_id)
        FROM attendance
        WHERE date = ? AND status = 'clocked_in'
    ''', (today.strftime('%Y-%m-%d'),))
    currently_working = cursor.fetchone()[0]
    
    # People on break
    cursor.execute('''
        SELECT COUNT(DISTINCT user_id)
        FROM attendance
        WHERE date = ? AND status = 'on_break'
    ''', (today.strftime('%Y-%m-%d'),))
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)