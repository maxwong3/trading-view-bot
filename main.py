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

q = asyncio.Queue()

app = Flask(__name__)

<<<<<<< Updated upstream
=======
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
        ''', (channel_id, server_id, ticker))
        conn.commit()



>>>>>>> Stashed changes
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

<<<<<<< Updated upstream
channel = None
discord_server = None
# dict that maps server id to channel that's set to the alert channel in that server
alert_channels = load_json('./json/alert_channels.json')
alerts_toggled = load_json('./json/alerts_toggled.json')
command_prefix = {}

=======
>>>>>>> Stashed changes
@bot.event
async def on_ready():
    print(f"We are ready to go in, {bot.user.name}")
<<<<<<< Updated upstream
=======

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
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
async def setchannel(ctx):
    alert_channels[str(ctx.guild.id)] = ctx.channel.id
    save_json('./json/alert_channels.json', alert_channels)

    await ctx.send("Alerts will now be sent here in #" + ctx.channel.name)
    if str(ctx.guild.id) not in alerts_toggled:
        alerts_toggled[str(ctx.guild.id)] = True
        save_json('./json/alerts_toggled.json', alerts_toggled)

@bot.command()
async def alerts(ctx):
    if str(ctx.guild.id) in alerts_toggled:
        if alerts_toggled[str(ctx.guild.id)] == True:
            await ctx.send("Alerts have been turned OFF.")
            alerts_toggled[str(ctx.guild.id)] = False
            save_json('./json/alerts_toggled.json', alerts_toggled)
        elif alerts_toggled[str(ctx.guild.id)] == False:
            await ctx.send("Alerts have been turned ON.")
            alerts_toggled[str(ctx.guild.id)] = True
            save_json('./json/alerts_toggled.json', alerts_toggled)
    else: 
        await ctx.send("Alerts are switched off, do !setchannel in this server first")

@bot.command()
async def setprefix(ctx):
    await ctx.send("Not implemented yet; Will be developed if needed.")
=======
async def setchannel(ctx, ticker):
    server_id = ctx.guild.id
    channel_id = ctx.channel.id
    
    set_channel(server_id, channel_id, ticker)

    await ctx.send(ticker + " alerts will now be sent here in #" + ctx.channel.name)

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
>>>>>>> Stashed changes

async def alert_request():
    while True:
        alert = await q.get()
        if isinstance(alert, dict):
            # Validate required keys
            if 'server_id' in alert and 'ticker' in alert and 'alert' in alert:
                server_id = alert['server_id']
                ticker = alert['ticker']

                with conn.cursor() as cur:
                    # Check if alerts are enabled for this server
                    cur.execute('SELECT alerts_on FROM servers WHERE server_id = %s', (server_id,))
                    res = cur.fetchone()
                    alerts_on = res[0] if res else False

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
                            print(f"Channel ID {channel_id} not found in bot cache.")
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

"""async def alert_request():
    while True:
        alert = await q.get()
        if isinstance(alert, dict):
            if 'server_id' in alert and 'ticker' in alert and 'alert' in alert:
<<<<<<< Updated upstream
                server_id = str(alert['server_id'])
                if alerts_toggled.get(server_id, False):
                    if server_id in alert_channels:
                        channel_id = alert_channels[server_id]
                        channel = bot.get_channel(channel_id)
=======
                if alerts_on == True:
                    with conn.cursor() as cur:
                        cur.execute('SELECT channel_id FROM channels WHERE server_id = %s AND ticker = %s', (server_id, ticker))
                        result = cur.fetchone()

                    if result:
                        channel_id = result[0]
                        channel = bot.get_channel(channel_id)

                    if channel: 
                        embed = Embed(
                            title=f"🚨 Alert: {alert['ticker']}",
                            description=f"{alert['alert']}",
                            color=0x00b05e
                        )
                        if 'exchange' in alert:
                            embed.add_field(name="Exchange", value=alert['exchange'], inline=False)
                        if 'time' in alert:
                            embed.add_field(name="Time", value=alert['time'], inline=False)
                        if 'interval' in alert:
                            embed.add_field(name="Interval", value=alert['interval'], inline=True)
                        if 'high' in alert:
                            embed.add_field(name="High", value=alert['high'], inline=True)
                        if 'low' in alert:
                            embed.add_field(name="Low", value=alert['low'], inline=True)
                        if 'open' in alert:
                            embed.add_field(name="Open", value=alert['open'], inline=True)
                        if 'close' in alert:
                            embed.add_field(name="Close", value=alert['close'], inline=True)
>>>>>>> Stashed changes

                        if channel: 
                            embed = Embed(
                                title=f"🚨 Alert: {alert['ticker']}",
                                description=f"{alert['alert']}",
                                color=0x00b05e
                            )
                            if 'exchange' in alert:
                                embed.add_field(name="Exchange", value=alert['exchange'], inline=False)
                            if 'time' in alert:
                                embed.add_field(name="Time", value=alert['time'], inline=False)
                            if 'interval' in alert:
                                embed.add_field(name="Interval", value=alert['interval'], inline=True)
                            if 'high' in alert:
                                embed.add_field(name="High", value=alert['high'], inline=True)
                            if 'low' in alert:
                                embed.add_field(name="Low", value=alert['low'], inline=True)
                            if 'open' in alert:
                                embed.add_field(name="Open", value=alert['open'], inline=True)
                            if 'close' in alert:
                                embed.add_field(name="Close", value=alert['close'], inline=True)

                            embed.set_footer(text="Data powered with TradingView")

                            await channel.send(embed=embed)
            else:
                print("ERROR: One of server_id, ticker, or alert (required) not found as key in json")
<<<<<<< Updated upstream
        q.task_done()
=======
        else:
            if alerts_on == True and channel:
                await channel.send(f'New alert: {alert}')
        q.task_done()"""
>>>>>>> Stashed changes

keep_alive()


bot.run(token, log_handler=handler, log_level=logging.DEBUG)