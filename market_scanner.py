# market_scanner.py

import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import os
import datetime
from pycoingecko import CoinGeckoAPI

# --- Basic Setup ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
#api_key = os.getenv('COINGECKO_API_KEY')

# It's good practice to define intents
intents = discord.Intents.default()
intents.message_content = True 

bot = commands.Bot(command_prefix='/', intents=intents)

# Initialize the CoinGecko API client
#cg = CoinGeckoAPI(api_key = api_key)
cg = CoinGeckoAPI()
# --- Configuration ---
# You can easily change these settings
CONFIG = {
    'ALERT_CHANNEL_ID': 1385799309211078737,      # <<< IMPORTANT: REPLACE WITH YOUR CHANNEL ID
    'TOP_N_COINS': 20,              # Number of top coins to monitor
    'PRICE_CHANGE_THRESHOLD': 4,  # Alert if price moves by this % or more
    'CHECK_INTERVAL_MINUTES': 5,   # How often to check the market
    'ALERT_COOLDOWN_HOURS': 0.1       # Cooldown period for a coin after an alert
}

# --- State Management ---
# This dictionary will store the last alert time for each coin to prevent spam
recent_alerts = {}


@bot.event
async def on_ready():
    """Event that runs when the bot is connected and ready."""
    print(f'{bot.user.name} is now running!')
    # Start the background task to check for price movements
    check_price_movements.start()



@tasks.loop(minutes=CONFIG['CHECK_INTERVAL_MINUTES'])
async def check_price_movements():
    """The main background task to scan the market for significant price movements."""
    try:
        print(f"[{datetime.datetime.now()}] --- Starting New Check ---")

        alert_channel = bot.get_channel(CONFIG['ALERT_CHANNEL_ID'])
        if not alert_channel:
            print(f"!!! CRITICAL ERROR: Could not find channel with ID {CONFIG['ALERT_CHANNEL_ID']}.")
            return
        print(f"Successfully found channel: #{alert_channel.name}")

        # --- THE FIX IS HERE ---
        # We now use get_coins_markets and ask for the '1h' price change percentage.
        # This one API call gets us everything we need.
        markets = cg.get_coins_markets(
            vs_currency='usd',
            order='market_cap_desc',
            per_page=CONFIG['TOP_N_COINS'],
            page=1,
            price_change_percentage='1h,24h'  # Ask for 1-hour and 24-hour change
        )
        print(f"Fetched market data for {len(markets)} coins.")

        # The data is now a LIST of dictionaries, so we loop differently
        for coin in markets:
            coin_id = coin.get('id')
            # The key for 1h change is 'price_change_percentage_1h_in_currency'
            change_1h = coin.get('price_change_percentage_1h_in_currency')

            if coin_id is None or change_1h is None:
                continue 

            print(f"  - Checking {coin_id.ljust(15)} | 1h Change: {change_1h:.4f}% | Threshold: {CONFIG['PRICE_CHANGE_THRESHOLD']}%")

            # Check if cooldown is active
            if coin_id in recent_alerts:
                cooldown_time = datetime.timedelta(hours=CONFIG['ALERT_COOLDOWN_HOURS'])
                if datetime.datetime.utcnow() - recent_alerts.get(coin_id, datetime.datetime.min) < cooldown_time:
                    continue 

            # Check if movement exceeds threshold
            if abs(change_1h) >= CONFIG['PRICE_CHANGE_THRESHOLD']:
                print(f"  ✅✅✅ ALERT TRIGGERED FOR {coin_id.upper()} ✅✅✅")
                
                recent_alerts[coin_id] = datetime.datetime.utcnow()
                
                # We get the other data points from the 'coin' dictionary
                embed = create_movement_embed(
                    coin_id=coin_id,
                    price=coin.get('current_price', 0),
                    change_1h=change_1h,
                    change_24h=coin.get('price_change_percentage_24h_in_currency', 0),
                    market_cap=coin.get('market_cap', 0)
                )
                
                print(f"      Attempting to send message to #{alert_channel.name}...")
                await alert_channel.send(embed=embed)
                print(f"      Message for {coin_id.upper()} sent successfully!")

    except Exception as e:
        print(f"!!! AN UNEXPECTED ERROR OCCURRED in the loop: {e}")
def create_movement_embed(coin_id, price, change_1h, change_24h, market_cap):
    """A helper function to create a nice-looking Discord embed for an alert."""
    is_positive = change_1h >= 0
    color = discord.Color.green() if is_positive else discord.Color.red()
    direction = "UP" if is_positive else "DOWN"
    
    embed = discord.Embed(
        title=f"🚨 Price Alert: {coin_id.capitalize()} is moving {direction}! 🚨",
        description=f"**{coin_id.capitalize()}** has moved by **{change_1h:.2f}%** in the last hour.",
        color=color,
        timestamp=datetime.datetime.utcnow()
    )
    
    # Find the coin's symbol and thumbnail for a richer embed
    try:
        coin_info = cg.get_coin_by_id(coin_id)
        if 'image' in coin_info and 'thumb' in coin_info['image']:
            embed.set_thumbnail(url=coin_info['image']['thumb'])
    except Exception:
        pass # Ignore if we can't fetch extra info

    embed.add_field(name="Current Price", value=f"${price:,.4f}", inline=True)
    embed.add_field(name="24h Change", value=f"{change_24h:.2f}%", inline=True)
    embed.add_field(name="Market Cap", value=f"${int(market_cap):,}", inline=True)
    embed.set_footer(text="Data from CoinGecko | Not Financial Advice")
    
    return embed

@check_price_movements.before_loop
async def before_check():
    """Ensures the bot is fully ready before starting the loop."""
    await bot.wait_until_ready()


# --- Run the bot ---
bot.run(TOKEN)