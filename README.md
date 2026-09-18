# Earning Wallah Scheduler

Self-hosted Telegram channel scheduler. No post-count limit is built into the bot.

## Supports
- Photo + caption
- One URL button
- Daily recurring posts
- Weekly recurring posts
- Asia/Kolkata (IST)
- SQLite persistence
- Docker

## Setup
1. Create a bot with @BotFather and copy its token.
2. Get your numeric Telegram user ID (for example with @userinfobot).
3. Copy `.env.example` to `.env` and fill both values.
4. Add your bot as an administrator of Earning Wallah with permission to post messages.
5. Run:
   `docker compose up -d --build`
6. Open your bot and send `/start`, then `/add`.

Important: this is self-hosted software. The software itself has no 50-post quota; your hosting provider can still have its own limits/costs.
