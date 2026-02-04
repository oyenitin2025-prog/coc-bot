import os
import re
import json
import asyncio
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# =============================
# CONFIG
# =============================

BOT_TOKEN = os.getenv("BOT_TOKEN")  # ← comes from Railway variable

if not BOT_TOKEN:
    raise Exception("BOT_TOKEN not found in environment variables")

DATA_FILE = "data.json"


# =============================
# STORAGE
# =============================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)


data = load_data()


# =============================
# TIME PARSER (any d/h/m)
# =============================

def parse_time(text: str):
    """
    Accepts:
    2h 3h 30m 1d 0 5h etc
    """

    total = timedelta()

    for part in text.split():
        if part == "0":
            continue

        match = re.match(r"(\d+)([dhm])", part.lower())
        if not match:
            continue

        value, unit = match.groups()
        value = int(value)

        if unit == "d":
            total += timedelta(days=value)
        elif unit == "h":
            total += timedelta(hours=value)
        elif unit == "m":
            total += timedelta(minutes=value)

    return total


# =============================
# START MENU
# =============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("➕ Add Account", callback_data="add_account")]
    ]

    await update.message.reply_text(
        "🏰 *Clash Builder Tracker*\n\nSelect account:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


# =============================
# ADD ACCOUNT
# =============================

async def add_account_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("✏️ Send account name:")
    context.user_data["adding_account"] = True


async def handle_account_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("adding_account"):
        return

    name = update.message.text
    uid = str(update.effective_user.id)

    data.setdefault(uid, {})
    data[uid][name] = {}

    save_data(data)

    context.user_data["adding_account"] = False

    await update.message.reply_text(
        f"✅ Added *{name}*\nUse /start",
        parse_mode="Markdown"
    )


# =============================
# ACCOUNT MENU
# =============================

async def account_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    account = query.data.split("|")[1]
    context.user_data["selected_account"] = account

    keyboard = [
        [InlineKeyboardButton("🧱 Builders", callback_data="builders")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    ]

    await query.message.reply_text(
        f"📌 *{account}*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


# =============================
# BUILDERS CLICK
# =============================

async def builders_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

    context.user_data["waiting_builders"] = True

    await update.callback_query.message.reply_text(
        "🧱 Send builder times\n\nExample:\n2h 1h 30m 0 5h 3h"
    )


# =============================
# HANDLE BUILDER TIMES
# =============================

async def handle_builders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_builders"):
        return

    context.user_data["waiting_builders"] = False

    times = update.message.text.split()
    now = datetime.now()

    messages = []

    for i, t in enumerate(times, start=1):
        delta = parse_time(t)

        if delta.total_seconds() == 0:
            continue

        finish = now + delta

        messages.append(
            f"🧱 Builder {i} → {finish.strftime('%H:%M %d %b')}"
        )

        # reminder
        async def reminder(ctx):
            await ctx.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"⏰ Builder {i} finished!"
            )

        context.job_queue.run_once(reminder, delta.total_seconds())

    if not messages:
        await update.message.reply_text("❌ No valid times found")
        return

    await update.message.reply_text("\n".join(messages))


# =============================
# MAIN
# =============================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(add_account_click, pattern="add_account"))
    app.add_handler(CallbackQueryHandler(builders_click, pattern="builders"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_account_name))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_builders))

    print("🚀 Bot running...")

    app.run_polling()


if __name__ == "__main__":
    main()
