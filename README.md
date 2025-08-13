# Market Pulse Bot

**Real-time Discord bot that reads market data, analyzes key metrics (OR levels, σ, RSI, VWAP, options flow), and posts concise, actionable summaries for traders. Designed for fast insights during market hours with customizable channels and secure `.env` configuration.**

## Features
- Pulls live market data from Yahoo Finance (`yfinance`).
- Parses metrics: price vs. Opening Range, standard deviation levels, RSI, VWAP.
- Tracks options flow (volume vs. open interest).
- Auto-generates trade bias (long/short/neutral).
- Posts to Discord with a clean, readable format.
- Configurable via `.env`.

## Requirements
- Python 3.10+
- Discord bot token & webhook URL
- Installed dependencies from `requirements.txt`:
  ```bash
  pip install -r requirements.txt
  ```

## Setup
1. Clone the repo:
   ```bash
   git clone https://github.com/yourusername/market-pulse-bot.git
   cd market-pulse-bot
   ```
2. Create `.env` file:
   ```env
   DISCORD_BOT_TOKEN=your_token_here
   DISCORD_WEBHOOK_URL=your_webhook_here
   TIMEZONE_OFFSET=-7
   ```
3. Run:
   ```bash
   python market_pulse_patched.py
   ```

## License
See [LICENSE](LICENSE) for details.