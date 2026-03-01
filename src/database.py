import os
import pytz
from datetime import datetime

# Detect if we should use PostgreSQL or SQLite
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    import psycopg2
    import psycopg2.extras
    USE_POSTGRES = True
else:
    import sqlite3
    USE_POSTGRES = False


class AttendanceDB:
    def __init__(self, db_file='attendance.db'):
        self.timezone = pytz.timezone('Asia/Manila')

        if USE_POSTGRES:
            self.db_url = DATABASE_URL
            print("✅ Using PostgreSQL (Supabase)")
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            if not os.access(project_root, os.W_OK):
                self.db_file = os.path.join('/tmp', db_file)
            else:
                self.db_file = os.path.join(project_root, db_file)
            print(f"✅ Using SQLite: {self.db_file}")

        self.init_database()

    # ─── Connection helpers ────────────────────────────────────────────────────

    def _get_conn(self):
        if USE_POSTGRES:
            return psycopg2.connect(self.db_url)
        return sqlite3.connect(self.db_file)

    def _placeholder(self):
        """Return the correct paramstyle placeholder."""
        return '%s' if USE_POSTGRES else '?'

    def _fix_sql(self, sql):
        """Convert SQLite ? placeholders to %s for PostgreSQL, and fix AUTOINCREMENT."""
        if USE_POSTGRES:
            sql = sql.replace('?', '%s')
            sql = sql.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
            sql = sql.replace('BOOLEAN', 'BOOLEAN')
        return sql

    def _fetchone(self, cursor):
        row = cursor.fetchone()
        if USE_POSTGRES and row and isinstance(row, tuple):
            return row
        return row

    # ─── Utilities ─────────────────────────────────────────────────────────────

    def get_current_pst_time(self):
        utc_now = datetime.now(pytz.utc)
        return utc_now.astimezone(self.timezone)

    def format_time_12hr(self, time_str):
        if 'AM' in time_str.upper() or 'PM' in time_str.upper():
            return time_str
        try:
            time_obj = datetime.strptime(time_str, '%H:%M')
            return time_obj.strftime('%I:%M %p')
        except:
            return time_str

    # ─── Init ──────────────────────────────────────────────────────────────────

    def init_database(self):
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute(self._fix_sql('''
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
        '''))

        cursor.execute(self._fix_sql('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                date DATE NOT NULL,
                task_description TEXT NOT NULL,
                has_link BOOLEAN DEFAULT FALSE,
                deliverable_url TEXT,
                created_at TIMESTAMP
            )
        '''))

        conn.commit()
        conn.close()
        print("✅ Database initialized")

    # ─── Save time in ──────────────────────────────────────────────────────────

    def save_time_in(self, user_id, name, date, time_in):
        conn = self._get_conn()
        cursor = conn.cursor()

        pst_now = self.get_current_pst_time()
        created_at = pst_now.strftime('%Y-%m-%d %I:%M:%S %p')

        cursor.execute(self._fix_sql('''
            SELECT id, status FROM attendance
            WHERE user_id = ? AND date = ?
        '''), (user_id, date))

        existing = cursor.fetchone()

        if existing:
            if existing[1] == 'complete':
                print(f"⚠️  {name} already has a complete record for today. Ignoring time-in.")
                conn.close()
                return

            cursor.execute(self._fix_sql('''
                UPDATE attendance
                SET time_in = ?, created_at = ?
                WHERE id = ?
            '''), (time_in, created_at, existing[0]))
        else:
            cursor.execute(self._fix_sql('''
                INSERT INTO attendance (user_id, name, date, time_in, status, created_at)
                VALUES (?, ?, ?, ?, 'clocked_in', ?)
            '''), (user_id, name, date, time_in, created_at))

        conn.commit()
        conn.close()
        print(f'💾 Saved: {name} clocked in at {time_in}')

    # ─── Save time out ─────────────────────────────────────────────────────────

    def save_time_out(self, user_id, name, date, time_in, time_out, hours_worked):
        conn = self._get_conn()
        cursor = conn.cursor()

        pst_now = self.get_current_pst_time()
        created_at = pst_now.strftime('%Y-%m-%d %I:%M:%S %p')

        # ✅ STEP 1: Read break_duration BEFORE deleting anything
        cursor.execute(self._fix_sql('''
            SELECT break_duration FROM attendance
            WHERE user_id = ? AND date = ? AND break_duration > 0
            ORDER BY created_at DESC
            LIMIT 1
        '''), (user_id, date))

        break_record = cursor.fetchone()
        break_duration = break_record[0] if break_record else 0

        # ✅ STEP 2: NOW safe to delete the clocked_in/on_break record
        cursor.execute(self._fix_sql('''
            DELETE FROM attendance
            WHERE user_id = ? AND date = ? AND status IN ('clocked_in', 'on_break')
        '''), (user_id, date))

        # ✅ STEP 3: Calculate net hours after deducting break
        net_hours = round(hours_worked - break_duration, 2)

        # Check for existing complete record
        cursor.execute(self._fix_sql('''
            SELECT id FROM attendance
            WHERE user_id = ? AND date = ? AND status = 'complete'
        '''), (user_id, date))

        existing_record = cursor.fetchone()

        if existing_record:
            cursor.execute(self._fix_sql('''
                UPDATE attendance
                SET time_in = ?, time_out = ?, hours_worked = ?, break_duration = ?, created_at = ?
                WHERE id = ?
            '''), (time_in, time_out, net_hours, break_duration, created_at, existing_record[0]))
        else:
            cursor.execute(self._fix_sql('''
                INSERT INTO attendance
                (user_id, name, date, time_in, time_out, hours_worked, break_duration, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'complete', ?)
            '''), (user_id, name, date, time_in, time_out, net_hours, break_duration, created_at))

        conn.commit()
        conn.close()

        if break_duration > 0:
            print(f'🍽️  Break deducted: {break_duration:.2f} hrs → Net hours: {net_hours:.2f} hrs')
        else:
            print(f'ℹ️  No break recorded for {name}')

    # ─── Save task ─────────────────────────────────────────────────────────────

    def save_task(self, user_id, name, date, task_description, deliverable_url=None):
        conn = self._get_conn()
        cursor = conn.cursor()

        has_link = True if deliverable_url else False

        pst_now = self.get_current_pst_time()
        created_at = pst_now.strftime('%Y-%m-%d %I:%M:%S %p')

        cursor.execute(self._fix_sql('''
            INSERT INTO tasks (user_id, name, date, task_description, has_link, deliverable_url, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        '''), (user_id, name, date, task_description, has_link, deliverable_url, created_at))

        conn.commit()
        conn.close()

    # ─── Get today attendance ──────────────────────────────────────────────────

    def get_today_attendance(self):
        conn = self._get_conn()
        cursor = conn.cursor()

        pst_now = self.get_current_pst_time()
        today = pst_now.strftime('%Y-%m-%d')

        cursor.execute(self._fix_sql('''
            SELECT name, time_in, time_out, hours_worked, status
            FROM attendance
            WHERE date = ?
            ORDER BY time_in
        '''), (today,))

        results = cursor.fetchall()
        conn.close()
        return results

    # ─── Save break start ──────────────────────────────────────────────────────

    def save_break_start(self, user_id, name, date, break_start):
        conn = self._get_conn()
        cursor = conn.cursor()

        pst_now = self.get_current_pst_time()
        created_at = pst_now.strftime('%Y-%m-%d %I:%M:%S %p')

        cursor.execute(self._fix_sql('''
            SELECT id FROM attendance
            WHERE user_id = ? AND date = ? AND status = 'clocked_in'
        '''), (user_id, date))

        record = cursor.fetchone()

        if not record:
            print(f"❌ No clocked_in record found for {name} today")
            conn.close()
            return False

        cursor.execute(self._fix_sql('''
            UPDATE attendance
            SET break_start = ?, status = 'on_break', created_at = ?
            WHERE id = ?
        '''), (break_start, created_at, record[0]))

        conn.commit()
        conn.close()
        print(f'🍽️  {name} started break at {break_start}')
        return True

    # ─── Save break end ────────────────────────────────────────────────────────

    def save_break_end(self, user_id, name, date, break_end):
        conn = self._get_conn()
        cursor = conn.cursor()

        pst_now = self.get_current_pst_time()
        created_at = pst_now.strftime('%Y-%m-%d %I:%M:%S %p')

        cursor.execute(self._fix_sql('''
            SELECT id, break_start FROM attendance
            WHERE user_id = ? AND date = ? AND status = 'on_break'
        '''), (user_id, date))

        record = cursor.fetchone()

        if not record:
            print(f"❌ No on_break record found for {name} today")
            conn.close()
            return False

        record_id, break_start = record

        try:
            start = datetime.strptime(break_start, '%I:%M %p')
            end = datetime.strptime(break_end, '%I:%M %p')
            if end < start:
                from datetime import timedelta
                end = end + timedelta(hours=24)
            break_duration = (end - start).total_seconds() / 3600
        except:
            break_duration = 0

        cursor.execute(self._fix_sql('''
            UPDATE attendance
            SET break_end = ?, break_duration = ?, status = 'clocked_in', created_at = ?
            WHERE id = ?
        '''), (break_end, break_duration, created_at, record_id))

        conn.commit()
        conn.close()
        print(f'✅ {name} ended break at {break_end} (duration: {break_duration:.2f} hrs)')
        return True


if __name__ == '__main__':
    db = AttendanceDB()
    print("Database setup complete!")
    pst_time = db.get_current_pst_time()
    print(f"Current PST time: {pst_time.strftime('%Y-%m-%d %I:%M:%S %p')}")