from flask import Flask, request, abort
import threading
import asyncio

import discord
from discord.ext import commands
from discord import Embed
import logging
from dotenv import load_dotenv
import os
import json
import psycopg

q = asyncio.Queue()

app = Flask(__name__)

load_dotenv()

conn = psycopg.connect(host=os.getenv('DB_HOST', 'localhost'), dbname=os.getenv('DB_NAME', 'postgres'), user=os.getenv('DB_USER', 'postgres'), password=os.getenv('DB_PASSWORD', 'postgres'), port=os.getenv('DB_PORT', 5432))
cur = None

# SQL helper methods
def toggle_alerts(server_id):
    with conn.cursor() as cur:
        cur.execute(''' 
                    UPDATE servers
                    SET alerts_on = NOT alerts_on
                    WHERE server_id = %s;
                    ''', (server_id,))
        conn.commit()
        cur.execute('''
                    SELECT alerts_on
                    FROM servers
                    WHERE server_id = %s;
                    ''', (server_id,))
        alerts_on = cur.fetchone()[0]
    return alerts_on

def set_channel(server_id, channel_id, ticker):
    with conn.cursor() as cur:
        cur.execute('''
            INSERT INTO channels (channel_id, server_id, ticker)
            VALUES (%s, %s, %s)
            ON CONFLICT (server_id, ticker) DO UPDATE
            SET channel_id = EXCLUDED.channel_id;
        ''', (channel_id, server_id, ticker.upper()))
        conn.commit()



@app.route('/')
def home():
    return 'Running'

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.method == 'POST':
        asyncio.run_coroutine_threadsafe(q.put(request.get_json(force=True)), bot.loop)
        # Try to implement this (currently not working)
        '''if request.content_type == 'application/json':
            asyncio.run_coroutine_threadsafe(q.put(request.get_json(force=True)), bot.loop)
        else:
            asyncio.run_coroutine_threadsafe(q.put(request.get_data(as_text=True)), bot.loop)'''
        return 'success', 200
    else:
        abort(400)

def run_flask():
    if __name__ == "__main__":
        app.run(host="0.0.0.0", port=80)


# json setup
def load_json(filename):
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return {}

def save_json(filename, data):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)



def keep_alive():
    threading.Thread(target=run_flask).start()

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f"We are ready to go in, {bot.user.name}")

    print("Connected to PostgreSQL")
    with conn.cursor() as cur:
        cur.execute('''--begin-sql
                CREATE TABLE IF NOT EXISTS servers (
                server_id BIGINT PRIMARY KEY, 
                alerts_on BOOLEAN DEFAULT TRUE
                );
''')
        cur.execute('''--begin-sql
                CREATE TABLE IF NOT EXISTS channels (
                channel_id BIGINT,
                server_id BIGINT, 
                ticker VARCHAR(50),
                UNIQUE (server_id, ticker)
                );
''')
        conn.commit()
    bot.loop.create_task(alert_request())

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)
    

@bot.command()
async def hello(ctx):
    await ctx.send(f"Hello {ctx.author.mention}")

@bot.command()
async def help(ctx):
    embed = Embed(
        title="Sending alerts with TradingView",
        description="Send alerts to webhook URL: https://trading-view-bot-0s4c.onrender.com/webhook"
    )

    json = '''```json
{
  "ticker": "{{ticker}}",
  "alert": "Enter desired alert message here: e.g. BUY NOW! ",
  "server_id": Your Discord server ID (e.g. 814304078158364750)
  "time": "{{time}}" ,
  "open": "{{open}}",
  "close": "{{close}}",
  "high": "{{high}}",
  "low": "{{low}}",
  "interval": "{{interval}}",
  "exchange": "{{exchange}}"
}
```'''

    embed.add_field(name="Structure the alert message as a json like this", value=json, inline=False)
    embed.add_field(name="REQUIRED JSON FIELDS:",value="server_id, ticker, alert", inline=False)
    embed.add_field(name="Other commands:", value="!setchannel, !alerts", inline=False)

    await ctx.send(embed=embed)



@bot.command()
async def setchannel(ctx, ticker):
    server_id = ctx.guild.id
    channel_id = ctx.channel.id
    
    set_channel(server_id, channel_id, ticker)

    await ctx.send(ticker.upper() + " alerts will now be sent here in #" + ctx.channel.name)

@bot.command()
async def alerts(ctx):
    alerts_on = toggle_alerts(ctx.guild.id)
    if (alerts_on):
        await ctx.send("Alerts are now turned ON.")
    else:
        await ctx.send("Alerts are now turned OFF.")

@bot.command()
async def setprefix(ctx, new_prefix):
    global prefix
    prefix = new_prefix
    await ctx.send("Prefix set to " + prefix + ".")

async def alert_request():
    while True:
        alert = await q.get()
        print('Received alert')
        if isinstance(alert, dict):
            # Validate required keys
            if 'server_id' in alert and 'ticker' in alert and 'alert' in alert:
                server_id = alert['server_id']
                ticker = alert['ticker']

                with conn.cursor() as cur:
                    # Check if alerts are enabled for this server
                    cur.execute('SELECT alerts_on FROM servers WHERE server_id = %s', (server_id,))
                    res = cur.fetchone()
                    if res:
                        alerts_on = res[0]
                    else:
                        alerts_on = False

                if alerts_on:
                    with conn.cursor() as cur:
                        # Get channel_id for this server and ticker
                        cur.execute('SELECT channel_id FROM channels WHERE server_id = %s AND ticker = %s', (server_id, ticker))
                        result = cur.fetchone()

                    if result:
                        channel_id = result[0]
                        channel = bot.get_channel(channel_id)

                        if channel:
                            embed = Embed(
                                title=f"🚨 Alert: {ticker}",
                                description=alert['alert'],
                                color=0x00b05e
                            )
                            # Add optional fields
                            for field in ['exchange', 'time', 'interval', 'high', 'low', 'open', 'close']:
                                if field in alert:
                                    embed.add_field(name=field.capitalize(), value=alert[field], inline=True)

                            embed.set_footer(text="Data powered with TradingView")

                            await channel.send(embed=embed)
                        else:
                            print(f"Channel ID {channel_id} not found.")
                    else:
                        print(f"No channel set for server {server_id} and ticker {ticker}.")
                else:
                    print(f"Alerts are disabled for server {server_id}.")
            else:
                print("ERROR: Missing required keys (server_id, ticker, alert) in alert JSON")
        else:
            # Handle non-dict alerts (if needed)
            print(f"Received non-dict alert: {alert}")
        q.task_done()

keep_alive()


bot.run(token, log_handler=handler, log_level=logging.DEBUG)