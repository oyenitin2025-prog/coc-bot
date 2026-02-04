import os
import re
import json
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =================================
# CONFIG
# =================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise Exception("BOT_TOKEN missing in Railway variables")

DATA_FILE = "data.json"


# =================================
# STORAGE
# =================================

def load_data():
    if not os.data_file.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)


def get_user_accounts(uid):
    data = load_data()
    return data.get(uid, {})


def add_account(uid, name):
    data = load_data()
    data.setdefault(uid, {})
    data[uid][name] = {}
    save_data(data)


# =================================
# TIME PARSER
# =================================

def parse_time(text):
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


# =================================
# START MENU (FIXED)
# =================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)

    accounts = get_user_accounts(uid)

    keyboard = []

    for acc in accounts:
        keyboard.append(
            [InlineKeyboardButton(f"🏰 {acc}", callback_data=f"account|{acc}")]
        )

    keyboard.append([InlineKeyboardButton("➕ Add Account", callback_data="add")])

    await update.message.reply_text(
        "🏰 *Clash Builder Tracker*\n\nSelect account:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =================================
# ADD ACCOUNT
# =================================

async def add_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["adding"] = True
    await update.callback_query.message.reply_text("✏️ Send account name:")


async def handle_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("adding"):
        return

    uid = str(update.effective_user.id)
    name = update.message.text

    add_account(uid, name)

    context.user_data["adding"] = False

    await update.message.reply_text(f"✅ Added {name}\nUse /start")


# =================================
# ACCOUNT MENU
# =================================

async def account_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    account = query.data.split("|")[1]
    context.user_data["selected"] = account

    keyboard = [
        [InlineKeyboardButton("🧱 Builders", callback_data="builders")],
        [InlineKeyboardButton("⬅️ Back", callback_data="back")]
    ]

    await query.message.reply_text(
        f"📌 *{account}*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =================================
# BUILDERS
# =================================

async def builders_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["builders"] = True

    await update.callback_query.message.reply_text(
        "🧱 Send 6 builder times\n\nExample:\n2h 1h 30m 0 5h 3h"
    )


async def handle_builders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("builders"):
        return

    context.user_data["builders"] = False

    now = datetime.now()
    parts = update.message.text.split()

    messages = []

    for i, t in enumerate(parts, start=1):
        delta = parse_time(t)

        if delta.total_seconds() == 0:
            continue

        finish = now + delta

        messages.append(
            f"🧱 Builder {i} → {finish.strftime('%H:%M %d %b')}"
        )

        async def reminder(ctx, chat_id=update.effective_chat.id, idx=i):
            await ctx.bot.send_message(chat_id, f"⏰ Builder {idx} finished!")

        context.job_queue.run_once(reminder, delta.total_seconds())

    if not messages:
        await update.message.reply_text("❌ Invalid format")
        return

    await update.message.reply_text("\n".join(messages))


# =================================
# MAIN
# =================================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(add_click, pattern="add"))
    app.add_handler(CallbackQueryHandler(account_click, pattern="account"))
    app.add_handler(CallbackQueryHandler(builders_click, pattern="builders"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_account))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_builders))

    print("🚀 Bot running...")

    app.run_polling()


if __name__ == "__main__":
    main()
