import sqlite3
import os

# Get database path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
db_path = os.path.join(project_root, 'attendance.db')

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Add new columns
try:
    cursor.execute('ALTER TABLE attendance ADD COLUMN break_start TIME')
    print("✅ Added break_start column")
except:
    print("⚠️  break_start column already exists")

try:
    cursor.execute('ALTER TABLE attendance ADD COLUMN break_end TIME')
    print("✅ Added break_end column")
except:
    print("⚠️  break_end column already exists")

try:
    cursor.execute('ALTER TABLE attendance ADD COLUMN break_duration REAL DEFAULT 0')
    print("✅ Added break_duration column")
except:
    print("⚠️  break_duration column already exists")

conn.commit()
conn.close()

print("\n✅ Database migration complete!")