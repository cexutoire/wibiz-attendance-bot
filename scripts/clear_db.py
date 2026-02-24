import sqlite3

conn = sqlite3.connect('./attendance.db')
cursor = conn.cursor()

# Clear all data
cursor.execute('DELETE FROM attendance')
cursor.execute('DELETE FROM tasks')

# Reset the auto-increment counters
cursor.execute('DELETE FROM sqlite_sequence')

conn.commit()
conn.close()

print("✅ Database cleared and ID counters reset!")