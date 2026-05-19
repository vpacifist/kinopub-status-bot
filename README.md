# Kinopub Telegram status bot

Telegram bot that checks `https://kino.pub/` every minute.

- If the site returns HTTP `404`, any `5xx` status, the known internal-server-error page, or cannot be reached, status becomes `down` and subscribers get one `kinopub is down` notification.
- If the response takes longer than `SLOW_RESPONSE_SECONDS` seconds, it is also treated as `down`.
- Set `CHECK_COOKIE` to a browser session cookie if you want to check the authenticated app instead of only the public login page.
- While it stays `down`, the bot keeps checking every minute without repeating the down notification.
- When the site returns `RECOVERY_CONFIRMATION_CHECKS` healthy responses in a row, status becomes `alive` and subscribers get `kinopub is alive`.
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
