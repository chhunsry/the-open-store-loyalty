# The Open Store Loyalty Points

A complete customer loyalty system with a responsive public points checker,
secure admin dashboard, permanent point history, and Telegram bot.

## What is included

- Public phone-number lookup (only name and current points are shown)
- Admin login with hashed passwords, signed secure cookies, CSRF protection,
  server-side validation, and parameterized database queries
- Create/update customers and search by name or phone
- Add or subtract points without allowing negative balances
- Full immutable point history with note, balance, date, and acting admin
- Telegram customer command plus admin-only lookup and point adjustments
- SQLite by default; the service layer is small enough to migrate to PostgreSQL

## Quick start

Requires Python 3.9 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` before the first start. Generate `APP_SECRET` with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set a strong `DEFAULT_ADMIN_PASSWORD`. The initial admin is created only if
that username does not already exist. Production secrets are never included in
source control.

Start the website:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000`. For production, enable HTTPS and set
`COOKIE_SECURE=true`.

You can later create or reset an administrator interactively:

```bash
python -m app.create_admin admin
```

## Add the store logo

The referenced upload was unavailable when this package was built. Copy the
original image to `app/static/logo.jpg`; no code change is needed. The UI uses
a branded fallback mark until then.

## Telegram bot setup

1. Message `@BotFather` in Telegram, create a bot, and copy the token.
2. Put the token in `TELEGRAM_BOT_TOKEN`.
3. Put permitted Telegram numeric user IDs in `TELEGRAM_ADMIN_IDS`, separated
   by commas. You can obtain your ID from a trusted Telegram ID bot.
4. Start the bot in a second process:

```bash
python -m app.bot
```

Commands:

- `/start` or `/help` — instructions and business link
- `/points PHONE` — public customer balance lookup
- `/customer PHONE` — admin lookup
- `/add PHONE AMOUNT [note]` — admin adds points
- `/subtract PHONE AMOUNT [note]` — admin subtracts points

The website and bot must share the same `DATABASE_PATH`. Polling is ideal for a
small deployment. On platforms that sleep processes, run the web and bot as
separate always-on services.

## Deployment

For a simple deployment, use Render, Railway, Fly.io, or a small VPS with a
persistent disk mounted for `DATABASE_PATH`. Run the web and bot as separate
processes using the same persistent volume. SQLite is suitable for one server.
For multiple web instances, migrate the small SQL layer to PostgreSQL.

Environment checklist:

- Use a unique 32+ character `APP_SECRET`
- Use a strong admin password and remove it from the environment after seeding
  if your platform permits
- Set `COOKIE_SECURE=true` behind HTTPS
- Restrict `TELEGRAM_ADMIN_IDS` to trusted accounts
- Back up the database file regularly

## Tests

```bash
pip install pytest
pytest -q
```
