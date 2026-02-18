import sqlite3
from datetime import datetime

class AttendanceDB:
    def __init__(self, db_file='attendance.db'):
        self.db_file = db_file
        self.init_database()

    def init_database(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # Create attendance table
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create tasks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                date DATE NOT NULL,
                task_description TEXT NOT NULL,
                has_link BOOLEAN DEFAULT 0,
                deliverable_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        conn.close()
        print("✅ Database initialized successfully!")

    def save_time_in(self, user_id, name, date, time_in):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO attendance (user_id, name, date, time_in, status)
            VALUES (?, ?, ?, ?, 'clocked_in')
        ''', (user_id, name, date, time_in))

        conn.commit()
        conn.close()
        print(f"💾 Saved time-in: {name} at {time_in}")

    def save_time_out(self, user_id, name, date, time_in, time_out, hours_worked):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        # Update existing record or insert new one
        cursor.execute('''
            INSERT OR REPLACE INTO attendance
            (user_id, name, date, time_in, time_out, hours_worked, status)
            VALUES (?, ?, ?, ?, ?, ?, 'complete')
        ''', (user_id, name, date, time_in, time_out, hours_worked))

        conn.commit()
        conn.close()
        print(f"💾 Saved time-out: {name} - {hours_worked} hours worked")

    def save_task(self, user_id, name, date, task_description, deliverable_url=None):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        has_link = 1 if deliverable_url else 0

        cursor.execute('''
            INSERT INTO tasks (user_id, name, date, task_description, has_link, deliverable_url)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, name, date, task_description, has_link, deliverable_url))

        conn.commit()
        conn.close()
        print(f"💾 Saved task: {task_description[:50]}...")

    def get_today_attendance(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT name, time_in, time_out, hours_worked, status
            FROM attendance
            WHERE date = ?
            ORDER BY time_in
        ''', (today,))

        results = cursor.fetchall()
        conn.close()
        return results

# Test the database
if __name__ == '__main__':
    db = AttendanceDB()
    print("Database setup complete!")