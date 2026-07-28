import logging
import os

from dotenv import load_dotenv
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Update,
    WebAppInfo,
)
from telegram.ext import Application, CommandHandler, ContextTypes

from app.database import init_db
from app.services import ValidationError, change_points, get_customer_by_phone

load_dotenv()
logging.basicConfig(level=logging.INFO)


def admin_ids() -> set[int]:
    values = os.getenv("TELEGRAM_ADMIN_IDS", "")
    return {int(value.strip()) for value in values.split(",") if value.strip().isdigit()}


def is_admin(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id in admin_ids())


def web_url() -> str:
    return os.getenv(
        "PUBLIC_BASE_URL", "https://the-open-store-loyalty.onrender.com"
    ).rstrip("/")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton(
                "🌷 Open Rewards Website",
                web_app=WebAppInfo(url=web_url()),
            )
        ]]
    )
    await update.message.reply_text(
        "🌷 Welcome to The Open Store Rewards!\n\n"
        "Tap the button below to check your points, or send:\n"
        "/points +85512345678\n\n"
        "Visit us: https://linktr.ee/theopenstore",
        reply_markup=keyboard,
    )


async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Your Telegram user ID is: {update.effective_user.id}"
    )


async def lookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /points +85512345678")
        return
    try:
        customer = get_customer_by_phone(context.args[0])
        if not customer:
            await update.message.reply_text("No customer was found with that phone number.")
            return
        await update.message.reply_text(
            f"✨ {customer['name']}\n"
            f"Current balance: {customer['points']:,} points\n"
            "Thank you for shopping with The Open Store!"
        )
    except ValidationError as exc:
        await update.message.reply_text(str(exc))


async def admin_customer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("This command is for store admins only.")
        return
    await lookup(update, context)


async def adjust(update: Update, context: ContextTypes.DEFAULT_TYPE, sign: int):
    if not is_admin(update):
        await update.message.reply_text("This command is for store admins only.")
        return
    if len(context.args) < 2:
        command = "add" if sign > 0 else "subtract"
        await update.message.reply_text(f"Usage: /{command} PHONE AMOUNT [note]")
        return
    try:
        customer = get_customer_by_phone(context.args[0])
        if not customer:
            await update.message.reply_text("Customer not found. Create them in the dashboard first.")
            return
        amount = int(context.args[1]) * sign
        note = " ".join(context.args[2:])
        result = change_points(
            customer["id"],
            amount,
            note,
            f"telegram:{update.effective_user.id}",
        )
        await update.message.reply_text(
            f"✅ Updated {result['name']}: {amount:+,} points\n"
            f"New balance: {result['points']:,} points"
        )
    except (ValidationError, ValueError) as exc:
        await update.message.reply_text(f"Could not update points: {exc}")


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await adjust(update, context, 1)


async def subtract(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await adjust(update, context, -1)


async def configure_bot(application: Application):
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Open The Open Store Rewards"),
            BotCommand("points", "Check points using a phone number"),
            BotCommand("myid", "Show your Telegram user ID"),
            BotCommand("help", "Show bot instructions"),
        ]
    )
    await application.bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="Rewards",
            web_app=WebAppInfo(url=web_url()),
        )
    )


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in .env before starting the bot.")
    init_db()
    application = Application.builder().token(token).post_init(configure_bot).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("myid", myid))
    application.add_handler(CommandHandler("points", lookup))
    application.add_handler(CommandHandler("customer", admin_customer))
    application.add_handler(CommandHandler("add", add))
    application.add_handler(CommandHandler("subtract", subtract))
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
