import sqlite3
from datetime import datetime
import pytz
import os

class AttendanceDB:
    def __init__(self, db_file='attendance.db'):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        
        # Use /tmp on serverless environments (Vercel)
        if not os.access(project_root, os.W_OK):
            self.db_file = os.path.join('/tmp', db_file)
        else:
            self.db_file = os.path.join(project_root, db_file)
        
        self.timezone = pytz.timezone('Asia/Manila')
        self.init_database()

    def get_current_pst_time(self):
        """Get current time in PST"""
        utc_now = datetime.now(pytz.utc)
        pst_now = utc_now.astimezone(self.timezone) 
        return pst_now

    def format_time_12hr(self, time_str):
        """Convert time to 12-hour format if needed"""
        if 'AM' in time_str.upper() or 'PM' in time_str.upper():
            return time_str
        
        try:
            time_obj = datetime.strptime(time_str, '%H:%M')
            return time_obj.strftime('%I:%M %p')
        except:
            return time_str

    def init_database(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                date DATE NOT NULL,
                time_in TIME,
                time_out TIME,
                break_start TIME,
                break_end TIME,
                break_duration REAL DEFAULT 0,
                hours_worked REAL,
                status TEXT DEFAULT 'incomplete',
                created_at TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                date DATE NOT NULL,
                task_description TEXT NOT NULL,
                has_link BOOLEAN DEFAULT 0,
                deliverable_url TEXT,
                created_at TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()
        print(f"✅ Database initialized: {self.db_file}")

    def save_time_in(self, user_id, name, date, time_in):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        pst_now = self.get_current_pst_time()
        created_at = pst_now.strftime('%Y-%m-%d %I:%M:%S %p')

        # Check if a record already exists for today
        cursor.execute('''
            SELECT id, status FROM attendance
            WHERE user_id = ? AND date = ?
        ''', (user_id, date))
        
        existing = cursor.fetchone()
        
        if existing:
            # If a complete record exists, don't overwrite it
            if existing[1] == 'complete':
                print(f"⚠️  {name} already has a complete record for today. Ignoring time-in.")
                conn.close()
                return
            
            # Update existing clocked_in record
            cursor.execute('''
                UPDATE attendance
                SET time_in = ?, created_at = ?
                WHERE id = ?
            ''', (time_in, created_at, existing[0]))
        else:
            # Insert new record
            cursor.execute('''
                INSERT INTO attendance (user_id, name, date, time_in, status, created_at)
                VALUES (?, ?, ?, ?, 'clocked_in', ?)
            ''', (user_id, name, date, time_in, created_at))

        conn.commit()
        conn.close()
        print(f'💾 Saved: {name} clocked in at {time_in}')
        print(f'   Database: {self.db_file}')

    def save_time_out(self, user_id, name, date, time_in, time_out, hours_worked):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        pst_now = self.get_current_pst_time()
        created_at = pst_now.strftime('%Y-%m-%d %I:%M:%S %p')

        # Delete any existing "clocked_in" or "on_break" records for this user on this date
        cursor.execute('''
            DELETE FROM attendance
            WHERE user_id = ? AND date = ? AND status IN ('clocked_in', 'on_break')
        ''', (user_id, date))
        
        # Check if a "complete" record already exists
        cursor.execute('''
            SELECT id FROM attendance
            WHERE user_id = ? AND date = ? AND status = 'complete'
        ''', (user_id, date))
        
        existing_record = cursor.fetchone()
        
        # Get break duration if there was a break today
        cursor.execute('''
            SELECT break_duration FROM attendance
            WHERE user_id = ? AND date = ? AND break_duration > 0
            ORDER BY created_at DESC
            LIMIT 1
        ''', (user_id, date))
        
        break_record = cursor.fetchone()
        break_duration = break_record[0] if break_record else 0
        
        # Deduct break time from hours worked
        net_hours = hours_worked - break_duration
        
        if existing_record:
            # Update existing complete record
            cursor.execute('''
                UPDATE attendance
                SET time_in = ?, time_out = ?, hours_worked = ?, break_duration = ?, created_at = ?
                WHERE id = ?
            ''', (time_in, time_out, net_hours, break_duration, created_at, existing_record[0]))
        else:
            # Insert new complete record
            cursor.execute('''
                INSERT INTO attendance
                (user_id, name, date, time_in, time_out, hours_worked, break_duration, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'complete', ?)
            ''', (user_id, name, date, time_in, time_out, net_hours, break_duration, created_at))

        conn.commit()
        conn.close()
        
        if break_duration > 0:
            print(f'🍽️  Break time deducted: {break_duration:.2f} hrs')

    def save_task(self, user_id, name, date, task_description, deliverable_url=None):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        has_link = 1 if deliverable_url else 0
        
        pst_now = self.get_current_pst_time()
        created_at = pst_now.strftime('%Y-%m-%d %I:%M:%S %p')

        cursor.execute('''
            INSERT INTO tasks (user_id, name, date, task_description, has_link, deliverable_url, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, name, date, task_description, has_link, deliverable_url, created_at))

        conn.commit()
        conn.close()

    def get_today_attendance(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        pst_now = self.get_current_pst_time()
        today = pst_now.strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT name, time_in, time_out, hours_worked, status
            FROM attendance
            WHERE date = ?
            ORDER BY time_in
        ''', (today,))

        results = cursor.fetchall()
        conn.close()
        return results
    
    def save_break_start(self, user_id, name, date, break_start):
        """Record when someone starts their break"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        pst_now = self.get_current_pst_time()
        created_at = pst_now.strftime('%Y-%m-%d %I:%M:%S %p')
        
        # Find today's clocked_in record
        cursor.execute('''
            SELECT id FROM attendance
            WHERE user_id = ? AND date = ? AND status = 'clocked_in'
        ''', (user_id, date))
        
        record = cursor.fetchone()
        
        if not record:
            print(f"❌ No clocked_in record found for {name} today")
            conn.close()
            return False
        
        # Update to on_break status
        cursor.execute('''
            UPDATE attendance
            SET break_start = ?, status = 'on_break', created_at = ?
            WHERE id = ?
        ''', (break_start, created_at, record[0]))
        
        conn.commit()
        conn.close()
        print(f'🍽️  {name} started break at {break_start}')
        return True

    def save_break_end(self, user_id, name, date, break_end):
        """Record when someone ends their break"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        pst_now = self.get_current_pst_time()
        created_at = pst_now.strftime('%Y-%m-%d %I:%M:%S %p')
        
        # Find today's on_break record
        cursor.execute('''
            SELECT id, break_start FROM attendance
            WHERE user_id = ? AND date = ? AND status = 'on_break'
        ''', (user_id, date))
        
        record = cursor.fetchone()
        
        if not record:
            print(f"❌ No on_break record found for {name} today")
            conn.close()
            return False
        
        record_id, break_start = record
        
        # Calculate break duration
        try:
            start = datetime.strptime(break_start, '%I:%M %p')
            end = datetime.strptime(break_end, '%I:%M %p')
            
            if end < start:
                from datetime import timedelta
                end = end + timedelta(hours=24)
            
            break_duration = (end - start).total_seconds() / 3600
        except:
            break_duration = 0
        
        # Update back to clocked_in status
        cursor.execute('''
            UPDATE attendance
            SET break_end = ?, break_duration = ?, status = 'clocked_in', created_at = ?
            WHERE id = ?
        ''', (break_end, break_duration, created_at, record_id))
        
        conn.commit()
        conn.close()
        print(f'✅ {name} ended break at {break_end} (duration: {break_duration:.2f} hrs)')
        return True

if __name__ == '__main__':
    db = AttendanceDB()
    print("Database setup complete!")
    
    pst_time = db.get_current_pst_time()
    print(f"Current PST time: {pst_time.strftime('%Y-%m-%d %I:%M:%S %p')}")