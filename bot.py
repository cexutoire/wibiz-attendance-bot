import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import re
import sqlite3
from datetime import datetime
from database import AttendanceDB
from utils import calculate_hours, extract_tasks, extract_urls
import json

def get_real_name(user_id, discord_username, message_content):
    """
    Get real name with priority:
    1. Name from message content (Name: XYZ)
    2. Name from mapping file
    3. Discord username (fallback)
    """
    # First, check if name is in the message
    name_match = re.search(NAME_PATTERN, message_content, re.IGNORECASE)
    if name_match:
        return name_match.group(1).strip()
    
    # Second, check name mapping file
    try:
        with open('name_mapping.json', 'r') as f:
            name_map = json.load(f)
            if user_id in name_map:
                return name_map[user_id]
    except FileNotFoundError:
        pass
    
    # Fallback to Discord username
    return discord_username


# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))

# Initialize database
db = AttendanceDB()

# Create bot with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Regex patterns for parsing
TIME_IN_PATTERN = r'Time [Ii]n:?\s*(\d{1,2}:\d{2}\s*[AP]M)'
TIME_OUT_PATTERN = r'Time [Oo]ut:?\s*(\d{1,2}:\d{2}\s*[AP]M)'
NAME_PATTERN = r'Name:?\s*([A-Za-z\s]+)'
DATE_PATTERN = r'Date:?\s*(\d{1,2}\s+\w+\s+\d{4})'

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Monitoring channel ID: {CHANNEL_ID}')

@bot.event
async def on_message(message):
    # Ignore bot's own messages
    if message.author == bot.user:
        return
    
    # Only monitor the daily-reports channel
    if message.channel.id != CHANNEL_ID:
        return
    
    content = message.content
    author = message.author.name
    timestamp = message.created_at
    
    # Check for time-in
    time_in_match = re.search(TIME_IN_PATTERN, content, re.IGNORECASE)
    if time_in_match:
        time_in = time_in_match.group(1)
        date = timestamp.strftime('%Y-%m-%d')
        
        # Get real name
        name = get_real_name(str(message.author.id), author, content)
        
        # Save to database
        db.save_time_in(str(message.author.id), name, date, time_in)
        
        print(f'✅ TIME IN detected: {name} at {time_in}')
        await message.add_reaction('✅')
    
    # Check for time-out (full report)
    time_out_match = re.search(TIME_OUT_PATTERN, content, re.IGNORECASE)
    if time_out_match:
        time_out = time_out_match.group(1)
        
        # Also look for time-in in the same message
        time_in_in_message = re.search(TIME_IN_PATTERN, content, re.IGNORECASE)
        
        # Get real name
        name = get_real_name(str(message.author.id), author, content)
        
        date = timestamp.strftime('%Y-%m-%d')
        time_in = time_in_in_message.group(1) if time_in_in_message else None
        
        # Calculate hours if we have both times
        hours_worked = 0.0
        if time_in and time_out:
            hours_worked = calculate_hours(time_in, time_out)
        
        # Save time-out to database
        db.save_time_out(str(message.author.id), name, date, time_in, time_out, hours_worked)
        
        # Extract tasks
        tasks = extract_tasks(content)
        urls = extract_urls(content)
        
        # Print summary ONCE at the beginning
        print(f'\n✅ TIME OUT REPORT - {name}')
        print(f'   📅 Date: {date}')
        print(f'   🕐 Time: {time_in} → {time_out}')
        print(f'   ⏱️  Hours: {hours_worked} hrs')
        print(f'   📝 Tasks: {len(tasks)}')
        
        # Save each task (quietly, without individual print statements)
        for i, task in enumerate(tasks):
            # Check if this task has a URL associated with it
            task_url = None
            if urls:
                # Simple logic: assign URLs to tasks in order
                if i < len(urls):
                    task_url = urls[i]
            
            db.save_task(str(message.author.id), name, date, task, task_url)
            # Print task summary (one line per task)
            print(f'      • {task[:60]}{"..." if len(task) > 60 else ""}')
        
        print()  # Empty line for spacing
        
        await message.add_reaction('📝')
# Commands
@bot.command()
async def ping(ctx):
    """Test if bot is online"""
    await ctx.send('🤖 Bot is online!')

@bot.command()
async def test(ctx):
    """Show which channel the bot is monitoring"""
    await ctx.send(f'Monitoring channel: <#{CHANNEL_ID}>')

@bot.command()
async def today(ctx):
    """Show today's attendance"""
    records = db.get_today_attendance()
    
    if not records:
        await ctx.send("📭 No attendance records for today yet.")
        return
    
    response = "📊 **Today's Attendance:**\n\n"
    for name, time_in, time_out, hours, status in records:
        if status == 'complete':
            response += f"✅ {name}: {time_in} - {time_out} ({hours:.1f} hrs)\n"
        else:
            response += f"🟡 {name}: {time_in} (still working)\n"
    
    await ctx.send(response)

@bot.command()
async def week(ctx):
    """Show this week's attendance summary"""
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    from datetime import datetime, timedelta
    
    # Get current week (Monday to today)
    pst_now = db.get_current_pst_time()
    today = pst_now.date()
    
    # Find Monday of current week
    days_since_monday = today.weekday()  # 0=Monday, 6=Sunday
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
    
    if not results:
        await ctx.send("📭 No completed attendance records this week yet.")
        return
    
    response = f"📊 **Week of {monday.strftime('%b %d')} - {today.strftime('%b %d')}:**\n\n"
    for name, total_hours, days in results:
        response += f"👤 {name}: {total_hours:.1f} hrs ({days} days)\n"
    
    await ctx.send(response)

@bot.command()
async def tasks(ctx, *, query=None):
    """Show tasks (usage: !tasks or !tasks @user or !tasks today)"""
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    if query and query.lower() == 'today':
        # Show today's tasks
        pst_now = db.get_current_pst_time()
        today = pst_now.strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT name, task_description, deliverable_url
            FROM tasks
            WHERE date = ?
            ORDER BY created_at DESC
        ''', (today,))
        
        results = cursor.fetchall()
        
        if not results:
            await ctx.send("📭 No tasks logged today yet.")
            conn.close()
            return
        
        response = "📝 **Today's Tasks:**\n\n"
        for name, task, url in results:
            task_line = f"• {name}: {task}"
            if url:
                task_line += f" [🔗]({url})"
            response += task_line + "\n"
        
        await ctx.send(response)
    
    else:
        # Show recent tasks (last 10)
        cursor.execute('''
            SELECT name, task_description, date, deliverable_url
            FROM tasks
            ORDER BY created_at DESC
            LIMIT 10
        ''', ())
        
        results = cursor.fetchall()
        
        if not results:
            await ctx.send("📭 No tasks logged yet.")
            conn.close()
            return
        
        response = "📝 **Recent Tasks:**\n\n"
        for name, task, date, url in results:
            task_line = f"• {name} ({date}): {task}"
            if url:
                task_line += f" [🔗]({url})"
            response += task_line + "\n"
        
        await ctx.send(response)
    
    conn.close()

@bot.command()
async def missing(ctx):
    """Show who hasn't clocked out today"""
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    
    pst_now = db.get_current_pst_time()
    today = pst_now.strftime('%Y-%m-%d')
    
    cursor.execute('''
        SELECT name, time_in
        FROM attendance
        WHERE date = ? AND status = 'clocked_in'
        ORDER BY time_in
    ''', (today,))
    
    results = cursor.fetchall()
    conn.close()
    
    if not results:
        await ctx.send("✅ Everyone has clocked out today!")
        return
    
    response = "⚠️ **Missing Time-Outs:**\n\n"
    for name, time_in in results:
        response += f"• {name} (clocked in at {time_in})\n"
    
    await ctx.send(response)

    @bot.command()
    async def stats(ctx):
        """Show overall system statistics"""
        conn = sqlite3.connect('attendance.db')
        cursor = conn.cursor()
        
        # Total records
        cursor.execute('SELECT COUNT(*) FROM attendance')
        total_attendance = cursor.fetchone()[0]
        
        # Total tasks
        cursor.execute('SELECT COUNT(*) FROM tasks')
        total_tasks = cursor.fetchone()[0]
        
        # Total hours (all time)
        cursor.execute('SELECT SUM(hours_worked) FROM attendance WHERE status = "complete"')
        total_hours = cursor.fetchone()[0] or 0
        
        # This week's hours
        from datetime import datetime, timedelta
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
        
        conn.close()
        
        response = f"""📊 **System Statistics:**

    Total Attendance Records: {total_attendance}
    Total Tasks Logged: {total_tasks}
    Total Hours Tracked: {total_hours:.1f} hrs
    This Week's Hours: {week_hours:.1f} hrs
    """
        
        await ctx.send(response)

bot.run(TOKEN)