import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import re
from datetime import datetime

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))

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
        print(f'✅ TIME IN detected: {author} at {time_in}')
        # Add emoji reaction to confirm
        await message.add_reaction('✅')
        # TODO: Save to database

    # Check for time-out (full report)
    time_out_match = re.search(TIME_OUT_PATTERN, content, re.IGNORECASE)
    if time_out_match:
        time_out = time_out_match.group(1)
        name_match = re.search(NAME_PATTERN, content, re.IGNORECASE)
        date_match = re.search(DATE_PATTERN, content, re.IGNORECASE)

        name = name_match.group(1).strip() if name_match else author
        date = date_match.group(1) if date_match else timestamp.strftime('%d %b %Y')

        print(f'✅ TIME OUT detected: {name} at {time_out}')
        await message.add_reaction('📝')
        # TODO: Save to database, extract tasks

    await bot.process_commands(message)

# Simple test command
@bot.command()
async def ping(ctx):
    await ctx.send('🤖 Bot is online!')

@bot.command()
async def test(ctx):
    await ctx.send(f'Monitoring channel: <#{CHANNEL_ID}>')

bot.run(TOKEN)