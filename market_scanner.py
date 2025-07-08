# market_scanner.py
from pycoingecko import CoinGeckoAPI
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import os
import datetime
import traceback
import pandas as pd, ta, aiohttp, asyncio


# --- Basic Setup ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
API_KEY = os.getenv("COINGECKO_API_KEY", None)
if not API_KEY:
    raise RuntimeError("Missing Coingecko API key in .env file")

cg = CoinGeckoAPI(api_key=API_KEY)

# Discord intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# --- Configuration ---
CONFIG = {
    "ALERT_CHANNEL_ID": 1385799309211078737,  # <— REPLACE WITH YOUR CHANNEL ID
    "TOP_N_COINS": 10,                 # <-- Replace with how many coins you want to track
    "PRICE_CHANGE_THRESHOLD": 7,       # % movement to trigger alert
    "CHECK_INTERVAL_MINUTES": 30,      # how often we poll
    "ALERT_COOLDOWN_HOURS": 0.1        # time before a new alert for same coin/period
}
SIGNAL_CONFIG = {
    # Bullish Signals (Green)
    'price_above_ema200': {
        'title': '📈 Price Cross Above EMA 200',
        'description': 'Price has crossed above the 200-period Exponential Moving Average.',
        'color': 0x00ff00  # Green
    },
    'cross_above_sma200': {
        'title': '📈 Price Cross Above SMA 200',
        'description': 'Price has crossed above the 200-period Simple Moving Average.',
        'color': 0x00ff00
    },
    'cross_above_vwap': {
        'title': '📈 Price Cross Above VWAP',
        'description': 'Price has crossed above the Volume-Weighted Average Price.',
        'color': 0x00ff00
    },
    '20p_high_break': {
        'title': '📈 New 20-Period High',
        'description': 'Price has broken above the high of the last 20 periods.',
        'color': 0x00ff00
    },
    'ema9_above_ema21': {
        'title': '📈 Bullish EMA Cross (9/21)',
        'description': 'The 9-period EMA has crossed above the 21-period EMA.',
        'color': 0x00ff00
    },
    'golden_cross': {
        'title': '🚀 GOLDEN CROSS (50/200 EMA)',
        'description': 'A major bullish signal: The 50-period EMA has crossed above the 200-period EMA.',
        'color': 0xffd700  # Gold
    },

    # Bearish Signals (Red)
    'price_below_ema200': {
        'title': '📉 Price Cross Below EMA 200',
        'description': 'Price has crossed below the 200-period Exponential Moving Average.',
        'color': 0xff0000  # Red
    },
    'cross_below_sma200': {
        'title': '📉 Price Cross Below SMA 200',
        'description': 'Price has crossed below the 200-period Simple Moving Average.',
        'color': 0xff0000
    },
    'cross_below_vwap': {
        'title': '📉 Price Cross Below VWAP',
        'description': 'Price has crossed below the Volume-Weighted Average Price.',
        'color': 0xff0000
    },
    '20p_low_break': {
        'title': '📉 New 20-Period Low',
        'description': 'Price has broken below the low of the last 20 periods.',
        'color': 0xff0000
    },
    'ema9_below_ema21': {
        'title': '📉 Bearish EMA Cross (9/21)',
        'description': 'The 9-period EMA has crossed below the 21-period EMA.',
        'color': 0xff0000
    },
    'death_cross': {
        'title': '💀 DEATH CROSS (50/200 EMA)',
        'description': 'A major bearish signal: The 50-period EMA has crossed below the 200-period EMA.',
        'color': 0x8b0000  # Dark Red
    }
}
# --- Cool‑down state ---
# Keyed by (coin_id, period) → last‑alert UTC timestamp
recent_alerts: dict[tuple[str, str], datetime.datetime] = {}

def cooldown_ok(key: tuple[str, str]) -> bool:
    """True if enough time has passed since last alert for this key."""
    last = recent_alerts.get(key, datetime.datetime.min.replace(tzinfo=datetime.UTC)) # Add tzinfo for comparison
    return (
        datetime.datetime.now(datetime.UTC) - last
        >= datetime.timedelta(hours=CONFIG["ALERT_COOLDOWN_HOURS"])
    )
#--------------------------------------------------------------------------------------------

async def send_discord_embed(coin_id: str, period: str, title: str, description: str, color: int):
    embed = discord.Embed(
        title = f"{title} occurred on the {period} time frame",
        description = description,
        color = color
    )
    print("Sending discord embed for moving average signals")
    alert_channel = bot.get_channel(CONFIG["ALERT_CHANNEL_ID"])
    if not alert_channel:
        print("!!! Cannot find alert channel. Check ALERT_CHANNEL_ID.")
        return
    await alert_channel.send(embed = embed)

#crossing above and below helper functions
def cross_above(series,level):
    return((series.shift(1) <= level.shift(1)) & (series > level))
def cross_below(series, level):
    return((series.shift(1) >= level.shift(1)) & (series < level))
#----------------------------------------------------------

def fetch_and_analyze(coin_id: str, days: int = 30) -> pd.DataFrame:
    """
    Fetches historical data for a coin from CoinGecko and returns a
    DataFrame with a full set of technical indicators and trading signals.
    """
    # Step 1: Fetch the data
    try:
        data = cg.get_coin_market_chart_by_id(
            coin_id,
            vs_currency="usd",
            days=days,
            interval="hourly"
        )
    except Exception as e:
        print(f"Error fetching data for {coin_id}: {e}")
        return pd.DataFrame() 

    prices = data.get("prices", [])
    volumes = data.get("total_volumes", [])
    if not prices or not volumes:
        return pd.DataFrame() 

    df = pd.DataFrame({
        "time":   [p[0] for p in prices],
        "close":  [p[1] for p in prices],
        "volume": [v[1] for v in volumes],
    })
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    df = df.set_index("time").sort_index()

    # Calculate ALL indicators and signals
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    df["ema_9"]   = df["close"].ewm(span=9,   adjust=False).mean()
    df["ema_21"]  = df["close"].ewm(span=21,  adjust=False).mean()
    df["ema_50"]  = df["close"].ewm(span=50,  adjust=False).mean()
    df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()
    df['sma_200'] = df['close'].rolling(window=200).mean()
    df["20p_high"] = df["close"].rolling(20).max()
    df["20p_low"]  = df["close"].rolling(20).min()
    df["vwap"] = (df["close"] * df["volume"]).groupby(df.index.date).cumsum() / df["volume"].groupby(df.index.date).cumsum()
    #Check for crossing signals
    df['price_above_ema200'] = cross_above(df['close'], df['ema_200'])
    df['price_below_ema200'] = cross_below(df['close'], df['ema_200'])
    df['cross_above_sma200'] = cross_above(df['close'], df['sma_200'])
    df['cross_below_sma200'] = cross_below(df['close'], df['sma_200'])
    df['cross_above_vwap']   = cross_above(df['close'], df['vwap'])
    df['cross_below_vwap']   = cross_below(df['close'], df['vwap'])
    df['20p_high_break']     = df['close'] > df['20p_high'].shift(1)
    df['20p_low_break']      = df['close'] < df['20p_low'].shift(1) 
    df['ema9_above_ema21']   = cross_above(df['ema_9'], df['ema_21'])
    df['ema9_below_ema21']   = cross_below(df['ema_9'], df['ema_21'])
    df['golden_cross']      = cross_above(df['ema_50'], df['ema_200'])
    df['death_cross']       = cross_below(df['ema_50'], df['ema_200'])

    return df
# --------------------------------------------------------
async def check_and_send_alerts(coin_id: str, period: str, latest_signals: pd.Series):
    """Checks the latest signals for a coin and sends alerts if triggers are met."""
    print(f"Checking signals for {coin_id.upper()} on the {period} timeframe..") 
    for signal_name, descr in SIGNAL_CONFIG.items():
        if latest_signals.get(signal_name) == True:
            cooldown_key = (coin_id, signal_name, period)
            if cooldown_ok(cooldown_key):
                print(f"✅ ALERT TRIGGERED for {coin_id}: {signal_name}")
                
                # Use the 'descr' variable from the loop to get the details
                alert_title = descr['title']
                alert_descr = descr['description']
                alert_color = descr['color']
                await send_discord_embed(coin_id, period, alert_title, alert_descr, alert_color)
                recent_alerts[cooldown_key] = datetime.datetime.now(datetime.UTC)
#--------------------------------------------------------------
@bot.event
async def on_ready():
    print(f"{bot.user.name} is now running!")
    print("CoinGecko ping:", cg.ping())
    check_price_movements.start()

# ---------------------------------------------------------
@tasks.loop(minutes=CONFIG["CHECK_INTERVAL_MINUTES"])
async def check_price_movements():
    try:
        print(f"[{datetime.datetime.now(datetime.UTC)}] — New market scan")
        alert_channel = bot.get_channel(CONFIG["ALERT_CHANNEL_ID"])
        if not alert_channel:
            print("!!! Cannot find alert channel. Check ALERT_CHANNEL_ID.")
            return
        

        markets = cg.get_coins_markets(
            vs_currency="usd",
            order="market_cap_desc",
            per_page=CONFIG["TOP_N_COINS"],
            page=1,
            price_change_percentage="1h,24h,7d",
        )

        for coin in markets:
            coin_id   = coin["id"]
            change_1h = coin.get("price_change_percentage_1h_in_currency")
            change_24h= coin.get("price_change_percentage_24h_in_currency")
            change_7d = coin.get("price_change_percentage_7d_in_currency")
            if None in (coin_id, change_1h, change_24h, change_7d):
                continue  # skip incomplete data
            df = await bot.loop.run_in_executor(
                None,
                fetch_price_history,
                coin_id, 7
                )
            rsi_value = await bot.loop.run_in_executor(None, latestrsi, df, 14)
            if rsi_value > 70:
                rsi_label = "Overbought 📈"
            elif rsi_value < 30:
                rsi_label = "Oversold 📉"
            else:
                rsi_label = f"RSI {rsi_value:.1f}"
            cg_technical = fetch_and_analyze(df)
            if cg_technical['price_above']



            # Build embeds once per coin
            hourembed = create_movement_embed(
                coin_id=coin_id,
                price=coin["current_price"],
                market_cap=coin["market_cap"],
                change_1h=change_1h,
                rsi_label=rsi_label,
                rsi_value = rsi_value
            )
            dayembed = create_movement_embed(
                coin_id=coin_id,
                price=coin["current_price"],
                market_cap=coin["market_cap"],
                change_24h=change_24h,
                rsi_label=rsi_label,
                rsi_value = rsi_value
            )
            weekembed = create_movement_embed(
                coin_id=coin_id,
                price=coin["current_price"],
                market_cap=coin["market_cap"],
                change_7d=change_7d,
                rsi_label=rsi_label,
                rsi_value = rsi_value
            )

            # ---- 1‑hour alert ----
            hour_key = (coin_id, "1h")
            if abs(change_1h) >= CONFIG["PRICE_CHANGE_THRESHOLD"] and cooldown_ok(hour_key) and (rsi_value > 70 or rsi_value < 30):
                await alert_channel.send(embed=hourembed)
                recent_alerts[hour_key] = datetime.datetime.now(datetime.UTC)

            # ---- 24‑hour alert ----
            day_key = (coin_id, "24h")
            if abs(change_24h) >= CONFIG["PRICE_CHANGE_THRESHOLD"] and cooldown_ok(day_key) and (rsi_value > 70 or rsi_value < 30):
                await alert_channel.send(embed=dayembed)
                recent_alerts[day_key] = datetime.datetime.now(datetime.UTC)

            # ---- 7‑day alert ----
            week_key = (coin_id, "7d")
            if abs(change_7d) >= CONFIG["PRICE_CHANGE_THRESHOLD"] and cooldown_ok(week_key) and (rsi_value > 70 or rsi_value < 30):
                await alert_channel.send(embed=weekembed)
                recent_alerts[week_key] = datetime.datetime.now(datetime.UTC)
            
            await asyncio.sleep(2)

    except Exception:
        traceback.print_exc()

# ---------------------------------------------------------
def create_movement_embed(*,
    coin_id: str,
    price: float,
    market_cap: float,
    rsi_label: str,
    rsi_value: float,
    change_1h: float | None = None,
    change_24h: float | None = None,
    change_7d: float | None = None,
):
    if change_1h is not None:
        change, period = change_1h, "1 Hour"
    elif change_24h is not None:
        change, period = change_24h, "24 Hours"
    elif change_7d is not None:
        change, period = change_7d, "7 Days"
    else:
        raise ValueError("Must supply at least one change value")

    color = discord.Color.green() if change >= 0 else discord.Color.red()
    direction = "UP" if change >= 0 else "DOWN"

    embed = discord.Embed(
        title=f"🚨 {coin_id.upper()} moving {direction}! 🚨",
        description=(f"**{coin_id.upper()}** moved **{change:+.2f}%** "
                     f"over the last {period}.") ,
        color=color,
        timestamp=datetime.datetime.now(datetime.UTC),
    )
    embed.add_field(name="Current Price", value=f"${price:,.4f}")
    embed.add_field(name=f"{period} Change", value=f"{change:+.2f}%")
    embed.add_field(name="Market Cap", value=f"${int(market_cap):,}")
    embed.add_field(name="RSI", value=rsi_label, inline=False)
    embed.add_field(name="RSI_VALUE", value=rsi_value, inline=False)
    return embed

# ---------------------------------------------------------
@check_price_movements.before_loop
async def before_check():
    await bot.wait_until_ready()

# ---------------------------------------------------------
# Simple slash command: top gainers/losers (24 h)
@bot.command(name="topgainerloser24hr")
async def top_gainers(ctx):
    try:
        await ctx.send("Fetching top gainers and losers…")
        results = cg.get_coin_top_gainers_losers("usd")
        gainers = results.get("top_gainers", [])[:10]
        losers  = results.get("top_losers",  [])[:10]

        def fmt(entry):
            return (
                f"**{entry.get('name','?')}** "
                f"({entry.get('symbol','?').upper()}) — "
                f"{entry.get('usd_24h_change',0):+.2f}%"
            )

        embed = discord.Embed(
            title="24‑Hour Top Gainers / Losers",
            color=discord.Color.purple(),
            timestamp=datetime.datetime.now(datetime.UTC),
        )
        embed.add_field(name="🚀 Gainers", value="\n".join(map(fmt, gainers)) or "No data", inline=False)
        embed.add_field(name="📉 Losers",  value="\n".join(map(fmt, losers))  or "No data", inline=False)
        await ctx.send(embed=embed)
    except Exception:
        traceback.print_exc()
        await ctx.send("Error fetching gainers/losers.")

# ---------------------------------------------------------
if __name__ == "__main__":
    bot.run(TOKEN)