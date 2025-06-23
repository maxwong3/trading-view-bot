# TradingView Discord Bot

Receives webhook alerts from TradingView with Flask web server, with a discord bot thread with discord.py that is ran simulataneously to run the bot and send these alerts.

.gitignore ignores .env that contains discord bot key.

developed on Python 3.13.4

Max: Main bot receiving TradingView webhooks (main.py). Deployed on Render and monitored with UptimeRobot.

Kevin: Script to deploy CoinGecko alerts with discord webhooks (market_scanner.py)
