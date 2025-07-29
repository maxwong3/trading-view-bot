import os
import discord
import psycopg
import psycopg_pool

from discord.ext import commands
from discord import Embed
from dotenv import load_dotenv
from shared import queue, logger
from shared import get_prefix, toggle_alerts, set_channel, set_secret, get_secret
from db import pool
from datetime import datetime
import traceback

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None)

@bot.event
async def on_ready():
    logger.info(f"We are ready to go in, {bot.user.name}")

    try:
        logger.info("Connected to PostgreSQL")
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute('''--begin-sql
                        CREATE TABLE IF NOT EXISTS servers (
                        server_id BIGINT PRIMARY KEY, 
                        alerts_on BOOLEAN DEFAULT TRUE,
                        prefix VARCHAR(10) DEFAULT '!',
                        secret TEXT
                        );
        ''')
                await cur.execute('''--begin-sql
                        CREATE TABLE IF NOT EXISTS channels (
                        id SERIAL PRIMARY KEY,
                        channel_id BIGINT,
                        server_id BIGINT, 
                        ticker VARCHAR(50),
                        signal_type VARCHAR(50) DEFAULT 'NONE',
                        UNIQUE (server_id, ticker, signal_type)
                        );
        ''')
            await conn.commit()
        bot.loop.create_task(alert_request())
    except Exception as e:
        logger.error(f"DB initialization error: {e}")
        return

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
        description="Send alerts to webhook URL: https://trading-view-bot-0s4c.onrender.com/webhook (This needs to be updated to new url with GCP)"
    )

    json = '''```json
{
  "ticker": "{{ticker}}",
  "alert": "Enter desired alert message here: e.g. BUY NOW! ",
  "server_id": Your Discord server ID (e.g. 814304078158364750),
  "secret": "Enter secret password here",
  "signal_type": "For advanced signals e.g. BUY or SELL",
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
    embed.add_field(name="For added security:",value="Add a secret using !setsecret, webhooks will now require the valid secret to be sent as a field", inline=False)
    embed.add_field(name="Other commands:", value="!setchannel [ticker, signal (optional)], !removealert, !setsecret [secret], !secret, !removesecret, !alerts, !togglealerts, !setprefix [prefix]", inline=False)

    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def setsecret(ctx, secret=None):
    if not secret:
        await ctx.send("Make sure to specify a secret password for the server, one that will be required in the json if set")
        return
    await set_secret(ctx.guild.id, secret)
    await ctx.send("🗝️ Server password set. You must now include the secret property and set the value to the appropriate secret password. !removesecret to remove secret")

@bot.command()
@commands.has_permissions(administrator=True)
async def removesecret(ctx):
    await set_secret(ctx.guild.id, None)
    await ctx.send("Secret removed. You now no longer need a secret to send webhooks.")

@bot.command()
@commands.has_permissions(administrator=True)
async def secret(ctx):
    secret = await get_secret(ctx.guild.id)
    if secret is None:
        await ctx.send("There is currently no secret set for this server. !setsecret [secret] to set one.")
    else:
        await ctx.send(f"The server secret is: {secret}")


@bot.command()
@commands.has_permissions(administrator=True)
async def setchannel(ctx, ticker=None, signal=None):
    if not ticker:
        await ctx.send("❌ Incorrect usage, specify ticker of active TradingView alert to add: e.g. !setchannel BTCUSD")
        return

    server_id = ctx.guild.id
    channel_id = ctx.channel.id
    
    await set_channel(server_id, channel_id, ticker, signal)
    
    if signal is None:
        await ctx.send(ticker.upper() + " alerts will now be sent here in #" + ctx.channel.name)
    else: 
        await ctx.send("Advanced signal " + signal.upper() + " for coin " + ticker.upper() + " will now be sent here in #" + ctx.channel.name)

@bot.command()
@commands.has_permissions(administrator=True)
async def removealert(ctx, ticker=None, signal=None):
    if not ticker:
        await ctx.send("❌ Incorrect usage, specify ticker of alert to remove: e.g. !removealert BTCUSD")
        return
    ticker = ticker.upper()

    signal_type = 'NONE' if signal is None else signal.upper()
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute('''
                            DELETE FROM channels
                            WHERE server_id = %s AND ticker = %s AND signal_type = %s
                            RETURNING *;
                ''', (ctx.guild.id, ticker, signal_type))
                deleted = await cur.fetchone()
                await conn.commit()

            if deleted:
                if signal_type == 'NONE':
                    await ctx.send(f"Alert {ticker} has been removed from this server.")
                else: 
                    await ctx.send(f"Advanced signal {signal_type} for coin {ticker} has been removed from this server.")
            else:
                await ctx.send(f"❌ ERROR: Alert {ticker} doesn't exist in this server.")
    except Exception as e:
        logger.error(f"DB error in removealert: {e}")
        return


@bot.command()
@commands.has_permissions(administrator=True)
async def togglealerts(ctx):
    alerts_on = await toggle_alerts(ctx.guild.id)
    if (alerts_on):
        await ctx.send("Alerts are now turned ON.")
    else:
        await ctx.send("Alerts are now turned OFF.")

@bot.command()
async def alerts(ctx):
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute('''
                            SELECT ticker, channel_id, signal_type
                            FROM channels
                            WHERE server_id = %s;
                ''', (ctx.guild.id,))
                channels = await cur.fetchall()

            if not channels:
                await ctx.send("No active alerts in this server. Use command !setchannel [ticker] to set an active ticker alert to the channel.")
                return
    except Exception as e:
        logger.error(f"DB error in alerts: {e}")
        return

    
    embed = Embed(
        title="List of Active Alerts"
    )

    for ticker, channel_id, signal_type in channels:
        channel = bot.get_channel(channel_id)
        if channel:
            if signal_type == 'NONE':  
                embed.add_field(name="⚪ Coin: " + ticker, value=f"Sent in #{channel.name}", inline=False)
            else: 
                embed.add_field(name="⭐ Advanced Signal: " + signal_type + ", Coin: " + ticker, value=f"Sent in #{channel.name}", inline=False)
        else:
            embed.add_field(name=ticker, value=f"Possibly deleted channel with channel ID: {channel_id}")

    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def setprefix(ctx, new_prefix):
    if not new_prefix:
        await ctx.send("❌ Incorrect usage, specify prefix: e.g. !setprefix ?")
        return
    new_prefix = new_prefix.strip()
    if len(new_prefix) > 5:
        await ctx.send("❌ ERROR: Prefix must be 5 characters or less.")
        return
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute('''
                            INSERT INTO servers (server_id, alerts_on, prefix)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (server_id) DO UPDATE
                            SET prefix = EXCLUDED.prefix;
                ''', (ctx.guild.id, True, new_prefix))
                await conn.commit()

            await ctx.send(f"Prefix for this server set to {new_prefix}")
    except Exception as e:
        logger.error(f"DB error in setprefix: {e}")
        return
        

async def alert_request():
    logger.info("✅ alert_request loop started.")
    while True:
        item_added = False
        try: 
            alert = await queue.get()
            item_added = True
            logger.info(f"Alert received in queue: {alert}")
            async with pool.connection() as conn:
                saved_secret = None
                if isinstance(alert, dict):
                    # Required json keys 
                    if 'server_id' in alert and 'ticker' in alert and 'alert' in alert:
                        server_id = alert['server_id']
                        ticker = alert['ticker']
                        # Check if advanced signal
                        signal_type = 'NONE'
                        if 'signal_type' in alert and alert['signal_type']:
                            signal_type = alert['signal_type'].upper()
                        logger.info(signal_type)
                        # Check for secret
                        secret = alert.get('secret')
                        if secret is not None:
                            secret = secret.strip()

                        async with conn.cursor() as cur:
                            # Check if alerts are enabled for this server
                            await cur.execute('SELECT alerts_on, secret FROM servers WHERE server_id = %s', (server_id,))
                            res = await cur.fetchone()
                            if res is None:
                                logger.info("Server is not in server list.")
                                continue
                            else:
                                alerts_on = res[0]
                            # Check if secret set in server
                            if res[1] is not None:
                                saved_secret = res[1]

                        if alerts_on:
                            async with conn.cursor() as cur:
                                # Get channel_id for this server and ticker
                                await cur.execute('SELECT channel_id FROM channels WHERE server_id = %s AND ticker = %s AND signal_type = %s', (server_id, ticker, signal_type))
                                res = await cur.fetchone()
                                logger.info(f"Looking for channel with server_id={server_id}, ticker={ticker}, signal_type={signal_type}")
                                logger.info(f"Query result: {res}")

                            if res:
                                channel_id = res[0]
                                channel = bot.get_channel(channel_id)

                                if channel:
                                    embed = Embed(
                                        title=f"🚨 Alert: {ticker}",
                                        description=alert['alert'],
                                        color=0x00b05e
                                    )
                                    # Compare secret
                                    if saved_secret:
                                        if secret == saved_secret:
                                            logger.info("Secret passed!")
                                        else: 
                                            logger.info("❌ Incorrect secret.")
                                            continue
                                    # Optional fields
                                    for field in ['signal_type', 'exchange', 'time', 'interval', 'high', 'low', 'open', 'close']:
                                        if field in alert:
                                            value = alert[field]
                                            name = field.capitalize()
                                            if field == 'time':
                                                try:
                                                    value = datetime.fromisoformat(value).strftime('%Y-%m-%d %H:%M UTC')
                                                except Exception:
                                                    pass
                                            if field == 'signal_type':
                                                if (alert.get('signal_type') or 'NONE').upper() == 'NONE':
                                                    continue
                                                else:
                                                    name = 'Advanced Signal'
                                                    value = alert[field].upper()
                                            embed.add_field(name=name, value=value, inline=True)

                                    embed.set_footer(text="Data powered with TradingView")

                                    await channel.send(embed=embed)
                                else:
                                    logger.error(f"Channel ID {channel_id} not found.")
                            else:
                                logger.error(f"No channel set for server {server_id} and ticker {ticker}.")
                        else:
                            logger.info(f"Alerts are disabled for server {server_id}.")
                    else:
                        logger.error("ERROR: Missing required keys (server_id, ticker, alert) in alert JSON")
                else:
                    # Handle non-dict alerts (if needed)
                    logger.error(f"Received non-dict alert: {alert}")
        except Exception as e:
            logger.error(f"ERROR while processing alert: {e}")
            logger.error(traceback.format_exc())
        finally:
            if item_added:
                queue.task_done()
