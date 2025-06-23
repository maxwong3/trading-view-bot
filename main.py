from flask import Flask, request, abort
import threading
import asyncio

import discord
from discord.ext import commands
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
        print(request.get_data(as_text=True))
        asyncio.run_coroutine_threadsafe(q.put(request.get_data(as_text=True)), bot.loop)
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

channel_id = 1385734799955722240

bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    global channel
    channel = bot.get_channel(channel_id)
    print(f"We are ready to go in, {bot.user.name}")
    if channel is None:
        print("Channel not found.")
    else:
        print(f"Ready to send messages to #{channel.name}")
        bot.loop.create_task(alert_request())

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)
    

@bot.command()
async def hello(ctx):
    await ctx.send(f"Hello {ctx.author.mention}")

async def alert_request():
    while True:
        alert = await q.get()
        if channel:
            await channel.send(f'New alert: {alert}')
        q.task_done()

keep_alive()

bot.run(token, log_handler=handler, log_level=logging.DEBUG)