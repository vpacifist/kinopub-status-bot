# Kinopub Telegram status bot

Telegram bot that checks `https://kino.pub/` every minute.

- If the site returns HTTP `404`, any `5xx` status, or cannot be reached, status becomes `down` and subscribers get one `kinopub is down` notification.
- While it stays `404`, the bot keeps checking every minute without repeating the down notification.
- When the site returns anything other than `404`, status becomes `alive` and subscribers get `knopub is alive`.
- `/status` replies with the current status and subscribes that chat for future alerts.
- `/start` subscribes the chat.
- `/stop` unsubscribes the chat.

## Run locally

PowerShell:

```powershell
$env:TELEGRAM_BOT_TOKEN="your-token-here"
python .\kinopub_bot.py
```

Or create a local `.env` file and load it before starting the bot.

The bot stores state in `kinopub_bot_state.json`.
