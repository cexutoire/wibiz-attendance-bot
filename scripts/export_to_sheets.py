"""
Export attendance.db to Google Sheets in near-real-time (polling demo).

Setup (summary):
1. Create a Google Cloud service account with the "Google Sheets API" enabled.
2. Download the service account JSON to `config/service_account.json` in the project root.
3. Create a Google Sheet and copy its Spreadsheet ID.
4. Share the sheet with the service account email (found in the JSON file).
5. Set environment variables or edit variables below: SPREADSHEET_ID, SERVICE_ACCOUNT_FILE.

Run:
    python sripts/export_to_sheets.py --once
    python sripts/export_to_sheets.py        # runs polling loop (default 10s)

Dependencies:
    pip install google-api-python-client google-auth-httplib2 google-auth

This script writes two sheets/tabs: "Attendance" and "Tasks".
"""

import os
import sys
import time
import json
import sqlite3
import argparse
from hashlib import md5

# Make project root importable
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from src.database import AttendanceDB

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Config (can be overridden via env)
SERVICE_ACCOUNT_FILE = os.environ.get('SERVICE_ACCOUNT_FILE') or os.path.join(ROOT_DIR, 'config', 'service_account.json')
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID') or '<YOUR_SPREADSHEET_ID>'

# Scopes
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def get_sheets_service(sa_file: str):
    creds = Credentials.from_service_account_file(sa_file, scopes=SCOPES)
    service = build('sheets', 'v4', credentials=creds)
    return service.spreadsheets()

def fetch_attendance(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, name, date, time_in, time_out, hours_worked, status, created_at
        FROM attendance
        ORDER BY date, time_in
    ''')
    rows = cursor.fetchall()
    conn.close()
    return rows

def fetch_tasks(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT user_id, name, date, task_description, has_link, deliverable_url, created_at
        FROM tasks
        ORDER BY created_at DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return rows

def rows_to_values(rows):
    return [list(r) for r in rows]

def compute_hash(data):
    return md5(json.dumps(data, default=str, sort_keys=True).encode('utf-8')).hexdigest()

def write_sheet(spreadsheet, sheet_name, header, rows):
    # Clear existing range by overwriting
    values = [header] + rows_to_values(rows)
    body = {'values': values}
    range_name = f"{sheet_name}!A1"
    spreadsheet.values().clear(spreadsheetId=SPREADSHEET_ID, range=sheet_name).execute()
    spreadsheet.values().update(spreadsheetId=SPREADSHEET_ID, range=range_name, valueInputOption='RAW', body=body).execute()

def main(args):
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        print('❌ service account JSON not found at', SERVICE_ACCOUNT_FILE)
        return

    if SPREADSHEET_ID == '<YOUR_SPREADSHEET_ID>':
        print('❌ Please set SPREADSHEET_ID in env or edit the script to include your spreadsheet id.')
        return

    db = AttendanceDB()
    spreadsheet = get_sheets_service(SERVICE_ACCOUNT_FILE)

    last_hash = None

    try:
        while True:
            attendance = fetch_attendance(db.db_file)
            tasks = fetch_tasks(db.db_file)

            payload = {'attendance': attendance, 'tasks': tasks}
            current_hash = compute_hash(payload)

            if current_hash != last_hash or args.once:
                print('🔁 Updating Google Sheet...')

                # Attendance sheet
                attendance_header = ['user_id', 'name', 'date', 'time_in', 'time_out', 'hours_worked', 'status', 'created_at']
                write_sheet(spreadsheet, 'Attendance', attendance_header, attendance)

                # Tasks sheet
                tasks_header = ['user_id', 'name', 'date', 'task_description', 'has_link', 'deliverable_url', 'created_at']
                write_sheet(spreadsheet, 'Tasks', tasks_header, tasks)

                print('✅ Google Sheet updated')
                last_hash = current_hash

            if args.once:
                break

            time.sleep(args.interval)
    except KeyboardInterrupt:
        print('\nStopped by user')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Export attendance.db to Google Sheets (polling demo)')
    parser.add_argument('--interval', type=int, default=10, help='Polling interval in seconds')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    args = parser.parse_args()
    main(args)
