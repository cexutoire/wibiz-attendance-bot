import sqlite3
import json

# Load name mapping
try:
    with open('name_mapping.json', 'r') as f:
        name_map = json.load(f)
except FileNotFoundError:
    print("❌ name_mapping.json not found!")
    exit()

conn = sqlite3.connect('attendance.db')
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