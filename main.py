from flask import Flask, request, abort
import threading
import asyncio

import discord
from discord.ext import commands
from discord import Embed
import logging
from dotenv import load_dotenv
import os

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

def keep_alive():
    threading.Thread(target=run_flask).start()

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

channel = None
alerts = True

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
  "time": "{{time}}",
  "open": "{{open}}",
  "close": "{{close}}",
  "high": "{{high}}",
  "low": "{{low}}",
  "interval": "{{interval}}",
  "exchange": "{{exchange}}"
}
```'''

    embed.add_field(name="Structure the alert message as a json like this", value=json)
    embed.set_footer(text="*Messages not sent as a json will be sent as raw text in specified channel*")

    await ctx.send(embed=embed)



@bot.command()
async def setchannel(ctx):
    global channel
    channel = ctx.channel
    await ctx.send("Alerts will now be sent here in #" + ctx.channel.name)

@bot.command()
async def alerts(ctx):
    if alerts == True:
        await ctx.send("Alerts have been turned OFF.")
        alerts = False
    if alerts == False:
        await ctx.send("Alerts have been turned ON.")
        alerts = True

async def alert_request():
    while True:
        alert = await q.get()
        if channel and alerts == True:
            if isinstance(alert, dict):
                embed = Embed(
                    title=f"🚨 Alert: {alert['ticker']}",
                    description=f"{alert['alert']}",
                )
                
                embed.add_field(name="Exchange", value=alert['exchange'], inline=True)
                embed.add_field(name="Time", value=alert['time'], inline=True)
                embed.add_field(name="Interval", value=alert['interval'], inline=True)
                embed.add_field(name="Open", value=alert['open'], inline=True)
                embed.add_field(name="Close", value=alert['close'], inline=True)
                embed.add_field(name="High", value=alert['high'], inline=True)
                embed.add_field(name="Low", value=alert['low'], inline=True)

                embed.set_footer(text="Data powered with TradingView")

                await channel.send(embed=embed)
            else:
                await channel.send(f'New alert: {alert}')
        q.task_done()

keep_alive()

bot.run(token, log_handler=handler, log_level=logging.DEBUG)