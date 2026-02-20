import sqlite3
from datetime import datetime
import pytz

class AttendanceDB:
    def __init__(self, db_file='attendance.db'):
        self.db_file = db_file
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
        print("✅ Database initialized successfully!")

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

    def save_time_out(self, user_id, name, date, time_in, time_out, hours_worked):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        pst_now = self.get_current_pst_time()
        created_at = pst_now.strftime('%Y-%m-%d %I:%M:%S %p')

        # Delete any existing "clocked_in" records for this user on this date
        cursor.execute('''
            DELETE FROM attendance
            WHERE user_id = ? AND date = ? AND status = 'clocked_in'
        ''', (user_id, date))
        
        # Check if a "complete" record already exists
        cursor.execute('''
            SELECT id FROM attendance
            WHERE user_id = ? AND date = ? AND status = 'complete'
        ''', (user_id, date))
        
        existing_record = cursor.fetchone()
        
        if existing_record:
            # Update existing complete record
            cursor.execute('''
                UPDATE attendance
                SET time_in = ?, time_out = ?, hours_worked = ?, created_at = ?
                WHERE id = ?
            ''', (time_in, time_out, hours_worked, created_at, existing_record[0]))
        else:
            # Insert new complete record
            cursor.execute('''
                INSERT INTO attendance
                (user_id, name, date, time_in, time_out, hours_worked, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'complete', ?)
            ''', (user_id, name, date, time_in, time_out, hours_worked, created_at))

        conn.commit()
        conn.close()

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

if __name__ == '__main__':
    db = AttendanceDB()
    print("Database setup complete!")
    
    pst_time = db.get_current_pst_time()
    print(f"Current PST time: {pst_time.strftime('%Y-%m-%d %I:%M:%S %p')}")