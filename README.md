# anon-prayer-intentions-tg-bot

Requirements:

- `pip install python-dotenv python-telegram-bot redis`
- Redis

The `.env` must have the following variables:

| Name                | Value                                                                    |
| ------------------- | ------------------------------------------------------------------------ |
| TELEGRAM_BOT_TOKEN  | Bot token obtained through Telegram                                      |
| ACTIVATION_PASSWORD | A string with the password to be used when activating the bot in a group |
| REDIS_HOST          | Redis host (default should be 'localhost')                               |
| REDIS_PORT          | Redis port (default should be 6379)                                      |
