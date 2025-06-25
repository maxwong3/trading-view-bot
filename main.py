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

prefix = '!'

bot = commands.Bot(command_prefix=prefix, intents=intents, help_command=None)

# set default channel (crypt0nest discord server default when you have it)
#
# IMPORTANNTT
#
#SET IT BELOW:: ---------------------------------------------------------------------------------------

channel = None
alerts_on = True
discord_server = None
# dict that maps server id to channel that's set to the alert channel in that server

# Below is for the bot to be functional across servers; not implemented currently
'''alert_channels = load_json('./json/alert_channels.json')
alerts_toggled = load_json('./json/alerts_toggled.json')
command_prefix = {}'''

@bot.event
async def on_ready():
    print(f"We are ready to go in, {bot.user.name}")
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
    global alerts_on
    if alerts_on == True:
        alerts_on = False
        await ctx.send("Alerts have been turned OFF.")
    elif alerts_on == False:
        alerts_on = True
        await ctx.send("Alerts have been turned ON.")

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