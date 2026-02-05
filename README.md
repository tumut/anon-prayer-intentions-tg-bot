# anon-prayer-intentions-tg-bot

## Environment variables

| Name                | Value                                                                    |
| ------------------- | ------------------------------------------------------------------------ |
| TELEGRAM_BOT_TOKEN  | Bot token obtained through Telegram                                      |
| ACTIVATION_PASSWORD | A string with the password to be used when activating the bot in a group |
| REDIS_HOST          | Redis host (default should be 'localhost' locally, 'redis' in Docker)    |
| REDIS_PORT          | Redis port (default should be 6379)                                      |

## Running with Docker

1. Create a `.env` file:

```
TELEGRAM_BOT_TOKEN=...
ACTIVATION_PASSWORD=...
REDIS_HOST=redis
REDIS_PORT=6379
```

2. Build and run:

```
docker compose up --build
```

This will start the Telegram bot and a Redis instance.

## Running locally

### Requirements

- Python 3.10+
- Redis

### Setup

1. Create a virtual environment:

   ```
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```
   pip install -r requirements.txt
   ```

3. Create a `.env` file:

   ```
   TELEGRAM_BOT_TOKEN=...
   ACTIVATION_PASSWORD=...
   REDIS_HOST=localhost
   REDIS_PORT=6379
   ```

4. Start Redis (if not already running):

   ```
   redis-server
   ```

5. Run the bot:

   ```
   python main.py
   ```
