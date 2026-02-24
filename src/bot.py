import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import re
import sqlite3
from datetime import datetime
from src.database import AttendanceDB
from src.utils import calculate_hours, extract_tasks, extract_urls
import json
from datetime import datetime, timedelta
import os

# Project root and mapping path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME_MAPPING_FILE = os.path.join(ROOT_DIR, 'data', 'name_mapping.json')

def get_real_name(user_id, discord_username, message_content):
    """
    Get real name with priority:
    1. Name from message content (Name: XYZ) - only if explicitly included
    2. Name from mapping file - MAIN METHOD
    3. Discord username (fallback) - if user not in mapping
    """
    # First, check if name is in the message
    name_match = re.search(NAME_PATTERN, message_content, re.IGNORECASE)
    if name_match:
        return name_match.group(1).strip()
    
    # Second, check name mapping file
    try:
        with open(NAME_MAPPING_FILE, 'r') as f:
            name_map = json.load(f)
            if user_id in name_map:
                return name_map[user_id]
    except FileNotFoundError:
        pass
    
    # Fallback to Discord username
    return discord_username


# Load environment variables
load_dotenv(os.path.join(os.getcwd(), 'config', '.env'))
TOKEN = os.getenv('DISCORD_TOKEN')
raw_channel_id = os.getenv('CHANNEL_ID')

if not TOKEN or not raw_channel_id:
    print("❌ ERROR: DISCORD_TOKEN or CHANNEL_ID missing in .env file.")
    exit(1)

CHANNEL_ID = int(raw_channel_id)

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
# Add to existing regex patterns
BREAK_START_PATTERN = r'[Oo]n [Bb]reak:?\s*(\d{1,2}:\d{2}\s*[AP]M)'
BREAK_END_PATTERN = r'[Bb]ack [Ff]rom [Bb]reak:?\s*(\d{1,2}:\d{2}\s*[AP]M)'

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
    
    # Get real name from mapping
    name = get_real_name(str(message.author.id), author, content)
    date = timestamp.strftime('%Y-%m-%d')
    
    # Check for BREAK START
    break_start_match = re.search(BREAK_START_PATTERN, content, re.IGNORECASE)
    if break_start_match:
        break_start = break_start_match.group(1).strip()
        break_start = re.sub(r'\s+', ' ', break_start)
        
        success = db.save_break_start(str(message.author.id), name, date, break_start)
        if success:
            await message.add_reaction('🍽️')
            print(f'🍽️  {name} on break at {break_start}')
        else:
            await message.add_reaction('❌')
        
        await bot.process_commands(message)
        return
    
    # Check for BREAK END
    break_end_match = re.search(BREAK_END_PATTERN, content, re.IGNORECASE)
    if break_end_match:
        break_end = break_end_match.group(1).strip()
        break_end = re.sub(r'\s+', ' ', break_end)
        
        success = db.save_break_end(str(message.author.id), name, date, break_end)
        if success:
            await message.add_reaction('✅')
        else:
            await message.add_reaction('❌')
        
        await bot.process_commands(message)
        return
    
    # Check for TIME OUT (full report)
    time_out_match = re.search(TIME_OUT_PATTERN, content, re.IGNORECASE)
    
    if time_out_match:
        # ... (your existing time-out code, but don't deduct lunch automatically)
        time_out = time_out_match.group(1).strip()
        time_in_match = re.search(TIME_IN_PATTERN, content, re.IGNORECASE)
        
        time_in = time_in_match.group(1).strip() if time_in_match else None
        
        if time_in:
            time_in = re.sub(r'\s+', ' ', time_in)
        time_out = re.sub(r'\s+', ' ', time_out)
        
        # Calculate hours WITHOUT automatic lunch deduction
        hours_worked = 0.0
        if time_in and time_out:
            from src.utils import calculate_hours
            hours_worked = calculate_hours(time_in, time_out, deduct_lunch=False)  # NO auto-deduction
        
        # Save time-out (will deduct break if logged)
        db.save_time_out(str(message.author.id), name, date, time_in, time_out, hours_worked)
        
        # Extract tasks
        tasks = extract_tasks(content)
        urls = extract_urls(content)
        
        # Print summary
        print(f'\n✅ TIME OUT REPORT - {name}')
        print(f'   📅 Date: {date}')
        print(f'   🕐 Time: {time_in} → {time_out}')
        print(f'   ⏱️  Hours: {hours_worked} hrs')
        print(f'   📝 Tasks: {len(tasks)}')
        
        # Save tasks
        for i, task in enumerate(tasks):
            task_url = None
            if urls and i < len(urls):
                task_url = urls[i]
            
            db.save_task(str(message.author.id), name, date, task, task_url)
            print(f'      • {task[:60]}{"..." if len(task) > 60 else ""}')
        
        print()
        await message.add_reaction('📝')
        
    else:
        # Check for TIME IN
        time_in_match = re.search(TIME_IN_PATTERN, content, re.IGNORECASE)
        if time_in_match:
            time_in = time_in_match.group(1).strip()
            time_in = re.sub(r'\s+', ' ', time_in)
            
            db.save_time_in(str(message.author.id), name, date, time_in)
            
            print(f'💾 Saved: {name} clocked in at {time_in}')
            await message.add_reaction('✅')
    
    await bot.process_commands(message)
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
    conn = sqlite3.connect(db.db_file)
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
    conn = sqlite3.connect(db.db_file)
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
    conn = sqlite3.connect(db.db_file)
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
        conn = sqlite3.connect(db.db_file)
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

@bot.command()
async def whoami(ctx):
    """Show your Discord user ID and current mapped name"""
    user_id = str(ctx.author.id)
    discord_name = ctx.author.name
    
    # Check if mapped
    try:
        with open(NAME_MAPPING_FILE, 'r') as f:
            name_map = json.load(f)
            real_name = name_map.get(user_id, "❌ Not mapped")
    except:
        real_name = "❌ Not mapped"
    
    await ctx.send(f"""📋 **Your Info:**
Discord Username: `{discord_name}`
User ID: `{user_id}`
Mapped Name: `{real_name}`

*To update your name, ask admin to add you to name_mapping.json*
""")
    
@bot.command()
async def status(ctx):
    """Show everyone's current status"""
    conn = sqlite3.connect(db.db_file)
    cursor = conn.cursor()
    
    pst_now = db.get_current_pst_time()
    today = pst_now.strftime('%Y-%m-%d')
    
    cursor.execute('''
        SELECT name, time_in, status, break_start
        FROM attendance
        WHERE date = ?
        ORDER BY time_in
    ''', (today,))
    
    results = cursor.fetchall()
    conn.close()
    
    if not results:
        await ctx.send("📭 No one has clocked in today yet.")
        return
    
    response = "📊 **Current Status:**\n\n"
    for name, time_in, status, break_start in results:
        if status == 'clocked_in':
            response += f"✅ {name}: Working (since {time_in})\n"
        elif status == 'on_break':
            response += f"🍽️ {name}: On break (since {break_start})\n"
        elif status == 'complete':
            response += f"✔️ {name}: Completed for the day\n"
    
    await ctx.send(response)

bot.run(TOKEN)