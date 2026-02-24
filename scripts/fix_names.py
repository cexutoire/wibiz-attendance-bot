import sqlite3
import json
import sys
import os

# Ensure project root is on sys.path so `from src...` works when running this script
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from src.database import AttendanceDB

# Load name mapping from project data folder
NAME_MAPPING_FILE = os.path.join(ROOT_DIR, 'data', 'name_mapping.json')

# Load name mapping
try:
    with open(NAME_MAPPING_FILE, 'r') as f:
        name_map = json.load(f)
except FileNotFoundError:
    print("❌ name_mapping.json not found!")
    exit()

# Use the same DB path as the app
db = AttendanceDB()
conn = sqlite3.connect(db.db_file)
cursor = conn.cursor()

attendance_updated = 0
tasks_updated = 0

for user_id, real_name in name_map.items():
    # Update attendance table
    cursor.execute('''
        UPDATE attendance 
        SET name = ? 
        WHERE user_id = ?
    ''', (real_name, user_id))
    attendance_updated += cursor.rowcount
    
    # Update tasks table
    cursor.execute('''
        UPDATE tasks 
        SET name = ? 
        WHERE user_id = ?
    ''', (real_name, user_id))
    tasks_updated += cursor.rowcount

conn.commit()
conn.close()

print(f"✅ Updated {attendance_updated} attendance records")
print(f"✅ Updated {tasks_updated} task records")
print(f"📋 Mapped {len(name_map)} users")