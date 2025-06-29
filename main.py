from flask import Flask, request, abort
import threading
import asyncio
import discord
from discord.ext import commands
from discord import Embed
import logging
from dotenv import load_dotenv
import os
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



@app.route('/')
def home():
    return 'Running'

@app.route('/webhook', methods=['POST'])
def webhook():
    # TODO Potentially: add secret token system so not everybody who knows the server ID can just send webhooks (spam/security concern)
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


def keep_alive():
    threading.Thread(target=run_flask).start()

token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

prefix = '!'

bot = commands.Bot(command_prefix=prefix, intents=intents, help_command=None)

channel = None
alerts_on = True
discord_server = None

@bot.event
async def on_ready():
    global cur
    print(f"We are ready to go in, {bot.user.name}")

    print("Connected to PostgreSQL")
    with conn.cursor() as cur:
        cur.execute('''--begin-sql
                CREATE TABLE IF NOT EXISTS servers (
                server_id BIGINT PRIMARY KEY, 
                alerts_on BOOLEAN DEFAULT TRUE
                );
''')
        conn.commit()
    bot.loop.create_task(alert_request())

# When bot joins a server, add new entry to server database
@bot.event
async def on_guild_join(guild):
    with conn.cursor() as cur:
        cur.execute('''--begin-sql
                    INSERT INTO servers (server_id, alerts_on) VALUES 
                    (%s, TRUE)
                    ON CONFLICT (server_id) DO NOTHING;
                    
''', (guild.id,))
        conn.commit()
    print(f"Added server {guild.id} to the database.")

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
    embed.add_field(name="REQUIRED JSON FIELDS:",value="ticker, alert, server_id", inline=False)
    embed.add_field(name="Other commands:", value="!setchannel, !alerts", inline=False)

    await ctx.send(embed=embed)



@bot.command()
async def setchannel(ctx):
    global channel
    channel = ctx.channel
    await ctx.send("Alerts will now be sent here in #" + channel.name)

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
        if isinstance(alert, dict):
            if 'server_id' in alert and 'ticker' in alert and 'alert' in alert:
                if alerts_on == True:
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
        else:
            if alerts_on == True and channel:
                await channel.send(f'New alert: {alert}')
        q.task_done()

keep_alive()


bot.run(token, log_handler=handler, log_level=logging.DEBUG)