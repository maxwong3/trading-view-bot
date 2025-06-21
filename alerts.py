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

# It's good practice to define intents
intents = discord.Intents.default()
intents.message_content = True 

bot = commands.Bot(command_prefix='!', intents=intents)

# Initialize the CoinGecko API client
cg = CoinGeckoAPI()

# --- Configuration ---
# You can easily change these settings
CONFIG = {
    'ALERT_CHANNEL_ID': 1385799309211078737,      # <<< IMPORTANT: REPLACE WITH YOUR CHANNEL ID
    'TOP_N_COINS': 20,              # Number of top coins to monitor
    'PRICE_CHANGE_THRESHOLD': 1.0,  # Alert if price moves by this % or more
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
        print(f"[{datetime.datetime.now()}] Checking for major price movements...")

        # 1. Get the list of top N coins by market cap
        markets = cg.get_coins_markets(
            vs_currency='usd',
            order='market_cap_desc',
            per_page=CONFIG['TOP_N_COINS'],
            page=1
        )
        coin_ids = [coin['id'] for coin in markets]

        # 2. Get the simple price for all these coins in one API call
        # We request the 1-hour percentage change, which is key for this scanner
        price_data = cg.get_price(
            ids=coin_ids,
            vs_currencies='usd',
            include_market_cap='true',
            include_24hr_vol='true',
            include_24hr_change='true',
            include_last_updated_at='true',
            precision=8,
            include_1h_change='true' # This is the crucial part for our check
        )

        alert_channel = bot.get_channel(CONFIG['ALERT_CHANNEL_ID'])
        if not alert_channel:
            print(f"ERROR: Channel with ID {CONFIG['ALERT_CHANNEL_ID']} not found. Halting check.")
            return

        # 3. Iterate through each coin and check for significant movement
        for coin_id, data in price_data.items():
            change_1h = data.get('usd_1h_change')

            if change_1h is None:
                continue # Skip if data is not available

            # Check if the coin is currently on cooldown
            if coin_id in recent_alerts:
                cooldown_time = datetime.timedelta(hours=CONFIG['ALERT_COOLDOWN_HOURS'])
                if datetime.datetime.utcnow() - recent_alerts[coin_id] < cooldown_time:
                    continue # Still on cooldown, skip to the next coin

            # 4. Check if the movement exceeds our threshold
            if abs(change_1h) >= CONFIG['PRICE_CHANGE_THRESHOLD']:
                print(f"!!! Significant movement detected for {coin_id}: {change_1h:.2f}%")
                
                # Update the cooldown timer for this coin immediately
                recent_alerts[coin_id] = datetime.datetime.utcnow()
                
                # 5. Create and send the alert embed
                embed = create_movement_embed(
                    coin_id=coin_id,
                    price=data.get('usd', 0),
                    change_1h=change_1h,
                    change_24h=data.get('usd_24h_change', 0),
                    market_cap=data.get('usd_market_cap', 0)
                )
                await alert_channel.send(embed=embed)

    except Exception as e:
        print(f"An error occurred in the check_price_movements loop: {e}")

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